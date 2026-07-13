<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { api, clearClientCache } from "../api";
import DeckBuilderCommanderStep from "../components/DeckBuilderCommanderStep.vue";
import DeckBuilderOptionsStep from "../components/DeckBuilderOptionsStep.vue";
import DeckBuilderPreviewStep from "../components/DeckBuilderPreviewStep.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import { cardFinish } from "../utils/finishes";

const STEPS = ["commander", "options", "preview"];

const router = useRouter();

const step = ref("commander");
const selectedCommander = ref(null);
const deckName = ref("");
const locationSlugs = ref([]);
const includeDeckStorage = ref(false);
const landCount = ref(38);
const budgetCap = ref(null);
const excludeCategories = ref([]);
const proposal = ref(null);
const generating = ref(false);
const applying = ref(false);
const error = ref("");

const stepIndex = computed(() => STEPS.indexOf(step.value));
const canContinue = computed(() => {
  if (step.value === "commander") {
    return Boolean(selectedCommander.value?.setCode && selectedCommander.value?.collectorNumber);
  }
  if (step.value === "options") {
    return locationSlugs.value.length > 0;
  }
  return Boolean(proposal.value?.cards?.length);
});

function goBack() {
  const index = stepIndex.value;
  if (index <= 0) {
    router.push("/decks");
    return;
  }
  step.value = STEPS[index - 1];
}

async function goNext() {
  error.value = "";
  if (step.value === "commander") {
    if (!deckName.value.trim() && selectedCommander.value?.name) {
      deckName.value = selectedCommander.value.name;
    }
    step.value = "options";
    return;
  }
  if (step.value === "options") {
    await generateProposal();
    if (proposal.value) {
      step.value = "preview";
    }
    return;
  }
  await applyProposal();
}

async function generateProposal() {
  if (!selectedCommander.value) {
    return;
  }
  generating.value = true;
  error.value = "";
  try {
    proposal.value = await api.generateDeck({
      commanders: [
        {
          setCode: selectedCommander.value.setCode,
          collectorNumber: selectedCommander.value.collectorNumber,
          finish: cardFinish(selectedCommander.value),
        },
      ],
      locationSlugs: locationSlugs.value,
      includeDeckStorage: includeDeckStorage.value,
      landCount: landCount.value,
      budgetCap: budgetCap.value,
      excludeCategories: excludeCategories.value,
    });
  } catch (err) {
    error.value = err?.message || "Could not generate deck.";
    proposal.value = null;
  } finally {
    generating.value = false;
  }
}

async function applyProposal() {
  if (!proposal.value || !selectedCommander.value) {
    return;
  }
  applying.value = true;
  error.value = "";
  try {
    const created = await api.createDeck({
      format: "commander",
      name: deckName.value.trim() || selectedCommander.value.name,
      commanders: [
        {
          setCode: selectedCommander.value.setCode,
          collectorNumber: selectedCommander.value.collectorNumber,
          finish: cardFinish(selectedCommander.value),
        },
      ],
    });
    const deckId = created?.deck?.id || created?.deckId;
    if (!deckId) {
      throw new Error("Deck was not created.");
    }
    await api.bulkAddDeckCards(deckId, {
      replaceMain: false,
      cards: (proposal.value.cards || []).map((card) => ({
        setCode: card.setCode || "",
        collectorNumber: card.collectorNumber || "",
        finish: cardFinish(card),
        section: "main",
        qty: card.qty || 1,
        owned: !card.suggested && !card.infiniteBasic,
        cardName: card.name,
      })),
    });
    clearClientCache();
    router.push({ path: "/decks", query: { deck: String(deckId) } });
  } catch (err) {
    error.value = err?.message || "Could not apply deck.";
  } finally {
    applying.value = false;
  }
}

watch(selectedCommander, (commander) => {
  if (commander?.name && !deckName.value.trim()) {
    deckName.value = commander.name;
  }
});
</script>

<template>
  <div class="deck-builder-page">
    <header class="deck-builder-page-head">
      <div>
        <h2>Build Commander deck</h2>
        <p>Owned-first generation with purchase suggestions for gaps.</p>
      </div>
      <button type="button" class="btn btn-secondary btn-small" @click="router.push('/decks')">
        Cancel
      </button>
    </header>

    <nav class="deck-builder-steps" aria-label="Builder steps">
      <span :class="{ active: step === 'commander' }">1. Commander</span>
      <span :class="{ active: step === 'options' }">2. Options</span>
      <span :class="{ active: step === 'preview' }">3. Preview</span>
    </nav>

    <label v-if="step !== 'preview'" class="deck-builder-field deck-builder-name-field">
      <span>Deck name</span>
      <input v-model="deckName" type="text" maxlength="120" placeholder="Deck name" />
    </label>

    <DeckBuilderCommanderStep
      v-if="step === 'commander'"
      :selected-commander="selectedCommander"
      @select="selectedCommander = $event"
    />

    <DeckBuilderOptionsStep
      v-else-if="step === 'options'"
      v-model:location-slugs="locationSlugs"
      v-model:include-deck-storage="includeDeckStorage"
      v-model:land-count="landCount"
      v-model:budget-cap="budgetCap"
      v-model:exclude-categories="excludeCategories"
    />

    <DeckBuilderPreviewStep
      v-else
      :proposal="proposal"
      :generating="generating"
      @regenerate="generateProposal"
    />

    <p v-if="error" class="deck-builder-error">{{ error }}</p>

    <footer class="deck-builder-actions">
      <button type="button" class="btn btn-secondary" @click="goBack">
        {{ stepIndex === 0 ? "Back to decks" : "Back" }}
      </button>
      <button
        type="button"
        class="btn btn-primary"
        :disabled="!canContinue || generating || applying"
        @click="goNext"
      >
        <LoadingIndicator v-if="generating || applying" label="" />
        <span v-if="step === 'preview'">{{ applying ? "Applying…" : "Create deck" }}</span>
        <span v-else-if="step === 'options'">{{ generating ? "Generating…" : "Generate" }}</span>
        <span v-else>Continue</span>
      </button>
    </footer>
  </div>
</template>
