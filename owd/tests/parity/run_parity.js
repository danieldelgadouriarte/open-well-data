/* SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
   Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE). */
// Parity test: the browser engine (sitio/static/convert.js) must reproduce the Python vectors exactly.
//   python owd/tests/parity/make_vectors.py OUT_DIR
//   node owd/tests/parity/run_parity.js OUT_DIR sitio/static/convert.js [sitio/static/convert-page.js]
// Exit code 0 when every CSV/LAS text is byte-identical and every provenance object is deep-equal.
"use strict";
const fs = require("fs");
const path = require("path");
const dir = process.argv[2] || "parity-out";
const enginePath = path.resolve(process.argv[3] || path.join(__dirname, "../../../sitio/static/convert.js"));
const OWD = require(enginePath);
const tables = JSON.parse(fs.readFileSync(path.join(dir, "tables.json"), "utf8"));
const V = JSON.parse(fs.readFileSync(path.join(dir, "vectors.json"), "utf8"));
const E = OWD.create(tables);
let fail = 0, pass = 0;

function deepEqual(a, b, where, out) {
  if (typeof a === "number" && typeof b === "number") { if (!(a === b || (a !== a && b !== b))) out.push(where + ": " + a + " != " + b); return; }
  if (a === null || b === null || typeof a !== "object" || typeof b !== "object") { if (a !== b) out.push(where + ": " + JSON.stringify(a) + " != " + JSON.stringify(b)); return; }
  if (Array.isArray(a) !== Array.isArray(b)) { out.push(where + ": array/object"); return; }
  const ka = Object.keys(a).sort(), kb = Object.keys(b).sort();
  if (ka.join("|") !== kb.join("|")) { out.push(where + ": keys " + ka.join(",") + " != " + kb.join(",")); return; }
  ka.forEach(k => deepEqual(a[k], b[k], where + "." + k, out));
}

function firstDiff(a, b) {
  const la = a.split("\n"), lb = b.split("\n");
  for (let i = 0; i < Math.max(la.length, lb.length); i++) if (la[i] !== lb[i]) return "line " + (i + 1) + ":\n  js: " + la[i] + "\n  py: " + lb[i];
  return "";
}

if (V.dictionary_version !== E.version) { console.log("tables and vectors come from different dictionary versions"); process.exit(2); }

for (const v of V.vectors) {
  const o = v.opts;
  let r;
  try {
    r = E.convertText(v.text, { names: o.names, units: o.units, to: o.to, csvHeader: o.csvHeader, comments: o.comments,
      digits: o.digits === undefined ? OWD.DEFAULT_DIGITS : o.digits, null: o.null, sourceFormat: o.sourceFormat,
      source: E.sourceInfo(o.source || null), fileName: v.file, inputSha256: v.sha256, now: v.now });
  } catch (e) { fail++; console.log("FAIL " + v.name + ": " + e.message); continue; }
  const diffs = [];
  if (r.text !== v.expected_text) diffs.push("text differs at " + firstDiff(r.text, v.expected_text));
  deepEqual(JSON.parse(JSON.stringify(r.provenance)), v.expected_provenance, "provenance", diffs);
  if (diffs.length) { fail++; console.log("FAIL " + v.name + "\n  " + diffs.slice(0, 5).join("\n  ")); } else pass++;
}
for (const [x, d, want] of V.numbers) {
  const got = OWD.fmtNumber(x, d);
  if (got !== want) { fail++; console.log("FAIL number " + x + " digits " + d + ": js " + got + " py " + want); } else pass++;
}

// Routes of the "Get data" button (no network: plans only).
const routes = [
  [E.getDataPlan("iodp-rigwatch", {}).route, "guided"],
  [E.getDataPlan("iodp-rigwatch", { copiesBase: "https://example.org/copies" }).route, "copy"],
  [E.getDataPlan("iodp-rigwatch", { helper: true }).route, "helper"],
  [E.getDataPlan("kgs-las", { copiesBase: "https://example.org/copies" }).route, "guided"],
  [E.getDataPlan("no-such-dataset", {}).route, "guided"],
];
routes.forEach(([got, want], i) => { if (got !== want) { fail++; console.log("FAIL route " + i + ": " + got + " != " + want); } else pass++; });

// Optional: page helpers (zip reader) when convert-page.js is given.
const pagePath = process.argv[4];
const finish = () => { console.log((fail ? "FAILED" : "OK") + ": " + pass + " passed, " + fail + " failed (dictionary " + E.version + ")"); process.exit(fail ? 1 : 0); };
if (pagePath && fs.existsSync(path.join(dir, "sample.zip"))) {
  const P = require(path.resolve(pagePath));
  const buf = new Uint8Array(fs.readFileSync(path.join(dir, "sample.zip")));
  const want = JSON.parse(fs.readFileSync(path.join(dir, "sample.zip.json"), "utf8"));
  P.unzipList(buf).then(list => {
    const names = list.map(e => e.name);
    if (JSON.stringify(names) !== JSON.stringify(Object.keys(want))) { fail++; console.log("FAIL zip names " + names); }
    return Promise.all(list.map(e => P.unzipEntry(buf, e).then(b => {
      const s = new TextDecoder().decode(b);
      if (s !== want[e.name]) { fail++; console.log("FAIL zip entry " + e.name); } else pass++;
    })));
  }).then(finish, e => { fail++; console.log("FAIL zip: " + e.message); finish(); });
} else finish();
