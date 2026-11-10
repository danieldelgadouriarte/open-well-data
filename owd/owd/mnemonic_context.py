# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Unit dimensions and context rules for mnemonics whose meaning depends on the source.

- unit_info(symbol) -> (dimension, factor, offset) to the base unit of the dimension, None if the file declares no
  unit, ("?", None, None) if the symbol is unknown. The table holds the symbols seen in the LAS, DLIS, LIS and WITSML
  headers harvested for DICTIONARY.md.
- context_variable(mnemonic, unit, source_format) -> variable from data/mnemonic_context.csv, or "" when the mnemonic
  has no context rule. source_format: "LAS", "DLIS", "LIS", "WITSML" (log files) or anything else (tables).
Standard library only.
"""
import csv
import math
import os
from collections import defaultdict


# ------------------------------------------------------------------ units: symbol -> (dimension, factor, offset) to base
# base units: length m, time s, velocity m/s, slowness s/m, density kg/m3, pressure Pa, force N, torque N.m,
# frequency 1/s (rpm = 1/60), flow_rate m3/s, volume m3, temperature degC, resistivity ohm.m, conductivity S/m,
# radioactivity gAPI, potential mV, fraction v/v, pef b/e, angle deg, acceleration m/s2, permeability mD,
# capture_cross_section cu, dimensionless 1.
U = {}


def _u(dim, factor, *symbols, offset=0.0):
    for s in symbols:
        U[s] = (dim, factor, offset)


_u("length", 1, "m", "M", "meters", "metres", "meter")
_u("length", 0.3048, "ft", "FT", "F", "feet", "FEET", "f")
_u("length", 0.0254, "in", "IN", "INCH", "inch", "inches", "INCHES")
_u("length", 0.00254, "0.1 in")
_u("length", 0.001, "mm", "MM")
_u("length", 0.01, "cm", "CM")
_u("time", 1, "s", "sec", "S")
_u("time", 1e-3, "ms", "MS")
_u("time", 60, "min", "MIN")
_u("time", 3600, "h", "hr", "HR", "H")
_u("velocity", 1, "m/s", "M/S")
_u("velocity", 1 / 3600, "m/h", "M/HR", "M/H", "m/hr", "MPH")
_u("velocity", 0.3048 / 3600, "ft/h", "ft/hr", "FT/HR", "F/HR", "ft_per_hr", "FPH")
_u("velocity", 1 / 60, "m/min")
_u("slowness", 1e-6 / 0.3048, "us/ft", "US/F", "usec/ft", "US/FT", "uspf", "USEC/FT", "us/f")
_u("slowness", 1e-6, "us/m", "US/M")
_u("slowness", 1, "s/m")
_u("density", 1000, "g/cm3", "G/CC", "G/C3", "g/cc", "GM/CC", "gm/cc", "G/CM3", "sg", "SG")
_u("density", 1, "kg/m3", "K/M3", "KG/M3")
_u("density", 0.45359237 / 0.003785411784, "ppg", "PPG", "lbm/gal", "lb/gal")
_u("pressure", 1, "Pa", "PA")
_u("pressure", 1e3, "kPa", "KPA", "kpa")
_u("pressure", 1e6, "MPa", "MPA")
_u("pressure", 1e5, "bar", "BAR", "bars")
_u("pressure", 6894.757293168361, "psi", "PSI", "psia", "PSIA", "psig", "PSIG")
_u("force", 1, "N")
_u("force", 1e3, "kN", "KN")
_u("force", 9806.65, "kkgf", "KKGF", "1000 kgf", "tonne", "TON", "t", "ton", "TONNE")
_u("force", 9.80665, "kgf", "KGF")
_u("force", 4.4482216152605, "lbf", "LBF", "lbs", "LBS")
_u("force", 4448.2216152605, "klbs", "klb", "klbf", "KLBS", "KLB", "KLBF", "1000lbm", "kips", "KIPS")
_u("force", 10, "daN", "DAN")
_u("torque", 1, "N.m", "NM", "N.M", "Nm")
_u("torque", 1e3, "kN.m", "KNM", "KN.M", "kNm", "KMN")
_u("torque", 1e4, "km.daN", "KMDN")
_u("torque", 1.3558179483314004, "ft-lbs", "lb-ft", "ft.lbf", "FT-LBS", "LB-FT", "ftlb", "FTLB", "ft-lb")
_u("torque", 1355.8179483314004, "kft_lb", "kft-lbs", "kft.lbf", "KFT-LBS", "kftlb", "KFTLB", "kft-lb")
_u("frequency", 1 / 60, "rpm", "RPM", "c/min", "1/min", "rev/min", "RPMS", "spm", "SPM", "cpm", "CPM")
_u("frequency", 1, "c/s", "1/s", "Hz", "HZ", "cps", "CPS", "rps")
_u("frequency", 1 / (2 * math.pi), "rad/s")
_u("flow_rate", 1, "m3/s")
_u("flow_rate", 1 / 60000, "L/min", "LPM", "L/MN", "l/min", "lpm")
_u("flow_rate", 1 / 60, "m3/min", "M3/MIN")
_u("flow_rate", 1 / 3600, "m3/h", "M3/H")
_u("flow_rate", 1 / 86400, "m3/d", "M3/D")
_u("flow_rate", 6.30901964e-5, "gal/min", "gpm", "GPM", "gal_per_min", "galUS/min")
_u("flow_rate", 0.158987294928 / 60, "bbl/min", "BPM", "bpm")
_u("volume", 1, "m3", "M3")
_u("volume", 0.158987294928, "bbl", "BBL", "barrels", "bbls", "BBLS")
_u("volume", 0.001, "L", "l")
_u("temperature", 1, "degC", "DEGC", "C", "deg C", "degc", "DEG C")
_u("temperature", 5 / 9, "degF", "DEGF", "deg F", "degf", "DEG F", offset=-32 * 5 / 9)
_u("temperature", 1, "K", offset=-273.15)
_u("resistivity", 1, "ohm.m", "OHMM", "ohmm", "ohm-m", "OHM-M", "Ohm.m", "OHM.M", "ohm m", "Ohmm")
_u("conductivity", 1, "S/m")
_u("conductivity", 1e-3, "mS/m", "MS/M", "mmho/m", "MMHO/M", "MMHO", "mmho")
_u("radioactivity", 1, "gAPI", "GAPI", "API", "api", "gapi", "GAPI units")
_u("potential", 1, "mV", "MV", "mv")
_u("potential", 1e3, "V")
_u("fraction", 1, "v/v", "V/V", "frac", "FRAC", "fraction", "dec", "DEC", "m3/m3", "ft3/ft3", "v/v_decimal",
   "CFCF", "cfcf", "Fraction", "FRACTION")
_u("fraction", 0.01, "%", "percent", "pu", "PU", "p.u.", "PCT", "pct", "%vol")
_u("fraction", 1e-6, "ppm", "PPM")
_u("fraction", 1e-3, "ppk", "PPK")
_u("pef", 1, "b/e", "B/E", "b/elec", "B/ELEC", "barns/e")
_u("angle", 1, "deg", "dega", "DEG", "degrees", "DEGA")
_u("angle", 180 / math.pi, "rad", "RAD")
_u("acceleration", 1, "m/s2")
_u("acceleration", 9.80665, "gravity", "G", "g_n")
_u("acceleration", 0.3048, "ft/s2")
_u("permeability", 1, "mD", "MD", "md")
_u("capture_cross_section", 1, "cu", "CU")
_u("power", 1, "W")
_u("power", 1e3, "kW", "KW")
_u("power", 0.3048 * 0.45359237 * 9.80665 * 550, "hp", "HP")
_u("current", 1, "A", "AMP", "amp")
_u("current", 1e-3, "mA", "MA")
_u("magnetic_field", 1, "T")
_u("magnetic_field", 1e-9, "nT", "NT", "gamma")
_u("conductivity", 1e-3, "MMHO/M", "mMHO", "MMHOS/M")
_u("pef", 1, "BARN", "barn", "B/EL")
_u("dimensionless", 1, "unitless", "UNITLESS", "none", "NONE", "ratio")
_u("fraction", 1, "kgf/kgf", "KGF/KGF")
_u("dimensionless", 1, "_")      # only as a variable unit: in files "_" is read as "no unit" (UNKNOWN_UNIT)
UNKNOWN_UNIT = {"", "_", "Time", "Euc", "EUC", "UNKNOWN", "....", "----", ".", "nan", "None", "BAD_UNIT-?"}

# ------------------------------------------------------------------ one unit table: conversion_units.tsv
# The converter (owd.convert) reads conversion_units.tsv. Every symbol and alias there that the hand-written table
# above lacks is added here, translated to this table's bases (rpm -> 1/s, V -> mV, ratio -> fraction), so that the
# dictionary verifies exactly the symbols the converter converts. tests/test_unit_tables.py checks that every symbol
# of this table is one of the readings of conversion_units.tsv and that no symbol of conversion_units.tsv is missing.
CONVERSION_UNITS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conversion_units.tsv")
_CONV_DIM = {"angular_velocity": ("frequency", 1 / 60), "count_rate": ("frequency", 1.0),
             "potential": ("potential", 1000.0), "ratio": ("fraction", 1.0), "code": ("dimensionless", 1.0)}


def _number(expr):
    return float(eval(str(expr), {"__builtins__": {}}, {}))      # arithmetic of the repository file only


def conversion_readings(path=CONVERSION_UNITS):
    """symbol -> list of (dimension, factor, offset) in the bases of U, in the order of conversion_units.tsv."""
    out = {}
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            dim, k = _CONV_DIM.get(r["dimension"], (r["dimension"], 1.0))
            if r["symbol"] == "b/e":
                dim = "pef"
            reading = (dim, _number(r["factor"]) * k, _number(r["offset"] or "0") * k)
            for sym in [r["symbol"]] + [a for a in r["aliases"].split("|") if a]:
                out.setdefault(sym, []).append(reading)
    return out


CONVERSION_READINGS = conversion_readings()
for _s, _r in CONVERSION_READINGS.items():
    if _s not in U and _s.strip() == _s and _s not in UNKNOWN_UNIT:
        U[_s] = _r[0]


def unit_table_disagreements():
    """Symbols whose reading in U is none of the readings of conversion_units.tsv, and symbols of U missing there."""
    bad = []
    for sym, (dim, fac, off) in U.items():
        if sym in UNKNOWN_UNIT:
            continue
        rs = CONVERSION_READINGS.get(sym)
        if not rs:
            bad.append((sym, "missing in conversion_units.tsv"))
            continue
        if not any((d == dim or {d, dim} <= {"fraction", "dimensionless"}) and math.isclose(f, fac, rel_tol=1e-9)
                   and math.isclose(o, off, rel_tol=1e-9, abs_tol=1e-9) for d, f, o in rs):
            bad.append((sym, f"U {(dim, fac, off)} vs conversion_units.tsv {rs}"))
    return bad


# ------------------------------------------------------------------ documented unit fixes (conversion_rules.tsv)
CONVERSION_RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conversion_rules.tsv")


def _load_rules(path=CONVERSION_RULES):
    rules = defaultdict(list)
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["action"] == "assume_unit":
                rules[r["mnemonic"].strip().upper()].append(([w for w in r["when_unit"].split("|") if w], r["unit"]))
    return rules


RULES = _load_rules()


def assumed_unit(mnemonic, unit):
    """Unit to use for verification when conversion_rules.tsv documents a mislabelled unit (TENS in lbm -> lbf), else
    the declared unit. 'none' matches an empty unit, 'dimensionless' a unitless one."""
    u = (unit or "").strip()
    for when, to in RULES.get(str(mnemonic).strip().upper(), []):
        for w in when:
            if (w == "none" and (u == "" or u in UNKNOWN_UNIT)) or (w == "dimensionless" and U.get(u, ("",))[0] == "dimensionless") \
                    or w == u:
                return to
    return unit


VAR_DIM = {"angular_velocity": "frequency", "dimensionless": "dimensionless", "code": "dimensionless"}
RATIO = {"fraction", "dimensionless"}


# difference dimension -> absolute dimension whose units it takes by scale only (no offset), as in owd.convert
DIFFERENCE_DIMS = {"temperature_difference": "temperature"}
# a context rule with this variable keeps the mnemonic out of every variable (no fallback to the name)
UNASSIGNED = "-"


def compat(a, b):
    return (a == b or (a in RATIO and b in RATIO) or DIFFERENCE_DIMS.get(a) == b or DIFFERENCE_DIMS.get(b) == a)


def unit_info(u):
    u = (u or "").strip()
    if u in UNKNOWN_UNIT or set(u) <= {"-", "."}:
        return None
    return U.get(u) or U.get(u.lower()) or ("?", None, None)


def to_var_unit(x, src, var_unit, dim):
    """Convert a value from src unit to var_unit (both in table U)."""
    s = unit_info(src)
    t = U.get(var_unit)
    if s is None or s[0] == "?" or t is None or not compat(s[0], t[0]):
        return None
    if DIFFERENCE_DIMS.get(t[0]) == s[0]:
        return x * s[1] / t[1]                       # a difference: scale only, no offset
    base = x * s[1] + s[2]
    return (base - t[2]) / t[1]

U["spm"] = U["rpm"]
LOG_FORMATS = {"LAS", "DLIS", "LIS", "WITSML"}
CONTEXT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "mnemonic_context.csv")


def load_context(path=CONTEXT_FILE):
    table = defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            table[r["mnemonic"].strip().upper()].append(r)
    return table


CONTEXT = load_context()


def unit_dimension(unit):
    """Dimension of a declared unit symbol; None if no unit is declared or the symbol is unknown."""
    i = unit_info(unit)
    return None if i is None or i[0] == "?" else i[0]


def dataset_matches(want, dataset):
    """Dataset condition of a context rule: empty = any (also unknown); '*' = any declared dataset; otherwise the id
    equals one of the values or starts with it and a hyphen ('_' counts as '-'), as owd.convert.dataset_matches."""
    if not want:
        return True
    ds = str(dataset or "").strip().lower().replace("_", "-")
    if not ds:
        return False
    for w in want:
        w = w.strip().lower().replace("_", "-")
        if w == "*" or ds == w or ds.startswith(w + "-"):
            return True
    return False


def context_rule(key, dim, fmt, table=None, dataset=None):
    """Variable from the context table for an upper-case mnemonic, a unit dimension (None = no unit), a source format
    and a dataset id; "" if the mnemonic has no context rule or none matches; UNASSIGNED if a rule keeps it out."""
    for r in (CONTEXT if table is None else table).get(key, ()):
        want_dim = [x for x in r["when_unit_dimension"].split("|") if x]
        if want_dim and not any((dim is None and w == "unknown") or (dim is not None and compat(dim, w)) for w in want_dim):
            continue
        src = [x for x in r["when_source"].split("|") if x]
        if src:
            ok = False
            for w in src:
                ok |= (w == "log" and fmt in LOG_FORMATS) or (w == "table" and fmt not in LOG_FORMATS) or w == fmt
            if not ok:
                continue
        if not dataset_matches([x for x in (r.get("when_dataset") or "").split("|") if x], dataset):
            continue
        return r["variable"]
    return ""


def context_variable(mnemonic, unit=None, source_format=None, table=None, dataset=None):
    """Variable for a mnemonic in its context (declared unit, source format and dataset), "" if no context rule
    applies, or UNASSIGNED if a rule keeps it out of every variable."""
    key = str(mnemonic or "").strip().upper()
    if key not in (CONTEXT if table is None else table):
        return ""
    return context_rule(key, unit_dimension(unit), (source_format or "").upper(), table, dataset)
