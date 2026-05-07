#!/usr/bin/env python
"""
CAG Demo - Démonstration du Contextual Augmented Generation (RAG + Cache)
Montre les économies d'appels LLM grâce au cache intelligent
"""

import sys
import time
from pathlib import Path

import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.cag_engine import get_cag_engine
from src.llm_helper import get_transformation_rules, print_cag_stats, reset_cag_session
from src.profiler import build_dataset_profile


def create_sample_profile_1():
    """Crée un profil de dataset simple - Sales"""
    df = pd.DataFrame(
        {
            "id": range(1, 101),
            "name": ["Customer_" + str(i) for i in range(1, 101)],
            "email": ["customer" + str(i) + "@example.com" for i in range(1, 101)],
            "age": [25 + (i % 50) for i in range(100)],
            "amount": [100.0 + (i * 10.5) for i in range(100)],
        }
    )
    # Ajouter quelques valeurs manquantes
    df.loc[::10, "email"] = None
    df.loc[::15, "age"] = None
    return build_dataset_profile(df)


def create_sample_profile_2():
    """Crée un profil très similaire - Clients (structure identique)"""
    df = pd.DataFrame(
        {
            "id": range(1, 51),  # Nombre de lignes différent
            "name": ["Person_" + str(i) for i in range(1, 51)],
            "email": ["person" + str(i) + "@company.com" for i in range(1, 51)],
            "age": [30 + (i % 40) for i in range(50)],
            "amount": [200.0 + (i * 15.0) for i in range(50)],
        }
    )
    df.loc[::8, "email"] = None
    df.loc[::12, "age"] = None
    return build_dataset_profile(df)


def create_sample_profile_3():
    """Crée un profil très différent - Logistics"""
    df = pd.DataFrame(
        {
            "tracking_id": ["TRACK_" + str(i) for i in range(1, 201)],
            "status": ["Pending" if i % 3 == 0 else "Delivered" for i in range(200)],
            "weight_kg": [5.0 + (i * 0.1) for i in range(200)],
            "destination": ["City_" + str(i % 20) for i in range(200)],
            "date_created": pd.date_range("2024-01-01", periods=200),
        }
    )
    df.loc[::25, "weight_kg"] = None
    return build_dataset_profile(df)


def main():
    """Démontre l'efficacité du cache CAG"""

    print("\n" + "=" * 70)
    print("🚀 CAG DEMO - Contextual Augmented Generation (RAG + Cache)")
    print("=" * 70)
    print("\nCAG combine:")
    print("  • RAG: Contexte pertinent des règles de nettoyage")
    print("  • Cache: Réutilisation des réponses LLM pour structures similaires")
    print("  • Résultat: Économies d'appels LLM et de coûts API\n")

    # Reset session
    reset_cag_session()
    cag = get_cag_engine()

    # Test 1: Premier dataset
    print("-" * 70)
    print("📊 Test 1: Dataset SALES (100 clients)")
    print("-" * 70)
    profile1 = create_sample_profile_1()
    print(f"Colonnes: {', '.join([c['name'] for c in profile1['columns']])}")
    print(f"Structure: {profile1['n_rows']} lignes, {profile1['n_columns']} colonnes")

    start = time.time()
    print("\n🔄 Appel de get_transformation_rules()...")
    rules1 = get_transformation_rules(profile1, use_cache=True)
    elapsed1 = time.time() - start
    print(f"✓ Temps: {elapsed1:.2f}s")
    print(f"✓ Résultat: {len(rules1)} clés de transformation générées")

    stats = cag.get_stats()
    print(f"\n📈 Stats après Test 1:")
    print(f"   • Cache hits: {stats['cache_hits']}")
    print(f"   • Cache misses: {stats['cache_misses']}")
    print(f"   • LLM calls: {stats['llm_calls_avoided']}")

    # Test 2: Dataset similaire (devrait utiliser le cache)
    print("\n" + "-" * 70)
    print("📊 Test 2: Dataset CLIENTS (50 clients - structure SIMILAIRE)")
    print("-" * 70)
    profile2 = create_sample_profile_2()
    print(f"Colonnes: {', '.join([c['name'] for c in profile2['columns']])}")
    print(f"Structure: {profile2['n_rows']} lignes, {profile2['n_columns']} colonnes")

    start = time.time()
    print("\n🔄 Appel de get_transformation_rules()...")
    rules2 = get_transformation_rules(profile2, use_cache=True)
    elapsed2 = time.time() - start
    print(f"✓ Temps: {elapsed2:.2f}s")
    print(f"✓ Résultat: {len(rules2)} clés de transformation")

    stats = cag.get_stats()
    print(f"\n📈 Stats après Test 2:")
    print(f"   • Cache hits: {stats['cache_hits']}")
    print(f"   • Cache misses: {stats['cache_misses']}")
    print(f"   • LLM calls avoided: {stats['llm_calls_avoided']}")
    if stats["cache_hits"] > 0:
        print(f"   ⚡ Gain: {elapsed2:.2f}s économisé vs appel LLM")

    # Test 3: Dataset très différent (cache miss)
    print("\n" + "-" * 70)
    print("📊 Test 3: Dataset LOGISTICS (200 colis - structure DIFFÉRENTE)")
    print("-" * 70)
    profile3 = create_sample_profile_3()
    print(f"Colonnes: {', '.join([c['name'] for c in profile3['columns']])}")
    print(f"Structure: {profile3['n_rows']} lignes, {profile3['n_columns']} colonnes")

    start = time.time()
    print("\n🔄 Appel de get_transformation_rules()...")
    rules3 = get_transformation_rules(profile3, use_cache=True)
    elapsed3 = time.time() - start
    print(f"✓ Temps: {elapsed3:.2f}s")
    print(f"✓ Résultat: {len(rules3)} clés de transformation")

    stats = cag.get_stats()
    print(f"\n📈 Stats après Test 3:")
    print(f"   • Cache hits: {stats['cache_hits']}")
    print(f"   • Cache misses: {stats['cache_misses']}")
    print(f"   • Hit rate: {stats['hit_rate_percent']:.1f}%")
    print(f"   • LLM calls avoided: {stats['llm_calls_avoided']}")

    # Résumé final
    print("\n" + "=" * 70)
    print("📊 RÉSUMÉ FINAL - CAG Statistics")
    print("=" * 70)
    print_cag_stats()

    print("\n✅ CAG Demo terminée!")
    print("   • Le cache a évité", stats["cache_hits"], "appels LLM")
    print("   • Hit rate:", f"{stats['hit_rate_percent']:.1f}%")
    print("   • Économie potentielle: ~", f"${stats['cache_hits'] * 0.05:.2f}")
    print("   (Estimation basée sur ~$0.05 par appel GPT-4o-mini)\n")


if __name__ == "__main__":
    main()
