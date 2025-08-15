# src/workers/activity_logger_worker.py

import logging
import csv
from pathlib import Path
from datetime import datetime
import time
from PySide6.QtCore import QThread, Signal
from src.context_manager import ContextManager
# We are simplifying this worker for now. The PatternAnalyzer will be upgraded later.
# from src.pattern_analyzer import PatternAnalyzer 
from typing import List, Optional

logger = logging.getLogger(__name__)

class ActivityLoggerWorker(QThread):
    activity_stats_updated = Signal(dict)  # For flow state monitoring
    # This signal will eventually be used by the SessionAnalyzer
    activity_logged = Signal(dict) 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.context_manager = ContextManager()
        self.log_path = Path("activity_log.csv")
        self.last_active_window_title: Optional[str] = None
        self.last_app_context: Optional[str] = None
        self._ensure_log_file_exists()

    def _ensure_log_file_exists(self):
        """Creates the CSV log file with the new, richer header if it doesn't exist."""
        if not self.log_path.exists():
            with open(self.log_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # The new header with window_title
                writer.writerow(['timestamp', 'process_name', 'window_title']) 
                logger.info("Created activity_log.csv with new header.")

    def run(self):
        """
        Monitors the active window and logs changes to a CSV file.
        This version logs the process name AND the window title for richer context.
        """
        logger.info("ActivityLoggerWorker started with enhanced context logging.")
        while self.running:
            title, process_name = self.context_manager.get_active_window_info()

            # We only log if there is a valid window and it has changed
            if process_name and title and title != self.last_active_window_title:
                logger.info(f"New context: App='{process_name}', Title='{title}'")
                self.last_active_window_title = title
                
                # Update our general app context (used for NLU)
                # We filter out our own application to avoid logging KAIROS itself
                if "python" not in process_name and "kairos" not in title.lower():
                    self.last_app_context = process_name

                # --- EMIT ACTIVITY STATS FOR FLOW STATE MONITORING ---
                # Emit a signal every time the app changes for flow state tracking
                stats = {"timestamp": time.time(), "app_switches": 1}
                self.activity_stats_updated.emit(stats)
                # --- END OF FLOW STATE STATS ---

                # Log the new, detailed context to our CSV file
                timestamp = datetime.now().isoformat()
                try:
                    with open(self.log_path, 'a', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow([timestamp, process_name, title])
                    
                    # Emit a signal that a new activity has been logged
                    self.activity_logged.emit({
                        "timestamp": timestamp,
                        "process_name": process_name,
                        "window_title": title
                    })
                except (IOError, PermissionError) as e:
                    logger.error(f"Could not write to activity_log.csv: {e}")

                # Note: The old pattern suggestion logic is removed from here.
                # A new, more intelligent Session Analyzer will handle that role.

            time.sleep(2)  # Check for changes every 2 seconds

    def stop(self):
        self.running = False
        logger.info("ActivityLoggerWorker stop signal received.")