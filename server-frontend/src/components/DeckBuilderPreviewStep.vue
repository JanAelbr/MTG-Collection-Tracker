<script setup>
import { computed } from "vue";
import ManaSymbols from "./ManaSymbols.vue";
import { formatEuro } from "../utils/format";
import { cardFinish, finishLabel } from "../utils/finishes";
import { groupProposalCards, slotLabel } from "../utils/deckPower";

const props = defineProps({
  proposal: { type: Object, default: null },
  generating: { type: Boolean, default: false },
});

const emit = defineEmits(["regenerate"]);

const grouped = computed(() => groupProposalCards(props.proposal?.cards || []));

const slotGroups = computed(() => {
  const groups = new Map();
  for (const card of props.proposal?.cards || []) {
    const slot = card.slot || "flex";
    if (!groups.has(slot)) {
      groups.set(slot, []);
    }
    groups.get(slot).push(card);
  }
  return [...groups.entries()].map(([slot, cards]) => ({ slot, cards }));
});

function cardPrice(card) {
  const finish = cardFinish(card);
  if (finish === 1) return card.marketValueFoil;
  if (finish === 2) return card.marketValueEtched;
  return card.marketValue;
}
</script>

<template>
  <section class="deck-builder-step">
    <header class="deck-builder-step-head">
      <div>
        <h3>Review proposal</h3>
        <p v-if="proposal">
          {{ proposal.stats?.ownedCount || 0 }} owned,
          {{ proposal.stats?.suggestedCount || 0 }} to buy
          <span v-if="proposal.stats?.estimatedCost">
            (≈ {{ formatEuro(proposal.stats.estimatedCost) }})
          </span>
        </p>
      </div>
      <button type="button" class="btn btn-secondary btn-small" :disabled="generating" @click="emit('regenerate')">
        Regenerate
      </button>
    </header>

    <div v-if="generating" class="deck-builder-loading">
      <p>Generating deck…</p>
    </div>

    <template v-else-if="proposal">
      <div class="deck-builder-preview-summary">
        <ManaSymbols :colors="proposal.colorIdentity || []" />
        <span>{{ proposal.stats?.totalCards || 0 }} maindeck cards</span>
      </div>

      <div v-if="proposal.warnings?.length" class="deck-builder-warnings">
        <p v-for="warning in proposal.warnings" :key="warning">{{ warning }}</p>
      </div>

      <div class="deck-builder-preview-columns">
        <section>
          <h4>Owned ({{ grouped.owned.length }})</h4>
          <ul class="deck-builder-card-list">
            <li v-for="card in grouped.owned" :key="`${card.name}-${card.setCode}-${card.collectorNumber}`">
              <span>{{ card.name }}</span>
              <span class="deck-builder-card-meta">{{ slotLabel(card.slot) }}</span>
            </li>
          </ul>
        </section>

        <section>
          <h4>To buy ({{ grouped.suggested.length }})</h4>
          <ul class="deck-builder-card-list">
            <li v-for="card in grouped.suggested" :key="`s-${card.name}-${card.setCode}-${card.collectorNumber}`">
              <span>{{ card.name }}</span>
              <span class="deck-builder-card-meta">
                {{ slotLabel(card.slot) }}
                <template v-if="cardPrice(card) != null"> · {{ formatEuro(cardPrice(card)) }}</template>
              </span>
            </li>
          </ul>
        </section>
      </div>

      <details class="deck-builder-slot-breakdown">
        <summary>Slot breakdown</summary>
        <div v-for="group in slotGroups" :key="group.slot" class="deck-builder-slot-group">
          <h5>{{ slotLabel(group.slot) }} ({{ group.cards.length }})</h5>
          <p>{{ group.cards.map((card) => card.name).join(", ") }}</p>
        </div>
      </details>
    </template>
  </section>
</template>
