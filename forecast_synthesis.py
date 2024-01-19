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

import os, sys, time
from datetime import datetime, timedelta
from netCDF4 import Dataset
import pandas as pd
import numpy as np
import geojson, json

import matplotlib
matplotlib.use('agg')
from pathlib import Path
import matplotlib.pyplot as plt

from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import QThread, QObject, QDate, QTime, QDateTime, Qt

from PyQt5.QtCore import pyqtSignal

import warnings
warnings.filterwarnings("ignore")

#rioxarray has to be installed, but does not have to be loaded
import cftime
import xarray as xr
#from geocube.api.core import make_geocube
import geopandas as gpd
import matplotlib.colors as colors
import cartopy.crs as ccrs

#defining fixed things
version="1.0"
qtCreatorFile = "forecast_synthesis.ui"

months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# these are parameters for selection of the season over which forecast is to be evaluated. 
# First value is duration of the period, second is the index of the LAST month of the target period.
# This index is 1-based, i.e. Jan is 1, Feb is 2 etc.
# For example, for JFM, the first value will be 3, second will be 3 as March is the last month of JFM.
seasonParam = {
           'JFM':[3,3],
           'FMA':[3,4],
           'MAM':[3,5],
           'AMJ':[3,6],
           'MJJ':[3,7],
           'JJA':[3,8],
           'JAS':[3,9],
           'ASO':[3,10],
           'SON':[3,11],
           'OND':[3,12],
           'NDJ':[3,1],
           'DJF':[3,2]
            }

signalAgreeLevels={"",
                   "low",
                   "moderate",
                   "high"}

skillLevels={"",
             "all low",
             "mixed/moderate",
             "all high"}

fcstCategories={"":0,
                "below normal":1,
                "normal to below":2,
                "normal to above":3,
                "above normal":4}

#first key is skillLevel,second is signalAgreeLevel
confLevels={
    "":{"":"",
        "low":"",
        "moderate":"",
        "high":""},
    "all low":{"":"",
        "low":"low",
        "moderate":"low",
        "high":"moderate"},
    "mixed/moderate":{"":"",
        "low":"low",
        "moderate":"moderate",
        "high":"high"},
    "all high":{"":"",
        "low":"moderate",
        "moderate":"high",
        "high":"very high"},
}


msgColors={"ERROR": "red",
           "INFO":"blue",
           "RUNTIME":"grey",
           "NONCRITICAL":"red",
           "SUCCESS":"green"
          }



# program flow functions
################################################################################################################

def openHelp():
    webbrowser.open(helpfile)

def clearLog():
    global window
    window.logWindow.clear()
        
def closeApp():
    sys.exit(app.exec_())

def addzonesFile():
    showMessage("Selecting forecast vector file...")
    global config
    fileName = QtWidgets.QFileDialog.getOpenFileName(window,
              'Select File', '..' + os.sep, filter="GeoJson File (*.geojson)")
    if fileName[0]!="":
        #widget will return empty string if selection cancelled        
        showMessage("Checking {}...".format(fileName[0]))
        try:
            with open(fileName[0]) as f:
                jsonfile = geojson.load(f)
                #at this stage, just keys of properties are needed. these can be read from the first feature only
                feature = jsonfile['features'][0]
                variables=list(feature["properties"].keys())
            
        except:
            showMessage("Could not read {}, check if it is a valid geojson file".format(fileName[0]), "ERROR")
            return
        
        if len(variables)==0:
            showMessage("Forecast geojson file should have at least one property associated with geometric features. Current file has 0. Please check if you loaded correct file", "ERROR")
            return
        
        showMessage("Zones will be read from: {}".format(fileName[0]), "INFO")
        
        window.zonesFilePath.setText(fileName[0])
        config['zonesFile'] = {"file": '', "ID": 0, "variable": []}
        config['zonesFile']['file'] = fileName[0]
        
        window.zonesFileVariable.clear()
        for variable in variables:
            window.zonesFileVariable.addItem(variable)
            config['zonesFile']['variable'].append(variable)
            
        config['zonesFilereference']=jsonfile
        config['zonesVariable']=variable
        window.zonesFileVariable.setCurrentText(variable)
        resetAll()
        window.saveButton.setEnabled(True)
#            print(config)
                        
    else:
        showMessage("Selecting forecast file aborted")
        

def saveZoneData():
    #writing zone data to config
    zone=window.zoneCode.currentText()
    print("Zone",zone)
    zoneData={}
    
    signalAgree=window.signalAgree.currentText()
    skillLevel=window.skillLevel.currentText()
    
    zoneData["signalAgree"]=signalAgree
    zoneData["skillLevel"]=skillLevel
    zoneData["fcstCategory"]=window.fcstCategory.currentText()
    
    confLevel=confLevels[skillLevel][signalAgree]
    zoneData["confLevel"]=confLevel
    window.confLevel.setText(confLevel)

    config['zoneData'][zone]=zoneData
    
    
    #print current status of all zones/variables in log window
    clearLog()
    showMessage("Current values:", "INFO")
    for zone in config['zoneData'].keys():
        zoneData=config['zoneData'][zone]
        showMessage("\nZone {}\n Skill level:{}\n Signal agreement:{}\n Confidence: {}\n Forecast category: {}".format(zone,config['zoneData'][zone]['skillLevel'],config['zoneData'][zone]['signalAgree'],config['zoneData'][zone]['confLevel'],config['zoneData'][zone]['fcstCategory']), "INFO")

    
