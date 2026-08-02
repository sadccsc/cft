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
    config=ff.saveConfig()
    if config is None:
        ff.showMessage("Could not read config, stopping early.", "ERROR")
        return

    #running computations
    
    ff.computeModelNoGui(config)


    
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
    print("failed to read config file")
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
