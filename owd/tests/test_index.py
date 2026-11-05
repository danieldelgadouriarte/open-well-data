# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Free for non-commercial use; companies need a licence (see NOTICE).
from owd import index, standard


def test_standard_channels_in_the_dictionary():
    v = {x["variable"]: x for x in index.variables()}
    for c in standard.CHANNELS:
        assert c["canonical"] in v, c["canonical"]
        assert v[c["canonical"]]["unit"] == c["unit"], c["canonical"]
        assert v[c["canonical"]]["standard_channel"] == "yes"
    assert sum(x["standard_channel"] == "yes" for x in v.values()) == len(standard.CHANNELS)


def test_unique_variables():
    names = [x["variable"] for x in index.variables()]
    assert len(names) == len(set(names))


def test_search_force_logs():
    r = index.search_variables(["gr", "rhob", "dt"])
    assert set(r.dataset) == {"force-2020"} and r.well.nunique() > 100
    assert (r.envelope_m >= 0).all()


def test_search_unknown_variable():
    import pytest
    with pytest.raises(KeyError):
        index.search_variables(["does_not_exist"])


def test_fraction_m3m3_is_vv():
    assert standard.equivalent_unit("m3/m3") == "v/v"
