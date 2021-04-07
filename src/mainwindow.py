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

import pyautogui
import pyperclip
import qtmodern.styles
import qtmodern.windows
from jsonpath_ng import jsonpath
from jsonpath_ng.ext import parse
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import (
    QByteArray, QEasingCurve, QObject, QPoint, QPointF, QPropertyAnimation, QRectF,
    QSequentialAnimationGroup, QSize, Qt, QUrl, pyqtProperty, pyqtSignal, pyqtSlot
)
from PyQt5.QtGui import (
    QBrush, QColor, QFont, QIcon, QImage, QPainter, QPainterPath, QPaintEvent, QPen, QPixmap
)
from PyQt5.QtNetwork import (QNetworkAccessManager, QNetworkReply, QNetworkRequest)
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel,
    QLayout, QListWidgetItem, QMainWindow, QPushButton, QScrollArea, QSizePolicy, QSystemTrayIcon,
    QToolButton, QVBoxLayout, QWidget
)
from youtube_dl import YoutubeDL

from .designer.YoutubeScraper import Ui_MainWindow
from .resources import MyIcons, get_path
from .save_restore import grab_GC, guirestore, guisave

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


class CustomYoutubeDL():
    def __init__(self):
        ydl_opts = {
            'format':
            'bestaudio/best',
            'postprocessors':
            [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'logger':
            MyLogger(),
            'progress_hooks': [self.my_hook],
        }
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download(["yt_video_url"])

        # TODO QRunnable for each video.
        # signal containing URL and temp file path
        # global slot in mainwindow to handle

    def my_hook(self, d):
        if d['status'] == 'finished':
            print('Done downloading, now converting ...')


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


class Video():
    """
    Store video information for ease of use
    """
    def __init__(self, id, title="", time="", author="", thumbnail="", author_thumbnail=""):
        self.id = str(id)
        self.url = "https://www.youtube.com/watch?v=" + self.id
        self.title = str(title)
        self.time = str(time)
        self.author = str(author)
        self.thumbnail = str(thumbnail)
        self.author_thumbnail = str(author_thumbnail)


class Sender(QObject):
    """
    To be used as QNetworkReply and QNetworkRequest ``originatingObject``.
    """
    def __init__(self, sender_name, sender_object):
        super(Sender, self).__init__()
        self._sender_name = sender_name
        self._sender_object = sender_object

    @property
    def sender_name(self):
        return self._sender_name

    @sender_name.setter
    def sender_name(self, name: str):
        if self.sender_name == name:
            return
        self.sender_name = name

    @property
    def sender_object(self):
        return self._sender_object

    @sender_object.setter
    def sender_object(self, object: QObject):
        if self.sender_object == object:
            return
        self.sender_object = object


class CustomNetworkManager(QObject):
    """QNetworkAccessManager wrapper to handle async downloads. \n
    Usage:
    ------
        ``foo = CustomNetworkManager()`` \n
        ``foo.downloaded.connect(lambda: GlobalClientLoader())`` \n
        original sender and data are passed 
        
        ``foo.startDownload(QUrl(my_url), sender)`` 
        execution continues. The download is tied to ``sender``.
        
        in main thread:
        ``def GlobalClientLoader(sender,byte_array):`` \n
            ``sender.sender_name == "some_name":``
               ``do_stuff(sender,byte_array)``
    """
    downloaded = pyqtSignal(QObject, QByteArray)

    def __init__(self):
        super(CustomNetworkManager, self).__init__()  # init QObject
        self._manager = QNetworkAccessManager(finished=self._downloadFinished)

    @pyqtSlot(QNetworkReply)
    def _downloadFinished(self, reply: QNetworkReply):
        """Handle signal 'finished'.  A network request has finished."""
        error = reply.error()
        sender = reply.request().originatingObject()

        if error == QNetworkReply.NoError:
            _downloadedData = reply.readAll()
            reply.deleteLater()  # schedule as per docs
            self.downloaded.emit(sender, _downloadedData)
        else:
            print("[INFO] Error: {}".format(reply.errorString()))

    def startDownload(self, url: str, sender: Sender):
        """Use in main application to start a download from ``url`` for
        a given object ``sender``."""
        request = QNetworkRequest(QUrl(url))
        request.setOriginatingObject(sender)  # keep track of download issuer
        self._manager.get(request)


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

        #* Async download manager
        self.network_manager = CustomNetworkManager(
        )  # only one instance necessary for the whole app
        self.network_manager.downloaded.connect(
            lambda sender, byte_array: self.GlobalClientLoader(sender, byte_array)
        )
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

        self.signal.add_listitem.connect(self.fill_list_widget)

        self.icons = MyIcons(BASEDIR)

        self.actionPLAY.setFlat(True)
        play_icon = QIcon(self.icons.playback_play_mblue)
        pause_icon = QPixmap(self.icons.playback_pause_mblue)
        # replace with pause icon on button click
        play_icon.addPixmap(pause_icon, QtGui.QIcon.Active, QtGui.QIcon.On)
        self.actionPLAY.setIcon(play_icon)
        self.actionPLAY.setIconSize(QtCore.QSize(48, 48))
        self.actionFF.setFlat(True)
        self.actionFF.setIcon(QIcon(self.icons.playback_ff_mblue))
        self.actionFF.setIconSize(QtCore.QSize(32, 32))

        self.actionREW.setFlat(True)
        self.actionREW.setIcon(QIcon(self.icons.playback_rew_mblue))
        self.actionREW.setIconSize(QtCore.QSize(32, 32))

        self.applyShadowEffect(
            self.horizontalSlider, color=QColor(16, 47, 151), blur_radius=20, offset=0
        )

        self.applyEffectOnHover(self.actionPLAY)
        self.applyEffectOnHover(self.actionFF)
        self.applyEffectOnHover(self.actionREW)

        self.actionPLAY.clicked.connect(self.onPlay)

        self.actionSave.setIcon(QIcon(self.icons.save))
        self.actionOpen.setIcon(QIcon(self.icons.open))
        self.actionAbout.setIcon(QIcon(self.icons.about))
        self.actionEdit.setIcon(QIcon(self.icons.settings))
        self.actionExit.setIcon(QIcon(self.icons.exit))
        self.actionGitHub_Homepage.setIcon(QIcon(self.icons.github))

        # Thread runner
        self.runner = None
        self.threadpool = QtCore.QThreadPool()

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

        self.actionGitHub_Homepage.triggered.connect(self.GitHubLink)
        self.actionOpen.triggered.connect(self.readFile)
        self.actionSave.triggered.connect(self.writeFile)
        self.actionSave_as.triggered.connect(self.writeNewFile)
        self.actionAbout.triggered.connect(self.AboutInfo)

        # self.horizontalHeader.sectionClicked.connect(self.on_view_horizontalHeader_sectionClicked)
        self.listWidgetVideos.setContextMenuPolicy(Qt.CustomContextMenu)
        self.listWidgetVideos.itemClicked.connect(self.on_list_item_left_click)  # item passed

        self.listWidgetVideos.customContextMenuRequested.connect(
            self.on_list_item_right_click
        )  # position passed

        #* Tray icon
        self.message_is_being_shown = False
        self.createTrayIcon()
        self.trayIcon.setIcon(QIcon(str(Path.joinpath(BASEDIR, 'data', 'main-icon.png'))))
        self.trayIcon.messageClicked.connect(self.notification_handler)

        # #### Quick view video attributes
        # i = 0
        # for id, video in my_videos.items():
        #     if i >= 3:
        #         break
        #     print('\n'.join("'%s': '%s', " % item for item in vars(video).items()))
        #     print("---------------------------")
        #     i += 1
        # #### END Quick view

        self.actionGetFeed.triggered.connect(lambda: self.start_worker("populate_worker"))

        #* Expandable section below
        spoiler = Spoiler(title="Settings", ref_parent=self)
        self.applyEffectOnHover(spoiler)
        self.gridLayout.addWidget(spoiler)

        self.resize(1300, 600)

        #TEST FRAME TODO
        #TEST FRAME TODO
        #TEST FRAME TODO

        self.frame = CustomFrame()

        frameLayout = QHBoxLayout(self.frame)
        frameLayout.setAlignment(Qt.AlignVCenter)

        download_button = CustomImageButton(
            icon=self.icons.cloud_download_lblue,
            icon_on_click=self.icons.cloud_download_white,
            icon_size=20,
            icon_max_size=30,
        )
        # self.applyEffectOnHover(download_button)
        frameLayout.addWidget(download_button)
        fav_button = CustomImageButton(
            icon=self.icons.favorite_lblue,
            icon_on_click=self.icons.favorite_white,
            icon_size=20,
            icon_max_size=30,
        )
        # self.applyEffectOnHover(fav_button)
        frameLayout.addWidget(fav_button)
        self.frame.setLayout(frameLayout)

        self.gridLayout.addWidget(self.frame)

        QtWidgets.QAction("Quit", self).triggered.connect(self.closeEvent)

    def start_worker(self, worker: str):
        if worker == "populate_worker":
            populate_worker = Worker(self.populate_video_list)
            self.threadpool.start(populate_worker)

    def populate_video_list(self):
        """Trigger scraping workflow"""
        self.signal.sync_icon.emit("Loading YouTube data", False)
        json_var = self.get_yt_source_text(from_local_dir=True)
        self.my_videos = self.get_my_videos(json_var)
        self.signal.sync_icon.emit("", True)

    def get_yt_source_text(
        self, from_local_dir=False, save_to_local_dir=False, last_video: Video = None
    ):
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
                json_var = re.findall(r'ytInitialData = (.*?);', source,
                                      re.DOTALL | re.MULTILINE)[0]
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, 'Error', f"Could not find a valid video feed in source: {e}"
                )

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

    def get_my_videos(self, json_var):
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
            self.signal.add_listitem.emit(my_videos[video_id])
            QApplication.processEvents()

        return my_videos

    def fill_list_widget(self, video: Video):
        item_widget = CustomQWidget(ref_parent=self)

        frameLayout = QHBoxLayout(item_widget.frame)
        frameLayout.setAlignment(QtCore.Qt.AlignTop)

        download_button = CustomImageButton(
            icon=self.icons.cloud_download_lblue,
            icon_on_click=self.icons.cloud_download_white,
            icon_size=20,
            icon_max_size=30,
        )
        # self.applyEffectOnHover(download_button)
        frameLayout.addWidget(download_button)
        fav_button = CustomImageButton(
            icon=self.icons.favorite_lblue,
            icon_on_click=self.icons.favorite_white,
            icon_size=20,
            icon_max_size=30,
        )
        # self.applyEffectOnHover(fav_button)
        frameLayout.addWidget(fav_button)
        item_widget.frame.setLayout(frameLayout)

        author_thumbnail_sender = Sender("author_thumbnail", item_widget)
        # it's not garbage. Else the reply will return a destroyed Sender
        self.sender_list.append(author_thumbnail_sender)
        self.network_manager.startDownload(
            url=video.author_thumbnail, sender=author_thumbnail_sender
        )

        item_widget.setTextUp(video.title)

        vid_thumbnail_sender = Sender("vid_thumbnail", item_widget)
        # it's not garbage. Else the reply will return a destroyed Sender
        self.sender_list.append(vid_thumbnail_sender)
        url = video.thumbnail
        self.network_manager.startDownload(url, vid_thumbnail_sender)

        # no need to subclass QListWidgetItem, just the widget set on it
        item = QListWidgetItem(self.listWidgetVideos)
        item.setSizeHint(item_widget.sizeHint())
        self.listWidgetVideos.addItem(item)
        self.listWidgetVideos.setItemWidget(item, item_widget)

    def on_list_item_left_click(self, item: QListWidgetItem):
        """Called when a QListWidget item is clicked"""
        self.list_requires_painter = True
        widget = item.listWidget().itemWidget(item)
        # return rest of list items to original state
        for i in range(self.listWidgetVideos.count()):
            item_i = self.listWidgetVideos.item(i)
            widget_i = self.listWidgetVideos.itemWidget(item_i)
            item_i.setBackground(QColor(237, 237, 237))
            textUpQLabel = widget_i.textUpQLabel
            textUpQLabel.setGraphicsEffect(None)
            textUpQLabel.setStyleSheet("""color: rgb(70,130,180);""")
            authorQLabel = widget_i.authorQLabel
            self.applyShadowEffect(authorQLabel)
            thumbnailQLabel = widget_i.thumbnailQLabel
            self.applyShadowEffect(thumbnailQLabel)
            frame = widget_i.frame
            self.applyShadowEffect(frame)
            widget_i.color = QtGui.QColor(235, 235, 235)

        shadow_color = QColor(49, 65, 129)
        self.applyShadowEffect(widget.authorQLabel, color=shadow_color)
        self.applyShadowEffect(widget.thumbnailQLabel, color=shadow_color)
        self.applyShadowEffect(widget.frame, color=shadow_color)
        self.applyShadowEffect(widget.textUpQLabel, color=shadow_color)
        widget.textUpQLabel.setStyleSheet("""
            color: rgb(250,250,250);
        """)
        widget.color = QtGui.QColor(61, 125, 194)

    def singleTimer(self, seconds, fn):
        """Single use timer that connects to ``fn`` after ``seconds``"""
        self.time_sync = QtCore.QTimer()
        self.time_sync.timeout.connect(lambda: fn)
        self.time_sync.setSingleShot(True)
        self.time_sync.start(int(seconds) * 1000)

    def AboutInfo(self):
        """Shows license information"""
        # parent is necessary to center by default
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

    def onPlay(self):
        """"""

    def applyShadowEffect(
        self, widget: QWidget, color=QColor(50, 50, 50), blur_radius=10, offset=2
    ):
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
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl('https://github.com/danicc097/Youtube-Feed-Scraper')
        )

    @QtCore.pyqtSlot(QtCore.QPoint)
    def on_list_item_right_click(self, pos):
        menu = QtWidgets.QMenu()
        delete_row = menu.addAction("Remove")
        action = menu.exec_(self.listWidgetVideos.viewport().mapToGlobal(pos))
        if action == delete_row:
            item = self.listWidgetVideos.itemAt(pos)
            row = self.listWidgetVideos.row(item)
            self.listWidgetVideos.takeItem(row)

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
                f"RNC data has been loaded!\n", "Click here to start searching.",
                self.windowManager.app_icon, 1200 * 1000
            )  # milliseconds default

    def notification_handler(self):
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.show()
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.show()

    def createTrayIcon(self):
        self.restoreAction = QtWidgets.QAction("&Restore", self, triggered=self.showNormal)
        self.quitAction = QtWidgets.QAction(
            "&Quit", self, triggered=QtWidgets.QApplication.instance().quit
        )
        self.trayIconMenu = QtWidgets.QMenu(self)
        self.trayIconMenu.addAction(self.restoreAction)
        self.trayIconMenu.addAction(self.quitAction)

        self.trayIcon = QSystemTrayIcon(self)
        self.trayIcon.setContextMenu(self.trayIconMenu)

    def GlobalClientLoader(self, sender: Sender, byte_array: QByteArray):
        """Handles requests made from a custom ``QNetworkAccessManager``"""

        if sender.sender_name == "vid_thumbnail":
            # thumbnail image
            vid_thumbnail = QImage()
            vid_thumbnail.loadFromData(byte_array)
            sender.sender_object.setIcon(vid_thumbnail)

        elif sender.sender_name == "author_thumbnail":
            sender.sender_object.authorQLabel.set_round_label(byte_array)

    #######################################################
    ##### EVENTS
    #######################################################

    def eventFilter(self, object, event):
        #* apply shadow effect when hovered over
        if isinstance(object, QWidget) and object in self.widgets_with_hover:
            if event.type() == QtCore.QEvent.Enter:
                self.applyShadowEffect(object, color=QColor(16, 47, 151), blur_radius=20, offset=0)

                return True
            elif event.type() == QtCore.QEvent.Leave:
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
        close = QtWidgets.QMessageBox(
            QtWidgets.QMessageBox.Question, 'Exit', 'Exit application?', parent=self
        )
        close_reject = close.addButton('No', QtWidgets.QMessageBox.NoRole)
        close_accept = close.addButton('Yes', QtWidgets.QMessageBox.AcceptRole)
        close.exec()  # Necessary for property-based API
        if close.clickedButton() == close_accept:
            self.trayIcon.setVisible(False)
            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Right:
            self.horizontalSlider.setValue(self.horizontalSlider.value() + 10)
        elif event.key() == Qt.Key_Left:
            self.horizontalSlider.setValue(self.horizontalSlider.value() - 10)
        elif event.key() == Qt.Key_Space:
            pass
        # TODO play
        if event.key() == Qt.Key_Up:
            pass
        # TODO list widget select previous
        elif event.key() == Qt.Key_Down:
            pass
        # TODO list widget select next
        else:
            QWidget.keyPressEvent(self, event)


