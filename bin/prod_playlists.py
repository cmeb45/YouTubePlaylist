#!/usr/bin/python3

# Usage example:
# python3 prod_playlists.py filename

import re
import unicodedata
import pandas as pd
import math
import httplib2
import os
import sys
import argparse
import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow


class YouTubeAuth:

    def __init__(self):
        """
        Constructs an object for authorizing request and storing YouTube authorization credentials.
        """
        def get_authenticated_service(self):
            """Authorize the request and store authorization credentials
            """
            flow = InstalledAppFlow.from_client_secrets_file(self.CLIENT_SECRETS_FILE, 
                                   self.SCOPES)

            credentials = flow.run_console()

            return build(self.YOUTUBE_API_SERVICE_NAME, self.YOUTUBE_API_VERSION,
                 credentials = credentials)

        """
The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
the OAuth 2.0 information for this application, including its client_id and
client_secret.
        """

        self.CLIENT_SECRETS_FILE = "client_secrets.json"

        # This OAuth 2.0 access scope allows for full read/write access to the
        # authenticated user's account and requires requests to use an SSL connection.
        self.SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
        self.YOUTUBE_API_SERVICE_NAME = "youtube"
        self.YOUTUBE_API_VERSION = "v3"
        self.YOUTUBE_AUTHENTICATED_SERVICE = get_authenticated_service(self)

class Playlists:

    def __init__(self, youtube):
        """Class for creating and managing YouTube playlists"""
        self.youtube_authentication = youtube

    def create_playlist(self, val):
        """Call the API to create a new playlist in the authorized user's channel
        """
        playlists_insert_request = self.youtube_authentication.playlists().insert(
            part="snippet,status",
            body=dict(
                snippet=dict(
                    title="Playlist %d v4" % val,
                    description="A music playlist created with the YouTube API v3"
                ),
                status=dict(
                    privacyStatus="public"
                )
            )
        ).execute()
        return playlists_insert_request


    def add_video_to_playlist(self, videoID, playlistID):
        """Call the API to add specified video to given playlist
        """
        add_video_request = self.youtube_authentication.playlistItems().insert(
            part="snippet",
            body={
                'snippet': {
                    'playlistId': playlistID,
                    'resourceId': {
                        'kind': 'youtube#video',
                        'videoId': videoID
                    }
                }
            }
        ).execute()

class VideoSearch:

    def __init__(self, youtube, artist, song):
        """Class for querying YouTube videos"""
        self.youtube_authentication = youtube
        self.keyword = artist + ' ' + song

    def youtube_search(self, maxResults):
        """Call the API to retrieve list of results for video search
        """
        return self.youtube_authentication.search().list(q=self.keyword,
                                 part="id,snippet",
                                 maxResults=maxResults
                                 ).execute().get("items", [])

