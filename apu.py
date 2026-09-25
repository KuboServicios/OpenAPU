from __future__ import annotations

import re
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from converter import format_number, safe_bc3_text


NATURES = {
    "M": "Materiales",
    "O": "Mano de obra",
    "E": "Equipos y maquinaria",
    "S": "Subcontratos",
}

AUXILIAR_RATES = {"M%AUX": 0.05, "E%AUX": 0.05, "O%AUX": 0.35}
AUXILIAR_LABELS = {
    "M%AUX": "Merma materiales (5%)",
    "E%AUX": "Desgaste equipos (5%)",
    "O%AUX": "Leyes sociales (35%)",
}


def normalize_resource_code(value: object, max_length: int = 13) -> str:
    code = str(value or "").strip().upper().replace(" ", "")
    code = re.sub(r"[^A-Z0-9%._-]", "", code)
    if not code:
        raise ValueError("Cada recurso debe tener código.")
    if len(code) > max_length:
        raise ValueError(f"El código de recurso '{code}' supera los {max_length} caracteres admitidos.")
    return code


def nature_from_code(code: str) -> str:
    return NATURES.get(code[:1].upper(), "Subcontratos")


def as_number(value: object) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return number if number == number and abs(number) != float("inf") else 0.0


def cost_round(value: float) -> int:
    """Replica Math.round del cliente web para costos no negativos."""
    return math.floor(as_number(value) + 0.5)


@dataclass
class CalculatedRow:
    code: str
    description: str
    unit: str
    quantity: float
    factor: float
    effective_quantity: float
    unit_price: float
    total: float
    nature: str
    is_subanalysis: bool = False
    is_percentage: bool = False

    def json(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "description": self.description,
            "unit": self.unit,
            "quantity": self.quantity,
            "factor": self.factor,
            "effectiveQuantity": self.effective_quantity,
            "unitPrice": self.unit_price,
            "total": self.total,
            "nature": self.nature,
            "isSubanalysis": self.is_subanalysis,
            "isPercentage": self.is_percentage,
        }


class ApuCalculator:
    def __init__(self, analyses: dict[str, list[dict]], max_code_length: int = 13) -> None:
        self.analyses = {str(key).upper(): value for key, value in analyses.items() if isinstance(value, list)}
        self.max_code_length = max_code_length
        self.cache: dict[str, tuple[float, list[CalculatedRow]]] = {}

    def calculate(self, parent_code: str, stack: tuple[str, ...] = ()) -> tuple[float, list[CalculatedRow]]:
        parent_code = str(parent_code).upper()
        if parent_code in self.cache:
            return self.cache[parent_code]
        if parent_code in stack:
            raise ValueError(f"Subanálisis circular detectado: {' > '.join((*stack, parent_code))}.")
        raw_rows = self.analyses.get(parent_code, [])
        normal_rows: list[CalculatedRow] = []
        percentage_rows: list[tuple[dict, str]] = []
        for raw in raw_rows:
            internal_code = normalize_resource_code(raw.get("code"), self.max_code_length)
            if internal_code in AUXILIAR_RATES:
                percentage_rows.append((raw, internal_code))
                continue
            is_sub = bool(raw.get("isSubanalysis")) or internal_code in self.analyses
            code = internal_code if is_sub else normalize_resource_code(raw.get("prestoCode") or internal_code, self.max_code_length)
            if is_sub:
                unit_price, _ = self.calculate(internal_code, (*stack, parent_code))
            else:
                unit_price = as_number(raw.get("unitPrice"))
            unit_price = cost_round(unit_price)
            quantity = as_number(raw.get("quantity"))
            raw_factor = raw.get("factor")
            factor = 1.0 if raw_factor is None or str(raw_factor).strip() == "" else as_number(raw_factor)
            effective_quantity = quantity * factor
            total = cost_round(effective_quantity * unit_price)
            normal_rows.append(CalculatedRow(
                code=code,
                description=safe_bc3_text(raw.get("description")) or code,
                unit=safe_bc3_text(raw.get("unit")).upper(),
                quantity=quantity,
                factor=factor,
                effective_quantity=effective_quantity,
                unit_price=unit_price,
                total=total,
                nature=nature_from_code(code),
                is_subanalysis=is_sub,
            ))

        calculated = list(normal_rows)
        for raw, code in percentage_rows:
            prefix = code[0]
            base = cost_round(sum(row.total for row in normal_rows if row.code.startswith(prefix)))
            rate = AUXILIAR_RATES[code]
            calculated.append(CalculatedRow(
                code=code,
                description=safe_bc3_text(raw.get("description")) or AUXILIAR_LABELS[code],
                unit="%",
                quantity=rate,
                factor=1.0,
                effective_quantity=rate,
                unit_price=base,
                total=cost_round(base * rate),
                nature=NATURES[prefix],
                is_percentage=True,
            ))
        price = cost_round(sum(row.total for row in calculated))
        self.cache[parent_code] = (price, calculated)
        return price, calculated


