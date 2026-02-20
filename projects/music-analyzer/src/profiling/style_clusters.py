"""
Style Clustering Module.

Discover sub-styles within reference collection using clustering algorithms.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass

from .profile_storage import StyleCluster, FeatureStatistics


def normalize_features(
    features: np.ndarray,
    method: str = "robust"
) -> Tuple[np.ndarray, Dict]:
    """
    Normalize features for clustering.

    Args:
        features: 2D array (n_tracks, n_features)
        method: "robust" (median/IQR), "standard" (mean/std), or "minmax"

    Returns:
        (normalized_features, scaler_params)
    """
    features = np.asarray(features)

    if method == "robust":
        # Robust scaling using median and IQR
        median = np.median(features, axis=0)
        q25 = np.percentile(features, 25, axis=0)
        q75 = np.percentile(features, 75, axis=0)
        iqr = q75 - q25
        iqr[iqr == 0] = 1.0  # Avoid division by zero

        normalized = (features - median) / iqr
        scaler_params = {'method': 'robust', 'center': median, 'scale': iqr}

    elif method == "standard":
        # Standard z-score normalization
        mean = np.mean(features, axis=0)
        std = np.std(features, axis=0)
        std[std == 0] = 1.0

        normalized = (features - mean) / std
        scaler_params = {'method': 'standard', 'center': mean, 'scale': std}

    else:  # minmax
        min_val = np.min(features, axis=0)
        max_val = np.max(features, axis=0)
        range_val = max_val - min_val
        range_val[range_val == 0] = 1.0

        normalized = (features - min_val) / range_val
        scaler_params = {'method': 'minmax', 'min': min_val, 'max': max_val}

    return normalized, scaler_params


def detect_optimal_clusters(
    features_normalized: np.ndarray,
    min_clusters: int = 2,
    max_clusters: int = 8
) -> int:
    """
    Determine optimal number of clusters using silhouette score.

    Args:
        features_normalized: Normalized feature matrix
        min_clusters: Minimum clusters to try
        max_clusters: Maximum clusters to try

    Returns:
        Recommended number of clusters
    """
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    n_samples = features_normalized.shape[0]
    max_clusters = min(max_clusters, n_samples - 1)

    if max_clusters < min_clusters:
        return min_clusters

    best_score = -1
    best_k = min_clusters

    for k in range(min_clusters, max_clusters + 1):
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(features_normalized)

        # Need at least 2 samples per cluster for silhouette
        unique_labels = np.unique(labels)
        if len(unique_labels) < 2:
            continue

        score = silhouette_score(features_normalized, labels)

        if score > best_score:
            best_score = score
            best_k = k

    return best_k


def cluster_references(
    features_normalized: np.ndarray,
    n_clusters: int,
    method: str = "kmeans",
    random_state: int = 42
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Cluster reference tracks by style similarity.

    Args:
        features_normalized: Normalized feature matrix (n_tracks, n_features)
        n_clusters: Number of clusters
        method: "kmeans", "hierarchical", or "gmm"
        random_state: Random seed for reproducibility

    Returns:
        (cluster_labels, cluster_centers)
    """
    if method == "kmeans":
        from sklearn.cluster import KMeans
        model = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
        labels = model.fit_predict(features_normalized)
        centers = model.cluster_centers_

    elif method == "hierarchical":
        from sklearn.cluster import AgglomerativeClustering
        model = AgglomerativeClustering(n_clusters=n_clusters, linkage='ward')
        labels = model.fit_predict(features_normalized)

        # Compute centers manually
        centers = np.zeros((n_clusters, features_normalized.shape[1]))
        for i in range(n_clusters):
            mask = labels == i
            if mask.sum() > 0:
                centers[i] = features_normalized[mask].mean(axis=0)

    elif method == "gmm":
        from sklearn.mixture import GaussianMixture
        model = GaussianMixture(n_components=n_clusters, random_state=random_state)
        labels = model.fit_predict(features_normalized)
        centers = model.means_

    else:
        raise ValueError(f"Unknown clustering method: {method}")

    return labels, centers


def find_exemplar_tracks(
    features_normalized: np.ndarray,
    labels: np.ndarray,
    centers: np.ndarray,
    n_exemplars: int = 3
) -> Dict[int, List[int]]:
    """
    Find tracks closest to each cluster centroid.

    Args:
        features_normalized: Normalized feature matrix
        labels: Cluster labels for each track
        centers: Cluster centroids
        n_exemplars: Number of exemplar tracks per cluster

    Returns:
        Dict mapping cluster_id -> list of track indices
    """
    n_clusters = len(centers)
    exemplars = {}

    for cluster_id in range(n_clusters):
        mask = labels == cluster_id
        cluster_indices = np.where(mask)[0]

        if len(cluster_indices) == 0:
            exemplars[cluster_id] = []
            continue

        # Calculate distance to centroid
        cluster_features = features_normalized[mask]
        centroid = centers[cluster_id]
        distances = np.linalg.norm(cluster_features - centroid, axis=1)

        # Get indices of closest tracks
        sorted_idx = np.argsort(distances)
        n_to_select = min(n_exemplars, len(sorted_idx))
        exemplar_idx = cluster_indices[sorted_idx[:n_to_select]]
        exemplars[cluster_id] = exemplar_idx.tolist()

    return exemplars


