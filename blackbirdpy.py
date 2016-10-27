# -*- coding: utf-8 -*-
#
# Blackbirdpy - a Python implementation of Blackbird Pie, the tool
# @robinsloan uses to generate embedded HTML tweets for blog posts.
#
# See: http://media.twitter.com/blackbird-pie
#
# This Python version was written by Jeff Miller, http://twitter.com/jeffmiller
#
# Various formatting changes by Dr. Drang, http://twitter.com/drdrang
#
# Additional changes by Alex Chan, http://twitter.com/alexwlchan
#
# Requires Python 2.6.
#
# Usage:
#
# - To generate embedded HTML for a tweet from inside a Python program:
#
#   import blackbirdpy
#   embed_html = blackbirdpy.embed_tweet_html(tweet_url)
#
# - To generate embedded HTML for a tweet from the command line:
#
#   $ python blackbirdpy.py <tweeturl>
#     e.g.
#   $ python blackbirdpy.py http://twitter.com/punchfork/status/16342628623
#

import filecmp
import itertools
import os
import re
import shutil
import sys
import tempfile

from jinja2 import Template
import keyring
import pytz
import requests
import tweepy

myTZ = pytz.timezone('GB')

IMAGE_DIR = os.path.join(
    os.environ['HOME'], 'Developer', 'alexwlchan.net', 'content', 'images'
)

TWEET_EMBED_HTML = Template("""

<!-- This comment is provided for the purposes of RSS autogen, and is stripped out in the final HTML -->
<!-- rss_tweet
<blockquote>
  <span class="twContent">{{ tweet_text }}</span>
  <span class="twMeta"><br />
    <span class="twDecoration">&nbsp;&nbsp;&mdash; </span>
    <span class="twRealName">{{ user.name }}</span>
    <span class="twDecoration"> (</span><a href="http://twitter.com/{{ user.screen_name }}"><span class="twScreenName">@{{ user.screen_name }}</span></a><span class="twDecoration">) </span>
    <a href="{{ tweet_url }}"><span class="twTimeStamp">{{ timestamp }}</span></a><span class="twDecoration"></span>
  </span>
</blockquote>
end_rss_tweet -->

<!-- start_bbpBox -->
<style>
#bbpBox{{ tweet.id_str }} { background: #{{profile_background_color}}; }
#bbpBox{{ tweet.id_str }} a { color: #{{profile_link_color}}; }
#bbpBox{{ tweet.id_str }} .metadata a:hover .display_name { color: #{{ profile_link_color }} !important; }
</style>

<div id="bbpBox{{ tweet.id_str }}" class="bbpBox bbpBox_new">
  <blockquote class="bbpTweet">
    <p class="metadata"><a href="https://twitter.com/{{ user.screen_name }}">
        <img src="/images/{{ profile_pic }}" class="avatar"/>
        <span class="display_name">{{ user.name }}</span>
        <span class="handle">@{{ user.screen_name }}</span>
    </a></p>
    <p class="tweet">{{tweet_text}}</p>
    <p class="timestamp"><a href="{{ tweet_url }}">{{ timestamp }}</a></p>
  </blockquote>
</div>
<!-- end_bbpBox -->
""".strip())

u'''
'''


def setup_api():
    """
    Authorise the use of the Twitter API.  This requires the appropriate
    tokens to be set in the system keychain (using the keyring module).
    """
    a = {
        attr: keyring.get_password('twitter', attr) for attr in [
            'consumerKey',
            'consumerSecret',
            'token',
            'tokenSecret'
        ]
    }
    if None in a.values():
        raise EnvironmentError("Missing Twitter API keys in keychain.")
    auth = tweepy.OAuthHandler(consumer_key=a['consumerKey'],
                               consumer_secret=a['consumerSecret'])
    auth.set_access_token(key=a['token'], secret=a['tokenSecret'])
    return tweepy.API(auth)