def export_apu_bc3(payload: dict) -> tuple[bytes, dict]:
    project_name = safe_bc3_text(payload.get("projectName")) or "Presupuesto con APU"
    budget_items = payload.get("budgetItems")
    raw_project_roots = payload.get("projectRoots") or []
    analyses = payload.get("analyses") or {}
    source_format = str(payload.get("sourceFormat") or "").upper()
    dirty_analyses = {str(code).upper() for code, dirty in (payload.get("dirtyAnalyses") or {}).items() if dirty}
    if not isinstance(budget_items, list) or not budget_items:
        raise ValueError("No hay conceptos de presupuesto para exportar.")
    if not isinstance(analyses, dict):
        raise ValueError("La estructura de análisis no es válida.")
    polhem = payload.get("polhemAnalysis") or {}
    enforce_polhem = bool(payload.get("enforcePolhem"))
    if enforce_polhem and str(polhem.get("status") or "").strip().lower() != "confirmado":
        raise ValueError("El análisis POLHEM del proyecto debe estar confirmado antes de exportar a Presto.")
    if enforce_polhem and not re.fullmatch(r"[A-Z0-9]{2,12}", str(polhem.get("projectCode") or "").strip().upper()):
        raise ValueError("El código de proyecto POLHEM no es válido.")

    calculator = ApuCalculator(analyses)

    def analysis_tree_dirty(code: str, stack: tuple[str, ...] = ()) -> bool:
        code = str(code).upper()
        if code in dirty_analyses:
            return True
        if code in stack:
            return False
        return any(
            bool(row.get("isSubanalysis")) and analysis_tree_dirty(str(row.get("code") or ""), (*stack, code))
            for row in calculator.analyses.get(code, [])
        )
    project_roots: dict[str, dict] = {}
    project_order: list[str] = []
    if isinstance(raw_project_roots, list):
        for raw_root in raw_project_roots:
            code = normalize_resource_code(raw_root.get("code"))
            if code == "ROOT##" or code in project_roots:
                continue
            project_roots[code] = {
                "code": code,
                "description": safe_bc3_text(raw_root.get("description")) or f"Proyecto {len(project_order) + 1}",
            }
            project_order.append(code)
    items: dict[str, dict] = {}
    order: list[str] = []
    for raw in budget_items:
        code = normalize_resource_code(raw.get("code"))
        if code in items:
            raise ValueError(f"Código de presupuesto duplicado: '{code}'.")
        item = dict(raw)
        item["code"] = code
        parent = str(raw.get("parentCode") or "ROOT##").upper()
        item["parentCode"] = parent
        items[code] = item
        order.append(code)

    export_codes: dict[str, str] = {}
    used_export_codes: set[str] = set(project_roots) | {"ROOT##"}
    for code in order:
        item = items[code]
        has_analysis = bool(calculator.analyses.get(code))
        candidate = str(item.get("polhemPrestoCode") or "").strip().upper()
        if has_analysis and enforce_polhem:
            if not item.get("polhemPartidaCode") or not candidate:
                raise ValueError(f"La partida {code} no tiene clasificación POLHEM completa.")
            candidate = normalize_resource_code(candidate)
        else:
            candidate = code
        if candidate in used_export_codes or candidate in export_codes.values():
            raise ValueError(f"El código PRESTO POLHEM '{candidate}' está duplicado.")
        export_codes[code] = candidate
        used_export_codes.add(candidate)

    children: dict[str, list[str]] = {}
    for code in order:
        parent = items[code]["parentCode"]
        if parent != "ROOT##" and parent not in items and parent not in project_roots:
            parent = "ROOT##"
            items[code]["parentCode"] = parent
        # Las filas de resumen comercial importadas (CD, GG, UT, IVA, total)
        # se conservan como conceptos y en su posición original, pero no vuelven
        # a sumarse como costo directo de ROOT##.
        if (parent == "ROOT##" or parent in project_roots) and str(items[code].get("rootKind")) == "commercial":
            continue
        children.setdefault(parent, []).append(code)

    quantities: dict[str, float] = {}
    for code in order:
        raw_quantity = items[code].get("quantity")
        quantities[code] = 1.0 if raw_quantity is None or str(raw_quantity).strip() == "" else as_number(raw_quantity)

    prices: dict[str, float] = {}

    def item_price(code: str, stack: tuple[str, ...] = ()) -> float:
        if code in prices:
            return prices[code]
        if code in stack:
            raise ValueError(f"Jerarquía circular en el presupuesto: {' > '.join((*stack, code))}.")
        item = items[code]
        analysis_rows = calculator.analyses.get(code, [])
        if source_format == "BC3" and analysis_rows and not analysis_tree_dirty(code):
            # A BC3 concept's ~C price is authoritative. Older databases can
            # contain rounded factors or decompositions whose recomputation is
            # slightly different; preserve that official price until edited.
            price = as_number(item.get("price"))
        elif analysis_rows:
            price = calculator.calculate(code)[0]
        elif children.get(code):
            price = sum(item_price(child, (*stack, code)) * quantities[child] for child in children[code])
        else:
            price = as_number(item.get("price"))
        prices[code] = price
        return price

    for code in order:
        item_price(code)
    project_prices = {
        code: sum(prices.get(child, 0.0) * quantities.get(child, 1.0) for child in children.get(code, []))
        for code in project_order
    }
    root_price = sum(project_prices.values()) + sum(
        prices.get(child, 0.0) * quantities.get(child, 1.0) for child in children.get("ROOT##", [])
    )

    def concept_ref(code: str) -> str:
        export_code = export_codes[code]
        return f"{export_code}#" if bool(items[code].get("isChapter", not safe_bc3_text(items[code].get("unit")))) else export_code

    today = datetime.now().strftime("%d%m%y")
    lines = [
        "~V|CodeAPU CODEAPU.CL|FIEBDC-3/2002|Gestor de APU compatible con Presto 8.8||ANSI|",
        "~K|\\2\\2\\3\\0\\0\\0\\0\\CLP\\|0|",
        f"~C|ROOT##||{project_name}|{format_number(root_price)}|{today}|0|",
    ]
    for code in project_order:
        lines.append(
            f"~C|{code}#||{project_roots[code]['description']}|{format_number(project_prices[code])}|{today}|0|"
        )
    for code in order:
        item = items[code]
        is_chapter = bool(item.get("isChapter", not safe_bc3_text(item.get("unit"))))
        unit = "" if is_chapter else safe_bc3_text(item.get("unit")).upper()
        lines.append(
            f"~C|{concept_ref(code)}|{unit}|{safe_bc3_text(item.get('description'))}|{format_number(prices[code])}|{today}|0|"
        )

    resource_defs: dict[str, CalculatedRow] = {}
    resource_prices: dict[str, float] = {}
    warnings: list[str] = []
    for parent_code in calculator.analyses:
        _, rows = calculator.calculate(parent_code)
        for row in rows:
            if row.code in items:
                continue
            if row.code in used_export_codes:
                raise ValueError(f"El código de recurso {row.code} colisiona con un código de partida POLHEM/PRESTO.")
            price = (AUXILIAR_RATES[row.code] * 100) if row.is_percentage else row.unit_price
            if row.code in resource_defs and not row.is_percentage:
                previous = resource_prices[row.code]
                if abs(previous - price) > 0.000001:
                    raise ValueError(
                        f"El concepto {row.code} tiene precios distintos ({format_number(previous)} y {format_number(price)}). "
                        "En Presto cada código identifica un único concepto; unifica el precio o usa otro código."
                    )
            resource_defs.setdefault(row.code, row)
            resource_prices.setdefault(row.code, price)
    for code, row in sorted(resource_defs.items()):
        lines.append(
            f"~C|{code}|{row.unit}|{row.description}|{format_number(resource_prices[code])}|{today}|1|"
        )

    root_tokens: list[str] = []
    for code in project_order:
        root_tokens.extend([f"{code}#", "1", "1"])
    for child in children.get("ROOT##", []):
        root_tokens.extend([concept_ref(child), "1", format_number(quantities[child])])
    if root_tokens:
        lines.append(f"~D|ROOT##|{'\\'.join(root_tokens)}|")
    for parent, child_codes in children.items():
        if parent == "ROOT##":
            continue
        tokens: list[str] = []
        for child in child_codes:
            tokens.extend([concept_ref(child), "1", format_number(quantities[child])])
        parent_ref = f"{parent}#" if parent in project_roots else concept_ref(parent)
        lines.append(f"~D|{parent_ref}|{'\\'.join(tokens)}|")
    for parent_code in calculator.analyses:
        if parent_code not in items and parent_code not in resource_defs:
            continue
        _, rows = calculator.calculate(parent_code)
        if not rows:
            continue
        tokens: list[str] = []
        for row in rows:
            tokens.extend([row.code, format_number(row.factor), format_number(row.quantity)])
        parent_ref = concept_ref(parent_code) if parent_code in items else parent_code
        lines.append(f"~D|{parent_ref}|{'\\'.join(tokens)}|")

    concepts = {line.split("|")[1] for line in lines if line.startswith("~C|")}
    missing: set[str] = set()
    for line in lines:
        if not line.startswith("~D|"):
            continue
        parts = line.split("|")
        if parts[1] not in concepts:
            missing.add(parts[1])
        tokens = [token for token in parts[2].split("\\") if token]
        missing.update(tokens[index] for index in range(0, len(tokens), 3) if tokens[index] not in concepts)
    if missing:
        raise ValueError(f"El BC3 contiene referencias sin concepto: {', '.join(sorted(missing)[:5])}.")

    content = ("\r\n".join(lines) + "\r\n").encode("cp1252", errors="replace")
    return content, {
        "rootTotal": root_price,
        "conceptCount": len(items) + len(resource_defs) + len(project_roots) + 1,
        "analysisCount": sum(1 for rows in calculator.analyses.values() if rows),
        "resourceCount": len(resource_defs),
        "warnings": list(dict.fromkeys(warnings)),
    }

