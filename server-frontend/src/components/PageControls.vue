<script setup>
import { computed } from "vue";
import { buildPageNumbers } from "../utils/pagination";

const props = defineProps({
  page: { type: Number, required: true },
  totalPages: { type: Number, required: true },
});

const emit = defineEmits(["update:page"]);

const pageItems = computed(() => buildPageNumbers(props.page, props.totalPages));

function goTo(page) {
  if (page < 1 || page > props.totalPages || page === props.page) {
    return;
  }
  emit("update:page", page);
}
</script>

<template>
  <nav class="page-controls" aria-label="Pagination">
    <button
      type="button"
      class="btn btn-secondary btn-small"
      :disabled="page <= 1"
      @click="goTo(page - 1)"
    >
      Previous
    </button>

    <div class="page-controls-pages">
      <template v-for="(item, index) in pageItems" :key="`${item}-${index}`">
        <span v-if="item === 'ellipsis'" class="page-controls-ellipsis" aria-hidden="true">…</span>
        <button
          v-else
          type="button"
          class="page-controls-page"
          :class="{ active: item === page }"
          :aria-current="item === page ? 'page' : undefined"
          @click="goTo(item)"
        >
          {{ item }}
        </button>
      </template>
    </div>

    <button
      type="button"
      class="btn btn-secondary btn-small"
      :disabled="page >= totalPages"
      @click="goTo(page + 1)"
    >
      Next
    </button>
  </nav>
</template>
