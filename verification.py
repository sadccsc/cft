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
version="4.1.0"


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
from geocube.api.core import make_geocube
import geopandas as gpd
import matplotlib.colors as colors
import cartopy.crs as ccrs
import webbrowser
from rasterstats import zonal_stats

#defining fixed things
qtCreatorFile = "verification.ui"
settingsfile = 'verification.json'
helpfile='./verification_help.html'

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

msgColors={"ERROR": "red",
           "INFO":"blue",
           "RUNTIME":"grey",
           "NONCRITICAL":"red",
           "SUCCESS":"green"
          }




# functions to calculate skill indices
################################################################################################################

def skill_single(_fprob,_obs_terc,_index):
    
    if _index=="heidke_hits_max":
        #this will return a map for each year
        if np.isnan(_fprob[0,0])==False and np.isnan(_obs_terc[0])==False:
            #this will be 1,2,3
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
        _q1,_q2,_q3=np.nanquantile(_obs,[0.33,0.5,0.66])
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
    _intrate=((_prob/0.33)-1)*100
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
        _temp=np.array(1-(_rps/_rpss)).reshape(-1).astype(float)
        #rpss - 0 for climatological forecast, 1 for perfect forecast
    else:
        _temp=np.copy(_f).astype(float)
        _temp[:]=np.nan
        
    return _temp

def val_to_quantanom(_val,_obs):
    _out=np.copy(_val)
    if np.sum(np.isnan(_val))==0:
        _val=_val[np.invert(np.isnan(_val))]
        _out=(_obs <= _val).mean().reshape(-1)
    return(_out)

    

# helper functions
################################################################################################################

def zonal_mean(_src,_summaryzonesVector,_summaryzonesName,_summaryzonesVar,_obsFileFormat):
    if _obsFileFormat=="netcdf":
        try:
            affine = _src.rio.transform()
            zonalscore = zonal_stats(_summaryzonesVector, _src[0,:,:].data, affine=affine, nodata=np.nan)
        except:
            _src=_src.reindex(latitude=_src.latitude[::-1])
            affine = _src.rio.transform()
            zonalscore = zonal_stats(_summaryzonesVector, _src[0,:,:].data, affine=affine, nodata=np.nan)
        zonalscore = pd.DataFrame(zonalscore)
    else:
        alldata=[]
        crossed=_src.overlay(_summaryzonesVector, how="intersection")
        for val in _summaryzonesName:
            sel=crossed[_summaryzonesVar]==val
            meanval=np.nanmean(crossed[sel][0])
            minval=np.nanmin(crossed[sel][0])
            maxval=np.nanmax(crossed[sel][0])
            countval=len(crossed[sel][0])
            alldata=alldata+[[minval,maxval,meanval,countval]]
        zonalscore = pd.DataFrame(alldata, columns=["min","max","mean","count"])
    return(zonalscore)


def neat_vmax(_value):
    _order=np.floor(np.log10(_value))
    _x=_value/(10**_order)
    return(np.ceil(_x)*10**_order)

def get_cmap(_data, _cmap, _vmin,_vmax,_ncat,_centre):
    #this generates categorical colormap
    
    if _vmax=="auto":
        #if vmax is to be calculated automatically
        _vmax=np.nanquantile(_data, 0.95)
        _vmax=neat_vmax(_vmax)
    if _vmin=="auto":
        #vmin will be symmetrical around 0 to vmax
        vmin=-vmax
    
    _catwidth=(_vmax-_vmin)/_ncat
    _levels = np.arange(_vmin,_vmax,_catwidth)
    
    _smax=100
    if _centre is None:
        _smin=0
    else:
        _smin=(1-((_vmax-_vmin)/(2*_vmax)))*100        
    _step=(_smax-_smin)/_ncat
    _seq=np.arange(_smin,_smax,_step)
    _cmap=colors.ListedColormap([plt.cm.get_cmap(_cmap, 100)(int(x)) for x in _seq])

    return({"cmap":_cmap, "levels":_levels, "vmin":_vmin, "vmax":_vmax,"ticklabels":None})


def get_plotparams(_data,_plotvar,currentoutDir,obsSeason,obsYear,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar):
    if _plotvar=="obs_quantanom":
        title="Percentile anomaly \n{}-{}".format(obsSeason,obsYear)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/obs_percentile-anomaly_{}-{}_{}.jpg".format(currentoutDir, obsSeason, obsYear,obsDsetCode)
        seq=[10]*10+[20]*10+[30]*13+[50]*34+[70]*13+[80]*10+[90]*10
        levels = [0,10,20,30,70,80,90,100]
        cmap=colors.ListedColormap([plt.cm.get_cmap('BrBG', 100)(x) for x in seq])
        vmin=0
        vmax=100     
        cmapdict={"cmap":cmap, "levels":levels, "vmin":vmin, "vmax":vmax, "ticklabels":None}
        cmapdict["mask"]=None
        cmapdict["cbar_label"]="percentile of distribution"

    if _plotvar=="obs_relanom":
        title="Relative anomaly \n {}-{}".format(obsSeason,obsYear)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/obs_relative-anomaly_{}-{}_{}.jpg".format(currentoutDir, obsSeason, obsYear,obsDsetCode)        
        seq=[10,20,30,40,50,50,60,70,80,90]
        levels = [-100,-80,-60,-40,-20,0,20,40,60,80,100]
        collist=[plt.cm.get_cmap('BrBG', 100)(x) for x in seq]
        collist[4]=(1,1,1,1)
        collist[5]=(1,1,1,1)
        cmap=colors.ListedColormap(collist)
        cmapdict={"cmap":cmap, "levels":levels, "vmin":-100, "vmax":100, "ticklabels":None}
        cmapdict["mask"]=None
        cmapdict["cbar_label"]="% of long-term mean"
        
    if _plotvar=="obs_season":
        title="Observed rainfall \n {}-{}".format(obsSeason,obsYear)
        annot="based on {} data".format(obsDsetCode)
        filename="{}/obs_values_{}-{}_{}.jpg".format(currentoutDir, obsSeason, obsYear,obsDsetCode)
        cmapdict=get_cmap(_data,"YlGnBu",0,"auto",10,None)
        cmapdict["mask"]=None
        cmapdict["cbar_label"]="mm"

    if _plotvar=="obs_cemcat":
        title="Observed rainfall categories \n{}-{}".format(obsSeason,obsYear)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/obs_CEM-category_{}-{}_{}.jpg".format(currentoutDir, obsSeason,obsYear, obsDsetCode)
        ticklabels=['BN', 'N-BN','N-AN','AN']
        levels=np.array([1,2,3,4])*5/4 - 0.6
        cmap=colors.ListedColormap(['#d2b48c', 'yellow','#0bfffb', 'blue'])
        vmin=0
        vmax=5
        cmapdict={"cmap":cmap, "levels":levels, "vmin":vmin, "vmax":vmax, "ticklabels":ticklabels}
        cmapdict["mask"]=None
        cmapdict["cbar_label"]="category"
        
    if _plotvar== "obs_terc":
        title="Observed tercile categories\n{}-{}".format(obsSeason,obsYear)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/obs_tercile-category_{}-{}_{}.jpg".format(currentoutDir, obsSeason, obsYear,obsDsetCode)
        ticklabels=['BN', 'N', 'AN']
        levels=np.array([1,2,3,])*5/4 - 0.6
        cmap=colors.ListedColormap(['#d2b48c', 'white','#0bfffb'])
        vmin=0
        vmax=4
        cmapdict={"cmap":cmap, "levels":levels, "vmin":vmin, "vmax":vmax, "ticklabels":ticklabels}
        cmapdict["mask"]=None
        cmapdict["cbar_label"]="category"
        
    if _plotvar=="clim_mean":
        title="Climatological rainfall for {}".format(obsSeason)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/obs_longterm-mean_{}_{}.jpg".format(currentoutDir, obsSeason, obsDsetCode)
        cmapdict=get_cmap(_data,"YlGnBu",0,"auto",10,None)
        cmapdict["mask"]=None
        cmapdict["cbar_label"]="mm"
        
    if _plotvar=="fcst_cemcat":
        title="Category forecast for {}".format(fcstVar)
        annot=""
        filename="{}/fcst_CEM-category_{}.jpg".format(currentoutDir, fcstCode)
        ticklabels=['BN', 'N-BN','N-AN','AN']
        levels=np.array([1,2,3,4])*5/4 - 0.6
        cmap=colors.ListedColormap(['#d2b48c', 'yellow','#0bfffb', 'blue'])
        vmin=0
        vmax=5
        cmapdict={"cmap":cmap, "levels":levels, "vmin":vmin, "vmax":vmax, "ticklabels":ticklabels}
        cmapdict["title"]=title
        cmapdict["filename"]=filename
        cmapdict["mask"]=None
        cmapdict["cbar_label"]="category"
        
    if _plotvar=="fcst_cemhit":
        title="Hit/miss (CEM definition) \n {} forecast vs. {}-{} observations".format(fcstVar,obsSeason,obsYear)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/fcst_CEM-hit_{}_{}-{}_{}.jpg".format(currentoutDir, fcstCode, obsSeason, obsYear,obsDsetCode)
        ticklabels=['error', 'half-miss','half-hit','hit']
        levels=np.array([0.5,1.5,2.5,3.5])
        cmap=colors.ListedColormap([plt.cm.get_cmap('RdBu', 10)(x) for x in [2,4,5,7]])
        vmin=0
        vmax=4
        cmapdict={"cmap":cmap, "levels":levels, "vmin":vmin, "vmax":vmax, "ticklabels":ticklabels}
        cmapdict["mask"]=None
        cmapdict["cbar_label"]=""
        
    if _plotvar=="fcst_intrate":
        title="Interest rate score\n {} forecast vs. {}-{} observations".format(fcstCode, obsSeason,obsYear)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/fcst_interest-rate_{}_{}-{}_{}.jpg".format(currentoutDir, fcstCode, obsSeason,obsYear,obsDsetCode)
        cmapdict=get_cmap(_data,"BrBG",-100,100,10,None)
        cmapdict["mask"]=None
        cmapdict["cbar_label"]="%"
        
    if _plotvar=="fcst_ignorance":
        title="Ignorance score \n{} forecast vs. {}-{} observations".format(fcstVar,obsSeason,obsYear)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/fcst_ignorance_{}_{}-{}_{}.jpg".format(currentoutDir, fcstCode, obsSeason,obsYear,obsDsetCode)
        cmapdict=get_cmap(_data,"Greys",0,10,10,None)
        cmapdict["mask"]=None
        cmapdict["cbar_label"]="score"
        
    if _plotvar=="fcst_hhit":
        title="Heidke hit score \n{} forecast vs. {}-{} observations".format(fcstVar,obsSeason,obsYear)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/fcst_heidke-hit_{}_{}-{}_{}.jpg".format(currentoutDir, fcstCode,obsSeason,obsYear, obsDsetCode)
        ticklabels=['miss', 'hit']
        levels=np.array([0.5,1.5])
        cmap=colors.ListedColormap([plt.cm.get_cmap('BrBG', 10)(x) for x in [3,6]])
        vmin=0
        vmax=2
        cmapdict={"cmap":cmap, "levels":levels, "vmin":vmin, "vmax":vmax, "ticklabels":ticklabels}

        cmapdict["mask"]=None
        cmapdict["cbar_label"]="score"
        
    if _plotvar=="fcst_rpss":
        title="Ranked probabilty skill score (RPSS) \n{} forecast vs. {}-{} observations".format(fcstVar,obsSeason,obsYear)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/fcst_rpss_{}_{}-{}_{}.jpg".format(currentoutDir, fcstCode, obsSeason, obsYear, obsDsetCode)
        vmin=-1
        vmax=1
        cmapdict=get_cmap(_data,"BrBG",vmin,vmax,10,None)
        cmapdict["mask"]=None
        cmapdict["cbar_label"]="score"
                
    cmapdict["title"]=title
    cmapdict["annot"]=annot
    cmapdict["filename"]=filename
        
    return(cmapdict)




