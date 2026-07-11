import { ref, shallowRef } from "vue";
import { api, clearClientCache } from "../api";
import { cardFinish } from "../utils/finishes";
import { fetchPricingSettings } from "./pricingSettings";

export const storageLocations = shallowRef([]);
const ownershipPatches = shallowRef(new Map());
const setCountPatches = shallowRef(new Map());
export { setCountPatches };
export const ownershipRevision = ref(0);

function setCodePatchKey(setCode) {
  return setCode === "All" ? "All" : String(setCode).toUpperCase();
}

export function ownershipPrintKey(setCode, collectorNumber, finish) {
  return `${String(setCode).toUpperCase()}|${String(collectorNumber).trim()}|${cardFinish({ finish })}`;
}

export function clearOwnershipPatches() {
  ownershipPatches.value = new Map();
}

export function setOwnershipPatch(setCode, collectorNumber, finish, patch) {
  const key = ownershipPrintKey(setCode, collectorNumber, finish);
  const next = new Map(ownershipPatches.value);
  next.set(key, patch);
  ownershipPatches.value = next;
  ownershipRevision.value += 1;
}

export function getOwnershipPatch(card) {
  if (!card) {
    return null;
  }
  const setCode = card.setCode || card.set_code;
  const collectorNumber = card.collectorNumber || card.collector_number;
  if (!setCode || collectorNumber == null || collectorNumber === "") {
    return null;
  }
  const key = ownershipPrintKey(setCode, collectorNumber, cardFinish(card));
  return ownershipPatches.value.get(key) ?? null;
}

function finishDataForCard(card) {
  if (!card?.finishes) {
    return null;
  }
  const finish = cardFinish(card);
  return card.finishes[String(finish)] ?? card.finishes[finish] ?? null;
}

export function isFinishDataOwned(finishInfo) {
  if (!finishInfo) {
    return false;
  }
  if (Array.isArray(finishInfo.locations) && finishInfo.locations.length > 0) {
    return true;
  }
  if (finishInfo.owned != null) {
    return Boolean(finishInfo.owned);
  }
  return finishInfo.purchaseValue != null;
}

function finishOwnedCount(finishInfo) {
  if (!finishInfo) {
    return null;
  }
  if (Array.isArray(finishInfo.locations) && finishInfo.locations.length > 0) {
    return finishInfo.locations.reduce(
      (sum, location) => sum + (Number(location.count) || 0),
      0,
    );
  }
  if (isFinishDataOwned(finishInfo)) {
    return 1;
  }
  return 0;
}

export function isEffectivelyOwned(card) {
  const patch = getOwnershipPatch(card);
  if (patch) {
    return patch.owned;
  }
  const finishInfo = finishDataForCard(card);
  if (finishInfo) {
    return isFinishDataOwned(finishInfo);
  }
  if (card?.ownedQty != null) {
    return Number(card.ownedQty) > 0;
  }
  if (card?.owned != null) {
    return Boolean(card.owned);
  }
  if (Array.isArray(card?.locations) && card.locations.length > 0) {
    return true;
  }
  return card?.purchaseValue != null;
}

export function effectiveDeckOwnedQty(card) {
  if (!card) {
    return 0;
  }
  const patch = getOwnershipPatch(card);
  if (patch?.ownedCount != null) {
    return patch.ownedCount;
  }
  const finishCount = finishOwnedCount(finishDataForCard(card));
  if (finishCount != null) {
    return finishCount;
  }
  return Number(card.ownedQty) || 0;
}

export function isDeckCardFullyOwned(card) {
  const qty = Number(card?.qty) || 0;
  if (!qty) {
    return false;
  }
  return effectiveDeckOwnedQty(card) >= qty;
}

export function reconcileSetCountPatches() {
  if (!setCountPatches.value.size) {
    return;
  }
  setCountPatches.value = new Map();
}

export function applySetCountPatchesToSets(sets) {
  if (!Array.isArray(sets) || !setCountPatches.value.size) {
    return sets;
  }
  return sets.map((set) => {
    const patch = setCountPatches.value.get(setCodePatchKey(set.setCode));
    if (!patch) {
      return set;
    }
    return {
      ...set,
      ownedCount: Math.max(0, (set.ownedCount ?? 0) + patch),
    };
  });
}

