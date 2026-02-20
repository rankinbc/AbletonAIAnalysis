"""
Embeddings Module.

Audio embedding extraction and similarity search for finding
tracks similar to reference profiles.
"""

from .openl3_extractor import (
    OpenL3Extractor,
    EmbeddingResult,
)
from .similarity_index import (
    SimilarityIndex,
    SimilarityResult,
)
from .embedding_utils import (
    normalize_embedding,
    aggregate_embeddings,
    compute_cosine_similarity,
)

__all__ = [
    # Extraction
    'OpenL3Extractor',
    'EmbeddingResult',
    # Indexing
    'SimilarityIndex',
    'SimilarityResult',
    # Utilities
    'normalize_embedding',
    'aggregate_embeddings',
    'compute_cosine_similarity',
]
