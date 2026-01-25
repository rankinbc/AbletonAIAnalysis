"""
Structure analysis pipeline for trance tracks.

Orchestrates section detection, beat tracking, and bar mapping
to provide complete structural analysis.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List
import time

from .section_detector import SectionInfo, detect_sections, identify_buildup_sections
from .beat_tracker import BeatInfo, track_beats, estimate_downbeats_with_energy
from .bar_mapper import (
    map_sections_to_bars,
    calculate_total_bars,
    quantize_sections_to_bars
)


@dataclass
class StructureFeatures:
    """Complete structure analysis results."""
    # Basic timing
    bpm: float
    time_signature: int  # Usually 4 for trance

    # Beat information
    beats: List[float]  # All beat timestamps
    downbeats: List[float]  # Downbeat (bar start) timestamps
    first_downbeat: float  # Timestamp of first downbeat
    total_bars: int  # Total bars in track

    # Section information
    sections: List[SectionInfo]  # Detected sections with bar numbers

    # Metadata
    beat_confidence: float  # Beat tracking confidence
    section_confidence: float  # Section detection confidence
    extraction_time_sec: float  # Time to extract features
    errors: List[str] = field(default_factory=list)  # Any errors encountered


def extract_structure(
    audio_path: Path,
    bpm_hint: Optional[float] = None,
    quantize: bool = True,
    min_section_bars: int = 4
) -> Optional[StructureFeatures]:
    """
    Extract complete structure features from an audio file.

    Args:
        audio_path: Path to audio file
        bpm_hint: Optional BPM hint to improve beat tracking
        quantize: Snap section boundaries to bar lines
        min_section_bars: Minimum section length in bars

    Returns:
        StructureFeatures or None on error
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        return None

    start_time = time.time()
    errors = []

    # Step 1: Beat tracking
    beat_info = track_beats(audio_path, bpm_hint)

    if beat_info is None:
        errors.append("Beat tracking failed")
        # Create fallback with estimated BPM
        bpm = bpm_hint or 140.0  # Default trance BPM
        beats = []
        downbeats = []
        first_downbeat = 0.0
        beat_confidence = 0.0
    else:
        bpm = beat_info.bpm
        beats = beat_info.beats
        first_downbeat = beat_info.first_downbeat
        beat_confidence = beat_info.beat_confidence

        # Improve downbeat estimation with energy analysis
        downbeats = estimate_downbeats_with_energy(
            audio_path, beats, beat_info.time_signature
        )
        if not downbeats:
            downbeats = beat_info.downbeats

    time_signature = 4  # Trance is always 4/4

    # Step 2: Section detection
    sections = detect_sections(audio_path)

    if sections is None:
        errors.append("Section detection failed")
        sections = []
        section_confidence = 0.0
    else:
        # Refine buildups based on energy
        sections = identify_buildup_sections(sections, audio_path)

        # Average confidence across sections
        section_confidence = sum(s.confidence for s in sections) / len(sections) if sections else 0.0

    # Step 3: Map sections to bars
    if sections and bpm > 0:
        sections = map_sections_to_bars(
            sections, bpm, first_downbeat, time_signature
        )

        # Optionally quantize to bar boundaries
        if quantize:
            sections = quantize_sections_to_bars(
                sections, bpm, first_downbeat, time_signature, min_section_bars
            )

    # Calculate total bars
    if beats:
        duration = beats[-1] if beats else 0
    else:
        # Try to get duration from audio file
        try:
            import librosa
            y, sr = librosa.load(str(audio_path), sr=22050, mono=True, duration=5)
            duration = librosa.get_duration(y=y, sr=sr) * (len(y) / (5 * sr))  # Estimate
        except Exception:
            duration = 0

    total_bars = calculate_total_bars(duration, bpm, first_downbeat, time_signature)

    extraction_time = time.time() - start_time

    return StructureFeatures(
        bpm=round(bpm, 2),
        time_signature=time_signature,
        beats=beats,
        downbeats=downbeats,
        first_downbeat=round(first_downbeat, 3),
        total_bars=total_bars,
        sections=sections,
        beat_confidence=round(beat_confidence, 3),
        section_confidence=round(section_confidence, 3),
        extraction_time_sec=round(extraction_time, 2),
        errors=errors
    )


