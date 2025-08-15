# src/workers/heuristics_tuner.py

import logging
import time
from PySide6.QtCore import QThread, Signal

# Forward declarations for type hinting
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.settings_manager import SettingsManager
    from src.database_manager import DatabaseManager

logger = logging.getLogger(__name__)

class HeuristicsTuner(QThread):
    """
    A worker that periodically analyzes system performance to suggest
    self-tuning actions, such as recommending NLU model retraining.
    """
    tuning_suggestion_ready = Signal(str, str) # title, message

    def __init__(self, settings_manager: "SettingsManager", db_manager: "DatabaseManager", parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.db_manager = db_manager
        self.running = True
        
        # --- Heuristic Thresholds ---
        self.ACCURACY_THRESHOLD = 85.0 # If accuracy drops below this %, suggest training.
        self.MIN_CORRECTIONS_FOR_TRAINING = 5 # Minimum new corrections needed to justify training.
        
        self.last_total_commands = 0 # To track how many new commands have been logged.

    def run(self):
        logger.info("HeuristicsTuner worker started. Will check performance periodically.")
        
        # Wait a few minutes on startup before the first check
        self.sleep(120)

        while self.running:
            try:
                logger.info("HeuristicsTuner: Performing periodic performance analysis...")
                
                stats = self.db_manager.get_command_stats()
                total_commands = stats.get("total", 0)
                
                # Check if there's enough new data to warrant an analysis
                if total_commands > self.last_total_commands + self.MIN_CORRECTIONS_FOR_TRAINING:
                    
                    # Extract the accuracy number, removing the '%' sign
                    accuracy_str = stats.get("accuracy", "100.0%").replace('%', '')
                    accuracy = float(accuracy_str)

                    if accuracy < self.ACCURACY_THRESHOLD:
                        title = "Performance Suggestion"
                        message = (
                            f"My command accuracy has dropped to {accuracy:.1f}%. "
                            "I've logged several new corrections since my last update.\n\n"
                            "I recommend running the NLU training script to improve my performance."
                        )
                        self.tuning_suggestion_ready.emit(title, message)
                        
                        # Update the count to prevent spamming the user with suggestions
                        self.last_total_commands = total_commands

            except Exception as e:
                logger.error(f"Error during heuristic analysis: {e}", exc_info=True)

            # This is a long-running background task, check every hour.
            self.sleep(3600)

    def stop(self):
        self.running = False
        logger.info("HeuristicsTuner stop signal received.")