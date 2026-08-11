# -*- coding: utf-8 -*-


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

from cft import gl

import warnings
warnings.filterwarnings("ignore")

#rioxarray has to be installed, but does not have to be loaded
import cftime
import xarray as xr
#from geocube.api.core import make_geocube
import geopandas as gpd
import matplotlib.colors as colors
import cartopy.crs as ccrs
from matplotlib.patches import Patch

#defining fixed things
version="1.0"
qtCreatorFile = os.path.join(os.path.dirname(__file__), "synthesis.ui")

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

confidence_hatches={"low":"",
          "moderate":"/",
          "high":"//",
          "very high":"///"}

category_colors={"below normal":'#d2b48c',
      "normal to below":'yellow',
      "normal to above":'#0bfffb',
      "above normal":'blue'}

cmap=colors.ListedColormap(['#d2b48c', 'yellow','#0bfffb', 'blue'])

# program flow functions
################################################################################################################

def clearLog():
    gl.window.logWindow.clear()
        
def closeApp():
    sys.exit(gl.app.exec_())

def addzonesFile():
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
                variables=list(feature["properties"].keys())
            
        except:
            showMessage("Could not read {}, check if it is a valid geojson file".format(fileName[0]), "ERROR")
            return
        
        if len(variables)==0:
            showMessage("Forecast geojson file should have at least one property associated with geometric features. Current file has 0. Please check if you loaded correct file", "ERROR")
            return
        
        showMessage("Zones will be read from: {}".format(fileName[0]), "INFO")
        
        gl.window.zonesFilePath.setText(fileName[0])
        gl.config['zonesFile'] = {"file": '', "ID": 0, "variable": []}
        gl.config['zonesFile']['file'] = fileName[0]
        
        gl.window.zonesFileVariable.clear()
        for variable in variables:
            gl.window.zonesFileVariable.addItem(variable)
            gl.config['zonesFile']['variable'].append(variable)
            
        gl.config['zonesFilereference']=jsonfile
        gl.config['zonesVariable']=variable
        gl.window.zonesFileVariable.setCurrentText(variable)
        resetAll()
        gl.window.saveButton.setEnabled(True)
                        
    else:
        showMessage("Selecting forecast file aborted")
        

def saveZoneData():
    #writing zone data to gl.config
    zone=gl.window.zoneCode.currentText()
    zoneData={}
    
    signalAgree=gl.window.signalAgree.currentText()
    skillLevel=gl.window.skillLevel.currentText()
    
    zoneData["signalAgree"]=signalAgree
    zoneData["skillLevel"]=skillLevel
    zoneData["fcstCategory"]=gl.window.fcstCategory.currentText()
    
    confLevel=confLevels[skillLevel][signalAgree]
    zoneData["confLevel"]=confLevel
    gl.window.confLevel.setText(confLevel)

    gl.config['zoneData'][zone]=zoneData
    
    
    #print current status of all zones/variables in log window
    clearLog()
    showMessage("Current values:", "INFO")
    for zone in gl.config['zoneData'].keys():
        zoneData=gl.config['zoneData'][zone]
        showMessage("\nZone {}\n Skill level:{}\n Signal agreement:{}\n Confidence: {}\n Forecast category: {}".format(zone,gl.config['zoneData'][zone]['skillLevel'],gl.config['zoneData'][zone]['signalAgree'],gl.config['zoneData'][zone]['confLevel'],gl.config['zoneData'][zone]['fcstCategory']), "INFO")

    
def loadZoneData():
    #loading zone data from gl.config to UI
    zone=gl.window.zoneCode.currentText()
    zoneData=gl.config['zoneData'][zone]
    gl.window.signalAgree.setCurrentText(zoneData["signalAgree"])
    gl.window.skillLevel.setCurrentText(zoneData["skillLevel"])
    gl.window.fcstCategory.setCurrentText(zoneData["fcstCategory"])
    gl.window.confLevel.setText(zoneData["confLevel"])


def resetAll():
    #this is on change of geojson file
    #resetting zone data
    #setConfigDefaults()
    resetZones()
    resetZoneData()

def resetZoneData():
    #resetting zone data
    zone=gl.window.zoneCode.currentText()
    zoneData=gl.config['zoneData'][zone]
    gl.window.signalAgree.setCurrentText(zoneData["signalAgree"])
    gl.window.skillLevel.setCurrentText(zoneData["skillLevel"])
    gl.window.fcstCategory.setCurrentText(zoneData["fcstCategory"])
    gl.window.confLevel.setText(zoneData["confLevel"])


