const MIN_ABS_DELTA = 1;

export function artStyleMoverKey(row) {
  const setCode = String(row?.setCode || "").trim().toUpperCase();
  const artStyle = String(row?.artStyle || "").trim();
  return `${setCode}|${artStyle}`;
}

export function isCardMoverRow(row) {
  return Boolean(String(row?.collectorNumber || "").trim());
}

export function collectPriceSyncCards(payload) {
  const fromPayload = Array.isArray(payload?.cards) ? payload.cards : [];
  const cards = fromPayload.filter(isCardMoverRow);
  if (cards.length) {
    return cards;
  }
  return [];
}

export function collectPriceSyncStyleRows(payload) {
  return aggregateArtStyleMovers(collectPriceSyncCards(payload));
}

export function cardsForArtStyle(cards, filter) {
  if (!filter) {
    return (cards || []).filter(isCardMoverRow);
  }
  const setCode = String(filter.setCode || "").trim().toUpperCase();
  const artStyle = String(filter.artStyle || "").trim();
  return (cards || []).filter((row) => (
    isCardMoverRow(row)
    && String(row.setCode || "").trim().toUpperCase() === setCode
    && String(row.artStyle || "").trim() === artStyle
  ));
}

export function aggregateArtStyleMovers(cards) {
  const groups = new Map();
  for (const card of cards || []) {
    const setCode = String(card.setCode || "").trim().toUpperCase();
    const artStyle = String(card.artStyle || "").trim() || "Unknown";
    const id = `${setCode}|${artStyle}`;
    const existing = groups.get(id) || {
      id,
      setCode,
      artStyle,
      label: artStyle,
      previous: 0,
      current: 0,
    };
    existing.previous += Number(card.previous) || 0;
    existing.current += Number(card.current) || 0;
    groups.set(id, existing);
  }
  return [...groups.values()].map((row) => {
    const delta = row.current - row.previous;
    return {
      ...row,
      delta,
      percent: row.previous > 0 ? (delta / row.previous) * 100 : 0,
    };
  }).filter((row) => Math.abs(row.delta) >= MIN_ABS_DELTA);
}

export function moverRowToTileCard(row) {
  const finishLabelText = String(row?.finish || "").trim();
  const rawName = String(row?.name || "").trim();
  const label = String(row?.label || "").trim();
  const name = rawName || label.replace(/\s+\((Foil|Etched)\)$/i, "").trim();
  return {
    name,
    cardName: name,
    setCode: String(row?.setCode || "").trim().toUpperCase(),
    collectorNumber: String(row?.collectorNumber || "").trim(),
    imageUri: String(row?.imageUri || row?.image_uri || "").trim(),
    finish: finishLabelText || row?.finish,
  };
}

export function rankMoverRows(rows, { scale = "absolute", limit = 25 } = {}) {
  const risers = (rows || []).filter((row) => Number(row.delta) > 0);
  const fallers = (rows || []).filter((row) => Number(row.delta) < 0);
  const compare = scale === "relative"
    ? (left, right) => (
      Math.abs(right.percent) - Math.abs(left.percent)
      || Math.abs(right.delta) - Math.abs(left.delta)
    )
    : (left, right) => (
      Math.abs(right.delta) - Math.abs(left.delta)
      || Math.abs(right.percent) - Math.abs(left.percent)
    );
  risers.sort(compare);
  fallers.sort(compare);
  return {
    risers: risers.slice(0, Math.max(0, limit)),
    fallers: fallers.slice(0, Math.max(0, limit)),
  };
}
