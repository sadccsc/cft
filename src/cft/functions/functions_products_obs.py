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
    1. write the kernel (in kernels_<category>.py)
    2. add it to CATEGORIES
    3. add a checkbox to products.ui with objectName equal to the product key

Adding a category: add pre/calc/post functions and an "if" branch in each dispatcher.
"""

import sys, time
from pathlib import Path

import inspect
import copy

from cft import gl
from cft.functions.functions_common import showMessage, readConfigFile, getNJobs
from cft.functions.functions_products_obs_common import readObs
from cft.functions import kernels_onset_agro, kernels_onset_accum, kernels_onset_dwtp
from cft.functions.functions_onset_agro import (preAgroOnset, calcAgroOnset, postAgroOnset,
                                                writeAgroOnsetOutput)
from cft.functions.functions_onset_accum import (preAccumOnset, calcAccumOnset, postAccumOnset,
                                                 writeAccumOnsetOutput)
from cft.functions.functions_onset_dwtp import preDWTPOnset, calcDWTPOnset, postDWTPOnset, writeDWTPOnsetOutput

from cft.functions.plot_onset_outputs import plotLocationOutput   # wherever you put the file
from cft.functions.plot_onset_diagnostics import runAllDiagnostics

# registry ##########################################################################

CATEGORIES = {
    "agronomic_onset": {
        "onsetTadross": kernels_onset_agro.onsetTadross,
        "onsetAngola": kernels_onset_agro.onsetAngola,
        "onsetBotswana": kernels_onset_agro.onsetBotswana,
        "onsetEswatini": kernels_onset_agro.onsetEswatini,
        "onsetMadagascar": kernels_onset_agro.onsetMadagascar,
        "onsetMalawi": kernels_onset_agro.onsetMalawi,
        "onsetMozambique": kernels_onset_agro.onsetMozambique,
        "onsetNamibia": kernels_onset_agro.onsetNamibia,
        "onsetSouthAfrica": kernels_onset_agro.onsetSouthAfrica,
        "onsetTanzania": kernels_onset_agro.onsetTanzania,
        "onsetZambia": kernels_onset_agro.onsetZambia,
        "onsetZimbabwe": kernels_onset_agro.onsetZimbabwe,
    },
    "accum_onset": {
        "onsetAccum": kernels_onset_accum.onsetAccum,
    },
    "dwtp_onset": {
        "onsetDWTP": kernels_onset_dwtp.onsetDWTP,
    }

}




# settings that users should not normally change. Values in dictionaries/deep_config.json override these.
DEFAULT_SETTINGS = {
    "fractionCpus": 0.5,
    "onsetAnchorMonth": {"summer": 10, "winter": 3},   # first month of the season (dry season)
    "onsetRegimeThreshold": 0.667,                    # share of annual rainfall in Oct-Mar (summer) or Apr-Sep (winter)
    "onsetWindowDays": {"summer": 123, "winter": 153},   # 1 Oct-31 Jan, 1 Mar-31 Jul
    "accumWindowDays": 365,
    "accumOnsetDays": 182,
    "accumDemiseDays": 182,
    "accumCutoff": 18,
    "dwtpFilterWindow": 60, 
    "dwtpMinLength": 30, 
    "dwtpMaxSeasons": 2,
}


def loadSettings(config=None):
    """Settings from DEFAULT_SETTINGS, overridden by values in the run config
    (from the GUI or the json file) for keys that exist in DEFAULT_SETTINGS."""
    if config is None:
        config = getattr(gl, "config", None) or {}
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    for key, value in config.items():
        if key not in settings:
            continue
        if isinstance(settings[key], dict) and isinstance(value, dict):
            settings[key].update(value)   # e.g. only "summer" given: "winter" keeps its default
        else:
            settings[key] = value
    return settings



def describe(func):
    doc = inspect.getdoc(func)
    return " ".join(doc.split()) if doc else ""
    

# dispatchers #######################################################################

def preprocess(category, data, config, settings):
    if category == "agronomic_onset":
        return preAgroOnset(data, config, settings)
    elif category == "accum_onset":
        return preAccumOnset(data, config, settings)
    elif category == "dwtp_onset":
        return preDWTPOnset(data, config, settings)
        

def calculate(category, inputs, func, n_jobs, settings):
    if category == "agronomic_onset":
        return calcAgroOnset(inputs, func, n_jobs, settings)
    elif category == "accum_onset":
        return calcAccumOnset(inputs, func, n_jobs, settings)
    elif category == "dwtp_onset":
        return calcDWTPOnset(inputs, func, n_jobs, settings)


def postprocess(category, result, settings):
    if category == "agronomic_onset":
        return postAgroOnset(result, gl.config)
    elif category == "accum_onset":
        return postAccumOnset(result, gl.config)
    elif category == "dwtp_onset":
        return postDWTPOnset(result, gl.config)

def writeoutput(category, result, meta, outDir, obsdatasetcode, productname, description, settings):
    if category == "agronomic_onset":
        writeAgroOnsetOutput(result, meta, outDir / "{}_{}".format(obsdatasetcode, productname), description, settings)
        if gl.config.get("plotMaps"):
            plotLocationOutput(result, meta, outDir / "{}_{}".format(obsdatasetcode, productname), description, settings)   
    elif category == "accum_onset":
        writeAccumOnsetOutput(result, meta, outDir / "{}_{}".format(obsdatasetcode, productname), description, settings)
        if gl.config.get("plotMaps"):
            plotLocationOutput(result, meta, outDir / "{}_{}".format(obsdatasetcode, productname), description, settings)   
    elif category == "dwtp_onset":
        writeDWTPOnsetOutput(result, meta, outDir / "{}_{}".format(obsdatasetcode, productname), description, settings)



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
                writeoutput(category,results,meta,outDir, config["obsDsetCode"], key, (describe(products[key])), settings)
                
            except Exception as e:
                showMessage("{} could not be calculated. Full error: {}".format(key, e), "ERROR")
                success = False

    if config.get("diagAll"):
        runAllDiagnostics(config, settings, data, meta, outDir, config["obsDsetCode"])

    if success:
        showMessage("All done!", "SUCCESS")
    else:
        showMessage("Finished with errors, see log above", "ERROR")
    return success


if __name__ == "__main__":
    computeProductsObsNoGui(readConfigFile(sys.argv[1]))
