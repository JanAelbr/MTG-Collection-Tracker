/**
 * Heuristic: does the guide region look like a printed MTG card vs empty surface?
 */

export const CARD_PRESENCE_THRESHOLD = 0.22;

function luminance(r, g, b) {
  return r * 0.299 + g * 0.587 + b * 0.114;
}

/**
 * @param {ImageData} imageData
 * @returns {{ looksLikeCard: boolean, score: number, edgeRatio: number, contrast: number }}
 */
export function scoreCardPresence(imageData) {
  if (!imageData?.data?.length || !imageData.width || !imageData.height) {
    return { looksLikeCard: false, score: 0, edgeRatio: 0, contrast: 0 };
  }

  const { data, width, height } = imageData;
  const step = Math.max(1, Math.floor(Math.sqrt((width * height) / 8000)));
  let samples = 0;
  let edges = 0;
  let sum = 0;
  let sumSq = 0;
  let min = 255;
  let max = 0;

  for (let y = step; y < height - step; y += step) {
    for (let x = step; x < width - step; x += step) {
      const i = (y * width + x) * 4;
      const lum = luminance(data[i], data[i + 1], data[i + 2]);
      const left = luminance(
        data[i - step * 4],
        data[i - step * 4 + 1],
        data[i - step * 4 + 2],
      );
      const up = luminance(
        data[((y - step) * width + x) * 4],
        data[((y - step) * width + x) * 4 + 1],
        data[((y - step) * width + x) * 4 + 2],
      );
      const grad = Math.abs(lum - left) + Math.abs(lum - up);
      samples += 1;
      sum += lum;
      sumSq += lum * lum;
      if (lum < min) min = lum;
      if (lum > max) max = lum;
      if (grad > 28) {
        edges += 1;
      }
    }
  }

  if (samples === 0) {
    return { looksLikeCard: false, score: 0, edgeRatio: 0, contrast: 0 };
  }

  const edgeRatio = edges / samples;
  const mean = sum / samples;
  const variance = Math.max(0, sumSq / samples - mean * mean);
  const contrast = (max - min) / 255;
  const score = Math.min(1, edgeRatio * 2.4 + Math.sqrt(variance) / 120 + contrast * 0.35);

  return {
    looksLikeCard: score >= CARD_PRESENCE_THRESHOLD,
    score,
    edgeRatio,
    contrast,
  };
}

/**
 * @param {HTMLCanvasElement} sourceCanvas
 * @param {{ x: number, y: number, width: number, height: number }} guide
 */
export function scoreCardPresenceInGuide(sourceCanvas, guide) {
  const x = Math.max(0, Math.round(guide.x));
  const y = Math.max(0, Math.round(guide.y));
  const width = Math.min(sourceCanvas.width - x, Math.round(guide.width));
  const height = Math.min(sourceCanvas.height - y, Math.round(guide.height));
  if (width <= 4 || height <= 4) {
    return { looksLikeCard: false, score: 0, edgeRatio: 0, contrast: 0 };
  }
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(sourceCanvas, x, y, width, height, 0, 0, width, height);
  return scoreCardPresence(ctx.getImageData(0, 0, width, height));
}
