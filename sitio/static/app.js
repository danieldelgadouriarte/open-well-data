/* SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
   Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE). */
// Open Well Data, web v2: progressive enhancement only. Every table is complete in the HTML; this file adds the theme
// switch, copy buttons, sorting, filters with their state in the URL, row density, column choice and the details panel.
// No dependencies, no requests to third parties.
(function () {
  "use strict";
  var B = document.documentElement.dataset.base || "./";
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };
  function $(id) { return document.getElementById(id); }
  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  // Same normalisation as owd.catalog.normalize: lower case, no accents, words separated by single spaces.
  function nz(t) {
    return " " + String(t || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "")
      .split(/[^a-z0-9]+/).filter(Boolean).join(" ") + " ";
  }

  // ------------------------------------------------------------ theme
  var tb = $("theme");
  function isDark() {
    var r = document.documentElement;
    return r.dataset.theme === "dark";  // light unless the reader chose dark (the system preference is not followed)
  }
  function themeLabel() {
    if (!tb) return;
    var d = isDark();
    tb.textContent = d ? "Light theme" : "Dark theme";
    tb.setAttribute("aria-pressed", d ? "true" : "false");
  }
  if (tb) {
    themeLabel();
    tb.addEventListener("click", function () {
      var r = document.documentElement;
      r.dataset.theme = isDark() ? "light" : "dark";
      store.set("owd-theme", r.dataset.theme);
      themeLabel();
      window.dispatchEvent(new Event("owd-theme"));
    });
  }

  // ------------------------------------------------------------ copy buttons on citation boxes
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-copy]"); if (!b) return;
    var pre = b.parentNode.querySelector(".cite-text"), txt = pre.textContent;
    var label = b.dataset.label || (b.dataset.label = b.textContent);
    var done = function () { b.textContent = "Copied"; setTimeout(function () { b.textContent = label; }, 1600); };
    var sel = function () { var r = document.createRange(); r.selectNodeContents(pre); var s = getSelection(); s.removeAllRanges(); s.addRange(r); b.textContent = "Selected: press Ctrl+C"; setTimeout(function () { b.textContent = label; }, 2400); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(done, sel); else sel();
  });

  // ------------------------------------------------------------ simple row filter (channel and variable dictionaries)
  var cf = $("cfilter");
  if (cf) cf.addEventListener("input", function () {
    var q = nz(cf.value).trim();
    document.querySelectorAll("tr[data-s]").forEach(function (tr) { tr.hidden = q && tr.dataset.s.indexOf(q) < 0; });
  });

  // ------------------------------------------------------------ sorting: every table with data-sort
  function cellValue(row, i) {
    var c = row.cells[i]; if (!c) return "";
    return c.hasAttribute("data-v") ? c.getAttribute("data-v") : c.textContent.trim();
  }
  function numeric(v) { var x = parseFloat(String(v).replace(/[,\s]/g, "")); return isNaN(x) ? null : x; }
  function sortTable(t, i, dir) {
    var body = t.tBodies[0], rows = [].slice.call(body.rows);
    var th = t.tHead.rows[0].cells[i], isNum = th.classList.contains("num") && !/check/i.test(th.textContent);
    rows.sort(function (a, b) {
      var x = cellValue(a, i), y = cellValue(b, i), r;
      if (isNum) { var nx = numeric(x), ny = numeric(y); r = (nx === null ? -Infinity : nx) - (ny === null ? -Infinity : ny); }
      else r = x.localeCompare(y, "en", { numeric: true, sensitivity: "base" });
      return dir === "descending" ? -r : r;
    });
    rows.forEach(function (r) { body.appendChild(r); });
    [].forEach.call(t.tHead.rows[0].cells, function (c, j) { if (j === i) c.setAttribute("aria-sort", dir); else c.removeAttribute("aria-sort"); });
    var cap = t.caption && t.caption.querySelector(".muted");
    if (cap && t.dataset.capBase === undefined) t.dataset.capBase = cap.textContent;
  }
  function initSort(t) {
    if (!t.tHead || !t.tBodies[0]) return;
    var param = t.dataset.sortParam;
    [].forEach.call(t.tHead.rows[0].cells, function (th, i) {
      if (th.hasAttribute("data-nosort") || th.classList.contains("js-only") && !th.textContent.trim()) return;
      var b = document.createElement("button");
      b.type = "button"; b.className = "sortbtn";
      while (th.firstChild) b.appendChild(th.firstChild);
      th.appendChild(b);
      b.addEventListener("click", function () {
        var dir = th.getAttribute("aria-sort") === "ascending" ? "descending" : "ascending";
        sortTable(t, i, dir);
        if (param) { var p = new URLSearchParams(location.search); p.set(param, (dir === "descending" ? "-" : "") + i); history.replaceState(null, "", location.pathname + "?" + p.toString() + location.hash); }
      });
    });
    if (param) {
      var v = new URLSearchParams(location.search).get(param);
      if (v && /^-?\d+$/.test(v)) { var i = Math.abs(parseInt(v, 10)); if (t.tHead.rows[0].cells[i]) sortTable(t, i, v.charAt(0) === "-" ? "descending" : "ascending"); }
    }
  }
  document.querySelectorAll("table[data-sort]").forEach(initSort);

  // ------------------------------------------------------------ row density (remembered on this device)
  function applyDensity(btn, dense) {
    var t = $(btn.dataset.densityFor); if (!t) return;
    t.classList.toggle("dense", dense);
    btn.setAttribute("aria-pressed", dense ? "true" : "false");
    btn.textContent = dense ? "Comfortable rows" : "Compact rows";
  }
  document.querySelectorAll("[data-density-for]").forEach(function (btn) {
    applyDensity(btn, store.get("owd-density") === "dense");
    btn.addEventListener("click", function () {
      var dense = btn.getAttribute("aria-pressed") !== "true";
      store.set("owd-density", dense ? "dense" : "comfortable");
      document.querySelectorAll("[data-density-for]").forEach(function (b) { applyDensity(b, dense); });
    });
  });

  // ------------------------------------------------------------ show or hide columns
  document.querySelectorAll("[data-columns-for]").forEach(function (d) {
    var t = $(d.dataset.columnsFor); if (!t || !t.tHead) return;
    var box = d.querySelector(".cols-box"), style = document.createElement("style");
    document.head.appendChild(style);
    var hidden = {};
    function apply() {
      style.textContent = Object.keys(hidden).filter(function (k) { return hidden[k]; }).map(function (k) {
        return "#" + t.id + " tr > :nth-child(" + (+k + 1) + ")";
      }).join(",") + (Object.keys(hidden).some(function (k) { return hidden[k]; }) ? "{display:none}" : "");
    }
    [].forEach.call(t.tHead.rows[0].cells, function (th, i) {
      if (i === 0 || th.hasAttribute("data-nosort")) return;
      var lab = document.createElement("label"), cb = document.createElement("input");
      cb.type = "checkbox"; cb.checked = true;
      cb.addEventListener("change", function () { hidden[i] = !cb.checked; apply(); });
      lab.appendChild(cb); lab.appendChild(document.createTextNode(" " + th.textContent.trim()));
      box.appendChild(lab);
    });
  });

  // ------------------------------------------------------------ filters for a server-rendered table
  function initFilter(form) {
    var t = $(form.dataset.filterFor); if (!t) return;
    var tid = t.id, rows = [].slice.call(t.tBodies[0].rows), unit = form.dataset.unit || "rows";
    var ctrls = [].slice.call(form.querySelectorAll("input[data-match], select[data-attr]"));
    var qEl = form.querySelector('input[data-match="text"]');
    var countEl = $(tid + "-n"), activeEl = $(tid + "-active"), emptyEl = $(tid + "-empty");
    var TXT = null, SYN = null, MULTI = [];
    rows.forEach(function (r) { r._x = nz(r.getAttribute("data-x") || r.textContent); });

    // Bilingual search over the catalogue index (same synonym groups as owd.search).
    function terms(text) {
      var q = nz(text), out = [];
      if (SYN) MULTI.forEach(function (v) {
        if (q.indexOf(" " + v + " ") >= 0) { out.push(SYN.find(function (g) { return g.indexOf(v) >= 0; })); q = q.replace(" " + v + " ", " "); }
      });
      q.split(" ").filter(Boolean).forEach(function (w) {
        out.push((SYN && SYN.find(function (g) { return g.indexOf(w) >= 0; })) || [w]);
      });
      return out;
    }
    function has(s, v) { return v.length <= 3 ? s.indexOf(" " + v + " ") >= 0 : s.indexOf(v) >= 0; }
    function textOf(r) { return (TXT && TXT[r.dataset.id]) || r._x; }
    function rowPasses(r, ts, skip) {
      if (ts.length) { var s = textOf(r); if (!ts.every(function (g) { return g.some(function (v) { return has(s, v); }); })) return false; }
      return ctrls.every(function (c) {
        if (c === skip || c === qEl || !c.value) return true;
        var v = r.getAttribute("data-" + c.dataset.attr) || "";
        return c.dataset.match === "word" ? (" " + v + " ").indexOf(" " + c.value + " ") >= 0 : v === c.value;
      });
    }
    function readURL() {
      var p = new URLSearchParams(location.search);
      ctrls.forEach(function (c) {
        var v = p.get(c.name); if (v == null) return;
        if (c.tagName === "SELECT" && ![].some.call(c.options, function (o) { return o.value === v; })) return;
        c.value = v;
      });
    }
    function writeURL() {
      var p = new URLSearchParams(location.search);
      ctrls.forEach(function (c) { p.delete(c.name); if (c.value.trim()) p.set(c.name, c.value.trim()); });
      var s = p.toString();
      history.replaceState(null, "", location.pathname + (s ? "?" + s : "") + location.hash);
    }
    function render() {
      var ts = qEl && qEl.value.trim() ? terms(qEl.value) : [];
      var n = 0;
      rows.forEach(function (r) { var ok = rowPasses(r, ts, null); r.hidden = !ok; if (ok) n++; });
      // option counts: each filter counted with the others applied, so the numbers stay true
      ctrls.forEach(function (c) {
        if (c.tagName !== "SELECT") return;
        var cnt = {};
        rows.forEach(function (r) {
          if (!rowPasses(r, ts, c)) return;
          var v = r.getAttribute("data-" + c.dataset.attr) || "";
          (c.dataset.match === "word" ? v.split(" ") : [v]).forEach(function (x) { if (x) cnt[x] = (cnt[x] || 0) + 1; });
        });
        [].forEach.call(c.options, function (o) { if (o.value) o.textContent = o.dataset.label + " (" + (cnt[o.value] || 0) + ")"; });
        c.classList.toggle("is-active", !!c.value);
      });
      if (qEl) qEl.classList.toggle("is-active", !!qEl.value.trim());
      var act = ctrls.filter(function (c) { return c.value.trim(); });
      activeEl.innerHTML = act.length ? "<span>Active filters:</span> " + act.map(function (c, i) {
        var val = c.tagName === "SELECT" ? c.options[c.selectedIndex].dataset.label : c.value.trim();
        return '<button type="button" class="chip" data-remove="' + i + '" aria-label="Remove filter ' + esc(c.dataset.name + ": " + val) + '">' +
          esc(c.dataset.name) + ": " + esc(val) + ' <span aria-hidden="true">×</span></button>';
      }).join(" ") + ' <button type="button" class="linkbtn" data-clear-for="' + tid + '">Clear filters</button>' : "";
      activeEl._act = act;
      countEl.textContent = (act.length ? n + " of " + rows.length : rows.length) + " " + unit;
      if (emptyEl) emptyEl.hidden = n > 0;
      // Measurement (only when the site runs its own collector): the search once the visitor pauses.
      clearTimeout(form._mt);
      form._mt = setTimeout(function () {
        if (!form.dataset.syn || !window.OWDMetrics || !window.OWDMetrics.search) return;
        window.OWDMetrics.search(qEl ? qEl.value : "", n, act.filter(function (c) { return c !== qEl; }).map(function (c) { return c.name + ":" + c.value; }));
      }, 1500);
    }
    var timer;
    form.addEventListener("input", function (e) {
      if (e.target === qEl) { clearTimeout(timer); timer = setTimeout(function () { writeURL(); render(); }, 150); }
      else { writeURL(); render(); }
    });
    form.addEventListener("submit", function (e) { e.preventDefault(); writeURL(); render(); });
    activeEl.addEventListener("click", function (e) {
      var b = e.target.closest("[data-remove]"); if (!b) return;
      var c = activeEl._act[+b.dataset.remove]; c.value = ""; writeURL(); render(); c.focus();
    });
    document.addEventListener("click", function (e) {
      var b = e.target.closest && e.target.closest('[data-clear-for="' + tid + '"]'); if (!b) return;
      ctrls.forEach(function (c) { c.value = ""; }); writeURL(); render(); (qEl || ctrls[0]).focus();
    });
    readURL(); render();
    if (form.dataset.syn) {
      fetch(form.dataset.syn).then(function (r) { return r.json(); }).then(function (d) {
        SYN = d.syn; TXT = {};
        MULTI = Array.from(new Set([].concat.apply([], d.syn).filter(function (v) { return v.indexOf(" ") >= 0; })))
          .sort(function (a, b) { return b.length - a.length; });
        d.items.forEach(function (it) { TXT[it.i] = nz(it.x); });
        render();
      }).catch(function () { /* the visible text of each row is searched instead */ });
    }
  }
  document.querySelectorAll("form[data-filter-for]").forEach(initFilter);


  // ------------------------------------------------------------ combined lookup (home page): mnemonic or source
  var lk = $("lk");
  if (lk) (function () {
    var form = $("lk-form"), out = $("lk-res"), base = form.dataset.base || B;
    var MN = null, IDX = null, SRC = null, SYN = [], loading = null, timer;
    function load() {
      if (loading) return loading;
      loading = Promise.all([
        fetch(base + "data/mnemonics.json").then(function (r) { return r.json(); }),
        fetch(base + "data/search.json").then(function (r) { return r.json(); })
      ]).then(function (a) {
        MN = a[0]; IDX = {}; MN.mnemonics.forEach(function (x) { IDX[x.m] = x; });
        SRC = a[1]; SYN = a[1].syn || [];
        SRC.items.forEach(function (it) { it._s = nz(it.x); it._n = nz(it.n); });
      });
      return loading;
    }
    var RANK = { verified_by_data: 0, conflict: 1, name_only: 2, unmapped: 3, listed: 4 };
    function rk(s) { return s in RANK ? RANK[s] : 9; }
    function best(x) { return x.r.slice().sort(function (a, b) { return rk(a.s) - rk(b.s) || (b.f || 0) - (a.f || 0); })[0]; }
    function mnCard(x) {
      var r = best(x), v = MN.variables[r.v] || ["", "", ""], st = (MN.status || {})[r.s] || r.s;
      var ev = r.f ? r.f.toLocaleString("en") + " file" + (r.f > 1 ? "s" : "") + ", " + (r.d || []).length + " dataset" + ((r.d || []).length === 1 ? "" : "s") : "not seen in the files read so far";
      return '<div class="lk-group"><h3>Mnemonic</h3>' + (r.v ?
        '<p class="lk-var"><code>' + esc(x.m) + "</code> → <code>" + esc(r.v) + "</code></p>" +
        "<p>" + esc(v[2]) + ". Unit <strong>" + esc(v[0]) + "</strong>, family " + esc(v[1]) + ". " + esc(st) + ": " + esc(ev) + "." +
        (x.r.length > 1 ? " " + (x.r.length - 1) + " other meaning" + (x.r.length > 2 ? "s" : "") + " depending on context." : "") + "</p>" :
        '<p class="lk-var"><code>' + esc(x.m) + "</code></p><p>Seen in the files (" + esc(ev) + ") but not mapped to a standard variable.</p>") +
        '<ul class="lk-list"><li><a href="' + base + "dictionary/?q=" + encodeURIComponent(x.m) + '"><strong>Evidence, ranges and context in the dictionary</strong></a></li></ul></div>';
    }
    function terms(text) {
      var q = nz(text), out2 = [];
      q.split(" ").filter(Boolean).forEach(function (w) { out2.push(SYN.find(function (g) { return g.indexOf(w) >= 0; }) || [w]); });
      return out2;
    }
    function has(s, v) { return v.length <= 3 ? s.indexOf(" " + v + " ") >= 0 : s.indexOf(v) >= 0; }
    function render() {
      var q = lk.value.trim();
      if (!q) { out.innerHTML = ""; return; }
      if (!MN) { out.innerHTML = '<p class="small muted">Loading the dictionary and the catalogue…</p>'; load().then(render, function () { out.innerHTML = '<p class="small">The lookup could not load its data here. Press Enter to search the catalogue.</p>'; }); return; }
      var h = "", up = q.toUpperCase().replace(/\s+/g, "");
      if (IDX[up]) h += mnCard(IDX[up]);
      else if (/^[A-Z0-9_]{2,12}$/.test(up)) {
        var pre = MN.mnemonics.filter(function (x) { return x.m.indexOf(up) === 0; }).slice(0, 6);
        if (pre.length) h += '<div class="lk-group"><h3>Mnemonics starting with ' + esc(up) + '</h3><ul class="lk-list">' + pre.map(function (x) {
          var r = best(x); return '<li><a href="' + base + "dictionary/?q=" + encodeURIComponent(x.m) + '"><strong>' + esc(x.m) + "</strong><span>" + esc(r.v || "not mapped") + "</span></a></li>";
        }).join("") + "</ul></div>";
      }
      var ts = terms(q);
      var res = SRC.items.filter(function (it) { return ts.every(function (g) { return g.some(function (v) { return has(it._s, v); }); }); });
      res.sort(function (a, b) { return ts.filter(function (g) { return g.some(function (v) { return has(b._n, v); }); }).length - ts.filter(function (g) { return g.some(function (v) { return has(a._n, v); }); }).length || a.n.localeCompare(b.n); });
      if (res.length) h += '<div class="lk-group"><h3>Sources: ' + res.length + " match" + (res.length > 1 ? "es" : "") + '</h3><ul class="lk-list">' + res.slice(0, 6).map(function (it) {
        return '<li><a href="' + base + "source/" + encodeURIComponent(it.i) + '/"><strong>' + esc(it.n) + "</strong><span>" + esc([it.c, (SRC.labels.s || {})[it.s]].filter(Boolean).join(", ")) + "</span></a></li>";
      }).join("") + '<li><a href="' + base + "search/?q=" + encodeURIComponent(q) + '"><strong>All ' + res.length + " in the catalogue</strong></a></li></ul></div>";
      // Measurement (only when the site runs its own collector): the lookup text and what it found, once the visitor pauses.
      var kind = IDX[up] ? "mnemonic" : h ? (res.length ? "source" : "prefix") : "none";
      clearTimeout(lk._mt);
      lk._mt = setTimeout(function () { if (window.OWDMetrics && window.OWDMetrics.lookup) window.OWDMetrics.lookup(q, kind); }, 1500);
      if (!h) h = '<div class="lk-group"><p>No mnemonic or source matches <strong>' + esc(q) + '</strong>. Try a broader word, or browse the <a href="' + base + 'search/">catalogue</a>.</p></div>';
      out.innerHTML = h;
    }
    lk.addEventListener("focus", function () { load().catch(function () {}); }, { once: true });
    lk.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(render, 120); });
    // keyboard: arrow down from the field into the results, up and down between them, Escape back to the field
    form.addEventListener("keydown", function (e) {
      var links = [].slice.call(out.querySelectorAll("a")), i = links.indexOf(document.activeElement);
      if (e.key === "ArrowDown" && links.length) { e.preventDefault(); links[Math.min(i + 1, links.length - 1)].focus(); }
      else if (e.key === "ArrowUp" && i >= 0) { e.preventDefault(); (i === 0 ? lk : links[i - 1]).focus(); }
      else if (e.key === "Escape") { if (document.activeElement === lk) { lk.value = ""; out.innerHTML = ""; } else lk.focus(); }
    });
  })();

  // ------------------------------------------------------------ side-by-side comparison of sources (up to four)
  // The selection is a per-viewer convenience kept on this device; the comparison page reads it from its address.
  var CMP_MAX = 4;
  function cmpGet() { try { return (localStorage.getItem("owd-compare") || "").split(",").filter(Boolean).slice(0, CMP_MAX); } catch (e) { return []; } }
  function cmpSet(a) { try { localStorage.setItem("owd-compare", a.slice(0, CMP_MAX).join(",")); } catch (e) {} cmpSync(); }
  var tray = null;
  function cmpSync() {
    var sel = cmpGet();
    document.querySelectorAll("input[data-compare]").forEach(function (c) {
      c.checked = sel.indexOf(c.dataset.compare) >= 0;
      c.disabled = !c.checked && sel.length >= CMP_MAX;
    });
    document.querySelectorAll("[data-compare-toggle]").forEach(function (b) {
      var on = sel.indexOf(b.dataset.compareToggle) >= 0;
      b.setAttribute("aria-pressed", on ? "true" : "false");
      b.textContent = on ? "Remove from comparison" : (sel.length >= CMP_MAX ? "Comparison full (4)" : "Add to comparison");
      b.disabled = !on && sel.length >= CMP_MAX;
    });
    if (!document.querySelector("input[data-compare], [data-compare-toggle]")) return;
    if (!tray) {
      tray = document.createElement("div"); tray.className = "cmp-tray"; tray.setAttribute("role", "region"); tray.setAttribute("aria-label", "Comparison");
      document.body.appendChild(tray);
      tray.addEventListener("click", function (e) { if (e.target.closest("[data-cmp-clear]")) cmpSet([]); });
    }
    tray.hidden = !sel.length;
    tray.innerHTML = '<div class="wrap cmp-in"><span><strong>' + sel.length + "</strong> of " + CMP_MAX + ' sources selected</span> <a class="btn btn-primary" href="' + B + "compare/?ids=" + sel.map(encodeURIComponent).join(",") + '">Compare</a> <button type="button" class="linkbtn" data-cmp-clear>Clear</button></div>';
  }
  document.addEventListener("change", function (e) {
    var c = e.target.closest && e.target.closest("input[data-compare]"); if (!c) return;
    var sel = cmpGet().filter(function (x) { return x !== c.dataset.compare; });
    if (c.checked) sel.push(c.dataset.compare);
    cmpSet(sel);
  });
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-compare-toggle]"); if (!b) return;
    var id = b.dataset.compareToggle, sel = cmpGet();
    cmpSet(sel.indexOf(id) >= 0 ? sel.filter(function (x) { return x !== id; }) : sel.concat([id]));
  });
  cmpSync();

  var cmpOut = $("cmp-out");
  if (cmpOut) (function () {
    var ids = (new URLSearchParams(location.search).get("ids") || cmpGet().join(",")).split(",").map(function (x) { return x.trim(); }).filter(Boolean).slice(0, CMP_MAX);
    if (!ids.length) return;
    cmpOut.innerHTML = '<p class="small">Loading the records…</p>';
    Promise.all([fetch(B + "data/sources-status.json").then(function (r) { return r.json(); })].concat(ids.map(function (id) {
      return fetch(B + "data/source/" + encodeURIComponent(id) + ".json").then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
    }))).then(function (a) {
      var st = {}; (a[0].listed || []).forEach(function (r) { st[r.id] = r; });
      var recs = a.slice(1), cols = [];
      ids.forEach(function (id, i) { if (recs[i] && st[id]) cols.push({ id: id, f: recs[i], s: st[id] }); });
      if (!cols.length) { cmpOut.innerHTML = '<p class="empty">None of these records exists. Choose sources in the <a href="' + B + 'search/">catalogue</a>.</p>'; return; }
      function ok(v) { return v && ["not stated", "not_stated", "none"].indexOf(String(v).toLowerCase()) < 0; }
      function list(v) { return Array.isArray(v) ? v.join(", ") : (v || ""); }
      var rows = [
        ["Publisher", function (c) { return ok(c.f.operator) ? esc(c.f.operator) : ""; }],
        ["Country", function (c) { return esc(c.s.country || "not stated") + (c.s.region ? '<span class="cell-sub">' + esc(c.s.region) + "</span>" : ""); }],
        ["Data types", function (c) { return esc(list(c.s.data_types)) || "not stated"; }],
        ["Formats", function (c) { return esc((c.f.formats || []).filter(ok).join(", ")); }],
        ["Access", function (c) { var v = (c.f.verification || {}).access_as_written; return esc(c.f.access || "") + (ok(v) ? '<span class="cell-sub">' + esc(v) + "</span>" : ""); }],
        ["Licence as written", function (c) { return esc(c.s.licence_as_written); }],
        ["What Open Well Data does", function (c) { return esc(c.s.owd_action); }],
        ["Verification", function (c) { return esc(c.s.verification_status); }],
        ["Last check", function (c) { return '<time datetime="' + esc(c.s.last_check) + '">' + esc(c.s.last_check) + "</time>" + (c.s.last_check_result ? '<span class="cell-sub">' + esc(c.s.last_check_result) + "</span>" : ""); }],
        ["Problems found", function (c) { return esc(list(c.s.problems)); }],
        ["Source address", function (c) { return c.s.url ? '<a class="ext" href="' + esc(c.s.url) + '" rel="noopener nofollow">' + esc(c.s.url.replace(/^https?:\/\/(www\.)?/, "")) + "</a>" : "link removed"; }]
      ];
      var head = '<tr><th scope="col"><span class="sr">Field</span></th>' + cols.map(function (c) {
        return '<th scope="col"><a class="rowname" href="' + B + "source/" + encodeURIComponent(c.id) + '/">' + esc(c.s.name) + '</a><button type="button" class="linkbtn cmp-rm" data-cmp-rm="' + esc(c.id) + '">Remove<span class="sr"> ' + esc(c.s.name) + "</span></button></th>";
      }).join("") + "</tr>";
      var body = rows.map(function (r) {
        var vals = cols.map(function (c) { return r[1](c) || '<span class="muted">not stated</span>'; });
        var differ = cols.length > 1 && vals.some(function (v) { return v !== vals[0]; });
        return '<tr' + (differ ? ' class="cmp-diff"' : "") + '><th scope="row">' + esc(r[0]) + (differ ? '<span class="cell-sub">differs</span>' : "") + "</th>" + vals.map(function (v) { return "<td>" + v + "</td>"; }).join("") + "</tr>";
      }).join("");
      cmpOut.innerHTML = '<div class="tablewrap"><table class="cmp-table"><caption>' + cols.length + " sources compared</caption><thead>" + head + "</thead><tbody>" + body + "</tbody></table></div>" +
        '<p class="small muted">Data: <a href="' + B + 'data/sources-status.csv">sources-status.csv</a> and the record files. <a href="' + B + "compare/?ids=" + cols.map(function (c) { return encodeURIComponent(c.id); }).join(",") + '">Link to this comparison</a>.</p>';
      if (!new URLSearchParams(location.search).get("ids")) history.replaceState(null, "", location.pathname + "?ids=" + cols.map(function (c) { return encodeURIComponent(c.id); }).join(","));
    }).catch(function () { cmpOut.innerHTML = '<p class="empty">The records could not be loaded here. Open them from the <a href="' + B + 'search/">catalogue</a>.</p>'; });
    cmpOut.addEventListener("click", function (e) {
      var b = e.target.closest("[data-cmp-rm]"); if (!b) return;
      var rest = (new URLSearchParams(location.search).get("ids") || "").split(",").filter(function (x) { return x && x !== b.dataset.cmpRm; });
      cmpSet(cmpGet().filter(function (x) { return x !== b.dataset.cmpRm; }));
      location.search = rest.length ? "?ids=" + rest.join(",") : "";
    });
  })();
  // ------------------------------------------------------------ details panel (side panel, not modal)
  var panel = null, opener = null;
  function closePanel() {
    if (!panel || panel.hidden) return;
    panel.hidden = true;
    if (opener) opener.focus();
  }
  function kv(k, v) { return v ? "<div><dt>" + esc(k) + "</dt><dd>" + v + "</dd></div>" : ""; }
  function stated(v) { return v && ["not stated", "not_stated", "not applicable", "none"].indexOf(String(v).toLowerCase()) < 0; }
  function openPanel(btn) {
    var id = btn.dataset.details, row = btn.closest("tr"), t = btn.closest("table");
    opener = btn;
    if (!panel) {
      panel = document.createElement("aside");
      panel.className = "panel"; panel.id = "panel"; panel.setAttribute("aria-labelledby", "panel-title"); panel.hidden = true;
      document.body.appendChild(panel);
      panel.addEventListener("click", function (e) { if (e.target.closest("[data-close]")) closePanel(); });
      document.addEventListener("keydown", function (e) { if (e.key === "Escape") closePanel(); });
    }
    var heads = [].map.call(t.tHead.rows[0].cells, function (c) { return c.textContent.trim(); });
    var cells = "";
    [].forEach.call(row.cells, function (c, i) { if (i > 0 && heads[i] && heads[i] !== "Details") cells += kv(heads[i], c.innerHTML); });
    var name = row.cells[0].querySelector("a") ? row.cells[0].querySelector("a").textContent : id;
    panel.innerHTML = '<div class="panel-head"><h2 id="panel-title" tabindex="-1">' + esc(name) + '</h2><button type="button" class="btn btn-small" data-close>Close</button></div>' +
      '<p class="muted small" id="panel-msg">Loading the record…</p><dl class="kv">' + cells + "</dl>" +
      '<p><a class="btn btn-primary" href="' + B + "source/" + encodeURIComponent(id) + '/">Open the full record</a> <a class="btn" href="' + B + "data/source/" + encodeURIComponent(id) + '.json">JSON</a></p>';
    panel.hidden = false;
    $("panel-title").focus();
    fetch(B + "data/source/" + encodeURIComponent(id) + ".json").then(function (r) { if (!r.ok) throw r; return r.json(); }).then(function (f) {
      var v = f.verification || {};
      var extra = kv("Publisher", stated(f.operator) ? esc(f.operator) : "") +
        (heads.indexOf("Licence as written") >= 0 ? "" : kv("Licence as written", stated(f.license) ? esc(f.license) : (stated(v.license_as_written) ? esc(v.license_as_written) : ""))) +
        kv("Access as written", stated(v.access_as_written) ? esc(v.access_as_written) : "") +
        kv("Formats", (f.formats || []).filter(stated).map(esc).join(", ")) +
        kv("Source address", f.url ? '<a class="ext" href="' + esc(f.url) + '" rel="noopener nofollow">' + esc(f.url) + "</a>" : "");
      var msg = $("panel-msg");
      msg.className = "";
      msg.innerHTML = stated(v.what_it_is) ? esc(v.what_it_is) : "No summary of the source page yet.";
      panel.querySelector("dl").insertAdjacentHTML("afterbegin", extra);
    }).catch(function () {
      var msg = $("panel-msg"); if (msg) msg.textContent = "The full record could not be loaded here. Open the record page instead.";
    });
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-details]"); if (!b) return;
    e.preventDefault(); openPanel(b);
  });
})();
