# src/ui_components/dashboard_widget.py

import logging
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QFrame, QLabel, QVBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QMenu, QLineEdit, QGroupBox, QScrollArea
)
from PySide6.QtGui import QImage, QPixmap, QColor
from .correction_dialog import CorrectionDialog
from src.settings_manager import SettingsManager
from src.database_manager import DatabaseManager
import cv2
import numpy as np
from typing import Any, Dict

# Import the widget classes
from .widgets.system_stats_widget import SystemStatsWidget
from .widgets.weather_widget import WeatherWidget
from .widgets.notification_widget import NotificationWidget
from .widgets.goal_memory_widget import GoalMemoryWidget  # <-- ADD THIS IMPORT

logger = logging.getLogger(__name__)

class DashboardWidget(QWidget):
    def __init__(self, settings_manager: SettingsManager, db_manager: DatabaseManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.db_manager = db_manager
        self.log_data_map: dict[int, Any] = {}
        
        # This dictionary maps widget keys to their class constructors.
        # It's our palette of available tools for the generative UI.
        self.available_widgets = {
            "SYSTEM_STATS": SystemStatsWidget,
            "WEATHER": WeatherWidget,
            "VIDEO_FEED": self._create_video_feed,
            "COMMAND_LOG": self._create_command_log,
            "NOTIFICATIONS": self._create_notifications_panel,
            "GOAL_MEMORY": GoalMemoryWidget,  # <-- ADD THIS NEW WIDGET
        }
        
        self.loaded_widgets: Dict[str, QWidget] = {}
        self.main_layout = QGridLayout(self)
        
        # Load the default layout from settings on startup
        self.update_layout(self.settings_manager.settings.dashboard.widgets)
        
        self.settings_manager.settings_updated.connect(self._reload_ui)

    def clear_layout(self):
        """Removes all widgets from the dashboard layout."""
        for widget in self.loaded_widgets.values():
            self.main_layout.removeWidget(widget)
            widget.deleteLater()
        self.loaded_widgets.clear()

    @Slot(dict)
    def update_layout(self, layout_config: Dict[str, Any]):
        """Clears the current dashboard and rebuilds it based on a new layout config."""
        logger.info("Updating dashboard layout...")
        self.clear_layout()
        
        for widget_key, config_data in layout_config.items():
            # In Pydantic v2, we need to handle the data correctly
            config = config_data if isinstance(config_data, dict) else config_data.model_dump()
            if not config.get("enabled", False):
                continue

            widget_constructor = self.available_widgets.get(widget_key)
            if not widget_constructor:
                logger.warning(f"Widget key '{widget_key}' in layout but no corresponding class found.")
                continue

            # Handle different widget constructor types
            if callable(widget_constructor):
                if widget_key in ["SYSTEM_STATS", "WEATHER", "GOAL_MEMORY"]:
                    # These are class constructors that need a parent
                    widget_instance = widget_constructor(self)
                else:
                    # These are method references that return widgets
                    widget_instance = widget_constructor()
            else:
                logger.error(f"Widget constructor for '{widget_key}' is not callable.")
                continue
            
            self.main_layout.addWidget(
                widget_instance,
                config["row"], config["col"],
                config["row_span"], config["col_span"]
            )
            self.loaded_widgets[widget_key] = widget_instance
            logger.debug(f"Loaded widget '{widget_key}' at ({config['row']}, {config['col']})")

    def _reload_ui(self):
        """Legacy method to maintain compatibility with existing settings update connections."""
        logger.info("Reloading dashboard UI due to settings change.")
        self.update_layout(self.settings_manager.settings.dashboard.widgets)

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

    def _create_notifications_panel(self) -> QWidget:
        notifications_group = QGroupBox("Phone Notifications")
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        self.notifications_layout = QVBoxLayout(container)
        self.notifications_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.notifications_layout.setSpacing(10)
        
        scroll_area.setWidget(container)
        
        group_layout = QVBoxLayout(notifications_group)
        group_layout.addWidget(scroll_area)
        
        return notifications_group

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

    @Slot(dict)
    def add_notification(self, data: dict):
        if "NOTIFICATIONS" not in self.loaded_widgets:
            return

        title = data.get("title", "N/A")
        content = data.get("content", "")
        package = data.get("package_name", "")

        notification_card = NotificationWidget(title, content, package)
        self.notifications_layout.insertWidget(0, notification_card)

        while self.notifications_layout.count() > 10:
            item = self.notifications_layout.takeAt(self.notifications_layout.count() - 1)
            if item and item.widget():
                item.widget().deleteLater()