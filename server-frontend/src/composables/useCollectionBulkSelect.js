import { ref, watch } from "vue";
import { cardSelectionKey } from "../utils/collectionScopeStats";

export function useCollectionBulkSelect() {
  const bulkSelectMode = ref(false);
  const selectedKeys = ref(new Set());
  const bulkBusy = ref(false);
  const focusedIndex = ref(-1);

  function toggleBulkMode() {
    bulkSelectMode.value = !bulkSelectMode.value;
    if (!bulkSelectMode.value) {
      selectedKeys.value = new Set();
      focusedIndex.value = -1;
    }
  }

  function toggleCardSelection(card) {
    const key = cardSelectionKey(card);
    const next = new Set(selectedKeys.value);
    if (next.has(key)) {
      next.delete(key);
    } else {
      next.add(key);
    }
    selectedKeys.value = next;
  }

  function clearSelection() {
    selectedKeys.value = new Set();
  }

  function isSelected(card) {
    return selectedKeys.value.has(cardSelectionKey(card));
  }

  function selectedCardsFrom(list) {
    const keys = selectedKeys.value;
    return list.filter((card) => keys.has(cardSelectionKey(card)));
  }

  watch(bulkSelectMode, (enabled) => {
    if (!enabled) {
      clearSelection();
      focusedIndex.value = -1;
    }
  });

  return {
    bulkSelectMode,
    selectedKeys,
    bulkBusy,
    focusedIndex,
    toggleBulkMode,
    toggleCardSelection,
    clearSelection,
    isSelected,
    selectedCardsFrom,
  };
}
