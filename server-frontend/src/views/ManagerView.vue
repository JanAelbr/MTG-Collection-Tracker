<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "../api";
import CardPreview from "../components/CardPreview.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import SetPicker from "../components/SetPicker.vue";
import { fetchPricingSettings, usePricingSettings } from "../composables/pricingSettings";
import { useAsyncLoad } from "../composables/useAsyncLoad";
import { getStoredFoilFilter, storeFoilFilter } from "../utils/filterStorage";
import { FINISH_ETCHED, FINISH_FOIL, FINISH_NONFOIL, hasFinish } from "../utils/finishes";
import ArtStylePicker from "../components/ArtStylePicker.vue";

const route = useRoute();
const router = useRouter();

const sets = ref([]);
const selectedSetCode = ref("");
const cardsPayload = ref(null);
const artStyle = ref("");
const foilFilter = ref(getStoredFoilFilter());
const searchInput = ref("");
const search = ref("");
const page = ref(1);
const selectedRows = ref(new Set());
const selectAllVisible = ref(false);
const storageLocations = ref([]);
const assignLocationSlug = ref("");
const { pageSize, setPickerMode } = usePricingSettings();
const { loading: loadingCards, run: runCardsLoad } = useAsyncLoad();

const visibleCards = computed(() => cardsPayload.value?.cards || []);
const totalPages = computed(() => cardsPayload.value?.totalPages || 1);
const artStyles = computed(() => cardsPayload.value?.artStyles || []);
const activeSet = computed(
  () => sets.value.find((set) => set.setCode === selectedSetCode.value) || null,
);
const activeSetFavorite = computed(() => Boolean(activeSet.value?.favorite));

const allVisibleSelected = computed({
  get() {
    if (!visibleCards.value.length) {
      return false;
    }
    return visibleCards.value.every((card) =>
      selectedRows.value.has(card.collectorNumber),
    );
  },
  set(checked) {
    const next = new Set(selectedRows.value);
    for (const card of visibleCards.value) {
      if (checked) {
        next.add(card.collectorNumber);
      } else {
        next.delete(card.collectorNumber);
      }
    }
    selectedRows.value = next;
    selectAllVisible.value = checked;
  },
});

function rowKey(card) {
  return card.collectorNumber;
}

function isRowSelected(card) {
  return selectedRows.value.has(rowKey(card));
}

function toggleRow(card) {
  const next = new Set(selectedRows.value);
  const key = rowKey(card);
  if (next.has(key)) {
    next.delete(key);
  } else {
    next.add(key);
  }
  selectedRows.value = next;
}

async function onSetsChanged(event) {
  if (event?.sets) {
    sets.value = event.sets;
  } else {
    let preferred = selectedSetCode.value;
    if (event?.removed && event.setCode === preferred) {
      preferred = "";
    } else if (event?.setCode && !event?.removed) {
      preferred = event.setCode;
    }
    await loadSets(preferred);
  }
  if (selectedSetCode.value) {
    await loadCards();
  }
}

async function loadSets(preferredSet = "") {
  const payload = await api.listManagerSets();
  sets.value = payload.sets || [];
  const fromRoute = typeof route.query.set === "string" ? route.query.set : "";
  selectedSetCode.value =
    preferredSet || fromRoute || payload.defaultSet || sets.value[0]?.setCode || "";
}

async function toggleFavorite(set) {
  const payload = await api.toggleManagerSetFavorite(set.setCode);
  sets.value = payload.sets || [];
}

async function loadCards() {
  if (!selectedSetCode.value) {
    cardsPayload.value = null;
    return;
  }
  await runCardsLoad(async () => {
    cardsPayload.value = await api.getManagerSetCards(selectedSetCode.value, {
      artStyle: artStyle.value,
      search: search.value.trim(),
      foilFilter: foilFilter.value,
      page: page.value,
      pageSize: pageSize.value,
    });
    selectedRows.value = new Set();
    selectAllVisible.value = false;
  });
}

async function loadStorageLocations() {
  const payload = await api.listStorageLocations();
  storageLocations.value = payload.locations || [];
  assignLocationSlug.value = payload.defaultLocation || storageLocations.value[0]?.slug || "";
}

