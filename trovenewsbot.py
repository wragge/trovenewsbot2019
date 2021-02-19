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
from pathlib import Path
from newspaper import Article
from credentials import *
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

s = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[ 502, 503, 504 ])
s.mount('https://', HTTPAdapter(max_retries=retries))
s.mount('http://', HTTPAdapter(max_retries=retries))

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token_key, access_token_secret)

api = tweepy.API(auth)

redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

API_URL = 'http://api.trove.nla.gov.au/v2/result'
START_YEAR = 1803
END_YEAR = 1995
ABC_RSS = 'https://www.abc.net.au/news/feed/51120/rss.xml'
GUARDIAN_RSS = 'https://www.theguardian.com/australia-news/rss'
NEWS_FEEDS = [
    {
        'rss': 'https://www.abc.net.au/news/feed/51120/rss.xml',
        'source': 'abc',
        'handle': '@abcnews'
    },
    {
        'rss': 'https://www.theguardian.com/australia-news/rss',
        'source': 'guardian',
        'handle': '@GuardianAus'
    }
]

YEAR_WEIGHTS = [526, 619, 430, 367, 134, 155, 237, 274, 228, 215, 234, 239, 226, 644, 1068, 1249, 1152, 1275, 1005, 1033, 1156, 1646, 3366, 5201, 6537, 6726, 8320, 8369, 10311, 13732, 15438, 18704, 20389, 20553, 21697, 25191, 31159, 40450, 43583, 44264, 45968, 51377, 60228, 58794, 59503, 60302, 59698, 78726, 93422, 77328, 89716, 111809, 152862, 165260, 167962, 170506, 192157, 203666, 222964, 231360, 236359, 250078, 270535, 286531, 294045, 301851, 323274, 368748, 357135, 381901, 419226, 434680, 465013, 476043, 497516, 567221, 605369, 620926, 663699, 743779, 766454, 852461, 908552, 992953, 1041609, 1160131, 1250597, 1356077, 1427624, 1484823, 1508559, 1552223, 1669993, 1787172, 1905923, 2124671, 2288907, 2523395, 2602286, 2663426, 2702366, 2866915, 3000008, 3048635, 3199578, 3296233, 3362224, 3596134, 3723366, 3875109, 3941035, 4637240, 4734766, 4329234, 4222288, 3999161, 3465955, 3226966, 3421136, 3548802, 3821708, 4110330, 4071865, 4049429, 4091342, 4174298, 4394891, 4247140, 3875921, 3858694, 4038925, 4153655, 4239521, 4357842, 4347202, 4341890, 4111150, 3481754, 3069593, 2454729, 2157464, 2204004, 2383297, 2691127, 2761582, 2532349, 2774027, 2773410, 2545264, 2603173, 2740557, 2760489, 268108, 188227, 107562, 107205, 101445, 96585, 90804, 90335, 99386, 100159, 104089, 101623, 100151, 103228, 126638, 144978, 143623, 140004, 140814, 139333, 126640, 126766, 131615, 136424, 141521, 139625, 118490, 110437, 106222, 110141, 117442, 115748, 114579, 123014, 126366, 129253, 131719, 132977, 137916, 133386, 132401, 47101, 49822, 56947, 67005, 33593, 32343, 33030, 14655, 12731, 7875, 6943, 7210, 6170, 5762, 5794, 5386, 4832, 4904, 4718, 4819, 1422, 1094, 1100, 1153]

YEARS = list(range(1803, 2020))

# Needed to run via cron
path = os.path.dirname(os.path.realpath(__file__))
json_path = Path(path, 'stopwords.json')
with json_path.open() as json_file:
    STOPWORDS = json.load(json_file)

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


def set_date_to_today(year):
    now = arrow.now('Australia/Canberra')
    current_year = now.year
    # Go back to the chosen year
    end = now.shift(years=(year-current_year))
    # Subtract an extra day for the start of the date range
    start = end.shift(days=-1)
    # Format the query
    return 'date:[{}Z TO {}Z]'.format(start.format('YYYY-MM-DDT00:00:00'), end.format('YYYY-MM-DDT00:00:00'))


