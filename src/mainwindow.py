import configparser
import copy
import ctypes
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

from PyQt5 import QtCore, QtGui
from PyQt5 import QtWidgets as qtw
from PyQt5.QtGui import (QColor, QFont, QIcon, QPainter, QPixmap, QStandardItem, QStandardItemModel)
from PyQt5.QtWidgets import (
    QAbstractButton, QApplication, QCompleter, QLabel, QMainWindow, QSizePolicy, QSystemTrayIcon,
    QTableWidget, QTableWidgetItem, QTreeView, QWidget
)

from .resources import get_path
from .save_restore import grab_GC, guirestore, guisave
from .YoutubeScraper import Ui_MainWindow

#? Use correct path for both bundled and dev versions
BASEDIR = get_path(Path(__file__).parent)

#* Set icon on Windows taskbar
if sys.platform == 'win32':
    myappid = u'Youtube Scraper'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)


class CustomProxyModel(QtCore.QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._filters = dict()

    @property
    def filters(self):
        return self._filters

    def setFilter(self, expresion, column):
        if expresion:
            self.filters[column] = expresion
        elif column in self.filters:
            del self.filters[column]
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        for column, expresion in self.filters.items():
            text = self.sourceModel().index(source_row, column, source_parent).data()
            regex = QtCore.QRegExp(expresion, QtCore.Qt.CaseInsensitive, QtCore.QRegExp.RegExp)
            if regex.indexIn(text) == -1:
                return False
        return True


class WorkerSignals(QtCore.QObject):
    '''
    Defines the signals available from a running worker thread.

    Supported signals are:

    finished
        No data

    error
        tuple (exctype, value, traceback.format_exc() )

    result
        object data returned from processing, anything

    progress
        int indicating % progress

    '''
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(tuple)
    result = QtCore.pyqtSignal(object)
    progress = QtCore.pyqtSignal(int)


class Worker(QtCore.QRunnable):
    '''
    Worker thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    '''
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        # Add the callback to our kwargs
        # self.kwargs['progress_callback'] = self.signals.progress

    @QtCore.pyqtSlot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''

        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False


class StandardItem(QStandardItem):
    def __init__(self, txt='', font_size=12, set_bold=False, color=QColor(0, 0, 0)):
        super().__init__()

        fnt = QFont('Open Sans', font_size)
        fnt.setBold(set_bold)

        self.setEditable(False)
        self.setForeground(color)
        self.setFont(fnt)
        self.setText(txt)


class treeTab(qtw.QWidget):
    def __init__(self, core, label):
        super(treeTab, self).__init__()
        self.label = label
        self.core = core

        self.sizes = core.UISizes

        self.tab_sizePolicy = qtw.QSizePolicy(qtw.QSizePolicy.Expanding, qtw.QSizePolicy.Expanding)

        self.tree = qtw.QTreeWidget(self)
        self.tree.setColumnCount(len(self.sizes.projectTreeColumnLabels))
        self.tree.setHeaderLabels(self.sizes.projectTreeColumnLabels)
        self.tree.setSizePolicy(self.tab_sizePolicy)
        self.tree_layout = qtw.QGridLayout()
        self.tree_layout.objectName = self.label + "TreeGridLayout"
        self.tree.setLayout(self.tree_layout)
        self.treeroot = self.tree.invisibleRootItem()
        self.tree.setSelectionMode(qtw.QAbstractItemView.ContiguousSelection)

    def addParent(self, parent, column, title, data):
        item = qtw.QTreeWidgetItem(parent, [title])
        item.setData(column, QtCore.Qt.UserRole, data)
        item.setChildIndicatorPolicy(qtw.QTreeWidgetItem.ShowIndicator)
        item.setExpanded(True)
        return item

    def addChild(self, parent, column, title, data):
        item = qtw.QTreeWidgetItem(parent, [title])
        item.setData(column, QtCore.Qt.UserRole, data)
        item.setText(1, data.print_tags())
        item.setText(2, data.category.name)
        item.setText(3, data.format)
        item.setCheckState(column, QtCore.Qt.Unchecked)
        item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
        return item


class AppDemo(QWidget):
    def __init__(self, parent_ref, part, row, theme):
        super().__init__()
        self.setWindowTitle('NHAs')
        self.resize(800, 400)
        self.setLayout(qtw.QVBoxLayout())
        treeView = QTreeView()
        treeView.setHeaderHidden(True)
        if theme == "dark": node_color = QColor(255, 255, 255)
        elif theme == "light": node_color = QColor(0, 0, 0)
        treeModel = QStandardItemModel()
        rootNode = treeModel.invisibleRootItem()
        root_component = StandardItem("NHA tree", 13, set_bold=True, color=node_color)

        nhas = parent_ref.NHA_list
        # print("nhas")
        # print(nhas)
        # print(nhas[row])
        size_count = 0
        for i in reversed(nhas[row][part]):
            child_component = StandardItem(i, 16 - size_count, set_bold=True, color=node_color)
            root_component.appendRow(child_component)
            size_count += 1
        rootNode.appendRow(root_component)
        child_component = StandardItem(
            part, 16 - size_count, set_bold=True, color=QColor(255, 0, 255)
        )
        root_component.appendRow(child_component)
        treeView.setModel(treeModel)
        treeView.expandAll()
        # treeView.doubleClicked.connect(self.makeEditable)
        self.layout().addWidget(treeView)

    def makeEditable(self, val):
        val.setFlags(val.flags() | QtCore.Qt.ItemIsEditable)


class Spoiler(QtGui.QWidget):
    def __init__(self, parent=None, title='', animationDuration=300):
        """
        Collapsable and expandable section.
        
        http://stackoverflow.com/questions/32476006/how-to-make-an-expandable-collapsable-section-widget-in-qt
        """
        super(Spoiler, self).__init__(parent=parent)

        self.animationDuration = animationDuration
        self.toggleAnimation = QtCore.QParallelAnimationGroup()
        self.contentArea = QtGui.QScrollArea()
        self.headerLine = QtGui.QFrame()
        self.toggleButton = QtGui.QToolButton()
        self.mainLayout = QtGui.QGridLayout()

        toggleButton = self.toggleButton
        toggleButton.setStyleSheet("QToolButton { border: none; }")
        toggleButton.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        toggleButton.setArrowType(QtCore.Qt.RightArrow)
        toggleButton.setText(str(title))
        toggleButton.setCheckable(True)
        toggleButton.setChecked(False)

        headerLine = self.headerLine
        headerLine.setFrameShape(QtGui.QFrame.HLine)
        headerLine.setFrameShadow(QtGui.QFrame.Sunken)
        headerLine.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Maximum)

        self.contentArea.setStyleSheet("QScrollArea { background-color: white; border: none; }")
        self.contentArea.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Fixed)
        # start out collapsed
        self.contentArea.setMaximumHeight(0)
        self.contentArea.setMinimumHeight(0)
        # let the entire widget grow and shrink with its content
        toggleAnimation = self.toggleAnimation
        toggleAnimation.addAnimation(QtCore.QPropertyAnimation(self, b"minimumHeight"))
        toggleAnimation.addAnimation(QtCore.QPropertyAnimation(self, b"maximumHeight"))
        toggleAnimation.addAnimation(QtCore.QPropertyAnimation(self.contentArea, b"maximumHeight"))
        # don't waste space
        mainLayout = self.mainLayout
        mainLayout.setVerticalSpacing(0)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        row = 0
        mainLayout.addWidget(self.toggleButton, row, 0, 1, 1, QtCore.Qt.AlignLeft)
        mainLayout.addWidget(self.headerLine, row, 2, 1, 1)
        row += 1
        mainLayout.addWidget(self.contentArea, row, 0, 1, 3)
        self.setLayout(self.mainLayout)

        def start_animation(checked):
            arrow_type = QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow
            direction = QtCore.QAbstractAnimation.Forward if checked else QtCore.QAbstractAnimation.Backward
            toggleButton.setArrowType(arrow_type)
            self.toggleAnimation.setDirection(direction)
            self.toggleAnimation.start()

        self.toggleButton.clicked.connect(start_animation)

    def setContentLayout(self, contentLayout):
        # Not sure if this is equivalent to self.contentArea.destroy()
        self.contentArea.destroy()
        self.contentArea.setLayout(contentLayout)
        collapsedHeight = self.sizeHint().height() - self.contentArea.maximumHeight()
        contentHeight = contentLayout.sizeHint().height()
        for i in range(self.toggleAnimation.animationCount() - 1):
            spoilerAnimation = self.toggleAnimation.animationAt(i)
            spoilerAnimation.setDuration(self.animationDuration)
            spoilerAnimation.setStartValue(collapsedHeight)
            spoilerAnimation.setEndValue(collapsedHeight + contentHeight)
        contentAnimation = self.toggleAnimation.animationAt(
            self.toggleAnimation.animationCount() - 1
        )
        contentAnimation.setDuration(self.animationDuration)
        contentAnimation.setStartValue(0)
        contentAnimation.setEndValue(contentHeight)