export function applyOptimisticSetScopeCount(card, previousCount, nextCount) {
  const wasPrintOwned = previousCount > 0;
  const isPrintOwned = nextCount > 0;
  if (wasPrintOwned === isPrintOwned) {
    return;
  }
  const delta = isPrintOwned ? 1 : -1;
  const target = normalizeCardMenuTarget(card);
  if (!target) {
    return;
  }
  const next = new Map(setCountPatches.value);
  for (const code of [setCodePatchKey(target.setCode), "All"]) {
    next.set(code, (next.get(code) || 0) + delta);
  }
  setCountPatches.value = next;
}

export function reconcileOwnershipPatches(cards) {
  if (!ownershipPatches.value.size || !Array.isArray(cards)) {
    return;
  }
  const next = new Map(ownershipPatches.value);
  for (const card of cards) {
    const patch = getOwnershipPatch(card);
    if (!patch) {
      continue;
    }
    const finishInfo = finishDataForCard(card);
    const serverOwned = card?.owned != null
      ? Boolean(card.owned)
      : finishInfo
        ? isFinishDataOwned(finishInfo)
        : (Array.isArray(card?.locations) && card.locations.length > 0)
          || card?.purchaseValue != null;
    if (serverOwned === patch.owned) {
      next.delete(ownershipPrintKey(card.setCode, card.collectorNumber, cardFinish(card)));
    }
  }
  if (next.size !== ownershipPatches.value.size) {
    ownershipPatches.value = next;
  }
}

export function mergeOwnershipPatchesIntoCards(cards) {
  if (!Array.isArray(cards) || !ownershipPatches.value.size) {
    return;
  }
  for (const card of cards) {
    const patch = getOwnershipPatch(card);
    if (!patch) {
      continue;
    }
    applyOwnershipPatchToCards(
      [card],
      card.setCode,
      card.collectorNumber,
      cardFinish(card),
      patch,
    );
  }
}

export function mergeOwnershipPatchesIntoPages(pages) {
  if (!pages || !ownershipPatches.value.size) {
    return;
  }
  for (const stats of Object.values(pages)) {
    mergeOwnershipPatchesIntoCards(stats?.cards);
  }
}

export function applyOwnershipPatchToCards(cards, setCode, collectorNumber, finish, patch) {
  if (!Array.isArray(cards)) {
    return;
  }
  const normalizedFinish = cardFinish({ finish });
  for (const card of cards) {
    if (
      String(card.setCode).toUpperCase() === String(setCode).toUpperCase()
      && String(card.collectorNumber) === String(collectorNumber)
      && cardFinish(card) === normalizedFinish
    ) {
      card.owned = patch.owned;
      if (card.ownedQty != null || card.qty != null) {
        const qty = Math.max(1, Number(card.qty) || 1);
        card.ownedQty = patch.owned ? Math.min(patch.ownedCount ?? qty, qty) : 0;
      }
      if (patch.owned) {
        card.purchaseValue = card.purchaseValue ?? 0;
      } else {
        card.purchaseValue = null;
      }
    }
  }
}

export function normalizeCardMenuTarget(card) {
  const setCode = card?.setCode || card?.set_code;
  const collectorNumber = card?.collectorNumber || card?.collector_number;
  if (!setCode || collectorNumber == null || collectorNumber === "") {
    return null;
  }
  return {
    setCode: String(setCode),
    collectorNumber: String(collectorNumber),
    finish: cardFinish(card),
    name: card?.name || card?.cardName || "",
    imageUri: card?.imageUri || card?.image_uri || "",
  };
}

async function ensureStorageLocations() {
  if (storageLocations.value.length) {
    return;
  }
  const payload = await api.listStorageLocations();
  storageLocations.value = payload.locations || [];
}

export { ensureStorageLocations };

function defaultStorageSlug(state, settings) {
  if (state?.copies?.length === 1) {
    return state.copies[0].locationSlug;
  }
  if (state?.locationSlug) {
    return state.locationSlug;
  }
  if (settings?.defaultStorageLocation) {
    return settings.defaultStorageLocation;
  }
  return storageLocations.value[0]?.slug || "storage:general";
}

function publishOwnershipChange(target, state, card = null) {
  const patch = {
    owned: (state?.ownedCount ?? 0) > 0,
    ownedCount: state?.ownedCount ?? 0,
  };
  setOwnershipPatch(target.setCode, target.collectorNumber, target.finish, patch);
  if (card) {
    applyOwnershipPatchToCards([card], target.setCode, target.collectorNumber, target.finish, patch);
  }
  clearClientCache();
}

