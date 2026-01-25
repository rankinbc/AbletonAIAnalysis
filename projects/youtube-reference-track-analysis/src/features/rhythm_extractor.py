"""
Rhythm and BPM extraction using librosa.

Uses librosa.beat.beat_track for BPM detection,
which works well for electronic/trance music.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple
import numpy as np


@dataclass
class RhythmFeatures:
    """Extracted rhythm features."""
    bpm: float
    bpm_confidence: float
    beats: List[float]  # Beat timestamps in seconds
    beat_loudness: List[float]  # Loudness at each beat
    danceability: float
    beats_count: int


def extract_rhythm(audio_path: Path) -> Optional[RhythmFeatures]:
    """
    Extract rhythm features from an audio file using librosa.

    Args:
        audio_path: Path to audio file

    Returns:
        RhythmFeatures or None on error
    """
    try:
        import librosa
    except ImportError:
        raise ImportError(
            "librosa is required for rhythm extraction. "
            "Install with: pip install librosa"
        )

    audio_path = Path(audio_path)
    if not audio_path.exists():
        return None

    try:
        # Load audio (mono, 22050 Hz default for librosa)
        y, sr = librosa.load(str(audio_path), sr=22050, mono=True)

        # Get tempo and beat frames
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)

        # Convert tempo to scalar if needed (newer librosa returns array)
        if hasattr(tempo, '__len__'):
            bpm = float(tempo[0]) if len(tempo) > 0 else 120.0
        else:
            bpm = float(tempo)

        # Convert beat frames to timestamps
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)

        # Calculate beat loudness (RMS energy at each beat)
        beat_loudness = []
        hop_length = 512
        if len(beat_frames) > 0:
            # Get RMS energy
            rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
            for frame in beat_frames:
                if frame < len(rms):
                    beat_loudness.append(float(rms[frame]))
                else:
                    beat_loudness.append(0.0)

        # Estimate confidence from beat consistency
        if len(beat_times) > 2:
            intervals = np.diff(beat_times)
            expected_interval = 60.0 / bpm
            # Confidence based on how consistent intervals are
            deviations = np.abs(intervals - expected_interval) / expected_interval
            confidence = max(0.0, 1.0 - np.mean(deviations))
        else:
            confidence = 0.5

        # Estimate danceability from rhythm regularity and tempo
        # Higher for stable rhythms in dance music tempo range (120-150 BPM)
        tempo_factor = 1.0 - abs(bpm - 135) / 100  # Peak at 135 BPM
        tempo_factor = max(0.0, min(1.0, tempo_factor))
        danceability = confidence * 0.7 + tempo_factor * 0.3

        return RhythmFeatures(
            bpm=round(bpm, 2),
            bpm_confidence=round(confidence, 3),
            beats=beat_times.tolist(),
            beat_loudness=beat_loudness,
            danceability=round(danceability, 3),
            beats_count=len(beat_times)
        )

    except Exception as e:
        print(f"Error extracting rhythm: {e}")
        return None


def detect_tempo_changes(
    beats: List[float],
    window_size: int = 16
) -> List[Tuple[float, float]]:
    """
    Detect tempo changes throughout the track.

    Args:
        beats: List of beat timestamps
        window_size: Number of beats per window for local BPM calculation

    Returns:
        List of (timestamp, local_bpm) tuples
    """
    if len(beats) < window_size * 2:
        return []

    tempo_changes = []

    for i in range(0, len(beats) - window_size, window_size // 2):
        window_beats = beats[i:i + window_size]
        if len(window_beats) >= 2:
            # Calculate local BPM from beat intervals
            intervals = np.diff(window_beats)
            avg_interval = np.mean(intervals)
            local_bpm = 60.0 / avg_interval if avg_interval > 0 else 0

            timestamp = window_beats[0]
            tempo_changes.append((timestamp, round(local_bpm, 2)))

    return tempo_changes


def get_downbeats(
    beats: List[float],
    bpm: float,
    beats_per_bar: int = 4
) -> List[float]:
    """
    Estimate downbeat positions (first beat of each bar).

    This is a simple estimation based on grouping beats.
    For more accurate downbeat detection, use madmom.

    Args:
        beats: List of beat timestamps
        bpm: Track BPM
        beats_per_bar: Number of beats per bar (typically 4 for trance)

    Returns:
        List of estimated downbeat timestamps
    """
    if len(beats) < beats_per_bar:
        return []

    # Simple approach: every Nth beat is a downbeat
    # This is a rough estimation - madmom is more accurate
    downbeats = beats[::beats_per_bar]

    return downbeats


def calculate_groove_stability(beats: List[float]) -> float:
    """
    Calculate how stable/consistent the groove is.

    A stable groove has consistent beat intervals.
    Returns a value between 0 (unstable) and 1 (very stable).

    Args:
        beats: List of beat timestamps

    Returns:
        Stability score (0-1)
    """
    if len(beats) < 3:
        return 0.0

    intervals = np.diff(beats)

    if len(intervals) == 0:
        return 0.0

    # Calculate coefficient of variation (lower = more stable)
    mean_interval = np.mean(intervals)
    std_interval = np.std(intervals)

    if mean_interval == 0:
        return 0.0

    cv = std_interval / mean_interval

    # Convert to stability score (invert and normalize)
    # CV of 0 = stability of 1.0
    # CV of 0.1 = stability of ~0.9
    # CV of 0.5 = stability of ~0.5
    stability = 1.0 / (1.0 + cv * 5)

    return round(stability, 3)
