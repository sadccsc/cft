import os, sys
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Patch
import xarray as xr

from scipy.stats import pearsonr

from sklearn.preprocessing import StandardScaler
from sklearn.cross_decomposition import CCA
from sklearn.decomposition import PCA

from sklearn.linear_model import LinearRegression, Ridge, Lasso
#from sklearn.linear_model import RidgeCV, LassoCV
from sklearn.tree import DecisionTreeRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.ensemble import RandomForestRegressor

from sklearn.model_selection import cross_val_score, RepeatedKFold, LeaveOneOut, LeavePOut, KFold, cross_val_predict

from sklearn.metrics import r2_score, mean_squared_error, roc_auc_score, mean_absolute_percentage_error, mean_squared_error, explained_variance_score

from sklearn.base import BaseEstimator, RegressorMixin

from rasterstats import zonal_stats

import matplotlib.colors as colors

import cartopy.crs as ccrs

from pathlib import Path

import inspect
import warnings
import numpy as np
import geojson, json

import gl

from PyQt5.QtWidgets import QFileDialog

    
import re
import unicodedata

seasons = ['JFM', 'FMA', 'MAM', 'AMJ', 'MJJ', 'JJA', 'JAS', 'ASO', 'SON', 'OND', 'NDJ', 'DJF']

months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


regressors = {
        "OLS": LinearRegression,
        'Lasso': Lasso,
        'Ridge': Ridge,
        'RF': RandomForestRegressor,
        'MLP': MLPRegressor,
        'Trees': DecisionTreeRegressor,
    }


terc2num={"below":0,"normal":1,"above":2}
num2terc={0: "below",1:"normal",2:"above"}

cem2num={"below":0,"normal-to-below":1,"normal-to-above":2,"above":3}
num2cem={0:"below",1:"normal-to-below",2:"normal-to-above",3:"above"}


tgtSeass=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan-Mar","Feb-Apr","Mar-May","Apr-Jun","May-Jul","Jun-Aug","Jul-Sep","Aug-Oct","Sep-Nov","Oct-Dec","Nov-Jan","Dec-Feb"]

srcMons=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

timeAggregations={"sum","mean"}

crossvalidator_config={
    "KF":["K-Fold",{"n_splits":5}],
    "LOO":["Leave One Out",{}],
}

#can be read from json - potentially editable by user
regressor_config = {
    "OLS":["Linear regression", {}],
    "Lasso":["Lasso regression", {'alpha': 0.01}],
    "Ridge":["Ridge regression", {'alpha': 1.0}],
    "RF":["Random Forest", {'n_estimators': 100, 'max_depth': 5}],
    "MLP":["Multi Layer Perceptron", {'hidden_layer_sizes': (50, 25), 'max_iter': 1000, 'random_state': 0}],
    "Trees":["Decision Trees", {'max_depth': 2}]
}

preprocessor_config={
    "PCR":["Principal Component Regression (PCR)", {}],
    "CCA":["Canonical Corelation Analysis (CCA)", {}],
    "NONE":["No preprocessing", {}],
}


def showMessage(_message, _type="RUNTIME"):
    msgColors={"ERROR": "red",
           "INFO":"grey",
           "RUNTIME":"grey",
           "NONCRITICAL":"red",
           "SUCCESS":"green"
          }
    try:
        _color=msgColors[_type]
        _message = "<pre><font color={}>{}</font></pre>".format(_color, _message)
        gl.window.log_signal.emit(_message)
    except:
        print(_message)

    
def month2int(_str):
    #converts month string to non-pythonic integer month number
    return (np.where(np.array(months)==_str)[0][0])+1    
    
    
    
def readPredictorCsv(csvfile):
    
    dat=pd.read_csv(csvfile, header=0, index_col=0, parse_dates=True)

    datdates=dat.index
    firstdatdate=datdates.strftime('%Y-%m-%d')[0]
    lastdatdate=datdates.strftime('%Y-%m-%d')[-1]

    showMessage("Predictor file covers period of: {} to {}".format(firstdatdate,lastdatdate),"RUNTIME")

    #check against the forecast date
    firstdatyear=datdates.year[0]
    lastdatyear=datdates.year[-1]


    if gl.config["climEndYr"]>lastdatyear or gl.config["climStartYr"]<firstdatyear:
        showMessage("Climatological period {}-{} extends beyond period covered by data {}-{}".format(gl.config["climStartYr"],gl.config["climEndYr"],firstdatyear,lastdatyear), "ERROR")
        return

    newtime=pd.to_datetime([x.replace(day=1) for x in pd.to_datetime(dat.index)])
    dat.index=newtime
    
    showMessage("Successfuly read data from {}\n".format(csvfile), "SUCCESS")
    
    return dat
    

    
    
def readPredictandCsv(csvfile):
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
        
        locs=dat.columns.get_level_values(0)
        
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
            
    if gl.predictandMissingValue != "":
        dat[dat==gl.predictandMissingValue]=np.nan

    #check only if rainfall
    if  gl.predictandCategory =='rainfall':
        dat[dat<0]=np.nan

    nancount=np.sum(np.isnan(dat), axis=0).sum()

    if nancount>0:
        nanperc=np.round(np.int32(nancount)/np.prod(dat.shape)*100,1)
        showMessage("There are {} missing data points, which is approx {}% of all data points in this dataset. Check if this is what is expected".format(nancount,nanperc), "NONCRITICAL")                  

    #creating geodataframe with all data
    geoData=gpd.GeoDataFrame(geometry=gpd.points_from_xy(lons, lats), crs="EPSG:4326", index=locs)
                            
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

    
    #converting to xarray - but do we have to?
    #dat=dat.stack().to_xarray()
    #dat=dat.rename({'level_0':"time", "level_1":"location"})
    #dat=dat.assign_coords(lat=("location",lats), lon=("location", lons))
    newtime=pd.to_datetime([x.replace(day=1) for x in pd.to_datetime(dat.index)])
    dat.index=newtime
    
    showMessage("Successfuly read data from {}\n".format(csvfile), "SUCCESS")
    
    return dat, geoData
        
    
def readPredictor(_model):
    
    predFile, predVar, predCode=gl.config["predictorFiles"][_model]
    if predFile=="":
        showMessage("predictor file not defined","ERROR")
        return

    showMessage("reading predictor from {}...".format(predFile), "INFO")
    if not os.path.exists(predFile):
        showMessage("file does not exist","ERROR")
        return

    showMessage("\tfile exists, reading...")

    #just to make sure...

    ext=predFile.split(".")[-1]
    if ext not in ["csv", "nc"]:
        showMessage("only .csv and .nc files accepted, got {}".format(ext),"ERROR")
        return

    srcMonth=month2int(gl.config['predictorMonth'])

    #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    #this is where code is different for csv and netcdf formats
    if ext=="nc":
        predictor=readNetcdf(predFile, predVar)
        if predictor is None:
            return

        #preparing to convert xarray to pandas
        predictor=predictor.stack(location=("lat", "lon"))

        #check for time steps in predictor, i.e. if predictor month was not wrongly selected by any chance.
        #dropping nans alon location dimension
        predictor=predictor.dropna("location")

        #converting to pandas
        predictor=predictor.to_pandas()

    else:
        predictor=readPredictorCsv(predFile)

        
    #making sure requested month is in the data
    if not srcMonth in predictor.index.month:
        showMessage("file does not contain data for requested month ({})".format(gl.config['predictorMonth']),"ERROR")
        return
    
    predictor=predictor[predictor.index.month==srcMonth]    
    if predictor is None:
        return
    
   
    datdates=predictor.index
    firstdatdate=datdates.strftime('%Y-%m-%d')[0]
    lastdatdate=datdates.strftime('%Y-%m-%d')[-1]

    showMessage("Predictor file covers period of: {} to {}".format(firstdatdate,lastdatdate),"RUNTIME")

    firstdatyear=datdates.year[0]
    lastdatyear=datdates.year[-1]

    #check if covers climatological period
    if gl.config["climEndYr"]>lastdatyear or gl.config["climStartYr"]<firstdatyear:
        showMessage("Climatological period {}-{} extends beyond period covered by data {}-{}".format(gl.config["climStartYr"],gl.config["climEndYr"],firstdatyear,lastdatyear), "ERROR")
        return
    
    #check if value for the forecast year is in data
    if not gl.predictorDate in datdates:
        showMessage("Predictor data do not include forecast date {}".format(gl.predictorDate.strftime("%b %Y")), "ERROR")
        return
        
    showMessage("done\n", "INFO")
    return predictor


