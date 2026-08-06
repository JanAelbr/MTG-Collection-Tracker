<script setup>
import "../styles/set-gallery.css";
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { api, clearClientCache } from "../api";
import {
  formatSetCountLabel,
  setCompletionPercent,
  setCompletionRarity,
  setDisplayName,
  setShortName,
} from "../utils/format";
import { applySetGalleryIconFallback, resolveSetGalleryIconUri } from "../utils/scryfall";
import { isSetBrowserHiddenSubsetType } from "../utils/setBrowserSubsets";
import { useSetGalleryFilter } from "../composables/setGalleryFilter";

/** Max set tiles shown while searching. */
const SET_GALLERY_SEARCH_LIMIT = 12;

const props = defineProps({
  sets: { type: Array, default: () => [] },
  activeSetCode: { type: String, default: "" },
  activeFamily: { type: Boolean, default: false },
  activeArtStyle: { type: String, default: "" },
});

const emit = defineEmits([
  "select",
  "select-family",
  "sets-changed",
]);

const { setGalleryFilter, showSetBrowserSubsets } = useSetGalleryFilter();
const galleryRef = ref(null);
const reloadingSetCode = ref("");
const contextMenu = ref(null);
const menuRef = ref(null);

const setsByCode = computed(() => {
  const map = new Map();
  for (const set of props.sets) {
    if (set?.setCode) {
      map.set(set.setCode, set);
    }
  }
  return map;
});

function setMatchesQuery(set, query) {
  if (!query || set.setCode === "All") {
    return true;
  }
  const members = set.familyMembers || [set.setCode];
  const haystack = [
    set.setCode,
    set.label,
    set.name,
    setDisplayName(set),
    set.setType,
    ...members,
  ].filter(Boolean).join(" ").toLowerCase();
  return haystack.includes(query);
}

function isBrowserRoot(set) {
  if (!set?.setCode) {
    return false;
  }
  if (set.setCode === "All") {
    return true;
  }
  const root = set.familyRoot || set.setCode;
  return set.setCode === root;
}

function familyOwnedTotal(set) {
  if (set?.familyOwnedCount != null) {
    return Number(set.familyOwnedCount) || 0;
  }
  return Number(set?.ownedCount) || 0;
}

function rootMatchesQuery(set, query) {
  if (!query || set.setCode === "All") {
    return !query || set.setCode === "All";
  }
  if (setMatchesQuery(set, query)) {
    return true;
  }
  const members = set.familyMembers || [];
  return members.some((code) => {
    const member = setsByCode.value.get(code);
    return member ? setMatchesQuery(member, query) : String(code).toLowerCase().includes(query);
  });
}

const activeFamilyRoot = computed(() => {
  if (!props.activeSetCode || props.activeSetCode === "All") {
    return "";
  }
  const active = setsByCode.value.get(props.activeSetCode);
  if (active?.familyRoot) {
    return active.familyRoot;
  }
  for (const set of props.sets) {
    if (!set?.setCode || set.setCode === "All" || !isBrowserRoot(set)) {
      continue;
    }
    const members = set.familyMembers || [];
    if (members.includes(props.activeSetCode)) {
      return set.setCode;
    }
  }
  return props.activeSetCode;
});

function isPinnedRoot(set) {
  if (!set?.setCode || set.setCode === "All") {
    return set?.setCode === "All";
  }
  return (
    set.setCode === props.activeSetCode
    || set.setCode === activeFamilyRoot.value
    || (set.familyMembers || []).includes(props.activeSetCode)
  );
}

const visibleFamilies = computed(() => {
  const query = setGalleryFilter.value.trim().toLowerCase();
  const roots = props.sets.filter((set) => isBrowserRoot(set));

  if (!query) {
    return roots.filter((set) => {
      if (set.setCode === "All" || isPinnedRoot(set)) {
        return true;
      }
      return familyOwnedTotal(set) > 0;
    });
  }

  const matchedTracked = roots.filter((set) => rootMatchesQuery(set, query));
  const limited = [];
  const seen = new Set();
  for (const set of matchedTracked) {
    if (!set?.setCode || seen.has(set.setCode)) {
      continue;
    }
    seen.add(set.setCode);
    limited.push(set);
    if (limited.length >= SET_GALLERY_SEARCH_LIMIT) {
      break;
    }
  }
  return limited;
});

