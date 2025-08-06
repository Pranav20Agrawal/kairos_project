from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
)


class CommandDialog(QDialog):
    """A dialog for adding or editing a voice command."""

    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Command Editor")

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # If we are editing existing data, pre-fill the fields
        initial_data = data or {}

        self.intent_name = QLineEdit(initial_data.get("name", ""))
        self.keywords = QLineEdit(", ".join(initial_data.get("keywords", [])))
        self.triggers = QLineEdit(", ".join(initial_data.get("triggers", [])))
        self.canonical = QLineEdit(initial_data.get("canonical", ""))

        form_layout.addRow("Intent Name:", self.intent_name)
        form_layout.addRow("Keywords (comma-separated):", self.keywords)
        form_layout.addRow("Triggers (comma-separated):", self.triggers)
        form_layout.addRow("Canonical Phrase:", self.canonical)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_data(self):
        """Returns the data entered in the dialog in a structured format."""
        return {
            "name": self.intent_name.text().strip(),
            "keywords": [
                k.strip() for k in self.keywords.text().split(",") if k.strip()
            ],
            "triggers": [
                t.strip() for t in self.triggers.text().split(",") if t.strip()
            ],
            "canonical": self.canonical.text().strip(),
        }
