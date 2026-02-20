"""
Delta Reporter Module.

Generate human-readable reports from gap analysis results.
"""

from typing import List, Optional
from .gap_analyzer import GapReport, FeatureGap, FixRecommendation


def format_gap_report(report: GapReport, detail_level: str = "standard") -> str:
    """
    Format gap report at specified detail level.

    Args:
        report: GapReport to format
        detail_level: "summary", "standard", or "detailed"

    Returns:
        Formatted string report
    """
    if detail_level == "summary":
        return format_summary_report(report)
    elif detail_level == "detailed":
        return format_detailed_report(report)
    else:
        return format_standard_report(report)


def format_summary_report(report: GapReport) -> str:
    """Format a brief summary report."""
    lines = [
        "=" * 60,
        "GAP ANALYSIS SUMMARY",
        "=" * 60,
        "",
        f"Track: {report.wip_path}",
        f"Profile: {report.profile_name}",
        "",
        f"Similarity: {report.overall_similarity:.0%}",
        f"Trance Score: {report.trance_score:.2f}",
        f"Style Match: {report.nearest_cluster_name}",
        "",
        "Issues:",
        f"  Critical: {report.gap_count_by_severity.get('critical', 0)}",
        f"  Warning: {report.gap_count_by_severity.get('warning', 0)}",
        f"  Minor: {report.gap_count_by_severity.get('minor', 0)}",
    ]

    # Top 3 fixes
    if report.prioritized_fixes:
        lines.extend(["", "Top Fixes:"])
        for fix in report.prioritized_fixes[:3]:
            lines.append(f"  {fix.priority}. [{fix.severity.upper()}] {fix.action}")

    lines.append("=" * 60)

    return '\n'.join(lines)


def format_standard_report(report: GapReport) -> str:
    """Format a standard-detail report."""
    lines = [
        "=" * 70,
        "                    GAP ANALYSIS REPORT",
        "=" * 70,
        "",
        f"Track: {report.wip_path}",
        f"Profile: {report.profile_name}",
        f"Analysis Date: {report.analysis_date}",
        "",
        "-" * 40,
        "OVERALL ASSESSMENT",
        "-" * 40,
        f"Similarity to References: {report.overall_similarity:.0%}",
        f"Trance Score: {report.trance_score:.2f} / 1.00",
        f"Nearest Style: \"{report.nearest_cluster_name}\"",
        "",
        "-" * 40,
        "ISSUES FOUND",
        "-" * 40,
        f"Critical: {report.gap_count_by_severity.get('critical', 0)}    "
        f"Warning: {report.gap_count_by_severity.get('warning', 0)}    "
        f"Minor: {report.gap_count_by_severity.get('minor', 0)}",
    ]

    # Problematic areas
    if report.most_problematic_areas:
        lines.extend(["", "Problem Areas: " + ", ".join(report.most_problematic_areas)])

    # Critical issues
    if report.critical_gaps:
        lines.extend(["", "-" * 40, "CRITICAL ISSUES", "-" * 40])
        for gap in report.critical_gaps:
            lines.append(f"  ✗ {gap.description}")
            lines.append(f"    → {gap.recommendation}")
            lines.append("")

    # Warnings
    if report.warning_gaps:
        lines.extend(["-" * 40, "WARNINGS", "-" * 40])
        for gap in report.warning_gaps:
            lines.append(f"  ⚠ {gap.description}")
            lines.append(f"    → {gap.recommendation}")
            lines.append("")

    # Top recommendations
    lines.extend(["-" * 40, "TOP RECOMMENDATIONS", "-" * 40])
    for fix in report.prioritized_fixes[:5]:
        severity_icon = "✗" if fix.severity == "critical" else "⚠" if fix.severity == "warning" else "·"
        lines.append(f"  {fix.priority}. [{severity_icon}] {fix.action}")
        lines.append(f"     Difficulty: {fix.difficulty} | {fix.expected_improvement}")
        lines.append("")

    lines.append("=" * 70)

    return '\n'.join(lines)


