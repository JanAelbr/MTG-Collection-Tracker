import { isEffectivelyOwned } from "../composables/cardContextMenu";
import { cardMatchesColorFilter } from "./deckCards";

export function cardMatchesCollectionTypeFilter(card, typeFilter) {
  if (!typeFilter || typeFilter === "all") {
    return true;
  }
  const cardType = String(card?.cardType || "").toLowerCase();
  return cardType === String(typeFilter).toLowerCase();
}

export function filterCollectionCards(
  cards,
  {
    setCode = "All",
    artStyle = "",
    ownedFilter = "all",
    foilFilter = "all",
    typeFilter = "all",
    colorFilters = [],
  } = {},
) {
  let result = cards || [];

  if (setCode && String(setCode).toLowerCase() !== "all") {
    const normalized = String(setCode).toUpperCase();
    result = result.filter((card) => String(card.setCode).toUpperCase() === normalized);
  }
  if (artStyle) {
    result = result.filter((card) => card.artStyle === artStyle);
  }
  if (foilFilter === "nonfoil") {
    result = result.filter((card) => (card.finish ?? card.foil) === 0);
  } else if (foilFilter === "foil") {
    result = result.filter((card) => (card.finish ?? card.foil) === 1);
  } else if (foilFilter === "etched") {
    result = result.filter((card) => (card.finish ?? card.foil) === 2);
  }
  if (ownedFilter === "owned") {
    result = result.filter((card) => isEffectivelyOwned(card));
  } else if (ownedFilter === "unowned") {
    result = result.filter((card) => !isEffectivelyOwned(card));
  }
  if (typeFilter && typeFilter !== "all") {
    result = result.filter((card) => cardMatchesCollectionTypeFilter(card, typeFilter));
  }
  if (colorFilters?.length) {
    result = result.filter((card) => cardMatchesColorFilter(card, colorFilters));
  }

  return result;
}
