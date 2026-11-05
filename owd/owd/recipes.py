# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Free for non-commercial use; companies need a licence (see NOTICE).
"""Recipes: how to get a dataset from its source and leave it standardized on the user's computer.

A recipe (owd/recipes.d/<id>.json) says where each file is downloaded from, which size and sha256 it must have, whether
the download may be automatic and how it is processed. The data never passes through Open Well Data: each person
downloads it from the source, accepting its terms, and it is processed on their machine.

    owd.get("iodp-rigwatch")                       # download, verify and standardize
    owd.import_data("volve", "Volve_WITSML.zip")   # same process with a file downloaded by hand
    python -m owd get iodp-rigwatch                # the same from the command line
"""
import csv, datetime, hashlib, io, json, os, re, shutil, sys, urllib.parse, urllib.request, zipfile
from pathlib import Path

RECIPES_DIR = Path(__file__).parent / "recipes.d"
USER_AGENT = "owd (Open Well Data; +https://danieldelgadouriarte.com)"


class RecipeError(Exception):
    pass


def recipes():
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(RECIPES_DIR.glob("*.json"))}


def recipe(id):
    r = recipes().get(id)
    if not r:
        raise RecipeError(f"No recipe for {id!r}. Recipes: {', '.join(recipes())}")
    return r


def folder(id=None):
    """Local data folder: OWD_DATA or ~/.owd/data."""
    base = Path(os.environ.get("OWD_DATA", Path.home() / ".owd" / "data"))
    return base / id if id else base


def _hash(path, algorithm):
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify(path, file):
    """Size and checksum of the file against the recipe. A server that cuts the download can leave a truncated zip
    that looks valid: that is why the bytes are always checked, not only that the file opens."""
    path = Path(path)
    errors = []
    if file.get("bytes") and path.stat().st_size != file["bytes"]:
        errors.append(f"size {path.stat().st_size} bytes, expected {file['bytes']}")
    for alg in ("sha256", "md5"):
        if file.get(alg) and _hash(path, alg) != file[alg]:
            errors.append(f"{alg} does not match")
            break
    return errors


def _domain_allowed(url, domains):
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in domains)


