# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Conflicts resolved for dictionary v1.1 (8 Nov 2026): documented unit fixes and context rules."""
import pytest
from owd import convert as C


def plan(name, unit, fmt="LAS"):
    return C.plan_channels([{"name": name, "unit": unit}], "owd", "si", fmt)[0]


@pytest.mark.parametrize("name,unit,expected", [
    ("TEMP", "DEG", "log_temperature"), ("TEMP", "US/F", "log_temperature"), ("TEMP", "CPS", None),
    ("TEMP", "degF", "log_temperature"), ("PE", "V/V", "pef"), ("PE", "NONE", "pef"), ("PEF", "V/V", "pef"),
    ("PE", "b/e", "pef"), ("SPHI", "MV", "sonic_porosity"), ("SPHI", "decp", "sonic_porosity"),
    ("CCL", "mv", "casing_collar_locator"), ("CCL", "", "casing_collar_locator"), ("ITT", "msec", None),
    ("ITT", "s", None), ("ITT", "US/F", "dt"), ("NPHI", "API", "neutron_api"), ("NPHI", "decp", "nphi"),
    ("NPHI", "CNTS", None), ("DI", "OHMM", "res_deep"), ("DI", "in", None), ("DPSS", "%", "density_porosity"),
    ("DPSS", "1/s", None), ("ACTC", "US/FT", "dt"), ("ACTC", "unitless", None), ("HV", "V", None),
    ("TT1", "us", None), ("GR7", "gAPI", None), ("GRR_CAL", "1/s", None), ("VS", "ft", None),
    ("UNKNOWN", "m/s2", None), ("PORSDEC", "g/cc", "sonic_porosity"), ("PORSDEC", "dec", "sonic_porosity"),
])
def test_variable(name, unit, expected):
    assert plan(name, unit)["variable"] == expected


def test_temp_deg_is_fahrenheit():
    p = plan("TEMP", "DEG")
    assert p["unit_rule"]["unit"] == "degF" and abs(p["factor"] - 5 / 9) < 1e-9


def test_pe_vv_keeps_values():
    p = plan("PE", "V/V")
    assert p["unit"] == "b/e" and p["factor"] == 1.0


def test_pe_without_unit_still_needs_a_unit():
    assert plan("PE", "")["status"] == "kept_no_unit"


def test_ccl_signal_without_unit():
    p = plan("CCL", "mv")
    assert p["unit"] == "" and p["factor"] == 1.0


def test_resolved_conflicts_not_open():
    open_ = C.tables()["conflicts"]
    for m in ("TEMP", "PE", "PEF", "CCL", "ITT", "NPHI", "SPHI", "DI", "DPSS", "ACTC", "HV", "TT1", "GS_BDTI"):
        assert m not in open_, m
