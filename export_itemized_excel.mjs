import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { SpreadsheetFile, Workbook } = require("@oai/artifact-tool");

const [, , inputPath, outputPath] = process.argv;
if (!inputPath || !outputPath) throw new Error("Uso: export_itemized_excel.mjs entrada.json salida.xlsx");

const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
const items = Array.isArray(payload.items) ? payload.items : [];
const roots = Array.isArray(payload.projectRoots) ? payload.projectRoots : [];
const project = payload.project || {};
const company = payload.company || {};
if (!items.length) throw new Error("No hay filas de itemizado para exportar.");

const primary = /^#[0-9a-f]{6}$/i.test(company.primaryColor || "") ? company.primaryColor : "#123B70";
const accent = /^#[0-9a-f]{6}$/i.test(company.accentColor || "") ? company.accentColor : "#E8F0F8";
const line = "#C3CED8";
const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Itemizado");
sheet.showGridLines = false;

if (/^data:image\/(?:png|jpeg|webp);base64,/i.test(company.logoDataUrl || "")) {
  sheet.images.add({ dataUrl: company.logoDataUrl, anchor: { from: { row: 0, col: 0 }, extent: { widthPx: 135, heightPx: 56 } } });
}
sheet.getRange("C1:F2").merge();
sheet.getRange("C1").values = [["ITEMIZADO DE PRESUPUESTO"]];
sheet.getRange("C1:F2").format = { font: { bold: true, color: primary, fontSize: 18 }, horizontalAlignment: "center", verticalAlignment: "center" };
sheet.getRange("C3:F3").merge();
sheet.getRange("C3").values = [[company.name || "CodeAPU · CodeAPU.cl"]];
sheet.getRange("C3:F3").format = { font: { color: "#53606B", fontSize: 9 }, horizontalAlignment: "right" };
sheet.getRange("A4:F4").values = [["Proyecto", project.name || payload.projectName || "", "Mandante", project.client || "", "Moneda", project.currency || "CLP"]];
for (const cell of ["A4", "C4", "E4"]) sheet.getRange(cell).format = { fill: accent, font: { bold: true, color: primary } };
sheet.getRange("A4:F4").format.borders = { preset: "all", style: "thin", color: line };

const rootByCode = new Map(roots.map(root => [String(root.code || "").toUpperCase(), root]));
const rows = [];
const insertedRoots = new Set();
for (const item of items) {
  const projectCode = String(item.projectCode || "ROOT").toUpperCase();
  if (!insertedRoots.has(projectCode)) {
    const source = rootByCode.get(projectCode) || roots.find(root => String(root.description || "") === String(item.projectName || "")) || {};
    rows.push({ code: source.code || item.projectCode || projectCode, description: source.description || item.projectName || payload.projectName || "Proyecto", level: 1, isRoot: true, isChapter: true, parentCode: "", quantity: null, price: null, total: null });
    insertedRoots.add(projectCode);
  }
  rows.push({ ...item, level: Math.max(2, Number(item.level) || 2) });
}

sheet.getRange("A6:F6").values = [["Código", "Descripción", "Unidad", "Cantidad", "Precio Unitario", "Total"]];
sheet.getRange("A6:F6").format = { fill: primary, font: { bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center", borders: { preset: "all", style: "thin", color: primary } };

const firstRow = 7;
const values = rows.map(row => [
  row.originalCode || row.code || "",
  `${"   ".repeat(Math.max(0, (Number(row.level) || 1) - 1))}${row.description || ""}`,
  row.unit || "",
  row.isPartida ? Number(row.quantity || 0) : null,
  row.isPartida ? Number(row.price || 0) : null,
  row.isPartida ? null : Number(row.total || 0),
]);
sheet.getRange(`A${firstRow}:F${firstRow + rows.length - 1}`).values = values;

const excelRowByCode = new Map();
rows.forEach((row, index) => excelRowByCode.set(String(row.code || "").toUpperCase(), firstRow + index));
const children = new Map();
rows.forEach((row, index) => {
  const parent = String(row.parentCode || "").toUpperCase();
  if (!parent) return;
  if (!children.has(parent)) children.set(parent, []);
  children.get(parent).push(firstRow + index);
});
rows.forEach((row, index) => {
  const excelRow = firstRow + index;
  if (row.isPartida) {
    sheet.getRange(`F${excelRow}`).formulas = [[`=D${excelRow}*E${excelRow}`]];
  } else {
    const directChildren = children.get(String(row.code || "").toUpperCase()) || [];
    if (directChildren.length === 1) sheet.getRange(`F${excelRow}`).formulas = [[`=F${directChildren[0]}`]];
    else if (directChildren.length > 1) sheet.getRange(`F${excelRow}`).formulas = [[`=SUM(${directChildren.map(value => `F${value}`).join(",")})`]];
  }
  const range = sheet.getRange(`A${excelRow}:F${excelRow}`);
  range.format.borders = { insideHorizontal: { style: "thin", color: line }, bottom: { style: "thin", color: line } };
  range.format.verticalAlignment = "center";
  if (row.isRoot) range.format = { fill: primary, font: { bold: true, color: "#FFFFFF", fontSize: 11 }, borders: { preset: "all", style: "thin", color: primary }, verticalAlignment: "center" };
  else if (row.isChapter || !String(row.unit || "").trim()) range.format = { fill: Number(row.level) === 2 ? accent : "#F4F7F9", font: { bold: true, color: primary }, borders: { insideHorizontal: { style: "thin", color: line }, bottom: { style: "thin", color: line } }, verticalAlignment: "center" };
});

sheet.getRange(`D${firstRow}:D${firstRow + rows.length - 1}`).format.numberFormat = "#,##0.000";
sheet.getRange(`E${firstRow}:F${firstRow + rows.length - 1}`).format.numberFormat = '"$"#,##0';
sheet.getRange(`B${firstRow}:B${firstRow + rows.length - 1}`).format.wrapText = true;
sheet.getRange("A:A").format.columnWidth = 18;
sheet.getRange("B:B").format.columnWidth = 62;
sheet.getRange("C:C").format.columnWidth = 12;
sheet.getRange("D:D").format.columnWidth = 15;
sheet.getRange("E:F").format.columnWidth = 18;
sheet.getRange("1:3").format.rowHeight = 22;
sheet.freezePanes.freezeRows(6);

const inspected = await workbook.inspect({ kind: "table", sheetId: "Itemizado", range: `A1:F${Math.min(firstRow + rows.length, 35)}`, include: "values,formulas", tableMaxRows: 35, tableMaxCols: 6, maxChars: 8000 });
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "formula error scan" });
if (errors.ndjson && /#REF!|#DIV\/0!|#VALUE!|#NAME\?|#N\/A/.test(errors.ndjson)) throw new Error(errors.ndjson);
if (!inspected.ndjson) throw new Error("No fue posible verificar el itemizado.");

await fs.mkdir(new URL(".", `file:///${outputPath.replace(/\\/g, "/")}`).pathname, { recursive: true }).catch(() => {});
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

