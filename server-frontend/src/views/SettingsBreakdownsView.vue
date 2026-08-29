<script setup>
import { computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { formatEuro } from "../utils/format";
import {
  loadSnapshots,
  snapshotList,
  snapshotOptionLabel,
  deleteSnapshot,
  applySnapshotSelection,
} from "../composables/storageBreakdownHistory";

const router = useRouter();
const hasSnapshots = computed(() => snapshotList.value.length > 0);

async function openSnapshot(snapshot) {
  await applySnapshotSelection(snapshot.id);
  router.push({
    path: "/storage",
    query: { view: "breakdown" },
  });
}

onMounted(() => {
  loadSnapshots();
});
</script>

<template>
  <div class="home-page">
    <section class="home-panel">
      <h2>Breakdown snapshots</h2>
      <p class="home-intro">
        Daily storage breakdowns are saved from Storage. There is one snapshot per UTC day;
        saving again that day replaces it. Delete days you no longer need.
      </p>

      <p v-if="!hasSnapshots" class="home-meta">No saved breakdowns yet.</p>

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
              View
            </button>
            <button
              type="button"
              class="btn btn-danger btn-small"
              @click="deleteSnapshot(snapshot)"
            >
              Delete
            </button>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>
