"""
DWTP (dry-to-wet transition period) category: pre, calc, post and write functions.

"""

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy.signal import butter
from cft.functions.functions_products_obs_common import toDaily, dropLeapDays
from cft.functions.functions_common import showMessage, runParallel
from cft.functions.kernels_onset_dwtp import NSTATS, DWTP_STATUS


DWTP_DESCRIPTION_STATS = (
    "DWTP statistics for each year and season. FirstDay is the first day of the DWTP, Length is the "
    "duration of the DWTP, OnsIntensity is the mean gradient of the BW60 filtered precipitation during "
    "the DWTP, TotPrecip is the total precipitation during the DWTP, PrecipRate is the precip rate during "
    "the DWTP, PrecipInt is precipitation intensity (total precipitation per wet days) during the DWTP, "
    "FrcWetDays is the fraction of wet days in the DWTP, LengthWetSpells is mean duration of wet spells "
    "during the DWTP, MaxWetSpell is longest wet spell in the DWTP, FrcDryDays is fraction of dry days in "
    "the DWTP, LengthDrySpells is the mean length of dry spells in the DWTP, and MaxDrySpell is longest "
    "dry spell in the DWTP.")
DWTP_DESCRIPTION_ENV = (
    "Climatological envelope of the DWTP. FirstDay is the first day of the climatological envelope, "
    "and Length is the duration of the climatological envelope.")
DWTP_DESCRIPTION_FLT = "Filtered daily precipitation using a Butterworth filter with a cutoff of 60 days."
 

# units and descriptions of the DWTP statistics (from the description of the original output)
DWTP_STATS_ATTRS = {
    "FirstDay": {"units": "day of year",
                 "description": "first day of the DWTP; 0-based in most years, 1-based in the first year, "
                                "can exceed 365 (as in the original code)"},
    "Length": {"units": "days", "description": "duration of the DWTP"},
    "OnsIntensity": {"units": "mm/day per day",
                     "description": "mean gradient of the BW60 filtered precipitation during the DWTP"},
    "TotPrecip": {"units": "mm", "description": "total precipitation during the DWTP"},
    "PrecipRate": {"units": "mm/day", "description": "precipitation rate during the DWTP"},
    "PrecipInt": {"units": "mm/wet day",
                  "description": "precipitation intensity (total precipitation per wet day) during the DWTP"},
    "FrcWetDays": {"units": "%", "description": "fraction of wet days in the DWTP"},
    "LengthWetSpells": {"units": "days", "description": "mean duration of wet spells during the DWTP"},
    "MaxWetSpell": {"units": "days", "description": "longest wet spell in the DWTP"},
    "FrcDryDays": {"units": "%", "description": "fraction of dry days in the DWTP"},
    "LengthDrySpells": {"units": "days", "description": "mean length of dry spells in the DWTP"},
    "MaxDrySpell": {"units": "days", "description": "longest dry spell in the DWTP"},
}
 
 


# pre ###############################################################################

def preDWTPOnset(data, config, settings):
    """
    Returns {"data": daily data without 29 February, "doy", "years": no-leap day of year and
    calendar year of each day, "climStart", "climStop": positions of the climatological period}
    """

    data = toDaily(data)
    if data is None:
        showMessage("DWTP requires daily data", "ERROR")
        return None
    # as in the original: negative values are not removed, calendar converted to no-leap
    data = dropLeapDays(data)

    times = pd.DatetimeIndex(data.time.values)
    if not (times[0].month == 1 and times[0].day == 1):
        showMessage("DWTP: the original method assumes data start on 1 January; data start on {}".format(
            times[0].date()), "NONCRITICAL")

    doy = np.asarray(times.dayofyear - (times.is_leap_year & (times.month > 2)))
    years = np.asarray(times.year)

    inClim = np.nonzero((years >= config["climStartYr"]) & (years <= config["climEndYr"]))[0]
    climStart, climStop = int(inClim[0]), int(inClim[-1]) + 1
    nClimYears = config["climEndYr"] - config["climStartYr"] + 1
    if climStop - climStart != nClimYears * 365:
        showMessage("DWTP: climatological period does not cover complete years - the climatological "
                    "envelope may be shifted", "NONCRITICAL")

    nGaps = int(data.isnull().any("time").sum())
    if nGaps > 0:
        showMessage("DWTP: {} locations have missing data - the method cannot process them".format(nGaps),
                    "NONCRITICAL")

    return {"data": data, "doy": doy, "years": years, "climStart": climStart, "climStop": climStop}


# calc ##############################################################################

