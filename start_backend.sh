#!/bin/bash
# ETL Platform - Démarrage du serveur backend

echo ""
echo "===================================="
echo "  🔧 ETL Platform - Backend Server"
echo "===================================="
echo ""

# Vérifier que nous sommes dans le bon répertoire
if [ ! -f "backend/main.py" ]; then
    echo "❌ Erreur: main.py non trouvé!"
    echo "   Exécutez ce script depuis le dossier ETL"
    exit 1
fi

# Aller dans le dossier backend
cd backend

if [ ! -x "../.venv/Scripts/python.exe" ]; then
    echo "❌ Python du projet introuvable: .venv/Scripts/python.exe"
    exit 1
fi

echo "✓ Démarrage du serveur..."
echo ""
echo "📍 Backend disponible sur: http://localhost:8000"
echo "📚 Documentation API: http://localhost:8000/docs"
echo "🛑 Appuyez sur CTRL+C pour arrêter le serveur"
echo ""

# Lancer le serveur avec le Python du projet pour garantir les dépendances
"../.venv/Scripts/python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000
