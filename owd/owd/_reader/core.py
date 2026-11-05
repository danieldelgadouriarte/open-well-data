# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Free for non-commercial use; companies need a licence (see NOTICE).
"""Step shared by every format: blacklist, text -> number, declared nulls, sentinels and unit conversion.

Everything removed or changed is recorded in `Reading.log` (one row per channel and action, with the number of values).
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import roles as R
from . import units as U

# Sentinels the file does not declare but that are known garbage: values ~1e31 in TQA and SPPA of Volve F-10
# 1-2-3-1 and F-15S 1-1-2-1, and 32767 (maximum of a 16-bit integer) in the RPM of F-15S 1-1-2-1.
SENTINEL_ABS = 1e30
SENTINEL_INT16 = 32767.0
# -999.25 is the conventional null of LAS/DLIS/Pason. If the file declares it, it is logged as "declared_null"; if
# not (Pason CSV, DLIS) it is removed anyway and logged separately as "sentinel_-999.25".
CONVENTION_NULL = -999.25


@dataclass
class Reading:
    data: pd.DataFrame                                   # index: UTC time (DatetimeIndex) or depth in m
    source_unit: dict = field(default_factory=dict)      # channel -> symbol as written in the file (None if absent)
    unit: dict = field(default_factory=dict)             # channel -> unit the data is now in
    description: dict = field(default_factory=dict)      # channel -> description from the file (curveDescription, descr...)
    role: dict = field(default_factory=dict)             # channel -> physical role or None
    log: list = field(default_factory=list)              # dicts: channel, action, n, detail, source
    meta: dict = field(default_factory=dict)

    def log_table(self):
        return pd.DataFrame(self.log, columns=["channel", "action", "n", "detail", "source"])

    def n(self, channel, action):
        return sum(r["n"] for r in self.log if r["channel"] == channel and r["action"] == action)


def _log(rd, channel, action, n, detail="", source=""):
    rd.log.append(dict(channel=channel, action=action, n=int(n), detail=detail, source=source))


def filter_blacklist(names, source, channels, allow, rd):
    """Return the names that may be read. Asking for a blacklisted channel without `allow` raises AmbiguousChannel."""
    allow = set(allow or ())
    asked = set(channels) if channels is not None else None
    keep = []
    for c in names:
        why = R.blacklist_reason(c, source)
        if why is None or c in allow:
            if why is not None:
                _log(rd, c, "blacklist_allowed", 0, why, "allow= from the caller")
            keep.append(c)
            continue
        if asked is not None and c in asked:
            raise R.AmbiguousChannel(f"{c}: {why}. If it is really needed, pass it in allow=")
        _log(rd, c, "blacklist_skipped", 0, why, "roles.py")
    return keep


def process(rd, raw, source, declared_nulls=None, drop_convention_null=True, convert=True, assumed=None):
    """raw: DataFrame (text or numbers) with its index already built. Fills rd.data and the log.

    declared_nulls: channel -> list of null values declared by the file (WITSML nullValue, LAS NULL).
    assumed: channel -> (symbol, source) for channels without a unit in the file; never applied without a source.
    """
    declared_nulls = declared_nulls or {}
    assumed = assumed or {}
    out = {}
    for c in raw.columns:
        col = raw[c]
        if col.dtype == object or pd.api.types.is_string_dtype(col.dtype):
            s = col.astype("string").str.strip()
            empty = s.isna() | (s == "")
            v = pd.to_numeric(s.where(~empty), errors="coerce")
            ntxt = int((v.isna() & ~empty).sum())
            if ntxt:
                _log(rd, c, "non_numeric_text", ntxt, "non-numeric value -> NaN")
        else:
            v = pd.to_numeric(col, errors="coerce")
        v = v.astype("float64")
        for nv in declared_nulls.get(c, []):
            m = v == float(nv)
            if m.any():
                _log(rd, c, "declared_null", m.sum(), f"value {nv}", "declared in the file")
                v = v.mask(m)
        m = v.abs() >= SENTINEL_ABS
        if m.any():
            _log(rd, c, "sentinel_1e30", m.sum(), f"|v| >= {SENTINEL_ABS:g}", "known sentinel (lector-canales E4)")
            v = v.mask(m)
        m = v == SENTINEL_INT16
        if m.any():
            _log(rd, c, "sentinel_32767", m.sum(), "v == 32767 (int16 maximum)", "known sentinel (lector-canales E4)")
            v = v.mask(m)
        if drop_convention_null:
            m = v == CONVENTION_NULL
            if m.any():
                _log(rd, c, "sentinel_-999.25", m.sum(), "undeclared LAS/DLIS/Pason convention null", "LAS 2.0 convention")
                v = v.mask(m)
        role = R.role_of(c, source)
        rd.role[c] = role
        u = U.normalize_symbol(rd.source_unit.get(c))
        if u is None and c in assumed:
            sym, src = assumed[c]
            if not src:
                raise U.UndeclaredUnit(f"{c}: assumed unit without a source")
            _log(rd, c, "assumed_unit", 0, f"{sym}", src)
            u = sym
        if convert:
            dim = R.ROLE_DIM.get(role) if role else None
            row = U.lookup(u)
            if row is None:
                if dim is not None:
                    if u is None:
                        raise U.UndeclaredUnit(f"{c} (role {role}): the file declares no unit; pass it in assumed= with its source")
                    raise U.UnitWithoutSource(f"{c} (role {role}): unit {u!r} has no row in units.tsv")
                rd.unit[c] = u
                if u not in (None, "unitless", "", "N/A"):
                    _log(rd, c, "not_converted", 0, f"unit {u!r} has no row in units.tsv; left as is")
            else:
                v, row = U.convert(v, u, dim, c)
                rd.unit[c] = row["canonical"]
                if row["factor"] != 1 or row["offset"] != 0 or row["symbol"] != row["canonical"]:
                    _log(rd, c, "conversion", int(v.notna().sum()),
                         f"{u} -> {row['canonical']} x{row['factor']:.10g}" + (f" {row['offset']:+g}" if row["offset"] else ""),
                         f"[{row['confidence']}] {row['source']}")
        else:
            rd.unit[c] = u
        out[c] = v.to_numpy()
    rd.data = pd.DataFrame(out, index=raw.index)
    return rd


def clip_range(rd, ranges, source):
    """Set out-of-range values to NaN, in canonical units. ranges: channel -> (min, max). A source is required."""
    if not source:
        raise ValueError("clip_range needs the source of the range (protocol, decision record...)")
    for c, (lo, hi) in ranges.items():
        if c not in rd.data:
            continue
        v = rd.data[c]
        m = v.notna() & ((v < lo) | (v > hi))
        if m.any():
            _log(rd, c, "out_of_range", m.sum(), f"outside [{lo}, {hi}] {rd.unit.get(c)}", source)
            rd.data[c] = v.mask(m)
    return rd
