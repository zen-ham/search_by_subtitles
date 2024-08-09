import argparse
import os
import re
from typing import List, Dict
from urllib.parse import urlparse, parse_qs

import dill
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from fuzzywuzzy import fuzz
from googleapiclient.discovery import build
from tqdm import tqdm

# Replace with your actual API key
YOUTUBE_API_KEY = "YOUR YOUTUBE API KEY"


def get_channel_id(url):
    response = requests.get(url)

    if response.status_code == 200:
        # Look for the canonical URL that usually contains the correct channel ID
        match = re.search(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[a-zA-Z0-9_-]+)">', response.text)

        if match:
            return match.group(1)
        else:
            print("Channel ID not found in the canonical URL.")
    else:
        print("Failed to fetch the page.")

    return None


def get_all_video_ids(channel_id: str) -> List[Dict[str, str]]:
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    videos = []
    next_page_token = None

    while True:
        request = youtube.search().list(
            part="id,snippet",
            channelId=channel_id,
            maxResults=50,
            type="video",
            pageToken=next_page_token
        )
        response = request.execute()

        for item in response["items"]:
            videos.append({
                "id": item["id"]["videoId"],
                "title": item["snippet"]["title"]
            })

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return videos


def get_video_subtitles(video_id: str) -> str:
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([entry["text"] for entry in transcript])
    except Exception:
        return ""


def fuzzy_search(text: str, search_phrases: List[str], threshold: int = 80) -> bool:
    return any(fuzz.partial_ratio(phrase.lower(), text.lower()) >= threshold for phrase in search_phrases)


def search_videos(channel_url: str, search_phrases: List[str]) -> List[Dict[str, str]]:
    cache_file = f"cache_{channel_url.split('/')[-1]}.pkl"

    if os.path.exists(cache_file):
        with open(cache_file, "rb") as f:
            videos = dill.load(f)
    else:
        channel_id = get_channel_id(channel_url)
        videos = get_all_video_ids(channel_id)
        for video in tqdm(videos, desc="Fetching subtitles"):
            video["subtitles"] = get_video_subtitles(video["id"])

        with open(cache_file, "wb") as f:
            dill.dump(videos, f)

    matching_videos = [
        {"title": video["title"], "url": f"https://www.youtube.com/watch?v={video['id']}"}
        for video in videos
        if fuzzy_search(video["subtitles"], search_phrases)
    ]

    return matching_videos


def main():
    parser = argparse.ArgumentParser(description="Search YouTube videos by subtitle content")
    parser.add_argument("-c", "--channel", help="YouTube channel URL")
    parser.add_argument("-t", "--text", help="Search text (use '|' to separate multiple phrases)")

    args = parser.parse_args()

    if not args.channel:
        args.channel = input("Enter the YouTube channel URL: ")
    if not args.text:
        args.text = input("Enter the search text (use '|' to separate multiple phrases): ")

    search_phrases = args.text.split("|")
    matching_videos = search_videos(args.channel, search_phrases)

    if matching_videos:
        print("\nMatching videos:")
        for video in matching_videos:
            print(f"Title: {video['title']}")
            print(f"URL: {video['url']}")
            print()
    else:
        print("No matching videos found.")


if __name__ == "__main__":
    main()
