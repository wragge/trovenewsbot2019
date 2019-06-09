from credentials import *
import tweepy
import redis
from rq import Queue
import re
import json
from trovenewsbot import process_tweet

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token_key, access_token_secret)

api = tweepy.API(auth)

redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)
tweet_queue = Queue('trovenewsbot', connection=redis.Redis())

since_id = redis_client.get('newsbot_last_tweet_id')
# since_id = None
if since_id:
    mentions = api.mentions_timeline(since_id=since_id, include_rts=False)
else:
    mentions = api.mentions_timeline(include_rts=False)
# [::-1] reverses the list
for tweet in mentions[::-1]:
    print(tweet.text)
    if tweet.in_reply_to_screen_name == 'TroveNewsBot':
        #tweet_author = '@' + tweet.author.screen_name
        #tweet_details = '{} | {} | {}'.format(tweet_id, tweet_author, tweet.text)
        tweet_json = json.dumps(tweet._json)
        #print(tweet_json)
        result = tweet_queue.enqueue(process_tweet, tweet_json)
    # redis_client.set('newsbot_last_tweet_id', tweet.id_str)

