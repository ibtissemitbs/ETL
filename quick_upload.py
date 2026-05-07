#!/usr/bin/env python3
import requests
import json

# Upload the file
url = "http://localhost:8000/upload-and-process"
files = {'file': open('test_logistics_clean.xlsx', 'rb')}
response = requests.post(url, files=files)

if response.status_code == 200:
    result = response.json()
    print(f"Upload successful - {result['data_stats']['original_size']} → {result['data_stats']['cleaned_size']} rows")
    print(f"After sample has {len(result['preview']['after_sample'])} rows")
    
    # Display the structure for debugging
    before_sample = result['preview']['before_sample'][:2] if result['preview']['before_sample'] else []
    after_sample = result['preview']['after_sample'][:2] if result['preview']['after_sample'] else []
    
    print(f"\nBefore sample (first 2): {len(before_sample)} rows")
    print(f"After sample (first 2): {len(after_sample)} rows")
else:
    print(f"Error: {response.status_code}")
    print(response.text)
