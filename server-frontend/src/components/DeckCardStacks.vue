<script setup>
import { computed, ref, watch } from "vue";
import DeckAddCardModal from "./DeckAddCardModal.vue";
import DeckCardQtyControl from "./DeckCardQtyControl.vue";
import DeckTypeIcon from "./DeckTypeIcon.vue";
import ManaSymbols from "./ManaSymbols.vue";
import {
  effectiveDeckOwnedQty,
  isDeckCardFullyOwned,
  ownershipRevision,
} from "../composables/cardContextMenu";
import { cardDisplayName, cardFinish, cardRouteQuery, finishLabel } from "../utils/finishes";
import { cardTypeGroup, deckTypeIconType, deckTypeLabel, formatDeckGroupHeading } from "../utils/deckCards";
import { deckStackRowStyle } from "../utils/deckStackStyles";
import { formatEuro } from "../utils/format";

const props = defineProps({
  groups: { type: Array, default: () => [] },
  defaultDeckId: { type: String, default: "" },
  showDeckRemove: { type: Boolean, default: false },
  deckName: { type: String, default: "" },
});

const emit = defineEmits(["deck-added", "deck-removed", "deck-changed"]);

const selectedCard = ref(null);
const addModal = ref({
  open: false,
  section: "main",
  cardType: "",
  typeLabel: "",
});

const ownershipTick = computed(() => ownershipRevision.value);

const stackColumns = computed(() =>
  (props.groups || []).filter(
    (group) => group.kind === "type" || (group.kind === "section" && group.cards?.length),
  ),
);

watch(
  () => props.groups,
  () => {
    if (!selectedCard.value) {
      return;
    }
    const stillPresent = stackColumns.value.some((group) =>
      group.cards?.some((card) => cardKey(card) === cardKey(selectedCard.value)),
    );
    if (!stillPresent) {
      selectedCard.value = null;
    }
  },
);

function cardKey(card) {
  return `${card.section}-${card.setCode}-${card.collectorNumber}-${cardFinish(card)}-${card.cardName}`;
}

function cardRoute(card) {
  if (!card?.setCode || !card?.collectorNumber) {
    return null;
  }
  const query = cardRouteQuery(cardFinish(card));
  if (props.defaultDeckId) {
    query.deck = props.defaultDeckId;
  }
  return {
    name: "card",
    params: { setCode: card.setCode, collectorNumber: card.collectorNumber },
    query,
  };
}

function ownershipClass(card) {
  ownershipTick.value;
  const qty = Number(card?.qty) || 0;
  const ownedQty = effectiveDeckOwnedQty(card);
  if (isDeckCardFullyOwned(card)) {
    return "is-owned";
  }
  if (ownedQty > 0 && ownedQty < qty) {
    return "is-partial";
  }
  return "is-missing";
}

function ownedLabel(card) {
  ownershipTick.value;
  const qty = Number(card?.qty) || 0;
  const ownedQty = effectiveDeckOwnedQty(card);
  if (isDeckCardFullyOwned(card)) {
    return qty > 1 ? `${qty} owned` : "Owned";
  }
  if (ownedQty > 0 && ownedQty < qty) {
    return `${ownedQty} / ${qty} owned`;
  }
  return "Missing";
}

function isSelected(card) {
  return Boolean(selectedCard.value && cardKey(card) === cardKey(selectedCard.value));
}

function toggleCard(card) {
  if (isSelected(card)) {
    selectedCard.value = null;
    return;
  }
  selectedCard.value = card;
}

function rowStyle(card) {
  return deckStackRowStyle(card);
}

function isCommanderColumn(group) {
  return group.kind === "section" && group.section === "commander";
}

function showExpanded(card, group) {
  return isCommanderColumn(group) || isSelected(card);
}

function openAddModal(group) {
  addModal.value = {
    open: true,
    section: group.section || "main",
    cardType: group.type || "",
    typeLabel: group.label || "",
  };
}

function closeAddModal() {
  addModal.value = { ...addModal.value, open: false };
}
</script>

