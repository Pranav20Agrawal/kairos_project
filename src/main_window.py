# src/main_window.py

# UI core primitives, signals/slots, timers, and types. Signal defines custom event channels; QTimer is used for the shutdown failsafe.
from PySide6.QtCore import Signal, QDateTime, QTime, Qt, QUrl, Slot, QTimer, QThreadPool
# Window close events, tray/menu icons/actions, and QDesktopServices.openUrl() to open links (used for update URL).
from PySide6.QtGui import QCloseEvent, QIcon, QAction, QDesktopServices
# Main UI building blocks. QSystemTrayIcon behavior is platform-dependent; Windows/Linux support is good, macOS requires special attention (app bundle).
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget,
    QFrame, QMessageBox, QStatusBar, QSystemTrayIcon, QMenu, QApplication
)
# Plays short sounds. Note: audio backend may behave differently across platforms and might need platform-specific fallbacks.
from PySide6.QtMultimedia import QSoundEffect
# Path handling
from pathlib import Path
import threading
from typing import Any, Dict, List
import asyncio
import logging

# --- K.A.I.R.O.S. Core Imports ---
from src.video_worker import VideoWorker
from src.audio_worker import AudioWorker
from src.speaker_worker import SpeakerWorker
from src.workers.system_stats_worker import SystemStatsWorker
from src.workers.update_checker_worker import UpdateCheckerWorker
from src.workers.ocr_worker import OcrWorker
from src.workers.activity_logger_worker import ActivityLoggerWorker
from src.workers.clipboard_worker import ClipboardWorker
from src.workers.discovery_worker import DiscoveryWorker
from src.workers.input_monitor_worker import InputMonitorWorker
from src.workers.flow_state_worker import FlowStateWorker, FlowState
from src.workers.task_context_worker import TaskContextWorker
from src.workers.goal_oriented_worker import GoalOrientedWorker
from src.workers.heuristics_tuner import HeuristicsTuner
from src.workers.system_indexer_worker import SystemIndexerWorker
from src.activity_analyzer import SessionAnalyzer
from src.nlu_engine import NluEngine
from src.memory_manager import MemoryManager
from src.llm_handler import LlmHandler
from src.action_manager import ActionManager
from src.ui_components.dashboard_widget import DashboardWidget
from src.ui_components.settings_widget import SettingsWidget
from src.settings_manager import SettingsManager
from src.database_manager import DatabaseManager
from src.scheduler import Scheduler
from src.ui_components.analytics_widget import AnalyticsWidget
from src.ui_components.goals_widget import GoalsWidget
from src.api_server import ServerWorker, kairos_api
from src.ui_components.widgets.command_bar_widget import CommandBarWidget

logger = logging.getLogger(__name__)

