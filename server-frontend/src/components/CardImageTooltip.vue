<script setup>
import { onMounted, onUnmounted, ref } from "vue";

const visible = ref(false);
const imageUrl = ref("");
const tooltipStyle = ref({ left: "0px", top: "0px" });

function positionTooltip(event) {
  const offset = 16;
  const padding = 8;
  const width = 256;
  const height = 360;
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

function hideTooltip() {
  visible.value = false;
  imageUrl.value = "";
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
  visible.value = true;
  positionTooltip(event);
}

function onMouseMove(event) {
  if (!visible.value) {
    return;
  }
  if (!event.target.closest(".card-preview")) {
    return;
  }
  positionTooltip(event);
}

function onMouseOut(event) {
  const previewEl = event.target.closest(".card-preview");
  if (!previewEl) {
    return;
  }
  const related = event.relatedTarget;
  if (related && previewEl.contains(related)) {
    return;
  }
  hideTooltip();
}

onMounted(() => {
  document.addEventListener("mouseover", onMouseOver);
  document.addEventListener("mousemove", onMouseMove);
  document.addEventListener("mouseout", onMouseOut);
});

onUnmounted(() => {
  document.removeEventListener("mouseover", onMouseOver);
  document.removeEventListener("mousemove", onMouseMove);
  document.removeEventListener("mouseout", onMouseOut);
});
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible && imageUrl"
      class="card-image-tooltip"
      :style="tooltipStyle"
    >
      <img :src="imageUrl" alt="">
    </div>
  </Teleport>
</template>
