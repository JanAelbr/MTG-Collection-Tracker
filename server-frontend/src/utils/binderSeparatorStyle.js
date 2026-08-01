export const BINDER_SEPARATOR_STYLE_KEY = "lotr.separators.binderStyle";

export const BINDER_FONT_OPTIONS = Object.freeze([
  {
    id: "cinzel",
    label: "Cinzel",
    stack: '"Cinzel", "Palatino Linotype", Palatino, serif',
  },
  {
    id: "imFell",
    label: "IM Fell English",
    stack: '"IM Fell English", "Palatino Linotype", Palatino, serif',
  },
  {
    id: "medieval",
    label: "MedievalSharp",
    stack: '"MedievalSharp", "Palatino Linotype", Palatino, serif',
  },
  {
    id: "libre",
    label: "Libre Baskerville",
    stack: '"Libre Baskerville", Georgia, serif',
  },
]);

export const BINDER_BORDER_STYLES = Object.freeze(["ornate", "simple", "none"]);
export const BINDER_TITLE_SCALES = Object.freeze(["sm", "md", "lg"]);

const FONT_IDS = new Set(BINDER_FONT_OPTIONS.map((option) => option.id));

export const DEFAULT_BINDER_SEPARATOR_STYLE = Object.freeze({
  inkColor: "#18120c",
  accentColor: "#b8944a",
  baseColor: "#f3e8d2",
  parchmentOpacity: 50,
  parchmentSoftness: 55,
  softVeil: true,
  uniqueParchment: true,
  borderStyle: "ornate",
  showCorners: true,
  showJewels: true,
  showOrnament: true,
  fontFamily: "cinzel",
  titleScale: "md",
  artStyleUppercase: true,
});

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function asNumber(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

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

export function normalizeBinderSeparatorStyle(input = {}) {
  const borderStyle = BINDER_BORDER_STYLES.includes(input.borderStyle)
    ? input.borderStyle
    : DEFAULT_BINDER_SEPARATOR_STYLE.borderStyle;
  const titleScale = BINDER_TITLE_SCALES.includes(input.titleScale)
    ? input.titleScale
    : DEFAULT_BINDER_SEPARATOR_STYLE.titleScale;
  const fontFamily = FONT_IDS.has(input.fontFamily)
    ? input.fontFamily
    : DEFAULT_BINDER_SEPARATOR_STYLE.fontFamily;

  return {
    inkColor: asHexColor(input.inkColor, DEFAULT_BINDER_SEPARATOR_STYLE.inkColor),
    accentColor: asHexColor(input.accentColor, DEFAULT_BINDER_SEPARATOR_STYLE.accentColor),
    baseColor: asHexColor(input.baseColor, DEFAULT_BINDER_SEPARATOR_STYLE.baseColor),
    parchmentOpacity: clamp(
      asNumber(input.parchmentOpacity, DEFAULT_BINDER_SEPARATOR_STYLE.parchmentOpacity),
      0,
      100,
    ),
    parchmentSoftness: clamp(
      asNumber(input.parchmentSoftness, DEFAULT_BINDER_SEPARATOR_STYLE.parchmentSoftness),
      0,
      100,
    ),
    softVeil: asBool(input.softVeil, DEFAULT_BINDER_SEPARATOR_STYLE.softVeil),
    uniqueParchment: asBool(input.uniqueParchment, DEFAULT_BINDER_SEPARATOR_STYLE.uniqueParchment),
    borderStyle,
    showCorners: asBool(input.showCorners, DEFAULT_BINDER_SEPARATOR_STYLE.showCorners),
    showJewels: asBool(input.showJewels, DEFAULT_BINDER_SEPARATOR_STYLE.showJewels),
    showOrnament: asBool(input.showOrnament, DEFAULT_BINDER_SEPARATOR_STYLE.showOrnament),
    fontFamily,
    titleScale,
    artStyleUppercase: asBool(
      input.artStyleUppercase,
      DEFAULT_BINDER_SEPARATOR_STYLE.artStyleUppercase,
    ),
  };
}

export function loadBinderSeparatorStyle() {
  try {
    const raw = localStorage.getItem(BINDER_SEPARATOR_STYLE_KEY);
    if (!raw) {
      return { ...DEFAULT_BINDER_SEPARATOR_STYLE };
    }
    return normalizeBinderSeparatorStyle(JSON.parse(raw));
  } catch {
    return { ...DEFAULT_BINDER_SEPARATOR_STYLE };
  }
}

export function saveBinderSeparatorStyle(settings) {
  const normalized = normalizeBinderSeparatorStyle(settings);
  localStorage.setItem(BINDER_SEPARATOR_STYLE_KEY, JSON.stringify(normalized));
  return normalized;
}

export function binderFontStack(fontFamily) {
  const match = BINDER_FONT_OPTIONS.find((option) => option.id === fontFamily);
  return match?.stack || BINDER_FONT_OPTIONS[0].stack;
}

/** Map softness 0–100 → brightness / contrast used on the parchment layer. */
export function parchmentFilterFromSoftness(softness) {
  const t = clamp(asNumber(softness, 55), 0, 100) / 100;
  return {
    brightness: (1.08 + t * 0.28).toFixed(3),
    contrast: (0.92 - t * 0.28).toFixed(3),
  };
}

export function binderStyleToCssVars(settings) {
  const style = normalizeBinderSeparatorStyle(settings);
  const filter = parchmentFilterFromSoftness(style.parchmentSoftness);
  return {
    "--binder-ink": style.inkColor,
    "--binder-accent": style.accentColor,
    "--binder-base": style.baseColor,
    "--binder-font": binderFontStack(style.fontFamily),
    "--parchment-opacity": (style.parchmentOpacity / 100).toFixed(3),
    "--parchment-brightness": filter.brightness,
    "--parchment-contrast": filter.contrast,
    "--parchment-sepia": "0.06",
  };
}

export function binderSeparatorClassNames(settings) {
  const style = normalizeBinderSeparatorStyle(settings);
  return [
    `binder-separator--border-${style.borderStyle}`,
    `binder-separator--title-${style.titleScale}`,
    style.softVeil ? "" : "binder-separator--no-veil",
    style.showCorners ? "" : "binder-separator--no-corners",
    style.showJewels ? "" : "binder-separator--no-jewels",
    style.showOrnament ? "" : "binder-separator--no-ornament",
    style.artStyleUppercase ? "" : "binder-separator--art-normal-case",
  ].filter(Boolean);
}
