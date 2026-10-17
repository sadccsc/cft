"""
Functions shared across all CFT modules: messages, config files, parallelisation,
coordinate names.
"""

import json

import numpy as np
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


# coordinates ######################################################################

coordsubs = {"lon": ["longitude", "X", "Longitude", "Lon"],
             "lat": ["latitude", "Y", "Latitude", "Lat"],
             "time": ["T", "valid_time"]}
