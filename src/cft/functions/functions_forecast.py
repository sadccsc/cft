import os
import json
import re
import inspect
import unicodedata

import numpy as np
import pandas as pd
import geopandas as gpd
import xarray as xr
import rioxarray

from pathlib import Path

import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import matplotlib.colors as colors

from scipy.interpolate import interp1d
from scipy.stats import norm
from scipy.ndimage import gaussian_filter
from shapely.validation import explain_validity

from rasterio.enums import Resampling
from rasterstats import zonal_stats

from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.preprocessing import StandardScaler
from sklearn.cross_decomposition import CCA
from sklearn.decomposition import PCA
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.tree import DecisionTreeRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import cross_val_predict, KFold, LeaveOneOut
from sklearn.metrics import mean_absolute_error, mean_squared_error, roc_auc_score, mean_absolute_percentage_error, explained_variance_score

import warnings
warnings.filterwarnings("ignore")

from cft import gl


months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

seasonmonths={
    "Jan":[1],
    "Feb":[2],
    "Mar":[3],
    "Apr":[4],
    "May":[5],
    "Jun":[6],
    "Jul":[7],
    "Aug":[8],
    "Sep":[9],
    "Oct":[10],
    "Nov":[11],
    "Dec":[12],
    "Jan-Mar":[1,2,3],
    "Feb-Apr":[2,3,4],
    "Mar-May":[3,4,5],
    "Apr-Jun":[4,5,6],
    "May-Jul":[5,6,7],
    "Jun-Aug":[6,7,8],
    "Jul-Sep":[7,8,9],
    "Aug-Oct":[8,9,10],
    "Sep-Nov":[9,10,11],
    "Oct-Dec":[10,11,12],
    "Nov-Jan":[11,12,1],
    "Dec-Feb":[12,1,2]
}

regressors = {
        "OLS": LinearRegression,
        'Lasso': Lasso,
        'Ridge': Ridge,
        'RF': RandomForestRegressor,
        'MLP': MLPRegressor,
        'Trees': DecisionTreeRegressor,
    }


terc2num={"below":0,"normal":1,"above":2}
num2terc={0: "below",1:"normal",2:"above"}

cem2num={"below":0,"normal-to-below":1,"normal-to-above":2,"above":3}
num2cem={0:"below",1:"normal-to-below",2:"normal-to-above",3:"above"}


tgtSeass=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan-Mar","Feb-Apr","Mar-May","Apr-Jun","May-Jul","Jun-Aug","Jul-Sep","Aug-Oct","Sep-Nov","Oct-Dec","Nov-Jan","Dec-Feb"]

timeAggregations={"sum","mean"}
predictandCats=["rainfall","temperature", "other"]

crossvalidators = {
        "KF": KFold,
        'LOO': LeaveOneOut,
}






def computeModelNoGui(config):
    """Run the full forecast pipeline for one predictor/predictand pair, without a GUI.

    Reads the predictor and predictand data described in ``config``, aligns them
    to a common hindcast period, optionally aggregates the predictand to zones,
    fits the configured statistical model under cross-validation, and produces
    deterministic, probabilistic, tercile, and 4-category (CEM) forecasts along
    with cross-validated skill scores. All results - forecast/hindcast data,
    skill scores, and diagnostic plots - are written to disk under
    ``config['rootDir']``; this function does not return the forecast data itself.

    On any failure (bad input data, incompatible predictor/pre-processor
    combination, etc.) an error is logged via ``showMessage`` and the function
    returns early.

    Args:
        config (dict): Forecast configuration. Expected keys:

            * ``rootDir`` (str): base directory under which output is written.
            * ``predictorYear`` (int): year of the predictor data to use.
            * ``predictorMonth`` (str): three-letter month the predictor is
              issued/observed in, e.g. ``'Jul'``.
            * ``fcstTargetSeas`` (str): target season for the forecast, e.g.
              ``'Aug-Oct'`` (or a single three-letter month for monthly forecasts).
            * ``fcstTargetYear`` (int): year of the first month of the forecast target season.
            * ``climStartYr`` / ``climEndYr`` (int): first/last year of the
              climatological reference period used to compute anomalies and terciles.
            * ``predictorExtents`` (dict): bounding box for the predictor domain,
              with keys ``minLon``, ``maxLon``, ``minLat``, ``maxLat``.
            * ``predictorFileName`` (str): path to the predictor NetCDF or CSV file.
            * ``predictorVar`` (str): variable name identifying the predictor within that file.
            * ``predictorCode`` (str): variable name to be used in plotting figures
            * ``crossval`` (str): cross-validation method - ``'KF'`` (k-fold) or
              ``'LOO'`` (leave-one-out).
            * ``preproc`` (str): pre-processing approach - ``'PCR'``, ``'CCA'``,
              or ``'NONE'`` (only valid for a 1-D predictor).
            * ``regression`` (str): statistical model - one of ``'OLS'``,
              ``'Lasso'``, ``'Ridge'``, ``'RF'``, ``'MLP'``, ``'Trees'``.
            * ``timeAggregation`` (str): how the predictand is aggregated in time,
              ``'mean'`` or ``'sum'``.
            * ``predictandFileName`` (str): path to the predictand file (NetCDF
              for gridded data, CSV for station data).
            * ``predictandVar`` (str): predictand variable name.
            * ``predictandCategory`` (str): predictand type, e.g. ``'rainfall'``
              or ``'temperature'`` - affects color scales in plots.
            * ``predictandMissingValue`` (str): missing-value flag used in the
              predictand file, e.g. ``'-999'``.
            * ``zonesAggregate`` (bool): if True, aggregate the predictand to
              zones before forecasting.
            * ``zonesFile`` (str or None): path to a vector file of zone
              boundaries, required if ``zonesAggregate`` is True.
            * ``zonesAttribute`` (str): attribute in ``zonesFile`` used as the
              unique zone identifier.
            * ``regridPredictand`` (bool): whether to regrid the predictand onto a coarser grid
            * ``overlayFile`` (str): optional vector file (e.g. admin boundaries)
              overlaid on output maps; pass ``""`` for none.
            * ``plotMaps`` (bool): whether or not output maps are created

    Returns:
        bool or None: ``True`` if the forecast ran to completion and all output
        was written successfully. ``None`` if any step failed - check the log
        (via ``showMessage``) for the specific reason.

    Example:
        >>> config = {
        ...     'rootDir': '../test',
        ...     'predictorYear': 2026,
        ...     'predictorMonth': 'Jun',
        ...     'fcstTargetSeas': 'Aug-Oct',
        ...     'fcstTargetYear': 2026,
        ...     'climEndYr': 2015,
        ...     'climStartYr': 1994,
        ...     'predictorExtents': {'minLon': -180.0, 'maxLon': 180.0,
        ...                          'minLat': -60.0, 'maxLat': 60.0},
        ...     'predictorFileName': 'GPH850_System9_CDS_Jun_1981-2026.nc',
        ...     'predictorVar': 'z',
        ...     'predictorCode': 'z',
        ...     'crossval': 'KF',
        ...     'preproc': 'PCR',
        ...     'regression': 'OLS',
        ...     'timeAggregation': 'mean',
        ...     'predictandFileName': 'PRCP_CHIRPSp25_IRIDL_Aug-Oct_1981-2025.nc',
        ...     'predictandVar': 'prcp',
        ...     'predictandCategory': 'rainfall',
        ...     'predictandMissingValue': '-999',
        ...     'zonesFile': None,
        ...     'zonesAttribute': 'Name',
        ...     'zonesAggregate': False,
        ...     'regridPredictand': False,
        ...     'overlayFile': '',
        ...     'plotMaps': True,
        ... }
        >>> computeModelNoGui(config)
        True
    """

    gl.config=config

    #reading inputs
    readFunctionConfig()
    
    #checking inputs
    result=checkInputs()

    if result is None:
        showMessage("Check of input fields failed. Look above for errors, fix and try again.", "ERROR")
        return
 
    #derived variables
    
    #set target type 
    if gl.config["zonesAggregate"]:
        gl.targetType="zones"
    elif gl.config["predictandFileName"][-3:]=="csv":
        gl.targetType="points"
    else:
        gl.targetType="grid"
    
    if len(gl.config["fcstTargetSeas"])>3:
        gl.fcstBaseTime="seas"
    else:
        gl.fcstBaseTime="mon"
    
    #=======================================================================================================
    #reading data
     
    #determine lead time
    leadTime=getLeadTime()
        
    if leadTime is None:
        showMessage("Lead time could not be calculated, stopping early.", "ERROR")
        return
       
    #reading predictors data
    predictor,geoDataPredictor=readPredictor()
    if predictor is None:
        showMessage("Predictor could not be read, stopping early.", "ERROR")
        return
    
    #reading predictand data - this will calculate seasonal from monthly if needed.
    predictand0, geoData0=readPredictand()
    if predictand0 is None:
        showMessage("Predictand could not be read, stopping early.", "ERROR")
        return
            
    if np.max(predictand0)<0.01:
        showMessage(f"Predictand has values ranging between {np.min(predictand0)} and {np.max(predictand0)}. CFT cannot handle that, please rescale your data so that values have no more than 2 significant decimal digits", "ERROR")
        return
        
    #aggregating to zones if required
    if gl.config["zonesAggregate"]:
        showMessage("Aggregating data to zones read from {} ...".format(gl.config["zonesFile"]))
        
        zonesVector=gpd.read_file(gl.config["zonesFile"])
        
        showMessage("checking validity of data from {} ...".format(gl.config["zonesFile"]))
        
        check=checkPolyValidity(zonesVector)
        if not check:
            showMessage("Vector file {} fails the validity check indicating that it is likely corrupted.".format(zonesVector), "ERROR")
            return
        
        if not zonesVector[gl.config["zonesAttribute"]].is_unique:
            showMessage("Selected vector attribute in regions map contains identical values. These values have to be unique for each zone, please check the zones vector file or the attribute you selected. Stopping early.", "ERROR")
            return
        
        #retaining just the attribute as index
        zonesVector=zonesVector[[gl.config["zonesAttribute"], 'geometry']].set_index(gl.config["zonesAttribute"])
        
        # calling the aggregation function   
        predictand,geoData=aggregatePredictand(predictand0, geoData0, zonesVector)
            
        if predictand is None:
            showMessage("Predictand could not be aggregated to zones. Make sure there is overlap between predictand data and zones vector. Stopping early.", "ERROR")
            return
        
        #checking if result has data
        if predictand.dropna(axis=1).empty:
            showMessage("Predictand could not be aggregated to zones. Make sure there is overlap between predictand data and zones vector. Stopping early.", "ERROR")
            return
            
    else:
        zonesVector=None
        predictand=predictand0.copy()
        geoData=geoData0.copy()
    
    
    
    #reading overlay file
    overlayVector=None
    if gl.config["overlayFile"] != "":
        if os.path.exists(gl.config["overlayFile"]):
            overlayVector=gpd.read_file(gl.config["overlayFile"])
            
            
    #=======================================================================================================
    #preprocessing
            
    #defining target date for forecast. If seasonal - then this is the first month of the season.
    fcstTgtDate=pd.to_datetime("01 {} {}".format(gl.config['fcstTargetSeas'][0:3], gl.config['fcstTargetYear']))
    
    #finding overlap of predictand and predictor
    showMessage("Aligning predictor and predictand data...")
    predictandHcst,predictorHcst=getHcstData(predictand,predictor)

    novlpYears=predictandHcst.shape[0]

    if novlpYears<20:
        showMessage(f"Only {novlpYears} of overlap years between predictand and predictor. Minimum allowed is 20.", "ERROR")
        return None
 
    predictorFcst=getFcstData(predictor)
    if predictandHcst is None:
        showMessage("Hindcast data for predictand could not be derived, stopping early.", "ERROR")
        return
    
    
    #calculaing observed terciles
    #is there a need to do a strict control of overlap???
    result=getObsTerciles(predictand, predictandHcst)
    if result is None:
        showMessage("Terciles could not be calculated, stopping early.", "ERROR")
        return
            
    obsTercile,tercThresh=result
    
    
    #check for locations with too many identical values - forecast and skill measures cannot be derived for such locations
    max_counts = predictandHcst.apply(lambda col: col.value_counts().max())
    bad=max_counts>0.2*predictandHcst.shape[0]
    good=np.invert(bad)
    
    #listing bad locations
    if len(bad)>0:
        badnames=predictandHcst.loc[:,bad].columns
        for name in badnames:
            showMessage("cannot calculate forecast for {} - too many similar values in predictand".format(name), "NONCRITICAL")
            
    
    #removing bad locations
    predictandHcst=predictandHcst.loc[:,good]
    tercThresh=tercThresh.loc[:,good]
    obsTercile=obsTercile.loc[:,good]
    
    
    #=======================================================================================================
    #setting up forecast
    
    #setting up cross-validation
    cvkwargs=gl.crossvalidator_config[gl.config['crossval']][1]
    cv=crossvalidators[gl.config['crossval']](**cvkwargs)
    
    #arguments for regressor
    kwargs=gl.regressor_config[gl.config['regression']][1]
    
    #arguments for preprocessor
    args=gl.preprocessor_config[gl.config['preproc']][1]
        
    #checking compatibility between data and selected regressor
    if gl.config['preproc']=="NONE":
        if predictorHcst.shape[1]==1:
            regressor = StdRegressor(regressor_name=gl.config['regression'], **args, **kwargs)
        else:
            #2-D predictor, no need to PCR or CCA
            showMessage("2-D predictor, but no preprocessing requested. Please change pre-processor to either PCR or CCA", "ERROR")
            return
    else:
        if predictorHcst.shape[1]==1:
            showMessage("1-D predictor, and neither PCR nor CCA are applicable. Please change pre-processor to 'No preprocessing'", "ERROR")
            #2-D predictor, no need to PCR or CCA
            return    

    
    #setting up regressor
    if gl.config['preproc']=="PCR":
        #regession model
        regressor = PCRegressor(regressor_name=gl.config['regression'], **args, **kwargs)
        
    if gl.config['preproc']=="CCA":
        
        regressor = CCARegressor(regressor_name=gl.config['regression'],**args, **kwargs)
        #return
    
    #=======================================================================================================
    #setting up output directory structure
    
    showMessage("Setting up directories to write to...")        
    forecastID="{}_{}".format(gl.predictorDate.strftime("%Y%m"), gl.config['fcstTargetSeas'])
    
    predictorCode=Path(gl.config["predictorFileName"]).stem
    
    # this is directory where all output for a given forecast will be written
    # Note - there is no signature of predictand in the structure of this directory, 
    # so if predictand changes, output will be written into the same directory. 
    forecastDir=Path(gl.config['rootDir'], forecastID, predictorCode,gl.targetType, "{}_{}_{}".format(gl.config["preproc"],gl.config["regression"],gl.config["crossval"]))
    
    #subdirectories for different type of output
    mapsDir=Path(forecastDir, "maps")
    timeseriesDir=Path(forecastDir, "timeseries")
    outputDir=Path(forecastDir, "output")
    diagsDir=Path(forecastDir, "diagnostics")
    
    dirs={"output":outputDir,
          "maps":mapsDir,
          "timeseries":timeseriesDir,
          "diagnostics":diagsDir}
    
    #creating them
    for adir in dirs.keys():
        if not os.path.exists(dirs[adir]):
            showMessage("{} directory {} does not exist. creating...".format(adir, dirs[adir]))
            os.makedirs(dirs[adir])
        else:
            showMessage("{} will be written to {}".format(adir, dirs[adir]), "INFO")
            

    

        
    #=======================================================================================================
    # calculating forecast
    
    # cross-validated hindcast
    showMessage("Calculating cross-validated hindcast...")
    cvHcst = cross_val_predict(regressor,predictorHcst,  predictandHcst, cv=cv)
    
    # output of the above is a plain numpy array, needs to be converted to pandas
    cvHcst=pd.DataFrame(cvHcst, index=predictandHcst.index, columns=predictandHcst.columns)
    
    # actual prediction - forecast
    showMessage("Calculating deteriministic forecast...")
    regressor.fit(predictorHcst,  predictandHcst)
    
    # output of regression is deterministic forecast
    detFcst=regressor.predict(predictorFcst)
    detFcst=pd.DataFrame(detFcst, index=[fcstTgtDate], columns=predictandHcst.columns)
    
    # hindcast based on full model - for diagnostics only - called est for estimated, 
    # to avoid confusion actual forecast 
    estHcst=regressor.predict(predictorHcst)
    estHcst=pd.DataFrame(estHcst, index=predictandHcst.index, columns=predictandHcst.columns)
    
    #extract reference period from predictand data
    refData=predictand[str(gl.config["climStartYr"]):str(gl.config["climEndYr"])]
    
    #this adds anomalies to the dataframe
    detFcst=getFcstAnomalies(detFcst,refData)
    
    # calculate anomalies on hindcast data
    # for "full model" hindcast
    estHcst=getFcstAnomalies(estHcst,refData)
    
    # for cross-validated hindcast
    cvHcst=getFcstAnomalies(cvHcst,refData)
    
    
    #deriving probabilistic prediction
    showMessage("Calculating probabilistic hindcast and forecast using error variance...")
    
    #this one uses cross-validated hindcast for error
    dist="normal"
    result=probabilisticForecastCalibrated(cvHcst["value"], predictandHcst,detFcst["value"],tercThresh, dist=dist)
    
    if result is None:
        showMessage("Probabilistic forecast could not be calculated", "ERROR")
        return
    
    probFcst,probHcst,calibHcstCdf=result    
        
    #tercile forecast
    showMessage("Calculating tercile forecast (highest probability category)")
    
    # forecast
    tercFcst=getTercCategory(probFcst)
    
    # and hindcast
    tercHcst=getTercCategory(probHcst)
    
    #CEM categories
    showMessage("Calculating CEM categories")
    
    #forecast
    cemFcst=getCemCategory(probFcst)
    
    #hindcast
    cemHcst=getCemCategory(probHcst)
    
    
    #calculating skill
    showMessage("Calculating skill scores...")
    scores=getSkill(probHcst,cvHcst["value"],predictandHcst,obsTercile)    
    if scores is None:
        showMessage("Skill could not be calculated", "ERROR")
        return
    
    
    #saving data
    showMessage("Plotting forecast maps and saving output files...")    
    #all dataframes have two levels of column multiindex 
    #cvHcst.unstack().to_xarray().transpose("time","lat","lon").to_dataset(name=gl.config['predictandVar'])
    
    if gl.targetType=="grid":
        #these are for plotting maps
        detfcst_plot=detFcst.stack(level=["lat","lon"],future_stack=True).droplevel(0).T
        probfcst_plot=probFcst.stack(level=["lat","lon"],future_stack=True).droplevel(0).T
        tercfcst_plot=tercFcst.stack(level=["lat","lon"],future_stack=True).droplevel(0).T
        cemfcst_plot=cemFcst.stack(level=["lat","lon"],future_stack=True).droplevel(0).T
        scores_plot=scores.copy()
        
        #these are for writing
        probfcst_write=probFcst.stack(level=["lat","lon"], future_stack=True).to_xarray().sortby("lat").sortby("lon")
        probhcst_write=probHcst.stack(level=["lat","lon"], future_stack=True).to_xarray().sortby("lat").sortby("lon")
        tercfcst_write=tercFcst.stack(level=["lat","lon"], future_stack=True).to_xarray().sortby("lat").sortby("lon")
        cemhcst_write=cemHcst.stack(level=["lat","lon"], future_stack=True).to_xarray().sortby("lat").sortby("lon")
        detfcst_write=detFcst.stack(level=["lat","lon"], future_stack=True).to_xarray().sortby("lat").sortby("lon")
        dethcst_write=cvHcst.stack(level=["lat","lon"], future_stack=True).to_xarray().sortby("lat").sortby("lon")
        scores_write=scores.T.to_xarray().sortby("lat").sortby("lon")
        fileExtension="nc"
    else:
        #these are for plotting maps
        detfcst_plot=detFcst.stack(future_stack=True).droplevel(0).T
        probfcst_plot=probFcst.stack(future_stack=True).droplevel(0).T
        tercfcst_plot=tercFcst.stack(future_stack=True).droplevel(0).T
        cemfcst_plot=cemFcst.stack(future_stack=True).droplevel(0).T
        scores_plot=scores.copy()
        
        #these are for writing
        detfcst_write=detfcst_plot.copy()
        probfcst_write=probfcst_plot.copy()
        tercfcst_write=tercfcst_plot.copy()
        cemfcst_write=cemfcst_plot.copy()
        dethcst_write=cvHcst.copy()
        probhcst_write=probHcst.copy()
        scores_write=scores.copy()
        fileExtension="csv"
        
    showMessage("Writing output files...")
    outputFile=Path(outputDir, "{}_deterministic-fcst_{}.{}".format(gl.config['predictandVar'], forecastID,fileExtension))
    writeOutput(np.round(detfcst_write,2), outputFile)
    
    outputFile=Path(outputDir, "{}_probabilistic-fcst_{}.{}".format(gl.config['predictandVar'], forecastID,fileExtension))
    writeOutput(np.round(probfcst_write,2),outputFile)
    
    outputFile=Path(outputDir, "{}_skill_{}.{}".format(gl.config['predictandVar'], forecastID,fileExtension))
    writeOutput(scores_write, outputFile)
    
    outputFile=Path(outputDir, "{}_deterministic-hcst_{}.{}".format(gl.config['predictandVar'], forecastID,fileExtension))
    writeOutput(np.round(dethcst_write,2),outputFile)
    
    outputFile=Path(outputDir, "{}_probabilistic-hcst_{}.{}".format(gl.config['predictandVar'], forecastID,fileExtension))
    writeOutput(np.round(probhcst_write,2),outputFile)
    
    
    showMessage("Plotting maps...")
    
    annotation="Forecast for: {} {}".format(gl.config['fcstTargetSeas'], gl.config['fcstTargetYear'])
    annotation+="\nPredictors from: {} {}".format(gl.config['predictorMonth'], gl.config['predictorYear'])
    annotation+="\nPredictor: {}".format(Path(gl.config["predictorFileName"]).stem)
    annotation+="\nPredictand: {}".format(Path(gl.config["predictandFileName"]).stem)
    annotation+="\nClimatological period: {}-{}".format(gl.config['climStartYr'], gl.config['climEndYr'])
    
    
    #maskedscores=getSkillMask(scores_plot, scores_plot)

    if gl.config["plotMaps"]:
        showMessage("Plotting tercile probabilities map...")    
        #plotting
        plotTercileProbMap(probFcst, predictandHcst, geoData, mapsDir, forecastID, annotation, overlayVector)

        showMessage("Plotting smooth tercile probabilities map...")
        #return probFcst, predictandHcst, geoData, mapsDir, forecastID, annotation, overlayVector

        plotSmoothTercileProbMap(probFcst, predictandHcst, geoData, mapsDir, forecastID, annotation, overlayVector, gl.deep_config["sigmaSmooth"], gl.deep_config["enhanceSmooth"])


        showMessage("Plotting forecast...")

        plotMaps(detfcst_plot, geoData, mapsDir, forecastID, zonesVector, annotation,overlayVector)
        plotMaps(probfcst_plot, geoData, mapsDir, forecastID, zonesVector, annotation, overlayVector)
        plotMaps(cemfcst_plot, geoData, mapsDir, forecastID, zonesVector, annotation, overlayVector)
        plotMaps(tercfcst_plot, geoData, mapsDir, forecastID, zonesVector, annotation, overlayVector)
        
        
        showMessage("Plotting skill maps...")    
        #plotting skill scores
        plotMaps(scores_plot, geoData, mapsDir, forecastID, zonesVector, annotation, overlayVector)
        
        
        showMessage("Plotting time series plots...") 
        plotTimeSeries(cvHcst["value"],predictandHcst, detFcst, tercThresh, timeseriesDir, forecastID, annotation)
        
        
        showMessage("Plotting preprocessing diagnostics...")
        if gl.config['preproc']=="PCR":
            plotDiagsPCR(regressor, predictorHcst, predictandHcst, geoData, diagsDir, forecastID, annotation)
        
        if gl.config['preproc']=="CCA":
            plotDiagsCCA(regressor, predictorHcst, predictandHcst, geoData, diagsDir, forecastID, annotation)
        
        showMessage("Plotting regression diagnostics...")
        plotDiagsRegression(predictandHcst, cvHcst, estHcst, tercThresh, detFcst, diagsDir, forecastID, annotation)
        
        showMessage("Plotting calibration diagnostics...")
        plotCalibDiags(calibHcstCdf, predictandHcst, cvHcst["value"], diagsDir, forecastID)
    else:
        showMessage("skipping plotting maps and diagnostics, as requested")
        
    showMessage("All done!", "SUCCESS")
    showMessage("Inspect log above for potential errors!", "SUCCESS")    
    showMessage("All output written to {}".format(forecastDir), "SUCCESS")    
        
    return True





