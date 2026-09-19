<script setup>
import { computed, ref, watch } from "vue";

import { api, ignoreAborted } from "../api";
import CollectionCardGrid from "./CollectionCardGrid.vue";
import LoadingIndicator from "./LoadingIndicator.vue";
import {
  fetchPricingSettings,
  usePricingSettings,
} from "../composables/pricingSettings";
import { sortCollectionCards } from "../utils/collectionSort";
import { applyGalleryDisplayToCards } from "../utils/priceStrategies";

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: "" },
  setCode: { type: String, default: "" },
  artStyle: { type: String, default: "" },
});

const emit = defineEmits(["close"]);

const { collectionCardScale } = usePricingSettings();
const cards = ref([]);
const loading = ref(false);
const error = ref("");

const heading = computed(() => props.title || props.artStyle || props.setCode || "Cards");

watch(
  () => [props.open, props.setCode, props.artStyle],
  async () => {
    if (!props.open) {
      cards.value = [];
      error.value = "";
      loading.value = false;
      return;
    }
    loading.value = true;
    error.value = "";
    cards.value = [];
    await fetchPricingSettings();
    const payload = await ignoreAborted(api.getReportCards({
      report: "all",
      setCode: props.setCode || "All",
      artStyle: props.artStyle || "",
      ownedFilter: "owned",
      sort: "value",
      dir: "desc",
    }));
    loading.value = false;
    if (!payload) {
      return;
    }
    cards.value = sortCollectionCards(
      applyGalleryDisplayToCards(payload.cards || []),
      { sort: "value", dir: "desc" },
    );
    if (!cards.value.length) {
      error.value = "No owned cards in this scope.";
    }
  },
);
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="modal-backdrop collection-tiles-modal-backdrop"
      role="presentation"
      @click.self="emit('close')"
    >
      <div
        class="modal-card collection-tiles-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="collection-tiles-modal-title"
        @keydown.esc.stop="emit('close')"
      >
        <div class="collection-tiles-modal-head">
          <div>
            <h3 id="collection-tiles-modal-title">{{ heading }}</h3>
            <p class="collection-tiles-modal-intro">
              Owned cards, highest current value first.
            </p>
          </div>
          <button type="button" class="btn btn-secondary" @click="emit('close')">
            Close
          </button>
        </div>
        <div class="collection-tiles-modal-body collection-gallery-panel">
          <LoadingIndicator v-if="loading" label="Loading cards…" />
          <p v-else-if="error" class="collection-tiles-modal-empty">{{ error }}</p>
          <CollectionCardGrid
            v-else
            :cards="cards"
            :show-unowned-badge="false"
            :show-set-label="!setCode"
            :card-scale="collectionCardScale"
            zoom-only
          />
        </div>
      </div>
    </div>
  </Teleport>
</template>
