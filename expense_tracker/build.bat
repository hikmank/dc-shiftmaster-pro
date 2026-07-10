@echo off
echo === ExpenseTracker Pro - Build Script ===
echo.
echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller
echo.
echo Building .exe...
pyinstaller --onefile --windowed --name "ExpenseTracker Pro" --add-data "ui;ui" --add-data "utils;utils" main.py
echo.
echo Done! Your .exe is in the dist\ folder.
echo Copy "dist\ExpenseTracker Pro.exe" to your Desktop.
pause
