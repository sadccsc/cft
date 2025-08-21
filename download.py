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

from functions.functions_download import *

gl.maxLeadTime=6
gl.configFile="download.json"    


            
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
        self.buttons = [self.button1_run, self.button2_run, self.button3_run, self.button4_run]

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
        self.groups=[self.groupBox1, self.groupBox2, self.groupBox3, self.groupBox4]                        
        for gB in self.groups:
            setup_collapsible(gB)
            #collapsing
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


    
    
            
        
if os.path.exists(gl.configFile):
    try:
        showMessage("reading config from: {}".format(gl.configFile))
        with open(gl.configFile, "r") as f:
            gl.config = json.load(f)
        populateGui()
    except:    
        showMessage("config file corrupted. Making default config.".format(gl.configFile))
        makeConfig()
        populateGui()
else:
    showMessage("config file {} does not exist. Making default config.".format(gl.configFile))
    makeConfig()
    populateGui()

    
sys.exit(app.exec_())

    