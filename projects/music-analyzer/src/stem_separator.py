"""
Stem Separator Module

Separates mixed audio files into individual stems using Demucs:
- vocals, drums, bass, other (htdemucs_ft fine-tuned model)

Features:
- MD5-based caching to avoid re-processing
- Progress callbacks for UI feedback
- Support for WAV, MP3, FLAC, and other common formats
- High-quality AI separation using Meta's Demucs (fine-tuned variant)
"""

import hashlib
import json
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Callable, List

import numpy as np
import librosa
import soundfile as sf

# Check for Demucs availability
DEMUCS_AVAILABLE = False
try:
    import torch
    from demucs.pretrained import get_model
    from demucs.audio import save_audio
    from demucs.apply import apply_model
    import torchaudio
    DEMUCS_AVAILABLE = True
except ImportError:
    pass


class StemType(Enum):
    """Supported stem types from Demucs htdemucs model."""
    VOCALS = "vocals"
    DRUMS = "drums"
    BASS = "bass"
    OTHER = "other"


@dataclass
class SeparationProgress:
    """Progress callback data."""
    stage: str          # 'loading', 'separating', 'saving', 'complete', 'cached'
    progress_pct: float # 0-100
    message: str
    current_stem: Optional[str] = None


@dataclass
class SeparatedStem:
    """A single separated stem with metadata."""
    stem_type: StemType
    file_path: str
    duration_seconds: float
    sample_rate: int
    peak_db: float
    rms_db: float


@dataclass
class StemSeparationResult:
    """Result of stem separation operation."""
    success: bool
    source_file: str
    source_hash: str                        # MD5 hash for cache key
    stems: Dict[StemType, SeparatedStem]    # Map of stem type to separated stem
    cached: bool                            # True if retrieved from cache
    separation_time_seconds: float
    output_dir: str
    error_message: Optional[str] = None


