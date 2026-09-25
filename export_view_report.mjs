import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { SpreadsheetFile, Workbook } = require("@oai/artifact-tool");
const [, , inputPath, outputPath] = process.argv;
const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
const columns = payload.columns || [];
const rows = payload.rows || [];
if (!columns.length) throw new Error("El reporte no tiene columnas.");

const company = payload.company || {};
const project = payload.project || {};
const primary = /^#[0-9a-f]{6}$/i.test(company.primaryColor || "") ? company.primaryColor : "#123B70";
const accent = /^#[0-9a-f]{6}$/i.test(company.accentColor || "") ? company.accentColor : "#E8F0F8";
const line = "#C3CED8";
const workbook = Workbook.create();
const sheet = workbook.worksheets.add(String(payload.sheetName || "Reporte").slice(0, 31));
sheet.showGridLines = false;

if (/^data:image\/(?:png|jpeg|webp);base64,/i.test(company.logoDataUrl || "")) {
  sheet.images.add({ dataUrl: company.logoDataUrl, anchor: { from: { row: 0, col: 0 }, extent: { widthPx: 135, heightPx: 56 } } });
}
const lastCol = String.fromCharCode(64 + Math.min(columns.length, 26));
sheet.getRange(`C1:${lastCol}2`).merge();
sheet.getRange("C1").values = [[payload.title || "REPORTE CodeAPU"]];
sheet.getRange(`C1:${lastCol}2`).format = { font:{bold:true,color:primary,fontSize:18}, horizontalAlignment:"center", verticalAlignment:"center" };
sheet.getRange(`A3:${lastCol}3`).merge();
sheet.getRange("A3").values = [[`${company.name || "CodeAPU · CodeAPU.cl"} · ${project.name || payload.projectName || "Proyecto"}`]];
sheet.getRange(`A3:${lastCol}3`).format = { font:{color:"#53606B",fontSize:9}, horizontalAlignment:"right" };

let rowIndex = 5;
for (const entry of payload.summary || []) {
  sheet.getRange(`A${rowIndex}:B${rowIndex}`).values = [[entry.label || "", Number(entry.value || 0)]];
  sheet.getRange(`A${rowIndex}`).format = { fill:accent, font:{bold:true,color:primary} };
  sheet.getRange(`B${rowIndex}`).format = { font:{bold:true}, numberFormat:entry.type === "money" ? '"$"#,##0' : "#,##0.00" };
  rowIndex += 1;
}
if ((payload.summary || []).length) rowIndex += 1;
const headerRow = rowIndex;
sheet.getRange(`A${headerRow}:${lastCol}${headerRow}`).values = [columns.map(column => column.label)];
sheet.getRange(`A${headerRow}:${lastCol}${headerRow}`).format = { fill:primary, font:{bold:true,color:"#FFFFFF"}, horizontalAlignment:"center", verticalAlignment:"center", borders:{preset:"all",style:"thin",color:primary} };

if (rows.length) {
  const first = headerRow + 1;
  const last = first + rows.length - 1;
  sheet.getRange(`A${first}:${lastCol}${last}`).values = rows.map(row => columns.map(column => row[column.key] ?? null));
  sheet.getRange(`A${first}:${lastCol}${last}`).format = { borders:{insideHorizontal:{style:"thin",color:line},bottom:{style:"thin",color:line}}, verticalAlignment:"center" };
  columns.forEach((column, index) => {
    const letter = String.fromCharCode(65 + index);
    sheet.getRange(`${letter}:${letter}`).format.columnWidth = column.width || 16;
    if (column.type === "money") sheet.getRange(`${letter}${first}:${letter}${last}`).format.numberFormat = '"$"#,##0';
    if (column.type === "number") sheet.getRange(`${letter}${first}:${letter}${last}`).format.numberFormat = "#,##0.000";
    if (column.type === "percent") sheet.getRange(`${letter}${first}:${letter}${last}`).format.numberFormat = "0.00%";
    if (column.align === "right" || ["money","number","percent"].includes(column.type)) sheet.getRange(`${letter}${first}:${letter}${last}`).format.horizontalAlignment = "right";
  });
  sheet.getRange(`B${first}:B${last}`).format.wrapText = true;
}
sheet.freezePanes.freezeRows(headerRow);
const errors = await workbook.inspect({ kind:"match", searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options:{useRegex:true,maxResults:100}, summary:"formula error scan" });
if (errors.ndjson && /#REF!|#DIV\/0!|#VALUE!|#NAME\?|#N\/A/.test(errors.ndjson)) throw new Error(errors.ndjson);
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

