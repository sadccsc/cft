import os, sys, time
from datetime import datetime
import pandas as pd
import numpy as np
import geojson, json
import xarray as xr
import rioxarray

from sklearn.cross_decomposition import CCA
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression, Ridge, Lasso
#from sklearn.linear_model import RidgeCV, LassoCV
from sklearn.tree import DecisionTreeRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import cross_val_score, RepeatedKFold, LeaveOneOut, LeavePOut, KFold, cross_val_predict
from sklearn.metrics import r2_score, mean_squared_error, roc_auc_score, mean_absolute_percentage_error, mean_squared_error, explained_variance_score
from sklearn.base import BaseEstimator, RegressorMixin
from rasterstats import zonal_stats
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
import matplotlib.colors as colors
import cartopy.crs as ccrs
import importlib
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtWidgets import QFileDialog
import traceback
import geopandas as gpd

from pathlib import Path


import gl
import functions.functions_forecast as ff


# in code
gl.configFile="forecast.json"

#this should be read from a "deep config json"
gl.maxLeadTime=6


def computeModel():
    
    #=======================================================================================================
    #preliminaries

    #reloading functions
    importlib.reload(ff) 
    
    #read config from gui
    check=ff.readGUI()
    if check is None:
        ff.showMessage("Errors in user input, stopping early.", "ERROR")
        return
    
    #check user inputs
    check=ff.checkInputs()
    if check is None:
        ff.showMessage("Errors in user input, stopping early.", "ERROR")
        return
    
    #save config to json file
    ff.saveConfig()

    
    #=======================================================================================================
    #reading data
    
    #determine lead time
    leadTime=ff.getLeadTime()
    
    if leadTime is None:
        ff.showMessage("Lead time could not be calculated, stopping early.", "ERROR")
        return
    
    #reading predictors data
    predictor,geoDataPredictor=ff.readPredictor()
    if predictor is None:
        ff.showMessage("Predictor could not be read, stopping early.", "ERROR")
        return

    #reading predictand data - this will calculate seasonal from monthly if needed.
    result=ff.readPredictand()
    if result is None:
        ff.showMessage("Predictand could not be read, stopping early.", "ERROR")
        return
    
    # 0 denotes data as read from input files, when transformed later, these are kept for later use 
    # predictand is Pandas DataFrame, geoData is empty geoDataFrame
    predictand0, geoData0=result
    
    #aggregating to zones if required
    if gl.config["zonesAggregate"]:
        ff.showMessage("Aggregating data to zones read from {} ...".format(gl.config["zonesFile"]))
        
        zonesVector=gpd.read_file(gl.config["zonesFile"])
        
        ff.showMessage("checking validity of data from {} ...".format(gl.config["zonesFile"]))
        
        check=ff.checkPolyValidity(zonesVector)
        if not check:
            ff.showMessage("Vector file {} fails the validity check indicating that it is likely corrupted.".format(zonesVector), "ERROR")
            return
        
        if not zonesVector[gl.config["zonesAttribute"]].is_unique:
            ff.showMessage("Selected vector attribute in regions map contains identical values. These values have to be unique for each zone, please check the zones vector file or the attribute you selected. Stopping early.", "ERROR")
            return
        
        #retaining just the attribute as index
        zonesVector=zonesVector[[gl.config["zonesAttribute"], 'geometry']].set_index(gl.config["zonesAttribute"])
        
        # calling the aggregation function   
        predictand,geoData=ff.aggregatePredictand(predictand0, geoData0, zonesVector)
            
        if predictand is None:
            ff.showMessage("Predictand could not be aggregated to zones. Make sure there is overlap between predictand data and zones vector. Stopping early.", "ERROR")
            return
        
        #checking if result has data
        if predictand.dropna(axis=1).empty:
            ff.showMessage("Predictand could not be aggregated to zones. Make sure there is overlap between predictand data and zones vector. Stopping early.", "ERROR")
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
    ff.showMessage("Aligning predictor and predictand data...")
    predictandHcst,predictorHcst=ff.getHcstData(predictand,predictor)
    
    
    predictorFcst=ff.getFcstData(predictor)
    if predictandHcst is None:
        ff.showMessage("Hindcast data for predictand could not be derived, stopping early.", "ERROR")
        return
    
    
    #calculaing observed terciles
    #is there a need to do a strict control of overlap???
    result=ff.getObsTerciles(predictand, predictandHcst)
    if result is None:
        ff.showMessage("Terciles could not be calculated, stopping early.", "ERROR")
                
    obsTercile,tercThresh=result
    
    
    #check for locations with too many identical values - forecast and skill measures cannot be derived for such locations
    max_counts = predictandHcst.apply(lambda col: col.value_counts().max())
    bad=max_counts>0.2*predictandHcst.shape[0]
    good=np.invert(bad)

    #listing bad locations
    if len(bad)>0:
        badnames=predictandHcst.loc[:,bad].columns
        for name in badnames:
            ff.showMessage("cannot calculate forecast for {} - too many similar values in predictand".format(name), "NONCRITICAL")
            

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
            regressor = ff.StdRegressor(regressor_name=gl.config['regression'], **args, **kwargs)
        else:
            #2-D predictor, no need to PCR or CCA
            ff.showMessage("2-D predictor, but no preprocessing requested. Please change pre-processor to either PCR or CCA", "ERROR")
            return
    else:
        if predictorHcst.shape[1]==1:
            ff.showMessage("1-D predictor, and neither PCR nor CCA are applicable. Please change pre-processor to 'No preprocessing'", "ERROR")
            #2-D predictor, no need to PCR or CCA
            return    
    
    #setting up regressor
    if gl.config['preproc']=="PCR":
        #regession model
        regressor = ff.PCRegressor(regressor_name=gl.config['regression'], **args, **kwargs)
        
    if gl.config['preproc']=="CCA":
        
        regressor = ff.CCARegressor(regressor_name=gl.config['regression'],**args, **kwargs)
        #return
  
    #=======================================================================================================
    #setting up output directory structure
    
    ff.showMessage("Setting up directories to write to...")        
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
            ff.showMessage("{} directory {} does not exist. creating...".format(adir, dirs[adir]))
            os.makedirs(dirs[adir])
        else:
            ff.showMessage("{} will be written to {}".format(adir, dirs[adir]), "INFO")
            


    #=======================================================================================================
    # calculating forecast

    # cross-validated hindcast
    ff.showMessage("Calculating cross-validated hindcast...")
    cvHcst = ff.cross_val_predict(regressor,predictorHcst,  predictandHcst, cv=cv)
    
    # output of the above is a plain numpy array, needs to be converted to pandas
    cvHcst=pd.DataFrame(cvHcst, index=predictandHcst.index, columns=predictandHcst.columns)

    # actual prediction - forecast
    ff.showMessage("Calculating deteriministic forecast...")
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
    detFcst=ff.getFcstAnomalies(detFcst,refData)
    
    # calculate anomalies on hindcast data
    # for "full model" hindcast
    estHcst=ff.getFcstAnomalies(estHcst,refData)
    
    # for cross-validated hindcast
    cvHcst=ff.getFcstAnomalies(cvHcst,refData)
    
    #deriving probabilistic prediction
    ff.showMessage("Calculating probabilistic hindcast and forecast using error variance...")
    
    #this one uses cross-validated hindcast for error
    result=ff.probabilisticForecast(cvHcst["value"], predictandHcst,detFcst["value"],tercThresh)
    if result is None:
        ff.showMessage("Probabilistic forecast could not be calculated", "ERROR")
        return
    probFcst,probHcst=result
    
    #tercile forecast
    ff.showMessage("Calculating tercile forecast (highest probability category)")
    
    # forecast
    tercFcst=ff.getTercCategory(probFcst)
    
    # and hindcast
    tercHcst=ff.getTercCategory(probHcst)
    
    #CEM categories
    ff.showMessage("Calculating CEM categories")
    
    #forecast
    cemFcst=ff.getCemCategory(probFcst)
    
    #hindcast
    cemHcst=ff.getCemCategory(probHcst)
    
    
    #calculating skill
    ff.showMessage("Calculating skill scores...")
    scores=ff.getSkill(probHcst,cvHcst["value"],predictandHcst,obsTercile)    
    if scores is None:
        ff.showMessage("Skill could not be calculated", "ERROR")
        return
    
    
    #saving data
    ff.showMessage("Plotting forecast maps and saving output files...")    
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
        
    ff.showMessage("Writing output files...")
    outputFile=Path(outputDir, "{}_deterministic-fcst_{}.{}".format(gl.config['predictandVar'], forecastID,fileExtension))
    ff.writeOutput(np.round(detfcst_write,2), outputFile)

    outputFile=Path(outputDir, "{}_probabilistic-fcst_{}.{}".format(gl.config['predictandVar'], forecastID,fileExtension))
    ff.writeOutput(np.round(probfcst_write,2),outputFile)

    outputFile=Path(outputDir, "{}_skill_{}.{}".format(gl.config['predictandVar'], forecastID,fileExtension))
    ff.writeOutput(scores_write, outputFile)

    outputFile=Path(outputDir, "{}_deterministic-hcst_{}.{}".format(gl.config['predictandVar'], forecastID,fileExtension))
    ff.writeOutput(np.round(dethcst_write,2),outputFile)

    outputFile=Path(outputDir, "{}_probabilistic-hcst_{}.{}".format(gl.config['predictandVar'], forecastID,fileExtension))
    ff.writeOutput(np.round(probhcst_write,2),outputFile)

    
    ff.showMessage("Plotting forecast maps...")

    annotation="Forecast for: {} {}".format(gl.config['fcstTargetSeas'], gl.config['fcstTargetYear'])
    annotation+="\nPredictors from: {} {}".format(gl.config['predictorMonth'], gl.config['predictorYear'])
    annotation+="\nPredictor: {}".format(Path(gl.config["predictorFileName"]).stem)
    annotation+="\nPredictand: {}".format(Path(gl.config["predictandFileName"]).stem)
    annotation+="\nClimatological period: {}-{}".format(gl.config['climStartYr'], gl.config['climEndYr'])
    

    #maskedscores=ff.getSkillMask(scores_plot, scores_plot)


    ff.plotMaps(detfcst_plot, geoData, mapsDir, forecastID, zonesVector, annotation,overlayVector)
    ff.plotMaps(probfcst_plot, geoData, mapsDir, forecastID, zonesVector, annotation, overlayVector)
    ff.plotMaps(cemfcst_plot, geoData, mapsDir, forecastID, zonesVector, annotation, overlayVector)
    ff.plotMaps(tercfcst_plot, geoData, mapsDir, forecastID, zonesVector, annotation, overlayVector)

    
    ff.showMessage("Plotting skill maps...")    
    #plotting skill scores
    ff.plotMaps(scores_plot, geoData, mapsDir, forecastID, zonesVector, annotation, overlayVector)

    
    ff.showMessage("Plotting time series plots...") 
    ff.plotTimeSeries(cvHcst["value"],predictandHcst, detFcst, tercThresh, timeseriesDir, forecastID, annotation)
    
    
    ff.showMessage("Plotting preprocessing diagnostics...")
    if gl.config['preproc']=="PCR":
        ff.plotDiagsPCR(regressor, predictorHcst, predictandHcst, geoData, diagsDir, forecastID, annotation)

    if gl.config['preproc']=="CCA":
        ff.plotDiagsCCA(regressor, predictorHcst, predictandHcst, geoData, diagsDir, forecastID, annotation)
    
    ff.showMessage("Plotting regression diagnostics...")
    ff.plotDiagsRegression(predictandHcst, cvHcst, estHcst, tercThresh, detFcst, diagsDir, forecastID, annotation)
    
    ff.showMessage("All done!", "SUCCESS")
    ff.showMessage("Inspect log above for potential errors!", "SUCCESS")    
    ff.showMessage("All output written to {}".format(forecastDir), "SUCCESS")    
    
    
    return


    
