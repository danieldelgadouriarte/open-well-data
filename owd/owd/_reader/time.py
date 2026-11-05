# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Free for non-commercial use; companies need a licence (see NOTICE).
"""Time handling that does not assume the internal resolution of pandas.

With pandas 3, `to_datetime` may return datetime64[us] (previously [ns]), and `astype('int64') / 1e9` then gives
thousands of seconds instead of seconds. astype('int64') is never used here: seconds come from subtracting the epoch
and dividing by a Timedelta, which is correct at any resolution.
"""
import pandas as pd

EPOCH = pd.Timestamp("1970-01-01", tz="UTC")


def iso_to_utc(series):
    """ISO 8601 text (WITSML: 2009-05-17T06:42:33.000Z) -> UTC DatetimeIndex. Anything unreadable becomes NaT."""
    return pd.DatetimeIndex(pd.to_datetime(series, utc=True, format="ISO8601", errors="coerce"))


def seconds_since_epoch(t):
    """Zone-aware DatetimeIndex/Series -> float64 seconds since 1970-01-01 UTC, whatever the resolution."""
    t = pd.DatetimeIndex(t) if not isinstance(t, pd.Series) else t
    d = (t - EPOCH) / pd.Timedelta(seconds=1)
    return d.to_numpy(dtype="float64") if hasattr(d, "to_numpy") else d


def local_to_utc(t_naive, utc_offset_h, source):
    """Naive local time -> UTC by adding the offset (e.g. +7 for MST). The source of the offset is required."""
    if not source:
        raise ValueError("local_to_utc needs the source of the offset (e.g. '16A Nov-Dec 2020, MST = UTC-7')")
    t = pd.DatetimeIndex(t_naive)
    if t.tz is not None:
        raise ValueError("the time already has a zone; no offset is added")
    return (t + pd.Timedelta(hours=utc_offset_h)).tz_localize("UTC")
