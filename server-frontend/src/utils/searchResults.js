import { COLLECTION_RARITY_LABELS } from "./collectionRarities";
import { COLLECTION_TYPE_LABELS, COLLECTION_TYPE_ORDER } from "./collectionTypes";
import { DECK_COLOR_LABELS, DECK_COLOR_ORDER } from "./deckCards";
import { formatCardRoleLabel } from "./deckPower";
import { formatEuro } from "./format";
import { galleryPricePair } from "./priceStrategies";

export const SEARCH_GROUP_BY_OPTIONS = [
  { value: "none", label: "None" },
  { value: "type", label: "Type" },
  { value: "role", label: "Role" },
  { value: "colorIdentity", label: "Color identity" },
  { value: "set", label: "Set" },
];

export function normalizeSearchGroupBy(value) {
  const key = String(value || "").trim();
  return SEARCH_GROUP_BY_OPTIONS.some((option) => option.value === key) ? key : "none";
}

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

/** Gallery-style value: lowest listing, then trend when higher (or a single number). */
export function displayCardValue(card) {
  const { low, high } = galleryPricePair(card);
  if (low == null) {
    return "—";
  }
  if (high == null) {
    return formatEuro(low);
  }
  return `${formatEuro(low)} ~ ${formatEuro(high)}`;
}

function colorIdentityKey(card) {
  const raw = card?.colorIdentity?.length
    ? card.colorIdentity
    : (card?.colors || []);
  const pips = [...new Set(
    (raw || [])
      .map((color) => String(color || "").toUpperCase())
      .filter((color) => DECK_COLOR_ORDER.includes(color) && color !== "C"),
  )].sort((left, right) => DECK_COLOR_ORDER.indexOf(left) - DECK_COLOR_ORDER.indexOf(right));
  return pips.length ? pips.join("") : "C";
}

function colorIdentityLabel(key) {
  if (!key || key === "C") {
    return DECK_COLOR_LABELS.C;
  }
  return key
    .split("")
    .map((pip) => DECK_COLOR_LABELS[pip] || pip)
    .join(" / ");
}

function typeGroupKey(card) {
  const cardType = String(card?.cardType || "").trim().toLowerCase();
  if (cardType) {
    return cardType;
  }
  const typeLine = String(card?.typeLine || "").toLowerCase();
  for (const type of COLLECTION_TYPE_ORDER) {
    if (typeLine.includes(type)) {
      return type;
    }
  }
  return "other";
}

function typeGroupLabel(key) {
  return COLLECTION_TYPE_LABELS[key] || formatTypeLabel({ cardType: key }) || "Other";
}

function roleGroupKey(card) {
  const roles = Array.isArray(card?.roles) ? card.roles : [];
  const first = roles.map((role) => String(role || "").trim()).find(Boolean);
  return first || "";
}

function setGroupKey(card) {
  return String(card?.setCode || "").trim().toUpperCase() || "—";
}

function groupMeta(groupBy, card, setLabelFor) {
  switch (groupBy) {
    case "type": {
      const key = typeGroupKey(card);
      return { key, label: typeGroupLabel(key) };
    }
    case "role": {
      const key = roleGroupKey(card);
      return {
        key: key || "__none__",
        label: key ? formatCardRoleLabel(key) : "No role",
      };
    }
    case "colorIdentity": {
      const key = colorIdentityKey(card);
      return { key, label: colorIdentityLabel(key) };
    }
    case "set": {
      const key = setGroupKey(card);
      const label = typeof setLabelFor === "function"
        ? (setLabelFor(key) || key)
        : key;
      return { key, label };
    }
    default:
      return { key: "all", label: "All" };
  }
}

function compareGroupKeys(groupBy, left, right) {
  if (groupBy === "type") {
    const leftIndex = COLLECTION_TYPE_ORDER.indexOf(left);
    const rightIndex = COLLECTION_TYPE_ORDER.indexOf(right);
    if (leftIndex !== -1 || rightIndex !== -1) {
      return (leftIndex === -1 ? 99 : leftIndex) - (rightIndex === -1 ? 99 : rightIndex);
    }
  }
  if (groupBy === "colorIdentity") {
    const rank = (key) => {
      if (key === "C") {
        return 99;
      }
      return key.length * 10 + DECK_COLOR_ORDER.indexOf(key[0] || "C");
    };
    const byRank = rank(left) - rank(right);
    if (byRank) {
      return byRank;
    }
  }
  if (groupBy === "role" && (left === "__none__" || right === "__none__")) {
    if (left === "__none__") {
      return 1;
    }
    if (right === "__none__") {
      return -1;
    }
  }
  return String(left).localeCompare(String(right), undefined, { sensitivity: "base" });
}

/**
 * Group search result cards for display.
 * @returns {{ key: string, label: string, cards: object[] }[]}
 */
export function groupSearchCards(cards = [], groupBy = "none", { setLabelFor } = {}) {
  const mode = normalizeSearchGroupBy(groupBy);
  if (mode === "none") {
    return [{ key: "all", label: "All", cards: [...(cards || [])] }];
  }
  const buckets = new Map();
  for (const card of cards || []) {
    const { key, label } = groupMeta(mode, card, setLabelFor);
    if (!buckets.has(key)) {
      buckets.set(key, { key, label, cards: [] });
    }
    buckets.get(key).cards.push(card);
  }
  return [...buckets.values()].sort((left, right) => compareGroupKeys(mode, left.key, right.key));
}
