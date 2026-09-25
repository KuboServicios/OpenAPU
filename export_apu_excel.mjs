import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { SpreadsheetFile, Workbook } = require("@oai/artifact-tool");

const [, , inputPath, outputPath] = process.argv;
if (!inputPath || !outputPath) throw new Error("Uso: export_apu_excel.mjs entrada.json salida.xlsx");

const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
const project = payload.project || {};
const company = payload.company || {};
const partidas = Array.isArray(payload.partidas) ? payload.partidas : [];
const workbook = Workbook.create();
const usedNames = new Set();
const primary = /^#[0-9a-f]{6}$/i.test(company.primaryColor || "") ? company.primaryColor : "#123B70";
const accent = /^#[0-9a-f]{6}$/i.test(company.accentColor || "") ? company.accentColor : "#E8F0F8";
const line = "#AAB9C9";
const groupSpecs = [["M", "1) MATERIALES"], ["O", "2) MANO DE OBRA"], ["E", "3) EQUIPOS Y MAQUINARIAS"], ["S", "4) SUBCONTRATOS"]];

function safeSheetName(code, index) {
  const base = String(code || `APU ${index + 1}`).replace(/[\\/*?:\[\]]/g, " ").replace(/\s+/g, " ").trim().slice(0, 31) || `APU ${index + 1}`;
  let candidate = base, suffix = 2;
  while (usedNames.has(candidate.toLowerCase())) {
    const tail = ` (${suffix++})`;
    candidate = `${base.slice(0, 31 - tail.length)}${tail}`;
  }
  usedNames.add(candidate.toLowerCase());
  return candidate;
}

function quoteSheet(name) { return `'${String(name).replace(/'/g, "''")}'`; }
function setBorders(range, color = line) { range.format.borders = { preset: "all", style: "thin", color }; }
function titleStyle(range) { range.format = { font: { bold: true, color: primary, fontSize: 20 }, horizontalAlignment: "center", verticalAlignment: "center" }; }
function sectionStyle(range) { range.format = { fill: primary, font: { bold: true, color: "#FFFFFF", fontSize: 10 }, verticalAlignment: "center" }; }
function headerStyle(range) { range.format = { fill: accent, font: { bold: true, color: primary }, horizontalAlignment: "center", verticalAlignment: "center", borders: { preset: "all", style: "thin", color: line } }; }
function addLogo(sheet) {
  if (!/^data:image\/(?:png|jpeg|webp);base64,/i.test(company.logoDataUrl || "")) return;
  sheet.images.add({ dataUrl: company.logoDataUrl, anchor: { from: { row: 0, col: 0 }, extent: { widthPx: 145, heightPx: 60 } } });
}
function companyIdentity() {
  return [company.name, company.rut ? `RUT ${company.rut}` : "", company.phone, company.email, company.website].filter(Boolean).join(" · ");
}

const sheetNames = partidas.map((partida, index) => safeSheetName(partida.originalCode || partida.code, index));
const reportRows = [];

for (const [index, partida] of partidas.entries()) {
  const sheet = workbook.worksheets.add(sheetNames[index]);
  sheet.showGridLines = false;
  addLogo(sheet);
  sheet.getRange("C1:G2").merge();
  sheet.getRange("C1").values = [["ANÁLISIS DE PRECIOS UNITARIOS"]];
  titleStyle(sheet.getRange("C1:G2"));
  sheet.getRange("C3:G3").merge();
  sheet.getRange("C3").values = [[companyIdentity()]];
  sheet.getRange("C3:G3").format = { font: { color: "#53606B", fontSize: 8 }, horizontalAlignment: "right", verticalAlignment: "center" };

  sheet.getRange("A5:G5").values = [["Código", partida.originalCode || partida.code || "", "Fecha", project.date || "", "Moneda", project.currency || "CLP", ""]];
  sheet.getRange("A6:G6").values = [["Partida", partida.description || "", "Proyecto", project.name || payload.projectName || "", "Unidad", partida.unit || "", ""]];
  sheet.getRange("A7:G7").values = [["Mandante", project.client || "", "Ubicación", project.location || "", "Rendimiento base", 1, partida.unit || ""]];
  for (const cell of ["A5", "C5", "E5", "A6", "C6", "E6", "A7", "C7", "E7"]) sheet.getRange(cell).format = { fill: accent, font: { bold: true, color: primary } };
  setBorders(sheet.getRange("A5:G7"), primary);
  sheet.getRange("B6").format.wrapText = true;

  const rows = Array.isArray(partida.rows) ? partida.rows : [];
  let cursor = 9;
  const subtotalCells = {};
  for (const [prefix, label] of groupSpecs) {
    const groupRows = rows.filter(row => String(row.code || "S").toUpperCase().startsWith(prefix));
    sheet.getRange(`A${cursor}:G${cursor}`).merge();
    sheet.getRange(`A${cursor}`).values = [[label]];
    sectionStyle(sheet.getRange(`A${cursor}:G${cursor}`));
    cursor += 1;
    sheet.getRange(`A${cursor}:G${cursor}`).values = [["Código", "Descripción", "", "Unidad", "Cantidad", "Precio Unitario", "Total"]];
    sheet.getRange(`B${cursor}:C${cursor}`).merge();
    headerStyle(sheet.getRange(`A${cursor}:G${cursor}`));
    const dataStart = cursor + 1;
    if (groupRows.length) {
      for (const row of groupRows) {
        sheet.getRange(`B${cursor + 1}:C${cursor + 1}`).merge();
        sheet.getRange(`A${cursor + 1}:G${cursor + 1}`).values = [[row.code || "", row.description || "", null, row.unit || "", Number(row.quantity || 0), row.isPercentage ? null : Number(row.unitPrice || 0), null]];
        if (row.isPercentage) sheet.getRange(`F${cursor + 1}`).formulas = [[cursor + 1 > dataStart ? `=SUM(G${dataStart}:G${cursor})` : "=0"]];
        sheet.getRange(`G${cursor + 1}`).formulas = [[`=E${cursor + 1}*F${cursor + 1}`]];
        cursor += 1;
      }
    } else {
      sheet.getRange(`B${cursor + 1}:C${cursor + 1}`).merge();
      sheet.getRange(`A${cursor + 1}:G${cursor + 1}`).values = [["", "Sin recursos de esta naturaleza", null, "", 0, 0, 0]];
      sheet.getRange(`A${cursor + 1}:G${cursor + 1}`).format = { font: { color: "#7B8580", italic: true } };
      cursor += 1;
    }
    const dataEnd = cursor;
    setBorders(sheet.getRange(`A${dataStart}:G${dataEnd}`));
    sheet.getRange(`A${cursor + 1}:F${cursor + 1}`).merge();
    sheet.getRange(`A${cursor + 1}`).values = [[`SUBTOTAL ${label.split(") ")[1]}`]];
    sheet.getRange(`G${cursor + 1}`).formulas = [[`=SUM(G${dataStart}:G${dataEnd})`]];
    sheet.getRange(`A${cursor + 1}:G${cursor + 1}`).format = { fill: "#F4F7FA", font: { bold: true, color: primary }, horizontalAlignment: "right", borders: { preset: "outside", style: "thin", color: primary } };
    subtotalCells[prefix] = `G${cursor + 1}`;
    cursor += 3;
  }

  const summaryStart = cursor;
  sheet.getRange(`A${summaryStart}:G${summaryStart}`).merge();
  sheet.getRange(`A${summaryStart}`).values = [["RESUMEN DE COSTOS"]];
  sectionStyle(sheet.getRange(`A${summaryStart}:G${summaryStart}`));
  const labels = ["Subtotal materiales", "Subtotal mano de obra", "Subtotal equipos y maquinarias", "Subtotal subcontratos", "COSTO DIRECTO", "Gastos generales", "Utilidad", `PRECIO UNITARIO FINAL POR ${partida.unit || "UN"}`];
  for (const [offset, label] of labels.entries()) {
    const row = summaryStart + 1 + offset;
    sheet.getRange(`A${row}:F${row}`).merge();
    sheet.getRange(`A${row}`).values = [[label]];
  }
  for (const [offset, prefix] of ["M", "O", "E", "S"].entries()) sheet.getRange(`G${summaryStart + 1 + offset}`).formulas = [[`=${subtotalCells[prefix]}`]];
  const directRow = summaryStart + 5, ggRow = summaryStart + 6, utilityRow = summaryStart + 7, finalRow = summaryStart + 8;
  sheet.getRange(`G${directRow}`).formulas = [[`=SUM(G${summaryStart + 1}:G${summaryStart + 4})`]];
  sheet.getRange(`G${ggRow}`).formulas = [[`=G${directRow}*${Number(payload.generalExpenseRate || 0) / 100}`]];
  sheet.getRange(`G${utilityRow}`).formulas = [[`=G${directRow}*${Number(payload.utilityRate || 0) / 100}`]];
  sheet.getRange(`G${finalRow}`).formulas = [[`=SUM(G${directRow}:G${utilityRow})`]];
  setBorders(sheet.getRange(`A${summaryStart + 1}:G${finalRow}`), line);
  sheet.getRange(`A${directRow}:G${directRow}`).format.font = { bold: true, color: primary };
  sheet.getRange(`A${finalRow}:G${finalRow}`).format = { fill: accent, font: { bold: true, color: primary, fontSize: 12 }, borders: { preset: "doubleBottom", style: "medium", color: primary } };

  let noteRow = finalRow + 2;
  if (company.reportNote) {
    sheet.getRange(`A${noteRow}:G${noteRow}`).merge();
    sheet.getRange(`A${noteRow}`).values = [[`Nota: ${company.reportNote}`]];
    sheet.getRange(`A${noteRow}:G${noteRow}`).format = { font: { italic: true, color: "#53606B", fontSize: 8 }, wrapText: true };
    noteRow += 2;
  }
  sheet.getRange(`A${noteRow}:B${noteRow + 2}`).merge(); sheet.getRange(`C${noteRow}:E${noteRow + 2}`).merge(); sheet.getRange(`F${noteRow}:G${noteRow + 2}`).merge();
  sheet.getRange(`A${noteRow}`).values = [[`PREPARÓ\n${company.preparedBy || "Nombre: __________________"}\nFecha: __________________`]];
  sheet.getRange(`C${noteRow}`).values = [[`REVISÓ\n${company.reviewedBy || "Nombre: __________________"}\nFecha: __________________`]];
  sheet.getRange(`F${noteRow}`).values = [[`APROBÓ\n${company.approvedBy || "Nombre: __________________"}\nFecha: __________________`]];
  setBorders(sheet.getRange(`A${noteRow}:G${noteRow + 2}`), primary);
  sheet.getRange(`A${noteRow}:G${noteRow + 2}`).format = { horizontalAlignment: "center", verticalAlignment: "center", wrapText: true, borders: { preset: "all", style: "thin", color: primary } };

  sheet.getRange(`E9:E${finalRow}`).format.numberFormat = "0.000";
  sheet.getRange(`F9:G${finalRow}`).format.numberFormat = "#,##0";
  sheet.getRange(`A1:G${noteRow + 2}`).format.wrapText = true;
  sheet.getRange(`A1:A${noteRow + 2}`).format.columnWidth = 15;
  sheet.getRange(`B1:C${noteRow + 2}`).format.columnWidth = 25;
  sheet.getRange(`D1:D${noteRow + 2}`).format.columnWidth = 12;
  sheet.getRange(`E1:E${noteRow + 2}`).format.columnWidth = 14;
  sheet.getRange(`F1:G${noteRow + 2}`).format.columnWidth = 17;
  sheet.freezePanes.freezeRows(8);
  reportRows.push({ sheetName: sheetNames[index], finalCell: `G${finalRow}`, directCell: `G${directRow}` });
}

const summary = workbook.worksheets.add("Resumen APU");
summary.showGridLines = false;
addLogo(summary);
summary.getRange("C1:G2").merge(); summary.getRange("C1").values = [["RESUMEN DE ANÁLISIS DE PRECIOS UNITARIOS"]]; titleStyle(summary.getRange("C1:G2"));
summary.getRange("C3:G3").merge(); summary.getRange("C3").values = [[companyIdentity()]]; summary.getRange("C3:G3").format = { horizontalAlignment: "right", font: { color: "#53606B", fontSize: 8 } };
summary.getRange("A5:G5").values = [["N°", "Código", "Partida", "Unidad", "Cantidad", "Precio unitario final", "Costo total"]]; headerStyle(summary.getRange("A5:G5"));
if (partidas.length) {
  const values = partidas.map((partida, index) => [index + 1, partida.originalCode || partida.code || "", partida.description || "", partida.unit || "", Number(partida.quantity || 0), null, null]);
  summary.getRangeByIndexes(5, 0, values.length, 7).values = values;
  partidas.forEach((partida, index) => {
    const row = 6 + index, report = reportRows[index];
    summary.getRange(`F${row}`).formulas = [[`=${quoteSheet(report.sheetName)}!${report.finalCell}`]];
    summary.getRange(`G${row}`).formulas = [[`=E${row}*F${row}`]];
  });
  setBorders(summary.getRange(`A6:G${5 + partidas.length}`));
}
const summaryLast = Math.max(6, 5 + partidas.length);
summary.getRange(`E6:E${summaryLast}`).format.numberFormat = "0.000";
summary.getRange(`F6:G${summaryLast}`).format.numberFormat = "#,##0";
summary.getRange(`A1:A${summaryLast}`).format.columnWidth = 7; summary.getRange(`B1:B${summaryLast}`).format.columnWidth = 17; summary.getRange(`C1:C${summaryLast}`).format.columnWidth = 53; summary.getRange(`D1:D${summaryLast}`).format.columnWidth = 11; summary.getRange(`E1:G${summaryLast}`).format.columnWidth = 17;
summary.freezePanes.freezeRows(5);

await workbook.inspect({ kind: "table", sheetId: "Resumen APU", range: `A1:G${Math.min(summaryLast, 20)}`, include: "values,formulas", tableMaxRows: 20, tableMaxCols: 7, maxChars: 4000 });
const formulaErrors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "final formula error scan" });
if (formulaErrors.ndjson && /#REF!|#DIV\/0!|#VALUE!|#NAME\?|#N\/A/.test(formulaErrors.ndjson)) throw new Error("El libro contiene errores de fórmula.");
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