# program flow functions
################################################################################################################

def openHelp():
    webbrowser.open(helpfile)

def clearLog():
    global window
    window.logWindow.clear()
        
def closeApp():
    sys.exit(app.exec_())

def addFcstFile():
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
            variables=list(feature.properties.keys())
        except:
            showMessage("Could not read {}, check if it is a valid geojson file".format(fileName[0]), "ERROR")
            return
        
        if len(variables)==0:
            showMessage("Forecast geojson file should have at least one property associated with geometric features. Current file has 0. Please check if you loaded correct file", "ERROR")
            return
        
        showMessage("Forecast will be read from: {}".format(fileName[0]), "INFO")
        
        window.fcstFilePath.setText(fileName[0])
        config['fcstFile'] = {"file": '', "ID": 0, "variable": []}
        config['fcstFile']['file'] = fileName[0]
        
        window.fcstFileVariable.clear()
        for variable in variables:
            window.fcstFileVariable.addItem(variable)
            config['fcstFile']['variable'].append(variable)
            
    else:
        showMessage("Selecting forecast file aborted")

def addsummaryzonesFile():
    showMessage("Selecting zones vector file...")
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
            variables=list(feature.properties.keys())
        except:
            showMessage("Could not read {}, check if it is a valid geojson file".format(fileName[0]), "ERROR")
            return
        
        if len(variables)==0:
            showMessage("Zones geojson file should have at least one property associated with geometric features. Current file has 0. Please check if you loaded correct file", "ERROR")
            return
        
        showMessage("Zones will be read from {}".format(fileName[0]), "INFO")
        
        config['summaryzonesFile'] = {"file": '', "ID": 0, "variable": []}
        config['summaryzonesFile']['file'] = fileName[0]
        window.summaryzonesFilePath.setText(fileName[0])
        
        window.summaryzonesFileVariable.clear()
        for variable in variables:
            config['summaryzonesFile']['variable'].append(variable)
            window.summaryzonesFileVariable.addItem(variable)
            
    else:
        showMessage("Selecting zones file aborted")
    
    