#######################################################
#######################################################
##### END OF MAINWINDOW
#######################################################
#######################################################

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
        toggleButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toggleButton.setArrowType(Qt.RightArrow)
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
        mainLayout.addWidget(self.toggleButton, row, 0, 1, 1, Qt.AlignLeft)
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
            arrow_type = Qt.DownArrow if checked else Qt.RightArrow
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


class CustomFrame(QFrame):
    def __init__(self, parent=None, ref_parent=None):
        super(QFrame, self).__init__(parent)
        self.border_radius = 6
        self.setStyleSheet(
            "color: rgb(237, 237, 237);"
            "background-color: rgb(237, 237, 237);"
            "text-align: center;"
            f"border-radius: {self.border_radius}px {self.border_radius}px {self.border_radius}px {self.border_radius}px;"
            "padding: 0px;"
        )
        # self.setFixedSize(200, 30)

    def paintEvent(self, event):
        #* draw decorative line between border radius centers
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.HighQualityAntialiasing, True)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
        brush_width = 3
        width_offset = 4
        height_offset = self.border_radius
        pen = QtGui.QPen(QColor(67, 142, 200), brush_width)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(
            width_offset + brush_width / 2,
            height_offset,
            width_offset + brush_width / 2,
            self.height() - height_offset,
        )


