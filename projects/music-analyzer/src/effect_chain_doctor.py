"""
Effect Chain Doctor

Analyzes Ableton device chains for common mixing problems and provides
actionable recommendations. Specialized for trance music production.

Rules engine that detects:
- Disabled device clutter
- Wrong effect order
- Inappropriate effects (de-esser on drums)
- Double/triple compression
- Unusual parameter values
- Gain staging issues
- And more...
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
from enum import Enum
from device_chain_analyzer import (
    ProjectDeviceAnalysis, TrackDeviceChain, Device, DeviceCategory,
    DeviceChainAnalyzer, analyze_als_devices
)


class IssueSeverity(Enum):
    """Severity levels for issues."""
    CRITICAL = "critical"  # Will definitely cause problems
    WARNING = "warning"    # Likely causing problems
    SUGGESTION = "suggestion"  # Could be improved
    INFO = "info"          # Just FYI


class IssueCategory(Enum):
    """Categories of issues."""
    CLUTTER = "clutter"           # Disabled/unused devices
    WRONG_EFFECT = "wrong_effect"  # Effect doesn't belong
    CHAIN_ORDER = "chain_order"    # Effects in wrong order
    DUPLICATE = "duplicate"        # Redundant effects
    PARAMETERS = "parameters"      # Unusual parameter values
    GAIN_STAGING = "gain_staging"  # Level issues
    MISSING = "missing"           # Missing essential effects


@dataclass
class Issue:
    """A single detected issue with recommendation."""
    severity: IssueSeverity
    category: IssueCategory
    track_name: str
    device_name: Optional[str]
    device_index: Optional[int]
    title: str
    description: str
    recommendation: str

    def __str__(self) -> str:
        sev = self.severity.value.upper()
        return f"[{sev}] {self.track_name}: {self.title}"


@dataclass
class TrackDiagnosis:
    """Diagnosis for a single track."""
    track_name: str
    track_type: str
    device_count: int
    disabled_count: int
    issues: List[Issue] = field(default_factory=list)
    health_score: int = 100  # 0-100, 100 is perfect

    @property
    def critical_count(self) -> int:
        return len([i for i in self.issues if i.severity == IssueSeverity.CRITICAL])

    @property
    def warning_count(self) -> int:
        return len([i for i in self.issues if i.severity == IssueSeverity.WARNING])


@dataclass
class ProjectDiagnosis:
    """Complete diagnosis for an Ableton project."""
    file_path: str
    tempo: float
    track_diagnoses: List[TrackDiagnosis] = field(default_factory=list)
    global_issues: List[Issue] = field(default_factory=list)

    # Aggregate scores
    overall_health: int = 100
    total_issues: int = 0
    critical_issues: int = 0
    warning_issues: int = 0

    # Summary stats
    total_devices: int = 0
    total_disabled: int = 0
    clutter_percentage: float = 0.0

    def get_priority_issues(self, limit: int = 10) -> List[Issue]:
        """Get the highest priority issues to fix first."""
        all_issues = self.global_issues.copy()
        for diag in self.track_diagnoses:
            all_issues.extend(diag.issues)

        # Sort by severity
        severity_order = {
            IssueSeverity.CRITICAL: 0,
            IssueSeverity.WARNING: 1,
            IssueSeverity.SUGGESTION: 2,
            IssueSeverity.INFO: 3
        }
        all_issues.sort(key=lambda i: severity_order[i.severity])
        return all_issues[:limit]


class EffectChainDoctor:
    """
    Analyzes device chains and diagnoses mixing problems.

    Specialized for trance production but applicable to other electronic genres.
    """

    # Effects that should NOT be on certain track types
    WRONG_EFFECTS = {
        # Track type keywords -> forbidden effects
        "kick": ["de-esser", "vocal"],
        "hat": ["de-esser", "vocal", "bass"],
        "hi-hat": ["de-esser", "vocal", "bass"],
        "snare": ["de-esser", "vocal"],
        "clap": ["de-esser", "vocal"],
        "perc": ["de-esser", "vocal"],
        "drum": ["de-esser", "vocal"],
    }

    # Typical effect chain order for trance (position 0 = first)
    # Lower numbers should come before higher numbers
    IDEAL_CHAIN_ORDER = {
        DeviceCategory.INSTRUMENT: 0,
        DeviceCategory.GATE: 1,
        DeviceCategory.EQ: 2,  # Subtractive EQ first
        DeviceCategory.COMPRESSOR: 3,
        DeviceCategory.SATURATOR: 4,
        DeviceCategory.MODULATION: 5,
        DeviceCategory.DELAY: 6,
        DeviceCategory.REVERB: 7,
        DeviceCategory.EQ: 8,  # Additive EQ / final shaping
        DeviceCategory.LIMITER: 9,  # Should be last
    }

    # Compressor threshold ranges (these are normalized 0-1 in Ableton)
    # Very low thresholds mean heavy compression
    THRESHOLD_WARNINGS = {
        "very_low": 0.01,   # Below this is extreme
        "low": 0.05,        # Below this is aggressive
        "typical": 0.1,     # Normal range starts here
    }

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def diagnose(self, analysis: ProjectDeviceAnalysis) -> ProjectDiagnosis:
        """
        Diagnose an analyzed project for mixing issues.

        Args:
            analysis: ProjectDeviceAnalysis from DeviceChainAnalyzer

        Returns:
            ProjectDiagnosis with all detected issues
        """
        diagnosis = ProjectDiagnosis(
            file_path=analysis.file_path,
            tempo=analysis.tempo,
            total_devices=analysis.total_devices,
            total_disabled=analysis.total_disabled_devices
        )

        # Calculate clutter percentage
        if analysis.total_devices > 0:
            diagnosis.clutter_percentage = (
                analysis.total_disabled_devices / analysis.total_devices * 100
            )

        # Diagnose each track
        for track in analysis.tracks:
            track_diag = self._diagnose_track(track)
            diagnosis.track_diagnoses.append(track_diag)

        # Global analysis
        self._diagnose_global(diagnosis, analysis)

        # Calculate totals
        diagnosis.total_issues = len(diagnosis.global_issues)
        for diag in diagnosis.track_diagnoses:
            diagnosis.total_issues += len(diag.issues)
            diagnosis.critical_issues += diag.critical_count
            diagnosis.warning_issues += diag.warning_count

        # Calculate overall health score
        diagnosis.overall_health = self._calculate_health_score(diagnosis)

        return diagnosis

    def _diagnose_track(self, track: TrackDeviceChain) -> TrackDiagnosis:
        """Diagnose a single track."""
        diag = TrackDiagnosis(
            track_name=track.track_name,
            track_type=track.track_type,
            device_count=track.total_device_count,
            disabled_count=track.disabled_device_count
        )

        if not track.devices:
            return diag

        # Check for disabled device clutter
        self._check_disabled_clutter(track, diag)

        # Check for wrong effects
        self._check_wrong_effects(track, diag)

        # Check effect chain order
        self._check_chain_order(track, diag)

        # Check for duplicate effects
        self._check_duplicates(track, diag)

        # Check parameter values
        self._check_parameters(track, diag)

        # Check gain staging
        self._check_gain_staging(track, diag)

        # Calculate track health
        diag.health_score = 100 - (diag.critical_count * 20) - (diag.warning_count * 5)
        diag.health_score = max(0, diag.health_score)

        return diag

    def _check_disabled_clutter(self, track: TrackDeviceChain,
                                diag: TrackDiagnosis) -> None:
        """Check for disabled devices that should be deleted."""
        disabled = track.disabled_devices

        if not disabled:
            return

        # More than 2 disabled devices is clutter
        if len(disabled) >= 2:
            device_list = ", ".join([d.name for d in disabled[:5]])
            if len(disabled) > 5:
                device_list += f" (+{len(disabled)-5} more)"

            diag.issues.append(Issue(
                severity=IssueSeverity.WARNING,
                category=IssueCategory.CLUTTER,
                track_name=track.track_name,
                device_name=None,
                device_index=None,
                title=f"{len(disabled)} disabled devices cluttering chain",
                description=f"Disabled devices: {device_list}. These do nothing but add visual clutter and CPU overhead.",
                recommendation=f"DELETE these {len(disabled)} disabled devices, or ENABLE them if needed. In Ableton: Right-click each => Delete."
            ))
        elif len(disabled) == 1:
            d = disabled[0]
            diag.issues.append(Issue(
                severity=IssueSeverity.SUGGESTION,
                category=IssueCategory.CLUTTER,
                track_name=track.track_name,
                device_name=d.name,
                device_index=d.index,
                title=f"Disabled {d.name} - delete or enable?",
                description=f"'{d.name}' is OFF. If you're not using it, it's just clutter.",
                recommendation=f"DELETE '{d.name}' if not needed, or ENABLE it. Position {d.index + 1} in chain."
            ))

    def _check_wrong_effects(self, track: TrackDeviceChain,
                            diag: TrackDiagnosis) -> None:
        """Check for effects that don't belong on this track type."""
        track_name_lower = track.track_name.lower()

        for track_keyword, forbidden_keywords in self.WRONG_EFFECTS.items():
            if track_keyword in track_name_lower:
                # This track matches a type, check its devices
                for device in track.enabled_devices:
                    device_name_lower = device.name.lower()

                    for forbidden in forbidden_keywords:
                        if forbidden in device_name_lower:
                            diag.issues.append(Issue(
                                severity=IssueSeverity.WARNING,
                                category=IssueCategory.WRONG_EFFECT,
                                track_name=track.track_name,
                                device_name=device.name,
                                device_index=device.index,
                                title=f"'{device.name}' doesn't belong on {track_keyword}",
                                description=f"A {device.name} is typically used for vocals, not {track_keyword}s. This suggests either a wrong device or leftover from copy/paste.",
                                recommendation=f"REMOVE '{device.name}' from this track. If you need dynamics control, use a regular Compressor instead."
                            ))
                            break

    def _check_chain_order(self, track: TrackDeviceChain,
                          diag: TrackDiagnosis) -> None:
        """Check if effects are in a sensible order."""
        enabled = track.enabled_devices

        if len(enabled) < 2:
            return

        # Check limiter is last (excluding analyzers)
        limiters = [d for d in enabled if d.category == DeviceCategory.LIMITER]
        if limiters:
            last_limiter = limiters[-1]
            # Get non-utility devices after the limiter
            devices_after_limiter = [
                d for d in enabled
                if d.index > last_limiter.index
                and d.category not in [DeviceCategory.UTILITY, DeviceCategory.UNKNOWN]
            ]
            if devices_after_limiter:
                after_names = ", ".join([d.name for d in devices_after_limiter[:3]])
                diag.issues.append(Issue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.CHAIN_ORDER,
                    track_name=track.track_name,
                    device_name=last_limiter.name,
                    device_index=last_limiter.index,
                    title=f"Limiter should be LAST in chain",
                    description=f"'{last_limiter.name}' has devices after it: {after_names}. Limiters should be the final stage.",
                    recommendation=f"MOVE '{last_limiter.name}' to the END of the effect chain."
                ))

        # Check EQ before compressor (subtractive EQ principle)
        compressors = [d for d in enabled if d.category == DeviceCategory.COMPRESSOR]
        eqs = [d for d in enabled if d.category == DeviceCategory.EQ]

        if compressors and eqs:
            first_comp = min(compressors, key=lambda d: d.index)
            eqs_after_first_comp = [eq for eq in eqs if eq.index < first_comp.index]

            # If no EQ before first compressor, might be an issue
            if not eqs_after_first_comp and eqs:
                first_eq = min(eqs, key=lambda d: d.index)
                if first_eq.index > first_comp.index:
                    diag.issues.append(Issue(
                        severity=IssueSeverity.SUGGESTION,
                        category=IssueCategory.CHAIN_ORDER,
                        track_name=track.track_name,
                        device_name=first_eq.name,
                        device_index=first_eq.index,
                        title="Consider EQ before compression",
                        description=f"Your first compressor (pos {first_comp.index + 1}) comes before your first EQ (pos {first_eq.index + 1}). Often better to cut problem frequencies BEFORE compressing.",
                        recommendation=f"Try moving an EQ with high-pass/problem frequency cuts BEFORE the compressor."
                    ))

    def _check_duplicates(self, track: TrackDeviceChain,
                         diag: TrackDiagnosis) -> None:
        """Check for suspicious duplicate effects."""
        enabled = track.enabled_devices

        # Count by category
        category_counts: Dict[DeviceCategory, List[Device]] = {}
        for device in enabled:
            if device.category not in category_counts:
                category_counts[device.category] = []
            category_counts[device.category].append(device)

        # Check for excessive compressors (3+ is suspicious)
        compressors = category_counts.get(DeviceCategory.COMPRESSOR, [])
        if len(compressors) >= 3:
            names = ", ".join([c.name for c in compressors])
            diag.issues.append(Issue(
                severity=IssueSeverity.WARNING,
                category=IssueCategory.DUPLICATE,
                track_name=track.track_name,
                device_name=None,
                device_index=None,
                title=f"{len(compressors)} compressors in chain - too many?",
                description=f"Compressors: {names}. While serial compression can work, 3+ compressors often indicates uncertainty about what each is doing.",
                recommendation=f"REVIEW each compressor's purpose. Can you achieve the same result with 1-2? Consider removing redundant ones."
            ))
        elif len(compressors) == 2:
            # Two compressors is fine but worth noting
            diag.issues.append(Issue(
                severity=IssueSeverity.INFO,
                category=IssueCategory.DUPLICATE,
                track_name=track.track_name,
                device_name=None,
                device_index=None,
                title=f"Serial compression (2 compressors)",
                description=f"You have 2 compressors: {compressors[0].name}, {compressors[1].name}. This can be intentional (e.g., gentle + peak limiting).",
                recommendation=f"Ensure each compressor has a distinct purpose. First for tone/body, second for peaks."
            ))

        # Check for excessive saturators
        saturators = category_counts.get(DeviceCategory.SATURATOR, [])
        if len(saturators) >= 3:
            names = ", ".join([s.name for s in saturators])
            diag.issues.append(Issue(
                severity=IssueSeverity.WARNING,
                category=IssueCategory.DUPLICATE,
                track_name=track.track_name,
                device_name=None,
                device_index=None,
                title=f"{len(saturators)} saturators - cumulative distortion!",
                description=f"Saturators: {names}. Stacking saturation multiplies the effect and can cause muddiness.",
                recommendation=f"REDUCE to 1-2 saturators max. Each one adds harmonics that can build up to mud."
            ))

        # Check for multiple limiters (almost always wrong)
        limiters = category_counts.get(DeviceCategory.LIMITER, [])
        if len(limiters) >= 2:
            diag.issues.append(Issue(
                severity=IssueSeverity.CRITICAL,
                category=IssueCategory.DUPLICATE,
                track_name=track.track_name,
                device_name=None,
                device_index=None,
                title=f"{len(limiters)} limiters on same track!",
                description=f"Multiple limiters fight each other and cause pumping/distortion. This is almost never correct.",
                recommendation=f"KEEP only ONE limiter (the last one in chain). Remove the others."
            ))

    def _check_parameters(self, track: TrackDeviceChain,
                         diag: TrackDiagnosis) -> None:
        """Check for unusual parameter values."""
        for device in track.enabled_devices:
            if device.category == DeviceCategory.COMPRESSOR:
                self._check_compressor_params(device, track.track_name, diag)
            elif device.category == DeviceCategory.SATURATOR:
                self._check_saturator_params(device, track.track_name, diag)
            elif device.category == DeviceCategory.LIMITER:
                self._check_limiter_params(device, track.track_name, diag)

    def _check_compressor_params(self, device: Device, track_name: str,
                                 diag: TrackDiagnosis) -> None:
        """Check compressor parameter values."""
        threshold = device.parameters.get("Threshold")
        ratio = device.parameters.get("Ratio")

        if threshold:
            val = threshold.value
            if isinstance(val, (int, float)) and val < self.THRESHOLD_WARNINGS["very_low"]:
                diag.issues.append(Issue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.PARAMETERS,
                    track_name=track_name,
                    device_name=device.name,
                    device_index=device.index,
                    title=f"'{device.name}' threshold extremely low",
                    description=f"Threshold is very low ({val:.4f}), meaning heavy compression on almost all signal. This can kill dynamics.",
                    recommendation=f"RAISE threshold on '{device.name}' so compression only catches peaks. Try threshold around 0.1-0.3."
                ))

        if ratio:
            val = ratio.value
            # Check for absurd ratios (like the infinity one we saw)
            if isinstance(val, (int, float)) and val > 20:
                diag.issues.append(Issue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.PARAMETERS,
                    track_name=track_name,
                    device_name=device.name,
                    device_index=device.index,
                    title=f"'{device.name}' ratio extremely high ({val:.0f}:1)",
                    description=f"Ratio above 20:1 is essentially limiting, not compression. If intentional, use a Limiter instead.",
                    recommendation=f"REDUCE ratio to 2:1-8:1 for natural compression, or replace with a Limiter."
                ))

    def _check_saturator_params(self, device: Device, track_name: str,
                               diag: TrackDiagnosis) -> None:
        """Check saturator parameter values."""
        dry_wet = device.parameters.get("DryWet")

        if dry_wet:
            val = dry_wet.value
            if isinstance(val, (int, float)) and val >= 0.95:
                diag.issues.append(Issue(
                    severity=IssueSeverity.SUGGESTION,
                    category=IssueCategory.PARAMETERS,
                    track_name=track_name,
                    device_name=device.name,
                    device_index=device.index,
                    title=f"'{device.name}' at 100% wet",
                    description=f"Saturator at full wet ({val*100:.0f}%) means no dry signal. This is aggressive - subtle saturation often works better.",
                    recommendation=f"Try REDUCING dry/wet to 30-70% on '{device.name}' for more subtle warmth."
                ))

    def _check_limiter_params(self, device: Device, track_name: str,
                             diag: TrackDiagnosis) -> None:
        """Check limiter parameter values."""
        gain = device.parameters.get("Gain")

        if gain:
            val = gain.value
            if isinstance(val, (int, float)) and val > 6:
                diag.issues.append(Issue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.PARAMETERS,
                    track_name=track_name,
                    device_name=device.name,
                    device_index=device.index,
                    title=f"'{device.name}' pushing +{val:.1f}dB gain",
                    description=f"Limiter input gain of +{val:.1f}dB is very aggressive. You're hitting the ceiling hard.",
                    recommendation=f"REDUCE limiter gain to +3dB or less. If you need more level, check gain staging earlier in chain."
                ))

    def _check_gain_staging(self, track: TrackDeviceChain,
                           diag: TrackDiagnosis) -> None:
        """Check track gain staging."""
        # Volume of +20dB is suspiciously high (default in Ableton display)
        if track.volume_db > 10:
            diag.issues.append(Issue(
                severity=IssueSeverity.INFO,
                category=IssueCategory.GAIN_STAGING,
                track_name=track.track_name,
                device_name=None,
                device_index=None,
                title=f"Track volume at +{track.volume_db:.1f}dB",
                description=f"High track volume. This is fine if your sources are quiet, but check you're not compensating for over-compression.",
                recommendation=f"Consider keeping track faders near 0dB and adjusting levels with Utility gain instead."
            ))

    def _diagnose_global(self, diagnosis: ProjectDiagnosis,
                        analysis: ProjectDeviceAnalysis) -> None:
        """Check for project-wide issues."""
        # High clutter percentage
        if diagnosis.clutter_percentage > 30:
            diagnosis.global_issues.append(Issue(
                severity=IssueSeverity.WARNING,
                category=IssueCategory.CLUTTER,
                track_name="PROJECT",
                device_name=None,
                device_index=None,
                title=f"{diagnosis.clutter_percentage:.0f}% of devices are disabled",
                description=f"{analysis.total_disabled_devices} of {analysis.total_devices} devices are OFF. This is significant clutter.",
                recommendation=f"CLEAN UP: Delete disabled devices you're not using. This will make your project clearer and lighter."
            ))

        # Check master chain
        master_tracks = [t for t in analysis.tracks if t.track_type == "master"]
        if master_tracks:
            master = master_tracks[0]
            enabled_on_master = len(master.enabled_devices)
            disabled_on_master = len(master.disabled_devices)

            if disabled_on_master > enabled_on_master:
                diagnosis.global_issues.append(Issue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.CLUTTER,
                    track_name="MASTER",
                    device_name=None,
                    device_index=None,
                    title=f"Master chain cluttered ({disabled_on_master} disabled vs {enabled_on_master} active)",
                    description=f"Your master chain has more disabled devices than active ones. Clean this up for clarity.",
                    recommendation=f"DELETE unused devices from master. Keep only: EQ (if needed), Compressor/Glue, Limiter, Analyzer."
                ))

    def _calculate_health_score(self, diagnosis: ProjectDiagnosis) -> int:
        """Calculate overall project health score (0-100)."""
        score = 100

        # Deduct for critical issues
        score -= diagnosis.critical_issues * 15

        # Deduct for warnings
        score -= diagnosis.warning_issues * 3

        # Deduct for high clutter
        if diagnosis.clutter_percentage > 30:
            score -= 10
        elif diagnosis.clutter_percentage > 20:
            score -= 5

        return max(0, min(100, score))

    def generate_report(self, diagnosis: ProjectDiagnosis) -> str:
        """Generate a human-readable diagnosis report."""
        lines = []
        lines.append("=" * 70)
        lines.append("EFFECT CHAIN DOCTOR - PROJECT DIAGNOSIS")
        lines.append("=" * 70)
        lines.append(f"Project: {diagnosis.file_path}")
        lines.append(f"Tempo: {diagnosis.tempo} BPM")
        lines.append("")

        # Health summary
        health_emoji = "[OK]" if diagnosis.overall_health >= 80 else "[!!]" if diagnosis.overall_health >= 50 else "[XX]"
        lines.append(f"OVERALL HEALTH: {health_emoji} {diagnosis.overall_health}/100")
        lines.append(f"Total Issues: {diagnosis.total_issues}")
        lines.append(f"  - Critical: {diagnosis.critical_issues}")
        lines.append(f"  - Warnings: {diagnosis.warning_issues}")
        lines.append(f"")
        lines.append(f"Devices: {diagnosis.total_devices} total, {diagnosis.total_disabled} disabled ({diagnosis.clutter_percentage:.0f}% clutter)")
        lines.append("")

        # Priority issues
        priority = diagnosis.get_priority_issues(10)
        if priority:
            lines.append("-" * 70)
            lines.append("TOP ISSUES TO FIX (in priority order):")
            lines.append("-" * 70)
            for i, issue in enumerate(priority, 1):
                sev_icon = {"critical": "[!!!]", "warning": "[!!]", "suggestion": "[!]", "info": "[i]"}.get(issue.severity.value, "")
                lines.append(f"\n{i}. {sev_icon} [{issue.severity.value.upper()}] {issue.title}")
                lines.append(f"   Track: {issue.track_name}")
                if issue.device_name:
                    lines.append(f"   Device: {issue.device_name} (position {issue.device_index + 1 if issue.device_index else '?'})")
                lines.append(f"   Problem: {issue.description}")
                lines.append(f"   => FIX: {issue.recommendation}")

        # Per-track summary
        lines.append("")
        lines.append("-" * 70)
        lines.append("TRACK-BY-TRACK SUMMARY:")
        lines.append("-" * 70)

        # Sort by health (worst first)
        sorted_tracks = sorted(diagnosis.track_diagnoses, key=lambda t: t.health_score)

        for track_diag in sorted_tracks:
            if track_diag.device_count == 0:
                continue

            health_icon = "[OK]" if track_diag.health_score >= 80 else "[!!]" if track_diag.health_score >= 50 else "[XX]"
            issue_summary = ""
            if track_diag.critical_count:
                issue_summary += f" {track_diag.critical_count} critical"
            if track_diag.warning_count:
                issue_summary += f" {track_diag.warning_count} warnings"

            lines.append(f"{health_icon} {track_diag.track_name}: {track_diag.device_count} devices, {track_diag.disabled_count} disabled{issue_summary}")

        lines.append("")
        lines.append("=" * 70)
        lines.append("Run this after making changes to track your improvement!")
        lines.append("=" * 70)

        return "\n".join(lines)


def diagnose_project(als_path: str, verbose: bool = False) -> ProjectDiagnosis:
    """Quick function to analyze and diagnose a project."""
    analysis = analyze_als_devices(als_path, verbose=verbose)
    doctor = EffectChainDoctor(verbose=verbose)
    return doctor.diagnose(analysis)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        diagnosis = diagnose_project(sys.argv[1], verbose=True)
        doctor = EffectChainDoctor()
        print(doctor.generate_report(diagnosis))
