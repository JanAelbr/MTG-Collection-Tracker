export const FINISH_NONFOIL = 0;
export const FINISH_FOIL = 1;
export const FINISH_ETCHED = 2;

export function normalizeFinish(value, defaultFinish = FINISH_NONFOIL) {
  if (value === null || value === undefined || value === "") {
    return defaultFinish;
  }
  const numeric = Number(value);
  if (Number.isInteger(numeric) && numeric >= 0 && numeric <= 2) {
    return numeric;
  }
  const text = String(value).trim().toLowerCase();
  if (text === "foil" || text === "1") {
    return FINISH_FOIL;
  }
  if (text === "etched" || text === "2") {
    return FINISH_ETCHED;
  }
  return FINISH_NONFOIL;
}

export function finishLabel(finish) {
  switch (normalizeFinish(finish)) {
    case FINISH_FOIL:
      return "Foil";
    case FINISH_ETCHED:
      return "Etched";
    default:
      return "Non-foil";
  }
}

export function cardFinish(card) {
  if (card?.finish !== undefined && card?.finish !== null && card?.finish !== "") {
    return normalizeFinish(card.finish);
  }
  return normalizeFinish(card?.foil);
}

export function cardRouteQuery(finish) {
  const normalized = normalizeFinish(finish);
  return normalized === FINISH_NONFOIL ? {} : { finish: String(normalized) };
}

export function displayNameWithFinish(name, finish) {
  const base = String(name || "").trim();
  if (!base) {
    return "";
  }
  const normalized = normalizeFinish(finish);
  if (normalized === FINISH_FOIL) {
    return `✨ ${base}`;
  }
  if (normalized === FINISH_ETCHED) {
    return `${base} (Etched)`;
  }
  return base;
}

export function cardDisplayName(card, finish = null) {
  const name = card?.name || card?.cardName || "";
  const resolvedFinish = finish == null ? cardFinish(card) : normalizeFinish(finish);
  return displayNameWithFinish(name, resolvedFinish);
}

export function marketValueForFinish(card, finish) {
  const normalized = normalizeFinish(finish);
  if (normalized === FINISH_FOIL) {
    return card?.currentValueFoil ?? card?.marketValueFoil ?? card?.market_value_foil;
  }
  if (normalized === FINISH_ETCHED) {
    return card?.currentValueEtched ?? card?.marketValueEtched ?? card?.market_value_etched;
  }
  return card?.currentValueNonfoil ?? card?.marketValue ?? card?.market_value;
}

export function finishHasPricing(card, finish) {
  if (!card) {
    return false;
  }
  const normalized = normalizeFinish(finish);
  const stored = marketValueForFinish(card, finish);
  if (stored != null && Number(stored) > 0) {
    return true;
  }
  const finishData = card.finishes?.[String(normalized)];
  const guide = finishData?.guidePrices;
  if (guide && Object.values(guide).some((value) => value != null && Number(value) > 0)) {
    return true;
  }
  if (normalizeFinish(card.finish ?? card.foil) === normalized) {
    const current = card.currentValue ?? card.current_value;
    if (current != null && Number(current) > 0) {
      return true;
    }
  }
  const finishValues = card.finishValues;
  if (finishValues?.[normalized] != null && Number(finishValues[normalized]) > 0) {
    return true;
  }
  return false;
}

export function hasFinish(card, finish) {
  return finishHasPricing(card, finish);
}

export function cardHasCatalogFinish(card, finish) {
  if (!card) {
    return false;
  }
  const normalized = normalizeFinish(finish);
  if (normalized === FINISH_NONFOIL) {
    return Boolean(card.hasNonfoil ?? card.has_nonfoil);
  }
  if (normalized === FINISH_FOIL) {
    return Boolean(card.hasFoil ?? card.has_foil);
  }
  if (normalized === FINISH_ETCHED) {
    return Boolean(card.hasEtched ?? card.has_etched);
  }
  return false;
}

export function isFinishOwnedOnCard(card, finish) {
  if (!card) {
    return false;
  }
  const normalized = normalizeFinish(finish);
  const finishInfo = card.finishes?.[String(normalized)] ?? card.finishes?.[normalized];
  if (finishInfo) {
    if (Array.isArray(finishInfo.locations) && finishInfo.locations.length > 0) {
      return true;
    }
    if (finishInfo.owned) {
      return true;
    }
    if (finishInfo.purchaseValue != null) {
      return true;
    }
  }
  if (normalized === FINISH_NONFOIL && card.ownedNonfoil) {
    return true;
  }
  if (normalized === FINISH_FOIL && card.ownedFoil) {
    return true;
  }
  if (normalized === FINISH_ETCHED && card.ownedEtched) {
    return true;
  }
  if (normalized === FINISH_NONFOIL && card.purchaseValueNonfoil != null) {
    return true;
  }
  if (normalized === FINISH_FOIL && card.purchaseValueFoil != null) {
    return true;
  }
  if (normalized === FINISH_ETCHED && card.purchaseValueEtched != null) {
    return true;
  }
  if (normalizeFinish(card.finish ?? card.foil) === normalized && card.owned) {
    return true;
  }
  return false;
}

export function canManageFinish(card, finish) {
  return (
    hasFinish(card, finish)
    || isFinishOwnedOnCard(card, finish)
    || cardHasCatalogFinish(card, finish)
  );
}

export function cardSupportsNonfoilFoilToggle(card) {
  if (!card) {
    return false;
  }
  const available = (card.availableFinishes || [])
    .map((value) => normalizeFinish(value));
  if (available.includes(FINISH_NONFOIL) && available.includes(FINISH_FOIL)) {
    return true;
  }
  return canManageFinish(card, FINISH_NONFOIL) && canManageFinish(card, FINISH_FOIL);
}
