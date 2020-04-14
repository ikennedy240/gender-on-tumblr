## import libraries
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException, StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import pandas as pd
import numpy as np
from datetime import datetime
import time
import os
import sys
import regex as re
import json


# set global vars
n_posts= 30
scrape_notes_n = 300
SCROLL_PAUSE_TIME = 1.1
note_mult = 3

# handles the driver for different systems
def make_driver(headless = False):
    # on mac we can just do this
    if sys.platform == 'darwin':
        if headless:
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument('--headless')
            driver = webdriver.Chrome(options = chrome_options)
        else:
            driver = webdriver.Chrome()
    # otherwise we need to specify where chromedriver is
    else:
        #chrome_options.binary_location = "/usr/bin/chromium"
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Chrome('/home/ikennedy/cl_daemon/resources/chromedriver', options = chrome_options)
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
    print("grab notes")
    print('wait time is',SCROLL_PAUSE_TIME*note_mult)
    time.sleep(SCROLL_PAUSE_TIME*note_mult)
    notes = current_post.find_element_by_css_selector('.note_link_current')
    ActionChains(driver).move_to_element(notes).click().perform()
    #time.sleep(SCROLL_PAUSE_TIME*note_mult)
    body = driver.find_element_by_tag_name("body")
    note_len = 0
    try:
        n_likes = driver.find_element_by_class_name('rollup-notes-summary-likes').text
        n_reblogs = driver.find_element_by_class_name('rollup-notes-summary-reblogs').text
    except:
        n_likes = 'unknown'
        n_reblogs = 'unknown'
    n_notes = driver.find_element_by_class_name('primary-message').text
    try_count = 0
    while(re.search('\d',n_notes) is None):
        n_notes = driver.find_element_by_class_name('primary-message').text
        try_count += 1
        time.sleep(SCROLL_PAUSE_TIME*note_mult)
        if try_count > 4:
            break
    try:
        element = WebDriverWait(driver, SCROLL_PAUSE_TIME*note_mult).until(EC.presence_of_element_located((By.CLASS_NAME,'rollup-notes-summary-likes')))
        ActionChains(driver).move_to_element(driver.find_element_by_class_name('rollup-notes-summary-likes')).click().perform()
        print('click success')
    except:
        print('no rollup')
        pass
    element = WebDriverWait(driver, SCROLL_PAUSE_TIME*note_mult).until(EC.presence_of_element_located((By.CLASS_NAME,'post-activity-note')))
    print('element is complete')
    print(element)
    notes = driver.find_elements_by_class_name('post-activity-note')
    try:
        n_notes_int = min(int(re.sub('\D','',n_notes)),scrape_notes_n)
    except:
        n_notes_int = 0
    while len(notes)<n_notes_int:
        try:
            post_activity_note = driver.find_element_by_class_name('post-activity-note')
            xoffset = post_activity_note.size['width'] - 10
            yoffset = round(post_activity_note.size['height']/2)
            ActionChains(driver).move_to_element_with_offset(post_activity_note, xoffset, yoffset).click().perform()
            body.send_keys(Keys.HOME,Keys.HOME)
            time.sleep(SCROLL_PAUSE_TIME*note_mult)
            notes = driver.find_elements_by_css_selector('.post-activity-note')
            #notes = notes + new_notes
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
    #print("sracpe post:", current_post.text)

    row_dict =  {}
    # grab post_id
    row_dict['post_id'] = current_post.get_attribute('data-post-id')

    #grab header info
    row_dict['source'] = current_post.get_attribute('data-tumblelog')

    #grab user info
    user_info = json.loads(current_post.get_attribute('data-json'))
    url = user_info['share_popover_data']
    user_info = user_info['tumblelog-data']
    row_dict['user_title'] = user_info['title']
    row_dict['user_description'] = user_info['description']

    # grab text
    try:
        row_dict['text'] = current_post.find_element_by_class_name('post_body').text
    except:
        row_dict['text'] = current_post.text

    # grab tags
    row_dict['tags'] = ', '.join([item.get_attribute('title') for item in current_post.find_elements_by_css_selector('.post_tag')])

    # grab post date
    # seems like this isn't available
    row_dict['scraped_time'] = datetime.now()

    # stable post url
    row_dict['url'] = url['post_url']

    # get some notes, yo
    driver.execute_script("arguments[0].scrollIntoView();", current_post)
    try:
        n_notes, n_reblogs, n_likes, likes, rebloggers = grab_notes(current_post, driver)
    except Exception as e:
        print('first try notes',e)
        try:
            n_notes, n_reblogs, n_likes, likes, rebloggers = grab_notes(current_post, driver, note_mult = 6)
        except Exception as e:
            print('second try notes',e)
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

