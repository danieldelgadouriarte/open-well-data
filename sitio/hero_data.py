#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Free for non-commercial use; companies need a licence (see NOTICE).
"""Export the real trace on the home page: Utah FORGE 16B, BHA 11 (GDR 1561, CC BY 4.0), loaded and standardized with owd.
A 3 h window with the bit on bottom, resampled to 15 s. Output: sitio/static/trace.json (versioned: it is small).
Usage: python sitio/hero_data.py CSV_PATH"""
import json, os, sys
import numpy as np, pandas as pd
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, "owd"))
import owd

src = sys.argv[1]
df = owd.load("utah-forge-16b", src)
cols = ["hookload", "wob", "surface_rpm", "spp", "bit_depth", "hole_depth"]
d = df[[c for c in cols if c in df.columns]].apply(pd.to_numeric, errors="coerce")
# On bottom: bit less than 0.5 m from the bottom of the hole and rotating.
bottom = ((d.hole_depth - d.bit_depth).abs() < 0.5) & (d.surface_rpm > 20)
r = bottom.rolling("3h").mean()
end = r.idxmax()
v = d.loc[end - pd.Timedelta("3h"):end].resample("15s").mean().interpolate(limit=4).dropna()
out = {
    "source": "Utah FORGE 16B(78)-32, BHA 11, GDR 1561 (doi:10.15121/2205632), CC BY 4.0",
    "start_utc": str(v.index[0]), "end_utc": str(v.index[-1]), "step_s": 15,
    "units": {c: df.attrs["unit"].get(c) for c in v.columns},
    "t_min": [round((t - v.index[0]).total_seconds() / 60, 2) for t in v.index],
    **{c: [round(float(x), 2) for x in v[c]] for c in v.columns},
}
dst = os.path.join(R, "sitio", "static", "trace.json")
json.dump(out, open(dst, "w"), ensure_ascii=False)
print(dst, len(v), "points", out["start_utc"], "->", out["end_utc"], {c: (min(out[c]), max(out[c])) for c in v.columns})
