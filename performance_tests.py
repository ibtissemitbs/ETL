#!/usr/bin/env python3
"""
🚀 PERFORMANCE TESTS - ETL / LLM / RAG
Mesure les performances et génère un rapport détaillé
"""

import json
import os
import sys
import threading
import time
import tracemalloc
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import psutil

# Ajouter le chemin pour importer les modules
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd


# Couleurs pour le terminal
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


@dataclass
class PerformanceMetrics:
    """Stocke les métriques de performance"""

    test_name: str
    duration: float  # secondes
    memory_start: float  # MB
    memory_end: float  # MB
    memory_peak: float  # MB
    cpu_percent: float  # %
    rows_processed: int = 0
    throughput: float = 0.0  # rows/sec
    status: str = "OK"
    error: str = ""

    def get_memory_used(self) -> float:
        """Mémoire utilisée en MB"""
        return self.memory_end - self.memory_start

    def get_memory_peak_used(self) -> float:
        """Pic de mémoire utilisé en MB"""
        return self.memory_peak - self.memory_start


class PerformanceMonitor:
    """Monitore les performances pendant l'exécution"""

    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.metrics = None
        self.process = psutil.Process()
        self.memory_samples = []
        self.cpu_samples = []
        self.monitoring = False
        self.monitor_thread = None

    def start(self):
        """Démarre le monitoring"""
        tracemalloc.start()
        self.start_time = time.perf_counter()
        self.memory_start = self.process.memory_info().rss / 1024 / 1024  # MB
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def _monitor_loop(self):
        """Boucle de monitoring en arrière-plan"""
        while self.monitoring:
            try:
                self.memory_samples.append(self.process.memory_info().rss / 1024 / 1024)
                self.cpu_samples.append(self.process.cpu_percent(interval=0.1))
                time.sleep(0.1)
            except:
                break

    def stop(self, rows_processed: int = 0) -> PerformanceMetrics:
        """Arrête le monitoring et retourne les métriques"""
        self.monitoring = False
        duration = time.perf_counter() - self.start_time

        memory_end = self.process.memory_info().rss / 1024 / 1024  # MB
        memory_peak = max(self.memory_samples) if self.memory_samples else memory_end

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        cpu_percent = np.mean(self.cpu_samples) if self.cpu_samples else 0
        throughput = (
            rows_processed / duration if duration > 0 and rows_processed > 0 else 0
        )

        self.metrics = PerformanceMetrics(
            test_name=self.name,
            duration=duration,
            memory_start=self.memory_start,
            memory_end=memory_end,
            memory_peak=memory_peak,
            cpu_percent=cpu_percent,
            rows_processed=rows_processed,
            throughput=throughput,
        )

        return self.metrics


def print_header(text: str):
    """Affiche un en-tête formaté"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text:^70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.ENDC}\n")


def print_metric(label: str, value: Any, unit: str = "", color: str = Colors.GREEN):
    """Affiche une métrique formatée"""
    if isinstance(value, float):
        formatted_value = f"{value:.2f}"
    else:
        formatted_value = str(value)

    print(
        f"{Colors.BOLD}{label:.<40}{Colors.ENDC} {color}{formatted_value}{unit}{Colors.ENDC}"
    )


def format_bytes(bytes_val: float) -> str:
    """Formate les bytes en format lisible"""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.2f} TB"


# ==================== TESTS ETL ====================


def test_extract_performance():
    """Test la performance de l'extraction de données"""
    print_header("🔍 TEST 1: PERFORMANCE D'EXTRACTION (Extract)")

    monitor = PerformanceMonitor("Extract")

    try:
        from src.extract import DataExtractor

        monitor.start()

        # Test avec CSV
        test_file = "data/in/sample_customers.csv"
        if not Path(test_file).exists():
            print(f"{Colors.YELLOW}⚠ Fichier test non trouvé: {test_file}{Colors.ENDC}")
            return None

        extractor = DataExtractor()
        data = extractor.extract_csv(test_file)

        rows = len(data) if isinstance(data, pd.DataFrame) else 0
        metrics = monitor.stop(rows)

        # Affichage des résultats
        print_metric("✅ Status", metrics.status)
        print_metric("📊 Rows Extracted", rows)
        print_metric("⏱ Duration", f"{metrics.duration:.3f}", " sec", Colors.BLUE)
        print_metric(
            "📈 Throughput", f"{metrics.throughput:.0f}", " rows/sec", Colors.BLUE
        )
        print_metric(
            "💾 Memory Used", f"{metrics.get_memory_used():.2f}", " MB", Colors.YELLOW
        )
        print_metric(
            "📍 Memory Peak",
            f"{metrics.get_memory_peak_used():.2f}",
            " MB",
            Colors.YELLOW,
        )
        print_metric("🖥 CPU Usage", f"{metrics.cpu_percent:.1f}", " %", Colors.YELLOW)

        return metrics

    except Exception as e:
        print(f"{Colors.RED}❌ Erreur: {str(e)}{Colors.ENDC}")
        return None


