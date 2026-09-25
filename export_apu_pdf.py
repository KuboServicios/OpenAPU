from __future__ import annotations

import base64
import html
import io
import json
import re
import sys
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, PageBreak, PageTemplate, Paragraph,
    Spacer, Table, TableStyle,
)


def number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def money(value: object) -> str:
    return f"{round(number(value)):,.0f}".replace(",", ".")


def quantity(value: object) -> str:
    text = f"{number(value):,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return text.rstrip("0").rstrip(",") or "0"


def valid_color(value: object, fallback: str) -> colors.Color:
    text = str(value or "")
    return colors.HexColor(text) if re.fullmatch(r"#[0-9A-Fa-f]{6}", text) else colors.HexColor(fallback)


def safe(value: object) -> str:
    """Escape user-supplied text before inserting it in a ReportLab Paragraph."""
    return html.escape(str(value or ""))


def logo_image(data_url: object) -> Image | None:
    match = re.fullmatch(r"data:image/(?:png|jpeg|webp);base64,(.+)", str(data_url or ""), re.I | re.S)
    if not match:
        return None
    try:
        source = PILImage.open(io.BytesIO(base64.b64decode(match.group(1))))
        source.load()
        normalized = io.BytesIO()
        source.convert("RGBA").save(normalized, format="PNG")
        normalized.seek(0)
        image = Image(normalized)
        image._restrictSize(42 * mm, 18 * mm)
        return image
    except Exception:
        return None


