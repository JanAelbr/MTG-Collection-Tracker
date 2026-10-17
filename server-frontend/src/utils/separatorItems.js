import { artStyleRulesFromApi } from "./artStyleRules.js";
import { setDisplayName } from "./format.js";
import { profileLocalStorage } from "./profileStorage.js";

export const BINDER_EXCLUDED_ART_STYLES_KEY = "lotr.separators.binderExcludedArtStyles";

export function binderArtStyleKey(setCode, artStyle) {
  return `${String(setCode || "").trim().toUpperCase()}|${String(artStyle || "").trim()}`;
}

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
    return prefix ? `#${prefix}…` : "";
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
  const range = sameNumber ? `#${first}` : `#${first} – #${last}`;
  return suffix ? `${range}${suffix}` : range;
}

function resolveSeparatorFamilyRoot(set, setCode) {
  const familyRoot = String(set?.familyRoot || "").trim();
  const parent = String(set?.parentSetCode || "").trim();
  if (familyRoot && familyRoot.toUpperCase() !== String(setCode).toUpperCase()) {
    return familyRoot;
  }
  if (parent) {
    return parent;
  }
  return familyRoot || setCode;
}

export function buildStorageSeparators(sets) {
  return (sets || []).map((set, index) => {
    const setCode = String(set.setCode || "").trim();
    const setName = setDisplayName(set) || setCode;
    const familyRoot = resolveSeparatorFamilyRoot(set, setCode);
    return {
      id: `storage-${setCode}-${index}`,
      mode: "storage",
      setCode,
      familyRoot,
      iconUri: set.iconUri || "",
      setName,
      year: releaseYear(set),
      previewLabel: setCode || setName,
    };
  });
}

function artStyleLabel(rule) {
  return String(rule?.name || "").trim() || "Art style";
}

export function buildBinderArtStyleGroups(sets, rulesBySetCode) {
  const groups = [];
  for (const set of sets || []) {
    const setCode = String(set.setCode || "").trim();
    if (!setCode) {
      continue;
    }
    const rawRules = rulesBySetCode?.get?.(setCode) ?? rulesBySetCode?.[setCode];
    const rules = artStyleRulesFromApi(rawRules || []);
    if (!rules.length) {
      continue;
    }
    groups.push({
      setCode,
      setName: setDisplayName(set) || setCode,
      styles: rules.map((rule) => {
        const artStyle = artStyleLabel(rule);
        return {
          key: binderArtStyleKey(setCode, artStyle),
          artStyle,
          numberRange: formatArtStyleNumberRange(rule),
        };
      }),
    });
  }
  return groups;
}

export function loadBinderExcludedArtStyles() {
  try {
    const raw = JSON.parse(profileLocalStorage.getItem(BINDER_EXCLUDED_ART_STYLES_KEY) || "[]");
    if (!Array.isArray(raw)) {
      return new Set();
    }
    return new Set(raw.filter((key) => typeof key === "string" && key));
  } catch {
    return new Set();
  }
}

export function saveBinderExcludedArtStyles(keys) {
  const list = [...(keys || [])].filter((key) => typeof key === "string" && key);
  try {
    profileLocalStorage.setItem(BINDER_EXCLUDED_ART_STYLES_KEY, JSON.stringify(list));
  } catch {
    // Private mode or a full quota should not block printing.
  }
  return new Set(list);
}

export function buildBinderSeparators(sets, rulesBySetCode, options = {}) {
  const excludedKeys = options.excludedKeys;
  const items = [];
  for (const set of sets || []) {
    const setCode = String(set.setCode || "").trim();
    const setName = setDisplayName(set) || setCode;
    const familyRoot = resolveSeparatorFamilyRoot(set, setCode);
    const iconUri = set.iconUri || "";
    const rawRules = rulesBySetCode?.get?.(setCode) ?? rulesBySetCode?.[setCode];
    const rules = artStyleRulesFromApi(rawRules || []);

    if (!rules.length) {
      items.push({
        id: `binder-${setCode}-default`,
        mode: "binder",
        setCode,
        familyRoot,
        iconUri,
        setName,
        artStyle: "",
        numberRange: "",
        previewLabel: setName,
      });
      continue;
    }

    for (const [index, rule] of rules.entries()) {
      const artStyle = artStyleLabel(rule);
      if (excludedKeys?.has?.(binderArtStyleKey(setCode, artStyle))) {
        continue;
      }
      const numberRange = formatArtStyleNumberRange(rule);
      items.push({
        id: `binder-${setCode}-${index}-${artStyle}`,
        mode: "binder",
        setCode,
        familyRoot,
        iconUri,
        setName,
        artStyle,
        numberRange,
        previewLabel: `${setCode} · ${artStyle}`,
      });
    }
  }
  return items;
}
