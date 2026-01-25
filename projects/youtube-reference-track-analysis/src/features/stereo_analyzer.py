"""
Stereo field analysis for width and imaging characteristics.

Analyzes the stereo image of a track including width, correlation,
and balance. Important for understanding how "wide" or "mono-compatible"
a mix is.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple
import numpy as np


@dataclass
class StereoFeatures:
    """Extracted stereo features."""
    # Overall stereo characteristics
    stereo_width: float  # 0-100, 0=mono, 100=full stereo
    correlation: float  # -1 to +1, higher = more mono-compatible
    balance: float  # -1 (left) to +1 (right), 0 = centered

    # Mid/Side analysis
    mid_energy_pct: float  # Percentage of energy in mid (center)
    side_energy_pct: float  # Percentage of energy in sides

    # Frequency-dependent width (percentage of side energy per band)
    low_width: float  # 20-250 Hz width score (should be narrow for trance)
    mid_width: float  # 250-2000 Hz width score
    high_width: float  # 2000+ Hz width score

    # Mono compatibility
    mono_compatible: bool  # True if correlation > 0.5
    phase_issues: bool  # True if significant phase cancellation detected


def load_stereo_audio(audio_path: Path) -> Tuple[np.ndarray, int]:
    """
    Load audio file as stereo.

    Args:
        audio_path: Path to audio file

    Returns:
        Tuple of (stereo_audio, sample_rate)
        stereo_audio shape: (2, samples) for stereo, (1, samples) for mono
    """
    try:
        import librosa
    except ImportError:
        raise ImportError(
            "librosa is required for audio loading. "
            "Install with: pip install librosa"
        )

    # Load with librosa (handles M4A via audioread)
    # mono=False to preserve stereo
    audio, sr = librosa.load(str(audio_path), sr=None, mono=False)

    # librosa returns (channels, samples) for stereo, (samples,) for mono
    if audio.ndim == 1:
        # Mono file - duplicate to stereo
        audio = np.stack([audio, audio])

    return audio, sr


def extract_stereo_features(audio_path: Path) -> Optional[StereoFeatures]:
    """
    Extract stereo field features from an audio file.

    Args:
        audio_path: Path to audio file

    Returns:
        StereoFeatures or None on error
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        return None

    try:
        audio, sr = load_stereo_audio(audio_path)

        if audio.shape[0] < 2:
            # Mono file - return mono characteristics
            return StereoFeatures(
                stereo_width=0.0,
                correlation=1.0,
                balance=0.0,
                mid_energy_pct=100.0,
                side_energy_pct=0.0,
                low_width=0.0,
                mid_width=0.0,
                high_width=0.0,
                mono_compatible=True,
                phase_issues=False
            )

        left = audio[0]
        right = audio[1]

        # Calculate Mid/Side
        mid = (left + right) / 2.0
        side = (left - right) / 2.0

        # Stereo correlation (Pearson correlation coefficient)
        correlation = calculate_correlation(left, right)

        # Balance (pan position)
        balance = calculate_balance(left, right)

        # Energy distribution
        mid_energy = np.sum(mid ** 2)
        side_energy = np.sum(side ** 2)
        total_energy = mid_energy + side_energy

        if total_energy > 0:
            mid_energy_pct = (mid_energy / total_energy) * 100
            side_energy_pct = (side_energy / total_energy) * 100
        else:
            mid_energy_pct = 100.0
            side_energy_pct = 0.0

        # Stereo width (based on side energy ratio)
        # More side energy = wider stereo image
        stereo_width = min(100.0, side_energy_pct * 2.0)

        # Frequency-dependent width
        low_width, mid_width, high_width = calculate_frequency_dependent_width(
            left, right, sr
        )

        # Mono compatibility check
        mono_compatible = correlation > 0.5

        # Phase issues detection (significant anti-correlation)
        phase_issues = correlation < 0.0

        return StereoFeatures(
            stereo_width=round(stereo_width, 1),
            correlation=round(correlation, 3),
            balance=round(balance, 3),
            mid_energy_pct=round(mid_energy_pct, 1),
            side_energy_pct=round(side_energy_pct, 1),
            low_width=round(low_width, 1),
            mid_width=round(mid_width, 1),
            high_width=round(high_width, 1),
            mono_compatible=mono_compatible,
            phase_issues=phase_issues
        )

    except Exception as e:
        print(f"Error extracting stereo features: {e}")
        return None


def calculate_correlation(left: np.ndarray, right: np.ndarray) -> float:
    """
    Calculate stereo correlation coefficient.

    +1 = perfectly correlated (mono)
    0 = uncorrelated
    -1 = perfectly anti-correlated (out of phase)

    Args:
        left: Left channel samples
        right: Right channel samples

    Returns:
        Correlation coefficient
    """
    # Remove DC offset
    left = left - np.mean(left)
    right = right - np.mean(right)

    # Calculate correlation
    numerator = np.sum(left * right)
    denominator = np.sqrt(np.sum(left ** 2) * np.sum(right ** 2))

    if denominator == 0:
        return 1.0

    return numerator / denominator


