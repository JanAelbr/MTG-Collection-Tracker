import { setCompletionRarity } from "./format";
import { mtgVectorsSetIconUri } from "./mtgVectors";

export function scryfallSetIconUri(setCode) {
  if (!setCode || String(setCode).toLowerCase() === "all") {
    return null;
  }
  return `https://svgs.scryfall.io/sets/${String(setCode).toLowerCase()}.svg`;
}

export function resolveSetIconUri(set) {
  if (!set) {
    return null;
  }
  return set.iconUri || scryfallSetIconUri(set.setCode);
}

/** Rarity-colored set symbol for the set browser gallery (mtg-vectors). */
export function resolveSetGalleryIconUri(set) {
  if (!set?.setCode || set.setCode === "All") {
    return null;
  }
  const completionRarity = setCompletionRarity(set) || "common";
  return mtgVectorsSetIconUri(set.setCode, completionRarity);
}

/** Switch a gallery icon to the Scryfall fallback once; avoids retry loops. */
export function applySetGalleryIconFallback(img, set) {
  if (!img || img.dataset.iconFallback === "scryfall") {
    return false;
  }
  const fallback = resolveSetIconUri(set);
  if (!fallback) {
    return false;
  }
  const current = img.currentSrc || img.src || "";
  if (current === fallback || current.endsWith(fallback)) {
    return false;
  }
  img.dataset.iconFallback = "scryfall";
  img.src = fallback;
  return true;
}
