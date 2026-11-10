#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Benchmark OWD-DT-1: predict compressional sonic (dt, us/ft) from other logs, on the FORCE 2020 wells
standardized by Open Well Data. Fixed splits by well (samples of one well are never mixed across parts), metric on
the test wells and baselines reproducible with numpy only.

Usage: python benchmark_dt.py PARQUET_DIR OUTPUT
Output: splits.json (wells of each part), results.json and LEADERBOARD.md.
"""
import hashlib, json, sys
from pathlib import Path
import numpy as np, pandas as pd

INPUTS = ["gr", "rhob", "res_deep"]  # + depth (index)
TARGET = "dt"


def part(well):
    # Deterministic split by well: sha1 of the name, 70 % train, 15 % validation, 15 % test.
    h = int(hashlib.sha1(well.encode()).hexdigest(), 16) % 100
    return "train" if h < 70 else "val" if h < 85 else "test"


def load(folder):
    tables = []
    for f in sorted(Path(folder).glob("*.parquet")):
        d = pd.read_parquet(f)
        cols = [c for c in INPUTS + [TARGET] if c in d.columns]
        if len(cols) < len(INPUTS) + 1:
            continue
        d = d[cols].copy()
        d["depth"] = d.index.astype(float)
        d["well"] = f.stem
        tables.append(d.dropna())
    t = pd.concat(tables)
    # Wide physical range to remove coded nulls (-999) and impossible values; nothing else is trimmed.
    t = t[(t.dt > 30) & (t.dt < 250) & (t.rhob > 1.0) & (t.rhob < 3.5) & (t.gr >= 0) & (t.gr < 500) & (t.res_deep > 0)]
    t["part"] = t.well.map(part)
    return t


def X(t, degree=1):
    cols = [t.gr.values, t.rhob.values, np.log10(t.res_deep.values), t.depth.values / 1000]
    base = np.column_stack(cols)
    if degree == 2:
        base = np.column_stack([base, base ** 2])
    return np.column_stack([np.ones(len(t)), base])


def metrics(y, p):
    e = p - y
    return {"rmse": float(np.sqrt(np.mean(e ** 2))), "mae": float(np.mean(np.abs(e))), "n": int(len(y))}


def main(folder, output):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    t = load(folder)
    tr, te = t[t.part == "train"], t[t.part == "test"]
    splits = {k: sorted(t[t.part == k].well.unique().tolist()) for k in ("train", "val", "test")}
    (output / "splits.json").write_text(json.dumps({"rule": "sha1(well) % 100: <70 train, <85 val, otherwise test",
                                                    "inputs": INPUTS + ["depth"], "target": TARGET, **splits}, indent=1))
    res = {"Training mean": metrics(te.dt.values, np.full(len(te), tr.dt.mean()))}
    for name, g in (("Linear regression", 1), ("Quadratic regression", 2)):
        beta, *_ = np.linalg.lstsq(X(tr, g), tr.dt.values, rcond=None)
        res[name] = metrics(te.dt.values, X(te, g) @ beta)
    kind = {"Training mean": "naive", "Linear regression": "data", "Quadratic regression": "data"}
    for k in res:
        res[k]["type"] = kind[k]
    (output / "results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    rows = "\n".join(f"| {k} | {v['type']} | {v['rmse']:.2f} | {v['mae']:.2f} |" for k, v in res.items())
    md = f"""# OWD-DT-1: compressional sonic (DT) from other logs

Data: FORCE 2020 wells, standardized by Open Well Data (standardized copy CC BY-NC 4.0; original data CC BY 4.0, doi:10.5281/zenodo.4351156).
Inputs: gamma ray (gAPI), bulk density (g/cm3), log10 deep resistivity (ohm.m), depth. Target: DT (us/ft).
Split by well, fixed: sha1(well name) % 100 → train < 70, validation < 85, test otherwise ({len(splits['train'])} / {len(splits['val'])} / {len(splits['test'])} wells).
Rows with all inputs and target present; physical range filter only. Test rows: {len(te):,}.

| Model | Type | RMSE (us/ft) | MAE (us/ft) |
|---|---|---|---|
{rows}

Baselines use numpy only and are fully reproducible. Submit results on the test wells with the same split.
"""
    (output / "LEADERBOARD.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main(*sys.argv[1:3])
