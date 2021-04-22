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

import ctypes
import os
import shutil
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

import qtmodern.styles
import qtmodern.windows
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import (QByteArray, Qt, QUrl)
from PyQt5.QtGui import (QColor, QFont, QIcon, QPixmap)
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer, QMediaPlaylist
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox,
                             QGraphicsDropShadowEffect, QGridLayout,
                             QHBoxLayout, QLabel, QLayout, QLineEdit,
                             QListWidget, QListWidgetItem, QMainWindow, QSizePolicy, QSlider, QSpinBox,
                             QSystemTrayIcon, QVBoxLayout,
                             QWidget)

from .custom_widgets import (CustomFrame, CustomImageButton,
                             CustomQWidget, CustomVerticalFrame, Notification,
                             RoundLabelImage, Spoiler, CustomDateEdit, CustomListWidget)
from .networking import CustomNetworkManager, Sender
from .custom_threading import Worker, WorkerSignals
from .resources import MyIcons, get_path, get_sec
from .save_restore import guirestore, guisave
from .youtube_scraper import get_videos_from_feed,Video

# if __debug__:
#     print("IN DEBUG MODE\n"*10)

BASEDIR = get_path(Path(__file__).parent)

basis = sys.executable if hasattr(sys, 'frozen') else sys.argv[0]
RUNTIME_DIR = Path(os.path.split(basis)[0])

#* Fix qtmodern stylesheets in runtime (plus spec file edit)
root = Path()
if getattr(sys, 'frozen', False):
    root = Path(sys._MEIPASS)
    qtmodern.styles._STYLESHEET = root / 'qtmodern/style.qss'
    qtmodern.windows._FL_STYLESHEET = root / 'qtmodern/frameless.qss'

ICONS = MyIcons(BASEDIR)

#* Enable icon on Windows taskbar
if sys.platform == 'win32':
    myappid = u'Youtube Scraper'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

print(f"BASEDIR is {BASEDIR}")
print(f"RUNTIME_DIR is {RUNTIME_DIR}")

class CustomSignals(QtCore.QObject):
    """
    New signals should only be defined in sub-classes of QObject.
    """
    no_args = QtCore.pyqtSignal()
    sync_icon = QtCore.pyqtSignal(str, bool)
    add_listitem = QtCore.pyqtSignal(Video)
    start_video_download = QtCore.pyqtSignal(Video)


class NewWindow(QMainWindow):
    """
    MainWindow factory.
    """
    def __init__(self):
        super().__init__()
        self.window_list = []
        self._add_new_window()

    def _add_new_window(self):
        """
        Creates new MainWindow instance.
        """
        self.app_icon = QIcon(str(Path.joinpath(BASEDIR, 'data', 'main_icon.png')))
        window = MainWindow(self)
        window.setWindowTitle("Youtube Scraper")
        app.setWindowIcon(self.app_icon)
        window.setWindowIcon(self.app_icon)
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
        """
        Center a QMainWindow in the primary screen.
        """
        window_rect = window.frameGeometry()
        center_point = QApplication.primaryScreen().geometry().center()
        window_rect.moveCenter(center_point)
        window.move(window_rect.topLeft())

    def shutdown(self):
        """
        Stop all QRunnables on app exit.
        """
        for window in self.window_list:
            if len(window.runners) > 0:
                #TODO not implemented in class
                for runner in window.runners: runner.kill()

