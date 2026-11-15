<script setup>
import "../styles/card-detail.css";
import { computed, onDeactivated, onMounted, onUnmounted, ref, watch } from "vue";
import { api, ignoreAborted } from "../api";
import { cacheKeyFor, getCachedEntry } from "../apiCache";
import CardmarketIcon from "./CardmarketIcon.vue";
import CollectionSetLink from "./CollectionSetLink.vue";
import ScryfallIcon from "./ScryfallIcon.vue";
import { fetchFavorites, useFavorites } from "../composables/favorites";
import { displayCardmarketUrl } from "../utils/cardmarketUrl";
import { formatEuro } from "../utils/format";
import { FINISH_NONFOIL, finishLabel, normalizeFinish } from "../utils/finishes";
import { priceStrategyDescription } from "../utils/priceStrategies";
import { scryfallCardUri, scryfallPrintsSearchUri } from "../utils/scryfall";

const props = defineProps({
  imageUri: { type: String, default: "" },
  alt: { type: String, default: "" },
  setCode: { type: String, default: "" },
  collectorNumber: { type: [String, Number], default: "" },
  finish: { type: [String, Number], default: null },
  seed: { type: Object, default: null },
});

const emit = defineEmits(["close"]);

const card = ref(null);
const loading = ref(false);
const loadError = ref("");
const showBackFace = ref(false);
const selectedFinish = ref(FINISH_NONFOIL);
const { isCardFavorite, toggleCardFavorite } = useFavorites();
let loadToken = 0;

const printKey = computed(() => ({
  setCode: String(props.setCode || props.seed?.setCode || "").trim().toUpperCase(),
  collectorNumber: String(props.collectorNumber ?? props.seed?.collectorNumber ?? "").trim(),
  finish: props.finish ?? props.seed?.finish ?? props.seed?.foil ?? null,
}));

const ownedCopies = computed(() => (card.value?.ownedInstances || []).map((instance) => ({
  instanceId: instance.instanceId,
  finish: instance.finishLabel || finishLabel(instance.finish),
  place: instance.locationLabel || "",
})));

const showNonfoilGuidePrices = computed(() =>
  card.value?.guidePriceMatrix?.rows?.some((row) => row.nonfoil != null),
);
const showFoilGuidePrices = computed(() =>
  card.value?.guidePriceMatrix?.rows?.some((row) => row.foil != null),
);
const showEtchedGuidePrices = computed(() =>
  card.value?.guidePriceMatrix?.rows?.some((row) => row.etched != null),
);
const priceStrategy = computed(() => card.value?.priceStrategy || "trend");
const cardmarketLinkUrl = computed(() => displayCardmarketUrl(card.value?.cardmarketUrl));
const scryfallCardLinkUrl = computed(() => (
  card.value?.setCode && card.value?.collectorNumber
    ? scryfallCardUri(card.value.setCode, card.value.collectorNumber)
    : ""
));
const scryfallPrintsLinkUrl = computed(() => (
  card.value?.name ? scryfallPrintsSearchUri(card.value.name) : ""
));
const hasBackImage = computed(() => Boolean(card.value?.imageUriBack));
const displayImageUri = computed(() => {
  if (showBackFace.value && card.value?.imageUriBack) {
    return card.value.imageUriBack;
  }
  return props.imageUri || card.value?.imageUri || "";
});
const title = computed(() => (
  card.value?.name
  || props.alt
  || (printKey.value.setCode && printKey.value.collectorNumber
    ? `${printKey.value.setCode} #${printKey.value.collectorNumber}`
    : "Card")
));

function detailPath(setCode, collectorNumber, finish) {
  const query = new URLSearchParams();
  if (finish != null && finish !== "" && normalizeFinish(finish) !== FINISH_NONFOIL) {
    query.set("finish", String(normalizeFinish(finish)));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return `/cards/${encodeURIComponent(setCode)}/${encodeURIComponent(collectorNumber)}${suffix}`;
}

function shellCard() {
  const seed = props.seed || {};
  const { setCode, collectorNumber, finish } = printKey.value;
  return {
    ...seed,
    setCode: setCode || seed.setCode || "",
    collectorNumber: collectorNumber || seed.collectorNumber || "",
    name: seed.name || props.alt || "",
    setLabel: seed.setLabel || seed.setName || setCode,
    artStyle: seed.artStyle || "",
    imageUri: props.imageUri || seed.imageUri || "",
    finishes: seed.finishes || {},
    guidePriceMatrix: seed.guidePriceMatrix || null,
    selectedFinish: finish == null ? FINISH_NONFOIL : normalizeFinish(finish),
  };
}

function applyCard(next) {
  card.value = next;
  selectedFinish.value = normalizeFinish(next?.selectedFinish ?? printKey.value.finish ?? FINISH_NONFOIL);
}

async function loadCard({ background = false } = {}) {
  const { setCode, collectorNumber, finish } = printKey.value;
  if (!setCode || !collectorNumber) {
    applyCard(shellCard());
    return;
  }
  const token = ++loadToken;
  if (!background) {
    loading.value = true;
  }
  loadError.value = "";
  try {
    const next = await ignoreAborted(api.getCardDetail(setCode, collectorNumber, {
      finish: finish == null ? undefined : normalizeFinish(finish),
    }));
    if (token !== loadToken || !next) {
      return;
    }
    applyCard(next);
  } catch (error) {
    if (token !== loadToken) {
      return;
    }
    loadError.value = error?.message || "Could not load card details.";
  } finally {
    if (token === loadToken) {
      loading.value = false;
    }
  }
}

function close() {
  emit("close");
}

function onKeydown(event) {
  if (event.key === "Escape") {
    close();
  }
}

function toggleCardFace() {
  if (hasBackImage.value) {
    showBackFace.value = !showBackFace.value;
  }
}

async function onToggleFavorite() {
  if (!card.value?.name) {
    return;
  }
  await toggleCardFavorite(card.value, selectedFinish.value);
}

watch(printKey, () => {
  showBackFace.value = false;
  const cached = readCachedCard();
  applyCard(cached || shellCard());
  loadCard({ background: Boolean(cached?.name || props.seed?.guidePriceMatrix) });
});

function readCachedCard() {
  const { setCode, collectorNumber, finish } = printKey.value;
  if (!setCode || !collectorNumber) {
    return null;
  }
  const cached = getCachedEntry(cacheKeyFor("GET", detailPath(setCode, collectorNumber, finish)));
  return cached?.data || null;
}

onMounted(() => {
  document.body.style.overflow = "hidden";
  window.addEventListener("keydown", onKeydown);
  fetchFavorites();
  const cached = readCachedCard();
  applyCard(cached || shellCard());
  loadCard({ background: Boolean(cached?.name || props.seed?.guidePriceMatrix) });
});

onUnmounted(() => {
  loadToken += 1;
  document.body.style.overflow = "";
  window.removeEventListener("keydown", onKeydown);
});

onDeactivated(() => {
  close();
});
</script>

<template>
  <Teleport to="body">
    <div
      class="card-image-zoom-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Card preview"
      @click.self="close"
    >
      <button
        type="button"
        class="card-image-zoom-close"
        aria-label="Close card preview"
        @click="close"
      >
        ×
      </button>
      <div class="card-preview-stage">
        <div class="card-preview-image">
          <img
            v-if="displayImageUri"
            :src="displayImageUri"
            :alt="title"
            class="card-image-zoom-image"
          >
          <button
            v-if="hasBackImage"
            type="button"
            class="btn btn-secondary btn-small card-preview-face-toggle"
            @click="toggleCardFace"
          >
            {{ showBackFace ? "View front" : "View back" }}
          </button>
        </div>
        <div class="card-preview-info">
          <section class="card-preview-tile">
            <div class="card-detail-meta">
              <div class="card-detail-title-row">
                <h1>
                  {{ title }}
                  <span
                    v-if="loading && !card?.name"
                    class="loading-spinner card-detail-inline-spinner"
                    aria-label="Loading card"
                  ></span>
                </h1>
                <button
                  v-if="card?.name"
                  type="button"
                  class="card-detail-favorite"
                  :class="{ 'is-favorite': isCardFavorite(card, selectedFinish) }"
                  :aria-pressed="isCardFavorite(card, selectedFinish) ? 'true' : 'false'"
                  :aria-label="isCardFavorite(card, selectedFinish) ? `Unfavourite ${card.name}` : `Favourite ${card.name}`"
                  :title="isCardFavorite(card, selectedFinish) ? 'Unfavourite card' : 'Favourite card'"
                  @click="onToggleFavorite"
                >
                  {{ isCardFavorite(card, selectedFinish) ? "★" : "☆" }}
                </button>
              </div>
              <p v-if="card?.setCode" class="card-detail-set">
                <CollectionSetLink
                  :set-code="card.setCode"
                  :art-style="card.artStyle || ''"
                  :label="card.setLabel || card.setCode"
                />
              </p>
              <p v-if="card?.collectorNumber" class="card-detail-subtitle">
                #{{ String(card.collectorNumber).padStart(3, "0") }}
              </p>
              <p v-if="card?.artStyle" class="card-detail-art-style">{{ card.artStyle }}</p>
            </div>
            <div v-if="card?.name" class="card-preview-copies">
              <div class="card-preview-copies-head">
                <span>Owned copies</span>
                <strong>{{ ownedCopies.length }}</strong>
              </div>
              <ul v-if="ownedCopies.length" class="card-preview-copy-list">
                <li v-for="copy in ownedCopies" :key="copy.instanceId">
                  <span>{{ copy.finish }}</span>
                  <span v-if="copy.place">{{ copy.place }}</span>
                </li>
              </ul>
            </div>
          </section>
          <section class="card-preview-tile">
            <div class="card-detail-guide-panel">
              <div class="card-detail-guide-heading">
                <h2>Cardmarket prices (EUR)</h2>
              </div>
              <p v-if="loadError" class="card-detail-sync-message is-error">{{ loadError }}</p>
              <div v-if="card?.guidePriceMatrix?.rows?.length" class="card-detail-guide-table-wrap">
                <table class="card-detail-guide-table">
                  <thead>
                    <tr>
                      <th>Strategy</th>
                      <th v-if="showNonfoilGuidePrices">Non-foil</th>
                      <th v-if="showFoilGuidePrices">Foil</th>
                      <th v-if="showEtchedGuidePrices">Etched</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="row in card.guidePriceMatrix.rows"
                      :key="row.strategyId"
                      :class="{ 'is-active-strategy': row.strategyId === priceStrategy }"
                    >
                      <td>
                        <span
                          class="card-detail-strategy-label"
                          :title="priceStrategyDescription(row.strategyId)"
                        >
                          {{ row.label }}
                        </span>
                      </td>
                      <td v-if="showNonfoilGuidePrices">{{ formatEuro(row.nonfoil) }}</td>
                      <td v-if="showFoilGuidePrices">{{ formatEuro(row.foil) }}</td>
                      <td v-if="showEtchedGuidePrices">{{ formatEuro(row.etched) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="card-detail-external-links">
                <a
                  v-if="cardmarketLinkUrl"
                  :href="cardmarketLinkUrl"
                  class="card-detail-external-link card-detail-cardmarket-link"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <CardmarketIcon class="card-detail-external-icon" :size="16" />
                  <span>View on Cardmarket</span>
                </a>
                <a
                  v-if="scryfallCardLinkUrl"
                  :href="scryfallCardLinkUrl"
                  class="card-detail-external-link card-detail-scryfall-link"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <ScryfallIcon class="card-detail-external-icon" :size="16" />
                  <span>View on Scryfall</span>
                </a>
                <a
                  v-if="scryfallPrintsLinkUrl"
                  :href="scryfallPrintsLinkUrl"
                  class="card-detail-external-link card-detail-scryfall-link"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <ScryfallIcon class="card-detail-external-icon" :size="16" />
                  <span>All prints on Scryfall</span>
                </a>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  </Teleport>
</template>