def addObsFile():
    showMessage("Selecting file with observations...")    
    global config
    
    if window.obsFileFormatCsv.isChecked() == True:
        filter="CSV File (*.csv)"
        filetype="csv"
    
    elif window.obsFileFormatNetcdf.isChecked() == True:
        filter="NetCDF File (*.nc*)"
        filetype="netcdf"
        
    fileName = QtWidgets.QFileDialog.getOpenFileName(window,
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
        
        config['obsFile'] = {"file": '', "ID": 0, "variable": []}
        config['obsFile']['file'] = fileName[0]
        window.obsFilePath.setText(fileName[0])
        
        window.obsFileVariable.clear()
        for variable in variables:
            config['obsFile']['variable'].append(variable)
            window.obsFileVariable.addItem(variable)
            
    else:
        showMessage("Selecting observations file aborted")

    
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


def changeFormatType():
    global config
    
    #resetting obsFile entry
    window.obsFilePath.clear()
    window.obsFileVariable.clear()
    config['obsFile'] = {"file": '', "ID": 0, "variable": []}
    


    
def setConfigDefaults():
    config = {}
    config['Version'] = version
    #output directory
    config['outDir'] = ''   

    #forecast file
    config['fcstFile'] = {"file": '', "variable": [], "ID": None}
    #zones file
    config['summaryzonesFile'] = {"file": '',"variable": [], "ID": None}
    #observed file
    config['obsFile'] = {"file": '',"variable": [], "ID": None}
    
    config['obsFileFormat'] = "netcdf"
    config['obsDsetCode'] = ""

    #climatology
    config['climStartYear'] = 1981
    config['climEndYear'] = 2010

    #verification parameters
    config['verifAggregation'] = "sum"
    config['verifYear'] = ""
    config['verifPeriod'] = {"season": list(seasonParam.keys()),
                        "indx": 20}
    #outputs
    config["outputQuantanom"] = True
    config["outputHeidke"] = False
    config["outptIgnorance"] = False
    config["outputIntrate"] = True
    config["outputCemhit"] = False
    config["outputObscemcat"] = True
    config["outputObsrelanom"] = False
    config["outputObsvalue"] = False
    config["outputRpss"] = False
    return config    



        
def populateUI():
    showMessage("Populating UI...")

    #this populates UI based on values in config dictionary
    global window

    #output directory
    window.outDirPath.setText(config.get('outDir'))
    #forecast file
    window.fcstFilePath.setText(os.path.basename(config.get('fcstFile').get('file')))
    for var in config.get('fcstFile').get('variable'):
        window.fcstFileVariable.addItem(var)
    if type(config.get('fcstFile').get('ID')) == type(0): 
        window.fcstFileVariable.setCurrentIndex(config.get('fcstFile').get('ID'))

    #zones file
    window.summaryzonesFilePath.setText(os.path.basename(config.get('summaryzonesFile').get('file')))
    for var in config.get('summaryzonesFile').get('variable'):
        window.summaryzonesFileVariable.addItem(var)
    if type(config.get('summaryzonesFile').get('ID')) == type(0): 
        window.summaryzonesFileVariable.setCurrentIndex(config.get('summaryzonesFile').get('ID'))

    #observations
    window.obsFilePath.setText(os.path.basename(config.get('obsFile').get('file')))
    for var in config.get('obsFile').get('variable'):
        window.obsFileVariable.addItem(var)
    if type(config.get('obsFile').get('ID')) == type(0): 
        window.obsFileVariable.setCurrentIndex(config.get('obsFile').get('ID'))
    window.obsDsetCode.setText(config.get('obsDsetCode'))


    if config.get('obsFileFormat') == "netcdf":
        window.obsFileFormatNetcdf.setChecked(True)
    else:
        window.obsFileFormatCsv.setChecked(True)


    #climatology
    window.climStartYear.setText(str(config.get('climStartYear')))
    window.climEndYear.setText(str(config.get('climEndYear')))

    #verification
    periodxs = config.get('verifPeriod').get('season')
    for periodx in periodxs:
        window.verifPeriod.addItem(periodx)  
    if type(config.get('verifPeriod').get('indx')) == type(0): 
        window.verifPeriod.setCurrentIndex(config.get('verifPeriod').get('indx'))
    window.verifYear.setText(str(config.get('verifYear')))

    if config.get('verifAggregation') == "sum":
        window.verifAggregationSum.setChecked(True)
    else:
        window.verifAggregationAvg.setChecked(True)

    #outputs
    window.outputQuantanom.setChecked(bool(config.get('outputQuantanom')))
    window.outputHeidke.setChecked(bool(config.get('outputHeidke')))
    window.outputIgnorance.setChecked(bool(config.get('outputIgnorance')))
    window.outputIntrate.setChecked(bool(config.get('outputIntrate')))
    window.outputCemhit.setChecked(bool(config.get('outputCemhit')))
    window.outputObscemcat.setChecked(bool(config.get('outputObscemcat')))
    window.outputObsrelanom.setChecked(bool(config.get('outputObsrelanom')))
    window.outputObsvalue.setChecked(bool(config.get('outputObsvalue')))
    window.outputRpss.setChecked(bool(config.get('outputRpss')))

    ## attaching signals
    #it is obvious what these do
    window.outDirButton.clicked.connect(getOutDir)
    window.fcstFileButton.clicked.connect(addFcstFile)
    window.obsFileButton.clicked.connect(addObsFile)
    window.summaryzonesFileButton.clicked.connect(addsummaryzonesFile)
    #changing format wipes out the obs file selection, thus functions for this
    window.obsFileFormatCsv.toggled.connect(changeFormatType)
    window.obsFileFormatNetcdf.toggled.connect(changeFormatType)
    #again, obvious actions
    window.runButton.clicked.connect(window.threadVerification)
    window.exitButton.clicked.connect(closeApp)
    window.helpButton.clicked.connect(openHelp)
    window.clearLogButton.clicked.connect(clearLog)
    showMessage("UI ready", "INFO")



    

def showMessage(_message, _type="RUNTIME"):
    #this print messages to log window, which are generated outside of the threaded function
    global window
    _color=msgColors[_type]
    _message = "<pre><font color={}>{}</font></pre>".format(_color, _message)
    window.logWindow.appendHtml(_message)
#    window.logWindow.update()
    window.logWindow.ensureCursorVisible()




    
#threading
# Step 1: Create a worker class
class Worker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(tuple)
    
    ################################################################################################################
    #workhorse function    
    
    def execVerification(self):
#        self.exception=None
#        try:
            #clearLog()
            global config

            # this picks up values from UI and performs some rudimentary checks and saves them into config
            # config is then dumped to json file
            # function returns None if checks fail or there is an error

            if self.updateConfig() is None:
                window.runButton.setEnabled(True)
                return

            #-------------------------------------------------------------------------------------------------
            #starting verification
            
            start_time = time.time()
            self.progress.emit(("Start time: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"RUNTIME"))
                        
            #-------------------------------------------------------------------------------------------------
            #reading user inputs from UI
            
            self.progress.emit(("\nReading user inputs...\n","RUNTIME"))
            
            #no check if input entries and files exist as it was done in updateConfig
            fcstFile =  Path(config.get('fcstFile').get('file'))
            fcstVar = config.get('fcstFile').get('variable')[config.get('fcstFile').get('ID')]

            summaryzonesFile=Path(config.get('summaryzonesFile').get('file'))
            summaryzonesVar = config.get('summaryzonesFile').get('variable')[config.get('summaryzonesFile').get('ID')]

            obsFile=Path(config.get('obsFile').get('file'))
            obsVar = config.get('obsFile').get('variable')[config.get('obsFile').get('ID')]

            outDir=Path(config.get('outDir'))

            obsYear = int(config.get('verifYear'))
            climStartYr = int(config.get('climStartYear'))
            climEndYr = int(config.get('climEndYear'))
            obsSeason = config.get('verifPeriod').get('season')[config.get('verifPeriod').get('indx')]

            obsDsetCode=config.get('obsDsetCode')
            
            obsFileFormat=config.get('obsFileFormat')
                        
            indx=config.get('verifPeriod').get("indx")
            seas=config.get('verifPeriod').get("season")[indx]

            outputQuantanom = config.get('outputQuantanom')
            outputHeidke = config.get('outputHeidke')
            outputIgnorance = config.get('outputIgnorance')
            outputIntrate = config.get('outputIntrate')
            outputCemhit = config.get('outputCemhit')
            outputObscemcat = config.get('outputObscemcat')
            outputObsrelanom = config.get('outputObsrelanom')
            outputObsvalue = config.get('outputObsvalue')
            outputRpss = config.get('outputRpss')
            
            #checks on input
            
            if climStartYr>=climEndYr:
                self.progress.emit(("Climatological period start year ({}) larger than end year ({}). Terminating...".format(climStartYr,climEndYr), "ERROR"))
                return

            if climEndYr-climStartYr<20:
                self.progress.emit(("Climatological period starting in {} and ending in {} is only {} years long. That is rather short. Please reconsider.".format(climStartYr,climEndYr,climEndYr-climStartYr+1), "NONCRITICAL"))
            
            #checking dependencies
            if outputCemhit:
                outputObscemcat=True
            if outputRpss:
                outputObscemcat=True

            #output files will use this code
            fcstCode=obsSeason+str(obsYear)

            #checking and creating output directory
            currentoutDir="{}/verification_{}-{}".format(outDir,seas,obsYear)

            if not os.path.exists(currentoutDir):
                self.progress.emit(("Creating {}".format(currentoutDir), "INFO"))
                try:
                    os.mkdir(currentoutDir)
                except:
                    self.progress.emit(("Could not create {}. Stopping...".format(currentoutDir), "ERROR"))
                    return

                
                
                
            #-------------------------------------------------------------------------------------------------
            #read and rasterize the forecast vector file
            
            self.progress.emit(('\nReading forecast file...',"RUNTIME"))
            self.progress.emit((str(fcstFile),"RUNTIME"))

            #reading geojson file
            try:
                fcstVector = gpd.read_file(fcstFile)
            except:
                self.progress.emit(("File {} cannot be read. please check if the file is properly formatted".format(fcstFile), "ERROR","RUNTIME"))
                return

            #check for forecast categories here
            test=np.unique(fcstVector[fcstVar])
            test=[x not in [1,2,3,4] for x in test]
            if np.sum(test)>0:
                self.progress.emit(("Forecast variable should have four values (1,2,3,4) denoting four CEM forecast categories. This is not the case. Please check if {} file is properly formatted and if {} variable of that file the one that describes forecast".format(fcstFile,fcstVar), "ERROR"))
                return

            self.progress.emit(("Successfuly read forecast data from {}".format(fcstFile), "INFO"))


            
            #-------------------------------------------------------------------------------------------------
            # reading observations
            
            self.progress.emit(("\nReading observations...","RUNTIME"))
            self.progress.emit((str(obsFile.resolve()),"RUNTIME"))

            #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            #this is where code is different for csv and netcdf formats
            if obsFileFormat=="netcdf":
                try:
                    #decode_times fixes the IRI netcdf calendar problem
                    ds = xr.open_dataset(obsFile, decode_times=False)
                except:
                    self.progress.emit(("File cannot be read. please check if the file is properly formatted", "ERROR"))
                    return

                #aligning coordinate names    
                if "T" in ds.coords.keys():
                    self.progress.emit(("found T - renaming to time","RUNTIME"))
                    ds=ds.rename({"T":"time"})
                if "X" in ds.coords.keys():
                    self.progress.emit(("found X - renaming to longitude","RUNTIME"))
                    ds=ds.rename({"X":"longitude"})
                if "Y" in ds.coords.keys():
                    self.progress.emit(("found Y - renaming to longitude","RUNTIME"))
                    ds=ds.rename({"Y":"latitude"})        
                if "lon" in ds.coords.keys():
                    self.progress.emit(("found lon - renaming to logitude","RUNTIME"))
                    ds=ds.rename({"lon":"longitude"})
                if "lat" in ds.coords.keys():
                    self.progress.emit(("found lat - renaming to latitude","RUNTIME"))
                    ds=ds.rename({"lat":"latitude"})

                if ds["time"].attrs['calendar'] == '360':
                    ds["time"].attrs['calendar'] = '360_day'
                ds = xr.decode_cf(ds)
                ds=ds.convert_calendar("standard", align_on="date")


                #exctracting obsVar dataArray
                obs=ds[obsVar]

                #testing if variable has all required dimensions
                test=[x not in obs.coords.keys() for x in ["latitude","longitude","time"]]
                if np.sum(test)>0:
                    self.progress.emit(("Observed variable should have time,latitude and longitude coordinates. This is not the case. Please check if {} file is properly formatted and if {} variable of that file the one that describes forecast".format(obsFile,obsVar), "ERROR"))
                    return    

                #processing obs data further
                obs=obs.rio.write_crs("epsg:4326") #adding crs

                if "units" in obs.attrs:
                    obsunits=obs.attrs["units"]
                    self.progress.emit(("Found units: {}".format(obsunits),"RUNTIME"))
                else:
                    self.progress.emit(("Observed data does not have units attribute. Setting that attribute to default (mm/month). If that is a problem - please add units attribute to the netcdf file using nco or similar software", "NONCRITICAL"))
                    obsunits="mm"
                    
                firstdate=obs.time.values[0]
                lastdate=obs.time.values[-1]
                
                self.progress.emit(("Observed file covers period of: {} to {}".format(firstdate,lastdate),"RUNTIME"))
                
                self.progress.emit(("Successfuly read observations from {}".format(obsFile), "INFO"))
                
            else:
                ds=pd.read_csv(obsFile)
                #for the time being only CFT format
                #ID,Lat,Lon,Year,Jan...Dec
                if "ID" in ds.keys():
                    locs=np.unique(ds.ID)
                    alldata=[]
                    lats=[]
                    lons=[]
                    for name in locs:
                        sel=ds.ID==name
                        lats=lats+[np.unique(ds[sel].Lat.values)[0]]
                        lons=lons+[np.unique(ds[sel].Lon.values)[0]]
                        years=np.unique(ds[sel].Year.values)
                        firstyear,lastyear=(np.min(years),np.max(years))
                        data=ds[sel].iloc[:,4:].values.flatten()
                        data=pd.DataFrame(data.reshape(-1,1), index=pd.date_range("{}-01-01".format(firstyear),"{}-12-31".format(lastyear),freq="M"),columns=[name])
                        alldata=alldata+[data]
                    #obs is pandas dataframe
                    obspd=pd.concat(alldata, axis=1)
                    
                    #creating geodataframe with all data
                    obsgpd=gpd.GeoDataFrame(obspd.T.reset_index(), geometry=gpd.points_from_xy(lons, lats), crs="EPSG:4326")

                    firstdate=obspd.index.values[0]
                    lastdate=obspd.index.values[-1]
                    self.progress.emit(("Observed file covers period of: {} to {}".format(firstdate,lastdate),"INFO"))
                    
                else:
                    self.progress.emit(("File should be in CFT format. This does not seem to be the case. Please check if {} file is properly formatted".format(obsFile), "ERROR"))                    
                    return
                cont=True

                self.progress.emit(("Successfuly read observations from {}".format(obsFile), "INFO"))
                self.progress.emit(("Observed data does not have units attribute. Setting that attribute to unknown.", "NONCRITICAL"))
                obsunits="mm/month"
            #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< this is where code is different for csv and netcdf formats


            
            #-------------------------------------------------------------------------------------------------
            #reading summary zones
            
            self.progress.emit(('\nReading summary zones file...',"RUNTIME"))
            self.progress.emit((str(summaryzonesFile),"RUNTIME"))

            #reading zones geojson file
            try:
                summaryzonesVector = gpd.read_file(summaryzonesFile)
            except:
                self.progress.emit(("Summary zones file {} cannot be read. please check if the file is properly formatted".format(summaryzonesFile), "ERROR"))
                return
            self.progress.emit(("Successfuly read zones from {}".format(summaryzonesFile), "INFO"))

            #this will be an array of id and values from the zonesVar column 
            #not sure what will happen if there are multiple features with the same ID and zonesVar column...
            summaryzonesName=summaryzonesVector[summaryzonesVar].copy()

                
            #-------------------------------------------------------------------------------------------------
            # preprocessing
            
            self.progress.emit(("\nPreprocessing...","RUNTIME"))

            #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            #this is where code is different for csv and netcdf formats
            if obsFileFormat=="netcdf":            
                self.progress.emit(("Clipping observations to forecast extent...","RUNTIME"))
                try:
                    obs=obs.rio.clip(fcstVector.geometry.values, "epsg:4326") #clipping to fcst geojson
                except:
                    self.progress.emit(("Variable {} in the observed file {} appears not to have spatial coordinates. Did you chose correct variable to process?".format(obsVar, obsFile), "ERROR"))
                    return

                #chunking obs, in case it is a large file
                obs=obs.chunk("auto")

                #this filters observations, and it's OK for rainfall, but if it ever is used for a different variable - then this needs to be changed
                obs=obs.where(obs>=0)

            else:
                    cont=True

                    self.progress.emit(("Clipping observations (csv) to forecast extent","RUNTIME"))
                
#                try:
                    #overlaying to select only ovelapping points

                    fcstPoint=obsgpd.overlay(fcstVector, how="intersection")
                    #extracting pandas dataframe
                    obspd_valid=fcstPoint.drop(columns=fcstVector.columns).drop(columns="index").T
                    
                    #fixing column names and index
                    obspd_valid.columns=fcstPoint['index']
                    obspd_valid.index=pd.to_datetime(obspd_valid.index)
                    
                    #removing actual data from geopandas array
                    fcstPoint.index=fcstPoint['index']
                    fcstPoint=fcstPoint[fcstVector.columns]
                    #checking number of valid
                    nofvalid=obspd_valid.shape[0]
                    nofall=obspd.shape[0]
                    self.progress.emit(("Read observations for {} locations".format(nofall), "INFO"))
                    if nofall>nofvalid:
                        self.progress.emit(("Only {} locations fall within polygons of the forecast data. Remaining locations have been dropped".format(nofvalid), "NONCRITICAL"))
                    
                    #converting to xarray with time and geometry dimensions
                    obs=xr.DataArray(obspd_valid)
                    obs=obs.rename({"dim_0":"time","index":"geometry"})
                    
                    #making sure no negative values
                    obs=obs.where(obs>=0)
                    
#                except:
#                    self.progress.emit(("Something went wrong with processing {} {}".format(obsVar, obsFile), "ERROR"))
#                    return
            #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

            #creating ds to store output layers for writing to disk
            outputds=xr.Dataset()
            

            
            #-------------------------------------------------------------------------------------------------           
            # compute observed season's rainfall 
            
            #this has to be done first, because season time expression is needed to convert forecast vector to gridded/station format
            self.progress.emit(('\nComputing observed rainfall for target season...',"RUNTIME"))

            #there is no need to differentiate between gridded and stations here!
            seasDuration,seasLastMon=seasonParam[seas]

            # compute season totals for current year
            if config.get('verifAggregation') == "sum":
                obsroll = obs.rolling(time=seasDuration, center=False).sum()
            else:
                obsroll = obs.rolling(time=seasDuration, center=False).mean()

            seltime=str(obsYear)+"-"+months[seasLastMon-1]

            try:
                obs_season=obsroll.sel(time=seltime)
            except:
                self.progress.emit(("Observed data does not cover {}. Please check your data, or adjust verification period so that it falls within the period covered by observed data.".format(seltime), "ERROR"))
                return

            obs_season.attrs=""
            
            #saving into output dataset
            outputds["obs_value"]=obs_season
            
            
            #-------------------------------------------------------------------------------------------------           
            # plotting observed rainfall
            
            self.progress.emit(('Plotting (always!)',"RUNTIME"))
            
            pars=get_plotparams(obs_season,"obs_season",currentoutDir,obsSeason,obsYear,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)
            
            
            temp=obs_season.copy()
            #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            if obsFileFormat=="netcdf":            
                cont=True
            else:
                temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
            #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
            
            self.plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                 pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)



            
            #-------------------------------------------------------------------------------------------------
            # creating forecast CEM categories map
            
            self.progress.emit(('\nCreating forecast CEM categories map...',"RUNTIME"))

            #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            #this is where code is different for csv and netcdf formats
            if obsFileFormat=="netcdf":
                self.progress.emit(('Rasterizing forecast vector file...',"RUNTIME"))
                
                fcst_ds = make_geocube(vector_data=fcstVector, like=obs) #gridding/rasterizing forecast
                fcst_cemcat=fcst_ds[fcstVar]
                fcsttime=obs_season.time.data
                #this gives the gridded forecast file the same time dimension as observations
                fcst_cemcat=fcst_cemcat.expand_dims(time=fcsttime)

                if "x" in fcst_cemcat.coords.keys():
                    self.progress.emit(("found x - renaming to longitude","RUNTIME"))
                    fcst_cemcat=fcst_cemcat.rename({"x":"longitude"})
                if "y" in fcst_cemcat.coords.keys():
                    self.progress.emit(("found y - renaming to latitude","RUNTIME"))
                    fcst_cemcat=fcst_cemcat.rename({"y":"latitude"})


                #need to reassign coordinates due to float rounding issues during rasterization
                fcst_cemcat=fcst_cemcat.assign_coords(latitude=obs.latitude.data)
                fcst_cemcat=fcst_cemcat.assign_coords(longitude=obs.longitude.data)
                
                fcst_cemcat.attrs=""

            else:
                cont=True
                self.progress.emit(('Converting forecast vector to xarray with data for station locations...',"RUNTIME"))
                
                fcst_cemcat=xr.DataArray(fcstPoint[fcstVar]).rename({"index":"geometry"})
                fcsttime=obs_season.time.data
                fcst_cemcat = fcst_cemcat.expand_dims(time=fcsttime)
                
            #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
            
            fcst_cemcat.attrs=""   
            outputds["fcst_cemcat"] = fcst_cemcat

            
            #-------------------------------------------------------------------------------------------------
            # plotting forecast CEM categories map
                    
            self.progress.emit(('Plotting (always!)',"RUNTIME"))
            
            pars=get_plotparams(fcst_cemcat,"fcst_cemcat",currentoutDir,obsSeason,obsYear,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)
            
            temp=fcst_cemcat.copy()
            #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            if obsFileFormat=="netcdf":            
                cont=True
            else:
                temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
            #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
            
            self.plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                 pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)
            
            
                    
            #-------------------------------------------------------------------------------------------------
            # calculating climatology
            
            self.progress.emit(("\nCalculating observed climatological mean...","RUNTIME"))
            
            #climatology period
            obs_clim=obsroll.sel(time=obsroll.time.dt.month==seasLastMon).sel(time=slice(str(climStartYr),str(climEndYr)))
            
            #climatological mean
            clim_mean = obs_clim.mean("time")

            clim_mean.attrs=""   
            outputds["obs_clim"]=clim_mean

            
            #-------------------------------------------------------------------------------------------------
            # plotting climatology

            self.progress.emit(("Plotting (always!)","RUNTIME"))

            #add obsunits to plotconfig
            #obsunits="mm/day"
            pars=get_plotparams(clim_mean,"clim_mean",currentoutDir,obsSeason,obsYear,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)
#            pars["cbar_label"]=obsunits
            
            temp=clim_mean.copy()
            #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            if obsFileFormat=="netcdf":            
                cont=True
            else:
                temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
            #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
            
            self.plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                 pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)
            
                

            
            #-------------------------------------------------------------------------------------------------            
            #calculating quantiles
            
            self.progress.emit(("\nCalculating observed quantiles...","RUNTIME"))
            
            clim_quant=obs_clim.quantile([0.33,0.50,0.66], dim="time")


            
            #-------------------------------------------------------------------------------------------------            
            #calculating relative anomaly
                            
            if outputObsrelanom:
                
                self.progress.emit(("\nCalculating relative anomaly...","RUNTIME"))

                obs_relanom=(obs_season-clim_mean)/clim_mean*100
                
                self.progress.emit(("Plotting","RUNTIME"))
                pars=get_plotparams(obs_relanom,"obs_relanom",currentoutDir,obsSeason,obsYear,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)
                
                temp=obs_relanom.copy()
                #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                if obsFileFormat=="netcdf":            
                    cont=True
                else:
                    temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                    temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
                #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

                self.plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                     pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)

                    
                obs_relanom.attrs=""   
                outputds["obs_relanom"]=obs_relanom
            else:
                self.progress.emit(("\nSkipping relative anomaly","RUNTIME"))


                
            #-------------------------------------------------------------------------------------------------
            #calculating terciles
            
            self.progress.emit(("\nCalculating observed terciles...","RUNTIME"))
            
            temp=xr.apply_ufunc(
                val_to_terc,
                obs_season.load(),
                obs_clim.rename({"time":"times"}).load(),
                input_core_dims=[["time"],["times"]],
                output_core_dims=[["time"]],
                vectorize=True
            )
            
            #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            if obsFileFormat=="netcdf":
                obs_terc=temp.transpose("time","latitude","longitude")
            else:
                obs_terc=temp.transpose("time","geometry")
            #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

                
                
                
            #-------------------------------------------------------------------------------------------------
            #calculating forecast tercileprobability
            
            self.progress.emit(("\nConverting CEM categories to tercile probabilities...","RUNTIME"))
            
            temp=xr.apply_ufunc(
                cemcat_to_tercprob, 
                fcst_cemcat,
                input_core_dims=[["time"]],
                output_core_dims=[["time","tercile"]],
                vectorize=True
            )

            #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            if obsFileFormat=="netcdf":            
                fcst_tercprob=temp.transpose("time","tercile","latitude","longitude").assign_coords(
                    {"tercile":["BN","N","AN"]})
                fcst_tercprob.name="tercprob"
            else:
                cont=True
                fcst_tercprob=temp.transpose("time","tercile","geometry").assign_coords(
                    {"tercile":["BN","N","AN"]})
                fcst_tercprob.name="tercprob"
            #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<


            

                
            #-------------------------------------------------------------------------------------------------
            #calculating and plotting obs cemcategories
            
            if outputObscemcat:
                self.progress.emit(("\nCalculating observed CEM categories...","RUNTIME"))

                temp=xr.apply_ufunc(
                    val_to_cemcat,
                    obs_season.load(),
                    obs_clim.rename({"time":"times"}).load(),
                    input_core_dims=[["time"],["times"]],
                    output_core_dims=[["time"]],
                    vectorize=True
                )

                #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                if obsFileFormat=="netcdf":
                    obs_cemcat=temp.transpose("time","latitude","longitude")
                    obs_cemcat.name="cemcat"
                else:
                    cont=True
                    obs_cemcat=temp.transpose("time","geometry")
                    obs_cemcat.name="cemcat"
                #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
                    
                    
                self.progress.emit(("Plotting","RUNTIME"))
                pars=get_plotparams(obs_cemcat,"obs_cemcat",currentoutDir,obsSeason,obsYear,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)

                temp=obs_cemcat.copy()
                #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                if obsFileFormat=="netcdf":            
                    cont=True
                else:
                    temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                    temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
                #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

                self.plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                     pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)
                                    
                obs_cemcat.attrs=""   
                outputds["obs_class"]=obs_cemcat

            else:
                self.progress.emit(("\nSkipping observed CEM categories","RUNTIME"))


                
            #-------------------------------------------------------------------------------------------------
            #calculating quantile anomaly

            if outputQuantanom:
                self.progress.emit(("\nCalculating quantile anomalies...","RUNTIME"))
                temp=xr.apply_ufunc(
                    val_to_quantanom,
                    obs_season.load(),
                    obs_clim.rename({"time":"times"}).load(),
                    input_core_dims=[["time"],["times"]],
                    output_core_dims=[["time"]],
                    vectorize=True
                )
                #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                if obsFileFormat=="netcdf":
                    obs_quantanom=temp.transpose("time","latitude","longitude")
                    obs_quantanom.name="quantanom"
                    
                else:
                    cont=True
                    obs_quantanom=temp.transpose("time","geometry")
                    obs_quantanom.name="quantanom"
                #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
                
                self.progress.emit(("Plotting","RUNTIME"))
                
                pars=get_plotparams(obs_quantanom,"obs_quantanom",currentoutDir,obsSeason,obsYear,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)

                temp=obs_quantanom.copy()*100
                
                #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                if obsFileFormat=="netcdf":            
                    cont=True
                else:
                    temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                    temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
                #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
                                
                self.plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                     pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)
                
                    
                obs_quantanom.attrs=""   
                outputds["obs_quantanom"]=obs_quantanom

            else:
                self.progress.emit(("\nSkipping quantile anomalies","RUNTIME"))



            #-------------------------------------------------------------------------------------------------
            #calculating heidke hits
            
            if outputHeidke:
                self.progress.emit(("\nCalclating Heidke hit scores...","RUNTIME"))
                fcst_hhit=None
                zonal_hhit=None
                
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
                    
                    #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                    if obsFileFormat=="netcdf":
                        fcst_hhit=temp.transpose("time","latitude","longitude")
                        fcst_hhit.name="hhit"
                    else:
                        fcst_hhit=temp.transpose("time","geometry")
                        fcst_hhit.name="hhit"
                    #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
                        
                    fcst_hhit.attrs=""
                    outputds["fcst_heidke"]=fcst_hhit

                    self.progress.emit(("Plotting","RUNTIME"))
                    pars=get_plotparams(fcst_hhit,"fcst_hhit",currentoutDir,obsSeason,obsYear,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)

                    
                    temp=fcst_hhit.copy()
                    #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                    if obsFileFormat=="netcdf":            
                        cont=True
                    else:
                        temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                        temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
                    #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

                    self.plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                         pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)
                    
                    
                    #CHECK
                    self.progress.emit(("Plotting Heidke hit scores zonal summary","RUNTIME"))
                    zonal_hhit=zonal_mean(temp,summaryzonesVector,summaryzonesName,summaryzonesVar,obsFileFormat)
                    self.plotzonalHistogram(zonal_hhit["mean"], 
                                             "Heidke skill score (most probable category)", 
                                             "{}/{}_{}_{}-{}_{}.jpg".format(currentoutDir, "zonal_heidke",fcstVar,obsSeason,obsYear,obsDsetCode),
                                             "HHS [-]", 
                                             0,
                                             1,
                                             "no-skill forecast=0, perfect forecast=1",
                                             summaryzonesVector,
                                             summaryzonesName,
                                             summaryzonesVar
                                               )                        
                except Exception as e: 
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    errortxt="ERROR: {} {}\nin line:{}".format(e,exc_type, exc_tb.tb_lineno)
                    self.progress.emit(("\nNot able to calculate Heidke hits \n{}\n".format(errortxt),"NONCRITICAL"))

            else:
                self.progress.emit(("\nSkipping Heidke hit scores","RUNTIME"))


                
                
            #-------------------------------------------------------------------------------------------------
            #interest rate

            if outputIntrate:
                self.progress.emit(("\nCalculating interest rate...","RUNTIME"))
                fcst_intrate=None
                zonal_intrate=None
                
                try:
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

                    #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                    if obsFileFormat=="netcdf":
                        fcst_intrate=temp.transpose("time","latitude","longitude")
                    else:
                        fcst_intrate=temp.transpose("time","geometry")
                    #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
                    fcst_intrate.name="intrate"
                        
                                            
                    self.progress.emit(("Plotting","RUNTIME"))
                    pars=get_plotparams(fcst_intrate,"fcst_intrate",currentoutDir,obsSeason,obsYear,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)

                    intratemax=max(abs(fcst_intrate.min().data), abs(fcst_intrate.max().data))*2

                    
                    temp=fcst_intrate.copy()
                    #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                    if obsFileFormat=="netcdf":            
                        cont=True
                    else:
                        temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                        temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
                    #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

                    self.plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                         pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)
    
                    fcst_intrate.attrs=""
                    outputds["fcst_intrate"]=fcst_intrate

                    self.progress.emit(("Plotting interest rate zonal summary","RUNTIME"))
                    zonal_intrate=zonal_mean(temp,summaryzonesVector,summaryzonesName,summaryzonesVar,obsFileFormat)
                    self.plotzonalHistogram(zonal_intrate["mean"], 
                            "Average interest rate", 
                            "{}/{}_{}_{}_{}_{}.jpg".format(currentoutDir, "zonal_intrate",fcstVar,obsSeason,obsYear,obsDsetCode),
                            "interest rate [%]",
                            0,
                            100,
                            "climatological forecast=0%, perfect forecast = 100%",
                            summaryzonesVector,
                            summaryzonesName,
                            summaryzonesVar
                            )
                except Exception as e: 
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    errortxt="ERROR: {} {}\nin line:{}".format(e,exc_type, exc_tb.tb_lineno)
                    self.progress.emit(("\nNot able to calculate igterest rate \n{}\n".format(errortxt),"NONCRITICAL"))
                        
                    
            else:
                self.progress.emit(("\nSkipping interest rate","RUNTIME"))




            #-------------------------------------------------------------------------------------------------
            #ignorance
            
            
            if outputIgnorance:
                self.progress.emit(("\nCalculating ignorance score...","RUNTIME"))
                fcst_ignorance=None
                zonal_ignorance=None
                
                try:
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
                    #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                    if obsFileFormat=="netcdf":
                        fcst_ignorance=temp.transpose("time","latitude","longitude")
                        fcst_ignorance.name="ignorance"
                    else:
                        fcst_ignorance=temp.transpose("time","geometry")
                        fcst_ignorance.name="ignorance"
                    #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
                        
                    ignorancemax=max(abs(fcst_ignorance.min().data), abs(fcst_ignorance.max().data))*2

                    self.progress.emit(("Plotting","RUNTIME"))
                    pars=get_plotparams(fcst_ignorance,"fcst_ignorance",currentoutDir,obsSeason,obsYear,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)
