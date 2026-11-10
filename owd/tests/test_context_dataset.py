# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Context rules by dataset, the UNASSIGNED target and temperature differences (7 Nov 2026), in the converter and in the
dictionary helpers (mnemonic_context), which must agree. The browser engine is checked by the parity vectors."""
import importlib.util
import os

import pytest

from owd import convert as C
from owd import mnemonic_context as M

_VC = os.path.join(os.path.dirname(__file__), "..", "pipeline", "variable_coverage.py")


def plan(name, unit, dataset=None, units="si", fmt="LAS"):
    return C.plan_channels([{"name": name, "unit": unit, "description": ""}], units=units, source_format=fmt,
                           dataset=dataset)[0]


def test_dataset_matching():
    assert C.dataset_matches([], None) and C.dataset_matches([], "kgs")
    assert C.dataset_matches(["kgs"], "kgs") and C.dataset_matches(["kgs"], "kgs-tables") and C.dataset_matches(["kgs"], "KGS_dst")
    assert not C.dataset_matches(["kgs"], "kgsx") and not C.dataset_matches(["kgs"], None)
    assert C.dataset_matches(["*"], "volve") and not C.dataset_matches(["*"], "")
    for want, ds in ((["kgs"], "kgs-tables"), (["*"], None), (["iodp"], "iodp_logdb"), (["kgs"], "wvgs")):
        assert M.dataset_matches(want, ds) == C.dataset_matches(want, ds)


def test_dcal_by_dataset():
    p = plan("DCAL", "IN", "kgs")                        # KGS mixes caliper and differential caliper: unassigned
    assert p["variable"] is None and p["mapped_by"] == "context_unassigned"
    assert plan("DCAL", "in", "force-2020")["variable"] == "differential_caliper"
    p = plan("DCAL", "in")                               # no dataset: unassigned, no fallback to the name
    assert p["variable"] is None and p["mapped_by"] == "context_unassigned"
    assert M.context_variable("DCAL", "in", "LAS", dataset="kgs") == M.UNASSIGNED
    assert M.context_variable("DCAL", "in", "LAS", dataset="iodp-logdb") == "differential_caliper"
    assert M.context_variable("DCAL", "in", "LAS") == M.UNASSIGNED


def test_dpls_fraction_or_unassigned():
    p = plan("DPLS", "%", "kgs")
    assert p["variable"] == "density_porosity" and p["factor"] == pytest.approx(0.01)
    p = plan("DPLS", "1/s", "iodp-logdb")
    assert p["variable"] is None and p["mapped_by"] == "context_unassigned" and p["factor"] == 1.0
    if not os.path.exists(_VC):
        pytest.skip("needs the pipeline/ folder of the repository")
    spec = importlib.util.spec_from_file_location("variable_coverage", _VC)
    vc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vc)
    assert vc.variable_of("DPLS", "DPLS", "1/s", "DLIS", "iodp-logdb") is None
    assert vc.variable_of("DPLS", "DPLS", "%", "LAS", "kgs") == "density_porosity"


def test_temperature_difference_is_scale_only():
    p = plan("DTMP", "DEGF", "kgs")                      # an absolute degF unit read as a difference
    assert p["variable"] == "differential_temperature" and p["unit"] == "delta_degC"
    assert p["factor"] == pytest.approx(5 / 9) and p["offset"] == 0.0
    assert C.apply_linear(9.0, p["base_factors"]) == pytest.approx(5.0)
    p = plan("DEL TEMP", "DEG", "kgs")                   # documented rule: DEG in these files is degF
    assert p["variable"] == "differential_temperature" and p["unit_rule"]["unit"] == "delta_degF"
    assert p["factor"] == pytest.approx(5 / 9) and p["offset"] == 0.0
    p = plan("DTMP", "degF", "kgs", units="field")       # field preset: degF difference, unchanged
    assert p["unit"] == "delta_degF" and p["factor"] == pytest.approx(1.0) and p["offset"] == 0.0
    assert C.convert_value(1.0, "delta_degF", "delta_degC", "temperature_difference") == pytest.approx(5 / 9)
    assert M.to_var_unit(9.0, "degF", "delta_degC", "temperature_difference") == pytest.approx(5.0)
    assert M.to_var_unit(9.0, "delta_degF", "delta_degC", "temperature_difference") == pytest.approx(5.0)
    assert M.to_var_unit(50.0, "degF", "degC", "temperature") == pytest.approx(10.0)   # absolute scale keeps its offset


def test_volve_total_gas_in_euc_is_a_fraction():
    p = plan("TOTGAS_AVG", "Euc", "volve", fmt="WITSML")
    assert p["variable"] == "total_gas" and p["unit_rule"]["unit"] == "v/v" and p["factor"] == pytest.approx(100.0)
    assert M.assumed_unit("TOTGAS_AVG", "Euc") == "v/v"
