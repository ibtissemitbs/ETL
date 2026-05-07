#!/usr/bin/env python3
"""
STANDALONE PERFORMANCE TESTS - Simple Version
Works without Unicode box drawing characters
Tests Pandas/NumPy performance locally
"""

import json
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import psutil


def print_header(text):
    """Print formatted header"""
    print(f"\n{'='*70}")
    print(f"{text:^70}")
    print(f"{'='*70}\n")


def print_metric(label, value, unit="", color_code=""):
    """Print formatted metric"""
    if isinstance(value, float):
        formatted = f"{value:.3f}"
    else:
        formatted = str(value)

    print(f"{label:.<45} {formatted}{unit}")


class PerformanceMonitor:
    """Standalone performance monitor"""

    def __init__(self, name):
        self.name = name
        self.process = psutil.Process()
        self.metrics = {}

    def test_dataframe_operations(self):
        """Test Pandas DataFrame operations"""
        print_header(f"[DATAFRAME OPERATIONS]")

        # Create test data
        print(f"Creating test data (1000 rows)...")
        df = pd.DataFrame(
            {
                "id": range(1000),
                "name": ["Person_" + str(i) for i in range(1000)],
                "age": np.random.randint(18, 80, 1000),
                "salary": np.random.uniform(30000, 150000, 1000),
                "dept": np.random.choice(["Sales", "Tech", "HR", "Ops"], 1000),
                "score": np.random.rand(1000),
            }
        )

        results = {}

        # Test 1: Filtering
        print(f"\n[1] Filtering (salary > 80000):")
        mem_start = self.process.memory_info().rss / 1024 / 1024
        start = time.perf_counter()
        filtered = df[df["salary"] > 80000]
        elapsed = time.perf_counter() - start
        mem_end = self.process.memory_info().rss / 1024 / 1024
        print_metric("    Time", elapsed * 1000, " ms")
        print_metric("    Rows matched", len(filtered))
        print_metric("    Memory delta", mem_end - mem_start, " MB")
        results["filter"] = {"time": elapsed, "rows": len(filtered)}

        # Test 2: Group By
        print(f"\n[2] Group By (dept):")
        start = time.perf_counter()
        grouped = df.groupby("dept")["salary"].agg(["mean", "count"])
        elapsed = time.perf_counter() - start
        print_metric("    Time", elapsed * 1000, " ms")
        print_metric("    Groups", len(grouped))
        results["groupby"] = {"time": elapsed, "groups": len(grouped)}

        # Test 3: Sort
        print(f"\n[3] Sort (by salary desc):")
        start = time.perf_counter()
        sorted_df = df.sort_values("salary", ascending=False)
        elapsed = time.perf_counter() - start
        print_metric("    Time", elapsed * 1000, " ms")
        results["sort"] = {"time": elapsed}

        # Test 4: Merge
        print(f"\n[4] Merge (2 DataFrames):")
        df2 = pd.DataFrame(
            {"id": range(500), "bonus": np.random.uniform(1000, 5000, 500)}
        )
        start = time.perf_counter()
        merged = pd.merge(df, df2, on="id", how="left")
        elapsed = time.perf_counter() - start
        print_metric("    Time", elapsed * 1000, " ms")
        print_metric("    Result rows", len(merged))
        results["merge"] = {"time": elapsed, "rows": len(merged)}

        # Test 5: Fill NA
        print(f"\n[5] Fill NA Values:")
        df_na = merged.copy()
        df_na.loc[df_na["bonus"].isna(), "bonus"] = 0
        start = time.perf_counter()
        filled = df_na.fillna(0)
        elapsed = time.perf_counter() - start
        print_metric("    Time", elapsed * 1000, " ms")
        results["fillna"] = {"time": elapsed}

        # Test 6: Apply Lambda
        print(f"\n[6] Apply Lambda (salary category):")
        start = time.perf_counter()
        df["salary_category"] = df["salary"].apply(
            lambda x: "High" if x > 100000 else "Medium" if x > 60000 else "Low"
        )
        elapsed = time.perf_counter() - start
        print_metric("    Time", elapsed * 1000, " ms")
        results["apply"] = {"time": elapsed}

        # Summary
        print(f"\n[SUMMARY] DATAFRAME OPERATIONS:")
        total_time = sum(v["time"] for v in results.values())
        print_metric("Total Time", total_time * 1000, " ms")
        print_metric("Avg Time Per Op", (total_time / len(results)) * 1000, " ms")
        print_metric("Throughput", 1000 / (total_time / len(results)), " ops/sec")

        return results

    def test_file_io(self):
        """Test file I/O operations"""
        print_header(f"[FILE I/O OPERATIONS]")

        # Create test data
        df = pd.DataFrame(
            {
                "id": range(5000),
                "value": np.random.rand(5000),
                "text": ["data_" + str(i) for i in range(5000)],
            }
        )

        results = {}

        # CSV Write
        print(f"[1] Write CSV (5000 rows):")
        start = time.perf_counter()
        df.to_csv("perf_test_write.csv", index=False)
        elapsed = time.perf_counter() - start
        file_size = Path("perf_test_write.csv").stat().st_size / 1024
        print_metric("    Time", elapsed * 1000, " ms")
        print_metric("    Throughput", len(df) / elapsed, " rows/sec")
        print_metric("    File Size", file_size, " KB")
        results["csv_write"] = {"time": elapsed, "rows": len(df)}

        # CSV Read
        print(f"\n[2] Read CSV (5000 rows):")
        start = time.perf_counter()
        df_read = pd.read_csv("perf_test_write.csv")
        elapsed = time.perf_counter() - start
        print_metric("    Time", elapsed * 1000, " ms")
        print_metric("    Throughput", len(df_read) / elapsed, " rows/sec")
        results["csv_read"] = {"time": elapsed, "rows": len(df_read)}

        # JSON Write
        print(f"\n[3] Write JSON (5000 rows):")
        start = time.perf_counter()
        df.to_json("perf_test_write.json", orient="records")
        elapsed = time.perf_counter() - start
        file_size = Path("perf_test_write.json").stat().st_size / 1024
        print_metric("    Time", elapsed * 1000, " ms")
        print_metric("    File Size", file_size, " KB")
        results["json_write"] = {"time": elapsed}

        # JSON Read
        print(f"\n[4] Read JSON (5000 rows):")
        start = time.perf_counter()
        df_json = pd.read_json("perf_test_write.json", orient="records")
        elapsed = time.perf_counter() - start
        print_metric("    Time", elapsed * 1000, " ms")
        results["json_read"] = {"time": elapsed}

        # Summary
        print(f"\n[SUMMARY] FILE I/O:")
        total_time = sum(v["time"] for v in results.values())
        print_metric("Total Time", total_time * 1000, " ms")

        # Cleanup
        Path("perf_test_write.csv").unlink()
        Path("perf_test_write.json").unlink()

        return results

    def test_string_operations(self):
        """Test string operations"""
        print_header(f"[STRING OPERATIONS]")

        data = ["string_" + str(i) for i in range(5000)]
        df = pd.DataFrame({"text": data})

        results = {}

        # String contains
        print(f"[1] String Contains (5000 strings):")
        start = time.perf_counter()
        mask = df["text"].str.contains("string_1")
        elapsed = time.perf_counter() - start
        print_metric("    Time", elapsed * 1000, " ms")
        print_metric("    Matches", mask.sum())
        results["contains"] = {"time": elapsed}

        # String split
        print(f"\n[2] String Split:")
        df["split"] = df["text"].str.split("_")
        start = time.perf_counter()
        df["first"] = df["split"].str[0]
        elapsed = time.perf_counter() - start
        print_metric("    Time", elapsed * 1000, " ms")
        results["split"] = {"time": elapsed}

        # String replace
        print(f"\n[3] String Replace:")
        start = time.perf_counter()
        df["replaced"] = df["text"].str.replace("string", "text")
        elapsed = time.perf_counter() - start
        print_metric("    Time", elapsed * 1000, " ms")
        results["replace"] = {"time": elapsed}

        # Summary
        print(f"\n[SUMMARY] STRING OPERATIONS:")
        total_time = sum(v["time"] for v in results.values())
        print_metric("Total Time", total_time * 1000, " ms")

        return results

    def test_numerical_operations(self):
        """Test numerical operations"""
        print_header(f"[NUMERICAL OPERATIONS]")

        df = pd.DataFrame(
            {
                "values": np.random.rand(10000),
                "integers": np.random.randint(0, 100, 10000),
            }
        )

        results = {}

        # Statistics
        print(f"[1] Descriptive Statistics:")
        start = time.perf_counter()
        stats = df.describe()
        elapsed = time.perf_counter() - start
        print_metric("    Time", elapsed * 1000, " ms")
        results["stats"] = {"time": elapsed}

        # Correlation
        print(f"\n[2] Correlation Matrix:")
        start = time.perf_counter()
        corr = df.corr()
        elapsed = time.perf_counter() - start
        print_metric("    Time", elapsed * 1000, " ms")
        results["corr"] = {"time": elapsed}

        # Apply numeric operations
        print(f"\n[3] Numeric Transformations:")
        start = time.perf_counter()
        df["log"] = np.log1p(df["values"])
        df["sqrt"] = np.sqrt(df["values"])
        df["sin"] = np.sin(df["values"])
        elapsed = time.perf_counter() - start
        print_metric("    Time", elapsed * 1000, " ms")
        results["transforms"] = {"time": elapsed}

        # Summary
        print(f"\n[SUMMARY] NUMERICAL OPERATIONS:")
        total_time = sum(v["time"] for v in results.values())
        print_metric("Total Time", total_time * 1000, " ms")

        return results


