# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""The 10 MVP datasets and the recipes added on 6 Nov 2026 (2 Italian Zenodo records, GDR 1188) and 7 Nov 2026: what they are, their licence and how they load. Licences read on 3 Nov 2026.

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
   license="CC BY 4.0", policy="copy", tested=True, citation="McLennan, J., Mock, B., Swearingen, L., Baldwin, R., Hodder, M., Vetsak, A., Kuhns, A., Breland, J., & England, K. (2023). Utah FORGE: Well 16B(78)-32 Drilling Data [Data set]. Geothermal Data Repository, Energy and Geoscience Institute at the University of Utah. doi:10.15121/1998591",
   format="Pason CSV"),
 "gdr-1329-pdc-granite": dict(name="PDC bit tests in Sierra White granite (Oklahoma State)",
   url="https://gdr.openei.org/submissions/1329", license="CC BY 4.0", policy="link", tested=True,
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
 "zenodo-italia-info": dict(name="Digitized legacy logs, Irpinia Near Fault Observatory (INFO), Italy",
   url="https://doi.org/10.5281/zenodo.18089199", license="CC BY 4.0", policy="copy", tested=True,
   citation="Ercoli, M., Barchi, M. R., Urbani, M., Safarzadeh, E. (2025). A digitized dataset of legacy geophysical logs from deep boreholes within the Irpinia Near Fault Observatory Area (INFO - Southern Apennines, Italy), v1.0. Zenodo, doi:10.5281/zenodo.18089199",
   format="LAS (and CSV copies) in zip"),
 "zenodo-italia-taboo": dict(name="Digitized legacy logs, Alto Tiberina Near Fault Observatory (TABOO), Italy",
   url="https://doi.org/10.5281/zenodo.21722086", license="CC BY 4.0", policy="copy", tested=True,
   citation="Ercoli, M., Safarzadeh, E., William, A. C., Kadari, N., Barchi, M. R. (2026). A digitized dataset of legacy geophysical logs from deep boreholes within the Alto Tiberina Near Fault Observatory Area - TABOO (Central Italy), v2.0. Zenodo, doi:10.5281/zenodo.21722086",
   format="LAS (and CSV copies) in zip"),
 "zenodo-italia-pesaro-fano": dict(name="Digitized legacy logs, deep boreholes of the 2022 Fano-Pesaro earthquake area (Adriatic Sea, Italy)",
   url="https://doi.org/10.5281/zenodo.17492273", license="CC BY 4.0", policy="copy", tested=True,
   citation="Safarzadeh, E., Ercoli, M., Barchi, M. R., Bertinelli, A. (2025). Dataset of Digitized Stratigraphic and Geophysical Logs from Deep Boreholes in the 2022 Fano-Pesaro Earthquake Area (Adriatic Sea, Italy), v1.0. Zenodo, doi:10.5281/zenodo.17492273",
   format="LAS (with PNG, ODS and CSV) in zip, 141 MB"),
 "ags-dig-2014-0002": dict(name="Alberta water-well geophysical logs (AGS DIG 2014-0002, 8,763 LAS)",
   attribution="Contains information licensed under the Open Government Licence – Alberta (https://open.alberta.ca/licence). Source: Alberta Energy Regulator / Alberta Geological Survey.",
   url="https://ags.aer.ca/publication/dig-2014-0002", license="Open Government Licence - Alberta (open.canada.ca record)", policy="copy", tested=True,
   citation="Alberta Environment and Sustainable Resource Development (2014). Geophysical Wireline Well Logs from Alberta Environment and Sustainable Resource Development Water Well Drill Hole Data Holdings in Log ASCII Standard (LAS) Format. Alberta Energy Regulator / Alberta Geological Survey, Digital Data 2014-0002. https://ags.aer.ca/publication/dig-2014-0002",
   format="8,763 LAS 2.0 in zip, 128 MB"),
 "purr-kentland-well-logs": dict(name="Kentland impact structure (Indiana), digital well logs of the Robitaille thesis",
   url="https://purr.purdue.edu/publications/4738/1", license="CC0 1.0", policy="copy", tested=True,
   citation="Robitaille, B., Schmitt, D. (2024). Kentland Impact Structure: Tomographic, and Well Log Data supporting Robitaille MSc (2024). Purdue University Research Repository, doi:10.4231/0E3T-DJ23",
   format="LAS 2.0 text files in nested zips (PURR bundle, 222 MB)"),
 "gdr-egs-collab-wireline": dict(name="EGS Collab Experiment 1 testbed, wireline geophysics of 8 boreholes (SURF, South Dakota)",
   url="https://gdr.openei.org/submissions/1602", license="CC BY 4.0 (GDR default, 'unless otherwise noted')", policy="copy", tested=False,
   citation="Schwering, P. (2018). EGS Collab Experiment 1: Wireline Geophysical Well Logs. Geothermal Data Repository, doi:10.15121/2350797",
   format="LAS, TXT, CSV and raw logger files in zip, 1.2 GB"),
 "edx-ibdp-well-info": dict(name="Illinois Basin - Decatur Project (IBDP) well information (ISGS, MGSC Phase III)",
   url="https://edx.netl.doe.gov/dataset/illinois-state-geological-survey-isgs-illinois-basin-decatur-project-ibdp-well-information",
   license="Creative Commons Attribution Share-Alike (EDX; version not stated; share-alike)", policy="copy", tested=False,
   citation="Illinois State Geological Survey (2021). Illinois Basin - Decatur Project (IBDP) Well Information, April 30, 2021. Midwest Geological Sequestration Consortium Phase III Data Sets, DOE Cooperative Agreement DE-FC26-05NT42588. NETL EDX",
   format="LAS, DLIS, XLS and PDF in zip, 4.6 GB"),
 "gdr-tuscarora-las": dict(name="Tuscarora Sandstone geophysical log digitization (West Virginia University)",
   url="https://gdr.openei.org/submissions/1188", license="CC BY 4.0", policy="copy", tested=True,
   citation="Moore, J. (2019). Deep Direct-Use Feasibility Study Tuscarora Sandstone Geophysical Log Digitization. West Virginia University. Geothermal Data Repository, doi:10.15121/1593278",
   format="LAS in zip (depth in feet)"),
 # Recipes of 7 Nov 2026 (sources in the redistribution bucket "permitida"; licence text as the bucket reads it).
 "mendeley-adriatic-sonic-las": dict(name="Sonic logs of 12 offshore exploration wells, Adriatic Sea (Italy, ViDEPI)",
   url="https://doi.org/10.17632/xrb2ny6scm.2", license="CC BY 4.0", policy="copy", tested=True,
   citation="Lombardo, C., Cicala, M., De Giosa, F., Sabato, L., Scicchitano, G., Spalluto, L., Tagliaro, G., Tropeano, M., Festa, V. (2026). Sonic Log LAS Files from offshore exploration wells in the middle and southern Adriatic Sea (Italy), derived from the ViDEPI Project (v2). Mendeley Data, doi:10.17632/xrb2ny6scm.2",
   format="12 LAS files"),
 "usgs-npra-ofr-99-15": dict(name="Eleven wildcat wells, National Petroleum Reserve in Alaska (USGS OFR 99-015)",
   url="https://pubs.usgs.gov/of/1999/ofr-99-0015/",
   license="No licence stated on the report page; US public domain per the USGS policy (redistribution bucket 'permitida')",
   policy="copy", tested=True,
   citation="Zihlman, F. N., and Oliver, H. L. (1999). Selected Data from Eleven Wildcat Wells in the National Petroleum Reserve in Alaska. U.S. Geological Survey Open-File Report 99-015. https://pubs.usgs.gov/of/1999/ofr-99-0015/",
   format="19 LAS files (wireline and core gamma ray)"),
 "gdr-glade-cbl": dict(name="GLADE East and West geothermal wells, cement bond logs (Oxy, Colorado)",
   url="https://gdr.openei.org/submissions/1857", license="CC BY 4.0 (GDR default, 'unless otherwise noted')", policy="copy", tested=True,
   citation="Rhodes, R. (2026). GLADE Project: Well Log Files for GLADE East and GLADE West wells. OXY USA Inc. Geothermal Data Repository. https://gdr.openei.org/submissions/1857",
   format="LAS (and PDF) in zip"),
 "gdr-glade-wireline": dict(name="GLADE East and West geothermal wells, wireline logs (Oxy, Colorado)",
   url="https://gdr.openei.org/submissions/1857", license="CC BY 4.0 (GDR default, 'unless otherwise noted')", policy="copy", tested=True,
   citation="Rhodes, R. (2026). GLADE Project: Well Log Files for GLADE East and GLADE West wells. OXY USA Inc. Geothermal Data Repository. https://gdr.openei.org/submissions/1857",
   format="LAS (and PDF) in zip, 422 MB"),
 "edx-secarb-cranfield-logs": dict(name="SECARB Cranfield CO2 site, wells CFU 31F-1, F-2 and F-3 (Mississippi)",
   url="https://edx.netl.doe.gov/dataset/secarb-cranfield-well-logs",
   license="Creative Commons Attribution (EDX; version not stated; redistribution bucket 'permitida')", policy="copy", tested=True,
   citation="SECARB, Gulf Coast Carbon Center, Bureau of Economic Geology, The University of Texas at Austin (2017). SECARB Cranfield Well Logs. NETL EDX, doi:10.18141/1468455",
   format="LAS (and PDF, PDS) in 3 zip"),
 "edx-cranfield-other-wells": dict(name="SECARB Cranfield CO2 site, other wells of the field (Mississippi)",
   url="https://edx.netl.doe.gov/dataset/secarb-cranfield-well-logs",
   license="Creative Commons Attribution (EDX; version not stated; redistribution approved by Daniel on 7 Nov 2026)", policy="copy", tested=True,
   citation="SECARB, Gulf Coast Carbon Center, Bureau of Economic Geology, The University of Texas at Austin (2017). SECARB Cranfield Well Logs. NETL EDX, doi:10.18141/1468455",
   format="LAS and deviation files in zip"),
 "gdr-srp-forge-inel1": dict(name="Snake River Plain FORGE, well INEL-1 logs (Idaho)",
   url="https://gdr.openei.org/submissions/792", license="CC BY 4.0 (GDR default, 'unless otherwise noted')", policy="copy", tested=True,
   citation="Prestwich, S. M., and Bowman, J. A. (1979). Snake River Plain FORGE: Well Data for INEL-1. Idaho National Laboratory. Geothermal Data Repository, doi:10.15121/1261969",
   format="LAS 1.2 in zip (depth in feet)"),
 "tno-nieuwerkerk-well-logs": dict(name="Well-log supplementary dataset of Dutch wells (TNO, Deliverable 2.1)",
   url="https://doi.org/10.5281/zenodo.20428397", license="CC0 1.0", policy="copy", tested=True,
   citation="Niederau, J., Sadrikhanloo, S., Carpentier, S., De Boever, E. (2026). Well-log supplementary dataset (Deliverable 2.1 - Dataset). Zenodo, doi:10.5281/zenodo.20428397",
   format="LAS in a zip inside a zip, 104 MB"),
 "4tu-delft-del-gt-logs": dict(name="TU Delft campus geothermal wells DEL-GT-01 and DEL-GT-02, wireline logs",
   url="https://doi.org/10.4121/2a7b2a63-dd7b-46bc-a275-97729b3ab348.v2", license="CC BY 4.0", policy="copy", tested=True,
   citation="Barnhoorn, A., Vondrak, A., Laumann, S., van Esser, B., Vargas Meleza, L., Abels, H. A., Vardon, P. J. (2024). Geothermal Project on TU Delft Campus - DEL-GT-01 and DEL-GT-02 Wireline Logs (v2). 4TU.ResearchData, doi:10.4121/2a7b2a63-dd7b-46bc-a275-97729b3ab348.v2",
   format="LAS 2.0 in zip, 1.29 GB"),
 "gdr-forge-58-32-pason": dict(name="Utah FORGE well 58-32, processed Pason drilling log at 1 ft",
   url="https://gdr.openei.org/submissions/1113", license="CC BY 4.0", policy="copy", tested=True,
   citation="Podgorney, R., McLennan, J., Moore, J. (2018). Utah FORGE: Drilling Data for Student Competition. Idaho National Laboratory. Geothermal Data Repository, doi:10.15121/1495411",
   format="CSV, depth index (ft and m columns)"),
 "gdr-cubo-esh1-depth": dict(name="Cornell CUBO well ESH-1, Pason drilling parameters by depth",
   url="https://gdr.openei.org/submissions/1849", license="CC BY 4.0", policy="copy", tested=True,
   citation="Fulton, P., Jordan, T., Gustafson, O., Tester, J., Erdinc, B. (2026). Drilling Parameters for ESH-1 Well at Cornell University Borehole Observatory. Cornell University. Geothermal Data Repository. https://gdr.openei.org/submissions/1849", format="CSV (GDR standard: units in the second row)"),
 "gdr-cubo-esh1-time-jun-jul": dict(name="Cornell CUBO well ESH-1, Pason drilling parameters in time, Jun-Jul 2022",
   url="https://gdr.openei.org/submissions/1849", license="CC BY 4.0", policy="copy", tested=True,
   citation="Fulton, P., Jordan, T., Gustafson, O., Tester, J., Erdinc, B. (2026). Drilling Parameters for ESH-1 Well at Cornell University Borehole Observatory. Cornell University. Geothermal Data Repository. https://gdr.openei.org/submissions/1849", format="Pason CSV (1 s) in zip, 117 MB"),
 "gdr-cubo-esh1-time-jul-sep": dict(name="Cornell CUBO well ESH-1, Pason drilling parameters in time, Jul-Sep 2022",
   url="https://gdr.openei.org/submissions/1849", license="CC BY 4.0", policy="copy", tested=True,
   citation="Fulton, P., Jordan, T., Gustafson, O., Tester, J., Erdinc, B. (2026). Drilling Parameters for ESH-1 Well at Cornell University Borehole Observatory. Cornell University. Geothermal Data Repository. https://gdr.openei.org/submissions/1849", format="Pason CSV (10 s) in zip"),
 "wapims-wa-petroleum-wells": dict(name="Western Australia petroleum wells, header table (DMPE, SLIP layer DMIRS-025)",
   url="https://catalogue.data.wa.gov.au/dataset/wa-onshore-petroleum-wells-dmirs-025", license="CC BY 4.0", policy="copy", tested=True,
   citation="© State of Western Australia (Department of Mines, Petroleum and Exploration) 2026. WA Onshore Petroleum Wells (DMIRS-025), Shared Location Information Platform (SLIP), https://catalogue.data.wa.gov.au/dataset/wa-onshore-petroleum-wells-dmirs-025. Based on Department of Mines, Petroleum and Exploration material.",
   format="GeoJSON from the SLIP ArcGIS REST service (one point per well)")
}

