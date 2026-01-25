"""
File-hash based cache for allin1 analysis results.

Caches analysis results by SHA256 hash of audio files, allowing
results to be reused across sessions without re-analyzing.
"""

import hashlib
import json
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .docker_allin1 import Allin1Result, Allin1Segment


class Allin1Cache:
    """
    File-hash based cache for allin1 results.

    Usage:
        cache = Allin1Cache(Path("~/.cache/allin1"))

        # Check cache first
        result = cache.get(audio_path)
        if result is None:
            result = analyzer.analyze(audio_path)
            cache.set(audio_path, result)
    """

    def __init__(self, cache_dir: Path):
        """
        Initialize cache manager.

        Args:
            cache_dir: Directory to store cached results
        """
        self.cache_dir = Path(cache_dir).expanduser().resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_file_hash(self, audio_path: Path) -> str:
        """
        Compute SHA256 hash of audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            Hex-encoded SHA256 hash
        """
        sha256 = hashlib.sha256()
        with open(audio_path, 'rb') as f:
            # Read in 64KB chunks for memory efficiency
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _get_cache_path(self, file_hash: str) -> Path:
        """Get cache file path for a given hash."""
        # Use first 2 chars as subdirectory for better filesystem performance
        subdir = self.cache_dir / file_hash[:2]
        subdir.mkdir(exist_ok=True)
        return subdir / f"{file_hash}.json"

    def get(self, audio_path: Path) -> Optional["Allin1Result"]:
        """
        Get cached result for an audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            Allin1Result if cached, None otherwise
        """
        # Import here to avoid circular imports
        from .docker_allin1 import Allin1Result, Allin1Segment

        audio_path = Path(audio_path).resolve()
        if not audio_path.exists():
            return None

        file_hash = self.get_file_hash(audio_path)
        cache_path = self._get_cache_path(file_hash)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)

            return Allin1Result(
                bpm=data['bpm'],
                beats=data['beats'],
                downbeats=data['downbeats'],
                segments=[
                    Allin1Segment(
                        label=s['label'],
                        start=s['start'],
                        end=s['end']
                    )
                    for s in data['segments']
                ]
            )
        except (json.JSONDecodeError, KeyError, IOError) as e:
            # Invalid cache entry, remove it
            cache_path.unlink(missing_ok=True)
            return None

    def set(self, audio_path: Path, result: "Allin1Result") -> None:
        """
        Cache result for an audio file.

        Args:
            audio_path: Path to audio file
            result: Analysis result to cache
        """
        audio_path = Path(audio_path).resolve()
        if not audio_path.exists():
            return

        file_hash = self.get_file_hash(audio_path)
        cache_path = self._get_cache_path(file_hash)

        data = {
            'bpm': result.bpm,
            'beats': result.beats,
            'downbeats': result.downbeats,
            'segments': [
                {
                    'label': s.label,
                    'start': s.start,
                    'end': s.end
                }
                for s in result.segments
            ],
            'source_file': str(audio_path),
            'file_hash': file_hash
        }

        with open(cache_path, 'w') as f:
            json.dump(data, f, indent=2)

    def has(self, audio_path: Path) -> bool:
        """
        Check if result is cached for an audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            True if cached result exists
        """
        audio_path = Path(audio_path).resolve()
        if not audio_path.exists():
            return False

        file_hash = self.get_file_hash(audio_path)
        cache_path = self._get_cache_path(file_hash)
        return cache_path.exists()

    def clear(self) -> int:
        """
        Clear all cached results.

        Returns:
            Number of cache entries removed
        """
        count = 0
        for json_file in self.cache_dir.rglob("*.json"):
            json_file.unlink()
            count += 1
        return count

    def stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats (count, size_bytes)
        """
        count = 0
        size = 0
        for json_file in self.cache_dir.rglob("*.json"):
            count += 1
            size += json_file.stat().st_size

        return {
            'count': count,
            'size_bytes': size,
            'cache_dir': str(self.cache_dir)
        }
