"""
Project Differ

Compares two Ableton Live Set (.als) files to show what changed.
Tracks whether changes are improvements or regressions.

Use this to answer: "Did my tweaks make the song better or worse?"
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
from pathlib import Path
from device_chain_analyzer import (
    ProjectDeviceAnalysis, TrackDeviceChain, Device, DeviceCategory,
    DeviceChainAnalyzer, analyze_als_devices
)
from effect_chain_doctor import (
    ProjectDiagnosis, diagnose_project, EffectChainDoctor
)


@dataclass
class DeviceChange:
    """A change to a device."""
    change_type: str  # added, removed, modified, enabled, disabled
    track_name: str
    device_name: str
    device_type: str
    details: str = ""


@dataclass
class ParameterChange:
    """A parameter value change."""
    track_name: str
    device_name: str
    param_name: str
    old_value: any
    new_value: any


@dataclass
class TrackChange:
    """Changes to a track."""
    change_type: str  # added, removed, modified
    track_name: str
    details: str = ""


@dataclass
class ProjectDiff:
    """Complete diff between two project versions."""
    before_path: str
    after_path: str

    # Health score comparison
    before_health: int
    after_health: int
    health_delta: int  # positive = improvement

    # Issue counts
    before_issues: int
    after_issues: int
    issues_delta: int  # negative = improvement (fewer issues)

    # Device counts
    before_devices: int
    after_devices: int
    before_disabled: int
    after_disabled: int

    # Specific changes
    device_changes: List[DeviceChange] = field(default_factory=list)
    track_changes: List[TrackChange] = field(default_factory=list)

    # Assessment
    is_improvement: bool = False
    improvement_reasons: List[str] = field(default_factory=list)
    regression_reasons: List[str] = field(default_factory=list)


class ProjectDiffer:
    """
    Compares two versions of an Ableton project.

    Helps producers track whether their changes are improvements.
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.analyzer = DeviceChainAnalyzer(verbose=verbose)
        self.doctor = EffectChainDoctor(verbose=verbose)

    def compare(self, before_path: str, after_path: str) -> ProjectDiff:
        """
        Compare two project versions.

        Args:
            before_path: Path to the earlier version (.als)
            after_path: Path to the later version (.als)

        Returns:
            ProjectDiff with all changes and assessment
        """
        # Analyze both projects
        before_analysis = self.analyzer.analyze(before_path)
        after_analysis = self.analyzer.analyze(after_path)

        # Diagnose both
        before_diag = self.doctor.diagnose(before_analysis)
        after_diag = self.doctor.diagnose(after_analysis)

        diff = ProjectDiff(
            before_path=before_path,
            after_path=after_path,
            before_health=before_diag.overall_health,
            after_health=after_diag.overall_health,
            health_delta=after_diag.overall_health - before_diag.overall_health,
            before_issues=before_diag.total_issues,
            after_issues=after_diag.total_issues,
            issues_delta=after_diag.total_issues - before_diag.total_issues,
            before_devices=before_analysis.total_devices,
            after_devices=after_analysis.total_devices,
            before_disabled=before_analysis.total_disabled_devices,
            after_disabled=after_analysis.total_disabled_devices
        )

        # Compare device chains
        self._compare_devices(before_analysis, after_analysis, diff)

        # Assess overall improvement
        self._assess_improvement(diff)

        return diff

    def _compare_devices(self, before: ProjectDeviceAnalysis,
                        after: ProjectDeviceAnalysis, diff: ProjectDiff) -> None:
        """Compare device chains between versions."""
        # Build track lookups
        before_tracks = {t.track_name: t for t in before.tracks}
        after_tracks = {t.track_name: t for t in after.tracks}

        # Find added/removed tracks
        before_names = set(before_tracks.keys())
        after_names = set(after_tracks.keys())

        for name in after_names - before_names:
            diff.track_changes.append(TrackChange(
                change_type="added",
                track_name=name,
                details=f"New track with {after_tracks[name].total_device_count} devices"
            ))

        for name in before_names - after_names:
            diff.track_changes.append(TrackChange(
                change_type="removed",
                track_name=name,
                details=f"Removed track that had {before_tracks[name].total_device_count} devices"
            ))

        # Compare shared tracks
        for name in before_names & after_names:
            before_track = before_tracks[name]
            after_track = after_tracks[name]
            self._compare_track_devices(before_track, after_track, diff)

    def _compare_track_devices(self, before: TrackDeviceChain,
                              after: TrackDeviceChain, diff: ProjectDiff) -> None:
        """Compare devices on a single track."""
        # Build device lookups by name + type
        def device_key(d: Device) -> str:
            return f"{d.device_type}:{d.name}"

        before_devices = {device_key(d): d for d in before.devices}
        after_devices = {device_key(d): d for d in after.devices}

        before_keys = set(before_devices.keys())
        after_keys = set(after_devices.keys())

        # Added devices
        for key in after_keys - before_keys:
            d = after_devices[key]
            status = "enabled" if d.is_enabled else "disabled"
            diff.device_changes.append(DeviceChange(
                change_type="added",
                track_name=after.track_name,
                device_name=d.name,
                device_type=d.device_type,
                details=f"Added ({status})"
            ))

        # Removed devices
        for key in before_keys - after_keys:
            d = before_devices[key]
            diff.device_changes.append(DeviceChange(
                change_type="removed",
                track_name=before.track_name,
                device_name=d.name,
                device_type=d.device_type,
                details="Removed from chain"
            ))

        # Check for enabled/disabled changes on existing devices
        for key in before_keys & after_keys:
            before_d = before_devices[key]
            after_d = after_devices[key]

            if before_d.is_enabled and not after_d.is_enabled:
                diff.device_changes.append(DeviceChange(
                    change_type="disabled",
                    track_name=after.track_name,
                    device_name=after_d.name,
                    device_type=after_d.device_type,
                    details="Was ON, now OFF"
                ))
            elif not before_d.is_enabled and after_d.is_enabled:
                diff.device_changes.append(DeviceChange(
                    change_type="enabled",
                    track_name=after.track_name,
                    device_name=after_d.name,
                    device_type=after_d.device_type,
                    details="Was OFF, now ON"
                ))

    def _assess_improvement(self, diff: ProjectDiff) -> None:
        """Assess whether the changes are an improvement."""
        # Health improved
        if diff.health_delta > 0:
            diff.improvement_reasons.append(
                f"Health score improved: {diff.before_health} => {diff.after_health} (+{diff.health_delta})"
            )

        if diff.health_delta < 0:
            diff.regression_reasons.append(
                f"Health score dropped: {diff.before_health} => {diff.after_health} ({diff.health_delta})"
            )

        # Fewer issues
        if diff.issues_delta < 0:
            diff.improvement_reasons.append(
                f"Reduced issues: {diff.before_issues} => {diff.after_issues} ({diff.issues_delta})"
            )

        if diff.issues_delta > 0:
            diff.regression_reasons.append(
                f"More issues: {diff.before_issues} => {diff.after_issues} (+{diff.issues_delta})"
            )

        # Less clutter (fewer disabled devices)
        clutter_delta = diff.after_disabled - diff.before_disabled
        if clutter_delta < 0:
            diff.improvement_reasons.append(
                f"Reduced clutter: {diff.before_disabled} => {diff.after_disabled} disabled devices ({clutter_delta})"
            )

        if clutter_delta > 0:
            diff.regression_reasons.append(
                f"More clutter: {diff.before_disabled} => {diff.after_disabled} disabled devices (+{clutter_delta})"
            )

        # Count device removals (usually good for cleaning)
        removed_count = len([c for c in diff.device_changes if c.change_type == "removed"])
        added_count = len([c for c in diff.device_changes if c.change_type == "added"])

        if removed_count > added_count:
            diff.improvement_reasons.append(
                f"Simplified: removed {removed_count} devices, added {added_count}"
            )

        if added_count > removed_count + 3:  # Adding lots of devices can be concerning
            diff.regression_reasons.append(
                f"Added many devices: +{added_count} devices, only -{removed_count} removed"
            )

        # Overall assessment
        diff.is_improvement = len(diff.improvement_reasons) > len(diff.regression_reasons)

    def generate_report(self, diff: ProjectDiff) -> str:
        """Generate a human-readable diff report."""
        lines = []
        lines.append("=" * 70)
        lines.append("PROJECT COMPARISON REPORT")
        lines.append("=" * 70)
        lines.append(f"BEFORE: {Path(diff.before_path).name}")
        lines.append(f"AFTER:  {Path(diff.after_path).name}")
        lines.append("")

        # Overall verdict
        if diff.is_improvement:
            verdict = "[IMPROVEMENT] Your changes made the project better!"
        elif diff.health_delta == 0 and diff.issues_delta == 0:
            verdict = "[NO CHANGE] Project health is the same"
        else:
            verdict = "[REGRESSION] Your changes may have made things worse"

        lines.append(verdict)
        lines.append("")

        # Health comparison
        lines.append("-" * 70)
        lines.append("HEALTH COMPARISON:")
        lines.append("-" * 70)

        health_arrow = "=>" if diff.health_delta >= 0 else "=>"
        health_sign = "+" if diff.health_delta > 0 else ""
        lines.append(f"  Health Score: {diff.before_health} => {diff.after_health} ({health_sign}{diff.health_delta})")

        issues_sign = "+" if diff.issues_delta > 0 else ""
        lines.append(f"  Total Issues: {diff.before_issues} => {diff.after_issues} ({issues_sign}{diff.issues_delta})")

        lines.append(f"  Total Devices: {diff.before_devices} => {diff.after_devices}")
        lines.append(f"  Disabled Devices: {diff.before_disabled} => {diff.after_disabled}")
        lines.append("")

        # Improvement reasons
        if diff.improvement_reasons:
            lines.append("-" * 70)
            lines.append("WHAT IMPROVED:")
            lines.append("-" * 70)
            for reason in diff.improvement_reasons:
                lines.append(f"  [+] {reason}")
            lines.append("")

        # Regression reasons
        if diff.regression_reasons:
            lines.append("-" * 70)
            lines.append("WHAT GOT WORSE:")
            lines.append("-" * 70)
            for reason in diff.regression_reasons:
                lines.append(f"  [-] {reason}")
            lines.append("")

        # Device changes
        if diff.device_changes:
            lines.append("-" * 70)
            lines.append("DEVICE CHANGES:")
            lines.append("-" * 70)

            # Group by type
            added = [c for c in diff.device_changes if c.change_type == "added"]
            removed = [c for c in diff.device_changes if c.change_type == "removed"]
            enabled = [c for c in diff.device_changes if c.change_type == "enabled"]
            disabled = [c for c in diff.device_changes if c.change_type == "disabled"]

            if removed:
                lines.append(f"\n  REMOVED ({len(removed)}):")
                for c in removed[:10]:
                    lines.append(f"    - {c.track_name}: {c.device_name}")
                if len(removed) > 10:
                    lines.append(f"    ... and {len(removed) - 10} more")

            if added:
                lines.append(f"\n  ADDED ({len(added)}):")
                for c in added[:10]:
                    lines.append(f"    + {c.track_name}: {c.device_name}")
                if len(added) > 10:
                    lines.append(f"    ... and {len(added) - 10} more")

            if enabled:
                lines.append(f"\n  ENABLED ({len(enabled)}):")
                for c in enabled[:5]:
                    lines.append(f"    * {c.track_name}: {c.device_name}")

            if disabled:
                lines.append(f"\n  DISABLED ({len(disabled)}):")
                for c in disabled[:5]:
                    lines.append(f"    * {c.track_name}: {c.device_name}")

        # Track changes
        if diff.track_changes:
            lines.append("")
            lines.append("-" * 70)
            lines.append("TRACK CHANGES:")
            lines.append("-" * 70)
            for change in diff.track_changes:
                symbol = "+" if change.change_type == "added" else "-"
                lines.append(f"  [{symbol}] {change.track_name}: {change.details}")

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)


def compare_projects(before_path: str, after_path: str,
                    verbose: bool = False) -> ProjectDiff:
    """Quick function to compare two project versions."""
    differ = ProjectDiffer(verbose=verbose)
    return differ.compare(before_path, after_path)


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        diff = compare_projects(sys.argv[1], sys.argv[2], verbose=True)
        differ = ProjectDiffer()
        print(differ.generate_report(diff))
    else:
        print("Usage: python project_differ.py <before.als> <after.als>")
