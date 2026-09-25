# OpenAPU

OpenAPU es una aplicación local, gratuita y de código abierto para preparar presupuestos de construcción mediante itemizados y análisis de precios unitarios (APU). Está desarrollada por **Kubo Servicios SpA** como parte del ecosistema [CodeAPU.cl](https://codeapu.cl/).

## Qué permite hacer

- Importar y normalizar proyectos desde Excel, CSV y BC3.
- Revisar el proyecto en las vistas Itemizado, APU, Gastos Generales y Cierre Comercial.
- Crear o ajustar APU directamente en la aplicación.
- Trabajar con hasta tres proyectos para una empresa identificada.
- Exportar Itemizado, APU, Gastos Generales y Cierre Comercial.
- Conectar Codex mediante un servidor MCP local para consultar y proponer cambios sobre el proyecto.

Los inspectores avanzados de partidas y recursos son funciones exclusivas de CodeAPU Full. OpenAPU no incorpora logos corporativos personalizados en sus informes.

## Requisitos

- Windows 10 u 11.
- Python 3.11 o superior disponible como `python` en PowerShell.
- Conexión a Internet solamente para instalar las dependencias la primera vez. El uso normal y los datos del proyecto permanecen en el equipo.

## Instalación rápida

1. Descarga el repositorio con **Code > Download ZIP** y descomprime el archivo, o clónalo con Git.
2. Haz clic derecho sobre `Iniciar OpenAPU.ps1` y selecciona **Ejecutar con PowerShell**.
3. Espera mientras se instalan las dependencias de Python.
4. Abre `http://127.0.0.1:8767/` si el navegador no se abre automáticamente.

Para una instalación manual:

```powershell
python -m pip install -r requirements.txt
python server.py --port 8767
```

Consulta [INSTALACION.md](INSTALACION.md) para solución de problemas y [MCP_CODEX.md](MCP_CODEX.md) para conectar Codex.

## Primer uso

1. Abre OpenAPU y registra el usuario local.
2. Identifica la empresa que utilizará el proyecto.
3. Crea un proyecto o importa un archivo compatible.
4. Revisa el itemizado y los APU antes de generar informes.
5. Usa la opción de respaldo antes de mover la aplicación a otro equipo.

## Privacidad y datos

OpenAPU se ejecuta en `127.0.0.1`: no publica la aplicación en Internet. Usuarios, empresas y proyectos se guardan en una base SQLite local llamada `openapu.db`. La carpeta `data/`, las bases de datos y las exportaciones están excluidas del repositorio.

Si conectas una herramienta externa mediante MCP, solo los datos solicitados por esa herramienta salen del proceso local. No compartas información confidencial que no sea necesaria para la consulta.

## Alcance gratuito

OpenAPU admite una empresa y hasta tres proyectos. Al requerir un cuarto proyecto, la aplicación informa las alternativas comerciales de CodeAPU. Esta limitación forma parte del producto gratuito y no cambia la licencia del código fuente.

## Desarrollo

```powershell
python -m pip install -r requirements.txt
python -m compileall -q .
python server.py --port 8767
```

Las contribuciones son bienvenidas. Revisa [CONTRIBUTING.md](CONTRIBUTING.md) y [SECURITY.md](SECURITY.md) antes de abrir un issue o pull request.

## Licencia

OpenAPU se distribuye bajo la licencia **GNU Affero General Public License v3.0 o posterior (AGPL-3.0-or-later)**. Consulta [LICENSE](LICENSE).

Copyright © 2026 Kubo Servicios SpA.

