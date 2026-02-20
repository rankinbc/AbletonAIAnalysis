"""
Arrangement Analyzer Module

Extracts trance-specific arrangement metrics using the shared allin1 Docker container.
Maps generic song structure labels to trance terminology and calculates statistics.
"""

import sys
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple

import numpy as np

# Add shared module to path
shared_path = Path(__file__).parent.parent.parent.parent.parent / "shared"
sys.path.insert(0, str(shared_path))

from allin1.docker_allin1 import DockerAllin1, Allin1Result, Allin1Segment

# Add database module to path
db_path = Path(__file__).parent.parent / "database"
sys.path.insert(0, str(db_path))

from database import YTArrangementStats


# Trance terminology mapping from allin1 labels
TRANCE_LABEL_MAP = {
    'intro': 'INTRO',
    'verse': 'BREAKDOWN',      # Melodic, lower energy sections
    'chorus': 'DROP',          # High energy, main hook
    'bridge': 'BREAKDOWN',     # Transition sections
    'pre-chorus': 'BUILDUP',   # Rising energy before drop
    'outro': 'OUTRO',
    'inst': 'DROP',            # Instrumental sections often drops in trance
    'solo': 'BREAKDOWN',       # Solo sections
}


@dataclass
class TranceSection:
    """A section mapped to trance terminology."""
    section_type: str  # INTRO, BUILDUP, DROP, BREAKDOWN, OUTRO
    start_time: float
    end_time: float
    start_bar: Optional[int] = None
    end_bar: Optional[int] = None
    original_label: Optional[str] = None


@dataclass
class ArrangementFeatures:
    """Extracted arrangement features for a track."""
    # Structure
    total_bars: int
    bpm: float

    # Section counts
    num_drops: int
    num_breakdowns: int
    num_buildups: int

    # Timing
    bars_to_first_drop: Optional[int]
    bars_to_first_breakdown: Optional[int]

    # Drop analysis
    avg_drop_length_bars: Optional[float]
    first_drop_energy: Optional[float]

    # Breakdown analysis
    avg_breakdown_length_bars: Optional[float]

    # Buildup analysis
    avg_buildup_length_bars: Optional[float]
    max_buildup_length_bars: Optional[int]

    # Phrase structure
    phrase_length_bars: Optional[int]
    phrase_regularity: Optional[float]

    # Raw sections
    sections: List[TranceSection]

    # Errors
    errors: List[str]


def map_to_trance_section(segment: Allin1Segment, bpm: float) -> TranceSection:
    """Map an allin1 segment to trance terminology."""
    label = segment.label.lower().strip()
    trance_type = TRANCE_LABEL_MAP.get(label, 'BREAKDOWN')  # Default to breakdown

    # Calculate bar positions
    seconds_per_bar = (60.0 / bpm) * 4  # Assuming 4/4 time
    start_bar = int(segment.start / seconds_per_bar)
    end_bar = int(segment.end / seconds_per_bar)

    return TranceSection(
        section_type=trance_type,
        start_time=segment.start,
        end_time=segment.end,
        start_bar=start_bar,
        end_bar=end_bar,
        original_label=segment.label
    )


def calculate_phrase_length(downbeats: List[float], bpm: float) -> Tuple[Optional[int], Optional[float]]:
    """
    Estimate phrase length from downbeat patterns.

    Returns:
        (phrase_length_bars, regularity_score)
    """
    if len(downbeats) < 8:
        return None, None

    # Common trance phrase lengths (in bars)
    common_lengths = [4, 8, 16, 32]

    # Calculate intervals between downbeats
    intervals = np.diff(downbeats)

    # Estimate bars per phrase by looking at energy/structure patterns
    # For now, use 8 bars as default trance phrase length
    phrase_length = 8

    # Calculate regularity (how consistent the intervals are)
    expected_interval = (60.0 / bpm) * 4  # 4 beats per bar
    deviations = np.abs(intervals - expected_interval) / expected_interval
    regularity = max(0.0, 1.0 - np.mean(deviations))

    return phrase_length, round(regularity, 3)