/** Flat gallery rows: set tiles, favourite divider, and year markers. */
const galleryItems = computed(() => {
  const families = visibleFamilies.value;
  const allTile = families.find((set) => set.setCode === "All");
  const rest = families.filter((set) => set.setCode !== "All");
  const favorites = rest.filter((set) => Boolean(set.favorite));
  const others = rest.filter((set) => !set.favorite);
  const items = [];
  if (allTile) {
    items.push({ type: "set", set: allTile, key: "All" });
  }
  for (const set of favorites) {
    items.push({ type: "set", set, key: set.setCode });
  }
  if (favorites.length && others.length) {
    items.push({
      type: "separator",
      key: "favorites-separator",
      ariaLabel: "Favourite sets",
    });
  }
  appendSetsWithYearMarkers(items, others, "other");
  return items;
});

function releaseYear(set) {
  const date = String(set?.releasedAt || "").trim();
  if (/^\d{4}/.test(date)) {
    return date.slice(0, 4);
  }
  return "";
}

function appendSetsWithYearMarkers(items, sets, keyPrefix) {
  let previousYear = null;
  for (const set of sets) {
    const year = releaseYear(set);
    if (year && year !== previousYear) {
      if (previousYear != null) {
        items.push({
          type: "separator",
          key: `${keyPrefix}-sep-${previousYear}-${year}`,
          ariaLabel: year,
        });
      }
      items.push({
        type: "year",
        year,
        key: `${keyPrefix}-year-${year}`,
      });
      previousYear = year;
    }
    items.push({ type: "set", set, key: set.setCode });
  }
}

function familyTagMembers(set) {
  if (!set?.setCode || set.setCode === "All") {
    return [];
  }
  const members = set.familyMembers || [];
  if (members.length <= 1) {
    return [];
  }
  const ordered = [
    set.setCode,
    ...members.filter((code) => code && code !== set.setCode),
  ];
  const seen = new Set();
  return ordered
    .filter((code) => {
      if (seen.has(code)) {
        return false;
      }
      seen.add(code);
      return true;
    })
    .map((code) => setsByCode.value.get(code) || {
      setCode: code,
      familyRoot: set.setCode,
      familyMembers: members,
    })
    .filter((member) => {
      if (showSetBrowserSubsets.value) {
        return true;
      }
      if (member.setCode === set.setCode || member.setCode === props.activeSetCode) {
        return true;
      }
      return !isSetBrowserHiddenSubsetType(member.setType);
    });
}

function showFamilyChildren(set) {
  return Boolean(isCardActive(set) && familyTagMembers(set).length > 1);
}

function setIconUri(set) {
  return resolveSetGalleryIconUri(set);
}

/** Icon shown on a family root tile — follows the selected subset when expanded. */
function cardIconSet(set) {
  if (isCardActive(set) && set.setCode !== "All") {
    return activeTitleSet(set);
  }
  return set;
}

function onSetIconError(event, set) {
  applySetGalleryIconFallback(event.target, set);
}

function displayOwnedCount(set) {
  if (
    props.activeFamily
    && set?.isFamilyRoot
    && set.familyOwnedCount != null
    && (set.setCode === props.activeSetCode || set.setCode === activeFamilyRoot.value)
  ) {
    return set.familyOwnedCount;
  }
  // Expanded family tile: show the selected subset's counts, not the root's.
  if (
    !props.activeFamily
    && set?.setCode
    && set.setCode === activeFamilyRoot.value
    && props.activeSetCode
    && props.activeSetCode !== "All"
    && props.activeSetCode !== set.setCode
  ) {
    const member = setsByCode.value.get(props.activeSetCode);
    if (member?.ownedCount != null) {
      return member.ownedCount;
    }
  }
  return set?.ownedCount;
}

