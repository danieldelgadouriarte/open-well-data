/* SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
   Copyright 2026 Daniel Delgado-Uriarte. Free for non-commercial use; companies need a licence (see NOTICE). */
// Theme chosen on this device, applied before the page paints. Separate file so the page needs no inline script.
try { var t = localStorage.getItem('owd-theme'); if (t) document.documentElement.dataset.theme = t; } catch (e) {}
