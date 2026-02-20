"""
Reference Profiler Module.

Build comprehensive style profiles from reference track collections.
"""

import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Callable, Any
from datetime import datetime
import json

from .profile_storage import (
    ReferenceProfile,
    FeatureStatistics,
    StyleCluster,
    TrackInfo,
    compute_feature_statistics
)
from .style_clusters import discover_clusters, normalize_features


# Features to extract for profiling
PROFILE_FEATURES = [
    # Rhythm features
    'tempo',
    'tempo_stability',
    'tempo_score',
    'four_on_floor_score',
    'four_on_floor_strength',
    'offbeat_hihat_score',
    'offbeat_hihat_strength',

    # Pumping features
    'pumping_score',
    'pumping_modulation_depth_db',
    'pumping_modulation_depth_linear',
    'pumping_regularity',

    # Stereo features
    'supersaw_score',
    'stereo_width',
    'phase_correlation',

    # 303/Acid features
    'acid_303_score',
    'acid_filter_sweep_score',
    'acid_resonance_score',
    'acid_glide_score',

    # Energy features
    'energy_progression',
    'energy_range',
    'energy_std',
    'avg_energy',

    # Spectral features
    'spectral_brightness',

    # Overall
    'trance_score',
]

# Range calculation methods per feature type
FEATURE_RANGE_METHODS = {
    'tempo': 'percentile',
    'tempo_score': 'iqr',
    'tempo_stability': 'std',
    'four_on_floor_score': 'iqr',
    'four_on_floor_strength': 'iqr',
    'offbeat_hihat_score': 'iqr',
    'pumping_score': 'iqr',
    'pumping_modulation_depth_db': 'iqr',
    'supersaw_score': 'percentile',
    'stereo_width': 'percentile',
    'acid_303_score': 'percentile',
    'energy_progression': 'iqr',
    'energy_range': 'iqr',
    'spectral_brightness': 'std',
    'trance_score': 'iqr',
}


