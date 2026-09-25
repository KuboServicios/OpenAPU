from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

from account_store import AccountStore
from apu import ApuCalculator, as_number
from app_paths import data_root, resource_dir


PROTOCOL_VERSION = "2025-06-18"
SERVER_VERSION = "1.1.0"
_FALLBACK_INSTRUCTIONS = (
    "CodeAPU MCP consulta y valida antes de modificar. Las propuestas originadas en el inspector requieren aprobación "
    "individual y codeapu_apply_approved_proposal. Cuando el usuario ordena directamente por MCP aplicar un lote, "
    "codeapu_apply_authorized_bundle valida todos los hashes y APU de origen y lo aplica de forma transaccional, dejando "
    "auditoría de la autorización directa. No inventes precios ni rendimientos: identifica todo supuesto. "
    "Respeta prefijos M/O/E/S y auxiliares M%AUX=0,05, E%AUX=0,05, O%AUX=0,35. "
    "Todo subcontrato S sin desglose documentado se abre conservando el costo total: O=25%, M=60% y E=15%, sin doble cargo. "
    "La distribución se expresa sólo en costos y tipos; la descripción conserva un nombre simple, sin porcentajes ni metadatos de origen. Los informes generan "
    "por separado el código maestro PRESTO y el código CodeAPU tipo + destino + subdestino + partida + correlativo conforme a REGLA_NOMENCLATURA_RECURSOS.md; "
    "la dependencia propia o subcontratada no cambia por sí sola la naturaleza O a S. Respeta también "
    "la clasificación, distribución y tarifas de mano de obra conforme a REGLA_ANALISIS_MANO_OBRA.md. "
    "Las distribuciones porcentuales son sólo respaldo para partidas sin APU verificable por EETT o subcontratos externos sin desglose. Si existe APU analizable, usa sus recursos, HH, rendimientos y dependencias reales. MIXTA conserva una sola fila y nunca duplica maestro o ayudante. "
    "Antes de proponer usa codeapu_get_apu_generation_rules. Para enriquecer una partida utiliza exclusivamente EETT, "
    "planificación y antecedentes del proyecto; si falta evidencia, solicita información."
)


def load_local_instructions() -> str:
    canonical = Path(__file__).resolve().parent.parent / "00_ECOSISTEMA_LOCAL" / "CODEX_MCP.md"
    try:
        text = canonical.read_text(encoding="utf-8").strip()
        if text:
            return text
    except OSError:
        pass
    return _FALLBACK_INSTRUCTIONS


INSTRUCTIONS = load_local_instructions()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def effective_apu_snapshot(itemized: dict, code: str, concept: dict | None, rows: list[dict]) -> dict:
    """Expone por MCP el precio vigente del APU sin perder el precio histórico importado."""
    source_price = as_number((concept or {}).get("price"))
    quantity = as_number((concept or {}).get("quantity"))
    if rows:
        effective_price = float(ApuCalculator(itemized.get("analyses") or {}, max_code_length=50).calculate(code)[0])
        price_source = "APU_CALCULATED"
    else:
        effective_price = source_price
        price_source = "CONCEPT_SOURCE"
    return {
        "sourcePrice": source_price,
        "effectivePrice": effective_price,
        "effectiveQuantity": quantity,
        "effectiveTotal": effective_price * quantity,
        "priceSource": price_source,
    }


def number(value: Any, field: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} debe ser numérico.") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError(f"{field} debe ser un número finito mayor o igual a cero.")
    return parsed


