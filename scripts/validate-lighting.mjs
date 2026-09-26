// Proxy diagnostics on existing private eye crops, not an exposure-labelled benchmark.
import { createServer } from "vite";
import { imageDataUrl } from "./image-data-url.mjs";
import { chromium } from "@playwright/test";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
const [existingRoot, output] = process.argv.slice(2);
if (!existingRoot || !output)
  throw new Error(
    "Usage: node scripts/validate-lighting.mjs original-project-root output.json",
  );
const mapping = JSON.parse(
  await readFile(
    path.join(
      existingRoot,
      "samples/private/visibility-review/private-source-map.json",
    ),
    "utf8",
  ),
);
const server = await createServer({
  server: { host: "127.0.0.1", port: 0 },
  logLevel: "error",
});
let browser;
try {
  await server.listen();
  browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto(server.resolvedUrls.local[0]);
  const rows = [];
  for (const item of mapping) {
    const bytes = await readFile(path.join(existingRoot, item.image));
    if (createHash("sha256").update(bytes).digest("hex") !== item.sha256)
      throw new Error("Input hash mismatch");
    const metrics = await page.evaluate(async (image) => {
      const { lightingMessage } = await import("/src/vision/lighting.ts");
      const img = new Image();
      img.src = image;
      await img.decode();
      const canvas = document.createElement("canvas");
      canvas.width = 32;
      canvas.height = 24;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0, 32, 24);
      const raw = ctx.getImageData(0, 0, 32, 24);
      const result = [];
      for (const condition of [
        "identity",
        "dim85",
        "dim20",
        "clipped",
        "half-shadow",
      ]) {
        const data = new Uint8ClampedArray(raw.data);
        for (let i = 0; i < data.length; i += 4)
          for (let c = 0; c < 3; c++) {
            if (condition === "dim85") data[i + c] *= 0.85;
            if (condition === "dim20") data[i + c] *= 0.2;
            if (condition === "clipped") data[i + c] = 252;
            if (condition === "half-shadow" && (i / 4) % 32 < 16)
              data[i + c] *= 0.3;
          }
        const started = performance.now();
        const message = lightingMessage(data);
        result.push({
          condition,
          message,
          durationMs: performance.now() - started,
        });
      }
      return result;
    }, imageDataUrl(bytes));
    rows.push({
      reviewId: item.reviewId,
      sourceId: item.sourceId,
      group: item.group,
      sha256: item.sha256,
      metrics,
    });
  }
  const counts = {};
  for (const row of rows)
    for (const m of row.metrics) {
      const key = row.group + "/" + m.condition;
      const c = (counts[key] ??= {
        samples: 0,
        dark: 0,
        highlights: 0,
        none: 0,
      });
      c.samples++;
      c[
        m.message.includes("偏暗") ? "dark" : m.message ? "highlights" : "none"
      ]++;
    }
  await mkdir(path.dirname(output), { recursive: true });
  await writeFile(
    output,
    JSON.stringify(
      {
        protocol:
          "Fixed mean<35 / luminance>=245 fraction>0.3; 32x24; existing canonical crops as proxy, not identical to live axis-aligned crops. No independent exposure truth. Five correlated variants per original. Parameters frozen before this run; no tuning on validation.",
        classifierHash: createHash("sha256")
          .update(await readFile("src/vision/lighting.ts"))
          .digest("hex"),
        rows,
        counts,
      },
      null,
      2,
    ),
  );
  console.log(JSON.stringify(counts));
} finally {
  await browser?.close();
  await server.close();
}
