#!/usr/bin/env python3
"""
PERFORMANCE TEST MENU
Simple interface to run all performance tests locally in VS Code
"""

import subprocess
import sys
from pathlib import Path


def print_menu():
    """Display main menu"""
    print("\n" + "=" * 70)
    print("ETL PERFORMANCE TEST SUITE - MAIN MENU")
    print("=" * 70)
    print("\nAvailable Tests:\n")
    print("  1. Standalone Tests (Pandas/NumPy/File I/O)")
    print("     - Pure Python performance benchmarks")
    print("     - No ETL dependencies required")
    print("     - Output: reports/execution/standalone_perf_report.json")
    print()
    print("  2. Complete ETL/LLM/RAG Tests")
    print("     - Full platform component testing")
    print("     - Extract, Transform, Load, Profile")
    print("     - LLM rules generation")
    print("     - Output: reports/execution/etl_perf_report_*.json")
    print()
    print("  3. ETL Cleaning Demo (Sample Data)")
    print("     - Real data cleaning with dirty dataset")
    print("     - Shows NULL/Duplicate/Standardization issues")
    print("     - LLM-generated solutions")
    print("     - RAG performance metrics")
    print("     - Output: reports/execution/etl_cleaning_demo_*.json")
    print()
    print("  4. View ETL Cleaning Results")
    print("     - Display cleaned data analysis")
    print("     - Before/After comparison")
    print("     - Transformations applied")
    print()
    print("  5. Logistics Data Cleaning Test (REAL DATA)")
    print("     - Test with logistics_dirty_test.csv")
    print("     - Real-world Tunisia business data")
    print("     - Order data with quality issues")
    print("     - Output: reports/execution/logistics_cleaning_*.json")
    print()
    print("  6. View Performance Results (Markdown)")
    print("     - Open PERFORMANCE_RESULTS.md")
    print()
    print("  7. View JSON Report (Latest)")
    print("     - Display latest ETL performance report")
    print()
    print("  8. Exit")
    print()
    print("=" * 70)


def run_standalone_tests():
    """Run standalone tests"""
    print("\n[STARTING] Standalone Performance Tests...\n")
    result = subprocess.run(
        [sys.executable, "simple_tests.py"], cwd=Path(__file__).parent
    )

    if result.returncode == 0:
        print("\n[SUCCESS] Tests completed!")
        print("[REPORT] reports/execution/standalone_perf_report.json\n")
    else:
        print("\n[FAILED] Tests encountered errors.\n")

    return result.returncode


def run_complete_tests():
    """Run complete ETL/LLM/RAG tests"""
    print("\n[STARTING] Complete ETL/LLM/RAG Performance Tests...\n")
    result = subprocess.run(
        [sys.executable, "perf_tests_complete.py"], cwd=Path(__file__).parent
    )

    if result.returncode == 0:
        print("\n[SUCCESS] Tests completed!")
        print("[REPORT] reports/execution/etl_perf_report_*.json\n")
    else:
        print("\n[COMPLETED] Tests finished (some may have warnings).\n")

    return 0


def run_cleaning_demo():
    """Run ETL cleaning demo"""
    print("\n[STARTING] ETL Cleaning & Transformation Demo...\n")
    result = subprocess.run(
        [sys.executable, "etl_cleaning_demo.py"], cwd=Path(__file__).parent
    )

    if result.returncode == 0:
        print("\n[SUCCESS] Cleaning demo completed!")
        print("[REPORT] reports/execution/etl_cleaning_demo_*.json\n")
    else:
        print("\n[COMPLETED] Demo finished.\n")

    return 0


def run_logistics_test():
    """Run logistics data cleaning test"""
    print("\n[STARTING] Logistics Data Cleaning Test...\n")
    result = subprocess.run(
        [sys.executable, "logistics_cleaning_test.py"], cwd=Path(__file__).parent
    )

    if result.returncode == 0:
        print("\n[SUCCESS] Logistics test completed!")
        print("[REPORT] reports/execution/logistics_cleaning_*.json\n")
    else:
        print("\n[COMPLETED] Test finished.\n")

    return 0


