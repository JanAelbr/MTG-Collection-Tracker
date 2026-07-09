<script setup>
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  effectiveDeckOwnedQty,
  isEffectivelyOwned,
  normalizeCardMenuTarget,
  ownershipRevision,
} from "../composables/cardContextMenu";
import CardCopyControls from "./CardCopyControls.vue";
import { cardFinish, cardRouteQuery } from "../utils/finishes";

const props = defineProps({
  src: { type: String, default: "" },
  alt: { type: String, default: "" },
  card: { type: Object, default: null },
  imgClass: { type: [String, Array, Object], default: "" },
  loading: { type: String, default: "lazy" },
  showDetails: { type: Boolean, default: true },
});

const emit = defineEmits(["finish-changed", "ownership-changed"]);

const router = useRouter();
const rootRef = ref(null);
const isHovered = ref(false);
const hoverPinned = ref(false);
const copyControlsRef = ref(null);
let leaveTimer = null;

const isInteractive = computed(() => Boolean(props.card && props.src && normalizeCardMenuTarget(props.card)));
const ownedCount = computed(() => {
  ownershipRevision.value;
  return effectiveDeckOwnedQty(props.card);
});
const canClickToAdd = computed(() => isInteractive.value && ownedCount.value === 0);
const showOverlay = computed(() => isInteractive.value && (isHovered.value || hoverPinned.value));
const effectivelyOwned = computed(() => {
  ownershipRevision.value;
  return isEffectivelyOwned(props.card);
});

watch(
  () => [
    props.card?.setCode,
    props.card?.set_code,
    props.card?.collectorNumber,
    props.card?.collector_number,
    props.card?.finish,
  ],
  () => {
    if (!isHovered.value) {
      return;
    }
  },
);

function clearLeaveTimer() {
  if (leaveTimer) {
    clearTimeout(leaveTimer);
    leaveTimer = null;
  }
}

function pinHover() {
  if (!isInteractive.value) {
    return;
  }
  hoverPinned.value = true;
  clearLeaveTimer();
  isHovered.value = true;
}

function onPointerEnter() {
  if (!isInteractive.value) {
    return;
  }
  clearLeaveTimer();
  isHovered.value = true;
}

function onPointerLeave(event) {
  const root = rootRef.value;
  const related = event.relatedTarget;
  if (related instanceof Node && root?.contains(related)) {
    return;
  }
  clearLeaveTimer();
  leaveTimer = setTimeout(() => {
    hoverPinned.value = false;
    isHovered.value = false;
  }, 220);
}

function onOverlayClick(event) {
  event.preventDefault();
  event.stopPropagation();
  if (canClickToAdd.value) {
    copyControlsRef.value?.addCopy();
  }
}

function onCardClick(event) {
  if (!canClickToAdd.value) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  copyControlsRef.value?.addCopy();
}

function stopNavigation(event) {
  event.preventDefault();
  event.stopPropagation();
}

function onViewDetails(event) {
  event.preventDefault();
  event.stopPropagation();
  const target = normalizeCardMenuTarget(props.card);
  if (!target) {
    return;
  }
  router.push({
    name: "card",
    params: { setCode: target.setCode, collectorNumber: target.collectorNumber },
    query: cardRouteQuery(cardFinish(props.card)),
  });
}
</script>

<template>
  <div
    v-if="src"
    ref="rootRef"
    class="card-interactive"
    :class="{
      'is-interactive': isInteractive,
      'is-hovered': showOverlay,
      'is-owned': effectivelyOwned,
      'is-unowned': isInteractive && !effectivelyOwned,
      'is-clickable-add': canClickToAdd,
    }"
    @click="onCardClick"
    @pointerenter="onPointerEnter"
    @pointerleave="onPointerLeave"
  >
    <img
      :src="src"
      :alt="alt"
      :loading="loading"
      :class="['card-interactive-image', imgClass]"
    >

    <div
      v-if="showOverlay"
      class="card-interactive-overlay"
      @pointerdown="pinHover"
      @click.stop="onOverlayClick"
      @mousedown.stop="stopNavigation"
    >
      <button
        v-if="showDetails"
        type="button"
        class="card-interactive-action card-interactive-details"
        @click="onViewDetails"
      >
        Details
      </button>

      <CardCopyControls
        ref="copyControlsRef"
        :card="card"
        :visible="showOverlay"
        variant="overlay"
        @finish-changed="emit('finish-changed', $event)"
        @ownership-changed="emit('ownership-changed')"
      />
    </div>
  </div>
</template>
