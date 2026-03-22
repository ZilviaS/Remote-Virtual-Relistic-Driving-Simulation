from PyQt5.QtCore import QObject, pyqtSignal

class RTC_Signal(QObject):
    connected = pyqtSignal()
    disconnected = pyqtSignal()