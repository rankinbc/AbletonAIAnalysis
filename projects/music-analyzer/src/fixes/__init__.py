"""
Fixes Module.

Prescriptive fix generation system for mapping audio analysis gaps
to specific, actionable Ableton Live parameter changes.
"""

from .parameter_mapper import (
    ParameterMapper,
    ParameterChange,
    FEATURE_TO_DEVICE_MAP,
)
from .prescriptive_generator import (
    PrescriptiveFix,
    PrescriptiveFixGenerator,
)
from .fix_validator import (
    FixValidator,
    ValidationResult,
)

__all__ = [
    # Parameter mapping
    'ParameterMapper',
    'ParameterChange',
    'FEATURE_TO_DEVICE_MAP',
    # Fix generation
    'PrescriptiveFix',
    'PrescriptiveFixGenerator',
    # Validation
    'FixValidator',
    'ValidationResult',
]
