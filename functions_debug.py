"""
@author: thembani
"""
import os, re, time
import pandas as pd
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Patch
from sklearn import linear_model, cluster
import statsmodels.api as sm
from scipy.stats import pearsonr
from shapely.geometry import shape, Point, Polygon
from descartes import PolygonPatch
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPRegressor
from netCDF4 import Dataset
from dateutil.relativedelta import relativedelta
from datetime import datetime
from pathlib import Path
import warnings
import numpy as np
import geojson, json
import untangle

SSTclusterSize=1200.
kms_per_radian = 6371.0088
epsilon = SSTclusterSize*1.0 / kms_per_radian

# --- constants ---
months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
seasons = ['JFM', 'FMA', 'MAM', 'AMJ', 'MJJ', 'JJA', 'JAS', 'ASO', 'SON', 'OND', 'NDJ', 'DJF']
month_dict = {'jan':'01','feb':'02','mar':'03','apr':'04','may':'05','jun':'06','jul':'07',
              'aug':'08','sep':'09','oct':'10','nov':'11','dec':'12'}
proj='GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],' \
     'AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433],' \
     'AUTHORITY["EPSG","4326"]]'
season_start_month = {'Jan': 'JFM', 'Feb': 'FMA', 'Mar': 'MAM', 'Apr': 'AMJ', 'May': 'MJJ', 'Jun': 'JJA', 'Jul': 'JAS',
                     'Aug': 'ASO', 'Sep': 'SON', 'Oct': 'OND', 'Nov': 'NDJ', 'Dec': 'DJF'}
season_months = {'JFM': ['Jan', 'Feb', 'Mar'], 'FMA': ['Feb', 'Mar', 'Apr'], 'MAM': ['Mar', 'Apr', 'May'],
                 'AMJ': ['Apr', 'May', 'Jun'], 'MJJ': ['May', 'Jun', 'Jul'], 'JJA': ['Jun', 'Jul', 'Aug'],
                 'JAS': ['Jul', 'Aug', 'Sep'], 'ASO': ['Aug', 'Sep', 'Oct'], 'SON': ['Sep', 'Oct', 'Nov'],
                 'OND': ['Oct', 'Nov', 'Dec'], 'NDJ': ['Nov', 'Dec', 'Jan'], 'DJF': ['Dec', 'Jan', 'Feb']}


# --- functions ---

def rename(string):
    return re.sub("[^0-9a-zA-Z]+", " ", str(string)).strip()

def integer(x):
    if np.isfinite(x):
        return int(round(x,0))
    else:
        return np.nan

    
class csv_data:
    def __init__(self, file, month, param = 'val'):
        self.X, self.Y, self.lons, self.lats = None, None, None, None
        self.file = file
        self.param = param
        self.month = month.lower()
        if self.is_csv():
            self.dataset = pd.read_csv(file)
        else:
            self.dataset = pd.read_csv(file, delimiter=r"\s+")
        self.dataset.columns = self.dataset.columns.str.lower()
        if self.month not in self.dataset.columns:
            raise ValueError('column "' + self.month + '" not detected in predictor csv. check format')
        if 'year' not in self.dataset.columns:
            self.dataset.index.rename('year', inplace=True)
            self.dataset.reset_index(inplace=True)
        
    def is_csv(self):
        f = open(self.file, "r")
        lines = f.read()
        f.close()
        if lines.count(',') > 1:
            return 1
        else:
            return 0

    def var(self):
        keys = []
        for key in self.keys:
            keys.append(key)
        ref_keys = ['Y', 'X', 'Z', 'T', 'zlev', 'time', 'lon', 'lat']
        for x in reversed(range(len(keys))):
            if keys[x] not in ref_keys:
                return keys[x]
        return None

    def tslice(self):
        return self.dataset[self.month]

    def times(self):
        timearr = []
        mon = datetime.strptime(self.month, '%b').strftime('%m')
        tarr = self.dataset['year']
        timearr = [str(tarr[x]) + str(mon) + '01' for x in range(len(tarr))]
        return timearr

    def years(self):
        return sorted(list(set([x[:4] for x in self.times()])))

    def months(self):
        return sorted(list(set([x[:6] for x in self.times()])))

    def shape(self):
        return(0, 0)



class netcdf_data:
    # NB: NetCDF reads from the bottom going up
    def __init__(self, file, param=None, level=0):
        self.X, self.Y, self.lons, self.lats = None, None, None, None
        self.file = file
        self.param = param
        self.level = level
        self.dataset = Dataset(file)
        self.keys = self.dataset.variables.keys()
        self.dimensions = self.dataset.dimensions.keys()
        if 'T' in self.keys:
            self.tpar = 'T'
        elif 'time' in self.keys:
            self.tpar = 'time'
        if 'X' in self.keys:
            self.X = 'X'
        elif 'lon' in self.keys:
            self.X = 'lon'
        if 'Y' in self.keys:
            self.Y = 'Y'
        elif 'lat' in self.keys:
            self.Y = 'lat'
        self.tunits = str(self.dataset.variables[self.tpar].units).split(" since ", 1)[0]
        ref_date = str(self.dataset.variables[self.tpar].units).split(" since ", 1)[1]
        self.ref_date = datetime.strptime(ref_date, '%Y-%m-%d')
        if self.X is not None: self.lons = self.dataset.variables[self.X][:]
        if self.Y is not None: self.lats = self.dataset.variables[self.Y][:]
        if param is None:
            self.param = self.var()
        if self.param not in self.keys:
            print(param, 'not available in the dataset')


    def var(self):
        keys = []
        for key in self.keys:
            keys.append(key)
        ref_keys = ['Y', 'X', 'Z', 'T', 'zlev', 'time', 'lon', 'lat']
        for x in reversed(range(len(keys))):
            if keys[x] not in ref_keys:
                return keys[x]
        return None

    def tslice(self, x=None, y=None):
        if x is None and y is None:
            if len(self.dimensions) == 3 or len(self.dimensions) == 1:
                data = self.dataset.variables[self.param][:]
            elif len(self.dimensions) == 4 or len(self.dimensions) == 2:
                data = self.dataset.variables[self.param][:, self.level]
            else:
                return None
            try:
                data[data.mask] = np.nan
                return data
            except:
                return data

        if x is not None and y is not None:
            if len(self.dimensions) == 3:
                data = self.dataset.variables[self.param][:, x, y]
            elif len(self.dimensions) == 4:
                data = self.dataset.variables[self.param][:, self.level, x, y]
            else:
                return None
            try:
                data[data.mask] = np.nan
                return list(data)
            except:
                return list(data)

    def times(self):
        timearr = []
        tarr = self.dataset.variables[self.tpar][:]
        for x in range(len(tarr)):
            if self.tunits == 'months':
                timearr.append((self.ref_date + relativedelta(months=+int(tarr[x]))).strftime("%Y%m%d"))
            if self.tunits == 'days':
                timearr.append((self.ref_date + relativedelta(days=+int(tarr[x]))).strftime("%Y%m%d"))
        return timearr

    def years(self):
        return sorted(list(set([x[:4] for x in self.times()])))

    def months(self):
        return sorted(list(set([x[:6] for x in self.times()])))

    def shape(self, lenX = 0, lenY = 0):
        if self.X is not None: lenX = len(self.lons)
        if self.Y is not None: lenY = len(self.lats)
        return(lenY, lenX)

def plot_forecast_png(lats, lons, fcst, title, qmlfile, base_vector, outputfile):
    if not os.path.exists(qmlfile):
        return
    # design colormap
    qml = untangle.parse(qmlfile)
    color, value, svalue, label = [],[],[],[]
    for item in qml.qgis.pipe.rasterrenderer.rastershader.colorrampshader.item:
      color.append(str(item['color']))
      value.append(float(item['value']))
      svalue.append(str(item['value']))
      label.append(str(item['label']))

    svalue.insert(0,str(value[0]-value[1]))
    cmap = mcolors.ListedColormap(color)
    num = len(value)
    value.append(value[num-1]+abs(value[num-2]))
    norm = mcolors.BoundaryNorm(value, len(value)-1)
    
    # prepare map figure
    DPI, W, H = 100, 1200, 1200
    xmin = lons.min()
    xmax = lons.max()
    ymin = lats.min()
    ymax = lats.max()
    major_lons, minor_lons = [], []
    major_lats, minor_lats = [], []
    for x in range(round(xmin), int(xmax), 1):
       if (xmax - xmin) > 10:
           if x % 10 == 0: major_lons.append(x)
           if (x % 5 == 0) and (x % 10 != 0): minor_lons.append(x)
       else:
           if x % 2 == 0: major_lons.append(x)
           if (x % 1 == 0) and (x % 2 != 0): minor_lons.append(x)

    for y in range(int(ymin), int(ymax), 1):
       if (ymax - ymin) > 10:
           if y % 10 == 0: major_lats.append(y)
           if (y % 5 == 0) and (y % 10 != 0): minor_lats.append(y)
       else:
           if y % 2 == 0: major_lats.append(y)
           if (y % 1 == 0) and (y % 2 != 0): minor_lats.append(y)
    
    H = W * (ymax - ymin) / (xmax - xmin)
    # create and plot map figure
    fig = plt.figure(figsize=(W/float(DPI), H/float(DPI)), frameon=True, dpi=DPI)
    ax = fig.add_subplot(111)
    x, y = np.meshgrid(lons, lats)
    cs = plt.pcolormesh(x,y,fcst,cmap=cmap,norm=norm, shading='auto')
    if base_vector.exists():
        # open base map to get bounds
        with open(base_vector, "r") as read_file:
            base_map = geojson.load(read_file)
        for feature in base_map['features']:
            poly = feature['geometry']
            ax.add_patch(PolygonPatch(poly, fc=None, fill=False, ec='#8f8f8f', alpha=1., zorder=2))
        ax.set_xlim([xmin, xmax])
        ax.set_ylim([ymin, ymax])
    plt.title(title, fontsize=10)
    plt.xlabel('Longitude', fontsize=8)
    plt.ylabel('Latitude', fontsize=8)
    cax = fig.add_axes([0.05,0.04,0.93,0.02])
    cbar = plt.colorbar(cs, cax=cax, spacing='uniform', pad=0.01, orientation='horizontal')
    cbar.set_ticks(value)
    label.append('')
    cbar.ax.set_xticklabels(label, ha='center', minor=False)
    labelen = len(str(label))
    fontsize = 11
    if labelen >= 100 : fontsize = 9
    if labelen >= 130 : fontsize = 8
    if labelen >= 160 : fontsize = 7
    if labelen >= 200 : fontsize = 6
    cbar.ax.tick_params(labelsize=fontsize)
    if len(major_lons) > 0: ax.set_xticks(major_lons)
    if len(minor_lons) > 0: ax.set_xticks(minor_lons, minor=True)
    if len(major_lats) > 0: ax.set_yticks(major_lats)
    if len(minor_lats) > 0: ax.set_yticks(minor_lats, minor=True)
    ax.grid(which='major', alpha=0.1)
    ax.grid(which='minor', alpha=0.05)
    plt.savefig(outputfile, bbox_inches = 'tight')
    plt.close(fig)
    


