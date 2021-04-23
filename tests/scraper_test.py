
from src.youtube_scraper import YoutubeScraper
from src.resources import get_path
import time
from pathlib import Path

BASEDIR = get_path(Path(__file__).parent)

NOW = time.time()
THREE_DAYS = 3 * 24 * 3600
MAX_DAYS = NOW - THREE_DAYS
MAX_VIDEOS = 5

scraper = YoutubeScraper(MAX_VIDEOS, MAX_DAYS)
test_source_path = str(Path(BASEDIR, "test_youtube_page_source.txt"))
my_videos = scraper.get_videos_from_feed(from_local_dir=test_source_path)


for id, video in my_videos.items():
    print(f"id :{id}")
