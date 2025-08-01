"""
@author: pwolski
"""
import os, sys
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Patch
import xarray as xr

import statsmodels.api as sm
from scipy.stats import pearsonr

from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPRegressor

from pathlib import Path

import warnings
import numpy as np
import geojson, json

import gl


# --- constants ---
months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
seasons = ['JFM', 'FMA', 'MAM', 'AMJ', 'MJJ', 'JJA', 'JAS', 'ASO', 'SON', 'OND', 'NDJ', 'DJF']
month_dict = {'jan':'01','feb':'02','mar':'03','apr':'04','may':'05','jun':'06','jul':'07',
              'aug':'08','sep':'09','oct':'10','nov':'11','dec':'12'}

season_start_month = {'Jan': 'JFM', 'Feb': 'FMA', 'Mar': 'MAM', 'Apr': 'AMJ', 'May': 'MJJ', 'Jun': 'JJA', 'Jul': 'JAS',
                     'Aug': 'ASO', 'Sep': 'SON', 'Oct': 'OND', 'Nov': 'NDJ', 'Dec': 'DJF'}

season_months = {'JFM': ['Jan', 'Feb', 'Mar'], 'FMA': ['Feb', 'Mar', 'Apr'], 'MAM': ['Mar', 'Apr', 'May'],
                 'AMJ': ['Apr', 'May', 'Jun'], 'MJJ': ['May', 'Jun', 'Jul'], 'JJA': ['Jun', 'Jul', 'Aug'],
                 'JAS': ['Jul', 'Aug', 'Sep'], 'ASO': ['Aug', 'Sep', 'Oct'], 'SON': ['Sep', 'Oct', 'Nov'],
                 'OND': ['Oct', 'Nov', 'Dec'], 'NDJ': ['Nov', 'Dec', 'Jan'], 'DJF': ['Dec', 'Jan', 'Feb']}

msgColors={"ERROR": "red",
           "INFO":"blue",
           "RUNTIME":"grey",
           "NONCRITICAL":"red",
           "SUCCESS":"green"
          }


# --- functions ---

def clearLog():
    gl.window.logWindow.clear()

def month2int(_str):
    #converts month string to non-pythonic integer month number
    return (np.where(np.array(months)==_str)[0][0])+1    
    
def showMessage(_message, _type="RUNTIME"):
    #this print messages to log window, which are generated outside of the threaded function
    try:
        _color=msgColors[_type]
        _message = "<pre><font color={}>{}</font></pre>".format(_color, _message)
        gl.window.logWindow.appendHtml(_message)
    #    window.logWindow.update()
        gl.window.logWindow.ensureCursorVisible()
        #print(_message)
    except:
        print(_message)

def launchForecast():
    #executed after pressing start button
    cont=True
    #have to include some flow control, so if any of functions fails the code stops
    
    #read forecast arguments from GUI
    response=updateConfig()
    if response is None:
        return
    
    #returns plain data with some basic checks
    predictand=readPredictand()
    if predictand is None:
        return
    
    #should be done always
    #qc=qualityCheck(predictand)
    #if qc==False:
    #    return
    
    if gl.config["gapFill"]==True:
        predictand=predictandGapFill(predictand)
    
    predictors=readPredictors()
    if predictors is None:
        return


    
