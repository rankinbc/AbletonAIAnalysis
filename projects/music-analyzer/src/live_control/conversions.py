"""
Value Conversions for Live DAW Control.

Converts human-readable values (Hz, dB, ms, %) to normalized 0.0-1.0 values
used by Ableton's MCP/OSC interface, and vice versa.

All Ableton parameters use normalized 0.0-1.0 values internally.
These functions handle the conversion between human-readable and normalized values.
"""

import math
from typing import Tuple, Optional
from dataclasses import dataclass


# =============================================================================
# EQ Frequency Conversion (Logarithmic Scale)
# =============================================================================

# EQ Eight frequency range
EQ_FREQ_MIN = 10.0      # 10 Hz
EQ_FREQ_MAX = 22000.0   # 22 kHz


def hz_to_normalized(hz: float,
                     min_hz: float = EQ_FREQ_MIN,
                     max_hz: float = EQ_FREQ_MAX) -> float:
    """
    Convert frequency in Hz to normalized 0.0-1.0 value.

    Uses logarithmic scale (how humans perceive frequency).

    Args:
        hz: Frequency in Hz
        min_hz: Minimum frequency (default 10 Hz)
        max_hz: Maximum frequency (default 22 kHz)

    Returns:
        Normalized value 0.0-1.0

    Examples:
        >>> hz_to_normalized(100)   # ~0.30
        >>> hz_to_normalized(1000)  # ~0.60
        >>> hz_to_normalized(10000) # ~0.90
    """
    hz = max(min_hz, min(max_hz, hz))  # Clamp to range
    log_min = math.log10(min_hz)
    log_max = math.log10(max_hz)
    log_hz = math.log10(hz)
    return (log_hz - log_min) / (log_max - log_min)


def normalized_to_hz(normalized: float,
                     min_hz: float = EQ_FREQ_MIN,
                     max_hz: float = EQ_FREQ_MAX) -> float:
    """
    Convert normalized 0.0-1.0 value to frequency in Hz.

    Args:
        normalized: Normalized value 0.0-1.0
        min_hz: Minimum frequency (default 10 Hz)
        max_hz: Maximum frequency (default 22 kHz)

    Returns:
        Frequency in Hz
    """
    normalized = max(0.0, min(1.0, normalized))  # Clamp to range
    log_min = math.log10(min_hz)
    log_max = math.log10(max_hz)
    log_hz = log_min + normalized * (log_max - log_min)
    return 10 ** log_hz


# =============================================================================
# Gain/dB Conversion (Linear Scale)
# =============================================================================

# EQ Eight gain range
EQ_GAIN_MIN = -15.0  # -15 dB
EQ_GAIN_MAX = 15.0   # +15 dB

# Compressor threshold/makeup range
COMP_DB_MIN = -60.0
COMP_DB_MAX = 0.0


def db_to_normalized(db: float,
                     min_db: float = EQ_GAIN_MIN,
                     max_db: float = EQ_GAIN_MAX) -> float:
    """
    Convert dB value to normalized 0.0-1.0 value.

    Uses linear scale (dB is already logarithmic).

    Args:
        db: Gain in dB
        min_db: Minimum dB (default -15)
        max_db: Maximum dB (default +15)

    Returns:
        Normalized value 0.0-1.0

    Examples:
        >>> db_to_normalized(0)    # 0.5 (center/unity)
        >>> db_to_normalized(-3)   # 0.4
        >>> db_to_normalized(6)    # 0.7
    """
    db = max(min_db, min(max_db, db))  # Clamp to range
    return (db - min_db) / (max_db - min_db)


def normalized_to_db(normalized: float,
                     min_db: float = EQ_GAIN_MIN,
                     max_db: float = EQ_GAIN_MAX) -> float:
    """
    Convert normalized 0.0-1.0 value to dB.

    Args:
        normalized: Normalized value 0.0-1.0
        min_db: Minimum dB (default -15)
        max_db: Maximum dB (default +15)

    Returns:
        Gain in dB
    """
    normalized = max(0.0, min(1.0, normalized))  # Clamp to range
    return min_db + normalized * (max_db - min_db)


