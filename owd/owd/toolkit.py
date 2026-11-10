# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Command line glue for the conversion engine: `owd convert` and `owd get ... --names --units --to`.

    owd convert well.las --names owd --units field --to las -o well_field.las
    owd get iodp-rigwatch --units field --to csv -o out/          # recipe: download from the source, verify, convert
    owd get force-2020:15_9-13 --to las -o out/                   # only the members whose name contains 15_9-13
    owd get https://example.org/public/well.las --to csv          # a public file, no login

Downloads: one at a time, identifiable User-Agent, public URLs only. Never logs in, never accepts terms on the user's
behalf, never works around a block: a closed source is reported with a link to its page. Files are cached on the
user's computer (OWD_DATA or ~/.owd) unless --no-cache is given.
"""
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import convert as C

USER_AGENT = "owd (Open Well Data; +https://openwelldata.org)"


def parse_units(s):
    """'si', 'field', or 'si,hookload=klbf,spp=bar' / 'hookload=klbf' -> engine units option."""
    if s is None:
        return "si"
    parts = [x.strip() for x in str(s).split(",") if x.strip()]
    base = [x for x in parts if "=" not in x and ":" not in x]
    pairs = [re.split(r"[=:]", x, maxsplit=1) for x in parts if "=" in x or ":" in x]
    default = base[0] if base else "si"
    if default not in ("si", "field"):
        raise C.ConversionError(f"units: {default!r} is not si or field")
    if not pairs:
        return default
    d = {k.strip(): v.strip() for k, v in pairs}
    if default != "si":
        d["_default"] = default
    return d


def add_convert_args(p, output=True):
    p.add_argument("--names", default="owd", choices=["owd", "original"], help="channel names (default owd)")
    p.add_argument("--units", default="si", help="si (OWD standard), field, or e.g. 'field,spp=bar' (default si)")
    p.add_argument("--to", choices=["csv", "las", "parquet"], help="output format (default from -o, else csv)")
    if output:
        p.add_argument("-o", "--output", help="output file (convert) or folder (get)")
    p.add_argument("--digits", type=int, default=12, help="significant digits of converted values (default 12; 0 = full double precision)")
    p.add_argument("--csv-header", choices=["unit", "plain"], default="unit", help="'name [unit]' (default) or 'name'")
    p.add_argument("--comments", action="store_true", help="CSV: add '# ' lines with the citation at the top")
    p.add_argument("--null", help="null value of a CSV input (e.g. -999.25); LAS uses its NULL")
    p.add_argument("--source-format", help="LAS, DLIS, LIS, WITSML or table (decides context rules; default from the file)")


def cmd_convert(a, notify=print):
    units = parse_units(a.units)
    out, prov = C.convert_file(a.input, a.output, names=a.names, units=units, to=a.to, source_format=a.source_format,
                               null=a.null, digits=a.digits, csv_header=a.csv_header, comments=a.comments,
                               dataset=a.dataset, citation=a.citation, licence=a.licence)
    s = prov["summary"]
    notify(f"{out}: {s['channels']} channels, {s['labelled']} with OWD names, {s['converted']} converted, "
           f"{len(s['not_labelled'])} kept as they were, {s['warnings']} warnings")
    if out.endswith(".csv"):
        notify(f"provenance and citation: {C.sidecar_path(out)}")
    notify(prov["how_to_cite"]["open_well_data"])
    return 0


# ------------------------------------------------------------------ downloads
class SourceClosed(Exception):
    pass


def cache_dir():
    return Path(os.environ.get("OWD_DATA", Path.home() / ".owd" / "data")).parent / "cache"


def fetch_url(url, cache=True, notify=print, opener=None):
    """Download a public file (no login, no cookies). Returns the local path. Raises SourceClosed when the source asks
    for a login, refuses the request or answers with a web page instead of a file."""
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        raise SourceClosed(f"{url}: only http(s) addresses")
    name = os.path.basename(urllib.parse.urlsplit(url).path) or "download"
    d = cache_dir() / hashlib.sha256(url.encode()).hexdigest()[:16]
    dest = d / name
    if cache and dest.exists():
        notify(f"{name}: from the local cache ({dest})")
        return dest
    d.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with (opener or urllib.request.urlopen)(req, timeout=60) as r:
            ctype = r.headers.get("Content-Type", "")
            if "text/html" in ctype and not name.lower().endswith((".html", ".htm")):
                raise SourceClosed(f"{url} answered with a web page, not a file: the source probably asks you to log in "
                                   f"or accept its terms. Open {url} in your browser, download the file and run "
                                   "`owd convert <file>`.")
            part = Path(str(dest) + ".part")
            with open(part, "wb") as f:
                for block in iter(lambda: r.read(1 << 20), b""):
                    f.write(block)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 407, 451):
            raise SourceClosed(f"{url}: the source refuses automatic downloads (HTTP {e.code}). Open its page in your "
                               "browser, download the file yourself (accepting its terms if you agree) and run "
                               "`owd convert <file>`.") from None
        raise SourceClosed(f"{url}: HTTP {e.code}") from None
    except urllib.error.URLError as e:
        raise SourceClosed(f"{url}: {e.reason}") from None
    part.replace(dest)
    if not cache:
        notify(f"{name}: downloaded (not kept after conversion)")
    return dest


# ------------------------------------------------------------------ catalogue sources (fichas/download_methods.csv)
OPEN_METHODS = ("direct_cors", "direct_no_cors", "bulk", "api")
CLOSED = {"registration": "asks for a free account", "terms_acceptance": "asks you to accept its terms first",
          "request_form": "sends data on request", "paid": "sells the data", "portal_click": "only gives files through its "
          "interactive pages", "none": "offers no data download", "dead": "is offline", "unknown": "has no tested download"}
_REPO = Path(__file__).resolve().parent.parent.parent / "fichas"


def download_methods(path=None):
    """{source id: [rows]} from fichas/download_methods.csv (OWD_DOWNLOAD_METHODS overrides the path); {} if absent."""
    import csv
    p = Path(path or os.environ.get("OWD_DOWNLOAD_METHODS") or _REPO / "download_methods.csv")
    if not p.exists():
        return {}
    out = {}
    with open(p, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["id"], []).append(r)
    return out


def source_record(id):
    try:
        from .catalog import sources
        return next((s for s in sources() if s.get("id") == id), None)
    except (OSError, ValueError):
        return None


def source_url(row, part):
    """URL to download for a catalogue source: its example file, or the same folder with another file name
    (e.g. kgs-las-kansas:2020 -> .../Log_Summary/2020.zip); a full URL after ':' is used as given."""
    ex = row.get("example_file_url") or ""
    if part and re.match(r"^https?://", part):
        return part, None
    if part and ex and not ex.rstrip("/").endswith("/content") and "?" not in ex:
        head, tail = ex.rsplit("/", 1)
        ext = os.path.splitext(tail)[1]
        name = part if os.path.splitext(part)[1] else part + ext
        return f"{head}/{name}", None
    return ex, part or None


def convert_downloaded(path, out_dir, member=None, names="owd", units="si", to="csv", digits=12, csv_header="unit",
                       comments=False, citation=None, licence=None, dataset=None, notify=print):
    """Convert a downloaded LAS/CSV, or the LAS/CSV members of a downloaded zip (optionally only those whose name
    contains `member`). Returns the output paths."""
    import tempfile
    import zipfile
    out_dir = Path(out_dir or ".")
    out_dir.mkdir(parents=True, exist_ok=True)
    done = []

    def one(p, label):
        target = out_dir / (Path(label).stem + f".owd.{to}")
        o, prov = C.convert_file(p, target, names=names, units=units, to=to, digits=digits, csv_header=csv_header,
                                 comments=comments, dataset=dataset, citation=citation, licence=licence)
        notify(f"  {o}: {prov['summary']['labelled']} channels with OWD names, {prov['summary']['converted']} converted")
        done.append(o)

    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z, tempfile.TemporaryDirectory() as tmp:
            members = [m for m in z.namelist() if re.search(r"\.(las|csv)$", m, re.I) and (not member or member in m)]
            if not members:
                notify(f"no LAS or CSV file{' matching ' + repr(member) if member else ''} in {Path(path).name}")
            for m in members:
                p = Path(tmp) / Path(m).name
                p.write_bytes(z.read(m))
                try:
                    one(p, m)
                except C.ConversionError as e:
                    notify(f"  {m}: skipped ({e})")
    else:
        one(path, Path(path).name)
    return done


def _std_frames(paths):
    """Standardized outputs of a recipe (Parquet or csv.gz with a .json of metadata) -> (frame, meta) pairs."""
    import pandas as pd
    for p in paths:
        p = str(p)
        meta_p = re.sub(r"\.(parquet|csv\.gz)$", ".json", p)
        meta = json.loads(Path(meta_p).read_text(encoding="utf-8")) if os.path.exists(meta_p) else {}
        df = pd.read_parquet(p) if p.endswith(".parquet") else pd.read_csv(p, index_col=0)
        yield p, df, meta


def convert_outputs(paths, dataset, out_dir, names="owd", units="si", to="csv", digits=None, csv_header="unit",
                    comments=False, notify=print):
    """Convert the standardized files of a recipe to the user's names, units and format, with provenance."""
    out_dir = Path(out_dir or ".")
    out_dir.mkdir(parents=True, exist_ok=True)
    done = []
    for p, df, meta in _std_frames(paths):
        unit = meta.get("unit") or {}
        original = meta.get("original") or {}
        tbl = C.frame_to_table(df, unit)
        if names == "original":
            for ch in tbl["channels"]:
                o = original.get(ch["name"])
                if o:
                    ch["description"] = f"standardized as {ch['name']}"
                    ch["name"] = o.get("name") or ch["name"]
        plans, cols, prov = C.convert_table(tbl, names=names, units=units, to=to, digits=digits, csv_header=csv_header,
                                            source=C.source_info(dataset), file_name=os.path.basename(p))
        prov["input"]["original_file"] = meta.get("original_file")
        prov["input"]["recipe_version"] = meta.get("recipe_version")
        target = out_dir / (re.sub(r"\.(parquet|csv\.gz)$", "", os.path.basename(p)) + f".{to}")
        C.write_output(tbl, plans, cols, prov, target, to, digits, csv_header, comments)
        notify(f"  {target}")
        done.append(str(target))
    return done


