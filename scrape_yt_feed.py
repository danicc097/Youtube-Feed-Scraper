import webbrowser
import pyautogui
import pyperclip
import re
import os
import json
from jsonpath_ng import jsonpath
from jsonpath_ng.ext import parse
import datetime
import urllib

#TODO
# base_yt_dl = "youtube-dl --extract-audio --audio-format mp3"

BASEDIR = os.path.dirname(os.path.realpath(__file__))
print(BASEDIR)


class Video():
    """Store video information for ease of use"""
    def __init__(
        self, id="", title="", time="", url="", author="", thumbnail="", author_thumbnail=""
    ):
        self.id = id
        self.title = title
        self.time = time
        self.author = author
        self.url = url
        self.thumbnail = thumbnail
        self.author_thumbnail = author_thumbnail


def get_my_videos(json_var):
    """Extract video metadata from feed to a dictionary accessed by video ID
    ``json_var`` : ytInitialData variable, containing rendered feed videos data"""

    my_videos = dict()

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
        'url': 'navigationEndpoint.commandMetadata.webCommandMetadata.url'
    }

    for i in range(len(videos_json)):
        for video_attr, parse_str in parse_strings.items():
            json_expr = parse(parse_str)
            matches = [match.value for match in json_expr.find(videos_json[i])]
            if not matches:
                match_attr = ""
            else:
                match_attr = matches[0]
                if video_attr == "id":
                    video_id = match_attr
                    my_videos[video_id] = Video()
                setattr(my_videos[video_id], video_attr, match_attr)
    return my_videos


def get_yt_source_text(from_local_dir=False, save_to_local_dir=False):
    """Opens a new browser window to get the feed page's source code"""

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
        with open(os.path.join(BASEDIR, "downloaded_source.json"), "r", encoding="utf-8") as f:
            json_var = f.read()

    if not from_local_dir and save_to_local_dir:
        with open(os.path.join(BASEDIR, "downloaded_source.json"), "a", encoding="utf-8") as f:
            f.write(json_var)

    return json.loads(json_var)


json_var = get_yt_source_text(from_local_dir=True)
my_videos = get_my_videos(json_var)

#### Quick view
i = 0
for id, video in my_videos.items():
    if i < 3:
        print(video.id)
        print(video.title)
        print(video.author)
        print(video.time)
        print(video.url)
        print(video.thumbnail)
        print(video.author_thumbnail)
        print("---------------------------")
        i += 1
    else:
        break
#### END Quick view
