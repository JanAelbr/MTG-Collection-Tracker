import { COLLECTION_RARITY_LABELS, COLLECTION_RARITY_ORDER } from "./collectionRarities";
import { COLLECTION_TYPE_LABELS, COLLECTION_TYPE_ORDER } from "./collectionTypes";
import { colorCombinationLabel, DECK_COLOR_ORDER } from "./deckCards";
import { formatCardRoleLabel } from "./deckPower";
import { formatEuro } from "./format";
import { galleryPricePair } from "./priceStrategies";

export const SEARCH_GROUP_BY_OPTIONS = [
  { value: "none", label: "None" },
  { value: "type", label: "Type" },
  { value: "subtype", label: "Subtype" },
  { value: "role", label: "Role" },
  { value: "colorIdentity", label: "Color identity" },
  { value: "rarity", label: "Rarity" },
  { value: "set", label: "Set" },
];

export const SEARCH_GROUP_BY_FIELDS = SEARCH_GROUP_BY_OPTIONS.filter(
  (option) => option.value !== "none",
);

const GROUP_BY_FIELD_SET = new Set(SEARCH_GROUP_BY_FIELDS.map((option) => option.value));
const MAX_GROUP_LEVELS = 3;

export function normalizeSearchGroupBy(value) {
  const key = String(value || "").trim();
  if (key === "none" || key === "off" || key === "0" || key === "false") {
    return "none";
  }
  return GROUP_BY_FIELD_SET.has(key) ? key : "none";
}

function normalizeGroupByField(value) {
  const raw = String(value || "").trim();
  if (!raw || raw.toLowerCase() === "none" || raw.toLowerCase() === "off") {
    return "";
  }
  const lower = raw.toLowerCase();
  if (lower === "color" || lower === "coloridentity") {
    return "colorIdentity";
  }
  if (lower === "subtypes" || lower === "sub-type" || lower === "sub_type") {
    return "subtype";
  }
  if (GROUP_BY_FIELD_SET.has(raw)) {
    return raw;
  }
  const match = SEARCH_GROUP_BY_FIELDS.find((option) => option.value.toLowerCase() === lower);
  return match?.value || "";
}

/**
 * Normalize one or more group-by levels (max 3, unique).
 * Accepts `"role"`, `"role,colorIdentity,rarity"`, or `["role", "colorIdentity"]`.
 */
export function normalizeGroupByLevels(value, { emptyDefault = [] } = {}) {
  let parts = [];
  if (Array.isArray(value)) {
    parts = value;
  } else if (value != null && String(value).trim()) {
    parts = String(value).split(/[,+/|]/);
  }
  const levels = [];
  const seen = new Set();
  for (const part of parts) {
    const field = normalizeGroupByField(part);
    if (!field || seen.has(field)) {
      continue;
    }
    seen.add(field);
    levels.push(field);
    if (levels.length >= MAX_GROUP_LEVELS) {
      break;
    }
  }
  return levels.length ? levels : [...emptyDefault];
}

export function formatGroupByLevels(levels = []) {
  const normalized = normalizeGroupByLevels(levels);
  return normalized.length ? normalized.join(",") : "none";
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
  return colorCombinationLabel(key);
}

