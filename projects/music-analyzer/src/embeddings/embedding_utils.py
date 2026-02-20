"""
Embedding Utilities Module.

Helper functions for working with audio embeddings.
"""

from typing import List, Optional, Tuple
import numpy as np


def normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    """
    L2 normalize an embedding vector.

    Args:
        embedding: Embedding vector or matrix

    Returns:
        Normalized embedding
    """
    embedding = np.asarray(embedding, dtype=np.float32)

    if embedding.ndim == 1:
        norm = np.linalg.norm(embedding)
        if norm > 0:
            return embedding / norm
        return embedding

    # Matrix case - normalize each row
    norms = np.linalg.norm(embedding, axis=1, keepdims=True)
    norms[norms == 0] = 1  # Avoid division by zero
    return embedding / norms


def aggregate_embeddings(
    embeddings: np.ndarray,
    method: str = "mean"
) -> np.ndarray:
    """
    Aggregate multiple embeddings into a single embedding.

    Args:
        embeddings: Embedding matrix (n_embeddings, dimension)
        method: Aggregation method
            - "mean": Average across embeddings
            - "max": Element-wise maximum
            - "weighted_mean": Weighted by norm (emphasizes stronger embeddings)

    Returns:
        Aggregated embedding vector
    """
    embeddings = np.asarray(embeddings, dtype=np.float32)

    if embeddings.ndim == 1:
        return embeddings

    if method == "mean":
        return np.mean(embeddings, axis=0)

    elif method == "max":
        return np.max(embeddings, axis=0)

    elif method == "weighted_mean":
        # Weight by L2 norm (emphasizes more "active" embeddings)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        weights = norms / (norms.sum() + 1e-8)
        return np.sum(embeddings * weights, axis=0)

    else:
        raise ValueError(f"Unknown aggregation method: {method}")


