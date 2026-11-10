# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Context rules that resolve dictionary conflicts (8 Nov 2026): the unit decides, and good channels keep their label."""
import pytest
from owd import convert as C


def var(name, unit, fmt="LAS"):
    return C.plan_channels([{"name": name, "unit": unit}], "owd", "si", fmt)[0]["variable"]


@pytest.mark.parametrize("name,unit,fmt,expected", [
    ("DP", "kPa", "table", "delta_p"), ("DP", "psi", "table", "delta_p"), ("DP", "%", "LAS", "density_porosity"),
    ("MDT", "uspf", "LAS", "dt"), ("GRR", "API", "LAS", "gr"), ("GRR", "1/s", "LAS", "gr_raw_counts"),
    ("PD_GRAV", "1/s", "WITSML", "gr_raw_counts"), ("GR", "gAPI", "LAS", "gr"), ("GR", "CPS", "LAS", None),
    ("GAMMA", "API", "LAS", "gr"), ("SGR", "gAPI", "LAS", "gr"), ("SGR", "1/s", "LAS", None),
    ("PE", "b/e", "LAS", "pef"), ("PEF", "barns/e-", "LAS", "pef"), ("NEU", "v/v", "LAS", "nphi"),
    ("NEU", "CPS", "LAS", None), ("NEUT", "API", "LAS", "neutron_api"), ("SSGR", "gAPI", "LAS", None),
    ("COND(DI)", "MMHO/M", "LAS", "conductivity_induction"), ("COND(DI)", "CPS", "LAS", None),
    ("RILD", "OHMM", "LAS", "res_deep"), ("RILD", "MMHO", "LAS", None), ("CALI", "in", "LAS", "caliper"),
    ("SCAL", "IN", "LAS", "caliper"), ("SCAL", "GAPI", "LAS", None), ("ROP5", "m/h", "LAS", "rop"),
    ("ROPI", "s/m", "LAS", "rop_inverse"), ("CNLS", "pu", "LAS", "nphi"), ("MEL20", "OHMM", "LAS", "res_flushed"),
])
def test_context_rules(name, unit, fmt, expected):
    assert var(name, unit, fmt) == expected
