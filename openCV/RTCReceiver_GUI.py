import sys
from PyQt5.QtWidgets import *
from RTCReceiver_Model import RTC_Receiver
from RTCSignal import RTC_Signal

# ======================
# GUI
# ======================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RTC Receiver")
        self.setGeometry(730,300,400,200)
        layout = QVBoxLayout()

        self.ipLabel = QLabel("Car IP")
        self.ipLabelInput = QLineEdit()
        self.submitButtonClick = QPushButton("Submit")

        self.submitButtonClick.clicked.connect(self.launchWebRTC)

        layout.addWidget(self.ipLabel)
        layout.addWidget(self.ipLabelInput)
        layout.addWidget(self.submitButtonClick)

        self.setLayout(layout)
        self.show()

    def launchWebRTC(self):
        self.rtc = RTC_Receiver(self.ipLabelInput.text())
        self.submitButtonClick.setEnabled(False)
        self.ipLabelInput.setReadOnly(True)
        self.rtc.signal.connected.connect(self.connectionSuccess)
        self.rtc.signal.disconnected.connect(self.connectionLost)

    def connectionSuccess(self):
        QMessageBox.information(self, "RTC", "Connection Success")

    def connectionLost(self):
        QMessageBox.warning(self,"RTC","Connection Lost")
        self.submitButtonClick.setEnabled(True)
        self.ipLabelInput.setReadOnly(False)

    def closeEvent(self, event):
        if hasattr(self, "rtc"):
            self.rtc.stop()
        event.accept()




# ======================
# Entry point
# ======================

if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    sys.exit(app.exec_())

