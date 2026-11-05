/* SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
   Copyright 2026 Daniel Delgado-Uriarte. Free for non-commercial use; companies need a licence (see NOTICE). */
// Open Well Data: anonymous measurement. Off unless the page declares <meta name="owd-metrics" content="…">, which the
// build adds only when the site is served by its own server (same origin as the collector).
// No cookies, nothing stored on the device, no ID of any kind: each event is a +1 on an hourly counter on the server.
// What is sent: page views (page, referring domain, screen size, language), searches and searches with no result,
// filters, which result is opened and its position, clicks to a source or its raw data, copied citations and
// downloads of the catalogue files. See /privacy/.
(function () {
  "use strict";
  var meta = document.querySelector('meta[name="owd-metrics"]');
  var END = meta && meta.content ? meta.content.replace(/\/$/, "") + "/api/events" : null;
  var queue = [];
  var internal = false;
  try {
    var p = new URLSearchParams(location.search).get("yo");
    if (p === "1") localStorage.setItem("owd-internal", "1");
    if (p === "0") localStorage.removeItem("owd-internal");
    internal = localStorage.getItem("owd-internal") === "1";
  } catch (e) {}

  function flush() {
    if (!END || !queue.length) return;
    var body = { anonymous: true, events: queue.splice(0, 20) };
    if (navigator.webdriver === true) body.automated = true;
    if (internal) body.internal = true;
    var data = JSON.stringify(body);
    try {
      // fetch with keepalive survives the page closing; sendBeacon is not used because some browsers send it
      // without the Origin header the collector requires.
      fetch(END, { method: "POST", body: data, headers: { "Content-Type": "application/json" }, keepalive: true, credentials: "omit" }).catch(function () {});
    } catch (e) {}
  }
  function track(event, props) {
    if (!END) return;
    queue.push({ event: event, props: props || {} });
    if (queue.length >= 20) flush();
  }
  window.OWDMetrics = { track: track };

  var ref = "direct";
  try { if (document.referrer) ref = new URL(document.referrer).hostname; } catch (e) {}
  track("page_view", {
    page: document.body.dataset.page || "page",
    path: location.pathname.slice(0, 100),
    referrer: ref,
    device: innerWidth < 600 ? "small" : innerWidth < 1000 ? "medium" : "large",
    language: (navigator.language || "").slice(0, 16)
  });

  // Clicks: sources, raw data, citations, catalogue files.
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a, button");
    if (!a) return;
    var rec = (document.body.dataset.record || "").slice(0, 80);
    if (a.matches("[data-copy]")) return track("citation_copy", { item: rec || location.pathname.slice(0, 80) });
    if (a.tagName !== "A" || !a.href) return;
    var url;
    try { url = new URL(a.href, location.href); } catch (err) { return; }
    if (url.origin !== location.origin) {
      var kind = a.dataset.kind || "outbound";
      return track(kind === "raw" ? "raw_click" : kind === "source" ? "outbound_source" : "outbound_click",
                   { host: url.hostname.slice(0, 100), item: rec });
    }
    if (/\/data\/.+\.(json|csv)$/.test(url.pathname)) track("data_download", { item: url.pathname.split("/").pop().slice(0, 80) });
    var pos = a.dataset.position;
    if (pos) track("result_click", { item: (a.dataset.id || "").slice(0, 80), position: pos });
  });

  // Search: the text once the visitor pauses, how many results (in bands) and filters. Called by app.js.
  var last = "";
  window.OWDMetrics.search = function (q, n, filters) {
    q = String(q || "").trim().toLowerCase().replace(/\s+/g, " ").slice(0, 60);
    var key = q + "|" + filters.join(",");
    if (key === last || (!q && !filters.length)) return;
    last = key;
    var band = n === 0 ? "0" : n <= 5 ? "1-5" : n <= 20 ? "6-20" : "21+";
    if (q) track(n === 0 ? "search_zero" : "search", { item: q, control: band });
    filters.forEach(function (f) { track("filter", { item: f.slice(0, 60) }); });
  };

  document.addEventListener("visibilitychange", function () { if (document.hidden) flush(); });
  window.addEventListener("pagehide", flush);
  setInterval(flush, 5000);
})();