def test_profiling_performance():
    """Test la performance du profiling"""
    print_header("📊 TEST 2: PERFORMANCE DU PROFILING (Profiler)")

    monitor = PerformanceMonitor("Profiler")

    try:
        from src.profiler import DataProfiler

        # Créer un dataset de test
        test_data = pd.DataFrame(
            {
                "id": range(1000),
                "name": ["Person " + str(i) for i in range(1000)],
                "age": np.random.randint(18, 80, 1000),
                "email": ["user" + str(i) + "@example.com" for i in range(1000)],
                "salary": np.random.uniform(30000, 150000, 1000),
                "date": pd.date_range("2020-01-01", periods=1000),
            }
        )

        monitor.start()

        profiler = DataProfiler()
        profile = profiler.profile(test_data)

        metrics = monitor.stop(len(test_data))

        print_metric("✅ Status", metrics.status)
        print_metric("📊 Rows Profiled", len(test_data))
        print_metric("⏱ Duration", f"{metrics.duration:.3f}", " sec", Colors.BLUE)
        print_metric(
            "📈 Throughput", f"{metrics.throughput:.0f}", " rows/sec", Colors.BLUE
        )
        print_metric(
            "💾 Memory Used", f"{metrics.get_memory_used():.2f}", " MB", Colors.YELLOW
        )
        print_metric("🖥 CPU Usage", f"{metrics.cpu_percent:.1f}", " %", Colors.YELLOW)

        if profile:
            print_metric("🔍 Columns Analyzed", len(profile))

        return metrics

    except Exception as e:
        print(f"{Colors.RED}❌ Erreur: {str(e)}{Colors.ENDC}")
        return None


def test_transform_performance():
    """Test la performance de la transformation"""
    print_header("🔄 TEST 3: PERFORMANCE DE TRANSFORMATION (Transform)")

    monitor = PerformanceMonitor("Transform")

    try:
        from src.transform import DataTransformer

        # Créer un dataset de test avec anomalies
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

        monitor.start()

        transformer = DataTransformer()
        cleaned_data = transformer.transform(test_data)

        metrics = monitor.stop(len(test_data))

        print_metric("✅ Status", metrics.status)
        print_metric("📊 Rows Transformed", len(test_data))
        print_metric("✓ Rows Output", len(cleaned_data))
        print_metric("⏱ Duration", f"{metrics.duration:.3f}", " sec", Colors.BLUE)
        print_metric(
            "📈 Throughput", f"{metrics.throughput:.0f}", " rows/sec", Colors.BLUE
        )
        print_metric(
            "💾 Memory Used", f"{metrics.get_memory_used():.2f}", " MB", Colors.YELLOW
        )
        print_metric("🖥 CPU Usage", f"{metrics.cpu_percent:.1f}", " %", Colors.YELLOW)

        return metrics

    except Exception as e:
        print(f"{Colors.RED}❌ Erreur: {str(e)}{Colors.ENDC}")
        return None


