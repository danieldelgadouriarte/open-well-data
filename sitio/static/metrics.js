/* SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
   Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE). */
// Open Well Data: first-party measurement by country tier. Off unless the page declares
// <meta name="owd-metrics" content="…">, which the build adds only when the site is served by its own server.
// Page views and downloads are counted by the server from the requests themselves, in every country, without this
// script. This script asks the server which tier applies to this visit (the tier name only; the country is not sent
// back) and then does only what that tier allows without consent, or what the visitor accepted:
//   - consent tier (t1): nothing at all, and nothing stored on the device, until the visitor chooses; the banner
//     offers Reject and Accept with the same weight.
//   - notice tiers: anonymous counts of searches, clicks, downloads and engagement (no ID), one statistical value on
//     the device (new or returning visitor) and, where the tier says so, this tab's journey; all with a notice and a
//     one-click opt-out. Global Privacy Control is honoured by the server.
//   - Detailed measurement (opt-in everywhere): this tab's journey with a random per-tab ID, timings and scroll.
//   - Session replay (a separate explicit opt-in everywhere): masked rrweb recording of this page, five minutes at
//     most, never on the converter. Withdrawing deletes the journey and the replay of this tab on the server.
// Never: cookies for measurement, third parties, fingerprinting, typed text other than the search box, file contents.
(function () {
  "use strict";
  var meta = document.querySelector('meta[name="owd-metrics"]');
  if (!meta || !meta.content || !/^https?:/.test(location.protocol)) { window.OWDMetrics = { track: function () {}, search: function () {}, lookup: function () {}, convert: function () {} }; return; }
  var BASE = meta.content.replace(/\/$/, "");
  var ROOT = document.documentElement.dataset.base || "./";
  function get(kind, k) { try { return window[kind].getItem(k); } catch (e) { return null; } }
  function put(kind, k, v) { try { window[kind].setItem(k, v); } catch (e) {} }
  function drop(kind, k) { try { window[kind].removeItem(k); } catch (e) {} }
  function uuid() { return crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + "-" + String(Math.random()).slice(2, 12); }

  // Our own devices: ?yo=1 marks this browser (local storage and a first-party cookie the server reads to skip its
  // own counts); ?yo=0 removes the mark. Only ever used on the maintainer's devices.
  var yo = new URLSearchParams(location.search).get("yo");
  if (yo === "1") { put("localStorage", "owd-internal", "1"); document.cookie = "owd_internal=1; path=/; max-age=31536000; SameSite=Strict" + (location.protocol === "https:" ? "; Secure" : ""); }
  if (yo === "0") { drop("localStorage", "owd-internal"); document.cookie = "owd_internal=; path=/; max-age=0; SameSite=Strict"; }
  var internal = get("localStorage", "owd-internal") === "1";

  // Choices, stored only once the visitor makes one: 'detailed' (consent level 1), 'reject' (no browser measurement),
  // 'optout' (no notice-based measurement), and owd-replay = 'yes' (consent level 2).
  var choice = get("localStorage", "owd-measurement");
  // Global Privacy Control (9 Nov 2026): counts as an opt-out of everything that runs on a notice; explicit consent still applies.
  var gpc = navigator.globalPrivacyControl === true;
  var replayChoice = get("localStorage", "owd-replay") === "yes";
  var st = null, queue = [], session = null, mode = "off", basis = null, viewed = false, sentEnd = false;
  var shownAt = Date.now(), visibleMs = 0, maxScroll = 0, activeAt = Date.now();
  var stopRecorder = null, replayQueue = [], recording = null, replaySeq = 0, replayTimer = null, replayLoading = false;

  function decideMode() {
    var consent = choice === "detailed";
    var refused = choice === "reject" || choice === "optout" || (gpc && !consent);
    basis = consent ? "consent" : "notice";
    if (!st) mode = "off";
    else if (consent) mode = "journey";
    else if (refused) mode = "off";
    else if (st.journeys === "notice") mode = "journey";
    else if (st.events === "notice") mode = "anonymous";
    else mode = "off";
  }
  function storageAllowed() { return choice === "detailed" || (!gpc && st && st.storage === "notice" && choice !== "reject" && choice !== "optout"); }
  function replayOn() { return st && st.replay && choice === "detailed" && replayChoice; }

  function track(event, props) {
    if (mode === "off") return;
    props = props || {};
    if (mode === "journey") queue.push({ id: uuid(), event: event, props: props });
    else if (event !== "page_view" && event !== "active_time") queue.push({ event: event, props: props });
    if (queue.length > 240) queue.shift();
    if (queue.length >= 20) flush();
  }
  function identify() {
    if (!session) { session = get("sessionStorage", "owd-session") || uuid(); put("sessionStorage", "owd-session", session); }
    return session;
  }
  function flush() {
    if (mode === "off" || !queue.length) return;
    var events = queue.splice(0, 20);
    var body = mode === "journey" ? { session: identify(), basis: basis, events: events } : { anonymous: true, basis: basis, events: events };
    if (navigator.webdriver === true) body.automated = true;
    if (internal) body.internal = true;
    try {
      fetch(BASE + "/api/events", { method: "POST", body: JSON.stringify(body), headers: { "Content-Type": "application/json" }, keepalive: true, credentials: "omit" })
        .then(function (r) { if (r.status === 409) { mode = "off"; queue = []; } }).catch(function () {});
    } catch (e) {}
  }

  // ------------------------------------------------------------ what is counted
  function band(w) { return w < 360 ? "<360" : w < 600 ? "360-599" : w < 1000 ? "600-999" : w < 1440 ? "1000-1439" : "1440+"; }
  function start() {
    if (viewed || mode === "off") return;
    viewed = true;
    var ref = "direct";
    try { if (document.referrer) ref = new URL(document.referrer).hostname; } catch (e) {}
    // The journey needs its page views in order; anonymous page views are the server's job.
    track("page_view", { path: location.pathname.slice(0, 100), referrer: ref });
    track("viewport", { item: band(innerWidth), control: innerWidth < 600 ? "small" : innerWidth < 1000 ? "medium" : "large" });
    if (storageAllowed()) {
      // The one statistical value on the device: the month of the last visit, to count new and returning visitors.
      var month = new Date().toISOString().slice(0, 7), last = get("localStorage", "owd-last");
      track("visit_kind", { item: last ? "returning" : "new" });
      put("localStorage", "owd-last", month);
    }
    startReplay();
    flush();
  }
  function end() {
    if (sentEnd || !viewed) return;
    sentEnd = true;
    if (!document.hidden) visibleMs += Date.now() - shownAt;
    var s = visibleMs / 1000;
    var tv = s < 10 ? "0-10s" : s < 30 ? "10-30s" : s < 120 ? "30s-2m" : s < 600 ? "2-10m" : "10m+";
    var sd = maxScroll >= 0.95 ? "100" : maxScroll >= 0.75 ? "75" : maxScroll >= 0.5 ? "50" : maxScroll >= 0.25 ? "25" : "0";
    track("scroll_depth", { path: location.pathname.slice(0, 100), item: sd });
    track("time_visible", { path: location.pathname.slice(0, 100), item: tv });
    flush();
    flushReplay();
  }
  addEventListener("scroll", function () {
    var h = document.documentElement.scrollHeight - innerHeight;
    maxScroll = Math.max(maxScroll, h > 0 ? scrollY / h : 1);
    activeAt = Date.now();
  }, { passive: true });
  ["pointerdown", "keydown"].forEach(function (t) { addEventListener(t, function () { activeAt = Date.now(); }, { passive: true }); });
  setInterval(function () {
    if (mode === "journey" && !document.hidden && document.hasFocus() && Date.now() - activeAt < 60000) track("active_time", { seconds: 10 });
  }, 10000);
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) { visibleMs += Date.now() - shownAt; end(); flush(); flushReplay(); }
    else shownAt = Date.now();
  });
  addEventListener("pagehide", function () { end(); flush(); flushReplay(); });
  setInterval(function () { flush(); flushReplay(); }, 5000);

  function copyKind(b) {
    var pre = b.parentNode && b.parentNode.querySelector("pre"), id = pre ? pre.id : "", label = (b.textContent || "").toLowerCase();
    if (id === "cv-bib") return "bibtex";
    if (id === "cv-cmd") return "command";
    if (id === "cv-link") return "link";
    if (label.indexOf("request") >= 0) return "request";
    if (label.indexOf("citation") >= 0 || id === "cv-cite" || id === "cv-srccite" || b.closest(".cite, .rail-block")) return "citation";
    if (pre && /^\s*(owd|pip|python)\b/.test(pre.textContent || "")) return "command";
    return "other";
  }
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a, button");
    if (!a) return;
    var rec = (document.body.dataset.record || "").slice(0, 80);
    if (a.matches("[data-copy]")) return track("citation_copy", { item: rec || location.pathname.slice(0, 80), control: copyKind(a) });
    if (a.tagName !== "A" || !a.href) return;
    var url;
    try { url = new URL(a.href, location.href); } catch (err) { return; }
    if (url.protocol === "blob:" || url.protocol === "data:" || url.protocol === "mailto:") return;
    if (url.origin !== location.origin) {
      var kind = a.dataset.kind || "outbound";
      return track(kind === "raw" ? "raw_click" : kind === "source" || location.pathname.indexOf("/datasets/") >= 0 ? "outbound_source" : "outbound_click",
                   { host: url.hostname.slice(0, 100), item: rec });
    }
    if (/\.(csv|tsv|json|jsonl|jsonld|txt|zip|parquet|ipynb|xml)$/i.test(url.pathname))
      return track(a.closest("figure") ? "figure_download" : "data_download", { item: url.pathname.slice(0, 100) });
    var m = url.pathname.match(/\/source\/([^/]+)\/?$/);
    if (m) {
      // A result opened from the catalogue table or the home lookup, with its position among the visible results.
      var list = a.closest("tbody, .lk-list");
      if (list) {
        var items = [].filter.call(list.querySelectorAll(list.tagName === "TBODY" ? "tr" : "li"), function (x) { return !x.hidden; });
        var pos = items.indexOf(a.closest("tr, li")) + 1;
        track("result_click", { item: decodeURIComponent(m[1]).slice(0, 80), position: pos <= 0 ? "?" : pos <= 3 ? String(pos) : pos <= 10 ? "4-10" : "11+" });
      }
    }
  });

  // Called by app.js and convert-page.js.
  var lastSearch = "", lastLookup = "";
  function clip(q) { return String(q || "").trim().toLowerCase().replace(/\s+/g, " ").slice(0, 60); }
  function resultBand(n) { return n === 0 ? "0" : n <= 5 ? "1-5" : n <= 20 ? "6-20" : "21+"; }
  window.OWDMetrics = {
    track: track,
    search: function (q, n, filters) {
      q = clip(q);
      var key = q + "|" + filters.join(",");
      if (key === lastSearch || (!q && !filters.length)) return;
      lastSearch = key;
      if (q) track(n === 0 ? "search_zero" : "search", { item: q, control: resultBand(n) });
      filters.forEach(function (f) { track("filter", { item: String(f).slice(0, 60) }); });
    },
    lookup: function (q, kind) {
      q = clip(q);
      if (!q || q === lastLookup) return;
      lastLookup = q;
      track("lookup", { item: q, control: kind });
    },
    // Formats only (las, csv, zip, notebook…): never the file, its name or its content.
    convert: function (from, to) {
      track("convert", { item: String(from || "unknown").toLowerCase().slice(0, 12), control: String(to || "unknown").toLowerCase().slice(0, 12) });
    },
    state: function () { return { tier: st && st.tier, mode: mode, choice: choice, replay: !!stopRecorder }; },
    decide: decide
  };

  // ------------------------------------------------------------ replay (consent level 2 only)
  function startReplay() {
    if (!replayOn() || stopRecorder || replayLoading || /\/convert\/?$/.test(location.pathname)) return;
    replayLoading = true;
    var go = function () {
      replayLoading = false;
      if (!replayOn() || !window.rrweb) return;
      recording = uuid(); replaySeq = 0;
      stopRecorder = window.rrweb.record({
        emit: function (ev) {
          if (!replayOn()) return;
          if (ev.type === 4) ev.data.href = location.origin + location.pathname;
          replayQueue.push(ev);
          if (replayQueue.length >= 30) flushReplay();
        },
        maskAllInputs: true,
        maskTextSelector: "input, textarea, [contenteditable], [data-mask]",
        blockSelector: "[data-private], #cv-app, form[data-contact], .owd-consent",
        inlineStylesheet: true, recordCanvas: false, collectFonts: false, recordCrossOriginIframes: false,
        sampling: { mousemove: 150, scroll: 250, input: "last" }, slimDOMOptions: "all"
      });
      replayTimer = setTimeout(function () { if (stopRecorder) stopRecorder(); stopRecorder = null; flushReplay(); }, 300000);
    };
    if (window.rrweb) return go();
    var s = document.createElement("script");
    s.src = ROOT + "static/vendor/rrweb-2.1.1.js";
    s.onload = go;
    s.onerror = function () { replayLoading = false; };
    document.head.appendChild(s);
  }
  function stopReplay() {
    if (stopRecorder) stopRecorder();
    stopRecorder = null; clearTimeout(replayTimer); replayQueue = []; recording = null;
  }
  function flushReplay() {
    if (!replayOn() || !recording || !replayQueue.length) return;
    var payload = JSON.stringify({ session: identify(), recording: recording, seq: replaySeq++, basis: "consent", replay_consent: true,
                                   events: replayQueue.splice(0, 100) });
    if (payload.length > 500000) return stopReplay();
    fetch(BASE + "/api/replay", { method: "POST", body: payload, headers: { "Content-Type": "application/json" }, keepalive: payload.length < 60000, credentials: "omit" })
      .then(function (r) { if (!r.ok) stopReplay(); }).catch(stopReplay);
  }

  // ------------------------------------------------------------ choices
  function forgetHere() {
    // Withdrawal: the server deletes the journey and the replay recorded under this tab's ID, then the ID goes.
    var id = session || get("sessionStorage", "owd-session");
    if (id) fetch(BASE + "/api/forget", { method: "POST", body: JSON.stringify({ session: id }), headers: { "Content-Type": "application/json" }, keepalive: true, credentials: "omit" }).catch(function () {});
    drop("sessionStorage", "owd-session"); session = null;
  }
  function decide(level) {
    // level: 'detailed', 'replay' (detailed + replay), 'reject', 'optout', 'notice' (accept the notice as it is).
    var before = mode;
    if (level === "replay") { choice = "detailed"; replayChoice = true; }
    else if (level === "detailed") { if (replayChoice) forgetReplayOnly(); choice = "detailed"; replayChoice = false; }
    else if (level === "notice") { choice = null; replayChoice = false; put("localStorage", "owd-notice", "seen"); }
    else { if (choice === "detailed" || mode === "journey") forgetHere(); choice = level; replayChoice = false; drop("localStorage", "owd-last"); }
    if (choice) put("localStorage", "owd-measurement", choice); else drop("localStorage", "owd-measurement");
    if (replayChoice) put("localStorage", "owd-replay", "yes"); else { drop("localStorage", "owd-replay"); stopReplay(); }
    if (level !== "notice") put("localStorage", "owd-notice", "seen");
    queue = [];
    decideMode();
    if (mode !== "off" && before === "off") { viewed = false; start(); } else startReplay();
    hideBanner(); describe();
  }
  function forgetReplayOnly() {
    // Replay withdrawn but detailed measurement kept: delete this tab's replay with its journey (one ID for both).
    stopReplay(); forgetHere();
  }

  // ------------------------------------------------------------ banner and privacy page controls
  var banner = null;
  function hideBanner() { if (banner) { banner.remove(); banner = null; } }
  function button(text, level, cls) {
    var b = document.createElement("button");
    b.type = "button"; b.className = "btn" + (cls ? " " + cls : ""); b.textContent = text;
    b.addEventListener("click", function () { decide(level); });
    return b;
  }
  function showBanner() {
    if (!st || choice !== null || get("localStorage", "owd-notice") === "seen" || /\/privacy\/?$/.test(location.pathname)) return;
    banner = document.createElement("aside");
    banner.className = "owd-consent"; banner.setAttribute("role", "region"); banner.setAttribute("aria-label", "Measurement");
    var p = document.createElement("p"), link = '<a href="' + ROOT + 'privacy/#measurement">Privacy and measurement</a>';
    var row = document.createElement("div"); row.className = "owd-consent-row";
    if (st.events === "consent") {
      p.innerHTML = "Our server counts page views and downloads without cookies or IDs. May we also measure, for this visit, " +
        "which searches, results and downloads you use, to improve the catalogue? Nothing is stored on your device unless you accept. " + link + ".";
      row.append(button("Reject", "reject"), button("Accept", "detailed"));
    } else if (gpc) {
      p.innerHTML = "Your browser sends Global Privacy Control, so nothing is measured in your browser and nothing is stored on your device. " +
        "Our server still counts page views and downloads without cookies or IDs. You can allow detailed measurement for this visit. " + link + ".";
      row.append(button("OK", "optout"), button("Allow detailed measurement", "detailed"));
    } else {
      p.innerHTML = "We count anonymously which searches, results and downloads are used" +
        (st.journeys === "notice" ? ", and the path of pages in this tab" : "") +
        ", and keep one statistical value on your device (new or returning visitor). No third parties, no advertising. " +
        "You can opt out, or allow more detail. " + link + ".";
      row.append(button("Opt out", "optout"), button("OK", "notice"), button("Allow detailed measurement", "detailed"));
    }
    banner.append(p, row);
    document.body.appendChild(banner);
  }
  function describe() {
    var el = document.getElementById("m-status");
    if (!el) return;
    var t = { off: "Nothing is measured in your browser on this visit (the server still counts page views and downloads).",
              anonymous: "Anonymous counts of searches, clicks and downloads, with no ID.",
              journey: "This tab's journey is recorded with a random per-tab ID." }[mode];
    if (replayOn()) t += " Session replay is on for this tab (masked, five minutes at most).";
    if (gpc && choice !== "detailed") t += " Your browser sends Global Privacy Control: it counts as an opt-out.";
    el.textContent = st ? "Your measurement tier: " + st.tier.toUpperCase() + ". " + t : "The measurement service did not answer: nothing is measured in your browser.";
    var tierEl = document.getElementById("m-tier");
    if (tierEl && st) tierEl.textContent = st.tier.toUpperCase();
    var r = document.getElementById("m-replay");
    if (r) r.checked = replayChoice && choice === "detailed";
  }
  function bindPrivacyPage() {
    var map = { "m-accept": "detailed", "m-reject": "reject", "m-optout": "optout" };
    Object.keys(map).forEach(function (id) {
      var b = document.getElementById(id);
      if (b) b.addEventListener("click", function () { decide(map[id]); });
    });
    var r = document.getElementById("m-replay");
    if (r) r.addEventListener("change", function () { decide(r.checked ? "replay" : (choice === "detailed" ? "detailed" : choice || "reject")); });
  }

  fetch(BASE + "/api/status", { credentials: "omit" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (s) {
    st = s && s.enabled && s.tier ? s : null;
    decideMode();
    bindPrivacyPage();
    describe();
    start();
    showBanner();
  }).catch(function () { bindPrivacyPage(); describe(); });
  addEventListener("storage", function (e) {
    if (e.key === "owd-measurement" || e.key === "owd-replay") {
      choice = get("localStorage", "owd-measurement"); replayChoice = get("localStorage", "owd-replay") === "yes";
      if (!replayOn()) stopReplay();
      decideMode(); describe();
    }
  });
})();