def readPredictand():
    obsFile=gl.config["predictandFileName"]
    if obsFile=="":
        showMessage("predictand file not defined","ERROR")
        return
        
    showMessage("Reading predictand from {}...".format(obsFile), "INFO")
    if not os.path.exists(obsFile):
        showMessage("file does not exist","ERROR")
        return
    
    showMessage("\tfile exists, reading...")
    
    #just to make sure...

    ext=obsFile.split(".")[-1]
    if ext not in ["csv", "nc"]:
        showMessage("only .csv and .nc files accepted, got {}".format(ext),"ERROR")
        return
    #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    #this is where code is different for csv and netcdf formats
    if gl.config["predictandFileName"][-2:]=="nc":
        obsVar=gl.config["predictandVar"]
        if obsVar=="":
            showMessage("predictand variable not defined","ERROR")
            return
        obsdata=readNetcdf(obsFile, obsVar) #this returns xarray
        if obsdata is None:
            showMessage("could not read requested variable from file","ERROR")
            return
            
        geoData=obsdata[0,:]
        #preparing to convert xarray to pandas
        obsdata=obsdata.stack(location=("lat", "lon"))
        
        #check for time steps in predictor, i.e. if predictor month was not wrongly selected by any chance.
        #dropping nans alon location dimension
        obsdata=obsdata.dropna("location")
        
        #converting to pandas
        obsdata=obsdata.to_pandas()
        
    else:
        obsdata,geoData=readPredictandCsv(obsFile)
        
    if obsdata is None:
        showMessage("could not read requested variable from file","ERROR")
        return
    
    #resampling if necessary
    if gl.fcstBaseTime=="seas":
        showMessage("Resampling to seasonal...")
        if gl.config['timeAggregation']=="mean":
             obsdata=obsdata.resample("QS-{}".format((gl.config['fcstTargetSeas'][0:3]).upper())).mean()
        else:
             obsdata=obsdata.resample("QS-{}".format((gl.config['fcstTargetSeas'][0:3]).upper())).sum()

    obsdata=obsdata.dropna()

    #select target season
    tgtMonth=month2int(gl.config['fcstTargetSeas'][0:3])
    if not tgtMonth in obsdata.index.month:
        showMessage("Predictand data do not contain data for requested month ({})".format(gl.config['fcstTargetSeas'][0:3]),"ERROR")
        return
    obsdata=obsdata[obsdata.index.month==tgtMonth]
    if obsdata is None:
        return        

    #check for climatological period
    datdates=obsdata.index
    firstdatdate=datdates.strftime('%Y-%m-%d')[0]
    lastdatdate=datdates.strftime('%Y-%m-%d')[-1]

    showMessage("Predictant file covers period of: {} to {}".format(firstdatdate,lastdatdate),"RUNTIME")

    firstdatyear=datdates.year[0]
    lastdatyear=datdates.year[-1]

    #check if covers climatological period
    if gl.config["climEndYr"]>lastdatyear or gl.config["climStartYr"]<firstdatyear:
        showMessage("Climatological period {}-{} extends beyond period covered by data {}-{}".format(gl.config["climStartYr"],gl.config["climEndYr"],firstdatyear,lastdatyear), "ERROR")
        return

    return obsdata, geoData

    

def readNetcdf(ncfile, ncvar):
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
                showMessage("\tfound {} - renaming to {}".format(x,key),"RUNTIME")
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
        msg="requested variable should have time,latitude and longitude coordinates. This is not the case. Please check if {} file is properly formatted and if {} variable of that file the one that describes forecast".format(ncfile,ncvar)
        showMessage(msg, "ERROR")
        return

    #dropping unnecessary dimensions
    for dimName in dat.sizes.keys():
        if dimName not in ["lat","lon","time"]:
            if dat.sizes[dimName]==1:
                msg="\tDropping redundand dimension of size 1: {}".format(dimName)
                showMessage(msg, "RUNTIME")
                dimValue=dat[dimName].values[0]
                dat=dat.sel({dimName:dimValue})
                dat=dat.drop_vars(dimName)
            else:
                msg="There is a redundand dimension in data that cannnot be dropped. {} of size {}. Please check your data file".format(dimName, dat.sizes[dimName])
                showMessage(msg, "ERROR")
                return

    
    #this is probably not important at this moment
    #dat=dat.rio.write_crs("epsg:4326") #adding crs
    #making sure time is aligned to 1th of the month
    newtime=pd.to_datetime([x.replace(day=1) for x in pd.to_datetime(dat.time.values)])
    dat["time"]=newtime
    
    if "units" in dat.attrs:
        datunits=dat.attrs["units"]
        showMessage("\tFound units: {}".format(datunits),"RUNTIME")
    else:
        datunits="unknown"

    datdates=pd.to_datetime(dat.time)
    firstdatdate=datdates.strftime('%Y-%m-%d')[0]
    lastdatdate=datdates.strftime('%Y-%m-%d')[-1]

    showMessage("\tNetcdf file covers period of: {} to {}".format(firstdatdate,lastdatdate),"RUNTIME")

    #check against the forecast date
    firstdatyear=datdates.year[0]
    lastdatyear=datdates.year[-1]

    if gl.config["climEndYr"]>lastdatyear or gl.config["climStartYr"]<firstdatyear:
        showMessage("Climatological period {}-{} extends beyond period covered by data {}-{}".format(gl.config["climStartYr"],gl.config["climEndYr"],firstdatyear,lastdatyear), "ERROR")
        return


    showMessage("done\n", "SUCCESS")
    
    ds.close()
    
    return(dat)
        

#this calculates zonal mean over individual time steps
def zonalMean(_grid, _poly):
    affine=_grid.rio.transform()
    _zonalmean=[]
    for i in range(_grid.shape[0]):
        zs=zonal_stats(_poly, 
                       _grid[i,:,:].data, 
                       affine=affine, 
                       nodata=np.nan)
        temp=[x["mean"] for x in zs]
        _zonalmean.append(temp)

    _zonalmean=np.array(_zonalmean)
    _zonalmean=pd.DataFrame(_zonalmean, index=_grid.time, columns=_poly.index)
    return(_zonalmean)


def aggregatePredictand(_data, _geodata, _poly):
    showMessage("aggregating...")
    
    if isinstance(_geodata,xr.DataArray):
        #this is if geodata is xarray object
        _data=_data.unstack().to_xarray()
        _data=_data.transpose("time","lat","lon")
        _data=_data.reindex(lat=np.sort(_data.lat)[::-1])
        _data.rio.set_spatial_dims(x_dim='lon', y_dim='lat')        
        _data=_data.rio.write_crs("epsg:4326")
        _aggregated=zonalMean(_data, _poly)
        
        showMessage("\tAverage values for {} regions derived from data for {} by {} grid".format(_aggregated.shape[1], _data.shape[1], _data.shape[2]))
        
    else:
        #this is if geodata is a geopandas object
        _points=_geodata.copy().join(_data.T)
        #joining polygons and points
        _joined = gpd.sjoin(_points, _poly, how="inner", predicate="within")
        
        # Check if spatial matches were found before trying to rename index_right
        if not _joined.empty and 'index_right' in _joined.columns:
            _joined = _joined.rename(columns={"index_right": gl.config["zonesAttribute"]})
            #aggregating 
            _aggregated = _joined.groupby(gl.config["zonesAttribute"]).mean(numeric_only=True).T
            _aggregated.index=_data.index
            showMessage("\tAverage values for {} regions derived from data for {} locations".format(_aggregated.shape[1], _points.shape[1]))
        else:
            # No spatial matches found, create empty aggregated data
            showMessage("\tWarning: No spatial matches found between station points and polygon boundaries")
            _aggregated = pd.DataFrame(index=_data.index)  # Empty dataframe with correct index
    
    return _aggregated, _poly



    
        








def getLeadTime():
    srcMonth=month2int(gl.config['predictorMonth'])
    tgtMonth=month2int(gl.config['fcstTargetSeas'][0:3])
    tgtYear=int(gl.config['fcstTargetYear'])
    tgtDate=pd.to_datetime("{}-{}-01".format(tgtYear,tgtMonth))
    
    leadTime=(tgtMonth+12-srcMonth)%12
    if leadTime>gl.maxLeadTime:
        msg="with forecast and target months provided ({} and {}), lead time is {} months. That exceeds the maximum allowed lead time of {}. Please adjust your configuration.".format(srcMonth, tgtMonth, leadTime, gl.maxLeadTime)
        showMessage(msg,"ERROR")
        return None
    gl.leadTime=leadTime
    
    srcDate=tgtDate-pd.offsets.MonthBegin(leadTime)

    gl.predictorDate=srcDate
    
    return leadTime

def getHcstData(_predictand,_predictor):
    
    #get time of predictand and predictor
    _predictor=_predictor.dropna()
    _predictand=_predictand.dropna()
    
    tgtTime=pd.to_datetime(_predictand.index)
    srcTime=pd.to_datetime(_predictor.index)
    #drop nans
    
    #align time
    tgtTimeAdj=tgtTime-pd.offsets.MonthBegin(gl.leadTime)
    _predictandOvlp=_predictand.copy()
    _predictandOvlp.index=tgtTimeAdj

    
    sel=np.intersect1d(tgtTimeAdj, srcTime)
    _predictorOvlp=_predictor.loc[sel]
    _predictandOvlp=_predictandOvlp.loc[sel]
    tgtTime=pd.to_datetime(_predictandOvlp.index)
    tgtTimeAdj=tgtTime+pd.offsets.MonthBegin(gl.leadTime)
    _predictandOvlp.index=tgtTimeAdj
    
    
    return _predictandOvlp, _predictorOvlp


def getFcstData(_predictor):
    tgtMonth=month2int(gl.config['fcstTargetSeas'][0:3])
    tgtYear=int(gl.config['fcstTargetYear'])
    tgtDate="{}-{}".format(tgtYear,tgtMonth)
    _data=_predictor.loc[gl.predictorDate:gl.predictorDate]
    return _data





    