# =============================================================================
# Time Conversion (Milliseconds)
# =============================================================================

# Compressor attack range
COMP_ATTACK_MIN = 0.01    # 0.01 ms
COMP_ATTACK_MAX = 1000.0  # 1000 ms (1 second)

# Compressor release range
COMP_RELEASE_MIN = 1.0      # 1 ms
COMP_RELEASE_MAX = 3000.0   # 3000 ms (3 seconds)

# Delay time range (for delay effects)
DELAY_TIME_MIN = 1.0      # 1 ms
DELAY_TIME_MAX = 1000.0   # 1000 ms


def ms_to_normalized(ms: float,
                     min_ms: float = COMP_ATTACK_MIN,
                     max_ms: float = COMP_ATTACK_MAX,
                     logarithmic: bool = True) -> float:
    """
    Convert milliseconds to normalized 0.0-1.0 value.

    Args:
        ms: Time in milliseconds
        min_ms: Minimum time
        max_ms: Maximum time
        logarithmic: Use logarithmic scale (True for most time controls)

    Returns:
        Normalized value 0.0-1.0
    """
    ms = max(min_ms, min(max_ms, ms))  # Clamp to range

    if logarithmic:
        log_min = math.log10(min_ms)
        log_max = math.log10(max_ms)
        log_ms = math.log10(ms)
        return (log_ms - log_min) / (log_max - log_min)
    else:
        return (ms - min_ms) / (max_ms - min_ms)


def normalized_to_ms(normalized: float,
                     min_ms: float = COMP_ATTACK_MIN,
                     max_ms: float = COMP_ATTACK_MAX,
                     logarithmic: bool = True) -> float:
    """
    Convert normalized 0.0-1.0 value to milliseconds.

    Args:
        normalized: Normalized value 0.0-1.0
        min_ms: Minimum time
        max_ms: Maximum time
        logarithmic: Use logarithmic scale

    Returns:
        Time in milliseconds
    """
    normalized = max(0.0, min(1.0, normalized))  # Clamp to range

    if logarithmic:
        log_min = math.log10(min_ms)
        log_max = math.log10(max_ms)
        log_ms = log_min + normalized * (log_max - log_min)
        return 10 ** log_ms
    else:
        return min_ms + normalized * (max_ms - min_ms)


# =============================================================================
# Ratio Conversion (Compressor)
# =============================================================================

# Compressor ratio range
COMP_RATIO_MIN = 1.0    # 1:1 (no compression)
COMP_RATIO_MAX = 20.0   # inf:1 (limiting) - Ableton uses ~20 for inf


def ratio_to_normalized(ratio: float,
                        min_ratio: float = COMP_RATIO_MIN,
                        max_ratio: float = COMP_RATIO_MAX) -> float:
    """
    Convert compression ratio to normalized 0.0-1.0 value.

    Args:
        ratio: Compression ratio (e.g., 4 for 4:1)
        min_ratio: Minimum ratio (default 1:1)
        max_ratio: Maximum ratio (default 20:1)

    Returns:
        Normalized value 0.0-1.0

    Examples:
        >>> ratio_to_normalized(1)   # 0.0 (no compression)
        >>> ratio_to_normalized(4)   # ~0.16
        >>> ratio_to_normalized(10)  # ~0.47
    """
    ratio = max(min_ratio, min(max_ratio, ratio))  # Clamp to range
    # Use logarithmic scale for ratio
    log_min = math.log10(min_ratio)
    log_max = math.log10(max_ratio)
    log_ratio = math.log10(ratio)
    return (log_ratio - log_min) / (log_max - log_min)


def normalized_to_ratio(normalized: float,
                        min_ratio: float = COMP_RATIO_MIN,
                        max_ratio: float = COMP_RATIO_MAX) -> float:
    """
    Convert normalized 0.0-1.0 value to compression ratio.

    Args:
        normalized: Normalized value 0.0-1.0
        min_ratio: Minimum ratio
        max_ratio: Maximum ratio

    Returns:
        Compression ratio
    """
    normalized = max(0.0, min(1.0, normalized))  # Clamp to range
    log_min = math.log10(min_ratio)
    log_max = math.log10(max_ratio)
    log_ratio = log_min + normalized * (log_max - log_min)
    return 10 ** log_ratio


