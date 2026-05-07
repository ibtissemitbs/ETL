#!/usr/bin/env python3
"""
🚀 SETUP & LAUNCH - Performance Tests
Configuration et lancement automatique
"""

import subprocess
import sys
from pathlib import Path


class Colors:
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def print_banner():
    """Affiche la bannière"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║        🚀 PERFORMANCE TEST SUITE - SETUP                 ║")
    print("║     ETL / LLM / RAG Benchmarking & Profiling              ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}\n")


def install_requirements():
    """Installe les dépendances"""
    required = ["psutil", "pandas", "numpy"]

    print(f"{Colors.YELLOW}Checking dependencies...{Colors.ENDC}\n")

    missing = []
    for package in required:
        try:
            __import__(package)
            print(f"{Colors.GREEN}✅ {package}{Colors.ENDC}")
        except ImportError:
            missing.append(package)
            print(f"{Colors.YELLOW}⚠️  {package} (missing){Colors.ENDC}")

    if missing:
        print(f"\n{Colors.YELLOW}Installing missing packages...{Colors.ENDC}")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", *missing, "-q"], check=False
        )
        print(f"{Colors.GREEN}✅ Dependencies installed{Colors.ENDC}\n")
    else:
        print(f"\n{Colors.GREEN}✅ All dependencies available{Colors.ENDC}\n")


def print_options():
    """Affiche les options"""
    print(f"{Colors.BOLD}{Colors.CYAN}Test Options:{Colors.ENDC}\n")

    print(f"{Colors.GREEN}1. test_menu.py{Colors.ENDC}")
    print(f"   └─ Interactive menu for all tests")
    print(f"   └─ {Colors.YELLOW}Recommended for beginners{Colors.ENDC}\n")

    print(f"{Colors.GREEN}2. performance_tests.py{Colors.ENDC}")
    print(f"   └─ Complete performance suite (all 8 tests)")
    print(f"   └─ Outputs JSON report\n")

    print(f"{Colors.GREEN}3. micro_benchmarks.py{Colors.ENDC}")
    print(f"   └─ Detailed timings with timeit & cProfile")
    print(f"   └─ Best for optimization\n")

    print(f"{Colors.BOLD}Or run directly from terminal:{Colors.ENDC}")
    print(f"   {Colors.CYAN}python test_menu.py{Colors.ENDC}")
    print(f"   {Colors.CYAN}python performance_tests.py{Colors.ENDC}")
    print(f"   {Colors.CYAN}python micro_benchmarks.py{Colors.ENDC}\n")


def main():
    """Main setup"""
    print_banner()

    # Vérifier dépendances
    install_requirements()

    # Créer répertoires si nécessaire
    Path("reports/execution").mkdir(parents=True, exist_ok=True)
    print(f"{Colors.GREEN}✅ Directories ready{Colors.ENDC}\n")

    # Afficher options
    print_options()

    # Lancer menu
    print(f"{Colors.BOLD}{Colors.YELLOW}Ready to run tests?{Colors.ENDC}")
    choice = input(f"\nLaunch test_menu.py now? (y/n): ").lower().strip()

    if choice == "y":
        print(f"\n{Colors.GREEN}Launching...{Colors.ENDC}\n")
        script = Path(__file__).parent / "test_menu.py"
        subprocess.run([sys.executable, str(script)])
    else:
        print(f"\n{Colors.CYAN}You can launch tests anytime with:{Colors.ENDC}")
        print(f"{Colors.YELLOW}python test_menu.py{Colors.ENDC}\n")


if __name__ == "__main__":
    import os

    os.chdir(Path(__file__).parent)
    print_banner()
    install_requirements()
    print_options()
