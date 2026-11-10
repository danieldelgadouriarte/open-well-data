# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Dictionary batch 5 (7 Nov 2026): RT_HRLT and DCAL.

RT_HRLT (HRLA computed true resistivity) maps to res_deep in every dataset: the low medians (0.02-0.05 ohm.m) of IODP
holes U1616E, U1617A and U1480G come from whole-pass DLIS frames that start at the seafloor, with most of the pass
inside the drill pipe (hole documentation: pipe at 264-316, 74-153 and 757 m WMSF), where every HRLA curve, the mud
resistivity included, reads 0.002-0.05 ohm.m. Same tool, unit and description as the good files: a quality matter, not
another variable, so there is no dataset or unit split.

DCAL stays unassigned in KGS: the file values do not separate caliper and differential caliper either (medians
continuous from 0 to 10 in, p99 above 6 in in both groups), so no value condition is added."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from owd import convert as C  # noqa: E402


def plan(name, unit, dataset=None, fmt="DLIS"):
    return C.plan_channels([{"name": name, "unit": unit, "description": ""}], source_format=fmt, dataset=dataset)[0]


def test_rt_hrlt_is_deep_resistivity_everywhere():
    for ds in ("iodp-logdb", "mseel", "kgs", None):
        p = plan("RT_HRLT", "ohm.m", ds)
        assert p["variable"] == "res_deep", ds
        assert p["unit"] == "ohm.m" and p["factor"] == 1.0
    p = plan("RT_HRLT", "OHMM", "mseel", "LAS")
    assert p["variable"] == "res_deep" and p["unit"] == "ohm.m"


def test_rt_hrlt_quality_flag_is_not_a_resistivity():
    assert plan("QC_RT_HRLT", "", "iodp-logdb")["variable"] != "res_deep"


def test_dcal_kgs_stays_unassigned():
    for u in ("IN", "in", "GAPI"):
        p = plan("DCAL", u, "kgs", "LAS")
        assert p["variable"] is None and p["mapped_by"] == "context_unassigned"
    assert plan("DCAL", "in", "fallon-forge-21-31", "LAS")["variable"] == "differential_caliper"
