"""
Reference Profile Integration for Live DAW Coaching.

Bridges the reference profile system with the coaching pipeline.
Provides gap analysis, target values, and prioritized recommendations.
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import sys

# Add parent path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from profiling.profile_storage import (
        ReferenceProfile,
        FeatureStatistics,
        load_profile
    )
except ImportError:
    # Fallback for standalone testing
    ReferenceProfile = None
    FeatureStatistics = None
    load_profile = None


# =============================================================================
# Gap Analysis Results
# =============================================================================

@dataclass
class FeatureGap:
    """A gap between user's track and reference profile."""
    feature_name: str
    user_value: float
    target_value: float          # Profile mean
    acceptable_low: float
    acceptable_high: float
    deviation: float             # Standard deviations from mean
    severity: str                # good, minor, moderate, significant, critical
    direction: str               # above, below, in_range
    description: str             # Human-readable description
    fix_suggestion: Optional[str] = None

    @property
    def is_in_range(self) -> bool:
        return self.acceptable_low <= self.user_value <= self.acceptable_high

    @property
    def priority_score(self) -> float:
        """Calculate priority score for sorting (higher = more urgent)."""
        severity_weights = {
            'critical': 5.0,
            'significant': 4.0,
            'moderate': 3.0,
            'minor': 2.0,
            'good': 0.0
        }
        return severity_weights.get(self.severity, 0.0) * abs(self.deviation)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'feature_name': self.feature_name,
            'user_value': self.user_value,
            'target_value': self.target_value,
            'acceptable_range': [self.acceptable_low, self.acceptable_high],
            'deviation': self.deviation,
            'severity': self.severity,
            'direction': self.direction,
            'description': self.description,
            'fix_suggestion': self.fix_suggestion,
            'is_in_range': self.is_in_range,
            'priority_score': self.priority_score
        }


@dataclass
class GapAnalysis:
    """Complete gap analysis comparing user track to reference profile."""
    profile_name: str
    track_name: str
    total_features: int
    in_range_count: int
    gap_count: int
    gaps: List[FeatureGap]
    overall_score: float         # 0-100, how close to reference
    closest_cluster: Optional[str] = None
    summary: str = ""

    @property
    def compliance_percentage(self) -> float:
        """Percentage of features within acceptable range."""
        if self.total_features == 0:
            return 0.0
        return (self.in_range_count / self.total_features) * 100

    def get_prioritized_gaps(self, max_items: int = 5) -> List[FeatureGap]:
        """Get gaps sorted by priority (most urgent first)."""
        sorted_gaps = sorted(
            [g for g in self.gaps if not g.is_in_range],
            key=lambda g: g.priority_score,
            reverse=True
        )
        return sorted_gaps[:max_items]

    def get_gaps_by_severity(self, severity: str) -> List[FeatureGap]:
        """Get gaps of a specific severity level."""
        return [g for g in self.gaps if g.severity == severity]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'profile_name': self.profile_name,
            'track_name': self.track_name,
            'total_features': self.total_features,
            'in_range_count': self.in_range_count,
            'gap_count': self.gap_count,
            'compliance_percentage': self.compliance_percentage,
            'overall_score': self.overall_score,
            'closest_cluster': self.closest_cluster,
            'summary': self.summary,
            'gaps': [g.to_dict() for g in self.gaps]
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# =============================================================================
# Feature Mapping
# =============================================================================

# Maps analysis output names to profile feature names
FEATURE_MAPPING = {
    # Loudness
    'integrated_lufs': 'integrated_lufs',
    'lufs': 'integrated_lufs',
    'loudness': 'integrated_lufs',
    'dynamic_range': 'dynamic_range',
    'dynamic_range_db': 'dynamic_range',

    # Frequency
    'spectral_centroid': 'spectral_brightness',
    'spectral_brightness': 'spectral_brightness',
    'brightness': 'spectral_brightness',

    # Sub-bass/Bass
    'sub_bass': 'sub_bass_energy',
    'sub_bass_energy': 'sub_bass_energy',
    'bass': 'bass_energy',
    'bass_energy': 'bass_energy',

    # Stereo
    'stereo_width': 'stereo_width',
    'width': 'stereo_width',
    'correlation': 'phase_correlation',
    'phase_correlation': 'phase_correlation',

    # Rhythm/Trance specific
    'tempo': 'tempo',
    'bpm': 'tempo',
    'tempo_stability': 'tempo_stability',
    'four_on_floor': 'four_on_floor_score',
    'four_on_floor_score': 'four_on_floor_score',

    # Pumping/Sidechain
    'pumping_score': 'pumping_score',
    'pumping': 'pumping_score',
    'modulation_depth': 'modulation_depth_db',
    'modulation_depth_db': 'modulation_depth_db',

    # Energy
    'energy': 'avg_energy',
    'avg_energy': 'avg_energy',
    'energy_range': 'energy_range',
    'energy_progression': 'energy_progression',

    # Trance score
    'trance_score': 'trance_score',
}

