# OpenAPU

OpenAPU es una aplicación local, gratuita y de código abierto para preparar presupuestos de construcción mediante itemizados y análisis de precios unitarios.

## Descargar OpenAPU para Windows

**No uses “Code → Download ZIP” si solo quieres utilizar el programa.** Esa opción descarga el código fuente para desarrolladores.

### [Descargar OpenAPU listo para usar](https://github.com/KuboServicios/OpenAPU/releases/latest/download/OpenAPU-Windows.zip)

1. Descarga `OpenAPU-Windows.zip`.
2. Haz clic derecho y elige **Extraer todo**.
3. Abre la carpeta extraída y haz doble clic en **INICIAR OPENAPU.cmd**.

El paquete para Windows ya incluye Python y sus componentes. No requiere instalador, comandos ni configuración técnica. Mantén abierta la ventana de inicio mientras utilizas OpenAPU.

> Si la descarga todavía no aparece, abre la sección [Releases](https://github.com/KuboServicios/OpenAPU/releases) y selecciona la versión más reciente.

## Qué permite hacer

- Importar y normalizar proyectos desde Excel, CSV y BC3.
- Revisar Itemizado, APU, Gastos Generales y Cierre Comercial.
- Crear o ajustar análisis de precios unitarios.
- Trabajar con una empresa y hasta tres proyectos.
- Exportar Itemizado, APU, Gastos Generales y Cierre Comercial.
- Conectar Codex mediante MCP local bajo autorización del usuario.

Los inspectores avanzados de partidas y recursos son funciones de CodeAPU Full. OpenAPU no incorpora logos corporativos personalizados en sus informes.

## Primer uso

1. Abre OpenAPU y registra tu usuario local.
2. Identifica la empresa que utilizará el proyecto.
3. Crea un proyecto o importa un archivo compatible.
4. Revisa el itemizado y los APU antes de generar informes.
5. Genera un respaldo antes de mover OpenAPU a otro equipo.

## Privacidad

OpenAPU se ejecuta en `127.0.0.1`. Los usuarios, empresas y proyectos se guardan en una base local dentro de tu computador. La aplicación no publica tus proyectos en Internet.

La conexión con Codex es opcional. Solo los datos solicitados mediante las herramientas MCP y autorizados por el usuario salen del proceso local.

## Para desarrolladores

El contenido normal del repositorio es el código fuente. Requiere Windows, Python 3.11 o superior y conexión a Internet durante la preparación inicial.

```powershell
git clone https://github.com/KuboServicios/OpenAPU.git
cd OpenAPU
& '.\INICIAR OPENAPU.cmd'
```

También puedes ejecutar:

```powershell
python -m pip install -r requirements.txt
python server.py --port 8767
```

Consulta [INSTALACION.md](INSTALACION.md), [MCP_CODEX.md](MCP_CODEX.md), [CONTRIBUTING.md](CONTRIBUTING.md) y [SECURITY.md](SECURITY.md).

## Alcance y licencia

OpenAPU admite una empresa y hasta tres proyectos. Al requerir un cuarto proyecto, informa las alternativas de [CodeAPU.cl](https://codeapu.cl/).

Se distribuye bajo la licencia **GNU Affero General Public License v3.0 o posterior (AGPL-3.0-or-later)**. Consulta [LICENSE](LICENSE).

Copyright © 2026 Kubo Servicios SpA.
