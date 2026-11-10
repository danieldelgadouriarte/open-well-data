# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Conversion engine, toolkit and local helper. Small fixtures in tests/data (see ORIGIN.txt), no network.

Parity with the browser engine: test_parity_with_javascript runs owd/tests/parity (needs `node`; skipped otherwise).
"""
import hashlib
import http.server
import io
import itertools
import json
import math
import os
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest

import owd
from owd import convert as C
from owd import recipes, toolkit

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
VOLVE = os.path.join(DATA, "synthetic_drilling.las")
SYN = os.path.join(DATA, "synthetic_mislabelled.las")
WRAP = os.path.join(DATA, "synthetic_wrapped.las")
TAB = os.path.join(DATA, "synthetic_table.csv")
FORGE = os.path.join(DATA, "synthetic_rig_1s.csv")
WITSML = os.path.join(DATA, "witsml_F-15S_1-2-1")
NOW = "2026-11-05T12:00:00Z"
T = C.tables()
IX = C.index()


def text(p):
    return C.decode(open(p, "rb").read())


def plan(name, unit="", fmt="LAS", units="si", names="owd"):
    return C.plan_channels([{"name": name, "unit": unit}], names, units, fmt)[0]


# ------------------------------------------------------------------ tables
def test_every_variable_unit_and_field_preset_resolves():
    for v, d in T["variables"].items():
        std = C.unit_row(d["unit"], d["dimension"])
        assert std is not None, f"{v}: {d['unit']} ({d['dimension']}) not in conversion_units.tsv"
        f = C.target_unit(v, "field")
        row = C.unit_row(f, d["dimension"])
        assert row is not None and row["base"] == std["base"], f"{v}: field unit {f}"
    for dim, u in T["presets"]["field"]["dimension"].items():
        assert C.unit_row(u, dim) is not None, (dim, u)


def test_unit_spellings_are_consistent():
    seen = {}
    for u in T["units"]:
        for s in [u["symbol"]] + u["aliases"]:
            k = (u["dimension"], s)
            assert k not in seen, f"{s} twice in {u['dimension']}"
            seen[k] = u
    by = {}
    for (dim, s), u in seen.items():          # case-insensitive spellings in one dimension must mean the same unit
        by.setdefault((dim, s.lower()), set()).add((u["base"], u["factor"], u["offset"]))
    bad = {k: v for k, v in by.items() if len(v) > 1}
    assert not bad, bad
    assert all(u["source"] for u in T["units"]), "every unit needs a source"


def test_number_expressions_are_safe():
    assert C.number_expression("0.3048*2") == 0.6096
    with pytest.raises(ValueError):
        C.number_expression("__import__('os')")


def test_spot_checks_against_known_constants():
    cv = C.convert_value
    close = lambda a, b: math.isclose(a, b, rel_tol=1e-12)
    assert close(cv(1, "psi", "kPa", "pressure"), 6.894757293168361)
    assert close(cv(1, "klbf", "kN", "force"), 4.4482216152605)
    assert close(cv(1, "kkgf", "kN", "force"), 9.80665)
    assert close(cv(1, "ft", "m", "length"), 0.3048)
    assert close(cv(1, "in", "mm", "length"), 25.4)
    assert close(cv(212, "degF", "degC", "temperature"), 100)
    assert close(cv(-40, "degF", "degC", "temperature"), -40)
    assert abs(cv(273.15, "K", "degC", "temperature")) < 1e-12
    assert close(cv(1, "ppg", "g/cm3", "density"), 0.119826427316897)
    assert close(cv(1, "lb/ft3", "kg/m3", "density"), 16.018463373960138)
    assert close(cv(1, "bbl", "m3", "volume"), 0.158987294928)
    assert close(cv(1, "gal/min", "L/min", "flow_rate"), 3.785411784)
    assert close(cv(1, "bbl/d", "m3/d", "flow_rate"), 0.158987294928)
    assert close(cv(1, "Mscf/d", "m3/d", "flow_rate"), 28.316846592)
    assert close(cv(1, "kft.lbf", "kN.m", "torque"), 1.3558179483314004)
    assert close(cv(1, "rad/s", "rpm", "angular_velocity"), 9.549296585513721)
    assert close(cv(1, "us/ft", "us/m", "slowness"), 3.280839895013123)
    assert close(cv(1, "mmho/m", "mS/m", "conductivity"), 1)
    assert close(cv(1, "hp", "kW", "power"), 0.7456998715822702)
    assert close(cv(1, "scf/bbl", "m3/m3", "ratio"), 0.17810760667903525)
    assert close(cv(1, "1/psi", "1/kPa", "compressibility"), 0.14503773773020923)
    assert close(cv(1, "cP", "mPa.s", "viscosity"), 1)
    assert close(cv(1, "gn", "m/s2", "acceleration"), 9.80665)
    assert close(cv(50, "pu", "v/v", "fraction"), 0.5)
    with pytest.raises(C.ConversionError):
        cv(1, "b/e", "API", "dimensionless")              # different quantities share a dimension, never converted


def test_round_trip_every_unit_pair():
    xs = [0.0, 1.0, -273.15, 3.14159, 1234.5678, 1e-9, 9.87654321e12, -42.0]
    n = 0
    groups = {}
    for u in T["units"]:
        groups.setdefault((u["dimension"], u["base"]), []).append(u)
    for units in groups.values():
        for a, b in itertools.product(units, units):
            fwd = [a["factor"], a["offset"], b["factor"], b["offset"]]
            back = [b["factor"], b["offset"], a["factor"], a["offset"]]
            for x in xs:
                y = C.apply_linear(C.apply_linear(x, fwd), back)
                assert math.isclose(y, x, rel_tol=1e-12, abs_tol=1e-9), (a["symbol"], b["symbol"], x, y)
            n += 1
    assert n > 500


def test_fmt_number_matches_javascript_rules():
    f = C.fmt_number
    assert [f(1e21), f(1e-7), f(1.5e-7), f(0.000001), f(123456789012345680000.0)] == \
        ["1e+21", "1e-7", "1.5e-7", "0.000001", "123456789012345680000"]
    assert [f(0.1 + 0.2), f(-0.0), f(100.0), f(2.5), f(1e16)] == ["0.30000000000000004", "0", "100", "2.5", "10000000000000000"]
    assert [f(0.125, 2), f(-0.125, 2), f(2.5, 1), f(4479.499999999999, 12)] == ["0.13", "-0.13", "3", "4479.5"]


# ------------------------------------------------------------------ mapping
def test_mapping_order_and_context():
    assert plan("hookload", "kN")["mapped_by"] == "standard_name"
    p = plan("HKLD", "KKGF")
    assert (p["variable"], p["mapped_by"], p["unit"], p["converted"]) == ("hookload", "dictionary", "kN", True)
    assert p["factor"] == 9.80665 and "Tonne-force" in p["unit_note"]
    assert plan("RS", "OHMM", "LAS")["variable"] == "res_shallow"
    assert plan("RS", "", "PVT")["candidate_variable"] == "rs"
    assert plan("DEPTH", "m", "LAS")["variable"] == "md"
    assert plan("DEPTH", "m", "WITSML")["variable"] == "hole_depth"
    assert plan("Hook Load (klbs)", "klbs", "table")["mapped_by"] in ("channel_alias", "dictionary")
    u = plan("NOT_A_CHANNEL", "m")
    assert u["variable"] is None and u["name"] == "NOT_A_CHANNEL" and u["unit"] == "m" and u["warnings"]


def test_mislabelled_units_are_never_converted_blindly():
    c = plan("CALI", "GAPI")
    assert c["status"] == "kept_unit_mismatch" and c["name"] == "CALI" and not c["converted"]
    assert "mislabelled" in c["warnings"][0]
    k = plan("CPAHX", "OHMM")
    assert k["status"] == "kept_unit_mismatch" and "reciprocal" in " ".join(k["warnings"])
    r = plan("RIGHEAVE", "", "WITSML", units="field")    # documented rule: unitless, values in metres
    assert r["unit_rule"]["unit"] == "m" and r["unit"] == "ft" and r["converted"]
    assert plan("SPM1", "")["status"] == "kept_no_unit"
    assert plan("ROP", "furlong/fortnight")["status"] == "kept_unknown_unit"


def test_targets_and_naming():
    assert plan("HKLD", "KKGF", units="field")["unit"] == "klbf"
    assert plan("HKLD", "KKGF", units={"hookload": "tonne"})["unit"] == "tonne"
    assert plan("CALI", "in", units="field")["unit"] == "in"
    assert plan("HKLD", "KKGF", names="original")["name"] == "HKLD"
    with pytest.raises(C.ConversionError):
        plan("HKLD", "KKGF", units={"hookload": "psi"})
    with pytest.raises(C.ConversionError):
        plan("HKLD", "KKGF", names="osdu")
    C.register_naming("upper-test", lambda v, o: v.upper())
    assert plan("HKLD", "KKGF", names="upper-test")["name"] == "HOOKLOAD"
    ps = C.plan_channels([{"name": "HKLD", "unit": "kN"}, {"name": "HKLA", "unit": "kN"}], "owd", "si", "LAS")
    assert [p["name"] for p in ps] == ["hookload", "hookload_2"]


def test_provenance_and_citation():
    out, prov = C.convert_text(text(VOLVE), to="csv", now=NOW, source=C.source_info("volve"))
    assert prov["generated_utc"] == NOW and prov["open_well_data"]["dictionary_version"] == IX.version
    assert prov["how_to_cite"]["open_well_data"] == "Processed with Open Well Data (Delgado-Uriarte, 2026), https://openwelldata.org"
    assert "@misc{openwelldata2026" in prov["how_to_cite"]["bibtex"]
    assert prov["source"]["citation"].startswith("Equinor ASA") and "Volve" in prov["source"]["license"]
    assert "contact@openwelldata.org" in prov["license_note"]
    assert prov["open_well_data"]["permalink"].startswith("https://openwelldata.org/convert/?names=owd&units=si&to=csv&v=")
    h = next(c for c in prov["channels"] if c["original_name"] == "HKLD")
    assert (h["name"], h["unit"], h["original_unit"], h["factor"]) == ("hookload", "kN", "KKGF", 9.80665)
    _, p2 = C.convert_text(text(VOLVE), to="csv", now=NOW)
    assert p2["source"]["license"] == "as stated by the source"
    assert not out.startswith("#")                     # no comment lines by default


# ------------------------------------------------------------------ files
def test_las_round_trip_si_field_si():
    lasio = pytest.importorskip("lasio")
    src = text(VOLVE)
    field, _ = C.convert_text(src, to="las", units="field", digits=0, now=NOW)
    back, _ = C.convert_text(field, to="las", units="si", digits=0, now=NOW)
    a, b = (lasio.read(io.StringIO(s), mnemonic_case="preserve") for s in (src, back))
    f = lasio.read(io.StringIO(field), mnemonic_case="preserve")
    assert "OWD_DICT" in f.params and "Processed with Open Well Data" in f.other
    assert math.isclose(f["hookload"][0], a["HKLD"][0] * 9806.65 / 4448.2216152605, rel_tol=1e-12)
    for orig, std in (("HKLD", "hookload"), ("SPPA", "spp"), ("ATMP", "downhole_temperature"), ("DEPT", "md")):
        x, y = a[orig], b[std]
        ok = ~(x != x)
        assert ((abs(y[ok] - x[ok] * (100 if orig == "SPPA" else 9.80665 if orig == "HKLD" else 1))
                 <= 1e-9 * abs(x[ok]) + 1e-9).all()), orig


def test_unconverted_values_are_copied_verbatim():
    # put the null token in the last column of the first data row
    src = text(VOLVE)
    head, rest = src.split("\n~A", 1)
    first, *others = rest.split("\n")[1:]
    toks = first.split()
    first = first[:first.rstrip().rfind(toks[-1])] + "-999.25"
    src = head + "\n~A" + rest.split("\n")[0] + "\n" + "\n".join([first] + others)
    out, prov = C.convert_text(src, to="las", now=NOW)
    data = out.split("~A\n")[1].splitlines()[0].split()
    assert data[3] == "46.6160"               # GR, renamed but not converted: token kept as written
    assert "-999.25" in data


def test_wrapped_las_and_semicolon_csv():
    out, prov = C.convert_text(text(WRAP), to="csv", now=NOW)
    lines = out.splitlines()
    assert lines[0].startswith("md [m],dt [us/ft],rhob [g/cm3]") and len(lines) == 4
    out, prov = C.convert_text(text(TAB), to="csv", now=NOW)
    assert out.splitlines()[0] == 'elapsed_time [h],hookload [kN],spp [kPa],flow_in [L/min],"Note, free text",log_temperature [degC]'
    assert '"say ""hi"""' in out
    w = " ".join(w for c in prov["channels"] for w in c["warnings"])
    assert "-999.25 appears 1 times" in w
    out2, _ = C.convert_text(text(TAB), to="csv", null="-999.25", now=NOW)
    assert out2.splitlines()[2].split(",")[1] == ""


