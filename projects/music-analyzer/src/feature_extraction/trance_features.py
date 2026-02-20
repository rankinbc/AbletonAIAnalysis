"""
Main Trance Feature Extraction Entry Point.

Orchestrates all trance-specific feature extractors and provides
a unified interface for extracting all features from an audio file.

Usage:
    from feature_extraction import extract_all_trance_features, TranceScoreCalculator

    features = extract_all_trance_features("track.wav")
    scorer = TranceScoreCalculator()
    score, breakdown = scorer.compute_total_score(features)
    print(scorer.format_score_report(score, breakdown))
"""

import numpy as np
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
import librosa

from .pumping_detector import extract_pumping_features, compute_pumping_score
from .acid_detector import extract_acid_features
from .supersaw_analyzer import analyze_supersaw_characteristics, compute_supersaw_score
from .energy_curves import extract_energy_curves, detect_drops, compute_energy_progression_score
from .rhythm_analyzer import analyze_rhythm
from .trance_scorer import TranceScoreCalculator, TranceScoreBreakdown


@dataclass
class TranceFeatures:
    """Complete trance feature extraction results."""
    # Pumping/Sidechain
    pumping_modulation_depth_db: float
    pumping_modulation_depth_linear: float
    pumping_regularity: float
    pumping_score: float

    # 303/Acid
    acid_filter_sweep_score: float
    acid_resonance_score: float
    acid_glide_score: float
    acid_accent_score: float
    acid_303_score: float

    # Supersaw/Stereo
    stereo_width: float
    phase_correlation: float
    detuning_detected: bool
    estimated_voices: int
    supersaw_score: float

    # Energy
    energy_range: float
    energy_std: float
    avg_energy: float
    num_drops: int
    energy_progression: float

    # Rhythm
    tempo: float
    tempo_stability: float
    tempo_score: float
    is_trance_tempo: bool
    four_on_floor_strength: float
    four_on_floor_score: float
    offbeat_hihat_strength: float
    offbeat_hihat_score: float

    # Spectral
    spectral_brightness: float

    # Overall
    trance_score: float
    trance_score_breakdown: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        return result


