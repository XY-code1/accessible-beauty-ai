import { describe, expect, it } from "vitest";
import { lightingMessage } from "./lighting";

const pixels = (...values: number[]) =>
  new Uint8ClampedArray(values.flatMap((value) => [value, value, value, 255]));

describe("lightingMessage", () => {
  it("uses strict dark and highlight boundaries", () => {
    expect(lightingMessage(pixels(54))).toContain("偏暗");
    expect(lightingMessage(pixels(55))).toBe("");
    expect(lightingMessage(pixels(235, 100, 100, 100, 100))).toBe("");
    expect(lightingMessage(pixels(235, 235, 100, 100, 100))).toContain(
      "高亮",
    );
  });

  it("keeps ordinary indoor luminance quiet", () => {
    expect(lightingMessage(pixels(90, 120, 150, 180, 220))).toBe("");
  });
});
