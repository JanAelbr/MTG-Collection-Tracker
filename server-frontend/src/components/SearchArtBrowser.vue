<script setup>
import { computed, nextTick, ref, watch } from "vue";
import CardInteractiveImage from "./CardInteractiveImage.vue";
import { isEffectivelyOwned, ownershipRevision } from "../composables/cardContextMenu";
import { formatEuro } from "../utils/format";
import {
  FINISH_ETCHED,
  FINISH_FOIL,
  FINISH_NONFOIL,
  cardFinish,
  cardRouteQuery,
  finishLabel,
  normalizeFinish,
} from "../utils/finishes";

const props = defineProps({
  name: { type: String, default: "" },
  variants: { type: Array, default: () => [] },
  selectedIndex: { type: Number, default: 0 },
  setLabelFor: { type: Function, default: null },
  showRandom: { type: Boolean, default: true },
  compact: { type: Boolean, default: false },
});

const emit = defineEmits(["update:selectedIndex", "random", "close"]);

const panelRef = ref(null);
const listRef = ref(null);

const selectedVariant = computed(() => props.variants[props.selectedIndex] || null);

const selectedIsOwned = computed(() => {
  ownershipRevision.value;
  const card = selectedVariant.value;
  return card ? isEffectivelyOwned(card) : false;
});

const selectedRoute = computed(() => {
  const card = selectedVariant.value;
  if (!card) {
    return null;
  }
  return {
    name: "card",
    params: { setCode: card.setCode, collectorNumber: card.collectorNumber },
    query: cardRouteQuery(cardFinish(card)),
  };
});

const availableFinishes = computed(() => {
  const card = selectedVariant.value;
  if (!card) {
    return [];
  }
  const finishes = card.availableFinishes?.map((value) => normalizeFinish(value)) || [cardFinish(card)];
  return [FINISH_NONFOIL, FINISH_FOIL, FINISH_ETCHED].filter((finish) => finishes.includes(finish));
});

function setLabel(code) {
  if (props.setLabelFor) {
    return props.setLabelFor(code);
  }
  return code;
}

function variantKey(card, index) {
  return `${card.setCode}-${card.collectorNumber}-${card.artStyle || ""}-${index}`;
}

function thumbTitle(card) {
  return card.artStyle || props.name;
}

function valueForFinish(card, finish) {
  const values = card.finishValues || {};
  const normalized = normalizeFinish(finish);
  if (values[normalized] != null) {
    return values[normalized];
  }
  if (normalizeFinish(card.finish) === normalized) {
    return card.currentValue;
  }
  return null;
}

function selectVariant(index) {
  if (index < 0 || index >= props.variants.length) {
    return;
  }
  emit("update:selectedIndex", index);
}

function scrollSelectedIntoView() {
  nextTick(() => {
    const list = listRef.value;
    if (!list) {
      return;
    }
    const active = list.querySelector(".search-art-thumb.is-active");
    active?.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
  });
}

function scrollPanelIntoView() {
  nextTick(() => {
    panelRef.value?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  });
}

watch(
  () => props.selectedIndex,
  () => scrollSelectedIntoView(),
);

watch(
  () => [props.name, props.variants],
  () => {
    scrollSelectedIntoView();
    scrollPanelIntoView();
  },
);
</script>

<template>
  <section
    v-if="name && variants.length"
    ref="panelRef"
    class="table-panel collection-search-art-panel"
    :class="{ 'collection-search-art-panel--compact': compact }"
  >
    <div class="collection-search-art-header">
      <div>
        <h2 class="collection-search-art-title">{{ name }}</h2>
        <p class="collection-search-art-meta">
          {{ variants.length }} art{{ variants.length === 1 ? "" : "s" }} across sets
        </p>
      </div>
      <div class="collection-search-art-actions">
        <button
          v-if="showRandom"
          type="button"
          class="btn btn-secondary btn-small"
          @click="emit('random')"
        >
          Another random
        </button>
        <button type="button" class="btn btn-secondary btn-small" @click="emit('close')">
          Close
        </button>
      </div>
    </div>

    <div v-if="selectedVariant" class="collection-search-art-selected">
      <div class="collection-search-art-preview-image-wrap">
        <img
          v-if="compact && selectedVariant.imageUri"
          :src="selectedVariant.imageUri"
          :alt="name"
          loading="lazy"
          class="collection-search-art-preview-image"
        />
        <CardInteractiveImage
          v-else-if="selectedVariant.imageUri"
          :src="selectedVariant.imageUri"
          :alt="name"
          :card="selectedVariant"
          :show-details="false"
          img-class="collection-search-art-preview-image"
        />
        <div v-else class="collection-search-art-preview-empty">No image</div>
      </div>

      <div class="collection-search-art-details">
        <dl class="collection-search-art-details-list">
          <div class="collection-search-art-detail">
            <dt>Set</dt>
            <dd>{{ setLabel(selectedVariant.setCode) }}</dd>
          </div>
          <div class="collection-search-art-detail">
            <dt>Number</dt>
            <dd>#{{ String(selectedVariant.collectorNumber).padStart(3, "0") }}</dd>
          </div>
          <div v-if="selectedVariant.artStyle" class="collection-search-art-detail">
            <dt>Art style</dt>
            <dd>{{ selectedVariant.artStyle }}</dd>
          </div>
          <div v-if="selectedVariant.typeLine" class="collection-search-art-detail">
            <dt>Type</dt>
            <dd>{{ selectedVariant.typeLine }}</dd>
          </div>
          <div class="collection-search-art-detail">
            <dt>Owned</dt>
            <dd>{{ selectedIsOwned ? "Yes" : "No" }}</dd>
          </div>
          <div v-if="availableFinishes.length" class="collection-search-art-detail">
            <dt>Finishes</dt>
            <dd class="collection-search-art-finish-list">
              <span
                v-for="finish in availableFinishes"
                :key="finish"
                class="collection-search-art-finish"
              >
                {{ finishLabel(finish) }} · {{ formatEuro(valueForFinish(selectedVariant, finish)) }}
              </span>
            </dd>
          </div>
        </dl>
        <RouterLink
          v-if="selectedRoute"
          :to="selectedRoute"
          class="btn btn-secondary btn-small"
        >
          Open card page
        </RouterLink>
      </div>
    </div>

    <div ref="listRef" class="collection-search-art-thumbs">
      <button
        v-for="(variant, index) in variants"
        :key="variantKey(variant, index)"
        type="button"
        class="search-art-thumb"
        :class="{ 'is-active': index === selectedIndex }"
        :title="thumbTitle(variant)"
        :aria-label="thumbTitle(variant)"
        @click="selectVariant(index)"
      >
        <img
          v-if="variant.imageUri"
          :src="variant.imageUri"
          :alt="thumbTitle(variant)"
          class="search-art-thumb-image"
        />
        <div v-else class="search-art-thumb-image search-art-thumb-empty" />
      </button>
    </div>
  </section>
</template>