def extract_date(query):
    query = query.replace('#year', '').strip()
    try:
        year = re.search(r'(\b\d{4}\b)', query).group(1)
    except AttributeError:
        # No year
        if '#onthisday' in query:
            query = query.replace('#onthisday', '').strip()
            year = random.choices(YEARS, weights=YEAR_WEIGHTS)[0]
            date_param = set_date_to_today(year)
        else:
            date_param = ''
    else:
        query = query.replace(year, '').strip()
        if '#onthisday' in query:
            query = query.replace('#onthisday', '').strip()
            date_param = set_date_to_today(int(year))
        else:
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
    query, sort, random, illustrated, article_id, category, hello = parse_tweet(tweet)
    if hello is True:
        article, message, illustrated = random_article()
        if article:
            message = 'Greetings human! Feed me keywords to search newspapers. Enjoy this random selection.'
        else:
            message = 'Greetings human! Feed me keywords to search newspapers.'
    elif not query:
        article, message, illustrated = random_article(illustrated=illustrated, category=category)
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
        article = reply_article(query=query, sort=sort, random=random, illustrated=illustrated, category=category)
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
    category = None
    sort = 'relevance'
    query = tweet['text'].strip()
    # Remove @trovenewsbot from tweet
    query = re.sub(r'\@trovenewsbot', '', query, flags=re.IGNORECASE).strip()
    query = query.replace(u'\u201c', '"').replace(u'\u201d', '"').replace(u'\u2019', "'")
    if re.search(r'\bhello\b', query, flags=re.IGNORECASE):
        query = ''
        random = True
        hello = True
    else:
        if '#luckydip' in query:
            # Get a random article
            query = query.replace('#luckydip', '').strip()
            random = True
        if '#illustrated' in query:
            # Get an illustrated
            query = query.replace('#illustrated', '').strip()
            illustrated = 'true'
        if '#earliest' in query:
            # Sort by date ascending
            query = query.replace('#earliest', '').strip()
            sort = 'dateasc'
        if '#latest' in query:
            # Sort by date descending
            query = query.replace('#latest', '').strip()
            sort = 'datedesc'
        if '#article' in query:
            # Limit to Article category
            query = query.replace('#article', '').strip()
            category = 'Article'
        if '#advertising' in query:
            # Limit to advertising category
            query = query.replace('#advertising', '').strip()
            category = 'Advertising'
        if '#id' in query:
            # Get a specific article
            query = query.replace('#id', '').strip()
            article_id = extract_id(query)
        # Check to see if there's a url in the tweet
        url = get_url(tweet)
        # If so, extract keywords and build search
        if url:
            query = get_url_keywords(url)
        else:
            # Check if there's a year, if so add date limit to search
            if '#year' in query or '#onthisday' in query:
                query = extract_date(query)
            # If #any then make a OR query
            else:
                query = check_for_any(query)
    return (query, sort, random, illustrated, article_id, category, hello)


def get_article_by_id(article_id):
    params = {
        'encoding': 'json',
        'key': api_key,
        'reclevel': 'full'
    }
    response = s.get('https://api.trove.nla.gov.au/v2/newspaper/{}'.format(article_id), params=params)
    data = response.json()
    try:
        article = data['article']
    except (KeyError, IndexError, TypeError):
        article = None
    return article


def reply_article(query=None, sort=None, random=None, illustrated=None, category=None):
    if not random:
        article = get_article(query=query, sort=sort, illustrated=illustrated, category=category)
    else:
        article = get_random_article(query=query, illustrated=illustrated, category=category)
    return article


def send_tweet(article, message=None, user=None, tweet_id=None, illustrated=False):
    if article:
        url = 'http://nla.gov.au/nla.news-article{}'.format(article['id'])
        thumbnail = get_page_thumbnail(article['id'], 800, illustrated=illustrated)
        media_response = api.media_upload(thumbnail)
        media_ids = [media_response.media_id]
        article_date = arrow.get(article['date'], 'YYYY-MM-DD').format('D MMM YYYY')
        newspaper = re.sub(r'\(.+?\)$', '', article['title']['value']).strip()
        if '@abcnews' in message:
            message_length = 65
        elif '@GuardianAus' in message:
            message_length = 70
        elif user:
            message_length = len(message) + len(user) + 2
        else:
            message_length = len(message)
        chars = 240 - (message_length + len(article_date) + len(newspaper) + 10)
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
        # pass
    except FileNotFoundError:
        pass


def get_article(query=None, random=False, start=0, sort='relevance', illustrated=False, category=None):
    '''
    Search for an article from Trove using the supplied parameters.
    '''
    params = {
        'q': query,
        'zone': 'newspaper',
        'encoding': 'json',
        'n': 1,
        'sortby': sort,
        'key': api_key
    }
    if illustrated:
        params['l-illustrated'] = 'true'
    if category:
        params['l-category'] = category
    try:
        response = s.get(API_URL, params=params, timeout=60)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        article = None
    else:
        try:
            data = response.json()
        except json.decoder.JSONDecodeError:
            article = None
        else:
            try:
                article = data['response']['zone'][0]['records']['article'][0]
            except (KeyError, IndexError, TypeError):
                article = None
    return article


def random_tweet(option=None):
    article, message, illustrated = random_article(option=option)
    send_tweet(article, message=message, illustrated=illustrated)