SPDX = {"volve": "LicenseRef-Equinor-Open-Data", "utah-forge-16b": "CC-BY-4.0", "gdr-1329-pdc-granite": "CC-BY-4.0",
        "3w": "CC-BY-4.0", "iodp-rigwatch": "CC-BY-4.0", "force-2020": "CC-BY-4.0", "kgs-las": "LicenseRef-KGS-Terms",
        "mseel": "NOASSERTION", "namss": "CC0-1.0", "f3": "CC-BY-SA-3.0",
        "zenodo-italia-info": "CC-BY-4.0", "zenodo-italia-taboo": "CC-BY-4.0", "gdr-tuscarora-las": "CC-BY-4.0",
        "mendeley-adriatic-sonic-las": "CC-BY-4.0", "usgs-npra-ofr-99-15": "LicenseRef-USGS-Public-Domain",
        "gdr-glade-cbl": "CC-BY-4.0", "gdr-glade-wireline": "CC-BY-4.0", "edx-secarb-cranfield-logs": "LicenseRef-EDX-CC-BY-unversioned", "edx-cranfield-other-wells": "LicenseRef-EDX-CC-BY-unversioned", "zenodo-italia-pesaro-fano": "CC-BY-4.0", "ags-dig-2014-0002": "LicenseRef-OGL-Alberta", "purr-kentland-well-logs": "CC0-1.0", "gdr-egs-collab-wireline": "CC-BY-4.0", "edx-ibdp-well-info": "LicenseRef-EDX-CC-BY-SA-unversioned",
        "gdr-srp-forge-inel1": "CC-BY-4.0", "tno-nieuwerkerk-well-logs": "CC0-1.0", "4tu-delft-del-gt-logs": "CC-BY-4.0",
        "gdr-forge-58-32-pason": "CC-BY-4.0", "gdr-cubo-esh1-depth": "CC-BY-4.0", "gdr-cubo-esh1-time-jun-jul": "CC-BY-4.0",
        "gdr-cubo-esh1-time-jul-sep": "CC-BY-4.0", "wapims-wa-petroleum-wells": "CC-BY-4.0"}