async function toggleOwnership(card, finish, owned) {
  const updated = await api.updateOwnership({
    setCode: selectedSetCode.value,
    collectorNumber: card.collectorNumber,
    finish,
    owned,
  });
  Object.assign(card, updated);
}

function ownedItemsForSelectedRows() {
  const items = [];
  for (const card of visibleCards.value) {
    if (!selectedRows.value.has(card.collectorNumber)) {
      continue;
    }
    if (hasFinish(card, FINISH_NONFOIL) && card.ownedNonfoil) {
      items.push({
        setCode: card.setCode,
        collectorNumber: card.collectorNumber,
        finish: FINISH_NONFOIL,
      });
    }
    if (hasFinish(card, FINISH_FOIL) && card.ownedFoil) {
      items.push({
        setCode: card.setCode,
        collectorNumber: card.collectorNumber,
        finish: FINISH_FOIL,
      });
    }
    if (hasFinish(card, FINISH_ETCHED) && card.ownedEtched) {
      items.push({
        setCode: card.setCode,
        collectorNumber: card.collectorNumber,
        finish: FINISH_ETCHED,
      });
    }
  }
  return items;
}

async function assignSelectedToStorage() {
  const items = ownedItemsForSelectedRows();
  if (!items.length) {
    window.alert("Select owned cards on this page first.");
    return;
  }
  if (!assignLocationSlug.value) {
    return;
  }
  const result = await api.bulkAssignStorage({
    locationSlug: assignLocationSlug.value,
    items,
  });
  window.alert(`Moved ${result.moved} card instance(s).`);
}

function goToPage(nextPage) {
  page.value = Math.min(Math.max(1, nextPage), totalPages.value);
}

watch(selectedSetCode, (setCode) => {
  page.value = 1;
  artStyle.value = "";
  search.value = "";
  router.replace({ query: setCode ? { set: setCode } : {} });
  loadCards();
});

function setFoilFilter(nextFilter) {
  foilFilter.value = nextFilter;
  storeFoilFilter(nextFilter);
  page.value = 1;
  loadCards();
}

watch([artStyle, search], () => {
  page.value = 1;
  loadCards();
});

let searchTimer = null;
watch(searchInput, (value) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    search.value = value;
  }, 300);
});

watch(page, () => {
  loadCards();
});

watch(pageSize, () => {
  page.value = 1;
  loadCards();
});

onMounted(async () => {
  await Promise.all([fetchPricingSettings(), loadSets(), loadStorageLocations()]);
  if (selectedSetCode.value) {
    await loadCards();
  }
});
</script>

