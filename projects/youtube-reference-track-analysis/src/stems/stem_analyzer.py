"""
Stem Analyzer Module

Separates audio into stems using Demucs and analyzes each stem.
Uses the existing StemSeparator from the music-analyzer project.
"""

import sys
import json
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple

import numpy as np
import librosa

# Add music-analyzer src to path for StemSeparator
music_analyzer_path = Path(__file__).parent.parent.parent.parent / "music-analyzer" / "src"
sys.path.insert(0, str(music_analyzer_path))

try:
    from stem_separator import StemSeparator, StemSeparationResult, StemType, DEMUCS_AVAILABLE
except ImportError:
    DEMUCS_AVAILABLE = False
    StemSeparator = None

# Add database module to path
db_path = Path(__file__).parent.parent / "database"
sys.path.insert(0, str(db_path))

from database import YTStem


# Formats that soundfile (libsndfile) can handle natively
NATIVE_FORMATS = {'.wav', '.flac', '.ogg', '.aiff'}
# Formats that need ffmpeg conversion
CONVERT_FORMATS = {'.m4a', '.aac', '.mp3', '.mp4', '.opus', '.webm'}


def convert_to_wav(audio_path: Path, output_dir: Optional[Path] = None) -> Tuple[Path, bool]:
    """
    Convert audio to WAV format using ffmpeg if needed.

    Args:
        audio_path: Path to audio file
        output_dir: Directory for converted file (uses temp if None)

    Returns:
        Tuple of (path to wav file, True if conversion was done)
    """
    suffix = audio_path.suffix.lower()

    # No conversion needed for native formats
    if suffix in NATIVE_FORMATS:
        return audio_path, False

    # Need to convert
    if output_dir is None:
        output_dir = Path(tempfile.gettempdir()) / "yt_stems_convert"
    output_dir.mkdir(parents=True, exist_ok=True)

    wav_path = output_dir / f"{audio_path.stem}.wav"

    # Skip if already converted
    if wav_path.exists():
        return wav_path, True

    # Convert using ffmpeg
    cmd = [
        'ffmpeg', '-y', '-i', str(audio_path),
        '-acodec', 'pcm_s16le', '-ar', '44100',
        str(wav_path)
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return wav_path, True
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg conversion failed: {e.stderr.decode() if e.stderr else str(e)}")
    except FileNotFoundError:
        raise RuntimeError("FFmpeg not found. Install ffmpeg to process m4a/mp3 files.")


@dataclass
class StemFeatures:
    """Analyzed features for a single stem."""
    stem_type: str  # vocals, drums, bass, other
    local_path: str
    peak_db: float
    rms_db: float
    spectral_centroid_hz: float
    dominant_freq_hz: Optional[float]
    presence_ratio: float  # % of track where stem is active
    energy_profile: List[float]  # Downsampled energy over time


@dataclass
class StemAnalysisResult:
    """Result of stem separation and analysis."""
    success: bool
    stems: List[StemFeatures]
    separation_time_sec: float
    cached: bool
    errors: List[str] = field(default_factory=list)


def calculate_presence_ratio(audio: np.ndarray, threshold_db: float = -40) -> float:
    """
    Calculate what percentage of the track has audible content.

    Args:
        audio: Audio samples
        threshold_db: RMS threshold below which is considered silence

    Returns:
        Ratio from 0.0 to 1.0
    """
    # Calculate RMS in windows
    frame_length = 2048
    hop_length = 512

    rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]
    rms_db = librosa.amplitude_to_db(rms, ref=np.max)

    # Count frames above threshold
    active_frames = np.sum(rms_db > threshold_db)
    total_frames = len(rms_db)

    return round(active_frames / total_frames, 3) if total_frames > 0 else 0.0


def calculate_energy_profile(audio: np.ndarray, sr: int, num_points: int = 100) -> List[float]:
    """
    Calculate downsampled energy profile over time.

    Args:
        audio: Audio samples
        sr: Sample rate
        num_points: Number of points in output profile

    Returns:
        List of energy values (normalized 0-1)
    """
    # Calculate RMS energy
    frame_length = 2048
    hop_length = 512
    rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]

    # Downsample to requested number of points
    if len(rms) > num_points:
        indices = np.linspace(0, len(rms) - 1, num_points).astype(int)
        rms = rms[indices]

    # Normalize to 0-1
    if np.max(rms) > 0:
        rms = rms / np.max(rms)

    return [round(float(x), 3) for x in rms]


def calculate_dominant_frequency(audio: np.ndarray, sr: int) -> Optional[float]:
    """
    Estimate the dominant frequency in the audio.

    Args:
        audio: Audio samples
        sr: Sample rate

    Returns:
        Dominant frequency in Hz, or None
    """
    try:
        # Use spectral centroid as a proxy for dominant frequency
        # For more accuracy, could use pitch tracking
        fft = np.abs(np.fft.rfft(audio))
        freqs = np.fft.rfftfreq(len(audio), 1/sr)

        # Find peak frequency (ignoring DC)
        fft[0] = 0  # Ignore DC
        peak_idx = np.argmax(fft)
        dominant_freq = freqs[peak_idx]

        return round(float(dominant_freq), 1) if dominant_freq > 20 else None
    except Exception:
        return None


