<script setup>
import { computed, ref, watch } from "vue";
import { api } from "../api";
import LoadingIndicator from "./LoadingIndicator.vue";
import {
  ART_STYLE_MATCH_TYPES,
  artStyleRuleFromApi,
  artStyleRulesFromApi,
  artStyleRulesToApi,
  createEmptyArtStyleRuleRow,
  nextArtStyleLabelPrefix,
  reorderArtStyleRules,
} from "../utils/artStyleRules";

const props = defineProps({
  setCode: { type: String, default: "" },
  open: { type: Boolean, default: false },
});

const emit = defineEmits(["update:open", "saved"]);

const loading = ref(false);
const saving = ref(false);
const errorMessage = ref("");
const successMessage = ref("");
const rows = ref([]);
const dragFromIndex = ref(null);
const dragOverIndex = ref(null);

const canSave = computed(() => Boolean(props.setCode) && rows.value.length > 0 && !saving.value);

async function loadRules() {
  if (!props.setCode) {
    rows.value = [];
    return;
  }
  loading.value = true;
  errorMessage.value = "";
  successMessage.value = "";
  try {
    const payload = await api.getManagerArtStyleRules(props.setCode);
    rows.value = artStyleRulesFromApi(payload.rules);
    if (!rows.value.length) {
      rows.value = [createEmptyArtStyleRuleRow({ name: "All", matchType: "all" })];
    }
  } catch (error) {
    errorMessage.value = error.message || "Could not load art style rules.";
    rows.value = [createEmptyArtStyleRuleRow({ name: "All", matchType: "all" })];
  } finally {
    loading.value = false;
  }
}

function closePanel() {
  emit("update:open", false);
}

function addRule() {
  rows.value = [
    ...rows.value,
    createEmptyArtStyleRuleRow({
      name: nextArtStyleLabelPrefix(rows.value),
    }),
  ];
}

function duplicateRule(index) {
  const source = rows.value[index];
  const copy = artStyleRuleFromApi(artStyleRuleToApiSafe(source));
  copy.name = nextArtStyleLabelPrefix(rows.value);
  rows.value = [
    ...rows.value.slice(0, index + 1),
    copy,
    ...rows.value.slice(index + 1),
  ];
}

function artStyleRuleToApiSafe(row) {
  try {
    return artStyleRulesToApi([row])[0];
  } catch {
    return {
      name: row.name,
      firstNumber: row.firstNumber,
      lastNumber: row.lastNumber,
      prefix: row.prefix,
      suffix: row.suffix,
      all: row.matchType === "all" ? true : undefined,
    };
  }
}

function removeRule(index) {
  if (rows.value.length <= 1) {
    return;
  }
  rows.value = rows.value.filter((_, rowIndex) => rowIndex !== index);
}

function onDragStart(index, event) {
  dragFromIndex.value = index;
  dragOverIndex.value = index;
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", String(index));
  if (event.dataTransfer.setDragImage && event.currentTarget?.closest) {
    const row = event.currentTarget.closest("tr");
    if (row) {
      event.dataTransfer.setDragImage(row, 24, 16);
    }
  }
}

function onDragOver(index, event) {
  event.preventDefault();
  event.dataTransfer.dropEffect = "move";
  if (dragOverIndex.value !== index) {
    dragOverIndex.value = index;
  }
}

function onDrop(index, event) {
  event.preventDefault();
  const fromIndex = dragFromIndex.value;
  rows.value = reorderArtStyleRules(rows.value, fromIndex, index);
  clearDragState();
}

function clearDragState() {
  dragFromIndex.value = null;
  dragOverIndex.value = null;
}

async function saveRules() {
  if (!props.setCode) {
    return;
  }
  saving.value = true;
  errorMessage.value = "";
  successMessage.value = "";
  try {
    const rules = artStyleRulesToApi(rows.value);
    const result = await api.saveManagerArtStyleRules(props.setCode, rules);
    rows.value = artStyleRulesFromApi(result.rules);
    successMessage.value = `Saved ${result.updatedCards ?? 0} card labels.`;
    emit("saved", result);
  } catch (error) {
    errorMessage.value = error.message || "Could not save art style rules.";
  } finally {
    saving.value = false;
  }
}

watch(
  () => [props.open, props.setCode],
  ([open, setCode]) => {
    if (open && setCode) {
      loadRules();
    }
  },
  { immediate: true },
);
</script>

