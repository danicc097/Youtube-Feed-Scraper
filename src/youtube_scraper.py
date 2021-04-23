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

import copy
from logging import info
import os
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
import time
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

import re
from youtube_dl import YoutubeDL
from jsonpath_ng import jsonpath
from jsonpath_ng.ext import parse
import json
from sys import platform
from typing import List, Set, Dict, Optional, Any, Tuple

class MyLogger(object):
    """
    YoutubeDL logger
    """
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
    def __init__(self, id, title="", time=time.time(), author="", thumbnail="", author_thumbnail="", duration=""):
        self.id               = str(id)
        self.url              = "https://www.youtube.com/watch?v=" + self.id
        self.title            = str(title)
        self.time             = int(time)
        self.author           = str(author)
        self.thumbnail        = str(thumbnail)
        self.author_thumbnail = str(author_thumbnail)
        self.duration         = str(duration)
        self.download_path    = None
        self.is_downloaded    = False
        self.download_button  = None

    def start_download(self, download_dir):
        """``download_dir`` : temp dir or user-defined."""
        self._download_dir = download_dir
        self.download_path = os.path.join(download_dir, f'{self.id}.mp3')
        # do not set extension explicitly bc of conversion done internally
        outtmpl = self.download_path.replace(".mp3", r".%(ext)s")
        self.ydl_opts = {
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
        with YoutubeDL(self.ydl_opts) as ydl:
            try:
                ydl.download([self.url])                
            except:
                self._download_fail()

    def download_video_metadata(self):
        with YoutubeDL(self.ydl_opts) as ydl:
            info_dict = ydl.extract_info(self.url, download=False)
            # print("\n"*6)
            self.title            = info_dict["title"]
            self.time             = info_dict["upload_date"] # YYYMMDD 
            self.author           = info_dict["uploader"]
            self.author_id        = info_dict["channel_id"]
            self.thumbnail        = info_dict["thumbnail"]
            self.author_thumbnail = info_dict["title"] 
            self.duration         = info_dict["duration"] # seconds

    def _progress_hook(self, d):
        # TODO more accurate conversion status after conversion:
        # download_button.icon = "file_download_done"
        # ? would require external FFmpeg usage
        
        if d['status'] == 'finished':
            print(f'Done downloading {self.title}. Converting...')
            self._download_success()
            self.is_downloaded = True

    def _download_success(self):
        self.download_button.icon = "download_success"
        
        # #? 'postprocessors' key to convert everything to mp3 is reccommended instead 
        # #? windows: see qmedia formats supported through DirectShow
        # for dirpath, dirnames, files in os.walk(self._download_dir):
        #     matching_video = [os.path.join(dirpath, file) for file in files if self.id in file]
        #     self.download_path = matching_video[0]

    def _download_fail(self):
        self.download_button.icon = "download_fail"

class InvalidUserDataFolder(Exception):
    pass

class YoutubeScraper():
    """
    Youtube subscription feed scraping object.
    """
    def __init__(self, max_videos, max_date, user_data=None, last_video_id=None):
        self.max_videos = max_videos
        self.max_date = max_date
        self.last_video_id = last_video_id
        self._user_data = user_data
    
    @property
    def user_data(self):
        return self._user_data

    @user_data.setter
    def user_data(self, user_data):
        if self.user_data == user_data:
            return
        self._user_data = user_data
    
    
    def get_videos_from_feed(self, from_local_dir=None) -> Dict[str, Video]: 
        """
        Return a dictionary of ``Video`` instances accessed by ``id``.
        """
        #TODO quit self.driver from mainwindow method
        #TODO on scrape button press try: quit self.driver
        #TODO new stop scraping button 
        
        
        driver_setup_success = self.setup_driver()
        if not driver_setup_success: 
            raise InvalidUserDataFolder("Select a valid browser user data folder.")
        print('\nRETRIEVING YOUTUBE DATA...\n')

        #* create new tab
        self.driver.execute_script("window.open('about:blank','_blank');")
        new_tab = self.driver.window_handles[1]
        self.driver.switch_to.window(new_tab)
        self.driver.get('https://www.youtube.com/feed/subscriptions')
        self.source = self.driver.page_source
        #TODO use beautiful soup to parse instead of selenium

        self.get_videos_metadata()
        
        self.videos_parsed = len(self.videos_json)
        print("on start, len(videos json) is", self.videos_parsed)
        
        my_videos = self.get_video_dict()
                
        self.stop_scraping()

        return my_videos
    
    def get_video_dict(self):
        """
        
        """
        #* get last video information
        last_video_parsed = self.parse_videos([self.videos_json[-1]])
        id, self._video = last_video_parsed.popitem()

        while self.videos_parsed < self.max_videos and self._video.time > self.max_date:  #it's using the same video every time
            print("\n"*3, "---------------------------------")
            print(f"video.time is {self._video.time}")
            print(f"self.videos_parsed are {self.videos_parsed}")
            print("\nScrolling down.\n")
            
            self.scroll_down()
            time.sleep(3)
            # TODO DEBUG: 
            # self.source is growing but not updating variable
            
            # WebDriverWait(self.driver, 10)
            previous_source = copy.deepcopy(self.source)
            self.source = self.driver.page_source
            print("previous_source == self.source ?")
            print(str(previous_source) == str(self.source))
            
            previous_json = copy.deepcopy(self.videos_json)
            self.get_videos_metadata()
            print("previous_json == self.videos_json ?")
            print(str(previous_json) == str(self.videos_json))
            
            self.videos_parsed = len(self.videos_json)
            print(f"self.videos_parsed (after new json) are {self.videos_parsed}")
            last_video_parsed = self.parse_videos([self.videos_json[-1]])
            id, self._video = last_video_parsed.popitem()
            
            with open("debug_old_youtube_page_source.txt","a+",encoding="utf8") as f:
                # global self.source
                f.write(str(previous_json))
            
            with open("debug_new_youtube_page_source.txt","a+",encoding="utf8") as f:
                # global self.source
                f.write(str(self.videos_json))
            
            
        return self.parse_videos(self.videos_json, id_stop=id)

    def parse_videos(self, videos_json, id_stop=None):
        #? new metadata to be as required + edit Video class accordingly
        
        #TODO use selenium and download metadata through youtubedl,
        # discard variable in source
        
        self.parse_strings = {
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
            current_video = self.create_video_dict_item(my_videos, item)
            videos_parsed += 1
            # TODO until user selected last video time or id (history button) -> qsettings
            
            #TODO FIX - uses the same current_video every time it scrolls
            
            print(f"current_video.time: {current_video.time} and max_date: {self.max_date}")
            if (
                videos_parsed >= self.max_videos or 
                # current_video.time < self.max_date or 
                current_video.id == id_stop
            ):
                break
                
        print("videos_json length :", len(videos_json))
        print("videos parsed :", videos_parsed)
        return my_videos
    
    def create_video_dict_item(self, my_videos, item):
        """
        Create a new ``Video`` value, accessed by ``id``.
        """
        for video_attr, parse_str in self.parse_strings.items():
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
                    match_attr = self.get_timestamp_from_relative_time(match_attr)
                setattr(my_videos[video_id], video_attr, match_attr)
        return my_videos[video_id]
    
    def stop_scraping(self):
        self.driver.quit()
        
    def scroll_down(self):
        self.driver.find_element_by_tag_name('html').send_keys(Keys.END)
        # self.driver.refresh()
        # for i in range(0, 20):
        #     self.driver.execute_script("window.scrollBy(0, 1000);")
        
    def setup_driver(self):
        if self._user_data is None:
            if platform == 'win32':
                self._user_data = os.path.expanduser('~') + r'\AppData\Local\Google\Chrome\User Data'
            elif platform == 'linux':
                self._user_data = os.path.expanduser('~') + r'/.config/google-chrome'

        #? automatic driver detection
        chrome_driver_path = ChromeDriverManager().install()
        os.environ["PATH"] += os.pathsep + chrome_driver_path

        options = webdriver.ChromeOptions()
        # options.add_argument("--no-sandbox")  # Bypass OS security model
        # options.add_argument("--disable-gpu")  # applicable to windows os only
        options.add_argument("--disable-dev-shm-usage")  # overcome limited resource problems
        options.add_argument("--disable-extensions")
        options.add_argument(r'--user-data-dir=' + self.user_data)
        options.add_argument("--headless")
        try:
            self.driver = webdriver.Chrome(chrome_driver_path, options=options)
        except WebDriverException:
            print("\n provide a valid user data folder \n")
            return False
        # self.driver.maximize_window()
        return True


    def get_timestamp_from_relative_time(self, time_string):
        """Return a timestamp from a relative ``time_string``, e.g. ``3 minutes ago``."""
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
        return int(timestamp)
    
    def get_videos_metadata(self):
        """
        Extract a list containing all videos' unparsed metadata.
        """
        try:
            #* variable containing rendered feed videos data
            json_var = re.findall(r'ytInitialData = (.*?);', self.source, re.DOTALL | re.MULTILINE)[0]
        except Exception as e:
            raise e 

        json_dict = json.loads(json_var)

        #* match all rendered video grids
        jsonpath_expr = parse('*..gridRenderer..gridVideoRenderer')

        #* get each video's data dict
        self.videos_json = [match.value for match in jsonpath_expr.find(json_dict)]