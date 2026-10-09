@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo Starting FastAPI with Gemini API...
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload