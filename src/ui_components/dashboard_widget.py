# src/ui_components/dashboard_widget.py

import logging
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QFrame, QLabel, QVBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QMenu, QLineEdit
)
from PySide6.QtGui import QImage, QPixmap, QColor
from .correction_dialog import CorrectionDialog
from src.settings_manager import SettingsManager
from src.database_manager import DatabaseManager
import cv2
import numpy as np
from typing import Any, Dict

# Import the widget classes we want to make available on the dashboard
from .widgets.system_stats_widget import SystemStatsWidget
from .widgets.weather_widget import WeatherWidget

logger = logging.getLogger(__name__)

class DashboardWidget(QWidget):
    def __init__(self, settings_manager: SettingsManager, db_manager: DatabaseManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.db_manager = db_manager
        self.log_data_map: dict[int, Any] = {}
        
        # This "widget store" maps the key from the config to the actual widget class.
        # This makes it easy to add new widgets in the future.
        self.available_widgets = {
            "SYSTEM_STATS": SystemStatsWidget,
            "WEATHER": WeatherWidget,
        }
        
        self.loaded_widgets: Dict[str, QWidget] = {}
        
        # Main layout for the dashboard
        self.main_layout = QGridLayout(self)
        
        self._setup_ui()
        
        # Connect signal to reload dashboard if settings change
        self.settings_manager.settings_updated.connect(self._reload_ui)

    def _setup_ui(self) -> None:
        """Dynamically builds the dashboard UI based on the settings."""
        logger.info("Setting up dynamic dashboard UI...")
        dashboard_config = self.settings_manager.settings.dashboard.widgets
        
        # A special map for widgets that are part of the DashboardWidget itself
        # and not separate classes.
        self_widgets = {
            "VIDEO_FEED": self._create_video_feed,
            "COMMAND_LOG": self._create_command_log
        }
        
        for widget_key, config in dashboard_config.items():
            if not config.enabled:
                continue

            widget_instance = None
            if widget_key in self_widgets:
                widget_instance = self_widgets[widget_key]()
            elif widget_key in self.available_widgets:
                widget_class = self.available_widgets[widget_key]
                widget_instance = widget_class(self)
            
            if widget_instance:
                self.main_layout.addWidget(
                    widget_instance,
                    config.row,
                    config.col,
                    config.row_span,
                    config.col_span
                )
                self.loaded_widgets[widget_key] = widget_instance
                logger.debug(f"Loaded widget '{widget_key}' at ({config.row}, {config.col})")
            else:
                logger.warning(f"Widget key '{widget_key}' in config but no corresponding class found.")

    def _reload_ui(self):
        """Clears and rebuilds the entire dashboard UI. Called when settings change."""
        logger.info("Reloading dashboard UI due to settings change.")
        # Clear all widgets from the layout
        for widget in self.loaded_widgets.values():
            widget.setParent(None)
            del widget
        self.loaded_widgets.clear()
        # Re-run the setup process
        self._setup_ui()

    # --- Methods to create the built-in widgets ---

    def _create_video_feed(self) -> QWidget:
        self.video_label = QLabel("Initializing Camera...")
        self.video_label.setScaledContents(False)
        self.video_label.setStyleSheet("background-color: black; border-radius: 8px;")
        video_display_frame = QFrame()
        video_layout = QVBoxLayout(video_display_frame)
        video_layout.addWidget(self.video_label)
        return video_display_frame

    def _create_command_log(self) -> QWidget:
        log_panel_frame = QFrame()
        log_layout = QVBoxLayout(log_panel_frame)
        
        self.log_search_bar = QLineEdit()
        self.log_search_bar.setPlaceholderText("Search logs...")
        self.log_search_bar.textChanged.connect(self._filter_logs)
        log_layout.addWidget(self.log_search_bar)

        self.log_table = QTableWidget()
        self.log_table.setColumnCount(3)
        self.log_table.setHorizontalHeaderLabels(["Timestamp", "Source", "Content"])
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.log_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.log_table.setColumnWidth(2, 500)
        self.log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.log_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.log_table.customContextMenuRequested.connect(self._show_log_context_menu)
        log_layout.addWidget(self.log_table)
        return log_panel_frame

    # --- Existing methods for functionality ---

    def _filter_logs(self, text: str):
        search_term = text.lower()
        for row in range(self.log_table.rowCount()):
            row_is_visible = False
            if not search_term:
                row_is_visible = True
            else:
                for col in range(self.log_table.columnCount()):
                    item = self.log_table.item(row, col)
                    if item and search_term in item.text().lower():
                        row_is_visible = True
                        break
            self.log_table.setRowHidden(row, not row_is_visible)

    def log_event(self, timestamp: str, source: str, content: str, level: str, data: dict | None = None) -> None:
        if "COMMAND_LOG" not in self.loaded_widgets: return

        row_position = self.log_table.rowCount()
        self.log_table.insertRow(row_position)
        
        if data:
            self.log_data_map[row_position] = data

        color = QColor("#2c2c2c")
        if level == "WARNING": color = QColor(100, 80, 0)
        elif level == "ERROR" or level == "CRITICAL": color = QColor(100, 0, 0)
        elif source == "[BRAIN]": color = QColor(0, 40, 80)

        ts_item, source_item, content_item = QTableWidgetItem(timestamp), QTableWidgetItem(source), QTableWidgetItem(content)
        for item in [ts_item, source_item, content_item]:
            item.setBackground(color)
        
        self.log_table.setItem(row_position, 0, ts_item)
        self.log_table.setItem(row_position, 1, source_item)
        self.log_table.setItem(row_position, 2, content_item)
        self.log_table.scrollToBottom()

    def _show_log_context_menu(self, pos) -> None:
        row = self.log_table.rowAt(pos.y())
        if row < 0: return

        log_data = self.log_data_map.get(row)
        if not log_data or "predicted_intent" not in log_data: return

        menu = QMenu()
        correct_action = menu.addAction("Correct AI Prediction...")
        action = menu.exec(self.log_table.mapToGlobal(pos))

        if action == correct_action:
            self._show_correction_dialog(row)

    def _show_correction_dialog(self, row: int) -> None:
        log_entry = self.log_data_map.get(row)
        if not log_entry: return
        
        intents_dict = self.settings_manager.settings.intents
        macros_dict = self.settings_manager.settings.macros
        all_intents = sorted(list(intents_dict.keys()) + list(macros_dict.keys()))
        
        dialog = CorrectionDialog(
            original_text=log_entry["original_text"],
            prediction=(log_entry["predicted_intent"], log_entry["predicted_entity"]),
            all_intents=all_intents,
            parent=self
        )
        
        if dialog.exec():
            correction = dialog.get_correction()
            self.db_manager.update_correction(
                log_id=log_entry["log_id"],
                corrected_intent=correction["intent"],
                corrected_entity=correction["entity"]
            )
            for col in range(self.log_table.columnCount()):
                item = self.log_table.item(row, col)
                if item:
                    font = item.font()
                    font.setItalic(True)
                    item.setFont(font)
                    item.setForeground(QColor("gray"))

    def update_video_feed(self, frame: np.ndarray) -> None:
        if "VIDEO_FEED" not in self.loaded_widgets: return
        try:
            h, w, ch = frame.shape
            if h > 0 and w > 0:
                qt_image = self._convert_cv_to_qt(frame)
                self.video_label.setPixmap(qt_image.scaled(
                    self.video_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                ))
        except Exception:
            pass

    def _convert_cv_to_qt(self, cv_img: np.ndarray) -> QPixmap:
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(convert_to_Qt_format)