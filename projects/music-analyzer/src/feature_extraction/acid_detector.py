"""
TB-303 Acid Bassline Detection Module.

Detects characteristics of 303-style acid basslines:
- Filter sweep detection via spectral centroid movement
- Resonance measurement via bandwidth/centroid ratio
- Pitch glide detection using pYIN F0 tracking
- Accent pattern detection via RMS/brightness correlation

Classic acid tracks (Hardfloor, Emmanuel Top) should score > 0.7.
Non-acid trance should score < 0.3.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple
import librosa


@dataclass
class AcidFeatures:
    """Results from acid bassline detection."""
    filter_sweep_score: float  # 0-1, amount of filter movement
    resonance_score: float  # 0-1, amount of resonant character
    glide_score: float  # 0-1, amount of pitch gliding
    accent_score: float  # 0-1, accent pattern presence
    overall_303_score: float  # Weighted composite score

    # Detailed metrics
    avg_centroid_movement: float  # Hz, average centroid change per frame
    centroid_range: float  # Hz, total centroid range
    avg_bandwidth: float  # Hz, average spectral bandwidth
    glide_count: int  # Number of detected pitch glides
    accent_correlation: float  # Correlation between RMS and brightness


def extract_acid_features(
    audio_path_or_data,
    sr: Optional[int] = None,
    frame_length: int = 2048,
    hop_length: int = 512,
    bass_freq_range: Tuple[float, float] = (40.0, 500.0),
) -> AcidFeatures:
    """
    Extract TB-303 acid bassline characteristics.

    Args:
        audio_path_or_data: Path to audio file or numpy array
        sr: Sample rate (required if array provided)
        frame_length: FFT window size
        hop_length: Hop length for analysis
        bass_freq_range: Frequency range to focus on (Hz)

    Returns:
        AcidFeatures with filter sweep, resonance, glide, and accent scores
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

    # Apply bandpass filter to focus on bass frequencies
    y_bass = _bandpass_filter(y, sr, bass_freq_range[0], bass_freq_range[1])

    # 1. Filter Sweep Detection - Spectral centroid movement
    filter_sweep_score, avg_centroid_movement, centroid_range = _analyze_filter_sweeps(
        y_bass, sr, frame_length, hop_length
    )

    # 2. Resonance Measurement - Bandwidth/centroid ratio
    resonance_score, avg_bandwidth = _analyze_resonance(
        y_bass, sr, frame_length, hop_length
    )

    # 3. Pitch Glide Detection - F0 tracking
    glide_score, glide_count = _analyze_pitch_glides(y_bass, sr, hop_length)

    # 4. Accent Pattern Detection - RMS/brightness correlation
    accent_score, accent_correlation = _analyze_accents(
        y_bass, sr, frame_length, hop_length
    )

    # Compute overall 303 score with weighted combination
    overall_303_score = compute_303_score_from_components(
        filter_sweep_score, resonance_score, glide_score, accent_score
    )

    return AcidFeatures(
        filter_sweep_score=float(filter_sweep_score),
        resonance_score=float(resonance_score),
        glide_score=float(glide_score),
        accent_score=float(accent_score),
        overall_303_score=float(overall_303_score),
        avg_centroid_movement=float(avg_centroid_movement),
        centroid_range=float(centroid_range),
        avg_bandwidth=float(avg_bandwidth),
        glide_count=int(glide_count),
        accent_correlation=float(accent_correlation)
    )


def _bandpass_filter(y: np.ndarray, sr: int, low_freq: float, high_freq: float) -> np.ndarray:
    """Apply bandpass filter to isolate frequency range."""
    from scipy.signal import butter, filtfilt

    nyquist = sr / 2
    low = low_freq / nyquist
    high = min(high_freq / nyquist, 0.99)

    if low >= high or low <= 0:
        return y

    try:
        b, a = butter(4, [low, high], btype='band')
        y_filtered = filtfilt(b, a, y)
        return y_filtered
    except Exception:
        return y


def _analyze_filter_sweeps(
    y: np.ndarray, sr: int, frame_length: int, hop_length: int
) -> Tuple[float, float, float]:
    """
    Analyze filter sweep characteristics via spectral centroid movement.

    Returns:
        (score, avg_movement_hz, range_hz)
    """
    # Compute spectral centroid
    centroid = librosa.feature.spectral_centroid(
        y=y, sr=sr, n_fft=frame_length, hop_length=hop_length
    )[0]

    if len(centroid) < 2:
        return 0.0, 0.0, 0.0

    # Calculate centroid movement (first derivative)
    centroid_diff = np.abs(np.diff(centroid))
    avg_movement = np.mean(centroid_diff)

    # Calculate centroid range
    centroid_range = np.max(centroid) - np.min(centroid)

    # Normalize to score
    # Typical 303 filter sweep: 100-300 Hz movement per frame
    # Range: 500-2000 Hz total
    movement_score = np.clip(avg_movement / 200.0, 0.0, 1.0)
    range_score = np.clip(centroid_range / 1500.0, 0.0, 1.0)

    # Combine movement and range
    filter_sweep_score = 0.6 * movement_score + 0.4 * range_score

    return filter_sweep_score, avg_movement, centroid_range


