# test_transfer_speed.py
import requests
import time
import os

# --- Configuration ---
URL = "http://127.0.0.1:8000/upload_file"
FILE_NAME = "dummy_test_file.bin"
FILE_SIZE_MB = 10  # We'll create a 10 MB file for the test


def create_dummy_file():
    """Creates a binary file of a specified size."""
    print(f"Creating a {FILE_SIZE_MB} MB dummy file for testing...")
    with open(FILE_NAME, "wb") as f:
        f.write(os.urandom(FILE_SIZE_MB * 1024 * 1024))
    print(f"'{FILE_NAME}' created successfully.")


def test_upload_speed():
    """Uploads the file and measures the transfer speed."""
    try:
        with open(FILE_NAME, "rb") as f:
            files = {"file": (FILE_NAME, f)}

            print("\nStarting upload test...")
            start_time = time.perf_counter()

            response = requests.post(URL, files=files, timeout=30)  # 30-second timeout

            end_time = time.perf_counter()

        if response.status_code == 200:
            duration = end_time - start_time
            speed_mbps = FILE_SIZE_MB / duration

            print("\n--- Results ---")
            print(f"File Size: {FILE_SIZE_MB} MB")
            print(f"Upload Time: {duration:.2f} seconds")
            print(f"Transfer Speed: {speed_mbps:.2f} MB/s")
        else:
            print(f"Error: Server responded with status {response.status_code}")
            print(response.text)

    except requests.exceptions.RequestException as e:
        print(f"\nConnection Error: Is the K.A.I.R.O.S. application running? Details: {e}")
    finally:
        # Clean up the dummy file
        if os.path.exists(FILE_NAME):
            os.remove(FILE_NAME)
            print(f"\nCleaned up '{FILE_NAME}'.")


if __name__ == "__main__":
    create_dummy_file()
    test_upload_speed()