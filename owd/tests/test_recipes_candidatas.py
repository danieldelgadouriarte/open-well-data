# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Recipes of 6 Nov 2026 (zenodo-italia-info, zenodo-italia-taboo, gdr-tuscarora-las): consistent with the registry, and the
zip_members process reads LAS in metres and in feet. No external network: a local HTTP server serves small zips. When the
real originals are on this machine (~/data/candidatos-completos), they are checked and processed whole."""
import hashlib, http.server, io, json, os, sys, threading, zipfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
import owd
from owd import recipes as R

NEW = ("zenodo-italia-info", "zenodo-italia-taboo", "gdr-tuscarora-las")
LAS_M = """~Version
VERS.   2.0 :
WRAP.   NO  :
~Well
STRT.m  1600.0 :
STOP.m  1600.3048 :
STEP.m  0.1524 :
NULL.   -999.25 :
WELL.   ACERNO_001 : well name
~Curve
DEPT.m      : Depth
GR  .GAPI   : Gamma ray
~A
1600.0    50.0
1600.1524 60.0
1600.3048 -999.25
"""
LAS_F = LAS_M.replace(".m ", ".F ").replace("1600.1524", "1000.5").replace("1600.3048", "1001.0").replace("1600.0", "1000.0").replace("STEP.F  0.1524", "STEP.F  0.5")


def test_new_recipes_match_the_registry():
    rec = R.recipes()
    for k in NEW:
        r, d = rec[k], owd.DATASETS[k]
        assert r["id"] == k and r["level"] == "A" and r["license"] == d["spdx"] == "CC-BY-4.0"
        assert d["policy"] == "copy" and d["citation"] and d["url"].startswith("https://")
        assert r["process"]["type"] == "zip_members" and r["process"]["file"] in [f["name"] for f in r["files"]]
        for f in r["files"]:
            assert f["bytes"] > 0 and len(f["sha256"]) == 64 and R._domain_allowed(f["url"], r["domains"])


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
    yield f"http://127.0.0.1:{srv.server_address[1]}", root, dr
    srv.shutdown()


@pytest.mark.parametrize("id,las,members", [
    ("zenodo-italia-info", LAS_M, ["INFO_well_logs_v.1.0/LAS/ACERNO_001.las", "INFO_well_logs_v.1.0/CSV/ACERNO_001/ACERNO_001_GR.csv"]),
    ("gdr-tuscarora-las", LAS_F, ["LAS Files/4702900086.LAS", "LAS Files/README.txt"]),
])
def test_zip_members_process_reads_only_the_las(server, id, las, members):
    import pytest as _p
    _p.importorskip("lasio")
    base, root, dr = server
    real = json.loads((R.Path(owd.__file__).parent / "recipes.d" / f"{id}.json").read_text())
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr(members[0], las)
        z.writestr(members[1], "DEPTH,GR\n1,2\n")
    data = b.getvalue()
    name = real["files"][0]["name"]
    (root / "f.zip").write_bytes(data)
    rec = dict(real, domains=["127.0.0.1"], files=[{"name": name, "url": base + "/f.zip", "bytes": len(data),
                                                   "sha256": hashlib.sha256(data).hexdigest()}])
    (dr / f"{id}.json").write_text(json.dumps(rec))
    done = owd.get(id, notify=lambda *a: None)
    assert len(done) == 1
    meta = json.loads(open(done[0].rsplit(".", 1)[0] + ".json").read())
    assert meta["rows"] == 3 and meta["license"] == "CC-BY-4.0" and meta["original_verified"] is True
    assert meta["member"] == members[0]
    assert "Delgado-Uriarte" in meta["open_well_data"]


REAL = os.path.expanduser("~/data/candidatos-completos")
CASES = [("zenodo-italia-info", "zenodo-italia-legacy-logs", 25), ("zenodo-italia-taboo", "zenodo-italia-legacy-logs", 29),
         ("gdr-tuscarora-las", "gdr-tuscarora-las", 90)]


@pytest.mark.parametrize("id,folder,n", CASES)
def test_real_original_is_verified_and_processed(tmp_path, monkeypatch, id, folder, n):
    r = R.recipe(id)
    f = os.path.join(REAL, folder, "originales", r["files"][0]["name"])
    if not os.path.exists(f):
        pytest.skip("original not on this machine")
    pytest.importorskip("lasio")
    assert R.verify(f, r["files"][0]) == []
    monkeypatch.setenv("OWD_DATA", str(tmp_path))
    done = owd.import_data(id, f, notify=lambda *a: None)
    assert len(done) == n
