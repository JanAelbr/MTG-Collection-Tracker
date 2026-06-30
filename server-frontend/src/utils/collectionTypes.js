export const COLLECTION_TYPE_ORDER = [
  "creature",
  "planeswalker",
  "enchantment",
  "artifact",
  "instant",
  "sorcery",
  "land",
  "battle",
  "kindred",
  "tribal",
];

export const COLLECTION_TYPE_LABELS = {
  creature: "Creature",
  planeswalker: "Planeswalker",
  enchantment: "Enchantment",
  artifact: "Artifact",
  instant: "Instant",
  sorcery: "Sorcery",
  land: "Land",
  battle: "Battle",
  kindred: "Kindred",
  tribal: "Tribal",
};

export const COLLECTION_TYPE_FILTER_VALUES = new Set(["all", ...COLLECTION_TYPE_ORDER]);
