import { describe, expect, test } from "vitest";
import { publicFeedbackUrl } from "./feedback";

describe("publicFeedbackUrl", () => {
  test("accepts only public HTTPS links", () => {
    expect(publicFeedbackUrl("https://example.com/form?id=1")).toBe(
      "https://example.com/form?id=1",
    );
    expect(publicFeedbackUrl("javascript:alert(1)")).toBeNull();
    expect(publicFeedbackUrl("http://example.com/form")).toBeNull();
    expect(publicFeedbackUrl(undefined)).toBeNull();
  });
});
