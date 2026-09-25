"""Construye el catálogo maestro de recursos CodeAPU desde todos los proyectos locales.

El proceso es de solo lectura respecto de SQLite. La identidad técnica excluye el
precio y el contexto de uso; ambos se conservan en priceHistory y usages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


CATALOG_SCHEMA = "CodeAPU-RESOURCE-CATALOG-1"
CODING_VERSION = 11
VALID_TYPES = {"M", "O", "E", "S"}
UNIT_ALIASES = {"U": "UN", "UND": "UN", "UNID": "UN", "M": "ML", "L": "LT", "H": "HM", "HR": "HM"}
DESTINATION_DEFAULT_SUBDESTINATION = {
    "ESSA": "SA", "ESEL": "EL", "ESCL": "CL", "ESGC": "GC",
    "ESOE": "OE", "ESPJ": "PJ", "ESTV": "TV", "ESSV": "OE",
}
FAMILY_LABELS = {
    "MHO": "Materiales · hormigón", "MTO": "Materiales · topografía",
    "MCJ": "Materiales · cubrejuntas", "MCV": "Materiales · canaleta vehicular",
    "MCS": "Materiales · cortina separadora", "MGM": "Materiales · guardamuros y protecciones",
    "MVE": "Materiales · ventanas, muros cortina y espejos", "MEM": "Materiales · estructuras metálicas",
    "MAR": "Materiales · áridos", "MPE": "Materiales · pavimentos exteriores no SERVIU",
    "MCP": "Materiales · cierros perimetrales", "MAO": "Materiales · aseo de obra",
    "MCAP": "CAP · Capacitación", "MSRV": "SRV · SERVIU", "MUI": "Materiales · muebles interiores",
    "MOE": "Materiales · mobiliario urbano", "MSÑ": "Materiales · señalética",
    "MTV": "Materiales · transporte vertical", "OTV": "Mano de obra · transporte vertical",
    "ETV": "Equipos · transporte vertical", "MPCI": "Materiales · protección contra incendio",
    "OPCI": "Mano de obra · protección contra incendio", "EPCI": "Equipos · protección contra incendio",
    "MREAS": "Materiales · residuos sólidos",
    "MSA": "Materiales · instalaciones sanitarias", "OSA": "Mano de obra · instalaciones sanitarias",
    "ESA": "Equipos · instalaciones sanitarias", "MSEA": "Materiales · estanque de agua potable",
    "OSEA": "Mano de obra · estanque de agua potable", "ESEA": "Equipos · estanque de agua potable",
    "MEL": "Materiales · instalaciones eléctricas", "OEL": "Mano de obra · instalaciones eléctricas",
    "EEL": "Equipos · instalaciones eléctricas", "MGEN": "Materiales · grupo electrógeno",
    "OGEN": "Mano de obra · grupo electrógeno", "EGEN": "Equipos · grupo electrógeno",
    "MCD": "Materiales · corrientes débiles", "OCD": "Mano de obra · corrientes débiles",
    "ECD": "Equipos · corrientes débiles",
    "MCL": "Materiales · climatización y ventilación", "OCL": "Mano de obra · climatización y ventilación",
    "ECL": "Equipos · climatización y ventilación",
    "MSE": "Materiales · señalética (familia histórica)",
    "MBA": "Materiales · baldosas", "MCC": "Materiales · cañerías de cobre",
    "MCA": "Materiales · cañerías", "MPJ": "Materiales · paisajismo", "MRI": "Materiales · riego",
    "MTA": "Materiales · tabiques", "MIM": "Materiales · impermeabilización",
    "MPI": "Materiales · pintura", "MEN": "Materiales · enfierradura",
    "MMD": "Materiales · moldajes", "MPU": "Materiales · puertas",
    "MPV": "Materiales · pavimentos", "MRE": "Materiales · revestimientos",
    "MGE": "Materiales · general pendiente de clasificación",
}
PREFERRED_MASTER_CODES = {
    ("MHO", "HORMIGON POBRE", "M3"): "MHO01",
    ("MHO", "HORMIGON G05", "M3"): "MHO02",
    ("MHO", "HORMIGON H05", "M3"): "MHO03",
}


def plain_text(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", text.upper()).strip()


def canonical_unit(value: object) -> str:
    unit = re.sub(r"[^A-Z0-9%]+", "", plain_text(value))
    return UNIT_ALIASES.get(unit, unit or "UN")


def canonical_identity_text(value: object) -> str:
    """Normaliza sólo equivalencias seguras; no interpreta el contexto del APU."""
    text = plain_text(value).replace("�", "")
    text = re.sub(r"^(SUMINISTRO|SUM\.?)(?:\s*[·:\-–—]+)?\s*", "", text)
    text = re.sub(r"^SERVICIO EXTERNO(?:\s*[·:\-–—]+)?\s*", "", text)
    text = re.sub(r"\b([GH])\s*[- ]?0?(\d{1,2})\b", lambda m: f"{m.group(1)}{int(m.group(2)):02d}", text)
    text = re.sub(r"\bHORMIGON\s+PREMEZCLADO\b", "HORMIGON", text)
    text = re.sub(r"[^A-Z0-9%]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def ambiguous_identity_text(value: str) -> bool:
    ignored = {"DE", "DEL", "LA", "EL", "Y", "PARA", "SUM", "SUMINISTRO", "SERVICIO", "EXTERNO", "TU", "VARIOS", "ACCESORIOS", "INSUMOS", "MENORES"}
    words = [token for token in value.split() if re.search(r"[A-Z]", token) and token not in ignored]
    return not words


MATERIAL_DIRECT_RULES = (
    ("MREAS", r"RESIDUOS? SOLIDOS?|RESIDUOS? PELIGROSOS?"),
    ("MTO", r"TABLA.*CERQUILLO|ESTACA.*CERQUILLO|LIENZA.*TRAZADO|TIZA.*TRAZADO|AGUA PARA COMPACTACION"),
    ("MCJ", r"CUBREJUNTA"),
    ("MCV", r"CANALETA.*(VEHICULAR|ACCESO)|REJILLA.*VEHICULAR"),
    ("MCS", r"CORTINA SEPARADORA|SISTEMA DE RIELES Y CORTINAS|CORTINAS? ACERO INOXIDABLE"),
    ("MGM", r"GUARDAMURO|CANTONERA|MALLAS? DE PROTECCION"),
    ("MVE", r"VENTANA|MURO CORTINA|ESPEJO|FILM TRASLUCIDO|FILM EMPAVONADO"),
    ("MPE", r"PASILLO.*PEATONAL"),
    ("MEM", r"ESTRUCTURAS? METALICAS?|MARCOS? DE (ACERO|ALUMINIO)|PLATAFORMA.*EQUIPO|GATERA|BARANDA|PASAMANO|TAPA METALICA|MARQUESINA"),
    ("MAR", r"ARIDOS?|ARENA|GRAVILLA|RIPIO|ESTABILIZAD|BASE Y SUB[- ]BASE|SUB[- ]RASANTE"),
    ("MCT", r"CONTENEDOR|MODULAR"), ("MBA", r"BALDOSA"),
    ("MCC", r"CA.?ERIA.*(?:CU|COBRE)|TUBERIA.*COBRE"), ("MCA", r"CA.?ERIA|TUBERIA"),
    ("MPJ", r"CRESP|ARBOL|ARBUST|PLANTA|PASTO|CESPED|TIERRA VEGETAL|FERTILIZ"),
    ("MRI", r"RIEGO|ASPERSOR|GOTEO"),
    ("MTA", r"TABIQU|VOLCOMETAL|VOLCANITA|YESO CARTON|MONTANTE GALVANIZADO|CANAL GALVANIZADO"),
    ("MIM", r"IMPERMEABILIZACION|IMPERMEABILIZANTE|MEMBRANA ASFALT"),
    ("MEN", r"ENFIERR|FIERRO|ACERO.*REFUERZO|ARMADURA|MALLA ELECTROSOLDADA"),
    ("MPI", r"PINTURA|ESMALTE|(?:^| )OLEO(?: |$)"),
    ("MHO", r"^(?:(?:SUMINISTRO|SUM\.?)\s*[·:\-–—]*\s*)?(?:HORMIGON|CONCRETO|MORTERO)(?:\s|$)"),
    ("MMD", r"MOLDAJE|ENCOFRADO"), ("MPU", r"(?:^| )PUERTA"),
    ("MPV", r"PAVIMENT|ADOQUIN|SOLERA"), ("MRE", r"REVEST|CERAMIC|PORCELANATO"),
    ("MSÑ", r"SENALETICA|SENALIZACION"), ("MTV", r"ASCENSOR|MONTACARGA|TRANSPORTE VERTICAL"),
    ("MPCI", r"EXTINTOR|GABINETE.*EXTINTOR|PROTECCION CONTRA INCENDIO"),
    ("MUI", r"MUEBLE|MESON|LOCKER|ESTANTE|REPISA"),
    ("MOE", r"ESCANO|BICICLETERO|ASTA DE BANDERA"),
    ("MCP", r"CIERRO|CERRAMIENTO|PANDERETA|BULLDOG|REJA|MURETE"),
    ("MAO", r"ASEO (DE )?(LA )?OBRA|ASEO FINAL"), ("MCAP", r"CAPACITACION"),
)


def infer_resource_family(resource_type: str, description: str, hierarchy: str = "", destination: str = "", subdestination: str = "GE") -> str:
    resource_type = (resource_type or "").upper()[:1]
    resource = plain_text(description)
    context = plain_text(hierarchy)
    destination = (destination or "").upper()
    subdestination = (subdestination or DESTINATION_DEFAULT_SUBDESTINATION.get(destination) or "GE").upper()
    tank_context = bool(re.search(r"ESTANQUE DE AGUA(?: POTABLE)?|SALA DE MAQUINAS.*ESTANQUE", context))
    sanitary_context = bool(re.search(r"INSTALACIONES? SANITARIAS?|AGUA POTABLE|AGUA CALIENTE|ALCANTARILLADO|AGUAS LLUVIAS|RED HUMEDA", context))
    earth_context = bool(re.search(r"MOVIMIENTO DE TIERRA|EXCAVACION|RELLENO|RETIRO DE MATERIAL|CAMA DE ARENA|GRAVA|ESTABILIZADO", context))
    generator_context = bool(re.search(r"GRUPO ELECTROGENO|GENERADOR DIESEL|SISTEMA DE RESPALDO DE ENERGIA", context))
    weak_current_context = bool(re.search(r"CORRIENTES? DEBILES?", context))
    climate_context = destination == "ESCL" or bool(re.search(r"INSTALACIONES? (?:DE )?CLIMATIZACION Y VENTILACION", context))
    electrical_context = destination == "ESEL" or bool(re.search(
        r"INSTALACIONES? ELECTRICAS?|EMPLAZAMIENTO ELECTRICO|ALIMENTADORES? ELECTRICOS?|"
        r"CANALIZACIONES? (?:ELECTRICAS?|SUBTERRANEAS?)|CIRCUITOS? ELECTRICOS?|TABLEROS? ELECTRICOS?|"
        r"ARTEFACTOS? ELECTRICOS?|MALLA (?:DE )?PUESTA A TIERRA|CORRIENTES? DEBILES?|ARRANQUES? ELECTRICOS?",
        context,
    ))
    if resource_type == "M":
        if tank_context:
            return "MSEA"
        if generator_context:
            return "MGEN"
        if climate_context:
            return "MCL"
        if weak_current_context:
            return "MCD"
        if electrical_context and not earth_context:
            return "MEL"
        if sanitary_context and not earth_context:
            return "MSA"
        for family, pattern in MATERIAL_DIRECT_RULES:
            if re.search(pattern, resource):
                return family
        context_rules = (
            ("MOE", r"MOBILIARIO URBANO"), ("MSÑ", r"SENALETICA|SENALIZACION"),
            ("MTV", r"ASCENSOR|MONTACARGA|TRANSPORTE VERTICAL"),
            ("MUI", r"MUEBLES? INCORPORADOS|MUEBLES? ADOSADOS|MOBILIARIO INTERIOR"),
            ("MCP", r"CIERROS? (PERIMETRALES?|EXTERIORES?)|CERRAMIENTO PERIMETRAL"),
            ("MTO", r"REPLANTEO|TRAZADO Y NIVELES|ESTABILIZADO DE RIPIO"),
            ("MAO", r"ASEO (Y ORDEN )?(PERMANENTE|FINAL)|ASEO DE (LA )?OBRA"),
            ("MCAP", r"CAPACITACION"),
        )
        for family, pattern in context_rules:
            if re.search(pattern, context):
                return family
        if destination == "ESTV":
            return "MTV"
        if destination == "ESSV":
            return "MSRV"
        if destination != "ESSV" and re.search(r"PAVIMENTACION|PAVIMENTOS? EXTERIORES?|CALZADAS?|VEREDAS?", context):
            return "MPE"
        if destination == "ESPJ":
            return "MPJ"
        return "MGE"
    if resource_type == "E":
        if tank_context:
            return "ESEA"
        if generator_context:
            return "EGEN"
        if climate_context:
            return "ECL"
        if weak_current_context:
            return "ECD"
        if electrical_context and not earth_context:
            return "EEL"
        if sanitary_context and not earth_context:
            return "ESA"
        if re.search(r"EXTINTOR|PROTECCION CONTRA INCENDIO", resource):
            return "EPCI"
        if destination == "ESTV":
            return "ETV"
        for family, pattern in (("EEX", r"EXCAVADORA|RETROEXCAV|MINICARGADOR"), ("EGR", r"GRUA|PLUMA"), ("ECA", r"CAMION|TOLVA"), ("EHM", r"HERRAMIENTA|EQUIPO MENOR")):
            if re.search(pattern, resource):
                return family
        return f"E{subdestination}"
    if resource_type == "O":
        if tank_context:
            return "OSEA"
        if generator_context:
            return "OGEN"
        if climate_context:
            return "OCL"
        if weak_current_context:
            return "OCD"
        if electrical_context and not earth_context:
            return "OEL"
        if sanitary_context and not earth_context:
            return "OSA"
        if re.search(r"EXTINTOR|PROTECCION CONTRA INCENDIO", resource):
            return "OPCI"
        if destination == "ESTV":
            return "OTV"
        for family, pattern in (("OJO", r"JORNAL"), ("OAY", r"AYUDANTE"), ("OPR", r"PROFESIONAL|INGENIERO|ARQUITECTO"), ("OMA", r"MAESTRO")):
            if re.search(pattern, resource):
                return family
        return f"O{subdestination}"
    return f"S{subdestination}"


def _hierarchy_text(items_by_code: dict[str, dict], code: str) -> str:
    current = items_by_code.get(code) or {}
    chain = []
    guard = 0
    while current.get("parentCode") and guard < 20:
        parent = items_by_code.get(current["parentCode"])
        if not parent:
            break
        chain.insert(0, f"{parent.get('originalCode') or parent.get('code', '')} {parent.get('description', '')}")
        current = parent
        guard += 1
    item = items_by_code.get(code) or {}
    chain.append(f"{item.get('originalCode') or code} {item.get('description', '')}")
    return " / ".join(chain)


def _resource_type(row: dict) -> str:
    explicit = str(row.get("resourceType") or "").upper()[:1]
    if explicit in VALID_TYPES:
        return explicit
    for field in ("prestoCode", "code", "legacyPrestoCode"):
        candidate = str(row.get(field) or "").upper()[:1]
        if candidate in VALID_TYPES:
            return candidate
    return "S"


def collect_occurrences(connection: sqlite3.Connection) -> tuple[list[dict], list[dict]]:
    projects, occurrences = [], []
    for project_id, project_name, project_code, updated_at, raw in connection.execute(
        "SELECT id, name, code, updated_at, project_data FROM projects ORDER BY created_at, id"
    ):
        data = json.loads(raw)
        currency = (data.get("project") or {}).get("currency") or "CLP"
        project_entry = {"projectId": project_id, "projectCode": project_code, "projectName": project_name, "updatedAt": updated_at}
        projects.append(project_entry)
        for itemized in data.get("itemizados") or []:
            itemized_id = itemized.get("id") or ""
            items = (itemized.get("data") or {}).get("items") or []
            items_by_code = {str(item.get("code") or ""): item for item in items}
            for analysis_code, rows in (itemized.get("analyses") or {}).items():
                item = items_by_code.get(str(analysis_code)) or {}
                hierarchy = _hierarchy_text(items_by_code, str(analysis_code))
                for index, row in enumerate(rows or []):
                    resource_type = _resource_type(row)
                    current_code = str(row.get("prestoCode") or row.get("code") or "").strip().upper()
                    legacy_code = str(row.get("legacyPrestoCode") or row.get("code") or current_code).strip().upper()
                    auxiliary = bool(re.fullmatch(r"[MOE]%AUX", current_code or legacy_code))
                    destination = str(row.get("destinationCode") or "").strip().upper()
                    subdestination = str(row.get("subdestinationCode") or DESTINATION_DEFAULT_SUBDESTINATION.get(destination) or "GE").strip().upper()
                    confirmed = bool(row.get("familyClassificationConfirmed"))
                    stored_family = str(row.get("resourceFamilyCode") or "").strip().upper()
                    family = stored_family if confirmed and stored_family else infer_resource_family(resource_type, row.get("description") or "", hierarchy, destination, subdestination)
                    description = str(row.get("description") or "").strip()
                    normalized_description = current_code if auxiliary else canonical_identity_text(description)
                    identity_text = normalized_description
                    unit = canonical_unit(row.get("unit"))
                    ambiguous_identity = not auxiliary and ambiguous_identity_text(identity_text)
                    if row.get("isSubanalysis"):
                        identity_text = f"SUBANALYSIS {project_id} {legacy_code} {identity_text}"
                    elif ambiguous_identity:
                        identity_text = f"AMBIGUOUS {project_id} {legacy_code} {identity_text}"
                    identity_material = f"{resource_type}|{identity_text}|{unit}"
                    identity_hash = hashlib.sha256(identity_material.encode("utf-8")).hexdigest()
                    occurrences.append({
                        "identityHash": identity_hash, "resourceType": resource_type, "description": description,
                        "normalizedDescription": normalized_description, "unit": unit, "observedUnit": str(row.get("unit") or "").strip().upper(),
                        "inferredFamilyCode": family, "storedFamilyCode": stored_family, "familyConfirmed": confirmed,
                        "currentPrestoCode": current_code, "legacyPrestoCode": legacy_code, "isAuxiliary": auxiliary,
                        "ambiguousIdentity": ambiguous_identity,
                        "isSubanalysis": bool(row.get("isSubanalysis")), "projectId": project_id, "projectCode": project_code,
                        "projectName": project_name, "projectUpdatedAt": updated_at, "currency": currency,
                        "itemizedId": itemized_id, "analysisCode": str(analysis_code),
                        "partidaCode": str(item.get("originalCode") or item.get("code") or analysis_code),
                        "partidaDescription": str(item.get("description") or ""), "hierarchy": hierarchy,
                        "relationId": str(row.get("relationId") or f"{project_id}:{itemized_id}:{analysis_code}:{index}"),
                        "codeapuCode": str(row.get("codeapuCode") or ""), "destinationCode": destination,
                        "subdestinationCode": subdestination, "dependency": str(row.get("dependency") or ""),
                        "quantity": float(row.get("quantity") or 0), "factor": float(row.get("factor") if row.get("factor") is not None else 1),
                        "unitPrice": float(row.get("unitPrice") or 0), "priceStatus": str(row.get("priceStatus") or ""),
                        "resourceSource": str(row.get("resourceSource") or ""), "technicalBasis": str(row.get("technicalBasis") or ""),
                        "classificationStatus": str(row.get("classificationStatus") or "inferido"),
                    })
    return projects, occurrences


def build_catalog(projects: list[dict], occurrences: list[dict], existing_catalog: dict | None = None) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for occurrence in occurrences:
        grouped[occurrence["identityHash"]].append(occurrence)

    current_code_owners: dict[str, set[str]] = defaultdict(set)
    for identity_hash, rows in grouped.items():
        for code in {row["currentPrestoCode"] for row in rows if row["currentPrestoCode"]}:
            current_code_owners[code].add(identity_hash)

    drafts = []
    for identity_hash, rows in grouped.items():
        family_counts = Counter(row["inferredFamilyCode"] for row in rows if row["inferredFamilyCode"])
        family = family_counts.most_common(1)[0][0] if family_counts else f"{rows[0]['resourceType']}GE"
        alias_counts = Counter(row["description"] for row in rows if row["description"])
        display_name = sorted(alias_counts, key=lambda value: (bool(re.match(r"^(SUMINISTRO|SUM\.)", plain_text(value))), len(value), value))[0] if alias_counts else rows[0]["normalizedDescription"]
        code_counts = Counter(row["currentPrestoCode"] for row in rows if row["currentPrestoCode"])
        confirmed_code_counts = Counter(row["currentPrestoCode"] for row in rows if row["currentPrestoCode"] and row["familyConfirmed"])
        safe_candidates = [
            code for code, _ in confirmed_code_counts.most_common()
            if len(current_code_owners[code]) == 1 and re.fullmatch(re.escape(family) + r"\d+", code) and len(code) <= 13
        ]
        drafts.append({"identityHash": identity_hash, "rows": rows, "family": family, "familyCounts": family_counts, "aliasCounts": alias_counts, "displayName": display_name, "codeCounts": code_counts, "candidate": safe_candidates[0] if safe_candidates else ""})

    existing_resources = (existing_catalog or {}).get("resources") or []
    existing_by_id = {row.get("catalogId"): row for row in existing_resources if row.get("catalogId") and row.get("prestoCode")}
    used_codes = {row["prestoCode"] for row in existing_resources if row.get("prestoCode")}
    reserved_codes = set(PREFERRED_MASTER_CODES.values())
    for draft in sorted(drafts, key=lambda value: (value["family"], value["displayName"], value["identityHash"])):
        catalog_id = f"res-{draft['identityHash'][:20]}"
        previous = existing_by_id.get(catalog_id)
        if previous:
            draft["catalogCode"] = previous["prestoCode"]
            draft["codeStatus"] = "preserved_existing_catalog"
            continue
        candidate = draft["candidate"]
        if candidate and candidate not in used_codes:
            draft["catalogCode"] = candidate
            draft["codeStatus"] = "reused_unique"
            used_codes.add(candidate)
    next_sequence = defaultdict(lambda: 1)
    for draft in sorted(drafts, key=lambda value: (value["family"], value["displayName"], value["identityHash"])):
        if draft.get("catalogCode"):
            continue
        family = draft["family"]
        preferred = PREFERRED_MASTER_CODES.get((family, draft["rows"][0]["normalizedDescription"], draft["rows"][0]["unit"]))
        if preferred and preferred not in used_codes:
            draft["catalogCode"] = preferred
            draft["codeStatus"] = "assigned_preferred_catalog_seed"
            used_codes.add(preferred)
            continue
        while True:
            sequence = next_sequence[family]
            next_sequence[family] += 1
            code = f"{family}{sequence:02d}"
            if code not in used_codes and code not in reserved_codes and len(code) <= 13:
                break
        draft["catalogCode"] = code
        draft["codeStatus"] = "assigned_initial_catalog"
        used_codes.add(code)

    resources = []
    issue_counts = Counter()
    for draft in drafts:
        rows = draft["rows"]
        price_groups: dict[tuple, int] = Counter()
        for row in rows:
            key = (row["projectId"], row["itemizedId"], row["unitPrice"], row["currency"], row["priceStatus"], row["resourceSource"], row["projectUpdatedAt"])
            price_groups[key] += 1
        price_history = [
            {"projectId": key[0], "itemizedId": key[1], "unitPrice": key[2], "currency": key[3], "priceStatus": key[4], "source": key[5], "observedAt": key[6], "usageCount": count}
            for key, count in sorted(price_groups.items(), key=lambda item: (item[0][0], item[0][2], item[0][6]))
        ]
        prices_by_project: dict[str, set[float]] = defaultdict(set)
        for row in rows:
            prices_by_project[row["projectId"]].add(row["unitPrice"])
        issues = []
        if len(draft["familyCounts"]) > 1:
            issues.append("MULTIPLE_INFERRED_FAMILIES")
        if len(draft["codeCounts"]) > 1:
            issues.append("MULTIPLE_CURRENT_PRESTO_CODES")
        if any(len(prices) > 1 for prices in prices_by_project.values()):
            issues.append("PRICE_VARIATION_WITHIN_PROJECT")
        if draft["family"].endswith("GE"):
            issues.append("GENERAL_FAMILY_REQUIRES_REVIEW")
        if any(row.get("ambiguousIdentity") for row in rows):
            issues.append("AMBIGUOUS_TECHNICAL_IDENTITY")
        if any("�" in row["description"] or "�" in row["projectName"] for row in rows):
            issues.append("SOURCE_TEXT_ENCODING_REPLACEMENT")
        for issue in issues:
            issue_counts[issue] += 1
        resources.append({
            "catalogId": f"res-{draft['identityHash'][:20]}", "prestoCode": draft["catalogCode"],
            "codeStatus": draft["codeStatus"], "resourceType": rows[0]["resourceType"],
            "resourceFamilyCode": draft["family"], "familyLabel": FAMILY_LABELS.get(draft["family"], draft["family"]),
            "canonicalDescription": draft["displayName"], "normalizedDescription": rows[0]["normalizedDescription"],
            "unit": rows[0]["unit"], "aliases": [{"description": alias, "count": count} for alias, count in draft["aliasCounts"].most_common()],
            "observedUnits": sorted({row["observedUnit"] for row in rows}),
            "currentPrestoCodes": [{"code": code, "count": count} for code, count in draft["codeCounts"].most_common()],
            "legacyPrestoCodes": sorted({row["legacyPrestoCode"] for row in rows if row["legacyPrestoCode"]}),
            "projects": sorted({row["projectId"] for row in rows}), "usageCount": len(rows),
            "priceHistory": price_history,
            "usages": [{key: row[key] for key in ("projectId", "itemizedId", "relationId", "analysisCode", "partidaCode", "partidaDescription", "codeapuCode", "destinationCode", "subdestinationCode", "dependency", "quantity", "factor", "unitPrice", "currency", "priceStatus", "resourceSource", "technicalBasis", "classificationStatus")} for row in rows],
            "issues": issues, "reviewStatus": "requires_review" if issues else "catalog_candidate", "active": True,
        })

    active_ids = {row["catalogId"] for row in resources}
    for previous in existing_resources:
        if previous.get("catalogId") in active_ids:
            continue
        retired = dict(previous)
        retired["active"] = False
        retired["reviewStatus"] = "historical_not_present_in_current_projects"
        retired["issues"] = sorted(set((retired.get("issues") or []) + ["SOURCE_NOT_PRESENT"]))
        resources.append(retired)
        issue_counts["SOURCE_NOT_PRESENT"] += 1

    type_order = {"M": 0, "O": 1, "E": 2, "S": 3}
    resources.sort(key=lambda row: (type_order.get(row["resourceType"], 9), row["resourceFamilyCode"], row["prestoCode"]))
    family_counts = Counter(row["resourceFamilyCode"] for row in resources)
    return {
        "schema": CATALOG_SCHEMA, "codingVersion": CODING_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "principles": {
            "masterIdentity": "resourceType + normalized technical description + canonical unit",
            "identityExcludes": ["price", "project", "destination", "subdestination", "partida"],
            "contextLivesIn": "usages[].codeapuCode/destinationCode/subdestinationCode/partidaCode",
            "priceLivesIn": "priceHistory and the adopted unitPrice of each usage",
        },
        "sourceProjects": projects,
        "diagnostics": {
            "projectCount": len(projects), "relationCount": len(occurrences), "resourceCount": len(resources),
            "familyCounts": dict(sorted(family_counts.items())), "issueCounts": dict(sorted(issue_counts.items())),
            "generalFamilyResourceCount": sum(1 for row in resources if row["resourceFamilyCode"].endswith("GE")),
        },
        "resources": resources,
    }


def generate_catalog(database: Path, output: Path, rebuild_codes: bool = False) -> dict:
    uri = f"file:{database.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        projects, occurrences = collect_occurrences(connection)
    existing_catalog = None
    if output.exists() and not rebuild_codes:
        try:
            candidate = json.loads(output.read_text(encoding="utf-8"))
            if candidate.get("schema") == CATALOG_SCHEMA:
                existing_catalog = candidate
        except (OSError, ValueError, TypeError):
            existing_catalog = None
    catalog = build_catalog(projects, occurrences, existing_catalog)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", delete=False, dir=output.parent, suffix=".tmp") as handle:
        json.dump(catalog, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, output)
    return catalog


def main() -> int:
    application_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Genera el catálogo maestro de recursos CodeAPU sin modificar proyectos.")
    parser.add_argument("--database", type=Path, default=application_dir.parent / "01. Proyectos" / "data" / "codeapu.db")
    parser.add_argument("--output", type=Path, default=application_dir.parent / "01. Proyectos" / "data" / "catalogo_recursos_codeapu.json")
    parser.add_argument("--rebuild-codes", action="store_true", help="Ignora códigos del catálogo anterior; úsese sólo para corregir una catalogación inicial no confirmada.")
    args = parser.parse_args()
    catalog = generate_catalog(args.database, args.output, rebuild_codes=args.rebuild_codes)
    print(json.dumps({"output": str(args.output.resolve()), **catalog["diagnostics"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

