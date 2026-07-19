<script setup>

import { computed, ref, watch } from "vue";
import { api } from "../api";
import CardPreview from "./CardPreview.vue";

import DeckPowerPanel from "./DeckPowerPanel.vue";

import ManaSymbols from "./ManaSymbols.vue";

import { formatEuro } from "../utils/format";

import { cardFinish } from "../utils/finishes";

import { cardTypeGroup, deckTypeLabel } from "../utils/deckCards";

import {

  formatBasicLandSummary,

  groupProposalBySlot,

  groupProposalByType,

  slotLabel,

} from "../utils/deckPower";



const props = defineProps({

  proposal: { type: Object, default: null },

  generating: { type: Boolean, default: false },

});



const emit = defineEmits(["regenerate"]);



const previewTab = ref("cards");

const previewView = ref("role");



const displayGroups = computed(() => {

  const cards = props.proposal?.cards || [];

  if (previewView.value === "type") {

    const { typeGroups, basicLandSummary } = groupProposalByType(cards);

    return {

      basicLandSummary,

      groups: typeGroups.map((group) => ({

        key: group.type,

        label: deckTypeLabel(group.type),

        cards: group.cards,

      })),

    };

  }



  const { slotGroups, basicLandSummary } = groupProposalBySlot(cards);

  return {

    basicLandSummary,

    groups: slotGroups.map((group) => ({

      key: group.slot,

      label: slotLabel(group.slot),

      cards: group.cards,

    })),

  };

});



const basicLandNote = computed(() =>

  formatBasicLandSummary(displayGroups.value.basicLandSummary),

);



function cardPrice(card) {

  const finish = cardFinish(card);

  if (finish === 1) return card.marketValueFoil;

  if (finish === 2) return card.marketValueEtched;

  return card.marketValue;

}



function cardTypeLabel(card) {

  return deckTypeLabel(cardTypeGroup(card));

}

const resolvedPower = ref(null);
const powerLoading = ref(false);
const powerError = ref("");

const activePowerPayload = computed(() => props.proposal?.power || resolvedPower.value);

watch(
  () => props.proposal,
  () => {
    resolvedPower.value = null;
    powerError.value = "";
  },
);

watch(
  () => [props.proposal, previewTab.value],
  async () => {
    if (previewTab.value !== "power" || !props.proposal || props.proposal.power) {
      return;
    }
    if (powerLoading.value || resolvedPower.value) {
      return;
    }
    const commanders = (props.proposal.commanders || [])
      .filter((commander) => commander?.setCode && commander?.collectorNumber)
      .map((commander) => ({
        setCode: commander.setCode,
        collectorNumber: commander.collectorNumber,
        finish: commander.finish ?? 0,
      }));
    if (!commanders.length || !(props.proposal.cards || []).length) {
      powerError.value = "Proposal data is incomplete.";
      return;
    }
    powerLoading.value = true;
    powerError.value = "";
    try {
      resolvedPower.value = await api.assessBuilderPower({
        commanders,
        cards: props.proposal.cards,
      });
    } catch (err) {
      powerError.value = err?.message || "Could not load power analysis.";
    } finally {
      powerLoading.value = false;
    }
  },
  { immediate: true },
);

</script>



