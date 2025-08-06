# src/workers/system_stats_worker.py

import logging
import psutil
import time
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

class SystemStatsWorker(QThread):
    """A worker thread that polls for system stats (CPU, RAM) periodically."""
    new_stats = Signal(float, float)  # Signal to emit CPU % and RAM %
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.poll_interval = 1.0  # seconds

    def run(self):
        """The main loop for the worker thread."""
        logger.info("SystemStatsWorker started.")
        while self.running:
            try:
                # Get CPU usage. interval > 0 is required for a non-blocking, comparable reading.
                cpu_percent = psutil.cpu_percent(interval=self.poll_interval)
                
                # Get memory usage
                ram_percent = psutil.virtual_memory().percent
                
                # Emit the stats for the UI to update
                self.new_stats.emit(cpu_percent, ram_percent)
                
            except psutil.NoSuchProcess:
                logger.warning("A process was terminated during stat collection.")
                time.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in SystemStatsWorker: {e}", exc_info=True)
                time.sleep(self.poll_interval * 2) # Wait a bit longer on error
    
    def stop(self):
        """Stops the worker thread gracefully."""
        self.running = False
        logger.info("SystemStatsWorker stop signal received.")