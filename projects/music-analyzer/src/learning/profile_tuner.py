"""
Profile Tuner Module.

Adjust profile weights and ranges based on learned user preferences
and fix effectiveness data.
"""

import sys
import json
import copy
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass

from .learning_db import LearningDatabase
from .effectiveness_tracker import EffectivenessTracker

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class TuningRecommendation:
    """A specific tuning recommendation for a feature."""
    feature: str
    recommendation_type: str  # 'confidence', 'range', 'weight', 'remove'
    current_value: Any
    suggested_value: Any
    reason: str
    confidence: float  # How confident we are in this recommendation

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            'feature': self.feature,
            'recommendation_type': self.recommendation_type,
            'current_value': self.current_value,
            'suggested_value': self.suggested_value,
            'reason': self.reason,
            'confidence': self.confidence
        }


@dataclass
class TuningReport:
    """Report of all tuning recommendations."""
    report_date: str
    profile_name: str
    sample_count: int
    recommendations: List[TuningRecommendation]
    weight_adjustments: Dict[str, float]
    confidence_adjustments: Dict[str, float]
    range_adjustments: Dict[str, Tuple[float, float]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            'report_date': self.report_date,
            'profile_name': self.profile_name,
            'sample_count': self.sample_count,
            'recommendations': [r.to_dict() for r in self.recommendations],
            'weight_adjustments': self.weight_adjustments,
            'confidence_adjustments': self.confidence_adjustments,
            'range_adjustments': {k: list(v) for k, v in self.range_adjustments.items()}
        }


