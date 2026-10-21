# Forecast

The forecast module builds statistical seasonal forecast models, cross-validates them, and produces deterministic and probabilistic forecasts with skill scores.

## Forecast timing

Four settings in the **Forecast timing** box decide which data CFT uses. They are the ones users most often find confusing.

| Setting | Meaning |
|---|---|
| **Target season** | the month or 3-month season being forecast, e.g. `Aug-Oct` or `Oct` |
| **Target year** | the year of the **first** month of the target season. `Dec-Feb` with target year 2026 is December 2026 to February 2027 |
| **Predictor/forecast month** | the month in which the forecast is made (issued) |
| **Predictor/forecast year** | the year in which the forecast is made |

The predictor/forecast month is the month the forecast is *made*, not necessarily the month of the predictor data. Which data CFT then takes depends on the type of predictor:

| Predictor type | Data CFT uses for a forecast made in July |
|---|---|
| Observed gridded field (netCDF without a lead-time dimension), e.g. SST | **June**: the last complete month of observations before the forecast is made |
| Forecast gridded field (netCDF with a lead-time dimension), e.g. a CDS seasonal forecast | the forecast **initialised in July**, averaged over the months of the target season |
| Observed teleconnection index (CSV file) | **June**, as for observed gridded fields |

CFT selects these months itself, in every year of the hindcast as well as in the forecast year. You do not need to cut the files to a single month.

### Example

A forecast for August–October 2026, made in July 2026:

| Setting | Value |
|---|---|
| Target season | `Aug-Oct` |
| Target year | 2026 |
| Predictor/forecast month | `Jul` |
| Predictor/forecast year | 2026 |

- With an **observed** predictor, gridded (e.g. SST) or an index, CFT relates June values to the following August–October predictand in every year, and uses the June 2026 values for the forecast.
- With a **forecast** predictor, the file must hold forecasts initialised in July, the month the file starts with. CFT averages the forecast values for August, September and October.
- The **predictand** must have monthly values for August, September and October, which CFT adds up or averages (see *Time aggregation* below).

### Around the turn of the year

- **Seasons that span two years:** the target year is the year the season starts. For December 2026 to February 2027, set `Dec-Feb` and 2026.
- **Forecasts made in January:** the predictor year is the year the forecast is made. For a forecast made in January 2027, set `Jan` and 2027. With an observed predictor, CFT uses December 2026.

### Lead time

CFT counts the lead time in months from the forecast month (month 1) to the last month of the target season. A July forecast for August–October has a lead time of 4 months: July, August, September, October. The lead time must not exceed the maximum set in CFT's configuration (`maxLeadTime`).

Forecast files number their lead months the same way: lead month 1 is the initialisation month (`forecastMonth` 1 in CDS files). For a July forecast of August–October, CFT averages lead months 2, 3 and 4. If the file does not contain all the lead months the target season needs, CFT stops with an error naming the missing months. CDS seasonal forecasts cover 6 lead months, so the target season can end at most 5 months after the forecast month.

### Overlap with the predictand

The predictor and predictand must overlap in at least 20 years after this alignment, and both must cover the climatological period.

### Time aggregation

**Time aggregation** in the Predictand box sets how monthly predictand values are combined into the target season: `sum` for totals such as rainfall, `mean` for averages such as temperature. For a single-month target season no aggregation is done. A predictand file that already holds seasonal values is also accepted if each season is stored under its middle month.

### Onset as a predictand

For onset files from the products module, set the target season to the single anchor month (e.g. `Oct`), the target year to the year of the season, and a predictor/forecast month before it, e.g. `Sep`. See [Using onset as a predictand](#using-onset-as-a-predictand).

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

All forecasts are cross-validated with leave-one-out or k-fold cross-validation: each year's forecast is made by a model fitted without that year (leave-one-out) or without the group of years it belongs to (k-fold). Skill scores are calculated from these out-of-fold predictions, so they show how the model performs on years it has not seen.

Most scores compare the forecast with a reference forecast, usually climatology: equal probabilities of ⅓ for each tercile category.

| Score | What it measures | Range | No skill | Perfect |
|---|---|---|---|---|
| Correlation | strength of the linear relationship between the deterministic forecast and observations | −1 to 1 | 0 | 1 |
| ROC score (below, normal, above) | area under the ROC curve: how well the forecast probabilities separate years in which a category occurred from years in which it did not; calculated for each category | 0 to 1 | 0.5 | 1 |
| 2AFC | two-alternative forced choice: the probability that, given two years with different observed outcomes, the forecast correctly tells which is which | 0 to 1 | 0.5 | 1 |
| Heidke skill score | proportion of years in which the category with the highest forecast probability was observed, relative to the proportion expected by chance | −∞ to 1 | 0 | 1 |
| RPSS | ranked probability skill score: error of the cumulative tercile probabilities, relative to climatology; it penalises probability placed far from the observed category more than probability placed next to it | −∞ to 1 | 0 | 1 |
| Brier skill score | squared error of the probability of one category, relative to climatology | −∞ to 1 | 0 | 1 |
| Ignorance score | how surprising the observed category was, given the forecast probabilities: the negative logarithm (base 2) of the probability given to the observed category; lower is better | 0 to ∞ | log₂3 ≈ 1.58 for climatology | 0 |
| Reliability score | how well forecast probabilities match observed frequencies: in a reliable forecast, events forecast with 60% probability happen in about 60% of cases | 0 to 1 | | 0 |

Correlation, ROC and 2AFC measure **discrimination**, whether the forecast can tell different outcomes apart. RPSS, Brier and ignorance scores also depend on how well calibrated the probabilities are. With the 30 to 40 years typical of a hindcast, all scores have large sampling uncertainty, so small positive values should be treated with caution.

Further reading:

- [Forecast verification: issues, methods and FAQ](https://cawcr.gov.au/projects/verification/verif.html), WWRP/WGNE Joint Working Group on Forecast Verification Research — short definitions of most of these scores, with formulas.
- [WWRP/WGNE Joint Working Group on Forecast Verification Research](https://wmo.int/node/37326), WMO.
- Mason, S. J. and Weigel, A. P. (2009). A generic forecast verification framework for administrative purposes. *Monthly Weather Review*, 137, 331–349 — the 2AFC score.

## Calibration

Probabilistic forecasts are calibrated by quantile mapping. A quantile transform is fitted on the overlapping period of hindcast and observed predictand, and then applied to both the hindcast and the forecast.

## Using onset as a predictand

The [products module](products.md) writes onset files with a `time` dimension, named `..._summer_forforecast.nc` and `..._winter_forforecast.nc`, which can be used directly as a gridded predictand. They hold the number of days from the season start to onset.

The time of each season in these files is its anchor date, the season start. Set the forecast target season to that anchor month: `Oct` for the default summer file and `Mar` for the default winter file. See [Files for forecasting](products.md#files-for-forecasting).

## Running without the graphical interface

See [Running CFT](../usage.md#forecast) for an example `config`, and the [API reference](../api.rst) for `computeModelNoGui`.
