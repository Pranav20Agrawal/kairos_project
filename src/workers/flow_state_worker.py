# src/workers/flow_state_worker.py

import logging
import time
from enum import Enum # <-- ADD THIS LINE
from PySide6.QtCore import QObject, QThread, Signal, Slot, QTimer
from collections import deque

logger = logging.getLogger(__name__)

class FlowState(str, Enum):
    IDLE = "IDLE"
    FOCUSED = "FOCUSED"

class FlowStateWorker(QThread):
    """
    Analyzes various data streams (input, activity, video) to determine
    if the user is in a "flow state" of deep work.
    """
    flow_state_changed = Signal(str)  # Emits the new FlowState (e.g., "FOCUSED")

    # --- CONFIGURABLE THRESHOLDS ---
    SCORE_THRESHOLD_TO_FOCUS = 0.75  # Score needed to enter flow state
    SCORE_THRESHOLD_TO_IDLE = 0.50   # Score below which to exit flow state
    DATA_RECENCY_SECONDS = 15        # How long to consider data points as "recent"
    CALCULATION_INTERVAL_MS = 2000   # How often to recalculate the score

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.running = True
        self.current_state = FlowState.IDLE
        
        # Data buffers to store recent stats from other workers
        self.input_stats_buffer = deque()
        self.activity_stats_buffer = deque()
        self.video_stats_buffer = deque()

    def run(self) -> None:
        """The main loop for the worker thread, driven by a timer."""
        logger.info("FlowStateWorker started.")
        
        # Use a QTimer for periodic checks, which is safer in a Qt thread
        self.timer = QTimer()
        self.timer.timeout.connect(self._recalculate_state)
        self.timer.start(self.CALCULATION_INTERVAL_MS)
        
        # Start the event loop for the timer
        self.exec()

        logger.info("FlowStateWorker stopped.")

    def _cleanup_buffers(self) -> None:
        """Removes old data points from the buffers."""
        cutoff_time = time.time() - self.DATA_RECENCY_SECONDS
        while self.input_stats_buffer and self.input_stats_buffer[0]['timestamp'] < cutoff_time:
            self.input_stats_buffer.popleft()
        while self.activity_stats_buffer and self.activity_stats_buffer[0]['timestamp'] < cutoff_time:
            self.activity_stats_buffer.popleft()
        while self.video_stats_buffer and self.video_stats_buffer[0]['timestamp'] < cutoff_time:
            self.video_stats_buffer.popleft()

    def _calculate_flow_score(self) -> float:
        """Calculates the current flow score based on buffered data."""
        self._cleanup_buffers()

        # --- Define Weights for each metric ---
        # These can be tuned later for personalization
        weights = {
            "kpm": 0.4,
            "mouse": 0.1,
            "switching": 0.3,
            "head_pose": 0.2
        }

        # --- Normalize and Score each metric from 0.0 to 1.0 ---
        
        # 1. Input Score (Typing Speed is a strong indicator of focus)
        kpm_values = [s['kpm'] for s in self.input_stats_buffer]
        avg_kpm = sum(kpm_values) / len(kpm_values) if kpm_values else 0
        # Normalize KPM: Assume a "good" KPM is around 300. Score is capped at 1.0.
        kpm_score = min(avg_kpm / 300.0, 1.0)

        # 2. Mouse Score (Low mouse travel can indicate focused reading/coding)
        mouse_travel = sum(s['mouse_travel_pixels'] for s in self.input_stats_buffer)
        # Normalize mouse travel: Less travel = higher score. Assume >5000px is high activity.
        mouse_score = 1.0 - min(mouse_travel / 5000.0, 1.0)

        # 3. Activity Score (Fewer app switches = more focus)
        app_switches = sum(s['app_switches'] for s in self.activity_stats_buffer)
        # Normalize switching: Score decreases with each switch.
        switching_score = max(0, 1.0 - (app_switches * 0.25))

        # 4. Video Score (High head stability = looking at the screen)
        stability_values = [s['head_stability'] for s in self.video_stats_buffer]
        avg_stability = sum(stability_values) / len(stability_values) if stability_values else 0
        head_pose_score = avg_stability # Already a 0-1 score

        # --- Calculate Final Weighted Score ---
        final_score = (
            (kpm_score * weights["kpm"]) +
            (mouse_score * weights["mouse"]) +
            (switching_score * weights["switching"]) +
            (head_pose_score * weights["head_pose"])
        )
        
        logger.debug(
            f"Flow Score: {final_score:.2f} [KPM: {kpm_score:.2f}, Mouse: {mouse_score:.2f}, "
            f"Switch: {switching_score:.2f}, Pose: {head_pose_score:.2f}]"
        )
        return final_score

    def _recalculate_state(self) -> None:
        """Periodically recalculates the flow score and updates the state if it changes."""
        score = self._calculate_flow_score()
        new_state = self.current_state

        if self.current_state == FlowState.IDLE and score >= self.SCORE_THRESHOLD_TO_FOCUS:
            new_state = FlowState.FOCUSED
        elif self.current_state == FlowState.FOCUSED and score < self.SCORE_THRESHOLD_TO_IDLE:
            new_state = FlowState.IDLE

        if new_state != self.current_state:
            self.current_state = new_state
            logger.info(f"Flow state changed to: {self.current_state.name}")
            self.flow_state_changed.emit(self.current_state.name)

    @Slot(dict)
    def update_input_stats(self, stats: dict) -> None:
        self.input_stats_buffer.append(stats)

    @Slot(dict)
    def update_activity_stats(self, stats: dict) -> None:
        self.activity_stats_buffer.append(stats)

    @Slot(dict)
    def update_video_stats(self, stats: dict) -> None:
        self.video_stats_buffer.append(stats)

    def stop(self) -> None:
        """Stops the worker thread gracefully."""
        self.running = False
        if hasattr(self, 'timer'):
            self.timer.stop()
        self.quit() # Exit the event loop