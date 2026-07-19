<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, clearClientCache } from "../api";
import CardVariantGallery from "../components/CardVariantGallery.vue";
import CardDetailOwnershipPanel from "../components/CardDetailOwnershipPanel.vue";
import CardmarketIcon from "../components/CardmarketIcon.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { formatEuro } from "../utils/format";
import { priceStrategyDescription } from "../utils/priceStrategies";
import {
  FINISH_ETCHED,
  FINISH_FOIL,
  FINISH_NONFOIL,
  canManageFinish,
  normalizeFinish,
} from "../utils/finishes";
import DeckCardQtyControl from "../components/DeckCardQtyControl.vue";
import CollectionSetLink from "../components/CollectionSetLink.vue";

const route = useRoute();
const router = useRouter();

const card = ref(null);
const selectedFinish = ref(FINISH_NONFOIL);
const priceStrategy = ref("trend");
const { loading, run } = useAsyncLoad();

const availableFinishes = computed(() =>
  Array.from(
    new Set(
      Object.entries(card.value?.finishes || {})
        .map(([key, item]) => normalizeFinish(item?.finish ?? key))
        .filter((finish) => [FINISH_NONFOIL, FINISH_FOIL, FINISH_ETCHED].includes(finish)),
    ),
  ).sort((left, right) => left - right),
);

const manageableFinishes = computed(() =>
  [FINISH_NONFOIL, FINISH_FOIL, FINISH_ETCHED].filter(
    (finish) => canManageFinish(card.value, finish) || availableFinishes.value.includes(finish),
  ),
);

const showNonfoilGuidePrices = computed(() =>
  card.value?.guidePriceMatrix?.rows?.some((row) => row.nonfoil != null),
);

const showFoilGuidePrices = computed(() =>
  card.value?.guidePriceMatrix?.rows?.some((row) => row.foil != null),
);

const showEtchedGuidePrices = computed(() =>
  card.value?.guidePriceMatrix?.rows?.some((row) => row.etched != null),
);

const cardmarketLinkUrl = computed(() => {
  const url = card.value?.cardmarketUrl;
  return url && String(url).trim() ? String(url).trim() : "";
});

const showNeighborGallery = computed(
  () => (card.value?.setGallery?.cards?.length || 0) > 1,
);

const menuCard = computed(() => {
  if (!card.value) {
    return null;
  }
  return {
    ...card.value,
    finish: selectedFinish.value,
    hasNonfoil: availableFinishes.value.includes(FINISH_NONFOIL),
    hasFoil: availableFinishes.value.includes(FINISH_FOIL),
    hasEtched: availableFinishes.value.includes(FINISH_ETCHED),
  };
});

const showVariantGallery = computed(
  () => (card.value?.variantGallery?.cards?.length || 0) > 1,
);

const defaultDeckId = computed(() =>
  typeof route.query.deck === "string" ? route.query.deck : "",
);
const activeDeckLabel = ref("");
const deckCardSlot = ref(null);
const imageZoomOpen = ref(false);
const showBackFace = ref(false);

const hasBackImage = computed(() => Boolean(card.value?.imageUriBack));
const displayImageUri = computed(() => {
  if (!card.value) {
    return "";
  }
  if (showBackFace.value && card.value.imageUriBack) {
    return card.value.imageUriBack;
  }
  return card.value.imageUri || "";
});

function toggleCardFace() {
  if (!hasBackImage.value) {
    return;
  }
  showBackFace.value = !showBackFace.value;
}

watch(
  defaultDeckId,
  async (deckId) => {
    if (!deckId) {
      activeDeckLabel.value = "";
      return;
    }
    try {
      const payload = await api.listDecks();
      const deck = (payload.decks || []).find((item) => String(item.id) === String(deckId));
      activeDeckLabel.value = deck?.label || deck?.name || "";
    } catch {
      activeDeckLabel.value = "";
    }
  },
  { immediate: true },
);

async function onDeckCardRemoved() {
  clearClientCache();
  deckCardSlot.value = null;
  await loadCard();
}

async function onDeckCardChanged() {
  clearClientCache();
  await loadCard();
}

function findDeckCardSlot(cards, setCode, collectorNumber, finish) {
  const matches = (cards || []).filter(
    (row) =>
      row.setCode === setCode &&
      String(row.collectorNumber) === String(collectorNumber) &&
      normalizeFinish(row.finish ?? row.foil ?? 0) === finish,
  );
  if (!matches.length) {
    return null;
  }
  return matches.find((row) => row.section === "main") || matches[0];
}

function closeImageZoom() {
  imageZoomOpen.value = false;
}

function onImageZoomKeydown(event) {
  if (event.key === "Escape") {
    closeImageZoom();
  }
}

watch(imageZoomOpen, (open) => {
  if (open) {
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onImageZoomKeydown);
    return;
  }
  document.body.style.overflow = "";
  window.removeEventListener("keydown", onImageZoomKeydown);
});

async function loadCard() {
  await run(async (isCurrent) => {
    const finishQuery = route.query.finish == null
      ? undefined
      : normalizeFinish(route.query.finish);
    const nextCard = await api.getCardDetail(
      route.params.setCode,
      route.params.collectorNumber,
      { finish: finishQuery },
    );
    if (!isCurrent()) {
      return;
    }
    card.value = nextCard;
    showBackFace.value = false;
    selectedFinish.value = normalizeFinish(card.value.selectedFinish ?? FINISH_NONFOIL);
    priceStrategy.value = card.value.priceStrategy || "trend";
    deckCardSlot.value = null;
    if (defaultDeckId.value) {
      try {
        const browse = await api.getDeckBrowse(defaultDeckId.value);
        if (isCurrent()) {
          deckCardSlot.value = findDeckCardSlot(
            browse.cards,
            card.value.setCode,
            card.value.collectorNumber,
            selectedFinish.value,
          );
        }
      } catch {
        deckCardSlot.value = null;
      }
    }
  });
}

