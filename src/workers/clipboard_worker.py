# src/workers/clipboard_worker.py
import clipboard
import time
import logging
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

class ClipboardWorker(QThread):
    """A worker that monitors the system clipboard for changes."""
    clipboard_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self._cached_clipboard = ""
        try:
            # Initialize the cache with the current clipboard content
            self._cached_clipboard = clipboard.paste()
        except clipboard.ClipboardException:
            logger.warning("Could not read initial clipboard content.")
            self._cached_clipboard = ""


    def run(self):
        logger.info("Clipboard worker started.")
        while self.running:
            try:
                current_clipboard = clipboard.paste()
                if current_clipboard != self._cached_clipboard:
                    self._cached_clipboard = current_clipboard
                    logger.info("Clipboard changed. Emitting signal.")
                    if current_clipboard: # Only emit if there's content
                        self.clipboard_changed.emit(current_clipboard)
            except clipboard.ClipboardException:
                # This can happen if the clipboard is in use or contains non-text data
                time.sleep(1.5) # Wait a bit longer on error
                continue
            
            time.sleep(0.5) # Poll every half a second

    def stop(self):
        self.running = False
        logger.info("Clipboard worker stopped.")

    def update_clipboard_cache(self, text: str):
        """Updates the internal cache to prevent echo."""
        self._cached_clipboard = text