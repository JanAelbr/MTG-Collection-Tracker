<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import BrowseSelect from "./BrowseSelect.vue";
import LoadingIndicator from "./LoadingIndicator.vue";
import {
  formatSetCountLabel,
  setCompletionPercent,
  setCompletionRarity,
  setDisplayName,
} from "../utils/format";
import { applySetGalleryIconFallback, resolveSetGalleryIconUri } from "../utils/scryfall";
import { useSetGalleryFilter } from "../composables/setGalleryFilter";

const props = defineProps({
  sets: { type: Array, default: () => [] },
  activeSetCode: { type: String, default: "" },
  activeArtStyle: { type: String, default: "" },
  showFavorites: { type: Boolean, default: false },
  manageSets: { type: Boolean, default: false },
  showReloadCatalog: { type: Boolean, default: true },
  deletingSetCode: { type: String, default: "" },
  reloadingSetCode: { type: String, default: "" },
  availableSetOptions: { type: Array, default: () => [] },
  loadingAvailableSets: { type: Boolean, default: false },
  addingSetCode: { type: String, default: "" },
  collapsed: { type: Boolean, default: false },
});

const emit = defineEmits(["select", "toggleFavorite", "add-set", "remove-set", "reload-catalog"]);

const { setGalleryFilter } = useSetGalleryFilter();
const galleryRef = ref(null);

const visibleSets = computed(() => {
  const query = setGalleryFilter.value.trim().toLowerCase();
  return props.sets.filter((set) => {
    if (!set?.setCode) {
      return false;
    }
    if (!query || set.setCode === "All") {
      return true;
    }
    const haystack = [
      set.setCode,
      set.label,
      setDisplayName(set),
    ].filter(Boolean).join(" ").toLowerCase();
    return haystack.includes(query);
  });
});

const addSetDisabled = computed(() => Boolean(props.addingSetCode));

function setIconUri(set) {
  return resolveSetGalleryIconUri(set);
}

function onSetIconError(event, set) {
  applySetGalleryIconFallback(event.target, set);
}

function countLabel(set) {
  return formatSetCountLabel(set);
}

function completionRarityClass(set) {
  const rarity = setCompletionRarity(set);
  return rarity ? `set-gallery-rarity--${rarity}` : "";
}

function isActiveSet(set) {
  return set?.setCode && set.setCode === props.activeSetCode;
}

function missingCount(set) {
  if (set?.ownedCount == null || set?.catalogCount == null) {
    return null;
  }
  return Math.max(0, set.catalogCount - set.ownedCount);
}

function flooredCompletionPercent(set) {
  const percent = setCompletionPercent(set);
  if (percent == null) {
    return null;
  }
  return Math.floor(percent);
}

function activeTitleLine(set) {
  const name = setDisplayName(set);
  if (!name || name === set.setCode) {
    return set.setCode;
  }
  return `${set.setCode} · ${name}`;
}

function activeStatsLine(set) {
  const parts = [];
  if (set.ownedCount != null && set.catalogCount != null) {
    parts.push(`${set.ownedCount}/${set.catalogCount}`);
  }
  const floored = flooredCompletionPercent(set);
  if (floored != null) {
    parts.push(`${floored}%`);
  }
  const missing = missingCount(set);
  if (missing != null && missing > 0) {
    parts.push(`${missing} missing`);
  }
  if (props.activeArtStyle && isActiveSet(set)) {
    parts.push(props.activeArtStyle);
  }
  return parts.join(" · ");
}

function canDelete(set) {
  if (!props.manageSets || !set?.setCode || set.setCode === "All") {
    return false;
  }
  return (set.ownedCount ?? 0) === 0;
}

function canReload(set) {
  return props.showReloadCatalog && props.manageSets && set?.setCode && set.setCode !== "All";
}

function isReloading(set) {
  return props.reloadingSetCode && props.reloadingSetCode === set.setCode;
}

