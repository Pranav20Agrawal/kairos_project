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

try:
    from speechbrain.inference.interfaces import foreign_class
    SPEECHBRAIN_AVAILABLE = True
except ImportError:
    SPEECHBRAIN_AVAILABLE = False
    foreign_class = None

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
        self.get_speech_timestamps = None

    def load_models(self) -> bool:
        """Loads all necessary AI models for the audio worker."""
        try:
            if not os.path.exists("voiceprint.npy"):
                self.error_occurred.emit("User voiceprint not found. Please run the enrollment script.", "CRITICAL")
                return False
            self.user_voiceprint = np.load("voiceprint.npy")
            logger.info("User voiceprint loaded successfully.")

            logger.info("Loading Whisper model...")
            self.whisper_model = whisper.load_model("small.en")
            logger.info("Whisper model loaded successfully.")

            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {device} for audio models.")

            if not SPEECHBRAIN_AVAILABLE:
                raise ImportError("SpeechBrain library is not installed.")

            logger.info("Loading speaker verification model...")
            self.embedding_model = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir="pretrained_models/spkrec-ecapa-voxceleb",
                run_opts={"device": device},
            )
            logger.info("Speaker verification model loaded.")

            try:
                logger.info("Loading emotion recognition model...")
                self.emotion_model = foreign_class(
                    source="speechbrain/emotion-recognition-wav2vec2-IEMOCAP",
                    pyf_file="custom.py",
                    savedir="pretrained_models/emotion-recognition-wav2vec2-IEMOCAP",
                    run_opts={"device": device}
                )
                logger.info("Emotion recognition model loaded successfully.")
            except Exception as e:
                logger.warning(f"Could not load emotion recognition model: {e}. Emotion detection will be disabled.")
                self.emotion_model = None

            logger.info("Loading Silero VAD model...")
            self.vad_model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad', model='silero_vad', force_reload=False, onnx=False
            )
            (self.get_speech_timestamps, _, _, _, _) = utils
            logger.info("Silero VAD model loaded.")
            
            return True

        except Exception as e:
            msg = "A critical error occurred while loading AI models for audio."
            logger.critical(f"{msg}: {e}", exc_info=True)
            self.error_occurred.emit(f"{msg}\n\nDetails: {e}", "CRITICAL")
            return False

    def is_user_speaking(self, audio_data_tensor: torch.Tensor) -> bool:
        """Verifies if the provided audio tensor matches the user's voiceprint."""
        if self.embedding_model is None or self.user_voiceprint is None: return False

        try:
            with torch.no_grad():
                # --- FIX APPLIED HERE ---
                # The model expects a 2D tensor of shape [batch, samples].
                # We ensure it has this shape before passing it to the model.
                if audio_data_tensor.ndim == 1:
                    audio_data_tensor = audio_data_tensor.unsqueeze(0)
                
                embedding = self.embedding_model.encode_batch(audio_data_tensor)
                embedding_numpy = embedding.squeeze().cpu().numpy()

            similarity = 1 - cosine(embedding_numpy, self.user_voiceprint)
            verification_threshold = self.settings_manager.settings.core.speaker_verification_threshold
            logger.info(f"DIAGNOSTIC: Speaker verification similarity: {similarity:.2f} (Threshold: {verification_threshold})")
            
            return similarity > verification_threshold

        except Exception as e:
            logger.error(f"Failed during speaker verification: {e}", exc_info=True)
            return False

    def detect_speech_with_vad(self, audio_tensor: torch.Tensor, sample_rate: int) -> List[Dict[str, int]]:
        """Use Silero VAD to detect speech segments."""
        if not callable(self.get_speech_timestamps):
            return [{'start': 0, 'end': len(audio_tensor)}]
        try:
            # --- FIX APPLIED HERE ---
            # The VAD model expects a 1D tensor. We ensure it's flattened.
            if audio_tensor.ndim > 1:
                audio_tensor = audio_tensor.flatten()
            return self.get_speech_timestamps(audio_tensor, self.vad_model, sampling_rate=sample_rate)
        except Exception as e:
            logger.error(f"VAD processing failed: {e}")
            return [{'start': 0, 'end': len(audio_tensor)}]

    def run(self) -> None:
        if not self.load_models(): return

        RATE = 16000
        CHUNK = 1024
        
        is_recording = False
        recorded_frames = []
        silent_chunks = 0

        try:
            with sd.InputStream(samplerate=RATE, channels=1, blocksize=CHUNK, dtype="int16") as stream:
                logger.info("Calibrating silence threshold for 2 seconds... Please be quiet.")
                calibration_frames = []
                num_calibration_chunks = int((RATE * 2) / CHUNK)
                
                for _ in range(num_calibration_chunks):
                    audio_chunk, _ = stream.read(CHUNK)
                    calibration_frames.append(np.sqrt(np.mean(audio_chunk.astype(float) ** 2)))
                
                ambient_noise_level = np.mean(calibration_frames)
                multiplier = self.settings_manager.settings.core.silence_threshold_multiplier
                calibrated_threshold = ambient_noise_level * multiplier
                
                logger.info(f"Calibration complete. Ambient noise: {ambient_noise_level:.2f}. Dynamic silence threshold set to: {calibrated_threshold:.2f}")

                logger.info("AudioWorker is now listening...")
                while self.running:
                    silence_duration = self.settings_manager.settings.core.silence_duration
                    num_silent_chunks_to_end = int(silence_duration * (RATE / CHUNK))

                    audio_chunk, overflowed = stream.read(CHUNK)
                    if overflowed: logger.warning("Audio buffer overflowed.")

                    rms = np.sqrt(np.mean(audio_chunk.astype(float) ** 2))
                    is_speech = rms > calibrated_threshold
                    
                    if is_speech and not is_recording:
                        is_recording = True
                        logger.info(f"Voice activity detected (RMS: {rms:.2f}). Starting recording...")
                        recorded_frames.clear()
                        silent_chunks = 0
                    
                    if is_recording:
                        recorded_frames.append(audio_chunk)
                        if not is_speech:
                            silent_chunks += 1
                        else:
                            silent_chunks = 0
                        
                        if silent_chunks > num_silent_chunks_to_end:
                            logger.info("Recording finished due to silence. Processing audio...")
                            recording_np = np.concatenate(recorded_frames)
                            
                            audio_float32 = recording_np.astype(np.float32) / 32768.0
                            audio_tensor = torch.from_numpy(audio_float32)
                            
                            speech_timestamps = self.detect_speech_with_vad(audio_tensor, RATE)

                            if not speech_timestamps:
                                logger.warning("VAD found no speech. Discarding.")
                            else:
                                start, end = speech_timestamps[0]['start'], speech_timestamps[-1]['end']
                                # --- FIX APPLIED HERE ---
                                # Ensure we are slicing a flattened array to get a 1D result
                                clean_audio_segment = audio_float32.flatten()[start:end]
                                clean_audio_tensor = torch.from_numpy(clean_audio_segment)

                                if self.is_user_speaking(clean_audio_tensor):
                                    logger.info("User verified. Transcribing command...")
                                    temp_file = "transcribe_temp.wav"
                                    # Use the clean audio segment for transcription as well
                                    write(temp_file, RATE, (clean_audio_segment * 32767).astype(np.int16))
                                    result = self.whisper_model.transcribe(temp_file, fp16=torch.cuda.is_available())
                                    text: str = result["text"].strip()
                                    os.remove(temp_file)
                                    
                                    if text:
                                        logger.info(f"Transcription result: '{text}'")
                                        self.new_transcription_with_emotion.emit(text, "neu")
                                else:
                                    logger.warning("Speaker not verified. Discarding audio.")
                            
                            is_recording = False
                            
        except Exception as e:
            msg = "A critical audio error occurred in the audio stream loop."
            logger.error(f"{msg}: {e}", exc_info=True)
            self.error_occurred.emit(f"{msg}\nIs a microphone connected?", "CRITICAL")

    def stop(self) -> None:
        self.running = False
        logger.info("AudioWorker stop signal received.")