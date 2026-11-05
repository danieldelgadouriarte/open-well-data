# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Free for non-commercial use; companies need a licence (see NOTICE).
"""Search over the catalogue of sources (fichas/sources.jsonl in the project).
Bilingual: every query term works in English or Spanish, with or without accents (dictionary in synonyms.tsv)."""
import json, os, re, unicodedata
# Catalogue: OWD_CATALOG if set; otherwise the one in the repository (development); otherwise the one shipped in the package.
_REPO = os.path.join(os.path.dirname(__file__), "..", "..", "fichas", "sources.jsonl")
_PACKAGE = os.path.join(os.path.dirname(__file__), "data", "sources.jsonl")
_DEF = os.environ.get("OWD_CATALOG") or (_REPO if os.path.exists(_REPO) else _PACKAGE)
_SYN = os.path.join(os.path.dirname(__file__), "synonyms.tsv")


def normalize(t):
    """Lower case, no accents, only letters and digits separated by one space, with a space at each end."""
    t = unicodedata.normalize("NFKD", str(t).lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " " + " ".join(re.split(r"[^a-z0-9]+", t)).strip() + " "


def _groups():
    g = []
    for l in open(_SYN, encoding="utf-8"):
        if l.strip() and not l.startswith("#"):
            g.append([normalize(x).strip() for x in l.rstrip("\n").split("\t") if x.strip()])
    return g


GROUPS = _groups()


def terms(text):
    """Split the query into terms. Multi-word expressions from the dictionary are recognised first.
    Each term is the list of equivalent variants; a word outside the dictionary stands alone."""
    q = normalize(text)
    out = []
    multi = sorted({v for g in GROUPS for v in g if " " in v}, key=len, reverse=True)
    for v in multi:
        if f" {v} " in q:
            out.append(next(g for g in GROUPS if v in g))
            q = q.replace(f" {v} ", " ")
    for w in q.split():
        out.append(next((g for g in GROUPS if w in g), [w]))
    return out


def _contains(s, v):
    # Short variants (2d, ml, ai, uk, das...) only as a whole word; longer ones also inside a word.
    return f" {v} " in s if len(v) <= 3 else v in s


def sources(path=None):
    return [json.loads(l) for l in open(path or _DEF, encoding="utf-8")]


def search(text="", country=None, discipline=None, access=None, category=None, path=None):
    """Records that contain every term of `text` (in any of its variants) and pass the filters.
    Order: records with more terms in their name first."""
    ts = terms(text)
    out = []
    for f in sources(path):
        s = normalize(json.dumps(f, ensure_ascii=False))
        if not all(any(_contains(s, v) for v in t) for t in ts): continue
        if country and normalize(country).strip() not in normalize(f.get("country", "")): continue
        if discipline and discipline not in (f.get("disciplines") or []): continue
        if access and f.get("access") != access: continue
        if category and f.get("category") != category: continue
        out.append(f)

    def weight(f):
        n = normalize(f.get("name", ""))
        return -sum(any(_contains(n, v) for v in t) for t in ts)
    return sorted(out, key=weight)
