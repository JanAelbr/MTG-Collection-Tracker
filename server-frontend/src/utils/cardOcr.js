/**
 * Parse OCR text from a modern MTG card's collector-number line.
 * Expects patterns like "279/291" plus a nearby set code "CLU".
 */

import { stripTrailingManaCost, titleHintIsUsable } from "./cardTitle";

const SET_CODE_RE = /\b([A-Z0-9]{2,5})\b/g;
const NUMBER_SLASH_RE = /\b(\d{1,4}[A-Za-z]?)\s*\/\s*\d{1,4}\b/;
const STANDALONE_NUMBER_RE = /\b(\d{1,4}[A-Za-z]?)\b/;

export const MIN_OCR_CONFIDENCE = 45;

const NOISE_TOKENS = new Set([
  "EN",
  "DE",
  "FR",
  "IT",
  "ES",
  "PT",
  "JP",
  "JA",
  "KO",
  "ZHS",
  "ZHT",
  "PH",
  "C",
  "U",
  "R",
  "M",
  "L",
  "S",
  "T",
  "W",
  "B",
  "THE",
  "AND",
  "FOR",
  "SET",
  "CARD",
]);

export function isAlchemyCollectorNumber(collectorNumber) {
  return String(collectorNumber || "").trim().toUpperCase().startsWith("A-");
}

