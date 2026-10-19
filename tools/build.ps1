param([switch]$SkipInstaller)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
& $pythonExe -m PyInstaller --noconfirm --windowed --onedir --name Paperlight --icon assets\paperlight.ico --add-data 'assets;assets' --add-data 'LICENSE;.' --add-data 'THIRD_PARTY_NOTICES.md;.' --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick main.py
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
& $pythonExe tools\fix_runtime.py
if ($LASTEXITCODE -ne 0) { throw 'Runtime dependency validation failed.' }
& $pythonExe tools\package_source.py
if ($LASTEXITCODE -ne 0) { throw 'Source packaging failed.' }
if ($SkipInstaller) { return }
$compiler = Join-Path $projectRoot '.scratch\tools\inno\ISCC.exe'
if (-not (Test-Path -LiteralPath $compiler)) { throw 'Inno Setup compiler is missing. See README.md.' }
& $compiler packaging\paperlight.iss
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed.' }