def format_structure_display(structure: StructureFeatures) -> str:
    """
    Format structure features for display.

    Args:
        structure: Structure analysis results

    Returns:
        Formatted string
    """
    lines = [
        "STRUCTURE ANALYSIS",
        "=" * 40,
        "",
        f"BPM: {structure.bpm}",
        f"Time Signature: {structure.time_signature}/4",
        f"Total Bars: {structure.total_bars}",
        f"Total Beats: {len(structure.beats)}",
        f"First Downbeat: {structure.first_downbeat:.2f}s",
        "",
        f"Beat Confidence: {structure.beat_confidence:.1%}",
        f"Section Confidence: {structure.section_confidence:.1%}",
        "",
    ]

    # Duration
    if structure.beats:
        duration = structure.beats[-1]
        mins = int(duration // 60)
        secs = int(duration % 60)
        lines.append(f"Duration: {mins}:{secs:02d}")
        lines.append("")

    # Sections
    if structure.sections:
        lines.append("SECTIONS")
        lines.append("-" * 40)
        for i, section in enumerate(structure.sections, 1):
            start_min = int(section.start_time // 60)
            start_sec = int(section.start_time % 60)
            end_min = int(section.end_time // 60)
            end_sec = int(section.end_time % 60)

            time_str = f"{start_min}:{start_sec:02d}-{end_min}:{end_sec:02d}"

            bar_str = ""
            if section.start_bar is not None and section.end_bar is not None:
                bar_str = f"bars {section.start_bar}-{section.end_bar}"

            lines.append(f"  {i}. {section.section_type:<12} {time_str}  {bar_str}")
    else:
        lines.append("No sections detected")

    # Errors
    if structure.errors:
        lines.append("")
        lines.append("WARNINGS:")
        for error in structure.errors:
            lines.append(f"  - {error}")

    lines.append("")
    lines.append(f"Extraction time: {structure.extraction_time_sec:.1f}s")

    return "\n".join(lines)


def get_section_at_time(
    structure: StructureFeatures,
    timestamp: float
) -> Optional[SectionInfo]:
    """
    Get the section at a specific timestamp.

    Args:
        structure: Structure analysis results
        timestamp: Time in seconds

    Returns:
        Section at that time or None
    """
    for section in structure.sections:
        if section.start_time <= timestamp < section.end_time:
            return section
    return None


def get_section_at_bar(
    structure: StructureFeatures,
    bar: int
) -> Optional[SectionInfo]:
    """
    Get the section at a specific bar number.

    Args:
        structure: Structure analysis results
        bar: Bar number (1-indexed)

    Returns:
        Section at that bar or None
    """
    for section in structure.sections:
        if section.start_bar is not None and section.end_bar is not None:
            if section.start_bar <= bar < section.end_bar:
                return section
    return None


def summarize_structure(structure: StructureFeatures) -> str:
    """
    Create a brief summary of the track structure.

    Args:
        structure: Structure analysis results

    Returns:
        Brief summary string
    """
    if not structure.sections:
        return f"{structure.total_bars} bars @ {structure.bpm} BPM"

    # Count section types
    type_counts = {}
    for section in structure.sections:
        type_counts[section.section_type] = type_counts.get(section.section_type, 0) + 1

    parts = [f"{structure.total_bars} bars @ {structure.bpm} BPM"]

    # Add section breakdown
    section_parts = []
    for stype in ['DROP', 'BUILDUP', 'BREAKDOWN', 'INTRO', 'OUTRO']:
        if stype in type_counts:
            count = type_counts[stype]
            section_parts.append(f"{count} {stype.lower()}{'s' if count > 1 else ''}")

    if section_parts:
        parts.append(", ".join(section_parts))

    return " | ".join(parts)
