import { ref } from "vue";

const deckGalleryFilter = ref("");

export function useDeckGalleryFilter() {
  return { deckGalleryFilter };
}
