<script setup>
import ConfirmModal from "./ConfirmModal.vue";
import {
  acceptConfirmDialog,
  cancelConfirmDialog,
  useConfirmDialogState,
} from "../composables/confirmDialog";

const state = useConfirmDialogState();
</script>

<template>
  <ConfirmModal
    :open="state.open"
    :title="state.title"
    :message="state.message"
    :confirm-label="state.confirmLabel"
    :cancel-label="state.cancelLabel"
    :danger="state.danger"
    :busy="state.busy"
    @confirm="acceptConfirmDialog"
    @cancel="cancelConfirmDialog"
  />
</template>
