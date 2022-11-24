"""
@author: thembani
"""
import os, sys, time, threading
from dateutil.relativedelta import relativedelta
from datetime import datetime
from netCDF4 import Dataset
import pandas as pd
import numpy as np
import geojson, json
from multiprocessing import Pool, cpu_count
from functools import partial
from functions import *

from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import QThread, QObject, QDate, QTime, QDateTime, Qt
pwd = os.path.dirname(os.path.realpath('__file__'))
qtCreatorFile = "cft.ui"

# Global Variables
version = '3.1.1'
months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
seasons = ['JFM','FMA','MAM','AMJ','MJJ','JJA','JAS','ASO','SON','OND','NDJ','DJF']
month_start_season = {'JFM': 'Jan', 'FMA': 'Feb', 'MAM': 'Mar', 'AMJ': 'Apr', 'MJJ': 'May', 'JJA': 'Jun', 'JAS': 'Jul',
                     'ASO': 'Aug', 'SON': 'Sep', 'OND': 'Oct', 'NDJ': 'Nov', 'DJF': 'Dec'}
csvheader = 'Year,Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec'
fcstyear = QDate.currentDate().year()
settingsfile = 'settings.json'
predictordict = {}
predictanddict = {}
predictanddict['stations'] = []
predictanddict['data'] = None
fcstPeriod = None
cpus = int(round(0.9 * cpu_count() - 0.5, 0))
if cpus == 0: cpus = 1

#
def concat_csvs(csvs, missing):
    dfs_files = []
    for file in csvs:
        dfs_files.append(pd.read_csv(file, encoding = 'ISO-8859-9'))
    dfs_files = pd.concat((dfs_files), axis=0)
    dfs_files = dfs_files.replace(str(missing), np.nan)
    dfs_files = dfs_files.dropna(how='all')
    dfs_files['ID'] = dfs_files['ID'].apply(rename)
    return dfs_files

def get_parameter(list):
    keys = []
    for key in list:
        keys.append(key)
    ref_keys = ['Y', 'X', 'T','zlev']
    for x in reversed(range(len(keys))):
        if keys[x] not in ref_keys:
            return keys[x]
    return None

#
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)

