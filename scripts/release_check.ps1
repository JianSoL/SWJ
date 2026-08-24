param(
    [string]$PythonExe = "C:\Users\ch\.conda\envs\QT\python.exe",
    [switch]$Build
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if (-not (Test-Path -LiteralPath $PythonExe)) {
    $PythonExe = "python"
}

$RequiredFiles = @(
    "ControlCANFD.dll",
    "DCFDV1.3.dbc",
    "DCBMS.spec",
    "CANFD\conf.yaml",
    "CANFD\SINGLE\BCU.yaml",
    "CANFD\resources\index_catalog.json",
    "CANFD\UI\release_theme.qss",
    "CANFD\1.ico",
    "CANFD\alarm.wav"
)

foreach ($RelativePath in $RequiredFiles) {
    $FullPath = Join-Path $RepoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $FullPath)) {
        throw "Missing release file: $RelativePath"
    }
}

$env:QT_QPA_PLATFORM = "offscreen"

Write-Host "Using Python: $PythonExe"
& $PythonExe -m py_compile `
    "main.py" `
    "CANFD\main.py" `
    "CANFD\application\runtime.py" `
    "CANFD\application\config_loader.py" `
    "CANFD\application\power_diagnostics.py" `
    "CANFD\application\trend_store.py" `
    "CANFD\domain\index_catalog.py" `
    "CANFD\presentation\index_browser_dialog.py" `
    "CANFD\presentation\power_diagnostic_page.py" `
    "CANFD\presentation\system_kline_page.py" `
    "CANFD\presentation\main_window.py"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $PythonExe -m unittest discover -s "CANFD\tests" -p "test_*.py" -v
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if ($Build) {
    & powershell -ExecutionPolicy Bypass -File ".\build_exe.ps1" -PythonExe $PythonExe -SkipChecks
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Write-Host "Release check passed."
