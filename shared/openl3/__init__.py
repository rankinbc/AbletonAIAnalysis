"""
OpenL3 Docker wrapper module.

Provides OpenL3 audio embeddings via Docker container,
avoiding Python 3.13 compatibility issues.
"""

from .docker_openl3 import (
    DockerOpenL3Extractor,
    EmbeddingResult,
    is_docker_available,
    is_openl3_image_available
)

__all__ = [
    'DockerOpenL3Extractor',
    'EmbeddingResult',
    'is_docker_available',
    'is_openl3_image_available'
]
