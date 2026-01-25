"""
Musical key detection using librosa.

Uses chroma features and the Krumhansl-Schmuckler key-finding algorithm.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple
import numpy as np


@dataclass
class KeyFeatures:
    """Extracted key features."""
    key: str  # e.g., "A", "Bb", "F#"
    scale: str  # "major" or "minor"
    key_confidence: float  # 0.0 to 1.0
    camelot: str  # Camelot notation (e.g., "8A", "11B")
    open_key: str  # Open Key notation
    # Alternative key estimations
    secondary_key: Optional[str] = None
    secondary_scale: Optional[str] = None
    secondary_confidence: Optional[float] = None


# Camelot wheel mapping
CAMELOT_MAJOR = {
    'B': '1B', 'F#': '2B', 'Db': '3B', 'Ab': '4B', 'Eb': '5B', 'Bb': '6B',
    'F': '7B', 'C': '8B', 'G': '9B', 'D': '10B', 'A': '11B', 'E': '12B',
    # Enharmonic equivalents
    'Gb': '2B', 'C#': '3B', 'G#': '4B', 'D#': '5B', 'A#': '6B'
}

CAMELOT_MINOR = {
    'G#': '1A', 'D#': '2A', 'Bb': '3A', 'F': '4A', 'C': '5A', 'G': '6A',
    'D': '7A', 'A': '8A', 'E': '9A', 'B': '10A', 'F#': '11A', 'C#': '12A',
    # Enharmonic equivalents
    'Ab': '1A', 'Eb': '2A', 'A#': '3A', 'Gb': '11A', 'Db': '12A'
}

# Open Key notation mapping (same numeric but different letter convention)
OPEN_KEY_MAJOR = {
    'C': '1d', 'G': '2d', 'D': '3d', 'A': '4d', 'E': '5d', 'B': '6d',
    'Gb': '7d', 'Db': '8d', 'Ab': '9d', 'Eb': '10d', 'Bb': '11d', 'F': '12d',
    'F#': '7d', 'C#': '8d', 'G#': '9d', 'D#': '10d', 'A#': '11d'
}

OPEN_KEY_MINOR = {
    'A': '1m', 'E': '2m', 'B': '3m', 'F#': '4m', 'C#': '5m', 'G#': '6m',
    'Eb': '7m', 'Bb': '8m', 'F': '9m', 'C': '10m', 'G': '11m', 'D': '12m',
    'Gb': '4m', 'Db': '5m', 'Ab': '6m', 'D#': '7m', 'A#': '8m'
}

# Key profiles for Krumhansl-Schmuckler algorithm
# Major key profile
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
# Minor key profile
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# Note names
NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def key_to_camelot(key: str, scale: str) -> str:
    """
    Convert key and scale to Camelot notation.

    Args:
        key: Musical key (e.g., "A", "Bb", "F#")
        scale: "major" or "minor"

    Returns:
        Camelot notation (e.g., "8A", "11B")
    """
    if scale == "minor":
        return CAMELOT_MINOR.get(key, "?")
    else:
        return CAMELOT_MAJOR.get(key, "?")


def key_to_open_key(key: str, scale: str) -> str:
    """
    Convert key and scale to Open Key notation.

    Args:
        key: Musical key
        scale: "major" or "minor"

    Returns:
        Open Key notation (e.g., "1m", "4d")
    """
    if scale == "minor":
        return OPEN_KEY_MINOR.get(key, "?")
    else:
        return OPEN_KEY_MAJOR.get(key, "?")


def get_compatible_keys(camelot: str) -> List[str]:
    """
    Get Camelot keys that are harmonically compatible.

    Returns keys that can be mixed together smoothly:
    - Same key
    - +/- 1 on the wheel (adjacent keys)
    - Relative major/minor (same number, different letter)

    Args:
        camelot: Camelot notation (e.g., "8A")

    Returns:
        List of compatible Camelot keys
    """
    if len(camelot) < 2 or camelot == "?":
        return []

    try:
        number = int(camelot[:-1])
        letter = camelot[-1].upper()
    except ValueError:
        return []

    compatible = []

    # Same key
    compatible.append(camelot)

    # Relative major/minor
    other_letter = 'B' if letter == 'A' else 'A'
    compatible.append(f"{number}{other_letter}")

    # Adjacent keys (same mode)
    prev_num = 12 if number == 1 else number - 1
    next_num = 1 if number == 12 else number + 1
    compatible.append(f"{prev_num}{letter}")
    compatible.append(f"{next_num}{letter}")

    return compatible


def extract_key(audio_path: Path, use_edma: bool = True) -> Optional[KeyFeatures]:
    """
    Extract musical key from an audio file using librosa.

    Args:
        audio_path: Path to audio file
        use_edma: Ignored (kept for compatibility)

    Returns:
        KeyFeatures or None on error
    """
    try:
        import librosa
    except ImportError:
        raise ImportError(
            "librosa is required for key extraction. "
            "Install with: pip install librosa"
        )

    audio_path = Path(audio_path)
    if not audio_path.exists():
        return None

    try:
        # Load audio
        y, sr = librosa.load(str(audio_path), sr=22050, mono=True)

        # Extract chroma features
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

        # Average chroma over time
        chroma_avg = np.mean(chroma, axis=1)

        # Normalize
        chroma_avg = chroma_avg / np.sum(chroma_avg)

        # Find best key using Krumhansl-Schmuckler algorithm
        best_key = None
        best_scale = None
        best_correlation = -1
        all_correlations = []

        for i in range(12):
            # Rotate chroma to start from this key
            rotated = np.roll(chroma_avg, -i)

            # Correlate with major profile
            major_corr = np.corrcoef(rotated, MAJOR_PROFILE)[0, 1]
            all_correlations.append((NOTE_NAMES[i], 'major', major_corr))

            if major_corr > best_correlation:
                best_correlation = major_corr
                best_key = NOTE_NAMES[i]
                best_scale = 'major'

            # Correlate with minor profile
            minor_corr = np.corrcoef(rotated, MINOR_PROFILE)[0, 1]
            all_correlations.append((NOTE_NAMES[i], 'minor', minor_corr))

            if minor_corr > best_correlation:
                best_correlation = minor_corr
                best_key = NOTE_NAMES[i]
                best_scale = 'minor'

        # Sort to find second best
        all_correlations.sort(key=lambda x: x[2], reverse=True)
        second_best = all_correlations[1] if len(all_correlations) > 1 else None

        # Calculate confidence (normalized correlation)
        confidence = max(0.0, min(1.0, (best_correlation + 1) / 2))

        # Convert to Camelot and Open Key
        camelot = key_to_camelot(best_key, best_scale)
        open_key = key_to_open_key(best_key, best_scale)

        # Secondary key if different from primary
        secondary_key = None
        secondary_scale = None
        secondary_confidence = None
        if second_best and (second_best[0] != best_key or second_best[1] != best_scale):
            secondary_key = second_best[0]
            secondary_scale = second_best[1]
            secondary_confidence = max(0.0, min(1.0, (second_best[2] + 1) / 2))

        return KeyFeatures(
            key=best_key,
            scale=best_scale,
            key_confidence=round(confidence, 3),
            camelot=camelot,
            open_key=open_key,
            secondary_key=secondary_key,
            secondary_scale=secondary_scale,
            secondary_confidence=round(secondary_confidence, 3) if secondary_confidence else None
        )

    except Exception as e:
        print(f"Error extracting key: {e}")
        return None


def extract_key_over_time(
    audio_path: Path,
    segment_duration: float = 30.0
) -> List[Tuple[float, str, str, float]]:
    """
    Extract key at different points in the track.

    Useful for detecting key changes or modulations.

    Args:
        audio_path: Path to audio file
        segment_duration: Duration of each segment in seconds

    Returns:
        List of (timestamp, key, scale, confidence) tuples
    """
    try:
        import librosa
    except ImportError:
        raise ImportError("librosa is required")

    audio_path = Path(audio_path)
    if not audio_path.exists():
        return []

    try:
        # Load full audio
        y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
        segment_samples = int(segment_duration * sr)

        results = []

        for i in range(0, len(y) - segment_samples, segment_samples):
            segment = y[i:i + segment_samples]

            # Extract chroma
            chroma = librosa.feature.chroma_cqt(y=segment, sr=sr)
            chroma_avg = np.mean(chroma, axis=1)
            chroma_avg = chroma_avg / np.sum(chroma_avg)

            best_key = None
            best_scale = None
            best_correlation = -1

            for j in range(12):
                rotated = np.roll(chroma_avg, -j)
                major_corr = np.corrcoef(rotated, MAJOR_PROFILE)[0, 1]
                if major_corr > best_correlation:
                    best_correlation = major_corr
                    best_key = NOTE_NAMES[j]
                    best_scale = 'major'
                minor_corr = np.corrcoef(rotated, MINOR_PROFILE)[0, 1]
                if minor_corr > best_correlation:
                    best_correlation = minor_corr
                    best_key = NOTE_NAMES[j]
                    best_scale = 'minor'

            confidence = max(0.0, min(1.0, (best_correlation + 1) / 2))
            timestamp = i / sr
            results.append((round(timestamp, 2), best_key, best_scale, round(confidence, 3)))

        return results

    except Exception as e:
        print(f"Error extracting key over time: {e}")
        return []


def format_key_display(key_features: KeyFeatures) -> str:
    """
    Format key features for display.

    Args:
        key_features: Extracted key features

    Returns:
        Formatted string like "Am (8A) [92%]"
    """
    key_str = f"{key_features.key}"
    if key_features.scale == "minor":
        key_str += "m"

    confidence_pct = int(key_features.key_confidence * 100)

    return f"{key_str} ({key_features.camelot}) [{confidence_pct}%]"
