# CFT — Climate Forecasting Toolbox

A Python-based tool for statistical climate forecasting, developed by the SADC Climate Services Centre (CSC).

[![PyPI](https://img.shields.io/pypi/v/sadc-cft)](https://pypi.org/project/sadc-cft/)
[![Read the Docs](https://img.shields.io/readthedocs/:sadc-cft)](https://sadc-cft.readthedocs.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Table of Contents

- [Introduction](#introduction)
- [Modules](#modules)
  - [Download](#download-module)
  - [Forecast](#forecast-module)
  - [Products (observed)](#products-observed-module)
  - [Zoning, Verification, Synthesis](#other-modules--zoning-verification-synthesis)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage — GUI](#usage--gui)
- [Usage — without GUI](#usage--without-gui)
- [Credits](#credits)
- [Development History](#developmentfunding-history)

## Introduction

CFT is a Python-based tool for statistical climate forecasting. From version 7, it consists of six modules:

| Module | Since | Description |
|---|---|---|
| **Download** | v6.0 (CDS support added) | Downloads predictor/predictand data from CDS, IRIDL, and JMA |
| **Forecast** | updated in v5 | Builds and cross-validates statistical seasonal forecast models |
| **Products (observed)** | v7.0 | Derives rainy season characteristics — onset, demise, duration and dry-to-wet transition statistics — from observed daily rainfall |
| **Zoning** | v3 | Spatial regionalization of station data into forecast zones |
| **Verification** | v4 | Forecast skill verification |
| **Synthesis** | v4 | Synthesis of forecast outputs |

## Modules

### Download module

Downloads the following data types:

1. **Gridded predictors from CDS** — SST, GPH, rainfall, and air temperature, from all models available on CDS as of July 2026 (except UKMO)
2. **Gridded predictand from CDS** — rainfall and temperature from the CDS ERA5 dataset
3. **Gridded predictors from IRIDL** *(legacy)* — SST
4. **Gridded predictand from IRIDL** *(legacy)* — CHIRPS precipitation
5. **Gridded forecast/hindcast data from IRIDL** *(legacy)* — SST, precipitation, and geopotential height, for three NMME models operational as of August 2025
6. **Teleconnection indices from JMA** *(chosen for lowest latency)* — IOD, Niño3, Niño4

Data are downloaded to a user-selected directory and converted to a format ingestible by the rest of CFT.

### Forecast module

**Predictand types:** gridded data, or station data

**Predictor types:**
- Observed teleconnection indices
- Observed gridded data (SST)
- Forecasted gridded fields *(not yet implemented)*

**Forecast output levels:**
- **Grid** — if the predictand is gridded
- **Zones** — if the predictand is gridded or station data; data are spatially aggregated into a zonal average and the forecast is generated for that average
- **Points** — if the predictand is station data

**Pre-processing approaches:**

| Approach | Description | Applicable to |
|---|---|---|
| **PCR** | Gridded predictor is reduced to Principal Components (EOFs), used as predictors in the statistical model | Gridded predictor, any predictand |
| **CCA** | Canonical components derived jointly from predictor and predictand | — |
| **None** | No dimensionality reduction | Gridded predictor, any predictand |

**Statistical models:** OLS regression, MLP regression, Decision Trees, Random Forest, Lasso regression, Ridge regression

**Forecast types:** deterministic, and tercile probabilistic. The tercile forecast is also presented as a 4-category forecast, splitting the normal category into normal-to-above and normal-to-below (no probabilities are allocated to these two split categories).

**Cross-validation:** all forecasts are cross-validated, using either leave-one-out or k-fold. Skill indices are calculated from out-of-fold predictions:

- ROC score (above / below / normal)
- RPSS
- Correlation
- Heidke skill score (highest-probability category)
- Ignorance score
- Reliability score
- Brier skill score
- 2AFC

**Calibration:** probabilistic forecasts are calibrated via quantile mapping — a quantile transform is developed from overlapping hindcast and observed predictand data, then applied to both hindcast and forecast.

### Products (observed) module

New in v7.0. Derives rainy season characteristics from observed **daily** rainfall, using three groups of methods:

| Group | Products | Approach |
|---|---|---|
| [**Agronomic onset**](#agronomic-onset) | Onset A, B, C, D | First day on which a rainfall threshold is reached, within a season defined per rainfall regime |
| [**Anomalous accumulation**](#onset-and-demise-from-anomalous-accumulation) | onset, demise, duration, wet and dry season rainfall | Turning points of cumulative rainfall anomalies, within a water year derived from the annual cycle |
| [**Dry-to-wet transition period (DWTP)**](#dry-to-wet-transition-period-dwtp) | DWTP statistics and climatological envelope | Transition from dry to wet conditions, within climatological envelopes; up to two rainy seasons per year |

#### Input data and common settings

- **Gridded data** — netCDF file with daily rainfall (time, lat, lon)
- **Station data** — CSV file with dates in the first column and one column per station; the top three rows hold station ID, latitude and longitude (`ID`, `Lat`, `Lon`), the same layout as station data in the forecast module

Grid cells and stations without any data are skipped. Values equal to the user-defined missing value code are treated as missing.

**Climatological period** — set by the user (start and end year); used to derive rainfall regimes, water years and climatological envelopes, and to calculate climatologies and anomalies. It must fall within the period covered by the data, and it may cover the entire data period.

**Seasons** are labelled with the year in which they start.

**Output** — gridded input produces netCDF files on the same grid as the input data. Station input produces one CSV file per output variable, with the same `ID`/`Lat`/`Lon` header rows as the input. Locations that were not processed have missing values.

**Parallel processing** — calculations can be run in parallel over locations, using a fraction of the available CPUs (`fractionCpus` in `DEFAULT_SETTINGS`, in `functions_products_obs.py`).

#### Agronomic onset

**Rainfall regime.** Onset is calculated separately for summer and winter rainfall locations. The regime of each location is either:
- **derived from the data** — a location is *summer rainfall* if at least ⅔ of its annual rainfall in the climatological period falls in October–March, *winter rainfall* if at least ⅔ falls in April–September, and *all-year rainfall* otherwise; or
- **read from a regime map** — a netCDF file coded 1 for summer and 2 for winter rainfall (any other value is treated as all-year rainfall).

Onset is not calculated for all-year rainfall locations. Negative rainfall values are treated as missing.

**Season definition.** For each regime, the user sets the month in which the season starts and the length of the onset search window. The start month should fall in the dry season, before any plausible onset. Onset is searched for from day 1 of that month until the end of the search window.

| Regime | Default season start | Default search window |
|---|---|---|
| Summer rainfall | 1 October | 123 days (to 31 January) |
| Winter rainfall | 1 March | 153 days (to 31 July) |

E.g. the summer season 2020 is the one starting on 1 October 2020.

**Onset definitions:**

| Product | Definition |
|---|---|
| **Onset A** | First day on which rainfall accumulated over 10 days reaches 25 mm (Tadross et al., 2007) |
| **Onset B** | As Onset A, but not followed by a dry spell of 10 or more consecutive days in the following 20 days |
| **Onset C** | First day on which rainfall accumulated over 4 days reaches 45 mm |
| **Onset D** | First day on which rainfall accumulated over 3 days reaches 20 mm, not followed by a dry spell of 10 consecutive days in the following 10 days |

Accumulations are trailing sums, and the onset day is the day on which the threshold is reached. A dry day is a day with less than 1 mm of rainfall.

**Outputs** (one file per selected onset definition, `<code>_<product>`):

| Variable | Dimensions | Description |
|---|---|---|
| `onsetDate` | season, location | date of onset |
| `onsetDoy` | season, location | day of the calendar year of onset (1–366) |
| `onsetDekad` | season, location | dekad of the calendar year of onset (1–36) |
| `onsetDaysSinceAnchor` | season, location | days from the season start to onset (0 = season start) |
| `onsetDekadsSinceAnchor` | season, location | dekads from the season start to onset |
| `onsetDoyClim`, `onsetDekadClim` | location | climatological onset — day of year and dekad |
| `onsetDoyAnom`, `onsetDekadAnom` | season, location | onset anomaly in days and in dekads; positive values mean later than normal |
| `anchorDate` | season, location | start date of the season |
| `regime` | location | rainfall regime: 1 — summer, 2 — winter |
| `anchorMonth` | location | season start month |

Seasons in which no onset is found within the search window have missing values, as do seasons with missing data.

The **climatology** is the mean onset over the climatological period, excluding seasons without onset. Climatology and anomalies are calculated on days counted from the season start, so they are not affected by the year end in summer rainfall seasons that span two calendar years.

#### Onset and demise from anomalous accumulation

Onset and demise are the turning points of the cumulative daily rainfall anomaly (Liebmann and Marengo, 2001), within a water year derived from harmonic analysis of the annual cycle (Dunning et al., 2016).

- **Water year** — for each location, the mean annual cycle of daily rainfall in the climatological period (29 February excluded) is decomposed into harmonics. If the annual harmonic explains more variance than the semi-annual and the third harmonic, the location has a single rainy season, and its water year starts at the minimum of the annual harmonic (`w0`). Locations without a single rainy season are not processed.
- **Anomaly** — daily rainfall minus the mean daily rainfall of the climatological period (`rm`).
- **Onset** — minimum of the smoothed cumulative anomaly, accumulated forward over the first 182 days of the water year.
- **Demise** — minimum of the smoothed cumulative anomaly, accumulated backward over the last 182 days of the water year.
- **Smoothing** — zero-phase Butterworth low-pass filter (order 2, filter parameter 18; removes variations shorter than about 36 days).

In seasons in which rainfall stays below the long-term mean throughout the onset search period, the minimum — and therefore the onset — falls on the last day of that period.

Each water year is labelled with the year in which it starts. Only complete water years are processed.

**Outputs** (`<code>_onsetAccum`):

| Variable | Dimensions | Description |
|---|---|---|
| `onsetDate`, `demiseDate` | season, location | date of onset and demise |
| `onsetDoy`, `demiseDoy` | season, location | day of the calendar year (1–366) |
| `onsetDekad`, `demiseDekad` | season, location | dekad of the calendar year (1–36) |
| `onsetDaysSinceAnchor`, `demiseDaysSinceAnchor` | season, location | days from the start of the water year |
| `onsetDoyClim`, `onsetDekadClim`, `demiseDoyClim`, `demiseDekadClim` | location | climatology — day of year and dekad |
| `onsetDoyAnom`, `onsetDekadAnom`, `demiseDoyAnom`, `demiseDekadAnom` | season, location | anomaly in days and in dekads; positive values mean later than normal |
| `duration` | season, location | days from onset to demise |
| `wetTotal` | season, location | rainfall from onset to demise (mm) |
| `dryTotal` | season, location | rainfall from the day after the previous season's demise to the day before onset (mm); missing in the first season |
| `durationClim`, `wetTotalClim`, `dryTotalClim` | location | climatological means |
| `durationAnom`, `wetTotalAnom`, `dryTotalAnom` | season, location | anomalies |
| `anchorDate` | season, location | start date of the water year |
| `w0` | location | start of the water year, day of year (no-leap calendar) |
| `anchorMonth`, `anchorDay` | location | start of the water year as month and day |
| `rm` | location | mean daily rainfall in the climatological period (mm/day) |

Climatologies are means over the climatological period. As for agronomic onset, onset and demise climatologies and anomalies are calculated on days counted from the start of the water year.

Method settings (`DEFAULT_SETTINGS`): `accumWindowDays` (365), `accumOnsetDays` (182), `accumDemiseDays` (182), `accumCutoff` (18).

#### Dry-to-wet transition period (DWTP)

The DWTP is the period in which a location transitions from dry to wet conditions. The method can identify up to two rainy seasons per year, so it can be applied in regions with a bimodal rainfall regime.

- **Transition days** — daily rainfall is smoothed with a Butterworth low-pass filter (filter parameter 60; removes variations shorter than about 120 days). Days on which smoothed rainfall is positive and increasing are transition days; sequences of at least 30 such days are transition periods.
- **Climatological envelope** — for each day of the year, the frequency of transition periods in the climatological period is calculated. The start of the water year (`w0`) is the day with the lowest frequency; envelopes are the parts of the year in which the (normalised, smoothed) frequency is at least 0.5. Up to two envelopes are kept; a second envelope is dropped if its mean smoothed rainfall is less than 35% of that of the first.
- **DWTP in each year** — within each envelope: the end of the DWTP is the day on which 50% of the rainfall in the envelope has fallen (moved later past long dry breaks); the start of the DWTP is the end of the longest dry break early in the envelope.
- **Statistics** — rainfall and wet and dry spell statistics for each DWTP.

The implementation reproduces the reference code of the method; known inconsistencies of that code are kept, and marked in the source (`kernels_dwtp.py`). Data should start on 1 January and should have no missing days — locations with missing data are not processed. 29 February is excluded from all calculations.

**Outputs:**

`<code>_onsetDWTP_Stats` — DWTP statistics; dimensions years, sea (season: 0, 1), location:

| Variable | Units | Description |
|---|---|---|
| `FirstDay` | day of year | first day of the DWTP (see note below) |
| `Length` | days | duration of the DWTP |
| `OnsIntensity` | mm/day per day | mean gradient of the filtered rainfall during the DWTP |
| `TotPrecip` | mm | total rainfall during the DWTP |
| `PrecipRate` | mm/day | rainfall rate during the DWTP |
| `PrecipInt` | mm/wet day | rainfall per wet day |
| `FrcWetDays`, `FrcDryDays` | % | fraction of wet and dry days |
| `LengthWetSpells`, `LengthDrySpells` | days | mean duration of wet and dry spells |
| `MaxWetSpell`, `MaxDrySpell` | days | longest wet and dry spell |

`<code>_onsetDWTP_ClmEnvelope` — climatological envelope:

| Variable | Dimensions | Description |
|---|---|---|
| `clmEnv` | season, Stats (FirstDay, Length), location | first day of year and length of each climatological envelope |
| `w0` | location | start of the water year, day of year |
| `status` | location | 0 — ok; 1 — no transition periods found; 2 — not processed (e.g. missing data); 3 — ok, with a warning from the envelope detection |

`<code>_onsetDWTP_PR60` — filtered daily rainfall (`bwpp`); written only if selected in the GUI (`dwtpSaveFiltered` in the configuration), as the file is as large as the input data.

Notes, as in the reference code: `FirstDay` is counted from 0 in most years and from 1 in the first year, and can exceed 365 when the envelope starts in the next calendar year; each DWTP is assigned to the calendar year in which its envelope starts; when only one climatological envelope is found, both rows of `clmEnv` hold that envelope. Wet days are days with rainfall above 0 mm, dry days with 0 mm.

Method settings (`DEFAULT_SETTINGS`): `dwtpFilterWindow` (60), `dwtpMinLength` (30), `dwtpMaxSeasons` (2).

### Other modules — Zoning, Verification, Synthesis

The zoning module was adapted to run under the v5 environment in v5.1.

> **Note:** the verification and synthesis modules have not yet been updated to the same extent as the modules above, and aren't documented in detail here yet. *(more to follow)*

## Requirements

- Python 3.12 (recommended for v6.0)
- All Python package dependencies are installed automatically via pip — see [`pyproject.toml`](pyproject.toml) for the full list. Notably: `numpy`, `pandas`, `geopandas`, `xarray`, `rioxarray`, `scipy`, `shapely`, `rasterio`, `rasterstats`, `scikit-learn`, `joblib`, `netCDF4`, `cftime`, `geocube`, `GDAL`, `matplotlib`, `cartopy`, `PyQt5`, `cdsapi`.

## Installation

### 1. Set up a Python environment

Installation should be done into a dedicated Python environment. You'll need one of:

- [Anaconda](https://www.anaconda.com/download/success) (full framework, >1GB)
- [Miniforge](https://github.com/conda-forge/miniforge) (installs both Conda and Mamba)
- [Micromamba](https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html) (lightweight; for advanced users)

Once installed, create a dedicated environment:

```bash
mamba create --name cft-env python=3.12
```

### 2. Install GDAL first, separately

`pip` does not reliably handle the GDAL system library, so it must be pre-installed via conda/mamba **before** installing the `sadc-cft` package itself:

```bash
mamba activate cft-env
mamba install -c conda-forge gdal=3.13.2
```

### 3. Install CFT with pip

```bash
pip install sadc-cft
```

### 4. Confirm the installation

```bash
python -m cft
```

This should launch the main CFT GUI.

## Usage — GUI

Activate the environment first, as always:

```bash
mamba activate cft-env
```

**Launch the main GUI:**
```bash
cft
```
or equivalently:
```bash
python -m cft
```

**Launch an individual module directly** (forecast, verification, synthesis, zoning, download, products):
```bash
forecast-tool
```
or equivalently:
```bash
python -m cft.forecast
```
(substitute `download-tool` / `verification-tool` / `synthesis-tool` / `zoning-tool`, or `cft.download` / `cft.verification` / `cft.synthesis` / `cft.zoning` / `cft.products_obs`, as needed)

## Usage — without GUI

Individual components can be called directly from Python, without launching any GUI.

### Forecast

```python
from cft.functions.functions_forecast import computeModelNoGui

computeModelNoGui(config)
```

where `config` is a dictionary of forecast model settings, for example:

```python
config = {
    'rootDir': '../test',
    'predictorYear': 2026,
    'predictorMonth': 'Jun',
    'fcstTargetSeas': 'Aug-Oct',
    'fcstTargetYear': 2026,
    'climEndYr': 2015,
    'climStartYr': 1994,
    'predictorExtents': {
        'minLon': -180.0,
        'maxLon': 180.0,
        'minLat': -60.0,
        'maxLat': 60.0,
    },
    'predictorFileName': '/work/code/csc/cft/test/GPH850_System9_CDS_Jun_s300s200e150e250_1981-2026.nc',
    'predictorVar': 'z',
    'predictorCode': 'z',
    'crossval': 'KF',
    'preproc': 'PCR',
    'regression': 'OLS',
    'timeAggregation': 'mean',
    'predictandFileName': '../test/PRCP_CHIRPSp25_IRIDL_Aug-Oct_s340s200e150e250_1981-2025.nc',
    'predictandVar': 'prcp',
    'predictandCategory': 'temperature',
    'predictandMissingValue': '-999',
    'zonesFile': None,
    'zonesAttribute': 'Name',
    'zonesAggregate': False,
    'regridPredictand': False,
    'overlayFile': '../gis/sadc/gadm41_ZAF_1.json',
}
```

### Products (observed)

```python
from cft.functions.functions_products_obs import computeProductsObsNoGui

computeProductsObsNoGui(config)
```

where `config` is a dictionary of settings, for example:

```python
config = {
    'outDir': '../output',
    'obsFile': '../test/PRCP_CHIRPS_daily_1981-2025.nc',  # .nc (grid) or .csv (stations)
    'obsVar': 'prcp',                                     # ignored for csv
    'obsMissingValue': '',                                # e.g. '-999', '' if none
    'obsDsetCode': 'chirps',                              # used in output file names
    'climStartYr': 1991,
    'climEndYr': 2020,
    # agronomic onset
    'regimeFile': '',                                     # '' - derive regime from data
    'onsetAnchorMonth': {'summer': 10, 'winter': 3},      # season start month
    'onsetWindowDays': {'summer': 123, 'winter': 153},    # onset search window, days
    # DWTP
    'dwtpSaveFiltered': False,                            # save filtered daily rainfall
    'parallelize': True,
    'products': {'onsetA': True, 'onsetB': True, 'onsetC': False, 'onsetD': False,
                 'onsetAccum': True, 'onsetDWTP': True},
}
```

The same settings, saved by the GUI to a json file, can be used from the command line:

```bash
python -m cft.functions.functions_products_obs products.json
```


## Credits

- **Piotr Wolski** (wolski@csag.uct.ac.za)
- **Sunshine Gamedze** (sgamedze@sadc.int)


**Original developer (2017–2022):** Thembani Moitlhobogi

## Development/funding History

- **2010–2017:** original version developed under funding from the SADC CSC project SARCIS-DR.
- **November 2022:** code ported from the original personal repo ([taxmanyana/cft](https://github.com/taxmanyana/cft)) to the institutional repo, [sadc-csc/cft](https://github.com/sadc-csc).
- **2023–2025:** development funded under the SADC CSC ClimSA project.
- **Versions after 6.0** developed under funding from the First Rains project.


**Source code:** maintained at [github.com/sadc-csc](https://github.com/sadc-csc) since v4.0.0. From v6.0.0, also available as a pip package: [pypi.org/project/sadc-cft](https://pypi.org/project/sadc-cft/).
