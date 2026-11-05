# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Free for non-commercial use; companies need a licence (see NOTICE).
"""Utah FORGE CSV: Pason EDR ("Name (unit)", date and time in two columns), Sanvean ("Name(unit)", DateTime column,
"#" comment header) and *_standard files (second row = units as long text).

Time in these files is local and the file carries no zone. Without `utc_offset_h` the index stays in naive local time
(and this is logged); with it, the index is moved to UTC and `offset_source` must be given.
"""
import re

import pandas as pd

from . import core, time

RE_UNIT = re.compile(r"^(.*?)\s*\(([^()]*)\)\s*$")


def _split(name):
    """'Hook Load (klbs)' -> ('Hook Load', 'klbs'); 'Surface_Top Drive Torque(kft-lbs)' -> (..., 'kft-lbs')."""
    m = RE_UNIT.match(name)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return name.strip(), None


def _symbol_from_unit_row(txt):
    """Unit row of *_standard: 'kilopounds (klbs)' -> 'klbs'; 'psi' -> 'psi'; 'N/A' -> None."""
    if txt is None or (isinstance(txt, float) and pd.isna(txt)):
        return None
    txt = str(txt).strip()
    if txt in ("", "N/A"):
        return None
    m = re.search(r"\(([^()]*)\)\s*$", txt)
    return m.group(1).strip() if m else txt


def _header(path):
    """Return (n_comment_lines, header as a list, second line as a list)."""
    ncom = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#"):
                ncom += 1
                continue
            head = next(iter(pd.read_csv(pd.io.common.StringIO(line), header=None, dtype=str).values.tolist()))
            second = next(f, "")
            second = next(iter(pd.read_csv(pd.io.common.StringIO(second), header=None, dtype=str).values.tolist())) if second.strip() else []
            return ncom, [str(c) for c in head], second
    raise ValueError(f"{path}: no header")


def read_forge_csv(path, channels=None, allow=(), convert=True, utc_offset_h=None, offset_source=None,
                   assumed=None, nrows=None):
    """Read a FORGE CSV. channels: names WITHOUT the unit (e.g. 'Hook Load', 'Surface_Top Drive Torque')."""
    ncom, head, second = _header(path)
    standard = bool(second) and str(second[0]).strip().lower() == "date/time"
    rd = core.Reading(data=pd.DataFrame())
    if head[:2] == ["YYYY/MM/DD", "HH:MM:SS"]:
        style, tcols = "pason", head[:2]
    elif "DateTime" in head:
        style, tcols = "sanvean", ["DateTime"]
    elif standard:
        style, tcols = "standard", [head[0]]
    else:
        raise ValueError(f"{path}: unrecognised FORGE CSV format (header {head[:3]})")
    name, unit = {}, {}
    for i, c in enumerate(head):
        if c in tcols or (style == "standard" and i < 3):
            continue
        if style == "standard":
            b, u = c.strip(), _symbol_from_unit_row(second[i] if i < len(second) else None)
        else:
            b, u = _split(c)
        if b in name:
            b = c                      # repeated name without unit: the full name is used
        name[b] = c
        unit[b] = u
    every = list(name)
    if channels is not None:
        missing = [c for c in channels if c not in name]
        if missing:
            raise KeyError(f"columns not in {path}: {missing}")
    use = core.filter_blacklist(every, "forge", channels, allow, rd)
    if channels is not None:
        use = [c for c in use if c in set(channels)]
    skip = list(range(ncom)) + ([ncom + 1] if standard else [])
    cols = tcols + [name[c] for c in use]
    df = pd.read_csv(path, skiprows=skip, usecols=cols, dtype=str, keep_default_na=False, na_values=[""],
                     nrows=nrows, low_memory=False)
    if style == "pason":
        t = pd.to_datetime(df["YYYY/MM/DD"] + " " + df["HH:MM:SS"], format="%Y/%m/%d %H:%M:%S", errors="coerce")
    elif style == "sanvean":
        t = pd.to_datetime(df["DateTime"], format="%Y/%m/%d %H:%M:%S.%f", errors="coerce")
    else:
        t = pd.to_datetime(df[tcols[0]], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    t = pd.DatetimeIndex(t)
    bad = pd.isna(t)
    if bad.any():
        core._log(rd, tcols[0], "unreadable_index", int(bad.sum()), "row without a valid date -> dropped")
    raw = df.loc[~bad, [name[c] for c in use]]
    raw.columns = use
    t = t[~bad]
    if utc_offset_h is None:
        raw.index = t
        raw.index.name = "time_local"
        core._log(rd, tcols[0], "local_time_no_zone", 0, "index in naive local time; not moved to UTC",
                  "the file declares no time zone (E8)")
    else:
        raw.index = time.local_to_utc(t, utc_offset_h, offset_source)
        raw.index.name = "time_utc"
        core._log(rd, tcols[0], "local_time_to_utc", 0, f"+{utc_offset_h} h", offset_source)
    rd.source_unit = {c: unit[c] for c in use}
    rd.description = {c: name[c] for c in use}
    core.process(rd, raw, "forge", drop_convention_null=True, convert=convert, assumed=assumed)
    rd.meta = dict(format=f"FORGE CSV ({style})", source_path=str(path))
    return rd
