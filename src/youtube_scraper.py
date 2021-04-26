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
import os
import re
import time
from logging import info
from sys import platform
from typing import Any, Dict, List, Optional, Set, Tuple

from bs4 import BeautifulSoup
from lxml import etree
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
import selenium.webdriver.support.expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from youtube_dl import YoutubeDL

from .resources import get_sec_from_hhmmss, get_timestamp_from_relative_time


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


class InvalidUserDataFolder(Exception):
    pass


class MissingHtmlElements(Exception):
    pass


class Video():
    """
    Store video information for ease of use. 
    Download it in parallel using ``start_download`` in a worker.
    """
    def __init__(
        self,
        id,
        title="",
        time=time.time(),
        author="",
        author_id="",
        duration=0,
    ):
        self.id               = str(id)
        self.url              = "https://www.youtube.com/watch?v=" + self.id
        self.title            = str(title)
        self.time             = int(time)
        self.author           = str(author)
        self.author_id        = str(author_id)
        self.duration         = int(duration) # hh:mm:ss format
        self.thumbnail        = None
        self.author_thumbnail = None
        self.download_path    = None
        self.is_downloaded    = False
        self.download_button  = None

    def start_download(self, download_dir):
        """
        ``download_dir`` : temp dir or user-defined.
        """
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
        """
        Downloads additional metadata through youtube-dl.
        """
        info_dict = YoutubeDL().extract_info(self.url, download=False)
        self.thumbnail = info_dict["thumbnail"]
        self.duration  = info_dict["duration"]
        # self.author_thumbnail =

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


    def get_videos_from_feed(self, local_dir=None) -> Dict[str, Video]:
        """
        Return a dictionary of ``Video`` instances accessed by ``id``.
        """


        driver_setup_success = self._setup_driver()
        if not driver_setup_success:
            raise InvalidUserDataFolder("Select a valid browser user data folder.")
        print('\nRETRIEVING YOUTUBE DATA...\n')
        
        if local_dir:
            with open(local_dir, "r", encoding="utf8") as f:
                self.source = f.read()
        else:
            #* create new tab
            self.driver.execute_script("window.open('about:blank','_blank');")
            new_tab = self.driver.window_handles[1]
            self.driver.switch_to.window(new_tab)
            self.driver.get('https://www.youtube.com/feed/subscriptions')
            time.sleep(8)
            self.source = self.driver.page_source
        
        
        
        # TODO all author profile thumbnails in sidebar>subscriptions

        # self.extract_author_thumbnails()

        self.get_videos_metadata()

        self.stop_scraping()

        return self.my_videos

    def stop_scraping(self):
        """
        Quit driver gracefully.
        """
        self.driver.quit()

    def _scroll_down(self):
        self.driver.find_element_by_tag_name('html').send_keys(Keys.END)
        # self.driver.refresh()
        # for i in range(0, 20):
        #     self.driver.execute_script("window.scrollBy(0, 1000);")

    def _setup_driver(self):
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
        options.add_argument('--window-size=1920,1080') #enable clicking in headles
        options.add_argument(r'--user-data-dir=' + self.user_data)
        options.add_argument("--headless")
        try:
            self.driver = webdriver.Chrome(chrome_driver_path, options=options)
        except WebDriverException:
            print("\n provide a valid user data folder \n")
            return False
        # self.driver.maximize_window()
        return True

    def get_videos_metadata(self):
        """
        Extract a list containing all videos' unparsed metadata.
        """
        upload_dates, video_links, authors, \
            author_channels, video_durations, video_titles = self.extract_video_elements()


        last_video_upload_date = get_timestamp_from_relative_time(upload_dates[-1])
        
        # check if enough data has been gathered:
        while len(video_links) < self.max_videos and last_video_upload_date > self.max_date:
            print("\nScrolling down.\n")
            print(len(video_links))
            self._scroll_down()
            time.sleep(5)
            self.source = self.driver.page_source
            upload_dates, video_links, authors, \
            author_channels, video_durations, video_titles = self.extract_video_elements()
            last_video_upload_date = get_timestamp_from_relative_time(upload_dates[-1])

        self.my_videos = {}
        
        for i in range(len(video_links)):
            if len(self.my_videos) < self.max_videos:
                # print(self.max_videos, "and current dict len is: " ,len(self.my_videos))
                
                video_id = video_links[i].split("/watch?v=")[-1].split("&")[0]
                self.my_videos[video_id] = Video(
                    id        = video_id,
                    title     = video_titles[i],
                    author    = authors[i],
                    author_id = author_channels[i],
                    duration  = get_sec_from_hhmmss(video_durations[i]),
                    time      = get_timestamp_from_relative_time(upload_dates[i]),
                )
                
                # TODO RETURN self.my_videos AND DO THIS IN GUI, PROCESSING EVENTS
                # alternative: 
                # see https://stackoverflow.com/questions/55088847/pyqt5-emit-signal-from-another-module
            else:
                break
        
    def extract_author_thumbnails(self):
        """
        Extracts channel profile pictures from the sidebar subscriptions list.
        """
        wait = WebDriverWait(self.driver, 5)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#endpoint')))
        
        #* the sidebar is opened by default. This hides the subscriptions button
        wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="guide-icon"]')))
        self.driver.find_element_by_xpath('//*[@id="guide-icon"]').click() 
        
        wait.until(EC.presence_of_element_located( \
            (By.XPATH, '//*[@id="endpoint"]//*[@attribute="enable-empty-style-class"]'))
                )
        self.driver.find_element_by_xpath( \
            '/*[@id="endpoint"]//*[@attribute="enable-empty-style-class"]').click() 
        
        
        soup = BeautifulSoup(self.source, "html.parser")
        dom = etree.HTML(str(soup))
        self.thumbnails = dom.xpath('//*[@id="img"]/./@src')  
        self.thumbnails_authors = dom.xpath('//*[@id="endpoint"]/@title')
        print("\n\n")
        print("len of subs thumbnails pictures: ", len(self.thumbnails), len(self.thumbnails_authors))
        print("\n\n")
        for tb, tb_autor in zip(self.thumbnails, self.thumbnails_authors):
            print(tb, " - ", tb_autor)  

    def extract_video_elements(self):
        """
        Parses the page source to get relevant video information.
        """
        soup = BeautifulSoup(self.source, "html.parser")
        dom = etree.HTML(str(soup))

        upload_dates    = dom.xpath('//*[@id="metadata-line"]/span[2]/text()')
        video_links     = dom.xpath('//*[@id="video-title"]/./@href')
        authors         = dom.xpath('//*[@id="text"]/a/text()')
        author_channels = dom.xpath('//*[@id="text"]/a/@href')
        video_durations = dom.xpath('//*[@id="overlays"]/ytd-thumbnail-overlay-time-status-renderer/span/text()')
        video_titles    = dom.xpath('//*[@id="video-title"]/./@title')

        print(len(upload_dates))
        print(len(video_links))
        print(len(authors))
        print(len(author_channels))
        print(len(video_durations))
        print(len(video_titles))

        # if not len(set(
        #         [
        #             len(upload_dates),
        #             len(video_links),
        #             len(authors),
        #             len(author_channels),
        #             len(video_durations),
        #             len(video_titles)
        #         ]
        #         )) == 1:
        #     raise MissingHtmlElements("Couldn't extract all required information. Please try again.")

        return upload_dates,video_links,authors,author_channels,video_durations,video_titles