async function onOwnershipChanged() {
  if (!card.value) {
    return;
  }
  await loadCard();
}

async function onFinishSelected(finish) {
  const normalized = normalizeFinish(finish);
  if (selectedFinish.value === normalized) {
    return;
  }
  selectedFinish.value = normalized;
  await router.replace({
    params: {
      setCode: route.params.setCode,
      collectorNumber: route.params.collectorNumber,
    },
    query: normalized === FINISH_NONFOIL ? {} : { finish: String(normalized) },
  });
}

watch(
  () => [route.params.setCode, route.params.collectorNumber, route.query.finish],
  () => {
    loadCard();
  },
);

onMounted(loadCard);

onUnmounted(() => {
  document.body.style.overflow = "";
  window.removeEventListener("keydown", onImageZoomKeydown);
});
</script>

<template>
  <div v-if="card" class="card-detail-page">
    <header class="card-detail-header-bar">
      <button type="button" class="card-detail-back" @click="router.back()">← Back</button>
    </header>

    <section class="card-detail-panel card-detail-main">
      <div class="card-detail-image-wrap">
        <button
          v-if="displayImageUri"
          type="button"
          class="card-detail-image-button"
          aria-label="View larger image"
          @click="imageZoomOpen = true"
        >
          <img
            :src="displayImageUri"
            :alt="card.name"
            class="card-detail-image"
          >
        </button>
        <div v-else class="card-detail-image card-detail-image-empty">No image</div>
        <button
          v-if="hasBackImage"
          type="button"
          class="btn btn-secondary btn-small card-detail-face-toggle"
          @click="toggleCardFace"
        >
          {{ showBackFace ? "View front" : "View back" }}
        </button>
      </div>

      <div class="card-detail-meta">
        <h1>{{ card.name }}</h1>
        <p class="card-detail-set">
          <CollectionSetLink
            :set-code="card.setCode"
            :art-style="card.artStyle || ''"
            :label="card.setLabel"
          />
        </p>
        <p class="card-detail-subtitle">#{{ String(card.collectorNumber).padStart(3, "0") }}</p>
        <p v-if="card.artStyle" class="card-detail-art-style">{{ card.artStyle }}</p>

        <div class="card-detail-actions">
          <DeckCardQtyControl
            v-if="menuCard && defaultDeckId && deckCardSlot"
            :card="{ ...menuCard, ...deckCardSlot }"
            :deck-id="defaultDeckId"
            :deck-name="activeDeckLabel"
            @changed="onDeckCardChanged"
            @removed="onDeckCardRemoved"
          />

          <CardDetailOwnershipPanel
            v-if="menuCard"
            :card="menuCard"
            :manageable-finishes="manageableFinishes"
            :loading="loading"
            @ownership-changed="onOwnershipChanged"
            @finish-selected="onFinishSelected"
          />
        </div>
      </div>

      <div class="card-detail-side">
        <div class="card-detail-guide-panel">
          <h2>Cardmarket prices (EUR)</h2>
          <div class="card-detail-guide-table-wrap">
            <table class="card-detail-guide-table">
              <thead>
                <tr>
                  <th>Strategy</th>
                  <th v-if="showNonfoilGuidePrices">Non-foil</th>
                  <th v-if="showFoilGuidePrices">Foil</th>
                  <th v-if="showEtchedGuidePrices">Etched</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in card.guidePriceMatrix.rows"
                  :key="row.strategyId"
                  :class="{ 'is-active-strategy': row.strategyId === priceStrategy }"
                >
                  <td>
                    <span
                      class="card-detail-strategy-label"
                      :title="priceStrategyDescription(row.strategyId)"
                    >
                      {{ row.label }}
                    </span>
                  </td>
                  <td v-if="showNonfoilGuidePrices">{{ formatEuro(row.nonfoil) }}</td>
                  <td v-if="showFoilGuidePrices">{{ formatEuro(row.foil) }}</td>
                  <td v-if="showEtchedGuidePrices">{{ formatEuro(row.etched) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <a
            v-if="cardmarketLinkUrl"
            :href="cardmarketLinkUrl"
            class="card-detail-cardmarket-link"
            target="_blank"
            rel="noopener noreferrer"
          >
            <CardmarketIcon class="card-detail-cardmarket-icon" :size="16" />
            <span>View on Cardmarket</span>
          </a>
        </div>
      </div>
    </section>

    <CardVariantGallery
      v-if="showVariantGallery"
      title="Alternative versions"
      :cards="card.variantGallery.cards"
      :current-index="card.variantGallery.currentIndex"
      :finish="selectedFinish"
      centered
    />

    <CardVariantGallery
      v-if="showNeighborGallery"
      title="Previous & next numbers"
      :cards="card.setGallery.cards"
      :current-index="card.setGallery.currentIndex"
      :finish="selectedFinish"
      show-name
      show-arrows
    />

    <Teleport to="body">
      <div
        v-if="imageZoomOpen && displayImageUri"
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
        <button
          v-if="hasBackImage"
          type="button"
          class="btn btn-secondary btn-small card-image-zoom-face-toggle"
          @click.stop="toggleCardFace"
        >
          {{ showBackFace ? "View front" : "View back" }}
        </button>
        <img
          :src="displayImageUri"
          :alt="card.name"
          class="card-image-zoom-image"
        >
      </div>
    </Teleport>
  </div>

  <div v-else class="card-detail-page">
    <LoadingIndicator label="Loading card…" />
  </div>
</template>