class QCustomQWidget(QtGui.QWidget):
    """Custom widget to be added as item in a QListWidget"""
    def __init__(self, parent=None):
        super(QCustomQWidget, self).__init__(parent)
        self.textQVBoxLayout = QtGui.QVBoxLayout()
        self.textUpQLabel = QtGui.QLabel()
        self.textDownQLabel = QtGui.QLabel()
        self.textQVBoxLayout.addWidget(self.textUpQLabel)
        self.textQVBoxLayout.addWidget(self.textDownQLabel)
        self.allQHBoxLayout = QtGui.QHBoxLayout()
        self.iconQLabel = QtGui.QLabel()
        self.allQHBoxLayout.addWidget(self.iconQLabel, 0)
        self.allQHBoxLayout.addLayout(self.textQVBoxLayout, 1)
        self.setLayout(self.allQHBoxLayout)
        # setStyleSheet
        self.textUpQLabel.setStyleSheet('''
            color: rgb(0, 0, 255);
        ''')
        self.textDownQLabel.setStyleSheet('''
            color: rgb(255, 0, 0);
        ''')

    def setTextUp(self, text):
        self.textUpQLabel.setText(text)

    def setTextDown(self, text):
        self.textDownQLabel.setText(text)

    def setIcon(self, imagePath):
        self.iconQLabel.setPixmap(QtGui.QPixmap(imagePath))


