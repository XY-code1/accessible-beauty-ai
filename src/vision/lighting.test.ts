import { describe, expect, it } from "vitest";
import { lightingMessage } from "./lighting";
import {
  LIGHTING_CLEAR_SAMPLES,
  LIGHTING_SAMPLE_MS,
  LIGHTING_SHOW_SAMPLES,
} from "../eyeliner/useLightingHint";

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

  it("requires two seconds to show and one-and-a-half seconds to clear", () => {
    expect(LIGHTING_SAMPLE_MS * LIGHTING_SHOW_SAMPLES).toBe(2_000);
    expect(LIGHTING_SAMPLE_MS * LIGHTING_CLEAR_SAMPLES).toBe(1_500);
  });
});
