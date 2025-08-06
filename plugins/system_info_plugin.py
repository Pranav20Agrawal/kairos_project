# plugins/system_info_plugin.py

from src.plugin_interface import BasePlugin
from typing import Dict, Any, List
from datetime import datetime

class SystemInfoPlugin(BasePlugin):
    """A simple plugin to provide system information like the current date."""

    @property
    def intents_to_register(self) -> List[str]:
        """Register the '[GET_TODAYS_DATE]' intent for this plugin."""
        return ["[GET_TODAYS_DATE]"]

    def execute(self, intent: str, entities: Dict[str, Any] | None) -> None:
        """Executes the action based on the triggered intent."""
        if intent == "[GET_TODAYS_DATE]":
            self.get_todays_date()

    def get_todays_date(self):
        """Speaks the current date in a friendly format."""
        # Use datetime.now() to get current date and time
        now = datetime.now()
        # Format the date into a readable string, e.g., "Monday, August 4th, 2025"
        date_str = now.strftime("%A, %B %dth, %Y").replace(" 0", " ")
        self._speak(f"Today's date is {date_str}.")