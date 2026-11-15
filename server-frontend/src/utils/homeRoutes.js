export function homeChangesRoute({ setCode = "", artStyle = "", deckId = "" } = {}) {
  const query = {};
  const code = String(setCode || "").trim();
  const style = String(artStyle || "").trim();
  const deck = String(deckId || "").trim();
  if (code) {
    query.set = code;
  }
  if (style) {
    query.art = style;
  }
  if (deck) {
    query.deck = deck;
  }
  if (!query.set && !query.art && !query.deck) {
    return { name: "home", hash: "#home-movers" };
  }
  return { name: "home-changes", query };
}

export function isHomeChangesRoute(route) {
  return route?.name === "home-changes";
}

export function homeRouteQueryValue(value) {
  const raw = Array.isArray(value) ? value[0] : value;
  return String(raw || "").trim();
}
