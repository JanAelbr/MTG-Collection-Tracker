import { describe, expect, it } from "vitest";
import { displayCardmarketUrl } from "./cardmarketUrl";

describe("displayCardmarketUrl", () => {
  it("removes utm_source=scryfall and keeps the product link", () => {
    const url = displayCardmarketUrl(
      "https://www.cardmarket.com/en/Magic/Products?idProduct=716201&referrer=scryfall&utm_campaign=card_prices&utm_medium=text&utm_source=scryfall",
    );
    const parsed = new URL(url);
    expect(parsed.searchParams.get("idProduct")).toBe("716201");
    expect(parsed.searchParams.get("utm_source")).toBeNull();
    expect(parsed.searchParams.get("referrer")).toBe("scryfall");
    expect(parsed.searchParams.get("utm_campaign")).toBe("card_prices");
  });

  it("leaves other utm sources unchanged", () => {
    const url = "https://www.cardmarket.com/en/Magic/Products?idProduct=1&utm_source=shop";
    expect(displayCardmarketUrl(url)).toBe(url);
  });

  it("returns an empty string for a missing url", () => {
    expect(displayCardmarketUrl("")).toBe("");
    expect(displayCardmarketUrl(null)).toBe("");
  });
});
