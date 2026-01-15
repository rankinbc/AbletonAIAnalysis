"""
Music Theory Key Relationships

This module provides data structures for musical key relationships
including the circle of fifths, relative minor/major keys, and neighboring keys.

Ported from ai-music-mix-analyzer with enhancements for the AbletonAIAnalysis project.
"""

from typing import Dict, List, Optional

# Basic key names (chromatic scale)
KEYS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
MAJOR_KEYS = KEYS.copy()
MINOR_KEYS = [k + 'm' for k in KEYS]
ALL_KEYS = MAJOR_KEYS + MINOR_KEYS

# Circle of fifths (clockwise from C)
CIRCLE_OF_FIFTHS = ['C', 'G', 'D', 'A', 'E', 'B', 'F#', 'C#', 'G#', 'D#', 'A#', 'F']

# Relative minor for each major key
RELATIVE_MINOR = {
    'C': 'Am',
    'G': 'Em',
    'D': 'Bm',
    'A': 'F#m',
    'E': 'C#m',
    'B': 'G#m',
    'F#': 'D#m',
    'C#': 'A#m',
    'G#': 'Fm',   # Enharmonic with Ab/Fm
    'D#': 'Cm',   # Enharmonic with Eb/Cm
    'A#': 'Gm',   # Enharmonic with Bb/Gm
    'F': 'Dm'
}

# Relative major for each minor key (reverse of RELATIVE_MINOR)
RELATIVE_MAJOR = {v: k for k, v in RELATIVE_MINOR.items()}

# Enharmonic equivalents for display purposes
ENHARMONIC_DISPLAY = {
    'C#': 'Db',
    'D#': 'Eb',
    'F#': 'Gb',
    'G#': 'Ab',
    'A#': 'Bb',
    'C#m': 'Dbm',
    'D#m': 'Ebm',
    'F#m': 'Gbm',
    'G#m': 'Abm',
    'A#m': 'Bbm',
}

# Common chord progressions by mode
COMMON_PROGRESSIONS = {
    'major': [
        ['I', 'IV', 'V'],           # Most basic progression
        ['I', 'vi', 'IV', 'V'],     # 50s progression
        ['I', 'V', 'vi', 'IV'],     # Popular modern progression
        ['ii', 'V', 'I'],           # Jazz progression
        ['I', 'IV', 'I', 'V'],      # Blues turnaround
        ['I', 'V', 'IV', 'I'],      # Common EDM progression
    ],
    'minor': [
        ['i', 'iv', 'V'],           # Minor with dominant V
        ['i', 'VI', 'VII'],         # Natural minor progression
        ['i', 'iv', 'v'],           # Natural minor progression
        ['i', 'VII', 'VI', 'V'],    # Descending progression (Andalusian cadence)
        ['i', 'v', 'VI', 'VII'],    # Ascending progression
        ['i', 'VI', 'III', 'VII'],  # Common trance progression
    ]
}

# Key modulation relationships
MODULATION_MAP = {
    # Closely related keys for modulation from a major key
    'major_modulations': {
        'dominant': lambda key: CIRCLE_OF_FIFTHS[(CIRCLE_OF_FIFTHS.index(key) + 1) % 12],
        'subdominant': lambda key: CIRCLE_OF_FIFTHS[(CIRCLE_OF_FIFTHS.index(key) - 1) % 12],
        'relative_minor': lambda key: RELATIVE_MINOR[key],
        'parallel_minor': lambda key: key + 'm',
        'dominant_of_relative': lambda key: get_neighboring_keys(RELATIVE_MINOR[key])[1],
        'supertonic_minor': lambda key: get_neighboring_keys(key)[1] + 'm'
    },
    # Closely related keys for modulation from a minor key
    'minor_modulations': {
        'relative_major': lambda key: RELATIVE_MAJOR[key],
        'dominant_minor': lambda key: get_neighboring_keys(key)[1],
        'subdominant_minor': lambda key: get_neighboring_keys(key)[0],
        'parallel_major': lambda key: key[:-1],  # Remove 'm'
        'mediant_major': lambda key: CIRCLE_OF_FIFTHS[(CIRCLE_OF_FIFTHS.index(RELATIVE_MAJOR[key]) + 4) % 12]
    }
}

# Key signatures (number of sharps/flats, positive = sharps, negative = flats)
KEY_SIGNATURES = {
    'C': 0,     # No sharps or flats
    'G': 1,     # 1 sharp
    'D': 2,     # 2 sharps
    'A': 3,     # 3 sharps
    'E': 4,     # 4 sharps
    'B': 5,     # 5 sharps
    'F#': 6,    # 6 sharps
    'C#': 7,    # 7 sharps
    'F': -1,    # 1 flat
    'A#': -2,   # 2 flats (Bb)
    'D#': -3,   # 3 flats (Eb)
    'G#': -4,   # 4 flats (Ab)
}

