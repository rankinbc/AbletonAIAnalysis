"""
Genre Presets Module

Provides genre-specific target values for analysis.
Each preset defines ideal frequency balance, loudness, dynamics, and stereo characteristics.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class GenrePreset:
    """Target values for a specific genre."""
    name: str
    description: str

    # Loudness targets
    target_lufs: float          # Integrated LUFS for streaming
    club_lufs: float            # LUFS for club/DJ play
    crest_factor_min: float     # Minimum crest factor (dB)
    crest_factor_max: float     # Maximum crest factor (dB)

    # Frequency balance (percentages, should sum to ~100%)
    sub_bass_pct: tuple         # (min, max) for 20-60Hz
    bass_pct: tuple             # (min, max) for 60-250Hz
    low_mid_pct: tuple          # (min, max) for 250-500Hz (mud zone)
    mid_pct: tuple              # (min, max) for 500-2kHz
    high_mid_pct: tuple         # (min, max) for 2-6kHz
    high_pct: tuple             # (min, max) for 6-20kHz

    # Stereo characteristics
    correlation_min: float      # Minimum L/R correlation (mono safety)
    correlation_max: float      # Maximum correlation (width)
    bass_mono_below_hz: int     # Frequency below which bass should be mono

    # Dynamics
    transient_strength_target: float  # Target avg transient strength

    # BPM range
    bpm_min: int
    bpm_max: int


# Genre preset definitions
GENRE_PRESETS: Dict[str, GenrePreset] = {
    'trance': GenrePreset(
        name='Trance',
        description='Uplifting/progressive trance with emotional breakdowns and impactful drops',
        target_lufs=-14.0,
        club_lufs=-9.0,
        crest_factor_min=8.0,
        crest_factor_max=12.0,
        sub_bass_pct=(5, 10),
        bass_pct=(20, 30),
        low_mid_pct=(10, 15),
        mid_pct=(20, 25),
        high_mid_pct=(15, 20),
        high_pct=(10, 15),
        correlation_min=0.3,
        correlation_max=0.6,
        bass_mono_below_hz=150,
        transient_strength_target=0.4,
        bpm_min=136,
        bpm_max=145
    ),

    'house': GenrePreset(
        name='House',
        description='Deep/tech house with groovy basslines and 4-on-the-floor kick',
        target_lufs=-14.0,
        club_lufs=-8.0,
        crest_factor_min=8.0,
        crest_factor_max=14.0,
        sub_bass_pct=(8, 15),
        bass_pct=(25, 35),
        low_mid_pct=(8, 14),
        mid_pct=(18, 25),
        high_mid_pct=(12, 18),
        high_pct=(8, 14),
        correlation_min=0.35,
        correlation_max=0.65,
        bass_mono_below_hz=120,
        transient_strength_target=0.45,
        bpm_min=120,
        bpm_max=128
    ),

    'techno': GenrePreset(
        name='Techno',
        description='Industrial/peak-time techno with driving rhythms and dark atmosphere',
        target_lufs=-14.0,
        club_lufs=-7.0,
        crest_factor_min=6.0,
        crest_factor_max=10.0,
        sub_bass_pct=(10, 18),
        bass_pct=(25, 38),
        low_mid_pct=(8, 12),
        mid_pct=(15, 22),
        high_mid_pct=(12, 18),
        high_pct=(8, 12),
        correlation_min=0.4,
        correlation_max=0.7,
        bass_mono_below_hz=100,
        transient_strength_target=0.5,
        bpm_min=128,
        bpm_max=140
    ),

    'dnb': GenrePreset(
        name='Drum & Bass',
        description='High-energy DnB with rolling breaks and heavy sub bass',
        target_lufs=-14.0,
        club_lufs=-8.0,
        crest_factor_min=10.0,
        crest_factor_max=16.0,
        sub_bass_pct=(12, 20),
        bass_pct=(18, 28),
        low_mid_pct=(8, 12),
        mid_pct=(18, 25),
        high_mid_pct=(15, 22),
        high_pct=(10, 16),
        correlation_min=0.25,
        correlation_max=0.55,
        bass_mono_below_hz=150,
        transient_strength_target=0.55,
        bpm_min=170,
        bpm_max=180
    ),

    'progressive': GenrePreset(
        name='Progressive House/Trance',
        description='Melodic progressive with long builds and subtle transitions',
        target_lufs=-14.0,
        club_lufs=-10.0,
        crest_factor_min=10.0,
        crest_factor_max=14.0,
        sub_bass_pct=(6, 12),
        bass_pct=(22, 30),
        low_mid_pct=(10, 15),
        mid_pct=(20, 28),
        high_mid_pct=(14, 20),
        high_pct=(10, 16),
        correlation_min=0.3,
        correlation_max=0.55,
        bass_mono_below_hz=140,
        transient_strength_target=0.35,
        bpm_min=122,
        bpm_max=132
    )
}


def get_preset(genre: str) -> Optional[GenrePreset]:
    """Get a genre preset by name (case-insensitive)."""
    return GENRE_PRESETS.get(genre.lower())


def list_presets() -> Dict[str, str]:
    """List all available presets with descriptions."""
    return {name: preset.description for name, preset in GENRE_PRESETS.items()}


def get_frequency_targets(genre: str) -> Optional[Dict[str, tuple]]:
    """Get frequency band targets for a genre."""
    preset = get_preset(genre)
    if not preset:
        return None

    return {
        'sub_bass': preset.sub_bass_pct,
        'bass': preset.bass_pct,
        'low_mid': preset.low_mid_pct,
        'mid': preset.mid_pct,
        'high_mid': preset.high_mid_pct,
        'high': preset.high_pct
    }


def check_against_preset(
    genre: str,
    frequency_data: Dict[str, float],
    loudness_lufs: float,
    crest_factor: float,
    correlation: float
) -> Dict[str, Dict]:
    """
    Check analysis values against genre preset targets.

    Returns dict with each parameter and its status (ok/warning/critical).
    """
    preset = get_preset(genre)
    if not preset:
        return {}

    results = {}

    # Check frequency bands
    band_mapping = {
        'sub_bass': ('sub_bass_energy', preset.sub_bass_pct),
        'bass': ('bass_energy', preset.bass_pct),
        'low_mid': ('low_mid_energy', preset.low_mid_pct),
        'mid': ('mid_energy', preset.mid_pct),
        'high_mid': ('high_mid_energy', preset.high_mid_pct),
        'high': ('high_energy', preset.high_pct)
    }

    for band_name, (data_key, (target_min, target_max)) in band_mapping.items():
        value = frequency_data.get(data_key, 0)
        if value < target_min * 0.5:
            status = 'critical'
            message = f"Way too low ({value:.1f}%, target: {target_min}-{target_max}%)"
        elif value < target_min:
            status = 'warning'
            message = f"Slightly low ({value:.1f}%, target: {target_min}-{target_max}%)"
        elif value > target_max * 1.5:
            status = 'critical'
            message = f"Way too high ({value:.1f}%, target: {target_min}-{target_max}%)"
        elif value > target_max:
            status = 'warning'
            message = f"Slightly high ({value:.1f}%, target: {target_min}-{target_max}%)"
        else:
            status = 'ok'
            message = f"Good ({value:.1f}%, target: {target_min}-{target_max}%)"

        results[band_name] = {'status': status, 'message': message, 'value': value}

    # Check loudness
    lufs_diff = abs(loudness_lufs - preset.target_lufs)
    if lufs_diff > 6:
        results['loudness'] = {
            'status': 'critical',
            'message': f"LUFS: {loudness_lufs:.1f} (target: {preset.target_lufs} for {preset.name})",
            'value': loudness_lufs
        }
    elif lufs_diff > 3:
        results['loudness'] = {
            'status': 'warning',
            'message': f"LUFS: {loudness_lufs:.1f} (target: {preset.target_lufs} for {preset.name})",
            'value': loudness_lufs
        }
    else:
        results['loudness'] = {
            'status': 'ok',
            'message': f"LUFS: {loudness_lufs:.1f} (target: {preset.target_lufs})",
            'value': loudness_lufs
        }

    # Check crest factor
    if crest_factor < preset.crest_factor_min:
        results['crest_factor'] = {
            'status': 'warning',
            'message': f"Over-compressed ({crest_factor:.1f}dB, target: {preset.crest_factor_min}-{preset.crest_factor_max}dB)",
            'value': crest_factor
        }
    elif crest_factor > preset.crest_factor_max:
        results['crest_factor'] = {
            'status': 'warning',
            'message': f"Very dynamic ({crest_factor:.1f}dB, target: {preset.crest_factor_min}-{preset.crest_factor_max}dB)",
            'value': crest_factor
        }
    else:
        results['crest_factor'] = {
            'status': 'ok',
            'message': f"Good dynamics ({crest_factor:.1f}dB)",
            'value': crest_factor
        }

    # Check correlation
    if correlation < preset.correlation_min:
        results['correlation'] = {
            'status': 'critical' if correlation < 0 else 'warning',
            'message': f"Too wide/phase issues ({correlation:.2f}, min: {preset.correlation_min})",
            'value': correlation
        }
    elif correlation > preset.correlation_max:
        results['correlation'] = {
            'status': 'warning',
            'message': f"Too narrow ({correlation:.2f}, max: {preset.correlation_max})",
            'value': correlation
        }
    else:
        results['correlation'] = {
            'status': 'ok',
            'message': f"Good stereo width ({correlation:.2f})",
            'value': correlation
        }

    return results
