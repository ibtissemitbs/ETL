@echo off
REM ETL Platform - Démarrage du serveur backend
REM Assurez-vous d'être dans le dossier ETL avant de lancer ce script

echo.
echo ====================================
echo  🔧 ETL Platform - Backend Server
echo ====================================
echo.

REM Vérifier la présence de Python
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo ❌ Python du projet introuvable: .venv\Scripts\python.exe
    pause
    exit /b 1
)

"%~dp0.venv\Scripts\python.exe" --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python du projet n'est pas utilisable
    pause
    exit /b 1
)

REM Aller dans le dossier backend
cd /d "%~dp0backend"

REM Vérifier la présence de main.py
if not exist "main.py" (
    echo ❌ Erreur: main.py non trouvé!
    echo   Assurez-vous que le script est dans le dossier ETL
    pause
    exit /b 1
)

echo ✓ Démarrage du serveur...
echo.
echo 📍 Backend disponible sur: http://localhost:8000
echo 📚 Documentation API: http://localhost:8000/docs
echo 🛑 Appuyez sur CTRL+C pour arrêter le serveur
echo.

REM Lancer le serveur avec le Python du projet pour garantir les dépendances
"%~dp0.venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000

pause
