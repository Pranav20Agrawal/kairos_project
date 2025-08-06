# src/workers/update_checker_worker.py

import logging
import requests
import time
from PySide6.QtCore import QThread, Signal
from packaging.version import parse as parse_version

logger = logging.getLogger(__name__)

class UpdateCheckerWorker(QThread):
    """A worker that checks for a new application version from a remote URL."""
    update_available = Signal(str, str) # Emits new_version, url

    def __init__(self, current_version: str, update_url: str | None, parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self.update_url = update_url
        self.running = True

    def run(self):
        if not self.update_url or "YourUsername" in self.update_url:
            logger.info("Update checker URL is not configured. Skipping check.")
            return

        # Wait a few seconds after startup to not impact launch performance
        time.sleep(10)

        logger.info(f"Checking for updates from {self.update_url}...")
        try:
            response = requests.get(self.update_url, timeout=15)
            response.raise_for_status() # Raise an exception for bad status codes

            latest_version_str = response.text.strip()
            
            # Use the 'packaging' library to safely compare version numbers
            current_v = parse_version(self.current_version)
            latest_v = parse_version(latest_version_str)

            if latest_v > current_v:
                logger.info(f"New version available: {latest_v} (current: {current_v})")
                repo_url = self.update_url.split("/raw/")[0] # Best guess for repo URL
                self.update_available.emit(str(latest_v), repo_url)
            else:
                logger.info("K.A.I.R.O.S. is up to date.")

        except requests.RequestException as e:
            logger.warning(f"Could not check for updates due to a network error: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred in the update checker: {e}", exc_info=True)

    def stop(self):
        self.running = False