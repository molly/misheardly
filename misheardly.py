# Copyright (c) 2014 Molly White
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from bs4 import BeautifulSoup
import codecs
import json
import re
import tweepy
import urllib2
from secrets import *
from time import gmtime, strftime


def get():
    # Get song lyrics from a popular song
    page = 1
    while page <= 20:
        try:
            # Get the top songs
            request = urllib2.Request("http://ws.audioscrobbler.com/2.0/?method=chart.gettoptracks&" +
                                      "api_key=" + LASTFM_KEY + "&format=json&page=" + str(page))
            response = urllib2.urlopen(request)
        except urllib2.URLError as e:
            print e.reason
            return
        else:
            # Extract the artist and track name
            blob = json.load(response)
            tracks = blob["tracks"]["track"]
            for track in tracks:
                artist = track["artist"]["name"]
                title = track["name"]

                # Check if we've already used this song
                f = codecs.open('tweeted_songs.txt', encoding='utf-8', mode='r')
                if title + ", " + artist in [line.strip() for line in f]:
                    continue
                f.close()

                # All systems go! Add to file so we don't keep trying it.
                f = codecs.open('tweeted_songs.txt', encoding='utf-8', mode='a')
                f.write("\n" + title + ", " + artist)
                f.close()

                # Format a URL to get the lyrics
                formatted_title = re.sub(r'[^a-z0-9 ]', '', title.lower())
                formatted_artist = re.sub(r'[^a-z0-9 ]', '', artist.lower())
                lyrics_url = "http://www.songlyrics.com/" + formatted_artist.replace(" ", "-") + \
                      "/" + formatted_title.replace(" ", "-") + "-lyrics/"
                print lyrics_url

                # Get the lyrics
                try:
                    request = urllib2.Request(lyrics_url)
                    response = urllib2.urlopen(request)
                except urllib2.URLError as e:
                    # Errors will happen when you're making up URLs
                    pass
                lyrics_html = response.read()
                soup = BeautifulSoup(lyrics_html)
                lyrics_div = soup.find(id="songLyricsDiv")

                # Couldn't find lyrics at this URL
                if not lyrics_div:
                    continue

                # Try to get the chorus by splitting the lyrics by block, then finding the most
                # frequently-occurring one
                lyrics = lyrics_div.get_text()
                spl = lyrics.replace("\r", "").split("\n\n")
                spl = [x for x in spl if "\n" in x]
                if not spl:
                    continue
                chorus = max(set(spl), key=spl.count)
                if len(chorus) < 30:
                    continue
                process(title, artist, chorus)
                return
            page += 1



def process(title, artist, text):
    # Find out how much of the chorus we can use, do replacement
    ind = 0
    length = 0
    spl = text.split("\n")
    while ind < len(spl):
        if len(spl[ind]) < 20 and re.search(r'(\A[(\[](?:.*?)[)\]]\Z)', spl[ind]):
            # Try to remove "[Chorus]", etc.
            spl.pop(ind)
            continue
        if length + len(spl[ind]) + len(title) + len(artist) > 120:
            break
        length += len(spl[ind])
        ind += 1
    snip = " / ".join(spl[:ind])
    print snip
    print '"' + title + '"' + ", " + artist


def tweet(text):
    auth = tweepy.OAuthHandler(C_KEY, C_SECRET)
    auth.set_access_token(A_TOKEN, A_TOKEN_SECRET)
    api = tweepy.API(auth)
    tweets = api.user_timeline('CyberPrefixer')

    # Check that we haven't tweeted this before
    for tw in tweets:
        if text == tw.text:
            return False

    # Log tweet to file
    f = open("cyberprefixer.log", 'a')
    t = strftime("%d %b %Y %H:%M:%S", gmtime())
    f.write("\n" + t + " " + text)
    f.close()

    # # Post tweet
    # api.update_status(text)
    # return True

if __name__ == "__main__":
    get()
