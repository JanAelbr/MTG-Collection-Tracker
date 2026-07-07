/** Pinned release from https://github.com/Investigamer/mtg-vectors */
const MTG_VECTORS_VERSION = "v0.9.1%2B20260707";
const MTG_VECTORS_CDN = `https://cdn.jsdelivr.net/gh/Investigamer/mtg-vectors@${MTG_VECTORS_VERSION}/svg/optimized/set`;

/** Set code -> symbol code (from data/set/routes.yml). */
const SET_SYMBOL_ROUTES = {
  PDP10: "DPA",
  PDP12: "DPA",
  PARL: "DEFAULT",
  PSDC: "M14",
  PS14: "M15",
  PS16: "STAR",
  PS17: "STAR",
  FNM: "DCI",
  P15A: "DCI",
  G99: "6ED",
  JGP: "USG",
  PWOR: "STAR",
};

/** Scryfall icon code -> catalog symbol code (from data/set/alias.yml). */
const SET_SYMBOL_ALIASES = {
  ARENA: "MTGA",
  PARL: "DCI",
  PMTG2: "DEFAULT",
  PMEI: "STAR",
  CON: "CONF",
};

const COMPLETION_TO_VECTOR_RARITY = {
  common: "C",
  uncommon: "U",
  rare: "R",
  mythic: "M",
};

export function mtgVectorsSymbolCode(setCode) {
  const normalized = String(setCode || "").trim().toUpperCase();
  if (!normalized || normalized === "ALL") {
    return null;
  }
  const routed = SET_SYMBOL_ROUTES[normalized] || normalized;
  return SET_SYMBOL_ALIASES[routed] || routed;
}

export function completionRarityToVectorCode(completionRarity) {
  return COMPLETION_TO_VECTOR_RARITY[completionRarity] || "C";
}

export function mtgVectorsSetIconUri(setCode, completionRarity = "common") {
  const symbolCode = mtgVectorsSymbolCode(setCode);
  if (!symbolCode) {
    return null;
  }
  const vectorRarity = completionRarityToVectorCode(completionRarity);
  return `${MTG_VECTORS_CDN}/${symbolCode}/${vectorRarity}.svg`;
}
