<script setup>
import "../styles/favorites-home.css";
import { computed, onMounted, ref, watch } from "vue";
import { api, clearClientCache, ignoreAborted, isApiAbortError } from "../api";
import CollectionCardGrid from "../components/CollectionCardGrid.vue";
import VirtualizedCollectionCardGrid from "../components/VirtualizedCollectionCardGrid.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import { syncFavoritesFromPayload, useFavorites } from "../composables/favorites";
import {
  fetchPricingSettings,
  usePricingSettings,
} from "../composables/pricingSettings";
import { collectionRouteForSet } from "../utils/setScope";
import { formatSetCountLabel, formatProfit, setDisplayName } from "../utils/format";
import { resolveSetIconUri } from "../utils/scryfall";
import { cardFinish } from "../utils/finishes";
import {
  cardFavoriteKeyFromCard,
  favoriteArtStyleKey,
  favoriteCardKey,
} from "../utils/favorites";
import { applyGalleryDisplayToCards } from "../utils/priceStrategies";
import { filterCollectionCards } from "../utils/collectionFilters";
import {
  defaultCollectionSortDir,
  sortCollectionCards,
} from "../utils/collectionSort";
import { shouldApplyPriceTileTint } from "../utils/catalogGroups";
import {
  lastPriceSyncOutcome,
  priceSyncHasMovers,
  showStoredPriceSyncMovers,
} from "../composables/startupPriceSync";
import {
  MOVER_SCALE_ABSOLUTE,
  MOVER_SCALE_PERCENT,
  loadMoverScale,
  saveMoverScale,
  topArtStyleMoversFromHistory,
  topArtStyleRisersFromHistory,
} from "../utils/breakdownHistory";

const GALLERY_SORT_OPTIONS = [
  { id: "value", label: "Value" },
  { id: "name", label: "Name" },
  { id: "number", label: "Number" },
  { id: "cmc", label: "CMC" },
  { id: "rarity", label: "Rarity" },
];

const payload = ref(null);
const loading = ref(true);
const loadError = ref("");
const historyPoints = ref([]);
const favoriteCardsScroller = ref(null);
const moverScale = ref(loadMoverScale());
const dragArtFrom = ref(-1);
const dragArtOver = ref(-1);
const lastPriceSyncStatus = ref(null);
const galleryOwnedFilter = ref("owned");
const gallerySort = ref("number");
const gallerySortDir = ref(defaultCollectionSortDir("number"));
const { settings: pricingSettings, collectionCardScale, collectionPriceTileTint } = usePricingSettings();
const showPriceTileTint = computed(() => shouldApplyPriceTileTint({
  enabled: collectionPriceTileTint.value,
  sort: gallerySort.value,
}));
const { toggleArtStyleFavorite, favoriteCards, favoriteArtStyles } = useFavorites();

const sets = computed(() => payload.value?.sets || []);
const artStyles = computed(() => payload.value?.artStyles || []);
const cards = computed(() => payload.value?.cards || []);
const artStyleMoverOptions = computed(() => ({
  limit: 10,
  favoriteSetCodes: sets.value.map((set) => set.setCode),
  scale: moverScale.value,
}));
const artStyleRisers = computed(() =>
  topArtStyleRisersFromHistory(historyPoints.value, artStyleMoverOptions.value),
);
const artStyleFallers = computed(() =>
  topArtStyleMoversFromHistory(historyPoints.value, {
    ...artStyleMoverOptions.value,
    direction: "down",
  }),
);
const artStyleMoverColumns = computed(() => [
  { id: "up", title: "Top risers", rows: artStyleRisers.value },
  { id: "down", title: "Top fallers", rows: artStyleFallers.value },
].filter((column) => column.rows.length));
const moverCompareDate = computed(() => {
  const points = historyPoints.value;
  if (!Array.isArray(points) || points.length < 2) {
    return "";
  }
  return String(points[points.length - 2]?.date || "").trim();
});
const moverCompareCaption = computed(() => {
  const date = formatSnapshotDay(moverCompareDate.value);
  return date
    ? `Art styles in favourite sets vs ${date}`
    : "Art styles in favourite sets vs previous snapshot";
});

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
  showStoredPriceSyncMovers(lastPriceSyncStatus.value || lastPriceSyncOutcome.value, {
    setCode: row.setCode,
    artStyle: row.artStyle,
    label: row.artStyle || row.label,
  });
}

function openLastPriceMovers() {
  showStoredPriceSyncMovers(lastPriceSyncStatus.value || lastPriceSyncOutcome.value);
}

