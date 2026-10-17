"""
Products module - calculations. Independent of the GUI.

API:
    computeProductsObsNoGui(config)

    config = {
        "outDir": "../output",
        "obsFile": "pr_daily.nc",     # .nc (grid) or .csv (stations)
        "obsVar": "pr",               # ignored for csv
        "obsMissingValue": "",        # e.g. "-999", "" if none
        "obsDsetCode": "chirps",      # used in output file names
        "climStartYr": 1991,
        "climEndYr": 2020,
        "regimeFile": "",             # "" - derive regime from data, otherwise netcdf map
        "parallelize": True,
        "products": {"onsetA": True, "onsetB": False, "onsetC": False, "onsetD": False},
    }

    or from command line:  python -m cft.functions.functions_products config.json

Structure:
    CATEGORIES  - {category: {product key: kernel}}. Kernels in one category share one signature.
    preprocess  - category-specific preparation of inputs (once per category)
    calculate   - category-specific calculation of one product
    postprocess - category-specific conversion of the result

Adding a product to an existing category:
    1. write the kernel (e.g. in products_onset.py)
    2. add it to CATEGORIES
    3. add a checkbox to products.ui with objectName equal to the product key

Adding a category: add pre/calc/post functions and an "if" branch in each dispatcher.
"""

import sys, time
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from cft import gl
from cft.functions.functions_common import (showMessage, readConfigFile, getNJobs, runParallel,
                                            readObs, toDaily, coordsubs)
from cft.functions import products_onset


# registry ##########################################################################

CATEGORIES = {
    "agronomic_onset": {
        "onsetA": products_onset.onsetA,
        "onsetB": products_onset.onsetB,
        "onsetC": products_onset.onsetC,
        "onsetD": products_onset.onsetD,
    },
}


# settings that users should not normally change. Values in dictionaries/deep_config.json override these.
DEFAULT_SETTINGS = {
    "fractionCpus": 0.5,
    "onsetAnchorMonth": {"summer": 10, "winter": 3},   # first month of the season (dry season)
    "onsetRegimeThreshold": 0.667,                    # share of annual rainfall in Oct-Mar (summer) or Apr-Sep (winter)
    "onsetWindowDays": {"summer": 123, "winter": 153},   # 1 Oct-31 Jan, 1 Mar-31 Jul
}

REGIMES = {"allyear": 0, "summer": 1, "winter": 2}


def loadSettings():
    """simply reads config from dictionary embedded in the code"""
    settings = dict(DEFAULT_SETTINGS)
    return settings


# dispatchers #######################################################################

def preprocess(category, data, config, settings):
    if category == "agronomic_onset":
        return preAgroOnset(data, config, settings)


def calculate(category, inputs, func, n_jobs, settings):
    if category == "agronomic_onset":
        return calcAgroOnset(inputs, func, n_jobs, settings)


def postprocess(category, result, settings):
    if category == "agronomic_onset":
        return postAgroOnset(result, gl.config)


def writeoutput(category, result, meta, outDir, obsdatasetcode, productname):
    if category == "agronomic_onset":
        writeAgroOnsetOutput(result, meta, outDir / "{}_{}".format(obsdatasetcode, productname))

    
# onset #############################################################################

def preAgroOnset(data, config, settings):
    """
    Preprocessing of data for calculation of agronomic onset
    Returns {"data": daily data for seasonal locations only with regime and anchorMonth coordinates}
    or None.
    """

    #checking if daily
    data = toDaily(data)
    if data is None:
        showMessage("Onset requires daily data", "ERROR")
        return None

    #replacing negative values with NaNs
    data = data.where(data >= 0)

    #deriving regime - summer, winter, all year. The last one will not be processed
    if config.get("regimeFile", "") == "":
        regime = regimeFromData(data, config, settings)
    else:
        regime = regimeFromMap(data, config["regimeFile"])
    if regime is None:
        return None

    for name, code in REGIMES.items():
        showMessage("\t{} rainfall regime: {} locations".format(name, int((regime == code).sum())))

    #regime as a coordinate along location (attrs keep the flag meanings)
    data = data.assign_coords(regime=("location", regime.values, regime.attrs))

    #seasonal is locations for which calculations will happen
    seasonal = (data.regime > 0).values
    if not seasonal.any():
        showMessage("No locations with seasonal rainfall regime - onset cannot be calculated", "ERROR")
        return None

    #selecting only locations that are seasonal
    data = data.isel(location=seasonal)

    #start month for each location
    anchors = {REGIMES[k]: v for k, v in settings["onsetAnchorMonth"].items()}
    data = data.assign_coords(anchorMonth=("location", [anchors[int(r)] for r in data.regime.values]))

    return {"data": data}

