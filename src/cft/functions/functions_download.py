import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import requests
import json,os, sys, glob, datetime
from cft import gl
import xarray as xr
import datetime
import io

import sys
import time

from cftime import num2date
import traceback
from pathlib import Path
import logging

msgColors={"ERROR": "red",
           "INFO":"blue",
           "RUNTIME":"grey",
           "NONCRITICAL":"red",
           "SUCCESS":"green"
          }

seasons=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan-Mar","Feb-Apr","Mar-May","Apr-Jun","May-Jul","Jun-Aug","Jul-Sep","Aug-Oct","Sep-Nov","Oct-Dec","Nov-Jan","Dec-Feb"]

seasonmonths={
    "Jan":[1],
    "Feb":[2],
    "Mar":[3],
    "Apr":[4],
    "May":[5],
    "Jun":[6],
    "Jul":[7],
    "Aug":[8],
    "Sep":[9],
    "Oct":[10],
    "Nov":[11],
    "Dec":[12],
    "Jan-Mar":[1,2,3],
    "Feb-Apr":[2,3,4],
    "Mar-May":[3,4,5],
    "Apr-Jun":[4,5,6],
    "May-Jul":[5,6,7],
    "Jun-Aug":[6,7,8],
    "Jul-Sep":[7,8,9],
    "Aug-Oct":[8,9,10],
    "Sep-Nov":[9,10,11],
    "Oct-Dec":[10,11,12],
    "Nov-Jan":[11,12,1],
    "Dec-Feb":[12,1,2]
}

monthNames = np.array(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])



def showMessage(message, msgType="RUNTIME"):
    #this print messages to log window, which are generated outside of the threaded function
    color=msgColors[msgType]
    message = "<pre><font color={}>{}</font></pre>".format(color, message)
    gl.window.log(message)


    
def downloadUrl(url, timeout=60):
    #requesting data
    showMessage("waiting for:\n{}".format(url))
    
    try:
        response=requests.get(url, timeout=(10,None))
        # If it returns a response object, you can also check:
        # response.raise_for_status()  # raises error for HTTP 4xx/5xx
        return response
    except requests.exceptions.Timeout:
        showMessage(f"Timeout error while downloading: {url}", "ERROR")
    except requests.exceptions.ConnectionError:
        showMessage(f"Connection error while downloading: {url}. Are you connected to internet?", "ERROR")
    except requests.exceptions.HTTPError as e:
        showMessage(f"HTTP error {e.response.status_code} while downloading: {url}", "ERROR")
    except requests.exceptions.RequestException as e:
        showMessage(f"General request error: {e}", "ERROR")
    return False



    
def month2int(s):
    #converts month string to non-pythonic integer month number
    return (np.where(np.array(monthNames)==s)[0][0])+1  




def isNumber(s):
    try:
        float(s)
        return True
    except ValueError:
        return False



class GuiLogHandler(logging.Handler):
    #forwards Python logging output to the GUI log window via showMessage,
    #instead of it printing straight to the terminal (e.g. cdsapi's request/queue/download status messages)
    def emit(self, record):
        try:
            msg=self.format(record)
        except Exception:
            msg=record.getMessage()
        if record.levelno>=logging.ERROR:
            msgType="ERROR"
        elif record.levelno>=logging.WARNING:
            msgType="NONCRITICAL"
        else:
            msgType="INFO"
        showMessage(msg, msgType)

_guiLogHandlerInstalled=False



def installGuiLogHandler():
    #routes Python's logging output (including cdsapi's own status messages, which otherwise
    #print straight to the terminal) through showMessage() instead. Safe to call more than once.
    global _guiLogHandlerInstalled
    if _guiLogHandlerInstalled:
        return
    rootLogger=logging.getLogger()
    handler=GuiLogHandler()
    handler.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
    rootLogger.addHandler(handler)
    rootLogger.setLevel(logging.INFO)
    _guiLogHandlerInstalled=True



def requireCdsapi():
    showMessage("checking if cdsapi available...")
    try:
        import cdsapi
        installGuiLogHandler()
        showMessage("cdsapi available")
        return cdsapi.Client()
    except Exception as exc:
        showMessage(
            "CDS downloads require the cdsapi package and a configured CDS API key. "
            "Install with: python -m pip install cdsapi. "
            "Then configure your CDS API credentials using the Copernicus CDS instructions. "
            "Original error: {}".format(exc),
            "ERROR",
        )
        return None



