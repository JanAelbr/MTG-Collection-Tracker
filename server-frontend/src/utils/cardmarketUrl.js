/** Drop Scryfall's attribution from a Cardmarket link without changing stored URLs. */
export function displayCardmarketUrl(value) {
  const text = String(value || "").trim();
  if (!text) {
    return "";
  }
  let parsed;
  try {
    parsed = new URL(text);
  } catch {
    return text;
  }
  const source = parsed.searchParams.get("utm_source");
  if (!source || source.toLowerCase() !== "scryfall") {
    return text;
  }
  parsed.searchParams.delete("utm_source");
  return parsed.toString();
}