def resetZones():
    gl.window.zoneCode.clear()
    jsonfile=gl.config['zonesFilereference']
    zonesVariable=gl.window.zonesFileVariable.currentText()
    gl.config['zonesVariable']=zonesVariable
    gl.config["zoneData"]={}

    codes=[]
    for feature in jsonfile['features']:
        code=str(feature["properties"][zonesVariable])
        if code in codes:
            showMessage("Zone names should be unique. Check if you selected correct variable storing zone ID", "NONCRITICAL")            
        else:
            codes.append(code)
        gl.window.zoneCode.addItem(code)
        zoneData={"signalAgree": '', "skillLevel": '',"fcstCategory":'',"confLevel":''}
        gl.config['zoneData'][code]=zoneData
    loadZoneData()
    
    
    
def writeOutput():
    #checking if all populated
    for zone in gl.config['zoneData'].keys():
        for var in gl.config['zoneData'][zone].keys():
            if gl.config['zoneData'][zone][var]=="":
                showMessage("{} for zone {} missing".format(var,zone), "ERROR")
                return
            
    if gl.config['outDir']=="":
        showMessage("output directory not set", "ERROR")
        return
    
    if gl.window.fcstYear.text()=="":
        showMessage("forecast year not set", "ERROR")
        return
    else:
        fcstYear=gl.window.fcstYear.text()
        gl.config['fcstYear']=fcstYear
        
    fcstPeriod=gl.window.fcstPeriod.currentText()
        
        
    showMessage("all information provided. Writing output...", "INFO")
    geojsondict0=gl.config['zonesFilereference']
    variable=gl.config['zonesVariable']
    
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
        fcstCategory=gl.config['zoneData'][zone]["fcstCategory"]
        confLevel=gl.config['zoneData'][zone]["confLevel"]
        fcstCategoryCode=fcstCategories[fcstCategory]
        skillLevel=gl.config['zoneData'][zone]["skillLevel"]
        signalAgree=gl.config['zoneData'][zone]["signalAgree"]
        
        geojsondict['features'][i]["properties"]["finalcode_{}-{}".format(fcstYear,fcstPeriod)]=fcstCategoryCode    
        geojsondict['features'][i]["properties"]["finalcategory_{}-{}".format(fcstYear,fcstPeriod)]=fcstCategory    
        geojsondict['features'][i]["properties"]["finalconfidence".format(fcstYear,fcstPeriod)]=confLevel
        geojsondict['features'][i]["properties"]["agreement_{}-{}".format(fcstYear,fcstPeriod)]=signalAgree
        geojsondict['features'][i]["properties"]["skill_{}-{}".format(fcstYear,fcstPeriod)]=skillLevel
            
    outputfile="{}/forecast_{}-{}.geojson".format(gl.config['outDir'],gl.config['fcstYear'],gl.window.fcstPeriod.currentText())
    
    if os.path.exists(outputfile):
        showMessage("outputfile {} exists. Overwriting...".format(outputfile), "INFO")
        
    with open(outputfile,'w') as f:
        json.dump(geojsondict, f)

    showMessage("written {}".format(outputfile), "RUNTIME")
    
    #need to finish this one still
    plotforecast(outputfile)

        
def plotforecast(_outputfile):

    poly = gpd.read_file(_outputfile)
    code="finalcode_{}-{}".format(gl.config['fcstYear'],gl.window.fcstPeriod.currentText())
    
    edgecolor="0.7"
    
    fig=plt.figure(figsize=(7,5))
    pl=fig.add_subplot(1,1,1, projection=ccrs.PlateCarree())
    for conf in confidence_hatches.keys():
        selpoly=poly[poly["finalconfidence"]==conf]
        if selpoly.shape[0]>0:
            selpoly.plot(column=code,hatch=confidence_hatches[conf], ax=pl, cmap=cmap, vmin=1, vmax=5, edgecolor="0.6",lw=0.5)
            #selpoly.boundary.plot(ax=pl, color="", lw=0.5)

            
    legend_conf = []
    for conf in confidence_hatches.keys():
        legend_entry=Patch(facecolor='white', edgecolor=edgecolor, hatch=confidence_hatches[conf],label=conf)
        legend_conf.append(legend_entry)

        
    legend_cat = []
    for x in category_colors.keys():
        legend_entry=Patch(facecolor=category_colors[x], edgecolor=edgecolor, label=x)
        legend_cat.append(legend_entry)
        

    legend1=pl.legend(handles=legend_conf, loc=(1.01,0), title="Forecast confidence",handleheight=2, handlelength=3)
    legend2=pl.legend(handles=legend_cat, loc=(1.01,0.5), title="Forecast category",handleheight=2, handlelength=3)
    plt.gca().add_artist(legend1)

    plt.subplots_adjust(right=0.7)
    figurefile="{}/forecast_{}-{}.jpg".format(gl.config['outDir'],gl.config['fcstYear'],gl.window.fcstPeriod.currentText())
    pl.set_title("Forecast for {} {}".format(gl.config['fcstYear'],gl.window.fcstPeriod.currentText()))
    plt.savefig(figurefile)
    showMessage("saved {}".format(figurefile), "RUNTIME")
        
    
