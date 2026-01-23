"""
Structure Detector Module

Detects song structure (sections, beats, downbeats) using AI-based analysis:
- Primary: all-in-one deep learning model for joint beat/structure detection
- Fallback: librosa novelty-based segmentation

Outputs section labels mapped to trance terminology:
- intro, buildup, drop, breakdown, outro
"""

import numpy as np
import librosa
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Callable
from pathlib import Path
from enum import Enum

# Check for all-in-one availability
ALLIN1_AVAILABLE = False
try:
    import allin1
    ALLIN1_AVAILABLE = True
except ImportError:
    pass


class SectionType(Enum):
    """Trance-specific section types."""
    INTRO = "intro"
    BUILDUP = "buildup"
    DROP = "drop"
    BREAKDOWN = "breakdown"
    OUTRO = "outro"
    UNKNOWN = "unknown"


# Map all-in-one labels to trance terminology
# all-in-one uses pop terminology: intro, verse, chorus, bridge, inst, solo, outro, break
TRANCE_LABEL_MAP = {
    'intro': SectionType.INTRO,
    'verse': SectionType.BREAKDOWN,      # In trance, "verse" = melodic breakdown
    'chorus': SectionType.DROP,          # "Chorus" = the main energy section
    'bridge': SectionType.BREAKDOWN,
    'inst': SectionType.DROP,            # Instrumental sections are usually drops
    'solo': SectionType.BREAKDOWN,
    'outro': SectionType.OUTRO,
    'break': SectionType.BREAKDOWN,
}


@dataclass
class Beat:
    """A single beat with timing info."""
    time: float          # Time in seconds
    is_downbeat: bool    # True if this is a downbeat (beat 1)
    bar_number: int      # Which bar this beat belongs to
    beat_in_bar: int     # Which beat within the bar (1-indexed)


