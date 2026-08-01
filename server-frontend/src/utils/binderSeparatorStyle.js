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

/** Distinct background looks for binder separators (CSS-rendered). */
export const BINDER_BACKGROUND_THEMES = Object.freeze([
  {
    id: "none",
    label: "Solid",
    description: "Flat base color only",
    defaults: {
      baseColor: "#f3e8d2",
      inkColor: "#18120c",
      accentColor: "#b8944a",
    },
  },
  {
    id: "parchment",
    label: "Parchment",
    description: "Aged manuscript paper",
    defaults: {
      baseColor: "#f3e8d2",
      inkColor: "#18120c",
      accentColor: "#b8944a",
    },
  },
  {
    id: "leather",
    label: "Leather",
    description: "Embossed book cover",
    defaults: {
      baseColor: "#3a2418",
      inkColor: "#f3e6d0",
      accentColor: "#c9a227",
    },
  },
  {
    id: "marble",
    label: "Marble",
    description: "Polished stone with veins",
    defaults: {
      baseColor: "#e8ecef",
      inkColor: "#2a3038",
      accentColor: "#8a9aaa",
    },
  },
  {
    id: "velvet",
    label: "Velvet",
    description: "Deep plush cloth",
    defaults: {
      baseColor: "#2a1020",
      inkColor: "#f5e6d0",
      accentColor: "#d4a017",
    },
  },
  {
    id: "night",
    label: "Night sky",
    description: "Celestial dark field",
    defaults: {
      baseColor: "#0c1220",
      inkColor: "#e8eef8",
      accentColor: "#c9b896",
    },
  },
  {
    id: "brass",
    label: "Brass plaque",
    description: "Brushed metal plate",
    defaults: {
      baseColor: "#8a7350",
      inkColor: "#1a140c",
      accentColor: "#e8d5a3",
    },
  },
]);

const FONT_IDS = new Set(BINDER_FONT_OPTIONS.map((option) => option.id));
const BACKGROUND_IDS = new Set(BINDER_BACKGROUND_THEMES.map((theme) => theme.id));

export const DEFAULT_BINDER_SEPARATOR_STYLE = Object.freeze({
  backgroundTheme: "parchment",
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
  const backgroundTheme = BACKGROUND_IDS.has(input.backgroundTheme)
    ? input.backgroundTheme
    : DEFAULT_BINDER_SEPARATOR_STYLE.backgroundTheme;

  return {
    backgroundTheme,
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

export function binderBackgroundTheme(id) {
  return (
    BINDER_BACKGROUND_THEMES.find((theme) => theme.id === id)
    || BINDER_BACKGROUND_THEMES[0]
  );
}

/** Apply a background theme and its suggested ink / accent / base colors. */
export function applyBinderBackgroundTheme(settings, themeId) {
  const theme = binderBackgroundTheme(themeId);
  return normalizeBinderSeparatorStyle({
    ...settings,
    backgroundTheme: theme.id,
    ...theme.defaults,
  });
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
    `binder-separator--bg-${style.backgroundTheme}`,
    `binder-separator--border-${style.borderStyle}`,
    `binder-separator--title-${style.titleScale}`,
    style.softVeil ? "" : "binder-separator--no-veil",
    style.showCorners ? "" : "binder-separator--no-corners",
    style.showJewels ? "" : "binder-separator--no-jewels",
    style.showOrnament ? "" : "binder-separator--no-ornament",
    style.artStyleUppercase ? "" : "binder-separator--art-normal-case",
  ].filter(Boolean);
}
