# src/main_window.py

from PySide6.QtCore import Signal, QDateTime, QTime, Qt, QUrl, Slot
from PySide6.QtGui import QCloseEvent, QIcon, QAction, QDesktopServices
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget,
    QFrame, QMessageBox, QStatusBar, QSystemTrayIcon, QMenu, QApplication
)
from PySide6.QtMultimedia import QSoundEffect
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
from src.workers.input_monitor_worker import InputMonitorWorker  # <-- ADDED THIS LINE
from src.workers.flow_state_worker import FlowStateWorker, FlowState  # <-- ADD THIS
from src.workers.browser_history_worker import BrowserHistoryWorker  # <-- ADD THIS
from src.workers.task_context_worker import TaskContextWorker  # <-- ADD THIS
from src.workers.goal_oriented_worker import GoalOrientedWorker  # <-- ADD THIS
from src.workers.heuristics_tuner import HeuristicsTuner  # <-- ADD THIS
from src.activity_analyzer import SessionAnalyzer  # --- ADDED THIS LINE ---
from src.nlu_engine import NluEngine
from src.memory_manager import MemoryManager  # <-- ADDED MEMORY MANAGER IMPORT
from src.llm_handler import LlmHandler  # <-- ADD THIS IMPORT
from src.action_manager import ActionManager
from src.ui_components.dashboard_widget import DashboardWidget
from src.ui_components.settings_widget import SettingsWidget
from src.settings_manager import SettingsManager
from src.database_manager import DatabaseManager
from src.scheduler import Scheduler
from src.ui_components.analytics_widget import AnalyticsWidget
from src.ui_components.goals_widget import GoalsWidget  # <-- ADD THIS
from src.api_server import ServerWorker, kairos_api, clipboard_update_callback, notification_callback, text_command_callback
from src.ui_components.widgets.command_bar_widget import CommandBarWidget

logger = logging.getLogger(__name__)

