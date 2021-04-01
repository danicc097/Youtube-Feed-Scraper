import configparser
import copy
import ctypes
import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path

import pyautogui
import pyperclip
import qtmodern.styles
import qtmodern.windows
from jsonpath_ng import jsonpath
from jsonpath_ng.ext import parse
from PyQt5 import QtCore, QtGui
from PyQt5 import QtWidgets
from PyQt5 import QtWidgets as qtw
from PyQt5.QtGui import (
    QColor, QFont, QIcon, QImage, QPainter, QPainterPath, QPixmap, QStandardItem, QStandardItemModel
)
from PyQt5.QtWidgets import (
    QAbstractButton, QApplication, QCompleter, QDesktopWidget, QFrame, QGraphicsDropShadowEffect,
    QGridLayout, QHBoxLayout, QLabel, QLayout, QListWidget, QListWidgetItem, QMainWindow,
    QScrollArea, QSizePolicy, QSystemTrayIcon, QTableWidget, QTableWidgetItem, QToolButton,
    QTreeView, QVBoxLayout, QWidget
)

from .designer.YoutubeScraper import Ui_MainWindow
from .file_loader import DownLoader
from .resources import get_path
from .save_restore import grab_GC, guirestore, guisave

BASEDIR = get_path(Path(__file__).parent)
print(f"BASEDIR is {BASEDIR}")

if hasattr(sys, 'frozen'):
    basis = sys.executable
else:
    basis = sys.argv[0]

#* Fix qtmodern stylesheets in runtime (plus spec file edit)
root = Path()
if getattr(sys, 'frozen', False):
    root = Path(sys._MEIPASS)
    qtmodern.styles._STYLESHEET = root / 'qtmodern/style.qss'
    qtmodern.windows._FL_STYLESHEET = root / 'qtmodern/frameless.qss'

RUNTIME_DIR = Path(os.path.split(basis)[0])
print(f"RUNTIME_DIR is {RUNTIME_DIR}")

#* Set icon on Windows taskbar
if sys.platform == 'win32':
    myappid = u'Youtube Scraper'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)


class NewWindow(QMainWindow):
    """MainWindow factory."""
    def __init__(self):
        super().__init__()
        self.window_list = []
        self.add_new_window()

    def add_new_window(self):
        """Creates new MainWindow instance."""
        self.app_icon = QIcon()
        app_icon_path = str(Path.joinpath(BASEDIR, 'data', 'main-icon.png'))
        self.app_icon.addFile(app_icon_path)
        app.setWindowIcon(self.app_icon)
        app_icon = QIcon(str(Path.joinpath(BASEDIR, 'data', 'main-icon.png')))
        app.setWindowIcon(app_icon)
        window = MainWindow(self)
        window.setWindowTitle("Youtube Scraper")
        window.setWindowIcon(app_icon)
        self.window_list.append(window)  # it's not garbage

        #* Fancier style
        qtmodern.styles.light(app)
        # not garbage either
        self.mw = qtmodern.windows.ModernWindow(window)
        self.center(self.mw)
        self.mw.show()

        #* Classic style
        # self.center(window)
        # window.show()

    def center(self, window):
        qr = window.frameGeometry()
        cp = QApplication.primaryScreen().geometry().center()
        qr.moveCenter(cp)
        window.move(qr.topLeft())

    def shutdown(self):
        for window in self.window_list:
            if window.runner:  # set self.runner=None in your __init__ so it's always defined.
                window.runner.kill()


