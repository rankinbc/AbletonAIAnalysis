"""
OpenL3 Embedding Extractor Module.

Extracts audio embeddings using the OpenL3 model for similarity search.
OpenL3 is trained on AudioSet and produces semantically meaningful
embeddings for audio comparison.

Supports two backends:
  1. Native OpenL3 (requires Python 3.11 or earlier)
  2. Docker-based (works on Python 3.13+)

The Docker backend is used automatically when native OpenL3 is unavailable.
"""

from dataclasses import dataclass
from typing import Optional, List, Tuple, Union
from pathlib import Path
import numpy as np
import warnings
import sys


@dataclass
class EmbeddingResult:
    """Result of embedding extraction."""
    embedding: np.ndarray  # Shape: (embedding_size,) for aggregated, or (n_frames, embedding_size)
    audio_path: str
    duration_seconds: float
    sample_rate: int
    embedding_size: int
    content_type: str  # "music" or "env"
    aggregation: str  # "mean", "max", "none"
    n_frames: int  # Number of embedding frames before aggregation

    def to_dict(self):
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


class OpenL3Extractor:
    """
    Extract OpenL3 embeddings from audio files.

    OpenL3 produces audio embeddings suitable for similarity search.
    Supports both 'music' and 'env' (environmental) content types,
    and 512 or 6144 dimensional embeddings.

    Usage:
        extractor = OpenL3Extractor(content_type="music", embedding_size=512)
        result = extractor.extract("track.wav")
        print(result.embedding.shape)  # (512,)
    """

    # Supported configurations
    VALID_CONTENT_TYPES = ["music", "env"]
    VALID_EMBEDDING_SIZES = [512, 6144]
    VALID_INPUT_REPR = ["mel128", "mel256"]

    def __init__(
        self,
        content_type: str = "music",
        embedding_size: int = 512,
        input_repr: str = "mel256",
        hop_size: float = 0.5,
        center: bool = True,
        verbose: bool = False
    ):
        """
        Initialize OpenL3 extractor.

        Args:
            content_type: "music" for music content, "env" for environmental sounds
            embedding_size: 512 or 6144 dimensional embeddings
            input_repr: Input representation ("mel128" or "mel256")
            hop_size: Hop size in seconds for embedding extraction
            center: Whether to center the audio before embedding
            verbose: Print progress information
        """
        if content_type not in self.VALID_CONTENT_TYPES:
            raise ValueError(f"content_type must be one of {self.VALID_CONTENT_TYPES}")
        if embedding_size not in self.VALID_EMBEDDING_SIZES:
            raise ValueError(f"embedding_size must be one of {self.VALID_EMBEDDING_SIZES}")
        if input_repr not in self.VALID_INPUT_REPR:
            raise ValueError(f"input_repr must be one of {self.VALID_INPUT_REPR}")

        self.content_type = content_type
        self.embedding_size = embedding_size
        self.input_repr = input_repr
        self.hop_size = hop_size
        self.center = center
        self.verbose = verbose

        # Model will be loaded lazily
        self._model = None
        self._openl3_available = None

    def _check_openl3_available(self) -> bool:
        """Check if OpenL3 is available."""
        if self._openl3_available is None:
            try:
                import openl3
                self._openl3_available = True
            except ImportError:
                self._openl3_available = False
        return self._openl3_available

    def _load_model(self):
        """Lazily load the OpenL3 model."""
        if self._model is not None:
            return

        if not self._check_openl3_available():
            raise ImportError(
                "OpenL3 is not installed. Install with: pip install openl3>=0.4.0\n"
                "Note: OpenL3 requires TensorFlow. If you encounter issues, try:\n"
                "  pip install tensorflow>=2.0.0 openl3"
            )

        import openl3

        if self.verbose:
            print(f"Loading OpenL3 model: content_type={self.content_type}, "
                  f"embedding_size={self.embedding_size}, input_repr={self.input_repr}")

        # Load the model
        self._model = openl3.models.load_audio_embedding_model(
            content_type=self.content_type,
            input_repr=self.input_repr,
            embedding_size=self.embedding_size
        )

        if self.verbose:
            print("OpenL3 model loaded successfully")

    def extract(
        self,
        audio_path: str,
        aggregation: str = "mean"
    ) -> EmbeddingResult:
        """
        Extract embedding vector from audio file.

        Args:
            audio_path: Path to audio file
            aggregation: How to aggregate frame embeddings
                        - "mean": Average across frames (default)
                        - "max": Max pooling across frames
                        - "none": Return all frame embeddings

        Returns:
            EmbeddingResult with embedding vector
        """
        self._load_model()

        import soundfile as sf
        import openl3

        # Load audio
        audio_path = str(audio_path)
        audio, sr = sf.read(audio_path)

        # Handle stereo by converting to mono
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)

        # Get duration
        duration_seconds = len(audio) / sr

        # Extract embeddings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            embeddings, timestamps = openl3.get_audio_embedding(
                audio,
                sr,
                model=self._model,
                content_type=self.content_type,
                input_repr=self.input_repr,
                embedding_size=self.embedding_size,
                hop_size=self.hop_size,
                center=self.center,
                verbose=self.verbose
            )

        n_frames = embeddings.shape[0]

        # Aggregate embeddings
        if aggregation == "mean":
            embedding = np.mean(embeddings, axis=0)
        elif aggregation == "max":
            embedding = np.max(embeddings, axis=0)
        elif aggregation == "none":
            embedding = embeddings  # Return all frames
        else:
            raise ValueError(f"Unknown aggregation method: {aggregation}")

        return EmbeddingResult(
            embedding=embedding,
            audio_path=audio_path,
            duration_seconds=duration_seconds,
            sample_rate=sr,
            embedding_size=self.embedding_size,
            content_type=self.content_type,
            aggregation=aggregation,
            n_frames=n_frames
        )

    def extract_from_array(
        self,
        audio: np.ndarray,
        sr: int,
        aggregation: str = "mean",
        audio_path: str = "<array>"
    ) -> EmbeddingResult:
        """
        Extract embedding from audio array.

        Args:
            audio: Audio samples as numpy array
            sr: Sample rate
            aggregation: Aggregation method
            audio_path: Optional path for reference

        Returns:
            EmbeddingResult with embedding vector
        """
        self._load_model()

        import openl3

        # Handle stereo
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)

        duration_seconds = len(audio) / sr

        # Extract embeddings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            embeddings, timestamps = openl3.get_audio_embedding(
                audio,
                sr,
                model=self._model,
                content_type=self.content_type,
                input_repr=self.input_repr,
                embedding_size=self.embedding_size,
                hop_size=self.hop_size,
                center=self.center,
                verbose=self.verbose
            )

        n_frames = embeddings.shape[0]

        # Aggregate
        if aggregation == "mean":
            embedding = np.mean(embeddings, axis=0)
        elif aggregation == "max":
            embedding = np.max(embeddings, axis=0)
        elif aggregation == "none":
            embedding = embeddings
        else:
            raise ValueError(f"Unknown aggregation method: {aggregation}")

        return EmbeddingResult(
            embedding=embedding,
            audio_path=audio_path,
            duration_seconds=duration_seconds,
            sample_rate=sr,
            embedding_size=self.embedding_size,
            content_type=self.content_type,
            aggregation=aggregation,
            n_frames=n_frames
        )

    def extract_batch(
        self,
        audio_paths: List[str],
        aggregation: str = "mean",
        progress_callback=None
    ) -> List[EmbeddingResult]:
        """
        Extract embeddings from multiple audio files.

        Args:
            audio_paths: List of paths to audio files
            aggregation: Aggregation method
            progress_callback: Optional callback(i, total, path) for progress

        Returns:
            List of EmbeddingResult objects
        """
        results = []
        total = len(audio_paths)

        for i, path in enumerate(audio_paths):
            if progress_callback:
                progress_callback(i, total, path)
            elif self.verbose:
                print(f"Processing [{i+1}/{total}]: {path}")

            try:
                result = self.extract(path, aggregation=aggregation)
                results.append(result)
            except Exception as e:
                if self.verbose:
                    print(f"  Error processing {path}: {e}")
                # Create empty result for failed extractions
                results.append(EmbeddingResult(
                    embedding=np.zeros(self.embedding_size),
                    audio_path=str(path),
                    duration_seconds=0.0,
                    sample_rate=0,
                    embedding_size=self.embedding_size,
                    content_type=self.content_type,
                    aggregation=aggregation,
                    n_frames=0
                ))

        return results

    def extract_segment(
        self,
        audio_path: str,
        start_time: float,
        end_time: float,
        aggregation: str = "mean"
    ) -> EmbeddingResult:
        """
        Extract embedding from a specific segment of an audio file.

        Args:
            audio_path: Path to audio file
            start_time: Start time in seconds
            end_time: End time in seconds
            aggregation: Aggregation method

        Returns:
            EmbeddingResult for the segment
        """
        import soundfile as sf

        # Load full audio
        audio, sr = sf.read(audio_path)

        # Handle stereo
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)

        # Extract segment
        start_sample = int(start_time * sr)
        end_sample = int(end_time * sr)
        segment = audio[start_sample:end_sample]

        return self.extract_from_array(
            segment,
            sr,
            aggregation=aggregation,
            audio_path=f"{audio_path}[{start_time:.2f}-{end_time:.2f}]"
        )


class MockOpenL3Extractor:
    """
    Mock extractor for testing when OpenL3 is not available.

    Generates random embeddings with consistent behavior for testing.
    """

    def __init__(
        self,
        content_type: str = "music",
        embedding_size: int = 512,
        **kwargs
    ):
        self.content_type = content_type
        self.embedding_size = embedding_size
        self._rng = np.random.RandomState(42)

    def extract(self, audio_path: str, aggregation: str = "mean") -> EmbeddingResult:
        """Generate mock embedding."""
        # Use path hash for reproducible results
        path_hash = hash(str(audio_path)) % (2**31)
        rng = np.random.RandomState(path_hash)

        embedding = rng.randn(self.embedding_size).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)  # Normalize

        return EmbeddingResult(
            embedding=embedding,
            audio_path=str(audio_path),
            duration_seconds=180.0,  # Mock 3 minutes
            sample_rate=44100,
            embedding_size=self.embedding_size,
            content_type=self.content_type,
            aggregation=aggregation,
            n_frames=360  # Mock ~2 frames per second
        )

    def extract_batch(
        self,
        audio_paths: List[str],
        aggregation: str = "mean",
        progress_callback=None
    ) -> List[EmbeddingResult]:
        """Generate mock embeddings for batch."""
        return [self.extract(path, aggregation) for path in audio_paths]


