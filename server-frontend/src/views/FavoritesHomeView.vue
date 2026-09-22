<script setup>
import "../styles/favorites-home.css";
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, clearClientCache, ignoreAborted } from "../api";
import CollectionCardGrid from "../components/CollectionCardGrid.vue";
import VirtualizedCollectionCardGrid from "../components/VirtualizedCollectionCardGrid.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import { syncFavoritesFromPayload, useFavorites } from "../composables/favorites";
import {
  fetchPricingSettings,
  usePricingSettings,
} from "../composables/pricingSettings";
import { useSetGalleryFilter } from "../composables/setGalleryFilter";
import { collectionRouteForSet } from "../utils/setScope";
import { formatSetCountLabel, setShortName } from "../utils/format";
import { resolveSetIconUri } from "../utils/scryfall";
import { cardFinish } from "../utils/finishes";
import {
  cardFavoriteKeyFromCard,
  favoriteArtStyleKey,
  favoriteCardKey,
} from "../utils/favorites";
import { applyGalleryDisplayToCards } from "../utils/priceStrategies";
import { filterCollectionCards } from "../utils/collectionFilters";
import { shouldApplyPriceTileTint } from "../utils/catalogGroups";
import EdgeCarousel from "../components/EdgeCarousel.vue";
import FavoriteDayChangeTiles from "../components/FavoriteDayChangeTiles.vue";
import PriceSyncMoversPanel from "../components/PriceSyncMoversModal.vue";
import {
  bindHomeChangesNavigation,
  lastPriceSyncOutcome,
  priceSyncHasMovers,
  showStoredPriceSyncMovers,
} from "../composables/startupPriceSync";
import { homeChangesRoute, isHomeChangesRoute } from "../utils/homeRoutes";
import {
  firstPriceSyncCards,
  favoriteArtStyleDayRows,
  favoriteCardDayRows,
  favoriteSetDayRows,
} from "../utils/priceSyncMovers";

const route = useRoute();
const router = useRouter();
const showingChanges = computed(() => isHomeChangesRoute(route));
const payload = ref(null);
const loading = ref(true);
const loadError = ref("");
const dragArtFrom = ref(-1);
const dragArtOver = ref(-1);
const lastPriceSyncStatus = ref(null);
const catalogSetNames = ref(new Map());
const catalogSets = ref([]);
const { showSetBrowserSubsets } = useSetGalleryFilter();
const { settings: pricingSettings, collectionCardScale, collectionPriceTileTint } = usePricingSettings();
const showPriceTileTint = computed(() => shouldApplyPriceTileTint({
  enabled: collectionPriceTileTint.value,
}));
const { toggleArtStyleFavorite, favoriteCards, favoriteArtStyles } = useFavorites();

const sets = computed(() => payload.value?.sets || []);
const artStyles = computed(() => payload.value?.artStyles || []);
const cards = computed(() => payload.value?.cards || []);
const lastSyncCards = computed(() => firstPriceSyncCards(
  lastPriceSyncOutcome.value,
  lastPriceSyncStatus.value,
));
const favoriteStyleDayTiles = computed(() =>
  favoriteArtStyleDayRows(artStyles.value, lastSyncCards.value),
);
const favoriteStyleDayByKey = computed(() => {
  const next = new Map();
  for (const row of favoriteStyleDayTiles.value) {
    next.set(favoriteArtStyleKey(row.setCode, row.artStyle), row);
  }
  return next;
});
const ownedCards = computed(() => filterCollectionCards(cards.value, {
  ownedFilter: "owned",
}));
const favoriteCardDayTiles = computed(() =>
  favoriteCardDayRows(ownedCards.value, lastSyncCards.value),
);
const favoriteSetDayTiles = computed(() =>
  favoriteSetDayRows(sets.value, lastSyncCards.value, {
    catalogSets: catalogSets.value,
    includeHiddenSubsets: showSetBrowserSubsets.value,
  }).map((row) => ({
    ...row,
    label: setNameFor(row.setCode),
  })),
);
const hasLastPriceMovers = computed(() => (
  priceSyncHasMovers(lastPriceSyncOutcome.value)
  || priceSyncHasMovers(lastPriceSyncStatus.value?.lastSync || lastPriceSyncStatus.value)
));

