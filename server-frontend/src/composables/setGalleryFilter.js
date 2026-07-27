import { ref } from "vue";

const setGalleryFilter = ref("");
/** When false, token / art card / promo / minigame family subtiles stay hidden. */
const showSetBrowserSubsets = ref(false);

export function useSetGalleryFilter() {
  return { setGalleryFilter, showSetBrowserSubsets };
}
