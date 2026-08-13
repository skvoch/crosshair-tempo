$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
git -C $projectRoot config core.hooksPath .githooks
Write-Host "Crosshair Tempo Git hooks installed."
