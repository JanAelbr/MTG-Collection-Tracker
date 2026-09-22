<script setup>
import { nextTick, onMounted, onUnmounted, ref } from "vue";

defineProps({
  label: { type: String, default: "items" },
});

const scroller = ref(null);
const canScroll = ref(false);
const canPrev = ref(false);
const canNext = ref(false);

let resizeObserver = null;

function updateEnds() {
  const el = scroller.value;
  if (!el) {
    return;
  }
  const max = el.scrollWidth - el.clientWidth;
  canScroll.value = max > 2;
  canPrev.value = el.scrollLeft > 2;
  canNext.value = el.scrollLeft < max - 2;
}

function scrollItem(el) {
  return (
    el.querySelector(".collection-card-grid-item")
    || el.querySelector(".price-sync-movers-list.is-tiles > li")
    || el.querySelector(".is-edge-carousel-track")?.firstElementChild
    || el.firstElementChild
  );
}

function scrollStep(el) {
  const item = scrollItem(el);
  if (!item) {
    return Math.max(120, el.clientWidth * 0.75);
  }
  const parent = item.parentElement;
  const styles = parent ? getComputedStyle(parent) : null;
  const gap = styles ? (Number.parseFloat(styles.columnGap || styles.gap) || 0) : 0;
  return item.getBoundingClientRect().width + gap;
}

function scrollByDirection(direction) {
  const el = scroller.value;
  if (!el) {
    return;
  }
  el.scrollBy({
    left: direction * scrollStep(el) * 3,
    behavior: "smooth",
  });
}

function observe() {
  resizeObserver?.disconnect();
  const el = scroller.value;
  if (!el) {
    return;
  }
  resizeObserver = new ResizeObserver(() => updateEnds());
  resizeObserver.observe(el);
  if (el.firstElementChild) {
    resizeObserver.observe(el.firstElementChild);
  }
}

onMounted(async () => {
  await nextTick();
  observe();
  updateEnds();
});

onUnmounted(() => {
  resizeObserver?.disconnect();
});

defineExpose({ scroller });
</script>

<template>
  <div class="edge-carousel" :class="{ 'can-scroll': canScroll }">
    <button
      type="button"
      class="edge-carousel-btn is-prev"
      :disabled="!canPrev"
      :aria-label="`Previous ${label}`"
      @click="scrollByDirection(-1)"
    >
      ‹
    </button>
    <div
      ref="scroller"
      class="edge-carousel-scroller"
      @scroll="updateEnds"
    >
      <slot />
    </div>
    <button
      type="button"
      class="edge-carousel-btn is-next"
      :disabled="!canNext"
      :aria-label="`Next ${label}`"
      @click="scrollByDirection(1)"
    >
      ›
    </button>
  </div>
</template>

<style scoped>
.edge-carousel {
  position: relative;
  min-width: 0;
}

.edge-carousel-btn {
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 3;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  margin: 0;
  padding: 0;
  border: 0;
  color: #111;
  font-size: 2.6rem;
  font-weight: 650;
  line-height: 1;
  text-shadow:
    0 0 10px rgba(255, 255, 255, 1),
    0 1px 0 rgba(255, 255, 255, 0.95);
  cursor: pointer;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
}

.edge-carousel:hover .edge-carousel-btn:not(:disabled),
.edge-carousel:focus-within .edge-carousel-btn:not(:disabled) {
  opacity: 1;
  pointer-events: auto;
}

.edge-carousel-btn.is-prev {
  left: 0;
  background: linear-gradient(
    to right,
    rgba(255, 255, 255, 0.96) 0%,
    rgba(255, 255, 255, 0.78) 42%,
    rgba(255, 255, 255, 0) 100%
  );
}

.edge-carousel-btn.is-next {
  right: 0;
  background: linear-gradient(
    to left,
    rgba(255, 255, 255, 0.96) 0%,
    rgba(255, 255, 255, 0.78) 42%,
    rgba(255, 255, 255, 0) 100%
  );
}

.edge-carousel-btn:disabled {
  cursor: default;
}

.edge-carousel-scroller {
  position: relative;
  z-index: 0;
  min-width: 0;
  overflow-x: auto;
  overflow-y: hidden;
  scroll-snap-type: x mandatory;
  scrollbar-width: none;
}

.edge-carousel-scroller::-webkit-scrollbar {
  display: none;
  height: 0;
}

.edge-carousel-scroller :deep(.is-edge-carousel-track) {
  overflow: visible;
  max-height: none;
  width: max-content;
  min-width: 100%;
  max-width: none;
  scrollbar-width: none;
}

.edge-carousel-scroller :deep(.is-edge-carousel-track)::-webkit-scrollbar {
  display: none;
  height: 0;
}

.edge-carousel-scroller :deep(.deck-overview-top-grid > .deck-overview-top-card) {
  flex: 0 0 140px;
  width: 140px;
  max-width: 140px;
}
</style>
