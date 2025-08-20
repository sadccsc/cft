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

msgColors={"ERROR": "red",
           "INFO":"blue",
           "RUNTIME":"grey",
           "NONCRITICAL":"red",
           "SUCCESS":"green"
          }

tgtSeass=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan-Mar","Feb-Apr","Mar-May","Apr-Jun","May-Jul","Jun-Aug","Jul-Sep","Aug-Oct","Sep-Nov","Oct-Dec","Nov-Jan","Dec-Feb"]

srcMons=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
          
indexSources={
"IOD_JMA": ["IOD (Dipole Mode Index) from JMA", "https://ds.data.jma.go.jp/tcc/tcc/products/elnino/index/sstindex/base_period_9120/DMI/anomaly"],
"Nino3_JMA":["Nino3 from JMA","https://ds.data.jma.go.jp/tcc/tcc/products/elnino/index/sstindex/base_period_9120/Nino_3/anomaly"],
"Nino4_JMA": ["Nino4 from JMA","https://ds.data.jma.go.jp/tcc/tcc/products/elnino/index/sstindex/base_period_9120/Nino_4/anomaly"]
}

predictandSources={
"PRCP_CHIRPSp25_IRIDL":["CHIRPS 0.25 deg rainfall from IRI data library",
                     "https://iridl.ldeo.columbia.edu/SOURCES/.UCSB/.CHIRPS/.v2p0/.daily-improved/.global/.0p25/.prcp/{}/mul/T/(1 Jan {})/(31 Dec {})/RANGE/T/({} {}-{})/seasonalAverage/Y/({})/({})/RANGEEDGES/X/({})/({})/RANGEEDGES/-999/setmissing_value/data.nc", "sum"],
}

predictorSources={
"SST_ERSSTv5_IRIDL":["Sea Surface temperature ERSST v5",
                         "http://iridl.ldeo.columbia.edu/SOURCES/.NOAA/.NCDC/.ERSST/.version5/.sst/T/(Jan 1979)/(Dec {})/RANGE/T/({} {}-{})/VALUES/T/12/STEP/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc"],
}