class CustomVerticalFrame(QFrame):
    def __init__(self, parent=None, ref_parent=None):
        super(QFrame, self).__init__(parent)
        self.border_radius = 6
        self.setStyleSheet(
            "color: rgb(237, 237, 237);"
            "background-color: rgb(237, 237, 237);"
            "text-align: center;"
            # "border-style: solid;"
            # "border-width: 0px 0px 0px 2px;"
            "border-color: white white white rgb(67, 142, 200);"
            f"border-radius: {self.border_radius}px {self.border_radius}px {self.border_radius}px {self.border_radius}px;"
            "padding: 0px;"
        )
        # self.setFixedWidth(200)

    def paintEvent(self, event):
        #* draw decorative line between border radius centers
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.HighQualityAntialiasing, True)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
        brush_width = 3
        width_offset = 4
        height_offset = self.border_radius
        pen = QtGui.QPen(QColor(67, 142, 200), brush_width)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(
            width_offset + brush_width / 2,
            height_offset,
            width_offset + brush_width / 2,
            self.height() - height_offset,
        )


class CustomQWidget(QWidget):
    def __init__(self, parent=None, ref_parent=None, base_color=QtGui.QColor(235, 235, 235)):
        super().__init__(parent)
        self.ref_parent = ref_parent
        self.shadow_effects = {}
        self.shadow_effects_counter = 0

        self.textUpQLabel = QLabel()
        font = QFont()
        font.setPointSize(12)
        self.textUpQLabel.setFont(font)

        base_size = 40
        border_width = 0
        self.authorQLabel = RoundLabelImage(
            size=base_size, border_width=border_width, border_color=QtGui.QColor(20, 60, 186)
        )

        self.frame = CustomFrame()

        self.textQVBoxLayout = QVBoxLayout()
        self.textQVBoxLayout.addWidget(self.textUpQLabel)
        self.textQVBoxLayout.addWidget(self.authorQLabel)

        self.allQGrid = QGridLayout()
        # icon will be set later, if a reply is received
        self.thumbnailQLabel = QLabel()
        self.thumbnailQLabel.setFixedWidth(140)
        self.allQGrid.addWidget(self.thumbnailQLabel, 0, 0, 2, 1)
        self.allQGrid.addLayout(self.textQVBoxLayout, 0, 1, 2, 1, Qt.AlignLeft)
        self.allQGrid.addWidget(self.frame, 1, 2, 1, 1, Qt.AlignRight)
        self.setLayout(self.allQGrid)
        self.textUpQLabel.setStyleSheet("""
            color: rgb(70,130,180);
        """)

        self.applyShadowEffect(self.authorQLabel)
        self.applyShadowEffect(self.frame)
        self.applyShadowEffect(self.thumbnailQLabel)

        self._color = base_color

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, color):
        if self.color == color:
            return
        self._color = color
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.HighQualityAntialiasing, True)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
        rect = QtCore.QRectF(self.rect())
        painter_path = QtGui.QPainterPath()
        border_radius = 20
        painter_path.addRoundedRect(rect, border_radius, border_radius)
        painter.setOpacity(0.4)  # before filling
        painter.fillPath(painter_path, QtGui.QBrush(self.color))
        painter.setPen(Qt.NoPen)
        painter.drawPath(painter_path)
        painter.setClipPath(painter_path)

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
            QSizePolicy(QSizePolicy.Minimum, QSizePolicy.MinimumExpanding)
        )

    def setIcon(self, imagePath):
        #TODO BREAKS ALIGNMENT IN CUSTOM FRAME
        img = QPixmap(imagePath)
        # important to use a SmoothTransformation
        thumbnail_width = self.thumbnailQLabel.width()
        img = img.scaledToWidth(thumbnail_width, Qt.SmoothTransformation)
        self.thumbnailQLabel.setPixmap(img)
        self.thumbnailQLabel.setAlignment(Qt.AlignTop)
        self.thumbnailQLabel.setContentsMargins(0, 0, 20, 0)
        self.thumbnailQLabel.setSizePolicy(QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum))
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setColor(QtGui.QColor(50, 50, 50))
        shadow.setOffset(2)
        self.thumbnailQLabel.setGraphicsEffect(shadow)