class StemSeparator:
    """Demucs wrapper for 4-stem separation with caching."""

    SUPPORTED_FORMATS = ['.wav', '.mp3', '.flac', '.aiff', '.ogg', '.m4a', '.aac']
    STEM_NAMES = ['vocals', 'drums', 'bass', 'other']

    def __init__(
        self,
        cache_dir: str = "./cache/stems",
        model: str = "htdemucs_ft",
        verbose: bool = False
    ):
        """
        Initialize the stem separator.

        Args:
            cache_dir: Directory for caching separated stems
            model: Demucs model to use (default htdemucs)
            verbose: Enable verbose output
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.model_name = model
        self.verbose = verbose
        self._model = None

        if not DEMUCS_AVAILABLE:
            raise ImportError(
                "Demucs is not installed. Install it with: pip install demucs"
            )

    def _get_model(self):
        """Lazy load the Demucs model."""
        if self._model is None:
            self._model = get_model(self.model_name)
            self._model.eval()
            # Use CPU by default, GPU if available
            if torch.cuda.is_available():
                self._model = self._model.cuda()
        return self._model

    def separate(
        self,
        audio_path: str,
        output_dir: Optional[str] = None,
        force: bool = False,
        progress_callback: Optional[Callable[[SeparationProgress], None]] = None
    ) -> StemSeparationResult:
        """
        Separate audio file into stems using Demucs.

        Args:
            audio_path: Path to audio file (WAV, MP3, FLAC, etc.)
            output_dir: Custom output directory (uses cache if None)
            force: Force re-separation even if cached
            progress_callback: Callback for progress updates

        Returns:
            StemSeparationResult with paths to separated stems
        """
        start_time = time.time()
        path = Path(audio_path)

        # Validate input
        if not path.exists():
            return StemSeparationResult(
                success=False,
                source_file=str(path),
                source_hash="",
                stems={},
                cached=False,
                separation_time_seconds=0,
                output_dir="",
                error_message=f"File not found: {audio_path}"
            )

        if path.suffix.lower() not in self.SUPPORTED_FORMATS:
            return StemSeparationResult(
                success=False,
                source_file=str(path),
                source_hash="",
                stems={},
                cached=False,
                separation_time_seconds=0,
                output_dir="",
                error_message=f"Unsupported format: {path.suffix}. Supported: {self.SUPPORTED_FORMATS}"
            )

        # Compute file hash for cache key
        file_hash = self._compute_file_hash(str(path))

        # Check cache
        if not force:
            cached_result = self.get_cached_stems(audio_path)
            if cached_result:
                if progress_callback:
                    progress_callback(SeparationProgress(
                        stage='cached',
                        progress_pct=100,
                        message='Using cached stems'
                    ))
                return cached_result

        # Determine output directory
        if output_dir:
            stems_dir = Path(output_dir)
        else:
            stems_dir = self.cache_dir / file_hash

        stems_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Report progress: loading
            if progress_callback:
                progress_callback(SeparationProgress(
                    stage='loading',
                    progress_pct=10,
                    message=f'Loading {path.name}...'
                ))

            # Load the audio file using soundfile (handles FLAC, WAV, etc.)
            audio_data, sr = sf.read(str(path), dtype='float32')

            # Convert to tensor (channels, samples)
            if len(audio_data.shape) == 1:
                # Mono - make stereo
                wav = torch.from_numpy(audio_data).unsqueeze(0).repeat(2, 1)
            else:
                # Already stereo/multi-channel - transpose to (channels, samples)
                wav = torch.from_numpy(audio_data.T)
                if wav.shape[0] == 1:
                    wav = wav.repeat(2, 1)
                elif wav.shape[0] > 2:
                    wav = wav[:2]

            # Get model and its sample rate
            model = self._get_model()
            model_sr = model.samplerate

            # Resample if needed
            if sr != model_sr:
                wav = torchaudio.functional.resample(wav, sr, model_sr)
                sr = model_sr

            # Add batch dimension
            wav = wav.unsqueeze(0)

            # Move to same device as model
            device = next(model.parameters()).device
            wav = wav.to(device)

            # Report progress: separating
            if progress_callback:
                progress_callback(SeparationProgress(
                    stage='separating',
                    progress_pct=20,
                    message='Separating stems with Demucs (this may take 1-3 minutes)...'
                ))

            # Apply the model
            with torch.no_grad():
                sources = apply_model(model, wav, progress=self.verbose)

            # Get source names from model
            source_names = model.sources

            # Save each stem
            actual_output_dir = stems_dir / path.stem
            actual_output_dir.mkdir(parents=True, exist_ok=True)

            stems = {}
            for i, stem_name in enumerate(self.STEM_NAMES):
                if progress_callback:
                    progress_callback(SeparationProgress(
                        stage='saving',
                        progress_pct=60 + (i + 1) * 10,
                        message=f'Saving {stem_name}...',
                        current_stem=stem_name
                    ))

                stem_path = actual_output_dir / f"{stem_name}.wav"

                # Find the source index
                if stem_name in source_names:
                    src_idx = source_names.index(stem_name)
                    stem_audio = sources[0, src_idx]  # Remove batch dim, get source

                    # Save using soundfile (more compatible than torchaudio)
                    stem_audio_cpu = stem_audio.cpu().numpy()
                    # Transpose from (channels, samples) to (samples, channels) for soundfile
                    stem_audio_cpu = stem_audio_cpu.T
                    sf.write(str(stem_path), stem_audio_cpu, sr)

                    # Analyze the saved stem
                    stem_type = StemType(stem_name)
                    stem_info = self._analyze_stem(str(stem_path), stem_type)
                    stems[stem_type] = stem_info

            # Save cache metadata
            self._save_cache_metadata(file_hash, str(path), str(actual_output_dir))

            # Report complete
            if progress_callback:
                progress_callback(SeparationProgress(
                    stage='complete',
                    progress_pct=100,
                    message='Separation complete'
                ))

            separation_time = time.time() - start_time

            return StemSeparationResult(
                success=True,
                source_file=str(path.absolute()),
                source_hash=file_hash,
                stems=stems,
                cached=False,
                separation_time_seconds=separation_time,
                output_dir=str(actual_output_dir)
            )

        except Exception as e:
            return StemSeparationResult(
                success=False,
                source_file=str(path),
                source_hash=file_hash,
                stems={},
                cached=False,
                separation_time_seconds=time.time() - start_time,
                output_dir=str(stems_dir),
                error_message=str(e)
            )

    def get_cached_stems(
        self,
        audio_path: str
    ) -> Optional[StemSeparationResult]:
        """
        Retrieve cached stems if available.

        Args:
            audio_path: Original audio file path

        Returns:
            StemSeparationResult if cached, None otherwise
        """
        file_hash = self._compute_file_hash(audio_path)
        cache_meta_path = self.cache_dir / f"{file_hash}.json"

        if not cache_meta_path.exists():
            return None

        try:
            with open(cache_meta_path, 'r') as f:
                meta = json.load(f)

            stems_dir = Path(meta['output_dir'])

            # Verify all stems still exist
            stems = {}
            for stem_name in self.STEM_NAMES:
                stem_path = stems_dir / f"{stem_name}.wav"
                if not stem_path.exists():
                    # Cache is invalid
                    return None

                stem_type = StemType(stem_name)
                stem_info = self._analyze_stem(str(stem_path), stem_type)
                stems[stem_type] = stem_info

            return StemSeparationResult(
                success=True,
                source_file=meta['source_file'],
                source_hash=file_hash,
                stems=stems,
                cached=True,
                separation_time_seconds=0,
                output_dir=str(stems_dir)
            )

        except (json.JSONDecodeError, KeyError):
            return None

    def clear_cache(
        self,
        audio_path: Optional[str] = None,
        older_than_days: Optional[int] = None
    ) -> int:
        """
        Clear stem cache.

        Args:
            audio_path: Clear cache for specific file (all if None)
            older_than_days: Only clear entries older than N days

        Returns:
            Number of cache entries cleared
        """
        cleared = 0

        if audio_path:
            # Clear specific file
            file_hash = self._compute_file_hash(audio_path)
            cache_dir = self.cache_dir / file_hash
            cache_meta = self.cache_dir / f"{file_hash}.json"

            if cache_dir.exists():
                shutil.rmtree(cache_dir)
                cleared += 1
            if cache_meta.exists():
                cache_meta.unlink()

        else:
            # Clear all or old entries
            now = datetime.now()

            for meta_file in self.cache_dir.glob("*.json"):
                try:
                    with open(meta_file, 'r') as f:
                        meta = json.load(f)

                    should_clear = True
                    if older_than_days:
                        cached_time = datetime.fromisoformat(meta.get('timestamp', '2000-01-01'))
                        age_days = (now - cached_time).days
                        should_clear = age_days > older_than_days

                    if should_clear:
                        file_hash = meta_file.stem
                        cache_dir = self.cache_dir / file_hash

                        if cache_dir.exists():
                            shutil.rmtree(cache_dir)
                        meta_file.unlink()
                        cleared += 1

                except (json.JSONDecodeError, KeyError):
                    # Invalid cache entry, remove it
                    meta_file.unlink()
                    cleared += 1

        return cleared

    def _compute_file_hash(self, file_path: str) -> str:
        """Compute MD5 hash of file for cache key."""
        hash_md5 = hashlib.md5()
        path = Path(file_path)

        # Use file path + size + mtime for faster hashing
        # (avoids reading entire file for large audio files)
        stat = path.stat()
        hash_input = f"{path.absolute()}:{stat.st_size}:{stat.st_mtime}"
        hash_md5.update(hash_input.encode())

        return hash_md5.hexdigest()[:16]  # Use first 16 chars

    def _analyze_stem(self, stem_path: str, stem_type: StemType) -> SeparatedStem:
        """Analyze a separated stem for basic metrics."""
        y, sr = librosa.load(stem_path, sr=None, mono=True)
        duration = librosa.get_duration(y=y, sr=sr)

        # Calculate levels
        peak = np.max(np.abs(y))
        peak_db = float(20 * np.log10(peak + 1e-10))

        rms = np.sqrt(np.mean(y ** 2))
        rms_db = float(20 * np.log10(rms + 1e-10))

        return SeparatedStem(
            stem_type=stem_type,
            file_path=stem_path,
            duration_seconds=duration,
            sample_rate=sr,
            peak_db=peak_db,
            rms_db=rms_db
        )

    def _save_cache_metadata(self, file_hash: str, source_file: str, output_dir: str):
        """Save cache metadata for later retrieval."""
        meta = {
            'source_file': source_file,
            'output_dir': output_dir,
            'timestamp': datetime.now().isoformat(),
            'model': self.model_name
        }

        meta_path = self.cache_dir / f"{file_hash}.json"
        with open(meta_path, 'w') as f:
            json.dump(meta, f, indent=2)


def separate_audio(
    audio_path: str,
    output_dir: Optional[str] = None,
    force: bool = False
) -> StemSeparationResult:
    """Quick function to separate an audio file into stems."""
    separator = StemSeparator()
    return separator.separate(audio_path, output_dir, force)
