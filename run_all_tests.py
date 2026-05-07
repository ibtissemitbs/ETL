#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Test Runner - Performance Tests
Fonctionne sans problèmes d'encodage
"""

import subprocess
import sys
from pathlib import Path


def main():
    print("\n" + "=" * 70)
    print("PERFORMANCE TEST RUNNER")
    print("=" * 70)

    print("\n1. Running Standalone Tests (Pandas/NumPy)...")
    print("-" * 70)
    result1 = subprocess.run(
        [sys.executable, "standalone_tests.py"], cwd=Path(__file__).parent
    )

    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print(f"\nStandalone Tests: {'PASSED' if result1.returncode == 0 else 'FAILED'}")
    print(f"Report: reports/execution/standalone_perf_report.json")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

    return result1.returncode


if __name__ == "__main__":
    sys.exit(main())
