# cft
Climate Forecasting Toolbox


INTRODUCTION
------------
The Climate Forecasting Toolbox is a Python based tool for statistical climate forecasting. 

CREDITS
=======
Piotr Wolski (wolski@csag.uct.ac.za)
Sunshine Gamedze (sgamedze@sadc.int)

Oringinal developer (2017-2022):
Thembani Moitlhobogi



Development history
=======
Current version is developed under funding from First Rains project.

Development in 2023-2025 has been funded under SADC CSC ClimSA project.

In November 2022, the software has been ported from the original personal github repo https://github.com/taxmanyana/cft to https://github.com/sadc-csc/cft

Original version developed during 2010-2017 under funding from SADC CSC project SARCIS-DR.


SOURCE CODE
------------
From version 6.0.0, the CFT code is available as pip package https://pypi.org/project/sadc-cft/
From version 4.0.0, the CFT code is maintained at:  https://github.com/sadc-csc


Basic functionality of v5 and later:
------------
Five modules:
data download (including from CDS from v6.0)
forecast (updated in v5)
zoning (since v3)
verification (since v4)
synthesis (since v4)

Download module
------------
Downloads following data types from sources:

1) gridded predictors from CDS:
- SST, GPH, rainfall, air temperature from all models (save UKMO one) available on CDS in July 2026.
2) gridded predictand from CDS:
- rainfall and temperatures from CDS ERA5 dataset
3) gridded predictors from IRIDL (legacy):
- SST
4) gridded predictand from IRIDL (legacy):
- CHIPRS precipitation
5) gridded forecast and hindcast data from IRIDL (legacy):
- SST, precipitation and geopotential height for three models from NMME that were operational in August 2025
6) teleconnection indices from JMA (because they have lowest latency)
- IOD, Nino3, Nino4

Data are downloaded to user-selected directory
All data are converted to a format ingestible by CFT


Forecast module
------------
Takes two types of data as predictand:
    - gridded data
    - station data

Takes three types of data as predictor:
    - observed teleconnection indices
    - observed gridded data (SST)
    - forecasted gridded fields (not yet implemented)

Produces forecast for:
    - grid - if predictand is gridded
    - zones - if predictand is either gridded or station data, with spatial aggregation of data into zonal average, and generation of forecast for that zonal average
    - points - if predictand is station data

Allows three pre-processing approaches:
    - PCR - gridded predictor is processed to derive Principal Components (aka EOFs), and these are used in a statistical model as predictors. This can be applied to gridded predictor, and any type of predictand.
    - CCA - canonical components are derived from predictor and predictand data
    - no preprocessing - this can be applied to gridded predictor and any type of predictand.
implements the following statistical models:
    - OLS regression
    - MLP regression
    - Decision trees
    - Random Forest
    - Lasso regression
    - Ridge regression

Two types of forecast are calculated:
    - deterministic forecast
    - tercile probabilistic forecast

Tercile forecast is also presented as a 4-category forecast, where normal category is split into normal-to-above and normal-to-below. No probabilities are allocated to these two categories. 

All forecasts are cross-validated. 

Two cross-validation approaches are possible:
    - leave-one-out
    - k-fold

Skill indices are calculated through cross-validation from out-of-fold predictions. The following skill indices are included:
    - ROC score (above, below, normal) 
    - RPSS
    - correlation
    - Heidke skill score for highest probability category
    - ignorance score 
    - reliability score
    - Brier skill score
    - 2AFC

Probabilistic forecast are calibrated using quantile mapping approach:
    -  quantile transform is developed based on overlapping hindcast and observed predictand data 
    - transform is applied to hindcast and forecast data



Other modules - zoning, verification, synthesis
------------

In v5.1 zoning module has been adapted to run under v5 environment.

Other packages were not updated in v5.0 , thus not described here explicitly


Requirements:
------------
python 3.12 
python packages:
    # scientific / data stack - used throughout functions_forecast.py
    "numpy",
    "pandas",
    "geopandas",
    "xarray",
    "rioxarray",
    "scipy",
    "shapely",
    "rasterio",
    "rasterstats",
    "scikit-learn",
    "statsmodels",
    "netCDF4",
    "cftime",
    "geojson",
    "descartes",
    "geocube",
    "GDAL",          # provides the 'osgeo' module (zoning.py's ogr usage)
    "requests",

    # plotting / mapping
    "matplotlib",
    "cartopy",

    # GUI
    "PyQt5",

    #CDS api
    "cdsapi",

Installation
------------

Python environment
=======

Installation should be done into a dedicated Python environment.

This requires installation of either:
    - Ancaconda framework (bulky, >1GB) https://www.anaconda.com/download/success
    - Miniforge (installs both Conda and Mamba) - https://github.com/conda-forge/miniforge
    - Micromamba (installs Mamba - lightweight, but for advanced users) https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html


Once installed, create a python enviroment e.g.

mamba create --name cft-env python=3.12

note - it is recommended that python 3.12 is used for version 6.0


Prerequisites
=======
The sadc-cft package is installed with pip, but pip does not handle GDAL libraries well. These have to be preinstalled using conda or mamba:

(one has to activate the cft environment first, of course)
mamba activate cft-env

(and then:)
mamba install -c conda-forge gdal=3.13.2

Installation with pip
=======
Once gdal is installed, sadc-cft package is installed using pip.

pip install sadc-cft


confirm that installation is complete:

python cft


How to use - GUI
------------

The main GUI of sadc-cft can be invoked as follows:

(one has to activate the cft environment first, of course)
mamba activate cft-env

(and then simply:)
cft

(or:)

python -m cft

Individual components (forecast, verification, synthesis, zoning and download) can be started directly as follows:

>forecast-tool

(or:)

python -m cft.forecast


How to use - without GUI
------------

individual packages can be invoked in Python without GUI. 

from cft.forecast import computeModelNoGui

and then run as follows:

computeModelNoGui(config)

where config is a dictionary containing forecast model configuration entries e.g. 

config={'rootDir': '../test',
 'predictorYear': 2026,
 'predictorMonth': 'Jun',
 'fcstTargetSeas': 'Aug-Oct',
 'fcstTargetYear': 2026,
 'climEndYr': 2015,
 'climStartYr': 1994,
 'predictorExtents': {'minLon': -180.0,
  'maxLon': 180.0,
  'minLat': -60.0,
  'maxLat': 60.0},
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
 'overlayFile': '../gis/sadc/gadm41_ZAF_1.json'
}

(more to follow...)

