# src/gesture_classifier.py

import math
from src.settings_manager import SettingsManager
from typing import Any, List, Deque
from collections import deque
import mediapipe as mp

# --- NEW: Define landmark constants for readability ---
HAND_LANDMARK = mp.solutions.hands.HandLandmark

class GestureClassifier:
    def __init__(self, settings_manager: SettingsManager) -> None:
        self.settings_manager = settings_manager
        # History buffer for dynamic gestures
        self.hand_positions: Deque[tuple[float, float]] = deque(maxlen=20)

        # Thresholds for swipe detection
        self.SWIPE_THRESHOLD_X = 0.3
        self.SWIPE_AXIS_LOCK_Y = 0.15

        # Thresholds for scroll detection
        self.SCROLL_THRESHOLD_Y = 0.25
        self.SCROLL_AXIS_LOCK_X = 0.1

    def classify(self, hand_landmarks: Any) -> str | None:
        """
        Classifies gestures, prioritizing dynamic gestures over static poses.
        The order of static gesture checks is important to avoid ambiguity.
        """
        # --- Dynamic Gestures First ---
        wrist_landmark = hand_landmarks.landmark[HAND_LANDMARK.WRIST]
        self.hand_positions.append((wrist_landmark.x, wrist_landmark.y))

        dynamic_gesture = self._classify_dynamic_gesture()
        if dynamic_gesture:
            return dynamic_gesture

        # --- Static Poses (from most to least specific) ---
        landmarks = hand_landmarks.landmark
        if self._is_thumbs_up(landmarks):
            return "THUMBS_UP"
        if self._is_pointing(landmarks):
            return "POINTING"
        if self._is_fist(landmarks):
            return "FIST"
        if self._is_open_palm(landmarks):
            return "OPEN_PALM"
            
        return None

    def _is_finger_extended(self, landmarks: Any, tip_index: int, dip_index: int) -> bool:
        """Checks if a finger is extended by comparing y-coordinates."""
        tip = landmarks[tip_index]
        dip = landmarks[dip_index]
        return tip.y < dip.y

    def _is_finger_curled(self, landmarks: Any, tip_index: int, dip_index: int) -> bool:
        """Checks if a finger is curled by comparing y-coordinates."""
        tip = landmarks[tip_index]
        dip = landmarks[dip_index]
        return tip.y > dip.y

    def _is_open_palm(self, landmarks: Any) -> bool:
        """New Rule: Checks if all five fingers are extended."""
        try:
            thumb_extended = landmarks[HAND_LANDMARK.THUMB_TIP].x < landmarks[HAND_LANDMARK.THUMB_IP].x
            index_extended = self._is_finger_extended(landmarks, HAND_LANDMARK.INDEX_FINGER_TIP, HAND_LANDMARK.INDEX_FINGER_DIP)
            middle_extended = self._is_finger_extended(landmarks, HAND_LANDMARK.MIDDLE_FINGER_TIP, HAND_LANDMARK.MIDDLE_FINGER_DIP)
            ring_extended = self._is_finger_extended(landmarks, HAND_LANDMARK.RING_FINGER_TIP, HAND_LANDMARK.RING_FINGER_DIP)
            pinky_extended = self._is_finger_extended(landmarks, HAND_LANDMARK.PINKY_TIP, HAND_LANDMARK.PINKY_DIP)
            return all([thumb_extended, index_extended, middle_extended, ring_extended, pinky_extended])
        except (IndexError, AttributeError):
            return False

    def _is_fist(self, landmarks: Any) -> bool:
        """New Rule: Checks if four fingers are curled and thumb is closed."""
        try:
            index_curled = self._is_finger_curled(landmarks, HAND_LANDMARK.INDEX_FINGER_TIP, HAND_LANDMARK.INDEX_FINGER_DIP)
            middle_curled = self._is_finger_curled(landmarks, HAND_LANDMARK.MIDDLE_FINGER_TIP, HAND_LANDMARK.MIDDLE_FINGER_DIP)
            ring_curled = self._is_finger_curled(landmarks, HAND_LANDMARK.RING_FINGER_TIP, HAND_LANDMARK.RING_FINGER_DIP)
            pinky_curled = self._is_finger_curled(landmarks, HAND_LANDMARK.PINKY_TIP, HAND_LANDMARK.PINKY_DIP)
            
            # Check if thumb is closed over the fingers
            thumb_closed = landmarks[HAND_LANDMARK.THUMB_TIP].x > landmarks[HAND_LANDMARK.INDEX_FINGER_PIP].x
            
            return all([index_curled, middle_curled, ring_curled, pinky_curled, thumb_closed])
        except (IndexError, AttributeError):
            return False

    def _is_thumbs_up(self, landmarks: Any) -> bool:
        """New Rule: Thumb is extended up, other four fingers are curled."""
        try:
            thumb_up = self._is_finger_extended(landmarks, HAND_LANDMARK.THUMB_TIP, HAND_LANDMARK.THUMB_IP)
            index_curled = self._is_finger_curled(landmarks, HAND_LANDMARK.INDEX_FINGER_TIP, HAND_LANDMARK.INDEX_FINGER_DIP)
            middle_curled = self._is_finger_curled(landmarks, HAND_LANDMARK.MIDDLE_FINGER_TIP, HAND_LANDMARK.MIDDLE_FINGER_DIP)
            ring_curled = self._is_finger_curled(landmarks, HAND_LANDMARK.RING_FINGER_TIP, HAND_LANDMARK.RING_FINGER_DIP)
            pinky_curled = self._is_finger_curled(landmarks, HAND_LANDMARK.PINKY_TIP, HAND_LANDMARK.PINKY_DIP)
            return all([thumb_up, index_curled, middle_curled, ring_curled, pinky_curled])
        except (IndexError, AttributeError):
            return False

    def _is_pointing(self, landmarks: Any) -> bool:
        """New Rule: Index finger is extended, others are curled."""
        try:
            index_extended = self._is_finger_extended(landmarks, HAND_LANDMARK.INDEX_FINGER_TIP, HAND_LANDMARK.INDEX_FINGER_DIP)
            middle_curled = self._is_finger_curled(landmarks, HAND_LANDMARK.MIDDLE_FINGER_TIP, HAND_LANDMARK.MIDDLE_FINGER_DIP)
            ring_curled = self._is_finger_curled(landmarks, HAND_LANDMARK.RING_FINGER_TIP, HAND_LANDMARK.RING_FINGER_DIP)
            pinky_curled = self._is_finger_curled(landmarks, HAND_LANDMARK.PINKY_TIP, HAND_LANDMARK.PINKY_DIP)
            return all([index_extended, middle_curled, ring_curled, pinky_curled])
        except (IndexError, AttributeError):
            return False
            
    def _classify_dynamic_gesture(self) -> str | None:
        """Analyzes the hand position history to detect swipes and scrolls."""
        if len(self.hand_positions) < self.hand_positions.maxlen:
            return None

        start_x, start_y = self.hand_positions[0]
        end_x, end_y = self.hand_positions[-1]
        delta_x = end_x - start_x
        delta_y = end_y - start_y

        if abs(delta_x) > self.SWIPE_THRESHOLD_X and abs(delta_y) < self.SWIPE_AXIS_LOCK_Y:
            self.hand_positions.clear()
            return "SWIPE_LEFT" if delta_x > 0 else "SWIPE_RIGHT"

        if abs(delta_y) > self.SCROLL_THRESHOLD_Y and abs(delta_x) < self.SCROLL_AXIS_LOCK_X:
            self.hand_positions.clear()
            return "SCROLL_UP" if delta_y < 0 else "SCROLL_DOWN"

        return None