def getOutDir():
    showMessage("Setting output directory...")
    outDir=QtWidgets.QFileDialog.getExistingDirectory(directory='..' + os.sep)
    if outDir!='':
        gl.config['outDir']=outDir 
        gl.window.outDirPath.setText(outDir)
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
    #this populates UI based on values in gl.config dictionary

    #output directory
    gl.window.outDirPath.setText(gl.config.get('outDir'))
    
    #zones file
    gl.window.zonesFilePath.setText(os.path.basename(gl.config.get('zonesFile').get('file')))
    for var in gl.config.get('zonesFile').get('variable'):
        gl.window.zonesFileVariable.addItem(var)
    if type(gl.config.get('zonesFile').get('ID')) == type(0): 
        gl.window.zonesFileVariable.setCurrentIndex(gl.config.get('zonesFile').get('ID'))

    #forecast
    periodxs = gl.config.get('fcstPeriod').get('season')
    for periodx in periodxs:
        gl.window.fcstPeriod.addItem(periodx)  
    if type(gl.config.get('fcstPeriod').get('indx')) == type(0): 
        gl.window.fcstPeriod.setCurrentIndex(gl.config.get('fcstPeriod').get('indx'))
    gl.window.fcstYear.setText(str(gl.config.get('fcstYear')))
    
    levels = gl.config.get('signalAgree').get('level')
    for levelx in levels:
        gl.window.signalAgree.addItem(levelx)  
    if type(gl.config.get('signalAgree').get('indx')) == type(0): 
        gl.window.signalAgree.setCurrentIndex(gl.config.get('signalAgree').get('indx'))

    levels = gl.config.get('skillLevel').get('level')
    for levelx in levels:
        gl.window.skillLevel.addItem(levelx)  
    if type(gl.config.get('skillLevel').get('indx')) == type(0): 
        gl.window.skillLevel.setCurrentIndex(gl.config.get('signalAgree').get('indx'))

        
    levels = gl.config.get('fcstCategory').get('category')
    for levelx in levels:
        gl.window.fcstCategory.addItem(levelx) 
    if type(gl.config.get('fcstCategory').get('indx')) == type(0): 
        gl.window.fcstCategory.setCurrentIndex(gl.config.get('fcstCategory').get('indx'))
        
    ## attaching signals
    #it is obvious what these do
    gl.window.outDirButton.clicked.connect(getOutDir)
    gl.window.zonesFileButton.clicked.connect(addzonesFile)

    #again, obvious actions
    gl.window.zonesFileVariable.textActivated.connect(resetZones)
    gl.window.zoneCode.textActivated.connect(loadZoneData)
    gl.window.signalAgree.textActivated.connect(saveZoneData)
    gl.window.skillLevel.textActivated.connect(saveZoneData)
    gl.window.fcstCategory.textActivated.connect(saveZoneData)    
    gl.window.exitButton.clicked.connect(closeApp)
    gl.window.clearLogButton.clicked.connect(clearLog)
    gl.window.saveButton.clicked.connect(writeOutput)
    gl.window.saveButton.setEnabled(False)
    showMessage("UI ready", "INFO")



    

def showMessage(_message, _type="RUNTIME"):
    #this prints messages to log window, which are generated outside of the threaded function
    _color=msgColors[_type]
    _message = "<pre><font color={}>{}</font></pre>".format(_color, _message)
    gl.window.logWindow.appendHtml(_message)
#    gl.window.logWindow.update()
    gl.window.logWindow.ensureCursorVisible()


    
    


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
        _message=_tuple[0]
        _type=_tuple[1]
        _color=msgColors[_type]
        if _type in ["ERROR","NONCRITICAL"]:
            _message="{}: {}".format(_type,_message)
        _message = "<pre><font color={}>{}</font></pre>".format(_color, _message)
        gl.window.logWindow.appendHtml(_message)
        gl.window.logWindow.ensureCursorVisible()
            


# this is where magic happens
def main():
    gl.app = QtWidgets.QApplication(sys.argv)
    gl.window = MyApp()
    gl.window.show()
    
    showMessage("Loading config...")
    gl.config=setConfigDefaults()
    showMessage("Default settings loaded.", "INFO")
                

    # --- Load values from config into the UI ---
    populateUI()
    gl.window.confLevel.setStyleSheet("background-color:lightyellow")
    

    sys.exit(gl.app.exec_())

if __name__ == "__main__":
    main()







