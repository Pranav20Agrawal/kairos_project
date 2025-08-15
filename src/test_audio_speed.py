import time
import whisper
import torch

MODEL_NAME = "small.en" # The model you use in the app
AUDIO_FILE = "test_audio.wav" # The audio file you just recorded

def test_transcription_speed():
    print(f"--- Testing Transcription Latency with Whisper '{MODEL_NAME}' ---")
    
    try:
        # Check for CUDA availability
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {device.upper()}")

        # 1. Time the model loading
        start_time = time.perf_counter()
        model = whisper.load_model(MODEL_NAME, device=device)
        end_time = time.perf_counter()
        print(f"Model load time: {end_time - start_time:.2f} seconds")

        # 2. Time the transcription itself
        print(f"\nTranscribing '{AUDIO_FILE}'...")
        start_time = time.perf_counter()
        result = model.transcribe(AUDIO_FILE, fp16=torch.cuda.is_available())
        end_time = time.perf_counter()
        
        latency = end_time - start_time
        
        print("\n--- Results ---")
        print(f"Transcription: '{result['text'].strip()}'")
        print(f"Transcription Latency: {latency:.2f} seconds")

    except FileNotFoundError:
        print(f"\nERROR: The audio file '{AUDIO_FILE}' was not found.")
        print("Please record a short .wav file and save it in the project directory.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    test_transcription_speed()