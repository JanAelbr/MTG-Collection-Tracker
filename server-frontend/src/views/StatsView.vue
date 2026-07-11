<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "../api";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import GalleryLoadingOverlay from "../components/GalleryLoadingOverlay.vue";
import SetPicker from "../components/SetPicker.vue";
import CollectionSetLink from "../components/CollectionSetLink.vue";
import FilterSidebar from "../components/FilterSidebar.vue";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { fetchPricingSettings } from "../composables/pricingSettings";
import { formatCompletion, formatEuro, formatProfit, formatRoi, setShortName } from "../utils/format";
import { finishLabel } from "../utils/finishes";
import { resolveSetIconUri } from "../utils/scryfall";
import { collectionScopeToQuery, setScopeFromRoute, setScopeToQuery } from "../utils/setScope";

const route = useRoute();
const router = useRouter();
const payload = ref(null);
const setCode = ref("All");
const { loading, run } = useAsyncLoad();

const stats = computed(() => payload.value?.stats || null);
const sets = computed(() => payload.value?.sets || []);

function setRowLabel(code) {
  const set = sets.value.find((item) => item.setCode === code);
  if (!set) {
    return code;
  }
  const name = setShortName(set);
  return set.favorite ? `★ ${name}` : name;
}

function setIconForCode(code) {
  const set = sets.value.find((item) => item.setCode === code);
  return resolveSetIconUri(set || { setCode: code });
}

function profitClass(value) {
  if (value == null || Number.isNaN(value)) {
    return "";
  }
  return value >= 0 ? "reports-gain" : "reports-loss";
}

function sumNullable(left, right) {
  if (left == null && right == null) {
    return null;
  }
  return (left ?? 0) + (right ?? 0);
}

function aggregateArtStylesBySet(artStyles) {
  const grouped = new Map();
  for (const row of artStyles) {
    const key = row.setCode;
    if (!key) {
      continue;
    }
    const prev = grouped.get(key) || {
      setCode: key,
      count: 0,
      current: null,
      invested: null,
      profit: null,
    };
    prev.count += row.count || 0;
    prev.current = sumNullable(prev.current, row.current);
    prev.invested = sumNullable(prev.invested, row.invested);
    prev.profit = sumNullable(prev.profit, row.profit);
    grouped.set(key, prev);
  }
  return [...grouped.values()].sort((a, b) => a.setCode.localeCompare(b.setCode));
}

const isAllSetsView = computed(() => String(setCode.value).toLowerCase() === "all");

const setBreakdownRows = computed(() => {
  if (!isAllSetsView.value || !stats.value) {
    return [];
  }
  const rows = stats.value.setBreakdown?.length
    ? stats.value.setBreakdown
    : aggregateArtStylesBySet(stats.value.artStyles || []);
  return [...rows].sort((a, b) => (b.current ?? 0) - (a.current ?? 0));
});

const maxSetValue = computed(() => {
  let max = 0;
  for (const row of setBreakdownRows.value) {
    const value = row.current;
    if (value != null && !Number.isNaN(value) && value > max) {
      max = value;
    }
  }
  return max;
});

function valueBarPercent(row) {
  const current = row.current;
  if (current == null || Number.isNaN(current) || maxSetValue.value <= 0) {
    return 0;
  }
  return Math.max(6, (current / maxSetValue.value) * 100);
}

const unknownCards = computed(() => stats.value?.unknownCards || []);
const hasUnknownCards = computed(() => (stats.value?.unknownCount ?? 0) > 0);

function unknownCardSetCode(card) {
  return card.setCode || card.set_code || "";
}

function unknownCardNumber(card) {
  return String(card.collectorNumber ?? card.collector_number ?? "");
}

function unknownCardFinish(card) {
  return card.finish ?? card.foil ?? 0;
}

function cardDetailLink(card) {
  return {
    name: "card",
    params: {
      setCode: unknownCardSetCode(card),
      collectorNumber: unknownCardNumber(card),
    },
  };
}

function selectSet(code) {
  if (!code || String(code).toLowerCase() === "all") {
    return;
  }
  setCode.value = code;
}

function clearSetFilter() {
  setCode.value = "All";
}

function collectionLinkForSet() {
  return {
    path: "/collection/all",
    query: collectionScopeToQuery(setCode.value),
  };
}