class MyApp(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MyApp()
    window.show()

    try:
        with open(settingsfile, "r") as read_file:
            config = json.load(read_file)
    except:
        config = {}
        config['Version'] = version
        config['outDir'] = ''
        config['predictorList'] = []
        config['predictandList'] = []
        config['predictandMissingValue'] = -9999
        config['predictandattr'] = 'pre'
        config['fcstPeriodStartMonth'] = 'Oct'
        config['fcstPeriodLength'] = '3month'
        config['trainStartYear'] = 1971
        config['trainEndYear'] = 2000
        config['predictorMonth'] = 'Jul'
        config['PValue'] = 0.05
        config['stepwisePvalue'] = 0.3
        config['minHSscore'] = 50
        config['PODfilter'] = 1
        config['inputFormat'] = "CSV"
        config['composition'] = "Sum"
        config['zonevector'] = {"file": "", "ID": 0, "attr": []}
        config['fcstyear'] = fcstyear
        config['algorithms'] = ['LR']
        config['basinbounds'] = {"minlat": -90, "maxlat": 90, "minlon": -180, "maxlon": 360}
        config['plots'] = {'basemap': 'data' + os.sep + 'sadc_countries.geojson', 'zonepoints': 1,
                           'fcstqml': 'styles'+os.sep+'fcstplot_new.qml', 'corrmaps': 1,
                           'corrcsvs': 1, 'regrcsvs': 1, 'fcstgraphs': 1, 'trainingraphs': 1}
        config['colors'] = {'class0': '#ffffff', 'class1': '#d2b48c', 'class2': '#fbff03', 'class3': '#0bfffb',
                            'class4': '#1601fc'}
        window.statusbar.showMessage("Default settings loaded.")

    def getOutDir():
        global config
        config['outDir'] = QtWidgets.QFileDialog.getExistingDirectory(directory='..' + os.sep)
        window.outdirlabel.setText(config.get('outDir'))

    def addPredictors():
        global config
        fileNames = QtWidgets.QFileDialog.getOpenFileNames(window,
                    'Add File(s)', '..' + os.sep, filter="NetCDF/CSV Files (*.nc* *.csv *.txt)")
        for fileName in fileNames[0]:
            config['predictorList'].append(fileName)
            window.predictorlistWidget.addItem(os.path.basename(fileName))

    def removePredictors():
        global config
        newList = []
        if len(window.predictorlistWidget.selectedItems()) == 0:
            return
        for yy in config.get('predictorList'):
            if os.path.basename(yy) != window.predictorlistWidget.selectedItems()[0].text():
                newList.append(yy)
        window.predictorlistWidget.clear()
        config['predictorList'] = newList
        for yy in newList:
            window.predictorlistWidget.addItem(os.path.basename(yy))

    def addPredictands():
        global config
        global csvheader
        config['predictandList'] = []
        window.predictandlistWidget.clear()
        window.predictandIDcombobox.clear()
        window.statusbar.showMessage("")
        if window.CSVRadio.isChecked() == True:
            config['inputFormat'] = "CSV"
            fileNames = QtWidgets.QFileDialog.getOpenFileNames(window,
                    'Add File(s)', '..' + os.sep, filter="CSV File (*.csv)")
            for filename in fileNames[0]:
                with open(filename) as f:
                    fline = f.readline().rstrip()
                if fline.count(',') < 4:
                    window.statusbar.showMessage(
                        "Format error in "+os.path.basename(filename)+", check if comma delimited")
                    continue
                if csvheader not in fline:
                    window.statusbar.showMessage(
                        "Format error, one or more column headers incorrect in " + os.path.basename(filename))
                    continue
                if 'ID' not in fline:
                    window.statusbar.showMessage(
                        "Format error, station name column header should be labelled as ID in " + os.path.basename(filename))
                    continue
                config['predictandList'].append(filename)
                window.predictandlistWidget.addItem(os.path.basename(filename))
        elif window.NetCDFRadio.isChecked() == True:
            config['inputFormat'] = "NetCDF"
            try:
                fileName = QtWidgets.QFileDialog.getOpenFileNames(window,
                    'Add File', '..' + os.sep, filter="NetCDF File (*.nc*)")[0]
                predictand = Dataset(fileName[0])
                for key in predictand.variables.keys():
                    if key not in ['Y', 'X', 'Z', 'T', 'zlev', 'time', 'lon', 'lat']:
                        window.predictandIDcombobox.addItem(key)
                config['predictandList'].append(fileName[0])
                window.predictandlistWidget.addItem(os.path.basename(fileName[0]))
            except:
                window.statusbar.showMessage(
                    "Could not read predictand file, check if it is a valid NetCDF")
                return

    def clearPredictands():
        global config
        config['predictandList'] = []
        window.predictandlistWidget.clear()
        window.predictandIDcombobox.clear()

    def change_period_list():
        global config
        periodlist = []
        window.periodComboBox.clear()
        if window.period1Radio.isChecked() == True:
            config['fcstPeriodLength'] = '3month'
            periodlist = seasons
        if window.period2Radio.isChecked() == True:
            config['fcstPeriodLength'] = '1month'
            periodlist = months
        for xx in range(len(periodlist)):
            window.periodComboBox.addItem(periodlist[xx])

    def change_format_type():
        global config
        window.predictandlistWidget.clear()
        window.predictandIDcombobox.clear()
        config['inputFormat'] = ""

    def populate_period_list(period, startmonth):
        periodlist = []
        index = months.index(startmonth)
        window.periodComboBox.clear()
        if period == '3month':
            window.period1Radio.setChecked(True)
            periodlist = seasons
        else:
            window.period2Radio.setChecked(True)
            periodlist = months
        for xx in range(len(periodlist)):
            window.periodComboBox.addItem(periodlist[xx])
        window.periodComboBox.setCurrentIndex(index)


    def addZoneVector():
        global config
        window.zoneIDcomboBox.clear()
        window.zonevectorlabel.setText('')
        config['zonevector'] = {"file": None, "ID": 0, "attr": []}
        zonefieldsx = []
        window.zoneIDcomboBox.setDuplicatesEnabled(False)
        fileName = QtWidgets.QFileDialog.getOpenFileName(window,
                  'Add File', '..' + os.sep, filter="GeoJson File (*.geojson)")
        config['zonevector']['file'] = fileName[0]
        if os.path.isfile(config.get('zonevector',{}).get('file')):
            with open(config.get('zonevector',{}).get('file')) as f:
                zonejson = geojson.load(f)
            for zonekey in zonejson['features']:
                for zonetype in zonekey.properties:
                    zonefieldsx.append(zonetype)
            zonefields = []
            [zonefields.append(x) for x in zonefieldsx if x not in zonefields]
            for xx in zonefields:
                window.zoneIDcomboBox.addItem(str(xx))
                config['zonevector']['attr'].append(str(xx))
            window.zonevectorlabel.setText(os.path.basename(config.get('zonevector',{}).get('file')))

    def setInputFormat():
        global config
        if window.CSVRadio.isChecked():
            config['inputFormat'] = "CSV"
        else:
            config['inputFormat'] = "NetCDF"

    for xx in range(len(months)):
        window.predictMonthComboBox.addItem(months[xx])

    def launch_forecast_Thread():
        t = threading.Thread(target=forecast)
        t.start()

    def forecast():
        global settingsfile
        global config
        global predictordict
        global predictanddict
        global fcstPeriod
        global cpus
        global pwd
        window.statusbar.showMessage('preparing inputs')
        start_time = time.time()
        config['algorithms'] = []
        if window.LRcheckBox.isChecked():
            config['algorithms'].append('LR')
        if window.MLPcheckBox.isChecked():
            config['algorithms'].append('MLP')
        if len(config.get('algorithms')) == 0:
            window.statusbar.showMessage("No algorithm set!")
            return None
        if window.cumRadio.isChecked():
            config['composition'] = "Sum"
        else:
            config['composition'] = "Average"
        if window.period1Radio.isChecked():
            config['fcstPeriodLength'] = '3month'
            config['fcstPeriodStartMonth'] = month_start_season.get(str(window.periodComboBox.currentText()))
        else:
            config['fcstPeriodLength'] = '1month'
            config['fcstPeriodStartMonth'] = window.periodComboBox.currentText()
        config['predictorMonth'] = window.predictMonthComboBox.currentText()
        config['stepwisePvalue'] = float(window.swpvaluelineEdit.text())
        config['PValue'] = float(window.pvaluelineEdit.text())
        config['fcstyear'] = int(window.fcstyearlineEdit.text())
        config['zonevector']['ID'] = window.zoneIDcomboBox.currentIndex()
        config['basinbounds']['minlat'] = float(str(window.minlatLineEdit.text()).strip() or -90)
        config['basinbounds']['maxlat'] = float(str(window.maxlatLineEdit.text()).strip() or 90)
        config['basinbounds']['minlon'] = float(str(window.minlonLineEdit.text()).strip() or -180)
        config['basinbounds']['maxlon'] = float(str(window.maxlonLineEdit.text()).strip() or 360)
        config['trainStartYear'] = int(window.startyearLineEdit.text())
        config['trainEndYear'] = int(window.endyearLineEdit.text())
        config['predictandattr'] = window.predictandIDcombobox.currentText()
        config['minHSscore'] = int(window.minHSLineEdit.text())

        # check if output directory exists
        if not os.path.exists(config.get('outDir')):
            window.statusbar.showMessage("Output Directory not set!")
            return None

        # Write configuration to settings file
        import json
        with open(settingsfile, 'w') as fp:
            json.dump(config, fp, indent=4)

        print('\nCFT', config.get('Version'))
        print('\nForecast:', config.get('fcstyear'), window.periodComboBox.currentText())
        print('Configuration:', os.path.basename(settingsfile))
        print('Output directory:', config.get('outDir'))
        print('Predictand: ')
        for predict in config.get('predictandList'):
            print('\t -', os.path.basename(predict))
        print('Predictand attribute:', config.get('predictandattr'))
        print('Predictor: ')
        for predict in config.get('predictorList'):
            print('\t -', os.path.basename(predict))
        print("Predictor month:", config.get('predictorMonth'))
        print('Algorithm: ')
        for alg in config.get('algorithms'):
            print('\t -', alg)
        print("Training period:", config.get('trainStartYear'), '-', config.get('trainEndYear'))
        print("number of cores to be used:", cpus)
        print("Start time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # prepare input data
        nstations = 0
        if config.get('inputFormat') == 'CSV':
            if len(config.get('predictandList')) != 0:
                missing = config.get('predictandMissingValue')
                if len(str(missing)) == 0: missing = -9999
                input_data = concat_csvs(config.get('predictandList'), missing)
                predictandstaryr = int(np.min(input_data['Year']))
                if predictandstaryr > int(config.get('trainStartYear')):
                    status = "Predictand data starts in " + str(predictandstaryr) + ", does not cover training period"
                    print(status)
                    window.statusbar.showMessage(status)
                    return
                predictanddict['data'] = input_data
                stations = list(input_data['ID'].unique())
                predictanddict['stations'] = stations
                nstations = len(stations)
                predictanddict['lats'], predictanddict['lons'] = [], []
                for n in range(nstations):
                    station_data_all = input_data.loc[input_data['ID'] == stations[n]]
                    predictanddict['lats'].append(station_data_all['Lat'].unique()[0])
                    predictanddict['lons'].append(station_data_all['Lon'].unique()[0])
                processes = stations
                print('stations:',nstations,'predictors:',len(config.get('predictorList')),'algorithms:',
                      config.get('algorithms'))
            else:
                input_data = None
        elif config.get('inputFormat') == 'NetCDF':
            if len(config.get('predictandList')) != 0:
                predictand_data = netcdf_data(config.get('predictandList')[0], param=config.get('predictandattr'))
                yrs = [int(x) for x in predictand_data.times()]
                predictandstaryr = int(str(np.min(yrs))[:4])
                if predictandstaryr > int(config.get('trainStartYear')):
                    status = "Predictand data starts in " + str(predictandstaryr) + ", does not cover training period"
                    print(status)
                    window.statusbar.showMessage(status)
                    return
                prs = list(range(len(config.get('predictorList'))))
                als = list(range(len(config.get('algorithms'))))
                rows, cols = predictand_data.shape()
                pixels = [(x, y) for x in range(rows) for y in range(cols)]
                combs = [(st, pr, al) for st in pixels for pr in prs for al in als]
                processes = combs
                print('pixels:',len(pixels),'predictors:',len(prs),'algorithms:',config.get('algorithms'),'---> chunks:'
                      , len(combs))

        predictorEndYr = int(config.get('fcstyear'))
        predictorStartYr = int(config.get('trainStartYear'))
        predictorMonth = str(window.predictMonthComboBox.currentText())
        fcstPeriod = str(window.periodComboBox.currentText())
        predictorMonthIndex = months.index(config.get('predictorMonth'))
        if config.get('fcstPeriodLength', '3month') == '3month':
            fcstPeriod = season_start_month[config.get('fcstPeriodStartMonth')]
            fcstPeriodIndex = seasons.index(fcstPeriod)
        else:
            fcstPeriod = config.get('fcstPeriodStartMonth')
            fcstPeriodIndex = months.index(fcstPeriod)

        for predictor in config.get('predictorList'):
            if os.path.isfile(predictor):
                predictorName, predictorExt = os.path.splitext(os.path.basename(predictor))
                window.statusbar.showMessage('checking ' + predictorName)
                predictorExt = predictorExt.replace('.', '')
                if predictorExt.lower() in ['nc']: 
                    try:
                        predictor_data = netcdf_data(predictor)
                    except:
                        status = 'error in reading ' + predictorName + ', check format'
                        print(status)
                        window.statusbar.showMessage(status)
                        exit()
                else:
                    try:
                        predictor_data = csv_data(predictor, predictorMonth, predictorName.replace(' ', '_'))
                    except:
                        status = 'error in reading ' + predictorName + ', check format'
                        print(status)
                        window.statusbar.showMessage(status)
                        exit()
                predmon = month_dict.get(predictorMonth.lower(), None)
                param = predictor_data.param
                timearr = predictor_data.times()
                sst = predictor_data.tslice()
                rows, cols = predictor_data.shape()
                year_arr, mon_arr = [], []
                for x in timearr:
                    tyear = x[:4]
                    tmonth = x[4:6]
                    if tmonth == predmon:
                        year_arr.append(int(tyear))
                        mon_arr.append(x)

                if len(year_arr) == 0:
                    status = "Predictor (" + predictorName + ") does not contain any data for " + predictorMonth
                    print(status)
                    continue

                if predictorMonthIndex >= fcstPeriodIndex:
                    predictorStartYr = int(config.get('trainStartYear')) - 1
                    predictorEndYr = int(config.get('fcstyear')) - 1

                if int(config.get('fcstyear')) > max(year_arr):
                    predictorStartYr = config.get('trainStartYear') - 1
                    predictorEndYr = int(config.get('fcstyear')) - 1
                    if  int(config.get('fcstyear')) - max(year_arr) > 1:
                        status = "Predictor ("+param+") for " + predictorMonth + " goes up to " + str(year_arr[-1]) + \
                            ", cannot be used to forecast " + str(config.get('fcstyear')) + ' ' + fcstPeriod
                        print(status)
                        window.statusbar.showMessage(status)
                        continue
                    if fcstPeriodIndex >= predictorMonthIndex:
                        status = "Predictor ("+param+") for " + predictorMonth + " goes up to " + str(year_arr[-1]) + \
                            ", cannot be used to forecast " + str(config.get('fcstyear')) + ' ' + fcstPeriod
                        print(status)
                        window.statusbar.showMessage(status)
                        continue

                if int(config.get('fcstyear')) <= int(config.get('trainEndYear')):
                    status = "Cannot forecast " + str(config.get('fcstyear')) + " as it is not beyond training period"
                    print(status)
                    window.statusbar.showMessage(status)
                    continue

                if predictorStartYr < year_arr[0]:
                    status = "Predictor ("+param+") data starts in " + str(year_arr[0]) + \
                        ", predictor require to start in " + str(predictorStartYr)
                    print(status)
                    window.statusbar.showMessage(status)
                    continue

                status = 'predictor data to be used: ' + str(predictorStartYr) + predictorMonth + ' to ' + \
                         str(predictorEndYr) + predictorMonth
                print(status)
                predictor_years = list(range(predictorStartYr, predictorEndYr + 1))
                if predictor_data.shape() == (0, 0):
                    sst_arr = np.zeros((len(predictor_years))) * np.nan
                else:
                    sst_arr = np.zeros((len(predictor_years), rows, cols)) * np.nan
                for y in range(len(predictor_years)):
                    year = predictor_years[y]
                    indxyear = year_arr.index(year)
                    vtimearr = mon_arr[indxyear]
                    indxtimearr = timearr.index(vtimearr)
                    sst_arr[y] = np.array(sst[indxtimearr])

                predictordict[predictorName] = {}
                predictordict[predictorName]['lats'] = predictor_data.lats
                predictordict[predictorName]['lons'] = predictor_data.lons
                predictordict[predictorName]['param'] = param
                predictordict[predictorName]['predictorMonth'] = predictorMonth
                predictordict[predictorName]['data'] = sst_arr
                predictordict[predictorName]['predictorStartYr'] = predictorStartYr
                predictordict[predictorName]['predictorEndYr'] = predictorEndYr
                sst_arr, sst = None, None

        # create output directory
        outdir = config.get('outDir') + os.sep + 'Forecast_' + str(config.get('fcstyear')) + \
                 '_' + fcstPeriod + os.sep
        os.makedirs(outdir, exist_ok=True)

        # split inputs into different cores and run the processing functions
        print("\nProcessing...")
        p = Pool(cpus)
        if config.get('inputFormat') == 'CSV':
            func = partial(forecast_station, config, predictordict, predictanddict, fcstPeriod, outdir)
        elif config.get('inputFormat') == 'NetCDF':
            func = partial(nc_unit_split, config, predictordict, fcstPeriod)

        rs = p.imap_unordered(func, processes)
        p.close()
        prevcompleted = 0
        while (True):
            completed = rs._index
            if completed != prevcompleted:
                print("Completed " + str(completed) + " of " + str(len(processes)))
                prevcompleted = completed
            if config.get('inputFormat') == 'CSV':
                status = "Completed processing " + str(completed) + " of " + str(len(processes)) + " stations"
            elif config.get('inputFormat') == 'NetCDF':
                status = "Completed " + str(completed) + " of " + str(len(processes)) + " processes"
            if (completed >= len(processes)): break
            window.statusbar.showMessage(status)
            time.sleep(0.3)

        outs = list(rs)
        outputs = []
        for out in outs:
            if isinstance(out, pd.DataFrame):
                if out.shape[0] > 0:
                    outputs.append(out)
        if len(outputs) == 0:
            window.statusbar.showMessage('Skill not enough to produce forecast')
            print('Skill not enough to produce forecast')
        else:
            # Write forecasts to output directory
            forecastsdf = pd.concat(outputs, ignore_index=True)
            window.statusbar.showMessage('Writing Forecast...')
            print('Writing Forecast...')
            forecastdir = outdir + os.sep + "Forecast"
            os.makedirs(forecastdir, exist_ok=True)
            fcstprefix = str(config.get('fcstyear')) + fcstPeriod + '_' + predictorMonth
            colors = config.get('colors', {})
            fcstName = str(config.get('fcstyear')) + fcstPeriod
            if config.get('inputFormat') == 'CSV':
                # write forecast by station or zone
                if len(config.get('zonevector', {}).get('file')) == 0:
                    fcstcsvout = forecastdir + os.sep + fcstprefix + '_station_members.csv'
                    forecastsdf.to_csv(fcstcsvout, header=True, index=True)
                    if int(config.get('PODfilter', 1)) == 1:
                        forecastsdf = forecastsdf[forecastsdf.apply(lambda x: good_POD(x.Prob, x['class']), axis=1)]
                    highskilldf = forecastsdf[forecastsdf.HS.ge(int(config.get('minHSscore', 50)))][['ID', 'Lat', 'Lon', 'HS', 'class']]
                    r, _ = highskilldf.shape
                    if r > 0:
                        csv = forecastdir + os.sep + fcstprefix + '_station_members_selected.csv'                   
                        forecastsdf[forecastsdf.HS.ge(int(config.get('minHSscore', 50)))].to_csv(csv, header=True, index=True)
                        stationclass = highskilldf.groupby(['ID', 'Lat', 'Lon']).apply(func=weighted_average).to_frame(name='WA')
                        stationclass[['wavg', 'class4', 'class3', 'class2', 'class1']] = pd.DataFrame(stationclass.WA.tolist(), index=stationclass.index)
                        stationclass = stationclass.drop(['WA'], axis=1)
                        stationclass['class'] = (stationclass['wavg']+0.5).astype(int)
                        stationclass = stationclass.reset_index()
                        stationclass['avgHS'] = stationclass.apply(lambda x: get_mean_HS(highskilldf, x.ID, 'ID'), axis=1)
                        stationclassout = forecastdir + os.sep + fcstprefix + '_station-forecast.csv'
                        stationclass.to_csv(stationclassout, header=True, index=True)
                        fcstjsonout = forecastdir + os.sep + fcstprefix + '_station-forecast.geojson'
                        data2geojson(stationclass, fcstjsonout)
                        base_map = None
                        base_mapfile = config.get('plots', {}).get('basemap', '')
                        if not os.path.isfile(base_mapfile):
                            base_mapfile = repr(config.get('plots', {}).get('basemap'))
                        if os.path.isfile(base_mapfile):
                            with open(base_mapfile, "r") as read_file:
                                base_map = geojson.load(read_file)
                        station_forecast_png(fcstprefix, stationclass, base_map, colors, forecastdir, fcstName)
                        window.statusbar.showMessage('Done in '+str(convert(time.time()-start_time)))
                        print('Done in '+str(convert(time.time()-start_time)))
                    else:
                        window.statusbar.showMessage('Skill not enough for station forecast')
                        print('Skill not enough for station forecast')
                else:
                    if not os.path.isfile(config.get('zonevector', {}).get('file')):
                        window.statusbar.showMessage('Error: Zone vector does not exist, will not write zone forecast')
                        print('Error: Zone vector does not exist, will not write zone forecast')
                    else:
                        with open(config.get('zonevector', {}).get('file')) as f:
                                zonejson = geojson.load(f)
                        zoneattrID = config.get('zonevector',{}).get('ID')
                        zoneattr = config.get('zonevector', {}).get('attr')[zoneattrID]
                        forecastsdf["Zone"] = np.nan
                        # --------------
                        for n in range(nstations):
                            station = predictanddict['stations'][n]
                            szone = whichzone(zonejson, predictanddict['lats'][n], predictanddict['lons'][n], zoneattr)
                            forecastsdf.loc[forecastsdf.ID == station, 'Zone'] = szone
                        fcstcsvout = forecastdir + os.sep + fcstprefix + '_zone_members.csv'
                        forecastsdf.to_csv(fcstcsvout, header=True, index=True)

                        # generate zone forecast
                        zonefcstprefix = forecastdir + os.sep + str(config.get('fcstyear')) + fcstPeriod + '_' + predictorMonth
                        if int(config.get('PODfilter', 1)) == 1:
                            forecastsdf = forecastsdf[forecastsdf.apply(lambda x: good_POD(x.Prob, x['class']), axis=1)]
                        highskilldf = forecastsdf[forecastsdf.HS.ge(int(config.get('minHSscore', 50)))][['HS', 'class', 'Zone']]
                        r, _ = highskilldf.shape
                        if r > 0:
                            csv = forecastdir + os.sep + fcstprefix + '_zone_members_selected.csv'                        
                            forecastsdf[forecastsdf.HS.ge(int(config.get('minHSscore', 50)))].to_csv(csv, header=True, index=True)
                            stationsdf = forecastsdf[forecastsdf.HS.ge(int(config.get('minHSscore', 50)))][['ID', 'Lat', 'Lon', 'HS', 'class']]
                            stationclass = stationsdf.groupby(['ID', 'Lat', 'Lon']).apply(func=weighted_average).to_frame(
                                name='WA')
                            stationclass[['wavg', 'class4', 'class3', 'class2', 'class1']] = pd.DataFrame(
                                stationclass.WA.tolist(), index=stationclass.index)
                            stationclass = stationclass.drop(['WA'], axis=1)
                            stationclass['class'] = (stationclass['wavg']+0.5).astype(int)
                            stationclass = stationclass.reset_index()
                            stationclass['avgHS'] = stationclass.apply(lambda x: get_mean_HS(stationsdf, x.ID, 'ID'), axis=1)
                            zoneclass = highskilldf.groupby('Zone').apply(func=weighted_average).to_frame(name='WA')
                            zoneclass[['wavg', 'class4', 'class3', 'class2', 'class1']] = pd.DataFrame(zoneclass.WA.tolist(), index=zoneclass.index)
                            zoneclass = zoneclass.drop(['WA'], axis=1)
                            zoneclass['class'] = (zoneclass['wavg']+0.5).astype(int)
                            zoneclass = zoneclass.reset_index()
                            zoneclass['avgHS'] = zoneclass.apply(lambda x: get_mean_HS(highskilldf, x.Zone, 'Zone'), axis=1)
                            ZoneID = config['zonevector']['attr'][config['zonevector']['ID']]
                            zonepoints = config.get('plots', {}).get('zonepoints', '0')
                            zoneclass.set_index('Zone', inplace=True)
                            write_zone_forecast(zonefcstprefix, zoneclass, zonejson, ZoneID, colors, stationclass, zonepoints,
                                                fcstName)
                            window.statusbar.showMessage('Done in '+str(convert(time.time()-start_time)))
                            print('Done in '+str(convert(time.time()-start_time)))
                        else:
                            window.statusbar.showMessage('Skill not enough for zone forecast')
                            print('Skill not enough for zone forecast')
            elif config.get('inputFormat') == 'NetCDF':
                # Write forecasts to output directory
                if int(config.get('PODfilter', 1)) == 1:
                    forecastsdf = forecastsdf[
                        forecastsdf.apply(lambda x: good_POD(x.Prob, x['class']), axis=1)]
                highskilldf = forecastsdf[forecastsdf.HS.ge(int(config.get('minHSscore', 50)))][
                    ['Point', 't1', 't2', 't3', 'fcst', 'HS', 'class']]
                r, _ = highskilldf.shape
                if r > 0:
                    stationclass = highskilldf.groupby(['Point']).apply(
                        func=weighted_average_fcst).to_frame(name='WA')
                    stationclass[['t1', 't2', 't3', 'fcst', 'HS', 'class']] = pd.DataFrame(
                        stationclass.WA.tolist(),
                        index=stationclass.index)
                    stationclass = stationclass.drop(['WA'], axis=1)
                    comments = 'predictors:'
                    for predict in config.get('predictorList'):
                        comments = comments + ' ' + os.path.basename(predict).replace(' ', '_')
                    comments = comments + ', predictand: ' + os.path.basename(
                        config.get('predictandList')[0]).replace(' ', '_')
                    comments = comments + ', algorithms:'
                    for alg in config.get('algorithms'):
                        comments = comments + ' ' + os.path.basename(alg).replace(' ', '_')
                    # write outputs to NetCDF
                    rows, cols = predictand_data.shape()
                    fclass = np.zeros(shape=predictand_data.shape())
                    HS = np.ones(shape=predictand_data.shape()) * np.nan
                    fcst = np.ones(shape=predictand_data.shape()) * np.nan
                    t3 = np.ones(shape=predictand_data.shape()) * np.nan
                    t2 = np.ones(shape=predictand_data.shape()) * np.nan
                    t1 = np.ones(shape=predictand_data.shape()) * np.nan
                    for row in range(rows):
                        for col in range(cols):
                            point = (row, col)
                            try:
                                t1[row, col], t2[row, col], t3[row, col], fcst[row, col], HS[row, col], \
                                fclass[row, col] = \
                                    np.ravel(stationclass.loc[[point]])
                            except:
                                pass
                    fplot = 100 * (fclass - 1) + HS
                    # generate NETCDF
                    outfile = fcstjsonout = forecastdir + os.sep + fcstprefix + '_forecast.nc'
                    output = Dataset(outfile, 'w', format='NETCDF4')
                    title = 'Forecast for ' + str(
                        config.get('fcstyear')) + ' ' + fcstPeriod + ' using ' + \
                                         predictorMonth + ' initial conditions'
                    output.description = title
                    output.comments = 'Created ' + datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")
                    output.source = 'SCFTv' + config.get('Version')
                    output.history = comments
                    lat = output.createDimension('lat', rows)
                    lon = output.createDimension('lon', cols)
                    T = output.createDimension('T', 1)

                    initial_date = output.createVariable('target', np.float64, ('T',))
                    latitudes = output.createVariable('lat', np.float32, ('lat',))
                    longitudes = output.createVariable('lon', np.float32, ('lon',))
                    fcstclass = output.createVariable('class', np.uint8, ('T', 'lat', 'lon'))
                    hitscore = output.createVariable('hitscore', np.uint8, ('T', 'lat', 'lon'))
                    forecast = output.createVariable('forecast', np.uint16, ('T', 'lat', 'lon'))
                    tercile3 = output.createVariable('tercile3', np.uint16, ('T', 'lat', 'lon'))
                    tercile2 = output.createVariable('tercile2', np.uint16, ('T', 'lat', 'lon'))
                    tercile1 = output.createVariable('tercile1', np.uint16, ('T', 'lat', 'lon'))
                    fcstplot = output.createVariable('fcstplot', np.uint16, ('T', 'lat', 'lon'))

                    latitudes.units = 'degree_north'
                    latitudes.axis = 'Y'
                    latitudes.long_name = 'Latitude'
                    latitudes.standard_name = 'Latitude'
                    longitudes.units = 'degree_east'
                    longitudes.axis = 'X'
                    longitudes.long_name = 'Longitude'
                    longitudes.standard_name = 'Longitude'
                    initial_date.units = 'days since ' + str(config.get('fcstyear')) + '-' + \
                                         str('{:02d}-'.format(fcstPeriodIndex + 1)) + '01 00:00:00'
                    initial_date.axis = 'T'
                    initial_date.calendar = 'standard'
                    initial_date.standard_name = 'time'
                    initial_date.long_name = 'forecast start date'

                    latitudes[:] = predictand_data.lats
                    longitudes[:] = predictand_data.lons
                    fcstclass[:] = fclass
                    hitscore[:] = HS
                    forecast[:] = fcst
                    tercile3[:] = t3
                    tercile2[:] = t2
                    tercile1[:] = t1
                    fcstplot[:] = fplot
                    fcstclass.units = '1=BN, 2=NB, 3=NA, 4=AN'
                    fcstplot.units = '100 * (fcstclass - 1) + hitscore'
                    hitscore.units = '%'
                    output.close()
                    qmlfile = config.get('plots', {}).get('fcstqml', 'styles'+os.sep+'fcstplot_new.qml')
                    outfcstpng = fcstjsonout = forecastdir + os.sep + fcstprefix + '_forecast.png'
                    base_mapfile = Path(config.get('plots', {}).get('basemap', ''))
                    plot_forecast_png(predictand_data.lats, predictand_data.lons, fplot, title, qmlfile, base_mapfile, outfcstpng)
                    window.statusbar.showMessage('Done in '+str(convert(time.time()-start_time)))
                    print('Done in ' + str(convert(time.time() - start_time)))
                else:
                    window.statusbar.showMessage('Skill not enough for zone forecast')
                    print('Skill not enough for zone forecast')
        print("\nEnd time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


    # Load values into the UI
    populate_period_list(config.get('fcstPeriodLength'), config.get('fcstPeriodStartMonth'))
    window.startyearLineEdit.setText(str(config.get('trainStartYear')))
    window.endyearLineEdit.setText(str(config.get('trainEndYear')))
    window.predictMonthComboBox.setCurrentIndex(months.index(config.get('predictorMonth','Jul')))
    if 'LR' in config.get('algorithms', []): window.LRcheckBox.setChecked(True)
    if 'MLP' in config.get('algorithms', []): window.LRcheckBox.setChecked(True)
    window.pvaluelineEdit.setText(str(config.get('PValue')))
    window.minHSLineEdit.setText(str(config.get('minHSscore')))
    window.swpvaluelineEdit.setText(str(config.get('stepwisePvalue')))
    window.missingvalueslineEdit.setText(str(config.get('predictandMissingValue')))
    window.outdirlabel.setText(config.get('outDir'))
    window.fcstyearlineEdit.setText(str(config.get('fcstyear')))
    window.zonevectorlabel.setText(config.get('zonevector',{}).get('file',''))
    for xx in config.get('zonevector', {}).get('attr',[]):
        window.zoneIDcomboBox.addItem(str(xx))
    window.zoneIDcomboBox.setCurrentIndex(config.get('zonevector', {}).get('ID',0))
    window.predictorlistWidget.clear()
    for fileName in config.get('predictorList'):
        window.predictorlistWidget.addItem(os.path.basename(fileName))
    window.predictandlistWidget.clear()
    for fileName in config.get('predictandList'):
        window.predictandlistWidget.addItem(os.path.basename(fileName))
    if config.get('inputFormat') == "CSV":
        window.CSVRadio.setChecked(True)
    else:
        window.NetCDFRadio.setChecked(True)
        window.predictandIDcombobox.addItem(config.get('predictandattr', ''))
    if config.get('composition') == "Sum":
        window.cumRadio.setChecked(True)
    if config.get('composition') == "Average":
        window.avgRadio.setChecked(True)
    if 'LR' in config.get('algorithms'):
        window.LRcheckBox.setChecked(True)
    else:
        window.LRcheckBox.setChecked(False)
    if 'MLP' in config.get('algorithms'):
        window.MLPcheckBox.setChecked(True)
    else:
        window.MLPcheckBox.setChecked(False)
    window.minlatLineEdit.setText(str(config.get("basinbounds",{}).get('minlat')))
    window.maxlatLineEdit.setText(str(config.get("basinbounds",{}).get('maxlat')))
    window.minlonLineEdit.setText(str(config.get("basinbounds",{}).get('minlon')))
    window.maxlonLineEdit.setText(str(config.get("basinbounds",{}).get('maxlon')))

    def closeapp():
        sys.exit(app.exec_())

    ## Signals
    window.outputButton.clicked.connect(getOutDir)
    window.period1Radio.toggled.connect(change_period_list)
    window.period2Radio.toggled.connect(change_period_list)
    window.CSVRadio.toggled.connect(change_format_type)
    window.NetCDFRadio.toggled.connect(change_format_type)
    window.addpredictButton.clicked.connect(addPredictors)
    window.removepredictButton.clicked.connect(removePredictors)
    window.browsepredictandButton.clicked.connect(addPredictands)
    window.clearpredictandButton.clicked.connect(clearPredictands)
    window.CSVRadio.toggled.connect(setInputFormat)
    window.ZoneButton.clicked.connect(addZoneVector)
    window.runButton.clicked.connect(launch_forecast_Thread)
    window.stopButton.clicked.connect(closeapp)
    sys.exit(app.exec_())
