# yapf: disable

from pathlib import Path
import sys


def get_path(relative_path):
    """Use correct absolute paths for bundled and dev versions."""
    rel_path = Path(relative_path)
    dev_base_path = Path(__file__).resolve().parent.parent
    #* dev_base_path is used by default if _MEIPASS doesn't exist
    base_path = getattr(sys, "_MEIPASS", dev_base_path)
    # _MEIPASS works for both onedir and onefile
    return base_path / rel_path


class MyIcons(object):
    """Icons to be initialized in QMainWindow"""
    def __init__(self, BASEDIR) -> None:
        super().__init__()
        self.set_my_attributes(BASEDIR)

    def set_my_attributes(self, BASEDIR):
        self.main_icon           = str(Path.joinpath(BASEDIR, 'data', 'main-icon.png'))
        self.playback_play       = str(Path.joinpath(BASEDIR, 'data', 'images', 'playback_play.png'))
        self.playback_pause      = str(Path.joinpath(BASEDIR, 'data', 'images', 'playback_pause.png'))
        self.playback_ff         = str(Path.joinpath(BASEDIR, 'data', 'images', 'playback_ff.png'))
        self.playback_rew        = str(Path.joinpath(BASEDIR, 'data', 'images', 'playback_rew.png'))
        self.save                = str(Path.joinpath(BASEDIR, 'data', 'images', 'save.png'))
        self.open                = str(Path.joinpath(BASEDIR, 'data', 'images', 'open.png'))
        self.about               = str(Path.joinpath(BASEDIR, 'data', 'images', 'about.png'))
        self.settings            = str(Path.joinpath(BASEDIR, 'data', 'images', 'settings.png'))
        self.exit                = str(Path.joinpath(BASEDIR, 'data', 'images', 'exit.png'))
        self.github              = str(Path.joinpath(BASEDIR, 'data', 'images', 'github.png'))
        self.block               = str(Path.joinpath(BASEDIR, 'data', 'images', 'block.png'))
        self.cancel              = str(Path.joinpath(BASEDIR, 'data', 'images', 'cancel.png'))
        self.cloud_download      = str(Path.joinpath(BASEDIR, 'data', 'images', 'cloud_download.png'))
        self.east                = str(Path.joinpath(BASEDIR, 'data', 'images', 'east.png'))
        self.west                = str(Path.joinpath(BASEDIR, 'data', 'images', 'west.png'))
        self.north               = str(Path.joinpath(BASEDIR, 'data', 'images', 'north.png'))
        self.favorite            = str(Path.joinpath(BASEDIR, 'data', 'images', 'favorite.png'))
        self.file_download_done  = str(Path.joinpath(BASEDIR, 'data', 'images', 'file_download_done.png'))
        self.restore             = str(Path.joinpath(BASEDIR, 'data', 'images', 'restore.png'))
        self.save_alt            = str(Path.joinpath(BASEDIR, 'data', 'images', 'save_alt.png'))
        self.schedule            = str(Path.joinpath(BASEDIR, 'data', 'images', 'schedule.png'))
        self.space_bar           = str(Path.joinpath(BASEDIR, 'data', 'images', 'space_bar.png'))
        self.subscriptions       = str(Path.joinpath(BASEDIR, 'data', 'images', 'subscriptions.png'))
        self.travel_explore      = str(Path.joinpath(BASEDIR, 'data', 'images', 'travel_explore.png'))

        #* Icons supporting multicolor. default black
        #//________________________________________________________________________________
        color_folder="black"
        self.block              = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'block.png'))
        self.cancel             = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'cancel.png'))
        self.cloud_download     = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'cloud_download.png'))
        self.download_off       = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'download_off.png'))
        self.east               = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'east.png'))
        self.favorite           = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'favorite.png'))
        self.file_download_done = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'file_download_done.png'))
        self.north              = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'north.png'))
        self.restore            = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'restore.png'))
        self.save_alt           = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'save_alt.png'))
        self.schedule           = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'schedule.png'))
        self.south              = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'south.png'))
        self.space_bar          = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'space_bar.png'))
        self.subscriptions      = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'subscriptions.png'))
        self.travel_explore     = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'travel_explore.png'))
        self.west               = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'west.png'))

        #//________________________________________________________________________________
        color_folder="#8AB4F8" #light blue
        self.block_lblue              = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'block.png'))
        self.cancel_lblue             = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'cancel.png'))
        self.cloud_download_lblue     = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'cloud_download.png'))
        self.download_off_lblue       = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'download_off.png'))
        self.east_lblue               = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'east.png'))
        self.favorite_lblue           = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'favorite.png'))
        self.file_download_done_lblue = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'file_download_done.png'))
        self.north_lblue              = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'north.png'))
        self.restore_lblue            = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'restore.png'))
        self.save_alt_lblue           = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'save_alt.png'))
        self.schedule_lblue           = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'schedule.png'))
        self.south_lblue              = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'south.png'))
        self.space_bar_lblue          = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'space_bar.png'))
        self.subscriptions_lblue      = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'subscriptions.png'))
        self.travel_explore_lblue     = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'travel_explore.png'))
        self.west_lblue               = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'west.png'))

        #//________________________________________________________________________________
        color_folder                  = "#438EC8" #mid blue
        self.block_mblue              = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'block.png'))
        self.cancel_mblue             = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'cancel.png'))
        self.cloud_download_mblue     = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'cloud_download.png'))
        self.download_off_mblue       = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'download_off.png'))
        self.east_mblue               = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'east.png'))
        self.favorite_mblue           = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'favorite.png'))
        self.file_download_done_mblue = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'file_download_done.png'))
        self.north_mblue              = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'north.png'))
        self.restore_mblue            = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'restore.png'))
        self.save_alt_mblue           = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'save_alt.png'))
        self.schedule_mblue           = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'schedule.png'))
        self.south_mblue              = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'south.png'))
        self.space_bar_mblue          = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'space_bar.png'))
        self.subscriptions_mblue      = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'subscriptions.png'))
        self.travel_explore_mblue     = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'travel_explore.png'))
        self.west_mblue               = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'west.png'))
        self.playback_play_mblue      = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'playback_play.png'))
        self.playback_pause_mblue     = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'playback_pause.png'))
        self.playback_ff_mblue        = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'playback_ff.png'))
        self.playback_rew_mblue       = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'playback_rew.png'))
        #//________________________________________________________________________________
        color_folder="grey"
        self.block_grey              = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'block.png'))
        self.cancel_grey             = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'cancel.png'))
        self.cloud_download_grey     = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'cloud_download.png'))
        self.download_off_grey       = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'download_off.png'))
        self.east_grey               = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'east.png'))
        self.favorite_grey           = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'favorite.png'))
        self.file_download_done_grey = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'file_download_done.png'))
        self.north_grey              = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'north.png'))
        self.restore_grey            = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'restore.png'))
        self.save_alt_grey           = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'save_alt.png'))
        self.schedule_grey           = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'schedule.png'))
        self.south_grey              = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'south.png'))
        self.space_bar_grey          = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'space_bar.png'))
        self.subscriptions_grey      = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'subscriptions.png'))
        self.travel_explore_grey     = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'travel_explore.png'))
        self.west_grey               = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'west.png'))

        #//________________________________________________________________________________
        color_folder="white"
        self.block_white              = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'block.png'))
        self.cancel_white             = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'cancel.png'))
        self.cloud_download_white     = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'cloud_download.png'))
        self.download_off_white       = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'download_off.png'))
        self.east_white               = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'east.png'))
        self.favorite_white           = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'favorite.png'))
        self.file_download_done_white = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'file_download_done.png'))
        self.north_white              = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'north.png'))
        self.restore_white            = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'restore.png'))
        self.save_alt_white           = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'save_alt.png'))
        self.schedule_white           = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'schedule.png'))
        self.south_white              = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'south.png'))
        self.space_bar_white          = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'space_bar.png'))
        self.subscriptions_white      = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'subscriptions.png'))
        self.travel_explore_white     = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'travel_explore.png'))
        self.west_white               = str(Path.joinpath(BASEDIR, 'data', 'images', color_folder , 'west.png'))
