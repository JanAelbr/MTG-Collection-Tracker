<script setup>
import { computed, ref, watch } from "vue";
import { api, clearClientCache } from "../api";
import LoadingIndicator from "./LoadingIndicator.vue";
import CardPreview from "./CardPreview.vue";
import { cardFinish, finishLabel } from "../utils/finishes";

const MODES = [
  {
    id: "merge",
    label: "Add / remove copies",
    hint: "Each line adds copies. Prefix - or use a negative qty to remove.",
  },
  {
    id: "set",
    label: "Set quantities",
    hint: "Set exact qty for listed cards. Unlisted cards stay unchanged.",
  },
  {
    id: "replace",
    label: "Replace section",
    hint: "Section becomes exactly this list. Cards not listed are removed.",
  },
];

const SECTIONS = [
  { id: "main", label: "Main deck" },
  { id: "commander", label: "Commander" },
  { id: "sideboard", label: "Sideboard" },
];

const props = defineProps({
  open: { type: Boolean, default: false },
  deckId: { type: String, required: true },
  deckName: { type: String, default: "" },
  deckCards: { type: Array, default: () => [] },
});

const emit = defineEmits(["close", "applied"]);

const csvText = ref("");
const mode = ref("merge");
const section = ref("main");
const preview = ref(null);
const previewError = ref("");
const previewing = ref(false);
const applying = ref(false);
const applyError = ref("");

const activeMode = computed(() => MODES.find((item) => item.id === mode.value) || MODES[0]);

const hasUnhandledChanges = computed(() => {
  if (previewing.value || applying.value) {
    return true;
  }
  if (csvText.value.trim()) {
    return true;
  }
  if (preview.value?.canApply) {
    return true;
  }
  return false;
});

const modalTitle = computed(() => {
  if (props.deckName) {
    return `Quick import — ${props.deckName}`;
  }
  return "Quick import";
});

function resetState() {
  csvText.value = "";
  mode.value = "merge";
  section.value = "main";
  preview.value = null;
  previewError.value = "";
  previewing.value = false;
  applying.value = false;
  applyError.value = "";
}

function closeModal() {
  resetState();
  emit("close");
}

function requestClose() {
  if (hasUnhandledChanges.value) {
    const message = preview.value?.canApply
      ? "You have unapplied deck changes. Close without applying?"
      : "You have unsaved import text. Close and discard it?";
    if (!window.confirm(message)) {
      return;
    }
  }
  closeModal();
}

function cardsForSection(targetSection) {
  return (props.deckCards || []).filter(
    (card) => (card.section || "main") === targetSection,
  );
}

function deckCardsToCsv(targetSection) {
  return cardsForSection(targetSection)
    .map((card) => {
      const finish = cardFinish(card);
      const qty = card.qty || 1;
      const finishPart = finish === 0 ? "" : finish;
      if (qty === 1 && finish === 0) {
        return `${card.setCode};${card.collectorNumber}`;
      }
      if (qty === 1) {
        return `${card.setCode};${card.collectorNumber};${finishPart}`;
      }
      return `${card.setCode};${card.collectorNumber};${finishPart};${qty}`;
    })
    .join("\n");
}

function loadCurrentSection() {
  csvText.value = deckCardsToCsv(section.value);
  preview.value = null;
  previewError.value = "";
  applyError.value = "";
}

function requestBody() {
  return {
    csv: csvText.value,
    mode: mode.value,
    section: section.value,
  };
}

async function validatePreview() {
  previewError.value = "";
  applyError.value = "";
  preview.value = null;
  if (!csvText.value.trim() && mode.value !== "replace") {
    previewError.value = "Paste at least one line in set;number;finish format.";
    return;
  }

  previewing.value = true;
  try {
    preview.value = await api.previewDeckCsvImport(props.deckId, requestBody());
  } catch (error) {
    previewError.value = error.message || "Preview failed.";
  } finally {
    previewing.value = false;
  }
}

async function applyChanges() {
  if (!preview.value?.canApply) {
    return;
  }
  applyError.value = "";
  applying.value = true;
  try {
    await api.applyDeckCsvImport(props.deckId, requestBody());
    clearClientCache();
    emit("applied");
    closeModal();
  } catch (error) {
    applyError.value = error.message || "Apply failed.";
  } finally {
    applying.value = false;
  }
}

function actionLabel(action) {
  switch (action) {
    case "add":
      return "Add";
    case "remove":
      return "Remove";
    case "update":
      return "Update";
    default:
      return action;
  }
}

watch(
  () => props.open,
  (open) => {
    if (!open) {
      resetState();
    }
  },
);