class StdRegressor(BaseEstimator, RegressorMixin):
    
    def __init__(self, regressor_name=None, fit_intercept=True, max_fraction=0.15, **regressor_kwargs):
        self.max_fraction = max_fraction
        self.fit_intercept = fit_intercept
        self.regressor_name = regressor_name
        self.regressor_kwargs = regressor_kwargs
        self.scaleX=StandardScaler()
        self.reg=self._get_regressor()
        
    def _get_regressor(self):
        if self.regressor_name not in regressors:
            raise ValueError(f"Unknown regressor '{self.regressor_name}'.")
        reg_class=regressors[self.regressor_name]
        
        # Inspect constructor to see if 'fit_intercept' is accepted
        sig = inspect.signature(reg_class.__init__)
        kwargs = self.regressor_kwargs.copy()
        if 'fit_intercept' in sig.parameters:
            kwargs['fit_intercept'] = self.fit_intercept
            self.supports_intercept=True
        else:
            self.supports_intercept=False
            
        return reg_class(**kwargs)
        
    def fit(self, X, Y):
        
        #scaling the predictor
        X_std=self.scaleX.fit_transform(X)
        
        #fitting regression model
        self.reg.fit(X_std, Y)
        
        return self

    
    def predict(self, X):
        #scale as per fitted model    
        X_c = self.scaleX.transform(X)
        
        #predict with model
        Y_pred=self.reg.predict(X_c)

        return Y_pred
    

    

    
    
def getObsTerciles(_predictand,_predictandHcst):
    
    showMessage("Calculating observed terciles...")
    refData=_predictand[str(gl.config["climStartYr"]):str(gl.config["climEndYr"])]   
    _tercThresh=refData.quantile([0.33, 0.5, 0.66])
    _obsTercile=_predictandHcst.copy().astype(str)
    _obsTercile[:]="normal"
    sel=_predictandHcst>=_tercThresh.loc[0.66]
    _obsTercile[sel.values]="above"
    #below
    sel=_predictandHcst<=_tercThresh.loc[0.33]
    _obsTercile[sel.values]="below"

    return _obsTercile,_tercThresh 
    
def getFcstAnomalies(_det_fcst,_ref_data):
    absanom=_det_fcst-_ref_data.mean()
    percanom=(_det_fcst-_ref_data.mean())/_ref_data.mean()*100
    percnorm=_det_fcst/_ref_data.mean()*100
    output=pd.concat([_det_fcst,absanom,percanom,percnorm], keys=["value","absolute_anomaly","percent_anomaly","percent_normal"], names=["category"], axis=1)
    output.index.name="time"
    return output



def get_prob_hcst(_data, _pred_err, _terc_thresh, what):
    if what=="above":
        prob=((_pred_err+_data>_terc_thresh).sum(0)/_pred_err.shape[0])
    elif what=="below":
        prob=((_pred_err+_data<_terc_thresh).sum(0)/_pred_err.shape[0])
    return(prob)


def probabilisticForecast(_Y_hcst,_Y_obs,_Y_fcst,_terc_thresh, _method="empirical"):
        
    #prediction error
    if _method=="empirical":
        
        pred_err=_Y_hcst-_Y_obs
        
        #tercile probabilities
        prob_above_fcst=((pred_err+_Y_fcst.values>_terc_thresh.loc[0.66]).sum(0)/pred_err.shape[0]).to_frame(name=_Y_fcst.index[0])
        prob_below_fcst=((pred_err+_Y_fcst.values<_terc_thresh.loc[0.33]).sum(0)/pred_err.shape[0]).to_frame(name=_Y_fcst.index[0])
        prob_normal_fcst=(((pred_err+_Y_fcst.values>=_terc_thresh.loc[0.33]) & (pred_err+_Y_fcst.values<=_terc_thresh.loc[0.66])).sum(0)/pred_err.shape[0]).to_frame(name=_Y_fcst.index[0])
        #should calculate for hindcast too

        pred_err=_Y_hcst-_Y_obs

        prob_above_hcst=_Y_hcst.apply(lambda row: get_prob_hcst(row, pred_err, _terc_thresh.loc[0.66], "above"), axis=1)
        prob_below_hcst=_Y_hcst.apply(lambda row: get_prob_hcst(row, pred_err, _terc_thresh.loc[0.33], "below"), axis=1)
        prob_normal_hcst=1-(prob_above_hcst+prob_below_hcst)
        
    else:
        return None
    terc_fcst=pd.concat([prob_above_fcst.T,prob_normal_fcst.T,prob_below_fcst.T], keys=["above","normal","below"],  names=["category"], axis=1)
    terc_hcst=pd.concat([prob_above_hcst,prob_normal_hcst,prob_below_hcst], keys=["above","normal","below"], names=["category"],axis=1)
    terc_fcst.index.name="time"
    terc_hcst.index.name="time"
    
    return terc_fcst, terc_hcst



def two_afc_multicategory(forecast_probs, obs):
    """
    Compute generalized 2AFC score for 3-category forecast.
    forecast_probs: np.array of shape (n_samples, 3)
    obs: np.array of shape (n_samples,) with values 0, 1, 2
    """
    scores = []
    
    for cat in range(3):
        correct = 0
        total = 0
        
        # Indices where obs is in current category (event)
        idx_event = np.where(obs == cat)[0]
        # Indices where obs is not in current category (non-event)
        idx_nonevent = np.where(obs != cat)[0]
        
        for i in idx_event:
            for j in idx_nonevent:
                f_i = forecast_probs[i, cat]
                f_j = forecast_probs[j, cat]
                
                if f_i > f_j:
                    correct += 1
                elif f_i == f_j:
                    correct += 0.5
                total += 1
                
        score = correct / total if total > 0 else np.nan
        scores.append(score)
        
    return np.nanmean(scores)


def rps_score(forecast_probs, observed_class, n_categories=3):
    # forecast_probs: array of shape (n_samples, n_categories)
    # observed_class: array of shape (n_samples,), with integer values 0, 1, ..., K-
    rps = 0
    for i in range(len(observed_class)):
        obs = np.zeros(n_categories)
        obs[observed_class[i]] = 1
        obs_cum = np.cumsum(obs)
        forecast_cum = np.cumsum(forecast_probs[i])
        rps += np.sum((forecast_cum - obs_cum) ** 2)
    return rps / len(observed_class)



def rpss_score(forecast_probs, climatology_probs, observed_class):
    rps_forecast = rps_score(forecast_probs, observed_class)
    rps_climatology = rps_score(np.tile(climatology_probs, (len(observed_class), 1)), observed_class)
    return 1 - rps_forecast / rps_climatology

cat2num={"below":0,"normal":1,"above":2}




def getSkill(_prob_hcst,_det_hcst,_predictand_hcst,_obs_tercile):
    #iterating through stations/locations
    index=["correlation",
       "MAPE",
       "RMSE",
       "ROC_above",
       "ROC_normal",
       "ROC_below",
       "rpss"]

    allscores=[]
    for entry in _det_hcst.columns:
        
        roc_score_above = np.round(roc_auc_score(_obs_tercile[entry]=="above", _prob_hcst["above"][entry]),2)
        roc_score_below = np.round(roc_auc_score(_obs_tercile[entry]=="below", _prob_hcst["below"][entry]),2)
        roc_score_normal = np.round(roc_auc_score(_obs_tercile[entry]=="normal", _prob_hcst["normal"][entry]),2)
        cor=np.round(np.corrcoef(_det_hcst[entry],_predictand_hcst[entry])[0][1],2)
        #r2=np.round(r2_score(_det_hcst[entry],_predictand_hcst[entry]))
        ev=np.round(explained_variance_score(_det_hcst[entry],_predictand_hcst[entry]))
        mape=np.round(mean_absolute_percentage_error(_det_hcst[entry],_predictand_hcst[entry]),2)
        rmse=np.round((mean_squared_error(_det_hcst[entry],_predictand_hcst[entry])**0.5),2)

        #prep data for rpss
        _prob_clim=_prob_hcst.copy()


        obsterc=_obs_tercile[entry]
        obsterc=obsterc.map(lambda x: cat2num[x]).values
        if isinstance(entry, tuple):
            mask = (_prob_clim.columns.get_level_values('lat') == entry[0]) & (_prob_clim.columns.get_level_values('lon') == entry[1])
            pclim=_prob_clim.loc[:, mask].values
            mask = (_prob_clim.columns.get_level_values('lat') == entry[0]) & (_prob_clim.columns.get_level_values('lon') == entry[1])
            phcst=_prob_hcst.loc[:,mask]
        else:
            pclim=_prob_clim.loc[:,_prob_clim.columns.get_level_values(1)==entry].values
            phcst=_prob_hcst.loc[:,_prob_hcst.columns.get_level_values(1)==entry]


        phcst.columns = phcst.columns.droplevel(1)
        #have to reorder so that below is 0, normal is 1, above is 2 as per cat2num
        phcst=phcst.loc[:,["below","normal","above"]].values

        #calculate rpss
        rpss=rpss_score(phcst, pclim,obsterc)

        # rpss
        # ignorance score
        # reliability diagram - plot
        # heidtke skill score for most probable forecast

        entryscores=pd.Series([cor,mape,rmse,roc_score_above, roc_score_normal,roc_score_below, rpss], index=index)

        allscores.append(entryscores)
    scores=pd.concat(allscores, axis=1, keys=_det_hcst.columns)
    scores.index.name = "category"        
    return(scores)






        
        
def saveConfig():
    #defined parameters/variables
    with open(gl.configFile, "w") as f:
        json.dump(gl.config, f, indent=4)
        showMessage("saved config to: {}".format(gl.configFile), "INFO")

        


