# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Fast tests without network. Real-data tests run only when OWD_TEST_DATA points to a folder with the original files."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest, owd
from owd import standard
DATA = os.environ.get("OWD_TEST_DATA", "/nonexistent")

def test_alias():
    assert owd.canonical("HKLD") == "hookload"
    assert owd.canonical("Hook Load (klbs)") == "hookload"
    assert owd.canonical("DTC") == "dt"
    assert owd.canonical("does-not-exist") is None

def test_unique_aliases():
    seen = {}
    for c in owd.CHANNELS:
        for a in c["aliases"].split("|"):
            assert seen.setdefault(a.lower(), c["canonical"]) == c["canonical"], a

def test_registry():
    assert len(owd.DATASETS) == 32  # 9 nov 2026: + wapims-wa-petroleum-wells
    for k, d in owd.DATASETS.items():
        assert d["policy"] in ("copy", "recipe", "link"), k
        assert d["license"] and d["url"].startswith("http"), k

def test_search():
    assert any(f["id"] == "usgs-namss" for f in owd.search("namss"))

F = os.path.join(DATA, "pason16b_10s_extracto.csv")
@pytest.mark.skipif(not os.path.exists(F), reason="needs OWD_TEST_DATA")
def test_forge_real():
    df = owd.load("utah-forge-16b", F)
    assert df.attrs["unit"]["surface_torque"] == "kN.m"
    assert df.attrs["original"]["surface_torque"]["unit"] == "kft_lb"
    assert df.attrs["license"] == "CC BY 4.0"

Z = os.path.join(DATA, "Rigid.zip")
@pytest.mark.skipif(not os.path.exists(Z), reason="needs OWD_TEST_DATA")
def test_gdr1329_without_units_is_not_labelled():
    df = owd.load("gdr-1329-pdc-granite", Z, member="Rigid/R.4B-120RPM.txt")
    assert "Torque" in df.columns and "surface_torque" not in df.columns

Q = DATA
@pytest.mark.skipif(not os.path.exists(f"{Q}/owd-3w"), reason="needs OWD_TEST_DATA")
def test_3w_real():
    df = owd.load("3w", f"{Q}/owd-3w/bruto/WELL-00002_20131104004101.parquet")
    assert df.attrs["unit"]["p_tpt"] == "kPa" and df.attrs["original"]["p_tpt"]["unit"] == "Pa"
    assert 1e4 < df["p_tpt"].median() < 1e5          # ~18,800 kPa in this well

@pytest.mark.skipif(not os.path.exists(f"{Q}/owd-rigwatch-zip"), reason="needs OWD_TEST_DATA")
def test_rigwatch_real():
    df = owd.load("iodp-rigwatch", f"{Q}/owd-rigwatch-zip/bruto/content", member="U1601C-LOG-SAMPLE.csv", nrows=5000)
    assert df.attrs["unit"]["hookload"] == "kN" and df.attrs["original"]["hookload"]["unit"] == "klbs"
    assert str(df.index.tz) == "UTC"

@pytest.mark.skipif(not os.path.exists(f"{Q}/owd-force2020"), reason="needs OWD_TEST_DATA")
def test_force_real():
    df = owd.load("force-2020", f"{Q}/owd-force2020/bruto/content", member="Force_2020_all_wells_train_test_blind_hidden_final/15_9-13.las")
    assert {"gr", "rhob", "dt"} <= set(df.columns)
    assert 1.5 < df["rhob"].median() < 3.0

def test_different_unit_is_not_labelled():
    assert owd.standard.equivalent_unit("GAPI") == "gAPI"
    assert owd.standard.equivalent_unit("ft/h") is None

@pytest.mark.skipif(not os.path.exists(f"{Q}/mseel"), reason="needs OWD_TEST_DATA")
def test_mseel_odd_unit_is_not_labelled():
    df = owd.load("mseel", f"{Q}/mseel/bruto/mip_4h.zip", inner="MIP_4H/GandG_and_Reservoir_Engineering/MIP_4H_Survey_and_well_logs.zip",
                  member="MIP-4H Survey and well logs/finalmipu4hgamma.las")
    assert "GR" in df.columns and "gr" not in df.columns      # unit "aapi": never guessed

def test_bilingual_search():
    # Spanish, English, with and without accents: same result.
    ids = lambda q: sorted(f["id"] for f in owd.search(q))
    assert ids("sísmica 3D") == ids("seismic 3d") == ids("sismica 3d")
    assert ids("perforación") == ids("drilling")
    assert ids("pozos noruega") == ids("wells norway")
    assert ids("almacenamiento de CO2") == ids("CCS")


def test_cite():
    assert "Delgado-Uriarte" in owd.cite()
    c = owd.cite("utah-forge-16b")
    assert "McLennan" in c and "Open Well Data" in c
