#!/usr/bin/env python3
"""
ETL CLEANING RESULTS VIEWER
Display cleaning demo results with before/after comparisons and LLM solutions
"""

import json
import sys
from pathlib import Path


def print_header(text):
    """Print formatted header"""
    print(f"\n{'='*70}")
    print(f"{text:^70}")
    print(f"{'='*70}\n")


def print_section(text):
    """Print section"""
    print(f"\n{text}")
    print("-" * 70)


def display_data_issues(issues, stage):
    """Display data quality issues"""
    print_section(f"DATA QUALITY ISSUES - {stage}")

    if not issues:
        print("No issues detected.")
        return

    # Null values
    if "nulls" in issues:
        print("\n[NULL VALUES]:")
        nulls = issues["nulls"]
        for col, info in nulls.items():
            print(f"  - {col}: {info['count']} nulls ({info['percentage']:.1f}%)")

    # Duplicate IDs
    if "duplicate_ids" in issues:
        print(f"\n[DUPLICATE IDs]: {issues['duplicate_ids']} found")

    # Standardization
    if "standardization" in issues:
        print("\n[STANDARDIZATION ISSUES]:")
        for col, issue in issues["standardization"].items():
            print(f"  - {col}: {issue}")


def display_llm_solutions(solutions):
    """Display LLM solutions"""
    print_section("LLM-RECOMMENDED SOLUTIONS")

    for category, rules in solutions.items():
        print(f"\n[{category.upper().replace('_', ' ')}]:")

        if isinstance(rules, dict):
            for key, solution in rules.items():
                if isinstance(solution, dict):
                    for sub_key, sub_solution in solution.items():
                        print(f"  - {sub_key}: {sub_solution}")
                else:
                    print(f"  - {key}: {solution}")
        else:
            print(f"  {rules}")


def display_transformations(transformations):
    """Display applied transformations"""
    print_section("TRANSFORMATIONS APPLIED")

    print(f"\nTotal: {len(transformations)} transformations\n")

    categories = {
        "NULL": [],
        "TYPE": [],
        "STANDARDIZED": [],
        "REMOVED": [],
        "OTHER": [],
    }

    for trans in transformations:
        if "NULL" in trans.upper() or "Filled" in trans:
            categories["NULL"].append(trans)
        elif "Convert" in trans:
            categories["TYPE"].append(trans)
        elif "Standardized" in trans:
            categories["STANDARDIZED"].append(trans)
        elif "Removed" in trans or "Dropped" in trans:
            categories["REMOVED"].append(trans)
        else:
            categories["OTHER"].append(trans)

    for category, items in categories.items():
        if items:
            print(f"[{category}]:")
            for i, item in enumerate(items, 1):
                print(f"  {i}. {item}")
            print()


def display_comparison(comparison):
    """Display before/after comparison"""
    print_section("DATA QUALITY IMPROVEMENTS")

    improvements = comparison["comparison"]

    print(f"\nRows removed: {improvements['rows_removed']}")
    print(f"Null values fixed: {improvements['nulls_fixed']}")
    print(f"Duplicates removed: {improvements['duplicates_removed']}")
    print(f"Completeness improvement: +{improvements['completeness_improvement']:.2f}%")


def display_rag_performance(rag_metrics):
    """Display RAG performance"""
    print_section("RAG ENGINE PERFORMANCE")

    print(f"\nStatus: {rag_metrics['status']}")

    if rag_metrics["status"] == "PASSED":
        metrics = rag_metrics["metrics"]
        print(f"\nMetrics:")
        print(
            f"  - Initialization Time: {metrics.get('initialization', 0)*1000:.2f} ms"
        )
        print(f"  - Avg Index Time: {metrics.get('avg_index_time', 0):.3f} ms")
        print(f"  - Avg Query Time: {metrics.get('avg_query_time', 0):.2f} ms")
        print(f"  - Total Queries: {metrics.get('total_queries', 0)}")
        print(f"  - Total Results Retrieved: {metrics.get('total_results', 0)}")
    else:
        print(f"Reason: {rag_metrics.get('reason', 'Unknown')}")
        if "error" in rag_metrics.get("metrics", {}):
            print(f"Error: {rag_metrics['metrics']['error'][:60]}...")


def view_latest_cleaning_report():
    """View latest cleaning demo report"""
    reports_dir = Path(__file__).parent / "reports" / "execution"

    if not reports_dir.exists():
        print("\n[ERROR] No reports found\n")
        return

    # Find latest cleaning report
    json_files = sorted(reports_dir.glob("etl_cleaning_demo_*.json"), reverse=True)

    if not json_files:
        print("\n[ERROR] No cleaning demo reports found\n")
        return

    latest = json_files[0]
    print(f"\n[REPORT] {latest.name}")

    with open(latest, "r") as f:
        report = json.load(f)

    print_header("ETL CLEANING DEMO RESULTS")

    # Display before analysis
    print(f"Dataset Size:")
    print(f"  - Before: {report['dataset']['before']['total_rows']} rows")
    print(f"  - After: {report['dataset']['after']['total_rows']} rows")

    display_data_issues(report["dataset"]["before"]["issues"], "BEFORE CLEANING")

    # Display LLM solutions
    display_llm_solutions(report["llm_solutions"])

    # Display transformations
    display_transformations(report["transformations_applied"])

    # Display after analysis
    display_data_issues(report["dataset"]["after"]["issues"], "AFTER CLEANING")

    # Display comparison
    display_comparison(report["dataset"])

    # Display RAG performance
    display_rag_performance(report["rag_performance"])

    print_header("END OF REPORT")


def main():
    """Main"""
    import os

    os.chdir(Path(__file__).parent)
    view_latest_cleaning_report()


if __name__ == "__main__":
    main()