def cdsRetrieve(client, dataset, request, outfile):
    try:
        client.retrieve(dataset, request, str(outfile))
        return True
    except Exception as exc:
        showMessage(
            f"CDS request failed. This is likely an unavailable/restricted initialization date, invalid area selection, or CDS access limitation. Original error: {exc}\nCDS request:{request}, dataset:{dataset}",
            "ERROR",
        )
        return False


def availableDataYears(fYear, month, latency=35):
    #full month's data becomes available mid of the next month
    lastDate=pd.Timestamp.today()-pd.offsets.Day(latency)
    #use whichever is later: the year data first became available, or the year the user requested
    dates=pd.date_range(f"01 {month} {fYear}", lastDate, freq="MS")
    dates=dates[dates.month==month]
    years=dates.year.values
    return years



def transformData(ds,transform):
    add,multiply,units,ncvar=transform
    da=ds[ncvar]
    da=(da*multiply)+add
    da.attrs["units"]=units
    ds=da.to_dataset(name=ncvar)
    return ds



def cdsDownloadReanalysis(client, dataset, productType, variable, transform, area, months, years, outfile):
    #builds and submits a CDS request across the given months/years, then verifies the result.
    #returns True on full success, False on any failure (CDS submission failed, or the
    #downloaded file could not be opened) - caller should stop in either case

    showMessage("creating cds request...")

    request = {
            "product_type": productType,
            "variable": variable,
            "year": [str(y) for y in years],
            "month": [str(m).zfill(2) for m in months],
            "time": "00:00",
            "area": area,
            "data_format": "netcdf",
            "download_format": "unarchived",
    }

    showMessage("Submitting request to CDS...")

    result=cdsRetrieve(client, dataset, request, outfile)

    if not result:
        return False

    showMessage("Download successful.", "SUCCESS")

    showMessage("Checking integrity of downloaded file...")

    try:
        ds=xr.open_dataset(outfile)
        showMessage("Downloaded file opens successfully.", "SUCCESS")
        ds.close()
        
        if len(transform)>0:
            print("transform", transform)
            ds=transformData(ds,transform)
            tmpfile = str(outfile) + ".tmp"
            ds.to_netcdf(tmpfile)
            ds.close()
            os.replace(tmpfile, outfile)   # atomic on POSIX and Windows
        else:
            ds.close()
                    
        return True

    except Exception as exc:
        showMessage(
            f" Downloaded file {outfile} cannot be opened. You might need to remove it and try downloading again. Original error: {exc}",
            "ERROR",
        )
        return False


def cdsDownloadForecast(client, dataset, originatingCentre, system, pressureLevel, variable, area, month, years, outfile):

    #builds and submits a CDS request for a single month across the given years, then verifies the result.
    #returns True on full success, False on any failure (CDS submission failed, or the
    #downloaded file could not be opened) - caller should stop in either case
    showMessage("creating cds request...")

    request = {
            "originating_centre": originatingCentre,
            "system": system,
            "variable": variable,
            "product_type": "monthly_mean",
            "year": [str(y) for y in years],
            "month": [str(month).zfill(2)],
            "leadtime_month": ["1","2","3","4","5","6"],
            "area": area,
            "data_format": "netcdf",
    }
    if pressureLevel:
        request["pressure_level"]=pressureLevel

    showMessage("Submitting request to CDS...")

    result=cdsRetrieve(client, dataset, request, outfile)

    if not result:
        return False

    showMessage("Download successful.", "SUCCESS")

    showMessage("Checking integrity of downloaded file...")
    try:
        ds=xr.open_dataset(outfile)
        ds.close()
        showMessage("Downloaded file opens successfully.", "SUCCESS")
        return True

    except Exception as exc:
        showMessage(
            f" Downloaded file {outfile} cannot be opened. You might need to remove it and try downloading again. Original error: {exc}",
            "ERROR",
        )
        return False



