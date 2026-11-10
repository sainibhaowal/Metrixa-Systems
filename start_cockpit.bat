@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
cd /d "%ROOT%"

if not exist ".venv\Scripts\python.exe" (
    echo Python virtual environment is missing. Create it and install the project dependencies first.
    pause
    exit /b 1
)
if not exist "web\node_modules\next\dist\bin\next" (
    echo Frontend dependencies are missing. Run npm ci in the web folder first.
    pause
    exit /b 1
)

for /f "usebackq delims=" %%p in (`".venv\Scripts\python.exe" -c "from metrixa_engine.config import settings; print(settings.api_port)"`) do set "API_PORT=%%p"
if not defined API_PORT (
    echo Could not read API_PORT from the local settings.
    pause
    exit /b 1
)

rem Keep this launcher bound to this laptop. The browser API URL is embedded at build time.
set "API_HOST=127.0.0.1"
set "NEXT_PUBLIC_API_URL=http://127.0.0.1:%API_PORT%"

echo Building the production frontend...
pushd web
call npm run build
if errorlevel 1 (
    popd
    echo Frontend build failed. The app was not started.
    pause
    exit /b 1
)
popd

echo Starting the local API...
start "Metrixa API" /D "%ROOT%" cmd /k ".\.venv\Scripts\python.exe -m metrixa_engine"
set /a ATTEMPTS=0
:wait_api
set /a ATTEMPTS+=1
curl.exe --silent --show-error --fail --max-time 2 "http://127.0.0.1:%API_PORT%/api/metrics" >nul 2>nul
if not errorlevel 1 goto api_ready
if %ATTEMPTS% geq 30 (
    echo API did not become healthy. Check the Metrixa API window for the startup error.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto wait_api

:api_ready
echo Starting the production frontend...
start "Metrixa Web" /D "%ROOT%web" cmd /k "npm run start"
set /a ATTEMPTS=0
:wait_web
set /a ATTEMPTS+=1
curl.exe --silent --show-error --fail --max-time 2 "http://127.0.0.1:3000/" >nul 2>nul
if not errorlevel 1 goto app_ready
if %ATTEMPTS% geq 30 (
    echo Frontend did not become healthy. Check the Metrixa Web window for the startup error.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto wait_web

:app_ready
echo.
echo Metrixa is responding locally:
echo Web App:   http://127.0.0.1:3000
echo API Docs:  http://127.0.0.1:%API_PORT%/docs
start "" "http://127.0.0.1:3000"
exit /b 0
