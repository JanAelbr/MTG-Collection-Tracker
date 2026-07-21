<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { api, clearClientCache } from "../api";
import { useDeckRename } from "../composables/useDeckRename";
import {
  deckCardImageUri,
  getGalleryCommanders,
  sortDecksForGallery,
} from "../utils/deckBrowse";
import { cardDisplayName } from "../utils/finishes";
import { formatDeckOwned, formatDeckValueRange, formatEuro } from "../utils/format";

const props = defineProps({
  decks: { type: Array, default: () => [] },
  pages: { type: Object, default: () => ({}) },
  activeDeckId: { type: String, default: "" },
  sortBy: { type: String, default: "year" },
  onRenamed: { type: Function, default: null },
  onDeleted: { type: Function, default: null },
});

const emit = defineEmits(["select", "create"]);

const galleryRef = ref(null);

const sortedDecks = computed(() =>
  sortDecksForGallery(props.decks, props.pages, props.sortBy),
);

const activeDeck = computed(
  () => props.decks.find((deck) => String(deck.id) === String(props.activeDeckId)) || null,
);

const {
  renaming,
  draft,
  error: renameError,
  saving: renameSaving,
  inputRef: renameInputRef,
  startRename,
  cancelRename,
  onRenameBlur,
  saveRename,
} = useDeckRename(
  () => props.activeDeckId,
  () => activeDeck.value?.name || "",
  (updatedDeck) => props.onRenamed?.(updatedDeck),
);

const deleting = ref(false);

async function deleteActiveDeck() {
  if (!props.activeDeckId || deleting.value || renaming.value) {
    return;
  }
  const deckName = activeDeck.value?.name || "this deck";
  if (!window.confirm(`Delete "${deckName}"? This cannot be undone.`)) {
    return;
  }
  deleting.value = true;
  try {
    await api.deleteDeck(props.activeDeckId);
    clearClientCache();
    await props.onDeleted?.(props.activeDeckId);
  } catch (err) {
    window.alert(err?.message || "Could not delete deck.");
  } finally {
    deleting.value = false;
  }
}

function deckStats(deck) {
  return props.pages[String(deck.id)] || {};
}

function deckCards(deck) {
  const stats = deckStats(deck);
  if (Array.isArray(stats.cards) && stats.cards.length) {
    return stats.cards;
  }
  return stats.previewCards || [];
}

function deckValueLabel(deck) {
  const stats = deckStats(deck);
  if (stats.ownedCurrent != null && stats.current != null) {
    return formatDeckValueRange(stats.ownedCurrent, stats.current);
  }
  return formatEuro(stats.current);
}

function deckOwnedLabel(deck) {
  const stats = deckStats(deck);
  return formatDeckOwned(stats.ownedQty, stats.deckSize);
}

function commandersFor(deck) {
  return getGalleryCommanders(deckCards(deck));
}

function isActiveDeck(deck) {
  return String(deck.id) === String(props.activeDeckId);
}

function selectDeck(deckId) {
  emit("select", String(deckId));
}

function onCardKeydown(event, deckId) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    selectDeck(deckId);
  }
}

function scrollActiveIntoView(behavior = "smooth") {
  nextTick(() => {
    const root = galleryRef.value;
    if (!root || !props.activeDeckId) {
      return;
    }
    const active = root.querySelector(".deck-gallery-card.active");
    if (!active) {
      return;
    }
    const rootRect = root.getBoundingClientRect();
    const activeRect = active.getBoundingClientRect();
    const activeCenter = activeRect.left - rootRect.left + root.scrollLeft + activeRect.width / 2;
    const targetScroll = activeCenter - root.clientWidth / 2;
    root.scrollTo({
      left: Math.max(0, targetScroll),
      behavior: behavior === "auto" ? "auto" : behavior,
    });
  });
}

watch(() => props.activeDeckId, () => {
  cancelRename();
  scrollActiveIntoView();
});
watch(
  () => [props.sortBy, sortedDecks.value.length],
  () => scrollActiveIntoView("auto"),
);

onMounted(() => scrollActiveIntoView("auto"));
</script>

<template>
  <div ref="galleryRef" class="deck-gallery" aria-label="All decks">
    <div
      v-for="deck in sortedDecks"
      :key="deck.id"
      class="deck-gallery-card"
      :class="{ active: isActiveDeck(deck) }"
      role="button"
      tabindex="0"
      @click="selectDeck(deck.id)"
      @keydown="onCardKeydown($event, deck.id)"
    >
      <div class="deck-gallery-visual">
        <div class="deck-gallery-commanders">
          <figure
            v-for="(card, index) in commandersFor(deck)"
            :key="`${deck.id}-commander-${index}`"
            class="deck-gallery-commander"
          >
            <img
              :src="deckCardImageUri(card)"
              :alt="cardDisplayName(card)"
              :title="cardDisplayName(card)"
              loading="lazy"
            />
          </figure>
          <div v-if="!commandersFor(deck).length" class="deck-gallery-placeholder">
            No commander image
          </div>
        </div>
      </div>

      <div class="deck-gallery-meta">
        <div
          v-if="isActiveDeck(deck)"
          class="deck-rename-wrap deck-gallery-name-wrap"
          @click.stop
        >
          <div class="deck-rename-title-row">
            <h3 v-if="!renaming" class="deck-gallery-name">{{ deck.label }}</h3>
            <input
              v-else
              ref="renameInputRef"
              v-model="draft"
              class="deck-gallery-name deck-rename-input"
              type="text"
              maxlength="120"
              :disabled="renameSaving"
              @keydown.enter.prevent="saveRename"
              @keydown.esc.prevent="cancelRename"
              @blur="onRenameBlur"
              @click.stop
            />
            <button
              v-if="!renaming"
              type="button"
              class="deck-rename-edit-button"
              aria-label="Rename deck"
              title="Rename deck"
              :disabled="deleting"
              @click.stop="startRename"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path
                  d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"
                  fill="currentColor"
                />
              </svg>
            </button>
            <button
              type="button"
              class="deck-gallery-delete"
              :class="{ 'is-loading': deleting }"
              aria-label="Delete deck"
              title="Delete deck"
              :disabled="renaming || deleting"
              @click.stop="deleteActiveDeck"
            >
              <span v-if="deleting" class="loading-spinner deck-gallery-delete-spinner" aria-hidden="true" />
              <span v-else aria-hidden="true">×</span>
            </button>
          </div>
          <p v-if="renameError" class="deck-rename-error">{{ renameError }}</p>
        </div>
        <h3 v-else class="deck-gallery-name">{{ deck.label }}</h3>
        <div class="deck-gallery-stats">
          <span v-if="deck.releaseYear" class="deck-gallery-year">{{ deck.releaseYear }}</span>
          <span class="deck-gallery-value">{{ deckValueLabel(deck) }}</span>
          <span v-if="deckOwnedLabel(deck)" class="deck-gallery-owned">{{ deckOwnedLabel(deck) }} owned</span>
        </div>
      </div>
    </div>

    <button
      type="button"
      class="deck-gallery-card deck-gallery-card--add"
      aria-label="Create deck"
      @click="emit('create')"
    >
      <div class="deck-gallery-visual">
        <span class="deck-gallery-add-icon" aria-hidden="true">+</span>
      </div>
      <div class="deck-gallery-meta">
        <h3 class="deck-gallery-name">New deck</h3>
      </div>
    </button>
  </div>
</template>
