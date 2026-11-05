# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Free for non-commercial use; companies need a licence (see NOTICE).
"""Readers by format. They return a Reading of the channel reader (data, units, role, log)."""
import io, re, zipfile
import pandas as pd
from . import _reader as L
from ._reader.core import Reading

def gdr1329_txt(zip_path, member):
    """PDC laboratory tests in Sierra White granite (GDR 1329, Oklahoma State): title, a tab-separated metadata line
    of "key = value" pairs, header and data at ~512 Hz. The file declares no units."""
    with zipfile.ZipFile(zip_path) as z:
        txt = z.read(member).decode("latin-1")
    lines = txt.splitlines()
    meta = {"title": lines[0].strip()}
    for pair in lines[1].split("\t"):
        if "=" in pair:
            k, v = pair.split("=", 1); meta[k.strip()] = v.strip()
    df = pd.read_csv(io.StringIO("\n".join(lines[2:])), sep="\t")
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
    df = df.set_index("Test Time").drop(columns=["Time"], errors="ignore")
    rd = Reading(data=df.apply(pd.to_numeric, errors="coerce"))
    rd.unit = {c: None for c in df.columns}; rd.source_unit = dict(rd.unit)
    rd.role = {c: None for c in df.columns}
    rd.meta = {"test_metadata": meta, "index": "Test Time (s)"}
    return rd

def force2020_csv(path, sep=";"):
    """FORCE 2020 CSV (one row per depth and well). Units from the competition documentation: GR gAPI, RHOB g/cm3,
    NPHI v/v, DTC and DTS us/ft, RDEP/RMED ohm.m, CALI in, PEF b/e, SP mV. NOT TESTED with the real file."""
    df = pd.read_csv(path, sep=sep)
    u = {"GR": "gAPI", "RHOB": "g/cm3", "NPHI": "v/v", "DTC": "us/ft", "DTS": "us/ft", "RDEP": "ohm.m",
         "RMED": "ohm.m", "CALI": "in", "PEF": "b/e", "SP": "mV"}
    df = df.set_index(["WELL", "DEPTH_MD"])
    rd = Reading(data=df)
    rd.unit = {c: u.get(c) for c in df.columns}; rd.source_unit = dict(rd.unit)
    rd.role = {c: None for c in df.columns}
    rd.meta = {"unit_source": "FORCE 2020 documentation (not checked against the file)"}
    return rd

def threew_parquet(path):
    """3W Parquet (Petrobras). Units from dataset/dataset.ini of 3W 2.0.0: pressures in Pa, temperatures in degC,
    rates (QGL, QBS) in m3/s. Tested with WELL-00002_20131104004101.parquet (3 Nov 2026)."""
    df = pd.read_parquet(path)
    pa = {c: "Pa" for c in df.columns if c.startswith("P-")}
    tc = {c: "degC" for c in df.columns if c.startswith("T-")}
    rd = Reading(data=df)
    rd.unit = {c: pa.get(c) or tc.get(c) for c in df.columns}; rd.source_unit = dict(rd.unit)
    for c, v in pa.items():
        rd.data[c] = rd.data[c] / 1000.0; rd.unit[c] = "kPa"
    for c in ("QGL", "QBS"):
        if c in df.columns:
            rd.data[c] = rd.data[c] * 86400.0; rd.unit[c] = "m3/d"; rd.source_unit[c] = "m3/s"
    rd.role = {c: None for c in df.columns}
    rd.meta = {"unit_source": "dataset/dataset.ini of 3W 2.0.0"}
    return rd

RE_U = re.compile(r"^(.*?)\s*\(([^()]*)\)\s*$")
# Same symbol written another way; the factor comes from units.tsv (NIST SP 811 B.9 for ft·lbf).
_SYNONYM = {"kft-lb": "kft-lbs"}

def rigwatch_csv(zip_path, member, nrows=None):
    """RigWatch CSV (IODP, JOIDES Resolution). Header "Name (unit)"; DATETIME in UTC according to OPSRIG-README.txt."""
    from ._reader import core
    with zipfile.ZipFile(zip_path) as z, z.open(member) as f:
        df = pd.read_csv(f, nrows=nrows, low_memory=False)
    tcol = df.columns[0]
    t = pd.to_datetime(df[tcol], format="%m/%d/%Y %H:%M:%S", errors="coerce", utc=True)
    base = {}
    for c in df.columns[1:]:
        m = RE_U.match(c); b, u = (m.group(1).strip(), m.group(2).strip()) if m else (c.strip(), None)
        base[c] = (b, u)
    count = pd.Series([b for b, _ in base.values()]).value_counts()
    names, unit = {}, {}
    for c, (b, u) in base.items():
        n = b if count[b] == 1 else c        # if two columns share a name (e.g. mbrf and mbsf) the full name is kept
        names[c] = n; unit[n] = _SYNONYM.get(u, u)
    rd = Reading(data=pd.DataFrame())
    raw = df.loc[t.notna(), list(names)].rename(columns=names)
    raw.index = t[t.notna()]; raw.index.name = "time_utc"
    rd.source_unit = unit
    core.process(rd, raw, "forge", drop_convention_null=True)
    rd.meta = {"format": "RigWatch CSV", "file": member, "time_zone": "UTC (OPSRIG-README.txt)"}
    return rd

def las_in_zip(zip_path, member):
    """A LAS inside a zip (FORCE 2020): extracted to a temporary folder and read by the channel reader."""
    import tempfile, os
    with zipfile.ZipFile(zip_path) as z, tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, os.path.basename(member))
        open(p, "wb").write(z.read(member))
        rd = L.read_las(p)
    rd.meta.update({"file": member})
    return rd


def las_in_nested_zip(zip_path, inner, member):
    """LAS inside a zip that is inside another zip (MSEEL MIP on EDX)."""
    import tempfile, os
    with zipfile.ZipFile(zip_path) as z:
        zi = zipfile.ZipFile(io.BytesIO(z.read(inner)))
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, os.path.basename(member))
            open(p, "wb").write(zi.read(member))
            rd = L.read_las(p)
    rd.meta.update({"file": f"{inner}/{member}"})
    return rd
