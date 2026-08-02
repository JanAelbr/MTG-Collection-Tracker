<script setup>
import "../styles/print-cards.css";
import { computed } from "vue";

import { usePrintList } from "../composables/printList";
import { cardSelectionKey } from "../utils/collectionScopeStats";
import { cardFinish } from "../utils/finishes";

const printList = usePrintList();

const listCards = computed(() => printList.items.value);
const selectedCards = computed(() => printList.selectedCards.value);
const listSelectedKeys = computed(() => printList.selectedKeys.value);
const listCount = computed(() => printList.count.value);
const selectedCount = computed(() => printList.selectedCount.value);

function clearList() {
  printList.clear();
}

function removeFromList(card) {
  printList.remove(card);
}

function togglePrintSelected(card) {
  printList.toggleSelected(card);
}

function selectAllForPrint() {
  printList.selectAll();
}

function clearPrintSelection() {
  printList.clearSelection();
}

function printCards() {
  if (!selectedCards.value.length) {
    return;
  }
  window.print();
}

function printTileKey(card) {
  return `print-${card.setCode}-${card.collectorNumber}-${cardFinish(card)}`;
}
</script>

<template>
  <div class="print-cards-page collection-page">
    <div class="print-cards-no-print">
      <header class="print-cards-page-header">
        <h1>Print cards</h1>
        <p class="print-cards-page-intro">
          Right-click any card in collection, search, storage, decks, or set views and choose
          <strong>Add to print list</strong>. Cards you add show up here — select which ones to include,
          then print or save as PDF.
        </p>
      </header>

      <div class="print-cards-page-toolbar">
        <div class="print-cards-page-actions">
          <span v-if="listCount" class="print-cards-page-selection-count">
            {{ selectedCount }} of {{ listCount }} selected
          </span>
          <button
            type="button"
            class="btn btn-secondary btn-small"
            :disabled="!listCount"
            @click="selectAllForPrint"
          >
            Select all
          </button>
          <button
            type="button"
            class="btn btn-secondary btn-small"
            :disabled="!selectedCount"
            @click="clearPrintSelection"
          >
            Clear selection
          </button>
          <button
            type="button"
            class="btn btn-secondary btn-small"
            :disabled="!listCount"
            @click="clearList"
          >
            Clear list
          </button>
          <button
            type="button"
            class="btn btn-primary btn-small"
            :disabled="!selectedCount"
            @click="printCards"
          >
            Print / Save PDF
          </button>
        </div>
      </div>

      <section class="print-cards-queue" aria-label="Print list">
        <h2 class="print-cards-queue-heading">Print list</h2>
        <p v-if="!listCards.length" class="print-cards-preview-empty">
          Your print list is empty. Browse to a card elsewhere in the app, open its context menu
          (right-click), and pick <strong>Add to print list</strong>.
        </p>
        <div v-else class="print-cards-list" role="list">
          <div
            v-for="card in listCards"
            :key="cardSelectionKey(card)"
            class="print-cards-list-item"
            role="listitem"
            :class="{ 'is-selected': listSelectedKeys.has(cardSelectionKey(card)) }"
          >
            <input
              type="checkbox"
              class="print-cards-list-checkbox"
              :checked="listSelectedKeys.has(cardSelectionKey(card))"
              :aria-label="`Include ${printList.displayLabel(card)} in print`"
              @click.prevent="togglePrintSelected(card)"
            />
            <button
              type="button"
              class="print-cards-thumb print-cards-list-thumb"
              :title="printList.displayLabel(card)"
              @click="togglePrintSelected(card)"
            >
              <img
                v-if="card.imageUri"
                :src="card.imageUri"
                :alt="printList.displayLabel(card)"
                loading="lazy"
              />
              <span v-else class="print-cards-thumb-fallback">{{ printList.displayLabel(card) }}</span>
            </button>
            <button
              type="button"
              class="print-cards-list-remove"
              :aria-label="`Remove ${printList.displayLabel(card)} from print list`"
              title="Remove from list"
              @click="removeFromList(card)"
            >
              ×
            </button>
          </div>
        </div>
      </section>
    </div>

    <div class="print-cards-print-sheet" aria-hidden="true">
      <div
        v-for="card in selectedCards"
        :key="printTileKey(card)"
        class="print-cards-print-tile"
      >
        <img
          v-if="card.imageUri"
          :src="card.imageUri"
          :alt="printList.displayLabel(card)"
        />
        <div v-else class="print-cards-print-fallback">
          {{ printList.displayLabel(card) }}
        </div>
      </div>
    </div>
  </div>
</template>