def readFunctionConfig():
    baseDir = Path(__file__).resolve().parent.parent
    deep_config_file=Path(baseDir, "dictionaries", "deep_config.json")
    crossvalidator_config_file=Path(baseDir, "dictionaries", "crossvalidator_config.json")
    regressor_config_file=Path(baseDir, "dictionaries", "regressor_config.json")
    preprocessor_config_file=Path(baseDir, "dictionaries", "preprocessor_config.json")
    
    gl.crossvalidator_config=readConfigFile(crossvalidator_config_file)
    if gl.crossvalidator_config is None:
        return

    gl.regressor_config=readConfigFile(regressor_config_file)
    if gl.regressor_config is None:
        return

    gl.preprocessor_config=readConfigFile(preprocessor_config_file)
    if gl.preprocessor_config is None:
        return

    gl.deep_config=readConfigFile(deep_config_file)
    if gl.deep_config is None:
        return
    
    return True


    
def readConfigFile(file):
    showMessage("Reading config file {}".format(file))
    if not os.path.exists(file):
        showMessage("Config file {} is missing. Please download the file from github and put it in the right folder.".format(file), "ERROR")
        return
    else:
        try:
            with open(file, "r") as inpf:
                config=json.load(inpf)
        except:
            showMessage("Config file {} appears to be corrupted. Please download the file from github and put it in the right folder.".format(file), "ERROR")
            return
        return config



def showMessage(message,type="RUNTIME"):
    msgColors={"ERROR": "red",
           "INFO":"grey",
           "RUNTIME":"grey",
           "NONCRITICAL":"red",
           "SUCCESS":"green"
          }
    try:
        color=msgColors[type]
        outmessage = "<pre><font color={}>{}</font></pre>".format(color, message)
        gl.window.log_signal.emit(outmessage)
    except:
        if type in ["NONCRITICAL","ERROR","INFO"]:
            message = f"{type}: {message})"
        print(message)

    
def month2int(_str):
    #converts month string to non-pythonic integer month number
    return (np.where(np.array(months)==_str)[0][0])+1    
    
    
    
def readPredictorCsv(csvfile):
    
    dat=pd.read_csv(csvfile, header=0, index_col=0, parse_dates=True)

    datdates=dat.index
    firstdatdate=datdates.strftime('%Y-%m-%d')[0]
    lastdatdate=datdates.strftime('%Y-%m-%d')[-1]

    showMessage("Predictor file covers period of: {} to {}".format(firstdatdate,lastdatdate),"RUNTIME")

    #check against the forecast date
    firstdatyear=datdates.year[0]
    lastdatyear=datdates.year[-1]


    if gl.config["climEndYr"]>lastdatyear or gl.config["climStartYr"]<firstdatyear:
        showMessage("Climatological period {}-{} extends beyond period covered by data {}-{}".format(gl.config["climStartYr"],gl.config["climEndYr"],firstdatyear,lastdatyear), "ERROR")
        return

    newtime=pd.to_datetime([x.replace(day=1) for x in pd.to_datetime(dat.index)])
    dat.index=newtime
    
    showMessage("Successfuly read data from {}\n".format(csvfile), "SUCCESS")
    
    return dat
    

    
    
def readPredictandCsv(csvfile):
    ds=pd.read_csv(csvfile)
    
    #main test is number of unique values in first colums
    test1=len(np.unique(ds.iloc[:,0]))<ds.shape[0]
    test2=ds.shape[1]==16
    
    if test1 and test2:
        msg="Detected file with 12 months of data in each row, i.e. CFT format."
        showMessage(msg, "RUNTIME")
        csvformat="byMonth" #months of year in columns
    else:
        msg="Detected file with time series of data in each column."
        showMessage(msg, "RUNTIME")
        csvformat="byLoc" #locations in columns
    
    if csvformat=="byMonth":
        #ID,Lat,Lon,Year,Jan...Dec
        if ("Year" not in ds.keys()):
            msg="Data should contain column named Year. Data file {} does not. Please inspect the data file.".format(csvfile)
            showMessage(msg, "ERROR")
            return None,None 
        if "ID" not in ds.keys():
            msg="Data should contain column named ID. Data file {} does not.Please inspect the data file.".format(csvfile)
            showMessage(msg, "ERROR")
            return None,None

        nans=pd.isnull(ds.ID)
        if nans.any():
            badrows=np.where(nans)[0]+1
            badrows=",".join(list(badrows.astype(str)))
            showMessage("CSV file contains rows {} with no data. Please edit the {} file with text editor (NOT Excel!) to remove these rows".format(badrows, csvfile), "ERROR")
            return None,None

        ds.ID=ds.ID.astype(str)

        locs=np.unique(ds.ID.astype(str))
        alldata=[]
        lats=[]
        lons=[]
        for name in locs:
            sel=ds.ID==name
            lats=lats+[np.unique(ds[sel].Lat.values)[0]]
            lons=lons+[np.unique(ds[sel].Lon.values)[0]]
            years=np.unique(ds[sel].Year.values)
            firstyear,lastyear=(np.min(years),np.max(years))
            dat=ds[sel].iloc[:,4:]
                        
            #check if data contains strings
    #       data=data.applymap(self.tofloat)
            dat=dat.values.flatten()
            try:
                dat=dat.astype(float)
            except:
                showMessage("Data for {} contains entries that are of string (character) type which cannot be converted to numerical values. There should be no non-numeric characters in the data. Please edit the {} file so that it is formatted correctly".format(name, csvfile), "ERROR")
                return
            
            index=pd.date_range("{}-01-01".format(int(firstyear)),"{}-12-31".format(int(lastyear)),freq="ME")
            try:
                dat=pd.DataFrame(dat.reshape(-1,1), index=index,columns=[name])
            except:
                msg="data for {} contains {} months, expected {} months - data should cover continuous period from Jan {} to Dec {} with entries for every month in that period".format(name, len(index),len(dat), firstyear, lastyear)
                showMessage(msg, "ERROR")
                return                 

            alldata.append(dat)

        #dat is pandas dataframe
        dat=pd.concat(alldata, axis=1)

    else:
        
        #rereading the file in appropriate way
        dat=pd.read_csv(csvfile, header=[0,1,2], index_col=0, parse_dates=True)
        
        locs=dat.columns.get_level_values(0)
        
        latVar,lonVar=None,None
        for x in ["Lat","lat","Latitude","latitude"]:
            if x in dat.columns.names:
                latVar=x
                lats=dat.columns.get_level_values(latVar)
                dat=dat.droplevel(latVar, axis=1)
                
        for x in ["Lon","lon","Longitude","longitude"]:
            if x in dat.columns.names:
                lonVar=x
                lons=dat.columns.get_level_values(lonVar)
                dat=dat.droplevel(lonVar, axis=1)
                
        dat.columns.name=None
        
        if latVar is None:
            msg="Data should contain values for Latitude of stations in one of the top three rows, marked by word 'Lat' in the first column of data. {} does not. Please inspect the data file.".format(csvfile)
            showMessage(msg, "ERROR")
            return None,None
        
        if lonVar is None:
            msg="Data should contain values for longitude of stations in one of the top three rows, marked by word 'Lon' in the first column of data. {} does not. Please inspect the data file.".format(csvfile)
            showMessage(msg, "ERROR")
            return None,None
            
    if gl.config["predictandMissingValue"] != "":
        dat[dat==gl.config["predictandMissingValue"]]=np.nan

    #check only if rainfall
    if  gl.config["predictandCategory"] =='rainfall':
        dat[dat<0]=np.nan

    nancount=np.sum(np.isnan(dat), axis=0).sum()

    if nancount>0:
        nanperc=np.round(np.int32(nancount)/np.prod(dat.shape)*100,1)
        showMessage("There are {} missing data points, which is approx {}% of all data points in this dataset. Check if this is what is expected".format(nancount,nanperc), "NONCRITICAL")                  

    #creating geodataframe with all data
    geoData=gpd.GeoDataFrame(geometry=gpd.points_from_xy(lons, lats), crs="EPSG:4326", index=locs)
                            
    datdates=dat.index
    firstdatdate=datdates.strftime('%Y-%m-%d')[0]
    lastdatdate=datdates.strftime('%Y-%m-%d')[-1]

    showMessage("Observed file covers period of: {} to {}".format(firstdatdate,lastdatdate),"RUNTIME")

    #check against the forecast date
    firstdatyear=datdates.year[0]
    lastdatyear=datdates.year[-1]
        
    if gl.config["climEndYr"]>lastdatyear or gl.config["climStartYr"]<firstdatyear:
        showMessage("Climatological period {}-{} extends beyond period covered by data {}-{}".format(gl.config["climStartYr"],gl.config["climEndYr"],firstdatyear,lastdatyear), "ERROR")
        return None,None

    #making sure dates start on the first of the month    
    newtime=pd.to_datetime([x.replace(day=1) for x in pd.to_datetime(dat.index)])
    dat.index=newtime
    
    showMessage("Successfuly read data from {}\n".format(csvfile), "SUCCESS")
    
    return dat, geoData
        





def readPredictor():
    
    predFile=gl.config["predictorFileName"]
    predVar=gl.config["predictorVar"]
    predCode=gl.config["predictorCode"]
    
    if predFile=="":
        showMessage("predictor file not defined","ERROR")
        return None,None

    showMessage("reading predictor from {}...".format(predFile), "INFO")
    if not os.path.exists(predFile):
        showMessage("file does not exist","ERROR")
        return None,None

    showMessage("\tfile exists, reading...")

    #just to make sure...

    ext=predFile.split(".")[-1]
    if ext not in ["csv", "nc"]:
        showMessage("only .csv and .nc files accepted, got {}".format(ext),"ERROR")
        return None,None

    srcMonthName=gl.config['predictorMonth']
    srcMonth=month2int(srcMonthName)
    srcYear=gl.config['predictorYear']

    #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    #this is where code is different for csv and netcdf formats
    if ext=="nc":
        predictor=readNetcdf(predFile, predVar)
        if predictor is None:
            return None,None


        if "lead_time" in predictor.dims:
            isForecast=True
            showMessage("lead_time dimension present, processed as forecast predictor")
        else:
            isForecast=False
            showMessage("lead_time dimension not found, processing as observed predictor")
            
        #predictor is xarray
        predictor=predictor.sortby('lon').sortby("lat")
        
        predictor=predictor.sel(lat=slice(gl.config["predictorExtents"]["minLat"],gl.config["predictorExtents"]["maxLat"]), lon=slice(gl.config["predictorExtents"]["minLon"],gl.config["predictorExtents"]["maxLon"]) )

        if isForecast:
            leadTime=getLeadTime()
            #check if forecast file is indeed from the init month
            firstdatamonth=predictor.time.dt.month.data[0]
            
            if firstdatamonth!=srcMonth:
                showMessage(f"File should start on the requested initialization month, which is {srcMonthName}. File starts in {months[firstdatamonth-1]}","ERROR")
                return None,None

            #making sure requested lead_time is in data
            leadtimes=np.ceil(predictor.lead_time.data).astype(int)
            predictor["lead_time"]=leadtimes
            
            #resampling if necessary
            if gl.fcstBaseTime=="seas":
                lastleadTime=leadTime+2
            else:
                lastleadTime=leadTime
            predictor=predictor.sel(lead_time=slice(leadTime, lastleadTime)).mean("lead_time")
                            
        else:
            #making sure requested forecast month is in the data
            # for observed predictor it should be one month behind the forecast srcMonth
            obssrcMonth = (srcMonth - 2) % 12 + 1
            obssrcMonthName=months[obssrcMonth-1]
            if not obssrcMonth in predictor.time.dt.month:
                availmonths=[months[x-1] for x in np.unique(predictor.time.dt.month)]
                showMessage(f"file does not contain data for requested month. Observed predictor for forecast issued in {srcMonthName} should be from {obssrcMonthName}. got {availmonths}","ERROR")
                return None,None
            
            #selecting this month    
            predictor=predictor.sel(time=predictor.time.dt.month==obssrcMonth)

            #aligning predictor data with forecast month - adding one month
            predictor["time"]=pd.to_datetime(predictor.time.data)+pd.offsets.MonthBegin(1)


        #processing for both forecast and observed

        #by this time this should be just time,lat,lon - so, selecting the first time step
        geodata=predictor[0,:]
        
        #preparing to convert xarray to pandas
        predictor=predictor.stack(location=("lat", "lon"))
        
        #dropping nans alon location dimension
        predictor=predictor.dropna("location")

        #converting to pandas
        predictor=predictor.to_pandas()

    else:
        isForecast=False
        predictor=readPredictorCsv(predFile)
        geodata=None
        
    if predictor is None:
        return None,None
    
    datdates=predictor.index
    firstdatdate=datdates.strftime('%Y-%m-%d')[0]
    lastdatdate=datdates.strftime('%Y-%m-%d')[-1]

    showMessage("Predictor file covers period of: {} to {}".format(firstdatdate,lastdatdate),"RUNTIME")

    firstdatyear=datdates.year[0]
    lastdatyear=datdates.year[-1]

    #check if covers climatological period
    if gl.config["climEndYr"]>lastdatyear or gl.config["climStartYr"]<firstdatyear:
        showMessage("Climatological period {}-{} extends beyond period covered by data {}-{}".format(gl.config["climStartYr"],gl.config["climEndYr"],firstdatyear,lastdatyear), "ERROR")
        return None,None
    
    #check if value for the forecast year is in data
    if not gl.predictorDate in datdates:
        showMessage("Predictor data do not include forecast date {}".format(gl.predictorDate.strftime("%b %Y")), "ERROR")
        return None,None
    predictor=predictor.astype("float")
    
    showMessage("done\n", "INFO")
    return predictor,geodata








