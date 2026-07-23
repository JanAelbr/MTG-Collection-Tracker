<script setup>
import "../styles/scan.css";
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import { api } from "../api";
import { terminateOcrWorker } from "../utils/cardOcr";
import { scoreCardPresenceInGuide } from "../utils/cardPresence";
import { cropGuideImageData, scoreFoilFromImageData } from "../utils/foilDetect";
import {
  AUTO_PICK_MAX_PRINTS,
  computeArtAHash,
  pickAutoArtMatch,
  rankPrintsByArt,
} from "../utils/cardArtCompare";
import { FINISH_FOIL, FINISH_NONFOIL, cardRouteQuery, finishLabel } from "../utils/finishes";
import { playScanSuccess } from "../utils/scanSounds";
import { normalizeCardTitle } from "../utils/cardTitle";

const FINISH_MODE_AUTO = "auto";
const FINISH_MODE_NONFOIL = "nonfoil";
const FINISH_MODE_FOIL = "foil";
const HARD_COOLDOWN_MS = 1100;
const SOFT_COOLDOWN_MS = 400;
const STABLE_FRAMES = 3;
const MOTION_THRESHOLD = 14;
const IDLE_HINT = "Center the card in the guide — matching uses art, not text";

const videoRef = ref(null);
const frameCanvasRef = ref(null);
const stageRef = ref(null);

const cameraError = ref("");
const statusMessage = ref(IDLE_HINT);
const statusKind = ref("idle"); // idle | success | fail | working
const finishMode = ref(FINISH_MODE_AUTO);
const sessionItems = ref([]);
const busy = ref(false);
const livePhase = ref("waiting"); // waiting | moving | steady | reading | confirming | picking
const namePicker = ref({
  open: false,
  query: "",
  resolvedName: "",
  nameOptions: [],
  variants: [],
  loading: false,
  error: "",
  finish: FINISH_NONFOIL,
  probeImage: null,
});
const diagnostics = ref({
  motion: null,
  cardSeen: null,
  cardScore: null,
  titleText: "",
  titleConfidence: null,
  lastDetail: "Start by centering a modern-frame card in the guide.",
});

let mediaStream = null;
let rafId = 0;
let lastGray = null;
let stableCount = 0;
let cooldownUntil = 0;
let lastFingerprint = "";
let pendingIdentityKey = "";
let disposed = false;

const finishModes = [
  { id: FINISH_MODE_AUTO, label: "Auto" },
  { id: FINISH_MODE_NONFOIL, label: "Non-foil" },
  { id: FINISH_MODE_FOIL, label: "Foil" },
];

const statusClass = computed(() => `scan-status is-${statusKind.value}`);
const phaseLabel = computed(() => {
  switch (livePhase.value) {
    case "moving":
      return "Hold still";
    case "steady":
      return "Steady";
    case "reading":
      return "Reading…";
    case "confirming":
      return "Confirming…";
    case "picking":
      return "Pick a print";
    default:
      return "Looking for a card";
  }
});

const scanningPaused = computed(() => namePicker.value.open);

const parsedLabel = computed(() => {
  const title = (diagnostics.value.titleText || "").replace(/^\(no title\)$/i, "").trim();
  if (title && !title.startsWith("(")) {
    return title;
  }
  return "—";
});

function patchDiagnostics(partial) {
  diagnostics.value = { ...diagnostics.value, ...partial };
}

function cardLink(item) {
  return {
    name: "card",
    params: {
      setCode: item.setCode,
      collectorNumber: item.collectorNumber,
    },
    query: cardRouteQuery(item.finish),
  };
}

function resetNamePicker() {
  namePicker.value = {
    open: false,
    query: "",
    resolvedName: "",
    nameOptions: [],
    variants: [],
    loading: false,
    error: "",
    finish: FINISH_NONFOIL,
    probeImage: null,
  };
}

