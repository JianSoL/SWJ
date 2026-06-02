param(
    [string]$PythonExe = "C:\Users\ch\.conda\envs\QT\python.exe"
)

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

if (-not (Test-Path -LiteralPath $PythonExe)) {
    $PythonExe = "python"
}

Write-Host "Using Python: $PythonExe"
& $PythonExe -m PyInstaller --noconfirm --clean DCBMS.spec

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$ExePath = Join-Path $RepoRoot "dist\\DCBMS\\DCBMS.exe"
if (Test-Path -LiteralPath $ExePath) {
    Write-Host "Build complete: $ExePath"
} else {
    Write-Error "Build finished but executable was not found: $ExePath"
    exit 1
}
