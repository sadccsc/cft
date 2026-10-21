#!/usr/bin/env python
# coding: utf-8
"""
Products module - GUI.
Calculations are done by computeProductsObsNoGui() in cft.functions.functions_products_obs,
which can also be called without the GUI.
"""
# this is the main flow control that manages UI
# the process here is as follows:
# - load default config - setConfigDefaults()
# - update that config if config file exists
# - populate gui with config - populateUI()
# - start event loop giving control to UI - gl.app.exec_()
# 
# - on pressing of the calculate button in UI
#      - runProducts() which
#           - updates config - reading UI and overwriting config file - updateConfig()
#           - starts Worker
#           - worker calls computeProductsObsNoGui()
#

import os, sys, json
from pathlib import Path

import xarray as xr

from PyQt5 import QtCore, QtWidgets, uic, QtGui
from PyQt5.QtCore import QThread, QObject, pyqtSignal

from cft import gl
from cft.functions.functions_common import showMessage
from cft.functions.functions_products_obs import computeProductsObsNoGui, CATEGORIES

baseDir = os.path.dirname(__file__)
qtCreatorFile = Path(baseDir, "products_obs.ui")
configfile = "products_obs.json"


#finding all products irrespective of category
productKeys = []
for products in CATEGORIES.values():   # outer loop: each category's dict
    for k in products:                 # inner loop: each key in that dict
        productKeys.append(k)
        

# UI actions ########################################################################

def clearLog():
    gl.window.logWindow.clear()


def closeApp():
    gl.window.close()


def getOutDir():
    outDir = QtWidgets.QFileDialog.getExistingDirectory(directory=".." + os.sep)
    if outDir != "":
        gl.window.lineEdit_outdir.setText(outDir)


def getObsFile():
    fileName = QtWidgets.QFileDialog.getOpenFileName(gl.window, "Select File", ".." + os.sep,
                                                     filter="Data files (*.nc *.csv)")[0]
    if fileName == "":
        return
    w = gl.window
    w.comboBox_obsvar.clear()
    if fileName.lower().endswith(".nc"):
        try:
            with xr.open_dataset(fileName, decode_times=False) as ds:
                variables = list(ds.data_vars)
        except Exception:
            showMessage("Could not read {}, check if it is a valid netcdf file".format(fileName), "ERROR")
            return
        w.comboBox_obsvar.addItems(variables)
    w.lineEdit_obsfile.setText(fileName)


def getRegimeFile():
    fileName = QtWidgets.QFileDialog.getOpenFileName(gl.window, "Select File", ".." + os.sep,
                                                     filter="NetCDF File (*.nc)")[0]
    if fileName != "":
        gl.window.lineEdit_regimefile.setText(fileName)


# config ############################################################################

def setConfigDefaults():
    return {
        "outDir": "",
        "obsFile": "",
        "obsVar": "",
        "obsMissingValue": "",
        "obsDsetCode": "",
        "climStartYr": 1991,
        "climEndYr": 2020,
        "onsetAnchorMonth": {"summer": 10, "winter": 3},    # month in which the onset search starts
        "onsetWindowDays": {"summer": 123, "winter": 153},  # length of the onset search window, days
        "regimeFile": "",
        "parallelize": True,
        "dwtpSaveFiltered":False,
        "products": {key: False for key in productKeys},
    }

def setDiagEnabled(enabled):
     for w in (gl.window.label_diaglat, gl.window.lineEdit_diaglat,
           gl.window.label_diaglon, gl.window.lineEdit_diaglon,
           gl.window.label_diagyear, gl.window.lineEdit_diagyear): w.setEnabled(enabled)

def populateUI():
    c = gl.config
    w = gl.window

    w.lineEdit_outdir.setText(c["outDir"])
    w.lineEdit_obsfile.setText(c["obsFile"])
    if c["obsVar"] != "":
        w.comboBox_obsvar.addItem(c["obsVar"])
    w.lineEdit_obsmissingvalue.setText(c["obsMissingValue"])
    w.lineEdit_dsetcode.setText(c["obsDsetCode"])
    w.lineEdit_climstartyr.setText(str(c["climStartYr"]))
    w.lineEdit_climendyr.setText(str(c["climEndYr"]))
    w.lineEdit_regimefile.setText(c["regimeFile"])
    w.checkBox_parallelize.setChecked(bool(c["parallelize"]))
    w.checkBox_dwtpsavefiltered.setChecked(bool(c["dwtpSaveFiltered"]))
    # checkbox objectName == product key
    for key in productKeys:
        getattr(w, key).setChecked(bool(c["products"].get(key, False)))

    w.comboBox_summerstart.setCurrentIndex(c["onsetAnchorMonth"]["summer"] - 1)
    w.spinBox_summerdays.setValue(c["onsetWindowDays"]["summer"])

    w.pushButton_outdir.clicked.connect(getOutDir)
    w.pushButton_obsfile.clicked.connect(getObsFile)
    w.pushButton_regimefile.clicked.connect(getRegimeFile)
    w.button_run.clicked.connect(w.runProductsObs)
    w.button_exit.clicked.connect(closeApp)
    w.clearLogButton.clicked.connect(clearLog)
    w.checkBox_plotmaps.setChecked(bool(gl.config.get("plotMaps", False)))
    w.checkBox_diagall.setChecked(bool(gl.config.get("diagAll", False)))
    w.lineEdit_diaglat.setText(str(gl.config.get("diagLat", "")))
    w.lineEdit_diaglon.setText(str(gl.config.get("diagLon", "")))
    w.lineEdit_diagyear.setText(str(gl.config.get("diagYear", "")))
    setDiagEnabled(w.checkBox_diagall.isChecked())



