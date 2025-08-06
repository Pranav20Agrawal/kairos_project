# src/plugin_interface.py

from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BasePlugin(ABC):
    """
    The abstract base class for all K.A.I.R.O.S. plugins.

    Each plugin must inherit from this class and implement the required
    properties and methods.
    """

    def __init__(self, speaker_worker=None):
        """
        The constructor for the plugin.
        It receives an instance of the SpeakerWorker to provide auditory feedback.
        """
        self.speaker_worker = speaker_worker

    @property
    @abstractmethod
    def intents_to_register(self) -> List[str]:
        """
        A list of intent names (e.g., '[DO_SOMETHING]') that this plugin handles.
        These names must match the intents defined in config.json.
        """
        pass

    @abstractmethod
    def execute(self, intent: str, entities: Dict[str, Any] | None) -> None:
        """
        The main execution method for the plugin. This is called by the
        ActionManager when one of the plugin's registered intents is triggered.

        Args:
            intent: The name of the intent that was triggered.
            entities: Any entities extracted by the NLU engine.
        """
        pass

    def _speak(self, text: str):
        """A helper method to easily use the text-to-speech engine."""
        if self.speaker_worker:
            self.speaker_worker.speak(text)
        else:
            print(f"[Plugin Fallback TTS]: {text}")