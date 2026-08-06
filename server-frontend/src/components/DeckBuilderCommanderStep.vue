<script setup>
import { computed } from "vue";
import CommanderGalleryPicker from "./CommanderGalleryPicker.vue";
import ManaSymbols from "./ManaSymbols.vue";
import { cardFinish } from "../utils/finishes";

const props = defineProps({
  selectedCommander: { type: Object, default: null },
});

const emit = defineEmits(["select"]);

const selectedKeys = computed(() => {
  const card = props.selectedCommander;
  if (!card?.setCode || card?.collectorNumber == null) {
    return null;
  }
  return new Set([`${card.setCode}|${card.collectorNumber}|${cardFinish(card)}`]);
});

function selectCommander(card) {
  emit("select", card);
}
</script>

<template>
  <section class="deck-builder-step deck-builder-commander-step">
    <header class="deck-builder-step-head">
      <h3>Pick your commander</h3>
      <p>Choose a legendary creature or planeswalker you own.</p>
    </header>

    <div v-if="selectedCommander" class="deck-builder-selected-commander">
      <img
        v-if="selectedCommander.imageUri"
        :src="selectedCommander.imageUri"
        :alt="selectedCommander.cardName || selectedCommander.name"
        loading="lazy"
      />
      <div>
        <strong>{{ selectedCommander.cardName || selectedCommander.name }}</strong>
        <ManaSymbols :colors="selectedCommander.colorIdentity || selectedCommander.colors || []" />
      </div>
    </div>

    <CommanderGalleryPicker
      :selected-keys="selectedKeys"
      @pick-card="selectCommander"
    />
  </section>
</template>
