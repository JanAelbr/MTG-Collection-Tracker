<script setup>
import "../styles/favorites-home.css";
import { computed, onActivated, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, clearClientCache, ignoreAborted } from "../api";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import { syncFavoritesFromPayload, useFavorites } from "../composables/favorites";
import { fetchPricingSettings } from "../composables/pricingSettings";
import { useSetGalleryFilter } from "../composables/setGalleryFilter";
import { collectionRouteForSet } from "../utils/setScope";
import { formatEuro, formatProfit, formatSetCountLabel, setShortName } from "../utils/format";
import { resolveSetIconUri } from "../utils/scryfall";
import { cardFinish, cardRouteQuery } from "../utils/finishes";
import {
  cardFavoriteKeyFromCard,
  favoriteArtStyleKey,
  favoriteCardKey,
} from "../utils/favorites";
import { applyGalleryDisplayToCards } from "../utils/priceStrategies";
import { filterCollectionCards } from "../utils/collectionFilters";
import FavoriteDayChangeTiles from "../components/FavoriteDayChangeTiles.vue";
import PriceSyncMoversPanel from "../components/PriceSyncMoversModal.vue";
import {
  bindHomeChangesNavigation,
  lastPriceSyncOutcome,
  priceSyncHasMovers,
  showStoredPriceSyncMovers,
} from "../composables/startupPriceSync";
import { homeChangesRoute, homeRouteQueryValue } from "../utils/homeRoutes";
import {
  compareCardsByCollectorNumber,
  firstPriceSyncCards,
  favoriteArtStyleDayRows,
  favoriteCardDayRows,
  favoriteSetDayRows,
  favoriteSetsDayTotal,
} from "../utils/priceSyncMovers";

defineOptions({ name: "FavoritesHomeView" });

const route = useRoute();
const router = useRouter();
const showingDetail = computed(() => Boolean(
  homeRouteQueryValue(route.query.set) || homeRouteQueryValue(route.query.art),
));
const payload = ref(null);
const loading = ref(true);
const loadError = ref("");
const dragArtFrom = ref(-1);
const dragArtOver = ref(-1);
const lastPriceSyncStatus = ref(null);
const catalogSetNames = ref(new Map());
const catalogSets = ref([]);
const { showSetBrowserSubsets } = useSetGalleryFilter();
const { toggleArtStyleFavorite, toggleCardFavorite, favoriteArtStyles } = useFavorites();

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
function sortChangedFirst(rows) {
  return rows.slice().sort((left, right) => {
    const leftMoved = Number(left.delta) !== 0;
    const rightMoved = Number(right.delta) !== 0;
    if (leftMoved !== rightMoved) {
      return leftMoved ? -1 : 1;
    }
    if (leftMoved) {
      return Math.abs(right.delta) - Math.abs(left.delta);
    }
    return 0;
  });
}

