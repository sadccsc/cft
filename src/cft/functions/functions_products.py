"""
Products module - calculations. Independent of the GUI.

API:
    computeProductsNoGui(config)

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
                                            readObs, writeOutput, toDaily, coordsubs)
from cft.functions import products_onset


# registry ##########################################################################

CATEGORIES = {
    "onset": {
        "onsetA": products_onset.onsetA,
        "onsetB": products_onset.onsetB,
        "onsetC": products_onset.onsetC,
        "onsetD": products_onset.onsetD,
    },
}


# settings that users should not normally change. Values in dictionaries/deep_config.json override these.
DEFAULT_SETTINGS = {
    "fractionCpus": 0.5,
    "onsetAnchorMonth": {"summer": 7, "winter": 1},   # first month of the season (dry season)
    "onsetRegimeThreshold": 0.667,                    # share of annual rainfall in Oct-Mar (summer) or Apr-Sep (winter)
    "onsetWindowDays": 365,
}

REGIMES = {"allyear": 0, "summer": 1, "winter": 2}


def loadSettings():
    settings = dict(DEFAULT_SETTINGS)
    deep = readConfigFile(Path(__file__).resolve().parent.parent / "dictionaries" / "deep_config.json")
    if deep is not None:
        settings.update({k: v for k, v in deep.items() if k in settings})
    return settings


# dispatchers #######################################################################

def preprocess(category, data, config, settings):
    if category == "onset":
        return preOnset(data, config, settings)


def calculate(category, inputs, func, n_jobs, settings):
    if category == "onset":
        return calcOnset(inputs, func, n_jobs, settings)


def postprocess(category, result, settings):
    if category == "onset":
        return postOnset(result)


# onset #############################################################################

def preOnset(data, config, settings):
    """
    Returns {"data": daily data for seasonal locations with anchorMonth coordinate,
             "outputs": {"regime": regime map}} or None.
    """
    data = toDaily(data)
    if data is None:
        showMessage("Onset requires daily data", "ERROR")
        return None
    data = data.where(data >= 0)

    if config.get("regimeFile", "") == "":
        regime = regimeFromData(data, config, settings)
    else:
        regime = regimeFromMap(data, config["regimeFile"])
    if regime is None:
        return None

    for name, code in REGIMES.items():
        showMessage("\t{} rainfall regime: {} locations".format(name, int((regime == code).sum())))

    seasonal = (regime > 0).values
    if not seasonal.any():
        showMessage("No locations with seasonal rainfall regime - onset cannot be calculated", "ERROR")
        return None

    anchors = {REGIMES[k]: v for k, v in settings["onsetAnchorMonth"].items()}
    data = data.isel(location=seasonal)
    data = data.assign_coords(anchorMonth=("location", [anchors[int(r)] for r in regime.values[seasonal]]))

    return {"data": data, "outputs": {"regime": regime}}


def regimeFromData(data, config, settings):
    clim = data.sel(time=slice(str(config["climStartYr"]), str(config["climEndYr"])))
    total = clim.sum("time")
    summer = clim.where(clim.time.dt.month.isin([10, 11, 12, 1, 2, 3])).sum("time") / total
    winter = clim.where(clim.time.dt.month.isin([4, 5, 6, 7, 8, 9])).sum("time") / total
    thresh = settings["onsetRegimeThreshold"]
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
    return setRegimeAttrs(regime.astype(int))


def setRegimeAttrs(regime):
    regime.name = "regime"
    regime.attrs = {"flag_values": "0 1 2", "flag_meanings": "all_year summer winter"}
    return regime


def calcOnset(inputs, func, n_jobs, settings):
    return runParallel(applyOnsetKernel, inputs["data"], n_jobs,
                       kernel=func, windowDays=settings["onsetWindowDays"])


def applyOnsetKernel(data, kernel, windowDays):
    # runs on one chunk of locations; returns offsets from the anchor date, dims (season, location)
    results = []
    for month in np.unique(data.anchorMonth.values):
        sub = data.isel(location=(data.anchorMonth.values == month))
        windows = seasonWindows(sub, int(month), windowDays)
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


def postOnset(offset):
    # offset (days from anchor date) -> day of year. -99 (no onset) is kept, NaN stays NaN
    doy = xr.full_like(offset, np.nan)
    for month in np.unique(offset.anchorMonth.values):
        sel = offset.anchorMonth.values == month
        off = offset.values[:, sel]
        starts = pd.to_datetime(["{}-{:02d}-01".format(y, int(month)) for y in offset.season.values])
        days = pd.to_timedelta(np.where(off >= 0, off, np.nan).ravel(), unit="D")
        dates = pd.DatetimeIndex(np.repeat(starts.values, off.shape[1]) + days.values)
        values = np.asarray(dates.dayofyear, dtype=float).reshape(off.shape)
        values[off == -99] = -99
        doy.values[:, sel] = values
    doy.attrs = {"units": "day of year",
                 "description": "day of rainy season onset; season labelled with the year of its first month",
                 "no_onset_value": -99}
    return doy


# main API function #################################################################

def computeProductsNoGui(config):
    gl.config = config
    settings = loadSettings()

    selected = [k for products in CATEGORIES.values() for k in products if config["products"].get(k)]
    if len(selected) == 0:
        showMessage("No products selected", "ERROR")
        return None

    outDir = Path(config["outDir"])
    outDir.mkdir(parents=True, exist_ok=True)

    data, meta = readObs(config)
    if data is None:
        showMessage("Observations could not be read, stopping early.", "ERROR")
        return None

    n_jobs = getNJobs(config, settings["fractionCpus"])
    success = True

    for category, products in CATEGORIES.items():
        keys = [k for k in products if config["products"].get(k)]
        if len(keys) == 0:
            continue

        showMessage("Preparing data for {} products...".format(category), "INFO")
        inputs = preprocess(category, data, config, settings)
        if inputs is None:
            showMessage("Data for {} products could not be prepared".format(category), "ERROR")
            success = False
            continue

        for name, output in inputs.get("outputs", {}).items():
            writeOutput(output, meta, outDir / "{}_{}-{}".format(config["obsDsetCode"], category, name))

        for key in keys:
            showMessage("Calculating {}...".format(key), "INFO")
            try:
                start = time.time()
                result = calculate(category, inputs, products[key], n_jobs, settings)
                result = postprocess(category, result, settings)
                result.name = key
                showMessage("\tjobs: {}, elapsed time: {:.1f} s".format(n_jobs, time.time() - start))
                writeOutput(result, meta, outDir / "{}_{}".format(config["obsDsetCode"], key))
            except Exception as e:
                showMessage("{} could not be calculated. Full error: {}".format(key, e), "ERROR")
                success = False

    if success:
        showMessage("All done!", "SUCCESS")
    else:
        showMessage("Finished with errors, see log above", "ERROR")
    return success


if __name__ == "__main__":
    computeProductsNoGui(readConfigFile(sys.argv[1]))