<template>
  <section v-if="open" class="art-style-rules-panel">
    <div class="art-style-rules-header">
      <div>
        <h2>Art style rules</h2>
        <p class="art-style-rules-help">
          Group cards into art styles for filters and stats. Rules are checked top to bottom;
          put specific matches like prefixes or serialized suffixes before broad number ranges.
          Drag rows to reorder.
        </p>
      </div>
      <button type="button" class="btn btn-secondary btn-small" @click="closePanel">
        Close
      </button>
    </div>

    <LoadingIndicator v-if="loading" compact label="Loading rules…" />

    <template v-else>
      <div class="art-style-rules-table-wrap">
        <table class="art-style-rules-table">
          <thead>
            <tr>
              <th aria-label="Reorder"></th>
              <th>Label</th>
              <th>Match</th>
              <th>Details</th>
              <th aria-label="Actions"></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, index) in rows"
              :key="row.id"
              class="art-style-rules-row"
              :class="{
                'art-style-rules-row--dragging': dragFromIndex === index,
                'art-style-rules-row--drop-target': dragOverIndex === index && dragFromIndex !== index,
              }"
              @dragover="onDragOver(index, $event)"
              @drop="onDrop(index, $event)"
              @dragend="clearDragState"
            >
              <td class="art-style-rules-order">
                <span
                  class="art-style-rules-icon-btn art-style-rules-drag-handle"
                  draggable="true"
                  title="Drag to reorder"
                  role="button"
                  tabindex="0"
                  aria-label="Drag to reorder"
                  @dragstart="onDragStart(index, $event)"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                    <circle cx="9" cy="7" r="1.5" fill="currentColor" />
                    <circle cx="15" cy="7" r="1.5" fill="currentColor" />
                    <circle cx="9" cy="12" r="1.5" fill="currentColor" />
                    <circle cx="15" cy="12" r="1.5" fill="currentColor" />
                    <circle cx="9" cy="17" r="1.5" fill="currentColor" />
                    <circle cx="15" cy="17" r="1.5" fill="currentColor" />
                  </svg>
                </span>
              </td>
              <td>
                <input
                  v-model="row.name"
                  type="text"
                  class="art-style-rules-input"
                  placeholder="01. Main set"
                />
              </td>
              <td>
                <select v-model="row.matchType" class="art-style-rules-select">
                  <option
                    v-for="option in ART_STYLE_MATCH_TYPES"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select>
              </td>
              <td>
                <div v-if="row.matchType === 'all'" class="art-style-rules-detail-muted">
                  Every card in this set
                </div>
                <div v-else-if="row.matchType === 'prefix'" class="art-style-rules-detail-fields">
                  <input
                    v-model="row.prefix"
                    type="text"
                    class="art-style-rules-input"
                    placeholder="Prefix"
                    aria-label="Prefix"
                  />
                </div>
                <div v-else class="art-style-rules-detail-fields">
                  <input
                    v-model="row.firstNumber"
                    type="number"
                    class="art-style-rules-input art-style-rules-input--number"
                    min="0"
                    placeholder="From"
                    aria-label="From"
                  />
                  <input
                    v-model="row.lastNumber"
                    type="number"
                    class="art-style-rules-input art-style-rules-input--number"
                    min="0"
                    placeholder="To"
                    aria-label="To"
                  />
                  <input
                    v-if="row.matchType === 'range_suffix'"
                    v-model="row.suffix"
                    type="text"
                    class="art-style-rules-input art-style-rules-input--suffix"
                    placeholder="Suffix"
                    aria-label="Suffix"
                  />
                </div>
              </td>
              <td class="art-style-rules-actions">
                <button
                  type="button"
                  class="art-style-rules-icon-btn"
                  title="Copy rule"
                  aria-label="Copy rule"
                  @click="duplicateRule(index)"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                    <rect
                      x="8"
                      y="8"
                      width="11"
                      height="11"
                      rx="2"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="1.8"
                    />
                    <path
                      d="M6 16V6a2 2 0 0 1 2-2h10"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="1.8"
                      stroke-linecap="round"
                    />
                  </svg>
                </button>
                <button
                  type="button"
                  class="art-style-rules-icon-btn art-style-rules-icon-btn--danger"
                  title="Remove rule"
                  aria-label="Remove rule"
                  :disabled="rows.length <= 1"
                  @click="removeRule(index)"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                    <path
                      d="M5 7h14"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="1.8"
                      stroke-linecap="round"
                    />
                    <path
                      d="M10 11v6M14 11v6"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="1.8"
                      stroke-linecap="round"
                    />
                    <path
                      d="M8 7l1-2h6l1 2v12a2 2 0 0 1-2 2H10a2 2 0 0 1-2-2V7z"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="1.8"
                      stroke-linejoin="round"
                    />
                  </svg>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="art-style-rules-footer">
        <button
          type="button"
          class="art-style-rules-icon-btn art-style-rules-icon-btn--add"
          title="Add rule"
          aria-label="Add rule"
          @click="addRule"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path
              d="M12 5v14M5 12h14"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
            />
          </svg>
          <span>Add rule</span>
        </button>
        <div class="art-style-rules-footer-actions">
          <p
            v-if="errorMessage"
            class="collection-sync-message error"
          >
            {{ errorMessage }}
          </p>
          <p
            v-else-if="successMessage"
            class="collection-sync-message"
          >
            {{ successMessage }}
          </p>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="!canSave"
            @click="saveRules"
          >
            {{ saving ? "Saving…" : "Save art styles" }}
          </button>
        </div>
      </div>
    </template>
  </section>
</template>
