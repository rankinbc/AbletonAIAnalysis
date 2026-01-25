"""
Reference Profiler Module

Batch analyzes reference tracks to build a statistical profile of
"what professional trance sounds like". Used to compare your tracks
against professional standards.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import numpy as np
from datetime import datetime


@dataclass
class StatRange:
    """Statistical range for a metric."""
    min: float
    max: float
    mean: float
    median: float
    std: float
    percentile_10: float
    percentile_90: float

    @classmethod
    def from_values(cls, values: List[float]) -> 'StatRange':
        """Create StatRange from a list of values."""
        if not values:
            return cls(0, 0, 0, 0, 0, 0, 0)

        arr = np.array(values)
        return cls(
            min=float(np.min(arr)),
            max=float(np.max(arr)),
            mean=float(np.mean(arr)),
            median=float(np.median(arr)),
            std=float(np.std(arr)),
            percentile_10=float(np.percentile(arr, 10)),
            percentile_90=float(np.percentile(arr, 90))
        )

    def score_value(self, value: float) -> Tuple[float, str]:
        """
        Score a value against this range.

        Returns:
            Tuple of (score 0-100, description)
        """
        # Within typical range (10th-90th percentile) = 100
        if self.percentile_10 <= value <= self.percentile_90:
            return 100.0, "within_range"

        # Slightly outside = 70-90
        if self.min <= value <= self.max:
            if value < self.percentile_10:
                distance = (self.percentile_10 - value) / (self.percentile_10 - self.min + 0.001)
            else:
                distance = (value - self.percentile_90) / (self.max - self.percentile_90 + 0.001)
            score = 90 - (distance * 20)
            return max(70, score), "slightly_outside"

        # Outside observed range = 0-70
        if value < self.min:
            distance = (self.min - value) / (abs(self.min) + 1)
            score = 70 - min(70, distance * 50)
            return max(0, score), "below_range"
        else:
            distance = (value - self.max) / (abs(self.max) + 1)
            score = 70 - min(70, distance * 50)
            return max(0, score), "above_range"


@dataclass
class ReferenceProfile:
    """
    Statistical profile built from reference tracks.
    Represents "what professional trance sounds like".
    """
    # Metadata
    name: str = "trance"
    track_count: int = 0
    created: str = ""
    tracks_analyzed: List[str] = field(default_factory=list)

    # Loudness
    loudness_lufs: Optional[StatRange] = None
    true_peak_db: Optional[StatRange] = None
    loudness_range_lu: Optional[StatRange] = None

    # Dynamics
    crest_factor_db: Optional[StatRange] = None
    dynamic_range_db: Optional[StatRange] = None

    # Frequency Balance (percentages)
    sub_bass_pct: Optional[StatRange] = None      # 20-60Hz
    bass_pct: Optional[StatRange] = None          # 60-250Hz
    low_mid_pct: Optional[StatRange] = None       # 250-500Hz
    mid_pct: Optional[StatRange] = None           # 500-2kHz
    high_mid_pct: Optional[StatRange] = None      # 2-6kHz
    high_pct: Optional[StatRange] = None          # 6-10kHz
    air_pct: Optional[StatRange] = None           # 10-20kHz
    spectral_centroid_hz: Optional[StatRange] = None

    # Stereo
    stereo_correlation: Optional[StatRange] = None
    stereo_width_pct: Optional[StatRange] = None

    # Transients
    transient_strength: Optional[StatRange] = None
    transients_per_second: Optional[StatRange] = None

    # Tempo (for genre validation)
    tempo_bpm: Optional[StatRange] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "name": self.name,
            "track_count": self.track_count,
            "created": self.created,
            "tracks_analyzed": self.tracks_analyzed,
        }

        # Convert StatRange objects
        for field_name in [
            'loudness_lufs', 'true_peak_db', 'loudness_range_lu',
            'crest_factor_db', 'dynamic_range_db',
            'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
            'high_mid_pct', 'high_pct', 'air_pct', 'spectral_centroid_hz',
            'stereo_correlation', 'stereo_width_pct',
            'transient_strength', 'transients_per_second', 'tempo_bpm'
        ]:
            value = getattr(self, field_name)
            if value is not None:
                result[field_name] = asdict(value)

        return result

    @classmethod
    def from_dict(cls, data: Dict) -> 'ReferenceProfile':
        """Create from dictionary."""
        profile = cls(
            name=data.get('name', 'trance'),
            track_count=data.get('track_count', 0),
            created=data.get('created', ''),
            tracks_analyzed=data.get('tracks_analyzed', [])
        )

        # Convert StatRange dictionaries back to objects
        for field_name in [
            'loudness_lufs', 'true_peak_db', 'loudness_range_lu',
            'crest_factor_db', 'dynamic_range_db',
            'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
            'high_mid_pct', 'high_pct', 'air_pct', 'spectral_centroid_hz',
            'stereo_correlation', 'stereo_width_pct',
            'transient_strength', 'transients_per_second', 'tempo_bpm'
        ]:
            if field_name in data and data[field_name]:
                setattr(profile, field_name, StatRange(**data[field_name]))

        return profile

    def save(self, path: str):
        """Save profile to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        print(f"Saved profile to {path}")

    @classmethod
    def load(cls, path: str) -> 'ReferenceProfile':
        """Load profile from JSON file."""
        with open(path, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)