def test_forge_csv_units_row():
    out, prov = C.convert_text(text(FORGE), to="csv", units="si", now=NOW)
    ch = {c["original_name"]: c for c in prov["channels"]}
    assert ch["Hookload"]["unit"] == "kN" and ch["Hookload"]["original_unit"] == "klbs"
    assert ch["Bit Depth"]["unit"] == "m"


def run_cli(*args):
    return recipes.main(list(args))


def test_cli_las_to_csv_with_sidecar(tmp_path):
    out = tmp_path / "v.csv"
    assert run_cli("convert", VOLVE, "--units", "field", "-o", str(out), "--dataset", "volve") == 0
    side = json.loads((tmp_path / "v.provenance.json").read_text())
    assert side["open_well_data"]["settings"]["units"] == "field" and side["source"]["dataset"] == "volve"
    assert side["input"]["sha256"] == hashlib.sha256(open(VOLVE, "rb").read()).hexdigest()
    assert out.read_text().splitlines()[0].startswith("md [ft],tvd [ft],rop_mean [ft/h]")   # ROP5 "5ft ROP": a 5 ft average (7 Nov 2026)
    assert run_cli("convert", VOLVE, "--comments", "-o", str(tmp_path / "c.csv")) == 0
    assert (tmp_path / "c.csv").read_text().startswith("# Processed with Open Well Data")