def browse(line_edit, mode='file', parent=None, caption="Select File", file_filter="All Files (*)", combo_box=None):
    if mode == 'file':
        path, _ = QFileDialog.getOpenFileName(parent, caption, "", file_filter)
    elif mode == 'dir':
        path = QFileDialog.getExistingDirectory(parent, caption)
    else:
        raise ValueError("Unsupported browse mode")

    if path:
        line_edit.setText(path)
        
    if combo_box is not None:
        # Read variables and populate the comboBox
        combo_box.clear()
        variables=ff.readVariablesFile(path)
        if variables is None:
            ff.showMessage("Problem reading variables from file".format(_file),"NONCRITICAL")            
        else:
            combo_box.addItems(variables)

        
class Worker(QtCore.QThread):
    log = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal(str)

    def __init__(self, task_name, task_function, *args, **kwargs):
        super().__init__()
        self.task_name=task_name
        self.task_function = task_function
        self.args = args
        self.kwargs = kwargs

    def run(self):
        """Run the provided function in a thread and emit logs."""
        try:
            self.log.emit(f"<i>Task '{self.task_name}' started...</i>")
            # Run the task
            self.task_function(*self.args, **self.kwargs)
            self.log.emit(f"<i>Task '{self.task_name}' finished successfully.</i>")
        except Exception as e:
            tb = traceback.format_exc()
            self.log.emit(f"Error occurred in {self.task_name}:\n{tb}")            
        finally:
            self.finished.emit(self.task_name)
            

