# src/settings_manager.py

import json
import os
from PySide6.QtCore import QObject, Signal
import logging
from typing import Any
from pydantic import ValidationError

from src.models import SettingsModel # <--- IMPORT OUR NEW MODEL

logger = logging.getLogger(__name__)

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
                    self.settings = SettingsModel() # Load defaults on error
                except ValidationError as e:
                    logger.warning(
                        f"Configuration validation failed for '{self.config_file}'. Please check the format.\n{e}\nLoading default settings."
                    )
                    self.settings = SettingsModel() # Load defaults on error
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