# src/ui_components/widgets/weather_widget.py

import logging
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QLabel, QHBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from src.workers.weather_worker import WeatherWorker

logger = logging.getLogger(__name__)

class WeatherWidget(QWidget):
    """A widget to display the current weather."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.weather_icons = self._load_weather_icons()
        self._setup_ui()
        self._start_worker()

    def _load_weather_icons(self):
        """Pre-loads weather icons into a dictionary for quick access."""
        # WMO Weather interpretation codes mapped to icon filenames
        # (This can be expanded with more icons)
        code_map = {
            0: "sun.png",  # Clear sky
            1: "sun_cloud.png",  # Mainly clear
            2: "sun_cloud.png",  # Partly cloudy
            3: "cloud.png",  # Overcast
            45: "fog.png", 48: "fog.png", # Fog
            51: "drizzle.png", 53: "drizzle.png", 55: "drizzle.png", # Drizzle
            61: "rain.png", 63: "rain.png", 65: "rain.png", # Rain
            80: "rain.png", 81: "rain.png", 82: "rain.png", # Showers
            71: "snow.png", 73: "snow.png", 75: "snow.png", # Snow
            95: "thunder.png", 96: "thunder.png", 99: "thunder.png" # Thunderstorm
        }
        return code_map

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        group_box = QGroupBox("Current Weather")
        self.group_layout = QHBoxLayout(group_box)

        self.icon_label = QLabel("...")
        self.icon_label.setFixedSize(64, 64)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.temp_label = QLabel("--°C")
        self.temp_label.setStyleSheet("font-size: 24pt; font-weight: bold;")
        
        self.location_label = QLabel("Fetching...")
        self.location_label.setStyleSheet("font-size: 10pt; color: #aaa;")

        text_layout = QVBoxLayout()
        text_layout.addWidget(self.temp_label)
        text_layout.addWidget(self.location_label)
        text_layout.addStretch()

        self.group_layout.addWidget(self.icon_label)
        self.group_layout.addLayout(text_layout)
        layout.addWidget(group_box)

    def _start_worker(self):
        self.worker = WeatherWorker()
        self.worker.weather_updated.connect(self.update_weather)
        self.worker.error_occurred.connect(self.show_error)
        self.worker.start()

    def update_weather(self, data):
        """Slot to update the UI with new weather data."""
        self.temp_label.setText(f"{data['temperature']}°C")
        self.location_label.setText(data['location'])
        
        icon_name = self.weather_icons.get(data['weather_code'], "unknown.png")
        pixmap = QPixmap(f"assets/weather_icons/{icon_name}")
        self.icon_label.setPixmap(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def show_error(self, message):
        """Slot to show an error state in the widget."""
        self.temp_label.setText("--°C")
        self.location_label.setText(message)
        pixmap = QPixmap("assets/weather_icons/unknown.png")
        self.icon_label.setPixmap(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))