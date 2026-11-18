# Remove a per-user WhatIsPlaying installation.
# The Discord token in %APPDATA%\whatisplaying\config.json is kept.
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$appRoot = Join-Path $env:LOCALAPPDATA "WhatIsPlaying"
$binDir = Join-Path $env:LOCALAPPDATA "Programs\WhatIsPlaying"
$shortcutPath = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\WhatIsPlaying.lnk"

Remove-Item -Path $shortcutPath -Force -ErrorAction SilentlyContinue
Remove-Item -Path $binDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path $appRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" `
    -Name "WhatIsPlaying" -ErrorAction SilentlyContinue

Write-Host "Uninstalled. Your settings were kept in $env:APPDATA\whatisplaying."
