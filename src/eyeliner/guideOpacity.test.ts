import { describe, expect, it } from "vitest";
import { DEFAULT_GUIDE_OPACITY, parseGuideOpacity } from "./guideOpacity";

describe("guide opacity storage", () => {
  it("defaults to 65% when no saved value exists", () => {
    expect(parseGuideOpacity(null)).toBe(DEFAULT_GUIDE_OPACITY);
  });

  it("accepts both range boundaries", () => {
    expect(parseGuideOpacity("0.2")).toBe(0.2);
    expect(parseGuideOpacity("1")).toBe(1);
  });

  it.each(["", "invalid", "0.19", "1.01", "Infinity"])(
    "falls back for an invalid saved value: %s",
    (value) => expect(parseGuideOpacity(value)).toBe(DEFAULT_GUIDE_OPACITY),
  );
});
