# src/workers/input_monitor_worker.py

import logging
import time
from PySide6.QtCore import QThread, Signal
from pynput import keyboard, mouse
from collections import deque
import math

logger = logging.getLogger(__name__)

class InputMonitorWorker(QThread):
    """
    A worker that passively monitors keyboard and mouse activity to gather
    metrics related to user focus and productivity, like typing speed and mouse travel.
    """
    new_input_stats = Signal(dict)  # Emits a dictionary of the latest stats

    def __init__(self, parent=None, interval_seconds: int = 5):
        super().__init__(parent)
        self.running = True
        self.interval = interval_seconds

        # --- Keyboard tracking ---
        self.key_press_timestamps = deque(maxlen=100) # Store timestamps of last 100 presses
        self.backspace_count = 0

        # --- Mouse tracking ---
        self.last_mouse_pos = None
        self.mouse_travel_distance = 0.0

        # --- Setup Listeners ---
        # We run listeners in non-blocking mode
        self.keyboard_listener = keyboard.Listener(on_press=self._on_press)
        self.mouse_listener = mouse.Listener(on_move=self._on_move)

    def _on_press(self, key):
        """Callback for when a key is pressed."""
        self.key_press_timestamps.append(time.time())
        if key == keyboard.Key.backspace:
            self.backspace_count += 1
        return self.running # Return False to stop the listener

    def _on_move(self, x, y):
        """Callback for when the mouse moves."""
        if self.last_mouse_pos is not None:
            dx = x - self.last_mouse_pos[0]
            dy = y - self.last_mouse_pos[1]
            self.mouse_travel_distance += math.sqrt(dx*dx + dy*dy)
        self.last_mouse_pos = (x, y)
        return self.running # Return False to stop the listener

    def run(self):
        """The main loop for the worker thread."""
        logger.info("InputMonitorWorker started.")
        self.keyboard_listener.start()
        self.mouse_listener.start()

        while self.running:
            # Wait for the specified interval
            self.sleep(self.interval)

            # --- Calculate metrics ---
            
            # Typing Speed (Keys Per Minute)
            kpm = 0
            if self.key_press_timestamps:
                # Remove timestamps older than the interval
                cutoff = time.time() - self.interval
                while self.key_press_timestamps and self.key_press_timestamps[0] < cutoff:
                    self.key_press_timestamps.popleft()
                
                if self.key_press_timestamps:
                    # Calculate KPM based on recent key presses
                    num_keys = len(self.key_press_timestamps)
                    kpm = (num_keys / self.interval) * 60

            # Create stats dictionary
            stats = {
                "timestamp": time.time(),
                "kpm": kpm,
                "backspace_count": self.backspace_count,
                "mouse_travel_pixels": self.mouse_travel_distance,
            }

            # Emit the signal and reset period-specific counters
            self.new_input_stats.emit(stats)
            self.backspace_count = 0
            self.mouse_travel_distance = 0.0
            
        # Stop the listeners when the loop ends
        self.keyboard_listener.stop()
        self.mouse_listener.stop()
        logger.info("InputMonitorWorker stopped.")

    def stop(self):
        """Stops the worker thread gracefully."""
        self.running = False