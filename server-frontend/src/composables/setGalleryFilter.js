import { ref, watch } from "vue";

const SET_GALLERY_PREFS_KEY = "setGalleryPrefs";

const setGalleryFilter = ref("");
const setGalleryCollapsed = ref(false);
let prefsLoaded = false;

function loadSetGalleryPrefs() {
  if (prefsLoaded) {
    return;
  }
  prefsLoaded = true;
  try {
    const parsed = JSON.parse(localStorage.getItem(SET_GALLERY_PREFS_KEY) || "{}");
    setGalleryCollapsed.value = Boolean(parsed.collapsed);
  } catch {
    setGalleryCollapsed.value = false;
  }
}

function storeSetGalleryPrefs() {
  localStorage.setItem(
    SET_GALLERY_PREFS_KEY,
    JSON.stringify({ collapsed: setGalleryCollapsed.value }),
  );
}

watch(setGalleryCollapsed, storeSetGalleryPrefs);

export function useSetGalleryFilter() {
  loadSetGalleryPrefs();
  return { setGalleryFilter, setGalleryCollapsed };
}
