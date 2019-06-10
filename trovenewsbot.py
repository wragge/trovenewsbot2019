import tweepy
import arrow
import random
import time
import requests
import redis
import feedparser
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import re
import json
import os
import argparse
from newspaper import Article
from credentials import *

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token_key, access_token_secret)

api = tweepy.API(auth)

redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

START_YEAR = 1803
END_YEAR = 1995
ABC_RSS = 'https://www.abc.net.au/news/feed/51120/rss.xml'

def get_url(tweet):
    urls = tweet['entities']['urls']
    try:
        url = urls[0]['expanded_url']
    except (IndexError, KeyError):
        try:
            url = urls[0]['url']
        except (IndexError, KeyError):
            url = None
    return url


def get_url_keywords(url):
    article = Article(url)
    article.download()
    article.parse()
    article.nlp()
    keywords = article.keywords
    if not keywords:
        keywords = article.title.split(' ')
    query = '({})'.format(' OR '.join(keywords))
    return query


def check_for_any(query):
    if '#any' in query:
        query = query.replace('#any', '').strip()
        query = '({})'.format(' OR '.join(query.split()))
    return query


def extract_date(query):
    query = query.replace('#year', '').strip()
    try:
        year = re.search(r'(\b\d{4}\b)', query).group(1)
    except AttributeError:
        date_param = ''
    else:
        query = query.replace(year, '').strip()
        date_param = 'date:[{0} TO {0}]'.format(year)
        query = check_for_any(query)
    return ' '.join([query, date_param])


def extract_id(query):
    try:
        article_id = re.search(r'(\b\d+\b)', query).group(1)
    except AttributeError:
        article_id = 'missing'
    return article_id


def process_tweet(tweet_json):
    tweet = json.loads(tweet_json)
    tweet_id = tweet['id']
    user = tweet['user']['screen_name']
    query, sort, random, illustrated, article_id, categories, hello = parse_tweet(tweet)
    if hello is True:
        article, message, illustrated = random_article()
        if article:
            message = 'Greetings human! Feed me keywords to search newspapers. Enjoy this random selection.'
        else:
            message = 'Greetings human! Feed me keywords to search newspapers.'
    elif not query:
        article, message, illustrated = random_article(illustrated=illustrated, categories=categories)
        if article:
            message = 'No search terms detected! Enjoy this random selection.'
    elif article_id:
        if article_id == 'missing':
            article, message, illustrated = random_article(illustrated=illustrated)
            if article:
                message = 'No article id detected! Enjoy this random selection.'
        else:
            article = get_article_by_id(article_id)
            if article:
                message = 'Found!'
            else:
                article, message, illustrated = random_article(illustrated=illustrated)
                if article:
                    message = 'Not found! Enjoy this random selection.'
    else:
        article = reply_article(query=query, sort=sort, random=random, illustrated=illustrated, categories=categories)
        message = ''
        if not article:
            article, message, illustrated = random_article()
            if article:
                message = 'No results found! Enjoy this random selection instead.'
    send_tweet(article, message, user, tweet_id, illustrated=illustrated)
    time.sleep(20)


def parse_tweet(tweet):
    query = None
    random = False
    hello = False
    illustrated = False
    article_id = None
    categories = []
    sort = 'relevance'
    text = tweet['text'].strip()
    query = text[14:].replace(u'\u201c', '"').replace(u'\u201d', '"').replace(u'\u2019', "'")
    if re.search(r'\bhello\b', text, re.IGNORECASE):
        query = ''
        random = True
        hello = True
    else:
        if '#luckydip' in query:
            # Get a random article
            query = query.replace('#luckydip', '').strip()
            random = True
        if '#illustrated' in query:
            # Get a random article
            query = query.replace('#illustrated', '').strip()
            illustrated = True
        if '#earliest' in query:
            query = query.replace('#earliest', '').strip()
            sort = 'dateasc'
        if '#latest' in query:
            query = query.replace('#latest', '').strip()
            sort = 'datedesc'
        if '#article' in query:
            query = query.replace('#article', '').strip()
            categories.append('Article')
        if '#advertising' in query:
            query = query.replace('#advertising', '').strip()
            categories.append('Advertising')
        if '#id' in query:
            query = query.replace('#id', '').strip()
            article_id = extract_id(query)
        url = get_url(tweet)
        if url:
            query = get_url_keywords(url)
        else:
            if '#year' in query:
                query = extract_date(query)
            else:
                query = check_for_any(query)
    return (query, sort, random, illustrated, article_id, categories, hello)


def get_article_by_id(article_id):
    params = {
        'encoding': 'json',
        'key': api_key,
        'reclevel': 'full'
    }
    response = requests.get('https://api.trove.nla.gov.au/newspaper/{}'.format(article_id), params=params)
    data = response.json()
    try:
        article = data['article']
    except (KeyError, IndexError, TypeError):
        article = None
    return article


