"""
Harmonic Content Analyzer

Analyzes harmonic content including:
- Key detection using chromagram analysis
- Harmonic complexity measurement
- Key consistency over time
- Chord change rate estimation
- Music theory relationships

Based on ai-music-mix-analyzer implementation, adapted for AbletonAIAnalysis.
"""

import numpy as np
import librosa
from scipy.stats import entropy
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from music_theory import (
    KEYS,
    PITCH_CLASS_NAMES,
    RELATIVE_MINOR,
    RELATIVE_MAJOR,
    get_key_relationship_info,
    get_camelot_notation,
)


@dataclass
class HarmonicInfo:
    """Harmonic content analysis results."""
    key: str                                    # Detected key (e.g., "A minor", "C major")
    key_confidence: float                       # 0-1 confidence in detection
    harmonic_complexity: float                  # 0-100 (Shannon entropy based)
    key_consistency: float                      # 0-100 (% segments in detected key)
    chord_changes_per_minute: float             # Estimated chord change rate
    top_key_candidates: List[Dict[str, Any]]    # Top 3 key candidates with confidence
    key_relationships: Dict[str, Any]           # Music theory relationships
    camelot_notation: str                       # DJ mixing notation (e.g., "8A")
    analysis: List[str] = field(default_factory=list)  # Textual analysis points


