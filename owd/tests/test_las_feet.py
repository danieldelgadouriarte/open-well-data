# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""LAS with the depth unit written F (feet), as in KGS, WVGS and GDR files: read and converted to metres."""
import pytest

from owd._reader import las_dlis as L
from owd._reader import units as U

pytest.importorskip("lasio")

LAS = """~Version
VERS.   2.0 :
WRAP.   NO  :
~Well
STRT.F  1000.0 :
STOP.F  1001.0 :
STEP.F  0.5    :
NULL.   -999.25 :
~Curve
DEPT.F      : Depth
GR  .GAPI   : Gamma ray
TEMP.F      : Temperature
~A
1000.0  50.0  120.0
1000.5  60.0  121.0
1001.0  -999.25  122.0
"""


@pytest.mark.parametrize("unit", ["F", "FT", "FT.", "FEET", "ft"])
def test_depth_in_feet_is_read(tmp_path, unit):
    p = tmp_path / "feet.las"
    text = LAS.replace("DEPT.F ", f"DEPT.{unit} ") if unit != "FT." else LAS.replace("DEPT.F      :", "DEPT.FT.    :")
    p.write_text(text)
    rd = L.read_las(str(p), source="kgs")
    assert list(rd.data.index) == pytest.approx([304.8, 304.9524, 305.1048])
    assert rd.meta["index_unit"] in ("F", "FT", "FT.", "FEET", "ft")


def test_F_is_never_guessed_without_a_dimension():
    assert U.lookup("F") is None                      # ambiguous: feet or degF
    assert U.lookup("F", "length")["factor"] == 0.3048
    assert U.lookup("F", "temperature")["canonical"] == "degC"


def test_temperature_in_F_without_role_is_left_as_is(tmp_path):
    p = tmp_path / "feet.las"
    p.write_text(LAS)
    rd = L.read_las(str(p), source="kgs")
    assert rd.unit.get("TEMP") == "F" and list(rd.data["TEMP"])[:2] == [120.0, 121.0]
