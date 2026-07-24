<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { api } from "../api";
import CardDetailOwnershipPanel from "./CardDetailOwnershipPanel.vue";
import CardInteractiveImage from "./CardInteractiveImage.vue";
import CardVariantGallery from "./CardVariantGallery.vue";
import CollectionSetLink from "./CollectionSetLink.vue";
import LoadingIndicator from "./LoadingIndicator.vue";
import { usePricingSettings } from "../composables/pricingSettings";
import { formatEuro } from "../utils/format";
import { valueForStrategy } from "../utils/priceStrategies";
import {
  FINISH_ETCHED,
  FINISH_FOIL,
  FINISH_NONFOIL,
  canManageFinish,
  cardFinish,
  cardRouteQuery,
  finishLabel,
  marketValueForFinish,
  normalizeFinish,
} from "../utils/finishes";

const props = defineProps({
  name: { type: String, default: "" },
  variants: { type: Array, default: () => [] },
  selectedIndex: { type: Number, default: 0 },
  setLabelFor: { type: Function, default: null },
  compact: { type: Boolean, default: false },
  sidebar: { type: Boolean, default: false },
});

const emit = defineEmits(["update:selectedIndex", "close", "ownership-changed"]);

const { settings: pricingSettings } = usePricingSettings();

const panelRef = ref(null);
const imageZoomOpen = ref(false);
const cardDetail = ref(null);
const detailLoading = ref(false);
const activeFinish = ref(FINISH_NONFOIL);
let detailLoadToken = 0;

const selectedVariant = computed(() => props.variants[props.selectedIndex] || null);
const useZoomPreview = computed(() => props.sidebar || props.compact);

