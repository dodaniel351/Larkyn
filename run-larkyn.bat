@echo off
REM Launch Larkyn using the project's own virtual environment.
REM Double-click this file, or run it from a terminal. The console window
REM stays open so you can see startup logs; closing it quits the app.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv not found. Run setup first:
    echo     python -m venv .venv
    echo     .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo     .venv\Scripts\python.exe -m pip install -r requirements-gpu.txt
    pause
    exit /b 1
)
".venv\Scripts\python.exe" run.py
echo.
echo Larkyn has exited.
pause
