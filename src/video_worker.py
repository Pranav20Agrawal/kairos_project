# src/video_worker.py

import cv2
import numpy as np
import mediapipe as mp
import time
from enum import Enum
from collections import deque
from PySide6.QtCore import QThread, Signal, QObject
from src.gesture_classifier import GestureClassifier
from src.settings_manager import SettingsManager
import logging
from typing import Dict, Any, Deque
import pyautogui
import pygetwindow as gw

logger = logging.getLogger(__name__)


class GestureState(Enum):
    IDLE = 0
    PRIMED = 1
    COOLDOWN = 2


class VideoWorker(QThread):
    new_data = Signal(np.ndarray)
    gesture_detected = Signal(str)
    error_occurred = Signal(str, str)
    state_changed = Signal(str)
    window_targeted = Signal(object)

    # --- NEW: Constants for the stability buffer and state machine ---
    GESTURE_BUFFER_SIZE = 7        # Look at the last 7 frames to determine stability
    STABILITY_THRESHOLD = 0.8      # A gesture must be present in 80% of frames to be "stable"
    REQUIRED_STABLE_FRAMES = 8     # Hold a stable gesture for 8 frames to confirm
    # ---

    PRIMED_DURATION = 3
    COOLDOWN_DURATION = 2
    IDLE_AFTER_N_FRAMES = 30
    IDLE_SLEEP_DURATION = 0.1
    POINTING_CONFIRM_FRAMES = 5

    def __init__(
        self, settings_manager: SettingsManager, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.running = True

        # --- NEW: Attributes for the stability logic ---
        self.gesture_buffer: Deque[str | None] = deque(maxlen=self.GESTURE_BUFFER_SIZE)
        self.stable_gesture: str | None = None
        self.stable_gesture_candidate: str | None = None
        self.stable_frames_count: int = 0
        # ---

    def _update_stable_gesture(self) -> None:
        """Analyzes the gesture buffer to find a stable gesture, debouncing flicker."""
        if len(self.gesture_buffer) < self.GESTURE_BUFFER_SIZE:
            self.stable_gesture = None
            return

        # Find the most common gesture in the buffer
        try:
            most_common = max(set(self.gesture_buffer), key=list(self.gesture_buffer).count)
            count = self.gesture_buffer.count(most_common)
            
            # If a gesture is consistently detected, declare it as stable
            if most_common is not None and (count / self.GESTURE_BUFFER_SIZE) >= self.STABILITY_THRESHOLD:
                self.stable_gesture = most_common
            else:
                self.stable_gesture = None
        except (ValueError, TypeError):
            self.stable_gesture = None
            
    def run(self) -> None:
        logger.info("VideoWorker thread started.")
        try:
            mp_hands = mp.solutions.hands
            hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7)
            mp_drawing = mp.solutions.drawing_utils
            classifier = GestureClassifier(self.settings_manager)
            logger.info("MediaPipe Hands model and GestureClassifier initialized.")
        except Exception as e:
            msg = "Critical Error: Could not initialize MediaPipe."
            logger.critical(f"{msg}: {e}", exc_info=True)
            self.error_occurred.emit(msg, "CRITICAL")
            return

        cap = None
        state = GestureState.IDLE
        primed_timestamp: float = 0.0
        cooldown_timestamp: float = 0.0
        
        no_hand_counter = 0
        is_in_idle_mode = False

        pointing_candidate_window = None
        pointing_confirm_frames = 0
        screen_width, screen_height = pyautogui.size()

        gesture_map: Dict[str, str] = {
            "FIST": "[MEDIA_PLAY_PAUSE]",
            "THUMBS_UP": "[CONFIRM_ACTION]",
            "SWIPE_LEFT": "[NEXT_TRACK]",
            "SWIPE_RIGHT": "[PREVIOUS_TRACK]",
            "SCROLL_UP": "[SCROLL_UP]",
            "SCROLL_DOWN": "[SCROLL_DOWN]",
        }

        while self.running:
            try:
                if cap is None:
                    # (Camera initialization logic remains the same)
                    camera_index = self.settings_manager.settings.core.camera_index
                    logger.info(f"Attempting to connect to webcam at index {camera_index}...")
                    cap = cv2.VideoCapture(camera_index)
                    if not cap.isOpened() and camera_index != 0:
                        logger.warning(f"Failed to open camera {camera_index}. Falling back to default.")
                        self.error_occurred.emit(f"Could not open camera {camera_index}. Trying default.", "WARNING")
                        cap = cv2.VideoCapture(0)
                    if not cap.isOpened():
                        raise IOError("Cannot open any webcam.")
                    logger.info(f"Webcam connected successfully.")

                ret, frame = cap.read()
                if not ret:
                    if cap: cap.release()
                    cap = None; time.sleep(2); continue

                small_frame = cv2.resize(frame, (320, 180))
                small_frame_rgb = cv2.cvtColor(cv2.flip(small_frame, 1), cv2.COLOR_BGR2RGB)
                results = hands.process(small_frame_rgb)
                display_frame = cv2.flip(frame, 1)

                current_frame_gesture: str | None = None
                if results.multi_hand_landmarks:
                    no_hand_counter = 0
                    if is_in_idle_mode:
                        is_in_idle_mode = False; logger.info("Hand detected. Resuming.")
                    
                    for hand_landmarks in results.multi_hand_landmarks:
                        mp_drawing.draw_landmarks(display_frame, hand_landmarks, mp.solutions.hands.HAND_CONNECTIONS)
                        current_frame_gesture = classifier.classify(hand_landmarks)
                        # Pointing logic is separate from the main state machine
                        if current_frame_gesture == "POINTING":
                            # (Pointing logic remains the same)
                            target_window = self._get_targeted_window(hand_landmarks, screen_width, screen_height)
                            if target_window and target_window.title == (pointing_candidate_window.title if pointing_candidate_window else None):
                                pointing_confirm_frames += 1
                            else:
                                pointing_candidate_window = target_window; pointing_confirm_frames = 1
                            if pointing_confirm_frames >= self.POINTING_CONFIRM_FRAMES:
                                self.window_targeted.emit(target_window)
                                cv2.putText(display_frame, f"TARGETED: {target_window.title[:20]}", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                        else:
                            pointing_confirm_frames = 0; pointing_candidate_window = None
                else:
                    no_hand_counter += 1

                # --- NEW STABILITY LOGIC ---
                self.gesture_buffer.append(current_frame_gesture)
                self._update_stable_gesture()
                # ---

                # --- REWRITTEN STATE MACHINE ---
                status_text = f"STATE: {state.name}"

                if state == GestureState.COOLDOWN and time.time() - cooldown_timestamp > self.COOLDOWN_DURATION:
                    state = GestureState.IDLE; self.state_changed.emit(state.name)

                if state == GestureState.IDLE:
                    if self.stable_gesture == "OPEN_PALM":
                        state = GestureState.PRIMED; self.state_changed.emit(state.name)
                        primed_timestamp = time.time()
                
                elif state == GestureState.PRIMED:
                    remaining_time = self.PRIMED_DURATION - (time.time() - primed_timestamp)
                    status_text = f"STATE: PRIMED ({int(remaining_time)}s left)"
                    if remaining_time <= 0 or self.stable_gesture is None:
                        state = GestureState.IDLE; self.state_changed.emit(state.name)
                        continue

                    # Check for a command gesture (anything other than OPEN_PALM)
                    if self.stable_gesture and self.stable_gesture != "OPEN_PALM":
                        intent_candidate = gesture_map.get(self.stable_gesture)
                        if intent_candidate:
                            if intent_candidate == self.stable_gesture_candidate:
                                self.stable_frames_count += 1
                            else:
                                self.stable_gesture_candidate = intent_candidate
                                self.stable_frames_count = 1
                            
                            status_text = f"CONFIRMING: {self.stable_gesture}"

                            if self.stable_frames_count >= self.REQUIRED_STABLE_FRAMES:
                                self.gesture_detected.emit(intent_candidate)
                                state = GestureState.COOLDOWN; self.state_changed.emit(state.name)
                                cooldown_timestamp = time.time()
                                self.stable_gesture_candidate = None
                                self.stable_frames_count = 0
                    else:
                        self.stable_gesture_candidate = None
                        self.stable_frames_count = 0
                # --- END REWRITTEN STATE MACHINE ---

                cv2.putText(display_frame, status_text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2, cv2.LINE_AA)
                if self.stable_gesture:
                    feedback_text = f"GESTURE: {self.stable_gesture}"
                    cv2.putText(display_frame, feedback_text, (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2, cv2.LINE_AA)
                
                self.new_data.emit(display_frame)

                if no_hand_counter > self.IDLE_AFTER_N_FRAMES:
                    if not is_in_idle_mode:
                        is_in_idle_mode = True; logger.info("No hand detected. Entering idle mode.")
                    time.sleep(self.IDLE_SLEEP_DURATION)

            except Exception as e:
                msg = "An unexpected error occurred in the video worker."
                logger.error(f"{msg}: {e}", exc_info=True)
                self.error_occurred.emit(msg, "WARNING")
                if cap: cap.release(); cap = None
                time.sleep(5)

        if cap: cap.release()
        hands.close()
        logger.info("VideoWorker thread finished and cleaned up.")

    def _get_targeted_window(self, landmarks: Any, sw: int, sh: int) -> Any:
        try:
            point_x_norm = landmarks[mp.solutions.hands.HandLandmark.INDEX_FINGER_TIP].x
            point_y_norm = landmarks[mp.solutions.hands.HandLandmark.INDEX_FINGER_TIP].y
            point_x_screen = int((1 - point_x_norm) * sw)
            point_y_screen = int(point_y_norm * sh)
            for window in gw.getAllWindows():
                if window.isVisible and window.width > 1 and window.height > 1:
                    if window.left < point_x_screen < window.right and window.top < point_y_screen < window.bottom:
                        return window
        except Exception: return None
        return None

    def stop(self) -> None:
        self.running = False
        logger.info("VideoWorker stop signal received.")