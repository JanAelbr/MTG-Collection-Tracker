export const COLLECTION_RARITY_ORDER = [
  "common",
  "uncommon",
  "rare",
  "mythic",
  "special",
  "bonus",
];

export const COLLECTION_RARITY_LABELS = {
  common: "Common",
  uncommon: "Uncommon",
  rare: "Rare",
  mythic: "Mythic",
  special: "Special",
  bonus: "Bonus",
};

export const COLLECTION_RARITY_FILTER_VALUES = new Set(["all", ...COLLECTION_RARITY_ORDER]);
