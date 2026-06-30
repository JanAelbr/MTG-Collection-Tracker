<script setup>
import { ref } from "vue";
import { formatUnknownCardLine } from "../utils/format";

const props = defineProps({
  cards: { type: Array, default: () => [] },
});

const show = ref(false);
const tooltipStyle = ref({ left: "0px", top: "0px" });

function positionTooltip(event) {
  const offset = 16;
  const padding = 8;
  const width = 320;
  const height = 240;
  let left = event.clientX + offset;
  let top = event.clientY + offset;
  if (left + width + padding > window.innerWidth) {
    left = event.clientX - width - offset;
  }
  if (top + height + padding > window.innerHeight) {
    top = event.clientY - height - offset;
  }
  left = Math.max(padding, Math.min(left, window.innerWidth - width - padding));
  top = Math.max(padding, Math.min(top, window.innerHeight - height - padding));
  tooltipStyle.value = { left: `${left}px`, top: `${top}px` };
}

function onEnter(event) {
  if (!props.cards.length) {
    return;
  }
  show.value = true;
  positionTooltip(event);
}

function onMove(event) {
  if (show.value) {
    positionTooltip(event);
  }
}

function onLeave() {
  show.value = false;
}
</script>

<template>
  <div
    class="stats-card stats-card-unknown unknown-cards-trigger"
    :class="{ 'has-unknown-tooltip': cards.length }"
    @mouseenter="onEnter"
    @mousemove="onMove"
    @mouseleave="onLeave"
  >
    <slot />
    <Teleport to="body">
      <div
        v-if="show && cards.length"
        class="unknown-cards-tooltip"
        :style="tooltipStyle"
      >
        <ul>
          <li v-for="(card, index) in cards" :key="`${card.set_code}-${card.collector_number}-${index}`">
            {{ formatUnknownCardLine(card) }}
          </li>
        </ul>
      </div>
    </Teleport>
  </div>
</template>
