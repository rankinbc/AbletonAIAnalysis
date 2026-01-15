"""
Configuration loader for Music Analyzer.

Loads settings from config.yaml and provides defaults.
Supports environment variable overrides.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
import yaml


# Default configuration - matches config.yaml structure
DEFAULT_CONFIG = {
    'stages': {
        'audio_analysis': True,
        'section_analysis': True,
        'clipping_detection': True,
        'stem_separation': False,
        'stem_analysis': True,
        'reference_comparison': True,
        'als_parsing': True,
        'dynamics_analysis': True,
        'frequency_analysis': True,
        'stereo_analysis': True,
        'loudness_analysis': True,
        'transient_analysis': True,
        'tempo_detection': True,
        'midi_humanization': False,
        'midi_quantization': False,
        'midi_chord_detection': False,
        'ai_mastering': False,
    },
    'report': {
        'format': 'html',
        'include_visualizations': True,
        'include_recommendations': True,
        'max_issues_per_category': 20,
        'timestamp_precision': 2,
        'show_platform_loudness': True,
        'show_frequency_bands': True,
        'show_stem_details': True,
        'show_midi_details': False,
    },
    'clipping': {
        'threshold': 0.99,
        'group_window_seconds': 0.1,
        'max_report_positions': 50,
        'severity_minor_threshold': 100,
        'severity_moderate_threshold': 1000,
    },
    'dynamics': {
        'crest_very_dynamic_threshold': 18.0,
        'crest_good_threshold': 12.0,
        'crest_compressed_threshold': 8.0,
        'over_compression_threshold': 6.0,
        'target_crest_factor': 12.0,
    },
    'frequency': {
        'fft_window_size': 4096,
        'bands': {
            'sub_bass': [20, 60],
            'bass': [60, 250],
            'low_mid': [250, 500],
            'mid': [500, 2000],
            'high_mid': [2000, 6000],
            'high': [6000, 20000],
        },
        'bass_excessive_threshold': 45,
        'bass_lacking_threshold': 15,
        'low_mid_buildup_threshold': 25,
        'high_lacking_threshold': 5,
        'high_excessive_threshold': 25,
        'centroid_dark_threshold': 1000,
        'centroid_bright_threshold': 4000,
        'muddy_range': [200, 500],
        'muddy_ratio_threshold': 0.25,
        'muddy_severe_threshold': 0.4,
        'muddy_moderate_threshold': 0.3,
        'harsh_range': [3000, 8000],
        'harsh_ratio_threshold': 0.35,
        'sub_bass_range': [20, 60],
        'sub_bass_weak_threshold': 0.05,
    },
    'stereo': {
        'mono_threshold': 0.95,
        'narrow_threshold': 0.7,
        'good_threshold': 0.3,
        'wide_threshold': 0.0,
        'mono_compatibility_threshold': 0.3,
    },
    'loudness': {
        'platforms': {
            'spotify': -14.0,
            'apple_music': -16.0,
            'youtube': -14.0,
            'tidal': -14.0,
            'amazon': -14.0,
            'soundcloud': -14.0,
        },
        'reference_loudness': -14.0,
        'hop_length_seconds': 0.1,
        'frame_length_seconds': 0.4,
        'short_term_window_seconds': 3.0,
        'warning_lower_threshold': -6,
        'warning_upper_threshold': 2,
        'true_peak_warning_threshold': -1.0,
    },
    'transients': {
        'punchy_threshold': 0.7,
        'average_threshold': 0.4,
        'max_positions_to_store': 20,
    },
    'sections': {
        'min_section_length_seconds': 15.0,
        'fixed_segment_length_seconds': 30.0,
        'detection_weights': {
            'rms_energy': 0.5,
            'onset_density': 0.3,
            'spectral_centroid': 0.2,
        },
        'novelty_smoothing_window_seconds': 2,
        'novelty_threshold_std_multiplier': 0.5,
        'intro_position_threshold': 0.1,
        'outro_position_threshold': 0.9,
        'drop_energy_threshold_db': -15,
        'drop_transient_density_threshold': 2.0,
        'drop_bass_ratio_threshold': 0.3,
        'breakdown_energy_threshold_db': -20,
        'breakdown_transient_density_threshold': 1.5,
        'buildup_transient_density_threshold': 1.0,
        'clipping_group_window': 0.1,
        'clipping_minor_threshold': 100,
        'clipping_severe_threshold': 500,
        'min_dynamic_range_db': 4,
    },
    'stems': {
        'fft_size': 4096,
        'bands': {
            'sub': [20, 60],
            'bass': [60, 200],
            'low_mid': [200, 500],
            'mid': [500, 2000],
            'high_mid': [2000, 6000],
            'high': [6000, 16000],
            'air': [16000, 20000],
        },
        'clash_overlap_threshold': 0.3,
        'clash_min_overlap_amount': 0.1,
        'clash_severe_threshold': 0.5,
        'clash_moderate_threshold': 0.3,
        'balance_too_loud_threshold': 6,
        'balance_too_quiet_threshold': 12,
        'masking_level_diff_threshold': 10,
        'masking_freq_overlap_threshold': 0.3,
        'masking_loud_energy_threshold': 0.5,
        'panning_center_threshold': 0.7,
        'bass_heavy_energy_threshold': 0.2,
    },
    'reference': {
        'fft_window_size': 4096,
        'spectrum_visualization_points': 256,
        'bands': {
            'bass': [20, 250],
            'low_mid': [250, 500],
            'mid': [500, 2000],
            'high_mid': [2000, 6000],
            'high': [6000, 20000],
        },
        'loudness_threshold_db': 2.0,
        'stereo_width_threshold_pct': 15,
        'frequency_threshold_pct': 8,
        'spectral_centroid_threshold_hz': 200,
        'balance_score_loudness_penalty': 2,
        'balance_score_freq_penalty': 10,
        'balance_score_width_penalty': 5,
    },
    'midi': {
        'quantization_detection_threshold': 0.01,
        'quantization_severe_threshold': 0.1,
        'quantization_notable_threshold': 0.03,
        'humanization_robotic_std': 5,
        'humanization_slight_std': 15,
        'chord_time_threshold_beats': 0.05,
        'chord_min_note_count': 3,
        'swing_min_note_count': 10,
        'swing_offbeat_lower_bound': 0.3,
        'swing_offbeat_upper_bound': 0.75,
    },
    'mastering': {
        'peak_limiting_threshold': 0.99,
        'k_weighting_constant': 0.691,
        'lufs_estimation_failure_default': -24.0,
    },
    'defaults': {
        'sample_rate_hz': 44100,
        'tempo_bpm': 140,
        'project_duration_beats': 16,
    },
}


def deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries, override takes precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@dataclass
class AnalyzerConfig:
    """Configuration container with convenient accessors."""

    _config: Dict = field(default_factory=dict)
    _config_path: Optional[Path] = None

    def __post_init__(self):
        if not self._config:
            self._config = DEFAULT_CONFIG.copy()

    def get(self, *keys: str, default: Any = None) -> Any:
        """Get a nested config value using dot notation or multiple keys.

        Examples:
            config.get('stages', 'audio_analysis')
            config.get('clipping', 'threshold')
        """
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access to top-level config sections."""
        return self._config.get(key, {})

    # Convenience properties for stages
    @property
    def stages(self) -> Dict[str, bool]:
        return self._config.get('stages', {})

    def stage_enabled(self, stage_name: str) -> bool:
        """Check if a specific stage is enabled."""
        return self.stages.get(stage_name, True)

    # Shorthand accessors for common sections
    @property
    def clipping(self) -> Dict:
        return self._config.get('clipping', {})

    @property
    def dynamics(self) -> Dict:
        return self._config.get('dynamics', {})

    @property
    def frequency(self) -> Dict:
        return self._config.get('frequency', {})

    @property
    def stereo(self) -> Dict:
        return self._config.get('stereo', {})

    @property
    def loudness(self) -> Dict:
        return self._config.get('loudness', {})

    @property
    def transients(self) -> Dict:
        return self._config.get('transients', {})

    @property
    def sections(self) -> Dict:
        return self._config.get('sections', {})

    @property
    def stems(self) -> Dict:
        return self._config.get('stems', {})

    @property
    def reference(self) -> Dict:
        return self._config.get('reference', {})

    @property
    def midi(self) -> Dict:
        return self._config.get('midi', {})

    @property
    def mastering(self) -> Dict:
        return self._config.get('mastering', {})

    @property
    def defaults(self) -> Dict:
        return self._config.get('defaults', {})

    @property
    def report(self) -> Dict:
        return self._config.get('report', {})

    def to_dict(self) -> Dict:
        """Return the full config as a dictionary."""
        return self._config.copy()


