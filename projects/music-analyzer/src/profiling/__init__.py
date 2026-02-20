"""
Reference Profiling Module.

Build style profiles from reference tracks for comparison and gap analysis.

Components:
- ReferenceProfiler: Build profiles from reference collections
- StyleClusters: Discover sub-styles within reference collection
- ProfileStorage: Save/load profiles to JSON
- ProfileValidator: Validate profile quality

Usage:
    from profiling import ReferenceProfiler

    profiler = ReferenceProfiler()
    profile = profiler.build_profile("references/", profile_name="my_trance_profile")
    profile.save("trance_profile.json")
"""

from .reference_profiler import ReferenceProfiler
from .style_clusters import discover_clusters, characterize_cluster
from .profile_storage import (
    ReferenceProfile,
    FeatureStatistics,
    StyleCluster,
    TrackInfo,
    save_profile,
    load_profile
)

__all__ = [
    'ReferenceProfiler',
    'ReferenceProfile',
    'FeatureStatistics',
    'StyleCluster',
    'TrackInfo',
    'discover_clusters',
    'characterize_cluster',
    'save_profile',
    'load_profile',
]
