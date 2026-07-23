import { normalizeFinish } from "./finishes";

export function favoriteCardKey(setCode, collectorNumber, finish) {
  const set = String(setCode || "").trim().toUpperCase();
  const number = String(collectorNumber ?? "").trim();
  const normalizedFinish = normalizeFinish(finish);
  if (!set || !number) {
    return "";
  }
  return `${set}|${number}|${normalizedFinish}`;
}

export function favoriteArtStyleKey(setCode, artStyle) {
  const set = String(setCode || "").trim().toUpperCase();
  const style = String(artStyle || "").trim();
  if (!set || !style) {
    return "";
  }
  return `${set}|${style}`;
}

export function cardFavoriteKeyFromCard(card, finish = null) {
  if (!card) {
    return "";
  }
  const resolvedFinish = finish == null
    ? (card.finish ?? card.foil ?? 0)
    : finish;
  return favoriteCardKey(card.setCode, card.collectorNumber, resolvedFinish);
}