<template>
  <div class="deck-stacks">
    <div v-if="!stackColumns.length" class="storage-empty deck-stacks-empty">
      No cards to display.
    </div>

    <div v-else class="deck-stacks-scroll">
      <section
        v-for="group in stackColumns"
        :key="group.key"
        class="deck-stacks-column"
        :class="{ 'is-commander': isCommanderColumn(group) }"
      >
        <header class="deck-stacks-column-header deck-type-heading">
          <DeckTypeIcon :type="deckTypeIconType(group)" />
          <span>{{ formatDeckGroupHeading(group) }}</span>
        </header>

        <div class="deck-stacks-column-body">
          <article
            v-for="card in group.cards"
            :key="`${group.key}-${cardKey(card)}`"
            class="deck-stacks-card"
            :class="[
              ownershipClass(card),
              { 'is-expanded': showExpanded(card, group) },
            ]"
          >
            <div v-if="showExpanded(card, group)" class="deck-stacks-expanded">
              <button
                v-if="!isCommanderColumn(group)"
                type="button"
                class="deck-stacks-collapse"
                aria-label="Collapse card"
                @click="selectedCard = null"
              >
                ×
              </button>

              <img
                v-if="card.imageUri"
                :src="card.imageUri"
                :alt="card.cardName"
                class="deck-stacks-expanded-image"
                loading="lazy"
              >
              <div v-else class="deck-stacks-expanded-placeholder">{{ card.cardName }}</div>

              <div class="deck-stacks-expanded-meta">
                <div class="deck-stacks-expanded-name-row">
                  <ManaSymbols :colors="card.colors" :size="16" />
                  <RouterLink
                    v-if="cardRoute(card)"
                    :to="cardRoute(card)"
                    class="deck-stacks-expanded-name"
                  >
                    {{ cardDisplayName(card) }}
                  </RouterLink>
                  <span v-else class="deck-stacks-expanded-name is-plain">
                    {{ cardDisplayName(card) }}
                  </span>
                </div>

                <p v-if="card.typeLine" class="deck-stacks-expanded-type">{{ card.typeLine }}</p>

                <dl class="deck-stacks-expanded-details">
                  <div v-if="cardTypeGroup(card)" class="deck-stacks-detail-row">
                    <dt>Type</dt>
                    <dd class="deck-type-label">
                      <DeckTypeIcon :type="cardTypeGroup(card)" />
                      <span>{{ deckTypeLabel(cardTypeGroup(card)) }}</span>
                    </dd>
                  </div>
                  <div v-if="card.qty > 1" class="deck-stacks-detail-row">
                    <dt>Qty</dt>
                    <dd>{{ card.qty }}</dd>
                  </div>
                  <div v-if="card.setCode" class="deck-stacks-detail-row">
                    <dt>Print</dt>
                    <dd>{{ card.setCode }} #{{ card.collectorNumber }}</dd>
                  </div>
                  <div v-if="card.finish != null" class="deck-stacks-detail-row">
                    <dt>Finish</dt>
                    <dd>{{ finishLabel(card.finish ?? card.foil ?? 0) }}</dd>
                  </div>
                  <div v-if="card.currentValue != null" class="deck-stacks-detail-row">
                    <dt>Value</dt>
                    <dd>{{ formatEuro(card.currentValue) }}</dd>
                  </div>
                  <div class="deck-stacks-detail-row">
                    <dt>Owned</dt>
                    <dd :class="`is-${ownershipClass(card)}`">{{ ownedLabel(card) }}</dd>
                  </div>
                </dl>
              </div>

              <DeckCardQtyControl
                v-if="showDeckRemove && defaultDeckId"
                :card="card"
                :deck-id="defaultDeckId"
                :deck-name="deckName"
                compact
                @changed="$emit('deck-changed', $event)"
                @removed="$emit('deck-removed', $event)"
              />
            </div>

            <button
              v-else
              type="button"
              class="deck-stacks-row"
              :style="rowStyle(card)"
              @click="toggleCard(card)"
            >
              <span v-if="card.qty > 1" class="deck-stacks-qty">{{ card.qty }}</span>
              <ManaSymbols class="deck-stacks-mana" :colors="card.colors" :size="14" />
              <span class="deck-stacks-name">{{ cardDisplayName(card) }}</span>
            </button>
          </article>

          <button
            v-if="group.kind === 'type' && defaultDeckId"
            type="button"
            class="deck-stacks-add-slot"
            :title="`Add ${group.label.toLowerCase()} to deck`"
            @click="openAddModal(group)"
          >
            +
          </button>
        </div>
      </section>
    </div>

    <DeckAddCardModal
      v-if="defaultDeckId"
      :open="addModal.open"
      :deck-id="defaultDeckId"
      :deck-name="deckName"
      :section="addModal.section"
      :card-type="addModal.cardType"
      :type-label="addModal.typeLabel"
      @close="closeAddModal"
      @added="$emit('deck-added', $event)"
    />
  </div>
</template>