def areaTag(south, north, west, east):
    #compact, filename-safe encoding of a lat/lon box, so that locally cached files
    #downloaded for a different area are never mistaken for the requested one
    #each value gets its own hemisphere letter (S/N for latitude, W/E for longitude)
    #and is scaled to tenths of a degree so no decimal point is needed, e.g. -34.0 -> S340

    def latPart(v):
        v=float(v)
        return "{}{}".format("s" if v<0 else "n", round(abs(v)*10))
    def lonPart(v):
        v=float(v)
        return "{}{}".format("w" if v<0 else "e", round(abs(v)*10))
    return "{}{}{}{}".format(latPart(south), latPart(north), lonPart(west), lonPart(east))


def ensureDownloadsDir(downloadsDir):
    #makes sure the output directory exists, creating it if needed.
    #returns True if ready to proceed, False if it could not be created (message already shown)
    if os.path.exists(downloadsDir):
        return True
    showMessage("output directory {} does not exist. creating...".format(downloadsDir))
    try:
        os.makedirs(downloadsDir)
        showMessage("done")
        return True
    except Exception:
        showMessage("Output directory could not be created. Make sure that the directory is correctly defined and try again.", "ERROR")
        return False


def validateDomain(south, north, west, east):
    #checks that a lat/lon bounding box is complete, numeric, and correctly ordered.
    #returns True if valid, False otherwise (message already shown)
    for x in [south, north, west, east]:
        if x=="":
            showMessage("\nplease define coordinates of requested domain", "ERROR")
            return False
    if not all(isNumber(x) for x in [south, north, west, east]):
        showMessage("\nLat and Lon values should be numeric.", "ERROR")
        return False
    if not (float(north)>float(south) and float(east)>float(west)):
        showMessage("\nLat and Lon values should be numeric.", "ERROR")
        return False
    return True


def skipIfExists(outfile, overwrite):
    #returns True (caller should skip/return) if the file already exists and overwrite is off
    if overwrite is False and os.path.exists(outfile):
        showMessage("file {} exists, and overwrite is OFF. Skipping...".format(outfile),"NONCRITICAL")
        return True
    return False


def decodeIridlTime(ds, timevar):
    #IRIDL netcdf files encode time as days-since-a-reference-date with a named calendar;
    #this decodes that coordinate (e.g. 'T' for predictand/predictor, 'S' for forecast predictor)
    #into actual cftime dates
    timeRaw = ds[timevar].values
    units = ds[timevar].attrs.get('units', 'days since 1900-01-01')
    calendar = ds[timevar].attrs.get('calendar', 'standard')
    if calendar == '360':
        calendar = '360_day'
    return num2date(timeRaw, units=units, calendar=calendar)
    



    
