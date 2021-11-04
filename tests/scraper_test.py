import time
from pathlib import Path

import pytest
from src.resources import get_path
from src.youtube_scraper import YoutubeScraper


def test_scrape():
    BASEDIR = get_path(Path(__file__).parent)
    NOW = 1619255833
    THREE_DAYS = 3 * 24 * 3600
    MAX_DAYS = NOW - THREE_DAYS
    MAX_VIDEOS = 50
    scraper = YoutubeScraper(MAX_VIDEOS, MAX_DAYS)
    test_source_path = str(Path(BASEDIR, "test_youtube_page_source.txt"))
    my_videos = scraper.get_videos_from_feed(local_dir=test_source_path)
    assert my_videos["n8o5TYmoAiA"].id == "n8o5TYmoAiA"
    assert my_videos["n8o5TYmoAiA"].title == "Ultraboss - Pronto!"
    # my_videos["n8o5TYmoAiA"].time uses relative time
    assert my_videos["n8o5TYmoAiA"].duration == 241
    assert my_videos["n8o5TYmoAiA"].author == "NewRetroWave"
    assert my_videos["n8o5TYmoAiA"].author_id == "/c/NewRetroWave"
    assert my_videos["n8o5TYmoAiA"].url == "https://www.youtube.com/watch?v=n8o5TYmoAiA"
