const GALLERY_COMMANDER_COUNT = 2;
const GALLERY_TOP_CARD_COUNT = 4;

export const HERO_TOP_CARD_COUNT = 5;
export const GALLERY_SORT_KEY = "reportDeckGallerySort";
export const DECK_CARDS_VIEW_KEY = "reportDeckCardsView";
export const DECK_IMAGES_CARD_SCALE_KEY = "deckImagesCardScale";
export const DECK_STACKS_CARD_SCALE_KEY = "deckStacksCardScale";
export const DECK_CARD_SCALE_OPTIONS = [75, 100, 125, 150, 175, 200, 225, 250];
export const DECK_COLOR_ORDER = ["W", "U", "B", "R", "G"];

export function getStoredGallerySort() {
  const stored = localStorage.getItem(GALLERY_SORT_KEY);
  return stored === "value" ? "value" : "year";
}

export function getStoredDeckCardsView() {
  const stored = localStorage.getItem(DECK_CARDS_VIEW_KEY);
  if (stored === "top") {
    return "overview";
  }
  if (
    stored === "table"
    || stored === "stacks"
    || stored === "overview"
    || stored === "power"
    || stored === "images"
  ) {
    return stored;
  }
  return "images";
}

function normalizeDeckCardScale(value, fallback = 100) {
  const parsed = Number(value);
  if (DECK_CARD_SCALE_OPTIONS.includes(parsed)) {
    return parsed;
  }
  return fallback;
}

export function getStoredDeckCardScale(view, fallback = 100) {
  const key = view === "stacks" ? DECK_STACKS_CARD_SCALE_KEY : DECK_IMAGES_CARD_SCALE_KEY;
  const stored = localStorage.getItem(key);
  if (stored == null) {
    return fallback;
  }
  return normalizeDeckCardScale(stored, fallback);
}

export function setStoredDeckCardScale(view, scale) {
  const key = view === "stacks" ? DECK_STACKS_CARD_SCALE_KEY : DECK_IMAGES_CARD_SCALE_KEY;
  localStorage.setItem(key, String(normalizeDeckCardScale(scale)));
}

export function deckCardImageUri(card) {
  return card?.imageUri || card?.image_uri || "";
}

export function getCommanderCards(cards) {
  return (cards || []).filter(
    (card) => card.section === "commander" && deckCardImageUri(card),
  );
}

export function getTopValueCards(cards, limit, excludeCommanders = true) {
  let pool = (cards || []).filter(
    (card) => card.inCatalog && deckCardImageUri(card) && card.currentValue != null,
  );
  if (excludeCommanders) {
    pool = pool.filter((card) => card.section !== "commander");
  }
  return [...pool]
    .sort((left, right) => (right.currentValue || 0) - (left.currentValue || 0))
    .slice(0, limit);
}

export function deckPreviewCards(deck, pages) {
  const stats = pages?.[String(deck?.id)] || {};
  if (Array.isArray(stats.cards) && stats.cards.length) {
    return stats.cards;
  }
  return stats.previewCards || [];
}

export function deckCommandersFromPages(deck, pages) {
  return (deckPreviewCards(deck, pages) || []).filter(
    (card) => String(card?.section || "") === "commander",
  );
}

/** WUBRG-sorted color identity for a deck's commanders (empty = colorless). */
export function deckColorIdentityFromPages(deck, pages) {
  const order = "WUBRG";
  const colors = new Set();
  for (const card of deckCommandersFromPages(deck, pages)) {
    const identity = card.colorIdentity?.length
      ? card.colorIdentity
      : (card.colors || []);
    for (const color of identity) {
      if (order.includes(color)) {
        colors.add(color);
      }
    }
  }
  return [...colors].sort((a, b) => order.indexOf(a) - order.indexOf(b));
}

/** Primary colour bucket for gallery separators: W/U/B/R/G or C. */
export function deckPrimaryColor(identity) {
  if (!identity?.length) {
    return "C";
  }
  return identity[0];
}

