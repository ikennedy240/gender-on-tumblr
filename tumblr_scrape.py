## import libraries
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import pandas as pd
import numpy as np
import datetime
import time
import os
import sys
import regex as re
import json

# set global vars
n_posts= 20
SCROLL_PAUSE_TIME = 1.5
note_mult = 3

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

def grab_notes(current_post, driver, note_mult = 3):
    print("grab notes:", current_post.text)
    print('wait time is',SCROLL_PAUSE_TIME*note_mult)
    time.sleep(SCROLL_PAUSE_TIME*note_mult)
    notes = current_post.find_element_by_css_selector('.note_link_current')
    ActionChains(driver).move_to_element(notes).click().perform()
    #time.sleep(SCROLL_PAUSE_TIME*note_mult)
    element = WebDriverWait(driver, 40).until(
                EC.presence_of_element_located((By.CLASS_NAME,'rollup-notes-summary-likes')))
    body = driver.find_element_by_tag_name("body")
    note_len = 0
    n_likes = driver.find_element_by_class_name('rollup-notes-summary-likes').text
    n_reblogs = driver.find_element_by_class_name('rollup-notes-summary-reblogs').text
    n_notes = driver.find_element_by_class_name('primary-message').text
    ActionChains(driver).move_to_element(driver.find_element_by_class_name('rollup-notes-summary-likes')).click().perform()
    element = WebDriverWait(driver, 40).until(
                EC.presence_of_element_located((By.CLASS_NAME,'post-activity-note')))
    notes = driver.find_elements_by_css_selector('.post-activity-note')
    while len(notes)<200:
        try:
            post_activity_note = driver.find_element_by_class_name('post-activity-note')
            xoffset = post_activity_note.size['width'] - 10
            yoffset = round(post_activity_note.size['height']/2)
            ActionChains(driver).move_to_element_with_offset(post_activity_note, xoffset, yoffset).click().perform()
            body.send_keys(Keys.HOME,Keys.HOME,Keys.HOME,Keys.HOME)
            time.sleep(SCROLL_PAUSE_TIME*note_mult)
            new_notes = driver.find_elements_by_css_selector('.post-activity-note')
            notes = notes + new_notes
        except Exception as e:
            print('grabbing notes', current_post.get_attribute('data-tumblelog'), e)
            break
        if note_len == len(notes):
            # if we didn't add any notes, try making the pause time longer
            # this partially depends on loading times
            note_mult =+ 1
            print("increased note pause time to",note_mult)
            if note_mult >=6:
                # break once we're at 6* pause time
                break
        else:
            note_len = len(notes)
    likes = [item.text for item in notes if re.search(' like ', item.get_attribute('class'))]
    rebloggers = [item.text for item in notes if re.search(' reblog ', item.get_attribute('class'))]
    return((n_notes, n_reblogs, n_likes, likes, rebloggers))

def scrape_post(current_post, driver):
    print("sracpe post:", current_post.text)
    # shit, this pretty workflow doesn't work because the css is different on different tumblr pages
    # but it works well for search pages!!
    row_dict =  {}
    # grab post_id
    row_dict['post_id'] = current_post.get_attribute('data-post-id')

    #grab header info
    row_dict['source'] = current_post.get_attribute('data-tumblelog')
    #current_post.find_element_by_css_selector('.post-body').get_attribute('href')

    #grab user info
    user_info = json.loads(current_post.get_attribute('data-json'))
    url = user_info['share_popover_data']
    user_info = user_info['tumblelog-data']
    row_dict['user_title'] = user_info['title']

    row_dict['user_description'] = user_info['description']

    # grab text
    row_dict['text'] = current_post.find_element_by_class_name('post_body').text

    # grab tags
    row_dict['tags'] = ', '.join([item.get_attribute('title') for item in current_post.find_elements_by_css_selector('.post_tag')])

    # grab post date
    # seems like this isn't available
    # row_dict['post_date'] = ', '.join([item.text for item in current_post.find_elements_by_xpath(".//*[contains(@class, 'date')]")])

    # stable post url
    row_dict['url'] = url['post_url']

    # get some notes, yo
    try:
        n_notes, n_reblogs, n_likes, likes, rebloggers, rebloged_from = grab_notes(current_post, driver)
    except Exception as e:
        print('first try notes', current_post.get_attribute('data-tumblelog'),e)
        try:
            n_notes, n_reblogs, n_likes, likes, rebloggers = grab_notes(current_post, driver, note_mult = 6)
        except Exception as e:
            print('second try notes', current_post.get_attribute('data-tumblelog'),e)
            n_notes, n_reblogs, n_likes, likes, rebloggers = ('could not find notes', '','','','')

    row_dict['n_notes'] =  n_notes
    row_dict['n_reblogs'] =  n_reblogs
    row_dict['n_likes'] =  n_likes
    row_dict['likes'] = ', '.join(likes)
    row_dict['rebloggers'] = ', '.join(rebloggers)
    return(row_dict)

