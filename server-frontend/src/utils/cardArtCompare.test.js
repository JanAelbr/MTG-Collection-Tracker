import { describe, expect, it } from "vitest";
import {
  compareRgbMaps,
  downsampleArtRgb,
  pickAutoArtMatch,
} from "./cardArtCompare";

function solidImageData(width, height, rgb) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let i = 0; i < data.length; i += 4) {
    data[i] = rgb[0];
    data[i + 1] = rgb[1];
    data[i + 2] = rgb[2];
    data[i + 3] = 255;
  }
  return { data, width, height };
}

describe("cardArtCompare", () => {
  it("scores identical rgb maps as 1", () => {
    const map = new Uint8Array([10, 20, 30, 40, 50, 60]);
    expect(compareRgbMaps(map, map)).toBe(1);
  });

  it("downsamples art and distinguishes different colors", () => {
    const red = downsampleArtRgb(solidImageData(64, 88, [220, 20, 20]));
    const blue = downsampleArtRgb(solidImageData(64, 88, [20, 40, 220]));
    expect(red).toBeTruthy();
    expect(compareRgbMaps(red, red)).toBe(1);
    expect(compareRgbMaps(red, blue)).toBeLessThan(0.5);
  });

  it("auto-picks a clear winner under the print cap", () => {
    const ranked = [
      { setCode: "MH3", artScore: 0.82 },
      { setCode: "M21", artScore: 0.55 },
    ];
    expect(pickAutoArtMatch(ranked)?.setCode).toBe("MH3");
  });

  it("auto-picks a clear hash-distance winner", () => {
    expect(
      pickAutoArtMatch([
        { setCode: "ONE", artDistance: 4 },
        { setCode: "TWO", artDistance: 14 },
      ])?.setCode,
    ).toBe("ONE");
    expect(
      pickAutoArtMatch([
        { setCode: "ONE", artDistance: 4 },
        { setCode: "TWO", artDistance: 5 },
      ]),
    ).toBeNull();
  });
});
