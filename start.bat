@echo off
echo.
echo  Job Application Tracker
echo  ========================
echo.

:: Check if venv exists
if not exist ".venv" (
    echo  Creating virtual environment...
    python -m venv .venv
    echo  Installing dependencies...
    .venv\Scripts\pip install -r requirements.txt --quiet
    echo  Done!
    echo.
)

:: Activate and run
call .venv\Scripts\activate.bat
echo  Starting server at http://localhost:5000
echo  Press Ctrl+C to stop.
echo.
start "" http://localhost:5000
python app.py
