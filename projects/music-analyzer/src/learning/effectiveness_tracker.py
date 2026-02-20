"""
Effectiveness Tracker Module.

Track whether applied fixes actually improved the mix by comparing
before/after analysis results.
"""

import sys
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass

from .learning_db import LearningDatabase, FixFeedback

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class FeatureEffectivenessStats:
    """Statistics on fix effectiveness for a single feature."""
    feature: str
    times_suggested: int
    times_accepted: int
    acceptance_rate: float
    avg_improvement: float
    improvement_std: float
    effective_count: int  # How many actually improved
    ineffective_count: int  # How many made it worse or no change
    confidence_adjustment: float  # Recommended adjustment to confidence

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            'feature': self.feature,
            'times_suggested': self.times_suggested,
            'times_accepted': self.times_accepted,
            'acceptance_rate': self.acceptance_rate,
            'avg_improvement': self.avg_improvement,
            'improvement_std': self.improvement_std,
            'effective_count': self.effective_count,
            'ineffective_count': self.ineffective_count,
            'confidence_adjustment': self.confidence_adjustment
        }


@dataclass
class EffectivenessReport:
    """Report on fix effectiveness across all features."""
    report_date: str
    total_sessions: int
    total_fixes_suggested: int
    total_fixes_accepted: int
    overall_acceptance_rate: float
    overall_avg_improvement: float

    feature_stats: Dict[str, FeatureEffectivenessStats]

    most_effective_features: List[str]
    least_effective_features: List[str]
    ineffective_fixes: List[str]  # Features that rarely help

    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            'report_date': self.report_date,
            'total_sessions': self.total_sessions,
            'total_fixes_suggested': self.total_fixes_suggested,
            'total_fixes_accepted': self.total_fixes_accepted,
            'overall_acceptance_rate': self.overall_acceptance_rate,
            'overall_avg_improvement': self.overall_avg_improvement,
            'feature_stats': {k: v.to_dict() for k, v in self.feature_stats.items()},
            'most_effective_features': self.most_effective_features,
            'least_effective_features': self.least_effective_features,
            'ineffective_fixes': self.ineffective_fixes,
            'recommendations': self.recommendations
        }


