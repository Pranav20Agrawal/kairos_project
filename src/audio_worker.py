# src/audio_worker.py

import os
import time
import numpy as np
import sounddevice as sd
import whisper
from scipy.io.wavfile import write
from PySide6.QtCore import QThread, Signal, QObject
from src.settings_manager import SettingsManager
import logging
import torch
import torchaudio
from speechbrain.inference.speaker import EncoderClassifier
from scipy.spatial.distance import cosine
from typing import List, Dict, Any

# --- MODIFIED: Correctly import foreign_class for the emotion model ---
from speechbrain.inference.interfaces import foreign_class
# ----------------------------------------------------------------------


logger = logging.getLogger(__name__)


class AudioWorker(QThread):
    new_transcription_with_emotion = Signal(str, str)
    error_occurred = Signal(str, str)

    def __init__(
        self, settings_manager: SettingsManager, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.running = True
        self.whisper_model = None
        self.embedding_model = None
        self.emotion_model = None
        self.vad_model = None
        self.user_voiceprint = None
        self.get_speech_timestamps = None # Initialize this as None

    def load_models(self) -> bool:
        """Loads all necessary AI models for the audio worker."""
        try:
            # Load User Voiceprint
            if not os.path.exists("voiceprint.npy"):
                logger.error("voiceprint.npy not found. Please run enroll_voice.py first.")
                self.error_occurred.emit("User voiceprint not found. Please run the enrollment script.", "CRITICAL")
                return False
            self.user_voiceprint = np.load("voiceprint.npy")
            logger.info("User voiceprint loaded successfully.")

            # Load Whisper Model
            logger.info("Loading Whisper model...")
            self.whisper_model = whisper.load_model("small.en")
            logger.info("Whisper model loaded successfully.")

            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {device} for audio models.")

            # Load Speaker Verification Model
            logger.info("Loading speaker verification model...")
            self.embedding_model = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir="pretrained_models/spkrec-ecapa-voxceleb",
                run_opts={"device": device},
            )
            logger.info("Speaker verification model loaded.")

            # --- MODIFIED: Correct way to load the emotion model ---
            logger.info("Loading emotion recognition model...")
            self.emotion_model = foreign_class(
                source="speechbrain/emotion-recognition-wav2vec2-IEMOCAP",
                pyf_file="custom.py",  # custom.py is needed for this specific model
                savedir="pretrained_models/emotion-recognition-wav2vec2-IEMOCAP",
                run_opts={"device": device}
            )
            logger.info("Emotion recognition model loaded.")
            # --- END MODIFIED ---

            # Load Silero VAD Model
            logger.info("Loading Silero VAD model...")
            try:
                self.vad_model, utils = torch.hub.load(
                    repo_or_dir='snakers4/silero-vad',
                    model='silero_vad',
                    force_reload=False,
                    onnx=False
                )
                self.get_speech_timestamps = utils[0]
                logger.info("Silero VAD model loaded.")
            except Exception as e:
                logger.warning(f"Failed to load Silero VAD model: {e}")
                logger.info("Continuing without VAD - will use simple audio detection.")
                self.vad_model = None

            return True

        except Exception as e:
            msg = "A critical error occurred while loading AI models for audio."
            logger.critical(f"{msg}: {e}", exc_info=True)
            # <--- MODIFICATION: Include the specific exception in the error message --->
            detailed_msg = f"{msg}\n\nDetails: {e}"
            self.error_occurred.emit(detailed_msg, "CRITICAL")
            # <--- END MODIFICATION --->
            return False

    def is_user_speaking(self, audio_data_tensor: torch.Tensor) -> bool:
        """Verifies if the provided audio tensor matches the user's voiceprint."""
        if self.embedding_model is None or self.user_voiceprint is None:
            return False

        try:
            with torch.no_grad():
                embedding = self.embedding_model.encode_batch(audio_data_tensor)
                embedding_numpy = embedding.squeeze().cpu().numpy()

            similarity = 1 - cosine(embedding_numpy, self.user_voiceprint)
            VERIFICATION_THRESHOLD = 0.60  # This may need tuning
            logger.debug(f"Speaker verification similarity: {similarity:.2f}")

            return similarity > VERIFICATION_THRESHOLD

        except Exception as e:
            logger.error(f"Failed during speaker verification: {e}", exc_info=True)
            return False

    def detect_speech_with_vad(self, audio_tensor: torch.Tensor, sample_rate: int) -> List[Dict[str, int]]:
        """Use Silero VAD to detect speech segments, with fallback if VAD is not available."""
        if self.vad_model is None or not hasattr(self, 'get_speech_timestamps'):
            return [{'start': 0, 'end': len(audio_tensor)}]
        
        try:
            speech_timestamps = self.get_speech_timestamps(audio_tensor, self.vad_model, sampling_rate=sample_rate)
            return speech_timestamps
        except Exception as e:
            logger.error(f"VAD processing failed: {e}")
            return [{'start': 0, 'end': len(audio_tensor)}]

    def run(self) -> None:
        if not self.load_models():
            return

        RATE = 16000
        CHUNK = 1024
        settings = self.settings_manager.settings.core
        
        is_recording = False
        recorded_frames = []
        silent_chunks = 0

        try:
            with sd.InputStream(
                samplerate=RATE, channels=1, blocksize=CHUNK, dtype="int16"
            ) as stream:
                logger.info("AudioWorker is now listening for verified user...")
                while self.running:
                    silence_duration = settings.silence_duration
                    silence_threshold = settings.silence_threshold
                    num_silent_chunks_to_end = int(silence_duration * (RATE / CHUNK))

                    audio_chunk, overflowed = stream.read(CHUNK)
                    if overflowed:
                        logger.warning("Audio buffer overflowed.")

                    rms = np.sqrt(np.mean(audio_chunk.astype(float) ** 2))

                    if rms > silence_threshold:
                        if not is_recording:
                            is_recording = True
                            logger.info("Voice activity detected. Starting recording...")
                        silent_chunks = 0
                    elif is_recording:
                        silent_chunks += 1

                    if is_recording:
                        recorded_frames.append(audio_chunk)
                        
                        if silent_chunks > num_silent_chunks_to_end:
                            logger.info("Recording finished. Processing audio...")
                            recording_np = np.concatenate(recorded_frames)
                            
                            audio_float32 = recording_np.astype(np.float32) / 32768.0
                            audio_tensor = torch.from_numpy(audio_float32)
                            
                            speech_timestamps = self.detect_speech_with_vad(audio_tensor, RATE)

                            if not speech_timestamps:
                                logger.info("VAD found no speech in the recording. Discarding.")
                            else:
                                # MODIFIED: Use the start of the first segment and the end of the last segment
                                start, end = speech_timestamps[0]['start'], speech_timestamps[-1]['end']
                                logger.info(f"VAD found speech from sample {start} to {end}.")
                                
                                clean_audio_np = recording_np[start:end]
                                clean_audio_float32 = clean_audio_np.astype(np.float32) / 32768.0
                                clean_audio_tensor = torch.from_numpy(clean_audio_float32).unsqueeze(0)

                                if self.is_user_speaking(clean_audio_tensor):
                                    logger.info("User verified. Analyzing emotion and transcribing command...")
                                    
                                    emotion_label = "unknown"
                                    try:
                                        with torch.no_grad():
                                            prediction = self.emotion_model.classify_batch(clean_audio_tensor)
                                            # The output format is (prob, index, label_str)
                                            emotion_label = prediction[3][0]
                                            logger.info(f"Emotion detected: {emotion_label}")
                                    except Exception as e:
                                        logger.error(f"Could not determine emotion: {e}", exc_info=True)

                                    temp_file = "transcribe_temp.wav"
                                    write(temp_file, RATE, clean_audio_np)
                                    result = self.whisper_model.transcribe(temp_file, fp16=torch.cuda.is_available())
                                    text: str = result["text"].strip()
                                    os.remove(temp_file)
                                    
                                    if text:
                                        logger.info(f"Transcription result: '{text}'")
                                        self.new_transcription_with_emotion.emit(text, emotion_label)
                                else:
                                    logger.info("Speaker not verified. Discarding audio.")
                            
                            is_recording = False
                            recorded_frames = []
                            silent_chunks = 0
        except Exception as e:
            msg = "A critical audio error occurred in the audio stream loop."
            logger.error(f"{msg}: {e}", exc_info=True)
            self.error_occurred.emit(msg, "CRITICAL")

    def stop(self) -> None:
        """Stops the thread gracefully."""
        self.running = False
        logger.info("AudioWorker stop signal received.")