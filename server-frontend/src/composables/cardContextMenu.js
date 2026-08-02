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

export function isDeckScopeCard(card) {
  const section = String(card?.section || "").toLowerCase();
  if (!["commander", "main", "sideboard"].includes(section)) {
    return false;
  }
  return card?.deckId != null || card?.deck_id != null;
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

const listingPatches = shallowRef(new Map());

export function setListingPatch(setCode, collectorNumber, finish, patch) {
  const key = ownershipPrintKey(setCode, collectorNumber, finish);
  const next = new Map(listingPatches.value);
  if (patch == null) {
    next.delete(key);
  } else {
    next.set(key, patch);
  }
  listingPatches.value = next;
  ownershipRevision.value += 1;
}

export function getListingPatch(card) {
  if (!card) {
    return null;
  }
  const setCode = card.setCode || card.set_code;
  const collectorNumber = card.collectorNumber || card.collector_number;
  if (!setCode || collectorNumber == null || collectorNumber === "") {
    return null;
  }
  const key = ownershipPrintKey(setCode, collectorNumber, cardFinish(card));
  return listingPatches.value.get(key) ?? null;
}

export function effectiveListingPrice(card) {
  ownershipRevision.value;
  const patch = getListingPatch(card);
  if (patch && Object.prototype.hasOwnProperty.call(patch, "listingPrice")) {
    return patch.listingPrice;
  }
  if (card?.listingPrice == null || Number.isNaN(Number(card.listingPrice))) {
    return null;
  }
  return Number(card.listingPrice);
}

export function applyListingPatchToCards(cards, setCode, collectorNumber, finish, patch) {
  if (!Array.isArray(cards) || !patch) {
    return;
  }
  const normalizedFinish = cardFinish({ finish });
  for (const card of cards) {
    if (
      String(card.setCode || card.set_code).toUpperCase() === String(setCode).toUpperCase()
      && String(card.collectorNumber || card.collector_number) === String(collectorNumber)
      && cardFinish(card) === normalizedFinish
    ) {
      card.forSale = Boolean(patch.forSale);
      card.listingPrice = patch.listingPrice;
      if (patch.listingId != null) {
        card.listingId = patch.listingId;
      }
      if (patch.listedInstanceId != null) {
        card.listedInstanceId = patch.listedInstanceId;
      }
    }
  }
}

export function applyListingResultToCard(card, result) {
  if (!card || !result) {
    return null;
  }
  const setCode = result.setCode || card.setCode || card.set_code;
  const collectorNumber = result.collectorNumber ?? card.collectorNumber ?? card.collector_number;
  const finish = result.finish ?? cardFinish(card);
  const patch = {
    forSale: true,
    listingPrice: Number(result.listingPrice),
    listingId: result.listingId,
    listedInstanceId: result.instanceId ?? null,
  };
  setListingPatch(setCode, collectorNumber, finish, patch);
  applyListingPatchToCards([card], setCode, collectorNumber, finish, patch);
  return patch;
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

function cardLocationsOwnedCount(card) {
  if (!Array.isArray(card?.locations) || !card.locations.length) {
    return null;
  }
  return card.locations.reduce(
    (sum, location) => sum + (Number(location.count) || 0),
    0,
  );
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
  if (isDeckScopeCard(card)) {
    return Number(card.ownedQty) || 0;
  }
  const finishCount = finishOwnedCount(finishDataForCard(card));
  if (finishCount != null) {
    return finishCount;
  }
  const locationCount = cardLocationsOwnedCount(card);
  if (locationCount != null && locationCount > 0) {
    return locationCount;
  }
  if (card.purchaseValue != null && isEffectivelyOwned(card)) {
    return 1;
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
    const serverOwned = isDeckScopeCard(card)
      ? (Number(card?.ownedQty) || 0) > 0
      : card?.owned != null
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
  let locationSlug;
  if (delta > 0) {
    if (storageSlug) {
      locationSlug = storageSlug;
    } else {
      await ensureStorageLocations();
      const settings = await fetchPricingSettings();
      locationSlug = defaultStorageSlug(null, settings);
    }
  }
  const state = await api.adjustCardCopyCount({
    setCode: target.setCode,
    collectorNumber: target.collectorNumber,
    finish: target.finish,
    delta,
    locationSlug,
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
