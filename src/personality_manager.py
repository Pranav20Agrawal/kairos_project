# src/personality_manager.py

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.settings_manager import SettingsManager

logger = logging.getLogger(__name__)

class PersonalityManager:
    """Handles the logic for reading and adapting the AI's personality traits."""
    
    def __init__(self, settings_manager: "SettingsManager"):
        self.settings_manager = settings_manager

    def adjust_trait(self, trait: str, amount: float):
        """
        Adjusts a personality trait by a given amount and saves the new settings.
        Ensures the value stays between 0.0 and 1.0.
        """
        if not hasattr(self.settings_manager.settings.personality, trait):
            logger.warning(f"Attempted to adjust non-existent personality trait: {trait}")
            return

        current_value = getattr(self.settings_manager.settings.personality, trait)
        new_value = current_value + amount
        
        # Clamp the value between 0.0 and 1.0
        clamped_value = max(0.0, min(1.0, new_value))

        setattr(self.settings_manager.settings.personality, trait, clamped_value)
        self.settings_manager.save_settings()
        logger.info(f"Adjusted personality trait '{trait}' to {clamped_value:.2f}")