# src/action_manager.py

import webbrowser
import pyautogui
import string
import time
import os
import subprocess
import sys
import requests
import pygetwindow as gw
import psutil
from datetime import datetime
from PySide6.QtCore import QObject, Signal
from src.context_manager import ContextManager
from src.settings_manager import SettingsManager
from src.llm_handler import LlmHandler
from src.speaker_worker import SpeakerWorker
from PySide6.QtWidgets import QMessageBox
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import threading
import importlib.util
import inspect

from src.automations.whatsapp_automation import send_whatsapp_message
from RestrictedPython import compile_restricted
from RestrictedPython.Guards import safe_builtins
from src.plugin_interface import BasePlugin


logger = logging.getLogger(__name__)


class ActionManager(QObject):
    ocr_requested = Signal()

    def __init__(self, settings_manager: SettingsManager, interrupt_event: threading.Event, speaker_worker: SpeakerWorker) -> None:
        super().__init__()
        self.settings_manager: SettingsManager = settings_manager
        self.context_manager: ContextManager = ContextManager()
        self.llm_handler: LlmHandler | None = None
        self.speaker_worker = speaker_worker
        self.interrupt_event = interrupt_event
        self.last_received_file: Optional[Path] = None
        
        # <--- MODIFICATION START --->
        # Add a variable to store the emotion of the current command transaction
        self.current_emotion: str = "neu"  # Default to neutral
        # <--- MODIFICATION END --->

        try:
            self.llm_handler = LlmHandler()
        except Exception as e:
            logger.error(f"Failed to initialize a component: {e}", exc_info=True)

        self.uwp_apps: Dict[str, str] = {
            "spotify": "shell:appsfolder\\SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"
        }
        self.action_map = {}
        self.reload_maps()
        self._load_plugins()
        self.settings_manager.settings_updated.connect(self.reload_maps)

    def _load_plugins(self):
        """Discovers, imports, and registers all valid plugins."""
        plugins_dir = Path("plugins")
        if not plugins_dir.exists():
            logger.warning("Plugins directory not found. Skipping plugin loading.")
            return

        logger.info("Loading plugins...")
        for file_path in plugins_dir.glob("*.py"):
            if file_path.name.startswith("_"):
                continue

            try:
                spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
                if spec and spec.loader:
                    plugin_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(plugin_module)
                    for name, obj in inspect.getmembers(plugin_module, inspect.isclass):
                        if issubclass(obj, BasePlugin) and obj is not BasePlugin:
                            logger.info(f"  - Found valid plugin class: {name}")
                            plugin_instance = obj(speaker_worker=self.speaker_worker)
                            for intent in plugin_instance.intents_to_register:
                                if intent in self.action_map:
                                    logger.warning(f"Plugin intent '{intent}' from {name} conflicts with an existing action and will be ignored.")
                                else:
                                    self.action_map[intent] = plugin_instance.execute
                                    logger.info(f"    - Registered intent '{intent}' to plugin '{name}'")
            except Exception as e:
                logger.error(f"Failed to load plugin from '{file_path}': {e}", exc_info=True)

    # <--- MODIFICATION START --->
    # The _speak method is now emotion-aware.
    def _speak(self, text: str) -> None:
        """
        Speaks a given text with a tone appropriate to the user's last detected emotion.
        """
        # A simple map of emotion codes to conversational filler phrases.
        # 'ang' (angry) gets a short, direct prefix. 'neu' (neutral) gets none.
        emotion_map = {
            "hap": "Happy to! ",
            "ang": "Okay. ",
            "sad": "Of course. ",
            "neu": "",
        }
        # Get the prefix for the current emotion, defaulting to an empty string if unknown.
        prefix = emotion_map.get(self.current_emotion, "")
        
        # Combine the prefix and the base text for the full response.
        full_response = f"{prefix}{text}"
        self.speaker_worker.speak(full_response)
    # <--- MODIFICATION END --->
    
    def set_last_received_file(self, file_path: Path) -> None:
        self.last_received_file = file_path
        logger.info(f"Last received file path set to: {file_path}")

    def reload_maps(self) -> None:
        settings = self.settings_manager.settings
        self.site_map = {k: v for k, v in settings.sites.items()}
        self.macros = {k: [step.model_dump() for step in v] for k, v in settings.macros.items()}
        self.action_map = {
            "[ANALYZE_SCREEN]": self._action_analyze_screen,
            "[GET_SYSTEM_STATS]": self._action_get_system_stats,
            "[NEXT_DESKTOP]": self._action_next_desktop,
            "[PREVIOUS_DESKTOP]": self._action_previous_desktop,
            "[SEND_WHATSAPP_MESSAGE]": self._action_send_whatsapp_message,
            "[SEARCH_WEB]": self._action_search_web,
            "[PLAY_MUSIC]": self._action_media_play_pause,
            "[MEDIA_PLAY_PAUSE]": self._action_media_play_pause,
            "[NEXT_TRACK]": self._action_media_next,
            "[PREVIOUS_TRACK]": self._action_media_previous,
            "[OPEN_WEBSITE]": self._action_open_website,
            "[MUTE_TOGGLE]": self._action_mute_toggle,
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
        }
        logger.debug("Built-in action map reloaded.")

    # <--- MODIFICATION START --->
    # The method signature is changed to accept an optional 'emotion' string.
    def execute_action(self, intent: str, entities: Dict[str, Any] | None = None, emotion: str | None = None) -> None:
        # Store the emotion for this transaction, defaulting to neutral.
        self.current_emotion = emotion or "neu"
        logger.debug(f"Executing action with emotion context: '{self.current_emotion}'")
        # <--- MODIFICATION END --->

        clean_intent = intent.strip("[]")
        if clean_intent in self.macros:
            logger.info(f"Executing macro '{clean_intent}'...")
            self._execute_macro(self.macros[clean_intent])
            return

        action_function = self.action_map.get(intent)
        if action_function:
            try:
                sig = inspect.signature(action_function)
                if len(sig.parameters) >= 2: 
                    logger.info(f"Executing plugin action for intent {intent} with entities: {entities}")
                    action_function(intent, entities)
                else:
                    logger.info(f"Executing built-in action {intent} with entities: {entities}")
                    if entities:
                        action_function(entities)
                    else:
                        action_function()
            except Exception as e:
                logger.error(f"Error during execution of action {intent}: {e}", exc_info=True)
        else:
            logger.warning(f"No action, macro, or plugin defined for intent {intent}")

    def execute_app_sequence(self, apps: List[str]):
        """Executes a sequence of application launch actions."""
        logger.info(f"Executing learned workspace sequence: {apps}")
        self._speak(f"Deploying workspace.")
        for app_name in apps:
            if self.interrupt_event.is_set():
                logger.info("Interrupt signal received, stopping workspace deployment.")
                self.interrupt_event.clear()
                self._speak("Action cancelled.")
                return
            self._atomic_open_app(app_name)
            time.sleep(2)

    def _execute_macro(self, steps: List[Dict[str, str]]) -> None:
        for step in steps:
            if self.interrupt_event.is_set():
                logger.info("Interrupt signal received, stopping macro execution.")
                self.interrupt_event.clear()
                self._speak("Action cancelled.")
                return
            action, param = step.get("action"), step.get("param")
            logger.debug(f"  - Macro Step: {action}, Param: {param}")
            try:
                if action == "OPEN_APP": self._atomic_open_app(param)
                elif action == "OPEN_URL": webbrowser.open(param)
                elif action == "PRESS_KEY": pyautogui.press([k.strip() for k in param.split(",")])
                elif action == "TYPE_TEXT": pyautogui.write(param, interval=0.05)
                elif action == "WAIT": time.sleep(float(param))
            except Exception as e:
                logger.error(f"Error executing macro step {action}: {e}", exc_info=True)

    def _atomic_open_app(self, path: str) -> None:
        try:
            clean_path_str = path.lower().strip()
            if sys.platform == "win32" and clean_path_str in self.uwp_apps:
                os.system(f"explorer.exe {self.uwp_apps[clean_path_str]}")
                return
            app_path = Path(path)
            if sys.platform == "win32": os.startfile(app_path)
            elif sys.platform == "darwin": subprocess.call(["open", app_path])
            else: subprocess.call([str(app_path)], shell=False)
            logger.info(f"Opened app '{path}'")
        except Exception as e:
            logger.error(f"Error opening app '{path}': {e}", exc_info=True)
    
    def _action_analyze_screen(self) -> None:
        self._speak("Analyzing the screen.")
        self.ocr_requested.emit()
        
    def _get_target_window(self, entities: Dict[str, Any] | None = None) -> Any:
        if entities and "target_window" in entities:
            logger.info("Action received a specific window target.")
            return entities["target_window"]
        try:
            logger.info("No specific window target, getting active window.")
            return gw.getActiveWindow()
        except Exception:
            logger.warning("Could not get active window.")
            return None

    def _action_close_window(self, entities: Dict[str, Any] | None = None) -> None:
        window = self._get_target_window(entities)
        if window and window.exists:
            try:
                logger.info(f"Closing window: '{window.title}'")
                window.close()
            except Exception as e:
                logger.error(f"Failed to close window '{window.title}': {e}")
        elif entities and "target_window" in entities:
             logger.warning("Targeted window for close action no longer exists.")
        else: # Fallback to original behavior if no window is found
            try:
                if sys.platform == "darwin": pyautogui.hotkey('command', 'q')
                else: pyautogui.hotkey('alt', 'f4')
            except Exception as e:
                logger.error(f"Could not execute close window hotkey: {e}", exc_info=True)
            
    def _action_maximize_window(self, entities: Dict[str, Any] | None = None) -> None:
        window = self._get_target_window(entities)
        if window and window.exists and not window.isMaximized:
            logger.info(f"Maximizing window: '{window.title}'")
            window.maximize()

    def _action_minimize_window(self, entities: Dict[str, Any] | None = None) -> None:
        window = self._get_target_window(entities)
        if window and window.exists and not window.isMinimized:
            logger.info(f"Minimizing window: '{window.title}'")
            window.minimize()

    def _action_snap_window_left(self, entities: Dict[str, Any] | None = None) -> None:
        window = self._get_target_window(entities)
        if window:
            screen_width, screen_height = pyautogui.size()
            window.resizeTo(screen_width // 2, screen_height)
            window.moveTo(0, 0)
            logger.info(f"Snapped window '{window.title}' to the left.")

    def _action_snap_window_right(self, entities: Dict[str, Any] | None = None) -> None:
        window = self._get_target_window(entities)
        if window:
            screen_width, screen_height = pyautogui.size()
            window.resizeTo(screen_width // 2, screen_height)
            window.moveTo(screen_width // 2, 0)
            logger.info(f"Snapped window '{window.title}' to the right.")

    def _action_send_whatsapp_message(self, entities: Dict[str, Any]) -> None:
        recipient = entities.get("recipient")
        message = entities.get("message")
        if not recipient or not message:
            logger.warning("WhatsApp action called without recipient or message.")
            self._speak("Sorry, I didn't catch the recipient and the message.")
            return
        self._speak(f"Sending a WhatsApp message to {recipient}.")
        automation_thread = threading.Thread(target=send_whatsapp_message, args=(recipient, message), daemon=True)
        automation_thread.start()

    def _action_write_code(self, entities: Dict[str, Any]) -> None:
        query = entities.get("query")
        if not query or not self.llm_handler or not self.llm_handler.llm: return
        self._speak("Generating the code for you now. Please place your cursor where you want the code to be typed. I will begin in 3 seconds.")
        script = self.llm_handler.generate_script(query)
        if not script:
            self._speak("I was unable to generate any code for your request.")
            return
        time.sleep(3)
        try:
            pyautogui.write(script, interval=0.01)
            self._speak("The code has been written.")
        except Exception as e:
            logger.error(f"Error typing out LLM-generated script: {e}", exc_info=True)
            self._speak("I encountered an error while trying to type the code.")

    def _action_execute_dynamic_task(self, entities: Dict[str, Any]) -> None:
        query = entities.get("query")
        if not query or not self.llm_handler or not self.llm_handler.llm: return
        self._speak("One moment, I will generate a plan to accomplish that.")
        script = self.llm_handler.generate_script(query)
        if not script:
            self._speak("I was unable to generate a valid plan for your request.")
            return
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("Confirm Execution")
        msg_box.setText("I have generated the following script.")
        msg_box.setInformativeText("Please review this code. Execute only if you understand and trust it.")
        msg_box.setDetailedText(script)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        reply = msg_box.exec()
        if reply == QMessageBox.StandardButton.Yes:
            self._speak("Executing the plan in a secure sandbox.")
            try:
                byte_code = compile_restricted(script, filename='<llm_generated_script>', mode='exec')
                exec(byte_code, {"__builtins__": safe_builtins})
            except Exception as e:
                logger.error(f"Error executing sandboxed LLM script: {e}", exc_info=True)
                self._speak(f"An error occurred during the secure execution: The script was blocked or contained an error.")
        else:
            self._speak("Execution cancelled.")
    
    def _action_scroll_up(self, entities: Dict[str, Any] | None = None) -> None:
        amount = 200
        if entities and entities.get("entity"):
            entity = entities.get("entity")
            if "little" in entity or "bit" in entity: amount = 100
            elif "lot" in entity or "large" in entity: amount = 500
        try:
            pyautogui.scroll(amount)
            logger.info(f"Scrolled up by {amount} units.")
        except Exception as e:
            logger.error(f"Could not execute scroll up: {e}", exc_info=True)

    def _action_scroll_down(self, entities: Dict[str, Any] | None = None) -> None:
        amount = -200
        if entities and entities.get("entity"):
            entity = entities.get("entity")
            if "little" in entity or "bit" in entity: amount = -100
            elif "lot" in entity or "large" in entity: amount = -500
        try:
            pyautogui.scroll(amount)
            logger.info(f"Scrolled down by {abs(amount)} units.")
        except Exception as e:
            logger.error(f"Could not execute scroll down: {e}", exc_info=True)

    def _action_open_last_received_file(self) -> None:
        if self.last_received_file and self.last_received_file.exists():
            try:
                if sys.platform == "win32": os.startfile(self.last_received_file)
                elif sys.platform == "darwin": subprocess.call(["open", self.last_received_file])
                else: subprocess.call(["xdg-open", self.last_received_file])
                self._speak(f"Opening {self.last_received_file.name}")
            except Exception as e:
                logger.error(f"Could not open last received file: {e}", exc_info=True)
                self._speak("Sorry, I was unable to open the last file.")
        else:
            logger.warning("Action called but no received file found.")
            self._speak("I don't have a record of any recently received files.")
    
    def _action_media_next(self) -> None:
        try: pyautogui.press("nexttrack")
        except Exception as e: logger.error(f"Could not press 'next track' key: {e}", exc_info=True)
            
    def _action_media_previous(self) -> None:
        try: pyautogui.press("prevtrack")
        except Exception as e: logger.error(f"Could not press 'previous track' key: {e}", exc_info=True)
            
    def _action_close_tab(self) -> None:
        try:
            if sys.platform == "darwin": pyautogui.hotkey('command', 'w')
            else: pyautogui.hotkey('ctrl', 'w')
        except Exception as e:
            logger.error(f"Could not execute close tab hotkey: {e}", exc_info=True)
            
    def _action_show_project_status(self) -> None:
        self._speak("Showing project status. All systems are nominal.")
        
    def _action_open_project_folder(self) -> None:
        try:
            project_path = os.getcwd()
            if sys.platform == "win32": os.startfile(project_path)
            elif sys.platform == "darwin": subprocess.call(["open", project_path])
            else: subprocess.call(["xdg-open", project_path])
        except Exception as e:
            logger.error(f"Could not open project folder: {e}", exc_info=True)
            self._speak("Sorry, I was unable to open the project folder.")

    def _action_next_desktop(self) -> None:
        try:
            if sys.platform == "win32": pyautogui.hotkey('ctrl', 'win', 'right')
            elif sys.platform == "darwin": pyautogui.hotkey('ctrl', 'right')
            else: logger.warning("Virtual desktop control not implemented for this OS.")
        except Exception as e:
            logger.error(f"Failed to switch to next desktop: {e}", exc_info=True)

    def _action_previous_desktop(self) -> None:
        try:
            if sys.platform == "win32": pyautogui.hotkey('ctrl', 'win', 'left')
            elif sys.platform == "darwin": pyautogui.hotkey('ctrl', 'left')
            else: logger.warning("Virtual desktop control not implemented for this OS.")
        except Exception as e:
            logger.error(f"Failed to switch to previous desktop: {e}", exc_info=True)

    def _action_get_system_stats(self) -> None:
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            ram_usage = psutil.virtual_memory().percent
            response = f"System status nominal. Current CPU usage is at {cpu_usage:.1f} percent, and RAM usage is at {ram_usage:.1f} percent."
            self._speak(response)
        except Exception as e:
            logger.error(f"Failed to get system stats: {e}", exc_info=True)
            self._speak("I was unable to retrieve the system performance stats.")

    def _action_daily_briefing(self) -> None:
        lat, lon = 26.2183, 78.1828 # Gwalior coordinates
        location_name = "Gwalior"
        try:
            now = datetime.now()
            current_time_str = now.strftime("%I:%M %p on %A")
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            response = requests.get(weather_url)
            response.raise_for_status()
            data: Dict[str, Any] = response.json()
            temp = data["current_weather"]["temperature"]
            briefing = f"Good morning. It is {current_time_str} in {location_name}. The current temperature is approximately {temp} degrees Celsius."
            self._speak(briefing)
        except requests.RequestException as e:
            logger.error(f"Network error during daily briefing fetch: {e}", exc_info=True)
            self._speak("I was unable to fetch the weather for the daily briefing due to a network error.")
        except Exception as e:
            logger.error(f"An unexpected error occurred during daily briefing: {e}", exc_info=True)
            self._speak("I was unable to fetch the daily briefing.")

    def _action_search_web(self, entities: Dict[str, Any]) -> None:
        query = entities.get("entity")
        if not query: return
        try:
            webbrowser.open(f"https://www.google.com/search?q={query}")
        except Exception as e:
            logger.error(f"Could not open web browser for search: {e}", exc_info=True)
            
    def _action_open_website(self, entities: Dict[str, Any]) -> None:
        site_name = entities.get("entity")
        if not site_name: return
        try:
            clean_site_name = site_name.lower().strip(string.punctuation + string.whitespace)
            url = self.site_map.get(clean_site_name)
            if url:
                webbrowser.open(url)
            else:
                self._action_search_web({"entity": site_name})
        except Exception as e:
            logger.error(f"Could not open website '{site_name}': {e}", exc_info=True)
            
    def _action_mute_toggle(self) -> None:
        try:
            pyautogui.press("volumemute")
        except Exception as e:
            logger.error(f"Could not press 'volumemute' key: {e}", exc_info=True)
            
    def _action_confirm(self) -> None:
        try:
            pyautogui.press("enter")
        except Exception as e:
            logger.error(f"Could not press 'enter' key: {e}", exc_info=True)
            
    def _action_media_play_pause(self, entities: Dict[str, Any] | None = None) -> None:
        try:
            _title, process_name = self.context_manager.get_active_window_info()
            if process_name in ["spotify.exe", "youtubemusic.exe"]:
                pyautogui.press("playpause")
            elif process_name in ["chrome.exe", "msedge.exe", "firefox.exe"]:
                pyautogui.press("k")
            else:
                pyautogui.press("playpause")
        except Exception as e:
            logger.error(f"Could not execute media command: {e}", exc_info=True)