def cmd_get(a, notify=print):
    """owd get <dataset>[:<filter>] | <url>, with optional conversion."""
    from . import recipes
    units = parse_units(a.units)
    to = a.to or "csv"
    spec = a.id
    if re.match(r"^https?://", spec):
        try:
            path = fetch_url(spec, cache=not a.no_cache, notify=notify)
        except SourceClosed as e:
            notify(f"owd: {e}")
            return 1
        import zipfile
        if zipfile.is_zipfile(path):
            done = convert_downloaded(path, a.output, a.member, a.names, units, to, a.digits, a.csv_header, a.comments,
                                      a.citation, a.licence, None, notify)
            if not done:
                return 1
        else:
            out = a.output
            if out and os.path.isdir(out):
                out = os.path.join(out, os.path.splitext(path.name)[0] + f".owd.{to}")
            out, prov = C.convert_file(path, out, names=a.names, units=units, to=to, digits=a.digits,
                                       csv_header=a.csv_header, comments=a.comments, null=a.null, citation=a.citation,
                                       licence=a.licence)
            notify(f"{out}: converted. Source licence: {prov['source']['license']}.")
        if a.no_cache:
            try:
                path.unlink()
            except OSError:
                pass
        return 0
    dataset, _, only = spec.partition(":")
    if dataset not in recipes.recipes():
        rows = download_methods().get(dataset)
        if not rows:
            notify(f"owd: {dataset!r} is neither a recipe ({', '.join(recipes.recipes())}) nor a catalogue source with a "
                   "known download method. Search the catalogue with owd.search() or pass a public URL.")
            return 1
        return _get_source(dataset, rows, only, a, units, to, notify)
    paths = recipes.get(dataset, notify=notify, only=only or None)
    if not (a.names != "owd" or a.units != "si" or a.to or a.output):
        return 0
    notify(f"Converting {len(paths)} files ({a.names} names, {C.units_label(units)} units, {to})")
    convert_outputs(paths, dataset, a.output, a.names, units, to, a.digits, a.csv_header, a.comments, notify)
    notify(C.owd_citation(__import__("datetime").date.today().year) + ". Cite the source too: owd cite " + dataset)
    return 0


