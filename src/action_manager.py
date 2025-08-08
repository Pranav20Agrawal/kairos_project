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
from RestrictedPython.Guards import safe_builtins, full_write_guard
from src.plugin_interface import BasePlugin
import src.primitives as primitives

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
        self.current_emotion: str = "neu"

        try:
            self.llm_handler = LlmHandler()
        except Exception as e:
            logger.error(f"Failed to initialize a component: {e}", exc_info=True)

        self.uwp_apps: Dict[str, str] = {
            "spotify": "shell:appsfolder\\SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"
        }
        self.action_map = {}
        self.macros = {}
        self.site_map = {}
        self._load_plugins()
        self.reload_maps() # Load built-in actions and settings-based ones
        self.settings_manager.settings_updated.connect(self.reload_maps)

    def _load_plugins(self):
        plugins_dir = Path("plugins")
        if not plugins_dir.exists(): return
        logger.info("Loading plugins...")
        for file_path in plugins_dir.glob("*.py"):
            if file_path.name.startswith("_"): continue
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
        
        # Start with a clean map to avoid duplicating on reload
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
        }
        # Preserve plugins by updating the base map with any loaded plugin actions
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
                # Correctly call plugins vs built-in functions
                if isinstance(getattr(action_function, '__self__', None), BasePlugin):
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
                safe_globals = {
                    "__builtins__": safe_builtins, "_write_": full_write_guard,
                    "primitives": primitives
                }
                byte_code = compile_restricted(script, filename='<llm_script>', mode='exec')
                exec(byte_code, safe_globals)
            except Exception as e:
                logger.error(f"Error executing sandboxed LLM script: {e}", exc_info=True)
                self._speak(f"An error occurred during execution: {e}")
        else:
            self._speak("Action cancelled.")

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