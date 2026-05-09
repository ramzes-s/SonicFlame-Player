@echo off
cd /d "%~dp0"

echo === Building SonicFlame Player (single-file exe) ===
echo.

REM Clean previous build
echo [1/3] Cleaning previous build...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

REM Build using spec file (all hidden-imports configured)
echo [2/3] Building exe...
.venv\Scripts\python.exe -m PyInstaller --noconfirm SonicFlame.spec

echo.
echo [3/3] Verifying output...
echo === Build complete! ===
echo Output: dist\SonicFlame Player.exe
echo.
if exist "dist\SonicFlame Player.exe" (
    echo File size:
    for %%A in ("dist\SonicFlame Player.exe") do echo   %%~zA bytes
    echo.
    explorer dist
) else (
    echo ERROR: Build failed! Check the log above.
    pause
)
