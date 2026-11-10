# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Recipes of 7 Nov 2026: consistent with the registry, and the new process forms (loose LAS files, several zips,
zip inside a zip, unreadable items listed instead of stopping). No external network: a local HTTP server serves the
fixtures. When the real originals are on this machine (~/data/candidatos-completos), they are verified and processed whole."""
import hashlib, http.server, io, json, os, sys, threading, zipfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
import owd
from owd import recipes as R

NEW = ("mendeley-adriatic-sonic-las", "usgs-npra-ofr-99-15", "gdr-glade-cbl", "gdr-glade-wireline", "edx-secarb-cranfield-logs",
       "gdr-srp-forge-inel1", "tno-nieuwerkerk-well-logs", "4tu-delft-del-gt-logs", "force-2020",
       "gdr-forge-58-32-pason", "gdr-cubo-esh1-depth", "gdr-cubo-esh1-time-jun-jul", "gdr-cubo-esh1-time-jul-sep", "edx-cranfield-other-wells", "zenodo-italia-pesaro-fano", "ags-dig-2014-0002", "purr-kentland-well-logs", "gdr-egs-collab-wireline", "edx-ibdp-well-info")
LAS = """~Version
VERS.   2.0 :
WRAP.   NO  :
~Well
STRT.m  100.0 :
STOP.m  100.2 :
STEP.m  0.1 :
NULL.   -999.25 :
WELL.   {well} : well name
~Curve
DEPT.m      : Depth
GR  .GAPI   : Gamma ray
~A
100.0  50.0
100.1  60.0
100.2  -999.25
"""
BROKEN = "~Version\nnot a LAS file {well}\n"  # any item the reader cannot read


def test_new_recipes_match_the_registry():
    rec = R.recipes()
    for k in NEW:
        r, d = rec[k], owd.DATASETS[k]
        assert r["id"] == k and r["license"] == d["spdx"], k
        assert d["citation"] and d["url"].startswith("https://") and d["policy"] in ("copy", "recipe"), k
        assert r.get("tested", "yes") in ("yes", "untested-large"), k
        if k != "force-2020":  # its reader was tested in the MVP; only the recipe download is untested
            assert (r.get("tested") == "untested-large") == (d["tested"] is False), k
        names = [f["name"] for f in r["files"]]
        p = r["process"]
        assert all(n in names for n in (p.get("files") or ([p["file"]] if p.get("file") else names))), k
        for f in r["files"]:
            assert f["bytes"] > 0 and R._domain_allowed(f["url"], r["domains"]), (k, f["name"])
            assert "/" not in f["name"], (k, f["name"])


@pytest.fixture
def server(tmp_path, monkeypatch):
    root = tmp_path / "web"; root.mkdir()

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(root), **k)
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    dr = tmp_path / "recipes"; dr.mkdir()
    monkeypatch.setattr(R, "RECIPES_DIR", dr)
    monkeypatch.setenv("OWD_DATA", str(tmp_path / "data"))
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def serve(id, blobs, process):
        """Publish blobs {name: bytes} and write a recipe for id (the real one, with local URLs and checksums)."""
        real = json.loads((R.Path(owd.__file__).parent / "recipes.d" / f"{id}.json").read_text())
        files = []
        for i, (name, data) in enumerate(blobs.items()):
            (root / f"f{i}").write_bytes(data)
            files.append({"name": name, "url": f"{base}/f{i}", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        (dr / f"{id}.json").write_text(json.dumps(dict(real, domains=["127.0.0.1"], files=files, process=process)))
    yield serve, tmp_path
    srv.shutdown()


def zipped(members):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for n, t in members.items():
            z.writestr(n, t)
    return b.getvalue()


def metas(done):
    return [json.loads(open(p.rsplit(".", 1)[0] + ".json").read()) for p in done]


def test_las_files_process(server):
    pytest.importorskip("lasio")
    serve, _ = server
    serve("mendeley-adriatic-sonic-las", {"Giove-1.las": LAS.format(well="GIOVE-1").encode(), "Giove-2.las": LAS.format(well="GIOVE-2").encode()},
          {"type": "las_files"})
    done = owd.get("mendeley-adriatic-sonic-las", notify=lambda *a: None)
    m = metas(done)
    assert sorted(x["original_file"] for x in m) == ["Giove-1.las", "Giove-2.las"]
    assert all(x["rows"] == 3 and x["license"] == "CC-BY-4.0" and x["original_verified"] for x in m)


def test_several_zips_and_unreadable_items_are_listed(server):
    pytest.importorskip("lasio")
    serve, tmp = server
    a = zipped({"F1 Well Logs/las/a.las": LAS.format(well="F1"), "F1 Well Logs/a.pdf": "x"})
    b = zipped({"F2 Well Logs/las/b.las": LAS.format(well="F2"), "F2 Well Logs/las/bad.las": BROKEN.format(well="F2")})
    serve("edx-secarb-cranfield-logs", {"F1 Well Logs.zip": a, "F2 Well Logs.zip": b},
          {"type": "zip_members", "files": ["F1 Well Logs.zip", "F2 Well Logs.zip"], "pattern": "(?i)\\.las$", "skip_unreadable": True})
    done = owd.get("edx-secarb-cranfield-logs", notify=lambda *a: None)
    m = metas(done)
    assert sorted((x["original_file"], x["member"]) for x in m) == [("F1 Well Logs.zip", "F1 Well Logs/las/a.las"),
                                                                   ("F2 Well Logs.zip", "F2 Well Logs/las/b.las")]
    assert sorted(os.path.basename(p).split(".")[0] for p in done) == ["F1_Well_Logs__a", "F2_Well_Logs__b"]
    fails = json.loads((tmp / "data" / "edx-secarb-cranfield-logs" / "standard" / "_failures.json").read_text())
    assert [f["item"] for f in fails] == ["F2 Well Logs.zip/F2 Well Logs/las/bad.las"]


def test_unreadable_item_stops_without_skip(server):
    pytest.importorskip("lasio")
    serve, _ = server
    serve("gdr-glade-cbl", {"Cement Bond Logs.zip": zipped({"x/bad.las": BROKEN.format(well="W")})},
          {"type": "zip_members", "file": "Cement Bond Logs.zip", "pattern": "(?i)\\.las$"})
    with pytest.raises(Exception):
        owd.get("gdr-glade-cbl", notify=lambda *a: None)


def test_import_one_of_several_processes_what_is_there(server, tmp_path):
    pytest.importorskip("lasio")
    serve, _ = server
    blobs = {"Giove-1.las": LAS.format(well="GIOVE-1").encode(), "Giove-2.las": LAS.format(well="GIOVE-2").encode()}
    serve("mendeley-adriatic-sonic-las", blobs, {"type": "las_files"})
    f = tmp_path / "Giove-2.las"; f.write_bytes(blobs["Giove-2.las"])
    said = []
    done = owd.import_data("mendeley-adriatic-sonic-las", f, notify=said.append)
    assert [x["original_file"] for x in metas(done)] == ["Giove-2.las"]
    assert any("Giove-1.las is not in" in s for s in said)


def test_nested_zip_members(server):
    pytest.importorskip("lasio")
    serve, _ = server
    inner = zipped({"original_las_files_TNO/A-01.las": LAS.format(well="A-01"), "original_las_files_TNO/B-02.las": LAS.format(well="B-02"),
                    "original_las_files_TNO/notes.txt": "x"})
    outer = zipped({"original_las/": "", "original_las/original_las_files_TNO.zip": inner})
    serve("tno-nieuwerkerk-well-logs", {"original_las.zip": outer},
          {"type": "nested_zip_members", "file": "original_las.zip", "inner": "(?i)\\.zip$", "pattern": "(?i)\\.las$", "skip_unreadable": True})
    done = owd.get("tno-nieuwerkerk-well-logs", notify=lambda *a: None)
    m = metas(done)
    assert sorted(x["member"] for x in m) == ["original_las_files_TNO/A-01.las", "original_las_files_TNO/B-02.las"]
    assert all(x["inner"] == "original_las/original_las_files_TNO.zip" and x["license"] == "CC0-1.0" for x in m)
    assert not (R.folder("tno-nieuwerkerk-well-logs") / "tmp").exists()


REAL = os.path.expanduser("~/data/candidatos-completos")
CASES = [("mendeley-adriatic-sonic-las", "mendeley-adriatic-sonic-las", 12), ("usgs-npra-ofr-99-15", "usgs-npra-ofr-99-15", 19),
         ("gdr-srp-forge-inel1", "gdr-srp-forge-inel1", 18), ("gdr-glade-cbl", "gdr-glade-well-logs", 2),
         ("edx-secarb-cranfield-logs", "edx-secarb-cranfield-logs", 37)]


@pytest.mark.parametrize("id,folder,n", CASES)
def test_real_originals_are_verified_and_processed(tmp_path, monkeypatch, id, folder, n):
    r = R.recipe(id)
    src = os.path.join(REAL, folder, "originales")
    paths = [os.path.join(src, f["name"]) if os.path.exists(os.path.join(src, f["name"])) else os.path.join(src, f["name"].replace("_", "/", 1))
             for f in r["files"]]
    if not all(os.path.exists(p) for p in paths):
        pytest.skip("originals not on this machine")
    pytest.importorskip("lasio")
    monkeypatch.setenv("OWD_DATA", str(tmp_path))
    d = R.folder(id) / "original"; d.mkdir(parents=True)
    for f, p in zip(r["files"], paths):
        assert R.verify(p, f) == [], f["name"]
        os.symlink(p, d / f["name"])
    done = R.process(id, notify=lambda *a: None)
    assert len(done) == n


DEPTH_CSV = ("Depth(ft),Depth(m),ROP(1 ft),ROP(1 m),weight on bit (k-lbs),weight on bit (kg),Pump Press (psi),Pump Press (KPa),"
             "Hookload (k-lbs),Hookload (kg),Flow In (gal/min),Flow In(liters/min)\n"
             "100.0,30.48,50.0,15.24,10.0,4535.9,1000.0,6894.76,100.0,45359.2,500.0,1892.7\n"
             "101.0,30.78,55.0,16.76,11.0,4989.5,1010.0,6963.70,101.0,45812.8,500.0,1892.7\n")


def test_depth_csv_recipe(server):
    """Depth-indexed Pason CSV with metric copy columns (GDR 1113): index in m, field-unit columns kept and converted."""
    serve, _ = server
    serve("gdr-forge-58-32-pason", {"Well_58-32_processed_pason_log.csv": DEPTH_CSV.encode()}, {"type": "csv_files"})
    done = owd.get("gdr-forge-58-32-pason", notify=lambda *a: None)
    m = metas(done)[0]
    assert m["rows"] == 2 and m["unit"]["hookload"] == "kN" and m["unit"]["flow_in"] == "L/min"
    import pandas as pd
    df = pd.read_parquet(done[0]) if done[0].endswith(".parquet") else pd.read_csv(done[0], index_col=0)
    assert abs(df.index[0] - 30.48) < 1e-9 and abs(df["hookload"].iloc[0] - 444.822) < 0.01
    assert not any("(kg)" in c or "liters" in c for c in df.columns)


REAL_PASON = [("gdr-forge-58-32-pason", "recetas-2026-11-07-gdr1113", 1), ("gdr-cubo-esh1-depth", "recetas-2026-11-07-gdr1849", 1),
              ("gdr-cubo-esh1-time-jul-sep", "recetas-2026-11-07-gdr1849", None)]


@pytest.mark.parametrize("id,case,n", REAL_PASON)
def test_real_pason_originals(tmp_path, monkeypatch, id, case, n):
    """The downloads of 7 Nov 2026, when OWD_TEST_DATA points to them (spaces and brackets in names written as _)."""
    import re as _re
    r = R.recipe(id)
    f = r["files"][0]
    p = os.path.join(os.environ.get("OWD_TEST_DATA", "/nonexistent"), case, "bruto", _re.sub(r"[^A-Za-z0-9._-]", "_", f["name"]))
    if not os.path.exists(p):
        pytest.skip("needs OWD_TEST_DATA")
    assert R.verify(p, f) == []
    monkeypatch.setenv("OWD_DATA", str(tmp_path))
    d = R.folder(id) / "original"; d.mkdir(parents=True)
    os.symlink(p, d / f["name"])
    done = R.process(id, notify=lambda *a: None)
    assert len(done) == n if n else len(done) > 30


def test_integer_las_null_is_written(server):
    """A LAS NULL read as an integer (numpy int64 in df.attrs) used to stop the Parquet write (GLADE wireline, 7 Nov 2026)."""
    pytest.importorskip("lasio")
    serve, _ = server
    las = LAS.format(well="W").replace("NULL.   -999.25 :", "NULL.   -999 :").replace("-999.25", "-999")
    serve("mendeley-adriatic-sonic-las", {"Giove-1.las": las.encode()}, {"type": "las_files"})
    done = owd.get("mendeley-adriatic-sonic-las", notify=lambda *a: None)
    assert len(done) == 1 and metas(done)[0]["rows"] == 3
