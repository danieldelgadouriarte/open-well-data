# owd, the Open Well Data Python package

Open Well Data: public subsurface data for oil, gas and CCS. Website: https://openwelldata.org

Loads public drilling, log and production datasets and returns standard channel names in SI units, with the original name and unit attached to every column.

```python
import owd
owd.DATASETS.keys()                       # datasets with a reader
owd.describe("iodp-rigwatch")             # licence, policy, citation, how to load
df = owd.load("utah-forge-16b", "file.csv")
owd.search("wells norway")                # bilingual catalogue search (English or Spanish)
owd.search_variables(["gr", "rhob", "dt"])  # wells and files that have all three
owd.cite("utah-forge-16b")
```

Rules:

- A channel is renamed only when its unit is declared and matches the SI unit or converts with a documented factor (`owd/_reader/units.tsv` lists each factor and its source).
- Undeclared or unknown units keep the original name. The package never guesses.
- Duplicated source columns keep their full original name.

Standard channels: `owd/channels.tsv` (28 channels: drilling, logs, production). Variable dictionary: `owd/variables.tsv`.

MCP server (read-only, stdio): `python -m owd.mcp_server`. Tools: `search_sources`, `list_datasets`, `describe_dataset`, `standard_channels`, `standard_name`, `variables` and `search_by_variables`. Every answer carries a `how_to_cite` field.

Tests: `python -m pytest -q tests`. Real-data tests run when `OWD_TEST_DATA` points to a folder with the original files.

Licence: code PolyForm Noncommercial 1.0.0 (free for non-commercial use); the bundled catalogue, dictionaries and recipes CC BY-NC 4.0. Commercial licences: https://danieldelgadouriarte.com

## MCP server

Read-only tools over the catalogue and the datasets, over stdio: `owd-mcp` (or `python -m owd.mcp_server`). Install with `pip install "openwelldata[mcp]"`.

<!-- mcp-name: io.github.danieldelgadouriarte/open-well-data -->
