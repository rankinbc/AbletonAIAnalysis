"""
Trance Score Calculator Module.

Computes a composite score (0-1) indicating how well a track
conforms to trance music characteristics.

Weights:
    tempo_score: 0.20 (BPM in trance range)
    pumping_score: 0.15 (Sidechain presence)
    energy_progression: 0.15 (Breakdown/buildup patterns)
    four_on_floor: 0.12 (Kick pattern)
    supersaw_score: 0.10 (Stereo characteristics)
    acid_303_score: 0.08 (303 elements - optional)
    offbeat_hihat: 0.08 (Hi-hat patterns)
    spectral_brightness: 0.07 (High spectral centroid)
    tempo_stability: 0.05 (Consistent tempo)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


@dataclass
class TranceScoreBreakdown:
    """Detailed breakdown of trance score components."""
    tempo_score: float = 0.0
    pumping_score: float = 0.0
    energy_progression: float = 0.0
    four_on_floor: float = 0.0
    supersaw_score: float = 0.0
    acid_303_score: float = 0.0
    offbeat_hihat: float = 0.0
    spectral_brightness: float = 0.0
    tempo_stability: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            'tempo_score': self.tempo_score,
            'pumping_score': self.pumping_score,
            'energy_progression': self.energy_progression,
            'four_on_floor': self.four_on_floor,
            'supersaw_score': self.supersaw_score,
            'acid_303_score': self.acid_303_score,
            'offbeat_hihat': self.offbeat_hihat,
            'spectral_brightness': self.spectral_brightness,
            'tempo_stability': self.tempo_stability
        }


class TranceScoreCalculator:
    """
    Calculate composite trance score from extracted features.

    The calculator uses weighted scoring across multiple trance-specific
    characteristics to produce a 0-1 score indicating genre conformance.
    """

    # Default weights for each component
    WEIGHTS = {
        'tempo_score': 0.20,          # BPM in trance range
        'pumping_score': 0.15,        # Sidechain presence
        'energy_progression': 0.15,   # Breakdown/buildup patterns
        'four_on_floor': 0.12,        # Kick pattern
        'supersaw_score': 0.10,       # Stereo characteristics
        'acid_303_score': 0.08,       # 303 elements (optional)
        'offbeat_hihat': 0.08,        # Hi-hat patterns
        'spectral_brightness': 0.07,  # High spectral centroid
        'tempo_stability': 0.05       # Consistent tempo
    }

    def __init__(self, custom_weights: Optional[Dict[str, float]] = None):
        """
        Initialize calculator with optional custom weights.

        Args:
            custom_weights: Dict of component name -> weight.
                           Weights will be normalized to sum to 1.
        """
        if custom_weights:
            self.weights = self._normalize_weights(custom_weights)
        else:
            self.weights = self.WEIGHTS.copy()

    def _normalize_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Normalize weights to sum to 1."""
        total = sum(weights.values())
        if total > 0:
            return {k: v / total for k, v in weights.items()}
        return self.WEIGHTS.copy()

    def compute_total_score(
        self,
        features: dict
    ) -> Tuple[float, TranceScoreBreakdown]:
        """
        Compute total trance score from extracted features.

        Args:
            features: Dictionary with keys matching weight names,
                     each value should be 0-1 or convertible to score.

        Returns:
            (total_score, breakdown) where total_score is 0-1
        """
        breakdown = TranceScoreBreakdown()

        # Extract each component score
        breakdown.tempo_score = self._get_score(features, 'tempo_score')
        breakdown.pumping_score = self._get_score(features, 'pumping_score')
        breakdown.energy_progression = self._get_score(features, 'energy_progression')
        breakdown.four_on_floor = self._get_score(features, 'four_on_floor')
        breakdown.supersaw_score = self._get_score(features, 'supersaw_score')
        breakdown.acid_303_score = self._get_score(features, 'acid_303_score')
        breakdown.offbeat_hihat = self._get_score(features, 'offbeat_hihat')
        breakdown.spectral_brightness = self._get_score(features, 'spectral_brightness')
        breakdown.tempo_stability = self._get_score(features, 'tempo_stability')

        # Compute weighted total
        total_score = (
            self.weights['tempo_score'] * breakdown.tempo_score +
            self.weights['pumping_score'] * breakdown.pumping_score +
            self.weights['energy_progression'] * breakdown.energy_progression +
            self.weights['four_on_floor'] * breakdown.four_on_floor +
            self.weights['supersaw_score'] * breakdown.supersaw_score +
            self.weights['acid_303_score'] * breakdown.acid_303_score +
            self.weights['offbeat_hihat'] * breakdown.offbeat_hihat +
            self.weights['spectral_brightness'] * breakdown.spectral_brightness +
            self.weights['tempo_stability'] * breakdown.tempo_stability
        )

        return float(np.clip(total_score, 0.0, 1.0)), breakdown

    def _get_score(self, features: dict, key: str) -> float:
        """
        Extract score for a component, handling various input formats.

        Args:
            features: Feature dictionary
            key: Key to look for

        Returns:
            Score value (0-1)
        """
        if key not in features:
            return 0.0

        value = features[key]

        # Handle None
        if value is None:
            return 0.0

        # Handle dict with 'score' key
        if isinstance(value, dict):
            if 'score' in value:
                return float(np.clip(value['score'], 0.0, 1.0))
            return 0.0

        # Handle numeric
        try:
            return float(np.clip(value, 0.0, 1.0))
        except (TypeError, ValueError):
            return 0.0

    def compute_from_raw_features(
        self,
        tempo: float,
        tempo_stability: float,
        modulation_depth_db: float,
        energy_range: float,
        four_on_floor_strength: float,
        stereo_width: float,
        acid_score: float,
        offbeat_strength: float,
        spectral_centroid: float,
        sample_rate: int = 44100
    ) -> Tuple[float, TranceScoreBreakdown]:
        """
        Compute score from raw feature values (convenience method).

        This method converts raw values to normalized scores.

        Args:
            tempo: Detected BPM
            tempo_stability: Tempo consistency (0-1)
            modulation_depth_db: Sidechain depth in dB
            energy_range: Energy curve range (0-1)
            four_on_floor_strength: Kick pattern strength (0-1)
            stereo_width: Stereo width ratio (0-1)
            acid_score: 303 presence score (0-1)
            offbeat_strength: Offbeat hihat strength (0-1)
            spectral_centroid: Average spectral centroid in Hz
            sample_rate: Audio sample rate (for centroid normalization)

        Returns:
            (total_score, breakdown)
        """
        features = {
            'tempo_score': self._tempo_to_score(tempo),
            'pumping_score': self._modulation_to_score(modulation_depth_db),
            'energy_progression': energy_range,
            'four_on_floor': four_on_floor_strength,
            'supersaw_score': stereo_width,
            'acid_303_score': acid_score,
            'offbeat_hihat': offbeat_strength,
            'spectral_brightness': self._centroid_to_score(spectral_centroid, sample_rate),
            'tempo_stability': tempo_stability
        }

        return self.compute_total_score(features)

    def _tempo_to_score(self, tempo: float) -> float:
        """
        Convert tempo to score.

        Optimal: 138-140 BPM (score = 1.0)
        Good: 128-150 BPM (score = 0.5-1.0)
        Outside: < 0.5
        """
        if 138 <= tempo <= 140:
            return 1.0
        elif 128 <= tempo <= 150:
            if tempo < 138:
                return 0.5 + 0.5 * (tempo - 128) / 10
            else:
                return 0.5 + 0.5 * (150 - tempo) / 10
        elif 120 <= tempo <= 160:
            # Still plausible but not typical
            return 0.3
        else:
            return 0.1

    def _modulation_to_score(self, modulation_db: float) -> float:
        """
        Convert sidechain modulation depth to score.

        Typical trance: 4-8 dB
        Light: 2-4 dB
        Heavy: 8-12 dB
        """
        if 4 <= modulation_db <= 8:
            return 0.8 + 0.2 * (1 - abs(modulation_db - 6) / 2)
        elif modulation_db < 4:
            return np.clip(modulation_db / 4 * 0.7, 0.0, 0.7)
        else:  # > 8
            return np.clip(0.8 - (modulation_db - 8) / 8, 0.3, 0.8)

    def _centroid_to_score(self, centroid: float, sample_rate: int) -> float:
        """
        Convert spectral centroid to brightness score.

        Trance is typically bright: 2000-4000 Hz centroid is good.
        """
        # Normalize by Nyquist
        nyquist = sample_rate / 2
        normalized = centroid / nyquist

        # Optimal brightness range
        if 0.1 <= normalized <= 0.25:  # ~2000-5500 Hz at 44.1kHz
            return 1.0
        elif normalized < 0.1:
            return normalized / 0.1
        else:
            return max(0.3, 1.0 - (normalized - 0.25) / 0.25)

    def format_score_report(
        self,
        total_score: float,
        breakdown: TranceScoreBreakdown
    ) -> str:
        """
        Format score as human-readable report.

        Args:
            total_score: Overall trance score
            breakdown: Component breakdown

        Returns:
            Formatted string report
        """
        def bar(score: float, width: int = 10) -> str:
            filled = int(score * width)
            return '=' * filled + ' ' * (width - filled)

        lines = [
            f"Trance Score: {total_score:.2f} / 1.00",
            "",
            "Component Breakdown:"
        ]

        components = [
            ('Tempo', breakdown.tempo_score, self.weights['tempo_score']),
            ('Sidechain Pumping', breakdown.pumping_score, self.weights['pumping_score']),
            ('Energy Progression', breakdown.energy_progression, self.weights['energy_progression']),
            ('4-on-the-Floor', breakdown.four_on_floor, self.weights['four_on_floor']),
            ('Supersaw Spread', breakdown.supersaw_score, self.weights['supersaw_score']),
            ('303 Acid Elements', breakdown.acid_303_score, self.weights['acid_303_score']),
            ('Off-beat Hi-hats', breakdown.offbeat_hihat, self.weights['offbeat_hihat']),
            ('Spectral Brightness', breakdown.spectral_brightness, self.weights['spectral_brightness']),
            ('Tempo Stability', breakdown.tempo_stability, self.weights['tempo_stability'])
        ]

        for name, score, weight in components:
            weighted = score * weight
            lines.append(
                f"  {name:20} {score:.2f}  [{bar(score)}] (w={weight:.2f}, contrib={weighted:.3f})"
            )

        return '\n'.join(lines)

    def get_improvement_suggestions(
        self,
        breakdown: TranceScoreBreakdown,
        threshold: float = 0.5
    ) -> list:
        """
        Get suggestions for improving trance score.

        Args:
            breakdown: Score breakdown
            threshold: Score below which suggestions are made

        Returns:
            List of suggestion strings
        """
        suggestions = []

        if breakdown.tempo_score < threshold:
            suggestions.append(
                "Tempo: Consider adjusting to 138-140 BPM (typical trance tempo)"
            )

        if breakdown.pumping_score < threshold:
            suggestions.append(
                "Sidechain: Add sidechain compression to create pumping effect (4-8 dB modulation)"
            )

        if breakdown.energy_progression < threshold:
            suggestions.append(
                "Energy: Add breakdown/buildup sections with dynamic contrast"
            )

        if breakdown.four_on_floor < threshold:
            suggestions.append(
                "Kicks: Strengthen the 4-on-the-floor kick pattern"
            )

        if breakdown.supersaw_score < threshold:
            suggestions.append(
                "Stereo: Add supersaw-style pads with unison detuning for wider sound"
            )

        if breakdown.offbeat_hihat < threshold:
            suggestions.append(
                "Hi-hats: Add off-beat hi-hats to drive the groove"
            )

        if breakdown.spectral_brightness < threshold:
            suggestions.append(
                "Brightness: Trance typically has bright, energetic highs - check EQ"
            )

        if breakdown.tempo_stability < threshold:
            suggestions.append(
                "Stability: Ensure consistent tempo throughout (avoid tempo drift)"
            )

        return suggestions
