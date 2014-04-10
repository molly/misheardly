# Copyright (c) 2014 Molly White
#
# Permission is hereby granted, free of charge, to any person obtaining a copy # of this software and associated documentation files (the "Software"), to deal
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
import os
from random import choice, shuffle
import re
import tweepy
import urllib2
from secrets import *
from time import gmtime, strftime

__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))


def get():
    # Get song lyrics from a popular song
    page = 1
    while page <= 3:
        try:
            # Get the top songs
            request = urllib2.Request(
                "http://ws.audioscrobbler.com/2.0/?method=chart.gettoptracks&" +
                "api_key=" + LASTFM_KEY + "&format=json&page=" + str(page))
            response = urllib2.urlopen(request)
        except urllib2.URLError as e:
            log("Error in requesting top tracks: " + e.strerror)
        else:
            # Extract the artist and track name
            blob = json.load(response)
            tracks = blob["tracks"]["track"]
            for track in tracks:
                artist = track["artist"]["name"]
                title = track["name"]

                # Check if we've already used this song
                try:
                    f = codecs.open(os.path.join(__location__,'tweeted_songs.txt'),
                            encoding='utf-8', mode='r')
                    if title + ", " + artist in [line.strip() for line in f]:
                        continue
                    f.close()
                except IOError as e:
                    log("Error in opening tweeted_songs: e.strerror")
                    pass

                # All systems go! Add to file so we don't keep trying it.
                f = codecs.open(os.path.join(__location__, 'tweeted_songs.txt'),
                        encoding='utf-8', mode='a')
                f.write("\n" + title + ", " + artist)
                f.close()

                # Format a URL to get the lyrics
                formatted_title = re.sub(r'[^a-z0-9 ]', '', title.lower())
                formatted_artist = re.sub(r'[^a-z0-9 ]', '', artist.lower())
                lyrics_url = "http://www.songlyrics.com/" + formatted_artist.replace(" ", "-") + \
                             "/" + formatted_title.replace(" ", "-") + "-lyrics/"

                # Get the lyrics
                try:
                    request = urllib2.Request(lyrics_url)
                    response = urllib2.urlopen(request)
                except urllib2.URLError as e:
                    # Errors will happen when you're making up URLs
                    log("Unable to get lyrics for " + title + ", " + artist + ": " + e.strerror)
                    pass
                lyrics_html = response.read()
                soup = BeautifulSoup(lyrics_html)
                lyrics_div = soup.find(id="songLyricsDiv")

                # Couldn't find lyrics at this URL
                if not lyrics_div:
                    log("Unable to extract lyrics for "  + title + ", " + artist)
                    continue

                # Try to get the chorus by splitting the lyrics by block, then finding the most
                # frequently-occurring one
                lyrics = lyrics_div.get_text()
                spl = lyrics.replace("\r", "")
                spl = re.sub(r'\[.+?\]', '', spl)
                spl = spl.split("\n\n")
                spl = [x for x in spl if "\n" in x]
                if not spl:
                    log("Unable to split lyrics for "  + title + ", " + artist)
                    continue
                chorus = ""
                try_num = 0
                while len(chorus) < 30 and try_num < 3:
                    chorus = choice(spl)
                    try_num += 1
                if len(chorus) < 30:
                    log("Unable to find long enough chorus for "  + title + ", " + artist)
                    continue
                process(title, artist, chorus)
                return
            page += 1
    else:
        # Cycle back around through the same songs, then
        log("Removing tweeted_songs file.")
        try:
            os.remove("tweeted_songs.txt")
        except OSError as e:
            log("Unable to remove tweeted_songs file: " + e.strerror)


def split_chorus(title, artist, spl):
    # Split the chorus so that it's under the twitter character limit
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
        if u"\u2018" in spl[ind]:
            spl[ind] = spl[ind].replace(u"\u2018", "'")
        length += len(spl[ind])
        ind += 1
    return ind


def choose_word_freq(word_freqs):
    # Choose one of the three lowest frequencies if there are > 3, otherwise just choose one
    # from the list.
    if len(word_freqs) > 3:
        return choice(word_freqs[:3])
    else:
        return choice(word_freqs)


def get_rhyme(word):
    # Get a rhyme for the given word
    try:
        request_orig = urllib2.Request(
            "http://rhymebrain.com/talk?function=getWordInfo&word=" + word)
        response_orig = json.load(urllib2.urlopen(request_orig))
        request = urllib2.Request("http://rhymebrain.com/talk?function=getRhymes&word=" + word)
        response = json.load(urllib2.urlopen(request))
    except urllib2.URLError as e:
        log("Error while retrieving rhyme for " + word + ": " + e.strerror)
        pass
    else:
        syl_orig = response_orig["syllables"]
        shuffle(response)   # mix things up a bit
        for result in response:
            # Try to find a word that's relatively common, has a syllable count within 1 of the
            # given word, has a "score" of > 250, and is not the same as the given word
            if result["freq"] > 10 and abs(int(result["syllables"]) == int(syl_orig)) and \
                            result["score"] > 250 and result["word"].lower() != word.lower():
                return result["word"]

def process(title, artist, text):
    # Find out how much of the chorus we can use, do replacement
    spl = text.split("\n")
    spl = filter(None, spl)
    ind = split_chorus(title, artist, spl)
    words = set(re.split(r"[^A-Za-z\-']", " ".join(spl[:ind])))
    word_dict = {}
    for word in words:
        try:
            request = urllib2.Request("http://rhymebrain.com/talk?function=getWordInfo&word=" + \
                                      word.lower())
            response = urllib2.urlopen(request)
        except urllib2.URLError as e:
            log("Unable to get word info for " + word.lower() + ": " + e.strerror)
            pass
        else:
            blob = json.load(response)
            word_dict[blob["freq"]] = word

    word_freqs = sorted(word_dict.keys())
    word = word_dict[choose_word_freq(word_freqs)]
    new_word = get_rhyme(word)
    if not new_word:
        log("Can't get rhyme for " + word)
        return

    if word.istitle():
        new_word = new_word.title()
    elif word.islower():
        new_word = new_word.lower()
    for i in range(ind):
        spl[i] = spl[i].replace(word, new_word)

    tw = "\"" + " / ".join(spl[:ind]) + "\""
    tw += " - \"" + title + "\", " + artist
    tweet(tw)


def tweet(text):
    # Send the tweet
    auth = tweepy.OAuthHandler(C_KEY, C_SECRET)
    auth.set_access_token(A_TOKEN, A_TOKEN_SECRET)
    api = tweepy.API(auth)
    tweets = api.user_timeline('misheardly')

    # Check that we haven't tweeted this before
    for tw in tweets:
        if text == tw.text:
            log("We've tweeted this before.")
            return False

    # Log tweet to file
    log(text)

    # Post tweet
    api.update_status(text)
    return True

def log(text):
    f = open(os.path.join(__location__, "misheardly.log"), 'a')
    t = strftime("%d %b %Y %H:%M:%S", gmtime())
    f.write("\n" + t + " " + text.encode('ascii', 'replace'))
    f.close()

if __name__ == "__main__":
    get()
