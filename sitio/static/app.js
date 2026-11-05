/* SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
   Copyright 2026 Daniel Delgado-Uriarte. Free for non-commercial use; companies need a licence (see NOTICE). */
// Open Well Data: theme toggle, bilingual search with facets, channel filter. No dependencies.
(function () {
  "use strict";
  var B = document.documentElement.dataset.base || "./";

  // Theme: system by default; the button cycles to the opposite of what is shown and remembers it.
  var tb = document.getElementById("theme");
  if (tb) tb.addEventListener("click", function () {
    var root = document.documentElement;
    var dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("owd-theme", root.dataset.theme); } catch (e) {}
    window.dispatchEvent(new Event("owd-theme"));
  });

  // Same normalisation as owd.catalog.normalize: lower case, no accents, words separated by single spaces.
  function nz(t) {
    return " " + String(t || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "")
      .split(/[^a-z0-9]+/).filter(Boolean).join(" ") + " ";
  }
  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // Copy buttons on citation boxes. Falls back to selecting the text if the clipboard is refused.
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-copy]"); if (!b) return;
    var pre = b.parentNode.querySelector(".cite-text"), txt = pre.textContent;
    var done = function () { b.textContent = "Copied"; setTimeout(function () { b.textContent = "Copy"; }, 1600); };
    var sel = function () { var r = document.createRange(); r.selectNodeContents(pre); var s = getSelection(); s.removeAllRanges(); s.addRange(r); b.textContent = "Selected"; };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(done, sel); else sel();
  });

  // Channel dictionary filter
  var cf = document.getElementById("cfilter");
  if (cf) cf.addEventListener("input", function () {
    var q = nz(cf.value).trim();
    document.querySelectorAll("tr[data-s]").forEach(function (tr) { tr.hidden = q && tr.dataset.s.indexOf(q) < 0; });
  });

  var resEl = document.getElementById("results");
  if (!resEl) return;

  var qEl = document.getElementById("q"), countEl = document.getElementById("count"), facEl = document.getElementById("facets");
  var FACETS = [
    { key: "s", title: "Verification", multi: false },
    { key: "t", title: "Discipline", multi: true, param: "d" },
    { key: "c", title: "Country" },
    { key: "a", title: "Access" },
    { key: "k", title: "Category" }
  ];
  var RANK = { confirmed: 0, web_verified: 1, declared: 2, seed: 3, not_stated: 4, url_discarded: 5 };
  var D, MULTI, sel = {}, expanded = {}, shown = 60;

  function terms(text) {
    var q = nz(text), out = [];
    MULTI.forEach(function (v) {
      if (q.indexOf(" " + v + " ") >= 0) { out.push(D.syn.find(function (g) { return g.indexOf(v) >= 0; })); q = q.replace(" " + v + " ", " "); }
    });
    q.split(" ").filter(Boolean).forEach(function (w) {
      out.push(D.syn.find(function (g) { return g.indexOf(w) >= 0; }) || [w]);
    });
    return out;
  }
  function has(s, v) { return v.length <= 3 ? s.indexOf(" " + v + " ") >= 0 : s.indexOf(v) >= 0; }
  function label(key, v) {
    var L = D.labels[key];
    return (L && L[v]) || v || "Not stated";
  }
  function val(it, key) { return key === "t" ? it.t : [it[key] || ""]; }

  function readURL() {
    var p = new URLSearchParams(location.search);
    qEl.value = p.get("q") || "";
    FACETS.forEach(function (f) {
      var raw = p.getAll(f.param || f.key);
      sel[f.key] = new Set(raw);
    });
  }
  function writeURL() {
    var p = new URLSearchParams();
    if (qEl.value.trim()) p.set("q", qEl.value.trim());
    FACETS.forEach(function (f) { sel[f.key].forEach(function (v) { p.append(f.param || f.key, v); }); });
    var s = p.toString();
    history.replaceState(null, "", location.pathname + (s ? "?" + s : ""));
  }

  function passes(it, ts, skip) {
    if (!ts.every(function (t) { return t.some(function (v) { return has(it._s, v); }); })) return false;
    return FACETS.every(function (f) {
      if (f.key === skip || !sel[f.key].size) return true;
      return val(it, f.key).some(function (v) { return sel[f.key].has(v); });
    });
  }

  function render() {
    var ts = terms(qEl.value);
    var res = D.items.filter(function (it) { return passes(it, ts, null); });
    var nameHit = function (it) { return ts.filter(function (t) { return t.some(function (v) { return has(it._n, v); }); }).length; };
    res.sort(function (a, b) { return nameHit(b) - nameHit(a) || RANK[a.s] - RANK[b.s] || a.n.localeCompare(b.n); });

    // Facet counts: each facet counted without its own selection, so options stay visible.
    facEl.innerHTML = FACETS.map(function (f) {
      var cnt = {};
      D.items.forEach(function (it) { if (passes(it, ts, f.key)) val(it, f.key).forEach(function (v) { cnt[v] = (cnt[v] || 0) + 1; }); });
      sel[f.key].forEach(function (v) { if (!(v in cnt)) cnt[v] = 0; });
      var keys = Object.keys(cnt).sort(function (a, b) {
        return f.key === "s" ? RANK[a] - RANK[b] : (cnt[b] - cnt[a]) || label(f.key, a).localeCompare(label(f.key, b));
      });
      var lim = expanded[f.key] ? keys.length : 7;
      var lis = keys.slice(0, lim).map(function (v) {
        var id = "f-" + f.key + "-" + v.replace(/[^a-z0-9]+/gi, "_");
        return '<li><label for="' + id + '"><input type="checkbox" id="' + id + '" data-f="' + f.key + '" value="' + esc(v) + '"' +
          (sel[f.key].has(v) ? " checked" : "") + "> " + esc(label(f.key, v)) + '<span class="n">' + cnt[v] + "</span></label></li>";
      }).join("");
      var more = keys.length > 7 ? '<button type="button" class="more-btn" data-more="' + f.key + '">' +
        (expanded[f.key] ? "Show fewer" : "Show all " + keys.length) + "</button>" : "";
      return '<div class="facet"><h3>' + f.title + "</h3><ul>" + lis + "</ul>" + more + "</div>";
    }).join("");

    var active = qEl.value.trim() || FACETS.some(function (f) { return sel[f.key].size; });
    countEl.innerHTML = res.length + " of " + D.items.length + " sources" +
      (active ? '<button type="button" class="clear" id="clear">Clear search and filters</button>' : "");

    var words = qEl.value.trim().split(/\s+/).filter(function (w) { return w.length > 2; })
      .map(function (w) { return w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); });
    var re = words.length ? new RegExp("(" + words.join("|") + ")", "gi") : null;
    var hl = function (t) { var e = esc(t); return re ? e.replace(re, "<mark>$1</mark>") : e; };

    resEl.innerHTML = res.slice(0, shown).map(function (it, i) {
      var sc = D.labels.sc[it.s] || "muted";
      return '<li class="res ' + sc + '"><div><h3><a href="' + B + "source/" + encodeURIComponent(it.i) + '/" data-id="' + esc(it.i) + '" data-position="' + (i + 1) + '">' + hl(it.n) + "</a></h3>" +
        (it.d ? "<p>" + hl(it.d) + "</p>" : "") +
        '<div class="meta"><span class="st st-' + sc + '">' + esc(label("s", it.s)) + "</span>" +
        (it.a && it.a !== "not_stated" ? '<span class="acc acc-' + esc(it.a) + '">' + esc(label("a", it.a)) + "</span>" : "") +
        (it.c ? '<span class="tag">' + esc(it.c) + "</span>" : "") +
        (it.k ? '<span class="tag">' + esc(label("k", it.k)) + "</span>" : "") +
        (it.l ? '<span class="tag" title="Licence">' + esc(it.l) + "</span>" : "") + "</div></div></li>";
    }).join("") + (res.length > shown ? '<li><button type="button" class="more-btn" id="showmore">Show ' + Math.min(60, res.length - shown) + " more</button></li>" : "");
    if (!res.length) resEl.innerHTML = '<li class="res"><div><h3>No source matches.</h3><p>Remove a filter or try a broader word. The search understands English and Spanish.</p></div></li>';
    // Measurement (only when the site runs its own collector): the search once the visitor pauses.
    clearTimeout(measureTimer);
    measureTimer = setTimeout(function () {
      if (!window.OWDMetrics || !window.OWDMetrics.search) return;
      var f = [];
      FACETS.forEach(function (x) { sel[x.key].forEach(function (v) { f.push(x.key + ":" + v); }); });
      window.OWDMetrics.search(qEl.value, res.length, f);
    }, 1500);
  }
  var measureTimer;

  facEl.addEventListener("change", function (e) {
    var t = e.target; if (!t.dataset.f) return;
    if (t.checked) sel[t.dataset.f].add(t.value); else sel[t.dataset.f].delete(t.value);
    shown = 60; writeURL(); render();
  });
  facEl.addEventListener("click", function (e) {
    var k = e.target.dataset && e.target.dataset.more; if (!k) return;
    expanded[k] = !expanded[k]; render();
  });
  document.addEventListener("click", function (e) {
    if (e.target.id === "clear") { qEl.value = ""; FACETS.forEach(function (f) { sel[f.key].clear(); }); shown = 60; writeURL(); render(); qEl.focus(); }
    if (e.target.id === "showmore") { shown += 60; render(); }
  });
  var timer;
  qEl.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(function () { shown = 60; writeURL(); render(); }, 120); });
  document.getElementById("sform").addEventListener("submit", function (e) { e.preventDefault(); writeURL(); render(); });

  fetch(B + "data/search.json").then(function (r) { return r.json(); }).then(function (d) {
    D = d;
    MULTI = Array.from(new Set([].concat.apply([], d.syn).filter(function (v) { return v.indexOf(" ") >= 0; })))
      .sort(function (a, b) { return b.length - a.length; });
    d.items.forEach(function (it) { it._s = nz(it.x); it._n = nz(it.n); });
    readURL(); render();
  }).catch(function () {
    countEl.textContent = "The catalogue could not be loaded. The full list is in data/sources.json.";
  });
})();
