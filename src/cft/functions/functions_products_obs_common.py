"""
Functions shared by the categories of the products module. Data are handled as xarray.DataArray.

Convention for observed data:
    dims (time, location)
    grid:     location = stacked (lat, lon); lat and lon are coordinates along location
    stations: location = station ID;         lat and lon are coordinates along location
    Locations with no data at all are dropped on reading.

readObs() also returns a small `meta` dictionary that the writing functions use to put
results back onto the original grid, or the original list of stations.
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from cft.functions.functions_common import showMessage, coordsubs


# reading ###########################################################################

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


def dropLeapDays(da):
    return da.sel(time=~((da.time.dt.month == 2) & (da.time.dt.day == 29)))


# dates ############################################################################

def datesToDoy(dates, shape):
    # NaT -> NaN
    return np.asarray(dates.dayofyear, dtype=float).reshape(shape)
 
 
def datesToDekad(dates, shape):
    # dekad of year 1-36; days 21-31 of a month are the third dekad. NaT -> NaN
    month = np.asarray(dates.month, dtype=float)
    day = np.asarray(dates.day, dtype=float)
    return ((month - 1) * 3 + np.minimum((day - 1) // 10, 2) + 1).reshape(shape)


# writing ##########################################################################

def writeLocationOutput(ds, meta, path):
    """
    Writes a Dataset (or DataArray) in which all variables have a location dimension.
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
