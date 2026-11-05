# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Free for non-commercial use; companies need a licence (see NOTICE).
"""Unit table: symbol read from the file -> canonical unit, with factor and source (units.tsv).

Rule: only a symbol that is in the table is converted. A symbol that is not there is never guessed: if the channel has
a known physical role (roles.py) UnitWithoutSource is raised; otherwise the channel keeps its original unit and the
fact is logged.
"""
import csv
import os

_TSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "units.tsv")

# Canonical unit per dimension.
CANONICAL = {"angular_velocity": "rpm", "torque": "kN.m", "force": "kkgf", "pressure": "kPa", "flow_rate": "L/min",
             "length": "m", "velocity": "m/h", "temperature": "degC"}


class UnitWithoutSource(ValueError):
    """The unit symbol is not in units.tsv and the channel needs a conversion."""


class UndeclaredUnit(ValueError):
    """The file declares no unit for a channel with a physical role and no assumed unit with a source was given."""


class DimensionMismatch(ValueError):
    """The declared unit is not of the dimension the channel's role requires."""


def _load():
    t = {}
    with open(_TSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            r["factor"] = float(r["factor"])
            r["offset"] = float(r["offset"])
            if r["symbol"] in t:
                raise RuntimeError(f"repeated symbol in units.tsv: {r['symbol']}")
            if CANONICAL[r["dimension"]] != r["canonical"]:
                raise RuntimeError(f"inconsistent canonical unit for {r['symbol']}")
            t[r["symbol"]] = r
    return t


TABLE = _load()


def normalize_symbol(u):
    """Strip spaces from the symbol as written in the file. Case is kept and nothing is interpreted."""
    if u is None:
        return None
    u = str(u).strip()
    return u if u else None


def lookup(u):
    """Table row for symbol u (exact after stripping spaces) or None."""
    u = normalize_symbol(u)
    return TABLE.get(u) if u is not None else None


def convert(values, unit, expected_dimension=None, channel="?"):
    """Convert an array/Series from `unit` to the canonical unit of its dimension.

    Returns (converted_values, table_row). Raises UnitWithoutSource if the unit is not in the table, and
    DimensionMismatch if a dimension is requested and does not match.
    """
    row = lookup(unit)
    if row is None:
        raise UnitWithoutSource(f"{channel}: unit {unit!r} has no row in units.tsv (never guessed)")
    if expected_dimension and row["dimension"] != expected_dimension:
        raise DimensionMismatch(f"{channel}: unit {unit!r} is {row['dimension']}, the role requires {expected_dimension}")
    v = values * row["factor"]
    if row["offset"]:
        v = v + row["offset"]
    return v, row
