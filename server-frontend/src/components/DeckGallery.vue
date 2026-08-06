<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { api, clearClientCache } from "../api";
import CardSetSymbol from "./CardSetSymbol.vue";
import ManaSymbols from "./ManaSymbols.vue";
import { useDeckRename } from "../composables/useDeckRename";
import { confirmDialog } from "../composables/confirmDialog";
import {
  buildDeckGalleryItems,
  deckCardImageUri,
} from "../utils/deckBrowse";
import { cardDisplayName } from "../utils/finishes";
import { formatDeckOwned, formatEuro } from "../utils/format";
import { useDeckGalleryFilter } from "../composables/deckGalleryFilter";

const props = defineProps({
  decks: { type: Array, default: () => [] },
  pages: { type: Object, default: () => ({}) },
  activeDeckId: { type: String, default: "" },
  onRenamed: { type: Function, default: null },
  onDeleted: { type: Function, default: null },
  onFavorited: { type: Function, default: null },
});

const emit = defineEmits(["select", "create"]);

const { deckGalleryFilter } = useDeckGalleryFilter();

const galleryRef = ref(null);
const menuRef = ref(null);
const contextMenu = ref(null);
const deleting = ref(false);
const favoriting = ref(false);

const galleryItems = computed(() =>
  buildDeckGalleryItems(props.decks, props.pages, deckGalleryFilter.value),
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

function commandersFor(deck) {
  return (deckCards(deck) || [])
    .filter((card) => String(card?.section || "") === "commander")
    .slice(0, 2);
}

function primaryCommander(deck) {
  return commandersFor(deck)[0] || null;
}

function commanderSetCode(deck) {
  return String(primaryCommander(deck)?.setCode || "").trim().toUpperCase();
}

function deckDisplayName(deck) {
  return String(deck?.name || deck?.label || "").trim() || "Deck";
}

function deckValueLabel(deck) {
  const stats = deckStats(deck);
  if (stats.ownedCurrent != null) {
    return formatEuro(stats.ownedCurrent);
  }
  return formatEuro(stats.current);
}

function deckOwnedLabel(deck) {
  const stats = deckStats(deck);
  return formatDeckOwned(stats.ownedQty, stats.deckSize);
}

function deckInfoLine(deck) {
  const parts = [];
  if (deck.releaseYear) {
    parts.push(String(deck.releaseYear));
  }
  const value = deckValueLabel(deck);
  if (value) {
    parts.push(value);
  }
  const owned = deckOwnedLabel(deck);
  if (owned) {
    parts.push(`${owned} owned`);
  }
  return parts.join(" · ");
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

function closeContextMenu() {
  contextMenu.value = null;
}

function onCreateDeck() {
  closeContextMenu();
  emit("create");
}

function onCardContextMenu(event, deck) {
  if (!deck?.id) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  const pad = 8;
  const menuWidth = 260;
  const menuHeight = 220;
  const x = Math.min(event.clientX, window.innerWidth - menuWidth - pad);
  const y = Math.min(event.clientY, window.innerHeight - menuHeight - pad);
  contextMenu.value = {
    deck,
    x: Math.max(pad, x),
    y: Math.max(pad, y),
  };
}

const menuStyle = computed(() => {
  if (!contextMenu.value) {
    return {};
  }
  return {
    left: `${contextMenu.value.x}px`,
    top: `${contextMenu.value.y}px`,
  };
});

const contextMenuDeck = computed(() => contextMenu.value?.deck || null);

async function onContextFavorite() {
  const deck = contextMenuDeck.value;
  closeContextMenu();
  if (!deck?.id || favoriting.value) {
    return;
  }
  favoriting.value = true;
  try {
    const result = await api.toggleDeckFavorite(deck.id);
    clearClientCache();
    await props.onFavorited?.(result?.deck || { ...deck, favorite: result?.favorite });
  } catch (err) {
    window.alert(err?.message || "Could not update favourite deck.");
  } finally {
    favoriting.value = false;
  }
}

async function onContextRename() {
  const deck = contextMenuDeck.value;
  closeContextMenu();
  if (!deck?.id || deleting.value) {
    return;
  }
  if (!isActiveDeck(deck)) {
    selectDeck(deck.id);
    await nextTick();
  }
  startRename();
}

async function deleteDeck(deckId) {
  if (!deckId || deleting.value || renaming.value) {
    return;
  }
  const deck = props.decks.find((item) => String(item.id) === String(deckId));
  const deckName = deck?.name || "this deck";
  const ok = await confirmDialog({
    title: "Delete deck",
    message: `Delete “${deckName}”? This cannot be undone.`,
    confirmLabel: "Delete",
    danger: true,
  });
  if (!ok) {
    return;
  }
  deleting.value = true;
  try {
    await api.deleteDeck(deckId);
    clearClientCache();
    await props.onDeleted?.(deckId);
  } catch (err) {
    window.alert(err?.message || "Could not delete deck.");
  } finally {
    deleting.value = false;
  }
}

async function onContextDelete() {
  const deck = contextMenuDeck.value;
  closeContextMenu();
  if (!deck?.id) {
    return;
  }
  await deleteDeck(deck.id);
}

function onDocumentPointerDown(event) {
  if (contextMenu.value && !menuRef.value?.contains(event.target)) {
    closeContextMenu();
  }
}

function onDocumentKeydown(event) {
  if (event.key === "Escape") {
    closeContextMenu();
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
    const sticky = root.querySelector(".deck-gallery-new-wrap");
    const stickyWidth = sticky ? sticky.getBoundingClientRect().width : 0;
    const pad = 8;
    const visibleLeft = root.scrollLeft + stickyWidth + pad;
    const visibleRight = root.scrollLeft + root.clientWidth - pad;
    const cardLeft = active.offsetLeft;
    const cardRight = cardLeft + active.offsetWidth;
    let nextScroll = root.scrollLeft;
    if (cardLeft < visibleLeft) {
      nextScroll = Math.max(0, cardLeft - stickyWidth - pad);
    } else if (cardRight > visibleRight) {
      nextScroll = Math.max(0, cardRight - root.clientWidth + pad);
    } else {
      return;
    }
    if (Math.abs(nextScroll - root.scrollLeft) < 1) {
      return;
    }
    root.scrollTo({
      left: nextScroll,
      behavior: behavior === "auto" ? "auto" : behavior,
    });
  });
}

watch(() => props.activeDeckId, () => {
  cancelRename();
  closeContextMenu();
  scrollActiveIntoView();
});
watch(
  () => galleryItems.value.map((item) => item.key).join("|"),
  () => {
    // Re-layout (sort/favourites/filter) can clip the active tile; only nudge if needed.
    scrollActiveIntoView("auto");
  },
);

onMounted(() => {
  document.addEventListener("pointerdown", onDocumentPointerDown, true);
  document.addEventListener("keydown", onDocumentKeydown);
});

onUnmounted(() => {
  document.removeEventListener("pointerdown", onDocumentPointerDown, true);
  document.removeEventListener("keydown", onDocumentKeydown);
});
</script>

<template>
  <div ref="galleryRef" class="deck-gallery" aria-label="All decks">
    <div class="deck-gallery-new-wrap">
      <button
        type="button"
        class="deck-gallery-card deck-gallery-card--add"
        aria-label="New deck"
        @click="onCreateDeck"
      >
        <div class="deck-gallery-card-main">
          <span class="deck-gallery-add-icon" aria-hidden="true">+</span>
          <span class="deck-gallery-name">New deck</span>
        </div>
      </button>
    </div>

    <template v-for="item in galleryItems" :key="item.key">
      <div
        v-if="item.type === 'separator'"
        class="deck-gallery-separator"
        role="separator"
        :aria-label="item.ariaLabel || 'Decks'"
      />
      <span
        v-else-if="item.type === 'color'"
        class="deck-gallery-color-label"
        aria-hidden="true"
      >
        <ManaSymbols :colors="item.colors" :size="14" />
      </span>
      <div
        v-else
        class="deck-gallery-card"
        :class="{
          active: isActiveDeck(item.deck),
          'deck-gallery-card--renaming': isActiveDeck(item.deck) && renaming,
          'deck-gallery-card--favorite': item.deck.favorite,
        }"
        role="button"
        tabindex="0"
        :aria-label="`Select ${deckDisplayName(item.deck)}`"
        :aria-current="isActiveDeck(item.deck) ? 'true' : undefined"
        :title="deckDisplayName(item.deck)"
        @click="selectDeck(item.deck.id)"
        @keydown="onCardKeydown($event, item.deck.id)"
        @contextmenu="onCardContextMenu($event, item.deck)"
      >
        <div class="deck-gallery-card-main">
          <div class="deck-gallery-icon-wrap">
            <CardSetSymbol
              v-if="commanderSetCode(item.deck)"
              :set-code="commanderSetCode(item.deck)"
              variant="generic"
              :size="28"
            />
            <div v-else class="deck-gallery-icon-placeholder" aria-hidden="true">?</div>
            <span
              v-if="item.deck.favorite"
              class="deck-gallery-favorite-mark"
              aria-hidden="true"
            >★</span>
          </div>

          <div class="deck-gallery-meta">
            <template v-if="isActiveDeck(item.deck) && renaming">
              <div class="deck-rename-wrap deck-gallery-name-wrap" @click.stop>
                <input
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
                <p v-if="renameError" class="deck-rename-error">{{ renameError }}</p>
              </div>
            </template>
            <template v-else>
              <span class="deck-gallery-name" :title="deckDisplayName(item.deck)">
                {{ deckDisplayName(item.deck) }}
              </span>
            </template>
          </div>
        </div>
      </div>
    </template>
  </div>

  <Teleport to="body">
    <div
      v-if="contextMenuDeck"
      ref="menuRef"
      class="card-context-menu deck-gallery-context-menu"
      role="menu"
      :style="menuStyle"
      @click.stop
      @contextmenu.prevent
    >
      <div class="deck-gallery-context-preview" aria-hidden="true">
        <figure
          v-for="(card, index) in commandersFor(contextMenuDeck)"
          :key="`${contextMenuDeck.id}-ctx-${index}`"
          class="deck-gallery-context-commander"
        >
          <img
            v-if="deckCardImageUri(card)"
            :src="deckCardImageUri(card)"
            :alt="cardDisplayName(card)"
            loading="lazy"
          />
          <figcaption>{{ cardDisplayName(card) }}</figcaption>
        </figure>
        <p v-if="!commandersFor(contextMenuDeck).length" class="deck-gallery-context-empty">
          No commander image
        </p>
      </div>

      <div class="deck-gallery-context-info">
        <strong class="deck-gallery-context-title">{{ deckDisplayName(contextMenuDeck) }}</strong>
        <span v-if="deckInfoLine(contextMenuDeck)" class="deck-gallery-context-stats">
          {{ deckInfoLine(contextMenuDeck) }}
        </span>
      </div>

      <div class="card-context-menu-divider" role="separator" />

      <button
        type="button"
        class="card-context-menu-item"
        role="menuitem"
        :disabled="favoriting || deleting || renaming"
        @click="onContextFavorite"
      >
        {{ contextMenuDeck.favorite ? "Unfavourite deck" : "Favourite deck" }}
      </button>
      <button
        type="button"
        class="card-context-menu-item"
        role="menuitem"
        :disabled="deleting || renaming || favoriting"
        @click="onContextRename"
      >
        Rename deck
      </button>
      <button
        type="button"
        class="card-context-menu-item"
        role="menuitem"
        :disabled="deleting || renaming || favoriting"
        @click="onContextDelete"
      >
        <span v-if="deleting">Deleting…</span>
        <span v-else>Delete deck</span>
      </button>
    </div>
  </Teleport>
</template>