def view_results():
    """View performance results"""
    # Try ASCII-safe version first, then fallback to full version
    ascii_file = Path(__file__).parent / "PERFORMANCE_RESULTS_ASCII.md"
    results_file = Path(__file__).parent / "PERFORMANCE_RESULTS.md"

    target_file = ascii_file if ascii_file.exists() else results_file

    if target_file.exists():
        print("\n" + "=" * 70)
        try:
            with open(target_file, "r", encoding="utf-8") as f:
                content = f.read()
                # Remove problematic unicode characters for Windows console
                content = content.replace("✅", "[OK]").replace("❌", "[FAIL]")
                content = content.replace("⭐", "*").replace("⏳", "[...]")
                print(content)
        except UnicodeEncodeError:
            # Fallback: print without unicode
            with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
                print(f.read())
        print("=" * 70 + "\n")
    else:
        print("\n[ERROR] Performance results not found\n")


def view_cleaning_results():
    """View cleaning demo results"""
    print("\n[STARTING] ETL Cleaning Results Viewer...\n")
    subprocess.run(
        [sys.executable, "view_cleaning_results.py"], cwd=Path(__file__).parent
    )


def view_latest_report():
    """View latest JSON report"""
    import json

    reports_dir = Path(__file__).parent / "reports" / "execution"

    if not reports_dir.exists():
        print("\n[ERROR] No reports found\n")
        return

    # Find latest ETL report
    json_files = sorted(reports_dir.glob("etl_perf_report_*.json"), reverse=True)

    if json_files:
        latest = json_files[0]
        print(f"\n[REPORT] {latest.name}\n")

        with open(latest, "r") as f:
            report = json.load(f)

        print("=" * 70)
        print("PERFORMANCE TEST RESULTS")
        print("=" * 70)

        summary = report.get("summary", {})
        print(f"\nTotal Tests: {summary.get('total', 0)}")
        print(f"  PASSED:  {summary.get('passed', 0)}")
        print(f"  FAILED:  {summary.get('failed', 0)}")
        print(f"  SKIPPED: {summary.get('skipped', 0)}")

        print("\nTest Details:\n")
        for test in report.get("tests", []):
            name = test.get("name", "Unknown")
            status = test.get("status", "UNKNOWN")
            metrics = test.get("metrics", {})

            status_icon = (
                "✅" if status == "PASSED" else "❌" if status == "FAILED" else "⏭️"
            )
            print(f"{status_icon} {name:<20} [{status}]")

            if metrics:
                if "time" in metrics:
                    time_ms = metrics["time"] * 1000
                    print(f"   - Time: {time_ms:.2f} ms")

                if "rows" in metrics:
                    print(f"   - Rows: {metrics['rows']}")

                if "columns" in metrics:
                    print(f"   - Columns: {metrics['columns']}")

        print("\n" + "=" * 70 + "\n")
    else:
        print("\n[ERROR] No ETL performance reports found\n")


def main():
    """Main menu loop"""
    while True:
        print_menu()
        choice = input("Enter your choice (1-8): ").strip()

        if choice == "1":
            run_standalone_tests()
        elif choice == "2":
            run_complete_tests()
        elif choice == "3":
            run_cleaning_demo()
        elif choice == "4":
            view_cleaning_results()
        elif choice == "5":
            run_logistics_test()
        elif choice == "6":
            view_results()
        elif choice == "7":
            view_latest_report()
        elif choice == "8":
            print("\n[EXIT] Goodbye!\n")
            sys.exit(0)
        else:
            print("\n[ERROR] Invalid choice. Please try again.\n")

        input("Press Enter to continue...")


if __name__ == "__main__":
    import os

    os.chdir(Path(__file__).parent)

    # If run with no args, show menu
    if len(sys.argv) == 1:
        main()
    # Support command line args for CI/CD
    elif sys.argv[1] == "standalone":
        sys.exit(run_standalone_tests())
    elif sys.argv[1] == "complete":
        sys.exit(run_complete_tests())
    elif sys.argv[1] == "results":
        view_results()
    elif sys.argv[1] == "report":
        view_latest_report()
    else:
        print(f"Unknown argument: {sys.argv[1]}")
        sys.exit(1)