async function loadNamePickerVariants(query, { preferName = "", probeImage = null } = {}) {
  const trimmed = String(query || "").trim();
  const probe = probeImage || namePicker.value.probeImage;
  namePicker.value.loading = true;
  namePicker.value.error = "";
  namePicker.value.variants = [];
  try {
    if (!trimmed && !preferName) {
      namePicker.value.error = "Enter a card name to search.";
      return { names: [], prints: [], resolvedName: "" };
    }
    const payload = await api.scanNameSearch({
      q: trimmed,
      ...(preferName ? { name: preferName } : {}),
      limit: 10,
    });
    const names = (payload.names || []).map((row) => row.name).filter(Boolean);
    const resolvedName = payload.resolvedName || names[0] || preferName || "";
    let prints = payload.prints || [];
    if (probe && prints.length) {
      setStatus("working", `Comparing ${prints.length} print${prints.length === 1 ? "" : "s"}…`);
      prints = await rankPrintsByArt(probe, prints);
    }
    namePicker.value.nameOptions = names;
    namePicker.value.resolvedName = resolvedName;
    namePicker.value.query = trimmed || resolvedName;
    namePicker.value.variants = prints;
    if (!resolvedName) {
      namePicker.value.error = `No cards found for “${trimmed}”.`;
    } else if (!prints.length) {
      namePicker.value.error = `No printings found for “${resolvedName}”.`;
    }
    return { names, prints, resolvedName };
  } catch (error) {
    namePicker.value.error = error?.message || "Could not load printings.";
    namePicker.value.variants = [];
    return { names: [], prints: [], resolvedName: "" };
  } finally {
    namePicker.value.loading = false;
  }
}

function showNamePicker(nameHint, finish, prints = [], names = []) {
  pendingIdentityKey = "";
  livePhase.value = "picking";
  setStatus("working", "Pick the set / art");
  namePicker.value = {
    ...namePicker.value,
    open: true,
    query: nameHint,
    resolvedName: names[0] || namePicker.value.resolvedName || nameHint,
    nameOptions: names.length ? names : namePicker.value.nameOptions,
    variants: prints,
    loading: false,
    error: "",
    finish,
  };
  const reason =
    prints.length > AUTO_PICK_MAX_PRINTS
      ? `${prints.length} printings — pick the matching art.`
      : "No clear art match — pick the printing.";
  patchDiagnostics({ lastDetail: reason });
}