class KairosMainWindow(QMainWindow):
    new_log_entry = Signal(str, str, str, str, dict)

    def __init__(self, app_version: str) -> None:
        super().__init__()
        self.app_version = app_version
        logger.info(f"K.A.I.R.O.S. version {self.app_version} initializing...")
        self.setWindowTitle(f"K.A.I.R.O.S. - Command Center v{self.app_version}")
        self.setGeometry(100, 100, 1200, 800)
        self.loop = None
        
        self.command_bar = CommandBarWidget()

        self.interrupt_event = threading.Event()
        self.pending_suggestion: List[str] | None = None
        self.targeted_window: Any | None = None
        self.startup_complete = False

        logger.info("Initializing backend components...")
        self.settings_manager = SettingsManager()
        self.db_manager = DatabaseManager()
        self.clipboard_worker = ClipboardWorker()
        self.nlu_engine = NluEngine(self.settings_manager)
        self.llm_handler = LlmHandler(settings_manager=self.settings_manager)  # <-- UPDATE THIS LINE
        self.memory_manager = MemoryManager(self.nlu_engine.model)  # <-- ADDED MEMORY MANAGER
        self.speaker_worker = SpeakerWorker()
        
        # --- UPDATED ACTION MANAGER WITH MEMORY MANAGER ---
        self.action_manager = ActionManager(
            self.settings_manager, 
            self.interrupt_event, 
            self.speaker_worker, 
            kairos_api, 
            self.memory_manager  # <-- ADDED MEMORY MANAGER PARAMETER
        )
        
        self.audio_worker = AudioWorker(self.settings_manager)
        self.scheduler = Scheduler()
        
        globals()['clipboard_update_callback'] = self.on_phone_clipboard_changed
        globals()['notification_callback'] = self.on_phone_notification_received
        globals()['text_command_callback'] = self.on_phone_text_command

        self._apply_theme()
        self._setup_ui_shell()
        self._init_sound_effects()
        self._setup_tray_icon()
        self.connect_signals()
        self._schedule_jobs()
        self._start_workers()

        # --- ADD THIS FINAL BLOCK OF CODE ---
        # It should be after all managers and the dashboard widget are initialized
        self.goal_oriented_worker = GoalOrientedWorker(
            settings_manager=self.settings_manager,
            memory_manager=self.memory_manager,
            llm_handler=self.action_manager.llm_handler,
            dashboard=self.dashboard_widget
        )
        # This is the final connection that brings the whole system to life
        if hasattr(self, 'task_context_worker'): # Check if task_context_worker was initialized
            self.task_context_worker.task_context_changed.connect(self.goal_oriented_worker.on_task_context_changed)
        # --- END OF FINAL BLOCK ---

        self.command_bar.show()
        logger.info("K.A.I.R.O.S. Main Window initialized successfully.")

    def _play_startup_sound(self):
        logger.info("Speaker is ready. Playing startup sound and finalizing sequence.")
        self.action_manager._speak("KAIROS systems are online.")
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
        btn_goals = QPushButton("Goals")  # <-- ADD THIS BUTTON
        nav_layout.addWidget(btn_dashboard)
        nav_layout.addWidget(btn_settings)
        nav_layout.addWidget(btn_analytics)
        nav_layout.addWidget(btn_goals)  # <-- ADD THIS BUTTON TO LAYOUT

        self.stacked_widget = QStackedWidget()
        self.dashboard_widget = DashboardWidget(self.settings_manager, self.db_manager)
        self.settings_widget = SettingsWidget(self.settings_manager)
        self.analytics_widget = AnalyticsWidget(self.db_manager)
        self.goals_widget = GoalsWidget(self.settings_manager)  # <-- INSTANTIATE WIDGET
        self.stacked_widget.addWidget(self.dashboard_widget)
        self.stacked_widget.addWidget(self.settings_widget)
        self.stacked_widget.addWidget(self.analytics_widget)
        self.stacked_widget.addWidget(self.goals_widget)  # <-- ADD WIDGET TO STACK
        
        main_layout.addWidget(nav_panel)
        main_layout.addWidget(self.stacked_widget)
        main_layout.setStretch(1, 1)

        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("K.A.I.R.O.S. Initialized and Ready.", 5000)
        
        btn_dashboard.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.dashboard_widget))
        btn_settings.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.settings_widget))
        btn_analytics.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.analytics_widget))
        btn_goals.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.goals_widget))  # <-- CONNECT BUTTON
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

    def _start_workers(self) -> None:
        logger.info("Starting worker threads...")
        self.discovery_worker = DiscoveryWorker()
        self.discovery_worker.start()
        
        self.api_server_worker = ServerWorker(self.action_manager)
        self.api_server_worker.start()
        
        self.clipboard_worker.start()
        
        self.video_worker = VideoWorker(self.settings_manager)
        self.video_worker.new_data.connect(self.dashboard_widget.update_video_feed)
        self.video_worker.gesture_detected.connect(self.handle_gesture)
        self.video_worker.error_occurred.connect(self.handle_system_message)
        self.video_worker.state_changed.connect(self.handle_gesture_state_change)
        self.video_worker.window_targeted.connect(self.set_targeted_window)
        self.video_worker.start()

        self.audio_worker.new_transcription_with_emotion.connect(self.handle_transcription)
        self.audio_worker.error_occurred.connect(self.handle_system_message)
        self.audio_worker.start()

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
        # Connect the new activity stats signal for flow state monitoring
        self.activity_logger_worker.activity_stats_updated.connect(
            lambda stats: logger.debug(f"Activity Stats: {stats}")
        )
        self.activity_logger_worker.start()
        
        # --- UPDATED FLOW STATE INTEGRATION BLOCK ---
        # 1. Start the input monitor
        self.input_monitor_worker = InputMonitorWorker()
        self.input_monitor_worker.start()
        
        # 2. Start the Flow State brain
        self.flow_state_worker = FlowStateWorker()
        
        # 3. Connect all data streams TO the FlowStateWorker
        self.input_monitor_worker.new_input_stats.connect(self.flow_state_worker.update_input_stats)
        self.activity_logger_worker.activity_stats_updated.connect(self.flow_state_worker.update_activity_stats)
        self.video_worker.video_stats_updated.connect(self.flow_state_worker.update_video_stats)
        
        # 4. Connect the final output FROM the FlowStateWorker to our handler
        self.flow_state_worker.flow_state_changed.connect(self.handle_flow_state_change)
        self.flow_state_worker.start()
        # --- END OF FLOW STATE INTEGRATION BLOCK ---

        # --- NEW BROWSER HISTORY WORKER INTEGRATION ---
        self.browser_history_worker = BrowserHistoryWorker(self.memory_manager)
        self.browser_history_worker.start()
        # --- END OF BROWSER HISTORY INTEGRATION ---

        # --- NEW TASK CONTEXT WORKER INTEGRATION ---
        self.task_context_worker = TaskContextWorker()
        self.activity_logger_worker.activity_logged.connect(self.task_context_worker.on_activity_logged)
        self.task_context_worker.task_context_changed.connect(self.handle_task_context_change)
        self.task_context_worker.start()
        # --- ADD THIS BLOCK ---
        self.heuristics_tuner = HeuristicsTuner(self.settings_manager, self.db_manager)
        self.heuristics_tuner.tuning_suggestion_ready.connect(self.handle_tuning_suggestion)
        self.heuristics_tuner.start()
        # --- END OF NEW BLOCK ---

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
        actions = suggestion.get("actions")  # Get the raw actions
        
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
            
            # --- FINAL LOGIC IMPLEMENTATION ---
            if actions:
                success = self.settings_manager.create_macro_from_suggestion(macro_name, actions)
                if success:
                    self.statusBar().showMessage(f"New command '{macro_name}' created successfully!", 5000)
                    self.action_manager._speak(f"Great. I've created the new command, {macro_name}.")
                    
                    # Log the successful macro creation
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
            # Announce that Guardian Mode is active
            self.action_manager._speak("Guardian mode activated. I'll keep you focused.")
            # TODO: Implement notification silencing logic here
        elif state == FlowState.IDLE:
            # Announce that Guardian Mode is off
            self.action_manager._speak("Guardian mode deactivated.")
            # TODO: Implement logic to restore notifications

    @Slot(str)
    def handle_task_context_change(self, context: str):
        """
        Handles the user's high-level task context changing.
        This will now trigger the generative UI.
        """
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        self.new_log_entry.emit(timestamp, "[BRAIN]", f"Context changed to {context}", "INFO", {})
        friendly_name = context.replace("TASK_", "").replace("_", " ").title()
        self.action_manager._speak(f"Reconfiguring for {friendly_name}.")
        
        # --- THIS IS THE NEW GENERATIVE UI LOGIC ---
        if not hasattr(self.action_manager, 'llm_handler') or not self.action_manager.llm_handler:
            logger.warning("LLM Handler not available, cannot generate new layout.")
            return
        
        # 1. Get the list of available widgets
        available_widget_keys = list(self.dashboard_widget.available_widgets.keys())
        
        # 2. Ask the LLM to generate a new layout
        new_layout = self.action_manager.llm_handler.generate_ui_layout(context, available_widget_keys)
        
        # 3. If the layout is valid, apply it to the dashboard
        if new_layout:
            self.dashboard_widget.update_layout(new_layout)
            logger.info(f"Applied AI-generated layout for context: {context}")
        else:
            logger.error("LLM failed to provide a valid layout. Dashboard remains unchanged.")
        # --- END OF NEW LOGIC ---

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
        logger.info(f"[GESTURE CONFIRMED] Received intent '{intent}' from VideoWorker. Executing action.")
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
            # Placeholder for actually executing the sequence
            self.pending_suggestion = None
            return
        if self.pending_suggestion: self.pending_suggestion = None

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
            self.action_manager.execute_action(intent, entities, emotion=emotion)
        
        if prompt:
            self.action_manager._speak(prompt)

    def _shutdown_application(self) -> None:
        logger.info("Shutdown signal received. Stopping all workers...")
        self.command_bar.close()

        workers = [
            self.video_worker, self.audio_worker, self.api_server_worker,
            self.speaker_worker, self.system_stats_worker, self.ocr_worker,
            self.activity_logger_worker, self.clipboard_worker, self.discovery_worker,
            self.input_monitor_worker, self.flow_state_worker,  # <-- ADDED BOTH WORKERS HERE
            self.browser_history_worker,  # <-- ADDED BROWSER HISTORY WORKER
            self.task_context_worker,  # <-- ADDED TASK CONTEXT WORKER
            self.heuristics_tuner  # <-- ADD THIS LINE
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
        self.command_bar.show()
        self.tray_icon.showMessage("K.A.I.R.O.S.", "Application is still running.", QSystemTrayIcon.MessageIcon.Information, 2000)