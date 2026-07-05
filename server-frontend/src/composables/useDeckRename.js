import { nextTick, ref } from "vue";
import { api, clearClientCache } from "../api";
export function useDeckRename(getDeckId, getDeckName, onRenamed) {
  const renaming = ref(false);
  const draft = ref("");
  const error = ref("");
  const saving = ref(false);
  const inputRef = ref(null);

  function startRename() {
    draft.value = getDeckName() || "";
    error.value = "";
    renaming.value = true;
    nextTick(() => {
      inputRef.value?.focus();
      inputRef.value?.select();
    });
  }

  function cancelRename() {
    renaming.value = false;
    error.value = "";
  }

  function onRenameBlur() {
    if (!renaming.value || saving.value) {
      return;
    }    const name = draft.value.trim();
    const original = (getDeckName() || "").trim();
    if (!name || name === original) {
      cancelRename();
      return;
    }
    void saveRename();
  }

  async function saveRename() {
    const name = draft.value.trim();
    const deckId = getDeckId();
    if (!name || saving.value || !deckId) {
      return;
    }
    if (name === (getDeckName() || "").trim()) {
      cancelRename();
      return;
    }
    saving.value = true;
    error.value = "";
    try {
      const result = await api.renameDeck(deckId, { name });
      renaming.value = false;
      clearClientCache();
      await onRenamed?.(result?.deck);    } catch (err) {
      error.value = err.message || "Could not rename deck.";
    } finally {
      saving.value = false;
    }
  }

  return {
    renaming,
    draft,
    error,
    saving,
    inputRef,
    startRename,
    cancelRename,
    onRenameBlur,
    saveRename,
  };
}
