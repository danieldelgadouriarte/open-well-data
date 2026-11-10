# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Statistic qualifier (7 Nov 2026): statistic variants of a variable are not merged into one column name."""
from owd import convert as C, index, mnemonic_lookup, standard

IX = C.index()


def plans(chs, fmt="WITSML", names="owd"):
    return C.plan_channels([{"name": n, "unit": u, "description": d} for n, u, d in chs], names, "si", fmt)


def by_orig(ps):
    return {p["original_name"]: p for p in ps}


# ------------------------------------------------------------------ the Volve hookload case
VOLVE_HKL = [("HKLD_MIN", "kkgf", "Hookload (min)"), ("HKLX", "kkgf", "Maximum Hookload"),
             ("HKLD_AVG", "kkgf", "Average Hookload"), ("HKLD", "kkgf", "Average Hookload")]


def test_hookload_min_max_mean_are_not_merged():
    p = by_orig(plans(VOLVE_HKL))
    assert p["HKLD_MIN"]["name"] == "hookload_min" and p["HKLD_MIN"]["statistic"] == "min"
    assert p["HKLX"]["name"] == "hookload_max" and p["HKLX"]["statistic"] == "max"
    assert p["HKLX"]["statistic_evidence"] == "description"          # the X alone says nothing
    assert p["HKLD_AVG"]["name"] == "hookload_mean" and p["HKLD_AVG"]["statistic_evidence"] == "name+description"
    # two channels with the same variable and statistic: a true duplicate keeps the numeric suffix
    assert p["HKLD"]["name"] == "hookload_mean_2" and p["HKLD"]["statistic"] == "mean"
    assert {x["variable"] for x in p.values()} == {"hookload"}          # one variable for every variant
    assert not any(x["name"] == "hookload" for x in p.values())         # nobody reads a minimum as "hookload"


def test_name_alone_and_description_alone():
    assert by_orig(plans([("HKLD_MIN", "kkgf", "")]))["HKLD_MIN"]["name"] == "hookload_min"
    assert by_orig(plans([("HKLX", "kkgf", "")]))["HKLX"]["name"] == "hookload"        # no evidence: unspecified
    p = by_orig(plans([("HKLD", "kkgf", "Average Hookload")]))["HKLD"]
    assert (p["name"], p["statistic"], p["statistic_evidence"]) == ("hookload_mean", "mean", "description")
    p = by_orig(plans([("HKLD", "kkgf", "Measured Hookload 2hz")]))["HKLD"]
    assert (p["name"], p["statistic"], p["window"]) == ("hookload", "unspecified", None)


def test_bare_mnemonic_is_not_assumed_a_mean():
    p = by_orig(plans([("HKLD", "kkgf", ""), ("HKLA", "kkgf", "")], "LAS"))
    assert [p["HKLD"]["name"], p["HKLA"]["name"]] == ["hookload", "hookload_2"]
    assert p["HKLD"]["statistic"] == p["HKLA"]["statistic"] == "unspecified"


def test_hmin_microlog_is_not_a_minimum():
    st, win, ev, w = C.channel_statistic("HMIN", "Micro Inverse Resistivity", "res_flushed")
    assert (st, ev) == ("unspecified", None)
    p = plans([("HMIN", "ohm.m", "Micro Inverse Resistivity")], "LAS")[0]
    assert (p["variable"], p["name"], p["statistic"]) == ("res_flushed", "res_flushed", "unspecified")
    # a glued MIN counts only when the stem is a mnemonic of the same variable: H is not one of res_flushed
    assert "H" not in IX.t["variables"]["res_flushed"]["mnemonics"]
    assert C.channel_statistic("HMIN", "", "res_flushed")[0] == "unspecified"


def test_glued_suffix_needs_a_mnemonic_stem():
    assert C.channel_statistic("WOBAVG", "", "wob")[:3] == ("mean", None, "name")
    assert C.channel_statistic("PUMPAVG", "", "spp")[0] == "mean"
    assert C.channel_statistic("TQX", "", "surface_torque")[0] == "unspecified"
    assert C.channel_statistic("TQX", "Maximum Surface Torque", "surface_torque")[0] == "max"


def test_windows_and_rop():
    st, win, ev, _ = C.channel_statistic("ROP5", "Rate of Penetration (5ft avg)", "rop")
    assert (st, win) == ("mean", "5 ft")
    assert C.channel_statistic("ROP_AVG", "Time Averaged ROP", "rop")[:2] == ("mean", "time")
    assert C.channel_statistic("ROP_AVG", "Depth Averaged ROP", "rop")[:2] == ("mean", "depth")
    assert C.channel_statistic("ROP5", "5ft ROP 2hz", "rop")[:2] == ("mean", "5 ft")
    assert C.channel_statistic("ROP", "Rate of Penetration", "rop")[0] == "unspecified"
    assert C.channel_statistic("ROPI", "EDR Instantaneous ROP", "rop")[0] == "inst"
    assert C.qualified_name("rop", "inst") == "rop"


