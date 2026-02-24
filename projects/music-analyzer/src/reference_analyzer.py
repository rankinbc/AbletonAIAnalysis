"""
Reference Analyzer Module

Performs standalone analysis of reference tracks to extract production roadmaps.
Combines structure detection with per-section metrics analysis.

Output includes:
- Song structure (sections, beats, tempo)
- Per-section audio metrics (loudness, frequency, stereo, dynamics)
- Arrangement analysis (stem activity per section)
- Production targets (what to aim for in your own mix)
- AI-ready summary for production guidance
"""

import json
import numpy as np
import librosa
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path
from datetime import datetime

# Handle both relative and absolute import contexts
try:
    from .structure_detector import (
        StructureDetector, StructureResult, Section, SectionType
    )
    from .audio_analyzer import AudioAnalyzer
    from .stem_separator import StemSeparator, StemType, DEMUCS_AVAILABLE
except ImportError:
    from structure_detector import (
        StructureDetector, StructureResult, Section, SectionType
    )
    from audio_analyzer import AudioAnalyzer
    from stem_separator import StemSeparator, StemType, DEMUCS_AVAILABLE


@dataclass
class MelodyNote:
    """A single detected melody note."""
    start_time: float
    end_time: float
    pitch_hz: float
    pitch_midi: int
    pitch_name: str
    confidence: float


@dataclass
class MelodyMetrics:
    """Melody metrics for a section or full track."""
    # Detection info
    detected: bool
    confidence: float

    # Pitch statistics
    pitch_range_semitones: int
    lowest_note: Optional[str]
    highest_note: Optional[str]
    avg_pitch_hz: float
    pitch_std_hz: float

    # Note statistics
    note_count: int
    note_density_per_bar: float
    avg_note_duration_ms: float

    # Interval distribution (semitones -> count)
    interval_distribution: Dict[int, int]
    most_common_intervals: List[int]

    # Contour analysis
    contour_direction: str  # 'ascending', 'descending', 'arch', 'wave', 'flat'
    contour_complexity: float  # 0-1, how much the melody changes direction

    # Scale/mode analysis
    detected_scale: Optional[str]
    scale_confidence: float
    in_scale_percentage: float

    # Phrase analysis
    phrase_count: int
    avg_phrase_length_bars: float

    # Raw pitch contour (downsampled for JSON)
    pitch_contour_hz: List[float]
    pitch_contour_times: List[float]


@dataclass
class MelodyAnalysis:
    """Complete melody analysis for the track."""
    # Overall melody metrics
    overall: MelodyMetrics

    # Per-section melody metrics
    by_section: Dict[int, MelodyMetrics]  # section_index -> metrics

    # Extracted notes (limited for JSON size)
    notes: List[MelodyNote]

    # Analysis metadata
    extraction_method: str  # 'pyin', 'crepe', etc.
    source: str  # 'full_mix', 'other_stem', 'vocals_stem'


@dataclass
class SectionMetrics:
    """Audio metrics for a single section."""
    # Identification
    section_type: str
    section_index: int
    start_time: float
    end_time: float
    duration_seconds: float
    duration_bars: int

    # Loudness
    rms_db: float
    peak_db: float
    lufs: float
    dynamic_range_db: float

    # Frequency
    spectral_centroid_hz: float
    spectral_rolloff_hz: float
    frequency_bands: Dict[str, float]  # band_name -> energy percentage

    # Stereo
    stereo_width_pct: float
    correlation: float

    # Rhythm
    transient_density: float  # transients per second
    has_kick: bool  # detected kick presence

    # Comparison to track average
    loudness_vs_average_db: float
    brightness_vs_average_hz: float


@dataclass
class StemActivity:
    """Stem presence/activity throughout the track."""
    stem_name: str
    active_regions: List[Dict[str, float]]  # list of {start, end, avg_db}
    total_active_time: float
    active_percentage: float
    peak_section: Optional[str]  # section where this stem is loudest


@dataclass
class BuildupPattern:
    """Detected buildup pattern before a drop."""
    pattern_type: str  # 'riser', 'snare_roll', 'filter_sweep', 'energy_rise'
    start_time: float
    end_time: float
    intensity: float  # 0-1


@dataclass
class ArrangementAnalysis:
    """Analysis of arrangement and element timing."""
    stems: Dict[str, StemActivity]
    layering_density: List[Dict[str, Any]]  # time-series of active stem count
    buildup_patterns: List[BuildupPattern]
    element_introductions: List[Dict[str, Any]]  # when each element first appears


@dataclass
class ProductionTargets:
    """Extracted production targets to match this reference."""
    by_section_type: Dict[str, Dict[str, Any]]  # section_type -> target metrics
    overall: Dict[str, Any]  # track-wide targets
    contrasts: Dict[str, Any]  # drop vs breakdown contrast, etc.


