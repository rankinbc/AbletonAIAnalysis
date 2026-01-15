"""
Music Theory Module

Provides data structures and functions for musical key relationships,
harmonic analysis, and music theory calculations.
"""

from .key_relationships import (
    KEYS,
    MAJOR_KEYS,
    MINOR_KEYS,
    ALL_KEYS,
    CIRCLE_OF_FIFTHS,
    RELATIVE_MINOR,
    RELATIVE_MAJOR,
    COMMON_PROGRESSIONS,
    MODULATION_MAP,
    KEY_SIGNATURES,
    get_parallel_key,
    get_neighboring_keys,
    get_key_relationship_info,
)

__all__ = [
    'KEYS',
    'MAJOR_KEYS',
    'MINOR_KEYS',
    'ALL_KEYS',
    'CIRCLE_OF_FIFTHS',
    'RELATIVE_MINOR',
    'RELATIVE_MAJOR',
    'COMMON_PROGRESSIONS',
    'MODULATION_MAP',
    'KEY_SIGNATURES',
    'get_parallel_key',
    'get_neighboring_keys',
    'get_key_relationship_info',
]