export async function fetchCardCopyState(card) {
  const target = normalizeCardMenuTarget(card);
  if (!target) {
    return null;
  }
  const [state, settings] = await Promise.all([
    api.getCardCopyState({
      setCode: target.setCode,
      collectorNumber: target.collectorNumber,
      finish: target.finish,
    }),
    ensureStorageLocations().then(() => fetchPricingSettings()),
  ]);
  return {
    target,
    state,
    settings,
    storageSlug: defaultStorageSlug(state, settings),
  };
}

export async function adjustCardCopyCount(card, delta, storageSlug) {
  const target = normalizeCardMenuTarget(card);
  if (!target) {
    throw new Error("Invalid card.");
  }
  const state = await api.adjustCardCopyCount({
    setCode: target.setCode,
    collectorNumber: target.collectorNumber,
    finish: target.finish,
    delta,
    locationSlug: delta > 0 ? storageSlug : undefined,
  });
  publishOwnershipChange(target, state, card);
  return state;
}

export async function setCardCopyAllocations(card, allocations) {
  const target = normalizeCardMenuTarget(card);
  if (!target) {
    throw new Error("Invalid card.");
  }
  const state = await api.setCardCopyAllocations({
    setCode: target.setCode,
    collectorNumber: target.collectorNumber,
    finish: target.finish,
    allocations,
  });
  publishOwnershipChange(target, state, card);
  return state;
}

export async function changeCardOwnershipFinish(card, toFinish) {
  const target = normalizeCardMenuTarget(card);
  if (!target) {
    throw new Error("Invalid card.");
  }
  const fromFinish = target.finish;
  const normalizedTo = cardFinish({ finish: toFinish });
  if (fromFinish === normalizedTo) {
    return null;
  }

  const state = await api.changeOwnershipFinish({
    setCode: target.setCode,
    collectorNumber: target.collectorNumber,
    fromFinish,
    toFinish: normalizedTo,
  });

  setOwnershipPatch(target.setCode, target.collectorNumber, fromFinish, {
    owned: false,
    ownedCount: 0,
  });
  publishOwnershipChange({ ...target, finish: normalizedTo }, state, card);
  if (card) {
    card.finish = normalizedTo;
    card.foil = normalizedTo;
  }
  return state;
}

export async function updateCardCopyStorage(card, instanceId, locationSlug) {
  const target = normalizeCardMenuTarget(card);
  if (!target || !instanceId || !locationSlug) {
    throw new Error("Invalid card, copy, or storage.");
  }
  const state = await api.updateCardCopyStorage(instanceId, { locationSlug });
  publishOwnershipChange(target, state, card);
  return state;
}

export async function updateCardCopyFinish(card, instanceId, toFinish) {
  const target = normalizeCardMenuTarget(card);
  if (!target || !instanceId) {
    throw new Error("Invalid card or copy.");
  }
  const normalizedTo = cardFinish({ finish: toFinish });
  const fromFinish = target.finish;
  await api.updateCardInstance(instanceId, { finish: normalizedTo });
  clearClientCache();

  if (card) {
    card.finish = normalizedTo;
    card.foil = normalizedTo;
  }

  const nextTarget = { ...target, finish: normalizedTo };
  const state = await api.getCardCopyState({
    setCode: nextTarget.setCode,
    collectorNumber: nextTarget.collectorNumber,
    finish: normalizedTo,
  });
  publishOwnershipChange(nextTarget, state, card);

  if (fromFinish !== normalizedTo) {
    const previousState = await api.getCardCopyState({
      setCode: target.setCode,
      collectorNumber: target.collectorNumber,
      finish: fromFinish,
    });
    publishOwnershipChange({ ...target, finish: fromFinish }, previousState, card);
  }

  return state;
}

export function applyOptimisticCopyCount(card, ownedCount, previousCount = null) {
  clearClientCache();
  const target = normalizeCardMenuTarget(card);
  if (!target) {
    return;
  }
  const prevCount = previousCount ?? (getOwnershipPatch(card)?.ownedCount ?? 0);
  applyOptimisticSetScopeCount(card, prevCount, ownedCount);
  const patch = {
    owned: ownedCount > 0,
    ownedCount,
  };
  setOwnershipPatch(target.setCode, target.collectorNumber, target.finish, patch);
  applyOwnershipPatchToCards([card], target.setCode, target.collectorNumber, target.finish, patch);
}