class HarmonicAnalyzer:
    """
    Analyzes harmonic content of audio files.

    Uses chromagram analysis to detect musical key, measure harmonic complexity,
    and track key consistency throughout the track.
    """

    def __init__(self, config=None):
        """
        Initialize the harmonic analyzer.

        Args:
            config: Optional configuration object with harmonic analysis settings
        """
        self.config = config

        # Load settings from config or use defaults
        if config and hasattr(config, 'harmonic'):
            harmonic_cfg = config.harmonic
            self.segment_length_sec = harmonic_cfg.get('segment_length_sec', 5.0)
            self.segment_overlap = harmonic_cfg.get('segment_overlap', 0.5)
            self.min_key_confidence = harmonic_cfg.get('min_key_confidence', 0.6)
        else:
            self.segment_length_sec = 5.0
            self.segment_overlap = 0.5
            self.min_key_confidence = 0.6

    def analyze(self, y: np.ndarray, sr: int) -> HarmonicInfo:
        """
        Perform harmonic content analysis on audio.

        Args:
            y: Audio time series (mono)
            sr: Sample rate

        Returns:
            HarmonicInfo with key detection and harmonic analysis results
        """
        # Ensure mono
        if len(y.shape) > 1:
            y = librosa.to_mono(y)

        analysis = []

        # Compute chromagram using Constant-Q Transform
        try:
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        except Exception:
            # Fallback to STFT-based chroma if CQT fails
            try:
                chroma = librosa.feature.chroma_stft(y=y, sr=sr)
            except Exception as e:
                # Return default values if both fail
                return self._create_default_result(f"Chromagram analysis failed: {str(e)}")

        # Detect key
        key, key_confidence, is_minor, top_candidates = self._detect_key(chroma)

        # Format key name
        if key_confidence < self.min_key_confidence:
            key_name = "Unknown"
            analysis.append(f"Key detection uncertain (confidence: {key_confidence:.0%})")
        else:
            key_name = f"{key} {'minor' if is_minor else 'major'}"
            analysis.append(f"Detected key: {key_name} ({key_confidence:.0%} confidence)")

        # Get music theory relationships
        key_short = f"{key}m" if is_minor else key
        key_relationships = get_key_relationship_info(key_short)
        camelot = get_camelot_notation(key_short)

        # Calculate harmonic complexity
        harmonic_complexity = self._calculate_complexity(chroma)
        if harmonic_complexity > 70:
            analysis.append(f"High harmonic complexity ({harmonic_complexity:.0f}%) - rich chord progressions")
        elif harmonic_complexity < 30:
            analysis.append(f"Low harmonic complexity ({harmonic_complexity:.0f}%) - simple harmonic content")
        else:
            analysis.append(f"Moderate harmonic complexity ({harmonic_complexity:.0f}%)")

        # Calculate key consistency
        key_consistency = self._calculate_key_consistency(y, sr, key, is_minor)
        if key_consistency < 70:
            analysis.append(f"Key varies throughout track ({key_consistency:.0f}% consistency) - possible modulations")
        else:
            analysis.append(f"Consistent key throughout ({key_consistency:.0f}%)")

        # Estimate chord changes per minute
        chord_changes = self._estimate_chord_changes(chroma, sr)
        analysis.append(f"Estimated {chord_changes:.1f} chord changes per minute")

        # Add mixing suggestions
        if key_name != "Unknown":
            compatible = key_relationships.get('compatible_keys', [])
            if compatible:
                analysis.append(f"Compatible keys for mixing: {', '.join(compatible[:5])}")
            analysis.append(f"Camelot notation: {camelot}")

        return HarmonicInfo(
            key=key_name,
            key_confidence=key_confidence,
            harmonic_complexity=harmonic_complexity,
            key_consistency=key_consistency,
            chord_changes_per_minute=chord_changes,
            top_key_candidates=top_candidates,
            key_relationships=key_relationships,
            camelot_notation=camelot,
            analysis=analysis
        )

    def _detect_key(self, chroma: np.ndarray) -> tuple:
        """
        Detect the musical key from chromagram.

        Returns:
            Tuple of (key_name, confidence, is_minor, top_candidates)
        """
        # Sum energy across time for each pitch class
        chroma_sum = np.sum(chroma, axis=1)

        # Normalize
        if np.sum(chroma_sum) > 0:
            chroma_norm = chroma_sum / np.sum(chroma_sum)
        else:
            return ('C', 0.0, False, [])

        # Major and minor key profiles (Krumhansl-Schmuckler)
        major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

        # Normalize profiles
        major_profile = major_profile / np.sum(major_profile)
        minor_profile = minor_profile / np.sum(minor_profile)

        # Calculate correlation with each possible key
        major_correlations = []
        minor_correlations = []

        for i in range(12):
            # Rotate chroma to test each key
            rotated = np.roll(chroma_norm, -i)

            # Correlate with major and minor profiles
            major_corr = np.corrcoef(rotated, major_profile)[0, 1]
            minor_corr = np.corrcoef(rotated, minor_profile)[0, 1]

            major_correlations.append((PITCH_CLASS_NAMES[i], major_corr, False))
            minor_correlations.append((PITCH_CLASS_NAMES[i], minor_corr, True))

        # Combine and sort all candidates
        all_candidates = major_correlations + minor_correlations
        all_candidates.sort(key=lambda x: x[1], reverse=True)

        # Get top candidate
        best_key, best_corr, is_minor = all_candidates[0]

        # Convert correlation to confidence (0-1)
        confidence = max(0.0, min(1.0, (best_corr + 1) / 2))

        # Build top candidates list
        top_candidates = []
        for key, corr, minor in all_candidates[:3]:
            key_name = f"{key}m" if minor else key
            conf = max(0.0, min(1.0, (corr + 1) / 2))
            top_candidates.append({
                'key': key_name,
                'confidence': conf,
                'display': f"{key} {'minor' if minor else 'major'}"
            })

        return (best_key, confidence, is_minor, top_candidates)

    def _calculate_complexity(self, chroma: np.ndarray) -> float:
        """
        Calculate harmonic complexity using Shannon entropy.

        Higher entropy = more evenly distributed pitch classes = more complex harmony.

        Returns:
            Complexity score 0-100
        """
        # Sum energy across time
        chroma_sum = np.sum(chroma, axis=1)

        # Normalize to probability distribution
        if np.sum(chroma_sum) > 0:
            chroma_prob = chroma_sum / np.sum(chroma_sum)
        else:
            return 0.0

        # Calculate Shannon entropy
        ent = entropy(chroma_prob)

        # Normalize to 0-100 (max entropy for 12 classes is log(12))
        max_entropy = np.log(12)
        complexity = (ent / max_entropy) * 100

        return float(complexity)

    def _calculate_key_consistency(
        self,
        y: np.ndarray,
        sr: int,
        detected_key: str,
        is_minor: bool
    ) -> float:
        """
        Calculate how consistently the detected key appears throughout the track.

        Splits audio into segments and checks key detection in each.

        Returns:
            Consistency score 0-100 (% of segments matching detected key)
        """
        duration = len(y) / sr
        segment_samples = int(self.segment_length_sec * sr)
        hop_samples = int(segment_samples * (1 - self.segment_overlap))

        if segment_samples >= len(y):
            return 100.0  # Track too short for segmentation

        matching_segments = 0
        total_segments = 0

        for start in range(0, len(y) - segment_samples, hop_samples):
            end = start + segment_samples
            segment = y[start:end]

            try:
                chroma = librosa.feature.chroma_cqt(y=segment, sr=sr)
                seg_key, _, seg_minor, _ = self._detect_key(chroma)

                # Check if segment key matches
                if seg_key == detected_key and seg_minor == is_minor:
                    matching_segments += 1

            except Exception:
                pass  # Skip failed segments

            total_segments += 1

        if total_segments == 0:
            return 100.0

        return (matching_segments / total_segments) * 100

    def _estimate_chord_changes(self, chroma: np.ndarray, sr: int) -> float:
        """
        Estimate chord changes per minute from chromagram.

        Uses onset detection on chroma flux.

        Returns:
            Estimated chord changes per minute
        """
        # Calculate chroma flux (rate of change in chroma)
        chroma_diff = np.diff(chroma, axis=1)
        chroma_flux = np.sum(np.abs(chroma_diff), axis=0)

        # Find peaks in chroma flux (chord change candidates)
        # Use adaptive threshold
        threshold = np.mean(chroma_flux) + 0.5 * np.std(chroma_flux)

        peaks = []
        for i in range(1, len(chroma_flux) - 1):
            if chroma_flux[i] > threshold:
                if chroma_flux[i] > chroma_flux[i-1] and chroma_flux[i] > chroma_flux[i+1]:
                    peaks.append(i)

        # Calculate duration
        # hop_length for chroma is typically sr/512
        hop_length = 512
        duration_sec = (chroma.shape[1] * hop_length) / sr
        duration_min = duration_sec / 60

        if duration_min <= 0:
            return 0.0

        # Chord changes per minute
        changes_per_min = len(peaks) / duration_min

        return float(changes_per_min)

    def _create_default_result(self, error_msg: str) -> HarmonicInfo:
        """Create a default HarmonicInfo for error cases."""
        return HarmonicInfo(
            key="Unknown",
            key_confidence=0.0,
            harmonic_complexity=0.0,
            key_consistency=0.0,
            chord_changes_per_minute=0.0,
            top_key_candidates=[],
            key_relationships={},
            camelot_notation="Unknown",
            analysis=[error_msg]
        )
