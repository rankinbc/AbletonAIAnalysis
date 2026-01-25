"""
Docker wrapper for allin1 music structure analysis.

Runs allin1 in a Docker container with Python 3.11 to avoid
compatibility issues with Python 3.13/madmom/natten.

Supports optional file-hash based caching for repeated analyses.
"""

import json
import subprocess
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class Allin1Segment:
    """A detected segment from allin1."""
    label: str
    start: float
    end: float


@dataclass
class Allin1Result:
    """Result from allin1 analysis."""
    bpm: float
    beats: List[float]
    downbeats: List[float]
    segments: List[Allin1Segment]


class DockerAllin1:
    """
    Wrapper to run allin1 via Docker.

    Usage:
        # Without caching (default)
        analyzer = DockerAllin1()
        result = analyzer.analyze("/path/to/audio.wav")

        # With caching enabled
        analyzer = DockerAllin1(
            enable_cache=True,
            cache_dir=Path("~/.cache/allin1")
        )
        result = analyzer.analyze("/path/to/audio.wav")

        print(f"BPM: {result.bpm}")
        for seg in result.segments:
            print(f"{seg.label}: {seg.start:.2f}s - {seg.end:.2f}s")
    """

    def __init__(
        self,
        image_name: str = "allin1:latest",
        enable_cache: bool = False,
        cache_dir: Optional[Path] = None,
        use_gpu: bool = False
    ):
        """
        Initialize Docker allin1 wrapper.

        Args:
            image_name: Docker image name (default: allin1:latest)
            enable_cache: Whether to cache results by file hash
            cache_dir: Directory for cache (default: ~/.cache/allin1)
            use_gpu: Whether to use GPU (requires nvidia-docker)
        """
        self.image_name = image_name
        self.enable_cache = enable_cache
        self.use_gpu = use_gpu
        self._cache = None

        if enable_cache:
            from .cache import Allin1Cache
            if cache_dir is None:
                cache_dir = Path.home() / ".cache" / "allin1"
            self._cache = Allin1Cache(cache_dir)

        self._check_docker()

    def _check_docker(self) -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _check_image_exists(self) -> bool:
        """Check if the allin1 Docker image exists."""
        try:
            result = subprocess.run(
                ["docker", "images", "-q", self.image_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            return bool(result.stdout.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def build_image(self, dockerfile_path: Optional[Path] = None) -> bool:
        """
        Build the allin1 Docker image.

        Args:
            dockerfile_path: Path to Dockerfile (auto-detected if None)

        Returns:
            True if build succeeded
        """
        if dockerfile_path is None:
            # Try to find Dockerfile relative to this file
            dockerfile_path = Path(__file__).parent / "Dockerfile"

        if not dockerfile_path.exists():
            print(f"Dockerfile not found: {dockerfile_path}")
            return False

        print(f"Building Docker image {self.image_name}...")
        print("This may take 5-10 minutes on first build...")

        try:
            result = subprocess.run(
                [
                    "docker", "build",
                    "-t", self.image_name,
                    "-f", str(dockerfile_path),
                    str(dockerfile_path.parent)
                ],
                capture_output=False,  # Show build output
                timeout=1800  # 30 minute timeout
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            print("Build timed out after 30 minutes")
            return False

    def analyze(
        self,
        audio_path: Path,
        timeout: int = 300
    ) -> Optional[Allin1Result]:
        """
        Analyze an audio file using allin1 in Docker.

        Args:
            audio_path: Path to audio file
            timeout: Analysis timeout in seconds (default 5 minutes)

        Returns:
            Allin1Result or None on error
        """
        audio_path = Path(audio_path).resolve()

        if not audio_path.exists():
            print(f"Audio file not found: {audio_path}")
            return None

        # Check cache first
        if self._cache is not None:
            cached_result = self._cache.get(audio_path)
            if cached_result is not None:
                print(f"Using cached result for: {audio_path.name}")
                return cached_result

        # Check if image exists
        if not self._check_image_exists():
            print(f"Docker image {self.image_name} not found.")
            print("Build it with: docker build -t allin1:latest -f Dockerfile .")
            return None

        # Build Docker command
        audio_dir = audio_path.parent
        audio_filename = audio_path.name

        cmd = ["docker", "run", "--rm"]

        # Add GPU support if enabled
        if self.use_gpu:
            cmd.extend(["--gpus", "all"])

        # Mount volumes
        cmd.extend([
            "-v", f"{audio_dir}:/input:ro",
            self.image_name,
            "--json",
            f"/input/{audio_filename}"
        ])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode != 0:
                print(f"allin1 failed: {result.stderr}")
                return None

            # Parse JSON output
            try:
                data = json.loads(result.stdout)
                analysis_result = Allin1Result(
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

                # Cache result if caching enabled
                if self._cache is not None:
                    self._cache.set(audio_path, analysis_result)

                return analysis_result

            except json.JSONDecodeError as e:
                print(f"Failed to parse allin1 output: {e}")
                print(f"Raw output: {result.stdout[:500]}")
                return None

        except subprocess.TimeoutExpired:
            print(f"Analysis timed out after {timeout} seconds")
            return None
        except FileNotFoundError:
            print("Docker not found. Is Docker installed and running?")
            return None

    def analyze_batch(
        self,
        audio_paths: List[Path],
        timeout_per_file: int = 300
    ) -> List[Optional[Allin1Result]]:
        """
        Analyze multiple audio files.

        Args:
            audio_paths: List of audio file paths
            timeout_per_file: Timeout per file in seconds

        Returns:
            List of results (None for failed analyses)
        """
        results = []
        cached_count = 0
        analyzed_count = 0

        for i, path in enumerate(audio_paths):
            print(f"[{i+1}/{len(audio_paths)}] Analyzing: {path.name}")

            # Track cache hits
            was_cached = self._cache is not None and self._cache.has(path)
            result = self.analyze(path, timeout=timeout_per_file)
            results.append(result)

            if was_cached and result is not None:
                cached_count += 1
            elif result is not None:
                analyzed_count += 1

        if self._cache is not None and cached_count > 0:
            print(f"\nCache stats: {cached_count} cached, {analyzed_count} analyzed")

        return results

    def cache_stats(self) -> Optional[dict]:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats, or None if caching disabled
        """
        if self._cache is None:
            return None
        return self._cache.stats()

    def clear_cache(self) -> int:
        """
        Clear the analysis cache.

        Returns:
            Number of entries cleared, or 0 if caching disabled
        """
        if self._cache is None:
            return 0
        return self._cache.clear()


def is_docker_available() -> bool:
    """Check if Docker is available on the system."""
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def is_allin1_image_available(image_name: str = "allin1:latest") -> bool:
    """Check if the allin1 Docker image exists."""
    try:
        result = subprocess.run(
            ["docker", "images", "-q", image_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
