@echo off
setlocal

set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"
set "APP_URL=http://127.0.0.1:8000/"

if not exist "%PY%" (
    echo Python environment not found: %PY%
    echo Create it, then run: pip install -r requirements.txt
    pause
    exit /b 1
)

echo Starting ETL backend...
echo URL: %APP_URL%

start "ETL Backend" /min "%PY%" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

timeout /t 3 /nobreak >nul
start "" "%APP_URL%"

echo.
echo ETL Platform is opening in your browser.
echo Keep the backend window running while using the app.
echo.
pause
