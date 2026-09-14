import { ref, watch } from "vue";
import {
  getStoredCatalogChromeExpanded,
  storeCatalogChromeExpanded,
} from "../utils/filterStorage";

const catalogChromeExpanded = ref(getStoredCatalogChromeExpanded());

watch(catalogChromeExpanded, (value) => {
  try {
    storeCatalogChromeExpanded(value);
  } catch {
    // Ignore quota / private-mode failures.
  }
});

export function useCatalogChrome() {
  function toggleCatalogChromeExpanded() {
    catalogChromeExpanded.value = !catalogChromeExpanded.value;
  }

  return { catalogChromeExpanded, toggleCatalogChromeExpanded };
}
