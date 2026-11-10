# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""LAS (lasio) and DLIS (dlisio). Both libraries are imported only when used.

LAS: unit = unit field of ~Curve; declared null = NULL of ~Well. lasio is read with null_policy='none' so that the
null is removed by this package and logged.
DLIS: unit = the channel's `units`; DLIS declares no null, so -999.25 is removed as a convention sentinel and logged
separately. The depth index is converted to m with its own unit ("0.1 in" in Volve).
"""
import pandas as pd

from . import core
from . import units as U


def read_las(path, channels=None, allow=(), convert=True, assumed=None, source="volve"):
    import lasio
    las = lasio.read(path, null_policy="none", mnemonic_case="preserve")   # case kept as in the file
    null = las.well["NULL"].value if "NULL" in las.well else None
    curves = las.curves
    idx = curves[0].mnemonic
    rd = core.Reading(data=pd.DataFrame())
    every = [c.mnemonic for c in curves[1:]]
    if channels is not None:
        missing = [c for c in channels if c not in every]
        if missing:
            raise KeyError(f"curves not in {path}: {missing}")
    use = core.filter_blacklist(every, source, channels, allow, rd)
    if channels is not None:
        use = [c for c in use if c in set(channels)]
    df = las.df().reset_index()
    uni = {c.mnemonic: (c.unit or None) for c in curves}
    for c in curves:                    # ".----" in Volve LAS = no unit
        if uni[c.mnemonic] and set(uni[c.mnemonic]) == {"-"}:
            uni[c.mnemonic] = None
    v, row = U.convert(df[idx].to_numpy(dtype=float), uni[idx], "length", idx)
    raw = df[use].copy()
    raw.index = pd.Index(v, name="depth_m")
    rd.source_unit = {c: uni[c] for c in use}
    rd.description = {c.mnemonic: c.descr for c in curves if c.mnemonic in use}
    nulls = {c: [null] for c in use} if null is not None else {}
    core.process(rd, raw, source, declared_nulls=nulls, drop_convention_null=False, convert=convert,
                 assumed=assumed)
    rd.meta = dict(format="LAS", source_path=str(path), index=idx, index_unit=uni[idx], null=null)
    return rd


def read_dlis(path, frame=None, channels=None, allow=(), convert=True, assumed=None, source="volve"):
    from dlisio import dlis
    with dlis.load(path) as fs:
        f = fs[0]
        frames = f.frames
        fr = frames[0] if frame is None else next(x for x in frames if x.name == frame)
        chans = list(fr.channels)
        a = fr.curves()
        idx = chans[0].name
        uni = {c.name: (c.units or None) for c in chans}
        desc = {c.name: c.long_name for c in chans}
        index_type = fr.index_type
    rd = core.Reading(data=pd.DataFrame())
    every = [c.name for c in chans[1:]]
    if channels is not None:
        missing = [c for c in channels if c not in every]
        if missing:
            raise KeyError(f"channels not in {path}: {missing}")
    use = core.filter_blacklist(every, source, channels, allow, rd)
    if channels is not None:
        use = [c for c in use if c in set(channels)]
    raw = pd.DataFrame({c: a[c].astype("float64") for c in use if a[c].ndim == 1})
    multi = [c for c in use if a[c].ndim != 1]
    for c in multi:
        core._log(rd, c, "multidimensional_channel_skipped", 0, f"shape {a[c].shape}")
    ix = a[idx].astype("float64")
    if (index_type or "").upper() == "BOREHOLE-DEPTH":
        ix, _ = U.convert(ix, uni[idx], "length", idx)
        raw.index = pd.Index(ix, name="depth_m")
    else:
        raw.index = pd.Index(ix, name=f"{idx} [{uni[idx]}]")
        core._log(rd, idx, "index_not_converted", 0, f"index_type {index_type}, unit {uni[idx]!r}")
    rd.source_unit = {c: uni[c] for c in raw.columns}
    rd.description = {c: desc[c] for c in raw.columns}
    for c, u in rd.source_unit.items():
        if u and u.startswith("BAD_UNIT"):
            rd.source_unit[c] = None
            core._log(rd, c, "invalid_unit_in_file", 0, f"{u!r} -> no unit")
    core.process(rd, raw, source, drop_convention_null=True, convert=convert, assumed=assumed)
    rd.meta = dict(format="DLIS", source_path=str(path), frame=fr.name, index_type=index_type, index=idx,
                   index_unit=uni[idx])
    return rd
