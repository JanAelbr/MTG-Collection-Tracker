import { computed, ref } from "vue";
import { api, clearClientCache, ignoreAborted } from "../api";

const settings = ref(null);
const LEGACY_PAGE_SIZE_KEY = "reportPageSize";

export async function fetchPricingSettings(force = false) {
  if (!force && settings.value) {
    return settings.value;
  }
  const next = await ignoreAborted(api.getSettings());
  if (next) {
    settings.value = next;
  }
  return settings.value;
}

export async function savePricingSettings(patch) {
  const next = await ignoreAborted(api.updateSettings(patch));
  if (!next) {
    return settings.value;
  }
  settings.value = next;
  if (patch.pageSize != null) {
    localStorage.setItem(LEGACY_PAGE_SIZE_KEY, String(settings.value.pageSize));
  }
  const strategyOnly = Object.keys(patch).length === 1 && patch.priceStrategy != null;
  if (!strategyOnly) {
    clearClientCache();
  }
  return settings.value;
}

export function usePricingSettings() {
  const pageSize = computed(() => settings.value?.pageSize ?? 25);
  const collectionCardScale = computed(() => settings.value?.collectionCardScale ?? 100);
  const setPickerMode = computed(() => settings.value?.setPickerMode ?? "dropdown");

  return {
    settings,
    pageSize,
    collectionCardScale,
    setPickerMode,
    fetchPricingSettings,
    savePricingSettings,
  };
}