def applyDWTPOnset(data, kernel, doy, years, climStart, climStop, b, a, padLen, minlen, mxrainy):
    # runs on one chunk of locations; returns Dataset with ons, clmEnv, w0, bwpp, status
    ons, clmEnv, w0, flt, status = xr.apply_ufunc(
        kernel, data,
        input_core_dims=[["time"]],
        output_core_dims=[["years", "sea", "nstats"], ["season", "Stats"], [], ["time"], []],
        vectorize=True,
        output_dtypes=[float] * 5,
        kwargs={"doy": doy, "years": years, "climStart": climStart, "climStop": climStop,
                "b": b, "a": a, "padLen": padLen, "minlen": minlen, "mxrainy": mxrainy})
    ds = xr.Dataset({"ons": ons, "clmEnv": clmEnv, "w0": w0, "bwpp": flt, "status": status})
    return ds.assign_coords(years=np.unique(years), sea=np.arange(mxrainy), nstats=NSTATS,
                            season=np.arange(mxrainy), Stats=["FirstDay", "Length"])


def calcDWTPOnset(inputs, func, n_jobs, settings):
    # Butterworth low-pass filter, as in the original: order 2, critical frequency 1/fwin of the
    # Nyquist frequency, padding of 2*fwin values
    fwin = settings["dwtpFilterWindow"]
    b, a = butter(2, 1 / float(fwin), btype="lowpass")
    padLen = int(2 * fwin)

    return runParallel(applyDWTPOnset, inputs["data"], n_jobs,
                       kernel=func,
                       doy=inputs["doy"], years=inputs["years"],
                       climStart=inputs["climStart"], climStop=inputs["climStop"],
                       b=b, a=a, padLen=padLen,
                       minlen=settings["dwtpMinLength"],
                       mxrainy=settings["dwtpMaxSeasons"])


# post ##############################################################################


def postDWTPOnset(result, config):
    """
    Returns dictionary of Datasets, one per output file:
        "Stats"       - one variable per statistic (FirstDay, Length, ...), dims (years, sea, location)
        "ClmEnvelope" - clmEnv (season, Stats, location), plus w0 and status (location)
        "PR60"        - bwpp (time, location), only if config["dwtpSaveFiltered"]
    """
    status = result.status.values
    for code, text in DWTP_STATUS.items():
        n = int((status == code).sum())
        if n > 0:
            showMessage("\tDWTP: {} locations - {}".format(n, text), "NONCRITICAL" if code in (2, 3) else "RUNTIME")
 
    # statistics as separate variables instead of the nstats dimension of the original ons array
    stats = result.ons.transpose("years", "sea", "nstats", "location").to_dataset(dim="nstats")
    for name in stats.data_vars:
        stats[name].attrs = DWTP_STATS_ATTRS[name]
    stats.attrs = {"description": DWTP_DESCRIPTION_STATS}
 
    envelope = xr.Dataset({"clmEnv": result.clmEnv.transpose("season", "Stats", "location"),
                           "w0": result.w0.assign_attrs(description="start of water year, day of year (no-leap)"),
                           "status": result.status.assign_attrs(
                               description="; ".join("{} - {}".format(k, v) for k, v in DWTP_STATUS.items()))},
                          attrs={"description": DWTP_DESCRIPTION_ENV})
 
    output = {"Stats": stats, "ClmEnvelope": envelope}
    if config.get("dwtpSaveFiltered", False):
        output["PR60"] = xr.Dataset({"bwpp": result.bwpp.transpose("time", "location")},
                                    attrs={"description": DWTP_DESCRIPTION_FLT})
    return output
 



# write #############################################################################

def writeDWTPOnsetOutput(output, meta, path, description, settings):
    """
    Writes each Dataset from postDWTP to a separate file: <path>_Stats, <path>_ClmEnvelope, <path>_PR60.
    Grid -> netcdf (compressed, as in the original). Stations -> one csv per variable, with ID/Lat/Lon
    header rows; dimensions other than location are stacked into rows.
    Returns list of written files.
    """
    path = Path(path)
    written = []
    for name, ds in output.items():
        base = path.parent / "{}_{}".format(path.name, name)
        if meta["type"] == "grid":
            out = ds.set_index(location=["lat", "lon"]).unstack("location")
            out = out.reindex(lat=meta["lat"], lon=meta["lon"]).transpose(..., "lat", "lon")
            outFile = base.with_suffix(".nc")
            out.to_netcdf(outFile, encoding={v: {"zlib": True} for v in out.data_vars})
            written.append(outFile)
        else:
            for var in ds.data_vars:
                da = ds[var].reindex(location=meta["ids"])
                other = [d for d in da.dims if d != "location"]
                if len(other) == 0:
                    df = da.to_pandas().to_frame(var).T
                elif len(other) == 1:
                    df = da.transpose(other[0], "location").to_pandas()
                else:
                    df = da.stack(row=other).transpose("row", "location").to_pandas()
                df.columns = pd.MultiIndex.from_arrays([meta["ids"], meta["lat"], meta["lon"]],
                                                       names=["ID", "Lat", "Lon"])
                outFile = base.parent / "{}_{}.csv".format(base.name, var)
                df.to_csv(outFile)
                written.append(outFile)

    for outFile in written:
        showMessage("Written {}".format(outFile), "INFO")
    return written
