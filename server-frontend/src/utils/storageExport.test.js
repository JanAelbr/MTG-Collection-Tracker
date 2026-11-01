import { describe, expect, it } from "vitest";

import {
  aggregateExportLines,
  buildCardmarketBulkCsv,
  buildCardmarketBulkZipFiles,
  buildTcgPowerToolsCsv,
  cardmarketBulkName,
  chunkExportLines,
  powerToolsCollectorNumber,
  chunkFileLabel,
  collectLeafExportGroups,
  parseIdProduct,
} from "./storageExport";

describe("storageExport", () => {
  it("parses Cardmarket product ids from urls", () => {
    expect(parseIdProduct("https://www.cardmarket.com/en/Magic/Products?idProduct=716201")).toBe("716201");
    expect(parseIdProduct("")).toBeNull();
  });

  it("aggregates copy counts per print", () => {
    const lines = aggregateExportLines([
      { setCode: "AFR", collectorNumber: "1", finish: 0, copyCount: 2, name: "A" },
      { setCode: "AFR", collectorNumber: "1", finish: 0, copyCount: 1, name: "A" },
      { setCode: "AFR", collectorNumber: "2", finish: 1, copyCount: 1, name: "B" },
    ]);
    expect(lines).toHaveLength(2);
    expect(lines[0].qty).toBe(3);
    expect(lines[1].qty).toBe(1);
  });

  it("chunks export lines at 100 rows", () => {
    const lines = Array.from({ length: 212 }, (_, index) => ({ card: { name: `C${index}` }, qty: 1 }));
    const chunks = chunkExportLines(lines, 100);
    expect(chunks).toHaveLength(3);
    expect(chunks[0]).toHaveLength(100);
    expect(chunks[1]).toHaveLength(100);
    expect(chunks[2]).toHaveLength(12);
  });

  it("names chunk files with segment label and row range", () => {
    expect(chunkFileLabel("Adventures in the Forgotten Realms", 1, 100)).toBe(
      "Adventures in the Forgotten Realms 1-100",
    );
    expect(chunkFileLabel("", 201, 212)).toBe("201-212");
  });

  it("builds Cardmarket bulk csv with foil and quantity columns", () => {
    const csv = buildCardmarketBulkCsv([
      {
        card: {
          name: "Dragon (Foil)",
          setCode: "AFR",
          collectorNumber: "1",
          finish: 1,
          rarity: "rare",
        },
        qty: 2,
      },
    ]);
    expect(csv.split("\n")[0]).toContain("Name");
    expect(csv).toContain("Dragon");
    expect(csv).not.toContain("(Foil)");
    expect(csv).toContain("foil");
    expect(csv).toContain(",2,");
    expect(csv).toContain(",NM,");
  });

  it("normalizes numeric collector numbers for PowerTools", () => {
    expect(powerToolsCollectorNumber("039")).toBe("39");
    expect(powerToolsCollectorNumber("123a")).toBe("123a");
  });

  it("builds TCG PowerTools csv with cardmarket id and foil flags", () => {
    const csv = buildTcgPowerToolsCsv([
      {
        card: {
          name: "Lightning Bolt (Foil)",
          setCode: "mh2",
          collectorNumber: "042",
          finish: 1,
          cardmarketUrlFoil: "https://www.cardmarket.com/en/Magic/Products?idProduct=12345",
        },
        qty: 3,
      },
    ]);
    expect(csv.split("\n")[0]).toContain("cardmarketId");
    expect(csv).toContain("12345");
    expect(csv).toContain("Lightning Bolt");
    expect(csv).not.toContain("(Foil)");
    expect(csv).toContain(",MH2,42,");
    expect(csv).toContain(",true,");
  });

  it("uses front face name for double-faced cards", () => {
    expect(cardmarketBulkName({ name: "Virtue of Loyalty // Ardenvale Fealty" })).toBe(
      "Virtue of Loyalty",
    );
  });

  it("splits mixed sets into separate csv files in the zip", () => {
    const files = buildCardmarketBulkZipFiles([{
      label: "Mixed",
      cards: [
        { setCode: "MH2", collectorNumber: "1", finish: 0, copyCount: 1, name: "A" },
        { setCode: "ELD", collectorNumber: "2", finish: 0, copyCount: 1, name: "B" },
      ],
    }]);
    expect(files["README.txt"]).toContain("ONE set");
    expect(Object.keys(files).filter((name) => name.endsWith(".csv")).sort()).toEqual([
      "ELD 1-1.csv",
      "MH2 1-1.csv",
    ]);
  });

  it("creates one csv per chunk per leaf group", () => {
    const groups = [
      {
        label: "AFR",
        cards: Array.from({ length: 212 }, (_, index) => ({
          setCode: "AFR",
          collectorNumber: String(index + 1),
          finish: 0,
          copyCount: 1,
          name: `Card ${index + 1}`,
        })),
        groups: [],
      },
    ];
    const segments = collectLeafExportGroups(groups).map((group) => ({
      label: group.label,
      cards: group.cards,
    }));
    const files = buildCardmarketBulkZipFiles(segments);
    expect(Object.keys(files).sort()).toEqual([
      "AFR 1-100.csv",
      "AFR 101-200.csv",
      "AFR 201-212.csv",
      "README.txt",
    ]);
  });
});
