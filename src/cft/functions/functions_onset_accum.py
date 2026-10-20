"""
Onset and demise of the rainy season from anomalous accumulation - pre-processing, calculation,
post-processing and writing of output. Kernel is in kernels_accum_onset.py.
Used by functions_products_obs.py.
"""

import numpy as np
import pandas as pd
import xarray as xr

from scipy.signal import butter

from cft.functions.functions_common import showMessage, runParallel
from cft.functions.functions_products_obs_common import (toDaily, dropLeapDays, datesToDoy, datesToDekad,
                                                     writeLocationOutput)
from cft.functions.kernels_onset_accum import ACCUM_VARS


# preprocessing for accumulated onset #############################################################################


def preAccumOnset(data, config, settings):
    """
    Returns {"data": daily data for locations with a single rainy season,
             with coordinates w0, anchorMonth, anchorDay and rm} or None.
    """
    data = toDaily(data)
    if data is None:
        showMessage("Onset requires daily data", "ERROR")
        return None
    data = data.where(data >= 0)
 
    # climatology without 29 February, as in the original code (no-leap calendar)
    clim = dropLeapDays(data.sel(time=slice(str(config["climStartYr"]), str(config["climEndYr"]))))
    w0 = harmonicW0(clim)
    rm = clim.mean("time")
 
    seasonal = w0.notnull().values
    showMessage("\tlocations with a single rainy season: {}, other: {}".format(
        int(seasonal.sum()), int((~seasonal).sum())))
    if not seasonal.any():
        showMessage("No locations with a single rainy season - onset cannot be calculated", "ERROR")
        return None
 
    # w0 as month and day, in a non-leap reference year
    w0dates = pd.Timestamp(2001, 1, 1) + pd.to_timedelta(w0.values[seasonal] - 1, unit="D")
 
    data = data.isel(location=seasonal)
    data = data.assign_coords(w0=("location", w0.values[seasonal].astype(int),
                                  {"description": "start of water year, day of year (no-leap calendar)"}),
                              anchorMonth=("location", w0dates.month.values),
                              anchorDay=("location", w0dates.day.values),
                              rm=("location", rm.values[seasonal],
                                  {"units": "mm/day", "description": "mean daily rainfall in climatological period"}))
    return {"data": data}


def harmonicW0(clim):
    """
    clim: daily data (time, location) for the climatological period, without 29 February
    Returns w0 (location) - day of year (1-365, no-leap) of the start of the water year,
    NaN where the annual harmonic does not dominate the annual cycle
    """
    # no-leap day of year: in leap years days after February shifted back by one
    doy = clim.time.dt.dayofyear - (clim.time.dt.is_leap_year & (clim.time.dt.month > 2))
    cycle = clim.groupby(doy.rename("doy")).mean("time").transpose("doy", "location").values
    n = cycle.shape[0]
 
    # share of variance explained by each harmonic
    yrfft = 2 * np.fft.rfft(cycle, axis=0) / n
    with np.errstate(divide="ignore", invalid="ignore"):
        frcharm = n * (yrfft.real ** 2 + yrfft.imag ** 2) / (2 * (n - 1) * np.var(cycle, axis=0, ddof=1))
 
    # single rainy season only if annual harmonic explains more than semi-annual and 3rd harmonic
    # (comparisons with NaN - missing data, no rain - are False, so such locations are excluded)
    seasonal = (frcharm[1] > frcharm[2]) & (frcharm[1] > frcharm[3])
 
    # start of water year - minimum of mean + annual harmonic
    harm = np.fft.irfft(yrfft[:2], n, axis=0) * (n / 2)
    w0 = np.where(seasonal, np.argmin(harm, axis=0) + 1, np.nan)
    return xr.DataArray(w0, dims="location")


# calculations for accumulated onset #############################################################################


def anchorDatesMD(years, months, days):
    """
    years: 1-D (season), months, days: 1-D (location)
    returns datetime64 array (season, location) of season start dates
    """
    Y, M = np.broadcast_arrays(np.asarray(years)[:, None], np.asarray(months)[None, :])
    D = np.broadcast_to(np.asarray(days)[None, :], Y.shape)
    dates = pd.to_datetime(pd.DataFrame({"year": Y.ravel(), "month": M.ravel(), "day": D.ravel()}))
    return dates.values.reshape(Y.shape)
 
 
