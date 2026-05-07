#!/usr/bin/env python3
"""
🔬 MICRO-BENCHMARKS - Performance Tests
Tests détaillés des composants individuels avec timeit et profiling
"""

import cProfile
import io
import pstats
import sys
import time
import timeit
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))


# Couleurs
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def print_section(title: str):
    """Print une section"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{title:^70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.ENDC}\n")


@contextmanager
def profile_function():
    """Context manager pour profiler du code"""
    pr = cProfile.Profile()
    pr.enable()
    try:
        yield pr
    finally:
        pr.disable()
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
        ps.print_stats(10)  # Top 10
        print(s.getvalue())


# ==================== BENCHMARKS PANDAS ====================


def benchmark_dataframe_operations():
    """Benchmark les opérations DataFrame"""
    print_section("📊 BENCHMARK: DataFrame Operations (Pandas)")

    # Créer des données
    n_rows = 10000
    df = pd.DataFrame(
        {
            "id": range(n_rows),
            "value": np.random.rand(n_rows),
            "category": np.random.choice(["A", "B", "C", "D"], n_rows),
            "text": ["text_" + str(i) for i in range(n_rows)],
        }
    )

    # Test 1: Filtrage
    print(f"{Colors.BOLD}1. Filtering ({n_rows:,} rows):{Colors.ENDC}")

    def filter_data():
        return df[df["value"] > 0.5]

    time_filter = timeit.timeit(filter_data, number=100) / 100
    print(f"   {Colors.GREEN}Avg time: {time_filter*1000:.3f} ms{Colors.ENDC}")

    # Test 2: Groupby
    print(f"\n{Colors.BOLD}2. Group By:{Colors.ENDC}")

    def groupby_data():
        return df.groupby("category")["value"].sum()

    time_groupby = timeit.timeit(groupby_data, number=100) / 100
    print(f"   {Colors.GREEN}Avg time: {time_groupby*1000:.3f} ms{Colors.ENDC}")

    # Test 3: Fillna
    print(f"\n{Colors.BOLD}3. Fill NA Values:{Colors.ENDC}")

    df_with_na = df.copy()
    df_with_na.loc[df_with_na["value"] < 0.2, "value"] = np.nan

    def fillna_data():
        return df_with_na.fillna(0)

    time_fillna = timeit.timeit(fillna_data, number=100) / 100
    print(f"   {Colors.GREEN}Avg time: {time_fillna*1000:.3f} ms{Colors.ENDC}")

    # Test 4: Merge
    print(f"\n{Colors.BOLD}4. Merge DataFrames:{Colors.ENDC}")

    df2 = pd.DataFrame({"id": range(5000), "extra": np.random.rand(5000)})

    def merge_data():
        return pd.merge(df, df2, on="id", how="left")

    time_merge = timeit.timeit(merge_data, number=10) / 10
    print(f"   {Colors.GREEN}Avg time: {time_merge*1000:.3f} ms{Colors.ENDC}")

    return {
        "filter": time_filter,
        "groupby": time_groupby,
        "fillna": time_fillna,
        "merge": time_merge,
    }


# ==================== BENCHMARKS EXTRACTION ====================


def benchmark_extraction():
    """Benchmark l'extraction"""
    print_section("🔍 BENCHMARK: Data Extraction")

    try:
        from src.extract import DataExtractor

        extractor = DataExtractor()

        # Test 1: CSV reading
        print(f"{Colors.BOLD}1. Reading CSV:{Colors.ENDC}")

        test_csv = Path("data/in/sample_customers.csv")
        if test_csv.exists():

            def read_csv():
                return extractor.extract_csv(str(test_csv))

            time_csv = timeit.timeit(read_csv, number=5) / 5
            print(f"   {Colors.GREEN}Avg time: {time_csv*1000:.3f} ms{Colors.ENDC}")
        else:
            print(f"   {Colors.YELLOW}⚠ Test file not found{Colors.ENDC}")
            time_csv = 0

        return {"csv_read": time_csv}

    except Exception as e:
        print(f"{Colors.RED}❌ Error: {str(e)}{Colors.ENDC}")
        return {}


# ==================== BENCHMARKS TRANSFORMATION ====================


def benchmark_transformation():
    """Benchmark la transformation"""
    print_section("🔄 BENCHMARK: Data Transformation")

    try:
        from src.transform import DataTransformer

        transformer = DataTransformer()

        # Créer données de test
        test_data = pd.DataFrame(
            {
                "id": range(1000),
                "name": [
                    "Person " + str(i) if i % 10 != 0 else "" for i in range(1000)
                ],
                "age": [
                    np.random.randint(18, 80) if i % 15 != 0 else -1
                    for i in range(1000)
                ],
                "email": ["user" + str(i) + "@example.com" for i in range(1000)],
                "salary": [
                    np.random.uniform(30000, 150000) if i % 20 != 0 else None
                    for i in range(1000)
                ],
            }
        )

        print(f"{Colors.BOLD}1. Cleaning {len(test_data):,} rows:{Colors.ENDC}")

        def transform_data():
            return transformer.transform(test_data)

        time_transform = timeit.timeit(transform_data, number=5) / 5
        print(f"   {Colors.GREEN}Avg time: {time_transform*1000:.3f} ms{Colors.ENDC}")

        return {"transform": time_transform}

    except Exception as e:
        print(f"{Colors.RED}❌ Error: {str(e)}{Colors.ENDC}")
        return {}


