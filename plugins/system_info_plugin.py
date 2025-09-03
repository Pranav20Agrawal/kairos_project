# plugins/system_info_plugin.py

from src.plugin_interface import BasePlugin
from typing import Dict, Any, List
from datetime import datetime

class SystemInfoPlugin(BasePlugin):
    """A simple plugin to provide system information like the current date and time."""

    @property
    def intents_to_register(self) -> List[str]:
        """Register intents for this plugin."""
        # --- ADD THE NEW INTENT HERE ---
        return ["[GET_TODAYS_DATE]", "[GET_CURRENT_TIME]"]

    def execute(self, intent: str, entities: Dict[str, Any] | None) -> None:
        """Executes the action based on the triggered intent."""
        if intent == "[GET_TODAYS_DATE]":
            self.get_todays_date()
        # --- ADD THE NEW LOGIC HERE ---
        elif intent == "[GET_CURRENT_TIME]":
            self.get_current_time()

    def get_todays_date(self):
        """Speaks the current date in a friendly format."""
        now = datetime.now()
        # A small fix to correctly format the day (e.g., 1st, 2nd, 3rd, 4th)
        day = int(now.strftime("%d"))
        if 4 <= day <= 20 or 24 <= day <= 30:
            suffix = "th"
        else:
            suffix = ["st", "nd", "rd"][day % 10 - 1]
        date_str = now.strftime(f"%A, %B {day}{suffix}, %Y")
        self._speak(f"Today's date is {date_str}.")

    # --- ADD THIS ENTIRE NEW METHOD ---
    def get_current_time(self):
        """Speaks the current time in a friendly format."""
        now = datetime.now()
        time_str = now.strftime("%I:%M %p") # e.g., "11:59 PM"
        self._speak(f"The current time is {time_str}.")