const displayCards = computed(() => {
  const filtered = filterCollectionCards(cards.value, {
    ownedFilter: galleryOwnedFilter.value,
  });
  return applyGalleryDisplayToCards(filtered);
});

const displayArtStyles = computed(() =>
  artStyles.value.map((style) => {
    const filtered = filterCollectionCards(style.cards || [], {
      ownedFilter: galleryOwnedFilter.value,
    });
    const sorted = sortCollectionCards(filtered, {
      sort: gallerySort.value,
      dir: gallerySortDir.value,
    });
    return {
      ...style,
      cards: applyGalleryDisplayToCards(sorted),
    };
  }),
);

const galleryCardCount = computed(() => {
  const favouriteCards = displayCards.value.length;
  const artGalleryCards = displayArtStyles.value.reduce(
    (sum, style) => sum + (style.cards?.length || 0),
    0,
  );
  return favouriteCards + artGalleryCards;
});

const galleryTotalCardCount = computed(() => {
  const favouriteCards = cards.value.length;
  const artGalleryCards = artStyles.value.reduce(
    (sum, style) => sum + (style.cards?.length || 0),
    0,
  );
  return favouriteCards + artGalleryCards;
});

const gallerySummary = computed(() => {
  const shown = galleryCardCount.value;
  const total = galleryTotalCardCount.value;
  if (galleryOwnedFilter.value === "owned") {
    return `${shown} owned card${shown === 1 ? "" : "s"}`;
  }
  return `${shown} shown · ${total} total`;
});

const cardsReorderable = computed(() => galleryOwnedFilter.value === "all");

function setGalleryOwnedFilter(next) {
  if (galleryOwnedFilter.value === next) {
    return;
  }
  galleryOwnedFilter.value = next;
}

function onGallerySortChange(event) {
  const next = event.target.value;
  if (next === gallerySort.value) {
    return;
  }
  gallerySort.value = next;
  gallerySortDir.value = defaultCollectionSortDir(next);
}

function toggleGallerySortDir() {
  gallerySortDir.value = gallerySortDir.value === "asc" ? "desc" : "asc";
}

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

function artStyleTitle(style) {
  const counts = artCountLabel(style);
  const base = `${style.setCode} · ${style.artStyle}`;
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
      loadError.value = error.message || "Could not load favourites.";
    }
  } finally {
    if (!silent) {
      loading.value = false;
    }
  }
}

async function loadArtStyleRisers() {
  try {
    const next = await ignoreAborted(api.listStorageBreakdownHistory());
    if (!next) {
      return;
    }
    historyPoints.value = next.points || [];
  } catch (error) {
    if (!isApiAbortError(error)) {
      historyPoints.value = [];
    }
  }
}

function scrollFavoriteCards(direction) {
  const scroller = favoriteCardsScroller.value;
  if (!scroller) {
    return;
  }
  const item = scroller.querySelector(".collection-card-grid-item");
  const gap = item
    ? Number.parseFloat(getComputedStyle(item.parentElement).columnGap || "16") || 16
    : 16;
  const step = item
    ? item.getBoundingClientRect().width + gap
    : scroller.clientWidth * 0.8;
  scroller.scrollBy({ left: direction * step, behavior: "smooth" });
}

function formatMoverValue(row) {
  if (moverScale.value === MOVER_SCALE_ABSOLUTE) {
    return formatProfit((Number(row?.current) || 0) - (Number(row?.previous) || 0));
  }
  const percent = Number(row?.percent);
  if (!Number.isFinite(percent)) {
    return "";
  }
  const formatted = `${Math.abs(percent).toFixed(1)}%`;
  if (percent > 0) {
    return `+${formatted}`;
  }
  if (percent < 0) {
    return `−${formatted}`;
  }
  return `0.0%`;
}

