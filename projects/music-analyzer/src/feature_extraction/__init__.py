"""
Trance-specific feature extraction module.

This module provides specialized feature extractors for analyzing trance music:
- Sidechain pumping detection
- TB-303 acid bassline detection
- Supersaw stereo spread analysis
- Energy curve extraction
- Tempo and rhythm analysis
- Composite trance scoring

Usage:
    from feature_extraction import extract_all_trance_features, TranceScoreCalculator

    features = extract_all_trance_features("track.wav")
    scorer = TranceScoreCalculator()
    score, breakdown = scorer.compute_total_score(features)
"""

from .pumping_detector import extract_pumping_features
from .acid_detector import compute_303_score, extract_acid_features
from .supersaw_analyzer import analyze_supersaw_characteristics
from .energy_curves import extract_energy_curves, detect_drops
from .rhythm_analyzer import (
    detect_trance_tempo,
    detect_four_on_floor,
    detect_offbeat_hihats
)
from .trance_scorer import TranceScoreCalculator
from .trance_features import extract_all_trance_features

__all__ = [
    # Pumping detection
    'extract_pumping_features',

    # 303/Acid detection
    'compute_303_score',
    'extract_acid_features',

    # Supersaw analysis
    'analyze_supersaw_characteristics',

    # Energy curves
    'extract_energy_curves',
    'detect_drops',

    # Rhythm analysis
    'detect_trance_tempo',
    'detect_four_on_floor',
    'detect_offbeat_hihats',

    # Scoring
    'TranceScoreCalculator',

    # Main entry point
    'extract_all_trance_features',
]