# ==================== BENCHMARKS RAG ====================


def benchmark_rag():
    """Benchmark RAG"""
    print_section("🔗 BENCHMARK: RAG Operations")

    try:
        from src.rag_engine import RAGEngine

        rag_engine = RAGEngine()

        # Documents de test
        documents = [
            f"Document {i}: This is a test document about data cleaning. "
            f"It contains information about handling missing values and duplicates. {i}"
            for i in range(50)
        ]

        print(f"{Colors.BOLD}1. Indexing {len(documents)} documents:{Colors.ENDC}")

        def index_docs():
            rag_engine.index_documents(documents[:10])  # Petit subset

        time_index = timeit.timeit(index_docs, number=3) / 3
        print(f"   {Colors.GREEN}Avg time: {time_index*1000:.3f} ms{Colors.ENDC}")

        # Index les documents pour le test de requête
        rag_engine.index_documents(documents)

        print(f"\n{Colors.BOLD}2. Query RAG (20 queries):{Colors.ENDC}")

        queries = [
            "How to clean data?",
            "What about missing values?",
            "Handle duplicates",
        ] * 6 + ["Query test"]

        def query_rag():
            for q in queries:
                rag_engine.query(q, top_k=3)

        time_query = timeit.timeit(query_rag, number=1)
        avg_query_time = time_query / len(queries)
        print(
            f"   {Colors.GREEN}Avg time per query: {avg_query_time*1000:.3f} ms{Colors.ENDC}"
        )

        return {"indexing": time_index, "query": avg_query_time}

    except Exception as e:
        print(f"{Colors.RED}❌ Error: {str(e)}{Colors.ENDC}")
        return {}


# ==================== PROFILING ====================


def profile_extraction():
    """Profile l'extraction"""
    print_section("📈 PROFILING: Data Extraction (Top Functions)")

    try:
        from src.extract import DataExtractor

        extractor = DataExtractor()
        test_csv = Path("data/in/sample_customers.csv")

        if test_csv.exists():
            with profile_function() as pr:
                for _ in range(3):
                    extractor.extract_csv(str(test_csv))
        else:
            print(f"{Colors.YELLOW}⚠ Test file not found{Colors.ENDC}")

    except Exception as e:
        print(f"{Colors.RED}❌ Error: {str(e)}{Colors.ENDC}")


def profile_transformation():
    """Profile la transformation"""
    print_section("📈 PROFILING: Data Transformation (Top Functions)")

    try:
        from src.transform import DataTransformer

        transformer = DataTransformer()

        # Données de test
        test_data = pd.DataFrame(
            {
                "id": range(500),
                "name": ["Person " + str(i) if i % 10 != 0 else "" for i in range(500)],
                "age": [
                    np.random.randint(18, 80) if i % 15 != 0 else -1 for i in range(500)
                ],
                "email": ["user" + str(i) + "@example.com" for i in range(500)],
            }
        )

        with profile_function() as pr:
            for _ in range(5):
                transformer.transform(test_data)

    except Exception as e:
        print(f"{Colors.RED}❌ Error: {str(e)}{Colors.ENDC}")


# ==================== SUMMARY ====================


def print_summary(benchmarks: dict):
    """Affiche un résumé"""
    print_section("📊 RÉSUMÉ DES BENCHMARKS")

    print(f"{Colors.BOLD}Extraction:{Colors.ENDC}")
    for name, time_val in benchmarks.get("extraction", {}).items():
        print(f"  {name:.<40} {Colors.YELLOW}{time_val*1000:.3f} ms{Colors.ENDC}")

    print(f"\n{Colors.BOLD}DataFrame Operations:{Colors.ENDC}")
    for name, time_val in benchmarks.get("dataframe", {}).items():
        print(f"  {name:.<40} {Colors.YELLOW}{time_val*1000:.3f} ms{Colors.ENDC}")

    print(f"\n{Colors.BOLD}Transformation:{Colors.ENDC}")
    for name, time_val in benchmarks.get("transformation", {}).items():
        print(f"  {name:.<40} {Colors.YELLOW}{time_val*1000:.3f} ms{Colors.ENDC}")

    print(f"\n{Colors.BOLD}RAG:{Colors.ENDC}")
    for name, time_val in benchmarks.get("rag", {}).items():
        print(f"  {name:.<40} {Colors.YELLOW}{time_val*1000:.3f} ms{Colors.ENDC}")


# ==================== MAIN ====================


def main():
    """Lance tous les benchmarks"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     🔬 MICRO-BENCHMARKS & PROFILING SUITE                 ║")
    print("║       Detailed Performance Analysis                       ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}")

    benchmarks = {
        "dataframe": benchmark_dataframe_operations(),
        "extraction": benchmark_extraction(),
        "transformation": benchmark_transformation(),
        "rag": benchmark_rag(),
    }

    # Profiling
    profile_extraction()
    profile_transformation()

    # Summary
    print_summary(benchmarks)

    print(f"\n{Colors.BOLD}{Colors.GREEN}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     ✅ BENCHMARKS COMPLETE                               ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}\n")


if __name__ == "__main__":
    import os

    os.chdir(Path(__file__).parent)
    main()
