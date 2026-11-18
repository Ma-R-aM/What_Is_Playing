# Run WhatIsPlaying directly from this checkout on Windows.
# Usage: .\packaging\windows\run-source.ps1 [--list-players] [--debug]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $AppArgs
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$env:PYTHONPATH = (Join-Path $repo "desktop")

if (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m whatisplaying @AppArgs
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -m whatisplaying @AppArgs
} else {
    throw "Python 3.10 or newer is required. Install it from https://www.python.org/downloads/windows/"
}
exit $LASTEXITCODE