#                    pars["vmax"]=ignorancemax

                    temp=fcst_ignorance.copy()
                    #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                    if obsFileFormat=="netcdf":            
                        cont=True
                    else:
                        temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                        temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
                    #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

                    self.plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                         pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)


                    fcst_ignorance.attrs=""        
                    outputds["fcst_ignorance"]=fcst_ignorance

                    self.progress.emit(("Plotting ignorance zonal summary","RUNTIME"))
                    
                    zonal_ignorance=zonal_mean(temp,summaryzonesVector,summaryzonesName,summaryzonesVar,obsFileFormat)
                    self.plotzonalHistogram(zonal_ignorance["mean"], 
                                         "Ignorance score", 
                                         "{}/{}_{}_{}-{}_{}.jpg".format(currentoutDir, "zonal_ignorance",fcstVar,obsSeason,obsYear,obsDsetCode),
                                         "Ignorance [-]", 
                                         1.58,
                                            0,
                                         "climatological forecast=1,58, perfect forecast=0 (lower values better)",
                                         summaryzonesVector,
                                         summaryzonesName,
                                         summaryzonesVar
                                           )
                    
                except Exception as e: 
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    errortxt="ERROR: {} {}\nin line:{}".format(e,exc_type, exc_tb.tb_lineno)
                    self.progress.emit(("\nNot able to calculate ignorance score \n{}\n".format(errortxt),"NONCRITICAL"))
                                        
                    
            else:
                self.progress.emit(("\nSkipping ignorance score","RUNTIME"))

                
                
            #-------------------------------------------------------------------------------------------------
            #calculating rpss
            
            if outputRpss:
                self.progress.emit(("\nCalcuating RPSS score...","RUNTIME"))
                fcst_rpss=None
                zonal_rpss=None
                
                try:
                    temp=xr.apply_ufunc(
                        get_rpss,
                        fcst_cemcat,
                        obs_cemcat,
                        input_core_dims=[["time"],["time"]],
                        output_core_dims=[["time"]],
                        vectorize=True
                    )
                    #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                    if obsFileFormat=="netcdf":
                        fcst_rpss=temp.transpose("time","latitude","longitude")
                        fcst_rpss.name="rpss"
                    else:
                        fcst_rpss=temp.transpose("time","geometry")
                        fcst_rpss.name="rpss"
                    #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
                        
                    self.progress.emit(("Plotting","RUNTIME"))
                    pars=get_plotparams(fcst_rpss,"fcst_rpss",currentoutDir,obsSeason,obsYear,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)

                    
                    temp=fcst_rpss.copy()
                    #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                    if obsFileFormat=="netcdf":            
                        cont=True
                    else:
                        temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                        temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
                    #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

                    
                    self.plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                         pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)
                    fcst_rpss.attrs=""                
                    outputds["fcst_rpss"]=fcst_rpss


                    self.progress.emit(("Plotting RPSS zonal summary","RUNTIME"))
                    
                    zonal_rpss=zonal_mean(temp,summaryzonesVector,summaryzonesName,summaryzonesVar,obsFileFormat)
                    
                    self.plotzonalHistogram(zonal_rpss["mean"],
                                     "RPSS",
                                     "{}/{}_{}_{}-{}_{}.jpg".format(currentoutDir, "zonal_rpss",fcstVar,obsSeason,obsYear,obsDsetCode),"[-]", 
                                     0,
                                     1,
                                     "climatological forecast=0 perfect forecast=1",
                                     summaryzonesVector,
                                     summaryzonesName,
                                     summaryzonesVar)
                    
                except Exception as e: 
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    errortxt="ERROR: {} {}\nin line:{}".format(e,exc_type, exc_tb.tb_lineno)
                    self.progress.emit(("\nNot able to calculate rpss score \n{}\n".format(errortxt),"NONCRITICAL"))

            else:
                self.progress.emit(("\nSkipping RPSS score","RUNTIME"))





            #-------------------------------------------------------------------------------------------------
            #cem hits
            
            if outputCemhit:
                self.progress.emit(("\nCalculating CEM hit scores...","RUNTIME"))
                fcst_cemhit=None
                zonal_cemhit=None
                
                try:
                    temp=xr.apply_ufunc(
                        get_cem_hit,
                        fcst_cemcat,
                        obs_cemcat,
                        input_core_dims=[["time"],["time"]],
                        output_core_dims=[["time"]],
                        vectorize=True
                    )
                    #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                    if obsFileFormat=="netcdf":
                        fcst_cemhit=temp.transpose("time","latitude","longitude")
                        fcst_cemhit.name="cemhit"
                        fcst_cemhit=fcst_cemhit.rio.write_crs("epsg:4326")
                    else:
                        fcst_cemhit=temp.transpose("time","geometry")
                        fcst_cemhit.name="cemhit"
                    #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
                        

                    self.progress.emit(("Plotting","RUNTIME"))
                    pars=get_plotparams(fcst_cemhit,"fcst_cemhit",currentoutDir,obsSeason,obsYear,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)

                    temp=fcst_cemhit.copy()
                    #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                    if obsFileFormat=="netcdf":            
                        cont=True
                    else:
                        temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                        temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
                    #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
            
                    self.plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                         pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)
                        
                    fcst_cemhit.attrs=""
                    outputds["fcst_classhit"]=fcst_cemhit

                    filename="{}/histogram_cemhitmiss_{}_{}.jpg".format(currentoutDir, fcstCode, obsDsetCode)
                    title="hits/misses in zones \n{} forecast vs. {}-{} observations ({})".format(fcstVar,obsSeason,obsYear,obsDsetCode)
                    
                    self.plotzonalCemhit(summaryzonesVector,summaryzonesName,summaryzonesVar,temp,filename,title,obsFileFormat)
                                        
                        
                except Exception as e: 
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    errortxt="ERROR: {} {}\nin line:{}".format(e,exc_type, exc_tb.tb_lineno)
                    self.progress.emit(("\nNot able to calculate cem hit/miss rate \n{}\n".format(errortxt),"NONCRITICAL"))
                    
            else:
                self.progress.emit(("\nSkipping CEM hit scores","RUNTIME"))



            #-------------------------------------------------------------------------------------------------
            #writing output file
            
            self.progress.emit(("\nWriting output file...","RUNTIME"))
            
            #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            if obsFileFormat=="netcdf":            
                outputfile="{}/maps_verification_{}_{}-{}_{}.nc".format(currentoutDir,fcstVar,obsSeason,obsYear,obsDsetCode)        
                outputds.to_netcdf(outputfile)    
                self.progress.emit(("Created {}".format(outputfile), "INFO"))
            else:
                cont=True
            #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
            

            #CHECK
            self.progress.emit(("\nPreparing zonal summaries...","RUNTIME"))

            summarylabels=[]
            summarydata=[]
            if outputIntrate and (fcst_intrate is not None):
               summarylabels=summarylabels+["average interest rate"]
               summarydata=summarydata+[fcst_intrate.mean().data]
            if outputHeidke and (fcst_hhit is not None):
               summarylabels=summarylabels+["Heidke skill score"]
               summarydata=summarydata+[fcst_hhit.mean().data]
            if outputRpss and (fcst_rpss is not None ):
               summarylabels=summarylabels+["RPSS"]
               summarydata=summarydata+[fcst_rpss.mean().data]
            if outputIgnorance and (fcst_ignorance is not None):
               summarylabels=summarylabels+["Ignorance skill score"]
               summarydata=summarydata+[fcst_ignorance.mean().data]

            self.progress.emit(('\nFinished running verification. Check output directory {} for output'.format(currentoutDir), "SUCCESS"))
            self.finished.emit()
                
                
            

    def plotMap(self,_data,_cmap,_levels,_vmin,_vmax, _title, _cbar_label,_ticklabels, _mask, _filename,_annotation,_geometryfile, _geometryVar,_obsFileFormat="netcdf"):
        
        regannotate=True
        
        regions = gpd.read_file(_geometryfile)
        
        
        if _obsFileFormat=="netcdf":
            fig=plt.figure(figsize=(5,4))
            pl=fig.add_subplot(1,1,1, projection=ccrs.PlateCarree())
            if _mask is not None:
                _sign,_val=_mask
                if _sign=="above":
                    _data=_data.where(_data<_val)
                else:
                    _data=_data.where(_data>_val)
            m=_data.plot(cmap=_cmap, vmin=_vmin,vmax=_vmax, add_colorbar=False)

            mm=regions.boundary.plot(ax=pl, linewidth=1, color="0.1")
            if regannotate:
                regions["labelcoords"]=regions['geometry'].apply(lambda x: x.representative_point().coords[:])
                for idx, row in regions.iterrows():
                    mm.annotate(text=row[_geometryVar][:3], xy=row['labelcoords'][0],
                                 horizontalalignment='center', zorder=10000)
    
            plt.title(_title, fontsize=10)
            pl.text(0,-0.03,_annotation,fontsize=6, transform=pl.transAxes)
            ax=fig.add_axes([0.82,0.25,0.02,0.5])
            if _levels is None:
                cbar = fig.colorbar(m, cax=ax, label=_cbar_label)
            else:
                cbar = fig.colorbar(m, cax=ax,ticks=_levels, label=_cbar_label)
            if _ticklabels is not None:
                cbar.ax.set_yticklabels(_ticklabels)
            plt.subplots_adjust(bottom=0.05,top=0.9,right=0.8,left=0.05)
            plt.savefig(_filename, dpi=300)
            self.progress.emit(("Created {}".format(_filename), "INFO"))
            plt.close()

        else:
            fig=plt.figure(figsize=(5,4))
            pl=fig.add_subplot(1,1,1, projection=ccrs.PlateCarree())
            if _mask is not None:
                _sign,_val=_mask
                if _sign=="above":
                    _data=_data.where(_data[0]<_val)
                else:
                    _data=_data.where(_data[0]>_val)
            m=_data.plot(0, 
                         cmap=_cmap, 
                         vmin=_vmin,
                         vmax=_vmax, 
                         legend=False,
                         edgecolors="0.7",
                         linewidths=0.3,
                         alpha=0.9,
                         ax=pl,
                        zorder=10)
            
            regions.boundary.plot(ax=pl, linewidth=0.5, color="0.1", zorder=1000)            
            if regannotate:
                regions["labelcoords"]=regions['geometry'].apply(lambda x: x.representative_point().coords[:])
                for idx, row in regions.iterrows():
                    m.annotate(text=row[_geometryVar][:3], xy=row['labelcoords'][0],
                                 horizontalalignment='center', zorder=10000, fontsize=5)
            
            plt.title(_title, fontsize=10)
            pl.text(0,-0.03,_annotation,fontsize=6, transform=pl.transAxes)
            ax=fig.add_axes([0.82,0.25,0.02,0.5])
            sm = plt.cm.ScalarMappable(cmap=_cmap, norm=plt.Normalize(vmin=_vmin, vmax=_vmax))
            # fake up the array of the scalar mappable. Urgh...
            sm._A = []
            if _levels is None:
                cbar = fig.colorbar(sm, cax=ax, label=_cbar_label)
            else:
                cbar = fig.colorbar(sm, cax=ax,ticks=_levels, label=_cbar_label)
            if _ticklabels is not None:
                cbar.ax.set_yticklabels(_ticklabels)
            plt.subplots_adjust(bottom=0.05,top=0.9,right=0.8,left=0.05)
            plt.savefig(_filename, dpi=300)
            self.progress.emit(("Created {}".format(_filename), "INFO"))
            plt.close()
        
    def plotzonalHistogram(self, _data, _title, _filename, _ylabel, _hline1, _hline2, _annotation,_summaryzonesVector,_summaryzonesName,_summaryzonesVar):
        
        fig=plt.figure(figsize=(6,3))
        pl=fig.add_subplot(1,1,1)
        plt.title(_title, fontsize=10)

        _data.plot.bar()

        pl.axhline(_hline1, linestyle="--",color="0.7")
        pl.axhline(_hline2, linestyle="--",color="0.7")
        pl.text(0.1,0.97,_annotation,fontsize=6, transform=pl.transAxes)
