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
        retval = os.system('START /B start_zoning.bat')
        if retval != 0:
            window.statusbar.showMessage('failed to start start_zoning.bat')
    
    def runforecasting():
        retval = os.system('START /B start_cft.bat')
        if retval != 0:
            window.statusbar.showMessage('failed to start start_cft.bat')
    
    def runverification():
        retval = os.system('START /B start_verification.bat')
        if retval != 0:
            window.statusbar.showMessage('failed to start start_verification.bat')
       
    def runsynthesis():
        retval = os.system('START /B start_synthesis.bat')
        if retval != 0:
            window.statusbar.showMessage('failed to start start_synthesis.bat')
       
    
    # --- Load values into the UI ---
    

    ## Signals
    window.zoningButton.clicked.connect(runzoning)
    window.fcstButton.clicked.connect(runforecasting)
    window.verButton.clicked.connect(runverification)
    window.synthesisButton.clicked.connect(runsynthesis)

    # window.stopButton.clicked.connect(closeapp)
    sys.exit(app.exec_())
