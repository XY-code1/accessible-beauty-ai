import { expect, test } from "vitest";
import { imageDataUrl } from "./image-data-url.mjs";
test.each([
  [[137, 80, 78, 71, 13, 10, 26, 10], "image/png"],
  [[255, 216, 255, 224], "image/jpeg"],
])("uses the encoded image signature: %j", (signature, mime) => {
  const bytes = Buffer.from(signature);
  expect(imageDataUrl(bytes)).toBe(
    `data:${mime};base64,${bytes.toString("base64")}`,
  );
});
test.each([[[]], [[137, 80]], [[0, 0, 0]]])(
  "rejects unsupported or truncated signatures: %j",
  (bytes) => {
    expect(() => imageDataUrl(Buffer.from(bytes))).toThrow(
      "Unsupported image encoding",
    );
  },
);
