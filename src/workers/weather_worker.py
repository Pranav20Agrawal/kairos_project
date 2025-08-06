# src/workers/weather_worker.py

import logging
import requests
from PySide6.QtCore import QThread, Signal
from typing import Dict, Any

logger = logging.getLogger(__name__)

class WeatherWorker(QThread):
    """A worker thread to fetch weather data from an API without blocking the UI."""
    weather_updated = Signal(dict)
    error_occurred = Signal(str)

    def run(self):
        # Coordinates for Gwalior, Madhya Pradesh
        lat, lon = 26.2183, 78.1828
        location_name = "Gwalior"
        
        logger.info(f"Fetching weather for {location_name}...")
        try:
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            response = requests.get(weather_url, timeout=10)
            response.raise_for_status()
            data: Dict[str, Any] = response.json()
            
            current_weather = data.get("current_weather", {})
            temperature = current_weather.get("temperature", "N/A")
            weather_code = current_weather.get("weathercode", -1)
            is_day = current_weather.get("is_day", 1)

            weather_data = {
                "location": location_name,
                "temperature": temperature,
                "weather_code": weather_code,
                "is_day": is_day
            }
            self.weather_updated.emit(weather_data)
            logger.info("Weather data fetched successfully.")

        except requests.RequestException as e:
            logger.error(f"Network error during weather fetch: {e}", exc_info=True)
            self.error_occurred.emit("Network Error")
        except Exception as e:
            logger.error(f"An unexpected error occurred during weather fetch: {e}", exc_info=True)
            self.error_occurred.emit("Fetch Failed")