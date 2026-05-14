"""
Job Tracker Launcher
- Double-click to start
- Opens dashboard as a standalone app window
- Close the window to stop everything
"""
import subprocess
import sys
import time
import os
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable
CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]

def find_chrome():
    for path in CHROME_PATHS:
        if os.path.exists(path):
            return path
    return None

# Start Flask server
flask_proc = subprocess.Popen(
    [PYTHON, 'app.py'],
    cwd=BASE_DIR,
    creationflags=subprocess.CREATE_NO_WINDOW,
)

# Wait for Flask to be ready
time.sleep(2)

# Open Chrome as standalone app window
chrome = find_chrome()
if not chrome:
    import ctypes
    ctypes.windll.user32.MessageBoxW(0, "Chrome not found. Please install Google Chrome.", "Job Tracker", 0)
    flask_proc.terminate()
    sys.exit(1)

chrome_proc = subprocess.Popen([
    chrome,
    '--app=http://localhost:5000',
    '--window-size=1400,900',
    '--disable-extensions',
])

# Wait for Chrome window to be closed by user
chrome_proc.wait()

# Chrome closed — stop Flask
flask_proc.terminate()