def characterize_cluster(
    cluster_features: np.ndarray,
    all_features: np.ndarray,
    feature_names: List[str],
    global_stats: Dict[str, FeatureStatistics],
    threshold_std: float = 0.5
) -> Dict:
    """
    Identify what makes a cluster distinctive.

    Args:
        cluster_features: Features for tracks in this cluster
        all_features: Features for all tracks
        feature_names: Names of features
        global_stats: Global statistics for each feature
        threshold_std: Min std deviation to be considered distinctive

    Returns:
        {
            'distinctive_features': List of features that distinguish cluster
            'feature_deviations': Dict of feature -> deviation from global mean
            'suggested_name': Auto-generated cluster name
        }
    """
    cluster_means = np.mean(cluster_features, axis=0)

    deviations = {}
    distinctive = []

    for i, name in enumerate(feature_names):
        if name not in global_stats:
            continue

        stats = global_stats[name]
        if stats.std == 0:
            continue

        # Calculate deviation in standard deviations
        dev = (cluster_means[i] - stats.mean) / stats.std
        deviations[name] = float(dev)

        if abs(dev) >= threshold_std:
            distinctive.append((name, dev))

    # Sort by absolute deviation
    distinctive.sort(key=lambda x: abs(x[1]), reverse=True)
    distinctive_names = [f[0] for f in distinctive[:5]]  # Top 5

    # Generate suggested name based on distinctive features
    suggested_name = _generate_cluster_name(distinctive)

    return {
        'distinctive_features': distinctive_names,
        'feature_deviations': deviations,
        'suggested_name': suggested_name
    }


def _generate_cluster_name(distinctive_features: List[Tuple[str, float]]) -> str:
    """Generate a cluster name based on distinctive features."""
    if not distinctive_features:
        return "Balanced"

    # Map features to descriptive terms
    feature_terms = {
        'tempo': ('Fast', 'Slow'),
        'tempo_score': ('Trance Tempo', 'Unusual Tempo'),
        'pumping_score': ('Heavy Sidechain', 'Light Sidechain'),
        'modulation_depth_db': ('Heavy Pumping', 'Subtle Pumping'),
        'energy_progression': ('High Energy', 'Mellow'),
        'energy_range': ('Dynamic', 'Consistent'),
        'four_on_floor_score': ('4/4 Kicks', 'Varied Rhythm'),
        'supersaw_score': ('Wide Stereo', 'Narrow'),
        'stereo_width': ('Wide', 'Mono'),
        'acid_303_score': ('Acid', 'Clean'),
        'offbeat_hihat_score': ('Driving Hats', 'Minimal Hats'),
        'spectral_brightness': ('Bright', 'Dark'),
    }

    parts = []
    for feature, deviation in distinctive_features[:2]:  # Use top 2
        if feature in feature_terms:
            if deviation > 0:
                parts.append(feature_terms[feature][0])
            else:
                parts.append(feature_terms[feature][1])

    if not parts:
        return "Standard"

    return " ".join(parts)


def discover_clusters(
    features: np.ndarray,
    feature_names: List[str],
    global_stats: Dict[str, FeatureStatistics],
    n_clusters: Optional[int] = None,
    method: str = "kmeans",
    min_clusters: int = 2,
    max_clusters: int = 6
) -> List[StyleCluster]:
    """
    Discover style clusters in the reference collection.

    Args:
        features: Feature matrix (n_tracks, n_features)
        feature_names: List of feature names
        global_stats: Global statistics for each feature
        n_clusters: Number of clusters (auto-detect if None)
        method: Clustering method
        min_clusters: Min clusters for auto-detection
        max_clusters: Max clusters for auto-detection

    Returns:
        List of StyleCluster objects
    """
    # Normalize features
    features_normalized, _ = normalize_features(features, method="robust")

    # Determine number of clusters
    if n_clusters is None:
        n_clusters = detect_optimal_clusters(
            features_normalized, min_clusters, max_clusters
        )

    # Cluster
    labels, centers = cluster_references(features_normalized, n_clusters, method)

    # Find exemplars
    exemplars = find_exemplar_tracks(features_normalized, labels, centers)

    # Build cluster objects
    clusters = []
    for cluster_id in range(n_clusters):
        mask = labels == cluster_id
        cluster_indices = np.where(mask)[0].tolist()

        if len(cluster_indices) == 0:
            continue

        cluster_features = features[mask]

        # Characterize
        char = characterize_cluster(
            cluster_features, features, feature_names, global_stats
        )

        # Compute centroid and variance in original (unnormalized) space
        centroid = {
            feature_names[i]: float(np.mean(cluster_features[:, i]))
            for i in range(len(feature_names))
        }
        variance = {
            feature_names[i]: float(np.var(cluster_features[:, i]))
            for i in range(len(feature_names))
        }

        cluster = StyleCluster(
            cluster_id=cluster_id,
            name=char['suggested_name'],
            track_indices=cluster_indices,
            centroid=centroid,
            variance=variance,
            distinctive_features=char['distinctive_features'],
            exemplar_tracks=exemplars.get(cluster_id, [])
        )
        clusters.append(cluster)

    return clusters
