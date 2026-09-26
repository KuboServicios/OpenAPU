param([string]$Version = "2026.09")
$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $PSScriptRoot
$releaseDir = Join-Path $PSScriptRoot "portable-release"
$staging = Join-Path $releaseDir "OpenAPU-Windows"
$archive = Join-Path $releaseDir "OpenAPU-Windows.zip"
$application = Join-Path $staging "Aplicacion"
$documentation = Join-Path $application "documentacion"
$runtime = Join-Path $application "runtime"
if (Test-Path $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
if (Test-Path $archive) { Remove-Item -LiteralPath $archive -Force }
New-Item -ItemType Directory -Path $application,$documentation,$runtime -Force | Out-Null

$files = @("server.py","index.html","gg_default_template.js","converter.py","apu.py","account_store.py","app_paths.py","resource_catalog.py","export_apu_pdf.py","export_excel.py","export_view_report.py","export_apu_excel.mjs","export_itemized_excel.mjs","export_view_report.mjs","requirements.txt")
foreach ($relative in $files) { $source=Join-Path $project $relative; if(-not(Test-Path $source)){throw "Falta $relative"}; Copy-Item -LiteralPath $source -Destination (Join-Path $application $relative) -Force }
$docs = @("MCP_CODEX.md","REGLAS_GENERACION_APU.md","REGLAS_NORMALIZACION.md","REGLA_NOMENCLATURA_RECURSOS.md","REGLA_ANALISIS_MANO_OBRA.md","REGLA_ANALISIS_FLUJO_COSTOS.md","SECURITY.md","LICENSE")
foreach ($relative in $docs) { Copy-Item -LiteralPath (Join-Path $project $relative) -Destination (Join-Path $documentation $relative) -Force }
Copy-Item -LiteralPath (Join-Path $project "INICIAR OPENAPU.cmd") -Destination (Join-Path $staging "INICIAR OPENAPU.cmd") -Force
Copy-Item -LiteralPath (Join-Path $project "LEEME - EMPIEZA AQUI.html") -Destination (Join-Path $staging "LEEME - EMPIEZA AQUI.html") -Force
New-Item -ItemType Directory -Path (Join-Path $application "assets") -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $project "assets\fonts") -Destination (Join-Path $application "assets\fonts") -Recurse -Force

$pythonLauncher=Get-Command py.exe -ErrorAction SilentlyContinue
if($pythonLauncher){$pythonExe=(& $pythonLauncher.Source -3 -c "import sys; print(sys.executable)").Trim()}else{$pythonExe=(Get-Command python.exe -ErrorAction Stop).Source}
$pythonRoot=(& $pythonExe -c "import sys; print(sys.base_prefix)").Trim()
Get-ChildItem -LiteralPath $pythonRoot -File | Where-Object { $_.Name -in @('python.exe','pythonw.exe','python3.dll','vcruntime140.dll','vcruntime140_1.dll','LICENSE.txt') -or $_.Name -match '^python3\d+\.dll$' } | Copy-Item -Destination $runtime -Force
Copy-Item -LiteralPath (Join-Path $pythonRoot "DLLs") -Destination (Join-Path $runtime "DLLs") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $pythonRoot "Lib") -Destination (Join-Path $runtime "Lib") -Recurse -Force
$sitePackages=Join-Path $runtime "Lib\site-packages"
if(Test-Path $sitePackages){Remove-Item -LiteralPath $sitePackages -Recurse -Force}
New-Item -ItemType Directory -Path $sitePackages -Force | Out-Null
& $pythonExe -m pip install --disable-pip-version-check --no-warn-script-location --target $sitePackages -r (Join-Path $project "requirements.txt")
if($LASTEXITCODE -ne 0){throw "No fue posible incorporar dependencias"}
& (Join-Path $runtime "python.exe") -E -c "import urllib.parse,mimetypes,openpyxl,xlrd,PIL,reportlab,cryptography; print('OpenAPU verificado')"
if($LASTEXITCODE -ne 0){throw "El entorno integrado no superó la verificación"}
Compress-Archive -Path $staging -DestinationPath $archive -CompressionLevel Optimal
[pscustomobject]@{Version=$Version;File=$archive;Size=(Get-Item $archive).Length;SHA256=(Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant()}|ConvertTo-Json
