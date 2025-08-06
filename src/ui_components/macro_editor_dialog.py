from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QDialogButtonBox,
    QListWidget,
    QComboBox,
    QHBoxLayout,
    QListWidgetItem,
)


class MacroEditorDialog(QDialog):
    """A dialog for creating and editing multi-step macros."""

    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Macro Editor")
        self.setMinimumWidth(400)

        # The safe, pre-defined "Lego Bricks" the user can choose from
        self.atomic_actions = ["OPEN_APP", "OPEN_URL", "PRESS_KEY", "TYPE_TEXT", "WAIT"]

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.macro_name = QLineEdit(data.get("name", "") if data else "")
        form_layout.addRow("Macro Voice Command:", self.macro_name)
        layout.addLayout(form_layout)

        self.step_list = QListWidget()
        if data:  # Populate existing steps if editing
            for step in data.get("steps", []):
                self.step_list.addItem(f"{step['action']}: {step['param']}")
        layout.addWidget(self.step_list)

        # --- UI for adding new steps ---
        add_step_layout = QHBoxLayout()
        self.action_combo = QComboBox()
        self.action_combo.addItems(self.atomic_actions)
        self.param_edit = QLineEdit()
        self.param_edit.setPlaceholderText(
            "Parameter (e.g., chrome.exe, 2, hello world)"
        )
        add_btn = QPushButton("Add Step")

        add_step_layout.addWidget(self.action_combo)
        add_step_layout.addWidget(self.param_edit)
        add_step_layout.addWidget(add_btn)
        layout.addLayout(add_step_layout)

        # --- Dialog Buttons ---
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(button_box)

        # --- Connections ---
        add_btn.clicked.connect(self._add_step)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def _add_step(self):
        action = self.action_combo.currentText()
        param = self.param_edit.text()
        if not param:
            return  # Don't add steps without parameters
        self.step_list.addItem(f"{action}: {param}")
        self.param_edit.clear()

    def get_data(self):
        """Returns the macro data from the dialog."""
        steps = []
        for i in range(self.step_list.count()):
            text = self.step_list.item(i).text()
            action, param = text.split(":", 1)
            steps.append({"action": action.strip(), "param": param.strip()})

        return {"name": self.macro_name.text().strip(), "steps": steps}