# Global config instance
_config: Optional[AnalyzerConfig] = None


def load_config(config_path: Optional[str] = None) -> AnalyzerConfig:
    """
    Load configuration from YAML file.

    Search order:
    1. Explicit path if provided
    2. ANALYZER_CONFIG environment variable
    3. config.yaml in music-analyzer directory
    4. Default config

    Args:
        config_path: Optional explicit path to config file

    Returns:
        AnalyzerConfig instance
    """
    global _config

    # Determine config file path
    if config_path:
        cfg_path = Path(config_path)
    elif os.environ.get('ANALYZER_CONFIG'):
        cfg_path = Path(os.environ['ANALYZER_CONFIG'])
    else:
        # Look for config.yaml relative to this file
        cfg_path = Path(__file__).parent.parent / 'config.yaml'

    config_data = DEFAULT_CONFIG.copy()

    if cfg_path.exists():
        try:
            with open(cfg_path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f) or {}

            # Merge user config over defaults
            config_data = deep_merge(DEFAULT_CONFIG, user_config)

        except Exception as e:
            print(f"Warning: Could not load config from {cfg_path}: {e}")
            print("Using default configuration.")

    # Apply environment variable overrides
    # Format: ANALYZER_<SECTION>_<KEY>=value
    # Example: ANALYZER_CLIPPING_THRESHOLD=0.98
    for env_key, env_value in os.environ.items():
        if env_key.startswith('ANALYZER_'):
            parts = env_key[9:].lower().split('_', 1)
            if len(parts) == 2:
                section, key = parts
                if section in config_data and key in config_data[section]:
                    try:
                        # Try to cast to the same type as default
                        original_type = type(config_data[section][key])
                        if original_type == bool:
                            config_data[section][key] = env_value.lower() in ('true', '1', 'yes')
                        else:
                            config_data[section][key] = original_type(env_value)
                    except (ValueError, TypeError):
                        pass

    _config = AnalyzerConfig(_config=config_data, _config_path=cfg_path)
    return _config


def get_config() -> AnalyzerConfig:
    """Get the current config instance, loading if necessary."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config(config_path: Optional[str] = None) -> AnalyzerConfig:
    """Force reload the configuration."""
    global _config
    _config = None
    return load_config(config_path)


# Convenience function for quick access
def cfg(*keys: str, default: Any = None) -> Any:
    """Quick access to config values.

    Example:
        cfg('clipping', 'threshold')  # Returns 0.99
        cfg('stages', 'stem_separation')  # Returns False
    """
    return get_config().get(*keys, default=default)
