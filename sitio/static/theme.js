/* SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
   Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE). */
// Runs before the page paints: marks that JavaScript is available (for the enhanced tables) and applies the theme chosen
// on this device. Without a stored choice the page is light, whatever the system preference: dark is only by choice.
// No inline script.
(function () {
  var r = document.documentElement;
  r.className = r.className.replace(/\bno-js\b/, "js");
  try { var t = localStorage.getItem("owd-theme"); if (t === "dark" || t === "light") r.dataset.theme = t; } catch (e) {}
})();
