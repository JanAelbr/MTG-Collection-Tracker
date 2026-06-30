<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { formatSetCountLabel, setShortName } from "../utils/format";
import { resolveSetIconUri } from "../utils/scryfall";

const props = defineProps({
  sets: { type: Array, default: () => [] },
  activeSetCode: { type: String, default: "" },
  showFavorites: { type: Boolean, default: false },
});

const emit = defineEmits(["select", "toggleFavorite"]);

const galleryRef = ref(null);

const visibleSets = computed(() => props.sets.filter((set) => set?.setCode));

function setIconUri(set) {
  return resolveSetIconUri(set);
}

function countLabel(set) {
  return formatSetCountLabel(set);
}

function scrollActiveIntoView(behavior = "smooth") {
  nextTick(() => {
    const root = galleryRef.value;
    if (!root || !props.activeSetCode) {
      return;
    }
    const active = root.querySelector(".set-gallery-card.active");
    active?.scrollIntoView({ block: "nearest", inline: "center", behavior });
  });
}

function onSelect(setCode) {
  emit("select", setCode);
}

function onToggleFavorite(event, set) {
  event.stopPropagation();
  emit("toggleFavorite", set);
}

watch(() => props.activeSetCode, () => scrollActiveIntoView());
watch(
  () => visibleSets.value.length,
  () => scrollActiveIntoView("auto"),
);

onMounted(() => scrollActiveIntoView("auto"));
</script>

<template>
  <div ref="galleryRef" class="set-gallery" aria-label="Sets">
    <button
      v-for="set in visibleSets"
      :key="set.setCode"
      type="button"
      class="set-gallery-card"
      :class="{ active: set.setCode === activeSetCode }"
      @click="onSelect(set.setCode)"
    >
      <button
        v-if="showFavorites && set.setCode !== 'All'"
        type="button"
        class="set-gallery-favorite"
        :class="{ 'is-favorite': set.favorite }"
        :aria-pressed="set.favorite ? 'true' : 'false'"
        :aria-label="set.favorite ? `Unfavourite ${setShortName(set)}` : `Favourite ${setShortName(set)}`"
        :title="set.favorite ? 'Unfavourite set' : 'Favourite set'"
        @click="onToggleFavorite($event, set)"
      >
        {{ set.favorite ? "★" : "☆" }}
      </button>

      <div class="set-gallery-icon-wrap">
        <img
          v-if="setIconUri(set)"
          :src="setIconUri(set)"
          :alt="`${set.setCode} set icon`"
          class="set-gallery-icon"
          loading="lazy"
        >
        <div v-else class="set-gallery-icon set-gallery-icon-placeholder" aria-hidden="true">
          All
        </div>
      </div>

      <div class="set-gallery-meta">
        <span class="set-gallery-code">{{ set.setCode === "All" ? "All" : set.setCode }}</span>
        <span class="set-gallery-name">{{ setShortName(set) }}</span>
        <span v-if="countLabel(set)" class="set-gallery-count">{{ countLabel(set) }}</span>
      </div>
    </button>
  </div>
</template>
