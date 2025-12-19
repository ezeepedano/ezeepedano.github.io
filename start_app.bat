@echo off
TITLE Portal.flow ERP Server
echo Starting Portal.flow ERP...
echo.

cd /d "%~dp0"

:: Check if venv exists
if not exist "venv" (
    echo Virtual environment not found! Please run setup first.
    pause
    exit
)

:: Activate venv
call venv\Scripts\activate

:: Open Browser
timeout /t 3 >nul
start "" http://127.0.0.1:8000

:: Run Server
echo Server running at http://127.0.0.1:8000
echo Close this window to stop the ERP.
echo.
python manage.py runserver

pause
