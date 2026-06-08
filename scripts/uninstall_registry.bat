@echo off
setlocal EnableExtensions
title PyGiffer - Uninstall context menu

net session >nul 2>&1
if %errorLevel% == 0 goto :run

echo Requesting administrator privileges...
powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs -Wait"
exit /b %ERRORLEVEL%

:run
echo.
echo PyGiffer context menu uninstaller
echo.

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_internal\install_registry.ps1" -Action uninstall -Root "%ROOT%"
exit /b %ERRORLEVEL%