def download(file, destination, domains, notify=print):
    url = file["url"]
    if not _domain_allowed(url, domains):
        raise RecipeError(f"{url}: domain not in the recipe ({', '.join(domains)})")
    partial = Path(str(destination) + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        if not _domain_allowed(r.geturl(), domains):  # also after redirects
            raise RecipeError(f"the download redirects to {r.geturl()}, outside the recipe")
        total, done, next_mark = file.get("bytes") or 0, 0, 0
        with open(partial, "wb") as f:
            for block in iter(lambda: r.read(1 << 20), b""):
                f.write(block)
                done += len(block)
                if total and done >= next_mark:
                    notify(f"  {file['name']}: {done / 1e6:,.0f} / {total / 1e6:,.0f} MB")
                    next_mark += max(total // 10, 1)
    errors = verify(partial, file)
    if errors:
        raise RecipeError(f"{file['name']}: {'; '.join(errors)}. The download is left in {partial} and not used.")
    partial.replace(destination)


def get(id, notify=print):
    """Download the files from the source (if the recipe allows it), verify them and standardize them."""
    r = recipe(id)
    d = folder(id) / "original"
    d.mkdir(parents=True, exist_ok=True)
    for file in r["files"]:
        destination = d / file["name"]
        if destination.exists() and not verify(destination, file):
            notify(f"{file['name']}: already here and verified")
            continue
        if r["download"] != "auto":
            raise RecipeError(
                f"{id}: the source asks you to download the data yourself ({r.get('manual_reason', 'accept its terms')}).\n"
                f"  1. Open {r['source']} and read its terms: {r['terms']}\n"
                f"  2. Download {file['name']}\n"
                f"  3. owd import {id} <path to the file>")
        notify(f"Downloading {file['name']} from {urllib.parse.urlsplit(file['url']).hostname}")
        download(file, destination, r["domains"], notify)
    return process(id, notify)


def import_data(id, path, notify=print, force=False):
    """Use a file the person already downloaded from the source. It is checked against the recipe before processing."""
    r = recipe(id)
    path = Path(path)
    file = next((f for f in r["files"] if f["name"] == path.name), None) or (r["files"][0] if len(r["files"]) == 1 else None)
    if not file:
        raise RecipeError(f"{path.name} is none of: {', '.join(f['name'] for f in r['files'])}")
    errors = verify(path, file)
    if errors and not force:
        raise RecipeError(f"{path.name}: {'; '.join(errors)}. Is it another version of the source? Use --force (force=True) if you are sure.")
    d = folder(id) / "original"
    d.mkdir(parents=True, exist_ok=True)
    destination = d / file["name"]
    if path.resolve() != destination.resolve():
        shutil.copy2(path, destination)
    return process(id, notify, verified=not errors)


def process(id, notify=print, verified=True):
    from .registry import load, describe
    r = recipe(id)
    p = r["process"]
    output = folder(id) / "standard"
    output.mkdir(parents=True, exist_ok=True)
    original = folder(id) / "original" / p["file"]
    done = []
    if p["type"] == "pending":
        notify(f"{id}: original saved in {original}. {p['note']}")
        return done

    def write(name, df, extra):
        base = output / re.sub(r"[^A-Za-z0-9._-]+", "_", name)
        try:
            df.to_parquet(str(base) + ".parquet", compression="zstd")
            path = str(base) + ".parquet"
        except (ImportError, ValueError):
            path = str(base) + ".csv.gz"
            df.to_csv(path, compression="gzip")
        info = describe(id)
        meta = {"dataset": id, "recipe_version": r["version"], "source": r["source"], "license": r["license"],
                "terms": r["terms"], "citation": info["citation"], "original_file": p["file"], **extra,
                "original_verified": verified, "rows": len(df), "unit": df.attrs.get("unit", {}),
                "original": {k: v for k, v in (df.attrs.get("original") or {}).items()},
                "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "open_well_data": "Loaded and standardized with Open Well Data, by Daniel Delgado-Uriarte"}
        Path(str(base) + ".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        done.append(path)
        notify(f"  {Path(path).name}: {len(df):,} rows")

    if p["type"] == "zip_members":
        with zipfile.ZipFile(original) as z:
            members = [m for m in z.namelist() if re.search(p["pattern"], m)]
        for m in members:
            df = load(id, str(original), member=m)
            write(Path(m).stem, df, {"member": m})
    elif p["type"] == "zip_csv_by_day":
        # Large CSV inside a zip: split by day (first column YYYY/MM/DD) and each day is standardized.
        tmp = folder(id) / "tmp"
        tmp.mkdir(exist_ok=True)
        with zipfile.ZipFile(original) as z, z.open(p["member"]) as f:
            text = io.TextIOWrapper(f, encoding="utf-8", errors="replace", newline="")
            head = text.readline()
            day, day_out = None, None
            for line in text:
                d = line[:10]
                if d != day:
                    if day_out:
                        day_out.close()
                    day = d
                    new = not (tmp / f"{d.replace('/', '-')}.csv").exists()
                    day_out = open(tmp / f"{d.replace('/', '-')}.csv", "a", encoding="utf-8", newline="")
                    if new:
                        day_out.write(head)
                day_out.write(line)
            if day_out:
                day_out.close()
        for part in sorted(tmp.glob("*.csv")):
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.csv", part.name):
                continue
            df = load(id, str(part))
            write(f"{Path(p['member']).stem}_{part.stem}", df, {"member": p["member"], "day": part.stem})
            part.unlink()
        shutil.rmtree(tmp, ignore_errors=True)
    elif p["type"] == "witsml_zip":
        # Volve WITSML 1.4 zip as Equinor distributes it: the NNNNN.xml chunks are grouped by log, each log is read
        # whole with the WITSML reader (units and nulls from its header) and standardized. Only logs with at least
        # p["min_channels"] standard channels are written; logs that fail are listed and the rest continue.
        from . import _reader as L, standard
        from .registry import DATASETS
        with zipfile.ZipFile(original) as z:
            logs = sorted({"{}/{}/log/{}/{}/{}".format(*m.groups()[:5]) for m in (L.witsml.RE_CHUNK.match(n) for n in z.namelist()) if m})
        limit = p.get("limit")
        failures = []
        for i, pre in enumerate(logs[:limit] if limit else logs):
            try:
                rd = L.witsml.read_witsml(str(original), log=pre)
                rd.meta.update({"dataset": id, "license": DATASETS[id]["license"], "citation": DATASETS[id]["citation"], "source": DATASETS[id]["url"]})
                df = standard.standardize(rd)
            except Exception as e:  # one broken log does not stop the rest
                failures.append({"log": pre, "error": f"{type(e).__name__}: {e}"[:300]})
                continue
            n_std = sum(1 for c in df.columns if c in standard._UNIT)
            if n_std < p.get("min_channels", 1):
                continue
            write(pre.replace("/", "__"), df, {"log": pre, "standard_channels": n_std})
        if failures:
            (output / "_failures.json").write_text(json.dumps(failures, ensure_ascii=False, indent=1), encoding="utf-8")
            notify(f"{id}: {len(failures)} logs could not be read; see {output / '_failures.json'}")
    else:
        raise RecipeError(f"unknown process: {p['type']}")
    notify(f"{id}: {len(done)} standardized files in {output}")
    return done


def main(argv=None):
    import argparse
    from . import registry
    ap = argparse.ArgumentParser(prog="owd", description="Open Well Data: public well data with standard channels and SI units.")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="datasets with a recipe")
    for n, h in (("info", "licence, source and how to get it"), ("cite", "citation text"), ("get", "download from the source and standardize")):
        sub.add_parser(n, help=h).add_argument("id")
    im = sub.add_parser("import", help="standardize a file you downloaded yourself")
    im.add_argument("id"); im.add_argument("file"); im.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.command == "list":
            for k, r in recipes().items():
                print(f"{k:24} level {r['level']:3} download {r['download']:7} {r['license']}")
        elif a.command == "info":
            r = recipe(a.id)
            print(json.dumps({k: r[k] for k in ("source", "license", "terms", "level", "download")}, ensure_ascii=False, indent=1))
        elif a.command == "cite":
            print(registry.cite(a.id))
        elif a.command == "get":
            get(a.id)
        elif a.command == "import":
            import_data(a.id, a.file, force=a.force)
    except RecipeError as e:
        print(f"owd: {e}", file=sys.stderr)
        return 1
    return 0
