// Recheck existing local experiments. Does not run or modify production vision.
import { readFile, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
const [privateRoot, output] = process.argv.slice(2);
if (!privateRoot || !output)
  throw new Error(
    "Usage: node scripts/audit-vision-evidence.mjs existing-private-directory output.json",
  );
const hashes = {};
async function load(file) {
  const data = await readFile(path.join(privateRoot, file));
  hashes[file] = createHash("sha256").update(data).digest("hex");
  return JSON.parse(data);
}
const mapping = await load("visibility-review/private-source-map.json");
const discovery = await load("quality-metrics-report.json");
const validation = await load("quality-validation/metrics-report.json");
const video = await load("user-video-2026-09-25/report.json");
const groups = new Map();
for (const row of mapping) {
  if (groups.has(row.sourceId) && groups.get(row.sourceId) !== row.group)
    throw new Error("Source leaks across groups");
  groups.set(row.sourceId, row.group);
}
const ratios = (report) => {
  const summary = {};
  for (const row of report.rows) {
    const identity = row.metrics.find((m) => m.kind === "identity");
    if (!identity) throw new Error("Missing original metrics");
    for (const m of row.metrics)
      for (const [metric, score] of Object.entries(m.scores)) {
        if (
          !Number.isFinite(score) ||
          !Number.isFinite(identity.scores[metric])
        )
          throw new Error("Invalid metric");
        const key = metric + "/" + m.kind;
        const bucket = (summary[key] ??= { total: 0, atLeastOriginal: 0 });
        bucket.total++;
        bucket.atLeastOriginal += Number(score >= identity.scores[metric]);
      }
  }
  return summary;
};
const windows = [];
for (const side of video.result) {
  if (!side.windows)
    throw new Error("Missing windows; cannot silently drop a side");
  for (const w of side.windows) {
    if (
      !w.indices.length ||
      new Set(w.indices).size !== w.indices.length ||
      w.compatibility.some((c) => !w.indices.includes(c.index)) ||
      w.indices.includes(side.baseIndex) ||
      w.indices.length > 5
    )
      throw new Error("Invalid candidate pool");
    const measurements = w.indices.map((i) =>
      side.measurements.find((m) => m.index === i),
    );
    if (measurements.some((m) => !m)) throw new Error("Missing measurement");
    if (
      Math.max(...measurements.map((m) => m.timeSeconds)) -
        Math.min(...measurements.map((m) => m.timeSeconds)) >
      1
    )
      throw new Error("Candidate pool spans over one second");
    const best = (indices) =>
      side.measurements
        .filter((m) => indices.includes(m.index) && m.status === "usable")
        .sort((a, b) => b.sharpness - a.sharpness || a.index - b.index)[0]
        ?.index;
    const a = best(w.indices),
      b = best(w.compatibility.filter((c) => c.compatible).map((c) => c.index));
    if (a !== w.sharpest.index || b !== w.compatibleSharpest.index)
      throw new Error("Stored selection is not the best eligible frame");
    windows.push({
      side: side.side,
      indices: w.indices,
      baseline: side.baseIndex,
      a,
      b,
      outcomeA: w.sharpest.outcome?.verdict ?? "not-run",
      outcomeB: w.compatibleSharpest.outcome?.verdict ?? "not-run",
      failureA: w.sharpest.diagnostics?.failure ?? null,
      failureB: w.compatibleSharpest.diagnostics?.failure ?? null,
      durationA: w.sharpest.outcome?.durationMs ?? null,
      durationB: w.compatibleSharpest.outcome?.durationMs ?? null,
    });
  }
}
const result = {
  status: "AWAITING_INDEPENDENT_LABELS_AND_REAL_MAKEUP",
  kind: "Reanalysis of stored measurements, NOT a new inference or current-main benchmark",
  sourceHashes: hashes,
  clarity: {
    reviewItems: mapping.length,
    groups: Object.fromEntries(
      ["discovery", "validation"].map((g) => [
        g,
        mapping.filter((r) => r.group === g).length,
      ]),
    ),
    discovery: ratios(discovery),
    validation: ratios(validation),
    acceptance:
      "NOT RUN: no independent labels provided to this runner; no new threshold selected.",
    recommendation:
      "Keep the existing production gate. Score ordering is not false-acceptance accuracy.",
  },
  selection: {
    sourceRevision: video.revision,
    sourceCodeHashes: video.codeHashes,
    protocol: video.protocol,
    windows,
    directionConclusionsA: windows.filter((w) =>
      ["high", "low", "close"].includes(w.outcomeA),
    ).length,
    directionConclusionsB: windows.filter((w) =>
      ["high", "low", "close"].includes(w.outcomeB),
    ).length,
    acceptance:
      "NOT RUN: one negative clip, no independently labelled real-makeup positives; retain current production selection.",
  },
};
await mkdir(path.dirname(output), { recursive: true });
await writeFile(output, JSON.stringify(result, null, 2));
console.log(
  JSON.stringify({
    reviewItems: mapping.length,
    windows: windows.length,
    status: result.status,
    output,
  }),
);
