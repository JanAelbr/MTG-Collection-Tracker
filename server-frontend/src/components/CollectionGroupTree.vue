<script setup>
import DeckTypeIcon from "./DeckTypeIcon.vue";
import ManaSymbols from "./ManaSymbols.vue";
import { colorIdentityPipsFromKey, groupHasChildren } from "../utils/searchResults";
import { formatEuro, formatProfit } from "../utils/format";

defineOptions({ name: "CollectionGroupTree" });

const props = defineProps({
  groups: { type: Array, default: () => [] },
  isExpanded: { type: Function, required: true },
  setIconFor: { type: Function, default: null },
  metaTextFor: { type: Function, default: null },
});

const emit = defineEmits(["toggle"]);

function metaText(group) {
  if (typeof props.metaTextFor === "function") {
    return props.metaTextFor(group);
  }
  if (group?.metaText) {
    return group.metaText;
  }
  const count = group?.cards?.length || 0;
  return `${count} ${count === 1 ? "card" : "cards"}`;
}

function setIcon(group) {
  if (group.groupBy !== "set" || typeof props.setIconFor !== "function") {
    return "";
  }
  return props.setIconFor(group.key) || "";
}

function snapshotDeltaClass(value) {
  if (value == null || Number(value) === 0) {
    return "";
  }
  return Number(value) > 0 ? "reports-gain" : "reports-loss";
}
</script>

<template>
  <section
    v-for="group in groups"
    :key="group.path"
    class="storage-set-group"
    :class="{
      'is-collapsed': !isExpanded(group.path),
      [`storage-set-group--depth-${group.depth || 0}`]: true,
    }"
  >
    <button
      type="button"
      class="storage-set-group-header"
      :aria-expanded="isExpanded(group.path)"
      @click="emit('toggle', group.path)"
    >
      <span class="storage-set-group-chevron" aria-hidden="true">▾</span>
      <img
        v-if="setIcon(group)"
        :src="setIcon(group)"
        alt=""
        class="storage-set-group-icon"
      >
      <ManaSymbols
        v-else-if="group.groupBy === 'colorIdentity'"
        class="storage-set-group-pips"
        :colors="colorIdentityPipsFromKey(group.key)"
        :size="16"
      />
      <DeckTypeIcon
        v-else-if="group.groupBy === 'type'"
        class="storage-set-group-type-icon"
        :type="group.key"
      />
      <span
        v-else-if="group.groupBy === 'rarity'"
        class="storage-set-group-rarity"
        :class="`storage-set-group-rarity--${group.key === '__none__' ? 'unknown' : group.key}`"
        aria-hidden="true"
      />
      <h3 class="storage-set-group-title">{{ group.label }}</h3>
      <ul
        v-if="group.valueBands?.length"
        class="catalog-gallery-group-bands"
      >
        <li
          v-for="band in group.valueBands"
          :key="band.key"
          class="catalog-gallery-group-band"
          :style="{ background: band.tint }"
          :title="`${band.label}: ${band.count}`"
        >
          <span class="catalog-gallery-group-band-label">{{ band.label }}</span>
          <span class="catalog-gallery-group-band-count">{{ band.count }}</span>
        </li>
      </ul>
      <span class="storage-set-group-meta">
        {{ metaText(group) }}
        <span
          v-if="group.snapshotValueDelta != null"
          class="storage-set-group-delta"
          :class="snapshotDeltaClass(group.snapshotValueDelta)"
          :title="`Saved ${formatEuro(group.snapshotCurrent)}`"
        >
          {{ formatProfit(group.snapshotValueDelta) }}
        </span>
      </span>
    </button>

    <div v-if="isExpanded(group.path)" class="storage-set-group-body">
      <CollectionGroupTree
        v-if="groupHasChildren(group)"
        :groups="group.groups"
        :is-expanded="isExpanded"
        :set-icon-for="setIconFor"
        :meta-text-for="metaTextFor"
        @toggle="emit('toggle', $event)"
      >
        <template #leaf="slotProps">
          <slot name="leaf" v-bind="slotProps" />
        </template>
      </CollectionGroupTree>
      <slot
        v-else
        name="leaf"
        :group="group"
      />
    </div>
  </section>
</template>
