/* SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
   Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE). */
// The /convert/ page: choose a source or drop a file, pick names, units and format, download the result with its
// provenance and citation. The conversion runs here (convert.js); the file is never uploaded. Network requests happen
// only to load the site's own tables and, when you press "Get data", to fetch the file from where it is published
// (our copy, the source itself when it allows it, or `owd helper` on your own computer).
(function (root) {
  "use strict";

  // ---------------------------------------------------------------- zip reader (stored and deflate; no zip64)
  function u16(b, o) { return b[o] | (b[o + 1] << 8); }
  function u32(b, o) { return (b[o] | (b[o + 1] << 8) | (b[o + 2] << 16) | (b[o + 3] << 24)) >>> 0; }
  function unzipList(buf) {
    return Promise.resolve().then(function () {
      var b = buf, e = -1;
      for (var i = b.length - 22; i >= Math.max(0, b.length - 65557); i--) if (u32(b, i) === 0x06054b50) { e = i; break; }
      if (e < 0) throw new Error("not a zip file");
      var n = u16(b, e + 10), off = u32(b, e + 16), out = [];
      if (off === 0xffffffff || n === 0xffff) throw new Error("zip64 archives are not supported in the browser; use `owd get` or unzip it first");
      var dec = new TextDecoder();
      for (var k = 0; k < n; k++) {
        if (u32(b, off) !== 0x02014b50) throw new Error("damaged zip directory");
        var method = u16(b, off + 10), csize = u32(b, off + 20), size = u32(b, off + 24);
        var nl = u16(b, off + 28), xl = u16(b, off + 30), cl = u16(b, off + 32), lho = u32(b, off + 42);
        var name = dec.decode(b.subarray(off + 46, off + 46 + nl));
        if (name.slice(-1) !== "/") out.push({ name: name, method: method, csize: csize, size: size, offset: lho });
        off += 46 + nl + xl + cl;
      }
      return out;
    });
  }
  function unzipEntry(buf, e) {
    var b = buf, o = e.offset;
    if (u32(b, o) !== 0x04034b50) return Promise.reject(new Error("damaged zip entry"));
    var start = o + 30 + u16(b, o + 26) + u16(b, o + 28), data = b.subarray(start, start + e.csize);
    if (e.method === 0) return Promise.resolve(data);
    if (e.method !== 8) return Promise.reject(new Error("unsupported zip compression (method " + e.method + ")"));
    if (typeof DecompressionStream === "undefined") return Promise.reject(new Error("this browser cannot unzip; unzip the file first"));
    var ds = new DecompressionStream("deflate-raw");
    var stream = new Blob([data]).stream().pipeThrough(ds);
    return new Response(stream).arrayBuffer().then(function (ab) { return new Uint8Array(ab); });
  }

  // ---------------------------------------------------------------- notebook for Colab / Jupyter (no data in it)
  function notebook(nb) {
    function cell(type, src) {
      var c = { cell_type: type, metadata: {}, source: src.split("\n").map(function (l, i, a) { return i < a.length - 1 ? l + "\n" : l; }) };
      if (type === "code") { c.outputs = []; c.execution_count = null; }
      return c;
    }
    var cmd = "owd get " + nb.spec + " --names " + nb.names + " --units " + nb.units + " --to " + nb.to + " -o owd_output";
    return JSON.stringify({ nbformat: 4, nbformat_minor: 5, metadata: { kernelspec: { name: "python3", display_name: "Python 3" },
      language_info: { name: "python" } }, cells: [
      cell("markdown", "# Open Well Data: get and convert\n\nDownloads the data from its source on this machine (no login, no terms accepted for you), converts it to the names and units below and saves it with its citation and provenance.\n\nSettings: " + nb.permalink + "\n\nNon-commercial use with credit. Companies need written permission: contact@openwelldata.org."),
      cell("code", "# Install Open Well Data (edit this line if you install it another way)\n!" + nb.pip),
      cell("code", "# Your settings (edit if you like)\nSPEC = " + JSON.stringify(nb.spec) + "\nNAMES = " + JSON.stringify(nb.names) + "   # owd or original\nUNITS = " + JSON.stringify(nb.units) + "   # si, field, or e.g. 'field,spp=bar'\nTO = " + JSON.stringify(nb.to) + "   # csv, las or parquet"),
      cell("code", "!owd get \"$SPEC\" --names \"$NAMES\" --units \"$UNITS\" --to \"$TO\" -o owd_output\n# Equivalent: " + cmd),
      cell("code", "# Download the results (Colab); in Jupyter they are in the owd_output folder\nimport glob, os\nfiles = sorted(glob.glob('owd_output/*'))\nprint('\\n'.join(files))\ntry:\n    from google.colab import files as colab_files\n    for f in files:\n        colab_files.download(f)\nexcept ImportError:\n    pass"),
      cell("code", "# How to cite\nimport json, glob\nfor p in sorted(glob.glob('owd_output/*.provenance.json'))[:1]:\n    c = json.load(open(p))['how_to_cite']\n    print(c['full']); print(); print(c['bibtex']); print(); print('Source:', c['source'], '| Licence:', c['source_license'])")
    ] }, null, 1);
  }

  if (typeof module === "object" && module.exports) { module.exports = { unzipList: unzipList, unzipEntry: unzipEntry, notebook: notebook }; return; }

  // ---------------------------------------------------------------- page
  var $ = function (id) { return document.getElementById(id); };
  var app = $("cv-app");
  if (!app) return;
  var B = document.documentElement.dataset.base || "../";
  var OWD = root.OWDConvert, E = null, T = null;
  var state = { text: null, fileName: "", sha: null, kind: null, plans: null, result: null, sourceId: "", helper: null, zip: null };
  var MAX_SIZE = 400 * 1024 * 1024;

  function esc(t) { return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function say(msg, bad) { var s = $("cv-status"); s.textContent = msg; s.className = "cv-status" + (bad ? " cv-bad" : ""); }
  function q(name) { return new URLSearchParams(location.search).get(name); }

  // settings <-> form <-> URL
  function settings() {
    var names = document.querySelector('input[name="cv-names"]:checked').value;
    var to = document.querySelector('input[name="cv-to"]:checked').value;
    var preset = $("cv-units").value, units = preset;
    var custom = Object.assign({}, state.urlUnits || {});
    document.querySelectorAll("select[data-var]").forEach(function (s) { if (s.value && s.value !== s.dataset.preset) custom[s.dataset.var] = s.value; });
    if (Object.keys(custom).length) {
      units = {}; if (preset === "field") units._default = "field";
      Object.keys(custom).forEach(function (k) { units[k] = custom[k]; });
    }
    var d = $("cv-digits").value;
    return { names: names, to: to, units: units, digits: d === "full" ? 0 : Number(d), csvHeader: $("cv-header").value,
      null: $("cv-null").value.trim() || null };
  }
  function applyUrl() {
    var n = q("names"), u = q("units"), to = q("to"), d = q("d"), h = q("h"), v = q("v"), src = q("src");
    if (n === "owd" || n === "original") document.querySelector('input[name="cv-names"][value="' + n + '"]').checked = true;
    if (u === "si" || u === "field") $("cv-units").value = u;
    if (to === "csv" || to === "las") document.querySelector('input[name="cv-to"][value="' + to + '"]').checked = true;
    if (d !== null) $("cv-digits").value = d === "0" ? "full" : (["6", "8", "10", "12"].indexOf(d) >= 0 ? d : "12");
    if (h === "plain") $("cv-header").value = "plain";
    state.urlUnits = {};
    (q("u") || "").split(",").forEach(function (p) { var kv = p.split(":"); if (kv.length === 2) state.urlUnits[kv[0]] = kv[1]; });
    if (v && E && v !== E.version) {
      $("cv-version").hidden = false;
      $("cv-version").innerHTML = "This link was made with dictionary version <code>" + esc(v) + "</code>; the site now uses <code>" + esc(E.version) +
        "</code>. Results can differ where the dictionary changed. Older versions are in the repository history.";
    }
    if (src) { $("cv-source").value = src; pickSource(); }
  }
  function permalink() {
    var s = settings(), link = E.permalink(s.names, s.units, s.to, s.digits, s.csvHeader);
    if (state.sourceId) link += "&src=" + encodeURIComponent(state.sourceId);
    return link;
  }
  function refreshLink() {
    if (!E) return;
    var link = permalink();
    $("cv-link").textContent = link;
    if (!state.result) {
      var st = settings(), c = E.cite(st.names, st.units, st.to, st.digits, st.csvHeader), i = state.sourceId ? info(state.sourceId) : null;
      $("cv-cite").textContent = c.full; $("cv-bib").textContent = c.bibtex;
      $("cv-srccite").textContent = i ? ((i.citation || (i.name + ". " + i.url)).replace(/\.?\s*$/, ".") + " Licence: " + (i.license && i.license !== "not stated" ? i.license : "as stated by the source") + ".")
        : "As stated by the source of your file.";
    }
    try { history.replaceState(null, "", "?" + link.split("?")[1] + location.hash); } catch (_) {}
    refreshPython();
  }

  // ---------------------------------------------------------------- sources and routes
  function sources() {
    var out = [], seen = {};
    Object.keys(T.datasets || {}).forEach(function (id) { var d = T.datasets[id]; out.push({ id: id, name: d.name, kind: "dataset" }); seen[id] = 1; });
    Object.keys(T.sources || {}).forEach(function (id) { if (!seen[id]) out.push({ id: id, name: T.sources[id].name, kind: "source" }); });
    return out;
  }
  function info(id) {
    var d = (T.datasets || {})[id], s = (T.sources || {})[id];
    if (!d && !s) return null;
    return { id: id, name: (d || s).name, url: (d && d.url) || (s && s.url) || "", license: (d && d.license) || (s && s.license) || "",
      citation: d ? d.citation : null, policy: d ? d.policy : null, download: d ? d.download : null, method: s ? s.method : null,
      flow: s ? s.browser_flow : null, example: s ? s.example_file_url : null, terms: (s && s.terms_url) || (d && d.terms) || "" };
  }
  function routeFor(id) {
    var i = info(id); if (!i) return null;
    var plan = E.getDataPlan(id, { helper: !!state.helper });
    if (plan.route !== "guided" || !i.flow) return plan;
    if (state.helper && (i.method === "direct_cors" || i.method === "direct_no_cors" || i.method === "bulk")) return { route: "helper-source", fallback: plan };
    if (i.flow === "one_click" && i.method === "direct_cors" && i.example && /\.(las|csv|txt|zip)(\/content)?$/i.test(i.example.split("?")[0]))
      return { route: "direct", files: [{ name: i.example.split("/").filter(function (x) { return x && x !== "content"; }).pop(), url: i.example }], fallback: plan };
    if (i.flow === "toolkit_only") return { route: "toolkit", fallback: plan };
    if (i.flow === "not_downloadable") return { route: "none", fallback: plan };
    return { route: "guided", source: i.url };
  }
  function pickSource() {
    var id = $("cv-source").value.trim().split(" ")[0];
    var i = info(id), box = $("cv-route");
    state.sourceId = i ? id : "";
    $("cv-get").hidden = true;
    if (!i) { box.innerHTML = ""; $("cv-srcline").textContent = "Source: as stated by the source (choose one above, or drop a file)."; refreshLink(); return; }
    $("cv-srcline").innerHTML = "Source: " + esc(i.name) + ", licence " + (i.license && i.license !== "not stated" ? esc(i.license) : "as stated by the source") +
      (i.url ? ' · <a href="' + esc(i.url) + '" rel="noopener nofollow" target="_blank">source page</a>' : "");
    var r = routeFor(id), h = "";
    if (r.route === "copy") h = "<p>We keep a standardized copy of this dataset. <strong>Get data</strong> downloads it from our copy and converts it here.</p>";
    else if (r.route === "helper" || r.route === "helper-source") h = "<p>Your local helper is running. <strong>Get data</strong> asks it to download the file from the source on your computer; the conversion runs here.</p>";
    else if (r.route === "direct") h = "<p>This source lets browsers download its files. <strong>Get data</strong> fetches <code>" + esc(r.files[0].name) + "</code> from the source and converts it here.</p>";
    else if (r.route === "toolkit") h = "<p>This source needs the Python toolkit (large files or formats a browser cannot read). Use the command or the notebook below.</p>";
    else if (r.route === "none") h = "<p>This source has no file to download (documents, an index or software). See its page.</p>";
    else h = '<ol class="cv-steps"><li><a class="cv-btn" href="' + esc(i.url) + '" target="_blank" rel="noopener nofollow">1. Download it from ' + esc(i.name) + "</a> " +
      '<span class="small muted">(opens its page in a new tab; accept its terms there only if you agree)</span></li>' +
      "<li>2. Drop the file here, below. It is converted at once, in this page.</li></ol>" +
      '<p class="small muted">Prefer one click? Run <code>owd helper</code> on your computer (see below) or open the notebook in Colab.</p>';
    box.innerHTML = h;
    $("cv-get").hidden = !(r.route === "copy" || r.route === "direct" || r.route === "helper" || r.route === "helper-source");
    state.route = r;
    refreshLink();
  }

  function fetchBytes(url, opts) {
    return fetch(url, opts || {}).then(function (r) {
      if (!r.ok) return r.text().then(function (t) { var m = t; try { m = JSON.parse(t).error; } catch (_) {} throw new Error("HTTP " + r.status + (m ? ": " + m : "")); });
      return r.arrayBuffer().then(function (b) { return { bytes: new Uint8Array(b), name: r.headers.get("X-OWD-File") }; });
    });
  }
  function helperCall(body) {
    var h = state.helper;
    return fetchBytes("http://127.0.0.1:" + h.port + "/v1/fetch", { method: "POST", headers: { "Authorization": "Bearer " + h.token, "Content-Type": "application/json" }, body: JSON.stringify(body) });
  }
  function getData() {
    var r = state.route, id = state.sourceId;
    if (!r) return;
    say("Getting the data…");
    var p;
    if (r.route === "copy") p = fetch(r.index).then(function (x) { if (!x.ok) throw new Error("HTTP " + x.status); return x.json(); })
      .then(function (j) { var f = (j.files || []).filter(function (f) { return /\.(las|csv)$/i.test(f.name); })[0]; if (!f) throw new Error("no LAS or CSV file in our copy"); return fetchBytes(f.url).then(function (b) { b.name = f.name; return b; }); });
    else if (r.route === "direct") p = fetchBytes(r.files[0].url).then(function (b) { b.name = r.files[0].name; return b; });
    else if (r.route === "helper") p = helperCall({ dataset: id });
    else if (r.route === "helper-source") p = helperCall({ source: id });
    else return;
    p.then(function (b) {
      var bytes = b.bytes, name = b.name || id;
      if (bytes.length && bytes[0] === 0x7b) {     // JSON from the helper: a zip listing
        var j = JSON.parse(new TextDecoder().decode(bytes));
        if (j.files) return chooseHelperMember(j.files, r.route === "helper" ? { dataset: id } : { source: id });
      }
      return handleBytes(bytes, name);
    }).catch(function (e) {
      var cors = e instanceof TypeError;
      say((cors ? "The browser could not fetch it (the source does not allow it, or the network failed). " : "Could not get it: " + e.message + ". ") +
        "Use the two steps: download it from the source, then drop it here.", true);
      var i = info(id);
      if (i) { state.route = { route: "guided" }; $("cv-get").hidden = true;
        $("cv-route").innerHTML = '<ol class="cv-steps"><li><a class="cv-btn" href="' + esc(i.url) + '" target="_blank" rel="noopener nofollow">1. Download it from ' + esc(i.name) + "</a></li><li>2. Drop the file here, below.</li></ol>"; }
    });
  }
  function chooseHelperMember(files, base) {
    var list = files.filter(function (f) { return /\.(las|csv)$/i.test(f); });
    say(list.length + " LAS/CSV files in the archive. Choose one.");
    $("cv-members").hidden = false;
    $("cv-members").innerHTML = '<label for="cv-member">File in the archive</label> <select id="cv-member">' + list.map(function (f) { return "<option>" + esc(f) + "</option>"; }).join("") + '</select> <button type="button" class="cv-btn" id="cv-member-go">Convert this file</button>';
    $("cv-member-go").onclick = function () {
      var m = $("cv-member").value, body = Object.assign({ member: m }, base);
      say("Getting " + m + "…");
      helperCall(body).then(function (b) { return handleBytes(b.bytes, m); }).catch(function (e) { say("Could not get it: " + e.message, true); });
    };
  }

  // ---------------------------------------------------------------- files
  function sha256(bytes) {
    if (!(root.crypto && crypto.subtle)) return Promise.resolve(null);
    return crypto.subtle.digest("SHA-256", bytes).then(function (h) { return Array.from(new Uint8Array(h)).map(function (x) { return x.toString(16).padStart(2, "0"); }).join(""); });
  }
  function decode(bytes) {
    try { return new TextDecoder("utf-8", { fatal: true }).decode(bytes); } catch (_) { return new TextDecoder("windows-1252").decode(bytes); }
  }
  function handleBytes(bytes, name) {
    if (bytes.length > 3 && u32(bytes, 0) === 0x04034b50) {
      state.zip = bytes;
      return unzipList(bytes).then(function (list) {
        list = list.filter(function (e) { return /\.(las|csv|txt)$/i.test(e.name); });
        if (!list.length) throw new Error("no LAS or CSV file in " + name);
        if (list.length === 1) return unzipEntry(bytes, list[0]).then(function (b) { return useFile(b, list[0].name.split("/").pop()); });
        $("cv-members").hidden = false;
        $("cv-members").innerHTML = '<label for="cv-member">' + list.length + ' files in the archive</label> <select id="cv-member">' + list.map(function (e, i) { return '<option value="' + i + '">' + esc(e.name) + "</option>"; }).join("") + '</select> <button type="button" class="cv-btn" id="cv-member-go">Convert this file</button>';
        say("Choose a file in the archive.");
        $("cv-member-go").onclick = function () { var e = list[Number($("cv-member").value)]; unzipEntry(bytes, e).then(function (b) { useFile(b, e.name.split("/").pop()); }).catch(function (x) { say(x.message, true); }); };
      }).catch(function (e) { say(e.message, true); });
    }
    return useFile(bytes, name);
  }
  function useFile(bytes, name) {
    if (bytes.length > MAX_SIZE) { say("This file is larger than " + (MAX_SIZE >> 20) + " MB. Convert it with the Python toolkit (owd convert), which works in blocks.", true); return; }
    return sha256(bytes).then(function (h) {
      state.text = decode(bytes); state.fileName = name; state.sha = h;
      state.kind = /^\s*~/.test(state.text.replace(/^\ufeff/, "")) ? "las" : "csv";
      $("cv-null-row").hidden = state.kind !== "csv";
      run();
    });
  }
  function run() {
    if (!state.text) return;
    var s = settings();
    try {
      var src = state.sourceId ? E.sourceInfo(info(state.sourceId) && T.datasets && T.datasets[state.sourceId] ? state.sourceId : null) : E.sourceInfo(null);
      if (state.sourceId && !(T.datasets && T.datasets[state.sourceId])) { var i = info(state.sourceId); src = E.sourceInfo(null, i.name + ". " + i.url, i.license && i.license !== "not stated" ? i.license : null, i.url); }
      var r = E.convertText(state.text, { names: s.names, units: s.units, to: s.to, digits: s.digits, csvHeader: s.csvHeader,
        null: s.null, fileName: state.fileName, inputSha256: state.sha, source: src });
      state.result = r; state.urlUnits = null;
      say("Converted " + state.fileName + ": " + r.provenance.summary.channels + " channels, " + r.provenance.summary.labelled + " with OWD names, " +
        r.provenance.summary.converted + " converted, " + r.provenance.input.rows + " rows. Nothing left this page.");
      render(r);
    } catch (e) { state.result = null; $("cv-out").hidden = true; say(e.message, true); }
    refreshLink();
  }
  function unitSelect(p, preset) {
    var V = T.variables[p.variable], std = E.unitRow(V.unit, V.dimension);
    var opts = E.unitsOf(V.dimension, std ? std.base : null), cur = p.unit || V.unit;
    if (opts.length < 2) return esc(p.unit);
    var pre = E.targetUnit(p.variable, preset);
    return '<label class="sr" for="u-' + esc(p.variable) + '">Unit for ' + esc(p.variable) + '</label><select id="u-' + esc(p.variable) + '" data-var="' + esc(p.variable) +
      '" data-preset="' + esc(pre) + '">' + opts.map(function (o) { return "<option" + (o === cur ? " selected" : "") + ">" + esc(o) + "</option>"; }).join("") + "</select>";
  }
  function render(r) {
    var preset = $("cv-units").value === "field" ? "field" : "si", seenVar = {};
    var rows = r.provenance.channels.map(function (c) {
      var st = c.status, cls = st === "converted" || st === "renamed" ? "ok" : (st === "unmapped" ? "muted" : "warn");
      var unit = c.variable && !seenVar[c.variable] ? unitSelect(c, preset) : esc(c.unit);
      if (c.variable) seenVar[c.variable] = 1;
      return "<tr><td><code>" + esc(c.original_name) + "</code></td><td>" + esc(c.original_unit) + "</td><td><code>" + esc(c.name) + "</code></td><td>" + unit +
        '</td><td class="num">' + (c.converted ? esc(OWD.fmtNumber(c.factor)) + (c.offset ? " " + (c.offset > 0 ? "+" : "−") + esc(OWD.fmtNumber(Math.abs(c.offset))) : "") : "") +
        '</td><td><span class="st st-' + cls + '">' + esc(st.replace(/_/g, " ")) + "</span>" + (c.mapped_by ? ' <span class="small muted">' + esc(c.mapped_by.replace(/_/g, " ")) + "</span>" : "") +
        "</td><td class=\"small\">" + esc(c.warnings.concat(c.unit_note ? ["unit read as: " + c.unit_note] : []).concat(c.unit_rule ? ["rule: " + c.unit_rule.note] : []).join(" · ")) + "</td></tr>";
    }).join("");
    $("cv-table").innerHTML = rows;
    document.querySelectorAll("select[data-var]").forEach(function (s) { s.addEventListener("change", run); });
    var w = r.provenance.warnings;
    $("cv-filewarn").innerHTML = w.length ? "<p class=\"note\">" + w.map(esc).join("<br>") + "</p>" : "";
    $("cv-cite").textContent = r.provenance.how_to_cite.full;
    $("cv-bib").textContent = r.provenance.how_to_cite.bibtex;
    $("cv-srccite").textContent = r.provenance.how_to_cite.source.replace(/\.?\s*$/, ".") + " Licence: " + r.provenance.how_to_cite.source_license + ".";
    $("cv-out").hidden = false;
  }
  function download(text, name, type) {
    var a = document.createElement("a"), url = URL.createObjectURL(new Blob([text], { type: type }));
    a.href = url; a.download = name; document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(url); a.remove(); }, 1000);
  }
  function outName(ext) { return (state.fileName || "data").replace(/\.[^.]+$/, "") + ".owd." + ext; }

  // ---------------------------------------------------------------- Python, notebook and helper
  function unitsArg(u) { if (typeof u === "string") return u; var parts = [u._default || "si"]; Object.keys(u).sort().forEach(function (k) { if (k !== "_default") parts.push(k + "=" + u[k]); }); return parts.join(","); }
  // What `owd get` receives: a recipe id (packaged with owd), else the source's public file URL, else the source id.
  function pySpec() {
    var id = state.sourceId, i = id ? info(id) : null;
    if (!i) return null;
    if (i.download === "auto") return id;
    if (i.example && ["direct_cors", "direct_no_cors", "bulk"].indexOf(i.method) >= 0) return i.example;
    return id;
  }
  function refreshPython() {
    var s = settings(), spec = pySpec() || "<dataset, source or https URL>";
    var cmd = "owd get " + spec + " --names " + s.names + " --units " + unitsArg(s.units) + " --to " + s.to + " -o owd_output";
    $("cv-cmd").textContent = "pip install " + (T.notebook && T.notebook.pip_target || "openwelldata") + "\n" + cmd;
    var nbBase = T.notebook && T.notebook.colab, bb = T.notebook && T.notebook.binder;
    $("cv-colab").hidden = !nbBase; if (nbBase) $("cv-colab").href = nbBase;
    $("cv-binder").hidden = !bb; if (bb) $("cv-binder").href = bb;
  }
  function detectHelper() {
    var m = /helper=(\d+)\.([A-Za-z0-9_\-]+)/.exec(location.hash), h = null;
    try { if (m) sessionStorage.setItem("owd-helper", m[1] + "." + m[2]); var sv = sessionStorage.getItem("owd-helper"); if (sv) { var p = sv.split("."); h = { port: p[0], token: p.slice(1).join(".") }; } } catch (_) {}
    if (m) { try { history.replaceState(null, "", location.pathname + location.search); } catch (_) {} }
    if (!h) return Promise.resolve(null);
    return fetch("http://127.0.0.1:" + h.port + "/v1/status", { headers: { "Authorization": "Bearer " + h.token } })
      .then(function (r) { if (!r.ok) throw new Error(); state.helper = h; $("cv-helper-state").textContent = "Local helper connected (127.0.0.1:" + h.port + ")."; return h; })
      .catch(function () { $("cv-helper-state").textContent = "Local helper not found. Start it with owd helper and open the link it prints."; return null; });
  }

  // ---------------------------------------------------------------- wiring
  function wire() {
    var drop = $("cv-drop"), input = $("cv-file");
    input.addEventListener("change", function () { var f = input.files[0]; if (f) readFile(f); });
    ["dragenter", "dragover"].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add("cv-over"); }); });
    ["dragleave", "drop"].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove("cv-over"); }); });
    drop.addEventListener("drop", function (e) { var f = e.dataTransfer.files[0]; if (f) readFile(f); });
    document.querySelectorAll('#cv-options input, #cv-options select').forEach(function (el) { el.addEventListener("change", function () { if (el.id === "cv-units") document.querySelectorAll("select[data-var]").forEach(function (s) { s.removeAttribute("data-var"); }); run(); refreshLink(); }); });
    $("cv-source").addEventListener("change", pickSource);
    $("cv-get").addEventListener("click", getData);
    $("cv-dl").addEventListener("click", function () {
      if (!state.result) return;
      download(state.result.text, outName(settings().to), settings().to === "csv" ? "text/csv" : "text/plain");
      // Measurement, where on: the input and output format only, never the file, its name or its content.
      if (window.OWDMetrics && window.OWDMetrics.convert) window.OWDMetrics.convert(state.kind, settings().to);
    });
    $("cv-dlprov").addEventListener("click", function () { if (state.result) download(OWD.provenanceJson(state.result.provenance), outName("provenance.json"), "application/json"); });
    $("cv-nb").addEventListener("click", function () {
      var s = settings();
      download(notebook({ spec: pySpec() || "https://example.org/your-file.las", names: s.names, units: unitsArg(s.units), to: s.to, permalink: permalink(),
        pip: "pip install -q " + ((T.notebook && T.notebook.pip_target) || "openwelldata") }), "owd-" + (state.sourceId || "convert") + ".ipynb", "application/x-ipynb+json");
      if (window.OWDMetrics && window.OWDMetrics.convert) window.OWDMetrics.convert("notebook", s.to);
    });
  }
  function readFile(f) {
    say("Reading " + f.name + "…");
    var r = new FileReader();
    r.onload = function () { handleBytes(new Uint8Array(r.result), f.name); };
    r.onerror = function () { say("Could not read the file.", true); };
    r.readAsArrayBuffer(f);
  }

  root.__owdConvertPage = { state: state, handleBytes: handleBytes, settings: settings, permalink: permalink, run: run, pickSource: pickSource, routeFor: routeFor };
  fetch(B + "data/convert-tables.json").then(function (r) { return r.json(); }).then(function (t) {
    T = t; E = OWD.create(t);
    $("cv-dict").textContent = E.version;
    var dl = $("cv-sources");
    dl.innerHTML = sources().map(function (s) { return '<option value="' + esc(s.id) + '">' + esc(s.name) + "</option>"; }).join("");
    wire(); applyUrl(); refreshLink();
    return detectHelper().then(function () { if (state.sourceId) pickSource(); });
  }).catch(function (e) { say("Could not load the conversion tables: " + e.message, true); });
})(typeof self !== "undefined" ? self : this);
