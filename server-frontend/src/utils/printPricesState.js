export const PRINT_PRICES_STATE_KEY = "lotr.print.prices";

export const DEFAULT_PRINT_PRICES_STATE = Object.freeze({
  filterQuery: "",
  setScope: "loaded",
  showTokenAndArtSets: false,
  showPromoSets: false,
  selectedCodes: [],
  strategy: "trend",
  minimumPrice: "",
  sort: "collector",
  ownedOnly: true,
  includeTimestamp: false,
  showSetIcon: true,
  showFullSetName: true,
  fontScale: 100,
  columnCount: 1,
  selectedArtStyles: [],
  previewIndex: 0,
});

function asBoolean(value, fallback) {
  return typeof value === "boolean" ? value : fallback;
}

function asStringArray(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item)).filter(Boolean);
}

export function normalizePrintPricesState(raw) {
  const source = raw && typeof raw === "object" ? raw : {};
  const fontScale = Number(source.fontScale);
  const previewIndex = Number(source.previewIndex);
  const columnCount = Number(source.columnCount);
  const clampedFont = Number.isFinite(fontScale)
    ? Math.min(100, Math.max(60, Math.round(fontScale / 5) * 5))
    : 100;
  const clampedColumns = Number.isInteger(columnCount)
    ? Math.min(4, Math.max(1, columnCount))
    : 1;
  return {
    filterQuery: typeof source.filterQuery === "string" ? source.filterQuery : "",
    setScope: source.setScope === "all" ? "all" : "loaded",
    showTokenAndArtSets: asBoolean(source.showTokenAndArtSets, false),
    showPromoSets: asBoolean(source.showPromoSets, false),
    selectedCodes: asStringArray(source.selectedCodes),
    strategy: typeof source.strategy === "string" && source.strategy ? source.strategy : "trend",
    minimumPrice: source.minimumPrice == null || source.minimumPrice === ""
      ? ""
      : String(source.minimumPrice),
    sort: source.sort === "price" ? "price" : "collector",
    ownedOnly: asBoolean(source.ownedOnly, true),
    includeTimestamp: asBoolean(source.includeTimestamp, false),
    showSetIcon: asBoolean(source.showSetIcon, true),
    showFullSetName: asBoolean(source.showFullSetName, true),
    fontScale: clampedFont,
    columnCount: clampedColumns,
    selectedArtStyles: asStringArray(source.selectedArtStyles),
    previewIndex: Number.isInteger(previewIndex) && previewIndex >= 0 ? previewIndex : 0,
  };
}

export function loadPrintPricesState() {
  try {
    const raw = localStorage.getItem(PRINT_PRICES_STATE_KEY);
    if (!raw) {
      return { ...DEFAULT_PRINT_PRICES_STATE, selectedCodes: [], selectedArtStyles: [] };
    }
    return normalizePrintPricesState(JSON.parse(raw));
  } catch {
    return { ...DEFAULT_PRINT_PRICES_STATE, selectedCodes: [], selectedArtStyles: [] };
  }
}

export function savePrintPricesState(state) {
  const normalized = normalizePrintPricesState(state);
  localStorage.setItem(PRINT_PRICES_STATE_KEY, JSON.stringify(normalized));
  return normalized;
}
