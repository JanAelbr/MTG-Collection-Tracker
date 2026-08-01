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
  nameScale: "md",
  metaFormat: "yearCode",
  fontFamily: "system",
});

function asBool(value, fallback) {
  return typeof value === "boolean" ? value : fallback;
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
    nameScale,
    metaFormat,
    fontFamily,
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
  return {
    "--storage-tab": style.tabColor,
    "--storage-name": style.nameColor,
    "--storage-meta": style.metaColor,
    "--storage-border": style.borderColor,
    "--storage-font": storageFontStack(style.fontFamily),
  };
}

export function storageSeparatorClassNames(settings) {
  const style = normalizeStorageSeparatorStyle(settings);
  return [
    `storage-separator--icon-${style.iconScale}`,
    `storage-separator--name-${style.nameScale}`,
    style.showIcon ? "" : "storage-separator--no-icon",
  ].filter(Boolean);
}