def extract_arrangement(
    audio_path: Path,
    allin1_result: Optional[Allin1Result] = None,
    use_cache: bool = True
) -> Optional[ArrangementFeatures]:
    """
    Extract arrangement features from an audio file.

    Args:
        audio_path: Path to audio file
        allin1_result: Pre-computed allin1 result (if available from structure stage)
        use_cache: Whether to use cached allin1 results

    Returns:
        ArrangementFeatures or None on error
    """
    audio_path = Path(audio_path)
    errors = []

    if not audio_path.exists():
        return None

    # Get allin1 result if not provided
    if allin1_result is None:
        try:
            analyzer = DockerAllin1(enable_cache=use_cache)
            allin1_result = analyzer.analyze(audio_path)
        except Exception as e:
            errors.append(f"allin1 failed: {str(e)}")
            return None

    if allin1_result is None:
        return None

    bpm = allin1_result.bpm
    if bpm <= 0:
        bpm = 140  # Default trance BPM

    # Map segments to trance sections
    sections = [map_to_trance_section(seg, bpm) for seg in allin1_result.segments]

    # Count section types
    type_counts = {}
    type_sections = {}
    for section in sections:
        stype = section.section_type
        type_counts[stype] = type_counts.get(stype, 0) + 1
        if stype not in type_sections:
            type_sections[stype] = []
        type_sections[stype].append(section)

    num_drops = type_counts.get('DROP', 0)
    num_breakdowns = type_counts.get('BREAKDOWN', 0)
    num_buildups = type_counts.get('BUILDUP', 0)

    # Calculate total bars
    if sections:
        max_end_bar = max(s.end_bar for s in sections if s.end_bar)
        total_bars = max_end_bar if max_end_bar else 0
    else:
        total_bars = 0

    # Find first drop/breakdown timing
    bars_to_first_drop = None
    bars_to_first_breakdown = None

    for section in sections:
        if section.section_type == 'DROP' and bars_to_first_drop is None:
            bars_to_first_drop = section.start_bar
        if section.section_type == 'BREAKDOWN' and bars_to_first_breakdown is None:
            bars_to_first_breakdown = section.start_bar

    # Calculate average section lengths
    def avg_section_length(section_list: List[TranceSection]) -> Optional[float]:
        if not section_list:
            return None
        lengths = [s.end_bar - s.start_bar for s in section_list if s.end_bar and s.start_bar]
        return round(np.mean(lengths), 1) if lengths else None

    avg_drop_length = avg_section_length(type_sections.get('DROP', []))
    avg_breakdown_length = avg_section_length(type_sections.get('BREAKDOWN', []))
    avg_buildup_length = avg_section_length(type_sections.get('BUILDUP', []))

    # Max buildup length
    buildup_lengths = [s.end_bar - s.start_bar for s in type_sections.get('BUILDUP', [])
                       if s.end_bar and s.start_bar]
    max_buildup_length = max(buildup_lengths) if buildup_lengths else None

    # Phrase analysis
    phrase_length, phrase_regularity = calculate_phrase_length(allin1_result.downbeats, bpm)

    return ArrangementFeatures(
        total_bars=total_bars,
        bpm=bpm,
        num_drops=num_drops,
        num_breakdowns=num_breakdowns,
        num_buildups=num_buildups,
        bars_to_first_drop=bars_to_first_drop,
        bars_to_first_breakdown=bars_to_first_breakdown,
        avg_drop_length_bars=avg_drop_length,
        first_drop_energy=None,  # TODO: Calculate from audio
        avg_breakdown_length_bars=avg_breakdown_length,
        avg_buildup_length_bars=avg_buildup_length,
        max_buildup_length_bars=max_buildup_length,
        phrase_length_bars=phrase_length,
        phrase_regularity=phrase_regularity,
        sections=sections,
        errors=errors
    )


def to_db_model(features: ArrangementFeatures, track_id: int) -> YTArrangementStats:
    """Convert ArrangementFeatures to database model."""
    return YTArrangementStats(
        track_id=track_id,
        total_bars=features.total_bars,
        bars_to_first_drop=features.bars_to_first_drop,
        bars_to_first_breakdown=features.bars_to_first_breakdown,
        num_drops=features.num_drops,
        num_breakdowns=features.num_breakdowns,
        num_buildups=features.num_buildups,
        avg_buildup_length_bars=features.avg_buildup_length_bars,
        max_buildup_length_bars=features.max_buildup_length_bars,
        avg_drop_length_bars=features.avg_drop_length_bars,
        first_drop_energy=features.first_drop_energy,
        drop_intensity_variance=None,  # TODO
        avg_breakdown_length_bars=features.avg_breakdown_length_bars,
        phrase_length_bars=features.phrase_length_bars,
        phrase_regularity=features.phrase_regularity,
        filter_sweeps_json=None,  # TODO
        risers_json=None  # TODO
    )


def format_arrangement_display(features: ArrangementFeatures) -> str:
    """Format arrangement features for display."""
    lines = [
        f"Structure: {features.total_bars} bars @ {features.bpm:.0f} BPM",
        f"Sections: {features.num_drops} drops, {features.num_breakdowns} breakdowns, {features.num_buildups} buildups",
    ]

    if features.bars_to_first_drop:
        lines.append(f"First drop at bar {features.bars_to_first_drop}")

    if features.avg_drop_length_bars:
        lines.append(f"Avg drop length: {features.avg_drop_length_bars} bars")

    if features.phrase_length_bars:
        lines.append(f"Phrase length: {features.phrase_length_bars} bars (regularity: {features.phrase_regularity:.0%})")

    return "\n".join(lines)