def main(input_path: str, output_path: str) -> None:
    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    project = payload.get("project") or {}
    company = payload.get("company") or {}
    partidas = payload.get("partidas") or []
    primary = valid_color(company.get("primaryColor"), "#123B70")
    accent = valid_color(company.get("accentColor"), "#E8F0F8")
    light_line = colors.HexColor("#B8C6D8")
    grey = colors.HexColor("#4F5B66")
    styles = getSampleStyleSheet()
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.8, leading=9.5, textColor=colors.HexColor("#17251F"))
    small = ParagraphStyle("Small", parent=body, fontSize=6.8, leading=8.2, textColor=grey)
    section = ParagraphStyle("Section", parent=body, fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=primary, spaceBefore=4, spaceAfter=3)
    title = ParagraphStyle("Title", parent=body, fontName="Helvetica-Bold", fontSize=18, leading=21, alignment=TA_CENTER, textColor=primary, spaceAfter=7)
    right = ParagraphStyle("Right", parent=body, alignment=TA_RIGHT)
    center = ParagraphStyle("Center", parent=body, alignment=TA_CENTER)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(light_line)
        canvas.line(14 * mm, 10 * mm, A4[0] - 14 * mm, 10 * mm)
        canvas.setFont("Helvetica", 6.8)
        canvas.setFillColor(grey)
        identity = str(company.get("name") or "CodeAPU.cl")
        canvas.drawString(14 * mm, 6.5 * mm, identity[:95])
        page_text = f"Pagina {doc.page}"
        canvas.drawRightString(A4[0] - 14 * mm, 6.5 * mm, page_text)
        canvas.restoreState()

    doc = BaseDocTemplate(
        output_path, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=12 * mm, bottomMargin=14 * mm,
        title=f"Desglose APU - {project.get('name') or payload.get('projectName') or 'Proyecto'}",
        author=str(company.get("name") or "CodeAPU.cl"),
    )
    doc.addPageTemplates(PageTemplate(id="APU", frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")], onPage=footer))
    story = []
    group_specs = [
        ("M", "1) MATERIALES"), ("O", "2) MANO DE OBRA"),
        ("E", "3) EQUIPOS Y MAQUINARIAS"), ("S", "4) SUBCONTRATOS"),
    ]

    for partida_index, partida in enumerate(partidas):
        if partida_index:
            story.append(PageBreak())
        logo = logo_image(company.get("logoDataUrl"))
        company_lines = [safe(company.get("name"))]
        if company.get("rut"):
            company_lines.append(f"RUT: {safe(company['rut'])}")
        contact = " · ".join(safe(company.get(key)) for key in ("phone", "email", "website") if company.get(key))
        if contact:
            company_lines.append(contact)
        company_block = Paragraph("<br/>".join(f"<b>{line}</b>" if index == 0 else line for index, line in enumerate(company_lines)), small)
        header = Table([[logo or "", company_block]], colWidths=[48 * mm, doc.width - 48 * mm], rowHeights=[20 * mm])
        header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (0, 0), "LEFT"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.extend([header, Paragraph("DESGLOSE APU", title)])

        info = [
            [Paragraph("<b>Código:</b>", body), Paragraph(safe(partida.get("originalCode") or partida.get("code")), body), Paragraph("<b>Fecha:</b>", body), Paragraph(safe(project.get("date")), body)],
            [Paragraph("<b>Partida:</b>", body), Paragraph(safe(partida.get("description")), body), Paragraph("<b>Moneda:</b>", body), Paragraph(safe(project.get("currency") or "CLP"), body)],
            [Paragraph("<b>Unidad:</b>", body), Paragraph(safe(partida.get("unit")), body), Paragraph("<b>Proyecto:</b>", body), Paragraph(safe(project.get("name") or payload.get("projectName")), body)],
            [Paragraph("<b>Rendimiento base:</b>", body), Paragraph(f"1,00 {safe(partida.get('unit'))}", body), Paragraph("<b>Mandante:</b>", body), Paragraph(safe(project.get("client")), body)],
        ]
        info_table = Table(info, colWidths=[26 * mm, 76 * mm, 25 * mm, doc.width - 127 * mm])
        info_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), .55, primary), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (0, -1), accent), ("BACKGROUND", (2, 0), (2, -1), accent),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.extend([info_table, Spacer(1, 4 * mm)])

        rows = list(partida.get("rows") or [])
        direct_cost = 0.0
        group_totals = {}
        for prefix, label in group_specs:
            group_rows = [row for row in rows if str(row.get("code") or "S").upper().startswith(prefix)]
            subtotal = sum(number(row.get("total")) for row in group_rows)
            group_totals[prefix] = subtotal
            direct_cost += subtotal
            story.append(Paragraph(label, section))
            data = [[Paragraph("Descripción", center), Paragraph("Unidad", center), Paragraph("Cantidad", center), Paragraph("Factor / Rend.", center), Paragraph("Precio Unitario", center), Paragraph("Total", center)]]
            if group_rows:
                for row in group_rows:
                    context = " · ".join(filter(None, [safe(row.get("codeapuCode")), safe(row.get("resourceFamilyCode")), safe(row.get("dependency"))]))
                    description = f"<b>{safe(row.get('prestoCode') or row.get('code'))}</b> · {safe(row.get('description'))}{f'<br/><font size=6>{context}</font>' if context else ''}"
                    factor = row.get("factor") if row.get("factor") is not None else 1
                    data.append([Paragraph(description, body), Paragraph(safe(row.get("unit")), center), Paragraph(quantity(row.get("quantity")), right), Paragraph(quantity(factor), right), Paragraph(money(row.get("unitPrice")), right), Paragraph(money(row.get("total")), right)])
            else:
                data.append([Paragraph("Sin recursos de esta naturaleza", small), "", "", "", "", ""])
            data.append([Paragraph(f"<b>SUBTOTAL {label.split(') ', 1)[-1]}</b>", right), "", "", "", "", Paragraph(f"<b>{money(subtotal)}</b>", right)])
            table = Table(data, colWidths=[64 * mm, 18 * mm, 23 * mm, 22 * mm, 27 * mm, doc.width - 154 * mm], repeatRows=1)
            table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -2), .35, light_line), ("BOX", (0, 0), (-1, -1), .65, primary),
                ("BACKGROUND", (0, 0), (-1, 0), accent), ("TEXTCOLOR", (0, 0), (-1, 0), primary),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F5F7FA")),
                ("SPAN", (0, -1), (4, -1)), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.extend([table, Spacer(1, 2 * mm)])

        gg_rate = number(payload.get("generalExpenseRate")) / 100
        utility_rate = number(payload.get("utilityRate")) / 100
        gg = direct_cost * gg_rate
        utility = direct_cost * utility_rate
        final_price = direct_cost + gg + utility
        summary_data = [
            [Paragraph("<b>RESUMEN DE COSTOS</b>", body), "", Paragraph("<b>Ajuste / %</b>", center), Paragraph("<b>Base de cálculo</b>", center), Paragraph("<b>Valor (CLP)</b>", center)],
            [Paragraph("Subtotal materiales", body), Paragraph(money(group_totals.get("M")), right), Paragraph(f"GG · {gg_rate*100:.2f}%".replace(".", ","), right), Paragraph(money(direct_cost), right), Paragraph(money(gg), right)],
            [Paragraph("Subtotal mano de obra", body), Paragraph(money(group_totals.get("O")), right), Paragraph(f"UT · {utility_rate*100:.2f}%".replace(".", ","), right), Paragraph(money(direct_cost), right), Paragraph(money(utility), right)],
            [Paragraph("Subtotal equipos y maquinarias", body), Paragraph(money(group_totals.get("E")), right), "", "", ""],
            [Paragraph("Subtotal subcontratos", body), Paragraph(money(group_totals.get("S")), right), "", Paragraph("<b>PRECIO UNITARIO FINAL</b>", body), Paragraph(f"<b>{money(final_price)}</b><br/>{safe(project.get('currency') or 'CLP')}/{safe(partida.get('unit'))}", right)],
            [Paragraph("<b>COSTO DIRECTO</b>", body), Paragraph(f"<b>{money(direct_cost)}</b>", right), "", "", ""],
        ]
        summary_table = Table(summary_data, colWidths=[55 * mm, 32 * mm, 22 * mm, 39 * mm, doc.width - 148 * mm])
        summary_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), .7, primary), ("INNERGRID", (2, 0), (-1, -2), .35, light_line),
            ("SPAN", (0, 0), (1, 0)), ("BACKGROUND", (0, 0), (-1, 0), accent),
            ("TEXTCOLOR", (0, 0), (-1, 0), primary), ("SPAN", (3, 4), (3, 5)), ("SPAN", (4, 4), (4, 5)),
            ("BACKGROUND", (3, 4), (4, 5), colors.HexColor("#F5F7FA")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.extend([Spacer(1, 2 * mm), summary_table])
        if company.get("reportNote"):
            story.extend([Spacer(1, 2 * mm), Paragraph(f"<b>Nota:</b> {safe(company['reportNote'])}", small)])
        signatures = []
        for label, key in (("Preparó", "preparedBy"), ("Revisó", "reviewedBy"), ("Aprobó", "approvedBy")):
            name = safe(company.get(key))
            signatures.append(Paragraph(f"<b>{label}</b><br/><br/>Nombre: {name}<br/>Fecha: __________________", center))
        sign_table = Table([signatures], colWidths=[doc.width / 3] * 3, rowHeights=[24 * mm])
        sign_table.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), .55, primary), ("INNERGRID", (0, 0), (-1, -1), .55, primary), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 6)]))
        story.extend([Spacer(1, 3 * mm), sign_table])

    if not partidas:
        story.append(Paragraph("No existen APU para exportar.", body))
    doc.build(story)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Uso: export_apu_pdf.py entrada.json salida.pdf")
    main(sys.argv[1], sys.argv[2])

