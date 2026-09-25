from __future__ import annotations

import base64, html, io, json, math, re, sys
from pathlib import Path
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.platypus import SimpleDocTemplate, Image, KeepTogether, Paragraph, Spacer, Table, TableStyle

def num(value):
    try: return float(value or 0)
    except (TypeError, ValueError): return 0
def money(value): return f"${round(num(value)):,.0f}".replace(",", ".")
def number(value): return f"{num(value):,.3f}".replace(",", "X").replace(".", ",").replace("X", ".").rstrip("0").rstrip(",")
def safe(value): return html.escape(str(value or ""))
def colour(value, fallback): return colors.HexColor(value) if re.fullmatch(r"#[0-9a-fA-F]{6}", str(value or "")) else colors.HexColor(fallback)

def summary_table(summary, body, accent, line, available_width):
    """Build a compact, uniform summary grid with at most two rows for 12 items."""
    column_count = len(summary) if len(summary) <= 6 else math.ceil(len(summary) / 2)
    rows = []
    for start in range(0, len(summary), column_count):
        row = []
        for item in summary[start:start + column_count]:
            shown = money(item.get("value")) if item.get("type") == "money" else number(item.get("value"))
            row.append(Paragraph(f"<b>{safe(item.get('label'))}</b><br/><font size=8>{safe(shown)}</font>", body))
        row.extend([Paragraph("", body)] * (column_count - len(row)))
        rows.append(row)
    return Table(
        rows,
        colWidths=[available_width / column_count] * column_count,
        rowHeights=[18 * mm] * len(rows),
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), accent),
            ("BOX", (0, 0), (-1, -1), .5, line),
            ("INNERGRID", (0, 0), (-1, -1), .35, line),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]),
    )

def logo(data_url):
    match = re.fullmatch(r"data:image/(?:png|jpeg|webp);base64,(.+)", str(data_url or ""), re.I | re.S)
    if not match: return None
    try:
        source=PILImage.open(io.BytesIO(base64.b64decode(match.group(1)))); source.load()
        target=io.BytesIO(); source.convert("RGBA").save(target,format="PNG"); target.seek(0)
        result=Image(target); result._restrictSize(40*mm,15*mm); return result
    except Exception: return None

def labor_histogram(chart, body, primary, line, available_width):
    months = list(chart.get("months") or [])
    if not months: return []
    csv_colour, sub_colour = colors.HexColor("#D97757"), colors.HexColor("#C69A45")
    drawing_height, baseline, plot_height = 54 * mm, 9 * mm, 39 * mm
    drawing = Drawing(available_width, drawing_height)
    drawing.add(Line(0, baseline, available_width, baseline, strokeColor=line, strokeWidth=.5))
    maximum = max(1, max(round(num(month.get("total"))) for month in months))
    slot = available_width / len(months); bar_width = slot * .62
    for index, month in enumerate(months):
        csv = max(0, round(num(month.get("csv")))); sub = max(0, round(num(month.get("sub")))); total = max(0, round(num(month.get("total"))))
        x = index * slot + (slot - bar_width) / 2; bar_height = plot_height * total / maximum; parts = max(1, csv + sub)
        csv_height = bar_height * csv / parts; sub_height = bar_height - csv_height
        drawing.add(Rect(x, baseline, bar_width, csv_height, fillColor=csv_colour, strokeColor=None))
        drawing.add(Rect(x, baseline + csv_height, bar_width, sub_height, fillColor=sub_colour, strokeColor=None))
        drawing.add(String(x + bar_width / 2, baseline + bar_height + 2, str(total), fontName="Helvetica", fontSize=6, textAnchor="middle", fillColor=primary))
        drawing.add(String(x + bar_width / 2, 1.5 * mm, f"M{round(num(month.get('month')))}", fontName="Helvetica", fontSize=6, textAnchor="middle", fillColor=colors.HexColor("#43556A")))
    company_label = str(chart.get("companyLabel") or "Empresa oferente no definida")
    legend = Table([[f"PROPIA · {company_label}", "SUB · Subcontratada", f"Peak: {round(num(chart.get('peak')))} personas"]], colWidths=[55*mm, 60*mm, available_width-115*mm], style=TableStyle([
        ("TEXTCOLOR", (0,0), (0,0), csv_colour), ("TEXTCOLOR", (1,0), (1,0), sub_colour), ("TEXTCOLOR", (2,0), (2,0), primary),
        ("FONTNAME", (0,0), (-1,-1), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 7), ("ALIGN", (2,0), (2,0), "RIGHT"),
        ("LEFTPADDING", (0,0), (-1,-1), 0), ("RIGHTPADDING", (0,0), (-1,-1), 4), ("TOPPADDING", (0,0), (-1,-1), 2), ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ]))
    matrix = [[Paragraph("<b>Dotación</b>", body)] + [Paragraph(f"<b>M{round(num(month.get('month')))}</b>", body) for month in months]]
    for label, key in (("PROPIA", "csv"), ("SUB", "sub"), ("TOTAL", "total")):
        matrix.append([Paragraph(f"<b>{label}</b>", body)] + [Paragraph(str(round(num(month.get(key)))), body) for month in months])
    label_width = 15 * mm; month_width = (available_width - label_width) / len(months)
    matrix_table = Table(matrix, colWidths=[label_width] + [month_width] * len(months), rowHeights=[6*mm]*4, style=TableStyle([
        ("BACKGROUND", (0,0), (-1,0), primary), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("BACKGROUND", (0,1), (0,-1), colors.HexColor("#E8F0F8")),
        ("GRID", (0,0), (-1,-1), .3, line), ("ALIGN", (0,0), (-1,-1), "CENTER"), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 1), ("RIGHTPADDING", (0,0), (-1,-1), 1), ("TOPPADDING", (0,0), (-1,-1), 1), ("BOTTOMPADDING", (0,0), (-1,-1), 1),
    ]))
    heading = Paragraph(f"<b>{safe(chart.get('title') or 'Histograma mensual de dotación')}</b>", ParagraphStyle("chart-title", parent=body, fontName="Helvetica-Bold", fontSize=10, leading=12, textColor=primary))
    return [KeepTogether([heading, Spacer(1, 1.5*mm), legend, drawing, matrix_table]), Spacer(1, 4*mm)]