async function loadLastPriceSync() {
  const status = await ignoreAborted(api.getPriceSyncStatus());
  if (status) {
    lastPriceSyncStatus.value = status;
  }
}

function openStylePriceMovers(row) {
  showStoredPriceSyncMovers(lastPriceSyncStatus.value || lastPriceSyncOutcome.value);
  router.push(homeChangesRoute({
    setCode: row.setCode,
    artStyle: row.artStyle || row.label,
  }));
}

function openLastPriceMovers() {
  showStoredPriceSyncMovers(lastPriceSyncStatus.value || lastPriceSyncOutcome.value);
  router.push(homeChangesRoute());
}

function openCardDayChange(row) {
  const match = lastSyncCards.value.find((card) => (
    String(card.setCode || "").trim().toUpperCase() === String(row.setCode || "").trim().toUpperCase()
    && String(card.collectorNumber || "").trim() === String(row.collectorNumber || "").trim()
  ));
  if (match?.artStyle) {
    openStylePriceMovers({
      setCode: match.setCode,
      artStyle: match.artStyle,
      label: match.artStyle,
    });
    return;
  }
  openLastPriceMovers();
}

const displayCards = computed(() => applyGalleryDisplayToCards(ownedCards.value));

const displayArtStyles = computed(() =>
  artStyles.value.map((style) => ({
    ...style,
    cards: applyGalleryDisplayToCards(filterCollectionCards(style.cards || [], {
      ownedFilter: "owned",
    })),
    dayChange: favoriteStyleDayByKey.value.get(
      favoriteArtStyleKey(style.setCode, style.artStyle),
    ) || null,
  })),
);

const galleryCardCount = computed(() => {
  const favouriteCards = displayCards.value.length;
  const artGalleryCards = displayArtStyles.value.reduce(
    (sum, style) => sum + (style.cards?.length || 0),
    0,
  );
  return favouriteCards + artGalleryCards;
});

const gallerySummary = computed(() => {
  const shown = galleryCardCount.value;
  return `${shown} owned card${shown === 1 ? "" : "s"}`;
});

const isEmpty = computed(
  () => !sets.value.length && !artStyles.value.length && !cards.value.length,
);

/** Above this many cards, an art-style gallery gets a bounded, virtualized
 * viewport instead of rendering every tile — some art styles span whole
 * sets and "expand all" style browsing would otherwise dump hundreds of
 * card tiles into the DOM at once. */
const ART_GALLERY_VIRTUALIZE_THRESHOLD = 40;

function isLargeArtGallery(style) {
  return (style?.cards?.length || 0) > ART_GALLERY_VIRTUALIZE_THRESHOLD;
}

function setRoute(set) {
  return collectionRouteForSet(set.setCode);
}

function artStyleRoute(style) {
  return collectionRouteForSet(style.setCode, style.artStyle);
}

function setIcon(set) {
  return set.iconUri || resolveSetIconUri(set);
}

function artCountLabel(style) {
  if (style.ownedCount == null || style.catalogCount == null) {
    return "";
  }
  return `${style.ownedCount}/${style.catalogCount}`;
}

function fullSetName(code, label = "") {
  const cleaned = setShortName({
    setCode: code,
    label: label || code,
  });
  const normalized = String(code || "").trim().toUpperCase();
  if (cleaned && cleaned.toUpperCase() !== normalized) {
    return cleaned;
  }
  return "";
}

const setNameByCode = computed(() => {
  const names = new Map();
  const remember = (code, label) => {
    const key = String(code || "").trim().toUpperCase();
    if (!key || names.has(key)) {
      return;
    }
    const name = fullSetName(key, label);
    if (name) {
      names.set(key, name);
    }
  };
  for (const set of sets.value) {
    remember(set.setCode, set.name || set.label);
  }
  for (const card of cards.value) {
    remember(card.setCode, card.setLabel || card.setName);
  }
  for (const style of artStyles.value) {
    remember(style.setCode, style.setName);
    for (const card of style.cards || []) {
      remember(card.setCode, card.setName || card.setLabel);
    }
  }
  return names;
});

function setNameFor(code) {
  const key = String(code || "").trim().toUpperCase();
  return setNameByCode.value.get(key) || catalogSetNames.value.get(key) || key;
}