function isDeleting(set) {
  return props.deletingSetCode && props.deletingSetCode === set.setCode;
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

function onSelect(setCode) {
  emit("select", setCode);
}

function onCardKeydown(event, setCode) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    onSelect(setCode);
  }
}

function onToggleFavorite(event, set) {
  event.stopPropagation();
  emit("toggleFavorite", set);
}

function onRemove(event, set) {
  event.stopPropagation();
  emit("remove-set", set);
}

function onReload(event, set) {
  event.stopPropagation();
  emit("reload-catalog", set);
}

function onAddSetSelect(setCode) {
  if (!setCode || props.addingSetCode) {
    return;
  }
  emit("add-set", setCode);
}

watch(() => props.activeSetCode, positionActiveSet);
watch(
  () => visibleSets.value.map((set) => set.setCode).join("|"),
  positionActiveSet,
);
watch(() => props.collapsed, positionActiveSet);

onMounted(positionActiveSet);
</script>

<template>
  <div
    ref="galleryRef"
    class="set-gallery"
    :class="{ 'set-gallery--collapsed': collapsed }"
    aria-label="Sets"
  >
    <div
      v-if="manageSets"
      class="set-gallery-add-slot"
      :class="{ 'is-loading': addingSetCode }"
    >
      <div v-if="addingSetCode" class="set-gallery-add-loading" aria-live="polite">
        <LoadingIndicator compact :label="`Adding ${addingSetCode}…`" />
      </div>
      <BrowseSelect
        v-else
        model-value=""
        class="set-gallery-add-select"
        :options="availableSetOptions"
        :disabled="addSetDisabled"
        filterable
        show-icons
        hide-arrows
        empty-icon-label="+"
        placeholder="Add"
        aria-label="Add set"
        portal-panel
        @update:model-value="onAddSetSelect"
      />
    </div>

    <div
      v-for="set in visibleSets"
      :key="set.setCode"
      class="set-gallery-card"
      :class="{
        active: isActiveSet(set),
        'has-delete-action': canDelete(set),
      }"
      role="button"
      tabindex="0"
      :aria-label="`Select ${setDisplayName(set) || set.setCode}`"
      :title="collapsed && !isActiveSet(set) ? (activeTitleLine(set) || set.setCode) : undefined"
      :aria-current="isActiveSet(set) ? 'true' : undefined"
      @click="onSelect(set.setCode)"
      @keydown="onCardKeydown($event, set.setCode)"
    >
      <button
        v-if="showFavorites && set.setCode !== 'All'"
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
        :aria-label="`Reload ${set.setCode} catalog from Scryfall`"
        :aria-busy="isReloading(set) ? 'true' : 'false'"
        title="Reload catalog from Scryfall"
        @click.stop="onReload($event, set)"
      >
        <span v-if="isReloading(set)" class="loading-spinner set-gallery-reload-spinner" aria-hidden="true" />
        <span v-else aria-hidden="true">↻</span>
      </button>

      <button
        v-if="canDelete(set)"
        type="button"
        class="set-gallery-delete"
        :class="{ 'is-loading': isDeleting(set) }"
        :aria-label="`Remove set ${set.setCode}`"
        :aria-busy="isDeleting(set) ? 'true' : 'false'"
        title="Remove set (catalog is kept)"
        @click.stop="onRemove($event, set)"
      >
        <span v-if="isDeleting(set)" class="loading-spinner set-gallery-delete-spinner" aria-hidden="true" />
        <span v-else aria-hidden="true">×</span>
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

      <div v-if="!collapsed || isActiveSet(set)" class="set-gallery-meta">
        <template v-if="isActiveSet(set) && collapsed">
          <span class="set-gallery-code" :class="completionRarityClass(set)">
            {{ set.setCode === "All" ? "All" : set.setCode }}
          </span>
          <span v-if="set.setCode !== 'All' && activeStatsLine(set)" class="set-gallery-stats">
            {{ activeStatsLine(set) }}
          </span>
        </template>
        <template v-else-if="isActiveSet(set) && set.setCode !== 'All'">
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
    </div>
  </div>
</template>