def compute_cosine_similarity(
    embedding1: np.ndarray,
    embedding2: np.ndarray
) -> float:
    """
    Compute cosine similarity between two embeddings.

    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector

    Returns:
        Cosine similarity (-1 to 1, higher is more similar)
    """
    e1 = np.asarray(embedding1, dtype=np.float32).flatten()
    e2 = np.asarray(embedding2, dtype=np.float32).flatten()

    norm1 = np.linalg.norm(e1)
    norm2 = np.linalg.norm(e2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(np.dot(e1, e2) / (norm1 * norm2))


def compute_euclidean_distance(
    embedding1: np.ndarray,
    embedding2: np.ndarray
) -> float:
    """
    Compute Euclidean (L2) distance between two embeddings.

    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector

    Returns:
        Euclidean distance (lower is more similar)
    """
    e1 = np.asarray(embedding1, dtype=np.float32).flatten()
    e2 = np.asarray(embedding2, dtype=np.float32).flatten()

    return float(np.linalg.norm(e1 - e2))


def distance_to_similarity(
    distance: float,
    method: str = "inverse"
) -> float:
    """
    Convert distance to similarity score.

    Args:
        distance: Distance value (lower = more similar)
        method: Conversion method
            - "inverse": 1 / (1 + distance)
            - "exp": exp(-distance)
            - "sigmoid": 1 / (1 + exp(distance - 1))

    Returns:
        Similarity score (0 to 1, higher = more similar)
    """
    if method == "inverse":
        return 1.0 / (1.0 + distance)

    elif method == "exp":
        return float(np.exp(-distance))

    elif method == "sigmoid":
        return 1.0 / (1.0 + np.exp(distance - 1))

    else:
        raise ValueError(f"Unknown conversion method: {method}")


def compute_centroid(embeddings: np.ndarray) -> np.ndarray:
    """
    Compute centroid (mean) of a set of embeddings.

    Args:
        embeddings: Embedding matrix (n_embeddings, dimension)

    Returns:
        Centroid embedding vector
    """
    embeddings = np.asarray(embeddings, dtype=np.float32)
    if embeddings.ndim == 1:
        return embeddings
    return np.mean(embeddings, axis=0)


def compute_embedding_variance(embeddings: np.ndarray) -> float:
    """
    Compute variance of embeddings around their centroid.

    Useful for measuring how diverse a set of embeddings is.

    Args:
        embeddings: Embedding matrix

    Returns:
        Average squared distance from centroid
    """
    embeddings = np.asarray(embeddings, dtype=np.float32)
    if embeddings.ndim == 1:
        return 0.0

    centroid = compute_centroid(embeddings)
    distances = np.linalg.norm(embeddings - centroid, axis=1)
    return float(np.mean(distances ** 2))


def pca_reduce(
    embeddings: np.ndarray,
    n_components: int = 128
) -> np.ndarray:
    """
    Reduce embedding dimensionality using PCA.

    Args:
        embeddings: Embedding matrix (n_embeddings, dimension)
        n_components: Target dimension

    Returns:
        Reduced embedding matrix
    """
    try:
        from sklearn.decomposition import PCA
    except ImportError:
        raise ImportError("scikit-learn required for PCA. Install with: pip install scikit-learn")

    embeddings = np.asarray(embeddings, dtype=np.float32)

    if embeddings.ndim == 1:
        embeddings = embeddings.reshape(1, -1)

    if embeddings.shape[1] <= n_components:
        return embeddings

    pca = PCA(n_components=n_components)
    return pca.fit_transform(embeddings)


def find_outliers(
    embeddings: np.ndarray,
    threshold: float = 2.0
) -> List[int]:
    """
    Find outlier embeddings using distance from centroid.

    Args:
        embeddings: Embedding matrix
        threshold: Number of standard deviations for outlier threshold

    Returns:
        List of outlier indices
    """
    embeddings = np.asarray(embeddings, dtype=np.float32)
    if embeddings.ndim == 1:
        return []

    centroid = compute_centroid(embeddings)
    distances = np.linalg.norm(embeddings - centroid, axis=1)

    mean_dist = np.mean(distances)
    std_dist = np.std(distances)

    outlier_threshold = mean_dist + threshold * std_dist
    outlier_indices = np.where(distances > outlier_threshold)[0]

    return outlier_indices.tolist()


def interpolate_embeddings(
    embedding1: np.ndarray,
    embedding2: np.ndarray,
    alpha: float = 0.5
) -> np.ndarray:
    """
    Linearly interpolate between two embeddings.

    Args:
        embedding1: First embedding
        embedding2: Second embedding
        alpha: Interpolation factor (0 = embedding1, 1 = embedding2)

    Returns:
        Interpolated embedding
    """
    e1 = np.asarray(embedding1, dtype=np.float32)
    e2 = np.asarray(embedding2, dtype=np.float32)

    return (1 - alpha) * e1 + alpha * e2


def batch_cosine_similarity(
    query: np.ndarray,
    embeddings: np.ndarray
) -> np.ndarray:
    """
    Compute cosine similarity between a query and multiple embeddings.

    Args:
        query: Query embedding vector
        embeddings: Embedding matrix (n_embeddings, dimension)

    Returns:
        Array of similarity scores
    """
    query = np.asarray(query, dtype=np.float32).flatten()
    embeddings = np.asarray(embeddings, dtype=np.float32)

    if embeddings.ndim == 1:
        embeddings = embeddings.reshape(1, -1)

    # Normalize query
    query_norm = query / (np.linalg.norm(query) + 1e-8)

    # Normalize embeddings
    emb_norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    emb_normalized = embeddings / (emb_norms + 1e-8)

    # Compute similarities
    similarities = np.dot(emb_normalized, query_norm)

    return similarities


def cluster_embeddings(
    embeddings: np.ndarray,
    n_clusters: int = 5,
    method: str = "kmeans"
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Cluster embeddings into groups.

    Args:
        embeddings: Embedding matrix
        n_clusters: Number of clusters
        method: Clustering method ("kmeans" or "agglomerative")

    Returns:
        Tuple of (cluster_labels, cluster_centers)
    """
    try:
        from sklearn.cluster import KMeans, AgglomerativeClustering
    except ImportError:
        raise ImportError("scikit-learn required for clustering")

    embeddings = np.asarray(embeddings, dtype=np.float32)

    if method == "kmeans":
        clusterer = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = clusterer.fit_predict(embeddings)
        centers = clusterer.cluster_centers_
        return labels, centers

    elif method == "agglomerative":
        clusterer = AgglomerativeClustering(n_clusters=n_clusters)
        labels = clusterer.fit_predict(embeddings)
        # Compute centers manually
        centers = np.array([
            embeddings[labels == i].mean(axis=0)
            for i in range(n_clusters)
        ])
        return labels, centers

    else:
        raise ValueError(f"Unknown clustering method: {method}")
