"""Feature extraction module for audio analysis."""

from .rhythm_extractor import (
    RhythmFeatures,
    extract_rhythm,
    detect_tempo_changes,
    get_downbeats,
    calculate_groove_stability
)

from .key_extractor import (
    KeyFeatures,
    extract_key,
    extract_key_over_time,
    key_to_camelot,
    key_to_open_key,
    get_compatible_keys,
    format_key_display
)

from .loudness_analyzer import (
    LoudnessFeatures,
    extract_loudness,
    calculate_short_term_loudness,
    get_loudness_over_time,
    format_loudness_display
)

from .spectral_analyzer import (
    SpectralFeatures,
    extract_spectral_features,
    get_spectral_profile_over_time,
    format_spectral_display,
    FREQUENCY_BANDS
)

from .stereo_analyzer import (
    StereoFeatures,
    extract_stereo_features,
    get_stereo_over_time,
    format_stereo_display
)

from .feature_pipeline import (
    AllFeatures,
    extract_all_features,
    format_all_features
)


__all__ = [
    # Rhythm
    'RhythmFeatures',
    'extract_rhythm',
    'detect_tempo_changes',
    'get_downbeats',
    'calculate_groove_stability',
    # Key
    'KeyFeatures',
    'extract_key',
    'extract_key_over_time',
    'key_to_camelot',
    'key_to_open_key',
    'get_compatible_keys',
    'format_key_display',
    # Loudness
    'LoudnessFeatures',
    'extract_loudness',
    'calculate_short_term_loudness',
    'get_loudness_over_time',
    'format_loudness_display',
    # Spectral
    'SpectralFeatures',
    'extract_spectral_features',
    'get_spectral_profile_over_time',
    'format_spectral_display',
    'FREQUENCY_BANDS',
    # Stereo
    'StereoFeatures',
    'extract_stereo_features',
    'get_stereo_over_time',
    'format_stereo_display',
    # Pipeline
    'AllFeatures',
    'extract_all_features',
    'format_all_features',
]
