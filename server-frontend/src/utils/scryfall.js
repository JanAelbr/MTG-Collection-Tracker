export function scryfallSetIconUri(setCode) {
  if (!setCode || String(setCode).toLowerCase() === "all") {
    return null;
  }
  return `https://svgs.scryfall.io/sets/${String(setCode).toLowerCase()}.svg`;
}

export function resolveSetIconUri(set) {
  if (!set) {
    return null;
  }
  return set.iconUri || scryfallSetIconUri(set.setCode);
}
