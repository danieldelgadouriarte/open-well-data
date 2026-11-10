# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Context rules: the same mnemonic maps to different variables by declared unit and source format."""
import importlib.util
import os
import pytest

from owd.mnemonic_context import context_variable

_VC = os.path.join(os.path.dirname(__file__), "..", "pipeline", "variable_coverage.py")


def _variable_of():
    if not os.path.exists(_VC):
        pytest.skip("needs the pipeline/ folder of the repository")
    spec = importlib.util.spec_from_file_location("variable_coverage", _VC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.variable_of


def test_rs_and_depth_by_context():
    assert context_variable("RS", "ohm.m", "LAS") == "res_shallow"
    assert context_variable("RS", "", "PVT") == "rs"
    assert context_variable("DEPTH", "m", "WITSML") == "hole_depth"
    assert context_variable("DEPTH", "m", "LAS") == "md"
    assert context_variable("GR", "gAPI", "LAS") == ""          # no context rule: caller falls back to the name


def test_variable_of_uses_context():
    variable_of = _variable_of()
    assert variable_of("RS", "RS", "OHMM", "DLIS") == "res_shallow"
    assert variable_of("RS", "RS", None, "PVT") == "rs"
    assert variable_of("DEPTH", "DEPTH", "m", "WITSML") == "hole_depth"
    assert variable_of("DEPTH", "DEPTH", "m", "LAS") == "md"
    assert variable_of("GR", "GR", "gAPI", "LAS") == "gr"


def test_unit_rules_of_batch_4():
    """Batch 4 (7 Nov 2026): the declared unit separates the meanings; other units keep the name lookup or stay unassigned."""
    variable_of = _variable_of()
    assert context_variable("TOTGAS", "SCF/TON", "LAS") == "gas_content"
    assert variable_of("TOTGAS", "TOTGAS", "%", "LAS") == "total_gas"
    assert context_variable("C2", "ppm", "LAS") == "gas_c2"
    assert context_variable("C2", "in", "LAS") == "caliper"
    assert context_variable("CAL", "IN", "LAS") == "caliper"
