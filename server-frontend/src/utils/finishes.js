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

export function hasFinish(card, finish) {
  const normalized = normalizeFinish(finish);
  if (normalized === FINISH_FOIL) {
    return Boolean(card?.hasFoil ?? card?.has_foil);
  }
  if (normalized === FINISH_ETCHED) {
    return Boolean(card?.hasEtched ?? card?.has_etched);
  }
  return Boolean(card?.hasNonfoil ?? card?.has_nonfoil);
}
