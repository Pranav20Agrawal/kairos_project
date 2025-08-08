# src/primitives.py

import pyautogui
import pyperclip
import pygetwindow as gw
import logging
from typing import List

"""
This file contains the foundational, 'hardcoded' primitives for K.A.I.R.O.S.
These are the most basic, atomic actions the AI can take to interact with the OS.
The LLM will use these building blocks to construct more complex tools and solutions.
"""

logger = logging.getLogger(__name__)

def get_active_window_title() -> str:
    """Returns the title of the currently active window on the screen."""
    try:
        active_window = gw.getActiveWindow()
        if active_window:
            return active_window.title
        return "No active window found."
    except Exception as e:
        logger.error(f"Error getting active window title: {e}")
        return f"Error: {e}"

def get_clipboard_text() -> str:
    """Returns the current text content from the system clipboard."""
    try:
        return pyperclip.paste()
    except pyperclip.PyperclipException as e:
        logger.error(f"Error reading from clipboard: {e}")
        return f"Error: {e}"

def type_text(text_to_type: str) -> str:
    """Types the given text at the current cursor location."""
    try:
        pyautogui.write(text_to_type, interval=0.02)
        return f"Successfully typed the text."
    except Exception as e:
        logger.error(f"Error typing text: {e}")
        return f"Error: {e}"

def press_hotkey(keys: List[str]) -> str:
    """
    Presses a combination of keys simultaneously.
    For example, to press Ctrl+C, the input should be ['ctrl', 'c'].
    """
    try:
        pyautogui.hotkey(*keys)
        return f"Successfully pressed the hotkey: {'+'.join(keys)}"
    except Exception as e:
        logger.error(f"Error pressing hotkey: {e}")
        return f"Error: {e}"