def test_load_performance():
    """Test la performance de l'export"""
    print_header("💾 TEST 4: PERFORMANCE D'EXPORT (Load)")

    monitor = PerformanceMonitor("Load")

    try:
        from src.load import DataLoader

        # Créer un dataset de test
        test_data = pd.DataFrame(
            {
                "id": range(1000),
                "name": ["Person " + str(i) for i in range(1000)],
                "age": np.random.randint(18, 80, 1000),
                "email": ["user" + str(i) + "@example.com" for i in range(1000)],
                "salary": np.random.uniform(30000, 150000, 1000),
            }
        )

        monitor.start()

        loader = DataLoader()
        output_path = loader.save_csv(test_data, "data/processed/perf_test_output.csv")

        metrics = monitor.stop(len(test_data))

        file_size = (
            Path(output_path).stat().st_size / 1024 if Path(output_path).exists() else 0
        )

        print_metric("✅ Status", metrics.status)
        print_metric("📊 Rows Saved", len(test_data))
        print_metric("📁 Output File", Path(output_path).name)
        print_metric("📦 File Size", f"{file_size:.2f}", " KB", Colors.YELLOW)
        print_metric("⏱ Duration", f"{metrics.duration:.3f}", " sec", Colors.BLUE)
        print_metric(
            "📈 Throughput", f"{metrics.throughput:.0f}", " rows/sec", Colors.BLUE
        )
        print_metric(
            "💾 Memory Used", f"{metrics.get_memory_used():.2f}", " MB", Colors.YELLOW
        )
        print_metric("🖥 CPU Usage", f"{metrics.cpu_percent:.1f}", " %", Colors.YELLOW)

        return metrics

    except Exception as e:
        print(f"{Colors.RED}❌ Erreur: {str(e)}{Colors.ENDC}")
        return None


# ==================== TESTS RAG ====================


def test_rag_indexing_performance():
    """Test la performance de l'indexation RAG"""
    print_header("🔗 TEST 5: PERFORMANCE INDEXATION RAG (RAG)")

    monitor = PerformanceMonitor("RAG Indexing")

    try:
        from src.rag_engine import RAGEngine

        # Créer des documents de test
        documents = [
            f"Document {i}: This is a sample document about data cleaning. "
            f"It contains information about handling missing values, duplicates, "
            f"and data validation. Document content for RAG testing {i}."
            for i in range(100)
        ]

        monitor.start()

        rag_engine = RAGEngine()
        rag_engine.index_documents(documents)

        metrics = monitor.stop(len(documents))

        print_metric("✅ Status", metrics.status)
        print_metric("📚 Documents Indexed", len(documents))
        print_metric("⏱ Duration", f"{metrics.duration:.3f}", " sec", Colors.BLUE)
        print_metric(
            "📈 Throughput", f"{metrics.throughput:.0f}", " docs/sec", Colors.BLUE
        )
        print_metric(
            "💾 Memory Used", f"{metrics.get_memory_used():.2f}", " MB", Colors.YELLOW
        )
        print_metric(
            "📍 Memory Peak",
            f"{metrics.get_memory_peak_used():.2f}",
            " MB",
            Colors.YELLOW,
        )
        print_metric("🖥 CPU Usage", f"{metrics.cpu_percent:.1f}", " %", Colors.YELLOW)

        return metrics

    except Exception as e:
        print(f"{Colors.RED}❌ Erreur: {str(e)}{Colors.ENDC}")
        return None


def test_rag_query_performance():
    """Test la performance des requêtes RAG"""
    print_header("🔍 TEST 6: PERFORMANCE REQUÊTES RAG (Query)")

    monitor = PerformanceMonitor("RAG Query")

    try:
        from src.rag_engine import RAGEngine

        # Créer et indexer des documents
        documents = [
            f"Document {i}: Data cleaning is important. Missing values must be handled. "
            f"Duplicates should be removed. Data validation ensures quality. {i}"
            for i in range(50)
        ]

        rag_engine = RAGEngine()
        rag_engine.index_documents(documents)

        queries = [
            "How to handle missing data?",
            "What about duplicates?",
            "Why data validation?",
            "Data quality importance",
            "Cleaning procedures",
        ] * 4  # 20 queries

        monitor.start()

        results = []
        for query in queries:
            result = rag_engine.query(query, top_k=3)
            results.append(result)

        metrics = monitor.stop(len(queries))

        print_metric("✅ Status", metrics.status)
        print_metric("🔍 Queries Executed", len(queries))
        print_metric("⏱ Total Duration", f"{metrics.duration:.3f}", " sec", Colors.BLUE)
        print_metric(
            "⏱ Avg Per Query",
            f"{metrics.duration/len(queries):.3f}",
            " sec",
            Colors.BLUE,
        )
        print_metric(
            "💾 Memory Used", f"{metrics.get_memory_used():.2f}", " MB", Colors.YELLOW
        )
        print_metric("🖥 CPU Usage", f"{metrics.cpu_percent:.1f}", " %", Colors.YELLOW)

        return metrics

    except Exception as e:
        print(f"{Colors.RED}❌ Erreur: {str(e)}{Colors.ENDC}")
        return None


