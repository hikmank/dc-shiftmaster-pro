@echo off
echo === DC-ShiftMaster Pro - Build Script ===
echo.
echo Installing dependencies...
pip install -r dc_shiftmaster\requirements.txt
pip install pyinstaller
echo.
echo Building .exe...
pyinstaller --onefile --windowed --name "DC-ShiftMaster-Pro" ^
    --icon "dc_shiftmaster\app_icon.ico" ^
    --add-data "dc_shiftmaster\app_icon.ico;dc_shiftmaster" ^
    --collect-all customtkinter ^
    dc_shiftmaster\main.py
echo.
if exist "dist\DC-ShiftMaster-Pro.exe" (
    echo Copying to Desktop...
    for /f "tokens=*" %%D in ('powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"') do set DESKTOP=%%D
    copy "dist\DC-ShiftMaster-Pro.exe" "%DESKTOP%\DC-ShiftMaster-Pro.exe"
    echo.
    echo Done! DC-ShiftMaster-Pro.exe is on your Desktop.
) else (
    echo Build failed — check the output above for errors.
)
pause