def readPredictand():
    predictandFile=gl.config["predictandFileName"]
    if predictandFile=="":
        showMessage("predictand file not defined","ERROR")
        return None,None
        
    showMessage("Reading predictand from {}...".format(predictandFile), "INFO")
    if not os.path.exists(predictandFile):
        showMessage("file does not exist","ERROR")
        return None,None
    
    showMessage("\tfile exists, reading...")
    
    #just to make sure...

    ext=predictandFile.split(".")[-1]
    if ext not in ["csv", "nc"]:
        showMessage("only .csv and .nc files accepted, got {}".format(ext),"ERROR")
        return None,None

        
    tgtSeason=gl.config['fcstTargetSeas']
    tgtMonths=seasonmonths[tgtSeason]
    firstTgtMonth=tgtMonths[0]
    firstTgtMonthName=months[firstTgtMonth-1]

    
    #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    #this is where code is different for csv and netcdf formats
    if ext=="nc":
        
        predictandVar=gl.config["predictandVar"]
        if predictandVar=="":
            showMessage("predictand variable not defined","ERROR")
            return None,None

            
        predictand=readNetcdf(predictandFile, predictandVar) #this returns xarray
        if predictand is None:
            showMessage("Could not read requested variable from file","ERROR")
            return None,None


        if "lead_time" in predictand.dims:
            showMessage("Predictand should not have lead time dimension. You provided wrong file","ERROR")
            return None,None
        
        geodata=predictand[0,:]
        
        if gl.config["regridPredictand"]:
            
            showMessage("Regridding predictand to {} deg grid".format(gl.deep_config["gridSize"]))
            
            lats=geodata.lat
            lons=geodata.lon
            
            #check if target resolution is higher than data to avoid downsampling
            
            dataGridSize=lats[1]-lats[0]
            if dataGridSize>gl.deep_config["gridSize"]:
                showMessage("Data grid is {} deg, requested grid is {} deg. Skipping regridding to avoid downsampling".format(dataGridSize, gl.deep_config["gridSize"]))
            else:
                #ok, let's regrid
                
                minlat=np.floor(np.min(lats.data))
                maxlat=np.ceil(np.max(lats.data))
                numlat=int((maxlat-minlat)/gl.deep_config["gridSize"])+1

                minlon=np.floor(np.min(lons.data))
                maxlon=np.ceil(np.max(lons.data))
                numlon=int((maxlon-minlon)/gl.deep_config["gridSize"])+1

                new_lon = np.linspace(minlon, maxlon, numlon)
                new_lat = np.linspace(minlat, maxlat, numlat)

                target = xr.Dataset(coords={"y": new_lat, "x": new_lon}).rio.write_crs("epsg:4326")

                predictand=predictand.rio.write_crs("epsg:4326")
                predictand.rio.write_nodata(np.nan, inplace=True)
                predictand=predictand.rio.reproject_match(target,resampling=Resampling.bilinear)
                predictand=predictand.rename({"x":"lon", "y":"lat"})
            
        #preparing to convert xarray to pandas
        predictand=predictand.stack(location=("lat", "lon"))
        
        #check for time steps in predictor, i.e. if predictor month was not wrongly selected by any chance.
        #dropping nans alon location dimension
        predictand=predictand.dropna("location")
        
        #converting to pandas
        predictand=predictand.to_pandas()
    else:
        predictand,geodata=readPredictandCsv(predictandFile)


    availMonths=np.unique(predictand.index.month)
    availMonthNames=[months[x-1] for x in availMonths]

    if gl.fcstBaseTime=="mon":
        if not firstTgtMonth in availMonths:
            showMessage(f"file does not contain data for requested month. Predicting {tgtSeason} but got {availMonthNames}","ERROR")
            return None,None    
        #selecting this month    
        predictand=predictand[predictand.index.month==firstTgtMonth]                

    else:
        #checking if all three months of the season are in data
        result = set(tgtMonths).issubset(availMonths)
        
        if not result:
            #if not - check if middle month in data
            if not (len(availMonths)==1 and tgtMonths[1] in availMonths):
                showMessage(f"file does not contain data for requested months. Predicting {tgtSeason} but got {availMonthNames}","ERROR")
                return None,None
                
        #resampling 
        showMessage("Resampling to seasonal...")
        if gl.config['timeAggregation']=="mean":
            cont=True
            predictand=predictand.resample(f"QS-{firstTgtMonthName}".upper()).mean()
        else:
            cont=True
            predictand=predictand.resample(f"QS-{firstTgtMonthName}".upper()).sum()

        predictand=predictand[predictand.index.month==firstTgtMonth]         

    
    
    if predictand is None:
        showMessage("could not read requested variable from file","ERROR")
        return None,None



    
    predictand=predictand.dropna()
        
    if predictand is None:
        return None,None

    #check for climatological period
    datdates=predictand.index
    firstdatdate=datdates.strftime('%Y-%m-%d')[0]
    lastdatdate=datdates.strftime('%Y-%m-%d')[-1]

    showMessage("Predictant file covers period of: {} to {}".format(firstdatdate,lastdatdate),"RUNTIME")

    firstdatyear=datdates.year[0]
    lastdatyear=datdates.year[-1]

        
    #check if covers climatological period
    if gl.config["climEndYr"]>lastdatyear or gl.config["climStartYr"]<firstdatyear:
        showMessage("Climatological period {}-{} extends beyond period covered by data {}-{}".format(gl.config["climStartYr"],gl.config["climEndYr"],firstdatyear,lastdatyear), "ERROR")
        return None,None
    
    predictand=predictand.astype("float")

    return predictand, geodata

        

def compute_valid_times(init_times, lead_months):
    """
    Compute valid times for each (init_time, lead_month) combination.
    Returns a 2D numpy array of datetime64.
    """
    valid_time = np.array([
        [init + pd.DateOffset(months=int(lead)-1) for lead in lead_months]
        for init in pd.DatetimeIndex(init_times)
    ], dtype="datetime64[ns]")
    return valid_time




def flatten_leadtime(ds, init_dim="forecast_reference_time", lead_dim="forecastMonth"):
    """
    Convert forecast data with init_time + lead_month dims to data with time dimension.
    
    Assumes no overlap between initializations.
    """
    # Compute the valid (wall-clock) time for each (init, lead) pair
    valid_times = compute_valid_times(ds[init_dim], ds[lead_dim])  # xarray broadcasts automatically

    # Stack into a single dimension
    ds_stacked = ds.stack(
        valid_time=(init_dim, lead_dim)
    ).reset_index("valid_time").assign_coords(valid_time=valid_times.flatten())

    # Sort by time and drop the now-redundant coords
    ds_stacked = ds_stacked.sortby("valid_time").transpose("valid_time",...).reset_coords([init_dim,lead_dim], drop=True)

    #renaming time dimension back to time
    ds_stacked=ds_stacked.rename({"valid_time":"time"})

    return ds_stacked



def readNetcdf(ncfile, ncvar):
    try:
        #decode_times fixes the IRI netcdf calendar problem
        ds = xr.open_mfdataset(ncfile, decode_times=False)
    except Exception as e:
        showMessage((f"File cannot be read. please check if the file is properly formatted. Full error: {e}", "ERROR"))
        return
    
    #aligning coordinate names    
    coordsubs={"lon":["longitude","X","Longitude","Lon"], "lat":["latitude","Y","Latitude","Lat"], "time":["T","S","forecast_reference_time", "valid_time"], "lead_time":["forecastMonth","L"]}
    for key in coordsubs.keys():
        for x in coordsubs[key]:
            if x in ds.coords.keys():
                showMessage("\tfound {} - renaming to {}".format(x,key),"RUNTIME")
                ds=ds.rename({x:key})

    #parsing time variable with some cleanup                
    if ds["time"].attrs['calendar'] == '360':
        ds["time"].attrs['calendar'] = '360_day'
    ds = xr.decode_cf(ds)
    ds=ds.convert_calendar("standard", align_on="date")

    if ncvar not in ds.variables:
        msg="Requestd variable named {}, but it is not present in the netcdf file {}. Please inspect the data file.".format(ncvar, ncfile)
        showMessage(msg, "ERROR")
        return
    
    #selecting only the requested variable
    dat=ds[ncvar]

    #testing if variable has all required dimensions
    test=[x not in dat.coords.keys() for x in ["lat","lon","time"]]
    if np.sum(test)>0:
        msg="requested variable should have time,latitude and longitude coordinates. This is not the case. Please check if {} file is properly formatted and if {} variable of that file the one that describes forecast".format(ncfile,ncvar)
        showMessage(msg, "ERROR")
        return

    # calculating ensemble mean, if needed
    for dimName in ["number"]:
        if dimName in dat.sizes.keys():
            msg="\tFound dimension {} which indicates that file contains ensemble data. Calculating ensemble mean.".format(dimName)
            dat=dat.mean(dimName)

    # this will be data from CDS, which are on a monthly time step with init_time and lead_time dimensions. 
#    for dimName in ["forecastMonth"]:
#        if dimName in dat.sizes.keys():
#            #making sure the init time dimension exists
#            msg="\tFound dimension {} which indicates that file contains lead time data. Converting lead time to real time.".format(dimName)
#            #calculating target months with defaults
#            dat=flatten_leadtime(dat,"time","forecastMonth")
    
    #dropping unnecessary dimensions
    for dimName in dat.sizes.keys():
        if dimName not in ["lat","lon","time","lead_time"]:
            if dat.sizes[dimName]==1:
                msg="\tDropping redundand dimension of size 1: {}".format(dimName)
                showMessage(msg, "RUNTIME")
                dimValue=dat[dimName].values[0]
                dat=dat.sel({dimName:dimValue})
                dat=dat.drop_vars(dimName)
            else:
                msg="There is a redundand dimension in data that cannnot be dropped. {} of size {}. Please check your data file".format(dimName, dat.sizes[dimName])
                showMessage(msg, "ERROR")
                return

    
    #this is probably not important at this moment
    #dat=dat.rio.write_crs("epsg:4326") #adding crs
    
    #making sure time is aligned to 1th of the month
    newtime=pd.to_datetime([x.replace(day=1) for x in pd.to_datetime(dat.time.values)]).normalize()
    
    dat["time"]=newtime

    #propagating units from original file
    if "units" in dat.attrs:
        gl.config['predictandUnit']=dat.attrs["units"]
        showMessage("\tFound units: {}".format(gl.config['predictandUnit']),"RUNTIME")
    else:
        if gl.config["predictandCategory"]=="rainfall":
            gl.config['predictandUnit']="mm"
        else:
            gl.config['predictandUnit']="deg C"
            

    datdates=pd.to_datetime(dat.time)
    firstdatdate=datdates.strftime('%Y-%m-%d')[0]
    lastdatdate=datdates.strftime('%Y-%m-%d')[-1]

    showMessage("\tNetcdf file covers period of: {} to {}".format(firstdatdate,lastdatdate),"RUNTIME")

    #check against the forecast date
    firstdatyear=datdates.year[0]
    lastdatyear=datdates.year[-1]

    if gl.config["climEndYr"]>lastdatyear or gl.config["climStartYr"]<firstdatyear:
        showMessage("Climatological period {}-{} extends beyond period covered by data {}-{}".format(gl.config["climStartYr"],gl.config["climEndYr"],firstdatyear,lastdatyear), "ERROR")
        return


    showMessage("done\n", "SUCCESS")
    
    ds.close()
    
    return(dat)


        
def checkPolyValidity(_poly):
    for idx, geom in enumerate(_poly.geometry):
        if not geom.is_valid:
            showMessage(f"Polygon at index {idx} is invalid: {explain_validity(geom)}", "ERROR")
            return False
    return True
    
#this calculates zonal mean over individual time steps
def zonalMean(_grid, _poly):
    affine=_grid.rio.transform()
    _zonalmean=[]
    #check for overlap
    try:
        zs=zonal_stats(_poly, 
                   _grid[0,:,:].data, 
                   affine=affine, 
                   nodata=np.nan,
                  all_touched=False)
    except ValueError as e:
        if "negative dimensions" in str(e):
            # Likely polygon completely outside raster
            showMessage("there is no overlap between raster and vector", "ERROR")
            return None
        else:
            raise  # Re-raise unexpected errors

    for i in range(_grid.shape[0]):
        zs=zonal_stats(_poly, 
                       _grid[i,:,:].data, 
                       affine=affine, 
                       nodata=np.nan,
                      all_touched=False)
        temp=[x["mean"] for x in zs]
        _zonalmean.append(temp)

    _zonalmean=np.array(_zonalmean)
    _zonalmean=pd.DataFrame(_zonalmean, index=_grid.time, columns=_poly.index)
    return(_zonalmean)


def aggregatePredictand(_data, _geodata, _poly):
    showMessage("aggregating...")
    
    
    if isinstance(_geodata,xr.DataArray):
        #this is if geodata is xarray object
        _data=_data.unstack().to_xarray()
        _data=_data.transpose("time","lat","lon")
        _data=_data.reindex(lat=np.sort(_data.lat)[::-1])
        _data.rio.set_spatial_dims(x_dim='lon', y_dim='lat')        
        _data=_data.rio.write_crs("epsg:4326")
        _aggregated=zonalMean(_data, _poly)
        if _aggregated is None:
            return None,None
            
        showMessage("\tAverage values for {} regions derived from data for {} by {} grid".format(_aggregated.shape[1], _data.shape[1], _data.shape[2]))
    else:
        #this is if geodata is a geopandas object
        _points=_geodata.copy().join(_data.T)
        #joining polygons and points
        _joined = gpd.sjoin(_points, _poly, how="inner", predicate="within")
        
        # Check if spatial matches were found before trying to rename index_right
        #if not _joined.empty and 'index_right' in _joined.columns:
        if not _joined.empty and gl.config["zonesAttribute"] in _joined.columns:
            #_joined = _joined.rename(columns={"index_right": gl.config["zonesAttribute"]})
            #aggregating 
            _aggregated = _joined.groupby(gl.config["zonesAttribute"]).mean(numeric_only=True).T
            _aggregated.index=_data.index
            showMessage("\tAverage values for {} regions derived from data for {} locations".format(_aggregated.shape[1], _points.shape[1]))
        else:
            # No spatial matches found, create empty aggregated data
            showMessage("\tWarning: No spatial matches found between station points and polygon boundaries")
            _aggregated = pd.DataFrame(index=_data.index)  # Empty dataframe with correct index
    
    #dropping columns that are empty
    
    cols_to_drop = _aggregated.columns[_aggregated.isna().all()]
    # Find columns to keep (those not all NaN)
    cols_to_keep = _aggregated.columns[~_aggregated.isna().all()]
    if len(cols_to_drop)>0:
        showMessage("\tSome polygons do not fall over predictand data", "NONCRITICAL")
        #return None, None
        showMessage("\tRetaining {} feature(s) out of {}".format(len(cols_to_keep),_aggregated.shape[1]), "NONCRITICAL")

    # Drop the NaN-only columns from df
    _aggregated = _aggregated[cols_to_keep]

    # Filter gdf to keep only those indices
    _poly = _poly.loc[cols_to_keep]

    return _aggregated, _poly



    
        








def getLeadTime():
    srcMonth=month2int(gl.config['predictorMonth'])
    srcYear=int(gl.config['predictorYear'])
    srcDate=pd.to_datetime("{}-{}-01".format(srcYear,srcMonth))

        
    tgtMonth=month2int(gl.config['fcstTargetSeas'][0:3])
    tgtYear=int(gl.config['fcstTargetYear'])
    tgtDate=pd.to_datetime("{}-{}-01".format(tgtYear,tgtMonth))
    tgtDateCheck=tgtDate
    
    time_diff = tgtDate - srcDate
    # Approximate months using the average number of days in a month (30.44)
    leadTime = int(np.round(time_diff.days / 30.44))
    leadTimeCheck=leadTime+1

    if len(gl.config['fcstTargetSeas'])>3:
        tgtDateCheck=tgtDate+pd.offsets.MonthBegin(2)
        time_diff = tgtDateCheck - srcDate
        # Approximate months using the average number of days in a month (30.44)
        leadTimeCheck = int(np.round(time_diff.days / 30.44))+1


    if leadTimeCheck>gl.deep_config["maxLeadTime"]:
        msg=f"with forecast and target months provided ({srcDate.strftime('%b %Y')} and {tgtDateCheck.strftime('%b %Y')}), lead time is {leadTimeCheck} months. That exceeds the maximum allowed lead time of {gl.deep_config['maxLeadTime']}. Please adjust your configuration."
        showMessage(msg,"ERROR")
        return None
    
    msg=f"forecast initialized on: {srcDate.strftime('%b %Y')},  last target month: {tgtDateCheck.strftime('%b %Y')}), lead time: {leadTimeCheck} months."
    showMessage(msg,"INFO")

    gl.leadTime=leadTime
    gl.predictorDate=srcDate
    
    return leadTime