def extract_all_trance_features(
    audio_path_or_data,
    sr: Optional[int] = None,
    hop_length: int = 512,
    include_time_series: bool = False,
    verbose: bool = False
) -> TranceFeatures:
    """
    Extract all trance-specific features from an audio file.

    This is the main entry point for trance feature extraction.
    It runs all extractors and computes the composite trance score.

    Args:
        audio_path_or_data: Path to audio file or numpy array
        sr: Sample rate (required if array provided)
        hop_length: Hop length for analysis
        include_time_series: If True, include time-varying features
        verbose: If True, print progress

    Returns:
        TranceFeatures dataclass with all extracted features
    """
    # Load audio once for reuse
    if isinstance(audio_path_or_data, str):
        if verbose:
            print(f"Loading audio: {audio_path_or_data}")
        # Load mono for most analysis
        y_mono, sr = librosa.load(audio_path_or_data, sr=None, mono=True)
        # Load stereo for supersaw analysis
        y_stereo, _ = librosa.load(audio_path_or_data, sr=sr, mono=False)
    else:
        if sr is None:
            raise ValueError("sr must be provided when passing audio array")
        if len(audio_path_or_data.shape) == 1:
            y_mono = audio_path_or_data
            y_stereo = np.vstack([audio_path_or_data, audio_path_or_data])
        else:
            y_mono = np.mean(audio_path_or_data, axis=0)
            y_stereo = audio_path_or_data

    # 1. Extract pumping features
    if verbose:
        print("Analyzing sidechain pumping...")
    pumping = extract_pumping_features(y_mono, sr=sr, hop_length=hop_length)
    pumping_score = compute_pumping_score(pumping)

    # 2. Extract acid features
    if verbose:
        print("Analyzing acid/303 characteristics...")
    acid = extract_acid_features(y_mono, sr=sr, hop_length=hop_length)

    # 3. Extract supersaw features
    if verbose:
        print("Analyzing stereo spread...")
    supersaw = analyze_supersaw_characteristics(
        y_stereo, sr=sr, hop_length=hop_length,
        return_time_series=include_time_series
    )
    supersaw_score = compute_supersaw_score(supersaw)

    # 4. Extract energy features
    if verbose:
        print("Analyzing energy progression...")
    energy = extract_energy_curves(y_mono, sr=sr, hop_length=hop_length)
    drops = detect_drops(energy)
    energy_progression_score = compute_energy_progression_score(energy)

    # 5. Extract rhythm features
    if verbose:
        print("Analyzing rhythm and tempo...")
    rhythm = analyze_rhythm(y_mono, sr=sr, hop_length=hop_length)

    # 6. Compute spectral brightness
    if verbose:
        print("Analyzing spectral characteristics...")
    centroid = librosa.feature.spectral_centroid(y=y_mono, sr=sr, hop_length=hop_length)
    avg_centroid = float(np.mean(centroid))
    # Normalize to 0-1 score (2000-5000 Hz is bright for trance)
    brightness_score = np.clip((avg_centroid - 1000) / 4000, 0.0, 1.0)

    # 7. Compute overall trance score
    if verbose:
        print("Computing trance score...")

    scorer = TranceScoreCalculator()
    score_features = {
        'tempo_score': rhythm.tempo_score,
        'pumping_score': pumping_score,
        'energy_progression': energy_progression_score,
        'four_on_floor': rhythm.four_on_floor_score,
        'supersaw_score': supersaw_score,
        'acid_303_score': acid.overall_303_score,
        'offbeat_hihat': rhythm.offbeat_hihat_score,
        'spectral_brightness': brightness_score,
        'tempo_stability': rhythm.tempo.tempo_stability
    }

    trance_score, breakdown = scorer.compute_total_score(score_features)

    return TranceFeatures(
        # Pumping
        pumping_modulation_depth_db=pumping.modulation_depth_db,
        pumping_modulation_depth_linear=pumping.modulation_depth_linear,
        pumping_regularity=pumping.pumping_regularity,
        pumping_score=pumping_score,

        # Acid
        acid_filter_sweep_score=acid.filter_sweep_score,
        acid_resonance_score=acid.resonance_score,
        acid_glide_score=acid.glide_score,
        acid_accent_score=acid.accent_score,
        acid_303_score=acid.overall_303_score,

        # Supersaw
        stereo_width=supersaw.stereo_width,
        phase_correlation=supersaw.phase_correlation,
        detuning_detected=supersaw.detuning_detected,
        estimated_voices=supersaw.estimated_voices,
        supersaw_score=supersaw_score,

        # Energy
        energy_range=energy.energy_range,
        energy_std=energy.energy_std,
        avg_energy=energy.avg_energy,
        num_drops=len(drops),
        energy_progression=energy_progression_score,

        # Rhythm
        tempo=rhythm.tempo.tempo,
        tempo_stability=rhythm.tempo.tempo_stability,
        tempo_score=rhythm.tempo_score,
        is_trance_tempo=rhythm.tempo.is_trance_tempo,
        four_on_floor_strength=rhythm.kicks.strength,
        four_on_floor_score=rhythm.four_on_floor_score,
        offbeat_hihat_strength=rhythm.hihats.offbeat_strength,
        offbeat_hihat_score=rhythm.offbeat_hihat_score,

        # Spectral
        spectral_brightness=brightness_score,

        # Overall
        trance_score=trance_score,
        trance_score_breakdown=breakdown.to_dict()
    )


