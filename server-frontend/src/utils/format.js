import { displayNameWithFinish } from "./finishes";

export function formatEuro(value) {
  if (value == null || Number.isNaN(value)) {
    return "Unknown";
  }
  return `€ ${Number(value).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",")}`;
}

export function formatProfit(value) {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }
  const formatted = formatEuro(Math.abs(value));
  return value >= 0 ? `+${formatted}` : `−${formatted}`;
}

export function formatRoi(profit, invested) {
  if (profit == null || invested == null || Number.isNaN(profit) || Number.isNaN(invested) || invested === 0) {
    return "Unknown";
  }
  return `${((profit / invested) * 100).toFixed(1)}%`;
}

export function formatDeckOwned(ownedQty, deckSize) {
  if (deckSize == null || deckSize <= 0) {
    return null;
  }
  const owned = ownedQty || 0;
  if (owned >= deckSize) {
    return String(owned);
  }
  return `${owned} / ${deckSize}`;
}

export function formatCoverage(covered, total) {
  if (!total) {
    return "Unknown";
  }
  const percent = (covered / total) * 100;
  return `${covered} / ${total} (${percent.toFixed(1)}%)`;
}

export function formatCompletion(ownedCount, catalogCount) {
  if (!catalogCount) {
    return "Unknown";
  }
  return formatCoverage(ownedCount, catalogCount);
}

export function formatDeckValueRange(ownedValue, totalValue) {
  if (ownedValue != null && totalValue != null) {
    return `${formatEuro(ownedValue)} / ${formatEuro(totalValue)}`;
  }
  return formatEuro(totalValue ?? ownedValue);
}

export function formatSection(section) {
  if (!section) {
    return "";
  }
  return section.charAt(0).toUpperCase() + section.slice(1);
}

export function displayNameWithFoil(name, foil) {
  if (!name) {
    return "Unknown";
  }
  return displayNameWithFinish(name, foil);
}

export function formatPercentChange(change, previousValue) {
  if (
    change == null
    || Number.isNaN(change)
    || previousValue == null
    || Number.isNaN(previousValue)
    || previousValue === 0
  ) {
    return "";
  }
  const percent = (change / previousValue) * 100;
  const formatted = `${Math.abs(percent).toFixed(1)}%`;
  if (percent > 0) {
    return ` (+${formatted})`;
  }
  if (percent < 0) {
    return ` (-${formatted})`;
  }
  return " (0.0%)";
}

export function formatPriceChangeEuroBracket(change) {
  if (change == null || Number.isNaN(change)) {
    return null;
  }
  if (change === 0) {
    return "(0)";
  }
  const formatted = formatEuro(Math.abs(change));
  const prefix = change >= 0 ? "+" : "−";
  return `(${prefix}${formatted})`;
}

export function formatPriceChangePercentBracket(change, previousValue) {
  const suffix = formatPercentChange(change, previousValue);
  return suffix ? suffix.trim() : null;
}

export function formatPriceChange(value, previousValue) {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }
  if (value === 0) {
    return "No changes";
  }
  const suffix = formatPercentChange(value, previousValue);
  const formatted = formatEuro(Math.abs(value));
  const prefix = value >= 0 ? "+" : "−";
  return `${prefix}${formatted}${suffix}`;
}

export function formatSetDropdownLabel(set) {
  if (!set?.label) {
    return "";
  }
  let label = set.favorite ? `★ ${set.label}` : set.label;
  const counts = formatSetCountLabel(set);
  if (counts) {
    label = `${label} ${counts}`;
  }
  return label;
}

export function setShortName(set) {
  if (!set) {
    return "";
  }
  if (set.setCode === "All") {
    return "All sets";
  }
  const label = set.label || set.setCode || "";
  return label.replace(/\s*\([A-Z0-9]+\)\s*$/i, "").trim() || set.setCode;
}

export function formatSetCountLabel(set) {
  if (set?.ownedCount == null || set?.catalogCount == null) {
    return "";
  }
  return `(${set.ownedCount}/${set.catalogCount})`;
}

export function artStyleOptionValue(style) {
  if (typeof style === "string") {
    return style;
  }
  return style?.artStyle || "";
}

export function formatArtStyleDropdownLabel(style) {
  const label = typeof style === "string" ? style : (style?.label || style?.artStyle || "");
  if (!label) {
    return "";
  }
  if (typeof style !== "string" && style?.ownedCount != null && style?.catalogCount != null) {
    return `${label} (${style.ownedCount}/${style.catalogCount})`;
  }
  return label;
}

export function formatUnknownCardLine(card) {
  const setCode = card.setCode || card.set_code || "";
  const collectorNumber = String(card.collectorNumber || card.collector_number || "");
  const number = collectorNumber.padStart(3, "0");
  const name = displayNameWithFoil(card.name, card.finish ?? card.foil);
  const artStyle = card.artStyle || card.art_style || "";
  return `${setCode} - ${number} - ${name} - ${artStyle}`;
}
