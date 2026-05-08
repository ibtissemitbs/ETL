from pathlib import Path

import requests


API_URL = "http://127.0.0.1:8000/upload-and-process?domain_override=sales"
SAMPLE_PATH = Path(__file__).resolve().parent.parent / "examples" / "sample_sales.csv"


def main() -> None:
    print(f"Posting {SAMPLE_PATH} to {API_URL}")
    with SAMPLE_PATH.open("rb") as fh:
        files = {"file": (SAMPLE_PATH.name, fh, "text/csv")}
        response = requests.post(API_URL, files=files, timeout=120)

    print("Status:", response.status_code)
    try:
        print(response.json())
    except Exception:
        print(response.text)


if __name__ == "__main__":
    main()