def main():
    """Main execution"""
    print(f"\n{'='*70}")
    print("STANDALONE PERFORMANCE TEST SUITE")
    print("Pandas / NumPy Benchmarking")
    print(f"{'='*70}")

    monitor = PerformanceMonitor("Standalone")

    # Run tests
    df_results = monitor.test_dataframe_operations()
    io_results = monitor.test_file_io()
    str_results = monitor.test_string_operations()
    num_results = monitor.test_numerical_operations()

    # Final summary
    print_header("OVERALL PERFORMANCE SUMMARY")

    all_results = {
        "dataframe": df_results,
        "file_io": io_results,
        "strings": str_results,
        "numerical": num_results,
    }

    all_times = []
    for category, results in all_results.items():
        cat_time = sum(v["time"] for v in results.values())
        all_times.append(cat_time)
        print_metric(f"  {category.upper()}", cat_time * 1000, " ms")

    total_time = sum(all_times)
    print_metric("\nTotal Time", total_time * 1000, " ms")

    # Save report
    report = {
        "timestamp": datetime.now().isoformat(),
        "results": all_results,
        "total_time": total_time,
    }

    Path("reports/execution").mkdir(parents=True, exist_ok=True)
    with open("reports/execution/standalone_perf_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(
        f"\n[SUCCESS] Report saved to: reports/execution/standalone_perf_report.json\n"
    )


if __name__ == "__main__":
    import os

    os.chdir(Path(__file__).parent)
    main()
