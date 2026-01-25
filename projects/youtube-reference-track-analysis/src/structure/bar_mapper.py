"""
Bar mapping utilities for converting between timestamps and bar numbers.

Essential for understanding track structure in musical terms rather than
absolute time.
"""

from typing import List, Optional, Tuple
from .section_detector import SectionInfo


def timestamp_to_bar(
    timestamp: float,
    bpm: float,
    first_downbeat: float = 0.0,
    time_signature: int = 4
) -> int:
    """
    Convert a timestamp to a bar number.

    Bar numbers are 1-indexed (first bar is bar 1).

    Args:
        timestamp: Time in seconds
        bpm: Beats per minute
        first_downbeat: Timestamp of first downbeat (bar 1, beat 1)
        time_signature: Beats per bar (default 4)

    Returns:
        Bar number (1-indexed)
    """
    if timestamp < first_downbeat:
        return 0  # Before first bar

    # Calculate bar duration in seconds
    beat_duration = 60.0 / bpm
    bar_duration = beat_duration * time_signature

    # Calculate bar number
    time_from_first_bar = timestamp - first_downbeat
    bar_number = int(time_from_first_bar / bar_duration) + 1

    return bar_number


def bar_to_timestamp(
    bar: int,
    bpm: float,
    first_downbeat: float = 0.0,
    time_signature: int = 4
) -> float:
    """
    Convert a bar number to a timestamp.

    Args:
        bar: Bar number (1-indexed)
        bpm: Beats per minute
        first_downbeat: Timestamp of first downbeat
        time_signature: Beats per bar

    Returns:
        Timestamp in seconds
    """
    if bar < 1:
        return first_downbeat

    # Calculate bar duration in seconds
    beat_duration = 60.0 / bpm
    bar_duration = beat_duration * time_signature

    # Calculate timestamp
    timestamp = first_downbeat + (bar - 1) * bar_duration

    return round(timestamp, 3)


def get_bar_duration(bpm: float, time_signature: int = 4) -> float:
    """
    Calculate the duration of one bar in seconds.

    Args:
        bpm: Beats per minute
        time_signature: Beats per bar

    Returns:
        Bar duration in seconds
    """
    beat_duration = 60.0 / bpm
    return beat_duration * time_signature


def map_sections_to_bars(
    sections: List[SectionInfo],
    bpm: float,
    first_downbeat: float = 0.0,
    time_signature: int = 4
) -> List[SectionInfo]:
    """
    Add bar numbers to sections.

    Args:
        sections: List of sections with timestamps
        bpm: Track BPM
        first_downbeat: Timestamp of first downbeat
        time_signature: Beats per bar

    Returns:
        Sections with bar numbers filled in
    """
    mapped_sections = []

    for section in sections:
        # Calculate bar numbers
        start_bar = timestamp_to_bar(
            section.start_time, bpm, first_downbeat, time_signature
        )
        end_bar = timestamp_to_bar(
            section.end_time, bpm, first_downbeat, time_signature
        )

        # Duration in bars
        duration_bars = end_bar - start_bar
        if duration_bars < 1:
            duration_bars = 1

        # Create new section with bar info
        mapped_section = SectionInfo(
            section_type=section.section_type,
            original_label=section.original_label,
            start_time=section.start_time,
            end_time=section.end_time,
            start_bar=start_bar,
            end_bar=end_bar,
            duration_bars=duration_bars,
            confidence=section.confidence
        )
        mapped_sections.append(mapped_section)

    return mapped_sections


def snap_to_bar_boundary(
    timestamp: float,
    bpm: float,
    first_downbeat: float = 0.0,
    time_signature: int = 4,
    mode: str = 'nearest'
) -> float:
    """
    Snap a timestamp to the nearest bar boundary.

    Args:
        timestamp: Time in seconds
        bpm: Beats per minute
        first_downbeat: Timestamp of first downbeat
        time_signature: Beats per bar
        mode: 'nearest', 'floor', or 'ceil'

    Returns:
        Snapped timestamp
    """
    bar_duration = get_bar_duration(bpm, time_signature)
    time_from_first = timestamp - first_downbeat

    if mode == 'floor':
        bars = int(time_from_first / bar_duration)
    elif mode == 'ceil':
        bars = int(time_from_first / bar_duration) + 1
    else:  # nearest
        bars = round(time_from_first / bar_duration)

    return first_downbeat + bars * bar_duration


