
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
    def __init__(self, BASEDIR) -> None:
        super().__init__()
        self.set_my_attributes(BASEDIR)

    def set_my_attributes(self, BASEDIR):
        self.main_icon =           str(Path.joinpath(BASEDIR, 'data', 'main-icon.png'))
        self.playback_play =       str(Path.joinpath(BASEDIR, 'data', 'images', 'playback_play.png'))
        self.playback_pause =      str(Path.joinpath(BASEDIR, 'data', 'images', 'playback_pause.png'))
        self.playback_ff =         str(Path.joinpath(BASEDIR, 'data', 'images', 'playback_ff.png'))
        self.playback_rew =        str(Path.joinpath(BASEDIR, 'data', 'images', 'playback_rew.png'))
        self.playback_play_blue =  str(Path.joinpath(BASEDIR, 'data', 'images', 'blue', 'playback_play.png'))
        self.playback_pause_blue = str(Path.joinpath(BASEDIR, 'data', 'images', 'blue', 'playback_pause.png'))
        self.playback_ff_blue =    str(Path.joinpath(BASEDIR, 'data', 'images', 'blue', 'playback_ff.png'))
        self.playback_rew_blue =   str(Path.joinpath(BASEDIR, 'data', 'images', 'blue', 'playback_rew.png'))
        self.save =                str(Path.joinpath(BASEDIR, 'data', 'images', 'save.png'))
        self.open =                str(Path.joinpath(BASEDIR, 'data', 'images', 'open.png'))
        self.about =               str(Path.joinpath(BASEDIR, 'data', 'images', 'about.png'))
        self.settings =            str(Path.joinpath(BASEDIR, 'data', 'images', 'settings.png'))
        self.exit =                str(Path.joinpath(BASEDIR, 'data', 'images', 'exit.png'))
        self.github =              str(Path.joinpath(BASEDIR, 'data', 'images', 'github.png'))
        self.block =               str(Path.joinpath(BASEDIR, 'data', 'images', 'block.png'))
        self.cancel =              str(Path.joinpath(BASEDIR, 'data', 'images', 'cancel.png'))
        self.cloud_download =      str(Path.joinpath(BASEDIR, 'data', 'images', 'cloud_download.png'))
        self.east =                str(Path.joinpath(BASEDIR, 'data', 'images', 'east.png'))
        self.west =                str(Path.joinpath(BASEDIR, 'data', 'images', 'west.png'))
        self.north =               str(Path.joinpath(BASEDIR, 'data', 'images', 'north.png'))
        self.favorite =            str(Path.joinpath(BASEDIR, 'data', 'images', 'favorite.png'))
        self.file_download_done =  str(Path.joinpath(BASEDIR, 'data', 'images', 'file_download_done.png'))
        self.restore =             str(Path.joinpath(BASEDIR, 'data', 'images', 'restore.png'))
        self.save_alt =            str(Path.joinpath(BASEDIR, 'data', 'images', 'save_alt.png'))
        self.schedule =            str(Path.joinpath(BASEDIR, 'data', 'images', 'schedule.png'))
        self.space_bar =           str(Path.joinpath(BASEDIR, 'data', 'images', 'space_bar.png'))
        self.subscriptions =       str(Path.joinpath(BASEDIR, 'data', 'images', 'subscriptions.png'))
        self.travel_explore =      str(Path.joinpath(BASEDIR, 'data', 'images', 'travel_explore.png'))
        
        