# Severity thresholds (in standard deviations)
SEVERITY_THRESHOLDS = {
    'good': 0.5,        # Within 0.5 std
    'minor': 1.0,       # 0.5-1.0 std
    'moderate': 2.0,    # 1.0-2.0 std
    'significant': 3.0, # 2.0-3.0 std
    'critical': float('inf')  # > 3.0 std
}

# Feature descriptions for human-readable output
FEATURE_DESCRIPTIONS = {
    'integrated_lufs': 'Overall loudness',
    'dynamic_range': 'Dynamic range',
    'spectral_brightness': 'Spectral brightness',
    'sub_bass_energy': 'Sub-bass energy',
    'bass_energy': 'Bass energy',
    'stereo_width': 'Stereo width',
    'phase_correlation': 'Stereo correlation',
    'tempo': 'Tempo',
    'tempo_stability': 'Tempo stability',
    'four_on_floor_score': 'Four-on-floor pattern',
    'pumping_score': 'Sidechain pumping',
    'modulation_depth_db': 'Modulation depth',
    'avg_energy': 'Average energy',
    'energy_range': 'Energy dynamics',
    'energy_progression': 'Energy progression',
    'trance_score': 'Overall trance score',
}


# =============================================================================
# Reference Integration Class
# =============================================================================