class NewWindow(QMainWindow):
    """MainWindow factory."""
    def __init__(self):
        super().__init__()
        GUI_preferences_path = str(Path.joinpath(BASEDIR.parent, 'data', 'GUI_preferences.ini'))
        self.GUI_preferences = QtCore.QSettings(GUI_preferences_path, QtCore.QSettings.IniFormat)
        self.window_list = []
        self.add_new_window()

    def add_new_window(self):
        """Creates new MainWindow instance."""
        self.app_icon = QIcon()
        app_icon_path = str(Path.joinpath(BASEDIR.parent, 'data', 'main-icon.png'))
        self.app_icon.addFile(app_icon_path)
        app.setWindowIcon(self.app_icon)
        app_icon = QIcon(str(Path.joinpath(BASEDIR.parent, 'data', 'main-icon.png')))
        app.setWindowIcon(app_icon)
        window = MainWindow(self, self.GUI_preferences)
        window.setWindowTitle("Youtube Scraper")
        window.setWindowIcon(app_icon)
        self.window_list.append(window)
        window.show()

    def shutdown(self):
        for window in self.window_list:
            if window.runner:  # set self.runner=None in your __init__ so it's always defined.
                window.runner.kill()


class MySignal(QtCore.QObject):
    ''' Why a whole new class? See here: 
    https://stackoverflow.com/a/25930966/2441026 '''
    sig_no_args = QtCore.pyqtSignal()
    sig_with_str = QtCore.pyqtSignal(str)