LAS_IN_ZIP = ("zenodo-italia-info", "zenodo-italia-taboo", "gdr-tuscarora-las", "gdr-glade-cbl", "gdr-glade-wireline",
              "edx-secarb-cranfield-logs", "gdr-srp-forge-inel1", "tno-nieuwerkerk-well-logs", "edx-cranfield-other-wells", "zenodo-italia-pesaro-fano", "ags-dig-2014-0002", "purr-kentland-well-logs", "4tu-delft-del-gt-logs", "gdr-egs-collab-wireline", "edx-ibdp-well-info")
LAS_FILES = ("mendeley-adriatic-sonic-las", "usgs-npra-ofr-99-15")
PASON_CSV = ("gdr-cubo-esh1-depth", "gdr-cubo-esh1-time-jun-jul", "gdr-cubo-esh1-time-jul-sep")
for _k, _v in SPDX.items(): DATASETS[_k]["spdx"] = _v

# Licence of Open Well Data's own standardized copies (decision of 8 Nov 2026). Default CC BY-NC 4.0; the source decides
# when its licence requires it: share-alike sources (ANH Colombia, IBDP) give CC BY-SA 4.0, Equinor Volve keeps the
# Equinor Open Data Licence, and any source more restrictive than CC BY-NC 4.0 keeps its own licence. Nothing of ours is
# CC BY. When the source is more permissive (CC BY, CC0), the original stays under its licence at the source and
# CC BY-NC 4.0 covers Open Well Data's contribution (names, units, provenance, packaging).
CC_BY_NC = ("CC BY-NC 4.0", "CC-BY-NC-4.0", "https://creativecommons.org/licenses/by-nc/4.0/")
CC_BY_SA = ("CC BY-SA 4.0", "CC-BY-SA-4.0", "https://creativecommons.org/licenses/by-sa/4.0/")
EQUINOR = ("Equinor Open Data Licence (Volve)", "LicenseRef-Equinor-Open-Data", "https://www.equinor.com/energy/volve-data-sharing")
PERMISSIVE = {"LicenseRef-OGL-Alberta", "LicenseRef-EDX-CC-BY-unversioned", "LicenseRef-USGS-Public-Domain", "CC0-1.0", "CC-BY-4.0", "CC-BY-3.0", "CC-BY-2.0", "PDDL-1.0", "ODC-By-1.0", "NLOD-2.0", "OGL-UK-3.0", "OGL-Canada-2.0",
              "etalab-2.0", "DL-DE-BY-2.0", "PDM-1.0", "CC-BY-NC-4.0"}