# =============================================================================
# Volume/Fader Conversion
# =============================================================================

# Track volume range
VOLUME_DB_MIN = -70.0   # -inf (practically)
VOLUME_DB_MAX = 6.0     # +6 dB


def volume_db_to_normalized(db: float) -> float:
    """
    Convert volume in dB to Ableton's normalized fader value.

    Ableton uses a specific curve for fader positions:
    - 0.0 = -inf (silence)
    - 0.85 ~ 0 dB (unity)
    - 1.0 = +6 dB

    This is an approximation of Ableton's fader curve.

    Args:
        db: Volume in dB (-70 to +6)

    Returns:
        Normalized fader value 0.0-1.0
    """
    if db <= -70:
        return 0.0
    if db >= 6:
        return 1.0

    # Ableton's fader is roughly:
    # - 0dB at 0.85
    # - Uses a modified log curve
    # This is an approximation
    if db <= 0:
        # Below unity: map -70..0 to 0..0.85
        # Use a curve that's more sensitive at lower volumes
        normalized_db = (db + 70) / 70  # 0 to 1
        return 0.85 * (normalized_db ** 0.5)  # Square root curve
    else:
        # Above unity: map 0..6 to 0.85..1.0
        return 0.85 + (db / 6) * 0.15


def normalized_to_volume_db(normalized: float) -> float:
    """
    Convert Ableton's normalized fader value to dB.

    Args:
        normalized: Fader value 0.0-1.0

    Returns:
        Volume in dB
    """
    if normalized <= 0:
        return -70.0
    if normalized >= 1.0:
        return 6.0

    if normalized <= 0.85:
        # Below unity
        curve_val = normalized / 0.85
        normalized_db = curve_val ** 2  # Inverse of square root
        return (normalized_db * 70) - 70
    else:
        # Above unity
        return ((normalized - 0.85) / 0.15) * 6


# =============================================================================
# Percentage Conversion
# =============================================================================

def percent_to_normalized(percent: float) -> float:
    """
    Convert percentage (0-100) to normalized (0.0-1.0).

    Args:
        percent: Value as percentage (0-100)

    Returns:
        Normalized value 0.0-1.0
    """
    return max(0.0, min(1.0, percent / 100.0))


def normalized_to_percent(normalized: float) -> float:
    """
    Convert normalized (0.0-1.0) to percentage (0-100).

    Args:
        normalized: Normalized value 0.0-1.0

    Returns:
        Value as percentage (0-100)
    """
    return max(0.0, min(100.0, normalized * 100.0))


# =============================================================================
# Q Factor Conversion (EQ)
# =============================================================================

# EQ Eight Q range
EQ_Q_MIN = 0.1
EQ_Q_MAX = 18.0


def q_to_normalized(q: float,
                    min_q: float = EQ_Q_MIN,
                    max_q: float = EQ_Q_MAX) -> float:
    """
    Convert Q factor to normalized 0.0-1.0 value.

    Q is typically logarithmic in EQ controls.

    Args:
        q: Q factor (bandwidth)
        min_q: Minimum Q
        max_q: Maximum Q

    Returns:
        Normalized value 0.0-1.0
    """
    q = max(min_q, min(max_q, q))
    log_min = math.log10(min_q)
    log_max = math.log10(max_q)
    log_q = math.log10(q)
    return (log_q - log_min) / (log_max - log_min)


def normalized_to_q(normalized: float,
                    min_q: float = EQ_Q_MIN,
                    max_q: float = EQ_Q_MAX) -> float:
    """
    Convert normalized 0.0-1.0 value to Q factor.

    Args:
        normalized: Normalized value 0.0-1.0
        min_q: Minimum Q
        max_q: Maximum Q

    Returns:
        Q factor
    """
    normalized = max(0.0, min(1.0, normalized))
    log_min = math.log10(min_q)
    log_max = math.log10(max_q)
    log_q = log_min + normalized * (log_max - log_min)
    return 10 ** log_q


