from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from apu import AUXILIAR_RATES, ApuCalculator, as_number
from resource_catalog import canonical_unit


SESSION_DAYS = 1
PBKDF2_ITERATIONS = 310_000
ARTIFACT_HOURS = 24


class ProjectVersionConflict(ValueError):
    """Evita que una sesión web antigua sobrescriba cambios MCP más recientes."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def project_file_summary(project_file: dict) -> dict:
    """Recalcula el mismo resumen que muestra y guarda el cliente web."""
    itemizeds = project_file.get("itemizados") or []
    active_id = str(project_file.get("activeItemizedId") or "")
    itemized = next((entry for entry in itemizeds if str(entry.get("id") or "") == active_id), None)
    if itemized is None:
        itemized = itemizeds[0] if itemizeds else {}
    data = itemized.get("data") or {}
    items = data.get("items") or []
    analyses = itemized.get("analyses") or {}
    dirty = {str(code).upper() for code, value in (itemized.get("dirtyAnalyses") or {}).items() if value}
    # Los códigos maestros internos pueden superar el límite BC3 de 13 caracteres.
    # El exportador conserva su validación estricta; el resumen local solo necesita calcularlos.
    calculator = ApuCalculator(analyses, max_code_length=50)
    source_is_bc3 = str(data.get("sourceFormat") or "").upper() == "BC3"

    def is_partida(item: dict) -> bool:
        explicit = item.get("isPartida")
        return bool(explicit) if explicit is not None else bool(str(item.get("unit") or "").strip())

    def tree_dirty(code: str, stack: tuple[str, ...] = ()) -> bool:
        code = str(code or "").upper()
        if code in dirty:
            return True
        if code in stack:
            return False
        return any(
            bool(row.get("isSubanalysis")) and tree_dirty(str(row.get("code") or ""), (*stack, code))
            for row in calculator.analyses.get(code, [])
        )

    def effective_price(item: dict) -> float:
        code = str(item.get("code") or "").upper()
        rows = calculator.analyses.get(code, [])
        if not rows or (source_is_bc3 and not tree_dirty(code)):
            return as_number(item.get("price"))
        return float(calculator.calculate(code)[0])

    def effective_quantity(item: dict) -> float:
        """Conserva cero como cantidad válida; usa 1 solo si el dato no existe."""
        raw = item.get("quantity")
        return 1.0 if raw is None or str(raw).strip() == "" else as_number(raw)

    def analysis_complete(code: str, stack: tuple[str, ...] = ()) -> bool:
        code = str(code or "").upper()
        if code in stack:
            return False
        rows = calculator.analyses.get(code, [])
        if not rows:
            return False
        for row in rows:
            row_code = str(row.get("code") or "").strip().upper()
            if not row_code or not str(row.get("description") or "").strip():
                return False
            if row_code in AUXILIAR_RATES:
                continue
            if as_number(row.get("quantity")) <= 0:
                return False
            raw_factor = row.get("factor")
            if raw_factor is not None and str(raw_factor).strip() != "" and as_number(raw_factor) <= 0:
                return False
            if row.get("isSubanalysis"):
                if not analysis_complete(row_code, (*stack, code)):
                    return False
            elif as_number(row.get("unitPrice")) <= 0:
                return False
        return calculator.calculate(code)[0] > 0

    # El resumen persistido debe usar el mismo universo visible del visor. Una
    # partida oculta sigue almacenada, pero no cuenta como APU pendiente.
    partidas = [
        item for item in items
        if is_partida(item) and not bool(item.get("hiddenInBudgetViewer"))
    ]
    direct_cost = sum(
        effective_price(item) * effective_quantity(item)
        for item in partidas
        if str(item.get("rootKind") or "") != "commercial"
    )
    return {
        "directCost": direct_cost,
        "partidaCount": len(partidas),
        "completedCount": sum(1 for item in partidas if analysis_complete(str(item.get("code") or ""))),
    }


def validate_resource_coding_consistency(project_file: dict, master_presto_filter: set[str] | None = None) -> None:
    """Impide inconsistencias maestras nuevas y códigos CodeAPU contradictorios.

    ``master_presto_filter`` permite validar sólo las identidades PRESTO tocadas
    por una propuesta. Así una corrección auditada no queda bloqueada por una
    inconsistencia histórica ajena, pero tampoco puede introducir o agravar una
    contradicción en los recursos que modifica.
    """
    master_types: dict[str, str] = {}
    master_names: dict[str, str] = {}
    master_units: dict[str, str] = {}
    master_prices: dict[str, float] = {}
    for itemized in project_file.get("itemizados") or []:
        for analysis_code, rows in (itemized.get("analyses") or {}).items():
            codeapu_codes: set[str] = set()
            for row in rows or []:
                presto = str(row.get("prestoCode") or row.get("code") or "").strip().upper()
                validate_master = master_presto_filter is None or presto in master_presto_filter
                if validate_master and presto and presto not in AUXILIAR_RATES and not row.get("isSubanalysis"):
                    resource_type = str(row.get("resourceType") or presto[:1]).strip().upper()
                    previous_type = master_types.setdefault(presto, resource_type)
                    if previous_type != resource_type:
                        raise ValueError(f"El concepto PRESTO {presto} tiene naturalezas incompatibles: {previous_type} y {resource_type}.")
                    description = unicodedata.normalize("NFKD", str(row.get("description") or "").upper())
                    description = " ".join(re.sub(r"[^A-Z0-9%]+", " ", description.encode("ascii", "ignore").decode()).split())
                    previous_name = master_names.setdefault(presto, description)
                    if previous_name != description:
                        raise ValueError(
                            f"El concepto PRESTO {presto} identifica recursos distintos: {previous_name or '(sin nombre)'} y {description or '(sin nombre)'}.")
                    unit = canonical_unit(row.get("unit"))
                    price = round(as_number(row.get("unitPrice")))
                    previous_unit = master_units.setdefault(presto, unit)
                    if previous_unit != unit:
                        raise ValueError(f"El concepto PRESTO {presto} tiene unidades incompatibles: {previous_unit} y {unit}.")
                    previous_price = master_prices.setdefault(presto, price)
                    if previous_price != price:
                        raise ValueError(
                            f"El concepto PRESTO {presto} tiene precios unitarios distintos ({previous_price:g} y {price:g}). "
                            "En Presto cada código identifica un único recurso y debe conservar un solo precio unitario."
                        )
                parts = [
                    str(row.get("resourceType") or "").strip().upper(),
                    str(row.get("destinationCode") or "").strip().upper(),
                    str(row.get("subdestinationCode") or "").strip().upper(),
                    str(row.get("partidaSourceCode") or "").strip(),
                    str(row.get("relationCorrelative") or "").strip().zfill(2),
                ]
                codeapu = str(row.get("codeapuCode") or "").strip().upper()
                if codeapu and codeapu != "-".join(parts).upper():
                    raise ValueError(f"El código CodeAPU {codeapu} no coincide con sus componentes en {analysis_code}.")
                if codeapu in codeapu_codes:
                    raise ValueError(f"El código CodeAPU {codeapu} está repetido dentro del APU {analysis_code}.")
                if codeapu:
                    codeapu_codes.add(codeapu)


def resource_economic_changes(before_project: dict, after_project: dict) -> list[dict]:
    """Compara relaciones estables para auditar códigos, nombres, familias y precios."""
    def snapshot(project_file: dict) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for itemized_index, itemized in enumerate(project_file.get("itemizados") or []):
            itemized_id = str(itemized.get("id") or itemized_index)
            for analysis_code, rows in (itemized.get("analyses") or {}).items():
                for row_index, row in enumerate(rows or []):
                    if row.get("isSubanalysis"):
                        continue
                    relation = str(row.get("relationId") or row.get("codeapuCode") or f"{row.get('code') or ''}:{row_index}")
                    key = f"{itemized_id}|{analysis_code}|{relation}"
                    result[key] = {
                        "itemizedId": itemized_id,
                        "analysisCode": str(analysis_code),
                        "relation": relation,
                        "prestoCode": str(row.get("prestoCode") or row.get("code") or "").strip().upper(),
                        "description": str(row.get("description") or "").strip(),
                        "resourceFamilyCode": str(row.get("resourceFamilyCode") or "").strip().upper(),
                        "quantity": as_number(row.get("quantity")),
                        "factor": as_number(row.get("factor")) if row.get("factor") not in (None, "") else 1.0,
                        "unitPrice": round(as_number(row.get("unitPrice"))),
                    }
        return result

    before = snapshot(before_project)
    after = snapshot(after_project)
    changes: list[dict] = []
    for key in sorted(before.keys() & after.keys()):
        previous = before[key]
        current = after[key]
        if all(previous[field] == current[field] for field in (
            "prestoCode", "description", "resourceFamilyCode", "quantity", "factor", "unitPrice"
        )):
            continue
        changes.append({
            "itemizedId": current["itemizedId"],
            "analysisCode": current["analysisCode"],
            "relation": current["relation"],
            "beforePrestoCode": previous["prestoCode"],
            "afterPrestoCode": current["prestoCode"],
            "beforeDescription": previous["description"],
            "afterDescription": current["description"],
            "beforeResourceFamilyCode": previous["resourceFamilyCode"],
            "afterResourceFamilyCode": current["resourceFamilyCode"],
            "beforeQuantity": previous["quantity"],
            "afterQuantity": current["quantity"],
            "beforeFactor": previous["factor"],
            "afterFactor": current["factor"],
            "beforeUnitPrice": previous["unitPrice"],
            "afterUnitPrice": current["unitPrice"],
        })
    return changes


def budget_quantity_changes(before_project: dict, after_project: dict) -> list[dict]:
    """Registra cambios manuales de cantidades del itemizado por código estable."""
    def snapshot(project_file: dict) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for itemized_index, itemized in enumerate(project_file.get("itemizados") or []):
            itemized_id = str(itemized.get("id") or itemized_index)
            for item in ((itemized.get("data") or {}).get("items") or []):
                code = str(item.get("code") or "").strip()
                if not code:
                    continue
                key = f"{itemized_id}|{code}"
                result[key] = {
                    "itemizedId": itemized_id,
                    "code": code,
                    "originalCode": str(item.get("originalCode") or code).strip(),
                    "description": str(item.get("description") or "").strip(),
                    "quantity": as_number(item.get("quantity")),
                }
        return result

    before = snapshot(before_project)
    after = snapshot(after_project)
    changes: list[dict] = []
    for key in sorted(before.keys() & after.keys()):
        previous = before[key]
        current = after[key]
        if previous["quantity"] == current["quantity"]:
            continue
        changes.append({
            "itemizedId": current["itemizedId"],
            "code": current["code"],
            "originalCode": current["originalCode"],
            "description": current["description"],
            "beforeQuantity": previous["quantity"],
            "afterQuantity": current["quantity"],
        })
    return changes


class AccountStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    csrf_hash TEXT NOT NULL DEFAULT '',
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    code TEXT NOT NULL DEFAULT '',
                    client TEXT NOT NULL DEFAULT '',
                    location TEXT NOT NULL DEFAULT '',
                    tender TEXT NOT NULL DEFAULT '',
                    responsible TEXT NOT NULL DEFAULT '',
                    direct_cost REAL NOT NULL DEFAULT 0,
                    partida_count INTEGER NOT NULL DEFAULT 0,
                    completed_count INTEGER NOT NULL DEFAULT 0,
                    project_data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_projects_user_updated
                    ON projects(user_id, updated_at DESC);
                CREATE TABLE IF NOT EXISTS companies (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    profile_data TEXT NOT NULL,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_companies_user_updated
                    ON companies(user_id, is_default DESC, updated_at DESC);
                CREATE TABLE IF NOT EXISTS artifacts (
                    filename TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    event_type TEXT NOT NULL,
                    project_id TEXT NOT NULL DEFAULT '',
                    detail_json TEXT NOT NULL DEFAULT '{}',
                    previous_hash TEXT NOT NULL DEFAULT '',
                    event_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events(created_at DESC);
                CREATE TABLE IF NOT EXISTS mcp_tokens (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    label TEXT NOT NULL DEFAULT 'Codex',
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT
                );
                CREATE TABLE IF NOT EXISTS mcp_proposals (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    project_id TEXT NOT NULL,
                    proposal_hash TEXT NOT NULL,
                    proposal_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    approved_at TEXT,
                    applied_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_mcp_proposals_user ON mcp_proposals(user_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS legal_acceptances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    terms_version TEXT NOT NULL,
                    accepted_at TEXT NOT NULL
                );
            """)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(sessions)").fetchall()}
            if "csrf_hash" not in columns:
                db.execute("ALTER TABLE sessions ADD COLUMN csrf_hash TEXT NOT NULL DEFAULT ''")

    @staticmethod
    def normalize_company_profile(raw: object) -> dict:
        if not isinstance(raw, dict):
            raise ValueError("La empresa no tiene una estructura válida.")
        limits = {
            "name": 200, "rut": 30, "address": 300, "phone": 80,
            "email": 160, "website": 240, "reportNote": 1000,
            "preparedBy": 160, "reviewedBy": 160, "approvedBy": 160,
        }
        profile = {key: str(raw.get(key) or "").strip()[:limit] for key, limit in limits.items()}
        if not profile["name"]:
            raise ValueError("La empresa requiere una razón social o nombre.")
        for key, fallback in (("primaryColor", "#123B70"), ("accentColor", "#E8F0F8")):
            value = str(raw.get(key) or fallback).strip().upper()
            profile[key] = value if re.fullmatch(r"#[0-9A-F]{6}", value) else fallback
        # OpenAPU identifica a la empresa, pero reserva los logos para
        # OpenAPU, CodeAPU y Kubo Servicios SpA.
        profile["logoDataUrl"] = ""
        return profile

    @staticmethod
    def normalize_email(email: object) -> str:
        value = str(email or "").strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Ingresa un correo electrónico válido.")
        return value

    @staticmethod
    def hash_password(password: object, salt: bytes | None = None) -> str:
        raw = str(password or "")
        if len(raw) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        salt = salt or secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", raw.encode("utf-8"), salt, PBKDF2_ITERATIONS)
        return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"

    @staticmethod
    def verify_password(password: object, encoded: str) -> bool:
        try:
            algorithm, iterations, salt, expected = encoded.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            digest = hashlib.pbkdf2_hmac(
                "sha256", str(password or "").encode("utf-8"), bytes.fromhex(salt), int(iterations)
            )
            return hmac.compare_digest(digest.hex(), expected)
        except (ValueError, TypeError):
            return False

    def register(self, name: object, email: object, password: object, terms_version: object = None) -> tuple[dict, str, str]:
        clean_name = str(name or "").strip()
        if len(clean_name) < 2:
            raise ValueError("Ingresa tu nombre.")
        clean_email = self.normalize_email(email)
        if str(terms_version or "") != "CodeAPU-BETA-2026-01":
            raise ValueError("Debes aceptar las condiciones de evaluación y privacidad para crear la cuenta.")
        encoded = self.hash_password(password)
        try:
            with self.connect() as db:
                cursor = db.execute(
                    "INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",
                    (clean_name[:120], clean_email, encoded, utc_now()),
                )
                user_id = int(cursor.lastrowid)
                db.execute(
                    "INSERT INTO legal_acceptances(user_id,terms_version,accepted_at) VALUES(?,?,?)",
                    (user_id, "CodeAPU-BETA-2026-01", utc_now()),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Ya existe una cuenta con ese correo.") from exc
        token, csrf = self.create_session(user_id)
        self.audit(user_id, "account.registered", detail={"email": clean_email})
        return {"id": user_id, "name": clean_name[:120], "email": clean_email}, token, csrf

    def login(self, email: object, password: object) -> tuple[dict, str, str]:
        clean_email = self.normalize_email(email)
        with self.connect() as db:
            row = db.execute("SELECT * FROM users WHERE email=?", (clean_email,)).fetchone()
        if not row or not self.verify_password(password, row["password_hash"]):
            raise ValueError("Correo o contraseña incorrectos.")
        user = {"id": row["id"], "name": row["name"], "email": row["email"]}
        token, csrf = self.create_session(int(row["id"]))
        self.audit(int(row["id"]), "account.login")
        return user, token, csrf

    def create_session(self, user_id: int) -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
        csrf_hash = hashlib.sha256(csrf.encode("ascii")).hexdigest()
        expires = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE expires_at < ?", (utc_now(),))
            db.execute(
                "INSERT INTO sessions(token_hash,user_id,csrf_hash,expires_at,created_at) VALUES(?,?,?,?,?)",
                (token_hash, user_id, csrf_hash, expires, utc_now()),
            )
        return token, csrf

    def user_for_token(self, token: str) -> dict | None:
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode("ascii", errors="ignore")).hexdigest()
        with self.connect() as db:
            row = db.execute(
                "SELECT users.id,users.name,users.email FROM sessions "
                "JOIN users ON users.id=sessions.user_id WHERE token_hash=? AND expires_at>=?",
                (token_hash, utc_now()),
            ).fetchone()
        return dict(row) if row else None

    def local_user(self) -> dict:
        """Devuelve el usuario principal del entorno local, priorizando quien posee proyectos."""
        with self.connect() as db:
            row = db.execute(
                "SELECT users.id,users.name,users.email,COUNT(projects.id) AS project_count "
                "FROM users LEFT JOIN projects ON projects.user_id=users.id "
                "GROUP BY users.id ORDER BY project_count DESC,users.id ASC LIMIT 1"
            ).fetchone()
            if row:
                return {"id": row["id"], "name": row["name"], "email": row["email"]}
            cursor = db.execute(
                "INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",
                ("Usuario local", "local@codeapu.internal", self.hash_password(secrets.token_urlsafe(32)), utc_now()),
            )
            return {"id": int(cursor.lastrowid), "name": "Usuario local", "email": "local@codeapu.internal"}

    def verify_csrf(self, token: str, csrf: str) -> bool:
        if not token or not csrf:
            return False
        token_hash = hashlib.sha256(token.encode("ascii", errors="ignore")).hexdigest()
        csrf_hash = hashlib.sha256(csrf.encode("ascii", errors="ignore")).hexdigest()
        with self.connect() as db:
            row = db.execute(
                "SELECT csrf_hash FROM sessions WHERE token_hash=? AND expires_at>=?",
                (token_hash, utc_now()),
            ).fetchone()
        return bool(row and row["csrf_hash"] and hmac.compare_digest(row["csrf_hash"], csrf_hash))

    def csrf_for_token_is_configured(self, token: str) -> bool:
        if not token:
            return False
        token_hash = hashlib.sha256(token.encode("ascii", errors="ignore")).hexdigest()
        with self.connect() as db:
            row = db.execute("SELECT csrf_hash FROM sessions WHERE token_hash=?", (token_hash,)).fetchone()
        return bool(row and row["csrf_hash"])

    def rotate_csrf(self, token: str) -> str:
        if not token:
            return ""
        raw = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("ascii", errors="ignore")).hexdigest()
        csrf_hash = hashlib.sha256(raw.encode("ascii")).hexdigest()
        with self.connect() as db:
            cursor = db.execute(
                "UPDATE sessions SET csrf_hash=? WHERE token_hash=? AND expires_at>=?",
                (csrf_hash, token_hash, utc_now()),
            )
        return raw if cursor.rowcount else ""

    def logout(self, token: str) -> None:
        token_hash = hashlib.sha256(token.encode("ascii", errors="ignore")).hexdigest()
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))

    def register_artifact(self, user_id: int, filename: str) -> None:
        expires = (datetime.now(timezone.utc) + timedelta(hours=ARTIFACT_HOURS)).isoformat(timespec="seconds")
        with self.connect() as db:
            db.execute("DELETE FROM artifacts WHERE expires_at < ?", (utc_now(),))
            db.execute(
                "INSERT OR REPLACE INTO artifacts(filename,user_id,expires_at,created_at) VALUES(?,?,?,?)",
                (filename, user_id, expires, utc_now()),
            )

    def owns_artifact(self, user_id: int, filename: str) -> bool:
        with self.connect() as db:
            row = db.execute(
                "SELECT 1 FROM artifacts WHERE filename=? AND user_id=? AND expires_at>=?",
                (filename, user_id, utc_now()),
            ).fetchone()
        return bool(row)

    def audit(
        self,
        user_id: int | None,
        event_type: str,
        project_id: str = "",
        detail: dict | None = None,
    ) -> str:
        created = utc_now()
        serialized = json.dumps(detail or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self.connect() as db:
            last = db.execute("SELECT event_hash FROM audit_events ORDER BY id DESC LIMIT 1").fetchone()
            previous = str(last["event_hash"] if last else "")
            material = f"{previous}|{user_id or ''}|{event_type}|{project_id}|{serialized}|{created}"
            event_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
            db.execute(
                "INSERT INTO audit_events(user_id,event_type,project_id,detail_json,previous_hash,event_hash,created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (user_id, event_type[:100], project_id[:80], serialized, previous, event_hash, created),
            )
        return event_hash

    def create_mcp_token(self, user_id: int, label: str = "Codex") -> str:
        token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
        expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(timespec="seconds")
        with self.connect() as db:
            db.execute("DELETE FROM mcp_tokens WHERE expires_at < ?", (utc_now(),))
            db.execute(
                "INSERT INTO mcp_tokens(token_hash,user_id,label,expires_at,created_at) VALUES(?,?,?,?,?)",
                (token_hash, user_id, str(label or "Codex")[:100], expires, utc_now()),
            )
        self.audit(user_id, "mcp.paired", detail={"label": str(label or "Codex")[:100]})
        return token

    def user_for_mcp_token(self, token: str) -> dict | None:
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode("ascii", errors="ignore")).hexdigest()
        with self.connect() as db:
            row = db.execute(
                "SELECT users.id,users.name,users.email FROM mcp_tokens "
                "JOIN users ON users.id=mcp_tokens.user_id WHERE token_hash=? AND expires_at>=?",
                (token_hash, utc_now()),
            ).fetchone()
            if row:
                db.execute("UPDATE mcp_tokens SET last_used_at=? WHERE token_hash=?", (utc_now(), token_hash))
        return dict(row) if row else None

    def save_mcp_proposal(self, user_id: int, project_id: str, proposal: dict, proposal_hash: str) -> dict:
        proposal_id = f"prop_{secrets.token_hex(10)}"
        created = datetime.now(timezone.utc)
        expires = created + timedelta(hours=24)
        serialized = json.dumps(proposal, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self.connect() as db:
            db.execute(
                "INSERT INTO mcp_proposals(id,user_id,project_id,proposal_hash,proposal_json,status,created_at,expires_at) "
                "VALUES(?,?,?,?,?,'pending',?,?)",
                (proposal_id, user_id, project_id, proposal_hash, serialized, created.isoformat(timespec="seconds"), expires.isoformat(timespec="seconds")),
            )
        self.audit(user_id, "mcp.proposal.created", project_id, {"proposalId": proposal_id, "hash": proposal_hash})
        return {"id": proposal_id, "status": "pending", "hash": proposal_hash, "expiresAt": expires.isoformat(timespec="seconds")}

    def list_mcp_proposals(self, user_id: int, statuses: tuple[str, ...] = ("pending", "approved")) -> list[dict]:
        placeholders = ",".join("?" for _ in statuses)
        with self.connect() as db:
            rows = db.execute(
                f"SELECT * FROM mcp_proposals WHERE user_id=? AND status IN ({placeholders}) AND expires_at>=? ORDER BY created_at DESC",
                (user_id, *statuses, utc_now()),
            ).fetchall()
        return [self._proposal_row(row) for row in rows]

    @staticmethod
    def _proposal_row(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"], "projectId": row["project_id"], "hash": row["proposal_hash"],
            "proposal": json.loads(row["proposal_json"]), "status": row["status"],
            "createdAt": row["created_at"], "expiresAt": row["expires_at"],
            "approvedAt": row["approved_at"], "appliedAt": row["applied_at"],
        }

    def get_mcp_proposal(self, user_id: int, proposal_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM mcp_proposals WHERE id=? AND user_id=?", (proposal_id, user_id)).fetchone()
        if not row:
            raise KeyError("Propuesta MCP no encontrada.")
        return self._proposal_row(row)

    def approve_mcp_proposal(self, user_id: int, proposal_id: str, expected_hash: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM mcp_proposals WHERE id=? AND user_id=?", (proposal_id, user_id)).fetchone()
            if not row:
                raise KeyError("Propuesta MCP no encontrada.")
            if row["status"] != "pending" or row["expires_at"] < utc_now():
                raise ValueError("La propuesta ya no puede aprobarse.")
            if not hmac.compare_digest(row["proposal_hash"], expected_hash):
                raise ValueError("La propuesta cambió después de ser mostrada.")
            db.execute("UPDATE mcp_proposals SET status='approved',approved_at=? WHERE id=?", (utc_now(), proposal_id))
        self.audit(user_id, "mcp.proposal.approved", row["project_id"], {"proposalId": proposal_id, "hash": expected_hash})
        return self.get_mcp_proposal(user_id, proposal_id)

    def reject_mcp_proposal(self, user_id: int, proposal_id: str) -> None:
        with self.connect() as db:
            row = db.execute("SELECT project_id FROM mcp_proposals WHERE id=? AND user_id=?", (proposal_id, user_id)).fetchone()
            if not row:
                raise KeyError("Propuesta MCP no encontrada.")
            db.execute("UPDATE mcp_proposals SET status='rejected' WHERE id=?", (proposal_id,))
        self.audit(user_id, "mcp.proposal.rejected", row["project_id"], {"proposalId": proposal_id})

    def supersede_stale_mcp_proposals(self, user_id: int, project_id: str) -> dict:
        superseded: list[str] = []
        with self.connect() as db:
            project_row = db.execute(
                "SELECT project_data FROM projects WHERE id=? AND user_id=?", (project_id, user_id)
            ).fetchone()
            if not project_row:
                raise KeyError("Proyecto no encontrado.")
            project_file = json.loads(project_row["project_data"])
            rows = db.execute(
                "SELECT id,proposal_json FROM mcp_proposals WHERE user_id=? AND project_id=? AND status IN ('pending','approved')",
                (user_id, project_id),
            ).fetchall()
            for row in rows:
                proposal = json.loads(row["proposal_json"])
                itemized = next(
                    (item for item in project_file.get("itemizados", []) if str(item.get("id")) == str(proposal.get("itemizedId") or "")),
                    None,
                )
                current = (itemized or {}).get("analyses", {}).get(str(proposal.get("conceptCode") or ""), [])
                current_hash = hashlib.sha256(
                    json.dumps(current, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                concept_code = str(proposal.get("conceptCode") or "")
                concept = next((entry for entry in ((itemized or {}).get("data") or {}).get("items", []) if str(entry.get("code")) == concept_code), None)
                current_inspector = ((itemized or {}).get("enrichment") or {}).get(concept_code, {})
                stale_quantity = "beforeQuantity" in proposal and (not concept or float(concept.get("quantity") or 0) != float(proposal.get("beforeQuantity") or 0))
                stale_description = "beforeDescription" in proposal and (not concept or str(concept.get("description") or "") != str(proposal.get("beforeDescription") or ""))
                stale_inspector = "beforeInspectorHash" in proposal and not hmac.compare_digest(
                    hashlib.sha256(json.dumps(current_inspector, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
                    str(proposal.get("beforeInspectorHash") or ""),
                )
                if not hmac.compare_digest(current_hash, str(proposal.get("beforeHash") or "")) or stale_quantity or stale_description or stale_inspector:
                    db.execute("UPDATE mcp_proposals SET status='superseded' WHERE id=? AND user_id=?", (row["id"], user_id))
                    superseded.append(str(row["id"]))
        if superseded:
            self.audit(user_id, "mcp.proposals.superseded", project_id, {"count": len(superseded), "proposalIds": superseded})
        return {"projectId": project_id, "status": "clean", "supersededCount": len(superseded)}

    def mark_mcp_proposal_applied(self, user_id: int, proposal_id: str) -> None:
        with self.connect() as db:
            cursor = db.execute(
                "UPDATE mcp_proposals SET status='applied',applied_at=? WHERE id=? AND user_id=? AND status='approved'",
                (utc_now(), proposal_id, user_id),
            )
        if not cursor.rowcount:
            raise ValueError("La propuesta no está aprobada o ya fue aplicada.")

    def apply_mcp_analysis(self, user_id: int, proposal_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM mcp_proposals WHERE id=? AND user_id=?", (proposal_id, user_id)).fetchone()
            if not row:
                raise KeyError("Propuesta MCP no encontrada.")
            if row["status"] != "approved" or row["expires_at"] < utc_now():
                raise ValueError("La propuesta no está aprobada o ya venció.")
            proposal = json.loads(row["proposal_json"])
            project_row = db.execute(
                "SELECT project_data FROM projects WHERE id=? AND user_id=?",
                (row["project_id"], user_id),
            ).fetchone()
            if not project_row:
                raise KeyError("Proyecto no encontrado.")
            project_file = json.loads(project_row["project_data"])
            itemized_id = str(proposal.get("itemizedId") or "")
            concept_code = str(proposal.get("conceptCode") or "")
            itemized = next((item for item in project_file.get("itemizados", []) if str(item.get("id")) == itemized_id), None)
            if not itemized:
                raise ValueError("El itemizado de la propuesta ya no existe.")
            analyses = itemized.setdefault("analyses", {})
            before = analyses.get(concept_code, [])
            before_hash = hashlib.sha256(
                json.dumps(before, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            if not hmac.compare_digest(before_hash, str(proposal.get("beforeHash") or "")):
                raise ValueError("El APU cambió después de la propuesta. Codex debe generar una nueva propuesta.")
            concept = next((entry for entry in (itemized.get("data") or {}).get("items", []) if str(entry.get("code")) == concept_code), None)
            if not concept:
                raise ValueError("La partida de la propuesta ya no existe.")
            if "beforeQuantity" in proposal and float(concept.get("quantity") or 0) != float(proposal.get("beforeQuantity") or 0):
                raise ValueError("La cantidad cambió después de la propuesta. Codex debe generar una nueva propuesta.")
            if "beforeDescription" in proposal and str(concept.get("description") or "") != str(proposal.get("beforeDescription") or ""):
                raise ValueError("La descripción cambió después de la propuesta. Codex debe generar una nueva propuesta.")
            current_inspector = itemized.get("enrichment", {}).get(concept_code, {})
            current_inspector_hash = hashlib.sha256(json.dumps(current_inspector, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            if "beforeInspectorHash" in proposal and not hmac.compare_digest(current_inspector_hash, str(proposal.get("beforeInspectorHash") or "")):
                raise ValueError("El inspector cambió después de la propuesta. Codex debe generar una nueva propuesta.")
            analyses[concept_code] = proposal["analysisRows"]
            if "quantity" in proposal:
                concept["quantity"] = proposal["quantity"]
            if "description" in proposal:
                concept["description"] = proposal["description"]
            if "inspector" in proposal:
                itemized.setdefault("enrichment", {})[concept_code] = proposal["inspector"]
            if not proposal.get("preserveOfficialPrice"):
                itemized.setdefault("dirtyAnalyses", {})[concept_code] = True
            affected_presto = {
                str(resource.get("prestoCode") or resource.get("code") or "").strip().upper()
                for resource in [*(before or []), *(proposal.get("analysisRows") or [])]
                if str(resource.get("prestoCode") or resource.get("code") or "").strip()
            }
            validate_resource_coding_consistency(project_file, affected_presto)
            serialized = json.dumps(project_file, ensure_ascii=False, separators=(",", ":"))
            summary = project_file_summary(project_file)
            now = utc_now()
            db.execute(
                "UPDATE projects SET project_data=?,direct_cost=?,partida_count=?,completed_count=?,updated_at=? "
                "WHERE id=? AND user_id=?",
                (serialized, summary["directCost"], summary["partidaCount"], summary["completedCount"], now, row["project_id"], user_id),
            )
            db.execute("UPDATE mcp_proposals SET status='applied',applied_at=? WHERE id=?", (now, proposal_id))
        self.audit(user_id, "mcp.proposal.applied", row["project_id"], {"proposalId": proposal_id, "hash": row["proposal_hash"]})
        return {"projectId": row["project_id"], "proposalId": proposal_id, "status": "applied"}

    def apply_mcp_authorized_bundle(self, user_id: int, entries: list[dict], authorization: str) -> dict:
        if not isinstance(entries, list) or not entries:
            raise ValueError("El lote MCP debe contener al menos una propuesta.")
        if len(entries) > 1000:
            raise ValueError("El lote MCP no puede contener más de 1.000 propuestas.")
        clean_authorization = str(authorization or "").strip()
        if not clean_authorization:
            raise ValueError("La aplicación masiva requiere registrar la autorización directa del usuario.")

        normalized: list[tuple[str, str]] = []
        seen_ids: set[str] = set()
        for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                raise ValueError(f"La propuesta {index} no tiene una estructura válida.")
            proposal_id = str(entry.get("proposalId") or "").strip()
            proposal_hash = str(entry.get("proposalHash") or "").strip().lower()
            if not proposal_id or not re.fullmatch(r"[0-9a-f]{64}", proposal_hash):
                raise ValueError(f"La propuesta {index} requiere proposalId y proposalHash SHA-256.")
            if proposal_id in seen_ids:
                raise ValueError(f"La propuesta {proposal_id} está repetida en el lote.")
            seen_ids.add(proposal_id)
            normalized.append((proposal_id, proposal_hash))

        batch_hash = hashlib.sha256(
            json.dumps(normalized, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        now = utc_now()
        project_id = ""
        applied_details: list[dict] = []

        with self.connect() as db:
            rows: list[sqlite3.Row] = []
            for proposal_id, expected_hash in normalized:
                row = db.execute(
                    "SELECT * FROM mcp_proposals WHERE id=? AND user_id=?",
                    (proposal_id, user_id),
                ).fetchone()
                if not row:
                    raise KeyError(f"Propuesta MCP no encontrada: {proposal_id}.")
                if row["status"] not in {"pending", "approved"} or row["expires_at"] < now:
                    raise ValueError(f"La propuesta {proposal_id} no está disponible para aplicación masiva.")
                if not hmac.compare_digest(row["proposal_hash"], expected_hash):
                    raise ValueError(f"El hash de la propuesta {proposal_id} no coincide.")
                if project_id and row["project_id"] != project_id:
                    raise ValueError("Todas las propuestas del lote deben pertenecer al mismo proyecto.")
                project_id = str(row["project_id"])
                rows.append(row)

            project_row = db.execute(
                "SELECT project_data FROM projects WHERE id=? AND user_id=?",
                (project_id, user_id),
            ).fetchone()
            if not project_row:
                raise KeyError("Proyecto no encontrado.")
            project_file = json.loads(project_row["project_data"])
            touched: set[tuple[str, str]] = set()
            affected_presto: set[str] = set()

            for row in rows:
                proposal = json.loads(row["proposal_json"])
                itemized_id = str(proposal.get("itemizedId") or "")
                concept_code = str(proposal.get("conceptCode") or "")
                target = (itemized_id, concept_code)
                if target in touched:
                    raise ValueError(f"El lote contiene más de una propuesta para la partida {concept_code}.")
                touched.add(target)
                itemized = next(
                    (item for item in project_file.get("itemizados", []) if str(item.get("id")) == itemized_id),
                    None,
                )
                if not itemized:
                    raise ValueError(f"El itemizado de la propuesta {row['id']} ya no existe.")
                analyses = itemized.setdefault("analyses", {})
                before = analyses.get(concept_code, [])
                affected_presto.update(
                    str(resource.get("prestoCode") or resource.get("code") or "").strip().upper()
                    for resource in [*(before or []), *(proposal.get("analysisRows") or [])]
                    if str(resource.get("prestoCode") or resource.get("code") or "").strip()
                )
                before_hash = hashlib.sha256(
                    json.dumps(before, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                if not hmac.compare_digest(before_hash, str(proposal.get("beforeHash") or "")):
                    raise ValueError(f"El APU {concept_code} cambió después de la propuesta.")
                concept = next((entry for entry in (itemized.get("data") or {}).get("items", []) if str(entry.get("code")) == concept_code), None)
                if not concept:
                    raise ValueError(f"La partida {concept_code} ya no existe.")
                if "beforeQuantity" in proposal and float(concept.get("quantity") or 0) != float(proposal.get("beforeQuantity") or 0):
                    raise ValueError(f"La cantidad {concept_code} cambió después de la propuesta.")
                if "beforeDescription" in proposal and str(concept.get("description") or "") != str(proposal.get("beforeDescription") or ""):
                    raise ValueError(f"La descripción {concept_code} cambió después de la propuesta.")
                current_inspector = itemized.get("enrichment", {}).get(concept_code, {})
                current_inspector_hash = hashlib.sha256(json.dumps(current_inspector, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
                if "beforeInspectorHash" in proposal and not hmac.compare_digest(current_inspector_hash, str(proposal.get("beforeInspectorHash") or "")):
                    raise ValueError(f"El inspector {concept_code} cambió después de la propuesta.")
                analyses[concept_code] = proposal["analysisRows"]
                if "quantity" in proposal:
                    concept["quantity"] = proposal["quantity"]
                if "description" in proposal:
                    concept["description"] = proposal["description"]
                if "inspector" in proposal:
                    itemized.setdefault("enrichment", {})[concept_code] = proposal["inspector"]
                if not proposal.get("preserveOfficialPrice"):
                    itemized.setdefault("dirtyAnalyses", {})[concept_code] = True
                applied_details.append({"proposalId": row["id"], "hash": row["proposal_hash"], "conceptCode": concept_code})

            validate_resource_coding_consistency(project_file, affected_presto)
            serialized = json.dumps(project_file, ensure_ascii=False, separators=(",", ":"))
            summary = project_file_summary(project_file)
            db.execute(
                "UPDATE projects SET project_data=?,direct_cost=?,partida_count=?,completed_count=?,updated_at=? "
                "WHERE id=? AND user_id=?",
                (serialized, summary["directCost"], summary["partidaCount"], summary["completedCount"], now, project_id, user_id),
            )
            for row in rows:
                db.execute(
                    "UPDATE mcp_proposals SET status='applied',approved_at=COALESCE(approved_at,?),applied_at=? "
                    "WHERE id=? AND user_id=?",
                    (now, now, row["id"], user_id),
                )

        self.audit(
            user_id,
            "mcp.bundle.applied",
            project_id,
            {
                "authorizationMode": "direct_mcp_user_request",
                "authorization": clean_authorization[:1000],
                "batchHash": batch_hash,
                "proposalCount": len(applied_details),
                "proposals": applied_details,
            },
        )
        return {
            "projectId": project_id,
            "status": "applied",
            "authorizationMode": "direct_mcp_user_request",
            "batchHash": batch_hash,
            "appliedCount": len(applied_details),
            "conceptCodes": [entry["conceptCode"] for entry in applied_details],
        }

    def list_companies(self, user_id: int) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT id,profile_data,is_default,created_at,updated_at FROM companies "
                "WHERE user_id=? ORDER BY is_default DESC,updated_at DESC",
                (user_id,),
            ).fetchall()
        companies = []
        for row in rows:
            profile = json.loads(str(row["profile_data"] or "{}"))
            companies.append({
                "id": row["id"], **profile, "isDefault": bool(row["is_default"]),
                "createdAt": row["created_at"], "updatedAt": row["updated_at"],
            })
        return companies

    def save_company(self, user_id: int, payload: dict) -> dict:
        profile = self.normalize_company_profile(payload.get("company"))
        company_id = str(payload.get("id") or secrets.token_hex(12))
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", company_id):
            raise ValueError("Identificador de empresa inválido.")
        make_default = bool(payload.get("isDefault"))
        now = utc_now()
        serialized = json.dumps(profile, ensure_ascii=False, separators=(",", ":"))
        with self.connect() as db:
            existing = db.execute("SELECT user_id,created_at FROM companies WHERE id=?", (company_id,)).fetchone()
            if existing and int(existing["user_id"]) != user_id:
                raise PermissionError("La empresa pertenece a otro usuario.")
            if not existing:
                company_count = int(db.execute("SELECT COUNT(*) FROM companies WHERE user_id=?", (user_id,)).fetchone()[0])
                if company_count >= 1:
                    raise PermissionError("OpenAPU permite identificar una sola empresa.")
            has_default = db.execute(
                "SELECT 1 FROM companies WHERE user_id=? AND is_default=1 LIMIT 1", (user_id,)
            ).fetchone()
            is_default = 1 if make_default or not has_default else 0
            if is_default:
                db.execute("UPDATE companies SET is_default=0 WHERE user_id=?", (user_id,))
            if existing:
                db.execute(
                    "UPDATE companies SET name=?,profile_data=?,is_default=?,updated_at=? WHERE id=? AND user_id=?",
                    (profile["name"], serialized, is_default, now, company_id, user_id),
                )
                created_at = str(existing["created_at"])
            else:
                db.execute(
                    "INSERT INTO companies(id,user_id,name,profile_data,is_default,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (company_id, user_id, profile["name"], serialized, is_default, now, now),
                )
                created_at = now
        self.audit(user_id, "company.saved", detail={"companyId": company_id, "name": profile["name"]})
        return {"id": company_id, **profile, "isDefault": bool(is_default), "createdAt": created_at, "updatedAt": now}

    def save_project(self, user_id: int, payload: dict) -> dict:
        project_file = payload.get("projectFile")
        if not isinstance(project_file, dict) or project_file.get("format") != "CodeAPU-PROJECT":
            raise ValueError("El proyecto CodeAPU no tiene una estructura válida.")
        project = project_file.get("project") or {}
        summary = payload.get("summary") or {}
        project_id = str(payload.get("id") or secrets.token_hex(12))
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", project_id):
            raise ValueError("Identificador de proyecto inválido.")
        name = str(project.get("name") or summary.get("name") or "Proyecto sin nombre").strip()[:200]
        now = utc_now()
        serialized = json.dumps(project_file, ensure_ascii=False, separators=(",", ":"))
        values = (
            name, str(project.get("code") or "")[:100], str(project.get("client") or "")[:200],
            str(project.get("location") or "")[:200], str(project.get("tender") or "")[:120],
            str(project.get("responsible") or "")[:160], float(summary.get("directCost") or 0),
            int(summary.get("partidaCount") or 0), int(summary.get("completedCount") or 0), serialized, now,
        )
        economic_changes: list[dict] = []
        quantity_changes: list[dict] = []
        with self.connect() as db:
            existing = db.execute("SELECT user_id,created_at,project_data FROM projects WHERE id=?", (project_id,)).fetchone()
            if existing and int(existing["user_id"]) != user_id:
                raise PermissionError("El proyecto pertenece a otro usuario.")
            if not existing:
                project_count = int(db.execute("SELECT COUNT(*) FROM projects WHERE user_id=?", (user_id,)).fetchone()[0])
                if project_count >= 3:
                    raise PermissionError("OpenAPU permite hasta 3 proyectos. Suscríbete a CodeAPU o adquiere la versión Full para crear el cuarto.")
            if existing:
                expected_hash = str(payload.get("expectedProjectHash") or "").strip().lower()
                current_hash = hashlib.sha256(str(existing["project_data"] or "").encode("utf-8")).hexdigest()
                if not expected_hash or not hmac.compare_digest(expected_hash, current_hash):
                    raise ProjectVersionConflict(
                        "El proyecto cambió por MCP u otra sesión. Vuelve a abrirlo antes de guardar para no sobrescribir los cambios recientes."
                    )
                previous_project = json.loads(str(existing["project_data"] or "{}"))
                economic_changes = resource_economic_changes(previous_project, project_file)
                quantity_changes = budget_quantity_changes(previous_project, project_file)
                if economic_changes:
                    touched_presto = {
                        code
                        for change in economic_changes
                        for code in (change["beforePrestoCode"], change["afterPrestoCode"])
                        if code
                    }
                    validate_resource_coding_consistency(project_file, touched_presto)
                db.execute(
                    "UPDATE projects SET name=?,code=?,client=?,location=?,tender=?,responsible=?,direct_cost=?,"
                    "partida_count=?,completed_count=?,project_data=?,updated_at=? WHERE id=? AND user_id=?",
                    (*values, project_id, user_id),
                )
            else:
                db.execute(
                    "INSERT INTO projects(id,user_id,name,code,client,location,tender,responsible,direct_cost,"
                    "partida_count,completed_count,project_data,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (project_id, user_id, *values[:-1], now, now),
                )
        self.audit(user_id, "project.saved", project_id, {"name": name})
        if economic_changes:
            self.audit(user_id, "project.resources.edited", project_id, {
                "authorization": "Edición directa del usuario autenticado en vista Recursos",
                "changeCount": len(economic_changes),
                "changes": economic_changes[:500],
                "truncated": len(economic_changes) > 500,
            })
        if quantity_changes:
            self.audit(user_id, "project.quantities.edited", project_id, {
                "authorization": "Edición directa del usuario autenticado en vista Presupuesto",
                "changeCount": len(quantity_changes),
                "changes": quantity_changes[:500],
                "truncated": len(quantity_changes) > 500,
            })
        return self.get_project_meta(user_id, project_id)

    def refresh_project_summary(self, user_id: int, project_id: str) -> dict:
        with self.connect() as db:
            row = db.execute(
                "SELECT project_data FROM projects WHERE id=? AND user_id=?", (project_id, user_id)
            ).fetchone()
            if not row:
                raise KeyError("Proyecto no encontrado.")
            project_file = json.loads(row["project_data"])
            summary = project_file_summary(project_file)
            now = utc_now()
            db.execute(
                "UPDATE projects SET direct_cost=?,partida_count=?,completed_count=?,updated_at=? "
                "WHERE id=? AND user_id=?",
                (summary["directCost"], summary["partidaCount"], summary["completedCount"], now, project_id, user_id),
            )
        return self.get_project_meta(user_id, project_id)

    @staticmethod
    def row_meta(row: sqlite3.Row) -> dict:
        loaded_count = 0
        try:
            project_file = json.loads(row["project_data"])
            itemizeds = project_file.get("itemizados") or []
            active_id = str(project_file.get("activeItemizedId") or "")
            itemized = next((entry for entry in itemizeds if str(entry.get("id") or "") == active_id), None)
            if itemized is None:
                itemized = itemizeds[0] if itemizeds else {}
            data = itemized.get("data") or {}
            analyses = itemized.get("analyses") or {}
            partidas = [
                item for item in (data.get("items") or [])
                if (
                    (
                        bool(item.get("isPartida")) if item.get("isPartida") is not None
                        else bool(str(item.get("unit") or "").strip())
                    )
                    and not bool(item.get("hiddenInBudgetViewer"))
                )
            ]
            loaded_count = sum(1 for item in partidas if analyses.get(str(item.get("code") or "")))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            loaded_count = 0
        return {
            "id": row["id"], "name": row["name"], "code": row["code"], "client": row["client"],
            "location": row["location"], "tender": row["tender"], "responsible": row["responsible"],
            "directCost": row["direct_cost"], "partidaCount": row["partida_count"],
            "loadedCount": loaded_count, "completedCount": row["completed_count"],
            "createdAt": row["created_at"], "updatedAt": row["updated_at"],
            "projectHash": hashlib.sha256(str(row["project_data"] or "").encode("utf-8")).hexdigest(),
        }

    def get_project_meta(self, user_id: int, project_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM projects WHERE id=? AND user_id=?", (project_id, user_id)).fetchone()
        if not row:
            raise KeyError("Proyecto no encontrado.")
        return self.row_meta(row)

    def list_projects(self, user_id: int) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM projects WHERE user_id=? ORDER BY updated_at DESC", (user_id,)).fetchall()
        return [self.row_meta(row) for row in rows]

    def load_project(self, user_id: int, project_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT project_data FROM projects WHERE id=? AND user_id=?", (project_id, user_id)).fetchone()
        if not row:
            raise KeyError("Proyecto no encontrado.")
        return json.loads(row["project_data"])

    def delete_project(self, user_id: int, project_id: str) -> None:
        with self.connect() as db:
            cursor = db.execute("DELETE FROM projects WHERE id=? AND user_id=?", (project_id, user_id))
        if not cursor.rowcount:
            raise KeyError("Proyecto no encontrado.")
        self.audit(user_id, "project.deleted", project_id)

