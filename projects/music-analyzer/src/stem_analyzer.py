"""
Stem Analyzer Module

Analyzes multiple audio stems together to detect:
- Frequency clashes between stems
- Masking issues
- Volume balance problems
- Panning conflicts
"""

import numpy as np
import librosa
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from collections import defaultdict


@dataclass
class FrequencyClash:
    """Represents a frequency clash between two stems."""
    stem1: str
    stem2: str
    frequency_range: Tuple[float, float]  # Hz range
    overlap_amount: float  # 0-1 scale
    severity: str  # 'minor', 'moderate', 'severe'
    recommendation: str


@dataclass
class StemInfo:
    """Information about a single stem."""
    name: str
    path: str
    peak_db: float
    rms_db: float
    dominant_frequencies: List[Tuple[float, float]]  # (freq_hz, magnitude)
    frequency_profile: Dict[str, float]  # Band name -> energy percentage
    is_mono: bool
    panning: float  # -1 (left) to 1 (right), 0 = center


@dataclass
class StemAnalysisResult:
    """Complete multi-stem analysis result."""
    stems: List[StemInfo]
    clashes: List[FrequencyClash]
    balance_issues: List[Dict]
    masking_issues: List[Dict]
    recommendations: List[str]
    frequency_spectrum_data: Optional[Dict] = None  # For visualization