class ReferenceProfiler:
    """
    Build and manage reference style profiles.

    Usage:
        profiler = ReferenceProfiler()
        profile = profiler.build_profile("references/")
        profile.save("trance_profile.json")
    """

    def __init__(self, cache_dir: Optional[str] = None, verbose: bool = False):
        """
        Initialize the profiler.

        Args:
            cache_dir: Directory to cache extracted features
            verbose: Print progress messages
        """
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.verbose = verbose
        self._feature_cache: Dict[str, Dict] = {}

    def build_profile(
        self,
        reference_dir: str,
        profile_name: str = "trance_profile",
        n_clusters: Optional[int] = None,
        min_tracks: int = 10,
        progress_callback: Optional[Callable] = None
    ) -> ReferenceProfile:
        """
        Build comprehensive profile from reference tracks.

        Args:
            reference_dir: Directory containing reference audio files
            profile_name: Name for the profile
            n_clusters: Number of style clusters (auto-detect if None)
            min_tracks: Minimum tracks required per cluster
            progress_callback: Optional callback(stage, progress_pct, message)

        Returns:
            Complete ReferenceProfile object
        """
        ref_path = Path(reference_dir)

        # Find audio files
        audio_files = self._find_audio_files(ref_path)
        if len(audio_files) < min_tracks:
            raise ValueError(
                f"Found only {len(audio_files)} tracks, need at least {min_tracks}"
            )

        self._log(f"Found {len(audio_files)} reference tracks")

        # Extract features from all tracks
        self._progress(progress_callback, 'extracting', 0, 'Extracting features...')
        features_dict_list = self._extract_all_features(audio_files, progress_callback)

        # Convert to feature matrix
        feature_names = PROFILE_FEATURES
        features_matrix, valid_indices = self._build_feature_matrix(
            features_dict_list, feature_names
        )

        self._log(f"Extracted features for {len(valid_indices)} tracks")

        # Compute statistics
        self._progress(progress_callback, 'statistics', 60, 'Computing statistics...')
        feature_stats = self._compute_all_statistics(features_matrix, feature_names)

        # Discover clusters
        self._progress(progress_callback, 'clustering', 70, 'Discovering style clusters...')
        clusters = discover_clusters(
            features_matrix,
            feature_names,
            feature_stats,
            n_clusters=n_clusters,
            min_clusters=2,
            max_clusters=6
        )

        self._log(f"Discovered {len(clusters)} style clusters")
        for c in clusters:
            self._log(f"  Cluster {c.cluster_id}: '{c.name}' ({c.track_count} tracks)")

        # Build track metadata
        self._progress(progress_callback, 'metadata', 85, 'Building metadata...')
        track_metadata = self._build_track_metadata(
            audio_files, features_dict_list, valid_indices, clusters
        )

        # Compute feature correlations
        self._progress(progress_callback, 'correlations', 90, 'Computing correlations...')
        correlations = np.corrcoef(features_matrix.T)

        # Create profile
        profile = ReferenceProfile(
            name=profile_name,
            created_date=datetime.now().isoformat(),
            track_count=len(valid_indices),
            feature_stats=feature_stats,
            clusters=clusters,
            feature_correlations=correlations,
            track_metadata=track_metadata
        )

        self._progress(progress_callback, 'complete', 100, 'Profile complete')

        return profile

    def _find_audio_files(self, directory: Path) -> List[Path]:
        """Find all audio files in directory."""
        extensions = {'.wav', '.flac', '.mp3', '.aiff', '.aif', '.ogg', '.m4a', '.aac'}
        files = []

        for ext in extensions:
            files.extend(directory.glob(f'*{ext}'))
            files.extend(directory.glob(f'*{ext.upper()}'))

        # Also search subdirectories
        for ext in extensions:
            files.extend(directory.glob(f'**/*{ext}'))
            files.extend(directory.glob(f'**/*{ext.upper()}'))

        # Remove duplicates and sort
        files = sorted(set(files))

        return files

    def _extract_all_features(
        self,
        audio_files: List[Path],
        progress_callback: Optional[Callable]
    ) -> List[Dict]:
        """Extract features from all audio files."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))

        from feature_extraction import extract_all_trance_features

        features_list = []
        n_files = len(audio_files)

        for i, audio_path in enumerate(audio_files):
            # Check cache
            cache_key = str(audio_path)
            if cache_key in self._feature_cache:
                features_list.append(self._feature_cache[cache_key])
                continue

            # Extract features
            try:
                features = extract_all_trance_features(str(audio_path))
                features_dict = features.to_dict()
                features_dict['_filename'] = audio_path.name
                features_dict['_path'] = str(audio_path)

                # Cache
                self._feature_cache[cache_key] = features_dict
                features_list.append(features_dict)

                self._log(f"  [{i+1}/{n_files}] Extracted: {audio_path.name}")

            except Exception as e:
                self._log(f"  [{i+1}/{n_files}] Failed: {audio_path.name} - {e}")
                features_list.append(None)

            # Progress
            pct = int(10 + 50 * (i + 1) / n_files)  # 10-60%
            self._progress(
                progress_callback, 'extracting', pct,
                f'Extracting {i+1}/{n_files}...'
            )

        return features_list

    def _build_feature_matrix(
        self,
        features_dict_list: List[Dict],
        feature_names: List[str]
    ) -> Tuple[np.ndarray, List[int]]:
        """Build feature matrix from feature dicts."""
        valid_features = []
        valid_indices = []

        for i, fd in enumerate(features_dict_list):
            if fd is None:
                continue

            # Extract features in order
            row = []
            valid = True
            for name in feature_names:
                if name in fd:
                    val = fd[name]
                    if val is None or (isinstance(val, float) and np.isnan(val)):
                        valid = False
                        break
                    row.append(float(val))
                else:
                    valid = False
                    break

            if valid:
                valid_features.append(row)
                valid_indices.append(i)

        return np.array(valid_features), valid_indices

    def _compute_all_statistics(
        self,
        features_matrix: np.ndarray,
        feature_names: List[str]
    ) -> Dict[str, FeatureStatistics]:
        """Compute statistics for all features."""
        stats = {}

        for i, name in enumerate(feature_names):
            values = features_matrix[:, i]
            method = FEATURE_RANGE_METHODS.get(name, 'iqr')
            stats[name] = compute_feature_statistics(values, method=method)

        return stats

    def _build_track_metadata(
        self,
        audio_files: List[Path],
        features_dict_list: List[Dict],
        valid_indices: List[int],
        clusters: List[StyleCluster]
    ) -> List[TrackInfo]:
        """Build track metadata list."""
        # Build cluster lookup
        cluster_lookup = {}
        for cluster in clusters:
            for idx in cluster.track_indices:
                cluster_lookup[idx] = cluster.cluster_id

        metadata = []
        for matrix_idx, original_idx in enumerate(valid_indices):
            fd = features_dict_list[original_idx]

            info = TrackInfo(
                index=matrix_idx,
                filename=fd.get('_filename', audio_files[original_idx].name),
                cluster=cluster_lookup.get(matrix_idx, 0),
                trance_score=fd.get('trance_score', 0.0),
                tempo=fd.get('tempo')
            )
            metadata.append(info)

        return metadata

    def _log(self, message: str):
        """Print log message if verbose."""
        if self.verbose:
            print(message, flush=True)

    def _progress(
        self,
        callback: Optional[Callable],
        stage: str,
        pct: int,
        message: str
    ):
        """Call progress callback if provided."""
        if callback:
            callback(stage, pct, message)

    def add_tracks_to_profile(
        self,
        profile: ReferenceProfile,
        new_tracks: List[str],
        progress_callback: Optional[Callable] = None
    ) -> ReferenceProfile:
        """
        Add new tracks to an existing profile and recompute statistics.

        Args:
            profile: Existing profile to extend
            new_tracks: List of new audio file paths
            progress_callback: Optional progress callback

        Returns:
            Updated profile
        """
        # This is a simplified version - full implementation would
        # properly merge feature matrices and recompute clusters
        raise NotImplementedError("Adding tracks to existing profile not yet implemented")


def validate_profile(profile: ReferenceProfile) -> List[str]:
    """
    Validate profile for common issues.

    Args:
        profile: Profile to validate

    Returns:
        List of warning messages (empty if profile is valid)
    """
    warnings = []

    # Check track count
    if profile.track_count < 50:
        warnings.append(
            f"Low track count ({profile.track_count}). "
            "Recommend 50+ tracks for reliable statistics."
        )

    # Check for zero-variance features
    for name, stats in profile.feature_stats.items():
        if stats.std == 0:
            warnings.append(f"Feature '{name}' has zero variance.")

    # Check cluster balance
    if profile.clusters:
        total = sum(c.track_count for c in profile.clusters)
        for cluster in profile.clusters:
            pct = 100 * cluster.track_count / total if total > 0 else 0
            if pct < 10:
                warnings.append(
                    f"Cluster '{cluster.name}' has only {pct:.1f}% of tracks. "
                    "May not be representative."
                )

    # Check for expected correlations
    if profile.feature_correlations is not None:
        # Example: tempo_score and is_trance_tempo should be correlated
        # This is simplified - real implementation would check specific pairs
        pass

    return warnings


def format_profile_info(profile: ReferenceProfile) -> str:
    """Format profile as human-readable summary."""
    lines = [
        f"Profile: {profile.name}",
        f"Created: {profile.created_date}",
        f"Tracks: {profile.track_count}",
        "",
        "Feature Ranges:",
    ]

    # Show key features
    key_features = [
        'tempo', 'pumping_modulation_depth_db', 'stereo_width',
        'energy_progression', 'trance_score'
    ]

    for feature in key_features:
        if feature in profile.feature_stats:
            stats = profile.feature_stats[feature]
            low, high = stats.acceptable_range
            lines.append(
                f"  {feature:25} {low:.2f} - {high:.2f} (mean: {stats.mean:.2f})"
            )

    # Show clusters
    lines.append("")
    lines.append("Clusters:")
    for cluster in profile.clusters:
        pct = 100 * cluster.track_count / profile.track_count
        lines.append(
            f"  [{cluster.cluster_id}] {cluster.name} "
            f"({cluster.track_count} tracks, {pct:.1f}%)"
        )

    return '\n'.join(lines)
