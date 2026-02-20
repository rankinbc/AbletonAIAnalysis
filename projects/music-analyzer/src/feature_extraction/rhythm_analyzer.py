"""
Tempo and Rhythm Analysis Module.

Analyzes rhythm characteristics specific to trance music:
- Trance-optimized tempo detection (138-140 BPM prior)
- 4-on-the-floor kick pattern detection
- Off-beat hi-hat detection
- Tempo stability measurement

Typical trance: 128-150 BPM, strong 4-on-the-floor, prominent off-beat hihats.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple
import librosa


@dataclass
class TempoFeatures:
    """Results from tempo analysis."""
    tempo: float  # Detected BPM
    beat_times: np.ndarray  # Timestamps of detected beats
    tempo_stability: float  # Consistency measure (0-1)
    is_trance_tempo: bool  # BPM in typical trance range (128-150)
    tempo_confidence: float  # Detection confidence (0-1)


@dataclass
class KickPatternFeatures:
    """Results from 4-on-the-floor detection."""
    is_four_on_floor: bool  # True if pattern detected (strength > 0.5)
    strength: float  # Autocorrelation strength at beat period (0-1)
    kick_consistency: float  # How consistent kicks are across song
    avg_kick_level: float  # Average kick energy


@dataclass
class HihatFeatures:
    """Results from off-beat hi-hat detection."""
    offbeat_strength: float  # Strength of off-beat hihats (0-1)
    hihat_consistency: float  # Consistency of hihat pattern
    hihat_brightness: float  # Average brightness of hihat region


@dataclass
class RhythmFeatures:
    """Combined rhythm analysis results."""
    tempo: TempoFeatures
    kicks: KickPatternFeatures
    hihats: HihatFeatures

    # Summary scores
    four_on_floor_score: float  # 0-1 score for kick pattern
    offbeat_hihat_score: float  # 0-1 score for hihat pattern
    tempo_score: float  # 0-1 score for trance-appropriate tempo


def detect_trance_tempo(
    audio_path_or_data,
    sr: Optional[int] = None,
    trance_prior: Tuple[float, float] = (138.0, 140.0),
    hop_length: int = 512
) -> TempoFeatures:
    """
    Tempo detection with trance-specific prior (138-140 BPM).

    Args:
        audio_path_or_data: Path to audio file or numpy array
        sr: Sample rate (required if array provided)
        trance_prior: Expected tempo range for prior (BPM)
        hop_length: Hop length for beat tracking

    Returns:
        TempoFeatures with tempo, beat times, and stability metrics
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

    # Compute onset strength envelope
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)

    # Initial tempo estimation using librosa's built-in
    tempo_estimate, _ = librosa.beat.beat_track(
        onset_envelope=onset_env, sr=sr, hop_length=hop_length
    )

    # Handle both scalar and array returns from librosa
    if isinstance(tempo_estimate, np.ndarray):
        tempo_estimate = float(tempo_estimate[0]) if len(tempo_estimate) > 0 else 138.0
    else:
        tempo_estimate = float(tempo_estimate)

    # Check if initial estimate is in trance range, if not, try to find a multiple/divisor
    tempo = _adjust_tempo_for_trance(tempo_estimate, trance_prior)

    # Get beat times with adjusted tempo as prior
    _, beat_frames = librosa.beat.beat_track(
        onset_envelope=onset_env,
        sr=sr,
        hop_length=hop_length,
        bpm=tempo
    )

    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length)

    # Calculate tempo stability
    if len(beat_times) > 1:
        inter_beat_intervals = np.diff(beat_times)
        expected_interval = 60.0 / tempo
        deviations = np.abs(inter_beat_intervals - expected_interval) / expected_interval
        tempo_stability = 1.0 - np.clip(np.mean(deviations), 0.0, 1.0)
    else:
        tempo_stability = 0.0

    # Check if in trance range
    is_trance_tempo = 128 <= tempo <= 150

    # Confidence based on tempo stability and onset strength
    tempo_confidence = tempo_stability * np.clip(np.mean(onset_env) / np.max(onset_env), 0.0, 1.0)

    return TempoFeatures(
        tempo=float(tempo),
        beat_times=beat_times,
        tempo_stability=float(tempo_stability),
        is_trance_tempo=bool(is_trance_tempo),
        tempo_confidence=float(tempo_confidence)
    )


