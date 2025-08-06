# src/ui_components/settings_widget.py

from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QFormLayout, QSlider, QDoubleSpinBox,
    QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QPushButton, QHBoxLayout, QMessageBox, QListWidget,
    QTimeEdit, QComboBox, QColorDialog, QCheckBox
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt, QTime
from src.settings_manager import SettingsManager
from src.models import Intent, MacroStep, WidgetConfig
from .command_dialog import CommandDialog
from .macro_editor_dialog import MacroEditorDialog
import cv2
import logging
from functools import partial

logger = logging.getLogger(__name__)


class SettingsWidget(QWidget):
    def __init__(self, settings_manager: SettingsManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings_manager = settings_manager
        
        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.core_tab = QWidget()
        self.dashboard_tab = QWidget() # <--- NEW
        self.theme_tab = QWidget()
        self.commands_tab = QWidget()
        self.macros_tab = QWidget()
        
        self.tabs.addTab(self.core_tab, "Core")
        self.tabs.addTab(self.dashboard_tab, "Dashboard") # <--- NEW
        self.tabs.addTab(self.theme_tab, "Appearance")
        self.tabs.addTab(self.commands_tab, "Commands")
        self.tabs.addTab(self.macros_tab, "Macros")

        self._setup_core_tab()
        self._setup_dashboard_tab() # <--- NEW
        self._setup_theme_tab()
        self._setup_commands_tab()
        self._setup_macros_tab()
        
        self.settings_manager.settings_updated.connect(self._on_settings_reloaded)

    def _on_settings_reloaded(self) -> None:
        """Slot to handle reloading data when settings are changed elsewhere."""
        self._populate_commands_table()
        self._populate_macros_list()
        self._update_color_previews()
        self.paranoid_mode_checkbox.setChecked(self.settings_manager.settings.core.paranoid_mode_enabled)
        self._populate_dashboard_widgets() # <--- NEW

    def _setup_core_tab(self) -> None:
        layout = QVBoxLayout(self.core_tab)
        settings = self.settings_manager.settings

        hardware_group = QGroupBox("Hardware")
        hardware_layout = QFormLayout(hardware_group)
        self.camera_combo = QComboBox()
        hardware_layout.addRow("Active Camera:", self.camera_combo)
        
        gesture_group = QGroupBox("Gesture Detection")
        gesture_layout = QFormLayout(gesture_group)
        self.fist_slider = QSlider(Qt.Orientation.Horizontal)
        self.fist_slider.setRange(1, 20)
        fist_val = int(settings.core.fist_threshold * 100)
        self.fist_slider.setValue(fist_val)
        self.fist_label = QLabel(f"{settings.core.fist_threshold:.2f}")
        gesture_layout.addRow("Fist Sensitivity:", self.fist_slider)
        gesture_layout.addRow("Current Value:", self.fist_label)
        
        audio_group = QGroupBox("Voice Activity Detection (VAD)")
        audio_layout = QFormLayout(audio_group)
        self.silence_duration_box = QDoubleSpinBox()
        self.silence_duration_box.setRange(0.5, 5.0)
        self.silence_duration_box.setSingleStep(0.1)
        self.silence_duration_box.setValue(settings.core.silence_duration)
        audio_layout.addRow("Silence Duration (s):", self.silence_duration_box)

        briefing_group = QGroupBox("Proactive Agent")
        briefing_layout = QFormLayout(briefing_group)
        self.briefing_time_edit = QTimeEdit()
        briefing_time_str = settings.core.daily_briefing_time
        self.briefing_time_edit.setTime(QTime.fromString(briefing_time_str, "HH:mm"))
        briefing_layout.addRow("Daily Briefing Time:", self.briefing_time_edit)

        security_group = QGroupBox("Fortress Protocol")
        security_layout = QVBoxLayout(security_group)
        self.paranoid_mode_checkbox = QCheckBox("Enable Paranoid Mode")
        self.paranoid_mode_checkbox.setChecked(settings.core.paranoid_mode_enabled)
        info_label = QLabel("When enabled, all high-risk commands (file access, web automation, code execution) will be disabled.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("font-size: 9pt; color: #aaa;")
        security_layout.addWidget(self.paranoid_mode_checkbox)
        security_layout.addWidget(info_label)

        layout.addWidget(hardware_group)
        layout.addWidget(gesture_group)
        layout.addWidget(audio_group)
        layout.addWidget(briefing_group)
        layout.addWidget(security_group)
        layout.addStretch()

        self._discover_cameras_and_populate()

        self.camera_combo.currentIndexChanged.connect(self._on_camera_selected)
        self.fist_slider.valueChanged.connect(self._on_fist_slider_change)
        self.silence_duration_box.valueChanged.connect(self._on_silence_duration_change)
        self.briefing_time_edit.timeChanged.connect(self._on_briefing_time_change)
        self.paranoid_mode_checkbox.stateChanged.connect(self._on_paranoid_mode_changed)

    # <--- NEW: All methods for the dashboard settings tab --->
    def _setup_dashboard_tab(self) -> None:
        """Sets up the UI for enabling/disabling dashboard widgets."""
        layout = QVBoxLayout(self.dashboard_tab)
        
        widgets_group = QGroupBox("Dashboard Widgets")
        self.widgets_layout = QVBoxLayout(widgets_group)
        
        info_label = QLabel("Select which widgets to display on the dashboard. A restart is required for changes to take effect.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("font-size: 9pt; color: #aaa; margin-bottom: 10px;")
        
        self.widgets_layout.addWidget(info_label)
        
        layout.addWidget(widgets_group)
        layout.addStretch()
        
        self.dashboard_checkboxes = {}
        self._populate_dashboard_widgets()

    def _populate_dashboard_widgets(self) -> None:
        """Clears and repopulates the list of dashboard widget checkboxes."""
        # Clear existing checkboxes before repopulating
        for widget_key, checkbox in self.dashboard_checkboxes.items():
            checkbox.setParent(None)
            del checkbox
        self.dashboard_checkboxes.clear()

        dashboard_settings = self.settings_manager.settings.dashboard
        for widget_key, widget_config in dashboard_settings.widgets.items():
            checkbox = QCheckBox(widget_config.name)
            checkbox.setChecked(widget_config.enabled)
            # Use a partial to pass the widget_key to the handler
            checkbox.stateChanged.connect(partial(self._on_widget_toggled, widget_key))
            self.widgets_layout.addWidget(checkbox)
            self.dashboard_checkboxes[widget_key] = checkbox

    def _on_widget_toggled(self, widget_key: str, state: int) -> None:
        """Handles a widget checkbox being toggled."""
        is_enabled = state == Qt.CheckState.Checked.value
        if widget_key in self.settings_manager.settings.dashboard.widgets:
            self.settings_manager.settings.dashboard.widgets[widget_key].enabled = is_enabled
            self.settings_manager.save_settings()
            logger.info(f"Dashboard widget '{widget_key}' set to enabled={is_enabled}.")
    # <--- END of new dashboard settings methods --->

    def _on_paranoid_mode_changed(self, state: int) -> None:
        is_enabled = state == Qt.CheckState.Checked.value
        self.settings_manager.settings.core.paranoid_mode_enabled = is_enabled
        self.settings_manager.save_settings()
        logger.info(f"Paranoid Mode {'enabled' if is_enabled else 'disabled'}.")

    def _setup_theme_tab(self) -> None:
        layout = QVBoxLayout(self.theme_tab)
        theme_group = QGroupBox("Color Customization")
        form_layout = QFormLayout(theme_group)

        primary_layout = QHBoxLayout()
        self.primary_color_preview = QLabel()
        self.primary_color_preview.setFixedSize(24, 24)
        primary_btn = QPushButton("Choose Primary Color...")
        primary_layout.addWidget(self.primary_color_preview)
        primary_layout.addWidget(primary_btn)
        form_layout.addRow("Primary Accent:", primary_layout)

        secondary_layout = QHBoxLayout()
        self.secondary_color_preview = QLabel()
        self.secondary_color_preview.setFixedSize(24, 24)
        secondary_btn = QPushButton("Choose Secondary Color...")
        secondary_layout.addWidget(self.secondary_color_preview)
        secondary_layout.addWidget(secondary_btn)
        form_layout.addRow("Secondary Accent:", secondary_layout)

        layout.addWidget(theme_group)
        layout.addStretch()

        self._update_color_previews()

        primary_btn.clicked.connect(self._choose_primary_color)
        secondary_btn.clicked.connect(self._choose_secondary_color)

    def _update_color_previews(self) -> None:
        theme = self.settings_manager.settings.theme
        self.primary_color_preview.setStyleSheet(f"background-color: {theme.primary_color}; border-radius: 4px;")
        self.secondary_color_preview.setStyleSheet(f"background-color: {theme.secondary_color}; border-radius: 4px;")

    def _choose_primary_color(self) -> None:
        self._choose_color("primary")

    def _choose_secondary_color(self) -> None:
        self._choose_color("secondary")

    def _choose_color(self, color_type: str) -> None:
        theme = self.settings_manager.settings.theme
        initial_color_str = theme.primary_color if color_type == "primary" else theme.secondary_color
        initial_color = QColor(initial_color_str)
        color = QColorDialog.getColor(initial_color, self, f"Select a New {color_type.capitalize()} Color")
        if color.isValid():
            hex_color = color.name()
            if color_type == "primary":
                self.settings_manager.settings.theme.primary_color = hex_color
            else:
                self.settings_manager.settings.theme.secondary_color = hex_color
            self.settings_manager.save_settings()
    
    def _discover_cameras_and_populate(self) -> None:
        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()
        logger.info("Discovering available cameras...")
        index = 0
        while True:
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                break
            self.camera_combo.addItem(f"Camera {index}")
            cap.release()
            index += 1
        logger.info(f"Found {index} cameras.")
        saved_index = self.settings_manager.settings.core.camera_index
        if saved_index < self.camera_combo.count():
            self.camera_combo.setCurrentIndex(saved_index)
        self.camera_combo.blockSignals(False)

    def _on_camera_selected(self, index: int) -> None:
        logger.info(f"Camera selection changed to index {index}.")
        self.settings_manager.settings.core.camera_index = index
        self.settings_manager.save_settings()
        QMessageBox.information(self, "Restart Required", "Please restart K.A.I.R.O.S. for the camera change to take effect.")

    def _on_fist_slider_change(self, value: int) -> None:
        float_value = value / 100.0
        self.settings_manager.settings.core.fist_threshold = float_value
        self.fist_label.setText(f"{float_value:.2f}")
        self.settings_manager.save_settings()

    def _on_silence_duration_change(self, value: float) -> None:
        self.settings_manager.settings.core.silence_duration = value
        self.settings_manager.save_settings()

    def _on_briefing_time_change(self, time: QTime) -> None:
        self.settings_manager.settings.core.daily_briefing_time = time.toString("HH:mm")
        self.settings_manager.save_settings()

    def _setup_commands_tab(self) -> None:
        layout = QVBoxLayout(self.commands_tab)
        self.commands_table = QTableWidget()
        self.commands_table.setColumnCount(4)
        self.commands_table.setHorizontalHeaderLabels(["Intent", "Keywords", "Triggers", "Canonical"])
        self.commands_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.commands_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.commands_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        button_layout = QHBoxLayout()
        add_btn = QPushButton("Add...")
        edit_btn = QPushButton("Edit...")
        delete_btn = QPushButton("Delete")
        button_layout.addStretch()
        button_layout.addWidget(add_btn)
        button_layout.addWidget(edit_btn)
        button_layout.addWidget(delete_btn)

        layout.addWidget(self.commands_table)
        layout.addLayout(button_layout)

        add_btn.clicked.connect(self._add_command)
        edit_btn.clicked.connect(self._edit_command)
        delete_btn.clicked.connect(self._delete_command)
        
        self._populate_commands_table()

    def _setup_macros_tab(self) -> None:
        layout = QVBoxLayout(self.macros_tab)
        self.macros_list = QListWidget()

        button_layout = QHBoxLayout()
        add_btn = QPushButton("Add...")
        edit_btn = QPushButton("Edit...")
        delete_btn = QPushButton("Delete")
        button_layout.addStretch()
        button_layout.addWidget(add_btn)
        button_layout.addWidget(edit_btn)
        button_layout.addWidget(delete_btn)

        layout.addWidget(self.macros_list)
        layout.addLayout(button_layout)

        add_btn.clicked.connect(self._add_macro)
        edit_btn.clicked.connect(self._edit_macro)
        delete_btn.clicked.connect(self._delete_macro)

        self._populate_macros_list()

    def _populate_commands_table(self) -> None:
        self.commands_table.blockSignals(True)
        self.commands_table.setRowCount(0)
        intents = self.settings_manager.settings.intents
        for name, data in intents.items():
            row = self.commands_table.rowCount()
            self.commands_table.insertRow(row)
            self.commands_table.setItem(row, 0, QTableWidgetItem(name))
            self.commands_table.setItem(row, 1, QTableWidgetItem(", ".join(data.keywords)))
            self.commands_table.setItem(row, 2, QTableWidgetItem(", ".join(data.triggers)))
            self.commands_table.setItem(row, 3, QTableWidgetItem(data.canonical))
        self.commands_table.blockSignals(False)

    def _add_command(self) -> None:
        dialog = CommandDialog(parent=self)
        if dialog.exec():
            data = dialog.get_data()
            if data["name"]:
                new_intent = Intent(
                    keywords=data["keywords"],
                    triggers=data["triggers"],
                    canonical=data["canonical"]
                )
                self.settings_manager.settings.intents[data["name"]] = new_intent
                self.settings_manager.save_settings()

    def _edit_command(self) -> None:
        selected_row = self.commands_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Warning", "Please select a command to edit.")
            return

        intent_name = self.commands_table.item(selected_row, 0).text()
        intent_model = self.settings_manager.settings.intents.get(intent_name)
        if not intent_model:
            return

        intent_data = intent_model.model_dump()
        intent_data["name"] = intent_name

        dialog = CommandDialog(data=intent_data, parent=self)
        if dialog.exec():
            new_data = dialog.get_data()
            if intent_name != new_data["name"]:
                del self.settings_manager.settings.intents[intent_name]
            
            updated_intent = Intent(
                keywords=new_data["keywords"],
                triggers=new_data["triggers"],
                canonical=new_data["canonical"]
            )
            self.settings_manager.settings.intents[new_data["name"]] = updated_intent
            self.settings_manager.save_settings()

    def _delete_command(self) -> None:
        selected_row = self.commands_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Warning", "Please select a command to delete.")
            return
            
        intent_name = self.commands_table.item(selected_row, 0).text()
        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete the '{intent_name}' command?")
        
        if reply == QMessageBox.StandardButton.Yes:
            if intent_name in self.settings_manager.settings.intents:
                del self.settings_manager.settings.intents[intent_name]
                self.settings_manager.save_settings()

    def _populate_macros_list(self) -> None:
        self.macros_list.clear()
        macros = self.settings_manager.settings.macros
        for name in macros.keys():
            self.macros_list.addItem(name)

    def _add_macro(self) -> None:
        dialog = MacroEditorDialog(parent=self)
        if dialog.exec():
            data = dialog.get_data()
            if data["name"]:
                macros = self.settings_manager.settings.macros
                macros[data["name"]] = [MacroStep(**step) for step in data["steps"]]
                
                intents = self.settings_manager.settings.intents
                intents[data["name"]] = Intent(keywords=[data["name"].lower().replace("_", " ")])
                
                self.settings_manager.save_settings()

    def _edit_macro(self) -> None:
        selected_item = self.macros_list.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "Warning", "Please select a macro to edit.")
            return
        
        macro_name = selected_item.text()
        macros = self.settings_manager.settings.macros
        intents = self.settings_manager.settings.intents
        
        macro_steps_models = macros.get(macro_name, [])
        macro_steps_dicts = [step.model_dump() for step in macro_steps_models]
        macro_data = {"name": macro_name, "steps": macro_steps_dicts}

        dialog = MacroEditorDialog(data=macro_data, parent=self)
        if dialog.exec():
            new_data = dialog.get_data()
            if macro_name != new_data["name"]:
                del macros[macro_name]
                if macro_name in intents:
                    del intents[macro_name]
            
            macros[new_data["name"]] = [MacroStep(**step) for step in new_data["steps"]]
            intents[new_data["name"]] = Intent(keywords=[new_data["name"].lower().replace("_", " ")])
            
            self.settings_manager.save_settings()

    def _delete_macro(self) -> None:
        selected_item = self.macros_list.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "Warning", "Please select a macro to delete.")
            return
            
        macro_name = selected_item.text()
        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete the '{macro_name}' macro?")
        
        if reply == QMessageBox.StandardButton.Yes:
            macros = self.settings_manager.settings.macros
            if macro_name in macros:
                del macros[macro_name]
            
            intents = self.settings_manager.settings.intents
            if macro_name in intents:
                del intents[macro_name]

            self.settings_manager.save_settings()