def loadZoneData():
    #loading zone data from config to UI
    cont=True
    zone=window.zoneCode.currentText()
    print("Zone",zone)
    zoneData=config['zoneData'][zone]
    window.signalAgree.setCurrentText(zoneData["signalAgree"])
    window.skillLevel.setCurrentText(zoneData["skillLevel"])
    window.fcstCategory.setCurrentText(zoneData["fcstCategory"])
    window.confLevel.setText(zoneData["confLevel"])


def resetAll():
    #this is on change of geojson file
    #resetting zone data
    setConfigDefaults()
    resetZones()
    resetZoneData()

def resetZoneData():
    #resetting zone data
    cont=True
    zone=window.zoneCode.currentText()
    print("Zone",zone)
    zoneData=config['zoneData'][zone]
    window.signalAgree.setCurrentText(zoneData["signalAgree"])
    window.skillLevel.setCurrentText(zoneData["skillLevel"])
    window.fcstCategory.setCurrentText(zoneData["fcstCategory"])
    window.confLevel.setText(zoneData["confLevel"])


def resetZones():
    window.zoneCode.clear()
    jsonfile=config['zonesFilereference']
    zonesVariable=window.zonesFileVariable.currentText()
    codes=[]
    for feature in jsonfile['features']:
        print(feature["properties"])
        code=str(feature["properties"][zonesVariable])
        print("code",code)
        if code in codes:
            showMessage("Zone names should be unique. Check if you selected correct variable storing zone ID", "NONCRITICAL")            
        else:
            codes.append(code)
        window.zoneCode.addItem(code)
        zoneData={"signalAgree": '', "skillLevel": '',"fcstCategory":'',"confLevel":''}
        config['zoneData'][code]=zoneData
    loadZoneData()
    
    
    
def writeOutput():
    cont=True
    #checking if all populated
    for zone in config['zoneData'].keys():
        for var in config['zoneData'][zone].keys():
            if config['zoneData'][zone][var]=="":
                showMessage("{} for zone {} missing".format(var,zone), "ERROR")
                return
            
    if config['outDir']=="":
        showMessage("output directory not set", "ERROR")
        return
    
    if window.fcstYear.text()=="":
        showMessage("forecast year not set", "ERROR")
        return
    else:
        fcstYear=window.fcstYear.text()
        config['fcstYear']=fcstYear
        
    fcstPeriod=window.fcstPeriod.currentText()
        
        
    showMessage("all information provided. Writing output...", "INFO")
    geojsondict0=config['zonesFilereference']
    variable=config['zonesVariable']
    
    #need to do this to drop superfluous variables from dictionary
    geojsondict=json.loads(json.dumps(geojsondict0))
    
    #removing old columns, keeping only zone ID one
    for i,feature in enumerate(geojsondict0['features']):
        zone=str(geojsondict0['features'][i]["properties"][variable])
        for key in geojsondict0['features'][i]["properties"]:
            if key!=variable:
                geojsondict['features'][i]["properties"].pop(key)
                
    #adding new entries
    for i,feature in enumerate(geojsondict['features']):
        zone=str(geojsondict['features'][i]["properties"][variable])
        fcstCategory=config['zoneData'][zone]["fcstCategory"]
        confLevel=config['zoneData'][zone]["confLevel"]
        fcstCategoryCode=fcstCategories[fcstCategory]
        skillLevel=config['zoneData'][zone]["skillLevel"]
        signalAgree=config['zoneData'][zone]["signalAgree"]
        
        geojsondict['features'][i]["properties"]["finalcode_{}-{}".format(fcstYear,fcstPeriod)]=fcstCategoryCode    
        geojsondict['features'][i]["properties"]["finalcategory_{}-{}".format(fcstYear,fcstPeriod)]=fcstCategory    
        geojsondict['features'][i]["properties"]["finalconfidence_{}-{}".format(fcstYear,fcstPeriod)]=confLevel
        geojsondict['features'][i]["properties"]["agreement_{}-{}".format(fcstYear,fcstPeriod)]=signalAgree
        geojsondict['features'][i]["properties"]["skill_{}-{}".format(fcstYear,fcstPeriod)]=skillLevel
            
    outputfile="{}/forecast_{}-{}.geojson".format(config['outDir'],config['fcstYear'],window.fcstPeriod.currentText())
    
    if os.path.exists(outputfile):
        showMessage("outputfile {} exists. Overwriting...".format(outputfile), "INFO")
        
    with open(outputfile,'w') as f:
        json.dump(geojsondict, f)

    showMessage("written {}".format(outputfile), "RUNTIME")
    
    #need to finish this one still
    #plotforecast(geojsondict)

        
def plotforecast(_geojsondict):
    cont=True
    #to be done    
    
    
