// Local-only diagnostic. No image is uploaded; generated photos must stay private.
import { createServer, transformWithOxc } from "vite";
import { imageDataUrl } from "./image-data-url.mjs";
import { chromium } from "@playwright/test";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import path from "node:path";
const [input, output, baseline = "eb426e0"] = process.argv.slice(2);
if (!input || !output)
  throw new Error(
    "Usage: node scripts/diagnose-guidance.mjs image output-directory [baseline-ref]",
  );
const bytes = await readFile(input);
const old = execFileSync(
  "git",
  ["show", `${baseline}:src/guidance/render.ts`],
  { encoding: "utf8" },
);
const { code: previous } = await transformWithOxc(old, "baseline-render.ts");
const server = await createServer({
  server: { host: "127.0.0.1", port: 0 },
  logLevel: "error",
});
let browser;
try {
  await server.listen();
  browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  await page.route("**/__previous-render.js", (r) =>
    r.fulfill({ contentType: "text/javascript", body: previous }),
  );
  await page.goto(server.resolvedUrls.local[0]);
  const result = await page.evaluate(
    async ({ image }) => {
      const { createDetector } = await import("/src/vision/detector.ts");
      const { eyeFromLandmarks, eyeCrop, referencePath, projectToDisplay } =
        await import("/src/guidance/geometry.ts");
      const { drawGuide } = await import("/src/guidance/render.ts");
      const { drawGuide: previous } = await import("/__previous-render.js");
      const img = new Image();
      img.src = image;
      await img.decode();
      const detector = await createDetector();
      let points;
      try {
        points = detector.detectForVideo(img, performance.now())
          .faceLandmarks[0];
      } finally {
        detector.close();
      }
      if (!points)
        throw new Error("No face found; no illustrative substitute produced.");
      const panels = [];
      const eyes = {};
      for (const side of ["left", "right"]) {
        const eye = eyeFromLandmarks(points, side, img.width, img.height);
        if (!eye) continue;
        eyes[side] = eye;
        const crop = eyeCrop(eye, { x: img.width, y: img.height });
        for (const layer of ["raw", "landmarks", "curve", "before", "after"]) {
          const c = document.createElement("canvas");
          c.width = 480;
          c.height = 320;
          const ctx = c.getContext("2d");
          const scale = Math.min(c.width / crop.width, c.height / crop.height);
          ctx.drawImage(
            img,
            crop.x,
            crop.y,
            crop.width,
            crop.height,
            (c.width - crop.width * scale) / 2,
            (c.height - crop.height * scale) / 2,
            crop.width * scale,
            crop.height * scale,
          );
          const project = (p) =>
            projectToDisplay(
              { x: p.x - crop.x, y: p.y - crop.y },
              { x: crop.width, y: crop.height },
              { x: c.width, y: c.height },
              false,
            );
          const ref = referencePath(eye, { side, length: 0.3, angle: 20 });
          if (layer === "landmarks")
            for (const p of eye.upper) {
              const q = project(p);
              ctx.beginPath();
              ctx.arc(q.x, q.y, 3, 0, Math.PI * 2);
              ctx.fillStyle = "#ff4488";
              ctx.fill();
            }
          if (layer === "curve") {
            ctx.beginPath();
            ref.lid.forEach((p, i) => {
              const q = project(p);
              if (!i) ctx.moveTo(q.x, q.y);
              else ctx.lineTo(q.x, q.y);
            });
            ctx.strokeStyle = "#ff4488";
            ctx.lineWidth = 2;
            ctx.stroke();
          }
          if (layer === "before" || layer === "after")
            (layer === "before" ? previous : drawGuide)(
              ctx,
              ref,
              project,
              "setup",
              "guide",
              true,
            );
          panels.push({ name: `${side}-${layer}`, url: c.toDataURL() });
        }
      }
      return { eyes, panels };
    },
    {
      image: imageDataUrl(bytes),
    },
  );
  await mkdir(output, { recursive: true });
  for (const p of result.panels)
    await writeFile(
      path.join(output, p.name + ".png"),
      Buffer.from(p.url.split(",")[1], "base64"),
    );
  const { panels, ...metadata } = result;
  await writeFile(
    path.join(output, "metadata.json"),
    JSON.stringify(
      {
        ...metadata,
        codeHashes: Object.fromEntries(
          await Promise.all(
            ["src/guidance/render.ts", "src/guidance/geometry.ts"].map(
              async (file) => [
                file,
                createHash("sha256")
                  .update(await readFile(file))
                  .digest("hex"),
              ],
            ),
          ),
        ),
        inputHash: createHash("sha256").update(bytes).digest("hex"),
        baseline,
        head: execFileSync("git", ["rev-parse", "HEAD"], {
          encoding: "utf8",
        }).trim(),
        note: "Working-tree renderer, fixed photograph; not a makeup accuracy label.",
      },
      null,
      2,
    ),
  );
  await writeFile(
    path.join(output, "index.html"),
    `<!doctype html><meta charset="utf-8"><title>参考路径分层对照</title><style>body{font-family:system-ui}main{display:flex;flex-wrap:wrap}figure{margin:8px}img{width:360px}</style><h1>原图 → 关键点 → 曲线 → 旧显示 → 新显示</h1><p>同图同关键点；未修改路径几何；不代表美妆适配已验收。</p><main>${panels.map((p) => `<figure><figcaption>${p.name}</figcaption><img src="${p.name}.png"></figure>`).join("")}</main>`,
  );
  console.log(`Saved ${panels.length} panels to ${output}`);
} finally {
  await browser?.close();
  await server.close();
}