def populateGui():
    #populate comboBoxes
    # target season
    gl.window.comboBox_tgtseas.clear()
    #gl.window.comboBox_tgtseas.addItem("", "")
    for key in tgtSeass:
        gl.window.comboBox_tgtseas.addItem(key, key)
    
    #source/predictand month
    gl.window.comboBox_srcmon.clear()
    #gl.window.comboBox_srcmon.addItem("", "")
    for key in srcMons:
        gl.window.comboBox_srcmon.addItem(key, key)

    #temporal aggregation
    gl.window.comboBox_timeaggregation.clear()
    #gl.window.comboBox_timeaggregation.addItem("", "")
    for key in timeAggregations:
        gl.window.comboBox_timeaggregation.addItem(key, key)
                
        
    for model in range(5):
        comboName="comboBox_preproc{}".format(model)
        if hasattr(gl.window, comboName):
            item=getattr(gl.window, comboName, None)
            item.clear()
            #item.addItem("", "")
            for key in preprocessor_config:
                item.addItem(preprocessor_config[key][0], key)
            
        comboName="comboBox_regression{}".format(model)
        if hasattr(gl.window, comboName):
            item=getattr(gl.window, comboName, None)
            item.clear()
            #item.addItem("", "")
            for key in regressor_config:
                item.addItem(regressor_config[key][0], key)
                
        comboName="comboBox_crossval{}".format(model)
        if hasattr(gl.window, comboName):
            item=getattr(gl.window, comboName, None)
            item.clear()
            #item.addItem("", "")
            for key in crossvalidator_config:
                item.addItem(crossvalidator_config[key][0], key)

                
    # read data from config
    gl.window.lineEdit_rootdir.setText(gl.config['rootDir'])
    gl.window.lineEdit_tgtyear.setText(str(gl.config['fcstTargetYear']))
    gl.window.lineEdit_srcyear.setText(str(gl.config['predictorYear']))
    gl.window.comboBox_srcmon.setCurrentText(gl.config['predictorMonth'])
    gl.window.comboBox_tgtseas.setCurrentText(gl.config['fcstTargetSeas'])
    gl.window.lineEdit_climstartyr.setText(str(gl.config['climStartYr']))
    gl.window.lineEdit_climendyr.setText(str(gl.config['climEndYr']))
    gl.window.comboBox_timeaggregation.setCurrentText(gl.config['timeAggregation'])

    for model in range(5):
        for var in ["minLon","maxLon","minLat","maxLat"]:
            itemName="lineEdit_{}{}".format(var, model)
            if hasattr(gl.window, itemName):
                item=getattr(gl.window, itemName, None)
                item.setText(str(gl.config['predictorExtents'][model][var]))
        
        itemName="comboBox_crossval{}".format(model)
        if hasattr(gl.window, itemName):
            item=getattr(gl.window, itemName, None)
            setval=crossvalidator_config[gl.config["crossval"][model]][0]
            item.setCurrentText(setval)

        itemName="comboBox_regression{}".format(model)
        if hasattr(gl.window, itemName):
            item=getattr(gl.window, itemName, None)
            setval=regressor_config[gl.config["regression"][model]][0]
            item.setCurrentText(setval)
            
        itemName="comboBox_preproc{}".format(model)
        if hasattr(gl.window, itemName):
            item=getattr(gl.window, itemName, None)
            setval=preprocessor_config[gl.config["preproc"][model]][0]
            item.setCurrentText(setval)

        itemName="lineEdit_predictorfile{}".format(model)
        if hasattr(gl.window, itemName):
            item=getattr(gl.window, itemName, None)
            predictorfile=gl.config["predictorFiles"][model][0]
            item.setText(predictorfile)
            variables=readVariablesFile(predictorfile)
    
        itemName="comboBox_predictorvar{}".format(model)
        if hasattr(gl.window, itemName):
            item=getattr(gl.window, itemName, None)
            setval=gl.config["predictorFiles"][model][1]
            #remove once (if) function to read file is implemented
            item.addItems(variables)
            if setval in variables:
                item.setCurrentText(setval)
                
        itemName="lineEdit_predictorcode{}".format(model)
        if hasattr(gl.window, itemName):
            item=getattr(gl.window, itemName, None)
            setval=gl.config["predictorFiles"][model][2]
            #remove once (if) function to read file is implemented
            item.setText(setval)
    
    gl.window.lineEdit_predictandfile.setText(gl.config['predictandFileName'])
    #for the time being - have to have a function that reads this file and populates variable list
    variables=readVariablesFile(gl.config['predictandFileName'])
    gl.window.comboBox_predictandvar.clear()
    gl.window.comboBox_predictandvar.addItems(variables)
    if gl.config['predictandVar'] in variables:
        gl.window.comboBox_predictandvar.setCurrentText(gl.config['predictandVar'])
            
    gl.window.checkBox_zonesaggregate.setChecked(gl.config["zonesAggregate"])
    
    gl.window.lineEdit_zonesfile.setText(gl.config['zonesFile'])
    attributes=readVariablesFile(gl.config['zonesFile'])        
    gl.window.comboBox_zonesattribute.clear()
    gl.window.comboBox_zonesattribute.addItems(attributes)
    if gl.config['zonesAttribute'] in attributes:
        gl.window.comboBox_zonesattribute.setCurrentText(gl.config['zonesAttribute'])

    gl.window.lineEdit_overlayfile.setText(gl.config['overlayFile'])

    
def makeConfig():
    gl.config={}

    #defined parameters/variables
    gl.config['rootDir'] = "../test_data"

    gl.config['predictorYear'] = 2025
    gl.config['predictorMonth'] = "Jun"

    #gl.config['fcstTargetSeas']="Mar-May"
    gl.config['fcstTargetSeas']="Dec"
    gl.config['fcstTargetYear']=2025

    gl.config["climEndYr"]=2015
    gl.config["climStartYr"]=1994

    gl.config["predictorExtents"]=[{'minLat':-60,'maxLat':60,'minLon':-180,'maxLon':180},
                                  ]


    gl.config['predictorFiles'] = [["./data/SST_Jun_1960-2025.nc","sst", "SST"]]
    gl.config['crossval']=["KF"]
    gl.config['preproc']=["PCR"]
    gl.config['regression']=["OLS"]

    gl.config['timeAggregation']="sum"
    gl.config["predictandFileName"]="./data/pr_mon_chirps-v2.0_198101-202308.nc"
    gl.config["predictandVar"]="PRCPTOT"

    gl.config["zonesFile"]="data/Botswana.geojson"
    gl.config["zonesAttribute"]="ID"
    gl.config["zonesAggregate"]=True

    gl.config["overlayFile"]="data/Botswana.geojson"
    
    
    
def readGUI():
    #defined parameters/variables
    gl.config['rootDir']=gl.window.lineEdit_rootdir.text()
    gl.config['fcstTargetYear']=int(gl.window.lineEdit_tgtyear.text())
    gl.config['predictorYear']=int(gl.window.lineEdit_srcyear.text())
    gl.config['predictorMonth']=gl.window.comboBox_srcmon.currentText()
    gl.config['fcstTargetSeas']=gl.window.comboBox_tgtseas.currentText()
    gl.config['climStartYr']=int(gl.window.lineEdit_climstartyr.text())
    gl.config['climEndYr']=int(gl.window.lineEdit_climendyr.text())
    gl.config['timeAggregation']=gl.window.comboBox_timeaggregation.currentText()

    gl.config["predictandFileName"]=gl.window.lineEdit_predictandfile.text()
    gl.config["predictandVar"]=gl.window.comboBox_predictandvar.currentText()

    gl.config["zonesFile"]=gl.window.lineEdit_zonesfile.text()
    gl.config["zonesAttribute"]=gl.window.comboBox_zonesattribute.currentText()
    gl.config["zonesAggregate"]=gl.window.checkBox_zonesaggregate.isChecked()

    gl.config["overlayFile"]=gl.window.lineEdit_overlayfile.text()

    
    gl.config["predictorExtents"]=[]
    for model in range(5):
        temp={}
        for var in ["minLon","maxLon","minLat","maxLat"]:
            itemName="lineEdit_{}{}".format(var, model)
            if hasattr(gl.window, itemName):
                item=getattr(gl.window, itemName, None)
                try:
                    temp[var]=float(item.text())
                except:
                    showMessage("Lat Lon values have to be numeric", "ERROR")
                    return
        if len(temp)==4:
            gl.config["predictorExtents"].append(temp)
    

    gl.config["predictorFiles"]=[]
    for model in range(5):
        temp=[]
        itemName="lineEdit_predictorfile{}".format(model)
        if hasattr(gl.window, itemName):
            temp.append(getattr(gl.window, itemName, None).text())
        itemName="comboBox_predictorvar{}".format(model)
        if hasattr(gl.window, itemName):
            temp.append(getattr(gl.window, itemName, None).currentText())
        itemName="lineEdit_predictorcode{}".format(model)
        if hasattr(gl.window, itemName):
            temp.append(getattr(gl.window, itemName, None).text())
            
        if len(temp)==3:
            gl.config["predictorFiles"].append(temp)

    gl.config["crossval"]=[]
    for model in range(5):
        itemName="comboBox_crossval{}".format(model)
        if hasattr(gl.window, itemName):
            gl.config["crossval"].append(getattr(gl.window, itemName, None).currentData())
                
    gl.config["preproc"]=[]
    for model in range(5):
        itemName="comboBox_preproc{}".format(model)
        if hasattr(gl.window, itemName):
            gl.config["preproc"].append(getattr(gl.window, itemName, None).currentData())
                
    gl.config["regression"]=[]
    for model in range(5):
        itemName="comboBox_regression{}".format(model)
        if hasattr(gl.window, itemName):
            gl.config["regression"].append(getattr(gl.window, itemName, None).currentData())

            
    #derived variables
    
    #set target type 
    if gl.config["zonesAggregate"]:
        gl.targetType="zones"
    elif gl.config["predictandFileName"][-3:]=="csv":
        gl.targetType="points"
    else:
        gl.targetType="grid"

    if len(gl.config["fcstTargetSeas"])>3:
        gl.fcstBaseTime="seas"
    else:
        gl.fcstBaseTime="mon"
        
    return True
        
        
