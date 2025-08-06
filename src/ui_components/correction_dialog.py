from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
    QComboBox,
    QLabel,
)


class CorrectionDialog(QDialog):
    """A dialog for correcting an NLU prediction."""

    def __init__(self, original_text, prediction, all_intents, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Correct AI Mistake")

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.original_text_label = QLabel(f"<b>Original Text:</b><br>'{original_text}'")
        self.predicted_intent_label = QLabel(
            f"<b>AI Prediction:</b><br>Intent: {prediction[0]} | Entity: '{prediction[1]}'"
        )

        self.corrected_intent_combo = QComboBox()
        self.corrected_intent_combo.addItems(all_intents)
        # Set the current prediction as the default
        if prediction[0] in all_intents:
            self.corrected_intent_combo.setCurrentText(prediction[0])

        self.corrected_entity_edit = QLineEdit(prediction[1] if prediction[1] else "")

        form_layout.addRow(self.original_text_label)
        form_layout.addRow(self.predicted_intent_label)
        form_layout.addRow("Correct Intent:", self.corrected_intent_combo)
        form_layout.addRow("Correct Entity:", self.corrected_entity_edit)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_correction(self):
        """Returns the corrected data from the dialog."""
        return {
            "intent": self.corrected_intent_combo.currentText(),
            "entity": self.corrected_entity_edit.text().strip(),
        }
