<script setup>
import "../styles/card-detail.css";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, clearClientCache, ignoreAborted } from "../api";
import { cacheKeyFor, getCachedEntry } from "../apiCache";
import CardPreviewDialog from "../components/CardPreviewDialog.vue";
import CardVariantGallery from "../components/CardVariantGallery.vue";
import CardDetailOwnershipPanel from "../components/CardDetailOwnershipPanel.vue";
import CardmarketIcon from "../components/CardmarketIcon.vue";
import ScryfallIcon from "../components/ScryfallIcon.vue";
import { displayCardmarketUrl } from "../utils/cardmarketUrl";
import { formatEuro } from "../utils/format";
import { priceStrategyDescription } from "../utils/priceStrategies";
import {
  FINISH_ETCHED,
  FINISH_FOIL,
  FINISH_NONFOIL,
  canManageFinish,
  catalogDeniesFinish,
  isFinishOwnedOnCard,
  normalizeFinish,
} from "../utils/finishes";
import CollectionSetLink from "../components/CollectionSetLink.vue";
import { fetchFavorites, useFavorites } from "../composables/favorites";
import { PRICE_SYNC_POLL_MS } from "../composables/startupPriceSync";
import { catalogVisibleFamilyCodes } from "../utils/priceSyncMovers";
import { scryfallCardUri, scryfallPrintsSearchUri } from "../utils/scryfall";

const route = useRoute();
const router = useRouter();

const card = ref(null);
const selectedFinish = ref(FINISH_NONFOIL);
const priceStrategy = ref("trend");
const detailLoading = ref(false);
const { isCardFavorite, toggleCardFavorite } = useFavorites();
const favoriteSetCodes = ref(new Set());
let favoriteCoveragePromise = null;
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
  [FINISH_NONFOIL, FINISH_FOIL, FINISH_ETCHED].filter((finish) => {
    // Cardmarket foil prices on etched-only prints must not unlock a Foil toggle.
    if (catalogDeniesFinish(card.value, finish) && !isFinishOwnedOnCard(card.value, finish)) {
      return false;
    }
    return canManageFinish(card.value, finish) || availableFinishes.value.includes(finish);
  }),
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

const cardmarketLinkUrl = computed(() => displayCardmarketUrl(card.value?.cardmarketUrl));

const scryfallCardLinkUrl = computed(() => {
  if (!card.value) {
    return "";
  }
  return scryfallCardUri(card.value.setCode, card.value.collectorNumber);
});