def populateGUI():
    cont=True
    return None
   # Load values into the UI
    #this populates the list of predictor months in combo
    populateComboBoxes(gl.config.get('fcstPeriodLength'), gl.config.get('fcstPeriodStartMonth'))
    gl.window.startyearLineEdit.setText(str(gl.config.get('trainStartYear')))
    gl.window.endyearLineEdit.setText(str(gl.config.get('trainEndYear')))
    gl.window.predictMonthComboBox.setCurrentIndex(months.index(gl.config.get('predictorMonth','Jul')))
    if 'LR' in gl.config.get('algorithms', []): gl.window.LRcheckBox.setChecked(True)
    if 'MLP' in gl.config.get('algorithms', []): gl.window.LRcheckBox.setChecked(True)
    gl.window.pvaluelineEdit.setText(str(gl.config.get('PValue')))
    gl.window.minHSLineEdit.setText(str(gl.config.get('minHSscore')))
    gl.window.swpvaluelineEdit.setText(str(gl.config.get('stepwisePvalue')))
    gl.window.missingvalueslineEdit.setText(str(gl.config.get('predictandMissingValue')))
    gl.window.outdirlabel.setText(gl.config.get('outDir'))
    gl.window.fcstyearlineEdit.setText(str(gl.config.get('fcstyear')))
    gl.window.zonevectorlabel.setText(gl.config.get('zonevector',{}).get('file',''))
    for xx in gl.config.get('zonevector', {}).get('attr',[]):
        gl.window.zoneIDcomboBox.addItem(str(xx))
    gl.window.zoneIDcomboBox.setCurrentIndex(gl.config.get('zonevector', {}).get('ID',0))
    gl.window.predictorlistWidget.clear()
    for fileName in gl.config.get('predictorList'):
        gl.window.predictorlistWidget.addItem(os.path.basename(fileName))
    gl.window.predictandlistWidget.clear()
    for fileName in gl.config.get('predictandList'):
        gl.window.predictandlistWidget.addItem(os.path.basename(fileName))
    if gl.config.get('inputFormat') == "CSV":
        gl.window.CSVRadio.setChecked(True)
    else:
        gl.window.NetCDFRadio.setChecked(True)
        gl.window.predictandIDcombobox.addItem(gl.config.get('predictandattr', ''))
    if gl.config.get('composition') == "Sum":
        gl.window.cumRadio.setChecked(True)
    if gl.config.get('composition') == "Average":
        gl.window.avgRadio.setChecked(True)
    if 'LR' in gl.config.get('algorithms'):
        gl.window.LRcheckBox.setChecked(True)
    else:
        gl.window.LRcheckBox.setChecked(False)
    if 'MLP' in gl.config.get('algorithms'):
        gl.window.MLPcheckBox.setChecked(True)
    else:
        gl.window.MLPcheckBox.setChecked(False)
    gl.window.minlatLineEdit.setText(str(gl.config.get("basinbounds",{}).get('minlat')))
    gl.window.maxlatLineEdit.setText(str(gl.config.get("basinbounds",{}).get('maxlat')))
    gl.window.minlonLineEdit.setText(str(gl.config.get("basinbounds",{}).get('minlon')))
    gl.window.maxlonLineEdit.setText(str(gl.config.get("basinbounds",{}).get('maxlon')))

    
    
def updateConfig():
    showMessage("Updating config...")
    cont=True
    
    readConfig()
    
    #saving config file
    writeConfigToFile()
    return

    
def readConfig():
    #reading config from GUI - this is still to be added, but only once the user input and GUI are "stabilized"
    #for the time being - entries in gl.config are used
    return None



def writeConfigToFile():
    cont=True
    for key in gl.config.keys():
        showMessage("{}: {}".format(key, gl.config[key]))
    #writing config to file
    showMessage("writing config to {}...".format(gl.configFileName))

    
def createConfig():
    #this creates
    showMessage("Creating config file...")
    gl.config = {}
    gl.config['Version'] = gl.version
    gl.config['outDir'] = './test_output'
    
    gl.config['predictandFileFormat'] = "csv"
    gl.config['predictandFileName'] = "./data/PRCPTOT_mon_CHIRPS-v2.0-p05-merged_cft_stations_BWA.csv"
#    gl.config['predictandFileFormat'] = "netcdf"
#    gl.config['predictandFileName'] = "./data/pr_mon_chirps-v2.0_198101-202308.nc"
    gl.config['predictandMissingValue'] = -9999
    gl.config['predictandCategory'] = 'precipitation'
    gl.config['predictandVar'] = 'PRCPTOT'
    gl.config['predictandGapFill'] = False
    
    gl.config['temporalAggregation'] = "Sum"
    
    gl.config['predictorFileList'] = [["./data/SST_Jan_1961-2024.nc","sst"]]
    gl.config['predictorMonth'] = 'Jul'
    gl.config['basinMinLat'] = -90
    gl.config['basinMaxLat'] = 90
    gl.config['basinMinLon'] = -180
    gl.config['basinMaxLon'] = -180
    
    
    gl.config['fcstBaseTime'] = 'month'
    gl.config['fcstTargetMonth'] = 'Oct'
    gl.config['fcstTargetYear'] = '2024'
    
    gl.config['climStartYr'] = 1991
    gl.config['climEndYr'] = 2020

    gl.config['crossvalidation'] = "k-fold"
    gl.config['nFolds'] = 5
    
    gl.config['zoneFile'] = "./data/Botswana.geojson"
    gl.config['spatialAggregation'] = "zonal"
    
    gl.config['algorithm'] = 'PCR'
    
    gl.config["gapFill"]=False    
    #populateGUI()
    
    writeConfigToFile()   

