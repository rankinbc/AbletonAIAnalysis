"""
Docker wrapper for OpenL3 audio embeddings.

Runs OpenL3 in a Docker container with Python 3.11 to avoid
compatibility issues with Python 3.13/resampy/imp module.

Usage:
    from shared.openl3.docker_openl3 import DockerOpenL3Extractor

    extractor = DockerOpenL3Extractor()
    result = extractor.extract("track.wav")
    print(result.embedding.shape)  # (512,)
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Union

import numpy as np


@dataclass
class EmbeddingResult:
    """Result of embedding extraction."""
    embedding: np.ndarray
    audio_path: str
    duration_seconds: float
    sample_rate: int
    embedding_size: int
    content_type: str
    aggregation: str
    n_frames: int

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            'audio_path': self.audio_path,
            'duration_seconds': self.duration_seconds,
            'sample_rate': self.sample_rate,
            'embedding_size': self.embedding_size,
            'content_type': self.content_type,
            'aggregation': self.aggregation,
            'n_frames': self.n_frames,
            'embedding': self.embedding.tolist()
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'EmbeddingResult':
        """Create from dict."""
        return cls(
            embedding=np.array(d['embedding']),
            audio_path=d['audio_path'],
            duration_seconds=d['duration_seconds'],
            sample_rate=d['sample_rate'],
            embedding_size=d['embedding_size'],
            content_type=d['content_type'],
            aggregation=d['aggregation'],
            n_frames=d['n_frames']
        )


class DockerOpenL3Extractor:
    """
    Extract OpenL3 embeddings via Docker.

    This runs OpenL3 in a Docker container with Python 3.11,
    avoiding compatibility issues with Python 3.13.

    Usage:
        extractor = DockerOpenL3Extractor()
        result = extractor.extract("track.wav")
        print(result.embedding.shape)  # (512,)

        # Batch processing
        results = extractor.extract_batch(["track1.wav", "track2.wav"])
    """

    VALID_CONTENT_TYPES = ["music", "env"]
    VALID_EMBEDDING_SIZES = [512, 6144]

    def __init__(
        self,
        image_name: str = "openl3:latest",
        content_type: str = "music",
        embedding_size: int = 512,
        input_repr: str = "mel256",
        hop_size: float = 0.5,
        verbose: bool = False
    ):
        """
        Initialize Docker OpenL3 extractor.

        Args:
            image_name: Docker image name
            content_type: "music" or "env"
            embedding_size: 512 or 6144
            input_repr: "mel128" or "mel256"
            hop_size: Hop size in seconds
            verbose: Print progress
        """
        if content_type not in self.VALID_CONTENT_TYPES:
            raise ValueError(f"content_type must be one of {self.VALID_CONTENT_TYPES}")
        if embedding_size not in self.VALID_EMBEDDING_SIZES:
            raise ValueError(f"embedding_size must be one of {self.VALID_EMBEDDING_SIZES}")

        self.image_name = image_name
        self.content_type = content_type
        self.embedding_size = embedding_size
        self.input_repr = input_repr
        self.hop_size = hop_size
        self.verbose = verbose

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
        """Check if the OpenL3 Docker image exists."""
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

    def build_image(self, dockerfile_dir: Optional[Path] = None) -> bool:
        """
        Build the OpenL3 Docker image.

        Args:
            dockerfile_dir: Directory containing Dockerfile

        Returns:
            True if build succeeded
        """
        if dockerfile_dir is None:
            dockerfile_dir = Path(__file__).parent

        dockerfile_path = dockerfile_dir / "Dockerfile"
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
                    str(dockerfile_dir)
                ],
                capture_output=False,
                timeout=1800
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            print("Build timed out after 30 minutes")
            return False

    def extract(
        self,
        audio_path: Union[str, Path],
        aggregation: str = "mean",
        timeout: int = 300
    ) -> Optional[EmbeddingResult]:
        """
        Extract embedding from audio file.

        Args:
            audio_path: Path to audio file
            aggregation: "mean", "max", or "none"
            timeout: Timeout in seconds

        Returns:
            EmbeddingResult or None on error
        """
        audio_path = Path(audio_path).resolve()

        if not audio_path.exists():
            print(f"Audio file not found: {audio_path}")
            return None

        if not self._check_image_exists():
            print(f"Docker image {self.image_name} not found.")
            print("Build with: docker build -t openl3:latest shared/openl3/")
            return None

        # Build Docker command
        audio_dir = audio_path.parent
        audio_filename = audio_path.name

        cmd = [
            "docker", "run", "--rm",
            "-v", f"{audio_dir}:/input:ro",
            self.image_name,
            f"/input/{audio_filename}",
            "--content-type", self.content_type,
            "--embedding-size", str(self.embedding_size),
            "--input-repr", self.input_repr,
            "--hop-size", str(self.hop_size),
            "--aggregation", aggregation
        ]

        if self.verbose:
            print(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode != 0:
                print(f"OpenL3 failed: {result.stderr}")
                return None

            # Parse JSON output
            try:
                data = json.loads(result.stdout)
                return EmbeddingResult(
                    embedding=np.array(data['embedding']),
                    audio_path=data['audio_path'],
                    duration_seconds=data['duration_seconds'],
                    sample_rate=data['sample_rate'],
                    embedding_size=data['embedding_size'],
                    content_type=data['content_type'],
                    aggregation=data['aggregation'],
                    n_frames=data['n_frames']
                )
            except json.JSONDecodeError as e:
                print(f"Failed to parse output: {e}")
                print(f"Raw output: {result.stdout[:500]}")
                return None

        except subprocess.TimeoutExpired:
            print(f"Extraction timed out after {timeout} seconds")
            return None
        except FileNotFoundError:
            print("Docker not found. Is Docker installed and running?")
            return None

    def extract_batch(
        self,
        audio_paths: List[Union[str, Path]],
        aggregation: str = "mean",
        timeout_per_file: int = 300,
        progress_callback=None
    ) -> List[Optional[EmbeddingResult]]:
        """
        Extract embeddings from multiple audio files.

        For efficiency, this mounts a common parent directory
        and processes files in a single Docker call when possible.

        Args:
            audio_paths: List of audio file paths
            aggregation: Aggregation method
            timeout_per_file: Timeout per file
            progress_callback: Optional callback(i, total, path)

        Returns:
            List of EmbeddingResult (None for failed)
        """
        results = []
        total = len(audio_paths)

        for i, path in enumerate(audio_paths):
            if progress_callback:
                progress_callback(i, total, str(path))
            elif self.verbose:
                print(f"[{i+1}/{total}] Processing: {path}")

            result = self.extract(path, aggregation=aggregation, timeout=timeout_per_file)
            results.append(result)

        return results


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


def is_openl3_image_available(image_name: str = "openl3:latest") -> bool:
    """Check if the OpenL3 Docker image exists."""
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
