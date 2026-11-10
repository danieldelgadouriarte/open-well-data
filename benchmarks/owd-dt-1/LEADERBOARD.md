# OWD-DT-1: compressional sonic (DT) from other logs

Data: FORCE 2020 wells, standardized by Open Well Data (standardized copy CC BY-NC 4.0; original data CC BY 4.0, doi:10.5281/zenodo.4351156).
Inputs: gamma ray (gAPI), bulk density (g/cm3), log10 deep resistivity (ohm.m), depth. Target: DT (us/ft).
Split by well, fixed: sha1(well name) % 100 → train < 70, validation < 85, test otherwise (82 / 19 / 17 wells).
Rows with all inputs and target present; physical range filter only. Test rows: 191,134.

| Model | Type | RMSE (us/ft) | MAE (us/ft) |
|---|---|---|---|
| Training mean | naive | 29.27 | 25.69 |
| Linear regression | data | 13.43 | 9.78 |
| Quadratic regression | data | 12.16 | 8.40 |

Baselines use numpy only and are fully reproducible. Submit results on the test wells with the same split.
