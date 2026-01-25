"""
URL parsing utilities for YouTube links.

Handles single URLs, playlist URLs, and URL files.
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse, parse_qs


def extract_youtube_id(url: str) -> Optional[str]:
    """
    Extract YouTube video ID from various URL formats.

    Supports:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://music.youtube.com/watch?v=VIDEO_ID
        - https://www.youtube.com/embed/VIDEO_ID
        - https://www.youtube.com/v/VIDEO_ID

    Returns:
        Video ID string or None if not found
    """
    if not url:
        return None

    url = url.strip()

    # Pattern for youtu.be short URLs
    short_pattern = r'youtu\.be/([a-zA-Z0-9_-]{11})'
    match = re.search(short_pattern, url)
    if match:
        return match.group(1)

    # Pattern for standard youtube.com URLs
    parsed = urlparse(url)

    # Check for video ID in query params
    if 'youtube.com' in parsed.netloc or 'youtube-nocookie.com' in parsed.netloc:
        query = parse_qs(parsed.query)
        if 'v' in query:
            video_id = query['v'][0]
            if len(video_id) == 11:
                return video_id

    # Check for /embed/ or /v/ paths
    embed_pattern = r'/(?:embed|v)/([a-zA-Z0-9_-]{11})'
    match = re.search(embed_pattern, url)
    if match:
        return match.group(1)

    return None


def is_playlist_url(url: str) -> bool:
    """Check if URL is a YouTube playlist."""
    if not url:
        return False

    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    return 'list' in query


def extract_playlist_id(url: str) -> Optional[str]:
    """Extract playlist ID from URL."""
    if not url:
        return None

    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    if 'list' in query:
        return query['list'][0]

    return None


def parse_url_file(file_path: Path) -> List[str]:
    """
    Parse a text file containing URLs (one per line).

    Ignores:
        - Empty lines
        - Lines starting with # (comments)
        - Lines that don't look like URLs
    """
    if not file_path.exists():
        return []

    urls = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            # Basic URL validation
            if line.startswith(('http://', 'https://', 'www.')):
                urls.append(line)
            elif 'youtube.com' in line or 'youtu.be' in line:
                # Handle URLs without protocol
                urls.append(f'https://{line}')

    return urls


def parse_urls(input_str: str) -> Tuple[List[str], bool, Optional[str]]:
    """
    Parse input which could be a single URL, playlist URL, or file path.

    Returns:
        (urls: List[str], is_playlist: bool, playlist_id: Optional[str])
    """
    input_str = input_str.strip()

    # Check if it's a file path
    input_path = Path(input_str)
    if input_path.exists() and input_path.is_file():
        urls = parse_url_file(input_path)
        return urls, False, None

    # Check if it's a playlist
    if is_playlist_url(input_str):
        playlist_id = extract_playlist_id(input_str)
        return [input_str], True, playlist_id

    # Single URL
    return [input_str], False, None


def sanitize_filename(title: str, max_length: int = 100) -> str:
    """
    Sanitize a string for use as a filename.

    Removes/replaces characters that are invalid in filenames.
    """
    if not title:
        return "untitled"

    # Replace invalid characters
    invalid_chars = r'<>:"/\|?*'
    for char in invalid_chars:
        title = title.replace(char, '_')

    # Replace multiple spaces/underscores with single underscore
    title = re.sub(r'[\s_]+', '_', title)

    # Remove leading/trailing underscores and spaces
    title = title.strip('_ ')

    # Truncate if too long
    if len(title) > max_length:
        title = title[:max_length].rstrip('_')

    return title or "untitled"
