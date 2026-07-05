<script setup>

import { computed, onMounted, reactive, ref, watch } from "vue";

import { useRoute } from "vue-router";

import { api } from "../api";

import CardPreview from "../components/CardPreview.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import StorageLocationIcon from "../components/StorageLocationIcon.vue";
import { savePricingSettings, usePricingSettings } from "../composables/pricingSettings";
import { useAsyncLoad } from "../composables/useAsyncLoad";

import { formatEuro } from "../utils/format";
import { cardDisplayName, cardFinish, cardRouteQuery, finishLabel } from "../utils/finishes";



const route = useRoute();

const { settings: pricingSettings, fetchPricingSettings: loadPricingSettings } = usePricingSettings();

const locations = ref([]);

const selectedSlug = ref("");

const cardsPayload = ref(null);

const defaultStorageSaving = ref(false);

const { loading: loadingCards, run: runCardsLoad } = useAsyncLoad();



const editor = reactive({
  open: false,
  locationType: "storage",
  label: "",
  description: "",
});

const inlineLabel = ref("");
const inlineDescription = ref("");
const inlineSaving = ref(false);
const inlineError = ref("");
const inlineLabelRef = ref(null);
const inlineDescRef = ref(null);

const selectedLocation = computed(() =>
  locations.value.find((item) => item.slug === selectedSlug.value),
);

const canInlineEdit = computed(() => {
  const type = selectedLocation.value?.locationType;
  return type === "storage" || type === "binder";
});

const visibleLocations = computed(() =>
  locations.value.filter(
    (location) => location.cardCount > 0 || location.isCustom || location.isSystem,
  ),
);

const LOCATION_TYPE_SECTIONS = [
  { type: "storage", label: "Storage", canCreate: true },
  { type: "binder", label: "Binders", canCreate: true },
  { type: "deck", label: "Decks", collapsible: true, defaultCollapsed: true },
];

const sectionExpanded = reactive(
  Object.fromEntries(
    LOCATION_TYPE_SECTIONS.filter((section) => section.collapsible).map((section) => [
      section.type,
      !section.defaultCollapsed,
    ]),
  ),
);

function isSectionExpanded(section) {
  if (!section.collapsible) {
    return true;
  }
  return sectionExpanded[section.type] ?? true;
}

function toggleSection(section) {
  if (!section.collapsible) {
    return;
  }
  sectionExpanded[section.type] = !sectionExpanded[section.type];
}

const groupedVisibleLocations = computed(() =>
  LOCATION_TYPE_SECTIONS.map((section) => ({
    ...section,
    locations: visibleLocations.value.filter(
      (location) => location.locationType === section.type,
    ),
  })).filter((section) => section.locations.length > 0 || section.canCreate),
);

function createLocationLabel(sectionType) {
  return sectionType === "binder" ? "New binder" : "New storage";
}

function isDefaultStorage(location) {
  if (!location || location.locationType !== "storage") {
    return false;
  }
  const current = pricingSettings.value?.defaultStorageLocation ?? "storage:general";
  return location.slug === current;
}

async function toggleDefaultStorage(location) {
  if (!location || location.locationType !== "storage" || defaultStorageSaving.value) {
    return;
  }
  if (isDefaultStorage(location)) {
    return;
  }
  defaultStorageSaving.value = true;
  try {
    await savePricingSettings({ defaultStorageLocation: location.slug });
  } catch (error) {
    window.alert(error.message || "Could not set default storage.");
  } finally {
    defaultStorageSaving.value = false;
  }
}

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



async function loadCards() {
  if (!selectedSlug.value) {
    cardsPayload.value = null;
    return;
  }
  await runCardsLoad(async () => {
    cardsPayload.value = await api.getStorageLocationCards(selectedSlug.value);
  });
}



function openCreateEditor(locationType = "storage") {
  editor.open = true;
  editor.locationType = locationType;
  editor.label = "";
  editor.description = "";
}

function closeEditor() {
  editor.open = false;
}

async function saveEditor() {
  const label = editor.label.trim();
  if (!label) {
    return;
  }
  const created = await api.createStorageLocation({
    label,
    description: editor.description.trim(),
    locationType: editor.locationType,
  });
  closeEditor();
  await loadLocations(created.slug);
}

function syncInlineFields(location) {
  if (!location) {
    inlineLabel.value = "";
    inlineDescription.value = "";
    return;
  }
  inlineLabel.value = location.label;
  inlineDescription.value = location.description || "";
  inlineError.value = "";
}

async function saveInlineLabel() {
  const location = selectedLocation.value;
  if (!location || !canInlineEdit.value || inlineSaving.value) {
    return;
  }
  const label = inlineLabel.value.trim();
  if (!label) {
    inlineLabel.value = location.label;
    inlineError.value = "Name is required.";
    return;
  }
  if (label === location.label) {
    return;
  }
  await saveInlineFields({ label });
}

async function saveInlineDescription() {
  const location = selectedLocation.value;
  if (!location || !canInlineEdit.value || inlineSaving.value) {
    return;
  }
  const description = inlineDescription.value.trim();
  if (description === (location.description || "")) {
    return;
  }
  await saveInlineFields({ description });
}

async function saveInlineFields(body) {
  const location = selectedLocation.value;
  if (!location) {
    return;
  }
  inlineSaving.value = true;
  inlineError.value = "";
  try {
    await api.updateStorageLocation(location.slug, body);
    await loadLocations(location.slug);
    syncInlineFields(selectedLocation.value);
  } catch (error) {
    inlineError.value = error.message || "Could not save.";
    syncInlineFields(location);
  } finally {
    inlineSaving.value = false;
  }
}

