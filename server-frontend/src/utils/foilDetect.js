/**
 * Heuristic foil detection from card ImageData.
 * Foil cards tend to show bright specular peaks and higher saturation variance.
 */

export const FOIL_SCORE_THRESHOLD = 0.42;

function rgbToHsl(r, g, b) {
  const rn = r / 255;
  const gn = g / 255;
  const bn = b / 255;
  const max = Math.max(rn, gn, bn);
  const min = Math.min(rn, gn, bn);
  const l = (max + min) / 2;
  if (max === min) {
    return { h: 0, s: 0, l };
  }
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let h = 0;
  if (max === rn) {
    h = ((gn - bn) / d + (gn < bn ? 6 : 0)) / 6;
  } else if (max === gn) {
    h = ((bn - rn) / d + 2) / 6;
  } else {
    h = ((rn - gn) / d + 4) / 6;
  }
  return { h, s, l };
}

/**
 * @param {ImageData} imageData
 * @returns {{ isFoil: boolean, score: number, specularRatio: number, satVariance: number }}
 */
export function scoreFoilFromImageData(imageData) {
  if (!imageData?.data?.length || !imageData.width || !imageData.height) {
    return { isFoil: false, score: 0, specularRatio: 0, satVariance: 0 };
  }

  const { data, width, height } = imageData;
  const sampleStep = Math.max(1, Math.floor(Math.sqrt((width * height) / 12000)));
  let samples = 0;
  let specular = 0;
  let satSum = 0;
  let satSq = 0;
  let hueBuckets = new Array(12).fill(0);

  for (let y = 0; y < height; y += sampleStep) {
    for (let x = 0; x < width; x += sampleStep) {
      const i = (y * width + x) * 4;
      const r = data[i];
      const g = data[i + 1];
      const b = data[i + 2];
      const lum = r * 0.299 + g * 0.587 + b * 0.114;
      const { h, s, l } = rgbToHsl(r, g, b);
      samples += 1;
      if (lum > 220 || (l > 0.78 && s > 0.15)) {
        specular += 1;
      }
      satSum += s;
      satSq += s * s;
      if (s > 0.25 && l > 0.2 && l < 0.9) {
        hueBuckets[Math.min(11, Math.floor(h * 12))] += 1;
      }
    }
  }

  if (samples === 0) {
    return { isFoil: false, score: 0, specularRatio: 0, satVariance: 0 };
  }

  const specularRatio = specular / samples;
  const satMean = satSum / samples;
  const satVariance = Math.max(0, satSq / samples - satMean * satMean);
  const colorful = hueBuckets.filter((count) => count > samples * 0.02).length;
  const hueSpread = colorful / 12;

  // Weighted blend tuned for phone captures under mixed lighting
  const score = Math.min(
    1,
    specularRatio * 2.2 + satVariance * 3.5 + hueSpread * 0.55,
  );

  return {
    isFoil: score >= FOIL_SCORE_THRESHOLD,
    score,
    specularRatio,
    satVariance,
  };
}

/**
 * Crop guide region from a canvas for foil scoring.
 */
export function cropGuideImageData(sourceCanvas, guide) {
  const x = Math.max(0, Math.round(guide.x));
  const y = Math.max(0, Math.round(guide.y));
  const width = Math.min(sourceCanvas.width - x, Math.round(guide.width));
  const height = Math.min(sourceCanvas.height - y, Math.round(guide.height));
  if (width <= 0 || height <= 0) {
    return null;
  }
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(sourceCanvas, x, y, width, height, 0, 0, width, height);
  return ctx.getImageData(0, 0, width, height);
}