class MainWindow(QtWidgets.QMainWindow):
    log_signal = QtCore.pyqtSignal(str)
    
  
    def __init__(self):
        super().__init__()
        uic.loadUi("forecast.ui", self)
        
        #initialize garbage collector
        self.workers = []
        
        self.log_signal.connect(self.append_log)
        
        # Connect signals
        self.button_run.clicked.connect(lambda: self.start_task(f"Model", computeModel))

        self.browseButton_predictorfile.clicked.connect(
            lambda: browse(self.lineEdit_predictorfile, mode='file', parent=self, 
                           file_filter="CSV or NetCDF (*.csv *.nc)", combo_box=self.comboBox_predictorvar)
        )
        
        self.clearLogButton.clicked.connect(self.logWindow.clear)
        
        #directory browser
        self.pushButton_rootdir.clicked.connect(
            lambda: browse(self.lineEdit_rootdir, mode='dir', parent=self)
        )

        self.pushButton_predictandfile.clicked.connect(
            lambda: browse(self.lineEdit_predictandfile, mode='file', parent=self, 
                           file_filter="CSV or NetCDF (*.csv *.nc)", combo_box=self.comboBox_predictandvar)
        )

        self.pushButton_zonesfile.clicked.connect(
            lambda: browse(self.lineEdit_zonesfile, mode='file', parent=self, 
                           file_filter="Vector Files (*.shp *.geojson)", combo_box=self.comboBox_zonesattribute)
        )
        self.pushButton_overlayfile.clicked.connect(
            lambda: browse(self.lineEdit_overlayfile, mode='file', parent=self, 
                           file_filter="Vector Files (*.shp *.geojson)")
        )

    # ---------- Thread Handling ----------
    def start_task(self, name, func, *args):
        worker = Worker(name, func, *args)
        worker.log.connect(self.log_signal.emit)
        # finished cleans up workers stack
        worker.finished.connect(self.cleanup_worker)
        self.workers.append(worker)  # keep reference
        worker.start()
        
    def append_log(self, message: str):
        self.logWindow.appendHtml(f"{message}")
        self.logWindow.ensureCursorVisible()
            
    def cleanup_worker(self, task_name):
        self.workers = [w for w in self.workers if w.isRunning()]
        self.logWindow.appendHtml(f"<i>Task '{task_name}' cleaned up.</i>")

        
    def set_buttons_enabled(self, enabled: bool):
        for btn in self.buttons:
            btn.setEnabled(enabled)

            
    
