"""
Agronomic onset (threshold-based onset definitions A-D) - pre-processing, calculation,
post-processing and writing of output. Kernels are in kernels_agro_onset.py.
Used by functions_products_obs.py.
"""

import numpy as np
import pandas as pd
import xarray as xr
import os

from cft.functions.functions_common import showMessage, runParallel, coordsubs
from cft.functions.functions_products_obs_common import toDaily, datesToDoy, datesToDekad, writeLocationOutput


#used by agronomic onsets
REGIMES = {"allyear": 0, "summer": 1, "winter": 2}


# preprocessing for agronomic onset #############################################################################


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


# calculations for agronomic onset #############################################################################

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


# postprocessing for agronomic onset #############################################################################

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
    print("here")
    ds = xr.Dataset(coords=offset.coords)
    ds["noOnset"] = (dims, noOnset, {"description": "where onset was not achieved during given season"})
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


# writing for agronomic onset #############################################################################

def writeAgroOnsetOutput(ds, meta, path, description, settings):
    # one netcdf (grid) or one csv per variable (stations)
    writeLocationOutput(ds, meta, path, description, settings)
    if "onsetDaysSinceAnchor" in ds:
        result=writeForecastFiles(ds, meta, path, description, settings)
    
    return result



SEASON_NAMES = {1: "summer", 2: "winter"}   # regime codes

def writeForecastFiles(ds, meta, path, description, settings):
    # one file per anchor month (rainfall season) with season replaced by time,
    # taken from anchorDate; skipped if the season has no data
    showMessage("writing files for forecast")
    print(settings)

    onsetWindowDays=settings["onsetWindowDays"]
    onsetAnchorMonths=settings["onsetAnchorMonth"]

    months = np.unique(ds["anchorMonth"].values)
    months = months[~np.isnan(months)].astype(int)
    for seas in onsetAnchorMonths.keys():
        m=onsetAnchorMonths[seas]
        windowdays=onsetWindowDays[seas]
        if m in months:
            mask = ds["anchorMonth"] == m
            da = ds[["onsetDaysSinceAnchor"]].where(mask)
            if not da["onsetDaysSinceAnchor"].notnull().any():
                continue
            if "noOnset" in ds:
                print("here2")
                lastDay = windowdays - 1      # days since anchor: 0 = season start
                da["onsetDaysSinceAnchor"] = da["onsetDaysSinceAnchor"].where(
                    ds["noOnset"] != 1, lastDay)

            # anchor date is the same for all cells of one season: collapse over space
            space = [d for d in ds["anchorDate"].dims if d != "season"]
            dates = ds["anchorDate"].where(mask).min(dim=space, skipna=True)
            da = (da.assign_coords(time=("season", dates.values))
                    .swap_dims({"season": "time"})
                    .drop_vars("season"))
            da = da.sel(time=da["time"].notnull())       # seasons without an anchor date
            if description:
                da = da.assign_attrs(description=description)
            name = "m{:02d}".format(m)
            if "regime" in ds:
                codes = np.unique(ds["regime"].where(mask).values)
                codes = codes[~np.isnan(codes)]
                if len(codes) == 1 and int(codes[0]) in SEASON_NAMES:
                    name = SEASON_NAMES[int(codes[0])]
            outfile = path.with_name("{}_{}_for_forecast".format(path.name, name))        
            writeLocationOutput(da, meta, outfile, description, settings)
                    
        
        

