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

import os
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
import time
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import re
from youtube_dl import YoutubeDL
from jsonpath_ng import jsonpath
from jsonpath_ng.ext import parse
import json


class MyLogger(object):
    """YoutubeDL logger"""
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        print(msg)


class Video():
    """
    Store video information for ease of use. 
    Download it in parallel using ``start_download`` in a worker.
    """
    def __init__(self, id, title="", time="", author="", thumbnail="", author_thumbnail="", duration=""):
        self.id               = str(id)
        self.url              = "https://www.youtube.com/watch?v=" + self.id
        self.title            = str(title)
        self.time             = str(time)
        self.author           = str(author)
        self.thumbnail        = str(thumbnail)
        self.author_thumbnail = str(author_thumbnail)
        self.duration         = str(duration)
        self.is_downloaded    = False
        self.download_button  = None

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
            'progress_hooks': [self._progress_hook],
            'outtmpl': outtmpl
        }
        with YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([self.url])
            except:
                self._download_fail()

    def _progress_hook(self, d):
        # TODO conversion status, "file_download_done" after conversion
        
        if d['status'] == 'finished':
            print(f'Done downloading {self.title}. Converting...')
            self._download_success()
            self.is_downloaded = True

    def _download_success(self):
        self.download_button.icon = "download_success"

    def _download_fail(self):
        self.download_button.icon = "download_fail"


def setup_driver(user_data=None):
    if user_data is None:
        user_data = os.path.expanduser('~') + r'\AppData\Local\Google\Chrome\User Data'

    #? automatic driver detection
    chrome_driver_path = ChromeDriverManager().install()
    os.environ["PATH"] += os.pathsep + chrome_driver_path

    options = webdriver.ChromeOptions()
    # options.add_argument("--no-sandbox")  # Bypass OS security model
    options.add_argument("--disable-dev-shm-usage")  # overcome limited resource problems
    options.add_argument("--disable-extensions")
    # options.add_argument("--disable-gpu")  # applicable to windows os only
    options.add_argument("--headless")
    options.add_argument(r'--user-data-dir=' + user_data)
    driver = webdriver.Chrome(chrome_driver_path, options=options)
    # driver.minimize_window()

    return driver


def scroll_down(driver):
    html = driver.find_element_by_tag_name('html')
    html.send_keys(Keys.END)


def get_timestamp_from_relative_time(time_string):
    """Return a timestamp from a relative ``time_string``, e.g. ``3 minutes ago```."""
    now = time.time()
    if re.findall('[0-9]+', time_string):
        relative_time = int(re.findall('[0-9]+', time_string)[0])
        if 'second' in time_string:
            timestamp = now - relative_time
        elif 'minute' in time_string:
            timestamp = now - relative_time * 60
        elif 'hour' in time_string:
            timestamp = now - relative_time * 60 * 60
        elif 'day' in time_string:
            timestamp = now - relative_time * 60 * 60 * 24
        elif 'week' in time_string:
            timestamp = now - relative_time * 60 * 60 * 24 * 7
        elif 'month' in time_string:
            timestamp = now - relative_time * 60 * 60 * 24 * 7 * 30
        else:
            timestamp = now
    else:
        timestamp = now
    return timestamp


def get_videos_metadata(source):
    """Extract a list containing all videos' unparsed metadata."""
    try:
        #* variable containing rendered feed videos data
        json_var = re.findall(r'ytInitialData = (.*?);', source, re.DOTALL | re.MULTILINE)[0]
    except Exception as e:
        return None, e  # not None triggers error msg

    json_dict = json.loads(json_var)

    #* match all rendered video grids
    jsonpath_expr = parse('*..gridRenderer..gridVideoRenderer')

    #* get each video's data dict
    videos_json = [match.value for match in jsonpath_expr.find(json_dict)]
    
    return videos_json, None

def get_feed_videos_source(max_videos, max_date, last_video_id=None):
    #TODO use user_data folder from GUI if available
    driver = setup_driver(user_data=None)
    print('\nRETRIEVING YOUTUBE DATA...\n')

    #* create new tab
    driver.execute_script("window.open('about:blank','_blank');")
    new_tab = driver.window_handles[1]
    driver.switch_to.window(new_tab)
    driver.get('https://www.youtube.com/feed/subscriptions')
    source = driver.page_source

    videos_json, error = get_videos_metadata(source)
    if error: return None, error
    
    videos_parsed = len(videos_json)
        
    my_videos = get_video_dict(videos_json, max_videos, max_date, driver, videos_parsed)
            
    driver.close()

    return my_videos, error

def get_video_dict(videos_json, max_videos, max_date, driver, videos_parsed):
    #* get last video information
    last_video_parsed = parse_videos([videos_json[-1]], max_videos, max_date)
    id, video = last_video_parsed.popitem()

    while videos_parsed < max_videos and video.time > max_date: 
        scroll_down(driver)
        time.sleep(1)
        source = driver.page_source
        videos_json, error = get_videos_metadata(source)
        if error: return 
        videos_parsed = len(videos_json)
        last_video_parsed = parse_videos([videos_json[-1]], max_videos, max_date)
        id, video = last_video_parsed.popitem()
        
    return parse_videos(videos_json, max_videos, max_date, id_stop=id)


def parse_videos(videos_json, max_videos, max_date, id_stop=None):
    #? new metadata to be as required + edit Video class accordingly
    parse_strings = {
        'id'              : 'videoId',
        'title'           : 'title.runs[*].text',
        'author'          : 'shortBylineText.runs[*].text',
        'author_thumbnail': 'channelThumbnail.thumbnails[*].url',
        'thumbnail'       : 'thumbnail.thumbnails[*].url',
        'time'            : 'publishedTimeText.simpleText',
        'duration'        : 'thumbnailOverlays[*].thumbnailOverlayTimeStatusRenderer.text.simpleText',
    }

    my_videos = {}
    videos_parsed = 0
    for item in videos_json:
        current_video = create_video_dict_item(parse_strings, my_videos, item)
        videos_parsed += 1
        # TODO until user selected last video time or id (history button) -> qsettings
        if (
            videos_parsed >= max_videos or 
            current_video.time < max_date or 
            current_video.id == id_stop
        ):
            break
            
    print("videos_json lenght :", len(videos_json))
    print("videos parsed :", videos_parsed)
    return my_videos

def create_video_dict_item(parse_strings, my_videos, item):
    """Create a new ``Video`` dict item, accessed by ``id``."""
    for video_attr, parse_str in parse_strings.items():
        json_expr = parse(parse_str)
        # see jsonpath_ng
        matches = [match.value for match in json_expr.find(item)]
        if not matches:
            match_attr = ""
        else:
            match_attr = matches[0]
            # this requires id to be the first key to be parsed
            if video_attr == "id":
                video_id = match_attr
                my_videos[video_id] = Video(video_id)
            elif video_attr == "time":
                match_attr = get_timestamp_from_relative_time(match_attr)
            setattr(my_videos[video_id], video_attr, match_attr)
    return my_videos[video_id]
