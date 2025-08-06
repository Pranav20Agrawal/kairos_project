# src/workers/activity_logger_worker.py

import logging
import csv
from pathlib import Path
from datetime import datetime
import time
from PySide6.QtCore import QThread, Signal
from src.context_manager import ContextManager
from src.pattern_analyzer import PatternAnalyzer
from typing import List

logger = logging.getLogger(__name__)

class ActivityLoggerWorker(QThread):
    """
    A worker that periodically logs the active application and checks for
    patterns to suggest proactive actions.
    """
    suggestion_ready = Signal(str, list) # Emits suggestion text and the app list

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.context_manager = ContextManager()
        self.pattern_analyzer = PatternAnalyzer()
        self.log_path = Path("activity_log.csv")
        self.last_active_app = None
        self.last_suggestion_time = 0
        self.SUGGESTION_COOLDOWN_S = 300 # 5 minutes

        self._ensure_log_file_exists()

    def _ensure_log_file_exists(self):
        """Creates the CSV log file with a header if it doesn't exist."""
        if not self.log_path.exists():
            with open(self.log_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'process_name'])
                logger.info("Created activity_log.csv.")

    def run(self):
        logger.info("ActivityLoggerWorker started.")
        while self.running:
            _title, process_name = self.context_manager.get_active_window_info()

            if process_name and process_name != self.last_active_app:
                logger.info(f"New active app detected: {process_name}")
                # Log the new activity
                timestamp = datetime.now().isoformat()
                with open(self.log_path, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([timestamp, process_name])
                
                self.last_active_app = process_name
                
                # Check for patterns after a change
                self.check_for_patterns(process_name)

            # Wait for a few seconds before checking again to keep CPU usage low
            time.sleep(3)

    def check_for_patterns(self, current_app: str):
        """Analyzes patterns and emits a suggestion if a trigger is met."""
        # Check if we are in a cooldown period
        if time.time() - self.last_suggestion_time < self.SUGGESTION_COOLDOWN_S:
            return

        frequent_patterns = self.pattern_analyzer.find_frequent_patterns()
        if not frequent_patterns:
            return
            
        # Check if the current app is the start of any frequent pattern
        for pattern, _count in frequent_patterns:
            if pattern[0] == current_app:
                apps_to_open = list(pattern[1:]) # The rest of the apps in the pattern
                
                # Formulate the suggestion text
                app_names = [name.replace('.exe', '').capitalize() for name in apps_to_open]
                suggestion_text = f"I notice you often open { ' and '.join(app_names) } after starting {current_app.replace('.exe','').capitalize()}. Shall I open them for you?"
                
                logger.info(f"Proactive suggestion triggered: {suggestion_text}")
                self.suggestion_ready.emit(suggestion_text, apps_to_open)
                self.last_suggestion_time = time.time() # Start cooldown
                return # Only make one suggestion at a time

    def stop(self):
        self.running = False
        logger.info("ActivityLoggerWorker stop signal received.")