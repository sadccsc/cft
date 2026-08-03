# -*- coding: utf-8 -*-
"""
originally developed in 2019-2020
@author: thembani

September 2025:
adapted to work in the cft v5 framework 
@author P.Wolski wolski@csag.uct.ac.za

"""
from cft.functions import functions_zoning as ff
import matplotlib.pyplot as plt
import numpy as np
import threading
from sklearn.decomposition import FactorAnalysis, PCA
from sklearn.preprocessing import StandardScaler
from sklearn import cluster
import pandas as pd
import os, time, sys, re
from datetime import datetime
import geojson, json
import math
from pathlib import Path
from shapely.geometry import shape, Point, Polygon
from descartes import PolygonPatch
from netCDF4 import Dataset
from osgeo import ogr
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import QThread, QObject, QDate, QTime, QDateTime, Qt

from cft import gl

qtCreatorFile = os.path.join(os.path.dirname(__file__), "zoning.ui")
settingsfile = 'zoning.json'
csvheader = 'Year,Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec'

def lat(stn, df):
    return float(df.loc[df.Station==stn]['Lat'])

def lon(stn, df):
    return float(df.loc[df.Station==stn]['Lon'])

def simple_idw(x, y, z, xi, yi):
    dist = distance_matrix(x,y, xi,yi)
    # In IDW, weights are 1 / distance
    weights = 1.0 / dist
    # Make weights sum to one
    weights /= weights.sum(axis=0)
    # Multiply the weights for each interpolated point by all observed Z-values
    zi = np.dot(weights.T, z)
    return zi

def linear_rbf(x, y, z, xi, yi):
    dist = distance_matrix(x,y, xi,yi)
    # Mutual pariwise distances between observations
    internal_dist = distance_matrix(x,y, x,y)
    # Now solve for the weights such that mistfit at the observations is minimized
    weights = np.linalg.solve(internal_dist, z)
    # Multiply the weights for each interpolated point by the distances
    zi =  np.dot(dist.T, weights)
    return zi


def distance_matrix(x0, y0, x1, y1):
    obs = np.vstack((x0, y0)).T
    interp = np.vstack((x1, y1)).T
    # Make a distance matrix between pairwise observations
    d0 = np.subtract.outer(obs[:,0], interp[:,0])
    d1 = np.subtract.outer(obs[:,1], interp[:,1])
    return np.hypot(d0, d1)


def convert(seconds):
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    return "%d hour(s) %d minute(s) %d second(s)" % (hour, minutes, seconds)

def shortest_distance(x1, y1, a, b, c): 
    return abs((a * x1 + b * y1 + c)) / (math.sqrt(a * a + b * b))


def fixname(text):
    newname = re.sub("[^0-9a-zA-Z]+", "_", str(text).strip())
    return newname.strip('_')

def concat_csvs(csvs, missing):
    dfs_files = []
    for file in csvs:
        dfs_files.append(pd.read_csv(file, encoding = 'ISO-8859-9', decimal='.'))
    dfs_files = pd.concat((dfs_files), axis=0)
    dfs_files = dfs_files.replace(str(missing), np.nan)
    dfs_files = dfs_files.dropna(how='all')
    dfs_files['ID'] = dfs_files['ID'].apply(fixname)
    return dfs_files


def stationdata(idata, station, season):
    smonths = ff.season_months[season][:]
    smonths.insert(0, 'Year')
    sdata = idata.loc[idata.ID==station][smonths]
    sdata.drop_duplicates('Year', inplace=True)
    sdata = sdata.apply(pd.to_numeric, errors='coerce')
    sdata.set_index('Year', inplace=True)
    return sdata

def bigger(bounds1, bounds2):
    # check if bounds1 is bigger than bounds2
    minx1, miny1, maxx1, maxy1 = bounds1
    minx2, miny2, maxx2, maxy2 = bounds2
    if (maxy1 - miny1) * (maxx1 - minx1) > (maxy2 - miny2) * (maxx2 - minx2):
        return 1
    else:
        return 0