def downloadPredictand():
    #read data from gui
    readGui()
    
    #save config to json file
    saveConfig()
    
    downloadsDir=gl.config['downloadDir']
   
    predictandCode=gl.config['predictandCode']
    overwrite=gl.config['predictandOverwrite']
    predictandSeas=gl.config['fcstTargetSeas']
    
    south=gl.config['predictandMinLat']
    north=gl.config['predictandMaxLat']
    west=gl.config['predictandMinLon']
    east=gl.config['predictandMaxLon']

    if not ensureDownloadsDir(downloadsDir):
        return

    if predictandCode=="":
        showMessage("\nplease select variable to download", "ERROR")
        return

    if predictandSeas=="":
        showMessage("\nplease provide predictand's season", "ERROR")
        return

    if not validateDomain(south, north, west, east):
        return

    showMessage("\ndownloading {}".format(predictandCode))
    
    
    source=predictandCode.split("_")[-1]

    #months needed for the requested predictand season, shared by both IRIDL and CDS branches
    months=seasonmonths[predictandSeas]
     
    area=[north, west, south, east]
    areaStr=areaTag(south, north, west, east)


    if source=="IRIDL":

        url=gl.predictandSources[predictandCode][1]
        
        temporalAggregation=gl.predictandSources[predictandCode][2]
        
        firstAvailYear=gl.predictandSources[predictandCode][3]
        
        availableYears=availableDataYears(int(firstAvailYear), months[-1])

        firstAvailYear=availableYears[0]
        lastAvailYear=availableYears[-1]

        #a single-month target has one entry in months, a seasonal target has several
        if len(months)==1:
            multiply=1
            baseTime="mon"
        else:
            baseTime="seas"
            multiply = 3 if temporalAggregation=="sum" else 1


        lastDate=pd.Timestamp(year=int(lastAvailYear), month=months[-1], day=1)
        
        
        dateRange="{}{}-{}{}".format(monthNames[months[0]-1],firstAvailYear, monthNames[months[-1]-1], lastAvailYear)
        showMessage("requesting date range: {}".format(dateRange))

        
        outfile=Path(downloadsDir,"{}_{}_{}_{}-{}.nc".format(predictandCode, predictandSeas, areaStr, firstAvailYear, lastAvailYear))

        if skipIfExists(outfile, overwrite):
            return

        url=url.format(multiply,firstAvailYear, lastAvailYear, predictandSeas, firstAvailYear, lastAvailYear, south,north,west,east)

        response=downloadUrl(url)
        
        if response is False:
            showMessage("failed to download data")
            return
        else:
            
            dataStream = io.BytesIO(response.content)

            # Open with xarray
            ds = xr.open_dataset(dataStream, decode_times=False)

            timeCftime = decodeIridlTime(ds, 'T')
            
            #iridl dates are mid of the season or mid month, aligning them with our notation
            #first month first year, and last month last year
            if baseTime=="seas":
                #back two months
                firstDataDate=pd.to_datetime("{}-{}-15".format(timeCftime[0].year, timeCftime[0].month))-pd.offsets.MonthBegin(2)
                #forward one month
                lastDataDate=pd.to_datetime("{}-{}-15".format(timeCftime[-1].year, timeCftime[-1].month))+pd.offsets.MonthBegin(1)
            else:
                #for montly data, it will be the first of the first month and the first of the last month
                firstDataDate=pd.to_datetime("{}-{}-15".format(timeCftime[0].year, timeCftime[0].month))-pd.offsets.MonthBegin()
                lastDataDate=pd.to_datetime("{}-{}-15".format(timeCftime[-1].year, timeCftime[-1].month))-pd.offsets.MonthBegin()
            
            if lastDataDate<lastDate:
                showMessage("Downloaded data contains data till {}, and thus does not fully cover the the requested period {}".format(lastDataDate.strftime("%b %Y"), dateRange), "NONCRITICAL")
                outfile=Path(downloadsDir,"{}_{}_{}_{}-{}.nc".format(predictandCode, gl.config['fcstTargetSeas'], areaStr, firstDataDate.strftime("%Y"), lastDataDate.strftime("%Y")))

            else:
                showMessage("All fine", "NONCRITICAL")
                
            # on successful response - writing raw file
            with open(outfile, "wb") as outf:
                outf.write(response.content)
            showMessage("Saved downloaded data to {}".format(outfile), "SUCCESS")


    elif source=="CDS":

        predictandTitle, predictandDataset, predictandProductType, predictandVariable, predictandAggregation, predictandTransform, firstAvailYear = gl.predictandSources[predictandCode]

        #checking if cds available
        client = requireCdsapi()
        if client is None:
            return



        availableYears=availableDataYears(int(firstAvailYear), months[-1], 40)

        firstAvailYear=availableYears[0]
        lastAvailYear=availableYears[-1]

        outfile=Path(f"{downloadsDir}/{predictandCode}_{predictandSeas}_{areaStr}_{firstAvailYear}-{lastAvailYear}.nc")

        if skipIfExists(outfile, overwrite):
            return

        print(client)
        print(predictandDataset)
        print(predictandProductType)
        print(predictandVariable)
        print(predictandTransform)
        print(area)
        print(months)
        print(availableYears)
        print(outfile)

        result=cdsDownloadReanalysis(client, predictandDataset, predictandProductType, predictandVariable, predictandTransform, area, months, availableYears, outfile)

        if result is False:
            return
    
    else:
        showMessage("\nSource {} not available. Exiting...".format(source), "ERROR")
        

    
    
    
    
    
