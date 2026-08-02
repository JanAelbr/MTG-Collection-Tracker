import { computed, ref } from "vue";
import { cardSelectionKey } from "../utils/collectionScopeStats";
import { cardDisplayName, cardFinish, normalizeFinish } from "../utils/finishes";

const PRINT_LIST_KEY = "lotr.printList";
const PRINT_SELECTED_KEY = "lotr.printList.selected";

const items = ref(loadItems());
const selectedKeys = ref(loadSelectedKeys(items.value));

function slimCard(card) {
  if (!card) {
    return null;
  }
  const setCode = card.setCode || card.set_code;
  const collectorNumber = card.collectorNumber ?? card.collector_number;
  if (!setCode || collectorNumber == null || collectorNumber === "") {
    return null;
  }
  const finish = cardFinish(card);
  return {
    setCode: String(setCode),
    collectorNumber: String(collectorNumber),
    finish,
    foil: finish,
    name: card.name || card.cardName || "",
    imageUri: card.imageUri || card.image_uri || "",
  };
}

function loadItems() {
  try {
    const raw = localStorage.getItem(PRINT_LIST_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed
      .map((entry) => slimCard(entry))
      .filter(Boolean);
  } catch {
    return [];
  }
}

function loadSelectedKeys(list) {
  const valid = new Set(list.map((card) => cardSelectionKey(card)));
  try {
    const raw = localStorage.getItem(PRINT_SELECTED_KEY);
    if (!raw) {
      return new Set(valid);
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return new Set(valid);
    }
    return new Set(parsed.filter((key) => valid.has(key)));
  } catch {
    return new Set(valid);
  }
}

function persistItems() {
  localStorage.setItem(PRINT_LIST_KEY, JSON.stringify(items.value));
}

function persistSelected() {
  localStorage.setItem(PRINT_SELECTED_KEY, JSON.stringify([...selectedKeys.value]));
}

function syncSelectedToItems() {
  const valid = new Set(items.value.map((card) => cardSelectionKey(card)));
  const next = new Set([...selectedKeys.value].filter((key) => valid.has(key)));
  selectedKeys.value = next;
  persistSelected();
}

export function usePrintList() {
  const count = computed(() => items.value.length);
  const selectedCount = computed(() => selectedKeys.value.size);
  const selectedCards = computed(() => (
    items.value.filter((card) => selectedKeys.value.has(cardSelectionKey(card)))
  ));

  function has(card) {
    const slim = slimCard(card);
    if (!slim) {
      return false;
    }
    const key = cardSelectionKey(slim);
    return items.value.some((entry) => cardSelectionKey(entry) === key);
  }

  function add(card) {
    const slim = slimCard(card);
    if (!slim) {
      return false;
    }
    const key = cardSelectionKey(slim);
    if (items.value.some((entry) => cardSelectionKey(entry) === key)) {
      return false;
    }
    items.value = [...items.value, slim];
    const nextSelected = new Set(selectedKeys.value);
    nextSelected.add(key);
    selectedKeys.value = nextSelected;
    persistItems();
    persistSelected();
    return true;
  }

  function remove(cardOrKey) {
    const key = typeof cardOrKey === "string"
      ? cardOrKey
      : cardSelectionKey(slimCard(cardOrKey) || cardOrKey || {});
    if (!key || key.includes("undefined") || key.startsWith("|")) {
      return false;
    }
    const prevLen = items.value.length;
    items.value = items.value.filter((entry) => cardSelectionKey(entry) !== key);
    if (items.value.length === prevLen) {
      return false;
    }
    const nextSelected = new Set(selectedKeys.value);
    nextSelected.delete(key);
    selectedKeys.value = nextSelected;
    persistItems();
    persistSelected();
    return true;
  }

  function toggle(card) {
    if (has(card)) {
      remove(card);
      return false;
    }
    add(card);
    return true;
  }

  function clear() {
    items.value = [];
    selectedKeys.value = new Set();
    persistItems();
    persistSelected();
  }

  function isSelected(cardOrKey) {
    const key = typeof cardOrKey === "string"
      ? cardOrKey
      : cardSelectionKey(slimCard(cardOrKey) || cardOrKey || {});
    return selectedKeys.value.has(key);
  }

  function toggleSelected(cardOrKey) {
    const key = typeof cardOrKey === "string"
      ? cardOrKey
      : cardSelectionKey(slimCard(cardOrKey) || cardOrKey || {});
    if (!key || !items.value.some((entry) => cardSelectionKey(entry) === key)) {
      return;
    }
    const next = new Set(selectedKeys.value);
    if (next.has(key)) {
      next.delete(key);
    } else {
      next.add(key);
    }
    selectedKeys.value = next;
    persistSelected();
  }

  function setSelected(cardOrKey, selected) {
    const key = typeof cardOrKey === "string"
      ? cardOrKey
      : cardSelectionKey(slimCard(cardOrKey) || cardOrKey || {});
    if (!key || !items.value.some((entry) => cardSelectionKey(entry) === key)) {
      return;
    }
    const next = new Set(selectedKeys.value);
    if (selected) {
      next.add(key);
    } else {
      next.delete(key);
    }
    selectedKeys.value = next;
    persistSelected();
  }

  function selectAll() {
    selectedKeys.value = new Set(items.value.map((card) => cardSelectionKey(card)));
    persistSelected();
  }

  function clearSelection() {
    selectedKeys.value = new Set();
    persistSelected();
  }

  function displayLabel(card) {
    return cardDisplayName(card, normalizeFinish(card?.finish));
  }

  return {
    items,
    selectedKeys,
    count,
    selectedCount,
    selectedCards,
    has,
    add,
    remove,
    toggle,
    clear,
    isSelected,
    toggleSelected,
    setSelected,
    selectAll,
    clearSelection,
    syncSelectedToItems,
    displayLabel,
  };
}