function colorIdentityRank(identity) {
  const colors = identity || [];
  if (!colors.length) {
    // Colorless after all coloured identities.
    return 90000;
  }
  const primary = DECK_COLOR_ORDER.indexOf(colors[0]);
  const mask = colors.reduce((value, color) => {
    const index = DECK_COLOR_ORDER.indexOf(color);
    return index >= 0 ? value | (1 << index) : value;
  }, 0);
  // Mono → dual → triple → …, then WUBRG within each band.
  return colors.length * 10000 + primary * 100 + mask;
}

function compareColorIdentities(left, right) {
  const rankDiff = colorIdentityRank(left) - colorIdentityRank(right);
  if (rankDiff !== 0) {
    return rankDiff;
  }
  return (left || []).join("").localeCompare((right || []).join(""));
}

function deckGalleryColorGroup(identity) {
  const colors = identity || [];
  if (!colors.length) {
    return { key: "C", colors: [] };
  }
  return { key: colors.join(""), colors };
}

/** Favourites first, then mono → dual → triple… (WUBRG within each), colorless last. */
export function sortDecksForGallery(decks, pages, _sortBy = "color") {
  return [...decks].sort((left, right) => {
    const leftFavorite = left?.favorite ? 0 : 1;
    const rightFavorite = right?.favorite ? 0 : 1;
    if (leftFavorite !== rightFavorite) {
      return leftFavorite - rightFavorite;
    }
    const leftIdentity = deckColorIdentityFromPages(left, pages);
    const rightIdentity = deckColorIdentityFromPages(right, pages);
    const identityDiff = compareColorIdentities(leftIdentity, rightIdentity);
    if (identityDiff !== 0) {
      return identityDiff;
    }
    return String(left.name || "").localeCompare(String(right.name || ""));
  });
}

function deckSearchHaystack(deck, pages) {
  const parts = [
    deck?.name,
    deck?.label,
    deck?.slug,
  ];
  for (const card of deckCommandersFromPages(deck, pages)) {
    parts.push(card.cardName, card.card_name, card.name);
  }
  return parts.filter(Boolean).join(" ").toLowerCase();
}

/** Filter gallery decks by name / label / commander name substring. */
export function filterDecksForGallery(decks, pages, query) {
  const needle = String(query || "").trim().toLowerCase();
  if (!needle) {
    return decks;
  }
  return (decks || []).filter((deck) => deckSearchHaystack(deck, pages).includes(needle));
}

/**
 * Flat gallery rows: decks, favourite/colour dividers, and colour-pip markers
 * beside each colour group (mirrors set browser favourites + year markers).
 */
export function buildDeckGalleryItems(decks, pages, query = "") {
  const sorted = filterDecksForGallery(
    sortDecksForGallery(decks, pages),
    pages,
    query,
  );
  const favorites = sorted.filter((deck) => Boolean(deck.favorite));
  const others = sorted.filter((deck) => !deck.favorite);
  const items = [];

  for (const deck of favorites) {
    items.push({ type: "deck", deck, key: `deck-${deck.id}` });
  }
  if (favorites.length && others.length) {
    items.push({
      type: "separator",
      key: "favorites-separator",
      ariaLabel: "Favourite decks",
    });
  }

  let previousGroup = null;
  for (const deck of others) {
    const identity = deckColorIdentityFromPages(deck, pages);
    const group = deckGalleryColorGroup(identity);
    if (group.key !== previousGroup) {
      if (previousGroup != null) {
        items.push({
          type: "separator",
          key: `color-sep-${previousGroup}-${group.key}`,
          ariaLabel: group.key,
        });
      }
      items.push({
        type: "color",
        colors: group.colors,
        key: `color-${group.key}`,
      });
      previousGroup = group.key;
    }
    items.push({ type: "deck", deck, key: `deck-${deck.id}` });
  }

  return items;
}

export function getGalleryCommanders(cards) {
  return getCommanderCards(cards).slice(0, GALLERY_COMMANDER_COUNT);
}

export function getGalleryHighlights(cards) {
  return getTopValueCards(cards, GALLERY_TOP_CARD_COUNT);
}
