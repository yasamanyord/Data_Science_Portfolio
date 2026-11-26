@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -3.12 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m warehouse demo
if errorlevel 1 goto fail
echo Open http://127.0.0.1:8000 in your browser. Press Ctrl+C to stop.
.venv\Scripts\python.exe -m uvicorn warehouse.api:app --host 127.0.0.1 --port 8000
exit /b %errorlevel%
:fail
echo Setup failed. Check Python 3.12 and the installation output.
pause
exit /b 1