def getHcstData(_predictand,_predictor):
    
    #get time of predictand and predictor
#    _predictor=_predictor.dropna()
#    _predictand=_predictand.dropna()
    
    tgtTime=pd.to_datetime(_predictand.index)
    srcTime=pd.to_datetime(_predictor.index)
    #drop nans
    
    #align time
    #this shifts predictand time to the nominal forecast init time
    tgtTimeAdj=tgtTime-pd.offsets.MonthBegin(gl.leadTime)
    
    _predictandOvlp=_predictand.copy()
    _predictandOvlp.index=tgtTimeAdj

    #finding intersection
    sel=np.intersect1d(tgtTimeAdj, srcTime)
    _predictorOvlp=_predictor.loc[sel]
    _predictandOvlp=_predictandOvlp.loc[sel]

    #bringing back the original predictand time
    tgtTime=pd.to_datetime(_predictandOvlp.index)
    tgtTimeAdj=tgtTime+pd.offsets.MonthBegin(gl.leadTime)
    _predictandOvlp.index=tgtTimeAdj

    return _predictandOvlp, _predictorOvlp


def getFcstData(_predictor):
    tgtMonth=month2int(gl.config['fcstTargetSeas'][0:3])
    tgtYear=int(gl.config['fcstTargetYear'])
    tgtDate="{}-{}".format(tgtYear,tgtMonth)
    _data=_predictor.loc[gl.predictorDate:gl.predictorDate]
    return _data





    

class StdRegressor(BaseEstimator, RegressorMixin):
    
    def __init__(self, regressor_name=None, fit_intercept=True, max_fraction=0.15, **regressor_kwargs):
        self.max_fraction = max_fraction
        self.fit_intercept = fit_intercept
        self.regressor_name = regressor_name
        self.regressor_kwargs = regressor_kwargs
        self.scaleX=StandardScaler()
        self.reg=self._get_regressor()
        
    def _get_regressor(self):
        if self.regressor_name not in regressors:
            raise ValueError(f"Unknown regressor '{self.regressor_name}'.")
        reg_class=regressors[self.regressor_name]
        
        # Inspect constructor to see if 'fit_intercept' is accepted
        sig = inspect.signature(reg_class.__init__)
        kwargs = self.regressor_kwargs.copy()
        if 'fit_intercept' in sig.parameters:
            kwargs['fit_intercept'] = self.fit_intercept
            self.supports_intercept=True
        else:
            self.supports_intercept=False
            
        return reg_class(**kwargs)
        
    def fit(self, X, Y):
        
        #scaling the predictor
        X_std=self.scaleX.fit_transform(X)
        
        #fitting regression model
        self.reg.fit(X_std, Y)
        
        return self

    
    def predict(self, X):
        #scale as per fitted model    
        X_c = self.scaleX.transform(X)
        
        #predict with model
        Y_pred=self.reg.predict(X_c)

        return Y_pred
    

    

    
    
def getObsTerciles(_predictand,_predictandHcst):
    
    showMessage("Calculating observed terciles...")
    refData=_predictand[str(gl.config["climStartYr"]):str(gl.config["climEndYr"])]   
    _tercThresh=refData.quantile([0.33, 0.5, 0.66])
    _obsTercile=_predictandHcst.copy().astype(str)
    _obsTercile[:]="normal"
    sel=_predictandHcst>=_tercThresh.loc[0.66]
    _obsTercile[sel.values]="above"
    #below
    sel=_predictandHcst<=_tercThresh.loc[0.33]
    _obsTercile[sel.values]="below"

    return _obsTercile,_tercThresh 
    
def getFcstAnomalies(_det_fcst,_ref_data):
    absanom=_det_fcst-_ref_data.mean()
    percanom=(_det_fcst-_ref_data.mean())/_ref_data.mean()*100
    percnorm=_det_fcst/_ref_data.mean()*100
    
    if gl.config["predictandCategory"] =='rainfall':
        output=pd.concat([_det_fcst,absanom,percanom,percnorm], keys=["value","absolute_anomaly","percent_anomaly","percent_normal"], names=["category"], axis=1)
    else:
        output=pd.concat([_det_fcst,absanom], keys=["value","absolute_anomaly"], names=["category"], axis=1)
    output.index.name="time"
    return output




def probabilisticForecastCalibrated(Y_hcst,Y_obs,Y_fcst,terc_thresh, dist="empirical"):
        
    # getting cdf threshold array (we are not using threshold values here)
    targetcdfs=np.tile(terc_thresh.index.values[:, np.newaxis], (1, terc_thresh.shape[1]))

    #prediction error
    pred_err=Y_hcst-Y_obs

    #forecast distribution
    fcstvals=(Y_fcst.values + pred_err.values).astype(float)

    fcstdistrib = fit_dist_to_arr(fcstvals, dist=dist)

    #obs distribution - should be list
    obsdistrib = fit_dist_to_arr(Y_obs.values.astype(float), dist=dist)

    #this is distribution of hindcast+error - shaped nyears*nyears,nfeatures
    hcstfulldata=(Y_hcst.values[:, None, :] + pred_err.values[None, :, :])

    arr=hcstfulldata.reshape(-1,Y_hcst.shape[1]).astype(float)
    #this will be a list
    hcstfulldistrib = fit_dist_to_arr(arr, dist=dist)


    calibfcstcdf=calibrate(targetcdfs, fcstdistrib, hcstfulldistrib, dist=dist)
    calibfcstcdf=pd.DataFrame(calibfcstcdf, index=terc_thresh.index, columns=Y_fcst.columns)    

    temp=calibfcstcdf.loc[0.33]
    prob_below_fcst=pd.DataFrame(temp.values.reshape(*Y_fcst.shape), index=Y_fcst.index, columns=Y_fcst.columns)

    temp=1-calibfcstcdf.loc[0.66]
    prob_above_fcst=pd.DataFrame(temp.values.reshape(*Y_fcst.shape), index=Y_fcst.index, columns=Y_fcst.columns)
    prob_normal_fcst=1-(prob_above_fcst+prob_below_fcst)


    calibhcstcdf=[]
    for i in range(hcstfulldata.shape[0]):
        hcstyeardistrib=fit_dist_to_arr(hcstfulldata[i,:].astype(float), dist=dist)
        temp=calibrate(targetcdfs,hcstyeardistrib,hcstfulldistrib, dist=dist)
        calibhcstcdf.append(temp)
    calibhcstcdf=pd.DataFrame(np.concatenate(calibhcstcdf, axis=1), index=terc_thresh.index)    


    temp=calibhcstcdf.loc[0.33]
    prob_below_hcst=pd.DataFrame(temp.values.reshape(*Y_hcst.shape), index=Y_hcst.index, columns=Y_hcst.columns)
    prob_below_hcst

    temp=1-calibhcstcdf.loc[0.66]
    prob_above_hcst=pd.DataFrame(temp.values.reshape(*Y_hcst.shape), index=Y_hcst.index, columns=Y_hcst.columns)
    prob_above_hcst
    prob_normal_hcst=1-(prob_above_hcst+prob_below_hcst)

    #preparing final dataframes
    terc_fcst=pd.concat([prob_below_fcst,prob_normal_fcst,prob_above_fcst], keys=["below","normal","above"],  names=["category"], axis=1)
    terc_hcst=pd.concat([prob_below_hcst,prob_normal_hcst,prob_above_hcst], keys=["below","normal","above"], names=["category"],axis=1)
    terc_fcst.index.name="time"
    terc_hcst.index.name="time"
    
    return terc_fcst, terc_hcst, calibhcstcdf



class ECDF:
    @staticmethod
    def fit(data):
        """Fit ECDF: returns (x_sorted, cdf_grid) like params."""
        data = np.sort(np.asarray(data, dtype=float))
        n = len(data)
        cdf_grid = np.linspace(1/n, 1, n)
        return data, cdf_grid

    @staticmethod
    def cdf(vals, x_sorted, cdf_grid):
        """CDF from fitted ECDF."""
        f = interp1d(x_sorted, cdf_grid, bounds_error=False, fill_value=(0, 1))
        return f(vals)

    @staticmethod
    def ppf(q, x_sorted, cdf_grid):
        """Quantile (inverse CDF) from fitted ECDF."""
        f = interp1d(cdf_grid, x_sorted, bounds_error=False,
                     fill_value=(x_sorted[0], x_sorted[-1]))
        return f(q)


def fit_dist_to_arr(data, dist="normal"):
    if dist=="normal":
        func=norm
    elif dist=="empirical":
        func=ECDF
        
    params=[func.fit(data[:, i][~np.isnan(data[:, i])]) for i in range(data.shape[1])]
    
    return params
        
        
def get_cdf(values, params, dist="normal"):
    if dist=="normal":
        func=norm
    elif dist=="empirical":
        func=ECDF
    
    cdf=values.copy()
    cdf[:]=np.nan
    for i in range(values.shape[1]):
        cdf[:,i]=func.cdf(values[:,i], *params[i])
        
    return cdf

def get_value(cdf, params, dist="normal"):
    if dist=="normal":
        func=norm
    elif dist=="empirical":
        func=ECDF
    
    values=cdf.copy()
    values[:]=np.nan
    for i in range(cdf.shape[1]):
        values[:,i]=func.ppf(cdf[:,i], *params[i])
    return values

def calibrate(targetcdfs, fcstdistrib, hcstfulldistrib, dist="normal"):
    
    hcsttargetvalue=get_value(targetcdfs,hcstfulldistrib, dist=dist)
    _calibfcstcdf=get_cdf(hcsttargetvalue,fcstdistrib, dist=dist)
    return _calibfcstcdf





def two_afc_multicategory(forecast_probs, obs):
    """
    Compute generalized 2AFC score for 3-category forecast.
    forecast_probs: np.array of shape (n_samples, 3)
    obs: np.array of shape (n_samples,) with values 0, 1, 2
    """
    scores = []
    
    for cat in range(3):
        correct = 0
        total = 0
        
        # Indices where obs is in current category (event)
        idx_event = np.where(obs == cat)[0]
        # Indices where obs is not in current category (non-event)
        idx_nonevent = np.where(obs != cat)[0]
        
        for i in idx_event:
            for j in idx_nonevent:
                f_i = forecast_probs[i, cat]
                f_j = forecast_probs[j, cat]
                
                if f_i > f_j:
                    correct += 1
                elif f_i == f_j:
                    correct += 0.5
                total += 1
                
        score = correct / total if total > 0 else np.nan
        scores.append(score)
        
    return np.nanmean(scores)


def rps_score(forecast_probs, observed_class, n_categories=3):
    # forecast_probs: array of shape (n_samples, n_categories)
    # observed_class: array of shape (n_samples,), with integer values 0, 1, ..., K-
    rps = 0
    for i in range(len(observed_class)):
        obs = np.zeros(n_categories)
        obs[observed_class[i]] = 1
        obs_cum = np.cumsum(obs)
        forecast_cum = np.cumsum(forecast_probs[i])
        rps += np.sum((forecast_cum - obs_cum) ** 2)
    return rps / len(observed_class)



def rpss_score(forecast_probs, climatology_probs, observed_class):
    rps_forecast = rps_score(forecast_probs, observed_class)
    rps_climatology = rps_score(np.tile(climatology_probs, (len(observed_class), 1)), observed_class)
    return 1 - rps_forecast / rps_climatology

cat2num={"below":0,"normal":1,"above":2}

def ignorance_score(forecast_probs, observed_class):
    # Clip probabilities to avoid log(0)
    eps = 1e-15
    prob = np.clip(forecast_probs, eps, 1-eps)
    # Select the probability assigned to the observed category
    p_observed = prob[np.arange(len(observed_class)), observed_class]

    # Compute ignorance
    ignorance = -np.log2(p_observed)

    # Mean ignorance over all instances
    mean_ignorance = np.mean(ignorance)

    return mean_ignorance
        
def heidke_skill_score(forecast_probs, obs):
        
    fcst=np.argmax(forecast_probs, axis=1)
    
    categories = np.unique(np.concatenate([obs, fcst]))
    K = len(categories)
    N_t = len(obs)
    
    # contingency counts per category
    N_f = np.array([np.sum(fcst == k) for k in categories])
    N_o = np.array([np.sum(obs == k) for k in categories])
    N_c = np.sum(obs == fcst)  # number of correct forecasts
    
    N_e = np.sum(N_f * N_o) / N_t  # expected correct by chance
    HSS = (N_c - N_e) / (N_t - N_e)
    return HSS

def brier_skill_score(forecast_probs, obs):
    
    n_instances = len(obs)
    n_categories = forecast_probs.shape[1]

    # one-hot encoding of observations
    obs_onehot = np.zeros_like(forecast_probs)
    obs_onehot[np.arange(n_instances), obs] = 1
    
    brier = np.mean(np.sum((forecast_probs - obs_onehot)**2, axis=1))
    return brier

def effective_interest_rate(forecast_probs, obs):

    # Clip probabilities to avoid log(0)
    eps = 1e-15
    prob = np.clip(forecast_probs, eps, 1-eps)

    # 1. Ignorance of forecast
    p_obs = prob[np.arange(len(obs)), obs]
    I_forecast = -np.log2(p_obs)

    # 2. Reference probabilities (climatology)
    obs_onehot = np.zeros_like(prob)
    obs_onehot[np.arange(len(obs)), obs] = 1
    clim_prob = obs_onehot.mean(axis=0)

    p_ref = clim_prob[obs]
    I_ref = -np.log2(p_ref)

    # 3. Effective information
    info_gain = I_ref - I_forecast
    mean_info_gain = np.mean(info_gain)
    
    return mean_info_gain



def groc_score(probs, obs):
    """
    Calculate the Generalized ROC (GROC) skill score.
    
    Parameters
    ----------
    probs : np.ndarray
        Array of forecast probabilities with shape (N, C),
        where N = number of forecasts, C = number of categories.
    obs : np.ndarray
        Array of observed categories with shape (N,), 
        integers in [0, C-1].
        
    Returns
    -------
    groc : float
        GROC value (0–1).
    groc_skill : float
        GROC skill score (-1–1).
    """
    N, C = probs.shape
    
    scores = []
    
    for i in range(N):
        p_obs = probs[i, obs[i]]
        
        for c in range(C):
            if c == obs[i]:
                continue
            p_other = probs[i, c]
            
            if p_obs > p_other:
                scores.append(1.0)
            elif p_obs == p_other:
                scores.append(0.5)
            else:
                scores.append(0.0)
    
    groc = np.mean(scores)
    groc_skill = 2 * (groc - 0.5)  # normalize to [-1, 1]
    
    return groc



def getSkill(_prob_hcst,_det_hcst,_predictand_hcst,_obs_tercile):
    #iterating through stations/locations

    allscores=[]
    for entry in _det_hcst.columns:
        index=[]
        scoreslist=[]
        
        roc_score_above = np.round(roc_auc_score(_obs_tercile[entry]=="above", _prob_hcst["above"][entry]),2)
        scoreslist.append(roc_score_above)
        index.append("ROC_above")
          
        roc_score_below = np.round(roc_auc_score(_obs_tercile[entry]=="below", _prob_hcst["below"][entry]),2)
        scoreslist.append(roc_score_below)
        index.append("ROC_below")
        
        roc_score_normal = np.round(roc_auc_score(_obs_tercile[entry]=="normal", _prob_hcst["normal"][entry]),2)
        scoreslist.append(roc_score_normal)
        index.append("ROC_normal")
        
        cor=np.round(np.corrcoef(_det_hcst[entry].values,_predictand_hcst[entry].values.astype(float))[0][1],2)
        scoreslist.append(cor)
        index.append("correlation")

        #r2=np.round(r2_score(_det_hcst[entry],_predictand_hcst[entry]))
        ev=np.round(explained_variance_score(_det_hcst[entry],_predictand_hcst[entry]))
        
        if gl.config["predictandCategory"] =='rainfall':        
            mape=np.round(mean_absolute_percentage_error(_det_hcst[entry],_predictand_hcst[entry]),2)
            scoreslist.append(mape)
            index.append("MAPE")
        else:
            mae=np.round(mean_absolute_error(_det_hcst[entry],_predictand_hcst[entry]),2)
            scoreslist.append(mae)
            index.append("MAE")
        
        rmse=np.round((mean_squared_error(_det_hcst[entry],_predictand_hcst[entry])**0.5),2)
        scoreslist.append(rmse)
        index.append("RMSE")

        #prep data for rpss
        _prob_clim=_prob_hcst.copy()
        _prob_clim[:]=0.33
        obsterc=_obs_tercile[entry]
        obsterc=obsterc.map(lambda x: cat2num[x]).values
        if isinstance(entry, tuple):
            mask = (_prob_clim.columns.get_level_values('lat') == entry[0]) & (_prob_clim.columns.get_level_values('lon') == entry[1])
            pclim=_prob_clim.loc[:, mask].values
            mask = (_prob_clim.columns.get_level_values('lat') == entry[0]) & (_prob_clim.columns.get_level_values('lon') == entry[1])
            phcst=_prob_hcst.loc[:,mask]
        else:
            pclim=_prob_clim.loc[:,_prob_clim.columns.get_level_values(1)==entry].values
            phcst=_prob_hcst.loc[:,_prob_hcst.columns.get_level_values(1)==entry]

        phcst.columns = phcst.columns.droplevel(1)
        #have to reorder so that below is 0, normal is 1, above is 2 as per cat2num
        phcst=phcst.loc[:,["below","normal","above"]].values

        #calculate rpss
        rpss=rpss_score(phcst, pclim,obsterc)
        rpss=np.round(rpss,2)
        scoreslist.append(rpss)
        index.append("rpss")


        # ignorance score
        ignorance=np.round(ignorance_score(phcst,obsterc),2)
        scoreslist.append(ignorance)
        index.append("ignorance")
        
        hss=np.round(heidke_skill_score(phcst,obsterc),2)
        scoreslist.append(hss)
        index.append("hss")

        twoafc=np.round(two_afc_multicategory(phcst, obsterc),2)
        scoreslist.append(twoafc)
        index.append("2afc")
        
        brier=np.round(brier_skill_score(phcst, obsterc),2)
        scoreslist.append(brier)
        index.append("brier")
        
        effintrate=np.round(effective_interest_rate(phcst,obsterc),2)
        scoreslist.append(effintrate)
        index.append("effintrate")
        
        groc=np.round(groc_score(phcst,obsterc),2)
        scoreslist.append(groc)
        index.append("groc")
        

        #entryscores=pd.Series([cor,mape,rmse,roc_score_above, roc_score_normal,roc_score_below, rpss, ignorance, hss, twoafc, brier, effintrate, groc], index=index)
        
        entryscores=pd.Series(scoreslist, index=index)

        allscores.append(entryscores)

    scores=pd.concat(allscores, axis=1, keys=_det_hcst.columns)
    scores.index.name = "category"
    return(scores)





    
        
        
