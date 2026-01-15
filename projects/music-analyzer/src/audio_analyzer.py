"""
Audio Analyzer Module

Analyzes single audio files (mixdowns or stems) for:
- Clipping detection
- Dynamic range measurement
- Frequency balance analysis
- Stereo width measurement
- Loudness estimation
- Tempo detection
"""

import numpy as np
import librosa
import soundfile as sf
from scipy import signal
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Any
from pathlib import Path

try:
    import pyloudnorm as pyln
    PYLOUDNORM_AVAILABLE = True
except ImportError:
    PYLOUDNORM_AVAILABLE = False


@dataclass
class ClippingInfo:
    """Information about detected clipping."""
    has_clipping: bool
    clip_count: int
    clip_positions: List[float]  # Times in seconds
    max_peak: float
    severity: str  # 'none', 'minor', 'moderate', 'severe'


@dataclass
class TimestampedIssue:
    """An issue that occurs at a specific time or time range."""
    issue_type: str  # 'clipping', 'frequency_clash', 'low_end_buildup', 'harsh_highs', etc.
    start_time: float  # seconds
    end_time: Optional[float]  # seconds, None for point issues
    severity: str  # 'minor', 'moderate', 'severe'
    message: str
    details: Optional[Dict] = None


@dataclass
class SectionInfo:
    """Information about a detected musical section."""
    section_type: str  # 'intro', 'buildup', 'drop', 'breakdown', 'outro', 'unknown'
    start_time: float  # seconds
    end_time: float  # seconds
    avg_rms_db: float
    peak_db: float
    transient_density: float  # transients per second
    spectral_centroid_hz: float
    issues: List[TimestampedIssue] = field(default_factory=list)
    severity_summary: str = 'clean'  # 'clean', 'minor', 'moderate', 'severe'


@dataclass
class SectionAnalysisResult:
    """Complete time-based section analysis result."""
    sections: List[SectionInfo]
    all_issues: List[TimestampedIssue]
    clipping_timestamps: List[float]
    section_summary: Dict[str, int]  # section_type -> count
    worst_section: Optional[str]  # description of worst section
    timeline_data: Dict  # for visualization


@dataclass
class DynamicsInfo:
    """Dynamic range information."""
    peak_db: float
    rms_db: float
    dynamic_range_db: float
    crest_factor_db: float
    is_over_compressed: bool
    severity: str
    # Enhanced crest factor interpretation
    crest_interpretation: str = ""    # 'very_dynamic', 'good', 'compressed', 'over_compressed'
    recommended_action: str = ""       # What to do about it


@dataclass
class FrequencyInfo:
    """Frequency balance information."""
    spectral_centroid_hz: float
    spectral_rolloff_hz: float
    sub_bass_energy: float  # 20-60 Hz
    bass_energy: float  # 60-250 Hz
    low_mid_energy: float  # 250-500 Hz
    mid_energy: float  # 500-2000 Hz
    high_mid_energy: float  # 2000-6000 Hz
    high_energy: float  # 6000-10000 Hz
    air_energy: float  # 10000-20000 Hz (shimmer and sparkle)
    balance_issues: List[str]
    problem_frequencies: List[Tuple[float, float, str]]  # (start_hz, end_hz, issue)


@dataclass
class StereoInfo:
    """Stereo width information."""
    is_stereo: bool
    correlation: float  # -1 to 1
    width_estimate: float  # 0-100%
    is_mono_compatible: bool
    issues: List[str]
    # Enhanced phase/width interpretation
    width_category: str = ""      # 'mono', 'narrow', 'good', 'wide', 'very_wide', 'out_of_phase'
    phase_safe: bool = True       # True if correlation > 0
    recommended_width: str = ""    # What width to target


@dataclass
class LoudnessInfo:
    """Loudness measurement information."""
    integrated_lufs: float
    short_term_max_lufs: float
    momentary_max_lufs: float
    loudness_range_lu: float
    true_peak_db: float
    # Streaming platform comparisons
    spotify_diff_db: float = 0.0      # Diff from -14 LUFS
    apple_music_diff_db: float = 0.0  # Diff from -16 LUFS
    youtube_diff_db: float = 0.0      # Diff from -14 LUFS
    target_platform: str = "spotify"  # Recommended target


@dataclass
class TransientInfo:
    """Transient detection and analysis information."""
    transient_count: int
    transients_per_second: float
    avg_transient_strength: float    # 0-1 normalized
    peak_transient_strength: float   # 0-1 normalized
    transient_positions: List[float]  # Times in seconds (first 20)
    attack_quality: str              # 'punchy', 'soft', 'average'
    interpretation: str              # Human-readable description


@dataclass
class AnalysisResult:
    """Complete analysis result for an audio file."""
    file_path: str
    duration_seconds: float
    sample_rate: int
    channels: int
    detected_tempo: Optional[float]
    clipping: ClippingInfo
    dynamics: DynamicsInfo
    frequency: FrequencyInfo
    stereo: StereoInfo
    loudness: LoudnessInfo
    transients: Optional[TransientInfo] = None
    # Extended analysis fields (from merged features)
    harmonic: Optional[Any] = None      # HarmonicInfo - key detection and harmonic content
    clarity: Optional[Any] = None       # ClarityInfo - spectral clarity analysis
    spatial: Optional[Any] = None       # SpatialInfo - 3D spatial perception
    surround: Optional[Any] = None      # SurroundInfo - mono/surround compatibility
    playback: Optional[Any] = None      # PlaybackInfo - headphone/speaker optimization
    overall_score: Optional[Any] = None # OverallScoreInfo - weighted quality score
    overall_issues: List[Dict] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    genre_preset: Optional[str] = None
    genre_comparison: Optional[Dict] = None


