@echo off
title DC-ShiftMaster Pro
cd /d "C:\Users\hikmank\Documents\Kiro - App Development"

call ".venv\Scripts\activate.bat"

echo Starting DC-ShiftMaster Pro...
echo Open http://127.0.0.1:5000 in your browser
echo Default password: shiftmaster
echo Press Ctrl+C to stop the server
echo.

start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:5000"

python -m dc_shiftmaster_html
pause
