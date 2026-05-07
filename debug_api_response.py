#!/usr/bin/env python3
"""Check full API response structure"""
import requests
import json

API_BASE = 'http://localhost:8000'

# Upload and process
with open('test_null_shipment_id.csv', 'rb') as f:
    files = {'file': f}
    resp = requests.post(f'{API_BASE}/upload-and-process?domain_override=logistics', files=files)

data = resp.json()

if resp.status_code == 200:
    # Show first row in detail
    after_sample = data.get('preview', {}).get('after_sample', [])
    if after_sample:
        print("First row in detail:")
        print(json.dumps(after_sample[0], indent=2))
    else:
        print("No after_sample found")
else:
    print(f"Upload failed: {resp.status_code}")
