"""
Détecteur de structure de données - identifie le format et applique le transformateur approprié
"""

from typing import Dict, Tuple

import numpy as np
import pandas as pd


class DataStructureDetector:
    """Détecte la structure des données et applique les transformations nécessaires"""

    @staticmethod
    def detect_structure(df: pd.DataFrame) -> str:
        """
        Détecte le type de structure des données.
        Retourne: 'pivoted', 'transactional', ou 'unknown'
        """
        if df.shape[0] < 2 or df.shape[1] < 3:
            return "unknown"

        # Heuristiques pour détecter les structures pivotées
        # 1. Présence de beaucoup de colonnes 'Unnamed:X'
        unnamed_cols = [c for c in df.columns if "Unnamed" in str(c)]
        unnamed_ratio = (
            len(unnamed_cols) / len(df.columns) if len(df.columns) > 0 else 0
        )

        # 2. Présence de totaux (colonnes se terminant par 'Total')
        total_cols = [c for c in df.columns if "Total" in str(c)]

        # 3. Beaucoup de NaN
        nan_ratio = df.isnull().sum().sum() / (df.shape[0] * df.shape[1])

        # 4. Premiers lignes contiennent des en-têtes (pas de données numériques)
        first_row_non_numeric = sum(
            1 for v in df.iloc[0] if pd.isna(v) or isinstance(v, str)
        )
        first_row_ratio = first_row_non_numeric / len(df.columns)

        # Critères de détection
        is_pivoted = (
            unnamed_ratio > 0.3  # Au moins 30% de colonnes 'Unnamed'
            and len(total_cols) >= 2  # Au moins 2 colonnes 'Total'
            and nan_ratio > 0.5  # Au moins 50% de NaN
        )

        if is_pivoted:
            return "pivoted"
        else:
            return "transactional"

    @staticmethod
    def describe_structure(df: pd.DataFrame) -> Dict:
        """Retourne une description détaillée de la structure"""
        return {
            "rows": df.shape[0],
            "columns": df.shape[1],
            "unnamed_count": len([c for c in df.columns if "Unnamed" in str(c)]),
            "total_count": len([c for c in df.columns if "Total" in str(c)]),
            "nan_ratio": round(
                df.isnull().sum().sum() / (df.shape[0] * df.shape[1]), 2
            ),
            "column_names": list(df.columns),
        }


class DataTransformer:
    """Applique les transformations appropriées selon la structure"""

    @staticmethod
    def transform(df: pd.DataFrame, structure_type: str) -> pd.DataFrame:
        """Applique la transformation appropriée"""
        if structure_type == "pivoted":
            return DataTransformer.unpivot_crosstab(df)
        else:
            return df.copy()

    @staticmethod
    def unpivot_crosstab(df: pd.DataFrame) -> pd.DataFrame:
        """
        Convertit structure pivotée (crosstab) en format transactionnel.
        Gère les structures multi-niveaux comme:
        Segment >> | Consumer (Ship Modes) | Consumer Total | Corporate (Ship Modes) | Corporate Total | ...
        """
        df_work = df.copy()

        # Identifier les groupes de colonnes par les patterns de noms
        # Chercher les colonnes 'Total' qui marquent la fin de chaque groupe
        total_cols = [i for i, c in enumerate(df_work.columns) if "Total" in str(c)]

        records = []

        # À partir de la ligne 2 (après les en-têtes)
        for idx in range(2, len(df_work)):
            order_id = df_work.iloc[idx, 0]  # Première colonne = identifiant principal

            if pd.isna(order_id) or str(order_id).strip() == "":
                continue

            # Pour chaque groupe (délimité par les colonnes Total)
            start_col = 1
            for total_col in total_cols:
                # Colonnes du groupe: de start_col à total_col (inclus)
                group_cols = list(range(start_col, total_col))

                if len(group_cols) == 0:
                    start_col = total_col + 1
                    continue

                # Récupérer le nom du groupe (2e ligne)
                group_name = str(df_work.iloc[1, start_col])
                if pd.isna(group_name) or group_name == "" or group_name == "nan":
                    group_name = str(df_work.columns[start_col])

                # Récupérer les valeurs pour ce groupe
                values = []
                for col_idx in group_cols:
                    val = df_work.iloc[idx, col_idx]
                    values.append(val)

                # Créer des records à partir des valeurs non-NaN
                for col_idx, (orig_col_idx, value) in enumerate(
                    zip(group_cols, values)
                ):
                    if pd.notna(value) and str(value).strip() != "":
                        try:
                            val_numeric = float(value)
                            # Récupérer le label de colonne (ship mode, etc.)
                            col_label = str(df_work.iloc[0, orig_col_idx])
                            if (
                                pd.isna(col_label)
                                or col_label == ""
                                or col_label == "nan"
                            ):
                                col_label = f"Type_{col_idx}"

                            records.append(
                                {
                                    "id": str(order_id),
                                    "category": group_name,
                                    "type": col_label,
                                    "value": val_numeric,
                                }
                            )
                        except (ValueError, TypeError):
                            continue

                start_col = total_col + 1

        df_result = pd.DataFrame(records)
        return df_result if len(df_result) > 0 else df_work


# Test
if __name__ == "__main__":
    print("=" * 80)
    print("DATA STRUCTURE DETECTOR & TRANSFORMER")
    print("=" * 80)

    # Tester sur le fichier sales
    from pathlib import Path

    file_path = Path("backend/uploads/1.-sales_dirty_data.xlsx")

    if file_path.exists():
        df = pd.read_excel(file_path, sheet_name=0)
        print(f"\n📊 Fichier chargé: {file_path}")
        print(f"   Dimensions: {df.shape}")

        # Détecter la structure
        structure = DataStructureDetector.detect_structure(df)
        print(f"\n🔍 Structure détectée: {structure}")

        # Décrire la structure
        description = DataStructureDetector.describe_structure(df)
        print(f"\n📋 Description:")
        for key, val in description.items():
            print(f"   {key}: {val}")

        # Transformer
        if structure == "pivoted":
            print(f"\n🔄 Application du transformateur unpivot...")
            df_transformed = DataTransformer.transform(df, structure)
            print(f"   ✅ Résultat: {df_transformed.shape}")
            print(f"   Colonnes: {list(df_transformed.columns)}")
            print(f"\n   Premières lignes:")
            print(df_transformed.head(10))

            # Sauvegarder
            output_path = Path("backend/uploads/sales_transformed.csv")
            df_transformed.to_csv(output_path, index=False)
            print(f"\n💾 Résultat sauvegardé: {output_path}")
    else:
        print(f"❌ Fichier non trouvé: {file_path}")
