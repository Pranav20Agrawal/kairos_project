# src/activity_analyzer.py

import logging
import time
from PySide6.QtCore import QObject, Signal, Slot, QTimer
from collections import Counter
import pandas as pd
from pathlib import Path
from typing import List, Tuple, Dict, TYPE_CHECKING

# Forward declaration for type hinting
if TYPE_CHECKING:
    from src.llm_handler import LlmHandler

logger = logging.getLogger(__name__)

# --- The existing PatternAnalyzer remains for now ---
class PatternAnalyzer:
    """Analyzes the activity log to find frequent workspace patterns."""
    # (The code for this class is unchanged)
    def __init__(self, log_file: str = "activity_log.csv"):
        self.log_path = Path(log_file)
        # ... rest of the class ...

# --- NEW: The intelligent SessionAnalyzer ---
class SessionAnalyzer(QObject):
    """
    Analyzes real-time user activity to identify meaningful work sessions,
    then uses an LLM to suggest workflow automation macros.
    """
    suggestion_ready = Signal(dict)  # Emits the LLM's suggestion

    SESSION_TIMEOUT_SECONDS = 120 # Inactivity duration to end a session
    MIN_SESSION_LENGTH = 3        # A session must have at least 3 distinct actions

    def __init__(self, llm_handler: "LlmHandler", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.llm_handler = llm_handler
        self.current_session: List[Dict] = []
        
        self.session_timeout_timer = QTimer(self)
        self.session_timeout_timer.setSingleShot(True)
        self.session_timeout_timer.setInterval(self.SESSION_TIMEOUT_SECONDS * 1000)
        self.session_timeout_timer.timeout.connect(self._analyze_session)

    @Slot(dict)
    def on_activity_logged(self, activity: dict) -> None:
        """Receives a new activity from the logger and adds it to the current session."""
        # Add activity to the session, avoiding direct duplicates
        if not self.current_session or self.current_session[-1]["window_title"] != activity["window_title"]:
            self.current_session.append(activity)
            logger.debug(f"Activity added to session. Current length: {len(self.current_session)}")

        # Reset the inactivity timer every time a new activity occurs
        self.session_timeout_timer.start()

    def _analyze_session(self) -> None:
        """
        Called after a period of user inactivity. Analyzes the completed session
        and asks the LLM for a macro suggestion.
        """
        logger.info(f"Session timeout reached. Analyzing session of {len(self.current_session)} actions.")

        if len(self.current_session) >= self.MIN_SESSION_LENGTH:
            # We have a meaningful session to analyze
            session_log = self.current_session
            
            # Ask the LLM to process this workflow in the background
            # Note: The LlmHandler call might be blocking, consider a QThread if it's slow
            suggestion = self.llm_handler.analyze_workflow(session_log)
            
            if suggestion and "macro_name" in suggestion:
                logger.info(f"LLM suggested a new macro: '{suggestion['macro_name']}'")
                # Add the original action sequence to the suggestion dictionary
                suggestion['actions'] = session_log
                self.suggestion_ready.emit(suggestion)

        # Clear the session for the next one
        self.current_session = []