"""
Pre-Export Checklist Module for ALS Doctor

Provides pre-export verification to ensure Ableton projects are
ready for final export/bounce. Checks for common issues that
could cause problems in the final render.

Usage:
    from preflight import preflight_check, PreflightResult
    result = preflight_check('/path/to/project.als', min_score=70)
    if result.is_ready:
        print("Ready to export!")
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from enum import Enum


class CheckStatus(Enum):
    """Status of an individual preflight check."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class PreflightCheckItem:
    """A single preflight check result."""
    name: str
    description: str
    status: CheckStatus
    details: Optional[str] = None
    is_blocker: bool = False  # True = must fix before export


@dataclass
class PreflightResult:
    """Complete preflight check result."""
    als_path: str
    als_filename: str
    health_score: int
    grade: str
    is_ready: bool  # True if no blockers

    # Check results
    checks: List[PreflightCheckItem] = field(default_factory=list)
    blockers: List[PreflightCheckItem] = field(default_factory=list)
    warnings: List[PreflightCheckItem] = field(default_factory=list)
    passed: List[PreflightCheckItem] = field(default_factory=list)

    # Configuration used
    min_score: int = 60
    strict_mode: bool = False

    # Summary
    total_checks: int = 0
    passed_count: int = 0
    failed_count: int = 0
    warning_count: int = 0


def _check_health_score(health_score: int, grade: str, min_score: int, strict: bool) -> PreflightCheckItem:
    """Check if health score meets the threshold."""
    if strict:
        # Strict mode requires Grade A (80+)
        if health_score >= 80:
            return PreflightCheckItem(
                name="Health Score",
                description="Project health meets strict Grade A requirement",
                status=CheckStatus.PASS,
                details=f"Score: {health_score}/100 [{grade}]",
                is_blocker=False
            )
        else:
            return PreflightCheckItem(
                name="Health Score",
                description="Project health below strict Grade A requirement",
                status=CheckStatus.FAIL,
                details=f"Score: {health_score}/100 [{grade}] (requires 80+ for strict mode)",
                is_blocker=True
            )
    else:
        # Normal mode checks against min_score threshold
        if health_score >= min_score:
            return PreflightCheckItem(
                name="Health Score",
                description="Project health meets minimum threshold",
                status=CheckStatus.PASS,
                details=f"Score: {health_score}/100 [{grade}] (min: {min_score})",
                is_blocker=False
            )
        else:
            return PreflightCheckItem(
                name="Health Score",
                description="Project health below minimum threshold",
                status=CheckStatus.FAIL,
                details=f"Score: {health_score}/100 [{grade}] (requires {min_score}+)",
                is_blocker=True
            )


def _check_critical_issues(critical_count: int) -> PreflightCheckItem:
    """Check for critical issues that block export."""
    if critical_count == 0:
        return PreflightCheckItem(
            name="Critical Issues",
            description="No critical issues found",
            status=CheckStatus.PASS,
            details="All critical checks passed",
            is_blocker=False
        )
    else:
        return PreflightCheckItem(
            name="Critical Issues",
            description=f"Found {critical_count} critical issue(s)",
            status=CheckStatus.FAIL,
            details=f"{critical_count} critical issue(s) must be resolved before export",
            is_blocker=True
        )


def _check_solo_tracks(tracks: list) -> PreflightCheckItem:
    """Check for accidentally solo'd tracks."""
    solo_tracks = [t for t in tracks if hasattr(t, 'is_solo') and t.is_solo]

    if not solo_tracks:
        return PreflightCheckItem(
            name="Solo'd Tracks",
            description="No tracks are in solo mode",
            status=CheckStatus.PASS,
            details="All tracks will be rendered",
            is_blocker=False
        )
    else:
        solo_names = [t.track_name for t in solo_tracks]
        return PreflightCheckItem(
            name="Solo'd Tracks",
            description=f"Found {len(solo_tracks)} solo'd track(s)",
            status=CheckStatus.FAIL,
            details=f"Solo'd: {', '.join(solo_names[:5])}{'...' if len(solo_names) > 5 else ''}",
            is_blocker=True
        )


def _check_master_mute(master_track) -> PreflightCheckItem:
    """Check if master track is muted."""
    if master_track is None:
        return PreflightCheckItem(
            name="Master Mute",
            description="Could not verify master track state",
            status=CheckStatus.SKIPPED,
            details="Master track not found in analysis",
            is_blocker=False
        )

    # Note: is_muted in our parser is inverted (True = NOT muted)
    # So we check if is_muted is False (meaning actually muted)
    if hasattr(master_track, 'is_muted'):
        if master_track.is_muted:  # In our parser, True = active (not muted)
            return PreflightCheckItem(
                name="Master Mute",
                description="Master track is active",
                status=CheckStatus.PASS,
                details="Master output is not muted",
                is_blocker=False
            )
        else:
            return PreflightCheckItem(
                name="Master Mute",
                description="Master track is muted!",
                status=CheckStatus.FAIL,
                details="Master output is muted - no audio will be rendered",
                is_blocker=True
            )

    return PreflightCheckItem(
        name="Master Mute",
        description="Master track state verified",
        status=CheckStatus.PASS,
        details="Master output is active",
        is_blocker=False
    )


