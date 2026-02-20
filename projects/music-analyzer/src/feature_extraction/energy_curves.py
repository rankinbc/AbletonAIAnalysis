"""
Energy Curve Extraction Module.

Extracts energy progression features for structure analysis:
- Multi-feature energy tracking (RMS, centroid, onset density)
- Combined normalized energy curve
- Drop detection (energy > 2x after quiet section)
- Bass ratio tracking

Used to analyze breakdown/buildup/drop patterns typical in trance.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple, List
import librosa


@dataclass
class EnergyCurves:
    """Results from energy curve extraction."""
    energy_curve: np.ndarray  # Combined normalized energy (0-1)
    rms: np.ndarray  # Smoothed RMS envelope
    centroid: np.ndarray  # Smoothed spectral centroid
    onset_density: np.ndarray  # Smoothed onset strength
    bass_ratio: np.ndarray  # Low-frequency energy ratio
    times: np.ndarray  # Time axis in seconds

    # Summary statistics
    energy_range: float  # Max - min of energy curve
    energy_std: float  # Standard deviation
    avg_energy: float  # Mean energy level


@dataclass
class DropInfo:
    """Information about a detected drop."""
    time: float  # Timestamp in seconds
    energy_before: float  # Energy level before drop
    energy_after: float  # Energy level after drop
    ratio: float  # energy_after / energy_before
    pre_drop_duration: float  # Duration of quiet section before drop


def extract_energy_curves(
    audio_path_or_data,
    sr: Optional[int] = None,
    hop_length: int = 512,
    smooth_seconds: float = 4.0,
    bass_cutoff: float = 250.0
) -> EnergyCurves:
    """
    Extract energy progression features for structure analysis.

    Args:
        audio_path_or_data: Path to audio file or numpy array
        sr: Sample rate (required if array provided)
        hop_length: Hop length for feature extraction
        smooth_seconds: Smoothing window in seconds
        bass_cutoff: Frequency below which is considered bass (Hz)

    Returns:
        EnergyCurves with multi-feature energy tracking
    """
    # Load audio if path provided
    if isinstance(audio_path_or_data, str):
        y, sr = librosa.load(audio_path_or_data, sr=None, mono=True)
    else:
        y = audio_path_or_data
        if sr is None:
            raise ValueError("sr must be provided when passing audio array")
        if len(y.shape) > 1:
            y = np.mean(y, axis=0)

    # Calculate smoothing window in frames
    smooth_frames = int(smooth_seconds * sr / hop_length)
    if smooth_frames < 1:
        smooth_frames = 1

    # 1. RMS Envelope
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    rms_smooth = _smooth_signal(rms, smooth_frames)

    # 2. Spectral Centroid (brightness)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]
    centroid_smooth = _smooth_signal(centroid, smooth_frames)

    # 3. Onset Strength (rhythmic density)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    onset_smooth = _smooth_signal(onset_env, smooth_frames)

    # 4. Bass Ratio
    bass_ratio = _compute_bass_ratio(y, sr, hop_length, bass_cutoff)
    bass_smooth = _smooth_signal(bass_ratio, smooth_frames)

    # Ensure all arrays are same length
    min_len = min(len(rms_smooth), len(centroid_smooth), len(onset_smooth), len(bass_smooth))
    rms_smooth = rms_smooth[:min_len]
    centroid_smooth = centroid_smooth[:min_len]
    onset_smooth = onset_smooth[:min_len]
    bass_smooth = bass_smooth[:min_len]

    # 5. Combine into normalized energy curve
    energy_curve = _combine_energy_features(
        rms_smooth, centroid_smooth, onset_smooth, bass_smooth
    )

    # Time axis
    times = librosa.frames_to_time(
        np.arange(len(energy_curve)), sr=sr, hop_length=hop_length
    )

    # Summary statistics
    energy_range = float(np.max(energy_curve) - np.min(energy_curve))
    energy_std = float(np.std(energy_curve))
    avg_energy = float(np.mean(energy_curve))

    return EnergyCurves(
        energy_curve=energy_curve,
        rms=rms_smooth,
        centroid=centroid_smooth,
        onset_density=onset_smooth,
        bass_ratio=bass_smooth,
        times=times,
        energy_range=energy_range,
        energy_std=energy_std,
        avg_energy=avg_energy
    )


def _smooth_signal(signal: np.ndarray, window_size: int) -> np.ndarray:
    """Apply moving average smoothing."""
    if window_size <= 1:
        return signal
    kernel = np.ones(window_size) / window_size
    return np.convolve(signal, kernel, mode='same')


def _compute_bass_ratio(
    y: np.ndarray,
    sr: int,
    hop_length: int,
    bass_cutoff: float
) -> np.ndarray:
    """
    Compute ratio of bass energy to total energy over time.

    Returns:
        Array of bass ratios per frame (0-1)
    """
    # Compute STFT
    D = np.abs(librosa.stft(y, hop_length=hop_length))
    freqs = librosa.fft_frequencies(sr=sr)

    # Find bass frequency bins
    bass_bins = freqs < bass_cutoff

    # Compute energy in bass and total
    bass_energy = np.sum(D[bass_bins, :]**2, axis=0)
    total_energy = np.sum(D**2, axis=0) + 1e-10

    bass_ratio = bass_energy / total_energy

    return bass_ratio


def _combine_energy_features(
    rms: np.ndarray,
    centroid: np.ndarray,
    onset: np.ndarray,
    bass: np.ndarray
) -> np.ndarray:
    """
    Combine multiple features into single energy curve.

    Weights:
        RMS: 0.40 (primary energy indicator)
        Centroid: 0.25 (brightness correlates with intensity)
        Onset: 0.20 (rhythmic activity)
        Bass: 0.15 (low-end presence)
    """
    # Normalize each feature to 0-1
    rms_norm = _normalize_feature(rms)
    centroid_norm = _normalize_feature(centroid)
    onset_norm = _normalize_feature(onset)
    bass_norm = _normalize_feature(bass)

    # Weighted combination
    energy = (
        0.40 * rms_norm +
        0.25 * centroid_norm +
        0.20 * onset_norm +
        0.15 * bass_norm
    )

    return energy


def _normalize_feature(feature: np.ndarray) -> np.ndarray:
    """Normalize feature to 0-1 range."""
    min_val = np.min(feature)
    max_val = np.max(feature)

    if max_val - min_val < 1e-10:
        return np.zeros_like(feature)

    return (feature - min_val) / (max_val - min_val)


def detect_drops(
    energy_curves: EnergyCurves,
    threshold_ratio: float = 2.0,
    min_quiet_duration: float = 4.0,
    quiet_threshold: float = 0.3
) -> List[DropInfo]:
    """
    Detect sudden energy increases (drops) after quiet sections.

    Args:
        energy_curves: EnergyCurves from extract_energy_curves
        threshold_ratio: Minimum energy increase ratio to qualify as drop
        min_quiet_duration: Minimum duration of quiet section before drop (seconds)
        quiet_threshold: Maximum energy level to qualify as "quiet" (0-1)

    Returns:
        List of DropInfo objects with timestamps and energy ratios
    """
    energy = energy_curves.energy_curve
    times = energy_curves.times

    if len(energy) < 10:
        return []

    # Find quiet sections (energy below threshold)
    is_quiet = energy < quiet_threshold

    # Find transitions from quiet to loud
    drops = []
    in_quiet = False
    quiet_start = 0

    for i in range(1, len(energy)):
        if is_quiet[i] and not in_quiet:
            # Entering quiet section
            in_quiet = True
            quiet_start = i
        elif not is_quiet[i] and in_quiet:
            # Exiting quiet section - potential drop
            in_quiet = False
            quiet_duration = times[i] - times[quiet_start]

            if quiet_duration >= min_quiet_duration:
                # Calculate energy before and after
                energy_before = np.mean(energy[max(0, quiet_start-10):quiet_start])
                energy_after = np.mean(energy[i:min(len(energy), i+10)])

                if energy_before > 0:
                    ratio = energy_after / max(energy_before, 0.01)
                else:
                    ratio = energy_after * 10  # High ratio if coming from silence

                if ratio >= threshold_ratio:
                    drops.append(DropInfo(
                        time=float(times[i]),
                        energy_before=float(energy_before),
                        energy_after=float(energy_after),
                        ratio=float(ratio),
                        pre_drop_duration=float(quiet_duration)
                    ))

    return drops


def compute_energy_progression_score(energy_curves: EnergyCurves) -> float:
    """
    Compute score based on energy progression characteristics.

    Good trance characteristics:
    - Wide energy range (builds and breaks)
    - Clear breakdown/buildup patterns
    - Dynamic contrast

    Args:
        energy_curves: EnergyCurves from extract_energy_curves

    Returns:
        Score 0-1 indicating trance-like energy progression
    """
    # Range score: wider range = better trance characteristics
    range_score = np.clip(energy_curves.energy_range / 0.7, 0.0, 1.0)

    # Variation score: trance should have dynamic variation
    std_score = np.clip(energy_curves.energy_std / 0.2, 0.0, 1.0)

    # Check for breakdown patterns (periods of low energy)
    energy = energy_curves.energy_curve
    low_energy_ratio = np.mean(energy < 0.3)  # Fraction of time at low energy
    # Ideal: 15-35% of track at low energy (breakdowns)
    if 0.1 <= low_energy_ratio <= 0.4:
        breakdown_score = 1.0
    else:
        breakdown_score = 1.0 - abs(low_energy_ratio - 0.25) / 0.25
        breakdown_score = max(0.0, breakdown_score)

    # Combine scores
    progression_score = (
        0.40 * range_score +
        0.30 * std_score +
        0.30 * breakdown_score
    )

    return float(np.clip(progression_score, 0.0, 1.0))


def detect_buildup_sections(
    energy_curves: EnergyCurves,
    min_duration: float = 8.0,
    slope_threshold: float = 0.02
) -> List[Tuple[float, float]]:
    """
    Detect buildup sections (sustained energy increase).

    Args:
        energy_curves: EnergyCurves from extract_energy_curves
        min_duration: Minimum buildup duration in seconds
        slope_threshold: Minimum average slope (energy/second)

    Returns:
        List of (start_time, end_time) tuples for buildup sections
    """
    energy = energy_curves.energy_curve
    times = energy_curves.times

    if len(energy) < 10:
        return []

    # Calculate energy derivative
    dt = np.diff(times)
    de = np.diff(energy)
    slope = de / (dt + 1e-10)

    # Smooth the slope
    smooth_frames = max(1, int(2.0 / np.mean(dt)))  # 2 second smoothing
    slope_smooth = _smooth_signal(slope, smooth_frames)

    # Find sections with positive slope
    is_building = slope_smooth > slope_threshold

    buildups = []
    in_buildup = False
    buildup_start = 0

    for i in range(len(is_building)):
        if is_building[i] and not in_buildup:
            in_buildup = True
            buildup_start = i
        elif not is_building[i] and in_buildup:
            in_buildup = False
            duration = times[i] - times[buildup_start]
            if duration >= min_duration:
                buildups.append((float(times[buildup_start]), float(times[i])))

    # Handle buildup that continues to end
    if in_buildup:
        duration = times[-1] - times[buildup_start]
        if duration >= min_duration:
            buildups.append((float(times[buildup_start]), float(times[-1])))

    return buildups