def test_false_friends_in_descriptions():
    assert C.channel_statistic("TVDSS", "True Vertical Depth measured from Mean Sea Level", "tvdss")[0] in (None, "unspecified")
    assert C.channel_statistic("TFLO", "Total Pump Flow (L/min)", "flow_in")[0] == "unspecified"
    assert C.channel_statistic("DPHZ", "Std. Res. Density Porosity", "density_porosity")[0] == "unspecified"
    assert C.channel_statistic("PEFL", "HLDS Weighted Average Photoelectric Factor", "pef")[0] == "unspecified"


def test_name_and_description_disagree():
    # Volve copies "Surface Torque Average" onto TORQUE_MAX and TORQUE_MIN: the statistic word in the name wins, warned
    st, win, ev, w = C.channel_statistic("TORQUE_MAX", "Surface Torque Average", "surface_torque")
    assert (st, ev) == ("max", "name_over_description") and w and "the name says max" in w[0]
    # several statistics in one description and nothing in the name: unspecified
    st, win, ev, w = C.channel_statistic("HKLD", "Hookload, maximum and minimum", "hookload")
    assert (st, ev) == ("unspecified", "conflict") and w and "statistic unclear" in w[0]


def test_windows_do_not_read_chemistry_or_fractions():
    assert C.channel_statistic("H2S1_AVG", "H2S Sensor 1", "gas_h2s")[:2] == ("mean", None)
    assert C.channel_statistic("ROPH", "1/2ft ROP", "rop")[:2] == ("mean", None)
    assert C.channel_statistic("ROP2M", "Rate of Penetration 2 minute average", "rop")[:2] == ("mean", "2 min")
    assert C.channel_statistic("SFLA", "SFL Resistivity Averaged over 2.5 Feet", "res_shallow")[:2] == ("mean", "2.5 ft")


def test_other_drilling_families():
    p = by_orig(plans([("WOB_AVG", "kkgf", ""), ("WOB_MAX", "kkgf", ""), ("WOB_MIN", "kkgf", ""),
                       ("WOBX", "kkgf", "Maximum Weight on Bit"),
                       ("TQA", "kN.m", "Average Surface Torque"), ("TORQUE_MIN", "kN.m", ""),
                       ("SPPA", "kPa", "Average Standpipe Pressure"), ("PUMP_MAX", "kPa", ""),
                       ("TOTGAS_AVG", "%", ""), ("TOTGAS_MAX", "%", ""), ("TOTGAS_MIN", "%", ""),
                       ("ANNVEL_MMAX", "m/s", "Annular Velocity Monitor Maximum")]))
    got = {k: v["name"] for k, v in p.items()}
    assert got == {"WOB_AVG": "wob_mean", "WOB_MAX": "wob_max", "WOB_MIN": "wob_min", "WOBX": "wob_max_2",
                   "TQA": "surface_torque_mean", "TORQUE_MIN": "surface_torque_min", "SPPA": "spp_mean",
                   "PUMP_MAX": "spp_max", "TOTGAS_AVG": "total_gas_mean", "TOTGAS_MAX": "total_gas_max",
                   "TOTGAS_MIN": "total_gas_min", "ANNVEL_MMAX": "annular_velocity_max"}


def test_round_trip_of_qualified_names():
    p = by_orig(plans([("hookload_max", "kN", ""), ("hookload_mean", "kN", ""), ("hookload", "kN", "")], "table"))
    assert [p[k]["variable"] for k in ("hookload_max", "hookload_mean", "hookload")] == ["hookload"] * 3
    assert [p[k]["name"] for k in ("hookload_max", "hookload_mean", "hookload")] == ["hookload_max", "hookload_mean", "hookload"]
    assert C.parse_output_name("hookload_max_2") == ("hookload", "max")
    assert C.parse_output_name("hookload") == ("hookload", "unspecified")
    for v in IX.t["variables"]:      # no variable name looks like a qualified one, and every name parses back
        assert C.parse_output_name(v) == (v, "unspecified"), v
        assert not C._QUALIFIED_NAME.match(v), v


def test_provenance_records_statistic_and_window():
    prov = C.provenance(plans([("ROP5", "m/h", "Rate of Penetration (5ft avg)"), ("GR", "gAPI", "")], "LAS"))
    ch = by_orig(prov["channels"])
    assert (ch["ROP5"]["statistic"], ch["ROP5"]["window"], ch["ROP5"]["statistic_evidence"]) == ("mean", "5 ft", "description")
    assert ch["GR"]["statistic"] == "unspecified" and ch["GR"]["window"] is None
    assert prov["open_well_data"]["engine_version"] == C.ENGINE_VERSION == "1.1"


