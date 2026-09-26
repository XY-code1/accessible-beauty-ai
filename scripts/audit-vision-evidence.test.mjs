import { test, expect, afterEach } from "vitest";
import { mkdtemp, mkdir, writeFile, rm, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
const dirs = [];
afterEach(async () => {
  await Promise.all(
    dirs.splice(0).map((dir) => rm(dir, { recursive: true, force: true })),
  );
});
async function audit(change = () => {}, changeFiles = () => {}) {
  const dir = await mkdtemp(path.join(tmpdir(), "vision-audit-test-"));
  dirs.push(dir);
  const bytes = Buffer.from("fixture pixels"),
    sha256 = createHash("sha256").update(bytes).digest("hex");
  const window = {
    indices: [1, 2],
    compatibility: [
      { index: 1, compatible: true },
      { index: 2, compatible: false },
    ],
    sharpest: { index: 2, outcome: { verdict: "unknown" } },
    compatibleSharpest: { index: 1, outcome: { verdict: "unknown" } },
  };
  change(window);
  const files = {
    "visibility-review/private-source-map.json": [
      {
        sourceId: "fixture",
        group: "discovery",
        image: "samples/private/eye.png",
        sha256,
      },
    ],
    "quality-metrics-report.json": {
      rows: [{ sha256, metrics: [{ kind: "identity", scores: { focus: 1 } }] }],
    },
    "quality-validation/metrics-report.json": { rows: [] },
    "user-video-2026-09-25/report.json": {
      result: [
        {
          side: "left",
          baseIndex: 0,
          measurements: [
            { index: 1, timeSeconds: 0.2, status: "usable", sharpness: 30 },
            { index: 2, timeSeconds: 0.4, status: "usable", sharpness: 40 },
          ],
          windows: [window],
        },
      ],
    },
  };
  changeFiles(files);
  for (const [name, data] of Object.entries(files)) {
    await mkdir(path.dirname(path.join(dir, name)), { recursive: true });
    await writeFile(path.join(dir, name), JSON.stringify(data));
  }
  await writeFile(path.join(dir, "eye.png"), bytes);
  const output = path.join(dir, "out.json");
  const run = spawnSync(
    process.execPath,
    ["scripts/audit-vision-evidence.mjs", dir, output],
    { encoding: "utf8" },
  );
  return {
    status: run.status,
    error: run.stderr,
    result: run.status === 0 ? JSON.parse(await readFile(output)) : null,
  };
}
test("keeps both paired selections", async () => {
  const r = await audit();
  expect(r.status).toBe(0);
  expect(r.result.selection.windows[0]).toMatchObject({ a: 2, b: 1 });
});
test.each([null, undefined, { status: "no-eligible-frame" }])(
  "keeps a missing compatible selection as null: %j",
  async (missing) => {
    const r = await audit((w) => {
      w.compatibility.forEach((c) => (c.compatible = false));
      w.compatibleSharpest = missing;
    });
    expect(r.status, r.error).toBe(0);
    expect(r.result.selection.windows[0]).toMatchObject({
      a: 2,
      b: null,
      outcomeB: "not-run",
      durationB: null,
    });
  },
);
test.each(["missing", "duplicate"])(
  "rejects %s compatibility entries",
  async (mode) => {
    const r = await audit((w) => {
      w.compatibility =
        mode === "missing"
          ? [w.compatibility[0]]
          : [w.compatibility[0], w.compatibility[0], w.compatibility[1]];
    });
    expect(r.status).not.toBe(0);
    expect(r.error).toContain("Invalid candidate pool");
  },
);

test("rejects one image aliased under two groups", async () => {
  const r = await audit(undefined, (files) => {
    const map = files["visibility-review/private-source-map.json"];
    map.push({ ...map[0], sourceId: "alias", group: "validation" });
    files["quality-validation/metrics-report.json"] =
      files["quality-metrics-report.json"];
  });
  expect(r.status).not.toBe(0);
  expect(r.error).toContain("Image hash leaks across groups");
});
test.each(["timeSeconds", "sharpness"])(
  "rejects missing %s instead of allowing NaN ordering",
  async (field) => {
    const r = await audit(undefined, (files) => {
      delete files["user-video-2026-09-25/report.json"].result[0]
        .measurements[0][field];
    });
    expect(r.status).not.toBe(0);
    expect(r.error).toContain("Invalid measurement");
  },
);
