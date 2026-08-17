import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import xarray as xr

import matplotlib.pyplot as plt
import matplotlib.colors as colors
import cartopy.crs as ccrs

from geocube.api.core import make_geocube
from rasterstats import zonal_stats

from cft import gl


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


def showMessage(message, msgType="RUNTIME"):
    #this prints messages to the log window; uses gl.window.log() so it is safe to call
    #from any thread (e.g. from execVerification, which runs in a worker thread)
    color=msgColors[msgType]
    message = "<pre><font color={}>{}</font></pre>".format(color, message)
    gl.window.log(message)


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
    mxs=mxs[int(_x[3]-1)]*1/np.sum(mxs)
    return mxs


def cemcat_to_tercprob(_cat):
    _cem_probs=np.array([[40,35,25],[35,40,25],[25,40,35],[25,35,40]])/100
    _probs=np.array([_cem_probs[int(x-1)] if not np.isnan(x) else np.array([np.nan,np.nan,np.nan]) for x in _cat])
    return _probs


def cemcat_to_terc(_cat):
    _tercarray=np.array([1,2,2,3])
    _terc=np.array([_tercarray[int(x-1)] if not np.isnan(x) else np.array([np.nan]) for x in _cat])
    return _terc 


def val_to_cemcat(_val,_obs):
    _out=np.copy(_val)
    _out[:]=np.nan
    if np.sum(np.isnan(_val))==0:
        _q1,_q2,_q3=np.nanquantile(_obs,[0.33,0.5,0.66])
        _out[_val<=_q1]=1
        _out[(_val>_q1) & (_val<=_q2)]=2
        _out[(_val>_q2) & (_val<=_q3)]=3
        _out[_val>_q3]=4
    return(_out)

def val_to_terc(_val,_obs):
    _out=np.copy(_val)
    _out[:]=np.nan
    if np.invert(np.isnan(_val))>0:
        _q1,_q2=np.nanquantile(_obs,[0.33,0.66])
        _out[_val<=_q1]=1
        _out[(_val>_q1) & (_val<=_q2)]=2
        _out[_val>_q2]=3
    return(_out.astype(float))

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
    _temp=np.copy(_f).astype(float)
    _temp[:]=np.nan
    if not np.isnan(_f).any() and not np.isnan(_o).any():
        _temp[:]=0
        _temp[_f==_o]=3 #hit
        _temp[np.abs((_f-_o))==1]=2
        _temp[np.abs((_f-_o))==2]=1
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

    

# helper 

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
            vals=crossed[sel][0]
            if len(vals)>0:
                meanval=np.nanmean(vals)
                minval=np.nanmin(vals)
                maxval=np.nanmax(vals)
                countval=len(vals)
            else:
                meanval=np.nan
                minval=np.nan
                maxval=np.nan
                countval=0                
            alldata=alldata+[[minval,maxval,meanval,countval]]
        zonalscore = pd.DataFrame(alldata, columns=["min","max","mean","count"])

    if zonalscore['mean'].isna().all():

        showMessage("\nAggregating to zones gives no data. Are you sure there is an overlap between aggregation zones and forecast map?\n","ERROR")
        return 
    else:
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
    _cmap=colors.ListedColormap([plt.colormaps[_cmap].resampled(100)(int(x)) for x in _seq])

    return({"cmap":_cmap, "levels":_levels, "vmin":_vmin, "vmax":_vmax,"ticklabels":None})


