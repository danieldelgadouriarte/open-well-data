# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Free for non-commercial use; companies need a licence (see NOTICE).
"""Index by variable.

- variables(): the variable dictionary (variables.tsv); the standard channels are a subset of it.
- coverage(): which variable each well and file of each dataset has, over which interval and in which unit.
- search_variables(["gr", "rhob", "dt"]): wells and files that have all the requested variables, with the common interval.

The index points to the packages; it does not duplicate data. To read an interval, owd.load(dataset, file)."""
import csv, os
import pandas as pd

_DIR = os.path.dirname(__file__)
VARIABLES = list(csv.DictReader(open(os.path.join(_DIR, "variables.tsv"), encoding="utf-8"), delimiter="\t"))
_COV = os.path.join(_DIR, "data", "variable_coverage.csv")


def variables(family=None):
    return [v for v in VARIABLES if not family or v["family"] == family]


def coverage():
    return pd.read_csv(_COV)


def search_variables(variables, dataset=None, with_unit=True):
    """Files that have ALL the requested variables. One row per file with the common depth interval (envelope: from
    the largest `start` to the smallest `end`; gaps are not subtracted) if the axis is depth, or the minimum hours if it
    is time. with_unit=True leaves out columns without a known unit."""
    asked = list(dict.fromkeys(variables))
    unknown = set(asked) - {v["variable"] for v in VARIABLES}
    if unknown:
        raise KeyError(f"variables not in the dictionary: {sorted(unknown)}")
    c = coverage()
    c = c[c.variable.isin(asked)]
    if dataset:
        c = c[c.dataset == dataset]
    if with_unit:
        c = c[c.unit_status != "no_unit"]
    g = c.groupby(["dataset", "well", "file"])
    r = g.agg(n=("variable", "nunique"), axis_=("axis", "first"), license=("license", "first"), policy=("policy", "first"),
              start=("start", "max"), end=("end", "min"), min_hours=("valid_hours", "min"), min_rows=("valid_rows", "min")).reset_index().rename(columns={"axis_": "axis"})  # agg() reserves the name axis
    r = r[r.n == len(asked)].drop(columns="n")
    r["envelope_m"] = (r.end - r.start).clip(lower=0)
    return r.reset_index(drop=True)
