from pathlib import Path

import requests

url = "http://127.0.0.1:8000/upload-and-process"
file_path = Path(__file__).parent.parent / "sample_data.csv"

print(f"Posting {file_path} to {url}")
with open(file_path, "rb") as f:
    files = {"file": (file_path.name, f, "text/csv")}
    r = requests.post(url, files=files)
    try:
        print("Status:", r.status_code)
        print(r.json())
    except Exception:
        print("Response text:", r.text)
