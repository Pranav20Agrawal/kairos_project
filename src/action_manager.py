# src/action_manager.py

import webbrowser
import pyautogui
import pyperclip
import string
import time
import os
import subprocess
import sys
import requests
import pygetwindow as gw
import psutil
import pytesseract
import re
from datetime import datetime
from PySide6.QtCore import QObject, Signal
from src.context_manager import ContextManager
from src.settings_manager import SettingsManager
from src.llm_handler import LlmHandler
from src.speaker_worker import SpeakerWorker
from src.personality_manager import PersonalityManager  # <-- ADD THIS IMPORT
from PySide6.QtWidgets import QMessageBox
import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from pathlib import Path
import threading
import importlib.util
import inspect
import asyncio
import ollama  # Added for memory query LLM calls

# Forward declaration for type hinting
if TYPE_CHECKING:
    from src.memory_manager import MemoryManager

# --- FINAL FIX: Added win32clipboard for robust file path copying ---
if sys.platform == "win32":
    import win32clipboard

from src.automations.whatsapp_automation import send_whatsapp_message
from RestrictedPython import compile_restricted
from RestrictedPython.Guards import safe_builtins, full_write_guard
from src.plugin_interface import BasePlugin
import src.primitives as primitives
from src import wifi_manager
from src import file_handler
from src.spotify_manager import SpotifyManager
from src import bluetooth_manager
from src import hotspot_manager


logger = logging.getLogger(__name__)


