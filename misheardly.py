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
from random import choice
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



def split_chorus(title, artist, spl):
    ind = 0
    length = 0
    while ind < len(spl):
        if re.search(r'(\A[(\[](?:.*?)[)\]]\Z)', spl[ind]):
            # Try to remove "[Chorus]", etc.
            spl.pop(ind)
            continue
        if length + len(spl[ind]) + len(title) + len(artist) > 120:
            break
        if u"\u2019" in spl[ind]:
            # Curly apostrophes are literally the worst
            spl[ind] = spl[ind].replace(u"\u2019", "'")
        length += len(spl[ind])
        ind += 1
    return ind


def get_rhyme(word):
    try:
        request_orig = urllib2.Request("http://rhymebrain.com/talk?function=getWordInfo&word=" + word)
        response_orig = json.load(urllib2.urlopen(request_orig))
        request = urllib2.Request("http://rhymebrain.com/talk?function=getRhymes&word=" + word)
        response = json.load(urllib2.urlopen(request))
    except urllib2.URLError as e:
        pass
    else:
        print response_orig
        syl_orig = response_orig["syllables"]
        for result in response:
            print result
            if result["freq"] > 10 and abs(int(result["syllables"]) - int(syl_orig)) <= 1\
                    and result["word"].lower() != word.lower():
                return result["word"]


def process(title, artist, text):
    # Find out how much of the chorus we can use, do replacement
    # I wrote this code at 4 in the morning; beware... Here be dragons.
    spl = text.split("\n")
    ind = split_chorus(title, artist, spl)
    words = set(re.split(r"[^A-Za-z\-']", " ".join(spl[:ind])))
    word_dict = {}
    for word in words:
        try:
            request = urllib2.Request("http://rhymebrain.com/talk?function=getWordInfo&word=" + \
                                        word.lower())
            response = urllib2.urlopen(request)
        except urllib2.URLError as e:
            pass
        else:
            blob = json.load(response)
            word_dict[blob["freq"]] = word

    word = word_dict[min(word_dict.iterkeys())]
    new_word = get_rhyme(word)

    if word.istitle():
        new_word = new_word.title()
    elif word.islower():
        new_word = new_word.lower()
    for i in range(ind):
        spl[i] = spl[i].replace(word, new_word)

    print word + " -> " + new_word
    tweet = "\"" + " / ".join(spl[:ind]) + "\""
    tweet += " - \"" + title + "\", " + artist
    print tweet


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
