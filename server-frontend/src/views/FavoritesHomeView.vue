<script setup>
import "../styles/favorites-home.css";
import { computed, onMounted, ref } from "vue";
import { api, clearClientCache, ignoreAborted } from "../api";
import CollectionCardGrid from "../components/CollectionCardGrid.vue";
import VirtualizedCollectionCardGrid from "../components/VirtualizedCollectionCardGrid.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import { fetchFavorites, useFavorites } from "../composables/favorites";
import {
  fetchPricingSettings,
  savePricingSettings,
  usePricingSettings,
} from "../composables/pricingSettings";
import { collectionRouteForSet } from "../utils/setScope";
import { formatSetCountLabel, setDisplayName } from "../utils/format";
import { resolveSetIconUri } from "../utils/scryfall";
import { cardFinish } from "../utils/finishes";
import {
  cardFavoriteKeyFromCard,
  favoriteArtStyleKey,
  favoriteCardKey,
} from "../utils/favorites";
import { applyStrategyToCards } from "../utils/priceStrategies";

const payload = ref(null);
const loading = ref(true);
const loadError = ref("");
const dragArtFrom = ref(-1);
const dragArtOver = ref(-1);
const { settings: pricingSettings, collectionCardScale } = usePricingSettings();
const { toggleArtStyleFavorite, favoriteCards, favoriteArtStyles } = useFavorites();

const sets = computed(() => payload.value?.sets || []);
const artStyles = computed(() => payload.value?.artStyles || []);
const cards = computed(() => payload.value?.cards || []);

const priceStrategies = computed(() => pricingSettings.value?.priceStrategies || []);
const globalPriceStrategy = computed(
  () => pricingSettings.value?.priceStrategy || "trend",
);

const cardsPriceStrategy = computed(
  () => pricingSettings.value?.favoritesCardsPriceStrategy || globalPriceStrategy.value,
);

const artStylesPriceStrategy = computed(
  () =>
    pricingSettings.value?.favoritesArtStylesPriceStrategy || globalPriceStrategy.value,
);

const displayCards = computed(() =>
  applyStrategyToCards(cards.value, cardsPriceStrategy.value),
);

const displayArtStyles = computed(() =>
  artStyles.value.map((style) => ({
    ...style,
    cards: applyStrategyToCards(style.cards || [], artStylesPriceStrategy.value),
  })),
);

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
    await fetchFavorites(true);
    const next = await ignoreAborted(api.getFavorites());
    if (!next) {
      return;
    }
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

async function onCardsPriceStrategyChange(event) {
  await savePricingSettings({ favoritesCardsPriceStrategy: event.target.value });
}

async function onArtStylesPriceStrategyChange(event) {
  await savePricingSettings({ favoritesArtStylesPriceStrategy: event.target.value });
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
  await fetchPricingSettings();
  await loadFavorites();
});
</script>

<template>
  <div class="favorites-home-page collection-page">
    <header class="favorites-home-header">
      <h1>Favourites</h1>
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

      <section v-if="cards.length" class="favorites-home-section home-panel">
        <div class="favorites-home-section-header">
          <h2>Cards</h2>
          <label v-if="priceStrategies.length" class="manager-filter favorites-home-strategy">
            <span>Price strategy</span>
            <select
              :value="cardsPriceStrategy"
              aria-label="Favourite cards price strategy"
              @change="onCardsPriceStrategyChange"
            >
              <option
                v-for="strategy in priceStrategies"
                :key="strategy.id"
                :value="strategy.id"
              >
                {{ strategy.label }}
              </option>
            </select>
          </label>
        </div>
        <div class="favorites-home-cards collection-gallery-panel">
          <CollectionCardGrid
            :cards="displayCards"
            show-set-label
            show-unowned-badge
            reorderable
            :card-scale="collectionCardScale"
            :price-strategy="cardsPriceStrategy"
            @ownership-changed="onOwnershipChanged"
            @favorite-changed="onCardFavoriteChanged"
            @reorder="onReorderCards"
          />
        </div>
      </section>

      <section v-if="artStyles.length" class="favorites-home-section home-panel">
        <div class="favorites-home-section-header">
          <h2>Art styles</h2>
          <label v-if="priceStrategies.length" class="manager-filter favorites-home-strategy">
            <span>Price strategy</span>
            <select
              :value="artStylesPriceStrategy"
              aria-label="Favourite art styles price strategy"
              @change="onArtStylesPriceStrategyChange"
            >
              <option
                v-for="strategy in priceStrategies"
                :key="strategy.id"
                :value="strategy.id"
              >
                {{ strategy.label }}
              </option>
            </select>
          </label>
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
              :price-strategy="artStylesPriceStrategy"
              @ownership-changed="onOwnershipChanged"
              @favorite-changed="onCardFavoriteChanged"
            />
            <CollectionCardGrid
              v-else
              :cards="style.cards"
              show-unowned-badge
              :card-scale="collectionCardScale"
              :price-strategy="artStylesPriceStrategy"
              @ownership-changed="onOwnershipChanged"
              @favorite-changed="onCardFavoriteChanged"
            />
          </div>
          <p v-else class="favorites-home-muted">No cards in this art style yet.</p>
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
