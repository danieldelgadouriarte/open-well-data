"""WAPIMS well header recipe (v1.1): the geojson_table process, attribution and licence, without network."""
import json

import pytest

from owd import recipes as R, registry

ID = "wapims-wa-petroleum-wells"
ATTR = "© State of Western Australia (Department of Mines, Petroleum and Exploration) 2026"
DERIV = "Based on Department of Mines, Petroleum and Exploration material"


def test_recipe_attribution_and_licence():
    r = R.recipe(ID)
    assert r["license"] == "CC-BY-4.0" and r["download"] == "auto"
    assert r["attribution"] == ATTR and r["attribution_derived"] == DERIV
    assert ATTR in r["notes"] and DERIV in r["notes"]
    assert registry.DATASETS[ID]["owd_copy_spdx"] == "CC-BY-NC-4.0"
    assert ATTR in registry.DATASETS[ID]["citation"] and DERIV in registry.DATASETS[ID]["citation"]


def _layer(features, cut=False):
    g = {"type": "FeatureCollection", "features": features}
    if cut:
        g["exceededTransferLimit"] = True
    return json.dumps(g)


def test_geojson_table(tmp_path, monkeypatch):
    pd = pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    monkeypatch.setenv("OWD_DATA", str(tmp_path))
    d = R.folder(ID) / "original"
    d.mkdir(parents=True)
    feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [114.0, -22.0]},
              "properties": {"uwi": "W000001", "well_name": "A 1", "spud_date": 0, "rig_release_date": None,
                             "extract_date": 86400000 + 28800000}},
             {"type": "Feature", "geometry": None,
              "properties": {"uwi": "W000002", "well_name": "B 1", "spud_date": None, "rig_release_date": 1800000,
                             "extract_date": 86400000}}]
    (d / R.recipe(ID)["process"]["file"]).write_text(_layer(feats), encoding="utf-8")
    out = R.process(ID, notify=lambda *a: None)
    df = pd.read_parquet(out[0])
    assert list(df["uwi"]) == ["W000001", "W000002"]
    assert df.loc[0, "spud_date"] == "1970-01-01" and df.loc[0, "extract_date"] == "1970-01-02"
    assert df.loc[1, "rig_release_date"] == "1970-01-01"
    assert df.loc[0, "lon_wgs84"] == 114.0 and df.loc[0, "lat_wgs84"] == -22.0
    assert pd.isna(df.loc[1, "lon_wgs84"])


def test_geojson_table_cut_layer(tmp_path, monkeypatch):
    monkeypatch.setenv("OWD_DATA", str(tmp_path))
    d = R.folder(ID) / "original"
    d.mkdir(parents=True)
    (d / R.recipe(ID)["process"]["file"]).write_text(_layer([], cut=True), encoding="utf-8")
    with pytest.raises(R.RecipeError):
        R.process(ID, notify=lambda *a: None)


def test_ogl_alberta_copy_licence():
    """OGL-Alberta allows copying and adapting with attribution: OWD's copy is CC BY-NC 4.0 with the source attribution."""
    d = registry.DATASETS["ags-dig-2014-0002"]
    assert d["spdx"] == "LicenseRef-OGL-Alberta" and d["owd_copy_spdx"] == "CC-BY-NC-4.0"
    assert d["attribution"] == registry.OGL_ALBERTA_ATTRIBUTION
    assert "Open Government Licence – Alberta" in d["attribution"] and "Alberta Geological Survey" in d["attribution"]
