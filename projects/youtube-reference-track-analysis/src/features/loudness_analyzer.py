"""
Loudness analysis using pyloudnorm.

Measures LUFS (Loudness Units Full Scale) according to ITU-R BS.1770
and EBU R128 standards, which are industry standards for broadcast
and streaming loudness normalization.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple
import numpy as np


@dataclass
class LoudnessFeatures:
    """Extracted loudness features."""
    integrated_lufs: float  # Overall loudness (ITU-R BS.1770)
    loudness_range_lu: float  # LRA - dynamic variation
    true_peak_dbtp: float  # True peak level
    short_term_max_lufs: float  # Maximum short-term loudness
    short_term_min_lufs: float  # Minimum short-term loudness (excl. silence)
    momentary_max_lufs: float  # Maximum momentary loudness
    dynamic_range_db: float  # Difference between loud and quiet parts
    # Streaming platform targets for reference
    spotify_gain_db: float  # Gain needed to reach Spotify target (-14 LUFS)
    youtube_gain_db: float  # Gain needed to reach YouTube target (-14 LUFS)
    apple_gain_db: float  # Gain needed to reach Apple Music target (-16 LUFS)


def load_audio_for_loudness(audio_path: Path) -> Tuple[np.ndarray, int]:
    """
    Load audio file for loudness analysis.

    Returns:
        Tuple of (audio_data, sample_rate)
    """
    try:
        import librosa
    except ImportError:
        raise ImportError(
            "librosa is required for audio loading. "
            "Install with: pip install librosa"
        )

    # Load with librosa (handles M4A via audioread)
    # Use sr=None to preserve original sample rate
    audio, sr = librosa.load(str(audio_path), sr=None, mono=False)

    # librosa returns (channels, samples) or (samples,) for mono
    # pyloudnorm expects (samples, channels) or (samples,)
    if audio.ndim == 2:
        audio = audio.T  # Transpose to (samples, channels)

    return audio, sr


def extract_loudness(audio_path: Path) -> Optional[LoudnessFeatures]:
    """
    Extract loudness features from an audio file.

    Args:
        audio_path: Path to audio file

    Returns:
        LoudnessFeatures or None on error
    """
    try:
        import pyloudnorm as pyln
    except ImportError:
        raise ImportError(
            "pyloudnorm is required for loudness analysis. "
            "Install with: pip install pyloudnorm"
        )

    audio_path = Path(audio_path)
    if not audio_path.exists():
        return None

    try:
        # Load audio
        audio, sr = load_audio_for_loudness(audio_path)

        # Create meter
        meter = pyln.Meter(sr)

        # Integrated loudness (full track)
        integrated_lufs = meter.integrated_loudness(audio)

        # Calculate short-term loudness (3 second windows)
        short_term_loudness = calculate_short_term_loudness(audio, sr)

        # Calculate momentary loudness (400ms windows)
        momentary_loudness = calculate_momentary_loudness(audio, sr)

        # Filter out silence (-70 LUFS threshold)
        valid_short_term = [l for l in short_term_loudness if l > -70]
        valid_momentary = [l for l in momentary_loudness if l > -70]

        # Short-term stats
        short_term_max = max(valid_short_term) if valid_short_term else -70.0
        short_term_min = min(valid_short_term) if valid_short_term else -70.0

        # Momentary stats
        momentary_max = max(valid_momentary) if valid_momentary else -70.0

        # Loudness Range (LRA) - simplified calculation
        # LRA is the difference between 10th and 95th percentile of short-term loudness
        if len(valid_short_term) > 10:
            sorted_st = sorted(valid_short_term)
            p10_idx = int(len(sorted_st) * 0.10)
            p95_idx = int(len(sorted_st) * 0.95)
            loudness_range = sorted_st[p95_idx] - sorted_st[p10_idx]
        else:
            loudness_range = short_term_max - short_term_min

        # True peak measurement
        true_peak = calculate_true_peak(audio, sr)

        # Dynamic range (simple peak-to-average ratio)
        dynamic_range = momentary_max - integrated_lufs

        # Streaming platform gain calculations
        spotify_target = -14.0
        youtube_target = -14.0
        apple_target = -16.0

        return LoudnessFeatures(
            integrated_lufs=round(integrated_lufs, 1),
            loudness_range_lu=round(loudness_range, 1),
            true_peak_dbtp=round(true_peak, 1),
            short_term_max_lufs=round(short_term_max, 1),
            short_term_min_lufs=round(short_term_min, 1),
            momentary_max_lufs=round(momentary_max, 1),
            dynamic_range_db=round(dynamic_range, 1),
            spotify_gain_db=round(spotify_target - integrated_lufs, 1),
            youtube_gain_db=round(youtube_target - integrated_lufs, 1),
            apple_gain_db=round(apple_target - integrated_lufs, 1)
        )

    except Exception as e:
        print(f"Error extracting loudness: {e}")
        return None


def calculate_short_term_loudness(
    audio: np.ndarray,
    sr: int,
    window_sec: float = 3.0,
    hop_sec: float = 1.0
) -> List[float]:
    """
    Calculate short-term loudness over time.

    Args:
        audio: Audio data
        sr: Sample rate
        window_sec: Window size in seconds (EBU R128 = 3s)
        hop_sec: Hop size in seconds

    Returns:
        List of loudness values
    """
    try:
        import pyloudnorm as pyln
    except ImportError:
        return []

    meter = pyln.Meter(sr)

    window_samples = int(window_sec * sr)
    hop_samples = int(hop_sec * sr)

    loudness_values = []

    for i in range(0, len(audio) - window_samples, hop_samples):
        segment = audio[i:i + window_samples]
        try:
            lufs = meter.integrated_loudness(segment)
            loudness_values.append(lufs)
        except Exception:
            loudness_values.append(-70.0)  # Below threshold

    return loudness_values


def calculate_momentary_loudness(
    audio: np.ndarray,
    sr: int,
    window_sec: float = 0.4,
    hop_sec: float = 0.1
) -> List[float]:
    """
    Calculate momentary loudness over time.

    Args:
        audio: Audio data
        sr: Sample rate
        window_sec: Window size in seconds (EBU R128 = 400ms)
        hop_sec: Hop size in seconds

    Returns:
        List of loudness values
    """
    try:
        import pyloudnorm as pyln
    except ImportError:
        return []

    meter = pyln.Meter(sr)

    window_samples = int(window_sec * sr)
    hop_samples = int(hop_sec * sr)

    loudness_values = []

    for i in range(0, len(audio) - window_samples, hop_samples):
        segment = audio[i:i + window_samples]
        try:
            lufs = meter.integrated_loudness(segment)
            loudness_values.append(lufs)
        except Exception:
            loudness_values.append(-70.0)

    return loudness_values


def calculate_true_peak(audio: np.ndarray, sr: int) -> float:
    """
    Calculate true peak level in dBTP.

    True peak accounts for inter-sample peaks that may occur
    during D/A conversion.

    Args:
        audio: Audio data
        sr: Sample rate

    Returns:
        True peak in dBTP
    """
    # Upsample by 4x for true peak detection
    try:
        from scipy import signal
    except ImportError:
        # Fallback to sample peak if scipy not available
        peak = np.max(np.abs(audio))
        return 20 * np.log10(peak) if peak > 0 else -100.0

    # Upsample
    upsampled = signal.resample(audio, len(audio) * 4)

    # Find peak
    peak = np.max(np.abs(upsampled))

    # Convert to dB
    if peak > 0:
        return 20 * np.log10(peak)
    else:
        return -100.0


def get_loudness_over_time(
    audio_path: Path,
    resolution_sec: float = 1.0
) -> List[Tuple[float, float]]:
    """
    Get loudness curve over time.

    Useful for visualizing loudness changes throughout the track.

    Args:
        audio_path: Path to audio file
        resolution_sec: Time resolution in seconds

    Returns:
        List of (timestamp, lufs) tuples
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        return []

    try:
        audio, sr = load_audio_for_loudness(audio_path)
        short_term = calculate_short_term_loudness(
            audio, sr,
            window_sec=3.0,
            hop_sec=resolution_sec
        )

        return [
            (round(i * resolution_sec, 2), round(lufs, 1))
            for i, lufs in enumerate(short_term)
        ]
    except Exception:
        return []


def format_loudness_display(loudness: LoudnessFeatures) -> str:
    """
    Format loudness features for display.

    Args:
        loudness: Extracted loudness features

    Returns:
        Formatted string
    """
    lines = [
        f"Integrated: {loudness.integrated_lufs} LUFS",
        f"True Peak: {loudness.true_peak_dbtp} dBTP",
        f"LRA: {loudness.loudness_range_lu} LU",
        f"Dynamic Range: {loudness.dynamic_range_db} dB",
    ]

    # Add streaming recommendations
    if loudness.spotify_gain_db > 0:
        lines.append(f"Note: Track is {abs(loudness.spotify_gain_db)} dB quieter than Spotify target")
    elif loudness.spotify_gain_db < -1:
        lines.append(f"Note: Spotify will reduce by {abs(loudness.spotify_gain_db)} dB")

    return "\n".join(lines)
