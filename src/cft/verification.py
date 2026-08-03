#!/usr/bin/env python
# coding: utf-8

# In[ ]:


#!/usr/bin/env python
# coding: utf-8

# In[ ]:


##!/usr/bin/env python
## coding: utf-8


#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
  This script generates verification maps:
      Inputs:
          Forecast vector file (geojson format)
          Predictand data covering the training period
      Outputs:
          Verification netCDF file

@author: thembani - original version
@author: pwolski - revised to the level that hardly anything of the original is left currently
         Nov 2022 - using xarray and allow more general format of netcdf files, also some changes to UI
         Aug 2023 - implemented threading and CSV format of csv files
"""
version="4.2.4"


import os, sys
from netCDF4 import Dataset
import pandas as pd
import geojson, json

import matplotlib
matplotlib.use('agg')
from pathlib import Path

from PyQt5 import QtCore, QtWidgets, uic
from PyQt5.QtCore import QThread, QObject

from PyQt5.QtCore import pyqtSignal

import warnings
warnings.filterwarnings("ignore")

import webbrowser

from cft import gl
from cft.functions.functions_verification import (
    showMessage,
    seasonParam,
    execVerification,
)

#defining fixed things

baseDir = os.path.dirname(__file__)

qtCreatorFile = Path(baseDir, "verification.ui")
settingsfile = 'verification.json'
helpfile='verification_help.html'




# functions to calculate skill indices
################################################################################################################

def openHelp():
    webbrowser.open(helpfile)

def clearLog():
    gl.window.logWindow.clear()
        
def closeApp():
    sys.exit(gl.app.exec_())

def addFcstFile():
    showMessage("Selecting forecast vector file...")
    fileName = QtWidgets.QFileDialog.getOpenFileName(gl.window,
              'Select File', '..' + os.sep, filter="GeoJson File (*.geojson)")
    if fileName[0]!="":
        #widget will return empty string if selection cancelled        
        showMessage("Checking {}...".format(fileName[0]))
        try:
            with open(fileName[0]) as f:
                jsonfile = geojson.load(f)
            #at this stage, just keys of properties are needed. these can be read from the first feature only
            feature = jsonfile['features'][0]
            variables=list(feature.properties.keys())
        except:
            showMessage("Could not read {}, check if it is a valid geojson file".format(fileName[0]), "ERROR")
            return
        
        if len(variables)==0:
            showMessage("Forecast geojson file should have at least one property associated with geometric features. Current file has 0. Please check if you loaded correct file", "ERROR")
            return
        
        showMessage("Forecast will be read from: {}".format(fileName[0]), "INFO")
        
        gl.window.fcstFilePath.setText(fileName[0])
        gl.config['fcstFile'] = {"file": '', "ID": 0, "variable": []}
        gl.config['fcstFile']['file'] = fileName[0]
        
        gl.window.fcstFileVariable.clear()
        for variable in variables:
            gl.window.fcstFileVariable.addItem(variable)
            gl.config['fcstFile']['variable'].append(variable)
            
    else:
        showMessage("Selecting forecast file aborted")

def addsummaryzonesFile():
    showMessage("Selecting zones vector file...")
    fileName = QtWidgets.QFileDialog.getOpenFileName(gl.window,
              'Select File', '..' + os.sep, filter="GeoJson File (*.geojson)")
    if fileName[0]!="":
        #widget will return empty string if selection cancelled        
        showMessage("Checking {}...".format(fileName[0]))
        try:
            with open(fileName[0]) as f:
                jsonfile = geojson.load(f)
            #at this stage, just keys of properties are needed. these can be read from the first feature only
            feature = jsonfile['features'][0]
            variables=list(feature.properties.keys())
        except:
            showMessage("Could not read {}, check if it is a valid geojson file".format(fileName[0]), "ERROR")
            return
        
        if len(variables)==0:
            showMessage("Zones geojson file should have at least one property associated with geometric features. Current file has 0. Please check if you loaded correct file", "ERROR")
            return
        
        showMessage("Zones will be read from {}".format(fileName[0]), "INFO")
        
        gl.config['summaryzonesFile'] = {"file": '', "ID": 0, "variable": []}
        gl.config['summaryzonesFile']['file'] = fileName[0]
        gl.window.summaryzonesFilePath.setText(fileName[0])
        
        gl.window.summaryzonesFileVariable.clear()
        for variable in variables:
            gl.config['summaryzonesFile']['variable'].append(variable)
            gl.window.summaryzonesFileVariable.addItem(variable)
            
    else:
        showMessage("Selecting zones file aborted")
    
    

def addObsFile():
    showMessage("Selecting file with observations...")    
    
    if gl.window.obsFileFormatCsv.isChecked() == True:
        filter="CSV File (*.csv)"
        filetype="csv"
    
    elif gl.window.obsFileFormatNetcdf.isChecked() == True:
        filter="NetCDF File (*.nc*)"
        filetype="netcdf"
        
    fileName = QtWidgets.QFileDialog.getOpenFileName(gl.window,
              'Add File', '..' + os.sep, filter=filter)
    
    if fileName[0]!="":
        #widget will return empty string if selection cancelled        
        showMessage("Checking {}...".format(fileName[0]))
        if filetype=="netcdf":
            try:
                observed = Dataset(fileName[0])
                variables=list(observed.variables.keys())
                variables=[x for x in variables if x not in ['Y', 'X', 'Z', 'T', 'zlev', 'time', 'lon', 'lat','latitude','longitude']]
                observed.close()            
            except:
                showMessage("Could not read {} file, check if it is a valid file".format(fileName[0]), "ERROR")
                return

            if len(variables)==0:
                showMessage("Observations netcdf file should have at least one variable. Current file has 0. Please check if you loaded correct file", "ERROR")
                return
        else:
            try:
                data=pd.read_csv(fileName[0])
                #will need to work on this...
                variables=["pr"]
                pass
            except:
                showMessage("Could not read observed file, check if {} is a valid file".format(fileName[0]), "ERROR")
                return
                                    
        showMessage("Observed data will be read from {}".format(fileName[0]), "INFO")
        
        gl.config['obsFile'] = {"file": '', "ID": 0, "variable": []}
        gl.config['obsFile']['file'] = fileName[0]
        gl.window.obsFilePath.setText(fileName[0])
        
        gl.window.obsFileVariable.clear()
        for variable in variables:
            gl.config['obsFile']['variable'].append(variable)
            gl.window.obsFileVariable.addItem(variable)
            
    else:
        showMessage("Selecting observations file aborted")

    
def getOutDir():
    showMessage("Setting output directory...")
    outDir=QtWidgets.QFileDialog.getExistingDirectory(directory='..' + os.sep)
    if outDir!='':
        gl.config['outDir']=outDir 
        gl.window.outDirPath.setText(outDir)
        showMessage("Output will be written to {}".format(outDir), "INFO")
    else:
        showMessage("Selecting output directory aborted")


def changeFormatType():
    
    #resetting obsFile entry
    gl.window.obsFilePath.clear()
    gl.window.obsFileVariable.clear()
    gl.config['obsFile'] = {"file": '', "ID": 0, "variable": []}
    gl.window.obsDsetCode.clear()    
    gl.config['obsDsetCode'] = ""   


    
def setConfigDefaults():
    gl.config = {}
    gl.config['Version'] = version
    #output directory
    gl.config['outDir'] = ''   

    #forecast file
    gl.config['fcstFile'] = {"file": '', "variable": [], "ID": None}
    #zones file
    gl.config['summaryzonesFile'] = {"file": '',"variable": [], "ID": None}
    #observed file
    gl.config['obsFile'] = {"file": '',"variable": [], "ID": None}
    
    gl.config['obsFileFormat'] = "netcdf"
    gl.config['obsDsetCode'] = ""

    #climatology
    gl.config['climStartYear'] = 1981
    gl.config['climEndYear'] = 2010

    #verification parameters
    gl.config['verifAggregation'] = "sum"
    gl.config['verifYear'] = ""
    gl.config['verifPeriod'] = {"season": list(seasonParam.keys()),
                        "indx": 20}
    #outputs
    gl.config["outputQuantanom"] = True
    gl.config["outputHeidke"] = False
    gl.config["outptIgnorance"] = False
    gl.config["outputIntrate"] = True
    gl.config["outputCemhit"] = False
    gl.config["outputObscemcat"] = True
    gl.config["outputFcstcemcat"] = False
    gl.config["outputFcsttercile"] = False
    gl.config["outputObstercile"] = False
    gl.config["outputObsrelanom"] = False
    gl.config["outputObsvalue"] = False
    gl.config["outputObsclim"] = False    
    gl.config["outputRpss"] = False
    return gl.config    



        
def populateUI():
    showMessage("Populating UI...")

    #this populates UI based on values in gl.config dictionary

    #output directory
    gl.window.outDirPath.setText(gl.config.get('outDir'))
    #forecast file
    gl.window.fcstFilePath.setText(os.path.basename(gl.config.get('fcstFile').get('file')))
    for var in gl.config.get('fcstFile').get('variable'):
        gl.window.fcstFileVariable.addItem(var)
    if type(gl.config.get('fcstFile').get('ID')) == type(0): 
        gl.window.fcstFileVariable.setCurrentIndex(gl.config.get('fcstFile').get('ID'))

    #zones file
    gl.window.summaryzonesFilePath.setText(os.path.basename(gl.config.get('summaryzonesFile').get('file')))
    for var in gl.config.get('summaryzonesFile').get('variable'):
        gl.window.summaryzonesFileVariable.addItem(var)
    if type(gl.config.get('summaryzonesFile').get('ID')) == type(0): 
        gl.window.summaryzonesFileVariable.setCurrentIndex(gl.config.get('summaryzonesFile').get('ID'))

    #observations
    gl.window.obsFilePath.setText(os.path.basename(gl.config.get('obsFile').get('file')))
    for var in gl.config.get('obsFile').get('variable'):
        gl.window.obsFileVariable.addItem(var)
    if type(gl.config.get('obsFile').get('ID')) == type(0): 
        gl.window.obsFileVariable.setCurrentIndex(gl.config.get('obsFile').get('ID'))
    gl.window.obsDsetCode.setText(gl.config.get('obsDsetCode'))


    if gl.config.get('obsFileFormat') == "netcdf":
        gl.window.obsFileFormatNetcdf.setChecked(True)
    else:
        gl.window.obsFileFormatCsv.setChecked(True)


    #climatology
    gl.window.climStartYear.setText(str(gl.config.get('climStartYear')))
    gl.window.climEndYear.setText(str(gl.config.get('climEndYear')))

    #verification
    periodxs = gl.config.get('verifPeriod').get('season')
    for periodx in periodxs:
        gl.window.verifPeriod.addItem(periodx)  
    if type(gl.config.get('verifPeriod').get('indx')) == type(0): 
        gl.window.verifPeriod.setCurrentIndex(gl.config.get('verifPeriod').get('indx'))
    gl.window.verifYear.setText(str(gl.config.get('verifYear')))

    if gl.config.get('verifAggregation') == "sum":
        gl.window.verifAggregationSum.setChecked(True)
    else:
        gl.window.verifAggregationAvg.setChecked(True)

    #outputs
    gl.window.outputQuantanom.setChecked(bool(gl.config.get('outputQuantanom')))
    gl.window.outputHeidke.setChecked(bool(gl.config.get('outputHeidke')))
    gl.window.outputIgnorance.setChecked(bool(gl.config.get('outputIgnorance')))
    gl.window.outputIntrate.setChecked(bool(gl.config.get('outputIntrate')))
    gl.window.outputCemhit.setChecked(bool(gl.config.get('outputCemhit')))
    gl.window.outputFcstcemcat.setChecked(bool(gl.config.get('outputFcstcemcat')))
    gl.window.outputFcsttercile.setChecked(bool(gl.config.get('outputFcsttercile')))
    gl.window.outputObscemcat.setChecked(bool(gl.config.get('outputObscemcat')))
    gl.window.outputObstercile.setChecked(bool(gl.config.get('outputObstercile')))
    gl.window.outputObsrelanom.setChecked(bool(gl.config.get('outputObsrelanom')))
    gl.window.outputObsvalue.setChecked(bool(gl.config.get('outputObsvalue')))
    gl.window.outputObsclim.setChecked(bool(gl.config.get('outputObsclim')))
    gl.window.outputRpss.setChecked(bool(gl.config.get('outputRpss')))

    ## attaching signals
    #it is obvious what these do
    gl.window.outDirButton.clicked.connect(getOutDir)
    gl.window.fcstFileButton.clicked.connect(addFcstFile)
    gl.window.obsFileButton.clicked.connect(addObsFile)
    gl.window.summaryzonesFileButton.clicked.connect(addsummaryzonesFile)
    #changing format wipes out the obs file selection, thus functions for this
    gl.window.obsFileFormatCsv.toggled.connect(changeFormatType)
    gl.window.obsFileFormatNetcdf.toggled.connect(changeFormatType)
    #again, obvious actions
    gl.window.runButton.clicked.connect(gl.window.threadVerification)
    gl.window.exitButton.clicked.connect(closeApp)
    gl.window.helpButton.clicked.connect(openHelp)
    gl.window.clearLogButton.clicked.connect(clearLog)
    showMessage("UI ready", "INFO")



    




    
#threading
# Step 1: Create a worker class
class Worker(QObject):
    finished = pyqtSignal()
    
    ################################################################################################################
    #workhorse function
    

    def execVerificationWrapper(self):
        # this picks up values from UI and performs some rudimentary checks and saves them into gl.config
        # gl.config is then dumped to json file
        # updateConfig returns None if checks fail or there is an error
        if self.updateConfig() is None:
            gl.window.runButton.setEnabled(True)
            self.finished.emit()
            return

        result = execVerification(gl.config)
        if not result:
            print("Error occurred!")
        self.finished.emit()

    def updateConfig(self):

        global settingsfile

        #this updates gl.config entries for arguments other than file selectors!!!
        #filepath elements are populated when user selects the file
        #this function does validity checks on all entries

        if gl.config['obsFile']['file']=="":
            showMessage("ERROR: observed file has to be selected", "ERROR")
            return

        obsFile=Path(gl.config.get('obsFile').get('file'))

        if not obsFile.exists():    
            showMessage("Observed data file {} does not exist".format(obsFile), "ERROR")
            return

        if gl.config['fcstFile']['file']=="":
            showMessage("ERROR: forecast file has to be selected", "ERROR")
            return

        fcstFile =  Path(gl.config.get('fcstFile').get('file'))
        if not fcstFile.exists():
            showMessage("Forecast file {} does not exist".format(fcstFile), "ERROR")
            return

        if gl.config['summaryzonesFile']['file']=="":
            showMessage("ERROR: zones file has to be selected", "ERROR")
            return

        zonesFile=Path(gl.config.get('summaryzonesFile').get('file'))
        if not zonesFile.exists():    
            showMessage("Zones file {} does not exist".format(zonesFile), "ERROR")
            return

        if gl.config['outDir']=="":
            showMessage("ERROR: output directory has to be set", "ERROR")
            return

        outDir=Path(gl.config['outDir'])
        if not outDir.exists():
            showMessage("Output directory {} does not exist".format(outDir), "ERROR")
            return
        #check if outputdirectory is writeable
        if not os.access(outDir, os.W_OK):
            showMessage("Output directory {} exists, but you have insufficient rights to write into it".format(outDir), "ERROR")
            return

        #updating variable selections
        #for obsFile
        gl.config['obsFile']['ID'] = gl.config.get('obsFile').get('variable').index(gl.window.obsFileVariable.currentText())
        #for forecast file
        gl.config['fcstFile']['ID'] = gl.config.get('fcstFile').get('variable').index(gl.window.fcstFileVariable.currentText())
        #for zones file
        gl.config['summaryzonesFile']['ID'] = gl.config.get('summaryzonesFile').get('variable').index(gl.window.summaryzonesFileVariable.currentText())


        #checking and updating text fields
        try:
            gl.config['climStartYear'] = int(gl.window.climStartYear.text())
        except:
            showMessage("ERROR: start of climatological period has to be an integer value", "ERROR")
            return

        try:
            gl.config['climEndYear'] = int(gl.window.climEndYear.text())
        except:
            showMessage("ERROR: end of climatological period has to be an integer value", "ERROR")
            return

        try:
            gl.config['verifYear'] = int(gl.window.verifYear.text())
        except:
            showMessage("ERROR: forecast year has to be an integer value", "ERROR")
            return

        if gl.window.obsDsetCode.text()=="":
            showMessage("ERROR: Dataset code missing", "ERROR")
            return        
        else:
            gl.config['obsDsetCode'] = gl.window.obsDsetCode.text()
            

        #updates radio buttons
        if gl.window.obsFileFormatCsv.isChecked():
            gl.config['obsFileFormat']="csv"
        else:
            gl.config['obsFileFormat']="netcdf"

        if gl.window.verifAggregationSum.isChecked():
            gl.config['verifAggregation']="sum"
        else:
            gl.config['verifAggregation']="avg"

        #verification period selector
        gl.config['verifPeriod']['indx'] = gl.config.get('verifPeriod').get('season').index(gl.window.verifPeriod.currentText())

        #updating output selectors
        gl.config['outputQuantanom'] = gl.window.outputQuantanom.isChecked()
        gl.config['outputHeidke'] = gl.window.outputHeidke.isChecked()
        gl.config['outputIgnorance'] = gl.window.outputIgnorance.isChecked()
        gl.config['outputIntrate'] = gl.window.outputIntrate.isChecked()
        gl.config['outputCemhit'] = gl.window.outputCemhit.isChecked()
        gl.config['outputObscemcat'] = gl.window.outputObscemcat.isChecked()
        gl.config['outputObstercile'] = gl.window.outputObstercile.isChecked()
        gl.config['outputFcstcemcat'] = gl.window.outputFcstcemcat.isChecked()
        gl.config['outputFcsttercile'] = gl.window.outputFcsttercile.isChecked()
        gl.config['outputObsrelanom'] = gl.window.outputObsrelanom.isChecked()
        gl.config['outputObsvalue'] = gl.window.outputObsvalue.isChecked()
        gl.config['outputObsclim'] = gl.window.outputObsclim.isChecked()
        
        gl.config['outputRpss'] = gl.window.outputRpss.isChecked()

        # Write configuration to settings file
        with open(settingsfile, 'w') as fp:
            json.dump(gl.config, fp, indent=4)

        return True

    
    
            
            
            
            
            


#reading UI - has to be done before UI class is implemented
################################################################################################################

Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)
    
    
class MyApp(QtWidgets.QMainWindow, Ui_MainWindow):
    log_signal = QtCore.pyqtSignal(str)

    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)
        self.log_signal.connect(self.appendLog)

    def appendLog(self, message):
        #this appends messages to the log window - safe to call from any thread via log_signal
        self.logWindow.appendHtml(message)
        self.logWindow.ensureCursorVisible()

    def log(self, message):
        # safe to call from any thread
        self.log_signal.emit(message)

    def threadVerification(self):
        # Step 2: Create a QThread object
        self.thread = QThread()
        # Step 3: Create a worker object
        self.worker = Worker()
        # Step 4: Move worker to the thread
        self.worker.moveToThread(self.thread)
        # Step 5: Connect signals and slots
        self.thread.started.connect(self.worker.execVerificationWrapper)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(
            lambda: gl.window.runButton.setEnabled(True)
        )
        
        # Step 6: Start the thread
        self.thread.start()

        # Final resets
        gl.window.runButton.setEnabled(False)


        


# this is where magic happens
if __name__ == "__main__":
    gl.app = QtWidgets.QApplication(sys.argv)
    gl.window = MyApp()
    gl.window.show()
    
    # the process is as follows:
    #1 - load gl.config from json file
    #2 - if that fails, populate gl.config with defaults
    #3 - once gl.config loaded - populate UI with values from gl.config
    #4 - when user presses run button -  update gl.config. This: 
    #    - picks values from UI for everything apart from file paths - these are set separately,
    #    - perform validity checks
    #    - updates gl.config dictonary
    #    - dumps the gl.config dictonary to json file
    #5 - if all that is successful - run the verification
    #6 - verification checks for contents of files rather than for their presence
    showMessage("Loading config...")
    try:
        #this tries to read the config file. 
        with open(settingsfile, "r") as read_file:
            gl.config = json.load(read_file)
        showMessage("Config loaded from {}".format(settingsfile), "INFO")
    except:
        #if reading config file fails, gl.config is created with default variables defined here 
        showMessage("Problem reading from {}. Loading default settings.".format(settingsfile))
        gl.config=setConfigDefaults()
        showMessage("Default settings loaded.", "INFO")
                

    # --- Load values from config file into the UI ---
    populateUI()
    
    # --- verification is run when user has pressed run button, so nothing else to do here...
    
    sys.exit(gl.app.exec_())


# In[ ]:






# In[ ]:




