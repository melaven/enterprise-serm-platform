@echo off
cd /d "c:\Users\Malyarenko17\Desktop\ОСНОВНЫЕ ПРОЕКТЫ\Tenable SERM"
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload