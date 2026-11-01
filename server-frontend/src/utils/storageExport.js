import { zipSync, strToU8 } from "fflate";

import { cardDisplayName, cardFinish } from "./finishes";
export const CARDMARKET_BULK_CHUNK_SIZE = 100;

export const STORAGE_EXPORT_FORMATS = [
  {
    id: "app-csv",
    label: "This app (set;number;finish;qty)",
    extension: "csv",
    mime: "text/csv;charset=utf-8",
  },
  {
    id: "moxfield",
    label: "Moxfield CSV",
    extension: "csv",
    mime: "text/csv;charset=utf-8",
  },
  {
    id: "archidekt",
    label: "Archidekt CSV",
    extension: "csv",
    mime: "text/csv;charset=utf-8",
  },
  {
    id: "deckbox",
    label: "Deckbox CSV",
    extension: "csv",
    mime: "text/csv;charset=utf-8",
  },
  {
    id: "tcg-powertools",
    label: "TCG PowerTools CSV",
    extension: "csv",
    mime: "text/csv;charset=utf-8",
    utf8Bom: true,
  },
  {
    id: "cardmarket-stock",
    label: "Cardmarket stock import",
    extension: "csv",
    mime: "text/csv;charset=utf-8",
  },
  {
    id: "cardmarket-bulk",
    label: "Cardmarket Bulk Import (ZIP, one set per file, max 100 rows)",
    extension: "zip",
    mime: "application/zip",
  },
];

const PRODUCT_ID_PATTERN = /idProduct=(\d+)/i;

export function parseIdProduct(url) {
  const text = String(url || "").trim();
  if (!text) {
    return null;
  }
  const match = text.match(PRODUCT_ID_PATTERN);
  return match ? match[1] : null;
}

export function cardmarketUrlForCard(card) {
  const finish = cardFinish(card);
  const nonfoil = String(card?.cardmarketUrl || "").trim();
  const foil = String(card?.cardmarketUrlFoil || "").trim();
  if (finish === 1 || finish === 2) {
    return foil || nonfoil;
  }
  return nonfoil || foil;
}

export function aggregateExportLines(cards = []) {
  const buckets = new Map();
  for (const card of cards || []) {
    const finish = cardFinish(card);
    const key = `${String(card.setCode || "").toUpperCase()}|${String(card.collectorNumber || "").trim()}|${finish}`;
    const qty = Math.max(0, Number(card.copyCount) || 0);
    if (qty <= 0) {
      continue;
    }
    const existing = buckets.get(key);
    if (existing) {
      existing.qty += qty;
    } else {
      buckets.set(key, { card, qty });
    }
  }
  return [...buckets.values()];
}

export function collectLeafExportGroups(groups = []) {
  const out = [];
  for (const group of groups || []) {
    if (group?.groups?.length) {
      out.push(...collectLeafExportGroups(group.groups));
    } else if (group?.cards?.length) {
      out.push(group);
    }
  }
  return out;
}

export function buildExportSegments({
  cards = [],
  groups = [],
  isGrouped = false,
  singleGroup = null,
} = {}) {
  if (singleGroup) {
    return [{
      label: exportSegmentLabel(singleGroup),
      cards: [...(singleGroup.cards || [])],
    }];
  }
  if (isGrouped && groups.length) {
    return collectLeafExportGroups(groups).map((group) => ({
      label: exportSegmentLabel(group),
      cards: [...(group.cards || [])],
    }));
  }
  return [{ label: "", cards: [...cards] }];
}

export function exportSegmentLabel(group) {
  if (!group) {
    return "";
  }
  return String(group.label || group.key || "").trim();
}

export function chunkExportLines(lines, chunkSize = CARDMARKET_BULK_CHUNK_SIZE) {
  if (!lines.length) {
    return [];
  }
  const size = Math.max(1, Number(chunkSize) || CARDMARKET_BULK_CHUNK_SIZE);
  const chunks = [];
  for (let index = 0; index < lines.length; index += size) {
    chunks.push(lines.slice(index, index + size));
  }
  return chunks;
}

export function chunkFileLabel(segmentLabel, startIndex, endIndex) {
  const range = `${startIndex}-${endIndex}`;
  const prefix = String(segmentLabel || "")
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "-")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 60);
  return prefix ? `${prefix} ${range}` : range;
}

export function safeFilePart(value, maxLen = 80) {
  const cleaned = String(value || "")
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "-")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, maxLen);
  return cleaned || "export";
}

function csvCell(value) {
  const text = value == null ? "" : String(value);
  if (/[",\n\r]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function csvRow(cells) {
  return cells.map(csvCell).join(",");
}

function semicolonRow(cells) {
  return cells.map((value) => String(value ?? "").replace(/;/g, ",")).join(";");
}

function formatPrice(value) {
  const num = Number(value);
  if (!Number.isFinite(num) || num <= 0) {
    return "";
  }
  return num.toFixed(2);
}

function foilFlag(card) {
  const finish = cardFinish(card);
  return finish === 1 || finish === 2 ? "true" : "false";
}

/** PowerTools `cn` column: strip leading zeros from numeric collector numbers. */
export function powerToolsCollectorNumber(value) {
  const text = String(value ?? "").trim();
  if (!text) {
    return "";
  }
  if (/^\d+$/.test(text)) {
    return String(parseInt(text, 10));
  }
  return text;
}

function cardmarketBulkFoil(card) {
  const finish = cardFinish(card);
  return finish === 1 || finish === 2 ? "foil" : "";
}

/** Plain English name for Cardmarket bulk listing fuzzy match (no finish suffix). */
export function cardmarketBulkName(card) {
  let name = String(card?.name || card?.cardName || "").trim();
  name = name.replace(/\s+\(Foil\)$/i, "").replace(/\s+\(Etched\)$/i, "");
  if (name.includes("//")) {
    name = name.split("//")[0].trim();
  }
  return name;
}

/** Cardmarket bulk import only works per expansion page — one set per CSV series. */
export function buildCardmarketBulkSetSegments(cards = []) {
  const bySet = new Map();
  for (const card of cards || []) {
    const setCode = String(card.setCode || "").trim().toUpperCase() || "UNKNOWN";
    const bucket = bySet.get(setCode) || [];
    bucket.push(card);
    bySet.set(setCode, bucket);
  }
  return [...bySet.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([setCode, setCards]) => ({
      label: setCode,
      cards: setCards,
    }));
}

const CARDMARKET_BULK_README = `Cardmarket Bulk Import (browser extension)

Each CSV in this ZIP contains cards from ONE set only (max 100 rows per file).

Before importing a file:
1. On Cardmarket, open Stock → List bulk items for that set's expansion.
2. Use the extension's Import CSV and choose the file whose name starts with that set code (e.g. "MH2 1-100.csv").
3. Map columns once if prompted: Name, Set, Foil, Quantity, Price, Condition, Language.
4. Select rows and click Fill page.

Rows stay disabled if the CSV set does not match the expansion page you have open.
`;

function linePurchasePrice(line) {
  const unit = line.card?.purchaseValue;
  if (unit != null && Number(unit) > 0) {
    return formatPrice(unit);
  }
  const total = line.card?.currentValue;
  if (total != null && line.qty > 0) {
    return formatPrice(Number(total) / line.qty);
  }
  return "";
}

export function buildAppCsv(lines) {
  const rows = lines.map(({ card, qty }) => {
    const finish = cardFinish(card);
    const finishPart = finish === 0 ? "" : finish;
    if (qty === 1 && finish === 0) {
      return `${card.setCode};${card.collectorNumber}`;
    }
    if (qty === 1) {
      return `${card.setCode};${card.collectorNumber};${finishPart}`;
    }
    return `${card.setCode};${card.collectorNumber};${finishPart};${qty}`;
  });
  return rows.join("\n");
}

export function buildMoxfieldCsv(lines) {
  const header = csvRow(["Count", "Name", "Edition", "Collector Number", "Foil"]);
  const rows = lines.map(({ card, qty }) => csvRow([
    qty,
    cardDisplayName(card),
    card.setCode,
    card.collectorNumber,
    foilFlag(card),
  ]));
  return [header, ...rows].join("\n");
}

export function buildArchidektCsv(lines) {
  const header = csvRow([
    "Amount",
    "Name",
    "Edition",
    "Collector Number",
    "Alter",
    "Foil",
    "Tags",
    "Purchase Price",
  ]);
  const rows = lines.map(({ card, qty }) => csvRow([
    qty,
    cardDisplayName(card),
    card.setCode,
    card.collectorNumber,
    "",
    foilFlag(card),
    "",
    linePurchasePrice({ card, qty }),
  ]));
  return [header, ...rows].join("\n");
}

export function buildDeckboxCsv(lines) {
  const header = csvRow(["Count", "Name", "Edition", "Card Number", "Foil"]);
  const rows = lines.map(({ card, qty }) => csvRow([
    qty,
    cardDisplayName(card),
    card.setCode,
    card.collectorNumber,
    foilFlag(card),
  ]));
  return [header, ...rows].join("\n");
}

export function buildTcgPowerToolsCsv(lines) {
  const header = csvRow([
    "cardmarketId",
    "quantity",
    "name",
    "set",
    "cn",
    "condition",
    "language",
    "isPlayset",
    "isFirstEd",
    "isReverseHolo",
    "isSigned",
    "price",
    "comment",
  ]);
  const rows = lines.map(({ card, qty }) => csvRow([
    parseIdProduct(cardmarketUrlForCard(card)) || "",
    qty,
    cardmarketBulkName(card),
    String(card.setCode || "").trim().toUpperCase(),
    powerToolsCollectorNumber(card.collectorNumber),
    "NM",
    "English",
    "false",
    "false",
    foilFlag(card),
    "false",
    linePurchasePrice({ card, qty }),
    "",
  ]));
  return [header, ...rows].join("\n");
}

export function buildCardmarketStockCsv(lines) {
  const header = semicolonRow([
    "idProduct",
    "Amount",
    "Price",
    "Condition",
    "Language",
    "Foil",
    "Comments",
  ]);
  const rows = lines.map(({ card, qty }) => {
    const idProduct = parseIdProduct(cardmarketUrlForCard(card)) || "";
    return semicolonRow([
      idProduct,
      qty,
      linePurchasePrice({ card, qty }),
      "NM",
      "en",
      foilFlag(card) === "true" ? "1" : "0",
      "",
    ]);
  });
  return [header, ...rows].join("\n");
}

export function buildCardmarketBulkCsv(lines) {
  const header = csvRow([
    "Name",
    "Set",
    "Foil",
    "Signed",
    "Quantity",
    "Price",
    "Condition",
    "Language",
    "Comment",
  ]);
  const rows = lines.map(({ card, qty }) => csvRow([
    cardmarketBulkName(card),
    String(card.setCode || "").trim().toUpperCase(),
    cardmarketBulkFoil(card),
    "",
    qty,
    linePurchasePrice({ card, qty }),
    "NM",
    "English",
    "",
  ]));
  return [header, ...rows].join("\n");
}

export function buildCsvForFormat(formatId, lines) {
  switch (formatId) {
    case "app-csv":
      return buildAppCsv(lines);
    case "moxfield":
      return buildMoxfieldCsv(lines);
    case "archidekt":
      return buildArchidektCsv(lines);
    case "deckbox":
      return buildDeckboxCsv(lines);
    case "tcg-powertools":
      return buildTcgPowerToolsCsv(lines);
    case "cardmarket-stock":
      return buildCardmarketStockCsv(lines);
    case "cardmarket-bulk":
      return buildCardmarketBulkCsv(lines);
    default:
      throw new Error(`Unknown export format: ${formatId}`);
  }
}

export function buildCardmarketBulkZipFiles(segments, { chunkSize = CARDMARKET_BULK_CHUNK_SIZE } = {}) {
  const files = { "README.txt": CARDMARKET_BULK_README };
  const setSegments = buildCardmarketBulkSetSegments(
    (segments || []).flatMap((segment) => segment.cards || []),
  );
  for (const segment of setSegments) {
    const lines = aggregateExportLines(segment.cards);
    if (!lines.length) {
      continue;
    }
    const chunks = chunkExportLines(lines, chunkSize);
    chunks.forEach((chunk, chunkIndex) => {
      const start = chunkIndex * chunkSize + 1;
      const end = chunkIndex * chunkSize + chunk.length;
      const label = chunkFileLabel(segment.label, start, end);
      const fileName = `${safeFilePart(label)}.csv`;
      files[fileName] = buildCardmarketBulkCsv(chunk);
    });
  }
  return files;
}

export function zipTextFiles(files) {
  const payload = {};
  for (const [name, content] of Object.entries(files)) {
    payload[name] = strToU8(content);
  }
  return zipSync(payload);
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function defaultExportBasename(locationLabels = "storage") {
  const stamp = new Date().toISOString().slice(0, 10);
  return `${safeFilePart(locationLabels, 48)}-${stamp}`;
}

export function runStorageExport({
  formatId,
  cards = [],
  groups = [],
  isGrouped = false,
  singleGroup = null,
  basename = "storage-export",
}) {
  const format = STORAGE_EXPORT_FORMATS.find((item) => item.id === formatId);
  if (!format) {
    throw new Error(`Unknown export format: ${formatId}`);
  }
  const segments = buildExportSegments({ cards, groups, isGrouped, singleGroup });
  const base = safeFilePart(basename);

  if (formatId === "cardmarket-bulk") {
    const exportCards = segments.flatMap((segment) => segment.cards || []);
    const files = buildCardmarketBulkZipFiles([{ label: "", cards: exportCards }]);
    if (!Object.keys(files).length) {
      throw new Error("Nothing to export");
    }
    const zipBytes = zipTextFiles(files);
    downloadBlob(new Blob([zipBytes], { type: format.mime }), `${base}.zip`);
    return;
  }

  const allLines = aggregateExportLines(
    segments.flatMap((segment) => segment.cards),
  );
  if (!allLines.length) {
    throw new Error("Nothing to export");
  }
  let csv = buildCsvForFormat(formatId, allLines);
  if (format.utf8Bom) {
    csv = `\uFEFF${csv}`;
  }
  downloadBlob(
    new Blob([csv], { type: format.mime }),
    `${base}.${format.extension}`,
  );
}
