<script setup>

import { computed, onMounted, reactive, ref, watch } from "vue";

import { useRoute } from "vue-router";

import { api } from "../api";

import CardPreview from "../components/CardPreview.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import { fetchPricingSettings, savePricingSettings, usePricingSettings } from "../composables/pricingSettings";
import { useAsyncLoad } from "../composables/useAsyncLoad";

import { formatEuro } from "../utils/format";
import { cardDisplayName, cardFinish, cardRouteQuery, finishLabel } from "../utils/finishes";



const route = useRoute();

const { settings: pricingSettings, fetchPricingSettings: loadPricingSettings } = usePricingSettings();

const locations = ref([]);

const selectedSlug = ref("");

const cardsPayload = ref(null);

const settingsMessage = ref("");

const { loading: loadingCards, run: runCardsLoad } = useAsyncLoad();

const storagePickerLocations = computed(() =>
  locations.value.filter((location) => location.locationType === "storage"),
);



const editor = reactive({

  open: false,

  mode: "create",

  slug: "",

  label: "",

  description: "",

});



const selectedLocation = computed(() =>

  locations.value.find((item) => item.slug === selectedSlug.value),

);



const visibleLocations = computed(() =>

  locations.value.filter(

    (location) => location.cardCount > 0 || location.isCustom || location.isSystem,

  ),

);



function lineTotal(card) {

  if (card.currentValue == null || Number.isNaN(card.currentValue)) {

    return null;

  }

  return card.currentValue * card.copyCount;

}



function cardRoute(card) {

  return {

    name: "card",

    params: { setCode: card.setCode, collectorNumber: card.collectorNumber },

    query: cardRouteQuery(cardFinish(card)),

  };

}



function setReportRoute(setCode) {
  return {
    path: "/collection/top",
    query: { set: setCode },
  };
}



async function loadLocations(preferredSlug = "") {

  const payload = await api.listStorageLocations();

  locations.value = payload.locations || [];

  const nextSlug =

    preferredSlug ||

    selectedSlug.value ||

    payload.defaultLocation ||

    locations.value[0]?.slug ||

    "";

  selectedSlug.value = nextSlug;

}



async function updateDefaultStorageLocation(event) {
  settingsMessage.value = "";
  try {
    await savePricingSettings({ defaultStorageLocation: event.target.value });
    settingsMessage.value = "Default storage saved.";
  } catch (error) {
    settingsMessage.value = error.message || "Could not save default storage.";
  }
}



async function loadCards() {
  if (!selectedSlug.value) {
    cardsPayload.value = null;
    return;
  }
  await runCardsLoad(async () => {
    cardsPayload.value = await api.getStorageLocationCards(selectedSlug.value);
  });
}



function openCreateEditor() {

  editor.open = true;

  editor.mode = "create";

  editor.slug = "";

  editor.label = "";

  editor.description = "";

}



function openEditEditor(location) {

  editor.open = true;

  editor.mode = "edit";

  editor.slug = location.slug;

  editor.label = location.label;

  editor.description = location.description || "";

}



function closeEditor() {

  editor.open = false;

}



async function saveEditor() {

  const label = editor.label.trim();

  if (!label) {

    return;

  }

  if (editor.mode === "create") {

    const created = await api.createStorageLocation({

      label,

      description: editor.description.trim(),

    });

    closeEditor();

    await loadLocations(created.slug);

    return;

  }

  await api.updateStorageLocation(editor.slug, {

    label,

    description: editor.description.trim(),

  });

  closeEditor();

  await loadLocations(editor.slug);

}



async function deleteLocation(location) {

  if (!location.canDelete) {

    return;

  }

  if (!window.confirm(`Delete empty storage "${location.label}"?`)) {

    return;

  }

  await api.deleteStorageLocation(location.slug);

  await loadLocations();

}



async function removeOneCopy(card) {

  const instanceId = card.instanceIds?.[card.instanceIds.length - 1];

  if (!instanceId) {

    return;

  }

  if (!window.confirm(`Remove one copy of ${cardDisplayName(card)}?`)) {

    return;

  }

  await api.deleteInstance(instanceId);

  await loadLocations(selectedSlug.value);

}



watch(selectedSlug, () => {

  loadCards();

});



onMounted(async () => {
  const preferredLocation =
    typeof route.query.location === "string" ? route.query.location : "";
  await Promise.all([loadLocations(preferredLocation), loadPricingSettings(true)]);
});

</script>



