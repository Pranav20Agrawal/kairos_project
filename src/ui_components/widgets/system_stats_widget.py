# src/ui_components/widgets/system_stats_widget.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QProgressBar, QLabel, QFormLayout
from PySide6.QtCore import Qt

class SystemStatsWidget(QWidget):
    """A widget to display live system stats like CPU and RAM usage."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0) # Use the parent's margins

        stats_group = QGroupBox("System Monitor")
        form_layout = QFormLayout(stats_group)
        form_layout.setSpacing(10)

        # CPU Progress Bar and Label
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setTextVisible(False)
        self.cpu_label = QLabel("0.0%")
        cpu_layout = QVBoxLayout()
        cpu_layout.addWidget(self.cpu_bar)
        cpu_layout.addWidget(self.cpu_label)
        form_layout.addRow("CPU:", cpu_layout)

        # RAM Progress Bar and Label
        self.ram_bar = QProgressBar()
        self.ram_bar.setTextVisible(False)
        self.ram_label = QLabel("0.0%")
        ram_layout = QVBoxLayout()
        ram_layout.addWidget(self.ram_bar)
        ram_layout.addWidget(self.ram_label)
        form_layout.addRow("RAM:", ram_layout)

        layout.addWidget(stats_group)
    
    def update_stats(self, cpu_percent: float, ram_percent: float):
        """Slot to receive new stats and update the UI elements."""
        # Update CPU
        self.cpu_bar.setValue(int(cpu_percent))
        self.cpu_label.setText(f"{cpu_percent:.1f}%")
        
        # Update RAM
        self.ram_bar.setValue(int(ram_percent))
        self.ram_label.setText(f"{ram_percent:.1f}%")

        # Dynamically color the progress bars based on usage
        self.cpu_bar.setStyleSheet(self._get_bar_stylesheet(cpu_percent))
        self.ram_bar.setStyleSheet(self._get_bar_stylesheet(ram_percent))

    def _get_bar_stylesheet(self, value: float) -> str:
        """Returns a stylesheet for the progress bar based on the value."""
        if value < 50:
            color = "#50e3c2" # Green/Teal (Secondary Accent)
        elif value < 80:
            color = "#f5a623" # Yellow
        else:
            color = "#d0021b" # Red
            
        return f"""
            QProgressBar {{
                border: 1px solid #606060;
                border-radius: 4px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
        """