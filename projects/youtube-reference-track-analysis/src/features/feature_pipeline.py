"""
Feature extraction pipeline that orchestrates all feature extractors.

Provides a single entry point for extracting all features from an audio file.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable
import time

from .rhythm_extractor import RhythmFeatures, extract_rhythm
from .key_extractor import KeyFeatures, extract_key, format_key_display
from .loudness_analyzer import LoudnessFeatures, extract_loudness
from .spectral_analyzer import SpectralFeatures, extract_spectral_features
from .stereo_analyzer import StereoFeatures, extract_stereo_features


@dataclass
class AllFeatures:
    """Combined features from all extractors."""
    rhythm: Optional[RhythmFeatures] = None
    key: Optional[KeyFeatures] = None
    loudness: Optional[LoudnessFeatures] = None
    spectral: Optional[SpectralFeatures] = None
    stereo: Optional[StereoFeatures] = None

    # Extraction metadata
    extraction_time_sec: float = 0.0
    errors: list = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def extract_all_features(
    audio_path: Path,
    progress_callback: Optional[Callable[[str], None]] = None,
    skip_slow: bool = False
) -> AllFeatures:
    """
    Extract all features from an audio file.

    Args:
        audio_path: Path to audio file
        progress_callback: Optional callback for progress updates
        skip_slow: If True, skip slower extractors (spectral)

    Returns:
        AllFeatures with all extracted data
    """
    audio_path = Path(audio_path)
    start_time = time.time()
    errors = []

    def update_progress(msg: str):
        if progress_callback:
            progress_callback(msg)

    # Rhythm extraction (BPM, beats)
    update_progress("Extracting rhythm features...")
    try:
        rhythm = extract_rhythm(audio_path)
        if not rhythm:
            errors.append("Rhythm extraction returned no data")
    except ImportError as e:
        errors.append(f"Rhythm: {str(e)}")
        rhythm = None
    except Exception as e:
        errors.append(f"Rhythm: {str(e)}")
        rhythm = None

    # Key extraction
    update_progress("Extracting key features...")
    try:
        key = extract_key(audio_path)
        if not key:
            errors.append("Key extraction returned no data")
    except ImportError as e:
        errors.append(f"Key: {str(e)}")
        key = None
    except Exception as e:
        errors.append(f"Key: {str(e)}")
        key = None

    # Loudness extraction
    update_progress("Extracting loudness features...")
    try:
        loudness = extract_loudness(audio_path)
        if not loudness:
            errors.append("Loudness extraction returned no data")
    except ImportError as e:
        errors.append(f"Loudness: {str(e)}")
        loudness = None
    except Exception as e:
        errors.append(f"Loudness: {str(e)}")
        loudness = None

    # Spectral extraction (can be slow)
    if not skip_slow:
        update_progress("Extracting spectral features...")
        try:
            spectral = extract_spectral_features(audio_path)
            if not spectral:
                errors.append("Spectral extraction returned no data")
        except ImportError as e:
            errors.append(f"Spectral: {str(e)}")
            spectral = None
        except Exception as e:
            errors.append(f"Spectral: {str(e)}")
            spectral = None
    else:
        spectral = None

    # Stereo extraction
    update_progress("Extracting stereo features...")
    try:
        stereo = extract_stereo_features(audio_path)
        if not stereo:
            errors.append("Stereo extraction returned no data")
    except ImportError as e:
        errors.append(f"Stereo: {str(e)}")
        stereo = None
    except Exception as e:
        errors.append(f"Stereo: {str(e)}")
        stereo = None

    extraction_time = time.time() - start_time
    update_progress(f"Feature extraction complete in {extraction_time:.1f}s")

    return AllFeatures(
        rhythm=rhythm,
        key=key,
        loudness=loudness,
        spectral=spectral,
        stereo=stereo,
        extraction_time_sec=round(extraction_time, 2),
        errors=errors
    )


def format_all_features(features: AllFeatures, verbose: bool = False) -> str:
    """
    Format all features for display.

    Args:
        features: Extracted features
        verbose: Include detailed information

    Returns:
        Formatted string
    """
    lines = []

    # Quick summary line
    summary_parts = []
    if features.rhythm:
        summary_parts.append(f"{features.rhythm.bpm} BPM")
    if features.key:
        summary_parts.append(format_key_display(features.key))
    if features.loudness:
        summary_parts.append(f"{features.loudness.integrated_lufs} LUFS")

    if summary_parts:
        lines.append("Quick Summary: " + " | ".join(summary_parts))
        lines.append("")

    # Detailed sections
    if features.rhythm:
        lines.append("=" * 40)
        lines.append("RHYTHM")
        lines.append("=" * 40)
        lines.append(f"BPM: {features.rhythm.bpm} (confidence: {features.rhythm.bpm_confidence:.0%})")
        lines.append(f"Beats: {features.rhythm.beats_count}")
        lines.append(f"Danceability: {features.rhythm.danceability:.0%}")
        lines.append("")

    if features.key:
        lines.append("=" * 40)
        lines.append("KEY")
        lines.append("=" * 40)
        lines.append(f"Key: {features.key.key} {features.key.scale}")
        lines.append(f"Camelot: {features.key.camelot}")
        lines.append(f"Open Key: {features.key.open_key}")
        lines.append(f"Confidence: {features.key.key_confidence:.0%}")
        if features.key.secondary_key:
            lines.append(f"Secondary: {features.key.secondary_key} {features.key.secondary_scale} ({features.key.secondary_confidence:.0%})")
        lines.append("")

    if features.loudness:
        lines.append("=" * 40)
        lines.append("LOUDNESS")
        lines.append("=" * 40)
        lines.append(f"Integrated: {features.loudness.integrated_lufs} LUFS")
        lines.append(f"True Peak: {features.loudness.true_peak_dbtp} dBTP")
        lines.append(f"Loudness Range: {features.loudness.loudness_range_lu} LU")
        lines.append(f"Dynamic Range: {features.loudness.dynamic_range_db} dB")
        lines.append("")
        lines.append("Streaming Adjustments:")
        lines.append(f"  Spotify/YouTube ({features.loudness.spotify_gain_db:+.1f} dB)")
        lines.append(f"  Apple Music ({features.loudness.apple_gain_db:+.1f} dB)")
        lines.append("")

    if features.spectral:
        lines.append("=" * 40)
        lines.append("SPECTRAL")
        lines.append("=" * 40)
        lines.append(f"Brightness: {features.spectral.brightness_score}/100")
        lines.append(f"Bass Weight: {features.spectral.bass_weight_score}/100")
        lines.append(f"Centroid: {features.spectral.spectral_centroid_hz:.0f} Hz")
        if verbose:
            lines.append("")
            lines.append("Band Distribution:")
            lines.append(f"  Sub-bass: {features.spectral.sub_bass_pct:.1f}%")
            lines.append(f"  Bass: {features.spectral.bass_pct:.1f}%")
            lines.append(f"  Low-mid: {features.spectral.low_mid_pct:.1f}%")
            lines.append(f"  Mid: {features.spectral.mid_pct:.1f}%")
            lines.append(f"  High-mid: {features.spectral.high_mid_pct:.1f}%")
            lines.append(f"  High: {features.spectral.high_pct:.1f}%")
        lines.append("")

    if features.stereo:
        lines.append("=" * 40)
        lines.append("STEREO")
        lines.append("=" * 40)
        lines.append(f"Width: {features.stereo.stereo_width}/100")
        lines.append(f"Correlation: {features.stereo.correlation:.3f}")
        lines.append(f"Mid/Side: {features.stereo.mid_energy_pct:.0f}% / {features.stereo.side_energy_pct:.0f}%")
        if verbose:
            lines.append("")
            lines.append("Width by Frequency:")
            lines.append(f"  Low: {features.stereo.low_width:.0f}/100")
            lines.append(f"  Mid: {features.stereo.mid_width:.0f}/100")
            lines.append(f"  High: {features.stereo.high_width:.0f}/100")

        # Warnings
        if features.stereo.phase_issues:
            lines.append("")
            lines.append("WARNING: Phase issues detected!")
        if not features.stereo.mono_compatible:
            lines.append("NOTE: May lose content when summed to mono")
        lines.append("")

    # Errors
    if features.errors:
        lines.append("=" * 40)
        lines.append("EXTRACTION ISSUES")
        lines.append("=" * 40)
        for error in features.errors:
            lines.append(f"  - {error}")
        lines.append("")

    lines.append(f"Extraction time: {features.extraction_time_sec:.1f}s")

    return "\n".join(lines)
