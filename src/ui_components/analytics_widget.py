# src/ui_components/analytics_widget.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel, 
    QPushButton, QGroupBox, QTextEdit, QHBoxLayout
)
from PySide6.QtCore import QThread, Signal
from src.database_manager import DatabaseManager
import subprocess
import sys
import logging
import pyqtgraph as pg

logger = logging.getLogger(__name__)

class TrainingWorker(QThread):
    """A worker thread to run the training script without blocking the UI."""
    new_output = Signal(str)
    finished = Signal(int)

    def run(self):
        """Executes the train_nlu.py script as a subprocess."""
        process = subprocess.Popen(
            [sys.executable, "train_nlu.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        
        if process.stdout:
            for line in iter(process.stdout.readline, ''):
                self.new_output.emit(line.strip())
        
        process.wait()
        self.finished.emit(process.returncode)


class AnalyticsWidget(QWidget):
    def __init__(self, db_manager: DatabaseManager, parent=None) -> None:
        super().__init__(parent)
        self.db_manager = db_manager
        self.training_thread = None
        # Set a dark theme for the plots to match our UI
        pg.setConfigOption('background', '#2c2c2c')
        pg.setConfigOption('foreground', 'w')
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        
        # --- Top Row: Stats and Training ---
        top_layout = QHBoxLayout()
        stats_group = QGroupBox("Usage Analytics")
        form_layout = QFormLayout(stats_group)
        self.total_commands_label = QLabel("N/A")
        self.accuracy_label = QLabel("N/A")
        self.most_used_label = QLabel("N/A")
        form_layout.addRow("Total Commands Logged:", self.total_commands_label)
        form_layout.addRow("NLU Accuracy:", self.accuracy_label)
        form_layout.addRow("Most Frequent Command:", self.most_used_label)
        refresh_btn = QPushButton("Refresh All Analytics")
        form_layout.addRow(refresh_btn)

        training_group = QGroupBox("NLU Model Training")
        training_layout = QVBoxLayout(training_group)
        self.train_button = QPushButton("Start NLU Fine-Tuning")
        info_label = QLabel("Improve the NLU model using your feedback from the dashboard.")
        info_label.setWordWrap(True)
        self.training_output = QTextEdit()
        self.training_output.setReadOnly(True)
        self.training_output.setPlaceholderText("Training output will appear here...")
        self.training_output.setFixedHeight(150)
        training_layout.addWidget(info_label)
        training_layout.addWidget(self.train_button)
        training_layout.addWidget(self.training_output)
        
        top_layout.addWidget(stats_group, 1)
        top_layout.addWidget(training_group, 2)
        main_layout.addLayout(top_layout)

        # --- Bottom Row: Charts ---
        charts_group = QGroupBox("Command Insights")
        charts_layout = QHBoxLayout(charts_group)

        # Intent Distribution Chart (Bar Chart)
        self.intent_plot = pg.PlotWidget(title="Top 10 Most Used Intents")
        self.intent_plot.showGrid(x=True, y=True, alpha=0.3)
        self.intent_plot.getAxis('left').setLabel('Count', color='#aaa')
        self.intent_plot.getAxis('bottom').setTicks([]) # Will be populated with text labels
        self.bar_chart = pg.BarGraphItem(x=[], height=[], width=0.6, brush=(74, 144, 226, 200)) # Primary color with some transparency
        self.intent_plot.addItem(self.bar_chart)
        
        # Usage Over Time Chart (Line Plot)
        self.time_plot = pg.PlotWidget(title="Command Usage Over Last 30 Days")
        self.time_plot.setAxisItems({'bottom': pg.DateAxisItem()})
        self.time_plot.showGrid(x=True, y=True, alpha=0.3)
        self.time_plot.getAxis('left').setLabel('Count', color='#aaa')
        
        charts_layout.addWidget(self.intent_plot)
        charts_layout.addWidget(self.time_plot)
        main_layout.addWidget(charts_group)

        # Set stretch factors for a balanced layout
        main_layout.setStretch(0, 1) # Top row gets 1 part of the space
        main_layout.setStretch(1, 2) # Bottom row (charts) gets 2 parts

        refresh_btn.clicked.connect(self.refresh_all_analytics)
        self.train_button.clicked.connect(self._start_training)
        
        self.refresh_all_analytics()

    def refresh_all_analytics(self) -> None:
        """Queries the database and updates all analytic components."""
        # Update top-level stats
        stats = self.db_manager.get_command_stats()
        self.total_commands_label.setText(str(stats["total"]))
        self.accuracy_label.setText(stats["accuracy"])
        self.most_used_label.setText(stats["most_used"])
        
        # Update charts with new data
        self._update_intent_distribution_chart()
        self._update_usage_over_time_chart()

    def _update_intent_distribution_chart(self):
        data = self.db_manager.get_intent_distribution(limit=10)
        if not data:
            self.bar_chart.setOpts(x=[], height=[])
            return

        intents, counts = zip(*data)
        # Clean up intent names for a nicer display on the chart
        clean_intents = [name.strip("[]").replace("_", " ").title() for name in intents]

        ticks = list(enumerate(clean_intents))
        self.intent_plot.getAxis('bottom').setTicks([ticks])
        self.bar_chart.setOpts(x=list(range(len(counts))), height=counts)

    def _update_usage_over_time_chart(self):
        data = self.db_manager.get_usage_over_time(days=30)
        self.time_plot.clear() # Clear previous plot data
        if not data:
            return

        timestamps, counts = zip(*data)
        # Plot with our secondary theme color and add symbols for data points
        pen = pg.mkPen(color='#50e3c2', width=2)
        self.time_plot.plot(timestamps, counts, pen=pen, symbol='o', symbolBrush='#50e3c2', symbolSize=6)

    def _start_training(self) -> None:
        self.train_button.setEnabled(False)
        self.training_output.clear()
        self.training_output.append("Starting training process...")
        
        self.training_thread = TrainingWorker()
        self.training_thread.new_output.connect(self.training_output.append)
        self.training_thread.finished.connect(self._on_training_finished)
        self.training_thread.start()

    def _on_training_finished(self, return_code: int) -> None:
        if return_code == 0:
            self.training_output.append("\n--- TRAINING SUCCESSFUL ---")
        else:
            self.training_output.append(f"\n--- TRAINING FAILED (code: {return_code}) ---")
            logger.error(f"Training script exited with code {return_code}")

        self.train_button.setEnabled(True)
        # Refresh stats to show any potential accuracy changes
        self.refresh_all_analytics()