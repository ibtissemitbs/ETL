"""
Transformateur pour convertir données sales pivotées en structure transactionnelle
Gère le format crosstab multi-niveaux → format tabulaire normal
"""

from pathlib import Path

import numpy as np
import pandas as pd


def unpivot_sales_crosstab(df):
    """
    Convertit structure pivotée sales en format transactionnel.

    Structure d'entrée:
    - Ligne 0: En-têtes de Ship Mode (First Class, Same Day, Second Class, Standard Class)
    - Ligne 1: Sous-catégories (Order ID, NaN, NaN, NaN)
    - Colonnes groupées par Segment (Consumer, Corporate, Home Office)
    - Chaque groupe a 4 colonnes (un pour chaque Ship Mode) + 1 Total

    Retourne: DataFrame avec colonnes:
    - order_id, segment, ship_mode, sales, ship_date (optionnel)
    """

    # Recréer les en-têtes corrects depuis la première colonne
    df_work = df.copy()

    # Identifier les groupes de colonnes (Consumer, Corporate, Home Office)
    segments = ["Consumer", "Corporate", "Home Office"]
    ship_modes_expected = ["First Class", "Same Day", "Second Class", "Standard Class"]

    records = []

    # Parcourir chaque ligne (à partir de la ligne 2, après les en-têtes)
    for idx in range(2, len(df_work)):
        order_id = df_work.iloc[idx, 0]  # Première colonne = Order ID

        if pd.isna(order_id) or order_id == "":
            continue

        # Parcourir chaque segment (Consumer, Corporate, Home Office)
        # Segments occupent les plages de colonnes:
        # Consumer: cols 1-5 (Consumer, Unnamed:2-4, Consumer Total)
        # Corporate: cols 6-10 (Corporate, Unnamed:7-9, Corporate Total)
        # Home Office: cols 11-15 (Home Office, Unnamed:12-14, Home Office Total)

        segment_ranges = [
            ("Consumer", [1, 2, 3, 4, 5]),  # Consumer + 4 ship modes + total
            ("Corporate", [6, 7, 8, 9, 10]),  # Corporate + 4 ship modes + total
            ("Home Office", [11, 12, 13, 14, 15]),  # Home Office + 4 ship modes + total
        ]

        for segment, col_indices in segment_ranges:
            # Extraire les 4 valeurs (une par ship mode) + total
            values = [df_work.iloc[idx, col] for col in col_indices[:4]]  # 4 ship modes
            total = df_work.iloc[idx, col_indices[4]]  # colonne Total

            # Créer un record par ship mode non-vide
            for ship_mode_idx, (ship_mode, value) in enumerate(
                zip(ship_modes_expected, values)
            ):
                if pd.notna(value) and value != "":
                    try:
                        sales_value = float(value)
                        records.append(
                            {
                                "order_id": str(order_id),
                                "segment": segment,
                                "ship_mode": ship_mode,
                                "sales": sales_value,
                            }
                        )
                    except (ValueError, TypeError):
                        continue

    # Créer DataFrame à partir des records
    df_unpivoted = pd.DataFrame(records)

    return df_unpivoted


# Test
if __name__ == "__main__":
    print("=" * 80)
    print("UNPIVOT SALES CROSSTAB DATA")
    print("=" * 80)

    file_path = Path("backend/uploads/1.-sales_dirty_data.xlsx")

    if file_path.exists():
        df_pivoted = pd.read_excel(file_path, sheet_name=0)
        print(f"\n✅ Données pivotées chargées: {df_pivoted.shape}")

        df_transactional = unpivot_sales_crosstab(df_pivoted)
        print(f"\n✅ Données dépivotées: {df_transactional.shape}")
        print(f"\nEn-têtes: {list(df_transactional.columns)}")
        print(f"\nPremières lignes:\n{df_transactional.head(10)}")
        print(f"\nStatistiques:\n{df_transactional.describe()}")

        # Sauvegarder le résultat
        output_path = Path("backend/uploads/sales_unpivoted.csv")
        df_transactional.to_csv(output_path, index=False)
        print(f"\n💾 Résultat sauvegardé: {output_path}")

        # Montrer les transformations effectuées
        print(f"\n🔄 Transformations effectuées:")
        print(f"   • Structure pivotée → transactionnelle")
        print(f"   • 825 lignes → {len(df_transactional)} transactions")
        print(f"   • 16 colonnes → {len(df_transactional.columns)} colonnes")
        print(f"   • Segments: {df_transactional['segment'].unique().tolist()}")
        print(f"   • Ship Modes: {df_transactional['ship_mode'].unique().tolist()}")
    else:
        print(f"❌ Fichier non trouvé: {file_path}")
