#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
  This script generates verification maps:
      Inputs:
          Forecast vector file (geojson format)
          Predictand data covering the training period
      Outputs:
          Verification netCDF file

@author: thembani
"""

import os, sys, time, threading
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from netCDF4 import Dataset
import pandas as pd
import numpy as np
import geojson, json
from multiprocessing import Pool, cpu_count
from functools import partial
from functions import *

from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import QThread, QObject, QDate, QTime, QDateTime, Qt
qtCreatorFile = "verification.ui"
settingsfile = 'verification.json'

#
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)

class MyApp(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)
        
def monthindex(arr, mon):
    for x in range(len(arr)):
        if str(arr[x][:6])==mon:
            return x
    raise ValueError('month '+str(mon)+' not available') 


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MyApp()
    window.show()
    
    try:
        with open(settingsfile, "r") as read_file:
            config = json.load(read_file)
    except:
        version = '3.1.1'
        config = {}
        config['Version'] = version
        config['outDir'] = ''
        config['fcstvector'] = {"file": '', "attr": [], "ID": 0}
        config['fcstattrib'] = ''
        config['predictand'] = {"file": '', "attr": [], "ID": 0}
        config['fcstPeriodLength'] = 'season'
        config['trainStartYear'] = 1981
        config['trainEndYear'] = 2010
        config['inputFormat'] = "NetCDF"
        config['composition'] = "Sum"
        config['fcstyear'] = QDate.currentDate().year()
        config['period'] = {"season": ['JFM', 'FMA', 'MAM', 'AMJ', 
                                       'MJJ', 'JJA', 'JAS', 'ASO', 
                                       'SON', 'OND', 'NDJ', 'DJF'],
                            "month": ['Jan', 'Feb','Mar','Apr','May','Jun',
                                      'Jul','Aug','Sep','Oct','Nov','Dec'],
                            "indx": 9}
        window.statusbar.showMessage("Default settings loaded.")


    def closeapp():
        sys.exit(app.exec_())

    def addBaseVector():
        global config
        window.forecastvectorlabel.setText('')
        config['fcstvector'] = {"file": '', "ID": 0, "attr": []}
        window.forecastvectorparamcombobox.clear()
        vectorfieldsx = []
        # window.zoneIDcomboBox.setDuplicatesEnabled(False)
        fileName = QtWidgets.QFileDialog.getOpenFileName(window,
                  'Add File', '..' + os.sep, filter="GeoJson File (*.geojson)")
        config['fcstvector']['file'] = fileName[0]
        if os.path.isfile(config.get('fcstvector').get('file')):
            with open(config.get('fcstvector',{}).get('file')) as f:
                zonejson = geojson.load(f)
            for zonekey in zonejson['features']:
                for zonetype in zonekey.properties:
                    vectorfieldsx.append(zonetype)
            zonefields = []
            [zonefields.append(x) for x in vectorfieldsx if x not in zonefields]
            for x in range(len(zonefields)):
                xx = zonefields[x]
                window.forecastvectorparamcombobox.addItem(str(xx))
                config['fcstvector']['attr'].append(str(xx))
                if xx == 'fcst_class':
                    window.forecastvectorparamcombobox.setCurrentIndex(x)
            window.forecastvectorlabel.setText(os.path.basename(config.get('fcstvector',{}).get('file')))

 
    def addPredictand():
        global config
        window.predictandlabel.setText('')
        config['predictand'] = {"file": '', "ID": 0, "attr": []}
        window.climatparamcombobox.clear()
        if window.CSVRadio.isChecked() == True:
            config['inputFormat'] = "CSV"
            fileNames = QtWidgets.QFileDialog.getOpenFileNames(window,
                    'Add File(s)', '..' + os.sep, filter="CSV File (*.csv)")
        elif window.NetCDFRadio.isChecked() == True:
            config['inputFormat'] = "NetCDF"
            try:
                fileName = QtWidgets.QFileDialog.getOpenFileName(window,
                          'Add File', '..' + os.sep, filter="NetCDF File (*.nc*)")
                config['predictand']['file'] = fileName[0]
                predictand = Dataset(fileName[0])
                for key in predictand.variables.keys():
                    if key not in ['Y', 'X', 'Z', 'T', 'zlev', 'time', 'lon', 'lat']:
                        window.climatparamcombobox.addItem(key)
                        config['predictand']['attr'].append(key)
                predictand.close()
            except:
                window.statusbar.showMessage(
                    "Could not read predictand file, check if it is a valid NetCDF")
                return
        window.predictandlabel.setText(os.path.basename(config.get('predictand',{}).get('file')))   
 
    def getOutDir():
        global config
        config['outDir'] = QtWidgets.QFileDialog.getExistingDirectory(directory='..' + os.sep)
        window.outdirlabel.setText(config.get('outDir'))


    def change_format_type():
        global config
        window.predictandlabel.clear()
        window.climatparamcombobox.clear()
        if window.CSVRadio.isChecked() == True:
            config['inputFormat'] = "CSV"
        else:
            config['inputFormat'] = "NetCDF"
            
    def change_composition():
        global config
        if window.cumRadio.isChecked() == True:
            config['composition'] = "Sum"
        else: 
            config['composition'] = "Avg"
        
    def write_config():
        global settingsfile
        global config
        config['trainStartYear'] = int(window.startyearLineEdit.text())
        config['trainEndYear'] = int(window.endyearLineEdit.text())
        config['fcstyear'] = int(window.fcstyearlineEdit.text())
        config['predictand']['ID'] = config.get('predictand').get('attr').index(window.climatparamcombobox.currentText())
        config['fcstvector']['ID'] = config.get('fcstvector').get('attr').index(window.forecastvectorparamcombobox.currentText())
        config['period']['indx'] = config.get('period').get(config.get('fcstPeriodLength')).index(window.periodComboBox.currentText())

        # Write configuration to settings file
        with open(settingsfile, 'w') as fp:
            json.dump(config, fp, indent=4)
            

    def launch_verification_Thread():
        t = threading.Thread(target=exec_verification)
        t.start()
    
    def exec_verification():
        global config
        write_config()
        
        #######
        start_time = time.time()
        print("Start time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        window.statusbar.showMessage("Start time: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        fcstshp =  Path(config.get('fcstvector').get('file'))
        if not fcstshp.exists():    
            print("Forecast vector map does not exist")
            window.statusbar.showMessage("Forecast vector map does not exist")
            return
        
        if not Path(config.get('predictand').get('file')).exists():    
            print("Climatological data file does not exist")
            window.statusbar.showMessage("Climatological data file does not exist")
            return
        
        fcst_attrib = config.get('fcstvector').get('attr')[config.get('fcstvector').get('ID')]
        fcst_raster = Path(config.get('outDir')) / (fcstshp.stem + '.nc')
        verstatscsvout = Path(config.get('outDir')) / (fcstshp.stem + '_verstats.csv')
        outputnc = Path(config.get('outDir')) / (fcstshp.stem + '_verification.nc')
        
        gdal_rasterize = None
        for d in os.environ['PATH'].split(os.pathsep) + sys.path:
            if (Path(d) / 'gdal_rasterize').exists():
                gdal_rasterize = str((Path(d) / 'gdal_rasterize'))
                break
            if (Path(d) / 'gdal_rasterize.exe').exists():
                gdal_rasterize = str((Path(d) / 'gdal_rasterize.exe'))
                break
        if gdal_rasterize == None:
            print('gdal_rasterize binary not found, required!')
            
        
        param = config.get('predictand').get('attr')[config.get('predictand').get('ID')]
        predictorEndYr = int(config.get('fcstyear'))
        trainStartYr = int(config.get('trainStartYear'))
        trainStopYr = int(config.get('trainEndYear'))
        predictorMonth = config.get('period').get('month')[config.get('period').get('indx')]
        trainingYears = [yr for yr in range(trainStartYr, trainStopYr+ 1)]
        #
        trainingseasonmaps = []
        #
        predictand_data = netcdf_data(config.get('predictand').get('file'), param=param)
        rows, cols = predictand_data.shape()
        xmin = np.min(predictand_data.lons)
        ymin = np.min(predictand_data.lats)
        xmax = np.max(predictand_data.lons)
        ymax = np.max(predictand_data.lats)
        if os.path.exists(fcst_raster):  os.remove(fcst_raster)
        
        # fcstnc(predictand_data, fcst_raster)
        
        # rasterize the forecast vector
        print('rasterizing the forecast vector')
        window.statusbar.showMessage('rasterizing the forecast vector')
        print(gdal_rasterize  + ' -a_srs EPSG:4326 -ts ' + str(cols) + ' ' + str(rows) + 
                           ' -te ' + str(xmin) + ' ' + str(ymin) + ' ' + str(xmax) + ' ' + str(ymax) + 
                           ' -a ' + fcst_attrib + ' "' + str(fcstshp) + '" "' + str(fcst_raster) + '"')
        retval = os.system(gdal_rasterize  + ' -a_srs EPSG:4326 -ts ' + str(cols) + ' ' + str(rows) + 
                           ' -te ' + str(xmin) + ' ' + str(ymin) + ' ' + str(xmax) + ' ' + str(ymax) + 
                           ' -a ' + fcst_attrib + ' "' + str(fcstshp) + '" "' + str(fcst_raster) + '"')
        if retval != 0:
            print('failed to rasterize the forecast vector into raster')
            return
        
        ffcst_dst = Dataset(fcst_raster)
        ffcst = ffcst_dst['Band1'][:]
        times = predictand_data.times()
        monn = datetime.strptime(predictorMonth, '%b').strftime('%m')
        season = season_start_month.get(predictorMonth)
        
        # compute long term statistics
        print('computing long term statistics')
        window.statusbar.showMessage('computing long term statistics')
        # compute season totals for training period
        try:
            # compute season totals for current year
            yr = config.get('fcstyear')
            mon1 = datetime.strptime(str(yr)+monn, '%Y%m')
            mon2 = (mon1 + relativedelta(months=+1)).strftime('%Y%m')
            mon3 = (mon1 + relativedelta(months=+2)).strftime('%Y%m')
            mon1 = predictand_data.tslice()[monthindex(times, mon1.strftime('%Y%m'))]
            mon2 = predictand_data.tslice()[monthindex(times, mon2)]
            mon3 = predictand_data.tslice()[monthindex(times, mon3)]
            if config.get('composition', 'Sum') == "Sum":
                currentseasonmap = np.sum([mon1, mon2, mon3], axis=0)
            else:
                currentseasonmap = np.mean([mon1, mon2, mon3], axis=0)
            # compute season totals for training period
            for yr in trainingYears:
                mon1 = datetime.strptime(str(yr)+monn, '%Y%m')
                mon2 = (mon1 + relativedelta(months=+1)).strftime('%Y%m')
                mon3 = (mon1 + relativedelta(months=+2)).strftime('%Y%m')
                mon1 = predictand_data.tslice()[monthindex(times, mon1.strftime('%Y%m'))]
                mon2 = predictand_data.tslice()[monthindex(times, mon2)]
                mon3 = predictand_data.tslice()[monthindex(times, mon3)]
                if config.get('composition', 'Sum') == "Sum":
                    trainingseasonmaps.append(np.sum([mon1, mon2, mon3], axis=0))
                else:
                    trainingseasonmaps.append(np.mean([mon1, mon2, mon3], axis=0))
                window.statusbar.showMessage('aggregation for ' + str(yr) + '...')
        except Exception as e:
            print('Error: ' + str(e))
            window.statusbar.showMessage('Error: ' + str(e))
            return
        
        ltmean = np.nanmean(trainingseasonmaps, axis=0)
        ltmedian = np.nanmedian(trainingseasonmaps, axis=0)
        ltstd = np.nanstd(trainingseasonmaps, axis=0)
        ltperc33 = np.nanpercentile(trainingseasonmaps, 33, axis=0)
        ltperc50 = np.nanpercentile(trainingseasonmaps, 50, axis=0)
        ltperc66 = np.nanpercentile(trainingseasonmaps, 66, axis=0)
        ltstdmod = ltstd * 1.25
        llimit = ltmean - ltstdmod
        ulimit = ltmean + ltstdmod
        testout = np.zeros((ltmean.shape))
        tercver = np.ones((ltmean.shape)) * 255.
        verout = np.ones((ltmean.shape)) * 255.
        ltmeannz = ltmean[:]
        ltmeannz[ltmeannz==0] = .0001 
        panom = 100. * currentseasonmap / ltmeannz
        ltmediannz = ltmedian[:]
        ltmediannz[ltmediannz==0] = .0001 
        percmedian = 100. * currentseasonmap / ltmediannz
        
        # compute verification matrices
        print('computing verification matrices')
        window.statusbar.showMessage('computing verification matrices')
        test1 = (currentseasonmap < llimit)
        test2 = ((currentseasonmap >= llimit) & (currentseasonmap < ltmedian))
        test3 = ((currentseasonmap >= ltmedian) & (currentseasonmap < ulimit))
        test4 = (currentseasonmap >= ulimit)
        testout[test1] = 1.
        testout[test2] = 2.
        testout[test3] = 3.
        testout[test4] = 4.
        verout[(testout == ffcst)] = 100.
        verout[(abs(testout - ffcst) == 1)] = 66.
        verout[(abs(testout - ffcst) == 2)] = 33.
        verout[(abs(testout - ffcst) == 3)] = 0.
        verout[(ffcst == 0)] = 255
        tercver[currentseasonmap < ltperc33] = 1.
        tercver[currentseasonmap >= ltperc33] = 2.
        tercver[currentseasonmap >= ltperc50] = 3.
        tercver[currentseasonmap >= ltperc66] = 4.
        verstats = pd.DataFrame(data=[np.count_nonzero(verout == 0),
                           np.count_nonzero(verout == 33),
                           np.count_nonzero(verout == 66),
                           np.count_nonzero(verout == 100)],
                     columns=['Total'],index=['False-Alarm','Half-Miss', 'Half-Hit', 'Hit'])
        verstats['%'] = round(100 * verstats.Total / verstats.Total.sum(),1)
        verstats.to_csv(verstatscsvout, header=True, index=True)
        
        np.count_nonzero(verout != 255)
        ffcst_dst.close()
        
        # compute verification matrices
        print('generate verification output file')
        window.statusbar.showMessage('generate verification output file')
        if os.path.exists(outputnc):  os.remove(outputnc)
        output = Dataset(outputnc, 'w', format='NETCDF4')
        title = 'Verification'
        output.description = title
        output.comments = 'Created ' + datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")
        output.source = config.get('Version')
        output.history = title
        lat = output.createDimension('lat', rows)
        lon = output.createDimension('lon', cols)
        T = output.createDimension('T', 1)
        initial_date = output.createVariable('T', np.float64, ('T',))
        latitudes = output.createVariable('lat', np.float32, ('lat',))
        longitudes = output.createVariable('lon', np.float32, ('lon',))
        bltmean = output.createVariable('mean', np.float64, ('T', 'lat', 'lon'))
        bltmedian = output.createVariable('median', np.float64, ('T', 'lat', 'lon'))
        bltsdmod = output.createVariable('stdmod', np.float64, ('T', 'lat', 'lon'))
        bllimit = output.createVariable('llimit', np.float64, ('T', 'lat', 'lon'))
        bulimit = output.createVariable('ulimit', np.float64, ('T', 'lat', 'lon'))
        bterc33 = output.createVariable('terc33', np.float64, ('T', 'lat', 'lon'))
        bterc50 = output.createVariable('terc50', np.float64, ('T', 'lat', 'lon'))
        bterc66 = output.createVariable('terc66', np.float64, ('T', 'lat', 'lon'))
        bffcst = output.createVariable('fcst', np.uint8, ('T', 'lat', 'lon'))
        bactual = output.createVariable('actual', np.float64, ('T', 'lat', 'lon'))
        banomp = output.createVariable('anom', np.float64, ('T', 'lat', 'lon'))
        bpercmedian = output.createVariable('percmedian', np.float64, ('T', 'lat', 'lon'))
        bterc = output.createVariable('terc', np.uint8, ('T', 'lat', 'lon'))
        bverif = output.createVariable('ver', np.uint8, ('T', 'lat', 'lon'))
        latitudes.units = 'degree_north'
        latitudes.axis = 'Y'
        latitudes.long_name = 'Latitude'
        latitudes.standard_name = 'Latitude'
        longitudes.units = 'degree_east'
        longitudes.axis = 'X'
        longitudes.long_name = 'Longitude'
        longitudes.standard_name = 'Longitude'
        initial_date.units = 'days since ' + str(config.get('fcstyear')) + '-' + monn + '-00'
        initial_date.axis = 'T'
        initial_date.calendar = 'standard'
        initial_date.standard_name = 'time'
        initial_date.long_name = 'date'
        latitudes[:] = predictand_data.lats
        longitudes[:] = predictand_data.lons
        bltmean[:] = ltmean
        bltmedian[:] = ltmedian
        bltsdmod[:] = ltstdmod
        bllimit[:] = llimit
        bulimit[:] = ulimit
        bterc33[:] = ltperc33
        bterc50[:] = ltperc50
        bterc66[:] = ltperc66
        bffcst[:] = ffcst
        bactual[:] = currentseasonmap
        banomp[:] = panom
        bpercmedian[:] = percmedian
        bterc[:] = tercver
        bverif[:] = verout
        output.close()     
        if os.path.exists(fcst_raster):  os.remove(fcst_raster)
        print(verstats)
        print("End time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print('Done in ' + str(convert(time.time() - start_time)))
        window.statusbar.showMessage('Done in ' + str(convert(time.time() - start_time)))
    
    
    # --- Load values into the UI ---
    #
    window.outdirlabel.setText(config.get('outDir'))
    #
    if config.get('fcstPeriodLength') == 'month':
        window.monthlyRadio.setChecked(True)
    else:
        window.seasonalRadio.setChecked(True)
    #
    window.forecastvectorlabel.setText(os.path.basename(config.get('fcstvector').get('file')))
    for attr in config.get('fcstvector').get('attr'):
        window.forecastvectorparamcombobox.addItem(attr)
    if type(config.get('fcstvector').get('ID')) == type(0): 
        window.forecastvectorparamcombobox.setCurrentIndex(config.get('fcstvector').get('ID'))
    #
    window.predictandlabel.setText(os.path.basename(config.get('predictand').get('file')))
    for attr in config.get('predictand').get('attr'):
        window.climatparamcombobox.addItem(attr)
    if type(config.get('predictand').get('ID')) == type(0): 
        window.climatparamcombobox.setCurrentIndex(config.get('predictand').get('ID'))
    #
    if window.seasonalRadio.isChecked():
        periodxs = config.get('period').get('season')
    else:
        periodxs = config.get('period').get('month')
    for periodx in periodxs:
        window.periodComboBox.addItem(periodx)  
    if type(config.get('period').get('indx')) == type(0): 
        window.periodComboBox.setCurrentIndex(config.get('period').get('indx'))
    #     
    if config.get('inputFormat') == "CSV":
        window.CSVRadio.setChecked(True)
    else:
        window.NetCDFRadio.setChecked(True)
    #
    if config.get('composition') == "Sum":
        window.cumRadio.setChecked(True)
    if config.get('composition') == "Average":
        window.avgRadio.setChecked(True)
    #
    window.forecastvectorlabel.setText(os.path.basename(config.get('fcstvector',{}).get('file')))
    window.startyearLineEdit.setText(str(config.get('trainStartYear')))
    window.endyearLineEdit.setText(str(config.get('trainEndYear')))
    window.fcstyearlineEdit.setText(str(config.get('fcstyear')))
    

    ## Signals
    window.outputButton.clicked.connect(getOutDir)
    window.forecastvectorButton.clicked.connect(addBaseVector)
    window.CSVRadio.toggled.connect(change_format_type)
    window.NetCDFRadio.toggled.connect(change_format_type)
    window.cumRadio.toggled.connect(change_composition)
    window.avgRadio.toggled.connect(change_composition)
    window.climatdataButton.clicked.connect(addPredictand)
    window.runButton.clicked.connect(launch_verification_Thread)
    # window.stopButton.clicked.connect(closeapp)
    sys.exit(app.exec_())