def test_cli_parquet_metadata(tmp_path):
    pq = pytest.importorskip("pyarrow.parquet")
    out = tmp_path / "v.parquet"
    assert run_cli("convert", VOLVE, "--names", "original", "--units", "si,hookload=klbf", "-o", str(out)) == 0
    t = pq.read_table(out)
    md = t.schema.metadata
    prov = json.loads(md[b"owd:provenance"])
    assert prov["open_well_data"]["settings"]["custom_units"] == {"hookload": "klbf"}
    assert "HKLD" in t.column_names and json.loads(md[b"owd:units"])["HKLD"] == "klbf"
    assert b"Processed with Open Well Data" in md[b"owd:citation"]


def test_cli_las_output_and_witsml(tmp_path):
    out = tmp_path / "s.las"
    assert run_cli("convert", SYN, "--to", "las", "-o", str(out)) == 0
    s = out.read_text()
    assert "~Other Information" in s and "kept_unit_mismatch" in s and "OWD_LINK" in s
    assert run_cli("convert", WITSML, "-o", str(tmp_path / "w.csv")) == 0
    side = json.loads((tmp_path / "w.provenance.json").read_text())
    assert side["input"]["format"] == "WITSML" and side["summary"]["labelled"] >= 10


def test_bad_options_fail_cleanly(tmp_path):
    assert run_cli("convert", VOLVE, "--units", "metric", "-o", str(tmp_path / "x.csv")) == 1
    with pytest.raises(C.ConversionError):
        C.convert_text("~Version\n VERS. 3.0 :\n~Curve\n DEPT.M :\n~A\n1\n")