def accumWindows(data, windowDays):
    """
    Cuts daily data (time, location) into windows (season, day, location), each starting on the
    location's own anchor date (anchorMonth, anchorDay). Season is labelled with the year of its first day.
    Incomplete windows are NaN; seasons with no complete window at any location are dropped.
    """
    times = pd.DatetimeIndex(data.time.values)
    years = np.arange(times[0].year, times[-1].year + 1)
    starts = anchorDatesMD(years, data.anchorMonth.values, data.anchorDay.values)
    pos = ((starts - times[0].to_datetime64()) // np.timedelta64(1, "D")).astype(int)
    valid = (pos >= 0) & (pos + windowDays <= len(times))
 
    nloc = data.sizes["location"]
    index = np.where(valid, pos, 0)[:, None, :] + np.arange(windowDays)[None, :, None]
    values = data.transpose("time", "location").values[index, np.arange(nloc)[None, None, :]]
    values[np.broadcast_to(~valid[:, None, :], values.shape)] = np.nan
 
    keep = valid.any(axis=1)
    coords = {k: v for k, v in data.coords.items() if v.dims == ("location",)}
    coords["season"] = years[keep]
    return xr.DataArray(values[keep], dims=("season", "day", "location"), coords=coords)


def applyAccumKernel(data, kernel, windowDays, onsetDays, demiseDays, b, a, padLen):
    # runs on one chunk of locations; returns (season, location, var)
    windows = accumWindows(data, windowDays)
    rm = xr.DataArray(data.rm.values, dims="location")
    result = xr.apply_ufunc(kernel, windows, rm,
                            input_core_dims=[["day"], []],
                            output_core_dims=[["var"]],
                            vectorize=True,
                            output_dtypes=[float],
                            kwargs={"onsetDays": onsetDays, "demiseDays": demiseDays,
                                    "b": b, "a": a, "padLen": padLen})
    return result.assign_coords(var=ACCUM_VARS)
 
 
def calcAccumOnset(inputs, func, n_jobs, settings):
    if settings["accumOnsetDays"] + settings["accumDemiseDays"] > settings["accumWindowDays"]:
        showMessage("onset and demise search periods are together longer than the water year", "ERROR")
        return None
 
    # Butterworth low-pass filter, designed once here and passed to the kernel.
    # As in the original code: order 2, critical frequency 1/cutoff of the Nyquist frequency
    # (i.e. periods shorter than about 2*cutoff days are removed), padding of 2*cutoff values
    cutoff = settings["accumCutoff"]
    b, a = butter(2, 1 / float(cutoff), btype="lowpass")
    padLen = int(2 * cutoff)
 
    return runParallel(applyAccumKernel, inputs["data"], n_jobs,
                       kernel=func,
                       windowDays=settings["accumWindowDays"],
                       onsetDays=settings["accumOnsetDays"],
                       demiseDays=settings["accumDemiseDays"],
                       b=b, a=a, padLen=padLen)


# postprocessing for accumulated onset #############################################################################


def postAccumOnset(result, config):
    """
    result: DataArray (season, location, var) from calcAccumOnset
    Returns Dataset with onset and demise dates, day of year, dekad, duration, rainfall in the
    wet and dry season, their climatologies and anomalies, and w0, rm, anchorMonth, anchorDay.
    """
    result = result.transpose("season", "location", "var")
    seasons = result.season.values
    months, days = result.anchorMonth.values, result.anchorDay.values
    shape = (len(seasons), len(months))
    dims = ("season", "location")
    climSel = (seasons >= config["climStartYr"]) & (seasons <= config["climEndYr"])
 
    # -99 - no onset/demise found (minimum on the edge of the search period)
    onsetOff = result.sel(var="onset").values
    demiseOff = result.sel(var="demise").values
    wet = result.sel(var="wet").values
    # dry season - from day after previous season's demise to day before this season's onset
    postDemise = result.sel(var="postDemise")
    dry = (postDemise.shift(season=1) + result.sel(var="preOnset")).values
 
    anchors = anchorDatesMD(seasons, months, days)
    anchorDekad = datesToDekad(pd.DatetimeIndex(anchors[0]), (len(months),))
    climAnchors = anchorDatesMD([2001], months, days)   # non-leap reference season
 
    def toDates(start, offset):
        days_ = pd.to_timedelta(offset.ravel(), unit="D")
        return pd.DatetimeIndex(start.ravel() + days_.values)
 
    def climMean(arr, roundDays=False):
        with np.errstate(invalid="ignore"):
            m = np.nanmean(np.where(climSel[:, None], arr, np.nan), axis=0)
        return np.round(m) if roundDays else m
 
    ds = xr.Dataset(coords=result.drop_vars("var").coords)
    ds["anchorDate"] = (dims, anchors, {"description": "start of water year"})
    textClim = "mean over seasons {}-{}".format(config["climStartYr"], config["climEndYr"])
 
    for name, off in (("onset", onsetOff), ("demise", demiseOff)):
        notFound = off == -99
        offValid = np.where(off >= 0, off, np.nan)
        dates = toDates(anchors, offValid)
        doy = datesToDoy(dates, shape)
        dekad = datesToDekad(dates, shape)
        dekadsSince = (dekad - anchorDekad) % 36
 
        climOff = climMean(offValid, roundDays=True)
        climDates = toDates(climAnchors, climOff[None, :])
        climDoy = datesToDoy(climDates, (len(months),))
        climDekad = datesToDekad(climDates, (len(months),))
        climDekadsSince = (climDekad - anchorDekad) % 36
 
        # no onset/demise found: -99 in day and dekad variables, empty date, NaN anomaly
        doy[notFound] = -99
        dekad[notFound] = -99
        noneText = "-99 - not found within the search period"
 
        ds[name + "Date"] = (dims, dates.values.reshape(shape), {"description": "date of " + name})
        ds[name + "DaysSinceAnchor"] = (dims, off, {"units": "days", "no_value": noneText,
                                                     "description": "days from start of water year to " + name})
        ds[name + "Doy"] = (dims, doy, {"units": "day of year", "no_value": noneText,
                                        "description": "day of calendar year of " + name})
        ds[name + "DoyClim"] = ("location", climDoy, {"units": "day of year", "description": textClim})
        ds[name + "DoyAnom"] = (dims, offValid - climOff, {"units": "days", "description": name + " minus climatology; positive - late"})
        ds[name + "Dekad"] = (dims, dekad, {"units": "dekad of year (1-36)", "no_value": noneText})
        ds[name + "DekadClim"] = ("location", climDekad, {"units": "dekad of year (1-36)", "description": textClim})
        ds[name + "DekadAnom"] = (dims, dekadsSince - climDekadsSince, {"units": "dekads", "description": name + " dekad minus climatological dekad; positive - late"})
 
    duration = np.where((onsetOff >= 0) & (demiseOff >= 0), demiseOff - onsetOff, np.nan)
    for name, arr, attrs in (("duration", duration, {"units": "days", "description": "demise minus onset"}),
                             ("wetTotal", wet, {"units": "mm", "description": "rainfall from onset to demise"}),
                             ("dryTotal", dry, {"units": "mm", "description": "rainfall from previous demise to onset"})):
        clim = climMean(arr)
        ds[name] = (dims, arr, attrs)
        ds[name + "Clim"] = ("location", clim, {"units": attrs["units"], "description": textClim})
        ds[name + "Anom"] = (dims, arr - clim, {"units": attrs["units"], "description": name + " minus climatology"})
 
    return ds.reset_coords(["w0", "rm", "anchorMonth", "anchorDay"])


# writing for accumulated onset #############################################################################

def writeAccumOnsetOutput(ds, meta, path, description):
    # same output layout as agronomic onset: one netcdf (grid) or one csv per variable (stations)
    return writeLocationOutput(ds, meta, path, description)
