@echo off
setlocal

set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"

if not exist "%PY%" (
    echo Python environment not found: %PY%
    echo Run:
    echo   python -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo Starting ETL Platform backend...
echo API:  http://127.0.0.1:8000
echo Docs: http://127.0.0.1:8000/docs
echo Press CTRL+C to stop.
echo.

cd /d "%ROOT%"
"%PY%" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
