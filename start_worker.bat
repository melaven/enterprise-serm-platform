@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo Starting ARQ Worker with Gemini API...
.venv\Scripts\python.exe -m app.worker.worker