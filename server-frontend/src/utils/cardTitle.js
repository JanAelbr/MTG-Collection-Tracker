/**
 * Card title normalization / fuzzy match for scan redundancy.
 */

const STOP = new Set([
  "A",
  "AN",
  "THE",
  "OF",
  "AND",
  "OR",
  "TO",
  "IN",
  "ON",
  "FOR",
]);

/** OCR'd mana-cost tokens that often trail the title (e.g. "1R", "UU", "3"). */
const MANA_COST_TOKEN_RE =
  /^(?:[0-9]{1,2}|[Xx]|[WUBRGCS]{1,5}|[0-9]{1,2}[WUBRGCS]{1,5}|[WUBRGC]P)$/i;

function normalizeManaOcrToken(token) {
  return String(token || "")
    .replace(/[{}\/·•.]/g, "")
    .replace(/[Il|]/g, "1")
    .replace(/[Oo]/g, "0")
    .trim();
}

export function isManaCostToken(token) {
  const raw = String(token || "").trim();
  if (!raw || raw.length > 6) {
    return false;
  }
  const normalized = normalizeManaOcrToken(raw);
  return MANA_COST_TOKEN_RE.test(normalized) || MANA_COST_TOKEN_RE.test(raw);
}

function stripEdgeNoise(token) {
  return String(token || "")
    .replace(/^[\s.·•\-_:;,"'`]+/, "")
    .replace(/[\s.·•\-_:;,"'`]+$/, "");
}

/**
 * Strip trailing mana-cost OCR from a title line ("Lightning Bolt 1R" → "Lightning Bolt").
 */
export function stripTrailingManaCost(raw) {
  let text = String(raw || "").replace(/\s+/g, " ").trim();
  if (!text) {
    return "";
  }
  text = text.replace(/(\s*\{[^}]+\})+\s*$/g, "").trim();
  text = stripEdgeNoise(text);
  const parts = text.split(" ").filter(Boolean);
  while (parts.length && stripEdgeNoise(parts[0]) !== parts[0]) {
    parts[0] = stripEdgeNoise(parts[0]);
    if (!parts[0]) {
      parts.shift();
    }
  }
  while (parts.length && stripEdgeNoise(parts[parts.length - 1]) !== parts[parts.length - 1]) {
    parts[parts.length - 1] = stripEdgeNoise(parts[parts.length - 1]);
    if (!parts[parts.length - 1]) {
      parts.pop();
    }
  }
  while (parts.length > 1 && isManaCostToken(parts[parts.length - 1])) {
    parts.pop();
  }
  if (parts.length) {
    const last = parts[parts.length - 1];
    // Only peel digit/X-led mana glued onto a word (e.g. Bolt1R). Never peel
    // bare letters — that turns "Counterspell" / "Ring" into truncated names.
    const glued = last.match(
      /^([A-Za-z][A-Za-z'-]*[A-Za-z])([0-9][0-9XxWUBRGCSwubrgcs]{0,5}|[Xx][0-9WUBRGCSwubrgcs]{0,5}|[Il][WUBRGCSwubrgcs]{1,5})$/,
    );
    if (glued && isManaCostToken(glued[2])) {
      parts[parts.length - 1] = glued[1];
    }
  }
  return parts.join(" ").trim();
}

export function normalizeCardTitle(raw) {
  return stripTrailingManaCost(String(raw || ""))
    .replace(/[‘’]/g, "'")
    .replace(/[“”]/g, "\"")
    .replace(/[^A-Za-z0-9'\s-]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toUpperCase();
}

export function titleTokens(raw) {
  return normalizeCardTitle(raw)
    .split(" ")
    .map((token) => token.replace(/^'+|'+$/g, ""))
    .filter((token) => token.length >= 2 && !STOP.has(token));
}

function editDistance(left, right, maxDist = 2) {
  if (left === right) {
    return 0;
  }
  if (Math.abs(left.length - right.length) > maxDist) {
    return maxDist + 1;
  }
  if (!left.length || !right.length) {
    return Math.max(left.length, right.length);
  }
  let prev = Array.from({ length: right.length + 1 }, (_, i) => i);
  for (let i = 0; i < left.length; i += 1) {
    const curr = [i + 1];
    let minRow = i + 1;
    for (let j = 0; j < right.length; j += 1) {
      const cost = left[i] === right[j] ? 0 : 1;
      const best = Math.min(prev[j + 1] + 1, curr[j] + 1, prev[j] + cost);
      curr.push(best);
      if (best < minRow) {
        minRow = best;
      }
    }
    if (minRow > maxDist) {
      return maxDist + 1;
    }
    prev = curr;
  }
  return prev[right.length];
}

export function tokensFuzzyEqual(left, right) {
  const a = String(left || "");
  const b = String(right || "");
  if (!a || !b) {
    return false;
  }
  if (a === b) {
    return true;
  }
  const shorter = a.length <= b.length ? a : b;
  const longer = a.length <= b.length ? b : a;
  if (shorter.length >= 5 && longer.startsWith(shorter) && longer.length - shorter.length <= 2) {
    return true;
  }
  if (Math.min(a.length, b.length) < 4) {
    return false;
  }
  const maxDist = Math.min(a.length, b.length) >= 7 ? 2 : 1;
  return editDistance(a, b, maxDist) <= maxDist;
}

function sharedTokenCount(leftTokens, rightTokens) {
  const unused = [...rightTokens];
  let shared = 0;
  for (const token of leftTokens) {
    const matchAt = unused.findIndex((other) => tokensFuzzyEqual(token, other));
    if (matchAt >= 0) {
      shared += 1;
      unused.splice(matchAt, 1);
    }
  }
  return shared;
}

/**
 * True when OCR title is empty/too weak to act as a check.
 */
export function titleHintIsUsable(raw) {
  const tokens = titleTokens(raw);
  const normalized = normalizeCardTitle(raw);
  return tokens.length >= 1 && normalized.length >= 3;
}

/**
 * Loose match: shared significant tokens or one contains the other.
 */
export function titlesLikelyMatch(ocrTitle, catalogName) {
  if (!titleHintIsUsable(ocrTitle)) {
    return true;
  }
  const left = normalizeCardTitle(ocrTitle);
  const right = normalizeCardTitle(catalogName);
  if (!right) {
    return true;
  }
  if (left === right) {
    return true;
  }
  if (left.includes(right) || right.includes(left)) {
    return true;
  }
  const a = titleTokens(left);
  const b = titleTokens(right);
  if (!a.length || !b.length) {
    return true;
  }
  const shared = sharedTokenCount(a, b);
  const needed = Math.min(2, Math.min(a.length, b.length));
  return shared >= needed;
}

export function nameMatchScore(ocrTitle, catalogName) {
  if (!titleHintIsUsable(ocrTitle) || !catalogName) {
    return 0;
  }
  const left = normalizeCardTitle(ocrTitle);
  const right = normalizeCardTitle(catalogName);
  if (!right) {
    return 0;
  }
  if (left === right) {
    return 1;
  }
  if (left.includes(right) || right.includes(left)) {
    return 0.92;
  }
  const a = titleTokens(left);
  const b = titleTokens(right);
  if (!a.length || !b.length) {
    return 0;
  }
  const shared = sharedTokenCount(a, b);
  if (!shared) {
    return 0;
  }
  const coverage = shared / Math.max(a.length, b.length);
  const overlap = shared / Math.min(a.length, b.length);
  let score = Math.max(coverage, overlap * 0.85);
  if (shared === a.length) {
    score = Math.max(score, 0.78);
  }
  return Math.min(1, score);
}
