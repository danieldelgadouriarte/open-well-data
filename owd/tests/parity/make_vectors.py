# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Write the parity test vectors: Python conversions of the fixtures that the JS engine must reproduce exactly.

    python owd/tests/parity/make_vectors.py OUT_DIR        # writes OUT_DIR/tables.json and OUT_DIR/vectors.json
    node owd/tests/parity/run_parity.js OUT_DIR sitio/static/convert.js

The two steps can run on different machines (copy the folder): only the JSON files and convert.js are needed. The
pytest test_parity_with_javascript runs both when `node` is on the PATH.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from owd import convert as C  # noqa: E402

DATA = os.path.join(HERE, "..", "data")
NOW = "2026-11-05T12:00:00Z"
FILES = ["synthetic_drilling.las", "synthetic_mislabelled.las", "synthetic_wrapped.las", "synthetic_table.csv",
         "synthetic_rig_1s.csv", "synthetic_context.las"]
OPTIONS = [
    {"names": "owd", "units": "si", "to": "csv"},
    {"names": "owd", "units": "field", "to": "las"},
    {"names": "original", "units": "field", "to": "csv", "csvHeader": "plain", "comments": True},
    {"names": "owd", "units": {"_default": "field", "hookload": "kN", "spp": "bar", "md": "m"}, "to": "las", "digits": 0},
    {"names": "owd", "units": {"rop": "m/min", "flow_in": "m3/h", "bit_depth": "km"}, "to": "csv", "digits": 6, "source": "volve"},
    {"names": "owd", "units": "si", "to": "csv", "null": "-999.25", "sourceFormat": "LAS"},
    {"names": "owd", "units": "field", "to": "csv", "source": "kgs"},
]
NUMBERS = [1e21, 1e-7, 1.5e-7, 0.000001, 123456789012345680000.0, 0.1 + 0.2, -0.0, 100.0, 4479.499999999999, 2.5e-5,
           1 / 3, -1234.5678e10, 5e-324, 1.7976931348623157e308, 0.125, -0.125, 2.5, 1e16, 123e-20]


def py_opts(o):
    return dict(names=o["names"], units=o["units"], to=o["to"], csv_header=o.get("csvHeader", "unit"),
                comments=o.get("comments", False), digits=o.get("digits", C.DEFAULT_DIGITS), null=o.get("null"),
                source_format=o.get("sourceFormat"), source=C.source_info(o.get("source")))


def main(out):
    os.makedirs(out, exist_ok=True)
    vectors = []
    for f in FILES:
        raw = open(os.path.join(DATA, f), "rb").read()
        text = C.decode(raw)
        sha = hashlib.sha256(raw).hexdigest()
        for i, o in enumerate(OPTIONS):
            txt, prov = C.convert_text(text, file_name=f, input_sha256=sha, now=NOW, **py_opts(o))
            vectors.append({"name": f"{f} #{i}", "text": text, "file": f, "sha256": sha, "opts": o, "now": NOW,
                            "expected_text": txt, "expected_provenance": prov})
    nums = [[x, d, C.fmt_number(x, d)] for x in NUMBERS for d in (None, 1, 2, 6, 12)]
    t = C.tables()
    with open(os.path.join(out, "tables.json"), "w", encoding="utf-8") as fh:
        json.dump(t, fh, ensure_ascii=False)
    with open(os.path.join(out, "vectors.json"), "w", encoding="utf-8") as fh:
        json.dump({"dictionary_version": t["meta"]["dictionary_version"], "vectors": vectors, "numbers": nums}, fh,
                  ensure_ascii=False)
    import zipfile
    members = {}
    with zipfile.ZipFile(os.path.join(out, "sample.zip"), "w") as z:
        for f, comp in (("synthetic_table.csv", zipfile.ZIP_DEFLATED), ("sub/synthetic_wrapped.las", zipfile.ZIP_STORED)):
            data = open(os.path.join(DATA, os.path.basename(f)), "rb").read()
            z.writestr(zipfile.ZipInfo(f, (2026, 11, 5, 12, 0, 0)), data, compress_type=comp)
            members[f] = data.decode("utf-8-sig")
    with open(os.path.join(out, "sample.zip.json"), "w", encoding="utf-8") as fh:
        json.dump(members, fh, ensure_ascii=False)
    print(f"{len(vectors)} conversion vectors and {len(nums)} number vectors in {out} "
          f"(dictionary {t['meta']['dictionary_version']})")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "parity-out")
