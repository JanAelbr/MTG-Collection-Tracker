/**
 * Fast art-region compare for scan print ranking.
 * Downscales the card art box to a tiny RGB map and scores mean absolute error.
 */

export const ART_COMPARE_SIZE = 12;
export const ART_HASH_SIZE = 8;
export const AUTO_PICK_MIN_SCORE = 0.62;
export const AUTO_PICK_MIN_GAP = 0.1;
export const AUTO_PICK_MAX_PRINTS = 10;
export const AUTO_PICK_MAX_HASH_DISTANCE = 12;
export const AUTO_PICK_MIN_HASH_GAP = 4;

/** Typical modern-frame art box inside a card face. */
export const ART_BOX = {
  x: 0.08,
  y: 0.12,
  width: 0.84,
  height: 0.42,
};

/**
 * @param {ImageData} imageData
 * @param {{ x: number, y: number, width: number, height: number }} [box]
 * @param {number} [size]
 * @returns {Uint8Array | null} packed RGB samples (size*size*3)
 */
export function downsampleArtRgb(imageData, box = ART_BOX, size = ART_COMPARE_SIZE) {
  if (!imageData?.data?.length || !imageData.width || !imageData.height || size < 4) {
    return null;
  }
  const srcX = Math.max(0, Math.floor(imageData.width * box.x));
  const srcY = Math.max(0, Math.floor(imageData.height * box.y));
  const srcW = Math.max(1, Math.floor(imageData.width * box.width));
  const srcH = Math.max(1, Math.floor(imageData.height * box.height));
  const out = new Uint8Array(size * size * 3);
  const data = imageData.data;

  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const px = srcX + Math.min(srcW - 1, Math.floor(((x + 0.5) / size) * srcW));
      const py = srcY + Math.min(srcH - 1, Math.floor(((y + 0.5) / size) * srcH));
      const i = (py * imageData.width + px) * 4;
      const o = (y * size + x) * 3;
      out[o] = data[i];
      out[o + 1] = data[i + 1];
      out[o + 2] = data[i + 2];
    }
  }
  return out;
}

/** @deprecated use downsampleArtRgb */
export function downsampleArtLuma(imageData, box = ART_BOX, size = ART_COMPARE_SIZE) {
  const rgb = downsampleArtRgb(imageData, box, size);
  if (!rgb) {
    return null;
  }
  const out = new Uint8Array(size * size);
  for (let i = 0, p = 0; i < rgb.length; i += 3, p += 1) {
    out[p] = Math.round(rgb[i] * 0.299 + rgb[i + 1] * 0.587 + rgb[i + 2] * 0.114);
  }
  return out;
}

/**
 * @param {Uint8Array | null} left
 * @param {Uint8Array | null} right
 * @returns {number} similarity 0..1
 */
export function compareRgbMaps(left, right) {
  if (!left?.length || !right?.length || left.length !== right.length) {
    return 0;
  }
  let total = 0;
  for (let i = 0; i < left.length; i += 1) {
    total += Math.abs(left[i] - right[i]);
  }
  const mae = total / left.length;
  return Math.max(0, Math.min(1, 1 - mae / 255));
}

/** @deprecated use compareRgbMaps */
export function compareLumaMaps(left, right) {
  return compareRgbMaps(left, right);
}

/**
 * Load a remote card image and downsample its art box.
 * @param {string} url
 * @param {{ size?: number, timeoutMs?: number }} [options]
 * @returns {Promise<Uint8Array | null>}
 */
export function loadArtRgbFromUrl(url, options = {}) {
  const size = options.size ?? ART_COMPARE_SIZE;
  const timeoutMs = options.timeoutMs ?? 4500;
  if (!url) {
    return Promise.resolve(null);
  }
  return new Promise((resolve) => {
    const image = new Image();
    let settled = false;
    const finish = (value) => {
      if (settled) {
        return;
      }
      settled = true;
      resolve(value);
    };
    const timer = window.setTimeout(() => finish(null), timeoutMs);
    image.crossOrigin = "anonymous";
    image.onload = () => {
      window.clearTimeout(timer);
      try {
        const canvas = document.createElement("canvas");
        canvas.width = image.naturalWidth || image.width;
        canvas.height = image.naturalHeight || image.height;
        if (!canvas.width || !canvas.height) {
          finish(null);
          return;
        }
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        ctx.drawImage(image, 0, 0);
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        finish(downsampleArtRgb(imageData, ART_BOX, size));
      } catch {
        finish(null);
      }
    };
    image.onerror = () => {
      window.clearTimeout(timer);
      finish(null);
    };
    image.src = url;
  });
}