class VideoRetrieval:

    def __init__(self, youtube, artist, song):
        """Class for retrieving YouTube videos"""
        self.youtube_authentication = youtube
        self.artist = artist
        self.song = song
        self.videos = []

    def name_variations(name):
        """Computes variations of string with punctuation/symbols and without
        """
        name = name.lower()
        name_sub = re.sub("[^\w\s]", "", name)
        name_sub = " ".join(name_sub.split())
        name_and = re.sub("&", "and", name)
        return [name, name_sub, name_and]

    assert name_variations("AC/DC") == ['ac/dc', 'acdc', 'ac/dc']
    assert name_variations("Coheed & Cambria") == ['coheed & cambria', 'coheed cambria', 'coheed and cambria']

    def is_video(search_result):
        """Check if YouTube search result is a video
        """
        if search_result["id"]["kind"] == "youtube#video":
            return True
        else:
            return False


    def retrieve_video_title(search_result):
        """Store title of YouTube video
        """
        title = search_result["snippet"]["title"]
        title = title.encode(encoding='UTF-8', errors='strict')
        title = title.lower()
        return title


    def retrieve_video_user(search_result):
        """Store user of YouTube video
        """
        user = search_result["snippet"]["channelTitle"]
        user = user.encode(encoding='UTF-8', errors='strict')
        user = user.lower()
        return user


    def retrieve_video_description(search_result):
        """Store description of YouTube video
        """
        description = search_result["snippet"]["description"]
        description = description.encode(encoding='UTF-8', errors='strict')
        description = description.lower()
        return description


    def retrieve_video_id(search_result):
        """Store ID of YouTube video
        """
        youtube_id = search_result["id"]["videoId"]
        youtube_id = youtube_id.encode(encoding='UTF-8', errors='strict')
        return youtube_id


    def retrieve_video_length(youtube_auth, youtube_id):
        """Call the API to retrieve duration info for specific video
        """
        #print("YouTube ID:", youtube_id)

        video_response = youtube_auth.videos().list(
            part='contentDetails,snippet',
            id=youtube_id
        ).execute()

        #print("Video Response:", video_response)

        length = video_response.get("items", [])[0][
            "contentDetails"]["duration"]
        length = length.encode(encoding='UTF-8', errors='strict').lower()
        return length


    def parse_video_length(length):
        """Retrieve number of hours, minutes, and seconds for specific video
        """
        len_search = re.search("pt([0-9]{1,}h)?([0-9]{1,2})m([0-9]{1,2})s",
                               length, flags=re.IGNORECASE)
        if len_search is not None:
            return [len_search.group(1), len_search.group(2), len_search.group(3)]
        else:
            return None


    def create_irrv_token_list():
        """Create list of regex for irrelevant videos
        """
        irrv_list = []
        irrv_list.append("rehearsal")
        irrv_list.append("behind the scenes")
        irrv_list.append("(guitar|drum|bass) (cover|playthrough|tab)")
        irrv_list.append("\((live|cover)\)$")
        return irrv_list


    def is_irrelevant(title, irrv_list):
        """Check if video title contains terms that render video irrelevant
        """
        for token in irrv_list:
            title_search = re.search(token, title, flags=re.IGNORECASE)
            if title_search is not None:
                return True
            else:
                continue
        return False


    def official_channel_search(user):
        """Search channel title for indicators of being an official channel
        """
        user_search = re.search("band|official|VEVO|records", user,
                                flags=re.IGNORECASE)
        return user_search


    def is_official_channel(user, user_search, artist_variations):
        """Check if a video comes from an official channel by the artist/label
        """
        if user_search is not None or user in artist_variations:
            return True
        else:
            return False


    def name_fuzzy_match(variations, search_text):
        """Check if string variations of a name appear in search text
        """
        return any(x in search_text for x in variations)


    def is_auto_channel(artist_variations, song_variations, title, description):
        """Check if video comes from auto-generated channel by YouTube
        """
        if (VideoRetrieval.name_fuzzy_match(artist_variations, description) and
            VideoRetrieval.name_fuzzy_match(song_variations, title) and
                "provided to youtube" in description):
            return True
        else:
            return False

    def search_videos(self, maxResults, irrv_list):
        """Search for top relevant videos given keyword
        """
        artist_variations = VideoRetrieval.name_variations(self.artist)
        song_variations = VideoRetrieval.name_variations(self.song)
        keyword = self.artist + ' ' + self.song
        response = VideoSearch(self.youtube_authentication, 
                               self.artist, self.song).youtube_search(maxResults)
        videos = []

        #print("Video Responses:", response)

        for record in response:
            if VideoRetrieval.is_video(record):
                title = VideoRetrieval.retrieve_video_title(record)
                title = str(title, 'utf-8')
                user = VideoRetrieval.retrieve_video_user(record)
                user = str(user, 'utf-8')
                description = VideoRetrieval.retrieve_video_description(record)
                description = str(description, 'utf-8')
                youtube_id = VideoRetrieval.retrieve_video_id(record)
                youtube_id = str(youtube_id, 'utf-8')
                length = VideoRetrieval.retrieve_video_length(self.youtube_authentication, youtube_id)
                length = str(length, 'utf-8')
                user_search = VideoRetrieval.official_channel_search(user)
                length_search = VideoRetrieval.parse_video_length(length)
                artist_title_match = VideoRetrieval.name_fuzzy_match(artist_variations, title)
                song_title_match = VideoRetrieval.name_fuzzy_match(song_variations, title)
                if (not VideoRetrieval.is_irrelevant(title, irrv_list) and
                        length_search is not None):
                    # If video does not contain terms irrelevant to search
                    hours, minutes, seconds = [length_search[0],
                                               int(length_search[1]),
                                               int(length_search[2])]
                    if minutes <= 20 and hours is None:
                        # If video is less than 20 minutes
                        if VideoRetrieval.is_auto_channel(artist_variations, song_variations,
                                           title, description):
                            self.videos.append({
                                'youtube_id': youtube_id,
                                'title': title,
                                'priority_flag': 1
                            })
                        elif VideoRetrieval.is_official_channel(user, user_search, artist_variations):
                            # If the song comes from an official channel by the
                            # band/label
                            if (artist_title_match and song_title_match):
                                self.videos.append({
                                    'youtube_id': youtube_id,
                                    'title': title,
                                    'priority_flag': 2
                                })
                        elif (artist_title_match and song_title_match):
                            # If the song comes from an unofficial channel
                            self.videos.append({
                                'youtube_id': youtube_id,
                                'title': title,
                                'priority_flag': 3
                            })
        return self.videos


    def retrieve_top_video(videos):
        """Returns most relevant video for given search term
        """
        for i in range(1, 4):
            try:
                PriorityCheck = [d['priority_flag'] == i for d in videos]
                return videos[PriorityCheck.index(True)]
            except ValueError:
                if i < 3:
                    continue
                else:
                    return "No results found"



