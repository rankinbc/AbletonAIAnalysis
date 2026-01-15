"""
Extended Audio Analyzers Module

Provides additional audio analysis capabilities beyond the core analyzer:
- HarmonicAnalyzer: Key detection and harmonic content analysis
- ClarityAnalyzer: Spectral clarity and masking detection
- SpatialAnalyzer: 3D spatial, surround compatibility, and playback optimization
- OverallScoreCalculator: Weighted quality score calculation
"""

from .harmonic_analyzer import HarmonicAnalyzer, HarmonicInfo
from .clarity_analyzer import ClarityAnalyzer, ClarityInfo
from .spatial_analyzer import SpatialAnalyzer, SpatialInfo, SurroundInfo, PlaybackInfo
from .overall_score import OverallScoreCalculator, OverallScoreInfo

__all__ = [
    # Harmonic Analysis
    'HarmonicAnalyzer',
    'HarmonicInfo',
    # Clarity Analysis
    'ClarityAnalyzer',
    'ClarityInfo',
    # Spatial Analysis
    'SpatialAnalyzer',
    'SpatialInfo',
    'SurroundInfo',
    'PlaybackInfo',
    # Overall Score
    'OverallScoreCalculator',
    'OverallScoreInfo',
]