/**
 * @template T
 * @param {T[]} items
 * @param {number} limit
 * @param {(item: T, index: number) => Promise<unknown>} worker
 */
async function mapPool(items, limit, worker) {
  const results = new Array(items.length);
  let next = 0;
  async function run() {
    while (next < items.length) {
      const index = next;
      next += 1;
      results[index] = await worker(items[index], index);
    }
  }
  const workers = Array.from({ length: Math.min(limit, items.length) }, () => run());
  await Promise.all(workers);
  return results;
}

/**
 * Rank prints by art similarity to a probe card crop.
 * @param {ImageData | null} probeImageData full card-face crop from the camera guide
 * @param {Array<{ imageUri?: string }>} prints
 * @param {{ concurrency?: number, size?: number }} [options]
 */
export async function rankPrintsByArt(probeImageData, prints, options = {}) {
  const list = Array.isArray(prints) ? prints : [];
  const probe = downsampleArtRgb(probeImageData, ART_BOX, options.size ?? ART_COMPARE_SIZE);
  if (!probe || !list.length) {
    return list.map((print) => ({ ...print, artScore: 0 }));
  }

  const scores = await mapPool(list, options.concurrency ?? 6, async (print) => {
    const rgb = await loadArtRgbFromUrl(print.imageUri || "", {
      size: options.size ?? ART_COMPARE_SIZE,
    });
    return compareRgbMaps(probe, rgb);
  });

  return list
    .map((print, index) => ({
      ...print,
      artScore: Number((scores[index] || 0).toFixed(4)),
    }))
    .sort((a, b) => b.artScore - a.artScore || String(a.setCode).localeCompare(String(b.setCode)));
}

/**
 * Average-hash of the art box (64-bit hex). Matches server util.art_hash.
 * @param {ImageData} imageData
 * @param {number} [size]
 */
export function computeArtAHash(imageData, size = ART_HASH_SIZE) {
  const rgb = downsampleArtRgb(imageData, ART_BOX, size);
  if (!rgb) {
    return "";
  }
  const lumas = [];
  for (let i = 0; i < rgb.length; i += 3) {
    lumas.push(Math.round(rgb[i] * 0.299 + rgb[i + 1] * 0.587 + rgb[i + 2] * 0.114));
  }
  const mean = lumas.reduce((sum, value) => sum + value, 0) / lumas.length;
  let bits = 0n;
  for (let i = 0; i < lumas.length; i += 1) {
    if (lumas[i] >= mean) {
      bits |= 1n << BigInt(lumas.length - 1 - i);
    }
  }
  return bits.toString(16).padStart(Math.max(16, Math.ceil(lumas.length / 4)), "0");
}

/**
 * Decide whether the top-ranked print is a clear auto-pick.
 * Supports RGB artScore ranking and hash artDistance ranking.
 */
export function pickAutoArtMatch(ranked, options = {}) {
  const list = Array.isArray(ranked) ? ranked : [];
  const maxPrints = options.maxPrints ?? AUTO_PICK_MAX_PRINTS;
  const minScore = options.minScore ?? AUTO_PICK_MIN_SCORE;
  const minGap = options.minGap ?? AUTO_PICK_MIN_GAP;
  const maxDistance = options.maxDistance ?? AUTO_PICK_MAX_HASH_DISTANCE;
  const minHashGap = options.minHashGap ?? AUTO_PICK_MIN_HASH_GAP;
  if (!list.length || list.length > maxPrints) {
    return null;
  }
  const best = list[0];
  if (best.artDistance != null) {
    const bestDist = Number(best.artDistance);
    if (list.length === 1) {
      return bestDist <= maxDistance ? best : null;
    }
    const secondDist = Number(list[1].artDistance);
    if (bestDist <= maxDistance && secondDist - bestDist >= minHashGap) {
      return best;
    }
    return null;
  }
  const bestScore = Number(best.artScore) || 0;
  if (list.length === 1) {
    return bestScore >= Math.min(minScore, 0.52) ? best : null;
  }
  const secondScore = Number(list[1].artScore) || 0;
  const gap = bestScore - secondScore;
  if (bestScore >= minScore && gap >= minGap) {
    return best;
  }
  return null;
}
