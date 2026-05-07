import os

import pandas as pd

print("=" * 80)
print("ANALYSE STRUCTURE RÉELLE DES DONNÉES SALES")
print("=" * 80)

# Chercher le fichier Excel
upload_dir = "backend/uploads"
excel_files = [f for f in os.listdir(upload_dir) if f.endswith((".xlsx", ".xls"))]

if not excel_files:
    print(f"❌ Aucun fichier Excel trouvé dans {upload_dir}")
else:
    for file in excel_files:
        file_path = os.path.join(upload_dir, file)
        print(f"\n📄 Fichier: {file}")
        print(f"📊 Chemin: {file_path}")

        try:
            # Lire avec pandas
            df = pd.read_excel(file_path, sheet_name=0)

            print(f"\n✅ Dimensions: {df.shape[0]} lignes × {df.shape[1]} colonnes")

            print(f"\n🏷️  En-têtes (colonnes):")
            for i, col in enumerate(df.columns):
                print(f"   Col {i}: '{col}' (type en-tête: {type(col).__name__})")

            print(f"\n📋 Premières 5 lignes:")
            print(df.head(5).to_string())

            print(f"\n🔍 Types de données:")
            print(df.dtypes)

            print(f"\n📈 Statistiques:")
            print(df.describe())

            print(f"\n⚠️  Valeurs manquantes:")
            print(df.isnull().sum())

        except Exception as e:
            print(f"❌ Erreur lecture: {e}")
            import traceback

            traceback.print_exc()