def analyze_stem(stem_path: Path, stem_type: str) -> Optional[StemFeatures]:
    """
    Analyze a separated stem file.

    Args:
        stem_path: Path to stem audio file
        stem_type: Type of stem (vocals, drums, bass, other)

    Returns:
        StemFeatures or None on error
    """
    if not stem_path.exists():
        return None

    try:
        # Load audio
        y, sr = librosa.load(str(stem_path), sr=22050, mono=True)

        # Calculate metrics
        # Peak dB
        peak = np.max(np.abs(y))
        peak_db = round(float(librosa.amplitude_to_db([peak], ref=1.0)[0]), 1)

        # RMS dB
        rms = np.sqrt(np.mean(y**2))
        rms_db = round(float(librosa.amplitude_to_db([rms], ref=1.0)[0]), 1)

        # Spectral centroid (average)
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        spectral_centroid_hz = round(float(np.mean(centroid)), 1)

        # Dominant frequency
        dominant_freq = calculate_dominant_frequency(y, sr)

        # Presence ratio
        presence_ratio = calculate_presence_ratio(y)

        # Energy profile
        energy_profile = calculate_energy_profile(y, sr)

        return StemFeatures(
            stem_type=stem_type,
            local_path=str(stem_path),
            peak_db=peak_db,
            rms_db=rms_db,
            spectral_centroid_hz=spectral_centroid_hz,
            dominant_freq_hz=dominant_freq,
            presence_ratio=presence_ratio,
            energy_profile=energy_profile
        )

    except Exception as e:
        print(f"Error analyzing stem {stem_type}: {e}")
        return None


def extract_stems(
    audio_path: Path,
    cache_dir: Optional[Path] = None,
    force: bool = False
) -> StemAnalysisResult:
    """
    Separate audio into stems and analyze each one.

    Args:
        audio_path: Path to audio file
        cache_dir: Directory for caching separated stems
        force: Force re-separation even if cached

    Returns:
        StemAnalysisResult with analyzed stems
    """
    audio_path = Path(audio_path)
    errors = []

    if not DEMUCS_AVAILABLE:
        return StemAnalysisResult(
            success=False,
            stems=[],
            separation_time_sec=0,
            cached=False,
            errors=["Demucs not installed. Install with: pip install demucs"]
        )

    if not audio_path.exists():
        return StemAnalysisResult(
            success=False,
            stems=[],
            separation_time_sec=0,
            cached=False,
            errors=[f"Audio file not found: {audio_path}"]
        )

    # Set up cache directory
    if cache_dir is None:
        cache_dir = Path(__file__).parent.parent.parent / "cache" / "stems"

    try:
        # Convert to WAV if needed (soundfile doesn't support m4a/aac)
        wav_path = audio_path
        converted = False
        if audio_path.suffix.lower() in CONVERT_FORMATS:
            convert_dir = cache_dir / "converted"
            wav_path, converted = convert_to_wav(audio_path, convert_dir)
            if converted:
                print(f"Converted {audio_path.suffix} to WAV for stem separation")

        # Initialize separator
        separator = StemSeparator(cache_dir=str(cache_dir))

        # Separate stems
        result = separator.separate(str(wav_path), force=force)

        if not result.success:
            return StemAnalysisResult(
                success=False,
                stems=[],
                separation_time_sec=result.separation_time_seconds,
                cached=result.cached,
                errors=[result.error_message or "Separation failed"]
            )

        # Analyze each stem
        analyzed_stems = []
        for stem_type, separated_stem in result.stems.items():
            stem_features = analyze_stem(
                Path(separated_stem.file_path),
                stem_type.value  # Convert StemType enum to string
            )
            if stem_features:
                analyzed_stems.append(stem_features)
            else:
                errors.append(f"Failed to analyze {stem_type.value} stem")

        return StemAnalysisResult(
            success=True,
            stems=analyzed_stems,
            separation_time_sec=result.separation_time_seconds,
            cached=result.cached,
            errors=errors
        )

    except Exception as e:
        return StemAnalysisResult(
            success=False,
            stems=[],
            separation_time_sec=0,
            cached=False,
            errors=[str(e)]
        )


def to_db_models(result: StemAnalysisResult, track_id: int) -> List[YTStem]:
    """Convert StemAnalysisResult to database models."""
    db_stems = []

    for stem in result.stems:
        db_stem = YTStem(
            track_id=track_id,
            stem_type=stem.stem_type,
            local_path=stem.local_path,
            peak_db=stem.peak_db,
            rms_db=stem.rms_db,
            spectral_centroid_hz=stem.spectral_centroid_hz,
            dominant_freq_hz=stem.dominant_freq_hz,
            presence_ratio=stem.presence_ratio,
            energy_profile=json.dumps(stem.energy_profile)
        )
        db_stems.append(db_stem)

    return db_stems


def format_stems_display(result: StemAnalysisResult) -> str:
    """Format stem analysis for display."""
    if not result.success:
        return f"Stem separation failed: {', '.join(result.errors)}"

    lines = [
        f"Separated into {len(result.stems)} stems" +
        (f" (cached)" if result.cached else f" ({result.separation_time_sec:.1f}s)"),
        ""
    ]

    for stem in result.stems:
        lines.append(f"  {stem.stem_type.upper()}:")
        lines.append(f"    Peak: {stem.peak_db} dB | RMS: {stem.rms_db} dB")
        lines.append(f"    Spectral centroid: {stem.spectral_centroid_hz} Hz")
        lines.append(f"    Presence: {stem.presence_ratio:.0%}")

    return "\n".join(lines)
