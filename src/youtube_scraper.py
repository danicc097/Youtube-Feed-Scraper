import os
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
import time
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager


def setup_driver(user_data=None):
    if user_data is None:
        user_data = os.path.expanduser('~') + r'\AppData\Local\Google\Chrome\User Data'
    
    #? automatic driver detection
    chrome_driver_path = ChromeDriverManager().install()
    os.environ["PATH"] += os.pathsep + chrome_driver_path

    options = webdriver.ChromeOptions()
    # options.add_argument("--no-sandbox")  # Bypass OS security model
    # options.add_argument("--disable-dev-shm-usage")  # overcome limited resource problems
    options.add_argument("--disable-extensions")
    # options.add_argument("--disable-gpu")  # applicable to windows os only
    options.add_argument("--headless")
    options.add_argument(r'--user-data-dir=' + user_data)
    driver = webdriver.Chrome(chrome_driver_path, options=options)
    driver.minimize_window()

    return driver

def get_feed_source(max_videos,max_date):
    #TODO use user_data folder from GUI if available
    driver = setup_driver()
    print('\nRETRIEVING YOUTUBE DATA...\n')
    
    #* create new tab
    driver.execute_script("window.open('about:blank','_blank');")
    new_tab = driver.window_handles[1]
    driver.switch_to.window(new_tab)
    driver.get('https://www.youtube.com/feed/subscriptions')

    #TODO end of page (with driver as well) until video number or max date.
    while video_count < max_videos or video_date < max_date:
        scroll_down(driver)
        source=driver.page_source
        # TODO count grids. get date 
    driver.close()

    return str(source)

def scroll_down(driver):
    html = driver.find_element_by_tag_name('html')
    html.send_keys(Keys.END)
    time.sleep(1)
