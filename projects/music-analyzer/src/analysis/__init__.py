"""
Gap Analysis Module.

Compare WIP tracks against reference profiles to identify production gaps.

Components:
- GapAnalyzer: Main analysis engine
- DeltaReporter: Human-readable report generation
- Prioritization: Issue ranking by importance

Usage:
    from analysis import GapAnalyzer
    from profiling import ReferenceProfile

    profile = ReferenceProfile.load("trance_profile.json")
    analyzer = GapAnalyzer(profile)
    report = analyzer.analyze("my_wip_track.wav")
    print(report.format_summary())
"""

from .gap_analyzer import GapAnalyzer, FeatureGap, GapReport
from .delta_reporter import (
    format_gap_report,
    format_summary_report,
    format_detailed_report
)

__all__ = [
    'GapAnalyzer',
    'FeatureGap',
    'GapReport',
    'format_gap_report',
    'format_summary_report',
    'format_detailed_report',
]
