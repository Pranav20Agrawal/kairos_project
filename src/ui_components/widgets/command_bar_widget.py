# src/ui_components/widgets/command_bar_widget.py

from PySide6.QtCore import Qt, Signal, QPoint, QSize
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel, QApplication
from PySide6.QtGui import QMouseEvent, QFocusEvent

class CommandBarWidget(QWidget):
    """
    A small, frameless, draggable, and expandable widget for text commands.
    Distinguishes between a click-to-toggle and a drag-to-move action.
    """
    command_submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.is_expanded = False
        self._drag_pos = QPoint()
        
        # --- MODIFICATION START ---
        # Add new variables to track the drag state
        self._drag_start_position = QPoint()
        self._is_dragging = False
        # --- MODIFICATION END ---

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.container = QWidget(self)
        self.container_layout = QHBoxLayout(self.container)
        self.container_layout.setContentsMargins(10, 5, 10, 5)
        
        self.label = QLabel("K")
        self.input = QLineEdit()
        self.input.setPlaceholderText("Enter command...")
        
        self.container_layout.addWidget(self.label)
        self.container_layout.addWidget(self.input)
        self.layout.addWidget(self.container)

        self.input.returnPressed.connect(self._on_command_submit)
        
        self._update_widget_state()

    def _update_widget_state(self):
        """Updates the widget's appearance based on its expanded/compact state."""
        if self.is_expanded:
            self.input.setVisible(True)
            self.container.setMinimumWidth(300)
            self.setFixedSize(QSize(320, 40))
            self.input.setFocus()
            self.setStyleSheet("""
                QWidget#CommandBarWidget { background-color: transparent; }
                QWidget#container {
                    background-color: rgba(25, 25, 25, 0.95); color: #f0f0f0;
                    border: 1px solid #5A5A5A; border-radius: 8px;
                }
                QLineEdit { border: none; background-color: transparent; font-size: 11pt; color: #f0f0f0; }
                QLabel { font-weight: bold; color: #4A90E2; }
            """)
        else:
            self.input.setVisible(False)
            self.setFixedSize(QSize(40, 40))
            self.container.setMinimumWidth(0)
            self.setStyleSheet("""
                QWidget#CommandBarWidget { background-color: transparent; }
                QWidget#container {
                    background-color: rgba(25, 25, 25, 0.9); color: #f0f0f0;
                    border: 1px solid #4A90E2; border-radius: 20px;
                }
                QLabel { font-weight: bold; padding-left: 2px; color: #f0f0f0; }
            """)
        self.setObjectName("CommandBarWidget")
        self.container.setObjectName("container")

    def _on_command_submit(self):
        """Emit the command, clear input, and collapse."""
        command_text = self.input.text()
        if command_text:
            self.command_submitted.emit(command_text)
            self.input.clear()
        
        self.is_expanded = False
        self._update_widget_state()

    def focusOutEvent(self, event: QFocusEvent):
        """Collapse the widget when it loses focus."""
        super().focusOutEvent(event)
        self.is_expanded = False
        self._update_widget_state()
        
    # --- MODIFICATION: Updated Mouse Event Logic ---

    def mousePressEvent(self, event: QMouseEvent):
        """Records the starting position for a potential drag."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_position = event.pos()
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._is_dragging = False
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """If the mouse moves beyond a threshold, it's a drag. Move the widget."""
        if event.buttons() == Qt.MouseButton.LeftButton:
            # Check if the distance moved is greater than the system's default drag distance
            if not self._is_dragging and (event.pos() - self._drag_start_position).manhattanLength() > QApplication.startDragDistance():
                self._is_dragging = True

            if self._is_dragging:
                self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """If not dragging, it was a click. Toggle the widget's state."""
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._is_dragging:
                # This was a click, not a drag, so toggle the state
                self.is_expanded = not self.is_expanded
                self._update_widget_state()
            # Reset the dragging flag for the next press
            self._is_dragging = False
            event.accept()