def readNetcdf(ncfile, ncvar):
    ds = xr.open_dataset(ncfile, decode_times=False)
    try:
        #decode_times fixes the IRI netcdf calendar problem
        ds = xr.open_dataset(ncfile, decode_times=False)
    except:
        showMessage(("File cannot be read. please check if the file is properly formatted", "ERROR"))
        return

    #aligning coordinate names    
    coordsubs={"lon":["longitude","X","Longitude","Lon"], "lat":["latitude","Y","Latitude","Lat"], "time":["T"]}
    for key in coordsubs.keys():
        for x in coordsubs[key]:
            if x in ds.coords.keys():
                showMessage("found {} - renaming to {}".format(x,key),"RUNTIME")
                ds=ds.rename({x:key})

    #parsing time variable with some cleanup                
    if ds["time"].attrs['calendar'] == '360':
        ds["time"].attrs['calendar'] = '360_day'
    ds = xr.decode_cf(ds)
    ds=ds.convert_calendar("standard", align_on="date")

    if ncvar not in ds.variables:
        msg="Requestd variable named {}, but it is not present in the netcdf file {}. Please inspect the data file.".format(ncvar, ncfile)
        showMessage(msg, "ERROR")
        return
    
    #selecting only the requested variable
    dat=ds[ncvar]

    #testing if variable has all required dimensions
    test=[x not in dat.coords.keys() for x in ["lat","lon","time"]]
    if np.sum(test)>0:
        message="requested variable should have time,latitude and longitude coordinates. This is not the case. Please check if {} file is properly formatted and if {} variable of that file the one that describes forecast".format(ncfile,ncvar)
        showMessage(msg, "ERROR")
        return

    #dropping unnecessary dimensions
    for dimName in dat.sizes.keys():
        if dimName not in ["lat","lon","time"]:
            if dat.sizes[dimName]==1:
                msg="Dropping redundand dimension of size 1: {}".format(dimName)
                showMessage(msg, "RUNTIME")
                dimValue=dat[dimName].values[0]
                dat=dat.sel({dimName:dimValue})
            else:
                msg="There is a redundand dimension in data that cannnot be dropped. {} of size {}. Please check your data file".format(dimName, dat.sizes[dimName])
                showMessage(msg, "ERROR")
                return

    
    #processing obs data further
    dat=dat.rio.write_crs("epsg:4326") #adding crs

    if "units" in dat.attrs:
        datunits=dat.attrs["units"]
        showMessage("Found units: {}".format(datunits),"RUNTIME")
    else:
        datunits="unknown"

    datdates=pd.to_datetime(dat.time)
    firstdatdate=datdates.strftime('%Y-%m-%d')[0]
    lastdatdate=datdates.strftime('%Y-%m-%d')[-1]

    showMessage("Netcdf file covers period of: {} to {}".format(firstdatdate,lastdatdate),"RUNTIME")

    #check against the forecast date
    firstdatyear=datdates.year[0]
    lastdatyear=datdates.year[-1]

    if gl.config["climEndYr"]>lastdatyear or gl.config["climStartYr"]<firstdatyear:
        showMewssage("Climatological period {}-{} extends beyond period covered by data {}-{}".format(gl.config["climStartYr"],gl.config["climEndYr"],firstobsyear,lastobsyear), "ERROR")
        return

    showMessage("Successfuly read data from {}\n".format(ncfile), "SUCCESS")
    
    return(dat)
    

    
    
