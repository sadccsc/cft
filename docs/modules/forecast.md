# Forecast

The forecast module builds statistical seasonal forecast models, cross-validates them, and produces deterministic and probabilistic forecasts with skill scores.

## Inputs

**Predictand** — the variable to be forecast:

- gridded data, as a netCDF file; or
- station data, as a CSV file with dates in the first column and one column per station. The top three rows hold the station ID, latitude and longitude (`ID`, `Lat`, `Lon`).

**Predictors:**

- observed teleconnection indices, such as those from the [download module](download.md);
- observed gridded fields, such as SST;
- forecast gridded fields *(not yet implemented)*.

## Forecast levels

| Level | Predictand | Description |
|---|---|---|
| Grid | gridded | a forecast for every grid cell |
| Zones | gridded or station | the predictand is averaged over each zone, and the forecast is made for that average |
| Points | station | a forecast for every station |

## Pre-processing

| Approach | Description |
|---|---|
| PCR | the gridded predictor is reduced to principal components (EOFs), which are used as predictors in the model |
| CCA | canonical components are derived jointly from predictor and predictand |
| None | no reduction; the predictor is used as is |

## Statistical models

OLS regression, Lasso regression, Ridge regression, MLP regression, decision trees and random forest.

## Forecast types

- **Deterministic** — a single forecast value.
- **Tercile probabilistic** — probabilities of below-normal, normal and above-normal conditions. The tercile forecast is also given as a 4-category forecast, in which the normal category is split into normal-to-below and normal-to-above. No probabilities are allocated to these two split categories.

## Cross-validation and skill

All forecasts are cross-validated with leave-one-out or k-fold cross-validation. Skill scores are calculated from the out-of-fold predictions:

| Score | What it measures |
|---|---|
| ROC score (below, normal, above) | how well forecast probabilities discriminate events of each category from non-events; 0.5 means no skill |
| RPSS | ranked probability skill score: accuracy of the tercile probabilities relative to climatology; above 0 means better than climatology |
| Correlation | correlation of the deterministic forecast with observations |
| Heidke skill score | how often the most likely category was observed, relative to chance |
| Ignorance score | information-based score of the probabilities; lower is better |
| Reliability score | how well forecast probabilities match observed frequencies |
| Brier skill score | accuracy of category probabilities relative to climatology |
| 2AFC | two-alternative forced choice: the probability that the forecast correctly tells apart two different observed outcomes; 0.5 means no skill |

## Calibration

Probabilistic forecasts are calibrated by quantile mapping. A quantile transform is fitted on the overlapping period of hindcast and observed predictand, and then applied to both the hindcast and the forecast.

## Using onset as a predictand

The [products module](products.md) writes onset files with a `time` dimension, named `..._summer_forforecast.nc` and `..._winter_forforecast.nc`, which can be used directly as a gridded predictand.

## Running without the graphical interface

See [Running CFT](../usage.md#forecast) for an example `config`, and the [API reference](../api.rst) for `computeModelNoGui`.
