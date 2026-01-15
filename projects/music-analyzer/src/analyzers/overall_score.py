"""
Overall Score Calculator

Calculates a weighted overall quality score based on all analysis components.
Provides a single 0-100 metric for quick assessment of mix quality.

Based on ai-music-mix-analyzer implementation, adapted for AbletonAIAnalysis.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class OverallScoreInfo:
    """Overall score calculation results."""
    overall_score: float                        # 0-100 weighted score
    component_scores: Dict[str, float]          # Individual component scores
    component_weights: Dict[str, float]         # Weights used for each component
    grade: str                                  # Letter grade (A, B, C, D, F)
    grade_description: str                      # Description of the grade
    weakest_component: str                      # Component dragging score down
    strongest_component: str                    # Best performing component
    summary: str                                # Overall summary text


class OverallScoreCalculator:
    """
    Calculates weighted overall quality score from analysis results.

    Combines scores from:
    - Frequency balance
    - Dynamics
    - Stereo/phase
    - Loudness
    - Clarity (if available)
    - Harmonic content (if available)
    - Transients
    - Surround compatibility (if available)
    """

    # Default weights for each component (must sum to ~1.0)
    DEFAULT_WEIGHTS = {
        'frequency_balance': 0.20,
        'dynamics': 0.15,
        'stereo': 0.15,
        'loudness': 0.10,
        'clarity': 0.15,
        'harmonic': 0.10,
        'transients': 0.10,
        'surround': 0.05,
    }

    # Grade thresholds
    GRADE_THRESHOLDS = {
        'A': (85, 100, "Release ready - professional quality mix"),
        'B': (70, 84, "Good mix with minor areas for improvement"),
        'C': (55, 69, "Decent mix but several issues to address"),
        'D': (40, 54, "Mix needs significant work"),
        'F': (0, 39, "Major problems - fundamental issues present"),
    }

    def __init__(self, config=None):
        """
        Initialize the score calculator.

        Args:
            config: Optional configuration object with weight overrides
        """
        self.config = config

        # Load weights from config or use defaults
        if config and hasattr(config, 'overall_score'):
            score_cfg = config.overall_score
            weights_cfg = score_cfg.get('weights', {})
            self.weights = {
                'frequency_balance': weights_cfg.get('frequency_balance', 0.20),
                'dynamics': weights_cfg.get('dynamics', 0.15),
                'stereo': weights_cfg.get('stereo', 0.15),
                'loudness': weights_cfg.get('loudness', 0.10),
                'clarity': weights_cfg.get('clarity', 0.15),
                'harmonic': weights_cfg.get('harmonic', 0.10),
                'transients': weights_cfg.get('transients', 0.10),
                'surround': weights_cfg.get('surround', 0.05),
            }
        else:
            self.weights = self.DEFAULT_WEIGHTS.copy()

    def calculate(self, results: Any) -> OverallScoreInfo:
        """
        Calculate overall score from analysis results.

        Args:
            results: AnalysisResult object or dict with analysis data

        Returns:
            OverallScoreInfo with overall score and breakdown
        """
        component_scores = {}
        available_weights = {}

        # Extract scores from each component
        # Frequency balance score
        freq_score = self._get_frequency_score(results)
        if freq_score is not None:
            component_scores['frequency_balance'] = freq_score
            available_weights['frequency_balance'] = self.weights['frequency_balance']

        # Dynamics score
        dynamics_score = self._get_dynamics_score(results)
        if dynamics_score is not None:
            component_scores['dynamics'] = dynamics_score
            available_weights['dynamics'] = self.weights['dynamics']

        # Stereo score
        stereo_score = self._get_stereo_score(results)
        if stereo_score is not None:
            component_scores['stereo'] = stereo_score
            available_weights['stereo'] = self.weights['stereo']

        # Loudness score
        loudness_score = self._get_loudness_score(results)
        if loudness_score is not None:
            component_scores['loudness'] = loudness_score
            available_weights['loudness'] = self.weights['loudness']

        # Clarity score (if available)
        clarity_score = self._get_clarity_score(results)
        if clarity_score is not None:
            component_scores['clarity'] = clarity_score
            available_weights['clarity'] = self.weights['clarity']

        # Harmonic score (if available)
        harmonic_score = self._get_harmonic_score(results)
        if harmonic_score is not None:
            component_scores['harmonic'] = harmonic_score
            available_weights['harmonic'] = self.weights['harmonic']

        # Transients score
        transients_score = self._get_transients_score(results)
        if transients_score is not None:
            component_scores['transients'] = transients_score
            available_weights['transients'] = self.weights['transients']

        # Surround score (if available)
        surround_score = self._get_surround_score(results)
        if surround_score is not None:
            component_scores['surround'] = surround_score
            available_weights['surround'] = self.weights['surround']

        # Calculate weighted average
        if not component_scores:
            return self._create_default_result("No analysis data available")

        # Normalize weights to sum to 1.0
        total_weight = sum(available_weights.values())
        normalized_weights = {k: v / total_weight for k, v in available_weights.items()}

        # Calculate overall score
        overall_score = sum(
            component_scores[k] * normalized_weights[k]
            for k in component_scores
        )

        # Ensure score is in valid range
        overall_score = max(0, min(100, overall_score))

        # Determine grade
        grade, grade_description = self._get_grade(overall_score)

        # Find weakest and strongest components
        weakest = min(component_scores, key=component_scores.get)
        strongest = max(component_scores, key=component_scores.get)

        # Generate summary
        summary = self._generate_summary(
            overall_score, grade, component_scores, weakest, strongest
        )

        return OverallScoreInfo(
            overall_score=overall_score,
            component_scores=component_scores,
            component_weights=normalized_weights,
            grade=grade,
            grade_description=grade_description,
            weakest_component=weakest,
            strongest_component=strongest,
            summary=summary
        )

    def _get_frequency_score(self, results: Any) -> Optional[float]:
        """Extract frequency balance score from results."""
        try:
            freq = self._get_attr(results, 'frequency')
            if freq is None:
                return None

            # Calculate score based on balance issues and spectral centroid
            issues_count = len(self._get_attr(freq, 'balance_issues', []))
            centroid = self._get_attr(freq, 'spectral_centroid_hz', 2500)

            # Start with base score
            score = 90

            # Penalty for balance issues
            score -= issues_count * 15

            # Centroid penalty (ideal: 1500-3500 Hz)
            if centroid < 1000:
                score -= (1000 - centroid) / 50
            elif centroid > 4000:
                score -= (centroid - 4000) / 100

            return max(0, min(100, score))

        except Exception:
            return None

    def _get_dynamics_score(self, results: Any) -> Optional[float]:
        """Extract dynamics score from results."""
        try:
            dynamics = self._get_attr(results, 'dynamics')
            if dynamics is None:
                return None

            crest_factor = self._get_attr(dynamics, 'crest_factor_db', 10)
            is_over_compressed = self._get_attr(dynamics, 'is_over_compressed', False)

            # Score based on crest factor
            # Ideal range: 8-18 dB
            if crest_factor >= 12 and crest_factor <= 18:
                score = 90 + (crest_factor - 12) / 6 * 10
            elif crest_factor >= 8:
                score = 70 + (crest_factor - 8) / 4 * 20
            elif crest_factor >= 4:
                score = 40 + (crest_factor - 4) / 4 * 30
            else:
                score = crest_factor * 10

            if is_over_compressed:
                score = min(score, 60)

            return max(0, min(100, score))

        except Exception:
            return None

    def _get_stereo_score(self, results: Any) -> Optional[float]:
        """Extract stereo/phase score from results."""
        try:
            stereo = self._get_attr(results, 'stereo')
            if stereo is None:
                return None

            correlation = self._get_attr(stereo, 'correlation', 0.5)
            is_mono_compatible = self._get_attr(stereo, 'is_mono_compatible', True)
            phase_safe = self._get_attr(stereo, 'phase_safe', True)

            # Critical: negative correlation
            if correlation < 0:
                return max(0, (correlation + 1) * 30)

            # Score based on correlation
            # Ideal: 0.3-0.7
            if 0.3 <= correlation <= 0.7:
                score = 85 + (0.5 - abs(correlation - 0.5)) / 0.2 * 15
            elif correlation > 0.7:
                score = 70 - (correlation - 0.7) / 0.3 * 20  # Too mono
            else:
                score = 70 - (0.3 - correlation) / 0.3 * 30  # Too wide

            if not is_mono_compatible:
                score = min(score, 60)

            if not phase_safe:
                score = min(score, 40)

            return max(0, min(100, score))

        except Exception:
            return None

    def _get_loudness_score(self, results: Any) -> Optional[float]:
        """Extract loudness score from results."""
        try:
            loudness = self._get_attr(results, 'loudness')
            if loudness is None:
                return None

            lufs = self._get_attr(loudness, 'integrated_lufs', -14)
            true_peak = self._get_attr(loudness, 'true_peak_db', -1)

            # Score based on LUFS (target: -14 LUFS for streaming)
            lufs_diff = abs(lufs - (-14))
            if lufs_diff <= 2:
                score = 95
            elif lufs_diff <= 4:
                score = 85
            elif lufs_diff <= 6:
                score = 70
            else:
                score = max(40, 70 - (lufs_diff - 6) * 5)

            # True peak penalty
            if true_peak > -0.5:
                score -= 20
            elif true_peak > -1.0:
                score -= 10

            return max(0, min(100, score))

        except Exception:
            return None

    def _get_clarity_score(self, results: Any) -> Optional[float]:
        """Extract clarity score from results."""
        try:
            clarity = self._get_attr(results, 'clarity')
            if clarity is None:
                return None

            return self._get_attr(clarity, 'clarity_score', None)

        except Exception:
            return None

    def _get_harmonic_score(self, results: Any) -> Optional[float]:
        """Extract harmonic score from results."""
        try:
            harmonic = self._get_attr(results, 'harmonic')
            if harmonic is None:
                return None

            key_confidence = self._get_attr(harmonic, 'key_confidence', 0)
            key_consistency = self._get_attr(harmonic, 'key_consistency', 0)
            complexity = self._get_attr(harmonic, 'harmonic_complexity', 50)

            # Score based on confidence and consistency
            confidence_score = key_confidence * 100
            consistency_score = key_consistency

            # Complexity in moderate range is good
            if 30 <= complexity <= 70:
                complexity_score = 80 + (50 - abs(complexity - 50)) / 50 * 20
            else:
                complexity_score = 60

            score = (confidence_score * 0.3 +
                     consistency_score * 0.4 +
                     complexity_score * 0.3)

            return max(0, min(100, score))

        except Exception:
            return None

    def _get_transients_score(self, results: Any) -> Optional[float]:
        """Extract transients score from results."""
        try:
            transients = self._get_attr(results, 'transients')
            if transients is None:
                return None

            avg_strength = self._get_attr(transients, 'avg_transient_strength', 0.5)
            attack_quality = self._get_attr(transients, 'attack_quality', 'average')

            # Score based on attack quality
            quality_scores = {
                'punchy': 95,
                'average': 75,
                'soft': 55,
                'unknown': 60
            }

            base_score = quality_scores.get(attack_quality, 60)

            # Adjust based on strength
            strength_adjustment = (avg_strength - 0.5) * 20

            return max(0, min(100, base_score + strength_adjustment))

        except Exception:
            return None

    def _get_surround_score(self, results: Any) -> Optional[float]:
        """Extract surround compatibility score from results."""
        try:
            surround = self._get_attr(results, 'surround')
            if surround is None:
                return None

            mono_compat = self._get_attr(surround, 'mono_compatibility', 80)
            phase_score = self._get_attr(surround, 'phase_score', 80)

            return (mono_compat + phase_score) / 2

        except Exception:
            return None

    def _get_attr(self, obj: Any, attr: str, default: Any = None) -> Any:
        """Get attribute from object or dict."""
        if obj is None:
            return default

        if isinstance(obj, dict):
            return obj.get(attr, default)
        elif hasattr(obj, attr):
            return getattr(obj, attr, default)
        else:
            return default

    def _get_grade(self, score: float) -> tuple:
        """Determine letter grade from score."""
        for grade, (low, high, description) in self.GRADE_THRESHOLDS.items():
            if low <= score <= high:
                return (grade, description)
        return ('F', "Score out of expected range")

    def _generate_summary(
        self,
        score: float,
        grade: str,
        components: Dict[str, float],
        weakest: str,
        strongest: str
    ) -> str:
        """Generate summary text for the overall score."""
        summaries = {
            'A': f"Excellent mix quality ({score:.0f}/100). {strongest.replace('_', ' ').title()} is particularly strong.",
            'B': f"Good mix ({score:.0f}/100). Focus on improving {weakest.replace('_', ' ')} for professional release.",
            'C': f"Mix needs work ({score:.0f}/100). Priority: address {weakest.replace('_', ' ')} issues.",
            'D': f"Significant issues ({score:.0f}/100). Start with {weakest.replace('_', ' ')} before other refinements.",
            'F': f"Major problems detected ({score:.0f}/100). Critical: fix {weakest.replace('_', ' ')} issues immediately.",
        }

        return summaries.get(grade, f"Overall score: {score:.0f}/100")

    def _create_default_result(self, message: str) -> OverallScoreInfo:
        """Create default result for error cases."""
        return OverallScoreInfo(
            overall_score=0.0,
            component_scores={},
            component_weights={},
            grade='F',
            grade_description=message,
            weakest_component='unknown',
            strongest_component='unknown',
            summary=message
        )
