<script setup>
import { computed } from "vue";
import { collectionRouteForSet } from "../utils/setScope";

const props = defineProps({
  setCode: { type: String, default: "" },
  artStyle: { type: String, default: "" },
  label: { type: String, default: "" },
});

const to = computed(() => collectionRouteForSet(props.setCode, props.artStyle));
const displayLabel = computed(() => props.label || props.setCode);
const hasSet = computed(() => Boolean(String(props.setCode || "").trim()));
</script>

<template>
  <RouterLink
    v-if="hasSet"
    :to="to"
    class="collection-set-link"
  >
    {{ displayLabel }}
  </RouterLink>
  <span v-else>—</span>
</template>