#        pl.text(0.02,0.98,_text, ha='left', va='top', transform=pl.transAxes)
        pl.set_xlabel("zone")
        pl.set_ylabel(_ylabel)
        yrange=np.abs(_hline1-_hline2)

        ymin=np.min([-0.05*yrange, np.nanmin(_data)])
        pl.set_ylim(ymin,None)
        pl.set_xticklabels([x[:3] for x in _summaryzonesName])
        
        
        #plotting small inlay with regions map
        ax2=fig.add_axes([0.79,0.3,0.2,0.4],projection=ccrs.PlateCarree())
        
        regions=_summaryzonesVector.copy()
        m=regions.boundary.plot(ax=ax2, linewidth=0.5, color="0.7", zorder=1000)
        
        regions["labelcoords"]=regions['geometry'].apply(lambda x: x.representative_point().coords[:])
        for idx, row in regions.iterrows():
            m.annotate(text=row[_summaryzonesVar][:3], xy=row['labelcoords'][0],
                         horizontalalignment='center', zorder=10000, fontsize=5, color="0.5")
    
        ax2.spines['geo'].set_edgecolor('0.7')
        
        plt.subplots_adjust(bottom=0.15,top=0.9, right=0.75,left=0.15)
        plt.savefig(_filename, dpi=300)
        self.progress.emit(("Created {}".format(_filename), "INFO"))
        plt.close()
        
        
        
        
    def plotzonalCemhit(self,summaryzonesVector,summaryzonesName,summaryzonesVar,fcst_cemhit,filename,title,obsFileFormat):
        self.progress.emit(("Creating hit/miss graph for zones","RUNTIME"))
        nzones=len(summaryzonesVector)
        
        alldata=[]
        if obsFileFormat=="netcdf":
            for i,geom in enumerate(summaryzonesVector.geometry):
                try:
                    clipped = fcst_cemhit.rio.clip([geom], "epsg:4326")
                    clipped=clipped.data.flatten()
                except Exception as e:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    errortxt="{} {}\nin line:{}".format(e,exc_type, exc_tb.tb_lineno)
                    self.progress.emit(("\nNot able to calculate cem hit/miss rate \n{}\n".format(errortxt),"NONCRITICAL"))
                    clipped=np.array([])
                alldata=alldata+[clipped[~np.isnan(clipped)]]
        else:
            crossed=fcst_cemhit.overlay(summaryzonesVector, how="intersection")
            for val in summaryzonesName:
                sel=crossed[summaryzonesVar]==val
                clipped=crossed[sel][0]
                alldata=alldata+[clipped[~np.isnan(clipped)]]
            
        bins=[-0.5,0.5,1.5,2.5,3.5]
        labels=["error","half-miss","half-hit","hit"]
        cols=colors.ListedColormap([plt.cm.get_cmap('RdBu', 10)(x) for x in [2,4,5,7]])
        cols=[cols(i) for i in range(4)]

        nx,ny=6,int(np.ceil(nzones/6))
        fx,fy=7,int(np.ceil(nzones/6))+1            

        fig=plt.figure(figsize=(fx,fy))
        for i,zdata in enumerate(alldata):
            pl=fig.add_subplot(ny,nx,i+1)   
            if len(zdata)>0:
                vals,b=np.histogram(zdata, bins=bins, normed=True)
                pie=pl.pie(vals, colors=cols)
            else:
                pl.pie([1], colors=["white"])
                pl.text(0.5,0.5,"no data", ha='center', va='center', transform=pl.transAxes, color="0.8")
            pl.set_title("{}".format(summaryzonesName[i][0:3]))
            
        #positioning the legend
        fig.legend(labels, loc="lower right", bbox_to_anchor=(1,0))
        
        #plotting small inlay with regions
        ax2=fig.add_axes([0.8,0.59,0.2,0.4],projection=ccrs.PlateCarree())
