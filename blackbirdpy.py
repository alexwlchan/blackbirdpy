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

import re
import sys

from jinja2 import Template
import keyring
import pytz
import tweepy

myTZ = pytz.timezone('GB')

TWEET_EMBED_HTML = Template("""
<div class="bbpBox" id="t{{id}}">
  <blockquote>
    <span class="twContent">{{tweetText}}</span>
    <span class="twMeta"><br />
      <span class="twDecoration">&mdash; </span>
      <span class="twRealName">{{realName}}</span>
      <span class="twDecoration">(</span><a href="http://twitter.com/{{screenName}}"><span class="twScreenName">@{{screenName}}</span></a><span class="twDecoration">)</span>
    <a href="{{tweetURL}}"><span class="twTimeStamp">{{timeStamp}}</span></a>
    <span class="twDecoration"></span></span>
  </blockquote>
</div>
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


def embed_tweet_html(tweet_url, extra_css=None):
    """Generate embedded HTML for a tweet, given its Twitter URL.  The
    result is formatted as a simple quote, but with span classes that
    allow it to be reformatted dynamically (through jQuery) in the style
    of Robin Sloan's Blackbird Pie.
    See: http://media.twitter.com/blackbird-pie

    The optional extra_css argument is a dictionary of CSS class names
    to CSS style text.  If provided, the extra style text will be
    included in the embedded HTML CSS.  Currently only the bbpBox
    class name is used by this feature.
    """
    tweet_id = tweet_id_from_tweet_url(tweet_url)
    api = setup_api()
    tweet = api.get_status(tweet_id)
    tweet_text = wrap_entities(tweet).replace('\n', '<br />')

    tweet_created_datetime = pytz.utc.localize(tweet.created_at).astimezone(myTZ)
    tweet_timestamp = tweet_created_datetime.strftime("%b %-d %Y %-I:%M %p")

    if extra_css is None:
        extra_css = {}

    html = TWEET_EMBED_HTML.render(
        id=tweet_id,
        tweetURL=tweet_url,
        screenName=tweet.user.screen_name,
        realName=tweet.user.name,
        tweetText=tweet_text,
        source=tweet.source,
        profilePic=tweet.user.profile_image_url,
        profileBackgroundColor=tweet.user.profile_background_color,
        profileBackgroundImage=tweet.user.profile_background_image_url,
        profileTextColor=tweet.user.profile_text_color,
        profileLinkColor=tweet.user.profile_link_color,
        timeStamp=tweet_timestamp,
        utcOffset=tweet.user.utc_offset,
        bbpBoxCss=extra_css.get('bbpBox', ''),
    )
    return html



if __name__ == '__main__':
    print(embed_tweet_html(sys.argv[1]))
