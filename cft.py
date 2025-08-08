import sys
import subprocess
from PyQt5 import QtWidgets, uic, QtCore


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("cft.ui", self)

        self.buttons = [
            self.downloadButton,
            self.zoningButton,
            self.forecastButton,
            self.verificationButton,
            self.synthesisButton,
        ]
        self.script_map = {
            self.downloadButton: "download.py",
            self.zoningButton: "zoning.py",
            self.forecastButton: "forecast.py",
            self.verificationButton: "verification.py",
            self.synthesisButton: "synthesis.py",
        }

        # Keep references to subprocesses
        self.processes = []

        for btn in self.buttons:
            btn.clicked.connect(lambda _, b=btn: self.launch_script(b))

    def launch_script(self, button):
        """Disable buttons, run script in background, re-enable when done"""
        script = self.script_map[button]
        self.set_buttons_enabled(False)

        # Launch script in a separate process
        process = subprocess.Popen([sys.executable, script])
        self.processes.append(process)

        # Use a QTimer to check if process is finished
        timer = QtCore.QTimer(self)
        timer.setInterval(500)  # check every 0.5 sec
        timer.timeout.connect(lambda: self.check_process(process, timer))
        timer.start()

    def check_process(self, process, timer):
        """Check if the subprocess finished, and re-enable buttons"""
        if process.poll() is not None:  # process finished
            timer.stop()
            self.processes.remove(process)
            self.set_buttons_enabled(True)

    def set_buttons_enabled(self, enabled: bool):
        for btn in self.buttons:
            btn.setEnabled(enabled)

    def closeEvent(self, event):
        """Gracefully close the app and terminate any running subprocesses"""
        # Optional: Ask the user for confirmation
        reply = QtWidgets.QMessageBox.question(
            self,
            "Exit",
            "Are you sure you want to quit?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.No:
            event.ignore()
            return

        # Terminate any running subprocesses
        for p in self.processes:
            if p.poll() is None:  # still running
                p.terminate()  # or p.kill() if you need to force

        event.accept()  # let the window close

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())