def wrap_entities(t):
  """Turn URLs and @ mentions into links. Embed Twitter native photos."""
  text = t.text
  mentions = t.entities['user_mentions']
  hashtags = t.entities['hashtags']
  urls = t.entities['urls']
  # media = json['entities']['media']
  try:
    media = t.extended_entities['media']
  except (KeyError, AttributeError):
    media = []

  for u in urls:
    try:
      link = '<a href="' + u['expanded_url'] + '">' + u['display_url'] + '</a>'
    except (KeyError, TypeError):
      link = '<a href="' + u['url'] + '">' + u['url'] + '</a>'
    text = text.replace(u['url'], link)

  for m in mentions:
    text = re.sub('(?i)@' + m['screen_name'], '<a href="http://twitter.com/' +
            m['screen_name'] + '">@' + m['screen_name'] + '</a>', text, 0)

  for h in hashtags:
    text = re.sub('(?i)#' + h['text'], '<a href="http://twitter.com/search/%23' +
            h['text'] + '">#' + h['text'] + '</a>', text, 0)

  # For some reason, multiple photos have only one URL in the text of the tweet.
  if len(media) > 0:
    photolink = ''
    for m in media:
      if m['type'] == 'photo':
        photolink += '<br /><br /><a href="' + m['media_url'] + ':large">' +\
                    '<img src="' + m['media_url'] + ':small"></a>'
      else:
        photolink += '<a href="' + m['expanded_url'] + '">' +\
                    m['display_url'] + '</a>'
    text = text.replace(m['url'], photolink)

  return text

def tweet_id_from_tweet_url(tweet_url):
    """Extract and return the numeric tweet ID from a full tweet URL."""
    match = re.match(r'^https?://twitter\.com/(?:#!\/)?\w+/status(?:es)?/(\d+)$', tweet_url)
    try:
        return match.group(1)
    except AttributeError:
        raise ValueError('Invalid tweet URL: {0}'.format(tweet_url))


def download_file(url):
    """Download a file.  http://stackoverflow.com/a/16696317/1558022"""
    _, local_filename = tempfile.mkstemp()
    # NOTE the stream=True parameter
    r = requests.get(url, stream=True)
    with open(local_filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk: # filter out keep-alive new chunks
                f.write(chunk)
                #f.flush() commented by recommendation from J.F.Sebastian
    return local_filename


def candidate_filenames(handle):
    yield os.path.join(IMAGE_DIR, 'twavatar_%s.jpeg' % handle)
    for i in itertools.count(start=1):
        yield os.path.join(IMAGE_DIR, 'twavatar_%s_%d.jpeg' % (handle, i))


def cache_avatar(profile_image_url, handle):
    """Cache the avatar locally."""
    avatar_url = profile_image_url.replace('_normal', '_bigger')
    local_download = download_file(avatar_url)
    for filename in candidate_filenames(handle):
        if not os.path.exists(filename):
            shutil.move(local_download, filename)
            return os.path.basename(filename)
        elif filecmp.cmp(local_download, filename):
            return os.path.basename(filename)


def embed_tweet_html(tweet_url):
    """Generate embedded HTML for a tweet, given its Twitter URL.  The
    result is formatted as a simple quote, but with span classes that
    allow it to be reformatted dynamically (through jQuery) in the style
    of Robin Sloan's Blackbird Pie.
    See: http://media.twitter.com/blackbird-pie
    """
    tweet_id = tweet_id_from_tweet_url(tweet_url)
    api = setup_api()
    tweet = api.get_status(tweet_id)
    tweet_text = wrap_entities(tweet).replace('\n', '<br />')

    tweet_created_datetime = pytz.utc.localize(tweet.created_at).astimezone(myTZ)
    tweet_timestamp = tweet_created_datetime.strftime("%-I:%M %p - %-d %b %Y")

    avatar_path = cache_avatar(
        tweet.user.profile_image_url,
        handle=tweet.user.screen_name
    )

    return TWEET_EMBED_HTML.render(
        tweet=tweet,
        tweet_url=tweet_url,
        user=tweet.user,
        tweet_text=tweet_text,
        source=tweet.source,
        profile_pic=avatar_path,
        profile_background_color=tweet.user.profile_background_color.lower(),
        profileTextColor=tweet.user.profile_text_color.lower(),
        profile_link_color=tweet.user.profile_link_color.lower(),
        timestamp=tweet_timestamp,
    )


if __name__ == '__main__':
    print(embed_tweet_html(sys.argv[1]))