def test_dictionary_version_includes_the_rules():
    t = C.tables()
    assert t["format"] == 2 and t["statistics"] and "channel_statistics.tsv" in C.DICTIONARY_FILES
    t2 = dict(t, statistics=[])
    import hashlib, json
    strip = lambda x: {k: v for k, v in x.items() if k not in ("meta", "datasets", "copies_base_url")}
    h = lambda x: hashlib.sha256(json.dumps(strip(x), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()[:12]
    assert h(t) == t["meta"]["dictionary_version"] != h(t2)


def test_search_finds_every_variant():
    vs = {v["mnemonic"]: v for v in mnemonic_lookup.variants("hookload")}
    assert {"HKLD", "HKLD_MIN", "HKLD_MAX", "HKLX", "HKLD_AVG"} <= set(vs)
    assert vs["HKLD_MIN"]["statistic"] == "min" and vs["HKLD_MIN"]["output_names"] == ["hookload_min"]
    assert vs["HKLD_AVG"]["statistic"] == "mean"
    r = mnemonic_lookup.lookup("HKLD_MIN")
    assert r["variable"] == "hookload" and r["statistic"] == "min"
    assert index.statistic_of("hookload_max", "hookload") == "max"
    assert index.statistic_of("hookload_2", "hookload") == "unspecified"


def test_reader_layer_keeps_variants_apart():
    import pandas as pd
    from owd._reader.core import Reading
    df = pd.DataFrame({"HKLD_MIN": [1.0], "HKLX": [2.0], "HKLD": [1.5]})
    rd = Reading(data=df, unit={c: "kkgf" for c in df}, source_unit={c: "kkgf" for c in df},
                 role={c: "HKL" for c in df}, description={"HKLX": "Maximum Hookload", "HKLD": "Average Hookload"},
                 meta={})
    out = standard.standardize(rd)
    assert list(out.columns) == ["hookload_min", "hookload_max", "hookload_mean"]
    assert out.attrs["statistic"]["hookload_max"] == {"variable": "hookload", "statistic": "max", "window": None}


# ------------------------------------------------------------------ log families (Daniel, 7 Nov 2026)
def test_log_statistic_only_in_provenance():
    p = plans([("GRMA", "gAPI", "Gamma Ray, Average"), ("BCAV", "in", "Best Caliper, Average Diameter")], "LAS")
    assert [(x["name"], x["statistic"]) for x in p] == [("gr", "mean"), ("caliper", "mean")]
    prov = C.provenance(p)
    assert by_orig(prov["channels"])["GRMA"]["statistic"] == "mean"
    # mean next to an unspecified channel of the same log variable: still plain names, numeric suffix
    p = by_orig(plans([("GR", "gAPI", "Gamma Ray"), ("GRMA", "gAPI", "Gamma Ray, Average")], "LAS"))
    assert (p["GR"]["name"], p["GRMA"]["name"], p["GRMA"]["statistic"]) == ("gr", "gr_2", "mean")


def test_log_suffix_when_two_statistics_coexist():
    p = by_orig(plans([("CALX", "in", "Caliper, maximum diameter"), ("CALY", "in", "Caliper, minimum diameter"),
                       ("CALI", "in", "Caliper")], "LAS"))
    assert {k: (v["variable"], v["name"]) for k, v in p.items() if v["variable"]} == {
        "CALX": ("caliper", "caliper_max"), "CALY": ("caliper", "caliper_min"), "CALI": ("caliper", "caliper")}


def test_naming_statistics_rule():
    assert C.naming_statistics([("hookload", "max"), ("gr", "mean"), ("caliper", "max"), ("caliper", "min"),
                                ("caliper", "unspecified"), (None, None)]) == ["max", None, "max", "min", None, None]
    vs = {v["mnemonic"]: v for v in mnemonic_lookup.variants("gr")}
    assert vs["GRMA"]["statistic"] == "mean" and vs["GRMA"]["output_names"] == ["gr"]


def test_reader_layer_logs_plain():
    import pandas as pd
    from owd._reader.core import Reading
    df = pd.DataFrame({"GRMA": [1.0]})
    rd = Reading(data=df, unit={"GRMA": "gAPI"}, source_unit={"GRMA": "gAPI"}, description={"GRMA": "Gamma Ray, Average"},
                 role={}, meta={})
    out = standard.standardize(rd)
    if "gr" in out.columns:
        assert out.attrs["statistic"]["gr"]["statistic"] == "mean"