function displayCatalogCount(set) {
  if (
    props.activeFamily
    && set?.isFamilyRoot
    && set.familyCatalogCount != null
    && (set.setCode === props.activeSetCode || set.setCode === activeFamilyRoot.value)
  ) {
    return set.familyCatalogCount;
  }
  if (
    !props.activeFamily
    && set?.setCode
    && set.setCode === activeFamilyRoot.value
    && props.activeSetCode
    && props.activeSetCode !== "All"
    && props.activeSetCode !== set.setCode
  ) {
    const member = setsByCode.value.get(props.activeSetCode);
    if (member?.catalogCount != null) {
      return member.catalogCount;
    }
  }
  return set?.catalogCount;
}

function countLabel(set) {
  const owned = displayOwnedCount(set);
  const catalog = displayCatalogCount(set);
  if (owned == null || catalog == null) {
    return formatSetCountLabel(set);
  }
  return `${owned}/${catalog}`;
}

function completionRarityClass(set) {
  const owned = displayOwnedCount(set);
  const catalog = displayCatalogCount(set);
  const rarity = setCompletionRarity({ ownedCount: owned, catalogCount: catalog });
  return rarity ? `set-gallery-rarity--${rarity}` : "";
}

function isFamilyActive(set) {
  if (!set?.setCode || set.setCode === "All") {
    return false;
  }
  if (props.activeFamily && (set.setCode === props.activeSetCode || set.setCode === activeFamilyRoot.value)) {
    return true;
  }
  return Boolean(
    !props.activeFamily
    && activeFamilyRoot.value === set.setCode
    && props.activeSetCode
    && props.activeSetCode !== "All"
    && props.activeSetCode !== set.setCode,
  );
}

function isSetActive(set) {
  if (!set?.setCode) {
    return false;
  }
  if (set.setCode === "All") {
    return props.activeSetCode === "All";
  }
  return !props.activeFamily && set.setCode === props.activeSetCode;
}

function isCardActive(set) {
  return isFamilyActive(set) || isSetActive(set);
}

function missingCount(set) {
  const owned = displayOwnedCount(set);
  const catalog = displayCatalogCount(set);
  if (owned == null || catalog == null) {
    return null;
  }
  return Math.max(0, catalog - owned);
}

function flooredCompletionPercent(set) {
  const percent = setCompletionPercent({
    ownedCount: displayOwnedCount(set),
    catalogCount: displayCatalogCount(set),
  });
  if (percent == null) {
    return null;
  }
  return Math.floor(percent);
}

function activeTitleSet(set) {
  if (
    props.activeSetCode
    && props.activeSetCode !== "All"
    && props.activeSetCode !== set.setCode
  ) {
    const member = setsByCode.value.get(props.activeSetCode);
    if (member) {
      return member;
    }
  }
  return set;
}

function activeTitleLine(set) {
  const selected = activeTitleSet(set);
  if (selected?.setCode === "All") {
    return "All sets";
  }
  return setShortName(selected) || selected?.setCode || "";
}

function activeStatsLine(set) {
  const parts = [];
  const owned = displayOwnedCount(set);
  const catalog = displayCatalogCount(set);
  if (owned != null && catalog != null) {
    parts.push(`${owned}/${catalog}`);
  }
  const floored = flooredCompletionPercent(set);
  if (floored != null) {
    parts.push(`${floored}%`);
  }
  const missing = missingCount(set);
  if (missing != null && missing > 0) {
    parts.push(`${missing} missing`);
  }
  if (props.activeArtStyle && isSetActive(set)) {
    parts.push(props.activeArtStyle);
  }
  return parts.join(" · ");
}

function positionActiveSet() {
  nextTick(() => {
    const root = galleryRef.value;
    if (!root || !props.activeSetCode) {
      return;
    }
    const active = root.querySelector(".set-gallery-card.active");
    if (!active) {
      return;
    }
    const rootWidth = root.clientWidth;
    if (!rootWidth) {
      return;
    }
    const targetScroll = active.offsetLeft - (rootWidth - active.offsetWidth) / 2;
    root.scrollLeft = Math.max(0, Math.min(targetScroll, root.scrollWidth - rootWidth));
  });
}

function onSelectFamilyOrSet(set) {
  if (!set?.setCode) {
    return;
  }
  emit("select", set.setCode);
}

function onSelectMember(setCode) {
  emit("select", setCode);
}