class RoundLabelImage(QLabel):
    """Based on:
    https://stackoverflow.com/questions/50819033/qlabel-with-image-in-round-shape/50821539"""
    def __init__(self, path="", size=50, border_width=0, border_color=None, antialiasing=True):
        super().__init__()
        self._size = size
        self._border_width = border_width
        self._border_color = border_color
        self._antialiasing = antialiasing
        self.setFixedSize(size, size)

        if path != "":
            self.set_round_label(from_local_path=True)

    def set_round_label(self, data: QByteArray = None, from_local_path=False):
        if from_local_path:
            self.source = QPixmap(path)
        else:
            self.source = QPixmap()
            self.source.loadFromData(data)
        pixmap_size = self._size - self._border_width * 2
        p = self.source.scaled(
            pixmap_size, pixmap_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        self.target = QPixmap(self.size())
        self.target.fill(Qt.transparent)

        painter = QPainter(self.target)
        if self._antialiasing:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        rect = QtCore.QRectF(self.rect())
        if self._border_width:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QtGui.QColor(self._border_color))
            painter.drawEllipse(rect)
            rect.adjust(
                self._border_width, self._border_width, -self._border_width, -self._border_width
            )

        painter_path = QPainterPath()
        painter_path.addEllipse(rect)
        painter.setClipPath(painter_path)

        painter.drawPixmap(self._border_width, self._border_width, p)
        painter.end()  # must be called if there are multiple painters
        painter = None
        self.setPixmap(self.target)


