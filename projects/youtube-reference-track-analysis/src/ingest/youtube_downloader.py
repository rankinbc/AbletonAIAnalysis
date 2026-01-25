"""
YouTube audio downloader using yt-dlp.

Downloads audio from YouTube URLs in m4a format (no transcoding).
"""

import subprocess
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Callable
import shutil

from .url_parser import extract_youtube_id, sanitize_filename


@dataclass
class DownloadResult:
    """Result of a download operation."""
    success: bool
    youtube_id: str
    youtube_url: str
    title: Optional[str] = None
    artist: Optional[str] = None
    channel: Optional[str] = None
    duration_seconds: Optional[float] = None
    local_path: Optional[str] = None
    thumbnail_url: Optional[str] = None
    upload_date: Optional[str] = None
    error_message: Optional[str] = None


class YouTubeDownloader:
    """
    Downloads audio from YouTube using yt-dlp.

    Extracts audio in m4a format (native, no transcoding) for best quality.
    """

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        audio_format: str = "m4a",
        audio_quality: str = "best"
    ):
        """
        Initialize the downloader.

        Args:
            output_dir: Directory to save downloaded files
            audio_format: Audio format (m4a, mp3, wav, etc.)
            audio_quality: Audio quality (best, 320, 256, etc.)
        """
        self.output_dir = output_dir or Path(__file__).parent.parent.parent / "tracks"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.audio_format = audio_format
        self.audio_quality = audio_quality

        # Check if yt-dlp is available
        self.yt_dlp_path = shutil.which("yt-dlp")
        self.use_module = False

        if not self.yt_dlp_path:
            # Try using as Python module
            try:
                result = subprocess.run(
                    ["python", "-m", "yt_dlp", "--version"],
                    capture_output=True,
                    timeout=10
                )
                if result.returncode == 0:
                    self.use_module = True
                    self.yt_dlp_path = "python"  # Will use python -m yt_dlp
                else:
                    raise RuntimeError("yt-dlp module check failed")
            except Exception:
                raise RuntimeError(
                    "yt-dlp not found. Install it with: pip install yt-dlp"
                )

    def _build_cmd(self, *args) -> List[str]:
        """Build command list, handling module vs executable."""
        if self.use_module:
            return ["python", "-m", "yt_dlp"] + list(args)
        else:
            return [self.yt_dlp_path] + list(args)

    def get_video_info(self, url: str) -> Optional[dict]:
        """
        Get video metadata without downloading.

        Returns:
            Dict with video info or None on error
        """
        try:
            cmd = self._build_cmd(
                "--dump-json",
                "--no-warnings",
                url
            )
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                return json.loads(result.stdout)
            return None

        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
            return None

    def download(
        self,
        url: str,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> DownloadResult:
        """
        Download audio from a YouTube URL.

        Args:
            url: YouTube video URL
            progress_callback: Optional callback for progress updates

        Returns:
            DownloadResult with download status and metadata
        """
        youtube_id = extract_youtube_id(url)
        if not youtube_id:
            return DownloadResult(
                success=False,
                youtube_id="",
                youtube_url=url,
                error_message="Could not extract YouTube ID from URL"
            )

        # Check if already downloaded
        existing = list(self.output_dir.glob(f"{youtube_id}.*"))
        if existing:
            # Get metadata for existing file
            info = self.get_video_info(url)
            if info:
                return DownloadResult(
                    success=True,
                    youtube_id=youtube_id,
                    youtube_url=url,
                    title=info.get('title'),
                    artist=info.get('artist') or info.get('uploader'),
                    channel=info.get('channel') or info.get('uploader'),
                    duration_seconds=info.get('duration'),
                    local_path=str(existing[0]),
                    thumbnail_url=info.get('thumbnail'),
                    upload_date=info.get('upload_date')
                )

        # Build yt-dlp command
        output_template = str(self.output_dir / f"{youtube_id}.%(ext)s")

        cmd = self._build_cmd(
            "--extract-audio",
            f"--audio-format={self.audio_format}",
            "--audio-quality=0",  # Best quality
            "--no-playlist",  # Download single video only
            "--write-info-json",  # Save metadata
            "--no-warnings",
            f"--output={output_template}",
            url
        )

        if progress_callback:
            progress_callback(f"Downloading: {url}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr or "Unknown error"
                # Clean up error message
                error_msg = error_msg.split('\n')[0][:200]
                return DownloadResult(
                    success=False,
                    youtube_id=youtube_id,
                    youtube_url=url,
                    error_message=f"yt-dlp error: {error_msg}"
                )

            # Find the downloaded file
            downloaded_files = list(self.output_dir.glob(f"{youtube_id}.*"))
            audio_file = None
            for f in downloaded_files:
                if f.suffix.lower() in ['.m4a', '.mp3', '.wav', '.opus', '.webm']:
                    audio_file = f
                    break

            if not audio_file:
                return DownloadResult(
                    success=False,
                    youtube_id=youtube_id,
                    youtube_url=url,
                    error_message="Download completed but audio file not found"
                )

            # Try to read metadata from info JSON
            info_file = self.output_dir / f"{youtube_id}.info.json"
            info = {}
            if info_file.exists():
                try:
                    with open(info_file, 'r', encoding='utf-8') as f:
                        info = json.load(f)
                    # Optionally delete info file to save space
                    # info_file.unlink()
                except json.JSONDecodeError:
                    pass

            return DownloadResult(
                success=True,
                youtube_id=youtube_id,
                youtube_url=url,
                title=info.get('title'),
                artist=info.get('artist') or info.get('uploader'),
                channel=info.get('channel') or info.get('uploader'),
                duration_seconds=info.get('duration'),
                local_path=str(audio_file),
                thumbnail_url=info.get('thumbnail'),
                upload_date=info.get('upload_date')
            )

        except subprocess.TimeoutExpired:
            return DownloadResult(
                success=False,
                youtube_id=youtube_id,
                youtube_url=url,
                error_message="Download timed out"
            )
        except Exception as e:
            return DownloadResult(
                success=False,
                youtube_id=youtube_id,
                youtube_url=url,
                error_message=f"Error: {str(e)}"
            )

    def download_playlist(
        self,
        playlist_url: str,
        limit: Optional[int] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> List[DownloadResult]:
        """
        Download all videos from a playlist.

        Args:
            playlist_url: YouTube playlist URL
            limit: Maximum number of videos to download
            progress_callback: Callback(message, current, total)

        Returns:
            List of DownloadResult for each video
        """
        # First, get playlist info
        cmd = self._build_cmd(
            "--flat-playlist",
            "--dump-json",
            "--no-warnings",
            playlist_url
        )

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                return [DownloadResult(
                    success=False,
                    youtube_id="",
                    youtube_url=playlist_url,
                    error_message="Failed to get playlist info"
                )]

            # Parse playlist entries (one JSON per line)
            entries = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        entry = json.loads(line)
                        entries.append(entry)
                    except json.JSONDecodeError:
                        continue

            if limit:
                entries = entries[:limit]

            if progress_callback:
                progress_callback(f"Found {len(entries)} videos in playlist", 0, len(entries))

            # Download each video
            results = []
            for i, entry in enumerate(entries):
                video_url = f"https://www.youtube.com/watch?v={entry.get('id', entry.get('url', ''))}"

                if progress_callback:
                    progress_callback(
                        f"Downloading {i+1}/{len(entries)}: {entry.get('title', 'Unknown')}",
                        i + 1,
                        len(entries)
                    )

                result = self.download(video_url)
                results.append(result)

            return results

        except subprocess.TimeoutExpired:
            return [DownloadResult(
                success=False,
                youtube_id="",
                youtube_url=playlist_url,
                error_message="Playlist fetch timed out"
            )]
        except Exception as e:
            return [DownloadResult(
                success=False,
                youtube_id="",
                youtube_url=playlist_url,
                error_message=f"Error: {str(e)}"
            )]