# Open Government Licence - Alberta 2.2 (official text, https://open.alberta.ca/licence, read 9 Nov 2026): «Copy, modify, publish, translate, adapt, distribute or otherwise use
# the Information in any medium, mode or format for any lawful purpose», acknowledging the source with the provider's
# attribution statement and, where possible, a link to the licence; the default statement is the one below. AGS asks for
# acknowledgement of the Alberta Energy Regulator / Alberta Geological Survey as the originator of the information.
OGL_ALBERTA_VERSION = "2.2"
OGL_ALBERTA_URL = "https://open.alberta.ca/licence"
OGL_ALBERTA_NOT_ENDORSED = "No endorsement by the Government of Alberta is implied."
OGL_ALBERTA_ATTRIBUTION = ("Contains information licensed under the Open Government Licence – Alberta "
                           "(https://open.alberta.ca/licence). Source: Alberta Energy Regulator / Alberta Geological Survey.")


def copy_licence(source_spdx):
    """(name, SPDX, URL) of the licence of an Open Well Data standardized copy of a source with this SPDX licence, or None
    when the source keeps its own (more restrictive or unclear) licence."""
    s = source_spdx or ""
    if s.startswith("CC-BY-SA") or "CC-BY-SA" in s:  # 9 Nov 2026: also LicenseRef-EDX-CC-BY-SA-unversioned (IBDP)
        return CC_BY_SA
    if s == "LicenseRef-Equinor-Open-Data":
        return EQUINOR
    if s in PERMISSIVE:
        return CC_BY_NC
    return None


