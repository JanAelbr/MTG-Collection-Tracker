<script setup>
import "../styles/stats.css";
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api, isApiAbortError } from "../api";
import CollectionStatsPanel from "../components/CollectionStatsPanel.vue";
import ConfigurableBreakdownCharts from "../components/ConfigurableBreakdownCharts.vue";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { fetchPricingSettings } from "../composables/pricingSettings";
import { formatEuro } from "../utils/format";
import {
  loadSnapshots,
  snapshotList,
  snapshotOptionLabel,
  deleteSnapshot,
  applySnapshotSelection,
  saveDailySnapshot,
  pruneSnapshots,
  pruningSnapshots,
  savingSnapshot,
  snapshotError,
} from "../composables/storageBreakdownHistory";

const router = useRouter();
const payload = ref(null);
const history = ref({ points: [], hasArtStyles: false });
const { loading, run } = useAsyncLoad();

const hasSnapshots = computed(() => snapshotList.value.length > 0);
const utcTodayDate = computed(() => new Date().toISOString().slice(0, 10));
const todaySnapshot = computed(() => (
  snapshotList.value.find((item) => item.snapshotDate === utcTodayDate.value) || null
));
const updateSnapshotLabel = computed(() => {
  if (savingSnapshot.value) {
    return "Updating snapshot…";
  }
  return todaySnapshot.value ? "Update today’s snapshot" : "Save today’s snapshot";
});

async function loadStats() {
  try {
    await run(async () => {
      payload.value = await api.getCollectionStats({
        setCode: "All",
        family: false,
        foilFilter: "all",
      });
    });
  } catch (error) {
    payload.value = null;
    snapshotError.value = error.message || "Could not load collection stats.";
  }
}

async function loadHistory() {
  try {
    history.value = await api.listStorageBreakdownHistory();
  } catch (error) {
    if (isApiAbortError(error)) {
      return;
    }
    history.value = { points: [], hasArtStyles: false };
  }
}

async function refreshSnapshotData() {
  await Promise.all([loadSnapshots(), loadHistory()]);
}

async function updateTodaySnapshot() {
  const saved = await saveDailySnapshot();
  if (saved) {
    await loadHistory();
    await loadStats();
  }
}

async function openSnapshot(snapshot) {
  await applySnapshotSelection(snapshot.id);
  router.push({
    path: "/storage",
    query: { view: "breakdown" },
  });
}

async function pruneHistory() {
  const result = await pruneSnapshots();
  if (result) {
    await loadHistory();
  }
}

async function removeSnapshot(snapshot) {
  if (await deleteSnapshot(snapshot)) {
    await loadHistory();
  }
}

function openSetStats(setCode) {
  if (!setCode || String(setCode).toLowerCase() === "all") {
    return;
  }
  router.push({
    path: "/collection/all",
    query: { set: String(setCode), view: "stats" },
  });
}

onMounted(() => {
  fetchPricingSettings();
  loadStats();
  refreshSnapshotData();
});
</script>

<template>
  <div class="home-page settings-stats-page">
    <section class="home-panel">
      <h2>Collection stats</h2>
      <p class="home-intro">
        Portfolio totals across every owned print. Open a set for per-set stats in the catalog.
        Daily snapshots (after the first price sync of the day) power the graphs below.
      </p>
      <CollectionStatsPanel
        :stats="payload?.stats || null"
        :sets="payload?.sets || []"
        set-code="All"
        :loading="loading"
        @select-set="openSetStats"
      />
    </section>

    <section class="home-panel">
      <div class="settings-stats-history-head">
        <div>
          <h2>History</h2>
          <p class="home-intro">
            One snapshot per UTC day. Graphs cover the whole collection, every set, art styles,
            and storage locations.
          </p>
        </div>
        <div class="settings-stats-history-actions">
          <button
            type="button"
            class="btn btn-secondary"
            :disabled="pruningSnapshots || snapshotList.length < 2"
            @click="pruneHistory"
          >
            {{ pruningSnapshots ? "Pruning…" : "Prune history" }}
          </button>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="savingSnapshot"
            @click="updateTodaySnapshot"
          >
            {{ updateSnapshotLabel }}
          </button>
        </div>
      </div>
      <p v-if="snapshotError" class="home-sync-message error">{{ snapshotError }}</p>

      <ConfigurableBreakdownCharts :history="history" />

      <p v-if="!hasSnapshots" class="home-meta">No saved snapshots yet.</p>

      <ul v-else class="settings-breakdown-list">
        <li
          v-for="snapshot in snapshotList"
          :key="snapshot.id"
          class="settings-breakdown-row"
        >
          <div class="settings-breakdown-copy">
            <strong>{{ snapshot.snapshotDate }}</strong>
            <span>{{ formatEuro(snapshot.totals?.current) }}</span>
            <span v-if="snapshot.note" class="settings-breakdown-note">{{ snapshot.note }}</span>
          </div>
          <div class="settings-breakdown-actions">
            <button
              type="button"
              class="btn btn-secondary btn-small"
              :title="snapshotOptionLabel(snapshot)"
              @click="openSnapshot(snapshot)"
            >
              View storage
            </button>
            <button
              type="button"
              class="btn btn-danger btn-small"
              @click="removeSnapshot(snapshot)"
            >
              Delete
            </button>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>