def downloadGriddedPredictor():
    #read data from gui
    readGui()
    
    #save config to json file
    saveConfig()
    
    downloadsDir=gl.config['downloadDir']
   
    predictorCode=gl.config['predictorCode']
    overwrite=gl.config['predictorOverwrite']
    predictorYear=gl.config['predictorYear']
    predictorMonth=gl.config['predictorMonth']
    
    
    south=gl.config['predictorMinLat']
    north=gl.config['predictorMaxLat']
    west=gl.config['predictorMinLon']
    east=gl.config['predictorMaxLon']

    if not ensureDownloadsDir(downloadsDir):
        return

    if predictorCode=="":
        showMessage("\nplease select variable to download", "ERROR")
        return

    if predictorYear=="":
        showMessage("\nplease provide predictor's year", "ERROR")
        return
    
    if not isNumber(predictorYear):
        showMessage("\npredictor year should be numeric", "ERROR")
        return
    
    if predictorMonth=="":
        showMessage("\nplease provide predictor's month", "ERROR")
        return

    if not validateDomain(south, north, west, east):
        return

    #setting up domain string
    area=[north, west, south, east]
    areaStr=areaTag(south, north, west, east)


    showMessage("\ndownloading {}".format(predictorCode))
    
    source=predictorCode.split("_")[-1] 

    #the gridded predictor is always requested for a single month, never a season
    month=month2int(predictorMonth)
    monthName=monthNames[month-1]

    if source=="IRIDL":

        url=gl.obspredSources[predictorCode][1]

        firstAvailYear=gl.obspredSources[predictorCode][2]

        availableYears=availableDataYears(int(firstAvailYear), month, 40)

        if int(predictorYear)>availableYears[-1]:
             showMessage(f"Requested data will contain data till {availableYears[-1]}, and does not include data for {predictorYear}{predictorMonth}", "ERROR")
             return
 
        lastDate=pd.Timestamp(year=int(predictorYear), month=month, day=1)

        dateRange="{}{}-{}{}".format(monthName,firstAvailYear, monthName, predictorYear)
        showMessage("requesting date range: {}".format(dateRange))

        outfile=Path(downloadsDir,"{}_{}_{}_{}-{}.nc".format(predictorCode, monthName, areaStr, firstAvailYear, predictorYear))
        
        if skipIfExists(outfile, overwrite):
            return

        url=url.format(predictorMonth, firstAvailYear, predictorYear, south,north,west,east)

        response=downloadUrl(url)
        
        if response is False:
            showMessage("failed to download data")
            return
        else:
            
            dataStream = io.BytesIO(response.content)

            # Open with xarray
            ds = xr.open_dataset(dataStream, decode_times=False)

            timeCftime = decodeIridlTime(ds, 'T')

            #iridl dates are mid of the season or mid month, aligning them with our notation
            #first month first year, and last month last year
            firstDataDate=pd.to_datetime("{}-{}-15".format(timeCftime[0].year, timeCftime[0].month))
            lastDataDate=pd.to_datetime("{}-{}-15".format(timeCftime[-1].year, timeCftime[-1].month))

            if lastDataDate<lastDate:
                showMessage("Downloaded data contains data till {}, and thus does not fully cover the the requested period {}. Keeping file, adjusting its name...".format(lastDataDate.strftime("%b %Y"), dateRange), "NONCRITICAL")
                #adjusting outfile name
                outfile=Path(downloadsDir,"{}_{}_{}_{}-{}.nc".format(predictorCode, monthName, areaStr, firstDataDate.strftime("%Y"), lastDataDate.strftime("%Y")))
            else:
                showMessage("All fine", "NONCRITICAL")
                
            # on successful response - writing raw file
            with open(outfile, "wb") as outf:
                outf.write(response.content)
            showMessage("Saved downloaded data to {}".format(outfile), "SUCCESS")



    elif source=="CDS":

        predictorTitle, predictorDataset, predictorProductType, predictorVariable, predictorAggregation, predictorTransform, firstAvailYear = gl.obspredSources[predictorCode]


        #checking if cds available
        client = requireCdsapi()

        if client is None:
            return

        showMessage("checking if data available locally...")

        #data for given month available only after the 10th

        availableYears=availableDataYears(int(firstAvailYear), month, 40)

        if int(predictorYear)>availableYears[-1]:
             showMessage(f"Requested data will contain data till {availableYears[-1]}, and does not include data for {predictorYear}{predictorMonth}", "ERROR")
             return
        
        firstAvailYear=availableYears[0]
        lastAvailYear=availableYears[-1]
        outfile=Path(f"{downloadsDir}/{predictorCode}_{monthName}_{areaStr}_{firstAvailYear}-{lastAvailYear}.nc")

        if skipIfExists(outfile, overwrite):
            return

        result=cdsDownloadReanalysis(client, predictorDataset, predictorProductType, predictorVariable, predictorTransform, area, [month], availableYears, outfile)

        if result is False:
            return

    else:
        showMessage("\nSource {} not available. Exiting...".format(source), "ERROR")
        







