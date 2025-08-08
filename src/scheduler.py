# src/scheduler.py

import atexit
from apscheduler.schedulers.background import BackgroundScheduler
import logging
from typing import Callable

logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self) -> None:
        self.scheduler = BackgroundScheduler(daemon=True)
        logger.info("BackgroundScheduler initialized.")
        # This line was removed in some versions, it's good practice to have it
        atexit.register(self.shutdown)

    def schedule_daily_job(self, hour: int, minute: int, callback: Callable) -> None:
        self.scheduler.add_job(callback, 'cron', hour=hour, minute=minute)
        logger.info(f"Job '{callback.__name__}' scheduled for {hour:02d}:{minute:02d} daily.")

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started.")

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler shut down.")