for _k, _d in DATASETS.items():
    _c = copy_licence(_d["spdx"]) if _d["policy"] == "copy" else None
    _d["owd_copy_license"] = _c[0] if _c else None
    _d["owd_copy_spdx"] = _c[1] if _c else None
    _d["owd_copy_license_url"] = _c[2] if _c else None

def info(id): return DATASETS[id]

def describe(id):
    """Everything an agent needs about a dataset in one object: what it is, licence, how to get it and load it."""
    d = dict(DATASETS[id]); d["id"] = id
    d["how_to_load"] = {"copy": "download the standardized copy (once published) or the original, then owd.load(id, path)",
                        "recipe": "download the original from the source with the user's own account, then owd.load(id, path)",
                        "link": "reference only; see url"}[d["policy"]]
    return d

def load(id, path, standardize=True, names=None, units=None, **kw):
    """Load a file already downloaded from the original source and return it with standard names and units.
    names ("owd" or "original") and units ("si", "field" or {variable: unit}) pass the result through the conversion
    engine (owd.convert); df.attrs["provenance"] then holds the per-channel provenance and the citation. Without them
    the behaviour is the previous one.
    Volve: path = .csv.gz extract and kw witsml_zip=...; FORGE: Pason CSV; GDR 1329: zip and kw member=...;
    3W: parquet; FORCE 2020: zip and kw member=...; IODP: zip and kw member=...; KGS: LAS; MSEEL: kw inner=..., member=..."""
    if id == "volve": rd = L.read_volve_extract(path, kw["witsml_zip"], channels=kw.get("channels"))
    elif id == "utah-forge-16b": rd = L.read_forge_csv(path, channels=kw.get("channels"))
    elif id == "gdr-1329-pdc-granite": rd = readers.gdr1329_txt(path, kw["member"])
    elif id == "3w": rd = readers.threew_parquet(path)
    elif id == "force-2020": rd = readers.las_in_zip(path, kw["member"])
    elif id in LAS_IN_ZIP: rd = readers.las_in_zip(path, kw["member"])
    elif id in LAS_FILES: rd = L.read_las(path)
    elif id in PASON_CSV: rd = L.read_forge_csv(path, channels=kw.get("channels"))
    elif id == "gdr-forge-58-32-pason": rd = readers.depth_csv(path)
    elif id == "iodp-rigwatch": rd = readers.rigwatch_csv(path, kw["member"], nrows=kw.get("nrows"))
    elif id == "kgs-las": rd = L.read_las(path)
    elif id == "mseel": rd = readers.las_in_nested_zip(path, kw["inner"], kw["member"])
    else: raise ValueError(f"{id}: link only or reader pending; see {DATASETS[id]['url']}")
    rd.meta.update({"dataset": id, "license": DATASETS[id]["license"], "citation": DATASETS[id]["citation"], "source": DATASETS[id]["url"]})
    out = standard.standardize(rd) if standardize else rd
    if names is not None or units is not None:
        out = _convert_loaded(id, rd, out if standardize else None, names or "owd", units or "si")
    try:
        out.attrs["how_to_cite"] = cite(id)
    except AttributeError:
        pass
    _cite_notice(id)
    return out


def _convert_loaded(id, rd, std, names, units):
    """Pass a loaded dataset through the conversion engine. From the standardized frame when there is one (its units
    are OWD standard); names="original" restores the source mnemonics before the engine maps them again."""
    from . import convert
    if std is not None:
        df, unit, original = std, dict(std.attrs.get("unit") or {}), std.attrs.get("original") or {}
        if names == "original":
            ren = {c: (original.get(c) or {}).get("name") or c for c in df.columns}
            df = df.rename(columns=ren)
            unit = {ren[c]: u for c, u in unit.items() if c in ren}
    else:
        df, unit = rd.data, dict(rd.unit)
    fmt = (rd.meta.get("format") or "table").upper()
    fmt = fmt if fmt in convert.LOG_FORMATS else "table"
    out, prov = convert.convert_frame(df, unit, names=names, units=units, source_format=fmt,
                                      source=convert.source_info(id), descriptions=rd.description)
    for k in ("dataset", "license", "citation", "source", "file", "format"):
        if k in rd.meta and k not in out.attrs:
            out.attrs[k] = rd.meta[k]
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