# =============================================================================
# Parameter Type Detection and Auto-Conversion
# =============================================================================

@dataclass
class ParameterSpec:
    """Specification for a parameter type."""
    name_patterns: Tuple[str, ...]  # Patterns to match parameter names
    unit: str                        # Human-readable unit (Hz, dB, ms, etc.)
    to_normalized: callable          # Function to convert to normalized
    from_normalized: callable        # Function to convert from normalized


# Common parameter types
PARAMETER_SPECS = {
    'frequency': ParameterSpec(
        name_patterns=('freq', 'frequency', 'hz'),
        unit='Hz',
        to_normalized=hz_to_normalized,
        from_normalized=normalized_to_hz
    ),
    'gain': ParameterSpec(
        name_patterns=('gain', 'level', 'boost', 'cut'),
        unit='dB',
        to_normalized=db_to_normalized,
        from_normalized=normalized_to_db
    ),
    'q': ParameterSpec(
        name_patterns=('q', 'bandwidth', 'resonance'),
        unit='Q',
        to_normalized=q_to_normalized,
        from_normalized=normalized_to_q
    ),
    'attack': ParameterSpec(
        name_patterns=('attack',),
        unit='ms',
        to_normalized=lambda ms: ms_to_normalized(ms, COMP_ATTACK_MIN, COMP_ATTACK_MAX),
        from_normalized=lambda n: normalized_to_ms(n, COMP_ATTACK_MIN, COMP_ATTACK_MAX)
    ),
    'release': ParameterSpec(
        name_patterns=('release', 'decay'),
        unit='ms',
        to_normalized=lambda ms: ms_to_normalized(ms, COMP_RELEASE_MIN, COMP_RELEASE_MAX),
        from_normalized=lambda n: normalized_to_ms(n, COMP_RELEASE_MIN, COMP_RELEASE_MAX)
    ),
    'ratio': ParameterSpec(
        name_patterns=('ratio',),
        unit=':1',
        to_normalized=ratio_to_normalized,
        from_normalized=normalized_to_ratio
    ),
    'threshold': ParameterSpec(
        name_patterns=('threshold', 'thresh'),
        unit='dB',
        to_normalized=lambda db: db_to_normalized(db, COMP_DB_MIN, COMP_DB_MAX),
        from_normalized=lambda n: normalized_to_db(n, COMP_DB_MIN, COMP_DB_MAX)
    ),
}


def detect_parameter_type(param_name: str) -> Optional[str]:
    """
    Detect parameter type from name.

    Args:
        param_name: Name of the parameter

    Returns:
        Parameter type key or None if not detected
    """
    param_lower = param_name.lower()
    for param_type, spec in PARAMETER_SPECS.items():
        for pattern in spec.name_patterns:
            if pattern in param_lower:
                return param_type
    return None


def convert_to_normalized(value: float, param_name: str) -> Tuple[float, str]:
    """
    Auto-detect parameter type and convert to normalized.

    Args:
        value: Human-readable value (Hz, dB, ms, etc.)
        param_name: Name of the parameter

    Returns:
        Tuple of (normalized_value, detected_unit)
    """
    param_type = detect_parameter_type(param_name)
    if param_type:
        spec = PARAMETER_SPECS[param_type]
        return spec.to_normalized(value), spec.unit
    else:
        # Assume already normalized or percentage
        if value > 1.0:
            return percent_to_normalized(value), '%'
        return value, ''


def convert_from_normalized(normalized: float, param_name: str) -> Tuple[float, str]:
    """
    Auto-detect parameter type and convert from normalized.

    Args:
        normalized: Normalized value 0.0-1.0
        param_name: Name of the parameter

    Returns:
        Tuple of (human_value, unit)
    """
    param_type = detect_parameter_type(param_name)
    if param_type:
        spec = PARAMETER_SPECS[param_type]
        return spec.from_normalized(normalized), spec.unit
    else:
        return normalized_to_percent(normalized), '%'
