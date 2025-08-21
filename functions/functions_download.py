import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import requests
import json,os, sys, glob, datetime
import gl
import xarray as xr
import datetime
import io

import sys
import time
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtWidgets import QFileDialog

from cftime import num2date
import traceback
from pathlib import Path

from functions.functions_download import *

gl.maxLeadTime=6
gl.configFile="download.json"    
gl.keepRaw=False

msgColors={"ERROR": "red",
           "INFO":"blue",
           "RUNTIME":"grey",
           "NONCRITICAL":"red",
           "SUCCESS":"green"
          }

seasons=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan-Mar","Feb-Apr","Mar-May","Apr-Jun","May-Jul","Jun-Aug","Jul-Sep","Aug-Oct","Sep-Nov","Oct-Dec","Nov-Jan","Dec-Feb"]

months=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

indexSources={
"IOD_JMA": ["IOD (Dipole Mode Index) from JMA", "https://ds.data.jma.go.jp/tcc/tcc/products/elnino/index/sstindex/base_period_9120/DMI/anomaly"],
"Nino3_JMA":["Nino3 from JMA","https://ds.data.jma.go.jp/tcc/tcc/products/elnino/index/sstindex/base_period_9120/Nino_3/anomaly"],
"Nino4_JMA": ["Nino4 from JMA","https://ds.data.jma.go.jp/tcc/tcc/products/elnino/index/sstindex/base_period_9120/Nino_4/anomaly"]
}

predictandSources={
"PRCP_CHIRPSp25_IRIDL":["CHIRPS 0.25 deg rainfall from IRI data library",
                     "https://iridl.ldeo.columbia.edu/SOURCES/.UCSB/.CHIRPS/.v2p0/.daily-improved/.global/.0p25/.prcp/{}/mul/T/(1 Jan {})/(31 Dec {})/RANGE/T/({} {}-{})/seasonalAverage/Y/({})/({})/RANGEEDGES/X/({})/({})/RANGEEDGES/-999/setmissing_value/data.nc", "sum", 1981],
}

predictorSources={
"SST_ERSSTv5_IRIDL":["Sea Surface temperature ERSST v5",
                         "http://iridl.ldeo.columbia.edu/SOURCES/.NOAA/.NCDC/.ERSST/.version5/.sst/T/(Jan 1979)/(Dec {})/RANGE/T/({} {}-{})/VALUES/T/12/STEP/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc", 1854],
}