def readVariablesFile(_file):        
    ext=os.path.splitext(_file)[1]
    if ext==".nc":
        variables = readVariablesNcfile(_file)
    elif ext in [".geojson",".shp"]:
        variables = readVariablesShpfile(_file)
    else:
        variables=[Path(_file).stem.split("_")[0]]
    if variables is None:
        #noncritical because check is done later too, and this will leave 
        showMessage("File with variables/attributes expected. If it is a netcdf file check if it is a dataset and has at least one variable, and if it is a shapefile - check if it has at least one attribute", "NONCRITICAL")
        variables=[]
    return variables

def readVariablesShpfile(_file):
    # Open the shapefile
    showMessage("reading variables from {}".format(_file))
    if os.path.exists(_file):
        gdf = gpd.read_file(_file)
        #exclude the geometry column:
        attributes = [col for col in gdf.columns if col != "geometry"]
        if len(attributes)>0:
            return attributes
        else:
            return
    else:
        showMessage("File {} does not exist".format(_file),"ERROR")
        return
            
def readVariablesNcfile(_file):
    # Open the shapefile
    showMessage("reading variables from {}".format(_file))
    if os.path.exists(_file):
        ds = xr.open_dataset(_file, decode_times=False)

        # If you want to exclude the geometry column:
        variables = ds.data_vars
        variables =[x for x in variables if x not in ["T","time","lat","lon","Lat","Lon","Latitude","Longitude","X","Y"]]
        ds.close()
        if len(variables)>0:
            return variables
        else:
            showMessage("File {} does not have any data variables".format(_file),"ERROR")
            return
    else:
        showMessage("File {} does not exist".format(_file),"ERROR")
        return        
    


def sanitize_string(value, replacement="_", max_length=255):
    """
    Sanitize a string so it can be safely used as a filename
    across Windows, macOS, and Linux.
    
    - Removes invalid characters
    - Removes control characters
    - Strips leading/trailing spaces and dots
    - Normalizes Unicode (optional transliteration to ASCII)
    - Truncates to max_length (default 255)
    """
    # Normalize Unicode (e.g., é → e)
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode()

    # Replace invalid characters with replacement
    value = re.sub(r'[<>:"/\\|?*]', replacement, value)

    # Remove control characters
    value = re.sub(r'[\x00-\x1f]', replacement, value)

    # Replace multiple consecutive replacements with a single one
    value = re.sub(rf'{re.escape(replacement)}+', replacement, value)

    # Strip leading/trailing spaces and dots
    value = value.strip(" .")

    # Truncate to safe length
    return value[:max_length] if max_length else value

def getCmap(d):
    vmin=d["vmin"]
    vmax=d["vmax"]
    nlev=d["nlev"]
    cmap=d["cmap"]
    extend=d["extend"]
    whitelev=d["whitelev"]
    levels = np.linspace(vmin,vmax,nlev)    
    cmap_rb = plt.get_cmap(cmap)
    if extend=="both":
        cols = cmap_rb(np.linspace(0.1, 0.9, len(levels)+1))
    elif extend=="neither":
        cols = cmap_rb(np.linspace(0.1, 0.9, len(levels)-1))
    else:
        cols = cmap_rb(np.linspace(0.1, 0.9, len(levels)))
        
    for lev in whitelev:
        cols[lev]=(1,1,1,1)
    cmap, norm = colors.from_levels_and_colors(levels, cols, extend=extend)
    return cmap,norm

colormaps={"percent_normal":{
        "categorized":True,
        "nlev":11,
        "title":"Forecast value as percent of normal",
        "cmap":"BrBG",
        "vmin":0,
        "vmax":200,
        "cbar_label":"mm",
        "levels":None,
        "whitelev":[4,5],
        "tick_labels":None,
        "extend":"max"},
    "value":{
        "categorized":True,
        "nlev":11,
        "title":"Forecast value",
        "cmap":plt.cm.YlGnBu,
        "vmin":0,
        "vmax":200,
        "cbar_label":"mm",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"max"},
    "absolute_anomaly":{
        "categorized":True,
        "nlev":11,
        "title":"Forecast anomaly",
        "cmap":plt.cm.BrBG,
        "vmin":-50,
        "vmax":50,
        "cbar_label":"mm",
        "levels":None,
        "whitelev":[5,6],
        "tick_labels":None,
        "extend":"both"},
    "percent_anomaly":{
        "categorized":True,
        "nlev":11,
        "title":"Forecast anomaly as percent of normal",
        "cmap":plt.cm.BrBG,
        "vmin":-100,
        "vmax":100,
        "cbar_label":"percent",
        "levels":None,
        "whitelev":[4,5],
        "tick_labels":None,
        "extend":"max"},
    "correlation":{
        "categorized":True,
        "nlev":21,
        "title":"Pearson's correlation coefficient\n(hindcast)",
        "cmap":plt.cm.RdBu,
        "vmin":-0.5,
        "vmax":0.5,
        "cbar_label":"-",
        "levels":None,
        "whitelev":[10,11],
        "tick_labels":None,
        "extend":"both"},
    "MAPE":{
        "categorized":True,
        "nlev":11,
        "title":"Mean absolute percentage error\n(hindcast)",
        "cmap":plt.cm.Grays,
        "vmin":0,
        "vmax":20,
        "cbar_label":"percent",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"max"},
    "RMSE":{        
        "categorized":True,
        "nlev":11,
        "title":"Root mean square error\n(hindcast)",
        "cmap":plt.cm.Grays,
        "vmin":0,
        "vmax":100,
        "cbar_label":"mm",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"max"},
    "ROC_above":{
        "categorized":True,
        "nlev":11,
        "title":"ROC score for above normal category\n(hindcast)",
        "cmap":plt.cm.RdBu,
        "vmin":0,
        "vmax":1,
        "cbar_label":"score",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"neither"},
    "ROC_normal":{
        "categorized":True,
        "nlev":11,
        "title":"ROC score for normal category\n(hindcast)",
        "cmap":plt.cm.RdBu,
        "vmin":0,
        "vmax":1,
        "cbar_label":"score",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"neither"},
    "ROC_below":{
        "categorized":True,
        "nlev":11,
        "title":"ROC score for above normal category\n(hindcast)",
        "cmap":plt.cm.RdBu,
        "vmin":0,
        "vmax":1,
        "cbar_label":"score",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"neither"},
    "rpss":{
        "categorized":True,
        "nlev":11,
        "title":"RPSS score\n(hindcast)",
        "cmap":plt.cm.RdBu,
        "vmin":-1,
        "vmax":1,
        "cbar_label":"score",
        "levels":None,
        "whitelev":[4,5],
        "tick_labels":None,
        "extend":"neither"},
    "normal":{
        "categorized":True,
        "nlev":11,
        "title":"Forecast probability of normal category",
        "cmap":plt.cm.Grays,
        "vmin":0,
        "vmax":1,
        "cbar_label":"probability",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"neither"},
    "below":{
        "categorized":True,
        "nlev":11,
        "title":"Forecast probability of below normal category",
        "cmap":plt.cm.Grays,
        "vmin":0,
        "vmax":1,
        "cbar_label":"probability",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"neither"},
    "above":{
        "categorized":True,
        "nlev":11,
        "title":"Forecast probability of above normal category",
        "cmap":plt.cm.Grays,
        "vmin":0,
        "vmax":1,
        "cbar_label":"probability",
        "levels":None,
        "whitelev":[],
        "tick_labels":None,
        "extend":"neither"},
    "cem_category":{
        "categorized":False,
        "nlev":None,
        "title":"Forecast category \n(four category forecast)",
        "cmap":colors.ListedColormap(['#d2b48c', 'yellow','#0bfffb', 'blue']),
        "vmin":0,
        "vmax":4,
        "cbar_label":"category",
        "levels":np.array([1,2,3,4])-0.5,
        "whitelev":[],
        "tick_labels":['BN', 'N-BN','N-AN','AN'],
        "extend":"neither"},
    "tercile_category":{
        "categorized":False,        
        "nlev":None,
        "title":"Forecast category (tercile)",
        "cmap":colors.ListedColormap(['#d2b48c', '0.8','blue']),
        "vmin":0,
        "vmax":3,
        "cbar_label":"category",
        "levels":np.array([1,2,3])-0.5,
        "whitelev":[],
        "tick_labels":['BN', 'N', 'AN'],
        "extend":"neither"}
}

        
    
    
def plotMaps(_scores, _geoData, _geoData0,_figuresDir, _forecastID, _zonesVector, _overlayVector=None):
    if gl.targetType=="grid":
        scoresxr=_scores.unstack().to_xarray().transpose("category","lat","lon")
        for score in scoresxr.category.values:
            outfile=Path(_figuresDir,"{}_{}_{}.jpg".format(gl.config['predictandVar'], score, _forecastID))
            #showMessage("plotting {}".format(outfile))
            fig=plt.figure(figsize=(5,5))
            pl=fig.add_subplot(1,1,1, projection=ccrs.PlateCarree())

            colorbar=False
            cm=colormaps[score]
            title=cm["title"]
            cmap=cm["cmap"]
            vmin=cm["vmin"]
            vmax=cm["vmax"]
            levels=cm["levels"]
            cbar_label=cm["cbar_label"]
            extend=cm["extend"]
            tick_labels=cm["tick_labels"]
            
            # add colorbar
            if cm["categorized"]:
                cmap,norm=getCmap(cm)
            else:
                cmap=cm["cmap"]
                norm = colors.Normalize(vmin=vmin, vmax=vmax)

                
            m=scoresxr.sortby("lat").sortby("lon").sel(category=score).plot(cmap=cmap, vmin=vmin,vmax=vmax, add_colorbar=colorbar)
            
            ax=fig.add_axes([0.82,0.25,0.03,0.6])
            
            if levels is None:
                cbar = fig.colorbar(m, cax=ax, label=cbar_label, extend=extend)
            else:
                cbar = fig.colorbar(m, cax=ax,ticks=levels, label=cbar_label, extend=extend)
                
            if tick_labels is not None:
                cbar.ax.set_yticklabels(tick_labels)
                
                
            if not _zonesVector is None:
                _zonesVector.boundary.plot()

            if not _overlayVector is None:
                _overlayVector.boundary.plot(ax=pl, color='black', linewidth=0.3)
                
            pl.set_title(title)
            
            plt.subplots_adjust(right=0.8)
            plt.savefig(outfile)
            plt.close()
            #showMessage("done")
         
    if gl.targetType=="zones":
        _geodata=_geoData.copy().join(_scores.T)
        for score in _scores.index:
            print(score)
            outfile=Path(_figuresDir,"{}_{}_{}.jpg".format(gl.config['predictandVar'], score, _forecastID))
            #showMessage("plotting {}".format(outfile))
            fig=plt.figure(figsize=(5,5))
            pl=fig.add_subplot(1,1,1, projection=ccrs.PlateCarree())

            colorbar=False
            cm=colormaps[score]
            title=cm["title"]
            vmin=cm["vmin"]
            vmax=cm["vmax"]
            
            levels=cm["levels"]
            cbar_label=cm["cbar_label"]
            extend=cm["extend"]
            tick_labels=cm["tick_labels"]
            
            # add colorbar
            if cm["categorized"]:
                cmap,norm=getCmap(cm)
            else:
                cmap=cm["cmap"]
                norm = colors.Normalize(vmin=vmin, vmax=vmax)
                
            cbar = plt.cm.ScalarMappable(norm=norm, cmap=cmap)

            m=_geodata.plot(column=score, cmap=cmap, legend=False, ax=pl, norm=norm)
            _geodata.boundary.plot(ax=pl)
            
            ax=fig.add_axes([0.82,0.25,0.03,0.6])
            
            
            if levels is None:
                # add colorbar
                ax_cbar = fig.colorbar(cbar, cax=ax, label=cbar_label, extend=extend)
            else:
                ax_cbar = fig.colorbar(cbar, cax=ax,ticks=levels, label=cbar_label, extend=extend)
                
            if tick_labels is not None:
                ax_cbar.ax.set_yticklabels(tick_labels)
                
            pl.set_title(title)

            if not _overlayVector is None:
                _overlayVector.boundary.plot(ax=pl, color='black', linewidth=0.3)
            plt.subplots_adjust(right=0.8)                
            plt.savefig(outfile)
            plt.close()
            #showMessage("done")
            
    if gl.targetType=="points":
        _geodata=_geoData.copy().join(_scores.T)
        for score in _scores.index:
            outfile=Path(_figuresDir, "{}_{}_{}.jpg".format(gl.config['predictandVar'], score, _forecastID))
            #showMessage("plotting {}".format(outfile))
            fig=plt.figure(figsize=(5,5))
            pl=fig.add_subplot(1,1,1, projection=ccrs.PlateCarree())
            
            colorbar=False
            cm=colormaps[score]
            title=cm["title"]
            cmap=cm["cmap"]
            vmin=cm["vmin"]
            vmax=cm["vmax"]
            levels=cm["levels"]
            cbar_label=cm["cbar_label"]
            extend=cm["extend"]
            tick_labels=cm["tick_labels"]
            
            # add colorbar
            if cm["categorized"]:
                cmap,norm=getCmap(cm)
            else:
                cmap=cm["cmap"]
                norm = colors.Normalize(vmin=vmin, vmax=vmax)
            
            m=_geodata.plot(column=score, cmap=cmap, legend=False, ax=pl, edgecolor='black', linewidth=0.5)
            
            ax=fig.add_axes([0.82,0.25,0.03,0.6])
            
            # add colorbar
            norm = colors.Normalize(vmin=vmin, vmax=vmax)
            cbar = plt.cm.ScalarMappable(norm=norm, cmap=cmap)

            if levels is None:
                # add colorbar
                ax_cbar = fig.colorbar(cbar, cax=ax, label=cbar_label, extend=extend)
            else:
                ax_cbar = fig.colorbar(cbar, cax=ax,ticks=levels, label=cbar_label, extend=extend)
                
            if tick_labels is not None:
                ax_cbar.ax.set_yticklabels(tick_labels)
                
            
            if not _zonesVector is None:
                _zonesVector.boundary.plot(ax=pl)
                
            if not _overlayVector is None:
                _overlayVector.boundary.plot(ax=pl, color='black', linewidth=0.3)
                
            pl.set_title(title)
                
            plt.subplots_adjust(right=0.8)
            plt.savefig(outfile)
            plt.close()
            #showMessage("done")   

            
            
            
            
