# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Rebuilding the candidates must keep Daniel's decisions and the proposals (pipeline/candidates_merge.py)."""
import os
import sys

import pytest

_PIPE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline")
if not os.path.exists(os.path.join(_PIPE, "candidates_merge.py")):
    pytest.skip("needs the pipeline/ folder of the repository", allow_module_level=True)
sys.path.insert(0, _PIPE)
from candidates_merge import merge, read_rows, write_rows  # noqa: E402

NEW_COLS = ["mnemonic", "proposed_variable", "status", "n_files", "decision"]
OLD_COLS = NEW_COLS + ["propuesta", "confianza", "lote", "impacto", "evidencia", "source_pass", "std_files"]


def old(m, v, **kw):
    r = dict(mnemonic=m, proposed_variable=v, status="unmapped", n_files="3", decision="", propuesta="", confianza="",
             lote="", impacto="", evidencia="", source_pass="diccionario", std_files="")
    r.update(kw)
    return r


def new(m, v, n="5"):
    return dict(mnemonic=m, proposed_variable=v, status="unmapped", n_files=n, decision="")


def test_rebuild_keeps_decisions_and_proposals(tmp_path):
    prev = [
        old("RILD", "res_deep", decision="res_deep", propuesta="res_deep", confianza="alta", lote="1", impacto="9",
            evidencia="u: OHM-M"),
        old("rilm", "res_medium", propuesta="res_medium", confianza="media", lote="2"),
        old("ccl", "", propuesta="new_variable:casing_collar_locator", lote="3", source_pass="diccionario"),
        old("PERIOD", "", decision="ignore:texto", propuesta="ignore:texto", source_pass="estandarizacion", std_files="292"),
        old("DEPTH_WMSF", "", propuesta="new_variable:depth_below_seafloor", source_pass="estandarizacion"),
        old("GONE", "gr", propuesta="gr", lote="2"),
        old("PROMOTED", "rop", decision="rop", propuesta="rop", lote="1"),
    ]
    p = tmp_path / "prev.csv"
    write_rows(p, prev, OLD_COLS)
    prev_rows, prev_cols = read_rows(p)
    rebuilt = [new("RILD", "res_deep", "4758"), new("RILM", "res_medium"), new("CCL", "casing_collar_locator"),
               new("DEPTH_WMSF", ""), new("NEWONE", "gr")]
    rows, cols, retired = merge(rebuilt, NEW_COLS, prev_rows, prev_cols)
    by = {r["mnemonic"].upper(): r for r in rows}
    # decision and proposal survive; values produced by the rebuild are refreshed
    assert by["RILD"]["decision"] == "res_deep" and by["RILD"]["propuesta"] == "res_deep"
    assert by["RILD"]["confianza"] == "alta" and by["RILD"]["evidencia"] == "u: OHM-M" and by["RILD"]["n_files"] == "4758"
    assert by["RILM"]["lote"] == "2"                               # matched case-insensitively
    assert by["CCL"]["propuesta"] == "new_variable:casing_collar_locator"   # proposed variable changed: matched by mnemonic
    assert by["DEPTH_WMSF"]["source_pass"] == "ambos"
    assert by["NEWONE"]["decision"] == "" and by["NEWONE"]["source_pass"] == "diccionario"
    # rows the rebuild no longer produces: kept if they carry a decision or come from the standardization
    assert by["PERIOD"]["decision"] == "ignore:texto" and by["PERIOD"]["en_ultima_reconstruccion"] == "no"
    assert by["PROMOTED"]["decision"] == "rop"
    assert "GONE" not in by and [r["mnemonic"] for r in retired] == ["GONE"]
    assert len(rows) + len(retired) == len(set(r["mnemonic"].upper() for r in prev) | {r["mnemonic"] for r in rebuilt})
    for c in ("propuesta", "confianza", "lote", "impacto", "evidencia", "decision", "std_files", "en_ultima_reconstruccion"):
        assert c in cols


def test_rebuild_never_overwrites_a_decision_with_an_empty_one():
    prev = [old("GR1", "gr", decision="gr")]
    rows, _, _ = merge([new("GR1", "gr")], NEW_COLS, prev, OLD_COLS)
    assert rows[0]["decision"] == "gr"


def test_merging_twice_gives_the_same_file(tmp_path):
    prev = [old("A", "gr", decision="gr", propuesta="gr"), old("B", "", propuesta="unknown", source_pass="estandarizacion")]
    r1, c1, _ = merge([new("A", "gr")], NEW_COLS, prev, OLD_COLS)
    r2, c2, _ = merge([new("A", "gr")], NEW_COLS, r1, c1)
    assert c1 == c2 and r1 == r2