fcstpredSources={
    "SST_GEOSS2S_IRIDL": ["SST forecasted by GEOSS2S (NASA)", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.NASA-GEOSS2S/.HINDCAST/.MONTHLY/.sst/[M]/average/SOURCES/.Models/.NMME/.NASA-GEOSS2S/.FORECAST/.MONTHLY/.sst/[M]/average/appendstream/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc",1981],
    "SST_CCSM4_IRIDL": ["SST forecasted by COLA-RSMAS-CCSM4", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.COLA-RSMAS-CCSM4/.MONTHLY/.sst/[M]/average/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc", 1981],
    "SST_CFSv2_IRIDL": ["SST forecasted by CFSv2 (NCEP)", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.NCEP-CFSv2/.HINDCAST/.PENTAD_SAMPLES_FULL/.sst/[M]/average/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc", 1981],
    "PRCP_GEOSS2S_IRIDL": ["Rainfall forecasted by GEOSS2S (NASA)", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.NASA-GEOSS2S/.HINDCAST/.MONTHLY/.prec/[M]/average/SOURCES/.Models/.NMME/.NASA-GEOSS2S/.FORECAST/.MONTHLY/.prec/[M]/average/appendstream/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc", 1981],
    "PRCP_CCSM4_IRIDL": ["Rainfall forecasted by COLA-RSMAS-CCSM4", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.COLA-RSMAS-CCSM4/.MONTHLY/.prec/[M]/average/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc", 1981],
    "PRCP_CFSv2_IRIDL": ["Rainfall forecasted by CFSv2 (NCEP)", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.NCEP-CFSv2/.HINDCAST/.PENTAD_SAMPLES_FULL/.prec/[M]/average/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc", 1981],
    "z500_GEOSS2S_IRIDL": ["z500 forecasted by GEOSS2S (NASA)", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.NASA-GEOSS2S/.HINDCAST/.MONTHLY/.h500/[M]/average/SOURCES/.Models/.NMME/.NASA-GEOSS2S/.FORECAST/.MONTHLY/.h500/[M]/average/appendstream/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc", 1981],
    "z200_CCSM4_IRIDL": ["z200 forecasted by COLA-RSMAS-CCSM4", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.COLA-RSMAS-CCSM4/.MONTHLY/.gz/[M]/average/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc", 1981],
    "z200_CFSv2_IRIDL": ["z200 forecasted by CFSv2 (NCEP)", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.NCEP-CFSv2/.HINDCAST/.PENTAD_SAMPLES_FULL/.hgt/[M]/average/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc", 1981],
}

#    "SST_CanSIPS-IC4_IRIDL": ["SST forecasted by CanSIPS-IC4", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.CanSIPS-IC4/.HINDCAST/.MONTHLY/.sst/[M]/average/SOURCES/.Models/.NMME/.CanSIPS-IC4/.FORECAST/.MONTHLY/.sst/[M]/average/appendstream/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc", 1981],
#    "PRCP_CanSIPS-IC4_IRIDL": ["Rainfall forecasted by CanSIPS-IC4", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.CanSIPS-IC4/.HINDCAST/.MONTHLY/.prec/[M]/average/SOURCES/.Models/.NMME/.CanSIPS-IC4/.FORECAST/.MONTHLY/.prec/[M]/average/appendstream/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc", 1981],
#    "z500_CanSIPS-IC4_IRIDL": ["z500 forecasted by CanSIPS-IC4", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.CanSIPS-IC4/.HINDCAST/.MONTHLY/.hgt/[M]/average/SOURCES/.Models/.NMME/.CanSIPS-IC4/.FORECAST/.MONTHLY/.hgt/[M]/average/appendstream/P/500/500/RANGEEDGES/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc", 1981],

#    "SST_SEAS51_IRIDL": ["SST forecasted by SEAS51 (ECMWF)", "https://iridl.ldeo.columbia.edu/SOURCES/.EU/.Copernicus/.CDS/.C3S/.ECMWF/.SEAS51_iri2/.hindcast/.sst/[M]/average/SOURCES/.EU/.Copernicus/.CDS/.C3S/.ECMWF/.SEAS51_iri2/.forecast/.sst/[M]/average/appendstream/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc", 1981],
#    "SST_GCFS2p2_IRIDL": ["SST forecasted by GCFS2p2 (DWD)", "https://iridl.ldeo.columbia.edu/SOURCES/.EU/.Copernicus/.CDS/.C3S/.DWD/.GCFS2p2/.hindcast/.sst/[M]/average/SOURCES/.EU/.Copernicus/.CDS/.C3S/.DWD/.GCFS2p2/.forecast/.sst/[M]/average/appendstream/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc", 1981],
#    "SST_CPS3_IRIDL": ["SST forecasted by CPS3 (JMA)", "https://iridl.ldeo.columbia.edu/SOURCES/.EU/.Copernicus/.CDS/.C3S/.JMA/.CPS3/.hindcast/.sst/[M]/average/SOURCES/.EU/.Copernicus/.CDS/.C3S/.JMA/.CPS3/.forecast/.sst/[M]/average/appendstream/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc", 1981],
#    "SST_System9_IRIDL": ["SST forecasted by System9 (MeteoFrance)", "https://iridl.ldeo.columbia.edu/SOURCES/.EU/.Copernicus/.CDS/.C3S/.Meteo_France/.System9/.hindcast/.sst/[M]/average/SOURCES/.EU/.Copernicus/.CDS/.C3S/.Meteo_France/.System9/.forecast/.sst/[M]/average/appendstream/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc", 1981],
#    "SST_SPSv4_IRIDL": ["SST forecasted by SPSv4 (CMCC)", "https://iridl.ldeo.columbia.edu/SOURCES/.EU/.Copernicus/.CDS/.C3S/.CMCC/.SPSv4/.hindcast/.sst/[M]/average/SOURCES/.EU/.Copernicus/.CDS/.C3S/.CMCC/.SPSv4/.forecast/.sst/[M]/average/appendstream/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc", 1981],           

#GFDL-SPEAR - ending in July 2025


def showMessage(_message, _type="RUNTIME"):
    #this print messages to log window, which are generated outside of the threaded function
    _color=msgColors[_type]
    _message = "<pre><font color={}>{}</font></pre>".format(_color, _message)
    gl.window.log(_message)

    
def downloadUrl(_url):        
    #requesting data
    showMessage("waiting for: {}".format(_url))
    
    response=requests.get(_url)
    showMessage("done")

    #checking if response successful
    if response.status_code!=200:
        print(response)
        return
    
    return response
    
def month2int(_str):
    #converts month string to non-pythonic integer month number
    return (np.where(np.array(months)==_str)[0][0])+1  

def getLeadTime():
    srcMonth=month2int(gl.config['predictorMonth'])
    tgtMonth=month2int(gl.config['fcstTargetSeas'][0:3])
    tgtYear=int(gl.config['fcstTargetYear'])
    tgtDate=pd.to_datetime("{}-{}-01".format(tgtYear,tgtMonth))
    
    leadTime=(tgtMonth+12-srcMonth)%12
    if leadTime<1:
        msg="with forecast and target months provided ({} and {}), lead time is {} months. That exceeds the minimum allowed lead time of 1. Please adjust your configuration.".format(srcMonth, tgtMonth, leadTime)
        showMessage(msg,"ERROR")
        return None
    if leadTime>gl.maxLeadTime:
        msg="with forecast and target months provided ({} and {}), lead time is {} months. That exceeds the maximum allowed lead time of {}. Please adjust your configuration.".format(srcMonth, tgtMonth, leadTime, gl.maxLeadTime)
        showMessage(msg,"ERROR")
        return None
    gl.leadTime=leadTime
    
    srcDate=tgtDate-pd.offsets.MonthBegin(leadTime)

    gl.predictorDate=srcDate
    
    return leadTime

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

    
    
def downloadPredictand():
    #read data from gui
    readGui()
    
    #save config to json file
    saveConfig()
    
    _downloadsdir=gl.config['downloadDir']
   
    _predictandcode=gl.config['predictandCode']
    _overwrite=gl.config['predictandOverwrite']
    _predictandyear=gl.config['fcstTargetYear']
    _predictandseas=gl.config['fcstTargetSeas']
    
    firstyear=gl.config['firstDataYear']
    
    south=gl.config['predictandMinLat']
    north=gl.config['predictandMaxLat']
    west=gl.config['predictandMinLon']
    east=gl.config['predictandMaxLon']

    if not os.path.exists(_downloadsdir):
        showMessage("output directory {} does not exist. creating...".format(_downloadsdir))
        try:
            os.makedirs(_downloadsdir)
            showMessage("done")
        except:
            showMessage("Output directory could not be created. Make sure that the directory is correctly defined and try again.", "ERROR")
            return
    
    
    if _predictandcode=="":
        showMessage("\nplease select variable to download", "ERROR")
        return

    if _predictandyear=="":
        showMessage("\nplease provide predicand's year", "ERROR")
        return
    
    if not is_number(_predictandyear):
        showMessage("\npredictand year should be numeric", "ERROR")
        return
    
    if _predictandseas=="":
        showMessage("\nplease provide predictand's season", "ERROR")
        return
    
    if firstyear=="":
        showMessage("\nplease provide first data year", "ERROR")
        return
    
    if not is_number(firstyear):
        showMessage("\nfirst data year should be numeric", "ERROR")
        return
        
    check=[]
    for _x in [east,west,south,north]:
        check.append(is_number(_x))
    if not all(check):
            showMessage("\nLat and Lon values should be numeric.", "ERROR")
            return
        
    check=[float(east)>float(west), float(north)>float(south)]
    if not all(check):
            showMessage("\nLat and Lon values should be numeric.", "ERROR")
            return    

                     
                     
            
    showMessage("\ndownloading {}".format(_predictandcode))

    _source=_predictandcode.split("_")[-1]
    
    url=predictandSources[_predictandcode][1]
    
    temporalaggregation=predictandSources[_predictandcode][2]
    
    firstavailyear=predictandSources[_predictandcode][3]
    
    if float(firstavailyear)>float(firstyear):
        showMessage("\nAdjusting requested first year to first year for which data are available. {} -> {}".format(firstyear, firstavailyear), "NONCRITICAL")
        firstyear=firstavailyear
    
    #simply - monthly target will have three letters, seasonal target - 7
    if len(_predictandseas)==3:
        #monthly
        multiply=1
        basetime="mon"
    else:
        basetime="seas"
        if temporalaggregation=="sum":
            #seasonal with sum
            multiply=3
        else:
            #seasonal with mean
            multiply=1

    
    if _source=="IRIDL":

        #defined internally, can be included in the variable-source dictionary
        firstmonth=_predictandseas[0:3]
        first_date=pd.to_datetime("01 {} {}".format(firstmonth, firstyear))
        
        finalyear=_predictandyear
        finalmonth=_predictandseas[-3:]
        
        last_date=pd.to_datetime("01 {} {}".format(finalmonth, finalyear))
        
        
        daterange="{}{}-{}{}".format(_predictandseas[0:3],firstyear, _predictandseas[-3:], finalyear)
        showMessage("requesting date range: {}".format(daterange))

        
        outfile=Path(_downloadsdir,"{}_{}_{}-{}.nc".format(_predictandcode, basetime, first_date.strftime("%Y%m"), last_date.strftime("%Y%m")))

    
        if _overwrite is False:
            if os.path.exists(outfile):
                showMessage("file {} exists, and overwrite is OFF. Skipping...".format(outfile),"NONCRITICAL")
                return
        

        
        url=url.format(multiply,firstyear, finalyear, _predictandseas, firstyear, finalyear, south,north,west,east)

        response=downloadUrl(url)
        
        if response is None:
            showMessage("failed to download data")
            return
        else:
            
            data_stream = io.BytesIO(response.content)

            # Open with xarray
            ds = xr.open_dataset(data_stream, decode_times=False)
            
            time_raw = ds['T'].values
            units = ds['T'].attrs.get('units', 'days since 1900-01-01')
            calendar = ds['T'].attrs.get('calendar', 'standard')
            if calendar == '360':
                calendar = '360_day'
            
            time_cftime = num2date(time_raw, units=units, calendar=calendar)
            
            #iridl dates are mid of the season or mid month, aligning them with our notation
            #first month first year, and last month last year
            if basetime=="seas":
                #back two months
                firstdatadate=pd.to_datetime("{}-{}-15".format(time_cftime[0].year, time_cftime[0].month))-pd.offsets.MonthBegin(2)
                #forward one month
                lastdatadate=pd.to_datetime("{}-{}-15".format(time_cftime[-1].year, time_cftime[-1].month))+pd.offsets.MonthBegin(1)
            else:
                #for montly data, it will be the first of the first month and the first of the last month
                firstdatadate=pd.to_datetime("{}-{}-15".format(time_cftime[0].year, time_cftime[0].month))-pd.offsets.MonthBegin()
                lastdatadate=pd.to_datetime("{}-{}-15".format(time_cftime[-1].year, time_cftime[-1].month))-pd.offsets.MonthBegin()
                           
            if lastdatadate<last_date:
                showMessage("Downloaded data contains data till {}, and thus does not fully cover the the requested period {}".format(last_date.strftime("%b %Y"), daterange), "NONCRITICAL")
            else:
                showMessage("All fine", "NONCRITICAL")
                
            # on successful response - writing raw file
            with open(outfile, "wb") as outf:
                outf.write(response.content)
            showMessage("Saved downloaded data to {}".format(outfile), "SUCCESS")
    
    else:
        showMessage("\nSource {} not available. Exiting...".format(_source), "ERROR")
        
    
    
    
    
    
def downloadGriddedPredictor():
    #read data from gui
    readGui()
    
    #save config to json file
    saveConfig()
    
    _downloadsdir=gl.config['downloadDir']
   
    _predictorcode=gl.config['predictorCode']
    _overwrite=gl.config['predictorOverwrite']
    _predictoryear=gl.config['predictorYear']
    _predictormonth=gl.config['predictorMonth']
    
    firstyear=gl.config['firstDataYear']
    
    south=gl.config['predictorMinLat']
    north=gl.config['predictorMaxLat']
    west=gl.config['predictorMinLon']
    east=gl.config['predictorMaxLon']

    
    for _x in [south,north,west,east]:
        if _x=="":
            showMessage("\nplease define coordinates of requested domain", "ERROR")
            return
         
    if not os.path.exists(_downloadsdir):
        try:
            os.makedirs(_downloadsdir)
            showMessage("done")
        except:
            showMessage("Output directory could not be created. Make sure that the directory is correctly defined and try again.", "ERROR")
            return
    
    if _predictorcode=="":
        showMessage("\nplease select variable to download", "ERROR")
        return

    if _predictoryear=="":
        showMessage("\nplease provide predictor's year", "ERROR")
        return
    
    if not is_number(_predictoryear):
        showMessage("\npredictor year should be numeric", "ERROR")
        return
    
    if _predictormonth=="":
        showMessage("\nplease provide predictor's month", "ERROR")
        return
    
    if firstyear=="":
        showMessage("\nplease provide first data year", "ERROR")
        return
    
    if not is_number(firstyear):
        showMessage("\nfirst data year should be numeric", "ERROR")
        return
    
    check=[]
    for _x in [east,west,south,north]:
        check.append(is_number(_x))
    if not all(check):
            showMessage("\nLat and Lon values should be numeric.", "ERROR")
            return
        
    check=[float(east)>float(west), float(north)>float(south)]
    if not all(check):
            showMessage("\nLat and Lon values should be numeric.", "ERROR")
            return    
 

    showMessage("\ndownloading {}".format(_predictorcode))
    
    _source=_predictorcode.split("_")[-1] 
    
    firstavailyear=predictorSources[_predictorcode][2]
    
    if float(firstavailyear)>float(firstyear):
        showMessage("\nAdjusting requested first year to first year for which data are available. {} -> {}".format(firstyear, firstavailyear), "NONCRITICAL")
        firstyear=firstavailyear    
        
        
    #always mon 
    basetime="mon"
    
    if _source=="IRIDL":

        #defined internally, can be included in the variable-source dictionary
        firstmonth=_predictormonth
        first_date=pd.to_datetime("01 {} {}".format(firstmonth, firstyear))
        
        lastyear=_predictoryear
        lastmonth=_predictormonth
        
        last_date=pd.to_datetime("01 {} {}".format(lastmonth, lastyear))
        
        
        daterange="{}{}-{}{}".format(_predictormonth,firstyear, _predictormonth, lastyear)
        showMessage("requesting date range: {}".format(daterange))

        outfile=Path(_downloadsdir,"{}_{}_{}-{}.nc".format(_predictorcode, basetime, first_date.strftime("%Y%m"), last_date.strftime("%Y%m")))
        
        if _overwrite is False:
            if os.path.exists(outfile):
                showMessage("file {} exists, and overwrite is OFF. Skipping...".format(outfile),"NONCRITICAL")
                return

        #"http://iridl.ldeo.columbia.edu/SOURCES/.NOAA/.NCDC/.ERSST/.version5/.sst/T/
        # (Jan 1982)/(Dec 2021)/RANGE/T/({} {}-{})/VALUES/T/12/STEP/Y/{}/{}/RANGEEDGES/
        # X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc"
        url=predictorSources[_predictorcode][1]
        url=url.format(lastyear, _predictormonth, firstyear, lastyear, south,north,west,east)

        response=downloadUrl(url)
        
        if response is None:
            showMessage("failed to download data")
            return
        else:
            
            data_stream = io.BytesIO(response.content)

            # Open with xarray
            ds = xr.open_dataset(data_stream, decode_times=False)
            
            time_raw = ds['T'].values
            units = ds['T'].attrs.get('units', 'days since 1900-01-01')
            calendar = ds['T'].attrs.get('calendar', 'standard')
            if calendar == '360':
                calendar = '360_day'
            
            time_cftime = num2date(time_raw, units=units, calendar=calendar)
            
            #iridl dates are mid of the season or mid month, aligning them with our notation
            #first month first year, and last month last year
            #back two months
            firstdatadate=pd.to_datetime("{}-{}-15".format(time_cftime[0].year, time_cftime[0].month))-pd.offsets.MonthBegin(2)
            #forward one month
            lastdatadate=pd.to_datetime("{}-{}-15".format(time_cftime[-1].year, time_cftime[-1].month))+pd.offsets.MonthBegin(1)

            if lastdatadate<last_date:
                showMessage("Downloaded data contains data till {}, and thus does not fully cover the the requested period {}".format(last_date.strftime("%b %Y"), daterange), "NONCRITICAL")
            else:
                showMessage("All fine", "NONCRITICAL")
                
            # on successful response - writing raw file
            with open(outfile, "wb") as outf:
                outf.write(response.content)
            showMessage("Saved downloaded data to {}".format(outfile), "SUCCESS")
            
        
def downloadFcstPredictor():
    
    readGui()
    
    #save config to json file
    saveConfig()
    
    _downloadsdir=gl.config['downloadDir']
    
    _predictorcode=gl.config['fcstpredCode']
    _overwrite=gl.config['fcstpredOverwrite']
    _predictoryear=gl.config['predictorYear']
    _predictormonth=gl.config['predictorMonth']
    
    firstyear=gl.config['firstDataYear']
    
    south=gl.config['fcstpredMinLat']
    north=gl.config['fcstpredMaxLat']
    west=gl.config['fcstpredMinLon']
    east=gl.config['fcstpredMaxLon']
    

    
    
    for _x in [south,north,west,east]:
        if _x=="":
            showMessage("\nplease define coordinates of requested domain", "ERROR")
            return
    
    if not os.path.exists(_downloadsdir):
        try:
            os.makedirs(_downloadsdir)
            showMessage("done")
        except:
            showMessage("Output directory could not be created. Make sure that the directory is correctly defined and try again.", "ERROR")
            return
    
    if _predictorcode=="":
        showMessage("\nplease select variable to download", "ERROR")
        return

    if _predictoryear=="":
        showMessage("\nplease provide predictor's year", "ERROR")
        return
    
    if not is_number(_predictoryear):
        showMessage("\npredictor year should be numeric", "ERROR")
        return
    
    if _predictormonth=="":
        showMessage("\nplease provide predictor's month", "ERROR")
        return
    
    if firstyear=="":
        showMessage("\nplease provide first data year", "ERROR")
        return
    
    if not is_number(firstyear):
        showMessage("\nfirst data year should be numeric", "ERROR")
        return
    
    check=[]
    for _x in [east,west,south,north]:
        check.append(is_number(_x))
    if not all(check):
            showMessage("\nLat and Lon values should be numeric.", "ERROR")
            return
        
    check=[float(east)>float(west), float(north)>float(south)]
    if not all(check):
            showMessage("\nLat and Lon values should be numeric.", "ERROR")
            return    
 

    showMessage("\ndownloading {}".format(_predictorcode))
    
    _source=_predictorcode.split("_")[-1]
    
    _predictortime=pd.to_datetime("{}-{}-01".format(_predictoryear, _predictormonth))
    _forecasttime=_predictortime+pd.offsets.MonthBegin(1)
    _forecastyear=_forecasttime.year
    _forecastmon=months[_forecasttime.month-1]

    url=fcstpredSources[_predictorcode][1]
    
    firstavailyear=fcstpredSources[_predictorcode][2]
    
    if float(firstavailyear)>float(firstyear):
        showMessage("\nAdjusting requested first year to first year for which data are available. {} -> {}".format(firstyear, firstavailyear), "NONCRITICAL")
        firstyear=firstavailyear
        
    #this is with respect to predictor month, not forecast month
    leadtime=getLeadTime()


    #this is with respect to forecast month
    leadtimestart=leadtime-1+0.5

    if len(gl.config['fcstTargetSeas'])==3:
        basetime="mon"
        leadtimeend=leadtime-1+0.5
    else:
        basetime="seas"
        leadtimeend=leadtime-1+2.5

    leadtimefile=(leadtimestart+leadtimeend)/2


    if _source=="IRIDL":

        
        #defined internally, can be included in the variable-source dictionary
        firstmonth=_predictormonth
        first_date=pd.to_datetime("01 {} {}".format(firstmonth, firstyear))

        lastyear=_predictoryear
        lastmonth=_predictormonth

        last_date=pd.to_datetime("01 {} {}".format(lastmonth, lastyear))


        daterange="{}{}-{}{}".format(_predictormonth,firstyear, _predictormonth, lastyear)
        showMessage("requesting date range: {}".format(daterange))


        outfile=Path(_downloadsdir,"{}_{}_{}-{}.nc".format(_predictorcode, basetime, first_date.strftime("%Y%m"), last_date.strftime("%Y%m")))
        
        if _overwrite is False:
            if os.path.exists(outfile):
                showMessage("file {} exists, and overwrite is OFF. Skipping...".format(outfile),"NONCRITICAL")
                return


        url=url.format(_forecastmon, firstyear, _forecastyear,leadtimestart,leadtimeend,south,north,west,east)

        response=downloadUrl(url)

        if response is None:
            showMessage("failed to download forecast data")
            return
        else:

            data_stream = io.BytesIO(response.content)

            # Open with xarray 
            # chunks argument prevents error with time conversion, requires dask to be installed, though
            try:
                
                ds = xr.open_dataset(data_stream, decode_times=False, chunks={})
            except:
                showMessage("Could not read downloaded data. This might be a result of a temporary problem with IRIDL server. Wait a couple of minutes and re-download the data. If the same error occurs - copy and paste the following url into a browser to identify the problem: \n{}".format(url), "ERROR")
                return
            #renaming to time as later functions do not work with T which is used by iri files
            ds=ds.rename({"S":"time", "X":"lon", "Y":"lat", "L":"lead_time"})


            if ds["time"].attrs['calendar'] == '360':
                ds["time"].attrs['calendar'] = '360_day'

            #decoding dates
            ds = xr.decode_cf(ds, use_cftime=True)

            #converting calendar
            ds=ds.convert_calendar("standard", align_on="date")

            #substituting initial condition time for forcast reference time
            #ds.time will be set on 1st of the month, newtime will be the last day of the previous month
            newtime=pd.to_datetime(ds.time)-pd.offsets.MonthBegin()
            ds["time"]=newtime

            #collapsing Lead time variable
            for var in ds.data_vars:
                ds[var] = ds[var].mean("lead_time")
            #adding atribute
            basetimetext={"mon":"mean monthly value for the forecast target month", "seas":"mean seasonal value for the forecast target season"}
            ds.attrs["description"]="Data time is set to the last day of the month for which initialization data are available. The forecast reference time, i.e. month when forecast is issued is the first day of the subsequent month"
            ds.attrs["value"]=basetimetext[basetime]
            ds.attrs["forecast_target"]=gl.config['fcstTargetSeas']        
            ds.attrs["forecast_reference_time"]="01 {}".format(_forecastmon)
        
            #iridl will not complain if available data does not cover the entire requested period
            #need to check if data for forecast is available.
            lastdatatime=pd.to_datetime(ds["time"].values[-1])
            firstdatatime=pd.to_datetime(ds["time"].values[0])

            if _predictortime !=lastdatatime:
                showMessage("Downloaded data contains data till {}, and thus does not include data required for forecast, i.e. for {}".format(lastdatatime.strftime("%b %Y"), _predictortime.strftime("%b %Y")), "ERROR")
                return
            else:
                showMessage("All fine", "NONCRITICAL")
                
            # on successful response - writing file
            ds.to_netcdf(outfile)
            showMessage("Saved downloaded data to {}".format(outfile), "SUCCESS")
            

def downloadIndexPredictor():
    
    readGui()    
    
    #save config to json file
    saveConfig()
    
    _downloadsdir=gl.config['downloadDir']
    _indexcode=gl.config['indexCode']
    _overwrite=gl.config['indexOverwrite']
    _predictoryear=gl.config['predictorYear']
    _predictormonth=gl.config['predictorMonth']
    
    firstyear=gl.config['firstDataYear']
    
    if not os.path.exists(_downloadsdir):
        try:
            os.makedirs(_downloadsdir)
            showMessage("done")
        except:
            showMessage("Output directory could not be created. Make sure that the directory is correctly defined and try again.", "ERROR")
            return
    
    if _indexcode=="":
        showMessage("\nplease select variable to download", "ERROR")
        return

    if _predictoryear=="":
        showMessage("\nplease provide predictor's year", "ERROR")
        return
    
    if not is_number(_predictoryear):
        showMessage("\npredictor year should be numeric", "ERROR")
        return
    
    if _predictormonth=="":
        showMessage("\nplease provide predictor's month", "ERROR")
        return
    
    if firstyear=="":
        showMessage("\nplease provide first data year", "ERROR")
        return
    
    if not is_number(firstyear):
        showMessage("\nfirst data year should be numeric", "ERROR")
        return
    
    showMessage("\ndownloading {}".format(_indexcode))

    _predictordate=pd.to_datetime("01 {} {}".format(_predictormonth, _predictoryear))+pd.offsets.MonthEnd()
    _url=indexSources[_indexcode][1]
    _source=_indexcode.split("_")[-1]

    
    #requesting data
    response=downloadUrl(_url)
    

    #index-specific processing
    if _source=="JMA":
        #processing raw data
        data=response.text.split("\n")
        data=np.array([x.split() for x in data[1:-1]])
        years=data[:,0]
        data=data[:,1:].flatten()
        
        #creating and populating dataframe
        dates=pd.date_range("{}-01-01".format(years[0]), periods=len(data), freq="ME")
        
        _index=_indexcode.split("_")[0]
        output=pd.DataFrame(data, index=dates, columns=[_index]).astype(float)
        output[output==99.90]=np.nan
        output=output[~np.isnan(output).values]
        
    first_date=output.index[0].strftime("%Y%m")
    last_date=output.index[-1].strftime("%Y%m")
    firstavailyear=output.index[0].year
    lastavailyear=output.index[-1].year
    
    showMessage("downloaded data covers the period of {} to {}".format(first_date, last_date))

    showMessage("checking if predictor date {} in data...".format(_predictordate.strftime("%b %Y")))
    if not _predictordate in output.index:
        showMessage("predictor date {} not in data!".format(_predictordate.strftime("%b %Y")),"NONCRITICAL")

    
    if float(firstavailyear)>float(firstyear):
        showMessage("\nAdjusting requested first year to first year for which data are available. {} -> {}".format(firstyear, firstavailyear), "NONCRITICAL")
        firstyear=firstavailyear
        
    output=output[str(firstyear):str(lastavailyear)]
    first_date=output.index[0].strftime("%Y%m")
        
        
    #defining file names
    #rawfile=Path(_downloadsdir,"{}_{}-{}.txt".format(_indexcode, first_date, last_date))
    outfile=Path(_downloadsdir,"{}_{}-{}.csv".format(_indexcode, first_date, last_date))
    
    if _overwrite is False:
        if os.path.exists(outfile):
            showMessage("file {} exists, and overwrite is OFF. Skipping...".format(outfile),"NONCRITICAL")
            return
          
    # on successful response - writing raw file
    #with open(rawfile, "w") as outf:
    #    outf.write(response.text)
    #showMessage("saved raw data to {}".format(rawfile), "SUCCESS")

    #saving file to csv
    output.to_csv(outfile)
    showMessage("saved csv data to {}".format(outfile), "SUCCESS")

            
            
            
def populateGui():
    
    gl.window.comboBox1_var.clear()
    gl.window.comboBox1_var.addItem("", "")
    for key, value in predictandSources.items():
        gl.window.comboBox1_var.addItem(value[0], key)
        
    gl.window.comboBox2_var.clear()
    gl.window.comboBox2_var.addItem("", "")
    for key, value in predictorSources.items():
        gl.window.comboBox2_var.addItem(value[0], key)
        
    gl.window.comboBox3_var.clear()
    gl.window.comboBox3_var.addItem("", "")
    for key, value in fcstpredSources.items():
        gl.window.comboBox3_var.addItem(value[0], key)
    
    gl.window.comboBox4_var.clear()
    gl.window.comboBox4_var.addItem("", "")
    for key, value in indexSources.items():
        gl.window.comboBox4_var.addItem(value[0], key)

    gl.window.comboBox_tgtseas.clear()
    gl.window.comboBox_tgtseas.addItem("", "")
    for key in seasons:
        gl.window.comboBox_tgtseas.addItem(key, key)
    
    gl.window.comboBox_srcmon.clear()
    gl.window.comboBox_srcmon.addItem("", "")
    for key in months:
        gl.window.comboBox_srcmon.addItem(key, key)
        
    gl.window.lineEditDirectory.setText(gl.config['downloadDir'])
    gl.window.lineEdit_tgtyear.setText(str(gl.config['fcstTargetYear']))
    gl.window.comboBox_tgtseas.setCurrentText(gl.config['fcstTargetSeas'])
    gl.window.lineEdit_srcyear.setText(str(gl.config['predictorYear']))
    gl.window.lineEdit_firstyear.setText(str(gl.config['firstDataYear']))
    gl.window.comboBox_srcmon.setCurrentText(gl.config['predictorMonth'])
    gl.window.lineEdit1_minlat.setText(str(gl.config['predictandMinLat']))
    gl.window.lineEdit1_minlon.setText(str(gl.config['predictandMinLon']))
    gl.window.lineEdit1_maxlat.setText(str(gl.config['predictandMaxLat']))
    gl.window.lineEdit1_maxlon.setText(str(gl.config['predictandMaxLon']))
    gl.window.lineEdit2_minlat.setText(str(gl.config['predictorMinLat']))
    gl.window.lineEdit2_minlon.setText(str(gl.config['predictorMinLon']))
    gl.window.lineEdit2_maxlat.setText(str(gl.config['predictorMaxLat']))
    gl.window.lineEdit2_maxlon.setText(str(gl.config['predictorMaxLon']))
    gl.window.lineEdit3_minlat.setText(str(gl.config['fcstpredMinLat']))
    gl.window.lineEdit3_minlon.setText(str(gl.config['fcstpredMinLon']))
    gl.window.lineEdit3_maxlat.setText(str(gl.config['fcstpredMaxLat']))
    gl.window.lineEdit3_maxlon.setText(str(gl.config['fcstpredMaxLon']))

    
def makeConfig():
    gl.config={}

    gl.config['downloadDir']="../test_data"
    gl.config['predictorMonth'] = "Jun"
    gl.config['predictorYear'] = 2025
    gl.config['fcstTargetSeas']="Dec"
    gl.config['fcstTargetYear']=2025
    
    gl.config['firstDataYear']=1981

    gl.config['predictandCode']=""
    gl.config['predictandOverwrite']=False
    gl.config['predictandMinLat']=-34
    gl.config['predictandMaxLat']=-30
    gl.config['predictandMinLon']=19
    gl.config['predictandMaxLon']=22

    gl.config['predictorCode']=""
    gl.config['predictorOverwrite']=False
    gl.config['predictorMinLat']=-60
    gl.config['predictorMaxLat']=60
    gl.config['predictorMinLon']=-180
    gl.config['predictorMaxLon']=180

    gl.config['fcstpredCode']=""
    gl.config['fcstpredOverwrite']=False
    gl.config['fcstpredMinLat']=-60
    gl.config['fcstpredMaxLat']=60
    gl.config['fcstpredMinLon']=-180
    gl.config['fcstpredMaxLon']=180

    gl.config['indexCode']=""
    gl.config['indexOverwrite']=False
    
def saveConfig():
    #defined parameters/variables
    with open(gl.configFile, "w") as f:
        json.dump(gl.config, f, indent=4)
        showMessage("saved config to: {}".format(gl.configFile), "INFO")   
        
        
def readGui():

    gl.config['downloadDir']=gl.window.lineEditDirectory.text()
        
    gl.config['predictorMonth'] = gl.window.comboBox_srcmon.currentData()
    gl.config['predictorYear'] = gl.window.lineEdit_srcyear.text()
    gl.config['fcstTargetSeas']=gl.window.comboBox_tgtseas.currentData()
    gl.config['fcstTargetYear']=gl.window.lineEdit_tgtyear.text()
    gl.config['firstDataYear']=gl.window.lineEdit_firstyear.text()

    gl.config['predictandCode']=gl.window.comboBox1_var.currentData()
    gl.config['predictandOverwrite']=gl.window.checkBox1_overwrite.isChecked()
    gl.config['predictandMinLat']=gl.window.lineEdit1_minlat.text()
    gl.config['predictandMaxLat']=gl.window.lineEdit1_maxlat.text()
    gl.config['predictandMinLon']=gl.window.lineEdit1_minlon.text()
    gl.config['predictandMaxLon']=gl.window.lineEdit1_maxlon.text()

    gl.config['predictorCode']=gl.window.comboBox2_var.currentData()
    gl.config['predictorOverwrite']=gl.window.checkBox2_overwrite.isChecked()
    gl.config['predictorMinLat']=gl.window.lineEdit2_minlat.text()
    gl.config['predictorMaxLat']=gl.window.lineEdit2_maxlat.text()
    gl.config['predictorMinLon']=gl.window.lineEdit2_minlon.text()
    gl.config['predictorMaxLon']=gl.window.lineEdit2_maxlon.text()

    gl.config['fcstpredCode']=gl.window.comboBox3_var.currentData()
    gl.config['fcstpredOverwrite']=gl.window.checkBox3_overwrite.isChecked()
    gl.config['fcstpredMinLat']=gl.window.lineEdit3_minlat.text()
    gl.config['fcstpredMaxLat']=gl.window.lineEdit3_maxlat.text()
    gl.config['fcstpredMinLon']=gl.window.lineEdit3_minlon.text()
    gl.config['fcstpredMaxLon']=gl.window.lineEdit3_maxlon.text()
    
    gl.config['indexCode']=gl.window.comboBox4_var.currentData()
    gl.config['indexOverwrite']=gl.window.checkBox4_overwrite.isChecked()
    
    