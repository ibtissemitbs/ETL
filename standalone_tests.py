#!/usr/bin/env python3
"""
🚀 STANDALONE PERFORMANCE TESTS
Works without module dependencies
Measures core performance metrics in local environment
"""

import json
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import psutil


class Colors:
    BOLD = "\033[1m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    ENDC = "\033[0m"


def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text:^70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.ENDC}\n")


def print_metric(label, value, unit="", color=Colors.GREEN):
    """Print formatted metric"""
    if isinstance(value, float):
        formatted = f"{value:.3f}"
    else:
        formatted = str(value)

    print(
        f"{Colors.BOLD}{label:.<45}{Colors.ENDC} {color}{formatted}{unit}{Colors.ENDC}"
    )


class PerformanceMonitor:
    """Standalone performance monitor"""

    def __init__(self, name):
        self.name = name
        self.process = psutil.Process()
        self.metrics = {}

    def test_dataframe_operations(self):
        """Test Pandas DataFrame operations"""
        print_header(f"🔍 {self.name}: DATAFRAME OPERATIONS")

        # Create test data
        print(f"{Colors.BOLD}Creating test data (1000 rows)...{Colors.ENDC}")
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
        print(f"\n{Colors.BOLD}1. Filtering (salary > 80000):{Colors.ENDC}")
        mem_start = self.process.memory_info().rss / 1024 / 1024
        start = time.perf_counter()
        filtered = df[df["salary"] > 80000]
        elapsed = time.perf_counter() - start
        mem_end = self.process.memory_info().rss / 1024 / 1024
        print_metric("   Time", elapsed * 1000, " ms", Colors.BLUE)
        print_metric("   Rows matched", len(filtered))
        print_metric("   Memory Δ", mem_end - mem_start, " MB", Colors.YELLOW)
        results["filter"] = {"time": elapsed, "rows": len(filtered)}

        # Test 2: Group By
        print(f"\n{Colors.BOLD}2. Group By (dept):{Colors.ENDC}")
        start = time.perf_counter()
        grouped = df.groupby("dept")["salary"].agg(["mean", "count"])
        elapsed = time.perf_counter() - start
        print_metric("   Time", elapsed * 1000, " ms", Colors.BLUE)
        print_metric("   Groups", len(grouped))
        results["groupby"] = {"time": elapsed, "groups": len(grouped)}

        # Test 3: Sort
        print(f"\n{Colors.BOLD}3. Sort (by salary desc):{Colors.ENDC}")
        start = time.perf_counter()
        sorted_df = df.sort_values("salary", ascending=False)
        elapsed = time.perf_counter() - start
        print_metric("   Time", elapsed * 1000, " ms", Colors.BLUE)
        results["sort"] = {"time": elapsed}

        # Test 4: Merge
        print(f"\n{Colors.BOLD}4. Merge (2 DataFrames):{Colors.ENDC}")
        df2 = pd.DataFrame(
            {"id": range(500), "bonus": np.random.uniform(1000, 5000, 500)}
        )
        start = time.perf_counter()
        merged = pd.merge(df, df2, on="id", how="left")
        elapsed = time.perf_counter() - start
        print_metric("   Time", elapsed * 1000, " ms", Colors.BLUE)
        print_metric("   Result rows", len(merged))
        results["merge"] = {"time": elapsed, "rows": len(merged)}

        # Test 5: Fill NA
        print(f"\n{Colors.BOLD}5. Fill NA Values:{Colors.ENDC}")
        df_na = merged.copy()
        df_na.loc[df_na["bonus"].isna(), "bonus"] = 0
        start = time.perf_counter()
        filled = df_na.fillna(0)
        elapsed = time.perf_counter() - start
        print_metric("   Time", elapsed * 1000, " ms", Colors.BLUE)
        results["fillna"] = {"time": elapsed}

        # Test 6: Apply Lambda
        print(f"\n{Colors.BOLD}6. Apply Lambda (salary category):{Colors.ENDC}")
        start = time.perf_counter()
        df["salary_category"] = df["salary"].apply(
            lambda x: "High" if x > 100000 else "Medium" if x > 60000 else "Low"
        )
        elapsed = time.perf_counter() - start
        print_metric("   Time", elapsed * 1000, " ms", Colors.BLUE)
        results["apply"] = {"time": elapsed}

        # Summary
        print(f"\n{Colors.BOLD}{Colors.CYAN}DATAFRAME OPERATIONS SUMMARY:{Colors.ENDC}")
        total_time = sum(v["time"] for v in results.values())
        print_metric("Total Time", total_time * 1000, " ms", Colors.BLUE)
        print_metric(
            "Avg Time Per Op", (total_time / len(results)) * 1000, " ms", Colors.BLUE
        )
        print_metric(
            "Throughput", 1000 / (total_time / len(results)), " ops/sec", Colors.BLUE
        )

        return results

    def test_file_io(self):
        """Test file I/O operations"""
        print_header(f"💾 {self.name}: FILE I/O OPERATIONS")

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
        print(f"{Colors.BOLD}1. Write CSV (5000 rows):{Colors.ENDC}")
        start = time.perf_counter()
        df.to_csv("perf_test_write.csv", index=False)
        elapsed = time.perf_counter() - start
        file_size = Path("perf_test_write.csv").stat().st_size / 1024
        print_metric("   Time", elapsed * 1000, " ms", Colors.BLUE)
        print_metric("   Throughput", len(df) / elapsed, " rows/sec", Colors.BLUE)
        print_metric("   File Size", file_size, " KB", Colors.YELLOW)
        results["csv_write"] = {"time": elapsed, "rows": len(df)}

        # CSV Read
        print(f"\n{Colors.BOLD}2. Read CSV (5000 rows):{Colors.ENDC}")
        start = time.perf_counter()
        df_read = pd.read_csv("perf_test_write.csv")
        elapsed = time.perf_counter() - start
        print_metric("   Time", elapsed * 1000, " ms", Colors.BLUE)
        print_metric("   Throughput", len(df_read) / elapsed, " rows/sec", Colors.BLUE)
        results["csv_read"] = {"time": elapsed, "rows": len(df_read)}

        # JSON Write
        print(f"\n{Colors.BOLD}3. Write JSON (5000 rows):{Colors.ENDC}")
        start = time.perf_counter()
        df.to_json("perf_test_write.json", orient="records")
        elapsed = time.perf_counter() - start
        file_size = Path("perf_test_write.json").stat().st_size / 1024
        print_metric("   Time", elapsed * 1000, " ms", Colors.BLUE)
        print_metric("   File Size", file_size, " KB", Colors.YELLOW)
        results["json_write"] = {"time": elapsed}

        # JSON Read
        print(f"\n{Colors.BOLD}4. Read JSON (5000 rows):{Colors.ENDC}")
        start = time.perf_counter()
        df_json = pd.read_json("perf_test_write.json", orient="records")
        elapsed = time.perf_counter() - start
        print_metric("   Time", elapsed * 1000, " ms", Colors.BLUE)
        results["json_read"] = {"time": elapsed}

        # Summary
        print(f"\n{Colors.BOLD}{Colors.CYAN}FILE I/O SUMMARY:{Colors.ENDC}")
        total_time = sum(v["time"] for v in results.values())
        print_metric("Total Time", total_time * 1000, " ms", Colors.BLUE)

        # Cleanup
        Path("perf_test_write.csv").unlink()
        Path("perf_test_write.json").unlink()

        return results

    def test_string_operations(self):
        """Test string operations"""
        print_header(f"✏️ {self.name}: STRING OPERATIONS")

        data = ["string_" + str(i) for i in range(5000)]
        df = pd.DataFrame({"text": data})

        results = {}

        # String contains
        print(f"{Colors.BOLD}1. String Contains (5000 strings):{Colors.ENDC}")
        start = time.perf_counter()
        mask = df["text"].str.contains("string_1")
        elapsed = time.perf_counter() - start
        print_metric("   Time", elapsed * 1000, " ms", Colors.BLUE)
        print_metric("   Matches", mask.sum())
        results["contains"] = {"time": elapsed}

        # String split
        print(f"\n{Colors.BOLD}2. String Split:{Colors.ENDC}")
        df["split"] = df["text"].str.split("_")
        start = time.perf_counter()
        df["first"] = df["split"].str[0]
        elapsed = time.perf_counter() - start
        print_metric("   Time", elapsed * 1000, " ms", Colors.BLUE)
        results["split"] = {"time": elapsed}

        # String replace
        print(f"\n{Colors.BOLD}3. String Replace:{Colors.ENDC}")
        start = time.perf_counter()
        df["replaced"] = df["text"].str.replace("string", "text")
        elapsed = time.perf_counter() - start
        print_metric("   Time", elapsed * 1000, " ms", Colors.BLUE)
        results["replace"] = {"time": elapsed}

        # Summary
        print(f"\n{Colors.BOLD}{Colors.CYAN}STRING OPERATIONS SUMMARY:{Colors.ENDC}")
        total_time = sum(v["time"] for v in results.values())
        print_metric("Total Time", total_time * 1000, " ms", Colors.BLUE)

        return results

    def test_numerical_operations(self):
        """Test numerical operations"""
        print_header(f"🔢 {self.name}: NUMERICAL OPERATIONS")

        df = pd.DataFrame(
            {
                "values": np.random.rand(10000),
                "integers": np.random.randint(0, 100, 10000),
            }
        )

        results = {}

        # Statistics
        print(f"{Colors.BOLD}1. Descriptive Statistics:{Colors.ENDC}")
        start = time.perf_counter()
        stats = df.describe()
        elapsed = time.perf_counter() - start
        print_metric("   Time", elapsed * 1000, " ms", Colors.BLUE)
        results["stats"] = {"time": elapsed}

        # Correlation
        print(f"\n{Colors.BOLD}2. Correlation Matrix:{Colors.ENDC}")
        start = time.perf_counter()
        corr = df.corr()
        elapsed = time.perf_counter() - start
        print_metric("   Time", elapsed * 1000, " ms", Colors.BLUE)
        results["corr"] = {"time": elapsed}

        # Apply numeric operations
        print(f"\n{Colors.BOLD}3. Numeric Transformations:{Colors.ENDC}")
        start = time.perf_counter()
        df["log"] = np.log1p(df["values"])
        df["sqrt"] = np.sqrt(df["values"])
        df["sin"] = np.sin(df["values"])
        elapsed = time.perf_counter() - start
        print_metric("   Time", elapsed * 1000, " ms", Colors.BLUE)
        results["transforms"] = {"time": elapsed}

        # Summary
        print(f"\n{Colors.BOLD}{Colors.CYAN}NUMERICAL OPERATIONS SUMMARY:{Colors.ENDC}")
        total_time = sum(v["time"] for v in results.values())
        print_metric("Total Time", total_time * 1000, " ms", Colors.BLUE)

        return results


def main():
    """Main execution"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║    🚀 STANDALONE PERFORMANCE TEST SUITE                   ║")
    print("║       Pandas / NumPy Benchmarking                         ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}\n")

    monitor = PerformanceMonitor("Standalone")

    # Run tests
    df_results = monitor.test_dataframe_operations()
    io_results = monitor.test_file_io()
    str_results = monitor.test_string_operations()
    num_results = monitor.test_numerical_operations()

    # Final summary
    print_header("📊 OVERALL PERFORMANCE SUMMARY")

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
        print_metric(f"  {category.upper()}", cat_time * 1000, " ms", Colors.BLUE)

    total_time = sum(all_times)
    print_metric("\nTotal Time", total_time * 1000, " ms", Colors.BLUE)

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
        f"\n{Colors.GREEN}✅ Report saved to: reports/execution/standalone_perf_report.json{Colors.ENDC}\n"
    )


if __name__ == "__main__":
    import os

    os.chdir(Path(__file__).parent)
    main()