def plotTimeSeries(_dethcst,_obs, _detfcst, _tercthresh, _figuresdir, _forecastid):
    if gl.targetType in ["zones","points"]:
        for entry in _obs.columns:
            _entry=sanitize_string(str(entry))
            outfile=Path(_figuresdir,"{}_{}_{}.jpg".format(gl.config['predictandVar'], _entry, _forecastid))
            #showMessage("plotting {}".format(outfile))

            fig=plt.figure(figsize=(7,4))
            pl=fig.add_subplot(1,1,1)

            _obs[entry].plot(marker="o", label="observed", markersize=3)
            _dethcst[entry].plot(label="deterministic hindcast", markersize=3)
            _detfcst["value"][entry].plot(marker="o",label="forecast", markersize=8)
            pl.axhline(_tercthresh.loc[0.33][entry], color="0.6")
            pl.axhline(_tercthresh.loc[0.66][entry], color="0.6", label="climatological terciles")
            pl.axhline(_tercthresh.loc[0.50][entry], color="0.8", label="climatological median")
            pl.set_title("Hindcast and forecast for {} in {} in region: {}\nissued in {}".format(gl.config["predictandVar"], gl.config["fcstTargetSeas"],entry,gl.predictorDate.strftime("%b %Y")))
            pl.set_xlim((_obs.index[0]-pd.offsets.YearBegin(2)).strftime("%Y-%m-%d"), (_detfcst.index[0]+pd.offsets.YearBegin(2)).strftime("%Y-%m-%d")
)
            plt.legend()
            
            plt.savefig(outfile)            
            plt.close()
        #showMessage("done")
    else:    
        showMessage("Forecasting target is a grid, time series cannot be plotted.", "INFO")


def getTercCategory(_data):
    if gl.targetType=="grid":
        temp=_data.stack(level=[1,2], future_stack=True).idxmax(axis=1).unstack(level=[1,2]).map(lambda x: terc2num[x])
        #add a level to multiindex
        temp.columns=pd.MultiIndex.from_tuples([('tercile_category',) + col for col in temp.columns], names=["category"] + list(temp.columns.names))

    else:
        temp=_data.stack(future_stack=True).idxmax(axis=1).unstack().map(lambda x: terc2num[x])
        temp.columns=pd.MultiIndex.from_tuples([('tercile_category',col) for col in temp.columns], names=["category",temp.columns.name])

    return temp


def getCemCategory(_data):
    if gl.targetType=="grid":
    
        stacked = _data.stack(level=[1, 2], future_stack=True)

        # Convert to numpy array
        vals = stacked.to_numpy()

        # argsort sorts ascending → take [:, ::-1] for descending
        order_idx = np.argsort(vals, axis=1)[:, ::-1]

        # Get the original column labels in sorted order
        col_array = np.array(stacked.columns)
        ordered_labels = col_array[order_idx]

        # Make a DataFrame with desired column names
        order = pd.DataFrame(
            ordered_labels[:, :3],  # top 3
            index=stacked.index,
            columns=["first", "second", "third"]
        )

        temp=order["first"].copy()
        sel=temp=="normal"
        temp[sel]="normal-to-"+order["second"][sel]
        temp=temp.map(lambda x: cem2num[x])
        temp=temp.unstack(level=["lat","lon"])
        temp.columns=pd.MultiIndex.from_tuples([('cem_category',) + col for col in temp.columns], names=["category"] + list(temp.columns.names))
    else:
        stacked = _data.stack(future_stack=True)

        # Convert to numpy array
        vals = stacked.to_numpy()

        # argsort sorts ascending → take [:, ::-1] for descending
        order_idx = np.argsort(vals, axis=1)[:, ::-1]

        # Get the original column labels in sorted order
        col_array = np.array(stacked.columns)
        ordered_labels = col_array[order_idx]

        # Make a DataFrame with desired column names
        order = pd.DataFrame(
            ordered_labels[:, :3],  # top 3
            index=stacked.index,
            columns=["first", "second", "third"]
        )

        temp=order["first"].copy()
        sel=temp=="normal"
        temp[sel]="normal-to-"+order["second"][sel]
        temp=temp.map(lambda x: cem2num[x])
        
        temp=temp.unstack()
        temp.columns=pd.MultiIndex.from_tuples([('cem_category',col) for col in temp.columns], names=["category", temp.columns.name])

    return temp  



