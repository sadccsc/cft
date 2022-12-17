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

@author: thembani
revised by pwolski on 1 Nov 2022 to use xarray and allow more general format of netcdf files
"""

import os, sys, time
#import threading
#from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from netCDF4 import Dataset
import pandas as pd
import numpy as np
import geojson, json
#from multiprocessing import Pool, cpu_count
#from functools import partial
#from functions import *
import matplotlib
matplotlib.use('agg')
from pathlib import Path
import matplotlib.pyplot as plt

from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import QThread, QObject, QDate, QTime, QDateTime, Qt

import warnings
warnings.filterwarnings("ignore")

#rioxarray has to be installed, but does not have to be loaded
import cftime
import xarray as xr
from geocube.api.core import make_geocube
import geopandas
import matplotlib.colors as colors
import cartopy.crs as ccrs
import webbrowser
from rasterstats import zonal_stats


qtCreatorFile = "verification.ui"
settingsfile = 'verification.json'


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
           'DJF':[3,2],
           'JF':[2,2],
           'FM':[2,3],
           'MA':[2,4],
           'AM':[2,5],
           'MJ':[2,6],
           'JJ':[2,7],
           'JA':[2,8],
           'AS':[2,9],
           'SO':[2,10],
           'ON':[2,11],
           'ND':[2,12],
           'DJ':[2,1],
           'Jan':[1,1],
           'Feb':[1,2],
           'Mar':[1,3],
           'Apr':[1,4],
           'May':[1,5],
           'Jun':[1,6],
           'Jul':[1,7],
           'Aug':[1,8],
           'Sep':[1,9],
           'Oct':[1,10],
           'Nov':[1,11],
           'Dec':[1,12]
                  }





#reading UI
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)


# original functions written by Thembani. Piotr modified some names for consistency.

class MyApp(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)

        
def closeApp():
    sys.exit(app.exec_())


def addBaseVector():
    global config
    window.fcstVectorLabel.setText('')
    config['fcstvector'] = {"file": '', "ID": 0, "attr": []}
    window.fcstVectorCombo.clear()
    vectorfieldsx = []
    fileName = QtWidgets.QFileDialog.getOpenFileName(window,
              'Add File', '..' + os.sep, filter="GeoJson File (*.geojson)")
    config['fcstvector']['file'] = fileName[0]
    if os.path.isfile(config.get('fcstvector').get('file')):
        with open(config.get('fcstvector',{}).get('file')) as f:
            zonejson = geojson.load(f)
        for zonekey in zonejson['features']:
            for zonetype in zonekey.properties:
                vectorfieldsx.append(zonetype)
        zonefields = []
        [zonefields.append(x) for x in vectorfieldsx if x not in zonefields]
        for x in range(len(zonefields)):
            xx = zonefields[x]
            window.fcstVectorCombo.addItem(str(xx))
            config['fcstvector']['attr'].append(str(xx))
            if xx == 'fcst_class':
                window.fcstVectorCombo.setCurrentIndex(x)
        window.fcstVectorLabel.setText(os.path.basename(config.get('fcstvector',{}).get('file')))


def addObserved():
    global config
    window.obsLabel.setText('')
    config['observed'] = {"file": '', "ID": 0, "attr": []}
    window.obsCombo.clear()
    if window.CSVRadio.isChecked() == True:
        config['inputFormat'] = "CSV"
        fileNames = QtWidgets.QFileDialog.getOpenFileNames(window,
                'Add File(s)', '..' + os.sep, filter="CSV File (*.csv)")
    elif window.NetCDFRadio.isChecked() == True:
        config['inputFormat'] = "NetCDF"
        try:
            fileName = QtWidgets.QFileDialog.getOpenFileName(window,
                      'Add File', '..' + os.sep, filter="NetCDF File (*.nc*)")
            config['observed']['file'] = fileName[0]
            observed = Dataset(fileName[0])
            for key in observed.variables.keys():
                if key not in ['Y', 'X', 'Z', 'T', 'zlev', 'time', 'lon', 'lat','latitude','longitude']:
                    window.obsCombo.addItem(key)
                    config['observed']['attr'].append(key)
            observed.close()
        except:
            showMessage(
                "Could not read observed file, check if it is a valid NetCDF")
            return
    window.obsLabel.setText(os.path.basename(config.get('observed',{}).get('file')))   



def getOutDir():
    global config
    config['outDir'] = QtWidgets.QFileDialog.getExistingDirectory(directory='..' + os.sep)
    window.outDirLabel.setText(config.get('outDir'))


def changeFormatType():
    global config
    window.obsLabel.clear()
    window.obsCombo.clear()
    if window.CSVRadio.isChecked() == True:
        config['inputFormat'] = "CSV"
    else:
        config['inputFormat'] = "NetCDF"

def changeComposition():
    global config
    if window.cumRadio.isChecked() == True:
        config['composition'] = "Sum"
    else: 
        config['composition'] = "Avg"


def writeConfig():
    global settingsfile
    global config
    config['climStartYear'] = int(window.startyearLineEdit.text())
    config['climEndYear'] = int(window.endyearLineEdit.text())
    config['fcstyear'] = int(window.fcstyearlineEdit.text())
    config['observed']['ID'] = config.get('observed').get('attr').index(window.obsCombo.currentText())
    config['fcstvector']['ID'] = config.get('fcstvector').get('attr').index(window.fcstVectorCombo.currentText())
    config['period']['indx'] = config.get('period').get('season').index(window.periodCombo.currentText())
    config['obsDsetCode'] = window.obsDsetCode.text()
    config['quantanom'] = window.quantanomCheckbox.isChecked()
    config['heidke'] = window.quantanomCheckbox.isChecked()
    config['ignorance'] = window.ignoranceCheckbox.isChecked()
    config['intrate'] = window.intrateCheckbox.isChecked()
    config['cemhit'] = window.cemhitCheckbox.isChecked()
    config['obscemcat'] = window.obscemcatCheckbox.isChecked()
    config['obsrelanom'] = window.obsrelanomCheckbox.isChecked()
    config['obsvalue'] = window.obsvalueCheckbox.isChecked()
    config['rpss'] = window.rpssCheckbox.isChecked()

    # Write configuration to settings file
    with open(settingsfile, 'w') as fp:
        json.dump(config, fp, indent=4)



# functions added by Piotr

def skill_single(_fprob,_obs_terc,_index):
    if _index=="heidke_hits_max":
        #this will return a map for each year
        if np.isnan(_fprob[0,0])==False and np.isnan(_obs_terc[0])==False:
            #this will be 1,2,3
            #print(_obs_terc[0])
            #print(np.isnan(_obs_terc[0]))
            temp=np.concatenate([_fprob,_obs_terc.reshape(-1,1)], axis=1)
            #this is heidtke hits
            _hits=np.apply_along_axis(get_heidke_hit,1,temp)
            return(_hits)
        else:
            _hits=np.copy(_obs_terc)
            _hits[:]=np.nan
        return(_hits)
        
    if _index=="interest_rate":
        #this will return a map for each year
        if np.isnan(_fprob[0,0])==False and np.isnan(_obs_terc[0])==False:
            temp=np.concatenate([_fprob,_obs_terc.reshape(-1,1)], axis=1)
            _intrate=np.apply_along_axis(get_interest_rate,1,temp)
            return(_intrate)
        else:
            _intrate=np.copy(_obs_terc)
            _intrate[:]=np.nan
            return(_intrate)        
    if _index=="ignorance":
        #this will return a map for each year
        if np.isnan(_fprob[0,0])==False and np.isnan(_obs_terc[0])==False:
            #this will be 1,2,3
            temp=np.concatenate([_fprob,_obs_terc.reshape(-1,1)], axis=1)
            _ignorance=np.apply_along_axis(get_ignorance,1,temp)
            return(_ignorance)
        else:
            _ignorance=np.copy(_obs_terc)
            _ignorance[:]=np.nan
            return(_ignorance)

def get_heidke_hit(_x):
    #print(_x)
    mxs=(_x==np.max(_x[0:3])).astype(int)
    #_x[3] is in 1,2,3    
    mxs=mxs[int(_x[3]-1)]*1/np.sum(mxs)
    return mxs


def cemcat_to_tercprob(_cat):
    _cem_probs=np.array([[40,35,25],[35,40,25],[25,40,35],[25,35,40]])/100
    _probs=np.array([_cem_probs[int(x-1)] if not np.isnan(x) else np.array([np.nan,np.nan,np.nan]) for x in _cat])
    return _probs


def val_to_cemcat(_val,_obs):
    _out=np.copy(_val)
    if np.sum(np.isnan(_val))==0:
        _q1,_q2,_q3=np.quantile(_obs,[0.33,0.5,0.66])
        _out[_val<=_q1]=1
        _out[(_val>_q1) & (_val<=_q2)]=2
        _out[(_val>_q2) & (_val<=_q3)]=3
        _out[_val>_q3]=4
    return(_out)

def val_to_terc(_val,_obs):
    _out=np.copy(_val)
    if np.sum(np.invert(np.isnan(_val)))>0:
        _q1,_q2=np.quantile(_obs,[0.33,0.66])
        _out[_val<=_q1]=1
        _out[(_val>_q1) & (_val<=_q2)]=2
        _out[_val>_q2]=3
    else:
        _out[:]=np.nan
    return(_out.astype(float))

def cemcat_to_tercprob(_cat):
    _cem_probs=np.array([[40,35,25],[35,40,25],[25,40,35],[25,35,40]])/100
    _probs=np.array([_cem_probs[int(x-1)] if not np.isnan(x) else np.array([np.nan,np.nan,np.nan]) for x in _cat])
    return _probs 

def get_interest_rate(_x):
    #_x[3] is in 1,2,3
    _prob=_x[int(_x[3]-1)]
    _intrate=_prob/0.33
    return _intrate

def get_ignorance(_x):
        _prob=_x[int(_x[3]-1)]
        if _prob==0:
            _prob=0.01
        _ign=-np.log2(_prob)
        return _ign
    
def get_cem_hit(_f,_o):
    #_f and _o are cemcat of forecast and observations
    if np.sum(np.invert(np.isnan(_f)))>0:
        _temp=np.copy(_f)
        _temp[:]=0
        _temp[_f==_o]=3 #hit
        _temp[np.abs((_f-_o))==1]=2
        _temp[np.abs((_f-_o))==2]=1
    else:
        _temp=np.copy(_f)
        _temp[:]=np.nan
    return _temp


def get_rpss(_f,_o):
    if np.sum(np.invert(np.isnan(_f)))>0 and np.sum(np.invert(np.isnan(_o)))>0:
        fcst_cumprobs=np.array([[40,75,100],[35,75,100],[25,65,100],[25,60,100]])/100
        obs_cumprobs=np.array([[100,100,100],[0,100,100],[0,100,100],[0,0,100]])/100
        clim_cumprobs=np.array([[33,66,100],[33,66,100],[33,66,100],[33,66,100]])/100
        _fcp=fcst_cumprobs[int(_f-1),:]
        _ocp=obs_cumprobs[int(_o-1),:]
        _ccp=clim_cumprobs[int(_o-1),:]
        _rps=np.sum((_fcp-_ocp)**2)
        _rpss=np.sum((_ccp-_ocp)**2)
        _temp=1-(_rps/_rpss)
        #rpss - 0 for climatological forecast, 1 for perfect forecast
    else:
        _temp=np.copy(_f)
        _temp[:]=np.nan
    return _temp

def val_to_quantanom(_val,_obs):
    _out=np.copy(_val)
    if np.sum(np.isnan(_val))==0:
        _val=_val[np.invert(np.isnan(_val))]
        _out=(_obs <= _val).mean().reshape(-1)
    return(_out)

def plot_map(_data,_cmap,_levels,_vmin,_vmax, _title, _cbar_label,_ticklabels, _mask, _filename,_geometryfile):
#    geometryfile="maps/sadc_continental_boundary.geojson"
#    sadc = geopandas.read_file(geometryfile)
    regions = geopandas.read_file(_geometryfile)
    regions=geopandas.read_file("/work/data/sarcof/gis/maps/SADC/GeoJSON/sadc_countries.geojson")
    fig=plt.figure(figsize=(5,4))
    pl=fig.add_subplot(1,1,1, projection=ccrs.PlateCarree())
    if _mask is not None:
        _sign,_val=_mask
        if _sign=="above":
            _data=_data.where(_data<_val)
        else:
            _data=_data.where(_data>_val)
    m=_data.plot(cmap=_cmap, vmin=_vmin,vmax=_vmax, add_colorbar=False)
    
    regions.boundary.plot(ax=pl, linewidth=1, color="0.1")    
    plt.title(_title, fontsize=10)
    ax=fig.add_axes([0.82,0.25,0.02,0.5])
    if _levels is None:
        cbar = fig.colorbar(m, cax=ax, label=_cbar_label)
    else:
        cbar = fig.colorbar(m, cax=ax,ticks=_levels, label=_cbar_label)
    if _ticklabels is not None:
        cbar.ax.set_yticklabels(_ticklabels)
    plt.subplots_adjust(bottom=0.05,top=0.9,right=0.8,left=0.05)
    plt.savefig(_filename, dpi=300)
    showMessage(_filename)
#    plt.show()
    plt.close()
    

def openHelp():
    webbrowser.open('verification_help.html')

def showMessage(_message):
    global window
    window.statusbar.showMessage(_message)
    print(_message)

    
def zonal_mean(_src,_vctr):
    try:
        affine = _src.rio.transform()
        zonalscore = zonal_stats(_vctr, _src[0,:,:].data, affine=affine, nodata=np.nan)
        zonalscore = pd.DataFrame(zonalscore)
    except:
        _src=_src.reindex(latitude=_src.latitude[::-1])
        affine = _src.rio.transform()
        zonalscore = zonal_stats(_vctr, _src[0,:,:].data, affine=affine, nodata=np.nan)
        zonalscore = pd.DataFrame(zonalscore)
    return(zonalscore)



def plot_zonal_histogram(_data, _title, _filename, _ylabel, _hline, _text, _xticklabels):
    fig=plt.figure(figsize=(6,4))
    pl=fig.add_subplot(1,1,1)
    plt.title(_title, fontsize=10)
    
    _data.plot.bar()
    
    pl.axhline(_hline, linestyle="--",color="0.7")
    pl.text(0.02,0.98,_text, ha='left', va='top', transform=pl.transAxes)
    pl.set_xlabel("zone")
    pl.set_ylabel(_ylabel)
    pl.set_xticklabels(_xticklabels)
    plt.subplots_adjust(bottom=0.15,top=0.9, right=0.9,left=0.15)
    plt.savefig(_filename, dpi=300)
    showMessage(_filename)
#    plt.show()
    plt.close()

    
    

def execVerification():
    global config
    writeConfig()

    #######
    start_time = time.time()
    showMessage("Start time: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    showMessage("Reading user input...")

    fcstshp =  Path(config.get('fcstvector').get('file'))
    if not fcstshp.exists():    
        showMessage("Forecast vector map does not exist")
        return
#        sys.exit()

    if not Path(config.get('observed').get('file')).exists():    
        showMessage("Observed data file does not exist")
#        return
        sys.exit()

    fcstVar = config.get('fcstvector').get('attr')[config.get('fcstvector').get('ID')]
    fcstCode=fcstVar
    
    
    outDir=config.get('outDir')
    obsYear = int(config.get('fcstyear'))
    climStartYr = int(config.get('climStartYear'))
    climEndYr = int(config.get('climEndYear'))
    obsSeason = config.get('period').get('season')[config.get('period').get('indx')]
    
    obsFile=config.get('observed').get('file')
    obsVar = config.get('observed').get('attr')[config.get('observed').get('ID')]
    obsDsetCode=config.get('obsDsetCode')

    indx=config.get('period').get("indx")
    seas=config.get('period').get("season")[indx]
    obsYear = config.get('fcstyear')
    doQuantanom = config.get('quantanom')
    doHeidke = config.get('heidke')
    doIgnorance = config.get('ignorance')
    doIntrate = config.get('quantanom')
    doCemhit = config.get('cemhit')
    doObscemcat = config.get('obscemcat')
    doObsrelanom = config.get('obsrelanom')
    doObsvalue = config.get('obsvalue')
    doRpss = config.get('rpss')

    
    # these are parameters for plots
    seq=[10]*10+[20]*10+[30]*13+[50]*34+[70]*13+[80]*10+[90]*10
    levels_quantanom = [0,10,20,30,70,80,90,100]
    cmap_quantanom=colors.ListedColormap([plt.cm.get_cmap('BrBG', 100)(x) for x in seq])
    
    plot_params={
        "obs_quantanom":{"title":"Percentile anomaly in {}-{}\nbased on {} data and {}-{} normals".format(obsSeason,obsYear,obsDsetCode, climStartYr,climEndYr),
                      "ticklabels":None,
                      "levels":levels_quantanom,
                      "cmap":cmap_quantanom,
                      "vmin":0,
                      "vmax":100,
                     "cbar_label":"percentile",
                     "mask":None,
                      "filename":"{}/obs_percentile-anomaly_{}-{}_{}.jpg".format(outDir, obsSeason, obsYear,obsDsetCode)

                     },
        "obs_relanom":{"title":"Relative anomaly (% of long-term mean) in {}-{}\nbased on {} data and {}-{} normals".format(obsSeason,obsYear,obsDsetCode, climStartYr,climEndYr),
                      "ticklabels":None,
                      "levels":np.arange(-100,100,20),
                      "cmap":plt.cm.BrBG,
                      "vmin":-100,
                      "vmax":100,
                     "cbar_label":"percent",
                     "mask":None,
                      "filename":"{}/obs_relative-anomaly_{}-{}_{}.jpg".format(outDir, obsSeason, obsYear,obsDsetCode)
                     },
        "obs_season":{"title":"Observed rainfall in {}-{}\nbased on {} data".format(obsSeason,obsYear,obsDsetCode),
                      "ticklabels":None,
                      "levels":None,
                      "cmap":plt.cm.BrBG,
                      "vmin":None,
                      "vmax":None,
                     "cbar_label":None,
                     "mask":None,
                      "filename":"{}/obs_values_{}-{}_{}.jpg".format(outDir, obsSeason, obsYear,obsDsetCode)
                     },
        
        "obs_cemcat":{"title":"Observed rainfall categories for {}-{}\nbased on {} data and {}-{} normals".format(obsSeason,obsYear,obsDsetCode, climStartYr,climEndYr),
                      "ticklabels":['BN', 'N-BN','N-AN','AN'],
                      "levels":(np.array([1,2,3,4])*5/4) - 0.6,
                      "cmap":colors.ListedColormap(['#d2b48c', 'yellow','#0bfffb', 'blue']),
                      "vmin":0,
                      "vmax":5,
                     "cbar_label":"",
                     "mask":None,
                      "filename":"{}/obs_CEM-category_{}-{}_{}.jpg".format(outDir, obsSeason,obsYear, obsDsetCode)
                     },
        "obs_terc":{"title":"Observed tercile categories for {}-{}\nbased on {} data and {}-{} normals".format(obsSeason,obsYear,obsDsetCode, climStartYr,climEndYr),
                      "ticklabels":['BN', 'N', 'AN'],
                      "levels":(np.array([1,2,3,])*5/4) - 0.6,
                      "cmap":colors.ListedColormap(['#d2b48c', 'white','#0bfffb']),
                      "vmin":0,
                      "vmax":4,
                     "cbar_label":"",
                     "mask":None,
                      "filename":"{}/obs_tercile-category_{}-{}_{}.jpg".format(outDir, obsSeason, obsYear,obsDsetCode)
                     },
        "clim_mean":{"title":"Climatological rainfall in {}\nbased on {} data and {}-{} normals".format(obsSeason,obsDsetCode, climStartYr,climEndYr),
                      "ticklabels":None,
                      "levels":None,
                      "cmap":plt.cm.BrBG,
                      "vmin":None,
                      "vmax":None,
                     "cbar_label":None,
                     "mask":None,
                      "filename":"{}/obs_longterm-mean_{}_{}.jpg".format(outDir, obsSeason, obsDsetCode)
                     },
        "fcst_cemcat":{"title":"Category forecast for {}".format(fcstVar),
                      "ticklabels":['BN','N-BN','N-AN','AN'],
                      "levels":(np.array([1,2,3,4])*5/4) - 0.6,
                      "cmap":colors.ListedColormap(['#d2b48c', 'yellow','#0bfffb', 'blue']),
                      "vmin":0,
                      "vmax":5,
                     "cbar_label":"",
                     "mask":None,
                      "filename":"{}/fcst_CEM-category_{}.jpg".format(outDir, fcstCode)
                     },
        "fcst_cemhit":{"title":"Hit/miss map \n {} forecast vs. {}-{} observations ({})".format(fcstVar,obsSeason,obsYear,obsDsetCode),
                      "ticklabels":['error', 'half-miss','half-hit','hit'],
                      "levels":np.array([0.5,1.5,2.5,3.5]),
                      "cmap1":plt.cm.get_cmap('RdBu', 4),
                      "cmap":colors.ListedColormap([plt.cm.get_cmap('RdBu', 10)(x) for x in [2,4,5,7]]),
                       "vmin":0,
                      "vmax":4,
                     "cbar_label":"",
                     "mask":None,
                      "filename":"{}/fcst_CEM-hit_{}_{}-{}_{}.jpg".format(outDir, fcstCode, obsSeason, obsYear,obsDsetCode)
                     },
        "fcst_intrate":{"title":"Interest rate score\n {} forecast vs. {}-{} observations ({})".format(fcstCode, obsSeason,obsYear,obsDsetCode),
                      "ticklabels":None,
                      "levels":None,
                      "cmap":plt.cm.Greys,
                      "vmin":0,
                      "vmax":10,
                     "cbar_label":"%",
                     "mask":["below",0],
                      "filename":"{}/fcst_interest-rate_{}_{}-{}_{}.jpg".format(outDir, fcstCode, obsSeason,obsYear,obsDsetCode)
                     },
        "fcst_ignorance":{"title":"Ignorance score \n{} forecast vs. {}-{} observations ({})".format(fcstVar,obsSeason,obsYear,obsDsetCode),
                      "ticklabels":None,
                      "levels":None,
                      "cmap":plt.cm.Greys,
                      "vmin":0,
                      "vmax":1,
                     "cbar_label":"",
                     "mask":["below",0],
                      "filename":"{}/fcst_ignorance_{}_{}-{}_{}.jpg".format(outDir, fcstCode, obsSeason,obsYear,obsDsetCode)
                     },
        "fcst_hhit":{"title":"Heidke hit score \n{} forecast vs. {}-{} observations ({})".format(fcstVar,obsSeason,obsYear,obsDsetCode),
                      "ticklabels":None,
                      "levels":None,
                      "cmap":plt.cm.BrBG,
                      "vmin":0,
                      "vmax":1,
                     "cbar_label":"",
                     "mask":["below",0],
                      "filename":"{}/fcst_heidke-hit_{}_{}-{}_{}.jpg".format(outDir, fcstCode,obsSeason,obsYear, obsDsetCode)
                     },
        "fcst_rpss":{"title":"Ranked probabilty skill score (RPSS) \n{} forecast vs. {}-{} observations ({})".format(fcstVar,obsSeason,obsYear,obsDsetCode),
                      "ticklabels":None,
                      "levels":None,
                      "cmap":plt.cm.BrBG,
                      "vmin":-10,
                      "vmax":10,
                     "cbar_label":"",
                     "mask":None,
                      "filename":"{}/fcst_rpss_{}_{}-{}_{}.jpg".format(outDir, fcstCode, obsSeason, obsYear, obsDsetCode)
                     }
    }

    
    showMessage("\nReading input files...")
    showMessage("Reading observed data")
    
    #this fixes the IRI netcdf calendar problem
    showMessage(obsFile)
    try:
        ds = xr.open_dataset(obsFile, decode_times=False)
    except:
        showMessage("file cannot be read. please check if the file is properly formatted")
        return
        
    if "T" in ds.coords.keys():
        showMessage("found T - renaming to time")
        ds=ds.rename({"T":"time"})
    if ds["time"].attrs['calendar'] == '360':
        ds["time"].attrs['calendar'] = '360_day'
    ds = xr.decode_cf(ds)
    ds=ds.convert_calendar("standard", align_on="date")
    
    if "X" in ds.coords.keys():
        showMessage("found X - renaming to longitude")
        ds=ds.rename({"X":"longitude"})
    if "Y" in ds.coords.keys():
        showMessage("found Y - renaming to longitude")
        ds=ds.rename({"Y":"latitude"})        
    if "lon" in ds.coords.keys():
        showMessage("found lon - renaming to logitude")
        ds=ds.rename({"lon":"longitude"})
    if "lat" in ds.coords.keys():
        showMessage("found lat - renaming to latitude")
        ds=ds.rename({"lat":"latitude"})
    #this creates dataArray from dataset
    obs=ds[obsVar]
    obs=obs.rio.write_crs("epsg:4326") #adding crs

    if "units" in obs.attrs:
        obsunits=obs.attrs["units"]    
        showMessage("found units: {}".format(obsunits))
    else:
        showMessage("observed data does not have units attribute. Setting that attribute to unknown. If that is a problem - \
              please add units attribute to the netcdf file using nco or similar software")
        obsunits="unknown"
        
    
    #rasterize the forecast vector
    showMessage('Reading forecast vector file')
    #reading geojson file
    print(fcstshp)
    try:
        fcstVector = geopandas.read_file(fcstshp)
    except:
        showMessage("file cannot be read. please check if the file is properly formatted")
        return

    zonenames=fcstVector["ID"]
 
    showMessage("clipping obs to forecast extent")
    try:
        obs=obs.rio.clip(fcstVector.geometry.values, "epsg:4326") #clipping to fcst geojson
    except:
        showMessage("variable {} appears not to have spatial coordinates. Did you chose correct variable to process?".format(obsVar))
        return
    obs=obs.chunk("auto")#.chunk(dict(time=-1)
    #print(obs.shape)
    #print(obs.chunksizes)
    obs=obs.chunk(dict(time=-1))
    #print(obs.chunksizes)
    obs=obs.where(obs>=0)
   

    # compute long term statistics 
    seasDuration,seasLastMon=seasonParam[seas]
    
    showMessage('computing long term statistics')
    
    # compute season totals for current year
    if config.get('composition', 'Sum') == "Sum":
        obsroll = obs.rolling(time=seasDuration, center=False).sum()
    else:
        obsroll = obs.rolling(time=seasDuration, center=False).mean()

    seltime=str(obsYear)+"-"+months[seasLastMon-1]
    try:
        obs_season=obsroll.sel(time=seltime)
    except:
        showMessage("observed data does not cover {}. Please check your data, or adjust verification period so that it falls within the period covered by observed data.".format(seltime))
        return
#        sys.exit()

    showMessage('plotting observed rainfall map')    
    pars=plot_params["obs_season"]
    plot_map(obs_season,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
         pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],fcstshp)

    obs_season.attrs=""
   
    outputds = obs_season.to_dataset(name = 'obs_value')


    showMessage('rasterizing forecast vector file')
    fcst_ds = make_geocube(vector_data=fcstVector, like=obs) #gridding/rasterizing forecast
    fcst_cemcat=fcst_ds[fcstVar]

    fcsttime=obs_season.time.data

    fcst_cemcat=fcst_cemcat.expand_dims(time=fcsttime)

    if "x" in fcst_cemcat.coords.keys():
        showMessage("found x - renaming to longitude")
        fcst_cemcat=fcst_cemcat.rename({"x":"longitude"})
    if "y" in fcst_cemcat.coords.keys():
        showMessage("found y - renaming to latitude")
        fcst_cemcat=fcst_cemcat.rename({"y":"latitude"})
 

    #need to assign coordinates due to float rounding issues
    fcst_cemcat=fcst_cemcat.assign_coords(latitude=obs.latitude.data)
    fcst_cemcat=fcst_cemcat.assign_coords(longitude=obs.longitude.data)
    fcst_cemcat.attrs=""
    outputds["fcst_class"]=fcst_cemcat
    
    showMessage('plotting forecast CEM categories map')    
    pars=plot_params["fcst_cemcat"]
    plot_map(fcst_cemcat,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
         pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],fcstshp)

    
    
    
    
    
    showMessage("\nCalcualating prerequisites")
   
    showMessage("calculating climatology")
    #climatology period
    obs_clim=obsroll.sel(time=obsroll.time.dt.month==seasLastMon).sel(time=slice(str(climStartYr),str(climEndYr)))

    #climatological mean
    clim_mean = obs_clim.mean("time")
    
    showMessage("plotting climatological mean")
    
    #add obsunits to plotconfig
    #obsunits="mm/day"
    plot_params["clim_mean"]["cbar_label"]=obsunits

    pars=plot_params["clim_mean"]
    plot_map(clim_mean,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
             pars["cbar_label"],pars["ticklabels"],pars["mask"], pars["filename"],fcstshp)
    
    outputds["obs_clim"]=clim_mean
    
    #quantiles
    showMessage("calculating percentiles")
    clim_quant=obs_clim.quantile([0.33,0.50,0.66], dim="time")
    
        
    showMessage("calculating relative anomaly")
    #relative anomaly
    obs_relanom=(obs_season-clim_mean)/clim_mean*100
    
    if doObsrelanom:
        showMessage("plotting relative anomaly")    
        pars=plot_params["obs_relanom"]
        plot_map(obs_relanom,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                 pars["cbar_label"],pars["ticklabels"],pars["mask"], pars["filename"],fcstshp)

    outputds["obs_relanom"]=obs_relanom

    
    showMessage("calculating observed terciles")
    #obs terciles
    temp=xr.apply_ufunc(
        val_to_terc,
        obs_season.load(),
        obs_clim.rename({"time":"times"}).load(),
        input_core_dims=[["time"],["times"]],
        output_core_dims=[["time"]],
        vectorize=True
    )
    obs_terc=temp.transpose("time","latitude","longitude")
    
#    pars=plot_params["obs_terc"]
#    plot_map(obs_terc,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
#             pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"])


    showMessage("converting CEM categories to tercile probabilities")
    #forecast tercileprobability
    temp=xr.apply_ufunc(
        cemcat_to_tercprob, 
        fcst_cemcat,
        input_core_dims=[["time"]],
        output_core_dims=[["time","tercile"]],
        vectorize=True
    )
    
    
    fcst_tercprob=temp.transpose("time","tercile","latitude","longitude").assign_coords(
        {"tercile":["BN","N","AN"]})
    fcst_tercprob.name="tercprob"

    
    
    
    
    showMessage("\nCalcualating verification indices - user selected")
    
    #obs cemcategories
    if doObscemcat:
        showMessage("calculating observed CEM forecast categories")
        temp=xr.apply_ufunc(
            val_to_cemcat,
            obs_season.load(),
            obs_clim.rename({"time":"times"}).load(),
            input_core_dims=[["time"],["times"]],
            output_core_dims=[["time"]],
            vectorize=True
        )
        obs_cemcat=temp.transpose("time","latitude","longitude")
        obs_cemcat.name="cemcat"
        
        pars=plot_params["obs_cemcat"]
        plot_map(obs_cemcat,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                 pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],fcstshp)
        
        outputds["obs_class"]=obs_cemcat
            
    else:
        showMessage("skipping CEM forecast categories")


        
        
        
    #quantile anomaly
    if doQuantanom:
        showMessage("calculating quantile anomalies")
        temp=xr.apply_ufunc(
            val_to_quantanom,
            obs_season.load(),
            obs_clim.rename({"time":"times"}).load(),
            input_core_dims=[["time"],["times"]],
            output_core_dims=[["time"]],
            vectorize=True
        )

        obs_quantanom=temp.transpose("time","latitude","longitude")
        obs_quantanom.name="quantanom"
        
        showMessage("plotting percentile anomaly")    
        pars=plot_params["obs_quantanom"]
        plot_map(obs_quantanom*100,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                 pars["cbar_label"],pars["ticklabels"],pars["mask"], pars["filename"],fcstshp)
        outputds["obs_quantanom"]=obs_quantanom
        
    else:
        showMessage("skipping quantile anomalies")



        
        
        #heidke hits
    if doHeidke:
        showMessage("calclating Heidke hit scores")
        try:
            temp=xr.apply_ufunc(
                skill_single,
                fcst_tercprob,
                obs_terc,
                "heidke_hits_max",
                input_core_dims=[["time","tercile"],["time"],[]],
                exclude_dims=set(["tercile"]),
                output_core_dims=[["time"]],
                vectorize=True
            )
            fcst_hhit=temp.transpose("time","latitude","longitude")
            fcst_hhit.name="hhit"
        except Exception as e: 
            exc_type, exc_obj, exc_tb = sys.exc_info()
            print("ERROR:\n",e,exc_type, "\nin line:",exc_tb.tb_lineno)
            
            #return
        pars=plot_params["fcst_hhit"]
        plot_map(fcst_hhit,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                 pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],fcstshp)
        outputds["fcst_heidke"]=fcst_hhit
        zonal_hhit=zonal_mean(fcst_hhit,fcstVector)
        plot_zonal_histogram(zonal_hhit["mean"], "Heidke skill score (most probable category)", "{}/{}_{}_{}-{}_{}.jpg".format(outDir, "zonal_heidke",fcstVar,obsSeason,obsYear,obsDsetCode),"HHS [-]", 0, "no-skill forecast=0\nperfect forecast=1",zonenames)

        
    else:
        showMessage("skipping Heidke hit scores")




        
        
        
    #interest rate
    if doIntrate:
        showMessage("calculating interest rate")
        temp=xr.apply_ufunc(
            skill_single,
            fcst_tercprob,
            obs_terc,
            "interest_rate",
            input_core_dims=[["time","tercile"],["time"],[]],
            exclude_dims=set(["tercile"]),
            output_core_dims=[["time"]],
            vectorize=True
        )

        fcst_intrate=temp.transpose("time","latitude","longitude")
        fcst_intrate.name="intrate"
        intratemax=max(abs(fcst_intrate.min().data), abs(fcst_intrate.max().data))*2
        plot_params["fcst_intrate"]["vmax"]=intratemax
        
        
        pars=plot_params["fcst_intrate"]
        plot_map(fcst_intrate,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                 pars["cbar_label"],pars["ticklabels"],pars["mask"], pars["filename"],fcstshp)

        outputds["fcst_intrate"]=fcst_intrate
        
        zonal_intrate=zonal_mean(fcst_intrate,fcstVector)
        plot_zonal_histogram(zonal_intrate["mean"], "Average interest rate", "{}/{}_{}_{}_{}_{}.jpg".format(outDir, "zonal_intrate",fcstVar,obsSeason,obsYear,obsDsetCode),"interest rate [%]", 0, "climatological forecast=0\nperfect forecast- 100%",zonenames)

    else:
        showMessage("skipping interest rate")

        
        
        
        
    #ignorance
    if doIgnorance:
        showMessage("calculating ignorance score")
        temp=xr.apply_ufunc(
            skill_single,
            fcst_tercprob,
            obs_terc,
            "ignorance",
            input_core_dims=[["time","tercile"],["time"],[]],
            exclude_dims=set(["tercile"]),
            output_core_dims=[["time"]],
            vectorize=True
        )
        fcst_ignorance=temp.transpose("time","latitude","longitude")
        fcst_ignorance.name="ignorance"
        ignorancemax=max(abs(fcst_ignorance.min().data), abs(fcst_ignorance.max().data))*2
        plot_params["fcst_ignorance"]["vmax"]=ignorancemax
        
        
        pars=plot_params["fcst_ignorance"]
        plot_map(fcst_ignorance,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                 pars["cbar_label"],pars["ticklabels"],pars["mask"], pars["filename"],fcstshp)
        outputds["fcst_ignorance"]=fcst_ignorance
        
        zonal_ignorance=zonal_mean(fcst_ignorance,fcstVector)
        plot_zonal_histogram(zonal_ignorance["mean"], "Ignorance score", "{}/{}_{}_{}-{}_{}.jpg".format(outDir, "zonal_ignorance",fcstVar,obsSeason,obsYear,obsDsetCode),"Ignorance [-]", 1.58, "climatological forecast=1,58\n0 - perfect score\n(lower values better)",zonenames)

    else:
        showMessage("skipping ignorance score")


        
        
    #rpss
    if doRpss:
        showMessage("calcuating RPSS score")
        temp=xr.apply_ufunc(
            get_rpss,
            fcst_cemcat,
            obs_cemcat,
            input_core_dims=[["time"],["time"]],
            output_core_dims=[["time"]],
            vectorize=True
        )
        fcst_rpss=temp.transpose("time","latitude","longitude")
        fcst_rpss.name="rpss"
        rpssmax=max(abs(fcst_rpss.min().data), abs(fcst_rpss.max().data))
        
        pars=plot_params["fcst_rpss"]
        plot_map(fcst_rpss,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                 pars["cbar_label"],pars["ticklabels"],pars["mask"], pars["filename"],fcstshp)
        outputds["fcst_rpss"]=fcst_rpss
        
        zonal_rpss=zonal_mean(fcst_rpss,fcstVector)
        plot_zonal_histogram(zonal_rpss["mean"], "RPSS", "{}/{}_{}_{}-{}_{}.jpg".format(outDir, "zonal_rpss",fcstVar,obsSeason,obsYear,obsDsetCode),"[-]", 0, "climatological forecast=0\nperfect score=1", zonenames)
        
    else:
        showMessage("skipping RPSS score")


        
        
        
    #cem hits
    if doCemhit:
        showMessage("calculating CEM hit scores")
        temp=xr.apply_ufunc(
            get_cem_hit,
            fcst_cemcat,
            obs_cemcat,
            input_core_dims=[["time"],["time"]],
            output_core_dims=[["time"]],
            vectorize=True
        )
        fcst_cemhit=temp.transpose("time","latitude","longitude")
        fcst_cemhit.name="cemhit"
        
        
        pars=plot_params["fcst_cemhit"]
        plot_map(fcst_cemhit,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                 pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],fcstshp)


        showMessage("creating hit/miss graph for zones")
        nzones=len(fcstVector)
        
        fcst_cemhit=fcst_cemhit.rio.write_crs("epsg:4326")

        alldata=[]
        for i,geom in enumerate(fcstVector.geometry.values):
            try:
                clipped = fcst_cemhit.rio.clip(geom, "epsg:4326")
                clipped=clipped.data.flatten()
            except:
                clipped=np.array([])
                print("no data")
            alldata=alldata+[clipped[~np.isnan(clipped)]]
    
        bins=[-0.5,0.5,1.5,2.5,3.5]
        labels=["error","half-miss","half-hit","hit"]
        cols=colors.ListedColormap([plt.cm.get_cmap('RdBu', 10)(x) for x in [2,4,5,7]])
        cols=[cols(i) for i in range(4)]
        
        if nzones>6:
            nx,ny=6,2
            fx,fy=7,3
        else:
            nx,ny=nzones+1,1
            fx,fy=7,2
            
        fig=plt.figure(figsize=(fx,fy))
        for i,zdata in enumerate(alldata):
            pl=fig.add_subplot(ny,nx,i+1)   
            if len(zdata)>0:
                vals,b=np.histogram(zdata, bins=bins, normed=True)
                pl.pie(vals, colors=cols)
            else:
                pl.pie([1], colors=["white"])
                pl.text(0.5,0.5,"no data", ha='center', va='center', transform=pl.transAxes, color="0.8")
            pl.set_title("zone {}".format(zonenames[i]))
        plt.legend(labels, loc=(1,0))
        title="hits/misses in zones \n{} forecast vs. {}-{} observations ({})".format(fcstVar,obsSeason,obsYear,obsDsetCode)
        plt.suptitle(title, fontsize=10)
        plt.subplots_adjust(bottom=0.05,top=0.75,right=0.8,left=0.05)
        filename="{}/histogram_cemhitmiss_{}_{}.jpg".format(outDir, fcstCode, obsDsetCode)
        showMessage(filename)
        plt.savefig(filename, dpi=300)

        
        outputds["fcst_classhit"]=fcst_cemhit
        
        zonal_cemhit=zonal_mean(fcst_cemhit,fcstVector)
        
    else:
        showMessage("skipping CEM hit scores")


        
        
        
        
        
    showMessage("\nPreparing summaries")

    
    outputds.to_netcdf("{}/maps_verification_{}_{}-{}_{}.nc".format(outDir,fcstVar,obsSeason,obsYear,obsDsetCode))

    
    summarylabels=[]
    summarydata=[]
    if doIntrate:
       summarylabels=summarylabels+["average interest rate"]
       summarydata=summarydata+[fcst_intrate.mean().data]
    if doHeidke:
       summarylabels=summarylabels+["Heidke skill score"]
       summarydata=summarydata+[fcst_hhit.mean().data]
    if doRpss:
       summarylabels=summarylabels+["RPSS"]
       summarydata=summarydata+[fcst_rpss.mean().data]
    if doIgnorance:
       summarylabels=summarylabels+["Ignorance skill score"]
       summarydata=summarydata+[fcst_ignorance.mean().data]
    
    # In[53]:
     
   # fcst_cemhit.to_netcdf("test.nc")

    showMessage('\nFinished running verification. Check output directory {} for output'.format(outDir))



# this is where magic happens
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MyApp()
    window.show()
    showMessage("Loading config...")
    try:
        #this tries to read the config file. 
        with open(settingsfile, "r") as read_file:
            config = json.load(read_file)
        showMessage("Settings loaded from {}".format(settingsfile))
    except:
        #if reading config file fails, config is created with default variables defined here 
        showMessage("Problem reading from {}. Loading default settings.".format(settingsfile))
        config = {}
        config['Version'] = "4.1.0"
        config['outDir'] = '/work/data/sarcof/verification/'
        config['fcstvector'] = {"file": '/work/data/sarcof/verification/sadc_OND_zones_forecast2022.geojson',
                                "attr": ["OND_2022"], "ID": 0}
        config['fcstattrib'] = "OND_2022"
        config['observed'] = {"file": '/work/data/sarcof/verification/pr_mon_cams-opi_197901-202210.nc', 
                                "attr": ["prcp"], "ID": 0}
        config['obsDsetCode']="CAMS"
        config['climStartYear'] = 1981
        config['climEndYear'] = 2010
        config['inputFormat'] = "NetCDF"
        config['composition'] = "Sum"
        config['fcstyear'] = "2022"
        config['period'] = {"season": list(seasonParam.keys()),
                            "indx": 20}


        config["quantanom"] = True
        config["heidke"] = False
        config["ignorance"] = False
        config["intrate"] = True
        config["cemhit"] = False
        config["obscemcat"] = True
        config["obsrelanom"] = False
        config["obsvalue"] = False
        config["rpss"] = False


        showMessage("Default settings loaded.")

    # --- Load values into the UI ---
    #
    showMessage("Loading values to UI")

    window.outDirLabel.setText(config.get('outDir'))
    window.fcstVectorLabel.setText(os.path.basename(config.get('fcstvector').get('file')))
    for attr in config.get('fcstvector').get('attr'):
        window.fcstVectorCombo.addItem(attr)
    if type(config.get('fcstvector').get('ID')) == type(0): 
        window.fcstVectorCombo.setCurrentIndex(config.get('fcstvector').get('ID'))
    #
    window.obsLabel.setText(os.path.basename(config.get('observed').get('file')))
    for attr in config.get('observed').get('attr'):
        window.obsCombo.addItem(attr)
    if type(config.get('observed').get('ID')) == type(0): 
        window.obsCombo.setCurrentIndex(config.get('observed').get('ID'))

    window.obsDsetCode.setText(config.get('obsDsetCode'))
    #
    periodxs = config.get('period').get('season')
    for periodx in periodxs:
        window.periodCombo.addItem(periodx)  
    if type(config.get('period').get('indx')) == type(0): 
        window.periodCombo.setCurrentIndex(config.get('period').get('indx'))
    #     
    if config.get('inputFormat') == "CSV":
        window.CSVRadio.setChecked(True)
    else:
        window.NetCDFRadio.setChecked(True)
    #
    if config.get('composition') == "Sum":
        window.cumRadio.setChecked(True)
    else:
        window.avgRadio.setChecked(True)
    #
    window.fcstVectorLabel.setText(os.path.basename(config.get('fcstvector',{}).get('file')))
    window.startyearLineEdit.setText(str(config.get('climStartYear')))
    window.endyearLineEdit.setText(str(config.get('climEndYear')))
    window.fcstyearlineEdit.setText(str(config.get('fcstyear')))

    window.quantanomCheckbox.setChecked(bool(config.get('quantanom')))
    window.heidkeCheckbox.setChecked(bool(config.get('heidke')))
    window.ignoranceCheckbox.setChecked(bool(config.get('ignorance')))
    window.intrateCheckbox.setChecked(bool(config.get('intrate')))
    window.cemhitCheckbox.setChecked(bool(config.get('cemhit')))
    window.obscemcatCheckbox.setChecked(bool(config.get('obscemcat')))
    window.obsrelanomCheckbox.setChecked(bool(config.get('obsrelanom')))
    window.obsvalueCheckbox.setChecked(bool(config.get('obsvalue')))
    window.rpssCheckbox.setChecked(bool(config.get('rpss')))

    ## Signals
    window.outDirButton.clicked.connect(getOutDir)
    window.fcstVectorButton.clicked.connect(addBaseVector)
    window.CSVRadio.toggled.connect(changeFormatType)
    window.NetCDFRadio.toggled.connect(changeFormatType)
    window.cumRadio.toggled.connect(changeComposition)
    window.avgRadio.toggled.connect(changeComposition)
    window.obsButton.clicked.connect(addObserved)
    window.runButton.clicked.connect(execVerification)
    window.exitButton.clicked.connect(closeApp)
    window.helpButton.clicked.connect(openHelp)
    sys.exit(app.exec_())


# In[ ]:




