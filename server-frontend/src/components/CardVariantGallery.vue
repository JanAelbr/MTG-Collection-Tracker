<script setup>
import "../styles/card-detail.css";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import CollectionSetLink from "./CollectionSetLink.vue";
import CardFinishBadge from "./CardFinishBadge.vue";
import CardSetSymbol from "./CardSetSymbol.vue";
import { formatEuro } from "../utils/format";
import {
  FINISH_ETCHED,
  FINISH_FOIL,
  FINISH_NONFOIL,
  cardRouteQuery,
  finishLabel,
  hasFinish,
  marketValueForFinish,
  normalizeFinish,
} from "../utils/finishes";

const NEIGHBOR_BATCH = 8;

const props = defineProps({
  title: { type: String, default: "" },
  cards: { type: Array, default: () => [] },
  currentIndex: { type: Number, default: -1 },
  finish: { type: Number, default: 0 },
  showName: { type: Boolean, default: false },
  showArrows: { type: Boolean, default: false },
  centered: { type: Boolean, default: false },
  selectable: { type: Boolean, default: false },
});

const emit = defineEmits(["select"]);

const prevCount = ref(NEIGHBOR_BATCH);
const nextCount = ref(NEIGHBOR_BATCH);
const listRef = ref(null);

const visibleCards = computed(() => {
  if (!props.showArrows || props.currentIndex < 0 || !props.cards.length) {
    return props.cards;
  }
  const start = Math.max(0, props.currentIndex - prevCount.value);
  const end = Math.min(props.cards.length, props.currentIndex + 1 + nextCount.value);
  return props.cards.slice(start, end);
});

const hasMorePrev = computed(
  () => props.showArrows && props.currentIndex - prevCount.value > 0,
);
const hasMoreNext = computed(
  () =>
    props.showArrows
    && props.currentIndex >= 0
    && props.currentIndex + 1 + nextCount.value < props.cards.length,
);

const listClass = computed(() => ({
  "card-variant-list": true,
  "is-fit-centered": props.centered && !props.showArrows,
}));

function cardRoute(card) {
  return {
    name: "card",
    params: { setCode: card.setCode, collectorNumber: card.collectorNumber },
    query: cardRouteQuery(normalizeFinish(props.finish)),
  };
}

function collectorNumberLabel(card) {
  return `#${String(card.collectorNumber).padStart(3, "0")}`;
}

function scrollList(alignment = "center") {
  const list = listRef.value;
  if (!list) {
    return;
  }
  if (alignment === "start") {
    list.scrollLeft = 0;
    return;
  }
  if (alignment === "end") {
    list.scrollLeft = Math.max(0, list.scrollWidth - list.clientWidth);
    return;
  }
  const current = list.querySelector(".card-variant-current");
  if (!current) {
    return;
  }
  const listRect = list.getBoundingClientRect();
  const currentRect = current.getBoundingClientRect();
  const delta = (currentRect.left + currentRect.width / 2) - (listRect.left + listRect.width / 2);
  list.scrollLeft += delta;
}

function resetWindow() {
  prevCount.value = NEIGHBOR_BATCH;
  nextCount.value = NEIGHBOR_BATCH;
}

function showMorePrev() {
  prevCount.value += NEIGHBOR_BATCH;
  nextTick(() => scrollList("start"));
}

function showMoreNext() {
  nextCount.value += NEIGHBOR_BATCH;
  nextTick(() => scrollList("end"));
}

watch(
  () => [props.cards, props.currentIndex, props.finish],
  async () => {
    resetWindow();
    await nextTick();
    scrollList("center");
  },
);

onMounted(() => {
  nextTick(() => scrollList("center"));
});
function onSelect(card) {
  emit("select", card);
}
</script>