def regimeFromData(data, config, settings):
    clim = data.sel(time=slice(str(config["climStartYr"]), str(config["climEndYr"])))
    #total rainfall
    total = clim.sum("time")
    
    #fraction of total during summer months
    summer = clim.where(clim.time.dt.month.isin([10, 11, 12, 1, 2, 3])).sum("time") / total
    
    #fraction of total during winter months
    winter = clim.where(clim.time.dt.month.isin([4, 5, 6, 7, 8, 9])).sum("time") / total

    #threshold for defining regimes
    thresh = settings["onsetRegimeThreshold"]

    #calculating regime
    regime = xr.where(summer >= thresh, REGIMES["summer"],
                      xr.where(winter >= thresh, REGIMES["winter"], REGIMES["allyear"]))
    
    return setRegimeAttrs(regime)


def regimeFromMap(data, file):
    # map: netcdf with one variable coded 1 - summer, 2 - winter, anything else - all year
    try:
        ds = xr.open_dataset(file)
        for key, alternatives in coordsubs.items():
            for x in alternatives:
                if x in ds.coords and key not in ds.coords:
                    ds = ds.rename({x: key})
        regmap = ds[list(ds.data_vars)[0]]
        regime = regmap.sel(lat=data.lat, lon=data.lon, method="nearest").drop_vars(["lat", "lon"])
    except Exception as e:
        showMessage("Could not read regime map {}. Full error: {}".format(file, e), "ERROR")
        return None
    regime = xr.where(regime.isin([REGIMES["summer"], REGIMES["winter"]]), regime, REGIMES["allyear"])
    regime = regime.assign_coords(lat=data.lat, lon=data.lon)
    
    #setting attributes
    regime.name = "regime"
    regime.attrs = {"flag_values": "0 1 2", "flag_meanings": "all_year summer winter"}

    #converting to integer
    regime=regime.astype(int)

    
    return regime


def setRegimeAttrs(regime):
    return regime


def calcAgroOnset(inputs, func, n_jobs, settings):
    windowDays = {settings["onsetAnchorMonth"][r]: settings["onsetWindowDays"][r]
                  for r in settings["onsetAnchorMonth"]}
    return runParallel(applyAgroOnsetKernel, inputs["data"], n_jobs,
                       kernel=func, windowDays=windowDays)


def applyAgroOnsetKernel(data, kernel, windowDays):
    # runs on one chunk of locations; returns offsets from the anchor date, dims (season, location)
    results = []
    for month in np.unique(data.anchorMonth.values):
        sub = data.isel(location=(data.anchorMonth.values == month))
        
        windows = seasonWindows(sub, int(month), windowDays[int(month)])
        results.append(xr.apply_ufunc(kernel, windows,
                                      input_core_dims=[["day"]],
                                      vectorize=True,
                                      output_dtypes=[float]))
    # summer and winter locations may have different seasons available; missing ones become NaN
    return xr.concat(results, dim="location", join="outer")


def seasonWindows(data, month, windowDays):
    # cuts daily data (time, location) into windows (season, day, location) starting on day 1 of month
    # season is labelled with the year of its first day. Only complete windows are kept.
    times = pd.DatetimeIndex(data.time.values)
    starts = [pd.Timestamp(y, month, 1) for y in range(times[0].year, times[-1].year + 1)]
    starts = [s for s in starts if s >= times[0] and s + pd.Timedelta(days=windowDays - 1) <= times[-1]]
    positions = np.array([(s - times[0]).days for s in starts], dtype=int)
    index = positions[:, None] + np.arange(windowDays)[None, :]

    coords = {k: v for k, v in data.coords.items() if v.dims == ("location",)}
    coords["season"] = [s.year for s in starts]
    return xr.DataArray(data.values[index], dims=("season", "day", "location"), coords=coords)




def anchorDates(years, months):
    """
    years:  1-D array, year of the anchor date for each season
    months: 1-D array, anchor month for each location
    returns flat DatetimeIndex (season*location) of anchor dates - day 1 of the anchor month
    """
    Y, M = np.broadcast_arrays(np.asarray(years)[:, None], np.asarray(months)[None, :])
    return pd.DatetimeIndex(pd.to_datetime(pd.DataFrame({"year": Y.ravel(), "month": M.ravel(), "day": 1})))
 
 