def _get_source(id, rows, part, a, units, to, notify=print):
    """owd get <catalogue source>[:<file>]: public direct downloads only; anything else is explained with a link."""
    rec = source_record(id) or {}
    page = rec.get("url") or ""
    licence = a.licence or (rec.get("license") if rec.get("license") not in (None, "", "not stated") else None)
    citation = a.citation or (f"{rec.get('operator') or rec.get('name')}. {rec.get('name')}. {page}" if rec else None)
    row = next((r for r in rows if r.get("method") in OPEN_METHODS and r.get("example_file_url")), None)
    if row is None:
        r = rows[0]
        why = CLOSED.get(r.get("method"), "has no direct public file")
        notify(f"owd: {id} {why} (method {r.get('method')}). Open {page or 'its page'} in your browser, download what you "
               f"need (accepting its terms if you agree) and run `owd convert <file>`.")
        return 1
    url, member = source_url(row, part)
    member = a.member or member
    notify(f"{id}: downloading {url} (method {row['method']}; one request, no login)")
    try:
        path = fetch_url(url, cache=not a.no_cache, notify=notify)
    except SourceClosed as e:
        notify(f"owd: {e} Source page: {page}")
        return 1
    done = convert_downloaded(path, a.output, member, a.names, units, to, a.digits, a.csv_header, a.comments,
                              citation, licence, None, notify)
    if a.no_cache:
        try:
            path.unlink()
        except OSError:
            pass
    notify(f"{len(done)} files converted. Source licence: {licence or C.AS_STATED}. "
           + C.owd_citation(__import__("datetime").date.today().year))
    return 0 if done else 1
