"""
Sidechain Pumping Detection Module.

Detects sidechain compression via RMS envelope analysis, measuring:
- Modulation depth (dB and linear)
- Pumping regularity (consistency of pump cycles)
- Number of detected pump cycles

Typical trance sidechain: 4-8 dB modulation depth, high regularity.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple
import librosa


@dataclass
class PumpingFeatures:
    """Results from pumping detection analysis."""
    modulation_depth_linear: float  # 0-1, 0.3-0.6 = moderate, >0.6 = heavy
    modulation_depth_db: float  # dB, 4-8 = moderate, >8 = heavy
    pumping_regularity: float  # Lower is more consistent (<0.1 = very consistent)
    num_pump_cycles: int  # Total detected cycles
    avg_pump_duration_ms: float  # Average time between peaks
    pump_times: Optional[np.ndarray] = None  # Timestamps of pump peaks


def extract_pumping_features(
    audio_path_or_data,
    sr: Optional[int] = None,
    expected_bpm: float = 138.0,
    frame_length: int = 2048,
    hop_length: int = 512,
    return_envelope: bool = False
) -> PumpingFeatures:
    """
    Detect sidechain compression via RMS envelope analysis.

    Args:
        audio_path_or_data: Path to audio file or numpy array of audio data
        sr: Sample rate (required if audio_path_or_data is numpy array)
        expected_bpm: Expected tempo for peak distance calculation
        frame_length: FFT window size (~46ms at 44.1kHz)
        hop_length: Hop length for RMS computation
        return_envelope: If True, include pump times in result

    Returns:
        PumpingFeatures with modulation depth, regularity, and cycle count
    """
    # Load audio if path provided
    if isinstance(audio_path_or_data, str):
        y, sr = librosa.load(audio_path_or_data, sr=None, mono=True)
    else:
        y = audio_path_or_data
        if sr is None:
            raise ValueError("sr must be provided when passing audio array")
        # Ensure mono
        if len(y.shape) > 1:
            y = np.mean(y, axis=0)

    # Compute RMS envelope
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]

    # Calculate expected distance between peaks based on BPM
    # For sidechain pumping, peaks typically occur on each beat
    beat_duration_seconds = 60.0 / expected_bpm
    frames_per_beat = int(beat_duration_seconds * sr / hop_length)

    # Find peaks in RMS envelope
    # Use a minimum distance of half a beat to avoid detecting multiple peaks per cycle
    min_distance = max(1, frames_per_beat // 2)

    # Find local maxima (peaks)
    peaks = _find_peaks(rms, min_distance=min_distance)

    # Find local minima (troughs)
    troughs = _find_peaks(-rms, min_distance=min_distance)

    if len(peaks) < 2 or len(troughs) < 2:
        # No significant pumping detected
        return PumpingFeatures(
            modulation_depth_linear=0.0,
            modulation_depth_db=0.0,
            pumping_regularity=1.0,
            num_pump_cycles=0,
            avg_pump_duration_ms=0.0,
            pump_times=np.array([]) if return_envelope else None
        )

    # Calculate modulation depth from peak-to-trough differences
    peak_values = rms[peaks]
    trough_values = rms[troughs]

    # Match peaks to nearest troughs for accurate depth calculation
    depths = []
    for peak_idx, peak_val in zip(peaks, peak_values):
        # Find closest trough before this peak
        troughs_before = troughs[troughs < peak_idx]
        if len(troughs_before) > 0:
            closest_trough_idx = troughs_before[-1]
            trough_val = rms[closest_trough_idx]
            if trough_val > 0:
                depth = (peak_val - trough_val) / peak_val
                depths.append(depth)

    if len(depths) == 0:
        return PumpingFeatures(
            modulation_depth_linear=0.0,
            modulation_depth_db=0.0,
            pumping_regularity=1.0,
            num_pump_cycles=0,
            avg_pump_duration_ms=0.0,
            pump_times=np.array([]) if return_envelope else None
        )

    # Calculate average modulation depth
    modulation_depth_linear = np.mean(depths)
    modulation_depth_linear = np.clip(modulation_depth_linear, 0.0, 1.0)

    # Convert to dB
    if modulation_depth_linear > 0:
        # Depth in dB = 20 * log10(peak/trough) = 20 * log10(1/(1-depth))
        modulation_depth_db = -20 * np.log10(1 - modulation_depth_linear + 1e-10)
    else:
        modulation_depth_db = 0.0

    # Calculate pumping regularity (coefficient of variation of inter-peak intervals)
    if len(peaks) > 1:
        inter_peak_intervals = np.diff(peaks)
        mean_interval = np.mean(inter_peak_intervals)
        std_interval = np.std(inter_peak_intervals)
        if mean_interval > 0:
            pumping_regularity = std_interval / mean_interval
        else:
            pumping_regularity = 1.0
    else:
        pumping_regularity = 1.0

    # Calculate average pump duration in milliseconds
    if len(peaks) > 1:
        avg_frames_between_peaks = np.mean(np.diff(peaks))
        avg_pump_duration_ms = (avg_frames_between_peaks * hop_length / sr) * 1000
    else:
        avg_pump_duration_ms = 0.0

    # Convert peak frame indices to time
    pump_times = librosa.frames_to_time(peaks, sr=sr, hop_length=hop_length) if return_envelope else None

    return PumpingFeatures(
        modulation_depth_linear=float(modulation_depth_linear),
        modulation_depth_db=float(modulation_depth_db),
        pumping_regularity=float(pumping_regularity),
        num_pump_cycles=len(peaks),
        avg_pump_duration_ms=float(avg_pump_duration_ms),
        pump_times=pump_times
    )


def _find_peaks(data: np.ndarray, min_distance: int = 1) -> np.ndarray:
    """
    Find local maxima in data with minimum distance constraint.

    Args:
        data: 1D array to find peaks in
        min_distance: Minimum number of samples between peaks

    Returns:
        Array of peak indices
    """
    peaks = []
    n = len(data)

    if n < 3:
        return np.array(peaks)

    # Find all local maxima
    for i in range(1, n - 1):
        if data[i] > data[i - 1] and data[i] > data[i + 1]:
            # Check if this peak is far enough from the last one
            if len(peaks) == 0 or i - peaks[-1] >= min_distance:
                peaks.append(i)
            elif data[i] > data[peaks[-1]]:
                # Replace last peak if this one is higher
                peaks[-1] = i

    return np.array(peaks)


def compute_pumping_score(features: PumpingFeatures) -> float:
    """
    Compute a normalized pumping score (0-1) from pumping features.

    Score interpretation:
    - 0.0-0.2: No significant sidechain
    - 0.2-0.5: Light sidechain
    - 0.5-0.7: Moderate sidechain (typical trance)
    - 0.7-1.0: Heavy sidechain (aggressive EDM)

    Args:
        features: PumpingFeatures from extract_pumping_features

    Returns:
        Normalized pumping score (0-1)
    """
    # Score based on modulation depth (primary factor)
    # 4-8 dB is typical trance, normalize so 6 dB = 0.5
    depth_score = np.clip(features.modulation_depth_db / 12.0, 0.0, 1.0)

    # Score based on regularity (lower is better)
    # Regularity < 0.1 is very consistent, > 0.3 is inconsistent
    regularity_score = np.clip(1.0 - features.pumping_regularity / 0.3, 0.0, 1.0)

    # Combine scores with depth having more weight
    pumping_score = 0.7 * depth_score + 0.3 * regularity_score

    return float(np.clip(pumping_score, 0.0, 1.0))