class JobRunner(QtCore.QRunnable):
    """keepwindows"""
    signals = WorkerSignals()

    def __init__(self):
        super().__init__()
        self.event_stop = threading.Event()
        self.is_paused = False
        self.is_killed = False

    @QtCore.pyqtSlot()
    def run(self):
        counter = 0
        while True:
            # essential condition to kill the runner
            if self.event_stop.is_set() or self.is_killed:
                return
            counter += 1
            refresh = w.window_list[0].refreshRate.value()
            if refresh == None or refresh < 1: refresh = 0.1  # TODO
            print(f"{counter}: keeping windows open for {refresh} minutes")
            #? what should've been done: timer.start(refresh), and then on timeout would connect to run()
            #? so that there's no long sleep function
            timer = QtCore.QTimer()
            timer.timeout.connect(lambda: None)
            timer.start(100)

    @QtCore.pyqtSlot()
    def pause(self):
        self.is_paused = True

    @QtCore.pyqtSlot()
    def resume(self):
        self.is_paused = False

    @QtCore.pyqtSlot()  # CRUCIAL TO ADD WRAPPER
    def kill(self):
        print("Thread killed")
        self.is_killed = True
        self.event_stop.set()


class MainWindow(QMainWindow, Ui_MainWindow):
    """Main application window."""
    def __init__(self, window, GUI):
        super().__init__()
        self.setupUi(self)
        self.windowManager = window
        self.GUI_preferences = GUI
        self.config = configparser.ConfigParser()
        self.config_is_set = 0
        self.FILEBROWSER_PATH = os.path.join(os.getenv('WINDIR'), 'explorer.exe')
        self.threadpool = QtCore.QThreadPool()
        print("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())
        self.keep_lists = []  # RNC_Form
        self.all_windows = []  # keepwindows
        self.run_keep_windows = False
        self.rnc_tabs = []
        # self.rnc_data.show()
        self.im = QPixmap(str(Path.joinpath(BASEDIR.parent, 'data', 'synchronize-icon.png')))
        self.im = self.im.scaled(25, 25)
        self.label = QLabel(None)
        self.title = QLabel("Loading NCR data...")
        self.label.setFixedSize(25, 25)
        self.title.setFixedSize(120, 25)
        self.title.setMinimumHeight(self.label.height())
        self.label.setPixmap(self.im)
        self.signal = MySignal()
        self.signal.sig_no_args.connect(self.add_sync_icon)
        self.signal.sig_no_args.connect(self.remove_sync_icon)
        self.updated_rncs = False
        self.startForce.setFlat(True)
        self.startForce.setIcon(QIcon(str(Path.joinpath(BASEDIR.parent, 'data', 'start-icon.png'))))
        self.startForce.setIconSize(QtCore.QSize(40, 40))
        self.stopForce.setFlat(True)
        self.stopForce.setIcon(QIcon(str(Path.joinpath(BASEDIR.parent, 'data', 'stop-icon.png'))))
        self.stopForce.setIconSize(QtCore.QSize(40, 40))
        self.tabWidget.setCurrentIndex(0)

        # TODO reopen
        # Thread runner
        self.runner = None
        self.threadpool = QtCore.QThreadPool()
        #ISCLOSED TODO
        self.startForce.clicked.connect(self.start_refreshing)
        self.stopForce.setEnabled(False)

        # try:
        #     guirestore(self, self.GUI_preferences)
        # except:
        #     guisave(self, self.GUI_preferences)
        self.ImportCSVFolder.clicked.connect(
            lambda: self.path_extractor(self.PathCSVFolder, button="dmu_csv")
        )
        self.ImportExcelFolder.clicked.connect(
            lambda: self.path_extractor(self.PathExcelFolder, button="dmu_excel")
        )
        self.actionOpen_settings.triggered.connect(self.readFile)
        self.actionSave_settings.triggered.connect(self.writeFile)
        self.actionSave_settings_to.triggered.connect(self.writeNewFile)
        self.horizontalHeader = self.TableResults_2.horizontalHeader()
        # self.horizontalHeader.sectionClicked.connect(self.on_view_horizontalHeader_sectionClicked)

        qtw.QAction("Quit", self).triggered.connect(self.closeEvent)

        self.ImportRNCDatabase.clicked.connect(
            lambda: self.path_extractor_excel(self.PathRNCDatabase)
        )

        self.TableResults.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.TableResults.customContextMenuRequested.connect(
            lambda pos: self.on_customContextMenuRequested(pos)
        )
        self.TableResults_2.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.TableResults_2.customContextMenuRequested.connect(
            lambda pos: self.on_customContextMenuRequested_2(pos)
        )
        self.listWidgetWindows.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.listWidgetWindows.itemClicked.connect(lambda item: self.qlist_focus_color(item))
        self.listWidgetWindows.customContextMenuRequested.connect(
            lambda pos: self.on_customContextMenuRequested_list(pos)
        )
        self.TableResults_2.setSelectionBehavior(qtw.QTableView.SelectRows)

        self.groupBoxCSV.toggled.connect(
            lambda checked: checked and self.groupBoxExcel.setChecked(False)
            if self.groupBoxExcel.isChecked() else checked
        )
        self.groupBoxExcel.toggled.connect(
            lambda checked: checked and self.groupBoxCSV.setChecked(False)
            if self.groupBoxCSV.isChecked() else checked
        )

        self.actionLight.toggled.connect(
            lambda checked: checked and self.actionDark.setChecked(False)
            if self.actionDark.isChecked() else checked
        )
        self.actionDark.toggled.connect(
            lambda checked: checked and self.actionLight.setChecked(False)
            if self.actionLight.isChecked() else checked
        )

        self.createTrayIcon()
        self.trayIcon.setIcon(QIcon(str(Path.joinpath(BASEDIR.parent, 'data', 'main-icon.png'))))
        self.trayIcon.messageClicked.connect(self.notification_handler)

        self.refreshWindows.clicked.connect(self.window_list_grabber)
        self.addWindow.clicked.connect(self.add_window_keeplist)

        #* EGGS
        egg_path = str(Path.joinpath(BASEDIR.parent, 'data', 'eggs', 'keyboard-0.13.4-py3.8.egg'))
        sys.path.append(egg_path)
        egg_path = str(Path.joinpath(BASEDIR.parent, 'data', 'eggs', 'py_trello-0.17.1-py3.8.egg'))
        sys.path.append(egg_path)

    def add_window_keeplist(self):
        self.listWidgetWindows.addItem(self.comboWindows.currentText())

    def window_list_grabber(self):
        self.comboWindows.clear()
        # for i in a:
        #     self.open_windows.append(i)
        self.comboWindows.addItems(self.open_windows)

    def start_refreshing(self):
        # self.runner.signals.progress.connect(self.update_progress)
        self.startForce.setEnabled(False)
        self.stopForce.setEnabled(True)
        self.my_windows = []
        for i in range(self.listWidgetWindows.count()):
            self.my_windows.append(self.listWidgetWindows.item(i).text())
        print("self.my_windows")
        print(self.my_windows)
        self.runner = JobRunner()
        self.threadpool.start(self.runner)

        # signal for runner has to be defined AFTER runner is instantiated
        self.stopForce.clicked.connect(lambda: self.startForce.setEnabled(True))
        self.stopForce.clicked.connect(lambda: self.stopForce.setEnabled(False))

        self.stopForce.clicked.connect(lambda: self.runner.kill())

    def stop_refreshing(self):
        self.run_keep_windows = False

    def add_sync_icon(self):
        self.statusBar().addPermanentWidget(self.label)
        self.statusBar().addPermanentWidget(self.title)

    def remove_sync_icon(self):
        self.statusBar().removeWidget(self.label)
        self.statusBar().removeWidget(self.title)

    # @QtCore.pyqtSlot(str)
    # def on_lineEdit_textChanged(self, text):
    #     self.proxy.setFilter(text, self.comboBox.currentIndex() + 1)

    def showSuccess(self):
        self.trayIcon.show()
        if not self.hasFocus():
            global message_is_being_shown
            message_is_being_shown = True
            self.trayIcon.showMessage(
                f"RNC data has been loaded!\n", "Click here to start searching.",
                self.windowManager.app_icon, 1200 * 1000
            )  # milliseconds default

    def notification_handler(self):
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        self.show()
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowStaysOnTopHint)
        self.show()

    def createTrayIcon(self):
        self.restoreAction = qtw.QAction("&Restore", self, triggered=self.showNormal)
        self.quitAction = qtw.QAction("&Quit", self, triggered=qtw.QApplication.instance().quit)
        self.trayIconMenu = qtw.QMenu(self)
        self.trayIconMenu.addAction(self.restoreAction)
        self.trayIconMenu.addAction(self.quitAction)

        self.trayIcon = QSystemTrayIcon(self)
        self.trayIcon.setContextMenu(self.trayIconMenu)

    def changeEvent(self, event):
        """Hides the system tray icon when the main window is visible, and viceversa."""
        if event.type() == QtCore.QEvent.WindowStateChange and self.windowState(
        ) and self.isMinimized:
            self.trayIcon.show()
            event.accept()
        else:
            try:
                global message_is_being_shown
                if not message_is_being_shown:
                    self.trayIcon.hide()
            except:
                pass

    def closeEvent(self, event):
        """Catches the MainWindow close button event and displays a dialog."""
        close = qtw.QMessageBox(qtw.QMessageBox.Question, 'Exit', 'Exit application?', parent=self)
        close_reject = close.addButton('No', qtw.QMessageBox.NoRole)
        close_accept = close.addButton('Yes', qtw.QMessageBox.AcceptRole)
        close.exec()  # Necessary for property-based API
        if close.clickedButton() == close_accept:
            self.trayIcon.setVisible(False)
            del self.keep_lists
            del self.rnc_tabs
            event.accept()
        else:
            event.ignore()

    def path_extractor_excel(self, dest):
        """Write Excel file path to destination"""
        my_path, _ = qtw.QFileDialog.getOpenFileName(
            self,
            "Select an Excel file to load…",
            str(BASEDIR),
            'Excel Files (*.xlsx)',
            options=qtw.QFileDialog.DontResolveSymlinks
        )
        if my_path == "":
            qtw.QMessageBox.critical(
                self, "Operation aborted", "Empty filename or none selected. \n Please try again.",
                qtw.QMessageBox.Ok
            )
            self.statusBar().showMessage("Select a valid CSV file")
        else:
            dest.setText(my_path)
            self.data_loaded = False

    def qlist_focus_color(self, item):
        for i in range(self.listWidgetWindows.count()):
            if self.actionLight.isChecked():
                self.listWidgetWindows.item(i).setForeground(QtCore.Qt.black)
            else:
                self.listWidgetWindows.item(i).setForeground(QtCore.Qt.white)
        item.setForeground(QtCore.Qt.green)

    @QtCore.pyqtSlot(QtCore.QPoint)
    def on_customContextMenuRequested_list(self, pos):
        menu = qtw.QMenu()
        delete_row = menu.addAction("Remove")
        action = menu.exec_(self.listWidgetWindows.viewport().mapToGlobal(pos))
        if action == delete_row:
            item = self.listWidgetWindows.itemAt(pos)
            row = self.listWidgetWindows.row(item)
            self.listWidgetWindows.takeItem(row)

    @QtCore.pyqtSlot(QtCore.QPoint)
    def on_customContextMenuRequested(self, pos):
        if self.TableResults.itemAt(pos) is None: return
        r = self.TableResults.itemAt(pos).row()
        # item_range = qtw.QTableWidgetSelectionRange(0, c, self.TableResults.rowCount() - 1, c)
        # self.TableResults.setRangeSelected(item_range, True)

        menu = qtw.QMenu()
        show_explorer_action = menu.addAction("Show in explorer")
        show_treeview_action = menu.addAction("Show NHA tree")
        action = menu.exec_(self.TableResults.viewport().mapToGlobal(pos))
        if action == show_explorer_action:
            self.search_explorer(r)
        if action == show_treeview_action:
            self.app_theme = "light" if self.actionLight.isChecked() else "dark"
            self.NHA_tree = AppDemo(
                parent_ref=self,
                part=self.TableResults.item(r, 0).text(),
                row=r,
                theme=self.app_theme
            )
            self.NHA_tree.show()

    @QtCore.pyqtSlot(QtCore.QPoint)
    def on_customContextMenuRequested_2(self, pos):
        if self.TableResults_2.itemAt(pos) is None: return
        r = self.TableResults_2.itemAt(pos).row()
        selected_rows = self.TableResults_2.selectionModel().selectedRows()
        selection_rows = [row.row() for row in sorted(selected_rows)]
        print(selection_rows)
        menu = qtw.QMenu()
        show_expanded_action = menu.addAction("Show expanded")
        action = menu.exec_(self.TableResults_2.viewport().mapToGlobal(pos))
        if action == show_expanded_action:
            for row in selection_rows:
                self.rnc_data.add_tab(row)
            self.rnc_data.show()
            # self.keep_lists.append(rnc_data)
            # self.keep_lists[-1].show()

    def explore(self, path):
        # explorer would choke on forward slashes
        path = os.path.normpath(path)

        if os.path.isdir(path):
            subprocess.run([self.FILEBROWSER_PATH, path])
        elif os.path.isfile(path):
            subprocess.run([self.FILEBROWSER_PATH, '/select,', path])

    def search_explorer(self, row):

        query_string = self.TableResults.item(row, 4).text()
        # query_string = query_string.partition(" ")[0]
        local_path = r'%s' % self.TableResults.item(row, 5).text()
        print(query_string)
        print(local_path)
        # local_path = r'%s' % local_path
        local_path = local_path.replace("/", '\\')
        local_path = r'%s' % local_path
        # local_path = r'%s' % local_path
        local_path = local_path + "\\" + query_string + ".3dxml"
        print(local_path)
        #crumb location network vs folder path
        # subprocess.Popen(
        #     f'explorer /root,"search-ms:crumb=location:{local_path}&query={query_string}&"'
        # )
        self.explore(local_path)

    def thread_complete(self):
        print("THREAD COMPLETE!")

    def print_output(self, s):
        if str(s[0]) == "fail":
            qtw.QMessageBox.critical(
                self, "Information", f"No results were found for {str(s[1])}.", qtw.QMessageBox.Ok
            )

    def progress_fn(self, n):
        print("%d%% done" % n)

    def oh_no(self, fn):
        # Pass the function to execute
        worker = Worker(fn)  # Any other args, kwargs are passed to the run function
        worker.signals.result.connect(self.print_output)
        # worker.signals.finished.connect(self.thread_complete)
        # worker.signals.progress.connect(self.progress_fn)
        # Execute
        self.threadpool.start(worker)

    def oh_no_no_output(self, fn):
        # Pass the function to execute
        worker = Worker(fn)  # Any other args, kwargs are passed to the run function
        # worker.signals.result.connect(self.print_output)
        # worker.signals.finished.connect(self.thread_complete)
        # worker.signals.progress.connect(self.progress_fn)
        # Execute
        self.threadpool.start(worker)

    def oh_no_preload(self, fn):
        # Pass the function to execute
        self.add_sync_icon()  # not displaying, shows the set size for statusbar only
        worker = Worker(fn)  # Any other args, kwargs are passed to the run function
        # worker.signals.result.connect(self.print_output)
        worker.signals.finished.connect(self.remove_sync_icon)
        # worker.signals.progress.connect(self.progress_fn)
        # Execute
        self.threadpool.start(worker)

    def writeNewFile(self):  # ? Save as
        """Saves GUI user input to a new config file"""
        self.config_is_set += 1
        self.filename, _ = qtw.QFileDialog.getSaveFileName(
            self,
            "Select where to save the configuration file…",
            str(Path.joinpath(BASEDIR.parent, 'data')),
            'Configuration Files (*.ini)',
            options=qtw.QFileDialog.DontResolveSymlinks
        )
        self.statusBar().showMessage(self.filename)
        if self.filename.lower().endswith('.ini'):
            try:
                self.my_settings = QtCore.QSettings(self.filename, QtCore.QSettings.IniFormat)
                # all values will be returned as QString
                guisave(self, self.my_settings)
                self.statusBar().showMessage("Changes saved to: {}".format(self.filename))
            except Exception as e:
                qtw.QMessageBox.critical(self, 'Error', f"Could not save settings: {e}")

    def readFile(self):  # ? Open
        """Restores GUI user input from a config file"""
        #* File dialog
        self.filename, _ = qtw.QFileDialog.getOpenFileName(
            self,
            "Select a configuration file to load…",
            "C:\\",
            'Configuration Files (*.ini)',
            options=qtw.QFileDialog.DontResolveSymlinks
        )
        #* Invalid file or none
        if self.filename == "":
            qtw.QMessageBox.critical(
                self, "Operation aborted", "Empty filename or none selected. \n Please try again.",
                qtw.QMessageBox.Ok
            )
            self.statusBar().showMessage("Select a valid configuration file")
        #* Valid file
        else:
            if self.filename.lower().endswith('.ini'):
                self.config_is_set += 1
                try:
                    self.my_settings = QtCore.QSettings(self.filename, QtCore.QSettings.IniFormat)
                    guirestore(self, self.my_settings)

                    self.app_theme = "light" if self.actionLight.isChecked() else "dark"
                    self.oh_no_no_output(self.set_autocomplete_dmu())
                    self.statusBar().showMessage(
                        "Changes now being saved to: {}".format(self.filename)
                    )
                    self.setWindowTitle(os.path.basename(self.filename))

                except Exception as e:
                    qtw.QMessageBox.critical(self, 'Error', f"Could not open settings: {e}")
            else:
                qtw.QMessageBox.critical(
                    self, "Invalid file type", "Please select a .ini file.", qtw.QMessageBox.Ok
                )

    def path_extractor(self, dest, button=None):
        """Write path to destination"""
        my_path = qtw.QFileDialog.getExistingDirectory(
            self,
            "Select a directory to save results",
            "C:\\",
            options=qtw.QFileDialog.DontResolveSymlinks
        )
        if my_path == "":
            qtw.QMessageBox.critical(
                self, "Operation aborted", "No folder. \n Please try again.", qtw.QMessageBox.Ok
            )
            self.statusBar().showMessage("Select a valid folder.")
        else:
            dest.setText(my_path)
            if button == "NCR":
                self.data_loaded = False
            elif button == "dmu_csv" or button == "dmu_excel":
                self.oh_no_no_output(self.set_autocomplete_dmu())

    def set_autocomplete_dmu(self):
        names = []
        names = list(set(names))  # drop duplicates
        # print(names)
        completer = QCompleter(names)
        # completer.setModelSorting(qtw.QCompleter.CaseSensitivelySortedModel)

        # completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.SearchTerm.setCompleter(completer)

    def writeFile(self):  # ? Save
        """Saves GUI user input to the previously opened config file"""
        if self.config_is_set and self.filename != "":
            self.statusBar().showMessage("Changes saved to: {}".format(self.filename))
            self.my_settings = QtCore.QSettings(self.filename, QtCore.QSettings.IniFormat)
            guisave(self, self.my_settings)
        else:
            self.writeNewFile()


app = qtw.QApplication(sys.argv)
app.setStyle('Fusion')
app.setStyleSheet("")
app.setApplicationName("Youtube Scraper")
app_icon = QIcon(str(Path.joinpath(BASEDIR.parent, 'data', 'main-icon.png')))
app.setWindowIcon(app_icon)
w = NewWindow()  # Instantiate window factory
app.aboutToQuit.connect(w.shutdown)

timer = QtCore.QTimer()
timer.timeout.connect(lambda: None)
timer.start(100)

sys.exit(app.exec_())
