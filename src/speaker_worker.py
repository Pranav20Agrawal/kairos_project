# src/speaker_worker.py

import logging
import queue
import torch
import sounddevice as sd
import soundfile as sf
import os
from pathlib import Path
from PySide6.QtCore import QThread, QObject

# <--- MODIFICATION START --->
# Set environment variable BEFORE importing TTS.
# This programmatically agrees to the Coqui TTS license to avoid the input() prompt.
os.environ["COQUI_TOS_AGREED"] = "1"
# <--- MODIFICATION END --->

logger = logging.getLogger(__name__)

# A flag to conditionally import and use TTS
try:
    from TTS.api import TTS
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    logger.warning("TTS library not found. SpeakerWorker will be disabled.")
    # Define a dummy class if TTS is not available to avoid NameErrors
    class TTS:
        def __init__(self, *args, **kwargs):
            pass
        def tts_to_file(self, *args, **kwargs):
            logger.error("TTS is not installed, cannot synthesize speech.")

class SpeakerWorker(QThread):
    """A dedicated worker thread for handling Text-to-Speech synthesis."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.text_queue = queue.Queue()
        self.running = True
        self.tts_model: TTS | None = None
        self.model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
        self.output_wav_path = Path("temp_speech.wav")

    def speak(self, text: str) -> None:
        """Adds text to the queue to be spoken by the worker."""
        if not TTS_AVAILABLE or not self.running:
            return
        self.text_queue.put(text)

    def _load_model(self) -> bool:
        """Loads the TTS model. This is a slow operation."""
        if not TTS_AVAILABLE:
            return False
            
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Initializing TTS model on device: {device}")
            # The model will be downloaded on the first run
            self.tts_model = TTS(self.model_name, gpu=(device == "cuda"))
            logger.info("TTS model loaded successfully.")
            return True
        except Exception as e:
            logger.critical(f"Failed to load TTS model: {e}", exc_info=True)
            self._cleanup()
            return False

    def run(self) -> None:
        """The main loop for the worker thread."""
        if not self._load_model():
            logger.error("Could not load TTS model. SpeakerWorker is shutting down.")
            return

        while self.running:
            try:
                # This will block until a text item is available
                text = self.text_queue.get()
                
                # A None in the queue is our signal to exit gracefully
                if text is None:
                    break

                if self.tts_model:
                    logger.info(f"Synthesizing speech for: '{text}'")
                    # Synthesize speech and save to a temporary file
                    self.tts_model.tts_to_file(
                        text=text, 
                        speaker="Ana Florence", # A high-quality default voice
                        language="en", 
                        file_path=str(self.output_wav_path)
                    )
                    
                    # Play the generated audio file
                    data, samplerate = sf.read(self.output_wav_path, dtype='float32')
                    sd.play(data, samplerate)
                    sd.wait() # Wait for the playback to finish

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in SpeakerWorker run loop: {e}", exc_info=True)
            finally:
                self._cleanup()
    
    def _cleanup(self) -> None:
        """Removes the temporary audio file if it exists."""
        if self.output_wav_path.exists():
            try:
                os.remove(self.output_wav_path)
            except OSError as e:
                logger.error(f"Error removing temp audio file: {e}")

    def stop(self) -> None:
        """Stops the worker thread gracefully."""
        self.running = False
        self.text_queue.put(None) # Unblock the queue.get()
        logger.info("SpeakerWorker stop signal sent.")