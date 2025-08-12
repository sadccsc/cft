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

from pathlib import Path

import gl
from functions.functions import *

# in code
gl.configFile="forecast.json"

#this should be read from a "deep config json"
gl.maxLeadTime=6

#this should be added to gui
gl.predictandCategory="rainfall"
gl.predictandMissingValue=-999



    
def computeModel(model):
    
    #read config from gui
    readGUI()
    
    #save config to json file
    saveConfig()
        
    showMessage(model, "INFO")
    leadTime=getLeadTime()
    
    if leadTime is None:
        showMessage("Lead time could not be calculated, stopping early.", "ERROR")
        return
    
    #reading predictors data
    predictor=readPredictor(model)
    if predictor is None:
        showMessage("Predictor could not be read, stopping early.", "ERROR")
        return

    #reading predictand data - this will calculate seasonal from monthly if needed.
    result=readPredictand()
    if result is None:
        showMessage("Predictand could not be read, stopping early.", "ERROR")
        return
    
    predictand0, geoData0=result
    
    if gl.config["zonesAggregate"]:
        zonesVector=gpd.read_file(gl.config["zonesFile"])
        showMessage("Aggregating data to zones read from {} ...".format(gl.config["zonesFile"]))
        predictand,geoData=aggregatePredictand(predictand0, geoData0, zonesVector)
    else:
        zonesVector=None
        predictand=predictand0.copy()
        geoData=geoData0.copy()
    
    overlayVector=None
    if gl.config["overlayFile"] != "":
        if os.path.exists(gl.config["overlayFile"]):
            overlayVector=gpd.read_file(gl.config["overlayFile"])

    #defining target date for forecast. If seasonal - then this is the first month of the season.
    fcstTgtDate=pd.to_datetime("01 {} {}".format(gl.config['fcstTargetSeas'][0:3], gl.config['fcstTargetYear']))
    
    #do not need this anymore
    #gl.config["fcstTgtCode"]=seasons[fcstTgtDate.month-1]
    
    #finding overlap of predictand and predictor
    showMessage("Aligning predictor and predictand data...")
    predictandHcst,predictorHcst=getHcstData(predictand,predictor)
    predictorFcst=getFcstData(predictor)
    if predictandHcst is None:
        showMessage("Hindcast data for predictand could not be derived, stopping early.", "ERROR")
        return

    showMessage("Setting up directories to write to...")        
    forecastID="{}_{}".format(gl.predictorDate.strftime("%Y%m"), gl.config['fcstTargetSeas'])
    forecastDir=Path(gl.config['rootDir'], forecastID, gl.config["predictorFiles"][model][1],gl.targetType, "{}_{}_{}".format(gl.config["preproc"][model],gl.config["regression"][model],gl.config["crossval"][model]))

    mapsDir=Path(forecastDir, "maps")
    timeseriesDir=Path(forecastDir, "timeseries")
    outputDir=Path(forecastDir, "output")
    diagsDir=Path(forecastDir, "diagnostics")

    for adir in [mapsDir,outputDir, diagsDir,timeseriesDir]:
        if not os.path.exists(adir):
            showMessage("\toutput directory {} does not exist. creating...".format(adir))
            os.makedirs(adir)
                
    #calculaing observed terciles
    #is there a need to do a strict control of overlap???
    result=getObsTerciles(predictand, predictandHcst)
    if result is None:
        showMessage("Terciles could not be calculated, stopping early.", "ERROR")
                
    obsTercile,tercThresh=result
    
    #locations with too many identical values
    bad=(tercThresh.loc[0.66]==tercThresh.loc[0.5]) | (tercThresh.loc[0.33]==tercThresh.loc[0.5])
    good=np.invert(bad)

    #removing bad locations
    predictandHcst=predictandHcst.loc[:,good]
    tercThresh=tercThresh.loc[:,good]
    obsTercile=obsTercile.loc[:,good]

    #setting up cross-validation
    cvkwargs=crossvalidator_config[gl.config['crossval'][model]][1]
    cv=crossvalidators[gl.config['crossval'][model]](**cvkwargs)
    
    
    #arguments for regressor
    kwargs=regressor_config[gl.config['regression'][model]][1]
    
    if gl.config['preproc'][model]=="NONE":
        if predictorHcst.shape[1]==1:
            regressor = StdRegressor(regressor_name=gl.config['regression'][model], **kwargs)
        else:
            #2-D predictor, no need to PCR or CCA
            showMessage("2-D predictor, but no preprocessing requested. Please change pre-processor to either PCR or CCA", "ERROR")
            return
    else:
        if predictorHcst.shape[1]==1:
            showMessage("1-D predictor, and neither PCR nor CCA are applicable. Please change pre-processor to None", "ERROR")
            #2-D predictor, no need to PCR or CCA
            return
        
    if gl.config['preproc'][model]=="PCR":
        #regession model
        regressor = PCRegressor(regressor_name=gl.config['regression'][model], **kwargs)
        
    if gl.config['preproc'][model]=="CCA":
        showMessage("sorry, CCA is not implemented yet", "NONCRITICAL")
        return