<template>

  <section class="deck-builder-step deck-builder-preview-step">

    <button

      type="button"

      class="deck-builder-regenerate-btn"

      :class="{ 'is-loading': generating }"

      :disabled="generating"

      aria-label="Regenerate proposal"

      title="Regenerate proposal"

      @click="emit('regenerate')"

    >

      <span v-if="generating" class="loading-spinner deck-builder-regenerate-spinner" aria-hidden="true" />

      <svg v-else viewBox="0 0 24 24" aria-hidden="true" focusable="false">

        <path

          d="M17.65 6.35A7.958 7.958 0 0 0 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0 1 12 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"

          fill="currentColor"

        />

      </svg>

    </button>



    <header class="deck-builder-step-head">

      <div>

        <h3>Review proposal</h3>

        <p v-if="proposal">

          {{ proposal.stats?.totalCards || 0 }}-card maindeck from your collection, with purchase

          suggestions for gaps.

        </p>

      </div>

    </header>



    <div v-if="generating" class="deck-builder-loading">

      <p>Generating deck…</p>

    </div>



    <template v-else-if="proposal">

      <div class="deck-builder-preview-summary">

        <ManaSymbols :colors="proposal.colorIdentity || []" />

        <span class="deck-builder-stat-chip">{{ proposal.stats?.ownedCount || 0 }} owned</span>

        <span class="deck-builder-stat-chip deck-builder-stat-chip--buy">

          {{ proposal.stats?.suggestedCount || 0 }} to buy

        </span>

        <span v-if="proposal.stats?.estimatedCost" class="deck-builder-stat-chip">

          ≈ {{ formatEuro(proposal.stats.estimatedCost) }}

        </span>

      </div>



      <div class="deck-builder-preview-toolbar">

        <div class="button-group deck-builder-preview-tab-group" role="tablist" aria-label="Preview panels">

          <button

            type="button"

            class="filter-button"

            role="tab"

            :class="{ active: previewTab === 'cards' }"

            :aria-selected="previewTab === 'cards'"

            @click="previewTab = 'cards'"

          >

            Cards

          </button>

          <button

            type="button"

            class="filter-button"

            role="tab"

            :class="{ active: previewTab === 'power' }"

            :aria-selected="previewTab === 'power'"

            @click="previewTab = 'power'"

          >

            Power

          </button>

        </div>



        <div

          v-if="previewTab === 'cards'"

          class="deck-builder-preview-grouping"

        >

          <span class="deck-builder-preview-toolbar-label">Group by</span>

          <div class="button-group deck-builder-preview-view-group" role="group" aria-label="Preview grouping">

            <button

              type="button"

              class="filter-button"

              :class="{ active: previewView === 'role' }"

              @click="previewView = 'role'"

            >

              Role

            </button>

            <button

              type="button"

              class="filter-button"

              :class="{ active: previewView === 'type' }"

              @click="previewView = 'type'"

            >

              Card type

            </button>

          </div>

        </div>

      </div>



      <template v-if="previewTab === 'cards'">

        <p v-if="basicLandNote" class="deck-builder-basic-lands-note">

          Basic lands included: {{ basicLandNote }}

        </p>



        <div v-if="proposal.warnings?.length" class="deck-builder-warnings">

          <p v-for="warning in proposal.warnings" :key="warning">{{ warning }}</p>

        </div>



        <div class="deck-builder-preview-body">

          <section

            v-for="group in displayGroups.groups"

            :key="`${previewView}-${group.key}`"

            class="deck-builder-slot-section"

          >

            <h4 class="deck-builder-slot-heading">

              {{ group.label }}

              <span class="deck-builder-slot-count">{{ group.cards.length }}</span>

            </h4>

            <ul class="deck-builder-card-rows">

              <li

                v-for="card in group.cards"

                :key="`${group.key}-${card.name}-${card.setCode}-${card.collectorNumber}`"

                class="deck-builder-card-row"

              >

                <span class="deck-builder-card-name">

                  <CardPreview
                    :image-uri="card.imageUri || ''"
                    :image-uri-back="card.imageUriBack || ''"
                  >

                    <span class="deck-builder-card-title">{{ card.name }}</span>

                  </CardPreview>

                  <span v-if="cardTypeLabel(card)" class="deck-builder-card-type">

                    {{ cardTypeLabel(card) }}

                  </span>

                </span>

                <span

                  class="deck-builder-card-status"

                  :class="card.suggested ? 'is-buy' : 'is-owned'"

                >

                  <template v-if="card.suggested">

                    Buy

                    <template v-if="cardPrice(card) != null">

                      · {{ formatEuro(cardPrice(card)) }}

                    </template>

                  </template>

                  <template v-else>Owned</template>

                </span>

              </li>

            </ul>

          </section>

        </div>

      </template>



      <div v-else class="deck-builder-preview-power">
        <p v-if="powerLoading" class="deck-builder-loading">Assessing deck…</p>
        <p v-else-if="powerError" class="deck-builder-error">{{ powerError }}</p>
        <DeckPowerPanel v-else :power-payload="activePowerPayload" />
      </div>

    </template>

  </section>

</template>


