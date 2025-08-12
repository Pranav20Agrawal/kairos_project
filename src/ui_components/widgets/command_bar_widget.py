# src/ui_components/widgets/command_bar_widget.py

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel
from PySide6.QtGui import QMouseEvent

class CommandBarWidget(QWidget):
    """
    A small, frameless, always-on-top widget for text commands.
    It's designed to be unobtrusive and context-aware.
    """
    command_submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- Key flags to make it a floating widget ---
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | # No title bar or borders
            Qt.WindowType.WindowStaysOnTopHint | # Always on top of other windows
            Qt.WindowType.Tool                 # Behaves as a tool window (may not show in taskbar)
        )
        # Make the background transparent
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # --- UI Setup ---
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 5, 10, 5)

        self.label = QLabel("K:")
        self.input = QLineEdit()
        self.input.setPlaceholderText("Enter command...")
        
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.input)

        # Connect the returnPressed signal
        self.input.returnPressed.connect(self._on_command_submit)

        # --- Styling ---
        self.setStyleSheet("""
            CommandBarWidget {
                background-color: rgba(30, 30, 30, 0.9);
                color: #f0f0f0;
                border: 1px solid #505050;
                border-radius: 8px;
            }
            QLineEdit {
                border: none;
                background-color: transparent;
                font-size: 11pt;
            }
            QLabel {
                font-weight: bold;
            }
        """)

        # --- Variables for moving the frameless window ---
        self._drag_pos = QPoint()

    def _on_command_submit(self):
        """Emit the command and clear the input field."""
        command_text = self.input.text()
        if command_text:
            self.command_submitted.emit(command_text)
            self.input.clear()

    # --- Methods to make the frameless window draggable ---
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()