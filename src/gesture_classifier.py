# src/gesture_classifier.py

import math
from typing import Any, List
from src.settings_manager import SettingsManager
import mediapipe as mp

HAND_LANDMARK = mp.solutions.hands.HandLandmark

class GestureClassifier:
    def __init__(self, settings_manager: SettingsManager) -> None:
        self.settings_manager = settings_manager

    def _get_distance(self, p1: Any, p2: Any) -> float:
        """Helper to calculate Euclidean distance between two landmarks."""
        return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2)

    def classify(self, hand_landmarks: Any, handedness: str) -> str | None:
        """Classifies the static pose of a hand using strict, mutually exclusive rules."""
        landmarks = hand_landmarks.landmark
        
        if self._is_thumbs_up(landmarks):
            return "THUMBS_UP"
        if self._is_thumbs_down(landmarks):
            return "THUMBS_DOWN"
        if self._is_fist(landmarks):
            return "FIST"
        if self._is_l_shape_volume(landmarks):
            return "L_SHAPE_VOLUME"
        if self._is_peace_sign(landmarks):
            return "PEACE_SIGN"
        if self._is_pinch(landmarks):
            return "PINCH"
        if self._is_open_palm(landmarks):
            return "OPEN_PALM"
        return None

    def _are_fingers_curled(self, landmarks: List[Any], finger_indices: List[int]) -> bool:
        """Checks if a specific list of fingers are curled."""
        for tip_idx, pip_idx in finger_indices:
            if landmarks[tip_idx].y >= landmarks[pip_idx].y:
                return False
        return True

    def _are_fingers_extended(self, landmarks: List[Any], finger_indices: List[int]) -> bool:
        """Checks if a specific list of fingers are extended."""
        for tip_idx, mcp_idx in finger_indices:
            if landmarks[tip_idx].y >= landmarks[mcp_idx].y:
                return False
        return True

    def _is_fist(self, landmarks: List[Any]) -> bool:
        """A fist: four fingers are curled AND the thumb is tucked in close to the hand."""
        try:
            four_fingers = [
                (HAND_LANDMARK.INDEX_FINGER_TIP, HAND_LANDMARK.INDEX_FINGER_PIP),
                (HAND_LANDMARK.MIDDLE_FINGER_TIP, HAND_LANDMARK.MIDDLE_FINGER_PIP),
                (HAND_LANDMARK.RING_FINGER_TIP, HAND_LANDMARK.RING_FINGER_PIP),
                (HAND_LANDMARK.PINKY_TIP, HAND_LANDMARK.PINKY_PIP)
            ]
            if not self._are_fingers_curled(landmarks, four_fingers):
                return False
            
            thumb_is_tucked = self._get_distance(
                landmarks[HAND_LANDMARK.THUMB_TIP], 
                landmarks[HAND_LANDMARK.INDEX_FINGER_PIP]
            ) < 0.08

            return thumb_is_tucked
        except (IndexError, AttributeError):
            return False

    def _is_thumbs_up(self, landmarks: List[Any]) -> bool:
        """Thumbs Up: Thumb is extended up and is far from the palm, while other fingers are curled."""
        try:
            four_fingers = [
                (HAND_LANDMARK.INDEX_FINGER_TIP, HAND_LANDMARK.INDEX_FINGER_PIP),
                (HAND_LANDMARK.MIDDLE_FINGER_TIP, HAND_LANDMARK.MIDDLE_FINGER_PIP),
                (HAND_LANDMARK.RING_FINGER_TIP, HAND_LANDMARK.RING_FINGER_PIP),
                (HAND_LANDMARK.PINKY_TIP, HAND_LANDMARK.PINKY_PIP)
            ]
            if not self._are_fingers_curled(landmarks, four_fingers):
                return False

            thumb_is_up = landmarks[HAND_LANDMARK.THUMB_TIP].y < landmarks[HAND_LANDMARK.THUMB_IP].y
            
            thumb_is_away = self._get_distance(
                landmarks[HAND_LANDMARK.THUMB_TIP], 
                landmarks[HAND_LANDMARK.PINKY_MCP]
            ) > 0.13

            return thumb_is_up and thumb_is_away
        except (IndexError, AttributeError):
            return False

    def _is_thumbs_down(self, landmarks: List[Any]) -> bool:
        """Thumbs Down: Thumb is pointed down, other four fingers are curled."""
        try:
            four_fingers = [
                (HAND_LANDMARK.INDEX_FINGER_TIP, HAND_LANDMARK.INDEX_FINGER_PIP),
                (HAND_LANDMARK.MIDDLE_FINGER_TIP, HAND_LANDMARK.MIDDLE_FINGER_PIP),
                (HAND_LANDMARK.RING_FINGER_TIP, HAND_LANDMARK.RING_FINGER_PIP),
                (HAND_LANDMARK.PINKY_TIP, HAND_LANDMARK.PINKY_PIP)
            ]
            if not self._are_fingers_curled(landmarks, four_fingers):
                return False
            
            return landmarks[HAND_LANDMARK.THUMB_TIP].y > landmarks[HAND_LANDMARK.THUMB_MCP].y
        except (IndexError, AttributeError):
            return False

    def _is_l_shape_volume(self, landmarks: List[Any]) -> bool:
        """'L' Shape: Thumb and Index are extended, others are curled."""
        try:
            index_thumb = [(HAND_LANDMARK.INDEX_FINGER_TIP, HAND_LANDMARK.INDEX_FINGER_MCP),
                           (HAND_LANDMARK.THUMB_TIP, HAND_LANDMARK.THUMB_MCP)]
            other_fingers = [(HAND_LANDMARK.MIDDLE_FINGER_TIP, HAND_LANDMARK.MIDDLE_FINGER_PIP),
                             (HAND_LANDMARK.RING_FINGER_TIP, HAND_LANDMARK.RING_FINGER_PIP),
                             (HAND_LANDMARK.PINKY_TIP, HAND_LANDMARK.PINKY_PIP)]
            
            return (self._are_fingers_extended(landmarks, index_thumb) and
                    self._are_fingers_curled(landmarks, other_fingers))
        except (IndexError, AttributeError):
            return False

    def _is_peace_sign(self, landmarks: Any) -> bool:
        """Peace Sign: Index and Middle are extended, others are curled."""
        try:
            index_middle = [(HAND_LANDMARK.INDEX_FINGER_TIP, HAND_LANDMARK.INDEX_FINGER_MCP),
                            (HAND_LANDMARK.MIDDLE_FINGER_TIP, HAND_LANDMARK.MIDDLE_FINGER_MCP)]
            ring_pinky = [(HAND_LANDMARK.RING_FINGER_TIP, HAND_LANDMARK.RING_FINGER_PIP),
                          (HAND_LANDMARK.PINKY_TIP, HAND_LANDMARK.PINKY_PIP)]
            
            return (self._are_fingers_extended(landmarks, index_middle) and
                    self._are_fingers_curled(landmarks, ring_pinky))
        except (IndexError, AttributeError):
            return False

    def _is_open_palm(self, landmarks: Any) -> bool:
        """Open Palm: All five fingers are extended."""
        try:
            all_fingers = [
                (HAND_LANDMARK.INDEX_FINGER_TIP, HAND_LANDMARK.INDEX_FINGER_MCP),
                (HAND_LANDMARK.MIDDLE_FINGER_TIP, HAND_LANDMARK.MIDDLE_FINGER_MCP),
                (HAND_LANDMARK.RING_FINGER_TIP, HAND_LANDMARK.RING_FINGER_MCP),
                (HAND_LANDMARK.PINKY_TIP, HAND_LANDMARK.PINKY_MCP),
                (HAND_LANDMARK.THUMB_TIP, HAND_LANDMARK.THUMB_IP)
            ]
            return self._are_fingers_extended(landmarks, all_fingers)
        except (IndexError, AttributeError):
            return False

    def _is_pinch(self, landmarks: Any) -> bool:
        """Pinch: Thumb tip and index finger tip are very close together."""
        try:
            return self._get_distance(landmarks[HAND_LANDMARK.THUMB_TIP], landmarks[HAND_LANDMARK.INDEX_FINGER_TIP]) < 0.04
        except (IndexError, AttributeError):
            return False