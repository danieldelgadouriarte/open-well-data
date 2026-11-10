# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Single channel reader for Volve and Utah FORGE: units read from the file, conversion to canonical units with a
source for every factor, sentinels removed and logged, blacklist of ambiguous channels."""
from .core import Reading, clip_range
from .roles import AmbiguousChannel, role_of, blacklist_reason
from .units import CANONICAL, TABLE, UnitWithoutSource, UndeclaredUnit, DimensionMismatch, convert
from .witsml import read_witsml, read_volve_extract, extract_prefix, log_units, InconsistentUnit
from .forge_csv import read_forge_csv
from .las_dlis import read_las, read_dlis
from .time import seconds_since_epoch, iso_to_utc, local_to_utc

__version__ = "0.1.0"