class PCRegressor(BaseEstimator, RegressorMixin):
    
    def __init__(self, regressor_name=None, fit_intercept=True, max_fraction=0.15, pca_explained_var=0.95, **regressor_kwargs):
        self.max_fraction = max_fraction
        self.fit_intercept = fit_intercept
        self.pca_explained_var = pca_explained_var
        self.regressor_name = regressor_name
        self.regressor_kwargs = regressor_kwargs
        self.scaleX=StandardScaler()
        self.pcaX = PCA()
        self.reg=self._get_regressor()
        
    def _get_regressor(self):

        if self.regressor_name not in regressors:
            raise ValueError(f"Unknown regressor '{self.regressor_name}'.")
        reg_class=regressors[self.regressor_name]
        
        # Inspect constructor to see if 'fit_intercept' is accepted
        sig = inspect.signature(reg_class.__init__)
        kwargs = self.regressor_kwargs.copy()
        if 'fit_intercept' in sig.parameters:
            kwargs['fit_intercept'] = self.fit_intercept
            self.supports_intercept=True
        else:
            self.supports_intercept=False
            
        return reg_class(**kwargs)
        
    def fit(self, X, Y):
        
        #scaling the predictor
        X_std=self.scaleX.fit_transform(X)
        
        #PCA on predictor
        #X_c holds scores
        X_c = self.pcaX.fit_transform(X_std)
        
        #selecting PCA components
        #
        cumvar = np.cumsum(self.pcaX.explained_variance_ratio_)
        n_samples=X.shape[0]
        
        #number of components should not exceed a fraction of the number of data
        max_data_comp=int(self.max_fraction*n_samples)
        
        # number of components that explain target fraction of variance
        max_var_comp=np.argmax(cumvar >= self.pca_explained_var) + 1
        
        #final number of components - the lower of the two
        ncompX=int(np.ceil(np.min([max_data_comp, max_var_comp])))
        
        X_c=X_c[:,:ncompX]
        
        #retaining scores # shape (n_samples, n_components)
        self.scores=X_c
        
        #retaining loadings # shape (n_features, n_components)
        self.loadings = self.pcaX.components_.T[:,:ncompX]
        
        #retaining number of components kept
        self.ncompX=ncompX
        
        #fitting regression model
        self.reg.fit(X_c, Y)
        
        return self

    
    def predict(self, X):
        #scale as per fitted model    
        X_c = self.scaleX.transform(X)
        #PCA trasform as per fitted model
        X_c = self.pcaX.transform(X_c)
        #select only retained PC components
        X_c=X_c[:,:self.ncompX]
        
        #predict with model
        Y_pred=self.reg.predict(X_c)

        return Y_pred
    
    
class CCARegressor(BaseEstimator, RegressorMixin):
    
    def __init__(self, n_components=None, regressor_name=None, fit_intercept=True, max_fraction=0.15,pca_explained_var=0.95, **regressor_kwargs):
        self.n_components = n_components
        self.max_fraction = max_fraction
        self.fit_intercept = fit_intercept
        self.pca_explained_var = pca_explained_var
        self.regressor_name = regressor_name
        self.regressor_kwargs = regressor_kwargs
        self.scaleX=StandardScaler()
        self.scaleY=StandardScaler()
        self.pcaX = PCA()
        self.pcaY = PCA()
        self.reg=self._get_regressor()        
        
    def _get_regressor(self):

        if self.regressor_name not in regressors:
            raise ValueError(f"Unknown regressor '{self.regressor_name}'.")
            
        reg_class=regressors[self.regressor_name]
        
        # Inspect constructor to see if 'fit_intercept' is accepted
        sig = inspect.signature(reg_class.__init__)
        kwargs = self.regressor_kwargs.copy()
        if 'fit_intercept' in sig.parameters:
            kwargs['fit_intercept'] = self.fit_intercept
            self.supports_intercept=True
        else:
            self.supports_intercept=False
      
        return reg_class(**kwargs)

    
    def fit(self, X, Y):
        #scaling predictor and predictand        
        X_std=self.scaleX.fit_transform(X)
        Y_std=self.scaleY.fit_transform(Y)
        
        X_c = self.pcaX.fit_transform(X_std)
        cumvar = np.cumsum(self.pcaX.explained_variance_ratio_)

        # Choose number of components that explain X % - for PCA that enters CCA 
        ncompX=np.argmax(cumvar >= self.pca_explained_var) + 1
        X_c=X_c[:,:ncompX]
        self.ncompX=ncompX
        
        Y_c = self.pcaY.fit_transform(Y_std)
        cumvar = np.cumsum(self.pcaY.explained_variance_ratio_)
        
        # Choose number of components that explain Y % - for PCA that enters CCA
        ncompY = np.argmax(cumvar >= self.pca_explained_var) + 1
        Y_c=Y_c[:,:ncompY]
        self.ncompY=ncompY
        
        #setting up number of components for CCA
        n_samples=X.shape[0]
        if self.n_components is None:
            max_allowed = int(np.floor(self.max_fraction * n_samples))
            self.n_components = min(self.ncompX, self.ncompY, max_allowed)

        #initializing cca once we know how many components we need
        self.cca = CCA(n_components=self.n_components)

        #fitting CCA
        self.cca.fit(X_c, Y_c)
        X_c, Y_c = self.cca.transform(X_c, Y_c)
        
        #retaining CCA scores
        self.scoresX=X_c
        self.scoresY=Y_c
        
        #retaining canonical patterns
        self.can_pattern_X = self.pcaX.components_[:ncompX, :].T @ self.cca.x_weights_
        self.can_pattern_Y = self.pcaY.components_[:ncompY, :].T @ self.cca.y_weights_

        #fitting regression model
        self.reg.fit(X_c, Y_c)
        
        return self

    
    def predict(self, X):
        #scale    
        X_c = self.scaleX.transform(X)
        #PCA trasform
        X_c = self.pcaX.transform(X_c)
        #select only retained PC components
        X_c=X_c[:,:self.ncompX]
        #CCA transform
        X_c = self.cca.transform(X_c)  # transform only X
        
        #predict with model
        Y_c_pred=self.reg.predict(X_c)
        
        # Inverse transform to get prediction in original Y space
        #invert CCA
        Y_pred = Y_c_pred @ self.cca.y_rotations_.T
        #invert PCA
        selComponents = self.pcaY.components_[0:self.ncompY]
        Y_pred = Y_pred @ selComponents
        #invert scaling
        Y_pred = self.scaleY.inverse_transform(Y_pred)
        

        return Y_pred
    

def writeOutput(_data, _outputfile):
    if gl.targetType=="grid":
        _data.to_netcdf(_outputfile)
    else:
        _data.to_csv(_outputfile)
    #showMessage("written {}".format(_outputfile), "INFO")
    return    


def plotDiagsCCA(_regressor, predictorhcst, predictandhcst, _diagsdir, _forecastid):
    #plotting predictor scores
    canpatX=_regressor.can_pattern_X 

    canpatX=pd.DataFrame(canpatX, index=predictorhcst.columns, columns=["Mode{}".format(x+1) for x in range(canpatX.shape[1])])
    canpatX=canpatX.to_xarray().sortby("lat").sortby("lon")

    for pc in canpatX.data_vars:
        outfile=Path(_diagsdir,"cannonical-pattern_predictor_{}_{}.jpg".format(pc,_forecastid))
        #showMessage("plotting {}".format(outfile))

        fig=plt.figure(figsize=(5,5))
        pl=fig.add_subplot(1,1,1)

        canpatX[pc].plot(ax=pl)
        pl.set_title("Predictor's {} pattern \n{}".format(pc, _forecastid))

        plt.savefig(outfile)            
        plt.close()

    if gl.targetType=="grid":
        canpatY=_regressor.can_pattern_Y
        
        canpatY=pd.DataFrame(canpatY, index=predictandhcst.columns, columns=["Mode{}".format(x+1) for x in range(canpatY.shape[1])])
        canpatY=canpatY.to_xarray().sortby("lat").sortby("lon")

        for pc in canpatY.data_vars:
            outfile=Path(_diagsdir,"cannonical-pattern_predictand_{}_{}.jpg".format(pc,_forecastid))
            #showMessage("plotting {}".format(outfile))

            fig=plt.figure(figsize=(5,5))
            pl=fig.add_subplot(1,1,1)

            canpatY[pc].plot(ax=pl)
            pl.set_title("Predictand's {} pattern \n{}".format(pc, _forecastid))

            plt.savefig(outfile)            
            plt.close()
        

    scoresX=_regressor.scoresX
    scoresX=pd.DataFrame(scoresX, index=predictandhcst.index, columns=["Mode{}".format(x+1) for x in range(scoresX.shape[1])])

    scoresY=_regressor.scoresY
    scoresY=pd.DataFrame(scoresY, index=predictandhcst.index, columns=["Mode{}".format(x+1) for x in range(scoresY.shape[1])])

    for mode in scoresX.columns:
        outfile=Path(_diagsdir,"CCA-scores_{}_{}.jpg".format(mode, _forecastid))
        #showMessage("plotting {}".format(outfile))

        fig=plt.figure(figsize=(7,4))
        pl=fig.add_subplot(1,1,1)

        scoresX[mode].plot(ax=pl, label="predictor")
        scoresY[mode].plot(ax=pl, label="predictand")
        pl.set_title("Scores of CCA {}\n{}".format(mode, _forecastid))
        plt.legend()

        plt.savefig(outfile)            
        plt.close()

        
    #plotting correlations        
    outfile=Path(_diagsdir,"CCA-correlations_{}.jpg".format( _forecastid))
    #showMessage("plotting {}".format(outfile))
    
    corrs = [np.corrcoef(scoresX.iloc[:, i], scoresY.iloc[:, i])[0,1] for i in range(scoresX.shape[1])]

    fig=plt.figure(figsize=(7,4))
    pl=fig.add_subplot(1,1,1)

    bars=pl.bar(range(1, len(corrs)+1), corrs)
    # annotate each bar with its value
    for bar, val in zip(bars, corrs):
        height = bar.get_height()
        pl.text(bar.get_x() + bar.get_width()/2, height + 0.02, f"{val:.2f}",
                ha='center', va='bottom')
    pl.set_ylim(0,1.1)
    pl.set_xlabel("Canonical mode")
    pl.set_ylabel("Canonical correlation")
    pl.set_title("Strength of canonical correlations")

    plt.savefig(outfile)            
    plt.close()

    
    
    
