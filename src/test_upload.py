# test_upload.py
import requests

url = "http://127.0.0.1:8000/upload_file"
file_path = "test.txt"

try:
    with open(file_path, "rb") as f:
        files = {"file": (file_path, f, "text/plain")}
        response = requests.post(url, files=files)
    
    if response.status_code == 200:
        print("Success! File uploaded.")
        print(response.json())
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
except requests.exceptions.ConnectionError as e:
    print(f"Connection Error: Is the K.A.I.R.O.S. application running? Details: {e}")