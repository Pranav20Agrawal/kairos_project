# src/scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler
import logging
from typing import Callable

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self) -> None:
        self.scheduler = BackgroundScheduler(daemon=True)
        logger.info("BackgroundScheduler initialized.")

    def schedule_daily_job(self, hour: int, minute: int, callback: Callable[[], None]) -> None:
        """Schedules a function to run every day at a specific time."""
        self.scheduler.add_job(callback, "cron", hour=hour, minute=minute)
        logger.info(f"Job '{callback.__name__}' scheduled for {hour:02d}:{minute:02d} daily.")

    def start(self) -> None:
        self.scheduler.start()
        logger.info("Scheduler started.")

    def shutdown(self) -> None:
        self.scheduler.shutdown()
        logger.info("Scheduler shut down.")