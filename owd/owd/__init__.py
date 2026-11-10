# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Open Well Data: public well, drilling and subsurface data with standard names and units."""
from .registry import DATASETS, load, info, describe, cite
from .catalog import search, sources
from .standard import canonical, CHANNELS
from .index import variables, search_variables
from .recipes import get, import_data, RecipeError
from .convert import convert_frame, convert_file, convert_text, ConversionError
__version__ = "1.1.0"