@dataclass
class ReferenceAnalysisResult:
    """Complete standalone reference track analysis."""
    # Metadata
    success: bool
    source_file: str
    analysis_timestamp: str
    analyzer_version: str

    # Global metrics
    duration_seconds: float
    tempo_bpm: float
    key: Optional[str]
    integrated_lufs: float
    dynamic_range_db: float

    # Structure
    structure: StructureResult
    section_count: int
    sections_by_type: Dict[str, int]  # section_type -> count

    # Per-section analysis
    section_metrics: List[SectionMetrics]

    # Arrangement (optional - requires stem separation)
    arrangement: Optional[ArrangementAnalysis]

    # Melody analysis (optional - requires include_melody=True)
    melody_analysis: Optional[MelodyAnalysis]

    # Production targets
    production_targets: ProductionTargets

    # AI summary
    ai_summary: Dict[str, Any]

    # Error info
    error_message: Optional[str] = None

    def _serialize_melody(self) -> Dict:
        """Serialize melody analysis for JSON."""
        if not self.melody_analysis:
            return None

        ma = self.melody_analysis
        return {
            'overall': asdict(ma.overall),
            'by_section': {
                str(idx): asdict(metrics)
                for idx, metrics in ma.by_section.items()
            },
            'notes': [asdict(n) for n in ma.notes[:500]],  # Limit notes for JSON size
            'extraction_method': ma.extraction_method,
            'source': ma.source,
        }

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            'metadata': {
                'success': self.success,
                'source_file': self.source_file,
                'analysis_timestamp': self.analysis_timestamp,
                'analyzer_version': self.analyzer_version,
            },
            'global_metrics': {
                'duration_seconds': self.duration_seconds,
                'tempo_bpm': self.tempo_bpm,
                'key': self.key,
                'integrated_lufs': self.integrated_lufs,
                'dynamic_range_db': self.dynamic_range_db,
            },
            'structure': {
                'detection_method': self.structure.detection_method,
                'confidence': self.structure.confidence,
                'total_bars': self.structure.total_bars,
                'section_count': self.section_count,
                'sections_by_type': self.sections_by_type,
                'sections': [
                    {
                        'label': s.section_type.value,
                        'start_time': s.start_time,
                        'end_time': s.end_time,
                        'duration_seconds': s.duration_seconds,
                        'duration_bars': s.duration_bars,
                        'original_label': s.original_label,
                    }
                    for s in self.structure.sections
                ],
                'beats': [b.time for b in self.structure.beats[:100]],  # Limit for JSON size
                'downbeats': self.structure.downbeats[:50],
            },
            'section_analysis': [asdict(sm) for sm in self.section_metrics],
            'arrangement': None,  # TODO: serialize if present
            'melody_analysis': self._serialize_melody() if self.melody_analysis else None,
            'production_targets': {
                'by_section_type': self.production_targets.by_section_type,
                'overall': self.production_targets.overall,
                'contrasts': self.production_targets.contrasts,
            },
            'ai_summary': self.ai_summary,
        }

        if self.error_message:
            result['error'] = self.error_message

        return result

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, output_path: str):
        """Save analysis to JSON file."""
        with open(output_path, 'w') as f:
            f.write(self.to_json())


@dataclass
class AnalysisProgress:
    """Progress callback data."""
    stage: str
    progress_pct: float
    message: str


