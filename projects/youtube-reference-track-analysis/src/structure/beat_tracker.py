"""
Enhanced beat tracking with downbeat detection.

Uses librosa for beat tracking and provides utilities for
downbeat estimation and time signature detection.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple
import numpy as np


@dataclass
class BeatInfo:
    """Beat tracking information."""
    bpm: float  # Estimated BPM
    beats: List[float]  # All beat timestamps in seconds
    downbeats: List[float]  # Downbeat (bar start) timestamps
    time_signature: int  # Beats per bar (typically 4)
    beat_confidence: float  # Overall beat tracking confidence
    first_downbeat: float  # Timestamp of first downbeat


def track_beats(
    audio_path: Path,
    bpm_hint: Optional[float] = None
) -> Optional[BeatInfo]:
    """
    Track beats in an audio file using librosa.

    Args:
        audio_path: Path to audio file
        bpm_hint: Optional BPM hint to improve accuracy

    Returns:
        BeatInfo or None on error
    """
    try:
        import librosa
    except ImportError:
        raise ImportError(
            "librosa is required for beat tracking. "
            "Install with: pip install librosa"
        )

    audio_path = Path(audio_path)
    if not audio_path.exists():
        return None

    try:
        # Load audio
        y, sr = librosa.load(str(audio_path), sr=22050, mono=True)

        # Set tempo prior if hint provided
        prior = None
        if bpm_hint and 60 < bpm_hint < 200:
            # Create a prior distribution favoring the hint
            prior = librosa.beat.tempo(y=y, sr=sr, prior=librosa.beat.tempo(
                y=y, sr=sr, start_bpm=bpm_hint
            ))

        # Get tempo and beat frames
        if bpm_hint:
            tempo, beat_frames = librosa.beat.beat_track(
                y=y, sr=sr, start_bpm=bpm_hint
            )
        else:
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)

        # Handle tempo array (newer librosa versions)
        if hasattr(tempo, '__len__'):
            bpm = float(tempo[0]) if len(tempo) > 0 else 120.0
        else:
            bpm = float(tempo)

        # Convert beat frames to timestamps
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        beats = beat_times.tolist()

        # Estimate time signature (default 4/4 for trance)
        time_signature = estimate_time_signature(beats)

        # Estimate downbeats
        downbeats = estimate_downbeats(beats, bpm, time_signature)

        # Calculate confidence from beat consistency
        confidence = calculate_beat_confidence(beats, bpm)

        # First downbeat
        first_downbeat = downbeats[0] if downbeats else (beats[0] if beats else 0.0)

        return BeatInfo(
            bpm=round(bpm, 2),
            beats=beats,
            downbeats=downbeats,
            time_signature=time_signature,
            beat_confidence=round(confidence, 3),
            first_downbeat=round(first_downbeat, 3)
        )

    except Exception as e:
        print(f"Error tracking beats: {e}")
        return None


def estimate_time_signature(beats: List[float]) -> int:
    """
    Estimate time signature from beat intervals.

    For trance music, this is almost always 4/4.

    Args:
        beats: List of beat timestamps

    Returns:
        Beats per bar (typically 4)
    """
    # For trance, we assume 4/4 time
    # More sophisticated analysis could use onset patterns
    # or autocorrelation to detect other signatures
    return 4


def estimate_downbeats(
    beats: List[float],
    bpm: float,
    time_signature: int = 4
) -> List[float]:
    """
    Estimate downbeat positions from beats.

    This is a heuristic approach - for more accurate results,
    consider using madmom's DBNDownBeatTrackingProcessor.

    Args:
        beats: List of beat timestamps
        bpm: Track BPM
        time_signature: Beats per bar

    Returns:
        List of downbeat timestamps
    """
    if not beats or len(beats) < time_signature:
        return []

    # Simple approach: every Nth beat is a downbeat
    # This assumes the first beat is a downbeat, which isn't always true

    # Try to find a better starting point by looking for strong beats
    try:
        import librosa
        # Look at beat strength pattern - downbeats tend to be stronger
        # For now, use simple heuristic
    except ImportError:
        pass

    # Simple downbeat estimation
    downbeats = beats[::time_signature]

    return downbeats


def estimate_downbeats_with_energy(
    audio_path: Path,
    beats: List[float],
    time_signature: int = 4
) -> List[float]:
    """
    Estimate downbeats using energy analysis.

    More accurate than simple grouping by detecting
    which beats have higher energy (likely downbeats).

    Args:
        audio_path: Path to audio file
        beats: List of beat timestamps
        time_signature: Beats per bar

    Returns:
        List of downbeat timestamps
    """
    if not beats or len(beats) < time_signature:
        return []

    try:
        import librosa
    except ImportError:
        return beats[::time_signature]

    try:
        # Load audio
        y, sr = librosa.load(str(audio_path), sr=22050, mono=True)

        # Get energy at each beat
        beat_energies = []
        window_samples = int(0.1 * sr)  # 100ms window around each beat

        for beat_time in beats:
            center_sample = int(beat_time * sr)
            start = max(0, center_sample - window_samples // 2)
            end = min(len(y), center_sample + window_samples // 2)
            segment = y[start:end]
            energy = np.sqrt(np.mean(segment ** 2)) if len(segment) > 0 else 0
            beat_energies.append(energy)

        # Find the phase offset that maximizes downbeat energy
        best_offset = 0
        best_energy_sum = 0

        for offset in range(time_signature):
            downbeat_indices = range(offset, len(beats), time_signature)
            energy_sum = sum(beat_energies[i] for i in downbeat_indices if i < len(beat_energies))
            if energy_sum > best_energy_sum:
                best_energy_sum = energy_sum
                best_offset = offset

        # Return downbeats with optimal offset
        downbeats = [beats[i] for i in range(best_offset, len(beats), time_signature)]

        return downbeats

    except Exception:
        return beats[::time_signature]


def calculate_beat_confidence(beats: List[float], bpm: float) -> float:
    """
    Calculate confidence score for beat tracking.

    Based on how consistent the beat intervals are.

    Args:
        beats: List of beat timestamps
        bpm: Estimated BPM

    Returns:
        Confidence score (0-1)
    """
    if len(beats) < 3:
        return 0.5

    intervals = np.diff(beats)
    expected_interval = 60.0 / bpm

    # Calculate deviation from expected
    deviations = np.abs(intervals - expected_interval) / expected_interval
    mean_deviation = np.mean(deviations)

    # Convert to confidence (lower deviation = higher confidence)
    confidence = max(0.0, 1.0 - mean_deviation)

    return confidence


def get_beats_in_range(
    beats: List[float],
    start_time: float,
    end_time: float
) -> List[float]:
    """
    Get beats within a time range.

    Args:
        beats: List of all beat timestamps
        start_time: Start of range
        end_time: End of range

    Returns:
        List of beats in range
    """
    return [b for b in beats if start_time <= b < end_time]


def count_bars_in_range(
    downbeats: List[float],
    start_time: float,
    end_time: float
) -> int:
    """
    Count number of bars in a time range.

    Args:
        downbeats: List of downbeat timestamps
        start_time: Start of range
        end_time: End of range

    Returns:
        Number of bars
    """
    bars_in_range = [d for d in downbeats if start_time <= d < end_time]
    return len(bars_in_range)


def format_beat_info_display(beat_info: BeatInfo) -> str:
    """
    Format beat info for display.

    Args:
        beat_info: Beat tracking information

    Returns:
        Formatted string
    """
    lines = [
        f"BPM: {beat_info.bpm}",
        f"Time Signature: {beat_info.time_signature}/4",
        f"Total Beats: {len(beat_info.beats)}",
        f"Total Bars: {len(beat_info.downbeats)}",
        f"Beat Confidence: {beat_info.beat_confidence:.1%}",
        f"First Downbeat: {beat_info.first_downbeat:.2f}s",
    ]

    # Duration
    if beat_info.beats:
        duration = beat_info.beats[-1]
        mins = int(duration // 60)
        secs = int(duration % 60)
        lines.append(f"Duration: {mins}:{secs:02d}")

    return "\n".join(lines)
