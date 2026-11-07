@echo off
echo Starting Metrixa Cockpit (FastAPI Backend + Next.js WebUI)...

start "Metrixa FastAPI Backend (:8000)" /D "%~dp0" cmd /k ".\.venv\Scripts\uvicorn.exe heidi_engine.api.server:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 3 /nobreak >nul

start "Metrixa Next.js WebUI (:3000)" /D "%~dp0web" cmd /k "npm run dev"

echo.
echo ==============================================================
echo METRIXA COCKPIT LAUNCHED SUCCESSFULLY
echo Web Application: http://localhost:3000
echo FastAPI Docs:    http://127.0.0.1:8000/docs
echo ==============================================================
echo.
