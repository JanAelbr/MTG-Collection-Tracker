<script setup>
import "../styles/stats.css";
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "../api";
import CollectionStatsPanel from "../components/CollectionStatsPanel.vue";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { fetchPricingSettings } from "../composables/pricingSettings";

const router = useRouter();
const payload = ref(null);
const { loading, run } = useAsyncLoad();

async function loadStats() {
  await run(async () => {
    payload.value = await api.getCollectionStats({
      setCode: "All",
      family: false,
      foilFilter: "all",
    });
  });
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
});
</script>

<template>
  <div class="home-page settings-stats-page">
    <section class="home-panel">
      <h2>Collection stats</h2>
      <p class="home-intro">
        Portfolio totals across every tracked set. Open a set to see per-set stats in the catalog.
      </p>
      <CollectionStatsPanel
        :stats="payload?.stats || null"
        :sets="payload?.sets || []"
        set-code="All"
        :loading="loading"
        @select-set="openSetStats"
      />
    </section>
  </div>
</template>