class EffectivenessTracker:
    """
    Track fix effectiveness over time.

    Analyzes feedback data to determine which fix types are most
    effective and adjusts confidence scores accordingly.
    """

    def __init__(
        self,
        db: Optional[LearningDatabase] = None,
        db_path: str = "learning_data.db",
        verbose: bool = False
    ):
        """
        Initialize effectiveness tracker.

        Args:
            db: LearningDatabase instance (creates one if not provided)
            db_path: Path to database file if creating new instance
            verbose: Print verbose output
        """
        self.db = db or LearningDatabase(db_path)
        self.verbose = verbose

        # Thresholds for effectiveness classification
        self.high_acceptance_threshold = 0.7
        self.low_acceptance_threshold = 0.3
        self.effective_improvement_threshold = 0.05
        self.min_samples_for_confidence = 5

    def compute_before_after(
        self,
        track_path: str,
        profile: Any,
        applied_fix_ids: List[str]
    ) -> Dict[str, float]:
        """
        Re-analyze track and compute improvement.

        This should be called after fixes are applied to measure
        their actual effectiveness.

        Args:
            track_path: Path to the (modified) audio file
            profile: ReferenceProfile to compare against
            applied_fix_ids: List of fix IDs that were applied

        Returns:
            Dict with improvement metrics
        """
        try:
            from analysis import GapAnalyzer
            from feature_extraction import extract_all_trance_features
        except ImportError as e:
            if self.verbose:
                print(f"Warning: Could not import analysis modules: {e}")
            return {}

        # Re-analyze the track
        analyzer = GapAnalyzer(profile)
        new_report = analyzer.analyze(track_path)

        # Get the original session data for comparison
        feedback_records = self.db.get_all_feedback(limit=100)
        session_feedback = [f for f in feedback_records if f.feedback_id in applied_fix_ids]

        if not session_feedback:
            if self.verbose:
                print("Warning: No feedback records found for applied fixes")
            return {
                'similarity': new_report.overall_similarity,
                'trance_score': new_report.trance_score
            }

        # Compute per-feature changes
        feature_changes = {}
        for gap in new_report.all_gaps:
            # Find if we had a fix for this feature
            matching_feedback = [f for f in session_feedback if f.feature == gap.feature_name]
            if matching_feedback:
                original_feedback = matching_feedback[0]
                # Compute improvement (closer to target is better)
                original_delta = abs(original_feedback.current_value - original_feedback.target_value)
                new_delta = abs(gap.wip_value - gap.target_value)
                improvement = original_delta - new_delta  # Positive = better
                feature_changes[gap.feature_name] = improvement

                # Update feedback record with effectiveness data
                self.db.update_feedback_effectiveness(
                    original_feedback.feedback_id,
                    pre_score=abs(gap.z_score),  # Using z-score as gap measure
                    post_score=abs(gap.z_score)  # Will be compared
                )

        result = {
            'similarity': new_report.overall_similarity,
            'trance_score': new_report.trance_score,
            'feature_changes': feature_changes
        }

        if self.verbose:
            print(f"[EffectivenessTracker] Re-analysis complete")
            print(f"  Similarity: {new_report.overall_similarity:.0%}")
            print(f"  Trance Score: {new_report.trance_score:.2f}")
            if feature_changes:
                print(f"  Feature changes: {len(feature_changes)}")

        return result

    def get_feature_effectiveness_report(self) -> EffectivenessReport:
        """
        Get comprehensive effectiveness stats for all features.

        Returns:
            EffectivenessReport with detailed statistics
        """
        import numpy as np

        # Get all feature stats from database
        feature_stats_raw = self.db.get_feature_stats()
        sessions = self.db.get_all_sessions(limit=1000)
        summary = self.db.get_summary_stats()

        feature_stats = {}
        all_feedback = self.db.get_all_feedback(limit=10000)

        for feature, raw_stats in feature_stats_raw.items():
            # Get improvement values for this feature
            feature_feedback = [f for f in all_feedback if f.feature == feature and f.improvement is not None]
            improvements = [f.improvement for f in feature_feedback if f.accepted]

            avg_improvement = np.mean(improvements) if improvements else 0.0
            improvement_std = np.std(improvements) if len(improvements) > 1 else 0.0

            # Count effective vs ineffective
            effective_count = sum(1 for imp in improvements if imp > self.effective_improvement_threshold)
            ineffective_count = len(improvements) - effective_count

            # Compute confidence adjustment
            confidence_adj = self._compute_confidence_adjustment(
                acceptance_rate=raw_stats['acceptance_rate'],
                avg_improvement=avg_improvement,
                sample_count=raw_stats['suggested']
            )

            feature_stats[feature] = FeatureEffectivenessStats(
                feature=feature,
                times_suggested=raw_stats['suggested'],
                times_accepted=raw_stats['accepted'],
                acceptance_rate=raw_stats['acceptance_rate'],
                avg_improvement=avg_improvement,
                improvement_std=improvement_std,
                effective_count=effective_count,
                ineffective_count=ineffective_count,
                confidence_adjustment=confidence_adj
            )

        # Identify most/least effective features
        sorted_by_effectiveness = sorted(
            feature_stats.values(),
            key=lambda x: (x.acceptance_rate * 0.5 + x.avg_improvement * 0.5) if x.times_suggested >= self.min_samples_for_confidence else -1,
            reverse=True
        )

        most_effective = [fs.feature for fs in sorted_by_effectiveness[:5] if fs.times_suggested >= self.min_samples_for_confidence]
        least_effective = [fs.feature for fs in sorted_by_effectiveness[-5:] if fs.times_suggested >= self.min_samples_for_confidence]

        # Identify ineffective fixes (low acceptance AND low improvement)
        ineffective = [
            fs.feature for fs in feature_stats.values()
            if fs.acceptance_rate < self.low_acceptance_threshold
            and fs.avg_improvement < self.effective_improvement_threshold
            and fs.times_suggested >= self.min_samples_for_confidence
        ]

        # Generate recommendations
        recommendations = self._generate_recommendations(feature_stats, most_effective, ineffective)

        return EffectivenessReport(
            report_date=datetime.now().isoformat(),
            total_sessions=len(sessions),
            total_fixes_suggested=summary.get('total_feedback', 0),
            total_fixes_accepted=summary.get('total_accepted', 0),
            overall_acceptance_rate=summary.get('overall_acceptance_rate', 0.0),
            overall_avg_improvement=summary.get('avg_fix_improvement') or 0.0,
            feature_stats=feature_stats,
            most_effective_features=most_effective,
            least_effective_features=least_effective,
            ineffective_fixes=ineffective,
            recommendations=recommendations
        )

    def _compute_confidence_adjustment(
        self,
        acceptance_rate: float,
        avg_improvement: float,
        sample_count: int
    ) -> float:
        """
        Compute recommended confidence adjustment for a feature.

        High acceptance + high improvement = boost confidence
        Low acceptance + low improvement = reduce confidence

        Args:
            acceptance_rate: Rate of fix acceptance (0-1)
            avg_improvement: Average improvement when applied
            sample_count: Number of samples

        Returns:
            Multiplier for confidence (1.0 = no change)
        """
        if sample_count < self.min_samples_for_confidence:
            return 1.0  # Not enough data

        # Base adjustment from acceptance rate
        # Scale from 0.7 (30% acceptance) to 1.3 (90% acceptance)
        acceptance_factor = 0.7 + (acceptance_rate * 0.6)

        # Improvement factor
        # Scale based on average improvement
        if avg_improvement > 0.15:
            improvement_factor = 1.2
        elif avg_improvement > 0.05:
            improvement_factor = 1.1
        elif avg_improvement > 0:
            improvement_factor = 1.0
        elif avg_improvement > -0.05:
            improvement_factor = 0.95
        else:
            improvement_factor = 0.8

        # Combined adjustment
        adjustment = acceptance_factor * improvement_factor

        # Clamp to reasonable range
        return max(0.5, min(1.5, adjustment))

    def _generate_recommendations(
        self,
        feature_stats: Dict[str, FeatureEffectivenessStats],
        most_effective: List[str],
        ineffective: List[str]
    ) -> List[str]:
        """Generate actionable recommendations based on effectiveness data."""
        recommendations = []

        # Boost confidence for highly effective features
        for feature in most_effective[:3]:
            if feature in feature_stats:
                stats = feature_stats[feature]
                if stats.acceptance_rate > self.high_acceptance_threshold and stats.avg_improvement > self.effective_improvement_threshold:
                    recommendations.append(
                        f"BOOST confidence for '{feature}' (high acceptance {stats.acceptance_rate:.0%} + improvement {stats.avg_improvement:+.2f})"
                    )

        # Reduce confidence for ineffective features
        for feature in ineffective:
            stats = feature_stats[feature]
            recommendations.append(
                f"REDUCE confidence for '{feature}' (low acceptance {stats.acceptance_rate:.0%})"
            )

        # Suggest removing consistently ineffective fixes
        for feature, stats in feature_stats.items():
            if (stats.times_suggested >= 10 and
                stats.acceptance_rate < 0.2 and
                stats.avg_improvement < 0.02):
                recommendations.append(
                    f"Consider REMOVING '{feature}' fixes (rarely accepted, minimal improvement)"
                )

        # Highlight features that need more data
        low_sample_features = [
            f for f, s in feature_stats.items()
            if s.times_suggested < self.min_samples_for_confidence
        ]
        if low_sample_features:
            recommendations.append(
                f"Need more data for: {', '.join(low_sample_features[:5])}"
            )

        return recommendations

    def identify_ineffective_fixes(self) -> List[str]:
        """
        Find fix types that rarely help.

        Returns:
            List of feature names with ineffective fixes
        """
        report = self.get_feature_effectiveness_report()
        return report.ineffective_fixes

    def get_confidence_adjustments(self) -> Dict[str, float]:
        """
        Get recommended confidence adjustments for all features.

        Returns:
            Dict mapping feature name to confidence multiplier
        """
        report = self.get_feature_effectiveness_report()
        return {
            feature: stats.confidence_adjustment
            for feature, stats in report.feature_stats.items()
        }

    def save_learned_weights(self):
        """
        Save computed confidence adjustments to the database.

        This persists the learned weights so they can be applied
        to future fix generation.
        """
        report = self.get_feature_effectiveness_report()

        for feature, stats in report.feature_stats.items():
            self.db.save_feature_weight(
                feature=feature,
                confidence_adjustment=stats.confidence_adjustment,
                priority_adjustment=1.0,  # Could compute this too
                sample_count=stats.times_suggested
            )

        if self.verbose:
            print(f"[EffectivenessTracker] Saved weights for {len(report.feature_stats)} features")