class MainWindow(QMainWindow, Ui_MainWindow):
    """Main application window."""
    def __init__(self, window):
        super().__init__()
        self.setupUi(self)
        self.windowManager = window
        self.GUI_preferences_path = str(Path.joinpath(RUNTIME_DIR, 'GUI_preferences.ini'))
        self.GUI_preferences = QtCore.QSettings(
            self.GUI_preferences_path, QtCore.QSettings.IniFormat
        )
        #* Object names not to be saved to settings
        self.objects_to_exclude = ["listWidgetVideos"]
        self.app_downloader = DownLoader()  # only one instance necessary for the whole app
        self.widgets_with_hover = []
        # workaround for graphics effect limitation
        self.shadow_effects = {}
        self.shadow_effects_counter = 0
        self.config = configparser.ConfigParser()
        self.config_is_set = 0
        self.save_to_runtimedir = False
        self.message_is_being_shown = False
        # self.FILEBROWSER_PATH = os.path.join(os.getenv('WINDIR'), 'explorer.exe')
        self.threadpool = QtCore.QThreadPool()
        self.img_sync = QPixmap(str(Path.joinpath(BASEDIR, 'data', 'synchronize-icon.png')))
        self.img_sync = self.img_sync.scaled(
            25, 25, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation
        )
        self.label_sync = QLabel(None)
        self.title = QLabel("Loading YouTube data...")
        self.label_sync.setFixedSize(25, 25)
        self.title.setFixedSize(120, 25)
        self.title.setMinimumHeight(self.label_sync.height())
        self.label_sync.setPixmap(self.img_sync)
        self.signal = MySignal()
        self.signal.sig_no_args.connect(self.add_sync_icon)
        self.signal.sig_no_args.connect(self.remove_sync_icon)
        self.updated_rncs = False
        self.actionPLAY.setFlat(True)
        play_icon = QIcon(str(Path.joinpath(BASEDIR, 'data', 'images', 'playback_play.png')))
        pause_icon = QPixmap(str(Path.joinpath(BASEDIR, 'data', 'images', 'playback_pause.png')))
        play_icon.addPixmap(pause_icon, QtGui.QIcon.Active, QtGui.QIcon.On)
        self.actionPLAY.setIcon(play_icon)
        self.actionPLAY.setIconSize(QtCore.QSize(48, 48))
        self.actionFF.setFlat(True)
        self.actionFF.setIcon(
            QIcon(str(Path.joinpath(BASEDIR, 'data', 'images', 'playback_ff.png')))
        )

        self.actionFF.setIconSize(QtCore.QSize(32, 32))
        self.actionREW.setFlat(True)
        self.actionREW.setIcon(
            QIcon(str(Path.joinpath(BASEDIR, 'data', 'images', 'playback_rew.png')))
        )
        self.actionREW.setIconSize(QtCore.QSize(32, 32))

        self.applyShadowEffect(
            self.horizontalSlider, color=QColor(16, 47, 151), blur_radius=20, offset=0
        )

        self.applyEffectOnHover(self.actionPLAY)
        self.applyEffectOnHover(self.actionFF)
        self.applyEffectOnHover(self.actionREW)

        self.actionPLAY.clicked.connect(self.onPlay)

        self.actionSave.setIcon(QIcon(str(Path.joinpath(BASEDIR, 'data', 'images', 'save.png'))))
        self.actionOpen.setIcon(QIcon(str(Path.joinpath(BASEDIR, 'data', 'images', 'open.png'))))
        self.actionAbout.setIcon(QIcon(str(Path.joinpath(BASEDIR, 'data', 'images', 'about.png'))))
        self.actionEdit.setIcon(
            QIcon(str(Path.joinpath(BASEDIR, 'data', 'images', 'settings.png')))
        )
        self.actionExit.setIcon(QIcon(str(Path.joinpath(BASEDIR, 'data', 'images', 'exit.png'))))
        self.actionGitHub_Homepage.setIcon(
            QIcon(str(Path.joinpath(BASEDIR, 'data', 'images', 'github.png')))
        )

        # TODO reopen
        # Thread runner
        self.runner = None
        self.threadpool = QtCore.QThreadPool()

        #TODO restore if GUI_preferences.ini file found in same dir
        if os.path.exists(self.GUI_preferences_path):
            try:
                guirestore(self, self.GUI_preferences)
                self.save_to_runtimedir = True
            except:
                pass
        else:
            with open(self.GUI_preferences_path, 'w'):
                guisave(self, self.GUI_preferences, self.objects_to_exclude)

        self.actionGitHub_Homepage.triggered.connect(self.GitHubLink)
        self.actionOpen.triggered.connect(self.readFile)
        self.actionSave.triggered.connect(self.writeFile)
        self.actionSave_as.triggered.connect(self.writeNewFile)
        self.actionAbout.triggered.connect(self.AboutInfo)

        # self.horizontalHeader.sectionClicked.connect(self.on_view_horizontalHeader_sectionClicked)
        self.listWidgetVideos.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        # self.listWidgetVideos.itemClicked.connect(lambda item: self.qlist_focus_color(item)) #TODO change highlight color

        self.listWidgetVideos.customContextMenuRequested.connect(
            lambda pos: self.on_customContextMenuRequested_list(pos)
        )

        self.createTrayIcon()
        self.trayIcon.setIcon(QIcon(str(Path.joinpath(BASEDIR, 'data', 'main-icon.png'))))
        self.trayIcon.messageClicked.connect(self.notification_handler)

        json_var = get_yt_source_text(from_local_dir=True)
        my_videos = get_my_videos(json_var)

        # #### Quick view
        # i = 0
        # for id, video in my_videos.items():
        #     if i >= 3:
        #         break
        #     print('\n'.join("'%s': '%s', " % item for item in vars(video).items()))
        #     print("---------------------------")
        #     i += 1
        # #### END Quick view

        #* Fill QListWidget with custom widgets
        for video_id, video in my_videos.items():
            myQCustomQWidget = QCustomQWidget(video=video)
            #TODO: use rounded card styles with QFrames
            """
            Create a widget with Qt::Window | Qt::FramelessWindowHint and Qt::WA_TranslucentBackground flag
            Create a QFrame inside of a widget
            Set a stylesheel to QFrame, for example:
            """
            myQCustomQWidget.setTextUp(video.title)
            url = video.thumbnail
            data = urllib.request.urlopen(url).read()
            vid_thumbnail = QImage()
            vid_thumbnail.loadFromData(data)
            myQCustomQWidget.setIcon(vid_thumbnail)
            myQListWidgetItem = QListWidgetItem(self.listWidgetVideos)
            myQListWidgetItem.setSizeHint(myQCustomQWidget.sizeHint())
            self.listWidgetVideos.addItem(myQListWidgetItem)
            self.listWidgetVideos.setItemWidget(myQListWidgetItem, myQCustomQWidget)
            self.listWidgetVideos

        #* Expandable section below
        spoiler = Spoiler(title="TEST", ref_parent=self)
        self.applyEffectOnHover(spoiler)
        self.gridLayout.addWidget(spoiler)

        qtw.QAction("Quit", self).triggered.connect(self.closeEvent)

    def AboutInfo(self):
        """Shows license information"""
        # parent is necessary to center by default
        self.infoScreen = qtw.QMessageBox(self)
        self.infoScreen.setWindowTitle('Legal Information')
        self.infoScreen.setText('This program is licenced under the GNU GPL v3.\t\t')
        self.infoScreen.setInformativeText("The complete license is available below.\t\t")
        try:
            self.infoScreen.setDetailedText(
                open(str(Path.joinpath(BASEDIR.parent, "LICENSE")), "r", encoding="utf-8").read()
            )
        except:
            self.infoScreen.setDetailedText("http://www.gnu.org/licenses/gpl-3.0.en.html")
        self.infoScreen.setWindowModality(QtCore.Qt.ApplicationModal)
        self.infoScreen.show()

    def onPlay(self):
        """"""

    def applyShadowEffect(
        self, widget: QWidget, color=QColor(50, 50, 50), blur_radius=10, offset=2
    ):
        """Same widget graphic effect instance can't be used more than once
        else it's removed from the first widget. Workaround using a dict:"""
        self.shadow_effects[self.shadow_effects_counter] = QGraphicsDropShadowEffect(self)
        self.shadow_effects[self.shadow_effects_counter].setBlurRadius(blur_radius)
        self.shadow_effects[self.shadow_effects_counter].setColor(color)
        self.shadow_effects[self.shadow_effects_counter].setOffset(offset)
        widget.setGraphicsEffect(self.shadow_effects[self.shadow_effects_counter])
        self.shadow_effects_counter += 1

    def applyEffectOnHover(self, widget: QWidget):
        """Installs an event filter to display a shadow upon hovering.
        The event filter is MainWindow. An event filter receives all events 
        that are sent to this object."""
        widget.installEventFilter(self)
        self.widgets_with_hover.append(widget)

    def GitHubLink(self):
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl('https://github.com/danicc097/Youtube-Feed-Scraper')
        )

    @QtCore.pyqtSlot(QtCore.QPoint)
    def on_customContextMenuRequested_list(self, pos):
        menu = qtw.QMenu()
        delete_row = menu.addAction("Remove")
        action = menu.exec_(self.listWidgetWindows.viewport().mapToGlobal(pos))
        if action == delete_row:
            item = self.listWidgetWindows.itemAt(pos)
            row = self.listWidgetWindows.row(item)
            self.listWidgetWindows.takeItem(row)

    def writeNewFile(self):  # ? Save as
        """Saves GUI user input to a new config file"""
        self.config_is_set += 1
        self.filename, _ = qtw.QFileDialog.getSaveFileName(
            self,
            "Select where to save the configuration file…",
            str(Path.joinpath(BASEDIR, 'data')),
            'Configuration Files (*.ini)',
            options=qtw.QFileDialog.DontResolveSymlinks
        )
        self.statusBar().showMessage(self.filename)
        if self.filename.lower().endswith('.ini'):
            try:
                self.my_settings = QtCore.QSettings(self.filename, QtCore.QSettings.IniFormat)
                # all values will be returned as QString
                guisave(self, self.my_settings, self.objects_to_exclude)
                self.save_to_runtimedir = False
                self.statusBar().showMessage("Changes saved to: {}".format(self.filename))
            except Exception as e:
                qtw.QMessageBox.critical(self, 'Error', f"Could not save settings: {e}")

    def writeFile(self):  # ? Save
        """Saves GUI user input to the previously opened config file"""
        #* A config file was found at runtime and restored
        if self.save_to_runtimedir:
            self.statusBar().showMessage("Changes saved to: {}".format(self.GUI_preferences_path))
            guisave(self, self.GUI_preferences, self.objects_to_exclude)
        #* A config file was opened from the menu
        elif self.config_is_set and self.filename != "":
            self.statusBar().showMessage("Changes saved to: {}".format(self.filename))
            self.my_settings = QtCore.QSettings(self.filename, QtCore.QSettings.IniFormat)
            guisave(self, self.my_settings, self.objects_to_exclude)
        else:
            self.writeNewFile()

    def readFile(self):  # ? Open
        """Restores GUI user input from a config file"""
        #* File dialog
        self.filename, _ = qtw.QFileDialog.getOpenFileName(
            self,
            "Select a configuration file to load…",
            str(RUNTIME_DIR),
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

    def add_sync_icon(self):
        self.statusBar().addPermanentWidget(self.label_sync)
        self.statusBar().addPermanentWidget(self.title)

    def remove_sync_icon(self):
        self.statusBar().removeWidget(self.label_sync)
        self.statusBar().removeWidget(self.title)

    def showSuccess(self):
        self.trayIcon.show()
        if not self.hasFocus():
            self.message_is_being_shown = True
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

    #######################################################
    ##### EVENTS
    #######################################################

    def eventFilter(self, object, event):
        if isinstance(object, QWidget) and object in self.widgets_with_hover:
            if event.type() == QtCore.QEvent.Enter:
                print("Mouse is over the widget ")
                self.applyShadowEffect(object, color=QColor(16, 47, 151), blur_radius=20, offset=0)

                return True
            elif event.type() == QtCore.QEvent.Leave:
                print("Mouse is not over the widget ")
                object.setGraphicsEffect(None)
        return False

    def changeEvent(self, event):
        """Hides the system tray icon when the main window is visible, and viceversa."""
        if event.type() == QtCore.QEvent.WindowStateChange and self.windowState(
        ) and self.isMinimized():
            self.trayIcon.show()
            event.accept()
        else:
            try:
                if not self.message_is_being_shown:
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
            event.accept()
        else:
            event.ignore()


#######################################################
#######################################################
##### END OF MAINWINDOW
#######################################################
#######################################################


class Video():
    """Store video information for ease of use
    """
    def __init__(self, id, title="", time="", author="", thumbnail="", author_thumbnail=""):
        self.id = str(id)
        self.url = "https://www.youtube.com/watch?v=" + self.id
        self.title = str(title)
        self.time = str(time)
        self.author = str(author)
        self.thumbnail = str(thumbnail)
        self.author_thumbnail = str(author_thumbnail)


def get_my_videos(json_var):
    """Extract video metadata from feed to a dictionary accessed by video ID
    \nParameters:\n   
    ``json_var`` : ytInitialData variable, containing rendered feed videos data"""

    my_videos = {}

    # match all rendered video grids
    jsonpath_expr = parse('*..gridRenderer..gridVideoRenderer')
    videos_json = [match.value for match in jsonpath_expr.find(json_var)]

    parse_strings = {
        'id': 'videoId',
        'title': 'title.runs[*].text',
        'author': 'shortBylineText.runs[*].text',
        'author_thumbnail': 'channelThumbnail.thumbnails[*].url',
        'thumbnail': 'thumbnail.thumbnails[*].url',
        'time': 'publishedTimeText.simpleText',
    }
    videos_parsed = 0
    parsing_limit = 5
    bypass_limit = False  # toggle False for fast dev with limit
    for item in videos_json:
        if videos_parsed >= parsing_limit and not bypass_limit:
            break
        for video_attr, parse_str in parse_strings.items():
            json_expr = parse(parse_str)  # see jsonpath_ng
            matches = [match.value for match in json_expr.find(item)]
            if not matches:
                match_attr = ""
            else:
                match_attr = matches[0]
                if video_attr == "id":
                    video_id = match_attr
                    my_videos[video_id] = Video(video_id)

                setattr(my_videos[video_id], video_attr, match_attr)
        videos_parsed += 1
    return my_videos


def get_yt_source_text(from_local_dir=False, save_to_local_dir=False, last_video: Video = None):
    """Opens a new browser window to get the feed page's source code.
    \nParameters:\n   
    ``from_local_dir`` : get data from local dir after first extraction (dev purposes)
    ``save_to_local_dir`` : save json data to local dir (dev purposes)
    ``last_video`` : ensure ``last_video.id`` is found in source. 
    If not found, it will search until the date is ``last_video.time`` 
    """

    if not from_local_dir:
        url = "https://www.youtube.com/feed/subscriptions"
        webbrowser.open(url)
        pyautogui.sleep(3)
        pyautogui.hotkey("ctrl", "n")
        pyautogui.typewrite(url)
        pyautogui.hotkey("enter")
        pyautogui.sleep(1)
        pyautogui.press("end", presses=10, interval=1)
        pyautogui.hotkey("ctrl", "u")
        pyautogui.sleep(2)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.sleep(0.1)
        pyautogui.hotkey("ctrl", "c")
        pyautogui.sleep(0.5)
        pyautogui.hotkey("ctrl", "w")
        pyautogui.sleep(0.2)
        pyautogui.hotkey("ctrl", "w")
        source = pyperclip.paste()
        try:
            json_var = re.findall(r'ytInitialData = (.*?);', source, re.DOTALL | re.MULTILINE)[0]
        except:
            # TODO qmessage
            print("ERROR : COULD NOT FIND A VALID VIDEO FEED IN SOURCE")
            exit()

    else:
        with open(
            str(Path.joinpath(RUNTIME_DIR, "downloaded_source.json")), "r", encoding="utf-8"
        ) as f:
            json_var = f.read()

    # TODO find last video id in source, else change tab and scroll down
    if last_video is not None:
        videoId = f'"videoId":"{last_video.id}"'
        if not videoId in json_var:
            pass
        else:
            pass

    if not from_local_dir and save_to_local_dir:
        with open(
            str(Path.joinpath(RUNTIME_DIR, "downloaded_source.json")), "a", encoding="utf-8"
        ) as f:
            f.write(json_var)

    return json.loads(json_var)


#########################################################################
#########################################################################
##### CUSTOM WIDGETS
#########################################################################
#########################################################################


class Spoiler(QWidget):
    def __init__(self, parent=None, title='', animationDuration=300, ref_parent=None):
        """
        Collapsable and expandable section.
        Based on:
        http://stackoverflow.com/questions/32476006/how-to-make-an-expandable-collapsable-section-widget-in-qt
        """
        super(Spoiler, self).__init__(parent=parent)
        self.ref_parent = ref_parent
        self.animationDuration = animationDuration
        self.toggleAnimation = QtCore.QParallelAnimationGroup()
        self.contentArea = QScrollArea()
        self.headerLine = QFrame()
        self.toggleButton = QToolButton()
        self.already_filtered = True
        mainLayout = QGridLayout()

        toggleButton = self.toggleButton
        toggleButton.setStyleSheet("QToolButton { border: none; }")
        toggleButton.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        toggleButton.setArrowType(QtCore.Qt.RightArrow)
        toggleButton.setText(str(title))
        toggleButton.setCheckable(True)
        toggleButton.setChecked(False)

        headerLine = self.headerLine
        headerLine.setFrameShape(QFrame.HLine)
        headerLine.setFrameShadow(QFrame.Sunken)
        headerLine.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        self.contentArea.setStyleSheet("QScrollArea { background-color: white; border: none; }")
        self.contentArea.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # start out collapsed
        self.contentArea.setMaximumHeight(0)
        self.contentArea.setMinimumHeight(0)
        # let the entire widget grow and shrink with its content
        toggleAnimation = self.toggleAnimation
        toggleAnimation.addAnimation(QtCore.QPropertyAnimation(self, b"minimumHeight"))
        toggleAnimation.addAnimation(QtCore.QPropertyAnimation(self, b"maximumHeight"))
        toggleAnimation.addAnimation(QtCore.QPropertyAnimation(self.contentArea, b"maximumHeight"))
        # don't waste space
        mainLayout = mainLayout
        mainLayout.setVerticalSpacing(0)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        row = 0
        mainLayout.addWidget(self.toggleButton, row, 0, 1, 1, QtCore.Qt.AlignLeft)
        mainLayout.addWidget(self.headerLine, row, 2, 1, 1)
        row += 1
        mainLayout.addWidget(self.contentArea, row, 0, 1, 3)
        self.setLayout(mainLayout)
        label = QLabel("LOREM IPSUM LOREM IPSUM LOREM IPSUM \n LOREM IPSUM LOREM IPSUM ")
        spoiler_layout = QVBoxLayout()
        spoiler_layout.addWidget(label)
        # set any QLayout in expandable item
        self.setContentLayout(spoiler_layout)

        def start_animation(checked):
            arrow_type = QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow
            direction = QtCore.QAbstractAnimation.Forward if checked else QtCore.QAbstractAnimation.Backward
            toggleButton.setArrowType(arrow_type)
            self.toggleAnimation.setDirection(direction)
            self.toggleAnimation.start()
            self.applyShadowEffect()

        self.toggleButton.clicked.connect(start_animation)

    def applyShadowEffect(self, color=QColor(50, 50, 50), blur_radius=10, offset=2):
        effect = QGraphicsDropShadowEffect(self)
        effect.setBlurRadius(blur_radius)
        effect.setColor(color)
        effect.setOffset(offset)
        if self.already_filtered:
            self.removeEventFilter(self.ref_parent)
            self.already_filtered = False
        else:
            self.installEventFilter(self.ref_parent)
            self.already_filtered = True

        self.setGraphicsEffect(effect)

    def setContentLayout(self, contentLayout: QLayout):
        """Adds a layout ``contentLayout`` to the spoiler area"""
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


class QCustomQWidget(QWidget):
    def __init__(self, parent=None, video: Video = ""):
        super(QCustomQWidget, self).__init__(parent)
        self.textQVBoxLayout = QVBoxLayout()
        self.shadow_effects = {}
        self.shadow_effects_counter = 0
        self.textUpQLabel = QLabel()
        font = QFont()
        font.setPointSize(12)
        self.textUpQLabel.setFont(font)
        base_size = 40
        border_width = 0
        # Overlap filled border-label with image
        self.imgDownQLabel = RoundLabelImage(
            urlpath=video.author_thumbnail,
            size=base_size,
            border_width=border_width,
            border_color=QtGui.QColor(20, 60, 186)
        )

        #* FRAME
        self.frame = QtWidgets.QFrame()
        self.frame.setStyleSheet(
            "color: rgb(70,130,180);\n"
            "background-color: rgb(70,130,180);\n"
            "text-align: center;\n"
            "border-radius: 150px;\n"
            "border-radius: 10px 10px 10px 10px;\n"
            "padding: 0px;"
        )
        self.frame.setWindowOpacity(0.4)
        self.frame.setFixedWidth(200)

        self.textQVBoxLayout.addWidget(self.textUpQLabel)
        self.textQVBoxLayout.addWidget(self.imgDownQLabel)
        self.allQGrid = QGridLayout()
        self.thumbnailQLabel = QLabel()
        self.allQGrid.addWidget(self.thumbnailQLabel, 0, 0, 2, 1, QtCore.Qt.AlignLeft)
        self.allQGrid.addLayout(self.textQVBoxLayout, 0, 1, 2, 1, QtCore.Qt.AlignLeft)
        self.allQGrid.addWidget(self.frame, 1, 2, 1, 1, QtCore.Qt.AlignRight)
        self.setLayout(self.allQGrid)

        # setStyleSheet
        self.textUpQLabel.setStyleSheet('''
            color: rgb(70,130,180);
        ''')
        # self.imgDownQLabel.setStyleSheet('''
        #     color: rgb(255, 0, 0);
        # ''')

        self.applyShadowEffect(self.imgDownQLabel)
        self.applyShadowEffect(self.frame)
        self.applyShadowEffect(self.thumbnailQLabel)

    def applyShadowEffect(self, widget: QWidget):
        """Same widget graphic effect instance can't be used more than once
        else it's removed from the first widget. Workaround using a dict:"""
        self.shadow_effects[self.shadow_effects_counter] = QGraphicsDropShadowEffect(self)
        self.shadow_effects[self.shadow_effects_counter].setBlurRadius(10)
        self.shadow_effects[self.shadow_effects_counter].setColor(QtGui.QColor(50, 50, 50))
        self.shadow_effects[self.shadow_effects_counter].setOffset(2)
        widget.setGraphicsEffect(self.shadow_effects[self.shadow_effects_counter])
        self.shadow_effects_counter += 1

    def setTextUp(self, text):
        self.textUpQLabel.setText(text)
        self.textUpQLabel.setSizePolicy(
            QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        )
        # self.textUpQLabel.setGraphicsEffect(self.effect)

    def setTextDown(self, text):
        """"""

        # self.imgDownQLabel.setText(text)
        # self.imgDownQLabel.setGraphicsEffect(self.effect)

    def setIcon(self, imagePath):
        img = QPixmap(imagePath)
        # important to use a SmoothTransformation
        img = img.scaledToWidth(140, QtCore.Qt.SmoothTransformation)
        self.thumbnailQLabel.setPixmap(img)
        self.thumbnailQLabel.setContentsMargins(0, 0, 20, 0)
        self.thumbnailQLabel.setSizePolicy(
            QSizePolicy(QSizePolicy.Maximum, QSizePolicy.MinimumExpanding)
        )
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setColor(QtGui.QColor(50, 50, 50))
        shadow.setOffset(2)
        self.thumbnailQLabel.setGraphicsEffect(shadow)


class RoundLabelImage(QLabel):
    """Based on:
    https://stackoverflow.com/questions/50819033/qlabel-with-image-in-round-shape/50821539"""
    def __init__(
        self, path="", urlpath="", size=50, border_width=0, border_color=None, antialiasing=True
    ):
        super().__init__()
        self.setFixedSize(size, size)

        if path != "":
            source = QPixmap(path)
        elif urlpath != "":
            # you really shouldn't rely on functions that are possibly blocking...
            data = urllib.request.urlopen(urlpath).read()

            source = QPixmap()
            source.loadFromData(data)

        pixmap_size = size - border_width * 2
        p = source.scaled(
            pixmap_size, pixmap_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation
        )

        self.target = QPixmap(self.size())
        self.target.fill(QtCore.Qt.transparent)

        painter = QPainter(self.target)
        if antialiasing:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        rect = QtCore.QRectF(self.rect())
        if border_width:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(border_color))
            painter.drawEllipse(rect)
            rect.adjust(border_width, border_width, -border_width, -border_width)

        painter_path = QPainterPath()
        painter_path.addEllipse(rect)
        painter.setClipPath(painter_path)

        painter.drawPixmap(border_width, border_width, p)
        self.setPixmap(self.target)

    def RoundLabelClientLoader():
        bar = foo.downloadedData()
        # bar is only a reference, consume it before calling doDownload() again


class MySignal(QtCore.QObject):
    ''' Why a whole new class? See here: 
    https://stackoverflow.com/a/25930966/2441026 '''
    sig_no_args = QtCore.pyqtSignal()
    sig_with_str = QtCore.pyqtSignal(str)


#########################################################################
#########################################################################
##### INITIALIZE UPON IMPORT
#########################################################################
#########################################################################

app = qtw.QApplication(sys.argv)
app.setStyle('Fusion')
app.setStyleSheet("")
app.setApplicationName("Youtube Scraper")
app_icon = QIcon(str(Path.joinpath(BASEDIR, 'data', 'main-icon.png')))
app.setWindowIcon(app_icon)
path = Path.joinpath(BASEDIR, 'data', 'fonts', 'Fira_Sans', 'FiraSans-Medium.ttf')
print(path)
id = QtGui.QFontDatabase.addApplicationFont(str(path))
family = QtGui.QFontDatabase.applicationFontFamilies(id)[0]
font = QtGui.QFont(family, 9)
app.setFont(font)
w = NewWindow()  # Instantiate window factory
app.aboutToQuit.connect(w.shutdown)

timer = QtCore.QTimer()
timer.timeout.connect(lambda: None)
timer.start(100)

sys.exit(app.exec_())
