"""
Section detection using allin1 deep learning model.

Detects musical sections (intro, verse, chorus, bridge, outro) and maps
them to trance-specific labels (intro, buildup, drop, breakdown, outro).

Uses the shared allin1 Docker module with caching enabled for batch processing.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple
import numpy as np

# Add shared module to path
_shared_path = Path(__file__).parents[4] / "shared"
if str(_shared_path) not in sys.path:
    sys.path.insert(0, str(_shared_path))

# Import from shared allin1 module
try:
    from allin1 import DockerAllin1, is_docker_available, is_allin1_image_available, Allin1Cache
    SHARED_ALLIN1_AVAILABLE = True
except ImportError:
    SHARED_ALLIN1_AVAILABLE = False
    DockerAllin1 = None  # Type hint placeholder


@dataclass
class SectionInfo:
    """Information about a detected section."""
    section_type: str  # Trance-mapped label: intro, buildup, drop, breakdown, outro
    original_label: str  # What allin1 called it
    start_time: float  # Start time in seconds
    end_time: float  # End time in seconds
    start_bar: Optional[int] = None  # Bar number at start
    end_bar: Optional[int] = None  # Bar number at end
    duration_bars: Optional[int] = None  # Duration in bars
    confidence: float = 0.8  # Detection confidence


# Mapping from allin1 labels to trance terminology
TRANCE_LABEL_MAP = {
    # Direct mappings
    'intro': 'INTRO',
    'outro': 'OUTRO',

    # Verse-like sections become breakdowns (melodic, lower energy)
    'verse': 'BREAKDOWN',
    'bridge': 'BREAKDOWN',

    # Chorus/inst sections become drops (high energy, main hook)
    'chorus': 'DROP',
    'inst': 'DROP',  # Instrumental sections are often drops in trance

    # Pre-chorus is buildup
    'pre-chorus': 'BUILDUP',

    # Fallbacks
    'interlude': 'BREAKDOWN',
    'solo': 'DROP',
}


def map_label_to_trance(label: str) -> str:
    """
    Map an allin1 label to trance-specific terminology.

    Args:
        label: Original label from allin1

    Returns:
        Trance-specific section type
    """
    label_lower = label.lower().strip()
    return TRANCE_LABEL_MAP.get(label_lower, 'BREAKDOWN')


# Global cached analyzer instance for youtube-analyzer batch processing
_cached_docker_analyzer: Optional[DockerAllin1] = None


def _get_docker_analyzer() -> Optional[DockerAllin1]:
    """Get or create the cached Docker analyzer with caching enabled."""
    global _cached_docker_analyzer

    if _cached_docker_analyzer is not None:
        return _cached_docker_analyzer

    if not SHARED_ALLIN1_AVAILABLE:
        return None

    if not is_docker_available():
        print("Docker not available for allin1")
        return None

    if not is_allin1_image_available():
        print("allin1 Docker image not built. Run:")
        print("  cd AbletonAIAnalysis/shared/allin1")
        print("  docker build -t allin1:latest .")
        return None

    # Create analyzer with caching enabled for batch processing
    _cached_docker_analyzer = DockerAllin1(
        enable_cache=True,
        cache_dir=Path.home() / ".cache" / "allin1",
        use_gpu=True  # Use GPU if available
    )
    return _cached_docker_analyzer


def detect_sections_docker_allin1(audio_path: Path) -> Optional[List[SectionInfo]]:
    """
    Detect sections using allin1 via Docker container.

    This bypasses Python 3.13 compatibility issues by running allin1
    in a Docker container with Python 3.11.

    Uses file-hash based caching for repeated analyses of the same files
    (useful for batch processing reference tracks).

    Args:
        audio_path: Path to audio file

    Returns:
        List of SectionInfo or None on error
    """
    analyzer = _get_docker_analyzer()
    if analyzer is None:
        # Try legacy local import as fallback
        try:
            from .docker_allin1 import DockerAllin1 as LocalDockerAllin1
            from .docker_allin1 import is_docker_available as local_is_docker_available
            from .docker_allin1 import is_allin1_image_available as local_is_allin1_image_available

            if not local_is_docker_available() or not local_is_allin1_image_available():
                return None
            analyzer = LocalDockerAllin1()
        except ImportError:
            return None

    audio_path = Path(audio_path)
    if not audio_path.exists():
        return None

    try:
        result = analyzer.analyze(audio_path)

        if result is None:
            return None

        sections = []
        for segment in result.segments:
            section = SectionInfo(
                section_type=map_label_to_trance(segment.label),
                original_label=segment.label,
                start_time=segment.start,
                end_time=segment.end,
                confidence=0.85  # Docker allin1 is reliable
            )
            sections.append(section)

        return sections if sections else None

    except Exception as e:
        print(f"Docker allin1 failed: {e}")
        return None


def get_allin1_cache_stats() -> Optional[dict]:
    """Get cache statistics for the allin1 analyzer."""
    analyzer = _get_docker_analyzer()
    if analyzer is None:
        return None
    return analyzer.cache_stats()


def clear_allin1_cache() -> int:
    """Clear the allin1 analysis cache."""
    analyzer = _get_docker_analyzer()
    if analyzer is None:
        return 0
    return analyzer.clear_cache()


def detect_sections_allin1(audio_path: Path) -> Optional[List[SectionInfo]]:
    """
    Detect sections using allin1 deep learning model.

    Tries native allin1 first, then Docker allin1, then returns None.

    Args:
        audio_path: Path to audio file

    Returns:
        List of SectionInfo or None on error
    """
    try:
        import allin1
    except ImportError:
        # Try Docker fallback
        print("Native allin1 not available, trying Docker...")
        return detect_sections_docker_allin1(audio_path)

    audio_path = Path(audio_path)
    if not audio_path.exists():
        return None

    try:
        # Run allin1 analysis
        result = allin1.analyze(str(audio_path))

        if result is None or not hasattr(result, 'segments'):
            return None

        sections = []

        for i, segment in enumerate(result.segments):
            # allin1 segments have: start, end, label
            section = SectionInfo(
                section_type=map_label_to_trance(segment.label),
                original_label=segment.label,
                start_time=float(segment.start),
                end_time=float(segment.end),
                confidence=0.8  # allin1 is generally reliable
            )
            sections.append(section)

        return sections if sections else None

    except Exception as e:
        print(f"Error in allin1 section detection: {e}")
        print("Falling back to Docker allin1...")
        return detect_sections_docker_allin1(audio_path)


def detect_sections_librosa_fallback(
    audio_path: Path,
    n_segments: int = 8
) -> Optional[List[SectionInfo]]:
    """
    Fallback section detection using librosa novelty-based segmentation.

    Less accurate than allin1 but works without deep learning model.

    Args:
        audio_path: Path to audio file
        n_segments: Approximate number of segments to detect

    Returns:
        List of SectionInfo or None on error
    """
    try:
        import librosa
        from scipy import signal
    except ImportError:
        return None

    audio_path = Path(audio_path)
    if not audio_path.exists():
        return None

    try:
        # Load audio
        y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
        duration = len(y) / sr

        # Compute novelty function (spectral flux)
        hop_length = 512
        S = np.abs(librosa.stft(y, hop_length=hop_length))
        novelty = librosa.onset.onset_strength(S=S, sr=sr, hop_length=hop_length)

        # Smooth novelty
        novelty_smooth = signal.medfilt(novelty, kernel_size=21)

        # Find peaks (potential section boundaries)
        # Use a larger distance to get fewer, more significant boundaries
        min_distance = int(sr / hop_length * 10)  # At least 10 seconds apart
        peaks, _ = signal.find_peaks(
            novelty_smooth,
            distance=min_distance,
            prominence=np.std(novelty_smooth)
        )

        # Convert peak frames to times
        boundary_times = librosa.frames_to_time(peaks, sr=sr, hop_length=hop_length)

        # Add start and end
        boundary_times = np.concatenate([[0], boundary_times, [duration]])
        boundary_times = np.unique(boundary_times)

        # Limit to reasonable number of segments
        if len(boundary_times) > n_segments + 1:
            # Keep most prominent boundaries
            indices = np.linspace(0, len(boundary_times) - 1, n_segments + 1).astype(int)
            boundary_times = boundary_times[indices]

        # Create sections with heuristic labels
        sections = []
        n_boundaries = len(boundary_times) - 1

        for i in range(n_boundaries):
            start = boundary_times[i]
            end = boundary_times[i + 1]

            # Heuristic labeling based on position
            if i == 0:
                label = 'INTRO'
            elif i == n_boundaries - 1:
                label = 'OUTRO'
            elif i % 2 == 1:
                # Odd positions (1, 3, 5...) tend to be higher energy
                label = 'DROP' if i > n_boundaries // 2 else 'BUILDUP'
            else:
                # Even positions (2, 4, 6...) tend to be lower energy
                label = 'BREAKDOWN'

            section = SectionInfo(
                section_type=label,
                original_label=f'segment_{i}',
                start_time=float(start),
                end_time=float(end),
                confidence=0.5  # Lower confidence for heuristic detection
            )
            sections.append(section)

        return sections if sections else None

    except Exception as e:
        print(f"Error in librosa fallback section detection: {e}")
        return None


def detect_sections(
    audio_path: Path,
    use_allin1: bool = True
) -> Optional[List[SectionInfo]]:
    """
    Detect sections in an audio file.

    Uses allin1 by default with librosa fallback if allin1 fails.

    Args:
        audio_path: Path to audio file
        use_allin1: Try allin1 first (recommended)

    Returns:
        List of SectionInfo or None on error
    """
    audio_path = Path(audio_path)

    if use_allin1:
        try:
            sections = detect_sections_allin1(audio_path)
            if sections:
                return sections
        except Exception as e:
            print(f"allin1 failed, falling back to librosa: {e}")

    # Fallback to librosa
    return detect_sections_librosa_fallback(audio_path)


def identify_buildup_sections(
    sections: List[SectionInfo],
    audio_path: Path
) -> List[SectionInfo]:
    """
    Post-process sections to better identify buildups.

    In trance, buildups are sections immediately before drops with
    rising energy. This refines the initial detection.

    Args:
        sections: List of detected sections
        audio_path: Path to audio for energy analysis

    Returns:
        Refined list of sections
    """
    if not sections or len(sections) < 2:
        return sections

    try:
        import librosa
    except ImportError:
        return sections

    try:
        # Load audio for energy analysis
        y, sr = librosa.load(str(audio_path), sr=22050, mono=True)

        # Calculate energy for each section
        energies = []
        for section in sections:
            start_sample = int(section.start_time * sr)
            end_sample = int(section.end_time * sr)
            segment = y[start_sample:end_sample]
            energy = np.sqrt(np.mean(segment ** 2)) if len(segment) > 0 else 0
            energies.append(energy)

        # Identify buildups: sections before drops with lower energy
        refined_sections = []
        for i, section in enumerate(sections):
            new_section = SectionInfo(
                section_type=section.section_type,
                original_label=section.original_label,
                start_time=section.start_time,
                end_time=section.end_time,
                start_bar=section.start_bar,
                end_bar=section.end_bar,
                duration_bars=section.duration_bars,
                confidence=section.confidence
            )

            # Check if this should be a buildup
            if i < len(sections) - 1:
                next_section = sections[i + 1]
                if (next_section.section_type == 'DROP' and
                    section.section_type in ['BREAKDOWN', 'DROP'] and
                    energies[i] < energies[i + 1] * 0.8):
                    new_section.section_type = 'BUILDUP'

            refined_sections.append(new_section)

        return refined_sections

    except Exception:
        return sections


def format_sections_display(sections: List[SectionInfo]) -> str:
    """
    Format sections for display.

    Args:
        sections: List of sections

    Returns:
        Formatted string
    """
    if not sections:
        return "No sections detected"

    lines = []
    for i, section in enumerate(sections, 1):
        # Format time as MM:SS
        start_min = int(section.start_time // 60)
        start_sec = int(section.start_time % 60)
        end_min = int(section.end_time // 60)
        end_sec = int(section.end_time % 60)

        time_str = f"{start_min}:{start_sec:02d}-{end_min}:{end_sec:02d}"

        bar_str = ""
        if section.start_bar is not None and section.end_bar is not None:
            bar_str = f"  bars {section.start_bar}-{section.end_bar}"

        lines.append(f"  {i}. {section.section_type:<12} {time_str}{bar_str}")

    return "\n".join(lines)
