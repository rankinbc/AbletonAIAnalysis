"""
Prescriptive Fix Generator Module.

Generates specific, actionable fix recommendations from gap analysis results.
Maps abstract feature gaps to concrete Ableton Live parameter changes.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from .parameter_mapper import ParameterMapper, ParameterChange, FEATURE_TO_DEVICE_MAP


@dataclass
class PrescriptiveFix:
    """A specific, actionable fix recommendation."""
    # Identity
    id: str
    priority: int  # 1 = highest priority

    # Source
    feature: str
    severity: str  # "critical", "warning", "minor"

    # The specific action
    action_type: str  # "eq", "compressor", "volume", "stereo", "add_element", "arrangement"
    target_track: Optional[str]  # Track name if known
    target_device: Optional[str]  # Device name
    target_parameter: Optional[str]  # Parameter name

    # Values
    current_value: float
    target_value: float
    suggested_change: str  # Human-readable: "Reduce by 3 dB"

    # Confidence
    confidence: float  # 0-1

    # For auto-application
    osc_command: Optional[str] = None  # AbletonOSC command if applicable
    track_index: Optional[int] = None
    device_index: Optional[int] = None
    parameter_index: Optional[int] = None

    # Additional context
    explanation: str = ""
    alternative_approaches: List[str] = field(default_factory=list)
    manual_steps: List[str] = field(default_factory=list)
    requires_new_device: bool = False
    is_automatable: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            'id': self.id,
            'priority': self.priority,
            'feature': self.feature,
            'severity': self.severity,
            'action_type': self.action_type,
            'target_track': self.target_track,
            'target_device': self.target_device,
            'target_parameter': self.target_parameter,
            'current_value': float(self.current_value),
            'target_value': float(self.target_value),
            'suggested_change': self.suggested_change,
            'confidence': float(self.confidence),
            'osc_command': self.osc_command,
            'track_index': self.track_index,
            'device_index': self.device_index,
            'parameter_index': self.parameter_index,
            'explanation': self.explanation,
            'alternative_approaches': self.alternative_approaches,
            'manual_steps': self.manual_steps,
            'requires_new_device': self.requires_new_device,
            'is_automatable': self.is_automatable
        }

    def format_display(self) -> str:
        """Format fix for terminal display."""
        severity_icon = {
            'critical': '🔴',
            'warning': '🟡',
            'minor': '🟢'
        }.get(self.severity, '⚪')

        auto_icon = '🤖' if self.is_automatable else '👤'

        lines = [
            f"[{self.priority}] {severity_icon} {self.feature.replace('_', ' ').title()} "
            f"(Confidence: {self.confidence*100:.0f}%) {auto_icon}"
        ]

        lines.append(f"    Current: {self.current_value:.2f} | Target: {self.target_value:.2f}")
        lines.append("")

        if self.target_track or self.target_device:
            track_str = f'"{self.target_track}"' if self.target_track else "appropriate"
            device_str = self.target_device or "relevant device"
            lines.append(f"    ACTION: On {track_str} track, adjust {device_str}:")
            lines.append(f"      - {self.suggested_change}")
        else:
            lines.append(f"    ACTION: {self.suggested_change}")

        if self.osc_command:
            lines.append("")
            lines.append(f"    OSC: {self.osc_command}")

        if self.manual_steps:
            lines.append("")
            lines.append("    Manual steps:")
            for step in self.manual_steps:
                lines.append(f"      • {step}")

        if self.alternative_approaches:
            lines.append("")
            lines.append("    Alternatives:")
            for alt in self.alternative_approaches:
                lines.append(f"      • {alt}")

        return "\n".join(lines)


class PrescriptiveFixGenerator:
    """
    Generate specific, actionable fixes from gap analysis.

    Takes a GapReport and optionally ALS project data to produce
    detailed fix recommendations with specific parameter values
    and OSC commands for automation.
    """

    def __init__(
        self,
        profile=None,
        parameter_mapper: Optional[ParameterMapper] = None
    ):
        """
        Initialize generator.

        Args:
            profile: ReferenceProfile for context (optional)
            parameter_mapper: Custom parameter mapper (optional)
        """
        self.profile = profile
        self.mapper = parameter_mapper or ParameterMapper()

        # Severity to confidence boost mapping
        self.severity_confidence = {
            'critical': 0.95,
            'warning': 0.85,
            'minor': 0.70
        }

        # Action type classification
        self.action_types = {
            'pumping': 'compressor',
            'modulation': 'compressor',
            'stereo': 'stereo',
            'width': 'stereo',
            'phase': 'stereo',
            'supersaw': 'stereo',
            'spectral': 'eq',
            'brightness': 'eq',
            'energy': 'dynamics',
            'four_on_floor': 'volume',
            'offbeat': 'volume',
            'hihat': 'volume',
            'acid': 'filter',
            'tempo': 'arrangement',
        }

    def generate_fixes(
        self,
        gap_report,
        als_data: Optional[Any] = None,
        max_fixes: int = 10
    ) -> List[PrescriptiveFix]:
        """
        Generate prescriptive fixes from gap analysis.

        Args:
            gap_report: GapReport from gap analyzer
            als_data: Optional ALSProject or dict with track/device info
            max_fixes: Maximum number of fixes to generate

        Returns:
            List of PrescriptiveFix objects, sorted by priority
        """
        fixes = []

        # Process critical gaps first, then warnings, then minor
        all_gaps = (
            gap_report.critical_gaps +
            gap_report.warning_gaps +
            gap_report.minor_gaps[:5]  # Limit minor gaps
        )

        for i, gap in enumerate(all_gaps[:max_fixes]):
            fix = self._generate_fix_for_gap(gap, als_data, priority=i + 1)
            if fix:
                fixes.append(fix)

        return fixes

    def _generate_fix_for_gap(
        self,
        gap,
        als_data: Optional[Any],
        priority: int
    ) -> Optional[PrescriptiveFix]:
        """
        Generate a prescriptive fix for a single feature gap.

        Args:
            gap: FeatureGap object
            als_data: Optional ALS project data
            priority: Fix priority (1 = highest)

        Returns:
            PrescriptiveFix or None
        """
        feature_name = gap.feature_name

        # Get parameter mapping
        param_change = self.mapper.map_gap_to_parameter(
            feature_name,
            gap.absolute_delta,
            gap.wip_value
        )

        # Determine action type
        action_type = self._classify_action_type(feature_name)

        # Base confidence from severity
        base_confidence = self.severity_confidence.get(gap.severity, 0.7)

        # Adjust confidence based on mapping availability
        if param_change:
            confidence = base_confidence
        else:
            confidence = base_confidence * 0.7  # Lower if no direct mapping

        # Find target track if ALS data available
        target_track = None
        target_device = None
        track_index = None
        device_index = None
        osc_command = None
        is_automatable = False

        if als_data:
            target_track, track_index, device_index = self._find_target_in_project(
                feature_name, als_data
            )

            if param_change and track_index is not None:
                target_device = param_change.device_type

                if device_index is not None and param_change.osc_parameter_index is not None:
                    osc_command = self.mapper.format_osc_command(
                        track_index,
                        device_index,
                        param_change.osc_parameter_index,
                        param_change.target_value
                    )
                    is_automatable = True
                    confidence *= 1.1  # Boost confidence when we can automate

        # Cap confidence at 1.0
        confidence = min(confidence, 1.0)

        # Generate suggested change string
        if param_change:
            suggested_change = param_change.format_change()
            explanation = param_change.explanation
        else:
            suggested_change = self._generate_generic_suggestion(gap)
            explanation = gap.recommendation

        # Get alternative approaches
        alternatives = self._get_alternatives(feature_name, gap)

        # Get manual steps if not automatable
        manual_steps = []
        if not is_automatable:
            manual_steps = self._generate_manual_steps(feature_name, gap, param_change)

        # Check if new device needed
        requires_new_device = (
            param_change is not None and
            als_data is not None and
            device_index is None
        )

        return PrescriptiveFix(
            id=f"fix_{feature_name}_{priority}",
            priority=priority,
            feature=feature_name,
            severity=gap.severity,
            action_type=action_type,
            target_track=target_track,
            target_device=param_change.device_type if param_change else None,
            target_parameter=param_change.parameter_name if param_change else None,
            current_value=gap.wip_value,
            target_value=gap.target_value,
            suggested_change=suggested_change,
            confidence=confidence,
            osc_command=osc_command,
            track_index=track_index,
            device_index=device_index,
            parameter_index=param_change.osc_parameter_index if param_change else None,
            explanation=explanation,
            alternative_approaches=alternatives,
            manual_steps=manual_steps,
            requires_new_device=requires_new_device,
            is_automatable=is_automatable
        )

    def _classify_action_type(self, feature_name: str) -> str:
        """Classify the type of action needed for a feature."""
        feature_lower = feature_name.lower()

        for keyword, action in self.action_types.items():
            if keyword in feature_lower:
                return action

        return 'general'

    def _find_target_in_project(
        self,
        feature_name: str,
        als_data: Any
    ) -> Tuple[Optional[str], Optional[int], Optional[int]]:
        """
        Find the target track and device in the ALS project.

        Returns:
            (track_name, track_index, device_index)
        """
        # Get typical target tracks for this feature
        target_tracks = self.mapper.get_target_tracks(feature_name)

        if not target_tracks:
            return None, None, None

        # Try to find a matching track
        result = self.mapper.find_matching_track(als_data, target_tracks)

        if result:
            track_name, track_index = result

            # Try to find the device
            mapping = FEATURE_TO_DEVICE_MAP.get(feature_name, {})
            device_type = mapping.get('device')

            if device_type:
                device_info = self.mapper.find_device_on_track(
                    als_data, track_name, device_type
                )
                if device_info:
                    return track_name, track_index, device_info['device_index']

            return track_name, track_index, None

        return None, None, None

    def _generate_generic_suggestion(self, gap) -> str:
        """Generate a generic suggestion when no parameter mapping exists."""
        feature_display = gap.feature_name.replace('_', ' ').title()

        if gap.direction == 'high':
            return f"Reduce {feature_display} by approximately {abs(gap.absolute_delta):.2f}"
        elif gap.direction == 'low':
            return f"Increase {feature_display} by approximately {abs(gap.absolute_delta):.2f}"
        else:
            return f"Adjust {feature_display} to {gap.target_value:.2f}"

    def _get_alternatives(self, feature_name: str, gap) -> List[str]:
        """Get alternative approaches for fixing a gap."""
        alternatives = []

        # Get alternative devices from mapper
        alt_devices = self.mapper.get_alternative_devices(feature_name)
        if alt_devices:
            alternatives.append(f"Use alternative: {', '.join(alt_devices)}")

        # Feature-specific alternatives
        if 'pumping' in feature_name.lower():
            alternatives.append("Use volume automation instead of compression")
            alternatives.append("Try a dedicated sidechain plugin (e.g., LFOTool)")

        if 'stereo' in feature_name.lower() or 'width' in feature_name.lower():
            alternatives.append("Use mid-side EQ for targeted width control")
            alternatives.append("Add stereo reverb/delay on sends")

        if 'brightness' in feature_name.lower() or 'spectral' in feature_name.lower():
            alternatives.append("Use a different synth preset with more/less highs")
            alternatives.append("Add/remove saturation or exciter")

        if 'energy' in feature_name.lower():
            alternatives.append("Review arrangement - add breakdowns or builds")
            alternatives.append("Layer additional elements in low-energy sections")

        return alternatives[:3]  # Limit to 3 alternatives

    def _generate_manual_steps(
        self,
        feature_name: str,
        gap,
        param_change: Optional[ParameterChange]
    ) -> List[str]:
        """Generate manual steps when automation isn't possible."""
        steps = []

        # If arrangement fix needed
        if self.mapper.is_arrangement_fix(feature_name):
            steps.append("This primarily requires arrangement changes")
            steps.append("Consider adding/removing sections for more contrast")
            steps.append("Use automation to create builds and drops")
            return steps

        # If sound design fix needed
        if self.mapper.is_sound_design_fix(feature_name):
            steps.append("This requires sound design changes")
            steps.append("Consider using a different synth or preset")
            steps.append("Add the characteristic elements (filter sweeps, modulation)")
            return steps

        # Standard device-based fix
        if param_change:
            device = param_change.device_type
            steps.append(f"Locate or add {device} on the target track")
            steps.append(f"Adjust {param_change.parameter_name}: {param_change.format_change()}")
            steps.append("A/B compare with reference to verify improvement")
        else:
            steps.append(f"Identify tracks affecting {gap.feature_name.replace('_', ' ')}")
            steps.append(gap.recommendation)
            steps.append("Compare with reference to verify improvement")

        return steps

    def format_fixes_report(self, fixes: List[PrescriptiveFix]) -> str:
        """
        Format all fixes as a detailed text report.

        Args:
            fixes: List of PrescriptiveFix objects

        Returns:
            Formatted report string
        """
        if not fixes:
            return "No prescriptive fixes needed - mix is within reference targets!"

        lines = [
            "=" * 60,
            "PRESCRIPTIVE FIXES",
            "=" * 60,
            ""
        ]

        automatable = [f for f in fixes if f.is_automatable]
        manual = [f for f in fixes if not f.is_automatable]

        if automatable:
            lines.append(f"🤖 AUTOMATABLE FIXES ({len(automatable)})")
            lines.append("-" * 40)
            for fix in automatable:
                lines.append(fix.format_display())
                lines.append("")

        if manual:
            lines.append(f"👤 MANUAL FIXES ({len(manual)})")
            lines.append("-" * 40)
            for fix in manual:
                lines.append(fix.format_display())
                lines.append("")

        # Summary
        lines.append("=" * 60)
        lines.append("SUMMARY")
        lines.append("-" * 40)

        critical_count = len([f for f in fixes if f.severity == 'critical'])
        warning_count = len([f for f in fixes if f.severity == 'warning'])
        minor_count = len([f for f in fixes if f.severity == 'minor'])

        lines.append(f"  🔴 Critical: {critical_count}")
        lines.append(f"  🟡 Warning:  {warning_count}")
        lines.append(f"  🟢 Minor:    {minor_count}")
        lines.append(f"  🤖 Automatable: {len(automatable)}")
        lines.append(f"  👤 Manual: {len(manual)}")

        if automatable:
            lines.append("")
            lines.append("To auto-apply fixes, use the AbletonOSC bridge:")
            lines.append("  python analyze.py --apply-fixes <gap_report.json>")

        lines.append("=" * 60)

        return "\n".join(lines)


def generate_prescriptive_fixes(
    gap_report,
    als_data: Optional[Any] = None,
    profile=None,
    max_fixes: int = 10
) -> Tuple[List[PrescriptiveFix], str]:
    """
    Convenience function to generate prescriptive fixes and report.

    Args:
        gap_report: GapReport from gap analyzer
        als_data: Optional ALS project data
        profile: Optional ReferenceProfile
        max_fixes: Maximum fixes to generate

    Returns:
        Tuple of (fixes list, formatted report string)
    """
    generator = PrescriptiveFixGenerator(profile=profile)
    fixes = generator.generate_fixes(gap_report, als_data, max_fixes)
    report = generator.format_fixes_report(fixes)

    return fixes, report
