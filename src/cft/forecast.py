import os, sys
import json
import traceback
import xarray as xr
import geopandas as gpd
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
 

from cft import gl
from cft.functions.functions_forecast import (
readFunctionConfig, 
computeModelNoGui, 
showMessage,
months,
tgtSeass,
timeAggregations,
predictandCats,
)

# in code
gl.configFile="forecast.json"

            
def main():
    print("setting up GUI")

    
    from PyQt5 import QtWidgets, uic, QtCore, QtGui
    from PyQt5.QtWidgets import QFileDialog




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

            uiFile = os.path.join(os.path.dirname(__file__), "forecast.ui")
            uic.loadUi(uiFile, self)

            iconPath = os.path.join(os.path.dirname(__file__), "cft.ico")
            self.setWindowIcon(QtGui.QIcon(iconPath))

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
            variables=readVariablesFile(path)
            if variables is None:
                showMessage("Problem reading variables from file {}".format(path),"NONCRITICAL")            
            else:
                combo_box.addItems(variables)

    

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


    def makeConfig():
        gl.config={}
    
        #defined parameters/variables
        gl.config['rootDir'] = ""
    
        gl.config['predictorYear'] = 2026
        gl.config['predictorMonth'] = "Jul"
    
        gl.config['fcstTargetSeas']="Dec-Feb"
        gl.config['fcstTargetYear']=2026
    
        gl.config["climEndYr"]=1991
        gl.config["climStartYr"]=2020
    
        gl.config["predictorExtents"]={'minLat':-60,'maxLat':60,'minLon':-180,'maxLon':180}
        
    
        gl.config['predictorFileName'] = ""
        gl.config['predictorVar'] = ""
        gl.config['predictorCode'] = ""
        gl.config['crossval']="KF"
        gl.config['preproc']="PCR"
        gl.config['regression']="OLS"
    
        gl.config['timeAggregation']="sum"
        gl.config["predictandFileName"]=""
        gl.config["predictandVar"]=""
        gl.config["predictandCategory"]=""
        gl.config["predictandMissingValue"]=-999
    
        gl.config["zonesFile"]=""
        gl.config["zonesAttribute"]=""
        gl.config["zonesAggregate"]=True
        gl.config["regridPredictand"]=False
    
        gl.config["overlayFile"]=""
        gl.config["plotMaps"]=True




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

        gl.config["plotMaps"]=True
    
        
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
            
       # variables fixed in gui
            gl.config["plotMaps"]=True


        return True

    \
    
    def readVariablesFile(file):        
        ext=os.path.splitext(file)[1]
        if ext==".nc":
            variables = readVariablesNcfile(file)
        elif ext in [".geojson",".shp"]:
            variables = readVariablesShpfile(file)
        else:
            variables=[Path(file).stem.split("_")[0]]
        if variables is None:
            #noncritical because check is done later too, and this will leave 
            showMessage("File with variables/attributes expected. If it is a netcdf file check if it is a dataset and has at least one variable, and if it is a shapefile - check if it has at least one attribute", "NONCRITICAL")
            variables=[]
        return variables




    
    def readVariablesShpfile(file):
        # Open the shapefile
        showMessage("reading variables from {}".format(file))
        if os.path.exists(file):
            gdf = gpd.read_file(file)
            #exclude the geometry column:
            attributes = [col for col in gdf.columns if col != "geometry"]
            if len(attributes)>0:
                return attributes
            else:
                return
        else:
            showMessage("File {} does not exist".format(file),"ERROR")
            return



            
    def readVariablesNcfile(file):
        # Open the shapefile
        showMessage("reading variables from {}".format(file))
        if os.path.exists(file):
            ds = xr.open_dataset(file, decode_times=False)
    
            # If you want to exclude the geometry column:
            variables = ds.data_vars
            variables =[x for x in variables if x not in ["T","time","lat","lon","Lat","Lon","Latitude","Longitude","X","Y"]]
            ds.close()
            if len(variables)>0:
                return variables
            else:
                showMessage("File {} does not have any data variables".format(file),"ERROR")
                return
        else:
            showMessage("File {} does not exist".format(file),"ERROR")
            return        


    def is_number(s):
        try:
            float(s)
            return True
        except ValueError:
            return False

    
    def saveConfig():
        #defined parameters/variables
        with open(gl.configFile, "w") as f:
            json.dump(gl.config, f, indent=4)
            showMessage("saved config to: {}".format(gl.configFile), "INFO")
        return gl.config

    

    if not os.path.exists(gl.configFile):
        showMessage("config file {} does not exist. Making default config.".format(gl.configFile))
        makeConfig()


    
    def computeModel():
        
        #=======================================================================================================
        #preliminaries
        
        #read config from gui
        check=readGUI()
        if check is None:
            showMessage("Errors in user input, stopping early.", "ERROR")
            return
        
        #save config to json file
        config=saveConfig()
        if config is None:
            showMessage("Could not read config, stopping early.", "ERROR")
            return
    
        #running computations
        
        computeModelNoGui(config)

    
    
    
    #shows the main window
    app = QtWidgets.QApplication(sys.argv)
    gl.window = MainWindow()

    check=readFunctionConfig()
    if check is None:
        print("Failed to read config file")
    else:
        try:
            showMessage("reading config from: {}".format(gl.configFile))
            with open(gl.configFile, "r") as f:
                gl.config = json.load(f)
            populateGui()
        except:    
            showMessage("config file corrupted. Making default config.".format(gl.configFile))
            makeConfig()
            populateGui()

    print("opening GUI...")
    
    gl.window.show()

    sys.exit(app.exec_())



if __name__ == "__main__":
    main()

