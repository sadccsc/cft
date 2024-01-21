#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
  CFT launcher startup script

@author: thembani
"""

import os, sys, time, threading
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import *
qtCreatorFile = "start.ui"

#
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)

class MyApp(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.setupUi(self)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MyApp()
    window.show()

    def closeapp():
        sys.exit(app.exec_())

    def runzoning():
        retval = os.system('bash start_linux.sh zoning.py')
        if retval != 0:
            window.statusbar.showMessage('failed to start zoning tool')
    
    def runforecasting():
        retval = os.system('bash start_linux.sh cft.py')
        if retval != 0:
            window.statusbar.showMessage('failed to start forecasting tool')
    
    def runverification():
        retval = os.system('bash start_linux.sh verification.py')
        if retval != 0:
            window.statusbar.showMessage('failed to start verification tool')
 
    def runsynthesis():
        retval = os.system('bash start_linux.sh forecast_synthesis.py')
        if retval != 0:
            window.statusbar.showMessage('failed to start synthesis tool')
       
    
    # --- Load values into the UI ---
    

    ## Signals
    window.zoningButton.clicked.connect(runzoning)
    window.fcstButton.clicked.connect(runforecasting)
    window.verButton.clicked.connect(runverification)
    window.synthesisButton.clicked.connect(runsynthesis)

    # window.stopButton.clicked.connect(closeapp)
    sys.exit(app.exec_())
