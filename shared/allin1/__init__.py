"""
Shared allin1 Docker service for AbletonAIAnalysis.

This module provides a Docker-based wrapper for the allin1 music structure
analyzer, avoiding Python 3.13 compatibility issues with madmom/natten.

Usage:
    from shared.allin1 import DockerAllin1, Allin1Result

    # Without caching (recommended for music-analyzer)
    analyzer = DockerAllin1()
    result = analyzer.analyze("song.wav")

    # With caching (recommended for youtube-analyzer batch processing)
    analyzer = DockerAllin1(
        enable_cache=True,
        cache_dir=Path("~/.cache/allin1")
    )
    result = analyzer.analyze("song.wav")

    # With GPU support
    analyzer = DockerAllin1(use_gpu=True)
"""

from .docker_allin1 import (
    DockerAllin1,
    Allin1Result,
    Allin1Segment,
    is_docker_available,
    is_allin1_image_available,
)
from .cache import Allin1Cache

__all__ = [
    'DockerAllin1',
    'Allin1Result',
    'Allin1Segment',
    'Allin1Cache',
    'is_docker_available',
    'is_allin1_image_available',
]

__version__ = '1.0.0'