def scrape_search(keyword, debug = False, recent = False, keyword_frame = None, post_status = None):
    # make a driver
    driver = make_driver()
    # set the url or the resent url
    url = 'https://www.tumblr.com/search/'+keyword
    if recent:
        url = 'https://www.tumblr.com/search/'+keyword+'/recent'
    # navigate to that url
    driver.get(url)
    # some extra time
    time.sleep(SCROLL_PAUSE_TIME)
    # initialize some data frames
    if keyword_frame is None:
        keyword_frame = pd.DataFrame()

    if post_status is None:
        post_status = pd.DataFrame()

    try_count = 0
    # while we have fewer posts than we want

    while keyword_frame.shape[0]<n_posts:
        # grap the raw posts
        try:
            posts = driver.find_elements_by_css_selector('article')
            n_now = post_status.shape[0]
            # update post_status with those posts
            post_status = post_status.append(pd.DataFrame({'text' : [post.text for post in posts], 'status' : 'waiting'}))
            post_status = post_status.drop_duplicates('text')
            post_status = post_status[post_status.text  != '']
            # if we didn't find more posts on the last scroll, try waiting longer
            if post_status.shape[0] == n_now:
                try_count += 1
                print("didn't add any new posts, try count = "+str(try_count))
                if try_count > 3:
                    print("Breaking because of Try Count, page not loading")
                    break
            posts = [post for post in posts if post.text in post_status.text[post_status.status == 'waiting'].values]
        except Exception as e:
            print("Get new posts failed with "+keyword)
            post_status.status[post_status.text.str.contains(pat = current_text, regex=False)] = 'error'
            driver.quit()
            return(scrape_search(keyword, debug, recent, keyword_frame, post_status))
        # loop throught the posts
        for current_post in posts:
            try:
                # make sure we have the post in post_status and that it's waiting
                if post_status.text.str.contains(pat = current_post.text, regex=False).any() and current_post.text  != '':
                    current_text = current_post.text
                    if (post_status.status[post_status.text.str.contains(pat = current_post.text, regex=False)] == 'waiting').any():
                        post_status.status[post_status.text.str.contains(pat = current_post.text, regex=False)] = 'processing'
                    else:
                        continue
                else:
                    continue
                # scrape the posts
                row_dict = scrape_post(current_post, driver)
                if row_dict['text'] == '':
                    row_dict['text'] = current_text
                # add it to the keword frame
                keyword_frame = keyword_frame.append(pd.DataFrame(row_dict, index = [0]))
                # update post status
                post_status.status[post_status.text.str.contains(pat = current_post.text, regex=False)] = 'complete'
            # if there's an error, print it and set the post status to error
            except Exception as e:
                print('error on scrape_post:'+current_text,e)
                post_status.status[post_status.text.str.contains(pat = current_text, regex=False)] = 'error'
                pass
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        print("collected "+str(keyword_frame.shape[0])+" posts for "+keyword)
        time.sleep(SCROLL_PAUSE_TIME+try_count)

    driver.quit()
    keyword_frame['keyword'] = keyword
    return(keyword_frame.reset_index(drop=True))


if __name__ == '__main__':
    #driver = make_driver()
    gender_list = pd.read_csv('masterlistofgender.txt')
    # notes = [scrape_note_counts(driver, x) for x in gender_list.gender]
    # gender_list['notes'] = pd.DataFrame(notes)[1]
    # gender_list['best_match'] = pd.DataFrame(notes)[0]
    # gender_list[gender_list.notes>2000].sort_values('notes', ascending = False).reset_index().drop('index',1)
    # gender_list.to_csv('masterlistofgender.txt', index=False)
    # user = 'queer-no-matter-what'
    keywords =  gender_list.sort_values('notes', ascending =  False).best_match
    keyword_frame = pd.DataFrame()
    for keyword in keywords[0:30]:
        file_exists = os.path.exists('tumblr_sample'+datetime.now().strftime('%Y_%m_%d')+'.csv')
        keyword_frame = scrape_search(keyword)
        keyword_frame['recent'] = False
        keyword_frame.to_csv('tumblr_sample'+datetime.now().strftime('%Y_%m_%d')+'.csv', mode = 'a', header = not file_exists, index = False)
        keyword_frame = scrape_search(keyword, recent = True)
        keyword_frame['recent'] = True
        keyword_frame.to_csv('tumblr_sample'+datetime.now().strftime('%Y_%m_%d')+'.csv', mode = 'a', header = not file_exists, index = False)

    #df = pd.read_csv('tumblr_sample2020_01_12.csv')
    df.keyword.value_counts()
    # (keyword_frame.text == '').head(20)
    #current_post = posts[3]
    keyword = 'demigender'
    current_post = posts[10]
    #debug == True
    #user_frame.to_csv('tumblr_sample.csv')
    #driver.quit()
    #keyword_frame.to_csv('tumblr_sample'+datetime.now().strftime('%Y_%m_%d'))