async function applyIngestResult(result, { via = "scan" } = {}) {
  lastFingerprint =
    identityKey({
      setCode: result.setCode,
      collectorNumber: result.collectorNumber,
      nameHint: result.name,
    }) + `|${result.finish}`;
  sessionItems.value = [
    {
      id: `${result.instanceId || Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      instanceId: result.instanceId,
      name: result.name,
      setCode: result.setCode,
      collectorNumber: result.collectorNumber,
      finish: result.finish,
      imageUri: result.imageUri,
      ownedCount: result.ownedCount,
      at: Date.now(),
    },
    ...sessionItems.value,
  ].slice(0, 40);
  playScanSuccess();
  resetNamePicker();
  livePhase.value = "waiting";
  const importedNote = result.setImported ? " · set synced" : "";
  setStatus(
    "success",
    `${result.name} · ${finishLabel(result.finish)} · ×${result.ownedCount}${importedNote}`,
  );
  patchDiagnostics({
    lastDetail: `Added ${result.name} (${result.setCode} #${result.collectorNumber} via ${via}).`,
  });
  armCooldown(HARD_COOLDOWN_MS, true);
}

/**
 * Name readable but set missing: compare preview arts and auto-add a clear winner.
 */
/**
 * Visual ID: match camera art hash to catalog preview fingerprints.
 * Falls back to manual name search when the index is cold or matches are unclear.
 */
async function resolveByArtHash(artHash, finish, probeImage) {
  pendingIdentityKey = "";
  livePhase.value = "picking";
  setStatus("working", "Matching art…");
  patchDiagnostics({
    lastDetail: "Comparing card art to catalog fingerprints (no OCR).",
  });
  namePicker.value = {
    open: false,
    query: "",
    resolvedName: "",
    nameOptions: [],
    variants: [],
    loading: true,
    error: "",
    finish,
    probeImage,
  };

  try {
    let payload = await api.scanArtSearch({
      artHash,
      limit: 16,
      buildMissing: true,
    });
    const hashed = Number(payload.coverage?.hashed || 0);
    if (!(payload.prints || []).length || hashed < 40) {
      setStatus("working", "Indexing catalog art…");
      patchDiagnostics({
        lastDetail: "Building art fingerprints from preview images (first run is slower).",
      });
      await api.scanArtIndex(120);
      payload = await api.scanArtSearch({
        artHash,
        limit: 16,
        buildMissing: false,
      });
    }

    const prints = payload.prints || [];
    if (!prints.length) {
      showNamePicker("", finish, [], []);
      namePicker.value.error =
        "No art matches yet — type the card name, or wait while more previews are indexed.";
      patchDiagnostics({
        lastDetail: `Art index coverage ${Math.round((payload.coverage?.coverage || 0) * 100)}%.`,
      });
      return;
    }

    const names = [];
    const seen = new Set();
    for (const print of prints) {
      const name = String(print.name || "").trim();
      if (!name || seen.has(name)) {
        continue;
      }
      seen.add(name);
      names.push(name);
    }

    const auto = pickAutoArtMatch(prints);
    if (auto) {
      setStatus("working", `Matched ${auto.name}…`);
      patchDiagnostics({
        lastDetail: `Art match ${auto.setCode} #${auto.collectorNumber} (distance ${auto.artDistance}).`,
      });
      try {
        const result = await api.ingestScan({
          setCode: auto.setCode,
          collectorNumber: String(auto.collectorNumber),
          finish,
          nameHint: auto.name,
        });
        await applyIngestResult(result, { via: "art-hash" });
        return;
      } catch (error) {
        showNamePicker(auto.name || "", finish, prints, names);
        namePicker.value.resolvedName = auto.name || "";
        namePicker.value.error = error?.message || "Could not add the matched print.";
        return;
      }
    }

    showNamePicker(names[0] || "", finish, prints, names);
    namePicker.value.resolvedName = names[0] || "";
    namePicker.value.query = names[0] || "";
  } catch (error) {
    showNamePicker("", finish, [], []);
    namePicker.value.error = error?.message || "Art matching failed — type the card name.";
  } finally {
    namePicker.value.loading = false;
  }
}

async function resolveByNameArt(nameHint, finish, probeImage) {
  pendingIdentityKey = "";
  livePhase.value = "picking";
  setStatus("working", "Finding printings…");
  patchDiagnostics({
    lastDetail: `Read “${nameHint}” — comparing art to catalog previews.`,
  });
  namePicker.value = {
    open: false,
    query: nameHint,
    resolvedName: "",
    nameOptions: [],
    variants: [],
    loading: true,
    error: "",
    finish,
    probeImage,
  };

  const { prints, names, resolvedName } = await loadNamePickerVariants(nameHint, {
    probeImage,
  });
  if (!prints.length) {
    showNamePicker(nameHint, finish, [], names);
    if (!namePicker.value.error) {
      namePicker.value.error = resolvedName
        ? `No printings found for “${resolvedName}”.`
        : `No cards found for “${nameHint}”.`;
    }
    return;
  }

  const auto = pickAutoArtMatch(prints);
  if (auto) {
    setStatus("working", `Matched ${auto.setCode} #${auto.collectorNumber}…`);
    patchDiagnostics({
      lastDetail: `Auto-picked ${auto.setCode} #${auto.collectorNumber} (art ${(auto.artScore * 100).toFixed(0)}%).`,
    });
    try {
      const result = await api.ingestScan({
        setCode: auto.setCode,
        collectorNumber: String(auto.collectorNumber),
        finish,
        nameHint: resolvedName || nameHint,
      });
      await applyIngestResult(result, { via: "art-match" });
    } catch (error) {
      showNamePicker(nameHint, finish, prints, names);
      namePicker.value.resolvedName = resolvedName || nameHint;
      namePicker.value.error = error?.message || "Could not add the matched print.";
    }
    return;
  }

  showNamePicker(nameHint, finish, prints, names);
  namePicker.value.resolvedName = resolvedName || nameHint;
}

async function openNamePicker(nameHint, finish) {
  namePicker.value.finish = finish;
  showNamePicker(nameHint, finish);
  await loadNamePickerVariants(nameHint);
}

async function refreshNamePicker() {
  if (!namePicker.value.open || namePicker.value.loading) {
    return;
  }
  await loadNamePickerVariants(namePicker.value.query);
}

async function selectPickerName(name) {
  if (!namePicker.value.open || namePicker.value.loading) {
    return;
  }
  await loadNamePickerVariants(namePicker.value.query || name, { preferName: name });
}

function closeNamePicker({ resumeMessage = "Ready for next card" } = {}) {
  resetNamePicker();
  livePhase.value = "waiting";
  setStatus("idle", resumeMessage);
  armCooldown(SOFT_COOLDOWN_MS, false);
}

async function choosePickerVariant(variant) {
  if (!variant || namePicker.value.loading || busy.value) {
    return;
  }
  busy.value = true;
  namePicker.value.loading = true;
  try {
    const finish = namePicker.value.finish;
    const result = await api.ingestScan({
      setCode: variant.setCode,
      collectorNumber: String(variant.collectorNumber),
      finish,
      nameHint: namePicker.value.resolvedName || variant.name || namePicker.value.query,
    });
    await applyIngestResult(result, { via: "picker" });
  } catch (error) {
    namePicker.value.error = error?.message || "Could not add that print.";
  } finally {
    namePicker.value.loading = false;
    busy.value = false;
  }
}

function setStatus(kind, message) {
  statusKind.value = kind;
  statusMessage.value = message;
}

function guideRectForCanvas(canvas) {
  const width = canvas.width;
  const height = canvas.height;
  const targetRatio = 63 / 88;
  let guideWidth = width * 0.72;
  let guideHeight = guideWidth / targetRatio;
  if (guideHeight > height * 0.78) {
    guideHeight = height * 0.78;
    guideWidth = guideHeight * targetRatio;
  }
  return {
    x: (width - guideWidth) / 2,
    y: (height - guideHeight) / 2,
    width: guideWidth,
    height: guideHeight,
  };
}

function frameToGray(ctx, width, height) {
  const image = ctx.getImageData(0, 0, width, height);
  const step = Math.max(2, Math.floor(Math.sqrt((width * height) / 4000)));
  const samples = [];
  for (let y = 0; y < height; y += step) {
    for (let x = 0; x < width; x += step) {
      const i = (y * width + x) * 4;
      samples.push(image.data[i] * 0.299 + image.data[i + 1] * 0.587 + image.data[i + 2] * 0.114);
    }
  }
  return samples;
}

function motionScore(prev, next) {
  if (!prev || !next || prev.length !== next.length) {
    return 999;
  }
  let total = 0;
  for (let i = 0; i < prev.length; i += 1) {
    total += Math.abs(prev[i] - next[i]);
  }
  return total / prev.length;
}

function resolveFinish(detectedFoil) {
  if (finishMode.value === FINISH_MODE_FOIL) {
    return FINISH_FOIL;
  }
  if (finishMode.value === FINISH_MODE_NONFOIL) {
    return FINISH_NONFOIL;
  }
  return detectedFoil ? FINISH_FOIL : FINISH_NONFOIL;
}

function identityKey(identity) {
  const title = normalizeCardTitle(identity.nameHint || "");
  if (title) {
    return `${identity.setCode}|${title}`;
  }
  return `${identity.setCode}|#${identity.collectorNumber || ""}`;
}

async function startCamera() {
  cameraError.value = "";
  const mediaDevices = navigator.mediaDevices;
  if (!mediaDevices || typeof mediaDevices.getUserMedia !== "function") {
    const insecure = typeof window.isSecureContext === "boolean" && !window.isSecureContext;
    cameraError.value = insecure
      ? "Camera needs HTTPS. Restart with .\\scripts\\run_app.ps1 -Lan and open the https:// URL (accept the certificate warning)."
      : "Camera API is unavailable in this browser.";
    setStatus("fail", "Camera unavailable");
    patchDiagnostics({ lastDetail: cameraError.value });
    return;
  }
  try {
    mediaStream = await mediaDevices.getUserMedia({
      audio: false,
      video: {
        facingMode: { ideal: "environment" },
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
    });
  } catch (error) {
    cameraError.value = error?.message || "Camera permission denied";
    setStatus("fail", "Camera unavailable");
    patchDiagnostics({ lastDetail: cameraError.value });
    return;
  }
  await nextTick();
  const video = videoRef.value;
  if (!video) {
    return;
  }
  video.srcObject = mediaStream;
  await video.play().catch(() => {});
  setStatus("idle", IDLE_HINT);
  loop();
}

function stopCamera() {
  if (rafId) {
    cancelAnimationFrame(rafId);
    rafId = 0;
  }
  if (mediaStream) {
    for (const track of mediaStream.getTracks()) {
      track.stop();
    }
    mediaStream = null;
  }
  const video = videoRef.value;
  if (video) {
    video.srcObject = null;
  }
}

function drawVideoFrame() {
  const video = videoRef.value;
  const canvas = frameCanvasRef.value;
  if (!video || !canvas || video.readyState < 2) {
    return null;
  }
  const width = video.videoWidth || 640;
  const height = video.videoHeight || 480;
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(video, 0, 0, width, height);
  return { canvas, ctx, width, height };
}

function softMiss(message = IDLE_HINT, detail = null) {
  pendingIdentityKey = "";
  livePhase.value = "waiting";
  setStatus("idle", message);
  if (detail) {
    patchDiagnostics({ lastDetail: detail });
  }
  armCooldown(SOFT_COOLDOWN_MS, false);
}

function hardFail(message, detail = null) {
  pendingIdentityKey = "";
  livePhase.value = "waiting";
  setStatus("fail", message);
  patchDiagnostics({ lastDetail: detail || message });
  armCooldown(HARD_COOLDOWN_MS, true);
}

async function processStableFrame(canvas, { manual = false } = {}) {
  if (busy.value || disposed || namePicker.value.open) {
    return;
  }
  busy.value = true;
  livePhase.value = "reading";
  try {
    const guide = guideRectForCanvas(canvas);
    const presence = scoreCardPresenceInGuide(canvas, guide);
    patchDiagnostics({
      cardSeen: presence.looksLikeCard,
      cardScore: Number(presence.score.toFixed(2)),
    });
    if (!presence.looksLikeCard && !manual) {
      softMiss(
        "No card detected in the guide",
        `Presence score ${presence.score.toFixed(2)} — fill more of the frame with the card face.`,
      );
      return;
    }
    if (!presence.looksLikeCard) {
      softMiss(
        "No card in frame",
        "Hold the card inside the guide, then try again.",
      );
      return;
    }

    const foilImage = cropGuideImageData(canvas, guide);
    const foil = foilImage ? scoreFoilFromImageData(foilImage) : { isFoil: false };
    const finish = resolveFinish(Boolean(foil.isFoil));
    const artHash = foilImage ? computeArtAHash(foilImage) : "";
    patchDiagnostics({
      titleText: artHash ? `hash ${artHash.slice(0, 8)}…` : "(no art hash)",
      titleConfidence: null,
    });
    if (!artHash) {
      showNamePicker("", finish, [], []);
      namePicker.value.probeImage = foilImage;
      namePicker.value.error = "Could not fingerprint this frame — type the card name.";
      return;
    }

    const key = identityKey({ nameHint: artHash, setCode: "", collectorNumber: null });
    if (!manual && pendingIdentityKey !== key) {
      pendingIdentityKey = key;
      livePhase.value = "confirming";
      setStatus("working", "Card seen — hold for confirm");
      patchDiagnostics({
        lastDetail: "Hold steady for a second confirmation frame.",
      });
      armCooldown(SOFT_COOLDOWN_MS, false);
      return;
    }
    pendingIdentityKey = "";

    const fingerprint = `${key}|${finish}`;
    if (!manual && fingerprint === lastFingerprint && Date.now() < cooldownUntil + 1500) {
      softMiss("Already added — next card", "Same art fingerprint as the last successful scan.");
      return;
    }

    await resolveByArtHash(artHash, finish, foilImage);
  } catch (error) {
    hardFail(error?.message || "Scan failed", error?.message || "Request failed");
  } finally {
    busy.value = false;
  }
}

function armCooldown(ms, resetIdleHint) {
  cooldownUntil = Date.now() + ms;
  stableCount = 0;
  lastGray = null;
  if (resetIdleHint) {
    window.setTimeout(() => {
      if (!disposed && statusKind.value !== "working") {
        setStatus("idle", "Ready for next card");
      }
    }, 450);
  }
}

async function scanNow() {
  if (busy.value || disposed || namePicker.value.open) {
    return;
  }
  const frame = drawVideoFrame();
  if (!frame) {
    setStatus("fail", "Camera not ready");
    return;
  }
  cooldownUntil = 0;
  await processStableFrame(frame.canvas, { manual: true });
}

function loop() {
  if (disposed) {
    return;
  }
  rafId = requestAnimationFrame(loop);
  if (busy.value || namePicker.value.open || Date.now() < cooldownUntil) {
    return;
  }
  const frame = drawVideoFrame();
  if (!frame) {
    return;
  }
  const gray = frameToGray(frame.ctx, frame.width, frame.height);
  const motion = motionScore(lastGray, gray);
  lastGray = gray;
  patchDiagnostics({ motion: Number(motion.toFixed(1)) });
  if (motion > MOTION_THRESHOLD) {
    stableCount = 0;
    livePhase.value = "moving";
    if (statusKind.value === "idle") {
      setStatus("idle", "Hold steady…");
    }
    return;
  }
  livePhase.value = "steady";
  stableCount += 1;
  if (stableCount >= STABLE_FRAMES) {
    stableCount = 0;
    processStableFrame(frame.canvas);
  }
}

async function undoItem(item) {
  if (!item?.instanceId) {
    sessionItems.value = sessionItems.value.filter((row) => row.id !== item.id);
    return;
  }
  try {
    await api.deleteCardInstance(item.instanceId);
    sessionItems.value = sessionItems.value.filter((row) => row.id !== item.id);
    setStatus("idle", `Removed ${item.name}`);
  } catch (error) {
    hardFail(error?.message || "Could not undo");
  }
}

onMounted(() => {
  disposed = false;
  startCamera();
});

onBeforeUnmount(() => {
  disposed = true;
  stopCamera();
  terminateOcrWorker();
});
</script>

<template>
  <section class="scan-page">
    <div class="scan-toolbar">
      <div class="scan-finish-modes" role="group" aria-label="Finish mode">
        <button
          v-for="mode in finishModes"
          :key="mode.id"
          type="button"
          class="scan-finish-btn"
          :class="{ active: finishMode === mode.id }"
          @click="finishMode = mode.id"
        >
          {{ mode.label }}
        </button>
      </div>
      <button
        type="button"
        class="scan-now-btn"
        :disabled="busy || scanningPaused || Boolean(cameraError)"
        @click="scanNow"
      >
        {{ busy ? "Scanning…" : scanningPaused ? "Paused" : "Scan now" }}
      </button>
    </div>

    <p :class="statusClass" role="status">{{ statusMessage }}</p>

    <div
      ref="stageRef"
      class="scan-stage"
      :class="[`is-${statusKind}`, { 'is-paused': scanningPaused }]"
    >
      <video
        ref="videoRef"
        class="scan-video"
        playsinline
        muted
        autoplay
      />
      <canvas ref="frameCanvasRef" class="scan-frame-canvas" aria-hidden="true" />
      <div class="scan-guide" aria-hidden="true" />
      <div class="scan-stage-hud" aria-live="polite">
        <span class="scan-phase-pill" :class="`is-${livePhase}`">{{ phaseLabel }}</span>
        <span
          class="scan-phase-pill"
          :class="diagnostics.cardSeen ? 'is-ok' : 'is-warn'"
        >
          {{ diagnostics.cardSeen ? "Card in frame" : "No card yet" }}
        </span>
      </div>
      <p v-if="cameraError" class="scan-camera-error">{{ cameraError }}</p>
      <div v-if="scanningPaused" class="scan-paused-banner" aria-live="polite">
        Scanning paused — choose a printing below
      </div>
    </div>

    <div
      v-if="namePicker.open"
      class="scan-picker"
      role="dialog"
      aria-modal="true"
      aria-label="Choose printing"
    >
      <div class="scan-picker-head">
        <div>
          <h2>Choose set / art</h2>
          <p>Type a name if needed, or tap the best art match.</p>
        </div>
        <button
          type="button"
          class="scan-picker-cancel"
          :disabled="busy"
          @click="closeNamePicker()"
        >
          Cancel
        </button>
      </div>

      <form class="scan-picker-search" @submit.prevent="refreshNamePicker">
        <label class="scan-diag-label" for="scan-picker-name">Card name</label>
        <div class="scan-picker-search-row">
          <input
            id="scan-picker-name"
            v-model="namePicker.query"
            type="search"
            autocomplete="off"
            enterkeyhint="search"
            :disabled="namePicker.loading || busy"
            placeholder="Edit OCR name if needed"
          />
          <button type="submit" :disabled="namePicker.loading || busy">
            {{ namePicker.loading ? "Loading…" : "Search" }}
          </button>
        </div>
      </form>

      <div v-if="namePicker.nameOptions.length > 1" class="scan-picker-names">
        <button
          v-for="name in namePicker.nameOptions"
          :key="name"
          type="button"
          class="scan-picker-name-chip"
          :class="{ active: name === namePicker.resolvedName }"
          :disabled="namePicker.loading || busy"
          @click="selectPickerName(name)"
        >
          {{ name }}
        </button>
      </div>

      <p v-if="namePicker.error" class="scan-picker-error">{{ namePicker.error }}</p>
      <p v-else-if="namePicker.loading" class="scan-picker-empty">Loading printings…</p>
      <p v-else-if="!namePicker.variants.length" class="scan-picker-empty">
        No printings to show.
      </p>
      <ul v-else class="scan-picker-grid">
        <li
          v-for="(variant, index) in namePicker.variants"
          :key="`${variant.setCode}-${variant.collectorNumber}-${variant.artStyle || ''}`"
        >
          <button
            type="button"
            class="scan-picker-card"
            :class="{ 'is-top-match': index === 0 && variant.artScore }"
            :disabled="namePicker.loading || busy"
            @click="choosePickerVariant(variant)"
          >
            <img
              v-if="variant.imageUri"
              :src="variant.imageUri"
              :alt="variant.name || namePicker.resolvedName"
              loading="lazy"
            />
            <div v-else class="scan-picker-card-empty" />
            <span class="scan-picker-card-meta">
              <strong>{{ variant.setCode }} #{{ variant.collectorNumber }}</strong>
              <em v-if="variant.artScore != null">
                {{ Math.round(variant.artScore * 100) }}% match
              </em>
              <em v-else-if="variant.artStyle">{{ variant.artStyle }}</em>
            </span>
          </button>
        </li>
      </ul>
    </div>

    <div class="scan-diagnostics">
      <div class="scan-diagnostics-grid">
        <div>
          <span class="scan-diag-label">Motion</span>
          <strong>{{ diagnostics.motion ?? "—" }}</strong>
        </div>
        <div>
          <span class="scan-diag-label">Card score</span>
          <strong>{{ diagnostics.cardScore ?? "—" }}</strong>
        </div>
        <div>
          <span class="scan-diag-label">Fingerprint</span>
          <strong>{{ parsedLabel }}</strong>
        </div>
        <div>
          <span class="scan-diag-label">Phase</span>
          <strong>{{ phaseLabel }}</strong>
        </div>
      </div>
      <p class="scan-diag-detail">{{ diagnostics.lastDetail }}</p>
      <ul class="scan-tips">
        <li>Matching uses card art fingerprints — OCR is no longer required.</li>
        <li>First runs index preview images; later scans are much faster.</li>
        <li>If art is unsure, type a name in the picker (quick search still works).</li>
        <li>Bright, even light helps art matching.</li>
      </ul>
    </div>

    <div class="scan-feed">
      <div class="scan-feed-head">
        <h2>This session</h2>
        <span v-if="sessionItems.length">{{ sessionItems.length }}</span>
      </div>
      <p v-if="!sessionItems.length" class="scan-feed-empty">
        Successful scans show up here.
      </p>
      <ul v-else class="scan-feed-list">
        <li v-for="item in sessionItems" :key="item.id" class="scan-feed-item">
          <RouterLink :to="cardLink(item)" class="scan-feed-link">
            <img
              v-if="item.imageUri"
              :src="item.imageUri"
              :alt="item.name"
              class="scan-feed-thumb"
            />
            <div v-else class="scan-feed-thumb scan-feed-thumb-empty" />
            <div class="scan-feed-meta">
              <strong>{{ item.name }}</strong>
              <span>
                {{ item.setCode }} #{{ item.collectorNumber }}
                · {{ finishLabel(item.finish) }}
                · ×{{ item.ownedCount }}
              </span>
            </div>
          </RouterLink>
          <button
            type="button"
            class="scan-feed-undo"
            :disabled="!item.instanceId"
            @click="undoItem(item)"
          >
            Undo
          </button>
        </li>
      </ul>
    </div>
  </section>
</template>
