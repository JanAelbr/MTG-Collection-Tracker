<script setup>
import { computed, ref, watch } from "vue";
import { COLLECTION_RARITY_LABELS } from "../utils/collectionRarities";
import { mtgVectorsCardSetIconUri } from "../utils/mtgVectors";
import { scryfallSetIconUri } from "../utils/scryfall";

const props = defineProps({
  setCode: { type: String, default: "" },
  rarity: { type: String, default: "" },
  /** rarity = tinted by print rarity; generic = Scryfall monochrome set icon */
  variant: {
    type: String,
    default: "rarity",
    validator: (value) => ["rarity", "generic"].includes(value),
  },
  size: { type: Number, default: 14 },
});

const usedFallback = ref(false);

const primarySrc = computed(() => {
  if (props.variant === "generic") {
    return scryfallSetIconUri(props.setCode);
  }
  return (
    mtgVectorsCardSetIconUri(props.setCode, props.rarity)
    || scryfallSetIconUri(props.setCode)
  );
});

const src = computed(() => {
  if (usedFallback.value) {
    return scryfallSetIconUri(props.setCode);
  }
  return primarySrc.value;
});

const title = computed(() => {
  const code = String(props.setCode || "").trim().toUpperCase();
  if (!code) {
    return "";
  }
  if (props.variant === "generic") {
    return code;
  }
  const rarityKey = String(props.rarity || "").trim().toLowerCase();
  const rarityLabel = COLLECTION_RARITY_LABELS[rarityKey];
  return rarityLabel ? `${code} · ${rarityLabel}` : code;
});

const imgStyle = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
}));

watch(
  () => [props.setCode, props.rarity, props.variant],
  () => {
    usedFallback.value = false;
  },
);

function onError(event) {
  const fallback = scryfallSetIconUri(props.setCode);
  if (!fallback || usedFallback.value || src.value === fallback) {
    if (event?.target) {
      event.target.style.display = "none";
    }
    return;
  }
  usedFallback.value = true;
}
</script>

<template>
  <img
    v-if="src"
    class="card-set-symbol"
    :class="`card-set-symbol--${variant}`"
    :src="src"
    alt=""
    loading="lazy"
    decoding="async"
    :width="size"
    :height="size"
    :style="imgStyle"
    :title="title"
    :aria-label="title"
    @error="onError"
  >
</template>
