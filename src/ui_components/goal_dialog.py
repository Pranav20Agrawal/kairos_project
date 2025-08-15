# src/ui_components/goal_dialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QDialogButtonBox, QDateEdit
)
from PySide6.QtCore import QDate, Qt

class GoalDialog(QDialog):
    """A dialog for adding or editing a goal."""

    def __init__(self, data: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Goal Editor")
        self.setMinimumWidth(400)

        initial_data = data or {}
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.goal_name = QLineEdit(initial_data.get("name", ""))
        self.deadline = QDateEdit(QDate.currentDate())
        self.deadline.setCalendarPopup(True)
        if initial_data.get("deadline"):
            self.deadline.setDate(QDate.fromString(initial_data["deadline"], "yyyy-MM-dd"))
        
        self.keywords = QLineEdit(", ".join(initial_data.get("keywords", [])))
        
        form_layout.addRow("Goal Name:", self.goal_name)
        form_layout.addRow("Deadline (Optional):", self.deadline)
        form_layout.addRow("Keywords (comma-separated):", self.keywords)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_data(self) -> dict:
        """Returns the data entered in the dialog in a structured format."""
        return {
            "name": self.goal_name.text().strip(),
            "deadline": self.deadline.date().toString("yyyy-MM-dd"),
            "keywords": [k.strip().lower() for k in self.keywords.text().split(",") if k.strip()],
        }