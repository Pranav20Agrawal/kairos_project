# src/workers/task_context_worker.py

import logging
import time
from PySide6.QtCore import QObject, QThread, Signal, Slot, QTimer
from collections import deque

logger = logging.getLogger(__name__)

class TaskContextWorker(QThread):
    """
    Analyzes real-time user activity to determine the user's current
    high-level task or context (e.g., coding, browsing, designing).
    """
    task_context_changed = Signal(str)  # Emits the new context name

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.running = True
        self.current_context = "TASK_IDLE"
        self.activity_buffer = deque(maxlen=10) # Store the last 10 activities

        # --- Rule-Based Context Definitions ---
        # We map process names to keywords found in window titles.
        # This is a simple but powerful way to determine context.
        self.context_rules = {
            "TASK_DEV_KAIROS": {
                "Code.exe": ["kairos_project"],
                "chrome.exe": ["github", "stack overflow", "pyside6", "flutter"]
            },
            "TASK_DESIGN": {
                "photoshop.exe": [""], # Any photoshop window
                "figma.exe": [""]
            },
            "TASK_BROWSING": {
                "chrome.exe": ["youtube", "reddit", "news"],
            }
            # We can add many more contexts here
        }

    def run(self) -> None:
        """The main loop for the worker thread, driven by a timer."""
        logger.info("TaskContextWorker started.")
        self.timer = QTimer()
        self.timer.timeout.connect(self._determine_context)
        self.timer.start(5000) # Analyze context every 5 seconds
        self.exec()
        logger.info("TaskContextWorker stopped.")

    @Slot(dict)
    def on_activity_logged(self, activity: dict) -> None:
        """Receives a new activity and adds it to our buffer."""
        self.activity_buffer.append(activity)

    def _determine_context(self) -> None:
        """
        Analyzes the recent activity buffer to find the most likely current task.
        """
        if not self.activity_buffer:
            return

        scores = {context: 0 for context in self.context_rules}
        
        # Check our recent activities against the rules
        for activity in self.activity_buffer:
            process = activity.get("process_name", "").lower()
            title = activity.get("window_title", "").lower()

            for context, rules in self.context_rules.items():
                if process in rules:
                    for keyword in rules[process]:
                        if keyword in title:
                            scores[context] += 1
                            break # Move to the next activity

        # Find the context with the highest score
        if any(s > 0 for s in scores.values()):
            best_context = max(scores, key=scores.get)
            
            # If the best context has a meaningful score and is different from the current one
            if scores[best_context] > 0 and best_context != self.current_context:
                self.current_context = best_context
                logger.info(f"Task context changed to: {self.current_context}")
                self.task_context_changed.emit(self.current_context)
    
    def stop(self) -> None:
        self.running = False
        if hasattr(self, 'timer'):
            self.timer.stop()
        self.quit()