class ReferenceIntegration:
    """
    Integrates reference profiles with the coaching pipeline.

    Usage:
        integration = ReferenceIntegration()
        integration.load_profile("profiles/trance_reference_profile.json")

        # Analyze user track against reference
        analysis_results = {...}  # From audio analyzer
        gaps = integration.analyze_gaps(analysis_results, "My Track")

        # Get prioritized issues
        top_issues = gaps.get_prioritized_gaps(5)

        # Get fix targets
        target = integration.get_fix_target("bass_energy")
    """

    def __init__(self):
        self._profile: Optional[ReferenceProfile] = None
        self._profile_path: Optional[str] = None

    @property
    def is_loaded(self) -> bool:
        """Check if a profile is loaded."""
        return self._profile is not None

    @property
    def profile_name(self) -> Optional[str]:
        """Get loaded profile name."""
        return self._profile.name if self._profile else None

    def load_profile(self, path: str) -> bool:
        """
        Load a reference profile from file.

        Args:
            path: Path to profile JSON file

        Returns:
            True if successful
        """
        try:
            if load_profile is None:
                raise ImportError("profile_storage not available")

            self._profile = load_profile(path)
            self._profile_path = path
            return True
        except Exception as e:
            print(f"Error loading profile: {e}")
            return False

    def load_profile_dict(self, data: Dict[str, Any]) -> bool:
        """
        Load a reference profile from a dictionary.

        Args:
            data: Profile data as dictionary

        Returns:
            True if successful
        """
        try:
            if ReferenceProfile is None:
                raise ImportError("profile_storage not available")

            self._profile = ReferenceProfile.from_dict(data)
            return True
        except Exception as e:
            print(f"Error loading profile from dict: {e}")
            return False

    def get_feature_stats(self, feature: str) -> Optional[FeatureStatistics]:
        """Get statistics for a feature."""
        if not self._profile:
            return None

        # Try direct lookup
        if feature in self._profile.feature_stats:
            return self._profile.feature_stats[feature]

        # Try mapping
        mapped = FEATURE_MAPPING.get(feature.lower())
        if mapped and mapped in self._profile.feature_stats:
            return self._profile.feature_stats[mapped]

        return None

    def get_acceptable_range(self, feature: str) -> Optional[Tuple[float, float]]:
        """Get acceptable range for a feature."""
        stats = self.get_feature_stats(feature)
        return stats.acceptable_range if stats else None

    def get_target_value(self, feature: str) -> Optional[float]:
        """Get target (mean) value for a feature."""
        stats = self.get_feature_stats(feature)
        return stats.mean if stats else None

    def get_fix_target(self, feature: str) -> Optional[Dict[str, Any]]:
        """
        Get complete fix target information for a feature.

        Returns:
            Dict with target, range, and conversion info
        """
        stats = self.get_feature_stats(feature)
        if not stats:
            return None

        return {
            'feature': feature,
            'target': stats.mean,
            'acceptable_low': stats.acceptable_range[0],
            'acceptable_high': stats.acceptable_range[1],
            'median': stats.p50,
            'description': FEATURE_DESCRIPTIONS.get(feature, feature)
        }

    def is_in_range(self, feature: str, value: float) -> bool:
        """Check if a value is within acceptable range for a feature."""
        stats = self.get_feature_stats(feature)
        if not stats:
            return True  # No data, assume OK
        return stats.is_in_range(value)

    def analyze_gaps(self,
                     analysis_results: Dict[str, Any],
                     track_name: str = "User Track") -> GapAnalysis:
        """
        Analyze gaps between user track and reference profile.

        Args:
            analysis_results: Dict of feature -> value from audio analysis
            track_name: Name of the track being analyzed

        Returns:
            GapAnalysis object with all gaps and recommendations
        """
        if not self._profile:
            return GapAnalysis(
                profile_name="None",
                track_name=track_name,
                total_features=0,
                in_range_count=0,
                gap_count=0,
                gaps=[],
                overall_score=0.0,
                summary="No reference profile loaded"
            )

        gaps: List[FeatureGap] = []
        in_range_count = 0
        total_deviation = 0.0
        feature_count = 0

        for feature, value in analysis_results.items():
            if not isinstance(value, (int, float)):
                continue

            stats = self.get_feature_stats(feature)
            if not stats:
                continue

            feature_count += 1
            deviation = stats.deviation_from_mean(value)
            total_deviation += abs(deviation)

            # Determine severity
            abs_dev = abs(deviation)
            if abs_dev <= SEVERITY_THRESHOLDS['good']:
                severity = 'good'
            elif abs_dev <= SEVERITY_THRESHOLDS['minor']:
                severity = 'minor'
            elif abs_dev <= SEVERITY_THRESHOLDS['moderate']:
                severity = 'moderate'
            elif abs_dev <= SEVERITY_THRESHOLDS['significant']:
                severity = 'significant'
            else:
                severity = 'critical'

            # Determine direction
            if stats.is_in_range(value):
                direction = 'in_range'
                in_range_count += 1
            elif value < stats.acceptable_range[0]:
                direction = 'below'
            else:
                direction = 'above'

            # Generate description
            feature_desc = FEATURE_DESCRIPTIONS.get(feature, feature)
            if direction == 'in_range':
                description = f"{feature_desc} is within acceptable range"
            elif direction == 'below':
                description = f"{feature_desc} is too low ({value:.2f} vs target {stats.mean:.2f})"
            else:
                description = f"{feature_desc} is too high ({value:.2f} vs target {stats.mean:.2f})"

            # Generate fix suggestion
            fix_suggestion = self._generate_fix_suggestion(feature, value, stats, direction)

            gaps.append(FeatureGap(
                feature_name=feature,
                user_value=value,
                target_value=stats.mean,
                acceptable_low=stats.acceptable_range[0],
                acceptable_high=stats.acceptable_range[1],
                deviation=deviation,
                severity=severity,
                direction=direction,
                description=description,
                fix_suggestion=fix_suggestion
            ))

        # Calculate overall score (0-100, higher is better)
        if feature_count > 0:
            avg_deviation = total_deviation / feature_count
            # Score decreases as average deviation increases
            overall_score = max(0, 100 - (avg_deviation * 25))
        else:
            overall_score = 0.0

        # Find closest cluster
        closest_cluster = None
        if self._profile.clusters and analysis_results:
            try:
                cluster = self._profile.find_closest_cluster(analysis_results)
                closest_cluster = cluster.name if cluster else None
            except:
                pass

        # Generate summary
        gap_count = len([g for g in gaps if not g.is_in_range])
        summary = self._generate_summary(gaps, overall_score, closest_cluster)

        return GapAnalysis(
            profile_name=self._profile.name,
            track_name=track_name,
            total_features=feature_count,
            in_range_count=in_range_count,
            gap_count=gap_count,
            gaps=gaps,
            overall_score=overall_score,
            closest_cluster=closest_cluster,
            summary=summary
        )

    def _generate_fix_suggestion(self,
                                  feature: str,
                                  value: float,
                                  stats: FeatureStatistics,
                                  direction: str) -> Optional[str]:
        """Generate a fix suggestion for a gap."""
        if direction == 'in_range':
            return None

        target = stats.mean
        diff = abs(value - target)

        suggestions = {
            'integrated_lufs': {
                'below': f"Increase overall loudness by ~{diff:.1f} LUFS",
                'above': f"Reduce overall loudness by ~{diff:.1f} LUFS"
            },
            'dynamic_range': {
                'below': f"Reduce compression to increase dynamic range by ~{diff:.1f} dB",
                'above': f"Apply more compression to reduce dynamic range by ~{diff:.1f} dB"
            },
            'sub_bass_energy': {
                'below': "Boost sub-bass frequencies (20-60Hz) or increase bass levels",
                'above': "Cut sub-bass frequencies or reduce bass levels"
            },
            'bass_energy': {
                'below': "Boost bass frequencies (60-250Hz) or increase bass instrument levels",
                'above': "Cut bass frequencies or reduce bass instrument levels"
            },
            'stereo_width': {
                'below': "Widen stereo image using stereo widening tools",
                'above': "Narrow stereo image to improve mono compatibility"
            },
            'pumping_score': {
                'below': "Increase sidechain compression on bass/pads",
                'above': "Reduce sidechain compression intensity"
            },
        }

        if feature in suggestions:
            return suggestions[feature].get(direction)

        # Generic suggestion
        if direction == 'below':
            return f"Increase {FEATURE_DESCRIPTIONS.get(feature, feature).lower()}"
        else:
            return f"Reduce {FEATURE_DESCRIPTIONS.get(feature, feature).lower()}"

    def _generate_summary(self,
                          gaps: List[FeatureGap],
                          score: float,
                          cluster: Optional[str]) -> str:
        """Generate a summary of the gap analysis."""
        critical = len([g for g in gaps if g.severity == 'critical'])
        significant = len([g for g in gaps if g.severity == 'significant'])
        moderate = len([g for g in gaps if g.severity == 'moderate'])
        in_range = len([g for g in gaps if g.is_in_range])
        total = len(gaps)

        parts = []

        if score >= 80:
            parts.append(f"Track is well-aligned with reference (score: {score:.0f}/100)")
        elif score >= 60:
            parts.append(f"Track is reasonably close to reference (score: {score:.0f}/100)")
        elif score >= 40:
            parts.append(f"Track needs some work to match reference (score: {score:.0f}/100)")
        else:
            parts.append(f"Track significantly differs from reference (score: {score:.0f}/100)")

        if cluster:
            parts.append(f"Closest style: {cluster}")

        if critical > 0:
            parts.append(f"{critical} critical issues need immediate attention")
        if significant > 0:
            parts.append(f"{significant} significant issues to address")

        if total > 0:
            parts.append(f"{in_range}/{total} features within acceptable range")

        return ". ".join(parts) + "."

    def get_available_features(self) -> List[str]:
        """Get list of features in the loaded profile."""
        if not self._profile:
            return []
        return list(self._profile.feature_stats.keys())


# =============================================================================
# Global Integration Instance
# =============================================================================

_integration: Optional[ReferenceIntegration] = None


def get_reference_integration() -> ReferenceIntegration:
    """Get or create the global reference integration."""
    global _integration
    if _integration is None:
        _integration = ReferenceIntegration()
    return _integration


def load_default_profile() -> bool:
    """
    Load the default trance reference profile.

    Looks for profile in standard locations.
    """
    integration = get_reference_integration()

    # Try standard locations
    possible_paths = [
        Path(__file__).parent.parent.parent / "profiles" / "trance_reference_profile.json",
        Path(__file__).parent.parent.parent.parent / "profiles" / "trance_reference_profile.json",
        Path.home() / ".claude_ableton" / "trance_reference_profile.json",
    ]

    for path in possible_paths:
        if path.exists():
            return integration.load_profile(str(path))

    return False
