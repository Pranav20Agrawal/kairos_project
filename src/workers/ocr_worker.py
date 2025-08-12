# src/workers/ocr_worker.py

import logging
import pyautogui
import pygetwindow as gw
import pytesseract
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

class OcrWorker(QThread):
    """A worker thread to perform OCR on the active window without freezing the UI."""
    
    ocr_complete = Signal   (str)  # Emits the extracted text
    error_occurred = Signal(str, str) # Emits message and level

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True

    def run(self):
        """
        The main logic for the worker thread. This is executed when .start() is called.
        """
        logger.info("OCR Worker started. Analyzing active window...")
        try:
            # 1. Get the active window
            active_window = gw.getActiveWindow()
            if not active_window:
                logger.warning("No active window found for OCR.")
                self.error_occurred.emit("No active window found to analyze.", "WARNING")
                return

            # 2. Get window geometry for a targeted screenshot (Optimization)
            # We add a small buffer just in case the window border is not included
            x, y, width, height = (
                active_window.left,
                active_window.top,
                active_window.width,
                active_window.height,
            )
            
            # Check for invalid window dimensions
            if width <= 0 or height <= 0:
                logger.warning(f"Invalid window dimensions for OCR: {width}x{height}")
                self.error_occurred.emit("Cannot analyze a minimized or invalid window.", "WARNING")
                return
            
            logger.debug(f"Capturing screen region: x={x}, y={y}, w={width}, h={height}")

            # 3. Take the screenshot of the specific region
            screenshot = pyautogui.screenshot(region=(x, y, width, height))

            # 4. Perform OCR using pytesseract
            logger.info("Performing OCR on captured image...")
            # We set a timeout to prevent tesseract from hanging indefinitely
            text = pytesseract.image_to_string(screenshot, timeout=10)
            
            if not text.strip():
                logger.info("OCR completed, but no text was found on the screen.")
                self.ocr_complete.emit("") # Emit empty string if no text
            else:
                logger.info("OCR completed successfully.")
                logger.debug(f"Extracted Text Snippet: {text.strip()[:100]}...")
                self.ocr_complete.emit(text)

        except pytesseract.TesseractNotFoundError:
            msg = "Tesseract OCR engine not found. Please install it and ensure 'tesseract' is in your system's PATH."
            logger.critical(msg)
            self.error_occurred.emit(msg, "CRITICAL")
        except Exception as e:
            msg = f"An unexpected error occurred during screen analysis."
            logger.error(f"{msg}: {e}", exc_info=True)
            self.error_occurred.emit(msg, "ERROR")

    def stop(self):
        """Stops the worker thread."""
        self.running = False
        logger.info("OCR Worker stop signal received.")