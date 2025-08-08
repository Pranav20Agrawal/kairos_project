# src/video_worker.py

import cv2
import mediapipe as mp
import time
from enum import Enum
from collections import deque
from PySide6.QtCore import QThread, Signal, QObject
from src.gesture_classifier import GestureClassifier
from src.settings_manager import SettingsManager
import logging
from typing import Dict, Any, Deque, Optional

HAND_LANDMARK = mp.solutions.hands.HandLandmark
logger = logging.getLogger(__name__)

class GestureState(Enum):
    IDLE = 0
    PRIMED = 1
    COOLDOWN = 2
    VOLUME_CONTROL = 3

class VideoWorker(QThread):
    new_data = Signal(object)
    gesture_detected = Signal(str, object)
    error_occurred = Signal(str, str)
    state_changed = Signal(str)
    # <--- MODIFICATION START: Added the missing signal back to fix the crash --->
    window_targeted = Signal(object)
    # <--- MODIFICATION END --->

    # Tuning parameters
    GESTURE_BUFFER_SIZE = 5
    STABILITY_THRESHOLD = 0.8
    REQUIRED_STABLE_FRAMES = 4
    PRIMED_DURATION = 3.0
    COOLDOWN_DURATION = 1.0 
    
    VOLUME_DISTANCE_THRESHOLD = 0.015 # Sensitivity for spread/pinch movement
    VOLUME_CONTROL_TIMEOUT = 2.0   # How long to stay in volume mode without a pinch

    def __init__(
        self, settings_manager: SettingsManager, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.running = True
        self.gesture_buffer: Deque[str | None] = deque(maxlen=self.GESTURE_BUFFER_SIZE)
        self.stable_gesture: str | None = None
        self.stable_gesture_candidate: str | None = None
        self.stable_frames_count: int = 0
        self.classifier = GestureClassifier(self.settings_manager)
        
        self.volume_control_ref_dist: Optional[float] = None
        self.last_pinch_time: float = 0.0

    def _update_stable_gesture(self) -> None:
        """Analyzes the gesture buffer to find a stable gesture."""
        if not self.gesture_buffer:
            self.stable_gesture = None
            return
        try:
            most_common = max(set(self.gesture_buffer), key=list(self.gesture_buffer).count)
            if most_common and list(self.gesture_buffer).count(most_common) / self.GESTURE_BUFFER_SIZE >= self.STABILITY_THRESHOLD:
                if self.stable_gesture != most_common: logger.debug(f"Stable gesture: {most_common}")
                self.stable_gesture = most_common
            else:
                self.stable_gesture = None
        except (ValueError, TypeError):
            self.stable_gesture = None
            
    def run(self) -> None:
        logger.info("VideoWorker thread started.")
        try:
            mp_hands = mp.solutions.hands
            hands = mp_hands.Hands(min_detection_confidence=0.75, min_tracking_confidence=0.75, max_num_hands=1)
            mp_drawing = mp.solutions.drawing_utils
        except Exception as e:
            self.error_occurred.emit(f"Could not initialize MediaPipe: {e}", "CRITICAL")
            return

        cap = None
        state = GestureState.IDLE
        primed_timestamp, cooldown_timestamp = 0.0, 0.0
        no_hand_counter = 0

        gesture_map: Dict[str, str] = {
            "FIST": "[MEDIA_PLAY_PAUSE]", "PEACE_SIGN": "[MUTE_TOGGLE]",
            "THUMBS_UP": "[NEXT_TRACK]", "THUMBS_DOWN": "[PREVIOUS_TRACK]",
        }

        while self.running:
            try:
                if cap is None:
                    cap = cv2.VideoCapture(self.settings_manager.settings.core.camera_index)
                    if not cap.isOpened(): raise IOError("Cannot open webcam.")
                    logger.info("Webcam connected.")

                ret, frame = cap.read()
                if not ret:
                    if cap: cap.release(); cap = None
                    time.sleep(2); continue

                small_frame_rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
                results = hands.process(small_frame_rgb)
                display_frame = cv2.flip(frame, 1)

                current_frame_gesture: str | None = None
                hand_landmarks = None
                handedness = 'Right' # Default
                if results.multi_hand_landmarks:
                    no_hand_counter = 0
                    hand_landmarks = results.multi_hand_landmarks[0]
                    if results.multi_handedness:
                        handedness = results.multi_handedness[0].classification[0].label
                    mp_drawing.draw_landmarks(display_frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                    current_frame_gesture = self.classifier.classify(hand_landmarks, handedness)
                else:
                    no_hand_counter += 1

                self.gesture_buffer.append(current_frame_gesture)
                self._update_stable_gesture()
                status_text = f"STATE: {state.name}"

                # --- NEW STATE MACHINE FOR "PINCH & SPREAD" VOLUME ---
                if state == GestureState.COOLDOWN and time.time() > cooldown_timestamp + self.COOLDOWN_DURATION:
                    state = GestureState.IDLE

                elif state == GestureState.IDLE:
                    if self.stable_gesture == "OPEN_PALM":
                        state = GestureState.PRIMED
                        primed_timestamp = time.time()
                
                elif state == GestureState.PRIMED:
                    if time.time() > primed_timestamp + self.PRIMED_DURATION or no_hand_counter > 5:
                        state = GestureState.IDLE; continue
                    status_text = f"STATE: PRIMED ({self.PRIMED_DURATION - (time.time() - primed_timestamp):.1f}s)"
                    
                    if self.stable_gesture and self.stable_gesture not in ["OPEN_PALM", None]:
                        if self.stable_gesture == "PINCH":
                            state = GestureState.VOLUME_CONTROL
                            self.volume_control_ref_dist = self.classifier._get_distance(
                                hand_landmarks.landmark[HAND_LANDMARK.THUMB_TIP],
                                hand_landmarks.landmark[HAND_LANDMARK.INDEX_FINGER_TIP]
                            )
                            self.last_pinch_time = time.time()
                            logger.info("Entering Volume Control mode.")
                            continue
                        
                        intent = gesture_map.get(self.stable_gesture)
                        if intent:
                            status_text = f"CONFIRMING: {self.stable_gesture}"
                            if self.stable_gesture == self.stable_gesture_candidate: self.stable_frames_count += 1
                            else: self.stable_gesture_candidate = self.stable_gesture; self.stable_frames_count = 1
                            
                            if self.stable_frames_count >= self.REQUIRED_STABLE_FRAMES:
                                self.gesture_detected.emit(intent, None)
                                state, cooldown_timestamp = GestureState.COOLDOWN, time.time()
                        else: self.stable_gesture_candidate = None; self.stable_frames_count = 0
                    else: self.stable_gesture_candidate = None; self.stable_frames_count = 0
                
                elif state == GestureState.VOLUME_CONTROL:
                    status_text = "STATE: VOLUME"
                    # In this mode, we ONLY care about the distance between thumb and index.
                    # We no longer classify the whole hand gesture.
                    if hand_landmarks:
                        self.last_pinch_time = time.time()
                        current_dist = self.classifier._get_distance(
                            hand_landmarks.landmark[HAND_LANDMARK.THUMB_TIP],
                            hand_landmarks.landmark[HAND_LANDMARK.INDEX_FINGER_TIP]
                        )
                        delta_dist = current_dist - self.volume_control_ref_dist

                        if delta_dist > self.VOLUME_DISTANCE_THRESHOLD: # Fingers moved apart
                            self.gesture_detected.emit("[VOLUME_UP]", None)
                            self.volume_control_ref_dist = current_dist
                        elif delta_dist < -self.VOLUME_DISTANCE_THRESHOLD: # Fingers moved closer
                            self.gesture_detected.emit("[VOLUME_DOWN]", None)
                            self.volume_control_ref_dist = current_dist
                        
                        # Exit if the user makes a fist.
                        if self.classifier._is_fist(hand_landmarks.landmark):
                            state = GestureState.IDLE
                            logger.info("Exiting Volume Control mode (fist detected).")

                    # Also exit after a timeout
                    if time.time() > self.last_pinch_time + self.VOLUME_CONTROL_TIMEOUT:
                        state = GestureState.IDLE
                        logger.info("Exiting Volume Control mode (timeout).")
                
                cv2.putText(display_frame, status_text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2, cv2.LINE_AA)
                if self.stable_gesture:
                    cv2.putText(display_frame, f"GESTURE: {self.stable_gesture}", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)
                
                self.new_data.emit(display_frame)

            except Exception as e:
                logger.error(f"Error in video worker loop: {e}", exc_info=True)
                if cap: cap.release(); cap = None
                time.sleep(5)

        if cap: cap.release()
        hands.close()
        logger.info("VideoWorker thread finished.")

    def stop(self) -> None:
        self.running = False
        logger.info("VideoWorker stop signal received.")