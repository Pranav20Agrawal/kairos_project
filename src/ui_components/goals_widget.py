# src/ui_components/goals_widget.py

import logging
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QPushButton,
    QMessageBox, QGroupBox, QFormLayout, QLabel
)
from PySide6.QtCore import Qt
from src.settings_manager import SettingsManager
from src.models import Goal
from .goal_dialog import GoalDialog

logger = logging.getLogger(__name__)

class GoalsWidget(QWidget):
    def __init__(self, settings_manager: SettingsManager, parent=None) -> None:
        super().__init__(parent)
        self.settings_manager = settings_manager
        self._setup_ui()
        self._connect_signals()
        self._populate_goals_list()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        
        # Left side: List of goals
        list_group = QGroupBox("Active Goals")
        list_layout = QVBoxLayout(list_group)
        self.goals_list = QListWidget()
        list_layout.addWidget(self.goals_list)

        # Left side: Management buttons
        button_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Goal...")
        self.edit_btn = QPushButton("Edit Goal...")
        self.complete_btn = QPushButton("Mark as Complete")
        button_layout.addWidget(self.add_btn)
        button_layout.addWidget(self.edit_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.complete_btn)
        list_layout.addLayout(button_layout)

        # Right side: Details of selected goal
        details_group = QGroupBox("Goal Details")
        details_layout = QFormLayout(details_group)
        self.name_label = QLabel("N/A")
        self.deadline_label = QLabel("N/A")
        self.keywords_label = QLabel("N/A")
        self.status_label = QLabel("N/A")
        
        details_layout.addRow("<b>Name:</b>", self.name_label)
        details_layout.addRow("<b>Deadline:</b>", self.deadline_label)
        details_layout.addRow("<b>Keywords:</b>", self.keywords_label)
        details_layout.addRow("<b>Status:</b>", self.status_label)
        details_group.setFixedWidth(400) # Fix width for details panel

        main_layout.addWidget(list_group, 2) # List takes 2/3 of space
        main_layout.addWidget(details_group, 1) # Details take 1/3 of space

    def _connect_signals(self):
        self.settings_manager.settings_updated.connect(self._populate_goals_list)
        self.goals_list.currentItemChanged.connect(self._update_details_panel)
        self.add_btn.clicked.connect(self._add_goal)
        self.edit_btn.clicked.connect(self._edit_goal)
        self.complete_btn.clicked.connect(self._complete_goal)

    def _populate_goals_list(self):
        self.goals_list.clear()
        for goal_name, goal_data in self.settings_manager.settings.goals.items():
            if goal_data.status == "Active":
                self.goals_list.addItem(goal_name)
        self._update_details_panel()

    def _update_details_panel(self):
        item = self.goals_list.currentItem()
        if not item:
            self.name_label.setText("N/A")
            self.deadline_label.setText("N/A")
            self.keywords_label.setText("N/A")
            self.status_label.setText("N/A")
            return
            
        goal_name = item.text()
        goal = self.settings_manager.settings.goals.get(goal_name)
        if goal:
            self.name_label.setText(goal.name)
            self.deadline_label.setText(goal.deadline or "Not set")
            self.keywords_label.setText(", ".join(goal.keywords) or "None")
            self.keywords_label.setWordWrap(True)
            self.status_label.setText(f"<b style='color: #50e3c2;'>{goal.status}</b>")

    def _add_goal(self):
        dialog = GoalDialog(parent=self)
        if dialog.exec():
            data = dialog.get_data()
            if not data["name"]:
                QMessageBox.warning(self, "Input Error", "Goal name cannot be empty.")
                return
            
            new_goal = Goal(**data)
            self.settings_manager.settings.goals[data["name"]] = new_goal
            self.settings_manager.save_settings()
            logger.info(f"New goal '{data['name']}' added.")

    def _edit_goal(self):
        # ... (Editing logic would be similar to _add_goal, pre-filling the dialog)
        logger.warning("Edit goal functionality is not yet fully implemented.")

    def _complete_goal(self):
        item = self.goals_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Selection Error", "Please select a goal to mark as complete.")
            return

        goal_name = item.text()
        reply = QMessageBox.question(self, "Confirm Completion", f"Are you sure you want to mark '{goal_name}' as complete?")
        if reply == QMessageBox.StandardButton.Yes:
            self.settings_manager.settings.goals[goal_name].status = "Completed"
            self.settings_manager.save_settings()
            logger.info(f"Goal '{goal_name}' marked as complete.")