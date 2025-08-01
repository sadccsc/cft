import json, os, sys
import gl
from PyQt5 import QtWidgets

months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
seasons = ['JFM','FMA','MAM','AMJ','MJJ','JJA','JAS','ASO','SON','OND','NDJ','DJF']










def writeConfigToFile(settingsFileName):
    try:
        with open(settingsFileName, 'w') as outfile:
            json.dump(gl.config, outfile, indent=4)
    except:
        print("Could not write to settings file {}".format(settingsFileName))




def getOutDir():
    gl.config['outDir'] = QtWidgets.QFileDialog.getExistingDirectory(directory='..' + os.sep)
    gl.window.outdirlabel.setText(gl.config.get('outDir'))



def addPredictors():
    global config
    fileNames = QtWidgets.QFileDialog.getOpenFileNames(gl.window,
                'Add File(s)', '..' + os.sep, filter="NetCDF/CSV Files (*.nc* *.csv *.txt)")
    for fileName in fileNames[0]:
        gl.config['predictorList'].append(fileName)
        gl.window.predictorlistWidget.addItem(os.path.basename(fileName))


def removePredictors():
    global config
    newList = []
    if len(gl.window.predictorlistWidget.selectedItems()) == 0:
        return
    for yy in gl.config.get('predictorList'):
        if os.path.basename(yy) != gl.window.predictorlistWidget.selectedItems()[0].text():
            newList.append(yy)
    gl.window.predictorlistWidget.clear()
    gl.config['predictorList'] = newList
    for yy in newList:
        gl.window.predictorlistWidget.addItem(os.path.basename(yy))


def addPredictands():
    global config
    global csvheader
    gl.config['predictandList'] = []
    gl.window.predictandlistWidget.clear()
    gl.window.predictandIDcombobox.clear()
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
                    gl.window.predictandIDcombobox.addItem(key)
            gl.config['predictandList'].append(fileName[0])
            gl.window.predictandlistWidget.addItem(os.path.basename(fileName[0]))
        except:
            gl.window.statusbar.showMessage(
                "Could not read predictand file, check if it is a valid NetCDF")
            return

def clearPredictands():
    gl.config['predictandList'] = []
    gl.window.predictandlistWidget.clear()
    gl.window.predictandIDcombobox.clear()


def changePeriodList():
    periodlist = []
    gl.window.periodComboBox.clear()
    if gl.window.period1Radio.isChecked() == True:
        gl.config['fcstPeriodLength'] = '3month'
        periodlist = seasons
    if gl.window.period2Radio.isChecked() == True:
        gl.config['fcstPeriodLength'] = '1month'
        periodlist = months
    for xx in range(len(periodlist)):
        gl.window.periodComboBox.addItem(periodlist[xx])


def changeFormatType():
    gl.window.predictandlistWidget.clear()
    gl.window.predictandIDcombobox.clear()
    gl.config['inputFormat'] = ""


def populateComboBoxes(period, startmonth):
    periodlist = []
    index = months.index(startmonth)
    gl.window.periodComboBox.clear()
    if period == '3month':
        gl.window.period1Radio.setChecked(True)
        periodlist = seasons
    else:
        gl.window.period2Radio.setChecked(True)
        periodlist = months
    for xx in range(len(periodlist)):
        gl.window.periodComboBox.addItem(periodlist[xx])
    gl.window.periodComboBox.setCurrentIndex(index)

    #populating list of months
    for xx in range(len(months)):
        gl.window.predictMonthComboBox.addItem(months[xx])



def addZoneVector():
    gl.window.zoneIDcomboBox.clear()
    gl.window.zonevectorlabel.setText('')
    gl.config['zonevector'] = {"file": None, "ID": 0, "attr": []}
    zonefieldsx = []
    gl.window.zoneIDcomboBox.setDuplicatesEnabled(False)
    fileName = QtWidgets.QFileDialog.getOpenFileName(gl.window,
              'Add File', '..' + os.sep, filter="GeoJson File (*.geojson)")
    gl.config['zonevector']['file'] = fileName[0]
    if os.path.isfile(gl.config.get('zonevector',{}).get('file')):
        with open(gl.config.get('zonevector',{}).get('file')) as f:
            zonejson = geojson.load(f)
        for zonekey in zonejson['features']:
            for zonetype in zonekey.properties:
                zonefieldsx.append(zonetype)
        zonefields = []
        [zonefields.append(x) for x in zonefieldsx if x not in zonefields]
        for xx in zonefields:
            gl.window.zoneIDcomboBox.addItem(str(xx))
            gl.config['zonevector']['attr'].append(str(xx))
        gl.window.zonevectorlabel.setText(os.path.basename(gl.config.get('zonevector',{}).get('file')))


def setInputFormat():
    if gl.window.CSVRadio.isChecked():
        gl.config['inputFormat'] = "CSV"
    else:
        gl.config['inputFormat'] = "NetCDF"





