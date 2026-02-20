"""
Ableton AI Analysis - Music Production Analysis Tool

A comprehensive tool for analyzing Ableton 11 projects and audio files
to provide actionable mixing and mastering recommendations.
"""

__version__ = "1.2.0"  # Added Phase 4 (Embeddings) and Phase 5 (Prescriptive Fixes)
__author__ = "AI Music Production Assistant"

try:
    from .audio_analyzer import AudioAnalyzer
    from .stem_analyzer import StemAnalyzer
    from .als_parser import ALSParser
    from .mastering import MasteringEngine
    from .reporter import ReportGenerator
    from .stem_separator import StemSeparator, StemType, StemSeparationResult
    from .reference_storage import ReferenceStorage, ReferenceAnalytics, TrackMetadata
    from .reference_comparator import ReferenceComparator, ComparisonResult
    # Extended analyzers (merged from ai-music-mix-analyzer)
    from .analyzers import (
        HarmonicAnalyzer, HarmonicInfo,
        ClarityAnalyzer, ClarityInfo,
        SpatialAnalyzer, SpatialInfo, SurroundInfo, PlaybackInfo,
        OverallScoreCalculator, OverallScoreInfo,
    )
    from .music_theory import (
        KEYS, MAJOR_KEYS, MINOR_KEYS, ALL_KEYS,
        CIRCLE_OF_FIFTHS, RELATIVE_MINOR, RELATIVE_MAJOR,
        get_key_relationship_info, get_parallel_key, get_neighboring_keys,
    )
except ImportError:
    from audio_analyzer import AudioAnalyzer
    from stem_analyzer import StemAnalyzer
    from als_parser import ALSParser
    from mastering import MasteringEngine
    from reporter import ReportGenerator
    from stem_separator import StemSeparator, StemType, StemSeparationResult
    from reference_storage import ReferenceStorage, ReferenceAnalytics, TrackMetadata
    from reference_comparator import ReferenceComparator, ComparisonResult
    # Extended analyzers may not be available in all import contexts
    try:
        from analyzers import (
            HarmonicAnalyzer, HarmonicInfo,
            ClarityAnalyzer, ClarityInfo,
            SpatialAnalyzer, SpatialInfo, SurroundInfo, PlaybackInfo,
            OverallScoreCalculator, OverallScoreInfo,
        )
        from music_theory import (
            KEYS, MAJOR_KEYS, MINOR_KEYS, ALL_KEYS,
            CIRCLE_OF_FIFTHS, RELATIVE_MINOR, RELATIVE_MAJOR,
            get_key_relationship_info, get_parallel_key, get_neighboring_keys,
        )
    except ImportError:
        pass  # Extended analyzers not available