# Pitch class to note name mapping (for chromagram analysis)
PITCH_CLASS_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Major scale intervals (semitones from root)
MAJOR_SCALE_INTERVALS = [0, 2, 4, 5, 7, 9, 11]

# Minor scale intervals (semitones from root)
MINOR_SCALE_INTERVALS = [0, 2, 3, 5, 7, 8, 10]

# Harmonic minor scale intervals
HARMONIC_MINOR_INTERVALS = [0, 2, 3, 5, 7, 8, 11]


def get_parallel_key(key: str) -> str:
    """
    Get the parallel key (major to minor or minor to major).

    Args:
        key: A string representing the musical key (e.g., 'C', 'Am')

    Returns:
        The parallel key (same root, different mode)
    """
    if key.endswith('m'):
        return key[:-1]  # Remove 'm' to get parallel major
    else:
        return key + 'm'  # Add 'm' to get parallel minor


def get_neighboring_keys(key: str) -> List[str]:
    """
    Get the neighboring keys in the circle of fifths.
    (one step clockwise and counterclockwise)

    Args:
        key: A string representing the musical key (e.g., 'C', 'Am')

    Returns:
        A list of two keys: [counterclockwise, clockwise]
    """
    if key.endswith('m'):  # Minor key
        # For minor keys, use the relative major to navigate the circle
        relative_major = RELATIVE_MAJOR.get(key)
        if relative_major is None:
            return ['Unknown', 'Unknown']
        major_idx = CIRCLE_OF_FIFTHS.index(relative_major)

        cw_major = CIRCLE_OF_FIFTHS[(major_idx + 1) % 12]
        ccw_major = CIRCLE_OF_FIFTHS[(major_idx - 1) % 12]

        return [RELATIVE_MINOR.get(ccw_major, 'Unknown'),
                RELATIVE_MINOR.get(cw_major, 'Unknown')]
    else:  # Major key
        if key not in CIRCLE_OF_FIFTHS:
            return ['Unknown', 'Unknown']
        major_idx = CIRCLE_OF_FIFTHS.index(key)
        cw = CIRCLE_OF_FIFTHS[(major_idx + 1) % 12]
        ccw = CIRCLE_OF_FIFTHS[(major_idx - 1) % 12]
        return [ccw, cw]


def get_key_relationship_info(key: str) -> Dict:
    """
    Get comprehensive information about a key's relationships.

    Args:
        key: A string representing the musical key (e.g., 'C', 'Am')

    Returns:
        A dictionary containing key relationship information including:
        - type (major/minor)
        - root note
        - relative major/minor
        - parallel major/minor
        - neighboring keys
        - common progressions
        - modulation options
    """
    is_minor = key.endswith('m')

    if is_minor:
        root = key[:-1]
        relative_major = RELATIVE_MAJOR.get(key, "Unknown")
        parallel_major = root

        # Get neighboring keys in the circle of fifths
        neighbors = get_neighboring_keys(key)

        return {
            "key": key,
            "type": "minor",
            "root_note": root,
            "relative_major": relative_major,
            "parallel_major": parallel_major,
            "neighboring_keys": neighbors,
            "common_progressions": COMMON_PROGRESSIONS['minor'],
            "modulation_options": {
                "relative_major": RELATIVE_MAJOR.get(key, "Unknown"),
                "dominant_minor": neighbors[1] if len(neighbors) > 1 else "Unknown",
                "subdominant_minor": neighbors[0] if len(neighbors) > 0 else "Unknown",
                "parallel_major": root,
            },
            "compatible_keys": _get_compatible_keys(key)
        }
    else:
        # Major key
        relative_minor = RELATIVE_MINOR.get(key, "Unknown")
        parallel_minor = key + 'm'

        # Get neighboring keys in the circle of fifths
        neighbors = get_neighboring_keys(key)

        return {
            "key": key,
            "type": "major",
            "root_note": key,
            "relative_minor": relative_minor,
            "parallel_minor": parallel_minor,
            "neighboring_keys": neighbors,
            "common_progressions": COMMON_PROGRESSIONS['major'],
            "modulation_options": {
                "dominant": CIRCLE_OF_FIFTHS[(CIRCLE_OF_FIFTHS.index(key) + 1) % 12] if key in CIRCLE_OF_FIFTHS else "Unknown",
                "subdominant": CIRCLE_OF_FIFTHS[(CIRCLE_OF_FIFTHS.index(key) - 1) % 12] if key in CIRCLE_OF_FIFTHS else "Unknown",
                "relative_minor": relative_minor,
                "parallel_minor": parallel_minor,
            },
            "compatible_keys": _get_compatible_keys(key)
        }