def reply_article(query, sort, random, illustrated, categories):
    trove_url = None
    if not random:
        article = get_article(query, random=random, sort=sort, illustrated=illustrated, categories=categories)
    else:
        retries = 0
        while not trove_url:
            if retries < 60:
                article = get_article(query, random=random, sort=sort, illustrated=illustrated, categories=categories)
                try:
                    trove_url = article['troveUrl']
                except (KeyError, TypeError):
                    pass
                retries += 1
                time.sleep(1)
            else:
                article = None
                break
    return article


def send_tweet(article, message=None, user=None, tweet_id=None, illustrated=False):
    if article:
        url = 'http://nla.gov.au/nla.news-article{}'.format(article['id'])
        thumbnail = get_page_thumbnail(article['id'], 800, illustrated=illustrated)
        media_response = api.media_upload(thumbnail)
        media_ids = [media_response.media_id]
        article_date = arrow.get(article['date'], 'YYYY-MM-DD').format('D MMM YYYY')
        newspaper = re.sub(r'\(.+?\)$', '', article['title']['value']).strip()
        chars = 240 - (len(message) + len(article_date) + len(newspaper) + 10)
        title = article['heading']
        if len(title) > chars:
            title = '{}…'.format(article['heading'][:chars])
        status = "{message}{date}: '{title}', {newspaper}, {url}".format(message='{} '.format(message) if message else '', date=article_date, title=title, newspaper=newspaper, url=url)
    else:
        status = message
        media_ids = []
    print(status)
    if tweet_id:
        #pass
        api.update_status('@{} {}'.format(user, status), media_ids=media_ids, in_reply_to_status_id=tweet_id)
    else:
        #pass
        api.update_status(status, media_ids=media_ids)
    try:
        os.remove(thumbnail)
    except FileNotFoundError:
        pass


def get_random_year():
    year = random.randint(START_YEAR, END_YEAR)
    return 'date:[{0} TO {0}]'.format(year)


def get_random_newspaper(decade, illustrated):
    params = {
        'q': ' ',
        'zone': 'newspaper',
        'l-category': 'Article',
        'l-decade': decade,
        'encoding': 'json',
        'facet': 'title',
        'key': api_key
    }
    if illustrated:
        params['l-illustrated'] = 'y'
    response = requests.get('https://api.trove.nla.gov.au/result', params=params)
    data = response.json()
    titles = data['response']['zone'][0]['facets']['facet']['term']
    title = random.choice(titles)
    start = random.randint(0, int(title['count']))
    params.pop('facet')
    params['l-title'] = title['search']
    params['s'] = start
    return params


def get_random_decade(illustrated=False, categories=['Article']):
    params = {
        'q': ' ',
        'zone': 'newspaper',
        'encoding': 'json',
        'facet': 'decade',
        'key': api_key
    }
    if illustrated:
        params['l-illustrated'] = 'y'
    for category in categories:
        params['l-category'] = category
    response = requests.get('https://api.trove.nla.gov.au/result', params=params)
    data = response.json()
    decades = data['response']['zone'][0]['facets']['facet']['term']
    decade = random.choice(decades)
    params.pop('facet')
    if int(decade['count']) > 500000:
        params = get_random_newspaper(decade['search'], illustrated)
    else:
        start = random.randint(0, int(decade['count']))
        params['s'] = start
        params['l-decade'] = decade['search']
    return params


def get_start(params):
    response = requests.get('https://api.trove.nla.gov.au/result', params=params)
    print(response.url)
    data = response.json()
    total = int(data['response']['zone'][0]['records']['total'])
    print(total)
    return random.randint(0, total)


def get_article(query, random=False, start=0, sort='relevance', illustrated=False, categories=[]):
    '''
    Search for an article from Trove using the supplied parameters.
    '''
    if query:
        params = {
            'q': query,
            'zone': 'newspaper',
            'encoding': 'json',
            'n': 1,
            'sortby': sort,
            'key': api_key
        }
        if illustrated:
            params['l-illustrated'] = 'y'
        for category in categories:
            params['l-category'] = category
    if random:
        if query:
            start = get_start(params)
            params['s'] = start
            params['reclevel'] = 'full'
        else:
            params = get_random_decade(illustrated=illustrated, categories=['Article'])
            params['reclevel'] = 'full'
    print(params)
    response = requests.get('https://api.trove.nla.gov.au/result', params=params)
    data = response.json()
    try:
        article = data['response']['zone'][0]['records']['article'][0]
    except (KeyError, IndexError, TypeError):
        article = None
    return article


def random_tweet():
    article, message, illustrated = random_article()
    send_tweet(article, message=message, illustrated=illustrated)


def random_article(illustrated=False, categories=[]):
    # updated, illustrated -> newspaper, newspaper -> decade
    options = ['updated', 'any', 'illustrated']
    option = random.choice(options)
    print(option)
    if illustrated is True:
        query = None
    elif option == 'updated':
        now = arrow.utcnow()
        yesterday = now.shift(days=-1)
        date = '{}T00:00:00Z'.format(yesterday.format('YYYY-MM-DD'))
        query = 'lastupdated:[{} TO *]'.format(date)
    elif option == 'any':
        query = None
    elif option == 'illustrated':
        query = None
        illustrated = True
    trove_url = None
    retries = 0
    while not trove_url:
        if retries < 60:
            article = get_article(query, random=True, illustrated=illustrated, categories=categories)
            try:
                trove_url = article['troveUrl']
            except (KeyError, TypeError):
                pass
            retries += 1
            time.sleep(1)
        else:
            article = None
            message = 'Error! I was unable to obtain an article!'
            break
    if article:
        if query and int(article['correctionCount']) > 0:
            message = 'Updated!'
        elif query:
            message = 'New!'
        else:
            message = 'Found!'
    return (article, message, illustrated)


def get_box(zones):
    '''
    Loop through all the zones to find the outer limits of each boundary.
    Return a bounding box around the article.
    '''
    left = 10000
    right = 0
    top = 10000
    bottom = 0
    page_id = zones[0]['data-page-id']
    for zone in zones:
        if int(zone['data-x']) < left:
            left = int(zone['data-x'])
    for zone in zones:
        if int(zone['data-x']) < (left + 200):
            if int(zone['data-y']) < top:
                top = int(zone['data-y'])
            if (int(zone['data-x']) + int(zone['data-w'])) > right:
                right = int(zone['data-x']) + int(zone['data-w'])
            if (int(zone['data-y']) + int(zone['data-h'])) > bottom:
                bottom = int(zone['data-y']) + int(zone['data-h'])
    # For a square image
    if bottom > top + (right - left):
        bottom = top + (right - left)
    return {'page_id': page_id, 'left': left, 'top': top, 'right': right, 'bottom': bottom}


def get_illustration(zone):
    page_id = zone['data-page-id']
    left = int(zone['data-x'])
    right = int(zone['data-x']) + int(zone['data-w'])
    top = int(zone['data-y'])
    bottom = int(zone['data-y']) + int(zone['data-h'])
    return {'page_id': page_id, 'left': left, 'top': top, 'right': right, 'bottom': bottom}


def get_article_box(article_url, illustrated=False):
    '''
    Positional information about the article is attached to each line of the OCR output in data attributes.
    This function loads the HTML version of the article and scrapes the x, y, and width values for each line of text 
    to determine the coordinates of a box around the article.
    '''
    response = requests.get(article_url)
    soup = BeautifulSoup(response.text, 'lxml')
    # Lines of OCR are in divs with the class 'zone'
    # 'onPage' limits to those on the current page
    illustrations = soup.select('div.illustration.onPage')
    if illustrations and illustrated is True:
        zone = illustrations[0].parent
        box = get_illustration(zone)
    else:
        zones = soup.select('div.zone.onPage')
        box = get_box(zones)
    return box


def get_page_thumbnail(article_id, size, illustrated=False):
    '''
    Extract a square thumbnail of the article from the page image, save it, and return the filename(s).
    '''
    images = []
    # Get position of article on the page(s)
    box = get_article_box('http://nla.gov.au/nla.news-article{}'.format(article_id), illustrated=illustrated)
    # print(box)
    # Construct the url we need to download the page image
    page_url = 'https://trove.nla.gov.au/ndp/imageservice/nla.news-page{}/level{}'.format(box['page_id'], 7)
    # Download the page image
    response = requests.get(page_url)
    # Open download as an image for editing
    img = Image.open(BytesIO(response.content))
    # Use coordinates of top line to create a square box to crop thumbnail
    points = (box['left'], box['top'], box['right'], box['bottom'])
    # Crop image to article box
    cropped = img.crop(points)
    # Resize if necessary
    if size:
        cropped.thumbnail((size, size), Image.ANTIALIAS)
    # Save and display thumbnail
    cropped_file = 'nla.news-article{}-{}.jpg'.format(article_id, box['page_id'])
    cropped.save(cropped_file)
    return cropped_file

def reply_abc():
    trove_url = None
    news = feedparser.parse(ABC_RSS)
    latest_url = news.entries[0].link
    try:
        last_url = redis_client.get('last_abc_link').decode('utf-8')
    except AttributeError:
        last_url = None
    if latest_url != last_url:
        redis_client.set('last_abc_link', latest_url)
        query = get_url_keywords(latest_url)
        retries = 0
        while not trove_url:
            if retries < 60:
                article = get_article(query)
                try:
                    trove_url = article['troveUrl']
                except (KeyError, TypeError):
                    pass
                retries += 1
                time.sleep(1)
            else:
                article = None
                break
        if article:
            message = 'Found in response to @abcnews latest at {}!'.format(latest_url)
            send_tweet(article, message, user=None, tweet_id=None, illustrated=False)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('task')
    args = parser.parse_args()
    if args.task == 'random':
        random_tweet()
    elif args.task == 'abc':
        reply_abc()
