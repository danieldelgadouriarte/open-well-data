# Open Well Data

An open index of public well, drilling, seismic and production data sources, with checked access, quoted licences and a verification status per record, plus a Python package (`owd`) that loads selected datasets with standard channel names and SI units.

- **Website:** the catalogue, search (English and Spanish), one page per source, channel dictionary and coverage tables.
- **Catalogue:** [`fichas/sources.jsonl`](fichas/sources.jsonl), one JSON record per source.
- **Package:** [`owd/`](owd/), readers, unit standardization, bilingual search and an MCP server for AI assistants.
- **Site generator:** [`sitio/`](sitio/), a static site with no build dependencies beyond `owd`.

## What a record says

| Field | Meaning |
|---|---|
| `url` | The source itself. Removed (null) when the address no longer belongs to the source. |
| `status` | Verification status: `confirmed` (data opened), `web_verified` (page read), `declared` (from research, not re-checked), `seed` (from a community list, not read), `url_discarded` (dead or hijacked address). |
| `verification` | What the page said when it was read (`what_it_is`, `access_as_written`, `license_as_written`...), and the `date`. |
| `license` | The source's licence as written by the source. |
| `access` | `open`, `registration`, `request_form`, `paid`, `restricted`, `mixed`, `embargo`, `dead` or `not_stated`. |
| `issue` | Problems found: dead links, hijacked domains, inconsistent licences. |
| `catalogue` | Who maintains the catalogue and how to cite it (in the website files). |

The JSON Schema of a record is in [`web/data/source.schema.json`](web/data/source.schema.json).

## Quick start

```python
import owd
owd.search("seismic 3d")              # bilingual search (English or Spanish, with or without accents)
owd.canonical("Hook Load (klbs)")     # 'hookload'
owd.describe("utah-forge-16b")        # licence, citation, how to get it
df = owd.load("utah-forge-16b", "path/to/16B_file.csv")
df.attrs["unit"]["hookload"]          # 'kN'
df.attrs["original"]["hookload"]      # original name and unit
owd.cite("utah-forge-16b")            # citation for the dataset and for Open Well Data
```

A source column gets a standard name only when its unit is declared and either matches the SI unit or converts with a documented factor. Undeclared units keep their original name.

Get a dataset from its source and standardize it on your computer (the data never passes through Open Well Data):

```bash
python -m owd list                 # datasets with a recipe
python -m owd get iodp-rigwatch    # download from Zenodo, verify size and sha256, write Parquet + JSON
python -m owd import volve <file>  # same with a file you downloaded yourself (sources with click-through terms)
```

MCP server for AI assistants (read-only): `python -m owd.mcp_server`.

## Licences

- **Catalogue and derived data files:** [CC BY-NC 4.0](LICENSE-DATA). Free for study, teaching, academic and public research, with credit to "Open Well Data, by Daniel Delgado-Uriarte". Commercial use needs a separate licence: ask through [danieldelgadouriarte.com](https://danieldelgadouriarte.com); free time-limited evaluation licences are available.
- **Code:** [PolyForm Noncommercial 1.0.0](LICENSE). Free for personal study and research, teaching, public research, non-profit and government organizations. Any use by or for a company needs a commercial licence ([COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md)). Versions published before 5 November 2026 keep the AGPL-3.0-only licence they were released under.
- **Contributions:** see [CONTRIBUTING.md](CONTRIBUTING.md).
- **Third-party data:** each listed source keeps its own licence, stated in its record. Nothing here grants rights over third-party data.

## How to cite

See [`CITATION.cff`](CITATION.cff). Cite the original provider of every dataset you use, and Open Well Data when the catalogue, its verification, the channel dictionary or the coverage tables helped your work.

## Maintainer

[Daniel Delgado-Uriarte](https://danieldelgadouriarte.com) · [LinkedIn](https://www.linkedin.com/in/daniel-delgado-uriarte-b9a523278/) · [ORCID 0009-0006-0536-5158](https://orcid.org/0009-0006-0536-5158)