def get_bar_timestamps(
    bpm: float,
    duration: float,
    first_downbeat: float = 0.0,
    time_signature: int = 4
) -> List[Tuple[int, float]]:
    """
    Get all bar boundaries in a track.

    Args:
        bpm: Beats per minute
        duration: Total track duration in seconds
        first_downbeat: Timestamp of first downbeat
        time_signature: Beats per bar

    Returns:
        List of (bar_number, timestamp) tuples
    """
    bar_duration = get_bar_duration(bpm, time_signature)
    bars = []

    bar_num = 1
    timestamp = first_downbeat

    while timestamp < duration:
        bars.append((bar_num, round(timestamp, 3)))
        bar_num += 1
        timestamp += bar_duration

    return bars


def calculate_total_bars(
    duration: float,
    bpm: float,
    first_downbeat: float = 0.0,
    time_signature: int = 4
) -> int:
    """
    Calculate total number of bars in a track.

    Args:
        duration: Track duration in seconds
        bpm: Beats per minute
        first_downbeat: Timestamp of first downbeat
        time_signature: Beats per bar

    Returns:
        Total number of bars
    """
    bar_duration = get_bar_duration(bpm, time_signature)
    effective_duration = duration - first_downbeat

    if effective_duration <= 0:
        return 0

    return int(effective_duration / bar_duration) + 1


def format_bar_time(
    bar: int,
    bpm: float,
    first_downbeat: float = 0.0,
    time_signature: int = 4
) -> str:
    """
    Format a bar number as both bar and time.

    Args:
        bar: Bar number
        bpm: Beats per minute
        first_downbeat: Timestamp of first downbeat
        time_signature: Beats per bar

    Returns:
        Formatted string like "bar 16 (0:27)"
    """
    timestamp = bar_to_timestamp(bar, bpm, first_downbeat, time_signature)
    mins = int(timestamp // 60)
    secs = int(timestamp % 60)

    return f"bar {bar} ({mins}:{secs:02d})"


def quantize_sections_to_bars(
    sections: List[SectionInfo],
    bpm: float,
    first_downbeat: float = 0.0,
    time_signature: int = 4,
    min_bars: int = 4
) -> List[SectionInfo]:
    """
    Quantize section boundaries to bar boundaries.

    Ensures sections start and end on bar lines and have
    a minimum length.

    Args:
        sections: List of sections
        bpm: Track BPM
        first_downbeat: Timestamp of first downbeat
        time_signature: Beats per bar
        min_bars: Minimum section length in bars

    Returns:
        Quantized sections
    """
    if not sections:
        return []

    quantized = []

    for section in sections:
        # Snap boundaries to bars
        start_time = snap_to_bar_boundary(
            section.start_time, bpm, first_downbeat, time_signature, 'floor'
        )
        end_time = snap_to_bar_boundary(
            section.end_time, bpm, first_downbeat, time_signature, 'ceil'
        )

        # Ensure minimum length
        bar_duration = get_bar_duration(bpm, time_signature)
        min_duration = min_bars * bar_duration
        if end_time - start_time < min_duration:
            end_time = start_time + min_duration

        # Calculate bar numbers
        start_bar = timestamp_to_bar(start_time, bpm, first_downbeat, time_signature)
        end_bar = timestamp_to_bar(end_time, bpm, first_downbeat, time_signature)

        quantized_section = SectionInfo(
            section_type=section.section_type,
            original_label=section.original_label,
            start_time=start_time,
            end_time=end_time,
            start_bar=start_bar,
            end_bar=end_bar,
            duration_bars=end_bar - start_bar,
            confidence=section.confidence
        )
        quantized.append(quantized_section)

    return quantized
