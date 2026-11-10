# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Mapping of unmapped mnemonics for dictionary v1.1 (9 Nov 2026): new variables, context rules and unit fixes."""
import csv
import os
import pytest
from owd import convert as C

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "owd", "data")


def plan(name, unit, fmt="LAS"):
    return C.plan_channels([{"name": name, "unit": unit}], "owd", "si", fmt)[0]


@pytest.mark.parametrize("name,unit,expected", [
    ("DGA", "G/CC", "apparent_grain_density"), ("XPOR", "PERC", "crossplot_porosity"), ("SVEL", "m/s", "compressional_velocity"),
    ("SVEL", "ms/f", None), ("SVEL", "", None), ("SSVE", "ft/s", "shear_velocity"), ("VPVS", "", "vp_vs_ratio"),
    ("ED", "ft", "displacement_east"), ("ND", "m", "displacement_north"), ("VSEC", "ft", "vertical_section"),
    ("VS", "ft", None), ("AMP3FT", "MV", "cbl_amplitude"), ("BONDIX", "", "bond_index"), ("TAB_DEN", "s", "time_after_bit"),
    ("RPTHM", "min", "time_after_bit"), ("COMP", "G/CC", "drho"), ("COMP", "", None), ("GRE", "gapi", "gr"), ("GRE", "", None),
    ("SWPOR", "PU", "nphi"), ("SWPOR", "", None), ("SWPOR", "cps", None), ("MINV", "OHMM", "res_flushed"),
    ("INV_RF", "ohm", "res_flushed"), ("FEFE", "OHMM", "res_shallow"), ("R60O", "OHMM", "res_medium"),
    ("R85O", "OHMM", "res_deep"), ("CTAO", "MMHO", "conductivity_induction"), ("CGXT", "DEGF", "log_temperature"),
    ("LWTLB", "lb", "cable_tension"), ("SIGC", "cu", "sigma"), ("DELTAT", "uspf", "dt"), ("PORS", "%", "sonic_porosity"),
    ("CCLPERF1", "", "casing_collar_locator"), ("HDEN", "K/M3", "rhob"), ("RMIC", "ohm.m", "res_flushed"),
])
def test_variable(name, unit, expected):
    assert plan(name, unit)["variable"] == expected


def test_minv_in_ohm_is_ohm_m():
    p = plan("INV_RF", "ohm")
    assert p["unit_rule"]["unit"] == "ohm.m" and p["factor"] == 1.0


def test_swn_porosity_percent():
    assert abs(plan("SWPOR", "PU")["factor"] - 0.01) < 1e-12


def test_time_after_bit_minutes_to_seconds():
    assert abs(plan("RPTHM", "min")["factor"] - 60) < 1e-9


def test_pwls_table_names_existing_variables():
    names = {r["variable"] for r in csv.DictReader(open(os.path.join(DATA, "..", "variables.tsv"), encoding="utf-8"), delimiter="\t")}
    for r in csv.DictReader(open(os.path.join(DATA, "pwls_property_kinds.csv"), encoding="utf-8")):
        for v in r["variable"].split("|"):
            assert v in names, v
