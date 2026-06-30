<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "../api";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import UnknownCardsTooltip from "../components/UnknownCardsTooltip.vue";
import SetPicker from "../components/SetPicker.vue";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { fetchPricingSettings } from "../composables/pricingSettings";
import { formatCompletion, formatEuro, formatProfit, formatRoi, formatSetDropdownLabel } from "../utils/format";
import { collectionScopeToQuery, setScopeFromRoute, setScopeToQuery } from "../utils/setScope";

const route = useRoute();
const router = useRouter();
const payload = ref(null);
const setCode = ref("All");
const { loading, run } = useAsyncLoad();

const stats = computed(() => payload.value?.stats || null);
const sets = computed(() => payload.value?.sets || []);

function setLabel(code) {
  const set = sets.value.find((item) => item.setCode === code);
  return set ? formatSetDropdownLabel(set) : code;
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
  if (stats.value.setBreakdown?.length) {
    return stats.value.setBreakdown;
  }
  return aggregateArtStylesBySet(stats.value.artStyles || []);
});

function selectSet(code) {
  if (!code || String(code).toLowerCase() === "all") {
    return;
  }
  setCode.value = code;
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

const collectionLink = computed(() => ({
  path: "/collection/top",
  query: collectionScopeToQuery(setCode.value),
}));

async function loadStats() {
  await run(async () => {
    payload.value = await api.getCollectionStats({
      setCode: setCode.value,
      foilFilter: "all",
    });
  });
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
    />

    <div class="reports-toolbar">
      <div class="reports-toolbar-filters">
        <SetPicker
          v-model="setCode"
          layout="dropdown"
          :sets="sets"
        />
        <RouterLink :to="collectionLink" class="btn btn-secondary btn-small">
          View collection
        </RouterLink>
        <LoadingIndicator v-if="loading" compact label="Updating stats…" />
      </div>
    </div>

    <div v-if="loading && !stats" class="storage-empty">
      <LoadingIndicator label="Loading stats…" />
    </div>

    <template v-else-if="stats">
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
          <strong>{{ formatProfit(stats.profit) }}</strong>
        </div>
        <div class="stats-card">
          <span>ROI</span>
          <strong>{{ formatRoi(stats.profit, stats.invested) }}</strong>
        </div>
        <div class="stats-card">
          <span>Owned</span>
          <strong>{{ formatCompletion(stats.ownedCount, stats.catalogCount) }}</strong>
        </div>
        <UnknownCardsTooltip :cards="stats.unknownCards">
          <span>Unknown value</span>
          <strong>{{ formatEuro(stats.unknownInvested) }}</strong>
        </UnknownCardsTooltip>
      </div>

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
            <tr v-for="row in setBreakdownRows" :key="row.setCode">
              <td>
                <button
                  type="button"
                  class="stats-set-drill"
                  @click="selectSet(row.setCode)"
                >
                  {{ setLabel(row.setCode) }}
                </button>
              </td>
              <td>{{ row.count }}</td>
              <td>{{ formatEuro(row.current) }}</td>
              <td>{{ formatEuro(row.invested) }}</td>
              <td>{{ formatProfit(row.profit) }}</td>
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
              <td>{{ formatProfit(row.profit) }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>
  </div>
</template>