def get_random_facet_value(params, facet):
    '''
    Get values for the supplied facet and choose one at random.
    '''
    these_params = params.copy()
    these_params['facet'] = facet
    response = s.get(API_URL, params=these_params)
    data = response.json()
    try:
        values = [t['search'] for t in data['response']['zone'][0]['facets']['facet']['term']]
    except TypeError:
        return None
    return random.choice(values)


def get_total_results(params):
    response = s.get(API_URL, params=params)
    data = response.json()
    total = int(data['response']['zone'][0]['records']['total'])
    return total


def get_random_article(query=None, **kwargs):
    '''
    Get a random article.
    The kwargs can be any of the available facets, such as 'state', 'title', 'illtype', 'year'.
    '''
    total = 0
    applied_facets = []
    facets = ['month', 'year', 'decade', 'word', 'illustrated', 'category', 'title']
    tries = 0
    params = {
        'zone': 'newspaper',
        'encoding': 'json',
        # Note that keeping n at 0 until we've filtered the result set speeds things up considerably
        'n': '0',
        # Uncomment these if you need more than the basic data
        'reclevel': 'full',
        #'include': 'articleText',
        'key': api_key
    }
    if query:
        params['q'] = query
    # If there's no query supplied then use a random stopword to mix up the results
    else:
        random_word = random.choice(STOPWORDS)
        params['q'] = f'"{random_word}"'
    # Apply any supplied factes
    for key, value in kwargs.items():
        if value:
            params[f'l-{key}'] = value
            applied_facets.append(key)
    # Remove any facets that have already been applied from the list of available facets
    facets[:] = [f for f in facets if f not in applied_facets]
    total = get_total_results(params)
    # If our randomly selected stopword has produced no results
    # keep trying with new queries until we get some (give up after 10 tries)
    while total == 0 and tries <= 10:
        if not query:
            random_word = random.choice(STOPWORDS)
            params['q'] = f'"{random_word}"'
        tries += 1
    # Apply facets one at a time until we have less than 100 results, or we run out of facets
    while total > 100 and len(facets) > 0:
        # Get the next facet
        facet = facets.pop()
        # Set the facet to a randomly selected value
        params[f'l-{facet}'] = get_random_facet_value(params, facet)
        total = get_total_results(params)
        #print(total)
        #print(response.url)
    # If we've ended up with some results, then select one (of the first 100) at random
    if total > 0:
        params['n'] = '100'
        response = s.get(API_URL, params=params)
        data = response.json()
        article = random.choice(data['response']['zone'][0]['records']['article'])
        return article


def random_article(illustrated=None, category=None, option=None):
    # Options for random searches
    options = ['updated', 'any', 'illustrated']
    if not option:
        option = random.choice(options)
    # If user has specified illustrated - then make sure it's illustrated no matter what option chosen
    if illustrated == 'true':
        query = None
    elif option == 'updated':
        # Get articles modified in the last day
        now = arrow.utcnow()
        yesterday = now.shift(days=-1)
        date = f'{yesterday.format("YYYY-MM-DD")}T00:00:00Z'
        query = f'lastupdated:[{date} TO *]'
    elif option == 'any':
        query = None
        category = 'Article'
    elif option == 'illustrated':
        query = None
        illustrated = 'true'
    elif option == 'onthisday':
        year = random.choices(YEARS, weights=YEAR_WEIGHTS)[0]
        query = set_date_to_today(year)
        category = 'Article'
    article = get_random_article(query=query, illustrated=illustrated, category=category)
    if article:
        if option == 'onthisday':
            current_year = arrow.now('Australia/Canberra').year
            message = f'On this day {current_year - year} years ago!'
        elif query and int(article['correctionCount']) > 0:
            message = 'Updated!'
        elif query:
            message = 'New!'
        else:
            message = 'Found!'
    else:
        message = 'Error! I was unable to obtain an article!'
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
    if illustrations and illustrated == 'true':
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
    cropped_file = f'nla.news-article{article_id}-{box["page_id"]}.jpg'
    cropped.save(cropped_file)
    return cropped_file

def reply_abc():
    feed = random.choice(NEWS_FEEDS)
    trove_url = None
    news = feedparser.parse(feed['rss'])
    latest_url = news.entries[0].link
    try:
        last_url = redis_client.get('last_{}_link'.format(feed['source'])).decode('utf-8')
    except AttributeError:
        last_url = None
    if latest_url != last_url:
        redis_client.set('last_{}_link'.format(feed['source']), latest_url)
        query = get_url_keywords(latest_url)
        article = get_article(query)
        if article:
            message = 'Found in response to {} latest at {}!'.format(feed['handle'], latest_url)
            send_tweet(article, message, user=None, tweet_id=None, illustrated=False)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('task')
    args = parser.parse_args()
    if args.task == 'random':
        random_tweet()
    elif args.task == 'onthisday':
        random_tweet(option='onthisday')
    elif args.task == 'abc':
        reply_abc()
