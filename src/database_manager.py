# src/database_manager.py

import sqlite3
from datetime import datetime
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Handles all database operations for K.A.I.R.O.S."""

    def __init__(self, db_name: str = "feedback.db") -> None:
        self.conn: sqlite3.Connection | None = None
        try:
            self.conn = sqlite3.connect(db_name, check_same_thread=False)
            self.cursor: sqlite3.Cursor = self.conn.cursor()
            logger.info(f"Successfully connected to database '{db_name}'.")
            self.create_table()
        except sqlite3.Error as e:
            logger.critical(
                f"Failed to connect to or create database '{db_name}': {e}",
                exc_info=True,
            )
            self.conn = None

    def create_table(self) -> None:
        if not self.conn:
            return
        try:
            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    original_text TEXT NOT NULL,
                    predicted_intent TEXT,
                    predicted_entity TEXT,
                    corrected_intent TEXT,
                    corrected_entity TEXT
                )
            """
            )
            self.conn.commit()
            logger.debug("'feedback_log' table exists or was created successfully.")
        except sqlite3.Error as e:
            logger.error(f"Failed to create 'feedback_log' table: {e}", exc_info=True)

    def get_training_data(self) -> List[Tuple[str, str]]:
        if not self.conn:
            return []
        try:
            self.cursor.execute(
                """
                SELECT original_text, corrected_intent FROM feedback_log
                WHERE predicted_intent != corrected_intent AND corrected_intent IS NOT NULL
                """
            )
            data = self.cursor.fetchall()
            logger.info(f"Retrieved {len(data)} records for NLU training.")
            return data
        except sqlite3.Error as e:
            logger.error(f"Failed to retrieve training data: {e}", exc_info=True)
            return []

    def log_nlu_result(
        self, original_text: str, predicted_intent: str, predicted_entity: str | None
    ) -> int | None:
        if not self.conn: return None
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self.cursor.execute(
                """
                INSERT INTO feedback_log (timestamp, original_text, predicted_intent, predicted_entity, corrected_intent, corrected_entity)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (timestamp, original_text, predicted_intent, predicted_entity, predicted_intent, predicted_entity),
            )
            self.conn.commit()
            log_id: int = self.cursor.lastrowid
            logger.info(f"Logged NLU result with ID {log_id}.")
            return log_id
        except sqlite3.Error as e:
            logger.error(f"Failed to log NLU result: {e}", exc_info=True)
            return None

    def update_correction(
        self, log_id: int, corrected_intent: str, corrected_entity: str | None
    ) -> None:
        if not self.conn: return
        try:
            self.cursor.execute(
                """
                UPDATE feedback_log 
                SET corrected_intent = ?, corrected_entity = ?
                WHERE id = ?
            """,
                (corrected_intent, corrected_entity, log_id),
            )
            self.conn.commit()
            logger.info(f"Updated correction for log ID {log_id}.")
        except sqlite3.Error as e:
            logger.error(
                f"Failed to update correction for log ID {log_id}: {e}", exc_info=True
            )

    def get_command_stats(self) -> Dict[str, Any]:
        default_stats = {"total": 0, "accuracy": "N/A", "most_used": "N/A"}
        if not self.conn: return default_stats
        try:
            self.cursor.execute("SELECT COUNT(*) FROM feedback_log")
            total = self.cursor.fetchone()[0]
            self.cursor.execute(
                "SELECT COUNT(*) FROM feedback_log WHERE predicted_intent != corrected_intent OR predicted_entity != corrected_entity"
            )
            corrections = self.cursor.fetchone()[0]
            self.cursor.execute(
                """
                SELECT corrected_intent, COUNT(corrected_intent) as count 
                FROM feedback_log 
                WHERE corrected_intent IS NOT NULL AND corrected_intent != '[UNKNOWN_INTENT]'
                GROUP BY corrected_intent 
                ORDER BY count DESC 
                LIMIT 1
            """
            )
            most_used_row = self.cursor.fetchone()
            most_used = most_used_row[0] if most_used_row else "N/A"
            accuracy = ((total - corrections) / total * 100) if total > 0 else 100
            return {"total": total, "accuracy": f"{accuracy:.2f}%", "most_used": most_used}
        except Exception as e:
            logger.error(f"Failed to calculate command stats: {e}", exc_info=True)
            return default_stats

    def get_intent_distribution(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Gets the counts of the most used intents."""
        if not self.conn: return []
        try:
            self.cursor.execute(
                f"""
                SELECT corrected_intent, COUNT(corrected_intent) as count
                FROM feedback_log
                WHERE corrected_intent IS NOT NULL AND corrected_intent != '[UNKNOWN_INTENT]'
                GROUP BY corrected_intent
                ORDER BY count DESC
                LIMIT {limit}
                """
            )
            return self.cursor.fetchall()
        except Exception as e:
            logger.error(f"Failed to get intent distribution: {e}", exc_info=True)
            return []

    def get_usage_over_time(self, days: int = 30) -> List[Tuple[float, int]]:
        """Gets the number of commands used per day for the last N days."""
        if not self.conn: return []
        try:
            self.cursor.execute(
                f"""
                SELECT DATE(timestamp), COUNT(*)
                FROM feedback_log
                WHERE DATE(timestamp) >= DATE('now', '-{days} days')
                GROUP BY DATE(timestamp)
                ORDER BY DATE(timestamp)
                """
            )
            rows = self.cursor.fetchall()
            # Convert date strings to timestamps for plotting
            return [(datetime.strptime(date_str, '%Y-%m-%d').timestamp(), count) for date_str, count in rows]
        except Exception as e:
            logger.error(f"Failed to get usage over time: {e}", exc_info=True)
            return []

    def __del__(self) -> None:
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed.")