def _get_compatible_keys(key: str) -> List[str]:
    """
    Get a list of keys that are harmonically compatible with the given key.
    Useful for DJ mixing and mashup creation.

    Args:
        key: A string representing the musical key

    Returns:
        A list of compatible keys for mixing
    """
    compatible = []

    is_minor = key.endswith('m')

    if is_minor:
        root = key[:-1]
        # Add the key itself
        compatible.append(key)
        # Add relative major
        if key in RELATIVE_MAJOR:
            compatible.append(RELATIVE_MAJOR[key])
        # Add parallel major
        compatible.append(root)
        # Add neighboring minor keys
        neighbors = get_neighboring_keys(key)
        compatible.extend([n for n in neighbors if n != 'Unknown'])
    else:
        # Major key
        # Add the key itself
        compatible.append(key)
        # Add relative minor
        if key in RELATIVE_MINOR:
            compatible.append(RELATIVE_MINOR[key])
        # Add parallel minor
        compatible.append(key + 'm')
        # Add neighboring major keys
        neighbors = get_neighboring_keys(key)
        compatible.extend([n for n in neighbors if n != 'Unknown'])

    # Remove duplicates while preserving order
    seen = set()
    result = []
    for k in compatible:
        if k not in seen:
            seen.add(k)
            result.append(k)

    return result


def key_to_pitch_class(key: str) -> int:
    """
    Convert a key name to its pitch class (0-11).

    Args:
        key: A string representing the musical key (e.g., 'C', 'Am', 'F#')

    Returns:
        An integer 0-11 representing the pitch class
    """
    root = key.rstrip('m')  # Remove 'm' suffix if present
    if root in KEYS:
        return KEYS.index(root)
    return 0  # Default to C if unknown


def pitch_class_to_key(pitch_class: int, is_minor: bool = False) -> str:
    """
    Convert a pitch class (0-11) to a key name.

    Args:
        pitch_class: An integer 0-11
        is_minor: If True, return the minor key name

    Returns:
        A string representing the key name
    """
    key = PITCH_CLASS_NAMES[pitch_class % 12]
    if is_minor:
        key += 'm'
    return key


def get_camelot_notation(key: str) -> str:
    """
    Convert a key to Camelot wheel notation (used by DJs).

    Args:
        key: A string representing the musical key

    Returns:
        A string in Camelot notation (e.g., '8A' for A minor, '11B' for G major)
    """
    # Camelot wheel mapping
    camelot_major = {
        'B': '1B', 'F#': '2B', 'C#': '3B', 'G#': '4B',
        'D#': '5B', 'A#': '6B', 'F': '7B', 'C': '8B',
        'G': '9B', 'D': '10B', 'A': '11B', 'E': '12B'
    }
    camelot_minor = {
        'G#m': '1A', 'D#m': '2A', 'A#m': '3A', 'Fm': '4A',
        'Cm': '5A', 'Gm': '6A', 'Dm': '7A', 'Am': '8A',
        'Em': '9A', 'Bm': '10A', 'F#m': '11A', 'C#m': '12A'
    }

    if key.endswith('m'):
        return camelot_minor.get(key, 'Unknown')
    else:
        return camelot_major.get(key, 'Unknown')


def get_open_key_notation(key: str) -> str:
    """
    Convert a key to Open Key notation (alternative to Camelot).

    Args:
        key: A string representing the musical key

    Returns:
        A string in Open Key notation (e.g., '5m' for A minor, '8d' for G major)
    """
    # Open Key mapping (d = major/dur, m = minor/moll)
    openkey_major = {
        'C': '1d', 'G': '2d', 'D': '3d', 'A': '4d',
        'E': '5d', 'B': '6d', 'F#': '7d', 'C#': '8d',
        'G#': '9d', 'D#': '10d', 'A#': '11d', 'F': '12d'
    }
    openkey_minor = {
        'Am': '1m', 'Em': '2m', 'Bm': '3m', 'F#m': '4m',
        'C#m': '5m', 'G#m': '6m', 'D#m': '7m', 'A#m': '8m',
        'Fm': '9m', 'Cm': '10m', 'Gm': '11m', 'Dm': '12m'
    }

    if key.endswith('m'):
        return openkey_minor.get(key, 'Unknown')
    else:
        return openkey_major.get(key, 'Unknown')
