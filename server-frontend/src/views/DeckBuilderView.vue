<script setup>
import "../styles/decks.css";
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, clearClientCache } from "../api";
import DeckBuilderCommanderStep from "../components/DeckBuilderCommanderStep.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import { cardFinish } from "../utils/finishes";

const router = useRouter();
const route = useRoute();

const selectedCommander = ref(null);
const deckName = ref("");
const creating = ref(false);
const error = ref("");

const canCreate = computed(() =>
  Boolean(selectedCommander.value?.setCode && selectedCommander.value?.collectorNumber),
);

function decksRoute(deckId = "") {
  return deckId
    ? { path: "/collection/decks", query: { deck: String(deckId) } }
    : { path: "/collection/decks" };
}

function goBack() {
  router.push(decksRoute());
}

async function createDeck() {
  if (!canCreate.value || creating.value) {
    return;
  }
  creating.value = true;
  error.value = "";
  try {
    const commander = selectedCommander.value;
    const created = await api.createDeck({
      format: "commander",
      name: deckName.value.trim() || commander.name || "New deck",
      commanders: [
        {
          setCode: commander.setCode,
          collectorNumber: commander.collectorNumber,
          finish: cardFinish(commander),
        },
      ],
    });
    const deckId = created?.deck?.id || created?.deckId;
    if (!deckId) {
      throw new Error("Deck was not created.");
    }
    clearClientCache();
    router.push(decksRoute(deckId));
  } catch (err) {
    error.value = err?.message || "Could not create deck.";
  } finally {
    creating.value = false;
  }
}

watch(selectedCommander, (commander) => {
  if (commander?.name && !deckName.value.trim()) {
    deckName.value = commander.name;
  }
});

onMounted(() => {
  // Auto-generation / improve / rebuild flows were removed; land on the deck browser.
  if (route.query.deck || route.query.mode) {
    const deckId = route.query.deck != null && String(route.query.deck).trim()
      ? String(route.query.deck).trim()
      : "";
    router.replace(decksRoute(deckId));
  }
});
</script>

<template>
  <div class="deck-builder-page">
    <header class="deck-builder-page-head">
      <div>
        <h2>New Commander deck</h2>
        <p>Pick a commander to create an empty deck, then add cards from your collection.</p>
      </div>
      <button type="button" class="btn btn-secondary btn-small" @click="goBack">
        Cancel
      </button>
    </header>

    <label class="deck-builder-field deck-builder-name-field">
      <span>Deck name</span>
      <input v-model="deckName" type="text" maxlength="120" placeholder="Deck name">
    </label>

    <DeckBuilderCommanderStep
      :selected-commander="selectedCommander"
      @select="selectedCommander = $event"
    />

    <p v-if="error" class="deck-builder-error">{{ error }}</p>

    <footer class="deck-builder-actions">
      <button type="button" class="btn btn-secondary" @click="goBack">
        Back to decks
      </button>
      <button
        type="button"
        class="btn btn-primary"
        :disabled="!canCreate || creating"
        @click="createDeck"
      >
        <LoadingIndicator v-if="creating" label="" />
        <span>{{ creating ? "Creating…" : "Create deck" }}</span>
      </button>
    </footer>
  </div>
</template>
