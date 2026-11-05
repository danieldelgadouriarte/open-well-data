# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Free for non-commercial use; companies need a licence (see NOTICE).
"""Common naming layer: maps each source's channel names to canonical channels and converts units to SI.

Uses the unit table of the channel reader (factor and source of every conversion) and adds the step from the reader's
canonical units (kkgf, ...) to those of Open Well Data (kN, ...)."""
import csv, os, re
import pandas as pd
_DIR = os.path.dirname(__file__)
CHANNELS = list(csv.DictReader(open(os.path.join(_DIR, "channels.tsv"), encoding="utf-8"), delimiter="\t"))
_ALIAS = {}
for c in CHANNELS:
    for a in c["aliases"].split("|"):
        _ALIAS.setdefault(a.strip().lower(), c["canonical"])
_ROLE = {c["reader_role"]: c["canonical"] for c in CHANNELS if c["reader_role"]}
# From the reader (Volve canonical units) to Open Well Data. 1 kgf = 9.80665 N (NIST SP 811 B.9, exact).
READER_TO_OWD = {"kkgf": ("kN", 9.80665), "m/h": ("m/h", 1.0), "kPa": ("kPa", 1.0), "kN.m": ("kN.m", 1.0),
                 "rpm": ("rpm", 1.0), "L/min": ("L/min", 1.0), "m": ("m", 1.0)}

# Equivalent spellings of the same unit (compared case-insensitively).
_EQ = {"gapi": "gAPI", "g/c3": "g/cm3", "g/cc": "g/cm3", "g/cm3": "g/cm3", "us/f": "us/ft", "us/ft": "us/ft",
       "ohmm": "ohm.m", "ohm.m": "ohm.m", "in": "in", "b/e": "b/e", "mv": "mV", "v/v": "v/v", "dec": "v/v",
       "m/hr": "m/h", "m/h": "m/h", "kn": "kN", "kpa": "kPa", "kn.m": "kN.m", "rpm": "rpm", "l/min": "L/min",
       "m": "m", "degc": "degC", "m3/d": "m3/d", "m3/m3": "v/v"}
_UNIT = {c["canonical"]: c["unit"] for c in CHANNELS}

def equivalent_unit(u):
    return _EQ.get(str(u).strip().lower()) if u is not None else None

def canonical(name, role=None):
    """Canonical name of a channel, or None. First by physical role (if the reader gave one), then by alias."""
    if role and role in _ROLE:
        return _ROLE[role]
    base = re.sub(r"\s*\([^()]*\)\s*$", "", str(name)).strip().lower()
    return _ALIAS.get(base)

def standardize(reading, known_only=False):
    """Reader output -> DataFrame with canonical columns in Open Well Data units.
    Channels without a canonical name keep their original name (or are dropped with known_only=True).
    df.attrs keeps the original name and unit of every column."""
    df = reading.data.copy()
    ren, original, unit = {}, {}, {}
    for c in df.columns:
        can = canonical(c, reading.role.get(c))
        u = reading.unit.get(c)
        if can and u is None:
            can = None   # without a declared unit a channel is not labelled as standard
        if can and u in READER_TO_OWD:
            u2, f = READER_TO_OWD[u]
            if equivalent_unit(u2) == _UNIT[can]:
                df[c] = df[c] * f; u = u2
        if can and equivalent_unit(u) != _UNIT[can]:
            can = None   # unit differs from the standard one and has no sourced conversion: keeps its name
        if can and can not in ren.values():
            u = _UNIT[can]
            ren[c] = can
        elif known_only:
            df = df.drop(columns=c); continue
        original[ren.get(c, c)] = {"name": c, "unit": reading.source_unit.get(c)}
        unit[ren.get(c, c)] = u
    df = df.rename(columns=ren)
    meta = dict(reading.meta); meta["file"] = meta.pop("source_path", None)
    df.attrs.update({**meta, "original": original, "unit": unit})
    return df
