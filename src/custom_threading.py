import sys
import traceback
from PyQt5 import QtCore
import threading
import traceback
import sys


class WorkerSignals(QtCore.QObject):
    """
    Defines the signals available from a running worker thread.
    Supported signals are:
    ``finished``: No data
    ``error``: tuple (exctype, value, traceback.format_exc() )
    ``result``: object data returned from processing, anything
    ``progress``: int indicating % progress
    """
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(tuple)
    result = QtCore.pyqtSignal(object)
    progress = QtCore.pyqtSignal(int)


class Worker(QtCore.QRunnable):
    """
    Inherits from QRunnable to handle worker thread setup, signals and wrap-up.
    ``param callback`` The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    ``type callback`` function
    ``param args`` Arguments to pass to the callback function
    ``param kwargs`` Keywords to pass to the callback function
    """
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.event_stop = threading.Event()
        self.is_killed = False
        
        # # Add the callback to our kwargs
        # self.kwargs['progress_callback'] = self.signals.progress

    @QtCore.pyqtSlot()
    def run(self):
        """Reimplementation of ``run()``."""
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
            
        self.signals.finished.emit()

    @QtCore.pyqtSlot()
    def kill(self):
        """
        Stop code execution.
        """
        print("Thread killed")
        self.is_killed = True
        self.event_stop.set()