async function loadCatalogSetNames() {
  const meta = await ignoreAborted(api.getReportsMeta());
  if (!meta) {
    return;
  }
  const next = new Map();
  const visible = [];
  for (const set of meta.sets || []) {
    const code = String(set.setCode || "").trim().toUpperCase();
    if (!code || code === "ALL") {
      continue;
    }
    visible.push(set);
    const name = fullSetName(code, set.name || set.label);
    if (name) {
      next.set(code, name);
    }
  }
  catalogSets.value = visible;
  catalogSetNames.value = next;
}

function artStyleTitle(style) {
  const counts = artCountLabel(style);
  const base = `${setNameFor(style.setCode)} · ${style.artStyle}`;
  return counts ? `${base} (${counts})` : base;
}

async function loadFavorites({ silent = false } = {}) {
  if (!silent) {
    loading.value = true;
    loadError.value = "";
  }
  try {
    const next = await ignoreAborted(api.getFavorites());
    if (!next) {
      return;
    }
    syncFavoritesFromPayload(next);
    payload.value = next;
  } catch (error) {
    if (!silent) {
      loadError.value = error.message || "Could not load home.";
    }
  } finally {
    if (!silent) {
      loading.value = false;
    }
  }
}

function syncCardsFromFavoriteList(nextFavorites) {
  if (!payload.value) {
    return;
  }
  const keys = new Set(
    (nextFavorites || []).map((item) =>
      favoriteCardKey(item.setCode, item.collectorNumber, item.finish),
    ),
  );
  payload.value = {
    ...payload.value,
    cards: (payload.value.cards || []).filter((card) =>
      keys.has(cardFavoriteKeyFromCard(card)),
    ),
  };
}

function removeArtStyleFromPayload(setCode, artStyle) {
  if (!payload.value) {
    return;
  }
  const key = favoriteArtStyleKey(setCode, artStyle);
  payload.value = {
    ...payload.value,
    artStyles: (payload.value.artStyles || []).filter(
      (style) => favoriteArtStyleKey(style.setCode, style.artStyle) !== key,
    ),
  };
}

function removeSetFromPayload(setCode) {
  if (!payload.value) {
    return;
  }
  const code = String(setCode || "").trim().toUpperCase();
  payload.value = {
    ...payload.value,
    sets: (payload.value.sets || []).filter(
      (set) => String(set.setCode || "").trim().toUpperCase() !== code,
    ),
  };
}

async function onUnfavoriteSet(set) {
  try {
    await api.toggleManagerSetFavorite(set.setCode);
    removeSetFromPayload(set.setCode);
    clearClientCache();
  } catch (error) {
    window.alert(error.message || "Could not update favourite set.");
  }
}

async function onUnfavoriteArtStyle(style) {
  const result = await toggleArtStyleFavorite(style.setCode, style.artStyle);
  if (!result) {
    return;
  }
  removeArtStyleFromPayload(style.setCode, style.artStyle);
}

async function onCardFavoriteChanged(result) {
  if (!result) {
    return;
  }
  if (result.favorite) {
    // Newly favourited from an art-style gallery needs a hydrated card row.
    await loadFavorites({ silent: true });
    return;
  }
  syncCardsFromFavoriteList(result.favoriteCards);
}

async function onOwnershipChanged() {
  await loadFavorites({ silent: true });
}

async function onReorderCards(nextCards) {
  if (!payload.value) {
    return;
  }
  payload.value = { ...payload.value, cards: nextCards };
  const body = nextCards.map((card) => ({
    setCode: card.setCode,
    collectorNumber: String(card.collectorNumber),
    finish: cardFinish(card),
  }));
  try {
    const result = await api.reorderFavoriteCards(body);
    favoriteCards.value = result.favoriteCards || body;
    clearClientCache();
  } catch (error) {
    window.alert(error.message || "Could not reorder favourite cards.");
    await loadFavorites({ silent: true });
  }
}

function clearArtDrag() {
  dragArtFrom.value = -1;
  dragArtOver.value = -1;
}

function onArtDragStart(index, event) {
  dragArtFrom.value = index;
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", String(index));
  }
}

