#!/usr/bin/env python3
"""
Batch ingest YouTube playlist and set ratings.

Ingests all tracks from the playlist JSON file.
Tracks up to and including "Baby Boomers" get rating 3 (favorites).
All other tracks get rating 1.
"""

import json
import sys
import re
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from database import init_yt_schema, YTRepository, YTTrack
from ingest import YouTubeDownloader, extract_youtube_id

# Path to playlist file
PLAYLIST_FILE = Path(r"C:\Users\badmin\Desktop\yt trance playlist extract\YoutubeTrancePlaylistSongs.txt")

# Tracks up to and including this one get rating 3
CUTOFF_TITLE = "Baby Boomers"


def load_playlist(file_path: Path) -> list:
    """Load and parse the playlist JSON file."""
    content = file_path.read_text(encoding='utf-8')
    return json.loads(content)


def main():
    # Initialize database
    db_path = Path(__file__).parent.parent.parent / "data" / "projects.db"
    success, msg = init_yt_schema(db_path)
    print(f"Database: {msg}")

    repo = YTRepository(db_path)

    # Load playlist
    print(f"\nLoading playlist from: {PLAYLIST_FILE}")
    tracks = load_playlist(PLAYLIST_FILE)
    print(f"Found {len(tracks)} tracks\n")

    # Find cutoff index
    cutoff_index = None
    for i, track in enumerate(tracks):
        if CUTOFF_TITLE.lower() in track['title'].lower():
            cutoff_index = i
            print(f"Cutoff track '{CUTOFF_TITLE}' found at index {i}")
            break

    if cutoff_index is None:
        print(f"WARNING: Cutoff track '{CUTOFF_TITLE}' not found! All tracks will get rating 1.")
        cutoff_index = -1

    # Initialize downloader
    tracks_dir = Path(__file__).parent / "tracks"
    tracks_dir.mkdir(exist_ok=True)

    try:
        downloader = YouTubeDownloader(output_dir=tracks_dir)
    except RuntimeError as e:
        print(f"ERROR: {e}")
        print("\nTo install yt-dlp: pip install yt-dlp")
        return

    # Process each track
    print("\n" + "=" * 60)
    print("INGESTING TRACKS")
    print("=" * 60 + "\n")

    success_count = 0
    error_count = 0
    skipped_count = 0

    for i, track_data in enumerate(tracks):
        title = track_data['title']
        url = track_data['url']
        rating = 3 if i <= cutoff_index else 1
        rating_stars = "*" * rating

        print(f"[{i+1}/{len(tracks)}] {rating_stars} {title[:50]}...")

        # Extract YouTube ID
        youtube_id = extract_youtube_id(url)
        if not youtube_id:
            print(f"  ERROR: Could not extract YouTube ID from URL")
            error_count += 1
            continue

        # Check if already exists
        existing = repo.get_track_by_youtube_id(youtube_id)
        if existing:
            print(f"  Already exists, updating rating...")
            repo.set_rating(youtube_id, rating)
            skipped_count += 1
            continue

        # Download
        result = downloader.download(url)

        if not result.success:
            print(f"  DOWNLOAD FAILED: {result.error_message}")
            error_count += 1
            continue

        # Create track record
        yt_track = YTTrack(
            youtube_id=result.youtube_id,
            youtube_url=result.youtube_url,
            title=result.title or title,
            artist=result.artist,
            channel=result.channel,
            duration_seconds=result.duration_seconds,
            local_path=result.local_path,
            thumbnail_url=result.thumbnail_url,
            upload_date=result.upload_date,
            genre_tag='trance',
            rating=rating
        )

        saved, msg, track_id = repo.create_track(yt_track)
        if saved:
            # Set rating (in case track existed)
            repo.set_rating(youtube_id, rating)
            print(f"  OK: {result.title or youtube_id}")
            success_count += 1
        else:
            print(f"  DB ERROR: {msg}")
            error_count += 1

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total tracks:    {len(tracks)}")
    print(f"Downloaded:      {success_count}")
    print(f"Already existed: {skipped_count}")
    print(f"Errors:          {error_count}")
    print(f"\nRating 3 (***):  {cutoff_index + 1} tracks")
    print(f"Rating 1 (*):    {len(tracks) - cutoff_index - 1} tracks")

    print("\nTo analyze all tracks, run:")
    print("  python yt_analyzer.py analyze --all-pending --features")
    print("\nTo list favorites:")
    print("  python yt_analyzer.py list --favorites")


if __name__ == '__main__':
    main()
