import { computed, ref } from "vue";
import { api } from "../api";
import { profileColor } from "../utils/profileColors";
import { migrateLegacyProfileStorage, removeProfileStorage } from "../utils/profileStorage";
import {
  forgetProfileId,
  getActiveProfileId,
  hasTabProfile,
  rememberedProfileId,
  setActiveProfileId,
} from "../utils/profileSession";

export const profiles = ref([]);
export const colors = ref([]);
export const switchingTo = ref(null);
export const profilesReady = ref(false);

const activeId = ref(null);

export const activeProfile = computed(
  () => profiles.value.find((profile) => profile.id === activeId.value) || null,
);
export const hasMultipleProfiles = computed(() => profiles.value.length > 1);

export function profileSummary(profile) {
  const stats = profile?.stats;
  if (!stats) {
    return "";
  }
  const cards = Number(stats.ownedCopies || stats.ownedPrints || 0);
  const decks = Number(stats.decks || 0);
  const cardLabel = `${cards} card${cards === 1 ? "" : "s"}`;
  const deckLabel = `${decks} deck${decks === 1 ? "" : "s"}`;
  return `${cardLabel} · ${deckLabel}`;
}

function remember(profileId, { persist = true } = {}) {
  activeId.value = profileId || null;
  setActiveProfileId(profileId, { remember: persist });
  applyProfileAccent(profiles.value.find((profile) => profile.id === profileId));
}

export function applyProfileAccent(profile) {
  const accent = profileColor(profile?.color).accent;
  document.documentElement.style.setProperty("--profile-accent", accent);
}

function applyList(payload) {
  profiles.value = payload?.profiles || [];
  if (Array.isArray(payload?.colors) && payload.colors.length) {
    colors.value = payload.colors;
  }
}

export async function refreshProfiles({ stats = false } = {}) {
  const payload = await api.listProfiles({ stats });
  applyList(payload);
  return payload;
}

/**
 * Resolve the tab's profile before the app mounts.
 * Returns needsPicker when several profiles exist and this browser has not
 * chosen one yet.
 */
export async function initActiveProfile() {
  const payload = await refreshProfiles();
  const known = new Set(profiles.value.map((profile) => profile.id));
  const remembered = rememberedProfileId();
  const fallback = profiles.value.find((profile) => profile.id === payload.defaultProfileId)
    || profiles.value[0]
    || null;
  const chosen = (remembered && known.has(remembered))
    ? profiles.value.find((profile) => profile.id === remembered)
    : fallback;
  const needsPicker = profiles.value.length > 1 && !(remembered && known.has(remembered));
  if (chosen) {
    remember(chosen.id, { persist: !needsPicker });
    if (!needsPicker) {
      migrateLegacyProfileStorage(chosen.id);
    }
  }
  profilesReady.value = true;
  return { needsPicker, profile: chosen };
}

export function sectionRoot(path = window.location.pathname) {
  if (path.startsWith("/collection") || path.startsWith("/storage") || path.startsWith("/decks")) {
    return path.startsWith("/collection/decks") || path.startsWith("/decks")
      ? "/collection/decks"
      : "/collection/all";
  }
  if (path.startsWith("/settings")) {
    return "/settings/display";
  }
  if (path.startsWith("/print")) {
    return "/print/cards";
  }
  if (path.startsWith("/stats")) {
    return "/stats";
  }
  if (path.startsWith("/sell")) {
    return "/sell";
  }
  return "/";
}

export async function switchProfile(profileId, { href } = {}) {
  const profile = profiles.value.find((item) => item.id === profileId);
  if (!profile || profile.id === getActiveProfileId()) {
    return;
  }
  remember(profile.id);
  migrateLegacyProfileStorage(profile.id);
  switchingTo.value = profile;
  try {
    await api.activateProfile(profile.id);
  } catch {
    // The reload still lands on the chosen profile via the stored id.
  }
  window.location.assign(href || sectionRoot());
}

export async function createProfile(input) {
  const created = await api.createProfile(input);
  await refreshProfiles({ stats: true });
  return created;
}

export async function updateProfile(profileId, patch) {
  const updated = await api.updateProfile(profileId, patch);
  await refreshProfiles({ stats: true });
  if (updated?.id === activeId.value) {
    applyProfileAccent(updated);
  }
  return updated;
}

export async function deleteProfile(profileId) {
  const payload = await api.deleteProfile(profileId);
  removeProfileStorage(profileId);
  forgetProfileId(profileId);
  applyList(payload);
  if (activeId.value === profileId) {
    const next = payload.defaultProfileId || profiles.value[0]?.id;
    if (next) {
      await switchProfile(next, { href: "/" });
    }
  }
  return payload;
}

export function isActiveProfile(profileId) {
  return profileId === activeId.value;
}

export { hasTabProfile };