def readCsv(csvfile):
    ds=pd.read_csv(csvfile)
    
    #main test is number of unique values in first colums
    test1=len(np.unique(ds.iloc[:,0]))<ds.shape[0]
    test2=ds.shape[1]==16
    
    if test1 and test2:
        msg="Detected file with 12 months of data in each row, i.e. CFT format."
        showMessage(msg, "RUNTIME")
        csvformat="byMonth" #months of year in columns
    else:
        msg="Detected file with time series of data in each column."
        showMessage(msg, "RUNTIME")
        csvformat="byLoc" #locations in columns
    
    if csvformat=="byMonth":
        #ID,Lat,Lon,Year,Jan...Dec
        if ("Year" not in ds.keys()):
            msg="Data should contain column named Year. Data file {} does not. Please inspect the data file.".format(csvfile)
            showMessage(msg, "ERROR")
            return                  
        if "ID" not in ds.keys():
            msg="Data should contain column named ID. Data file {} does not.Please inspect the data file.".format(csvfile)
            showMessage(msg, "ERROR")
            return

        nans=pd.isnull(ds.ID)
        if nans.any():
            badrows=np.where(nans)[0]+1
            badrows=",".join(list(badrows.astype(str)))
            showMessage("CSV file contains rows {} with no data. Please edit the {} file with text editor (NOT Excel!) to remove these rows".format(badrows, obsFile), "ERROR")
            return                       
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
            dat=ds[sel].iloc[:,4:]
            
            #check if data contains strings
    #       data=data.applymap(self.tofloat)
            dat=dat.values.flatten()
            try:
                dat=dat.astype(float)
            except:
                showMessage("Data for {} contains entries that are of string (character) type which cannot be converted to numerical values. There should be no non-numeric characters in the data. Please edit the {} file so that it is formatted correctly".format(name, obsFile), "ERROR")
                return
            
            
            index=pd.date_range("{}-01-01".format(int(firstyear)),"{}-12-31".format(int(lastyear)),freq="ME")
            try:
                dat=pd.DataFrame(dat.reshape(-1,1), index=index,columns=[name])
            except:
                msg="data for {} contains {} months, expected {} months - data should cover continuous period from Jan {} to Dec {} with entries for every month in that period".format(name, len(index),len(data), firstyear, lastyear)
                showMessage(msg, "ERROR")
                return                 

            alldata.append(dat)

        #dat is pandas dataframe
        dat=pd.concat(alldata, axis=1)
        
        
    else:
        
        #rereading the file in appropriate way
        dat=pd.read_csv(csvfile, header=[0,1,2], index_col=0, parse_dates=True)
        
        latVar,lonVar=None,None
        for x in ["Lat","lat","Latitude","latitude"]:
            if x in dat.columns.names:
                latVar=x
                lats=dat.columns.get_level_values(latVar)
                dat=dat.droplevel(latVar, axis=1)
                
        for x in ["Lon","lon","Longitude","longitude"]:
            if x in dat.columns.names:
                lonVar=x
                lons=dat.columns.get_level_values(lonVar)
                dat=dat.droplevel(lonVar, axis=1)
                
        dat.columns.name=None
        
        if latVar is None:
            msg="Data should contain values for Latitude of stations in one of the top three rows, marked by word 'Lat' in the first column of data. {} does not. Please inspect the data file.".format(csvfile)
            showMessage(msg, "ERROR")
            return
        
        if lonVar is None:
            msg="Data should contain values for longitude of stations in one of the top three rows, marked by word 'Lon' in the first column of data. {} does not. Please inspect the data file.".format(csvfile)
            showMessage(msg, "ERROR")
    
        
        
    if gl.config['predictandMissingValue'] != "":
        dat[dat==gl.config['predictandMissingValue']]=np.nan

    #check only if rainfall
    if  gl.config['predictandCategory'] =='rainfall':
        dat[dat<0]=np.nan

    nancount=np.sum(np.isnan(dat), axis=0).sum()

    if nancount>0:
        nanperc=np.round(np.int32(nancount)/np.prod(dat.shape)*100,1)
        showMessage("There are {} missing data points, which is approx {}% of all data points in this dataset. Check if this is what is expected".format(nancount,nanperc), "NONCRITICAL")                  

    #creating geodataframe with all data
    #datgpd=gpd.GeoDataFrame(dat.T.reset_index(), geometry=gpd.points_from_xy(lons, lats), crs="EPSG:4326")

    datdates=dat.index
    firstdatdate=datdates.strftime('%Y-%m-%d')[0]
    lastdatdate=datdates.strftime('%Y-%m-%d')[-1]

    showMessage("Observed file covers period of: {} to {}".format(firstdatdate,lastdatdate),"RUNTIME")

    #check against the forecast date
    firstdatyear=datdates.year[0]
    lastdatyear=datdates.year[-1]


    if gl.config["climEndYr"]>lastdatyear or gl.config["climStartYr"]<firstdatyear:
        showMessage("Climatological period {}-{} extends beyond period covered by data {}-{}".format(gl.config["climStartYr"],gl.config["climEndYr"],firstdatyear,lastdatyear), "ERROR")
        return


    dat=dat.stack().to_xarray()
    dat=dat.rename({'level_0':"time", "level_1":"loc"})
    dat=dat.to_dataset(name="predictand")
    dat=dat.assign(dict(lat=(["loc"], lats), lon=(["loc"], lons)))

    showMessage("Successfuly read data from {}\n".format(csvfile), "SUCCESS")
    return dat
        

        

      
