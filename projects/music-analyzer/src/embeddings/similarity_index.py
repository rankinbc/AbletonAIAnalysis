"""
Similarity Index Module.

FAISS-based similarity search index for finding similar audio tracks
based on their embeddings.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import json
import numpy as np
import warnings


@dataclass
class SimilarityResult:
    """Result of a similarity search."""
    track_id: str
    distance: float  # Lower is more similar (L2 distance)
    similarity: float  # 0-1, higher is more similar
    rank: int  # 1 = most similar
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            'track_id': self.track_id,
            'distance': float(self.distance),
            'similarity': float(self.similarity),
            'rank': self.rank,
            'metadata': self.metadata
        }


class SimilarityIndex:
    """
    FAISS-based similarity search index.

    Stores embeddings and enables fast nearest-neighbor search
    to find similar tracks.

    Usage:
        index = SimilarityIndex(dimension=512)
        index.add(embedding1, "track_1")
        index.add(embedding2, "track_2")

        results = index.search(query_embedding, k=5)
        for result in results:
            print(f"{result.track_id}: similarity={result.similarity:.3f}")
    """

    def __init__(
        self,
        dimension: int = 512,
        index_type: str = "flat",
        metric: str = "l2",
        use_gpu: bool = False
    ):
        """
        Initialize similarity index.

        Args:
            dimension: Embedding dimension (512 or 6144 for OpenL3)
            index_type: Index type
                - "flat": Exact search (slow for large datasets)
                - "hnsw": Approximate search (fast, good for >10k items)
                - "ivf": Inverted file index (requires training)
            metric: Distance metric ("l2" or "cosine")
            use_gpu: Use GPU acceleration if available
        """
        self.dimension = dimension
        self.index_type = index_type
        self.metric = metric
        self.use_gpu = use_gpu

        # Track ID to index mapping
        self._track_ids: List[str] = []
        self._id_to_index: Dict[str, int] = {}

        # Metadata storage
        self._metadata: Dict[str, Dict[str, Any]] = {}

        # FAISS index (lazily initialized)
        self._index = None
        self._faiss_available = None

    def _check_faiss_available(self) -> bool:
        """Check if FAISS is available."""
        if self._faiss_available is None:
            try:
                import faiss
                self._faiss_available = True
            except ImportError:
                self._faiss_available = False
        return self._faiss_available

    def _init_index(self):
        """Initialize the FAISS index."""
        if self._index is not None:
            return

        if not self._check_faiss_available():
            raise ImportError(
                "FAISS is not installed. Install with: pip install faiss-cpu\n"
                "For GPU support: pip install faiss-gpu"
            )

        import faiss

        # Create base index based on type
        if self.index_type == "flat":
            if self.metric == "cosine":
                # Normalize vectors and use L2 (equivalent to cosine)
                self._index = faiss.IndexFlatIP(self.dimension)  # Inner product
            else:
                self._index = faiss.IndexFlatL2(self.dimension)

        elif self.index_type == "hnsw":
            # HNSW is approximate but very fast
            # M = 32 is a good default
            self._index = faiss.IndexHNSWFlat(self.dimension, 32)
            self._index.hnsw.efConstruction = 40
            self._index.hnsw.efSearch = 16

        elif self.index_type == "ivf":
            # IVF requires training - will need separate setup
            # Use IVF with flat quantizer
            nlist = 100  # Number of clusters
            quantizer = faiss.IndexFlatL2(self.dimension)
            self._index = faiss.IndexIVFFlat(quantizer, self.dimension, nlist)
            self._needs_training = True

        else:
            raise ValueError(f"Unknown index_type: {self.index_type}")

        # GPU support
        if self.use_gpu:
            try:
                res = faiss.StandardGpuResources()
                self._index = faiss.index_cpu_to_gpu(res, 0, self._index)
            except Exception as e:
                warnings.warn(f"GPU not available, using CPU: {e}")

    @property
    def size(self) -> int:
        """Number of embeddings in index."""
        return len(self._track_ids)

    def add(
        self,
        embedding: np.ndarray,
        track_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Add embedding to index.

        Args:
            embedding: Embedding vector (must match dimension)
            track_id: Unique identifier for the track
            metadata: Optional metadata to store with track
        """
        self._init_index()

        # Validate embedding
        embedding = np.asarray(embedding, dtype=np.float32)
        if embedding.ndim == 1:
            embedding = embedding.reshape(1, -1)

        if embedding.shape[1] != self.dimension:
            raise ValueError(
                f"Embedding dimension {embedding.shape[1]} doesn't match "
                f"index dimension {self.dimension}"
            )

        # Normalize for cosine similarity
        if self.metric == "cosine":
            norm = np.linalg.norm(embedding, axis=1, keepdims=True)
            embedding = embedding / (norm + 1e-8)

        # Add to index
        self._index.add(embedding)

        # Track mapping
        index = len(self._track_ids)
        self._track_ids.append(track_id)
        self._id_to_index[track_id] = index

        # Store metadata
        if metadata:
            self._metadata[track_id] = metadata

    def add_batch(
        self,
        embeddings: np.ndarray,
        track_ids: List[str],
        metadata_list: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Add multiple embeddings to index.

        Args:
            embeddings: Embedding matrix (n_tracks, dimension)
            track_ids: List of track IDs
            metadata_list: Optional list of metadata dicts
        """
        self._init_index()

        embeddings = np.asarray(embeddings, dtype=np.float32)
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)

        if len(track_ids) != embeddings.shape[0]:
            raise ValueError("Number of track_ids must match number of embeddings")

        # Normalize for cosine similarity
        if self.metric == "cosine":
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / (norms + 1e-8)

        # Add to index
        self._index.add(embeddings)

        # Track mappings
        start_index = len(self._track_ids)
        for i, track_id in enumerate(track_ids):
            self._track_ids.append(track_id)
            self._id_to_index[track_id] = start_index + i

            if metadata_list and i < len(metadata_list):
                self._metadata[track_id] = metadata_list[i]

    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
        exclude_ids: Optional[List[str]] = None
    ) -> List[SimilarityResult]:
        """
        Find k most similar tracks.

        Args:
            query_embedding: Query embedding vector
            k: Number of results to return
            exclude_ids: Track IDs to exclude from results

        Returns:
            List of SimilarityResult sorted by similarity (highest first)
        """
        if self._index is None or self.size == 0:
            return []

        query = np.asarray(query_embedding, dtype=np.float32)
        if query.ndim == 1:
            query = query.reshape(1, -1)

        # Normalize for cosine similarity
        if self.metric == "cosine":
            norm = np.linalg.norm(query, axis=1, keepdims=True)
            query = query / (norm + 1e-8)

        # Search for more results if we need to exclude some
        search_k = k
        if exclude_ids:
            search_k = min(k + len(exclude_ids), self.size)

        # FAISS search
        distances, indices = self._index.search(query, search_k)

        # Build results
        results = []
        for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx < 0 or idx >= len(self._track_ids):
                continue

            track_id = self._track_ids[idx]

            # Skip excluded IDs
            if exclude_ids and track_id in exclude_ids:
                continue

            # Convert distance to similarity
            if self.metric == "cosine":
                # For inner product, higher is more similar
                similarity = float(dist)
            else:
                # For L2, lower distance is more similar
                # Convert to 0-1 similarity
                similarity = 1.0 / (1.0 + float(dist))

            results.append(SimilarityResult(
                track_id=track_id,
                distance=float(dist),
                similarity=similarity,
                rank=len(results) + 1,
                metadata=self._metadata.get(track_id)
            ))

            if len(results) >= k:
                break

        return results

    def get_embedding(self, track_id: str) -> Optional[np.ndarray]:
        """
        Retrieve embedding for a track.

        Args:
            track_id: Track identifier

        Returns:
            Embedding vector or None if not found
        """
        if track_id not in self._id_to_index:
            return None

        if self._index is None:
            return None

        idx = self._id_to_index[track_id]

        # Reconstruct from index
        import faiss
        embedding = self._index.reconstruct(idx)
        return embedding

    def remove(self, track_id: str) -> bool:
        """
        Remove a track from the index.

        Note: FAISS doesn't support efficient removal for all index types.
        For flat indices, this rebuilds the index.

        Args:
            track_id: Track to remove

        Returns:
            True if removed, False if not found
        """
        if track_id not in self._id_to_index:
            return False

        # For simple removal, rebuild the index without this track
        # This is inefficient but works for all index types
        if self._index is None:
            return False

        idx = self._id_to_index[track_id]

        # Get all embeddings except the one to remove
        embeddings = []
        new_track_ids = []

        for i, tid in enumerate(self._track_ids):
            if tid != track_id:
                emb = self._index.reconstruct(i)
                embeddings.append(emb)
                new_track_ids.append(tid)

        # Reset index
        self._track_ids = []
        self._id_to_index = {}
        old_metadata = self._metadata
        self._metadata = {}
        self._index = None

        # Re-add all except removed
        if embeddings:
            metadata_list = [old_metadata.get(tid) for tid in new_track_ids]
            self.add_batch(
                np.array(embeddings),
                new_track_ids,
                metadata_list
            )

        return True

    def save(self, path: str):
        """
        Save index to disk.

        Args:
            path: Output directory path
        """
        if self._index is None:
            raise ValueError("Index is empty, nothing to save")

        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        import faiss

        # Save FAISS index
        index_path = path / "index.faiss"

        # Convert GPU index to CPU for saving
        if self.use_gpu:
            cpu_index = faiss.index_gpu_to_cpu(self._index)
            faiss.write_index(cpu_index, str(index_path))
        else:
            faiss.write_index(self._index, str(index_path))

        # Save metadata
        meta = {
            'dimension': self.dimension,
            'index_type': self.index_type,
            'metric': self.metric,
            'track_ids': self._track_ids,
            'metadata': self._metadata
        }

        meta_path = path / "metadata.json"
        with open(meta_path, 'w') as f:
            json.dump(meta, f, indent=2)

    def load(self, path: str):
        """
        Load index from disk.

        Args:
            path: Directory path containing saved index
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Index path not found: {path}")

        import faiss

        # Load FAISS index
        index_path = path / "index.faiss"
        if not index_path.exists():
            raise FileNotFoundError(f"Index file not found: {index_path}")

        self._index = faiss.read_index(str(index_path))

        # Move to GPU if requested
        if self.use_gpu:
            try:
                res = faiss.StandardGpuResources()
                self._index = faiss.index_cpu_to_gpu(res, 0, self._index)
            except Exception as e:
                warnings.warn(f"GPU not available, using CPU: {e}")

        # Load metadata
        meta_path = path / "metadata.json"
        if meta_path.exists():
            with open(meta_path, 'r') as f:
                meta = json.load(f)

            self.dimension = meta.get('dimension', self.dimension)
            self.index_type = meta.get('index_type', self.index_type)
            self.metric = meta.get('metric', self.metric)
            self._track_ids = meta.get('track_ids', [])
            self._metadata = meta.get('metadata', {})

            # Rebuild ID mapping
            self._id_to_index = {
                tid: i for i, tid in enumerate(self._track_ids)
            }

    def get_all_track_ids(self) -> List[str]:
        """Get all track IDs in the index."""
        return self._track_ids.copy()

    def get_metadata(self, track_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a track."""
        return self._metadata.get(track_id)

    def set_metadata(self, track_id: str, metadata: Dict[str, Any]):
        """Set metadata for a track."""
        if track_id in self._id_to_index:
            self._metadata[track_id] = metadata


class MockSimilarityIndex:
    """
    Mock index for testing when FAISS is not available.

    Uses brute-force numpy operations.
    """

    def __init__(self, dimension: int = 512, **kwargs):
        self.dimension = dimension
        self._embeddings: List[np.ndarray] = []
        self._track_ids: List[str] = []
        self._metadata: Dict[str, Dict] = {}

    @property
    def size(self) -> int:
        return len(self._track_ids)

    def add(self, embedding: np.ndarray, track_id: str, metadata: Optional[Dict] = None):
        embedding = np.asarray(embedding, dtype=np.float32).flatten()
        self._embeddings.append(embedding)
        self._track_ids.append(track_id)
        if metadata:
            self._metadata[track_id] = metadata

    def add_batch(self, embeddings: np.ndarray, track_ids: List[str],
                  metadata_list: Optional[List[Dict]] = None):
        for i, (emb, tid) in enumerate(zip(embeddings, track_ids)):
            meta = metadata_list[i] if metadata_list and i < len(metadata_list) else None
            self.add(emb, tid, meta)

    def search(self, query_embedding: np.ndarray, k: int = 5,
               exclude_ids: Optional[List[str]] = None) -> List[SimilarityResult]:
        if not self._embeddings:
            return []

        query = np.asarray(query_embedding, dtype=np.float32).flatten()
        query = query / (np.linalg.norm(query) + 1e-8)

        # Compute all distances
        distances = []
        for emb in self._embeddings:
            emb_norm = emb / (np.linalg.norm(emb) + 1e-8)
            dist = np.linalg.norm(query - emb_norm)
            distances.append(dist)

        # Sort by distance
        indices = np.argsort(distances)

        results = []
        for idx in indices:
            track_id = self._track_ids[idx]
            if exclude_ids and track_id in exclude_ids:
                continue

            dist = distances[idx]
            similarity = 1.0 / (1.0 + dist)

            results.append(SimilarityResult(
                track_id=track_id,
                distance=float(dist),
                similarity=float(similarity),
                rank=len(results) + 1,
                metadata=self._metadata.get(track_id)
            ))

            if len(results) >= k:
                break

        return results

    def save(self, path: str):
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        data = {
            'dimension': self.dimension,
            'embeddings': [e.tolist() for e in self._embeddings],
            'track_ids': self._track_ids,
            'metadata': self._metadata
        }

        with open(path / "mock_index.json", 'w') as f:
            json.dump(data, f)

    def load(self, path: str):
        with open(Path(path) / "mock_index.json", 'r') as f:
            data = json.load(f)

        self.dimension = data['dimension']
        self._embeddings = [np.array(e) for e in data['embeddings']]
        self._track_ids = data['track_ids']
        self._metadata = data['metadata']


def get_similarity_index(
    use_mock: bool = False,
    **kwargs
) -> SimilarityIndex:
    """
    Get a similarity index instance.

    Args:
        use_mock: If True, return mock index
        **kwargs: Arguments passed to index

    Returns:
        SimilarityIndex or MockSimilarityIndex
    """
    if use_mock:
        return MockSimilarityIndex(**kwargs)

    try:
        return SimilarityIndex(**kwargs)
    except ImportError:
        warnings.warn(
            "FAISS not available, using mock index. "
            "Install with: pip install faiss-cpu"
        )
        return MockSimilarityIndex(**kwargs)
