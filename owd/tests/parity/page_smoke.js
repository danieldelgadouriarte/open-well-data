/* SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
   Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE). */
// Smoke test of the /convert/ page script with a minimal fake DOM (no browser needed).
//   node owd/tests/parity/page_smoke.js SITE_DIR FIXTURE.las [sample.zip]
// SITE_DIR is sitio/_site after a build (it reads data/convert-tables.json and static/*.js from it).
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm");
const site = process.argv[2], fixture = process.argv[3], zip = process.argv[4];
const els = {};
function el(id) {
  if (!els[id]) els[id] = { id, textContent: "", innerHTML: "", value: "", hidden: false, className: "", href: "", dataset: {},
    classList: { add() {}, remove() {} }, handlers: {}, addEventListener(ev, f) { this.handlers[ev] = f; }, removeAttribute() {} };
  return els[id];
}
const radios = { "cv-names": "owd", "cv-to": "las" };
const ctx = {
  console, TextDecoder, TextEncoder, Blob, Response, URL, URLSearchParams, DecompressionStream, setTimeout, crypto: globalThis.crypto,
  location: { search: "?names=owd&units=field&to=las&u=hookload%3Atonne&src=volve", hash: "", pathname: "/convert/" },
  history: { replaceState() {} }, sessionStorage: { getItem() { return null; }, setItem() {} },
  document: { documentElement: { dataset: { base: "../" } }, getElementById: el,
    querySelector(sel) { const m = /name="([^"]+)"\]:checked/.exec(sel); return m ? { value: radios[m[1]] } : { checked: false }; },
    querySelectorAll() { return []; }, createElement() { return { click() {}, remove() {} }; }, body: { appendChild() {} } },
  fetch(url) {
    if (url.startsWith("../data/")) return Promise.resolve({ ok: true, json: () => Promise.resolve(JSON.parse(fs.readFileSync(path.join(site, url.slice(3)), "utf8"))) });
    return Promise.reject(new TypeError("network"));
  }
};
ctx.self = ctx; vm.createContext(ctx);
["cv-units", "cv-digits", "cv-header", "cv-null", "cv-source"].forEach(id => el(id));
el("cv-app"); el("cv-units").value = "field"; el("cv-digits").value = "12"; el("cv-header").value = "unit";
vm.runInContext(fs.readFileSync(path.join(site, "static/convert.js"), "utf8"), ctx);
vm.runInContext(fs.readFileSync(path.join(site, "static/convert-page.js"), "utf8"), ctx);
let fail = 0;
const check = (c, msg) => { if (!c) { fail++; console.log("FAIL " + msg); } };
setTimeout(async () => {
  const P = ctx.__owdConvertPage;
  check(P.state.sourceId === "volve", "source from the link");
  check(/src=volve/.test(P.permalink()) && /u=hookload%3Atonne/.test(P.permalink()), "permalink keeps settings " + P.permalink());
  check(/Equinor|Volve/.test(el("cv-srcline").innerHTML), "source line");
  check(/Processed with Open Well Data/.test(el("cv-cite").textContent) && /Equinor/.test(el("cv-srccite").textContent), "citation visible before any file");
  await P.handleBytes(new Uint8Array(fs.readFileSync(fixture)), path.basename(fixture));
  const r = P.state.result;
  check(r && /hookload\.tonne/.test(r.text) && /md\.ft/.test(r.text), "converted LAS with custom unit");
  check(r && r.provenance.source.dataset === "volve" && /Processed with Open Well Data/.test(el("cv-cite").textContent), "citation box");
  check(!el("cv-out").hidden, "download area shown");
  if (zip) {
    await P.handleBytes(new Uint8Array(fs.readFileSync(zip)), "sample.zip");
    check(/2 files in the archive/.test(el("cv-members").innerHTML), "zip member chooser");
  }
  console.log((fail ? "FAILED" : "OK") + ": page smoke test, " + fail + " failures");
  process.exit(fail ? 1 : 0);
}, 300);
