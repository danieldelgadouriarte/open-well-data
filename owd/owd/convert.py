# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Conversion engine: channel names and units, with provenance and citation. Single source of truth.

The same tables drive this module and the web converter (sitio/static/convert.js reads data/convert-tables.json, written
by tables()). Change a rule here or in the tables, never in one place only: the parity test checks both give the same
output byte for byte.

Tables (read at import time):
  conversion_units.tsv     every unit symbol, its dimension, factor and offset to the base unit of its dimension, the
                           spellings seen in files, an interpretation note when the reading is not literal, and its source
  conversion_presets.tsv   the "field" (oilfield) target: one unit per dimension and exceptions per variable
  conversion_rules.tsv     documented fixes for mislabelled units (mnemonic + declared unit -> assumed unit)
  variables.tsv            variables, dimensions, OWD standard units ("si" target) and mnemonics (dictionary)
  data/mnemonic_context.csv  meaning by declared unit dimension and source format
  data/mnemonic_conflicts.csv  open conflicts, reported as warnings
  channels.tsv             aliases used by the readers
  channel_statistics.tsv   explicit rules that say which statistic a channel is (mean, max, min, std...) and its window

How a channel is mapped, in order: standard name (an OWD variable name, exact, or a variable name with a statistic
qualifier such as hookload_max), context rule, dictionary mnemonic (listed under exactly one variable), channels.tsv
alias. A mapped channel is renamed and converted only when its declared unit resolves to the dimension of the variable;
otherwise it keeps its name and values and a warning says why. Unknown channels keep their name and values and are
reported, never dropped.

Statistic of a labelled channel (7 Nov 2026): the variable stays the same (HKLD_MIN, HKLX and HKLD are all hookload),
and a statistic qualifier says which aggregate the column is: unspecified or inst (instantaneous) are written with the
variable name alone; mean, max, min, std, median and rms add a suffix (hookload_mean, hookload_max, hookload_min) for
drilling and mud_gas variables. Log variables (logs, petrophysics and the other families) keep the plain name and the
statistic only in the provenance, except when two different statistics of one variable coexist in the file
(caliper_max, caliper_min); see naming_statistics(). It is
decided only from explicit evidence (channel_statistics.tsv): a whole statistic token in the name (HKLD_MIN, WOB_MAX),
a glued suffix whose stem is a mnemonic of the same variable (WOBAVG), or the channel's own description ("Average
Hookload", "Maximum Hookload"). One-letter suffixes (HKLX, HKLA, TQX) say nothing by themselves. When a statistic word
in the name and the description disagree (Volve TORQUE_MAX described as "Surface Torque Average"), the name is kept and
a warning says so; several statistics in one name or in one description leave it unspecified, with a warning. Numeric suffixes (_2, _3) are kept for true
duplicates only (same variable and same statistic). The window, when the description states it (5 ft, time, depth), is
recorded in the provenance.

Python API:
  plan_channels(channels, names=, units=, source_format=)   -> per-channel plan (the provenance rows)
  convert_frame(df, units={col: unit}, names=, target=)     -> (DataFrame, provenance)
  convert_text(text, ...) / convert_file(path, ...)         -> LAS 2.0 or CSV in, CSV / LAS / Parquet out
  tables()                                                  -> the JSON the web page loads
Standard library only, except pandas for frames and pyarrow for Parquet.
"""
import ast
import csv
import datetime
import hashlib
import io
import json
import operator
import os
import re
import shutil
import subprocess
import urllib.parse
from decimal import Decimal, ROUND_HALF_UP

_DIR = os.path.dirname(os.path.abspath(__file__))
SITE = "https://openwelldata.org"
ENGINE_VERSION = "1.1"   # 1.1 (7 Nov 2026): statistic qualifier in names and provenance (channel_statistics.tsv)
TABLES_FORMAT = 2        # 2: tables carry "statistics"
AUTHOR = "Delgado-Uriarte"
CONTACT = "contact@openwelldata.org"
LICENCE_NOTE = ("Free for non-commercial use with credit. Companies need written permission: " + CONTACT +
                " (" + SITE + "/licence/#permission).")
AS_STATED = "as stated by the source"
LOG_FORMATS = ("LAS", "DLIS", "LIS", "WITSML")
UNKNOWN_UNIT = ("", "_", "Time", "Euc", "EUC", "UNKNOWN", "Unknown", "unknown", "nan", "NaN", "None", "N/A", "n/a",
                "NA")
RATIO_DIMS = ("fraction", "dimensionless", "ratio")
DEFAULT_DIGITS = 12   # significant digits of converted values in files; 0 = full double precision
DICTIONARY_FILES = ["variables.tsv", "channels.tsv", "conversion_units.tsv", "conversion_presets.tsv",
                    "conversion_rules.tsv", "data/mnemonic_context.csv", "data/mnemonic_conflicts.csv",
                    "channel_statistics.tsv"]
# Statistics that qualify the output name (variable + "_" + statistic). "unspecified" and "inst" keep the plain name.
QUALIFIED_STATISTICS = ("mean", "max", "min", "std", "median", "rms")
PLAIN_STATISTICS = ("unspecified", "inst")
_QUALIFIED_NAME = re.compile(r"^(.+)_(" + "|".join(QUALIFIED_STATISTICS) + r")$")


class ConversionError(ValueError):
    """Bad input or option (unknown target unit, unsupported file...)."""


# ------------------------------------------------------------------ table loading
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def number_expression(s):
    """Evaluate a factor written as arithmetic on numbers only (e.g. 0.45359237*9.80665/(0.0254*0.0254))."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return float(n.value)
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -ev(n.operand)
        raise ValueError(f"not a number expression: {s!r}")
    return ev(ast.parse(str(s).strip(), mode="eval"))


def _rows(path, delimiter):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def _split(s):
    return [x for x in (s or "").split("|") if x != ""]


