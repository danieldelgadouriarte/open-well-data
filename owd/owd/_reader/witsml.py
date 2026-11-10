# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Volve WITSML 1.4 logs (witsml.zip or a folder of NNNNN.xml chunks).

The unit of each channel comes from the `<unit>` of its `<logCurveInfo>` and, if missing, from the `<unitList>` of
the data block. If both exist and differ, or if it changes between chunks, InconsistentUnit is raised (no choice is
made). Declared nulls are the log's `<nullValue>` and that of each `<logCurveInfo>`. If a log declares no null (183 of
2047 in Volve), any -999.25 found is removed anyway as a convention sentinel and logged separately.
"""
import glob
import io
import os
import re
import zipfile

import pandas as pd

from . import core, time

RE_LCI = re.compile(r"<logCurveInfo\b[^>]*>(.*?)</logCurveInfo>", re.S)
ZIP_ROOT = "sitecom14.statoil.no/"
RE_CHUNK = re.compile(r"^(?:sitecom14\.statoil\.no/)?(.+?)/(\d+)/log/(\d+)/(\d+)/(\d+)/(\d+)\.xml$")


class InconsistentUnit(ValueError):
    pass


def _tag(txt, t):
    m = re.search(r"<%s\b[^>]*>([^<]*)</%s>" % (t, t), txt)
    return m.group(1) if m else None


def header(txt):
    """Read the header of a chunk: log dict, dict mnemonic -> logCurveInfo, mnemonicList, unitList."""
    p = txt.find("<logData>")
    h = txt if p < 0 else txt[:p]
    outside = RE_LCI.sub("", h)
    log = {t: _tag(outside, t) for t in ("nameWell", "nameWellbore", "name", "indexType", "indexCurve", "nullValue",
                                          "serviceCompany", "runNumber", "startDateTimeIndex", "endDateTimeIndex")}
    lci = {}
    for blk in RE_LCI.findall(h):
        m = _tag(blk, "mnemonic")
        if m:
            lci[m] = dict(unit=_tag(blk, "unit"), nullValue=_tag(blk, "nullValue"),
                          curveDescription=_tag(blk, "curveDescription"))
    tail = txt[p:p + 200000] if p >= 0 else ""
    ml = _tag(tail, "mnemonicList")
    ul = _tag(tail, "unitList")
    return log, lci, (ml.split(",") if ml is not None else None), (ul.split(",") if ul is not None else None)


class _Source:
    """Wraps a zip + prefix or a list of xml files."""

    def __init__(self, origin, log=None):
        self.z = None
        if isinstance(origin, (list, tuple)):
            self.names = sorted(origin)
        elif str(origin).endswith(".zip"):
            if log is None:
                raise ValueError("with a zip, log= is required (e.g. 'Norway-StatoilHydro-15_$47$_9-F-10/1/log/2/3/1')")
            self.z = zipfile.ZipFile(origin)
            pre = log.strip("/")
            if not pre.startswith(ZIP_ROOT):
                pre = ZIP_ROOT + pre
            pre += "/"
            self.names = sorted(i.filename for i in self.z.infolist()
                                if i.filename.startswith(pre) and i.filename.endswith(".xml") and i.file_size
                                and "/" not in i.filename[len(pre):])
        else:
            self.names = sorted(glob.glob(os.path.join(origin, "*.xml")))
        if not self.names:
            raise FileNotFoundError(f"no xml chunks in {origin} {log or ''}")

    def read(self, n, head=None):
        if self.z is not None:
            with self.z.open(n) as f:
                b = f.read(head) if head else f.read()
        else:
            with open(n, "rb") as f:
                b = f.read(head) if head else f.read()
        return b.decode("utf-8", "replace")


def _units(heads):
    """Unit per mnemonic from the headers of all chunks; raises on any contradiction."""
    uni, desc, nulls = {}, {}, {}
    for log, lci, ml, ul in heads:
        for m, d in lci.items():
            u = d["unit"]
            if m in uni and uni[m] is not None and u is not None and uni[m] != u:
                raise InconsistentUnit(f"{m}: <unit> {uni[m]!r} and {u!r} in different chunks")
            if u is not None or m not in uni:
                uni[m] = u
            if d["curveDescription"]:
                desc.setdefault(m, d["curveDescription"])
            if d["nullValue"] is not None:
                nulls.setdefault(m, set()).add(d["nullValue"])
        if ml and ul:
            for m, u in zip(ml, ul):
                u = u or None
                if uni.get(m) is None:
                    uni[m] = u
                elif u is not None and uni[m] != u:
                    raise InconsistentUnit(f"{m}: <unit> {uni[m]!r} and unitList {u!r}")
        if log.get("nullValue") is not None:
            for m in (ml or lci):
                nulls.setdefault(m, set()).add(log["nullValue"])
    return uni, desc, {k: sorted(v) for k, v in nulls.items()}


def log_units(origin, log=None):
    """Headers only (reads the first ~200 kB of each chunk): unit, description and nulls per mnemonic, and the log."""
    F = _Source(origin, log)
    heads = []
    for n in F.names:
        t = F.read(n, head=400000)
        if "</mnemonicList>" not in t or "</unitList>" not in t:
            t = F.read(n)                      # header longer than what was read: whole chunk
        heads.append(header(t))
    uni, desc, nulls = _units(heads)
    return dict(log=heads[0][0], unit=uni, description=desc, nulls=nulls, chunks=len(F.names))


def read_witsml(origin, log=None, channels=None, allow=(), convert=True, assumed=None):
    """Read a whole WITSML log (all its chunks) and return a Reading.

    origin: path to witsml.zip (with log=prefix of the log inside the zip), a folder with the NNNNN.xml files or a list
    of xml files. channels: list of mnemonics (None = all except the blacklist). allow: blacklisted mnemonics accepted
    when asked for explicitly. assumed: mnemonic -> (unit, source) for channels without a declared unit.
    """
    F = _Source(origin, log)
    rd = core.Reading(data=pd.DataFrame())
    heads, parts = [], []
    for n in F.names:
        txt = F.read(n)
        hd = header(txt)
        heads.append(hd)
        lg, lci, ml, ul = hd
        if ml is None:
            continue
        idx = lg.get("indexCurve") or ml[0]
        rows = re.findall(r"<data>([^<]*)</data>", txt)
        if not rows:
            continue
        df = pd.read_csv(io.StringIO("\n".join(rows)), header=None, names=ml, dtype=str, keep_default_na=False,
                         na_values=[""], engine="c")
        parts.append((idx, df))
    if not parts:
        raise ValueError("log without data rows")
    uni, desc, nulls = _units(heads)
    lg0 = heads[0][0]
    idx = parts[0][0]
    every = list(dict.fromkeys(c for _, d in parts for c in d.columns if c != idx))
    if channels is not None:
        missing = [c for c in channels if c not in every]
        if missing:
            raise KeyError(f"channels not in the log: {missing}")
    rd.source_unit = {c: uni.get(c) for c in every}
    rd.description = {c: desc.get(c) for c in every}
    use = core.filter_blacklist(every, "volve", channels, allow, rd)
    if channels is not None:
        use = [c for c in use if c in set(channels)]
    df = pd.concat([d.reindex(columns=[idx] + use) for _, d in parts], ignore_index=True)
    is_time = "time" in (lg0.get("indexType") or "").lower()
    if is_time:
        ix = time.iso_to_utc(df[idx])
    else:
        ix = pd.Index(pd.to_numeric(df[idx], errors="coerce"), name=idx)
    bad = pd.isna(ix)
    if bad.any():
        core._log(rd, idx, "unreadable_index", int(bad.sum()), "row without a valid index -> dropped")
    raw = df.loc[~bad, use]
    raw.index = ix[~bad]
    raw.index.name = "time_utc" if is_time else idx
    rd.source_unit = {c: uni.get(c) for c in use}
    rd.description = {c: desc.get(c) for c in use}
    core.process(rd, raw, "volve", declared_nulls={c: nulls.get(c, []) for c in use},
                 drop_convention_null=True, convert=convert, assumed=assumed)
    if not is_time:
        # depth index: to metres with the declared unit of the index
        from . import units as U
        v, row = U.convert(rd.data.index.to_numpy(dtype=float), uni.get(idx), "length", idx)
        rd.data.index = pd.Index(v, name="depth_m")
    if not rd.data.index.is_monotonic_increasing:
        core._log(rd, idx, "non_monotonic_index", 0, "the index is not increasing; sorted (stable sort)")
        rd.data = rd.data.sort_index(kind="stable")
    rd.meta = dict(format="WITSML", log=lg0, chunks=len(F.names), index=idx, source_path=str(origin), prefix=log)
    return rd


# --- per-log extracts of the Volve WITSML zip (csv.gz files written by an earlier parser) ---------------------------

def _wn(w):
    m = re.search(r"15_\$47\$_9-(F-\S+(?: \w)?)$", w)       # same rule as the parser that wrote the extracts
    return m.group(1) if m else w


def extract_prefix(name, zip_path, _cache={}):
    """'F-10__15_9-F-10__1-2-3-1.csv.gz' -> prefix of the log in witsml.zip, with the same matching as the parser
    (well = wn(folder) with spaces -> '_', key = wellbore-a-b-c)."""
    base = os.path.basename(name)
    base = re.sub(r"\.csv(\.gz)?$", "", base)
    well = base.split("__")[0]
    key = tuple(base.split("__")[-1].split("-"))
    if zip_path not in _cache:
        logs = set()
        with zipfile.ZipFile(zip_path) as z:
            for n in z.namelist():
                m = RE_CHUNK.match(n)
                if m:
                    logs.add(m.groups()[:5])
        _cache[zip_path] = logs
    cand = [k for k in _cache[zip_path] if k[1:] == key and _wn(k[0]).replace(" ", "_") == well]
    if len(cand) > 1 and os.path.exists(name):
        # two zip folders give the same extract name (e.g. F-14 under "StatoilHydro" and "Statoil-NO"; the parser
        # wrote the last one): chosen by content, the extract's header and first row against the first chunk.
        import gzip
        op = gzip.open if str(name).endswith(".gz") else open
        with op(name, "rt", encoding="utf-8", errors="replace") as fh:
            head = fh.readline().strip()
            row1 = fh.readline().strip()
        good = []
        with zipfile.ZipFile(zip_path) as z:
            for k in cand:
                pre = f"{ZIP_ROOT}{k[0]}/{k[1]}/log/{k[2]}/{k[3]}/{k[4]}/"
                ns = sorted(n for n in z.namelist() if n.startswith(pre) and n.endswith(".xml"))
                if not ns:
                    continue
                t = z.read(ns[0]).decode("utf-8", "replace")
                ml = _tag(t, "mnemonicList")
                d1 = re.search(r"<data>([^<]*)</data>", t)
                if ml == head and d1 and d1.group(1).split(",")[0] == row1.split(",")[0]:
                    good.append(k)
        cand = good
    if len(cand) != 1:
        raise LookupError(f"{name}: {len(cand)} logs in the zip match well {well} and key {key}")
    k = cand[0]
    return f"{k[0]}/{k[1]}/log/{k[2]}/{k[3]}/{k[4]}"


def read_volve_extract(csv_path, zip_path, channels=None, allow=(), convert=True, assumed=None):
    """Read a csv.gz extract (data already taken out of the zip) with the units and nulls of its log's WITSML header
    in the zip. Checks that the extract's columns are those of the log."""
    pre = extract_prefix(csv_path, zip_path)
    info = log_units(zip_path, pre)
    head = pd.read_csv(csv_path, nrows=0).columns.tolist()
    tcol = info["log"].get("indexCurve") or head[0]
    if tcol not in head:
        raise ValueError(f"{csv_path}: the log index {tcol} is not in the extract")
    unknown = [c for c in head if c not in info["unit"]]
    if unknown:
        raise ValueError(f"{csv_path}: columns not in the log header: {unknown[:5]}")
    rd = core.Reading(data=pd.DataFrame())
    every = [c for c in head if c != tcol]
    if channels is not None:
        missing = [c for c in channels if c not in every]
        if missing:
            raise KeyError(f"channels not in the extract: {missing}")
    use = core.filter_blacklist(every, "volve", channels, allow, rd)
    if channels is not None:
        use = [c for c in use if c in set(channels)]
    df = pd.read_csv(csv_path, usecols=[tcol] + use, dtype=str, keep_default_na=False, na_values=[""])
    ix = time.iso_to_utc(df[tcol])
    bad = pd.isna(ix)
    if bad.any():
        core._log(rd, tcol, "unreadable_index", int(bad.sum()), "row without a valid time -> dropped")
    raw = df.loc[~bad, use]
    raw.index = ix[~bad]
    raw.index.name = "time_utc"
    rd.source_unit = {c: info["unit"].get(c) for c in use}
    rd.description = {c: info["description"].get(c) for c in use}
    core.process(rd, raw, "volve", declared_nulls={c: info["nulls"].get(c, []) for c in use},
                 drop_convention_null=True, convert=convert, assumed=assumed)
    rd.meta = dict(format="WITSML (csv extract)", log=info["log"], prefix=pre, extract=str(csv_path))
    return rd
