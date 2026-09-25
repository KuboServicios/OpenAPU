# OpenAPU MCP para Codex

OpenAPU expone un servidor MCP local mediante el mismo ejecutable con el argumento `--mcp`. No publica un puerto de red ni entrega acceso directo a SQLite o al sistema de archivos.

## Conexión

OpenAPU corre en modo local de un solo usuario. El servidor MCP (`server.py --mcp`)
identifica automáticamente al usuario local principal:
no es necesario generar ni renovar ningún token de vinculación.

1. Apunta tu cliente MCP (Claude, Codex, etc.) al ejecutable `server.py --mcp` de esta
   carpeta.
2. Reinicia el cliente y comprueba el servidor `openapu`.

Si una instalación llega a tener más de un usuario local, sigue existiendo un mecanismo
opcional de token por cuenta (variable de entorno
`CodeAPU_MCP_TOKEN`) para distinguirlos, pero no es obligatorio.

Ejemplo para Codex en Windows, ajustando la ruta a tu instalación:

```toml
[mcp_servers.openapu]
command = "python"
args = ["D:/OpenAPU/server.py", "--mcp"]
```

El prefijo `codeapu_` de las herramientas y la variable `CodeAPU_MCP_TOKEN` se mantienen por compatibilidad técnica con el núcleo compartido.

## Modelo de autorización

- OpenAPU es de uso local y no aplica caducidad de uso.
- Las consultas son de solo lectura.
- `codeapu_propose_apu` registra una propuesta inmutable, pero no cambia el presupuesto.
- `codeapu_apply_approved_proposal` aplica únicamente una propuesta que ya cuenta con aprobación válida.
- Una orden directa del usuario por MCP puede aplicar un lote con `codeapu_apply_authorized_bundle`, sin aprobación individual en la interfaz.
- El lote directo valida todos los IDs, hashes y APU de origen y se aplica de forma transaccional.
- Si el APU cambió después de la propuesta, la aplicación se rechaza.
- Toda creación, aprobación, rechazo y aplicación —individual o masiva— queda en la cadena de auditoría local.

## Herramientas

- `codeapu_list_projects`
- `codeapu_get_project_summary`
- `codeapu_get_normalization_scope`
- `codeapu_get_apu`
- `codeapu_validate_apu`
- `codeapu_propose_apu`
- `codeapu_apply_approved_proposal`
- `codeapu_apply_authorized_bundle`

Para normalización masiva, `codeapu_get_normalization_scope` identifica las relaciones pendientes. Cada propuesta se envía con `normalizationMode: true`, lo que exige código PRESTO, tipo, familia, dependencia, destino, subdestino, partida y correlativo antes de admitirla al lote.

## Privacidad

OpenAPU continúa guardando proyectos localmente. Sin embargo, los datos que una herramienta devuelve a Codex pasan a formar parte del contexto procesado por el servicio de Codex del usuario. Debe evitarse enviar el proyecto completo cuando basta una partida y no deben incluirse secretos, datos personales innecesarios ni antecedentes confidenciales ajenos al análisis solicitado.