def season_cumulation(dfm, year, season):
        nyear = year + 1
    #try:
        if season == 'JFM':
            if ~np.isnan(np.ravel(dfm.loc[[year], 'Jan':'Mar']).astype(float)).any(): return np.round(
                dfm.loc[[year], 'Jan':'Mar'].sum(axis=1).astype(float), 1)
        if season == 'FMA':
            if ~np.isnan(np.ravel(dfm.loc[[year], 'Feb':'Apr']).astype(float)).any(): return np.round(
                dfm.loc[[year], 'Feb':'Apr'].sum(axis=1).astype(float), 1)
        if season == 'MAM':
            if ~np.isnan(np.ravel(dfm.loc[[year], 'Mar':'May']).astype(float)).any(): return np.round(
                dfm.loc[[year], 'Mar':'May'].sum(axis=1).astype(float), 1)
        if season == 'AMJ':
            if ~np.isnan(np.ravel(dfm.loc[[year], 'Apr':'Jun']).astype(float)).any(): return np.round(
                dfm.loc[[year], 'Apr':'Jun'].sum(axis=1).astype(float), 1)
        if season == 'MJJ':
            if ~np.isnan(np.ravel(dfm.loc[[year], 'May':'Jul']).astype(float)).any(): return np.round(
                dfm.loc[[year], 'May':'Jul'].sum(axis=1).astype(float), 1)
        if season == 'JJA':
            if ~np.isnan(np.ravel(dfm.loc[[year], 'Jun':'Aug']).astype(float)).any(): return np.round(
                dfm.loc[[year], 'Jun':'Aug'].sum(axis=1).astype(float), 1)
        if season == 'JAS':
            if ~np.isnan(np.ravel(dfm.loc[[year], 'Jul':'Sep']).astype(float)).any(): return np.round(
                dfm.loc[[year], 'Jul':'Sep'].sum(axis=1).astype(float), 1)
        if season == 'ASO':
            if ~np.isnan(np.ravel(dfm.loc[[year], 'Aug':'Oct']).astype(float)).any(): return np.round(
                dfm.loc[[year], 'Aug':'Oct'].sum(axis=1).values, 1)
        if season == 'SON':
            if ~np.isnan(np.ravel(dfm.loc[[year], 'Sep':'Nov']).astype(float)).any(): return np.round(
                dfm.loc[[year], 'Sep':'Nov'].sum(axis=1).astype(float), 1)
        if season == 'OND':
            if ~np.isnan(np.ravel(dfm.loc[[year], 'Oct':'Dec']).astype(float)).any(): return np.round(
                dfm.loc[[year], 'Oct':'Dec'].sum(axis=1).astype(float), 1)
        if season == 'NDJ':
            p1 = ~np.isnan(np.ravel(dfm.loc[[year], 'Nov':'Dec']).astype(float)).any()
            p2 = ~np.isnan(np.ravel(dfm.loc[[nyear], 'Jan']).astype(float)).any()
            
            if p1 and p2: 
                aggr=np.round(dfm.loc[[nyear], 'Jan'].values + dfm.loc[[year], 'Nov':'Dec'].sum(axis=1).values,1)
                return aggr 

        if season == 'DJF':
            p1 = ~np.isnan(np.ravel(dfm.loc[[year], 'Dec']).astype(float)).any()
            p2 = ~np.isnan(np.ravel(dfm.loc[[nyear], 'Jan':'Feb']).astype(float)).any()
            if p1 and p2: 
                aggr=np.round(dfm.loc[[year], 'Dec'].values + dfm.loc[[nyear], 'Jan':'Feb'].sum(axis=1).values,1)
                return aggr 
        return
   # except:
        print("could not calculate season accumulation", year, season)
        
        return


def stepwise_selection(X, y,
                       initial_list=[],
                       threshold_in=0.01,
                       threshold_out=0.4,
                       verbose=True):
    included = list(initial_list)
    comment = []
    while True:
        changed = False
        # forward step
        excluded = list(set(X.columns) - set(included))
        new_pval = pd.Series(index=excluded, dtype=float)
        for new_column in excluded:
            model = sm.OLS(y, sm.add_constant(pd.DataFrame(X[included + [new_column]]))).fit()
            new_pval[new_column] = model.pvalues[new_column]
        best_pval = new_pval.min()
        if best_pval < threshold_in:
            best_feature = new_pval.argmin()
            included.append(best_feature)
            changed = True
            comment.append('Add {:4} with p-value {:.3}'.format(best_feature, best_pval))
        # backward step
        model = sm.OLS(y, sm.add_constant(pd.DataFrame(X[included]))).fit()
        # use all coefs except intercept
        pvalues = model.pvalues.iloc[1:]
        worst_pval = pvalues.max()  # null if pvalues is empty
        if worst_pval > threshold_out:
            changed = True
            worst_feature = pvalues.idxmax()
            included.remove(worst_feature)
            comment.append('Drop {:4} with p-value {:.3}'.format(worst_feature, worst_pval))

        if not changed:
            break
    if len(included) == 0:
        included = list(initial_list)
    return included, comment


def season_average(dfm,year,season):
  nyear=year+1
  try:
    if season=='JFM':
      if ~np.isnan(np.ravel(dfm.loc[[year],'Jan':'Mar']).astype(float)).any(): return np.round(dfm.loc[[year],'Jan':'Mar'].mean(axis=1),1)
    if season=='FMA':
      if ~np.isnan(np.ravel(dfm.loc[[year],'Feb':'Apr']).astype(float)).any(): return np.round(dfm.loc[[year],'Feb':'Apr'].mean(axis=1),1)
    if season=='MAM':
      if ~np.isnan(np.ravel(dfm.loc[[year],'Mar':'May']).astype(float)).any(): return np.round(dfm.loc[[year],'Mar':'May'].mean(axis=1),1)
    if season=='AMJ':
      if ~np.isnan(np.ravel(dfm.loc[[year],'Apr':'Jun']).astype(float)).any(): return np.round(dfm.loc[[year],'Apr':'Jun'].mean(axis=1),1)
    if season=='MJJ':
      if ~np.isnan(np.ravel(dfm.loc[[year],'May':'Jul']).astype(float)).any(): return np.round(dfm.loc[[year],'May':'Jul'].mean(axis=1),1)
    if season=='JJA':
      if ~np.isnan(np.ravel(dfm.loc[[year],'Jun':'Aug']).astype(float)).any(): return np.round(dfm.loc[[year],'Jun':'Aug'].mean(axis=1),1)
    if season=='JAS':
      if ~np.isnan(np.ravel(dfm.loc[[year],'Jul':'Sep']).astype(float)).any(): return np.round(dfm.loc[[year],'Jul':'Sep'].mean(axis=1),1)
    if season=='ASO':
      if ~np.isnan(np.ravel(dfm.loc[[year],'Aug':'Oct']).astype(float)).any(): return np.round(dfm.loc[[year],'Aug':'Oct'].mean(axis=1),1)
    if season=='SON':
      if ~np.isnan(np.ravel(dfm.loc[[year],'Sep':'Nov']).astype(float)).any(): return np.round(dfm.loc[[year],'Sep':'Nov'].mean(axis=1),1)
    if season=='OND':
      if ~np.isnan(np.ravel(dfm.loc[[year],'Oct':'Dec']).astype(float)).any(): return np.round(dfm.loc[[year],'Oct':'Dec'].mean(axis=1),1)
    if season=='NDJ':
        p1=~np.isnan(np.ravel(dfm.loc[[year],'Nov':'Dec']).astype(float)).any()
        p2=~np.isnan(np.ravel(dfm.loc[[nyear],'Jan']).astype(float)).any()
        if p1 and p2: return np.round((dfm.loc[[year],'Nov':'Dec'].sum(axis=1).values+dfm.loc[[nyear],'Jan'].values)/3.,1)
    if season=='DJF':
        p1=~np.isnan(np.ravel(dfm.loc[[year],'Dec']).astype(float)).any()
        p2=~np.isnan(np.ravel(dfm.loc[[nyear],'Jan':'Feb']).astype(float)).any()
        if p1 and p2: return np.round((dfm.loc[[year],'Dec'].values+dfm.loc[[nyear],'Jan':'Feb'].sum(axis=1).values)/3.,1)
    return
  except:
    return


def dbcluster(coordinates, func, n_clusters, mindist, samples, njobs):
    if func == 'kmeans':
        db = cluster.KMeans(n_clusters=n_clusters).fit(coordinates)
    if func == 'dbscan':
        db = cluster.DBSCAN(eps=mindist * 1.0 / 6371.0088, min_samples=samples, n_jobs=1)
        db = db.fit(np.radians(coordinates))
    return db


def data2geojson(dfw, jsonout):
    dfw = dfw.fillna('')
    features = []
    insert_features = lambda X: features.append(
        geojson.Feature(geometry=geojson.Point((X["Lon"],
                                                X["Lat"])),
                        properties=dict(ID=X["ID"], class4=X["class4"], class3=X["class3"], class2=X["class2"],
                                        class1=X["class1"], wavg=X["wavg"], fcst_class=X["class"], avgHS=X["avgHS"])))
    dfw.apply(insert_features, axis=1)
    with open(jsonout, 'w') as fp:
        geojson.dump(geojson.FeatureCollection(features), fp, sort_keys=False, ensure_ascii=False)


def whichzone(zonejson, lat, lon, field):
    point = Point(lon, lat)
    for feature in zonejson['features']:
        polygon = shape(feature['geometry'])
        if polygon.contains(point):
            return feature['properties'][field]
    return None

def whichpolygons(zonejson, coords):
    polygons = []
    for f in range(len(zonejson['features'])):
        feature = zonejson['features'][f]
        polygon = shape(feature['geometry'])
        for pts in coords:
            point = Point(pts[0], pts[1])
            if polygon.contains(point):
                polygons.append(f)
    return np.unique(polygons)

def zonelist(zonejson, field):
    zarr = []
    for feature in zonejson['features']:
        zarr.append(feature['properties'][field])
    return zarr

def station_forecast_png(prefix, stationclass, base_map, colors, outdir, fcstName):
    DPI = 150
    W = 1000
    H = 1000
    stationclass = stationclass.reset_index()
    fig = plt.figure(figsize=(W / float(DPI), H / float(DPI)), frameon=True, dpi=DPI)
    ax = fig.gca()
    xs, _ = stationclass.shape
    if base_map is not None:
        coords = list(stationclass[['Lon', 'Lat']].to_records(index=False))
        polygons = whichpolygons(base_map, coords)
        for polygon in polygons:
            feature = base_map['features'][polygon]
            poly = feature['geometry']
            ax.add_patch(PolygonPatch(poly, fc='#ffffff', ec='#8f8f8f', alpha=1.0, zorder=2))
    for x in range(xs):
        fclass = stationclass.iloc[x]['class']
        name = str(stationclass.iloc[x]['ID']) + ' ' + str(int(float(stationclass.iloc[x]['avgHS'])+0.5)) + '%'
        color = colors.get('class'+str(fclass), 'class0')
        midx = stationclass.iloc[x]['Lon']
        midy = stationclass.iloc[x]['Lat']
        plt.plot(midx, midy, color=color, marker='o', markersize=8)
        plt.text(midx, midy, name, fontsize=4)

    plt.title(fcstName + ' Forecast', fontsize=12)
    plt.xlabel('Longitude', fontsize=10)
    plt.ylabel('Latitude', fontsize=10)
    ax.axis('scaled')
    lelem = [Patch(facecolor=colors.get('class0'), edgecolor='none', label='Forecast Class  (PA PN PB)'),
             Patch(facecolor=colors.get('class4'), edgecolor='none', label='Above to Normal (40 35 25)'),
             Patch(facecolor=colors.get('class3'), edgecolor='none', label='Normal to Above (35 40 25)'),
             Patch(facecolor=colors.get('class2'), edgecolor='none', label='Normal to Below (25 40 35)'),
             Patch(facecolor=colors.get('class1'), edgecolor='none', label='Below to Normal (25 35 40)')]
    ax.legend(handles=lelem, prop={'size': 5})
    plt.savefig(outdir + os.sep + prefix + '_station-forecast.png', bbox_inches = 'tight')
    plt.close(fig)

