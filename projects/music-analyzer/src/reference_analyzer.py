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

from .structure_detector import (
    StructureDetector, StructureResult, Section, SectionType
)
from .audio_analyzer import AudioAnalyzer
from .stem_separator import StemSeparator, StemType, DEMUCS_AVAILABLE


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

    # Production targets
    production_targets: ProductionTargets

    # AI summary
    ai_summary: Dict[str, Any]

    # Error info
    error_message: Optional[str] = None

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
        verbose: bool = False,
        config=None
    ):
        """
        Initialize the reference analyzer.

        Args:
            include_stems: Whether to separate and analyze stems (slower but more detailed)
            verbose: Enable verbose output
            config: Optional config object
        """
        self.include_stems = include_stems
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
            if self.include_stems and self.stem_separator:
                if progress_callback:
                    progress_callback(AnalysisProgress(
                        stage='stems',
                        progress_pct=70,
                        message='Analyzing stems (this may take a while)...'
                    ))
                arrangement = self._analyze_arrangement(audio_path, structure)

            # Stage 5: Generate production targets
            if progress_callback:
                progress_callback(AnalysisProgress(
                    stage='targets',
                    progress_pct=85,
                    message='Generating production targets...'
                ))

            production_targets = self._generate_production_targets(
                section_metrics, structure
            )

            # Stage 6: Generate AI summary
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
            production_targets=ProductionTargets(
                by_section_type={},
                overall={},
                contrasts={}
            ),
            ai_summary={},
            error_message=message
        )


def analyze_reference(audio_path: str, include_stems: bool = False) -> ReferenceAnalysisResult:
    """Quick function to analyze a reference track."""
    analyzer = ReferenceAnalyzer(include_stems=include_stems)
    return analyzer.analyze(audio_path)