/** Mana pip letters for a color-identity group key (`"WU"`, `"C"`, …). */
export function colorIdentityPipsFromKey(key) {
  const normalized = String(key || "").trim().toUpperCase();
  if (!normalized || normalized === "C") {
    return [];
  }
  return normalized
    .split("")
    .filter((pip) => DECK_COLOR_ORDER.includes(pip) && pip !== "C");
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

/** Subtype text after the type-line dash (Aura, Equipment, Elf Druid, …). */
export function cardSubtypeLabel(card) {
  const typeLine = String(card?.typeLine || card?.type_line || "").trim();
  if (!typeLine) {
    return "";
  }
  const face = typeLine.split("//")[0]?.trim() || "";
  for (const separator of ["—", "–", " - "]) {
    if (!face.includes(separator)) {
      continue;
    }
    const text = face
      .split(separator)
      .slice(1)
      .join(separator)
      .replace(/,/g, " ")
      .trim()
      .replace(/\s+/g, " ");
    return text;
  }
  return "";
}

function subtypeGroupKey(card) {
  return cardSubtypeLabel(card) || "__none__";
}

function subtypeGroupLabel(key) {
  if (!key || key === "__none__") {
    return "No subtype";
  }
  return key;
}

function roleGroupKey(card) {
  const roles = Array.isArray(card?.roles) ? card.roles : [];
  const first = roles.map((role) => String(role || "").trim()).find(Boolean);
  return first || "";
}

function setGroupKey(card) {
  return String(card?.setCode || "").trim().toUpperCase() || "—";
}

function rarityGroupKey(card) {
  const rarity = String(card?.rarity || "").trim().toLowerCase();
  return rarity || "__none__";
}

function rarityGroupLabel(key) {
  if (!key || key === "__none__") {
    return "Unknown rarity";
  }
  return COLLECTION_RARITY_LABELS[key] || formatRarityLabel(key);
}

function groupMeta(groupBy, card, setLabelFor) {
  switch (groupBy) {
    case "type": {
      const key = typeGroupKey(card);
      return { key, label: typeGroupLabel(key) };
    }
    case "subtype": {
      const key = subtypeGroupKey(card);
      return { key, label: subtypeGroupLabel(key) };
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
    case "rarity": {
      const key = rarityGroupKey(card);
      return { key, label: rarityGroupLabel(key) };
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
  if (groupBy === "rarity") {
    const leftIndex = COLLECTION_RARITY_ORDER.indexOf(left);
    const rightIndex = COLLECTION_RARITY_ORDER.indexOf(right);
    if (left === "__none__" || right === "__none__") {
      if (left === "__none__") {
        return 1;
      }
      if (right === "__none__") {
        return -1;
      }
    }
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
  if (
    (groupBy === "role" || groupBy === "subtype")
    && (left === "__none__" || right === "__none__")
  ) {
    if (left === "__none__") {
      return 1;
    }
    if (right === "__none__") {
      return -1;
    }
  }
  return String(left).localeCompare(String(right), undefined, { sensitivity: "base" });
}

function groupCardsOneLevel(cards, mode, { setLabelFor, pathPrefix = "", depth = 0 } = {}) {
  const buckets = new Map();
  for (const card of cards || []) {
    const { key, label } = groupMeta(mode, card, setLabelFor);
    if (!buckets.has(key)) {
      const path = pathPrefix ? `${pathPrefix}/${mode}:${key}` : `${mode}:${key}`;
      buckets.set(key, {
        key,
        label,
        path,
        groupBy: mode,
        depth,
        cards: [],
        groups: [],
      });
    }
    buckets.get(key).cards.push(card);
  }
  return [...buckets.values()].sort((left, right) => compareGroupKeys(mode, left.key, right.key));
}

function nestGroups(cards, levels, { setLabelFor, pathPrefix = "", depth = 0 } = {}) {
  if (!levels.length) {
    return [];
  }
  const [mode, ...rest] = levels;
  const groups = groupCardsOneLevel(cards, mode, { setLabelFor, pathPrefix, depth });
  if (!rest.length) {
    return groups;
  }
  return groups.map((group) => ({
    ...group,
    groups: nestGroups(group.cards, rest, {
      setLabelFor,
      pathPrefix: group.path,
      depth: depth + 1,
    }),
  }));
}

/**
 * Group cards for display. `groupBy` may be one field or nested levels.
 * @returns {{ key: string, label: string, path: string, groupBy: string, depth: number, cards: object[], groups: object[] }[]}
 */
export function groupSearchCards(cards = [], groupBy = "none", { setLabelFor } = {}) {
  const levels = normalizeGroupByLevels(groupBy, { emptyDefault: [] });
  if (!levels.length) {
    return [{
      key: "all",
      label: "All",
      path: "all",
      groupBy: "none",
      depth: 0,
      cards: [...(cards || [])],
      groups: [],
    }];
  }
  return nestGroups(cards, levels, { setLabelFor });
}

/** Collect every group path in a nested tree (depth-first). */
export function collectGroupPaths(groups = [], out = []) {
  for (const group of groups || []) {
    if (group?.path) {
      out.push(group.path);
    }
    if (group?.groups?.length) {
      collectGroupPaths(group.groups, out);
    }
  }
  return out;
}

/** True when a group has nested child groups. */
export function groupHasChildren(group) {
  return Boolean(group?.groups?.length);
}