class DockerOpenL3Extractor:
    """
    Wrapper that delegates to Docker-based OpenL3 extraction.

    This class provides the same interface as OpenL3Extractor but
    runs OpenL3 in a Docker container with Python 3.11.
    """

    VALID_CONTENT_TYPES = ["music", "env"]
    VALID_EMBEDDING_SIZES = [512, 6144]

    def __init__(
        self,
        content_type: str = "music",
        embedding_size: int = 512,
        input_repr: str = "mel256",
        hop_size: float = 0.5,
        center: bool = True,
        verbose: bool = False
    ):
        self.content_type = content_type
        self.embedding_size = embedding_size
        self.input_repr = input_repr
        self.hop_size = hop_size
        self.center = center
        self.verbose = verbose
        self._docker_extractor = None

    def _get_docker_extractor(self):
        """Lazily initialize Docker extractor."""
        if self._docker_extractor is None:
            try:
                from shared.openl3.docker_openl3 import DockerOpenL3Extractor as _DockerExtractor
                self._docker_extractor = _DockerExtractor(
                    content_type=self.content_type,
                    embedding_size=self.embedding_size,
                    input_repr=self.input_repr,
                    hop_size=self.hop_size,
                    verbose=self.verbose
                )
            except ImportError:
                # Try relative import path
                import sys
                from pathlib import Path
                shared_path = Path(__file__).parent.parent.parent.parent.parent / "shared"
                if str(shared_path) not in sys.path:
                    sys.path.insert(0, str(shared_path))
                from openl3.docker_openl3 import DockerOpenL3Extractor as _DockerExtractor
                self._docker_extractor = _DockerExtractor(
                    content_type=self.content_type,
                    embedding_size=self.embedding_size,
                    input_repr=self.input_repr,
                    hop_size=self.hop_size,
                    verbose=self.verbose
                )
        return self._docker_extractor

    def extract(self, audio_path: str, aggregation: str = "mean") -> EmbeddingResult:
        """Extract embedding via Docker."""
        extractor = self._get_docker_extractor()
        result = extractor.extract(audio_path, aggregation=aggregation)
        if result is None:
            raise RuntimeError(f"Docker extraction failed for {audio_path}")
        return result

    def extract_batch(
        self,
        audio_paths: List[str],
        aggregation: str = "mean",
        progress_callback=None
    ) -> List[EmbeddingResult]:
        """Extract embeddings from multiple files via Docker."""
        extractor = self._get_docker_extractor()
        return extractor.extract_batch(
            audio_paths,
            aggregation=aggregation,
            progress_callback=progress_callback
        )