def _check_limiter_ceiling(master_track, threshold_db: float = -0.3) -> PreflightCheckItem:
    """
    Check if master limiter ceiling is at safe level.

    Args:
        master_track: Master track with devices
        threshold_db: Maximum safe ceiling (default -0.3dB for true peak headroom)
    """
    if master_track is None or not hasattr(master_track, 'devices'):
        return PreflightCheckItem(
            name="Limiter Ceiling",
            description="Could not verify limiter settings",
            status=CheckStatus.SKIPPED,
            details="Master track devices not found",
            is_blocker=False
        )

    # Find limiter devices
    limiters = []
    for device in master_track.devices:
        # Check if it's a limiter by name or category
        device_name = getattr(device, 'name', '')
        device_category = getattr(device, 'category', None)

        is_limiter = (
            'Limiter' in device_name or
            (device_category and str(device_category) == 'DeviceCategory.LIMITER')
        )

        if is_limiter and getattr(device, 'is_enabled', True):
            limiters.append(device)

    if not limiters:
        return PreflightCheckItem(
            name="Limiter Ceiling",
            description="No active limiter found on master",
            status=CheckStatus.WARNING,
            details="Consider adding a limiter to prevent clipping",
            is_blocker=False
        )

    # Check ceiling parameter on each limiter
    for limiter in limiters:
        params = getattr(limiter, 'parameters', {})
        ceiling = params.get('Ceiling')

        if ceiling is not None:
            try:
                ceiling_value = float(ceiling)
                if ceiling_value <= threshold_db:
                    return PreflightCheckItem(
                        name="Limiter Ceiling",
                        description="Limiter ceiling is at safe level",
                        status=CheckStatus.PASS,
                        details=f"Ceiling: {ceiling_value:.1f}dB (max: {threshold_db}dB)",
                        is_blocker=False
                    )
                else:
                    return PreflightCheckItem(
                        name="Limiter Ceiling",
                        description="Limiter ceiling is too high",
                        status=CheckStatus.WARNING,
                        details=f"Ceiling: {ceiling_value:.1f}dB (recommended: {threshold_db}dB or lower)",
                        is_blocker=False  # Warning, not blocker
                    )
            except (ValueError, TypeError):
                pass

    # No ceiling parameter found
    return PreflightCheckItem(
        name="Limiter Ceiling",
        description="Limiter found, ceiling not verified",
        status=CheckStatus.WARNING,
        details="Could not read ceiling parameter - verify manually",
        is_blocker=False
    )


def _check_disabled_on_master(master_track) -> PreflightCheckItem:
    """Check for disabled devices on master that might be intentional."""
    if master_track is None or not hasattr(master_track, 'devices'):
        return PreflightCheckItem(
            name="Master Disabled Devices",
            description="Could not verify master devices",
            status=CheckStatus.SKIPPED,
            details="Master track devices not found",
            is_blocker=False
        )

    disabled = [d for d in master_track.devices if hasattr(d, 'is_enabled') and not d.is_enabled]

    if not disabled:
        return PreflightCheckItem(
            name="Master Disabled Devices",
            description="No disabled devices on master",
            status=CheckStatus.PASS,
            details="All master devices are active",
            is_blocker=False
        )
    else:
        names = [getattr(d, 'name', 'Unknown') for d in disabled]
        return PreflightCheckItem(
            name="Master Disabled Devices",
            description=f"Found {len(disabled)} disabled device(s) on master",
            status=CheckStatus.WARNING,
            details=f"Disabled: {', '.join(names[:3])}{'...' if len(names) > 3 else ''}",
            is_blocker=False  # Warning, might be intentional
        )


def _check_clutter(clutter_percentage: float, threshold: float = 30.0) -> PreflightCheckItem:
    """Check project clutter level."""
    if clutter_percentage <= threshold:
        return PreflightCheckItem(
            name="Project Clutter",
            description="Project clutter is within acceptable range",
            status=CheckStatus.PASS,
            details=f"Clutter: {clutter_percentage:.1f}% (max: {threshold}%)",
            is_blocker=False
        )
    else:
        return PreflightCheckItem(
            name="Project Clutter",
            description="Project has high clutter",
            status=CheckStatus.WARNING,
            details=f"Clutter: {clutter_percentage:.1f}% - consider cleaning up disabled devices",
            is_blocker=False
        )