def smooth(shp,out,name,smooth_size):
    driver = ogr.GetDriverByName('GeoJSON')
    dataSource = driver.Open(shp, 0)  # 0 It's read-only ,1 Can write 
    layer = dataSource.GetLayer(0)
    t = int(layer.GetFeatureCount())
    drv = ogr.GetDriverByName('GeoJSON')
    Polygon = drv.CreateDataSource(out)
    oLayer = Polygon.CreateLayer(name)
    oFieldID = ogr.FieldDefn("Zone", ogr.OFTInteger)
    oLayer.CreateField(oFieldID, 1)
    feature = ogr.Feature(oLayer.GetLayerDefn())
    ID=0
    for i in range(0, t):
        feat = layer.GetFeature(i)
        geom = feat.GetGeometryRef()
        ID = ID+1
        buffer = geom.Buffer(smooth_size).Buffer(-smooth_size)
        feature.SetGeometry(buffer)
        feature.SetField(0, ID)
        oLayer.CreateFeature(feature)

def create_nc(outfile, zonegrid, lats, lons):
    print(outfile)
    rows = len(lats)
    cols = len(lons)
    startyr = str(gl.config.get('startyr'))
    endyr = str(gl.config.get('endyr'))
    period = gl.config.get('period').get('season')[int(gl.config.get('period').get('indx'))]
    title = 'Rasterized zonal map ' + period + ' ' + startyr + ' - ' + endyr 
    timenow = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")
    print("here")
    output = Dataset(outfile, 'w', format='NETCDF4')
    print("here")
    output.description = title
    output.comments = 'Created ' + timenow
    output.source = 'CFT'
    output.history = 'Created ' + timenow
    lat = output.createDimension('lat', rows)
    lon = output.createDimension('lon', cols)
    #T = output.createDimension('T', 1)
    #initial_date = output.createVariable('target', np.float64, ('T',))
    latitudes = output.createVariable('lat', np.float32, ('lat',))
    longitudes = output.createVariable('lon', np.float32, ('lon',))
    #zones = output.createVariable('Zones', np.uint8, ('T', 'lat', 'lon'))
    zones = output.createVariable('Zones', np.uint8, ('lat', 'lon'))
    latitudes.units = 'degree_north'
    latitudes.axis = 'Y'
    latitudes.long_name = 'Latitude'
    latitudes.standard_name = 'Latitude'
    longitudes.units = 'degree_east'
    longitudes.axis = 'X'
    longitudes.long_name = 'Longitude'
    longitudes.standard_name = 'Longitude'
    #initial_date.units = 'days since ' + timenow
    #initial_date.axis = 'T'
    #initial_date.calendar = 'standard'
    #initial_date.standard_name = 'time'
    #initial_date.long_name = 'zoning date'
    latitudes[:] = lats
    longitudes[:] = lons
    zones[:] = zonegrid
    zones.units = 'Zone ID'
    output.close()
    print("done")

def sizeof_fmt(num, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"

#
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)

class MyApp(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)


def closeapp():
    sys.exit(gl.app.exec_())

def addBaseVector():
    gl.window.inputlayerlabel.setText('')
    gl.config['base_vector'] = {"file": '', "ID": 0, "attr": []}
    vectorfieldsx = []
    # gl.window.zoneIDcomboBox.setDuplicatesEnabled(False)
    fileName = QtWidgets.QFileDialog.getOpenFileName(gl.window,
              'Add File', '..' + os.sep, filter="GeoJson File (*.geojson)")
    gl.config['base_vector']['file'] = fileName[0]
    gl.window.inputlayerlabel.setText(os.path.basename(gl.config.get('base_vector',{}).get('file')))

def getOutDir():
    gl.config['outdir'] = QtWidgets.QFileDialog.getExistingDirectory(directory='..' + os.sep)
    gl.window.outdirlabel.setText(gl.config.get('outdir'))

