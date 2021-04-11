# Copyright (C) 2021 Daniel Castro

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
import webbrowser
from pathlib import Path
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer, QMediaPlaylist

import pyautogui
import pyperclip
import qtmodern.styles
import qtmodern.windows
from jsonpath_ng import jsonpath
from jsonpath_ng.ext import parse
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import (
    QByteArray, QEasingCurve, QObject, QPoint, QPointF, QPropertyAnimation, QRectF, QSequentialAnimationGroup, QSize,
    Qt, QUrl, pyqtProperty, pyqtSignal, pyqtSlot
)
from PyQt5.QtGui import (QBrush, QColor, QFont, QIcon, QImage, QPainter, QPainterPath, QPaintEvent, QPen, QPixmap)
from PyQt5.QtNetwork import (QNetworkAccessManager, QNetworkReply, QNetworkRequest)
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel, QLayout,
    QListWidgetItem, QMainWindow, QPushButton, QScrollArea, QSizePolicy, QSlider, QSystemTrayIcon, QToolButton,
    QVBoxLayout, QWidget
)
from youtube_dl import YoutubeDL

from .resources import *
from .save_restore import *
from .networking import *
from .custom_widgets import *

# from qt_material import apply_stylesheet

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


class MyLogger(object):
    """YoutubeDL logger"""
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        print(msg)


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

        # # Add the callback to our kwargs
        # self.kwargs['progress_callback'] = self.signals.progress

    @QtCore.pyqtSlot()
    def run(self):
        """Initialise the runner function with passed args, kwargs."""
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


ICONS = MyIcons(BASEDIR)


class Video():
    """
    Store video information for ease of use. 
    Download it in parallel using ``start_download`` in a worker.
    """
    def __init__(self, id, title="", time="", author="", thumbnail="", author_thumbnail="", duration=""):
        self.id = str(id)
        self.url = "https://www.youtube.com/watch?v=" + self.id
        self.title = str(title)
        self.time = str(time)
        self.author = str(author)
        self.thumbnail = str(thumbnail)
        self.author_thumbnail = str(author_thumbnail)
        self.duration = str(duration)
        self.is_downloaded = False
        self.download_button: CustomImageButton = None

    def start_download(self, download_dir):
        """``download_dir`` : temp dir or user-defined."""
        self.download_path = os.path.join(download_dir, f'{self.id}.mp3')
        # do not set extension explicitly bc of conversion done internally
        outtmpl = self.download_path.replace(".mp3", r".%(ext)s")
        ydl_opts = {
            'format': 'bestaudio',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
            'logger': MyLogger(),
            'progress_hooks': [self.progress_hook],
            'outtmpl': outtmpl
        }
        with YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([self.url])
            except:
                self.download_fail()

    def progress_hook(self, d):
        if d['status'] == 'finished':
            print(f'Done downloading {self.title}. Converting...')
            self.download_success()
            self.is_downloaded = True

    def download_success(self):
        self.download_button.icon = QIcon(ICONS.cloud_download_green)

    def download_fail(self):
        self.download_button.icon = QIcon(ICONS.cloud_download_red)


class CustomSignals(QtCore.QObject):
    """ Why a whole new class? See here: 
    https://stackoverflow.com/a/25930966/2441026 """
    no_args = QtCore.pyqtSignal()
    sync_icon = QtCore.pyqtSignal(str, bool)
    add_listitem = QtCore.pyqtSignal(Video)
    start_video_download = QtCore.pyqtSignal(Video)


class NewWindow(QMainWindow):
    """MainWindow factory."""
    def __init__(self):
        super().__init__()
        self.window_list = []
        self.add_new_window()

    def add_new_window(self):
        """Creates new MainWindow instance."""
        app_icon = QIcon(str(Path.joinpath(BASEDIR, 'data', 'main-icon.png')))
        window = MainWindow(self)
        window.setWindowTitle("Youtube Scraper")
        app.setWindowIcon(app_icon)
        window.setWindowIcon(app_icon)
        self.window_list.append(window)  # it's not garbage

        # #* Fancier style
        # qtmodern.styles.light(app)
        # # not garbage either
        # self.mw = qtmodern.windows.ModernWindow(window)
        # self.center(self.mw)
        # self.mw.show()

        #* Classic style
        self.center(window)
        window.show()

    def center(self, window):
        qr = window.frameGeometry()
        cp = QApplication.primaryScreen().geometry().center()
        qr.moveCenter(cp)
        window.move(qr.topLeft())

    def shutdown(self):
        for window in self.window_list:
            if window.runner:  # set self.runner=None in your __init__ so it's always defined.
                window.runner.kill()


# yapf: disable

