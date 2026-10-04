@echo off
rem Starts SynapSet School on its own, independent of Claude. Close the two windows to stop it.
cd /d "%~dp0"
start "SynapSet backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --port 8001"
start "SynapSet frontend" cmd /k "npm run dev"
timeout /t 8 /nobreak >nul
start http://localhost:5174
