$ErrorActionPreference = 'Stop'
$openApuRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue

if (-not $pythonCommand) {
    Write-Host 'OpenAPU requiere Python 3.11 o superior.' -ForegroundColor Red
    Read-Host 'Presiona Enter para cerrar'
    exit 1
}

Set-Location -LiteralPath $openApuRoot
& $pythonCommand.Source -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $pythonCommand.Source server.py --port 8767

