import { COLLECTION_TYPE_ORDER } from "./collectionTypes";
import { cardTypeGroup } from "./deckCards";

export const POWER_COMPONENTS = [
  { id: "ramp", label: "Ramp", showCount: true },
  { id: "draw", label: "Card draw", showCount: true },
  { id: "interaction", label: "Interaction", showCount: true },
  { id: "tutors", label: "Tutors", showCount: true },
  { id: "fastMana", label: "Fast mana", showCount: true },
  { id: "gameChangers", label: "Game changers", showCount: true },
  { id: "comboDensity", label: "Combo pieces", showCount: true },
];

/** Snake_case role ids from the API → short table labels. */
export const CARD_ROLE_LABELS = {
  ramp: "Ramp",
  draw: "Draw",
  removal: "Removal",
  interaction: "Interaction",
  protection: "Protection",
  tutor: "Tutor",
  fast_mana: "Fast mana",
  game_changer: "Game changer",
  combo_piece: "Combo",
  synergy: "Synergy",
  recursion: "Recursion",
  reanimate: "Reanimate",
  equipment: "Equipment",
  aura: "Aura",
  graveyard_hate: "GY hate",
  extra_turn: "Extra turn",
  mass_land_destruction: "MLD",
  board_wipe: "Board wipe",
  bounce: "Bounce",
  counterspell: "Counter",
  land_destruction: "LD",
  mill: "Mill",
  discard: "Discard",
  sac_outlet: "Sac outlet",
  fog: "Fog",
};

const HIDDEN_TABLE_ROLES = new Set(["land"]);

export function formatCardRoleLabel(role) {
  const key = String(role || "").trim();
  if (!key) {
    return "";
  }
  return CARD_ROLE_LABELS[key] || key.replace(/_/g, " ");
}

/** Roles shown in the deck cards table (skip redundant land). */
export function formatCardRoles(roles = []) {
  return (roles || [])
    .filter((role) => role && !HIDDEN_TABLE_ROLES.has(String(role)))
    .map(formatCardRoleLabel)
    .filter(Boolean);
}

export const EXCLUDE_CATEGORY_OPTIONS = [
  { id: "extra_turn", label: "Extra turns" },
  { id: "mass_land_destruction", label: "Mass land destruction" },
];

export function bracketLabel(bracket) {
  const value = Number(bracket) || 1;
  return `Bracket ${value}`;
}

export function bracketDescription(bracket) {
  const descriptions = {
    1: "Exhibition — battlecruiser, theme-first",
    2: "Core — precon strength",
    3: "Upgraded — strong synergies, limited tutors",
    4: "Optimized — fast mana and tutors",
    5: "cEDH — highly tuned combo potential",
  };
  return descriptions[Number(bracket) || 1] || descriptions[1];
}

export function confidenceLabel(confidence) {
  const labels = {
    low: "Low confidence",
    medium: "Medium confidence",
    high: "High confidence",
  };
  return labels[String(confidence || "").toLowerCase()] || labels.medium;
}

export function componentScoreClass(score) {
  const value = Number(score) || 0;
  if (value >= 80) return "power-score-high";
  if (value >= 55) return "power-score-mid";
  return "power-score-low";
}

export function formatComponentCount(componentId, counts = {}) {
  const value = Number(counts[componentId]) || 0;
  return value === 1 ? "1 card" : `${value} cards`;
}

export function powerCardRoute(card, deckId = "") {
  if (!card?.setCode || !card?.collectorNumber) {
    return null;
  }
  const query = {};
  if (card.finish != null) {
    query.finish = String(card.finish);
  }
  if (deckId) {
    query.deck = String(deckId);
  }
  return {
    name: "card",
    params: {
      setCode: card.setCode,
      collectorNumber: card.collectorNumber,
    },
    query,
  };
}

export function groupProposalCards(cards = []) {
  const owned = [];
  const suggested = [];
  const basicLands = [];
  for (const card of cards) {
    if (card.infiniteBasic) {
      basicLands.push(card);
      continue;
    }
    if (card.suggested) {
      suggested.push(card);
    } else {
      owned.push(card);
    }
  }
  return { owned, suggested, basicLands };
}

export const PROPOSAL_SLOT_ORDER = [
  "lands",
  "ramp",
  "draw",
  "removal",
  "protection",
  "synergy",
  "flex",
];

function sortProposalCardsByName(cards) {
  return [...cards].sort((left, right) =>
    String(left.name || "").localeCompare(String(right.name || "")),
  );
}

function splitProposalCards(cards = []) {
  const basicLandSummary = [];
  const tracked = [];
  for (const card of cards) {
    if (card.infiniteBasic) {
      basicLandSummary.push({ name: card.name, qty: card.qty || 1 });
      continue;
    }
    tracked.push(card);
  }
  return { basicLandSummary, tracked };
}

export function groupProposalBySlot(cards = []) {
  const { basicLandSummary, tracked } = splitProposalCards(cards);
  const groups = new Map();

  for (const card of tracked) {
    const slot = card.slot || "flex";
    if (!groups.has(slot)) {
      groups.set(slot, []);
    }
    groups.get(slot).push(card);
  }

  const slotGroups = [];
  for (const slot of PROPOSAL_SLOT_ORDER) {
    const slotCards = groups.get(slot);
    if (!slotCards?.length) {
      continue;
    }
    slotGroups.push({ slot, cards: sortProposalCardsByName(slotCards) });
    groups.delete(slot);
  }
  for (const [slot, slotCards] of groups) {
    slotGroups.push({ slot, cards: sortProposalCardsByName(slotCards) });
  }

  return { slotGroups, basicLandSummary };
}

export function groupProposalByType(cards = []) {
  const { basicLandSummary, tracked } = splitProposalCards(cards);
  const groups = new Map();

  for (const card of tracked) {
    const type = cardTypeGroup(card) || "unknown";
    if (!groups.has(type)) {
      groups.set(type, []);
    }
    groups.get(type).push(card);
  }

  const typeGroups = [];
  for (const type of COLLECTION_TYPE_ORDER) {
    const typeCards = groups.get(type);
    if (!typeCards?.length) {
      continue;
    }
    typeGroups.push({ type, cards: sortProposalCardsByName(typeCards) });
    groups.delete(type);
  }
  if (groups.has("unknown")) {
    typeGroups.push({
      type: "unknown",
      cards: sortProposalCardsByName(groups.get("unknown")),
    });
    groups.delete("unknown");
  }
  for (const [type, typeCards] of groups) {
    typeGroups.push({ type, cards: sortProposalCardsByName(typeCards) });
  }

  return { typeGroups, basicLandSummary };
}

export function formatBasicLandSummary(basicLandSummary = []) {
  if (!basicLandSummary.length) {
    return "";
  }
  const parts = basicLandSummary.map(({ name, qty }) => `${name} ×${qty}`);
  const total = basicLandSummary.reduce((sum, item) => sum + (item.qty || 1), 0);
  return `${parts.join(", ")} (${total} total)`;
}

export function slotLabel(slot) {
  const labels = {
    lands: "Lands",
    ramp: "Ramp",
    draw: "Draw",
    removal: "Removal",
    protection: "Protection",
    synergy: "Synergy",
    flex: "Flex",
  };
  return labels[slot] || slot || "Other";
}
