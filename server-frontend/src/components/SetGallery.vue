<script setup>
import "../styles/set-gallery.css";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import LoadingIndicator from "./LoadingIndicator.vue";
import {
  formatSetCountLabel,
  setCompletionPercent,
  setCompletionRarity,
  setDisplayName,
} from "../utils/format";
import { applySetGalleryIconFallback, resolveSetGalleryIconUri } from "../utils/scryfall";
import { useSetGalleryFilter } from "../composables/setGalleryFilter";

/** Max set tiles shown while searching (tracked + Scryfall candidates). */
const SET_GALLERY_SEARCH_LIMIT = 12;

const props = defineProps({
  sets: { type: Array, default: () => [] },
  activeSetCode: { type: String, default: "" },
  activeFamily: { type: Boolean, default: false },
  activeArtStyle: { type: String, default: "" },
  showFavorites: { type: Boolean, default: false },
  showReloadCatalog: { type: Boolean, default: true },
  reloadingSetCode: { type: String, default: "" },
  searchSets: { type: Array, default: () => [] },
  loadingSearchSets: { type: Boolean, default: false },
  addingSetCode: { type: String, default: "" },
});

const emit = defineEmits([
  "select",
  "select-family",
  "toggleFavorite",
  "reload-catalog",
]);

const { setGalleryFilter } = useSetGalleryFilter();
const galleryRef = ref(null);

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
  const trackedCodes = new Set();
  for (const set of roots) {
    for (const code of set.familyMembers || [set.setCode]) {
      if (code) {
        trackedCodes.add(String(code).toUpperCase());
      }
    }
    if (set.setCode) {
      trackedCodes.add(String(set.setCode).toUpperCase());
    }
  }

  const matchedSearch = (props.searchSets || [])
    .filter((set) => {
      if (!set?.setCode || trackedCodes.has(String(set.setCode).toUpperCase())) {
        return false;
      }
      return setMatchesQuery(set, query);
    })
    .map((set) => ({
      ...set,
      pendingImport: true,
      familyRoot: set.familyRoot || set.setCode,
      familyMembers: set.familyMembers || [set.setCode],
      isFamilyRoot: true,
      ownedCount: set.ownedCount ?? 0,
      catalogCount: set.catalogCount ?? 0,
    }));

  const combined = [...matchedTracked, ...matchedSearch];
  const limited = [];
  const seen = new Set();
  for (const set of combined) {
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

function familyTagMembers(set) {
  if (!set?.setCode || set.setCode === "All" || set.pendingImport) {
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
    });
}

function showFamilyChildren(set) {
  return Boolean(isCardActive(set) && familyTagMembers(set).length > 1);
}

function setIconUri(set) {
  return resolveSetGalleryIconUri(set);
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
  return set?.catalogCount;
}

function countLabel(set) {
  if (set?.pendingImport) {
    return "Add";
  }
  const owned = displayOwnedCount(set);
  const catalog = displayCatalogCount(set);
  if (owned == null || catalog == null) {
    return formatSetCountLabel(set);
  }
  return `${owned}/${catalog}`;
}

function completionRarityClass(set) {
  if (set?.pendingImport) {
    return "";
  }
  const owned = displayOwnedCount(set);
  const catalog = displayCatalogCount(set);
  const rarity = setCompletionRarity({ ownedCount: owned, catalogCount: catalog });
  return rarity ? `set-gallery-rarity--${rarity}` : "";
}