def getOutDir():
    global config
    showMessage("Setting output directory...")
    outDir=QtWidgets.QFileDialog.getExistingDirectory(directory='..' + os.sep)
    if outDir!='':
        config['outDir']=outDir 
        window.outDirPath.setText(outDir)
        showMessage("Output will be written to {}".format(outDir), "INFO")
    else:
        showMessage("Selecting output directory aborted")

    
def setConfigDefaults():
    config = {}
    
    #output directory
    config['outDir'] = ''   

    #zones file
    config['zonesFile'] = {"file": '',"variable": [], "ID": None}

    config['fcstYear'] = ""
    config['fcstPeriod'] = {"season": list(seasonParam.keys()),
                        "indx": 2}
    
    config['signalAgree'] = {"level": list(signalAgreeLevels),
                        "indx": 0}
    
    config['skillLevel'] = {"level": list(skillLevels),
                        "indx": 0}

    config['fcstCategory'] = {"category": list(fcstCategories.keys()),
                        "indx": 0}

    config['zoneData'] = {}
    config['zonesFilereference'] = ''
    config['zonesVariable'] = ''
    
    return config    



        
def populateUI():
    showMessage("Populating UI...")
    #this populates UI based on values in config dictionary
    global window

    #output directory
    window.outDirPath.setText(config.get('outDir'))
    
    #zones file
    window.zonesFilePath.setText(os.path.basename(config.get('zonesFile').get('file')))
    for var in config.get('zonesFile').get('variable'):
        window.zonesFileVariable.addItem(var)
    if type(config.get('zonesFile').get('ID')) == type(0): 
        window.zonesFileVariable.setCurrentIndex(config.get('zonesFile').get('ID'))

    #forecast
    periodxs = config.get('fcstPeriod').get('season')
    for periodx in periodxs:
        window.fcstPeriod.addItem(periodx)  
    if type(config.get('fcstPeriod').get('indx')) == type(0): 
        window.fcstPeriod.setCurrentIndex(config.get('fcstPeriod').get('indx'))
    window.fcstYear.setText(str(config.get('fcstYear')))
    
    levels = config.get('signalAgree').get('level')
    for levelx in levels:
        window.signalAgree.addItem(levelx)  
    if type(config.get('signalAgree').get('indx')) == type(0): 
        window.signalAgree.setCurrentIndex(config.get('signalAgree').get('indx'))

    levels = config.get('skillLevel').get('level')
    for levelx in levels:
        window.skillLevel.addItem(levelx)  
    if type(config.get('skillLevel').get('indx')) == type(0): 
        window.skillLevel.setCurrentIndex(config.get('signalAgree').get('indx'))

        
    levels = config.get('fcstCategory').get('category')
    for levelx in levels:
        window.fcstCategory.addItem(levelx) 
    if type(config.get('fcstCategory').get('indx')) == type(0): 
        window.fcstCategory.setCurrentIndex(config.get('fcstCategory').get('indx'))
        
    ## attaching signals
    #it is obvious what these do
    window.outDirButton.clicked.connect(getOutDir)
    window.zonesFileButton.clicked.connect(addzonesFile)

    #again, obvious actions
    window.zonesFileVariable.textActivated.connect(resetZones)
    window.zoneCode.textActivated.connect(loadZoneData)
    window.signalAgree.textActivated.connect(saveZoneData)
    window.skillLevel.textActivated.connect(saveZoneData)
    window.fcstCategory.textActivated.connect(saveZoneData)    
    window.exitButton.clicked.connect(closeApp)
    window.helpButton.clicked.connect(openHelp)
    window.clearLogButton.clicked.connect(clearLog)
    window.saveButton.clicked.connect(writeOutput)
    window.saveButton.setEnabled(False)
    showMessage("UI ready", "INFO")



    

def showMessage(_message, _type="RUNTIME"):
    #this print messages to log window, which are generated outside of the threaded function
    global window
    _color=msgColors[_type]
    _message = "<pre><font color={}>{}</font></pre>".format(_color, _message)
    window.logWindow.appendHtml(_message)
#    window.logWindow.update()
    window.logWindow.ensureCursorVisible()


    
    


#reading UI - has to be done before UI class is implemented
################################################################################################################

Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)
    
    
class MyApp(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)
        
        
    def reportProgress(self, _tuple):
        #this print messages to log window, which are generated in the threaded function
        global window
        _message=_tuple[0]
        _type=_tuple[1]
        _color=msgColors[_type]
        if _type in ["ERROR","NONCRITICAL"]:
            _message="{}: {}".format(_type,_message)
        _message = "<pre><font color={}>{}</font></pre>".format(_color, _message)
        window.logWindow.appendHtml(_message)
        window.logWindow.ensureCursorVisible()
            


# this is where magic happens
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MyApp()
    window.show()
    
    showMessage("Loading config...")
    config=setConfigDefaults()
    showMessage("Default settings loaded.", "INFO")
                

    # --- Load values from config file into the UI ---
    populateUI()
    window.confLevel.setStyleSheet("background-color:lightyellow")
    

    sys.exit(app.exec_())


# In[ ]:






# In[ ]:





