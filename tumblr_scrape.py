## import libraries
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.common.keys import Keys
import pandas as pd
import numpy as np
import datetime
import time
import os
import sys
import regex as re

# set global vars

SCROLL_PAUSE_TIME = 1.5

# handles the driver for different systems
def make_driver(headless = False):
    # on mac we can just do this
    if sys.platform == 'darwin':
        chrome_options = webdriver.ChromeOptions()
        if headless:
            chrome_options.add_argument('--headless')
        driver = webdriver.Chrome(options = chrome_options)
    # otherwise we need to specify where chromedriver is
    else:
        #chrome_options.binary_location = "/usr/bin/chromium"
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Chrome('/home/ikennedy/apts_scrape/resources/chromedriver', options = chrome_options)
    return(driver)

def scrape_note_counts(driver,query,full=True):
    if(bool(re.search('gender', query))&full):
        full = scrape_note_counts(driver, query, full=False)
        split = scrape_note_counts(driver, re.sub('^gender','gender+',re.sub('gender$','+gender',query)), full=False)
        return([full, split][np.argmax([full[1], split[1]])])
    if(bool(re.search('binary', query))&full):
        full = scrape_note_counts(driver, query, full=False)
        split = scrape_note_counts(driver, re.sub('^binary','binary+',re.sub('binary$','+binary',query)), full=False)
        return([full, split][np.argmax([full[1], split[1]])])
    driver.get('https://www.tumblr.com/search/'+query)
    notes = driver.find_elements_by_css_selector('.note_link_current')
    notes = [re.sub('\D','',x.text) for x in notes]
    mean = np.mean([int(x) for x in notes if x != ''])
    if notes==[]: mean = 0
    return(query, mean)

def scroll_page(driver):


    # Get scroll height
    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        # Scroll down to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        # Wait to load page
        time.sleep(SCROLL_PAUSE_TIME)

        # Calculate new scroll height and compare with last scroll height
        new_height = driver.execute_script("return document.body.scrollHeight")
        #print('heightdif')
        #print(new_height,last_height)
        if new_height == last_height:
            break
        last_height = new_height
    return(driver)


def grab_notes(url):
    note_driver = make_driver(headless = True)
    note_driver.get(url)
    body = note_driver.find_element_by_tag_name("body")
    note_len = 0
    while True:
        try:
            note_driver.find_element_by_css_selector('.notes').click()
            body.send_keys(Keys.END)
            notes = note_driver.find_elements_by_css_selector('.note')
        except:
            break
        time.sleep(SCROLL_PAUSE_TIME)
        if note_len == len(notes):
            break
        else:
            note_len = len(notes)
    note_class = [item.get_attribute('class') for item in notes]
    likes = [item.find_element_by_css_selector('span').text for item in notes if re.search(' like ', item.get_attribute('class'))]
    reblogs = [item.find_element_by_css_selector('span').text for item in notes if re.search(' reblog ', item.get_attribute('class'))]
    likes = [like.split()[0] for like in likes if len(like.split())>0]
    rebloggers = [reblog.split()[0] for reblog in reblogs if len(reblog.split())>0]
    rebloged_from = [reblog.split()[-1] for reblog in reblogs if len(reblog.split())>0]
    note_driver.close()
    return((likes, rebloggers, rebloged_from))

def scrape_post(current_post):
    row_dict =  {}
    # grab post_id
    row_dict['post_id'] = current_post.get_attribute('data-post-id')

    #grab header info
    row_dict['source'] = ', '.join(list(set([item.text for item in current_post.find_elements_by_css_selector('.post-tumblelog-name')])))
    current_post.find_element_by_css_selector('.post-body').get_attribute('href')
    # grab text
    row_dict['text'] = ', '.join([item.text for item in current_post.find_elements_by_css_selector('.post-body')])

    # grab tags -> extract from text
    row_dict['tags'] = ', '.join([item.text for item in current_post.find_elements_by_css_selector('.tag-link')])

    # grab post date
    row_dict['post_date'] = ', '.join([item.text for item in current_post.find_elements_by_css_selector('.post-date')])

    # possibly stable post url
    row_dict['url'] = current_post.get_attribute('user')

    # get some notes, yo
    notes = current_post.find_element_by_css_selector('.post-notes')
    likes, rebloggers, rebloged_from = grab_notes(notes.get_attribute('href'))
    row_dict['likes'] = ', '.join(likes)
    row_dict['rebloggers'] = ', '.join(rebloggers)
    row_dict['rebloged_from'] = ', '.join(rebloged_from)
    return(row_dict)

# scroll the whole pages
def scrape_user(driver, user, debug):
    driver.get('https://'+user+'.tumblr.com/')
    if not debug:
        driver = scroll_page(driver)
    posts = driver.find_elements_by_css_selector('article')
    if debug:
        posts = posts[:10]
    user_frame = pd.DataFrame()
    for current_post in posts:
        row_dict = scrape_post(current_post)
        user_frame = user_frame.append(pd.DataFrame(row_dict, index = [0]))
    user_frame['user'] = user
    return(driver, user_frame)



if __name__ == '__main__':
    driver = make_driver()
    gender_list = pd.read_csv('masterlistofgender.txt')
    notes = [scrape_note_counts(driver, x) for x in gender_list.gender]
    gender_list['notes'] = pd.DataFrame(notes)[1]
    gender_list['best_match'] = pd.DataFrame(notes)[0]
    gender_list[gender_list.notes>2000].sort_values('notes', ascending = False).reset_index().drop('index',1)
    gender_list.to_csv('masterlistofgender.txt', index=False)
    user = 'queer-no-matter-what'
    current_post = posts[13]
    driver, user_frame = scrape_user(driver, user, debug = True)
    driver.close()