def format_effectiveness_report(report: EffectivenessReport) -> str:
    """
    Format an effectiveness report as a human-readable string.

    Args:
        report: EffectivenessReport to format

    Returns:
        Formatted report string
    """
    lines = [
        "",
        "=" * 60,
        "LEARNING STATISTICS",
        "=" * 60,
        f"Sessions: {report.total_sessions}",
        f"Total fixes suggested: {report.total_fixes_suggested}",
        f"Total fixes accepted: {report.total_fixes_accepted} ({report.overall_acceptance_rate:.0%})",
        "",
        "Per-Feature Breakdown:",
        f"{'Feature':<35} {'Suggested':>10} {'Accepted':>10} {'Rate':>8} {'Avg Improve':>12}",
        "-" * 80
    ]

    # Sort by times suggested
    sorted_features = sorted(
        report.feature_stats.items(),
        key=lambda x: x[1].times_suggested,
        reverse=True
    )

    for feature, stats in sorted_features:
        lines.append(
            f"  {feature:<33} {stats.times_suggested:>10} {stats.times_accepted:>10} "
            f"{stats.acceptance_rate:>7.0%} {stats.avg_improvement:>+11.2f}"
        )

    lines.extend([
        "",
        "Recommendations:"
    ])

    for rec in report.recommendations:
        lines.append(f"  - {rec}")

    if report.most_effective_features:
        lines.extend([
            "",
            f"Most effective features: {', '.join(report.most_effective_features)}"
        ])

    if report.ineffective_fixes:
        lines.extend([
            f"Ineffective fixes to review: {', '.join(report.ineffective_fixes)}"
        ])

    lines.append("=" * 60)

    return "\n".join(lines)
