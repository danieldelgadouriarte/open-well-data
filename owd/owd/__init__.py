# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Free for non-commercial use; companies need a licence (see NOTICE).
"""Open Well Data: public well, drilling and subsurface data with standard names and units."""
from .registry import DATASETS, load, info, describe, cite
from .catalog import search, sources
from .standard import canonical, CHANNELS
from .index import variables, search_variables
from .recipes import get, import_data, RecipeError
__version__ = "0.0.1"