function formatSnapshotDay(raw) {
  const text = String(raw || "").trim();
  if (!text) {
    return "";
  }
  const date = new Date(`${text.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) {
    return text;
  }
  return date.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

watch(moverScale, (next) => {
  saveMoverScale(next);
});

function setMoverScale(next) {
  moverScale.value = next === MOVER_SCALE_ABSOLUTE
    ? MOVER_SCALE_ABSOLUTE
    : MOVER_SCALE_PERCENT;
}

function moverSet(row) {
  const code = String(row?.setCode || "").trim().toUpperCase();
  if (!code) {
    return null;
  }
  return sets.value.find(
    (set) => String(set.setCode || "").trim().toUpperCase() === code,
  ) || { setCode: code };
}

function moverSetIcon(row) {
  const set = moverSet(row);
  return set ? setIcon(set) : "";
}

function onMoverCardEnter(event) {
  const card = event.currentTarget;
  const label = card.querySelector(".favorites-home-mover-label");
  if (!label) {
    return;
  }
  card.classList.toggle("is-label-clipped", label.scrollWidth > label.clientWidth + 0.5);
}

function onMoverCardLeave(event) {
  event.currentTarget.classList.remove("is-label-clipped");
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

onMounted(async () => {
  await Promise.all([
    fetchPricingSettings(),
    loadFavorites(),
    loadArtStyleRisers(),
    loadLastPriceSync(),
  ]);
});
</script>

<template>
  <div class="favorites-home-page collection-page">
    <header class="favorites-home-header">
      <div class="favorites-home-header-row">
        <h1>Favourites</h1>
        <button
          v-if="hasLastPriceMovers"
          type="button"
          class="btn btn-secondary"
          @click="openLastPriceMovers"
        >
          Last price movers
        </button>
      </div>
      <p class="favorites-home-intro">
        Cards, art styles, and sets you have starred. Drag cards and art-style rows to reorder.
      </p>
    </header>

    <LoadingIndicator v-if="loading" label="Loading favourites…" />
    <p v-else-if="loadError" class="favorites-home-error">{{ loadError }}</p>
    <template v-else>
      <p v-if="isEmpty" class="favorites-home-empty">
        No favourites yet. Star a card tile, an art style in the filter list, or a set in the gallery.
      </p>

      <div
        v-if="cards.length || artStyles.length"
        class="favorites-home-gallery-toolbar"
      >
        <div
          class="button-group collection-ownership-group collection-ownership-group--binary"
          role="group"
          aria-label="Ownership filter"
        >
          <button
            type="button"
            class="filter-button"
            :class="{ active: galleryOwnedFilter === 'owned' }"
            @click="setGalleryOwnedFilter('owned')"
          >
            Owned
          </button>
          <button
            type="button"
            class="filter-button"
            :class="{ active: galleryOwnedFilter === 'all' }"
            @click="setGalleryOwnedFilter('all')"
          >
            All
          </button>
        </div>
        <label class="collection-all-sort favorites-home-gallery-sort" for="favorites-gallery-sort">
          <span class="visually-hidden">Sort art styles by</span>
          <div class="collection-sort-row">
            <select id="favorites-gallery-sort" :value="gallerySort" @change="onGallerySortChange">
              <option
                v-for="option in GALLERY_SORT_OPTIONS"
                :key="option.id"
                :value="option.id"
              >
                {{ option.label }}
              </option>
            </select>
            <button
              type="button"
              class="btn btn-secondary collection-sort-dir"
              :title="gallerySortDir === 'asc' ? 'Ascending' : 'Descending'"
              :aria-label="`Sort ${gallerySortDir === 'asc' ? 'ascending' : 'descending'}`"
              @click="toggleGallerySortDir"
            >
              {{ gallerySortDir === "asc" ? "↑" : "↓" }}
            </button>
          </div>
        </label>
        <p class="favorites-home-gallery-summary">{{ gallerySummary }}</p>
      </div>

      <div
        v-if="cards.length || artStyleMoverColumns.length"
        class="favorites-home-highlights"
      >
        <section v-if="cards.length" class="favorites-home-section home-panel favorites-home-cards-pane">
          <div class="favorites-home-section-header">
            <h2>Cards</h2>
            <div
              v-if="displayCards.length > 1"
              class="favorites-home-carousel-nav"
            >
              <button
                type="button"
                class="btn btn-secondary"
                aria-label="Previous favourite cards"
                @click="scrollFavoriteCards(-1)"
              >
                ‹
              </button>
              <button
                type="button"
                class="btn btn-secondary"
                aria-label="Next favourite cards"
                @click="scrollFavoriteCards(1)"
              >
                ›
              </button>
            </div>
          </div>
          <div
            v-if="displayCards.length"
            ref="favoriteCardsScroller"
            class="favorites-home-cards favorites-home-art-gallery favorites-home-card-carousel collection-gallery-panel"
          >
            <CollectionCardGrid
              :cards="displayCards"
              show-set-label
              show-unowned-badge
              :reorderable="cardsReorderable"
              :card-scale="collectionCardScale"
              :price-tile-tint="showPriceTileTint"
              @ownership-changed="onOwnershipChanged"
              @favorite-changed="onCardFavoriteChanged"
              @reorder="onReorderCards"
            />
          </div>
          <p v-else class="favorites-home-muted">
            {{ galleryOwnedFilter === "owned" ? "No owned favourite cards." : "No favourite cards." }}
          </p>
        </section>
        <section
          v-for="column in artStyleMoverColumns"
          :key="column.id"
          class="favorites-home-section home-panel favorites-home-movers"
        >
          <div class="favorites-home-section-header">
            <h2>{{ column.title }}</h2>
            <div class="button-group" role="group" aria-label="Change scale">
              <button
                type="button"
                class="filter-button"
                :class="{ active: moverScale === MOVER_SCALE_PERCENT }"
                :aria-pressed="moverScale === MOVER_SCALE_PERCENT"
                @click="setMoverScale(MOVER_SCALE_PERCENT)"
              >
                %
              </button>
              <button
                type="button"
                class="filter-button"
                :class="{ active: moverScale === MOVER_SCALE_ABSOLUTE }"
                :aria-pressed="moverScale === MOVER_SCALE_ABSOLUTE"
                @click="setMoverScale(MOVER_SCALE_ABSOLUTE)"
              >
                €
              </button>
            </div>
          </div>
          <p class="favorites-home-riser-caption">
            {{ moverCompareCaption }}
          </p>
          <ol>
            <li v-for="row in column.rows" :key="row.id">
              <button
                type="button"
                class="favorites-home-set-card favorites-home-mover-card"
                :class="{ 'is-down': column.id === 'down' }"
                :title="row.artStyle || row.label"
                @click="openStylePriceMovers(row)"
                @mouseenter="onMoverCardEnter"
                @mouseleave="onMoverCardLeave"
              >
                <img
                  v-if="moverSetIcon(row)"
                  :src="moverSetIcon(row)"
                  alt=""
                  class="favorites-home-set-icon"
                  loading="lazy"
                >
                <span class="favorites-home-mover-label">{{ row.artStyle || row.label }}</span>
                <strong
                  :class="row.percent < 0 ? 'reports-loss' : 'reports-gain'"
                >{{ formatMoverValue(row) }}</strong>
              </button>
            </li>
          </ol>
        </section>
      </div>

      <section v-if="artStyles.length" class="favorites-home-section home-panel">
        <div class="favorites-home-section-header">
          <h2>Art styles</h2>
        </div>
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
          <div
            v-if="style.cards?.length"
            class="favorites-home-art-gallery collection-gallery-panel"
            :class="{ 'is-scrollable-group': isLargeArtGallery(style) }"
          >
            <VirtualizedCollectionCardGrid
              v-if="isLargeArtGallery(style)"
              :cards="style.cards"
              show-unowned-badge
              :card-scale="collectionCardScale"
              :price-tile-tint="showPriceTileTint"
              @ownership-changed="onOwnershipChanged"
              @favorite-changed="onCardFavoriteChanged"
            />
            <CollectionCardGrid
              v-else
              :cards="style.cards"
              show-unowned-badge
              :card-scale="collectionCardScale"
              :price-tile-tint="showPriceTileTint"
              @ownership-changed="onOwnershipChanged"
              @favorite-changed="onCardFavoriteChanged"
            />
          </div>
          <p v-else class="favorites-home-muted">
            {{ galleryOwnedFilter === "owned" ? "No owned cards in this art style." : "No cards in this art style yet." }}
          </p>
        </div>
      </section>

      <section v-if="sets.length" class="favorites-home-section home-panel">
        <h2>Sets</h2>
        <div class="favorites-home-set-grid">
          <RouterLink
            v-for="set in sets"
            :key="set.setCode"
            :to="setRoute(set)"
            class="favorites-home-set-card"
          >
            <img
              v-if="setIcon(set)"
              :src="setIcon(set)"
              alt=""
              class="favorites-home-set-icon"
              loading="lazy"
            >
            <div class="favorites-home-set-meta">
              <strong>{{ set.setCode }}</strong>
              <span>{{ setDisplayName(set) || set.label || set.setCode }}</span>
              <span v-if="formatSetCountLabel(set)" class="favorites-home-muted">
                {{ formatSetCountLabel(set) }}
              </span>
            </div>
            <button
              type="button"
              class="favorites-home-star is-favorite"
              aria-label="Unfavourite set"
              title="Unfavourite set"
              @click.prevent.stop="onUnfavoriteSet(set)"
            >
              ★
            </button>
          </RouterLink>
        </div>
      </section>
    </template>
  </div>
</template>