def format_trance_features_report(features: TranceFeatures) -> str:
    """
    Format trance features as a human-readable report.

    Args:
        features: TranceFeatures from extract_all_trance_features

    Returns:
        Formatted string report
    """
    def bar(score: float, width: int = 10) -> str:
        filled = int(score * width)
        return '=' * filled + ' ' * (width - filled)

    lines = [
        "=" * 60,
        "TRANCE DNA ANALYSIS REPORT",
        "=" * 60,
        "",
        f"Overall Trance Score: {features.trance_score:.2f} / 1.00",
        "",
        "-" * 40,
        "RHYTHM & TEMPO",
        "-" * 40,
        f"  Tempo: {features.tempo:.1f} BPM {'[TRANCE RANGE]' if features.is_trance_tempo else ''}",
        f"  Tempo Score:      {features.tempo_score:.2f}  [{bar(features.tempo_score)}]",
        f"  Tempo Stability:  {features.tempo_stability:.2f}  [{bar(features.tempo_stability)}]",
        f"  4-on-the-Floor:   {features.four_on_floor_score:.2f}  [{bar(features.four_on_floor_score)}]",
        f"  Off-beat Hihats:  {features.offbeat_hihat_score:.2f}  [{bar(features.offbeat_hihat_score)}]",
        "",
        "-" * 40,
        "SIDECHAIN & PUMPING",
        "-" * 40,
        f"  Modulation Depth: {features.pumping_modulation_depth_db:.1f} dB",
        f"  Regularity:       {features.pumping_regularity:.3f} (lower = more consistent)",
        f"  Pumping Score:    {features.pumping_score:.2f}  [{bar(features.pumping_score)}]",
        "",
        "-" * 40,
        "STEREO & SUPERSAW",
        "-" * 40,
        f"  Stereo Width:     {features.stereo_width:.2f}  [{bar(features.stereo_width)}]",
        f"  Phase Correlation: {features.phase_correlation:.2f}",
        f"  Detuning Detected: {'Yes' if features.detuning_detected else 'No'}",
        f"  Est. Voices:      {features.estimated_voices}",
        f"  Supersaw Score:   {features.supersaw_score:.2f}  [{bar(features.supersaw_score)}]",
        "",
        "-" * 40,
        "303 ACID ELEMENTS",
        "-" * 40,
        f"  Filter Sweep:     {features.acid_filter_sweep_score:.2f}  [{bar(features.acid_filter_sweep_score)}]",
        f"  Resonance:        {features.acid_resonance_score:.2f}  [{bar(features.acid_resonance_score)}]",
        f"  Pitch Glides:     {features.acid_glide_score:.2f}  [{bar(features.acid_glide_score)}]",
        f"  Accents:          {features.acid_accent_score:.2f}  [{bar(features.acid_accent_score)}]",
        f"  Overall 303:      {features.acid_303_score:.2f}  [{bar(features.acid_303_score)}]",
        "",
        "-" * 40,
        "ENERGY PROGRESSION",
        "-" * 40,
        f"  Energy Range:     {features.energy_range:.2f}",
        f"  Energy Std Dev:   {features.energy_std:.3f}",
        f"  Drops Detected:   {features.num_drops}",
        f"  Progression Score: {features.energy_progression:.2f}  [{bar(features.energy_progression)}]",
        "",
        "-" * 40,
        "SPECTRAL",
        "-" * 40,
        f"  Brightness Score: {features.spectral_brightness:.2f}  [{bar(features.spectral_brightness)}]",
        "",
        "=" * 60,
        "SCORE BREAKDOWN",
        "=" * 60,
    ]

    # Add breakdown
    breakdown = features.trance_score_breakdown
    weights = TranceScoreCalculator.WEIGHTS
    for key, score in breakdown.items():
        weight = weights.get(key, 0.0)
        contrib = score * weight
        name = key.replace('_', ' ').title()
        lines.append(f"  {name:20} {score:.2f} x {weight:.2f} = {contrib:.3f}")

    lines.append("")
    lines.append("=" * 60)

    return '\n'.join(lines)


def quick_trance_score(audio_path: str, verbose: bool = False) -> float:
    """
    Quickly compute just the trance score without full feature extraction.

    Args:
        audio_path: Path to audio file
        verbose: Print progress

    Returns:
        Trance score (0-1)
    """
    features = extract_all_trance_features(audio_path, verbose=verbose)
    return features.trance_score