watch([mode, section, csvText], () => {
  preview.value = null;
  applyError.value = "";
});
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="modal-backdrop deck-csv-import-backdrop"
    >
      <div class="modal-card deck-csv-import-modal" role="dialog" aria-modal="true">
        <header class="deck-csv-import-head">
          <div>
            <h3>{{ modalTitle }}</h3>
            <p class="deck-csv-import-subtitle">
              One card per line: <code>SET;NUMBER</code>,
              <code>SET;NUMBER;FINISH</code>, or
              <code>SET;NUMBER;FINISH;QTY</code>.
              Finish is optional (defaults to non-foil).
            </p>
          </div>
          <button type="button" class="btn btn-secondary btn-small" @click="requestClose">
            Close
          </button>
        </header>

        <div class="deck-csv-import-controls">
          <label class="deck-csv-import-field">
            <span>Section</span>
            <select v-model="section">
              <option v-for="item in SECTIONS" :key="item.id" :value="item.id">
                {{ item.label }}
              </option>
            </select>
          </label>

          <label class="deck-csv-import-field deck-csv-import-field--wide">
            <span>Mode</span>
            <select v-model="mode">
              <option v-for="item in MODES" :key="item.id" :value="item.id">
                {{ item.label }}
              </option>
            </select>
          </label>

          <button
            type="button"
            class="btn btn-secondary btn-small"
            :disabled="!cardsForSection(section).length"
            @click="loadCurrentSection"
          >
            Load current
          </button>
        </div>

        <p class="deck-csv-import-mode-hint">{{ activeMode.hint }}</p>

        <textarea
          v-model="csvText"
          class="deck-csv-import-textarea"
          rows="10"
          spellcheck="false"
          placeholder="LTC;284&#10;LTR;123;1&#10;LTR;123;;2"
          aria-label="Deck card list"
        />

        <div class="deck-csv-import-actions">
          <button
            type="button"
            class="btn btn-secondary"
            :disabled="previewing || (!csvText.trim() && mode !== 'replace')"
            @click="validatePreview"
          >
            {{ previewing ? "Validating…" : "Validate & preview" }}
          </button>
        </div>

        <p v-if="previewError" class="deck-csv-import-status error">{{ previewError }}</p>
        <p v-if="applyError" class="deck-csv-import-status error">{{ applyError }}</p>

        <div v-if="previewing" class="deck-csv-import-loading">
          <LoadingIndicator label="Validating list…" />
        </div>

        <section v-else-if="preview" class="deck-csv-import-preview">
          <div class="deck-csv-import-summary">
            <span v-if="preview.summary.add">{{ preview.summary.add }} add</span>
            <span v-if="preview.summary.update">{{ preview.summary.update }} update</span>
            <span v-if="preview.summary.remove">{{ preview.summary.remove }} remove</span>
            <span v-if="preview.summary.errors">{{ preview.summary.errors }} error</span>
            <span v-if="!preview.changes.length && !preview.errors.length">No changes</span>
          </div>

          <ul v-if="preview.errors.length" class="deck-csv-import-errors">
            <li v-for="(error, index) in preview.errors" :key="`err-${index}`">
              Line {{ error.line }}: {{ error.message }}
            </li>
          </ul>

          <table v-if="preview.changes.length" class="reports-table deck-csv-import-table">
            <thead>
              <tr>
                <th>Action</th>
                <th>Card</th>
                <th>Print</th>
                <th>Finish</th>
                <th>Qty</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="change in preview.changes" :key="`${change.setCode}-${change.collectorNumber}-${change.finish}-${change.action}`">
                <td>
                  <span class="deck-csv-import-action" :class="`is-${change.action}`">
                    {{ actionLabel(change.action) }}
                  </span>
                </td>
                <td>
                  <CardPreview
                    :image-uri="change.imageUri"
                    :image-uri-back="change.imageUriBack || ''"
                  >
                    <span>{{ change.cardName }}</span>
                  </CardPreview>
                </td>
                <td>{{ change.setCode }} #{{ change.collectorNumber }}</td>
                <td>{{ finishLabel(change.finish) }}</td>
                <td>
                  <span v-if="change.action === 'add'">{{ change.newQty }}</span>
                  <span v-else-if="change.action === 'remove'">{{ change.currentQty }} → 0</span>
                  <span v-else>{{ change.currentQty }} → {{ change.newQty }}</span>
                </td>
              </tr>
            </tbody>
          </table>

          <div v-if="preview.canApply" class="deck-csv-import-apply">
            <button
              type="button"
              class="btn btn-primary"
              :disabled="applying"
              @click="applyChanges"
            >
              {{ applying ? "Applying…" : "Apply changes" }}
            </button>
          </div>
        </section>
      </div>
    </div>
  </Teleport>
</template>
