# Instalación y uso de OpenAPU

## Instalación en Windows

1. Instala Python 3.11 o superior desde [python.org](https://www.python.org/downloads/windows/).
2. Durante la instalación marca **Add Python to PATH**.
3. Descarga OpenAPU y descomprime la carpeta en una ubicación con permisos de escritura.
4. Ejecuta `Iniciar OpenAPU.ps1` con PowerShell.
5. Mantén abierta la ventana de PowerShell mientras utilizas la aplicación.

El iniciador instala automáticamente las dependencias declaradas en `requirements.txt` y levanta el servidor local en `http://127.0.0.1:8767/`.

## Si PowerShell bloquea el iniciador

Abre PowerShell dentro de la carpeta de OpenAPU y ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File ".\Iniciar OpenAPU.ps1"
```

Esta opción solo omite la política para esa ejecución; no cambia permanentemente la configuración del equipo.

## Inicio manual

```powershell
python -m pip install -r requirements.txt
python server.py --port 8767
```

Después abre `http://127.0.0.1:8767/` en el navegador.

## Detener OpenAPU

Vuelve a la ventana de PowerShell y presiona `Ctrl+C`. Tus proyectos permanecen guardados en la base local.

## Actualizar

Antes de actualizar, genera un respaldo desde OpenAPU. Si clonaste el repositorio, cierra la aplicación, ejecuta `git pull` y vuelve a iniciar. Si descargaste un ZIP, conserva el respaldo y reemplaza los archivos de la aplicación con la nueva versión.

## Problemas habituales

### `python` no se reconoce

Python no está instalado o no se agregó a `PATH`. Reinstálalo marcando **Add Python to PATH** y abre una nueva ventana de PowerShell.

### El puerto 8767 está ocupado

Inicia temporalmente otro puerto:

```powershell
python server.py --port 8768
```

Luego abre `http://127.0.0.1:8768/`.

### No abre la página

Confirma que la ventana de PowerShell siga abierta y que muestre el servidor activo. OpenAPU solo escucha conexiones del propio equipo.

### Restaurar información

Utiliza las opciones de respaldo y restauración incluidas en la aplicación. No publiques ni adjuntes `openapu.db` en reportes de errores: puede contener datos de proyectos y usuarios.

## Soporte

Para errores reproducibles, abre un issue en GitHub sin adjuntar información confidencial. Para servicios y CodeAPU Full visita [CodeAPU.cl](https://codeapu.cl/).

