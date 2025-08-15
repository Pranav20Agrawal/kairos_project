# src/ui_components/widgets/goal_memory_widget.py

from PySide6.QtWidgets import QWidget, QGroupBox, QVBoxLayout, QLabel
from PySide6.QtCore import Qt

class GoalMemoryWidget(QWidget):
    """A widget to display a list of relevant memories for a specific goal."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        group_box = QGroupBox("Relevant Memories from Nexus")
        self.group_layout = QVBoxLayout(group_box)
        main_layout.addWidget(group_box)

    def populate_memories(self, memories: list):
        # Clear previous memories
        while self.group_layout.count():
            item = self.group_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not memories:
            self.group_layout.addWidget(QLabel("No relevant memories found."))
            return

        for memory in memories:
            doc = memory.get('document', 'No content')
            # Create a simple label for each memory
            label = QLabel(f"• {doc}")
            label.setWordWrap(True)
            self.group_layout.addWidget(label)
        
        self.group_layout.addStretch()