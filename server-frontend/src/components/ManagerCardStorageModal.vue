<script setup>
import { computed } from "vue";
import CardOwnedQtyControl from "./CardOwnedQtyControl.vue";
import { finishLabel } from "../utils/finishes";

const props = defineProps({
  open: { type: Boolean, default: false },
  card: { type: Object, default: null },
  finish: { type: Number, default: 0 },
});

const emit = defineEmits(["close", "saved"]);

const modalCard = computed(() => {
  if (!props.card) {
    return null;
  }
  return {
    ...props.card,
    finish: props.finish,
    foil: props.finish,
  };
});

const title = computed(() => {
  const name = props.card?.name || "Card";
  return `${name} — ${finishLabel(props.finish)} storage`;
});

function onOwnershipChanged() {
  emit("saved");
}

function onClose() {
  emit("close");
}
</script>

<template>
  <div
    v-if="open && modalCard"
    class="modal-backdrop manager-storage-modal-backdrop"
    @click.self="onClose"
  >
    <div class="modal-card manager-storage-modal" role="dialog" aria-modal="true">
      <h3>{{ title }}</h3>
      <CardOwnedQtyControl :card="modalCard" @ownership-changed="onOwnershipChanged" />
      <div class="modal-actions">
        <button type="button" class="btn btn-secondary" @click="onClose">
          Close
        </button>
      </div>
    </div>
  </div>
</template>