def saveConfig():
    #defined parameters/variables
    with open(gl.configFile, "w") as f:
        json.dump(gl.config, f, indent=4)
        showMessage("saved config to: {}".format(gl.configFile), "INFO")
    return gl.config

        


def populateGui():
    #populate comboBoxes
    # target season
    gl.window.comboBox_tgtseas.clear()
    #gl.window.comboBox_tgtseas.addItem("", "")
    for key in tgtSeass:
        gl.window.comboBox_tgtseas.addItem(key, key)
    
    #source/predictand month
    gl.window.comboBox_srcmon.clear()
    #gl.window.comboBox_srcmon.addItem("", "")
    for key in months:
        gl.window.comboBox_srcmon.addItem(key, key)

    #temporal aggregation
    gl.window.comboBox_timeaggregation.clear()
    #gl.window.comboBox_timeaggregation.addItem("", "")
    for key in timeAggregations:
        gl.window.comboBox_timeaggregation.addItem(key, key)
                
    #predictand category
    gl.window.comboBox_predictandcategory.clear()
    for item in predictandCats:
        gl.window.comboBox_predictandcategory.addItem(item, item)
        
    comboName="comboBox_preproc"
    if hasattr(gl.window, comboName):
        item=getattr(gl.window, comboName, None)
        item.clear()
        #item.addItem("", "")
        for key in gl.preprocessor_config:
            item.addItem(gl.preprocessor_config[key][0], key)

    comboName="comboBox_regression"
    if hasattr(gl.window, comboName):
        item=getattr(gl.window, comboName, None)
        item.clear()
        #item.addItem("", "")
        for key in gl.regressor_config:
            item.addItem(gl.regressor_config[key][0], key)

    comboName="comboBox_crossval"
    if hasattr(gl.window, comboName):
        item=getattr(gl.window, comboName, None)
        item.clear()
        #item.addItem("", "")
        for key in gl.crossvalidator_config:
            item.addItem(gl.crossvalidator_config[key][0], key)

                
    # read data from config
    gl.window.lineEdit_rootdir.setText(gl.config['rootDir'])
    gl.window.lineEdit_tgtyear.setText(str(gl.config['fcstTargetYear']))
    gl.window.lineEdit_srcyear.setText(str(gl.config['predictorYear']))
    gl.window.comboBox_srcmon.setCurrentText(gl.config['predictorMonth'])
    gl.window.comboBox_tgtseas.setCurrentText(gl.config['fcstTargetSeas'])
    gl.window.lineEdit_climstartyr.setText(str(gl.config['climStartYr']))
    gl.window.lineEdit_climendyr.setText(str(gl.config['climEndYr']))
    gl.window.comboBox_predictandcategory.setCurrentText(gl.config['predictandCategory'])
    gl.window.lineEdit_predictandmissingvalue.setText(str(gl.config['predictandMissingValue']))

    for var in ["minLon","maxLon","minLat","maxLat"]:
        itemName="lineEdit_{}".format(var)
        if hasattr(gl.window, itemName):
            item=getattr(gl.window, itemName, None)
            item.setText(str(gl.config['predictorExtents'][var]))

    itemName="comboBox_crossval"
    if hasattr(gl.window, itemName):
        item=getattr(gl.window, itemName, None)
        setval=gl.crossvalidator_config[gl.config["crossval"]][0]
        item.setCurrentText(setval)

    itemName="comboBox_regression"
    if hasattr(gl.window, itemName):
        item=getattr(gl.window, itemName, None)
        setval=gl.regressor_config[gl.config["regression"]][0]
        item.setCurrentText(setval)

    itemName="comboBox_preproc"
    if hasattr(gl.window, itemName):
        item=getattr(gl.window, itemName, None)
        setval=gl.preprocessor_config[gl.config["preproc"]][0]
        item.setCurrentText(setval)

    itemName="lineEdit_predictorfile"
    if hasattr(gl.window, itemName):
        item=getattr(gl.window, itemName, None)
        predictorfile=gl.config["predictorFileName"]
        item.setText(predictorfile)
        variables=readVariablesFile(predictorfile)

    itemName="comboBox_predictorvar"
    if hasattr(gl.window, itemName):
        item=getattr(gl.window, itemName, None)
        setval=gl.config["predictorVar"]
        #remove once (if) function to read file is implemented
        item.addItems(variables)
        if setval in variables:
            item.setCurrentText(setval)

    itemName="lineEdit_predictorcode"
    if hasattr(gl.window, itemName):
        item=getattr(gl.window, itemName, None)
        setval=gl.config["predictorCode"]
        item.setText(setval)
    
    gl.window.lineEdit_predictandfile.setText(gl.config['predictandFileName'])
    #for the time being - have to have a function that reads this file and populates variable list
    variables=readVariablesFile(gl.config['predictandFileName'])
    gl.window.comboBox_predictandvar.clear()
    gl.window.comboBox_predictandvar.addItems(variables)
    if gl.config['predictandVar'] in variables:
        gl.window.comboBox_predictandvar.setCurrentText(gl.config['predictandVar'])
            
    gl.window.checkBox_zonesaggregate.setChecked(gl.config["zonesAggregate"])
    
    gl.window.checkBox_regridpredictand.setChecked(gl.config["regridPredictand"])
    
    gl.window.lineEdit_zonesfile.setText(gl.config['zonesFile'])
    attributes=readVariablesFile(gl.config['zonesFile'])        
    gl.window.comboBox_zonesattribute.clear()
    gl.window.comboBox_zonesattribute.addItems(attributes)
    if gl.config['zonesAttribute'] in attributes:
        gl.window.comboBox_zonesattribute.setCurrentText(gl.config['zonesAttribute'])

    gl.window.lineEdit_overlayfile.setText(gl.config['overlayFile'])

    
def makeConfig():
    gl.config={}

    #defined parameters/variables
    gl.config['rootDir'] = "../test_data"

    gl.config['predictorYear'] = 2025
    gl.config['predictorMonth'] = "Jul"

    gl.config['fcstTargetSeas']="Dec-Feb"
    gl.config['fcstTargetYear']=2025

    gl.config["climEndYr"]=2015
    gl.config["climStartYr"]=1994

    gl.config["predictorExtents"]={'minLat':-60,'maxLat':60,'minLon':-180,'maxLon':180}
    

    gl.config['predictorFileName'] = "/work/code/csc/cft/download_test/SST_ERSSTv5_IRIDL_mon_198107-202507.nc"
    gl.config['predictorVar'] = "sst"
    gl.config['predictorCode'] = "SST"
    gl.config['crossval']="KF"
    gl.config['preproc']="PCR"
    gl.config['regression']="OLS"

    gl.config['timeAggregation']="sum"
    gl.config["predictandFileName"]="/work/code/csc/cft/sadc_cft_current/example_data/pr_mon_chirps-v2.0_198101-202308.nc"
    gl.config["predictandVar"]="PRCPTOT"
    gl.config["predictandCategory"]="rainfall"
    gl.config["predictandMissingValue"]=-999

    gl.config["zonesFile"]="data/Botswana.geojson"
    gl.config["zonesAttribute"]="ID"
    gl.config["zonesAggregate"]=True
    gl.config["regridPredictand"]=False

    gl.config["overlayFile"]=""
    
    
    
def readGUI():
    #defined parameters/variables
    gl.config['rootDir']=gl.window.lineEdit_rootdir.text()
    gl.config['fcstTargetYear']=int(gl.window.lineEdit_tgtyear.text())
    gl.config['predictorYear']=int(gl.window.lineEdit_srcyear.text())
    gl.config['predictorMonth']=gl.window.comboBox_srcmon.currentText()
    gl.config['fcstTargetSeas']=gl.window.comboBox_tgtseas.currentText()
    gl.config['climStartYr']=int(gl.window.lineEdit_climstartyr.text())
    gl.config['climEndYr']=int(gl.window.lineEdit_climendyr.text())
    gl.config['timeAggregation']=gl.window.comboBox_timeaggregation.currentText()

    gl.config["predictandFileName"]=gl.window.lineEdit_predictandfile.text()
    gl.config["predictandVar"]=gl.window.comboBox_predictandvar.currentText()
    gl.config["predictandCategory"]=gl.window.comboBox_predictandcategory.currentText()
    gl.config["predictandMissingValue"]=gl.window.lineEdit_predictandmissingvalue.text()

    gl.config["zonesFile"]=gl.window.lineEdit_zonesfile.text()
    gl.config["zonesAttribute"]=gl.window.comboBox_zonesattribute.currentText()
    gl.config["zonesAggregate"]=gl.window.checkBox_zonesaggregate.isChecked()
    gl.config["regridPredictand"]=gl.window.checkBox_regridpredictand.isChecked()

    gl.config["overlayFile"]=gl.window.lineEdit_overlayfile.text()

    
    temp={}
    for var in ["minLon","maxLon","minLat","maxLat"]:
        itemName="lineEdit_{}".format(var)
        if hasattr(gl.window, itemName):
            item=getattr(gl.window, itemName, None)
            try:
                temp[var]=float(item.text())
            except:
                showMessage("Lat Lon values have to be numeric", "ERROR")
                return
    if len(temp)==4:
        gl.config["predictorExtents"]=temp
    

    temp=[]
    itemName="lineEdit_predictorfile"
    if hasattr(gl.window, itemName):
        gl.config["predictorFileName"]=getattr(gl.window, itemName, None).text()
        
    itemName="comboBox_predictorvar"
    if hasattr(gl.window, itemName):
        gl.config["predictorVar"]=getattr(gl.window, itemName, None).currentText()
        
    itemName="lineEdit_predictorcode"
    if hasattr(gl.window, itemName):
        gl.config["predictorCode"]=getattr(gl.window, itemName, None).text()

    itemName="comboBox_crossval"
    if hasattr(gl.window, itemName):
        gl.config["crossval"]=getattr(gl.window, itemName, None).currentData()
                
    itemName="comboBox_preproc"
    if hasattr(gl.window, itemName):
        gl.config["preproc"]=getattr(gl.window, itemName, None).currentData()
                
    itemName="comboBox_regression"
    if hasattr(gl.window, itemName):
        gl.config["regression"]=getattr(gl.window, itemName, None).currentData()

            
    #derived variables
    
    #set target type 
    if gl.config["zonesAggregate"]:
        gl.targetType="zones"
    elif gl.config["predictandFileName"][-3:]=="csv":
        gl.targetType="points"
    else:
        gl.targetType="grid"

    if len(gl.config["fcstTargetSeas"])>3:
        gl.fcstBaseTime="seas"
    else:
        gl.fcstBaseTime="mon"
        
    return True
        
        
def readVariablesFile(_file):        
    ext=os.path.splitext(_file)[1]
    if ext==".nc":
        variables = readVariablesNcfile(_file)
    elif ext in [".geojson",".shp"]:
        variables = readVariablesShpfile(_file)
    else:
        variables=[Path(_file).stem.split("_")[0]]
    if variables is None:
        #noncritical because check is done later too, and this will leave 
        showMessage("File with variables/attributes expected. If it is a netcdf file check if it is a dataset and has at least one variable, and if it is a shapefile - check if it has at least one attribute", "NONCRITICAL")
        variables=[]
    return variables

def readVariablesShpfile(_file):
    # Open the shapefile
    showMessage("reading variables from {}".format(_file))
    if os.path.exists(_file):
        gdf = gpd.read_file(_file)
        #exclude the geometry column:
        attributes = [col for col in gdf.columns if col != "geometry"]
        if len(attributes)>0:
            return attributes
        else:
            return
    else:
        showMessage("File {} does not exist".format(_file),"ERROR")
        return
            
def readVariablesNcfile(_file):
    # Open the shapefile
    showMessage("reading variables from {}".format(_file))
    if os.path.exists(_file):
        ds = xr.open_dataset(_file, decode_times=False)

        # If you want to exclude the geometry column:
        variables = ds.data_vars
        variables =[x for x in variables if x not in ["T","time","lat","lon","Lat","Lon","Latitude","Longitude","X","Y"]]
        ds.close()
        if len(variables)>0:
            return variables
        else:
            showMessage("File {} does not have any data variables".format(_file),"ERROR")
            return
    else:
        showMessage("File {} does not exist".format(_file),"ERROR")
        return        
    


def sanitize_string(value, replacement="_", max_length=255):
    """
    Sanitize a string so it can be safely used as a filename
    across Windows, macOS, and Linux.
    
    - Removes invalid characters
    - Removes control characters
    - Strips leading/trailing spaces and dots
    - Normalizes Unicode (optional transliteration to ASCII)
    - Truncates to max_length (default 255)
    """
    # Normalize Unicode (e.g., é → e)
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode()

    # Replace invalid characters with replacement
    value = re.sub(r'[<>:"/\\|?*]', replacement, value)

    # Remove control characters
    value = re.sub(r'[\x00-\x1f]', replacement, value)

    # Replace multiple consecutive replacements with a single one
    value = re.sub(rf'{re.escape(replacement)}+', replacement, value)

    # Strip leading/trailing spaces and dots
    value = value.strip(" .")

    # Truncate to safe length
    return value[:max_length] if max_length else value


def getCmap(vmin,vmax,nlev,cmap,extend,whitelev):
#    vmin=d["vmin"]
#    vmax=d["vmax"]
#    nlev=d["nlev"]
#    cmap=d["cmap"]
#    extend=d["extend"]
#    whitelev=d["whitelev"]
    levels = np.linspace(vmin,vmax,nlev)    
    cmap_rb = plt.get_cmap(cmap)
    if extend=="both":
        cols = cmap_rb(np.linspace(0.1, 0.9, len(levels)+1))
    elif extend=="neither":
        cols = cmap_rb(np.linspace(0.1, 0.9, len(levels)-1))
    else:
        cols = cmap_rb(np.linspace(0.1, 0.9, len(levels)))
        
    for lev in whitelev:
        cols[lev]=(1,1,1,1)
    cmap, norm = colors.from_levels_and_colors(levels, cols, extend=extend)
    return cmap,norm,levels


def getCmap_dev(d):
    vmin=d["vmin"]
    vmax=d["vmax"]
    nlev=d["nlev"]
    cmap=d["cmap"]
    extend=d["extend"]
    whitelev=d["whitelev"]
    vcenter  = d.get("vcenter", None)   # optional    
    
    
    levels=d["levels"]
    if levels is None:
        levels = np.linspace(vmin,vmax,nlev)   
    
    # choose norm
    if vcenter is not None:
        levels = d["levels"]   
        norm = colors.TwoSlopeNorm(vmin=vmin, vcenter=vcenter, vmax=vmax)
    else:
        norm = colors.Normalize(vmin=vmin, vmax=vmax)
  
    # get base colormap
    cmap_rb = plt.get_cmap(cmap)
    
    if extend=="both":
        cols = cmap_rb(np.linspace(0.1, 0.9, len(levels)+1))
    elif extend=="neither":
        cols = cmap_rb(np.linspace(0.1, 0.9, len(levels)-1))
    else:
        cols = cmap_rb(np.linspace(0.1, 0.9, len(levels)))

    # overwrite selected bins with white if requested
    for lev in whitelev:
        cols[lev] = (1,1,1,1)

    cmap, _ = colors.from_levels_and_colors(levels, cols, extend=extend)
    
    return cmap,norm, levels