def quota_estimate(TotalPlaylists, TotalSongs):
    """Estimates current quota usage
    """
    playlist_create_cost = 50 * TotalPlaylists
    playlist_insert_cost = 50 * TotalSongs
    video_search_cost = 100 * TotalSongs
    video_info_cost = 3 * TotalSongs
    total_cost = (playlist_create_cost + playlist_insert_cost +
                  video_search_cost + video_info_cost)
    return total_cost

def main():
    NewSongs = pd.read_csv("SongsToAdd.csv", encoding = "ISO-8859-1")
    TotalSongs = len(NewSongs)
    MaxVideos = 200
    # Maximum number of videos per playlist
    TotalPlaylists = int(math.ceil(1. * TotalSongs / MaxVideos))
    AddedSongs = []
    # Contains songs that were successfully added to a playlist
    est = quota_estimate(TotalPlaylists, TotalSongs)
    if est >= 1000000:
        print("""WARNING: Your quota usage is estimated to exceed your daily limit.
        Please proceed accordingly.""")
        sys.exit()
    print("""NOTE: Your estimated quota usage is %i units.""" % est)
    try:
        youtube = YouTubeAuth().YOUTUBE_AUTHENTICATED_SERVICE
    except:
        print("Error in YouTube authentication.")
        sys.exit()
    song_counter = 0
    irrv_list = VideoRetrieval.create_irrv_token_list()
    for i in range(TotalPlaylists):
        playlist_obj = Playlists(youtube)
        playlists_insert_response = playlist_obj.create_playlist(i)
        playlist_id = playlists_insert_response["id"]
        for j in range(0, MaxVideos):
            try:
                if j + song_counter == TotalSongs:
                    break
                artist = NewSongs.loc[j + song_counter, ["Artist"]].values[0]
                song = NewSongs.loc[j + song_counter, ["Song"]].values[0]
                vid_retrieve_obj = VideoRetrieval(youtube, artist, song)
                videos = vid_retrieve_obj.search_videos(maxResults=5, irrv_list=irrv_list)
                top_vid = VideoRetrieval.retrieve_top_video(videos)
                if top_vid != "No results found":
                    playlist_obj.add_video_to_playlist(
                        top_vid['youtube_id'], playlist_id)
                    AddedSongs.append(
                        NewSongs.loc[j + song_counter, ["ID"]].values[0])
            except HttpError as e:
                MissedSongs = NewSongs[~NewSongs["ID"].isin(AddedSongs)]
                MissedSongs.to_csv(path_or_buf="MissedSongs_%d_%d.csv" %
                                   (i, song_counter), index=False, encoding = "ISO-8859-1")
                print("An HTTP error %d occurred:\n%s" % (e.resp.status, e.content))
        song_counter += MaxVideos
    MissedSongs = NewSongs[~NewSongs["ID"].isin(AddedSongs)]
    MissedSongs.to_csv(path_or_buf="MissedSongs_Final.csv", index=False)
    

if __name__ == '__main__':
    main()
