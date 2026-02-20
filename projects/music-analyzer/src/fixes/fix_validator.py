"""
Fix Validator Module.

Validates prescriptive fixes before application to ensure safety
and estimate their impact on closing feature gaps.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from .prescriptive_generator import PrescriptiveFix


@dataclass
class ValidationResult:
    """Result of fix validation."""
    is_valid: bool
    reason: str
    warnings: List[str]
    estimated_impact: float  # 0-1, how much this will improve the gap
    risk_level: str  # "low", "medium", "high"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            'is_valid': self.is_valid,
            'reason': self.reason,
            'warnings': self.warnings,
            'estimated_impact': self.estimated_impact,
            'risk_level': self.risk_level
        }


# Safe parameter ranges to prevent destructive changes
SAFE_RANGES = {
    # Volume changes (dB)
    'volume': {
        'min': -12.0,
        'max': 6.0,
        'description': 'Volume adjustment range'
    },
    'gain': {
        'min': -12.0,
        'max': 12.0,
        'description': 'Gain adjustment range'
    },

    # EQ gains (dB)
    'eq_gain': {
        'min': -12.0,
        'max': 12.0,
        'description': 'EQ band gain range'
    },

    # Compressor threshold (dB)
    'threshold': {
        'min': -40.0,
        'max': 0.0,
        'description': 'Compressor threshold range'
    },

    # Compressor ratio
    'ratio': {
        'min': 1.0,
        'max': 20.0,
        'description': 'Compression ratio range'
    },

    # Attack/Release (ms)
    'attack': {
        'min': 0.1,
        'max': 100.0,
        'description': 'Attack time range'
    },
    'release': {
        'min': 10.0,
        'max': 1000.0,
        'description': 'Release time range'
    },

    # Stereo width (%)
    'width': {
        'min': 0.0,
        'max': 200.0,
        'description': 'Stereo width range'
    },

    # Filter frequency (Hz)
    'frequency': {
        'min': 20.0,
        'max': 20000.0,
        'description': 'Filter frequency range'
    },

    # Resonance (%)
    'resonance': {
        'min': 0.0,
        'max': 100.0,
        'description': 'Filter resonance range'
    },
}

# High-risk parameter changes that need extra validation
HIGH_RISK_PARAMETERS = [
    'master_volume',
    'master_gain',
    'threshold',  # Can drastically change dynamics
    'width',  # Can cause phase issues
]

# Destructive action types to block
BLOCKED_ACTIONS = [
    'delete_track',
    'delete_device',
    'reset_all',
]


class FixValidator:
    """
    Validates fixes before application.

    Checks:
    - Parameter values are within safe ranges
    - Changes won't cause audio damage (clipping, phase cancellation)
    - Confidence level is acceptable
    - Track/device references are valid
    """

    def __init__(
        self,
        min_confidence: float = 0.5,
        strict_mode: bool = False,
        custom_safe_ranges: Optional[Dict] = None
    ):
        """
        Initialize validator.

        Args:
            min_confidence: Minimum confidence threshold (0-1)
            strict_mode: If True, apply stricter validation rules
            custom_safe_ranges: Override default safe parameter ranges
        """
        self.min_confidence = min_confidence
        self.strict_mode = strict_mode
        self.safe_ranges = SAFE_RANGES.copy()
        if custom_safe_ranges:
            self.safe_ranges.update(custom_safe_ranges)

    def validate(self, fix: PrescriptiveFix) -> ValidationResult:
        """
        Validate a single fix before application.

        Args:
            fix: PrescriptiveFix to validate

        Returns:
            ValidationResult with validation details
        """
        warnings = []
        reason = "Valid"

        # Check confidence threshold
        if fix.confidence < self.min_confidence:
            return ValidationResult(
                is_valid=False,
                reason=f"Confidence {fix.confidence:.2f} below threshold {self.min_confidence:.2f}",
                warnings=[],
                estimated_impact=0.0,
                risk_level="high"
            )

        # Check for blocked actions
        if fix.action_type in BLOCKED_ACTIONS:
            return ValidationResult(
                is_valid=False,
                reason=f"Action type '{fix.action_type}' is blocked for safety",
                warnings=[],
                estimated_impact=0.0,
                risk_level="high"
            )

        # Validate parameter value is in safe range
        param_valid, param_warning = self._validate_parameter_range(fix)
        if not param_valid:
            return ValidationResult(
                is_valid=False,
                reason=param_warning,
                warnings=[],
                estimated_impact=0.0,
                risk_level="high"
            )
        if param_warning:
            warnings.append(param_warning)

        # Check for high-risk changes
        risk_level = self._assess_risk_level(fix)
        if risk_level == "high" and self.strict_mode:
            warnings.append("High-risk change - manual review recommended")

        # Validate OSC command format if present
        if fix.osc_command:
            osc_valid, osc_warning = self._validate_osc_command(fix.osc_command)
            if not osc_valid:
                warnings.append(osc_warning)
                # Don't block for invalid OSC, just warn
                fix.is_automatable = False

        # Check change magnitude
        magnitude_warning = self._check_change_magnitude(fix)
        if magnitude_warning:
            warnings.append(magnitude_warning)

        # Estimate impact
        estimated_impact = self.estimate_impact(fix)

        return ValidationResult(
            is_valid=True,
            reason=reason,
            warnings=warnings,
            estimated_impact=estimated_impact,
            risk_level=risk_level
        )

    def validate_batch(
        self,
        fixes: List[PrescriptiveFix]
    ) -> Dict[str, ValidationResult]:
        """
        Validate multiple fixes.

        Args:
            fixes: List of fixes to validate

        Returns:
            Dict mapping fix ID to ValidationResult
        """
        results = {}
        for fix in fixes:
            results[fix.id] = self.validate(fix)
        return results

    def _validate_parameter_range(
        self,
        fix: PrescriptiveFix
    ) -> Tuple[bool, Optional[str]]:
        """Check if the parameter change is within safe limits."""
        if not fix.target_parameter:
            return True, None

        # Find matching safe range
        param_lower = fix.target_parameter.lower()
        matching_range = None

        for key, range_info in self.safe_ranges.items():
            if key in param_lower:
                matching_range = range_info
                break

        if not matching_range:
            # No specific range defined - allow with warning
            return True, f"No safe range defined for '{fix.target_parameter}' - verify manually"

        # Check if target value is in range
        min_val = matching_range['min']
        max_val = matching_range['max']

        if not (min_val <= fix.target_value <= max_val):
            return False, (
                f"Target value {fix.target_value:.2f} outside safe range "
                f"[{min_val:.2f}, {max_val:.2f}] for {fix.target_parameter}"
            )

        # Check if change amount is reasonable
        change_abs = abs(fix.target_value - fix.current_value)
        range_size = max_val - min_val

        if change_abs > range_size * 0.5:
            return True, (
                f"Large change detected ({change_abs:.2f}) - "
                f"more than 50% of safe range"
            )

        return True, None

    def _assess_risk_level(self, fix: PrescriptiveFix) -> str:
        """Assess the risk level of a fix."""
        # Check for high-risk parameters
        if fix.target_parameter:
            param_lower = fix.target_parameter.lower()
            for high_risk in HIGH_RISK_PARAMETERS:
                if high_risk in param_lower:
                    return "high"

        # Master track changes are higher risk
        if fix.target_track and 'master' in fix.target_track.lower():
            return "high" if fix.severity == 'critical' else "medium"

        # Critical severity with low confidence
        if fix.severity == 'critical' and fix.confidence < 0.7:
            return "high"

        # Large changes
        change_abs = abs(fix.target_value - fix.current_value)
        if change_abs > 10:  # More than 10 dB or equivalent
            return "medium"

        return "low"

    def _validate_osc_command(self, osc_command: str) -> Tuple[bool, Optional[str]]:
        """Validate OSC command format."""
        if not osc_command:
            return True, None

        # Basic format check: /live/track/X/device/Y/parameter/Z set VALUE
        parts = osc_command.split()

        if len(parts) < 3:
            return False, f"Invalid OSC command format: '{osc_command}'"

        path = parts[0]
        if not path.startswith('/live/'):
            return False, f"OSC path should start with '/live/': '{path}'"

        # Check for 'set' or valid action
        if 'set' not in osc_command.lower():
            return False, f"OSC command missing 'set' action: '{osc_command}'"

        return True, None

    def _check_change_magnitude(self, fix: PrescriptiveFix) -> Optional[str]:
        """Check if the change magnitude is unusually large."""
        change_abs = abs(fix.target_value - fix.current_value)

        # Thresholds vary by action type
        thresholds = {
            'volume': 6.0,
            'eq': 8.0,
            'compressor': 15.0,
            'stereo': 50.0,
            'filter': 5000.0,
        }

        threshold = thresholds.get(fix.action_type, 10.0)

        if change_abs > threshold:
            return (
                f"Large change magnitude ({change_abs:.2f}) - "
                f"consider incremental adjustment"
            )

        return None

    def estimate_impact(self, fix: PrescriptiveFix) -> float:
        """
        Estimate how much this fix will improve the gap score.

        Args:
            fix: PrescriptiveFix to estimate

        Returns:
            Impact score from 0-1 (1 = completely fixes the gap)
        """
        # Base impact from confidence
        base_impact = fix.confidence * 0.8

        # Severity weight
        severity_weight = {
            'critical': 1.0,
            'warning': 0.8,
            'minor': 0.5
        }.get(fix.severity, 0.5)

        # Automatable boost
        auto_boost = 1.1 if fix.is_automatable else 0.9

        # Calculate gap closure percentage
        if fix.current_value != 0:
            change_ratio = abs(fix.target_value - fix.current_value) / abs(fix.current_value)
            # If change is small relative to current, impact is higher (more precise)
            precision_factor = min(1.0, 1.0 / (change_ratio + 0.1))
        else:
            precision_factor = 0.8

        # Combined impact
        impact = base_impact * severity_weight * auto_boost * precision_factor

        # Cap at 1.0
        return min(impact, 1.0)

    def get_safe_range(self, parameter_name: str) -> Optional[Dict]:
        """
        Get the safe range for a parameter.

        Args:
            parameter_name: Parameter name to look up

        Returns:
            Dict with min, max, description or None
        """
        param_lower = parameter_name.lower()

        for key, range_info in self.safe_ranges.items():
            if key in param_lower:
                return range_info

        return None

    def suggest_safe_value(
        self,
        fix: PrescriptiveFix
    ) -> Optional[float]:
        """
        Suggest a safe value if the original is out of range.

        Args:
            fix: Fix with potentially unsafe value

        Returns:
            Safe value or None if original is safe
        """
        if not fix.target_parameter:
            return None

        safe_range = self.get_safe_range(fix.target_parameter)
        if not safe_range:
            return None

        min_val = safe_range['min']
        max_val = safe_range['max']

        if fix.target_value < min_val:
            return min_val
        elif fix.target_value > max_val:
            return max_val

        return None


def validate_fixes(
    fixes: List[PrescriptiveFix],
    min_confidence: float = 0.5,
    strict_mode: bool = False
) -> Tuple[List[PrescriptiveFix], List[ValidationResult]]:
    """
    Convenience function to validate a list of fixes.

    Args:
        fixes: List of fixes to validate
        min_confidence: Minimum confidence threshold
        strict_mode: Use strict validation

    Returns:
        Tuple of (valid_fixes, all_results)
    """
    validator = FixValidator(
        min_confidence=min_confidence,
        strict_mode=strict_mode
    )

    valid_fixes = []
    results = []

    for fix in fixes:
        result = validator.validate(fix)
        results.append(result)

        if result.is_valid:
            valid_fixes.append(fix)

    return valid_fixes, results
