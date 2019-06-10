# TroveNewsBot (the 2019 edition)

[@TroveNewsBot](http://twitter.com/trovenewsbot) is **live** on Twitter.

This is the latest version of @TroveNewsBot which includes a number of new or enhanced features:

* Article thumbnails with every tweet!
* Search Trove without leaving Twitter!
* Grab a nice thumbnailed version of any newspaper article!
* Serendipify your life with randomly-selected articles!
* Automatically search Trove based on the contents of any web page!

![Tweet screenshot](images/trovenewsbot.png)

For an earlier incarnation of TroveNewsBot [see this repository](https://github.com/wragge/trovenewsbot).

## Search Trove newspapers

Ever wanted to search Trove's newspapers without leaving Twitter? @TroveNewsBot can help! Simply tweet your search terms at @TroveNewsbot and it will search Trove for you, tweeting back the most relevant result. It can be as simple as this:

```
@TroveNewsbot lamingtons
```

[Here's an example](https://twitter.com/wragge/status/1137667800950960129) of a tweeted query and @TroveNewsBot's response. Note that '@TroveNewsBot' has to appear first in your tweet (this is to stop the bot responding every time it gets a mention!).

### Sorting results

By default, @TroveNewsBot tweets back the most relevant result (as defined by Trove's relevance ranking). But you can change this by adding one of the following hashtags to your tweet:

* `#luckydip` – return an article chosen at random from the results set
* `#earliest` – return the article that was published first
* `#latest` – return the article that was published last

For example:

```
@TroveNewsBot lamingtons #earliest
```

### Filtering results

You can filter your results by using the following hashtags:

* `#article` – only include results in the 'Article' category
* `#advertising` – only include results in the 'Advertising' category
* `#year` – if you include this hashtag *and* a year in your tweet, @TroveNewsBot will limit the results to articles published in that year.
* `#illustrated` – only include articles that have illustrations

Examples:

```
@TroveNewsbot lamingtons #advertising
@TroveNewsBot lamingtons 1920 #year
```

Note that if you use the `#illustrated` hashtag, @TroveNewsBot will use the first illustration it finds in the selected article as the thumnail, rather than the article's headline.

### Combining search terms

If you include multiple search terms, @TroveNewsBot will look for articles that contain *all* the terms (an 'AND' search). If you want to change this, you can add the following hashtag:

* `#any` – returns results that have *any* of the supplied search terms (an 'OR' search)

For example:

```
@TroveNewsBot lamingtons pavlova #any
```

### Combining hashtags

You can can combine any of the hashtags described above to make more complex searches. For example:

```
@TroveNewsBot lamington #earliest #illustrated
```

## Serendipity mode

But what if don't have a particular search term in mind? What if you just want to explore? @TroveNewsBot can help with that as well! Simply tweet `#luckydip` at @TroveNewsBot for a randomly selected newspaper article. If you want slightly less random results, you can add any of the filters describe above. For example:

```
@TroveNewsBot #luckydip
@TroveNewsBot #luckydip #illustrated
@TroveNewsBot 1910 #luckydip #illustrated #year
```

Behind the scenes, @TroveNewsBot randomly selects a random option to find your random article. The options are:

* A random selection from articles that have been added or updated in the last 24 hours (that means they're new, they've been corrected, or they've had a tag or comment added)
* A random selection from *all* of Trove's newspaper articles
* A random selection from *all illustrated* newspaper articles

Note that this is something you *can't* do through the Trove web interface. Bots FTW!

## Opinionator mode

Instead of feeding search terms to @TroveNewsBot, you can send it a complete web page! Just tweet a url at @TroveNewsBot and it will automatically extract keywords from the page and use them to search Trove. You can limit the results using the filters described above. For example:

```
@TroveNewsBot https://en.wikipedia.org/wiki/Lamington
@TroveNewsBot https://en.wikipedia.org/wiki/Lamington #illustrated
```

While you could add `#luckydip` to this search, you're not likely to get a very useful result. That's because @TroveNewsBot searches for articles containing *any* of the keywords it extracts. Trove's relevance ranking will push articles that match mutiple keywords to the top of the results, but a random result might only match a single keyword. But hey, if you're feeling adventurous give it a go!

## Single article mode

@TroveNewsBot's tweets include a specially-generated thumbnail image of the newspaper article. To get these sorts of images from the Trove web interface you have to fiddle around with screen captures or PDFs. But again, @TroveNewsBot can help! If you already know the article you want, just tweet its identifier (that's the number in the article's url) and add the `#id` hashtag. For example, here's the url of a newspaper article in Trove:

```
https://trove.nla.gov.au/newspaper/article/162833980
```

The article identifier is `162833980`, so to get the article from @TroveNewsBot, just tweet:

```
@TroveNewsBot 162833980 #id
```

If the article has an illustration and you'd like the illustration used as the thumbnail image rather than the headline, just add `#illustrated`:

```
@TroveNewsBot 162833980 #id #illustrated
```

Here's the results [without](https://twitter.com/TroveNewsBot/status/1137673479858184194) and [with](https://twitter.com/TroveNewsBot/status/1137673583214321667) the `#illustrated` hashtag. Obviously, if the article doesn't have an illustration, adding `#illustrated` will have no effect!

Once @TroveNewsBot has responded with your nicely-presented article reference, you can save the thumbnail, or quote tweet the result. It's an easy way of sharing a social media friendly version of a Trove newspaper article.

## Automated updates

* At 9am, 3pm and 9pm (AEST), @TroveNewsBot tweets a random article. Here's [an example](https://twitter.com/TroveNewsBot/status/1137856976136704001).
* At 8am, 12 noon, 4pm and 8pm (AEST), @TroveNewsBot tweets a response to the latest news item on the ABC's [Just In](https://www.abc.net.au/news/justin/) page, using its 'Opinionator' mode. Here's [an example](https://twitter.com/TroveNewsBot/status/1137842076458971138).

## Technical details

@TroveNewsBot uses the following libraries (amongst others):

* [Tweepy](https://www.tweepy.org/) – to interact with Twitter
* [Newspaper](https://github.com/codelucas/newspaper) – to extract keywords from web pages
* [Arrow](https://arrow.readthedocs.io/en/latest/) – for easy date parsing and formatting
* [RQ](https://python-rq.org/) – to queue tweets for processing

If you'd like to know more about how @TroveNewsBot generates the article thumbnails, look at the examples in the [Trove Newspapers section](https://glam-workbench.github.io/trove-newspapers/) of the GLAM Workbench.

____

Created by [Tim Sherratt](http://timsherratt.org/).

If you like this project, you can support it on [Patreon](https://www.patreon.com/timsherratt).