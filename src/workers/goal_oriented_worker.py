# src/workers/goal_oriented_worker.py

import logging
from PySide6.QtCore import QObject, Slot

# Forward declarations for type hinting
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.settings_manager import SettingsManager
    from src.memory_manager import MemoryManager
    from src.llm_handler import LlmHandler
    from src.ui_components.dashboard_widget import DashboardWidget

logger = logging.getLogger(__name__)

class GoalOrientedWorker(QObject):
    """
    Orchestrates KAIROS systems to proactively assist with user-defined goals.
    This is an event-driven QObject, not a QThread, as it only needs to react to signals.
    """
    def __init__(self, settings_manager: "SettingsManager", memory_manager: "MemoryManager", 
                 llm_handler: "LlmHandler", dashboard: "DashboardWidget", parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.memory_manager = memory_manager
        self.llm_handler = llm_handler
        self.dashboard = dashboard
        self.active_goal_session = None

    @Slot(str)
    def on_task_context_changed(self, context: str):
        """
        Receives the user's current task context and decides if it aligns with a goal.
        """
        logger.info(f"Goal worker received new context: {context}")
        
        active_goals = [
            (name, goal) for name, goal in self.settings_manager.settings.goals.items() 
            if goal.status == "Active"
        ]

        matched_goal = None
        for name, goal in active_goals:
            # Simple matching: check if any goal keyword is in the context name
            for keyword in goal.keywords:
                if keyword in context.lower():
                    matched_goal = goal
                    break
            if matched_goal:
                break
        
        if matched_goal:
            # A goal-oriented session is active
            if self.active_goal_session != matched_goal.name:
                self.active_goal_session = matched_goal.name
                logger.info(f"User is now working on goal: '{matched_goal.name}'")
                self._activate_goal_mode(matched_goal)
        else:
            # No goal is active, return to default mode
            if self.active_goal_session is not None:
                self.active_goal_session = None
                logger.info("User is no longer working on a defined goal. Returning to default mode.")
                # We can trigger a "default" layout regeneration here if desired
                # For now, we'll just let the user's manual navigation take over.

    def _activate_goal_mode(self, goal):
        """Orchestrates KAIROS systems to assist with the active goal."""
        # 1. Query the Nexus for relevant memories
        memories = self.memory_manager.query_memory(
            query_text=f"Information related to my goal: {goal.name} ({', '.join(goal.keywords)})",
            n_results=5
        )

        # 2. Ask the Composer to generate a goal-oriented UI
        available_widgets = list(self.dashboard.available_widgets.keys())
        new_layout = self.llm_handler.generate_ui_layout(
            task_context=self.active_goal_session, 
            available_widgets=available_widgets,
            goal_info=goal.model_dump()
        )

        # 3. Apply the new layout
        if new_layout:
            self.dashboard.update_layout(new_layout)
            
            # 4. Populate the smart widget with our retrieved memories
            # We need to wait a moment for the UI to update before finding the widget
            QTimer.singleShot(100, lambda: self._populate_goal_widget(memories))

    def _populate_goal_widget(self, memories):
        """Finds the GoalMemoryWidget in the new layout and gives it the data."""
        if 'GOAL_MEMORY' in self.dashboard.loaded_widgets:
            memory_widget = self.dashboard.loaded_widgets['GOAL_MEMORY']
            if memory_widget and hasattr(memory_widget, 'populate_memories'):
                memory_widget.populate_memories(memories)
                logger.info("Successfully populated Goal Memory widget.")