#        ax2=fig.add_axes([0.8,0.59,0.2,0.4])
        
        regions=summaryzonesVector.copy()
        m=regions.boundary.plot(ax=ax2, linewidth=0.5, color="0.7", zorder=1000)
        
        regions["labelcoords"]=regions['geometry'].apply(lambda x: x.representative_point().coords[:])
        for idx, row in regions.iterrows():
            m.annotate(text=row[summaryzonesVar][:3], xy=row['labelcoords'][0],
                         horizontalalignment='center', zorder=10000, fontsize=5, color="0.5")
    
        ax2.spines['geo'].set_edgecolor('0.7')
        
        
        plt.suptitle(title, fontsize=10)
        plt.subplots_adjust(bottom=0.05,top=0.75,right=0.7,left=0.05)
        plt.savefig(filename, dpi=300)

        self.progress.emit(("Created {}".format(filename), "INFO"))
        
    
        
    def updateConfig(self):

        global settingsfile
        global config

        #this updates config entries for arguments other than file selectors!!!
        #filepath elements are populated when user selects the file
        #this function does validity checks on all entries

        if config['obsFile']['file']=="":
            self.progress.emit(("ERROR: observed file has to be selected", "ERROR"))
            return

        obsFile=Path(config.get('obsFile').get('file'))

        if not obsFile.exists():    
            self.progress.emit(("Observed data file {} does not exist".format(obsFile)))
            return

        if config['fcstFile']['file']=="":
            self.progress.emit(("ERROR: forecast file has to be selected", "ERROR"))
            return

        fcstFile =  Path(config.get('fcstFile').get('file'))
        if not fcstFile.exists():
            self.progress.emit(("Forecast file {} does not exist".format(fcstFile), "ERROR"))
            return

        if config['summaryzonesFile']['file']=="":
            self.progress.emit(("ERROR: zones file has to be selected", "ERROR"))
            return

        zonesFile=Path(config.get('summaryzonesFile').get('file'))
        if not zonesFile.exists():    
            self.progress.emit(("Zones file {} does not exist".format(zonesFile), "ERROR"))
            return

        if config['outDir']=="":
            self.progress.emit(("ERROR: output directory has to be set", "ERROR"))
            return

        outDir=Path(config['outDir'])
        if not outDir.exists():
            self.progress.emit(("Output directory {} does not exist".format(outDir), "ERROR"))
            return
        #check if outputdirectory is writeable
        if not os.access(outDir, os.W_OK):
            self.progress.emit(("Output directory {} exists, but you have insufficient rights to write into it".format(outDir), "ERROR"))
            return

        #updating variable selections
        #for obsFile
        config['obsFile']['ID'] = config.get('obsFile').get('variable').index(window.obsFileVariable.currentText())
        #for forecast file
        config['fcstFile']['ID'] = config.get('fcstFile').get('variable').index(window.fcstFileVariable.currentText())
        #for zones file
        config['summaryzonesFile']['ID'] = config.get('summaryzonesFile').get('variable').index(window.summaryzonesFileVariable.currentText())


        #checking and updating text fields
        try:
            config['climStartYear'] = int(window.climStartYear.text())
        except:
            self.progress.emit(("ERROR: start of climatological period has to be an integer value", "ERROR"))
            return

        try:
            config['climEndYear'] = int(window.climEndYear.text())
        except:
            self.progress.emit(("ERROR: end of climatological period has to be an integer value", "ERROR"))
            return

        try:
            config['verifYear'] = int(window.verifYear.text())
        except:
            self.progress.emit(("ERROR: forecast year has to be an integer value", "ERROR"))
            return

        if window.obsDsetCode.text()=="":
            self.progress.emit(("ERROR: Dataset code missing", "ERROR"))
            return        
        else:
            config['obsDsetCode'] = window.obsDsetCode.text()
            

        #updates radio buttons
        if window.obsFileFormatCsv.isChecked():
            config['obsFileFormat']="csv"
        else:
            config['obsFileFormat']="netcdf"

        if window.verifAggregationSum.isChecked():
            config['verifAggregation']="sum"
        else:
            config['verifAggregation']="avg"

        #verification period selector
        config['verifPeriod']['indx'] = config.get('verifPeriod').get('season').index(window.verifPeriod.currentText())

        #updating output selectors
        config['outputQuantanom'] = window.outputQuantanom.isChecked()
        config['outputHeidke'] = window.outputHeidke.isChecked()
        config['outputIgnorance'] = window.outputIgnorance.isChecked()
        config['outputIntrate'] = window.outputIntrate.isChecked()
        config['outputCemhit'] = window.outputCemhit.isChecked()
        config['outputObscemcat'] = window.outputObscemcat.isChecked()
        config['outputObsrelanom'] = window.outputObsrelanom.isChecked()
        config['outputObsvalue'] = window.outputObsvalue.isChecked()
        config['outputRpss'] = window.outputRpss.isChecked()

        # Write configuration to settings file
        with open(settingsfile, 'w') as fp:
            json.dump(config, fp, indent=4)

        return True

    


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
        _message = "<pre><font color={}>{}</font></pre>".format(_color, _message)
        window.logWindow.appendHtml(_message)
    #    window.logWindow.update()
        window.logWindow.ensureCursorVisible()
        if _type=="ERROR":
            self.thread.terminate()
            self.thread.wait()
            window.runButton.setEnabled(True)
            
    
    def threadVerification(self):
        # Step 2: Create a QThread object
        self.thread = QThread()
        # Step 3: Create a worker object
        self.worker = Worker()
        # Step 4: Move worker to the thread
        self.worker.moveToThread(self.thread)
        # Step 5: Connect signals and slots
        self.thread.started.connect(self.worker.execVerification)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.progress.connect(self.reportProgress)
        # Step 6: Start the thread
        self.thread.start()

        # Final resets
        window.runButton.setEnabled(False)
        self.thread.finished.connect(
            lambda: window.runButton.setEnabled(True)
        )


        


# this is where magic happens
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MyApp()
    window.show()
    
    # the process is as follows:
    #1 - load config from json file
    #2 - if that fails, populate config with defaults
    #3 - once config loaded - populate UI with values from config
    #4 - when user presses run button -  update config. This: 
    #    - picks values from UI for everything apart from file paths - these are set separately,
    #    - perform validity checks
    #    - updates config dictonary
    #    - dumps the config dictonary to json file
    #5 - if all that is successful - run the verification
    #6 - verification checks for contents of files rather than for their presence
    showMessage("Loading config...")
    try:
        #this tries to read the config file. 
        with open(settingsfile, "r") as read_file:
            config = json.load(read_file)
        showMessage("Config loaded from {}".format(settingsfile), "INFO")
    except:
        #if reading config file fails, config is created with default variables defined here 
        showMessage("Problem reading from {}. Loading default settings.".format(settingsfile))
        config=setConfigDefaults()
        showMessage("Default settings loaded.", "INFO")
                
    # --- Load values from config file into the UI ---
    populateUI()
    
    # --- verification is run when user has pressed run button, so nothing else to do here...
    sys.exit(app.exec_())


# In[ ]:



# In[ ]:




