<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { formatSetCountLabel, setCompletionRarity, setDisplayName } from "../utils/format";
import { applySetGalleryIconFallback, resolveSetGalleryIconUri } from "../utils/scryfall";

const props = defineProps({
  sets: { type: Array, default: () => [] },
  activeSetCode: { type: String, default: "" },
  showFavorites: { type: Boolean, default: false },
  manageSets: { type: Boolean, default: false },
  showReloadCatalog: { type: Boolean, default: true },
  deletingSetCode: { type: String, default: "" },
  reloadingSetCode: { type: String, default: "" },
});

const emit = defineEmits(["select", "toggleFavorite", "add-set", "remove-set", "reload-catalog"]);

const galleryRef = ref(null);

const visibleSets = computed(() => props.sets.filter((set) => set?.setCode));

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
  if (isDeleting(set)) {
    return;
  }
  emit("remove-set", set);
}

function onReload(event, set) {
  event.stopPropagation();
  if (isReloading(set)) {
    return;
  }
  emit("reload-catalog", set);
}

watch(() => props.activeSetCode, positionActiveSet);
watch(
  () => visibleSets.value.map((set) => set.setCode).join("|"),
  positionActiveSet,
);

onMounted(positionActiveSet);
</script>

<template>
  <div ref="galleryRef" class="set-gallery" aria-label="Sets">
    <div
      v-for="set in visibleSets"
      :key="set.setCode"
      class="set-gallery-card"
      :class="{
        active: set.setCode === activeSetCode,
        'has-delete-action': canDelete(set),
      }"
      role="button"
      tabindex="0"
      :aria-label="`Select ${setDisplayName(set) || set.setCode}`"
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
        :disabled="isReloading(set)"
        :aria-label="`Reload ${set.setCode} catalog from Scryfall`"
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
        :disabled="isDeleting(set)"
        :aria-label="`Remove set ${set.setCode}`"
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

      <div class="set-gallery-meta">
        <span class="set-gallery-code" :class="completionRarityClass(set)">
          {{ set.setCode === "All" ? "All" : set.setCode }}
        </span>
        <span v-if="countLabel(set)" class="set-gallery-count">{{ countLabel(set) }}</span>
      </div>
    </div>

    <button
      v-if="manageSets"
      type="button"
      class="set-gallery-card set-gallery-card--add"
      aria-label="Add set"
      @click="emit('add-set')"
    >
      <div class="set-gallery-icon-wrap">
        <span class="set-gallery-add-icon" aria-hidden="true">+</span>
      </div>
      <div class="set-gallery-meta">
        <span class="set-gallery-code">Add</span>
        <span class="set-gallery-name">New set</span>
      </div>
    </button>
  </div>
</template>
