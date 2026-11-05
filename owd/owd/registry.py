# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Free for non-commercial use; companies need a licence (see NOTICE).
"""The 10 MVP datasets: what they are, their licence and how they load. Licences read on 3 Nov 2026.

policy: "copy" = a standardized copy may be published, citing the source; "recipe" = only the code is published and
each user downloads the data from the original source; "link" = reference only (size or terms)."""
from . import _reader as L, readers, standard

DATASETS = {
 "volve": dict(name="Equinor Volve, real-time drilling logs", url="https://www.equinor.com/energy/volve-data-sharing",
   license="Equinor Open Data Licence (Volve): based on CC BY 4.0; commercial use and redistribution allowed, sale prohibited",
   policy="copy", tested=True,
   citation="Equinor ASA, ExxonMobil Exploration & Production Norway AS and Bayerngas Norge AS (former Volve licence partners). "
            "Volve Data Village. Terms: https://www.equinor.com/content/dam/statoil/documents/what-we-do/"
            "Equinor-HRS-Terms-and-conditions-for-licence-to-data-Volve.pdf",
   format="WITSML / CSV extracts",
   terms="May not be sold. Credit Equinor and the former partners, link the terms and do not present the data "
         "in a misleading way. Do not use their names or trademarks for promotion. Norwegian law."),
 "utah-forge-16b": dict(name="Utah FORGE well 16B(78)-32, Pason rig data", url="https://gdr.openei.org/submissions/1516",
   license="CC BY 4.0", policy="copy", tested=True, citation="McLennan, J., et al. (2023), Utah FORGE: Well 16B(78)-32 Drilling Data, GDR, doi:10.15121/1998591",
   format="Pason CSV"),
 "gdr-1329-pdc-granite": dict(name="PDC bit tests in Sierra White granite (Oklahoma State)",
   url="https://gdr.openei.org/submissions/1329", license="CC BY 4.0", policy="copy", tested=True,
   citation="Al Dushaishi and Hareland, GDR, doi:10.15121/1842335", format="TXT in zip"),
 "3w": dict(name="3W, undesirable events in offshore oil wells (Petrobras)", url="https://github.com/petrobras/3W",
   license="CC BY 4.0 (data), Apache 2.0 (code)", policy="copy", tested=True, citation="Vargas et al., 3W (see CITATION.md)", format="Parquet"),
 "iodp-rigwatch": dict(name="IODP JOIDES Resolution RigWatch rig data", url="https://doi.org/10.5281/zenodo.18497029",
   license="CC BY 4.0 (Exp. 399; others not checked)", policy="copy", tested=True, citation="IODP Exp. 399 Scientists, doi:10.5281/zenodo.18497029",
   format="CSV in zip, one per expedition"),
 "force-2020": dict(name="FORCE 2020 well logs and lithofacies (118 wells)", url="https://doi.org/10.5281/zenodo.4351156",
   license="CC BY 4.0", policy="copy", tested=True, citation="Bormann et al. (2020), doi:10.5281/zenodo.4351156", format="LAS in zip"),
 "kgs-las": dict(name="Kansas Geological Survey LAS well logs", url="https://www.kgs.ku.edu/Magellan/Logs/",
   license="Own terms, All Rights Reserved", policy="recipe", tested=False,
   citation="Kansas Geological Survey, http://www.kgs.ku.edu/", format="LAS"),
 "mseel": dict(name="MSEEL Marcellus shale wells (MIP)", url="https://edx.netl.doe.gov/dataset/mseel-mip-4h-well-data",
   license="CC BY (version not stated; \"License Not Specified\" on the EDX page)", policy="recipe", tested=True,
   citation="Marcellus Shale Energy and Environment Laboratory Team, MSEEL MIP 4H Well Data (2021), NETL EDX", format="zip with LAS, PDF and XLS"),
 "namss": dict(name="USGS NAMSS marine seismic (3D and 2D)", url="https://walrus.wr.usgs.gov/namss/",
   license="CC0 1.0", policy="link", tested=False, citation="Triezenberg, Hart and Childs (2016), doi:10.5066/F7930R7P",
   format="SEG-Y in zip (TB)"),
 "f3": dict(name="F3 Netherlands 3D seismic cube", url="https://terranubis.com/datainfo/F3-Demo-2023",
   license="CC BY-SA 3.0 on the record page; the TerraNubis Derivative Work Agreement restricts derivative works to those who sign it", policy="recipe", tested=False,
   citation="dGB Earth Sciences, terranubis.com", format="OpendTect project (CBVS), 4.5 GB"),
}

