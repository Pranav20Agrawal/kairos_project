# src/ui_components/widgets/notification_widget.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout
from PySide6.QtCore import Qt

class NotificationWidget(QFrame):
    """A custom widget to display a single notification."""
    def __init__(self, title: str, content: str, package_name: str, parent=None):
        super().__init__(parent)
        self.setObjectName("notificationCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(5)

        # Title (e.g., "WhatsApp")
        title_label = QLabel(f"<b>{title}</b>")
        title_label.setStyleSheet("font-size: 11pt;")

        # Content (e.g., "John: Hey, are you free?")
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("color: #bbb;")
        
        # Package Name (e.g., "com.whatsapp")
        package_label = QLabel(f"<i>from {package_name}</i>")
        package_label.setStyleSheet("font-size: 8pt; color: #888;")
        package_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        main_layout.addWidget(title_label)
        main_layout.addWidget(content_label)
        main_layout.addWidget(package_label)

        # Simple styling for the card
        self.setStyleSheet("""
            #notificationCard {
                background-color: #3a3a3a;
                border-radius: 8px;
                padding: 10px;
            }
        """)