class StemAnalyzer:
    """Multi-stem frequency clash and balance analyzer."""

    # Default frequency bands for analysis
    DEFAULT_FREQ_BANDS = {
        'sub': (20, 60),
        'bass': (60, 200),
        'low_mid': (200, 500),
        'mid': (500, 2000),
        'high_mid': (2000, 6000),
        'high': (6000, 16000),
        'air': (16000, 20000)
    }

    # Common instrument frequency ranges (for intelligent recommendations)
    INSTRUMENT_RANGES = {
        'kick': (30, 150),
        'bass': (40, 300),
        'snare': (150, 5000),
        'hihat': (3000, 16000),
        'vocal': (100, 8000),
        'guitar': (80, 5000),
        'piano': (30, 8000),
        'synth': (100, 10000),
        'pad': (200, 8000)
    }

    def __init__(self, n_fft: int = 4096, config=None):
        self.config = config

        # Load from config or use defaults
        if config:
            self.n_fft = config.stems.get('fft_size', n_fft)
            # Load frequency bands from config
            bands_cfg = config.stems.get('bands', {})
            self.FREQ_BANDS = {
                'sub': tuple(bands_cfg.get('sub', [20, 60])),
                'bass': tuple(bands_cfg.get('bass', [60, 200])),
                'low_mid': tuple(bands_cfg.get('low_mid', [200, 500])),
                'mid': tuple(bands_cfg.get('mid', [500, 2000])),
                'high_mid': tuple(bands_cfg.get('high_mid', [2000, 6000])),
                'high': tuple(bands_cfg.get('high', [6000, 16000])),
                'air': tuple(bands_cfg.get('air', [16000, 20000])),
            }
            # Load thresholds
            self.clash_overlap_threshold = config.stems.get('clash_overlap_threshold', 0.3)
            self.clash_min_overlap = config.stems.get('clash_min_overlap_amount', 0.1)
            self.clash_severe_threshold = config.stems.get('clash_severe_threshold', 0.5)
            self.clash_moderate_threshold = config.stems.get('clash_moderate_threshold', 0.3)
            self.balance_too_loud_threshold = config.stems.get('balance_too_loud_threshold', 6)
            self.balance_too_quiet_threshold = config.stems.get('balance_too_quiet_threshold', 12)
            self.masking_level_diff = config.stems.get('masking_level_diff_threshold', 10)
            self.masking_freq_threshold = config.stems.get('masking_freq_overlap_threshold', 0.3)
        else:
            self.n_fft = n_fft
            self.FREQ_BANDS = self.DEFAULT_FREQ_BANDS.copy()
            self.clash_overlap_threshold = 0.3
            self.clash_min_overlap = 0.1
            self.clash_severe_threshold = 0.5
            self.clash_moderate_threshold = 0.3
            self.balance_too_loud_threshold = 6
            self.balance_too_quiet_threshold = 12
            self.masking_level_diff = 10
            self.masking_freq_threshold = 0.3

    def analyze_stems(self, stem_paths: List[str], stem_names: Optional[List[str]] = None) -> StemAnalysisResult:
        """
        Analyze multiple stems for clashes and balance issues.

        Args:
            stem_paths: List of paths to stem audio files
            stem_names: Optional list of names for each stem (defaults to filenames)

        Returns:
            StemAnalysisResult with complete analysis
        """
        if not stem_paths:
            raise ValueError("No stem paths provided")

        # Use filenames as names if not provided
        if stem_names is None:
            stem_names = [Path(p).stem for p in stem_paths]

        # Load and analyze each stem
        stems = []
        stem_spectrograms = {}

        for path, name in zip(stem_paths, stem_names):
            stem_info, spectrogram = self._analyze_single_stem(path, name)
            stems.append(stem_info)
            stem_spectrograms[name] = spectrogram

        # Detect frequency clashes
        clashes = self._detect_clashes(stems, stem_spectrograms)

        # Analyze balance
        balance_issues = self._analyze_balance(stems)

        # Detect masking
        masking_issues = self._detect_masking(stems, stem_spectrograms)

        # Generate recommendations
        recommendations = self._generate_recommendations(clashes, balance_issues, masking_issues, stems)

        # Prepare visualization data
        freq_data = self._prepare_visualization_data(stems, stem_spectrograms)

        return StemAnalysisResult(
            stems=stems,
            clashes=clashes,
            balance_issues=balance_issues,
            masking_issues=masking_issues,
            recommendations=recommendations,
            frequency_spectrum_data=freq_data
        )

    def _analyze_single_stem(self, path: str, name: str) -> Tuple[StemInfo, np.ndarray]:
        """Analyze a single stem and return its info and spectrogram."""
        # Load audio
        y, sr = librosa.load(path, sr=None, mono=False)

        # Check if mono or stereo
        is_mono = len(y.shape) == 1 or (len(y.shape) == 2 and y.shape[0] == 1)

        if is_mono:
            y_mono = y.flatten() if len(y.shape) > 1 else y
            panning = 0.0
        else:
            y_mono = librosa.to_mono(y)
            # Estimate panning from L/R balance
            left_rms = np.sqrt(np.mean(y[0] ** 2))
            right_rms = np.sqrt(np.mean(y[1] ** 2))
            total_rms = left_rms + right_rms + 1e-10
            panning = (right_rms - left_rms) / total_rms

        # Calculate levels
        peak = np.max(np.abs(y_mono))
        peak_db = float(20 * np.log10(peak + 1e-10))

        rms = np.sqrt(np.mean(y_mono ** 2))
        rms_db = float(20 * np.log10(rms + 1e-10))

        # Compute spectrogram
        D = np.abs(librosa.stft(y_mono, n_fft=self.n_fft))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=self.n_fft)

        # Find dominant frequencies
        avg_spectrum = np.mean(D, axis=1)
        dominant_indices = np.argsort(avg_spectrum)[-5:][::-1]
        dominant_frequencies = [(float(freqs[i]), float(avg_spectrum[i])) for i in dominant_indices if freqs[i] > 20]

        # Calculate frequency profile
        frequency_profile = {}
        total_energy = np.sum(avg_spectrum ** 2) + 1e-10

        for band_name, (low, high) in self.FREQ_BANDS.items():
            mask = (freqs >= low) & (freqs < high)
            band_energy = np.sum(avg_spectrum[mask] ** 2)
            frequency_profile[band_name] = float(band_energy / total_energy * 100)

        stem_info = StemInfo(
            name=name,
            path=path,
            peak_db=peak_db,
            rms_db=rms_db,
            dominant_frequencies=dominant_frequencies,
            frequency_profile=frequency_profile,
            is_mono=is_mono,
            panning=panning
        )

        return stem_info, D

    def _detect_clashes(
        self,
        stems: List[StemInfo],
        spectrograms: Dict[str, np.ndarray]
    ) -> List[FrequencyClash]:
        """Detect frequency clashes between pairs of stems."""
        clashes = []

        # Compare each pair of stems
        for i, stem1 in enumerate(stems):
            for stem2 in stems[i + 1:]:
                spec1 = np.mean(spectrograms[stem1.name], axis=1)
                spec2 = np.mean(spectrograms[stem2.name], axis=1)

                # Normalize spectra
                spec1_norm = spec1 / (np.max(spec1) + 1e-10)
                spec2_norm = spec2 / (np.max(spec2) + 1e-10)

                # Find overlapping regions (both stems have significant energy)
                threshold = 0.3  # 30% of peak
                overlap = (spec1_norm > threshold) & (spec2_norm > threshold)

                if np.any(overlap):
                    # Calculate overlap amount
                    overlap_product = spec1_norm * spec2_norm * overlap
                    overlap_amount = float(np.sum(overlap_product) / np.sum(overlap + 1e-10))

                    if overlap_amount > 0.1:  # Significant overlap
                        # Find the frequency range of overlap
                        overlap_indices = np.where(overlap)[0]
                        sr = 44100  # Assume standard sample rate for frequency calculation
                        freqs = librosa.fft_frequencies(sr=sr, n_fft=self.n_fft)

                        freq_low = float(freqs[overlap_indices[0]])
                        freq_high = float(freqs[overlap_indices[-1]])

                        # Determine severity
                        if overlap_amount > 0.5:
                            severity = 'severe'
                        elif overlap_amount > 0.3:
                            severity = 'moderate'
                        else:
                            severity = 'minor'

                        # Generate recommendation
                        recommendation = self._generate_clash_recommendation(
                            stem1.name, stem2.name, freq_low, freq_high
                        )

                        clashes.append(FrequencyClash(
                            stem1=stem1.name,
                            stem2=stem2.name,
                            frequency_range=(freq_low, freq_high),
                            overlap_amount=overlap_amount,
                            severity=severity,
                            recommendation=recommendation
                        ))

        return clashes

    def _generate_clash_recommendation(
        self,
        stem1: str,
        stem2: str,
        freq_low: float,
        freq_high: float
    ) -> str:
        """Generate a specific recommendation for a frequency clash."""
        center_freq = (freq_low + freq_high) / 2

        # Determine which stem might be more important at this frequency
        # This is a heuristic based on common mixing practices

        if center_freq < 100:
            return f"Cut {freq_low:.0f}-{freq_high:.0f}Hz on '{stem1}' or '{stem2}' by 2-4dB. Keep bass/kick in this range."
        elif center_freq < 300:
            return f"High-pass one of '{stem1}' or '{stem2}' around {freq_low:.0f}Hz to reduce low-end buildup."
        elif center_freq < 1000:
            return f"Cut {freq_low:.0f}-{freq_high:.0f}Hz on secondary element by 2-3dB to create space."
        elif center_freq < 4000:
            return f"Apply dynamic EQ sidechain between '{stem1}' and '{stem2}' at {center_freq:.0f}Hz."
        else:
            return f"Reduce high frequencies ({freq_low:.0f}-{freq_high:.0f}Hz) on less important element."

    def _analyze_balance(self, stems: List[StemInfo]) -> List[Dict]:
        """Analyze volume balance between stems."""
        issues = []

        if len(stems) < 2:
            return issues

        rms_values = [s.rms_db for s in stems]
        avg_rms = np.mean(rms_values)
        std_rms = np.std(rms_values)

        for stem in stems:
            diff_from_avg = stem.rms_db - avg_rms

            # Check for stems that are way louder or quieter than average
            if diff_from_avg > 6:
                issues.append({
                    'type': 'too_loud',
                    'stem': stem.name,
                    'severity': 'warning',
                    'message': f"'{stem.name}' is {diff_from_avg:.1f}dB louder than average",
                    'recommendation': f"Reduce '{stem.name}' volume by {diff_from_avg - 3:.1f}dB"
                })
            elif diff_from_avg < -12:
                issues.append({
                    'type': 'too_quiet',
                    'stem': stem.name,
                    'severity': 'info',
                    'message': f"'{stem.name}' is {abs(diff_from_avg):.1f}dB quieter than average",
                    'recommendation': f"Consider boosting '{stem.name}' by {abs(diff_from_avg) - 6:.1f}dB if it should be more prominent"
                })

        return issues

    def _detect_masking(
        self,
        stems: List[StemInfo],
        spectrograms: Dict[str, np.ndarray]
    ) -> List[Dict]:
        """Detect masking issues where one stem obscures another."""
        issues = []

        # Sort stems by RMS level (loudest first)
        sorted_stems = sorted(stems, key=lambda s: s.rms_db, reverse=True)

        for i, loud_stem in enumerate(sorted_stems):
            for quiet_stem in sorted_stems[i + 1:]:
                # Check if louder stem might be masking quieter stem
                level_diff = loud_stem.rms_db - quiet_stem.rms_db

                if level_diff > 10:  # Significant level difference
                    # Check frequency overlap
                    loud_spec = np.mean(spectrograms[loud_stem.name], axis=1)
                    quiet_spec = np.mean(spectrograms[quiet_stem.name], axis=1)

                    loud_norm = loud_spec / (np.max(loud_spec) + 1e-10)
                    quiet_norm = quiet_spec / (np.max(quiet_spec) + 1e-10)

                    # Find where quiet stem has significant energy
                    quiet_active = quiet_norm > 0.3
                    loud_at_quiet = loud_norm[quiet_active]

                    if np.any(loud_at_quiet > 0.5):
                        issues.append({
                            'type': 'masking',
                            'masker': loud_stem.name,
                            'masked': quiet_stem.name,
                            'severity': 'warning',
                            'message': f"'{loud_stem.name}' may be masking '{quiet_stem.name}'",
                            'recommendation': f"Cut overlapping frequencies on '{loud_stem.name}' or boost presence on '{quiet_stem.name}'"
                        })

        return issues

    def _generate_recommendations(
        self,
        clashes: List[FrequencyClash],
        balance_issues: List[Dict],
        masking_issues: List[Dict],
        stems: List[StemInfo]
    ) -> List[str]:
        """Generate overall recommendations based on all analysis."""
        recommendations = []

        # Clash recommendations
        severe_clashes = [c for c in clashes if c.severity == 'severe']
        if severe_clashes:
            recommendations.append(
                f"PRIORITY: Fix {len(severe_clashes)} severe frequency clash(es) - "
                "these are significantly impacting mix clarity"
            )

        # Balance recommendations
        if balance_issues:
            recommendations.append(
                "Review stem volumes - some elements may need level adjustments"
            )

        # Masking recommendations
        if masking_issues:
            recommendations.append(
                "Consider EQ carving to reduce masking between overlapping elements"
            )

        # Panning recommendations
        center_heavy = [s for s in stems if abs(s.panning) < 0.2]
        if len(center_heavy) > len(stems) * 0.7:
            recommendations.append(
                "Mix is center-heavy - pan some elements wider for better stereo separation"
            )

        # Low-end recommendations
        bass_heavy_stems = [
            s for s in stems
            if s.frequency_profile.get('sub', 0) + s.frequency_profile.get('bass', 0) > 40
        ]
        if len(bass_heavy_stems) > 2:
            recommendations.append(
                f"{len(bass_heavy_stems)} stems have significant low-end content - "
                "apply high-pass filters to non-bass elements"
            )

        return recommendations

    def _prepare_visualization_data(
        self,
        stems: List[StemInfo],
        spectrograms: Dict[str, np.ndarray]
    ) -> Dict:
        """Prepare data for frequency visualization."""
        sr = 44100
        freqs = librosa.fft_frequencies(sr=sr, n_fft=self.n_fft)

        data = {
            'frequencies': freqs.tolist(),
            'stems': {}
        }

        for stem in stems:
            avg_spectrum = np.mean(spectrograms[stem.name], axis=1)
            # Convert to dB
            spectrum_db = 20 * np.log10(avg_spectrum + 1e-10)
            data['stems'][stem.name] = {
                'spectrum_db': spectrum_db.tolist(),
                'peak_db': stem.peak_db,
                'rms_db': stem.rms_db,
                'frequency_profile': stem.frequency_profile
            }

        return data


def analyze_stems_quick(stem_paths: List[str]) -> StemAnalysisResult:
    """Quick function to analyze multiple stems."""
    analyzer = StemAnalyzer()
    return analyzer.analyze_stems(stem_paths)
