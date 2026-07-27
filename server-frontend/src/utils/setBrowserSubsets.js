/** Scryfall child set types loaded automatically with a family root. */
export const AUTO_LOAD_SUBSET_TYPES = Object.freeze([
  "commander",
  "token",
  "memorabilia",
  "minigame",
]);

const AUTO_LOAD_TYPE_SET = new Set(AUTO_LOAD_SUBSET_TYPES);

/** Scryfall set types hidden as family subtiles in the set browser by default. */
export const SET_BROWSER_HIDDEN_SUBSET_TYPES = Object.freeze([
  "token",
  "memorabilia",
  "art_series",
  "promo",
  "minigame",
]);

const HIDDEN_TYPE_SET = new Set(SET_BROWSER_HIDDEN_SUBSET_TYPES);

/** Promo family roots hidden on the Sets page unless Promos is on / searching. */
export const SETS_PAGE_PROMO_TYPES = Object.freeze(["promo"]);

/** Arena / Alchemy family roots hidden unless Alchemy is on / searching. */
export const SETS_PAGE_ALCHEMY_TYPES = Object.freeze(["alchemy"]);

const PROMO_TYPE_SET = new Set(SETS_PAGE_PROMO_TYPES);
const ALCHEMY_TYPE_SET = new Set(SETS_PAGE_ALCHEMY_TYPES);

export function isSetBrowserHiddenSubsetType(setType) {
  return HIDDEN_TYPE_SET.has(String(setType || "").trim().toLowerCase());
}

export function isAutoLoadSubsetType(setType) {
  return AUTO_LOAD_TYPE_SET.has(String(setType || "").trim().toLowerCase());
}

export function isSetsPagePromoType(setType) {
  return PROMO_TYPE_SET.has(String(setType || "").trim().toLowerCase());
}

export function isSetsPageAlchemyType(setType) {
  return ALCHEMY_TYPE_SET.has(String(setType || "").trim().toLowerCase());
}

/** Digital-only roots that are not Alchemy (Alchemy has its own toggle). */
export function isSetsPageDigitalOnlySet(set) {
  if (!set?.digital) {
    return false;
  }
  return !isSetsPageAlchemyType(set.setType);
}

/** @deprecated Prefer the specific helpers above. */
export function isSetsPageSearchOnlyType(setType) {
  return isSetsPagePromoType(setType) || isSetsPageAlchemyType(setType);
}

export function formatSubsetTypeLabel(setType) {
  const type = String(setType || "").trim().toLowerCase();
  if (type === "memorabilia" || type === "art_series") {
    return "art";
  }
  if (type === "commander") {
    return "cmd";
  }
  return type || "set";
}
