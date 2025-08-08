# src/kairos_tools.py

import datetime
import os
import pyperclip
import logging
from typing import List

logger = logging.getLogger(__name__)

"""
This file contains the 'hardcoded' toolbox for K.A.I.R.O.S.
Each function is a simple, safe, and reliable tool that the LLM can use to interact with the system.
The LLM's intelligence comes from its ability to combine these simple tools to solve complex tasks.
"""

def get_current_date_and_time() -> str:
    """
    Returns the current date and time as a formatted string.
    Example: "The current date and time is: 2025-08-07 10:30:00"
    """
    now = datetime.datetime.now()
    return f"The current date and time is: {now.strftime('%Y-%m-%d %H:%M:%S')}"

def get_clipboard_text() -> str:
    """
    Returns the current text content from the system clipboard.
    Returns an empty string if the clipboard is empty or contains non-text data.
    """
    try:
        return pyperclip.paste()
    except pyperclip.PyperclipException:
        logger.warning("Could not get clipboard text. Pyperclip may not be configured for your system.")
        return "Error: Could not access clipboard."

def list_files_on_desktop() -> List[str]:
    """
    Returns a list of filenames of items on the user's desktop.
    """
    desktop_path = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
    try:
        return [f for f in os.listdir(desktop_path) if os.path.isfile(os.path.join(desktop_path, f))]
    except FileNotFoundError:
        logger.error(f"Desktop path not found at: {desktop_path}")
        return ["Error: Desktop path not found."]

# We can add many more tools here in the future, like:
# - set_clipboard_text(text: str)
# - get_active_window_title() -> str
# - switch_to_window(window_title: str)
# - summarize_text(text: str) -> str