def write_zone_forecast(zonefcstprefix, fcstzone_df, forecastjson, ZoneID, colors, stationclass, zonepoints, fcstName):
    ids = list(fcstzone_df.reset_index()['Zone'])
    fcstjsonout = zonefcstprefix + '_zone-forecast.geojson'
    fcstcsvout = zonefcstprefix + '_zone-forecast.csv'
    for feature in forecastjson['features']:
        ID = feature['properties'][ZoneID]
        if ID in ids:
            feature['properties']['class4'] = list(fcstzone_df.loc[[ID],'class4'])[0]
            feature['properties']['class3'] = list(fcstzone_df.loc[[ID],'class3'])[0]
            feature['properties']['class2'] = list(fcstzone_df.loc[[ID],'class2'])[0]
            feature['properties']['class1'] = list(fcstzone_df.loc[[ID],'class1'])[0]
            feature['properties']['wavg'] = list(fcstzone_df.loc[[ID],'wavg'])[0]
            feature['properties']['fcst_class'] = list(fcstzone_df.loc[[ID],'class'])[0]
            feature['properties']['avgHS'] = list(fcstzone_df.loc[[ID],'avgHS'])[0]
    fcstzone_df.to_csv(fcstcsvout, header=True, index=True)
    with open(fcstjsonout, 'w') as fp:
        geojson.dump(forecastjson, fp)
    DPI = 150
    W = 1000
    H = 1000
    fig = plt.figure(figsize=(W / float(DPI), H / float(DPI)), frameon=True, dpi=DPI)
    ax = fig.gca()
    features = forecastjson['features']
    for feature in features:
        fclass = 'class'+str(feature['properties'].get('fcst_class', 0))
        poly = feature['geometry']
        avgHS = feature['properties'].get('avgHS', None)
        color = colors[fclass]
        minx, miny, maxx, maxy = shape(feature["geometry"]).bounds
        midx = minx + 0.25 * (maxx - minx)
        midy = maxy - 0.25 * (maxy - miny)
        ax.add_patch(PolygonPatch(poly, fc=color, ec='#6699cc', alpha=0.5, zorder=2))
        if avgHS is not None:
            name = str(feature['properties'][ZoneID]) + ' ' + str(int(float(avgHS)+0.5)) + '%'
            plt.text(midx, midy, name, fontsize=6)
    if str(zonepoints) == '1':
        stationclass = stationclass.reset_index()
        xs, _ = stationclass.shape
        for x in range(xs):
            fclass = stationclass.iloc[x]['class']
            color = colors.get('class' + str(fclass), 'class0')
            lon = stationclass.iloc[x]['Lon']
            lat = stationclass.iloc[x]['Lat']
            plt.plot(lon, lat, color='#bebebe', marker='o', markersize=5, markerfacecolor=color)
    ax.axis('scaled')
    plt.title(fcstName + ' Forecast', fontsize=12)
    plt.xlabel('Longitude', fontsize=10)
    plt.ylabel('Latitude', fontsize=10)
    lelem = [Patch(facecolor=colors.get('class0'), edgecolor='none', label='Forecast Class  (PA PN PB)'),
             Patch(facecolor=colors.get('class4'), edgecolor='none', label='Above to Normal (40 35 25)'),
             Patch(facecolor=colors.get('class3'), edgecolor='none', label='Normal to Above (35 40 25)'),
             Patch(facecolor=colors.get('class2'), edgecolor='none', label='Normal to Below (25 40 35)'),
             Patch(facecolor=colors.get('class1'), edgecolor='none', label='Below to Normal (25 35 40)')]
    ax.legend(handles=lelem, prop={'size': 5})
    plt.savefig(zonefcstprefix + '_zone-forecast.png', bbox_inches = 'tight')
    plt.close(fig)	

def weighted_average(group):
   HS = group['HS']
   fclass = group['class']
   n4 = list(fclass).count(4)
   n3 = list(fclass).count(3)
   n2 = list(fclass).count(2)
   n1 = list(fclass).count(1)
   try:
      wavg = np.average(fclass,weights=HS)
   except:
      wavg = 0
   return wavg, n4, n3, n2, n1

def weighted_average_fcst(group):
   HS = group['HS']
   fclass = group['class']
   fcst = group['fcst']
   t3 = int(np.ravel(group['t3'])[0]+0.5)
   t2 = int(np.ravel(group['t2'])[0]+0.5)
   t1 = int(np.ravel(group['t1'])[0]+0.5)
   try:
      wavgclass = int(np.average(fclass, weights=HS)+0.5)
   except:
      wavgclass = 0
   avgfcst = int(np.mean(fcst)+0.5)
   avgHS = int(np.mean(HS)+0.5)
   return t1, t2, t3, avgfcst, avgHS, wavgclass

def convert(seconds):
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    return "%d hour(s) %d minute(s) %d second(s)" % (hour, minutes, seconds)

def get_mean_HS(df, ID, attr):
    return np.mean(df[df[attr] == ID]['HS'])

def model_skill(fcst_df, lim1, lim2):
    HS = 0
    HSS = 0
    POD_below = 0
    POD_normal = 0
    POD_above = 0
    FA_below = 0
    FA_normal = 0
    FA_above = 0
    cgtable_df = pd.DataFrame(columns=['-','FCST BELOW','FCST NORMAL','FCST ABOVE','Total'])
    cgtable_df['-'] = ['OBS BELOW','OBS_NORMAL','OBS_ABOVE','Total']
    df = fcst_df.dropna()
    obs = np.array(df.sort_values(by=['obs'])['obs'])
    fcst = np.array(df.sort_values(by=['obs'])['fcst'])
    below = obs <= lim1
    normal = (obs > lim1) & (obs <= lim2)
    above = obs > lim2
    A11 = sum(fcst[below] <= lim1)
    A12 = sum((fcst[below] > lim1) & (fcst[below] <= lim2))
    A13 = sum(fcst[below] > lim2)
    A21 = sum(fcst[normal] <= lim1)
    A22 = sum((fcst[normal] > lim1) & (fcst[normal] <= lim2))
    A23 = sum(fcst[normal] > lim2)
    A31 = sum(fcst[above] <= lim1)
    A32 = sum((fcst[above] > lim1) & (fcst[above] <= lim2))
    A33 = sum(fcst[above] > lim2)
    M = A11 + A21 + A31
    N = A12 + A22 + A32
    O = A13 + A23 + A33
    J = A11 + A12 + A13
    K = A21 + A22 + A23
    L = A31 + A32 + A33
    T = M + N + O
    cgtable_df['FCST BELOW'] = [A11, A21, A31, M]
    cgtable_df['FCST NORMAL'] = [A12, A22, A32, N]
    cgtable_df['FCST ABOVE'] = [A13, A23, A33, O]
    cgtable_df['Total'] = [J, K, L, T]
    if T != 0:
        try:
            HS = integer(100 * (A11 + A22 + A33) / T)
        except:
            HS = np.nan
        try:
            Factor = (J*M + K*N + L*O) / T
            HSS = (A11 + A22 + A33 - Factor) / (T - Factor)
        except:
            HSS = np.nan
    if A11 != 0: POD_below = integer(100 * A11 / M)
    if A22 != 0: POD_normal = integer(100 * A22 / N)
    if A33 != 0: POD_above = integer(100 * A33 / O)
    if M != 0: FA_below = integer(100 * A31 / M)
    if N != 0: FA_normal = integer(100 * (A12 + A32) / N)
    if O != 0: FA_above = integer(100 * A13 / O)
    warnings.filterwarnings('error')
    try:
        PB = [POD_below, integer(100 * A21 / M), integer(100 * A31 / M)]
    except:
        PB = np.nan
    try:
        PN = [integer(100 * A12 / N), POD_normal, integer(100 * A32 / N)]
    except:
        PN = np.nan
    try:
        PA = [FA_above, integer(100 * A23 / O), POD_above]
    except:
        PA = np.nan
    return HS, HSS, POD_below, POD_normal, POD_above, FA_below, FA_normal, FA_above, cgtable_df, PB, PN, PA


def hit_score(fcst, obs, lim1, lim2):
    if len(fcst) != len(obs):
        print('fcst and obs length not equal')
        return 0
    obs = np.sort(np.array(obs))
    fcst = np.sort(np.array(fcst))
    below = obs <= lim1
    normal = (obs > lim1) & (obs <= lim2)
    above = obs > lim2
    A11 = sum(fcst[below] <= lim1)
    A12 = sum((fcst[below] > lim1) & (fcst[below] <= lim2))
    A13 = sum(fcst[below] > lim2)
    A21 = sum(fcst[normal] <= lim1)
    A22 = sum((fcst[normal] > lim1) & (fcst[normal] <= lim2))
    A23 = sum(fcst[normal] > lim2)
    A31 = sum(fcst[above] <= lim1)
    A32 = sum((fcst[above] > lim1) & (fcst[above] <= lim2))
    A33 = sum(fcst[above] > lim2)
    M = A11 + A21 + A31
    N = A12 + A22 + A32
    O = A13 + A23 + A33
    T = M + N + O
    if T != 0:
        try:
            HS = 100 * (A11 + A22 + A33) / T
        except:
            return 0
        if np.isfinite(HS):
            return int(HS+0.5)
        else:
            return 0
    return 0



def good_POD(string, fclass):
    if str(string).count(':') != 2:
        return False
    try:
        probs = re.sub("[][]+", "", str(string)).split(':')
        pB = int(probs[0])
        pN = int(probs[1])
        pA = int(probs[2])
    except:
        return False
    if int(fclass) == 1:
        return (pB >= pN) and (pB >= pA)
    if (int(fclass) == 2) or (int(fclass) == 3):
        return (pN >= pB) and (pN >= pA)
    if int(fclass) == 4:
        return (pA >= pB) and (pA >= pN)
    return False


def plot_Station_forecast(forecast_df, fcstPeriod, graphpng, station, q1, q2, q3):
    DPI = 100
    W = 1000
    H = 600
    colors = ['#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4', '#46f0f0', '#f032e6', '#bcf60c', '#fabebe',
              '#008080', '#e6beff', '#9a6324', '#fffac8', '#800000', '#aaffc3', '#808000', '#ffd8b1', '#000075',
              '#808080', '#dcbeff']
    graphs = list(forecast_df.columns)
    indx = graphs.index('Year')
    graphs.pop(indx)
    maxval = np.nanmax(np.ravel(forecast_df[graphs]))
    minval = np.nanmin(np.ravel(forecast_df[graphs]))
    indx = graphs.index(fcstPeriod)
    graphs.pop(indx)
    q1s = [q1] * len(forecast_df['Year'])
    q2s = [q2] * len(forecast_df['Year'])
    q3s = [q3] * len(forecast_df['Year'])
    maxvals = [maxval + (0.05 * maxval)] * len(forecast_df['Year'])
    minvals = [minval - abs(0.05 * minval)] * len(forecast_df['Year'])
    fig = plt.figure(figsize=(W/float(DPI), H/float(DPI)), frameon=True, dpi=DPI)
    plt.fill_between(forecast_df['Year'], minvals, q1s, color='#ffe7d1')
    plt.fill_between(forecast_df['Year'], q1s, q3s, color='#e8f9e9')
    plt.fill_between(forecast_df['Year'], q3s, maxvals, color='#f4f6ff')
    plt.plot(np.array(forecast_df['Year']), [q1] * len(list(forecast_df['Year'])), color='#e5e5e5', linestyle='dashed')
    plt.plot(np.array(forecast_df['Year']), [q2] * len(list(forecast_df['Year'])), color='#e5e5e5', linestyle='dashed')
    plt.plot(np.array(forecast_df['Year']), [q3] * len(list(forecast_df['Year'])), color='#e5e5e5', linestyle='dashed')
    plt.plot(np.array(forecast_df['Year']), np.array(forecast_df[fcstPeriod]), color='red', marker='o', label='Actual')
    for n in range(len(graphs)):
        graph = graphs[n]
        plt.plot(np.array(forecast_df['Year']), np.array(forecast_df[graph]), color=colors[n], marker='+', label=graph, linewidth=0.7)
    plt.title('Actual ('+fcstPeriod+') vs Forecasts for '+station, fontsize=12)
    plt.legend(prop={'size': 6})
    plt.xticks(list(forecast_df['Year']), [str(x) for x in list(forecast_df['Year'])], fontsize=8, rotation=90)
    plt.xlabel('Year', fontsize=12)
    plt.ylabel('Forecast', fontsize=12)
    plt.savefig(graphpng, bbox_inches = 'tight')
    plt.close(fig)

def plot_correlation_graph(corr_df, act, pred, fcst, graphpng):
    DPI = 100
    W = 800
    H = 800
    fig = plt.figure(figsize=(W/float(DPI), H/float(DPI)), frameon=True, dpi=DPI)
    plt.scatter(np.array(corr_df[pred]), np.array(corr_df[act]), s=5, marker='o', c='blue', label=act)
    plt.plot(np.array(corr_df[pred]), np.array(corr_df[fcst]), color='red', marker='+', label=fcst, linewidth=0.7)
    plt.title('Predictand vs Predictor values', fontsize=12)
    plt.legend(prop={'size': 6})
    #plt.xticks(list(forecast_df['Year']), [str(x) for x in list(forecast_df['Year'])], fontsize=8, rotation=90)
    plt.xlabel('Predictor', fontsize=12)
    plt.ylabel('Predictand', fontsize=12)
    plt.savefig(graphpng, bbox_inches = 'tight')
    plt.close(fig)