def test_load_backward_compatible_and_with_units():
    df = owd.load("kgs-las", VOLVE)
    assert "hookload" in df.columns and df.attrs["unit"]["hookload"] == "kN" and "provenance" not in df.attrs
    f = owd.load("kgs-las", VOLVE, units="field")
    assert f.attrs["unit"]["hookload"] == "klbf" and f.index.name == "depth_ft"
    assert math.isclose(f["hookload"].iloc[0], df["hookload"].iloc[0] / 4.4482216152605, rel_tol=1e-12)
    o = owd.load("kgs-las", VOLVE, names="original")
    assert "HKLD" in o.columns and o.attrs["provenance"]["source"]["dataset"] == "kgs-las"


def test_convert_frame():
    import pandas as pd
    df = pd.DataFrame({"HKLD": [100.0, None], "note": ["a", "b"]}, index=pd.Index([1.0, 2.0], name="depth_m"))
    out, prov = owd.convert_frame(df, {"HKLD": "kkgf"}, units="field")
    assert list(out.columns) == ["hookload", "note"] and out.index.name == "depth_ft"
    assert math.isclose(out["hookload"].iloc[0], 100 * 9806.65 / 4448.2216152605, rel_tol=1e-12)
    assert out.attrs["provenance"]["channels"][1]["status"] == "unmapped"


