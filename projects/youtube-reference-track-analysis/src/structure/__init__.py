"""
Structure analysis module for trance tracks.

Provides section detection, beat tracking, bar mapping, and energy analysis
for understanding track arrangements.
"""

from .section_detector import (
    SectionInfo,
    detect_sections,
    detect_sections_allin1,
    detect_sections_docker_allin1,
    detect_sections_librosa_fallback,
    map_label_to_trance,
    format_sections_display,
    get_allin1_cache_stats,
    clear_allin1_cache,
)

# Import from shared allin1 module
import sys
from pathlib import Path
_shared_path = Path(__file__).parents[3] / "shared"
if str(_shared_path) not in sys.path:
    sys.path.insert(0, str(_shared_path))

try:
    from allin1 import (
        DockerAllin1,
        Allin1Result,
        Allin1Segment,
        is_docker_available,
        is_allin1_image_available,
    )
except ImportError:
    # Fallback to local module if shared not available
    from .docker_allin1 import (
        DockerAllin1,
        Allin1Result,
        Allin1Segment,
        is_docker_available,
        is_allin1_image_available,
    )

from .beat_tracker import (
    BeatInfo,
    track_beats,
    estimate_downbeats,
    estimate_downbeats_with_energy,
    calculate_beat_confidence,
    get_beats_in_range,
    count_bars_in_range,
    format_beat_info_display,
)

from .bar_mapper import (
    timestamp_to_bar,
    bar_to_timestamp,
    get_bar_duration,
    map_sections_to_bars,
    snap_to_bar_boundary,
    get_bar_timestamps,
    calculate_total_bars,
    format_bar_time,
    quantize_sections_to_bars,
)

from .structure_pipeline import (
    StructureFeatures,
    extract_structure,
    format_structure_display,
    get_section_at_time,
    get_section_at_bar,
    summarize_structure,
)

from .energy_analyzer import (
    EnergyProfile,
    SectionEnergy,
    extract_energy_profile,
    analyze_section_energy,
    classify_section_by_energy,
    refine_sections_with_energy,
    detect_drops_by_bass,
    get_energy_curve,
)

__all__ = [
    # Section detection
    'SectionInfo',
    'detect_sections',
    'detect_sections_allin1',
    'detect_sections_docker_allin1',
    'detect_sections_librosa_fallback',
    'map_label_to_trance',
    'format_sections_display',
    'get_allin1_cache_stats',
    'clear_allin1_cache',

    # Beat tracking
    'BeatInfo',
    'track_beats',
    'estimate_downbeats',
    'estimate_downbeats_with_energy',
    'calculate_beat_confidence',
    'get_beats_in_range',
    'count_bars_in_range',
    'format_beat_info_display',

    # Bar mapping
    'timestamp_to_bar',
    'bar_to_timestamp',
    'get_bar_duration',
    'map_sections_to_bars',
    'snap_to_bar_boundary',
    'get_bar_timestamps',
    'calculate_total_bars',
    'format_bar_time',
    'quantize_sections_to_bars',

    # Structure pipeline
    'StructureFeatures',
    'extract_structure',
    'format_structure_display',
    'get_section_at_time',
    'get_section_at_bar',
    'summarize_structure',

    # Energy analysis
    'EnergyProfile',
    'SectionEnergy',
    'extract_energy_profile',
    'analyze_section_energy',
    'classify_section_by_energy',
    'refine_sections_with_energy',
    'detect_drops_by_bass',
    'get_energy_curve',
]