def downloadFcstPredictor():
    
    readGui()
    
    #save config to json file
    saveConfig()
    
    downloadsDir=gl.config['downloadDir']
    
    predictorCode=gl.config['fcstpredCode']
    overwrite=gl.config['fcstpredOverwrite']
    predictorYear=gl.config['fcstpredYear']
    predictorMonth=gl.config['fcstpredMonth']
    
    
    south=gl.config['fcstpredMinLat']
    north=gl.config['fcstpredMaxLat']
    west=gl.config['fcstpredMinLon']
    east=gl.config['fcstpredMaxLon']
    
    
    if not ensureDownloadsDir(downloadsDir):
        return
    
    if predictorCode=="":
        showMessage("\nplease select variable to download", "ERROR")
        return

    if predictorYear=="":
        showMessage("\nplease provide predictor's year", "ERROR")
        return
    
    if not isNumber(predictorYear):
        showMessage("\npredictor year should be numeric", "ERROR")
        return
    
    if predictorMonth=="":
        showMessage("\nplease provide predictor's month", "ERROR")
        return

    if not validateDomain(south, north, west, east):
        return

    area=[north, west, south, east]
    areaStr=areaTag(south, north, west, east)


    showMessage("\ndownloading {}".format(predictorCode))
    
    source=predictorCode.split("_")[-1]
    
   
 
    #the gridded forecast predictor is always requested for a single month, never a season
    month=month2int(predictorMonth)
    monthName=monthNames[month-1]


    if source=="IRIDL":

        predictorDate=pd.to_datetime("{}-{}-15".format(predictorYear, predictorMonth))

        url=gl.fcstpredSources[predictorCode][1]
        firstAvailYear=gl.fcstpredSources[predictorCode][2]

        # this is just about password-free access to IRIDL data
        isAvailable=gl.fcstpredSources[predictorCode][3]
        if not isAvailable:
            showMessage("The data were not downloaded. To download these data from IRIDL, these data require one to sign a license and to log onto IRI server. To do so - copy the url below, paste it to your browser and this will bring you to the website where you can log in and sign the license\n{}".format(url), "ERROR")
            return
        

        availableYears=availableDataYears(int(firstAvailYear), month, 10)

        firstAvailYear=availableYears[0]
        
        if int(predictorYear)>availableYears[-1]:
             showMessage(f"Requested data will contain data till {availableYears[-1]}, and does not include data for {predictorYear}{predictorMonth}", "ERROR")
             return
 
        leadTimeStart=0.5
        leadTimeEnd=5.5

        dateRange="{}{}-{}{}".format(predictorMonth,firstAvailYear, predictorMonth, predictorYear)
        showMessage("requesting date range: {}".format(dateRange))

        outfile=Path(downloadsDir,"{}_{}_{}_{}-{}.nc".format(predictorCode, predictorMonth, areaStr, firstAvailYear, predictorYear))
        
        if skipIfExists(outfile, overwrite):
            return

        url=url.format(predictorMonth, firstAvailYear, predictorYear,leadTimeStart,leadTimeEnd,south,north,west,east)

          
        response=downloadUrl(url)

        if response is False:
            showMessage("failed to download forecast data")
            return

        else:

            dataStream = io.BytesIO(response.content)

            # Open with xarray 
            # chunks argument prevents error with time conversion, requires dask to be installed, though
            try:
                
                ds = xr.open_dataset(dataStream, decode_times=False, chunks={})
            except:
                showMessage("Could not read downloaded data. This might be a result of a temporary problem with IRIDL server. Wait a couple of minutes and re-download the data. If the same error occurs - copy and paste the following url into a browser to identify the problem: \n{}".format(url), "ERROR")
                return

            timeCftime = decodeIridlTime(ds, 'S')

            firstDataDate=pd.to_datetime("{}-{}-15".format(timeCftime[0].year, timeCftime[0].month))
            lastDataDate=pd.to_datetime("{}-{}-15".format(timeCftime[-1].year, timeCftime[-1].month))

            if predictorDate>lastDataDate:
                showMessage("Downloaded data contains data till {}, and thus does not include data required for forecast, i.e. for {}. Keeping file but renaming it...".format(lastDataDate.strftime("%b %Y"), predictorDate.strftime("%b %Y")), "ERROR")
                outfile=Path(downloadsDir,"{}_{}_{}_{}-{}.nc".format(predictorCode, predictorMonth, areaStr, firstDataDate.strftime("%Y"), lastDataDate.year))
                #return
            else:
                showMessage("All fine", "NONCRITICAL")
                
            # on successful response - writing file
            ds.to_netcdf(outfile)
            showMessage("Saved downloaded data to {}".format(outfile), "SUCCESS")

    elif source=="CDS":

        predictorTitle, predictorDataset, predictorOriginatingCentre, predictorSystem, predictorVariable, predictorPressureLevel, predictorAggregation,predictorTransform,firstAvailYear=gl.fcstpredSources[predictorCode]

        #checking if cds available
        client = requireCdsapi()

        if client is None:
            return

        showMessage("checking if data available locally...")

        availableYears=availableDataYears(int(firstAvailYear), month, 10)

        if int(predictorYear)>availableYears[-1]:
             showMessage(f"Requested data will contain data till {availableYears[-1]}, and does not include data for {predictorYear}{predictorMonth}", "ERROR")
             return
 
        firstAvailYear=availableYears[0]
        lastAvailYear=availableYears[-1]
        outfile=Path(f"{downloadsDir}/{predictorCode}_{monthName}_{areaStr}_{firstAvailYear}-{lastAvailYear}.nc")

        if skipIfExists(outfile, overwrite):
            return

        result=cdsDownloadForecast(client, predictorDataset, predictorOriginatingCentre, predictorSystem, predictorPressureLevel, predictorVariable, area, month, availableYears, outfile)

        if result is False:
            return

    else:
        showMessage("\nSource {} not available. Exiting...".format(source), "ERROR")
            


