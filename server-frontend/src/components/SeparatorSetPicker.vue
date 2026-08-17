<script setup>
defineProps({
  visibleGroups: { type: Array, default: () => [] },
  setScope: { type: String, default: "loaded" },
  isSelected: { type: Function, required: true },
  allSelectedInGroup: { type: Function, required: true },
  setPickerLabel: { type: Function, required: true },
  setIconUri: { type: Function, required: true },
});

const emit = defineEmits(["toggle-select", "toggle-year", "icon-error"]);
</script>

<template>
  <div class="separators-picker">
    <p v-if="!visibleGroups.length" class="separators-page-empty">
      {{
        setScope === "loaded"
          ? "No loaded sets match this filter."
          : "No sets match this filter."
      }}
    </p>

    <section
      v-for="group in visibleGroups"
      :key="group.key"
      class="separators-year-group"
    >
      <div class="separators-year-heading-row">
        <h2 class="separators-year-heading">{{ group.label }}</h2>
        <button
          type="button"
          class="separators-year-select"
          @click="emit('toggle-year', group)"
        >
          {{ allSelectedInGroup(group) ? "Clear year" : "Select year" }}
        </button>
      </div>
      <div class="separators-set-grid">
        <button
          v-for="set in group.sets"
          :key="set.setCode"
          type="button"
          class="separators-set-tile"
          :class="{
            'is-selected': isSelected(set),
            'is-pending': set.pendingImport,
          }"
          :aria-pressed="isSelected(set) ? 'true' : 'false'"
          @click="emit('toggle-select', set)"
        >
          <input
            class="separators-set-tile-check"
            type="checkbox"
            tabindex="-1"
            :checked="isSelected(set)"
            @click.stop="emit('toggle-select', set)"
          />
          <img
            v-if="setIconUri(set)"
            class="separators-set-tile-icon"
            :src="setIconUri(set)"
            alt=""
            loading="lazy"
            @error="emit('icon-error', $event, set)"
          />
          <span class="separators-set-tile-label">
            {{ setPickerLabel(set) }}
          </span>
          <span v-if="set.pendingImport" class="separators-set-tile-badge">
            Not loaded
          </span>
        </button>
      </div>
    </section>
  </div>
</template>
