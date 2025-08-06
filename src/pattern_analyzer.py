# src/pattern_analyzer.py

import pandas as pd
from pathlib import Path
from collections import Counter
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

class PatternAnalyzer:
    """Analyzes the activity log to find frequent workspace patterns."""
    
    def __init__(self, log_file: str = "activity_log.csv"):
        self.log_path = Path(log_file)
        self.SESSION_THRESHOLD_SECONDS = 60  # Max time between apps in a session
        self.MIN_PATTERN_FREQUENCY = 3       # How many times a pattern must appear
        self.MIN_PATTERN_LENGTH = 2          # A pattern must involve at least 2 apps

    def _get_sessions(self, df: pd.DataFrame) -> List[List[str]]:
        """Groups app launches into sessions based on time."""
        sessions = []
        if df.empty:
            return sessions

        current_session = [df.iloc[0]['process_name']]
        for i in range(1, len(df)):
            time_diff = (df.iloc[i]['timestamp'] - df.iloc[i-1]['timestamp']).total_seconds()
            if time_diff < self.SESSION_THRESHOLD_SECONDS:
                # Add app to current session if it's not a direct duplicate of the last one
                if df.iloc[i]['process_name'] != current_session[-1]:
                    current_session.append(df.iloc[i]['process_name'])
            else:
                # Time gap is too large, end the current session and start a new one
                if len(current_session) >= self.MIN_PATTERN_LENGTH:
                    sessions.append(current_session)
                current_session = [df.iloc[i]['process_name']]
        
        # Add the last session if it's long enough
        if len(current_session) >= self.MIN_PATTERN_LENGTH:
            sessions.append(current_session)
            
        return sessions

    def find_frequent_patterns(self) -> List[Tuple[Tuple[str, ...], int]]:
        """
        Reads the log file and returns the most frequent application patterns.
        
        Returns:
            A list of tuples, where each tuple is ((app1, app2, ...), frequency).
        """
        if not self.log_path.exists() or self.log_path.stat().st_size == 0:
            return []

        try:
            df = pd.read_csv(self.log_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.drop_duplicates(subset=['timestamp', 'process_name']).sort_values('timestamp')

            sessions = self._get_sessions(df)
            
            # Find all sub-patterns of length >= MIN_PATTERN_LENGTH
            all_patterns = []
            for session in sessions:
                for i in range(len(session) - self.MIN_PATTERN_LENGTH + 1):
                    pattern = tuple(session[i : i + self.MIN_PATTERN_LENGTH])
                    all_patterns.append(pattern)
            
            if not all_patterns:
                return []

            # Count pattern occurrences
            pattern_counts = Counter(all_patterns)
            
            # Filter for patterns that meet the minimum frequency
            frequent_patterns = [
                (pattern, count) for pattern, count in pattern_counts.items()
                if count >= self.MIN_PATTERN_FREQUENCY
            ]
            
            # Sort by frequency (most frequent first)
            frequent_patterns.sort(key=lambda item: item[1], reverse=True)
            
            if frequent_patterns:
                logger.info(f"Found frequent patterns: {frequent_patterns}")
            return frequent_patterns

        except Exception as e:
            logger.error(f"Failed to analyze activity patterns: {e}", exc_info=True)
            return []