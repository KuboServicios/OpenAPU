from __future__ import annotations

import json
import mimetypes
import platform
import re
import secrets
import os
import subprocess
import sys
import tempfile
import time
import traceback
import unicodedata
import webbrowser
import zipfile
import urllib.error
import urllib.request
from urllib.request import urlopen
from email import policy
from email.parser import BytesParser
from http.cookies import SimpleCookie
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Timer
from urllib.parse import urlparse

from account_store import AccountStore, ProjectVersionConflict, SESSION_DAYS
from app_paths import data_root, resource_dir, write_projects_dir
from apu import export_apu_bc3
from converter import convert_bytes
from export_apu_pdf import main as build_apu_pdf
from export_excel import export_apu_workbook, export_itemized_workbook, export_view_workbook
from export_view_report import main as build_view_pdf


def argument_value(name: str) -> str | None:
    try:
        index = sys.argv.index(name)
        return sys.argv[index + 1]
    except (ValueError, IndexError):
        return None


BASE_DIR = resource_dir()
CONFIGURE_ROOT = argument_value("--configure-projects-dir")
DATA_ROOT = write_projects_dir(CONFIGURE_ROOT) if CONFIGURE_ROOT else data_root(argument_value("--data-dir"))
EXPORT_DIR = DATA_ROOT / "exports"
MAX_UPLOAD = 25 * 1024 * 1024
STORE = AccountStore(DATA_ROOT / "data" / "openapu.db")

GELI_ROOT = Path(os.environ.get("CodeAPU_GELI_ROOT", Path.home() / "Desktop" / "GELI"))
GELI_ANALYSIS_LIMIT = 240_000
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-5"
APU_AI_RULES_FILE = BASE_DIR / "REGLAS_IA_APU.md"


def _normalized_name(value: str) -> str:
    return "".join(
        character for character in unicodedata.normalize("NFKD", str(value).lower())
        if not unicodedata.combining(character)
    )


def _read_json_file(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return fallback


def _geli_config() -> dict:
    return _read_json_file(GELI_ROOT / "data" / "config.json", {})


def _geli_records() -> list[dict]:
    records = _read_json_file(GELI_ROOT / "data" / "seguidas.json", [])
    return records if isinstance(records, list) else []


def _safe_geli_project(project_id: str) -> tuple[Path, dict]:
    if not re.fullmatch(r"[A-Za-z0-9-]{3,80}", project_id):
        raise ValueError("El identificador GELI no es válido.")
    config = _geli_config()
    base_value = str(config.get("adjuntos_base_dir") or "").strip()
    if not base_value:
        raise FileNotFoundError("GELI no tiene configurada la carpeta de proyectos.")
    base = Path(base_value).expanduser().resolve()
    safe_name = re.sub(r'[<>:"/\\|?*]', "_", project_id.strip())
    project = (base / safe_name).resolve()
    try:
        project.relative_to(base)
    except ValueError as exc:
        raise PermissionError("La carpeta solicitada está fuera de los proyectos GELI.") from exc
    record = next((entry for entry in _geli_records() if str(entry.get("id")) == project_id), None)
    if record is None:
        raise FileNotFoundError("El proyecto no está registrado en GELI.")
    return project, record


def _project_file_inventory(root: Path) -> tuple[list[dict], dict[str, list[dict]]]:
    categories = {"eett": [], "planning": [], "bim": [], "analysis": [], "budget": [], "other": []}
    entries: list[dict] = []
    if not root.is_dir():
        return entries, categories
    keywords = {
        "eett": ("eett", "especificacion", "bases tecnicas", "memoria"),
        "planning": ("planificacion", "programa", "gantt", "cronograma", "hito", "plazo", "secuencia", "plan de trabajo"),
        "bim": ("bim", "ifc", "revit", ".rvt", "modelo", "coordinacion"),
        "analysis": ("_analisis_ia", "analisis ia", "informe ia"),
        "budget": ("itemizado", "presupuesto", "apu", "precio unitario", "oferta economica"),
    }
    for index, path in enumerate(sorted(root.rglob("*"), key=lambda item: str(item).lower())):
        if index >= 2500:
            break
        if not path.is_file():
            continue
        try:
            relative = path.relative_to(root).as_posix()
            size = path.stat().st_size
        except OSError:
            continue
        normalized = _normalized_name(relative)
        category = next((name for name, words in keywords.items() if any(word in normalized for word in words)), "other")
        item = {"name": path.name, "path": relative, "size": size, "category": category}
        entries.append(item)
        if len(categories[category]) < 150:
            categories[category].append(item)
    return entries, categories


def _read_project_texts(root: Path, files: list[dict], limit: int = GELI_ANALYSIS_LIMIT) -> list[dict]:
    allowed = {".md", ".txt", ".json", ".csv", ".log"}
    result: list[dict] = []
    used = 0
    for item in files:
        path = (root / item["path"]).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError:
            continue
        if path.suffix.lower() not in allowed or not path.is_file() or used >= limit:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[: min(80_000, limit - used)]
        except OSError:
            continue
        used += len(text)
        result.append({"path": item["path"], "content": text})
    return result


def _geli_project_payload(project_id: str, include_text: bool = True) -> dict:
    root, record = _safe_geli_project(project_id)
    files, categories = _project_file_inventory(root)
    documents = record.get("documentos_md") or {}
    eett_documents = []
    for relative, info in documents.items():
        if not isinstance(info, dict):
            continue
        document_type = _normalized_name(str(info.get("tipo") or ""))
        if "especificacion" not in document_type and "eett" not in document_type:
            continue
        eett_documents.append({
            "path": relative,
            "name": info.get("archivo") or Path(relative).name,
            "type": info.get("tipo") or "especificaciones",
            "content": str(info.get("contenido") or "")[:100_000] if include_text else "",
        })
    context_files = categories["eett"] + categories["analysis"] + categories["planning"] + categories["budget"]
    return {
        "id": project_id,
        "name": (record.get("snapshot") or {}).get("nombre") or project_id,
        "folder": str(root),
        "exists": root.is_dir(),
        "fileCount": len(files),
        "categories": categories,
        "eettDocuments": eett_documents,
        "analysis": record.get("ia_analisis") or {},
        "technical": record.get("datos_tecnicos") or {},
        "contextTexts": _read_project_texts(root, context_files) if include_text else [],
    }


def _extract_json_object(text: str) -> dict:
    cleaned = str(text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ValueError("Claude no devolvió una propuesta estructurada.")
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("La respuesta de Claude no tiene una estructura válida.")
    return payload


def _ask_claude_for_apu(api_key: str, prompt: str) -> dict:
    request_body = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 7000,
        "messages": [{"role": "user", "content": prompt}],
    }, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=request_body,
        method="POST",
        headers={"content-type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Claude respondió con error {exc.code}: {detail}") from exc
    blocks = payload.get("content") or []
    text = "\n".join(str(block.get("text") or "") for block in blocks if block.get("type") == "text")
    return _extract_json_object(text)


def record_error(context: str, exc: Exception) -> str:
    error_id = f"CodeAPU-{time.strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"
    log_dir = DATA_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": error_id,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "context": context,
        "type": type(exc).__name__,
        "message": str(exc)[:1000],
        "traceback": traceback.format_exc(limit=12),
    }
    with (log_dir / "errors.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"{error_id} [{context}] {exc}", file=sys.stderr)
    return error_id


def prepare_packaged_logs() -> None:
    if not getattr(sys, "frozen", False) or CONFIGURE_ROOT:
        return
    log_dir = DATA_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    if sys.stdout is None:
        sys.stdout = (log_dir / "server.log").open("a", encoding="utf-8", buffering=1)
    if sys.stderr is None:
        sys.stderr = (log_dir / "server-error.log").open("a", encoding="utf-8", buffering=1)


def clean_filename(value: str, fallback: str = "itemizado") -> str:
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(value).stem).strip("_-") or fallback
    return stem[:80]


