# src/settings_manager.py

import json
import os
import re  # <-- ADDED THIS IMPORT
from PySide6.QtCore import QObject, Signal
import logging
from typing import Any, List, Dict  # <-- ADDED LIST AND DICT
from pydantic import ValidationError

from src.models import SettingsModel, MacroStep, Intent  # <-- ADDED MacroStep AND Intent

logger = logging.getLogger(__name__)

# A simple regex to find URLs in window titles
URL_REGEX = re.compile(r'https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)')

class SettingsManager(QObject):
    settings_updated = Signal()

    def __init__(self, config_file: str = "config.json") -> None:
        super().__init__()
        self.config_file: str = config_file
        # The settings attribute will now be a Pydantic model instance
        self.settings: SettingsModel = SettingsModel()
        logger.info(f"SettingsManager initialized for '{config_file}'.")
        self.load_settings()

    def load_settings(self) -> None:
        """Loads settings from the config file and validates them using Pydantic."""
        logger.info(f"Loading settings from '{self.config_file}'...")
        if os.path.exists(self.config_file):
            with open(self.config_file, "r") as f:
                try:
                    loaded_data = json.load(f)
                    # This is the validation step!
                    self.settings = SettingsModel(**loaded_data)
                    logger.info("Settings loaded and validated successfully.")
                except json.JSONDecodeError:
                    logger.warning(
                        f"Could not decode JSON from {self.config_file}. The file might be corrupted. Loading default settings.",
                        exc_info=True,
                    )
                    self.settings = SettingsModel()  # Load defaults on error
                except ValidationError as e:
                    logger.warning(
                        f"Configuration validation failed for '{self.config_file}'. Please check the format.\n{e}\nLoading default settings."
                    )
                    self.settings = SettingsModel()  # Load defaults on error
        else:
            logger.warning(
                f"Config file '{self.config_file}' not found. A new one will be created with default settings."
            )
            self.settings = SettingsModel()
        
        # Save to ensure the file on disk is always valid and has all fields
        self.save_settings()

    def save_settings(self) -> None:
        """Saves the current settings model to the config file."""
        logger.info(f"Saving settings to '{self.config_file}'...")
        try:
            with open(self.config_file, "w") as f:
                # Use Pydantic's model_dump to get a dictionary for JSON
                json.dump(self.settings.model_dump(), f, indent=4)
            self.settings_updated.emit()
            logger.info("Settings saved successfully.")
        except Exception as e:
            logger.error(
                f"Failed to save settings to '{self.config_file}': {e}", exc_info=True
            )

    def create_macro_from_suggestion(self, macro_name: str, actions: List[Dict]) -> bool:
        """
        Takes a macro name and a list of logged actions, converts them into a
        Macro and a corresponding Intent, and saves them to the settings.
        """
        logger.info(f"Attempting to create and save new macro: '{macro_name}'")
        if macro_name in self.settings.macros:
            logger.warning(f"Macro '{macro_name}' already exists. Aborting creation.")
            return False
        
        macro_steps: List[MacroStep] = []
        
        # --- Intelligent Action Conversion ---
        # This loop converts the raw log into executable macro steps.
        for action in actions:
            process = action.get("process_name", "").lower()
            title = action.get("window_title", "")
            
            # Check if the title contains a URL for browser processes
            if process in ["chrome.exe", "msedge.exe", "firefox.exe"]:
                match = URL_REGEX.search(title)
                if match:
                    # If we find a URL, the action is to open that URL
                    macro_steps.append(MacroStep(action="OPEN_URL", param=match.group(0)))
                    continue
            
            # Default action is to open the application executable
            # We can make this smarter later to find the full app path
            macro_steps.append(MacroStep(action="OPEN_APP", param=process))
        
        if not macro_steps:
            logger.error("Could not convert logged actions into any valid macro steps.")
            return False
        
        # Add the new macro to settings
        self.settings.macros[macro_name] = macro_steps
        
        # --- Create a corresponding Intent to make the macro voice-callable ---
        intent_name = macro_name.upper().replace(" ", "_")
        # Create a user-friendly keyword from the macro name
        keyword = macro_name.lower()
        
        new_intent = Intent(
            keywords=[keyword],
            canonical=f"execute the '{macro_name}' workflow",
            is_high_risk=True  # Automations are considered high-risk
        )
        self.settings.intents[intent_name] = new_intent
        
        # Save all changes to config.json
        self.save_settings()
        logger.info(f"Successfully created macro '{macro_name}' with {len(macro_steps)} steps and corresponding intent '{intent_name}'")
        return True