def test_parse_units_option():
    assert toolkit.parse_units("field") == "field"
    assert toolkit.parse_units("field,spp=bar") == {"_default": "field", "spp": "bar"}
    assert toolkit.parse_units("hookload:klbf") == {"hookload": "klbf"}


# ------------------------------------------------------------------ downloads and the local helper
class _Files(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/closed.las":
            self.send_response(403)
            self.end_headers()
            return
        if self.path == "/login.las":
            body = b"<html>log in</html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()


@pytest.fixture
def files_server(tmp_path, monkeypatch):
    shutil.copy(VOLVE, tmp_path / "well.las")
    monkeypatch.setenv("OWD_DATA", str(tmp_path / "owd" / "data"))
    h = lambda *a, **k: _Files(*a, directory=str(tmp_path), **k)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_get_url_converts_and_reports_closed_sources(files_server, tmp_path):
    out = tmp_path / "o.las"
    assert run_cli("get", files_server + "/well.las", "--units", "field", "--to", "las", "-o", str(out)) == 0
    assert "hookload.klbf" in out.read_text()
    with pytest.raises(toolkit.SourceClosed, match="refuses automatic downloads"):
        toolkit.fetch_url(files_server + "/closed.las", notify=lambda *a: None)
    with pytest.raises(toolkit.SourceClosed, match="web page"):
        toolkit.fetch_url(files_server + "/login.las", notify=lambda *a: None)
    assert run_cli("get", files_server + "/closed.las") == 1


def _req(port, path, token=None, origin=None, method="GET", body=None, host=None):
    r = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=body, method=method)
    if token:
        r.add_header("Authorization", "Bearer " + token)
    if origin:
        r.add_header("Origin", origin)
    if host:
        r.add_header("Host", host)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def test_local_helper_security_and_fetch(files_server):
    from owd import helper
    srv = helper.Helper(0, token="t0k")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    try:
        assert srv.server_address[0] == "127.0.0.1" and srv.link.endswith(f"#helper={port}.t0k")
        assert _req(port, "/v1/status")[0] == 401
        assert _req(port, "/v1/status", "wrong")[0] == 401
        assert _req(port, "/v1/status", "t0k", origin="https://evil.example")[0] == 403
        assert _req(port, "/v1/status", "t0k", host="evil.example")[0] == 403
        code, hdr, body = _req(port, "/v1/status", "t0k", origin="https://openwelldata.org")
        assert code == 200 and hdr["Access-Control-Allow-Origin"] == "https://openwelldata.org"
        assert "iodp-rigwatch" in json.loads(body)["datasets"]
        code, hdr, _ = _req(port, "/v1/status", origin="https://openwelldata.org", method="OPTIONS")
        assert code == 204 and hdr["Access-Control-Allow-Private-Network"] == "true"
        assert _req(port, "/v1/status", origin="https://evil.example", method="OPTIONS")[0] == 403
        code, hdr, body = _req(port, "/v1/fetch", "t0k", method="POST",
                               body=json.dumps({"url": files_server + "/well.las"}).encode())
        assert code == 200 and body == open(VOLVE, "rb").read() and hdr["X-OWD-File"] == "well.las"
        code, _, body = _req(port, "/v1/fetch", "t0k", method="POST", body=json.dumps({"url": files_server + "/closed.las"}).encode())
        assert code == 502 and json.loads(body)["closed"]
        code, _, body = _req(port, "/v1/fetch", "t0k", method="POST", body=json.dumps({"dataset": "volve"}).encode())
        assert code == 409 and json.loads(body)["closed"]
    finally:
        srv.shutdown()
        srv.server_close()


