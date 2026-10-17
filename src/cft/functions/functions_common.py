"""
Functions shared across CFT modules. Data are handled as xarray.DataArray.

Convention for observed data:
    dims (time, location)
    grid:     location = stacked (lat, lon); lat and lon are coordinates along location
    stations: location = station ID;         lat and lon are coordinates along location
    Locations with no data at all are dropped on reading.

readObs() also returns a small `meta` dictionary that writeOutput() uses to put
results back onto the original grid, or the original list of stations.
"""

import os, json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from joblib import Parallel, delayed, cpu_count

from cft import gl


# messages ##########################################################################

def showMessage(message, type="RUNTIME"):
    msgColors = {"ERROR": "red",
                 "INFO": "grey",
                 "RUNTIME": "grey",
                 "NONCRITICAL": "red",
                 "SUCCESS": "green"}
    try:
        outmessage = "<pre><font color={}>{}</font></pre>".format(msgColors[type], message)
        gl.window.log_signal.emit(outmessage)
    except Exception:
        if type in ["NONCRITICAL", "ERROR", "INFO"]:
            message = "{}: {}".format(type, message)
        print(message)


def readConfigFile(file):
    try:
        with open(file) as f:
            return json.load(f)
    except Exception:
        return None


# parallelisation ###################################################################

def getNJobs(config, fractionCpus):
    if not config.get("parallelize", False):
        return 1
    return max(1, int(cpu_count(only_physical_cores=False) * fractionCpus))


def runParallel(func, da, n_jobs, **kwargs):
    """
    Runs func(chunk, **kwargs) on chunks of da split along the location dimension
    and concatenates the results along location. func has to be a module-level
    function (so that it can be sent to another process).
    """
    nloc = da.sizes["location"]
    if n_jobs <= 1 or nloc < 2:
        return func(da, **kwargs)
    # a few chunks per job, so that a slow chunk does not hold up the whole run
    chunks = [i for i in np.array_split(np.arange(nloc), n_jobs * 4) if len(i) > 0]
    results = Parallel(n_jobs=n_jobs)(delayed(func)(da.isel(location=i), **kwargs) for i in chunks)
    return xr.concat(results, dim="location", join="outer")


# reading ###########################################################################

coordsubs = {"lon": ["longitude", "X", "Longitude", "Lon"],
             "lat": ["latitude", "Y", "Latitude", "Lat"],
             "time": ["T", "valid_time"]}


def readObs(config):
    """Returns (DataArray(time, location), meta) or (None, None)."""
    file = config["obsFile"]
    if not os.path.exists(file):
        showMessage("Observations file {} does not exist".format(file), "ERROR")
        return None, None

    showMessage("Reading observations from {}...".format(file), "INFO")
    ext = Path(file).suffix.lower()
    try:
        if ext == ".nc":
            da, meta = readObsNetcdf(file, config["obsVar"])
        elif ext == ".csv":
            da, meta = readObsCsv(file)
        else:
            showMessage("Only .nc and .csv files are accepted, got {}".format(ext), "ERROR")
            return None, None
    except Exception as e:
        showMessage("Could not read {}. Full error: {}".format(file, e), "ERROR")
        return None, None
    if da is None:
        return None, None

    if config.get("obsMissingValue", "") != "":
        da = da.where(da != float(config["obsMissingValue"]))

    da = da.astype("float32")
    da = da.dropna("location", how="all")
    if da.sizes["location"] == 0:
        showMessage("Observations contain no valid data", "ERROR")
        return None, None

    firstyear, lastyear = int(da.time.dt.year[0]), int(da.time.dt.year[-1])
    showMessage("Data cover {} to {}, {} locations with data".format(
        str(da.time.values[0])[:10], str(da.time.values[-1])[:10], da.sizes["location"]))
    if config["climStartYr"] < firstyear or config["climEndYr"] > lastyear:
        showMessage("Climatological period {}-{} extends beyond period covered by data {}-{}".format(
            config["climStartYr"], config["climEndYr"], firstyear, lastyear), "ERROR")
        return None, None

    return da.load(), meta


def readObsNetcdf(file, var):
    """
    reads netcdf file, harmonizes coordinates, stacks along lat lon dimensions crating location dimension
    returns transformed data and meta - object containing original lat lon values
    """
    ds = xr.open_dataset(file, decode_times=False)
    for key, alternatives in coordsubs.items():
        for x in alternatives:
            if x in ds.coords and key not in ds.coords:
                ds = ds.rename({x: key})

    # same calendar clean-up as in forecast
    if ds["time"].attrs.get("calendar") == "360":
        ds["time"].attrs["calendar"] = "360_day"
    ds = xr.decode_cf(ds)
    if not np.issubdtype(ds["time"].dtype, np.datetime64):
        ds = ds.convert_calendar("standard", align_on="date", missing=np.nan)

    if var not in ds.data_vars:
        showMessage("Variable {} is not in {}".format(var, file), "ERROR")
        return None, None
    da = ds[var]

    for dim in list(da.dims):
        if dim not in ["time", "lat", "lon"]:
            if da.sizes[dim] == 1:
                da = da.isel({dim: 0}, drop=True)
            else:
                showMessage("Variable has an extra dimension {} of size {}".format(dim, da.sizes[dim]), "ERROR")
                return None, None

    da = da.transpose("time", "lat", "lon")
    meta = {"type": "grid", "lat": da.lat.values, "lon": da.lon.values}
    
    # lat/lon -> location. reset_index keeps lat and lon as plain coordinates along location
    da = da.stack(location=("lat", "lon")).reset_index("location")
    da["time"] = pd.to_datetime(da.time.values).normalize()
    return da, meta


def readObsCsv(file):
    # same layout as the "byLoc" format in forecast: rows ID, Lat, Lon at the top, then dates
    df = pd.read_csv(file, header=[0, 1, 2], index_col=0, parse_dates=True)
    names = [str(x).lower() for x in df.columns.names]
    if "lat" not in names or "lon" not in names:
        showMessage("CSV file should have rows named Lat and Lon below the ID row", "ERROR")
        return None, None
    ids = df.columns.get_level_values(0).astype(str).values
    lats = df.columns.get_level_values(names.index("lat")).astype(float).values
    lons = df.columns.get_level_values(names.index("lon")).astype(float).values

    da = xr.DataArray(df.values.astype(float), dims=("time", "location"),
                      coords={"time": pd.to_datetime(df.index).normalize().values,
                              "location": ids,
                              "lat": ("location", lats),
                              "lon": ("location", lons)})
    meta = {"type": "stations", "ids": ids, "lat": lats, "lon": lons}
    return da, meta


def toDaily(da):
    """Checks that data are daily and fills gaps in the time axis with NaN. Returns None if not daily."""
    step = pd.Series(da.time.values).diff().median()
    if step != pd.Timedelta(days=1):
        return None
    full = pd.date_range(da.time.values[0], da.time.values[-1], freq="D")
    return da.reindex(time=full)


