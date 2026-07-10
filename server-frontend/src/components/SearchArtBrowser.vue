<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import CardInteractiveImage from "./CardInteractiveImage.vue";
import CardCopyControls from "./CardCopyControls.vue";
import CardVariantGallery from "./CardVariantGallery.vue";
import CollectionSetLink from "./CollectionSetLink.vue";
import { isEffectivelyOwned, ownershipRevision } from "../composables/cardContextMenu";
import { usePricingSettings } from "../composables/pricingSettings";
import { formatEuro } from "../utils/format";
import { valueForStrategy } from "../utils/priceStrategies";
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
  sidebar: { type: Boolean, default: false },
});

const emit = defineEmits(["update:selectedIndex", "random", "close", "ownership-changed"]);

const { settings: pricingSettings } = usePricingSettings();

const panelRef = ref(null);
const imageZoomOpen = ref(false);

const selectedVariant = computed(() => props.variants[props.selectedIndex] || null);
const useZoomPreview = computed(() => props.sidebar || props.compact);

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

const galleryCards = computed(() =>
  props.variants.map((card, index) => ({
    ...card,
    isCurrent: index === props.selectedIndex,
  })),
);

const showVariantGallery = computed(() => props.variants.length > 1);
const selectedFinish = computed(() => cardFinish(selectedVariant.value || {}));

function setLabel(code) {
  if (props.setLabelFor) {
    return props.setLabelFor(code);
  }
  return code;
}

function valueForFinish(card, finish) {
  const strategy = pricingSettings.value?.priceStrategy || "trend";
  const values = card.finishValues || {};
  const normalized = normalizeFinish(finish);
  const byStrategy = card.finishValuesByStrategy?.[normalized];
  if (byStrategy?.[strategy] != null) {
    return byStrategy[strategy];
  }
  if (values[normalized] != null) {
    return values[normalized];
  }
  if (normalizeFinish(card.finish ?? card.foil) === normalized) {
    return valueForStrategy(card, strategy);
  }
  return null;
}

function onGallerySelect(card) {
  const index = props.variants.findIndex(
    (variant) =>
      variant.setCode === card.setCode
      && String(variant.collectorNumber) === String(card.collectorNumber)
      && (variant.artStyle || "") === (card.artStyle || ""),
  );
  if (index >= 0) {
    emit("update:selectedIndex", index);
  }
}

function closeImageZoom() {
  imageZoomOpen.value = false;
}

function onImageZoomKeydown(event) {
  if (event.key === "Escape") {
    closeImageZoom();
  }
}

function scrollPanelIntoView() {
  if (props.sidebar) {
    return;
  }
  nextTick(() => {
    panelRef.value?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  });
}

watch(
  () => [props.name, props.variants],
  () => {
    scrollPanelIntoView();
  },
);

watch(
  () => props.selectedIndex,
  () => {
    imageZoomOpen.value = false;
  },
);

watch(imageZoomOpen, (open) => {
  if (open) {
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onImageZoomKeydown);
    return;
  }
  document.body.style.overflow = "";
  window.removeEventListener("keydown", onImageZoomKeydown);
});

onBeforeUnmount(() => {
  document.body.style.overflow = "";
  window.removeEventListener("keydown", onImageZoomKeydown);
});
</script>

<template>
  <section
    v-if="name && variants.length"
    ref="panelRef"
    class="table-panel collection-search-art-panel"
    :class="{
      'collection-search-art-panel--compact': compact,
      'collection-search-art-panel--sidebar': sidebar,
    }"
  >
    <div class="collection-search-art-header">
      <div>
        <h2 class="collection-search-art-title">
          <RouterLink
            v-if="selectedRoute"
            :to="selectedRoute"
            class="collection-search-art-title-link"
          >
            {{ name }}
          </RouterLink>
          <span v-else>{{ name }}</span>
        </h2>
        <p class="collection-search-art-meta">
          {{ variants.length }} version{{ variants.length === 1 ? "" : "s" }} across sets
        </p>
      </div>
      <div v-if="showRandom || !sidebar" class="collection-search-art-actions">
        <button
          v-if="showRandom"
          type="button"
          class="btn btn-secondary btn-small"
          @click="emit('random')"
        >
          Another random
        </button>
        <button
          v-if="!sidebar"
          type="button"
          class="btn btn-secondary btn-small"
          @click="emit('close')"
        >
          Close
        </button>
      </div>
    </div>

    <div v-if="selectedVariant" class="collection-search-art-selected">
      <div class="collection-search-art-preview-image-wrap">
        <button
          v-if="useZoomPreview && selectedVariant.imageUri"
          type="button"
          class="collection-search-art-preview-zoom-btn"
          aria-label="View larger image"
          @click="imageZoomOpen = true"
        >
          <img
            :src="selectedVariant.imageUri"
            :alt="name"
            loading="lazy"
            class="collection-search-art-preview-image"
          >
        </button>
        <CardInteractiveImage
          v-else-if="selectedVariant.imageUri"
          :src="selectedVariant.imageUri"
          :alt="name"
          :card="selectedVariant"
          :show-details="false"
          img-class="collection-search-art-preview-image"
          @ownership-changed="emit('ownership-changed')"
        />
        <div v-else class="collection-search-art-preview-empty">No image</div>
      </div>

      <div class="collection-search-art-details">
        <dl class="collection-search-art-details-list">
          <div class="collection-search-art-detail">
            <dt>Set</dt>
            <dd>
              <CollectionSetLink
                :set-code="selectedVariant.setCode"
                :art-style="selectedVariant.artStyle || ''"
                :label="setLabel(selectedVariant.setCode)"
              />
            </dd>
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
        <CardCopyControls
          :card="selectedVariant"
          variant="panel"
          :visible="true"
          @ownership-changed="emit('ownership-changed')"
        />
      </div>
    </div>

    <CardVariantGallery
      v-if="showVariantGallery"
      class="collection-search-art-gallery"
      title="Alternative versions"
      :cards="galleryCards"
      :current-index="selectedIndex"
      :finish="selectedFinish"
      :centered="sidebar"
      selectable
      @select="onGallerySelect"
    />

    <Teleport to="body">
      <div
        v-if="imageZoomOpen && selectedVariant?.imageUri"
        class="card-image-zoom-backdrop"
        role="dialog"
        aria-modal="true"
        aria-label="Card image preview"
        @click.self="closeImageZoom"
      >
        <button
          type="button"
          class="card-image-zoom-close"
          aria-label="Close image preview"
          @click="closeImageZoom"
        >
          ×
        </button>
        <img
          :src="selectedVariant.imageUri"
          :alt="name"
          class="card-image-zoom-image"
        >
      </div>
    </Teleport>
  </section>
</template>
