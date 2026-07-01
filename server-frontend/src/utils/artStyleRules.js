let nextRuleId = 1;

export const ART_STYLE_MATCH_TYPES = [
  { value: "all", label: "All cards" },
  { value: "range", label: "Collector number range" },
  { value: "prefix", label: "Collector number prefix" },
  { value: "range_suffix", label: "Number range with suffix" },
];

export function createEmptyArtStyleRuleRow(overrides = {}) {
  return {
    id: `rule-${nextRuleId += 1}`,
    name: "",
    matchType: "range",
    firstNumber: "",
    lastNumber: "",
    prefix: "",
    suffix: "",
    ...overrides,
  };
}

function inferMatchType(rule) {
  if (rule?.all) {
    return "all";
  }
  if (rule?.prefix && rule?.firstNumber == null && rule?.lastNumber == null) {
    return "prefix";
  }
  if (rule?.suffix && rule?.firstNumber != null && rule?.lastNumber != null) {
    return "range_suffix";
  }
  return "range";
}

export function artStyleRuleFromApi(rule) {
  const matchType = inferMatchType(rule);
  return createEmptyArtStyleRuleRow({
    name: rule?.name || "",
    matchType,
    firstNumber: rule?.firstNumber ?? "",
    lastNumber: rule?.lastNumber ?? "",
    prefix: rule?.prefix || "",
    suffix: rule?.suffix || "",
  });
}

export function artStyleRulesFromApi(rules) {
  return (rules || []).map((rule) => artStyleRuleFromApi(rule));
}

function parseNumber(value) {
  if (value === "" || value == null) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function artStyleRuleToApi(row) {
  const name = String(row.name || "").trim();
  const payload = { name };

  if (row.matchType === "all") {
    payload.all = true;
    return payload;
  }
  if (row.matchType === "prefix") {
    payload.prefix = String(row.prefix || "").trim();
    return payload;
  }

  const firstNumber = parseNumber(row.firstNumber);
  const lastNumber = parseNumber(row.lastNumber);
  if (firstNumber == null || lastNumber == null) {
    throw new Error(`Rule "${name || "Untitled"}" needs a collector number range`);
  }
  payload.firstNumber = firstNumber;
  payload.lastNumber = lastNumber;
  if (row.matchType === "range_suffix") {
    payload.suffix = String(row.suffix || "").trim();
    if (!payload.suffix) {
      throw new Error(`Rule "${name || "Untitled"}" needs a collector number suffix`);
    }
  }
  return payload;
}

export function artStyleRulesToApi(rows) {
  if (!rows.length) {
    throw new Error("Add at least one art style rule");
  }
  return rows.map((row) => artStyleRuleToApi(row));
}

export function moveArtStyleRule(rows, index, direction) {
  const target = index + direction;
  if (target < 0 || target >= rows.length) {
    return rows;
  }
  const next = [...rows];
  const [item] = next.splice(index, 1);
  next.splice(target, 0, item);
  return next;
}