fcstpredSources={
    "SST_GEOSS2S_IRIDL": ["SST forecasted by GEOSS2S (NASA)", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.NASA-GEOSS2S/.HINDCAST/.MONTHLY/.sst/[M]/average/SOURCES/.Models/.NMME/.NASA-GEOSS2S/.FORECAST/.MONTHLY/.sst/[M]/average/appendstream/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc"],
    "SST_CanSIPS-IC4_IRIDL": ["SST forecasted by CanSIPS-IC4", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.CanSIPS-IC4/.HINDCAST/.MONTHLY/.sst/[M]/average/SOURCES/.Models/.NMME/.CanSIPS-IC4/.FORECAST/.MONTHLY/.sst/[M]/average/appendstream/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc"],
    "SST_CCSM4_IRIDL": ["SST forecasted by COLA-RSMAS-CCSM4", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.COLA-RSMAS-CCSM4/.MONTHLY/.sst/[M]/average/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc"],
    "SST_CFSv2_IRIDL": ["SST forecasted by CFSv2 (NCEP)", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.NCEP-CFSv2/.HINDCAST/.PENTAD_SAMPLES_FULL/.sst/[M]/average/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc"],
    "PRCP_GEOSS2S_IRIDL": ["Rainfall forecasted by GEOSS2S (NASA)", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.NASA-GEOSS2S/.HINDCAST/.MONTHLY/.prec/[M]/average/SOURCES/.Models/.NMME/.NASA-GEOSS2S/.FORECAST/.MONTHLY/.prec/[M]/average/appendstream/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc"],
    "PRCP_CanSIPS-IC4_IRIDL": ["Rainfall forecasted by CanSIPS-IC4", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.CanSIPS-IC4/.HINDCAST/.MONTHLY/.prec/[M]/average/SOURCES/.Models/.NMME/.CanSIPS-IC4/.FORECAST/.MONTHLY/.prec/[M]/average/appendstream/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc"],
    "PRCP_CCSM4_IRIDL": ["Rainfall forecasted by COLA-RSMAS-CCSM4", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.COLA-RSMAS-CCSM4/.MONTHLY/.prec/[M]/average/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc"],
    "PRCP_CFSv2_IRIDL": ["Rainfall forecasted by CFSv2 (NCEP)", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.NCEP-CFSv2/.HINDCAST/.PENTAD_SAMPLES_FULL/.prec/[M]/average/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc"],
    "z500_GEOSS2S_IRIDL": ["z500 forecasted by GEOSS2S (NASA)", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.NASA-GEOSS2S/.HINDCAST/.MONTHLY/.h500/[M]/average/SOURCES/.Models/.NMME/.NASA-GEOSS2S/.FORECAST/.MONTHLY/.h500/[M]/average/appendstream/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc"],
    "z500_CanSIPS-IC4_IRIDL": ["z500 forecasted by CanSIPS-IC4", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.CanSIPS-IC4/.HINDCAST/.MONTHLY/.hgt/[M]/average/SOURCES/.Models/.NMME/.CanSIPS-IC4/.FORECAST/.MONTHLY/.hgt/[M]/average/appendstream/P/500/500/RANGEEDGES/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc"],
    "z200_CCSM4_IRIDL": ["z200 forecasted by COLA-RSMAS-CCSM4", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.COLA-RSMAS-CCSM4/.MONTHLY/.gz/[M]/average/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc"],
    "z200_CFSv2_IRIDL": ["z200 forecasted by CFSv2 (NCEP)", "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.NCEP-CFSv2/.HINDCAST/.PENTAD_SAMPLES_FULL/.hgt/[M]/average/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc"],
}
#    "SST_SEAS51_IRIDL": ["SST forecasted by SEAS51 (ECMWF)", "https://iridl.ldeo.columbia.edu/SOURCES/.EU/.Copernicus/.CDS/.C3S/.ECMWF/.SEAS51_iri2/.hindcast/.sst/[M]/average/SOURCES/.EU/.Copernicus/.CDS/.C3S/.ECMWF/.SEAS51_iri2/.forecast/.sst/[M]/average/appendstream/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc"],
#    "SST_GCFS2p2_IRIDL": ["SST forecasted by GCFS2p2 (DWD)", "https://iridl.ldeo.columbia.edu/SOURCES/.EU/.Copernicus/.CDS/.C3S/.DWD/.GCFS2p2/.hindcast/.sst/[M]/average/SOURCES/.EU/.Copernicus/.CDS/.C3S/.DWD/.GCFS2p2/.forecast/.sst/[M]/average/appendstream/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc"],
#    "SST_CPS3_IRIDL": ["SST forecasted by CPS3 (JMA)", "https://iridl.ldeo.columbia.edu/SOURCES/.EU/.Copernicus/.CDS/.C3S/.JMA/.CPS3/.hindcast/.sst/[M]/average/SOURCES/.EU/.Copernicus/.CDS/.C3S/.JMA/.CPS3/.forecast/.sst/[M]/average/appendstream/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc"],
#    "SST_System9_IRIDL": ["SST forecasted by System9 (MeteoFrance)", "https://iridl.ldeo.columbia.edu/SOURCES/.EU/.Copernicus/.CDS/.C3S/.Meteo_France/.System9/.hindcast/.sst/[M]/average/SOURCES/.EU/.Copernicus/.CDS/.C3S/.Meteo_France/.System9/.forecast/.sst/[M]/average/appendstream/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc"],
#    "SST_SPSv4_IRIDL": ["SST forecasted by SPSv4 (CMCC)", "https://iridl.ldeo.columbia.edu/SOURCES/.EU/.Copernicus/.CDS/.C3S/.CMCC/.SPSv4/.hindcast/.sst/[M]/average/SOURCES/.EU/.Copernicus/.CDS/.C3S/.CMCC/.SPSv4/.forecast/.sst/[M]/average/appendstream/S/(0000 1 {} {}-{})/VALUES/L/{}/{}/RANGEEDGES/[L]//keepgrids/average/Y/{}/{}/RANGEEDGES/X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc"],           

#GFDL-SPEAR - ending in July 2025

def showMessage_print(_message, _type="RUNTIME"):
    #this print messages to log window, which are generated outside of the threaded function
    print(_message)

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
    return (np.where(np.array(srcMons)==_str)[0][0])+1  

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

    
def downloadPredictand():
    #read data from gui
    _predictandcode=gl.window.comboBox1_var.currentData()
    _overwrite=gl.window.checkBox1_overwrite.isChecked()
    _predictandyear=gl.window.lineEdit_tgtyear.text()
    _predictandseas=gl.window.comboBox_tgtseas.currentData()    
    south=gl.window.lineEdit1_minlat.text()
    north=gl.window.lineEdit1_maxlat.text()
    west=gl.window.lineEdit1_minlon.text()
    east=gl.window.lineEdit1_maxlon.text()
    
    _downloadsdir=gl.window.lineEditDirectory.text()
    
    if not os.path.exists(_downloadsdir):
        showMessage("output directory {} does not exist. creating...".format(_downloadsdir))
        os.makedirs(downloadsdir)
        showMessage("done")
    
    if _predictandcode=="":
        showMessage("\nplease select variable to download", "ERROR")
        return

    if _predictandyear=="":
        showMessage("\nplease provide predicand's year", "ERROR")
        return
    
    if _predictandseas=="":
        showMessage("\nplease provide predictand's season", "ERROR")
        return

    showMessage_print("\ndownloading {}".format(_predictandcode))

    
    #simply - monthly target will have three letters, seasonal target - 7
    temporalaggregation=predictandSources[_predictandcode][2]
    
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

    _source=_predictandcode.split("-")[-1]
    
    if _source=="IRIDL":

        #defined internally, can be included in the variable-source dictionary
        firstyear=1981
        firstmonth=_predictandseas[0:3]
        first_date=pd.to_datetime("01 {} {}".format(firstmonth, firstyear))
        
        finalyear=_predictandyear
        finalmonth=_predictandseas[-3:]
        
        last_date=pd.to_datetime("01 {} {}".format(finalmonth, finalyear))
        
        
        daterange="{}{}-{}{}".format(_predictandseas[0:3],firstyear, _predictandseas[-3:], finalyear)
        showMessage("requesting date range: {}".format(daterange))

        
        outfile=Path("{}","{}_{}_{}-{}.nc".format(_downloadsdir,_predictandcode, basetime, first_date.strftime("%Y%m"), last_date.strftime("%Y%m")))
        
        if _overwrite is False:
            if os.path.exists(outfile):
                showMessage("file {} exists, and overwrite is OFF. Skipping...".format(outfile),"NONCRITICAL")
                return
        
        url=predictandSources[_predictandcode][1]
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
    

        
def downloadIndexPredictor():
#def downloadIndex(_indexcode, _url, _downloadsdir, _predictordate, _overwrite=False):
    #read data from gui
    _indexcode=gl.window.comboBox4_var.currentData()
    _overwrite=gl.window.checkBox4_overwrite.isChecked()
    _predictoryear=gl.window.lineEdit_srcyear.text()
    _predictormonth=gl.window.comboBox_srcmon.currentData()    
    _predictordate=pd.to_datetime("01 {} {}".format(_predictormonth, _predictoryear))+pd.offsets.MonthEnd()
    
    _downloadsdir=gl.window.lineEditDirectory.text()
    
    if not os.path.exists(_downloadsdir):
        showMessage("output directory {} does not exist. creating...".format(_downloadsdir))
        os.makedirs(downloadsdir)
        showMessage("done")
    
    if _indexcode=="":
        showMessage("\nplease select variable to download", "ERROR")
        return

    if _predictoryear=="":
        showMessage("\nplease provide predictor's year", "ERROR")
        return
    
    if _predictormonth=="":
        showMessage("\nplease provide predictor's month", "ERROR")
        return

    showMessage_print("\ndownloading {}".format(_indexcode))

    _url=indexSources[_indexcode][1]
    
    #requesting data
    response=downloadUrl(_url)
    
    _source=_indexcode.split("_")[-1]

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
    showMessage("downloaded data covers the period of {} to {}".format(first_date, last_date))

    showMessage("checking if predictor date {} in data...".format(_predictordate.strftime("%b %Y")))
    if not _predictordate in output.index:
        showMessage("predictor date {} not in data!".format(_predictordate.strftime("%b %Y")),"NONCRITICAL")
          
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

    
    
    
    
    
def downloadGriddedPredictor():
    #read data from gui
    _predictorcode=gl.window.comboBox2_var.currentData()
    _overwrite=gl.window.checkBox2_overwrite.isChecked()
    _predictoryear=gl.window.lineEdit_srcyear.text()
    _predictormon=gl.window.comboBox_srcmon.currentData()    
    south=gl.window.lineEdit2_minlat.text()
    north=gl.window.lineEdit2_maxlat.text()
    west=gl.window.lineEdit2_minlon.text()
    east=gl.window.lineEdit2_maxlon.text()
    
    for _x in [south,north,west,east]:
        if _x=="":
            showMessage("\nplease define coordinates of requested domain", "ERROR")
            return
        
    _downloadsdir=gl.window.lineEditDirectory.text()
    
    if not os.path.exists(_downloadsdir):
        showMessage("output directory {} does not exist. creating...".format(_downloadsdir))
        os.makedirs(downloadsdir)
        showMessage("done")
    
    if _predictorcode=="":
        showMessage("\nplease select variable to download", "ERROR")
        return

    if _predictoryear=="":
        showMessage("\nplease provide predictor's year", "ERROR")
        return
    
    if _predictormon=="":
        showMessage("\nplease provide predictor's month", "ERROR")
        return
    
    

    showMessage("\ndownloading {}".format(_predictorcode))
    
    _source=_predictorcode.split("_")[-1]
    
    #always
    basetime="mon"
    
    if _source=="IRIDL":

        #defined internally, can be included in the variable-source dictionary
        firstyear=1981
        firstmonth=_predictormon
        first_date=pd.to_datetime("01 {} {}".format(firstmonth, firstyear))
        
        lastyear=_predictoryear
        lastmonth=_predictormon
        
        last_date=pd.to_datetime("01 {} {}".format(lastmonth, lastyear))
        
        
        daterange="{}{}-{}{}".format(_predictormon,firstyear, _predictormon, lastyear)
        showMessage("requesting date range: {}".format(daterange))

        
        outfile="{}/{}_{}_{}-{}.nc".format(_downloadsdir,_predictorcode, basetime, first_date.strftime("%Y%m"), last_date.strftime("%Y%m"))
        
        if _overwrite is False:
            if os.path.exists(outfile):
                showMessage("file {} exists, and overwrite is OFF. Skipping...".format(outfile),"NONCRITICAL")
                return

        #"http://iridl.ldeo.columbia.edu/SOURCES/.NOAA/.NCDC/.ERSST/.version5/.sst/T/
        # (Jan 1982)/(Dec 2021)/RANGE/T/({} {}-{})/VALUES/T/12/STEP/Y/{}/{}/RANGEEDGES/
        # X/{}/{}/RANGEEDGES/-999/setmissing_value/data.nc"
        url=predictorSources[_predictorcode][1]
        url=url.format(lastyear, _predictormon, firstyear, lastyear, south,north,west,east)

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
            print(lastdatadate, last_date)
            if lastdatadate<last_date:
                showMessage("Downloaded data contains data till {}, and thus does not fully cover the the requested period {}".format(last_date.strftime("%b %Y"), daterange), "NONCRITICAL")
            else:
                showMessage("All fine", "NONCRITICAL")
                
            # on successful response - writing raw file
            with open(outfile, "wb") as outf:
                outf.write(response.content)
            showMessage("Saved downloaded data to {}".format(outfile), "SUCCESS")
            
        
def downloadFcstPredictor():
    #read data from gui
    _predictorcode=gl.window.comboBox3_var.currentData()
    _overwrite=gl.window.checkBox3_overwrite.isChecked()
    _predictoryear=gl.window.lineEdit_srcyear.text()
    _predictormon=gl.window.comboBox_srcmon.currentData()
    
    _predictortime=pd.to_datetime("{}-{}-01".format(_predictoryear, _predictormon))

    _forecasttime=_predictortime+pd.offsets.MonthBegin(1)
    _forecastyear=_forecasttime.year
    _forecastmon=srcMons[_forecasttime.month-1]
    
    south=gl.window.lineEdit3_minlat.text()
    north=gl.window.lineEdit3_maxlat.text()
    west=gl.window.lineEdit3_minlon.text()
    east=gl.window.lineEdit3_maxlon.text()

    for _x in [south,north,west,east]:
        if _x=="":
            showMessage("\nplease define coordinates of requested domain", "ERROR")
            return
        
    _downloadsdir=gl.window.lineEditDirectory.text()
    
    if not os.path.exists(_downloadsdir):
        showMessage("output directory {} does not exist. creating...".format(_downloadsdir))
        os.makedirs(downloadsdir)
        showMessage("done")
    
    if _predictorcode=="":
        showMessage("\nplease select variable to download", "ERROR")
        return

    if _predictoryear=="":
        showMessage("\nplease provide predictor's year", "ERROR")
        return
    
    if _predictormon=="":
        showMessage("\nplease provide predictor's month", "ERROR")
        return
    
    

    showMessage("\ndownloading {}".format(_predictorcode))
    
    _source=_predictorcode.split("_")[-1]
    
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
        firstyear=1980
        firstmonth=_predictormon
        first_date=pd.to_datetime("01 {} {}".format(firstmonth, firstyear))

        lastyear=_predictoryear
        lastmonth=_predictormon

        last_date=pd.to_datetime("01 {} {}".format(lastmonth, lastyear))


        daterange="{}{}-{}{}".format(_predictormon,firstyear, _predictormon, lastyear)
        showMessage("requesting date range: {}".format(daterange))


        outfile="{}/{}_{}_{}-{}.nc".format(_downloadsdir,_predictorcode, basetime, first_date.strftime("%Y%m"), last_date.strftime("%Y%m"))

        if _overwrite is False:
            if os.path.exists(outfile):
                showMessage("file {} exists, and overwrite is OFF. Skipping...".format(outfile),"NONCRITICAL")
                return

        url=fcstpredSources[_predictorcode][1]
        url=url.format(_forecastmon, firstyear, _forecastyear,leadtimestart,leadtimeend,south,north,west,east)
        showMessage(url)

        response=downloadUrl(url)

        if response is None:
            showMessage("failed to download forecast data")
            return
        else:

            data_stream = io.BytesIO(response.content)

            # Open with xarray 
            # chunks argument prevents error with time conversion, requires dask to be installed, though
            ds = xr.open_dataset(data_stream, decode_times=False, chunks={})

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
            print(lastdatatime, _predictortime, firstdatatime)
            if _predictortime !=lastdatatime:
                showMessage("Downloaded data contains data till {}, and thus does not include data required for forecast, i.e. for {}".format(lastdatatime.strftime("%b %Y"), _predictortime.strftime("%b %Y")), "ERROR")
                return
            else:
                showMessage("All fine", "NONCRITICAL")
                
            # on successful response - writing file
            ds.to_netcdf(outfile)
            showMessage("Saved downloaded data to {}".format(outfile), "SUCCESS")
            
            
class Worker(QtCore.QThread):
    log = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal()

    def __init__(self, task_function, *args, **kwargs):
        super().__init__()
        self.task_function = task_function
        self.args = args
        self.kwargs = kwargs

    def run(self):
        """Run the provided function in a thread and emit logs."""
        try:
            self.log.emit("Task started...")
            # Run the task
            self.task_function(*self.args, **self.kwargs)
            self.log.emit("Task finished successfully.")
        except Exception as e:
            tb = traceback.format_exc()
            self.log.emit(f"Error occurred:\n{tb}")
            #self.log.emit(f"Error: {e}")
        finally:
            self.finished.emit()

class MainWindow(QtWidgets.QMainWindow):
    log_signal = QtCore.pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        uic.loadUi("download.ui", self)
        
        
        # Collect buttons
        self.buttons = [self.button1_run]

        # Connect signals
        self.button1_run.clicked.connect(lambda: self.start_task(downloadPredictand))
        self.button2_run.clicked.connect(lambda: self.start_task(downloadGriddedPredictor))
        self.button3_run.clicked.connect(lambda: self.start_task(downloadFcstPredictor))
        self.button4_run.clicked.connect(lambda: self.start_task(downloadIndexPredictor))
        self.clearLogButton.clicked.connect(self.logWindow.clear)
        
        self.log_signal.connect(self.logWindow.appendHtml)
        
        # Set up collapsible groupBox and connect its checkbox signal
        def setup_collapsible(group_box):
            group_box.toggled.connect(
                lambda checked, box=group_box: (
                    [child.setVisible(checked) 
                     for child in box.findChildren(QtWidgets.QWidget) if child is not box]
                )
            )
                        
        for gB in [self.groupBox1, self.groupBox2, self.groupBox4, self.groupBox3]:
            setup_collapsible(gB)
            
        # collapsing
        for gB in [self.groupBox2, self.groupBox4, self.groupBox1]:
            for child in gB.findChildren(QtWidgets.QWidget):
                if child is not gB:
                    child.setVisible(False)
                    
        #file/directory browser
        self.browseButton.clicked.connect(self.browse_directory)

    # ---------- Thread Handling ----------
    def start_task(self, func):
        """Start a task in a background thread and disable buttons."""
        self.set_buttons_enabled(False)
        self.worker = Worker(func)
        self.worker.log.connect(self.logWindow.appendHtml)
        self.worker.finished.connect(lambda: self.set_buttons_enabled(True))
        self.worker.start()

    def set_buttons_enabled(self, enabled: bool):
        for btn in self.buttons:
            btn.setEnabled(enabled)

    def browse_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory", "")
        if dir_path:
            self.lineEditDirectory.setText(dir_path)
            
    def log(self, message):
        # safe to call from any thread
        self.log_signal.emit(message)            
            
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    gl.window = MainWindow()
    gl.window.show()

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
    for key in tgtSeass:
        gl.window.comboBox_tgtseas.addItem(key, key)
    
    gl.window.comboBox_srcmon.clear()
    gl.window.comboBox_srcmon.addItem("", "")
    for key in srcMons:
        gl.window.comboBox_srcmon.addItem(key, key)
    
    
gl.config={}
gl.config['downloadDir']="../test_data"
gl.config['predictorMonth'] = "Jun"
gl.config['predictorYear'] = 2025
gl.config['fcstTargetSeas']="Dec"
gl.config['fcstTargetYear']=2025

gl.config['predictandMinLat']=-34
gl.config['predictandMaxLat']=-30
gl.config['predictandMinLon']=19
gl.config['predictandMaxLon']=22

gl.config['predictorMinLat']=-60
gl.config['predictorMaxLat']=60
gl.config['predictorMinLon']=-180
gl.config['predictorMaxLon']=180

gl.config['fcstpredMinLat']=-60
gl.config['fcstpredMaxLat']=60
gl.config['fcstpredMinLon']=-180
gl.config['fcstpredMaxLon']=180

gl.maxLeadTime=6
    
def populateGui():
    gl.window.lineEditDirectory.setText(gl.config['downloadDir'])
    gl.window.lineEdit_tgtyear.setText(str(gl.config['fcstTargetYear']))
    gl.window.comboBox_tgtseas.setCurrentText(gl.config['fcstTargetSeas'])
    gl.window.lineEdit_srcyear.setText(str(gl.config['predictorYear']))
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
    
populateGui()

sys.exit(app.exec_())