# ==================== TESTS LLM ====================


def test_llm_performance():
    """Test la performance du LLM"""
    print_header("🤖 TEST 7: PERFORMANCE LLM (Language Model)")

    monitor = PerformanceMonitor("LLM")

    try:
        from src.llm_helper import LLMHelper

        llm_helper = LLMHelper()

        # Vérifier si les clés API sont configurées
        if not llm_helper.has_api_keys():
            print(
                f"{Colors.YELLOW}⚠ Clés API non configurées ({llm_helper.get_api_key_status()}){Colors.ENDC}"
            )
            print(f"{Colors.YELLOW}⚠ Skipping LLM test{Colors.ENDC}")
            return None

        prompts = [
            "Suggest a data cleaning rule for handling NULL values in age column",
            "Generate a validation rule for email addresses",
            "What's a good strategy for deduplicating data?",
        ]

        monitor.start()

        responses = []
        for prompt in prompts:
            response = llm_helper.generate(prompt, max_tokens=100)
            responses.append(response)

        metrics = monitor.stop(len(prompts))

        print_metric("✅ Status", metrics.status)
        print_metric("💬 Prompts Processed", len(prompts))
        print_metric("⏱ Total Duration", f"{metrics.duration:.3f}", " sec", Colors.BLUE)
        print_metric(
            "⏱ Avg Per Prompt",
            f"{metrics.duration/len(prompts):.3f}",
            " sec",
            Colors.BLUE,
        )
        print_metric(
            "💾 Memory Used", f"{metrics.get_memory_used():.2f}", " MB", Colors.YELLOW
        )
        print_metric("🖥 CPU Usage", f"{metrics.cpu_percent:.1f}", " %", Colors.YELLOW)

        return metrics

    except Exception as e:
        print(f"{Colors.RED}❌ Erreur: {str(e)}{Colors.ENDC}")
        print(f"{Colors.YELLOW}ℹ Note: LLM test requires API keys in .env{Colors.ENDC}")
        return None


# ==================== TEST INTÉGRATION ====================


def test_full_pipeline_performance():
    """Test la performance du pipeline complet"""
    print_header("🚀 TEST 8: PERFORMANCE PIPELINE COMPLET (E2E)")

    monitor = PerformanceMonitor("Full Pipeline")

    try:
        from src.extract import DataExtractor
        from src.load import DataLoader
        from src.profiler import DataProfiler
        from src.transform import DataTransformer

        monitor.start()

        # 1. Extract
        extractor = DataExtractor()
        test_file = "data/in/sample_customers.csv"

        if Path(test_file).exists():
            data = extractor.extract_csv(test_file)
            rows = len(data)
        else:
            # Créer un dataset de test
            data = pd.DataFrame(
                {
                    "id": range(500),
                    "name": ["Person " + str(i) for i in range(500)],
                    "age": np.random.randint(18, 80, 500),
                    "email": ["user" + str(i) + "@example.com" for i in range(500)],
                }
            )
            rows = len(data)

        # 2. Profile
        profiler = DataProfiler()
        profile = profiler.profile(data)

        # 3. Transform
        transformer = DataTransformer()
        cleaned_data = transformer.transform(data)

        # 4. Load
        loader = DataLoader()
        output_path = loader.save_csv(
            cleaned_data, "data/processed/perf_test_pipeline.csv"
        )

        metrics = monitor.stop(rows)

        print_metric("✅ Status", metrics.status)
        print_metric("📊 Rows Processed", rows)
        print_metric("✓ Rows Output", len(cleaned_data))
        print_metric("⏱ Total Duration", f"{metrics.duration:.3f}", " sec", Colors.BLUE)
        print_metric(
            "📈 Throughput", f"{metrics.throughput:.0f}", " rows/sec", Colors.BLUE
        )
        print_metric(
            "💾 Memory Used", f"{metrics.get_memory_used():.2f}", " MB", Colors.YELLOW
        )
        print_metric(
            "📍 Memory Peak",
            f"{metrics.get_memory_peak_used():.2f}",
            " MB",
            Colors.YELLOW,
        )
        print_metric("🖥 CPU Usage", f"{metrics.cpu_percent:.1f}", " %", Colors.YELLOW)

        return metrics

    except Exception as e:
        print(f"{Colors.RED}❌ Erreur: {str(e)}{Colors.ENDC}")
        return None