def addPredictands():
    global csvheader
    gl.config['predictandList'] = []
    gl.window.predictandlistWidget.clear()
    gl.window.predictandparamcombobox.clear()
    gl.window.statusbar.showMessage("")
    if gl.window.CSVRadio.isChecked() == True:
        gl.config['inputFormat'] = "CSV"
        fileNames = QtWidgets.QFileDialog.getOpenFileNames(gl.window,
                'Add File(s)', '..' + os.sep, filter="CSV File (*.csv)")
        for filename in fileNames[0]:
            with open(filename) as f:
                fline = f.readline().rstrip()
            if fline.count(',') < 4:
                gl.window.statusbar.showMessage(
                    "Format error in "+os.path.basename(filename)+", check if comma delimited")
                continue
            if csvheader not in fline:
                gl.window.statusbar.showMessage(
                    "Format error, one or more column headers incorrect in " + os.path.basename(filename))
                continue
            if 'ID' not in fline:
                gl.window.statusbar.showMessage(
                    "Format error, station name column header should be labelled as ID in " + os.path.basename(filename))
                continue
            gl.config['predictandList'].append(filename)
            gl.window.predictandlistWidget.addItem(os.path.basename(filename))
    elif gl.window.NetCDFRadio.isChecked() == True:
        gl.config['inputFormat'] = "NetCDF"
        try:
            fileName = QtWidgets.QFileDialog.getOpenFileNames(gl.window,
                'Add File', '..' + os.sep, filter="NetCDF File (*.nc*)")[0]
            predictand = Dataset(fileName[0])
            for key in predictand.variables.keys():
                if key not in ['Y', 'X', 'Z', 'T', 'zlev', 'time', 'lon', 'lat']:
                    gl.window.predictandparamcombobox.addItem(key)
            gl.config['predictandList'].append(fileName[0])
            gl.window.predictandlistWidget.addItem(os.path.basename(fileName[0]))
        except:
            gl.window.statusbar.showMessage(
                "Could not read predictand file, check if it is a valid NetCDF")
            return

def clearPredictands():
    gl.config['predictandList'] = []
    gl.window.predictandlistWidget.clear()
    gl.window.predictandparamcombobox.clear()

def change_format_type():
    gl.window.predictandlistWidget.clear()
    gl.window.predictandparamcombobox.clear()
    if gl.window.CSVRadio.isChecked() == True:
        gl.config['inputFormat'] = "CSV"
    else:
        gl.config['inputFormat'] = "NetCDF"

def change_interpolation():
    if gl.window.radioButtonIDW.isChecked() == True:
        gl.config['interpolation'] = "idw"
    else: 
        gl.config['interpolation'] = "linear"
        
def change_composition():
    if gl.window.cumRadio.isChecked() == True:
        gl.config['composition'] = "Sum"
    else: 
        gl.config['composition'] = "Avg"
    
def write_config():
    global settingsfile
    gl.config['ExplainedVariance'] = float(gl.window.PEV.text())
    gl.config['gridsize'] = float(gl.window.gridsizelineEdit.text())
    gl.config['predictandMissingValue'] = str(gl.window.missingvalueslineEdit.text())  
    gl.config['startyr'] = int(gl.window.startyearLineEdit.text())
    gl.config['endyr'] = int(gl.window.endyearLineEdit.text())
    gl.config['zones'] = gl.window.ZonesLineEdit.text()
    gl.config['rotation']['indx'] = gl.config.get('rotation').get('types').index(gl.window.rotationDcombobox.currentText())
    gl.config['period']['indx'] = gl.config.get('period').get('season').index(gl.window.periodComboBox.currentText())
    # Write configuration to settings file
    with open(settingsfile, 'w') as fp:
        json.dump(gl.config, fp, indent=4)
        

def launch_zoning_Thread():
    t = threading.Thread(target=exec_zoning)
    t.start()

