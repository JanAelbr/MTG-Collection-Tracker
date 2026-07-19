import { COLLECTION_RARITY_LABELS } from "./collectionRarities";
import { formatEuro } from "./format";
import { valueForStrategy } from "./priceStrategies";

export function formatPowerToughness(card) {
  const power = card?.power;
  const toughness = card?.toughness;
  if (!power && !toughness) {
    return "—";
  }
  return `${power ?? "—"}/${toughness ?? "—"}`;
}

export function formatRarityLabel(rarity) {
  const key = String(rarity || "").trim().toLowerCase();
  if (!key) {
    return "—";
  }
  return COLLECTION_RARITY_LABELS[key] || key;
}

export function formatTypeLabel(card) {
  const cardType = String(card?.cardType || "").trim();
  if (cardType) {
    return cardType.charAt(0).toUpperCase() + cardType.slice(1);
  }
  const typeLine = String(card?.typeLine || "").trim();
  if (!typeLine) {
    return "—";
  }
  const primary = typeLine.split("—")[0]?.trim();
  return primary || typeLine;
}

export function displayCardValue(card, strategyId) {
  const value = valueForStrategy(card, strategyId);
  if (value == null) {
    return "—";
  }
  return formatEuro(value);
}