def readPredictand():
    obsFile=gl.config["predictandFileName"]
    if obsFile=="":
        showMessage("predictand file not defined","ERROR")
        return
        
    showMessage("reading predictand from {}...".format(obsFile), "INFO")
    if not os.path.exists(obsFile):
        showMessage("file does not exist","ERROR")
        return
    
    showMessage("file exists, reading...")
    
    #just to make sure...

    ext=obsFile.split(".")[-1]
    if ext not in ["csv", "nc"]:
        showMessage("only .csv and .nc files accepted, got {}".format(ext),"ERROR")
        return
    
    #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    #this is where code is different for csv and netcdf formats
    if gl.config["predictandFileFormat"]=="netcdf":
        obsVar=gl.config["predictandVar"]
        if obsVar=="":
            showMessage("predictand variable not defined","ERROR")
            return
        obsdata=readNetcdf(obsFile, obsVar)
    else:
        obsdata=readCsv(obsFile)
    
    print("obsdata", obsdata)
    
    if obsdata is None:
        #if read functions return False, i.e. data could not be read
        return
    
    else:
        #ggregate if necessary
        if gl.config['fcstBaseTime']=="season":
            if gl.config['temporalAggregation']=="mean":
                 obsdata=obsdata.rolling(time=3).mean()
            else:
                 obsdata=obsdata.rolling(time=3).sum()

        #select target season
        #should be last month of the 3-month period for seasonal
        tgtMonth=month2int(gl.config['fcstTargetMonth'])
        obsdata=obsdata.sel(time=obsdata.time.dt.month==tgtMonth)
        return obsdata

    
        

def readPredictors():
    predictors=[]
    for predFile, predVar in gl.config["predictorFileList"]:
        if predFile=="":
            showMessage("predictor file not defined","ERROR")
            return

        showMessage("reading predictor from {}...".format(predFile), "INFO")
        if not os.path.exists(predFile):
            showMessage("file does not exist","ERROR")
            return

        showMessage("file exists, reading...")

        #just to make sure...

        ext=predFile.split(".")[-1]
        if ext not in ["csv", "nc"]:
            showMessage("only .csv and .nc files accepted, got {}".format(ext),"ERROR")
            return

        #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        #this is where code is different for csv and netcdf formats
        if ext=="nc":
            predictor=readNetcdf(predFile, predVar)
        else:
            predictor=readCsv(predFile)
            #need to convert to pandas
        if predictor is None:
            return

        print(predictor.shape)
        #select predictor month. IRI data comes filtered for a particular month, but other data sources will not be. So just to make sure.
        tgtMonth=month2int(gl.config['predictorMonth'])
        
        predictor=predictor.sel(time=predictor.time.dt.month==tgtMonth)
        #check for time steps in predictor, i.e. if predictor month was not wrongly selected by any chance.
        
        predictors.append(predictor)
    return predictors
    