def scoped_export_name(payload: dict, fallback: str = "proyecto") -> str:
    project = payload.get("project") if isinstance(payload.get("project"), dict) else {}
    project_id = str(
        payload.get("projectCode")
        or project.get("code")
        or project.get("tender")
        or payload.get("projectId")
        or ""
    ).strip()
    if project_id:
        return clean_filename(project_id, fallback)
    project_name = str(project.get("name") or payload.get("projectName") or "").strip()
    return clean_filename(project_name, fallback)


class Handler(BaseHTTPRequestHandler):
    server_version = "CodeAPU/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def send_json(self, payload: dict, status: int = 200, headers: dict[str, str] | None = None) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_security_headers()
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def send_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self' http://127.0.0.1:8777; frame-ancestors 'none'")

    def json_body(self, maximum: int = 50 * 1024 * 1024) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > maximum:
            raise ValueError("La solicitud está vacía o supera el máximo permitido.")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("La solicitud no tiene una estructura válida.")
        return payload

    def session_token(self) -> str:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        return cookie.get("codeapu_session").value if cookie.get("codeapu_session") else ""

    def current_user(self) -> dict | None:
        return STORE.user_for_token(self.session_token())

    def require_user(self) -> dict:
        user = self.current_user()
        if not user:
            raise PermissionError("No fue posible preparar el usuario local de CodeAPU.")
        return user

    def require_same_origin(self) -> None:
        host = self.headers.get("Host", "")
        if not re.fullmatch(r"(?:127\.0\.0\.1|localhost):\d{1,5}", host, re.IGNORECASE):
            raise PermissionError("Solicitud local no autorizada.")
        origin = self.headers.get("Origin", "")
        referer = self.headers.get("Referer", "")
        allowed = {f"http://{host}", f"http://{host.lower()}"}
        if origin and origin not in allowed:
            raise PermissionError("Origen de solicitud no autorizado.")
        if not origin and referer and not any(referer.startswith(value + "/") for value in allowed):
            raise PermissionError("Referencia de solicitud no autorizada.")

    def require_api_user(self, capability: str | None = None) -> dict:
        self.require_same_origin()
        user = self.require_user()
        if not STORE.verify_csrf(self.session_token(), self.headers.get("X-CodeAPU-CSRF", "")):
            raise PermissionError("La autorización local venció. Recarga CodeAPU para renovarla automáticamente.")
        return user

    @staticmethod
    def session_cookie(token: str, clear: bool = False) -> str:
        maximum = 0 if clear else SESSION_DAYS * 24 * 60 * 60
        return f"codeapu_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={maximum}"

    def register_export(self, filename: str, event_type: str, detail: dict | None = None) -> None:
        user_id = int(self.api_user["id"])
        STORE.register_artifact(user_id, filename)
        STORE.audit(user_id, event_type, detail=detail or {"filename": filename})

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route in {"/", "/index.html"}:
            return self.send_file(BASE_DIR / "index.html")
        if route == "/gg_default_template.js":
            return self.send_file(BASE_DIR / "gg_default_template.js")
        if route == "/assets/fonts/Inter-Regular.woff2":
            return self.send_file(BASE_DIR / "assets" / "fonts" / "Inter-Regular.woff2")
        if route in {"/assets/codeapu-icon.png", "/assets/codeapu-logo.png"}:
            return self.send_file(BASE_DIR / route.lstrip("/"))
        if route == "/api/health":
            return self.send_json({"ok": True})
        if route == "/api/auth/me":
            user = self.current_user()
            headers = {}
            if user:
                csrf = STORE.rotate_csrf(self.session_token())
            else:
                user = STORE.local_user()
                token, csrf = STORE.create_session(int(user["id"]))
                headers["Set-Cookie"] = self.session_cookie(token)
            return self.send_json({"ok": True, "authenticated": True, "localMode": True, "user": user, "csrf": csrf}, headers=headers)
        if route == "/api/projects":
            try:
                user = self.require_user()
                return self.send_json({"ok": True, "projects": STORE.list_projects(int(user["id"]))})
            except PermissionError as exc:
                return self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.UNAUTHORIZED)
        if route == "/api/companies":
            try:
                user = self.require_user()
                return self.send_json({"ok": True, "companies": STORE.list_companies(int(user["id"]))})
            except PermissionError as exc:
                return self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.UNAUTHORIZED)
        if route == "/api/mcp/proposals":
            try:
                user = self.require_user()
                return self.send_json({"ok": True, "proposals": STORE.list_mcp_proposals(int(user["id"]))})
            except PermissionError as exc:
                return self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.UNAUTHORIZED)
        if route == "/api/geli/projects":
            try:
                self.require_user()
                records = []
                for entry in _geli_records():
                    project_id = str(entry.get("id") or "")
                    try:
                        root, _record = _safe_geli_project(project_id)
                    except (ValueError, FileNotFoundError, PermissionError):
                        continue
                    snapshot = entry.get("snapshot") or {}
                    records.append({
                        "id": project_id,
                        "name": snapshot.get("nombre") or project_id,
                        "client": snapshot.get("organismo") or "",
                        "folder": str(root),
                        "exists": root.is_dir(),
                        "hasEett": bool(entry.get("documentos_md")),
                        "hasAnalysis": bool(entry.get("ia_analisis")),
                        "hasTechnical": bool(entry.get("datos_tecnicos")),
                    })
                return self.send_json({"ok": True, "geliAvailable": GELI_ROOT.is_dir(), "projects": records})
            except PermissionError as exc:
                return self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.UNAUTHORIZED)
        project_match = re.fullmatch(r"/api/projects/([A-Za-z0-9_-]{8,80})", route)
        if project_match:
            try:
                user = self.require_user()
                project_id = project_match.group(1)
                project = STORE.load_project(int(user["id"]), project_id)
                meta = STORE.get_project_meta(int(user["id"]), project_id)
                return self.send_json({
                    "ok": True,
                    "id": project_id,
                    "projectHash": meta["projectHash"],
                    "updatedAt": meta["updatedAt"],
                    "projectFile": project,
                })
            except PermissionError as exc:
                return self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.UNAUTHORIZED)
            except KeyError as exc:
                return self.send_json({"ok": False, "message": str(exc.args[0])}, HTTPStatus.NOT_FOUND)
        if route.startswith("/download/"):
            token = route.removeprefix("/download/")
            if not re.fullmatch(r"[A-Za-z0-9_.-]+\.(?:bc3|xlsx|pdf|zip|json)", token, re.IGNORECASE):
                return self.send_error(HTTPStatus.BAD_REQUEST)
            try:
                user = self.require_user()
            except PermissionError:
                return self.send_error(HTTPStatus.UNAUTHORIZED)
            if not STORE.owns_artifact(int(user["id"]), token):
                return self.send_error(HTTPStatus.FORBIDDEN)
            path = EXPORT_DIR / token
            if not path.is_file():
                return self.send_error(HTTPStatus.NOT_FOUND)
            return self.send_file(path, download=True)
        self.send_error(HTTPStatus.NOT_FOUND)

    def send_file(self, path: Path, download: bool = False) -> None:
        if not path.is_file():
            return self.send_error(HTTPStatus.NOT_FOUND)
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        content_type = "application/octet-stream" if download else mimetypes.guess_type(path.name)[0] or "text/html"
        if path.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif path.suffix == ".woff2":
            content_type = "font/woff2"
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_security_headers()
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        if route == "/api/auth/register":
            return self.auth_register()
        if route == "/api/auth/login":
            return self.auth_login()
        route_capabilities = {
            "/api/auth/logout": None,
            "/api/projects/save": "write",
            "/api/projects/delete": "write",
            "/api/companies/save": "write",
            "/api/export-apu-excel": "export",
            "/api/export-apu-pdf": "export",
            "/api/export-itemized-excel": "export",
            "/api/export-view-report": "export",
            "/api/export-apu": "export",
            "/api/convert": "import",
            "/api/backup": "backup",
            "/api/diagnostics/export": "backup",
            "/api/mcp/pair": "mcp_read",
            "/api/mcp/approve": "mcp_apply",
            "/api/mcp/reject": None,
            "/api/geli/context": "mcp_read",
            "/api/geli/apu-assist": "mcp_read",
        }
        if route not in route_capabilities:
            return self.send_error(HTTPStatus.NOT_FOUND)
        try:
            self.api_user = self.require_api_user(route_capabilities[route])
        except PermissionError as exc:
            return self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.FORBIDDEN)
        if route == "/api/auth/logout":
            return self.auth_logout()
        if route == "/api/projects/save":
            return self.save_account_project()
        if route == "/api/projects/delete":
            return self.delete_account_project()
        if route == "/api/companies/save":
            return self.save_account_company()
        if route == "/api/export-apu-excel":
            return self.export_apu_excel()
        if route == "/api/export-apu-pdf":
            return self.export_apu_pdf()
        if route == "/api/export-itemized-excel":
            return self.export_itemized_excel()
        if route == "/api/export-view-report":
            return self.export_view_report()
        if route == "/api/export-apu":
            return self.export_apu()
        if route == "/api/backup":
            return self.export_backup()
        if route == "/api/diagnostics/export":
            return self.export_diagnostics()
        if route == "/api/mcp/pair":
            return self.pair_mcp()
        if route == "/api/mcp/approve":
            return self.approve_mcp_proposal()
        if route == "/api/mcp/reject":
            return self.reject_mcp_proposal()
        if route == "/api/geli/context":
            return self.geli_context()
        if route == "/api/geli/apu-assist":
            return self.geli_apu_assist()
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_UPLOAD:
                raise ValueError("El archivo está vacío o supera el máximo de 25 MB.")
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                raise ValueError("La carga debe enviarse como formulario multipart.")
            body = self.rfile.read(length)
            message = BytesParser(policy=policy.default).parsebytes(
                f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("ascii") + body
            )
            upload_part = None
            project_name = ""
            for part in message.iter_parts():
                field_name = part.get_param("name", header="content-disposition")
                if field_name == "file":
                    upload_part = part
                elif field_name == "projectName":
                    project_name = part.get_content().strip()
            if upload_part is None or not upload_part.get_filename():
                raise ValueError("No se recibió un archivo.")
            filename = Path(upload_part.get_filename()).name
            data = upload_part.get_payload(decode=True) or b""
            result = convert_bytes(data, filename, project_name)
            EXPORT_DIR.mkdir(exist_ok=True)
            export_name = f"{clean_filename(result.project_name)}_{secrets.token_hex(4)}.bc3"
            (EXPORT_DIR / export_name).write_bytes(result.bc3_bytes)
            self.register_export(export_name, "itemized.imported", {"source": filename, "export": export_name})
            payload = result.preview()
            payload.update({"ok": True, "downloadUrl": f"/download/{export_name}", "exportName": export_name})
            self.send_json(payload)
        except ValueError as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            error_id = record_error("convert", exc)
            self.send_json({"ok": False, "message": f"No fue posible procesar el archivo. Código {error_id}."}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def geli_context(self) -> None:
        try:
            payload = self.json_body(256 * 1024)
            project_id = str(payload.get("projectId") or "").strip()
            context = _geli_project_payload(project_id, include_text=True)
            self.send_json({"ok": True, "context": context})
        except (ValueError, FileNotFoundError, PermissionError) as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            error_id = record_error("geli.context", exc)
            self.send_json({"ok": False, "message": f"No fue posible leer el proyecto GELI. Código {error_id}."}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def geli_apu_assist(self) -> None:
        try:
            payload = self.json_body(2 * 1024 * 1024)
            project_id = str(payload.get("projectId") or "").strip()
            question = str(payload.get("question") or "").strip()[:4000]
            concept = payload.get("concept") if isinstance(payload.get("concept"), dict) else {}
            current_rows = payload.get("analysisRows") if isinstance(payload.get("analysisRows"), list) else []
            current_enrichment = payload.get("enrichment") if isinstance(payload.get("enrichment"), dict) else {}
            context = _geli_project_payload(project_id, include_text=True)
            config = _geli_config()
            api_key = str(config.get("anthropic_api_key") or "").strip()
            if not api_key:
                raise ValueError("GELI no tiene configurada la conexión con Claude.")
            rules = APU_AI_RULES_FILE.read_text(encoding="utf-8") if APU_AI_RULES_FILE.is_file() else "No inventar precios ni rendimientos; proponer antes de aplicar."
            source_sections = []
            for document in context["eettDocuments"]:
                source_sections.append(f"EETT: {document['name']}\n{document['content']}")
            for document in context["contextTexts"]:
                source_sections.append(f"ARCHIVO DE CONTEXTO: {document['path']}\n{document['content']}")
            evidence = "\n\n".join(source_sections)[:500_000]
            existing_analysis = json.dumps(context.get("analysis") or {}, ensure_ascii=False)[:60_000]
            technical = json.dumps(context.get("technical") or {}, ensure_ascii=False)[:60_000]
            prompt = f"""Eres el asistente técnico de CodeAPU para presupuestos de construcción en Chile.
Trabaja exclusivamente con la evidencia incluida. Si falta información, formula preguntas; no inventes precios, rendimientos, consumos, BIM ni requisitos.

REGLAS CodeAPU:
{rules}

JERARQUÍA BC3 DEL ITEMIZADO:
El itemizado es un árbol BC3: proyecto → capítulos y subcapítulos (sin unidad, agrupan partidas) → partidas (con unidad; son las que se presupuestan). El prefijo del código de cada nivel identifica el frente del proyecto: "CA" = Cafetería Ampliada, "CD" = Colegio Doctoral (ver REGLA_CODIFICACION_APU y REGLA_PROYECTO_UNICO en la evidencia documental — este proyecto es una sola licitación con dos frentes, no dos proyectos separados).
El frente de la PARTIDA ACTIVA NO se pregunta al mandante: se lee directamente del prefijo de su `originalCode` y de su `breadcrumb` (ruta de capítulos padre, del proyecto hacia la partida, en orden). Si el `breadcrumb` solo contiene un frente, la partida es exclusiva de ese frente — no preguntes si corresponde "a CA, a CD o a ambos" salvo que el propio itemizado repita la partida bajo el otro prefijo.
La cantidad de la PARTIDA ACTIVA (`quantity`) ya es la cubicación fijada en el itemizado, no un dato pendiente de mandante: úsala tal cual para calcular consumos y rendimientos. Solo pregunta por la cantidad si llega vacía o en 0.
Antes de agregar una pregunta a `questions`, verifica que no se responda ya con el `breadcrumb`, el `originalCode` o la `quantity` de la PARTIDA ACTIVA, ni con REGLA_CODIFICACION_APU/REGLA_PROYECTO_UNICO — repetir esa pregunta es un error, no una pregunta pendiente real.

PROYECTO GELI: {context['id']} — {context['name']}
ANÁLISIS GELI EXISTENTE:
{existing_analysis}

DATOS TÉCNICOS GELI:
{technical}

PARTIDA ACTIVA (code = ID interno; originalCode = código BC3 real con prefijo de frente; breadcrumb = ruta de capítulos padre del proyecto a la partida; quantity = cubicación ya fijada):
{json.dumps(concept, ensure_ascii=False)}

APU ACTUAL:
{json.dumps(current_rows, ensure_ascii=False)}

INSPECTOR ACTUAL:
{json.dumps(current_enrichment, ensure_ascii=False)}

SOLICITUD DEL USUARIO:
{question or 'Analiza la partida y propón un APU y contenido para su inspector.'}

EVIDENCIA DOCUMENTAL:
{evidence}

Devuelve SOLAMENTE JSON válido con estas claves:
message (string), questions (array de strings), sources (array de referencias exactas), assumptions (array), confidence (alta|media|baja),
analysisRows (array o null) y enrichment (objeto).
Cada elemento de analysisRows debe conservar o proponer el contrato común CodeAPU/PRESTO:
code y prestoCode (código maestro PRESTO), description, unit, quantity, factor, unitPrice,
isSubanalysis opcional, relationId, resourceType (M/O/E/S), resourceFamilyCode,
familyItemSequence, dependency, destinationCode, subdestinationCode, partidaSourceCode,
relationCorrelative, codeapuCode, classificationStatus (inferido|confirmado),
classificationOrigin, classificationRule, technicalBasis, priceStatus, resourceSource,
resourceNotes, changeReference, costTimingDecision y codingVersion.
Cuando manualUnitPriceOverride sea verdadero, conserva también manualUnitPriceUpdatedAt y
manualUnitPriceUpdatedBy: el precio digitado por el usuario es la fuente vigente y no debe
reemplazarse por una inferencia o normalización automática.
No reemplaces valores canónicos existentes por inferencias. Si un dato nuevo no puede
confirmarse con la evidencia, consérvalo y marca classificationStatus como inferido;
technicalBasis o priceStatus deben quedar PENDIENTE cuando corresponda.
enrichment puede usar theoreticalProductivity, crewComposition, directPlacement, scheduleDemand, productivityBasis, eettRequirements, eettConsidered, eettDecisions, eettPending, aiProductivityAdjustment, aiCostAdjustment, aiAnalysis.
En la sección técnica, vacía las EETT en cuatro campos: eettRequirements (lo exigido por los antecedentes), eettConsidered (lo incorporado al APU), eettDecisions (criterios y supuestos adoptados) y eettPending (dudas o validaciones pendientes).
Si faltan precios o rendimientos, usa 0 solo como pendiente, explícalo y pregunta. No agregues claves distintas a las definidas en este contrato."""
            proposal = _ask_claude_for_apu(api_key, prompt)
            allowed_enrichment = {"theoreticalProductivity", "crewComposition", "directPlacement", "scheduleDemand", "productivityBasis", "eettRequirements", "eettConsidered", "eettDecisions", "eettPending", "aiProductivityAdjustment", "aiCostAdjustment", "aiAnalysis"}
            proposal["enrichment"] = {
                key: str(value)[:5000] for key, value in (proposal.get("enrichment") or {}).items()
                if key in allowed_enrichment and isinstance(value, (str, int, float))
            }
            if proposal.get("analysisRows") is not None:
                if not isinstance(proposal["analysisRows"], list) or len(proposal["analysisRows"]) > 500:
                    raise ValueError("La propuesta de APU devuelta por Claude no es válida.")
            proposal["projectId"] = project_id
            proposal["conceptCode"] = str(concept.get("code") or "")
            self.send_json({"ok": True, "proposal": proposal})
        except (ValueError, FileNotFoundError, PermissionError) as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.BAD_REQUEST)
        except RuntimeError as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.BAD_GATEWAY)
        except Exception as exc:
            error_id = record_error("geli.apu-assist", exc)
            self.send_json({"ok": False, "message": f"No fue posible generar la propuesta. Código {error_id}."}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def auth_register(self) -> None:
        try:
            self.require_same_origin()
            user = STORE.local_user()
            token, csrf = STORE.create_session(int(user["id"]))
            self.send_json({"ok": True, "localMode": True, "user": user, "csrf": csrf}, headers={"Set-Cookie": self.session_cookie(token)})
        except PermissionError as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.FORBIDDEN)

    def auth_login(self) -> None:
        try:
            self.require_same_origin()
            user = STORE.local_user()
            token, csrf = STORE.create_session(int(user["id"]))
            self.send_json({"ok": True, "localMode": True, "user": user, "csrf": csrf}, headers={"Set-Cookie": self.session_cookie(token)})
        except PermissionError as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.FORBIDDEN)

    def auth_logout(self) -> None:
        token = self.session_token()
        if token:
            STORE.logout(token)
        self.send_json({"ok": True, "localMode": True}, headers={"Set-Cookie": self.session_cookie("", clear=True)})

    def save_account_project(self) -> None:
        try:
            user = self.api_user
            payload = self.json_body()
            project = STORE.save_project(int(user["id"]), payload)
            self.send_json({"ok": True, "project": project})
        except ProjectVersionConflict as exc:
            self.send_json({"ok": False, "message": str(exc), "conflict": True}, HTTPStatus.CONFLICT)
        except PermissionError as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.UNAUTHORIZED)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.BAD_REQUEST)

    def save_account_company(self) -> None:
        try:
            company = STORE.save_company(int(self.api_user["id"]), self.json_body(4 * 1024 * 1024))
            self.send_json({"ok": True, "company": company})
        except PermissionError as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.UNAUTHORIZED)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.BAD_REQUEST)

    def delete_account_project(self) -> None:
        try:
            user = self.api_user
            payload = self.json_body(64 * 1024)
            STORE.delete_project(int(user["id"]), str(payload.get("id") or ""))
            self.send_json({"ok": True})
        except PermissionError as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.UNAUTHORIZED)
        except KeyError as exc:
            self.send_json({"ok": False, "message": str(exc.args[0])}, HTTPStatus.NOT_FOUND)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.BAD_REQUEST)

    def export_apu(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 10 * 1024 * 1024:
                raise ValueError("La edición APU está vacía o supera el máximo permitido.")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            bc3_bytes, summary = export_apu_bc3(payload)
            EXPORT_DIR.mkdir(exist_ok=True)
            name = scoped_export_name(payload, "presupuesto_apu")
            export_name = f"{name}_BC3.bc3"
            (EXPORT_DIR / export_name).write_bytes(bc3_bytes)
            self.register_export(export_name, "apu.exported.presto", {"filename": export_name})
            self.send_json({
                "ok": True,
                "downloadUrl": f"/download/{export_name}",
                "exportName": export_name,
                **summary,
            })
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            error_id = record_error("export-presto", exc)
            self.send_json({"ok": False, "message": f"No fue posible generar el BC3 con APU. Código {error_id}."}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def export_apu_excel(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 50 * 1024 * 1024:
                raise ValueError("La exportación Excel está vacía o supera el máximo permitido.")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload.get("partidas"), list) or not payload["partidas"]:
                raise ValueError("No hay partidas para exportar a Excel.")
            EXPORT_DIR.mkdir(exist_ok=True)
            name = scoped_export_name(payload, "presupuesto_apu")
            export_name = f"{name}_Desglose_APU.xlsx"
            output_path = EXPORT_DIR / export_name
            export_apu_workbook(payload, output_path)
            self.register_export(export_name, "apu.exported.excel", {"filename": export_name})
            self.send_json({
                "ok": True,
                "downloadUrl": f"/download/{export_name}",
                "exportName": export_name,
                "sheetCount": len(payload["partidas"]) + 1,
            })
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            error_id = record_error("export-apu-excel", exc)
            self.send_json({"ok": False, "message": f"No fue posible generar el Excel de APU. Código {error_id}."}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def export_itemized_excel(self) -> None:
        try:
            payload = self.json_body(100 * 1024 * 1024)
            if not isinstance(payload.get("items"), list) or not payload["items"]:
                raise ValueError("No hay filas de itemizado para exportar.")
            EXPORT_DIR.mkdir(exist_ok=True)
            name = scoped_export_name(payload, "itemizado")
            export_name = f"{name}_Itemizado_detallado.xlsx"
            output_path = EXPORT_DIR / export_name
            export_itemized_workbook(payload, output_path)
            self.register_export(export_name, "itemized.exported.excel", {"filename": export_name})
            self.send_json({
                "ok": True,
                "downloadUrl": f"/download/{export_name}",
                "exportName": export_name,
                "rowCount": len(payload["items"]),
            })
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            error_id = record_error("export-itemized-excel", exc)
            self.send_json({"ok": False, "message": f"No fue posible generar el Excel del itemizado. Código {error_id}."}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def export_apu_pdf(self) -> None:
        try:
            payload = self.json_body(100 * 1024 * 1024)
            if not isinstance(payload.get("partidas"), list) or not payload["partidas"]:
                raise ValueError("No hay partidas para exportar a PDF.")
            EXPORT_DIR.mkdir(exist_ok=True)
            name = scoped_export_name(payload, "presupuesto_apu")
            export_name = f"{name}_Desglose_APU.pdf"
            output_path = EXPORT_DIR / export_name
            with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False, dir=EXPORT_DIR) as handle:
                json.dump(payload, handle, ensure_ascii=False)
                input_path = Path(handle.name)
            try:
                build_apu_pdf(str(input_path), str(output_path))
                if not output_path.is_file():
                    raise ValueError("No fue posible construir el informe PDF de APU.")
            finally:
                input_path.unlink(missing_ok=True)
            self.register_export(export_name, "apu.exported.pdf", {"filename": export_name})
            self.send_json({
                "ok": True,
                "downloadUrl": f"/download/{export_name}",
                "exportName": export_name,
                "analysisCount": len(payload["partidas"]),
            })
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            error_id = record_error("export-apu-pdf", exc)
            self.send_json({"ok": False, "message": f"No fue posible generar el PDF de APU. Código {error_id}."}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def export_view_report(self) -> None:
        try:
            payload = self.json_body(100 * 1024 * 1024)
            report_format = str(payload.get("format") or "").lower()
            if report_format not in {"xlsx", "pdf"}:
                raise ValueError("El formato del reporte debe ser Excel o PDF.")
            if not isinstance(payload.get("columns"), list) or not payload["columns"]:
                raise ValueError("El reporte no contiene columnas.")
            EXPORT_DIR.mkdir(exist_ok=True)
            project_name = scoped_export_name(payload, "proyecto")
            report_name = clean_filename(str(payload.get("sheetName") or payload.get("title") or "reporte"), "reporte")
            export_name = f"{clean_filename(project_name)}_{report_name}.{report_format}"
            output_path = EXPORT_DIR / export_name
            with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False, dir=EXPORT_DIR) as handle:
                json.dump(payload, handle, ensure_ascii=False)
                input_path = Path(handle.name)
            try:
                if report_format == "xlsx":
                    export_view_workbook(payload, output_path)
                else:
                    build_view_pdf(str(input_path), str(output_path))
                if not output_path.is_file():
                    raise ValueError(f"No fue posible construir el reporte {report_format.upper()}.")
            finally:
                input_path.unlink(missing_ok=True)
            self.register_export(export_name, f"report.exported.{report_format}", {"filename": export_name, "report": report_name})
            self.send_json({"ok": True, "downloadUrl": f"/download/{export_name}", "exportName": export_name, "rowCount": len(payload.get("rows") or [])})
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            error_id = record_error("export-view-report", exc)
            self.send_json({"ok": False, "message": f"No fue posible generar el reporte solicitado. Código {error_id}."}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def export_backup(self) -> None:
        try:
            user = self.api_user
            projects = STORE.list_projects(int(user["id"]))
            EXPORT_DIR.mkdir(exist_ok=True)
            export_name = f"CodeAPU_RESPALDO_{clean_filename(user['email'], 'usuario')}_{secrets.token_hex(4)}.zip"
            output_path = EXPORT_DIR / export_name
            with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                manifest = {
                    "format": "CodeAPU-BACKUP",
                    "version": 1,
                    "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "user": {"name": user["name"], "email": user["email"]},
                    "projects": projects,
                }
                archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
                for project in projects:
                    data = STORE.load_project(int(user["id"]), project["id"])
                    archive.writestr(
                        f"projects/{project['id']}.codeapu.json",
                        json.dumps(data, ensure_ascii=False, indent=2),
                    )
                archive.writestr(
                    "LEEME.txt",
                    "Respaldo local CodeAPU. Conserva este archivo en un lugar seguro. "
                    "Contiene los proyectos del usuario indicado en manifest.json.\n",
                )
            self.register_export(export_name, "backup.exported", {"filename": export_name, "projectCount": len(projects)})
            self.send_json({"ok": True, "downloadUrl": f"/download/{export_name}", "exportName": export_name, "projectCount": len(projects)})
        except Exception as exc:
            error_id = record_error("export-backup", exc)
            self.send_json({"ok": False, "message": f"No fue posible generar el respaldo CodeAPU. Código {error_id}."}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def pair_mcp(self) -> None:
        try:
            payload = self.json_body(64 * 1024)
            label = str(payload.get("label") or "Codex local")[:100]
            token = STORE.create_mcp_token(int(self.api_user["id"]), label)
            if getattr(sys, "frozen", False):
                command = str(Path(sys.executable).resolve().with_name("CodeAPU-MCP.exe"))
                args = ["--mcp"]
            else:
                command = sys.executable
                args = [str((BASE_DIR / "server.py").resolve()), "--mcp"]
            quoted_args = ", ".join(json.dumps(value, ensure_ascii=False) for value in args)
            config = (
                "[mcp_servers.codeapu]\n"
                f"command = {json.dumps(command, ensure_ascii=False)}\n"
                f"args = [{quoted_args}]\n"
                "enabled = true\nrequired = false\n"
                "default_tools_approval_mode = \"writes\"\n"
                f"env = {{ CodeAPU_MCP_TOKEN = {json.dumps(token)} }}\n"
            )
            self.send_json({"ok": True, "token": token, "command": command, "args": args, "configToml": config, "expiresInDays": 30})
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.BAD_REQUEST)

    def export_diagnostics(self) -> None:
        try:
            EXPORT_DIR.mkdir(exist_ok=True)
            export_name = f"CodeAPU_DIAGNOSTICO_{time.strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(3)}.zip"
            output_path = EXPORT_DIR / export_name
            home = str(Path.home())
            errors: list[dict] = []
            error_path = DATA_ROOT / "logs" / "errors.jsonl"
            if error_path.is_file():
                for line in error_path.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]:
                    try:
                        entry = json.loads(line)
                        text = json.dumps(entry, ensure_ascii=False).replace(home, "<CARPETA_USUARIO>")
                        text = re.sub(r"[^\s@]+@[^\s@]+\.[^\s@]+", "<CORREO>", text)
                        errors.append(json.loads(text))
                    except ValueError:
                        continue
            summary = {
                "format": "CodeAPU-DIAGNOSTICS",
                "version": 1,
                "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "appVersion": "1.0.0",
                "platform": sys.platform,
                "python": platform.python_version(),
                "packaged": bool(getattr(sys, "frozen", False)),
                "errorCount": len(errors),
            }
            with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("diagnostico.json", json.dumps(summary, ensure_ascii=False, indent=2))
                archive.writestr("errores_anonimizados.json", json.dumps(errors, ensure_ascii=False, indent=2))
            self.register_export(export_name, "diagnostics.exported", {"filename": export_name, "errorCount": len(errors)})
            self.send_json({"ok": True, "downloadUrl": f"/download/{export_name}", "exportName": export_name, "errorCount": len(errors)})
        except Exception as exc:
            error_id = record_error("diagnostics-export", exc)
            self.send_json({"ok": False, "message": f"No fue posible generar el diagnóstico. Código {error_id}."}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def approve_mcp_proposal(self) -> None:
        try:
            payload = self.json_body(64 * 1024)
            proposal = STORE.approve_mcp_proposal(
                int(self.api_user["id"]),
                str(payload.get("proposalId") or ""),
                str(payload.get("proposalHash") or ""),
            )
            self.send_json({"ok": True, "proposal": proposal})
        except KeyError as exc:
            self.send_json({"ok": False, "message": str(exc.args[0])}, HTTPStatus.NOT_FOUND)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.BAD_REQUEST)

    def reject_mcp_proposal(self) -> None:
        try:
            payload = self.json_body(64 * 1024)
            STORE.reject_mcp_proposal(int(self.api_user["id"]), str(payload.get("proposalId") or ""))
            self.send_json({"ok": True})
        except KeyError as exc:
            self.send_json({"ok": False, "message": str(exc.args[0])}, HTTPStatus.NOT_FOUND)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"ok": False, "message": str(exc)}, HTTPStatus.BAD_REQUEST)


def main() -> None:
    if "--mcp" in sys.argv:
        from mcp_server import main as mcp_main

        mcp_main()
        return
    if CONFIGURE_ROOT:
        print(f"Carpeta de proyectos OpenAPU configurada: {DATA_ROOT}")
        return
    host = "127.0.0.1"
    try:
        installed_windows_port = "18765" if getattr(sys, "frozen", False) and sys.platform == "win32" else "8765"
        port = int(argument_value("--port") or installed_windows_port)
    except ValueError:
        raise SystemExit("El puerto indicado no es válido.")
    url = f"http://{host}:{port}"
    try:
        with urlopen(f"{url}/api/health", timeout=0.8) as response:
            if response.status == 200:
                if "--no-browser" not in sys.argv:
                    webbrowser.open(url)
                return
    except Exception:
        pass
    prepare_packaged_logs()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"OpenAPU disponible en {url}")
    print(f"Carpeta de gestión de proyectos: {DATA_ROOT}")
    if "--no-browser" not in sys.argv:
        Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

