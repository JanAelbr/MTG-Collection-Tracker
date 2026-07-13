export const POWER_COMPONENTS = [
  { id: "ramp", label: "Ramp", showCount: true },
  { id: "draw", label: "Card draw", showCount: true },
  { id: "interaction", label: "Interaction", showCount: true },
  { id: "tutors", label: "Tutors", showCount: true },
  { id: "fastMana", label: "Fast mana", showCount: true },
  { id: "gameChangers", label: "Game changers", showCount: true },
  { id: "comboDensity", label: "Combo pieces", showCount: true },
  { id: "curve", label: "Mana curve", showCount: false },
];

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
  if (componentId === "curve") {
    return "";
  }
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
