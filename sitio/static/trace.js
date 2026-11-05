/* SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
   Copyright 2026 Daniel Delgado-Uriarte. Free for non-commercial use; companies need a licence (see NOTICE). */
// Home page log: real Utah FORGE 16B data drawn as a log print (time down, one track per channel, scale in each header).
(function () {
  "use strict";
  var cv = document.getElementById("trace");
  if (!cv) return;
  var B = document.documentElement.dataset.base || "./";
  var D, hover = null;
  var TR = [
    { k: "hookload", c: "--gr", lo: 0, hi: 1000 },
    { k: "wob", c: "--res", lo: 0, hi: 250 },
    { k: "surface_rpm", c: "--son", lo: 0, hi: 120 },
    { k: "spp", c: "--spp", lo: 0, hi: 20000 }
  ];

  function css(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }

  function draw() {
    if (!D) return;
    var dpr = window.devicePixelRatio || 1, W = cv.clientWidth, H = Math.round(W * 0.75);
    cv.width = W * dpr; cv.height = H * dpr;
    var g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0);
    var fg = css("--fg"), mu = css("--muted"), grid = css("--grid"), line = css("--line"), surf = css("--surface");
    g.fillStyle = surf; g.fillRect(0, 0, W, H);
    var depthW = Math.max(54, W * 0.13), head = 34, top = head + 4, bot = H - 8;
    var tw = (W - depthW) / TR.length, n = D.t_min.length, tmax = D.t_min[n - 1];
    var y = function (t) { return top + (bot - top) * t / tmax; };
    g.font = "500 10px " + css("--f-mono");

    // Depth/time column: minutes on the left, bit depth beside it.
    g.fillStyle = mu; g.textAlign = "left";
    g.fillText("min", 6, 14); g.fillText("bit m", 6, 27);
    for (var m = 0; m <= tmax; m += 15) {
      var yy = y(m), i = Math.min(n - 1, Math.round(m / tmax * (n - 1)));
      g.strokeStyle = m % 60 === 0 ? line : grid; g.lineWidth = 1;
      g.beginPath(); g.moveTo(depthW - 6, yy); g.lineTo(W, yy); g.stroke();
      if (m % 30 === 0) {
        g.fillStyle = fg; g.fillText(String(m), 6, yy + 3);
        g.fillStyle = mu; g.fillText(D.bit_depth[i].toFixed(0), 26, yy + 3);
      }
    }
    TR.forEach(function (tr, j) {
      var x0 = depthW + j * tw, col = css(tr.c), v = D[tr.k], u = D.units[tr.k];
      g.strokeStyle = line; g.beginPath(); g.moveTo(x0 + .5, 0); g.lineTo(x0 + .5, H); g.stroke();
      for (var q = 1; q < 4; q++) { g.strokeStyle = grid; g.beginPath(); g.moveTo(x0 + tw * q / 4, top); g.lineTo(x0 + tw * q / 4, bot); g.stroke(); }
      // Track header: name and scale, as on a log print.
      g.fillStyle = col; g.fillRect(x0 + 6, 9, tw - 12, 2);
      // Name on the first line (shortened to fit), scale and unit on the second, as on a log heading.
      var name = tr.k; while (name.length > 3 && g.measureText(name).width > tw - 8) name = name.slice(0, -1);
      if (name !== tr.k) name = name.slice(0, -1) + "…";
      g.fillStyle = fg; g.textAlign = "center"; g.fillText(name, x0 + tw / 2, 21);
      g.fillStyle = mu; g.textAlign = "left"; g.fillText(String(tr.lo), x0 + 4, 32);
      g.textAlign = "center"; g.fillText(u, x0 + tw / 2, 32);
      g.textAlign = "right"; g.fillText(String(tr.hi), x0 + tw - 4, 32);
      g.strokeStyle = col; g.lineWidth = 1.4; g.beginPath();
      for (var i2 = 0; i2 < n; i2++) {
        var xv = x0 + 3 + (tw - 6) * Math.max(0, Math.min(1, (v[i2] - tr.lo) / (tr.hi - tr.lo)));
        if (i2) g.lineTo(xv, y(D.t_min[i2])); else g.moveTo(xv, y(D.t_min[i2]));
      }
      g.stroke();
    });
    g.strokeStyle = line; g.lineWidth = 1; g.beginPath(); g.moveTo(0, head + .5); g.lineTo(W, head + .5); g.stroke();

    if (hover != null) {
      var k = hover, yy2 = y(D.t_min[k]);
      g.strokeStyle = fg; g.setLineDash([3, 3]); g.beginPath(); g.moveTo(0, yy2); g.lineTo(W, yy2); g.stroke(); g.setLineDash([]);
      var txt = D.t_min[k].toFixed(0) + " min · bit " + D.bit_depth[k].toFixed(1) + " m · " +
        TR.map(function (tr) { return tr.k + " " + Math.round(D[tr.k][k]); }).join(" · ");
      g.font = "500 11px " + css("--f-mono");
      var w = Math.min(W - 8, g.measureText(txt).width + 12), bx = 4, by = yy2 > H - 30 ? yy2 - 24 : yy2 + 6;
      g.fillStyle = surf; g.strokeStyle = line; g.fillRect(bx, by, w, 18); g.strokeRect(bx + .5, by + .5, w, 18);
      g.fillStyle = fg; g.textAlign = "left"; g.fillText(txt, bx + 6, by + 13, w - 12);
    }
  }

  function pick(e) {
    if (!D) return;
    var r = cv.getBoundingClientRect(), H = r.height, top = 38, bot = H - 8;
    var f = (e.clientY - r.top - top) / (bot - top);
    hover = f < 0 || f > 1 ? null : Math.round(f * (D.t_min.length - 1));
    draw();
  }
  cv.addEventListener("pointermove", pick);
  cv.addEventListener("pointerleave", function () { hover = null; draw(); });
  window.addEventListener("resize", draw);
  window.addEventListener("owd-theme", draw);
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", draw);
  if (document.fonts) document.fonts.ready.then(draw);

  fetch(B + "static/trace.json").then(function (r) { return r.json(); }).then(function (d) { D = d; draw(); });
})();