def preflight_check(
    als_path: str,
    min_score: int = 60,
    strict: bool = False,
    analyzer_func=None
) -> Tuple[Optional['PreflightResult'], str]:
    """
    Run pre-export checklist on an Ableton project.

    Args:
        als_path: Path to .als file
        min_score: Minimum health score required (default: 60)
        strict: If True, requires Grade A (80+) regardless of min_score
        analyzer_func: Optional custom analyzer function for testing

    Returns:
        Tuple of (PreflightResult or None, message)
    """
    file_path = Path(als_path)

    if not file_path.exists():
        return (None, f"File not found: {als_path}")

    if file_path.suffix.lower() != '.als':
        return (None, "File must be an Ableton Live Set (.als)")

    # Analyze the file
    try:
        if analyzer_func:
            # Use provided analyzer (for testing)
            analysis, scan_result = analyzer_func(file_path)
        else:
            # Use the actual analyzer
            from device_chain_analyzer import analyze_als_devices
            from effect_chain_doctor import EffectChainDoctor
            from database import ScanResult, ScanResultIssue, _calculate_grade

            analysis = analyze_als_devices(str(file_path))
            doctor = EffectChainDoctor()
            diagnosis = doctor.diagnose(analysis)

            # Build scan result
            issues = []
            for issue in diagnosis.global_issues:
                issues.append(ScanResultIssue(
                    track_name=issue.track_name,
                    severity=issue.severity.value,
                    category=issue.category.value,
                    description=issue.description,
                    fix_suggestion=issue.recommendation
                ))
            for track_diag in diagnosis.track_diagnoses:
                for issue in track_diag.issues:
                    issues.append(ScanResultIssue(
                        track_name=issue.track_name,
                        severity=issue.severity.value,
                        category=issue.category.value,
                        description=issue.description,
                        fix_suggestion=issue.recommendation
                    ))

            scan_result = ScanResult(
                als_path=str(file_path),
                health_score=diagnosis.overall_health,
                grade=_calculate_grade(diagnosis.overall_health),
                total_issues=diagnosis.total_issues,
                critical_issues=diagnosis.critical_issues,
                warning_issues=diagnosis.warning_issues,
                total_devices=diagnosis.total_devices,
                disabled_devices=diagnosis.total_disabled,
                clutter_percentage=diagnosis.clutter_percentage,
                issues=issues
            )
    except Exception as e:
        return (None, f"Failed to analyze file: {e}")

    # Find master track
    master_track = None
    all_tracks = getattr(analysis, 'tracks', [])
    for track in all_tracks:
        if hasattr(track, 'track_type') and track.track_type == 'master':
            master_track = track
            break

    # Run checks
    checks = []

    # 1. Health Score Check (blocker)
    checks.append(_check_health_score(
        scan_result.health_score,
        scan_result.grade,
        min_score,
        strict
    ))

    # 2. Critical Issues Check (blocker)
    checks.append(_check_critical_issues(scan_result.critical_issues))

    # 3. Solo'd Tracks Check (blocker)
    checks.append(_check_solo_tracks(all_tracks))

    # 4. Master Mute Check (blocker)
    checks.append(_check_master_mute(master_track))

    # 5. Limiter Ceiling Check (warning)
    checks.append(_check_limiter_ceiling(master_track))

    # 6. Master Disabled Devices (warning)
    checks.append(_check_disabled_on_master(master_track))

    # 7. Clutter Check (warning)
    checks.append(_check_clutter(scan_result.clutter_percentage))

    # Categorize results
    blockers = [c for c in checks if c.status == CheckStatus.FAIL and c.is_blocker]
    warnings = [c for c in checks if c.status == CheckStatus.WARNING or
                (c.status == CheckStatus.FAIL and not c.is_blocker)]
    passed = [c for c in checks if c.status == CheckStatus.PASS]

    # Determine if ready
    is_ready = len(blockers) == 0

    return (PreflightResult(
        als_path=str(file_path),
        als_filename=file_path.name,
        health_score=scan_result.health_score,
        grade=scan_result.grade,
        is_ready=is_ready,
        checks=checks,
        blockers=blockers,
        warnings=warnings,
        passed=passed,
        min_score=min_score,
        strict_mode=strict,
        total_checks=len(checks),
        passed_count=len(passed),
        failed_count=len(blockers),
        warning_count=len(warnings)
    ), "OK")


def get_preflight_summary(result: PreflightResult) -> str:
    """Generate a text summary of preflight results."""
    lines = []

    # Verdict
    if result.is_ready:
        lines.append("VERDICT: GO - Ready to export!")
    else:
        lines.append("VERDICT: NO-GO - Issues must be resolved")

    lines.append("")
    lines.append(f"Health: {result.health_score}/100 [{result.grade}]")
    lines.append(f"Mode: {'Strict (Grade A required)' if result.strict_mode else f'Normal (min score: {result.min_score})'}")
    lines.append("")

    # Blockers
    if result.blockers:
        lines.append("BLOCKERS (must fix):")
        for check in result.blockers:
            lines.append(f"  X {check.name}: {check.details}")

    # Warnings
    if result.warnings:
        lines.append("")
        lines.append("WARNINGS (optional):")
        for check in result.warnings:
            lines.append(f"  ! {check.name}: {check.details}")

    # Passed
    if result.passed:
        lines.append("")
        lines.append("PASSED:")
        for check in result.passed:
            lines.append(f"  + {check.name}")

    return "\n".join(lines)