# TODO kill runners on exit. stop conversion from yt_dl
class MainWindow(QMainWindow):
    """Main application window."""
    def __init__(self, window_manager):
        super(MainWindow, self).__init__()

        self.windowManager = window_manager
        self.GUI_preferences_path = str(Path.joinpath(RUNTIME_DIR, 'GUI_preferences.ini'))
        self.GUI_preferences = QtCore.QSettings(self.GUI_preferences_path, QtCore.QSettings.IniFormat)

        #* Object names not to be saved to settings
        self.objects_to_exclude = ["listVideos"]

        #* Async download manager
        self.network_manager = CustomNetworkManager()  # only one instance necessary for the whole app
        self.network_manager.downloaded.connect(self.GlobalClientLoader)
        self.sender_list = []  # prevent gc on sender objects

        #* QGraphicsEffect
        self.widgets_with_hover = []
        # workaround for graphics effect limitation
        self.shadow_effects = {}
        self.shadow_effects_counter = 0

        #* QSettings
        self.config_is_set = 0
        self.save_to_runtimedir = False

        #* Sync status bar label
        self.signal = CustomSignals()
        self.signal.sync_icon.connect(self.add_sync_icon)
        self.label_sync = None

        #* Temporary video downloads folder
        self.temp_dir = tempfile.mkdtemp()
        self.media_download_path=self.temp_dir # TODO user defined
        self.media_download_path=r"D:\Desktop\TEST_DOWNLOADS"
        self.max_video_duration=500
        print(self.temp_dir)

        self.player = QMediaPlayer()
        self.playlist = QMediaPlaylist()
        self.was_paused=False
        self.current_item=None

        self.player.mediaStatusChanged.connect(self.qmp_mediaStatusChanged)
        self.player.stateChanged.connect(self.qmp_stateChanged)
        self.player.positionChanged.connect(self.qmp_positionChanged)
        self.player.volumeChanged.connect(self.qmp_volumeChanged)
        self.player.setVolume(60)

        ##############?##############?##############?##############?
        ##############?##############? UI definition

        self.setObjectName("MainWindow")
        self.setDockNestingEnabled(True)
        id = QtGui.QFontDatabase.addApplicationFont(str(path))
        family = QtGui.QFontDatabase.applicationFontFamilies(id)[0]
        font = QtGui.QFont(family, 9)

        self.centralwidget = QtWidgets.QWidget(self, objectName="centralwidget")
        self.centralwidget.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.setCentralWidget(self.centralwidget)

        self.create_music_controls()

        self.listVideos = QtWidgets.QListWidget(
            self.centralwidget,
            objectName="listVideos",
            currentItemChanged=self.onItemChange,
        )
        self.listVideos.setTabKeyNavigation(False)
        self.listVideos.setContextMenuPolicy(Qt.CustomContextMenu)
        self.listVideos.customContextMenuRequested.connect(self.onListItemRightClick)  # position passed
        self.listVideos.itemClicked.connect(self.onListItemLeftClick)

        #* Expandable section below
        spoiler = Spoiler(title="Settings", ref_parent=self)

        self.gridLayout = QtWidgets.QGridLayout(self.centralwidget, objectName="gridLayout")
        self.gridLayout.addLayout(self.horizontalLayout, 0, 0)
        self.gridLayout.addWidget(self.horizontalSlider, 1, 0)
        self.gridLayout.addWidget(self.listVideos, 2, 0)
        self.gridLayout.addWidget(spoiler, 3, 0)

        self.create_statusbar()

        self.create_toolbar()

        self.create_menubar(font)


        ##############?##############? END UI DEFINITION
        ##############?##############?##############?##############?

        #* Custom effect
        self.applyEffectOnHover(self.horizontalSlider)
        self.applyEffectOnHover(self.listVideos)
        self.applyEffectOnHover(self.playButton)
        self.applyEffectOnHover(self.fastForwardButton)
        self.applyEffectOnHover(self.rewindButton)
        self.applyEffectOnHover(spoiler)

        #* Thread runner
        self.runner = None
        self.threadpool = QtCore.QThreadPool()

        #* Auto restore settings on startup
        self.restore_settings_on_start()

        #* Tray icon
        self.message_is_being_shown = False
        self.createTrayIcon()


        self.signal.add_listitem.connect(self.fill_list_widget)
        self.signal.start_video_download.connect(self.video_downloader)

        # #### Quick view video attributes
        # i = 0
        # for id, video in my_videos.items():
        #     if i >= 3:
        #         break
        #     print('\n'.join("'%s': '%s', " % item for item in vars(video).items()))
        #     print("---------------------------")
        #     i += 1
        # #### END Quick view

        self.resize(1300, 600)

        #TODO add styles to resources file
        self.setCustomStylesheets()

        QtWidgets.QAction("Quit", self).triggered.connect(self.closeEvent)

    def restore_settings_on_start(self):
        if os.path.exists(self.GUI_preferences_path):
            try:
                guirestore(self, self.GUI_preferences)
                self.save_to_runtimedir = True
            except:
                pass
        else:
            with open(self.GUI_preferences_path, 'w') as f:
                guisave(self, self.GUI_preferences, self.objects_to_exclude)
                f.close()

    def create_menubar(self, font):
        self.menuBarTop = QtWidgets.QMenuBar(self, font=font)
        self.menuFile   = QtWidgets.QMenu("&File", self.menuBarTop, font=font)
        self.menuEdit   = QtWidgets.QMenu("&Edit", self.menuBarTop, font=font)
        self.menuHelp   = QtWidgets.QMenu("&Help", self.menuBarTop, font=font)
        self.setMenuBar(self.menuBarTop)
        self.menuBarTop.addAction(self.menuFile.menuAction())
        self.menuBarTop.addAction(self.menuEdit.menuAction())
        self.menuBarTop.addAction(self.menuHelp.menuAction())
        self.actionOpen = QtWidgets.QAction(
            "Open...",
            self,
            shortcut="Ctrl+O",
            icon=QIcon(ICONS.open),
            triggered=self.readFile,
        )
        self.actionSave = QtWidgets.QAction(
            "Save",
            self,
            shortcut="Ctrl+S",
            icon=QIcon(ICONS.save),
            triggered=self.writeFile,
        )
        self.actionSaveAs = QtWidgets.QAction(
            "Save as...",
            self,
            shortcut="Ctrl+Shift+S",
            triggered=self.writeNewFile,
        )
        self.actionExit = QtWidgets.QAction(
            "Exit",
            self,
            shortcut="Esc",
            icon=QIcon(ICONS.exit),
        )
        self.actionEdit = QtWidgets.QAction(
            "Preferences",
            self,
            shortcut="Ctrl+P",
            icon=QIcon(ICONS.settings),
        )
        self.actionAbout = QtWidgets.QAction(
            "About",
            self,
            icon=QIcon(ICONS.about),
            triggered=self.AboutInfo,
        )
        self.actionGitHubHomepage = QtWidgets.QAction(
            "GitHub Homepage",
            self,
            icon=QIcon(ICONS.github),
            triggered=self.GitHubLink,
        )
        self.menuFile.addAction(self.actionOpen)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionSave)
        self.menuFile.addAction(self.actionSaveAs)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionExit)
        self.menuEdit.addAction(self.actionEdit)
        self.menuHelp.addAction(self.actionGitHubHomepage)
        self.menuHelp.addAction(self.actionAbout)

    def create_statusbar(self):
        self.statusbar = QtWidgets.QStatusBar(self)
        self.setStatusBar(self.statusbar)

    def create_toolbar(self):
        self.actionGetFeed = QtWidgets.QAction("Scrape Youtube feed")
        self.actionGetFeed.triggered.connect(lambda: self.startWorker("populate_worker"))
        self.toolBar = QtWidgets.QToolBar(self)
        self.toolBar.addAction(self.actionGetFeed)
        self.addToolBar(QtCore.Qt.TopToolBarArea, self.toolBar)

    def create_music_controls(self):
        size_policy = QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        play_icon = QIcon(ICONS.playback_play_mblue)
        pause_pix = QPixmap(ICONS.playback_pause_mblue)
        # replace with pause icon on button click
        play_icon.addPixmap(pause_pix, QtGui.QIcon.Active, QtGui.QIcon.On)
        self.playButton = QtWidgets.QPushButton(
            "",
            self.centralwidget,
            icon       = play_icon,
            flat       = True,
            checkable  = True,
            iconSize   = QtCore.QSize(48, 48),
            sizePolicy = size_policy,
            styleSheet = "border: 0px",
            clicked    = self.onPlay,
        )
        self.rewindButton = QtWidgets.QPushButton(
            "",
            self.centralwidget,
            icon       = QIcon(ICONS.playback_rew_mblue),
            flat       = True,
            iconSize   = QtCore.QSize(32, 32),
            sizePolicy = size_policy,
            styleSheet = "border: 0px",
            clicked    = self.onRewind,
        )
        self.fastForwardButton = QtWidgets.QPushButton(
            "",
            self.centralwidget,
            icon       = QIcon(ICONS.playback_ff_mblue),
            flat       = True,
            iconSize   = QtCore.QSize(32, 32),
            sizePolicy = size_policy,
            styleSheet = "border: 0px",
            clicked    = self.onFastForward,
        )

        spacerItem = QtWidgets.QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.addItem(spacerItem)
        self.horizontalLayout.addWidget(self.rewindButton)
        self.horizontalLayout.addWidget(self.playButton)
        self.horizontalLayout.addWidget(self.fastForwardButton)
        self.horizontalLayout.addItem(spacerItem)

        self.horizontalSlider = QtWidgets.QSlider(self.centralwidget)
        self.horizontalSlider.setSingleStep(10)
        self.horizontalSlider.setOrientation(QtCore.Qt.Horizontal)
        self.horizontalSlider.setTickPosition(QtWidgets.QSlider.TicksBothSides)
        self.horizontalSlider.setMinimum(0)
        self.horizontalSlider.setMaximum(100)
        self.horizontalSlider.setTracking(False)
        self.horizontalSlider.sliderMoved.connect(self.seekPosition)

    # yapf: enable

    def setCustomStylesheets(self):
        #* FOR A VERTICAL SLIDER - <:vertical>
        self.horizontalSlider.setStyleSheet(
            """
                .QSlider::groove:horizontal {
            background: red;
            position: absolute; 
            /* absolutely position 4px from the left and right of the widget. 
            setting margins on the widget should work too... */
            left: 4px; right: 4px;
            border-radius: 4px 4px 4px 4px ;
        }

        .QSlider::handle:horizontal {
            height: 10px;
            background: #438EC8;
            width: 12px ;
            border-radius: 3px 3px 3px 3px ;
            margin: 0 -4px; /* expand outside the groove */
        }

        .QSlider::add-page:horizontal {
            background: white;
            border-radius: 3px 3px 3px 3px ;
        }

        .QSlider::sub-page:horizontal {
            background: #8AB4F8;
            border-radius: 4px 4px 4px 4px ;
        }"""
        )

    def startWorker(self, worker: str, **kwargs):
        """Start a worker by its arbitrary name."""
        if worker == "populate_worker":
            populate_worker = Worker(self.populate_video_list)
            self.threadpool.start(populate_worker)
        elif worker == "video_download":
            video = kwargs.pop('video')
            if isinstance(video, Video):
                if get_sec(video.duration) < self.max_video_duration:
                    yt_dl_worker = Worker(video.start_download, self.media_download_path)
                    self.threadpool.start(yt_dl_worker)
                else:
                    pass
                    #TODO grey out videos

    def video_downloader(self, video: Video):
        self.startWorker("video_download", video=video)

    def populate_video_list(self):
        """Trigger scraping workflow"""
        self.signal.sync_icon.emit("Loading YouTube data", False)
        json_var = self.get_yt_source_text(from_local_dir=True)
        self.my_videos = self.get_my_videos(json_var)
        self.signal.sync_icon.emit("", True)

    def get_yt_source_text(self, from_local_dir=False, save_to_local_dir=False, last_video: Video = None):
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
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, 'Error', f"Could not find a valid video feed in source: {e}")

        else:
            with open(str(Path.joinpath(RUNTIME_DIR, "downloaded_source.json")), "r", encoding="utf-8") as f:
                json_var = f.read()

        # TODO find last video id in source, else change tab and scroll down
        # until last video date | max videos to download is reached
        if last_video is not None:
            videoId = f'"videoId":"{last_video.id}"'
            if not videoId in json_var:
                pass
            else:
                pass

        #* Optionally save the page's source
        if not from_local_dir and save_to_local_dir:
            with open(str(Path.joinpath(RUNTIME_DIR, "downloaded_source.json")), "a", encoding="utf-8") as f:
                f.write(json_var)

        return json.loads(json_var)

    def get_my_videos(self, json_var):
        """Extract video metadata from feed to a dictionary accessed by video ID
        \nParameters:\n   
        ``json_var`` : ytInitialData variable, containing rendered feed videos data"""

        #* match all rendered video grids and get each video's data
        jsonpath_expr = parse('*..gridRenderer..gridVideoRenderer')
        videos_json = [match.value for match in jsonpath_expr.find(json_var)]

        #* add new metadata as required and edit Video class accordingly
        parse_strings = {
            'id': 'videoId',
            'title': 'title.runs[*].text',
            'author': 'shortBylineText.runs[*].text',
            'author_thumbnail': 'channelThumbnail.thumbnails[*].url',
            'thumbnail': 'thumbnail.thumbnails[*].url',
            'time': 'publishedTimeText.simpleText',
            'duration': 'thumbnailOverlays[*].thumbnailOverlayTimeStatusRenderer.text.simpleText',
        }

        return self.create_video_instances(videos_json, parse_strings)

    def create_video_instances(self, videos_json, parse_strings):
        """Create ``Video`` instances and trigger the 
        loading of ``Video`` into a list widget."""
        my_videos = {}
        videos_parsed = 0
        parsing_limit = 10  # limit videos to show
        for item in videos_json:
            if parsing_limit and videos_parsed >= parsing_limit:
                break
            for video_attr, parse_str in parse_strings.items():
                json_expr = parse(parse_str)  # see jsonpath_ng
                matches = [match.value for match in json_expr.find(item)]
                if not matches:
                    match_attr = ""
                else:
                    match_attr = matches[0]
                    # this assumes id will always be the first key
                    if video_attr == "id":
                        video_id = match_attr
                        my_videos[video_id] = Video(video_id)
                    setattr(my_videos[video_id], video_attr, match_attr)
            videos_parsed += 1
            #* send signal with the current video and fill the list
            self.signal.add_listitem.emit(my_videos[video_id])
            self.signal.start_video_download.emit(my_videos[video_id])
            QApplication.processEvents()  # QRunnable not worth it
        return my_videos

    def fill_list_widget(self, video: Video):
        """Create the item for the list widget, start downloading it's data 
        asynchronously and insert it."""
        item_widget = CustomQWidget(ref_parent=self)

        #* Add own buttons to frame
        # TODO they're linked to ``video`` --> defined here, and not in CustomQWidget
        frameLayout = QHBoxLayout(item_widget.frame)
        frameLayout.setAlignment(QtCore.Qt.AlignTop)

        download_button = CustomImageButton(
            icon=ICONS.cloud_download_lblue,
            icon_on_click=ICONS.cloud_download_white,
            icon_size=20,
            icon_max_size=30,
        )
        self.applyEffectOnHover(download_button)
        frameLayout.addWidget(download_button)

        fav_button = CustomImageButton(
            icon=ICONS.favorite_lblue,
            icon_on_click=ICONS.favorite_white,
            icon_size=20,
            icon_max_size=30,
        )
        self.applyEffectOnHover(fav_button)
        frameLayout.addWidget(fav_button)
        item_widget.frame.setLayout(frameLayout)

        #* keep track of video in list widget and viceversa
        video.item_widget = item_widget
        item_widget.video = video
        item_widget.media_path = os.path.join(self.media_download_path)
        item_widget.video.download_button = download_button
        # item_widget.frame.layout().itemAt() #! incomprehensible later on

        item_widget.setTextUp(video.title)

        author_thumbnail_sender = Sender("author_thumbnail", item_widget)
        # it's not garbage. Else the reply will return a destroyed Sender
        self.sender_list.append(author_thumbnail_sender)
        self.network_manager.startDownload(url=video.author_thumbnail, sender=author_thumbnail_sender)

        vid_thumbnail_sender = Sender("vid_thumbnail", item_widget)
        self.sender_list.append(vid_thumbnail_sender)
        self.network_manager.startDownload(url=video.thumbnail, sender=vid_thumbnail_sender)

        # no need to subclass QListWidgetItem, just the widget (CustomQWidget) set on it
        item = QListWidgetItem(self.listVideos)
        item.setSizeHint(item_widget.sizeHint())
        self.listVideos.addItem(item)
        self.listVideos.setItemWidget(item, item_widget)

    def onListItemLeftClick(self, item: QListWidgetItem):
        """Called when a QListWidget item is clicked."""
        #* Return the rest of list items to their original state
        for i in range(self.listVideos.count()):
            item_i = self.listVideos.item(i)
            widget_i = self.listVideos.itemWidget(item_i)
            item_i.setBackground(QColor(255, 255, 255))
            textUpQLabel = widget_i.textUpQLabel
            textUpQLabel.setGraphicsEffect(None)
            textUpQLabel.setStyleSheet("""color: rgb(70,130,180);""")
            authorQLabel = widget_i.authorQLabel
            self.applyShadowEffect(authorQLabel)
            thumbnailQLabel = widget_i.thumbnailQLabel
            self.applyShadowEffect(thumbnailQLabel)
            frame = widget_i.frame
            self.applyShadowEffect(frame)
            widget_i.color = QtGui.QColor(255, 255, 255)

        #* Format the clicked item
        widget = item.listWidget().itemWidget(item)  # returns a CustomQWidget
        shadow_color = QColor(49, 65, 129)
        self.applyShadowEffect(widget.authorQLabel, color=shadow_color)
        self.applyShadowEffect(widget.thumbnailQLabel, color=shadow_color)
        self.applyShadowEffect(widget.frame, color=shadow_color)
        self.applyShadowEffect(widget.textUpQLabel, color=shadow_color)
        widget.textUpQLabel.setStyleSheet("""
            color: rgb(255,255,255);
        """)
        widget.color = QtGui.QColor(61, 125, 194)

    def onItemChange(self, item, previous_item):
        self.current_item = item
        self.was_paused = self.playButton.isChecked()
        if self.was_paused:
            current_video = self.listVideos.itemWidget(self.current_item).video
            self.playlist.clear()
            if not hasattr(current_video, "download_path"): return
            video_media = QMediaContent(QUrl.fromLocalFile(current_video.download_path))
            self.playlist.addMedia(video_media)
            self.player.play()
            self.played_video = current_video

    def qmp_mediaStatusChanged(self):
        if self.player.mediaStatus() == QMediaPlayer.LoadedMedia and self.playButton.isChecked():
            durationT = self.player.duration()
            self.horizontalSlider.setRange(0, durationT)
            # self.centralWidget().layout().itemAt(0).layout().itemAt(2).widget().setText(
            #     '%d:%02d' % (int(durationT / 60000), int((durationT / 1000) % 60))
            # )
            self.player.play()

    def qmp_stateChanged(self):
        if self.player.state() == QMediaPlayer.StoppedState:
            self.player.stop()

    def qmp_positionChanged(self, position):
        self.horizontalSlider.setValue(position)
        # setText('%d:%02d' % (int(position / 60000), int((position / 1000) % 60)))

    def qmp_volumeChanged(self):
        msg = self.statusBar().currentMessage()
        msg = msg[:-2] + str(self.player.volume())
        self.statusBar().showMessage(msg)

    def seekPosition(self, position):
        sender = self.sender()
        print("in seekposition with sender", sender)
        if isinstance(sender, QSlider):
            if self.player.isSeekable():
                self.player.setPosition(position)

    def onPlay(self, checked):
        """"""
        if not self.current_item: return
        self.was_paused = checked
        print("now playing: ", self.was_paused)
        current_video = self.listVideos.itemWidget(self.current_item).video
        if self.player.mediaStatus() == QMediaPlayer.NoMedia:
            self.played_video = current_video
            if not hasattr(current_video, "download_path"): return
            print("current_video.download_path : ", current_video.download_path)
            video_media = QMediaContent(QUrl.fromLocalFile(current_video.download_path))
            self.playlist.addMedia(video_media)
            if self.playlist.mediaCount() != 0:
                self.player.setPlaylist(self.playlist)
        else:
            if self.played_video != current_video:
                self.playlist.clear()
                video_media = QMediaContent(QUrl.fromLocalFile(current_video.download_path))
                self.playlist.addMedia(video_media)
                self.player.play()
                self.played_video = current_video

        if self.was_paused:
            self.player.play()
        elif not self.was_paused:
            self.player.pause()

    #TODO show the custom frame selection color (same for shortcut)
    def onRewind(self):
        """"""
        if self.listVideos.currentRow() == 0: return
        self.listVideos.setCurrentRow(self.listVideos.currentRow() - 1)

    def onFastForward(self):
        """"""
        if self.listVideos.currentRow() == self.listVideos.count(): return

        self.listVideos.setCurrentRow(self.listVideos.currentRow() + 1)

    def onKeyUp(self):
        """"""

    def onKeyDown(self):
        """"""

    def applyShadowEffect(self, widget: QWidget, color=QColor(50, 50, 50), blur_radius=10, offset=2):
        """Same widget graphic effect instance can't be used more than once
        else it's removed from the first widget. Workaround using a dict:
        
        Notes: when applied to a ``CustomImageButton``, this effect will add a rounded rect 
        background. See 'CustomImageButton_example.png' for reference"""
        self.shadow_effects[self.shadow_effects_counter] = QGraphicsDropShadowEffect(self)
        self.shadow_effects[self.shadow_effects_counter].setBlurRadius(blur_radius)
        self.shadow_effects[self.shadow_effects_counter].setColor(color)
        self.shadow_effects[self.shadow_effects_counter].setOffset(offset)
        widget.setGraphicsEffect(self.shadow_effects[self.shadow_effects_counter])
        self.shadow_effects_counter += 1

    def applyEffectOnHover(self, widget: QWidget):
        """Installs an event filter to display a shadow upon hovering.
        The event filter is a MainWindow. An event filter receives all events 
        that are sent to ``widget``.
        
        Notes: applying this effect to a ``CustomImageButton`` will disable the animation
        and add a rounded rect as with the ``applyShadowEffect`` method.
        """
        widget.installEventFilter(self)
        self.widgets_with_hover.append(widget)

    def GitHubLink(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl('https://github.com/danicc097/Youtube-Feed-Scraper'))

    @QtCore.pyqtSlot(QtCore.QPoint)
    def onListItemRightClick(self, pos):
        menu = QtWidgets.QMenu()
        delete_row = menu.addAction("Remove")
        action = menu.exec_(self.listVideos.viewport().mapToGlobal(pos))
        if action == delete_row:
            item = self.listVideos.itemAt(pos)
            row = self.listVideos.row(item)
            self.listVideos.takeItem(row)

    def writeNewFile(self):  # ? Save as
        """Saves GUI user input to a new config file"""
        self.config_is_set += 1
        self.filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Select where to save the configuration file…",
            str(Path.joinpath(BASEDIR, 'data')),
            'Configuration Files (*.ini)',
            options=QtWidgets.QFileDialog.DontResolveSymlinks
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
                QtWidgets.QMessageBox.critical(self, 'Error', f"Could not save settings: {e}")

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
        self.filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select a configuration file to load…",
            str(RUNTIME_DIR),
            'Configuration Files (*.ini)',
            options=QtWidgets.QFileDialog.DontResolveSymlinks
        )
        #* Invalid file or none
        if self.filename == "":
            QtWidgets.QMessageBox.critical(
                self,
                "Operation aborted",
                "Empty filename or none selected. \n Please try again.",
                QtWidgets.QMessageBox.Ok,
            )
            self.statusBar().showMessage("Select a valid configuration file")
        #* Valid file
        else:
            if self.filename.lower().endswith('.ini'):
                self.config_is_set += 1
                try:
                    self.my_settings = QtCore.QSettings(self.filename, QtCore.QSettings.IniFormat)
                    guirestore(self, self.my_settings)
                    self.statusBar().showMessage(f"Changes now being saved to: {self.filename}")
                    self.setWindowTitle(os.path.basename(self.filename))

                except Exception as e:
                    QtWidgets.QMessageBox.critical(self, 'Error', f"Could not open settings: {e}")
            else:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Invalid file type",
                    "Please select a .ini file.",
                    QtWidgets.QMessageBox.Ok,
                )

    @QtCore.pyqtSlot(str, bool)
    def add_sync_icon(self, label_text: str, remove_icon: bool):
        """Status bar sync label showing ``label_text``."""
        if remove_icon:
            self.statusBar().removeWidget(self.label_sync)
            self.statusBar().removeWidget(self.title)
            self.statusBar().setGeometry(self.statusbar_geo)
            return

        self.statusbar_geo = self.statusBar().geometry()
        self.statusBar().setStyleSheet("border-top-width : 3px;" "border-color: rgb(0, 0, 0);")
        self.img_sync = QPixmap(str(Path.joinpath(BASEDIR, 'data', 'synchronize-icon.png')))
        self.img_sync = self.img_sync.scaled(25, 25, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.label_sync = QLabel(None)
        self.title = QLabel(label_text)
        self.label_sync.setFixedSize(25, 25)
        # self.title.setFixedSize(150, 25)
        self.title.setMinimumHeight(self.label_sync.height())
        self.label_sync.setPixmap(self.img_sync)

        def ellipsis_in_label(label):
            if self.label_counter < self.label_limit:
                text = label.text() + "."
                self.label_counter += 1
            else:
                text = label.text()[:-self.label_limit]
                self.label_counter = 0
            label.setText(text)

        self.label_counter = 0
        self.label_limit = 3
        self.label_timer = QtCore.QTimer()
        self.label_timer.timeout.connect(lambda: ellipsis_in_label(self.title))
        self.label_timer.start(1 * 1000)

        self.statusBar().addPermanentWidget(self.label_sync)
        self.statusBar().addPermanentWidget(self.title)

    def showSuccess(self):
        self.trayIcon.show()
        if not self.hasFocus():
            self.message_is_being_shown = True
            self.trayIcon.showMessage(
                f"RNC data has been loaded!\n", "Click here to start searching.", self.windowManager.app_icon,
                1200 * 1000
            )  # milliseconds default

    def notificationHandler(self):
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.show()
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.show()

    def createTrayIcon(self):
        self.restoreAction = QtWidgets.QAction("&Restore", self, triggered=self.showNormal)
        self.quitAction = QtWidgets.QAction("&Quit", self, triggered=self.close)  # invoke closeEvent
        self.trayIconMenu = QtWidgets.QMenu(self)
        self.trayIconMenu.addAction(self.restoreAction)
        self.trayIconMenu.addAction(self.quitAction)

        self.trayIcon = QSystemTrayIcon(self)
        self.trayIcon.setContextMenu(self.trayIconMenu)
        self.trayIcon.setIcon(QIcon(str(Path.joinpath(BASEDIR, 'data', 'main-icon.png'))))
        self.trayIcon.messageClicked.connect(self.notificationHandler)

    def GlobalClientLoader(self, sender: Sender, byte_array: QByteArray):
        """Handles requests made from a custom ``QNetworkAccessManager``"""
        if sender.sender_name == "vid_thumbnail":
            vid_thumbnail = QPixmap()
            vid_thumbnail.loadFromData(byte_array)
            sender.sender_object.setThumbnail(vid_thumbnail)

        if sender.sender_name == "author_thumbnail":
            sender.sender_object.authorQLabel.set_round_label(byte_array)

    def singleTimer(self, seconds, fn):
        """Single use timer that connects to ``fn`` after ``seconds``"""
        self.time_sync = QtCore.QTimer()
        self.time_sync.timeout.connect(lambda: fn)
        self.time_sync.setSingleShot(True)
        self.time_sync.start(int(seconds) * 1000)

    def AboutInfo(self):
        """Shows license information"""
        # parent is necessary to center msgbox by default
        self.infoScreen = QtWidgets.QMessageBox(self)
        self.infoScreen.setWindowTitle('Legal Information')
        self.infoScreen.setText('This program is licenced under the GNU GPL v3.\t\t')
        self.infoScreen.setInformativeText("The complete license is available below.\t\t")
        try:
            self.infoScreen.setDetailedText(
                open(str(Path.joinpath(BASEDIR.parent, "LICENSE")), "r", encoding="utf-8").read()
            )
        except:
            self.infoScreen.setDetailedText("http://www.gnu.org/licenses/gpl-3.0.en.html")
        self.infoScreen.setWindowModality(Qt.ApplicationModal)
        self.infoScreen.show()

    #####???##################################################
    #####??? EVENTS
    #####???##################################################

    def eventFilter(self, object, event):
        #* apply shadow effect when hovered over
        if isinstance(object, QWidget) and object in self.widgets_with_hover:
            if event.type() == QtCore.QEvent.Enter:
                self.applyShadowEffect(object, color=QColor(16, 47, 151), blur_radius=20, offset=0)
                #? the custom event is overridden by the effect
                if isinstance(object, CustomImageButton):
                    object.enterEvent(event)
                return True
            elif event.type() == QtCore.QEvent.Leave:
                object.setGraphicsEffect(None)
                if isinstance(object, CustomImageButton):
                    object.leaveEvent(event)
        return False

    def changeEvent(self, event):
        #* Hides the system tray icon when the main window is visible, and viceversa.
        if event.type() == QtCore.QEvent.WindowStateChange and self.windowState() and self.isMinimized():
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
        close = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Question, 'Exit', 'Exit application?', parent=self)
        close_reject = close.addButton('No', QtWidgets.QMessageBox.NoRole)
        close_accept = close.addButton('Yes', QtWidgets.QMessageBox.AcceptRole)
        close.exec()  # Necessary for property-based API
        if close.clickedButton() == close_accept:
            self.trayIcon.setVisible(False)
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            # TODO if custom download path and checkbox to delete:
            # shutil.rmtree(self.media_download_path, ignore_errors=True)
            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        #* Control media playing through arrows and spacebar
        if event.key() == Qt.Key_Right:
            self.horizontalSlider.setValue(self.horizontalSlider.value() + 10)
        elif event.key() == Qt.Key_Left:
            self.horizontalSlider.setValue(self.horizontalSlider.value() - 10)
        elif event.key() == Qt.Key_Space:
            #TODO
            self.onPlay(True)
        if event.key() == Qt.Key_Up:
            self.onKeyUp()
        # TODO list widget select previous
        elif event.key() == Qt.Key_Down:
            self.onKeyDown()
        # TODO list widget select next
        else:
            QWidget.keyPressEvent(self, event)

    #####???##################################################
    #####??? END OF MAINWINDOW
    #####???##################################################


#####???##################################################
#####??? INITIALIZE UPON IMPORT
#####???##################################################

app = QtWidgets.QApplication(sys.argv)
app.setStyle('Fusion')
app.setStyleSheet("")
app.setApplicationName("Youtube Scraper")
app_icon = QIcon(str(Path.joinpath(BASEDIR, 'data', 'main-icon.png')))
app.setWindowIcon(app_icon)
path = Path.joinpath(BASEDIR, 'data', 'fonts', 'Fira_Sans', 'FiraSans-Medium.ttf')
id = QtGui.QFontDatabase.addApplicationFont(str(path))
family = QtGui.QFontDatabase.applicationFontFamilies(id)[0]
font = QtGui.QFont(family, 9)
app.setFont(font)
w = NewWindow()  # Instantiate window factory
app.aboutToQuit.connect(w.shutdown)

timer = QtCore.QTimer()
timer.timeout.connect(lambda: None)
timer.start(100)
# apply_stylesheet(app, theme='dark_teal.xml')

sys.exit(app.exec_())