class ReferenceAnalyzer:
    """Analyzes reference tracks to extract production roadmaps."""

    VERSION = "2.0.0"

    def __init__(
        self,
        include_stems: bool = False,
        include_melody: bool = False,
        verbose: bool = False,
        config=None
    ):
        """
        Initialize the reference analyzer.

        Args:
            include_stems: Whether to separate and analyze stems (slower but more detailed)
            include_melody: Whether to extract melody/pitch data (adds processing time)
            verbose: Enable verbose output
            config: Optional config object
        """
        self.include_stems = include_stems
        self.include_melody = include_melody
        self.verbose = verbose
        self.config = config

        self.structure_detector = StructureDetector(verbose=verbose)
        self.audio_analyzer = AudioAnalyzer(verbose=verbose, config=config)

        if include_stems and DEMUCS_AVAILABLE:
            self.stem_separator = StemSeparator(verbose=verbose)
        else:
            self.stem_separator = None

    def analyze(
        self,
        audio_path: str,
        progress_callback: Optional[Callable[[AnalysisProgress], None]] = None
    ) -> ReferenceAnalysisResult:
        """
        Perform standalone analysis of a reference track.

        Args:
            audio_path: Path to audio file
            progress_callback: Optional callback for progress updates

        Returns:
            ReferenceAnalysisResult with complete analysis
        """
        path = Path(audio_path)

        if not path.exists():
            return self._error_result(audio_path, f"File not found: {audio_path}")

        try:
            # Stage 1: Detect structure
            if progress_callback:
                progress_callback(AnalysisProgress(
                    stage='structure',
                    progress_pct=10,
                    message='Detecting song structure...'
                ))

            structure = self.structure_detector.detect(audio_path)

            if not structure.success:
                return self._error_result(
                    audio_path,
                    f"Structure detection failed: {structure.error_message}"
                )

            # Stage 2: Load audio and compute global metrics
            if progress_callback:
                progress_callback(AnalysisProgress(
                    stage='global',
                    progress_pct=30,
                    message='Analyzing global metrics...'
                ))

            y, sr = librosa.load(audio_path, sr=22050, mono=False)

            # Handle mono vs stereo
            if len(y.shape) == 1:
                y_mono = y
                y_stereo = np.vstack([y, y])
            else:
                y_mono = librosa.to_mono(y)
                y_stereo = y

            # Global metrics
            global_rms = np.sqrt(np.mean(y_mono ** 2))
            global_rms_db = 20 * np.log10(global_rms + 1e-10)
            global_peak_db = 20 * np.log10(np.max(np.abs(y_mono)) + 1e-10)
            global_dynamic_range = global_peak_db - global_rms_db

            # Estimate LUFS (approximate)
            integrated_lufs = global_rms_db - 0.691

            # Global spectral centroid
            global_centroid = float(np.mean(librosa.feature.spectral_centroid(y=y_mono, sr=sr)))

            # Key detection (if available)
            try:
                chroma = librosa.feature.chroma_cqt(y=y_mono, sr=sr)
                key_idx = np.argmax(np.mean(chroma, axis=1))
                key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
                detected_key = key_names[key_idx]
            except Exception:
                detected_key = None

            # Stage 3: Analyze each section
            if progress_callback:
                progress_callback(AnalysisProgress(
                    stage='sections',
                    progress_pct=50,
                    message='Analyzing sections...'
                ))

            section_metrics = []
            for i, section in enumerate(structure.sections):
                metrics = self._analyze_section(
                    section, i, y_mono, y_stereo, sr,
                    global_rms_db, global_centroid
                )
                section_metrics.append(metrics)

            # Stage 4: Arrangement analysis (if stems enabled)
            arrangement = None
            separated_stems = None
            if self.include_stems and self.stem_separator:
                if progress_callback:
                    progress_callback(AnalysisProgress(
                        stage='stems',
                        progress_pct=60,
                        message='Separating and analyzing stems (this may take a while)...'
                    ))
                # Store stems result for potential melody analysis
                try:
                    separation = self.stem_separator.separate(audio_path)
                    if separation.success:
                        separated_stems = separation.stems
                except Exception:
                    pass
                arrangement = self._analyze_arrangement(audio_path, structure)

            # Stage 5: Melody analysis (if enabled)
            melody_analysis = None
            if self.include_melody:
                if progress_callback:
                    progress_callback(AnalysisProgress(
                        stage='melody',
                        progress_pct=75,
                        message='Extracting melody data...'
                    ))
                melody_analysis = self._analyze_melody(
                    audio_path, y_mono, sr, structure, separated_stems
                )

            # Stage 6: Generate production targets
            if progress_callback:
                progress_callback(AnalysisProgress(
                    stage='targets',
                    progress_pct=88,
                    message='Generating production targets...'
                ))

            production_targets = self._generate_production_targets(
                section_metrics, structure
            )

            # Stage 7: Generate AI summary
            if progress_callback:
                progress_callback(AnalysisProgress(
                    stage='summary',
                    progress_pct=95,
                    message='Generating summary...'
                ))

            ai_summary = self._generate_ai_summary(
                structure, section_metrics, production_targets
            )

            # Count sections by type
            sections_by_type = {}
            for section in structure.sections:
                stype = section.section_type.value
                sections_by_type[stype] = sections_by_type.get(stype, 0) + 1

            if progress_callback:
                progress_callback(AnalysisProgress(
                    stage='complete',
                    progress_pct=100,
                    message='Analysis complete'
                ))

            return ReferenceAnalysisResult(
                success=True,
                source_file=str(path.absolute()),
                analysis_timestamp=datetime.now().isoformat(),
                analyzer_version=self.VERSION,
                duration_seconds=structure.duration_seconds,
                tempo_bpm=structure.tempo_bpm,
                key=detected_key,
                integrated_lufs=integrated_lufs,
                dynamic_range_db=global_dynamic_range,
                structure=structure,
                section_count=len(structure.sections),
                sections_by_type=sections_by_type,
                section_metrics=section_metrics,
                arrangement=arrangement,
                melody_analysis=melody_analysis,
                production_targets=production_targets,
                ai_summary=ai_summary
            )

        except Exception as e:
            return self._error_result(audio_path, str(e))

    def _analyze_section(
        self,
        section: Section,
        index: int,
        y_mono: np.ndarray,
        y_stereo: np.ndarray,
        sr: int,
        global_rms_db: float,
        global_centroid: float
    ) -> SectionMetrics:
        """Analyze a single section."""

        start_sample = int(section.start_time * sr)
        end_sample = int(section.end_time * sr)

        # Extract section audio
        section_mono = y_mono[start_sample:end_sample]

        if y_stereo.shape[0] == 2:
            section_left = y_stereo[0, start_sample:end_sample]
            section_right = y_stereo[1, start_sample:end_sample]
        else:
            section_left = section_mono
            section_right = section_mono

        # Loudness metrics
        rms = np.sqrt(np.mean(section_mono ** 2))
        rms_db = 20 * np.log10(rms + 1e-10)
        peak_db = 20 * np.log10(np.max(np.abs(section_mono)) + 1e-10)
        dynamic_range = peak_db - rms_db
        lufs = rms_db - 0.691  # Approximate LUFS

        # Frequency metrics
        centroid = float(np.mean(librosa.feature.spectral_centroid(y=section_mono, sr=sr)))
        rolloff = float(np.mean(librosa.feature.spectral_rolloff(y=section_mono, sr=sr)))

        # Frequency bands
        freq_bands = self._compute_frequency_bands(section_mono, sr)

        # Stereo metrics
        correlation, width = self._compute_stereo_metrics(section_left, section_right)

        # Transient density
        onset_env = librosa.onset.onset_strength(y=section_mono, sr=sr)
        onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
        transient_count = len(onset_frames)
        transient_density = transient_count / section.duration_seconds if section.duration_seconds > 0 else 0

        # Kick detection (check for strong low-frequency transients)
        has_kick = self._detect_kick_presence(section_mono, sr)

        return SectionMetrics(
            section_type=section.section_type.value,
            section_index=index,
            start_time=section.start_time,
            end_time=section.end_time,
            duration_seconds=section.duration_seconds,
            duration_bars=section.duration_bars,
            rms_db=round(rms_db, 2),
            peak_db=round(peak_db, 2),
            lufs=round(lufs, 2),
            dynamic_range_db=round(dynamic_range, 2),
            spectral_centroid_hz=round(centroid, 1),
            spectral_rolloff_hz=round(rolloff, 1),
            frequency_bands=freq_bands,
            stereo_width_pct=round(width * 100, 1),
            correlation=round(correlation, 3),
            transient_density=round(transient_density, 2),
            has_kick=has_kick,
            loudness_vs_average_db=round(rms_db - global_rms_db, 2),
            brightness_vs_average_hz=round(centroid - global_centroid, 1)
        )

    def _compute_frequency_bands(self, y: np.ndarray, sr: int) -> Dict[str, float]:
        """Compute energy distribution across frequency bands."""

        # Compute spectrum
        D = np.abs(librosa.stft(y))
        freqs = librosa.fft_frequencies(sr=sr)

        # Define bands
        bands = {
            'sub_bass': (20, 60),
            'bass': (60, 200),
            'low_mid': (200, 500),
            'mid': (500, 2000),
            'high_mid': (2000, 6000),
            'high': (6000, 20000),
        }

        # Compute energy per band
        total_energy = np.sum(D ** 2)
        band_energies = {}

        for band_name, (low, high) in bands.items():
            mask = (freqs >= low) & (freqs < high)
            band_energy = np.sum(D[mask] ** 2)
            percentage = (band_energy / total_energy * 100) if total_energy > 0 else 0
            band_energies[band_name] = round(percentage, 1)

        return band_energies

    def _compute_stereo_metrics(
        self,
        left: np.ndarray,
        right: np.ndarray
    ) -> tuple:
        """Compute stereo correlation and width."""

        if len(left) != len(right) or len(left) == 0:
            return 1.0, 0.0

        # Correlation
        correlation = np.corrcoef(left, right)[0, 1]
        if np.isnan(correlation):
            correlation = 1.0

        # Width estimate (based on correlation)
        # correlation=1 -> width=0 (mono)
        # correlation=0 -> width=1 (fully uncorrelated)
        # correlation=-1 -> width=1 but out of phase
        width = 1.0 - abs(correlation)

        return float(correlation), float(width)

    def _detect_kick_presence(self, y: np.ndarray, sr: int) -> bool:
        """Detect if kick drum is present in section."""

        # Look for strong low-frequency transients
        # Filter to low frequencies
        y_low = librosa.effects.preemphasis(y, coef=-0.97)  # Boost lows

        # Get onset strength in low frequencies
        onset_env = librosa.onset.onset_strength(
            y=y_low, sr=sr,
            aggregate=np.median,
            fmax=150  # Focus on kick range
        )

        # Check if there are regular strong onsets
        peaks = librosa.util.peak_pick(
            onset_env,
            pre_max=3, post_max=3,
            pre_avg=3, post_avg=5,
            delta=0.3, wait=10
        )

        # If we have regular peaks, likely has kick
        return len(peaks) > 4

    def _analyze_arrangement(
        self,
        audio_path: str,
        structure: StructureResult
    ) -> Optional[ArrangementAnalysis]:
        """Analyze arrangement by separating stems."""

        if not self.stem_separator:
            return None

        try:
            # Separate stems
            separation = self.stem_separator.separate(audio_path)
            if not separation.success:
                return None

            # Analyze each stem's activity across sections
            stems = {}
            for stem_type, stem_info in separation.stems.items():
                activity = self._analyze_stem_activity(
                    stem_info.file_path,
                    structure
                )
                stems[stem_type.value] = activity

            # Compute layering density
            layering_density = self._compute_layering_density(stems, structure)

            # Detect buildup patterns
            buildup_patterns = self._detect_buildup_patterns(audio_path, structure)

            return ArrangementAnalysis(
                stems=stems,
                layering_density=layering_density,
                buildup_patterns=buildup_patterns,
                element_introductions=[]  # TODO: implement
            )

        except Exception as e:
            if self.verbose:
                print(f"Arrangement analysis failed: {e}")
            return None

    def _analyze_stem_activity(
        self,
        stem_path: str,
        structure: StructureResult
    ) -> StemActivity:
        """Analyze when a stem is active throughout the track."""

        y, sr = librosa.load(stem_path, sr=22050, mono=True)

        # Compute RMS over time
        frame_length = int(sr * 0.5)  # 0.5 second frames
        hop_length = frame_length // 2
        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
        rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
        rms_db = 20 * np.log10(rms + 1e-10)

        # Threshold for "active" (-40dB)
        threshold_db = -40

        # Find active regions
        active_regions = []
        in_region = False
        region_start = 0

        for i, (time, db) in enumerate(zip(rms_times, rms_db)):
            if db > threshold_db and not in_region:
                in_region = True
                region_start = time
            elif db <= threshold_db and in_region:
                in_region = False
                active_regions.append({
                    'start': region_start,
                    'end': time,
                    'avg_db': float(np.mean(rms_db[max(0, i-10):i]))
                })

        # Close final region if still active
        if in_region:
            active_regions.append({
                'start': region_start,
                'end': float(rms_times[-1]),
                'avg_db': float(np.mean(rms_db[-10:]))
            })

        # Calculate totals
        total_active_time = sum(r['end'] - r['start'] for r in active_regions)
        active_percentage = (total_active_time / structure.duration_seconds * 100) if structure.duration_seconds > 0 else 0

        # Find peak section
        peak_section = None
        peak_db = -100
        for section in structure.sections:
            start_idx = np.searchsorted(rms_times, section.start_time)
            end_idx = np.searchsorted(rms_times, section.end_time)
            section_avg_db = float(np.mean(rms_db[start_idx:end_idx])) if end_idx > start_idx else -100
            if section_avg_db > peak_db:
                peak_db = section_avg_db
                peak_section = section.section_type.value

        return StemActivity(
            stem_name=Path(stem_path).stem,
            active_regions=active_regions,
            total_active_time=total_active_time,
            active_percentage=round(active_percentage, 1),
            peak_section=peak_section
        )

    def _compute_layering_density(
        self,
        stems: Dict[str, StemActivity],
        structure: StructureResult
    ) -> List[Dict[str, Any]]:
        """Compute how many stems are active at each time point."""

        # Sample every 0.5 seconds
        time_points = np.arange(0, structure.duration_seconds, 0.5)
        density = []

        for t in time_points:
            active_count = 0
            active_stems = []

            for stem_name, activity in stems.items():
                for region in activity.active_regions:
                    if region['start'] <= t < region['end']:
                        active_count += 1
                        active_stems.append(stem_name)
                        break

            density.append({
                'time': float(t),
                'active_count': active_count,
                'active_stems': active_stems
            })

        return density

    def _detect_buildup_patterns(
        self,
        audio_path: str,
        structure: StructureResult
    ) -> List[BuildupPattern]:
        """Detect buildup patterns (risers, snare rolls, filter sweeps)."""

        patterns = []

        # Find buildup sections
        for i, section in enumerate(structure.sections):
            if section.section_type == SectionType.BUILDUP:
                # Load section audio
                y, sr = librosa.load(
                    audio_path, sr=22050, mono=True,
                    offset=section.start_time,
                    duration=section.duration_seconds
                )

                # Check for rising spectral centroid (riser)
                centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
                if len(centroid) > 10:
                    first_half = np.mean(centroid[:len(centroid)//2])
                    second_half = np.mean(centroid[len(centroid)//2:])
                    if second_half > first_half * 1.3:
                        patterns.append(BuildupPattern(
                            pattern_type='riser',
                            start_time=section.start_time,
                            end_time=section.end_time,
                            intensity=min(1.0, (second_half / first_half - 1))
                        ))

                # Check for increasing transient density (snare roll)
                onset_env = librosa.onset.onset_strength(y=y, sr=sr)
                if len(onset_env) > 10:
                    first_half_density = np.mean(onset_env[:len(onset_env)//2])
                    second_half_density = np.mean(onset_env[len(onset_env)//2:])
                    if second_half_density > first_half_density * 1.5:
                        patterns.append(BuildupPattern(
                            pattern_type='snare_roll',
                            start_time=section.start_time,
                            end_time=section.end_time,
                            intensity=min(1.0, (second_half_density / first_half_density - 1))
                        ))

        return patterns

    def _generate_production_targets(
        self,
        section_metrics: List[SectionMetrics],
        structure: StructureResult
    ) -> ProductionTargets:
        """Generate production targets from analyzed sections."""

        # Group metrics by section type
        by_type: Dict[str, List[SectionMetrics]] = {}
        for sm in section_metrics:
            if sm.section_type not in by_type:
                by_type[sm.section_type] = []
            by_type[sm.section_type].append(sm)

        # Calculate targets per section type
        targets_by_type = {}
        for stype, metrics_list in by_type.items():
            targets_by_type[stype] = {
                'target_rms_db': round(np.mean([m.rms_db for m in metrics_list]), 1),
                'target_lufs': round(np.mean([m.lufs for m in metrics_list]), 1),
                'target_spectral_centroid_hz': round(np.mean([m.spectral_centroid_hz for m in metrics_list]), 0),
                'target_stereo_width_pct': round(np.mean([m.stereo_width_pct for m in metrics_list]), 0),
                'target_transient_density': round(np.mean([m.transient_density for m in metrics_list]), 1),
                'has_kick': any(m.has_kick for m in metrics_list),
                'avg_frequency_bands': {
                    band: round(np.mean([m.frequency_bands.get(band, 0) for m in metrics_list]), 1)
                    for band in ['sub_bass', 'bass', 'low_mid', 'mid', 'high_mid', 'high']
                }
            }

        # Calculate overall targets
        all_rms = [m.rms_db for m in section_metrics]
        all_centroid = [m.spectral_centroid_hz for m in section_metrics]

        overall = {
            'tempo_bpm': structure.tempo_bpm,
            'avg_rms_db': round(np.mean(all_rms), 1),
            'rms_range_db': round(max(all_rms) - min(all_rms), 1),
            'avg_spectral_centroid_hz': round(np.mean(all_centroid), 0),
        }

        # Calculate contrasts
        contrasts = {}

        drop_metrics = by_type.get('drop', [])
        breakdown_metrics = by_type.get('breakdown', [])

        if drop_metrics and breakdown_metrics:
            drop_avg_db = np.mean([m.rms_db for m in drop_metrics])
            breakdown_avg_db = np.mean([m.rms_db for m in breakdown_metrics])
            contrasts['drop_vs_breakdown_db'] = round(drop_avg_db - breakdown_avg_db, 1)

            drop_avg_width = np.mean([m.stereo_width_pct for m in drop_metrics])
            breakdown_avg_width = np.mean([m.stereo_width_pct for m in breakdown_metrics])
            contrasts['drop_vs_breakdown_width_pct'] = round(breakdown_avg_width - drop_avg_width, 1)

        return ProductionTargets(
            by_section_type=targets_by_type,
            overall=overall,
            contrasts=contrasts
        )

    def _generate_ai_summary(
        self,
        structure: StructureResult,
        section_metrics: List[SectionMetrics],
        production_targets: ProductionTargets
    ) -> Dict[str, Any]:
        """Generate AI-readable summary with actionable insights."""

        insights = []

        # Tempo insight
        insights.append(f"Match tempo at {structure.tempo_bpm:.0f} BPM")

        # Loudness targets
        if 'drop' in production_targets.by_section_type:
            drop_target = production_targets.by_section_type['drop']
            insights.append(f"Target {drop_target['target_rms_db']:.0f} to {drop_target['target_rms_db']+1:.0f} dB RMS in drops")

        # Contrast insight
        if 'drop_vs_breakdown_db' in production_targets.contrasts:
            contrast = production_targets.contrasts['drop_vs_breakdown_db']
            insights.append(f"Energy contrast should be {contrast:.0f} dB between drops and breakdowns")

        # Stereo width insights
        if 'drop' in production_targets.by_section_type:
            drop_width = production_targets.by_section_type['drop']['target_stereo_width_pct']
            insights.append(f"Target {drop_width:.0f}% stereo width in drops")

        if 'breakdown' in production_targets.by_section_type:
            breakdown_width = production_targets.by_section_type['breakdown']['target_stereo_width_pct']
            insights.append(f"Target {breakdown_width:.0f}% stereo width in breakdowns")

        # Kick presence
        drop_metrics = [m for m in section_metrics if m.section_type == 'drop']
        breakdown_metrics = [m for m in section_metrics if m.section_type == 'breakdown']

        if drop_metrics and all(m.has_kick for m in drop_metrics):
            if breakdown_metrics and not any(m.has_kick for m in breakdown_metrics):
                insights.append("Remove kick completely in breakdowns for maximum contrast")
            else:
                insights.append("Kick present in drops")

        # Structure insight
        section_sequence = [s.section_type.value for s in structure.sections]
        insights.append(f"Structure: {' -> '.join(section_sequence)}")

        return {
            'track_character': self._describe_track_character(section_metrics, structure),
            'actionable_insights': insights,
            'key_techniques': self._identify_key_techniques(section_metrics, production_targets)
        }

    def _describe_track_character(
        self,
        section_metrics: List[SectionMetrics],
        structure: StructureResult
    ) -> str:
        """Generate a brief character description of the track."""

        # Analyze energy profile
        drop_metrics = [m for m in section_metrics if m.section_type == 'drop']
        breakdown_metrics = [m for m in section_metrics if m.section_type == 'breakdown']

        if drop_metrics and breakdown_metrics:
            contrast = np.mean([m.rms_db for m in drop_metrics]) - np.mean([m.rms_db for m in breakdown_metrics])
            if contrast > 10:
                energy_desc = "strong emotional contrast"
            elif contrast > 6:
                energy_desc = "moderate energy dynamics"
            else:
                energy_desc = "steady energy flow"
        else:
            energy_desc = "consistent energy"

        # Analyze tempo character
        if structure.tempo_bpm >= 140:
            tempo_desc = "high-energy"
        elif structure.tempo_bpm >= 130:
            tempo_desc = "driving"
        else:
            tempo_desc = "melodic"

        return f"{tempo_desc.capitalize()} trance track with {energy_desc}"

    def _identify_key_techniques(
        self,
        section_metrics: List[SectionMetrics],
        production_targets: ProductionTargets
    ) -> List[str]:
        """Identify key production techniques used in the track."""

        techniques = []

        # Check for kick-only drops
        drop_metrics = [m for m in section_metrics if m.section_type == 'drop']
        breakdown_metrics = [m for m in section_metrics if m.section_type == 'breakdown']

        if drop_metrics and breakdown_metrics:
            if all(m.has_kick for m in drop_metrics) and not any(m.has_kick for m in breakdown_metrics):
                techniques.append("Kick only in drops")

        # Check energy contrast
        if 'drop_vs_breakdown_db' in production_targets.contrasts:
            contrast = production_targets.contrasts['drop_vs_breakdown_db']
            techniques.append(f"{contrast:.0f}dB energy contrast")

        # Check for wide breakdowns
        if 'drop' in production_targets.by_section_type and 'breakdown' in production_targets.by_section_type:
            drop_width = production_targets.by_section_type['drop']['target_stereo_width_pct']
            breakdown_width = production_targets.by_section_type['breakdown']['target_stereo_width_pct']
            if breakdown_width > drop_width + 10:
                techniques.append("Wider stereo in breakdowns")

        return techniques

    # ========================
    # Melody Analysis Methods
    # ========================

    def _analyze_melody(
        self,
        audio_path: str,
        y_mono: np.ndarray,
        sr: int,
        structure: StructureResult,
        separated_stems: Optional[Dict] = None
    ) -> Optional[MelodyAnalysis]:
        """
        Analyze melody from audio using pitch detection.

        Args:
            audio_path: Path to audio file
            y_mono: Mono audio array
            sr: Sample rate
            structure: Detected structure
            separated_stems: Optional pre-separated stems

        Returns:
            MelodyAnalysis or None if detection fails
        """
        try:
            # Decide which audio source to use for melody extraction
            # Prefer 'other' stem (contains synths/leads) if available
            melody_audio = y_mono
            source = 'full_mix'

            if separated_stems and 'other' in separated_stems:
                try:
                    other_path = separated_stems['other'].file_path
                    melody_audio, _ = librosa.load(other_path, sr=sr, mono=True)
                    source = 'other_stem'
                    if self.verbose:
                        print("  Using 'other' stem for melody extraction")
                except Exception:
                    pass

            # Extract pitch contour using pyin
            if self.verbose:
                print("  Extracting pitch contour...")

            f0, voiced_flag, voiced_prob = librosa.pyin(
                melody_audio,
                fmin=librosa.note_to_hz('C2'),
                fmax=librosa.note_to_hz('C7'),
                sr=sr,
                frame_length=2048,
                hop_length=512
            )

            times = librosa.times_like(f0, sr=sr, hop_length=512)

            # Segment into notes
            if self.verbose:
                print("  Segmenting notes...")

            notes = self._segment_notes(f0, voiced_flag, voiced_prob, times)

            if not notes:
                if self.verbose:
                    print("  No melody notes detected")
                return None

            # Analyze overall melody metrics
            if self.verbose:
                print("  Computing melody metrics...")

            overall_metrics = self._compute_melody_metrics(
                notes, f0, times, structure.tempo_bpm, structure.duration_seconds
            )

            # Analyze melody per section
            by_section = {}
            for i, section in enumerate(structure.sections):
                section_notes = [
                    n for n in notes
                    if n.start_time >= section.start_time and n.end_time <= section.end_time
                ]
                if section_notes:
                    # Extract section's pitch contour
                    start_idx = np.searchsorted(times, section.start_time)
                    end_idx = np.searchsorted(times, section.end_time)
                    section_f0 = f0[start_idx:end_idx]
                    section_times = times[start_idx:end_idx]

                    section_metrics = self._compute_melody_metrics(
                        section_notes, section_f0, section_times,
                        structure.tempo_bpm, section.duration_seconds
                    )
                    by_section[i] = section_metrics

            return MelodyAnalysis(
                overall=overall_metrics,
                by_section=by_section,
                notes=notes,
                extraction_method='pyin',
                source=source
            )

        except Exception as e:
            if self.verbose:
                print(f"  Melody analysis failed: {e}")
            return None

    def _segment_notes(
        self,
        f0: np.ndarray,
        voiced_flag: np.ndarray,
        voiced_prob: np.ndarray,
        times: np.ndarray,
        min_note_duration: float = 0.05
    ) -> List[MelodyNote]:
        """Segment pitch contour into discrete notes."""
        notes = []

        # Find voiced regions
        in_note = False
        note_start_idx = 0
        note_pitches = []
        note_probs = []

        for i in range(len(f0)):
            is_voiced = voiced_flag[i] if voiced_flag is not None else (not np.isnan(f0[i]))

            if is_voiced and not np.isnan(f0[i]):
                if not in_note:
                    # Start new note
                    in_note = True
                    note_start_idx = i
                    note_pitches = [f0[i]]
                    note_probs = [voiced_prob[i] if voiced_prob is not None else 0.8]
                else:
                    # Check if pitch jumped significantly (new note)
                    if note_pitches and abs(librosa.hz_to_midi(f0[i]) - librosa.hz_to_midi(note_pitches[-1])) > 1.5:
                        # End current note, start new one
                        note = self._create_note(
                            times[note_start_idx], times[i-1],
                            note_pitches, note_probs
                        )
                        if note and (note.end_time - note.start_time) >= min_note_duration:
                            notes.append(note)
                        # Start new note
                        note_start_idx = i
                        note_pitches = [f0[i]]
                        note_probs = [voiced_prob[i] if voiced_prob is not None else 0.8]
                    else:
                        note_pitches.append(f0[i])
                        note_probs.append(voiced_prob[i] if voiced_prob is not None else 0.8)
            else:
                if in_note:
                    # End current note
                    note = self._create_note(
                        times[note_start_idx], times[i-1],
                        note_pitches, note_probs
                    )
                    if note and (note.end_time - note.start_time) >= min_note_duration:
                        notes.append(note)
                    in_note = False
                    note_pitches = []
                    note_probs = []

        # Close final note if still in one
        if in_note and note_pitches:
            note = self._create_note(
                times[note_start_idx], times[-1],
                note_pitches, note_probs
            )
            if note and (note.end_time - note.start_time) >= min_note_duration:
                notes.append(note)

        return notes

    def _create_note(
        self,
        start_time: float,
        end_time: float,
        pitches: List[float],
        probs: List[float]
    ) -> Optional[MelodyNote]:
        """Create a MelodyNote from a list of pitch values."""
        if not pitches:
            return None

        avg_hz = float(np.median(pitches))
        midi = int(round(librosa.hz_to_midi(avg_hz)))
        note_name = librosa.midi_to_note(midi)
        confidence = float(np.mean(probs))

        return MelodyNote(
            start_time=float(start_time),
            end_time=float(end_time),
            pitch_hz=avg_hz,
            pitch_midi=midi,
            pitch_name=note_name,
            confidence=confidence
        )

    def _compute_melody_metrics(
        self,
        notes: List[MelodyNote],
        f0: np.ndarray,
        times: np.ndarray,
        tempo_bpm: float,
        duration_seconds: float
    ) -> MelodyMetrics:
        """Compute melody metrics from notes and pitch contour."""

        if not notes:
            return self._empty_melody_metrics()

        # Pitch statistics
        midi_values = [n.pitch_midi for n in notes]
        hz_values = [n.pitch_hz for n in notes]

        pitch_range = max(midi_values) - min(midi_values)
        lowest_note = librosa.midi_to_note(min(midi_values))
        highest_note = librosa.midi_to_note(max(midi_values))
        avg_pitch_hz = float(np.mean(hz_values))
        pitch_std_hz = float(np.std(hz_values))

        # Note statistics
        note_count = len(notes)
        bars = (duration_seconds / 60) * tempo_bpm / 4  # Assuming 4/4
        note_density = note_count / bars if bars > 0 else 0

        durations_ms = [(n.end_time - n.start_time) * 1000 for n in notes]
        avg_duration_ms = float(np.mean(durations_ms)) if durations_ms else 0

        # Interval distribution
        intervals = []
        for i in range(1, len(notes)):
            interval = notes[i].pitch_midi - notes[i-1].pitch_midi
            intervals.append(interval)

        interval_dist = {}
        for interval in intervals:
            interval_dist[interval] = interval_dist.get(interval, 0) + 1

        # Most common intervals (sorted by frequency)
        sorted_intervals = sorted(interval_dist.items(), key=lambda x: -x[1])
        most_common = [i[0] for i in sorted_intervals[:5]]

        # Contour analysis
        contour_dir, contour_complexity = self._analyze_contour(notes)

        # Scale detection
        detected_scale, scale_conf, in_scale_pct = self._detect_scale(midi_values)

        # Phrase analysis (simplified: phrases separated by gaps > 1 second)
        phrases = self._detect_phrases(notes)
        phrase_count = len(phrases)
        avg_phrase_bars = (sum(len(p) for p in phrases) / len(phrases) / note_density) if phrases and note_density > 0 else 0

        # Downsample pitch contour for JSON
        valid_f0 = f0[~np.isnan(f0)]
        valid_times = times[~np.isnan(f0)]

        # Keep ~100 points
        step = max(1, len(valid_f0) // 100)
        contour_hz = [float(x) for x in valid_f0[::step]]
        contour_times = [float(x) for x in valid_times[::step]]

        return MelodyMetrics(
            detected=True,
            confidence=float(np.mean([n.confidence for n in notes])),
            pitch_range_semitones=pitch_range,
            lowest_note=lowest_note,
            highest_note=highest_note,
            avg_pitch_hz=avg_pitch_hz,
            pitch_std_hz=pitch_std_hz,
            note_count=note_count,
            note_density_per_bar=round(note_density, 2),
            avg_note_duration_ms=round(avg_duration_ms, 1),
            interval_distribution=interval_dist,
            most_common_intervals=most_common,
            contour_direction=contour_dir,
            contour_complexity=round(contour_complexity, 3),
            detected_scale=detected_scale,
            scale_confidence=round(scale_conf, 3),
            in_scale_percentage=round(in_scale_pct, 1),
            phrase_count=phrase_count,
            avg_phrase_length_bars=round(avg_phrase_bars, 2),
            pitch_contour_hz=contour_hz,
            pitch_contour_times=contour_times
        )

    def _empty_melody_metrics(self) -> MelodyMetrics:
        """Return empty melody metrics when no melody detected."""
        return MelodyMetrics(
            detected=False,
            confidence=0.0,
            pitch_range_semitones=0,
            lowest_note=None,
            highest_note=None,
            avg_pitch_hz=0.0,
            pitch_std_hz=0.0,
            note_count=0,
            note_density_per_bar=0.0,
            avg_note_duration_ms=0.0,
            interval_distribution={},
            most_common_intervals=[],
            contour_direction='flat',
            contour_complexity=0.0,
            detected_scale=None,
            scale_confidence=0.0,
            in_scale_percentage=0.0,
            phrase_count=0,
            avg_phrase_length_bars=0.0,
            pitch_contour_hz=[],
            pitch_contour_times=[]
        )

    def _analyze_contour(self, notes: List[MelodyNote]) -> tuple:
        """Analyze melodic contour direction and complexity."""
        if len(notes) < 3:
            return 'flat', 0.0

        pitches = [n.pitch_midi for n in notes]

        # Calculate direction changes
        directions = []
        for i in range(1, len(pitches)):
            diff = pitches[i] - pitches[i-1]
            if diff > 0:
                directions.append(1)
            elif diff < 0:
                directions.append(-1)
            else:
                directions.append(0)

        # Count direction changes
        changes = sum(1 for i in range(1, len(directions)) if directions[i] != directions[i-1])
        complexity = changes / len(directions) if directions else 0

        # Determine overall contour
        first_third = np.mean(pitches[:len(pitches)//3])
        mid_third = np.mean(pitches[len(pitches)//3:2*len(pitches)//3])
        last_third = np.mean(pitches[2*len(pitches)//3:])

        if first_third < mid_third > last_third:
            contour = 'arch'
        elif first_third > mid_third < last_third:
            contour = 'wave'
        elif first_third < last_third and last_third - first_third > 2:
            contour = 'ascending'
        elif first_third > last_third and first_third - last_third > 2:
            contour = 'descending'
        else:
            contour = 'flat'

        return contour, complexity

    def _detect_scale(self, midi_values: List[int]) -> tuple:
        """Detect the most likely scale from MIDI note values."""
        if not midi_values:
            return None, 0.0, 0.0

        # Pitch classes (0-11)
        pitch_classes = [m % 12 for m in midi_values]
        pc_counts = [0] * 12
        for pc in pitch_classes:
            pc_counts[pc] += 1

        # Define scale templates
        scales = {
            'major': [0, 2, 4, 5, 7, 9, 11],
            'natural_minor': [0, 2, 3, 5, 7, 8, 10],
            'harmonic_minor': [0, 2, 3, 5, 7, 8, 11],
            'melodic_minor': [0, 2, 3, 5, 7, 9, 11],
            'dorian': [0, 2, 3, 5, 7, 9, 10],
            'phrygian': [0, 1, 3, 5, 7, 8, 10],
            'lydian': [0, 2, 4, 6, 7, 9, 11],
            'mixolydian': [0, 2, 4, 5, 7, 9, 10],
        }

        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

        best_match = None
        best_score = 0
        best_root = 0

        for root in range(12):
            for scale_name, intervals in scales.items():
                # Transpose scale to root
                scale_pcs = [(root + i) % 12 for i in intervals]

                # Calculate match score
                in_scale = sum(pc_counts[pc] for pc in scale_pcs)
                total = sum(pc_counts)

                if total > 0:
                    score = in_scale / total
                    if score > best_score:
                        best_score = score
                        best_match = f"{note_names[root]} {scale_name}"
                        best_root = root

        # Calculate in-scale percentage
        if best_match:
            scale_intervals = scales[best_match.split()[1]]
            scale_pcs = [(best_root + i) % 12 for i in scale_intervals]
            in_scale_count = sum(1 for pc in pitch_classes if pc in scale_pcs)
            in_scale_pct = (in_scale_count / len(pitch_classes) * 100) if pitch_classes else 0
        else:
            in_scale_pct = 0

        return best_match, best_score, in_scale_pct

    def _detect_phrases(self, notes: List[MelodyNote], gap_threshold: float = 1.0) -> List[List[MelodyNote]]:
        """Detect melodic phrases separated by gaps."""
        if not notes:
            return []

        phrases = []
        current_phrase = [notes[0]]

        for i in range(1, len(notes)):
            gap = notes[i].start_time - notes[i-1].end_time
            if gap > gap_threshold:
                # New phrase
                phrases.append(current_phrase)
                current_phrase = [notes[i]]
            else:
                current_phrase.append(notes[i])

        if current_phrase:
            phrases.append(current_phrase)

        return phrases

    def _error_result(self, audio_path: str, message: str) -> ReferenceAnalysisResult:
        """Create an error result."""
        return ReferenceAnalysisResult(
            success=False,
            source_file=audio_path,
            analysis_timestamp=datetime.now().isoformat(),
            analyzer_version=self.VERSION,
            duration_seconds=0,
            tempo_bpm=0,
            key=None,
            integrated_lufs=0,
            dynamic_range_db=0,
            structure=StructureResult(
                success=False,
                detection_method='none',
                confidence=0,
                tempo_bpm=0,
                beats=[],
                downbeats=[],
                sections=[],
                section_count=0,
                duration_seconds=0,
                total_bars=0
            ),
            section_count=0,
            sections_by_type={},
            section_metrics=[],
            arrangement=None,
            melody_analysis=None,
            production_targets=ProductionTargets(
                by_section_type={},
                overall={},
                contrasts={}
            ),
            ai_summary={},
            error_message=message
        )


def analyze_reference(
    audio_path: str,
    include_stems: bool = False,
    include_melody: bool = False
) -> ReferenceAnalysisResult:
    """
    Quick function to analyze a reference track.

    Args:
        audio_path: Path to audio file
        include_stems: Whether to separate and analyze stems (slower)
        include_melody: Whether to extract melody/pitch data (adds processing time)

    Returns:
        ReferenceAnalysisResult with complete analysis
    """
    analyzer = ReferenceAnalyzer(
        include_stems=include_stems,
        include_melody=include_melody
    )
    return analyzer.analyze(audio_path)
