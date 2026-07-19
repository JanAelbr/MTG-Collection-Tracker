<script setup>
import { onMounted, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const visible = ref(false);
const imageUrl = ref("");
const imageUrlBack = ref("");
const showingBack = ref(false);
const tooltipStyle = ref({ left: "0px", top: "0px" });

const canFlip = ref(false);
const activeImageUrl = ref("");

function positionTooltip(event) {
  const offset = 16;
  const padding = 8;
  const width = 256;
  const height = 400;
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

function syncActiveImage() {
  activeImageUrl.value = showingBack.value && imageUrlBack.value
    ? imageUrlBack.value
    : imageUrl.value;
}

function hideTooltip() {
  visible.value = false;
  imageUrl.value = "";
  imageUrlBack.value = "";
  showingBack.value = false;
  canFlip.value = false;
  activeImageUrl.value = "";
}

function onMouseOver(event) {
  const previewEl = event.target.closest(".card-preview");
  if (!previewEl) {
    return;
  }
  const url = previewEl.getAttribute("data-image");
  if (!url) {
    return;
  }
  imageUrl.value = url;
  imageUrlBack.value = previewEl.getAttribute("data-image-back") || "";
  canFlip.value = Boolean(imageUrlBack.value);
  showingBack.value = false;
  syncActiveImage();
  visible.value = true;
  positionTooltip(event);
}

function onMouseMove(event) {
  if (!visible.value) {
    return;
  }
  if (!event.target.closest(".card-preview") && !event.target.closest(".card-image-tooltip")) {
    return;
  }
  positionTooltip(event);
}

function onMouseOut(event) {
  const previewEl = event.target.closest(".card-preview");
  const tooltipEl = event.target.closest(".card-image-tooltip");
  if (!previewEl && !tooltipEl) {
    return;
  }
  const related = event.relatedTarget;
  if (related instanceof Node) {
    if (previewEl?.contains(related) || tooltipEl?.contains(related)) {
      return;
    }
  }
  hideTooltip();
}

function onMouseDown(event) {
  if (event.target.closest(".card-image-tooltip-flip-btn")) {
    return;
  }
  if (visible.value) {
    hideTooltip();
  }
}

function toggleFace() {
  if (!canFlip.value) {
    return;
  }
  showingBack.value = !showingBack.value;
  syncActiveImage();
}

watch(
  () => router.currentRoute.value.fullPath,
  () => {
    hideTooltip();
  },
);

onMounted(() => {
  document.addEventListener("mouseover", onMouseOver);
  document.addEventListener("mousemove", onMouseMove);
  document.addEventListener("mouseout", onMouseOut);
  document.addEventListener("mousedown", onMouseDown);
  document.addEventListener("scroll", hideTooltip, true);
});

onUnmounted(() => {
  document.removeEventListener("mouseover", onMouseOver);
  document.removeEventListener("mousemove", onMouseMove);
  document.removeEventListener("mouseout", onMouseOut);
  document.removeEventListener("mousedown", onMouseDown);
  document.removeEventListener("scroll", hideTooltip, true);
});
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible && activeImageUrl"
      class="card-image-tooltip"
      :class="{ 'card-image-tooltip--flippable': canFlip }"
      :style="tooltipStyle"
    >
      <img :src="activeImageUrl" alt="">
      <button
        v-if="canFlip"
        type="button"
        class="btn btn-secondary btn-small card-image-tooltip-flip-btn"
        @click.stop="toggleFace"
      >
        {{ showingBack ? "View front" : "View back" }}
      </button>
    </div>
  </Teleport>
</template>