SPDX = {"volve": "LicenseRef-Equinor-Open-Data", "utah-forge-16b": "CC-BY-4.0", "gdr-1329-pdc-granite": "CC-BY-4.0",
        "3w": "CC-BY-4.0", "iodp-rigwatch": "CC-BY-4.0", "force-2020": "CC-BY-4.0", "kgs-las": "LicenseRef-KGS-Terms",
        "mseel": "NOASSERTION", "namss": "CC0-1.0", "f3": "CC-BY-SA-3.0"}
for _k, _v in SPDX.items(): DATASETS[_k]["spdx"] = _v

def info(id): return DATASETS[id]

def describe(id):
    """Everything an agent needs about a dataset in one object: what it is, licence, how to get it and load it."""
    d = dict(DATASETS[id]); d["id"] = id
    d["how_to_load"] = {"copy": "download the standardized copy (once published) or the original, then owd.load(id, path)",
                        "recipe": "download the original from the source with the user's own account, then owd.load(id, path)",
                        "link": "reference only; see url"}[d["policy"]]
    return d

def load(id, path, standardize=True, **kw):
    """Load a file already downloaded from the original source and return it with standard names and units.
    Volve: path = .csv.gz extract and kw witsml_zip=...; FORGE: Pason CSV; GDR 1329: zip and kw member=...;
    3W: parquet; FORCE 2020: zip and kw member=...; IODP: zip and kw member=...; KGS: LAS; MSEEL: kw inner=..., member=..."""
    if id == "volve": rd = L.read_volve_extract(path, kw["witsml_zip"], channels=kw.get("channels"))
    elif id == "utah-forge-16b": rd = L.read_forge_csv(path, channels=kw.get("channels"))
    elif id == "gdr-1329-pdc-granite": rd = readers.gdr1329_txt(path, kw["member"])
    elif id == "3w": rd = readers.threew_parquet(path)
    elif id == "force-2020": rd = readers.las_in_zip(path, kw["member"])
    elif id == "iodp-rigwatch": rd = readers.rigwatch_csv(path, kw["member"], nrows=kw.get("nrows"))
    elif id == "kgs-las": rd = L.read_las(path)
    elif id == "mseel": rd = readers.las_in_nested_zip(path, kw["inner"], kw["member"])
    else: raise ValueError(f"{id}: link only or reader pending; see {DATASETS[id]['url']}")
    rd.meta.update({"dataset": id, "license": DATASETS[id]["license"], "citation": DATASETS[id]["citation"], "source": DATASETS[id]["url"]})
    out = standard.standardize(rd) if standardize else rd
    try:
        out.attrs["how_to_cite"] = cite(id)
    except AttributeError:
        pass
    _cite_notice(id)
    return out


# ---------------------------------------------------------------- how to cite
OWD_CITATION = ("Delgado-Uriarte, D. (2026). Open Well Data: an index of public subsurface data sources [Data set]. "
                "https://danieldelgadouriarte.com")
_notified = set()


def cite(id=None):
    """Citation text: the original dataset first and Open Well Data after it. Without id, Open Well Data only."""
    if id is None:
        return OWD_CITATION
    return f"{DATASETS[id]['citation']}\nLoaded and standardized with Open Well Data: {OWD_CITATION}"


def _cite_notice(id):
    """One line per dataset and session, on stderr. Silenced with OWD_NO_NOTICE=1."""
    import os, sys
    if id in _notified or os.environ.get("OWD_NO_NOTICE"):
        return
    _notified.add(id)
    print(f"owd: if you use {id} in your work, cite its authors and Open Well Data (Daniel Delgado-Uriarte). "
          f"Text: owd.cite({id!r})", file=sys.stderr)
