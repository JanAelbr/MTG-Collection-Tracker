import { describe, expect, it } from "vitest";
import { FOIL_SCORE_THRESHOLD, scoreFoilFromImageData } from "./foilDetect";

function makeImageData(width, height, fill) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let i = 0; i < width * height; i += 1) {
    const pixel = fill(i, width, height);
    const offset = i * 4;
    data[offset] = pixel[0];
    data[offset + 1] = pixel[1];
    data[offset + 2] = pixel[2];
    data[offset + 3] = 255;
  }
  return { data, width, height };
}

describe("foilDetect scoreFoilFromImageData", () => {
  it("scores matte flat colors as non-foil", () => {
    const image = makeImageData(80, 120, () => [40, 70, 50]);
    const result = scoreFoilFromImageData(image);
    expect(result.isFoil).toBe(false);
    expect(result.score).toBeLessThan(FOIL_SCORE_THRESHOLD);
  });

  it("scores bright specular + colorful variance as foil", () => {
    const image = makeImageData(80, 120, (i) => {
      const n = i % 7;
      if (n === 0) return [255, 255, 255];
      if (n === 1) return [255, 40, 180];
      if (n === 2) return [40, 220, 255];
      if (n === 3) return [255, 220, 40];
      if (n === 4) return [120, 40, 255];
      return [30, 30, 30];
    });
    const result = scoreFoilFromImageData(image);
    expect(result.score).toBeGreaterThanOrEqual(FOIL_SCORE_THRESHOLD);
    expect(result.isFoil).toBe(true);
  });
});
