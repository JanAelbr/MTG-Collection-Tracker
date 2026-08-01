export const STORAGE_SEPARATOR_STYLE_KEY = "lotr.separators.storageStyle";

export const STORAGE_META_FORMATS = Object.freeze([
  "yearCode",
  "codeYear",
  "year",
  "code",
  "none",
]);

export const STORAGE_ICON_SCALES = Object.freeze(["sm", "md", "lg"]);
export const STORAGE_NAME_SCALES = Object.freeze(["sm", "md", "lg"]);
export const STORAGE_HEADER_ALIGNS = Object.freeze(["left", "center"]);

export const STORAGE_FONT_OPTIONS = Object.freeze([
  {
    id: "system",
    label: "System sans",
    stack: 'Segoe UI, Arial, sans-serif',
  },
  {
    id: "cinzel",
    label: "Cinzel",
    stack: '"Cinzel", "Palatino Linotype", Palatino, serif',
  },
  {
    id: "libre",
    label: "Libre Baskerville",
    stack: '"Libre Baskerville", Georgia, serif',
  },
]);

const FONT_IDS = new Set(STORAGE_FONT_OPTIONS.map((option) => option.id));

export const DEFAULT_STORAGE_SEPARATOR_STYLE = Object.freeze({
  tabColor: "#f3f3f3",
  nameColor: "#222222",
  metaColor: "#666666",
  borderColor: "#bbbbbb",
  showIcon: true,
  iconScale: "lg",
  iconOffsetMm: 0,
  headerAlign: "left",
  nameScale: "md",
  metaFormat: "yearCode",
  fontFamily: "system",
  tabHeightMm: 17,
});

export const STORAGE_TAB_HEIGHT_MIN_MM = 10;
export const STORAGE_TAB_HEIGHT_MAX_MM = 30;
export const STORAGE_ICON_OFFSET_MIN_MM = -8;
export const STORAGE_ICON_OFFSET_MAX_MM = 8;

function asBool(value, fallback) {
  return typeof value === "boolean" ? value : fallback;
}

