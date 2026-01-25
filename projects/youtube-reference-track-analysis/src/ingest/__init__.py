"""Ingest module for downloading YouTube tracks."""

from .youtube_downloader import YouTubeDownloader, DownloadResult
from .url_parser import parse_urls, extract_youtube_id

__all__ = [
    'YouTubeDownloader',
    'DownloadResult',
    'parse_urls',
    'extract_youtube_id',
]
