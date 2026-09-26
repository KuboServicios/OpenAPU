@echo off
setlocal
chcp 65001 >nul
title OpenAPU
cd /d "%~dp0"

if exist "Aplicacion\runtime\python.exe" goto :portable
goto :source

:portable
if not exist "Aplicacion\server.py" goto :package_error
if not exist "Aplicacion\runtime\Lib\urllib\parse.py" goto :package_error
"Aplicacion\runtime\python.exe" -E -c "import urllib.parse, mimetypes" >nul 2>nul
if errorlevel 1 goto :package_error
echo.
echo   OpenAPU se esta iniciando...
echo   En unos segundos se abrira en su navegador.
echo.
echo   Mantenga esta ventana abierta mientras usa OpenAPU.
echo   Para terminar, cierre esta ventana.
echo.
"Aplicacion\runtime\python.exe" -E "Aplicacion\server.py" --port 8767
if errorlevel 1 goto :start_error
exit /b 0

:source
set "OPENAPU_PYTHON="
where py.exe >nul 2>nul
if not errorlevel 1 set "OPENAPU_PYTHON=py -3"
if defined OPENAPU_PYTHON goto :source_python_found
where python.exe >nul 2>nul
if not errorlevel 1 set "OPENAPU_PYTHON=python"
if not defined OPENAPU_PYTHON goto :source_error

:source_python_found
if not exist ".venv\Scripts\python.exe" (
  echo.
  echo   Preparando OpenAPU por primera vez...
  %OPENAPU_PYTHON% -m venv .venv
  if errorlevel 1 goto :source_error
)
echo.
echo   Comprobando componentes necesarios...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :source_error
echo.
echo   OpenAPU se esta iniciando...
echo   Mantenga esta ventana abierta mientras usa OpenAPU.
echo.
".venv\Scripts\python.exe" server.py --port 8767
if errorlevel 1 goto :start_error
exit /b 0

:package_error
echo.
echo   Este paquete esta incompleto o se abrio dentro del ZIP.
echo   Elija "Extraer todo" y luego abra INICIAR OPENAPU.cmd.
echo.
pause
exit /b 1

:source_error
echo.
echo   Esta es una copia del codigo fuente y necesita Python 3.11 o superior.
echo   Para una instalacion simple descargue "OpenAPU-Windows.zip" desde:
echo   https://github.com/KuboServicios/OpenAPU/releases/latest
echo.
pause
exit /b 1

:start_error
echo.
echo   OpenAPU no pudo iniciarse.
echo   Cierre esta ventana, reinicie el computador e intentelo otra vez.
echo   Si continua, abra un reporte en GitHub sin adjuntar datos de proyectos.
echo.
pause
exit /b 1
