import { isEffectivelyOwned } from "../composables/cardContextMenu";
import { cardMatchesColorFilter } from "./deckCards";
import { COLLECTION_RARITY_FILTER_VALUES } from "./collectionRarities";

export function cardMatchesCollectionTypeFilter(card, typeFilter) {
  if (!typeFilter || typeFilter === "all") {
    return true;
  }
  const cardType = String(card?.cardType || "").toLowerCase();
  return cardType === String(typeFilter).toLowerCase();
}

export function parseOptionalNumber(value) {
  const text = String(value ?? "").trim();
  if (!text) {
    return null;
  }
  const parsed = Number(text);
  return Number.isFinite(parsed) ? parsed : null;
}

export function parseNumericStat(value) {
  const text = String(value ?? "").trim();
  if (!text || text === "*") {
    return null;
  }
  const parsed = Number(text);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

export function cardMatchesCollectionRarityFilter(card, rarityFilter) {
  if (!rarityFilter || rarityFilter === "all") {
    return true;
  }
  const rarity = String(card?.rarity || "").toLowerCase();
  return rarity === String(rarityFilter).toLowerCase();
}

export function cardMatchesCollectionCmcFilter(card, { cmcMin = null, cmcMax = null } = {}) {
  const cmc = Number(card?.cmc);
  const resolved = Number.isFinite(cmc) ? cmc : 0;
  if (cmcMin != null && resolved < cmcMin) {
    return false;
  }
  if (cmcMax != null && resolved > cmcMax) {
    return false;
  }
  return true;
}

export function cardMatchesCollectionPriceFilter(card, { priceMin = null, priceMax = null } = {}) {
  if (priceMin == null && priceMax == null) {
    return true;
  }
  const raw = card?.currentValue;
  if (raw == null || raw === "") {
    return false;
  }
  const value = Number(raw);
  if (!Number.isFinite(value)) {
    return false;
  }
  if (priceMin != null && value < priceMin) {
    return false;
  }
  if (priceMax != null && value > priceMax) {
    return false;
  }
  return true;
}

export function cardMatchesCollectionStatFilter(
  card,
  { powerMin = null, toughnessMin = null } = {},
) {
  if (powerMin == null && toughnessMin == null) {
    return true;
  }
  const power = parseNumericStat(card?.power);
  const toughness = parseNumericStat(card?.toughness);
  if (powerMin != null && (power == null || power < powerMin)) {
    return false;
  }
  if (toughnessMin != null && (toughness == null || toughness < toughnessMin)) {
    return false;
  }
  return true;
}

export function cardMatchesCollectionStorageFilter(card, storageFilters) {
  if (!storageFilters?.length) {
    return true;
  }
  const locations = card?.locations || [];
  const slugs = new Set(
    locations
      .map((location) => String(location?.slug || "").trim())
      .filter(Boolean),
  );
  if (!slugs.size) {
    return false;
  }
  return storageFilters.some((slug) => slugs.has(slug));
}

export function cardMatchesSearchQuery(card, searchQuery) {
  const query = String(searchQuery || "").trim().toLowerCase();
  if (!query) {
    return true;
  }
  const number = String(card?.collectorNumber ?? "").toLowerCase();
  const padded = number.padStart(3, "0");
  const name = String(card?.name ?? "").toLowerCase();
  const oracleText = String(card?.oracleText ?? "").toLowerCase();
  return (
    number.includes(query)
    || padded.includes(query)
    || name.includes(query)
    || oracleText.includes(query)
    || `#${number}`.includes(query)
    || `#${padded}`.includes(query)
  );
}

export function filterCollectionCards(
  cards,
  {
    setCode = "All",
    artStyle = "",
    ownedFilter = "all",
    foilFilter = "all",
    typeFilter = "all",
    colorFilters = [],
    searchQuery = "",
    rarityFilter = "all",
    cmcMin = null,
    cmcMax = null,
    priceMin = null,
    priceMax = null,
    powerMin = null,
    toughnessMin = null,
    storageFilters = [],
  } = {},
) {
  let result = cards || [];

  if (setCode && String(setCode).toLowerCase() !== "all") {
    const normalized = String(setCode).toUpperCase();
    result = result.filter((card) => String(card.setCode).toUpperCase() === normalized);
  }
  if (artStyle) {
    result = result.filter((card) => card.artStyle === artStyle);
  }
  if (foilFilter === "nonfoil") {
    result = result.filter((card) => (card.finish ?? card.foil) === 0);
  } else if (foilFilter === "foil") {
    result = result.filter((card) => (card.finish ?? card.foil) === 1);
  } else if (foilFilter === "etched") {
    result = result.filter((card) => (card.finish ?? card.foil) === 2);
  }
  if (ownedFilter === "owned") {
    result = result.filter((card) => isEffectivelyOwned(card));
  } else if (ownedFilter === "unowned") {
    result = result.filter((card) => !isEffectivelyOwned(card));
  }
  if (typeFilter && typeFilter !== "all") {
    result = result.filter((card) => cardMatchesCollectionTypeFilter(card, typeFilter));
  }
  if (colorFilters?.length) {
    result = result.filter((card) => cardMatchesColorFilter(card, colorFilters));
  }
  if (rarityFilter && rarityFilter !== "all") {
    result = result.filter((card) => cardMatchesCollectionRarityFilter(card, rarityFilter));
  }
  if (cmcMin != null || cmcMax != null) {
    result = result.filter((card) => cardMatchesCollectionCmcFilter(card, { cmcMin, cmcMax }));
  }
  if (priceMin != null || priceMax != null) {
    result = result.filter((card) => cardMatchesCollectionPriceFilter(card, { priceMin, priceMax }));
  }
  if (powerMin != null || toughnessMin != null) {
    result = result.filter((card) => cardMatchesCollectionStatFilter(card, { powerMin, toughnessMin }));
  }
  if (storageFilters?.length) {
    result = result.filter((card) => cardMatchesCollectionStorageFilter(card, storageFilters));
  }
  if (searchQuery) {
    result = result.filter((card) => cardMatchesSearchQuery(card, searchQuery));
  }

  return result;
}

export { COLLECTION_RARITY_FILTER_VALUES };
