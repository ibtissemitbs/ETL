import json
import os
import subprocess
import sys
import time

sys.path.append(".")

print("Starting local LLM test script")

os.environ["LLM_PROVIDER"] = "local"

# detect model via ollama ls
model = None
try:
    res = subprocess.run(["ollama", "ls"], capture_output=True, text=True, check=True)
    lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
    for l in lines:
        parts = l.split()
        if len(parts) == 0:
            continue
        candidate = parts[0]
        if (
            ":" in candidate
            or "mistral" in candidate.lower()
            or "llama" in candidate.lower()
            or "guanaco" in candidate.lower()
        ):
            model = candidate
            break
    if not model and lines:
        model = lines[0].split()[0]
except Exception as e:
    print("ollama ls failed:", e)
    model = os.environ.get("LLM_LOCAL_MODEL")

if not model:
    model = os.environ.get("LLM_LOCAL_MODEL", "llama2")

os.environ["LLM_LOCAL_MODEL"] = model
print(f"Using model: {model}")

import pandas as pd

from src.llm_helper import get_transformation_rules
from src.profiler import build_dataset_profile

csv_path = "backend/uploads/logistics_dirty_test.csv"
if not os.path.exists(csv_path):
    raise FileNotFoundError(csv_path)

df = pd.read_csv(csv_path)
profile = build_dataset_profile(df)

start = time.time()
try:
    rules = get_transformation_rules(
        profile, model=model, use_cache=False, dataframe=df
    )
    print("\n=== RULES JSON ===")
    print(json.dumps(rules, indent=2, ensure_ascii=False))
except Exception as e:
    print("LLM call failed:", str(e))
    import traceback

    traceback.print_exc()
    sys.exit(2)
finally:
    print("Elapsed:", time.time() - start)

print("Done")
