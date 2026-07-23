import { describe, expect, it } from "vitest";
import { CARD_PRESENCE_THRESHOLD, scoreCardPresence } from "./cardPresence";

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

describe("cardPresence scoreCardPresence", () => {
  it("scores a flat surface as not a card", () => {
    const image = makeImageData(80, 120, () => [180, 180, 175]);
    const result = scoreCardPresence(image);
    expect(result.looksLikeCard).toBe(false);
    expect(result.score).toBeLessThan(CARD_PRESENCE_THRESHOLD);
  });

  it("scores a high-edge structured image as card-like", () => {
    const image = makeImageData(80, 120, (i, width) => {
      const x = i % width;
      const y = Math.floor(i / width);
      if (x < 4 || x > width - 5 || y < 4 || y > 115) {
        return [20, 20, 20];
      }
      if ((x + y) % 7 === 0) {
        return [240, 240, 240];
      }
      if (y > 90 && x < 40) {
        return [30, 30, 30];
      }
      return [90, 120, 70];
    });
    const result = scoreCardPresence(image);
    expect(result.score).toBeGreaterThanOrEqual(CARD_PRESENCE_THRESHOLD);
    expect(result.looksLikeCard).toBe(true);
  });
});
