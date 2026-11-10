# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""The dictionary unit table (mnemonic_context.U) and the converter table (conversion_units.tsv) agree, and the unit
fixes of 6 Nov 2026 (aliases, TENS in lbm, ROP in min/ft, C1 in ppm) work in both."""
import pytest

from owd import convert as C
from owd import mnemonic_context as M


def test_unit_tables_agree():
    assert M.unit_table_disagreements() == []
    missing = [s for s in M.CONVERSION_READINGS if s.strip() == s and s not in M.UNKNOWN_UNIT and s not in M.U]
    assert missing == []


@pytest.mark.parametrize("unit,dim,factor", [
    ("PERC", "fraction", 0.01), ("GRAMS/CC", "density", 1000), ("g/cm", "density", 1000), ("B/E-", "pef", 1),
    ("barns/e-", "pef", 1), ("BARNES", "pef", 1), ("(IN)", "length", 0.0254), ("IN.", "length", 0.0254),
    ("(mbrf)", "length", 1), ("aapi", "radioactivity", 1), ("API-GR", "radioactivity", 1), ("decp", "fraction", 1),
    ("mmo/m", "conductivity", 1e-3), ("ohm/m", "resistivity", 1), ("F3", "volume", 0.028316846592),
    ("FT3", "volume", 0.028316846592), ("MSEC", "time", 1e-3), ("min/ft", "slowness", 60 / 0.3048)])
def test_new_aliases_in_the_dictionary_table(unit, dim, factor):
    d, f, _ = M.unit_info(unit)
    assert d == dim and f == pytest.approx(factor)


def plan(name, unit, fmt="LAS"):
    return C.plan_channels([{"name": name, "unit": unit, "description": ""}], source_format=fmt)[0]


def test_aliases_convert_in_the_converter():
    p = plan("DEN", "GRAMS/CC")
    assert p["variable"] == "rhob" and p["status"] in ("renamed", "converted")
    p = plan("DPOR", "PERC")
    assert p["variable"] == "density_porosity" and p["factor"] == pytest.approx(0.01)
    p = plan("PEF", "barns/e-")
    assert p["variable"] == "pef"


def test_tens_in_lbm_is_lbf():
    p = plan("TENS", "lbm", "DLIS")
    assert p["variable"] == "cable_tension" and p["unit_rule"]["unit"] == "lbf"
    assert p["factor"] == pytest.approx(4.4482216152605 / 1000)          # lbf -> kN
    assert M.assumed_unit("TENS", "lbm") == "lbf" and M.assumed_unit("TENS", "lbf") == "lbf"


def test_rop_in_min_per_ft_is_inverse_rop():
    p = plan("ROP", "min/ft")
    assert p["variable"] == "rop_inverse" and p["factor"] == pytest.approx(60 / 0.3048)
    assert plan("ROP", "ft/h")["variable"] == "rop"


def test_c1_in_ppm_is_methane():
    assert plan("C1", "ppm")["variable"] == "gas_c1"
    assert plan("C1", "in")["variable"] == "caliper"