def plotDiagsPCR(_regressor, predictorhcst, predictandhcst, _diagsdir, _forecastid):
    #plotting predictor scores
    scores=_regressor.scores
    scores=pd.DataFrame(scores, index=predictandhcst.index, columns=["PC{}".format(x+1) for x in range(scores.shape[1])])

    outfile=Path(_diagsdir,"PCA-scores_predictand_{}.jpg".format(_forecastid))
    #showMessage("plotting {}".format(outfile))

    fig=plt.figure(figsize=(7,4))
    pl=fig.add_subplot(1,1,1)

    scores.plot(ax=pl)
    pl.set_title("Scores of retained PCs \n{}".format(_forecastid))

    plt.savefig(outfile)            
    plt.close()


    #plotting loadings
    loadings=_regressor.loadings
    loadings.shape

    loadings=pd.DataFrame(loadings, index=predictorhcst.columns, columns=["PC{}".format(x+1) for x in range(loadings.shape[1])])
    loadings=loadings.to_xarray().sortby("lat").sortby("lon")


    for pc in loadings.data_vars:
        outfile=Path(_diagsdir,"{}-loadings_predictand_{}.jpg".format(pc,_forecastid))
        #showMessage("plotting {}".format(outfile))

        fig=plt.figure(figsize=(5,5))
        pl=fig.add_subplot(1,1,1)

        loadings[pc].plot(ax=pl)
        pl.set_title("{} loadings \n{}".format(pc, _forecastid))

        plt.savefig(outfile)            
        plt.close()
        
        

def plotDiagsRegression(predictandhcst, cvhcst, esthcst, tercthresh, detfcst, _diagsdir, _forecastid):
    
    if gl.targetType!="grid":
        for entry in predictandhcst.columns:
            entryw=sanitize_string(str(entry))
            outfile=Path(_diagsdir,"regression-diags_{}_{}.jpg".format(entryw,_forecastid))
            fig=plt.figure(figsize=(10,6))

            pl=fig.add_subplot(2,3,1)

            obs=predictandhcst.loc[:,entry]
            hcst=cvhcst["value"].loc[:,entry]

            xmin,xmax=nice_minmax(obs,hcst)

            pl.plot(obs,hcst,"o")
            pl.set_ylim(xmin,xmax)
            pl.set_xlim(xmin,xmax)

            pl.set_xlabel("observations")
            pl.set_ylabel("out-of-sample forecast")

            pl.set_title("out-of-sample forecast \nvs observations")



            pl=fig.add_subplot(2,3,2)

            hcst=esthcst["value"].loc[:,entry]
            xmin,xmax=nice_minmax(obs,hcst)

            pl.plot(obs,hcst,"o")
            pl.set_ylim(xmin,xmax)
            pl.set_xlim(xmin,xmax)

            pl.set_xlabel("observations")
            pl.set_ylabel("in-sample estimate")

            pl.set_title("in-sample estimate \nvs observations")

            pl=fig.add_subplot(2,3,3)

            
            
            
            obs=predictandhcst.loc[:,entry]
            hcst=cvhcst["value"].loc[:,entry]
            resid=hcst-obs
            
            hcstfit=esthcst["value"].loc[:,entry]
            residfit=hcstfit-obs

            xmin,xmax=nice_minmax(obs,resid)

            pl.plot(obs,resid,"o")
            pl.set_ylim(xmin,xmax)
            pl.set_xlim(xmin,xmax)

            pl.set_xlabel("observations")
            pl.set_ylabel("out-of-sample residuals")

            pl.set_title("out-of-sample\n residual vs observations")



            
            pl=fig.add_subplot(2,3,4)

            pl.hist(resid, label="out-of-sample", alpha=0.5)
            pl.hist(residfit, label="in-sample", alpha=0.5)

            pl.set_xlabel("residuals")
            pl.set_ylabel("frequency")

            pl.set_title("error distribution")

            plt.legend()
            
            
            
            pl=fig.add_subplot(2,3,5)
            
            hcst=cvhcst["value"].loc[:,entry]
            
            resid=hcst-obs
            
            fcst=detfcst["value"].loc[:,entry]

            error=fcst.values+resid
            
            pl.hist(error, label="forecast error", alpha=0.5)
            
            pl.axvline(fcst.values, color="red", label="forecast")
            
            pl.axvline(tercthresh.loc[0.33][entry], color="blue", label="terciles")
            pl.axvline(tercthresh.loc[0.66][entry], color="blue", label="_terciles")
            

            pl.set_xlabel("value")
            pl.set_ylabel("frequency")
            plt.legend()
            pl.set_title("forecast error distribution")

            
            plt.suptitle("zone/location: {} \n{}\n".format(entry, _forecastid))
            
            plt.subplots_adjust(top=0.85, left=0.1, right=0.9, wspace=0.5, hspace=0.5)
            plt.savefig(outfile)
            plt.close()


def nice_minmax(x,y):
    # 1. Get global min and max
    data_min = min(np.min(x), np.min(y))
    data_max = max(np.max(x), np.max(y))

    # 2. Add padding
    padding = 0.05 * (data_max - data_min)
    raw_min = data_min - padding
    raw_max = data_max + padding

    # 3. Round to "nice" numbers (nearest power of 10 multiples)
    def nice_limits(vmin, vmax):
        rng = vmax - vmin
        exp = int(np.floor(np.log10(rng)))  # order of magnitude
        step = 10 ** exp
        vmin = np.floor(vmin / step) * step
        vmax = np.ceil(vmax / step) * step
        return vmin, vmax

    lims = nice_limits(raw_min, raw_max)
    return lims    

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

    
def checkInputs():

    if gl.config["rootDir"]=="":
        showMessage("output directory cannot be empty", "ERROR")
        return
    else:
        if not os.path.exists(gl.config["rootDir"]):
            showMessage("output directory does not exist", "ERROR")
            return    
    
    if not is_number(gl.config["predictorYear"]):
        showMessage("predictor year should be numeric", "ERROR")
        return
    
    if not is_number(gl.config["fcstTargetYear"]):
        showMessage("predictand year should be numeric", "ERROR")
        return
    
    if not is_number(gl.config["climEndYr"]):
        showMessage("last year of climatological period should be numeric", "ERROR")
        return
    
    if not is_number(gl.config["climStartYr"]):
        showMessage("first year of climatological period should be numeric", "ERROR")
        return
    
    if gl.config["predictandFileName"]=="":
        showMessage("predictand file cannot be empty", "ERROR")
        return
    elif not os.path.exists(gl.config["predictandFileName"]):
        showMessage("predictand file does not exist", "ERROR")
        return
    
    if gl.config["predictandVar"]=="":
        showMessage("predictand variable cannot be empty", "ERROR")
        return
    
    if gl.config["zonesAggregate"]:
        if gl.config["zonesFile"]!="":
            if not os.path.exists(gl.config["zonesFile"]):
                showMessage("Aggregation to zones is selected. But zones file does not exist", "ERROR")
                return    
        
        if gl.config["zonesAttribute"]=="":
            showMessage("Aggregation to zones is selected.  But zones variable is empty", "ERROR")
            return
        
    if gl.config["overlayFile"]!="":
        if not os.path.exists(gl.config["overlayFile"]):
            showMessage("overlay file does not exist", "ERROR")
            return
        
    for model in range(len(gl.config['predictorFiles'])):
        file=gl.config['predictorFiles'][model][0]
        var=gl.config['predictorFiles'][model][1]
        code=gl.config['predictorFiles'][model][2]
        
        extents=gl.config['predictorExtents'][model]
        south=extents["minLat"]
        north=extents["maxLat"]
        west=extents["minLon"]
        east=extents["maxLon"]        
        
        if file=="":
            showMessage("predictor file cannot be empty", "ERROR")
            return
        elif not os.path.exists(file):
            showMessage("predictor file does not exist", "ERROR")
            return
        
        if var=="":
            showMessage("predictor variable cannot be empty. Please repeat selection of predictor file", "ERROR")
            return

        if code=="":
            showMessage("predictor code cannot be empty. Please repeat selection of predictor file or add code to the input box manually", "ERROR")
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
        
    return True
