import { ref, watch } from "vue";

const STORAGE_KEY = "showSetBrowserSubsets";

function readStoredSubsets() {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

const setGalleryFilter = ref("");
/** When false, token / art card / promo / minigame family subtiles stay hidden. */
const showSetBrowserSubsets = ref(readStoredSubsets());

watch(showSetBrowserSubsets, (value) => {
  try {
    localStorage.setItem(STORAGE_KEY, value ? "1" : "0");
  } catch {
    // Ignore quota / private-mode failures.
  }
});

export function useSetGalleryFilter() {
  return { setGalleryFilter, showSetBrowserSubsets };
}
