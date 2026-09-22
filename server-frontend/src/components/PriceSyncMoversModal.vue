<script setup>
import { computed, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { api, ignoreAborted } from "../api";
import CardFinishBadge from "./CardFinishBadge.vue";
import CardInteractiveImage from "./CardInteractiveImage.vue";
import EdgeCarousel from "./EdgeCarousel.vue";
import FavoriteDayChangeTiles from "./FavoriteDayChangeTiles.vue";
import { formatEuro, formatProfit, setShortName } from "../utils/format";
import { cardFinish, cardRouteQuery } from "../utils/finishes";
import {
  cardsForArtStyle,
  collectPriceSyncCards,
  collectPriceSyncStyleRows,
  moverRowToTileCard,
  rankMoverRows,
} from "../utils/priceSyncMovers";
import { applySetGalleryIconFallback, resolveSetIconUri } from "../utils/scryfall";
import { homeChangesRoute, homeRouteQueryValue } from "../utils/homeRoutes";

const props = defineProps({
  cards: { type: Array, default: () => [] },
  movers: { type: Object, default: () => ({}) },
  setDayTiles: { type: Array, default: () => [] },
});

const route = useRoute();
const router = useRouter();
const setsByCode = ref(new Map());

const routeSetCode = computed(() => homeRouteQueryValue(route.query.set).toUpperCase());
const routeArtStyle = computed(() => homeRouteQueryValue(route.query.art));
const setScope = computed(() => {
  const setCode = routeSetCode.value;
  if (!setCode) {
    return null;
  }
  const tile = (props.setDayTiles || []).find((item) => (
    String(item?.setCode || "").trim().toUpperCase() === setCode
  ));
  const memberCodes = Array.isArray(tile?.memberCodes) && tile.memberCodes.length
    ? tile.memberCodes
    : [setCode];
  return { setCode, memberCodes };
});
const styleFilter = computed(() => {
  const setCode = routeSetCode.value;
  const artStyle = routeArtStyle.value;
  if (!setCode || !artStyle) {
    return null;
  }
  return {
    setCode,
    artStyle,
    label: artStyle,
  };
});

loadSetCatalog();

async function loadSetCatalog() {
  const payload = await ignoreAborted(api.getReportsMeta());
  if (!payload) {
    return;
  }
  const next = new Map();
  for (const set of payload.sets || []) {
    const code = String(set.setCode || "").trim().toUpperCase();
    if (code && code !== "ALL") {
      next.set(code, set);
    }
  }
  setsByCode.value = next;
}

function setMeta(rowOrCode) {
  const code = String(rowOrCode?.setCode || rowOrCode || "").trim().toUpperCase();
  if (!code) {
    return null;
  }
  return setsByCode.value.get(code) || { setCode: code };
}

function setName(rowOrCode) {
  const set = setMeta(rowOrCode);
  return setShortName(set) || String(set?.setCode || "").toUpperCase();
}

function setIcon(rowOrCode) {
  const set = setMeta(rowOrCode);
  return set ? (set.iconUri || resolveSetIconUri(set)) : "";
}

function onSetIconError(event, rowOrCode) {
  if (!applySetGalleryIconFallback(event.target, setMeta(rowOrCode))) {
    event.target.style.display = "none";
  }
}

const storedCards = computed(() => collectPriceSyncCards({
  cards: props.cards,
  movers: props.movers,
}));
const styleRows = computed(() => collectPriceSyncStyleRows({
  cards: props.cards,
  movers: props.movers,
}));
function scopeMemberCodes(scope) {
  const listed = Array.isArray(scope?.memberCodes) ? scope.memberCodes : [];
  const codes = listed.length ? listed : [scope?.setCode];
  return new Set(
    codes
      .map((code) => String(code || "").trim().toUpperCase())
      .filter(Boolean),
  );
}

const visibleStyleRows = computed(() => {
  if (!setScope.value) {
    return styleRows.value;
  }
  const members = scopeMemberCodes(setScope.value);
  return styleRows.value.filter((row) => (
    members.has(String(row.setCode || "").trim().toUpperCase())
  ));
});
const showingOverview = computed(() => !styleFilter.value && !setScope.value);
const showingStyles = computed(() => Boolean(setScope.value) && !styleFilter.value);
const activeRows = computed(() => {
  if (styleFilter.value) {
    return cardsForArtStyle(storedCards.value, styleFilter.value);
  }
  if (setScope.value) {
    return visibleStyleRows.value;
  }
  return storedCards.value;
});

function columnsFor(rankedRows) {
  const columns = [
    { id: "up", title: "Risers", rows: rankedRows.risers, empty: "No risers this sync." },
    { id: "down", title: "Fallers", rows: rankedRows.fallers, empty: "No fallers this sync." },
  ];
  const filled = columns.filter((column) => column.rows.length);
  return filled.length === 1 ? filled : columns;
}

const pageSections = computed(() => {
  if (!showingOverview.value) {
    return [{
      id: "main",
      heading: "",
      tiles: Boolean(styleFilter.value),
      styles: showingStyles.value,
      columns: columnsFor(rankMoverRows(activeRows.value, {
        limit: 25,
      })),
    }];
  }
  const sections = [{
    id: "cards",
    heading: "Top cards",
    tiles: true,
    styles: false,
    columns: columnsFor(rankMoverRows(storedCards.value, {
      limit: 10,
    })),
  }];
  const styleRanked = rankMoverRows(styleRows.value, {
    limit: 25,
  });
  if (styleRanked.risers.length || styleRanked.fallers.length) {
    sections.push({
      id: "styles",
      heading: "Art styles",
      tiles: false,
      styles: true,
      columns: columnsFor(styleRanked),
    });
  }
  return sections;
});
const title = computed(() => {
  if (styleFilter.value) {
    return styleFilter.value.artStyle || styleFilter.value.label || "Art style";
  }
  if (setScope.value) {
    return setName(setScope.value);
  }
  return "Changes";
});
const titleSet = computed(() => (
  styleFilter.value || setScope.value
    ? setMeta(styleFilter.value || setScope.value)
    : null
));
const showBreadcrumb = computed(() => Boolean(setScope.value || styleFilter.value));
const intro = computed(() => {
  if (styleFilter.value) {
    return "Owned card changes from the last price update for this art style, ranked by euro change.";
  }
  if (showingStyles.value) {
    const family = scopeMemberCodes(setScope.value).size > 1;
    const scopeLabel = family ? "set family" : "set";
    return `Owned-card changes from the last price update for this ${scopeLabel}. Top 25 art styles, ranked by euro change.`;
  }
  return "Top 10 owned card risers and fallers, then art styles, from the last price update, ranked by euro change.";
});

function formatDelta(row) {
  return formatProfit((Number(row?.current) || 0) - (Number(row?.previous) || 0));
}

function formatPrice(value) {
  return formatEuro(value);
}

function rowLabel(row, section) {
  if (section?.styles) {
    return row.artStyle || row.label;
  }
  return row.label;
}

function rowMeta(row, section) {
  if (section?.styles || !row.collectorNumber) {
    return "";
  }
  return `#${row.collectorNumber}`;
}

function tileCard(row) {
  return moverRowToTileCard(row);
}

function tileRoute(row) {
  const card = tileCard(row);
  if (!card.setCode || !card.collectorNumber) {
    return null;
  }
  return {
    name: "card",
    params: { setCode: card.setCode, collectorNumber: card.collectorNumber },
    query: cardRouteQuery(cardFinish(card)),
  };
}

function openStyle(row) {
  const setCode = String(row?.setCode || "").trim();
  const artStyle = String(row?.artStyle || "").trim();
  if (!setCode || !artStyle) {
    return;
  }
  router.push(homeChangesRoute({ setCode, artStyle }));
}

function openSet(row) {
  const setCode = String(row?.setCode || "").trim();
  if (!setCode) {
    return;
  }
  router.push(homeChangesRoute({ setCode }));
}
</script>

<template>
  <section class="home-panel price-sync-movers-page">
    <div class="price-sync-movers-header">
      <h2 id="price-sync-movers-title">
        <img
          v-if="titleSet && setIcon(titleSet)"
          :src="setIcon(titleSet)"
          alt=""
          class="price-sync-movers-set-icon"
          :title="setName(titleSet)"
          :aria-label="setName(titleSet)"
          @error="onSetIconError($event, titleSet)"
        >
        <nav v-if="showBreadcrumb" class="price-sync-breadcrumb" aria-label="Price changes">
          <RouterLink :to="homeChangesRoute()">Changes</RouterLink>
          <template v-if="setScope">
            <span class="price-sync-breadcrumb-sep" aria-hidden="true">/</span>
            <RouterLink
              v-if="styleFilter"
              :to="homeChangesRoute({ setCode: setScope.setCode })"
            >
              {{ setName(setScope) }}
            </RouterLink>
            <span v-else aria-current="page">{{ setName(setScope) }}</span>
          </template>
          <template v-if="styleFilter">
            <span class="price-sync-breadcrumb-sep" aria-hidden="true">/</span>
            <span aria-current="page">{{ styleFilter.artStyle || styleFilter.label }}</span>
          </template>
        </nav>
        <span v-else>{{ title }}</span>
      </h2>
    </div>
    <p class="price-sync-movers-intro">{{ intro }}</p>
    <div v-if="showingOverview && setDayTiles.length" class="price-sync-favorite-day">
      <h3>Favourite sets</h3>
      <FavoriteDayChangeTiles
        :items="setDayTiles"
        @select="openSet"
      />
    </div>
    <div
      v-for="section in pageSections"
      :key="section.id"
      class="price-sync-movers-section"
    >
      <h3 v-if="section.heading" class="price-sync-section-heading">{{ section.heading }}</h3>
    <div
      class="price-sync-movers-columns"
      :class="{ 'is-single': section.columns.length === 1 }"
    >
      <section
        v-for="column in section.columns"
        :key="column.id"
        class="price-sync-movers-column"
      >
        <h3>{{ column.title }}</h3>
        <EdgeCarousel
          v-if="section.tiles && column.rows.length"
          :label="column.title.toLowerCase()"
        >
        <ol class="price-sync-movers-list is-tiles is-edge-carousel-track">
          <li v-for="row in column.rows" :key="row.id || row.label">
            <figure
              v-if="section.tiles"
              class="price-sync-mover-tile"
            >
              <div class="price-sync-mover-tile-image">
                <CardInteractiveImage
                  v-if="tileCard(row).imageUri"
                  :src="tileCard(row).imageUri"
                  :alt="tileCard(row).name"
                  :card="tileCard(row)"
                  img-class="price-sync-mover-tile-art"
                  :show-details="false"
                  :show-copy-controls="false"
                />
                <div v-else class="price-sync-mover-tile-placeholder">
                  {{ tileCard(row).name || rowLabel(row, section) }}
                </div>
                <CardFinishBadge
                  :card="tileCard(row)"
                  variant="overlay"
                  compact
                />
              </div>
              <figcaption class="price-sync-mover-tile-caption">
                <RouterLink
                  v-if="tileRoute(row)"
                  :to="tileRoute(row)"
                  class="price-sync-mover-tile-name"
                  :title="tileCard(row).name || rowLabel(row, section)"
                >
                  {{ tileCard(row).name || rowLabel(row, section) }}
                </RouterLink>
                <span
                  v-else
                  class="price-sync-mover-tile-name"
                  :title="tileCard(row).name || rowLabel(row, section)"
                >
                  {{ tileCard(row).name || rowLabel(row, section) }}
                </span>
                <strong
                  class="price-sync-movers-change"
                  :class="column.id === 'up' ? 'is-up' : 'is-down'"
                >
                  <span class="price-sync-movers-range">
                    {{ formatPrice(row.previous) }} → {{ formatPrice(row.current) }}
                  </span>
                  <span class="price-sync-movers-deltas">
                    <span class="is-primary">{{ formatDelta(row) }}</span>
                  </span>
                </strong>
              </figcaption>
            </figure>
          </li>
        </ol>
        </EdgeCarousel>
        <ol
          v-else-if="column.rows.length"
          class="price-sync-movers-list"
        >
          <li v-for="row in column.rows" :key="row.id || row.label">
            <component
              :is="section.styles ? 'button' : 'div'"
              class="price-sync-movers-item"
              :class="{ 'has-set-icon': section.styles }"
              v-bind="section.styles ? { type: 'button' } : {}"
              @click="section.styles ? openStyle(row) : undefined"
            >
              <img
                v-if="section.styles && setIcon(row)"
                :src="setIcon(row)"
                alt=""
                class="price-sync-movers-set-icon"
                :title="setName(row)"
                :aria-label="setName(row)"
                @error="onSetIconError($event, row)"
              >
              <span class="price-sync-movers-copy">
                <span class="price-sync-movers-name" :title="rowLabel(row, section)">{{ rowLabel(row, section) }}</span>
                <span v-if="rowMeta(row, section)" class="price-sync-movers-meta">{{ rowMeta(row, section) }}</span>
              </span>
              <strong
                class="price-sync-movers-change"
                :class="column.id === 'up' ? 'is-up' : 'is-down'"
              >
                <span class="price-sync-movers-range">
                  {{ formatPrice(row.previous) }} → {{ formatPrice(row.current) }}
                </span>
                <span class="price-sync-movers-deltas">
                  <span class="is-primary">{{ formatDelta(row) }}</span>
                </span>
              </strong>
            </component>
          </li>
        </ol>
        <p v-else class="price-sync-movers-empty">{{ column.empty }}</p>
      </section>
    </div>
    </div>
  </section>
</template>
