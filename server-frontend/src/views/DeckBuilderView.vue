<script setup>
import "../styles/decks.css";
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, clearClientCache } from "../api";
import DeckBuilderCommanderStep from "../components/DeckBuilderCommanderStep.vue";
import DeckBuilderOptionsStep from "../components/DeckBuilderOptionsStep.vue";
import DeckBuilderPreviewStep from "../components/DeckBuilderPreviewStep.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import { cardFinish } from "../utils/finishes";

const STEPS = ["commander", "options", "preview"];

const router = useRouter();
const route = useRoute();

const step = ref("commander");
const selectedCommander = ref(null);
const deckName = ref("");
const locationSlugs = ref([]);
const includeDeckStorage = ref(false);
const landCount = ref(38);
const budgetCap = ref(null);
const excludeCategories = ref([]);
const preset = ref("balanced");
const proposal = ref(null);
const generating = ref(false);
const applying = ref(false);
const error = ref("");

const targetDeckId = computed(() => {
  const raw = route.query.deck;
  return raw != null && String(raw).trim() ? String(raw).trim() : "";
});
const builderMode = computed(() => {
  const mode = String(route.query.mode || "generate").toLowerCase();
  if (mode === "rebuild" || mode === "improve") {
    return mode;
  }
  return targetDeckId.value ? "improve" : "generate";
});
const isExistingDeckFlow = computed(() => Boolean(targetDeckId.value));

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

const pageTitle = computed(() => {
  if (builderMode.value === "rebuild") {
    return "Rebuild Commander deck";
  }
  if (builderMode.value === "improve") {
    return "Improve Commander deck";
  }
  return "Build Commander deck";
});

const primaryActionLabel = computed(() => {
  if (step.value !== "preview") {
    return "";
  }
  if (applying.value) {
    return "Applying…";
  }
  if (builderMode.value === "rebuild") {
    return "Replace main deck";
  }
  if (builderMode.value === "improve") {
    return "Apply improvements";
  }
  return "Create deck";
});

function goBack() {
  const index = stepIndex.value;
  if (index <= 0 || (isExistingDeckFlow.value && step.value === "options")) {
    if (targetDeckId.value) {
      router.push({ path: "/decks", query: { deck: targetDeckId.value } });
    } else {
      router.push("/decks");
    }
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

function proposalBody() {
  return {
    locationSlugs: locationSlugs.value,
    includeDeckStorage: includeDeckStorage.value,
    landCount: landCount.value,
    budgetCap: budgetCap.value,
    excludeCategories: excludeCategories.value,
    preset: preset.value,
  };
}

async function generateProposal() {
  generating.value = true;
  error.value = "";
  try {
    if (isExistingDeckFlow.value) {
      proposal.value = await api.improveDeck({
        deckId: targetDeckId.value,
        rebuild: builderMode.value === "rebuild",
        ...proposalBody(),
      });
    } else {
      if (!selectedCommander.value) {
        return;
      }
      proposal.value = await api.generateDeck({
        commanders: [
          {
            setCode: selectedCommander.value.setCode,
            collectorNumber: selectedCommander.value.collectorNumber,
            finish: cardFinish(selectedCommander.value),
          },
        ],
        ...proposalBody(),
      });
    }
  } catch (err) {
    error.value = err?.message || "Could not generate deck.";
    proposal.value = null;
  } finally {
    generating.value = false;
  }
}

function proposalCardsPayload() {
  return (proposal.value?.cards || []).map((card) => ({
    setCode: card.setCode || "",
    collectorNumber: card.collectorNumber || "",
    finish: cardFinish(card),
    section: "main",
    qty: card.qty || 1,
    owned: !card.suggested && !card.infiniteBasic,
    cardName: card.name,
  }));
}

async function applyProposal() {
  if (!proposal.value) {
    return;
  }
  applying.value = true;
  error.value = "";
  try {
    if (isExistingDeckFlow.value) {
      await api.applyDeckProposal(targetDeckId.value, {
        mode: builderMode.value === "rebuild" ? "rebuild" : "improve",
        cards: proposalCardsPayload(),
      });
      clearClientCache();
      router.push({ path: "/decks", query: { deck: targetDeckId.value } });
      return;
    }
    if (!selectedCommander.value) {
      return;
    }
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
      cards: proposalCardsPayload(),
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

onMounted(() => {
  if (isExistingDeckFlow.value) {
    step.value = "options";
    if (builderMode.value === "rebuild") {
      preset.value = "theme_first";
    }
  }
});
</script>

<template>
  <div class="deck-builder-page">
    <header class="deck-builder-page-head">
      <div>
        <h2>{{ pageTitle }}</h2>
        <p v-if="isExistingDeckFlow">
          Multi-phase packages with commander theme scoring, then apply to this deck.
        </p>
        <p v-else>
          Owned-first generation with theme synergy and purchase suggestions for gaps.
        </p>
      </div>
      <button type="button" class="btn btn-secondary btn-small" @click="goBack">
        Cancel
      </button>
    </header>

    <nav class="deck-builder-steps" aria-label="Builder steps">
      <span v-if="!isExistingDeckFlow" :class="{ active: step === 'commander' }">1. Commander</span>
      <span :class="{ active: step === 'options' }">
        {{ isExistingDeckFlow ? "1. Options" : "2. Options" }}
      </span>
      <span :class="{ active: step === 'preview' }">
        {{ isExistingDeckFlow ? "2. Preview" : "3. Preview" }}
      </span>
    </nav>

    <label v-if="step !== 'preview' && !isExistingDeckFlow" class="deck-builder-field deck-builder-name-field">
      <span>Deck name</span>
      <input v-model="deckName" type="text" maxlength="120" placeholder="Deck name">
    </label>

    <DeckBuilderCommanderStep
      v-if="step === 'commander' && !isExistingDeckFlow"
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
      v-model:preset="preset"
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
        {{ stepIndex === 0 || (isExistingDeckFlow && step === 'options') ? "Back to decks" : "Back" }}
      </button>
      <button
        type="button"
        class="btn btn-primary"
        :disabled="!canContinue || generating || applying"
        @click="goNext"
      >
        <LoadingIndicator v-if="generating || applying" label="" />
        <span v-if="step === 'preview'">{{ primaryActionLabel }}</span>
        <span v-else-if="step === 'options'">{{ generating ? "Generating…" : "Generate" }}</span>
        <span v-else>Continue</span>
      </button>
    </footer>
  </div>
</template>
