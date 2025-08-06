# src/main_window.py

from PySide6.QtCore import Signal, QDateTime, QTime, Qt, QUrl
from PySide6.QtGui import QCloseEvent, QIcon, QAction, QDesktopServices
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget,
    QFrame, QMessageBox, QStatusBar, QSystemTrayIcon, QMenu, QApplication
)
from PySide6.QtMultimedia import QSoundEffect
from pathlib import Path
import threading
from typing import Any, Dict, List

from src.video_worker import VideoWorker
from src.audio_worker import AudioWorker
from src.speaker_worker import SpeakerWorker
from src.workers.system_stats_worker import SystemStatsWorker
from src.workers.update_checker_worker import UpdateCheckerWorker
from src.workers.ocr_worker import OcrWorker
from src.workers.activity_logger_worker import ActivityLoggerWorker
from src.nlu_engine import NluEngine
from src.action_manager import ActionManager
from src.ui_components.dashboard_widget import DashboardWidget
from src.ui_components.settings_widget import SettingsWidget
from src.settings_manager import SettingsManager
from src.database_manager import DatabaseManager
from src.scheduler import Scheduler
from src.ui_components.analytics_widget import AnalyticsWidget
from src.context_manager import ContextManager
from src.api_server import ServerWorker
import logging

logger = logging.getLogger(__name__)