def _git(args, files):
    try:
        out = subprocess.run(["git", "-C", _DIR] + args + ["--"] + files, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def build_tables(directory=_DIR):
    """Read the dictionary and conversion files into one dict (the content of data/convert-tables.json)."""
    units = []
    for r in _rows(os.path.join(directory, "conversion_units.tsv"), "\t"):
        units.append({"symbol": r["symbol"], "dimension": r["dimension"], "base": r["base"],
                      "factor": number_expression(r["factor"]), "offset": number_expression(r["offset"] or "0"),
                      "aliases": _split(r["aliases"]), "note": r["note"] or "", "source": r["source"] or ""})
    field_dim, field_var, notes = {}, {}, {}
    for r in _rows(os.path.join(directory, "conversion_presets.tsv"), "\t"):
        (field_dim if r["scope"] == "dimension" else field_var)[r["key"]] = r["field"]
        if r.get("note"):
            notes[r["scope"] + ":" + r["key"]] = r["note"]
    rules = [{"mnemonic": r["mnemonic"].strip().upper(), "when_unit": _split(r["when_unit"]), "variable": r["variable"],
              "action": r["action"], "unit": r["unit"], "note": r["note"], "source": r["source"]}
             for r in _rows(os.path.join(directory, "conversion_rules.tsv"), "\t")]
    variables = {}
    for r in _rows(os.path.join(directory, "variables.tsv"), "\t"):
        variables[r["variable"]] = {"dimension": r["dimension"], "unit": r["unit"], "family": r["family"],
                                    "description": r["description"], "mnemonics": _split(r["mnemonics"])}
    context = {}
    for r in _rows(os.path.join(directory, "data", "mnemonic_context.csv"), ","):
        context.setdefault(r["mnemonic"].strip().upper(), []).append(
            {"when_unit_dimension": _split(r["when_unit_dimension"]), "when_source": _split(r["when_source"]),
             "when_dataset": _split(r.get("when_dataset") or ""), "variable": r["variable"], "note": r["note"]})
    conflicts = {}
    for r in _rows(os.path.join(directory, "data", "mnemonic_conflicts.csv"), ","):
        t = r.get("conflict_type") or ""
        if t and t != "resolved_by_context":
            lst = conflicts.setdefault(r["mnemonic"].strip().upper(), [])
            if t not in lst:
                lst.append(t)
    aliases = {}
    for r in _rows(os.path.join(directory, "channels.tsv"), "\t"):
        for a in _split(r["aliases"]):
            aliases.setdefault(a.strip().lower(), r["canonical"])
    statistics = [{"kind": r["kind"], "pattern": r["pattern"], "statistic": r["statistic"] or "",
                   "window": r["window"] or "", "not_dimension": _split(r["not_dimension"]), "note": r["note"] or ""}
                  for r in _rows(os.path.join(directory, "channel_statistics.tsv"), "\t")]
    t = {"format": TABLES_FORMAT, "units": units,
         "presets": {"field": {"dimension": field_dim, "variable": field_var, "notes": notes}},
         "rules": rules, "variables": variables, "context": context, "conflicts": conflicts, "aliases": aliases,
         "statistics": statistics,
         "unknown_units": list(UNKNOWN_UNIT), "log_formats": list(LOG_FORMATS), "ratio_dimensions": list(RATIO_DIMS),
         "naming": {"schemes": ["owd", "original"],
                    "note": "A naming scheme maps an OWD variable to a name. More schemes (e.g. OSDU) can be added with "
                            "owd.convert.register_naming(name, mapping) without changing the engine."}}
    version = hashlib.sha256(json.dumps(t, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()[:12]
    t["meta"] = {"dictionary_version": version, "engine_version": ENGINE_VERSION,
                 "dictionary_commit": _git(["log", "-1", "--format=%h"], DICTIONARY_FILES),
                 "dictionary_date": _git(["log", "-1", "--format=%cs"], DICTIONARY_FILES),
                 "site": SITE, "author": AUTHOR, "contact": CONTACT, "licence_note": LICENCE_NOTE}
    t["datasets"] = datasets_table()        # citation and access only; not part of the dictionary version
    t["copies_base_url"] = ""               # where the standardized copies live once published (set by the site build)
    return t


def datasets_table():
    """Registry datasets with their licence, citation, policy and recipe files (for citations and the Get data routes)."""
    try:
        from .registry import DATASETS
        from .recipes import recipes
    except ImportError:
        return {}
    rec = recipes()
    out = {}
    for k, d in DATASETS.items():
        r = rec.get(k) or {}
        out[k] = {"name": d["name"], "url": d["url"], "license": d["license"], "spdx": d.get("spdx"),
                  "citation": d["citation"], "policy": d["policy"], "format": d.get("format"), "terms": d.get("terms") or r.get("terms"),
                  "download": r.get("download"), "files": [{"name": f["name"], "url": f.get("url"), "bytes": f.get("bytes")}
                                                         for f in r.get("files", [])]}
    return out


class Index:
    """Lookup structures built from the tables (the JS builds the same ones)."""

    def __init__(self, t):
        self.t = t
        self.units = t["units"]
        self.exact, self.lower = {}, {}
        for i, u in enumerate(self.units):
            for s in [u["symbol"]] + u["aliases"]:
                lst = self.exact.setdefault(s, [])
                if i not in lst:
                    lst.append(i)
                lst = self.lower.setdefault(s.lower(), [])
                if i not in lst:
                    lst.append(i)
        self.mnem = {}
        for v, d in t["variables"].items():
            for m in d["mnemonics"]:
                lst = self.mnem.setdefault(m.upper(), [])
                if v not in lst:
                    lst.append(v)
        self.std = {}                   # (dimension, symbol) -> unit index, for targets
        for i, u in enumerate(self.units):
            self.std.setdefault((u["dimension"], u["symbol"]), i)
        # statistic rules; regular expressions are case-insensitive and use only syntax shared with JavaScript
        self.stat_rules = [dict(r, rx=re.compile(r["pattern"], re.I) if r["kind"] in ("window", "exclude", "description")
                                else None) for r in t.get("statistics", [])]

    @property
    def version(self):
        return self.t["meta"]["dictionary_version"]


_INDEX = None


def index():
    global _INDEX
    if _INDEX is None:
        _INDEX = Index(build_tables())
    return _INDEX


def tables():
    """The tables as written to data/convert-tables.json (a fresh read of the files)."""
    return build_tables()


# ------------------------------------------------------------------ units
def is_no_unit(s):
    s = (s or "").strip()
    return s in UNKNOWN_UNIT or set(s) <= set("-.") or s.startswith("BAD_UNIT")


def resolve_unit(s, dimension=None, ix=None):
    """Resolve a declared unit symbol. Returns a dict with status ok | none | unknown | mismatch | ambiguous, the unit
    row index (ok), the candidate dimensions and how the symbol matched (exact or case-insensitive)."""
    ix = ix or index()
    s = (s or "").strip()
    if is_no_unit(s):
        return {"status": "none", "dimensions": []}
    cands, how = ix.exact.get(s), "exact"
    if not cands:
        cands, how = ix.lower.get(s.lower()), "case-insensitive"
    if not cands:
        return {"status": "unknown", "dimensions": []}
    dims = []
    for i in cands:
        if ix.units[i]["dimension"] not in dims:
            dims.append(ix.units[i]["dimension"])
    if dimension:
        f = [i for i in cands if ix.units[i]["dimension"] == dimension]
        if not f:
            return {"status": "mismatch", "dimensions": dims, "match": how}
        cands = f
    u0 = ix.units[cands[0]]
    for i in cands[1:]:
        u = ix.units[i]
        if (u["base"], u["factor"], u["offset"], u["dimension"]) != (u0["base"], u0["factor"], u0["offset"], u0["dimension"]):
            return {"status": "ambiguous", "dimensions": dims, "match": how}
    return {"status": "ok", "unit": cands[0], "dimensions": dims, "match": how}


def factor_offset(src, dst):
    """y = x * factor + offset converts from unit row src to unit row dst (same base)."""
    if src is dst or (src["factor"] == dst["factor"] and src["offset"] == dst["offset"]):
        return 1.0, 0.0
    return src["factor"] / dst["factor"], (src["offset"] - dst["offset"]) / dst["factor"]


def unit_row(symbol, dimension, ix=None):
    """Unit row for a target symbol in a dimension: exact symbol first, then any spelling of it."""
    ix = ix or index()
    i = ix.std.get((dimension, symbol))
    if i is None:
        r = resolve_unit(symbol, dimension, ix)
        i = r.get("unit") if r["status"] == "ok" else None
    return None if i is None else ix.units[i]


def apply_linear(x, base):
    """Convert with the base factors [factor_from, offset_from, factor_to, offset_to] of a plan: through the base unit,
    y = (x * a + b - d) / c. Same operation order in the JS, so both give the same double."""
    a, b, c, d = base
    if b == 0 and d == 0:
        return x * a / c
    return (x * a + b - d) / c


def convert_value(x, from_unit, to_unit, dimension):
    """Convert one number between two unit symbols of a dimension (helper for users and tests)."""
    a, b = unit_row(from_unit, dimension), unit_row(to_unit, dimension)
    if a is None or b is None or a["base"] != b["base"]:
        raise ConversionError(f"cannot convert {from_unit!r} to {to_unit!r} as {dimension}")
    if factor_offset(a, b) == (1.0, 0.0):
        return x
    return apply_linear(x, [a["factor"], a["offset"], b["factor"], b["offset"]])


def units_of(dimension, base=None, ix=None):
    """Unit symbols a variable of this dimension can be converted to."""
    ix = ix or index()
    return [u["symbol"] for u in ix.units if u["dimension"] == dimension and (base is None or u["base"] == base)]


# ------------------------------------------------------------------ number formatting (same as JavaScript String(x))
def round_sig(x, digits):
    """Round to `digits` significant digits, half away from zero on the exact binary value (= JS toPrecision)."""
    if x == 0 or x != x or x in (float("inf"), float("-inf")):
        return x
    d = Decimal(x)
    q = Decimal(1).scaleb(d.adjusted() - digits + 1)
    return float(d.quantize(q, rounding=ROUND_HALF_UP))


def fmt_number(x, digits=None):
    """Shortest text that reads back as the same double, formatted like JavaScript's Number.prototype.toString."""
    if digits:
        x = round_sig(x, digits)
    if x != x:
        return "NaN"
    if x in (float("inf"), float("-inf")):
        return "Infinity" if x > 0 else "-Infinity"
    if x == 0:
        return "0"
    r = repr(x)
    sign = "-" if r.startswith("-") else ""
    r = r.lstrip("-")
    if "e" in r:
        mant, exp = r.split("e")
        exp = int(exp)
    else:
        mant, exp = r, 0
    if "." in mant:
        ip, fp = mant.split(".")
    else:
        ip, fp = mant, ""
    digits_s = (ip + fp).lstrip("0")
    lead = len(ip + fp) - len((ip + fp).lstrip("0"))
    n = len(ip) - lead + exp                       # value = 0.DIGITS x 10^n
    digits_s = digits_s.rstrip("0") or "0"
    k = len(digits_s)
    if k <= n <= 21:
        out = digits_s + "0" * (n - k)
    elif 0 < n <= 21:
        out = digits_s[:n] + "." + digits_s[n:]
    elif -6 < n <= 0:
        out = "0." + "0" * (-n) + digits_s
    else:
        e = n - 1
        out = digits_s[0] + ("." + digits_s[1:] if k > 1 else "") + "e" + ("+" if e >= 0 else "-") + str(abs(e))
    return sign + out


_NUM = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


def parse_number(tok):
    """Float for a strictly numeric token, else None (same rule as the JS)."""
    tok = tok.strip()
    return float(tok) if _NUM.match(tok) else None


# ------------------------------------------------------------------ mapping
def _compat(a, b):
    return a == b or (a in RATIO_DIMS and b in RATIO_DIMS)


def lookup_key(name):
    s = str(name if name is not None else "").strip()
    s = re.sub(r":\d+$", "", s)
    return s.upper()


def _strip_unit_suffix(name):
    return re.sub(r"\s*[\(\[][^()\[\]]*[\)\]]\s*$", "", str(name)).strip()


# A context rule whose variable is UNASSIGNED keeps the mnemonic out of every variable (no fallback to the name).
UNASSIGNED = "-"
# A variable of a difference dimension takes a declared unit of the paired absolute dimension by scale only (no offset):
# a temperature difference of 1 degF is 5/9 degC, whatever the offset of the absolute scales.
DIFFERENCE_DIMS = {"temperature_difference": "temperature"}


def _norm_dataset(d):
    return str(d or "").strip().lower().replace("_", "-")


def dataset_matches(want, dataset):
    """True when a rule's dataset condition holds: empty = any (also no dataset); '*' = any declared dataset; otherwise
    the dataset id equals one of the values or starts with it and a hyphen (kgs matches kgs, kgs-tables, kgs_dst)."""
    if not want:
        return True
    ds = _norm_dataset(dataset)
    if not ds:
        return False
    for w in want:
        w = _norm_dataset(w)
        if w == "*" or ds == w or ds.startswith(w + "-"):
            return True
    return False


def context_variable(key, dims, source_format, ix=None, dataset=None):
    """(variable, rule) from the context table for a mnemonic, the candidate dimensions of its declared unit (empty =
    no unit or unknown), the source format and the dataset id; (None, None) when no rule matches. The variable can be
    UNASSIGNED."""
    ix = ix or index()
    fmt = (source_format or "").upper()
    for r in ix.t["context"].get(key, []):
        want = r["when_unit_dimension"]
        if want and not any((not dims and w == "unknown") or (dims and any(_compat(d, w) for d in dims)) for w in want):
            continue
        src = r["when_source"]
        if src and not any((w == "log" and fmt in LOG_FORMATS) or (w == "table" and fmt not in LOG_FORMATS) or w == fmt
                           for w in src):
            continue
        if not dataset_matches(r.get("when_dataset") or [], dataset):
            continue
        return r["variable"], r
    return None, None


def map_channel(name, unit, source_format, ix=None, dataset=None):
    """(variable or None, how, detail, warnings) for one channel."""
    ix = ix or index()
    t = ix.t
    raw = str(name if name is not None else "").strip()
    key = lookup_key(raw)
    if raw in t["variables"]:
        return raw, "standard_name", None, []
    q = _QUALIFIED_NAME.match(raw)
    if q and q.group(1) in t["variables"]:
        return q.group(1), "standard_name", None, []    # an OWD output name with its statistic (hookload_max)
    warnings = []
    if key in t["context"]:
        r = resolve_unit(unit, None, ix)
        var, rule = context_variable(key, r["dimensions"] if r["status"] != "unknown" else [], source_format, ix, dataset)
        if var == UNASSIGNED:
            return None, "context_unassigned", {"when_unit_dimension": rule["when_unit_dimension"],
                                                "when_source": rule["when_source"], "when_dataset": rule["when_dataset"],
                                                "note": rule["note"]}, \
                [f"a context rule keeps {key} out of every variable here ({rule['note']}): kept with its original name, "
                 "values unchanged"]
        if var:
            if var in t["variables"]:
                return var, "context_rule", {"when_unit_dimension": rule["when_unit_dimension"],
                                             "when_source": rule["when_source"], "when_dataset": rule["when_dataset"],
                                             "note": rule["note"]}, []
            warnings.append(f"context rule points to '{var}', which is not a variable of the dictionary")
    cands = ix.mnem.get(key, [])
    if len(cands) == 1:
        return cands[0], "dictionary", None, warnings
    if len(cands) > 1:
        warnings.append(f"{key} is listed under several variables ({', '.join(cands)}) and no context rule decides "
                        "(pass the source format, or the unit); kept with its original name")
        return None, "ambiguous", {"candidates": cands}, warnings
    a = t["aliases"].get(_strip_unit_suffix(raw).lower())
    if a and a in t["variables"]:
        return a, "channel_alias", None, warnings
    return None, None, None, warnings


# ------------------------------------------------------------------ statistic of a channel
_NAME_TOKENS = re.compile(r"[^A-Z0-9]+")


def channel_statistic(name, description, variable, ix=None):
    """(statistic, window, evidence, warnings) of a channel labelled as `variable`, from explicit evidence only.

    statistic: unspecified | inst | mean | max | min | std | median | rms (None when there is no variable).
    window: e.g. "5 ft", "time", "depth" when the description states it, else None (only for a qualified statistic).
    evidence: name | description | name+description | name_over_description (the name has a statistic word and the
    description says another one: the name is kept and a warning is added) | conflict (several statistics in the name,
    or in a description when the name has none: unspecified) | None. Rules: channel_statistics.tsv."""
    ix = ix or index()
    t = ix.t
    if not variable or variable not in t["variables"]:
        return None, None, None, []
    dim = t["variables"][variable]["dimension"]
    rules = [r for r in ix.stat_rules if dim not in r["not_dimension"]]
    key = lookup_key(_strip_unit_suffix(str(name if name is not None else "")))
    by_name, by_desc = [], []
    toks = [x for x in _NAME_TOKENS.split(key) if x]
    for r in rules:
        s = r["statistic"]
        if r["kind"] == "name_token" and len(toks) > 1 and r["pattern"] in toks and s not in by_name:
            by_name.append(s)
        elif r["kind"] == "name_suffix" and key.endswith(r["pattern"]) and len(key) > len(r["pattern"]):
            stem = key[:-len(r["pattern"])].rstrip("_-. ")
            if stem and (stem == variable.upper() or variable in ix.mnem.get(stem, [])) and s not in by_name:
                by_name.append(s)
    desc = str(description or "")
    window = None
    if desc.strip():
        for r in rules:
            if r["kind"] == "window" and window is None:
                m = r["rx"].search(desc)
                if m:
                    window = r["window"].replace("{1}", (m.group(1) or "") if m.groups() else "")
        d = desc
        for r in rules:
            if r["kind"] == "exclude":
                d = r["rx"].sub(" ", d)
        for r in rules:
            if r["kind"] == "description" and r["rx"].search(d) and r["statistic"] not in by_desc:
                by_desc.append(r["statistic"])
    warnings = []
    if len(by_name) > 1 or (not by_name and len(by_desc) > 1):
        return "unspecified", None, "conflict", [
            f"statistic unclear: the name says {', '.join(by_name) or 'nothing'} and the description says "
            f"{', '.join(by_desc) or 'nothing'}; written without a statistic qualifier"]
    if by_name:
        st = by_name[0]
        if not by_desc:
            ev = "name"
        elif by_desc == [st]:
            ev = "name+description"
        else:
            # a statistic word in the name (TORQUE_MAX) is kept over a description copied from a sibling channel
            # ("Surface Torque Average"); the disagreement is reported
            ev = "name_over_description"
            warnings.append(f"the name says {st} but the description says {', '.join(by_desc)}: written as {st} "
                            "(statistic word in the name); check the values")
    elif by_desc:
        st, ev = by_desc[0], "description"
    else:
        return "unspecified", None, None, []
    return st, (window if st in QUALIFIED_STATISTICS else None), ev, warnings


def dictionary_statistic(mnemonic, variable, descriptions=(), ix=None):
    """(statistics, windows) of a mnemonic in the dictionary, over the descriptions recorded for it: one value when they
    all agree (HKLD_MIN -> min; HKLX "Maximum Hookload" -> max), several joined by | when each file's own description
    decides (HKLD -> mean|unspecified: "Average Hookload" in Volve, "Hookload" elsewhere). Empty without a variable."""
    descs = [d for d in descriptions if str(d or "").strip()] or [""]
    sts, wins = [], []
    for d in descs:
        st, w, _, _ = channel_statistic(mnemonic, d, variable, ix)
        if st and st not in sts:
            sts.append(st)
        if w and w not in wins:
            wins.append(w)
    return "|".join(sts), "|".join(wins)


def naming_statistics(pairs, ix=None):
    """Statistic that goes into the output name for each (variable, statistic) of one file. Variables of the families
    listed as qualify_family in channel_statistics.tsv (drilling, mud_gas) always carry it (hookload_max). Other
    families (logs, petrophysics...) keep the plain name and the statistic only in the provenance (GRMA "Gamma Ray,
    Average" is gr, statistic mean), unless two different qualified statistics of the same variable coexist in the
    file: then those channels carry it (caliper_max, caliper_min). Decision of Daniel, 7 Nov 2026."""
    t = (ix or index()).t
    fams = {r["pattern"] for r in t.get("statistics", []) if r["kind"] == "qualify_family"}
    seen = {}
    for v, st in pairs:
        if v and st in QUALIFIED_STATISTICS:
            lst = seen.setdefault(v, [])
            if st not in lst:
                lst.append(st)
    out = []
    for v, st in pairs:
        if not v or st not in QUALIFIED_STATISTICS:
            out.append(None)
        elif t["variables"].get(v, {}).get("family") in fams or len(seen[v]) > 1:
            out.append(st)
        else:
            out.append(None)
    return out


def qualified_name(variable, statistic):
    """Output name of a variable with its statistic: hookload, hookload_mean, hookload_max..."""
    return f"{variable}_{statistic}" if statistic in QUALIFIED_STATISTICS else variable


def parse_output_name(name, ix=None):
    """(variable, statistic) of an OWD output column name (hookload -> (hookload, unspecified), hookload_max_2 ->
    (hookload, max)); (None, None) when it is not an OWD variable name. Outputs written before 7 Nov 2026 have no
    qualifier: their statistic is only in the provenance (original_name and description)."""
    t = (ix or index()).t
    n = re.sub(r"_\d+$", "", str(name or ""))
    if n in t["variables"]:
        return n, "unspecified"
    q = _QUALIFIED_NAME.match(n)
    if q and q.group(1) in t["variables"]:
        return q.group(1), q.group(2)
    return None, None


# ------------------------------------------------------------------ naming schemes
NAMING = {}


def register_naming(name, mapping):
    """Add a naming scheme: a dict {variable: name} or a callable(variable, original_name) -> name. Unlabelled
    channels always keep their original name."""
    if name in ("owd", "original"):
        raise ConversionError("owd and original are built in")
    NAMING[name] = mapping


def _scheme_name(scheme, var, original, statistic=None):
    """Output name. With a statistic qualifier (mean, max, min...) the scheme's name of the variable gets the suffix
    _<statistic>; a dict scheme can name the qualified variable itself ({"hookload_max": "HKL_MAX"})."""
    if var is None or scheme == "original":
        return original
    q = qualified_name(var, statistic)
    if scheme == "owd":
        return q
    m = NAMING.get(scheme, scheme) if isinstance(scheme, str) else scheme
    if isinstance(m, str):
        raise ConversionError(f"unknown naming scheme {scheme!r}; use owd, original, a dict or register_naming()")
    if callable(m):
        n = m(var, original)
        return (n + q[len(var):]) if n else original
    if q != var and q in m:
        return m[q]
    return m.get(var, var) + q[len(var):]


def _las_safe(s, fallback):
    s = re.sub(r"[\s.:~#]+", "_", str(s or "")).strip("_")
    return s or fallback


def _las_unit(s):
    return re.sub(r"\s+", "_", str(s or "").strip())


# ------------------------------------------------------------------ targets
def target_unit(var, units="si", ix=None):
    """Target unit symbol for a variable: units = 'si' (OWD standard), 'field' (oilfield) or a dict {variable: unit}
    (key '_default' = 'si' or 'field' for the rest)."""
    ix = ix or index()
    v = ix.t["variables"][var]
    default = units if isinstance(units, str) else "si"
    if isinstance(units, dict):
        default = units.get("_default", "si")
        if var in units:
            row = unit_row(units[var], v["dimension"], ix)
            std = unit_row(v["unit"], v["dimension"], ix)
            if row is None or std is None or row["base"] != std["base"]:
                raise ConversionError(f"{var}: cannot convert to {units[var]!r} (a {v['dimension']} variable; units: "
                                      f"{', '.join(units_of(v['dimension'], std['base'] if std else None, ix))})")
            return row["symbol"]
    if default == "si":
        return v["unit"]
    if default == "field":
        p = ix.t["presets"]["field"]
        return p["variable"].get(var) or p["dimension"].get(v["dimension"]) or v["unit"]
    raise ConversionError(f"units must be 'si', 'field' or a dict, not {units!r}")


def units_label(units):
    if isinstance(units, dict):
        return "custom" if units.get("_default", "si") == "si" else "custom:" + units["_default"]
    return units


def _rule_for(key, var, unit, res):
    ix = index()
    for r in ix.t["rules"]:
        if r["mnemonic"] != key or r["variable"] != var:
            continue
        for w in r["when_unit"]:
            if (w == "none" and res["status"] == "none") or (w == "dimensionless" and "dimensionless" in res["dimensions"]) \
                    or (w == (unit or "").strip()):
                return r
    return None


def plan_channels(channels, names="owd", units="si", source_format="table", output=None, ix=None, dataset=None):
    """One plan per channel: what it maps to, its output name and unit, factor and offset, rule and warnings.

    channels: list of dicts {name, unit, description}. output: 'las' makes names and units LAS-safe. dataset: the
    catalogue id of the source, for the context rules that depend on it (None = unknown)."""
    ix = ix or index()
    t = ix.t
    if not isinstance(names, (dict,)) and not callable(names) and names not in ("owd", "original") and names not in NAMING:
        raise ConversionError(f"names must be 'owd', 'original', a registered scheme, a dict or a callable, not '{names}'")
    plans = []
    for ch in channels:
        name = str(ch.get("name") if ch.get("name") is not None else "")
        unit = str(ch.get("unit") or "").strip()
        key = lookup_key(name)
        p = {"original_name": name, "original_unit": unit, "description": str(ch.get("description") or ""),
             "variable": None, "candidate_variable": None, "mapped_by": None, "context_rule": None, "status": "unmapped",
             "name": name, "unit": unit, "factor": 1.0, "offset": 0.0, "base_factors": None, "converted": False, "unit_rule": None,
             "unit_note": "", "statistic": None, "window": None, "statistic_evidence": None, "warnings": []}
        var, how, detail, w = map_channel(name, unit, source_format, ix, dataset)
        p["warnings"] += w
        if how == "ambiguous":
            p["status"] = "ambiguous_mnemonic"
        if how == "context_unassigned":
            p["mapped_by"], p["context_rule"] = how, detail
        if var is None and how not in ("ambiguous", "context_unassigned"):
            p["warnings"].append("not in the dictionary: kept with its original name, values unchanged")
        if var is not None:
            v = t["variables"][var]
            dim = v["dimension"]
            p["candidate_variable"], p["mapped_by"] = var, how
            if how == "context_rule":
                p["context_rule"] = detail
            res = resolve_unit(unit, dim, ix)
            rule = _rule_for(key, var, unit, res)
            if rule and rule["action"] == "assume_unit":
                res = resolve_unit(rule["unit"], dim, ix)
                p["unit_rule"] = {"action": rule["action"], "unit": rule["unit"], "note": rule["note"], "source": rule["source"]}
            tgt_sym = target_unit(var, units, ix)
            diff_row = None
            if res["status"] == "mismatch" and DIFFERENCE_DIMS.get(dim) in res["dimensions"]:
                r2 = resolve_unit(rule["unit"] if p["unit_rule"] else unit, DIFFERENCE_DIMS[dim], ix)
                tgt0 = unit_row(tgt_sym, dim, ix)
                if r2["status"] == "ok" and tgt0 is not None:
                    a = ix.units[r2["unit"]]
                    diff_row = dict(a, offset=0.0, base=tgt0["base"], dimension=dim,
                                    note=(a["note"] + "; " if a["note"] else "") + "read as a difference: scale only, no offset")
                    res = {"status": "ok", "unit": None, "dimensions": [dim], "match": r2["match"]}
                    p["warnings"].append(f"unit '{unit}' read as a {dim.replace('_', ' ')} in {a['symbol']}: scale only, "
                                         "no offset")
            if res["status"] == "ok":
                src = diff_row or ix.units[res["unit"]]
                tgt = unit_row(tgt_sym, dim, ix)
                if tgt is None or src["base"] != tgt["base"]:
                    p["status"] = "kept_incompatible_unit"
                    p["warnings"].append(f"unit '{unit}' ({src['base']}) cannot be converted to '{tgt_sym}': values "
                                         "kept as they are, original name kept")
                else:
                    f, o = factor_offset(src, tgt)
                    p["base_factors"] = [src["factor"], src["offset"], tgt["factor"], tgt["offset"]]
                    p.update(variable=var, factor=f, offset=o, converted=(f != 1.0 or o != 0.0),
                             unit="" if tgt["symbol"] == "_" else tgt["symbol"], unit_note=src["note"],
                             status="converted" if (f != 1.0 or o != 0.0) else "renamed")
                    if res["match"] == "case-insensitive":
                        p["warnings"].append(f"unit '{unit}' read as {src['symbol']} (case-insensitive match)")
            elif res["status"] == "none" and (dim == "code" or v["unit"] == "_"):
                p.update(variable=var, unit="", status="renamed")
            elif res["status"] == "none":
                p["status"] = "kept_no_unit"
                p["warnings"].append(f"no unit declared: a unit is needed to label it as {var} ({v['unit']}); values "
                                     "kept as they are, original name kept")
            elif res["status"] == "unknown":
                p["status"] = "kept_unknown_unit"
                p["warnings"].append(f"unit '{unit}' is not in the unit table (never guessed): values kept as they are, "
                                     f"original name kept (it looks like {var})")
            elif res["status"] == "ambiguous":
                p["status"] = "kept_ambiguous_unit"
                p["warnings"].append(f"unit '{unit}' has several readings in {dim}: values kept as they are, original name kept")
            else:
                dims = res["dimensions"]
                msg = (f"declared unit '{unit}' is {' or '.join(dims)} but {var} is {dim}: the unit looks mislabelled. "
                       "No documented rule covers it, so values are kept as they are and the channel keeps its name")
                if {dim, *dims} >= {"resistivity", "conductivity"}:
                    msg += (". Resistivity and conductivity are reciprocal (mS/m = 1000 / ohm.m); OWD never inverts "
                            "values without a documented rule")
                p["status"] = "kept_unit_mismatch"
                p["warnings"].append(msg)
        if p["variable"]:
            st, win, ev, sw = channel_statistic(name, p["description"], p["variable"], ix)
            p.update(statistic=st, window=win, statistic_evidence=ev)
            p["warnings"] += sw
        if key in t["conflicts"]:
            p["warnings"].append(f"the dictionary records an open conflict for {key} ({', '.join(t['conflicts'][key])}): "
                                 "check the values")
        plans.append(p)
    # output names: variable (+ _statistic); numeric suffixes only for the same variable and statistic
    name_stats = naming_statistics([(p["variable"], p["statistic"]) for p in plans], ix)
    seen = set()
    for i, p in enumerate(plans):
        n = _scheme_name(names, p["variable"], p["original_name"], name_stats[i])
        if output == "las":
            n = _las_safe(n, f"CURVE{i + 1}")
            p["unit"] = _las_unit(p["unit"])
        base, k = n, 2
        while n in seen:
            n = f"{base}_{k}"
            k += 1
        if n != base:
            p["warnings"].append(f"output name '{base}' already used: written as '{n}'")
        seen.add(n)
        p["name"] = n
    return plans


# ------------------------------------------------------------------ citation and provenance
def permalink(names="owd", units="si", to="csv", version=None, digits=DEFAULT_DIGITS, csv_header="unit"):
    q = urllib.parse.quote
    s = lambda x: q(str(x), safe="-_.!~*'()")
    nm = names if names in ("owd", "original") else "custom"
    u = units_label(units)
    parts = [f"names={s(nm)}", f"units={s('field' if u == 'custom:field' else ('si' if u == 'custom' else u))}"]
    if isinstance(units, dict):
        cu = ",".join(f"{k}:{units[k]}" for k in sorted(units) if k != "_default")
        if cu:
            parts.append(f"u={s(cu)}")
    parts.append(f"to={s(to)}")
    if digits != DEFAULT_DIGITS:
        parts.append(f"d={int(digits or 0)}")
    if to == "csv" and csv_header != "unit":
        parts.append(f"h={s(csv_header)}")
    parts.append(f"v={s(version or index().version)}")
    return f"{SITE}/convert/?" + "&".join(parts)


def owd_citation(year):
    return f"Processed with Open Well Data ({AUTHOR}, {year}), {SITE}"


def owd_bibtex(year, version, link):
    return ("@misc{openwelldata" + str(year) + ",\n  author = {Delgado-Uriarte, Daniel},\n"
            "  title = {Open Well Data: public subsurface data for oil, gas and CCS, with standard names and units},\n"
            f"  year = {{{year}}},\n  howpublished = {{\\url{{{SITE}}}}},\n"
            f"  note = {{Dictionary version {version}. Conversion settings: \\url{{{link}}}}}\n}}")


def source_info(dataset=None, citation=None, licence=None, url=None):
    """Citation and licence of the source: from the registry when the dataset is known, else as stated by the source."""
    out = {"dataset": dataset, "name": None, "citation": citation or AS_STATED, "license": licence or AS_STATED,
           "url": url}
    if dataset:
        try:
            from .registry import DATASETS
            d = DATASETS.get(dataset)
        except ImportError:
            d = None
        if d:
            out.update(name=d["name"], citation=citation or d["citation"], license=licence or d["license"],
                       url=url or d["url"])
    return out


def _now(now=None):
    if now:
        return now
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def provenance(plans, *, names="owd", units="si", to="csv", source=None, input_info=None, now=None, digits=DEFAULT_DIGITS,
               csv_header="unit", source_format="table", extra_warnings=(), ix=None):
    ix = ix or index()
    meta = ix.t["meta"]
    when = _now(now)
    year = when[:4]
    link = permalink(names, units, to, meta["dictionary_version"], digits, csv_header)
    src = source or source_info()
    text = owd_citation(year)
    channels = []
    for p in plans:
        channels.append({k: p[k] for k in ("original_name", "original_unit", "name", "unit", "variable",
                                           "candidate_variable", "mapped_by", "context_rule", "status", "factor",
                                           "offset", "base_factors", "converted", "unit_rule", "unit_note", "warnings", "description",
                                           "statistic", "window", "statistic_evidence")})
    nw = sum(len(p["warnings"]) for p in plans) + len(extra_warnings)
    return {
        "open_well_data": {"engine": "owd.convert", "engine_version": ENGINE_VERSION,
                           "dictionary_version": meta["dictionary_version"], "dictionary_commit": meta["dictionary_commit"],
                           "dictionary_date": meta["dictionary_date"],
                           "settings": {"names": names if isinstance(names, str) else "custom", "units": units_label(units),
                                        "custom_units": {k: v for k, v in units.items() if k != "_default"} if isinstance(units, dict) else {},
                                        "to": to, "digits": digits, "csv_header": csv_header,
                                        "source_format": source_format},
                           "permalink": link},
        "generated_utc": when,
        "input": input_info or {},
        "source": src,
        "summary": {"channels": len(plans), "labelled": sum(1 for p in plans if p["variable"]),
                    "converted": sum(1 for p in plans if p["converted"]),
                    "unchanged": sum(1 for p in plans if not p["converted"]),
                    "not_labelled": [p["original_name"] for p in plans if not p["variable"]], "warnings": nw},
        "warnings": list(extra_warnings),
        "channels": channels,
        "how_to_cite": {"open_well_data": text,
                        "full": f"{text}. Dictionary version {meta['dictionary_version']}; conversion settings: {link}",
                        "bibtex": owd_bibtex(year, meta["dictionary_version"], link),
                        "source": src["citation"], "source_license": src["license"]},
        "license_note": LICENCE_NOTE,
    }


def citation_lines(prov):
    """Short text lines with the citation and provenance (LAS ~Other, CSV comment header)."""
    c, s = prov["how_to_cite"], prov["source"]
    lines = [c["open_well_data"],
             f"Dictionary version {prov['open_well_data']['dictionary_version']}; settings: {prov['open_well_data']['permalink']}",
             f"Source: {s['citation']}. Licence: {s['license']}.",
             prov["license_note"]]
    return lines


def channel_line(p):
    def nu(n, u):
        return n + (f" [{u}]" if u else "")
    s = f"{nu(p['original_name'], p['original_unit'])} -> {nu(p['name'], p['unit'])}"
    if p["converted"]:
        s += f" x{fmt_number(p['factor'])}" + (f" {'+' if p['offset'] >= 0 else '-'}{fmt_number(abs(p['offset']))}" if p["offset"] else "")
    s += f"; {p['status']}"
    if p["mapped_by"]:
        s += f" ({p['mapped_by']})"
    if p["unit_rule"]:
        s += f"; rule: {p['unit_rule']['note']}"
    if p["unit_note"]:
        s += f"; unit read as: {p['unit_note']}"
    return s


# ------------------------------------------------------------------ parsing: LAS 2.0 and CSV
def decode(data):
    """Bytes -> text: UTF-8 (BOM removed), else Windows-1252 (as browsers decode latin-1), else Latin-1."""
    if isinstance(data, str):
        return data.lstrip("\ufeff")
    try:
        return data.decode("utf-8").lstrip("\ufeff")
    except UnicodeDecodeError:
        try:
            return data.decode("cp1252")
        except UnicodeDecodeError:
            return data.decode("latin-1")


def _splitlines(text):
    return re.split(r"\r\n|\n|\r", text)


def parse_las_line(line):
    """LAS 2.0 header line -> (mnemonic, unit, value, description) or None. The unit starts right after the first dot
    and ends at the first space; the description follows the last colon."""
    dot = line.find(".")
    if dot < 0:
        return None
    mnem = line[:dot].strip()
    rest = line[dot + 1:]
    m = re.match(r"\S*", rest)
    unit = m.group(0)
    rest = rest[len(unit):]
    c = rest.rfind(":")
    value, descr = (rest.strip(), "") if c < 0 else (rest[:c].strip(), rest[c + 1:].strip())
    return mnem, unit, value, descr


def parse_las(text):
    """LAS 1.2/2.0 (wrapped or not) -> table dict: channels, columns of raw tokens, null, header sections, warnings."""
    sec, items, other, data = None, {"V": [], "W": [], "C": [], "P": []}, [], []
    for line in _splitlines(text):
        s = line.strip()
        if s.startswith("~"):
            sec = s[1:2].upper()
            continue
        if sec == "A":
            if s and not s.startswith("#"):
                data.append(s)
            continue
        if sec == "O":
            if s and not s.startswith("#"):
                other.append(line.rstrip())
            continue
        if not s or s.startswith("#") or sec not in items:
            continue
        it = parse_las_line(line)
        if it:
            items[sec].append(list(it))
    vers = next((i[2] for i in items["V"] if i[0].upper() == "VERS"), "")
    vn = parse_number(vers.split()[0]) if vers.split() else None
    if vn is not None and vn >= 3:
        raise ConversionError("LAS 3.0 is not supported yet; LAS 1.2 and 2.0 are")
    if not items["C"]:
        raise ConversionError("no ~Curve section: not a LAS file")
    wrap = next((i[2] for i in items["V"] if i[0].upper() == "WRAP"), "NO").strip().upper().startswith("Y")
    null = next((i[2] for i in items["W"] if i[0].upper() == "NULL"), None)
    n = len(items["C"])
    rows, warnings = [], []
    short = long_ = 0
    if wrap:
        toks = [t for ln in data for t in ln.split()]
        for k in range(0, len(toks), n):
            r = toks[k:k + n]
            if len(r) < n:
                short += 1
                r += [""] * (n - len(r))
            rows.append(r)
    else:
        for ln in data:
            r = ln.split()
            if len(r) < n:
                short += 1
                r += [""] * (n - len(r))
            elif len(r) > n:
                long_ += 1
                r = r[:n]
            rows.append(r)
    if short:
        warnings.append(f"{short} data rows had fewer values than curves: the missing values are written as null")
    if long_:
        warnings.append(f"{long_} data rows had more values than curves: the extra values were left out")
    cols = [[r[j] for r in rows] for j in range(n)]
    chans = [{"name": c[0], "unit": "" if is_no_unit(c[1]) else c[1], "description": c[3]} for c in items["C"]]
    return {"format": "LAS", "version": vers, "channels": chans, "columns": cols, "null": null, "well": items["W"],
            "params": items["P"], "other": other, "warnings": warnings, "rows": len(rows)}


def _csv_rows(text, delim):
    rows, row, field, i, q, n = [], [], [], 0, False, len(text)
    while i < n:
        c = text[i]
        if q:
            if c == '"':
                if i + 1 < n and text[i + 1] == '"':
                    field.append('"')
                    i += 1
                else:
                    q = False
            else:
                field.append(c)
        elif c == '"':
            q = True
        elif c == delim:
            row.append("".join(field))
            field = []
        elif c == "\r" or c == "\n":
            row.append("".join(field))
            field = []
            rows.append(row)
            row = []
            if c == "\r" and i + 1 < n and text[i + 1] == "\n":
                i += 1
        else:
            field.append(c)
        i += 1
    if field or row:
        row.append("".join(field))
        rows.append(row)
    return rows


_HDR_UNIT = re.compile(r"^(.*?)\s*[\(\[]([^()\[\]]*)[\)\]]\s*$")


def _cell_unit(cell, ix):
    """Unit written in a units-row cell: the part in brackets if it is a known unit, else the whole cell."""
    c = cell.strip()
    m = _HDR_UNIT.match(c)
    if m and resolve_unit(m.group(2), None, ix)["status"] in ("ok", "ambiguous"):
        return m.group(2).strip()
    return c


def parse_csv(text, null=None, ix=None):
    """CSV with a header row ("Name", "Name (unit)" or "Name [unit]"), an optional units row, leading '#' comments."""
    ix = ix or index()
    lines = _splitlines(text)
    k = 0
    while k < len(lines) and lines[k].lstrip().startswith("#"):
        k += 1
    first = lines[k] if k < len(lines) else ""
    counts = {d: _csv_rows(first, d)[0].__len__() - 1 if first else 0 for d in (",", ";", "\t")}
    delim = max((",", ";", "\t"), key=lambda d: counts[d]) if any(counts.values()) else ","
    body = "\n".join(lines[k:])
    rows = _csv_rows(body, delim)
    while rows and all(c.strip() == "" for c in rows[-1]):
        rows.pop()
    if not rows:
        raise ConversionError("empty CSV")
    header = rows[0]
    chans = []
    for c in header:
        m = _HDR_UNIT.match(c.strip())
        name, unit = (m.group(1).strip(), m.group(2).strip()) if m else (c.strip(), "")
        chans.append({"name": name, "unit": "" if is_no_unit(unit) else unit, "description": c.strip()})
    start, units_row = 1, False
    if len(rows) > 1:
        r2 = [c for c in rows[1] if c.strip()]
        if r2 and not any(parse_number(c) is not None for c in r2):
            known = sum(1 for c in r2 if resolve_unit(_cell_unit(c, ix), None, ix)["status"] in ("ok", "ambiguous"))
            if known >= max(1, (len(r2) + 1) // 2):
                units_row, start = True, 2
                for j, ch in enumerate(chans):
                    if not ch["unit"] and j < len(rows[1]):
                        u = _cell_unit(rows[1][j], ix)
                        ch["unit"] = "" if is_no_unit(u) else u
    n = len(chans)
    data, bad = [], 0
    for r in rows[start:]:
        if len(r) != n:
            bad += 1
            r = (r + [""] * n)[:n]
        data.append(r)
    warnings = [f"{bad} rows had a different number of fields than the header: padded with nulls or cut"] if bad else []
    cols = [[r[j] for r in data] for j in range(n)]
    return {"format": "CSV", "version": "", "channels": chans, "columns": cols, "null": null, "well": [], "params": [],
            "other": [], "warnings": warnings, "rows": len(data), "units_row": units_row, "delimiter": delim}


# ------------------------------------------------------------------ applying a plan to columns of tokens
def convert_columns(tbl, plans, digits=None, counts=None, las=False):
    """Return (output columns with None for nulls, warnings). Unconverted values are copied verbatim.
    counts: a dict to accumulate the per-channel counts in (streaming); the warnings are then added by
    add_count_warnings() once at the end instead of here. las: text values with spaces get '_' (LAS has no quoting)."""
    null = tbl.get("null")
    null_num = parse_number(null) if null is not None else None
    out = []
    for j, (col, p) in enumerate(zip(tbl["columns"], plans)):
        conv, base = p["converted"], p["base_factors"]
        res, ntext, n999, nsp = [], 0, 0, 0
        for tok in col:
            s = tok.strip()
            if s == "":
                res.append(None)
                continue
            x = parse_number(s)
            if null is not None and ((null_num is not None and x is not None and x == null_num) or s == null.strip()):
                res.append(None)
                continue
            if las and x is None and re.search(r"\s", s):
                nsp += 1
                s = re.sub(r"\s+", "_", s)
            if not conv:
                res.append(s)
                continue
            if x is None:
                ntext += 1
                res.append(s)
                continue
            if x == -999.25 and null_num is None:
                n999 += 1
            res.append(fmt_number(apply_linear(x, base), digits))
        if counts is None:
            add_count_warnings([p], {0: (ntext, n999, nsp)})
        else:
            a, b, c = counts.get(j, (0, 0, 0))
            counts[j] = (a + ntext, b + n999, c + nsp)
        out.append(res)
    return out, []


def add_count_warnings(plans, counts):
    for j, p in enumerate(plans):
        ntext, n999, nsp = counts.get(j, (0, 0, 0))
        if ntext:
            p["warnings"].append(f"{p['original_name']}: {ntext} non-numeric values copied as they are (not converted)")
        if n999:
            p["warnings"].append(f"{p['original_name']}: the value -999.25 appears {n999} times and was converted as a "
                                 "number; if it marks missing data, declare it as the null value")
        if nsp:
            p["warnings"].append(f"{p['original_name']}: {nsp} text values contained spaces; written with '_' because "
                                 "LAS has no quoting")


# ------------------------------------------------------------------ writers
def _csv_cell(s):
    if s is None:
        return ""
    if any(c in s for c in ',"\n\r') or s != s.strip():
        return '"' + s.replace('"', '""') + '"'
    return s


def write_csv(plans, cols, prov, csv_header="unit", comments=False):
    lines = []
    if comments:
        lines += ["# " + ln for ln in citation_lines(prov)]
    hdr = [p["name"] if (csv_header == "plain" or not p["unit"]) else f"{p['name']} [{p['unit']}]" for p in plans]
    lines.append(",".join(_csv_cell(h) for h in hdr))
    n = len(cols[0]) if cols else 0
    for i in range(n):
        lines.append(",".join(_csv_cell(c[i]) for c in cols))
    return "\n".join(lines) + "\n"


def _las_items(items):
    if not items:
        return []
    left = [f"{m}.{u}" for m, u, _, _ in items]
    w = max(len(x) for x in left)
    vw = max(len(v) for _, _, v, _ in items)
    return [(" " + left[i].ljust(w) + " " + items[i][2].ljust(vw) + " : " + items[i][3]).rstrip() for i in range(len(items))]


WELL_DEFAULT = [("COMP", "COMPANY"), ("WELL", "WELL"), ("FLD", "FIELD"), ("LOC", "LOCATION"), ("SRVC", "SERVICE COMPANY"),
                ("DATE", "LOG DATE"), ("UWI", "UNIQUE WELL ID")]


def write_las(tbl, plans, cols, prov, digits=None, step=None):
    null_out = (tbl.get("null") or "").strip() or "-999.25"
    p0 = plans[0]
    iu = p0["unit"]
    col0 = cols[0]
    strt = next((v for v in col0 if v is not None), "")
    stop = next((v for v in reversed(col0) if v is not None), "")
    src_step = next((i[2] for i in tbl["well"] if i[0].upper() == "STEP"), None) if tbl["format"] == "LAS" else None
    if step is not None:
        pass
    elif src_step is not None and not p0["converted"]:
        step = src_step
    elif src_step is not None and parse_number(src_step) is not None:
        a, _, c, _ = p0["base_factors"]
        step = fmt_number(parse_number(src_step) * a / c, digits)
    else:
        nums = [parse_number(v) for v in col0 if v is not None]
        nums = [x for x in nums if x is not None]
        step = "0"
        if len(nums) > 1:
            d0 = nums[1] - nums[0]
            if d0 != 0 and all(abs((nums[i] - nums[i - 1]) - d0) <= 1e-9 * abs(d0) for i in range(2, len(nums))):
                step = fmt_number(d0, 10)
    fixed = {"STRT": (iu, strt, "START DEPTH"), "STOP": (iu, stop, "STOP DEPTH"), "STEP": (iu, step, "STEP"),
             "NULL": ("", null_out, "NULL VALUE")}
    well = []
    for k in ("STRT", "STOP", "STEP", "NULL"):
        old = next((i for i in tbl["well"] if i[0].upper() == k), None)
        u, v, d = fixed[k]
        well.append((k, u, v, (old[3] if old and old[3] else d)))
    if tbl["format"] == "LAS":
        well += [tuple(i) for i in tbl["well"] if i[0].upper() not in fixed]
    else:
        well += [(m, "", "", d) for m, d in WELL_DEFAULT]
    curves = []
    for p in plans:
        d = p["description"] if tbl["format"] == "LAS" else ""
        if p["name"] != p["original_name"] or p["converted"] or p["unit"] != p["original_unit"]:
            was = "was " + p["original_name"] + (f" [{p['original_unit']}]" if p["original_unit"] else "")
            d = f"{d} | {was}" if d else was
        curves.append((p["name"], p["unit"], "", d))
    o = prov["open_well_data"]
    params = [tuple(i) for i in tbl["params"] if not i[0].upper().startswith("OWD_")]
    params += [("OWD_DICT", "", o["dictionary_version"], "Open Well Data dictionary version"),
               ("OWD_ENGINE", "", o["engine_version"], "Open Well Data conversion engine version"),
               ("OWD_DATE", "", prov["generated_utc"], "Converted on (UTC)"),
               ("OWD_NAMES", "", o["settings"]["names"], "Naming scheme"),
               ("OWD_UNITS", "", o["settings"]["units"], "Unit target"),
               ("OWD_LINK", "", o["permalink"], "Conversion settings (no data in the link)")]
    other = citation_lines(prov)
    other.append("Channels (original [unit] -> output [unit], factor, offset; status (how mapped); rule):")
    other += ["  " + channel_line(p) for p in plans]
    ws = prov["warnings"] + [f"{p['original_name']}: {w}" for p in plans for w in p["warnings"]]
    if ws:
        other.append("Warnings:")
        other += ["  " + w for w in ws]
    other.append("BibTeX:")
    other += prov["how_to_cite"]["bibtex"].split("\n")
    if tbl["other"]:
        other.append("Original ~Other section:")
        other += tbl["other"]
    other = [(" " + ln) if ln.lstrip().startswith("~") else ln for ln in other]
    out = ["~Version Information"]
    out += _las_items([("VERS", "", "2.0", "CWLS log ASCII Standard - Version 2.0"),
                       ("WRAP", "", "NO", "One line per depth step")])
    out.append("~Well Information")
    out += _las_items(well)
    out.append("~Curve Information")
    out += _las_items(curves)
    out.append("~Parameter Information")
    out += _las_items(params)
    out.append("~Other Information")
    out += other
    out.append("~A")
    strs = [[null_out if v is None else v for v in c] for c in cols]
    widths = [max([len(x) for x in c] + [1]) for c in strs]
    n = len(cols[0]) if cols else 0
    for i in range(n):
        out.append(" ".join(strs[j][i].rjust(widths[j]) for j in range(len(strs))))
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ text and file API
def _input_info(tbl, file_name, sha):
    info = {"file": file_name,
            "format": ("LAS " + tbl["version"].split()[0]) if tbl["format"] == "LAS" and tbl["version"].split() else tbl["format"],
            "sha256": sha, "rows": tbl["rows"], "null": tbl.get("null")}
    if tbl["format"] == "LAS":
        info["well"] = {i[0]: i[2] for i in tbl["well"]
                        if i[0].upper() in ("WELL", "COMP", "FLD", "UWI", "API", "SRVC", "CTRY", "DATE") and i[2]}
    return info


def convert_table(tbl, *, names="owd", units="si", to="csv", source_format=None, digits=DEFAULT_DIGITS, csv_header="unit",
                  source=None, file_name="", input_sha256=None, now=None):
    """Plan and convert a parsed table. Returns (plans, output columns, provenance)."""
    ix = index()
    if to not in ("csv", "las", "parquet"):
        raise ConversionError("to must be csv, las or parquet")
    if csv_header not in ("unit", "plain"):
        raise ConversionError("csv_header must be 'unit' or 'plain'")
    fmt = source_format or (tbl["format"] if tbl["format"] in LOG_FORMATS else "table")
    plans = plan_channels(tbl["channels"], names, units, fmt, output="las" if to == "las" else None, ix=ix,
                          dataset=(source or {}).get("dataset"))
    cols, _ = convert_columns(tbl, plans, digits, las=(to == "las"))
    prov = provenance(plans, names=names, units=units, to=to, source=source or source_info(),
                      input_info=_input_info(tbl, file_name, input_sha256 or tbl.get("sha256")), now=now, digits=digits,
                      csv_header=csv_header, source_format=fmt, extra_warnings=tbl["warnings"], ix=ix)
    return plans, cols, prov


def render(tbl, plans, cols, prov, to, digits=None, csv_header="unit", comments=False):
    """Output text for csv or las."""
    if to == "csv":
        return write_csv(plans, cols, prov, csv_header, comments)
    if to == "las":
        return write_las(tbl, plans, cols, prov, digits)
    raise ConversionError("render writes csv or las")


def parse_text(text, kind=None, null=None):
    text = decode(text)
    if kind is None:
        kind = "las" if re.match(r"\s*~", text) else "csv"
    tbl = parse_las(text) if kind == "las" else parse_csv(text, null=null)
    if kind == "las" and null is not None:
        tbl["null"] = null
    tbl["sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return tbl


def convert_text(text, kind=None, *, names="owd", units="si", to="csv", source_format=None, null=None, digits=DEFAULT_DIGITS,
                 csv_header="unit", comments=False, source=None, file_name="", input_sha256=None, now=None):
    """Convert the text of a LAS 2.0 or CSV file. Returns (output_text, provenance). to: 'csv' or 'las'."""
    if to not in ("csv", "las"):
        raise ConversionError("convert_text writes csv or las; use convert_file for parquet")
    tbl = parse_text(text, kind, null)
    plans, cols, prov = convert_table(tbl, names=names, units=units, to=to, source_format=source_format, digits=digits,
                                      csv_header=csv_header, source=source, file_name=file_name,
                                      input_sha256=input_sha256, now=now)
    return render(tbl, plans, cols, prov, to, digits, csv_header, comments), prov


def provenance_json(prov):
    return json.dumps(prov, ensure_ascii=False, indent=1) + "\n"


def sidecar_path(out):
    root, _ = os.path.splitext(str(out))
    return root + ".provenance.json"


def _tbl_frame(cols, plans):
    import pandas as pd
    data = {}
    for p, c in zip(plans, cols):
        nums = [parse_number(v) if v is not None else None for v in c]
        if all(v is None or x is not None for v, x in zip(c, nums)):
            data[p["name"]] = pd.array([float("nan") if x is None else x for x in nums], dtype="float64")
        else:
            data[p["name"]] = pd.array(c, dtype="string")
    return pd.DataFrame(data)


def write_parquet(df, prov, path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    t = pa.Table.from_pandas(df, preserve_index=False)
    md = dict(t.schema.metadata or {})
    md.update({b"owd:provenance": provenance_json(prov).encode("utf-8"),
               b"owd:citation": prov["how_to_cite"]["full"].encode("utf-8"),
               b"owd:bibtex": prov["how_to_cite"]["bibtex"].encode("utf-8"),
               b"owd:units": json.dumps({c["name"]: c["unit"] for c in prov["channels"]}, ensure_ascii=False).encode("utf-8"),
               b"owd:license_note": prov["license_note"].encode("utf-8")})
    pq.write_table(t.replace_schema_metadata(md), path)


def frame_to_table(df, units=None, descriptions=None, fmt="table"):
    """A DataFrame (index included unless it is a plain RangeIndex) as the engine's table of tokens."""
    import pandas as pd
    units = units or {}
    descriptions = descriptions or {}
    chans, cols = [], []

    def tokens(s):
        if s.dtype.kind == "M":
            return ["" if pd.isna(v) else pd.Timestamp(v).isoformat() for v in s]
        if s.dtype.kind in "fiu":
            return ["" if v != v else fmt_number(float(v)) for v in s.to_numpy(dtype="float64")]
        return ["" if pd.isna(v) else str(v) for v in s]

    if not isinstance(df.index, pd.RangeIndex):
        nm = df.index.name or "index"
        u = units.get(nm) or ("m" if nm == "depth_m" else "")
        if nm == "depth_m":
            nm = "md"
        chans.append({"name": nm, "unit": u, "description": "index"})
        cols.append(tokens(pd.Series(df.index)))
    for c in df.columns:
        chans.append({"name": str(c), "unit": units.get(c) or "", "description": descriptions.get(c, "")})
        cols.append(tokens(df[c]))
    return {"format": fmt, "version": "", "channels": chans, "columns": cols, "null": None, "well": [], "params": [],
            "other": [], "warnings": [], "rows": len(df), "sha256": None}


def read_any(path, null=None):
    """Read a LAS 2.0, CSV, DLIS or WITSML file into the engine's table form."""
    p = str(path)
    if p.lower().endswith((".dlis", ".xml", ".zip")) or os.path.isdir(p):
        return _read_with_reader(p)
    with open(p, "rb") as f:
        raw = f.read()
    tbl = parse_text(raw, None, null)
    tbl["sha256"] = hashlib.sha256(raw).hexdigest()
    return tbl


def _read_with_reader(path):
    """DLIS (dlisio) and WITSML (owd channel reader) without the reader's own unit conversion: raw values and the
    units declared in the file go to the engine. The reader's cleaning steps (nulls, sentinels) are listed as
    warnings."""
    from . import _reader as L
    import pandas as pd
    if path.lower().endswith(".dlis"):
        from dlisio import dlis
        with dlis.load(path) as fs:
            every = [c.name for fr in fs[0].frames for c in fr.channels]
        rd = L.read_dlis(path, convert=False, allow=every)
        fmt = "DLIS"
    else:
        rd = L.read_witsml(path, convert=False)
        fmt = "WITSML"
    df = rd.data
    units = dict(rd.source_unit)
    idx = df.index
    if idx.dtype.kind == "M":
        df = df.copy()
        df.index = pd.Index([v.isoformat() for v in idx], name="time_utc")
    tbl = frame_to_table(df, units, rd.description, fmt)
    if idx.dtype.kind == "M":
        tbl["channels"][0].update(name="time_utc", description="UTC time (ISO 8601)")
    tbl["warnings"] = [f"{r['channel']}: {r['action']} ({r['n']}) {r['detail']}".strip() for r in rd.log]
    tbl["sha256"] = None
    if os.path.isfile(path):
        with open(path, "rb") as f:
            tbl["sha256"] = hashlib.sha256(f.read()).hexdigest()
    return tbl


def write_output(tbl, plans, cols, prov, out, to, digits=None, csv_header="unit", comments=False):
    if to == "csv":
        with open(out, "w", encoding="utf-8", newline="") as f:
            f.write(write_csv(plans, cols, prov, csv_header, comments))
        with open(sidecar_path(out), "w", encoding="utf-8") as f:
            f.write(provenance_json(prov))
    elif to == "las":
        with open(out, "w", encoding="utf-8", newline="") as f:
            f.write(write_las(tbl, plans, cols, prov, digits))
    else:
        write_parquet(_tbl_frame(cols, plans), prov, out)
    return str(out)


# ------------------------------------------------------------------ streaming (files of several GB)
STREAM_BYTES = 256 * 2**20      # files larger than this are converted in blocks unless stream=False
CHUNK_ROWS = 100_000


def _open_text(path):
    """Text stream with the same decoding rule as decode(): UTF-8, else Windows-1252, else Latin-1 (first 1 MB tested)."""
    with open(path, "rb") as f:
        head = f.read(1 << 20)
    enc = "utf-8-sig"
    try:
        head.decode("utf-8")
    except UnicodeDecodeError as e:
        if e.start < len(head) - 4:         # not just a character cut at the end of the sample
            try:
                head.decode("cp1252")
                enc = "cp1252"
            except UnicodeDecodeError:
                enc = "latin-1"
    return open(path, encoding=enc, errors="replace", newline="")


def stream_las(path):
    """(table skeleton without data, iterator of row blocks) for a LAS 1.2/2.0 file, reading the data in blocks."""
    f = _open_text(path)
    head = []
    for line in f:
        head.append(line)
        if line.strip().upper().startswith("~A"):
            break
    tbl = parse_las("".join(head) + "\n")
    n = len(tbl["channels"])
    wrap = next((i[2] for i in parse_las_line_items(head, "V") if i[0].upper() == "WRAP"), "NO").strip().upper().startswith("Y")
    stats = {"short": 0, "long": 0, "rows": 0}

    def blocks():
        rows, toks = [], []
        try:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if wrap:
                    toks += s.split()
                    while len(toks) >= n:
                        rows.append(toks[:n])
                        toks = toks[n:]
                else:
                    r = s.split()
                    if len(r) < n:
                        stats["short"] += 1
                        r += [""] * (n - len(r))
                    elif len(r) > n:
                        stats["long"] += 1
                        r = r[:n]
                    rows.append(r)
                if len(rows) >= CHUNK_ROWS:
                    stats["rows"] += len(rows)
                    yield rows
                    rows = []
            if toks:
                stats["short"] += 1
                rows.append(toks + [""] * (n - len(toks)))
            if rows:
                stats["rows"] += len(rows)
                yield rows
        finally:
            f.close()
    return tbl, blocks(), stats


def parse_las_line_items(lines, section):
    sec, out = None, []
    for line in lines:
        s = line.strip()
        if s.startswith("~"):
            sec = s[1:2].upper()
            continue
        if sec == section and s and not s.startswith("#"):
            it = parse_las_line(line)
            if it:
                out.append(list(it))
    return out


def stream_csv(path, null=None):
    """(table skeleton, iterator of row blocks, stats) for a large CSV (csv module; same header and units-row rules)."""
    f = _open_text(path)
    while True:
        line = f.readline()
        if not line or not line.lstrip().startswith("#"):
            break
    head_text = line
    second = f.readline()
    third = f.readline()
    tbl = parse_csv(head_text + second + third, null=null)
    delim = tbl["delimiter"]
    n = len(tbl["channels"])
    stats = {"bad": 0, "rows": 0}
    rest = io.StringIO((third if tbl.get("units_row") else second + third))

    def blocks():
        rows = []
        try:
            for src in (rest, f):
                for r in csv.reader(src, delimiter=delim):
                    if not r or all(c.strip() == "" for c in r):
                        continue
                    if len(r) != n:
                        stats["bad"] += 1
                        r = (r + [""] * n)[:n]
                    rows.append(r)
                    if len(rows) >= CHUNK_ROWS:
                        stats["rows"] += len(rows)
                        yield rows
                        rows = []
            if rows:
                stats["rows"] += len(rows)
                yield rows
        finally:
            f.close()
    return tbl, blocks(), stats


def convert_file_streaming(path, out, *, names="owd", units="si", to="csv", source_format=None, null=None,
                           digits=DEFAULT_DIGITS, csv_header="unit", comments=False, source=None, now=None):
    """Convert a large LAS or CSV block by block (constant memory). Same mapping, units and provenance as
    convert_file; the LAS output aligns columns within each block only."""
    import tempfile
    with open(path, "rb") as fb:
        first = fb.read(4096).decode("latin-1")
    is_las = bool(re.match(r"\s*~", first.lstrip("\ufeff\xef\xbb\xbf")))
    tbl, blocks, stats = stream_las(path) if is_las else stream_csv(path, null)
    if is_las and null is not None:
        tbl["null"] = null
    fmt = source_format or ("LAS" if is_las else "table")
    plans = plan_channels(tbl["channels"], names, units, fmt, output="las" if to == "las" else None,
                          dataset=(source or {}).get("dataset"))
    h = hashlib.sha256()
    with open(path, "rb") as fb:
        for blk in iter(lambda: fb.read(1 << 22), b""):
            h.update(blk)
    src = source or source_info()

    def prov_now(extra):
        tbl["rows"] = stats["rows"]
        return provenance(plans, names=names, units=units, to=to, source=src,
                          input_info=_input_info(tbl, os.path.basename(path), h.hexdigest()), now=now, digits=digits,
                          csv_header=csv_header, source_format=fmt, extra_warnings=extra)

    counts, extra_counts = {}, {}
    first_idx = last_idx = None
    stp = {"prev": None, "d0": None, "n": 0, "uniform": True}     # same uniform-step rule as write_las
    tmp = None
    writer = None
    if to == "csv":
        fo = open(out, "w", encoding="utf-8", newline="")
        if comments:
            fo.write("\n".join("# " + ln for ln in citation_lines(prov_now([]))) + "\n")
        fo.write(",".join(_csv_cell(p["name"] if (csv_header == "plain" or not p["unit"]) else f"{p['name']} [{p['unit']}]")
                          for p in plans) + "\n")
    elif to == "las":
        tmp = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".owd-data", dir=os.path.dirname(os.path.abspath(out)))
        fo = tmp
    try:
        for rows in blocks:
            chunk = dict(tbl, columns=[[r[j] for r in rows] for j in range(len(plans))])
            cols, _ = convert_columns(chunk, plans, digits, counts, las=(to == "las"))
            idx = [v for v in cols[0] if v is not None]
            if idx:
                first_idx = idx[0] if first_idx is None else first_idx
                last_idx = idx[-1]
            for v in idx:
                x = parse_number(v)
                if x is None:
                    continue
                if stp["prev"] is not None:
                    d = x - stp["prev"]
                    if stp["d0"] is None:
                        stp["d0"] = d
                        stp["uniform"] = d != 0
                    elif not abs(d - stp["d0"]) <= 1e-9 * abs(stp["d0"]):
                        stp["uniform"] = False
                stp["prev"] = x
                stp["n"] += 1
            if to == "csv":
                fo.write("".join(",".join(_csv_cell(c[i]) for c in cols) + "\n" for i in range(len(rows))))
            elif to == "las":
                nul = (tbl.get("null") or "").strip() or "-999.25"
                strs = [[nul if v is None else v for v in c] for c in cols]
                w = [max([len(x) for x in c] + [1]) for c in strs]
                fo.write("".join(" ".join(strs[j][i].rjust(w[j]) for j in range(len(strs))) + "\n" for i in range(len(rows))))
            else:
                import pyarrow as pa
                import pyarrow.parquet as pq
                if writer is None:      # column types from the first block: numeric, or text for the whole file
                    numeric = [all(v is None or parse_number(v) is not None for v in c) for c in cols]
                    schema = pa.schema([(p["name"], pa.float64() if k else pa.string()) for p, k in zip(plans, numeric)])
                    writer = pq.ParquetWriter(out, schema)
                arrays = []
                for c, k in zip(cols, numeric):
                    if k:
                        vals = [None if v is None else parse_number(v) for v in c]
                        bad = sum(1 for v, x in zip(c, vals) if v is not None and x is None)
                        if bad:
                            extra_counts["parquet_text"] = extra_counts.get("parquet_text", 0) + bad
                        arrays.append(pa.array(vals, pa.float64()))
                    else:
                        arrays.append(pa.array(c, pa.string()))
                writer.write_table(pa.Table.from_arrays(arrays, schema=writer.schema))
    finally:
        if to in ("csv", "las"):
            fo.close()
    extra = list(tbl["warnings"])
    if stats.get("short"):
        extra.append(f"{stats['short']} data rows had fewer values than curves: the missing values are written as null")
    if stats.get("long"):
        extra.append(f"{stats['long']} data rows had more values than curves: the extra values were left out")
    if extra_counts.get("parquet_text"):
        extra.append(f"{extra_counts['parquet_text']} text values in numeric columns were written as null in Parquet")
    if stats.get("bad"):
        extra.append(f"{stats['bad']} rows had a different number of fields than the header: padded with nulls or cut")
    add_count_warnings(plans, counts)
    prov = prov_now(extra)
    prov["input"]["streamed"] = True
    if to == "csv":
        with open(sidecar_path(out), "w", encoding="utf-8") as f:
            f.write(provenance_json(prov))
    elif to == "las":
        c0 = [first_idx, last_idx]
        cols0 = [c0] + [[None, None] for _ in plans[1:]]
        head = write_las(dict(tbl, columns=[]), plans, cols0, prov, digits,
                         step=None if is_las else (fmt_number(stp["d0"], 10) if stp["n"] > 1 and stp["uniform"]
                                                   else "0")).split("~A\n")[0] + "~A\n"
        with open(out, "w", encoding="utf-8", newline="") as fo, open(tmp.name, encoding="utf-8") as fi:
            fo.write(head)
            shutil.copyfileobj(fi, fo, 1 << 22)
        os.unlink(tmp.name)
    else:
        if writer is None:
            write_parquet(_tbl_frame([[] for _ in plans], plans), prov, out)
        else:
            writer.add_key_value_metadata({"owd:provenance": provenance_json(prov),
                                           "owd:citation": prov["how_to_cite"]["full"],
                                           "owd:bibtex": prov["how_to_cite"]["bibtex"],
                                           "owd:units": json.dumps({c["name"]: c["unit"] for c in prov["channels"]}, ensure_ascii=False),
                                           "owd:license_note": prov["license_note"]})
            writer.close()
    return str(out), prov


def convert_file(path, out=None, *, names="owd", units="si", to=None, source_format=None, null=None, digits=DEFAULT_DIGITS,
                 csv_header="unit", comments=False, dataset=None, citation=None, licence=None, now=None, stream=None):
    """Convert a LAS 2.0 / CSV / DLIS / WITSML file and write CSV, LAS or Parquet with citation and provenance.
    Returns (output path, provenance). CSV writes the provenance to <name>.provenance.json next to it; LAS keeps it in
    ~Parameter and ~Other; Parquet in the file's key-value metadata (owd:provenance, owd:citation, owd:bibtex).
    stream: convert block by block in constant memory (default: for LAS and CSV files larger than STREAM_BYTES)."""
    if to is None:
        to = os.path.splitext(str(out))[1].lstrip(".").lower() if out else "csv"
        to = {"pq": "parquet"}.get(to, to)
    if to not in ("csv", "las", "parquet"):
        raise ConversionError("to must be csv, las or parquet")
    if out is None:
        root = os.path.splitext(os.path.basename(str(path).rstrip("/")))[0]
        out = f"{root}.owd.{to}"
    p = str(path)
    plain = os.path.isfile(p) and not p.lower().endswith((".dlis", ".xml", ".zip"))
    if stream is None:
        stream = plain and os.path.getsize(p) > STREAM_BYTES
    if stream:
        if not plain:
            raise ConversionError("block-by-block conversion reads LAS and CSV files only")
        return convert_file_streaming(p, out, names=names, units=units, to=to, source_format=source_format, null=null,
                                      digits=digits, csv_header=csv_header, comments=comments,
                                      source=source_info(dataset, citation, licence), now=now)
    tbl = read_any(path, null=null)
    plans, cols, prov = convert_table(tbl, names=names, units=units, to=to, source_format=source_format, digits=digits,
                                      csv_header=csv_header, source=source_info(dataset, citation, licence),
                                      file_name=os.path.basename(str(path).rstrip("/")), now=now)
    return write_output(tbl, plans, cols, prov, out, to, digits, csv_header, comments), prov


# ------------------------------------------------------------------ DataFrames
def convert_frame(df, units_in=None, *, names="owd", units="si", source_format="table", source=None, now=None,
                  descriptions=None):
    """Convert an already-read DataFrame. units_in: {column: declared unit} (default df.attrs['unit'] when present).
    Returns (new DataFrame, provenance); the provenance is also in out.attrs['provenance']."""
    import pandas as pd
    ix = index()
    units_in = dict(units_in if units_in is not None else (df.attrs.get("unit") or {}))
    descriptions = descriptions or {}
    chans = [{"name": str(c), "unit": units_in.get(c) or "", "description": descriptions.get(c, "")} for c in df.columns]
    plans = plan_channels(chans, names, units, source_format, ix=ix, dataset=(source or {}).get("dataset"))
    out = {}
    for c, p in zip(df.columns, plans):
        s = df[c]
        if p["converted"]:
            if pd.api.types.is_numeric_dtype(s.dtype):
                a, b, c, d = p["base_factors"]
                s = s.astype("float64")
                s = s * a / c if b == 0 and d == 0 else (s * a + b - d) / c
            else:
                p["converted"], p["status"] = False, "kept_not_numeric"
                p["warnings"].append("column is not numeric: values kept as they are")
                p["name"], p["unit"], p["variable"] = p["original_name"], p["original_unit"], None
                p["statistic"] = p["window"] = p["statistic_evidence"] = None
        out[p["name"]] = s
    res = pd.DataFrame(out, index=df.index)
    if res.index.name == "depth_m":
        tu = None
        if "md" in ix.t["variables"]:
            tu = target_unit("md", units, ix)
        if tu and tu != "m":
            c = unit_row(tu, "length", ix)["factor"]
            res.index = pd.Index(res.index.to_numpy(dtype="float64") / c, name=f"depth_{tu}")
    prov = provenance(plans, names=names, units=units, to="dataframe", source=source,
                      input_info={"format": "DataFrame", "rows": len(df), "index": df.index.name}, now=now,
                      source_format=source_format, ix=ix)
    attrs = {k: v for k, v in df.attrs.items() if k not in ("unit", "original")}
    res.attrs.update(attrs)
    res.attrs["unit"] = {p["name"]: p["unit"] for p in plans}
    res.attrs["original"] = {p["name"]: {"name": p["original_name"], "unit": p["original_unit"]} for p in plans}
    res.attrs["statistic"] = {p["name"]: {"variable": p["variable"], "statistic": p["statistic"], "window": p["window"]}
                              for p in plans if p["variable"]}
    res.attrs["provenance"] = prov
    return res, prov
