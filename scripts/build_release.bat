@echo off
setlocal EnableExtensions

cd /d "%~dp0.."

set "CLEAN=0"
set "PACK=0"
if /I "%~1"=="clean" set "CLEAN=1"
if /I "%~1"=="--clean" set "CLEAN=1"
if /I "%~1"=="pack" set "PACK=1"
if /I "%~2"=="pack" set "PACK=1"

echo [1/5] Stopping running PyGiffer processes...
taskkill /IM pygiffer.exe /F >nul 2>&1
taskkill /IM pygiffer-cli.exe /F >nul 2>&1

echo [2/5] Generating icon assets...
".\.venv\Scripts\python.exe" scripts\generate_assets.py
if errorlevel 1 exit /b 1

echo.
echo [3/5] Building onedir release (PyInstaller: GUI + CLI)...
".\.venv\Scripts\pip.exe" install -q -r requirements-build.txt
if "%CLEAN%"=="1" (
  echo        clean rebuild ^(--clean^)
  ".\.venv\Scripts\pyinstaller.exe" --noconfirm --clean pygiffer.spec
) else (
  echo        incremental rebuild
  ".\.venv\Scripts\pyinstaller.exe" --noconfirm pygiffer.spec
)
if errorlevel 1 exit /b 1

echo.
echo [4/5] Staging layout (CLI into _internal + registry scripts)...
".\.venv\Scripts\python.exe" scripts\post_build_layout.py
if errorlevel 1 exit /b 1

if "%PACK%"=="1" (
  echo.
  echo [5/5] Packaging layered update assets ^(app + deps + manifest^)...
  ".\.venv\Scripts\python.exe" scripts\package_release.py
  if errorlevel 1 exit /b 1
)

echo.
echo Done. Release folder: dist\pygiffer\
echo   pygiffer.exe          GUI ^(PyQt^)
echo   _internal\pygiffer-cli.exe   CLI ^(convert / merge^)
echo.
exit /b 0