def _analyze_resonance(
    y: np.ndarray, sr: int, frame_length: int, hop_length: int
) -> Tuple[float, float]:
    """
    Analyze resonant character via spectral bandwidth/centroid ratio.

    Returns:
        (score, avg_bandwidth_hz)
    """
    # Compute spectral centroid and bandwidth
    centroid = librosa.feature.spectral_centroid(
        y=y, sr=sr, n_fft=frame_length, hop_length=hop_length
    )[0]

    bandwidth = librosa.feature.spectral_bandwidth(
        y=y, sr=sr, n_fft=frame_length, hop_length=hop_length
    )[0]

    if len(centroid) == 0 or len(bandwidth) == 0:
        return 0.0, 0.0

    # Calculate bandwidth/centroid ratio
    # Low ratio = resonant (narrow bandwidth relative to centroid)
    # Avoid division by zero
    centroid_safe = np.where(centroid > 0, centroid, 1)
    ratio = bandwidth / centroid_safe

    avg_ratio = np.mean(ratio)
    avg_bandwidth = np.mean(bandwidth)

    # Resonant 303: ratio around 0.5-1.5
    # Non-resonant: ratio > 2.0
    # Score inversely related to ratio
    resonance_score = np.clip(1.0 - (avg_ratio - 0.5) / 2.0, 0.0, 1.0)

    # Also check for resonance peaks in spectrum
    resonance_variability = np.std(ratio) / np.mean(ratio) if np.mean(ratio) > 0 else 0
    resonance_score = 0.7 * resonance_score + 0.3 * np.clip(resonance_variability, 0.0, 1.0)

    return resonance_score, avg_bandwidth


def _analyze_pitch_glides(
    y: np.ndarray, sr: int, hop_length: int
) -> Tuple[float, int]:
    """
    Analyze pitch gliding using pYIN F0 tracking.

    Returns:
        (score, glide_count)
    """
    try:
        # Use pYIN for pitch tracking
        f0, voiced_flag, voiced_probs = librosa.pyin(
            y, fmin=30, fmax=500, sr=sr, hop_length=hop_length
        )

        if f0 is None or len(f0) < 2:
            return 0.0, 0

        # Get voiced sections only
        voiced_f0 = f0[voiced_flag]

        if len(voiced_f0) < 2:
            return 0.0, 0

        # Calculate pitch changes in cents
        # cent = 1200 * log2(f1/f0)
        voiced_f0_safe = np.where(voiced_f0 > 0, voiced_f0, 1)
        pitch_diff = np.abs(np.diff(np.log2(voiced_f0_safe))) * 1200

        # Count glides (significant pitch changes > 50 cents per frame)
        glide_threshold = 50  # cents
        glides = pitch_diff > glide_threshold
        glide_count = np.sum(glides)

        # Score based on glide frequency
        # Typical 303: glides on 10-30% of voiced frames
        glide_ratio = glide_count / max(len(pitch_diff), 1)
        glide_score = np.clip(glide_ratio / 0.25, 0.0, 1.0)

        # Also consider glide magnitude
        if glide_count > 0:
            avg_glide_magnitude = np.mean(pitch_diff[glides])
            # 303 glides typically 100-300 cents
            magnitude_score = np.clip(avg_glide_magnitude / 200.0, 0.0, 1.0)
            glide_score = 0.6 * glide_score + 0.4 * magnitude_score

        return glide_score, glide_count

    except Exception:
        return 0.0, 0


def _analyze_accents(
    y: np.ndarray, sr: int, frame_length: int, hop_length: int
) -> Tuple[float, float]:
    """
    Analyze accent patterns via RMS/brightness correlation.

    303 accents increase both volume and filter cutoff simultaneously.

    Returns:
        (score, correlation)
    """
    # Compute RMS
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]

    # Compute spectral centroid (brightness)
    centroid = librosa.feature.spectral_centroid(
        y=y, sr=sr, n_fft=frame_length, hop_length=hop_length
    )[0]

    if len(rms) < 2 or len(centroid) < 2:
        return 0.0, 0.0

    # Align lengths
    min_len = min(len(rms), len(centroid))
    rms = rms[:min_len]
    centroid = centroid[:min_len]

    # Calculate correlation between RMS and brightness
    # 303 accents: high correlation (volume and brightness move together)
    correlation = np.corrcoef(rms, centroid)[0, 1]

    if np.isnan(correlation):
        correlation = 0.0

    # Score based on positive correlation
    # 303 typical: correlation 0.4-0.8
    accent_score = np.clip((correlation + 0.2) / 1.0, 0.0, 1.0)

    return accent_score, correlation


def compute_303_score_from_components(
    filter_sweep: float,
    resonance: float,
    glides: float,
    accents: float
) -> float:
    """
    Compute overall 303-ness score from component scores.

    Weights:
        filter_sweep: 0.30 (most characteristic)
        resonance: 0.25 (classic squelchy sound)
        glides: 0.25 (portamento/slide)
        accents: 0.20 (accent patterns)

    Args:
        filter_sweep: Filter movement score (0-1)
        resonance: Resonance score (0-1)
        glides: Pitch glide score (0-1)
        accents: Accent correlation score (0-1)

    Returns:
        Overall 303 score (0-1)
    """
    weights = {
        'filter_sweep': 0.30,
        'resonance': 0.25,
        'glides': 0.25,
        'accents': 0.20
    }

    total = (
        weights['filter_sweep'] * filter_sweep +
        weights['resonance'] * resonance +
        weights['glides'] * glides +
        weights['accents'] * accents
    )

    return float(np.clip(total, 0.0, 1.0))


def compute_303_score(y, sr: int) -> float:
    """
    Convenience function to compute 303 score directly.

    Args:
        y: Audio signal (mono)
        sr: Sample rate

    Returns:
        Overall 303 score (0-1)
    """
    features = extract_acid_features(y, sr=sr)
    return features.overall_303_score