#        regressor = CCAregressor(regressor_name=gl.config['regression'][model], **kwargs)
  
    #cross-validated hindcast
    showMessage("Calculating cross-validated hindcast...")
    cvHcst = cross_val_predict(regressor,predictorHcst,  predictandHcst, cv=cv)
    cvHcst=pd.DataFrame(cvHcst, index=predictandHcst.index, columns=predictandHcst.columns)

    
    #actual prediction
    showMessage("Calculating deteriministic forecast...")
    regressor.fit(predictorHcst,  predictandHcst)
    detFcst=regressor.predict(predictorFcst)
    detFcst=pd.DataFrame(detFcst, index=[fcstTgtDate], columns=predictandHcst.columns)
    
    #calculate forecast anomalies
    refData=predictand[str(gl.config["climStartYr"]):str(gl.config["climEndYr"])]   
    detFcst=getFcstAnomalies(detFcst,refData)
    
    #deriving probabilistic prediction
    showMessage("Calculating probabilistic hindcast and forecast using error variance...")
    result=probabilisticForecast(cvHcst, predictandHcst,detFcst["value"],tercThresh)
    if result is None:
        showMessage("Probabilistic forecast could not be calculated", "ERROR")
        return
    probFcst,probHcst=result
    
    showMessage("Calculating tercile forecast (highest probability category)")
    
    tercFcst=getTercCategory(probFcst)
    tercHcst=getTercCategory(probHcst)
    
    showMessage("Calculating CEM categories")
    cemFcst=getCemCategory(probFcst)
    cemHcst=getCemCategory(probHcst)
    
    #calculating skill
    showMessage("Calculating skill scores...")
    scores=getSkill(probHcst,cvHcst,predictandHcst,obsTercile)    
    if scores is None:
        showMessage("Skill could not be calculated", "ERROR")
        return
    
    
    #saving data
    showMessage("Plotting forecast maps and saving output files...")    
    # these are ways to convert dataframes to dataarrays
    #converts dataframe with two levels of column multiindex to xarray with variables taken from zero level of multiindex
    #cvHcst.unstack().to_xarray().transpose("time","lat","lon").to_dataset(name=gl.config['predictandVar'])

    #this does the same
    #cvHcst.stack(level=[0,1], future_stack=True).to_xarray().to_dataset(name=gl.config['predictandVar'])

    #this is for three-level multi-index
    #probHcst.stack(level=[1,2]).to_xarray()


    if gl.targetType=="grid":
        #this is for plotting
        detfcst=detFcst.stack(level=["lat","lon"],future_stack=True).droplevel(0).T
        probfcst=probFcst.stack(level=["lat","lon"],future_stack=True).droplevel(0).T
        tercfcst=tercFcst.stack(level=["lat","lon"],future_stack=True).droplevel(0).T
        cemfcst=cemFcst.stack(level=["lat","lon"],future_stack=True).droplevel(0).T
        #this is for writing
        probfcst_write=probFcst.unstack().to_xarray()
        probhcst_write=probHcst.unstack().to_xarray()
        tercfcst_write=tercFcst.unstack().to_xarray()
        cemhcst_write=cemHcst.unstack().to_xarray()
        detfcst_write=detFcst.unstack().to_xarray()
        dethcst_write=cvHcst.stack(level=[0,1], future_stack=True).to_xarray().to_dataset(name=gl.config['predictandVar'])
        scores_write=scores.T.to_xarray()
        fileExtension="nc"
    else:
        #this is for plotting
        detfcst=detFcst.stack(future_stack=True).droplevel(0).T
        probfcst=probFcst.stack(future_stack=True).droplevel(0).T
        tercfcst=tercFcst.stack(future_stack=True).droplevel(0).T
        cemfcst=cemFcst.stack(future_stack=True).droplevel(0).T
        #this is for writing
        detfcst_write=detfcst.copy()
        probfcst_write=probfcst.copy()
        tercfcst_write=tercfcst.copy()
        cemfcst_write=cemfcst.copy()
        dethcst_write=cvHcst.copy()
        probhcst_write=probHcst.copy()
        scores_write=scores.copy()
        fileExtension="csv"

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

    plotMaps(detfcst, geoData, geoData0, mapsDir, forecastID, zonesVector, overlayVector)
    plotMaps(probfcst, geoData, geoData0, mapsDir, forecastID, zonesVector, overlayVector)
    plotMaps(cemfcst, geoData, geoData0, mapsDir, forecastID, zonesVector, overlayVector)
    plotMaps(tercfcst, geoData, geoData0, mapsDir, forecastID, zonesVector, overlayVector)

    showMessage("Plotting skill maps...")    
    #plotting skill scores
    plotMaps(scores, geoData, geoData0, mapsDir, forecastID, zonesVector, overlayVector)

    showMessage("Plotting time series...") 
    plotTimeSeries(cvHcst,predictandHcst, detFcst, tercThresh, timeseriesDir, forecastID)

    showMessage("All done!", "SUCCESS")    
    
    
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
        
    if combo_box:
        # Read variables and populate the comboBox
        combo_box.clear()
        variables=readVariablesFile(path)
        if variables is None:
            showMessage("Problem reading variables from file".format(_file),"NONCRITICAL")            
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
            self.log.emit(f"Task '{self.task_name}' started...")
            # Run the task
            self.task_function(*self.args, **self.kwargs)
            self.log.emit(f"Task '{self.task_name}' finished successfully.")
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

        # Collect buttons
        self.runbuttons = [self.button_run0]
        self.predictors = [[self.browseButton_predictorfile0, self.lineEdit_predictorfile0, self.comboBox_predictorvar0]]
        

        # Connect signals
        for i,button in enumerate(self.runbuttons):
            button.clicked.connect(lambda _, idx=i: self.start_task(f"Model {idx}", computeModel, idx))

            
        for i,item in enumerate(self.predictors):
            button,line_edit,combo_box=item
            button.clicked.connect(
                lambda: browse(line_edit, mode='file', parent=self, 
                               file_filter="CSV or NetCDF (*.csv *.nc)", combo_box=combo_box)
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
        self.logWindow.appendHtml(f"<pre>{message}</pre>")
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

#can be read from json - potentially editable by user
regressors = {
    "OLS":["Linear regression", {}],
    "Lasso":["Lasso regression", {'alpha': 0.01}],
    "Ridge":["Ridge regression", {'alpha': 1.0}],
    "RF":["Random Forest", {'n_estimators': 100, 'max_depth': 5}],
    "MLP":["Multi Layer Perceptron", {'hidden_layer_sizes': (50, 25), 'max_iter': 1000, 'random_state': 0}],
    "Trees":["Decision Trees", {'max_depth': 2}]
}

preprocessors={
    "PCR":["Principal Component Regression (PCR)", {}],
    "CCA":["Canonical Corelation Analysis (CCA)", {}],
    "NONE":["No preprocessing", {}],
}

if os.path.exists(gl.configFile):
    try:
        showMessage("reading config from: {}".format(gl.configFile))
        with open(gl.configFile, "r") as f:
            gl.config = json.load(f)
        populateGui()
    except:    
        showMessage("config file corrupted. Making default config.".format(gl.configFile))
        makeConfig()
        populateGui()
else:
    showMessage("config file {} does not exist. Making default config.".format(gl.configFile))
    makeConfig()
    populateGui()
    
sys.exit(app.exec_())
