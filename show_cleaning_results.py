"""
Afficher les résultats du nettoyage - données avant/après
"""

from pathlib import Path

import pandas as pd

print("=" * 80)
print("RÉSULTATS DU NETTOYAGE AUTOMATIQUE - AVANT / APRÈS")
print("=" * 80)

# Charger les données
orig_file = Path("backend/uploads/1.-sales_dirty_data.xlsx")
transformed_file = Path("backend/uploads/sales_transformed.csv")

if orig_file.exists():
    df_orig = pd.read_excel(orig_file)
    print(f"\n📥 AVANT (structure pivotée):")
    print(f"   Fichier: {orig_file.name}")
    print(f"   Dimensions: {df_orig.shape[0]} lignes × {df_orig.shape[1]} colonnes")
    print(f"   Colonnes: {list(df_orig.columns)}")
    print(
        f"   NaN: {df_orig.isnull().sum().sum()} ({df_orig.isnull().sum().sum() / (df_orig.shape[0] * df_orig.shape[1]):.1%})"
    )
    print(f"\n   Premières 5 lignes:")
    print(f"   {df_orig.head(5).to_string()}")

if transformed_file.exists():
    df_transformed = pd.read_csv(transformed_file)
    print(f"\n✅ APRÈS (structure transactionnelle + nettoyée):")
    print(f"   Fichier: {transformed_file.name}")
    print(
        f"   Dimensions: {df_transformed.shape[0]} lignes × {df_transformed.shape[1]} colonnes"
    )
    print(f"   Colonnes: {list(df_transformed.columns)}")
    print(
        f"   NaN: {df_transformed.isnull().sum().sum()} ({df_transformed.isnull().sum().sum() / (df_transformed.shape[0] * df_transformed.shape[1]):.1%})"
    )
    print(f"\n   Premières 10 lignes:")
    print(f"   {df_transformed.head(10).to_string()}")

    print(f"\n   Statistiques:")
    print(
        f"   - Catégories uniques: {df_transformed['category'].nunique()} ({df_transformed['category'].unique().tolist()})"
    )
    print(
        f"   - Types uniques: {df_transformed['type'].nunique()} ({df_transformed['type'].unique().tolist()})"
    )
    print(
        f"   - Valeurs min/max: {df_transformed['value'].min():.2f} / {df_transformed['value'].max():.2f}"
    )

print(f"\n" + "=" * 80)
print(f"✅ LE SYSTÈME A TRANSFORMÉ ET NETTOYÉ LES DONNÉES AUTOMATIQUEMENT")
print(f"=" * 80)
