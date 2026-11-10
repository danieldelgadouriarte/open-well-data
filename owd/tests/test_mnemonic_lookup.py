# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Mnemonic lookup (owd.mnemonic_lookup) and its MCP tool."""
import json

import pytest

from owd import mnemonic_lookup as ML


@pytest.fixture(scope="module")
def tables():
    return ML.load()


def test_lookup_verified_mnemonic(tables):
    r = ML.lookup("hkla", tables=tables)
    assert r["mnemonic"] == "HKLA" and r["variable"] == "hookload"
    assert r["variable_info"]["unit"] == "kN" and r["variable_info"]["family"] == "drilling"
    assert r["status"] == "verified_by_data"
    ev = next(e for e in r["evidence"] if e["variable"] == "hookload")
    assert ev["n_files"] > 0 and ev["n_datasets"] >= 1 and ev["typical_range"]["unit"] == "kN"


def test_lookup_context_rule(tables):
    r = ML.lookup("RS", tables=tables)
    assert r["variable"] == "" and {"res_shallow", "rs"} <= set(r["candidates"]) and r["context_rules"]
    log = ML.lookup("RS", "ohm.m", "LAS", tables=tables)
    assert log["variable"] == "res_shallow" and log["how"] == "context rule"
    assert log["context_rule"]["unit_dimension"] == "resistivity"
    pvt = ML.lookup("RS", "", "PVT", tables=tables)
    assert pvt["variable"] == "rs" and "gas-oil ratio" in pvt["context_rule"]["note"]


def test_lookup_unknown(tables):
    r = ML.lookup("NOT_A_MNEMONIC_XYZ", tables=tables)
    assert not r["found"] and r["variable"] == ""


def test_entries_cover_listed_mnemonics(tables):
    ents = {e["m"]: e for e in ML.entries(tables)}
    assert "HKLA" in ents and any(r.get("v") == "hookload" for r in ents["HKLA"]["r"])
    assert "ctx" in ents["RS"]
    variables = tables[0]
    for v in variables.values():
        for m in v["mnemonics"].split("|"):
            if m:
                assert m.upper() in ents


def test_mcp_tool():
    pytest.importorskip("mcp")
    from owd import mcp_server
    r = json.loads(mcp_server.lookup_mnemonic("RS", "ohm.m", "DLIS"))
    assert r["variable"] == "res_shallow" and "how_to_cite" in r
