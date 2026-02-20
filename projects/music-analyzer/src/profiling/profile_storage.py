"""
Profile Storage Module.

Data classes and serialization for reference profiles.
"""

import json
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime


@dataclass
class FeatureStatistics:
    """Statistics for a single feature across all reference tracks."""
    mean: float
    std: float
    min: float
    max: float
    p10: float  # 10th percentile
    p25: float  # 25th percentile (Q1)
    p50: float  # Median
    p75: float  # 75th percentile (Q3)
    p90: float  # 90th percentile
    confidence_interval_95: Tuple[float, float]
    acceptable_range: Tuple[float, float]  # Derived bounds for gap analysis

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            'mean': float(self.mean),
            'std': float(self.std),
            'min': float(self.min),
            'max': float(self.max),
            'p10': float(self.p10),
            'p25': float(self.p25),
            'p50': float(self.p50),
            'p75': float(self.p75),
            'p90': float(self.p90),
            'confidence_interval_95': [float(self.confidence_interval_95[0]),
                                       float(self.confidence_interval_95[1])],
            'acceptable_range': [float(self.acceptable_range[0]),
                                 float(self.acceptable_range[1])]
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'FeatureStatistics':
        """Create from dict."""
        return cls(
            mean=d['mean'],
            std=d['std'],
            min=d['min'],
            max=d['max'],
            p10=d['p10'],
            p25=d['p25'],
            p50=d['p50'],
            p75=d['p75'],
            p90=d['p90'],
            confidence_interval_95=tuple(d['confidence_interval_95']),
            acceptable_range=tuple(d['acceptable_range'])
        )

    def is_in_range(self, value: float) -> bool:
        """Check if value is within acceptable range."""
        low, high = self.acceptable_range
        return low <= value <= high

    def deviation_from_mean(self, value: float) -> float:
        """Calculate deviation in standard deviations from mean."""
        if self.std == 0:
            return 0.0
        return (value - self.mean) / self.std


@dataclass
class StyleCluster:
    """A style sub-cluster within the reference collection."""
    cluster_id: int
    name: str
    track_indices: List[int]
    centroid: Dict[str, float]
    variance: Dict[str, float]
    distinctive_features: List[str]
    exemplar_tracks: List[int]

    @property
    def track_count(self) -> int:
        return len(self.track_indices)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            'cluster_id': self.cluster_id,
            'name': self.name,
            'track_count': self.track_count,
            'track_indices': self.track_indices,
            'centroid': {k: float(v) for k, v in self.centroid.items()},
            'variance': {k: float(v) for k, v in self.variance.items()},
            'distinctive_features': self.distinctive_features,
            'exemplar_tracks': self.exemplar_tracks
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'StyleCluster':
        """Create from dict."""
        return cls(
            cluster_id=d['cluster_id'],
            name=d['name'],
            track_indices=d['track_indices'],
            centroid=d['centroid'],
            variance=d['variance'],
            distinctive_features=d['distinctive_features'],
            exemplar_tracks=d['exemplar_tracks']
        )


@dataclass
class TrackInfo:
    """Metadata for a track in the reference collection."""
    index: int
    filename: str
    cluster: int
    trance_score: float
    artist: Optional[str] = None
    title: Optional[str] = None
    tempo: Optional[float] = None
    key: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        d = {
            'index': self.index,
            'filename': self.filename,
            'cluster': self.cluster,
            'trance_score': float(self.trance_score)
        }
        if self.artist:
            d['artist'] = self.artist
        if self.title:
            d['title'] = self.title
        if self.tempo:
            d['tempo'] = float(self.tempo)
        if self.key:
            d['key'] = self.key
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'TrackInfo':
        """Create from dict."""
        return cls(
            index=d['index'],
            filename=d['filename'],
            cluster=d['cluster'],
            trance_score=d['trance_score'],
            artist=d.get('artist'),
            title=d.get('title'),
            tempo=d.get('tempo'),
            key=d.get('key')
        )


@dataclass
class ReferenceProfile:
    """
    Complete reference style profile.

    Contains statistical summaries, style clusters, and track metadata
    for a collection of reference tracks.
    """
    name: str
    created_date: str
    track_count: int
    feature_stats: Dict[str, FeatureStatistics]
    clusters: List[StyleCluster]
    feature_correlations: Optional[np.ndarray] = None
    track_metadata: List[TrackInfo] = field(default_factory=list)
    version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        d = {
            'name': self.name,
            'version': self.version,
            'created_date': self.created_date,
            'track_count': self.track_count,
            'feature_statistics': {
                k: v.to_dict() for k, v in self.feature_stats.items()
            },
            'clusters': [c.to_dict() for c in self.clusters],
            'track_metadata': [t.to_dict() for t in self.track_metadata]
        }

        if self.feature_correlations is not None:
            d['feature_correlations'] = self.feature_correlations.tolist()

        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'ReferenceProfile':
        """Create from dict."""
        feature_stats = {
            k: FeatureStatistics.from_dict(v)
            for k, v in d['feature_statistics'].items()
        }

        clusters = [StyleCluster.from_dict(c) for c in d['clusters']]

        track_metadata = [
            TrackInfo.from_dict(t) for t in d.get('track_metadata', [])
        ]

        correlations = None
        if 'feature_correlations' in d:
            correlations = np.array(d['feature_correlations'])

        return cls(
            name=d['name'],
            version=d.get('version', '1.0'),
            created_date=d['created_date'],
            track_count=d['track_count'],
            feature_stats=feature_stats,
            clusters=clusters,
            feature_correlations=correlations,
            track_metadata=track_metadata
        )

    def get_acceptable_range(self, feature: str) -> Tuple[float, float]:
        """Get acceptable range for a feature."""
        if feature not in self.feature_stats:
            raise KeyError(f"Feature '{feature}' not in profile")
        return self.feature_stats[feature].acceptable_range

    def get_target_value(self, feature: str) -> float:
        """Get target (mean) value for a feature."""
        if feature not in self.feature_stats:
            raise KeyError(f"Feature '{feature}' not in profile")
        return self.feature_stats[feature].mean

    def get_cluster_by_id(self, cluster_id: int) -> Optional[StyleCluster]:
        """Get cluster by ID."""
        for cluster in self.clusters:
            if cluster.cluster_id == cluster_id:
                return cluster
        return None

    def find_closest_cluster(self, features: Dict[str, float]) -> StyleCluster:
        """Find the cluster whose centroid is closest to given features."""
        if not self.clusters:
            raise ValueError("Profile has no clusters")

        best_cluster = None
        best_distance = float('inf')

        for cluster in self.clusters:
            # Calculate Euclidean distance to centroid (normalized)
            distance = 0.0
            for feature, value in features.items():
                if feature in cluster.centroid and feature in self.feature_stats:
                    centroid_val = cluster.centroid[feature]
                    std = self.feature_stats[feature].std
                    if std > 0:
                        diff = (value - centroid_val) / std
                        distance += diff ** 2

            if distance < best_distance:
                best_distance = distance
                best_cluster = cluster

        return best_cluster

    def save(self, path: str):
        """Save profile to JSON file."""
        save_profile(self, path)

    @classmethod
    def load(cls, path: str) -> 'ReferenceProfile':
        """Load profile from JSON file."""
        return load_profile(path)


def save_profile(profile: ReferenceProfile, path: str):
    """
    Save reference profile to JSON file.

    Args:
        profile: ReferenceProfile to save
        path: Output file path
    """
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(profile.to_dict(), f, indent=2)


def load_profile(path: str) -> ReferenceProfile:
    """
    Load reference profile from JSON file.

    Args:
        path: Path to profile JSON file

    Returns:
        ReferenceProfile object
    """
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return ReferenceProfile.from_dict(data)


def compute_feature_statistics(
    values: np.ndarray,
    method: str = "iqr"
) -> FeatureStatistics:
    """
    Compute comprehensive statistics for a feature.

    Args:
        values: Array of feature values
        method: Method for acceptable range calculation
                "iqr" - Interquartile range (robust to outliers)
                "percentile" - P10 to P90
                "std" - Mean ± 2 std

    Returns:
        FeatureStatistics object
    """
    values = np.asarray(values)
    values = values[~np.isnan(values)]  # Remove NaNs

    if len(values) == 0:
        return FeatureStatistics(
            mean=0.0, std=0.0, min=0.0, max=0.0,
            p10=0.0, p25=0.0, p50=0.0, p75=0.0, p90=0.0,
            confidence_interval_95=(0.0, 0.0),
            acceptable_range=(0.0, 0.0)
        )

    mean = float(np.mean(values))
    std = float(np.std(values))
    min_val = float(np.min(values))
    max_val = float(np.max(values))

    p10 = float(np.percentile(values, 10))
    p25 = float(np.percentile(values, 25))
    p50 = float(np.percentile(values, 50))
    p75 = float(np.percentile(values, 75))
    p90 = float(np.percentile(values, 90))

    # 95% confidence interval for the mean
    n = len(values)
    se = std / np.sqrt(n) if n > 0 else 0
    ci_95 = (mean - 1.96 * se, mean + 1.96 * se)

    # Acceptable range based on method
    if method == "iqr":
        iqr = p75 - p25
        low = p25 - 1.5 * iqr
        high = p75 + 1.5 * iqr
        # Constrain to actual data range
        low = max(low, min_val)
        high = min(high, max_val)
        acceptable_range = (low, high)
    elif method == "percentile":
        acceptable_range = (p10, p90)
    else:  # std
        acceptable_range = (mean - 2 * std, mean + 2 * std)

    return FeatureStatistics(
        mean=mean,
        std=std,
        min=min_val,
        max=max_val,
        p10=p10,
        p25=p25,
        p50=p50,
        p75=p75,
        p90=p90,
        confidence_interval_95=ci_95,
        acceptable_range=acceptable_range
    )