def calculate_balance(left: np.ndarray, right: np.ndarray) -> float:
    """
    Calculate stereo balance.

    -1 = fully left
    0 = centered
    +1 = fully right

    Args:
        left: Left channel samples
        right: Right channel samples

    Returns:
        Balance value
    """
    left_energy = np.sum(left ** 2)
    right_energy = np.sum(right ** 2)
    total_energy = left_energy + right_energy

    if total_energy == 0:
        return 0.0

    # Calculate balance (-1 to +1)
    balance = (right_energy - left_energy) / total_energy

    return balance


def calculate_frequency_dependent_width(
    left: np.ndarray,
    right: np.ndarray,
    sr: int
) -> Tuple[float, float, float]:
    """
    Calculate stereo width in different frequency bands.

    Args:
        left: Left channel samples
        right: Right channel samples
        sr: Sample rate

    Returns:
        Tuple of (low_width, mid_width, high_width) as 0-100 scores
    """
    try:
        from scipy import signal
    except ImportError:
        # Return default values if scipy not available
        return (0.0, 50.0, 50.0)

    def bandpass_filter(data, lowcut, highcut, sr, order=4):
        nyq = 0.5 * sr
        low = max(lowcut / nyq, 0.001)
        high = min(highcut / nyq, 0.999)
        if low >= high:
            return data
        b, a = signal.butter(order, [low, high], btype='band')
        return signal.filtfilt(b, a, data)

    # Define frequency bands
    bands = [
        (20, 250),    # Low
        (250, 2000),  # Mid
        (2000, min(20000, sr // 2 - 100))  # High
    ]

    widths = []

    for low_freq, high_freq in bands:
        try:
            # Filter both channels
            left_band = bandpass_filter(left, low_freq, high_freq, sr)
            right_band = bandpass_filter(right, low_freq, high_freq, sr)

            # Calculate side energy for this band
            mid = (left_band + right_band) / 2.0
            side = (left_band - right_band) / 2.0

            mid_energy = np.sum(mid ** 2)
            side_energy = np.sum(side ** 2)
            total = mid_energy + side_energy

            if total > 0:
                side_ratio = side_energy / total
                width = min(100.0, side_ratio * 200.0)
            else:
                width = 0.0

            widths.append(width)
        except Exception:
            widths.append(0.0)

    return tuple(widths)


def get_stereo_over_time(
    audio_path: Path,
    segment_duration: float = 5.0
) -> List[Tuple[float, float, float]]:
    """
    Get stereo width and correlation over time.

    Useful for seeing how the stereo image evolves (e.g., breakdown
    sections often have wider stereo than drops).

    Args:
        audio_path: Path to audio file
        segment_duration: Segment duration in seconds

    Returns:
        List of (timestamp, width, correlation) tuples
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        return []

    try:
        audio, sr = load_stereo_audio(audio_path)

        if audio.shape[0] < 2:
            return []

        left = audio[0]
        right = audio[1]

        segment_samples = int(segment_duration * sr)
        results = []

        for i in range(0, len(left) - segment_samples, segment_samples):
            left_seg = left[i:i + segment_samples]
            right_seg = right[i:i + segment_samples]

            # Calculate segment metrics
            correlation = calculate_correlation(left_seg, right_seg)

            mid = (left_seg + right_seg) / 2.0
            side = (left_seg - right_seg) / 2.0
            mid_e = np.sum(mid ** 2)
            side_e = np.sum(side ** 2)
            total_e = mid_e + side_e

            if total_e > 0:
                width = min(100.0, (side_e / total_e) * 200.0)
            else:
                width = 0.0

            timestamp = i / sr
            results.append((
                round(timestamp, 1),
                round(width, 1),
                round(correlation, 3)
            ))

        return results

    except Exception:
        return []


def format_stereo_display(stereo: StereoFeatures) -> str:
    """
    Format stereo features for display.

    Args:
        stereo: Extracted stereo features

    Returns:
        Formatted string
    """
    width_desc = "Mono" if stereo.stereo_width < 10 else \
                "Narrow" if stereo.stereo_width < 30 else \
                "Moderate" if stereo.stereo_width < 60 else \
                "Wide" if stereo.stereo_width < 80 else \
                "Very Wide"

    balance_desc = "Centered" if abs(stereo.balance) < 0.05 else \
                  f"{'Left' if stereo.balance < 0 else 'Right'} ({abs(stereo.balance):.1%})"

    lines = [
        f"Stereo Width: {stereo.stereo_width}/100 ({width_desc})",
        f"Correlation: {stereo.correlation:.3f}",
        f"Balance: {balance_desc}",
        "",
        "Mid/Side Distribution:",
        f"  Mid (Center): {stereo.mid_energy_pct:.1f}%",
        f"  Side (Stereo): {stereo.side_energy_pct:.1f}%",
        "",
        "Width by Frequency:",
        f"  Low (20-250 Hz): {stereo.low_width:.0f}/100",
        f"  Mid (250-2k Hz): {stereo.mid_width:.0f}/100",
        f"  High (2k+ Hz): {stereo.high_width:.0f}/100",
    ]

    # Add warnings
    if stereo.phase_issues:
        lines.append("")
        lines.append("WARNING: Phase issues detected (negative correlation)")

    if not stereo.mono_compatible:
        lines.append("")
        lines.append("NOTE: May lose content when summed to mono")

    if stereo.low_width > 30:
        lines.append("")
        lines.append("NOTE: Bass may be too wide for club systems")

    return "\n".join(lines)