def writeout(prefix, p_matrix, corgrp_matrix, corr_df, lats, lons, outdir, config):
    outfile = outdir + os.sep + prefix + '_correlation-maps.nc'
    if os.path.exists(outfile): return 0
    os.makedirs(outdir, exist_ok=True)
    if int(config.get('plots', {}).get('corrmaps', 1)) == 1:
        corgrp_matrix[corgrp_matrix == -1] = 255
        corgrp_matrix[np.isnan(corgrp_matrix)] = 255
        # generate NETCDF
        output = Dataset(outfile, 'w', format='NETCDF4')
        output.description = 'P-Values and High-Correlation Basins [' + prefix + ']'
        output.comments = 'Created ' + datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")
        output.source = 'CFTv' + config.get('Version', '1.4.2')
        lat = output.createDimension('lat', len(lats))
        lon = output.createDimension('lon', len(lons))
        T = output.createDimension('T', 1)
        initial_date = output.createVariable('target', np.float64, ('T',))
        latitudes = output.createVariable('lat', np.float32, ('lat',))
        longitudes = output.createVariable('lon', np.float32, ('lon',))
        basins = output.createVariable('basins', np.uint8, ('T', 'lat', 'lon'))
        pvalues = output.createVariable('pvalues', np.float32, ('T', 'lat', 'lon'))
        latitudes.units = 'degree_north'
        latitudes.axis = 'Y'
        latitudes.long_name = 'Latitude'
        latitudes.standard_name = 'Latitude'
        longitudes.units = 'degree_east'
        longitudes.axis = 'X'
        longitudes.long_name = 'Longitude'
        longitudes.standard_name = 'Longitude'
        initial_date.units = 'days since ' + str(config.get('trainStartYear')) + '-' + \
                             str('{:02d}-'.format(months.index(config.get('predictorMonth')) + 1)) + '01 00:00:00'
        initial_date.axis = 'T'
        initial_date.calendar = 'standard'
        initial_date.standard_name = 'time'
        initial_date.long_name = 'training start date'
        latitudes[:] = lats
        longitudes[:] = lons
        basins[:] = corgrp_matrix
        pvalues[:] = p_matrix
        output.close()
    # print correlation csv
    if int(config.get('plots', {}).get('corrcsvs', 1)) == 1:
        csv = outdir + os.sep + prefix + '_correlation-basin-avgs.csv'
        corr_df.reset_index()
        corr_df.to_csv(csv)


def run_model_skill(fcst_df, fcstPeriod, fcstcol, r2score, training_actual):
    # generate model skill statistics and write to file
    limits = [0.3333, 0.6667]
    fcst_precip = round(list(fcst_df.tail(1)[fcstcol])[0], 1)
    observed = np.array(training_actual)
    observed_clean = observed[np.isfinite(observed)]
    t1, t2 = list(pd.DataFrame(training_actual)[0].quantile(limits))
    nfcst_df = fcst_df.rename(columns={fcstPeriod: "obs", fcstcol: "fcst"})
    HS, HSS, POD_below, POD_normal, POD_above, FA_below, FA_normal, FA_above, cgtable_df, PB, PN, PA = \
        model_skill(nfcst_df, t1, t2)
    skillColumns = ['Statistic', 'Value']
    skill_df = pd.DataFrame(columns=skillColumns)
    skill_df['Statistic'] = ['R-Squared Score', 'Hit Score (HS)', 'Hit Skill Score (HSS)',
                             'Probability of Detecting Below', 'Probability of Detecting Normal',
                             'Probability of Detecting Above', 'False Alarm 1st Order (Below)',
                             'False Alarm 1st Order (Normal)', 'False Alarm 1st Order (Above)',
                             'Probability Forecast For Below-Normal', 'Probability Forecast For Near-Normal',
                             'Probability Forecast For Above-Normal']
    skill_df['Value'] = [r2score, HS, HSS, POD_below, POD_normal, POD_above, FA_below, FA_normal, FA_above, PB,
                         PN, PA]
    if fcst_precip < 0:  fcst_precip = 0.0
    qlimits = [0.3333, 0.5, 0.6667]
    dfp = pd.DataFrame(observed_clean)[0].quantile(qlimits)
    q1 = float(round(dfp.loc[qlimits[0]], 1))
    q2 = float(round(dfp.loc[qlimits[1]], 1))
    q3 = float(round(dfp.loc[qlimits[2]], 1))
    forecast_class = np.nan
    Prob = np.nan
    if fcst_precip <= q1:
        forecast_class = 1
        Prob = PB
    if fcst_precip >= q1:
        forecast_class = 2
        Prob = PN
    if fcst_precip >= q2:
        forecast_class = 3
        Prob = PN
    if fcst_precip >= q3:
        forecast_class = 4
        Prob = PA
    pmedian = round(np.median(observed_clean), 1)
    return q1, q2, q3, pmedian, fcst_precip, forecast_class, HS, str(Prob).replace(',', ':'), cgtable_df, skill_df

def nc_unit_split(config, predictordict, fcstPeriod, comb):
    point, pr, al = comb
    algorithm = config.get('algorithms')[al]
    try:
        predictor = predictordict[list(predictordict.keys())[pr]]
    except:
        return None
    predictor['Name'] = list(predictordict.keys())[pr]
    predictand_data = netcdf_data(config.get('predictandList')[0], param=config.get('predictandattr'))
    return forecast_pixel_unit(config, predictor, predictand_data, fcstPeriod, algorithm, point)

def forecast_pixel_unit(config, predictordict, predictand_data, fcstPeriod, algorithm, point):
    x, y = point
    predictorName = predictordict.get('Name')
    input_data = predictand_data.tslice(x=x, y=y)
    times = predictand_data.times()
    trainStartYear = int(config['trainStartYear'])
    trainEndYear = int(config['trainEndYear'])
    fcstYear = int(config['fcstyear'])
    years = list(range(trainStartYear, fcstYear + 1))
    trainingYears = [yr for yr in range(trainStartYear, trainEndYear + 1)]
    nyears = len(trainingYears)
    point_season = pd.DataFrame(columns=['Year', fcstPeriod])
    point_season['Year'] = years
    point_season.set_index('Year', inplace=True)
    if config.get('fcstPeriodLength', '3month') != '3month':
        for x in range(len(times)):
            year = int(times[x][:4])
            mon = times[x][4:6]
            month = datetime.strptime(mon, '%m').strftime('%b')
            if (year in years) and (month == fcstPeriod):
                point_season.loc[[year], fcstPeriod] = input_data[x]
    elif config.get('fcstPeriodLength', '3month') == '3month':
        columns = season_months[fcstPeriod][:]
        columns.insert(0, 'Year')
        point_data = pd.DataFrame(columns=columns)
        point_data['Year'] = years
        point_data.set_index('Year', inplace=True)
        for x in range(len(times)):
            year = int(times[x][:4])
            mon = times[x][4:6]
            month = datetime.strptime(mon, '%m').strftime('%b')
            if (year in years) and (month in season_months[fcstPeriod]):
                point_data.loc[[year], month] = input_data[x]
        for year in years:
            if config['composition'] == "Sum":
                point_season.loc[[year], fcstPeriod] = season_cumulation(point_data, year, fcstPeriod)
            else:
                point_season.loc[[year], fcstPeriod] = season_average(point_data, year, fcstPeriod)
    #forecastdf = pd.DataFrame(columns=['Predictor', 'Algorithm', 'Point', 't1', 't2', 't3',
    #                                   'median', 'fcst', 'class', 'r2score', 'HS', 'Prob'])

    sst_arr = predictordict['data']

    predictand = np.asarray(point_season, dtype=float).reshape(-1, )
    training_actual = predictand[:len(trainingYears)]
    test_actual = predictand[len(trainingYears):]
    test_notnull = np.isfinite(test_actual)
    if (len(training_actual[np.isfinite(training_actual)]) < 6) or (len(test_actual[np.isfinite(test_actual)]) < 2):
        return None

    # compute basins
    trainPredictand = predictand[:nyears]
    trainSST = sst_arr[:nyears]
    pnotnull = np.isfinite(trainPredictand)
    try:
        nyearssst, nrowssst, ncolssst = sst_arr.shape
    except ValueError:
        nyearssst, nrowssst, ncolssst = len(sst_arr), 0, 0
    yearssst = [yr for yr in range(trainStartYear, (trainStartYear + nyearssst))]
    if (nrowssst, ncolssst) != (0, 0):
        SSTclusterSize = 1000.
        lons2d, lats2d = np.meshgrid(predictordict['lons'], predictordict['lats'])
        # calculate correlation
        r_matrix = np.zeros((nrowssst, ncolssst))
        p_matrix = np.zeros((nrowssst, ncolssst))
        # calculate correlation
        for row in range(nrowssst):
            for col in range(ncolssst):
                sstvals = np.array(trainSST[:, row][:, col], dtype=float)
                warnings.filterwarnings('error')
                try:
                    notnull = pnotnull & np.isfinite(sstvals)
                    r_matrix[row][col], p_matrix[row][col] = pearsonr(trainPredictand[notnull], sstvals[notnull])
                except:
                    pass
        # corr = (p_matrix <= config['PValue']) & (abs(r_matrix) >= 0.5)
        # corr = (p_matrix <= config['PValue'])
        corr = (p_matrix <= config['PValue']) & (p_matrix != 0)
        if not corr.any():
            return 0
        corr_coords = list(zip(lons2d[corr], lats2d[corr]))
        # create correlation basins
        corgrp_matrix = np.zeros((nrowssst, ncolssst)) * np.nan
    
        minx = float(config.get('basinbounds', {}).get('minlon', -180))
        maxx = float(config.get('basinbounds', {}).get('maxlon', 366))
        miny = float(config.get('basinbounds', {}).get('minlat', -90))
        maxy = float(config.get('basinbounds', {}).get('maxlat', 90))
        roi = [False] * len(corr_coords)
        for i in range(len(corr_coords)):
            if corr_coords[i][0] < minx or corr_coords[i][0] > maxx or corr_coords[i][1] < miny or \
                    corr_coords[i][1] > maxy:
                roi[i] = True
    
        db = dbcluster(corr_coords, 'dbscan', 5, SSTclusterSize, 3, 2)
        coords_clustered = np.array(db.labels_)
        coords_clustered[roi] = -1
        uniq = list(set(coords_clustered))
        minpixelperbasin = 6
        for zone in uniq:
            count = len(coords_clustered[coords_clustered == zone])
            if count < minpixelperbasin: coords_clustered[coords_clustered == zone] = -1
    
        basins = list(set(coords_clustered[coords_clustered != -1]))
        SSTzones = len(basins)
        if corr[corr == True].shape == coords_clustered.shape:
            index = 0
            for row in range(nrowssst):
                for col in range(ncolssst):
                    if corr[row][col]:
                        corgrp_matrix[row][col] = coords_clustered[index]
                        index = index + 1
        # generate correlation group matrices
        basin_arr = ['Basin' + str(x) for x in basins]
        basin_arr.insert(0, fcstPeriod)
        basin_arr.insert(0, 'year')
        corr_df = pd.DataFrame(columns=basin_arr)
        corr_df['year'] = trainingYears
        corr_df[fcstPeriod] = trainPredictand
        corr_df.set_index('year', inplace=True)
        for yr in range(nyearssst):
            year = yearssst[yr]
            sstavg = np.zeros(SSTzones)
            corr_df.loc[year, fcstPeriod] = list(point_season.loc[[year], fcstPeriod])[0]
            for group in range(SSTzones):
                sstavg[group] = "{0:.3f}".format(np.mean(sst_arr[yr][corgrp_matrix == basins[group]]))
                corr_df.loc[year, 'Basin' + str(basins[group])] = sstavg[group]
        corr_df = corr_df.dropna(how='all', axis=1)
        basin_arr = list(corr_df.columns)
        indx = basin_arr.index(fcstPeriod)
        basin_arr.pop(indx)
        if len(basin_arr) == 0:
            return None
        basin_matrix = np.array(corr_df[basin_arr])
    
        # get basin combination with highest r-square: returns bestr2score, final_basins, final_basin_matrix
        basin_matrix_df = pd.DataFrame(basin_matrix[:len(trainingYears)], columns=basin_arr)
        notnull = np.isfinite(np.array(predictand[:len(trainingYears)]))
        try:
            final_basins, comments = stepwise_selection(basin_matrix_df[notnull].astype(float),
                                                    list(predictand[:len(trainingYears)][notnull]),
                                                    initial_list=basin_arr, threshold_out=config.get('stepwisePvalue'))
        except:
            final_basins = basin_arr[:]
        if len(final_basins) == 0:
            final_basins = basin_arr[:]
                
        combo_basin_matrix = np.zeros((len(yearssst), len(final_basins))) * np.nan
        # loop for all years where SST is available
        for yr in range(len(yearssst)):
            for group in range(len(final_basins)):
                # get corresponding sst average for the group from main basin_matrix
                combo_basin_matrix[yr][group] = basin_matrix[yr][basin_arr.index(final_basins[group])]
                
        nbasins = len(final_basins)
    else:            
        nbasins = 1
        combo_basin_matrix = np.zeros((len(yearssst), nbasins)) * np.nan
        # loop for all years where SST is available
        for yr in range(len(yearssst)):
            # get corresponding sst average for the group from main basin_matrix
            combo_basin_matrix[yr][0] = sst_arr[yr]

    training_Xmatrix = combo_basin_matrix[:len(trainingYears)]
    testing_Xmatrix = combo_basin_matrix[len(trainingYears):]
    testing_years = yearssst[len(trainingYears):]
    notnull = np.isfinite(training_actual)
    t1, t2 = np.quantile(training_actual, [0.333, 0.666])
    # scale the predictor
    scaler = StandardScaler()
    scaler.fit(training_Xmatrix)
    StandardScaler(copy=True, with_mean=True, with_std=True)
    X_train = scaler.transform(training_Xmatrix)
    X_test = scaler.transform(testing_Xmatrix)

    if algorithm == 'MLP':
        # start_time = time.time()
        activation_fn = 'tanh'
        solver_fn = 'lbfgs'
        ratings = {}
        for x in range(2, 21):
            for y in range(0, 21):
                if y > x: continue
                hiddenlayerSize = (x + 1, y + 1)
                regm = MLPRegressor(hidden_layer_sizes=hiddenlayerSize,
                                    activation=activation_fn, solver=solver_fn, random_state=42, max_iter=700)
                try:
                    regm.fit(X_train[notnull], np.asarray(training_actual)[notnull])
                except:
                    continue
                forecasts = np.array(regm.predict(X_test))
                warnings.filterwarnings('error')
                try:
                    m, n = pearsonr(np.array(forecasts)[test_notnull], list(np.ravel(test_actual)[test_notnull]))
                except:
                    continue
                v = np.std(forecasts)
                ratings[str(x + 1) + '_' + str(y + 1)] = ((hit_score(forecasts, test_actual, t1, t2)+1) * (m**2), v)

        combs = sorted(ratings.items(), key=lambda xx: xx[1][0], reverse=True)
        v = np.std(np.ravel(test_actual[test_notnull]))
        r, s = None, None
        for x in range(len(combs)):
            if combs[x][1][0] >= 0.1 and combs[x][1][1] >= v / 2:
                r, s = combs[x][0].split('_')
                break
        if (r is not None) and (s is not None):
            if int(s) == 0:
                hiddenlayerSize = (int(r),)
            else:
                hiddenlayerSize = (int(r), int(s),)
            regm = MLPRegressor(hidden_layer_sizes=hiddenlayerSize,
                                activation=activation_fn, solver=solver_fn, random_state=42, max_iter=700)
            regm.fit(X_train[notnull], np.asarray(training_actual)[notnull])
            mlp_fcstdf = pd.DataFrame(columns=['Year', fcstPeriod, 'MLPfcst'])
            mlp_fcstdf['Year'] = testing_years
            mlp_fcstdf[fcstPeriod] = test_actual
            mlp_fcstdf['MLPfcst'] = np.array(regm.predict(X_test))
            mlp_fcstdf.set_index('Year', inplace=True)
            warnings.filterwarnings('error')
            m, n = pearsonr(np.array(mlp_fcstdf['MLPfcst'])[test_notnull], list(np.ravel(test_actual[test_notnull])))
            r2score = m ** 2
            q1, q2, q3, pmedian, famnt, fclass, HS, Prob, cgtable_df, skill_df = \
                run_model_skill(mlp_fcstdf, fcstPeriod, 'MLPfcst', r2score, training_actual)
            a_series = pd.DataFrame.from_dict({'Predictor': predictorName, 'Algorithm': algorithm, 'Point': [point], 
                                      't1': q1, 't2': q2, 't3': q3, 'median': pmedian, 'fcst': famnt, 'class': fclass,
                                      'r2score': r2score, 'HS': HS, 'Prob': Prob})
            try:
                forecastdf = pd.concat([forecastdf, a_series], axis=0, ignore_index=True)
            except:
                forecastdf=a_series.copy()

            mlp_fcstdf.rename(columns={'MLPfcst': predictorName +'_MLP'}, inplace=True)

    if algorithm == 'LR':
        regr = linear_model.LinearRegression()
        regr.fit(X_train[notnull], np.asarray(training_actual)[notnull])
        intercept = regr.intercept_
        coefficients = regr.coef_
        lr_fcstdf = pd.DataFrame(columns=['Year', fcstPeriod, 'LRfcst'])
        lr_fcstdf['Year'] = testing_years
        lr_fcstdf[fcstPeriod] = test_actual
        lr_fcstdf['LRfcst'] = np.array(regr.predict(X_test))
        lr_fcstdf.set_index('Year', inplace=True)
        warnings.filterwarnings('error')
        try:
            m, n = pearsonr(np.array(lr_fcstdf['LRfcst'])[test_notnull], list(np.ravel(test_actual)[test_notnull]))
        except:
            return None
        r2score = m ** 2
        regrFormula = {"intercept": intercept, "coefficients": coefficients}
        coeff_arr = list(regrFormula["coefficients"])
        coeff_arr.insert(0, regrFormula["intercept"])
        q1, q2, q3, pmedian, famnt, fclass, HS, Prob, cgtable_df, skill_df = \
            run_model_skill(lr_fcstdf, fcstPeriod, 'LRfcst', r2score, training_actual)
        a_series = pd.DataFrame.from_dict({'Predictor': predictorName, 'Algorithm': algorithm, 'Point': [point], 
                                  't1': q1, 't2': q2, 't3': q3, 'median': pmedian, 'fcst': famnt, 'class': fclass,
                                  'r2score': r2score, 'HS': HS, 'Prob': Prob})
        try:
            forecastdf = pd.concat([forecastdf, a_series], axis=0, ignore_index=True)
        except:
            forecastdf=a_series.copy()

        lr_fcstdf.rename(columns={'LRfcst': predictorName + '_LR'}, inplace=True)

    # return station forecast
    if isinstance(forecastdf, pd.DataFrame):
        return forecastdf
    else:
        return None