function onSetRowClick(code) {
  selectSet(code);
}

function syncSetRoute() {
  router.replace({
    path: route.path,
    query: setScopeToQuery(setCode.value),
  });
}

function syncSetFromRoute() {
  const fromRoute = setScopeFromRoute(route);
  if (fromRoute !== setCode.value) {
    setCode.value = fromRoute;
    return true;
  }
  return false;
}

function collectionLinkForArtStyle(row) {
  return {
    path: "/collection/all",
    query: collectionScopeToQuery(setCode.value, row.artStyle),
  };
}

async function loadStats() {
  await run(async () => {
    payload.value = await api.getCollectionStats({
      setCode: setCode.value,
      foilFilter: "all",
    });
  });
}

async function onSetsChanged(event) {
  if (event?.sets && payload.value) {
    payload.value = { ...payload.value, sets: event.sets };
  } else {
    await loadStats();
  }
  if (event?.catalogReloaded) {
    await loadStats();
  }
}

watch(setCode, () => {
  syncSetRoute();
  loadStats();
});

watch(
  () => route.query.set,
  () => {
    if (syncSetFromRoute()) {
      return;
    }
  },
);

onMounted(() => {
  fetchPricingSettings();
  if (!syncSetFromRoute()) {
    loadStats();
  }
});
</script>

