import { reactive, readonly } from "vue";

const state = reactive({
  open: false,
  title: "Confirm",
  message: "",
  confirmLabel: "Confirm",
  cancelLabel: "Cancel",
  danger: false,
  busy: false,
  requireText: "",
  typed: "",
});

let resolvePromise = null;

function reset() {
  state.open = false;
  state.busy = false;
  state.requireText = "";
  state.typed = "";
  resolvePromise = null;
}

/**
 * Open a confirm dialog. Resolves true if confirmed, false if cancelled.
 * @param {{
 *   title?: string,
 *   message?: string,
 *   confirmLabel?: string,
 *   cancelLabel?: string,
 *   danger?: boolean,
 *   requireText?: string,
 * }} [options]
 */
export function confirmDialog(options = {}) {
  if (resolvePromise) {
    resolvePromise(false);
    resolvePromise = null;
  }
  state.title = options.title || "Confirm";
  state.message = options.message || "";
  state.confirmLabel = options.confirmLabel || "Confirm";
  state.cancelLabel = options.cancelLabel || "Cancel";
  state.danger = Boolean(options.danger);
  state.requireText = options.requireText || "";
  state.typed = "";
  state.busy = false;
  state.open = true;
  return new Promise((resolve) => {
    resolvePromise = resolve;
  });
}

export function setConfirmTyped(value) {
  state.typed = value;
}

export function acceptConfirmDialog() {
  if (state.requireText && state.typed !== state.requireText) {
    return;
  }
  if (!resolvePromise) {
    reset();
    return;
  }
  const resolve = resolvePromise;
  reset();
  resolve(true);
}

export function cancelConfirmDialog() {
  if (!resolvePromise) {
    reset();
    return;
  }
  const resolve = resolvePromise;
  reset();
  resolve(false);
}

export function useConfirmDialogState() {
  return readonly(state);
}