function asNumber(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function asHexColor(value, fallback) {
  const text = String(value || "").trim();
  if (/^#[0-9a-fA-F]{6}$/.test(text)) {
    return text.toLowerCase();
  }
  if (/^#[0-9a-fA-F]{3}$/.test(text)) {
    const [, r, g, b] = text;
    return `#${r}${r}${g}${g}${b}${b}`.toLowerCase();
  }
  return fallback;
}

function resolveIconOffsetMm(input) {
  if (input.iconOffsetMm != null) {
    return asNumber(input.iconOffsetMm, DEFAULT_STORAGE_SEPARATOR_STYLE.iconOffsetMm);
  }
  // Legacy left-only control stored a positive leftward shift.
  if (input.iconOffsetLeftMm != null) {
    return -asNumber(input.iconOffsetLeftMm, 0);
  }
  return DEFAULT_STORAGE_SEPARATOR_STYLE.iconOffsetMm;
}

export function normalizeStorageSeparatorStyle(input = {}) {
  const metaFormat = STORAGE_META_FORMATS.includes(input.metaFormat)
    ? input.metaFormat
    : DEFAULT_STORAGE_SEPARATOR_STYLE.metaFormat;
  const iconScale = STORAGE_ICON_SCALES.includes(input.iconScale)
    ? input.iconScale
    : DEFAULT_STORAGE_SEPARATOR_STYLE.iconScale;
  const nameScale = STORAGE_NAME_SCALES.includes(input.nameScale)
    ? input.nameScale
    : DEFAULT_STORAGE_SEPARATOR_STYLE.nameScale;
  const headerAlign = STORAGE_HEADER_ALIGNS.includes(input.headerAlign)
    ? input.headerAlign
    : DEFAULT_STORAGE_SEPARATOR_STYLE.headerAlign;
  const fontFamily = FONT_IDS.has(input.fontFamily)
    ? input.fontFamily
    : DEFAULT_STORAGE_SEPARATOR_STYLE.fontFamily;

  return {
    tabColor: asHexColor(input.tabColor, DEFAULT_STORAGE_SEPARATOR_STYLE.tabColor),
    nameColor: asHexColor(input.nameColor, DEFAULT_STORAGE_SEPARATOR_STYLE.nameColor),
    metaColor: asHexColor(input.metaColor, DEFAULT_STORAGE_SEPARATOR_STYLE.metaColor),
    borderColor: asHexColor(input.borderColor, DEFAULT_STORAGE_SEPARATOR_STYLE.borderColor),
    showIcon: asBool(input.showIcon, DEFAULT_STORAGE_SEPARATOR_STYLE.showIcon),
    iconScale,
    iconOffsetMm: clamp(
      resolveIconOffsetMm(input),
      STORAGE_ICON_OFFSET_MIN_MM,
      STORAGE_ICON_OFFSET_MAX_MM,
    ),
    headerAlign,
    nameScale,
    metaFormat,
    fontFamily,
    tabHeightMm: clamp(
      asNumber(input.tabHeightMm, DEFAULT_STORAGE_SEPARATOR_STYLE.tabHeightMm),
      STORAGE_TAB_HEIGHT_MIN_MM,
      STORAGE_TAB_HEIGHT_MAX_MM,
    ),
  };
}

export function loadStorageSeparatorStyle() {
  try {
    const raw = localStorage.getItem(STORAGE_SEPARATOR_STYLE_KEY);
    if (!raw) {
      return { ...DEFAULT_STORAGE_SEPARATOR_STYLE };
    }
    return normalizeStorageSeparatorStyle(JSON.parse(raw));
  } catch {
    return { ...DEFAULT_STORAGE_SEPARATOR_STYLE };
  }
}

export function saveStorageSeparatorStyle(settings) {
  const normalized = normalizeStorageSeparatorStyle(settings);
  localStorage.setItem(STORAGE_SEPARATOR_STYLE_KEY, JSON.stringify(normalized));
  return normalized;
}

export function storageFontStack(fontFamily) {
  const match = STORAGE_FONT_OPTIONS.find((option) => option.id === fontFamily);
  return match?.stack || STORAGE_FONT_OPTIONS[0].stack;
}

export function formatStorageMetaLine(year, setCode, metaFormat) {
  const y = String(year || "").trim();
  const code = String(setCode || "").trim().toUpperCase();
  switch (metaFormat) {
    case "codeYear":
      if (code && y) {
        return `${code} - ${y}`;
      }
      return code || y;
    case "year":
      return y;
    case "code":
      return code;
    case "none":
      return "";
    case "yearCode":
    default:
      if (y && code) {
        return `${y} - ${code}`;
      }
      return y || code;
  }
}

export function storageStyleToCssVars(settings) {
  const style = normalizeStorageSeparatorStyle(settings);
  const iconScale = style.iconScale === "sm" ? 0.48 : style.iconScale === "md" ? 0.64 : 0.8;
  const nameScale = style.nameScale === "sm" ? 0.155 : style.nameScale === "lg" ? 0.23 : 0.19;
  return {
    "--storage-tab": style.tabColor,
    "--storage-name": style.nameColor,
    "--storage-meta": style.metaColor,
    "--storage-border": style.borderColor,
    "--storage-font": storageFontStack(style.fontFamily),
    "--storage-tab-height": `${style.tabHeightMm}mm`,
    "--storage-icon-scale": String(iconScale),
    "--storage-icon-offset": `${style.iconOffsetMm}mm`,
    "--storage-name-scale": String(nameScale),
  };
}

export function storageSeparatorClassNames(settings) {
  const style = normalizeStorageSeparatorStyle(settings);
  return [
    style.showIcon ? "" : "storage-separator--no-icon",
    style.headerAlign === "center" ? "storage-separator--center" : "",
  ].filter(Boolean);
}