class AnimatedToggle(QCheckBox):
    """Based on https://www.learnpyqt.com/tutorials/qpropertyanimation/"""
    _transparent_pen = QPen(Qt.transparent)
    _light_grey_pen = QPen(Qt.lightGray)

    def __init__(
        self,
        parent=None,
        bar_color=Qt.gray,
        checked_color="#00B0FF",
        handle_color=Qt.white,
        pulse_unchecked_color="#44999999",
        pulse_checked_color="#4400B0EE"
    ):
        super().__init__(parent)

        # Save our properties on the object via self, so we can access them later
        # in the paintEvent.
        self._bar_brush = QBrush(bar_color)
        self._bar_checked_brush = QBrush(QColor(checked_color).lighter())

        self._handle_brush = QBrush(handle_color)
        self._handle_checked_brush = QBrush(QColor(checked_color))

        self._pulse_unchecked_animation = QBrush(QColor(pulse_unchecked_color))
        self._pulse_checked_animation = QBrush(QColor(pulse_checked_color))

        # Setup the rest of the widget.
        self.setContentsMargins(8, 0, 8, 0)
        self._handle_position = 0

        self._pulse_radius = 0

        self.animation = QPropertyAnimation(self, b"handle_position", self)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.setDuration(200)  # time in ms

        self.pulse_anim = QPropertyAnimation(self, b"pulse_radius", self)
        self.pulse_anim.setDuration(350)  # time in ms
        self.pulse_anim.setStartValue(10)
        self.pulse_anim.setEndValue(20)

        self.animations_group = QSequentialAnimationGroup()
        self.animations_group.addAnimation(self.animation)
        self.animations_group.addAnimation(self.pulse_anim)

        self.stateChanged.connect(self.setup_animation)

    def sizeHint(self):
        return QSize(58, 45)

    def hitButton(self, pos: QPoint):
        return self.contentsRect().contains(pos)

    @pyqtSlot(int)
    def setup_animation(self, value):
        self.animations_group.stop()
        if value:
            self.animation.setEndValue(1)
        else:
            self.animation.setEndValue(0)
        self.animations_group.start()

    def paintEvent(self, e: QPaintEvent):

        contRect = self.contentsRect()
        handleRadius = round(0.24 * contRect.height())

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        p.setPen(self._transparent_pen)
        barRect = QRectF(0, 0, contRect.width() - handleRadius, 0.40 * contRect.height())
        barRect.moveCenter(contRect.center())
        rounding = barRect.height() / 2

        # the handle will move along this line
        trailLength = contRect.width() - 2 * handleRadius

        xPos = contRect.x() + handleRadius + trailLength * self._handle_position

        if self.pulse_anim.state() == QPropertyAnimation.Running:
            p.setBrush(
                self._pulse_checked_animation if self.isChecked() else self.
                _pulse_unchecked_animation
            )
            p.drawEllipse(
                QPointF(xPos,
                        barRect.center().y()), self._pulse_radius, self._pulse_radius
            )

        if self.isChecked():
            p.setBrush(self._bar_checked_brush)
            p.drawRoundedRect(barRect, rounding, rounding)
            p.setBrush(self._handle_checked_brush)

        else:
            p.setBrush(self._bar_brush)
            p.drawRoundedRect(barRect, rounding, rounding)
            p.setPen(self._light_grey_pen)
            p.setBrush(self._handle_brush)

        p.drawEllipse(QPointF(xPos, barRect.center().y()), handleRadius, handleRadius)

        p.end()

    @pyqtProperty(float)
    def handle_position(self):
        return self._handle_position

    @handle_position.setter
    def handle_position(self, pos):
        """change the property
        we need to trigger QWidget.update() method, either by:
            1- calling it here [ what we doing ].
            2- connecting the QPropertyAnimation.valueChanged() signal to it.
        """
        self._handle_position = pos
        self.update()

    @pyqtProperty(float)
    def pulse_radius(self):
        return self._pulse_radius

    @pulse_radius.setter
    def pulse_radius(self, pos):
        self._pulse_radius = pos
        self.update()