function onInlineLabelKeydown(event) {
  if (event.key === "Enter") {
    event.preventDefault();
    inlineLabelRef.value?.blur();
  }
  if (event.key === "Escape") {
    inlineLabel.value = selectedLocation.value?.label || "";
    inlineLabelRef.value?.blur();
  }
}

function onInlineDescKeydown(event) {
  if (event.key === "Escape") {
    inlineDescription.value = selectedLocation.value?.description || "";
    inlineDescRef.value?.blur();
  }
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

watch(selectedLocation, (location) => {
  syncInlineFields(location);
  if (location?.locationType === "deck") {
    sectionExpanded.deck = true;
  }
});



onMounted(async () => {
  const preferredLocation =
    typeof route.query.location === "string" ? route.query.location : "";
  await Promise.all([loadLocations(preferredLocation), loadPricingSettings(true)]);
});

</script>



<template>

  <div class="storage-page">
    <div class="storage-layout">

      <nav class="storage-location-nav" aria-label="Storage locations">
        <section
          v-for="section in groupedVisibleLocations"
          :key="section.type"
          class="storage-location-section"
          :class="{ 'storage-location-section--collapsed': !isSectionExpanded(section) }"
        >
          <button
            v-if="section.collapsible"
            type="button"
            class="storage-location-section-heading storage-location-section-toggle"
            :aria-expanded="isSectionExpanded(section) ? 'true' : 'false'"
            @click="toggleSection(section)"
          >
            <StorageLocationIcon :type="section.type" />
            <span class="storage-location-section-title">{{ section.label }}</span>
            <span class="storage-location-section-count">{{ section.locations.length }}</span>
            <span class="storage-location-section-chevron" aria-hidden="true">▾</span>
          </button>
          <h3 v-else class="storage-location-section-heading">
            <StorageLocationIcon :type="section.type" />
            <span class="storage-location-section-title">{{ section.label }}</span>
            <button
              v-if="section.canCreate"
              type="button"
              class="storage-location-section-add"
              :aria-label="createLocationLabel(section.type)"
              :title="createLocationLabel(section.type)"
              @click="openCreateEditor(section.type)"
            >
              +
            </button>
          </h3>
          <div
            v-for="location in section.locations"
            v-show="isSectionExpanded(section)"
            :key="location.slug"
            class="storage-location-link"
            :class="{ active: location.slug === selectedSlug }"
          >
            <button
              type="button"
              class="storage-location-select"
              @click="selectedSlug = location.slug"
            >
              <span class="storage-location-link-main">
                <StorageLocationIcon :type="location.locationType" />
                <span class="storage-location-label">{{ location.label }}</span>
              </span>
            </button>
            <button
              v-if="location.locationType === 'storage'"
              type="button"
              class="storage-location-default"
              :class="{ 'is-default': isDefaultStorage(location) }"
              :disabled="defaultStorageSaving"
              :aria-pressed="isDefaultStorage(location) ? 'true' : 'false'"
              :aria-label="isDefaultStorage(location) ? `${location.label} is default storage` : `Set ${location.label} as default storage`"
              :title="isDefaultStorage(location) ? 'Default storage' : 'Set as default storage'"
              @click="toggleDefaultStorage(location)"
            >
              {{ isDefaultStorage(location) ? "★" : "☆" }}
            </button>
            <span class="storage-location-count">{{ location.cardCount }}</span>
          </div>
        </section>
      </nav>



      <div class="storage-detail">

        <div v-if="selectedLocation" class="storage-detail-header">

          <div class="storage-detail-title-row">
            <div class="storage-detail-title-main">
              <StorageLocationIcon
                :type="selectedLocation.locationType"
                class="storage-detail-type-icon"
              />
              <input
              v-if="canInlineEdit"
              ref="inlineLabelRef"
              v-model="inlineLabel"
              class="storage-inline-title"
              type="text"
              maxlength="120"
              :disabled="inlineSaving"
              aria-label="Storage name"
              @blur="saveInlineLabel"
              @keydown="onInlineLabelKeydown"
              />
              <h2 v-else>{{ selectedLocation.label }}</h2>
            </div>

            <div class="storage-detail-actions">
              <button
                v-if="selectedLocation.locationType === 'storage'"
                type="button"
                class="storage-location-default storage-location-default--detail"
                :class="{ 'is-default': isDefaultStorage(selectedLocation) }"
                :disabled="defaultStorageSaving"
                :aria-pressed="isDefaultStorage(selectedLocation) ? 'true' : 'false'"
                :aria-label="isDefaultStorage(selectedLocation) ? 'Default storage' : 'Set as default storage'"
                :title="isDefaultStorage(selectedLocation) ? 'Default storage' : 'Set as default storage'"
                @click="toggleDefaultStorage(selectedLocation)"
              >
                {{ isDefaultStorage(selectedLocation) ? "★ Default" : "☆ Set default" }}
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

          <textarea
            v-if="canInlineEdit"
            ref="inlineDescRef"
            v-model="inlineDescription"
            class="storage-inline-description"
            rows="2"
            maxlength="500"
            placeholder="Add a description…"
            :disabled="inlineSaving"
            aria-label="Storage description"
            @blur="saveInlineDescription"
            @keydown="onInlineDescKeydown"
          />
          <p
            v-else-if="selectedLocation.description"
            class="storage-location-description"
          >
            {{ selectedLocation.description }}
          </p>

          <p v-if="inlineError" class="storage-inline-error">{{ inlineError }}</p>

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

        <h3>{{ editor.locationType === "binder" ? "New binder" : "New storage" }}</h3>

        <label>
          <span>Type</span>
          <select v-model="editor.locationType">
            <option value="storage">Storage</option>
            <option value="binder">Binder</option>
          </select>
        </label>

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

          <button type="submit" class="btn btn-primary">Create</button>

        </div>

      </form>

    </div>

  </div>

</template>


