@echo off
rem Run WhatIsPlaying directly from this checkout on Windows.
setlocal
set "PYTHONPATH=%~dp0..\..\desktop"
where python >nul 2>nul
if errorlevel 1 (
    py -3 -m whatisplaying %*
) else (
    python -m whatisplaying %*
)
exit /b %ERRORLEVEL%
