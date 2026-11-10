# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Recipes: download with byte and checksum verification, allowed domains, import and processing. No external network:
a local HTTP server serves a small zip in the RigWatch format."""
import hashlib, http.server, io, json, os, sys, threading, zipfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
import owd
from owd import recipes as R

CSV = ("DATETIME,Hook Load (kkgf),Depth Bit (mbrf)\n"
       "04/26/2023 16:15:00,100.0,5.0\n04/26/2023 16:15:01,101.0,5.1\n")


def zip_bytes():
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("U1309D-2-3.csv", CSV)
        z.writestr("OPSRIG-README.txt", "readme")
    return b.getvalue()


@pytest.fixture
def env(tmp_path, monkeypatch):
    data = zip_bytes()
    root = tmp_path / "web"; root.mkdir()
    (root / "data.zip").write_bytes(data)
    (root / "broken.zip").write_bytes(data[:-10])

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(root), **k)
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    dr = tmp_path / "recipes"; dr.mkdir()

    def write(url, domains=("127.0.0.1",), download="auto", sha=None):
        rec = {"id": "iodp-rigwatch", "version": 1, "level": "A", "license": "CC-BY-4.0", "source": "https://example.org",
               "terms": "https://creativecommons.org/licenses/by/4.0/", "download": download, "domains": list(domains),
               "files": [{"name": "data_by_expedition.zip", "url": url, "bytes": len(data),
                          "sha256": sha or hashlib.sha256(data).hexdigest()}],
               "process": {"type": "zip_members", "file": "data_by_expedition.zip", "pattern": "\\.csv$"}}
        (dr / "iodp-rigwatch.json").write_text(json.dumps(rec))
    monkeypatch.setattr(R, "RECIPES_DIR", dr)
    monkeypatch.setenv("OWD_DATA", str(tmp_path / "data"))
    yield base, write, data, tmp_path
    srv.shutdown()


def test_get_downloads_verifies_and_standardizes(env):
    base, write, _, tmp = env
    write(base + "/data.zip")
    done = owd.get("iodp-rigwatch", notify=lambda *a: None)
    assert len(done) == 1
    meta = json.loads(open(done[0].rsplit(".", 1)[0] + ".json").read())
    assert meta["license"] == "CC-BY-4.0" and meta["original_verified"] is True
    assert meta["unit"]["hookload"] == "kN" and meta["rows"] == 2
    assert "Delgado-Uriarte" in meta["open_well_data"]


def test_truncated_download_is_not_used(env):
    base, write, _, tmp = env
    write(base + "/broken.zip")
    with pytest.raises(R.RecipeError, match="size"):
        owd.get("iodp-rigwatch", notify=lambda *a: None)
    assert not (tmp / "data" / "iodp-rigwatch" / "original" / "data_by_expedition.zip").exists()


def test_domain_outside_the_recipe(env):
    base, write, _, _ = env
    write(base + "/data.zip", domains=("zenodo.org",))
    with pytest.raises(R.RecipeError, match="domain"):
        owd.get("iodp-rigwatch", notify=lambda *a: None)


def test_manual_download_gives_instructions(env):
    base, write, _, _ = env
    write(base + "/data.zip", download="manual")
    with pytest.raises(R.RecipeError, match="owd import"):
        owd.get("iodp-rigwatch", notify=lambda *a: None)


def test_import_checks_checksum(env):
    base, write, data, tmp = env
    f = tmp / "data_by_expedition.zip"; f.write_bytes(data)
    write(base + "/data.zip", sha="0" * 64)
    with pytest.raises(R.RecipeError, match="sha256"):
        owd.import_data("iodp-rigwatch", f, notify=lambda *a: None)
    done = owd.import_data("iodp-rigwatch", f, notify=lambda *a: None, force=True)
    meta = json.loads(open(done[0].rsplit(".", 1)[0] + ".json").read())
    assert meta["original_verified"] is False


def test_published_recipes_are_consistent():
    for k, r in R.recipes().items():
        assert k == r["id"] and r["level"] and r["license"] and r["source"].startswith("http")
        if r["download"] == "auto":
            for f in r["files"]:
                # a live service (a layer the source updates every day, 9 Nov 2026) has no fixed size or checksum; it says so with live: true
                if f.get("live") is True:
                    assert R._domain_allowed(f["url"], r["domains"]) and "bytes" not in f and "sha256" not in f
                    continue
                # sha256 of a verified download; a large source not downloaded yet may carry only the md5 its repository publishes
                assert f["bytes"] > 0 and (len(f.get("sha256", "")) == 64 or (r.get("tested") == "untested-large" and len(f.get("md5", "")) == 32))
                assert R._domain_allowed(f["url"], r["domains"])


def test_volve_witsml_zip_direct(tmp_path, monkeypatch):
    """Direct reader of the Volve WITSML zip (4 Nov 2026): with the original zip available locally, the first logs are standardized."""
    import os, pytest
    from pathlib import Path
    zipo = Path(os.path.expanduser("~/data/volve/witsml.zip"))
    if not zipo.exists():
        pytest.skip("original Volve zip not available")
    import owd.recipes as R
    r = dict(R.recipe("volve")); r["process"] = dict(r["process"], file="witsml.zip", limit=12)
    (tmp_path / "original").mkdir(); (tmp_path / "original" / "witsml.zip").symlink_to(zipo)
    monkeypatch.setattr(R, "recipe", lambda id: r)
    monkeypatch.setattr(R, "folder", lambda id=None: tmp_path)
    done = R.process("volve", notify=lambda *a: None)
    assert len(done) >= 5