class KairosMainWindow(QMainWindow):
    new_log_entry = Signal(str, str, str, str, dict)

    def __init__(self, app_version: str) -> None:
        super().__init__()
        self.app_version = app_version
        logger.info(f"K.A.I.R.O.S. version {self.app_version} initializing...")
        self.setWindowTitle(f"K.A.I.R.O.S. - Command Center v{self.app_version}")
        self.setGeometry(100, 100, 1200, 800)

        self.interrupt_event = threading.Event()
        self.pending_suggestion: List[str] | None = None
        self.targeted_window: Any | None = None

        logger.info("Initializing backend components...")
        self.settings_manager = SettingsManager()
        self.db_manager = DatabaseManager()
        self.nlu_engine = NluEngine(self.settings_manager)
        
        self.speaker_worker = SpeakerWorker()
        self.action_manager = ActionManager(self.settings_manager, self.interrupt_event, self.speaker_worker)
        
        self.scheduler = Scheduler()
        self.context_manager = ContextManager()

        self._apply_theme()
        self._setup_ui_shell()
        self._init_sound_effects()
        self._setup_tray_icon()
        self.connect_signals()
        self._schedule_jobs()
        self._start_workers()
        logger.info("K.A.I.R.O.S. Main Window initialized successfully.")

    def _apply_theme(self) -> None:
        try:
            with open("assets/style.qss.template", "r") as f:
                template = f.read()
            theme = self.settings_manager.settings.theme
            stylesheet = template.replace("{{PRIMARY_COLOR}}", theme.primary_color).replace("{{SECONDARY_COLOR}}", theme.secondary_color)
            self.setStyleSheet(stylesheet)
            logger.info("UI theme applied successfully.")
        except Exception as e:
            logger.error(f"Failed to apply theme: {e}", exc_info=True)

    def _setup_ui_shell(self) -> None:
        logger.debug("Setting up UI shell...")
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        nav_panel = QFrame()
        nav_panel.setObjectName("nav_panel")
        nav_panel.setFixedHeight(50)
        nav_layout = QHBoxLayout(nav_panel)
        btn_dashboard = QPushButton("Dashboard")
        btn_settings = QPushButton("Settings")
        btn_analytics = QPushButton("Analytics")
        nav_layout.addWidget(btn_dashboard)
        nav_layout.addWidget(btn_settings)
        nav_layout.addWidget(btn_analytics)
        self.stacked_widget = QStackedWidget()
        self.dashboard_widget = DashboardWidget(self.settings_manager, self.db_manager)
        self.settings_widget = SettingsWidget(self.settings_manager)
        self.analytics_widget = AnalyticsWidget(self.db_manager)
        self.stacked_widget.addWidget(self.dashboard_widget)
        self.stacked_widget.addWidget(self.settings_widget)
        self.stacked_widget.addWidget(self.analytics_widget)
        main_layout.addWidget(nav_panel)
        main_layout.addWidget(self.stacked_widget)
        main_layout.setStretch(1, 1)
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("K.A.I.R.O.S. Initialized and Ready.", 5000)
        btn_dashboard.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.dashboard_widget))
        btn_settings.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.settings_widget))
        btn_analytics.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.analytics_widget))
        logger.debug("UI shell setup complete.")

    def _init_sound_effects(self) -> None:
        logger.debug("Initializing sound effects...")
        self.primed_sound = QSoundEffect()
        self.confirmed_sound = QSoundEffect()
        self.error_sound = QSoundEffect()
        sound_files = {
            self.primed_sound: "assets/sounds/primed.wav",
            self.confirmed_sound: "assets/sounds/confirmed.wav",
            self.error_sound: "assets/sounds/error.wav",
        }
        for sound_effect, path_str in sound_files.items():
            path = Path(path_str)
            if path.exists():
                sound_effect.setSource(QUrl.fromLocalFile(str(path.resolve())))
                sound_effect.setVolume(0.5)
            else:
                logger.warning(f"Sound file not found at '{path_str}'. This sound will be disabled.")

    def _setup_tray_icon(self) -> None:
        self.tray_icon = QSystemTrayIcon(QIcon("assets/kairos_icon.png"), self)
        self.tray_icon.setToolTip("K.A.I.R.O.S. is active.")
        tray_menu = QMenu()
        show_action = QAction("Show Command Center", self)
        quit_action = QAction("Quit K.A.I.R.O.S.", self)
        show_action.triggered.connect(self.show)
        quit_action.triggered.connect(QApplication.instance().quit)
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def connect_signals(self) -> None:
        self.new_log_entry.connect(self.dashboard_widget.log_event)
        self.settings_manager.settings_updated.connect(self._apply_theme)
        self.settings_manager.settings_updated.connect(self.dashboard_widget._reload_ui)
        QApplication.instance().aboutToQuit.connect(self._shutdown_application)
        self.action_manager.ocr_requested.connect(self._trigger_ocr_worker)

    def _schedule_jobs(self) -> None:
        try:
            briefing_time = QTime.fromString(self.settings_manager.settings.core.daily_briefing_time, "HH:mm")
            self.scheduler.schedule_daily_job(hour=briefing_time.hour(), minute=briefing_time.minute(), callback=self.action_manager._action_daily_briefing)
            self.scheduler.start()
        except Exception as e:
            logger.error(f"Failed to schedule daily briefing job: {e}", exc_info=True)

    def _start_workers(self) -> None:
        logger.info("Starting worker threads...")
        self.video_worker = VideoWorker(self.settings_manager)
        self.video_worker.new_data.connect(self.dashboard_widget.update_video_feed)
        self.video_worker.gesture_detected.connect(self.handle_gesture)
        self.video_worker.error_occurred.connect(self.handle_system_message)
        self.video_worker.state_changed.connect(self.handle_gesture_state_change)
        self.video_worker.window_targeted.connect(self.set_targeted_window)
        self.video_worker.start()

        self.audio_worker = AudioWorker(self.settings_manager)
        self.audio_worker.new_transcription_with_emotion.connect(self.handle_transcription)
        self.audio_worker.error_occurred.connect(self.handle_system_message)
        self.audio_worker.start()

        self.api_server_worker = ServerWorker(self.action_manager)
        self.api_server_worker.start()
        self.speaker_worker.start()

        self.system_stats_worker = SystemStatsWorker()
        if "SYSTEM_STATS" in self.dashboard_widget.loaded_widgets:
            self.system_stats_worker.new_stats.connect(self.dashboard_widget.loaded_widgets["SYSTEM_STATS"].update_stats)
        self.system_stats_worker.start()

        self.update_checker = UpdateCheckerWorker(self.app_version, self.settings_manager.settings.core.update_checker_url)
        self.update_checker.update_available.connect(self._on_update_available)
        self.update_checker.start()
        
        self.ocr_worker = OcrWorker()
        self.ocr_worker.ocr_complete.connect(self.handle_ocr_result)
        self.ocr_worker.error_occurred.connect(self.handle_system_message)
        
        self.activity_logger_worker = ActivityLoggerWorker()
        self.activity_logger_worker.suggestion_ready.connect(self.handle_proactive_suggestion)
        self.activity_logger_worker.start()
        
    def set_targeted_window(self, window_object: Any):
        """Stores the window currently being pointed at."""
        self.targeted_window = window_object
        logger.debug(f"Gesture context updated: Targeted window is now '{window_object.title}'")

    def _on_update_available(self, new_version: str, repo_url: str):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Update Available")
        msg_box.setText(f"A new version of K.A.I.R.O.S. is available: <b>{new_version}</b>")
        msg_box.setInformativeText("Would you like to visit the download page?")
        visit_button = msg_box.addButton("Visit Page", QMessageBox.ButtonRole.ActionRole)
        msg_box.addButton("Dismiss", QMessageBox.ButtonRole.RejectRole)
        msg_box.exec()
        if msg_box.clickedButton() == visit_button:
            QDesktopServices.openUrl(QUrl(repo_url))
            
    def _trigger_ocr_worker(self):
        if not self.ocr_worker.isRunning(): self.ocr_worker.start()
        else: logger.warning("OCR worker is already running. Ignoring request.")

    def handle_ocr_result(self, text: str):
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        if not text:
            self.action_manager._speak("I analyzed the screen but could not find any readable text.")
            return
        self.new_log_entry.emit(timestamp, "[OCR]", f"Screen text extracted (snippet): {text[:70]}...", "INFO", {})
        if self.action_manager.llm_handler:
            suggestion = self.action_manager.llm_handler.get_proactive_suggestion(text)
            if suggestion:
                self.action_manager._speak(suggestion)

    def handle_system_message(self, message: str, level: str) -> None:
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        self.new_log_entry.emit(timestamp, "[SYSTEM]", message, level.upper(), {})
        self.error_sound.play()
        if level.upper() == "CRITICAL": QMessageBox.critical(self, "Critical System Error", message)
        elif level.upper() == "WARNING": self.statusBar().showMessage(f"Warning: {message}", 5000)

    def handle_gesture(self, intent: str, entities: Dict[str, Any] | None = None) -> None:
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        if intent == "[STOP_ACTION]":
            self.interrupt_event.set()
            return
        self.new_log_entry.emit(timestamp, "[GESTURE]", f"Intent Detected: {intent}", "INFO", {})
        self.confirmed_sound.play()
        self.action_manager.execute_action(intent, entities)

    def handle_gesture_state_change(self, state: str) -> None:
        if state == "PRIMED": self.primed_sound.play()

    def handle_proactive_suggestion(self, suggestion_text: str, app_sequence: List[str]):
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        self.new_log_entry.emit(timestamp, "[BRAIN]", f"Proactive Suggestion: {suggestion_text}", "INFO", {})
        self.action_manager._speak(suggestion_text)
        self.pending_suggestion = app_sequence

    def handle_transcription(self, text: str, emotion: str) -> None:
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        self.new_log_entry.emit(timestamp, "[VOICE]", text, "INFO", {})
        
        emotion_map = {"neu": "Neutral", "hap": "Happy", "sad": "Sad", "ang": "Angry"}
        emotion_full = emotion_map.get(emotion, emotion.capitalize())
        self.new_log_entry.emit(timestamp, "[EMOTION]", f"Detected emotion: {emotion_full}", "INFO", {})
        
        _, process_name = self.context_manager.get_active_window_info()
        intent, entities, prompt = self.nlu_engine.process(text, context=process_name)
        
        if self.pending_suggestion and intent == "[CONFIRM_SUGGESTION]":
            self.action_manager.execute_app_sequence(self.pending_suggestion)
            self.pending_suggestion = None
            return
        if self.pending_suggestion: self.pending_suggestion = None

        is_generic_window_command = intent in ["[CLOSE_WINDOW]", "[MINIMIZE_WINDOW]", "[MAXIMIZE_WINDOW]"]
        if self.targeted_window and is_generic_window_command and not entities:
            entities = {"target_window": self.targeted_window}
            logger.info(f"Fusing gesture context: Applying command to window '{self.targeted_window.title}'")
            self.targeted_window = None

        if not intent:
            if prompt: self.action_manager._speak(prompt)
            return

        if intent == "[STOP_ACTION]":
            self.interrupt_event.set()
            return

        entity_str = str(entities) if entities else "None"
        log_id = self.db_manager.log_nlu_result(text, str(intent), entity_str)
        log_content = f"Intent: {intent}" + (f" | Entities: {entity_str}" if entities else "")
        log_data = {"log_id": log_id, "original_text": text, "predicted_intent": intent, "predicted_entity": entity_str}
        self.new_log_entry.emit(timestamp, "[BRAIN]", log_content, "INFO", log_data)
        
        if intent != "[UNKNOWN_INTENT]":
            # <--- MODIFICATION --->
            # Pass the detected emotion to the action manager to influence the response tone.
            self.action_manager.execute_action(intent, entities, emotion=emotion)
        
        if prompt:
            self.action_manager._speak(prompt)

    def _shutdown_application(self) -> None:
        logger.info("Shutdown signal received. Stopping all workers...")
        workers = [
            self.video_worker, self.audio_worker, self.api_server_worker,
            self.speaker_worker, self.system_stats_worker, self.ocr_worker,
            self.activity_logger_worker
        ]
        for worker in workers:
            if hasattr(worker, 'stop'): worker.stop()
        for worker in workers:
            if hasattr(worker, 'wait'): worker.wait(2000)

        logger.info("Worker threads stopped.")
        self.scheduler.shutdown()
        self.settings_manager.save_settings()
        self.tray_icon.hide()
        logger.info("K.A.I.R.O.S. shutdown complete.")

    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()
        self.hide()
        self.tray_icon.showMessage("K.A.I.R.O.S.", "Application is still running.", QSystemTrayIcon.MessageIcon.Information, 2000)