function onArtDragOver(index, event) {
  if (dragArtFrom.value < 0) {
    return;
  }
  event.preventDefault();
  dragArtOver.value = index;
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = "move";
  }
}

async function onArtDrop(index, event) {
  event.preventDefault();
  const from = dragArtFrom.value;
  clearArtDrag();
  if (from < 0 || from === index || !payload.value) {
    return;
  }
  const next = artStyles.value.slice();
  const [moved] = next.splice(from, 1);
  next.splice(index, 0, moved);
  payload.value = { ...payload.value, artStyles: next };
  const body = next.map((style) => ({
    setCode: style.setCode,
    artStyle: style.artStyle,
  }));
  try {
    const result = await api.reorderFavoriteArtStyles(body);
    favoriteArtStyles.value = result.favoriteArtStyles || body;
    clearClientCache();
  } catch (error) {
    window.alert(error.message || "Could not reorder favourite art styles.");
    await loadFavorites({ silent: true });
  }
}

let unbindChangesNav = () => {};

onMounted(async () => {
  unbindChangesNav = bindHomeChangesNavigation(() => {
    if (route.name === "home") {
      router.push(homeChangesRoute());
    }
  });
  await Promise.all([
    fetchPricingSettings(),
    loadFavorites(),
    loadLastPriceSync(),
    loadCatalogSetNames(),
  ]);
});

onUnmounted(() => {
  unbindChangesNav();
});
</script>