const favoriteSetDayTiles = computed(() =>
  favoriteSetDayRows(sets.value, lastSyncCards.value, {
    catalogSets: catalogSets.value,
    includeHiddenSubsets: showSetBrowserSubsets.value,
  }).map((row) => ({
    ...row,
    label: setNameFor(row.setCode),
  })),
);
const favoriteSetSummaries = computed(() => {
  const tiles = new Map(favoriteSetDayTiles.value.map((row) => [row.setCode, row]));
  return sets.value.map((set) => {
    const setCode = String(set.setCode || "").trim().toUpperCase();
    const tile = tiles.get(setCode);
    return {
      ...set,
      setCode,
      up: tile?.up || 0,
      down: tile?.down || 0,
      delta: tile?.delta || 0,
    };
  });
});
const favoriteSetsTotal = computed(() =>
  favoriteSetsDayTotal(favoriteSetDayTiles.value, lastSyncCards.value),
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
  if (route.name === "home" && !showingDetail.value) {
    document.getElementById("home-movers")?.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  router.push(homeChangesRoute());
}

const openFavoriteSets = ref(new Set());

function favoriteSetCode(set) {
  return String(set?.setCode || "").trim().toUpperCase();
}

function isFavoriteSetOpen(set) {
  return openFavoriteSets.value.has(favoriteSetCode(set));
}

function toggleFavoriteSet(set) {
  const code = favoriteSetCode(set);
  if (!code) {
    return;
  }
  const next = new Set(openFavoriteSets.value);
  if (next.has(code)) {
    next.delete(code);
  } else {
    next.add(code);
  }
  openFavoriteSets.value = next;
}

function cardRoute(card) {
  return {
    name: "card",
    params: {
      setCode: card.setCode,
      collectorNumber: String(card.collectorNumber),
    },
    query: cardRouteQuery(cardFinish(card)),
  };
}

function formatSide(amount) {
  if (!Number(amount)) {
    return formatEuro(0);
  }
  return formatProfit(amount);
}

function openFavoriteCard(row) {
  router.push(cardRoute(row));
}

async function onCardOwnershipChanged() {
  await loadFavorites({ silent: true });
}

const displayCards = computed(() => applyGalleryDisplayToCards(ownedCards.value));
const favoriteCardDayTiles = computed(() =>
  sortChangedFirst(favoriteCardDayRows(displayCards.value, lastSyncCards.value)),
);

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

const artStyleToday = computed(() => {
  const sync = lastSyncCards.value;
  const next = new Map();
  for (const style of displayArtStyles.value) {
    const rows = favoriteCardDayRows(style.cards, sync).slice().sort(compareCardsByCollectorNumber);
    next.set(favoriteArtStyleKey(style.setCode, style.artStyle), { shown: rows });
  }
  return next;
});

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

function styleToday(style) {
  return artStyleToday.value.get(favoriteArtStyleKey(style.setCode, style.artStyle))
    || { shown: [] };
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

async function onUnfavoriteArtStyle(style) {
  const result = await toggleArtStyleFavorite(style.setCode, style.artStyle);
  if (!result) {
    return;
  }
  removeArtStyleFromPayload(style.setCode, style.artStyle);
}

async function onUnfavoriteCard(card) {
  const result = await toggleCardFavorite(card, cardFinish(card));
  if (!result || result.favorite) {
    return;
  }
  syncCardsFromFavoriteList(result.favoriteCards);
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
let homeReady = false;

function refreshHome({ silent = false } = {}) {
  return Promise.all([
    fetchPricingSettings(),
    loadFavorites({ silent }),
    loadLastPriceSync(),
    loadCatalogSetNames(),
  ]);
}

onMounted(() => {
  unbindChangesNav = bindHomeChangesNavigation(() => {
    openLastPriceMovers();
  });
  refreshHome();
});

onActivated(() => {
  if (!homeReady) {
    homeReady = true;
    return;
  }
  refreshHome({ silent: true });
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
      </div>
      <p v-if="!showingDetail" class="favorites-home-intro">
        Starred cards, art styles, and sets, with today's price moves. Drag art-style rows to reorder.
      </p>
    </header>

    <LoadingIndicator v-if="loading" label="Loading home…" />
    <p v-else-if="loadError" class="favorites-home-error">{{ loadError }}</p>
    <template v-else>
      <p v-if="isEmpty && !showingDetail" class="favorites-home-empty">
        Nothing on Home yet. Star a card tile, an art style in the filter list, or a set in the gallery.
      </p>

      <template v-if="!showingDetail">
      <div
        v-if="cards.length || artStyles.length"
        class="favorites-home-gallery-toolbar"
      >
        <p class="favorites-home-gallery-summary">{{ gallerySummary }}</p>
      </div>

      <div
        v-if="sets.length || hasLastPriceMovers || cards.length"
        class="favorites-home-card-row"
      >
        <section v-if="sets.length" class="favorites-home-section home-panel favorites-home-sets-pane">
          <div class="favorites-home-section-header">
            <h2>Favourite sets</h2>
            <p class="favorites-home-set-total">
              <span class="is-up">{{ formatProfit(favoriteSetsTotal.up) }}</span>
              <span class="is-down">{{ formatProfit(favoriteSetsTotal.down) }}</span>
              <strong :class="favoriteSetsTotal.delta < 0 ? 'is-down' : 'is-up'">
                {{ formatProfit(favoriteSetsTotal.delta) }}
              </strong>
            </p>
          </div>
          <div class="favorites-home-set-grid">
            <div
              v-for="set in favoriteSetSummaries"
              :key="set.setCode"
              class="favorites-home-set-card"
              :class="{ 'is-open': isFavoriteSetOpen(set) }"
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
                class="favorite-set-delta"
                :class="{ 'is-open': isFavoriteSetOpen(set) }"
                :aria-expanded="isFavoriteSetOpen(set)"
                :aria-label="`Today's change for ${setNameFor(set.setCode)}`"
                title="Today's change"
                @click="toggleFavoriteSet(set)"
              >
                <span class="is-up">{{ formatSide(set.up) }}</span>
                <span class="is-down">{{ formatSide(set.down) }}</span>
                <strong :class="set.delta < 0 ? 'is-down' : 'is-up'">{{ formatProfit(set.delta) }}</strong>
              </button>
              <div v-if="isFavoriteSetOpen(set)" class="favorites-home-set-expand">
                <PriceSyncMoversPanel
                  embedded
                  :fixed-set-code="set.setCode"
                  :cards="lastSyncCards"
                  :movers="lastPriceSyncOutcome?.movers"
                  :set-day-tiles="favoriteSetDayTiles"
                  :source-cards="displayCards"
                />
              </div>
            </div>
          </div>
        </section>
        <section v-if="cards.length" class="favorites-home-section home-panel favorites-home-cards-pane">
          <div class="favorites-home-section-header">
            <h2>Favourite cards</h2>
          </div>
          <FavoriteDayChangeTiles
            v-if="favoriteCardDayTiles.length"
            class="favorites-home-card-list"
            variant="list"
            columns
            show-price
            :items="favoriteCardDayTiles"
            @select="openFavoriteCard"
            @ownership-changed="onCardOwnershipChanged"
          >
            <template #extra="{ item }">
              <button
                type="button"
                class="favorites-home-star is-favorite favorite-day-tile-star"
                aria-label="Unfavourite card"
                title="Unfavourite card"
                @click.stop="onUnfavoriteCard(item)"
              >
                ★
              </button>
            </template>
          </FavoriteDayChangeTiles>
          <p v-else class="favorites-home-muted">
            No owned favourite cards.
          </p>
        </section>
        <div
          v-if="hasLastPriceMovers"
          id="home-movers"
          class="favorites-home-mover-pair"
        >
          <section class="favorites-home-section home-panel favorites-home-movers">
            <div class="favorites-home-section-header">
              <h2>Risers</h2>
            </div>
            <PriceSyncMoversPanel
              variant="cards"
              side="up"
              :cards="lastSyncCards"
              :movers="lastPriceSyncOutcome?.movers"
              :set-day-tiles="favoriteSetDayTiles"
              :source-cards="displayCards"
            />
          </section>
          <section class="favorites-home-section home-panel favorites-home-movers">
            <div class="favorites-home-section-header">
              <h2>Fallers</h2>
            </div>
            <PriceSyncMoversPanel
              variant="cards"
              side="down"
              :cards="lastSyncCards"
              :movers="lastPriceSyncOutcome?.movers"
              :set-day-tiles="favoriteSetDayTiles"
              :source-cards="displayCards"
            />
          </section>
        </div>
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
          <div v-if="styleToday(style).shown.length" class="favorites-home-art-today">
            <FavoriteDayChangeTiles
              variant="list"
              columns
              show-price
              :items="styleToday(style).shown"
              empty-label="No owned cards in this art style."
              @select="openFavoriteCard"
              @ownership-changed="onCardOwnershipChanged"
            />
          </div>
          <p v-else class="favorites-home-muted">
            No owned cards in this art style.
          </p>
        </div>
        </div>
      </section>
      </template>
      <PriceSyncMoversPanel
        v-else
        :cards="lastSyncCards"
        :movers="lastPriceSyncOutcome?.movers"
        :set-day-tiles="favoriteSetDayTiles"
        :source-cards="displayCards"
      />
    </template>
  </div>
</template>