def forecast_unit(config, predictordict, predictanddict, fcstPeriod, algorithm, station, outdir):
    predictorName = predictordict.get('Name')
    output = {}
    stationYF_dfs = []
    output[station] = {}
    input_data = predictanddict['data']
    indx = predictanddict['stations'].index(station)
    lat = predictanddict['lats'][indx]
    lon = predictanddict['lons'][indx]
    station_data_all =  input_data.loc[input_data['ID'] == station]
    trainStartYear = int(config['trainStartYear'])
    trainEndYear = int(config['trainEndYear'])
    trainingYears = [yr for yr in range(trainStartYear, trainEndYear + 1)]
    nyears = len(trainingYears)
    #forecastdf = pd.DataFrame(columns=['Predictor', 'Algorithm', 'ID', 'Lat', 'Lon', 't1', 't2', 't3',
    #                                   'median', 'fcst', 'class', 'r2score', 'HS', 'Prob'])

    output[station][predictorName] = {}
    sst_arr = predictordict.get('data')
    prefixParam = {"Predictor": predictorName, "Param": predictordict['param'],
                   "PredictorMonth": config.get('predictorMonth'),
                   "startyr": trainStartYear, "endyr": config['trainEndYear'],
                   "fcstYear": config['fcstyear'], "fcstPeriod": fcstPeriod, "station": str(station)}
    try:
        nyearssst, nrowssst, ncolssst = sst_arr.shape
    except ValueError:
        nyearssst, nrowssst, ncolssst = len(sst_arr), 0, 0
    yearspredictand = [yr for yr in range(trainStartYear, (trainStartYear + nyearssst))]
    station_data = station_data_all.loc[:,
                   ('Year', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')]
    station_data.drop_duplicates('Year', inplace=True)
    station_data = station_data.apply(pd.to_numeric, errors='coerce')
    seasonal_precip = pd.DataFrame(columns=['Year',fcstPeriod])
    seasonal_precip['Year'] = yearspredictand
    seasonal_precip.set_index('Year', inplace=True)
    station_data.set_index('Year', inplace=True)
    for year in yearspredictand:
        if config.get('fcstPeriodLength', '3month') == '3month':
            if config['composition'] == "Sum":
                seasonal_precip.loc[[year], fcstPeriod] = season_cumulation(station_data, year, fcstPeriod)
            else:
                seasonal_precip.loc[[year], fcstPeriod] = season_average(station_data, year, fcstPeriod)
        else:
            try:
                seasonal_precip.loc[[year], fcstPeriod] = round(float(station_data.loc[[year], fcstPeriod]), 1)
            except KeyError:
                seasonal_precip.loc[[year], fcstPeriod] = np.nan

    predictand = np.asarray(seasonal_precip, dtype=float).reshape(-1, )
    training_actual = predictand[:len(trainingYears)]
    test_actual = predictand[len(trainingYears):]
    test_notnull = np.isfinite(test_actual)
    name = re.sub('[^a-zA-Z0-9]', '', prefixParam["station"])
    prefix = prefixParam["Predictor"] + '_' + prefixParam["Param"] + '_' + config.get('predictorMonth') + '_' + \
             str(prefixParam["startyr"]) + '-' + str(prefixParam["endyr"]) + '_' + name
    if (len(training_actual[np.isfinite(training_actual)]) < 6) or (len(test_actual[np.isfinite(test_actual)]) < 2):
        return None

    # compute basins
    trainPredictand = predictand[:nyears]
    trainSST = sst_arr[:nyears]
    pnotnull = np.isfinite(trainPredictand)
    yearssst = [yr for yr in range(trainStartYear, (trainStartYear + nyearssst))]
    if (nrowssst, ncolssst) != (0, 0):
        SSTclusterSize = 1000.
        # nsst = sst_arr[yearssst.index(fcstYear)]
        lons2d, lats2d = np.meshgrid(predictordict['lons'], predictordict['lats'])
        # calculate correlation
        r_matrix = np.zeros((nrowssst, ncolssst))
        p_matrix = np.zeros((nrowssst, ncolssst))
        # calculate correlation
        for row in range(nrowssst):
            for col in range(ncolssst):
                sstvals = np.array(trainSST[:, row][:, col], dtype=float)
                warnings.filterwarnings('error')
                try:
                    notnull = pnotnull & np.isfinite(sstvals)
                    r_matrix[row][col], p_matrix[row][col] = pearsonr(trainPredictand[notnull], sstvals[notnull])
                except:
                    pass
        # corr = (p_matrix <= config['PValue']) & (abs(r_matrix) >= 0.5)
        corr = (p_matrix <= config['PValue']) & (p_matrix != 0)
        if not corr.any():
            return 0
        corr_coords = list(zip(lons2d[corr], lats2d[corr]))
        # create correlation basins
        corgrp_matrix = np.zeros((nrowssst, ncolssst)) * np.nan
    
        minx = float(config.get('basinbounds',{}).get('minlon', -180))
        maxx = float(config.get('basinbounds',{}).get('maxlon', 366))
        miny = float(config.get('basinbounds',{}).get('minlat', -90))
        maxy = float(config.get('basinbounds',{}).get('maxlat', 90))
        roi = [False] * len(corr_coords)
        for i in range(len(corr_coords)):
            if corr_coords[i][0] < minx or corr_coords[i][0] > maxx or corr_coords[i][1] < miny or \
                    corr_coords[i][1] > maxy:
                roi[i] = True
    
        db = dbcluster(corr_coords, 'dbscan', 5, SSTclusterSize, 3, 2)
        coords_clustered = np.array(db.labels_)
        coords_clustered[roi] = -1
        uniq = list(set(coords_clustered))
        minpixelperbasin = 6
        for zone in uniq:
            count = len(coords_clustered[coords_clustered == zone])
            if count < minpixelperbasin: coords_clustered[coords_clustered == zone] = -1
    
        basins = list(set(coords_clustered[coords_clustered != -1]))
        SSTzones = len(basins)
        if corr[corr == True].shape == coords_clustered.shape:
            index = 0
            for row in range(nrowssst):
                for col in range(ncolssst):
                    if corr[row][col]:
                        corgrp_matrix[row][col] = coords_clustered[index]
                        index = index + 1
        # generate correlation group matrices
        basin_arr = ['Basin' + str(x) for x in basins]
        basin_arr.insert(0, fcstPeriod)
        basin_arr.insert(0, 'year')
        corr_df = pd.DataFrame(columns=basin_arr)
        corr_df['year'] = trainingYears
        corr_df[fcstPeriod] = trainPredictand
        corr_df.set_index('year', inplace=True)
        for yr in range(nyearssst):
            year = yearssst[yr]
            sstavg = np.zeros(SSTzones)
            corr_df.loc[year, fcstPeriod] = list(seasonal_precip.loc[[year], fcstPeriod])[0]
            for group in range(SSTzones):
                sstavg[group] = "{0:.3f}".format(np.mean(sst_arr[yr][corgrp_matrix == basins[group]]))
                corr_df.loc[year, 'Basin' + str(basins[group])] = sstavg[group]
        corr_df = corr_df.dropna(how='all', axis=1)
        basin_arr = list(corr_df.columns)
        indx = basin_arr.index(fcstPeriod)
        basin_arr.pop(indx)
        # basins = [x.replace('Basin','') for x in basin_arr]
        if len(basin_arr) == 0:
            return None
        basin_matrix = np.array(corr_df[basin_arr])
        corroutdir = outdir + os.sep + "Correlation"
        writeout(prefix, p_matrix, corgrp_matrix, corr_df, predictordict['lats'],
                 predictordict['lons'], corroutdir, config)
    
        # get basin combination with highest r-square: returns bestr2score, final_basins, final_basin_matrix
        basin_matrix_df = pd.DataFrame(basin_matrix[:len(trainingYears)], columns=basin_arr)
        notnull = np.isfinite(np.array(predictand[:len(trainingYears)]))
        try:
            final_basins, comments = stepwise_selection(basin_matrix_df[notnull].astype(float),
                                                    list(predictand[:len(trainingYears)][notnull]),
                                                    initial_list=basin_arr, threshold_out=config.get('stepwisePvalue'))
        except:
            final_basins = basin_arr[:]
            comments = []
        selected_basins = final_basins[:]
        if len(final_basins) == 0:
            selected_basins = basin_arr[:]
            final_basins = basin_arr[:]
            comments = []
        comments.append("Final basins: " + str(final_basins))
        csv = corroutdir + os.sep + prefix + '_forward-selection.csv'
        comment_df = pd.DataFrame(columns=['Comment'])
        comment_df['Comment'] = comments
        if int(config.get('plots', {}).get('corrcsvs', 1)) == 1: comment_df.to_csv(csv, header=True, index=False)
    
        combo_basin_matrix = np.zeros((len(yearssst), len(final_basins))) * np.nan
        # loop for all years where SST is available
        for yr in range(len(yearssst)):
            for group in range(len(final_basins)):
                # get corresponding sst average for the group from main basin_matrix
                combo_basin_matrix[yr][group] = basin_matrix[yr][basin_arr.index(final_basins[group])]
    
        nbasins = len(final_basins)
    else:            
        nbasins = 1
        selected_basins = [prefixParam["Param"]]
        combo_basin_matrix = np.zeros((len(yearssst), nbasins)) * np.nan
        # loop for all years where SST is available
        for yr in range(len(yearssst)):
            # get corresponding sst average for the group from main basin_matrix
            combo_basin_matrix[yr][0] = sst_arr[yr]
            
      
    selected_basins.insert(0, 'y_intercept')      
    training_Xmatrix = combo_basin_matrix[:len(trainingYears)]
    testing_Xmatrix = combo_basin_matrix[len(trainingYears):]
    testing_years = yearssst[len(trainingYears):]
    notnull = np.isfinite(training_actual)
    t1, t2 = np.quantile(training_actual, [0.333, 0.666])
    # scale the predictor
    scaler = StandardScaler()
    scaler.fit(training_Xmatrix)
    StandardScaler(copy=True, with_mean=True, with_std=True)
    X_train = scaler.transform(training_Xmatrix)
    X_test = scaler.transform(testing_Xmatrix)
    regoutdir = outdir + os.sep + "Regression"
    os.makedirs(regoutdir, exist_ok=True)

    if algorithm == 'MLP':
        start_time = time.time()
        activation_fn = 'tanh'
        solver_fn = 'lbfgs'
        ratings = {}
        for x in range(2, 21):
            for y in range(0, 21):
                if y > x: continue
                hiddenlayerSize = (x + 1, y + 1)
                regm = MLPRegressor(hidden_layer_sizes=hiddenlayerSize,
                                    activation=activation_fn, solver=solver_fn, random_state=42, max_iter=700)
                try:
                    regm.fit(X_train[notnull], np.asarray(training_actual)[notnull])
                except:
                    continue
                forecasts = np.array(regm.predict(X_test))
                warnings.filterwarnings('error')
                try:
                    m, n = pearsonr(np.array(forecasts)[test_notnull], list(np.ravel(test_actual)[test_notnull]))
                except:
                    continue
                v = np.std(forecasts)
                ratings[str(x + 1) + '_' + str(y + 1)] = ((hit_score(forecasts, test_actual, t1, t2)+1) * (m**2), v)

        combs = sorted(ratings.items(), key=lambda xx: xx[1][0], reverse=True)
        v = np.std(np.ravel(test_actual[test_notnull]))
        r, s = None, None
        for x in range(len(combs)):
            if combs[x][1][0] >= 0.1 and combs[x][1][1] >= v / 2:
                r, s = combs[x][0].split('_')
                break
        if (r is not None) and (s is not None):
            if int(s) == 0:
                hiddenlayerSize = (int(r),)
            else:
                hiddenlayerSize = (int(r), int(s),)
            regm = MLPRegressor(hidden_layer_sizes=hiddenlayerSize,
                                activation=activation_fn, solver=solver_fn, random_state=42, max_iter=700)
            regm.fit(X_train[notnull], np.asarray(training_actual)[notnull])
            if int(config.get('plots', {}).get('trainingraphs', 0)) == 1:
                mlp_traindf = pd.DataFrame(columns=['Year', fcstPeriod, 'MLPfcst'])
                mlp_traindf['Year'] = trainingYears
                mlp_traindf[fcstPeriod] = training_actual
                mlp_traindf['MLPfcst'] =  np.array(regm.predict(X_train))
                mlp_traindf.set_index('Year', inplace=True)
            mlp_fcstdf = pd.DataFrame(columns=['Year', fcstPeriod, 'MLPfcst'])
            mlp_fcstdf['Year'] = testing_years
            mlp_fcstdf[fcstPeriod] = test_actual
            mlp_fcstdf['MLPfcst'] = np.array(regm.predict(X_test))
            mlp_fcstdf.set_index('Year', inplace=True)
            warnings.filterwarnings('error')
            m, n = pearsonr(np.array(mlp_fcstdf['MLPfcst'])[test_notnull], list(np.ravel(test_actual[test_notnull])))
            r2score = m ** 2
            mlpdirout = regoutdir + os.sep + 'MLP'
            os.makedirs(mlpdirout, exist_ok=True)
            file = mlpdirout + os.sep + prefix + '_' + fcstPeriod + '_mlpsummary.txt'
            if int(config.get('plots', {}).get('regrcsvs', 1)) == 1:
                f = open(file, 'w')
                f.write('MLPRegressor Parameters ---\n')
                f.write('architecture=' + str(nbasins) + ',' + r + ',' + s + ',1\n')
                f.write('r-square: ' + str(r2score) + ', p-value:' + str(n) + '\n')
                f.write('processing time: ' + str(time.time() - start_time) + ' seconds\n\n')
                f.write(json.dumps(regm.get_params(), indent=4, sort_keys=True))
                f.write('\n\n')
                f.write('Ranking of number of neurons per hidden layer (HL) ---\n')
                f.write('("HL1_HL2", (r2score, std))\n')
                for ele in combs[:20]:
                    f.write(str(ele) + '\n')
                f.close()
            csv = mlpdirout + os.sep + prefix + '_' + fcstPeriod + '_forecast_matrix.csv'
            mlp_fcstdf.reset_index()
            if int(config.get('plots', {}).get('regrcsvs', 1)) == 1: mlp_fcstdf.to_csv(csv, index=True)
            #
            q1, q2, q3, pmedian, famnt, fclass, HS, Prob, cgtable_df, skill_df = \
                run_model_skill(mlp_fcstdf, fcstPeriod, 'MLPfcst', r2score, training_actual)
            csv = mlpdirout + os.sep + prefix + '_score-contingency-table.csv'
            if int(config.get('plots', {}).get('regrcsvs', 1)) == 1: cgtable_df.to_csv(csv, index=False)
            csv = mlpdirout + os.sep + prefix + '_score-statistics.csv'
            if int(config.get('plots', {}).get('regrcsvs', 1)) == 1: skill_df.to_csv(csv, index=False)
            a_series = pd.DataFrame({'Predictor': predictorName, 'Algorithm': algorithm, 'ID': station, 
                                     'Lat': lat, 'Lon': lon, 't1': q1, 't2': q2, 't3': q3, 'median': pmedian, 
                                     'fcst': famnt, 'class': fclass, 'r2score': r2score, 'HS': HS, 'Prob': Prob}, index=[0])
            try:
                forecastdf = pd.concat([forecastdf, a_series], axis=0, ignore_index=True)
            except:
                forecastdf=a_series.copy()

            if int(config.get('plots', {}).get('trainingraphs', 0)) == 1:
                mlp_fcstdf = pd.concat([mlp_traindf, mlp_fcstdf], ignore_index=False)
            mlp_fcstdf.rename(columns={'MLPfcst': predictorName +'_MLP'}, inplace=True)
            stationYF_dfs.append(mlp_fcstdf)
                    
            if (nbasins == 1) and (int(config.get('plots', {}).get('regrcsvs', 1)) == 1):
                graphcpng = mlpdirout + os.sep + prefix + '_correlation-graph.png'
                graphdf = mlp_fcstdf.copy()
                graphdf[prefixParam["Param"]] = np.array(combo_basin_matrix).flatten()
                plot_correlation_graph(graphdf, fcstPeriod, prefixParam["Param"], predictorName + '_MLP', graphcpng)

    if algorithm == 'LR':
        # start_time = time.time()
        regr = linear_model.LinearRegression()
        regr.fit(X_train[notnull], np.asarray(training_actual)[notnull])
        intercept = regr.intercept_
        coefficients = regr.coef_
        if int(config.get('plots', {}).get('trainingraphs', 0)) == 1:
            lr_traindf = pd.DataFrame(columns=['Year', fcstPeriod, 'LRfcst'])
            lr_traindf['Year'] = trainingYears
            lr_traindf[fcstPeriod] = training_actual
            lr_traindf['LRfcst'] = np.array(regr.predict(X_train))
            lr_traindf.set_index('Year', inplace=True)
        lr_fcstdf = pd.DataFrame(columns=['Year', fcstPeriod, 'LRfcst'])
        lr_fcstdf['Year'] = testing_years
        lr_fcstdf[fcstPeriod] = test_actual
        lr_fcstdf['LRfcst'] = np.array(regr.predict(X_test))
        lr_fcstdf.set_index('Year', inplace=True)
        warnings.filterwarnings('error')
        try:
            m, n = pearsonr(np.array(lr_fcstdf['LRfcst'])[test_notnull], list(np.ravel(test_actual)[test_notnull]))
        except:
            return None
        r2score = m ** 2
        lrdirout = regoutdir + os.sep + 'LR'
        os.makedirs(lrdirout, exist_ok=True)
        csv = lrdirout + os.sep + prefix + '_' + fcstPeriod + '_forecast_matrix.csv'
        lr_fcstdf.reset_index()
        if int(config.get('plots', {}).get('regrcsvs', 1)) == 1: lr_fcstdf.to_csv(csv, index=True)
        #
        regrFormula = {"intercept": intercept, "coefficients": coefficients}
        coeff_arr = list(regrFormula["coefficients"])
        coeff_arr.insert(0, regrFormula["intercept"])
        reg_df = pd.DataFrame(columns=selected_basins)
        reg_df.loc[0] = coeff_arr
        csv = lrdirout+ os.sep + prefix + '_correlation-formula.csv'
        if int(config.get('plots', {}).get('regrcsvs', 1)) == 1: reg_df.to_csv(csv, index=False)
        #
        q1, q2, q3, pmedian, famnt, fclass, HS, Prob, cgtable_df, skill_df = \
            run_model_skill(lr_fcstdf, fcstPeriod, 'LRfcst', r2score, training_actual)
        csv = lrdirout + os.sep + prefix + '_score-contingency-table.csv'
        if int(config.get('plots', {}).get('regrcsvs', 1)) == 1: cgtable_df.to_csv(csv, index=False)
        csv = lrdirout + os.sep + prefix + '_score-statistics.csv'
        if int(config.get('plots', {}).get('regrcsvs', 1)) == 1: skill_df.to_csv(csv, index=False)
        a_series = pd.DataFrame({'Predictor': predictorName, 'Algorithm': algorithm, 'ID': station, 
                                 'Lat': lat, 'Lon': lon, 't1': q1, 't2': q2, 't3': q3, 'median': pmedian, 
                                 'fcst': famnt, 'class': fclass, 'r2score': r2score, 'HS': HS, 'Prob': Prob}, index=[0])
        try:
            forecastdf = pd.concat([forecastdf, a_series], axis=0, ignore_index=True)
        except:
            forecastdf=a_series.copy()

        if int(config.get('plots', {}).get('trainingraphs', 0)) == 1:
            lr_fcstdf = pd.concat([lr_traindf, lr_fcstdf], ignore_index=False)
        lr_fcstdf.rename(columns={'LRfcst': predictorName + '_LR'}, inplace=True)
        stationYF_dfs.append(lr_fcstdf)
                
        if (nbasins == 1) and (int(config.get('plots', {}).get('regrcsvs', 1)) == 1):
            graphcpng = lrdirout+ os.sep + prefix + '_correlation-graph.png'
            graphdf = lr_fcstdf.copy()
            graphdf[prefixParam["Param"]] = np.array(combo_basin_matrix).flatten()
            plot_correlation_graph(graphdf, fcstPeriod, prefixParam["Param"], predictorName + '_LR', graphcpng)

    # plot the forecast graphs
    if (len(stationYF_dfs) > 0) and (int(config.get('plots', {}).get('fcstgraphs', 1)) == 1):
        stationYF_df = pd.concat(stationYF_dfs, axis=1, join='outer')
        stationYF_df = stationYF_df.loc[:, ~stationYF_df.columns.duplicated()]
        stationYF_df = stationYF_df.reset_index()
        fcstoutdir = outdir + os.sep + "Forecast"
        os.makedirs(fcstoutdir, exist_ok=True)
        graphpng = fcstoutdir + os.sep + 'forecast_graphs_' + station + '_' + predictorName + '_' + algorithm + '.png'
        plot_Station_forecast(stationYF_df, fcstPeriod, graphpng, station, q1, q2, q3)
        
    # return station forecast
    if isinstance(forecastdf, pd.DataFrame):
        return forecastdf
    else:
        return None

def forecast_station(config, predictordict, predictanddict, fcstPeriod, outdir, station):
    output = {}
    stationYF_dfs = []
    output[station] = {}
    input_data = predictanddict['data']
    indx = predictanddict['stations'].index(station)
    lat = predictanddict['lats'][indx]
    lon = predictanddict['lons'][indx]
    station_data_all =  input_data.loc[input_data['ID'] == station]
    trainStartYear = int(config['trainStartYear'])
    trainEndYear = int(config['trainEndYear'])
    fcstYear = int(config['fcstyear'])
    trainingYears = [yr for yr in range(trainStartYear, trainEndYear + 1)]
    nyears = len(trainingYears)
    #forecastdf = pd.DataFrame(columns=['Predictor', 'Algorithm', 'ID', 'Lat', 'Lon', 't1', 't2', 't3',
    #                                   'median', 'fcst', 'class', 'r2score', 'HS', 'Prob'])
    for predictorName in predictordict:
        output[station][predictorName] = {}
        predictorStartYr = predictordict[predictorName]['predictorStartYr']
        sst_arr = predictordict[predictorName]['data']
        prefixParam = {"Predictor": predictorName, "Param": predictordict[predictorName]['param'],
                       "PredictorMonth": predictordict[predictorName]['predictorMonth'],
                       "startyr": trainStartYear, "endyr": config['trainEndYear'],
                       "fcstYear": config['fcstyear'], "fcstPeriod": fcstPeriod, "station": str(station)}
        try:
            nyearssst, nrowssst, ncolssst = sst_arr.shape
        except ValueError:
            nyearssst, nrowssst, ncolssst = len(sst_arr), 0, 0
        yearspredictand = [yr for yr in range(trainStartYear, (trainStartYear + nyearssst))]
        print(station,nyearssst, yearspredictand)
        station_data = station_data_all.loc[:,
                       ('Year', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')]
        station_data.drop_duplicates('Year', inplace=True)
        station_data = station_data.apply(pd.to_numeric, errors='coerce')
        seasonal_precip = pd.DataFrame(columns=['Year',fcstPeriod])
        seasonal_precip['Year'] = yearspredictand
        seasonal_precip.set_index('Year', inplace=True)
        station_data.set_index('Year', inplace=True)
        for year in yearspredictand:
            if config.get('fcstPeriodLength', '3month') == '3month':
                if config['composition'] == "Sum":
                    temp=season_cumulation(station_data, year, fcstPeriod)
                    seasonal_precip.loc[[year], fcstPeriod] = temp
                else:
                    seasonal_precip.loc[[year], fcstPeriod] = season_average(station_data, year, fcstPeriod)
            else:
                try:
                    seasonal_precip.loc[[year], fcstPeriod] = round(float(station_data.loc[[year], fcstPeriod]), 1)
                except KeyError:
                    seasonal_precip.loc[[year], fcstPeriod] = np.nan
                    
        predictand = np.asarray(seasonal_precip, dtype=float).reshape(-1,)
        training_actual = predictand[:len(trainingYears)]
        test_actual = predictand[len(trainingYears):]
        test_notnull = np.isfinite(test_actual)
        name = re.sub('[^a-zA-Z0-9]', '', prefixParam["station"])
        prefix = prefixParam["Predictor"] + '_' + prefixParam["Param"] + '_' + prefixParam["PredictorMonth"] + '_' + \
                 str(prefixParam["startyr"]) + '-' + str(prefixParam["endyr"]) + '_' + name
        
        if (len(training_actual[np.isfinite(training_actual)]) < 6) or (len(test_actual[np.isfinite(test_actual)]) < 2):
            #print("not enough data to train")      
            continue

        # compute basins
        trainPredictand = predictand[:nyears]
        trainSST = sst_arr[:nyears]
        pnotnull = np.isfinite(trainPredictand)
        yearssst = [yr for yr in range(predictorStartYr, (predictorStartYr + nyearssst))]
        print("s",station,yearssst)
        #yearssst = [yr for yr in range(trainStartYear, (trainStartYear + nyearssst))]
        print(station, yearspredictand,yearssst,len(yearspredictand),len(yearssst))
        if (nrowssst, ncolssst) != (0, 0): 
            SSTclusterSize = 1000.
            lons2d, lats2d = np.meshgrid(predictordict[predictorName]['lons'], predictordict[predictorName]['lats'])
            # calculate correlation
            r_matrix = np.zeros((nrowssst, ncolssst))
            p_matrix = np.zeros((nrowssst, ncolssst))
            for row in range(nrowssst):
                for col in range(ncolssst):
                    sstvals = np.array(trainSST[:, row][:, col], dtype=float)
                    warnings.filterwarnings('error')
                    try:
                        notnull = pnotnull & np.isfinite(sstvals)
                        r_matrix[row][col], p_matrix[row][col] = pearsonr(trainPredictand[notnull], sstvals[notnull])
                    except:
                        pass
            # corr = (p_matrix <= config['PValue']) & (abs(r_matrix) >= 0.5)
            corr = (p_matrix <= config['PValue']) & (p_matrix != 0)
            if not corr.any():
                continue
            corr_coords = list(zip(lons2d[corr], lats2d[corr]))
            # create correlation basins
            corgrp_matrix = np.zeros((nrowssst, ncolssst)) * np.nan
    
            minx = float(config.get('basinbounds',{}).get('minlon', -180))
            maxx = float(config.get('basinbounds',{}).get('maxlon', 366))
            miny = float(config.get('basinbounds',{}).get('minlat', -90))
            maxy = float(config.get('basinbounds',{}).get('maxlat', 90))
            roi = [False] * len(corr_coords)
            for i in range(len(corr_coords)):
                if corr_coords[i][0] < minx or corr_coords[i][0] > maxx or corr_coords[i][1] < miny or \
                        corr_coords[i][1] > maxy:
                    roi[i] = True
    
            db = dbcluster(corr_coords, 'dbscan', 5, SSTclusterSize, 3, 2)
            coords_clustered = np.array(db.labels_)
            coords_clustered[roi] = -1
            uniq = list(set(coords_clustered))
            minpixelperbasin = 6
            for zone in uniq:
                count = len(coords_clustered[coords_clustered == zone])
                if count < minpixelperbasin: coords_clustered[coords_clustered == zone] = -1
    
            basins = list(set(coords_clustered[coords_clustered != -1]))
            SSTzones = len(basins)
            if corr[corr == True].shape == coords_clustered.shape:
                index = 0
                for row in range(nrowssst):
                    for col in range(ncolssst):
                        if corr[row][col]:
                            corgrp_matrix[row][col] = coords_clustered[index]
                            index = index + 1
            # generate correlation group matrices
            basin_arr = ['Basin' + str(x) for x in basins]
            basin_arr.insert(0, fcstPeriod)
            basin_arr.insert(0, 'year')
            corr_df = pd.DataFrame(columns=basin_arr)
            corr_df['year'] = trainingYears
            corr_df[fcstPeriod] = trainPredictand
            corr_df.set_index('year', inplace=True)
            print(station,nyearssst,len(yearspredictand),len(yearssst))
            for yr in range(nyearssst):
                yearsst = yearssst[yr]
                yearpredictand = yearspredictand[yr]
                sstavg = np.zeros(SSTzones)
                corr_df.loc[yearpredictand, fcstPeriod] = list(seasonal_precip.loc[[yearpredictand], fcstPeriod])[0]
                for group in range(SSTzones):
                    sstavg[group] = "{0:.3f}".format(np.mean(sst_arr[yr][corgrp_matrix == basins[group]]))
                    corr_df.loc[year, 'Basin' + str(basins[group])] = sstavg[group]
            corr_df = corr_df.dropna(how='all', axis=1)
            basin_arr = list(corr_df.columns)
            indx = basin_arr.index(fcstPeriod)
            basin_arr.pop(indx)
            # basins = [x.replace('Basin','') for x in basin_arr]
            if len(basin_arr) == 0:
                continue
            basin_matrix = np.array(corr_df[basin_arr])
            corroutdir = outdir + os.sep + "Correlation"
            writeout(prefix, p_matrix, corgrp_matrix, corr_df, predictordict[predictorName]['lats'],
                     predictordict[predictorName]['lons'], corroutdir, config)
    
            # get basin combination with highest r-square: returns bestr2score, final_basins, final_basin_matrix
            basin_matrix_df = pd.DataFrame(basin_matrix[:len(trainingYears)], columns=basin_arr)
            notnull = np.isfinite(np.array(predictand[:len(trainingYears)]))
            try:
                final_basins, comments = stepwise_selection(basin_matrix_df[notnull].astype(float),
                                                        list(predictand[:len(trainingYears)][notnull]),
                                                        initial_list=basin_arr, threshold_out=config.get('stepwisePvalue'))
            except:
                final_basins = basin_arr[:]
                comments = []
            selected_basins = final_basins[:]
            if len(final_basins) == 0:
                selected_basins = basin_arr[:]
                final_basins = basin_arr[:]
                comments = []
            
            comments.append("Final basins: " + str(final_basins))
            csv = corroutdir + os.sep + prefix + '_forward-selection.csv'
            comment_df = pd.DataFrame(columns=['Comment'])
            comment_df['Comment'] = comments
            if int(config.get('plots', {}).get('corrcsvs', 1)) == 1: comment_df.to_csv(csv, header=True, index=False)
            
            combo_basin_matrix = np.zeros((len(yearssst), len(final_basins))) * np.nan
            # loop for all years where SST is available
            for yr in range(len(yearssst)):
                for group in range(len(final_basins)):
                    # get corresponding sst average for the group from main basin_matrix
                    combo_basin_matrix[yr][group] = basin_matrix[yr][basin_arr.index(final_basins[group])]
    
            nbasins = len(final_basins)
        else:            
            nbasins = 1
            selected_basins = [prefixParam["Param"]]
            combo_basin_matrix = np.zeros((len(yearssst), nbasins)) * np.nan
            # loop for all years where SST is available
            for yr in range(len(yearssst)):
                # get corresponding sst average for the group from main basin_matrix
                combo_basin_matrix[yr][0] = sst_arr[yr]

        selected_basins.insert(0, 'y_intercept')
        training_Xmatrix = combo_basin_matrix[:len(trainingYears)]
        testing_Xmatrix = combo_basin_matrix[len(trainingYears):]
        testing_years = yearssst[len(trainingYears):]
        notnull = np.isfinite(training_actual)
        t1, t2 = np.quantile(training_actual, [0.333, 0.666])
        # scale the predictor
        scaler = StandardScaler()
        scaler.fit(training_Xmatrix)
        StandardScaler(copy=True, with_mean=True, with_std=True)
        X_train = scaler.transform(training_Xmatrix)
        X_test = scaler.transform(testing_Xmatrix)
        regoutdir = outdir + os.sep + "Regression"
        os.makedirs(regoutdir, exist_ok=True)
        
        for algorithm in config.get('algorithms'):

            if algorithm == 'MLP':
                start_time = time.time()
                activation_fn = 'tanh'
                solver_fn = 'lbfgs'
                ratings = {}
                for x in range(2, 21):
                    for y in range(0, 21):
                        if y > x: continue
                        hiddenlayerSize = (x + 1, y + 1)
                        regm = MLPRegressor(hidden_layer_sizes=hiddenlayerSize,
                                            activation=activation_fn, solver=solver_fn, random_state=42, max_iter=700)
                        try:
                            regm.fit(X_train[notnull], np.asarray(training_actual)[notnull])
                        except:
                            continue
                        forecasts = np.array(regm.predict(X_test))
                        warnings.filterwarnings('error')
                        try:
                            m, n = pearsonr(forecasts[test_notnull], list(np.ravel(test_actual)[test_notnull]))
                        except:
                            continue
                        v = np.std(forecasts)
                        ratings[str(x + 1) + '_' + str(y + 1)] = ((hit_score(forecasts, test_actual, t1, t2)+1) * (m**2), v)

                combs = sorted(ratings.items(), key=lambda xx: xx[1][0], reverse=True)
                v = np.std(np.ravel(test_actual[test_notnull]))
                r, s = None, None
                for x in range(len(combs)):
                    if combs[x][1][0] >= 0.1 and combs[x][1][1] >= v / 2:
                        r, s = combs[x][0].split('_')
                        break
                if (r is not None) and (s is not None):
                    if int(s) == 0:
                        hiddenlayerSize = (int(r),)
                    else:
                        hiddenlayerSize = (int(r), int(s),)
                    regm = MLPRegressor(hidden_layer_sizes=hiddenlayerSize,
                                        activation=activation_fn, solver=solver_fn, random_state=42, max_iter=700)
                    regm.fit(X_train[notnull], np.asarray(training_actual)[notnull])
                    if int(config.get('plots', {}).get('trainingraphs', 0)) == 1:
                        mlp_traindf = pd.DataFrame(columns=['Year', fcstPeriod, 'MLPfcst'])
                        mlp_traindf['Year'] = trainingYears
                        mlp_traindf[fcstPeriod] = training_actual
                        mlp_traindf['MLPfcst'] =  np.array(regm.predict(X_train))
                        mlp_traindf.set_index('Year', inplace=True)
                    mlp_fcstdf = pd.DataFrame(columns=['Year', fcstPeriod, 'MLPfcst'])
                    mlp_fcstdf['Year'] = testing_years
                    mlp_fcstdf[fcstPeriod] = test_actual
                    mlp_fcstdf['MLPfcst'] = np.array(regm.predict(X_test))
                    mlp_fcstdf.set_index('Year', inplace=True)
                    warnings.filterwarnings('error')
                    m, n = pearsonr(np.array(mlp_fcstdf['MLPfcst'])[test_notnull], list(np.ravel(test_actual[test_notnull])))
                    r2score = m ** 2
                    mlpdirout = regoutdir + os.sep + 'MLP'
                    os.makedirs(mlpdirout, exist_ok=True)
                    file = mlpdirout + os.sep + prefix + '_' + fcstPeriod + '_mlpsummary.txt'
                    if int(config.get('plots', {}).get('regrcsvs', 1)) == 1:
                        f = open(file, 'w')
                        f.write('MLPRegressor Parameters ---\n')
                        f.write('architecture=' + str(nbasins) + ',' + r + ',' + s + ',1\n')
                        f.write('r-square: ' + str(r2score) + ', p-value:' + str(n) + '\n')
                        f.write('processing time: ' + str(time.time() - start_time) + ' seconds\n\n')
                        f.write(json.dumps(regm.get_params(), indent=4, sort_keys=True))
                        f.write('\n\n')
                        f.write('Ranking of number of neurons per hidden layer (HL) ---\n')
                        f.write('("HL1_HL2", (r2score, std))\n')
                        for ele in combs[:20]:
                            f.write(str(ele) + '\n')
                        f.close()
                    csv = mlpdirout + os.sep + prefix + '_' + fcstPeriod + '_forecast_matrix.csv'
                    mlp_fcstdf.reset_index()
                    if int(config.get('plots', {}).get('regrcsvs', 1)) == 1: mlp_fcstdf.to_csv(csv, index=True)
                    #
                    q1, q2, q3, pmedian, famnt, fclass, HS, Prob, cgtable_df, skill_df = \
                        run_model_skill(mlp_fcstdf, fcstPeriod, 'MLPfcst', r2score, training_actual)
                    csv = mlpdirout + os.sep + prefix + '_score-contingency-table.csv'
                    if int(config.get('plots', {}).get('regrcsvs', 1)) == 1: cgtable_df.to_csv(csv, index=False)
                    csv = mlpdirout + os.sep + prefix + '_score-statistics.csv'
                    if int(config.get('plots', {}).get('regrcsvs', 1)) == 1: skill_df.to_csv(csv, index=False)
                    a_series = pd.DataFrame({'Predictor': predictorName, 'Algorithm': algorithm, 'ID': station, 
                                             'Lat': lat, 'Lon': lon, 't1': q1, 't2': q2, 't3': q3, 'median': pmedian, 
                                             'fcst': famnt, 'class': fclass, 'r2score': r2score, 'HS': HS, 'Prob': Prob}, index=[0])
                    try:
                        forecastdf = pd.concat([forecastdf, a_series], axis=0, ignore_index=True)
                    except:
                        forecastdf = a_series.copy()

                    if int(config.get('plots', {}).get('trainingraphs', 0)) == 1:
                        mlp_fcstdf = pd.concat([mlp_traindf, mlp_fcstdf], ignore_index=False)
                    mlp_fcstdf.rename(columns={'MLPfcst': predictorName +'_MLP'}, inplace=True)
                    stationYF_dfs.append(mlp_fcstdf)
                    
                    if (nbasins == 1) and (int(config.get('plots', {}).get('regrcsvs', 1)) == 1):
                        graphcpng = mlpdirout + os.sep + prefix + '_correlation-graph.png'
                        graphdf = mlp_fcstdf.copy()
                        graphdf[prefixParam["Param"]] = np.array(combo_basin_matrix).flatten()
                        plot_correlation_graph(graphdf, fcstPeriod, prefixParam["Param"], predictorName + '_MLP', graphcpng)

            if algorithm == 'LR':
                # start_time = time.time()
                regr = linear_model.LinearRegression()
                regr.fit(X_train[notnull], np.asarray(training_actual)[notnull])
                intercept = regr.intercept_
                coefficients = regr.coef_
                if int(config.get('plots', {}).get('trainingraphs', 0)) == 1:
                    lr_traindf = pd.DataFrame(columns=['Year', fcstPeriod, 'LRfcst'])
                    lr_traindf['Year'] = trainingYears
                    lr_traindf[fcstPeriod] = training_actual
                    lr_traindf['LRfcst'] = np.array(regr.predict(X_train))
                    lr_traindf.set_index('Year', inplace=True)
                lr_fcstdf = pd.DataFrame(columns=['Year', fcstPeriod, 'LRfcst'])
                lr_fcstdf['Year'] = testing_years
                lr_fcstdf[fcstPeriod] = test_actual
                lr_fcstdf['LRfcst'] = np.array(regr.predict(X_test))
                lr_fcstdf.set_index('Year', inplace=True)
                warnings.filterwarnings('error')
                try:
                    m, n = pearsonr(np.array(lr_fcstdf['LRfcst'])[test_notnull], list(np.ravel(test_actual)[test_notnull]))
                except:
#                    print(station,"failed correlation")
                    continue
                r2score = m ** 2
                lrdirout = regoutdir + os.sep + 'LR'
                os.makedirs(lrdirout, exist_ok=True)
                csv = lrdirout + os.sep + prefix + '_' + fcstPeriod + '_forecast_matrix.csv'
                lr_fcstdf.reset_index()
                if int(config.get('plots', {}).get('regrcsvs', 1)) == 1: lr_fcstdf.to_csv(csv, index=True)
                #
                regrFormula = {"intercept": intercept, "coefficients": coefficients}
                coeff_arr = list(regrFormula["coefficients"])
                coeff_arr.insert(0, regrFormula["intercept"])
                reg_df = pd.DataFrame(columns=selected_basins)
                reg_df.loc[0] = coeff_arr
                csv = lrdirout+ os.sep + prefix + '_correlation-formula.csv'
                if int(config.get('plots', {}).get('regrcsvs', 1)) == 1: reg_df.to_csv(csv, index=False)
                
                q1, q2, q3, pmedian, famnt, fclass, HS, Prob, cgtable_df, skill_df = \
                    run_model_skill(lr_fcstdf, fcstPeriod, 'LRfcst', r2score, training_actual)
                csv = lrdirout + os.sep + prefix + '_score-contingency-table.csv'
                if int(config.get('plots', {}).get('regrcsvs', 1)) == 1: cgtable_df.to_csv(csv, index=False)
                csv = lrdirout + os.sep + prefix + '_score-statistics.csv'
                if int(config.get('plots', {}).get('regrcsvs', 1)) == 1: skill_df.to_csv(csv, index=False)
                a_series = pd.DataFrame({'Predictor': predictorName, 'Algorithm': algorithm, 'ID': station, 
                                         'Lat': lat, 'Lon': lon, 't1': q1, 't2': q2, 't3': q3, 'median': pmedian, 
                                         'fcst': famnt, 'class': fclass, 'r2score': r2score, 'HS': HS, 'Prob': Prob}, index=[0])

                try:
                    forecastdf = pd.concat([forecastdf, a_series], axis=0, ignore_index=True)
                except:
                    forecastdf=a_series.copy()

                if int(config.get('plots', {}).get('trainingraphs', 0)) == 1:
                    lr_fcstdf = pd.concat([lr_traindf, lr_fcstdf], ignore_index=False)
                    
                lr_fcstdf.rename(columns={'LRfcst': predictorName + '_LR'}, inplace=True)
                stationYF_dfs.append(lr_fcstdf)
                
                if (nbasins == 1) and (int(config.get('plots', {}).get('regrcsvs', 1)) == 1):
                    graphcpng = lrdirout+ os.sep + prefix + '_correlation-graph.png'
                    graphdf = lr_fcstdf.copy()
                    graphdf[prefixParam["Param"]] = np.array(combo_basin_matrix).flatten()
                    plot_correlation_graph(graphdf, fcstPeriod, prefixParam["Param"], predictorName + '_LR', graphcpng)

    # plot the forecast graphs
    if (len(stationYF_dfs) > 0) and (int(config.get('plots', {}).get('fcstgraphs', 1)) == 1):
        stationYF_df = pd.concat(stationYF_dfs, axis=1, join='outer')
        stationYF_df = stationYF_df.loc[:, ~stationYF_df.columns.duplicated()]
        stationYF_df = stationYF_df.reset_index()
        fcstoutdir = outdir + os.sep + "Forecast"
        os.makedirs(fcstoutdir, exist_ok=True)
        graphpng = fcstoutdir + os.sep + 'forecast_graphs_' + station + '.png'
        plot_Station_forecast(stationYF_df, fcstPeriod, graphpng, station, q1, q2, q3)
    # return station forecast
    try:
        if isinstance(forecastdf, pd.DataFrame):
            return forecastdf
        else:
            return None
    except:

        return None
