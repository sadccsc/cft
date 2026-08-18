# CFT — Climate Forecasting Toolbox

A Python-based tool for statistical climate forecasting, developed by the SADC Climate Services Centre (CSC).

[![PyPI](https://img.shields.io/pypi/v/sadc-cft)](https://pypi.org/project/sadc-cft/)
[![Readthedocs](https://img.shields.io/readthedocs/:sadc-cft)](https://sadc-cft.readthedocs.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Table of Contents

- [Introduction](#introduction)
- [Modules](#modules)
  - [Download](#download-module)
  - [Forecast](#forecast-module)
  - [Zoning, Verification, Synthesis](#other-modules--zoning-verification-synthesis)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage — GUI](#usage--gui)
- [Usage — without GUI](#usage--without-gui)
- [Credits](#credits)
- [Development History](#development-history)

## Introduction

CFT is a Python-based tool for statistical climate forecasting. From version 5, it consists of five modules:

| Module | Since | Description |
|---|---|---|
| **Download** | v6.0 (CDS support added) | Downloads predictor/predictand data from CDS, IRIDL, and JMA |
| **Forecast** | updated in v5 | Builds and cross-validates statistical seasonal forecast models |
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

### Other modules — Zoning, Verification, Synthesis

The zoning module was adapted to run under the v5 environment in v5.1.

> **Note:** the verification and synthesis modules have not yet been updated to the same extent as the modules above, and aren't documented in detail here yet. *(more to follow)*

## Requirements

- Python 3.12 (recommended for v6.0)
- All Python package dependencies are installed automatically via pip — see [`pyproject.toml`](pyproject.toml) for the full list. Notably: `numpy`, `pandas`, `geopandas`, `xarray`, `rioxarray`, `scipy`, `shapely`, `rasterio`, `rasterstats`, `scikit-learn`, `netCDF4`, `cftime`, `geocube`, `GDAL`, `matplotlib`, `cartopy`, `PyQt5`, `cdsapi`.

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

**Launch an individual module directly** (forecast, verification, synthesis, zoning, download):
```bash
forecast-tool
```
or equivalently:
```bash
python -m cft.forecast
```
(substitute `download-tool` / `verification-tool` / `synthesis-tool` / `zoning-tool`, or `cft.download` / `cft.verification` / `cft.synthesis` / `cft.zoning`, as needed)

## Usage — without GUI

Individual components can be called directly from Python, without launching any GUI:

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

*(more to follow...)*

## Credits

- **Piotr Wolski** (wolski@csag.uct.ac.za)
- **Sunshine Gamedze** (sgamedze@sadc.int)


**Original developer (2017–2022):** Thembani Moitlhobogi

## Development History

- **2010–2017:** original version developed under funding from the SADC CSC project SARCIS-DR.
- **2023–2025:** development funded under the SADC CSC ClimSA project.
- **November 2022:** code ported from the original personal repo ([taxmanyana/cft](https://github.com/taxmanyana/cft)) to the institutional repo, [sadc-csc/cft](https://github.com/sadc-csc).
- **Current version:** developed under funding from the First Rains project.

**Source code:** maintained at [github.com/sadc-csc](https://github.com/sadc-csc) since v4.0.0. From v6.0.0, also available as a pip package: [pypi.org/project/sadc-cft](https://pypi.org/project/sadc-cft/).