# ------------------------------------------------------------------ parity with the browser engine
@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed (run the parity test where it is)")
def test_parity_with_javascript(tmp_path):
    root = os.path.abspath(os.path.join(HERE, "..", ".."))
    subprocess.run([sys.executable, os.path.join(HERE, "parity", "make_vectors.py"), str(tmp_path)], check=True)
    r = subprocess.run(["node", os.path.join(HERE, "parity", "run_parity.js"), str(tmp_path),
                        os.path.join(root, "sitio", "static", "convert.js"),
                        os.path.join(root, "sitio", "static", "convert-page.js")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


# ------------------------------------------------------------------ block-by-block conversion (large files)
def test_streaming_matches_in_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "CHUNK_ROWS", 7)
    for src in (VOLVE, TAB, WRAP, SYN, FORGE):
        o1, p1 = C.convert_file(src, tmp_path / "a.csv", stream=False, units="field", now=NOW)
        o2, p2 = C.convert_file(src, tmp_path / "b.csv", stream=True, units="field", now=NOW)
        assert open(o1).read() == open(o2).read(), src
        assert p2["input"].pop("streamed") is True
        assert json.loads(json.dumps(p1)) == json.loads(json.dumps(p2)), src
    lasio = pytest.importorskip("lasio")
    for src in (VOLVE, WRAP, TAB, SYN):        # same header and values (column alignment may differ by block)
        C.convert_file(src, tmp_path / "a.las", stream=False, now=NOW)
        C.convert_file(src, tmp_path / "b.las", stream=True, now=NOW)
        x, y = (C.parse_las(open(tmp_path / n).read()) for n in ("a.las", "b.las"))
        assert x["columns"] == y["columns"] and x["well"] == y["well"] and x["channels"] == y["channels"], src
    for src in (VOLVE, WRAP):
        C.convert_file(src, tmp_path / "a.las", stream=False, now=NOW)
        C.convert_file(src, tmp_path / "b.las", stream=True, now=NOW)
        a, b = (lasio.read(str(tmp_path / n), mnemonic_case="preserve") for n in ("a.las", "b.las"))
        assert [c.mnemonic for c in a.curves] == [c.mnemonic for c in b.curves]
        assert (a.data[a.data == a.data] == b.data[b.data == b.data]).all()
        assert {k: a.well[k].value for k in a.well.keys()} == {k: b.well[k].value for k in b.well.keys()}, src
    pq = pytest.importorskip("pyarrow.parquet")
    C.convert_file(VOLVE, tmp_path / "a.parquet", stream=False, now=NOW)
    C.convert_file(VOLVE, tmp_path / "b.parquet", stream=True, now=NOW)
    ta, tb = pq.read_table(tmp_path / "a.parquet"), pq.read_table(tmp_path / "b.parquet")
    assert ta.to_pandas().equals(tb.to_pandas())
    assert b"owd:provenance" in pq.ParquetFile(tmp_path / "b.parquet").metadata.metadata


def test_get_catalogue_source(files_server, tmp_path, monkeypatch):
    import zipfile
    with zipfile.ZipFile(tmp_path / "2020.zip", "w") as z:
        z.write(VOLVE, "logs/well_a.las")
        z.write(SYN, "logs/well_b.las")
    m = tmp_path / "methods.csv"
    m.write_text("id,method,example_file_url,browser_flow\n"
                 f"test-open,bulk,{files_server}/2019.zip,drop_file\n"
                 "test-closed,registration,,drop_file\n")
    monkeypatch.setenv("OWD_DOWNLOAD_METHODS", str(m))
    out = tmp_path / "out"
    assert run_cli("get", "test-open:2020", "--member", "well_a", "--units", "field", "-o", str(out)) == 0
    assert [p.name for p in out.iterdir()] == ["well_a.owd.csv", "well_a.owd.provenance.json"] or \
        sorted(p.name for p in out.iterdir()) == ["well_a.owd.csv", "well_a.owd.provenance.json"]
    assert run_cli("get", "test-closed") == 1
    assert run_cli("get", "no-such-thing") == 1
    assert toolkit.source_url({"example_file_url": "https://h/x/Log_Summary/2022.zip"}, "2020") == ("https://h/x/Log_Summary/2020.zip", None)