def _adjust_tempo_for_trance(
    tempo: float,
    trance_range: Tuple[float, float]
) -> float:
    """
    Adjust tempo to fall within trance range if possible.

    Tries multiples and divisors to find a tempo in the trance range.
    """
    trance_min, trance_max = trance_range
    target_center = (trance_min + trance_max) / 2

    # If already in range, return as-is
    if trance_min - 10 <= tempo <= trance_max + 10:
        return tempo

    # Try doubling (half-time detection)
    if trance_min - 10 <= tempo * 2 <= trance_max + 10:
        return tempo * 2

    # Try halving (double-time detection)
    if trance_min - 10 <= tempo / 2 <= trance_max + 10:
        return tempo / 2

    # If still outside range, use target center as best guess
    # but keep original if it's at least somewhat reasonable
    if 100 <= tempo <= 180:
        return tempo

    return target_center


def detect_four_on_floor(
    audio_path_or_data,
    sr: Optional[int] = None,
    tempo: Optional[float] = None,
    hop_length: int = 512
) -> KickPatternFeatures:
    """
    Verify 4-on-the-floor kick pattern.

    Args:
        audio_path_or_data: Path to audio file or numpy array
        sr: Sample rate (required if array provided)
        tempo: Expected tempo (will be detected if not provided)
        hop_length: Hop length for analysis

    Returns:
        KickPatternFeatures with pattern strength and consistency
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

    # Detect tempo if not provided
    if tempo is None:
        tempo_features = detect_trance_tempo(y, sr=sr, hop_length=hop_length)
        tempo = tempo_features.tempo

    # Focus on kick frequency range (20-150 Hz)
    y_kick = _lowpass_filter(y, sr, 150)

    # Compute onset strength for kick region
    onset_env = librosa.onset.onset_strength(y=y_kick, sr=sr, hop_length=hop_length)

    # Calculate expected beat period in frames
    beat_period_seconds = 60.0 / tempo
    beat_period_frames = int(beat_period_seconds * sr / hop_length)

    if beat_period_frames < 2 or len(onset_env) < beat_period_frames * 4:
        return KickPatternFeatures(
            is_four_on_floor=False,
            strength=0.0,
            kick_consistency=0.0,
            avg_kick_level=0.0
        )

    # Compute autocorrelation at beat period
    autocorr = np.correlate(onset_env, onset_env, mode='full')
    autocorr = autocorr[len(autocorr)//2:]  # Take positive lags only

    # Normalize
    autocorr = autocorr / (autocorr[0] + 1e-10)

    # Get strength at beat period (and nearby for tolerance)
    tolerance = max(1, beat_period_frames // 8)
    start_idx = max(0, beat_period_frames - tolerance)
    end_idx = min(len(autocorr), beat_period_frames + tolerance + 1)

    if end_idx <= start_idx:
        strength = 0.0
    else:
        strength = np.max(autocorr[start_idx:end_idx])

    # Also check half-beat period (should be weak for true 4/4)
    half_beat_frames = beat_period_frames // 2
    if half_beat_frames > 0 and half_beat_frames < len(autocorr):
        half_beat_strength = autocorr[half_beat_frames]
        # If half-beat is as strong as full beat, might be 8th note pattern, not kick
        if half_beat_strength > strength * 0.9:
            strength *= 0.7  # Penalty

    # Calculate kick consistency across track
    # Divide into 8-bar sections and check pattern in each
    frames_per_8bars = beat_period_frames * 32  # 8 bars * 4 beats
    n_sections = max(1, len(onset_env) // frames_per_8bars)

    section_strengths = []
    for i in range(n_sections):
        start = i * frames_per_8bars
        end = min((i + 1) * frames_per_8bars, len(onset_env))
        section = onset_env[start:end]

        if len(section) > beat_period_frames * 2:
            section_autocorr = np.correlate(section, section, mode='full')
            section_autocorr = section_autocorr[len(section_autocorr)//2:]
            section_autocorr = section_autocorr / (section_autocorr[0] + 1e-10)

            if beat_period_frames < len(section_autocorr):
                section_strengths.append(section_autocorr[beat_period_frames])

    if len(section_strengths) > 0:
        kick_consistency = 1.0 - np.std(section_strengths)
        kick_consistency = np.clip(kick_consistency, 0.0, 1.0)
    else:
        kick_consistency = 0.0

    # Average kick level
    avg_kick_level = float(np.mean(onset_env))

    # Determine if 4-on-the-floor
    is_four_on_floor = strength > 0.5 and kick_consistency > 0.4

    return KickPatternFeatures(
        is_four_on_floor=bool(is_four_on_floor),
        strength=float(np.clip(strength, 0.0, 1.0)),
        kick_consistency=float(kick_consistency),
        avg_kick_level=float(avg_kick_level)
    )


def _lowpass_filter(y: np.ndarray, sr: int, cutoff: float) -> np.ndarray:
    """Apply lowpass filter."""
    from scipy.signal import butter, filtfilt

    nyquist = sr / 2
    normalized_cutoff = min(cutoff / nyquist, 0.99)

    if normalized_cutoff <= 0:
        return y

    try:
        b, a = butter(4, normalized_cutoff, btype='low')
        return filtfilt(b, a, y)
    except Exception:
        return y


def _highpass_filter(y: np.ndarray, sr: int, cutoff: float) -> np.ndarray:
    """Apply highpass filter."""
    from scipy.signal import butter, filtfilt

    nyquist = sr / 2
    normalized_cutoff = cutoff / nyquist

    if normalized_cutoff <= 0 or normalized_cutoff >= 1:
        return y

    try:
        b, a = butter(4, normalized_cutoff, btype='high')
        return filtfilt(b, a, y)
    except Exception:
        return y


def detect_offbeat_hihats(
    audio_path_or_data,
    sr: Optional[int] = None,
    tempo: Optional[float] = None,
    hop_length: int = 512
) -> HihatFeatures:
    """
    Detect off-beat hi-hat patterns typical in trance.

    Args:
        audio_path_or_data: Path to audio file or numpy array
        sr: Sample rate (required if array provided)
        tempo: Expected tempo (will be detected if not provided)
        hop_length: Hop length for analysis

    Returns:
        HihatFeatures with offbeat strength and consistency
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

    # Detect tempo if not provided
    if tempo is None:
        tempo_features = detect_trance_tempo(y, sr=sr, hop_length=hop_length)
        tempo = tempo_features.tempo

    # Focus on hi-hat frequency range (5000-15000 Hz)
    y_hihat = _highpass_filter(y, sr, 5000)

    # Compute onset strength for hihat region
    onset_env = librosa.onset.onset_strength(y=y_hihat, sr=sr, hop_length=hop_length)

    # Calculate beat period in frames
    beat_period_seconds = 60.0 / tempo
    beat_period_frames = int(beat_period_seconds * sr / hop_length)
    half_beat_frames = beat_period_frames // 2

    if half_beat_frames < 1 or len(onset_env) < beat_period_frames * 4:
        return HihatFeatures(
            offbeat_strength=0.0,
            hihat_consistency=0.0,
            hihat_brightness=0.0
        )

    # Get beat tracking
    _, beat_frames = librosa.beat.beat_track(
        onset_envelope=librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length),
        sr=sr,
        hop_length=hop_length,
        bpm=tempo
    )

    if len(beat_frames) < 4:
        return HihatFeatures(
            offbeat_strength=0.0,
            hihat_consistency=0.0,
            hihat_brightness=0.0
        )

    # Sample onset strength at on-beats and off-beats
    on_beat_strengths = []
    off_beat_strengths = []

    for i, beat in enumerate(beat_frames[:-1]):
        # On-beat
        if beat < len(onset_env):
            on_beat_strengths.append(onset_env[beat])

        # Off-beat (between this beat and next)
        offbeat = beat + half_beat_frames
        if offbeat < len(onset_env) and offbeat < beat_frames[i + 1]:
            off_beat_strengths.append(onset_env[offbeat])

    if len(off_beat_strengths) == 0:
        return HihatFeatures(
            offbeat_strength=0.0,
            hihat_consistency=0.0,
            hihat_brightness=0.0
        )

    # Calculate off-beat strength relative to on-beat
    avg_offbeat = np.mean(off_beat_strengths)
    avg_onbeat = np.mean(on_beat_strengths) if len(on_beat_strengths) > 0 else 1.0

    # Offbeat should be prominent but not overwhelm kick
    if avg_onbeat > 0:
        relative_strength = avg_offbeat / avg_onbeat
        # Ideal: offbeat is 50-100% of onbeat strength
        offbeat_strength = np.clip(relative_strength, 0.0, 1.0)
    else:
        offbeat_strength = avg_offbeat / (np.max(onset_env) + 1e-10)

    # Consistency of offbeat pattern
    if len(off_beat_strengths) > 1:
        hihat_consistency = 1.0 - np.std(off_beat_strengths) / (np.mean(off_beat_strengths) + 1e-10)
        hihat_consistency = np.clip(hihat_consistency, 0.0, 1.0)
    else:
        hihat_consistency = 0.0

    # Brightness of hihat region
    centroid = librosa.feature.spectral_centroid(y=y_hihat, sr=sr, hop_length=hop_length)
    hihat_brightness = np.mean(centroid) / 10000  # Normalize roughly to 0-1

    return HihatFeatures(
        offbeat_strength=float(offbeat_strength),
        hihat_consistency=float(hihat_consistency),
        hihat_brightness=float(np.clip(hihat_brightness, 0.0, 1.0))
    )


