<script setup>
import { computed, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { api, ignoreAborted } from "../api";
import FavoriteDayChangeTiles from "./FavoriteDayChangeTiles.vue";
import PriceSyncMiniCardList from "./PriceSyncMiniCardList.vue";
import { formatEuro, formatProfit, setShortName } from "../utils/format";
import {
  cardsForArtStyle,
  changeMoveCounts,
  deckImpactRows,
  deckImpactTotals,
  deckUnchangedCount,
  compareCardsByCollectorNumber,
  collectPriceSyncCards,
  collectPriceSyncStyleRows,
  HOME_PRICE_TINT_FLOOR,
  priceChangeStyle,
  priceChangeTinted,
  rankMoverRows,
} from "../utils/priceSyncMovers";
import { applySetGalleryIconFallback, resolveSetIconUri } from "../utils/scryfall";
import { homeChangesRoute, homeRouteQueryValue } from "../utils/homeRoutes";

const props = defineProps({
  cards: { type: Array, default: () => [] },
  movers: { type: Object, default: () => ({}) },
  setDayTiles: { type: Array, default: () => [] },
  sourceCards: { type: Array, default: () => [] },
  variant: { type: String, default: "full" },
  side: { type: String, default: "" },
  fixedSetCode: { type: String, default: "" },
  embedded: { type: Boolean, default: false },
  decks: { type: Array, default: () => [] },
  deckPages: { type: Object, default: () => ({}) },
  artStyles: { type: Array, default: () => [] },
});

const route = useRoute();
const router = useRouter();
const setsByCode = ref(new Map());
const openStyleKeys = ref(new Set());

const routeSetCode = computed(() => {
  const fixed = String(props.fixedSetCode || "").trim().toUpperCase();
  if (fixed) {
    return fixed;
  }
  return homeRouteQueryValue(route.query.set).toUpperCase();
});
const routeArtStyle = computed(() => {
  if (String(props.fixedSetCode || "").trim()) {
    return "";
  }
  return homeRouteQueryValue(route.query.art);
});
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

const styleOwnedCount = ref(null);

watch(
  [styleFilter, () => props.artStyles],
  () => {
    const filter = styleFilter.value;
    styleOwnedCount.value = null;
    if (!filter) {
      return;
    }
    const owned = favouriteStyleOwnedCount(filter);
    if (owned != null) {
      styleOwnedCount.value = owned;
      return;
    }
    const { setCode, artStyle } = filter;
    ignoreAborted(api.getManagerArtStyles(setCode)).then((payload) => {
      if (
        !styleFilter.value
        || styleFilter.value.setCode !== setCode
        || styleFilter.value.artStyle !== artStyle
      ) {
        return;
      }
      const match = (payload?.artStyles || []).find((style) => (
        String(style?.artStyle || "").trim() === artStyle
      ));
      styleOwnedCount.value = match ? Number(match.ownedCount) || 0 : null;
    });
  },
  { immediate: true },
);

function favouriteStyleOwnedCount(filter) {
  const match = (props.artStyles || []).find((style) => (
    String(style?.setCode || "").trim().toUpperCase() === filter.setCode
    && String(style?.artStyle || "").trim() === filter.artStyle
  ));
  if (!Array.isArray(match?.cards)) {
    return null;
  }
  const owned = new Set();
  for (const card of match.cards) {
    const setCode = String(card?.setCode || "").trim().toUpperCase();
    const number = String(card?.collectorNumber || "").trim();
    if (setCode && number) {
      owned.add(`${setCode}|${number}`);
    }
  }
  return owned.size;
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
const routeDeckId = computed(() => homeRouteQueryValue(route.query.deck));
const deckScope = computed(() => {
  const deckId = routeDeckId.value;
  if (!deckId) {
    return null;
  }
  const deck = (props.decks || []).find((item) => String(item?.id) === deckId) || null;
  const page = props.deckPages?.[deckId] || {};
  return {
    id: deckId,
    name: String(deck?.name || deck?.label || "Deck"),
    prints: page.ownedPrints || [],
  };
});
const showingOverview = computed(() => !styleFilter.value && !setScope.value && !deckScope.value);
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

function columnsFor(rankedRows, { keepEmpty = false } = {}) {
  const columns = [
    { id: "up", title: "Risers", rows: rankedRows.risers, empty: "No risers this sync." },
    { id: "down", title: "Fallers", rows: rankedRows.fallers, empty: "No fallers this sync." },
  ];
  if (keepEmpty) {
    return columns;
  }
  const filled = columns.filter((column) => column.rows.length);
  return filled.length === 1 ? filled : columns;
}

function stylesByTotalChange(rows) {
  return [...(rows || [])].sort((left, right) => {
    const byChange = (Number(right.delta) || 0) - (Number(left.delta) || 0);
    if (byChange) {
      return byChange;
    }
    return String(left.artStyle || left.label || "").localeCompare(
      String(right.artStyle || right.label || ""),
      undefined,
      { numeric: true, sensitivity: "base" },
    );
  });
}

function rowTintClass(row, column) {
  if (!priceChangeTinted(row?.delta, backgroundFloor.value)) {
    return "";
  }
  return rowChangeClass(row, column);
}

function rowChangeClass(row, column) {
  if (column.id === "up") {
    return "is-up";
  }
  if (column.id === "down") {
    return "is-down";
  }
  return Number(row?.delta) < 0 ? "is-down" : "is-up";
}

const isDetailPage = computed(() => props.variant !== "cards" && !props.embedded);
const backgroundFloor = computed(() => (isDetailPage.value ? 0 : HOME_PRICE_TINT_FLOOR));
const deckImpact = computed(() => (
  deckScope.value
    ? deckImpactRows(storedCards.value, deckScope.value.prints)
    : []
));
const deckTotals = computed(() => deckImpactTotals(deckImpact.value));
const scopeCards = computed(() => {
  if (deckScope.value) {
    return deckImpact.value;
  }
  if (styleFilter.value) {
    return cardsForArtStyle(storedCards.value, styleFilter.value);
  }
  if (setScope.value) {
    const members = scopeMemberCodes(setScope.value);
    return storedCards.value.filter((card) => (
      members.has(String(card?.setCode || "").trim().toUpperCase())
    ));
  }
  return [];
});
const changeTotals = computed(() => {
  if (props.embedded || props.variant === "cards") {
    return null;
  }
  let euros = null;
  if (deckScope.value) {
    euros = deckTotals.value;
  } else if (styleFilter.value) {
    euros = deckImpactTotals(activeRows.value);
  } else if (showingStyles.value) {
    euros = deckImpactTotals(visibleStyleRows.value);
  }
  if (!euros) {
    return null;
  }
  const counts = changeMoveCounts(scopeCards.value);
  return {
    ...euros,
    upCount: counts.upCount,
    downCount: counts.downCount,
    unchangedCount: unchangedCount(counts.movedSlots),
  };
});

function unchangedCount(movedSlots) {
  if (deckScope.value) {
    return deckUnchangedCount(deckScope.value.prints, scopeCards.value);
  }
  if (styleFilter.value) {
    if (styleOwnedCount.value == null) {
      return null;
    }
    return Math.max(0, styleOwnedCount.value - movedSlots.size);
  }
  if (setScope.value) {
    let owned = 0;
    let known = false;
    for (const code of scopeMemberCodes(setScope.value)) {
      const meta = setsByCode.value.get(code);
      if (meta?.ownedCount == null) {
        continue;
      }
      known = true;
      owned += Number(meta.ownedCount) || 0;
    }
    if (!known) {
      return null;
    }
    return Math.max(0, owned - movedSlots.size);
  }
  return null;
}

function cardCountLabel(count) {
  const amount = Number(count) || 0;
  return `${amount} ${amount === 1 ? "card" : "cards"}`;
}

function columnBarWidth(row, rows) {
  const peak = Math.max(0, ...(rows || []).map((item) => Math.abs(Number(item?.delta) || 0)));
  if (!peak) {
    return "0%";
  }
  const share = Math.abs(Number(row?.delta) || 0) / peak;
  return `${Math.max(share > 0 ? 8 : 0, share * 100)}%`;
}

const pageSections = computed(() => {
  if (deckScope.value) {
    return [{
      id: "main",
      heading: "",
      tiles: true,
      styles: false,
      columns: columnsFor(rankMoverRows(deckImpact.value, {
        limit: 25,
        minChange: 1,
      })),
    }];
  }
  if (!showingOverview.value) {
    if (props.embedded && showingStyles.value) {
      return [{
        id: "main",
        heading: "",
        tiles: false,
        styles: true,
        columns: [{
          id: "all",
          title: "",
          rows: stylesByTotalChange(visibleStyleRows.value),
          empty: "No art style changes this sync.",
        }],
      }];
    }
    return [{
      id: "main",
      heading: "",
      tiles: Boolean(styleFilter.value),
      styles: showingStyles.value,
      columns: columnsFor(rankMoverRows(activeRows.value, {
        limit: 25,
        minChange: styleFilter.value ? 1 : 0,
      })),
    }];
  }
  const sections = [{
    id: "cards",
    heading: "Top cards",
    tiles: true,
    styles: false,
    columns: columnsFor(rankMoverRows(storedCards.value, {
      limit: 25,
      minChange: 1,
    }), { keepEmpty: true }),
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
const visibleSections = computed(() => {
  let sections = props.variant === "cards"
    ? pageSections.value.filter((section) => section.tiles)
    : pageSections.value;
  if (props.variant !== "cards") {
    return sections;
  }
  return sections.map((section) => {
    let columns = section.columns;
    if (props.side) {
      columns = columns.filter((column) => column.id === props.side);
    } else {
      const filled = columns.filter((column) => column.rows.length);
      columns = filled.length === 1 ? filled : columns;
    }
    return { ...section, columns };
  });
});
const title = computed(() => {
  if (deckScope.value) {
    return deckScope.value.name;
  }
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
const showBreadcrumb = computed(() => Boolean(setScope.value || styleFilter.value || deckScope.value));
const intro = computed(() => {
  if (deckScope.value) {
    return "";
  }
  if (styleFilter.value) {
    return "Owned card changes from the last price update for this art style, ranked by euro change.";
  }
  if (showingStyles.value) {
    const family = scopeMemberCodes(setScope.value).size > 1;
    const scopeLabel = family ? "set family" : "set";
    return `Owned-card changes from the last price update for this ${scopeLabel}. Top 25 art styles, ranked by euro change. Open an art style to see its cards.`;
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

function styleKey(row) {
  return row?.id || `${row?.setCode}|${row?.artStyle}`;
}

function isStyleOpen(row) {
  return openStyleKeys.value.has(styleKey(row));
}

function toggleStyle(row) {
  const key = styleKey(row);
  const next = new Set(openStyleKeys.value);
  if (next.has(key)) {
    next.delete(key);
  } else {
    next.add(key);
  }
  openStyleKeys.value = next;
}

function styleCards(row) {
  return [...cardsForArtStyle(storedCards.value, row)].sort(compareCardsByCollectorNumber);
}

function onStyleClick(row) {
  if (showingStyles.value) {
    toggleStyle(row);
    return;
  }
  openStyle(row);
}

watch(routeSetCode, () => {
  openStyleKeys.value = new Set();
});

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
  <section
    class="price-sync-movers-page"
    :class="{
      'home-panel': variant !== 'cards' && !embedded,
      'is-embedded': variant === 'cards' || embedded,
      'is-detail': isDetailPage,
      'is-deck': Boolean(deckScope),
    }"
  >
    <div v-if="variant !== 'cards' && !embedded" class="price-sync-movers-header">
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
          <RouterLink :to="homeChangesRoute()">Home</RouterLink>
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
          <template v-if="deckScope">
            <span class="price-sync-breadcrumb-sep" aria-hidden="true">/</span>
            <span aria-current="page">{{ deckScope.name }}</span>
          </template>
          <template v-if="styleFilter">
            <span class="price-sync-breadcrumb-sep" aria-hidden="true">/</span>
            <span aria-current="page">{{ styleFilter.artStyle || styleFilter.label }}</span>
          </template>
        </nav>
        <span v-else>{{ title }}</span>
      </h2>
    </div>
    <p v-if="intro && variant !== 'cards' && !embedded" class="price-sync-movers-intro">{{ intro }}</p>
    <div
      v-if="changeTotals"
      class="price-sync-deck-summary"
      aria-label="Price change"
    >
      <span class="is-up">
        <small>Rose</small>
        {{ formatProfit(changeTotals.up) }}
        <em>{{ cardCountLabel(changeTotals.upCount) }}</em>
      </span>
      <span class="is-down">
        <small>Fell</small>
        {{ formatProfit(changeTotals.down) }}
        <em>{{ cardCountLabel(changeTotals.downCount) }}</em>
      </span>
      <span v-if="changeTotals.unchangedCount != null" class="is-flat">
        <small>Unchanged</small>
        {{ changeTotals.unchangedCount }}
        <em>{{ changeTotals.unchangedCount === 1 ? "card" : "cards" }}</em>
      </span>
      <strong :class="changeTotals.delta < 0 ? 'is-down' : 'is-up'">
        <small>Net</small>
        {{ formatProfit(changeTotals.delta) }}
      </strong>
    </div>
    <div v-if="variant !== 'cards' && showingOverview && setDayTiles.length" class="price-sync-favorite-day">
      <h3>Favourite sets</h3>
      <FavoriteDayChangeTiles
        :items="setDayTiles"
        @select="openSet"
      />
    </div>
    <div
      v-for="section in visibleSections"
      :key="section.id"
      class="price-sync-movers-section"
    >
      <h3 v-if="section.heading && variant !== 'cards'" class="price-sync-section-heading">{{ section.heading }}</h3>
    <div
      class="price-sync-movers-columns"
      :class="{ 'is-single': section.columns.length === 1 }"
    >
      <section
        v-for="column in section.columns"
        :key="column.id"
        class="price-sync-movers-column"
        :class="isDetailPage ? `is-${column.id}` : ''"
      >
        <h3 v-if="!side && column.title">{{ column.title }}</h3>
        <PriceSyncMiniCardList
          v-if="section.tiles && column.rows.length"
          :rows="column.rows"
          :source-cards="sourceCards"
          :direction="column.id"
          :variant="isDetailPage ? 'detail' : ''"
          :background-floor="backgroundFloor"
        />
        <ol
          v-else-if="column.rows.length"
          class="price-sync-movers-list"
        >
          <li v-for="row in column.rows" :key="row.id || row.label">
            <component
              :is="section.styles ? 'button' : 'div'"
              class="price-sync-movers-item"
              :class="{
                'has-set-icon': section.styles,
                'has-style-toggle': showingStyles && section.styles,
                'is-open': section.styles && isStyleOpen(row),
                'is-up': rowTintClass(row, column) === 'is-up',
                'is-down': rowTintClass(row, column) === 'is-down',
              }"
              :style="priceChangeStyle(row.delta, { floor: backgroundFloor })"
              v-bind="section.styles ? { type: 'button', 'aria-expanded': showingStyles ? String(isStyleOpen(row)) : undefined } : {}"
              @click="section.styles ? onStyleClick(row) : undefined"
            >
              <span
                v-if="showingStyles && section.styles"
                class="price-sync-style-chevron"
                aria-hidden="true"
              >{{ isStyleOpen(row) ? "▾" : "▸" }}</span>
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
                <span v-if="isDetailPage" class="price-sync-deck-prices">
                  <span class="was">{{ formatPrice(row.previous) }}</span>
                  <span class="arrow" aria-hidden="true">→</span>
                  <span class="now">{{ formatPrice(row.current) }}</span>
                </span>
                <span v-if="isDetailPage" class="price-sync-deck-bar" aria-hidden="true">
                  <span :style="{ width: columnBarWidth(row, column.rows) }"></span>
                </span>
              </span>
              <strong
                v-if="isDetailPage"
                class="price-sync-deck-pill"
                :class="rowChangeClass(row, column)"
              >{{ formatDelta(row) }}</strong>
              <strong
                v-else
                class="price-sync-movers-change"
                :class="rowChangeClass(row, column)"
              >
                <span class="price-sync-movers-range">
                  {{ formatPrice(row.previous) }} → {{ formatPrice(row.current) }}
                </span>
                <span class="price-sync-movers-deltas">
                  <span class="is-primary">{{ formatDelta(row) }}</span>
                </span>
              </strong>
            </component>
            <div
              v-if="showingStyles && section.styles && isStyleOpen(row)"
              class="price-sync-style-cards"
            >
              <PriceSyncMiniCardList
                v-if="styleCards(row).length"
                :rows="styleCards(row)"
                :source-cards="sourceCards"
                :variant="isDetailPage ? 'detail' : ''"
                :background-floor="backgroundFloor"
              />
              <p v-else class="price-sync-movers-empty">No card changes in this art style.</p>
            </div>
          </li>
        </ol>
        <p v-else class="price-sync-movers-empty">{{ column.empty }}</p>
      </section>
    </div>
    </div>
  </section>
</template>