@dataclass
class Section:
    """A detected song section."""
    section_type: SectionType
    start_time: float           # Seconds
    end_time: float             # Seconds
    duration_seconds: float
    duration_bars: int          # Estimated bars based on tempo
    confidence: float           # 0-1 detection confidence
    original_label: str         # Original label from detector (before mapping)

    @property
    def duration_formatted(self) -> str:
        """Format duration as MM:SS."""
        mins = int(self.start_time // 60)
        secs = int(self.start_time % 60)
        return f"{mins}:{secs:02d}"

    @property
    def time_range_formatted(self) -> str:
        """Format time range as MM:SS-MM:SS."""
        start_mins = int(self.start_time // 60)
        start_secs = int(self.start_time % 60)
        end_mins = int(self.end_time // 60)
        end_secs = int(self.end_time % 60)
        return f"{start_mins}:{start_secs:02d}-{end_mins}:{end_secs:02d}"


@dataclass
class StructureResult:
    """Complete structure detection result."""
    success: bool
    detection_method: str       # 'allin1' or 'librosa_novelty'
    confidence: float           # Overall confidence (0-1)

    # Tempo and rhythm
    tempo_bpm: float
    beats: List[Beat]
    downbeats: List[float]      # Downbeat times in seconds

    # Sections
    sections: List[Section]
    section_count: int

    # Track info
    duration_seconds: float
    total_bars: int

    # Error info
    error_message: Optional[str] = None

    def get_sections_by_type(self, section_type: SectionType) -> List[Section]:
        """Get all sections of a specific type."""
        return [s for s in self.sections if s.section_type == section_type]

    def get_section_at_time(self, time_seconds: float) -> Optional[Section]:
        """Get the section that contains the given time."""
        for section in self.sections:
            if section.start_time <= time_seconds < section.end_time:
                return section
        return None


@dataclass
class StructureProgress:
    """Progress callback data."""
    stage: str          # 'loading', 'detecting', 'processing', 'complete'
    progress_pct: float # 0-100
    message: str


class StructureDetector:
    """Detects song structure using AI-based analysis."""

    def __init__(self, use_gpu: bool = True, verbose: bool = False):
        """
        Initialize the structure detector.

        Args:
            use_gpu: Use GPU acceleration if available
            verbose: Enable verbose output
        """
        self.use_gpu = use_gpu
        self.verbose = verbose

    def detect(
        self,
        audio_path: str,
        progress_callback: Optional[Callable[[StructureProgress], None]] = None
    ) -> StructureResult:
        """
        Detect song structure from audio file.

        Args:
            audio_path: Path to audio file
            progress_callback: Optional callback for progress updates

        Returns:
            StructureResult with detected sections, beats, and tempo
        """
        path = Path(audio_path)

        if not path.exists():
            return StructureResult(
                success=False,
                detection_method="none",
                confidence=0,
                tempo_bpm=0,
                beats=[],
                downbeats=[],
                sections=[],
                section_count=0,
                duration_seconds=0,
                total_bars=0,
                error_message=f"File not found: {audio_path}"
            )

        # Try all-in-one first, fall back to librosa
        if ALLIN1_AVAILABLE:
            return self._detect_allin1(audio_path, progress_callback)
        else:
            return self._detect_librosa(audio_path, progress_callback)

    def _detect_allin1(
        self,
        audio_path: str,
        progress_callback: Optional[Callable[[StructureProgress], None]] = None
    ) -> StructureResult:
        """Detect structure using all-in-one deep learning model."""

        if progress_callback:
            progress_callback(StructureProgress(
                stage='detecting',
                progress_pct=10,
                message='Analyzing structure with AI model...'
            ))

        try:
            # Run all-in-one analysis
            result = allin1.analyze(
                audio_path,
                include_activations=False,
                include_embeddings=False
            )

            if progress_callback:
                progress_callback(StructureProgress(
                    stage='processing',
                    progress_pct=70,
                    message='Processing detected sections...'
                ))

            # Get duration
            y, sr = librosa.load(audio_path, sr=None, mono=True, duration=10)
            full_duration = librosa.get_duration(path=audio_path)

            # Process beats
            beats = []
            bar_number = 1
            beat_in_bar = 1
            downbeat_set = set(result.downbeats) if result.downbeats else set()

            for beat_time in result.beats:
                is_downbeat = beat_time in downbeat_set
                if is_downbeat and beats:  # New bar
                    bar_number += 1
                    beat_in_bar = 1

                beats.append(Beat(
                    time=float(beat_time),
                    is_downbeat=is_downbeat,
                    bar_number=bar_number,
                    beat_in_bar=beat_in_bar
                ))
                beat_in_bar += 1

            # Process sections with trance label mapping
            sections = []
            for seg in result.segments:
                original_label = seg.label.lower()
                section_type = TRANCE_LABEL_MAP.get(original_label, SectionType.UNKNOWN)

                start_time = float(seg.start)
                end_time = float(seg.end)
                duration = end_time - start_time

                # Estimate bars based on tempo
                if result.bpm and result.bpm > 0:
                    seconds_per_bar = (60 / result.bpm) * 4  # Assuming 4/4 time
                    duration_bars = round(duration / seconds_per_bar)
                else:
                    duration_bars = 0

                sections.append(Section(
                    section_type=section_type,
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=duration,
                    duration_bars=duration_bars,
                    confidence=0.8,  # all-in-one doesn't provide per-section confidence
                    original_label=original_label
                ))

            # Post-process: detect buildups (sections before drops with rising energy)
            sections = self._detect_buildups(sections, audio_path)

            # Calculate total bars
            total_bars = bar_number if beats else 0

            if progress_callback:
                progress_callback(StructureProgress(
                    stage='complete',
                    progress_pct=100,
                    message='Structure detection complete'
                ))

            return StructureResult(
                success=True,
                detection_method='allin1',
                confidence=0.8,
                tempo_bpm=float(result.bpm) if result.bpm else 0,
                beats=beats,
                downbeats=[float(d) for d in result.downbeats] if result.downbeats else [],
                sections=sections,
                section_count=len(sections),
                duration_seconds=full_duration,
                total_bars=total_bars
            )

        except Exception as e:
            if self.verbose:
                print(f"all-in-one failed: {e}, falling back to librosa")
            return self._detect_librosa(audio_path, progress_callback)

    def _detect_librosa(
        self,
        audio_path: str,
        progress_callback: Optional[Callable[[StructureProgress], None]] = None
    ) -> StructureResult:
        """Fallback: detect structure using librosa novelty-based segmentation."""

        if progress_callback:
            progress_callback(StructureProgress(
                stage='loading',
                progress_pct=10,
                message='Loading audio for analysis...'
            ))

        try:
            # Load audio
            y, sr = librosa.load(audio_path, sr=22050, mono=True)
            duration = librosa.get_duration(y=y, sr=sr)

            if progress_callback:
                progress_callback(StructureProgress(
                    stage='detecting',
                    progress_pct=30,
                    message='Detecting tempo and beats...'
                ))

            # Detect tempo and beats
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)

            # Handle tempo as array or scalar
            tempo_value = float(tempo[0]) if hasattr(tempo, '__len__') else float(tempo)

            # Estimate downbeats (every 4 beats for 4/4 time)
            downbeats = []
            beats = []
            bar_number = 1

            for i, beat_time in enumerate(beat_times):
                beat_in_bar = (i % 4) + 1
                is_downbeat = beat_in_bar == 1

                if is_downbeat:
                    downbeats.append(float(beat_time))
                    if i > 0:
                        bar_number += 1

                beats.append(Beat(
                    time=float(beat_time),
                    is_downbeat=is_downbeat,
                    bar_number=bar_number,
                    beat_in_bar=beat_in_bar
                ))

            if progress_callback:
                progress_callback(StructureProgress(
                    stage='detecting',
                    progress_pct=50,
                    message='Detecting section boundaries...'
                ))

            # Compute multiple features for segmentation
            # RMS energy
            rms = librosa.feature.rms(y=y)[0]

            # Spectral centroid (brightness)
            centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]

            # MFCCs for timbral changes
            mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)

            # Onset strength (transient density)
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)

            if progress_callback:
                progress_callback(StructureProgress(
                    stage='processing',
                    progress_pct=70,
                    message='Segmenting sections...'
                ))

            # Build recurrence matrix and find segment boundaries
            # Use beat-synchronous features
            beat_rms = librosa.util.sync(rms, beat_frames)
            beat_centroid = librosa.util.sync(centroid, beat_frames)
            beat_mfcc = librosa.util.sync(mfcc, beat_frames)

            # Stack features
            features = np.vstack([
                librosa.util.normalize(beat_rms),
                librosa.util.normalize(beat_centroid),
                librosa.util.normalize(beat_mfcc)
            ])

            # Compute self-similarity matrix
            rec = librosa.segment.recurrence_matrix(
                features,
                mode='affinity',
                sym=True
            )

            # Compute novelty curve
            novelty = np.diff(np.sum(rec, axis=0))
            novelty = np.concatenate([[0], novelty])
            novelty = np.abs(novelty)

            # Smooth novelty
            kernel_size = max(1, len(novelty) // 50)
            if kernel_size > 1:
                novelty = np.convolve(novelty, np.ones(kernel_size)/kernel_size, mode='same')

            # Find peaks (section boundaries)
            threshold = np.mean(novelty) + 0.5 * np.std(novelty)
            peaks = []
            for i in range(1, len(novelty) - 1):
                if novelty[i] > novelty[i-1] and novelty[i] > novelty[i+1] and novelty[i] > threshold:
                    peaks.append(i)

            # Convert beat indices to times
            boundary_times = [0.0]  # Always start at 0
            for peak_idx in peaks:
                if peak_idx < len(beat_times):
                    boundary_times.append(float(beat_times[peak_idx]))
            boundary_times.append(duration)  # Always end at duration

            # Remove duplicates and sort
            boundary_times = sorted(set(boundary_times))

            # Create sections
            sections = []
            seconds_per_bar = (60 / tempo_value) * 4 if tempo_value > 0 else 8

            for i in range(len(boundary_times) - 1):
                start_time = boundary_times[i]
                end_time = boundary_times[i + 1]
                section_duration = end_time - start_time

                # Skip very short sections
                if section_duration < 4:
                    continue

                # Classify section based on position and energy
                section_type = self._classify_section_librosa(
                    start_time, end_time, duration, y, sr
                )

                duration_bars = round(section_duration / seconds_per_bar)

                sections.append(Section(
                    section_type=section_type,
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=section_duration,
                    duration_bars=duration_bars,
                    confidence=0.6,  # Lower confidence for heuristic method
                    original_label=section_type.value
                ))

            # Post-process: detect buildups
            sections = self._detect_buildups(sections, audio_path)

            if progress_callback:
                progress_callback(StructureProgress(
                    stage='complete',
                    progress_pct=100,
                    message='Structure detection complete'
                ))

            return StructureResult(
                success=True,
                detection_method='librosa_novelty',
                confidence=0.6,
                tempo_bpm=tempo_value,
                beats=beats,
                downbeats=downbeats,
                sections=sections,
                section_count=len(sections),
                duration_seconds=duration,
                total_bars=bar_number
            )

        except Exception as e:
            return StructureResult(
                success=False,
                detection_method='librosa_novelty',
                confidence=0,
                tempo_bpm=0,
                beats=[],
                downbeats=[],
                sections=[],
                section_count=0,
                duration_seconds=0,
                total_bars=0,
                error_message=str(e)
            )

    def _classify_section_librosa(
        self,
        start_time: float,
        end_time: float,
        total_duration: float,
        y: np.ndarray,
        sr: int
    ) -> SectionType:
        """Classify a section based on position and audio features."""

        # Position-based heuristics
        position_ratio = start_time / total_duration

        # Intro: first 10% of track
        if position_ratio < 0.1:
            return SectionType.INTRO

        # Outro: last 10% of track
        if position_ratio > 0.9:
            return SectionType.OUTRO

        # Get section audio
        start_sample = int(start_time * sr)
        end_sample = int(end_time * sr)
        section_audio = y[start_sample:end_sample]

        if len(section_audio) == 0:
            return SectionType.UNKNOWN

        # Compute energy
        rms = np.sqrt(np.mean(section_audio ** 2))
        rms_db = 20 * np.log10(rms + 1e-10)

        # Compute transient density (onset rate)
        onset_env = librosa.onset.onset_strength(y=section_audio, sr=sr)
        onset_rate = np.sum(onset_env > np.mean(onset_env) + np.std(onset_env)) / len(onset_env)

        # Classification based on energy and transients
        # High energy + high transients = drop
        # Low energy + low transients = breakdown
        if rms_db > -15 and onset_rate > 0.1:
            return SectionType.DROP
        elif rms_db < -20 and onset_rate < 0.08:
            return SectionType.BREAKDOWN
        else:
            return SectionType.UNKNOWN

    def _detect_buildups(
        self,
        sections: List[Section],
        audio_path: str
    ) -> List[Section]:
        """
        Post-process sections to detect buildups.

        A buildup is a section that:
        1. Comes directly before a drop
        2. Has rising energy profile
        3. Is relatively short (4-16 bars typically)
        """
        if not sections:
            return sections

        # Load audio for energy analysis
        try:
            y, sr = librosa.load(audio_path, sr=22050, mono=True)
        except Exception:
            return sections

        new_sections = []

        for i, section in enumerate(sections):
            # Check if next section is a drop
            is_before_drop = (
                i < len(sections) - 1 and
                sections[i + 1].section_type == SectionType.DROP
            )

            # If current section is unknown/breakdown and before a drop, check if it's a buildup
            if is_before_drop and section.section_type in [SectionType.UNKNOWN, SectionType.BREAKDOWN]:
                # Analyze energy trend in this section
                start_sample = int(section.start_time * sr)
                end_sample = int(section.end_time * sr)
                section_audio = y[start_sample:end_sample]

                if len(section_audio) > sr:  # At least 1 second
                    # Split into first and second half
                    mid = len(section_audio) // 2
                    first_half_rms = np.sqrt(np.mean(section_audio[:mid] ** 2))
                    second_half_rms = np.sqrt(np.mean(section_audio[mid:] ** 2))

                    # If energy is rising, it's likely a buildup
                    if second_half_rms > first_half_rms * 1.2:  # 20% increase
                        section = Section(
                            section_type=SectionType.BUILDUP,
                            start_time=section.start_time,
                            end_time=section.end_time,
                            duration_seconds=section.duration_seconds,
                            duration_bars=section.duration_bars,
                            confidence=section.confidence,
                            original_label=section.original_label
                        )

            new_sections.append(section)

        return new_sections


def detect_structure(audio_path: str) -> StructureResult:
    """Quick function to detect song structure."""
    detector = StructureDetector()
    return detector.detect(audio_path)