if __name__ == "__main__":
    
    #shows the main window
    app = QtWidgets.QApplication(sys.argv)
    gl.window = MainWindow()
    gl.window.show()

    
    

    
    

tgtSeass=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan-Mar","Feb-Apr","Mar-May","Apr-Jun","May-Jul","Jun-Aug","Jul-Sep","Aug-Oct","Sep-Nov","Oct-Dec","Nov-Jan","Dec-Feb"]

srcMons=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

timeAggregations={"sum","mean"}

crossvalidators = {
        "KF": KFold,
        'LOO': LeaveOneOut,
}

preprocessors={
    "PCR":["Principal Component Regression (PCR)", {}],
    "CCA":["Canonical Corelation Analysis (CCA)", {}],
    "NONE":["No preprocessing", {}],
}


if not os.path.exists(gl.configFile):
    ff.showMessage("config file {} does not exist. Making default config.".format(gl.configFile))
    ff.makeConfig()
    
check=ff.readFunctionConfig()
if check is None:
    print("failed")
else:
    try:
        ff.showMessage("reading config from: {}".format(gl.configFile))
        with open(gl.configFile, "r") as f:
            gl.config = json.load(f)
        ff.populateGui()
    except:    
        ff.showMessage("config file corrupted. Making default config.".format(gl.configFile))
        ff.makeConfig()
        ff.populateGui()
    
sys.exit(app.exec_())