colormaps={"percent_normal":{
        "categorized":True,
        "nlev":21,
        "title":"Forecast value as percent of normal",
        "cmap":"BrBG",
        "vmin":0,
        "vmax":200,
        "symmetric":False,
        "cbar_label":"%",
        "levels":None,
        "whitelev":[9,10],
        "tick_labels":None,
        "extend":"max"},
    "value":{
        "categorized":True,
        "nlev":11,
        "title":"Forecast value",
        "cmap":{"rainfall":plt.cm.YlGnBu, "temperature":plt.cm.RdBu_r},
        "vmin":"auto",
        "vmax":"auto",
        "symmetric":False,
        "cbar_label":"unit",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"max"},
    "absolute_anomaly":{
        "categorized":True,
        "nlev":21,
        "title":"Forecast anomaly",
        "cmap":{"rainfall":plt.cm.BrBG, "temperature":plt.cm.RdBu_r},
        "vmin":"auto",
        "vmax":"auto",
        "symmetric":True,
        "cbar_label":"unit",
        "levels":None,
        "whitelev":[10,11],
        "tick_labels":None,
        "extend":"both"},
    "percent_anomaly":{
        "categorized":True,
        "nlev":21,
        "title":"Forecast anomaly as percent of normal",
        "cmap":plt.cm.BrBG,
        "vmin":"auto",
        "vmax":"auto",
        "symmetric":True,
        "cbar_label":"%",
        "levels":None,
        "whitelev":[9,10],
        "tick_labels":None,
        "extend":"max"},
    "correlation":{
        "categorized":True,
        "nlev":21,
        "title":"Pearson's correlation coefficient\n(hindcast)",
        "cmap":plt.cm.RdBu,
        "vmin":-0.5,
        "vmax":0.5,
        "symmetric":True,
        "cbar_label":"-",
        "levels":None,
        "whitelev":[10,11],
        "tick_labels":None,
        "extend":"both"},
    "MAPE":{
        "categorized":True,
        "nlev":11,
        "title":"Mean absolute percentage error\n(hindcast)",
        "cmap":plt.cm.Grays,
        "vmin":0,
        "vmax":"auto",
        "symmetric":False,
        "cbar_label":"%",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"max"},
    "MAE":{
        "categorized":True,
        "nlev":11,
        "title":"Mean absolute error\n(hindcast)",
        "cmap":plt.cm.Grays,
        "vmin":0,
        "vmax":"auto",
        "symmetric":False,
        "cbar_label":"unit",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"max"},
    "RMSE":{        
        "categorized":True,
        "nlev":11,
        "title":"Root mean square error\n(hindcast)",
        "cmap":plt.cm.Grays,
        "vmin":0,
        "vmax":"auto",
        "symmetric":False,
        "cbar_label":"unit",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"max"},
    "ROC_above":{
        "categorized":True,
        "nlev":11,
        "title":"ROC score for above normal category\n(hindcast)",
        "cmap":plt.cm.RdBu,
        "vmin":0,
        "vmax":1,
        "symmetric":False,
        "cbar_label":"score",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"neither"},
    "ROC_normal":{
        "categorized":True,
        "nlev":11,
        "title":"ROC score for normal category\n(hindcast)",
        "cmap":plt.cm.RdBu,
        "vmin":0,
        "vmax":1,
        "symmetric":False,
        "cbar_label":"score",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"neither"},
    "ROC_below":{
        "categorized":True,
        "nlev":11,
        "title":"ROC score for below normal category\n(hindcast)",
        "cmap":plt.cm.RdBu,
        "vmin":0,
        "vmax":1,
        "symmetric":False,
        "cbar_label":"score",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"neither"},
    "groc":{
        "categorized":True,
        "nlev":11,
        "title":"Generalized ROC score\n(hindcast)",
        "cmap":plt.cm.RdBu,
        "vmin":0,
        "vmax":1,
        "symmetric":False,
        "cbar_label":"score",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"neither"},
           
    "rpss":{
        "categorized":True,
        "nlev":21,
        "title":"RPSS score\n(hindcast)",
        "cmap":plt.cm.RdBu,
        "vmin":-1,
        "vmax":1,
        "symmetric":True,
        "cbar_label":"score",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"neither"},
    "ignorance":{
        "categorized":True,
        "nlev":11,
        "title":"Ignorance score\n(hindcast)",
        "cmap":plt.cm.Greys_r,
        "vmin":0,
        "vmax":"auto",
        "symmetric":False,
        "cbar_label":"score",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"max"},
    "hss":{
        "categorized":True,
        "nlev":11,
        "title":"Heidke skill score\n(hindcast)",
        "cmap":plt.cm.RdBu,
        "vmin":-1,
        "vmax":1,
        "symmetric":True,
        "cbar_label":"score",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"neither"},
    "2afc":{
        "categorized":True,
        "nlev":11,
        "title":"2AFC score\n(hindcast)",
        "cmap":plt.cm.RdBu,
        "vmin":0,
        "vmax":1,
        "symmetric":False,
        "cbar_label":"score",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"neither"},
    "brier":{
        "categorized":True,
        "nlev":11,
        "title":"Brier score\n(hindcast)",
        "cmap":plt.cm.RdBu,
        "vmin":-1,
        "vmax":1,
        "symmetric":False,
        "cbar_label":"score",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"min"},
    "effintrate":{
        "categorized":True,
        "nlev":11,
        "title":"Effective interest rate\n(hindcast)",
        "cmap":plt.cm.RdBu,
        "vmin":-1,
        "vmax":1,
        "symmetric":False,
        "cbar_label":"score",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"both"},
    "normal":{
        "categorized":True,
        "nlev":11,
        "title":"Forecast probability \nof normal category",
        "cmap":plt.cm.RdBu,
        "vmin":0,
        "vmax":1,
        "symmetric":False,
        "vcenter":0.33,
        "cbar_label":"probability",
        "levels":[0, 0.15, 0.20,0.25, 0.3, 0.33, 0.35, 0.4, 0.45, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        "whitelev":[],
        "tick_labels":None,
        "extend":"neither"},
    "below":{
        "categorized":True,
        "nlev":11,
        "title":"Forecast probability \nof below normal category",
        "cmap":plt.cm.RdBu,
        "vmin":0,
        "vmax":1,
        "symmetric":False,
        "vcenter":0.33,
        "cbar_label":"probability",
        "levels":[0, 0.15, 0.20,0.25, 0.3, 0.33, 0.35, 0.4, 0.45, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        "whitelev":[],
        "tick_labels":None,
        "extend":"neither"},
    "above":{
        "categorized":True,
        "nlev":11,
        "title":"Forecast probability \nof above normal category",
        "cmap":plt.cm.RdBu,
        "vmin":0,
        "vmax":1,
        "symmetric":False,
        "vcenter":0.33,
        "cbar_label":"probability",
        "levels":[0, 0.15, 0.20,0.25, 0.3, 0.33, 0.35, 0.4, 0.45, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        "whitelev":[],
        "tick_labels":None,
        "extend":"neither"},
    "cem_category":{
        "categorized":False,
        "nlev":None,
        "title":"Forecast category \n(four category forecast)",
        "cmap":colors.ListedColormap(['#d2b48c', 'yellow','#0bfffb', 'blue']),
        "vmin":0,
        "vmax":4,
        "symmetric":False,
        "cbar_label":"category",
        "levels":np.array([1,2,3,4])-0.5,
        "whitelev":[],
        "tick_labels":['BN', 'N-BN','N-AN','AN'],
        "extend":"neither"},
    "tercile_category":{
        "categorized":False,        
        "nlev":None,
        "title":"Forecast category (tercile)",
        "cmap":{"rainfall": colors.ListedColormap(['#d2b48c', '0.8','blue']), "temperature": colors.ListedColormap(['blue', '0.8','red'])},
        "vmin":0,
        "vmax":3,
        "symmetric":False,
        "cbar_label":"category",
        "levels":np.array([1,2,3])-0.5,
        "whitelev":[],
        "tick_labels":['BN', 'N', 'AN'],
        "extend":"neither"}
}

skillMasks={
    "ROC_above":["ROC_above",0.5,"<"]
}

def nice_minmax(x,y=None, symmetric=False):
    # 1. Get global min and max
    if y is None:
        data_min = np.nanmin(x)
        data_max = np.nanmax(x)        
    else:
        data_min = min(np.nanmin(x), np.nanmin(y))
        data_max = max(np.nanmax(x), np.nanmax(y))


    # 2. Add padding
    padding = 0.05 * (data_max - data_min)
    raw_min = data_min - padding
    raw_max = data_max + padding
    
    # 3. Round to "nice" numbers (nearest power of 10 multiples)
    def nice_limits(vmin, vmax):
        rng = vmax - vmin
        exp = int(np.floor(np.log10(rng)))  # order of magnitude
        step = 10 ** exp
        vmin = np.floor(vmin / step) * step
        vmax = np.ceil(vmax / step) * step
        return [vmin, vmax]

    lims = nice_limits(raw_min, raw_max)
    if symmetric:
        largest=max([abs(lims[0]), lims[1]])
        lims[0]=-largest
        lims[1]=largest

    return lims    


def nice_max(x):
    # 1. Get global min and max
    data_max = np.nanmax(x)

    # 2. Add padding
    padding = 0.05 * (data_max)
    raw_max = data_max + padding

    # 3. Round to "nice" numbers (nearest power of 10 multiples)
    def nice_limits(vmax):
        rng = vmax
        exp = int(np.floor(np.log10(rng)))  # order of magnitude
        step = 10 ** exp
        vmax = np.ceil(vmax / step) * step
        return vmax

    lims = nice_limits(raw_max)

    return lims    
    
def getSkillMask(_vars, _skillscores):
     if gl.targetType=="grid":
        #no need to use geodata as _scores unstacks to proper xarray
        dataxr=_vars.unstack().to_xarray().transpose("category","lat","lon")
        skillxr=_skillscores.unstack().to_xarray().transpose("category","lat","lon")
        outdata=[]
        for cat in dataxr.category.values:
            if cat in skillMasks.keys(): 
                dat=dataxr[cat]
                skillvar,skillthresh,skillsign=skillMasks[cat]
                skilldat=skillxr[cat]
                if sign==">":
                    mask=skilldat>skillthresh
                else:
                    mask=skilldat<skillthresh

                dat=dat.where(mask)
            outdata.append(dat)
        if len(outdata)>0:
            outdata=xr.concat(outdata)

     if gl.targetType=="zones":
        outdata=[]
        for cat in _vars.index:
            if cat in skillMasks.keys(): 
                outdata.append(_vars[cat])

     return outdata



def plotCalibDiags(calibhcstcdf, Y_obs, Y_hcst, figuresdir, forecastid):
    if gl.targetType!="grid":    
        allprobs=calibhcstcdf.values.reshape(-1,*Y_hcst.shape)
        #distribution here has to be empirical, this is how the terciles are calculated
        obsdistrib=fit_dist_to_arr(Y_obs.values.astype(float), dist="empirical")
        obsprobs=get_cdf(Y_obs.values.astype(float),obsdistrib, dist="empirical")

        catnames=["below normal","normal","above normal"]

        ncat=calibhcstcdf.shape[0]
        obscat=(obsprobs*ncat).astype(int)
        obscat[obscat==ncat]=ncat-1

        for loc,name in enumerate(Y_obs.columns):
            probs=allprobs[:,:,loc]
            obs_idx=obscat[:,loc]

            # Rank histogram
            counts = np.zeros(probs.shape[0])
            for i in range(len(obscat)):
                counts[obs_idx[i]] += 1

            fig=plt.figure(figsize=(5,3))
            pl=fig.add_subplot(1,1,1)

            pl.bar(np.arange(1, ncat+1), counts)
            pl.set_xticks(range(1, ncat+1))
            pl.set_xticklabels(catnames)
            pl.set_xlabel("Forecast category \n(in {} years of hindcast data)".format(Y_hcst.shape[0]))
            pl.set_ylabel("Count of observations")
            pl.set_title("Rank Histogram\nregion: {}".format(name))
            plt.subplots_adjust(bottom=0.25, top=0.8)
            plt.savefig("{}/calibration-diags_{}_{}.jpg".format(figuresdir, sanitize_string(name), forecastid))
            plt.close()






def plotTercileProbMap(probfcst, predictandhcst, geodata, mapsdir, forecastid, annotation, overlayvector=None):
    if gl.config["predictandCategory"]=="rainfall":
        _cmap_above="BrBG"
        _cmap_below="BrBG_r"
    else:
        _cmap_above="RdBu_r"
        _cmap_below="RdBu"
    
    cbar_label_dry="probablity [%]\nbelow normal"
    cbar_label_norm="probablity [%]\nnormal"
    cbar_label_wet="probablity [%]\nabove normal"

    
    #calculating max value
    data=probfcst.values.reshape(-1,predictandhcst.shape[1])
    row_idx = np.argmax(data, axis=0)
    data_max=np.max(data, 0)
    data=(data_max+row_idx)*100

    

    fig=plt.figure(figsize=(5,5))
    pl=fig.add_subplot(1,1,1, projection=ccrs.PlateCarree())

    levels_dry=[33,40,50,60,70,100]
    ncat=len(levels_dry)
    cmap_dry = plt.get_cmap(_cmap_below)
    cols_dry = cmap_dry(np.linspace(0.53, 0.9, ncat-1))
    cmap_dry, norm_dry = colors.from_levels_and_colors(levels_dry, cols_dry, extend="neither")



    levels_norm=[133,140,150,170,200]
    ncat=len(levels_norm)
    cmap_norm = plt.get_cmap("Greys")
    cols_norm = cmap_norm(np.linspace(0, 0.5, ncat-1))
    cmap_norm, norm_norm = colors.from_levels_and_colors(levels_norm, cols_norm, extend="neither")



    levels_wet=[233,240,250,260,270,300]
    ncat=len(levels_wet)
    cmap_wet = plt.get_cmap(_cmap_above)
    cols_wet = cmap_wet(np.linspace(0.53, 0.9, ncat-1))
    cmap_wet, norm_wet = colors.from_levels_and_colors(levels_wet, cols_wet, extend="neither")


    if gl.targetType=="grid":
        cont=True

        datadf=predictandhcst.iloc[0:1,:].copy()
        datadf[:]=data
        dataxr=datadf.unstack().to_xarray().transpose("time","lat","lon").sortby('lon').sortby("lat")

        m_dry=dataxr.plot(cmap=cmap_dry, vmin=33,vmax=100, add_colorbar=False, norm=norm_dry, ax=pl)
        m_norm=dataxr.plot(cmap=cmap_norm, vmin=133,vmax=200, add_colorbar=False, norm=norm_norm, ax=pl)
        m_wet=dataxr.plot(cmap=cmap_wet, vmin=233,vmax=300, add_colorbar=False, norm=norm_wet, ax=pl)

    else:
        
        data=data.reshape(1,-1)
        
        data=pd.DataFrame(data, index=["probability"], columns=predictandhcst.columns)
        geodata=geodata.copy().join(data.T)

        m_dry=geodata.plot(column="probability", cmap=cmap_dry, legend=False, ax=pl, norm=norm_dry, vmin=33, vmax=100)
        m_norm=geodata.plot(column="probability", cmap=cmap_norm, legend=False, ax=pl, norm=norm_norm, vmin=133, vmax=200)
        m_wet=geodata.plot(column="probability", cmap=cmap_wet, legend=False, ax=pl, norm=norm_wet, vmin=233, vmax=300)

        #geodata.boundary.plot(ax=pl)


    cbar_label="below\nnormal"
    ax=fig.add_axes([0.82,0.25,0.02,0.15])
    cbar = plt.cm.ScalarMappable(norm=norm_dry, cmap=cmap_dry)
    ax_cbar = fig.colorbar(cbar, cax=ax, label=cbar_label, extend="neither")

    ticklabels=levels_dry
    ax_cbar.ax.set_yticklabels([x-0 for x in ticklabels])
    ax_cbar.ax.tick_params(labelsize=6)
    ax_cbar.ax.tick_params(size=0)



    cbar_label="normal"
    ax=fig.add_axes([0.82,0.45,0.02,0.1])
    cbar = plt.cm.ScalarMappable(norm=norm_norm, cmap=cmap_norm)
    ax_cbar = fig.colorbar(cbar, cax=ax, label=cbar_label, extend="neither")

    ticklabels=levels_norm
    ax_cbar.ax.set_yticklabels([x-100 for x in ticklabels])
    ax_cbar.ax.tick_params(labelsize=6)
    ax_cbar.ax.tick_params(size=0)


    cbar_label="above\nnormal"
    ax=fig.add_axes([0.82,0.60,0.02,0.15])     
    cbar = plt.cm.ScalarMappable(norm=norm_wet, cmap=cmap_wet)        
    ax_cbar = fig.colorbar(cbar, cax=ax, label=cbar_label, extend="neither")

    ticklabels=levels_wet
    ax_cbar.ax.set_yticklabels([x-200 for x in ticklabels])
    ax_cbar.ax.tick_params(labelsize=6)
    ax_cbar.ax.tick_params(size=0)

    
    if not overlayvector is None:
        overlayvector.boundary.plot(ax=pl, color='black', linewidth=0.3)
    
    title="Tercile probabilities"
    
    pl.set_title(title)
    
    pl.text(0,-0.01,annotation,fontsize=6, transform=pl.transAxes, va="top")
    
    plt.subplots_adjust(right=0.8)
    outfile=Path(mapsdir,"{}_tercile-probability_{}.jpg".format(gl.config['predictandVar'], forecastid))
    
    plt.savefig(outfile)

    plt.close()
    

def plotSmoothTercileProbMap(probfcst, predictandhcst, geodata, mapsdir, forecastid, annotation, overlayvector=None, sigma=2, enhanced=True):
    
    if gl.targetType!="grid":
        showMessage("can only do for gridded data. skipping...")
    else:
        
        #plotting now
        _cmap_above="BrBG"
        _cmap_below="BrBG"
        
        cbar_label_dry="probablity [%]\nbelow normal"
        cbar_label_wet="probablity [%]\nabove normal"
        data=probfcst.stack(level=["lat","lon"], future_stack=True).to_xarray().sortby("lat").sortby("lon")
        probs=-data["below"]
        probs=probs.where(data["above"]<data["below"],data["above"])
        probs=probs.rio.write_crs("epsg:4326")

        tempsmooth=nan_gaussian_smooth(probs, sigma=sigma)
        
        #back to xarray
        smooth=probs.copy()
        smooth[:]=tempsmooth
        
        smooth=smooth.rio.write_crs("epsg:4326")
        
        fig=plt.figure(figsize=(5,5))
        pl=fig.add_subplot(1,1,1, projection=ccrs.PlateCarree())
        
        vmin_dry,vmax_dry=-1,-0.33
        levels_dry=[-0.33,-0.40,-0.50,-0.60,-0.70,-1.00][::-1]
        ncat=len(levels_dry)
        cmap_dry = plt.get_cmap(_cmap_below)
        cols_dry = cmap_dry(np.linspace(0.1, 0.45, ncat-1))
        cmap_dry, norm_dry = colors.from_levels_and_colors(levels_dry, cols_dry, extend="neither")
        
        
        vmin_wet,vmax_wet=0.33,1
        levels_wet=[0.33,0.40,0.50,0.60,0.70,1.0]
        ncat=len(levels_wet)
        cmap_wet = plt.get_cmap(_cmap_above)
        cols_wet = cmap_wet(np.linspace(0.55, 0.9, ncat-1))
        cmap_wet, norm_wet = colors.from_levels_and_colors(levels_wet, cols_wet, extend="neither")
        

        if enhanced:
            
            scale = probs.std() / np.nanstd(smooth)   # or store this scale factor if data_filled isn't available later
            #toplot=probs.copy()
            toplot = np.clip(smooth * scale.data, -1, 1)
                               
        else:
            toplot=smooth
            
        m_wet=toplot.plot(cmap=cmap_wet, vmin=vmin_wet,vmax=vmax_wet, add_colorbar=False, norm=norm_wet, ax=pl)
        m_dry=toplot.plot(cmap=cmap_dry, vmin=vmin_dry,vmax=vmax_dry, add_colorbar=False, norm=norm_dry, ax=pl)
    
        pl.contour(toplot.lon, toplot.lat, toplot[0,:], levels=[-1,-0.7,-0.6,-0.5,-0.4,-0.33,0.33,0.4,0.5,0.6,0.7,1], linewidths=1, colors="grey", linestyles="dashed")
        
        if not overlayvector is None:
            overlayvector.boundary.plot(ax=pl, color='black', linewidth=0.3)

        
        
        cbar_label="below\nnormal"
        ax=fig.add_axes([0.82,0.25,0.02,0.15])
        cbar = plt.cm.ScalarMappable(norm=norm_dry, cmap=cmap_dry)
        ax_cbar = fig.colorbar(cbar, cax=ax, label=cbar_label, extend="neither")
        
        ticklabels=levels_dry
        ax_cbar.ax.set_yticklabels([int(-x*100) for x in ticklabels])
        ax_cbar.ax.tick_params(labelsize=6)
        ax_cbar.ax.tick_params(size=0)
        
        
        cbar_label="above\nnormal"
        ax=fig.add_axes([0.82,0.60,0.02,0.15])     
        cbar = plt.cm.ScalarMappable(norm=norm_wet, cmap=cmap_wet)        
        ax_cbar = fig.colorbar(cbar, cax=ax, label=cbar_label, extend="neither")
        
        ticklabels=levels_wet
        ax_cbar.ax.set_yticklabels([int(x*100) for x in ticklabels])
        ax_cbar.ax.tick_params(labelsize=6)
        ax_cbar.ax.tick_params(size=0)
        
        
        if not overlayvector is None:
            overlayvector.boundary.plot(ax=pl, color='black', linewidth=0.3)
        
        title="Tercile probabilities"
        
        pl.set_title(title)
        
        pl.text(0,-0.01,annotation,fontsize=6, transform=pl.transAxes, va="top")
        
        plt.subplots_adjust(right=0.8)
        
        outfile=Path(mapsdir,"{}_tercile-probability-smooth_{}.jpg".format(gl.config['predictandVar'], forecastid))
        
        plt.savefig(outfile)
        
        plt.close()
        



def nan_gaussian_smooth(data, sigma=2):
    """
    Apply Gaussian filter to data with NaNs handled properly.
    NaNs remain NaN in output, edges are preserved.
    """
    # Create weights (1 where data is valid, 0 where NaN)
    data = np.array(data, dtype=float)
    nan_mask = np.isnan(data)
    #filling with 0
    data_filled = np.where(nan_mask, 0, data)
    
    #values have to be float, because smoothing will generate fractions of weights
    weights = np.where(nan_mask, 0., 1.)

    # Apply Gaussian filter to data and weights
    smooth_data = gaussian_filter(data_filled, sigma=sigma, mode='nearest')
    smooth_weights = gaussian_filter(weights, sigma=sigma, mode='nearest')

    # Avoid division by zero
    with np.errstate(invalid='ignore'):

        #calculate weighted smooth
        smooth_data = smooth_data / smooth_weights

    #mask the original nans
    smooth_data[nan_mask]=np.nan
    
    return smooth_data

    
    
    
def plotMaps(_scores, _geoData, _figuresDir, _forecastID, _zonesVector, annotation, _overlayVector=None):
    
    if gl.targetType=="grid":
        #no need to use geodata as _scores unstacks to proper xarray
        scoresxr=_scores.unstack().to_xarray().transpose("category","lat","lon")
        for score in scoresxr.category.values:
            showMessage(score)
            outfile=Path(_figuresDir,"{}_{}_{}.jpg".format(gl.config['predictandVar'], score, _forecastID))
            showMessage("plotting {}".format(outfile))
            fig=plt.figure(figsize=(5,5))
            pl=fig.add_subplot(1,1,1, projection=ccrs.PlateCarree())

            colorbar=False

            cm=colormaps[score]
            title=cm["title"]
            cmap=cm["cmap"]
            symmetric=cm["symmetric"]
            vmin=cm["vmin"]
            vmax=cm["vmax"]
            levels=cm["levels"]
            nlev=cm["nlev"]
            
            whitelev=cm["whitelev"]
            cbar_label=cm["cbar_label"]

            extend=cm["extend"]
            tick_labels=cm["tick_labels"]

            if isinstance(cmap, dict):
                cmap=cmap[gl.config["predictandCategory"]]
                
             
            dat2plot=scoresxr.sortby("lat").sortby("lon").sel(category=score)
            
            if vmax=="auto":
                if vmin=="auto":
                    vmin,vmax=nice_minmax(dat2plot.data.flatten(), None,True)
                else:
                    vmax=nice_max(dat2plot.data.flatten())
                    
            cm["vmin"]=vmin
            cm["vmax"]=vmax

            if cbar_label=="unit":
                cbar_label=gl.config["predictandUnit"]
                
            # add colorbar
            if cm["categorized"]:
                cmap,norm,levels=getCmap(vmin,vmax,nlev,cmap,extend,whitelev)
            else:
                norm = colors.Normalize(vmin=vmin, vmax=vmax)

            m=dat2plot.plot(cmap=cmap, vmin=vmin,vmax=vmax, add_colorbar=colorbar)
            
            ax=fig.add_axes([0.82,0.15,0.03,0.7])
            
            if levels is None:
                cbar = fig.colorbar(m, cax=ax, label=cbar_label, extend=extend)
            else:
                cbar = fig.colorbar(m, cax=ax,ticks=levels, label=cbar_label, extend=extend)
                
            if tick_labels is not None:
                cbar.ax.set_yticklabels(tick_labels)
                
                
            if not _zonesVector is None:
                _zonesVector.boundary.plot()

            if not _overlayVector is None:
                _overlayVector.boundary.plot(ax=pl, color='black', linewidth=0.3)
                
            pl.set_title(title)
            
#            ab = AnnotationBbox(m, (0.99, 0.99), xycoords=pl.transAxes, box_alignment=(1,1), frameon=False)
#            pl.add_artist(ab)
            pl.text(0,-0.01,annotation,fontsize=6, transform=pl.transAxes, va="top")
            
            plt.subplots_adjust(right=0.8)
            plt.savefig(outfile)
            plt.close()
            #showMessage("done")
         
    if gl.targetType=="zones":
        _geodata=_geoData.copy().join(_scores.T)
        for score in _scores.index:
            outfile=Path(_figuresDir,"{}_{}_{}.jpg".format(gl.config['predictandVar'], score, _forecastID))
            #showMessage("plotting {}".format(outfile))
            fig=plt.figure(figsize=(5,5))
            pl=fig.add_subplot(1,1,1, projection=ccrs.PlateCarree())

            colorbar=False
            cm=colormaps[score]

            cm=colormaps[score]
            title=cm["title"]
            cmap=cm["cmap"]
            symmetric=cm["symmetric"]
            vmin=cm["vmin"]
            vmax=cm["vmax"]
            levels=cm["levels"]
            nlev=cm["nlev"]
            
            whitelev=cm["whitelev"]
            cbar_label=cm["cbar_label"]

            extend=cm["extend"]
            tick_labels=cm["tick_labels"]

            if isinstance(cmap, dict):
                cmap=cmap[gl.config["predictandCategory"]]
            
            if vmax=="auto":
                if vmin=="auto":
                    vmin,vmax=nice_minmax(_geodata[score].values.flatten(), None,True)
                else:
                    vmax=nice_max(_geodata[score].values.flatten())
                    
            #have to feed back, because new values are used later
            cm["vmin"]=vmin
            cm["vmax"]=vmax
                        
            # add colorbar
            if cm["categorized"]:
                cmap,norm,levels=getCmap(vmin,vmax,nlev,cmap,extend,whitelev)
            else:
                norm = colors.Normalize(vmin=vmin, vmax=vmax)
                
            cbar = plt.cm.ScalarMappable(norm=norm, cmap=cmap)

            m=_geodata.plot(column=score, cmap=cmap, legend=False, ax=pl, norm=norm)
            _geodata.boundary.plot(ax=pl)
            
            ax=fig.add_axes([0.82,0.15,0.03,0.7])
            
            
            if levels is None:
                # add colorbar
                ax_cbar = fig.colorbar(cbar, cax=ax, label=cbar_label, extend=extend)
            else:
                ax_cbar = fig.colorbar(cbar, cax=ax,ticks=levels, label=cbar_label, extend=extend)
                
            if tick_labels is not None:
                ax_cbar.ax.set_yticklabels(tick_labels)
            
            pl.set_title(title)

            if not _overlayVector is None:
                _overlayVector.boundary.plot(ax=pl, color='black', linewidth=0.3)
                
            pl.text(0,-0.01,annotation,fontsize=6, transform=pl.transAxes, va="top")
                
            plt.subplots_adjust(right=0.8)                
            plt.savefig(outfile)
            plt.close()
            #showMessage("done")
            
    if gl.targetType=="points":
        _geodata=_geoData.copy().join(_scores.T)
        for score in _scores.index:
            outfile=Path(_figuresDir, "{}_{}_{}.jpg".format(gl.config['predictandVar'], score, _forecastID))
            #showMessage("plotting {}".format(outfile))
            fig=plt.figure(figsize=(5,5))
            pl=fig.add_subplot(1,1,1, projection=ccrs.PlateCarree())
            
            colorbar=False
            cm=colormaps[score]
            title=cm["title"]
            cmap=cm["cmap"]
            vmin=cm["vmin"]
            vmax=cm["vmax"]
            levels=cm["levels"]
            nlev=cm["nlev"]
            whitelev=cm["whitelev"]
            
            if isinstance(cmap, dict):
                cmap=cmap[gl.config["predictandCategory"]]

            if vmax=="auto":
                if vmin=="auto":
                    vmin,vmax=nice_minmax(_geodata[score].values.flatten(), None,True)
                else:
                    vmax=nice_max(_geodata[score].values.flatten())
                    
            cm["vmin"]=vmin
            cm["vmax"]=vmax
            
            cbar_label=cm["cbar_label"]
            extend=cm["extend"]
            tick_labels=cm["tick_labels"]
            
            # add colorbar
            if cm["categorized"]:
                cmap,norm,levels=getCmap(vmin,vmax,nlev,cmap,extend,whitelev)
            else:
                norm = colors.Normalize(vmin=vmin, vmax=vmax)
            
            m=_geodata.plot(column=score, cmap=cmap, legend=False, ax=pl, edgecolor='black', linewidth=0.5)
            
            ax=fig.add_axes([0.82,0.15,0.03,0.7])
            
            # add colorbar
            norm = colors.Normalize(vmin=vmin, vmax=vmax)
            cbar = plt.cm.ScalarMappable(norm=norm, cmap=cmap)

            if levels is None:
                # add colorbar
                ax_cbar = fig.colorbar(cbar, cax=ax, label=cbar_label, extend=extend)
            else:
                ax_cbar = fig.colorbar(cbar, cax=ax,ticks=levels, label=cbar_label, extend=extend)
                
            if tick_labels is not None:
                ax_cbar.ax.set_yticklabels(tick_labels)
                
            
            if not _zonesVector is None:
                _zonesVector.boundary.plot(ax=pl)
                
            if not _overlayVector is None:
                _overlayVector.boundary.plot(ax=pl, color='black', linewidth=0.3)
                
            pl.set_title(title)
            
            pl.text(0,-0.01,annotation,fontsize=6, transform=pl.transAxes, va="top")
                
            plt.subplots_adjust(right=0.8)
            plt.savefig(outfile)
            plt.close()
            #showMessage("done")   

            
            
            
            
def plotTimeSeries(_dethcst,_obs, _detfcst, _tercthresh, _figuresdir, _forecastid, annotation):
    if gl.targetType in ["zones","points"]:
        for entry in _obs.columns:
            _entry=sanitize_string(str(entry))
            outfile=Path(_figuresdir,"{}_{}_{}.jpg".format(gl.config['predictandVar'], _entry, _forecastid))

            fig=plt.figure(figsize=(10,4))
            pl=fig.add_subplot(1,1,1)

            _obs[entry].plot(marker="o", label="observed", markersize=3)
            _dethcst[entry].plot(label="deterministic hindcast", markersize=3)
            _detfcst["value"][entry].plot(marker="o",label="forecast", markersize=8)
            pl.axhline(_tercthresh.loc[0.33][entry], color="0.6")
            pl.axhline(_tercthresh.loc[0.66][entry], color="0.6", label="climatological terciles")
            pl.axhline(_tercthresh.loc[0.50][entry], color="0.8", label="climatological median")

            pl.axvline(pd.to_datetime("{}-01-01".format(gl.config["climStartYr"])), color="0.9", label="climatological period")
            pl.axvline(pd.to_datetime("{}-12-31".format(gl.config["climEndYr"])), color="0.9", label="climatological period")
            pl.set_title("Hindcast and forecast for {} in {} in region: {}".format(gl.config["predictandVar"], gl.config["fcstTargetSeas"],entry))
            pl.set_xlim((_obs.index[0]-pd.offsets.YearBegin(2)).strftime("%Y-%m-%d"), (_detfcst.index[0]+pd.offsets.YearBegin(2)).strftime("%Y-%m-%d")
)

            pl.text(0,-0.15,annotation,fontsize=6, transform=pl.transAxes, va="top")
            plt.legend(loc=(1.05, 0.3))
            
            plt.subplots_adjust(bottom=0.25, right=0.7)
            plt.savefig(outfile)            
            plt.close()
        #showMessage("done")
    else:    
        showMessage("Forecasting target is a grid, time series cannot be plotted.", "INFO")



def plotDiagsCCA(_regressor, predictorhcst, predictandhcst, _geodata, _diagsdir, _forecastid, annotation):
    #plotting predictor scores
    canpatX=_regressor.can_pattern_X 

    canpatX=pd.DataFrame(canpatX, index=predictorhcst.columns, columns=["Mode{}".format(x+1) for x in range(canpatX.shape[1])])
    canpatX=canpatX.to_xarray().sortby("lat").sortby("lon")

    for pc in canpatX.data_vars:
        outfile=Path(_diagsdir,"cannonical-pattern_predictor_{}_{}.jpg".format(pc,_forecastid))
        #showMessage("plotting {}".format(outfile))

        fig=plt.figure(figsize=(10,4))

        pl=fig.add_subplot(1,1,1, projection=ccrs.PlateCarree())

        canpatX[pc].plot(ax=pl)
        pl.set_title("Predictor's {} pattern".format(pc))

        pl.text(0.1,-0.15,annotation,fontsize=6, transform=pl.transAxes, va="top")

        plt.subplots_adjust(bottom=0.25)
        plt.savefig(outfile)            
        plt.close()

    if gl.targetType=="grid":
        canpatY=_regressor.can_pattern_Y
        
        canpatY=pd.DataFrame(canpatY, index=predictandhcst.columns, columns=["Mode{}".format(x+1) for x in range(canpatY.shape[1])])
        canpatY=canpatY.to_xarray().sortby("lat").sortby("lon")

        for pc in canpatY.data_vars:
            outfile=Path(_diagsdir,"cannonical-pattern_predictand_{}_{}.jpg".format(pc,_forecastid))
            #showMessage("plotting {}".format(outfile))

            fig=plt.figure(figsize=(10,4))

            pl=fig.add_subplot(1,1,1, projection=ccrs.PlateCarree())

            canpatY[pc].plot(ax=pl)
            pl.set_title("Predictand's {} pattern \n{}".format(pc, _forecastid))

            pl.text(0.1,-0.15,annotation,fontsize=6, transform=pl.transAxes, va="top")

            plt.subplots_adjust(bottom=0.25)
            plt.savefig(outfile)            
            plt.close()
        

    scoresX=_regressor.scoresX
    scoresX=pd.DataFrame(scoresX, index=predictandhcst.index, columns=["Mode{}".format(x+1) for x in range(scoresX.shape[1])])

    scoresY=_regressor.scoresY
    scoresY=pd.DataFrame(scoresY, index=predictandhcst.index, columns=["Mode{}".format(x+1) for x in range(scoresY.shape[1])])

    for mode in scoresX.columns:
        outfile=Path(_diagsdir,"CCA-scores_{}_{}.jpg".format(mode, _forecastid))
        #showMessage("plotting {}".format(outfile))

        fig=plt.figure(figsize=(7,4))
        pl=fig.add_subplot(1,1,1)

        scoresX[mode].plot(ax=pl, label="predictor")
        scoresY[mode].plot(ax=pl, label="predictand")
        pl.set_title("Scores of CCA {}".format(mode))
        plt.legend()

        pl.text(0.1,-0.15,annotation,fontsize=6, transform=pl.transAxes, va="top")

        plt.subplots_adjust(bottom=0.25)
        plt.savefig(outfile)            
        plt.close()

        
    #plotting correlations        
    outfile=Path(_diagsdir,"CCA-correlations_{}.jpg".format( _forecastid))
    #showMessage("plotting {}".format(outfile))
    
    corrs = [np.corrcoef(scoresX.iloc[:, i], scoresY.iloc[:, i])[0,1] for i in range(scoresX.shape[1])]

    fig=plt.figure(figsize=(7,4))
    pl=fig.add_subplot(1,1,1)

    bars=pl.bar(range(1, len(corrs)+1), corrs)
    # annotate each bar with its value
    for bar, val in zip(bars, corrs):
        height = bar.get_height()
        pl.text(bar.get_x() + bar.get_width()/2, height + 0.02, f"{val:.2f}",
                ha='center', va='bottom')
    pl.set_xticks(range(1,len(corrs)+1))
    pl.set_ylim(0,1.1)
    pl.set_xlabel("Canonical mode")
    pl.set_ylabel("Canonical correlation")
    pl.set_title("Strength of canonical correlations")

    pl.text(0.1,-0.15,annotation,fontsize=6, transform=pl.transAxes, va="top")
    plt.subplots_adjust(bottom=0.25)
    plt.savefig(outfile)            
    plt.close()

    
    
    
def plotDiagsPCR(_regressor, predictorhcst, predictandhcst, _geodata, _diagsdir, _forecastid, annotation):
    #plotting predictor scores
    scores=_regressor.scores
    scores=pd.DataFrame(scores, index=predictandhcst.index, columns=["PC{}".format(x+1) for x in range(scores.shape[1])])

    outfile=Path(_diagsdir,"PCA-scores_predictand_{}.jpg".format(_forecastid))
    #showMessage("plotting {}".format(outfile))

    fig=plt.figure(figsize=(7,4))
    pl=fig.add_subplot(1,1,1)

    scores.plot(ax=pl)
    pl.set_title("Scores of retained PCs".format())

    pl.text(0.1,-0.15,annotation,fontsize=6, transform=pl.transAxes, va="top")
    plt.subplots_adjust(bottom=0.25)
    plt.savefig(outfile)            
    plt.close()


    #plotting loadings
    loadings=_regressor.loadings

    loadings=pd.DataFrame(loadings, index=predictorhcst.columns, columns=["PC{}".format(x+1) for x in range(loadings.shape[1])])
    loadings=loadings.to_xarray().sortby("lat").sortby("lon")

    
    for pc in loadings.data_vars:
        outfile=Path(_diagsdir,"{}-loadings_predictand_{}.jpg".format(pc,_forecastid))
        #showMessage("plotting {}".format(outfile))

        fig=plt.figure(figsize=(10,4))
        
        pl=fig.add_subplot(1,1,1, projection=ccrs.PlateCarree())

        loadings[pc].plot(ax=pl)
        pl.set_title("{} loadings".format(pc))

        pl.text(0,-0.15,annotation,fontsize=6, transform=pl.transAxes, va="top")
        plt.subplots_adjust(bottom=0.25)
        plt.savefig(outfile)            
        plt.close()
        
        

def plotDiagsRegression(predictandhcst, cvhcst, esthcst, tercthresh, detfcst, _diagsdir, _forecastid, annotation):
    
    if gl.targetType!="grid":
        for entry in predictandhcst.columns:
            entryw=sanitize_string(str(entry))
            outfile=Path(_diagsdir,"regression-diags_{}_{}.jpg".format(entryw,_forecastid))
            fig=plt.figure(figsize=(10,6))

            pl=fig.add_subplot(2,3,1)

            obs=predictandhcst.loc[:,entry]
            hcst=cvhcst["value"].loc[:,entry]

            xmin,xmax=nice_minmax(obs,hcst)

            pl.plot(obs,hcst,"o")
            pl.set_ylim(xmin,xmax)
            pl.set_xlim(xmin,xmax)

            pl.set_xlabel("observations")
            pl.set_ylabel("out-of-sample forecast")

            pl.set_title("out-of-sample forecast \nvs observations")



            pl=fig.add_subplot(2,3,2)

            hcst=esthcst["value"].loc[:,entry]
            xmin,xmax=nice_minmax(obs,hcst)

            pl.plot(obs,hcst,"o")
            pl.set_ylim(xmin,xmax)
            pl.set_xlim(xmin,xmax)

            pl.set_xlabel("observations")
            pl.set_ylabel("in-sample estimate")

            pl.set_title("in-sample estimate \nvs observations")

            pl=fig.add_subplot(2,3,3)

            
            
            
            obs=predictandhcst.loc[:,entry]
            hcst=cvhcst["value"].loc[:,entry]
            resid=hcst-obs
            
            hcstfit=esthcst["value"].loc[:,entry]
            residfit=hcstfit-obs

            xmin,xmax=nice_minmax(obs,resid)

            pl.plot(obs,resid,"o")
            pl.set_ylim(xmin,xmax)
            pl.set_xlim(xmin,xmax)

            pl.set_xlabel("observations")
            pl.set_ylabel("out-of-sample residuals")

            pl.set_title("out-of-sample\n residual vs observations")



            
            pl=fig.add_subplot(2,3,4)

            pl.hist(resid, label="out-of-sample", alpha=0.5)
            pl.hist(residfit, label="in-sample", alpha=0.5)

            pl.set_xlabel("residuals")
            pl.set_ylabel("frequency")

            pl.set_title("error distribution")

            plt.legend()
            
            
            
            pl=fig.add_subplot(2,3,5)
            
            hcst=cvhcst["value"].loc[:,entry]
            
            resid=hcst-obs
            
            fcst=detfcst["value"].loc[:,entry]

            error=fcst.values+resid
            
            pl.hist(error, label="forecast error", alpha=0.5)
            
            pl.axvline(fcst.values, color="red", label="forecast")
            
            pl.axvline(tercthresh.loc[0.33][entry], color="blue", label="terciles")
            pl.axvline(tercthresh.loc[0.66][entry], color="blue", label="_terciles")
            

            pl.set_xlabel("value")
            pl.set_ylabel("frequency")
            plt.legend()
            pl.set_title("forecast error distribution")

            
            plt.suptitle("zone/location: {} \n{}\n".format(entry, _forecastid))
            
            pl.text(1.1,0,annotation,fontsize=6, transform=pl.transAxes, va="top")
            plt.subplots_adjust(top=0.85, left=0.1, right=0.9, wspace=0.5, hspace=0.5)
            plt.savefig(outfile)
            plt.close()



def getTercCategory(_data):
    if gl.targetType=="grid":
        temp=_data.stack(level=[1,2], future_stack=True).idxmax(axis=1).unstack(level=[1,2]).map(lambda x: terc2num[x])
        #add a level to multiindex
        temp.columns=pd.MultiIndex.from_tuples([('tercile_category',) + col for col in temp.columns], names=["category"] + list(temp.columns.names))

    else:
        temp=_data.stack(future_stack=True).idxmax(axis=1).unstack().map(lambda x: terc2num[x])
        temp.columns=pd.MultiIndex.from_tuples([('tercile_category',col) for col in temp.columns], names=["category",temp.columns.name])

    return temp




def getCemCategory(_data):
    if gl.targetType=="grid":
    
        stacked = _data.stack(level=[1, 2], future_stack=True)

        # Convert to numpy array
        vals = stacked.to_numpy()

        # argsort sorts ascending → take [:, ::-1] for descending
        order_idx = np.argsort(vals, axis=1)[:, ::-1]

        # Get the original column labels in sorted order
        col_array = np.array(stacked.columns)
        ordered_labels = col_array[order_idx]

        # Make a DataFrame with desired column names
        order = pd.DataFrame(
            ordered_labels[:, :3],  # top 3
            index=stacked.index,
            columns=["first", "second", "third"]
        )

        temp=order["first"].copy()
        sel=temp=="normal"
        temp[sel]="normal-to-"+order["second"][sel]
        temp=temp.map(lambda x: cem2num[x])
        temp=temp.unstack(level=["lat","lon"])
        temp.columns=pd.MultiIndex.from_tuples([('cem_category',) + col for col in temp.columns], names=["category"] + list(temp.columns.names))
    else:
        stacked = _data.stack(future_stack=True)

        # Convert to numpy array
        vals = stacked.to_numpy()

        # argsort sorts ascending → take [:, ::-1] for descending
        order_idx = np.argsort(vals, axis=1)[:, ::-1]

        # Get the original column labels in sorted order
        col_array = np.array(stacked.columns)
        ordered_labels = col_array[order_idx]

        # Make a DataFrame with desired column names
        order = pd.DataFrame(
            ordered_labels[:, :3],  # top 3
            index=stacked.index,
            columns=["first", "second", "third"]
        )

        temp=order["first"].copy()
        sel=temp=="normal"
        temp[sel]="normal-to-"+order["second"][sel]
        temp=temp.map(lambda x: cem2num[x])
        
        temp=temp.unstack()
        temp.columns=pd.MultiIndex.from_tuples([('cem_category',col) for col in temp.columns], names=["category", temp.columns.name])

    return temp  



class PCRegressor(BaseEstimator, RegressorMixin):
    
    def __init__(self, regressor_name=None, fit_intercept=True, max_fraction=0.15, pca_explained_var=0.95, **regressor_kwargs):
        self.max_fraction = max_fraction
        self.fit_intercept = fit_intercept
        self.pca_explained_var = pca_explained_var
        self.regressor_name = regressor_name
        self.regressor_kwargs = regressor_kwargs
        self.scaleX=StandardScaler()
        self.pcaX = PCA()
        self.reg=self._get_regressor()
        
    def _get_regressor(self):

        if self.regressor_name not in regressors:
            raise ValueError(f"Unknown regressor '{self.regressor_name}'.")
        reg_class=regressors[self.regressor_name]
        
        # Inspect constructor to see if 'fit_intercept' is accepted
        sig = inspect.signature(reg_class.__init__)
        kwargs = self.regressor_kwargs.copy()
        if 'fit_intercept' in sig.parameters:
            kwargs['fit_intercept'] = self.fit_intercept
            self.supports_intercept=True
        else:
            self.supports_intercept=False
            
        return reg_class(**kwargs)
        
    def fit(self, X, Y):
        
        #scaling the predictor
        X_std=self.scaleX.fit_transform(X)
        
        #PCA on predictor
        #X_c holds scores
        X_c = self.pcaX.fit_transform(X_std)
        
        #selecting PCA components
        #
        cumvar = np.cumsum(self.pcaX.explained_variance_ratio_)
        n_samples=X.shape[0]
        
        #number of components should not exceed a fraction of the number of data
        max_data_comp=int(self.max_fraction*n_samples)
        
        # number of components that explain target fraction of variance
        max_var_comp=np.argmax(cumvar >= self.pca_explained_var) + 1
        
        #final number of components - the lower of the two
        ncompX=int(np.ceil(np.min([max_data_comp, max_var_comp])))
        
        X_c=X_c[:,:ncompX]
        
        #retaining scores # shape (n_samples, n_components)
        self.scores=X_c
        
        #retaining loadings # shape (n_features, n_components)
        self.loadings = self.pcaX.components_.T[:,:ncompX]
        
        #retaining number of components kept
        self.ncompX=ncompX
        
        #fitting regression model
        self.reg.fit(X_c, Y)
        
        return self

    
    def predict(self, X):
        #scale as per fitted model    
        X_c = self.scaleX.transform(X)
        #PCA trasform as per fitted model
        X_c = self.pcaX.transform(X_c)
        #select only retained PC components
        X_c=X_c[:,:self.ncompX]
        
        #predict with model
        Y_pred=self.reg.predict(X_c)

        return Y_pred
    
    
class CCARegressor(BaseEstimator, RegressorMixin):
    
    def __init__(self, n_components=None, regressor_name=None, fit_intercept=True, max_fraction=0.15,pca_explained_var=0.95, **regressor_kwargs):
        self.n_components = n_components
        self.max_fraction = max_fraction
        self.fit_intercept = fit_intercept
        self.pca_explained_var = pca_explained_var
        self.regressor_name = regressor_name
        self.regressor_kwargs = regressor_kwargs
        self.scaleX=StandardScaler()
        self.scaleY=StandardScaler()
        self.pcaX = PCA()
        self.pcaY = PCA()
        self.reg=self._get_regressor()        
        
    def _get_regressor(self):

        if self.regressor_name not in regressors:
            raise ValueError(f"Unknown regressor '{self.regressor_name}'.")
            
        reg_class=regressors[self.regressor_name]
        
        # Inspect constructor to see if 'fit_intercept' is accepted
        sig = inspect.signature(reg_class.__init__)
        kwargs = self.regressor_kwargs.copy()
        if 'fit_intercept' in sig.parameters:
            kwargs['fit_intercept'] = self.fit_intercept
            self.supports_intercept=True
        else:
            self.supports_intercept=False
      
        return reg_class(**kwargs)

    
    def fit(self, X, Y):
        #scaling predictor and predictand        
        X_std=self.scaleX.fit_transform(X)
        Y_std=self.scaleY.fit_transform(Y)
        
        X_c = self.pcaX.fit_transform(X_std)
        cumvar = np.cumsum(self.pcaX.explained_variance_ratio_)

        # Choose number of components that explain X % - for PCA that enters CCA 
        ncompX=np.argmax(cumvar >= self.pca_explained_var) + 1
        X_c=X_c[:,:ncompX]
        self.ncompX=ncompX
        
        Y_c = self.pcaY.fit_transform(Y_std)
        cumvar = np.cumsum(self.pcaY.explained_variance_ratio_)
        
        # Choose number of components that explain Y % - for PCA that enters CCA
        ncompY = np.argmax(cumvar >= self.pca_explained_var) + 1
        Y_c=Y_c[:,:ncompY]
        self.ncompY=ncompY
        
        #setting up number of components for CCA
        n_samples=X.shape[0]
        if self.n_components is None:
            max_allowed = int(np.floor(self.max_fraction * n_samples))
            self.n_components = min(self.ncompX, self.ncompY, max_allowed)

        #initializing cca once we know how many components we need
        self.cca = CCA(n_components=self.n_components)

        #fitting CCA
        self.cca.fit(X_c, Y_c)
        X_c, Y_c = self.cca.transform(X_c, Y_c)
        
        #retaining CCA scores
        self.scoresX=X_c
        self.scoresY=Y_c
        
        #retaining canonical patterns
        self.can_pattern_X = self.pcaX.components_[:ncompX, :].T @ self.cca.x_weights_
        self.can_pattern_Y = self.pcaY.components_[:ncompY, :].T @ self.cca.y_weights_

        #fitting regression model
        self.reg.fit(X_c, Y_c)
        
        return self

    
    def predict(self, X):
        #scale    
        X_c = self.scaleX.transform(X)
        #PCA trasform
        X_c = self.pcaX.transform(X_c)
        #select only retained PC components
        X_c=X_c[:,:self.ncompX]
        #CCA transform
        X_c = self.cca.transform(X_c)  # transform only X
        
        #predict with model
        Y_c_pred=self.reg.predict(X_c)
        
        # Inverse transform to get prediction in original Y space
        #invert CCA
        Y_pred = Y_c_pred @ self.cca.y_rotations_.T
        #invert PCA
        selComponents = self.pcaY.components_[0:self.ncompY]
        Y_pred = Y_pred @ selComponents
        #invert scaling
        Y_pred = self.scaleY.inverse_transform(Y_pred)
        

        return Y_pred
    

def writeOutput(_data, _outputfile):
    if gl.targetType=="grid":
        _data=_data.rio.write_crs("epsg:4326") #adding crs
        # Add CF-compliant attributes
        _data["lat"].attrs = {
            "standard_name": "latitude",
            "units": "degrees_north"
        }
        _data["lon"].attrs = {
            "standard_name": "longitude",
            "units": "degrees_east"
        }

        _data.to_netcdf(_outputfile)
    else:
        _data.to_csv(_outputfile)
    #showMessage("written {}".format(_outputfile), "INFO")
    return    

            

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

    
def checkInputs():
    configVars=['rootDir', 'predictorYear', 'predictorMonth', 'fcstTargetSeas', 'fcstTargetYear', 'climStartYr', 'climEndYr', 'predictorExtents', 'predictorFileName', 'predictorVar', 'predictorCode', 'crossval', 'preproc', 'regression', 'timeAggregation', 'predictandFileName', 'predictandVar', 'predictandCategory', 'predictandMissingValue', 'zonesFile', 'zonesAttribute', 'zonesAggregate', 'regridPredictand', 'overlayFile', 'predictandUnit','plotMaps']

    for var in configVars:
        if not var in configVars:
            showMessage(f"config variable {var} missing", "ERROR")
            return


    if gl.config["rootDir"]=="":
        showMessage("output directory cannot be empty", "ERROR")
        return
    else:
        if not os.path.exists(gl.config["rootDir"]):
            showMessage("output directory does not exist", "ERROR")
            return    
    
    if not is_number(gl.config["predictorYear"]):
        showMessage("predictor year should be numeric", "ERROR")
        return
    
    if not is_number(gl.config["fcstTargetYear"]):
        showMessage("predictand year should be numeric", "ERROR")
        return

    if not is_number(gl.config["climEndYr"]):
        showMessage("last year of climatological period should be numeric", "ERROR")
        return
    
    if not is_number(gl.config["climStartYr"]):
        showMessage("first year of climatological period should be numeric", "ERROR")
        return
    
    if int(gl.config["climEndYr"])<=int(gl.config["climStartYr"]):
        showMessage(f"Last year of climatological should be larger than its first. Got: First: {gl.config["climStartYr"]}, Last:{gl.config["climEndYr"]}", "ERROR")
        return
        
    if int(gl.config["climEndYr"])-int(gl.config["climStartYr"])<10:
        showMessage(f"Climatological period should be longer than 10 years. Got: First: {gl.config["climStartYr"]}, Last:{gl.config["climEndYr"]}", "ERROR")
        return
        
    if gl.config["predictandFileName"]=="":
        showMessage("predictand file cannot be empty", "ERROR")
        return
    elif not os.path.exists(gl.config["predictandFileName"]):
        showMessage("predictand file does not exist", "ERROR")
        return
    
    if gl.config["predictandVar"]=="":
        showMessage("predictand variable cannot be empty", "ERROR")
        return
    
    if gl.config["zonesAggregate"]:
        if gl.config["zonesFile"]!="":
            if not os.path.exists(gl.config["zonesFile"]):
                showMessage("Aggregation to zones is selected. But zones file does not exist", "ERROR")
                return    
        
        if gl.config["zonesAttribute"]=="":
            showMessage("Aggregation to zones is selected.  But zones variable is empty", "ERROR")
            return
        
    if gl.config["overlayFile"]!="":
        if not os.path.exists(gl.config["overlayFile"]):
            showMessage("overlay file does not exist", "ERROR")
            return

    if not isinstance(gl.config["plotMaps"], bool):
        showMessage("plotMaps variable is not a boolean", "ERROR")
        return
 

    file=gl.config['predictorFileName']
    var=gl.config['predictorVar']
    code=gl.config['predictorCode']

    extents=gl.config['predictorExtents']
    south=extents["minLat"]
    north=extents["maxLat"]
    west=extents["minLon"]
    east=extents["maxLon"]        

    if file=="":
        showMessage("predictor file cannot be empty", "ERROR")
        return
    elif not os.path.exists(file):
        showMessage("predictor file does not exist", "ERROR")
        return

    if var=="":
        showMessage("predictor variable cannot be empty. Please repeat selection of predictor file", "ERROR")
        return

    if code=="":
        showMessage("predictor code cannot be empty. Please repeat selection of predictor file or add code to the input box manually", "ERROR")
        return

    check=[]
    for _x in [east,west,south,north]:
        check.append(is_number(_x))
    if not all(check):
            showMessage("\nLat and Lon values should be numeric.", "ERROR")
            return

    check=[float(east)>float(west), float(north)>float(south)]
    if not all(check):
            showMessage("\nLat and Lon values should be numeric.", "ERROR")
            return    
        
    return True
