<script setup>
defineProps({
  selectedSnapshotId: { type: [Number, String, null], default: null },
  snapshotList: { type: Array, default: () => [] },
  snapshotOptionLabel: { type: Function, required: true },
});

const emit = defineEmits(["change"]);
</script>

<template>
  <label class="storage-breakdown-select">
    <span class="visually-hidden">Saved breakdown</span>
    <select
      :value="selectedSnapshotId ?? ''"
      aria-label="Saved breakdown"
      @change="emit('change', $event)"
    >
      <option value="">Live current</option>
      <option
        v-for="snapshot in snapshotList"
        :key="snapshot.id"
        :value="snapshot.id"
      >
        {{ snapshotOptionLabel(snapshot) }}
      </option>
    </select>
  </label>
</template>
