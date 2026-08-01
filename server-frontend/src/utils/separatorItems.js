import { artStyleRulesFromApi } from "./artStyleRules.js";
import { setDisplayName, setShortName } from "./format.js";

export function releaseYear(set) {
  const date = String(set?.releasedAt || "").trim();
  if (/^\d{4}/.test(date)) {
    return date.slice(0, 4);
  }
  return "";
}

export function formatArtStyleNumberRange(rule) {
  if (!rule) {
    return "";
  }
  if (rule.matchType === "all") {
    return "All";
  }
  if (rule.matchType === "prefix") {
    const prefix = String(rule.prefix || "").trim();
    return prefix ? `${prefix}…` : "";
  }
  const first = rule.firstNumber;
  const last = rule.lastNumber;
  if (first === "" || first == null || last === "" || last == null) {
    return "";
  }
  const suffix = rule.matchType === "range_suffix" && rule.suffix
    ? String(rule.suffix).trim()
    : "";
  const sameNumber = Number(first) === Number(last) && Number.isFinite(Number(first));
  const range = sameNumber ? String(first) : `${first} – ${last}`;
  return suffix ? `${range}${suffix}` : range;
}

export function buildStorageSeparators(sets) {
  return (sets || []).map((set, index) => {
    const setCode = String(set.setCode || "").trim();
    const setName = setShortName(set) || setDisplayName(set) || setCode;
    const familyRoot = String(set.familyRoot || set.parentSetCode || setCode || "").trim();
    return {
      id: `storage-${setCode}-${index}`,
      mode: "storage",
      setCode,
      familyRoot: familyRoot || setCode,
      setName,
      year: releaseYear(set),
      previewLabel: setCode || setName,
    };
  });
}

export function buildBinderSeparators(sets, rulesBySetCode) {
  const items = [];
  for (const set of sets || []) {
    const setCode = String(set.setCode || "").trim();
    const setName = setShortName(set) || setDisplayName(set) || setCode;
    const familyRoot = String(set.familyRoot || set.parentSetCode || setCode || "").trim() || setCode;
    const rawRules = rulesBySetCode?.get?.(setCode) ?? rulesBySetCode?.[setCode];
    const rules = artStyleRulesFromApi(rawRules || []);

    if (!rules.length) {
      items.push({
        id: `binder-${setCode}-default`,
        mode: "binder",
        setCode,
        familyRoot,
        setName,
        artStyle: "",
        numberRange: "",
        previewLabel: setName,
      });
      continue;
    }

    for (const [index, rule] of rules.entries()) {
      const artStyle = String(rule.name || "").trim() || "Art style";
      const numberRange = formatArtStyleNumberRange(rule);
      items.push({
        id: `binder-${setCode}-${index}-${artStyle}`,
        mode: "binder",
        setCode,
        familyRoot,
        setName,
        artStyle,
        numberRange,
        previewLabel: `${setCode} · ${artStyle}`,
      });
    }
  }
  return items;
}