export function normalizeOcrText(raw) {
  return String(raw || "")
    .replace(/[|]/g, "I")
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[\u00B7\u2022\u2219\u22C5]/g, " ")
    .replace(/[^\w\s/#.-]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toUpperCase();
}

/** Common OCR confusions for set codes only (not collector numbers). */
export function fixOcrSetCode(code) {
  const upper = String(code || "").toUpperCase();
  if (!upper || /^\d+$/.test(upper)) {
    return upper;
  }
  // Prefer letter-looking substitutions in alpha-heavy codes
  return upper
    .replace(/0/g, "O")
    .replace(/1/g, "I")
    .replace(/5/g, "S");
}

export function setCodeCandidates(code) {
  const raw = String(code || "").toUpperCase();
  const fixed = fixOcrSetCode(raw);
  const variants = new Set([raw, fixed]);
  // Also try digit-looking forms when letters might have been wrong
  variants.add(
    raw
      .replace(/O/g, "0")
      .replace(/I/g, "1")
      .replace(/S/g, "5"),
  );
  return [...variants].filter(Boolean);
}

function extractSetCodes(text) {
  const codes = [];
  SET_CODE_RE.lastIndex = 0;
  let match = SET_CODE_RE.exec(text);
  while (match) {
    const code = match[1];
    if (!NOISE_TOKENS.has(code) && !/^\d+$/.test(code)) {
      codes.push(code);
    }
    match = SET_CODE_RE.exec(text);
  }
  return codes;
}

/**
 * @param {string} ocrText
 * @returns {{ setCode: string, collectorNumber: string | null, usedSlash: boolean } | null}
 */
export function parseCollectorAndSet(ocrText) {
  const text = normalizeOcrText(ocrText);
  if (!text) {
    return null;
  }
  if (/\bA-\d/i.test(text) || /\bA\s*-\s*\d/i.test(ocrText || "")) {
    return null;
  }

  let collectorNumber = null;
  let usedSlash = false;
  const slash = text.match(NUMBER_SLASH_RE);
  if (slash) {
    collectorNumber = slash[1];
    usedSlash = true;
  } else {
    const standalone = text.match(STANDALONE_NUMBER_RE);
    if (standalone) {
      collectorNumber = standalone[1];
    }
  }

  if (collectorNumber && isAlchemyCollectorNumber(collectorNumber)) {
    return null;
  }

  const setCodes = extractSetCodes(text);
  const rawSet =
    setCodes.find((code) => !collectorNumber || code !== collectorNumber.toUpperCase())
    || null;
  if (!rawSet) {
    return null;
  }

  return {
    setCode: fixOcrSetCode(rawSet),
    collectorNumber: collectorNumber ? String(collectorNumber).trim() : null,
    usedSlash,
  };
}

/**
 * Accept a parse when we have a set code, and either a confident number or set-only.
 */
export function acceptOcrParse(parsed, confidence, { allowSetOnly = true } = {}) {
  if (!parsed?.setCode) {
    return false;
  }
  if (parsed.collectorNumber) {
    if (parsed.usedSlash) {
      return true;
    }
    return Number(confidence) >= MIN_OCR_CONFIDENCE;
  }
  return Boolean(allowSetOnly);
}

function otsuThreshold(hist, total) {
  let sum = 0;
  for (let i = 0; i < 256; i += 1) {
    sum += i * hist[i];
  }
  let sumB = 0;
  let wB = 0;
  let maxVar = 0;
  let threshold = 128;
  for (let t = 0; t < 256; t += 1) {
    wB += hist[t];
    if (wB === 0) continue;
    const wF = total - wB;
    if (wF === 0) break;
    sumB += t * hist[t];
    const mB = sumB / wB;
    const mF = (sum - sumB) / wF;
    const between = wB * wF * (mB - mF) * (mB - mF);
    if (between > maxVar) {
      maxVar = between;
      threshold = t;
    }
  }
  return threshold;
}

/**
 * Upscale, grayscale, Otsu threshold, mild sharpen for Tesseract.
 * @param {HTMLCanvasElement} sourceBand
 * @param {number} [scale=2.5]
 */
export function preprocessCollectorBand(sourceBand, scale = 2.5) {
  const width = Math.max(1, Math.round(sourceBand.width * scale));
  const height = Math.max(1, Math.round(sourceBand.height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(sourceBand, 0, 0, width, height);
  const image = ctx.getImageData(0, 0, width, height);
  const data = image.data;
  const gray = new Uint8ClampedArray(width * height);
  const hist = new Array(256).fill(0);
  for (let i = 0, p = 0; i < data.length; i += 4, p += 1) {
    const g = Math.round(data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114);
    gray[p] = g;
    hist[g] += 1;
  }
  const threshold = otsuThreshold(hist, width * height);
  for (let i = 0, p = 0; i < data.length; i += 4, p += 1) {
    // Mild unsharp: boost local difference vs average of neighbors approximated by threshold path
    const value = gray[p] < threshold ? 0 : 255;
    data[i] = data[i + 1] = data[i + 2] = value;
    data[i + 3] = 255;
  }
  ctx.putImageData(image, 0, 0);
  return canvas;
}

/**
 * Crop the bottom band of a card-guide region for OCR (collector line).
 * @param {HTMLCanvasElement} sourceCanvas full frame
 * @param {{ x: number, y: number, width: number, height: number }} guide
 * @param {{ bandRatio?: number, liftRatio?: number }} [options]
 */
export function cropCollectorBand(sourceCanvas, guide, options = {}) {
  const bandRatio = options.bandRatio ?? 0.18;
  const liftRatio = options.liftRatio ?? 0.02;
  const bandHeight = Math.max(24, Math.round(guide.height * bandRatio));
  const y = Math.min(
    sourceCanvas.height - bandHeight,
    Math.round(guide.y + guide.height - bandHeight - guide.height * liftRatio),
  );
  const x = Math.max(0, Math.round(guide.x + guide.width * 0.05));
  const width = Math.min(
    sourceCanvas.width - x,
    Math.round(guide.width * 0.9),
  );
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, width);
  canvas.height = Math.max(1, bandHeight);
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(sourceCanvas, x, y, width, bandHeight, 0, 0, width, bandHeight);
  return canvas;
}

/**
 * Crop the top title band of a card-guide region.
 * @param {HTMLCanvasElement} sourceCanvas
 * @param {{ x: number, y: number, width: number, height: number }} guide
 */
export function cropTitleBand(sourceCanvas, guide) {
  const bandHeight = Math.max(20, Math.round(guide.height * 0.12));
  const y = Math.max(0, Math.round(guide.y + guide.height * 0.04));
  // Keep left/center of the nameplate; mana cost sits on the far right.
  const x = Math.max(0, Math.round(guide.x + guide.width * 0.08));
  const width = Math.min(sourceCanvas.width - x, Math.round(guide.width * 0.62));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, width);
  canvas.height = Math.max(1, bandHeight);
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(sourceCanvas, x, y, width, bandHeight, 0, 0, width, bandHeight);
  return canvas;
}

let workerPromise = null;
let workerMode = "collector";

async function getOcrWorker() {
  if (!workerPromise) {
    workerPromise = (async () => {
      const { createWorker, PSM } = await import("tesseract.js");
      const worker = await createWorker("eng", 1, {
        logger: () => {},
      });
      await worker.setParameters({
        tessedit_char_whitelist: "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/#.- ",
        preserve_interword_spaces: "1",
        tessedit_pageseg_mode: PSM.SINGLE_LINE,
      });
      workerMode = "collector";
      return worker;
    })();
  }
  return workerPromise;
}

async function configureWorker(mode) {
  const worker = await getOcrWorker();
  if (workerMode === mode) {
    return worker;
  }
  const { PSM } = await import("tesseract.js");
  if (mode === "title") {
    await worker.setParameters({
      tessedit_char_whitelist:
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789' -:,.",
      preserve_interword_spaces: "1",
      tessedit_pageseg_mode: PSM.SINGLE_LINE,
    });
  } else {
    await worker.setParameters({
      tessedit_char_whitelist: "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/#.- ",
      preserve_interword_spaces: "1",
      tessedit_pageseg_mode: PSM.SINGLE_LINE,
    });
  }
  workerMode = mode;
  return worker;
}

function meanConfidence(data) {
  const conf = data?.confidence;
  if (typeof conf === "number" && !Number.isNaN(conf)) {
    return conf;
  }
  const words = data?.words || [];
  if (!words.length) {
    return 0;
  }
  const total = words.reduce((sum, word) => sum + (Number(word.confidence) || 0), 0);
  return total / words.length;
}

/**
 * Run OCR on a collector-band canvas and parse set + number.
 * @param {HTMLCanvasElement} bandCanvas
 */
export async function recognizeCollectorLine(bandCanvas) {
  const worker = await configureWorker("collector");
  const prepared = preprocessCollectorBand(bandCanvas);
  const result = await worker.recognize(prepared);
  const text = result?.data?.text || "";
  const confidence = meanConfidence(result?.data);
  const parsed = parseCollectorAndSet(text);
  return {
    text,
    confidence,
    parsed: acceptOcrParse(parsed, confidence) ? parsed : null,
  };
}

/**
 * OCR the card title from the top of the guide.
 * @param {HTMLCanvasElement} sourceCanvas
 * @param {{ x: number, y: number, width: number, height: number }} guide
 */
export async function recognizeTitleFromGuide(sourceCanvas, guide) {
  const worker = await configureWorker("title");
  const band = cropTitleBand(sourceCanvas, guide);
  const prepared = preprocessCollectorBand(band, 2.2);
  const result = await worker.recognize(prepared);
  const text = stripTrailingManaCost(String(result?.data?.text || "").replace(/\s+/g, " ").trim());
  const confidence = meanConfidence(result?.data);
  return {
    text,
    confidence,
    usable: confidence >= 35 && titleHintIsUsable(text),
  };
}

/**
 * Try primary + alternate collector bands until one parses.
 * @param {HTMLCanvasElement} sourceCanvas
 * @param {{ x: number, y: number, width: number, height: number }} guide
 */
export async function recognizeCollectorFromGuide(sourceCanvas, guide) {
  const attempts = [
    { bandRatio: 0.18, liftRatio: 0.02 },
    { bandRatio: 0.22, liftRatio: 0.06 },
  ];
  let best = { text: "", confidence: 0, parsed: null };
  for (const options of attempts) {
    const band = cropCollectorBand(sourceCanvas, guide, options);
    const result = await recognizeCollectorLine(band);
    if (result.parsed) {
      return result;
    }
    if ((result.confidence || 0) > (best.confidence || 0)) {
      best = result;
    }
  }
  return best;
}

export async function terminateOcrWorker() {
  if (!workerPromise) {
    return;
  }
  try {
    const worker = await workerPromise;
    await worker.terminate();
  } catch {
    // ignore
  }
  workerPromise = null;
  workerMode = "collector";
}
