"""
@author: Piotr Wolski
# wolski@csag.uct.ac.za
#
# developed in 2025
#
# GUI code modified from earlier CFT version by Thembani
# forecast functionality completely revised compared to earlier versions of CFT
#
#
"""
import os, sys, time
from datetime import datetime
import pandas as pd
import numpy as np
import geojson, json
import xarray as xr

#importing libraries for GUI
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import QThread, QObject, QDate, QTime, QDateTime, Qt

#importing functions library
# file to store global variables
import gl

from functions_forecast import *
#from functions_gui import *
#from functions_preproc import *

qtCreatorFile = "cft.ui"

# Global Variables
gl.version = '5.0.0'


#not sure about this
gl.fcstyear = QDate.currentDate().year()


#these might need to be set as global variables
predictordict = {}
predictanddict = {}
predictanddict['stations'] = []
predictanddict['data'] = None
fcstPeriod = None


# ---constants---


#loading UI data
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)


#this sets up Qt window as Qt app
class MyApp(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)

        

def closeapp():
    sys.exit(app.exec_())

    
if __name__ == "__main__":
    #
    app = QtWidgets.QApplication(sys.argv)
    #initantiate app window
    gl.window = MyApp()
    #show app window
    gl.window.show()
    
    if len(sys.argv)>1:
        print(sys.argv)
        gl.configFileName=sys.argv[1]
    else:
        gl.configFileName="config.json"

    try:
        #it's a try because it covers both the case settings file does not exist, and if it is not a json file
        if os.path.exists(configFileName):
            with open(configFileName, "r") as conffile:
                gl.config = json.load(conffile)
                #would need to implement a check if settingsfile is actually well formed, not just json-parsable
                showMessage("Config loaded.")
                populateGUI()
        else:
            showMessage("Failed to load config. Creating config from built-in setting data", "NONCRITICAL")            
            createConfig()
    except:
        showMessage("Failed to load config. Creating config from built-in setting data", "NONCRITICAL")
        createConfig()


    ## Signals
    #gl.window.outputButton.clicked.connect(getOutDir)
    #gl.window.period1Radio.toggled.connect(changePeriodList)
    #gl.window.period2Radio.toggled.connect(changePeriodList)
    #gl.window.CSVRadio.toggled.connect(changeFormatType)
    #gl.window.NetCDFRadio.toggled.connect(changeFormatType)
    #gl.window.addpredictButton.clicked.connect(addPredictors)
    #gl.window.removepredictButton.clicked.connect(removePredictors)
    #gl.window.browsepredictandButton.clicked.connect(addPredictands)
    #gl.window.clearpredictandButton.clicked.connect(clearPredictands)
    #gl.window.CSVRadio.toggled.connect(setInputFormat)
    #gl.window.ZoneButton.clicked.connect(addZoneVector)
    gl.window.runButton.clicked.connect(launchForecast)
    #window.stopButton.clicked.connect(closeapp)
    gl.window.exitButton.clicked.connect(closeapp)
    sys.exit(app.exec_())



    