class AudioAnalyzer:
    """Main audio analysis class."""

    # Default frequency band definitions (Hz) - can be overridden by config
    DEFAULT_FREQ_BANDS = {
        'sub_bass': (20, 60),
        'bass': (60, 250),
        'low_mid': (250, 500),
        'mid': (500, 2000),
        'high_mid': (2000, 6000),
        'high': (6000, 10000),
        'air': (10000, 20000)  # Shimmer and sparkle
    }

    # Default streaming platform loudness targets (LUFS)
    DEFAULT_STREAMING_TARGETS = {
        'spotify': -14.0,
        'apple_music': -16.0,
        'youtube': -14.0,
        'tidal': -14.0,
        'amazon': -14.0,
        'soundcloud': -14.0
    }

    # Default reference loudness for commercial tracks (LUFS)
    DEFAULT_REFERENCE_LOUDNESS = -14.0  # Streaming standard (Spotify)

    # Default crest factor interpretation thresholds
    DEFAULT_CREST_THRESHOLDS = {
        'very_dynamic': 18.0,    # 18+ dB = very dynamic
        'good': 12.0,            # 12-18 dB = good balance
        'compressed': 8.0,       # 8-12 dB = compressed
        'over_compressed': 0.0   # < 8 dB = over-compressed
    }

    # Default stereo correlation interpretation
    DEFAULT_STEREO_THRESHOLDS = {
        'mono': 0.95,            # > 0.95 = essentially mono
        'narrow': 0.7,           # 0.7-0.95 = narrow
        'good': 0.3,             # 0.3-0.7 = good width
        'wide': 0.0,             # 0-0.3 = wide
        'out_of_phase': -1.0     # < 0 = out of phase (CRITICAL)
    }

    def __init__(self, verbose: bool = False, config=None):
        self.verbose = verbose
        self.config = config

        # Load values from config or use defaults
        if config:
            # Frequency bands
            freq_cfg = config.frequency.get('bands', {})
            self.FREQ_BANDS = {
                'sub_bass': tuple(freq_cfg.get('sub_bass', [20, 60])),
                'bass': tuple(freq_cfg.get('bass', [60, 250])),
                'low_mid': tuple(freq_cfg.get('low_mid', [250, 500])),
                'mid': tuple(freq_cfg.get('mid', [500, 2000])),
                'high_mid': tuple(freq_cfg.get('high_mid', [2000, 6000])),
                'high': tuple(freq_cfg.get('high', [6000, 10000])),
                'air': tuple(freq_cfg.get('air', [10000, 20000])),
            }

            # Streaming targets
            platforms = config.loudness.get('platforms', {})
            self.STREAMING_TARGETS = {
                'spotify': platforms.get('spotify', -14.0),
                'apple_music': platforms.get('apple_music', -16.0),
                'youtube': platforms.get('youtube', -14.0),
                'tidal': platforms.get('tidal', -14.0),
                'amazon': platforms.get('amazon', -14.0),
                'soundcloud': platforms.get('soundcloud', -14.0),
            }

            self.REFERENCE_LOUDNESS = config.loudness.get('reference_loudness', -14.0)

            # Crest factor thresholds
            dyn_cfg = config.dynamics
            self.CREST_THRESHOLDS = {
                'very_dynamic': dyn_cfg.get('crest_very_dynamic_threshold', 18.0),
                'good': dyn_cfg.get('crest_good_threshold', 12.0),
                'compressed': dyn_cfg.get('crest_compressed_threshold', 8.0),
                'over_compressed': 0.0,
            }

            # Stereo thresholds
            stereo_cfg = config.stereo
            self.STEREO_THRESHOLDS = {
                'mono': stereo_cfg.get('mono_threshold', 0.95),
                'narrow': stereo_cfg.get('narrow_threshold', 0.7),
                'good': stereo_cfg.get('good_threshold', 0.3),
                'wide': stereo_cfg.get('wide_threshold', 0.0),
                'out_of_phase': -1.0,
            }

            # Store additional config values for use in analysis methods
            self.clipping_threshold = config.clipping.get('threshold', 0.99)
            self.clipping_group_window = config.clipping.get('group_window_seconds', 0.1)
            self.clipping_max_positions = config.clipping.get('max_report_positions', 50)
            self.over_compression_threshold = dyn_cfg.get('over_compression_threshold', 6.0)
            self.mono_compatibility_threshold = stereo_cfg.get('mono_compatibility_threshold', 0.3)
        else:
            self.FREQ_BANDS = self.DEFAULT_FREQ_BANDS.copy()
            self.STREAMING_TARGETS = self.DEFAULT_STREAMING_TARGETS.copy()
            self.REFERENCE_LOUDNESS = self.DEFAULT_REFERENCE_LOUDNESS
            self.CREST_THRESHOLDS = self.DEFAULT_CREST_THRESHOLDS.copy()
            self.STEREO_THRESHOLDS = self.DEFAULT_STEREO_THRESHOLDS.copy()
            self.clipping_threshold = 0.99
            self.clipping_group_window = 0.1
            self.clipping_max_positions = 50
            self.over_compression_threshold = 6.0
            self.mono_compatibility_threshold = 0.3

    def analyze(
        self,
        audio_path: str,
        reference_tempo: Optional[float] = None,
        genre_preset: Optional[str] = None
    ) -> AnalysisResult:
        """
        Perform complete analysis on an audio file.

        Args:
            audio_path: Path to the audio file (WAV, FLAC, etc.)
            reference_tempo: Expected tempo (from project file) for verification
            genre_preset: Genre preset name for target comparison (trance, house, techno, dnb, progressive)

        Returns:
            AnalysisResult with all analysis data
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Load audio
        y, sr = librosa.load(audio_path, sr=None, mono=False)

        # Get original audio for peak detection (soundfile preserves scale)
        audio_data, sr_orig = sf.read(audio_path)

        # Determine if stereo
        is_stereo = len(y.shape) > 1 and y.shape[0] == 2

        # Create mono mix for analysis
        if is_stereo:
            y_mono = librosa.to_mono(y)
        else:
            y_mono = y if len(y.shape) == 1 else y[0]

        duration = librosa.get_duration(y=y_mono, sr=sr)

        # Perform all analyses
        clipping = self._analyze_clipping(audio_data, sr)
        dynamics = self._analyze_dynamics(y_mono, sr)
        frequency = self._analyze_frequency(y_mono, sr)
        stereo = self._analyze_stereo(y, sr) if is_stereo else self._create_mono_stereo_info()
        loudness = self._analyze_loudness(y_mono, sr, audio_data)
        transients = self._analyze_transients(y_mono, sr, duration)

        # Detect tempo
        detected_tempo = self._detect_tempo(y_mono, sr)

        # Extended analysis (merged from ai-music-mix-analyzer)
        harmonic = None
        clarity = None
        spatial = None
        surround = None
        playback = None
        overall_score_result = None

        # Check if extended analyzers should run
        if self.config:
            # Harmonic analysis (key detection)
            if self.config.stage_enabled('harmonic_analysis'):
                try:
                    from analyzers import HarmonicAnalyzer
                    harmonic = HarmonicAnalyzer(self.config).analyze(y_mono, sr)
                except Exception as e:
                    if self.verbose:
                        print(f"Harmonic analysis failed: {e}")

            # Clarity analysis
            if self.config.stage_enabled('clarity_analysis'):
                try:
                    from analyzers import ClarityAnalyzer
                    clarity = ClarityAnalyzer(self.config).analyze(y_mono, sr)
                except Exception as e:
                    if self.verbose:
                        print(f"Clarity analysis failed: {e}")

            # 3D Spatial analysis (optional)
            if self.config.stage_enabled('spatial_analysis'):
                try:
                    from analyzers import SpatialAnalyzer
                    spatial = SpatialAnalyzer(self.config).analyze_3d(y, sr)
                except Exception as e:
                    if self.verbose:
                        print(f"Spatial analysis failed: {e}")

            # Surround compatibility
            if self.config.stage_enabled('surround_analysis'):
                try:
                    from analyzers import SpatialAnalyzer
                    surround = SpatialAnalyzer(self.config).analyze_surround(y, sr)
                except Exception as e:
                    if self.verbose:
                        print(f"Surround analysis failed: {e}")

            # Playback optimization (optional)
            if self.config.stage_enabled('playback_analysis'):
                try:
                    from analyzers import SpatialAnalyzer
                    playback = SpatialAnalyzer(self.config).analyze_playback(y, sr)
                except Exception as e:
                    if self.verbose:
                        print(f"Playback analysis failed: {e}")

        # Compile issues and recommendations
        issues, recommendations = self._compile_issues_and_recommendations(
            clipping, dynamics, frequency, stereo, loudness, transients,
            detected_tempo, reference_tempo
        )

        # Add issues from extended analyzers
        self._add_extended_analysis_issues(
            issues, recommendations, harmonic, clarity, spatial, surround, playback
        )

        # Overall score calculation (must be after other analyses)
        if self.config and self.config.stage_enabled('overall_score'):
            try:
                from analyzers import OverallScoreCalculator
                # Create a temporary result object for score calculation
                temp_result = type('TempResult', (), {
                    'frequency': frequency,
                    'dynamics': dynamics,
                    'stereo': stereo,
                    'loudness': loudness,
                    'transients': transients,
                    'harmonic': harmonic,
                    'clarity': clarity,
                    'surround': surround,
                })()
                overall_score_result = OverallScoreCalculator(self.config).calculate(temp_result)
            except Exception as e:
                if self.verbose:
                    print(f"Overall score calculation failed: {e}")

        # Genre preset comparison (if specified)
        genre_comparison = None
        if genre_preset:
            from genre_presets import check_against_preset
            freq_data = {
                'sub_bass_energy': frequency.sub_bass_energy,
                'bass_energy': frequency.bass_energy,
                'low_mid_energy': frequency.low_mid_energy,
                'mid_energy': frequency.mid_energy,
                'high_mid_energy': frequency.high_mid_energy,
                'high_energy': frequency.high_energy,
                'air_energy': frequency.air_energy
            }
            genre_comparison = check_against_preset(
                genre_preset,
                freq_data,
                loudness.integrated_lufs,
                dynamics.crest_factor_db,
                stereo.correlation
            )

        return AnalysisResult(
            file_path=str(path.absolute()),
            duration_seconds=duration,
            sample_rate=sr,
            channels=2 if is_stereo else 1,
            detected_tempo=detected_tempo,
            clipping=clipping,
            dynamics=dynamics,
            frequency=frequency,
            stereo=stereo,
            loudness=loudness,
            transients=transients,
            harmonic=harmonic,
            clarity=clarity,
            spatial=spatial,
            surround=surround,
            playback=playback,
            overall_score=overall_score_result,
            overall_issues=issues,
            recommendations=recommendations,
            genre_preset=genre_preset,
            genre_comparison=genre_comparison
        )

    def _analyze_clipping(self, audio_data: np.ndarray, sr: int) -> ClippingInfo:
        """Detect clipping in audio data."""
        # Use config threshold or default
        clip_threshold = self.clipping_threshold

        # Find samples that exceed threshold
        if len(audio_data.shape) > 1:
            # Stereo - check both channels
            clipped_samples = np.where(np.abs(audio_data).max(axis=1) >= clip_threshold)[0]
        else:
            clipped_samples = np.where(np.abs(audio_data) >= clip_threshold)[0]

        clip_count = len(clipped_samples)
        max_peak = float(np.abs(audio_data).max())

        # Convert sample positions to time
        clip_positions = []
        if clip_count > 0:
            # Group nearby clips and report unique positions
            clip_times = clipped_samples / sr
            # Group clips within configurable window
            group_window = self.clipping_group_window
            grouped_times = []
            current_group_start = clip_times[0]
            for t in clip_times:
                if t - current_group_start > group_window:
                    grouped_times.append(current_group_start)
                    current_group_start = t
            grouped_times.append(current_group_start)
            # Limit positions to config max (0 = unlimited)
            max_positions = self.clipping_max_positions
            if max_positions > 0:
                clip_positions = grouped_times[:max_positions]
            else:
                clip_positions = grouped_times

        # Determine severity using config thresholds
        minor_threshold = 100
        moderate_threshold = 1000
        if self.config:
            minor_threshold = self.config.clipping.get('severity_minor_threshold', 100)
            moderate_threshold = self.config.clipping.get('severity_moderate_threshold', 1000)

        if clip_count == 0:
            severity = 'none'
        elif clip_count < minor_threshold:
            severity = 'minor'
        elif clip_count < moderate_threshold:
            severity = 'moderate'
        else:
            severity = 'severe'

        return ClippingInfo(
            has_clipping=clip_count > 0,
            clip_count=clip_count,
            clip_positions=clip_positions,
            max_peak=max_peak,
            severity=severity
        )

    def _analyze_dynamics(self, y: np.ndarray, sr: int) -> DynamicsInfo:
        """Analyze dynamic range and compression with enhanced crest factor interpretation."""
        # Calculate peak (dBFS)
        peak = np.max(np.abs(y))
        peak_db = 20 * np.log10(peak + 1e-10)

        # Calculate RMS (dBFS)
        rms = np.sqrt(np.mean(y ** 2))
        rms_db = 20 * np.log10(rms + 1e-10)

        # Dynamic range (difference between peak and RMS)
        dynamic_range_db = peak_db - rms_db

        # Crest factor
        crest_factor_db = dynamic_range_db

        # Check for over-compression
        # Typical modern masters have 6-10 dB crest factor
        # Over-compressed tracks often have < 6 dB
        is_over_compressed = dynamic_range_db < 6.0

        # Enhanced crest factor interpretation
        if crest_factor_db >= self.CREST_THRESHOLDS['very_dynamic']:
            crest_interpretation = 'very_dynamic'
            recommended_action = "Very dynamic mix - consider light limiting if targeting loud streaming platforms"
            severity = 'none'
        elif crest_factor_db >= self.CREST_THRESHOLDS['good']:
            crest_interpretation = 'good'
            recommended_action = "Good dynamic balance - no changes needed"
            severity = 'none'
        elif crest_factor_db >= self.CREST_THRESHOLDS['compressed']:
            crest_interpretation = 'compressed'
            recommended_action = "Compressed but acceptable for modern genres"
            severity = 'minor'
        else:
            crest_interpretation = 'over_compressed'
            target_crest = 12.0
            reduction_needed = target_crest - crest_factor_db
            recommended_action = f"Over-compressed - reduce limiting by ~{reduction_needed:.0f}dB to reach {target_crest:.0f}dB crest factor"
            if crest_factor_db < 4:
                severity = 'severe'
            else:
                severity = 'moderate'

        return DynamicsInfo(
            peak_db=peak_db,
            rms_db=rms_db,
            dynamic_range_db=dynamic_range_db,
            crest_factor_db=crest_factor_db,
            is_over_compressed=is_over_compressed,
            severity=severity,
            crest_interpretation=crest_interpretation,
            recommended_action=recommended_action
        )

    def _analyze_frequency(self, y: np.ndarray, sr: int) -> FrequencyInfo:
        """Analyze frequency balance and identify problem areas."""
        # Compute spectral features
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]

        # Average spectral features
        avg_centroid = float(np.mean(spectral_centroid))
        avg_rolloff = float(np.mean(spectral_rolloff))

        # Compute STFT for band analysis
        n_fft = 4096
        D = np.abs(librosa.stft(y, n_fft=n_fft))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

        # Calculate energy in each frequency band
        def get_band_energy(low: float, high: float) -> float:
            mask = (freqs >= low) & (freqs < high)
            if not np.any(mask):
                return 0.0
            return float(np.mean(D[mask, :] ** 2))

        # Get energy for each band
        sub_bass = get_band_energy(20, 60)
        bass = get_band_energy(60, 250)
        low_mid = get_band_energy(250, 500)
        mid = get_band_energy(500, 2000)
        high_mid = get_band_energy(2000, 6000)
        high = get_band_energy(6000, 10000)
        air = get_band_energy(10000, 20000)

        # Normalize energies to percentages
        total_energy = sub_bass + bass + low_mid + mid + high_mid + high + air + 1e-10
        sub_bass_energy = sub_bass / total_energy * 100
        bass_energy = bass / total_energy * 100
        low_mid_energy = low_mid / total_energy * 100
        mid_energy = mid / total_energy * 100
        high_mid_energy = high_mid / total_energy * 100
        high_energy = high / total_energy * 100
        air_energy = air / total_energy * 100

        # Identify balance issues
        balance_issues = []
        problem_frequencies = []

        # Check for common issues (sub_bass + bass combined for legacy checks)
        combined_bass = sub_bass_energy + bass_energy
        if combined_bass > 45:
            balance_issues.append("Excessive bass energy - mix may sound muddy")
            problem_frequencies.append((20, 250, "excessive_energy"))
        elif combined_bass < 15:
            balance_issues.append("Lacking bass energy - mix may sound thin")
            problem_frequencies.append((20, 250, "lacking_energy"))

        if low_mid_energy > 25:
            balance_issues.append("Low-mid buildup - common 'muddy' frequency range")
            problem_frequencies.append((250, 500, "buildup"))

        if high_energy < 5:
            balance_issues.append("Lacking high frequency content - mix may sound dull")
            problem_frequencies.append((6000, 20000, "lacking_energy"))
        elif high_energy > 25:
            balance_issues.append("Excessive high frequencies - mix may sound harsh")
            problem_frequencies.append((6000, 20000, "excessive_energy"))

        # Check spectral centroid for overall brightness
        if avg_centroid < 1000:
            balance_issues.append("Overall mix is very dark (low spectral centroid)")
        elif avg_centroid > 4000:
            balance_issues.append("Overall mix is very bright (high spectral centroid)")

        return FrequencyInfo(
            spectral_centroid_hz=avg_centroid,
            spectral_rolloff_hz=avg_rolloff,
            sub_bass_energy=sub_bass_energy,
            bass_energy=bass_energy,
            low_mid_energy=low_mid_energy,
            mid_energy=mid_energy,
            high_mid_energy=high_mid_energy,
            high_energy=high_energy,
            air_energy=air_energy,
            balance_issues=balance_issues,
            problem_frequencies=problem_frequencies
        )

    def _analyze_stereo(self, y: np.ndarray, sr: int) -> StereoInfo:
        """Analyze stereo width, phase correlation, and mono compatibility."""
        if len(y.shape) != 2 or y.shape[0] != 2:
            return self._create_mono_stereo_info()

        left = y[0]
        right = y[1]

        # Calculate correlation coefficient
        correlation = float(np.corrcoef(left, right)[0, 1])

        # Estimate stereo width (0-100%)
        # Correlation of 1 = mono (0% width)
        # Correlation of 0 = full stereo (100% width)
        # Correlation of -1 = out of phase (problematic)
        width_estimate = (1 - abs(correlation)) * 100

        # Check mono compatibility
        # If correlation is very low or negative, mono summing will cause issues
        is_mono_compatible = correlation > 0.3

        # Phase safety check
        phase_safe = correlation >= 0

        # Enhanced width category interpretation
        issues = []
        if correlation < 0:
            width_category = 'out_of_phase'
            recommended_width = "CRITICAL: Fix phase issues immediately - check stereo processors, inverted cables, or stereo widening plugins"
            issues.append(f"CRITICAL: Out-of-phase content (correlation: {correlation:.2f}) - will cancel in mono!")
        elif correlation > self.STEREO_THRESHOLDS['mono']:
            width_category = 'mono'
            recommended_width = "Add stereo width using panning, stereo widening (Utility 120-150%), or wider reverbs on pads/synths"
            issues.append(f"Mix is essentially mono (correlation: {correlation:.2f}) - very narrow stereo image")
        elif correlation > self.STEREO_THRESHOLDS['narrow']:
            width_category = 'narrow'
            recommended_width = "Consider widening pads, synths, or reverbs slightly for more spaciousness"
            issues.append(f"Narrow stereo image (correlation: {correlation:.2f}) - could benefit from more width")
        elif correlation > self.STEREO_THRESHOLDS['good']:
            width_category = 'good'
            recommended_width = "Good stereo width - no changes needed"
        elif correlation > self.STEREO_THRESHOLDS['wide']:
            width_category = 'wide'
            recommended_width = "Wide mix - ensure bass and kick are mono-centered for club playback"
            issues.append(f"Wide stereo image (correlation: {correlation:.2f}) - check mono compatibility on bass")
        else:
            width_category = 'very_wide'
            recommended_width = "Very wide mix - may have mono compatibility issues on some playback systems"
            issues.append(f"Very wide stereo (correlation: {correlation:.2f}) - may have mono compatibility issues")

        return StereoInfo(
            is_stereo=True,
            correlation=correlation,
            width_estimate=width_estimate,
            is_mono_compatible=is_mono_compatible,
            issues=issues,
            width_category=width_category,
            phase_safe=phase_safe,
            recommended_width=recommended_width
        )

    def _create_mono_stereo_info(self) -> StereoInfo:
        """Create stereo info for mono files."""
        return StereoInfo(
            is_stereo=False,
            correlation=1.0,
            width_estimate=0.0,
            is_mono_compatible=True,
            issues=["File is mono - no stereo width analysis available"],
            width_category='mono',
            phase_safe=True,
            recommended_width="File is mono - stereo analysis skipped"
        )

    def _analyze_loudness(self, y: np.ndarray, sr: int, audio_data: np.ndarray = None) -> LoudnessInfo:
        """
        Analyze loudness using industry-standard LUFS measurement.
        Uses pyloudnorm for accurate ITU-R BS.1770-4 compliant measurement.
        Falls back to approximation if pyloudnorm is not available.
        """
        if PYLOUDNORM_AVAILABLE:
            try:
                # Create meter with sample rate
                meter = pyln.Meter(sr)

                # For stereo audio, use the original multi-channel data
                if audio_data is not None and len(audio_data.shape) > 1 and audio_data.shape[1] == 2:
                    # Stereo - use full audio data for accurate LUFS
                    integrated_lufs = float(meter.integrated_loudness(audio_data))
                else:
                    # Mono or use y
                    if len(y.shape) == 1:
                        integrated_lufs = float(meter.integrated_loudness(y))
                    else:
                        integrated_lufs = float(meter.integrated_loudness(y.T))

                # True peak measurement (inter-sample peaks)
                if audio_data is not None:
                    true_peak_linear = np.max(np.abs(audio_data))
                else:
                    true_peak_linear = np.max(np.abs(y))
                true_peak_db = float(20 * np.log10(true_peak_linear + 1e-10))

                # For short-term and momentary, we need windowed analysis
                hop_length = int(sr * 0.1)  # 100ms hop
                frame_length = int(sr * 0.4)  # 400ms window (momentary)
                rms = librosa.feature.rms(y=y if len(y.shape) == 1 else y[0], frame_length=frame_length, hop_length=hop_length)[0]
                rms_db = 20 * np.log10(rms + 1e-10)

                # Approximate short-term max (3s windows)
                short_term_window = int(3.0 / 0.1)
                if len(rms_db) >= short_term_window:
                    short_term_values = np.convolve(rms_db, np.ones(short_term_window)/short_term_window, mode='valid')
                    short_term_max_lufs = float(np.max(short_term_values)) - 0.5  # Adjustment for LUFS
                else:
                    short_term_max_lufs = integrated_lufs + 3.0

                # Momentary max
                momentary_max_lufs = float(np.max(rms_db)) - 0.5

                # Loudness range
                loudness_range_lu = float(np.percentile(rms_db, 95) - np.percentile(rms_db, 10))

            except Exception as e:
                # Fallback to approximation if pyloudnorm fails
                return self._analyze_loudness_fallback(y, sr)
        else:
            # Fallback to approximation
            return self._analyze_loudness_fallback(y, sr)

        # Calculate streaming platform differences
        spotify_diff = integrated_lufs - self.STREAMING_TARGETS['spotify']
        apple_diff = integrated_lufs - self.STREAMING_TARGETS['apple_music']
        youtube_diff = integrated_lufs - self.STREAMING_TARGETS['youtube']

        # Determine best target platform based on current loudness
        if integrated_lufs < -18:
            target_platform = "mastering_needed"
        elif integrated_lufs < -16:
            target_platform = "apple_music"
        else:
            target_platform = "spotify"

        return LoudnessInfo(
            integrated_lufs=integrated_lufs,
            short_term_max_lufs=short_term_max_lufs,
            momentary_max_lufs=momentary_max_lufs,
            loudness_range_lu=loudness_range_lu,
            true_peak_db=true_peak_db,
            spotify_diff_db=spotify_diff,
            apple_music_diff_db=apple_diff,
            youtube_diff_db=youtube_diff,
            target_platform=target_platform
        )

    def _analyze_loudness_fallback(self, y: np.ndarray, sr: int) -> LoudnessInfo:
        """Fallback LUFS approximation when pyloudnorm is not available."""
        # Calculate RMS in 400ms windows (momentary)
        hop_length = int(sr * 0.1)  # 100ms hop
        frame_length = int(sr * 0.4)  # 400ms window

        y_mono = y if len(y.shape) == 1 else y[0]
        rms = librosa.feature.rms(y=y_mono, frame_length=frame_length, hop_length=hop_length)[0]
        rms_db = 20 * np.log10(rms + 1e-10)

        # Integrated loudness (average over entire track) with K-weighting approximation
        integrated_lufs = float(np.mean(rms_db)) - 0.691

        # Short-term max (3s windows)
        short_term_window = int(3.0 / 0.1)
        if len(rms_db) >= short_term_window:
            short_term_values = np.convolve(rms_db, np.ones(short_term_window)/short_term_window, mode='valid')
            short_term_max_lufs = float(np.max(short_term_values))
        else:
            short_term_max_lufs = integrated_lufs

        # Momentary max
        momentary_max_lufs = float(np.max(rms_db))

        # Loudness range (simplified)
        loudness_range_lu = float(np.percentile(rms_db, 95) - np.percentile(rms_db, 10))

        # True peak
        true_peak_db = float(20 * np.log10(np.max(np.abs(y_mono)) + 1e-10))

        # Calculate streaming platform differences
        spotify_diff = integrated_lufs - self.STREAMING_TARGETS['spotify']
        apple_diff = integrated_lufs - self.STREAMING_TARGETS['apple_music']
        youtube_diff = integrated_lufs - self.STREAMING_TARGETS['youtube']

        return LoudnessInfo(
            integrated_lufs=integrated_lufs,
            short_term_max_lufs=short_term_max_lufs,
            momentary_max_lufs=momentary_max_lufs,
            loudness_range_lu=loudness_range_lu,
            true_peak_db=true_peak_db,
            spotify_diff_db=spotify_diff,
            apple_music_diff_db=apple_diff,
            youtube_diff_db=youtube_diff,
            target_platform="spotify"
        )

    def _analyze_transients(self, y: np.ndarray, sr: int, duration: float) -> TransientInfo:
        """
        Analyze transients (attacks) in the audio using librosa onset detection.
        Useful for understanding punch/attack quality of the mix.
        """
        try:
            # Detect onsets (transients)
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            onset_frames = librosa.onset.onset_detect(
                y=y, sr=sr, onset_envelope=onset_env, backtrack=False
            )
            onset_times = librosa.frames_to_time(onset_frames, sr=sr)

            transient_count = len(onset_frames)
            transients_per_second = transient_count / duration if duration > 0 else 0

            # Calculate transient strengths
            if len(onset_frames) > 0:
                # Get the onset envelope values at detected onsets
                transient_strengths = onset_env[onset_frames]

                # Normalize to 0-1 range
                max_strength = np.max(onset_env) if np.max(onset_env) > 0 else 1.0
                normalized_strengths = transient_strengths / max_strength

                avg_transient_strength = float(np.mean(normalized_strengths))
                peak_transient_strength = float(np.max(normalized_strengths))
            else:
                avg_transient_strength = 0.0
                peak_transient_strength = 0.0

            # Interpret attack quality
            if avg_transient_strength >= 0.7:
                attack_quality = 'punchy'
                interpretation = f"Punchy transients ({avg_transient_strength:.2f}) - good attack definition"
            elif avg_transient_strength >= 0.4:
                attack_quality = 'average'
                interpretation = f"Average transients ({avg_transient_strength:.2f}) - consider transient shaping for more punch"
            else:
                attack_quality = 'soft'
                interpretation = f"Soft transients ({avg_transient_strength:.2f}) - drums/percussion may lack punch, consider transient enhancement"

            # Get first 20 transient positions for reference
            transient_positions = list(onset_times[:20]) if len(onset_times) > 0 else []

            return TransientInfo(
                transient_count=transient_count,
                transients_per_second=transients_per_second,
                avg_transient_strength=avg_transient_strength,
                peak_transient_strength=peak_transient_strength,
                transient_positions=transient_positions,
                attack_quality=attack_quality,
                interpretation=interpretation
            )

        except Exception as e:
            # Return default values if analysis fails
            return TransientInfo(
                transient_count=0,
                transients_per_second=0.0,
                avg_transient_strength=0.0,
                peak_transient_strength=0.0,
                transient_positions=[],
                attack_quality='unknown',
                interpretation=f"Transient analysis failed: {str(e)}"
            )

    def _detect_tempo(self, y: np.ndarray, sr: int) -> Optional[float]:
        """Detect tempo from audio."""
        try:
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            # Handle both old and new librosa return types
            if isinstance(tempo, np.ndarray):
                return float(tempo[0]) if len(tempo) > 0 else None
            return float(tempo)
        except Exception:
            return None

    def analyze_sections(
        self,
        audio_path: str,
        min_section_length: float = 15.0,
        detect_musical_sections: bool = True
    ) -> SectionAnalysisResult:
        """
        Analyze audio in time-based sections with timestamp-specific issue detection.

        Args:
            audio_path: Path to the audio file
            min_section_length: Minimum section length in seconds (default 15s)
            detect_musical_sections: If True, detect intro/buildup/drop/breakdown;
                                    if False, use fixed-length segments

        Returns:
            SectionAnalysisResult with sections, timestamped issues, and timeline data
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Load audio
        y, sr = librosa.load(audio_path, sr=None, mono=False)
        audio_data, sr_orig = sf.read(audio_path)

        # Create mono mix
        if len(y.shape) > 1 and y.shape[0] == 2:
            y_mono = librosa.to_mono(y)
        else:
            y_mono = y if len(y.shape) == 1 else y[0]

        duration = librosa.get_duration(y=y_mono, sr=sr)

        # Detect section boundaries
        if detect_musical_sections:
            boundaries = self._detect_section_boundaries(y_mono, sr, min_section_length)
        else:
            # Fixed-length segments (default 30 seconds)
            boundaries = list(np.arange(0, duration, 30.0))
            boundaries.append(duration)

        # Analyze each section
        sections = []
        all_issues = []
        clipping_timestamps = []

        for i in range(len(boundaries) - 1):
            start_time = boundaries[i]
            end_time = boundaries[i + 1]

            # Extract section audio
            start_sample = int(start_time * sr)
            end_sample = int(end_time * sr)
            section_audio = y_mono[start_sample:end_sample]

            # Extract section from original audio for clipping detection
            start_sample_orig = int(start_time * sr_orig)
            end_sample_orig = int(end_time * sr_orig)
            section_orig = audio_data[start_sample_orig:end_sample_orig]

            # Classify section type
            section_type = self._classify_section(
                section_audio, sr, start_time, end_time, duration,
                i, len(boundaries) - 1
            )

            # Analyze section
            section_info, section_issues, section_clips = self._analyze_section(
                section_audio, section_orig, sr, sr_orig, start_time, end_time, section_type
            )

            sections.append(section_info)
            all_issues.extend(section_issues)
            clipping_timestamps.extend(section_clips)

        # Compile section summary
        section_summary = {}
        for section in sections:
            section_summary[section.section_type] = section_summary.get(section.section_type, 0) + 1

        # Find worst section
        worst_section = None
        worst_severity = 0
        severity_map = {'clean': 0, 'minor': 1, 'moderate': 2, 'severe': 3}
        for section in sections:
            sev = severity_map.get(section.severity_summary, 0)
            if sev > worst_severity:
                worst_severity = sev
                worst_section = f"{self._format_time(section.start_time)}-{self._format_time(section.end_time)} ({section.section_type}): {section.severity_summary.upper()}"

        # Prepare timeline data for visualization
        timeline_data = self._prepare_timeline_data(sections, all_issues, duration)

        return SectionAnalysisResult(
            sections=sections,
            all_issues=all_issues,
            clipping_timestamps=clipping_timestamps,
            section_summary=section_summary,
            worst_section=worst_section,
            timeline_data=timeline_data
        )

    def _detect_section_boundaries(
        self,
        y: np.ndarray,
        sr: int,
        min_section_length: float
    ) -> List[float]:
        """
        Detect musical section boundaries using energy, transients, and spectral changes.
        Optimized for trance music structure (intro->buildup->drop->breakdown pattern).
        """
        duration = librosa.get_duration(y=y, sr=sr)

        # Calculate features over time
        hop_length = 512
        frame_length = 2048

        # RMS energy over time
        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
        rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)

        # Onset strength (transient density)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)

        # Spectral centroid (brightness)
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]

        # Compute novelty curve (changes in all features combined)
        # Normalize features
        rms_norm = (rms - rms.min()) / (rms.max() - rms.min() + 1e-10)
        onset_norm = (onset_env - onset_env.min()) / (onset_env.max() - onset_env.min() + 1e-10)
        centroid_norm = (spectral_centroid - spectral_centroid.min()) / (spectral_centroid.max() - spectral_centroid.min() + 1e-10)

        # Combined novelty: emphasize RMS changes (energy) for trance
        min_len = min(len(rms_norm), len(onset_norm), len(centroid_norm))
        combined = 0.5 * rms_norm[:min_len] + 0.3 * onset_norm[:min_len] + 0.2 * centroid_norm[:min_len]

        # Compute derivative (rate of change)
        novelty = np.abs(np.diff(combined, prepend=combined[0]))

        # Smooth novelty curve
        kernel_size = int(sr / hop_length * 2)  # 2 second smoothing
        if kernel_size > 1:
            novelty = np.convolve(novelty, np.ones(kernel_size)/kernel_size, mode='same')

        # Find peaks in novelty (section boundaries)
        min_samples = int(min_section_length * sr / hop_length)

        # Adaptive threshold based on novelty statistics
        threshold = np.mean(novelty) + 0.5 * np.std(novelty)

        # Find peaks above threshold with minimum distance
        peaks = []
        last_peak = -min_samples
        for i in range(len(novelty)):
            if novelty[i] > threshold and i - last_peak >= min_samples:
                # Verify it's a local maximum
                window_start = max(0, i - min_samples // 4)
                window_end = min(len(novelty), i + min_samples // 4)
                if novelty[i] == max(novelty[window_start:window_end]):
                    peaks.append(i)
                    last_peak = i

        # Convert to times
        boundaries = [0.0]
        for peak in peaks:
            time = float(rms_times[min(peak, len(rms_times) - 1)])
            if time > min_section_length and time < duration - min_section_length:
                boundaries.append(time)
        boundaries.append(duration)

        # Merge sections that are too short
        merged = [boundaries[0]]
        for b in boundaries[1:]:
            if b - merged[-1] >= min_section_length:
                merged.append(b)
            elif b == boundaries[-1]:
                merged[-1] = b  # Extend last section to end

        return merged

    def _classify_section(
        self,
        section_audio: np.ndarray,
        sr: int,
        start_time: float,
        end_time: float,
        total_duration: float,
        section_index: int,
        total_sections: int
    ) -> str:
        """
        Classify a section type based on its audio characteristics and position.
        Optimized for trance: intro->buildup->drop->breakdown->buildup->drop->outro
        """
        # Calculate section features
        rms = np.sqrt(np.mean(section_audio ** 2))
        rms_db = 20 * np.log10(rms + 1e-10)

        # Onset density (transients per second)
        onset_frames = librosa.onset.onset_detect(y=section_audio, sr=sr)
        onset_times = librosa.frames_to_time(onset_frames, sr=sr)
        section_duration = end_time - start_time
        transient_density = len(onset_times) / section_duration if section_duration > 0 else 0

        # Spectral centroid (brightness)
        centroid = np.mean(librosa.feature.spectral_centroid(y=section_audio, sr=sr))

        # Low frequency energy ratio
        D = np.abs(librosa.stft(section_audio))
        freqs = librosa.fft_frequencies(sr=sr)
        low_mask = freqs < 200
        low_energy_ratio = np.sum(D[low_mask, :]) / (np.sum(D) + 1e-10)

        # Position in track
        relative_position = (start_time + end_time) / 2 / total_duration

        # Classification logic for trance
        # Intro: first 10%, low energy, low transient density
        if relative_position < 0.1:
            return 'intro'

        # Outro: last 10%, decreasing energy
        if relative_position > 0.9:
            return 'outro'

        # Drops: high energy, high transient density, strong bass
        is_high_energy = rms_db > -15
        is_percussive = transient_density > 2.0
        has_bass = low_energy_ratio > 0.3

        if is_high_energy and is_percussive and has_bass:
            return 'drop'

        # Breakdown: low energy, low transients, mid-track
        is_low_energy = rms_db < -20
        is_sparse = transient_density < 1.5

        if is_low_energy and is_sparse:
            return 'breakdown'

        # Buildup: increasing energy, moderate transients, often before drops
        # Check if next section would be a drop (energy increasing)
        if transient_density > 1.0 and not is_high_energy:
            return 'buildup'

        return 'unknown'

    def _analyze_section(
        self,
        section_audio: np.ndarray,
        section_orig: np.ndarray,
        sr: int,
        sr_orig: int,
        start_time: float,
        end_time: float,
        section_type: str
    ) -> Tuple[SectionInfo, List[TimestampedIssue], List[float]]:
        """Analyze a single section for issues and metrics."""
        issues = []
        clipping_times = []

        # Basic metrics
        rms = np.sqrt(np.mean(section_audio ** 2))
        avg_rms_db = float(20 * np.log10(rms + 1e-10))
        peak = np.max(np.abs(section_audio))
        peak_db = float(20 * np.log10(peak + 1e-10))

        # Transient density
        onset_frames = librosa.onset.onset_detect(y=section_audio, sr=sr)
        onset_times = librosa.frames_to_time(onset_frames, sr=sr)
        section_duration = end_time - start_time
        transient_density = float(len(onset_times) / section_duration) if section_duration > 0 else 0.0

        # Spectral centroid
        spectral_centroid_hz = float(np.mean(librosa.feature.spectral_centroid(y=section_audio, sr=sr)))

        # --- Issue Detection ---

        # 1. Clipping detection with timestamps
        clip_threshold = 0.99
        if len(section_orig.shape) > 1:
            clipped_samples = np.where(np.abs(section_orig).max(axis=1) >= clip_threshold)[0]
        else:
            clipped_samples = np.where(np.abs(section_orig) >= clip_threshold)[0]

        if len(clipped_samples) > 0:
            clip_times_in_section = clipped_samples / sr_orig
            # Group nearby clips
            grouped_times = []
            current_group_start = clip_times_in_section[0]
            for t in clip_times_in_section:
                if t - current_group_start > 0.1:
                    abs_time = start_time + current_group_start
                    grouped_times.append(abs_time)
                    clipping_times.append(abs_time)
                    current_group_start = t
            abs_time = start_time + current_group_start
            grouped_times.append(abs_time)
            clipping_times.append(abs_time)

            severity = 'severe' if len(clipped_samples) > 500 else ('moderate' if len(clipped_samples) > 100 else 'minor')
            issues.append(TimestampedIssue(
                issue_type='clipping',
                start_time=start_time,
                end_time=end_time,
                severity=severity,
                message=f"Clipping detected at {', '.join([self._format_time(t) for t in grouped_times[:5]])}",
                details={'clip_count': len(clipped_samples), 'timestamps': grouped_times[:10]}
            ))

        # 2. Low-end buildup detection
        D = np.abs(librosa.stft(section_audio))
        freqs = librosa.fft_frequencies(sr=sr)

        # Check 200-500Hz buildup (muddy frequencies)
        mud_mask = (freqs >= 200) & (freqs < 500)
        total_energy = np.sum(D ** 2)
        mud_energy = np.sum(D[mud_mask, :] ** 2)
        mud_ratio = mud_energy / (total_energy + 1e-10)

        if mud_ratio > 0.25:
            severity = 'severe' if mud_ratio > 0.4 else ('moderate' if mud_ratio > 0.3 else 'minor')
            issues.append(TimestampedIssue(
                issue_type='low_end_buildup',
                start_time=start_time,
                end_time=end_time,
                severity=severity,
                message=f"Low-end buildup (200-500Hz) at {self._format_time(start_time)}-{self._format_time(end_time)}",
                details={'mud_ratio': float(mud_ratio * 100)}
            ))

        # 3. Sub-bass energy check (especially important for drops)
        sub_mask = freqs < 60
        sub_energy = np.sum(D[sub_mask, :] ** 2)
        sub_ratio = sub_energy / (total_energy + 1e-10)

        if section_type == 'drop' and sub_ratio < 0.05:
            issues.append(TimestampedIssue(
                issue_type='weak_sub',
                start_time=start_time,
                end_time=end_time,
                severity='minor',
                message=f"Weak sub-bass in drop section at {self._format_time(start_time)}-{self._format_time(end_time)}",
                details={'sub_ratio': float(sub_ratio * 100)}
            ))

        # 4. Harsh highs detection
        harsh_mask = (freqs >= 3000) & (freqs < 8000)
        harsh_energy = np.sum(D[harsh_mask, :] ** 2)
        harsh_ratio = harsh_energy / (total_energy + 1e-10)

        if harsh_ratio > 0.35:
            severity = 'severe' if harsh_ratio > 0.5 else ('moderate' if harsh_ratio > 0.4 else 'minor')
            issues.append(TimestampedIssue(
                issue_type='harsh_highs',
                start_time=start_time,
                end_time=end_time,
                severity=severity,
                message=f"Harsh high frequencies (3-8kHz) at {self._format_time(start_time)}-{self._format_time(end_time)}",
                details={'harsh_ratio': float(harsh_ratio * 100)}
            ))

        # 5. Dynamic range check per section
        section_dynamic_range = peak_db - avg_rms_db
        if section_dynamic_range < 4:
            issues.append(TimestampedIssue(
                issue_type='over_compressed',
                start_time=start_time,
                end_time=end_time,
                severity='moderate' if section_dynamic_range < 3 else 'minor',
                message=f"Over-compressed section ({section_dynamic_range:.1f}dB range) at {self._format_time(start_time)}-{self._format_time(end_time)}",
                details={'dynamic_range_db': float(section_dynamic_range)}
            ))

        # Determine overall severity for section
        if not issues:
            severity_summary = 'clean'
        else:
            severities = [i.severity for i in issues]
            if 'severe' in severities:
                severity_summary = 'severe'
            elif 'moderate' in severities:
                severity_summary = 'moderate'
            else:
                severity_summary = 'minor'

        section_info = SectionInfo(
            section_type=section_type,
            start_time=start_time,
            end_time=end_time,
            avg_rms_db=avg_rms_db,
            peak_db=peak_db,
            transient_density=transient_density,
            spectral_centroid_hz=spectral_centroid_hz,
            issues=issues,
            severity_summary=severity_summary
        )

        return section_info, issues, clipping_times

    def _format_time(self, seconds: float) -> str:
        """Format seconds as M:SS or H:MM:SS."""
        if seconds < 3600:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}:{secs:02d}"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            return f"{hours}:{mins:02d}:{secs:02d}"

    def _prepare_timeline_data(
        self,
        sections: List[SectionInfo],
        issues: List[TimestampedIssue],
        duration: float
    ) -> Dict:
        """Prepare data for timeline visualization."""
        return {
            'duration': duration,
            'sections': [
                {
                    'type': s.section_type,
                    'start': s.start_time,
                    'end': s.end_time,
                    'rms_db': s.avg_rms_db,
                    'severity': s.severity_summary
                }
                for s in sections
            ],
            'issues': [
                {
                    'type': i.issue_type,
                    'start': i.start_time,
                    'end': i.end_time,
                    'severity': i.severity,
                    'message': i.message
                }
                for i in issues
            ]
        }

    def _compile_issues_and_recommendations(
        self,
        clipping: ClippingInfo,
        dynamics: DynamicsInfo,
        frequency: FrequencyInfo,
        stereo: StereoInfo,
        loudness: LoudnessInfo,
        transients: Optional[TransientInfo],
        detected_tempo: Optional[float],
        reference_tempo: Optional[float]
    ) -> Tuple[List[Dict], List[str]]:
        """Compile all issues and generate recommendations with priority ordering."""
        issues = []
        recommendations = []

        # ========== CRITICAL ISSUES (Phase, Severe Clipping) ==========

        # Phase correlation - CRITICAL if negative
        if stereo.is_stereo and not stereo.phase_safe:
            issues.append({
                'type': 'phase',
                'severity': 'critical',
                'message': f"PHASE CORRELATION NEGATIVE ({stereo.correlation:.2f}) - will cancel in mono!"
            })
            recommendations.insert(0, "CRITICAL: Fix phase issues - check for out-of-phase stereo processing, inverted cables, or stereo widening plugins")

        # Clipping issues
        if clipping.has_clipping:
            severity = 'critical' if clipping.severity in ['moderate', 'severe'] else 'warning'
            issues.append({
                'type': 'clipping',
                'severity': severity,
                'message': f"Clipping detected ({clipping.clip_count} samples, peak: {clipping.max_peak:.3f})",
                'positions': clipping.clip_positions[:5]
            })
            recommendations.append(
                f"Fix clipping: Reduce gain by at least {abs(20 * np.log10(clipping.max_peak + 0.001)):.1f}dB "
                "or check individual tracks for overloads"
            )

        # ========== WARNING ISSUES ==========

        # Enhanced Dynamics/Crest Factor issues
        if dynamics.is_over_compressed:
            issues.append({
                'type': 'dynamics',
                'severity': 'warning' if dynamics.severity == 'minor' else 'critical',
                'message': f"Crest factor {dynamics.crest_factor_db:.1f}dB ({dynamics.crest_interpretation}) - {dynamics.recommended_action}"
            })
            if dynamics.crest_interpretation == 'over_compressed':
                recommendations.append(
                    f"Reduce master limiting - aim for 12dB crest factor (currently {dynamics.crest_factor_db:.1f}dB)"
                )

        # Enhanced LUFS with streaming platform targets
        loudness_diff = loudness.integrated_lufs - self.REFERENCE_LOUDNESS
        if loudness_diff < -6:
            issues.append({
                'type': 'loudness',
                'severity': 'warning',
                'message': f"LUFS: {loudness.integrated_lufs:.1f} (Target: -14 LUFS for Spotify) - {abs(loudness_diff):.1f}dB too quiet"
            })
            recommendations.append(
                f"Increase overall loudness by {abs(loudness_diff):.0f}dB to reach -14 LUFS for streaming"
            )
        elif loudness_diff > 2:
            issues.append({
                'type': 'loudness',
                'severity': 'warning',
                'message': f"LUFS: {loudness.integrated_lufs:.1f} - {loudness_diff:.1f}dB louder than streaming standard"
            })
            recommendations.append(
                "Mix may be over-limited; Spotify/YouTube will turn it down automatically"
            )
        else:
            # Good loudness - add as info
            issues.append({
                'type': 'loudness',
                'severity': 'info',
                'message': f"LUFS: {loudness.integrated_lufs:.1f} - good for streaming (target: -14 LUFS)"
            })

        # True peak warning
        if loudness.true_peak_db > -1.0:
            issues.append({
                'type': 'true_peak',
                'severity': 'warning',
                'message': f"True Peak: {loudness.true_peak_db:.1f}dB - may clip after encoding"
            })
            recommendations.append(
                f"Reduce true peak to -1.0dB or lower to prevent clipping in MP3/AAC encoding"
            )

        # Enhanced stereo width issues (non-phase-related)
        if stereo.is_stereo and stereo.phase_safe:
            for issue in stereo.issues:
                if 'CRITICAL' not in issue:  # Already handled phase issues above
                    issues.append({
                        'type': 'stereo',
                        'severity': 'warning',
                        'message': issue
                    })

            if stereo.width_category == 'mono':
                recommendations.append(
                    f"Stereo Width: {stereo.correlation:.2f} correlation ({stereo.width_category}) - add width to pads/synths using Utility (120-150%)"
                )
            elif stereo.width_category == 'narrow':
                recommendations.append(
                    f"Stereo Width: {stereo.correlation:.2f} correlation ({stereo.width_category}) - consider widening reverbs or pads"
                )

        # Frequency issues
        for issue in frequency.balance_issues:
            issues.append({
                'type': 'frequency',
                'severity': 'warning',
                'message': issue
            })

        for freq_range in frequency.problem_frequencies:
            low, high, problem = freq_range
            if problem == "excessive_energy":
                recommendations.append(f"Cut {low}-{high}Hz by 2-4dB to reduce buildup")
            elif problem == "lacking_energy":
                recommendations.append(f"Boost {low}-{high}Hz by 1-3dB or check if elements are missing")
            elif problem == "buildup":
                recommendations.append(f"Apply high-pass filter around {low}Hz on non-bass elements")

        # ========== INFO/OBSERVATIONS ==========

        # Transient analysis
        if transients:
            issues.append({
                'type': 'transients',
                'severity': 'info',
                'message': f"Transients: {transients.transient_count} detected, avg strength {transients.avg_transient_strength:.2f} ({transients.attack_quality})"
            })
            if transients.attack_quality == 'soft':
                recommendations.append(
                    "Consider transient enhancement on drums/percussion for more punch"
                )

        # Dynamic range observation (if not over-compressed)
        if not dynamics.is_over_compressed:
            issues.append({
                'type': 'dynamics',
                'severity': 'info',
                'message': f"Dynamic Range: {dynamics.dynamic_range_db:.1f}dB ({dynamics.crest_interpretation})"
            })

        # Tempo verification
        if reference_tempo and detected_tempo:
            tempo_diff = abs(detected_tempo - reference_tempo)
            if tempo_diff > 2:
                issues.append({
                    'type': 'tempo',
                    'severity': 'info',
                    'message': f"Detected tempo ({detected_tempo:.1f} BPM) differs from project ({reference_tempo:.1f} BPM)"
                })

        # Calculate priority scores for each issue
        issues = self._add_priority_scores(issues)

        # Sort by priority score (highest first)
        issues.sort(key=lambda x: x.get('priority_score', 0), reverse=True)

        return issues, recommendations

    def _add_priority_scores(self, issues: List[Dict]) -> List[Dict]:
        """Add priority scores to issues based on severity, category, and scope."""

        # Base severity scores
        severity_scores = {
            'critical': 100,
            'severe': 70,
            'warning': 40,
            'moderate': 40,
            'minor': 15,
            'info': 5
        }

        # Category multipliers (based on impact)
        category_multipliers = {
            'phase': 3.0,        # Playback failure
            'clipping': 2.5,    # Audible damage
            'low_end': 2.5,     # Foundation
            'loudness': 2.0,    # Streaming requirement
            'true_peak': 2.0,   # Encoding issues
            'stereo': 2.0,      # Professional width
            'frequency': 1.5,   # Clarity
            'dynamics': 1.5,    # Punch
            'transients': 1.2,  # Attack quality
            'tempo': 1.0,       # Reference info
        }

        for issue in issues:
            severity = issue.get('severity', 'info')
            issue_type = issue.get('type', 'other')

            base_score = severity_scores.get(severity, 5)
            category_mult = category_multipliers.get(issue_type, 1.0)

            # Scope multiplier (assume entire mix for now)
            scope_mult = 1.5 if severity in ['critical', 'severe'] else 1.0

            priority_score = int(base_score * category_mult * scope_mult)

            issue['priority_score'] = priority_score
            issue['priority_tier'] = self._get_priority_tier(priority_score)

        return issues

    def _get_priority_tier(self, score: int) -> str:
        """Convert priority score to tier label."""
        if score > 200:
            return 'CRITICAL'
        elif score >= 100:
            return 'HIGH'
        elif score >= 50:
            return 'MEDIUM'
        else:
            return 'LOW'

    def _add_extended_analysis_issues(
        self,
        issues: List[Dict],
        recommendations: List[str],
        harmonic: Optional[Any],
        clarity: Optional[Any],
        spatial: Optional[Any],
        surround: Optional[Any],
        playback: Optional[Any]
    ) -> None:
        """Add issues and recommendations from extended analyzers."""

        # Harmonic analysis issues
        if harmonic:
            # Add key detection info
            if harmonic.key != "Unknown":
                issues.append({
                    'type': 'harmonic',
                    'severity': 'info',
                    'message': f"Key: {harmonic.key} ({harmonic.key_confidence:.0%} confidence) - Camelot: {harmonic.camelot_notation}"
                })

                # Low key consistency warning
                if harmonic.key_consistency < 70:
                    issues.append({
                        'type': 'harmonic',
                        'severity': 'warning',
                        'message': f"Key consistency: {harmonic.key_consistency:.0f}% - possible modulations or key clashes"
                    })
                    recommendations.append(
                        "Check for key clashes between layered elements or intentional modulations"
                    )
            else:
                issues.append({
                    'type': 'harmonic',
                    'severity': 'warning',
                    'message': f"Key detection uncertain ({harmonic.key_confidence:.0%} confidence)"
                })

        # Clarity analysis issues
        if clarity:
            issues.append({
                'type': 'clarity',
                'severity': 'info',
                'message': f"Clarity: {clarity.clarity_score:.0f}/100 - {clarity.brightness_category} brightness"
            })

            if clarity.masking_risk == 'high':
                issues.append({
                    'type': 'clarity',
                    'severity': 'warning',
                    'message': f"High masking risk detected - elements may be fighting for same frequencies"
                })
                recommendations.append(
                    "Use EQ to carve space for each element - cut competing frequencies"
                )

            if clarity.brightness_category == 'dark':
                recommendations.append(
                    "Mix sounds dark - add presence (2-5kHz) or air (10-20kHz)"
                )
            elif clarity.brightness_category == 'harsh':
                recommendations.append(
                    "Mix sounds harsh - reduce 3-6kHz with dynamic EQ or de-esser"
                )

        # Spatial analysis issues
        if spatial:
            issues.append({
                'type': 'spatial',
                'severity': 'info',
                'message': f"3D Spatial: Height {spatial.height_score:.0f}%, Depth {spatial.depth_score:.0f}%, Width stability {spatial.width_consistency:.0f}%"
            })

            if spatial.width_consistency < 60:
                issues.append({
                    'type': 'spatial',
                    'severity': 'warning',
                    'message': f"Unstable stereo image ({spatial.width_consistency:.0f}%) - stereo width varies significantly"
                })
                recommendations.append(
                    "Stereo image is unstable - check for aggressive stereo modulation or panning automation"
                )

        # Surround compatibility issues
        if surround:
            if surround.mono_compatibility < 50:
                issues.append({
                    'type': 'surround',
                    'severity': 'critical',
                    'message': f"MONO COMPATIBILITY CRITICAL ({surround.mono_compatibility:.0f}%) - mix will collapse in mono!"
                })
                recommendations.insert(0,
                    "CRITICAL: Fix mono compatibility - check bass/kick mono, reduce stereo widening"
                )
            elif surround.mono_compatibility < 70:
                issues.append({
                    'type': 'surround',
                    'severity': 'warning',
                    'message': f"Mono compatibility concerns ({surround.mono_compatibility:.0f}%)"
                })
                recommendations.append(
                    "Improve mono compatibility - mono the bass below 150Hz"
                )
            else:
                issues.append({
                    'type': 'surround',
                    'severity': 'info',
                    'message': f"Mono compatible: {surround.mono_compatibility:.0f}% - Phase: {surround.phase_score:.0f}%"
                })

            if surround.phase_score < 50:
                issues.append({
                    'type': 'surround',
                    'severity': 'warning',
                    'message': f"Phase concerns ({surround.phase_score:.0f}%) - potential phase cancellation"
                })

        # Playback optimization issues
        if playback:
            issues.append({
                'type': 'playback',
                'severity': 'info',
                'message': f"Playback: Headphone {playback.headphone_score:.0f}%, Speaker {playback.speaker_score:.0f}%"
            })

            if not playback.crossfeed_safe:
                issues.append({
                    'type': 'playback',
                    'severity': 'warning',
                    'message': "Extreme stereo separation may cause headphone listening fatigue"
                })
                recommendations.append(
                    "Consider reducing extreme stereo elements for headphone listeners"
                )

            if playback.bass_translation == 'weak':
                recommendations.append(
                    "Bass may not translate to laptop/phone speakers - add harmonics in 100-300Hz"
                )
            elif playback.bass_translation == 'excessive':
                recommendations.append(
                    "Excessive sub-bass may overwhelm small speakers - consider high-pass at 30Hz"
                )


def quick_analyze(audio_path: str) -> AnalysisResult:
    """Quick analysis function for simple use cases."""
    analyzer = AudioAnalyzer()
    return analyzer.analyze(audio_path)
