@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Avval virtual muhit yaratib, kutubxonalarni o'rnating:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8019 --reload