def main(input_path, output_path):
    payload=json.loads(Path(input_path).read_text(encoding="utf-8")); company=payload.get("company") or {}; project=payload.get("project") or {}
    primary=colour(company.get("primaryColor"),"#123B70"); accent=colour(company.get("accentColor"),"#E8F0F8"); line=colors.HexColor("#C3CED8")
    styles=getSampleStyleSheet(); body=ParagraphStyle("body",parent=styles["BodyText"],fontName="Helvetica",fontSize=7,leading=8.5,textColor=colors.HexColor("#17251F")); body_bold=ParagraphStyle("body-bold",parent=body,fontName="Helvetica-Bold"); body_bold_white=ParagraphStyle("body-bold-white",parent=body_bold,textColor=colors.white); title=ParagraphStyle("title",parent=body,fontName="Helvetica-Bold",fontSize=17,leading=20,textColor=primary,alignment=1); header=ParagraphStyle("header",parent=body,fontName="Helvetica-Bold",textColor=colors.white,alignment=1)
    doc=SimpleDocTemplate(output_path,pagesize=landscape(A4),leftMargin=11*mm,rightMargin=11*mm,topMargin=10*mm,bottomMargin=12*mm,title=str(payload.get("title") or "Reporte"),author=str(company.get("name") or "CodeAPU.cl"))
    story=[]; mark=logo(company.get("logoDataUrl")); identity=Paragraph(f"<b>{safe(company.get('name') or 'CodeAPU.cl')}</b><br/>{safe(company.get('rut'))}<br/>{safe(company.get('email'))}",body)
    story.append(Table([[mark or "",Paragraph(safe(payload.get("title") or "REPORTE"),title),identity]],colWidths=[45*mm,175*mm,50*mm],style=TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(1,0),(1,0),"CENTER"),("ALIGN",(2,0),(2,0),"RIGHT"),("LINEBELOW",(0,0),(-1,-1),1,primary),("BOTTOMPADDING",(0,0),(-1,-1),6)])))
    story.append(Spacer(1,4*mm)); story.append(Paragraph(f"<b>Proyecto:</b> {safe(project.get('name') or payload.get('projectName'))} &nbsp;&nbsp; <b>Fecha:</b> {safe(project.get('reportDate') or '')}",body)); story.append(Spacer(1,3*mm))
    summary=payload.get("summary") or []
    if summary:
        story.append(summary_table(summary, body, accent, line, doc.width)); story.append(Spacer(1,3*mm))
    if (payload.get("chart") or {}).get("type") == "laborHistogram":
        story.extend(labor_histogram(payload["chart"], body, primary, line, doc.width))
    columns=payload.get("columns") or []; rows=payload.get("rows") or []
    data=[[Paragraph(safe(c.get('label')),header) for c in columns]]
    type_palette={"M":("#D9EAF7","#0B4F8A"),"O":("#DCE6F2","#17365D"),"E":("#F7DED5","#8B452E"),"S":("#E5E7EB","#374151")}
    for row in rows:
        current=[]
        row_style=body_bold_white if row.get("rowKind") in {"group","grandTotal"} else body_bold if row.get("rowKind") in {"typeHeader","typeSubtotal","subtotal"} else body
        for column in columns:
            value=row.get(column.get("key")); kind=column.get("type")
            shown="" if value in (None, "") else money(value) if kind=="money" else f"{number(num(value)*100)}%" if kind=="percent" else number(value) if kind=="number" else safe(value)
            current.append(Paragraph(f"<nobr>{shown}</nobr>" if kind in {"money","number","percent"} else shown,row_style))
        data.append(current)
    widths=[max(18,min(80,float(c.get("pdfWidth") or c.get("width") or 20)))*mm for c in columns]; scale=(landscape(A4)[0]-22*mm)/sum(widths); widths=[w*scale for w in widths]
    row_heights=[None]+[3*mm if row.get("rowKind")=="separator" else None for row in rows]
    table=Table(data,colWidths=widths,rowHeights=row_heights,repeatRows=1)
    commands=[("BACKGROUND",(0,0),(-1,0),primary),("TEXTCOLOR",(0,0),(-1,0),colors.white),("VALIGN",(0,0),(-1,-1),"TOP"),("GRID",(0,0),(-1,-1),.3,line),("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]
    for table_row,row in enumerate(rows,1):
        if row.get("rowKind") == "group":
            row_colour=colors.HexColor(row["rowColor"]) if re.fullmatch(r"#[0-9a-fA-F]{6}",str(row.get("rowColor") or "")) else primary
            commands.extend([("BACKGROUND",(0,table_row),(-1,table_row),row_colour),("SPAN",(1,table_row),(-1,table_row))])
        elif row.get("rowKind") == "typeHeader":
            fill,text=type_palette.get(str(row.get("natureCode") or ""),("#E8F0F8","#123B70"))
            commands.extend([("BACKGROUND",(0,table_row),(-1,table_row),colors.HexColor(fill)),("TEXTCOLOR",(0,table_row),(-1,table_row),colors.HexColor(text)),("SPAN",(1,table_row),(-1,table_row))])
        elif row.get("rowKind") in {"typeSubtotal","subtotal"}:
            fill,text=type_palette.get(str(row.get("natureCode") or ""),("#E9EEF4","#123B70"))
            commands.extend([("BACKGROUND",(0,table_row),(-1,table_row),colors.HexColor(fill)),("TEXTCOLOR",(0,table_row),(-1,table_row),colors.HexColor(text)),("LINEABOVE",(0,table_row),(-1,table_row),.8,colors.HexColor(text))])
        elif row.get("rowKind") == "grandTotal": commands.extend([("BACKGROUND",(0,table_row),(-1,table_row),primary),("TEXTCOLOR",(0,table_row),(-1,table_row),colors.white),("LINEABOVE",(0,table_row),(-1,table_row),1,primary)])
        elif row.get("rowKind") == "separator": commands.extend([("SPAN",(0,table_row),(-1,table_row)),("BACKGROUND",(0,table_row),(-1,table_row),colors.white),("LINEABOVE",(0,table_row),(-1,table_row),0,colors.white),("LINEBELOW",(0,table_row),(-1,table_row),0,colors.white)])
    for index,column in enumerate(columns):
        if column.get("type") in ("money","number","percent"): commands.append(("ALIGN",(index,1),(index,-1),"RIGHT"))
    table.setStyle(TableStyle(commands)); story.append(table)
    note=company.get("reportNote");
    if note: story.extend([Spacer(1,3*mm),Paragraph(f"<b>Nota:</b> {safe(note)}",body)])
    doc.build(story)

if __name__ == "__main__": main(sys.argv[1],sys.argv[2])

