<script setup>
import { computed } from "vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: "Confirm" },
  message: { type: String, default: "" },
  confirmLabel: { type: String, default: "Confirm" },
  cancelLabel: { type: String, default: "Cancel" },
  danger: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
});

const emit = defineEmits(["confirm", "cancel"]);

const confirmButtonClass = computed(() =>
  props.danger ? "btn btn-danger" : "btn btn-primary",
);

function onCancel() {
  if (props.busy) {
    return;
  }
  emit("cancel");
}

function onConfirm() {
  if (props.busy) {
    return;
  }
  emit("confirm");
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="modal-backdrop confirm-modal-backdrop"
      role="presentation"
      @click.self="onCancel"
    >
      <div
        class="modal-card confirm-modal"
        role="alertdialog"
        aria-modal="true"
        :aria-labelledby="'confirm-modal-title'"
        :aria-describedby="message ? 'confirm-modal-message' : undefined"
        @keydown.esc.stop="onCancel"
      >
        <h3 id="confirm-modal-title">{{ title }}</h3>
        <p
          v-if="message"
          id="confirm-modal-message"
          class="confirm-modal-message"
        >
          {{ message }}
        </p>
        <div class="modal-actions">
          <button
            type="button"
            class="btn btn-secondary"
            :disabled="busy"
            @click="onCancel"
          >
            {{ cancelLabel }}
          </button>
          <button
            type="button"
            :class="confirmButtonClass"
            :disabled="busy"
            @click="onConfirm"
          >
            {{ busy ? "Working…" : confirmLabel }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
