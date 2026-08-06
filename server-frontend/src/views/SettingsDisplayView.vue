<script setup>
import { onMounted, ref } from "vue";
import { fetchPricingSettings, savePricingSettings, usePricingSettings } from "../composables/pricingSettings";
import { useSetGalleryFilter } from "../composables/setGalleryFilter";

const { settings: pricingSettings } = usePricingSettings();
const { showSetBrowserSubsets } = useSetGalleryFilter();
const settingsMessage = ref("");

async function loadPricingSettings() {
  await fetchPricingSettings(true);
}

async function updatePageSize(event) {
  settingsMessage.value = "";
  try {
    await savePricingSettings({ pageSize: Number(event.target.value) });
    settingsMessage.value = "Display settings saved.";
  } catch (error) {
    settingsMessage.value = error.message || "Could not save display settings.";
  }
}

function setSortModeLabel(mode) {
  if (mode === "owned") {
    return "Most owned";
  }
  if (mode === "chronological") {
    return "Chronological (new to old)";
  }
  return "Alphabetical";
}

async function updateSetSortMode(event) {
  settingsMessage.value = "";
  try {
    await savePricingSettings({ setSortMode: event.target.value });
    settingsMessage.value = "Display settings saved.";
  } catch (error) {
    settingsMessage.value = error.message || "Could not save display settings.";
  }
}

onMounted(() => {
  loadPricingSettings();
});
</script>

<template>
  <div class="home-page">
    <section v-if="pricingSettings" class="home-panel">
      <h2>Display</h2>
      <p class="home-intro">
        Gallery prices show the lowest listing first, then Cardmarket trend when it
        is higher. Rows per page applies to Collection gallery and table lists.
        Price change columns compare against the previous price snapshot
        automatically.
      </p>
      <div class="home-pricing-panel">
        <label class="manager-filter">
          <span>Rows per page</span>
          <select :value="pricingSettings.pageSize" @change="updatePageSize">
            <option
              v-for="size in pricingSettings.pageSizeOptions"
              :key="size"
              :value="size"
            >
              {{ size }}
            </option>
          </select>
        </label>
        <label class="manager-filter">
          <span>Set browser order</span>
          <select
            :value="pricingSettings.setSortMode ?? 'alphabetical'"
            @change="updateSetSortMode"
          >
            <option
              v-for="mode in (pricingSettings.setSortModeOptions ?? ['alphabetical', 'owned', 'chronological'])"
              :key="mode"
              :value="mode"
            >
              {{ setSortModeLabel(mode) }}
            </option>
          </select>
        </label>
        <label
          class="manager-filter home-subset-toggle"
          title="Show token, art card, promo, and minigame family subsets in the set browser"
        >
          <span>Set browser subsets</span>
          <span class="home-subset-toggle-control">
            <input v-model="showSetBrowserSubsets" type="checkbox" />
            <span>Show tokens &amp; promos</span>
          </span>
        </label>
      </div>
      <p v-if="settingsMessage" class="home-sync-message">{{ settingsMessage }}</p>
    </section>
  </div>
</template>
