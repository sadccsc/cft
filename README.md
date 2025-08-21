# cft
Climate Forecasting Toolbox


INTRODUCTION
------------
The Climate Forecasting Toolbox is a Python based tool for statistical climate forecasting. 

CREDITS
=======
Oringinal developers (2017-2022):
Programmer: Thembani Moitlhobogi
Climatologist: Mduduzi Sunshine Gamedze

Contributor (after Nov 2022):
Piotr Wolski (wolski@csag.uct.ac.za)


Development history
=======
This software has been developed during 2017-2010 under funding from SADC CSC project SARCIS-DR

In November 2022, the software has been ported from the original personal github repo https://github.com/taxmanyana/cft
to this "institutional" repo.

Development since 2023 has been funded under ClimSA project


SOURCE CODE
------------
From version 4.0.0, the CFT code is maintained at:  https://github.com/sadc-csc/cft.git
prior to that - it was maintained at https://github.com/taxmanyana/cft


Basic functionality of v5.0:
------------
Five modules:
data download (new in v.5)
forecast (new in v.5)
zoning (from v.3)
verification (from v.4)
synthesis (from v.4)

Download module
------------
downloads following data types from sources:
1) teleconnection indices from JMA (because they have lowest latency) 
- IOD, Nino3, Nino4
2) gridded predictors from IRI:
- SST
3) gridded predictand from IRI:
- CHIPRS precipitation
4) gridded forecast and hindcast data
- SST, precipitation and geopotential height for three models from NMME that are currently (August 2025) operational

Data are downloaded to user-selected directory
All data are converted to a format ingestible by CFT
Note that geopotential height data availability varies between models, some offer only z200, some other levels. In the latter, z500 is set to be downloaded.


Forecast module
------------
takes two types of data as predictand:
- gridded data
- station data

takes three types of data as predictor:
    - observed teleconnection indices
    - observed gridded data (SST)
    - forecasted gridded fields (not yet implemented)

produces forecast for:
    - grid - if predictand is gridded
    - zones - if predictand is either gridded or station data, with spatial aggregation of data into zonal average, and generation of forecast for that zonal average
    - points - if predictand is station data

allows three pre-processing approaches:
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
all forecasts are cross-validated. 

Two cross-validation approaches are possible:
    - leave-one-out
    - k-fold

Skill indices are calculated through cross-validation from out-of-fold predictions. The following skill indices are included:
    - ROC score (above, below, normal) 
    - RPSS
    - correlation

Not yet implemented skill scores:
    - Heidke skill score for highest probability category
    - ignorance score 
    - reliability diagram 
    - plotting of ROC curve
    - reliability score
    - Brier skill score
    - 2AFC


Other modules - zoning, verification, synthesis
------------
Not updated in v5.0 , thus not described here explicitly


Requirements:
------------
python 3.10 or higher installed with conda package manager
python packages:
numpy
pandas
geojson
xarray with netcdf libraries
rioxarray
geopandas
scikit-learn
rasterstats
matplotlib
cartopy
pyqt
scipy
cftime
dask

Installation
------------
1. Install Anaconda  (instructions t.b.d.)
2. Download and unzip CFT release files
3. Open terminal (in Linux or Mac) or Anaconda Prompt (windows), navigate to the directory in which you unzipped CFT files (using cd Dir commands - instructions to follow) and type:
install_win.bat (on Windows)
install_mac.sh (on Mac)
install_linux.sh ( on Linux)


Starting
------------
on Windows:
- you should see cft.lnk on your Desktop. Double click on it.

alternatively:
- open Anaconda Prompt
- navigate to your CFT directory (using cd commands)
- type:
      cft.bat
alternatively:
- open Anaconda Prompt
- navigate to your CFT directory (using cd commands)
- type:
   mamba activate cft-v5.0
   python cft.py



on Mac/Linux:
- open terminal
- navigate to your CFT directory (using cd commands)
- type: 
    ./cft.sh

alternatively:
- open terminal
- navigate to your CFT directory (using cd commands)
- type: 
   mamba activate cft-v5.0
   python cft.py



Still to do in v5.0
------------
in download.py:
- implement control of lat lon to make sure integers within range

in forecast.py
- extend and clean up plotting 
- include skill-masked plots
- catch error when some zones get dropped if spatial aggregation is used
- include more skill measures
- data saving - diagnostics - results of pca and cca
- test data ingestion errors for csv files
- add missing value to gui
- add category of predictand to gui
- add buttons to clear file selectors to gui
- add "too dry to forecast" colour to plots
- implement ability to use forecast data as predictor - it should work even now, but there is a need to make sure dates are handled correctly.

wish list:
------------
- multimodel forecast
- filling missing values in predictand
- regridding of gridded predictand to a coarser resolution if domain too large
- optimize skill calculation on gridded data - it takes much longer than calculations of the model
- parameters that are not defined throug gui to be read from json file (in this way, advanced users can change them)