const scryfallPrintsLinkUrl = computed(() => {
  if (!card.value?.name) {
    return "";
  }
  return scryfallPrintsSearchUri(card.value.name);
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

const routeDeckId = computed(() =>
  typeof route.query.deck === "string" ? route.query.deck : "",
);
const sessionDeckId = ref("");
const activeDeckId = computed(() => routeDeckId.value || sessionDeckId.value);
const imageZoomOpen = ref(false);
const showBackFace = ref(false);
const priceSyncing = ref(false);
const priceSyncMessage = ref("");
const priceSyncFailed = ref(false);
let priceSyncPoll = null;
let loadToken = 0;
let syncGeneration = 0;

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

async function onDeckCardChanged(result) {
  if (result?.deckId != null) {
    sessionDeckId.value = String(result.deckId);
  }
  clearClientCache();
  await loadCard();
}

function closeImageZoom() {
  imageZoomOpen.value = false;
}

function routeFinish() {
  return route.query.finish == null ? undefined : normalizeFinish(route.query.finish);
}

function cardDetailPath() {
  const finishQuery = routeFinish();
  const query = new URLSearchParams();
  if (finishQuery != null) {
    query.set("finish", String(finishQuery));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return `/cards/${encodeURIComponent(route.params.setCode)}/${encodeURIComponent(route.params.collectorNumber)}${suffix}`;
}

function cardMatchesRoute(value) {
  if (!value?.setCode || value.collectorNumber == null) {
    return false;
  }
  return String(value.setCode).toUpperCase() === String(route.params.setCode || "").toUpperCase()
    && String(value.collectorNumber) === String(route.params.collectorNumber || "");
}

function shellFromRoute() {
  const finish = routeFinish();
  return {
    setCode: String(route.params.setCode || "").toUpperCase(),
    collectorNumber: String(route.params.collectorNumber || ""),
    name: "",
    setLabel: String(route.params.setCode || "").toUpperCase(),
    artStyle: "",
    imageUri: "",
    finishes: {},
    guidePriceMatrix: null,
    selectedFinish: finish == null ? FINISH_NONFOIL : finish,
  };
}

function readCachedCard() {
  const cached = getCachedEntry(cacheKeyFor("GET", cardDetailPath()));
  return cached?.data && cardMatchesRoute(cached.data) ? cached.data : null;
}

function applyKnownCard() {
  const cached = readCachedCard();
  if (cached) {
    card.value = cached;
    selectedFinish.value = normalizeFinish(cached.selectedFinish ?? FINISH_NONFOIL);
    priceStrategy.value = cached.priceStrategy || "trend";
    return;
  }
  if (!cardMatchesRoute(card.value) || !card.value?.name) {
    card.value = shellFromRoute();
    selectedFinish.value = card.value.selectedFinish;
  }
}

function cardSetIsFavourite(setCode) {
  return favoriteSetCodes.value.has(String(setCode || "").trim().toUpperCase());
}

async function ensureFavoriteCoverage() {
  if (!favoriteCoveragePromise) {
    favoriteCoveragePromise = ignoreAborted(api.getReportsMeta()).then((meta) => {
      const codes = new Set();
      const catalog = meta?.sets || [];
      for (const code of meta?.favoriteSets || []) {
        const normalized = String(code || "").trim().toUpperCase();
        if (!normalized) {
          continue;
        }
        codes.add(normalized);
        for (const member of catalogVisibleFamilyCodes(
          { setCode: normalized },
          catalog,
          { includeHiddenSubsets: true },
        )) {
          codes.add(member);
        }
      }
      favoriteSetCodes.value = codes;
      return codes;
    }).catch((error) => {
      favoriteCoveragePromise = null;
      throw error;
    });
  }
  return favoriteCoveragePromise;
}

async function loadCard({ background = false, syncAfter = false } = {}) {
  const token = ++loadToken;
  if (!background) {
    applyKnownCard();
  }
  const waitingForRecord = !card.value?.name;
  if (waitingForRecord) {
    detailLoading.value = true;
  }
  try {
    const nextCard = await ignoreAborted(api.getCardDetail(
      route.params.setCode,
      route.params.collectorNumber,
      { finish: routeFinish() },
    ));
    if (!nextCard || token !== loadToken || !cardMatchesRoute(nextCard)) {
      return;
    }
    card.value = nextCard;
    if (!background) {
      showBackFace.value = false;
    }
    selectedFinish.value = normalizeFinish(card.value.selectedFinish ?? FINISH_NONFOIL);
    priceStrategy.value = card.value.priceStrategy || "trend";
    if (syncAfter) {
      void maybeAutoSync(token);
    }
  } catch (error) {
    if (token === loadToken && waitingForRecord) {
      priceSyncFailed.value = true;
      priceSyncMessage.value = error.message || "Could not load this card.";
    }
  } finally {
    if (token === loadToken) {
      detailLoading.value = false;
    }
  }
}

async function onOwnershipChanged() {
  if (!card.value?.name) {
    return;
  }
  await loadCard({ background: true });
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

function stopPriceSyncPoll() {
  if (priceSyncPoll) {
    clearInterval(priceSyncPoll);
    priceSyncPoll = null;
  }
}

async function pollCardPriceSync() {
  const generation = syncGeneration;
  try {
    const status = await api.getPriceSyncStatus();
    if (generation !== syncGeneration) {
      return;
    }
    if (status?.status === "running") {
      return;
    }
    stopPriceSyncPoll();
    priceSyncing.value = false;
    if (status?.status === "failed") {
      priceSyncFailed.value = true;
      priceSyncMessage.value = status.error || status.message || "Could not sync this card.";
      return;
    }
    priceSyncFailed.value = false;
    priceSyncMessage.value = "";
    clearClientCache();
    await loadCard({ background: true });
  } catch (error) {
    if (generation !== syncGeneration) {
      return;
    }
    stopPriceSyncPoll();
    priceSyncing.value = false;
    priceSyncFailed.value = true;
    priceSyncMessage.value = error.message || "Could not sync this card.";
  }
}

function watchPriceSync() {
  stopPriceSyncPoll();
  void pollCardPriceSync();
  priceSyncPoll = setInterval(pollCardPriceSync, PRICE_SYNC_POLL_MS);
}

async function syncThisCard() {
  if (!card.value?.name || priceSyncing.value || cardSetIsFavourite(card.value.setCode)) {
    return;
  }
  priceSyncFailed.value = false;
  priceSyncMessage.value = "";
  priceSyncing.value = true;
  try {
    await api.triggerPriceSync({
      setCode: card.value.setCode,
      collectorNumber: String(card.value.collectorNumber),
    });
    watchPriceSync();
  } catch (error) {
    const message = error.message || "";
    if (/already running/i.test(message)) {
      watchPriceSync();
      return;
    }
    priceSyncing.value = false;
    priceSyncFailed.value = true;
    priceSyncMessage.value = message || "Could not sync this card.";
  }
}

async function retryCardSync() {
  priceSyncFailed.value = false;
  priceSyncMessage.value = "";
  if (!card.value?.name) {
    await loadCard({ syncAfter: true });
    return;
  }
  await syncThisCard();
}

async function maybeAutoSync(token) {
  try {
    await ensureFavoriteCoverage();
  } catch {
    return;
  }
  if (token !== loadToken || !card.value?.name || cardSetIsFavourite(card.value.setCode)) {
    return;
  }
  await syncThisCard();
}

async function onToggleFavorite() {
  if (!card.value) {
    return;
  }
  await toggleCardFavorite(card.value, selectedFinish.value);
}

watch(
  () => [route.params.setCode, route.params.collectorNumber, route.query.finish],
  (next, previous) => {
    const printChanged = !previous
      || next[0] !== previous[0]
      || next[1] !== previous[1];
    if (printChanged) {
      syncGeneration += 1;
      stopPriceSyncPoll();
      priceSyncing.value = false;
      priceSyncMessage.value = "";
      priceSyncFailed.value = false;
    }
    loadCard({ syncAfter: printChanged });
  },
);

applyKnownCard();

onMounted(() => {
  fetchFavorites();
  ensureFavoriteCoverage().catch(() => {});
  loadCard({ syncAfter: true });
});

onUnmounted(() => {
  syncGeneration += 1;
  loadToken += 1;
  stopPriceSyncPoll();
  document.body.style.overflow = "";
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
            :alt="card.name || `${card.setCode} #${card.collectorNumber}`"
            class="card-detail-image"
          >
        </button>
        <div
          v-else-if="detailLoading"
          class="card-detail-image card-detail-image-pending"
          aria-hidden="true"
        ></div>
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
        <div class="card-detail-title-row">
          <h1>
            {{ card.name || `${card.setCode} #${card.collectorNumber}` }}
            <span
              v-if="detailLoading && !card.name"
              class="loading-spinner card-detail-inline-spinner"
              aria-label="Loading card"
            ></span>
          </h1>
          <button
            type="button"
            class="card-detail-favorite"
            :class="{ 'is-favorite': isCardFavorite(card, selectedFinish) }"
            :aria-pressed="isCardFavorite(card, selectedFinish) ? 'true' : 'false'"
            :aria-label="isCardFavorite(card, selectedFinish) ? `Unfavourite ${card.name}` : `Favourite ${card.name}`"
            :title="isCardFavorite(card, selectedFinish) ? 'Unfavourite card' : 'Favourite card'"
            @click="onToggleFavorite"
          >
            {{ isCardFavorite(card, selectedFinish) ? "★" : "☆" }}
          </button>
        </div>
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
          <CardDetailOwnershipPanel
            v-if="menuCard && card.name"
            :card="menuCard"
            :manageable-finishes="manageableFinishes"
            :loading="false"
            :default-deck-id="activeDeckId"
            @ownership-changed="onOwnershipChanged"
            @finish-selected="onFinishSelected"
            @deck-changed="onDeckCardChanged"
          />
        </div>
      </div>

      <div class="card-detail-side">
        <div class="card-detail-guide-panel">
          <div class="card-detail-guide-heading">
            <h2>Cardmarket prices (EUR)</h2>
            <span v-if="priceSyncing || (detailLoading && card.name)" class="card-detail-sync-note">
              <span class="loading-spinner" aria-hidden="true"></span>
              Updating
            </span>
            <button
              v-else-if="priceSyncFailed"
              type="button"
              class="card-detail-sync-retry"
              @click="retryCardSync"
            >
              Retry
            </button>
          </div>
          <p
            v-if="priceSyncMessage"
            class="card-detail-sync-message"
            :class="{ 'is-error': priceSyncFailed }"
          >
            {{ priceSyncMessage }}
          </p>
          <div v-if="card.guidePriceMatrix?.rows?.length" class="card-detail-guide-table-wrap">
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
          <div class="card-detail-external-links">
            <a
              v-if="cardmarketLinkUrl"
              :href="cardmarketLinkUrl"
              class="card-detail-external-link card-detail-cardmarket-link"
              target="_blank"
              rel="noopener noreferrer"
            >
              <CardmarketIcon class="card-detail-external-icon" :size="16" />
              <span>View on Cardmarket</span>
            </a>
            <a
              v-if="scryfallCardLinkUrl"
              :href="scryfallCardLinkUrl"
              class="card-detail-external-link card-detail-scryfall-link"
              target="_blank"
              rel="noopener noreferrer"
            >
              <ScryfallIcon class="card-detail-external-icon" :size="16" />
              <span>View on Scryfall</span>
            </a>
            <a
              v-if="scryfallPrintsLinkUrl"
              :href="scryfallPrintsLinkUrl"
              class="card-detail-external-link card-detail-scryfall-link"
              target="_blank"
              rel="noopener noreferrer"
            >
              <ScryfallIcon class="card-detail-external-icon" :size="16" />
              <span>All prints on Scryfall</span>
            </a>
          </div>
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

    <CardPreviewDialog
      v-if="imageZoomOpen && displayImageUri"
      :image-uri="displayImageUri"
      :alt="card.name"
      :set-code="card.setCode"
      :collector-number="card.collectorNumber"
      :finish="selectedFinish"
      :seed="card"
      @close="closeImageZoom"
    />
  </div>
</template>
