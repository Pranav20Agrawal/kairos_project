# src/models.py

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class CoreSettings(BaseModel):
    camera_index: int = Field(0, ge=0, description="The index of the camera to use (0 is default).")
    fist_threshold: float = Field(0.08, ge=0.0, le=1.0, description="Sensitivity for fist gesture detection.")
    open_palm_threshold: float = Field(0.20, ge=0.0, le=1.0, description="Sensitivity for open palm gesture detection.")
    silence_duration: float = Field(2.0, ge=0.5, le=10.0, description="Seconds of silence to end a voice command.")
    silence_threshold: int = Field(350, ge=0, description="Audio RMS level to be considered silence. (Overridden by auto-calibration)")
    # <--- MODIFICATION START --->
    silence_threshold_multiplier: float = Field(2.5, ge=1.0, le=10.0, description="Multiplier for auto-calibrated silence threshold.")
    speaker_verification_threshold: float = Field(0.55, ge=0.0, le=1.0, description="Similarity score required to verify the user's voice (0.0 to 1.0).")
    # <--- MODIFICATION END --->
    daily_briefing_time: str = Field("07:00", pattern=r"^\d{2}:\d{2}$", description="HH:MM time for the daily briefing.")
    setup_complete: bool = Field(False, description="Flag to indicate if the first-time setup has been completed.")
    paranoid_mode_enabled: bool = Field(False, description="If true, all high-risk intents are disabled.")
    update_checker_url: Optional[str] = Field(
        None, 
        description="URL to the raw version.txt file for update checks."
    )

class Intent(BaseModel):
    keywords: List[str] = []
    canonical: str = ""
    triggers: List[str] = []
    contexts: List[str] = Field([], description="A list of process names where this intent is active (e.g., ['chrome.exe']). Empty means global.")
    starts_conversation: bool = Field(False, description="True if this intent starts a multi-step dialogue.")
    initial_prompt: Optional[str] = Field(None, description="The first question K.A.I.R.O.S. should ask.")
    conversation_state: Optional[str] = Field(None, description="The state the NLU enters after this intent.")
    is_high_risk: bool = Field(False, description="True if this intent performs high-risk actions like file access or web automation.")

class MacroStep(BaseModel):
    action: str
    param: str

class ThemeSettings(BaseModel):
    primary_color: str = Field("#4a90e2", description="The main accent color for highlights and borders.")
    secondary_color: str = Field("#50e3c2", description="The secondary accent color for interactive elements like sliders.")

class WidgetConfig(BaseModel):
    name: str = Field(description="Display name for the widget.")
    enabled: bool = Field(True, description="Whether the widget is visible on the dashboard.")
    row: int = Field(description="Grid row for the widget.")
    col: int = Field(description="Grid column for the widget.")
    row_span: int = Field(1, description="Number of rows the widget should span.")
    col_span: int = Field(1, description="Number of columns the widget should span.")

class DashboardSettings(BaseModel):
    widgets: Dict[str, WidgetConfig] = Field(default_factory=lambda: {
        "VIDEO_FEED": WidgetConfig(name="Video Feed", enabled=True, row=0, col=0, row_span=1, col_span=2),
        "SYSTEM_STATS": WidgetConfig(name="System Monitor", enabled=True, row=1, col=0, row_span=1, col_span=1),
        "COMMAND_LOG": WidgetConfig(name="Command Log", enabled=True, row=1, col=1, row_span=2, col_span=1),
        "WEATHER": WidgetConfig(name="Weather", enabled=False, row=2, col=0, row_span=1, col_span=1)
    })

class SettingsModel(BaseModel):
    core: CoreSettings = Field(default_factory=CoreSettings)
    theme: ThemeSettings = Field(default_factory=ThemeSettings)
    dashboard: DashboardSettings = Field(default_factory=DashboardSettings)
    intents: Dict[str, Intent] = Field(default_factory=dict)
    sites: Dict[str, str] = Field(default_factory=dict)
    macros: Dict[str, List[MacroStep]] = Field(default_factory=dict)