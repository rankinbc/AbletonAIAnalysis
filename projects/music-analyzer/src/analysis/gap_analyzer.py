"""
Gap Analyzer Module.

Compare WIP tracks against reference profiles to identify production gaps.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
from pathlib import Path
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from profiling.profile_storage import ReferenceProfile, FeatureStatistics, StyleCluster


@dataclass
class FeatureGap:
    """Gap information for a single feature."""
    feature_name: str
    wip_value: float
    target_value: float  # Profile mean or cluster centroid
    acceptable_range: Tuple[float, float]

    # Computed metrics
    absolute_delta: float  # Raw difference
    z_score: float  # Standard deviations from mean
    percentile: float  # Where WIP falls in reference distribution

    # Classification
    severity: str  # "critical", "warning", "minor", "ok"
    is_outside_range: bool
    direction: str  # "high", "low", "ok"

    # Actionability
    is_fixable: bool = True
    fix_difficulty: str = "medium"  # "easy", "medium", "hard", "manual"

    # Human-readable
    description: str = ""
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            'feature_name': self.feature_name,
            'wip_value': float(self.wip_value),
            'target_value': float(self.target_value),
            'acceptable_range': [float(self.acceptable_range[0]),
                                  float(self.acceptable_range[1])],
            'absolute_delta': float(self.absolute_delta),
            'z_score': float(self.z_score),
            'percentile': float(self.percentile),
            'severity': self.severity,
            'is_outside_range': self.is_outside_range,
            'direction': self.direction,
            'is_fixable': self.is_fixable,
            'fix_difficulty': self.fix_difficulty,
            'description': self.description,
            'recommendation': self.recommendation
        }


@dataclass
class FixRecommendation:
    """A prioritized fix recommendation."""
    priority: int
    feature: str
    severity: str
    action: str
    expected_improvement: str
    difficulty: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'priority': self.priority,
            'feature': self.feature,
            'severity': self.severity,
            'action': self.action,
            'expected_improvement': self.expected_improvement,
            'difficulty': self.difficulty
        }


@dataclass
class GapReport:
    """Complete gap analysis report."""
    wip_path: str
    profile_name: str
    analysis_date: str

    # Overall scores
    overall_similarity: float  # 0-1, how close to references
    trance_score: float  # From TranceScoreCalculator
    nearest_cluster: int
    nearest_cluster_name: str
    cluster_distance: float

    # Detailed gaps
    all_gaps: List[FeatureGap]
    critical_gaps: List[FeatureGap] = field(default_factory=list)
    warning_gaps: List[FeatureGap] = field(default_factory=list)
    minor_gaps: List[FeatureGap] = field(default_factory=list)

    # Summary statistics
    gap_count_by_severity: Dict[str, int] = field(default_factory=dict)
    most_problematic_areas: List[str] = field(default_factory=list)

    # Per-stem analysis (if requested)
    stem_gaps: Dict[str, List[FeatureGap]] = field(default_factory=dict)

    # Recommendations
    prioritized_fixes: List[FixRecommendation] = field(default_factory=list)

    def __post_init__(self):
        """Organize gaps by severity."""
        self.critical_gaps = [g for g in self.all_gaps if g.severity == 'critical']
        self.warning_gaps = [g for g in self.all_gaps if g.severity == 'warning']
        self.minor_gaps = [g for g in self.all_gaps if g.severity == 'minor']

        self.gap_count_by_severity = {
            'critical': len(self.critical_gaps),
            'warning': len(self.warning_gaps),
            'minor': len(self.minor_gaps),
            'ok': len([g for g in self.all_gaps if g.severity == 'ok'])
        }

    def format_summary(self) -> str:
        """Format as summary string."""
        from .delta_reporter import format_summary_report
        return format_summary_report(self)

    def format_detailed(self) -> str:
        """Format as detailed report."""
        from .delta_reporter import format_detailed_report
        return format_detailed_report(self)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            'wip_path': self.wip_path,
            'profile_name': self.profile_name,
            'analysis_date': self.analysis_date,
            'overall_similarity': float(self.overall_similarity),
            'trance_score': float(self.trance_score),
            'nearest_cluster': self.nearest_cluster,
            'nearest_cluster_name': self.nearest_cluster_name,
            'cluster_distance': float(self.cluster_distance),
            'all_gaps': [g.to_dict() for g in self.all_gaps],
            'gap_count_by_severity': self.gap_count_by_severity,
            'most_problematic_areas': self.most_problematic_areas,
            'stem_gaps': {
                k: [g.to_dict() for g in v]
                for k, v in self.stem_gaps.items()
            },
            'prioritized_fixes': [f.to_dict() for f in self.prioritized_fixes]
        }


# Feature importance weights for prioritization
FEATURE_IMPORTANCE = {
    'trance_score': 1.0,
    'pumping_score': 0.9,
    'pumping_modulation_depth_db': 0.9,
    'stereo_width': 0.85,
    'supersaw_score': 0.8,
    'energy_progression': 0.8,
    'four_on_floor_score': 0.75,
    'tempo_score': 0.7,
    'spectral_brightness': 0.7,
    'offbeat_hihat_score': 0.65,
    'acid_303_score': 0.5,  # Optional element
    'tempo_stability': 0.5,
}

# Fix difficulty by feature
FIX_DIFFICULTY = {
    'pumping_modulation_depth_db': 'easy',  # Adjust compressor
    'stereo_width': 'easy',  # Stereo widener plugin
    'spectral_brightness': 'easy',  # EQ
    'energy_progression': 'hard',  # Arrangement change
    'tempo': 'manual',  # Re-record
    'tempo_score': 'manual',
    'four_on_floor_score': 'medium',  # Drum programming
    'offbeat_hihat_score': 'easy',  # Add/adjust hihats
    'pumping_score': 'easy',
    'supersaw_score': 'medium',  # Synth sound design
    'acid_303_score': 'hard',  # Sound design / add 303
}

# Feature-specific recommendations
FEATURE_RECOMMENDATIONS = {
    'pumping_modulation_depth_db': {
        'high': 'Reduce sidechain compression depth - lower ratio or raise threshold',
        'low': 'Increase sidechain compression on bass/pads - lower threshold or raise ratio'
    },
    'stereo_width': {
        'high': 'Reduce stereo width to improve mono compatibility - check mid/side balance',
        'low': 'Add stereo widening to leads/pads using mid-side EQ, chorus, or unison detuning'
    },
    'spectral_brightness': {
        'high': 'Reduce high frequencies with low-pass filter or high shelf cut',
        'low': 'Boost highs with high shelf EQ or add brighter elements (hihats, cymbals)'
    },
    'energy_progression': {
        'high': 'Add more breakdown sections or reduce overall intensity',
        'low': 'Add more contrast between sections - bigger drops, quieter breakdowns'
    },
    'four_on_floor_score': {
        'high': 'Kick pattern is already strong',
        'low': 'Strengthen the 4-on-the-floor kick - check kick volume/compression'
    },
    'offbeat_hihat_score': {
        'high': 'Hihats may be too prominent - reduce level slightly',
        'low': 'Add off-beat hihats or increase their level for more drive'
    },
    'tempo_score': {
        'high': 'Tempo is in trance range',
        'low': 'Consider adjusting tempo closer to 138-140 BPM (typical trance)'
    },
    'pumping_score': {
        'high': 'Sidechain pumping is already strong',
        'low': 'Add or increase sidechain compression for that pumping trance feel'
    },
    'supersaw_score': {
        'high': 'Supersaw/stereo presence is strong',
        'low': 'Add supersaw-style pads or widen existing synths with unison detuning'
    },
    'acid_303_score': {
        'high': 'Strong acid elements detected',
        'low': 'Consider adding acid bass elements if genre-appropriate'
    }
}


class GapAnalyzer:
    """
    Analyze gaps between WIP track and reference profile.

    Usage:
        profile = ReferenceProfile.load("trance_profile.json")
        analyzer = GapAnalyzer(profile)
        report = analyzer.analyze("my_wip.wav")
        print(report.format_summary())
    """

    def __init__(self, profile: ReferenceProfile):
        """
        Initialize analyzer with a reference profile.

        Args:
            profile: ReferenceProfile to compare against
        """
        self.profile = profile

    def analyze(
        self,
        wip_path: str,
        target_cluster: Optional[int] = None,
        include_stems: bool = False,
        detail_level: str = "full"
    ) -> GapReport:
        """
        Analyze WIP track against reference profile.

        Args:
            wip_path: Path to WIP audio file
            target_cluster: Optional cluster ID to compare against
            include_stems: Whether to analyze separated stems
            detail_level: "summary", "standard", or "full"

        Returns:
            Comprehensive gap analysis report
        """
        from feature_extraction import extract_all_trance_features

        # Extract features from WIP
        wip_features = extract_all_trance_features(wip_path)
        wip_dict = wip_features.to_dict()

        # Find nearest cluster
        nearest_cluster_id, cluster_distance = self.find_nearest_cluster(wip_dict)

        if target_cluster is not None and target_cluster < len(self.profile.clusters):
            nearest_cluster_id = target_cluster
            cluster = self.profile.clusters[target_cluster]
            cluster_distance = self._compute_cluster_distance(wip_dict, cluster)

        nearest_cluster = self.profile.get_cluster_by_id(nearest_cluster_id)
        cluster_name = nearest_cluster.name if nearest_cluster else "Unknown"

        # Compute gaps for all features
        all_gaps = []
        for feature_name, stats in self.profile.feature_stats.items():
            if feature_name in wip_dict and wip_dict[feature_name] is not None:
                gap = self.compute_feature_gap(
                    feature_name,
                    float(wip_dict[feature_name]),
                    stats
                )
                all_gaps.append(gap)

        # Prioritize gaps
        all_gaps = self.prioritize_gaps(all_gaps)

        # Calculate overall similarity
        overall_similarity = self._compute_overall_similarity(all_gaps)

        # Identify problematic areas
        problematic = self._identify_problematic_areas(all_gaps)

        # Generate prioritized fixes
        prioritized_fixes = self._generate_fix_recommendations(all_gaps[:10])

        report = GapReport(
            wip_path=wip_path,
            profile_name=self.profile.name,
            analysis_date=datetime.now().isoformat(),
            overall_similarity=overall_similarity,
            trance_score=wip_features.trance_score,
            nearest_cluster=nearest_cluster_id,
            nearest_cluster_name=cluster_name,
            cluster_distance=cluster_distance,
            all_gaps=all_gaps,
            most_problematic_areas=problematic,
            prioritized_fixes=prioritized_fixes
        )

        return report

    def compute_feature_gap(
        self,
        feature_name: str,
        wip_value: float,
        stats: FeatureStatistics
    ) -> FeatureGap:
        """
        Compute gap for a single feature.

        Args:
            feature_name: Name of the feature
            wip_value: WIP track's value for this feature
            stats: Reference statistics for this feature

        Returns:
            FeatureGap with all computed metrics
        """
        target_value = stats.mean
        acceptable_range = stats.acceptable_range
        absolute_delta = wip_value - target_value

        # Z-score
        if stats.std > 0:
            z_score = absolute_delta / stats.std
        else:
            z_score = 0.0

        # Percentile (approximate using z-score and normal distribution)
        from scipy.stats import norm
        percentile = float(norm.cdf(z_score) * 100)

        # Range check
        is_outside, range_distance, direction = self._compute_range_gap(
            wip_value, acceptable_range
        )

        # Severity based on z-score
        severity = self._classify_severity(z_score)

        # Get recommendation
        description, recommendation = self._get_feature_guidance(
            feature_name, wip_value, target_value, z_score, direction
        )

        return FeatureGap(
            feature_name=feature_name,
            wip_value=wip_value,
            target_value=target_value,
            acceptable_range=acceptable_range,
            absolute_delta=absolute_delta,
            z_score=z_score,
            percentile=percentile,
            severity=severity,
            is_outside_range=is_outside,
            direction=direction if is_outside else "ok",
            is_fixable=feature_name not in ['tempo', 'tempo_score'],
            fix_difficulty=FIX_DIFFICULTY.get(feature_name, 'medium'),
            description=description,
            recommendation=recommendation
        )

    def find_nearest_cluster(
        self,
        wip_features: Dict[str, float]
    ) -> Tuple[int, float]:
        """
        Find which style cluster the WIP is closest to.

        Args:
            wip_features: Dict of feature name -> value

        Returns:
            (cluster_id, distance)
        """
        if not self.profile.clusters:
            return 0, 0.0

        best_cluster = 0
        best_distance = float('inf')

        for cluster in self.profile.clusters:
            distance = self._compute_cluster_distance(wip_features, cluster)
            if distance < best_distance:
                best_distance = distance
                best_cluster = cluster.cluster_id

        return best_cluster, best_distance

    def _compute_cluster_distance(
        self,
        wip_features: Dict[str, float],
        cluster: StyleCluster
    ) -> float:
        """Compute normalized distance to cluster centroid."""
        distance = 0.0
        n_features = 0

        for feature, wip_val in wip_features.items():
            if feature in cluster.centroid and feature in self.profile.feature_stats:
                centroid_val = cluster.centroid[feature]
                stats = self.profile.feature_stats[feature]

                if stats.std > 0:
                    # Normalized difference
                    diff = (wip_val - centroid_val) / stats.std
                    distance += diff ** 2
                    n_features += 1

        if n_features > 0:
            distance = np.sqrt(distance / n_features)

        return float(distance)

    def prioritize_gaps(self, gaps: List[FeatureGap]) -> List[FeatureGap]:
        """
        Sort gaps by priority score, highest first.

        Args:
            gaps: List of FeatureGap objects

        Returns:
            Sorted list with highest priority first
        """
        def priority_score(gap: FeatureGap) -> float:
            severity_weight = {
                'critical': 4.0,
                'warning': 2.0,
                'minor': 1.0,
                'ok': 0.0
            }

            fix_bonus = {
                'easy': 1.5,
                'medium': 1.2,
                'hard': 1.0,
                'manual': 0.5
            }

            importance = FEATURE_IMPORTANCE.get(gap.feature_name, 0.5)
            severity = severity_weight.get(gap.severity, 0.0)
            fixability = fix_bonus.get(gap.fix_difficulty, 1.0)

            return severity * importance * fixability

        return sorted(gaps, key=priority_score, reverse=True)

    def _compute_range_gap(
        self,
        wip_value: float,
        acceptable_range: Tuple[float, float]
    ) -> Tuple[bool, float, str]:
        """Compute gap relative to acceptable range."""
        low, high = acceptable_range

        if wip_value < low:
            return True, low - wip_value, "low"
        elif wip_value > high:
            return True, wip_value - high, "high"
        else:
            return False, 0.0, "ok"

    def _classify_severity(self, z_score: float) -> str:
        """Classify severity based on z-score."""
        abs_z = abs(z_score)
        if abs_z > 3:
            return "critical"
        elif abs_z > 2:
            return "warning"
        elif abs_z > 1:
            return "minor"
        else:
            return "ok"

    def _get_feature_guidance(
        self,
        feature_name: str,
        wip_value: float,
        target_value: float,
        z_score: float,
        direction: str
    ) -> Tuple[str, str]:
        """Generate human-readable description and recommendation."""
        # Format value for display
        if 'db' in feature_name.lower() or 'depth' in feature_name.lower():
            wip_str = f"{wip_value:.1f} dB"
            target_str = f"{target_value:.1f} dB"
            delta_str = f"{abs(wip_value - target_value):.1f} dB"
        elif 'score' in feature_name.lower() or 'width' in feature_name.lower():
            wip_str = f"{wip_value:.2f}"
            target_str = f"{target_value:.2f}"
            delta_str = f"{abs(wip_value - target_value):.2f}"
        elif feature_name == 'tempo':
            wip_str = f"{wip_value:.1f} BPM"
            target_str = f"{target_value:.1f} BPM"
            delta_str = f"{abs(wip_value - target_value):.1f} BPM"
        else:
            wip_str = f"{wip_value:.2f}"
            target_str = f"{target_value:.2f}"
            delta_str = f"{abs(wip_value - target_value):.2f}"

        # Generate description
        feature_display = feature_name.replace('_', ' ').title()

        if direction == "high":
            description = f"{feature_display} is {delta_str} above reference target ({wip_str} vs {target_str})"
        elif direction == "low":
            description = f"{feature_display} is {delta_str} below reference target ({wip_str} vs {target_str})"
        else:
            description = f"{feature_display} is within target range ({wip_str})"

        # Get recommendation
        if feature_name in FEATURE_RECOMMENDATIONS and direction in FEATURE_RECOMMENDATIONS[feature_name]:
            recommendation = FEATURE_RECOMMENDATIONS[feature_name][direction]
        else:
            if direction == "high":
                recommendation = f"Consider reducing {feature_display.lower()}"
            elif direction == "low":
                recommendation = f"Consider increasing {feature_display.lower()}"
            else:
                recommendation = "No action needed"

        return description, recommendation

    def _compute_overall_similarity(self, gaps: List[FeatureGap]) -> float:
        """Compute overall similarity score (0-1)."""
        if not gaps:
            return 1.0

        # Use weighted average of normalized scores
        total_weight = 0.0
        weighted_score = 0.0

        for gap in gaps:
            weight = FEATURE_IMPORTANCE.get(gap.feature_name, 0.5)

            # Convert z-score to similarity (z=0 -> 1.0, z=3 -> 0)
            # Using sigmoid-like function
            z_similarity = 1.0 / (1.0 + abs(gap.z_score) / 2.0)

            weighted_score += weight * z_similarity
            total_weight += weight

        if total_weight > 0:
            return weighted_score / total_weight

        return 0.5

    def _identify_problematic_areas(self, gaps: List[FeatureGap]) -> List[str]:
        """Identify the most problematic feature areas."""
        problematic = []

        for gap in gaps:
            if gap.severity in ['critical', 'warning']:
                # Map to broader area
                area = self._feature_to_area(gap.feature_name)
                if area not in problematic:
                    problematic.append(area)

        return problematic[:5]  # Top 5 areas

    def _feature_to_area(self, feature_name: str) -> str:
        """Map feature name to broader production area."""
        area_map = {
            'pumping': 'Sidechain/Dynamics',
            'modulation': 'Sidechain/Dynamics',
            'stereo': 'Stereo Width',
            'supersaw': 'Stereo Width',
            'energy': 'Energy/Arrangement',
            'tempo': 'Tempo/Rhythm',
            'four_on_floor': 'Tempo/Rhythm',
            'offbeat': 'Tempo/Rhythm',
            'spectral': 'Frequency Balance',
            'acid': 'Sound Design',
        }

        for key, area in area_map.items():
            if key in feature_name.lower():
                return area

        return 'General'

    def _generate_fix_recommendations(self, gaps: List[FeatureGap]) -> List[FixRecommendation]:
        """Generate prioritized fix recommendations from gaps."""
        fixes = []

        for i, gap in enumerate(gaps):
            if gap.severity == 'ok':
                continue

            expected = f"Move {gap.feature_name} closer to reference range"
            if gap.direction == 'high':
                expected = f"Reduce {gap.feature_name} by ~{abs(gap.absolute_delta):.2f}"
            elif gap.direction == 'low':
                expected = f"Increase {gap.feature_name} by ~{abs(gap.absolute_delta):.2f}"

            fix = FixRecommendation(
                priority=i + 1,
                feature=gap.feature_name,
                severity=gap.severity,
                action=gap.recommendation,
                expected_improvement=expected,
                difficulty=gap.fix_difficulty
            )
            fixes.append(fix)

        return fixes