def get_plotparams(_data,_plotvar,currentoutDir,obsSeason,obsYearExpr,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar):
    if _plotvar=="obs_quantanom":
        title="Observed percentile anomaly \n{}-{}".format(obsSeason,obsYearExpr)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/obs_percentile-anomaly_{}-{}_{}.jpg".format(currentoutDir, obsSeason, obsYearExpr,obsDsetCode)
        seq=[10]*10+[20]*10+[30]*13+[50]*34+[70]*13+[80]*10+[90]*10
        levels = [0,10,20,30,70,80,90,100]
        cmap=colors.ListedColormap([plt.colormaps['BrBG'].resampled(100)(x) for x in seq])
        vmin=0
        vmax=100     
        cmapdict={"cmap":cmap, "levels":levels, "vmin":vmin, "vmax":vmax, "ticklabels":None}
        cmapdict["mask"]=None
        cmapdict["extend"]=None
        cmapdict["cbar_label"]="percentile of distribution"

    if _plotvar=="obs_relanom":
        title="Observed relative anomaly \n {}-{}".format(obsSeason,obsYearExpr)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/obs_relative-anomaly_{}-{}_{}.jpg".format(currentoutDir, obsSeason, obsYearExpr,obsDsetCode)        
        seq=[10,20,30,40,50,50,60,70,80,90]
        levels = [-100,-80,-60,-40,-20,0,20,40,60,80,100]
        collist=[plt.colormaps['BrBG'].resampled(100)(x) for x in seq]
        collist[4]=(1,1,1,1)
        collist[5]=(1,1,1,1)
        cmap=colors.ListedColormap(collist)
        cmapdict={"cmap":cmap, "levels":levels, "vmin":-100, "vmax":100, "ticklabels":None}
        cmapdict["mask"]=None
        cmapdict["extend"]=None
        cmapdict["cbar_label"]="% of long-term mean"
        
    if _plotvar=="obs_season":
        title="Observed rainfall \n {}-{}".format(obsSeason,obsYearExpr)
        annot="based on {} data".format(obsDsetCode)
        filename="{}/obs_values_{}-{}_{}.jpg".format(currentoutDir, obsSeason, obsYearExpr,obsDsetCode)
        cmapdict=get_cmap(_data,"YlGnBu",0,"auto",10,None)
        cmapdict["mask"]=None
        cmapdict["extend"]="max"
        cmapdict["cbar_label"]="mm"

    if _plotvar=="obs_cemcat":
        title="Observed rainfall categories \n{}-{}".format(obsSeason,obsYearExpr)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/obs_CEM-category_{}-{}_{}.jpg".format(currentoutDir, obsSeason,obsYearExpr, obsDsetCode)
        ticklabels=['BN', 'N-BN','N-AN','AN']
        levels=np.array([1,2,3,4])*5/4 - 0.6
        cmap=colors.ListedColormap(['#d2b48c', 'yellow','#0bfffb', 'blue'])
        vmin=0
        vmax=5
        cmapdict={"cmap":cmap, "levels":levels, "vmin":vmin, "vmax":vmax, "ticklabels":ticklabels}
        cmapdict["mask"]=None
        cmapdict["extend"]=None
        cmapdict["cbar_label"]="category"
        
    if _plotvar== "obs_terc":
        title="Observed tercile categories\n{}-{}".format(obsSeason,obsYearExpr)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/obs_tercile-category_{}-{}_{}.jpg".format(currentoutDir, obsSeason, obsYearExpr,obsDsetCode)
        ticklabels=['BN', 'N', 'AN']
        levels=np.array([1,2,3,])*5/4 - 0.6
        cmap=colors.ListedColormap(['#d2b48c', '0.8','#0bfffb'])
        vmin=0
        vmax=4
        cmapdict={"cmap":cmap, "levels":levels, "vmin":vmin, "vmax":vmax, "ticklabels":ticklabels}
        cmapdict["mask"]=None
        cmapdict["extend"]=None
        cmapdict["cbar_label"]="category"
        
    if _plotvar== "fcst_terc":
        title="Forecast tercile categories\n{}-{}".format(obsSeason,obsYearExpr)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/fcst_tercile-category_{}-{}_{}.jpg".format(currentoutDir, obsSeason, obsYearExpr,obsDsetCode)
        ticklabels=['BN', 'N', 'AN']
        levels=np.array([1,2,3,])*5/4 - 0.6
        cmap=colors.ListedColormap(['#d2b48c', 'white','#0bfffb'])
        vmin=0
        vmax=4
        cmapdict={"cmap":cmap, "levels":levels, "vmin":vmin, "vmax":vmax, "ticklabels":ticklabels}
        cmapdict["mask"]=None
        cmapdict["extend"]=None
        cmapdict["cbar_label"]="category"
        
    if _plotvar=="clim_mean":
        title="Climatological rainfall for {}".format(obsSeason)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/obs_longterm-mean_{}_{}.jpg".format(currentoutDir, obsSeason, obsDsetCode)
        cmapdict=get_cmap(_data,"YlGnBu",0,"auto",10,None)
        cmapdict["mask"]=None
        cmapdict["extend"]="max"
        cmapdict["cbar_label"]="mm"
        
    if _plotvar=="fcst_cemcat":
        title="Category forecast (CEM definition)\n{}-{}".format(obsSeason,obsYearExpr)
        annot=""
        filename="{}/fcst_CEM-category_{}-{}_{}.jpg".format(currentoutDir, obsSeason,obsYearExpr,obsDsetCode)
        ticklabels=['BN', 'N-BN','N-AN','AN']
        levels=np.array([1,2,3,4])*5/4 - 0.6
        cmap=colors.ListedColormap(['#d2b48c', 'yellow','#0bfffb', 'blue'])
        vmin=0
        vmax=5
        cmapdict={"cmap":cmap, "levels":levels, "vmin":vmin, "vmax":vmax, "ticklabels":ticklabels}
        cmapdict["title"]=title
        cmapdict["filename"]=filename
        cmapdict["mask"]=None
        cmapdict["extend"]=None
        cmapdict["cbar_label"]="category"
        
    if _plotvar=="fcst_cemhit":
        title="Hit/miss (for CEM categories) \n{}-{}".format(obsSeason,obsYearExpr)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/fcst_CEM-hit_{}-{}_{}.jpg".format(currentoutDir, obsSeason, obsYearExpr,obsDsetCode)
        ticklabels=['miss', 'half-miss','half-hit','hit']
        levels=np.array([0.5,1.5,2.5,3.5])
        cmap=colors.ListedColormap([plt.colormaps['RdBu'].resampled(10)(x) for x in [2,4,5,7]])
        vmin=0
        vmax=4
        cmapdict={"cmap":cmap, "levels":levels, "vmin":vmin, "vmax":vmax, "ticklabels":ticklabels}
        cmapdict["mask"]=None
        cmapdict["extend"]=None
        cmapdict["cbar_label"]=""
        
    if _plotvar=="fcst_intrate":
        title="Interest rate score (for terciles)\n{}-{}".format(obsSeason,obsYearExpr)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/fcst_interest-rate_{}-{}_{}.jpg".format(currentoutDir, obsSeason,obsYearExpr,obsDsetCode)
        cmapdict=get_cmap(_data,"BrBG",-100,100,10,None)
        cmapdict["mask"]=None
        cmapdict["extend"]=None
        cmapdict["cbar_label"]="%"
        
    if _plotvar=="fcst_ignorance":
        title="Ignorance score (for terciles)\n{}-{}".format(obsSeason,obsYearExpr)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/fcst_ignorance_{}-{}_{}.jpg".format(currentoutDir,obsSeason,obsYearExpr,obsDsetCode)
        cmapdict=get_cmap(_data,"Greys",0,10,10,None)
        cmapdict["mask"]=None
        cmapdict["extend"]=None
        cmapdict["cbar_label"]="score"
        
    if _plotvar=="fcst_hhit":
        title="Heidke hit score (for terciles)\n{}-{}".format(obsSeason,obsYearExpr)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/fcst_heidke-hit_{}-{}_{}.jpg".format(currentoutDir, obsSeason,obsYearExpr, obsDsetCode)
        ticklabels=['miss', 'hit']
        levels=np.array([0.5,1.5])
        cmap=colors.ListedColormap([plt.colormaps['BrBG'].resampled(10)(x) for x in [3,6]])
        vmin=0
        vmax=2
        cmapdict={"cmap":cmap, "levels":levels, "vmin":vmin, "vmax":vmax, "ticklabels":ticklabels}

        cmapdict["mask"]=None
        cmapdict["extend"]=None
        cmapdict["cbar_label"]="score"
        
    if _plotvar=="fcst_rpss":
        title="Ranked probabilty skill score (RPSS) (for terciles)\n{}-{}".format(obsSeason,obsYearExpr)
        annot="based on {} data and {}-{} normals".format(obsDsetCode, climStartYr,climEndYr)
        filename="{}/fcst_rpss_{}-{}_{}.jpg".format(currentoutDir,obsSeason, obsYearExpr, obsDsetCode)
        vmin=-1
        vmax=1
        cmapdict=get_cmap(_data,"BrBG",vmin,vmax,10,None)
        cmapdict["mask"]=None
        cmapdict["cbar_label"]="score"
        cmapdict["extend"]=None
                
    cmapdict["title"]=title
    cmapdict["annot"]=annot
    cmapdict["filename"]=filename
        
    return(cmapdict)




# program flow functions
################################################################################################################



# verification workhorse function and its plotting helpers
# (moved from the Worker class - now plain functions taking config explicitly,
# and reporting progress via showMessage() instead of a Qt signal)
################################################################################################################