def exec_zoning():
    write_config()

    gdal_polygonize = None
    for d in os.environ['PATH'].split(os.pathsep):
        if (Path(d) / 'gdal_polygonize.py').exists():
            gdal_polygonize = str((Path(d) / 'gdal_polygonize.py'))
            break
    
    if gdal_polygonize == None:
        print('gdal_polygonize.py command not found, required!')
        gl.window.statusbar.showMessage('gdal binaries not found, required!')
        return
    
    scriptpath = os.path.dirname(os.path.realpath(__file__))
    scriptpath = Path(scriptpath)
    outdir = Path(gl.config.get('outdir'))
    csvs = gl.config.get('predictandList')        
    startyr = int(gl.config.get('startyr'))
    endyr = int(gl.config.get('endyr'))
    missing = float(gl.config.get('predictandMissingValue'))
    ExplainedVariance = float(gl.config.get('ExplainedVariance'))
    gridsize = float(gl.config.get('gridsize'))
    rotation = gl.config.get('rotation').get('types')[gl.config.get('rotation').get('indx')]
    period = gl.config.get('period').get('season')[int(gl.config.get('period').get('indx'))]
    composition = gl.config.get('composition')
    interpolation = gl.config.get('interpolation')
    base_vector = gl.config.get('base_vector').get('file')
    nzones = gl.config.get('zones')
    if nzones.isnumeric(): 
        nzones = int(nzones)
    else:
        nzones = None
    vname, _ = os.path.splitext(os.path.basename(base_vector))
    vname = fixname(vname)
    proj='GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],' \
          'AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433],' \
          'AUTHORITY["EPSG","4326"]]'
    
    # check if output directory exists
    if not os.path.exists(outdir):
        print("output directory does not exist")
        gl.window.statusbar.showMessage("output directory does not exist")
        sys.exit()
    
    # check if input GeoJSON exists
    if not os.path.exists(base_vector):
        print("input GeoJSON file does not exist")
        gl.window.statusbar.showMessage("input GeoJSON file does not exist")
        sys.exit()
    
    # create output directory
    period_text = period + '_' + str(startyr)  + '_' + str(endyr) 
    zonepath = (outdir / vname).joinpath(period_text)
    os.makedirs(zonepath, exist_ok=True)
    
    # outputs 
    dst_layername = (period_text + "_zones").lower()
    dst_zones = str(zonepath / (dst_layername + ".geojson"))
    zonejson = str(zonepath / (vname + "_" + period_text.lower() + "_zones.geojson"))
    zonejson_clean = str(zonepath / (dst_layername + "_clean.geojson"))
    zonejson_smooth = str(zonepath / (dst_layername + "_smooth.geojson"))
    zonenc = str(zonepath / "izones.nc")
    datacsv = str(zonepath / "data.csv")
    faw = str(zonepath / "components.csv")
    far = str(zonepath / ("components_" + rotation + ".csv"))
    farpng = str(zonepath / ("components_" + rotation + ".png"))
    evpng = str(zonepath / ("explained_variance.png"))
    izonespng = str(zonepath / ("izones.png"))
    with open(str(zonepath / "zoning.json"), 'w') as fp:
        json.dump(gl.config, fp, indent=4)
    
    # clean outputs
    if os.path.exists(zonejson):
        os.remove(zonejson)
        
    if os.path.exists(dst_zones):
        os.remove(dst_zones)
    
    if os.path.exists(zonenc):
        os.remove(zonenc)
    
    if os.path.exists(faw):
        os.remove(faw)
    
    if os.path.exists(far):
        os.remove(far)
        
        
    #######
    start_time = time.time()
    print("Start time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    gl.window.statusbar.showMessage("Start time: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    input_data = concat_csvs(csvs, missing)
    stations = list(input_data['ID'].unique())
    nstations_prev = len(stations)
    trainyears = list(range(startyr,endyr+1))
    data = pd.DataFrame(columns=stations)
    data['Year'] = trainyears
    data.set_index(['Year'], inplace=True)    
    
    for station in stations:
        station_data = stationdata(input_data, station, period)
        for year in trainyears:
            if composition == "Sum":
                data.loc[[year], station] =ff. season_cumulation(station_data, year, period)
            else:
                data.loc[[year], station] = ff.season_average(station_data, year, period)
    
    # remove gaps
    data.dropna(axis=1, inplace=True)
    # data.to_csv(datacsv)
    # data = pd.read_csv(datacsv, index_col=0)
    stations = list(data.columns)
    nstations = len(stations)
    if nstations_prev != nstations:
        print(str(nstations_prev-nstations)+' stations removed due to gaps')   
        gl.window.statusbar.showMessage(str(nstations_prev-nstations)+' stations removed due to gaps')
    if nstations <= 1:
        print(str(nstations)+' stations without gaps, not enough for zoning.')   
        gl.window.statusbar.showMessage(str(nstations)+' stations without gaps, not enough for zoning.')
        return
    lats, lons = [], []
    for n in range(nstations):
        station_data_all = input_data.loc[input_data['ID'] == stations[n]]
        lats.append(station_data_all['Lat'].unique()[0])
        lons.append(station_data_all['Lon'].unique()[0])
    print('number of stations '+str(nstations))
    gl.window.statusbar.showMessage('number of stations '+str(nstations))
    data.to_csv(datacsv)
    
    data.columns = ['s'+str(x) for x in range(len(stations))]
    X = StandardScaler().fit_transform(data)
    fa = PCA()
    fa.fit(X)
    
    print('explained variance')
    gl.window.statusbar.showMessage('computing explained variance')
    explained_variance = fa.explained_variance_.T
    ncomps = len(explained_variance)
    total_exp_var = explained_variance.sum()
    explained_variance_p, y = [], 0
    for x in explained_variance:
        y = y + x
        explained_variance_p.append(round(100. * (y / total_exp_var),1))
       
    # scree plot
    fig, axs = plt.subplots(2, figsize=(12,8), sharex=True)
    fig.suptitle('Explained Variance (EV)')
    axs[0].plot(list(range(1,ncomps+1)),explained_variance,'b*')
    axs[0].set_ylabel('EV per component');
    axs[1].plot(list(range(1,ncomps+1)),explained_variance_p, label="Cum. EV (%)")
    axs[1].plot(list(range(1,ncomps+1)),[ExplainedVariance] * ncomps,'r--', label="Min. PEV")
    axs[1].set_xlabel('Number of components')
    axs[1].set_ylabel('EV (%)')
    axs[1].legend()
    axs[1].set_xticks(list(range(1,len(explained_variance)+1)))
    plt.savefig(evpng)
    plt.close(fig)
    
    n_comps = (np.array(explained_variance_p) <= ExplainedVariance).sum() + 1
    colnames = ['cmp'+str(x) for x in list(range(1,n_comps+1))]
    
    fa = FactorAnalysis()
    fa.set_params(n_components=n_comps)
    fa.fit(X)
    components = fa.components_.T
    df1 = pd.DataFrame(components,columns = colnames)
    df1['station'] = stations
    df1['Lat'] = lats
    df1['Lon'] = lons
    df1.to_csv(faw)
    
    fa = FactorAnalysis(rotation=rotation)
    fa.set_params(n_components=n_comps)
    fa.fit(X)
    components = fa.components_.T
    df2 = pd.DataFrame(components,columns = colnames)
    df2['station'] = stations
    df2['Lat'] = lats
    df2['Lon'] = lons
    df2.to_csv(far)
    
    # open base map to get bounds
    with open(base_vector, "r") as read_file:
        base_map = geojson.load(read_file)
    
    mx, xx, my, yy = [], [], [], []
    for feature in base_map['features']:
        poly = feature['geometry']
        polygon = shape(feature['geometry'])
        minx, miny, maxx, maxy = polygon.bounds
        mx.append(minx)
        xx.append(maxx)
        my.append(miny)
        yy.append(maxy)
        
    minx = int(np.min(mx)-1) * 1.0
    maxx = round(np.max(xx)+0.5,0)
    miny = int(np.min(my)-1) * 1.0
    maxy = round(np.max(yy)+0.5,0)
    
    # target grid to interpolate to
    if minx > int(min(lons)-1) * 1.0: minx = int(min(lons)-1) * 1.0
    if maxx < round(max(lons)+0.5,0): maxx = round(max(lons)+0.5,0)
    if miny > int(min(lats)-1) * 1.0: miny = int(min(lats)-1) * 1.0
    if maxy < round(max(lats)+0.5,0): maxy = round(max(lats)+0.5,0)

    x = np.array(lons)
    y = np.array(lats)
    xs = np.arange(minx,maxx+gridsize,gridsize)
    ys = np.arange(miny,maxy+gridsize,gridsize)
    nx = len(xs)
    ny = len(ys)
    print("grid bounds (xmin, ymin, xmax, ymax): " + str((minx, miny, maxx, maxy)))
    print("number of grid points: " + str(nx * ny))
    print("minimum memory required: " + sizeof_fmt(nx * ny * 64 * 6))
    if (nx * ny * 64 * 6) > 1073741824:
        status = "images too big (>1 GiB memory required). consider increasing the gridsize value"
        print(status)
        gl.window.statusbar.showMessage(status)
        
    else:
        gl.window.statusbar.showMessage("creating grids, minimum memory required: " + sizeof_fmt(nx * ny * 64) + " x 3")  
        xi,yi = np.meshgrid(xs,ys)
        xi, yi = xi.flatten(), yi.flatten()
        comps = []
        
        c = 3
        r = int(len(colnames)/3)
        if (len(colnames)%3 != 0) or (r == 0): r+=1
        
        
        # generating and plotting interpolated components maps
        print('generate and plot the interpolated components maps')
        gl.window.statusbar.showMessage('generate and plot the interpolated components maps')
        fig, axs = plt.subplots(r, c, figsize=(30, 6*r), facecolor='w', edgecolor='k')
        fig.tight_layout()
        axs = axs.ravel()
         
        for i in range(len(colnames)):
            col = colnames[i]
            z = np.ravel(df2[col].values)
            # interpolate
            if interpolation == 'idw':
                zi = simple_idw(x,y,z,xi,yi)
            else:
                zi = linear_rbf(x,y,z,xi,yi)
            zi = zi.reshape((ny, nx))
            comps.append(list(zi))
            # plot
            axs[i].imshow(zi, extent=(minx, maxx, maxy, miny))
            for feature in base_map['features']:
                poly = feature['geometry']
                axs[i].add_patch(PolygonPatch(poly, fc=None, fill=False, ec='#8f8f8f', alpha=1., zorder=2))
            axs[i].plot(x,y,'k.')
            axs[i].title.set_text(col)
            axs[i].title.set_fontsize(10)
            axs[i].invert_yaxis()
            axs[i].set_xlim([minx, maxx])
            axs[i].set_ylim([miny, maxy])
        plt.savefig(farpng,dpi=100)
        plt.close(fig)
        
        comps = np.array(comps)    
        #comps[np.isnan(comps)] = 0
        comps = comps.reshape(len(colnames),len(xs)*len(ys))
        
        if nzones is None:
            # compute optimal number of zones
            print('compute optimal number of zones')
            gl.window.statusbar.showMessage('computing optimal number of zones')
            wcss = []
            distances = []
            maxk = 16
            klist = list(range(1, maxk+1))
            for d in klist:
                kmeans = cluster.KMeans(n_clusters = d, random_state=42, n_init=5).fit(comps.T)
                wcss.append(kmeans.inertia_)
            
            # create linear coefficients for line joining first and last kmeans inertia
            a = (float(wcss[-1] - wcss[0]))/(klist[-1] - klist[0])
            b = -1
            c = wcss[0] - (klist[0] * a)
            
            # calculate perpendicular distances from each kmeans to line
            for e in klist:
                distances.append((e, shortest_distance(e, wcss[e-1], a, b, c)))
            
            # locate albow and get optimal number of zones
            distances.sort(key=lambda g: g[1])
            n_clusters = distances[-1][0]
        else:
            n_clusters = nzones
        
        print('clustering of components')
        gl.window.statusbar.showMessage('clustering components')
        db = cluster.KMeans(n_clusters = n_clusters, random_state=42, n_init=5).fit(comps.T)
        dblabels = np.array(db.labels_) + 1
        zi = dblabels.reshape(len(ys), len(xs))
        print("number of zones ", len(np.unique(dblabels)))
        gl.window.statusbar.showMessage("number of zones " + str(len(np.unique(dblabels))))
        # plot
        DPI = 150
        W = 750
        H = int(W * ny / nx)
        fig = plt.figure(figsize=(W / float(DPI), H / float(DPI)), frameon=True, dpi=DPI)
        ax = fig.gca()
        ax.imshow(zi, extent=(minx, maxx, maxy, miny))
        for feature in base_map['features']:
            poly = feature['geometry']
            ax.add_patch(PolygonPatch(poly, fc=None, fill=False, ec='#8f8f8f', alpha=1., zorder=2))
        ax.plot(x,y,'k.')
        ax.title.set_text(period_text + ' Zones')
        ax.title.set_fontsize(10)
        ax.invert_yaxis()
        ax.set_xlim([minx, maxx])
        ax.set_ylim([miny, maxy])
        plt.savefig(izonespng,dpi=DPI)
        plt.close(fig)
        
        # elbow plot
        if nzones is None:      
            print("elbow plot")
            if os.path.exists(zonepath / 'elbowplot.png'):
                os.remove(zonepath / 'elbowplot.png')
            plt.figure()
            plt.plot(klist, wcss, 'bx-')
            plt.plot(n_clusters, wcss[klist.index(n_clusters)], 'r.')
            plt.xlabel('Values of K')
            plt.xticks(klist)
            plt.ylabel('Distortion')
            plt.title('The Elbow Method using Distortion')
            plt.savefig(zonepath / 'elbowplot.png',dpi=100)
            plt.close(fig)
        
        # create a raster for the zones
        print('creating zone NetCDF')
        gl.window.statusbar.showMessage('creating zone NetCDF')
        create_nc(zonenc, zi, ys, xs)

        # polygonize the raster
        print('polygonizing the zone raster into a geojson')
        gl.window.statusbar.showMessage('polygonizing the zone raster into a geojson')
        retval = os.system('python "' + gdal_polygonize + '" -b 1 -f GeoJSON "' + zonenc + '" "' + dst_zones + '" izones Zone')
        if retval != 0:
            print('failed to polygonize the zone raster into a geojson')
            gl.window.statusbar.showMessage('failed to polygonize the zone raster into a geojson')
            return
        
        # clean the vector zone map
        print('cleaning the vector zone map')
        gl.window.statusbar.showMessage('cleaning the vector zone map')
        with open(dst_zones, "r") as read_file:
            base_map = geojson.load(read_file)
        
        extents = []
        for feature in base_map['features']:
            extents.append(shape(feature['geometry']).bounds)
        smallerpolygons = []
        for i in range(len(extents)):
            for j in range(len(extents)):
                if i == j: continue
                zonei = base_map['features'][i]['properties']['Zone']
                zonej = base_map['features'][j]['properties']['Zone']
                if (zonei == zonej) and (bigger(extents[i], extents[j])):
                    smallerpolygons.append(j)
        
        containedpolygons = []
        for i in range(len(extents)):
            for j in range(len(extents)):
                if i == j: continue
                coordsi = base_map['features'][i]['geometry']['coordinates'][0]
                coordsj = base_map['features'][j]['geometry']['coordinates'][0]
                polyi = Polygon([(x,y) for x,y in coordsi])
                polyj = Polygon([(x,y) for x,y in coordsj])
                if polyi.contains(polyj):
                    containedpolygons.append(j)
                    
        containedpolygons = np.unique(containedpolygons)
        smallerpolygons = np.unique(smallerpolygons)
        smallerpolygons = list(set(smallerpolygons).intersection(containedpolygons))
        print('will clean out tiny polygons ', smallerpolygons)
        gl.window.statusbar.showMessage('removing tiny polygons ' + str(smallerpolygons))
        
        zones = []
        coords = []
        # remove tiny polygons, reorder the zones and close holes
        for n in range(len(base_map['features'])):
            if n not in smallerpolygons:
                feature = base_map['features'][n]
                coords.append([feature['geometry']['coordinates'][0]])
                zones.append(feature['properties']['Zone'])
        
        uniquezones = np.unique(zones)
        featurecoords = [[] for x in range(len(uniquezones))]
        
        for n in range(len(uniquezones)):
            for m in range(len(zones)):
                if zones[m] == uniquezones[n]:
                    featurecoords[n].append(coords[m])
        
        features = []
        for n in range(len(uniquezones)):
            features.append(
                { 
                    "type": "Feature", 
                    "properties": 
                        { 
                            "Zone": int(uniquezones[n])
                                }, 
                            "geometry": 
                                { 
                                    "type": "MultiPolygon", 
                                    "coordinates": featurecoords[n]
                                    }
                                })
        
        new_map = geojson.feature.FeatureCollection(features)
        new_map["name"] = "Zones"

        with open(zonejson_clean, 'w') as fp:
            geojson.dump(new_map, fp, sort_keys=False, ensure_ascii=False)
        
        # perform smoothing if activated
        if gl.config.get('smoothing', 0):
            # smooth the output vector
            print('smoothing the output vector')
            smooth_size = gridsize * 2.0
            smooth(zonejson_clean,zonejson_smooth,dst_layername,smooth_size)
            # open base map for clipping
            print('opening smoothed map for clipping')
            zonejson_clean = zonejson_smooth
        
        # clip intermediate zone layer with base map
        print('clip intermediate zone layer with base map')
        retval = os.system('ogr2ogr -f GeoJSON -clipsrc "' + base_vector + '" "' + zonejson + '" "' + zonejson_clean + '"')
        if retval != 0:
            print('failed to clip intermediate zone layer with base map')
            gl.window.statusbar.showMessage('failed to clip intermediate zone layer with base map')
            return
        
        # close data sources
        print('close the data sources')
        
        inDataSource = None
        inClipSource = None
        outDataSource = None
        
        
        print("End time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print('Done in ' + str(convert(time.time() - start_time)))
        gl.window.statusbar.showMessage('Done in ' + str(convert(time.time() - start_time)))
        


def main():
    gl.app = QtWidgets.QApplication(sys.argv)
    gl.window = MyApp()
    gl.window.show()
    
    try:
        with open(settingsfile, "r") as read_file:
            gl.config = json.load(read_file)
    except:
        gl.config = {}
        gl.config['outdir'] = ''
        gl.config['base_vector'] = {"file": '', "ID": 0, "attr": []}
        gl.config['interpolation'] = 'idw'
        gl.config['ExplainedVariance'] = 70
        gl.config['gridsize'] = 0.05
        gl.config['rotation'] = {"types": ["varimax", "quartimax"], "indx": 0}
        gl.config['inputFormat'] = "CSV"
        gl.config['predictandMissingValue'] = -9999
        gl.config['composition'] = "Sum"
        gl.config['period'] = {"season": ['JFM', 'FMA', 'MAM', 'AMJ', 
                                       'MJJ', 'JJA', 'JAS', 'ASO', 
                                       'SON', 'OND', 'NDJ', 'DJF'], "indx": 9}
        gl.config['startyr'] = 1981
        gl.config['endyr'] = 2010
        gl.config['zones'] = ''
        gl.config['smoothing'] = 0
        gl.config['predictandList'] = []
        gl.config['predictandattr'] = {"params": ['pre'], "indx": 0}
        gl.window.statusbar.showMessage("Default settings loaded.")

    # --- Load values into the UI ---
    gl.window.outdirlabel.setText(gl.config.get('outdir'))
    gl.window.inputlayerlabel.setText(os.path.basename(gl.config.get('base_vector',{}).get('file')))
    if gl.config.get('interpolation') == 'idw':
        gl.window.radioButtonIDW.setChecked(True)
    else:
        gl.window.radioButtonLinear.setChecked(True)
    gl.window.PEV.setText(str(gl.config.get('ExplainedVariance', 70)))
    gl.window.gridsizelineEdit.setText(str(gl.config.get('gridsize', 0.05)))
    for rotationalg in gl.config.get('rotation').get('types'):
        gl.window.rotationDcombobox.addItem(rotationalg)
    gl.window.rotationDcombobox.setCurrentIndex(int(gl.config.get('rotation').get('indx')))
    if gl.config.get('inputFormat') == "CSV":
        gl.window.CSVRadio.setChecked(True)
    else:
        gl.window.NetCDFRadio.setChecked(True)
        # gl.window.predictandparamcombobox.addItem(gl.config.get('predictandattr', ''))
    gl.window.missingvalueslineEdit.setText(str(gl.config.get('predictandMissingValue', -9999)))  
    if gl.config.get('composition') == "Sum":
        gl.window.cumRadio.setChecked(True)
    if gl.config.get('composition') == "Average":
        gl.window.avgRadio.setChecked(True)
    for periodx in gl.config.get('period').get('season'):
        gl.window.periodComboBox.addItem(periodx)
    gl.window.periodComboBox.setCurrentIndex(int(gl.config.get('period').get('indx')))
    gl.window.startyearLineEdit.setText(str(gl.config.get('startyr')))
    gl.window.endyearLineEdit.setText(str(gl.config.get('endyr')))
    gl.window.ZonesLineEdit.setText(str(gl.config.get('zones', '')))
    for fileName in gl.config.get('predictandList'):
        gl.window.predictandlistWidget.addItem(os.path.basename(fileName))
    

    ## Signals
    gl.window.outputButton.clicked.connect(getOutDir)
    gl.window.InputLayerButton.clicked.connect(addBaseVector)
    gl.window.radioButtonIDW.toggled.connect(change_interpolation)
    gl.window.radioButtonLinear.toggled.connect(change_interpolation)
    gl.window.CSVRadio.toggled.connect(change_format_type)
    gl.window.NetCDFRadio.toggled.connect(change_format_type)
    gl.window.cumRadio.toggled.connect(change_composition)
    gl.window.avgRadio.toggled.connect(change_composition)
    gl.window.browsepredictandButton.clicked.connect(addPredictands)
    gl.window.clearpredictandButton.clicked.connect(clearPredictands)
    gl.window.runButton.clicked.connect(launch_zoning_Thread)
    # gl.window.stopButton.clicked.connect(closeapp)
    sys.exit(gl.app.exec_())


if __name__ == "__main__":
    main()

    
