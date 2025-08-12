# src/file_handler.py
import logging
import win32gui
import win32process
import psutil
from typing import Optional

logger = logging.getLogger(__name__)

def get_active_file_path() -> Optional[str]:
    """
    Attempts to get the file path from the active window.
    This is a complex task and currently works best for apps like Adobe Acrobat.
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process = psutil.Process(pid)
        
        # This is a common way processes list their open files.
        # It may not work for all applications (e.g., browsers).
        open_files = process.open_files()
        if open_files:
            # We assume the first file is the primary one.
            # We can add more sophisticated logic later to filter for PDFs, DOCX, etc.
            file_path = open_files[0].path
            logger.info(f"Found active file path: {file_path}")
            return file_path
            
    except Exception as e:
        logger.error(f"Could not determine active file path: {e}")
        return None
    
    return None