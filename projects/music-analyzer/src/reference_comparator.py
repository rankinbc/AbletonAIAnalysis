"""
Reference Comparator Module

Compares user mixes against professional reference tracks stem-by-stem.
Generates specific, actionable recommendations based on differences.

Example output:
  "Your bass is 3.2dB too loud - reduce by 3dB"
  "Reference drums have more high-end presence (+4.3%) - boost 6-12kHz by 2dB"
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Callable, Any, Tuple

import numpy as np
import librosa

try:
    from .stem_separator import StemSeparator, StemSeparationResult, StemType
    from .reference_storage import ReferenceStorage, ReferenceAnalytics, StemMetrics, TrackMetadata
except ImportError:
    from stem_separator import StemSeparator, StemSeparationResult, StemType
    from reference_storage import ReferenceStorage, ReferenceAnalytics, StemMetrics, TrackMetadata


@dataclass
class StemComparison:
    """Comparison between user and reference for a single stem."""
    stem_type: str

    # User metrics
    user_rms_db: float
    user_lufs: float
    user_spectral_centroid_hz: float
    user_stereo_width_pct: float

    # Reference metrics
    ref_rms_db: float
    ref_lufs: float
    ref_spectral_centroid_hz: float
    ref_stereo_width_pct: float

    # Differences (user - reference, positive = user is higher)
    rms_diff_db: float
    lufs_diff: float
    spectral_centroid_diff_hz: float
    stereo_width_diff_pct: float
    dynamic_range_diff_db: float

    # Frequency band differences (user - reference)
    bass_diff_pct: float
    low_mid_diff_pct: float
    mid_diff_pct: float
    high_mid_diff_pct: float
    high_diff_pct: float

    # Severity assessment
    severity: str  # 'good', 'minor', 'moderate', 'significant'

    # Actionable recommendations
    recommendations: List[str] = field(default_factory=list)


@dataclass
class ComparisonProgress:
    """Progress callback data for comparison."""
    stage: str
    progress_pct: float
    message: str


@dataclass
class ComparisonResult:
    """Complete comparison result between user mix and reference."""
    user_file: str
    reference_file: str
    reference_id: Optional[str]
    comparison_timestamp: str

    # Per-stem comparisons
    stem_comparisons: Dict[str, StemComparison]

    # Overall mix comparison
    overall_loudness_diff_db: float
    overall_balance_score: float  # 0-100, how similar the mix balance is

    # Prioritized action list
    priority_recommendations: List[str]

    # Raw metrics for detailed analysis
    user_metrics: Dict[str, StemMetrics]
    reference_metrics: Dict[str, StemMetrics]

    # Status
    success: bool = True
    error_message: Optional[str] = None


class ReferenceComparator:
    """Compare user mixes against reference tracks stem-by-stem."""

    # Thresholds for recommendations
    LOUDNESS_THRESHOLD_DB = 2.0      # Recommend action if diff > 2dB
    STEREO_WIDTH_THRESHOLD_PCT = 15  # Recommend action if diff > 15%
    FREQUENCY_THRESHOLD_PCT = 8      # Recommend action if band diff > 8%
    SPECTRAL_CENTROID_THRESHOLD_HZ = 200  # Recommend if diff > 200Hz

    # Frequency band definitions
    FREQ_BANDS = {
        'bass': (20, 250),
        'low_mid': (250, 500),
        'mid': (500, 2000),
        'high_mid': (2000, 6000),
        'high': (6000, 20000)
    }

    # Stem priority for recommendations (higher = more important)
    STEM_PRIORITY = {
        'drums': 4,
        'bass': 4,
        'vocals': 3,
        'other': 2
    }

    def __init__(
        self,
        separator: Optional[StemSeparator] = None,
        storage: Optional[ReferenceStorage] = None,
        cache_dir: str = "./cache/stems",
        library_dir: str = "./reference_library",
        verbose: bool = False
    ):
        """
        Initialize comparator.

        Args:
            separator: StemSeparator instance (creates one if None)
            storage: ReferenceStorage instance (creates one if None)
            cache_dir: Directory for stem cache
            library_dir: Directory for reference library
            verbose: Enable verbose output
        """
        self.separator = separator or StemSeparator(cache_dir=cache_dir, verbose=verbose)
        self.storage = storage or ReferenceStorage(library_dir=library_dir, verbose=verbose)
        self.verbose = verbose

    def compare(
        self,
        user_audio: str,
        reference_audio: str,
        progress_callback: Optional[Callable[[ComparisonProgress], None]] = None
    ) -> ComparisonResult:
        """
        Compare user mix against reference track.

        Args:
            user_audio: Path to user's mix
            reference_audio: Path to reference track
            progress_callback: Progress update callback

        Returns:
            ComparisonResult with detailed stem-by-stem comparison
        """
        try:
            # Validate inputs
            user_path = Path(user_audio)
            ref_path = Path(reference_audio)

            if not user_path.exists():
                return self._error_result(user_audio, reference_audio,
                                          f"User audio not found: {user_audio}")
            if not ref_path.exists():
                return self._error_result(user_audio, reference_audio,
                                          f"Reference audio not found: {reference_audio}")

            # Step 1: Separate user audio
            if progress_callback:
                progress_callback(ComparisonProgress(
                    stage='separating_user',
                    progress_pct=10,
                    message='Separating your mix into stems...'
                ))

            user_stems = self.separator.separate(user_audio)
            if not user_stems.success:
                return self._error_result(user_audio, reference_audio,
                                          f"Failed to separate user audio: {user_stems.error_message}")

            # Step 2: Separate reference audio
            if progress_callback:
                progress_callback(ComparisonProgress(
                    stage='separating_reference',
                    progress_pct=40,
                    message='Separating reference track into stems...'
                ))

            ref_stems = self.separator.separate(reference_audio)
            if not ref_stems.success:
                return self._error_result(user_audio, reference_audio,
                                          f"Failed to separate reference audio: {ref_stems.error_message}")

            # Step 3: Analyze each stem pair
            if progress_callback:
                progress_callback(ComparisonProgress(
                    stage='analyzing',
                    progress_pct=70,
                    message='Analyzing and comparing stems...'
                ))

            user_metrics = {}
            ref_metrics = {}
            stem_comparisons = {}

            for stem_type in StemType:
                stem_name = stem_type.value

                if stem_type in user_stems.stems and stem_type in ref_stems.stems:
                    # Analyze both stems
                    user_stem_metrics = self.analyze_stem(
                        user_stems.stems[stem_type].file_path, stem_name
                    )
                    ref_stem_metrics = self.analyze_stem(
                        ref_stems.stems[stem_type].file_path, stem_name
                    )

                    user_metrics[stem_name] = user_stem_metrics
                    ref_metrics[stem_name] = ref_stem_metrics

                    # Compare stems
                    comparison = self._compare_stems(user_stem_metrics, ref_stem_metrics)
                    stem_comparisons[stem_name] = comparison

            # Step 4: Calculate overall metrics
            overall_loudness_diff = self._calculate_overall_loudness_diff(user_metrics, ref_metrics)
            balance_score = self._calculate_balance_score(stem_comparisons)

            # Step 5: Generate prioritized recommendations
            priority_recommendations = self._prioritize_recommendations(stem_comparisons)

            # Step 6: Store reference analytics for future use
            if progress_callback:
                progress_callback(ComparisonProgress(
                    stage='storing',
                    progress_pct=90,
                    message='Storing reference analytics...'
                ))

            # Add reference to library if not already there
            ref_id = self._store_reference_if_new(reference_audio, ref_metrics)

            # Complete
            if progress_callback:
                progress_callback(ComparisonProgress(
                    stage='complete',
                    progress_pct=100,
                    message='Comparison complete'
                ))

            return ComparisonResult(
                user_file=str(user_path.absolute()),
                reference_file=str(ref_path.absolute()),
                reference_id=ref_id,
                comparison_timestamp=datetime.now().isoformat(),
                stem_comparisons=stem_comparisons,
                overall_loudness_diff_db=overall_loudness_diff,
                overall_balance_score=balance_score,
                priority_recommendations=priority_recommendations,
                user_metrics=user_metrics,
                reference_metrics=ref_metrics,
                success=True
            )

        except Exception as e:
            return self._error_result(user_audio, reference_audio, str(e))

    def compare_with_stored(
        self,
        user_audio: str,
        reference_id: str,
        progress_callback: Optional[Callable[[ComparisonProgress], None]] = None
    ) -> ComparisonResult:
        """
        Compare user mix against stored reference analytics (faster).

        Args:
            user_audio: Path to user's mix
            reference_id: ID of stored reference track
            progress_callback: Progress update callback

        Returns:
            ComparisonResult using stored analytics
        """
        # Get stored reference
        ref_analytics = self.storage.get_reference(reference_id)
        if not ref_analytics:
            return self._error_result(user_audio, "",
                                      f"Reference not found: {reference_id}")

        if not ref_analytics.stems_separated or not ref_analytics.stem_metrics:
            return self._error_result(user_audio, ref_analytics.metadata.file_path,
                                      "Stored reference has no stem analysis. Re-analyze with stem separation.")

        try:
            # Separate user audio
            if progress_callback:
                progress_callback(ComparisonProgress(
                    stage='separating_user',
                    progress_pct=20,
                    message='Separating your mix into stems...'
                ))

            user_stems = self.separator.separate(user_audio)
            if not user_stems.success:
                return self._error_result(user_audio, ref_analytics.metadata.file_path,
                                          f"Failed to separate user audio: {user_stems.error_message}")

            # Analyze user stems
            if progress_callback:
                progress_callback(ComparisonProgress(
                    stage='analyzing',
                    progress_pct=60,
                    message='Analyzing your stems...'
                ))

            user_metrics = {}
            stem_comparisons = {}

            # Convert stored stem metrics
            ref_metrics = {}
            for stem_name, metrics in ref_analytics.stem_metrics.items():
                if isinstance(metrics, dict):
                    ref_metrics[stem_name] = StemMetrics(**metrics)
                else:
                    ref_metrics[stem_name] = metrics

            for stem_type in StemType:
                stem_name = stem_type.value

                if stem_type in user_stems.stems and stem_name in ref_metrics:
                    user_stem_metrics = self.analyze_stem(
                        user_stems.stems[stem_type].file_path, stem_name
                    )
                    user_metrics[stem_name] = user_stem_metrics

                    comparison = self._compare_stems(user_stem_metrics, ref_metrics[stem_name])
                    stem_comparisons[stem_name] = comparison

            # Calculate overall metrics
            overall_loudness_diff = self._calculate_overall_loudness_diff(user_metrics, ref_metrics)
            balance_score = self._calculate_balance_score(stem_comparisons)
            priority_recommendations = self._prioritize_recommendations(stem_comparisons)

            if progress_callback:
                progress_callback(ComparisonProgress(
                    stage='complete',
                    progress_pct=100,
                    message='Comparison complete'
                ))

            return ComparisonResult(
                user_file=str(Path(user_audio).absolute()),
                reference_file=ref_analytics.metadata.file_path,
                reference_id=reference_id,
                comparison_timestamp=datetime.now().isoformat(),
                stem_comparisons=stem_comparisons,
                overall_loudness_diff_db=overall_loudness_diff,
                overall_balance_score=balance_score,
                priority_recommendations=priority_recommendations,
                user_metrics=user_metrics,
                reference_metrics=ref_metrics,
                success=True
            )

        except Exception as e:
            return self._error_result(user_audio, ref_analytics.metadata.file_path, str(e))

    def analyze_stem(
        self,
        stem_path: str,
        stem_type: str
    ) -> StemMetrics:
        """
        Analyze a single stem for all metrics.

        Args:
            stem_path: Path to stem audio file
            stem_type: Type of stem ('vocals', 'drums', 'bass', 'other')

        Returns:
            StemMetrics with complete analysis
        """
        y, sr = librosa.load(stem_path, sr=None, mono=False)

        # Handle stereo vs mono
        is_stereo = len(y.shape) > 1 and y.shape[0] == 2
        if is_stereo:
            y_mono = librosa.to_mono(y)
            # Calculate stereo metrics
            left, right = y[0], y[1]
            correlation = float(np.corrcoef(left, right)[0, 1])
            stereo_width = (1 - abs(correlation)) * 100
        else:
            y_mono = y if len(y.shape) == 1 else y[0]
            correlation = 1.0
            stereo_width = 0.0

        # Loudness metrics
        peak = np.max(np.abs(y_mono))
        peak_db = float(20 * np.log10(peak + 1e-10))
        rms = np.sqrt(np.mean(y_mono ** 2))
        rms_db = float(20 * np.log10(rms + 1e-10))

        # Approximate LUFS
        integrated_lufs = rms_db - 0.691

        # Dynamic range
        dynamic_range = peak_db - rms_db

        # Spectral analysis
        spectral_centroid = float(np.mean(librosa.feature.spectral_centroid(y=y_mono, sr=sr)))

        # Frequency band energies
        D = np.abs(librosa.stft(y_mono, n_fft=4096))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=4096)
        total_energy = np.sum(D ** 2) + 1e-10

        band_energies = {}
        for band_name, (low, high) in self.FREQ_BANDS.items():
            mask = (freqs >= low) & (freqs < high)
            band_energy = np.sum(D[mask, :] ** 2)
            band_energies[band_name] = float(band_energy / total_energy * 100)

        # Compute spectrum for visualization (256 points)
        avg_spectrum = np.mean(D, axis=1)
        spectrum_db = 20 * np.log10(avg_spectrum + 1e-10)
        indices = np.linspace(0, len(spectrum_db) - 1, 256, dtype=int)
        frequency_spectrum = spectrum_db[indices].tolist()

        return StemMetrics(
            stem_type=stem_type,
            peak_db=peak_db,
            rms_db=rms_db,
            integrated_lufs=integrated_lufs,
            spectral_centroid_hz=spectral_centroid,
            bass_energy_pct=band_energies.get('bass', 0),
            low_mid_energy_pct=band_energies.get('low_mid', 0),
            mid_energy_pct=band_energies.get('mid', 0),
            high_mid_energy_pct=band_energies.get('high_mid', 0),
            high_energy_pct=band_energies.get('high', 0),
            frequency_spectrum=frequency_spectrum,
            stereo_width_pct=stereo_width,
            correlation=correlation,
            dynamic_range_db=dynamic_range,
            crest_factor_db=dynamic_range
        )

    def _compare_stems(
        self,
        user_metrics: StemMetrics,
        ref_metrics: StemMetrics
    ) -> StemComparison:
        """Compare two stem metrics and generate recommendations."""
        stem_type = user_metrics.stem_type

        # Calculate differences (user - reference)
        rms_diff = user_metrics.rms_db - ref_metrics.rms_db
        lufs_diff = user_metrics.integrated_lufs - ref_metrics.integrated_lufs
        centroid_diff = user_metrics.spectral_centroid_hz - ref_metrics.spectral_centroid_hz
        width_diff = user_metrics.stereo_width_pct - ref_metrics.stereo_width_pct
        dynamic_diff = user_metrics.dynamic_range_db - ref_metrics.dynamic_range_db

        # Frequency band differences
        bass_diff = user_metrics.bass_energy_pct - ref_metrics.bass_energy_pct
        low_mid_diff = user_metrics.low_mid_energy_pct - ref_metrics.low_mid_energy_pct
        mid_diff = user_metrics.mid_energy_pct - ref_metrics.mid_energy_pct
        high_mid_diff = user_metrics.high_mid_energy_pct - ref_metrics.high_mid_energy_pct
        high_diff = user_metrics.high_energy_pct - ref_metrics.high_energy_pct

        # Determine severity
        severity = self._assess_severity(
            rms_diff, width_diff, bass_diff, low_mid_diff, mid_diff, high_mid_diff, high_diff
        )

        # Generate recommendations
        recommendations = self._generate_stem_recommendations(
            stem_type, rms_diff, lufs_diff, centroid_diff, width_diff,
            bass_diff, low_mid_diff, mid_diff, high_mid_diff, high_diff,
            ref_metrics
        )

        return StemComparison(
            stem_type=stem_type,
            user_rms_db=user_metrics.rms_db,
            user_lufs=user_metrics.integrated_lufs,
            user_spectral_centroid_hz=user_metrics.spectral_centroid_hz,
            user_stereo_width_pct=user_metrics.stereo_width_pct,
            ref_rms_db=ref_metrics.rms_db,
            ref_lufs=ref_metrics.integrated_lufs,
            ref_spectral_centroid_hz=ref_metrics.spectral_centroid_hz,
            ref_stereo_width_pct=ref_metrics.stereo_width_pct,
            rms_diff_db=rms_diff,
            lufs_diff=lufs_diff,
            spectral_centroid_diff_hz=centroid_diff,
            stereo_width_diff_pct=width_diff,
            dynamic_range_diff_db=dynamic_diff,
            bass_diff_pct=bass_diff,
            low_mid_diff_pct=low_mid_diff,
            mid_diff_pct=mid_diff,
            high_mid_diff_pct=high_mid_diff,
            high_diff_pct=high_diff,
            severity=severity,
            recommendations=recommendations
        )

    def _assess_severity(
        self,
        rms_diff: float,
        width_diff: float,
        bass_diff: float,
        low_mid_diff: float,
        mid_diff: float,
        high_mid_diff: float,
        high_diff: float
    ) -> str:
        """Assess overall severity of differences."""
        issues = 0

        if abs(rms_diff) > self.LOUDNESS_THRESHOLD_DB * 2:
            issues += 2
        elif abs(rms_diff) > self.LOUDNESS_THRESHOLD_DB:
            issues += 1

        if abs(width_diff) > self.STEREO_WIDTH_THRESHOLD_PCT * 2:
            issues += 2
        elif abs(width_diff) > self.STEREO_WIDTH_THRESHOLD_PCT:
            issues += 1

        freq_diffs = [bass_diff, low_mid_diff, mid_diff, high_mid_diff, high_diff]
        for diff in freq_diffs:
            if abs(diff) > self.FREQUENCY_THRESHOLD_PCT * 2:
                issues += 1
            elif abs(diff) > self.FREQUENCY_THRESHOLD_PCT:
                issues += 0.5

        if issues >= 4:
            return 'significant'
        elif issues >= 2:
            return 'moderate'
        elif issues >= 1:
            return 'minor'
        else:
            return 'good'

    def _generate_stem_recommendations(
        self,
        stem_type: str,
        rms_diff: float,
        lufs_diff: float,
        centroid_diff: float,
        width_diff: float,
        bass_diff: float,
        low_mid_diff: float,
        mid_diff: float,
        high_mid_diff: float,
        high_diff: float,
        ref_metrics: StemMetrics
    ) -> List[str]:
        """Generate actionable recommendations for a stem."""
        recommendations = []
        stem_label = stem_type.upper()

        # Loudness recommendations
        if abs(rms_diff) > self.LOUDNESS_THRESHOLD_DB:
            if rms_diff > 0:
                recommendations.append(
                    f"{stem_label}: Reduce level by {abs(rms_diff):.1f}dB "
                    f"(yours: {ref_metrics.rms_db + rms_diff:.1f}dB, ref: {ref_metrics.rms_db:.1f}dB)"
                )
            else:
                recommendations.append(
                    f"{stem_label}: Boost level by {abs(rms_diff):.1f}dB "
                    f"(yours: {ref_metrics.rms_db + rms_diff:.1f}dB, ref: {ref_metrics.rms_db:.1f}dB)"
                )

        # Stereo width recommendations
        if abs(width_diff) > self.STEREO_WIDTH_THRESHOLD_PCT:
            if width_diff > 0:
                if stem_type == 'bass':
                    recommendations.append(
                        f"{stem_label}: Too wide - narrow stereo image or mono the bass "
                        f"(yours: {ref_metrics.stereo_width_pct + width_diff:.0f}%, ref: {ref_metrics.stereo_width_pct:.0f}%)"
                    )
                else:
                    recommendations.append(
                        f"{stem_label}: Consider narrowing stereo width "
                        f"(yours: {ref_metrics.stereo_width_pct + width_diff:.0f}%, ref: {ref_metrics.stereo_width_pct:.0f}%)"
                    )
            else:
                recommendations.append(
                    f"{stem_label}: Add stereo width "
                    f"(yours: {ref_metrics.stereo_width_pct + width_diff:.0f}%, ref: {ref_metrics.stereo_width_pct:.0f}%)"
                )

        # Frequency balance recommendations
        if abs(bass_diff) > self.FREQUENCY_THRESHOLD_PCT:
            action = "cut" if bass_diff > 0 else "boost"
            recommendations.append(
                f"{stem_label}: {action.capitalize()} 20-250Hz by {abs(bass_diff) / 3:.1f}dB "
                f"({'+' if bass_diff > 0 else ''}{bass_diff:.1f}% vs reference)"
            )

        if abs(low_mid_diff) > self.FREQUENCY_THRESHOLD_PCT:
            action = "cut" if low_mid_diff > 0 else "boost"
            recommendations.append(
                f"{stem_label}: {action.capitalize()} 250-500Hz by {abs(low_mid_diff) / 3:.1f}dB "
                f"({'+' if low_mid_diff > 0 else ''}{low_mid_diff:.1f}% vs reference)"
            )

        if abs(mid_diff) > self.FREQUENCY_THRESHOLD_PCT:
            action = "cut" if mid_diff > 0 else "boost"
            recommendations.append(
                f"{stem_label}: {action.capitalize()} 500Hz-2kHz by {abs(mid_diff) / 3:.1f}dB "
                f"({'+' if mid_diff > 0 else ''}{mid_diff:.1f}% vs reference)"
            )

        if abs(high_mid_diff) > self.FREQUENCY_THRESHOLD_PCT:
            action = "cut" if high_mid_diff > 0 else "boost"
            recommendations.append(
                f"{stem_label}: {action.capitalize()} 2-6kHz (presence) by {abs(high_mid_diff) / 3:.1f}dB "
                f"({'+' if high_mid_diff > 0 else ''}{high_mid_diff:.1f}% vs reference)"
            )

        if abs(high_diff) > self.FREQUENCY_THRESHOLD_PCT:
            action = "cut" if high_diff > 0 else "boost"
            recommendations.append(
                f"{stem_label}: {action.capitalize()} 6-20kHz (air/brightness) by {abs(high_diff) / 3:.1f}dB "
                f"({'+' if high_diff > 0 else ''}{high_diff:.1f}% vs reference)"
            )

        # Spectral centroid (brightness) recommendation
        if abs(centroid_diff) > self.SPECTRAL_CENTROID_THRESHOLD_HZ:
            if centroid_diff > 0:
                recommendations.append(
                    f"{stem_label}: Overall too bright - consider high shelf cut or reduce presence"
                )
            else:
                recommendations.append(
                    f"{stem_label}: Lacks brightness - consider high shelf boost or add air"
                )

        return recommendations

    def _calculate_overall_loudness_diff(
        self,
        user_metrics: Dict[str, StemMetrics],
        ref_metrics: Dict[str, StemMetrics]
    ) -> float:
        """Calculate overall loudness difference between mixes."""
        user_total_rms = 0
        ref_total_rms = 0
        count = 0

        for stem_name in user_metrics:
            if stem_name in ref_metrics:
                # Convert from dB for averaging
                user_total_rms += 10 ** (user_metrics[stem_name].rms_db / 20)
                ref_total_rms += 10 ** (ref_metrics[stem_name].rms_db / 20)
                count += 1

        if count == 0:
            return 0.0

        user_avg_db = 20 * np.log10(user_total_rms / count + 1e-10)
        ref_avg_db = 20 * np.log10(ref_total_rms / count + 1e-10)

        return float(user_avg_db - ref_avg_db)

    def _calculate_balance_score(
        self,
        stem_comparisons: Dict[str, StemComparison]
    ) -> float:
        """Calculate 0-100 score for how close the mix balance is."""
        if not stem_comparisons:
            return 0.0

        # Score based on how close each metric is to reference
        total_score = 100.0
        penalties = 0

        for stem_name, comparison in stem_comparisons.items():
            # Loudness penalty (max -10 per stem)
            loudness_penalty = min(10, abs(comparison.rms_diff_db) * 2)
            penalties += loudness_penalty

            # Frequency balance penalty (max -10 per stem)
            freq_diffs = [
                comparison.bass_diff_pct,
                comparison.low_mid_diff_pct,
                comparison.mid_diff_pct,
                comparison.high_mid_diff_pct,
                comparison.high_diff_pct
            ]
            freq_penalty = min(10, sum(abs(d) for d in freq_diffs) / 5)
            penalties += freq_penalty

            # Stereo width penalty (max -5 per stem)
            width_penalty = min(5, abs(comparison.stereo_width_diff_pct) / 5)
            penalties += width_penalty

        # Normalize penalty based on number of stems
        max_penalty = len(stem_comparisons) * 25
        normalized_penalty = (penalties / max_penalty) * 100 if max_penalty > 0 else 0

        return max(0, total_score - normalized_penalty)

    def _prioritize_recommendations(
        self,
        stem_comparisons: Dict[str, StemComparison]
    ) -> List[str]:
        """Sort all recommendations by impact/importance."""
        all_recs = []

        for stem_name, comparison in stem_comparisons.items():
            priority = self.STEM_PRIORITY.get(stem_name, 1)

            # Add severity multiplier
            severity_mult = {
                'significant': 3,
                'moderate': 2,
                'minor': 1,
                'good': 0
            }.get(comparison.severity, 1)

            for rec in comparison.recommendations:
                # Higher score = more important
                score = priority * severity_mult

                # Boost loudness recommendations
                if 'level' in rec.lower() or 'reduce' in rec.lower() or 'boost' in rec.lower():
                    score += 1

                all_recs.append((score, rec))

        # Sort by score descending
        all_recs.sort(key=lambda x: x[0], reverse=True)

        return [rec for score, rec in all_recs]

    def _store_reference_if_new(
        self,
        reference_audio: str,
        ref_metrics: Dict[str, StemMetrics]
    ) -> Optional[str]:
        """Store reference in library if not already there."""
        try:
            # Check if already in library
            existing = self.storage.list_references()
            ref_path = str(Path(reference_audio).absolute())

            for track in existing:
                if track.file_path == ref_path:
                    return track.track_id

            # Add to library
            analytics = self.storage.add_reference(
                reference_audio,
                stem_metrics={k: v for k, v in ref_metrics.items()}
            )
            return analytics.metadata.track_id

        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not store reference: {e}")
            return None

    def _error_result(
        self,
        user_file: str,
        ref_file: str,
        error_message: str
    ) -> ComparisonResult:
        """Create an error result."""
        return ComparisonResult(
            user_file=user_file,
            reference_file=ref_file,
            reference_id=None,
            comparison_timestamp=datetime.now().isoformat(),
            stem_comparisons={},
            overall_loudness_diff_db=0,
            overall_balance_score=0,
            priority_recommendations=[],
            user_metrics={},
            reference_metrics={},
            success=False,
            error_message=error_message
        )


def compare_to_reference(
    user_audio: str,
    reference_audio: str
) -> ComparisonResult:
    """Quick function to compare a mix against a reference."""
    comparator = ReferenceComparator()
    return comparator.compare(user_audio, reference_audio)