class ProfileTuner:
    """
    Tune profile based on user feedback.

    Adjusts feature weights, confidence scores, and acceptable ranges
    based on historical user decisions and fix effectiveness.
    """

    def __init__(
        self,
        db: Optional[LearningDatabase] = None,
        db_path: str = "learning_data.db",
        verbose: bool = False
    ):
        """
        Initialize profile tuner.

        Args:
            db: LearningDatabase instance (creates one if not provided)
            db_path: Path to database file if creating new instance
            verbose: Print verbose output
        """
        self.db = db or LearningDatabase(db_path)
        self.tracker = EffectivenessTracker(db=self.db, verbose=verbose)
        self.verbose = verbose

        # Tuning parameters
        self.min_samples = 5
        self.high_acceptance_threshold = 0.7
        self.low_acceptance_threshold = 0.3
        self.range_expansion_threshold = 0.6  # Expand range if many accepted outside it

    def compute_weight_adjustments(self) -> Dict[str, float]:
        """
        Compute adjusted weights based on acceptance rates.

        Features with high acceptance get boosted.
        Features with low acceptance get reduced.

        Returns:
            Dict mapping feature name to weight multiplier
        """
        feature_stats = self.db.get_feature_stats()
        adjustments = {}

        for feature, stats in feature_stats.items():
            if stats['suggested'] < self.min_samples:
                adjustments[feature] = 1.0  # Not enough data
                continue

            acceptance_rate = stats['acceptance_rate']

            # Scale weight based on acceptance
            # High acceptance = boost weight (more important to fix)
            # Low acceptance = reduce weight (less important to users)
            if acceptance_rate >= self.high_acceptance_threshold:
                # Boost: 1.0 to 1.3 based on how far above threshold
                boost = 1.0 + (acceptance_rate - self.high_acceptance_threshold) * 0.5
                adjustments[feature] = min(1.3, boost)
            elif acceptance_rate <= self.low_acceptance_threshold:
                # Reduce: 0.7 to 1.0 based on how far below threshold
                reduction = 1.0 - (self.low_acceptance_threshold - acceptance_rate) * 0.5
                adjustments[feature] = max(0.7, reduction)
            else:
                adjustments[feature] = 1.0

        if self.verbose:
            print(f"[ProfileTuner] Computed weight adjustments for {len(adjustments)} features")
            boosted = [f for f, w in adjustments.items() if w > 1.05]
            reduced = [f for f, w in adjustments.items() if w < 0.95]
            if boosted:
                print(f"  Boosted: {', '.join(boosted)}")
            if reduced:
                print(f"  Reduced: {', '.join(reduced)}")

        return adjustments

    def compute_confidence_adjustments(self) -> Dict[str, float]:
        """
        Adjust confidence scores based on effectiveness.

        If a fix type consistently improves scores, boost confidence.
        If it rarely helps, reduce confidence.

        Returns:
            Dict mapping feature name to confidence multiplier
        """
        return self.tracker.get_confidence_adjustments()

    def suggest_profile_updates(self, profile: Any) -> TuningReport:
        """
        Suggest updates to acceptable ranges based on user behavior.

        If users consistently accept fixes outside current range,
        maybe the range should be adjusted.

        Args:
            profile: ReferenceProfile to analyze

        Returns:
            TuningReport with all recommendations
        """
        recommendations = []
        weight_adjustments = self.compute_weight_adjustments()
        confidence_adjustments = self.compute_confidence_adjustments()
        range_adjustments = {}

        feedback = self.db.get_all_feedback(limit=10000)
        feature_stats = self.db.get_feature_stats()
        summary = self.db.get_summary_stats()

        # Analyze each feature
        for feature, stats in feature_stats.items():
            if stats['suggested'] < self.min_samples:
                continue

            # Get feedback for this feature
            feature_feedback = [f for f in feedback if f.feature == feature]
            accepted_feedback = [f for f in feature_feedback if f.accepted]

            # Weight adjustment recommendation
            weight_adj = weight_adjustments.get(feature, 1.0)
            if weight_adj > 1.05:
                recommendations.append(TuningRecommendation(
                    feature=feature,
                    recommendation_type='weight',
                    current_value=1.0,
                    suggested_value=weight_adj,
                    reason=f"High acceptance rate ({stats['acceptance_rate']:.0%})",
                    confidence=min(0.9, stats['suggested'] / 20)  # More samples = higher confidence
                ))
            elif weight_adj < 0.95:
                recommendations.append(TuningRecommendation(
                    feature=feature,
                    recommendation_type='weight',
                    current_value=1.0,
                    suggested_value=weight_adj,
                    reason=f"Low acceptance rate ({stats['acceptance_rate']:.0%})",
                    confidence=min(0.9, stats['suggested'] / 20)
                ))

            # Confidence adjustment recommendation
            conf_adj = confidence_adjustments.get(feature, 1.0)
            if abs(conf_adj - 1.0) > 0.05:
                recommendations.append(TuningRecommendation(
                    feature=feature,
                    recommendation_type='confidence',
                    current_value=1.0,
                    suggested_value=conf_adj,
                    reason=f"Based on fix effectiveness (avg improvement: {stats['avg_improvement']:.2f})",
                    confidence=min(0.9, stats['accepted'] / 10)
                ))

            # Range adjustment recommendation
            if feature in profile.feature_stats and accepted_feedback:
                current_range = profile.feature_stats[feature].acceptable_range

                # Check how many accepted fixes were outside the current range
                outside_range = []
                for fb in accepted_feedback:
                    if fb.current_value < current_range[0] or fb.current_value > current_range[1]:
                        outside_range.append(fb)

                if len(outside_range) / len(accepted_feedback) > self.range_expansion_threshold:
                    # Many accepted fixes were outside range - suggest expanding
                    all_values = [fb.current_value for fb in accepted_feedback]
                    new_min = min(all_values + [current_range[0]])
                    new_max = max(all_values + [current_range[1]])

                    # Don't expand too much
                    range_width = current_range[1] - current_range[0]
                    new_min = max(new_min, current_range[0] - range_width * 0.5)
                    new_max = min(new_max, current_range[1] + range_width * 0.5)

                    if new_min < current_range[0] or new_max > current_range[1]:
                        range_adjustments[feature] = (new_min, new_max)
                        recommendations.append(TuningRecommendation(
                            feature=feature,
                            recommendation_type='range',
                            current_value=list(current_range),
                            suggested_value=[new_min, new_max],
                            reason=f"{len(outside_range)}/{len(accepted_feedback)} accepted fixes were outside current range",
                            confidence=min(0.8, len(accepted_feedback) / 15)
                        ))

            # Check for consistently ineffective features
            if (stats['acceptance_rate'] < 0.2 and
                stats['avg_improvement'] < 0.02 and
                stats['suggested'] >= 10):
                recommendations.append(TuningRecommendation(
                    feature=feature,
                    recommendation_type='remove',
                    current_value=True,
                    suggested_value=False,
                    reason=f"Rarely accepted ({stats['acceptance_rate']:.0%}) and minimal improvement ({stats['avg_improvement']:.2f})",
                    confidence=min(0.85, stats['suggested'] / 20)
                ))

        return TuningReport(
            report_date=datetime.now().isoformat(),
            profile_name=profile.name,
            sample_count=summary.get('total_feedback', 0),
            recommendations=recommendations,
            weight_adjustments=weight_adjustments,
            confidence_adjustments=confidence_adjustments,
            range_adjustments=range_adjustments
        )

    def apply_tuning(
        self,
        profile: Any,
        apply_weights: bool = True,
        apply_confidence: bool = True,
        apply_ranges: bool = False  # More conservative by default
    ) -> Any:
        """
        Apply learned adjustments to profile.

        Args:
            profile: ReferenceProfile to tune
            apply_weights: Apply weight adjustments
            apply_confidence: Apply confidence adjustments
            apply_ranges: Apply range adjustments (more aggressive)

        Returns:
            Tuned ReferenceProfile (new instance)
        """
        # Deep copy the profile
        tuned_profile = copy.deepcopy(profile)

        weight_adjustments = self.compute_weight_adjustments() if apply_weights else {}
        confidence_adjustments = self.compute_confidence_adjustments() if apply_confidence else {}

        # Store adjustments in profile metadata
        if not hasattr(tuned_profile, 'learned_adjustments'):
            tuned_profile.learned_adjustments = {}

        tuned_profile.learned_adjustments = {
            'tuning_date': datetime.now().isoformat(),
            'weight_adjustments': weight_adjustments,
            'confidence_adjustments': confidence_adjustments,
            'applied_weights': apply_weights,
            'applied_confidence': apply_confidence,
            'applied_ranges': apply_ranges
        }

        # Apply range adjustments if requested
        if apply_ranges:
            report = self.suggest_profile_updates(profile)
            for feature, new_range in report.range_adjustments.items():
                if feature in tuned_profile.feature_stats:
                    tuned_profile.feature_stats[feature].acceptable_range = tuple(new_range)

        if self.verbose:
            print(f"[ProfileTuner] Applied tuning to profile '{profile.name}'")
            print(f"  Weight adjustments: {len(weight_adjustments)}")
            print(f"  Confidence adjustments: {len(confidence_adjustments)}")
            if apply_ranges:
                print(f"  Range adjustments: {len(report.range_adjustments)}")

        return tuned_profile

    def export_learning_report(self, profile: Any = None) -> str:
        """
        Generate human-readable report of learned adjustments.

        Args:
            profile: Optional profile for context

        Returns:
            Formatted report string
        """
        effectiveness_report = self.tracker.get_feature_effectiveness_report()
        summary = self.db.get_summary_stats()
        weights = self.compute_weight_adjustments()
        confidence = self.compute_confidence_adjustments()

        lines = [
            "",
            "=" * 70,
            "LEARNING REPORT",
            "=" * 70,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "OVERALL STATISTICS",
            "-" * 40,
            f"  Sessions analyzed: {summary.get('session_count', 0)}",
            f"  Total fixes suggested: {summary.get('total_feedback', 0)}",
            f"  Total fixes accepted: {summary.get('total_accepted', 0)} ({summary.get('overall_acceptance_rate', 0):.0%})",
            "",
        ]

        if summary.get('avg_similarity_improvement') is not None:
            lines.append(f"  Avg similarity improvement: {summary['avg_similarity_improvement']:+.0%}")
        if summary.get('avg_trance_score_improvement') is not None:
            lines.append(f"  Avg trance score improvement: {summary['avg_trance_score_improvement']:+.2f}")

        lines.extend([
            "",
            "PER-FEATURE ANALYSIS",
            "-" * 70,
            f"{'Feature':<35} {'Accept %':>10} {'Weight':>8} {'Conf':>8}",
            "-" * 70
        ])

        feature_stats = self.db.get_feature_stats()
        sorted_features = sorted(
            feature_stats.items(),
            key=lambda x: x[1]['suggested'],
            reverse=True
        )

        for feature, stats in sorted_features:
            weight = weights.get(feature, 1.0)
            conf = confidence.get(feature, 1.0)
            weight_str = f"{weight:.2f}" if abs(weight - 1.0) > 0.01 else "-"
            conf_str = f"{conf:.2f}" if abs(conf - 1.0) > 0.01 else "-"

            lines.append(
                f"  {feature:<33} {stats['acceptance_rate']:>9.0%} {weight_str:>8} {conf_str:>8}"
            )

        lines.extend([
            "",
            "RECOMMENDATIONS",
            "-" * 40
        ])

        # Add recommendations
        for rec in effectiveness_report.recommendations:
            lines.append(f"  - {rec}")

        # Features to boost
        boost_features = [f for f, w in weights.items() if w > 1.05]
        if boost_features:
            lines.extend([
                "",
                "  BOOST PRIORITY for:",
                *[f"    + {f}" for f in boost_features[:5]]
            ])

        # Features to reduce
        reduce_features = [f for f, w in weights.items() if w < 0.95]
        if reduce_features:
            lines.extend([
                "",
                "  REDUCE PRIORITY for:",
                *[f"    - {f}" for f in reduce_features[:5]]
            ])

        # Features to potentially remove
        if effectiveness_report.ineffective_fixes:
            lines.extend([
                "",
                "  CONSIDER REMOVING (rarely helpful):",
                *[f"    x {f}" for f in effectiveness_report.ineffective_fixes[:5]]
            ])

        lines.extend([
            "",
            "=" * 70,
            "To apply these learnings to a profile:",
            "  python analyze.py --tune-profile profile.json --output tuned_profile.json",
            "=" * 70
        ])

        return "\n".join(lines)

    def save_tuned_profile(
        self,
        profile: Any,
        output_path: str,
        apply_weights: bool = True,
        apply_confidence: bool = True,
        apply_ranges: bool = False
    ):
        """
        Tune and save a profile to a new file.

        Args:
            profile: Original profile
            output_path: Path to save tuned profile
            apply_weights: Apply weight adjustments
            apply_confidence: Apply confidence adjustments
            apply_ranges: Apply range adjustments
        """
        tuned = self.apply_tuning(
            profile,
            apply_weights=apply_weights,
            apply_confidence=apply_confidence,
            apply_ranges=apply_ranges
        )

        tuned.save(output_path)

        if self.verbose:
            print(f"[ProfileTuner] Saved tuned profile to {output_path}")