const selectedRoute = computed(() => {
  const card = selectedVariant.value;
  if (!card) {
    return null;
  }
  return {
    name: "card",
    params: { setCode: card.setCode, collectorNumber: card.collectorNumber },
    query: cardRouteQuery(activeFinish.value ?? cardFinish(card)),
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

const detailAvailableFinishes = computed(() =>
  Array.from(
    new Set(
      Object.entries(cardDetail.value?.finishes || {})
        .map(([key, item]) => normalizeFinish(item?.finish ?? key))
        .filter((finish) => [FINISH_NONFOIL, FINISH_FOIL, FINISH_ETCHED].includes(finish)),
    ),
  ).sort((left, right) => left - right),
);

const manageableFinishes = computed(() =>
  [FINISH_NONFOIL, FINISH_FOIL, FINISH_ETCHED].filter(
    (finish) => canManageFinish(cardDetail.value, finish) || detailAvailableFinishes.value.includes(finish),
  ),
);

const menuCard = computed(() => {
  if (!cardDetail.value) {
    return null;
  }
  return {
    ...cardDetail.value,
    finish: activeFinish.value,
    hasNonfoil: cardDetail.value.hasNonfoil ?? Boolean(selectedVariant.value?.hasNonfoil),
    hasFoil: cardDetail.value.hasFoil ?? Boolean(selectedVariant.value?.hasFoil),
    hasEtched: cardDetail.value.hasEtched ?? Boolean(selectedVariant.value?.hasEtched),
  };
});

const galleryCards = computed(() =>
  props.variants.map((card, index) => ({
    ...card,
    isCurrent: index === props.selectedIndex,
  })),
);

const galleryFinish = computed(() => cardFinish(selectedVariant.value || {}));
const showVariantGallery = computed(() => props.variants.length > 1);
const canGoPrevVariant = computed(() => props.selectedIndex > 0);
const canGoNextVariant = computed(() => props.selectedIndex < props.variants.length - 1);

function goPrevVariant() {
  if (!canGoPrevVariant.value) {
    return;
  }
  emit("update:selectedIndex", props.selectedIndex - 1);
}

function goNextVariant() {
  if (!canGoNextVariant.value) {
    return;
  }
  emit("update:selectedIndex", props.selectedIndex + 1);
}

function setLabel(code) {
  if (props.setLabelFor) {
    return props.setLabelFor(code);
  }
  return code;
}

function valueForFinish(card, finish) {
  const strategy = pricingSettings.value?.priceStrategy || "trend";
  const normalized = normalizeFinish(finish);
  const byStrategy = card.finishValuesByStrategy?.[normalized];
  if (byStrategy && strategy in byStrategy) {
    const value = byStrategy[strategy];
    return value == null ? null : value;
  }
  const finishValue = card.finishValues?.[normalized];
  if (finishValue != null && Number(finishValue) > 0) {
    return finishValue;
  }
  if (normalizeFinish(card.finish ?? card.foil) === normalized) {
    const strategyValue = valueForStrategy(card, strategy);
    if (strategyValue != null) {
      return strategyValue;
    }
  }
  const market = marketValueForFinish(card, normalized);
  return market == null || Number(market) <= 0 ? null : market;
}

async function loadCardDetail() {
  const variant = selectedVariant.value;
  if (!variant?.setCode || variant.collectorNumber == null) {
    cardDetail.value = null;
    return;
  }
  const token = ++detailLoadToken;
  detailLoading.value = true;
  cardDetail.value = null;
  try {
    const finishQuery = normalizeFinish(activeFinish.value ?? cardFinish(variant));
    const next = await api.getCardDetail(
      variant.setCode,
      variant.collectorNumber,
      { finish: finishQuery },
    );
    if (token !== detailLoadToken) {
      return;
    }
    cardDetail.value = next;
    activeFinish.value = normalizeFinish(next.selectedFinish ?? finishQuery);
  } catch {
    if (token !== detailLoadToken) {
      return;
    }
    cardDetail.value = null;
  } finally {
    if (token === detailLoadToken) {
      detailLoading.value = false;
    }
  }
}

async function onOwnershipChanged() {
  await loadCardDetail();
  emit("ownership-changed");
}

function onFinishSelected(finish) {
  activeFinish.value = normalizeFinish(finish);
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
  () => [
    selectedVariant.value?.setCode,
    selectedVariant.value?.collectorNumber,
    props.selectedIndex,
  ],
  () => {
    activeFinish.value = normalizeFinish(cardFinish(selectedVariant.value || {}));
    loadCardDetail();
  },
  { immediate: true },
);

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
      <div class="collection-search-art-heading">
        <div class="collection-search-art-title-row">
          <button
            v-if="variants.length > 1"
            type="button"
            class="collection-search-art-nav-btn"
            :disabled="!canGoPrevVariant"
            aria-label="Previous version"
            @click="goPrevVariant"
          >
            ‹
          </button>
          <div class="collection-search-art-heading-text">
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
          </div>
          <button
            v-if="variants.length > 1"
            type="button"
            class="collection-search-art-nav-btn"
            :disabled="!canGoNextVariant"
            aria-label="Next version"
            @click="goNextVariant"
          >
            ›
          </button>
        </div>
        <p class="collection-search-art-meta">
          <template v-if="variants.length > 1">
            Version {{ selectedIndex + 1 }} of {{ variants.length }}
          </template>
          <template v-else>
            {{ variants.length }} version{{ variants.length === 1 ? "" : "s" }} across sets
          </template>
        </p>
      </div>
      <div v-if="!sidebar" class="collection-search-art-actions">
        <button
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
          @ownership-changed="onOwnershipChanged"
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
        <CardDetailOwnershipPanel
          v-if="menuCard"
          :card="menuCard"
          :manageable-finishes="manageableFinishes"
          :loading="detailLoading"
          @ownership-changed="onOwnershipChanged"
          @finish-selected="onFinishSelected"
        />
        <LoadingIndicator
          v-else-if="detailLoading"
          compact
          label="Loading card…"
          class="collection-search-art-detail-loading"
        />
      </div>
    </div>

    <CardVariantGallery
      v-if="showVariantGallery"
      class="collection-search-art-gallery"
      title="Alternative versions"
      :cards="galleryCards"
      :current-index="selectedIndex"
      :finish="galleryFinish"
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