def updateConfig():
    # reads values from UI, checks them, saves config to json. Returns True if all OK
    c = gl.config
    w = gl.window

    c["outDir"] = w.lineEdit_outdir.text()
    c["obsFile"] = w.lineEdit_obsfile.text()
    c["obsVar"] = w.comboBox_obsvar.currentText()
    c["obsMissingValue"] = w.lineEdit_obsmissingvalue.text()
    c["obsDsetCode"] = w.lineEdit_dsetcode.text()
    c["regimeFile"] = w.lineEdit_regimefile.text()
    c["parallelize"] = w.checkBox_parallelize.isChecked()
    c["dwtpSaveFiltered"] = w.checkBox_dwtpsavefiltered.isChecked()
    
    
    c["products"] = {key: getattr(w, key).isChecked() for key in productKeys}
    
    c["onsetAnchorMonth"] = {"summer": w.comboBox_summerstart.currentIndex() + 1,
                             "winter": w.comboBox_winterstart.currentIndex() + 1}
    c["onsetWindowDays"] = {"summer": w.spinBox_summerdays.value(),
                            "winter": w.spinBox_winterdays.value()}

    if c["outDir"] == "":
        showMessage("Output directory has to be set", "ERROR")
        return False
    if c["obsFile"] == "" or not Path(c["obsFile"]).exists():
        showMessage("Observations file has to be selected and must exist", "ERROR")
        return False
    if c["obsFile"].lower().endswith(".nc") and c["obsVar"] == "":
        showMessage("Variable has to be selected", "ERROR")
        return False
    if c["obsDsetCode"] == "":
        showMessage("Dataset code missing", "ERROR")
        return False
    if c["regimeFile"] != "" and not Path(c["regimeFile"]).exists():
        showMessage("Regime map {} does not exist".format(c["regimeFile"]), "ERROR")
        return False
    try:
        c["climStartYr"] = int(w.lineEdit_climstartyr.text())
        c["climEndYr"] = int(w.lineEdit_climendyr.text())
    except ValueError:
        showMessage("Climatological period years have to be integers", "ERROR")
        return False
    if c["obsMissingValue"] != "":
        try:
            float(c["obsMissingValue"])
        except ValueError:
            showMessage("Missing value code has to be a number", "ERROR")
            return False
    if not any(c["products"].values()):
        showMessage("Select at least one product", "ERROR")
        return False

    c["plotMaps"] = w.checkBox_plotmaps.isChecked()
    c["diagAll"] = w.checkBox_diagall.isChecked()
    c["diagLat"] = w.lineEdit_diaglat.text().strip()
    c["diagLon"] = w.lineEdit_diaglon.text().strip()
    c["diagYear"] = w.lineEdit_diagyear.text().strip()

    with open(configfile, "w") as fp:
        json.dump(c, fp, indent=4)
    return True


# threading #########################################################################

class Worker(QObject):
    finished = pyqtSignal()

    def run(self):
        try:
            computeProductsObsNoGui(gl.config)
        except Exception as e:
            showMessage("Unexpected error: {}".format(e), "ERROR")
        self.finished.emit()


# main window #######################################################################

Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)


class MyApp(QtWidgets.QMainWindow, Ui_MainWindow):
    log_signal = QtCore.pyqtSignal(str)

    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)
        self.log_signal.connect(self.appendLog)
        self.setWindowTitle(gl.titleFor("Products module"))
        self.setWindowIcon(QtGui.QIcon(os.path.join(baseDir, "cft.ico")))
        
        # starting widths of left and right panel, in pixels
        self.splitter.setSizes([650, 350])
        # when the window is resized, the left panel takes 2 parts of the change, the log 1
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 1)
        # stop either panel being dragged to zero width
        self.splitter.setChildrenCollapsible(False)
        self.checkBox_diagall.toggled.connect(setDiagEnabled)

    def appendLog(self, message):
        self.logWindow.appendHtml(message)
        self.logWindow.ensureCursorVisible()

    def runProductsObs(self):
        # UI is read in the main thread, calculation runs in a worker thread
        if not updateConfig():
            return
        self.button_run.setEnabled(False)
        self.thread = QThread()
        self.worker = Worker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(lambda: self.button_run.setEnabled(True))
        self.thread.start()


def main():
    gl.app = QtWidgets.QApplication(sys.argv)
    gl.window = MyApp()
    gl.window.show()

    #setting config defaults
    gl.config = setConfigDefaults()

    #updating config if config file exists
    try:
        with open(configfile) as fp:
            gl.config.update(json.load(fp))
        showMessage("Config loaded from {}".format(configfile), "INFO")
    except Exception:
        showMessage("Default settings loaded", "INFO")

    populateUI()
    
    sys.exit(gl.app.exec_())


if __name__ == "__main__":
    main()