# scroll the whole pages
def scrape_user(driver, user, debug):
    driver.get('https://'+user+'.tumblr.com/')
    if not debug:
        driver = scroll_page(driver)

    # let's see if there are articles, then we can use our existing scrape_post anything
    posts = driver.find_elements_by_css_selector('article')
    type = 'article'
    if posts == []:
        posts = driver.find_elements_by_css_selector('.post')
        type = 'post'
    if posts == []:
        posts = driver.find_elements_by_css_selector('.entry')
        type = 'post'
    if debug:
        posts = posts[:5]
    user_frame = pd.DataFrame()
    for current_post in posts:
        try:
            row_dict = scrape_post(current_post, type)
            user_frame = user_frame.append(pd.DataFrame(row_dict, index = [0]))
        except:
            pass
    user_frame['user'] = user
    return(driver, user_frame)

def scrape_search(keyword, debug = True):
    driver = make_driver()
    url = 'https://www.tumblr.com/search/'+keyword
    driver.get(url)
    time.sleep(SCROLL_PAUSE_TIME)
    posts = driver.find_elements_by_css_selector('article')
    while len(posts)<n_posts:
        scroll_page(driver)
        posts = driver.find_elements_by_css_selector('article')
    keyword_frame = pd.DataFrame()
    if debug:
        posts = posts[:5]
    for current_post in posts:
        try:
            row_dict = scrape_post(current_post, driver)
            keyword_frame = keyword_frame.append(pd.DataFrame(row_dict, index = [0]))
        except Exception as e:
            print('scrape_search', current_post.get_attribute('data-tumblelog'),e)
            pass
    driver.quit()
    keyword_frame['keyword'] = keyword
    return(keyword_frame)


if __name__ == '__main__':
    driver = make_driver()
    gender_list = pd.read_csv('masterlistofgender.txt')
    # notes = [scrape_note_counts(driver, x) for x in gender_list.gender]
    # gender_list['notes'] = pd.DataFrame(notes)[1]
    # gender_list['best_match'] = pd.DataFrame(notes)[0]
    # gender_list[gender_list.notes>2000].sort_values('notes', ascending = False).reset_index().drop('index',1)
    # gender_list.to_csv('masterlistofgender.txt', index=False)
    # user = 'queer-no-matter-what'
    keywords =  gender_list.sort_values('notes', ascending =  False).best_match
    keyword_frame = pd.DataFrame()
    for keyword in keywords[:10]:
        keyword_frame = keyword_frame.append(scrape_search(keyword))
    current_post = posts[2]
    debug = True
    user_frame.to_csv('tumblr_sample.csv')
    driver.close()
    likes = keyword_frame[keyword_frame.post_id == '145066979045'].likes.values
    reblogs = keyword_frame[keyword_frame.post_id == '145066979045'].rebloggers.values
    rebloged_from = keyword_frame[keyword_frame.post_id == '145066979045'].rebloged_from.values

len(rebloged_from[0])