# ==================== RAPPORT ====================


def generate_report(metrics_list: List[PerformanceMetrics]):
    """Génère un rapport de performance"""
    print_header("📋 RAPPORT DE PERFORMANCE GLOBAL")

    total_duration = sum(m.duration for m in metrics_list if m)
    total_memory = sum(m.get_memory_used() for m in metrics_list if m)
    avg_cpu = np.mean([m.cpu_percent for m in metrics_list if m])

    print_metric("Total Tests", len([m for m in metrics_list if m]))
    print_metric("Total Duration", f"{total_duration:.3f}", " sec", Colors.BLUE)
    print_metric("Total Memory Used", f"{total_memory:.2f}", " MB", Colors.YELLOW)
    print_metric("Avg CPU Usage", f"{avg_cpu:.1f}", " %", Colors.YELLOW)

    print(f"\n{Colors.BOLD}{Colors.CYAN}Résumé par Test:{Colors.ENDC}\n")

    for m in metrics_list:
        if m:
            status_color = Colors.GREEN if m.status == "OK" else Colors.RED
            print(
                f"{Colors.BOLD}{m.test_name:.<40}{Colors.ENDC} "
                f"{status_color}{m.status}{Colors.ENDC} "
                f"⏱ {m.duration:.3f}s "
                f"💾 {m.get_memory_used():.2f}MB"
            )

    # Sauvegarder le rapport en JSON
    report_path = "reports/execution/performance_report.json"
    Path("reports/execution").mkdir(parents=True, exist_ok=True)

    report = {
        "timestamp": datetime.now().isoformat(),
        "tests": [asdict(m) for m in metrics_list if m],
        "summary": {
            "total_duration": total_duration,
            "total_memory": total_memory,
            "avg_cpu": avg_cpu,
            "total_tests": len([m for m in metrics_list if m]),
        },
    }

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n{Colors.GREEN}✅ Rapport sauvegardé: {report_path}{Colors.ENDC}")


# ==================== MAIN ====================


def main():
    """Exécute tous les tests"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║   🚀 SUITE COMPLÈTE DE TESTS DE PERFORMANCE                 ║")
    print("║      ETL / LLM / RAG Performance Benchmark                  ║")
    print(
        "║      Démarré le: "
        + datetime.now().strftime("%Y-%m-%d %H:%M:%S").ljust(33)
        + "║"
    )
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}\n")

    metrics_list = []

    # Exécuter les tests
    metrics_list.append(test_extract_performance())
    metrics_list.append(test_profiling_performance())
    metrics_list.append(test_transform_performance())
    metrics_list.append(test_load_performance())
    metrics_list.append(test_rag_indexing_performance())
    metrics_list.append(test_rag_query_performance())
    metrics_list.append(test_llm_performance())
    metrics_list.append(test_full_pipeline_performance())

    # Générer le rapport
    generate_report(metrics_list)

    print(f"\n{Colors.BOLD}{Colors.GREEN}")
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║   ✅ TOUS LES TESTS SONT TERMINÉS                           ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}\n")


if __name__ == "__main__":
    main()
