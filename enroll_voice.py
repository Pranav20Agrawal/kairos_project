# enroll_voice.py

import sounddevice as sd
import numpy as np
import os
import json
from pathlib import Path
from scipy.io.wavfile import write
import logging

# --- MODIFIED: Use torchaudio directly to load the audio, bypassing torch.hub ---
import torchaudio
# -------------------------------------------------------------------------------

# Setup basic logging for the script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    import torch
    from speechbrain.pretrained import EncoderClassifier
except ImportError:
    print("\n--- ERROR ---")
    print("Required libraries (torch, speechbrain) are not installed.")
    print("Please make sure you have installed all dependencies from requirements.txt in your virtual environment.")
    exit()

# --- Configuration ---
SAMPLE_RATE = 16000     # 16kHz, standard for speech models
RECORDING_DURATION = 4  # 4 seconds per phrase
VOICEPRINT_PATH = Path("voiceprint.npy")
TEMP_WAV_PATH = Path("enrollment_temp.wav")
CONFIG_PATH = Path("config.json")

PHRASES = [
    "The quick brown fox jumps over the lazy dog.",
    "Never underestimate the power of a well-structured plan.",
    "Artificial intelligence is rapidly changing our world.",
    "Houston, we have a solution.",
    "Kairos, initialize all systems."
]

def update_config_file():
    """Sets the setup_complete flag in config.json to True."""
    if not CONFIG_PATH.exists():
        logging.warning(f"'{CONFIG_PATH}' not found. Cannot update setup status.")
        return

    try:
        with open(CONFIG_PATH, 'r') as f:
            config_data = json.load(f)

        if 'core' in config_data:
            config_data['core']['setup_complete'] = True
        else:
            logging.warning("Config file is missing the 'core' section. Cannot update setup status.")
            return

        with open(CONFIG_PATH, 'w') as f:
            json.dump(config_data, f, indent=4)
        logging.info(f"Successfully updated '{CONFIG_PATH}' to mark setup as complete.")
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Failed to read or write to '{CONFIG_PATH}': {e}")


def main():
    """Main function to guide the user through voice enrollment."""
    print("="*50)
    print(" K.A.I.R.O.S. Voice Enrollment Utility")
    print("="*50)
    print("You will be asked to read 5 phrases to create your unique voiceprint.")
    print("Please ensure you are in a quiet environment.")
    print("\nPress Enter when you are ready to begin...")
    input()

    recorded_audio = []

    # 1. Record Audio
    for i, phrase in enumerate(PHRASES):
        print(f"\n--- Phrase {i+1}/{len(PHRASES)} ---")
        print(f"Please read the following sentence clearly:")
        print(f"  '{phrase}'")
        print("\nPress Enter to start recording...")
        input()

        try:
            print("Recording for 4 seconds... Speak now!")
            audio_chunk = sd.rec(int(RECORDING_DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype='float32')
            sd.wait()
            recorded_audio.append(audio_chunk)
            print("Recording finished.")
        except sd.PortAudioError:
            logging.critical("No microphone found! Please ensure a microphone is connected and configured.")
            return

    # 2. Process and Save Audio
    logging.info("All phrases recorded. Processing audio...")
    full_recording = np.concatenate(recorded_audio)

    # Normalize and convert to int16 for WAV file
    scaled_recording = np.int16(full_recording / np.max(np.abs(full_recording)) * 32767)
    write(TEMP_WAV_PATH, SAMPLE_RATE, scaled_recording)
    logging.info(f"Temporary audio saved to '{TEMP_WAV_PATH}'.")

    # 3. Generate Voiceprint
    try:
        logging.info("Loading speaker verification model (this may take a moment)...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        classifier = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir="pretrained_models/spkrec-ecapa-voxceleb",
            run_opts={"device": device}
        )

        logging.info("Generating voiceprint embedding...")

        # --- MODIFIED: Use torchaudio to load audio, it's more robust on Windows ---
        signal, fs = torchaudio.load(str(TEMP_WAV_PATH))
        # Resample if needed (though we're already recording at 16k)
        # if fs != SAMPLE_RATE:
        #     signal = torchaudio.transforms.Resample(orig_freq=fs, new_freq=SAMPLE_RATE)(signal)
        # --------------------------------------------------------------------------

        embedding = classifier.encode_batch(signal)
        embedding_numpy = embedding.squeeze().cpu().numpy()

        np.save(VOICEPRINT_PATH, embedding_numpy)
        logging.info(f"Voiceprint successfully saved to '{VOICEPRINT_PATH}'!")

        # 4. Update config file
        update_config_file()

        print("\n" + "="*50)
        print(" ✅ Enrollment Complete!")
        print(" You can now launch the main K.A.I.R.O.S. application.")
        print("="*50)

    except Exception as e:
        logging.critical(f"An error occurred during voiceprint generation: {e}", exc_info=True)
    finally:
        # 5. Cleanup
        if os.path.exists(TEMP_WAV_PATH):
            os.remove(TEMP_WAV_PATH)
            logging.info(f"Cleaned up temporary file: '{TEMP_WAV_PATH}'.")

if __name__ == "__main__":
    main()