def _check_openl3_native() -> bool:
    """Check if native OpenL3 is available."""
    try:
        import openl3
        return True
    except ImportError:
        return False


def _check_docker_available() -> bool:
    """Check if Docker-based OpenL3 is available."""
    try:
        from shared.openl3.docker_openl3 import is_docker_available, is_openl3_image_available
        return is_docker_available() and is_openl3_image_available()
    except ImportError:
        try:
            import subprocess
            result = subprocess.run(
                ["docker", "images", "-q", "openl3:latest"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return bool(result.stdout.strip())
        except:
            return False


def get_extractor(
    use_mock: bool = False,
    use_docker: Optional[bool] = None,
    **kwargs
) -> Union[OpenL3Extractor, DockerOpenL3Extractor, MockOpenL3Extractor]:
    """
    Get an embedding extractor instance.

    Automatically selects the best available backend:
    1. Native OpenL3 (if available and Python < 3.12)
    2. Docker-based OpenL3 (if image is available)
    3. Mock extractor (fallback for testing)

    Args:
        use_mock: If True, return mock extractor
        use_docker: Force Docker backend (None = auto-detect)
        **kwargs: Arguments passed to extractor

    Returns:
        OpenL3Extractor, DockerOpenL3Extractor, or MockOpenL3Extractor
    """
    if use_mock:
        return MockOpenL3Extractor(**kwargs)

    # Auto-detect best backend
    if use_docker is None:
        # Try native first
        if _check_openl3_native():
            try:
                return OpenL3Extractor(**kwargs)
            except Exception as e:
                warnings.warn(f"Native OpenL3 failed: {e}, trying Docker...")

        # Try Docker
        if _check_docker_available():
            if kwargs.get('verbose'):
                print("Using Docker-based OpenL3 extractor")
            return DockerOpenL3Extractor(**kwargs)

        # Fall back to mock
        warnings.warn(
            "OpenL3 not available. Options:\n"
            "  1. Use Python 3.11: pip install openl3\n"
            "  2. Build Docker image: docker build -t openl3:latest shared/openl3/\n"
            "Using mock extractor for now."
        )
        return MockOpenL3Extractor(**kwargs)

    elif use_docker:
        return DockerOpenL3Extractor(**kwargs)
    else:
        return OpenL3Extractor(**kwargs)