def analyze_rhythm(
    audio_path_or_data,
    sr: Optional[int] = None,
    hop_length: int = 512
) -> RhythmFeatures:
    """
    Comprehensive rhythm analysis for trance music.

    Args:
        audio_path_or_data: Path to audio file or numpy array
        sr: Sample rate (required if array provided)
        hop_length: Hop length for analysis

    Returns:
        RhythmFeatures with tempo, kick, and hihat analysis
    """
    # Detect tempo first
    tempo_features = detect_trance_tempo(audio_path_or_data, sr=sr, hop_length=hop_length)

    # Use detected tempo for other analyses
    tempo = tempo_features.tempo

    # Detect 4-on-the-floor
    kick_features = detect_four_on_floor(
        audio_path_or_data, sr=sr, tempo=tempo, hop_length=hop_length
    )

    # Detect off-beat hihats
    hihat_features = detect_offbeat_hihats(
        audio_path_or_data, sr=sr, tempo=tempo, hop_length=hop_length
    )

    # Calculate summary scores
    four_on_floor_score = kick_features.strength * kick_features.kick_consistency
    offbeat_hihat_score = hihat_features.offbeat_strength * hihat_features.hihat_consistency

    # Tempo score: highest for 138-140, still good for 128-150
    if 138 <= tempo <= 140:
        tempo_score = 1.0
    elif 128 <= tempo <= 150:
        # Linear falloff from optimal range
        if tempo < 138:
            tempo_score = 0.7 + 0.3 * (tempo - 128) / 10
        else:
            tempo_score = 0.7 + 0.3 * (150 - tempo) / 10
    else:
        tempo_score = 0.3

    return RhythmFeatures(
        tempo=tempo_features,
        kicks=kick_features,
        hihats=hihat_features,
        four_on_floor_score=float(four_on_floor_score),
        offbeat_hihat_score=float(offbeat_hihat_score),
        tempo_score=float(tempo_score)
    )