def factor_number(value: Any, field: str) -> float:
    """Acepta factores decimales y rendimientos escritos como /36 o 1/36."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return number(value, field)
    text = str(value or "").strip().replace(" ", "").replace("$", "")
    if "/" not in text:
        return number(text.replace(",", "."), field)
    parts = text.split("/")
    if len(parts) != 2 or not parts[1]:
        raise ValueError(f"{field} debe ser numérico o un rendimiento como /36 o 1/36.")
    numerator = number((parts[0] or "1").replace(",", "."), f"Numerador de {field.lower()}")
    denominator = number(parts[1].replace(",", "."), f"Denominador de {field.lower()}")
    if denominator <= 0:
        raise ValueError(f"El denominador de {field.lower()} debe ser mayor que cero.")
    return numerator / denominator


DESTINATION_CODES = {"Z00", "Z01", "Z02", "Z03", "Z04", "Z05", "Z06", "Z07", "Z08", "Z09", "Z10", "Z11", "IF", "OP", "OG", "TE", "ESSA", "ESEL", "ESCL", "ESGC", "ESOE", "ESPJ", "ESTV", "ESSV", "OF", "GG"}
SUBDESTINATION_CODES = {"S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10", "S11", "S12", "S13", "S14", "S15", "S16", "S17", "S18", "CT", "MT", "HO", "EN", "MO", "MD", "AL", "IM", "TA", "CI", "RE", "PI", "PV", "CU", "SA", "EL", "CD", "CL", "GC", "FL", "OE", "PJ", "TV", "GEN", "GE"}
DEPENDENCIES = {"EMPRESA", "KUBO", "SUBCONTRATO", "MIXTA", "COMPRA", "ARRIENDO", "PROPIO", "PROVEEDOR", "AUXILIAR"}
TECHNICAL_BASES = {"PENDIENTE", "EETT", "ALTERNATIVO", "MODIFICADO_CONSULTA", "RDI_NOTA_CAMBIO", "DECISION_ESTUDIO"}
PRICE_STATUSES = {"PENDIENTE", "REFERENCIAL", "COTIZADO", "CONTRATO"}


def validate_rows(raw_rows: Any, partida_source_code: str = "", require_complete_coding: bool = False, require_polhem_coding: bool = False) -> tuple[list[dict], list[str]]:
    if not isinstance(raw_rows, list) or not raw_rows:
        raise ValueError("analysisRows debe contener al menos un recurso.")
    if len(raw_rows) > 500:
        raise ValueError("Un APU no puede contener más de 500 recursos.")
    rows: list[dict] = []
    warnings: list[str] = []
    seen: set[str] = set()
    used_correlatives: dict[str, set[int]] = {}
    auxiliary = {"M%AUX": 0.05, "E%AUX": 0.05, "O%AUX": 0.35}
    for index, raw in enumerate(raw_rows, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"La fila {index} no tiene una estructura válida.")
        code = str(raw.get("code") or "").strip().upper()[:50]
        description = str(raw.get("description") or "").strip()[:300]
        unit = str(raw.get("unit") or "").strip().upper()[:20]
        is_subanalysis = bool(raw.get("isSubanalysis"))
        if not code or not description or not unit:
            raise ValueError(f"La fila {index} requiere código, descripción y unidad.")
        if code in seen:
            raise ValueError(f"El recurso {code} está repetido dentro del APU.")
        seen.add(code)
        if code in auxiliary:
            quantity = auxiliary[code]
            unit = "%"
            unit_price = number(raw.get("unitPrice", 0), f"Precio unitario de {code}")
        else:
            if not is_subanalysis and code[0] not in {"M", "O", "E", "S"}:
                raise ValueError(f"El recurso {code} no usa un prefijo M, O, E o S.")
            quantity = number(raw.get("quantity", 0), f"Cantidad de {code}")
            raw_factor = raw.get("factor")
            factor = 1.0 if raw_factor is None or str(raw_factor).strip() == "" else factor_number(raw_factor, f"Factor de {code}")
            unit_price = number(raw.get("unitPrice", 0), f"Precio unitario de {code}")
        row = {
            "code": code,
            "description": description,
            "unit": unit,
            "quantity": quantity,
            "factor": 1.0 if code in auxiliary else factor,
            "unitPrice": unit_price,
        }
        if is_subanalysis:
            row["isSubanalysis"] = True
        resource_type = str(raw.get("resourceType") or code[:1]).strip().upper()
        # Las familias PRESTO admiten Ñ porque el código visible se exporta en
        # Windows-1252. Esto permite familias semánticas como MSÑ sin recortarlas
        # silenciosamente a MS durante la validación MCP.
        family = re.sub(r"[^A-ZÑ0-9%]", "", str(raw.get("resourceFamilyCode") or "").strip().upper())[:12]
        presto_code = str(raw.get("prestoCode") or code).strip().upper()[:50]
        dependency = str(raw.get("dependency") or "").strip().upper()[:30]
        destination = str(raw.get("destinationCode") or "").strip().upper()
        subdestination = str(raw.get("subdestinationCode") or "").strip().upper()
        partida = re.sub(r"[^A-Za-z0-9.]", "", str(raw.get("partidaSourceCode") or partida_source_code).strip())[:80]
        if resource_type not in {"M", "O", "E", "S"}:
            raise ValueError(f"Tipo de recurso no válido en {code}.")
        if presto_code not in auxiliary and (not presto_code or presto_code[0] != resource_type):
            raise ValueError(f"Código PRESTO no válido en {code}: {presto_code}.")
        if destination and destination not in DESTINATION_CODES:
            raise ValueError(f"Destino no válido en {code}: {destination}.")
        if subdestination and subdestination not in SUBDESTINATION_CODES:
            raise ValueError(f"Subdestino no válido en {code}: {subdestination}.")
        if dependency and dependency not in DEPENDENCIES:
            raise ValueError(f"Dependencia no válida en {code}: {dependency}.")
        correlation_text = str(raw.get("relationCorrelative") or "").strip()
        correlation = int(correlation_text) if correlation_text.isdigit() and int(correlation_text) > 0 else 0
        if destination and subdestination and partida:
            context_key = f"{resource_type}|{destination}|{subdestination}|{partida}"
            occupied = used_correlatives.setdefault(context_key, set())
            if not correlation or correlation in occupied:
                correlation = 1
                while correlation in occupied:
                    correlation += 1
            occupied.add(correlation)
        sequence = f"{correlation:02d}" if correlation else ""
        status_text = str(raw.get("classificationStatus") or "").strip().casefold()
        status = "confirmado" if status_text in {"confirmado", "validado", "confirmed"} else "inferido"
        polhem_project = re.sub(r"[^A-Z0-9]", "", str(raw.get("polhemProjectCode") or "").strip().upper())[:12]
        polhem_zone = re.sub(r"[^A-Z0-9]", "", str(raw.get("polhemZoneCode") or "").strip().upper())[:3]
        polhem_system = re.sub(r"[^A-Z0-9]", "", str(raw.get("polhemSystemCode") or "").strip().upper())[:3]
        polhem_entity = re.sub(r"[^A-Z0-9]", "", str(raw.get("polhemEntityCode") or "").strip().upper())[:4]
        polhem_partida = str(raw.get("polhemPartidaCode") or "").strip().upper()[:50]
        polhem_presto = str(raw.get("polhemPrestoCode") or "").strip().upper()[:13]
        expected_polhem_presto = f"{polhem_zone}{polhem_system}{polhem_entity}{str(raw.get('polhemPartidaCode') or '').rsplit('-', 1)[-1]}" if polhem_partida and "-" in polhem_partida else ""
        if polhem_presto and (not re.fullmatch(r"[A-Z0-9]{1,13}", polhem_presto) or (expected_polhem_presto and polhem_presto != expected_polhem_presto)):
            raise ValueError(f"Código PRESTO POLHEM no válido en {code}: {polhem_presto}.")
        technical_basis = str(raw.get("technicalBasis") or "PENDIENTE").strip().upper()
        price_status = str(raw.get("priceStatus") or ("REFERENCIAL" if unit_price > 0 else "PENDIENTE")).strip().upper()
        if technical_basis not in TECHNICAL_BASES:
            raise ValueError(f"Base técnica no válida en {code}: {technical_basis}.")
        if price_status not in PRICE_STATUSES:
            raise ValueError(f"Estado de precio no válido en {code}: {price_status}.")
        if any((family, dependency, destination, subdestination, partida, sequence)) or require_complete_coding:
            if not family:
                family = f"{resource_type}GE"
            row.update({
                "relationId": str(raw.get("relationId") or f"rel-{hashlib.sha256(f'{partida}|{code}|{index}'.encode()).hexdigest()[:20]}")[:100],
                "prestoCode": presto_code,
                "legacyPrestoCode": str(raw.get("legacyPrestoCode") or code).strip().upper()[:50],
                "resourceType": resource_type,
                "resourceFamilyCode": family,
                "familyItemSequence": str(raw.get("familyItemSequence") or (re.search(r"(\d+)$", presto_code).group(1) if re.search(r"(\d+)$", presto_code) else ""))[-4:],
                "dependency": dependency,
                "destinationCode": destination,
                "subdestinationCode": subdestination,
                "partidaSourceCode": partida,
                "relationCorrelative": sequence,
                "codeapuCode": f"{resource_type}-{destination}-{subdestination}-{partida}-{sequence}" if destination and subdestination and partida and sequence else "",
                "polhemProjectCode": polhem_project,
                "polhemZoneCode": polhem_zone,
                "polhemSystemCode": polhem_system,
                "polhemEntityCode": polhem_entity,
                "polhemPartidaCode": polhem_partida,
                "polhemPrestoCode": polhem_presto,
                "polhemCodingStatus": "confirmado" if all((polhem_project, polhem_zone, polhem_system, polhem_entity, polhem_partida, polhem_presto)) else "pendiente",
                "classificationOrigin": str(raw.get("classificationOrigin") or "normalización MCP CodeAPU")[:300],
                "classificationRule": str(raw.get("classificationRule") or "")[:1000],
                "classificationStatus": status,
                "familyClassificationConfirmed": bool(raw.get("familyClassificationConfirmed")) or status == "confirmado",
                "subdestinationClassificationConfirmed": bool(raw.get("subdestinationClassificationConfirmed")) or status == "confirmado",
                "resourceSource": str(raw.get("resourceSource") or "")[:2000],
                "resourceNotes": str(raw.get("resourceNotes") or "")[:3000],
                "technicalBasis": technical_basis,
                "priceStatus": price_status,
                "changeReference": str(raw.get("changeReference") or "")[:1000],
                "costTimingDecision": str(raw.get("costTimingDecision") or "")[:3000],
                "codingVersion": 13 if polhem_presto else 11,
            })
            if bool(raw.get("manualUnitPriceOverride")):
                row.update({
                    "manualUnitPriceOverride": True,
                    "manualUnitPriceUpdatedAt": str(raw.get("manualUnitPriceUpdatedAt") or "")[:50],
                    "manualUnitPriceUpdatedBy": str(raw.get("manualUnitPriceUpdatedBy") or "usuario CodeAPU")[:200],
                })
        if require_complete_coding:
            required_fields = [("familia", family), ("dependencia", dependency), ("destino", destination), ("subdestino", subdestination), ("partida", partida), ("correlativo", sequence)]
            if require_polhem_coding:
                required_fields.extend((("proyecto POLHEM", polhem_project), ("zona POLHEM", polhem_zone), ("sistema POLHEM", polhem_system), ("entidad POLHEM", polhem_entity), ("partida POLHEM", polhem_partida), ("código PRESTO POLHEM", polhem_presto)))
            missing = [label for label, value in required_fields if not value]
            if missing:
                raise ValueError(f"{code} no puede incorporarse al lote de normalización; falta: {', '.join(missing)}.")
        rows.append(row)
        if unit_price == 0 and code not in auxiliary:
            warnings.append(f"{code} tiene precio unitario cero.")
        if code.startswith("S") and not is_subanalysis:
            warnings.append(
                f"{code} es un subcontrato integral: debe reemplazarse por un desglose de respaldo "
                "O=25%, M=60% y E=15%, salvo que exista un desglose documentado más preciso."
            )
    resource_order = {
        "M": 0, "M%AUX": 1,
        "O": 2, "O%AUX": 3,
        "E": 4, "E%AUX": 5,
        "S": 6,
    }

    def order_key(indexed_row: tuple[int, dict]) -> tuple[int, int]:
        index, row = indexed_row
        code = str(row.get("code") or "").upper()
        group = code if code in {"M%AUX", "O%AUX", "E%AUX"} else code[:1]
        return resource_order.get(group, 7), index

    ordered_rows = [row for _, row in sorted(enumerate(rows), key=order_key)]
    if [row["code"] for row in ordered_rows] != [row["code"] for row in rows]:
        warnings.append(
            "Los recursos fueron ordenados según la secuencia CodeAPU: "
            "M, M%AUX, O, O%AUX, E, E%AUX y S."
        )
    return ordered_rows, warnings


INSPECTOR_LIMITS = {
    "executiveSummary": 2000, "executionDays": 100,
    "reviewStatus": 100, "studyProductivity": 300,
    "theoreticalProductivity": 300, "crewComposition": 300, "directPlacement": 300,
    "requiredProductivity": 300, "scheduleDemand": 500, "productivityBasis": 2000,
    "equipmentUsage": 2000, "rentalBasis": 2000, "technicalSources": 2000,
    "eettRequirements": 5000, "eettConsidered": 5000,
    "eettDecisions": 5000, "eettPending": 5000,
    "decisionOwner": 300, "decisionDate": 50, "executorDecision": 3000,
    "aiProductivityAdjustment": 3000,
    "aiCostAdjustment": 3000, "aiAnalysis": 5000,
}


def validate_inspector(raw: Any) -> dict:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("inspector debe ser un objeto.")
    unknown = set(raw) - set(INSPECTOR_LIMITS)
    if unknown:
        raise ValueError(f"Campos de inspector no permitidos: {', '.join(sorted(unknown))}.")
    return {key: str(value or "").strip()[:INSPECTOR_LIMITS[key]] for key, value in raw.items()}


def is_cost_neutral_recode(before_rows: Any, after_rows: Any) -> bool:
    if not isinstance(before_rows, list) or not isinstance(after_rows, list) or len(before_rows) != len(after_rows):
        return False
    auxiliary = {"M%AUX", "E%AUX", "O%AUX"}
    for before, after in zip(before_rows, after_rows):
        if not isinstance(before, dict) or not isinstance(after, dict):
            return False
        before_code = str(before.get("code") or "").strip().upper()
        after_code = str(after.get("code") or "").strip().upper()
        if before_code != after_code:
            if before_code[:1] not in {"M", "O", "E", "S"} or before_code[:1] != after_code[:1]:
                return False
            if before_code in auxiliary or after_code in auxiliary or before.get("isSubanalysis") or after.get("isSubanalysis"):
                return False
        if str(before.get("description") or "").strip() != str(after.get("description") or "").strip():
            return False
        is_auxiliary = before_code == after_code and before_code in auxiliary
        if not is_auxiliary and str(before.get("unit") or "").strip().upper() != str(after.get("unit") or "").strip().upper():
            return False
        if number(before.get("quantity", 0), "Cantidad") != number(after.get("quantity", 0), "Cantidad"):
            return False
        is_subanalysis = bool(before.get("isSubanalysis")) and bool(after.get("isSubanalysis"))
        if not is_subanalysis and not is_auxiliary and number(before.get("unitPrice", 0), "Precio unitario") != number(after.get("unitPrice", 0), "Precio unitario"):
            return False
        if bool(before.get("isSubanalysis")) != bool(after.get("isSubanalysis")):
            return False
    return True


class CodeApuMcp:
    def __init__(self) -> None:
        root = data_root(self._argument("--data-dir"))
        self.store = AccountStore(root / "data" / "codeapu.db")
        self.token = os.environ.get("CodeAPU_MCP_TOKEN", "")

    @staticmethod
    def _argument(name: str) -> str | None:
        try:
            return sys.argv[sys.argv.index(name) + 1]
        except (ValueError, IndexError):
            return None

    def user(self) -> dict:
        # CodeAPU corre en modo local de un solo usuario: no exige un token de vinculación
        # con caducidad. Si se configuró CodeAPU_MCP_TOKEN y sigue vigente se respeta (permite
        # distinguir cuentas en instalaciones con más de un usuario); si no, se usa
        # automáticamente el usuario local principal.
        user = self.store.user_for_mcp_token(self.token) if self.token else None
        if not user:
            user = self.store.local_user()
        return user

    def tools(self) -> list[dict]:
        return [
            self.tool("codeapu_list_projects", "Lista los proyectos CodeAPU del usuario vinculado.", {}, True),
            self.tool("codeapu_get_apu_generation_rules", "Devuelve las reglas completas y campos editables para generar APU y enriquecer el inspector.", {}, True),
            self.tool("codeapu_get_project_summary", "Obtiene metadatos y estructura general de un proyecto sin modificarlo.", {"projectId": {"type": "string"}}, True, ["projectId"]),
            self.tool("codeapu_get_normalization_scope", "Audita todas las relaciones partida-recurso y devuelve las brechas de codificación necesarias para preparar una normalización masiva.", {"projectId": {"type": "string"}, "itemizedId": {"type": "string"}}, True, ["projectId"]),
            self.tool(
                "codeapu_search_concepts",
                "Busca conceptos por código o descripción dentro de un itemizado, sin devolver el proyecto completo ni modificarlo.",
                {"projectId": {"type": "string"}, "itemizedId": {"type": "string"}, "query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 100}},
                True,
                ["projectId", "itemizedId", "query"],
            ),
            self.tool("codeapu_get_apu", "Obtiene las filas del APU de una partida específica.", {"projectId": {"type": "string"}, "itemizedId": {"type": "string"}, "conceptCode": {"type": "string"}}, True, ["projectId", "itemizedId", "conceptCode"]),
            self.tool("codeapu_get_partida_context", "Obtiene APU e inspector Rendimiento/Técnico/IA de una partida para analizarla sin modificarla.", {"projectId": {"type": "string"}, "itemizedId": {"type": "string"}, "conceptCode": {"type": "string"}}, True, ["projectId", "itemizedId", "conceptCode"]),
            self.tool("codeapu_validate_apu", "Valida recursos; requirePolhemCoding exige la clasificación previa Proyecto-Zona-Sistema-Entidad-Partida.", {"analysisRows": {"type": "array", "items": {"type": "object"}}, "partidaSourceCode": {"type": "string"}, "requireCompleteCoding": {"type": "boolean"}, "requirePolhemCoding": {"type": "boolean"}}, True, ["analysisRows"]),
            self.tool("codeapu_propose_apu", "Registra una propuesta inmutable; todavía no modifica el proyecto. requirePolhemCoding exige la clasificación previa POLHEM. preserveOfficialPrice solo admite una recodificación neutral.", {"projectId": {"type": "string"}, "itemizedId": {"type": "string"}, "conceptCode": {"type": "string"}, "reason": {"type": "string"}, "analysisRows": {"type": "array", "items": {"type": "object"}}, "description": {"type": "string", "minLength": 1, "maxLength": 500}, "quantity": {"type": "number", "minimum": 0}, "inspector": {"type": "object"}, "preserveOfficialPrice": {"type": "boolean"}, "normalizationMode": {"type": "boolean"}, "requirePolhemCoding": {"type": "boolean"}}, False, ["projectId", "itemizedId", "conceptCode", "reason", "analysisRows"]),
            self.tool("codeapu_apply_approved_proposal", "Aplica exclusivamente una propuesta cuyo mismo hash fue aprobado dentro de CodeAPU.", {"proposalId": {"type": "string"}, "proposalHash": {"type": "string"}}, False, ["proposalId", "proposalHash"], destructive=True),
            self.tool(
                "codeapu_apply_authorized_bundle",
                "Aplica de forma masiva y transaccional un lote pedido directamente por el usuario vía MCP; valida cada ID, hash y APU de origen y registra la autorización en auditoría.",
                {
                    "authorization": {"type": "string"},
                    "proposals": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"proposalId": {"type": "string"}, "proposalHash": {"type": "string"}},
                            "required": ["proposalId", "proposalHash"],
                            "additionalProperties": False,
                        },
                    },
                },
                False,
                ["authorization", "proposals"],
                destructive=True,
            ),
            self.tool("codeapu_supersede_stale_proposals", "Marca como obsoletas las propuestas pendientes o aprobadas cuyo hash APU de origen ya no coincide con el proyecto vigente.", {"projectId": {"type": "string"}}, False, ["projectId"]),
        ]

    @staticmethod
    def tool(name: str, description: str, properties: dict, read_only: bool, required: list[str] | None = None, destructive: bool = False) -> dict:
        return {
            "name": name,
            "description": description,
            "inputSchema": {"type": "object", "properties": properties, "required": required or [], "additionalProperties": False},
            "annotations": {"readOnlyHint": read_only, "destructiveHint": destructive, "idempotentHint": read_only},
        }

    def call(self, name: str, args: dict) -> dict:
        user = self.user()
        user_id = int(user["id"])
        if name not in {"codeapu_list_projects", "codeapu_get_apu_generation_rules", "codeapu_get_project_summary", "codeapu_get_normalization_scope", "codeapu_search_concepts", "codeapu_get_apu", "codeapu_get_partida_context", "codeapu_validate_apu", "codeapu_propose_apu", "codeapu_apply_approved_proposal", "codeapu_apply_authorized_bundle", "codeapu_supersede_stale_proposals"}:
            raise KeyError(f"Herramienta desconocida: {name}")
        if name == "codeapu_list_projects":
            return {"projects": self.store.list_projects(user_id)}
        if name == "codeapu_get_apu_generation_rules":
            rules_path = resource_dir() / "REGLAS_IA_APU.md"
            generation_path = resource_dir() / "REGLAS_GENERACION_APU.md"
            normalization_path = resource_dir() / "REGLAS_NORMALIZACION.md"
            naming_path = resource_dir() / "REGLA_NOMENCLATURA_RECURSOS.md"
            labor_path = resource_dir() / "REGLA_ANALISIS_MANO_OBRA.md"
            schema_path = resource_dir() / "apu_ai_schema.json"
            return {
                "rules": rules_path.read_text(encoding="utf-8") if rules_path.is_file() else INSTRUCTIONS,
                "apuGenerationRules": generation_path.read_text(encoding="utf-8") if generation_path.is_file() else "",
                "normalizationRules": normalization_path.read_text(encoding="utf-8") if normalization_path.is_file() else "",
                "resourceNamingRules": naming_path.read_text(encoding="utf-8") if naming_path.is_file() else "",
                "laborAnalysisRules": labor_path.read_text(encoding="utf-8") if labor_path.is_file() else "",
                "proposalSchema": json.loads(schema_path.read_text(encoding="utf-8")) if schema_path.is_file() else {},
                "mandatoryFlow": {
                    "inspector": ["read", "validate", "propose", "human_approval", "apply_exact_hash"],
                    "directMcpBundle": ["read", "validate", "direct_user_request", "apply_authorized_bundle"],
                },
            }
        if name == "codeapu_validate_apu":
            rows, warnings = validate_rows(args.get("analysisRows"), str(args.get("partidaSourceCode") or ""), bool(args.get("requireCompleteCoding")), bool(args.get("requirePolhemCoding")))
            return {"valid": True, "normalizedRows": rows, "warnings": warnings, "estimatedDirectTotal": round(sum(row["quantity"] * row.get("factor", 1) * row["unitPrice"] for row in rows))}
        if name == "codeapu_get_normalization_scope":
            project_id = str(args.get("projectId") or "")
            project_file = self.store.load_project(user_id, project_id)
            require_polhem = bool(str((project_file.get("project") or {}).get("polhemAnalysisStatus") or "").strip())
            requested_itemized = str(args.get("itemizedId") or "")
            findings = []
            for itemized in project_file.get("itemizados", []):
                if requested_itemized and str(itemized.get("id") or "") != requested_itemized:
                    continue
                analyses = itemized.get("analyses") or {}
                concepts = {str(item.get("code") or ""): item for item in (itemized.get("data") or {}).get("items", [])}
                for concept_code, analysis_rows in analyses.items():
                    concept = concepts.get(str(concept_code), {})
                    partida = str(concept.get("originalCode") or concept.get("code") or concept_code)
                    missing = set()
                    for row in analysis_rows or []:
                        required_fields = ["prestoCode", "resourceType", "resourceFamilyCode", "dependency", "destinationCode", "subdestinationCode", "partidaSourceCode", "relationCorrelative", "codeapuCode", "classificationStatus", "technicalBasis", "priceStatus"]
                        if require_polhem:
                            required_fields.extend(["polhemProjectCode", "polhemZoneCode", "polhemSystemCode", "polhemEntityCode", "polhemPartidaCode", "polhemPrestoCode", "polhemCodingStatus"])
                        for field in required_fields:
                            if not str(row.get(field) or "").strip():
                                missing.add(field)
                    findings.append({"itemizedId": itemized.get("id"), "conceptCode": concept_code, "partidaSourceCode": partida, "description": concept.get("description", ""), "resourceCount": len(analysis_rows or []), "analysisHash": digest(analysis_rows or []), "ready": bool(analysis_rows) and not missing, "missingFields": sorted(missing)})
            ready = sum(1 for item in findings if item["ready"])
            return {"projectId": project_id, "apuCount": len(findings), "readyCount": ready, "pendingCount": len(findings)-ready, "findings": findings}
        if name == "codeapu_get_project_summary":
            project_id = str(args.get("projectId") or "")
            project_file = self.store.load_project(user_id, project_id)
            return {
                "meta": self.store.get_project_meta(user_id, project_id),
                "project": project_file.get("project", {}),
                "itemized": [
                    {"id": item.get("id"), "name": (item.get("data") or {}).get("sourceName", ""), "conceptCount": len((item.get("data") or {}).get("items", [])), "apuCount": len(item.get("analyses", {}))}
                    for item in project_file.get("itemizados", [])
                ],
            }
        if name == "codeapu_search_concepts":
            project_id = str(args.get("projectId") or "")
            itemized_id = str(args.get("itemizedId") or "")
            query = str(args.get("query") or "").strip().casefold()
            if not query:
                raise ValueError("query debe contener un código o texto a buscar.")
            try:
                limit = int(args.get("limit", 25))
            except (TypeError, ValueError) as exc:
                raise ValueError("limit debe ser un número entero.") from exc
            limit = max(1, min(100, limit))
            project_file = self.store.load_project(user_id, project_id)
            itemized = next((entry for entry in project_file.get("itemizados", []) if str(entry.get("id")) == itemized_id), None)
            if not itemized:
                raise ValueError("Itemizado no encontrado dentro del proyecto.")
            matches = []
            for item in (itemized.get("data") or {}).get("items", []):
                code = str(item.get("code") or "")
                original_code = str(item.get("originalCode") or "")
                description = str(item.get("description") or "")
                if query not in f"{code} {original_code} {description}".casefold():
                    continue
                matches.append({
                    "code": code,
                    "originalCode": original_code,
                    "description": description,
                    "unit": str(item.get("unit") or ""),
                    "quantity": item.get("quantity"),
                    "price": item.get("price"),
                    "isPartida": bool(item.get("isPartida", str(item.get("unit") or "").strip())),
                    "parentCode": str(item.get("parentCode") or ""),
                    "level": item.get("level"),
                })
                if len(matches) >= limit:
                    break
            return {"query": str(args.get("query") or "").strip(), "matches": matches, "returned": len(matches), "limit": limit}
        if name == "codeapu_get_apu":
            project_file, itemized, code = self._locate(user_id, args)
            rows = itemized.get("analyses", {}).get(code, [])
            concept = next((item for item in (itemized.get("data") or {}).get("items", []) if str(item.get("code")) == code), None)
            return {"concept": concept or {"code": code}, "analysisRows": rows, "analysisHash": digest(rows), **effective_apu_snapshot(itemized, code, concept, rows)}
        if name == "codeapu_get_partida_context":
            project_file, itemized, code = self._locate(user_id, args)
            rows = itemized.get("analyses", {}).get(code, [])
            concept = next((item for item in (itemized.get("data") or {}).get("items", []) if str(item.get("code")) == code), None)
            enrichment = (itemized.get("enrichment") or {}).get(code, {})
            return {
                "concept": concept or {"code": code},
                "analysisRows": rows,
                "analysisHash": digest(rows),
                "inspector": enrichment,
                "allowedInspectorFields": list(INSPECTOR_LIMITS),
                "sourcePolicy": "Usar exclusivamente EETT, planificación y antecedentes del proyecto; solicitar información si falta evidencia.",
                **effective_apu_snapshot(itemized, code, concept, rows),
            }
        if name == "codeapu_propose_apu":
            project_file, itemized, code = self._locate(user_id, args)
            before = itemized.get("analyses", {}).get(code, [])
            concept = next((entry for entry in (itemized.get("data") or {}).get("items", []) if str(entry.get("code")) == code), None)
            if not concept:
                raise ValueError("La partida no existe en el itemizado.")
            rows, warnings = validate_rows(
                args.get("analysisRows"),
                str(concept.get("originalCode") or concept.get("code") or code),
                bool(args.get("normalizationMode")),
                bool(args.get("requirePolhemCoding")),
            )
            inspector = validate_inspector(args.get("inspector", (itemized.get("enrichment") or {}).get(code, {})))
            before_inspector = (itemized.get("enrichment") or {}).get(code, {})
            preserve_official_price = bool(args.get("preserveOfficialPrice"))
            if preserve_official_price and not is_cost_neutral_recode(before, rows):
                raise ValueError("preserveOfficialPrice solo admite cambiar códigos manteniendo naturaleza, orden, descripción, unidad, rendimiento y precio.")
            proposal = {
                "kind": "replace_apu",
                "projectId": str(args["projectId"]),
                "itemizedId": str(args["itemizedId"]),
                "conceptCode": code,
                "reason": str(args.get("reason") or "")[:1000],
                "beforeHash": digest(before),
                "beforeRows": before,
                "analysisRows": rows,
                "beforeQuantity": number(concept.get("quantity", 0), "Cantidad vigente"),
                "beforeInspectorHash": digest(before_inspector),
                "inspector": inspector,
                "warnings": warnings,
                "preserveOfficialPrice": preserve_official_price,
                "normalizationMode": bool(args.get("normalizationMode")),
            }
            if "quantity" in args:
                proposal["quantity"] = number(args.get("quantity"), "quantity")
            if "description" in args:
                description = str(args.get("description") or "").strip()
                if not description:
                    raise ValueError("description no puede quedar vacía.")
                proposal["beforeDescription"] = str(concept.get("description") or "")
                proposal["description"] = description[:500]
            proposal_hash = digest(proposal)
            saved = self.store.save_mcp_proposal(user_id, proposal["projectId"], proposal, proposal_hash)
            return {"proposal": saved, "summary": {"conceptCode": code, "previousRows": len(before), "proposedRows": len(rows), "warnings": warnings}, "nextStep": "Abre CodeAPU > Codex, revisa los cambios y aprueba exactamente este hash."}
        if name == "codeapu_apply_approved_proposal":
            proposal_id = str(args.get("proposalId") or "")
            proposal_hash = str(args.get("proposalHash") or "")
            proposal = self.store.get_mcp_proposal(user_id, proposal_id)
            if proposal["status"] != "approved" or proposal["hash"] != proposal_hash:
                raise PermissionError("La propuesta no fue aprobada en CodeAPU o el hash no coincide.")
            return self.store.apply_mcp_analysis(user_id, proposal_id)
        if name == "codeapu_supersede_stale_proposals":
            return self.store.supersede_stale_mcp_proposals(user_id, str(args.get("projectId") or ""))
        return self.store.apply_mcp_authorized_bundle(
            user_id,
            args.get("proposals"),
            str(args.get("authorization") or ""),
        )

    def _locate(self, user_id: int, args: dict) -> tuple[dict, dict, str]:
        project_id = str(args.get("projectId") or "")
        itemized_id = str(args.get("itemizedId") or "")
        code = str(args.get("conceptCode") or "").strip()
        project_file = self.store.load_project(user_id, project_id)
        itemized = next((item for item in project_file.get("itemizados", []) if str(item.get("id")) == itemized_id), None)
        if not itemized:
            raise ValueError("Itemizado no encontrado dentro del proyecto.")
        concepts = (itemized.get("data") or {}).get("items", [])
        is_partida = any(str(item.get("code")) == code and str(item.get("unit") or "").strip() for item in concepts)
        is_subanalysis = code in (itemized.get("analyses") or {}) and any(
            str(row.get("code") or "").strip().upper() == code.upper() and bool(row.get("isSubanalysis"))
            for rows in (itemized.get("analyses") or {}).values() for row in rows
        )
        if not is_partida and not is_subanalysis:
            raise ValueError("La partida no existe o no tiene unidad.")
        return project_file, itemized, code


def success(request_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def failure(request_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def tool_result(payload: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}], "structuredContent": payload, "isError": False}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    server = CodeApuMcp()
    for raw_line in sys.stdin.buffer:
        try:
            request = json.loads(raw_line.decode("utf-8"))
            request_id, method = request.get("id"), request.get("method")
            if request_id is None:
                continue
            if method == "initialize":
                response = success(request_id, {"protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "CodeAPU MCP", "version": SERVER_VERSION}, "instructions": INSTRUCTIONS})
            elif method == "tools/list":
                response = success(request_id, {"tools": server.tools()})
            elif method == "tools/call":
                params = request.get("params") or {}
                response = success(request_id, tool_result(server.call(str(params.get("name") or ""), params.get("arguments") or {})))
            elif method == "ping":
                response = success(request_id, {})
            else:
                response = failure(request_id, -32601, "Método MCP no implementado.")
        except Exception as exc:
            request_id = locals().get("request_id")
            if locals().get("method") == "tools/call":
                response = success(request_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
            else:
                response = failure(request_id, -32603, str(exc))
        sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

