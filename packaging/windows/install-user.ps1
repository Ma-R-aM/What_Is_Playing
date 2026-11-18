# Install WhatIsPlaying for the current Windows user, without administrator rights.
# Usage: powershell -ExecutionPolicy Bypass -File .\packaging\windows\install-user.ps1
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$appRoot = Join-Path $env:LOCALAPPDATA "WhatIsPlaying"
$appDir = Join-Path $appRoot "app"
$venv = Join-Path $appRoot "venv"
$binDir = Join-Path $env:LOCALAPPDATA "Programs\WhatIsPlaying"
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$shortcutPath = Join-Path $startMenu "WhatIsPlaying.lnk"
$requirements = Join-Path $repo "packaging\windows\requirements-windows.txt"

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -m venv $venv
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m venv $venv
} else {
    throw "Python 3.10 or newer is required. Install it from https://www.python.org/downloads/windows/"
}
if ($LASTEXITCODE -ne 0) {
    throw "Could not create the virtual environment."
}

$venvPython = Join-Path $venv "Scripts\python.exe"
$venvPythonw = Join-Path $venv "Scripts\pythonw.exe"

& $venvPython -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.10 or newer is required. Install it from https://www.python.org/downloads/windows/"
}

Write-Host "Installing Python dependencies..."
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r $requirements
if ($LASTEXITCODE -ne 0) {
    throw "Could not install the Windows dependencies."
}

Write-Host "Copying the application..."
New-Item -ItemType Directory -Force -Path $appDir | Out-Null
$target = Join-Path $appDir "whatisplaying"
if (Test-Path $target) {
    Remove-Item $target -Recurse -Force
}
Copy-Item (Join-Path $repo "desktop\whatisplaying") $target -Recurse
Get-ChildItem $appDir -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

# Make the copied package importable by the venv without a PYTHONPATH variable.
# UTF-8 without a BOM: Python reads .pth files as UTF-8 and a BOM would become
# part of the path.
$sitePackages = Join-Path $venv "Lib\site-packages"
$pthPath = Join-Path $sitePackages "whatisplaying.pth"
[System.IO.File]::WriteAllText(
    $pthPath,
    $appDir,
    (New-Object System.Text.UTF8Encoding $false)
)

Write-Host "Creating launchers..."
New-Item -ItemType Directory -Force -Path $binDir | Out-Null
$launcher = Join-Path $binDir "whatisplaying.cmd"
# Expand LOCALAPPDATA at run time so the launcher stays ASCII-only and works
# when the user profile path contains non-ASCII characters.
$launcherLines = @(
    "@echo off",
    "`"%LOCALAPPDATA%\WhatIsPlaying\venv\Scripts\python.exe`" -m whatisplaying %*",
    "exit /b %ERRORLEVEL%"
)
Set-Content -Path $launcher -Value $launcherLines -Encoding ASCII

New-Item -ItemType Directory -Force -Path $startMenu | Out-Null
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $venvPythonw
$shortcut.Arguments = "-m whatisplaying"
$shortcut.WorkingDirectory = $appDir
$shortcut.Description = "Share what you are listening to as a Discord custom status"
$shortcut.Save()

Write-Host ""
Write-Host "Installed."
Write-Host "  Launch from the Start menu, or run:"
Write-Host "    $launcher"
Write-Host "  Add $binDir to PATH if you want to run 'whatisplaying' from any terminal."
