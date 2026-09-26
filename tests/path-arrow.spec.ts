import { test, expect } from "@playwright/test";

for (const eyeY of [180, 220]) {
  test(`direction arrow follows the active stroke at eye height ${eyeY}`, async ({
    page,
  }) => {
    await page.goto("/#/eyeliner");
    const counts = await page.evaluate(async (eyeY) => {
      // Exercise the existing canvas renderer with known eye coordinates.
      const { drawGuide } = await import(
        /* @vite-ignore */ "/src/guidance/" + "render.ts"
      );
      const { referencePath } = await import(
        /* @vite-ignore */ "/src/guidance/" + "geometry.ts"
      );
      const canvas = document.createElement("canvas");
      canvas.width = 400;
      canvas.height = 300;
      const ctx = canvas.getContext("2d")!;
      const eye = {
        inner: { x: 80, y: eyeY },
        outer: { x: 200, y: eyeY },
        width: 120,
        outward: { x: 1, y: 0 },
        up: { x: 0, y: -1 },
        upper: [
          { x: 80, y: eyeY },
          { x: 140, y: eyeY - 15 },
          { x: 200, y: eyeY },
        ],
        openness: 0.25,
        poseRatio: 1,
      };
      // Physical backing size must match CSS pixels for this deterministic image.
      Object.defineProperty(window, "devicePixelRatio", {
        value: 1,
        configurable: true,
      });
      drawGuide(
        ctx,
        referencePath(eye, { side: "left", length: 0.3, angle: 20 }),
        (p: { x: number; y: number }) => p,
        "wing",
        "guide",
        true,
      );
      const count = (top: number, bottom: number) => {
        const pixels = ctx.getImageData(205, top, 30, bottom - top).data;
        let n = 0;
        for (let i = 0; i < pixels.length; i += 4)
          if (
            pixels[i] > 220 &&
            pixels[i + 1] > 235 &&
            pixels[i + 2] > 190 &&
            pixels[i + 3] > 80
          )
            n++;
        return n;
      };
      return { near: count(eyeY - 40, eyeY - 14), detached: count(15, 50) };
    }, eyeY);
    expect(counts.near).toBeGreaterThan(5);
    expect(counts.detached).toBe(0);
  });
}