def format_tuning_report(report: TuningReport) -> str:
    """
    Format a tuning report as a human-readable string.

    Args:
        report: TuningReport to format

    Returns:
        Formatted string
    """
    lines = [
        "",
        "=" * 60,
        "PROFILE TUNING RECOMMENDATIONS",
        "=" * 60,
        f"Profile: {report.profile_name}",
        f"Based on: {report.sample_count} feedback records",
        f"Date: {report.report_date}",
        "",
        "RECOMMENDATIONS:",
        "-" * 60
    ]

    # Group by type
    by_type = {}
    for rec in report.recommendations:
        if rec.recommendation_type not in by_type:
            by_type[rec.recommendation_type] = []
        by_type[rec.recommendation_type].append(rec)

    type_labels = {
        'weight': 'Weight Adjustments',
        'confidence': 'Confidence Adjustments',
        'range': 'Range Adjustments',
        'remove': 'Consider Removing'
    }

    for rec_type, recs in by_type.items():
        lines.append(f"\n{type_labels.get(rec_type, rec_type)}:")
        for rec in recs:
            if rec.recommendation_type in ('weight', 'confidence'):
                lines.append(
                    f"  {rec.feature}: {rec.current_value:.2f} -> {rec.suggested_value:.2f} "
                    f"({rec.reason})"
                )
            elif rec.recommendation_type == 'range':
                curr = rec.current_value
                sugg = rec.suggested_value
                lines.append(
                    f"  {rec.feature}: [{curr[0]:.2f}, {curr[1]:.2f}] -> "
                    f"[{sugg[0]:.2f}, {sugg[1]:.2f}] ({rec.reason})"
                )
            elif rec.recommendation_type == 'remove':
                lines.append(f"  {rec.feature}: {rec.reason}")

    lines.extend([
        "",
        "=" * 60,
        "To apply:",
        "  python analyze.py --tune-profile <profile> --output <output>",
        "=" * 60
    ])

    return "\n".join(lines)
