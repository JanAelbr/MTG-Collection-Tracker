export function homeChangesRoute({ setCode = "", artStyle = "" } = {}) {
  const query = {};
  const code = String(setCode || "").trim();
  const style = String(artStyle || "").trim();
  if (code) {
    query.set = code;
  }
  if (style) {
    query.art = style;
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