class ReferenceProfiler:
    """
    Analyzes a library of reference tracks to build a statistical profile.

    Usage:
        profiler = ReferenceProfiler()
        profile = profiler.analyze_directory("D:/Music/Trance References/")
        profile.save("models/trance_profile.json")
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self._analyzer = None

    def _get_analyzer(self):
        """Lazy load the audio analyzer."""
        if self._analyzer is None:
            from audio_analyzer import AudioAnalyzer
            self._analyzer = AudioAnalyzer(verbose=False)
        return self._analyzer

    def analyze_directory(
        self,
        directory: str,
        extensions: List[str] = None,
        profile_name: str = "trance",
        max_tracks: int = None
    ) -> ReferenceProfile:
        """
        Analyze all audio files in a directory.

        Args:
            directory: Path to directory containing reference tracks
            extensions: File extensions to include (default: wav, flac, mp3)
            profile_name: Name for the profile
            max_tracks: Maximum number of tracks to analyze (for testing)

        Returns:
            ReferenceProfile with statistics
        """
        if extensions is None:
            extensions = ['.wav', '.flac', '.mp3', '.aiff', '.m4a']

        # Find all audio files
        directory = Path(directory)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        audio_files = []
        for ext in extensions:
            audio_files.extend(directory.glob(f"**/*{ext}"))
            audio_files.extend(directory.glob(f"**/*{ext.upper()}"))

        # Remove duplicates and sort
        audio_files = sorted(set(audio_files))

        if max_tracks:
            audio_files = audio_files[:max_tracks]

        if not audio_files:
            raise ValueError(f"No audio files found in {directory}")

        if self.verbose:
            print(f"Found {len(audio_files)} audio files")
            print("Analyzing...")

        # Analyze each file and collect metrics
        metrics = self._initialize_metrics()
        analyzed_tracks = []

        for i, audio_file in enumerate(audio_files):
            if self.verbose:
                progress = (i + 1) / len(audio_files) * 100
                print(f"  [{progress:5.1f}%] {audio_file.name[:50]}...", end="")

            try:
                result = self._get_analyzer().analyze(str(audio_file))
                self._collect_metrics(metrics, result)
                analyzed_tracks.append(audio_file.name)
                if self.verbose:
                    print(" ✓")
            except Exception as e:
                if self.verbose:
                    print(f" ✗ ({e})")

        if not analyzed_tracks:
            raise ValueError("No tracks could be analyzed")

        # Build profile from collected metrics
        profile = self._build_profile(metrics, profile_name, analyzed_tracks)

        if self.verbose:
            print(f"\nAnalyzed {len(analyzed_tracks)} tracks successfully")
            self._print_profile_summary(profile)

        return profile

    def _initialize_metrics(self) -> Dict[str, List[float]]:
        """Initialize empty metric collections."""
        return {
            'loudness_lufs': [],
            'true_peak_db': [],
            'loudness_range_lu': [],
            'crest_factor_db': [],
            'dynamic_range_db': [],
            'sub_bass_pct': [],
            'bass_pct': [],
            'low_mid_pct': [],
            'mid_pct': [],
            'high_mid_pct': [],
            'high_pct': [],
            'air_pct': [],
            'spectral_centroid_hz': [],
            'stereo_correlation': [],
            'stereo_width_pct': [],
            'transient_strength': [],
            'transients_per_second': [],
            'tempo_bpm': [],
        }

    def _collect_metrics(self, metrics: Dict, result) -> None:
        """Collect metrics from an analysis result."""
        # Loudness
        metrics['loudness_lufs'].append(result.loudness.integrated_lufs)
        metrics['true_peak_db'].append(result.loudness.true_peak_db)
        metrics['loudness_range_lu'].append(result.loudness.loudness_range_lu)

        # Dynamics
        metrics['crest_factor_db'].append(result.dynamics.crest_factor_db)
        metrics['dynamic_range_db'].append(result.dynamics.dynamic_range_db)

        # Frequency
        metrics['sub_bass_pct'].append(result.frequency.sub_bass_energy)
        metrics['bass_pct'].append(result.frequency.bass_energy)
        metrics['low_mid_pct'].append(result.frequency.low_mid_energy)
        metrics['mid_pct'].append(result.frequency.mid_energy)
        metrics['high_mid_pct'].append(result.frequency.high_mid_energy)
        metrics['high_pct'].append(result.frequency.high_energy)
        metrics['air_pct'].append(result.frequency.air_energy)
        metrics['spectral_centroid_hz'].append(result.frequency.spectral_centroid_hz)

        # Stereo
        if result.stereo.is_stereo:
            metrics['stereo_correlation'].append(result.stereo.correlation)
            metrics['stereo_width_pct'].append(result.stereo.width_estimate)

        # Transients
        if result.transients:
            metrics['transient_strength'].append(result.transients.avg_transient_strength)
            metrics['transients_per_second'].append(result.transients.transients_per_second)

        # Tempo
        if result.detected_tempo:
            metrics['tempo_bpm'].append(result.detected_tempo)

    def _build_profile(
        self,
        metrics: Dict,
        name: str,
        tracks: List[str]
    ) -> ReferenceProfile:
        """Build a ReferenceProfile from collected metrics."""
        profile = ReferenceProfile(
            name=name,
            track_count=len(tracks),
            created=datetime.now().isoformat(),
            tracks_analyzed=tracks
        )

        # Convert each metric list to StatRange
        for metric_name, values in metrics.items():
            if values:
                setattr(profile, metric_name, StatRange.from_values(values))

        return profile

    def _print_profile_summary(self, profile: ReferenceProfile) -> None:
        """Print a summary of the profile."""
        print("\n" + "=" * 60)
        print(f"REFERENCE PROFILE: {profile.name.upper()}")
        print(f"Based on {profile.track_count} tracks")
        print("=" * 60)

        def fmt_range(sr: Optional[StatRange], unit: str = "") -> str:
            if sr is None:
                return "N/A"
            return f"{sr.percentile_10:.1f} - {sr.percentile_90:.1f}{unit} (mean: {sr.mean:.1f}{unit})"

        print("\n📊 LOUDNESS:")
        print(f"  LUFS:        {fmt_range(profile.loudness_lufs)}")
        print(f"  True Peak:   {fmt_range(profile.true_peak_db, 'dB')}")

        print("\n🎚️ DYNAMICS:")
        print(f"  Crest Factor: {fmt_range(profile.crest_factor_db, 'dB')}")

        print("\n📈 FREQUENCY BALANCE:")
        print(f"  Sub Bass:    {fmt_range(profile.sub_bass_pct, '%')}")
        print(f"  Bass:        {fmt_range(profile.bass_pct, '%')}")
        print(f"  Low Mid:     {fmt_range(profile.low_mid_pct, '%')}")
        print(f"  Mid:         {fmt_range(profile.mid_pct, '%')}")
        print(f"  High Mid:    {fmt_range(profile.high_mid_pct, '%')}")
        print(f"  High:        {fmt_range(profile.high_pct, '%')}")
        print(f"  Air:         {fmt_range(profile.air_pct, '%')}")

        print("\n🔊 STEREO:")
        print(f"  Correlation: {fmt_range(profile.stereo_correlation)}")
        print(f"  Width:       {fmt_range(profile.stereo_width_pct, '%')}")

        if profile.tempo_bpm:
            print("\n🎵 TEMPO:")
            print(f"  BPM:         {fmt_range(profile.tempo_bpm)}")

        print("\n" + "=" * 60)


class DeltaAnalyzer:
    """
    Compares a track against a reference profile to find deltas.
    """

    def __init__(self, profile: ReferenceProfile):
        self.profile = profile

    def analyze(self, analysis_result) -> Dict:
        """
        Compare an analysis result against the reference profile.

        Returns:
            Dictionary with scores and deltas for each metric.
        """
        deltas = {
            'overall_score': 0,
            'metrics': {},
            'issues': [],
            'strengths': []
        }

        scores = []

        # Compare each metric
        comparisons = [
            ('loudness_lufs', analysis_result.loudness.integrated_lufs, 'LUFS', 'Loudness'),
            ('crest_factor_db', analysis_result.dynamics.crest_factor_db, 'dB', 'Crest Factor'),
            ('sub_bass_pct', analysis_result.frequency.sub_bass_energy, '%', 'Sub Bass'),
            ('bass_pct', analysis_result.frequency.bass_energy, '%', 'Bass'),
            ('low_mid_pct', analysis_result.frequency.low_mid_energy, '%', 'Low Mids'),
            ('mid_pct', analysis_result.frequency.mid_energy, '%', 'Mids'),
            ('high_mid_pct', analysis_result.frequency.high_mid_energy, '%', 'High Mids'),
            ('high_pct', analysis_result.frequency.high_energy, '%', 'Highs'),
            ('air_pct', analysis_result.frequency.air_energy, '%', 'Air'),
        ]

        if analysis_result.stereo.is_stereo:
            comparisons.extend([
                ('stereo_correlation', analysis_result.stereo.correlation, '', 'Stereo Correlation'),
                ('stereo_width_pct', analysis_result.stereo.width_estimate, '%', 'Stereo Width'),
            ])

        for metric_name, value, unit, display_name in comparisons:
            ref_range = getattr(self.profile, metric_name)
            if ref_range is None:
                continue

            score, status = ref_range.score_value(value)
            scores.append(score)

            delta = value - ref_range.mean
            delta_str = f"{delta:+.1f}{unit}" if delta != 0 else "on target"

            deltas['metrics'][metric_name] = {
                'value': value,
                'reference_mean': ref_range.mean,
                'reference_range': (ref_range.percentile_10, ref_range.percentile_90),
                'delta': delta,
                'score': score,
                'status': status,
                'display_name': display_name,
                'unit': unit
            }

            # Categorize as issue or strength
            if score < 70:
                direction = "low" if value < ref_range.mean else "high"
                deltas['issues'].append({
                    'metric': display_name,
                    'message': f"{display_name} is {abs(delta):.1f}{unit} {direction}er than reference",
                    'value': value,
                    'target': f"{ref_range.percentile_10:.1f}-{ref_range.percentile_90:.1f}{unit}",
                    'score': score
                })
            elif score >= 95:
                deltas['strengths'].append({
                    'metric': display_name,
                    'message': f"{display_name} matches reference tracks perfectly",
                    'score': score
                })

        # Calculate overall score
        if scores:
            deltas['overall_score'] = sum(scores) / len(scores)

        return deltas

    def print_report(self, deltas: Dict) -> None:
        """Print a formatted delta report."""
        print("\n" + "=" * 60)
        print(f"COMPARISON TO REFERENCE PROFILE: {self.profile.name.upper()}")
        print(f"Overall Score: {deltas['overall_score']:.0f}/100")
        print("=" * 60)

        if deltas['issues']:
            print("\n🔴 ISSUES (below reference standards):")
            for issue in sorted(deltas['issues'], key=lambda x: x['score']):
                print(f"  • {issue['message']}")
                print(f"    Your value: {issue['value']:.1f}, Target: {issue['target']}")

        if deltas['strengths']:
            print("\n🟢 STRENGTHS (matching reference):")
            for strength in deltas['strengths']:
                print(f"  • {strength['message']}")

        print("\n📊 ALL METRICS:")
        for name, data in deltas['metrics'].items():
            status_icon = "✓" if data['score'] >= 80 else "⚠" if data['score'] >= 60 else "✗"
            print(f"  {status_icon} {data['display_name']}: {data['value']:.1f}{data['unit']} "
                  f"(ref: {data['reference_mean']:.1f}{data['unit']}, score: {data['score']:.0f})")

        print("\n" + "=" * 60)


def build_trance_profile(
    reference_dir: str,
    output_path: str = None,
    max_tracks: int = None
) -> ReferenceProfile:
    """
    Convenience function to build a trance reference profile.

    Args:
        reference_dir: Directory containing reference tracks
        output_path: Where to save the profile (optional)
        max_tracks: Limit number of tracks for testing

    Returns:
        ReferenceProfile
    """
    profiler = ReferenceProfiler(verbose=True)
    profile = profiler.analyze_directory(
        reference_dir,
        profile_name="trance",
        max_tracks=max_tracks
    )

    if output_path:
        profile.save(output_path)

    return profile


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python reference_profiler.py <reference_directory> [output_path]")
        print("\nExample:")
        print("  python reference_profiler.py 'D:/Music/Trance References/' models/trance_profile.json")
        sys.exit(1)

    ref_dir = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "trance_profile.json"

    build_trance_profile(ref_dir, output)