def execVerification(config):
        #-------------------------------------------------------------------------------------------------
        #starting verification
        
        start_time = time.time()
        showMessage("Start time: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"RUNTIME")
                    
        #-------------------------------------------------------------------------------------------------
        #reading user inputs from UI
        
        showMessage("\nReading user inputs...\n","RUNTIME")
        
        #no check if input entries and files exist as it was done in updateConfig
        fcstFile =  Path(config.get('fcstFile').get('file'))
        fcstVar = config.get('fcstFile').get('variable')[config.get('fcstFile').get('ID')]

        summaryzonesFile=Path(config.get('summaryzonesFile').get('file'))
        summaryzonesVar = config.get('summaryzonesFile').get('variable')[config.get('summaryzonesFile').get('ID')]

        obsFile=Path(config.get('obsFile').get('file'))
        obsVar = config.get('obsFile').get('variable')[config.get('obsFile').get('ID')]

        outDir=Path(config.get('outDir'))

        climStartYr = int(config.get('climStartYear'))
        climEndYr = int(config.get('climEndYear'))
        
        obsYear = int(config.get('verifYear')) #year of the first month of the season
        obsSeason = config.get('verifPeriod').get('season')[config.get('verifPeriod').get('indx')]
        
        obsDsetCode=config.get('obsDsetCode')
        
        obsFileFormat=config.get('obsFileFormat')

        outputQuantanom = config.get('outputQuantanom')
        outputHeidke = config.get('outputHeidke')
        outputIgnorance = config.get('outputIgnorance')
        outputIntrate = config.get('outputIntrate')
        outputCemhit = config.get('outputCemhit')
        outputObscemcat = config.get('outputObscemcat')
        outputObstercile = config.get('outputObstercile')
        outputFcstcemcat = config.get('outputFcstcemcat')
        outputFcsttercile = config.get('outputFcsttercile')
        outputObsrelanom = config.get('outputObsrelanom')
        outputObsvalue = config.get('outputObsvalue')
        outputObsclim = config.get('outputObsclim')
        outputRpss = config.get('outputRpss')
        
        #checks on input
        
        if climStartYr>=climEndYr:
            showMessage("Climatological period start year ({}) larger than end year ({}). Terminating...".format(climStartYr,climEndYr), "ERROR")
            return

        if climEndYr-climStartYr<20:
            showMessage("Climatological period starting in {} and ending in {} is only {} years long. That is rather short. Please reconsider.".format(climStartYr,climEndYr,climEndYr-climStartYr+1), "NONCRITICAL")

            
        #checking dependencies
        if outputCemhit:
            outputObscemcat=True
        if outputRpss:
            outputObscemcat=True

        
        seasDuration,seasLastMon=seasonParam[obsSeason]
        
        if seasLastMon-seasDuration<0:
            obsLastYear=obsYear+1
            obsYearExpr="{}-{}".format(obsYear,obsYear+1)
        else:
            obsLastYear=obsYear
            obsYearExpr=obsYear
            
        #output files will use this code
        fcstCode="{}-{}".format(obsSeason,obsYearExpr) 
            
        #checking and creating output directory
        currentoutDir="{}/verification_{}-{}/{}".format(outDir,obsSeason,obsYearExpr,obsDsetCode)

        if not os.path.exists(currentoutDir):
            showMessage("Creating {}".format(currentoutDir), "INFO")
            try:
                os.makedirs(currentoutDir)
            except:
                showMessage("Could not create {}. Stopping...".format(currentoutDir), "ERROR")
                return False

            
            
            
        #-------------------------------------------------------------------------------------------------
        #read and rasterize the forecast vector file
        
        showMessage('\nReading forecast file...',"RUNTIME")
        showMessage(str(fcstFile),"RUNTIME")

        #reading geojson file
        try:
            fcstVector = gpd.read_file(fcstFile)
            #making sure values are integers and not string
            fcstVector[fcstVar]=fcstVector[fcstVar].astype(int)
        except:
            showMessage("File {} cannot be read. please check if the file is properly formatted".format(fcstFile), "ERROR")
            return False

        #check for forecast categories here
        test=np.unique(fcstVector[fcstVar])
        #int has to be there,because categories can be saved as string
        test=[int(x) not in [1,2,3,4] for x in test]
        if np.sum(test)>0:
            showMessage("Forecast variable should have four values (1,2,3,4) denoting four CEM forecast categories. This is not the case. Please check if {} file is properly formatted and if {} variable of that file the one that describes forecast".format(fcstFile,fcstVar), "ERROR")
            return False

        showMessage("Successfuly read forecast data from {}".format(fcstFile), "INFO")


        
        #-------------------------------------------------------------------------------------------------
        # reading observations
        
        showMessage("\nReading observations...","RUNTIME")
        showMessage(str(obsFile.resolve()),"RUNTIME")

        #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        #this is where code is different for csv and netcdf formats
        if obsFileFormat=="netcdf":
            try:
                #decode_times fixes the IRI netcdf calendar problem
                ds = xr.open_dataset(obsFile, decode_times=False)
            except:
                showMessage("File cannot be read. please check if the file is properly formatted", "ERROR")
                return False

            #aligning coordinate names    
            if "valid_time" in ds.coords.keys():
                showMessage("found valid_time - renaming to time","RUNTIME")
                ds=ds.rename({"valid_time":"time"})
            if "T" in ds.coords.keys():
                showMessage("found T - renaming to time","RUNTIME")
                ds=ds.rename({"T":"time"})
            if "X" in ds.coords.keys():
                showMessage("found X - renaming to longitude","RUNTIME")
                ds=ds.rename({"X":"longitude"})
            if "Y" in ds.coords.keys():
                showMessage("found Y - renaming to longitude","RUNTIME")
                ds=ds.rename({"Y":"latitude"})        
            if "lon" in ds.coords.keys():
                showMessage("found lon - renaming to logitude","RUNTIME")
                ds=ds.rename({"lon":"longitude"})
            if "lat" in ds.coords.keys():
                showMessage("found lat - renaming to latitude","RUNTIME")
                ds=ds.rename({"lat":"latitude"})

            if ds["time"].attrs['calendar'] == '360':
                ds["time"].attrs['calendar'] = '360_day'
            ds = xr.decode_cf(ds)
            ds=ds.convert_calendar("standard", align_on="date")


            if not obsVar in  ds.variables:
                msg=f"{obsVar} is not available. Are you sure this is the variable you wanted?"
                showMessage(msg, "ERROR")
                return

            #exctracting obsVar dataArray
            obs=ds[obsVar]

            #testing if variable has all required dimensions
            test=[x not in obs.coords.keys() for x in ["latitude","longitude","time"]]
            if np.sum(test)>0:
                showMessage("Observed variable should have time,latitude and longitude coordinates. This is not the case. Please check if {} file is properly formatted and if {} variable of that file the one that describes forecast".format(obsFile,obsVar), "ERROR")

                #dropping unnecessary dimensions
                for dimName in obs.sizes.keys():
                    if dimName not in ["latitude","longitude","time"]:
                        if obs.sizes[dimName]==1:
                            msg="\tDropping redundand dimension of size 1: {}".format(dimName)
                            showMessage(msg, "RUNTIME")
                            dimValue=obs[dimName].values[0]
                            obs=obs.sel({dimName:dimValue})
                            obs=obs.drop_vars(dimName)
                        else:
                            msg="There is a redundand dimension in data that cannnot be dropped. {} of size {}. Please check your data file".format(dimName, obs.sizes[dimName])
                            showMessage(msg, "ERROR")
                            return

                return
            #processing obs data further
            obs=obs.rio.write_crs("epsg:4326") #adding crs

            if "units" in obs.attrs:
                obsunits=obs.attrs["units"]
                showMessage("Found units: {}".format(obsunits),"RUNTIME")
            else:
                obsunits="mm"
                
            obsdates=pd.to_datetime(obs.time)
            firstobsdate=obsdates.strftime('%Y-%m-%d')[0]
            lastobsdate=obsdates.strftime('%Y-%m-%d')[-1]
            
            showMessage("Observed file covers period of: {} to {}".format(firstobsdate,lastobsdate),"RUNTIME")
            
            #check against the forecast date
            firstobsyear=obsdates.year[0]
            lastobsyear=obsdates.year[-1]
            
            if climEndYr>lastobsyear or climStartYr<firstobsyear:
                showMessage("Climatological period {}-{} extends beyond period covered by data {}-{}".format(climStartYr,climEndYr,firstobsyear,lastobsyear), "ERROR")
                return False
            
            
            showMessage("Successfuly read observations from {}".format(obsFile), "INFO")
            
        else:
            ds=pd.read_csv(obsFile)
            #for the time being only CFT format
            #ID,Lat,Lon,Year,Jan...Dec
            if ("Year" not in ds.keys()):
                msg="Data should contain column named Year. Data file {} does not. Please inspect the data file.".format(obsFile)
                showMessage(msg, "ERROR")
                return False                     
            if "ID" not in ds.keys():
                msg="Data should contain column named ID. Data file {} does not.Please inspect the data file.".format(obsFile)
                showMessage(msg, "ERROR")
                return False
            
            nans=pd.isnull(ds.ID)
            if nans.any():
                badrows=np.where(nans)[0]+1
                badrows=",".join(list(badrows.astype(str)))
                showMessage("CSV file contains rows {} with no data. Please edit the {} file with text editor (NOT Excel!) to remove these rows".format(badrows, obsFile), "ERROR")
                return False                        
            locs=np.unique(ds.ID.astype(str))
            alldata=[]
            lats=[]
            lons=[]
            for name in locs:
                sel=ds.ID==name
                lats=lats+[np.unique(ds[sel].Lat.values)[0]]
                lons=lons+[np.unique(ds[sel].Lon.values)[0]]
                years=np.unique(ds[sel].Year.values)
                firstyear,lastyear=(np.min(years),np.max(years))
                data=ds[sel].iloc[:,4:]
                #check if data contains strings
#                        data=data.applymap(self.tofloat)
                data=data.values.flatten()
                try:
                    data=data.astype(float)
                except:
                    showMessage("Data for {} contains entries that are of string (character) type which cannot be converted to numerical values. There should be no non-numeric characters in the data. Please edit the {} file so that it is formatted correctly".format(name, obsFile), "ERROR")
                    return False                        
                index=pd.date_range("{}-01-01".format(int(firstyear)),"{}-12-31".format(int(lastyear)),freq="ME")
                try:
                    data=pd.DataFrame(data.reshape(-1,1), index=index,columns=[name])
                except:
                    msg="data for {} contains {} months, expected {} months - data should cover continuous period from Jan {} to Dec {} with entries for every month in that period".format(name, len(index),len(data), firstyear, lastyear)
                    showMessage(msg, "ERROR")
                    return False                 

                alldata=alldata+[data]
                
            #obs is pandas dataframe
            obspd=pd.concat(alldata, axis=1)

            obspd[obspd<0]=np.nan

            nancount=np.sum(np.isnan(obspd)).sum()
            if nancount>0:
                nanperc=np.int32(nancount/np.prod(obspd.shape)*100)
                showMessage("There are {} missing data points, which is approx {}% of all data points in this dataset. Check if this is what is expected".format(nancount,nanperc), "NONCRITICAL")                    

            #creating geodataframe with all data
            obsgpd=gpd.GeoDataFrame(obspd.T.reset_index(), geometry=gpd.points_from_xy(lons, lats), crs="EPSG:4326")

            obsdates=obspd.index
            firstobsdate=obsdates.strftime('%Y-%m-%d')[0]
            lastobsdate=obsdates.strftime('%Y-%m-%d')[-1]

            showMessage("Observed file covers period of: {} to {}".format(firstobsdate,lastobsdate),"RUNTIME")

            #check against the forecast date
            firstobsyear=obsdates.year[0]
            lastobsyear=obsdates.year[-1]


            if climEndYr>lastobsyear or climStartYr<firstobsyear:
                showMessage("Climatological period {}-{} extends beyond period covered by data {}-{}".format(climStartYr,climEndYr,firstobsyear,lastobsyear), "ERROR")
                return False

            cont=True

            showMessage("Successfuly read observations from {}".format(obsFile), "INFO")
            
            obsunits="mm"
        #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< this is where code is different for csv and netcdf formats


        
        #-------------------------------------------------------------------------------------------------
        #reading summary zones
        
        showMessage('\nReading summary zones file...',"RUNTIME")
        showMessage(str(summaryzonesFile),"RUNTIME")

        #reading zones geojson file
        try:
            summaryzonesVector = gpd.read_file(summaryzonesFile)
        except:
            showMessage("Summary zones file {} cannot be read. please check if the file is properly formatted".format(summaryzonesFile), "ERROR")
            return False
        showMessage("Successfuly read zones from {}".format(summaryzonesFile), "INFO")

        #this will be an array of id and values from the zonesVar column 
        #not sure what will happen if there are multiple features with the same ID and zonesVar column...
        summaryzonesName=summaryzonesVector[summaryzonesVar].copy()

            
        #-------------------------------------------------------------------------------------------------
        # preprocessing:
        
        showMessage("\nPreprocessing...","RUNTIME")

        print(obs)


        #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        #this is where code is different for csv and netcdf formats
        if obsFileFormat=="netcdf":            
            showMessage("Clipping observations to forecast extent...","RUNTIME")
            try:
                obs=obs.rio.clip(fcstVector.geometry.values, "epsg:4326") #clipping to fcst geojson
            except Exception as e:
                showMessage("Variable {} in the observed file {} cannot be intersected with the polygon {}\n Error: {}".format(obsVar, obsFile, fcstFile,  e), "ERROR")
                return False

            #chunking obs, in case it is a large file
#                obs=obs.chunk("auto")

            #this filters observations, and it's OK for rainfall, but if it ever is used for a different variable - then this needs to be changed
            obs=obs.where(obs>=0)

        else:
                cont=True

                showMessage("Clipping observations (csv) to forecast extent","RUNTIME")
            
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
                showMessage("Read observations for {} locations".format(nofall), "INFO")
                if nofall>nofvalid:
                    showMessage("Only {} locations fall within polygons of the forecast data. Remaining locations have been dropped".format(nofvalid), "NONCRITICAL")
                
                #converting to xarray with time and geometry dimensions
                obs=xr.DataArray(obspd_valid)
                obs=obs.rename({"dim_0":"time","index":"geometry"})
                
                #making sure no negative values
                obs=obs.where(obs>=0)
                
#                except:
#                    showMessage("Something went wrong with processing {} {}".format(obsVar, obsFile), "ERROR")
#                    return
        #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

        #creating ds to store output layers for writing to disk
        outputds=xr.Dataset()
        

        
        #-------------------------------------------------------------------------------------------------           
        # compute observed season's rainfall  - always
        
        #this has to be done first, because season time expression is needed to convert forecast vector to gridded/station format
        showMessage('\nComputing observed rainfall for target season...',"RUNTIME")

        #there is no need to differentiate between gridded and stations here!


        # compute season totals for current year
        if config.get('verifAggregation') == "sum":
            obsroll = obs.rolling(time=seasDuration, center=False).sum()
        else:
            obsroll = obs.rolling(time=seasDuration, center=False).mean()
        
        #have to remove time steps for which rolling generates nans
        if obsFileFormat=="netcdf":
            nancount=np.isnan(obsroll).sum(["latitude","longitude"])
        else:
            nancount=np.isnan(obsroll).sum(["geometry"])
            
        sel=nancount<np.prod(obsroll[0,:].shape)
        obsroll=obsroll[sel,:]
        
        #check if the target period in obs data
        
        seltime=str(obsLastYear)+"-"+months[seasLastMon-1]
        try:
            obs_season=obsroll.sel(time=seltime)
        except:
            showMessage("Observed data does not cover {}. Please check your data, or adjust verification period so that it falls within the period covered by observed data.".format(seltime), "ERROR")
            return False

        obs_season.attrs=""
        
        
        
        #-------------------------------------------------------------------------------------------------           
        # plotting observed rainfall
        if outputObsvalue:
            
            #saving into output dataset
            outputds["obs_value"]=np.round(obs_season,1)
            
            showMessage('Plotting',"RUNTIME")

            pars=get_plotparams(obs_season,"obs_season",currentoutDir,obsSeason,obsYearExpr,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)


            temp=obs_season.copy()
            #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            if obsFileFormat=="netcdf":            
                cont=True
            else:
                temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
            #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
            
            
#                test=pd.DataFrame(temp).drop(columns="geometry")
#                if np.isnan(test.values).any():
#                    nancount=np.isnan(test.values).sum()
#                    allcount=len(test)
#                    nanperc=int(nancount/allcount*100)
#                    showMessage('Data for the target period is missng at {} locations. That is {}% of all {} locations. Check if this is what is expected. Note that stations with missing value will not appear in some output maps.'.format(nancount,nanperc,allcount),"NONCRITICAL")
                
            plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                 pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["extend"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)
        else:
            showMessage("\nSkipping outputting observed value","RUNTIME")                



        
        #-------------------------------------------------------------------------------------------------
        # creating forecast CEM categories map
        
        showMessage('\nCreating forecast CEM categories map...',"RUNTIME")

        #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        #this is where code is different for csv and netcdf formats
        if obsFileFormat=="netcdf":
            showMessage('Rasterizing forecast vector file...',"RUNTIME")
            fcst_ds = make_geocube(vector_data=fcstVector, like=obs) #gridding/rasterizing forecast
            fcst_cemcat=fcst_ds[fcstVar]
            fcsttime=obs_season.time.data
            #this gives the gridded forecast file the same time dimension as observations
            fcst_cemcat=fcst_cemcat.expand_dims(time=fcsttime)

            if "x" in fcst_cemcat.coords.keys():
                showMessage("found x - renaming to longitude","RUNTIME")
                fcst_cemcat=fcst_cemcat.rename({"x":"longitude"})
            if "y" in fcst_cemcat.coords.keys():
                showMessage("found y - renaming to latitude","RUNTIME")
                fcst_cemcat=fcst_cemcat.rename({"y":"latitude"})


            #need to reassign coordinates due to float rounding issues during rasterization
            fcst_cemcat=fcst_cemcat.assign_coords(latitude=obs.latitude.data)
            fcst_cemcat=fcst_cemcat.assign_coords(longitude=obs.longitude.data)
            
            fcst_cemcat.attrs=""

        else:
            cont=True
            showMessage('Converting forecast vector to xarray with data for station locations...',"RUNTIME")
            
            fcst_cemcat=xr.DataArray(fcstPoint[fcstVar]).rename({"index":"geometry"})
            fcsttime=obs_season.time.data
            fcst_cemcat = fcst_cemcat.expand_dims(time=fcsttime)
            
        #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
        

        
        #-------------------------------------------------------------------------------------------------
        # plotting forecast CEM categories map
        if outputFcstcemcat:
            
            fcst_cemcat.attrs=""   
            outputds["fcst_cemcat"] = fcst_cemcat
            
            showMessage('Plotting',"RUNTIME")

            pars=get_plotparams(fcst_cemcat,"fcst_cemcat",currentoutDir,obsSeason,obsYearExpr,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)

            temp=fcst_cemcat.copy()
            #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            if obsFileFormat=="netcdf":            
                cont=True
            else:
                temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
            #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

            plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                 pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["extend"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)
        else:
            showMessage("\nSkipping outputting observed value","RUNTIME")                
        
        
                
        #-------------------------------------------------------------------------------------------------
        # calculating climatology
        
        showMessage("\nCalculating observed climatological mean...","RUNTIME")
        
        if not seasLastMon in obsroll.time.dt.month:
            showMessage(f"The last month of the forecasted season is {seasLastMon} but observed data only has {np.unique(obsroll.time.dt.month)}. Please check your data. Exiting...", "ERROR")
            return

        #climatology period
        obs_clim=obsroll.sel(time=obsroll.time.dt.month==seasLastMon).sel(time=slice(str(climStartYr),str(climEndYr)))
        
        #climatological mean
        clim_mean = obs_clim.mean("time")


        
        #-------------------------------------------------------------------------------------------------
        # plotting climatology
        if outputObsclim:

            clim_mean.attrs=""   
            outputds["obs_clim"]=np.round(clim_mean,2)
            
            showMessage("Plotting","RUNTIME")

            #add obsunits to plotconfig
            #obsunits="mm/day"
            pars=get_plotparams(clim_mean,"clim_mean",currentoutDir,obsSeason,obsYearExpr,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)
#            pars["cbar_label"]=obsunits

            temp=clim_mean.copy()
            #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            if obsFileFormat=="netcdf":            
                cont=True
            else:
                temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
            #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

            plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                 pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["extend"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)
        else:
            showMessage("\nSkipping outputting observed climatology","RUNTIME")                
        
            

        
        #-------------------------------------------------------------------------------------------------            
        #calculating quantiles
        
        showMessage("\nCalculating observed quantiles...","RUNTIME")
        
        print(obs_clim.shape)

 
        clim_quant=obs_clim.quantile([0.33,0.50,0.66], dim="time")


        
        #-------------------------------------------------------------------------------------------------            
        #calculating relative anomaly
                        
        if outputObsrelanom:
            
            
            showMessage("\nCalculating relative anomaly...","RUNTIME")

            obs_relanom=(obs_season-clim_mean)/clim_mean*100
            
            showMessage("Plotting","RUNTIME")
            pars=get_plotparams(obs_relanom,"obs_relanom",currentoutDir,obsSeason,obsYearExpr,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)
            
            temp=obs_relanom.copy()
            #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            if obsFileFormat=="netcdf":            
                cont=True
            else:
                temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
            #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

            plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                 pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["extend"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)

            obs_relanom.attrs=""   
            outputds["obs_relanom"]=np.round(obs_relanom)
                
        else:
            showMessage("\nSkipping relative anomaly","RUNTIME")


            
        #-------------------------------------------------------------------------------------------------
        #calculating terciles
        
        showMessage("\nCalculating observed terciles...","RUNTIME")
        
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

        
        if outputObstercile:
            
            obs_terc.attrs=""   
            outputds["obs_terc"]=obs_terc
            
            showMessage("Plotting","RUNTIME")

            pars=get_plotparams(obs_terc,"obs_terc",currentoutDir,obsSeason,obsYearExpr,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)

            temp=obs_terc.copy()
            #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            if obsFileFormat=="netcdf":            
                cont=True
            else:
                temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
            #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

            plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                 pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["extend"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)
        else:
            showMessage("\nSkipping outputting observed tercile category","RUNTIME")                
        
            
            
        
        

        #-------------------------------------------------------------------------------------------------
        #calculating forecast tercile
        
        showMessage("\nConverting CEM categories to tercile categories...","RUNTIME")
        
        temp=xr.apply_ufunc(
            cemcat_to_terc, 
            fcst_cemcat,
            input_core_dims=[["time"]],
            output_core_dims=[["time"]],
            vectorize=True
        )

        #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        if obsFileFormat=="netcdf":            
            fcst_terc=temp.transpose("time","latitude","longitude")
            fcst_terc.name="tercile"
        else:
            cont=True
            fcst_terc=temp.transpose("time","geometry")
            fcst_terc.name="tercile"
        #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

        

        if outputFcsttercile:
            
            fcst_terc.attrs=""   
            outputds["fcst_terc"]=fcst_terc
            
            showMessage("Plotting","RUNTIME")

            pars=get_plotparams(fcst_terc,"fcst_terc",currentoutDir,obsSeason,obsYearExpr,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)

            temp=fcst_terc.copy()
            #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            if obsFileFormat=="netcdf":            
                cont=True
            else:
                temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
            #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

            plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                 pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["extend"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)
        else:
            showMessage("\nSkipping outputting forecast tercile category","RUNTIME")                

            
            
        
        #-------------------------------------------------------------------------------------------------
        #calculating forecast tercileprobability
        
        showMessage("\nConverting CEM categories to tercile probabilities...","RUNTIME")
        
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
            showMessage("\nCalculating observed CEM categories...","RUNTIME")

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
                
                
            showMessage("Plotting","RUNTIME")
            pars=get_plotparams(obs_cemcat,"obs_cemcat",currentoutDir,obsSeason,obsYearExpr,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)

            temp=obs_cemcat.copy()
            #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            if obsFileFormat=="netcdf":            
                cont=True
            else:
                temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
            #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

            plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                 pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["extend"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)
                                
            obs_cemcat.attrs=""   
            outputds["obs_cemcat"]=obs_cemcat

        else:
            showMessage("\nSkipping observed CEM categories","RUNTIME")


            
        #-------------------------------------------------------------------------------------------------
        #calculating quantile anomaly

        if outputQuantanom:
            showMessage("\nCalculating quantile anomalies...","RUNTIME")
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
            
            showMessage("Plotting","RUNTIME")
            
            pars=get_plotparams(obs_quantanom,"obs_quantanom",currentoutDir,obsSeason,obsYearExpr,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)

            temp=obs_quantanom.copy()*100
            
            #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            if obsFileFormat=="netcdf":            
                cont=True
            else:
                temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
            #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
                            
            plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                 pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["extend"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)
            
                
            obs_quantanom.attrs=""   
            outputds["obs_quantanom"]=np.round(obs_quantanom,3)

        else:
            showMessage("\nSkipping quantile anomalies","RUNTIME")



        #-------------------------------------------------------------------------------------------------
        #calculating heidke hits
        
        if outputHeidke:
                showMessage("\nCalclating Heidke hit scores...","RUNTIME")
                fcst_hhit=None
                zonal_hhit=None

#                try:
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
                outputds["fcst_heidkehit"]=fcst_hhit

                showMessage("Plotting","RUNTIME")
                pars=get_plotparams(fcst_hhit,"fcst_hhit",currentoutDir,obsSeason,obsYearExpr,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)

                
                temp=fcst_hhit.copy()
                #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                if obsFileFormat=="netcdf":            
                    cont=True
                else:
                    temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                    temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
                #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

                plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                     pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["extend"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)
                
                
                #CHECK
                showMessage("Plotting Heidke hit scores zonal summary","RUNTIME")
                zonal_hhit=zonal_mean(temp,summaryzonesVector,summaryzonesName,summaryzonesVar,obsFileFormat)
                if zonal_hhit==None:
                    return
                
                plotzonalHistogram(zonal_hhit["mean"], 
                                         "Heidke skill score (HSS) for most probable tercile category\n{} {}".format(obsSeason,obsYearExpr), 
                                         "{}/{}_{}-{}_{}.jpg".format(currentoutDir, "zonal_heidke",obsSeason,obsYearExpr,obsDsetCode),
                                         "HHS [-]", 
                                         0,
                                         1,
                                         "HSS values: no-skill forecast=0, perfect forecast=1",
                                         summaryzonesVector,
                                         summaryzonesName,
                                         summaryzonesVar
                                           )                        
#                except Exception as e: 
#                    exc_type, exc_obj, exc_tb = sys.exc_info()
#                    errortxt="ERROR: {} {}\nin line:{}".format(e,exc_type, exc_tb.tb_lineno)
#                    showMessage("\nNot able to calculate Heidke hits \n{}\n".format(errortxt),"NONCRITICAL")

        else:
            showMessage("\nSkipping Heidke hit scores","RUNTIME")


            
            
        #-------------------------------------------------------------------------------------------------
        #interest rate

        if outputIntrate:
            showMessage("\nCalculating interest rate...","RUNTIME")
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
                    
                                        
                showMessage("Plotting","RUNTIME")
                pars=get_plotparams(fcst_intrate,"fcst_intrate",currentoutDir,obsSeason,obsYearExpr,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)

                intratemax=max(abs(fcst_intrate.min().data), abs(fcst_intrate.max().data))*2

                
                temp=fcst_intrate.copy()
                #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                if obsFileFormat=="netcdf":            
                    cont=True
                else:
                    temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                    temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
                #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

                plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                     pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["extend"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)

                fcst_intrate.attrs=""
                outputds["fcst_intrate"]=np.round(fcst_intrate,1)

                showMessage("Plotting interest rate zonal summary","RUNTIME")
                zonal_intrate=zonal_mean(temp,summaryzonesVector,summaryzonesName,summaryzonesVar,obsFileFormat)
                if zonal_intrate is None:
                    return

                plotzonalHistogram(zonal_intrate["mean"], 
                        "Average interest rate (for terciles)\n{} {}".format(obsSeason,obsYearExpr), 
                        "{}/{}_{}_{}_{}.jpg".format(currentoutDir, "zonal_intrate",obsSeason,obsYearExpr,obsDsetCode),
                        "interest rate [%]",
                        0,
                        100,
                        "Interest rate values: climatological forecast=0%, perfect forecast = 200%",
                        summaryzonesVector,
                        summaryzonesName,
                        summaryzonesVar
                        )
            except Exception as e: 
                exc_type, exc_obj, exc_tb = sys.exc_info()
                errortxt="ERROR: {} {}\nin line:{}".format(e,exc_type, exc_tb.tb_lineno)
                showMessage("\nNot able to calculate igterest rate \n{}\n".format(errortxt),"NONCRITICAL")
                    
                
        else:
            showMessage("\nSkipping interest rate","RUNTIME")




        #-------------------------------------------------------------------------------------------------
        #ignorance
        
        
        if outputIgnorance:
            showMessage("\nCalculating ignorance score...","RUNTIME")
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

                showMessage("Plotting","RUNTIME")
                pars=get_plotparams(fcst_ignorance,"fcst_ignorance",currentoutDir,obsSeason,obsYearExpr,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)

                temp=fcst_ignorance.copy()
                #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                if obsFileFormat=="netcdf":            
                    cont=True
                else:
                    temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                    temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
                #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

                plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                     pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["extend"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)


                fcst_ignorance.attrs=""        
                outputds["fcst_ignorance"]=np.round(fcst_ignorance,2)

                showMessage("Plotting ignorance zonal summary","RUNTIME")
                
                zonal_ignorance=zonal_mean(temp,summaryzonesVector,summaryzonesName,summaryzonesVar,obsFileFormat)
                if zonal_ignorance is None:
                    return

                plotzonalHistogram(zonal_ignorance["mean"], 
                                     "Ignorance score (for terciles)\n{} {}".format(obsSeason,obsYearExpr), 
                                     "{}/{}_{}-{}_{}.jpg".format(currentoutDir, "zonal_ignorance",obsSeason,obsYearExpr,obsDsetCode),
                                     "Ignorance [-]", 
                                     1.58,
                                        0,
                                     "Ignorance score values: climatological forecast=1,58, perfect forecast=0 (lower values better)",
                                     summaryzonesVector,
                                     summaryzonesName,
                                     summaryzonesVar
                                       )
                
            except Exception as e: 
                exc_type, exc_obj, exc_tb = sys.exc_info()
                errortxt="ERROR: {} {}\nin line:{}".format(e,exc_type, exc_tb.tb_lineno)
                showMessage("\nNot able to calculate ignorance score \n{}\n".format(errortxt),"NONCRITICAL")
                                    
                
        else:
            showMessage("\nSkipping ignorance score","RUNTIME")

            
            
        #-------------------------------------------------------------------------------------------------
        #calculating rpss
        
        if outputRpss:
            showMessage("\nCalcuating RPSS score...","RUNTIME")
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
                    
                showMessage("Plotting","RUNTIME")
                pars=get_plotparams(fcst_rpss,"fcst_rpss",currentoutDir,obsSeason,obsYearExpr,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)

                
                temp=fcst_rpss.copy()
                #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                if obsFileFormat=="netcdf":            
                    cont=True
                else:
                    temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                    temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
                #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

                
                plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                     pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["extend"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)
                fcst_rpss.attrs=""                
                outputds["fcst_rpss"]=np.round(fcst_rpss,2)


                showMessage("Plotting RPSS zonal summary","RUNTIME")
                
                zonal_rpss=zonal_mean(temp,summaryzonesVector,summaryzonesName,summaryzonesVar,obsFileFormat)
                if zonal_rpss is None:
                    return
                
                plotzonalHistogram(zonal_rpss["mean"],
                                 "Ranked probability skill score (RPSS) (for terciles)\n{} {}".format(obsSeason,obsYearExpr),
                                 "{}/{}_{}-{}_{}.jpg".format(currentoutDir, "zonal_rpss",obsSeason,obsYearExpr,obsDsetCode),"[-]", 
                                 0,
                                 1,
                                 "RPSS values: climatological forecast=0 perfect forecast=1",
                                 summaryzonesVector,
                                 summaryzonesName,
                                 summaryzonesVar)
                
            except Exception as e: 
                exc_type, exc_obj, exc_tb = sys.exc_info()
                errortxt="ERROR: {} {}\nin line:{}".format(e,exc_type, exc_tb.tb_lineno)
                showMessage("\nNot able to calculate rpss score \n{}\n".format(errortxt),"NONCRITICAL")

        else:
            showMessage("\nSkipping RPSS score","RUNTIME")





        #-------------------------------------------------------------------------------------------------
        #cem hits
        
        if outputCemhit:
                showMessage("\nCalculating CEM hit scores...","RUNTIME")
                fcst_cemhit=None
                zonal_cemhit=None
            
#                try:
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
                    

                showMessage("Plotting","RUNTIME")
                pars=get_plotparams(fcst_cemhit,"fcst_cemhit",currentoutDir,obsSeason,obsYearExpr,obsDsetCode,climStartYr,climEndYr,fcstCode,fcstVar)

                temp=fcst_cemhit.copy()
                #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                if obsFileFormat=="netcdf":            
                    cont=True
                else:
                    temp=pd.DataFrame(temp.data.T, index=temp.geometry)
                    temp=gpd.GeoDataFrame(temp.copy(), geometry=fcstPoint.geometry, crs="EPSG:4326")
                #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
        
                plotMap(temp,pars["cmap"],pars["levels"],pars["vmin"],pars["vmax"],pars["title"],
                     pars["cbar_label"],pars["ticklabels"], pars["mask"], pars["filename"],pars["extend"],pars["annot"],summaryzonesFile,summaryzonesVar,obsFileFormat)
                    
                fcst_cemhit.attrs=""
                outputds["fcst_cemhit"]=fcst_cemhit

                filename="{}/zonal_cemhitmiss_{}_{}.jpg".format(currentoutDir, fcstCode, obsDsetCode)
                title="Hits/misses (CEM categories) in zones \n{} {}".format(obsSeason,obsYearExpr,obsDsetCode)
                
                plotzonalCemhit(summaryzonesVector,summaryzonesName,summaryzonesVar,temp,filename,title,obsFileFormat)
                                    
                    
#                except Exception as e: 
#                    exc_type, exc_obj, exc_tb = sys.exc_info()
#                    errortxt="ERROR: {} {}\nin line:{}".format(e,exc_type, exc_tb.tb_lineno)
#                    showMessage("\nNot able to calculate cem hit/miss rate \n{}\n".format(errortxt),"NONCRITICAL")
                
        else:
            showMessage("\nSkipping CEM hit scores","RUNTIME")



        #-------------------------------------------------------------------------------------------------
        #writing output file
        
        showMessage("\nWriting output file...","RUNTIME")
        
        #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        if obsFileFormat=="netcdf":            
            outputfile="{}/maps_verification_{}-{}_{}.nc".format(currentoutDir,obsSeason,obsYearExpr,obsDsetCode)        
            outputds.to_netcdf(outputfile)    
            showMessage("Created {}".format(outputfile), "INFO")
        else:
            outputfile="{}/maps_verification_{}-{}_{}.csv".format(currentoutDir,obsSeason,obsYearExpr,obsDsetCode)        
            geom=outputds.geometry
            outputds=outputds.drop(["geometry","time"])
            outputdf=[]
            for var in outputds.variables:
                df=pd.DataFrame(outputds[var].data.reshape(1,-1).T)
                df.index=geom
                df.columns=[var]
                outputdf=outputdf+[df]
            outputdf=pd.concat(outputdf, axis=1)
            outputdf.to_csv(outputfile)
            cont=True
        #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
        

        #CHECK
        showMessage("\nPreparing zonal summaries...","RUNTIME")

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

        showMessage('\nFinished running verification. Check output directory {} for output'.format(currentoutDir), "SUCCESS")
#            self.finished.emit()
        return True               
            
        


def plotMap(_data,_cmap,_levels,_vmin,_vmax, _title, _cbar_label,_ticklabels, _mask, _filename,_extend,_annotation,_geometryfile, _geometryVar,_obsFileFormat="netcdf"):
    
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
                mm.annotate(text=str(row[_geometryVar])[:3], xy=row['labelcoords'][0],
                             horizontalalignment='center', zorder=10000)

        plt.title(_title, fontsize=10)
        pl.text(0,-0.03,_annotation,fontsize=6, transform=pl.transAxes)
        ax=fig.add_axes([0.82,0.25,0.02,0.5])
        if _levels is None:
            cbar = fig.colorbar(m, cax=ax, label=_cbar_label,extend=_extend)
        else:
            cbar = fig.colorbar(m, cax=ax,ticks=_levels, label=_cbar_label, extend=_extend)
        if _ticklabels is not None:
            cbar.ax.set_yticklabels(_ticklabels)
        plt.subplots_adjust(bottom=0.05,top=0.9,right=0.8,left=0.05)
        plt.savefig(_filename, dpi=300)
        showMessage("Created {}".format(_filename), "INFO")
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
                m.annotate(text=str(row[_geometryVar])[:3], xy=row['labelcoords'][0],
                             horizontalalignment='center', zorder=10000, fontsize=5)
        
        plt.title(_title, fontsize=10)
        pl.text(0,-0.03,_annotation,fontsize=6, transform=pl.transAxes)
        ax=fig.add_axes([0.82,0.25,0.02,0.5])
        sm = plt.cm.ScalarMappable(cmap=_cmap, norm=plt.Normalize(vmin=_vmin, vmax=_vmax))
        # fake up the array of the scalar mappable. Urgh...
        sm._A = []
        if _levels is None:
            cbar = fig.colorbar(sm, cax=ax, label=_cbar_label,extend=_extend)
        else:
            cbar = fig.colorbar(sm, cax=ax,ticks=_levels, label=_cbar_label,extend=_extend)
        if _ticklabels is not None:
            cbar.ax.set_yticklabels(_ticklabels)
        plt.subplots_adjust(bottom=0.05,top=0.9,right=0.8,left=0.05)
        plt.savefig(_filename, dpi=300)
        showMessage("Created {}".format(_filename), "INFO")
        plt.close()
        
            
def plotzonalHistogram(_data, _title, _filename, _ylabel, _hline1, _hline2, _annotation,_summaryzonesVector,_summaryzonesName,_summaryzonesVar):
    
    fig=plt.figure(figsize=(6,3))
    pl=fig.add_subplot(1,1,1)
    plt.title(_title, fontsize=10)
    bars=_data.plot.bar()

    for i,x in enumerate(np.isnan(_data)):
        if x:
            pl.text((float(i)+0.5)/len(_data),0.1,"no data", rotation=90, ha='center', va='bottom', transform=pl.transAxes, color="0.8")
            
    pl.axhline(_hline1, linestyle="--",color="0.7")
    pl.axhline(_hline2, linestyle="--",color="0.7")
    
    pl.text(0.1,0.02,_annotation,fontsize=6, transform=plt.gcf().transFigure)
    
    pl.set_xlabel("zone")
    pl.set_ylabel(_ylabel)
    yrange=np.abs(_hline1-_hline2)

    ymin=np.min([-0.05*yrange, np.nanmin(_data)])
    pl.set_ylim(ymin,None)
    pl.set_xticklabels([str(x)[:3] for x in _summaryzonesName])
    
    
    #plotting small inlay with regions map
    ax2=fig.add_axes([0.79,0.3,0.2,0.4],projection=ccrs.PlateCarree())
    
    regions=_summaryzonesVector.copy()
    m=regions.boundary.plot(ax=ax2, linewidth=0.5, color="0.7", zorder=1000)
    
    regions["labelcoords"]=regions['geometry'].apply(lambda x: x.representative_point().coords[:])
    for idx, row in regions.iterrows():
        m.annotate(text=str(row[_summaryzonesVar])[:3], xy=row['labelcoords'][0],
                     horizontalalignment='center', zorder=10000, fontsize=5, color="0.5")

    ax2.spines['geo'].set_edgecolor('0.7')
    
    plt.subplots_adjust(bottom=0.25,top=0.85, right=0.75,left=0.15)
    plt.savefig(_filename, dpi=300)
    showMessage("Created {}".format(_filename), "INFO")
    plt.close()
    
    
    
    
def plotzonalCemhit(summaryzonesVector,summaryzonesName,summaryzonesVar,fcst_cemhit,filename,title,obsFileFormat):
    showMessage("Creating hit/miss graph for zones","RUNTIME")
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
                showMessage("\nNot able to calculate cem hit/miss rate \n{}\n".format(errortxt),"NONCRITICAL")
                clipped=np.array([])
            alldata=alldata+[clipped[~np.isnan(clipped)]]
    else:
        crossed=fcst_cemhit.overlay(summaryzonesVector, how="intersection")
        for i,val in enumerate(summaryzonesName):
            sel=crossed[summaryzonesVar]==val
            clipped=crossed[sel][0]
            alldata=alldata+[clipped[~np.isnan(clipped)]]
            
    bins=[-0.5,0.5,1.5,2.5,3.5]
    labels=["miss","half-miss","half-hit","hit"]
    cols=colors.ListedColormap([plt.colormaps['RdBu'].resampled(10)(x) for x in [2,4,5,7]])
    cols=[cols(i) for i in range(4)]

    nx,ny=6,int(np.ceil(nzones/6))
    fx,fy=7,int(np.ceil(nzones/6))+1            

    fig=plt.figure(figsize=(fx,fy))
    for i,zdata in enumerate(alldata):
        pl=fig.add_subplot(ny,nx,i+1)   
        if len(zdata)>0:
            vals,b=np.histogram(zdata, bins=bins, density=True)
            pie=pl.pie(vals, colors=cols)
        else:
            pl.pie([1], colors=["white"])
            pl.text(0.5,0.5,"no data", ha='center', va='center', transform=pl.transAxes, color="0.8")
        pl.set_title("{}".format(str(summaryzonesName[i])[0:3]))
        
    #positioning the legend
    fig.legend(labels, loc="lower right", bbox_to_anchor=(1,0))
    
    #plotting small inlay with regions
    ax2=fig.add_axes([0.79,0.59,0.2,0.4],projection=ccrs.PlateCarree())
#        ax2=fig.add_axes([0.8,0.59,0.2,0.4])
    
    regions=summaryzonesVector.copy()
    m=regions.boundary.plot(ax=ax2, linewidth=0.5, color="0.7", zorder=1000)
    
    regions["labelcoords"]=regions['geometry'].apply(lambda x: x.representative_point().coords[:])
    for idx, row in regions.iterrows():
        m.annotate(text=str(row[summaryzonesVar])[:3], xy=row['labelcoords'][0],
                     horizontalalignment='center', zorder=10000, fontsize=5, color="0.5")

    ax2.spines['geo'].set_edgecolor('0.7')
    
    
    plt.suptitle(title, fontsize=10)
    plt.subplots_adjust(bottom=0.05,top=0.75,right=0.7,left=0.05)
    plt.savefig(filename, dpi=300)

    showMessage("Created {}".format(filename), "INFO")
    

    
