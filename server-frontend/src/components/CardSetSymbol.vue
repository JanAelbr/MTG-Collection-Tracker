<script setup>
import { computed, ref, watch } from "vue";
import { COLLECTION_RARITY_LABELS } from "../utils/collectionRarities";
import { mtgVectorsCardSetIconUri } from "../utils/mtgVectors";
import { scryfallSetIconUri, setFamilyRootCode } from "../utils/scryfall";

const props = defineProps({
  setCode: { type: String, default: "" },
  familyRoot: { type: String, default: "" },
  /** Preferred icon URL (e.g. API iconUri); tried before generated candidates. */
  iconUri: { type: String, default: "" },
  rarity: { type: String, default: "" },
  /** rarity = tinted by print rarity; generic = Scryfall monochrome set icon */
  variant: {
    type: String,
    default: "rarity",
    validator: (value) => ["rarity", "generic"].includes(value),
  },
  size: { type: Number, default: 14 },
  /**
   * When true and familyRoot differs from setCode, try the family-root icon
   * before the subset's own SVG (many subsets have missing/placeholder marks).
   */
  preferFamilyRoot: { type: Boolean, default: false },
});

const fallbackIndex = ref(0);

const rootCode = computed(() =>
  setFamilyRootCode({
    setCode: props.setCode,
    familyRoot: props.familyRoot,
  }),
);

const candidates = computed(() => {
  const code = String(props.setCode || "").trim().toUpperCase();
  if (!code || code === "ALL") {
    return [];
  }
  const root = rootCode.value;
  const preferred = String(props.iconUri || "").trim();
  const urls = [];
  if (preferred) {
    urls.push(preferred);
  }
  const own = [];
  const parent = [];
  if (props.variant === "rarity") {
    own.push(mtgVectorsCardSetIconUri(code, props.rarity));
  }
  own.push(scryfallSetIconUri(code));
  if (root && root !== code) {
    if (props.variant === "rarity") {
      parent.push(mtgVectorsCardSetIconUri(root, props.rarity));
    }
    parent.push(scryfallSetIconUri(root));
  }
  if (props.preferFamilyRoot && parent.length) {
    urls.push(...parent, ...own);
  } else {
    urls.push(...own, ...parent);
  }
  const seen = new Set();
  return urls.filter((url) => {
    if (!url || seen.has(url)) {
      return false;
    }
    seen.add(url);
    return true;
  });
});

const src = computed(() => candidates.value[fallbackIndex.value] || "");

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
  () => [props.setCode, props.familyRoot, props.iconUri, props.rarity, props.variant, props.preferFamilyRoot],
  () => {
    fallbackIndex.value = 0;
  },
);

function onError(event) {
  if (fallbackIndex.value + 1 < candidates.value.length) {
    fallbackIndex.value += 1;
    return;
  }
  if (event?.target) {
    event.target.style.display = "none";
  }
}
</script>

<template>
  <img
    v-if="src"
    class="card-set-symbol"
    :class="`card-set-symbol--${variant}`"
    :src="src"
    alt=""
    loading="eager"
    decoding="async"
    :width="size"
    :height="size"
    :style="imgStyle"
    :title="title"
    :aria-label="title"
    @error="onError"
  >
</template>
