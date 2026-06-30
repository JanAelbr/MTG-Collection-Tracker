const GALLERY_COMMANDER_COUNT = 2;
const GALLERY_TOP_CARD_COUNT = 4;

export const HERO_TOP_CARD_COUNT = 5;
export const GALLERY_SORT_KEY = "reportDeckGallerySort";
export const DECK_CARDS_VIEW_KEY = "reportDeckCardsView";

export function getStoredGallerySort() {
  const stored = localStorage.getItem(GALLERY_SORT_KEY);
  return stored === "value" ? "value" : "year";
}

export function getStoredDeckCardsView() {
  return localStorage.getItem(DECK_CARDS_VIEW_KEY) === "table" ? "table" : "images";
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

export function sortDecksForGallery(decks, pages, sortBy) {
  return [...decks].sort((left, right) => {
    if (sortBy === "value") {
      const leftValue = pages[String(left.id)]?.current;
      const rightValue = pages[String(right.id)]?.current;
      const leftNumber = leftValue == null || Number.isNaN(leftValue) ? -Infinity : leftValue;
      const rightNumber = rightValue == null || Number.isNaN(rightValue) ? -Infinity : rightValue;
      const valueDiff = rightNumber - leftNumber;
      if (valueDiff !== 0) {
        return valueDiff;
      }
    } else {
      const leftYear = Number(left.releaseYear) || 9999;
      const rightYear = Number(right.releaseYear) || 9999;
      const yearDiff = leftYear - rightYear;
      if (yearDiff !== 0) {
        return yearDiff;
      }
    }
    return String(left.name).localeCompare(String(right.name));
  });
}

export function getGalleryCommanders(cards) {
  return getCommanderCards(cards).slice(0, GALLERY_COMMANDER_COUNT);
}

export function getGalleryHighlights(cards) {
  return getTopValueCards(cards, GALLERY_TOP_CARD_COUNT);
}