<template>
  <div class="favorites-home-page collection-page">
    <header class="favorites-home-header">
      <div class="favorites-home-header-row">
        <h1>Home</h1>
        <div class="button-group" role="group" aria-label="Home view">
          <RouterLink
            :to="{ name: 'home' }"
            class="filter-button"
            :class="{ active: !showingChanges }"
            :aria-current="!showingChanges ? 'page' : undefined"
          >
            Starred
          </RouterLink>
          <RouterLink
            v-if="hasLastPriceMovers"
            :to="homeChangesRoute()"
            class="filter-button"
            :class="{ active: showingChanges }"
            :aria-current="showingChanges ? 'page' : undefined"
          >
            Changes
          </RouterLink>
          <button
            v-else
            type="button"
            class="filter-button"
            disabled
          >
            Changes
          </button>
        </div>
      </div>
      <p class="favorites-home-intro">
        {{ showingChanges
          ? "Owned risers and fallers from the last price update."
          : "Cards, art styles, and sets you have starred. Drag cards and art-style rows to reorder." }}
      </p>
    </header>

    <LoadingIndicator v-if="loading" label="Loading home…" />
    <p v-else-if="loadError" class="favorites-home-error">{{ loadError }}</p>
    <template v-else>
      <p v-if="isEmpty && !showingChanges" class="favorites-home-empty">
        Nothing on Home yet. Star a card tile, an art style in the filter list, or a set in the gallery.
      </p>

      <template v-if="!showingChanges">
      <div
        v-if="cards.length || artStyles.length"
        class="favorites-home-gallery-toolbar"
      >
        <p class="favorites-home-gallery-summary">{{ gallerySummary }}</p>
      </div>

      <div
        v-if="cards.length"
        class="favorites-home-highlights"
      >
        <section class="favorites-home-section home-panel favorites-home-cards-pane">
          <div class="favorites-home-section-header">
            <h2>Cards</h2>
          </div>
          <EdgeCarousel v-if="displayCards.length" label="favourite cards">
            <div class="favorites-home-cards favorites-home-art-gallery favorites-home-card-carousel collection-gallery-panel is-edge-carousel-track">
              <CollectionCardGrid
                :cards="displayCards"
                show-set-label
                :set-label-for="setNameFor"
                :card-scale="collectionCardScale"
                :price-tile-tint="showPriceTileTint"
                @ownership-changed="onOwnershipChanged"
                @favorite-changed="onCardFavoriteChanged"
                @reorder="onReorderCards"
              />
            </div>
          </EdgeCarousel>
          <p v-else class="favorites-home-muted">
            No owned favourite cards.
          </p>
        </section>
        <aside
          v-if="favoriteCardDayTiles.length"
          class="favorites-home-section home-panel favorites-home-movers"
        >
          <div class="favorites-home-section-header">
            <h2>Today</h2>
          </div>
          <p class="favorites-home-riser-caption">
            Owned + and − from the last price update.
          </p>
          <FavoriteDayChangeTiles
            variant="list"
            :items="favoriteCardDayTiles"
            @select="openCardDayChange"
          />
        </aside>
      </div>

      <section v-if="artStyles.length" class="favorites-home-section home-panel">
        <div class="favorites-home-section-header">
          <h2>Art styles</h2>
        </div>
        <div class="favorites-home-art-list">
        <div
          v-for="(style, index) in displayArtStyles"
          :key="`${style.setCode}|${style.artStyle}`"
          class="favorites-home-art-row"
          :class="{
            'is-wide': isLargeArtGallery(style),
            'is-dragging': dragArtFrom === index,
            'is-drop-target': dragArtOver === index && dragArtFrom !== index,
          }"
          @dragover="onArtDragOver(index, $event)"
          @drop="onArtDrop(index, $event)"
          @dragend="clearArtDrag"
        >
          <div class="favorites-home-art-row-header">
            <span
              class="favorites-home-drag-handle"
              draggable="true"
              title="Drag to reorder"
              role="button"
              tabindex="0"
              aria-label="Drag to reorder art style"
              @dragstart="onArtDragStart(index, $event)"
            >⋮⋮</span>
            <RouterLink :to="artStyleRoute(style)" class="favorites-home-art-row-title">
              {{ artStyleTitle(style) }}
            </RouterLink>
            <FavoriteDayChangeTiles
              v-if="style.dayChange"
              variant="inline"
              :items="[style.dayChange]"
              @select="openStylePriceMovers"
            />
            <button
              type="button"
              class="favorites-home-star is-favorite"
              aria-label="Unfavourite art style"
              title="Unfavourite art style"
              @click="onUnfavoriteArtStyle(style)"
            >
              ★
            </button>
          </div>
          <EdgeCarousel
            v-if="style.cards?.length && !isLargeArtGallery(style)"
            label="cards"
          >
            <div class="favorites-home-art-gallery collection-gallery-panel is-edge-carousel-track">
              <CollectionCardGrid
                :cards="style.cards"
                :card-scale="collectionCardScale"
                :price-tile-tint="showPriceTileTint"
                @ownership-changed="onOwnershipChanged"
                @favorite-changed="onCardFavoriteChanged"
              />
            </div>
          </EdgeCarousel>
          <div
            v-else-if="style.cards?.length"
            class="favorites-home-art-gallery collection-gallery-panel is-scrollable-group"
          >
            <VirtualizedCollectionCardGrid
              :cards="style.cards"
              :card-scale="collectionCardScale"
              :price-tile-tint="showPriceTileTint"
              @ownership-changed="onOwnershipChanged"
              @favorite-changed="onCardFavoriteChanged"
            />
          </div>
          <p v-else class="favorites-home-muted">
            No owned cards in this art style.
          </p>
        </div>
        </div>
      </section>

      <section v-if="sets.length" class="favorites-home-section home-panel">
        <h2>Sets</h2>
        <div class="favorites-home-set-grid">
          <div
            v-for="set in sets"
            :key="set.setCode"
            class="favorites-home-set-card"
          >
            <RouterLink :to="setRoute(set)" class="favorites-home-set-link">
              <img
                v-if="setIcon(set)"
                :src="setIcon(set)"
                alt=""
                class="favorites-home-set-icon"
                loading="lazy"
              >
              <div class="favorites-home-set-meta">
                <strong>{{ setNameFor(set.setCode) }}</strong>
                <span v-if="formatSetCountLabel(set)" class="favorites-home-muted">
                  {{ formatSetCountLabel(set) }}
                </span>
              </div>
            </RouterLink>
            <button
              type="button"
              class="favorites-home-star is-favorite"
              aria-label="Unfavourite set"
              title="Unfavourite set"
              @click="onUnfavoriteSet(set)"
            >
              ★
            </button>
          </div>
        </div>
      </section>
      </template>
      <PriceSyncMoversPanel
        v-else
        :cards="lastSyncCards"
        :movers="lastPriceSyncOutcome?.movers"
        :set-day-tiles="favoriteSetDayTiles"
      />
    </template>
  </div>
</template>