<template>
  <div class="manager-page">
    <SetPicker
      v-model="selectedSetCode"
      layout="banner"
      :sets="sets"
      show-favorites
      @toggle-favorite="toggleFavorite"
      @sets-changed="onSetsChanged"
    />

    <div class="manager-layout manager-layout--single">
      <div class="manager-detail">
        <div class="manager-toolbar">
          <div class="manager-toolbar-filters">
            <SetPicker
              v-model="selectedSetCode"
              layout="dropdown"
              :sets="sets"
            />
            <button
              v-if="setPickerMode !== 'browser' && selectedSetCode && activeSet"
              type="button"
              class="btn btn-secondary btn-small manager-set-favorite-btn"
              :class="{ 'is-favorite': activeSetFavorite }"
              @click="toggleFavorite(activeSet)"
            >
              {{ activeSetFavorite ? "★ Favourited" : "☆ Favourite set" }}
            </button>
            <input
              v-model="searchInput"
              type="search"
              class="manager-search"
              placeholder="Search cards…"
            />
            <ArtStylePicker
              v-model="artStyle"
              :art-styles="artStyles"
            />
            <div class="manager-filter">
              <span>Finish filter</span>
              <div class="button-group deck-gallery-sort-group">
                <button
                  type="button"
                  class="filter-button"
                  :class="{ active: foilFilter === 'all' }"
                  @click="setFoilFilter('all')"
                >
                  All
                </button>
                <button
                  type="button"
                  class="filter-button"
                  :class="{ active: foilFilter === 'nonfoil' }"
                  @click="setFoilFilter('nonfoil')"
                >
                  Non-foil
                </button>
                <button
                  type="button"
                  class="filter-button"
                  :class="{ active: foilFilter === 'foil' }"
                  @click="setFoilFilter('foil')"
                >
                  Foil
                </button>
                <button
                  type="button"
                  class="filter-button"
                  :class="{ active: foilFilter === 'etched' }"
                  @click="setFoilFilter('etched')"
                >
                  Etched
                </button>
              </div>
            </div>
            <LoadingIndicator v-if="loadingCards" compact label="Loading cards…" />
          </div>

          <div class="manager-toolbar-actions">
            <label class="manager-select-all">
              <input v-model="allVisibleSelected" type="checkbox" />
              Select visible
            </label>

            <label class="manager-filter">
              <span>Assign to</span>
              <select v-model="assignLocationSlug">
                <option
                  v-for="location in storageLocations"
                  :key="location.slug"
                  :value="location.slug"
                >
                  {{ location.label }}
                </option>
              </select>
            </label>
            <button type="button" class="btn btn-secondary" @click="assignSelectedToStorage">
              Assign storage
            </button>
          </div>
        </div>

        <p v-if="selectedSetCode" class="manager-stats">
          {{ cardsPayload?.total ?? 0 }} cards
          <span v-if="cardsPayload?.totalPages > 1">
            · page {{ cardsPayload?.page }} / {{ cardsPayload?.totalPages }}
          </span>
        </p>

        <div v-if="loadingCards && !visibleCards.length" class="storage-empty">
          <LoadingIndicator label="Loading cards…" />
        </div>

        <div v-else-if="!visibleCards.length" class="storage-empty">
          No cards found for this set.
        </div>

        <div v-else class="table-panel cards-panel manager-cards-panel">
          <table class="manager-table">
            <thead>
              <tr>
                <th></th>
                <th>#</th>
                <th>Card</th>
                <th>Art Style</th>
                <th>Non-foil</th>
                <th>Foil</th>
                <th>Etched</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="card in visibleCards" :key="rowKey(card)">
                <td>
                  <input
                    type="checkbox"
                    :checked="isRowSelected(card)"
                    @change="toggleRow(card)"
                  />
                </td>
                <td>{{ card.collectorNumber }}</td>
                <td>
                  <CardPreview :image-uri="card.imageUri">
                    <RouterLink
                      :to="{
                        name: 'card',
                        params: { setCode: card.setCode, collectorNumber: card.collectorNumber },
                      }"
                      class="reports-card-link"
                    >
                      {{ card.name }}
                    </RouterLink>
                  </CardPreview>
                </td>
                <td>{{ card.artStyle || "—" }}</td>
                <td class="manager-checkbox-cell">
                  <input
                    v-if="hasFinish(card, FINISH_NONFOIL)"
                    type="checkbox"
                    :checked="card.ownedNonfoil"
                    @change="toggleOwnership(card, FINISH_NONFOIL, $event.target.checked)"
                  />
                  <span v-else class="manager-finish-unavailable">—</span>
                </td>
                <td class="manager-checkbox-cell">
                  <input
                    v-if="hasFinish(card, FINISH_FOIL)"
                    type="checkbox"
                    :checked="card.ownedFoil"
                    @change="toggleOwnership(card, FINISH_FOIL, $event.target.checked)"
                  />
                  <span v-else class="manager-finish-unavailable">—</span>
                </td>
                <td class="manager-checkbox-cell">
                  <input
                    v-if="hasFinish(card, FINISH_ETCHED)"
                    type="checkbox"
                    :checked="card.ownedEtched"
                    @change="toggleOwnership(card, FINISH_ETCHED, $event.target.checked)"
                  />
                  <span v-else class="manager-finish-unavailable">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="totalPages > 1" class="manager-pagination">
          <button
            type="button"
            class="btn btn-secondary"
            :disabled="page <= 1"
            @click="goToPage(page - 1)"
          >
            Previous
          </button>
          <span>Page {{ page }} / {{ totalPages }}</span>
          <button
            type="button"
            class="btn btn-secondary"
            :disabled="page >= totalPages"
            @click="goToPage(page + 1)"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