class ActionManager(QObject):
    ocr_requested = Signal()

    def __init__(self, settings_manager: SettingsManager, interrupt_event: threading.Event, speaker_worker: SpeakerWorker, api_manager, memory_manager: "MemoryManager") -> None:
        super().__init__()
        self.settings_manager: SettingsManager = settings_manager
        self.context_manager: ContextManager = ContextManager()
        self.llm_handler: LlmHandler | None = None
        self.speaker_worker = speaker_worker
        self.interrupt_event = interrupt_event
        self.api_manager = api_manager
        self.memory_manager = memory_manager  # <-- ADDED MEMORY MANAGER
        self.personality_manager = PersonalityManager(self.settings_manager)  # <-- ADD THIS LINE
        self.last_received_file: Optional[Path] = None
        self.current_emotion: str = "neu"
        self.spotify_manager = SpotifyManager()

        try:
            self.llm_handler = LlmHandler(settings_manager=self.settings_manager)
        except Exception as e:
            logger.error(f"Failed to initialize a component: {e}", exc_info=True)

        self.uwp_apps: Dict[str, str] = {
            "spotify": "shell:appsfolder\\SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"
        }
        self.action_map = {}
        self.macros = {}
        self.site_map = {}
        self._load_plugins()
        self.reload_maps()
        self.settings_manager.settings_updated.connect(self.reload_maps)

    def _load_plugins(self):
        plugins_dir = Path("plugins")
        if not plugins_dir.exists():
            return
        logger.info("Loading plugins...")
        for file_path in plugins_dir.glob("*.py"):
            if file_path.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    for _, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, BasePlugin) and obj is not BasePlugin:
                            instance = obj(speaker_worker=self.speaker_worker)
                            for intent in instance.intents_to_register:
                                self.action_map[intent] = instance.execute
                                logger.info(f"Registered plugin intent '{intent}'")
            except Exception as e:
                logger.error(f"Failed to load plugin '{file_path}': {e}", exc_info=True)

    def _speak(self, text: str) -> None:
        self.speaker_worker.speak(text)
    
    def set_last_received_file(self, file_path: Path) -> None:
        self.last_received_file = file_path

    def reload_maps(self) -> None:
        settings = self.settings_manager.settings
        self.site_map = {k.lower(): v for k, v in settings.sites.items()}
        self.macros = {k.lower(): [step.model_dump() for step in v] for k, v in settings.macros.items()}
        
        base_actions = {
            "[ANALYZE_SCREEN]": self._action_analyze_screen,
            "[GET_SYSTEM_STATS]": self._action_get_system_stats,
            "[NEXT_DESKTOP]": self._action_next_desktop,
            "[PREVIOUS_DESKTOP]": self._action_previous_desktop,
            "[SEND_WHATSAPP_MESSAGE]": self._action_send_whatsapp_message,
            "[SEARCH_WEB]": self._action_search_web,
            "[MEDIA_PLAY_PAUSE]": self._action_media_play_pause,
            "[NEXT_TRACK]": self._action_media_next,
            "[PREVIOUS_TRACK]": self._action_media_previous,
            "[MUTE_TOGGLE]": self._action_mute_toggle,
            "[VOLUME_UP]": self._action_volume_up,
            "[VOLUME_DOWN]": self._action_volume_down,
            "[OPEN_WEBSITE]": self._action_open_website,
            "[CONFIRM_ACTION]": self._action_confirm,
            "[SCROLL_UP]": self._action_scroll_up,
            "[SCROLL_DOWN]": self._action_scroll_down,
            "[CLOSE_TAB]": self._action_close_tab,
            "[CLOSE_WINDOW]": self._action_close_window,
            "[EXECUTE_DYNAMIC_TASK]": self._action_execute_dynamic_task,
            "[WRITE_CODE]": self._action_write_code,
            "[SHOW_PROJECT_STATUS]": self._action_show_project_status,
            "[OPEN_PROJECT_FOLDER]": self._action_open_project_folder,
            "[OPEN_LAST_RECEIVED_FILE]": self._action_open_last_received_file,
            "[MAXIMIZE_WINDOW]": self._action_maximize_window,
            "[MINIMIZE_WINDOW]": self._action_minimize_window,
            "[SNAP_WINDOW_LEFT]": self._action_snap_window_left,
            "[SNAP_WINDOW_RIGHT]": self._action_snap_window_right,
            "[BROWSER_HANDOFF]": self._execute_handoff_sequence,
            "[DOCUMENT_HANDOFF]": self._execute_handoff_sequence,
            "[SPOTIFY_HANDOFF]": self._execute_handoff_sequence,
            "[HEADSET_HANDOFF]": self._execute_handoff_sequence,
            "[QUERY_MEMORY]": self._action_query_memory,
            # --- ADD THESE THREE LINES ---
            "[FEEDBACK_POSITIVE]": self._action_feedback_positive,
            "[FEEDBACK_NEGATIVE_CONCISE]": self._action_feedback_concise,
            "[FEEDBACK_NEGATIVE_DETAILED]": self._action_feedback_detailed,
        }
        base_actions.update(self.action_map)
        self.action_map = base_actions
        logger.debug("Action maps reloaded.")

    def execute_action(self, intent: str, entities: Dict[str, Any] | None = None, emotion: str | None = None) -> None:
        self.current_emotion = emotion or "neu"
        logger.info(f"Attempting to execute action for intent: {intent}")

        clean_intent = intent.strip("[]").lower()
        if clean_intent in self.macros:
            logger.info(f"Executing macro '{clean_intent}'...")
            self._execute_macro(self.macros[clean_intent])
            return

        action_function = self.action_map.get(intent)
        if action_function:
            try:
                sig = inspect.signature(action_function)
                if action_function == self._execute_handoff_sequence:
                    threading.Thread(target=action_function, args=(intent,)).start()
                elif isinstance(getattr(action_function, '__self__', None), BasePlugin):
                    action_function(intent, entities)
                elif len(sig.parameters) > 0:
                    action_function(entities)
                else:
                    action_function()
            except Exception as e:
                logger.error(f"Error executing action {intent}: {e}", exc_info=True)
        else:
            logger.warning(f"No action or macro defined for intent {intent}")

    def _execute_macro(self, steps: List[Dict[str, str]]) -> None:
        for step in steps:
            if self.interrupt_event.is_set(): self._speak("Action cancelled."); return
            action, param = step.get("action"), step.get("param")
            try:
                if action == "OPEN_APP": self._atomic_open_app(param)
                elif action == "OPEN_URL": webbrowser.open(param)
                elif action == "PRESS_KEY": pyautogui.press(param.split(','))
                elif action == "TYPE_TEXT": pyautogui.write(param, interval=0.02)
                elif action == "WAIT": time.sleep(float(param))
            except Exception as e:
                logger.error(f"Error in macro step {action}: {e}")

    def _atomic_open_app(self, path: str) -> None:
        try:
            if sys.platform == "win32": os.startfile(path)
            else: subprocess.call(["open", path])
        except Exception as e:
            logger.error(f"Error opening app '{path}': {e}")
    
    def _execute_handoff_sequence(self, handoff_intent: str):
        try:
            if not hotspot_manager.is_hotspot_active():
                self._speak("To create a direct link, I need to activate the mobile hotspot on this PC. Opening settings now.")
                if not hotspot_manager.open_hotspot_settings():
                    self._speak("Sorry, I couldn't open the hotspot settings.")
                    return
                
                self._speak("Please enable the mobile hotspot. I will wait for it to become active.")
                if not hotspot_manager.wait_for_hotspot_activation(timeout_seconds=30):
                    self._speak("I didn't detect the hotspot being enabled. Please try the command again once it's on.")
                    return
                else:
                    self._speak("Great! Hotspot detected. Give your phone a moment to connect, then please repeat your command.")
                    return

            self._speak("Direct link is active. Performing handoff now.")
            time.sleep(1)

            window_title, process_name = self.context_manager.get_active_window_info()
            window_title = (window_title or "").lower()
            process_name = (process_name or "").lower()

            browser_processes = ["chrome.exe", "msedge.exe", "firefox.exe"]

            if window_title.endswith('.pdf'):
                logger.info("Window title ends with .pdf. Forcing a document handoff.")
                self._perform_document_handoff_action()
            elif process_name in browser_processes:
                logger.info("Context suggests a browser handoff.")
                self._perform_browser_handoff_action()
            else:
                logger.info("Context is not a browser. Defaulting to document handoff.")
                self._perform_document_handoff_action()

        except Exception as e:
            logger.error(f"An error occurred during the handoff sequence: {e}", exc_info=True)
            self._speak("An unexpected error occurred during the transfer.")

    def _get_page_number_from_screen(self) -> int:
        try:
            active_window = gw.getActiveWindow()
            if not active_window: return 1
            x, y, width, height = active_window.left, active_window.top, active_window.width, active_window.height
            region = (x + (width - 300) // 2, y + height - 80, 300, 80)
            screenshot = pyautogui.screenshot(region=region)
            text = pytesseract.image_to_string(screenshot)
            matches = re.findall(r'\b(\d+)\s*(?:/|\bof\b)\s*\d+', text)
            if matches: return int(matches[0])
            matches = re.findall(r'\b(\d+)\b', text)
            if matches: return int(matches[-1])
        except Exception as e:
            logger.error(f"Could not extract page number via OCR: {e}")
        return 1
    
    def _perform_browser_handoff_action(self):
        try:
            pyautogui.hotkey('alt', 'd'); time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'c'); time.sleep(0.1)
            url = pyperclip.paste()
            if url and url.startswith("http"):
                logger.info(f"Sending URL to mobile: {url}")
                if self.api_manager.loop:
                    asyncio.run_coroutine_threadsafe(self.api_manager.send_browser_handoff(url), self.api_manager.loop)
            else:
                self._speak("I couldn't get a valid URL from the browser.")
        except Exception as e:
            logger.error(f"Error during browser handoff action: {e}")
            self._speak("Sorry, an error occurred while getting the URL.")

    def _perform_document_handoff_action(self):
        self._speak("Please select the file and press Control-C. I will check the clipboard in 10 seconds.")
        time.sleep(10)
        try:
            if sys.platform != "win32":
                self._speak("File handoff from clipboard is only supported on Windows.")
                return

            win32clipboard.OpenClipboard()
            file_path = None
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_HDROP):
                data = win32clipboard.GetClipboardData(win32clipboard.CF_HDROP)
                if data:
                    file_path = data[0]
            win32clipboard.CloseClipboard()

            if not file_path:
                self._speak("I couldn't find a file on the clipboard. Please try the handoff command again.")
                return
            
            logger.info(f"Retrieved file path from clipboard: {file_path}")
            if not os.path.exists(file_path):
                self._speak("The file path I found doesn't seem to exist. Handoff cancelled.")
                return
            
            page_number = self._get_page_number_from_screen()
            transfer_thread = threading.Thread(target=self._stream_file, args=(file_path, page_number))
            transfer_thread.start()
        except Exception as e:
            logger.error(f"Error during document handoff from clipboard: {e}", exc_info=True)
            self._speak("I ran into an issue trying to access the clipboard. Handoff cancelled.")

    def _perform_spotify_handoff_action(self):
        playback_state = self.spotify_manager.get_playback_state()
        if playback_state:
            if self.api_manager.loop:
                asyncio.run_coroutine_threadsafe(self.api_manager.send_spotify_handoff(playback_state), self.api_manager.loop)
        else:
            self._speak("I couldn't find a song playing on Spotify.")
    
    def _perform_headset_handoff_action(self):
        headset_name = bluetooth_manager.get_active_audio_device_name()
        if not headset_name:
            self._speak("I couldn't figure out which headset you're using. Aborting handoff.")
            return
        self._speak(f"Switching {headset_name} to your phone.")
        if self.api_manager.loop:
            asyncio.run_coroutine_threadsafe(self.api_manager.send_headset_handoff(headset_name), self.api_manager.loop)

    def _stream_file(self, file_path: str, page_number: int = 1):
        if not (self.api_manager.loop and self.api_manager.loop.is_running()):
            logger.error("Cannot stream file, asyncio loop is not running.")
            return
        try:
            self._speak(f"Transferring {os.path.basename(file_path)}.")
            future = asyncio.run_coroutine_threadsafe(
                self.api_manager.send_file_start(file_path, page_number), self.api_manager.loop
            )
            future.result()
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk: break
                    future = asyncio.run_coroutine_threadsafe(
                        self.api_manager.send_file_chunk(chunk), self.api_manager.loop
                    )
                    future.result()
            future = asyncio.run_coroutine_threadsafe(
                self.api_manager.send_file_end(), self.api_manager.loop
            )
            future.result()
            self._speak("File transfer complete.")
        except Exception as e:
            logger.error(f"File streaming failed: {e}", exc_info=True)
            self._speak("Sorry, the file transfer failed.")

    def _action_execute_dynamic_task(self, entities: Dict[str, Any]) -> None:
        query = entities.get("query")
        if not self.llm_handler:
            self._speak("The dynamic task handler is not available.")
            return
        self._speak(f"Thinking about: {query}")
        plan, script = self.llm_handler.generate_script(query)
        if not script or "error" in script.lower():
            self._speak(f"I was unable to generate a valid plan. The model responded: {script}")
            return
        self._speak(f"My plan is to: {plan}")
        time.sleep(0.5)
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("Confirm Dynamic Action")
        msg_box.setText("Please review the code I've generated to accomplish this task.")
        msg_box.setInformativeText("Execute only if you understand and trust it.")
        msg_box.setDetailedText(script)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        reply = msg_box.exec()
        if reply == QMessageBox.StandardButton.Yes:
            self._speak("Executing.")
            try:
                safe_globals = {"__builtins__": safe_builtins, "_write_": full_write_guard, "primitives": primitives}
                byte_code = compile_restricted(script, filename='<llm_script>', mode='exec')
                exec(byte_code, safe_globals)
            except Exception as e:
                logger.error(f"Error executing sandboxed LLM script: {e}", exc_info=True)
                self._speak(f"An error occurred during execution: {e}")
        else:
            self._speak("Action cancelled.")

    def _action_query_memory(self, entities: Dict[str, Any]) -> None:
        """
        Handles the [QUERY_MEMORY] intent. Retrieves relevant documents from the
        vector database and uses the LLM to synthesize an answer.
        """
        query = entities.get("entity")
        if not query:
            self._speak("I'm sorry, I didn't catch what you wanted me to search for in my memory.")
            return
        
        if not self.memory_manager or not self.llm_handler:
            self._speak("My memory systems are not available at the moment.")
            return
        
        self._speak(f"Searching my memory for information about {query}...")
        
        try:
            # 1. RETRIEVE: Search the vector DB for the most relevant documents.
            results = self.memory_manager.query_memory(query_text=query, n_results=5)
            if not results:
                self._speak(f"I don't seem to have any memories related to {query}.")
                return
            
            # 2. AUGMENT: Prepare the retrieved documents as context for the LLM.
            context_documents = "\n".join([f"- {res['document']}" for res in results])
            personality_suffix = self.llm_handler._get_personality_prompt_suffix()  # <-- GET SUFFIX
            
            # 3. GENERATE: Ask the LLM to synthesize an answer based on the context.
            prompt = (
                f"You are KAIROS, an AI assistant. You have searched your personal memory database for information related to the user's query. "
                f"Based *only* on the following retrieved documents, provide a concise, natural language summary that directly answers the user's question.\n\n"
                f"User's Question: '{query}'\n\n"
                f"Retrieved Memories:\n{context_documents}\n\n"
                f"Your Synthesized Answer:"
                f"{personality_suffix}"  # <-- ADD SUFFIX TO PROMPT
            )
            
            # Use ollama to generate the response
            response = ollama.generate(model=self.llm_handler.model, prompt=prompt)
            answer = response['response']
            
            logger.info(f"LLM synthesized memory response: {answer}")
            self._speak(answer)
            
        except Exception as e:
            logger.error(f"Failed to query memory or synthesize answer: {e}", exc_info=True)
            self._speak("I found some relevant information, but I'm having trouble summarizing it right now.")

    # --- ADD THESE THREE NEW METHODS AT THE END OF THE CLASS ---
    def _action_feedback_positive(self) -> None:
        """Handles positive feedback to increase proactivity."""
        self.personality_manager.adjust_trait("proactivity", 0.05)
        self._speak("Thanks for the feedback. I'll keep that in mind.")

    def _action_feedback_concise(self) -> None:
        """Handles feedback to be less verbose."""
        self.personality_manager.adjust_trait("verbosity", -0.1)
        self._speak("Understood. I'll be more concise.")

    def _action_feedback_detailed(self) -> None:
        """Handles feedback to be more verbose."""
        self.personality_manager.adjust_trait("verbosity", 0.1)
        self._speak("Okay, I'll provide more detail in the future.")

    def _action_analyze_screen(self) -> None: self.ocr_requested.emit()
    def _get_target_window(self, entities: Dict[str, Any] | None = None) -> Any:
        if entities and "target_window" in entities: return entities["target_window"]
        try: return gw.getActiveWindow()
        except Exception: return None
    def _action_close_window(self, entities: Dict[str, Any] | None = None) -> None: pyautogui.hotkey('alt', 'f4')
    def _action_maximize_window(self, entities: Dict[str, Any] | None = None) -> None: pyautogui.hotkey('win', 'up')
    def _action_minimize_window(self, entities: Dict[str, Any] | None = None) -> None: pyautogui.hotkey('win', 'down')
    def _action_snap_window_left(self, entities: Dict[str, Any] | None = None) -> None: pyautogui.hotkey('win', 'left')
    def _action_snap_window_right(self, entities: Dict[str, Any] | None = None) -> None: pyautogui.hotkey('win', 'right')
    def _action_scroll_up(self) -> None: pyautogui.scroll(200)
    def _action_scroll_down(self) -> None: pyautogui.scroll(-200)
    def _action_media_next(self) -> None: pyautogui.press("nexttrack")
    def _action_media_previous(self) -> None: pyautogui.press("prevtrack")
    def _action_close_tab(self) -> None: pyautogui.hotkey('ctrl', 'w')
    def _action_show_project_status(self) -> None: self._speak("All systems are nominal.")
    def _action_open_project_folder(self) -> None: os.startfile(os.getcwd())
    def _action_next_desktop(self) -> None: pyautogui.hotkey('ctrl', 'win', 'right')
    def _action_previous_desktop(self) -> None: pyautogui.hotkey('ctrl', 'win', 'left')
    def _action_get_system_stats(self) -> None:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        self._speak(f"System status nominal. CPU at {cpu:.1f} percent, RAM at {ram:.1f} percent.")
    def _action_search_web(self, entities: Dict[str, Any]) -> None: webbrowser.open(f"https://www.google.com/search?q={entities.get('entity')}")
    def _action_open_website(self, entities: Dict[str, Any]) -> None:
        url = self.site_map.get(entities.get("entity").lower().strip())
        if url: webbrowser.open(url)
        else: self._action_search_web(entities)
    def _action_mute_toggle(self) -> None: pyautogui.press("volumemute")
    def _action_volume_up(self) -> None: pyautogui.press("volumeup")
    def _action_volume_down(self) -> None: pyautogui.press("volumedown")
    def _action_confirm(self) -> None: pyautogui.press("enter")
    def _action_media_play_pause(self) -> None: pyautogui.press("playpause")
    def _action_open_last_received_file(self) -> None:
        if self.last_received_file and self.last_received_file.exists():
            try:
                if sys.platform == "win32": os.startfile(self.last_received_file)
                else: subprocess.call(["open", self.last_received_file])
                self._speak(f"Opening {self.last_received_file.name}")
            except Exception as e:
                self._speak("Sorry, I was unable to open the last file.")
        else:
            self._speak("I don't have a record of any recently received files.")
    def _action_write_code(self, entities: Dict[str, Any]) -> None:
        query = entities.get("query")
        if not query or not self.llm_handler: return
        self._speak("Generating code. Place your cursor where you want it typed. I will begin in 3 seconds.")
        _, script = self.llm_handler.generate_script(query)
        if not script:
            self._speak("I was unable to generate any code for your request.")
            return
        time.sleep(3)
        pyautogui.write(script, interval=0.01)
        self._speak("The code has been written.")
    def _action_send_whatsapp_message(self, entities: Dict[str, Any]) -> None:
        recipient = entities.get("recipient")
        message = entities.get("message")
        if not recipient or not message:
            self._speak("Sorry, I didn't catch the recipient and the message.")
            return
        self._speak(f"Sending a WhatsApp message to {recipient}.")
        threading.Thread(target=send_whatsapp_message, args=(recipient, message), daemon=True).start()
    def _action_daily_briefing(self) -> None:
        now = datetime.now()
        current_time_str = now.strftime("%I:%M %p on %A")
        self._speak(f"Good morning. It is currently {current_time_str}.")