<template>

  <div class="storage-page">

    <div class="storage-toolbar">
      <label v-if="storagePickerLocations.length" class="storage-default-setting">
        <span>Default storage</span>
        <select
          :value="pricingSettings?.defaultStorageLocation ?? 'storage:general'"
          @change="updateDefaultStorageLocation"
        >
          <option
            v-for="location in storagePickerLocations"
            :key="location.slug"
            :value="location.slug"
          >
            {{ location.label }}
          </option>
        </select>
      </label>
      <button type="button" class="btn btn-primary" @click="openCreateEditor">
        New storage
      </button>
    </div>

    <p v-if="settingsMessage" class="storage-settings-message">{{ settingsMessage }}</p>



    <div class="storage-layout">

      <nav class="storage-location-nav" aria-label="Storage locations">

        <button

          v-for="location in visibleLocations"

          :key="location.slug"

          type="button"

          class="storage-location-link"

          :class="{ active: location.slug === selectedSlug }"

          @click="selectedSlug = location.slug"

        >

          <span>{{ location.label }}</span>

          <span class="storage-location-count">{{ location.cardCount }}</span>

        </button>

      </nav>



      <div class="storage-detail">

        <div v-if="selectedLocation" class="storage-detail-header">

          <div class="storage-detail-title-row">

            <h2>{{ selectedLocation.label }}</h2>

            <div class="storage-detail-actions">

              <button

                type="button"

                class="btn btn-secondary"

                @click="openEditEditor(selectedLocation)"

              >

                Edit

              </button>

              <button

                v-if="selectedLocation.canDelete"

                type="button"

                class="btn btn-danger"

                @click="deleteLocation(selectedLocation)"

              >

                Delete

              </button>

            </div>

          </div>

          <p v-if="selectedLocation.description" class="storage-location-description">

            {{ selectedLocation.description }}

          </p>

          <p class="storage-location-stats">

            {{ cardsPayload?.totalCopies ?? selectedLocation.cardCount }} copies ·

            {{ cardsPayload?.uniquePrints ?? selectedLocation.uniquePrints }} unique prints

          </p>

        </div>



        <div v-if="loadingCards" class="storage-empty">
          <LoadingIndicator label="Loading cards…" />
        </div>

        <div

          v-else-if="!cardsPayload?.cards?.length"

          class="storage-empty"

        >

          No cards in this location.

        </div>



        <div v-else class="table-panel cards-panel storage-cards-panel">

          <table class="storage-table">

            <thead>

              <tr>

                <th>Set</th>

                <th>#</th>

                <th>Card</th>

                <th>Art Style</th>

                <th>Finish</th>

                <th>Copies</th>

                <th>Total value</th>

                <th></th>

              </tr>

            </thead>

            <tbody>

              <tr v-for="card in cardsPayload.cards" :key="`${card.setCode}-${card.collectorNumber}-${cardFinish(card)}`">

                <td>

                  <RouterLink :to="setReportRoute(card.setCode)" class="reports-card-link">

                    {{ card.setCode }}

                  </RouterLink>

                </td>

                <td>{{ card.collectorNumber }}</td>

                <td>

                  <CardPreview :image-uri="card.imageUri">

                    <RouterLink :to="cardRoute(card)" class="reports-card-link">

                      {{ String(card.collectorNumber).padStart(3, "0") }} · {{ cardDisplayName(card) }}

                    </RouterLink>

                  </CardPreview>

                </td>

                <td>{{ card.artStyle || "—" }}</td>

                <td>{{ finishLabel(cardFinish(card)) }}</td>

                <td>{{ card.copyCount }}</td>

                <td>

                  <span>{{ formatEuro(lineTotal(card)) }}</span>

                  <span

                    v-if="card.copyCount > 1 && card.currentValue != null"

                    class="storage-unit-value"

                  >

                    {{ formatEuro(card.currentValue) }} each

                  </span>

                </td>

                <td class="storage-row-actions">

                  <button

                    type="button"

                    class="btn btn-small"

                    @click="removeOneCopy(card)"

                  >

                    Remove one

                  </button>

                </td>

              </tr>

            </tbody>

          </table>

        </div>

      </div>

    </div>



    <div v-if="editor.open" class="modal-backdrop" @click.self="closeEditor">

      <form class="modal-card" @submit.prevent="saveEditor">

        <h3>{{ editor.mode === "create" ? "New storage" : "Edit storage" }}</h3>

        <label>

          <span>Label</span>

          <input v-model="editor.label" type="text" maxlength="120" required />

        </label>

        <label>

          <span>Description</span>

          <textarea v-model="editor.description" rows="3" maxlength="500" />

        </label>

        <div class="modal-actions">

          <button type="button" class="btn btn-secondary" @click="closeEditor">

            Cancel

          </button>

          <button type="submit" class="btn btn-primary">

            {{ editor.mode === "create" ? "Create" : "Save" }}

          </button>

        </div>

      </form>

    </div>

  </div>

</template>


