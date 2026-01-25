"""
Spectral analysis for frequency content characterization.

Extracts spectral features that describe the timbral qualities
of the track, useful for comparing the "brightness" or "darkness"
of mixes and understanding frequency distribution.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import numpy as np


@dataclass
class SpectralFeatures:
    """Extracted spectral features."""
    # Spectral shape descriptors
    spectral_centroid_hz: float  # "Center of mass" of spectrum - brightness indicator
    spectral_spread_hz: float  # How spread out the spectrum is
    spectral_rolloff_hz: float  # Frequency below which 85% of energy lies
    spectral_flatness: float  # How noise-like vs tonal (0-1)
    spectral_flux: float  # Rate of spectral change

    # Band energy distribution (percentage of total energy)
    sub_bass_pct: float  # 20-60 Hz
    bass_pct: float  # 60-250 Hz
    low_mid_pct: float  # 250-500 Hz
    mid_pct: float  # 500-2000 Hz
    high_mid_pct: float  # 2000-6000 Hz
    high_pct: float  # 6000-20000 Hz

    # Derived metrics
    brightness_score: float  # 0-100, higher = brighter
    bass_weight_score: float  # 0-100, higher = more bass heavy


# Frequency band definitions (Hz)
FREQUENCY_BANDS = {
    'sub_bass': (20, 60),
    'bass': (60, 250),
    'low_mid': (250, 500),
    'mid': (500, 2000),
    'high_mid': (2000, 6000),
    'high': (6000, 20000)
}


def extract_spectral_features(audio_path: Path) -> Optional[SpectralFeatures]:
    """
    Extract spectral features from an audio file.

    Args:
        audio_path: Path to audio file

    Returns:
        SpectralFeatures or None on error
    """
    try:
        import librosa
    except ImportError:
        raise ImportError(
            "librosa is required for spectral analysis. "
            "Install with: pip install librosa"
        )

    audio_path = Path(audio_path)
    if not audio_path.exists():
        return None

    try:
        # Load audio (mono for spectral analysis)
        y, sr = librosa.load(str(audio_path), sr=44100, mono=True)

        # Compute STFT
        n_fft = 2048
        hop_length = 512
        stft = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop_length))

        # Spectral centroid (brightness indicator)
        centroid = librosa.feature.spectral_centroid(S=stft, sr=sr)[0]
        spectral_centroid = float(np.mean(centroid))

        # Spectral bandwidth (spread)
        bandwidth = librosa.feature.spectral_bandwidth(S=stft, sr=sr)[0]
        spectral_spread = float(np.mean(bandwidth))

        # Spectral rolloff (85% energy threshold)
        rolloff = librosa.feature.spectral_rolloff(S=stft, sr=sr, roll_percent=0.85)[0]
        spectral_rolloff = float(np.mean(rolloff))

        # Spectral flatness (tonality vs noise)
        flatness = librosa.feature.spectral_flatness(S=stft)[0]
        spectral_flatness = float(np.mean(flatness))

        # Spectral flux (rate of change)
        flux = calculate_spectral_flux(stft)
        spectral_flux = float(np.mean(flux))

        # Calculate band energies
        band_energies = calculate_band_energies(stft, sr, n_fft)
        total_energy = sum(band_energies.values())

        # Convert to percentages
        if total_energy > 0:
            sub_bass_pct = (band_energies['sub_bass'] / total_energy) * 100
            bass_pct = (band_energies['bass'] / total_energy) * 100
            low_mid_pct = (band_energies['low_mid'] / total_energy) * 100
            mid_pct = (band_energies['mid'] / total_energy) * 100
            high_mid_pct = (band_energies['high_mid'] / total_energy) * 100
            high_pct = (band_energies['high'] / total_energy) * 100
        else:
            sub_bass_pct = bass_pct = low_mid_pct = mid_pct = high_mid_pct = high_pct = 0.0

        # Calculate derived scores
        brightness_score = calculate_brightness_score(spectral_centroid, spectral_rolloff)
        bass_weight_score = calculate_bass_weight_score(sub_bass_pct, bass_pct, low_mid_pct)

        return SpectralFeatures(
            spectral_centroid_hz=round(spectral_centroid, 1),
            spectral_spread_hz=round(spectral_spread, 1),
            spectral_rolloff_hz=round(spectral_rolloff, 1),
            spectral_flatness=round(spectral_flatness, 4),
            spectral_flux=round(spectral_flux, 4),
            sub_bass_pct=round(sub_bass_pct, 1),
            bass_pct=round(bass_pct, 1),
            low_mid_pct=round(low_mid_pct, 1),
            mid_pct=round(mid_pct, 1),
            high_mid_pct=round(high_mid_pct, 1),
            high_pct=round(high_pct, 1),
            brightness_score=round(brightness_score, 1),
            bass_weight_score=round(bass_weight_score, 1)
        )

    except Exception as e:
        print(f"Error extracting spectral features: {e}")
        return None


def calculate_spectral_flux(stft: np.ndarray) -> np.ndarray:
    """
    Calculate spectral flux (frame-to-frame spectral change).

    Args:
        stft: STFT magnitude spectrogram

    Returns:
        Array of flux values per frame
    """
    # Normalize columns
    norm_stft = stft / (np.sum(stft, axis=0, keepdims=True) + 1e-10)

    # Calculate difference between consecutive frames
    diff = np.diff(norm_stft, axis=1)

    # Sum of squared differences (only positive changes for onset-like flux)
    flux = np.sum(np.maximum(0, diff) ** 2, axis=0)

    return flux


def calculate_band_energies(
    stft: np.ndarray,
    sr: int,
    n_fft: int
) -> Dict[str, float]:
    """
    Calculate energy in each frequency band.

    Args:
        stft: STFT magnitude spectrogram
        sr: Sample rate
        n_fft: FFT size

    Returns:
        Dict mapping band name to energy
    """
    # Get frequency bins
    freqs = np.fft.rfftfreq(n_fft, 1/sr)

    # Calculate mean power spectrum
    power = np.mean(stft ** 2, axis=1)

    energies = {}
    for band_name, (low_freq, high_freq) in FREQUENCY_BANDS.items():
        # Find bins in this band
        band_mask = (freqs >= low_freq) & (freqs < high_freq)
        band_energy = np.sum(power[band_mask])
        energies[band_name] = float(band_energy)

    return energies


def calculate_brightness_score(centroid: float, rolloff: float) -> float:
    """
    Calculate a brightness score from 0-100.

    Higher values indicate brighter (more high-frequency content) mixes.

    Typical values:
    - Dark/warm mix: 20-40
    - Balanced mix: 40-60
    - Bright/airy mix: 60-80
    - Very bright: 80+

    Args:
        centroid: Spectral centroid in Hz
        rolloff: Spectral rolloff in Hz

    Returns:
        Brightness score 0-100
    """
    # Normalize centroid (typical range 500-5000 Hz for music)
    centroid_normalized = np.clip((centroid - 500) / 4500, 0, 1)

    # Normalize rolloff (typical range 2000-15000 Hz)
    rolloff_normalized = np.clip((rolloff - 2000) / 13000, 0, 1)

    # Combine (centroid weighted more heavily)
    brightness = (centroid_normalized * 0.7 + rolloff_normalized * 0.3) * 100

    return brightness


def calculate_bass_weight_score(
    sub_bass_pct: float,
    bass_pct: float,
    low_mid_pct: float
) -> float:
    """
    Calculate a bass weight score from 0-100.

    Higher values indicate more bass-heavy mixes.

    Typical values for trance:
    - Light bass: 20-35
    - Balanced: 35-50
    - Bass heavy: 50-70
    - Sub-heavy: 70+

    Args:
        sub_bass_pct: Sub-bass energy percentage
        bass_pct: Bass energy percentage
        low_mid_pct: Low-mid energy percentage

    Returns:
        Bass weight score 0-100
    """
    # Weighted sum (sub-bass and bass matter most)
    weighted = (sub_bass_pct * 2.0 + bass_pct * 1.5 + low_mid_pct * 0.5)

    # Scale to 0-100 (typical weighted sum is 20-80)
    score = np.clip(weighted * 1.25, 0, 100)

    return score


def get_spectral_profile_over_time(
    audio_path: Path,
    segment_duration: float = 10.0
) -> List[Tuple[float, float, float]]:
    """
    Get spectral centroid and rolloff over time.

    Useful for seeing how the track's brightness evolves.

    Args:
        audio_path: Path to audio file
        segment_duration: Segment duration in seconds

    Returns:
        List of (timestamp, centroid, rolloff) tuples
    """
    try:
        import librosa
    except ImportError:
        return []

    audio_path = Path(audio_path)
    if not audio_path.exists():
        return []

    try:
        y, sr = librosa.load(str(audio_path), sr=44100, mono=True)

        segment_samples = int(segment_duration * sr)
        results = []

        for i in range(0, len(y) - segment_samples, segment_samples):
            segment = y[i:i + segment_samples]

            # Quick spectral analysis
            stft = np.abs(librosa.stft(segment))
            centroid = librosa.feature.spectral_centroid(S=stft, sr=sr)[0]
            rolloff = librosa.feature.spectral_rolloff(S=stft, sr=sr)[0]

            timestamp = i / sr
            results.append((
                round(timestamp, 1),
                round(float(np.mean(centroid)), 1),
                round(float(np.mean(rolloff)), 1)
            ))

        return results

    except Exception:
        return []


def format_spectral_display(spectral: SpectralFeatures) -> str:
    """
    Format spectral features for display.

    Args:
        spectral: Extracted spectral features

    Returns:
        Formatted string
    """
    brightness_desc = "Dark" if spectral.brightness_score < 40 else \
                     "Balanced" if spectral.brightness_score < 60 else \
                     "Bright"

    bass_desc = "Light" if spectral.bass_weight_score < 35 else \
               "Balanced" if spectral.bass_weight_score < 50 else \
               "Heavy"

    lines = [
        f"Brightness: {spectral.brightness_score}/100 ({brightness_desc})",
        f"Bass Weight: {spectral.bass_weight_score}/100 ({bass_desc})",
        f"Spectral Centroid: {spectral.spectral_centroid_hz} Hz",
        "",
        "Band Distribution:",
        f"  Sub-bass (20-60 Hz): {spectral.sub_bass_pct}%",
        f"  Bass (60-250 Hz): {spectral.bass_pct}%",
        f"  Low-mid (250-500 Hz): {spectral.low_mid_pct}%",
        f"  Mid (500-2k Hz): {spectral.mid_pct}%",
        f"  High-mid (2k-6k Hz): {spectral.high_mid_pct}%",
        f"  High (6k-20k Hz): {spectral.high_pct}%",
    ]

    return "\n".join(lines)
