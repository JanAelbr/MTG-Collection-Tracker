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
  moveArtStyleRule,
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
  rows.value = [...rows.value, createEmptyArtStyleRuleRow()];
}

function duplicateRule(index) {
  const source = rows.value[index];
  const copy = artStyleRuleFromApi(artStyleRuleToApiSafe(source));
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

function moveRule(index, direction) {
  rows.value = moveArtStyleRule(rows.value, index, direction);
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
            <tr v-for="(row, index) in rows" :key="row.id">
              <td class="art-style-rules-order">
                <button
                  type="button"
                  class="btn btn-secondary btn-small"
                  :disabled="index === 0"
                  aria-label="Move up"
                  @click="moveRule(index, -1)"
                >
                  ↑
                </button>
                <button
                  type="button"
                  class="btn btn-secondary btn-small"
                  :disabled="index === rows.length - 1"
                  aria-label="Move down"
                  @click="moveRule(index, 1)"
                >
                  ↓
                </button>
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
                  <label>
                    Prefix
                    <input
                      v-model="row.prefix"
                      type="text"
                      class="art-style-rules-input"
                      placeholder="A-"
                    />
                  </label>
                </div>
                <div v-else class="art-style-rules-detail-fields">
                  <label>
                    From
                    <input
                      v-model="row.firstNumber"
                      type="number"
                      class="art-style-rules-input art-style-rules-input--number"
                      min="0"
                    />
                  </label>
                  <label>
                    To
                    <input
                      v-model="row.lastNumber"
                      type="number"
                      class="art-style-rules-input art-style-rules-input--number"
                      min="0"
                    />
                  </label>
                  <label v-if="row.matchType === 'range_suffix'">
                    Suffix
                    <input
                      v-model="row.suffix"
                      type="text"
                      class="art-style-rules-input"
                      placeholder="z"
                    />
                  </label>
                </div>
              </td>
              <td class="art-style-rules-actions">
                <button
                  type="button"
                  class="btn btn-secondary btn-small"
                  aria-label="Duplicate rule"
                  @click="duplicateRule(index)"
                >
                  Copy
                </button>
                <button
                  type="button"
                  class="btn btn-secondary btn-small"
                  :disabled="rows.length <= 1"
                  aria-label="Remove rule"
                  @click="removeRule(index)"
                >
                  Remove
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="art-style-rules-footer">
        <button type="button" class="btn btn-secondary" @click="addRule">
          Add rule
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
