<script setup>
defineProps({
  open: { type: Boolean, default: false },
});

const emit = defineEmits(["close"]);
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="collection-filter-sheet-backdrop"
      @click.self="emit('close')"
    >
      <div class="collection-filter-sheet" role="dialog" aria-label="Collection filters">
        <div class="collection-filter-sheet-header">
          <h2>Filters</h2>
          <button type="button" class="btn btn-secondary btn-small" @click="emit('close')">
            Done
          </button>
        </div>
        <div class="collection-filter-sheet-body">
          <slot />
        </div>
      </div>
    </div>
  </Teleport>
</template>