<template>
  <div class="stats-page">
    <SetPicker
      v-model="setCode"
      layout="banner"
      :sets="sets"
      @sets-changed="onSetsChanged"
    />

    <div class="page-with-sidebar">
      <FilterSidebar>
        <div class="filter-sidebar-section">
          <p class="filter-sidebar-label">Set</p>
          <SetPicker
            v-model="setCode"
            layout="dropdown"
            :sets="sets"
          />
        </div>
      </FilterSidebar>

      <div class="page-with-sidebar-main">
    <p v-if="!isAllSetsView" class="stats-set-breadcrumb">
      <button type="button" class="stats-set-breadcrumb-back" @click="clearSetFilter">
        All sets
      </button>
      <span aria-hidden="true">›</span>
      <strong>{{ setRowLabel(setCode) }}</strong>
      <RouterLink :to="collectionLinkForSet()" class="stats-set-collection-link">
        View collection
      </RouterLink>
    </p>
    <div v-if="loading && !stats" class="storage-empty">
      <LoadingIndicator label="Loading stats…" />
    </div>

    <GalleryLoadingOverlay
      v-else-if="stats"
      class="stats-content-loading"
      :loading="loading"
      label="Updating stats…"
    >
      <div class="stats-hero-grid">
        <div class="stats-card">
          <span>Current value</span>
          <strong>{{ formatEuro(stats.current) }}</strong>
        </div>
        <div class="stats-card">
          <span>Invested</span>
          <strong>{{ formatEuro(stats.invested) }}</strong>
        </div>
        <div class="stats-card">
          <span>Profit / loss</span>
          <strong :class="profitClass(stats.profit)">{{ formatProfit(stats.profit) }}</strong>
        </div>
        <div class="stats-card">
          <span>ROI</span>
          <strong>{{ formatRoi(stats.profit, stats.invested) }}</strong>
        </div>
        <div class="stats-card">
          <span>Owned</span>
          <strong>{{ formatCompletion(stats.ownedCount, stats.catalogCount) }}</strong>
        </div>
        <div v-if="hasUnknownCards" class="stats-card stats-card-unknown">
          <span>Unknown value</span>
          <strong>{{ formatEuro(stats.unknownInvested) }}</strong>
          <span class="stats-card-subtext">
            {{ stats.unknownCount }} {{ stats.unknownCount === 1 ? "card" : "cards" }}
          </span>
        </div>
      </div>

      <section
        class="table-panel"
        :class="hasUnknownCards ? 'stats-unknown-panel' : 'stats-healthy-panel'"
        :aria-label="hasUnknownCards ? 'Unknown value' : 'Pricing status'"
      >
        <h2 v-if="hasUnknownCards">Unknown value</h2>
        <template v-if="hasUnknownCards">
          <p class="stats-unknown-intro">
            These owned cards have no current market price.
            Total invested: {{ formatEuro(stats.unknownInvested) }}.
          </p>
          <table class="reports-table">
          <thead>
            <tr>
              <th>Set</th>
              <th>#</th>
              <th>Name</th>
              <th>Art style</th>
              <th>Finish</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(card, index) in unknownCards"
              :key="`${unknownCardSetCode(card)}-${unknownCardNumber(card)}-${unknownCardFinish(card)}-${index}`"
            >
              <td>
                <div class="stats-set-drill">
                  <button
                    type="button"
                    class="stats-set-drill-icon"
                    :aria-label="`Filter stats to ${setRowLabel(unknownCardSetCode(card))}`"
                    @click="selectSet(unknownCardSetCode(card))"
                  >
                    <img
                      v-if="setIconForCode(unknownCardSetCode(card))"
                      :src="setIconForCode(unknownCardSetCode(card))"
                      alt=""
                      class="stats-set-icon"
                    >
                  </button>
                  <CollectionSetLink
                    :set-code="unknownCardSetCode(card)"
                    :label="setRowLabel(unknownCardSetCode(card))"
                  />
                </div>
              </td>
              <td>{{ unknownCardNumber(card) }}</td>
              <td>
                <RouterLink :to="cardDetailLink(card)" class="stats-art-drill">
                  {{ card.name || "Unknown" }}
                </RouterLink>
              </td>
              <td>{{ card.artStyle || card.art_style || "—" }}</td>
              <td>{{ finishLabel(unknownCardFinish(card)) }}</td>
            </tr>
          </tbody>
        </table>
        </template>
        <div v-else class="stats-healthy-state">
          <span class="stats-health-check" aria-hidden="true">✓</span>
          <p>
            Every owned card
            {{ isAllSetsView ? "in your collection" : "in this set" }}
            has a current market price.
          </p>
        </div>
      </section>

      <section v-if="isAllSetsView && setBreakdownRows.length" class="table-panel">
        <h2>By set</h2>
        <table class="reports-table">
          <thead>
            <tr>
              <th>Set</th>
              <th>Cards</th>
              <th>Value</th>
              <th>Invested</th>
              <th>Profit / loss</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in setBreakdownRows"
              :key="row.setCode"
              class="stats-set-row"
              @click="onSetRowClick(row.setCode)"
            >
              <td>
                <div class="stats-set-drill">
                  <button
                    type="button"
                    class="stats-set-drill-icon"
                    :aria-label="`Filter stats to ${setRowLabel(row.setCode)}`"
                    @click.stop="selectSet(row.setCode)"
                  >
                    <img
                      v-if="setIconForCode(row.setCode)"
                      :src="setIconForCode(row.setCode)"
                      alt=""
                      class="stats-set-icon"
                    >
                  </button>
                  <CollectionSetLink
                    :set-code="row.setCode"
                    :label="setRowLabel(row.setCode)"
                  />
                </div>
              </td>
              <td>{{ row.count }}</td>
              <td class="stats-value-cell">
                <div class="stats-value-bar-wrap">
                  <div
                    class="stats-value-bar"
                    :style="{ width: `${valueBarPercent(row)}%` }"
                    :title="`${((row.current ?? 0) / (stats.current || 1) * 100).toFixed(1)}% of portfolio`"
                  />
                  <span class="stats-value-label">{{ formatEuro(row.current) }}</span>
                </div>
              </td>
              <td>{{ formatEuro(row.invested) }}</td>
              <td :class="profitClass(row.profit)">{{ formatProfit(row.profit) }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section v-if="!isAllSetsView && stats.artStyles?.length" class="table-panel">
        <h2>By art style</h2>
        <table class="reports-table">
          <thead>
            <tr>
              <th>Art style</th>
              <th>Cards</th>
              <th>Value</th>
              <th>Invested</th>
              <th>Profit / loss</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in stats.artStyles" :key="`${row.setCode}-${row.artStyle}`">
              <td>
                <RouterLink
                  :to="collectionLinkForArtStyle(row)"
                  class="stats-art-drill"
                >
                  {{ row.artStyle }}
                </RouterLink>
              </td>
              <td>{{ row.count }}</td>
              <td>{{ formatEuro(row.current) }}</td>
              <td>{{ formatEuro(row.invested) }}</td>
              <td :class="profitClass(row.profit)">{{ formatProfit(row.profit) }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </GalleryLoadingOverlay>
      </div>
    </div>
  </div>
</template>