class CustomImageButton(QPushButton):
    """Replaces the button frame with an image and custom animation. 
    Same principle applies to ``QLabel``, etc.\n
    Parameters
    ----------
    ``icon_size`` : in pixels.
    ``icon_max_size`` : in pixels.
    ``icon`` : path to default icon.
    ``icon_on_click`` : path to icon for ``mousePress`` event.
    """
    def __init__(
        self,
        parent=None,
        icon_size: int = 30,
        icon_max_size: int = None,
        icon: str = None,
        icon_on_click: str = None,
    ):
        super().__init__(parent)

        self._size = icon_size
        self._max_size = icon_max_size if icon_max_size is not None else icon_size
        self._icon = QtGui.QIcon(icon)
        self._icon_on_click = QtGui.QIcon(icon_on_click)

        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.setSizePolicy(sizePolicy)

        self.setStyleSheet("border: none;" "margin: 0px;" "padding: 0px;")

        self.setIcon(self._icon)
        self.setIconSize(QSize(self._size, self._size))
        self.setFixedSize(self._max_size, self._max_size)  # png size -> max size possible

        self._animation = QtCore.QVariantAnimation(
            self,
            startValue=1.0,
            endValue=1.1,
            duration=1000,
            valueChanged=self.on_valueChanged,
        )

    def start_animation(self):
        if self._animation.state() != QtCore.QAbstractAnimation.Running:
            self._animation.start()

    def stop_animation(self):
        if self._animation.state() == QtCore.QAbstractAnimation.Running:
            self._animation.stop()

    @QtCore.pyqtSlot(QtCore.QVariant)
    def on_valueChanged(self, value):
        icon_size = self.iconSize().width()
        if icon_size < self._max_size:
            self.setIconSize(self.iconSize() * value)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.setIcon(self._icon_on_click)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.setIcon(self._icon)

    def enterEvent(self, event):
        self.start_animation()

    def leaveEvent(self, event):
        self.stop_animation()
        self.setIconSize(QSize(self._size, self._size))


class CustomSignals(QtCore.QObject):
    """ Why a whole new class? See here: 
    https://stackoverflow.com/a/25930966/2441026 """
    no_args = QtCore.pyqtSignal()
    sync_icon = QtCore.pyqtSignal(str, bool)
    add_listitem = QtCore.pyqtSignal(Video)


#########################################################################
#########################################################################
##### INITIALIZE UPON IMPORT
#########################################################################
#########################################################################

app = QtWidgets.QApplication(sys.argv)
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
# apply_stylesheet(app, theme='dark_teal.xml')

sys.exit(app.exec_())