def downloadIndexPredictor():
    
    readGui()    
    
    #save config to json file
    saveConfig()
    
    downloadsDir=gl.config['downloadDir']
    indexCode=gl.config['indexCode']
    overwrite=gl.config['indexOverwrite']
    predictorYear=gl.config['predictorYear']
    predictorMonth=gl.config['predictorMonth']
    
    if not ensureDownloadsDir(downloadsDir):
        return
    
    if indexCode=="":
        showMessage("\nplease select variable to download", "ERROR")
        return

    if predictorYear=="":
        showMessage("\nplease provide predictor's year", "ERROR")
        return
    
    if not isNumber(predictorYear):
        showMessage("\npredictor year should be numeric", "ERROR")
        return
    
    if predictorMonth=="":
        showMessage("\nplease provide predictor's month", "ERROR")
        return
    
    showMessage("\ndownloading {}".format(indexCode))

    predictorDate=pd.to_datetime("01 {} {}".format(predictorMonth, predictorYear))+pd.offsets.MonthEnd()
    url=gl.indexSources[indexCode][1]
    source=indexCode.split("_")[-1]

    
    #requesting data
    response=downloadUrl(url)
    if response is False:
        showMessage("Failed to download data", "ERROR") 
        return

    #index-specific processing
    if source=="JMA":
        #processing raw data
        data=response.text.split("\n")
        data=np.array([x.split() for x in data[1:-1]])
        years=data[:,0]
        data=data[:,1:].flatten()
        
        #creating and populating dataframe
        dates=pd.date_range("{}-01-01".format(years[0]), periods=len(data), freq="ME")
        
        indexName=indexCode.split("_")[0]
        output=pd.DataFrame(data, index=dates, columns=[indexName]).astype(float)
        output[output==99.90]=np.nan
        output=output[~np.isnan(output).values]
        
    firstDate=output.index[0].strftime("%Y%m")
    lastDate=output.index[-1].strftime("%Y%m")
    firstAvailYear=output.index[0].year
    lastAvailYear=output.index[-1].year
    
    showMessage("downloaded data covers the period of {} to {}".format(firstDate, lastDate))

    showMessage("checking if predictor date {} in data...".format(predictorDate.strftime("%b %Y")))
    if not predictorDate in output.index:
        showMessage("predictor date {} not in data!".format(predictorDate.strftime("%b %Y")),"NONCRITICAL")

    
    output=output[str(firstAvailYear):str(lastAvailYear)]
    firstDate=output.index[0].strftime("%Y%m")
        
        
    #defining file names
    #rawfile=Path(downloadsDir,"{}_{}-{}.txt".format(indexCode, firstDate, lastDate))
    outfile=Path(downloadsDir,"{}_{}-{}.csv".format(indexCode, firstDate, lastDate))
    
    if skipIfExists(outfile, overwrite):
        return
          
    # on successful response - writing raw file
    #with open(rawfile, "w") as outf:
    #    outf.write(response.text)
    #showMessage("saved raw data to {}".format(rawfile), "SUCCESS")

    #saving file to csv
    output.to_csv(outfile)
    showMessage("saved csv data to {}".format(outfile), "SUCCESS")


