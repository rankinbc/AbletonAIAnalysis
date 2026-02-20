"""
Supersaw Stereo Spread Analysis Module.

Analyzes characteristics of supersaw-style stereo synthesis:
- Mid-Side width ratio
- Phase correlation (L/R)
- Detuning detection via spectral peak clustering
- Estimated voice count

Classic supersaw: stereo width 0.3-0.8, phase correlation 0.3-0.7.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple
import librosa


@dataclass
class SupersawFeatures:
    """Results from supersaw stereo analysis."""
    stereo_width: float  # 0-1, 0 = mono, 0.3-0.8 = typical supersaw
    phase_correlation: float  # -1 to +1, 0.3-0.7 = supersaw typical
    detuning_detected: bool  # Whether detuning patterns found
    estimated_voices: int  # Estimated number of unison voices (typically 5-9)
    spread_cents: float  # Estimated detuning amount (10-40 typical)

    # Detailed metrics
    mid_energy: float  # RMS of mid channel
    side_energy: float  # RMS of side channel
    width_over_time: Optional[np.ndarray] = None  # Width evolution


def analyze_supersaw_characteristics(
    audio_path_or_data,
    sr: Optional[int] = None,
    frame_length: int = 2048,
    hop_length: int = 512,
    return_time_series: bool = False
) -> SupersawFeatures:
    """
    Analyze supersaw-style stereo spread characteristics.

    Args:
        audio_path_or_data: Path to stereo audio file or (2, N) array
        sr: Sample rate (required if array provided)
        frame_length: FFT window size
        hop_length: Hop length for analysis
        return_time_series: If True, include width over time

    Returns:
        SupersawFeatures with stereo width, correlation, and detuning info
    """
    # Load audio if path provided
    if isinstance(audio_path_or_data, str):
        y, sr = librosa.load(audio_path_or_data, sr=None, mono=False)
    else:
        y = audio_path_or_data
        if sr is None:
            raise ValueError("sr must be provided when passing audio array")

    # Handle mono input
    if len(y.shape) == 1 or (len(y.shape) == 2 and y.shape[0] == 1):
        # Mono signal - no stereo information
        if len(y.shape) == 2:
            y = y[0]
        return SupersawFeatures(
            stereo_width=0.0,
            phase_correlation=1.0,
            detuning_detected=False,
            estimated_voices=1,
            spread_cents=0.0,
            mid_energy=float(np.sqrt(np.mean(y**2))),
            side_energy=0.0,
            width_over_time=None
        )

    # Ensure stereo format (2, N)
    if y.shape[0] > 2:
        y = y.T
    if y.shape[0] != 2:
        raise ValueError("Audio must be stereo (2 channels)")

    left = y[0]
    right = y[1]

    # Compute Mid-Side
    mid = (left + right) / 2
    side = (left - right) / 2

    # Calculate basic energy levels
    mid_energy = np.sqrt(np.mean(mid**2))
    side_energy = np.sqrt(np.mean(side**2))

    # 1. Stereo Width Ratio
    stereo_width, width_over_time = _compute_stereo_width(
        mid, side, frame_length, hop_length, return_time_series
    )

    # 2. Phase Correlation
    phase_correlation = _compute_phase_correlation(left, right, frame_length, hop_length)

    # 3. Detuning Detection
    detuning_detected, estimated_voices, spread_cents = _detect_detuning(
        mid, sr, frame_length, hop_length
    )

    return SupersawFeatures(
        stereo_width=float(stereo_width),
        phase_correlation=float(phase_correlation),
        detuning_detected=bool(detuning_detected),
        estimated_voices=int(estimated_voices),
        spread_cents=float(spread_cents),
        mid_energy=float(mid_energy),
        side_energy=float(side_energy),
        width_over_time=width_over_time if return_time_series else None
    )


def _compute_stereo_width(
    mid: np.ndarray,
    side: np.ndarray,
    frame_length: int,
    hop_length: int,
    return_time_series: bool
) -> Tuple[float, Optional[np.ndarray]]:
    """
    Compute stereo width as side/mid RMS ratio.

    Returns:
        (average_width, width_over_time)
    """
    # Compute frame-by-frame RMS
    mid_rms = librosa.feature.rms(y=mid, frame_length=frame_length, hop_length=hop_length)[0]
    side_rms = librosa.feature.rms(y=side, frame_length=frame_length, hop_length=hop_length)[0]

    # Calculate width ratio per frame (avoid division by zero)
    mid_safe = np.where(mid_rms > 1e-10, mid_rms, 1e-10)
    width_per_frame = side_rms / mid_safe

    # Clip to reasonable range
    width_per_frame = np.clip(width_per_frame, 0.0, 2.0)

    # Average width, normalized to 0-1 range
    # Width ratio of 1.0 = equal mid and side = moderately wide
    # Normalize so that typical supersaw (0.5-1.0 ratio) maps to 0.3-0.8 score
    avg_width = np.mean(width_per_frame)
    normalized_width = np.clip(avg_width / 1.5, 0.0, 1.0)

    return normalized_width, width_per_frame if return_time_series else None


def _compute_phase_correlation(
    left: np.ndarray,
    right: np.ndarray,
    frame_length: int,
    hop_length: int
) -> float:
    """
    Compute phase correlation coefficient between L and R channels.

    Returns:
        correlation: -1 (out of phase) to +1 (mono/in-phase)
        Typical supersaw: 0.3-0.7
    """
    # Frame the signals
    n_frames = 1 + (len(left) - frame_length) // hop_length

    if n_frames < 1:
        return float(np.corrcoef(left, right)[0, 1])

    correlations = []
    for i in range(n_frames):
        start = i * hop_length
        end = start + frame_length

        l_frame = left[start:end]
        r_frame = right[start:end]

        # Pearson correlation
        corr = np.corrcoef(l_frame, r_frame)[0, 1]
        if not np.isnan(corr):
            correlations.append(corr)

    if len(correlations) == 0:
        return 1.0

    return float(np.mean(correlations))


def _detect_detuning(
    y: np.ndarray,
    sr: int,
    frame_length: int,
    hop_length: int
) -> Tuple[bool, int, float]:
    """
    Detect supersaw-style detuning via spectral peak clustering.

    Supersaw characteristics:
    - Multiple closely-spaced spectral peaks around fundamental
    - Peak clustering indicates detuned oscillators
    - Spread typically 10-40 cents between voices

    Returns:
        (detuning_detected, estimated_voices, spread_cents)
    """
    # Compute spectrogram
    D = np.abs(librosa.stft(y, n_fft=frame_length, hop_length=hop_length))

    # Average across time to get overall spectrum
    avg_spectrum = np.mean(D, axis=1)

    # Find spectral peaks
    freqs = librosa.fft_frequencies(sr=sr, n_fft=frame_length)
    peaks = _find_spectral_peaks(avg_spectrum, freqs, min_db=-40)

    if len(peaks) < 3:
        return False, 1, 0.0

    # Look for clustered peaks (indicates detuning)
    # Sort peaks by frequency
    peak_freqs = np.array([p[0] for p in peaks])
    peak_freqs = np.sort(peak_freqs)

    # Find fundamental (lowest significant peak)
    fundamental = peak_freqs[0]
    if fundamental < 50:  # Too low, likely DC or noise
        fundamental = peak_freqs[1] if len(peak_freqs) > 1 else 100

    # Look for clusters around harmonic frequencies
    clusters = []
    for harmonic in range(1, 5):  # Check first 4 harmonics
        target_freq = fundamental * harmonic
        # Find peaks within ±5% of target frequency
        tolerance = target_freq * 0.05
        cluster_peaks = peak_freqs[
            (peak_freqs >= target_freq - tolerance) &
            (peak_freqs <= target_freq + tolerance)
        ]
        if len(cluster_peaks) > 1:
            clusters.append(cluster_peaks)

    if len(clusters) == 0:
        return False, 1, 0.0

    # Estimate number of voices and spread from clusters
    all_voices = []
    all_spreads = []

    for cluster in clusters:
        n_voices = len(cluster)
        if n_voices > 1:
            # Calculate spread in cents between min and max
            freq_ratio = cluster[-1] / cluster[0]
            spread = 1200 * np.log2(freq_ratio)  # Convert to cents
            all_voices.append(n_voices)
            all_spreads.append(spread)

    if len(all_voices) == 0:
        return False, 1, 0.0

    estimated_voices = int(np.median(all_voices))
    spread_cents = float(np.median(all_spreads))

    # Typical supersaw: 5-9 voices, 10-40 cents spread
    detuning_detected = estimated_voices >= 3 and spread_cents > 5

    return detuning_detected, estimated_voices, spread_cents


def _find_spectral_peaks(
    spectrum: np.ndarray,
    freqs: np.ndarray,
    min_db: float = -40
) -> list:
    """
    Find prominent peaks in spectrum.

    Returns:
        List of (frequency, magnitude_db) tuples
    """
    # Convert to dB
    spectrum_db = 20 * np.log10(spectrum + 1e-10)
    max_db = np.max(spectrum_db)

    # Normalize relative to max
    spectrum_db_norm = spectrum_db - max_db

    peaks = []
    for i in range(1, len(spectrum_db) - 1):
        # Local maximum above threshold
        if (spectrum_db_norm[i] > spectrum_db_norm[i-1] and
            spectrum_db_norm[i] > spectrum_db_norm[i+1] and
            spectrum_db_norm[i] > min_db):
            peaks.append((freqs[i], spectrum_db_norm[i]))

    return peaks


def compute_supersaw_score(features: SupersawFeatures) -> float:
    """
    Compute normalized supersaw score (0-1) from features.

    Score interpretation:
    - 0.0-0.2: Mono or narrow
    - 0.2-0.5: Light stereo spread
    - 0.5-0.8: Typical supersaw
    - 0.8-1.0: Very wide supersaw

    Args:
        features: SupersawFeatures from analyze_supersaw_characteristics

    Returns:
        Normalized supersaw score (0-1)
    """
    # Width score (primary factor)
    width_score = features.stereo_width

    # Correlation score (ideal: 0.4-0.6 for supersaw)
    # Too high = mono, too low = phase issues
    corr = features.phase_correlation
    if 0.3 <= corr <= 0.7:
        corr_score = 1.0
    elif corr > 0.7:
        corr_score = 1.0 - (corr - 0.7) / 0.3  # Penalty for being too mono
    else:
        corr_score = max(0.0, corr / 0.3)  # Penalty for phase issues

    # Detuning score
    if features.detuning_detected:
        # Score based on voice count (5-9 optimal)
        voice_score = np.clip((features.estimated_voices - 2) / 7, 0.0, 1.0)
        # Score based on spread (20-30 cents optimal)
        spread_score = np.clip(features.spread_cents / 40, 0.0, 1.0)
        detuning_score = 0.5 * voice_score + 0.5 * spread_score
    else:
        detuning_score = 0.0

    # Combine scores
    supersaw_score = (
        0.50 * width_score +
        0.25 * corr_score +
        0.25 * detuning_score
    )

    return float(np.clip(supersaw_score, 0.0, 1.0))