# TODO kill runners on exit. stop conversion from yt_dl
class MainWindow(QMainWindow):
    """
    Main application window.
    """
    def __init__(self, window_manager):
        super(MainWindow, self).__init__()

        self.window_manager = window_manager

        #* User settings
        self.GUI_preferences_path = str(Path.joinpath(RUNTIME_DIR, 'GUI_preferences.ini'))
        #! CRUCIAL set objectNames, else QSettings::setValue: Empty key passed
        self.my_settings = QtCore.QSettings(self.GUI_preferences_path, QtCore.QSettings.IniFormat)
        # Object names not to be saved to settings
        self.objects_to_exclude = ["listVideos"]

        #* Async download manager
        self.network_manager = CustomNetworkManager()  # only one instance necessary for the whole app
        self.network_manager.downloaded.connect(self.global_client_loader)
        self.sender_list = []  # prevent gc on sender objects

        #* QGraphicsEffect
        self.widgets_with_hover = []
        # workaround for graphics effect limitation
        self.shadow_effects = {}
        self.shadow_effects_counter = 0

        #* QSettings
        self.config_is_set = 0
        self.save_to_runtimedir = False

        self.signal = CustomSignals()
        self.signal.add_listitem.connect(self.fill_list_widget)
        self.signal.start_video_download.connect(self.video_downloader)
        #* Sync status bar label
        self.signal.sync_icon.connect(self.add_sync_icon)
        self.label_sync = None

        #* Temporary video downloads folder
        self.temp_dir = tempfile.mkdtemp()
        self.media_download_path=self.temp_dir
        self.max_video_duration=500
        print(self.temp_dir)

        ##############?##############?##############?##############?
        ##############?##############? UI definition

        self.resize(1300, 600)
        self.setObjectName("MainWindow")
        self.setDockNestingEnabled(True)
        id = QtGui.QFontDatabase.addApplicationFont(str(path))
        family = QtGui.QFontDatabase.applicationFontFamilies(id)[0]
        font = QtGui.QFont(family, 9)
        self.my_font = font

        self.centralwidget = QtWidgets.QWidget(self, objectName="centralwidget")
        self.centralwidget.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.setCentralWidget(self.centralwidget)

        self._create_music_controls()

        self._create_video_list()

        self._create_spoiler_section(font=font)

        self._create_statusbar()

        self._create_toolbar()

        self._create_menubar(font)

        self.gridLayout = QtWidgets.QGridLayout(self.centralwidget, objectName="gridLayout")
        self.gridLayout.addLayout(self.horizontalLayout, 0, 0)
        self.gridLayout.addWidget(self.horizontalSlider, 1, 0)
        self.gridLayout.addWidget(self.listVideos, 2, 0)
        self.gridLayout.addWidget(self.spoiler, 3, 0)

        ##############?##############? END UI DEFINITION
        ##############?##############?##############?##############?

        #* Custom effect
        self.apply_effect_on_hover(self.horizontalSlider)
        self.apply_effect_on_hover(self.listVideos)
        self.apply_effect_on_hover(self.playButton)
        self.apply_effect_on_hover(self.fastForwardButton)
        self.apply_effect_on_hover(self.rewindButton)
        self.apply_effect_on_hover(self.spoiler)

        #* Thread runner
        self.runners = []
        self.threadpool = QtCore.QThreadPool()

        #* Auto restore ini settings on startup
        self._restore_settings_on_start()

        #* Tray icon
        self.message_is_being_shown = False
        self._create_tray_icon()

        self._setup_media_player()

        self._apply_custom_stylesheets()

        QtWidgets.QAction("Quit", self).triggered.connect(self.closeEvent)

        # #### Quick view video attributes
        # i = 0
        # for id, video in my_videos.items():
        #     if i >= 3:
        #         break
        #     print('\n'.join("'%s': '%s', " % item for item in vars(video).items()))
        #     print("---------------------------")
        #     i += 1
        # #### END Quick view


    def _create_video_list(self):
        """
        List widget containing scraped videos.
        """
        self.listVideos = CustomListWidget(self.centralwidget, objectName="listVideos")
        self.listVideos.setTabKeyNavigation(False)
        self.listVideos.setContextMenuPolicy(Qt.CustomContextMenu)
        self.listVideos.customContextMenuRequested.connect(self.on_list_item_right_click)
        self.listVideos.itemClicked.connect(self.on_list_item_left_click)
        self.listVideos.currentItemChanged.connect(self.on_item_change)


    def _create_spoiler_section(self,font=None):
        """
        Expandable lower section.
        """
        self.spoiler = Spoiler(title="Settings", ref_parent=self,font=font)
        sizePolicy = QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Maximum)

        self.list_settings_combo=QComboBox(objectName="list_settings_combo",font=font)
        self.list_settings_combo.addItems(["Favorites","Blacklist"])
        self.list_settings=QListWidget(objectName="list_settings")
        self.list_settings.setSizePolicy(sizePolicy)

        vLayout_0 = QVBoxLayout()
        vLayout_0.setAlignment(Qt.AlignTop)
        vLayout_0.addWidget(self.list_settings_combo)
        vLayout_0.addWidget(self.list_settings)

        self.cb_delete_on_exit = QCheckBox("Delete download folder on exit", objectName="cb_delete_on_exit")
        self.cb_notify_on_download = QCheckBox("Notify when all downloads finish", objectName="cb_delete_on_exit")
        self.cb_user_temp_folder = QCheckBox("Use custom temporary download folder", objectName="cb_user_temp_folder")
        self.media_download_path = QLineEdit(
            r"D:\Desktop\TEST_DOWNLOADS", # TODO replace to "Choose a different download folder",
            objectName="media_download_path",
            enabled=False,
            readOnly=True,
            )
        # TODO add import button
        self.cb_user_temp_folder.toggled.connect(self.media_download_path.setEnabled)

        self.cb_max_video_date = QCheckBox("Set oldest video date to download", objectName="cb_max_video_date")
        self.max_video_date_calendar = CustomDateEdit(
            sizePolicy=sizePolicy,
            enabled = False,
            objectName="max_video_date_calendar",
            )
        self.cb_max_video_date.toggled.connect(self.max_video_date_calendar.setEnabled)

        self.cb_max_video_number = QCheckBox("Set maximum videos to download", objectName="cb_max_video_number")
        self.max_video_number_spinbox = QSpinBox(
            sizePolicy=sizePolicy,
            enabled = False,
            objectName="max_video_number_spinbox",
            maximum=9999
            )
        self.cb_max_video_number.toggled.connect(self.max_video_number_spinbox.setEnabled)

        hLayout_1a=QHBoxLayout()
        hLayout_1a.addWidget(self.cb_user_temp_folder)
        hLayout_1a.addWidget(self.media_download_path)

        hLayout_1b=QHBoxLayout()
        hLayout_1b.addWidget(self.cb_max_video_date)
        hLayout_1b.addWidget(self.max_video_date_calendar)

        hLayout_1c=QHBoxLayout()
        hLayout_1c.addWidget(self.cb_max_video_number)
        hLayout_1c.addWidget(self.max_video_number_spinbox)

        vLayout_1 = QVBoxLayout()
        vLayout_1.setAlignment(Qt.AlignTop)
        vLayout_1.addWidget(self.cb_delete_on_exit)
        vLayout_1.addWidget(self.cb_notify_on_download)
        vLayout_1.addLayout(hLayout_1a)
        vLayout_1.addLayout(hLayout_1b)
        vLayout_1.addLayout(hLayout_1c)

        self.cb_max_video_duration = QCheckBox("Limit video duration (min)", objectName="cb_max_video_duration")
        self.max_video_duration_spinbox = QSpinBox(
            sizePolicy=sizePolicy,
            enabled = False,
            objectName="max_video_duration_spinbox",
            )
        self.cb_max_video_duration.toggled.connect(self.max_video_duration_spinbox.setEnabled)

        hLayout_2a=QHBoxLayout()
        hLayout_2a.addWidget(self.cb_max_video_duration)
        hLayout_2a.addWidget(self.max_video_duration_spinbox)

        vLayout_2 = QVBoxLayout()
        vLayout_2.setAlignment(Qt.AlignTop)
        vLayout_2.addLayout(hLayout_2a)

        main_layout = QHBoxLayout()
        main_layout.setAlignment(Qt.AlignTop)
        main_layout.addLayout(vLayout_0)
        main_layout.addLayout(vLayout_1)
        main_layout.addLayout(vLayout_2)

        # TODO QGroupBox with scraping settings: ,
        # TODO QGroupBox with player settings: fastforward offset,



        #* set any QLayout in expandable item
        self.spoiler.set_content_layout(main_layout)


    def _setup_media_player(self):
        """
        Initializes ``QMediaPlayer``.
        """
        self.player = QMediaPlayer()
        self.playlist = QMediaPlaylist()
        self.was_paused = False
        self.is_playing = False
        self.current_item = None

        self.player.mediaStatusChanged.connect(self.on_media_status_changed)
        self.player.stateChanged.connect(self.on_state_changed)
        self.player.durationChanged.connect(self.horizontalSlider.setMaximum)
        self.player.positionChanged.connect(self.horizontalSlider.setValue)
        # TODO small volume slider in toolbar right aligned
        # self.player.volumeChanged.connect()
        self.player.setVolume(60)

    def _restore_settings_on_start(self):
        """
        Restores user settings found in the excutable's runtime dir after window initialization.
        Alternatively, creates a configuration file if none is found.
        """
        self.save_to_runtimedir = True
        if os.path.exists(self.GUI_preferences_path):
            try:
                guirestore(self, self.my_settings)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, 'Error', f"Could not restore settings: {e}")
        else:
            with open(self.GUI_preferences_path, 'w') as f:
                guisave(self, self.my_settings, self.objects_to_exclude)
                f.close()

    def _create_menubar(self, font):
        """
        Initializes the top menu bar.
        """
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
            triggered=self.read_file,
        )
        self.actionSave = QtWidgets.QAction(
            "Save",
            self,
            shortcut="Ctrl+S",
            icon=QIcon(ICONS.save),
            triggered=self.write_file,
        )
        self.actionSaveAs = QtWidgets.QAction(
            "Save as...",
            self,
            shortcut="Ctrl+Shift+S",
            triggered=self.write_new_file,
        )
        self.actionExit = QtWidgets.QAction(
            "Exit",
            self,
            shortcut="Escape",
            icon=QIcon(ICONS.exit),
            triggered=self.close,
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
            triggered=self.about_info,
        )
        self.actionGitHubHomepage = QtWidgets.QAction(
            "GitHub Homepage",
            self,
            icon=QIcon(ICONS.github),
            triggered=self.github_link,
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

    def _create_statusbar(self):
        """
        Initializes the bottom statusbar.
        """
        self.statusbar = QtWidgets.QStatusBar(self)
        self.setStatusBar(self.statusbar)

    def _create_toolbar(self):
        """
        Initializes the top tool bar.
        """
        self.actionGetFeed = QtWidgets.QAction("Scrape YouTube feed",icon=QIcon(ICONS.travel_explore))
        self.actionGetFeed.triggered.connect(lambda: self.start_worker("populate_worker"))
        self.actionRestoreFeed = QtWidgets.QAction("Restore YouTube feed",icon=QIcon(ICONS.restore))
        self.actionOpenFeed = QtWidgets.QAction("Open YouTube in browser",icon=QIcon(ICONS.subscriptions))
        self.actionOpenFeed.triggered.connect(self.youtube_link)
        self.actionShowHowToUse = QtWidgets.QAction("Show usage",icon=QIcon(ICONS.keyboard_alt))
        self.actionShowHowToUse.triggered.connect(self.show_how_to_use)

        self.toolBar = QtWidgets.QToolBar(self)
        self.toolBar.addAction(self.actionGetFeed)
        self.toolBar.addAction(self.actionRestoreFeed)
        self.toolBar.addAction(self.actionOpenFeed)
        self.toolBar.addAction(self.actionShowHowToUse)
        self.toolBar.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.addToolBar(QtCore.Qt.TopToolBarArea, self.toolBar)

    def _create_music_controls(self):
        """
        Setups ``QMediaPlayer`` control widgets.
        """
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
            styleSheet = "border: none",
            clicked    = self.on_play,
            shortcut   = Qt.Key_Space, # TODO FIX acts like tab effect adding borders
        )
        self.rewindButton = QtWidgets.QPushButton(
            "",
            self.centralwidget,
            icon       = QIcon(ICONS.playback_rew_mblue),
            flat       = True,
            iconSize   = QtCore.QSize(32, 32),
            sizePolicy = size_policy,
            styleSheet = "border: none",
            clicked    = self.on_previous_song,
            shortcut   = Qt.Key_Up,
        )
        self.fastForwardButton = QtWidgets.QPushButton(
            "",
            self.centralwidget,
            icon       = QIcon(ICONS.playback_ff_mblue),
            flat       = True,
            iconSize   = QtCore.QSize(32, 32),
            sizePolicy = size_policy,
            styleSheet = "border: none",
            clicked    = self.on_next_song,
            shortcut   = Qt.Key_Down, 
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
        self.horizontalSlider.setTracking(False)
        #* manually moved slider
        self.horizontalSlider.sliderMoved.connect(self.seek_position)
        #? signal for slider moved via key presses
        #? causes audio stuttering -> done manually on key press
        # self.horizontalSlider.valueChanged[int].connect(self.changeValue)

    def _apply_custom_stylesheets(self):
        """
        Defines custom stylesheets for window widgets.
        """
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

    def start_worker(self, worker: str, **kwargs):
        """
        Starts a worker by its arbitrary name.
        """
        if worker == "populate_worker":
            populate_worker = Worker(self.populate_video_list)
            self.threadpool.start(populate_worker)
        elif worker == "video_download":
            video = kwargs.pop('video')
            if isinstance(video, Video):
                if not isinstance(get_sec(video.duration), int):
                    #? ignores unreleased videos (premiere, etc)
                    pass
                elif get_sec(video.duration) < self.max_video_duration:
                    media_download_path = self.get_media_download_path()
                    yt_dl_worker = Worker(video.start_download, media_download_path)
                    self.threadpool.start(yt_dl_worker)
                #TODO if not self.is_downloaded -> gray out

    def video_downloader(self, video: Video):
        """
        Starts a parallel execution to download the given ``Video`` instance.
        """
        self.start_worker("video_download", video=video)

    def populate_video_list(self):
        """
        Triggers the main scraping workflow.
        """
        self.listVideos.clear()
        self.signal.sync_icon.emit("Loading YouTube data", False)
        now = time.time()
        self.max_video_date = self.max_video_date_calendar.dateTime().toSecsSinceEpoch()

        max_date = self.max_video_date if self.cb_max_video_date.isChecked() else now
        max_videos = self.max_video_number_spinbox.value() if self.cb_max_video_number.isChecked() else 999
        self.my_videos, error = get_videos_from_feed(max_videos, max_date)

        if error:
            QtWidgets.QMessageBox.critical(self, 'Error', \
                f"Could not find a valid video feed in source: {error}")

        for id, video in self.my_videos.items():
            self.signal.add_listitem.emit(video)
            self.signal.start_video_download.emit(video)
            QApplication.processEvents()  # QRunnable not worth it

        self.signal.sync_icon.emit("", True)

    def fill_list_widget(self, video: Video):
        """
        Creates the item for the list widget, starts downloading it's data 
        asynchronously and inserts it.
        """
        item_widget = CustomQWidget(ref_parent=self)

        #* Add own buttons to frame
        frameLayout = QHBoxLayout(item_widget.frame)
        frameLayout.setAlignment(QtCore.Qt.AlignTop)

        download_button = CustomImageButton(
            icon=ICONS.cloud_download_lblue,
            icon_on_click=ICONS.cloud_download_white,
            icon_size=20,
            icon_max_size=30,
            custom_icons=ICONS, # allow download icon update from Video class
        )
        self.apply_effect_on_hover(download_button)
        frameLayout.addWidget(download_button)

        fav_button = CustomImageButton(
            icon=ICONS.favorite_lblue,
            icon_on_click=ICONS.favorite_white,
            icon_size=20,
            icon_max_size=30,
        )
        self.apply_effect_on_hover(fav_button)
        frameLayout.addWidget(fav_button)

        block_button = CustomImageButton(
            icon=ICONS.block_lblue,
            icon_on_click=ICONS.block_white,
            icon_size=20,
            icon_max_size=30,
        )
        self.apply_effect_on_hover(block_button)
        frameLayout.addWidget(block_button)

        checkpoint_button = CustomImageButton(
            icon=ICONS.schedule_lblue,
            icon_on_click=ICONS.schedule_white,
            icon_size=20,
            icon_max_size=30,
        )
        self.apply_effect_on_hover(checkpoint_button)
        frameLayout.addWidget(checkpoint_button)

        item_widget.frame.setLayout(frameLayout)

        #* keep track of video in list widget and viceversa
        video.item_widget = item_widget
        item_widget.video = video
        media_download_path = self.get_media_download_path()
        item_widget.media_path = os.path.join(media_download_path)
        item_widget.video.download_button = download_button
        # item_widget.frame.layout().itemAt() #! incomprehensible later on

        item_widget.setTextUp(video.title)

        author_thumbnail_sender = Sender("author_thumbnail", item_widget)
        # it's not garbage. Else the reply will return a destroyed Sender
        self.sender_list.append(author_thumbnail_sender)
        self.network_manager.start_download(url=video.author_thumbnail, sender=author_thumbnail_sender)

        vid_thumbnail_sender = Sender("vid_thumbnail", item_widget)
        self.sender_list.append(vid_thumbnail_sender)
        self.network_manager.start_download(url=video.thumbnail, sender=vid_thumbnail_sender)

        # no need to subclass QListWidgetItem, just the widget (CustomQWidget) set on it
        item = QListWidgetItem(self.listVideos)
        item.setSizeHint(item_widget.sizeHint())
        self.listVideos.addItem(item)
        self.listVideos.setItemWidget(item, item_widget)

    def get_media_download_path(self):
        """
        Defines the dir where videos should be downloaded.
        """
        if not self.cb_user_temp_folder.isChecked():
            media_download_path = self.temp_dir
        else:
            media_download_path = self.media_download_path.text()
        return media_download_path

    def on_list_item_left_click(self, item: QListWidgetItem):
        """
        Called when a ``QListWidget`` item is left clicked.
        """
        if item is None: return

        #* Return the rest of list items to their original state
        for i in range(self.listVideos.count()):
            item_i = self.listVideos.item(i)
            widget_i = self.listVideos.itemWidget(item_i)
            item_i.setBackground(QColor(240, 240, 240))
            textUpQLabel = widget_i.textUpQLabel
            textUpQLabel.setGraphicsEffect(None)
            textUpQLabel.setStyleSheet("""color: rgb(70,130,180);""")
            authorQLabel = widget_i.authorQLabel
            self.apply_shadow_effect(authorQLabel)
            thumbnailQLabel = widget_i.thumbnailQLabel
            self.apply_shadow_effect(thumbnailQLabel)
            frame = widget_i.frame
            self.apply_shadow_effect(frame)
            widget_i.color = QtGui.QColor(240, 240, 240)

        #* Format the clicked item
        widget = item.listWidget().itemWidget(item)  # returns a CustomQWidget
        shadow_color = QColor(49, 65, 129)
        self.apply_shadow_effect(widget.authorQLabel, color=shadow_color)
        self.apply_shadow_effect(widget.thumbnailQLabel, color=shadow_color)
        self.apply_shadow_effect(widget.frame, color=shadow_color)
        self.apply_shadow_effect(widget.textUpQLabel, color=shadow_color)
        widget.textUpQLabel.setStyleSheet("""
            color: rgb(255,255,255);
        """)
        widget.color = QtGui.QColor(61, 125, 194)

    def on_item_change(self, item, previous_item):
        """
        Invoked when the selected video item in a list changes.
        """
        current_item = item
        current_widget = self.listVideos.itemWidget(current_item)
        self.is_playing = self.playButton.isChecked()
        if self.is_playing:
            if not hasattr(current_widget, "video"):
                # end of list
                # self.on_next_song()
                # TODO select next_song or previous song depending on
                # item and previous_item row number
                return
            current_video = current_widget.video
            if current_video.download_path is None: return
            video_media = QMediaContent(QUrl.fromLocalFile(current_video.download_path))
            self.playlist.clear()
            self.playlist.addMedia(video_media)
            self.player.play()
            self.played_video = current_video
            self.current_item = current_item

    def on_media_status_changed(self):
        """
        Invoked when a file is loaded in ``QMediaPlayer``.
        """
        self.is_playing = self.playButton.isChecked()
        if self.player.mediaStatus()==QMediaPlayer.LoadedMedia and self.is_playing:
            durationT = self.player.duration()
            self.horizontalSlider.setRange(0, durationT)
            self.player.play()

    def on_state_changed(self):
        """
        Invoked when the ``QMediaPlayer`` state changes.
        """
        if self.player.state() == QMediaPlayer.StoppedState:
            self.player.stop()

    def on_position_changed(self, position):
        """
        ``position`` : timestamp in milliseconds.
        """
        self.horizontalSlider.setValue(position)

        # TODO
        # if position == self.player.duration():
        #     self.on_next_song()



    def seek_position(self, position):
        """
        Change player position through manual slider drag.
        """
        sender = self.sender()
        if isinstance(sender, QSlider):
            if self.player.isSeekable():
                self.player.setPosition(position)

    def on_play(self, checked):
        """
        Select the previous video list item.
        """
        if not self.current_item: return
        self.was_paused = checked
        current_video = self.listVideos.itemWidget(self.current_item).video
        print("current_video.download_path : ", current_video.download_path)
        if self.player.mediaStatus() == QMediaPlayer.NoMedia:
            self.played_video = current_video
            if current_video.download_path is None: return
            # print("current_video.download_path : ", current_video.download_path)
            video_media = QMediaContent(QUrl.fromLocalFile(current_video.download_path))
            self.playlist.addMedia(video_media)
            if self.playlist.mediaCount() != 0:
                self.player.setPlaylist(self.playlist)
        else:
            if self.played_video != current_video:
                self.playlist.clear()
                video_media = QMediaContent(QUrl.fromLocalFile(current_video.download_path))
                self.playlist.addMedia(video_media)
                self.played_video = current_video

        if self.was_paused:
            self.player.play()
            self.is_playing = True
        elif not self.was_paused:
            self.player.pause()

    def on_previous_song(self):
        """
        Select the previous video list item.
        """
        if self.listVideos.count() == 0: return

        previous_row = self.listVideos.currentRow() - 1
        if self.listVideos.currentRow() == 0:
            previous_row = self.listVideos.count() - 1

        self.listVideos.setCurrentRow(previous_row)
        self.on_list_item_left_click(self.listVideos.item(previous_row))

    def on_next_song(self):
        """
        Select the next video list item.
        """
        if self.listVideos.count() == 0: return

        next_row = self.listVideos.currentRow() + 1
        if self.listVideos.currentRow() == self.listVideos.count() - 1:
            next_row = 0

        self.listVideos.setCurrentRow(next_row)
        self.on_list_item_left_click(self.listVideos.item(next_row))

    def apply_shadow_effect(self, widget: QWidget, color=QColor(50, 50, 50), blur_radius=10, offset=2):
        """
        Same widget graphic effect instance can't be used more than once
        else it's removed from the first widget. Workaround using a dict:\n
        Notes: when applied to a ``CustomImageButton``, this effect will add a rounded rect 
        background. See 'CustomImageButton_example.png' for reference
        """
        self.shadow_effects[self.shadow_effects_counter] = QGraphicsDropShadowEffect(self)
        self.shadow_effects[self.shadow_effects_counter].setBlurRadius(blur_radius)
        self.shadow_effects[self.shadow_effects_counter].setColor(color)
        self.shadow_effects[self.shadow_effects_counter].setOffset(offset)
        widget.setGraphicsEffect(self.shadow_effects[self.shadow_effects_counter])
        self.shadow_effects_counter += 1

    def apply_effect_on_hover(self, widget: QWidget):
        """
        Installs an event filter to display a shadow upon hovering.
        The event filter is a MainWindow. An event filter receives all events 
        that are sent to ``widget``.\n        
        Note that applying this effect will:
            - override the set Enter and Leave events. (must call object.enterEvent() explicitly)
            - add a rounded rect as with the ``apply_shadow_effect`` method.
        """
        widget.installEventFilter(self)
        self.widgets_with_hover.append(widget)

    def github_link(self):
        """
        Opens the project's GitHub page.
        """
        url = 'https://github.com/danicc097/Youtube-Feed-Scraper'
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def youtube_link(self):
        """
        Opens the user's Youtube subscriptions page.
        """
        url = "https://www.youtube.com/feed/subscriptions"
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def show_how_to_use(self):
        """
        Displays a popup showing the app main controls.
        """
        self.notification = Notification(ref_parent=self)
        self.apply_shadow_effect(self.notification.frame)
        self.notification.animate_opening()  #? call before setting up widgets
        #! CRUCIAL inside frames to show properly
        sizePolicy = QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Maximum)

        left_arrow  = CustomImageButton(icon=ICONS.west_lblue, icon_size=25, icon_max_size=30)
        right_arrow = CustomImageButton(icon=ICONS.east_lblue, icon_size=25, icon_max_size=30)
        up_arrow    = CustomImageButton(icon=ICONS.north_lblue, icon_size=25, icon_max_size=30)
        down_arrow  = CustomImageButton(icon=ICONS.south_lblue, icon_size=25, icon_max_size=30)
        spacebar    = CustomImageButton(icon=ICONS.space_bar_lblue, icon_size=25, icon_max_size=30)

        all_GridLayout = QGridLayout()
        font = QFont()
        font.setPointSize(15)

        all_GridLayout.addWidget(left_arrow, 0, 0, 1, 1, alignment=Qt.AlignCenter)
        all_GridLayout.addWidget(right_arrow, 0, 1, 1, 1, alignment=Qt.AlignCenter)
        label = QLabel("Fast forward / Rewind", sizePolicy=sizePolicy, alignment=Qt.AlignLeft, font=font)
        all_GridLayout.addWidget(label, 0, 2, 1, 1)

        all_GridLayout.addWidget(up_arrow, 1, 0, 1, 1, alignment=Qt.AlignCenter)
        all_GridLayout.addWidget(down_arrow, 1, 1, 1, 1, alignment=Qt.AlignCenter)
        label = QLabel(text="Switch tracks", sizePolicy=sizePolicy, alignment=Qt.AlignLeft, font=font)
        all_GridLayout.addWidget(label, 1, 2, 1, 1)

        all_GridLayout.addWidget(spacebar, 3, 0, 1, 2, alignment=Qt.AlignCenter)
        label = QLabel(text="Play / Pause", sizePolicy=sizePolicy, alignment=Qt.AlignLeft, font=font)
        all_GridLayout.addWidget(label, 3, 2, 1, 1)

        font.setPointSize(20)
        frameLayout = QVBoxLayout(self.notification.frame)
        frameLayout.addWidget(QLabel("HOW TO USE", sizePolicy=sizePolicy, alignment=Qt.AlignCenter, font=font))

        frameLayout.addLayout(all_GridLayout)

    @QtCore.pyqtSlot(QtCore.QPoint)
    def on_list_item_right_click(self, pos):
        """
        Called when a ``QListWidget`` item is right clicked.
        """
        item = self.listVideos.itemAt(pos)
        self.on_list_item_left_click(item)  # emulate click
        menu = QtWidgets.QMenu()
        delete_row = menu.addAction("Remove")
        delete_row.setIconVisibleInMenu(True)
        delete_row.setIcon(QIcon(ICONS.delete))
        action = menu.exec_(self.listVideos.viewport().mapToGlobal(pos))
        if action == delete_row:
            row = self.listVideos.row(item)
            self.listVideos.takeItem(row)

    def write_new_file(self):  # ? Save as
        """
        Saves GUI user input to a new config file.
        """
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

    def write_file(self):  # ? Save
        """
        Saves GUI user input to the previously opened config file.
        """
        #* Default to writing to current directory
        if self.save_to_runtimedir:
            self.statusBar().showMessage("Changes saved to: {}".format(self.GUI_preferences_path))
            guisave(self, self.my_settings, self.objects_to_exclude)

        #* A specific config file was opened from the menu
        elif self.config_is_set and self.filename:
            self.statusBar().showMessage("Changes saved to: {}".format(self.filename))
            self.my_settings = QtCore.QSettings(self.filename, QtCore.QSettings.IniFormat)
            guisave(self, self.my_settings, self.objects_to_exclude)

        else:
            self.write_new_file()

    def read_file(self):  # ? Open
        """
        Restores GUI user input from a config file.
        """
        #* File dialog
        self.filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select a configuration file to load…",
            str(RUNTIME_DIR),
            'Configuration Files (*.ini)',
            options=QtWidgets.QFileDialog.DontResolveSymlinks
        )
        #* Invalid file or none
        if not self.filename:
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
        """
        Status bar sync label showing ``label_text``.
        """
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

        self.label_counter = 0
        self.label_limit = 3
        self.label_timer = QtCore.QTimer()
        self.label_timer.timeout.connect(lambda: self.ellipsis_in_label(self.title))
        self.label_timer.start(1 * 1000)
        self.statusBar().addPermanentWidget(self.label_sync)
        self.statusBar().addPermanentWidget(self.title)

    def ellipsis_in_label(self, widget):
        """
        Appends a dynamic ellipsis at the end of a widget's ``text``, if available.
        """
        try:
            if self.label_counter < self.label_limit:
                text = widget.text() + "."
                self.label_counter += 1
            else:
                text = widget.text()[:-self.label_limit]
                self.label_counter = 0
            widget.setText(text)
        except AttributeError:
            return

    def notify_all_videos_downloaded(self):
        """
        Desktop notification after the complete download process is done.
        """
        self.trayIcon.show()
        if not self.hasFocus():
            self.message_is_being_shown = True
            self.trayIcon.showMessage(
                f"🎼 All videos have been downloaded!\n",
                "Click here to start listening 🎵.",
                self.window_manager.app_icon,
                1200 * 1000,
            )  # milliseconds default

    def notification_handler(self):
        """
        Ensure the app is focused after a desktop notification click.
        """
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.show()
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.show()

    def _create_tray_icon(self):
        """
        Define an icon in the notification area.
        Also necessary to display a desktop notification.
        """
        self.restoreAction = QtWidgets.QAction("&Restore", self, triggered=self.showNormal)
        self.quitAction = QtWidgets.QAction("&Quit", self, triggered=self.close)  # filtered in closeEvent
        self.trayIconMenu = QtWidgets.QMenu(self)
        self.trayIconMenu.addAction(self.restoreAction)
        self.trayIconMenu.addAction(self.quitAction)

        self.trayIcon = QSystemTrayIcon(self)
        self.trayIcon.setContextMenu(self.trayIconMenu)
        self.trayIcon.setIcon(QIcon(str(Path.joinpath(BASEDIR, 'data', 'main_icon.png'))))
        self.trayIcon.messageClicked.connect(self.notification_handler)

    def global_client_loader(self, sender: Sender, byte_array: QByteArray):
        """
        Handles requests made from a custom ``QNetworkAccessManager``.
        """
        if sender.sender_name == "vid_thumbnail":
            vid_thumbnail = QPixmap()
            vid_thumbnail.loadFromData(byte_array)
            sender.sender_object.set_thumbnail(vid_thumbnail)

        if sender.sender_name == "author_thumbnail":
            sender.sender_object.authorQLabel.set_round_label(byte_array)

    def single_timer(self, seconds, fn, *args, **kwargs):
        """
        Single use timer that connects to ``fn`` after ``seconds``.
        """
        self.time_sync = QtCore.QTimer()
        self.time_sync.timeout.connect(lambda: fn, *args, **kwargs)
        self.time_sync.setSingleShot(True)
        self.time_sync.start(int(seconds) * 1000)

    def about_info(self):
        """
        Shows license information.
        """
        # parent is necessary to center msgbox by default
        self.infoScreen = QtWidgets.QMessageBox(self)
        self.infoScreen.setFont(self.my_font)
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

    def change_slider_position(self, fast_forward=True, offset=20000):
        """
        Fast forward or rewind song.
        Parameters:
        -----------
        ``offset`` : in milliseconds.
        ``fast_forward`` : advance (True) or rewind (False).
        """
        offset = offset if fast_forward else (-1)*offset
        self.player.positionChanged.disconnect()
        position = self.horizontalSlider.value() + offset
        self.horizontalSlider.setValue(position)
        self.player.setPosition(position)
        # self.horizontalSlider.setValue(position)
        self.player.positionChanged.connect(self.on_position_changed)


    #####???##################################################
    #####??? EVENTS
    #####???##################################################

    # TODO may need to override events in list widget
    # def event(self, event):
    #     if (event.type() == QtCore.QEvent.KeyPress) and (
    #         event.key() == Qt.Key_Up or
    #         event.key() == Qt.Key_Down or
    #         event.key() == Qt.Key_Left or
    #         event.key() == Qt.Key_Right
    #     ):
    #         print('Parent handling arrow keys')
    #         return True
    #     return QWidget.event(self, event)

    def eventFilter(self, object, event):
        """
        Certain events for widgets have to be defined and 
        filtered inside here, not in their own classes.
        """
        #* apply shadow effect when hovered over
        if isinstance(object, QWidget) and object in self.widgets_with_hover:
            if event.type() == QtCore.QEvent.Enter:
                self.apply_shadow_effect(object, color=QColor(16, 47, 151), blur_radius=20, offset=0)
                #? the custom event is overridden by the effect
                if isinstance(object, CustomImageButton):
                    object.enterEvent(event)
                return True
            elif event.type() == QtCore.QEvent.Leave:
                object.setGraphicsEffect(None)
                if isinstance(object, CustomImageButton):
                    object.leaveEvent(event)
            # elif event.type() == QtCore.QEvent.FocusOut:
            #     if isinstance(object, Notification):
            #         object.destroy()

        elif event.type() == QtCore.QEvent.MouseButtonPress and isinstance(object, CustomListWidget):
            return True

        return super().eventFilter(object, event)

    def changeEvent(self, event):
        """
        Reimplements ``changeEvent``.
        """
        #* Hides the system tray icon when the main window is visible, and viceversa.
        if event.type()==QtCore.QEvent.WindowStateChange and self.windowState() and self.isMinimized():
            self.trayIcon.show()
            event.accept()
        else:
            try:
                if not self.message_is_being_shown:
                    self.trayIcon.hide()
            except:
                pass

    def closeEvent(self, event):
        """
        Catches the MainWindow close button event and displays a dialog.
        """
        close = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Question, 'Exit', 'Exit application?', parent=self)
        close.setFont(self.my_font)
        close_reject = close.addButton('No', QtWidgets.QMessageBox.NoRole)
        close_accept = close.addButton('Yes', QtWidgets.QMessageBox.AcceptRole)
        close.exec()  # Necessary for property-based API
        if close.clickedButton() == close_accept:
            self.trayIcon.setVisible(False)
            
            #* Delete temp folder
            media_download_path = self.get_media_download_path()
            if self.cb_delete_on_exit.isChecked():
                shutil.rmtree(media_download_path, ignore_errors=True)
            
            guisave(self, self.my_settings, self.objects_to_exclude)
            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        """
        Reimplements ``keyPressEvent``.
        """
        #* Control media playing through arrows and spacebar

        # TODO left and right only work properly
        # AFTER clicking on any video manually
        # not with up and down keys
        if event.key() == Qt.Key_Left:
            self.change_slider_position(fast_forward=False)

        elif event.key() == Qt.Key_Right:
            self.change_slider_position(fast_forward=True)


        # elif event.key() == Qt.Key_Up:
        #     print("Key_Up pressed")
        #     self.on_previous_song()

        # elif event.key() == Qt.Key_Down:
        #     print("Key_Down pressed")
        #     self.on_next_song()

        # else:
        #     return False

    #####???##################################################
    #####??? END OF MAINWINDOW
    #####???##################################################


#####???##################################################
#####??? INITIALIZE UPON IMPORT
#####???##################################################

app = QtWidgets.QApplication(sys.argv)
app.setStyle('Fusion')
# app.setFont not cascaded to nested widgets. Define inside window instance
app.setApplicationName("Youtube Scraper")
app.setOrganizationName("@danicc097")
app_icon = QIcon(str(Path.joinpath(BASEDIR, 'data', 'main_icon.png')))
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

sys.exit(app.exec_())
