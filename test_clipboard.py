# test_clipboard.py

import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

def get_pc_clipboard():
    """Sends a GET request to fetch the PC's clipboard content."""
    try:
        response = requests.get(f"{BASE_URL}/clipboard", timeout=5)
        response.raise_for_status()
        data = response.json()
        print("--- PC Clipboard Content ---")
        print(data.get("content", "No content found."))
        print("----------------------------")
    except requests.exceptions.RequestException as e:
        print(f"Error: Could not connect to K.A.I.R.O.S. server. Is it running? Details: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def set_pc_clipboard(text_to_set: str):
    """Sends a POST request to set the PC's clipboard content."""
    try:
        payload = {"content": text_to_set}
        response = requests.post(f"{BASE_URL}/clipboard", json=payload, timeout=5)
        response.raise_for_status()
        print("Success! PC clipboard has been updated.")
        print("Try pasting somewhere to confirm.")
    except requests.exceptions.RequestException as e:
        print(f"Error: Could not connect to K.A.I.R.O.S. server. Is it running? Details: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_clipboard.py get          # To get the PC's clipboard")
        print("  python test_clipboard.py set \"Hello\" # To set the PC's clipboard")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "get":
        get_pc_clipboard()
    elif command == "set":
        if len(sys.argv) < 3:
            print("Error: 'set' command requires text. Example: python test_clipboard.py set \"My Text\"")
        else:
            content = " ".join(sys.argv[2:])
            set_pc_clipboard(content)
    else:
        print(f"Error: Unknown command '{command}'. Use 'get' or 'set'.")