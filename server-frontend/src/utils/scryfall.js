import { setCompletionRarity } from "./format";
import { mtgVectorsSetIconUri } from "./mtgVectors";

/**
 * Scryfall set codes whose icon file name differs from the set code.
 * Secret Lair Drop uses star.svg (there is no sld.svg).
 */
const SCRYFALL_SET_ICON_CODES = {
  SLD: "star",
};

export function scryfallSetIconCode(setCode) {
  const normalized = String(setCode || "").trim().toUpperCase();
  if (!normalized || normalized === "ALL") {
    return null;
  }
  return SCRYFALL_SET_ICON_CODES[normalized] || normalized.toLowerCase();
}

export function scryfallSetIconUri(setCode) {
  const iconCode = scryfallSetIconCode(setCode);
  if (!iconCode) {
    return null;
  }
  return `https://svgs.scryfall.io/sets/${String(iconCode).toLowerCase()}.svg`;
}

/** Canonical Scryfall page for a specific printing. */
export function scryfallCardUri(setCode, collectorNumber) {
  const set = String(setCode || "").trim().toLowerCase();
  const number = String(collectorNumber || "").trim();
  if (!set || !number) {
    return "";
  }
  return `https://scryfall.com/card/${encodeURIComponent(set)}/${encodeURIComponent(number)}`;
}

/** Scryfall search of every printing for this card name (unique=prints). */
export function scryfallPrintsSearchUri(cardName) {
  const name = String(cardName || "").trim();
  if (!name) {
    return "";
  }
  const query = `!"${name}"`;
  return `https://scryfall.com/search?as=grid&order=released&q=${encodeURIComponent(query)}&unique=prints`;
}

export function setFamilyRootCode(setOrCode) {
  if (setOrCode && typeof setOrCode === "object") {
    const root = String(setOrCode.familyRoot || setOrCode.parentSetCode || "").trim().toUpperCase();
    if (root && root !== "ALL") {
      return root;
    }
    const code = String(setOrCode.setCode || "").trim().toUpperCase();
    return code && code !== "ALL" ? code : "";
  }
  const code = String(setOrCode || "").trim().toUpperCase();
  return code && code !== "ALL" ? code : "";
}

export function resolveSetIconUri(set) {
  if (!set) {
    return null;
  }
  if (set.iconUri) {
    return set.iconUri;
  }
  return scryfallSetIconUri(set.setCode);
}

/** Rarity-colored set symbol for the set browser gallery (mtg-vectors). */
export function resolveSetGalleryIconUri(set) {
  if (!set?.setCode || set.setCode === "All") {
    return null;
  }
  const completionRarity = setCompletionRarity(set) || "common";
  return mtgVectorsSetIconUri(set.setCode, completionRarity);
}

function uniqueIconCandidates(urls) {
  const seen = new Set();
  const out = [];
  for (const url of urls) {
    if (!url || seen.has(url)) {
      continue;
    }
    seen.add(url);
    out.push(url);
  }
  return out;
}

/** Ordered icon URLs: own set first, then family root. */
export function setIconFallbackCandidates(set, { gallery = false } = {}) {
  if (!set?.setCode || set.setCode === "All") {
    return [];
  }
  const code = String(set.setCode).trim().toUpperCase();
  const root = setFamilyRootCode(set);
  const completionRarity = setCompletionRarity(set) || "common";
  const candidates = [];

  if (gallery) {
    candidates.push(mtgVectorsSetIconUri(code, completionRarity));
  }
  if (set.iconUri) {
    candidates.push(set.iconUri);
  }
  candidates.push(scryfallSetIconUri(code));

  if (root && root !== code) {
    if (gallery) {
      candidates.push(mtgVectorsSetIconUri(root, completionRarity));
    }
    candidates.push(scryfallSetIconUri(root));
  }

  return uniqueIconCandidates(candidates);
}

/** Advance a gallery/set tile icon through own Scryfall, then family-root icons. */
export function applySetGalleryIconFallback(img, set) {
  if (!img || !set) {
    return false;
  }
  const candidates = setIconFallbackCandidates(set, { gallery: true });
  const current = img.currentSrc || img.src || "";
  let start = Number(img.dataset.iconFallbackIndex);
  if (!Number.isFinite(start) || start < 0) {
    start = candidates.findIndex((url) => url && (current === url || current.endsWith(url)));
    if (start < 0) {
      start = 0;
    }
  }
  let nextIndex = start + 1;
  while (nextIndex < candidates.length) {
    const nextSrc = candidates[nextIndex];
    if (nextSrc && nextSrc !== current && !current.endsWith(nextSrc)) {
      img.dataset.iconFallbackIndex = String(nextIndex);
      img.src = nextSrc;
      return true;
    }
    nextIndex += 1;
  }
  return false;
}
