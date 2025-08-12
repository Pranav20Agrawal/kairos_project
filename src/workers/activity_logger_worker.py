# src/workers/activity_logger_worker.py

import logging
import csv
from pathlib import Path
from datetime import datetime
import time
from PySide6.QtCore import QThread, Signal
from src.context_manager import ContextManager
from src.pattern_analyzer import PatternAnalyzer
from typing import List, Optional

logger = logging.getLogger(__name__)

class ActivityLoggerWorker(QThread):
    suggestion_ready = Signal(str, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.context_manager = ContextManager()
        self.pattern_analyzer = PatternAnalyzer()
        self.log_path = Path("activity_log.csv")
        self.last_active_app: Optional[str] = None
        self.last_suggestion_time = 0
        self.SUGGESTION_COOLDOWN_S = 300
        
        # --- NEW: Variable to store the last relevant context ---
        self.last_app_context: Optional[str] = None

        self._ensure_log_file_exists()

    def _ensure_log_file_exists(self):
        if not self.log_path.exists():
            with open(self.log_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'process_name'])
                logger.info("Created activity_log.csv.")

    def run(self):
        logger.info("ActivityLoggerWorker started.")
        while self.running:
            title, process_name = self.context_manager.get_active_window_info()

            if process_name:
                # --- NEW: Logic to update the last context ---
                # We only update the context if the active window is NOT our own GUI.
                # 'python.exe' or 'pythonw.exe' is often the process for PySide apps.
                if "python" not in process_name and "kairos" not in title.lower():
                    self.last_app_context = process_name
                
                if process_name != self.last_active_app:
                    logger.info(f"New active app detected: {process_name}")
                    timestamp = datetime.now().isoformat()
                    with open(self.log_path, 'a', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow([timestamp, process_name])
                    
                    self.last_active_app = process_name
                    self.check_for_patterns(process_name)

            time.sleep(2) # Check every 2 seconds

    def check_for_patterns(self, current_app: str):
        if time.time() - self.last_suggestion_time < self.SUGGESTION_COOLDOWN_S:
            return

        frequent_patterns = self.pattern_analyzer.find_frequent_patterns()
        if not frequent_patterns:
            return
            
        for pattern, _count in frequent_patterns:
            if pattern and pattern[0] == current_app:
                apps_to_open = list(pattern[1:])
                if not apps_to_open: continue
                
                app_names = [name.replace('.exe', '').capitalize() for name in apps_to_open]
                suggestion_text = f"I notice you often open { ' and '.join(app_names) } after starting {current_app.replace('.exe','').capitalize()}. Shall I open them for you?"
                
                logger.info(f"Proactive suggestion triggered: {suggestion_text}")
                self.suggestion_ready.emit(suggestion_text, apps_to_open)
                self.last_suggestion_time = time.time()
                return

    def stop(self):
        self.running = False
        logger.info("ActivityLoggerWorker stop signal received.")