def offsetToDates(offset, years, months):
    """
    offset: 2-D array (season, location), days from anchor date; values < 0 (-99) and NaN give NaT
    returns flat DatetimeIndex of length season*location
    """
    days = pd.to_timedelta(np.where(offset >= 0, offset, np.nan).ravel(), unit="D")
    return pd.DatetimeIndex(anchorDates(years, months).values + days.values)
 
 
def datesToDoy(dates, shape):
    # NaT -> NaN
    return np.asarray(dates.dayofyear, dtype=float).reshape(shape)
 
 
def datesToDekad(dates, shape):
    # dekad of year 1-36; days 21-31 of a month are the third dekad. NaT -> NaN
    month = np.asarray(dates.month, dtype=float)
    day = np.asarray(dates.day, dtype=float)
    return ((month - 1) * 3 + np.minimum((day - 1) // 10, 2) + 1).reshape(shape)
 



def postAgroOnset(offset, config):
    """
    offset: DataArray (season, location) with days from anchor date, -99 for no onset,
            and coordinates regime and anchorMonth along location
    Returns Dataset with:
        anchorDate, onsetDate                     - dates (season, location)
        onsetDaysSinceAnchor, onsetDekadsSinceAnchor - counted from the anchor date/dekad (0 = anchor)
        onsetDoy, onsetDekad                      - day and dekad of calendar year
        onsetDoyClim, onsetDekadClim              - climatology (location)
        onsetDoyAnom, onsetDekadAnom              - anomalies in days and dekads, positive = late
        regime, anchorMonth                       - (location)
 
    Climatology is the mean onset over seasons climStartYr-climEndYr, calculated on days
    from the anchor (which do not wrap around the year end), excluding seasons without onset.
    """
    offset = offset.transpose("season", "location")
    off = offset.values
    seasons = offset.season.values
    months = offset.anchorMonth.values
    shape = off.shape
    noOnset = off == -99
 
    # dates
    anchors = anchorDates(seasons, months).values.reshape(shape)
    dates = offsetToDates(off, seasons, months)
 
    # day and dekad of calendar year
    doy = datesToDoy(dates, shape)
    dekad = datesToDekad(dates, shape)
 
    # days and dekads since anchor - these do not wrap around the year end
    anchorDekad = (months - 1) * 3 + 1
    daysSince = np.where(off >= 0, off, np.nan)
    dekadsSince = (dekad - anchorDekad) % 36
 
    # climatology - mean of days since anchor, rounded to whole days
    valid = offset.where(offset >= 0)
    climOff = valid.sel(season=slice(config["climStartYr"], config["climEndYr"])).mean("season").round()
    # converted to a date in a reference season of non-leap years (2001/2002)
    climDates = offsetToDates(climOff.values[None, :], [2001], months)
    climDoy = datesToDoy(climDates, (len(months),))
    climDekad = datesToDekad(climDates, (len(months),))
    climDekadsSince = (climDekad - anchorDekad) % 36
 
    # anomalies
    anomDays = daysSince - climOff.values
    anomDekad = dekadsSince - climDekadsSince
 
    # no onset
    for arr in (doy, dekad, daysSince, dekadsSince):
        arr[noOnset] = np.nan
 
    climText = "mean over seasons {}-{}, excluding seasons without onset".format(config["climStartYr"], config["climEndYr"])
    dims = ("season", "location")
    ds = xr.Dataset(coords=offset.coords)
    ds["anchorDate"] = (dims, anchors, {"description": "first day of the season (anchor date)"})
    ds["onsetDate"] = (dims, dates.values.reshape(shape),
                       {"description": "date of rainy season onset; empty if no onset or missing data"})
    ds["onsetDaysSinceAnchor"] = (dims, daysSince,
                                  {"units": "days", "no_onset_value": -99,
                                   "description": "days from anchor date to onset; 0 = anchor date"})
    ds["onsetDekadsSinceAnchor"] = (dims, dekadsSince,
                                    {"units": "dekads", "no_onset_value": -99,
                                     "description": "dekads from anchor dekad to onset dekad; 0 = anchor dekad"})
    ds["onsetDoy"] = (dims, doy,
                      {"units": "day of year", "no_onset_value": -99,
                       "description": "day of calendar year of rainy season onset; season labelled with the year of its first month"})
    ds["onsetDoyClim"] = ("location", climDoy, {"units": "day of year", "description": climText})
    ds["onsetDoyAnom"] = (dims, anomDays,
                          {"units": "days", "description": "onset minus climatology; positive - late onset"})
    ds["onsetDekad"] = (dims, dekad,
                        {"units": "dekad of year (1-36)", "no_onset_value": -99})
    ds["onsetDekadClim"] = ("location", climDekad, {"units": "dekad of year (1-36)", "description": climText})
    ds["onsetDekadAnom"] = (dims, anomDekad,
                            {"units": "dekads", "description": "onset dekad minus climatological dekad; positive - late onset"})
 
    # regime and anchorMonth from coordinates to variables
    return ds.reset_coords(["regime", "anchorMonth"])
 


def writeAgroOnsetOutput(ds, meta, path):
    """
    Writes the Dataset returned by postAgroOnset (all variables have a location dimension).
    Grid -> one netcdf with all variables on the original grid.
    Stations -> one csv per variable, <path>_<variable>.csv, with ID/Lat/Lon header rows,
    as in the input format.
    Locations that were dropped (no data, all-year regime) come out as NaN.
    Returns list of written files.
    """
    path = Path(path)
    if isinstance(ds, xr.DataArray):
        ds = ds.to_dataset(name=ds.name or "value")
 
    # keep only coordinates that are needed to rebuild the grid/station list
    extra = [c for c in ds.coords if c not in ds.dims and c not in ("lat", "lon")]
    ds = ds.drop_vars(extra)
 
    written = []
    if meta["type"] == "grid":
        out = ds.set_index(location=["lat", "lon"]).unstack("location")
        out = out.reindex(lat=meta["lat"], lon=meta["lon"]).transpose(..., "lat", "lon")
        outFile = path.with_suffix(".nc")
        out.to_netcdf(outFile)
        written.append(outFile)
    else:
        for var in ds.data_vars:
            out = ds[var].reindex(location=meta["ids"]).transpose(..., "location")
            if out.ndim == 1:
                df = out.to_pandas().to_frame(var).T
            else:
                df = out.to_pandas()
            df.columns = pd.MultiIndex.from_arrays([meta["ids"], meta["lat"], meta["lon"]],
                                                   names=["ID", "Lat", "Lon"])
            outFile = path.parent / "{}_{}.csv".format(path.name, var)
            df.to_csv(outFile)
            written.append(outFile)
 
    for outFile in written:
        showMessage("Written {}".format(outFile), "INFO")
    return written

    

# main API function #################################################################

def computeProductsObsNoGui(config):
    gl.config = config
    settings = loadSettings()

    selected = [k for products in CATEGORIES.values() for k in products if config["products"].get(k)]
    if len(selected) == 0:
        showMessage("No products selected", "ERROR")
        return None

    outDir = Path(config["outDir"])
    outDir.mkdir(parents=True, exist_ok=True)

    #reading data file
    # data will have location coordinate
    data, meta = readObs(config)
    
    if data is None:
        showMessage("Observations could not be read, stopping early.", "ERROR")
        return None

    n_jobs = getNJobs(config, settings["fractionCpus"])
    success = True

    # iterating through categories
    for category, products in CATEGORIES.items():
        
        #selecting products from that category that are requested in the config
        keys = [k for k in products if config["products"].get(k)]
        if len(keys) == 0:
            continue

        showMessage("Preparing data for {} products...".format(category), "INFO")

        #preparation is identical for all products in a category - if not - then it should be movedd to the for key loop
        inputs = preprocess(category, data, config, settings)
        
        if inputs is None:
            showMessage("Data for {} products could not be prepared".format(category), "ERROR")
            success = False
            continue
        
        #iterating through products within the category
        for key in keys:
            showMessage("Calculating {}...".format(key), "INFO")
            try:
                start = time.time()

                #dispatch calculations
                results = calculate(category, inputs, products[key], n_jobs, settings)

                #dispatch postprocessing
                results = postprocess(category, results, settings)
                
                showMessage("\tjobs: {}, elapsed time: {:.1f} s".format(n_jobs, time.time() - start))

                #dispatch writing output
                writeoutput(category,results,meta,outDir, config["obsDsetCode"], key)
                
            except Exception as e:
                showMessage("{} could not be calculated. Full error: {}".format(key, e), "ERROR")
                success = False

    if success:
        showMessage("All done!", "SUCCESS")
    else:
        showMessage("Finished with errors, see log above", "ERROR")
    return success


if __name__ == "__main__":
    computeProductsObsNoGui(readConfigFile(sys.argv[1]))