def loadDataSources():            
    #reading data source dictionary
    try:
        with open(gl.sourcesFile) as f:
            sourcesDict = json.load(f)
            #at this stage, just keys of properties are needed.
        indexSources = sourcesDict['indexSources']
        predictandSources = sourcesDict['predictandSources']
        obspredSources = sourcesDict['obspredSources']
        fcstpredSources = sourcesDict['fcstpredSources']
        return indexSources,predictandSources,obspredSources,fcstpredSources
    except:
        showMessage("Could not read {}, check if it is a valid json file".format(gl.sourcesFile), "ERROR")
        return {},{},{},{}
           
            
def populateGui():
    
    gl.indexSources,gl.predictandSources,gl.obspredSources,gl.fcstpredSources=loadDataSources()

    gl.window.comboBox1_var.clear()
    gl.window.comboBox1_var.addItem("", "")
    for key, value in gl.predictandSources.items():
        gl.window.comboBox1_var.addItem(value[0], key)
        
    gl.window.comboBox2_var.clear()
    gl.window.comboBox2_var.addItem("", "")
    for key, value in gl.obspredSources.items():
        gl.window.comboBox2_var.addItem(value[0], key)
        
    gl.window.comboBox3_var.clear()
    gl.window.comboBox3_var.addItem("", "")
    for key, value in gl.fcstpredSources.items():
        gl.window.comboBox3_var.addItem(value[0], key)
    
    gl.window.comboBox4_var.clear()
    gl.window.comboBox4_var.addItem("", "")
    for key, value in gl.indexSources.items():
        gl.window.comboBox4_var.addItem(value[0], key)

    gl.window.comboBox_tgtseas.clear()
    for key in seasonmonths.keys():
        gl.window.comboBox_tgtseas.addItem(key, key)
    
    gl.window.comboBox_srcmon.clear()
    for key in monthNames:
        gl.window.comboBox_srcmon.addItem(key, key)
        
    gl.window.comboBox_fcstsrcmon.clear()
    for key in monthNames:
        gl.window.comboBox_fcstsrcmon.addItem(key, key)

    gl.window.lineEditDirectory.setText(gl.config['downloadDir'])
    gl.window.comboBox_tgtseas.setCurrentText(gl.config['fcstTargetSeas'])
    gl.window.lineEdit_srcyear.setText(str(gl.config['predictorYear']))
    gl.window.lineEdit_fcstsrcyear.setText(str(gl.config['fcstpredYear']))
    gl.window.comboBox_srcmon.setCurrentText(gl.config['predictorMonth'])
    gl.window.comboBox_fcstsrcmon.setCurrentText(gl.config['fcstpredMonth'])
    
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
    gl.config['fcstpredMonth'] = "Jun"
    gl.config['predictorYear'] = 2025
    gl.config['fcstpredYear'] = 2025
    gl.config['fcstTargetSeas']="Dec"
    

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
    gl.config['fcstpredMonth'] = gl.window.comboBox_fcstsrcmon.currentData()
    gl.config['predictorYear'] = gl.window.lineEdit_srcyear.text()
    gl.config['fcstpredYear'] = gl.window.lineEdit_fcstsrcyear.text()
    gl.config['fcstTargetSeas']=gl.window.comboBox_tgtseas.currentData()

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
    
    
