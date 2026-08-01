<script setup>
import { computed } from "vue";

import CardSetSymbol from "./CardSetSymbol.vue";
import {
  DEFAULT_STORAGE_SEPARATOR_STYLE,
  formatStorageMetaLine,
  normalizeStorageSeparatorStyle,
  storageSeparatorClassNames,
  storageStyleToCssVars,
} from "../utils/storageSeparatorStyle";

const props = defineProps({
  setCode: { type: String, default: "" },
  familyRoot: { type: String, default: "" },
  setName: { type: String, default: "" },
  year: { type: String, default: "" },
  styleSettings: {
    type: Object,
    default: () => ({ ...DEFAULT_STORAGE_SEPARATOR_STYLE }),
  },
});

const style = computed(() => normalizeStorageSeparatorStyle(props.styleSettings));

const metaLine = computed(() =>
  formatStorageMetaLine(props.year, props.setCode, style.value.metaFormat),
);

const rootStyle = computed(() => storageStyleToCssVars(style.value));
const rootClass = computed(() => storageSeparatorClassNames(style.value));

const iconPx = computed(() => {
  if (style.value.iconScale === "sm") {
    return 28;
  }
  if (style.value.iconScale === "md") {
    return 40;
  }
  return 48;
});
</script>

<template>
  <article
    class="storage-separator"
    :class="rootClass"
    aria-label="Storage separator"
    :style="rootStyle"
  >
    <header class="storage-separator-tab">
      <CardSetSymbol
        v-if="style.showIcon"
        class="storage-separator-icon"
        :set-code="setCode"
        :family-root="familyRoot"
        variant="generic"
        :size="iconPx"
      />
      <div class="storage-separator-text">
        <span class="storage-separator-name">{{ setName }}</span>
        <span v-if="metaLine" class="storage-separator-meta">{{ metaLine }}</span>
      </div>
    </header>
    <div class="storage-separator-body" />
  </article>
</template>