function isFamilyActive(set) {
  if (!set?.setCode || set.setCode === "All" || set.pendingImport) {
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
  if (!set?.setCode || set.pendingImport) {
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

function activeTitleLine(set) {
  const name = setDisplayName(set);
  const code = set.setCode;
  if (set.isFamilyRoot && (set.familyMembers || []).length > 1) {
    const suffix = props.activeFamily || isFamilyActive(set) ? " family" : "";
    if (!name || name === code) {
      return `${code}${suffix}`;
    }
    return `${code}${suffix} · ${name}`;
  }
  if (!name || name === code) {
    return code;
  }
  return `${code} · ${name}`;
}

function activeStatsLine(set) {
  if (set?.pendingImport) {
    return "Not in library yet";
  }
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

function canReload(set) {
  return (
    props.showReloadCatalog
    && set?.setCode
    && set.setCode !== "All"
    && !set.pendingImport
  );
}

function isReloading(set) {
  if (!props.reloadingSetCode) {
    return false;
  }
  const members = set.familyMembers || [set.setCode];
  return members.includes(props.reloadingSetCode) || props.reloadingSetCode === set.setCode;
}

function isAdding(set) {
  return Boolean(props.addingSetCode && set?.setCode === props.addingSetCode);
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
  if (!set?.setCode || props.addingSetCode) {
    return;
  }
  emit("select", set.setCode);
}

function onSelectMember(setCode) {
  if (props.addingSetCode) {
    return;
  }
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

function onToggleFavorite(event, set) {
  event.stopPropagation();
  if (set?.pendingImport) {
    return;
  }
  emit("toggleFavorite", set);
}

function onReload(event, set) {
  event.stopPropagation();
  emit("reload-catalog", set);
}

watch(() => props.activeSetCode, positionActiveSet);
watch(() => props.activeFamily, positionActiveSet);
watch(
  () => visibleFamilies.value.map((set) => set.setCode).join("|"),
  positionActiveSet,
);

onMounted(positionActiveSet);
</script>

<template>
  <div class="set-gallery-stack">
    <div
      ref="galleryRef"
      class="set-gallery"
      aria-label="Set families"
    >
      <div
        v-for="set in visibleFamilies"
        :key="set.setCode"
        class="set-gallery-card"
        :class="{
          active: isCardActive(set),
          'set-gallery-card--all': set.setCode === 'All',
          'set-gallery-card--expanded': showFamilyChildren(set),
          'set-gallery-card--pending': set.pendingImport,
          'is-importing': isAdding(set),
        }"
        role="button"
        tabindex="0"
        :aria-label="set.pendingImport
          ? `Add and select ${setDisplayName(set) || set.setCode}`
          : `Select ${setDisplayName(set) || set.setCode}`"
        :aria-current="isCardActive(set) ? 'true' : undefined"
        :aria-busy="isAdding(set) ? 'true' : undefined"
        @click="onSelectFamilyOrSet(set)"
        @keydown="onCardKeydown($event, set)"
      >
        <div class="set-gallery-card-main">
          <div v-if="isAdding(set)" class="set-gallery-importing" aria-live="polite">
            <LoadingIndicator compact :label="`Adding ${set.setCode}…`" />
          </div>

          <template v-else>
            <button
              v-if="showFavorites && set.setCode !== 'All' && !set.pendingImport"
              type="button"
              class="set-gallery-favorite set-gallery-favorite--left"
              :class="{ 'is-favorite': set.favorite }"
              :aria-pressed="set.favorite ? 'true' : 'false'"
              :aria-label="set.favorite ? `Unfavourite ${setDisplayName(set) || set.setCode}` : `Favourite ${setDisplayName(set) || set.setCode}`"
              :title="set.favorite ? 'Unfavourite set' : 'Favourite set'"
              @click.stop="onToggleFavorite($event, set)"
            >
              {{ set.favorite ? "★" : "☆" }}
            </button>

            <button
              v-if="canReload(set)"
              type="button"
              class="set-gallery-reload"
              :class="{ 'is-loading': isReloading(set) }"
              :aria-label="`Reload ${set.setCode} family catalog from Scryfall`"
              :aria-busy="isReloading(set) ? 'true' : 'false'"
              title="Reload family catalog from Scryfall"
              @click.stop="onReload($event, set)"
            >
              <span v-if="isReloading(set)" class="loading-spinner set-gallery-reload-spinner" aria-hidden="true" />
              <span v-else aria-hidden="true">↻</span>
            </button>

            <div class="set-gallery-icon-wrap">
              <img
                v-if="setIconUri(set)"
                :src="setIconUri(set)"
                :alt="`${set.setCode} set icon`"
                class="set-gallery-icon"
                loading="lazy"
                @error="onSetIconError($event, set)"
              >
              <div v-else class="set-gallery-icon set-gallery-icon-placeholder" aria-hidden="true">
                All
              </div>
            </div>

            <div class="set-gallery-meta">
              <template v-if="isCardActive(set) && set.setCode !== 'All'">
                <span
                  class="set-gallery-title"
                  :class="completionRarityClass(set)"
                  :title="activeTitleLine(set)"
                >
                  {{ activeTitleLine(set) }}
                </span>
                <span v-if="activeStatsLine(set)" class="set-gallery-stats">{{ activeStatsLine(set) }}</span>
              </template>
              <template v-else>
                <span class="set-gallery-code" :class="completionRarityClass(set)">
                  {{ set.setCode === "All" ? "All" : set.setCode }}
                </span>
                <span v-if="countLabel(set)" class="set-gallery-count">{{ countLabel(set) }}</span>
              </template>
            </div>
          </template>
        </div>

        <div
          v-if="showFamilyChildren(set)"
          class="set-gallery-subtiles"
          @click.stop
        >
          <button
            v-for="member in familyTagMembers(set)"
            :key="member.setCode"
            type="button"
            class="set-gallery-subtile"
            :class="{
              active: isSetActive(member),
              'set-gallery-subtile--root': member.setCode === set.setCode,
            }"
            :aria-pressed="isSetActive(member) ? 'true' : 'false'"
            :aria-label="`Select ${member.setCode}`"
            :title="setDisplayName(member) || member.setCode"
            @click.stop="onSelectMember(member.setCode)"
            @keydown="onMemberKeydown($event, member.setCode)"
          >
            <img
              v-if="setIconUri(member)"
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
    </div>
    <p
      v-if="setGalleryFilter.trim() && loadingSearchSets && !visibleFamilies.length"
      class="set-gallery-search-hint"
    >
      Searching sets…
    </p>
  </div>
</template>