function onCardKeydown(event, set) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    onSelectFamilyOrSet(set);
  }
}

function onMemberKeydown(event, setCode) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    onSelectMember(setCode);
  }
}

function closeContextMenu() {
  contextMenu.value = null;
}

function onCardContextMenu(event, set) {
  if (!set?.setCode || set.setCode === "All") {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  const pad = 8;
  const menuWidth = 200;
  const menuHeight = 96;
  const x = Math.min(event.clientX, window.innerWidth - menuWidth - pad);
  const y = Math.min(event.clientY, window.innerHeight - menuHeight - pad);
  contextMenu.value = {
    set,
    x: Math.max(pad, x),
    y: Math.max(pad, y),
  };
}

const menuStyle = computed(() => {
  if (!contextMenu.value) {
    return {};
  }
  return {
    left: `${contextMenu.value.x}px`,
    top: `${contextMenu.value.y}px`,
  };
});

const contextMenuSet = computed(() => contextMenu.value?.set || null);

async function onToggleFavorite() {
  const set = contextMenuSet.value;
  closeContextMenu();
  if (!set?.setCode) {
    return;
  }
  try {
    const result = await api.toggleManagerSetFavorite(set.setCode);
    clearClientCache();
    emit("sets-changed", {
      sets: result?.sets,
      setCode: set.setCode,
      favorite: result?.favorite,
    });
  } catch (error) {
    window.alert(error.message || "Could not update favourite set.");
  }
}

async function onRefreshCatalog() {
  const set = contextMenuSet.value;
  closeContextMenu();
  if (!set?.setCode || reloadingSetCode.value) {
    return;
  }
  reloadingSetCode.value = set.setCode;
  try {
    await api.reloadManagerSetCatalog(set.setCode);
    clearClientCache();
    const managerPayload = await api.listManagerSets();
    emit("sets-changed", {
      sets: managerPayload?.sets,
      setCode: set.setCode,
      catalogReloaded: true,
    });
  } catch (error) {
    window.alert(error.message || "Could not reload catalog.");
  } finally {
    reloadingSetCode.value = "";
  }
}

function onDocumentPointerDown(event) {
  if (!contextMenu.value) {
    return;
  }
  if (menuRef.value?.contains(event.target)) {
    return;
  }
  closeContextMenu();
}

function onDocumentKeydown(event) {
  if (event.key === "Escape") {
    closeContextMenu();
  }
}

watch(() => props.activeSetCode, positionActiveSet);
watch(() => props.activeFamily, positionActiveSet);
watch(
  () => galleryItems.value.map((item) => item.key).join("|"),
  positionActiveSet,
);

onMounted(() => {
  positionActiveSet();
  document.addEventListener("pointerdown", onDocumentPointerDown, true);
  document.addEventListener("keydown", onDocumentKeydown);
});

onUnmounted(() => {
  document.removeEventListener("pointerdown", onDocumentPointerDown, true);
  document.removeEventListener("keydown", onDocumentKeydown);
});
</script>

<template>
  <div class="set-gallery-stack">
    <div
      ref="galleryRef"
      class="set-gallery"
      aria-label="Set families"
    >
      <template v-for="item in galleryItems" :key="item.key">
        <div
          v-if="item.type === 'separator'"
          class="set-gallery-separator"
          role="separator"
          :aria-label="item.ariaLabel || 'Sets'"
        />
        <span
          v-else-if="item.type === 'year'"
          class="set-gallery-year-label"
          aria-hidden="true"
        >
          {{ item.year }}
        </span>
        <div
          v-else
          class="set-gallery-card"
          :class="{
            active: isCardActive(item.set),
            'set-gallery-card--all': item.set.setCode === 'All',
            'set-gallery-card--expanded': showFamilyChildren(item.set),
            'set-gallery-card--favorite': item.set.favorite,
            'is-reloading': reloadingSetCode === item.set.setCode,
          }"
          role="button"
          tabindex="0"
          :aria-label="`Select ${isCardActive(item.set) && item.set.setCode !== 'All' ? activeTitleLine(item.set) : (setDisplayName(item.set) || item.set.setCode)}`"
          :aria-current="isCardActive(item.set) ? 'true' : undefined"
          :aria-busy="reloadingSetCode === item.set.setCode ? 'true' : undefined"
          :title="isCardActive(item.set) && item.set.setCode !== 'All' ? activeTitleLine(item.set) : undefined"
          @click="onSelectFamilyOrSet(item.set)"
          @keydown="onCardKeydown($event, item.set)"
          @contextmenu="onCardContextMenu($event, item.set)"
        >
          <div
            v-if="reloadingSetCode === item.set.setCode"
            class="set-gallery-reloading"
            aria-hidden="true"
          >
            <span class="loading-spinner set-gallery-reload-spinner" />
          </div>

          <div class="set-gallery-card-main">
            <div class="set-gallery-icon-wrap">
              <img
                v-if="setIconUri(cardIconSet(item.set))"
                :key="`${item.set.setCode}:${cardIconSet(item.set).setCode}:${setIconUri(cardIconSet(item.set))}`"
                :src="setIconUri(cardIconSet(item.set))"
                :alt="`${cardIconSet(item.set).setCode} set icon`"
                class="set-gallery-icon"
                loading="lazy"
                @error="onSetIconError($event, cardIconSet(item.set))"
              >
              <div v-else class="set-gallery-icon set-gallery-icon-placeholder" aria-hidden="true">
                All
              </div>
            </div>

            <div class="set-gallery-meta">
              <template v-if="isCardActive(item.set) && item.set.setCode !== 'All'">
                <span
                  class="set-gallery-title"
                  :class="completionRarityClass(item.set)"
                  :title="activeTitleLine(item.set)"
                >
                  {{ activeTitleLine(item.set) }}
                </span>
                <span v-if="activeStatsLine(item.set)" class="set-gallery-stats">{{ activeStatsLine(item.set) }}</span>
              </template>
              <template v-else>
                <span class="set-gallery-code" :class="completionRarityClass(item.set)">
                  <span v-if="item.set.favorite" class="set-gallery-favorite-mark" aria-hidden="true">★</span>
                  {{ item.set.setCode === "All" ? "All" : item.set.setCode }}
                </span>
                <span v-if="countLabel(item.set)" class="set-gallery-count">{{ countLabel(item.set) }}</span>
              </template>
            </div>
          </div>

          <div
            v-if="showFamilyChildren(item.set)"
            class="set-gallery-subtiles"
            @click.stop
          >
            <button
              v-for="member in familyTagMembers(item.set)"
              :key="member.setCode"
              type="button"
              class="set-gallery-subtile"
              :class="{
                active: isSetActive(member),
                'set-gallery-subtile--root': member.setCode === item.set.setCode,
              }"
              :aria-pressed="isSetActive(member) ? 'true' : 'false'"
              :aria-label="`Select ${member.setCode}`"
              :title="setDisplayName(member) || member.setCode"
              @click.stop="onSelectMember(member.setCode)"
              @keydown="onMemberKeydown($event, member.setCode)"
            >
              <img
                v-if="setIconUri(member)"
                :key="`${member.setCode}:${setIconUri(member)}`"
                :src="setIconUri(member)"
                alt=""
                class="set-gallery-subtile-icon"
                loading="lazy"
                @error="onSetIconError($event, member)"
              >
              <span class="set-gallery-subtile-code">{{ member.setCode }}</span>
            </button>
          </div>
        </div>
      </template>
    </div>

    <Teleport to="body">
      <div
        v-if="contextMenuSet"
        ref="menuRef"
        class="card-context-menu set-gallery-context-menu"
        role="menu"
        :style="menuStyle"
        @click.stop
        @contextmenu.prevent
      >
        <button
          type="button"
          class="card-context-menu-item"
          role="menuitem"
          @click="onToggleFavorite"
        >
          {{ contextMenuSet.favorite ? "Unfavourite set" : "Favourite set" }}
        </button>
        <button
          type="button"
          class="card-context-menu-item"
          role="menuitem"
          :disabled="Boolean(reloadingSetCode)"
          @click="onRefreshCatalog"
        >
          Refresh catalog
        </button>
      </div>
    </Teleport>
  </div>
</template>