def format_detailed_report(report: GapReport) -> str:
    """Format a comprehensive detailed report."""
    lines = [
        "=" * 80,
        "                      DETAILED GAP ANALYSIS REPORT",
        "=" * 80,
        "",
        _format_section_header("TRACK INFORMATION"),
        f"  Path: {report.wip_path}",
        f"  Profile: {report.profile_name}",
        f"  Analysis Date: {report.analysis_date}",
        "",
        _format_section_header("OVERALL ASSESSMENT"),
        f"  Similarity to References: {report.overall_similarity:.1%}",
        f"  Trance Score: {report.trance_score:.3f} / 1.000",
        f"  Nearest Style Cluster: [{report.nearest_cluster}] \"{report.nearest_cluster_name}\"",
        f"  Cluster Distance: {report.cluster_distance:.3f}",
        "",
        _format_section_header("ISSUE SUMMARY"),
        f"  Critical Issues: {report.gap_count_by_severity.get('critical', 0)}",
        f"  Warnings: {report.gap_count_by_severity.get('warning', 0)}",
        f"  Minor Issues: {report.gap_count_by_severity.get('minor', 0)}",
        f"  OK Features: {report.gap_count_by_severity.get('ok', 0)}",
        "",
    ]

    # Problem areas
    if report.most_problematic_areas:
        lines.append(f"  Most Problematic Areas:")
        for area in report.most_problematic_areas:
            lines.append(f"    • {area}")
        lines.append("")

    # Critical issues section
    if report.critical_gaps:
        lines.extend([
            _format_section_header("CRITICAL ISSUES (Must Fix)"),
            ""
        ])
        for i, gap in enumerate(report.critical_gaps, 1):
            lines.extend(_format_gap_detail(gap, i, "CRITICAL"))
            lines.append("")

    # Warning issues section
    if report.warning_gaps:
        lines.extend([
            _format_section_header("WARNINGS (Should Fix)"),
            ""
        ])
        for i, gap in enumerate(report.warning_gaps, 1):
            lines.extend(_format_gap_detail(gap, i, "WARNING"))
            lines.append("")

    # Minor issues section
    if report.minor_gaps:
        lines.extend([
            _format_section_header("MINOR ISSUES (Consider Fixing)"),
            ""
        ])
        for i, gap in enumerate(report.minor_gaps, 1):
            lines.extend(_format_gap_detail(gap, i, "MINOR"))
            lines.append("")

    # Feature-by-feature breakdown
    lines.extend([
        _format_section_header("COMPLETE FEATURE BREAKDOWN"),
        "",
        _format_feature_table_header(),
    ])

    for gap in report.all_gaps:
        lines.append(_format_feature_table_row(gap))

    lines.append("")

    # Prioritized recommendations
    lines.extend([
        _format_section_header("PRIORITIZED FIX RECOMMENDATIONS"),
        ""
    ])

    for fix in report.prioritized_fixes:
        lines.extend(_format_fix_recommendation(fix))
        lines.append("")

    lines.append("=" * 80)

    return '\n'.join(lines)


def _format_section_header(title: str) -> str:
    """Format a section header."""
    return f"──── {title} " + "─" * (60 - len(title) - 5)


def _format_gap_detail(gap: FeatureGap, number: int, severity: str) -> List[str]:
    """Format detailed gap information."""
    lines = [
        f"  {number}. [{severity}] {gap.feature_name.replace('_', ' ').title()}",
        f"     WIP Value: {gap.wip_value:.3f}",
        f"     Target: {gap.target_value:.3f} (range: {gap.acceptable_range[0]:.3f} - {gap.acceptable_range[1]:.3f})",
        f"     Delta: {gap.absolute_delta:+.3f} ({gap.z_score:+.2f}σ)",
        f"     Direction: {gap.direction.upper()}",
        f"     ",
        f"     Issue: {gap.description}",
        f"     Fix: {gap.recommendation}",
        f"     Difficulty: {gap.fix_difficulty}",
    ]
    return lines


def _format_feature_table_header() -> str:
    """Format feature comparison table header."""
    return (
        f"  {'Feature':<30} {'WIP':>10} {'Target':>10} {'Delta':>10} "
        f"{'Z-Score':>8} {'Status':>10}"
    )


def _format_feature_table_row(gap: FeatureGap) -> str:
    """Format a single feature row in the comparison table."""
    status_icons = {
        'critical': '✗✗',
        'warning': '✗ ',
        'minor': '· ',
        'ok': '✓ '
    }

    status = status_icons.get(gap.severity, '  ')
    feature = gap.feature_name[:28]

    return (
        f"  {feature:<30} {gap.wip_value:>10.3f} {gap.target_value:>10.3f} "
        f"{gap.absolute_delta:>+10.3f} {gap.z_score:>+8.2f} {status:>10}"
    )


def _format_fix_recommendation(fix: FixRecommendation) -> List[str]:
    """Format a fix recommendation."""
    severity_markers = {
        'critical': '‼️ ',
        'warning': '⚠️ ',
        'minor': 'ℹ️ '
    }
    marker = severity_markers.get(fix.severity, '  ')

    return [
        f"  {fix.priority}. {marker}[{fix.severity.upper()}] {fix.feature.replace('_', ' ').title()}",
        f"     Action: {fix.action}",
        f"     Expected: {fix.expected_improvement}",
        f"     Difficulty: {fix.difficulty}",
    ]


def format_json_report(report: GapReport) -> str:
    """Format report as JSON string."""
    import json
    return json.dumps(report.to_dict(), indent=2)