class KairosMainWindow(QMainWindow):
    new_log_entry = Signal(str, str, str, str, dict)

    def __init__(self, app_version: str) -> None:
        super().__init__()
        self.app_version = app_version
        self.thread_pool = QThreadPool()
        logger.info(f"Global thread pool created with {self.thread_pool.maxThreadCount()} threads.")
        logger.info(f"K.A.I.R.O.S. version {self.app_version} initializing...")
        self.setWindowTitle(f"K.A.I.R.O.S. - Command Center v{self.app_version}")
        self.setGeometry(100, 100, 1200, 800)
        self.loop = None
        
        self.command_bar = CommandBarWidget()

        self.interrupt_event = threading.Event()
        self.pending_suggestion: List[str] | None = None
        self.targeted_window: Any | None = None
        self.startup_complete = False

        # === SHUTDOWN COORDINATION ===
        self._shutdown_in_progress = False
        self._shutdown_timer = QTimer()
        self._shutdown_timer.setSingleShot(True)
        self._shutdown_timer.timeout.connect(self._force_shutdown)

        # === LAZY LOADING STATE TRACKING ===
        self.video_worker_active = False
        self.audio_worker_active = False
        self.heavy_workers_initialized = False

        # === WORKER REFERENCES FOR PROPER CLEANUP ===
        self.all_workers = []
        self.essential_workers = []
        self.heavy_workers = []

        logger.info("Initializing essential backend components...")
        self.settings_manager = SettingsManager()
        self.db_manager = DatabaseManager()
        self.clipboard_worker = ClipboardWorker()
        self.nlu_engine = NluEngine(self.settings_manager)
        self.llm_handler = LlmHandler(settings_manager=self.settings_manager)
        self.session_analyzer = SessionAnalyzer(self.llm_handler)
        self.memory_manager = MemoryManager(self.nlu_engine.model)
        self.speaker_worker = SpeakerWorker()
        
        self.action_manager = ActionManager(
            self.settings_manager, 
            self.interrupt_event, 
            self.speaker_worker, 
            kairos_api, 
            self.memory_manager,
            self.thread_pool
        )
        
        # Initialize lightweight audio worker but don't start it
        self.audio_worker = AudioWorker(self.settings_manager)
        self.scheduler = Scheduler()
        
        # Initialize video worker but don't start it
        self.video_worker = VideoWorker(self.settings_manager)
        
        kairos_api.clipboard_update_callback = self.on_phone_clipboard_changed
        kairos_api.notification_callback = self.on_phone_notification_received
        kairos_api.text_command_callback = self.on_phone_text_command

        self._apply_theme()
        self._setup_ui_shell()
        self._init_sound_effects()
        self._setup_tray_icon()
        self.connect_signals()
        self._schedule_jobs()
        self._start_essential_workers()  # Only start essential workers

        logger.info("K.A.I.R.O.S. Main Window initialized successfully in low-power mode.")

    def _play_startup_sound(self):
        logger.info("Speaker is ready. Playing startup sound and finalizing sequence.")
        self.action_manager._speak("KAIROS essential systems are online. Camera and microphone are in standby mode.")
        self.startup_complete = True

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
        btn_goals = QPushButton("Goals")
        nav_layout.addWidget(btn_dashboard)
        nav_layout.addWidget(btn_settings)
        nav_layout.addWidget(btn_analytics)
        nav_layout.addWidget(btn_goals)

        self.stacked_widget = QStackedWidget()
        self.dashboard_widget = DashboardWidget(self.settings_manager, self.db_manager, self)
        self.settings_widget = SettingsWidget(self.settings_manager)
        self.analytics_widget = AnalyticsWidget(self.db_manager)
        self.goals_widget = GoalsWidget(self.settings_manager)
        self.stacked_widget.addWidget(self.dashboard_widget)
        self.stacked_widget.addWidget(self.settings_widget)
        self.stacked_widget.addWidget(self.analytics_widget)
        self.stacked_widget.addWidget(self.goals_widget)
        
        main_layout.addWidget(nav_panel)
        main_layout.addWidget(self.stacked_widget)
        main_layout.setStretch(1, 1)

        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("K.A.I.R.O.S. Initialized in Low-Power Mode - Camera and Audio on Standby.", 5000)
        
        btn_dashboard.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.dashboard_widget))
        btn_settings.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.settings_widget))
        btn_analytics.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.analytics_widget))
        btn_goals.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.goals_widget))
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
        self.tray_icon.setToolTip("K.A.I.R.O.S. is active in low-power mode.")
        tray_menu = QMenu()
        show_action = QAction("Show Command Center", self)
        activate_camera_action = QAction("Activate Camera", self)
        activate_audio_action = QAction("Activate Audio", self)
        quit_action = QAction("Quit K.A.I.R.O.S.", self)
        
        show_action.triggered.connect(self.show)
        activate_camera_action.triggered.connect(self.start_video_worker)
        activate_audio_action.triggered.connect(self.start_audio_worker)
        quit_action.triggered.connect(QApplication.instance().quit)
        
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(activate_camera_action)
        tray_menu.addAction(activate_audio_action)
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
        self.speaker_worker.model_loaded.connect(self._play_startup_sound)
        self.command_bar.command_submitted.connect(self.handle_chat_submission)
        self.clipboard_worker.clipboard_changed.connect(self.on_pc_clipboard_changed)

    def _schedule_jobs(self) -> None:
        try:
            briefing_time = QTime.fromString(self.settings_manager.settings.core.daily_briefing_time, "HH:mm")
            self.scheduler.schedule_daily_job(hour=briefing_time.hour(), minute=briefing_time.minute(), callback=self.action_manager._action_daily_briefing)
            self.scheduler.start()
        except Exception as e:
            logger.error(f"Failed to schedule daily briefing job: {e}", exc_info=True)

    def _start_essential_workers(self) -> None:
        """
        PERFORMANCE OPTIMIZATION: Only start essential, lightweight workers.
        Heavy workers (video, audio, flow state monitoring) are started on-demand.
        """
        logger.info("Starting essential worker threads only...")
        
        # Essential workers that are lightweight
        self.system_indexer_worker = SystemIndexerWorker()
        self.essential_workers.append(self.system_indexer_worker)
        self.system_indexer_worker.start()
        
        self.discovery_worker = DiscoveryWorker()
        self.essential_workers.append(self.discovery_worker)
        self.discovery_worker.start()
        
        self.api_server_worker = ServerWorker(self.action_manager)
        self.essential_workers.append(self.api_server_worker)
        self.api_server_worker.start()
        
        self.essential_workers.append(self.clipboard_worker)
        self.clipboard_worker.start()
        
        # Start speaker worker (essential for feedback)
        self.essential_workers.append(self.speaker_worker)
        self.speaker_worker.start()

        # Lightweight system monitoring
        self.system_stats_worker = SystemStatsWorker()
        self.essential_workers.append(self.system_stats_worker)
        if "SYSTEM_STATS" in self.dashboard_widget.loaded_widgets:
            self.system_stats_worker.new_stats.connect(self.dashboard_widget.loaded_widgets["SYSTEM_STATS"].update_stats)
        self.system_stats_worker.start()

        # Update checker (low resource usage)
        self.update_checker = UpdateCheckerWorker(self.app_version, self.settings_manager.settings.core.update_checker_url)
        self.essential_workers.append(self.update_checker)
        self.update_checker.update_available.connect(self._on_update_available)
        self.update_checker.start()

        # OCR worker (initialized but not started until needed)
        self.ocr_worker = OcrWorker()
        self.essential_workers.append(self.ocr_worker)
        self.ocr_worker.ocr_complete.connect(self.handle_ocr_result)
        self.ocr_worker.error_occurred.connect(self.handle_system_message)

        # Activity logger (lightweight but essential for context)
        self.activity_logger_worker = ActivityLoggerWorker()
        self.essential_workers.append(self.activity_logger_worker)
        self.activity_logger_worker.activity_logged.connect(self.session_analyzer.on_activity_logged)
        self.session_analyzer.suggestion_ready.connect(self.handle_macro_suggestion)
        self.activity_logger_worker.activity_stats_updated.connect(
            lambda stats: logger.debug(f"Activity Stats: {stats}")
        )
        self.activity_logger_worker.start()

        # Task context worker (lightweight)
        self.task_context_worker = TaskContextWorker()
        self.essential_workers.append(self.task_context_worker)
        self.activity_logger_worker.activity_logged.connect(self.task_context_worker.on_activity_logged)
        self.task_context_worker.task_context_changed.connect(self.handle_task_context_change)
        self.task_context_worker.start()

        # Heuristics tuner (lightweight)
        self.heuristics_tuner = HeuristicsTuner(self.settings_manager, self.db_manager)
        self.essential_workers.append(self.heuristics_tuner)
        self.heuristics_tuner.tuning_suggestion_ready.connect(self.handle_tuning_suggestion)
        self.heuristics_tuner.start()

        # Update all_workers list
        self.all_workers = self.essential_workers.copy()

        logger.info("Essential workers started. Heavy workers (video, audio, flow state) are on standby.")

    def _initialize_heavy_workers(self) -> None:
        """
        LAZY LOADING: Initialize heavy workers only when needed.
        This method is called when either video or audio workers are requested.
        """
        if self.heavy_workers_initialized:
            return

        logger.info("Initializing heavy monitoring workers...")

        # Input monitor for flow state detection
        self.input_monitor_worker = InputMonitorWorker()
        self.heavy_workers.append(self.input_monitor_worker)
        self.input_monitor_worker.start()
        
        # Flow state worker
        self.flow_state_worker = FlowStateWorker()
        self.heavy_workers.append(self.flow_state_worker)
        
        # Connect data streams to flow state worker
        self.input_monitor_worker.new_input_stats.connect(self.flow_state_worker.update_input_stats)
        self.activity_logger_worker.activity_stats_updated.connect(self.flow_state_worker.update_activity_stats)
        self.video_worker.video_stats_updated.connect(self.flow_state_worker.update_video_stats)
        
        self.flow_state_worker.flow_state_changed.connect(self.handle_flow_state_change)
        self.flow_state_worker.start()

        # Goal-oriented worker
        self.goal_oriented_worker = GoalOrientedWorker(
            settings_manager=self.settings_manager,
            memory_manager=self.memory_manager,
            llm_handler=self.action_manager.llm_handler,
            dashboard=self.dashboard_widget
        )
        self.heavy_workers.append(self.goal_oriented_worker)
        
        if hasattr(self, 'task_context_worker'):
            self.task_context_worker.task_context_changed.connect(self.goal_oriented_worker.on_task_context_changed)

        # Update all_workers list
        self.all_workers = self.essential_workers + self.heavy_workers

        self.heavy_workers_initialized = True
        logger.info("Heavy workers initialized successfully.")

    def start_video_worker(self) -> None:
        """
        ON-DEMAND ACTIVATION: Start the video worker when explicitly requested.
        """
        if self.video_worker_active:
            logger.info("Video worker is already active.")
            return

        logger.info("User requested video worker activation. Starting camera...")
        
        # Initialize heavy workers if not already done
        self._initialize_heavy_workers()
        
        # Add video worker to heavy workers if not already there
        if self.video_worker not in self.heavy_workers:
            self.heavy_workers.append(self.video_worker)
            self.all_workers.append(self.video_worker)
        
        # Connect video worker signals
        self.video_worker.new_data.connect(self.dashboard_widget.update_video_feed)
        self.video_worker.gesture_detected.connect(self.handle_gesture)
        self.video_worker.error_occurred.connect(self.handle_system_message)
        self.video_worker.state_changed.connect(self.handle_gesture_state_change)
        self.video_worker.window_targeted.connect(self.set_targeted_window)
        
        # Start the worker
        self.video_worker.start()
        self.video_worker_active = True
        
        # Update UI status
        self.statusBar().showMessage("Camera activated - Gesture recognition enabled.", 5000)
        self.tray_icon.setToolTip("K.A.I.R.O.S. is active - Camera enabled.")
        
        # Provide audio feedback
        self.action_manager._speak("Camera activated. Gesture recognition is now online.")

    def start_audio_worker(self) -> None:
        """
        ON-DEMAND ACTIVATION: Start the audio worker when explicitly requested.
        """
        if self.audio_worker_active:
            logger.info("Audio worker is already active.")
            return

        logger.info("User requested audio worker activation. Starting microphone...")
        
        # Initialize heavy workers if not already done
        self._initialize_heavy_workers()
        
        # Add audio worker to heavy workers if not already there
        if self.audio_worker not in self.heavy_workers:
            self.heavy_workers.append(self.audio_worker)
            self.all_workers.append(self.audio_worker)
        
        # Connect audio worker signals
        self.audio_worker.new_transcription_with_emotion.connect(self.handle_transcription)
        self.audio_worker.error_occurred.connect(self.handle_system_message)
        
        # Start the worker
        self.audio_worker.start()
        self.audio_worker_active = True
        
        # Update UI status
        self.statusBar().showMessage("Microphone activated - Voice commands enabled.", 5000)
        self.tray_icon.setToolTip("K.A.I.R.O.S. is active - Microphone enabled.")
        
        # Provide audio feedback
        self.action_manager._speak("Microphone activated. Voice commands are now online.")

    def stop_video_worker(self) -> None:
        """Stop the video worker to save resources."""
        if not self.video_worker_active:
            return
        
        logger.info("Stopping video worker to conserve resources...")
        if hasattr(self.video_worker, 'stop'):
            self.video_worker.stop()
        
        self.video_worker_active = False
        self.statusBar().showMessage("Camera deactivated - Gesture recognition disabled.", 5000)
        self.tray_icon.setToolTip("K.A.I.R.O.S. is active - Camera disabled.")
        self.action_manager._speak("Camera deactivated to conserve resources.")

    def stop_audio_worker(self) -> None:
        """Stop the audio worker to save resources."""
        if not self.audio_worker_active:
            return
        
        logger.info("Stopping audio worker to conserve resources...")
        if hasattr(self.audio_worker, 'stop'):
            self.audio_worker.stop()
        
        self.audio_worker_active = False
        self.statusBar().showMessage("Microphone deactivated - Voice commands disabled.", 5000)
        self.tray_icon.setToolTip("K.A.I.R.O.S. is active - Microphone disabled.")
        self.action_manager._speak("Microphone deactivated to conserve resources.")

    @Slot(str, str)
    def handle_tuning_suggestion(self, title: str, message: str):
        """Shows a dialog box with a tuning suggestion from the HeuristicsTuner."""
        logger.info(f"Displaying tuning suggestion: {title}")
        QMessageBox.information(self, title, message)

    @Slot(dict)
    def handle_macro_suggestion(self, suggestion: dict):
        """Presents the LLM's macro suggestion to the user."""
        macro_name = suggestion.get("macro_name", "this workflow")
        goal = suggestion.get("goal", "No goal described.")
        actions = suggestion.get("actions")
        
        reply = QMessageBox.question(self,
            "Workflow Suggestion",
            f"I noticed a pattern:\n\n"
            f"<b>Goal:</b> {goal}\n\n"
            f"Would you like to create a new command called <b>'{macro_name}'</b> to automate this?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            logger.info(f"User accepted suggestion to create macro: '{macro_name}'")
            
            if actions:
                success = self.settings_manager.create_macro_from_suggestion(macro_name, actions)
                if success:
                    self.statusBar().showMessage(f"New command '{macro_name}' created successfully!", 5000)
                    self.action_manager._speak(f"Great. I've created the new command, {macro_name}.")
                    
                    timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
                    self.new_log_entry.emit(
                        timestamp, 
                        "[MACRO]", 
                        f"Created new macro '{macro_name}' with {len(actions)} steps", 
                        "INFO", 
                        {"macro_name": macro_name, "steps_count": len(actions)}
                    )
                else:
                    self.statusBar().showMessage(f"Error: A macro with that name may already exist.", 5000)
                    self.action_manager._speak(f"Sorry, I couldn't create the macro. A command with that name might already exist.")
            else:
                logger.error("Cannot create macro, action sequence was missing from suggestion.")
                self.statusBar().showMessage("Error: Cannot create macro without action sequence.", 5000)
                self.action_manager._speak("Sorry, I couldn't create the macro because the action sequence was incomplete.")
        else:
            logger.info(f"User declined macro suggestion for '{macro_name}'")
            self.action_manager._speak("No problem. I'll keep watching for other patterns.")
        
    @Slot(str)
    def handle_flow_state_change(self, state: str):
        """Handles the user entering or leaving a flow state."""
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        log_message = f"Detected transition to {state} state."
        self.new_log_entry.emit(timestamp, "[BRAIN]", log_message, "INFO", {})
        if state == FlowState.FOCUSED:
            self.action_manager._speak("Guardian mode activated. I'll keep you focused.")
        elif state == FlowState.IDLE:
            self.action_manager._speak("Guardian mode deactivated.")

    @Slot(str)
    def handle_task_context_change(self, context: str):
        """Handles the user's high-level task context changing."""
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        self.new_log_entry.emit(timestamp, "[BRAIN]", f"Context changed to {context}", "INFO", {})
        friendly_name = context.replace("TASK_", "").replace("_", " ").title()
        self.action_manager._speak(f"Reconfiguring for {friendly_name}.")
        
        if not hasattr(self.action_manager, 'llm_handler') or not self.action_manager.llm_handler:
            logger.warning("LLM Handler not available, cannot generate new layout.")
            return
        
        available_widget_keys = list(self.dashboard_widget.available_widgets.keys())
        new_layout = self.action_manager.llm_handler.generate_ui_layout(context, available_widget_keys)
        
        if new_layout:
            self.dashboard_widget.update_layout(new_layout)
            logger.info(f"Applied AI-generated layout for context: {context}")
        else:
            logger.error("LLM failed to provide a valid layout. Dashboard remains unchanged.")

    @Slot(str)
    def on_phone_text_command(self, command: str):
        context = self.activity_logger_worker.last_app_context
        self._process_input_text(command, source="[PHONE_CHAT]", context=context)

    def on_pc_clipboard_changed(self, text: str):
        if kairos_api.loop and kairos_api.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                kairos_api.send_clipboard_update(text),
                kairos_api.loop
            )

    def on_phone_clipboard_changed(self, text: str):
        self.clipboard_worker.update_clipboard_cache(text)

    @Slot(dict)
    def on_phone_notification_received(self, notification_data: dict):
        self.dashboard_widget.add_notification(notification_data)

    def set_targeted_window(self, window_object: Any):
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
        if not self.ocr_worker.isRunning(): 
            self.ocr_worker.start()
        else: 
            logger.warning("OCR worker is already running. Ignoring request.")

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
        if level.upper() == "CRITICAL": 
            QMessageBox.critical(self, "Critical System Error", message)
        elif level.upper() == "WARNING": 
            self.statusBar().showMessage(f"Warning: {message}", 5000)

    def handle_gesture(self, intent: str, entities: Dict[str, Any] | None = None) -> None:
        logger.info(f"[GESTURE CONFIRMED] Received intent '{intent}' from VideoWorker. Executing action.")
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        if intent == "[STOP_ACTION]":
            self.interrupt_event.set()
            return
        self.new_log_entry.emit(timestamp, "[GESTURE]", f"Intent Detected: {intent}", "INFO", {})
        self.confirmed_sound.play()
        self.action_manager.execute_action(intent, entities)

    def handle_gesture_state_change(self, state: str) -> None:
        if state == "PRIMED": 
            self.primed_sound.play()

    def handle_proactive_suggestion(self, suggestion_text: str, app_sequence: List[str]):
        if not self.startup_complete:
            logger.info("Startup sequence not complete — skipping proactive suggestion.")
            return
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        self.new_log_entry.emit(timestamp, "[BRAIN]", f"Proactive Suggestion: {suggestion_text}", "INFO", {})
        self.action_manager._speak(suggestion_text)
        self.pending_suggestion = app_sequence

    def handle_chat_submission(self, text: str):
        if not text:
            return
        context = self.activity_logger_worker.last_app_context
        logger.info(f"Processing text command '{text}' with context '{context}'")
        self._process_input_text(text, source="[COMMAND_BAR]", context=context)

    def handle_transcription(self, text: str, emotion: str):
        context = self.activity_logger_worker.last_app_context
        self._process_input_text(text, source="[VOICE]", emotion=emotion, context=context)

    def _process_input_text(self, text: str, source: str, emotion: str = "neu", context: str | None = None):
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        self.new_log_entry.emit(timestamp, source, text, "INFO", {})
        
        intent, entities, prompt = self.nlu_engine.process(text, context=context)
        
        if self.pending_suggestion and intent == "[CONFIRM_SUGGESTION]":
            logger.info(f"Executing suggested sequence: {self.pending_suggestion}")
            self.pending_suggestion = None
            return
        if self.pending_suggestion: 
            self.pending_suggestion = None

        if not intent:
            if prompt: 
                self.action_manager._speak(prompt)
            return

        if intent == "[STOP_ACTION]":
            self.interrupt_event.set()
            return

        entity_str = str(entities) if entities else "None"
        log_id = self.db_manager.log_nlu_result(text, str(intent), entity_str)
        log_content = f"Intent: {intent}" + (f" | Entities: {entity_str}" if entities else "")
        log_data = {"log_id": log_id, "original_text": text, "predicted_intent": intent, "predicted_entity": entity_str}
        self.new_log_entry.emit(timestamp, "[BRAIN]", log_content, "INFO", log_data)
        
        self.action_manager.execute_action(intent, entities, emotion)
        
    def _shutdown_application(self) -> None:
            """Gracefully stops all worker threads and saves settings."""
            if self._shutdown_in_progress:
                return
            
            logger.info("Shutdown signal received. Stopping all workers...")
            self._shutdown_in_progress = True
            self.command_bar.close()

            # Start a failsafe timer. If shutdown takes too long, force quit.
            self._shutdown_timer.start(5000) # 5-second timeout

            # Stop all workers
            for worker in self.all_workers:
                if hasattr(worker, 'stop'):
                    worker.stop()
            
            # Wait for all threads to finish
            for worker in self.all_workers:
                if hasattr(worker, 'wait'):
                    worker.wait(2000) # Wait up to 2 seconds for each worker

            logger.info("Worker threads stopped.")
            
            self.scheduler.shutdown()
            self.settings_manager.save_settings()
            self.tray_icon.hide()
            
            self._shutdown_timer.stop() # Cancel the failsafe timer
            logger.info("K.A.I.R.O.S. shutdown complete.")
            QApplication.instance().quit()


    def _force_shutdown(self) -> None:
        """Forces the application to exit if graceful shutdown fails."""
        logger.warning("Graceful shutdown timed out. Forcing exit.")
        QApplication.instance().quit()


    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()
        self.hide()
        self.command_bar.show()
        self.tray_icon.showMessage("K.A.I.R.O.S.", "Application is still running in low-power mode.", QSystemTrayIcon.MessageIcon.Information, 2000)