<script setup>
import { computed, ref, watch } from "vue";
import { COLLECTION_RARITY_LABELS } from "../utils/collectionRarities";
import { mtgVectorsCardSetIconUri } from "../utils/mtgVectors";
import { scryfallSetIconUri, setFamilyRootCode } from "../utils/scryfall";

const props = defineProps({
  setCode: { type: String, default: "" },
  familyRoot: { type: String, default: "" },
  /** Preferred icon URL (e.g. API iconUri); used after rarity vectors when variant is rarity. */
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

const rarityKey = computed(() => String(props.rarity || "").trim().toLowerCase());

const rootCode = computed(() =>
  setFamilyRootCode({
    setCode: props.setCode,
    familyRoot: props.familyRoot,
  }),
);

function uniqueUrls(urls) {
  const seen = new Set();
  return urls.filter((url) => {
    if (!url || seen.has(url)) {
      return false;
    }
    seen.add(url);
    return true;
  });
}

const candidates = computed(() => {
  const code = String(props.setCode || "").trim().toUpperCase();
  if (!code || code === "ALL") {
    return [];
  }
  const root = rootCode.value;
  const preferred = String(props.iconUri || "").trim();
  const urls = [];

  if (props.variant === "rarity") {
    // Prefer colored rarity vectors (own set, then family root) before any
    // monochrome Scryfall / API icons — otherwise a successful Scryfall load
    // masks the rarity tint.
    const vectorOwn = mtgVectorsCardSetIconUri(code, props.rarity);
    const vectorRoot = root && root !== code
      ? mtgVectorsCardSetIconUri(root, props.rarity)
      : null;
    if (props.preferFamilyRoot && vectorRoot) {
      urls.push(vectorRoot, vectorOwn);
    } else {
      urls.push(vectorOwn, vectorRoot);
    }
    if (preferred && !preferred.includes("mtg-vectors")) {
      // Keep API URI as a late fallback only when it is not already a vector.
      urls.push(preferred);
    } else if (preferred) {
      urls.push(preferred);
    }
    urls.push(scryfallSetIconUri(code));
    if (root && root !== code) {
      urls.push(scryfallSetIconUri(root));
    }
    return uniqueUrls(urls);
  }

  if (preferred) {
    urls.push(preferred);
  }
  if (props.preferFamilyRoot && root && root !== code) {
    urls.push(scryfallSetIconUri(root), scryfallSetIconUri(code));
  } else {
    urls.push(scryfallSetIconUri(code));
    if (root && root !== code) {
      urls.push(scryfallSetIconUri(root));
    }
  }
  return uniqueUrls(urls);
});

const src = computed(() => candidates.value[fallbackIndex.value] || "");

const isScryfallFallback = computed(() => {
  const current = src.value || "";
  return current.includes("svgs.scryfall.io");
});

const title = computed(() => {
  const code = String(props.setCode || "").trim().toUpperCase();
  if (!code) {
    return "";
  }
  if (props.variant === "generic") {
    return code;
  }
  const rarityLabel = COLLECTION_RARITY_LABELS[rarityKey.value];
  return rarityLabel ? `${code} · ${rarityLabel}` : code;
});

const imgStyle = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
}));

const imgClass = computed(() => {
  const classes = [`card-set-symbol--${props.variant}`];
  if (props.variant === "rarity" && rarityKey.value) {
    classes.push(`card-set-symbol-rarity--${rarityKey.value}`);
  }
  if (props.variant === "rarity" && isScryfallFallback.value) {
    classes.push("is-scryfall-fallback");
  }
  return classes;
});

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
    :class="imgClass"
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