<template>
  <section v-if="cards.length" class="card-detail-panel card-detail-gallery">
    <div v-if="showArrows" class="card-neighbor-header">
      <button
        type="button"
        class="card-neighbor-arrow card-neighbor-arrow-prev"
        :class="{ 'is-hidden': !hasMorePrev }"
        aria-label="More previous cards"
        title="More previous cards"
        @click="showMorePrev"
      >
        ←
      </button>
      <h2>{{ title }}</h2>
      <button
        type="button"
        class="card-neighbor-arrow card-neighbor-arrow-next"
        :class="{ 'is-hidden': !hasMoreNext }"
        aria-label="More next cards"
        title="More next cards"
        @click="showMoreNext"
      >
        →
      </button>
    </div>
    <h2 v-else>{{ title }}</h2>

    <div ref="listRef" :class="listClass">
      <template v-for="card in visibleCards" :key="`${card.setCode}-${card.collectorNumber}-${card.artStyle || ''}`">
        <button
          v-if="selectable && !card.isCurrent"
          type="button"
          class="card-variant"
          @click="onSelect(card)"
        >
          <div class="card-variant-body">
            <div class="card-variant-image-wrap">
              <img
                v-if="card.imageUri"
                :src="card.imageUri"
                :alt="card.name"
                class="card-variant-image"
              />
              <div v-else class="card-variant-image card-variant-image-empty" />
            </div>
            <p class="card-variant-caption">
              <CardSetSymbol
                :set-code="card.setCode"
                variant="generic"
                :size="12"
              />
              <CollectionSetLink :set-code="card.setCode" :art-style="card.artStyle || ''" />
              · {{ collectorNumberLabel(card) }}
            </p>
            <p v-if="showName" class="card-variant-name">
              <CardSetSymbol :set-code="card.setCode" :rarity="card.rarity || ''" />
              <span>{{ card.name }}</span>
              <CardFinishBadge :card="card" :finish="finish" compact />
            </p>
            <div class="card-variant-prices">
              <template v-for="finishOption in [FINISH_NONFOIL, FINISH_FOIL, FINISH_ETCHED]" :key="finishOption">
                <div
                  v-if="hasFinish(card, finishOption)"
                  class="card-variant-price-row"
                  :class="{ 'card-variant-price-row-highlight': finishOption !== FINISH_NONFOIL }"
                >
                  <span class="card-variant-key">{{ finishLabel(finishOption) }}</span>
                  <span>{{ formatEuro(marketValueForFinish(card, finishOption)) }}</span>
                </div>
              </template>
            </div>
          </div>
        </button>
        <RouterLink
          v-else-if="!card.isCurrent"
          :to="cardRoute(card)"
          class="card-variant"
        >
          <div class="card-variant-body">
            <div class="card-variant-image-wrap">
              <img
                v-if="card.imageUri"
                :src="card.imageUri"
                :alt="card.name"
                class="card-variant-image"
              />
              <div v-else class="card-variant-image card-variant-image-empty" />
            </div>
            <p class="card-variant-caption">
              <CardSetSymbol
                :set-code="card.setCode"
                variant="generic"
                :size="12"
              />
              <CollectionSetLink :set-code="card.setCode" :art-style="card.artStyle || ''" />
              · {{ collectorNumberLabel(card) }}
            </p>
            <p v-if="showName" class="card-variant-name">
              <CardSetSymbol :set-code="card.setCode" :rarity="card.rarity || ''" />
              <span>{{ card.name }}</span>
              <CardFinishBadge :card="card" :finish="finish" compact />
            </p>
            <div class="card-variant-prices">
              <template v-for="finishOption in [FINISH_NONFOIL, FINISH_FOIL, FINISH_ETCHED]" :key="finishOption">
                <div
                  v-if="hasFinish(card, finishOption)"
                  class="card-variant-price-row"
                  :class="{ 'card-variant-price-row-highlight': finishOption !== FINISH_NONFOIL }"
                >
                  <span class="card-variant-key">{{ finishLabel(finishOption) }}</span>
                  <span>{{ formatEuro(marketValueForFinish(card, finishOption)) }}</span>
                </div>
              </template>
            </div>
          </div>
        </RouterLink>
        <div v-else class="card-variant card-variant-current">
          <div class="card-variant-body">
            <div class="card-variant-image-wrap">
              <img
                v-if="card.imageUri"
                :src="card.imageUri"
                :alt="card.name"
                class="card-variant-image"
              />
              <div v-else class="card-variant-image card-variant-image-empty" />
            </div>
            <p class="card-variant-caption">
              <CardSetSymbol
                :set-code="card.setCode"
                variant="generic"
                :size="12"
              />
              <CollectionSetLink :set-code="card.setCode" :art-style="card.artStyle || ''" />
              · {{ collectorNumberLabel(card) }}
            </p>
            <p v-if="showName" class="card-variant-name">
              <CardSetSymbol :set-code="card.setCode" :rarity="card.rarity || ''" />
              <span>{{ card.name }}</span>
              <CardFinishBadge :card="card" :finish="finish" compact />
            </p>
            <div class="card-variant-prices">
              <template v-for="finishOption in [FINISH_NONFOIL, FINISH_FOIL, FINISH_ETCHED]" :key="finishOption">
                <div
                  v-if="hasFinish(card, finishOption)"
                  class="card-variant-price-row"
                  :class="{ 'card-variant-price-row-highlight': finishOption !== FINISH_NONFOIL }"
                >
                  <span class="card-variant-key">{{ finishLabel(finishOption) }}</span>
                  <span>{{ formatEuro(marketValueForFinish(card, finishOption)) }}</span>
                </div>
              </template>
            </div>
          </div>
        </div>
      </template>
    </div>
  </section>
</template>
