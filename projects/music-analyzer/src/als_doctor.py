"""
ALS Doctor - Unified CLI for Ableton Project Analysis

Commands:
  diagnose <file.als>           - Full diagnosis of a single project
  compare <before.als> <after.als> - Compare two versions
  scan <directory>              - Batch scan and rank projects
  quick <file.als>              - Quick health check (just the score)

  db init                       - Initialize the database
  db changes <song>             - Show changes between versions (with impact assessments)
  db history <song>             - Show version history timeline
  db trend <song>               - Show health trend analysis
  db insights                   - Show patterns across all projects
  db status                     - Show library status overview
  db list                       - List all tracked projects
  db compute-changes <song>     - Compute and store changes for a project

  # Phase 2: Intelligence Commands
  db whatif <song>              - Show what-if predictions for potential changes
  db recommend                  - Show smart recommendations based on patterns
  db patterns                   - Show all learned patterns with statistics

Examples:
  python als_doctor.py diagnose "D:/Music/MyProject/project.als"
  python als_doctor.py compare "v1.als" "v2.als"
  python als_doctor.py scan "D:/Ableton Projects" --limit 20
  python als_doctor.py quick "project.als"

  python als_doctor.py db init
  python als_doctor.py db changes "22 Project" --detailed
  python als_doctor.py db history "35"
  python als_doctor.py db trend "MyTrack"
  python als_doctor.py db insights
  python als_doctor.py db whatif "22 Project"
  python als_doctor.py db recommend
  python als_doctor.py db patterns --min-samples 3
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional


def cmd_diagnose(args):
    """Run full diagnosis on a project."""
    from effect_chain_doctor import diagnose_project, EffectChainDoctor

    print(f"Analyzing: {args.file}")
    diagnosis = diagnose_project(args.file, verbose=args.verbose)
    doctor = EffectChainDoctor()
    print(doctor.generate_report(diagnosis))

    if args.json:
        import json
        with open(args.json, 'w') as f:
            # Simple JSON export
            data = {
                "file": diagnosis.file_path,
                "health_score": diagnosis.overall_health,
                "total_issues": diagnosis.total_issues,
                "critical_issues": diagnosis.critical_issues,
                "warning_issues": diagnosis.warning_issues,
                "total_devices": diagnosis.total_devices,
                "disabled_devices": diagnosis.total_disabled,
                "clutter_percentage": diagnosis.clutter_percentage
            }
            json.dump(data, f, indent=2)
        print(f"\nJSON saved to: {args.json}")

    if args.html:
        from html_reports import (
            generate_project_report, ProjectReportData, ReportIssue,
            get_default_report_path
        )

        # Build report data from diagnosis
        issues = []
        for issue in diagnosis.issues:
            issues.append(ReportIssue(
                track_name=issue.track_name or 'Unknown',
                severity=issue.severity or 'warning',
                category=issue.category or 'general',
                description=issue.description or '',
                fix_suggestion=issue.fix_suggestion
            ))

        report_data = ProjectReportData(
            song_name=Path(args.file).stem,
            folder_path=str(Path(args.file).parent),
            als_filename=Path(args.file).name,
            als_path=str(args.file),
            health_score=diagnosis.overall_health,
            grade=diagnosis.grade,
            total_issues=diagnosis.total_issues,
            critical_issues=diagnosis.critical_issues,
            warning_issues=diagnosis.warning_issues,
            total_devices=diagnosis.total_devices,
            disabled_devices=diagnosis.total_disabled,
            clutter_percentage=diagnosis.clutter_percentage,
            scanned_at=datetime.now(),
            issues=issues
        )

        # Determine output path
        if args.html is True or args.html == '':
            output_path = get_default_report_path('project', Path(args.file).stem)
        else:
            output_path = Path(args.html)

        _, saved_path = generate_project_report(report_data, output_path)
        print(f"\nHTML report saved to: {saved_path}")


def cmd_compare(args):
    """Compare two project versions."""
    from project_differ import compare_projects, ProjectDiffer

    print(f"Comparing:")
    print(f"  BEFORE: {args.before}")
    print(f"  AFTER:  {args.after}")
    print()

    diff = compare_projects(args.before, args.after, verbose=args.verbose)
    differ = ProjectDiffer()
    print(differ.generate_report(diff))


def cmd_scan(args):
    """Batch scan projects in a directory."""
    from batch_scanner import BatchScanner
    import re

    print(f"Scanning: {args.directory}")
    if args.limit:
        print(f"Limit: {args.limit} files")
    if args.min_number:
        print(f"Filter: Projects numbered {args.min_number}+")
    print()

    scanner = BatchScanner(verbose=args.verbose)
    path = Path(args.directory)

    # Get all als files
    als_files = list(path.rglob("*.als"))

    # Filter by project number if specified
    if args.min_number:
        filtered = []
        for f in als_files:
            # Extract number from parent folder name (e.g., "35 Project" -> 35)
            parent = f.parent.name
            match = re.match(r'^(\d+)', parent)
            if match:
                num = int(match.group(1))
                if num >= args.min_number:
                    filtered.append(f)
        als_files = filtered
        print(f"Found {len(als_files)} projects numbered {args.min_number}+")

    # Apply limit
    if args.limit:
        als_files = als_files[:args.limit]

    if not als_files:
        print("No matching projects found.")
        return

    result = scanner.scan_files([str(f) for f in als_files])
    print(scanner.generate_report(result))


def cmd_quick(args):
    """Quick health check - just the score."""
    from effect_chain_doctor import diagnose_project

    diagnosis = diagnose_project(args.file, verbose=False)

    # Determine grade
    score = diagnosis.overall_health
    if score >= 80:
        grade = "A"
        status = "GREAT"
    elif score >= 60:
        grade = "B"
        status = "GOOD"
    elif score >= 40:
        grade = "C"
        status = "NEEDS WORK"
    elif score >= 20:
        grade = "D"
        status = "SIGNIFICANT ISSUES"
    else:
        grade = "F"
        status = "MAJOR PROBLEMS"

    print(f"[{grade}] {score}/100 - {status}")
    print(f"    {diagnosis.total_issues} issues ({diagnosis.critical_issues} critical, {diagnosis.warning_issues} warnings)")
    print(f"    {diagnosis.total_devices} devices, {diagnosis.total_disabled} disabled ({diagnosis.clutter_percentage:.0f}% clutter)")


# ==================== DATABASE COMMANDS ====================


# Change category mapping for better organization
CHANGE_CATEGORIES = {
    # Structural changes - affect arrangement/composition
    'track_added': 'structural',
    'track_removed': 'structural',
    # Plugin changes - adding/removing/toggling effects
    'device_added': 'plugin',
    'device_removed': 'plugin',
    'device_enabled': 'plugin',
    'device_disabled': 'plugin',
}

# Device types that are typically mixing-related
MIXING_DEVICE_TYPES = {
    'Eq8', 'Eq3', 'FilterDelay', 'Compressor', 'GlueCompressor', 'MultibandDynamics',
    'Limiter', 'Gate', 'AutoFilter', 'Saturator', 'Utility', 'ChannelEq',
    'Spectrum', 'Tuner', 'Redux', 'Erosion', 'Vinyl',
}

# Device types that are typically arrangement/sound-design related
ARRANGEMENT_DEVICE_TYPES = {
    'Reverb', 'Delay', 'Chorus', 'Flanger', 'Phaser', 'FrequencyShifter',
    'PingPongDelay', 'FilterDelay', 'GrainDelay', 'Resonators', 'Vocoder',
    'BeatRepeat', 'Looper', 'Pedal',
}


def categorize_change(change_type: str, device_type: str = None) -> str:
    """
    Categorize a change into structural, mixing, arrangement, or plugin.

    Args:
        change_type: The type of change (device_added, track_removed, etc.)
        device_type: The device type if applicable (Eq8, Compressor, etc.)

    Returns:
        Category string: 'structural', 'mixing', 'arrangement', or 'plugin'
    """
    # Track changes are always structural
    if change_type.startswith('track_'):
        return 'structural'

    # Device changes need further categorization
    if device_type:
        if device_type in MIXING_DEVICE_TYPES:
            return 'mixing'
        elif device_type in ARRANGEMENT_DEVICE_TYPES:
            return 'arrangement'

    return 'plugin'


def format_health_delta(delta: int) -> str:
    """Format health delta with appropriate symbol."""
    if delta > 0:
        return f"+{delta}"
    elif delta < 0:
        return str(delta)
    return "="


def format_trend_symbol(direction: str) -> str:
    """Format trend direction with Unicode symbol."""
    symbols = {
        'improving': '↑',
        'declining': '↓',
        'stable': '→',
        'up': '↑',
        'down': '↓',
        'new': '★',
    }
    return symbols.get(direction, '?')


def cmd_db_init(args):
    """Initialize the database."""
    from database import db_init

    success, message = db_init()
    print(message)
    if not success:
        sys.exit(1)


def cmd_db_status(args):
    """Show library status overview."""
    from database import get_library_status, generate_grade_bar, list_projects

    result, message = get_library_status()

    if not result:
        print(f"Error: {message}")
        sys.exit(1)

    # Generate HTML report if requested
    if hasattr(args, 'html') and args.html:
        from html_reports import (
            generate_library_report, LibraryReportData, GradeData,
            get_default_report_path
        )

        # Build project list for the report
        projects, _ = list_projects(sort_by='name')
        project_list = []
        for p in projects:
            project_list.append({
                'song_name': p.song_name,
                'version_count': p.version_count,
                'best_score': p.best_score,
                'best_grade': p.best_grade,
                'latest_score': p.latest_score,
                'latest_grade': p.latest_grade,
                'trend': p.trend
            })

        report_data = LibraryReportData(
            total_projects=result.total_projects,
            total_versions=result.total_versions,
            total_issues=result.total_issues,
            last_scan_date=result.last_scan_date,
            grade_distribution=[
                GradeData(grade=g.grade, count=g.count, percentage=g.percentage)
                for g in result.grade_distribution
            ],
            ready_to_release=result.ready_to_release,
            needs_work=result.needs_work,
            projects=project_list
        )

        # Determine output path
        if args.html is True or args.html == '':
            output_path = get_default_report_path('library')
        else:
            output_path = Path(args.html)

        _, saved_path = generate_library_report(report_data, output_path)
        print(f"HTML report saved to: {saved_path}")
        return

    print("=" * 60)
    print("LIBRARY STATUS")
    print("=" * 60)
    print()
    print(f"  Projects: {result.total_projects}")
    print(f"  Versions: {result.total_versions}")
    print(f"  Issues:   {result.total_issues}")
    if result.last_scan_date:
        print(f"  Last scan: {result.last_scan_date.strftime('%Y-%m-%d %H:%M')}")
    print()

    # Grade distribution
    print("-" * 60)
    print("GRADE DISTRIBUTION")
    print("-" * 60)

    for grade in result.grade_distribution:
        bar = generate_grade_bar(grade.count, result.total_versions, max_width=30)
        print(f"  [{grade.grade}] {bar} {grade.count} ({grade.percentage:.1f}%)")
    print()

    # Ready to release
    if result.ready_to_release:
        print("-" * 60)
        print("READY TO RELEASE (Grade A)")
        print("-" * 60)
        for filename, score, song_name in result.ready_to_release:
            print(f"  ✓ {song_name}: {filename} ({score}/100)")
        print()

    # Needs work
    if result.needs_work:
        print("-" * 60)
        print("NEEDS WORK (Grade D-F)")
        print("-" * 60)
        for filename, score, song_name in result.needs_work:
            print(f"  ✗ {song_name}: {filename} ({score}/100)")
        print()


def cmd_db_list(args):
    """List all tracked projects."""
    from database import list_projects

    projects, stats = list_projects(sort_by=args.sort or 'name')

    if not projects:
        print("No projects found in database.")
        print("Run 'als-doctor scan <directory> --save' to add projects.")
        return

    print("=" * 70)
    print(f"TRACKED PROJECTS ({stats['projects']} projects, {stats['versions']} versions)")
    print("=" * 70)
    print()
    print(f"{'Song':<25} {'Versions':>8} {'Best':>6} {'Latest':>8} {'Trend':>6}")
    print("-" * 70)

    for p in projects:
        trend_sym = format_trend_symbol(p.trend)
        print(f"{p.song_name:<25} {p.version_count:>8} {p.best_grade:>3}/{p.best_score:<3} {p.latest_grade:>3}/{p.latest_score:<3} {trend_sym:>6}")

    print()


def cmd_db_history(args):
    """Show version history timeline for a project."""
    from database import get_project_history

    result, message = get_project_history(args.song)

    if not result:
        print(f"Error: {message}")
        sys.exit(1)

    # Generate HTML report if requested
    if hasattr(args, 'html') and args.html:
        from html_reports import (
            generate_history_report, HistoryReportData, ReportVersion,
            get_default_report_path
        )

        # Build report versions
        report_versions = []
        for v in result.versions:
            report_versions.append(ReportVersion(
                id=v.id,
                filename=v.als_filename,
                path=v.als_path,
                health_score=v.health_score,
                grade=v.grade,
                total_issues=v.total_issues,
                critical_issues=v.critical_issues,
                warning_issues=v.warning_issues,
                scanned_at=v.scanned_at,
                delta=v.delta,
                is_best=v.is_best,
                is_current=v.is_current
            ))

        # Build best/current versions
        best_version = None
        current_version = None
        if result.best_version:
            best_version = ReportVersion(
                id=result.best_version.id,
                filename=result.best_version.als_filename,
                path=result.best_version.als_path,
                health_score=result.best_version.health_score,
                grade=result.best_version.grade,
                total_issues=result.best_version.total_issues,
                critical_issues=result.best_version.critical_issues,
                warning_issues=result.best_version.warning_issues,
                scanned_at=result.best_version.scanned_at,
                is_best=True
            )
        if result.current_version:
            current_version = ReportVersion(
                id=result.current_version.id,
                filename=result.current_version.als_filename,
                path=result.current_version.als_path,
                health_score=result.current_version.health_score,
                grade=result.current_version.grade,
                total_issues=result.current_version.total_issues,
                critical_issues=result.current_version.critical_issues,
                warning_issues=result.current_version.warning_issues,
                scanned_at=result.current_version.scanned_at,
                is_current=True
            )

        report_data = HistoryReportData(
            song_name=result.song_name,
            folder_path=result.folder_path,
            versions=report_versions,
            best_version=best_version,
            current_version=current_version
        )

        # Determine output path
        if args.html is True or args.html == '':
            output_path = get_default_report_path('history', result.song_name)
        else:
            output_path = Path(args.html)

        _, saved_path = generate_history_report(report_data, output_path)
        print(f"HTML report saved to: {saved_path}")
        return

    print("=" * 70)
    print(f"VERSION HISTORY: {result.song_name}")
    print("=" * 70)
    print(f"Folder: {result.folder_path}")
    print()

    # Summary
    if result.best_version and result.current_version:
        print(f"Best version:    {result.best_version.als_filename} ({result.best_version.health_score}/100, {result.best_version.grade})")
        print(f"Current version: {result.current_version.als_filename} ({result.current_version.health_score}/100, {result.current_version.grade})")

        if result.best_version.id != result.current_version.id:
            diff = result.current_version.health_score - result.best_version.health_score
            if diff < 0:
                print(f"  ⚠ Current version is {abs(diff)} points below best")
        print()

    # Timeline
    print("-" * 70)
    print("TIMELINE")
    print("-" * 70)
    print(f"{'#':<3} {'Version':<30} {'Score':>6} {'Grade':>6} {'Delta':>7} {'Date'}")
    print("-" * 70)

    for i, v in enumerate(result.versions, 1):
        delta_str = format_health_delta(v.delta) if v.delta is not None else "-"
        best_marker = " ★" if v.is_best else ""
        date_str = v.scanned_at.strftime('%Y-%m-%d') if v.scanned_at else ""

        print(f"{i:<3} {v.als_filename:<30} {v.health_score:>6} {v.grade:>6} {delta_str:>7} {date_str}{best_marker}")

    print()

    # ASCII sparkline of health scores
    if len(result.versions) > 1:
        print("-" * 70)
        print("HEALTH TREND (ASCII)")
        print("-" * 70)
        scores = [v.health_score for v in result.versions]
        min_s, max_s = min(scores), max(scores)
        range_s = max_s - min_s if max_s != min_s else 1

        # Normalize to 0-7 for sparkline characters
        sparkline_chars = "▁▂▃▄▅▆▇█"
        sparkline = ""
        for s in scores:
            idx = int((s - min_s) / range_s * 7)
            sparkline += sparkline_chars[idx]

        print(f"  {min_s} {sparkline} {max_s}")
        print()


def format_impact_badge(category: str, confidence: str) -> str:
    """Format impact category with confidence as a badge."""
    badges = {
        'helped': '✓ HELPED',
        'hurt': '✗ HURT',
        'neutral': '○ NEUTRAL',
        'unknown': '? UNKNOWN'
    }
    conf_markers = {
        'HIGH': '●●●',
        'MEDIUM': '●●○',
        'LOW': '●○○',
        'NONE': '○○○'
    }
    badge = badges.get(category, '?')
    conf = conf_markers.get(confidence, '○○○')
    return f"{badge} [{conf}]"


def cmd_db_changes(args):
    """Show changes between versions of a project with impact assessments."""
    from database import get_project_changes, compute_and_store_all_changes, get_learned_patterns

    # First check if changes are computed
    result, message = get_project_changes(args.song)

    if not result:
        print(f"Error: {message}")
        sys.exit(1)

    # Check if we have changes stored - if not, offer to compute them
    has_changes = any(c.changes for c in result.comparisons)

    if not has_changes and not args.no_compute:
        print(f"No changes stored for '{result.song_name}'. Computing now...")
        success, compute_msg, total = compute_and_store_all_changes(args.song)
        if success:
            print(f"  {compute_msg}")
            # Re-fetch with computed changes
            result, message = get_project_changes(args.song)
        else:
            print(f"  Warning: {compute_msg}")
        print()

    # Load learned patterns for impact assessments
    patterns, _ = get_learned_patterns(min_occurrences=2)
    pattern_lookup = {}
    for p in patterns:
        key = (p.change_type, p.device_type or 'unknown')
        pattern_lookup[key] = p

    print("=" * 70)
    print(f"CHANGES: {result.song_name}")
    print("=" * 70)
    print()

    # Show legend
    if args.detailed:
        print("Legend: ✓=Helped ✗=Hurt ○=Neutral ?=Unknown | Confidence: ●●●=High ●●○=Med ●○○=Low")
        print()

    for comp in result.comparisons:
        # Header for this comparison
        verdict = "IMPROVEMENT" if comp.is_improvement else "REGRESSION" if comp.health_delta < 0 else "NO CHANGE"
        verdict_color = "+" if comp.is_improvement else "-" if comp.health_delta < 0 else "="
        print(f"─── {comp.before_filename} → {comp.after_filename} [{verdict}] ───")
        print(f"    Health: {comp.before_health} → {comp.after_health} ({format_health_delta(comp.health_delta)})")
        print(f"    Issues: {comp.before_issues} → {comp.after_issues} ({format_health_delta(-comp.issues_delta)} issues)")
        print()

        if comp.changes:
            # Group changes by impact category for Phase 2 intelligence
            by_impact = {'helped': [], 'hurt': [], 'neutral': [], 'unknown': []}
            by_category = {'structural': [], 'mixing': [], 'arrangement': [], 'plugin': []}

            for change in comp.changes:
                category = categorize_change(change.change_type, change.device_type)
                by_category[category].append(change)

                # Determine impact from historical patterns
                key = (change.change_type, change.device_type or 'unknown')
                pattern = pattern_lookup.get(key)

                if pattern:
                    if pattern.avg_health_delta > 2:
                        impact = 'helped'
                    elif pattern.avg_health_delta < -2:
                        impact = 'hurt'
                    else:
                        impact = 'neutral'
                    # Also attach pattern to change for detailed view
                    change._pattern = pattern
                else:
                    impact = 'unknown'
                    change._pattern = None

                by_impact[impact].append(change)

            # Display by category
            category_labels = {
                'structural': '📁 STRUCTURAL',
                'mixing': '🎚️ MIXING',
                'arrangement': '🎵 ARRANGEMENT',
                'plugin': '🔌 PLUGIN'
            }

            for category, changes in by_category.items():
                if not changes:
                    continue

                print(f"    {category_labels[category]}:")
                for change in changes[:10]:  # Limit to 10 per category
                    action = change.change_type.replace('device_', '').replace('track_', '')

                    # Determine impact indicator
                    pattern = getattr(change, '_pattern', None)
                    if pattern:
                        if pattern.avg_health_delta > 2:
                            impact_sym = "✓"
                            confidence = pattern.confidence
                        elif pattern.avg_health_delta < -2:
                            impact_sym = "✗"
                            confidence = pattern.confidence
                        else:
                            impact_sym = "○"
                            confidence = pattern.confidence
                    elif change.likely_helped:
                        impact_sym = "✓"
                        confidence = "LOW"
                    elif not change.likely_helped and change.health_delta < 0:
                        impact_sym = "✗"
                        confidence = "LOW"
                    else:
                        impact_sym = " "
                        confidence = "NONE"

                    if change.device_name:
                        line = f"      [{impact_sym}] {action}: {change.device_name} ({change.device_type}) on {change.track_name}"
                    else:
                        line = f"      [{impact_sym}] {action}: {change.track_name}"

                    # Add pattern insight in detailed mode
                    if args.detailed and pattern:
                        line += f" | {pattern.avg_health_delta:+.1f} avg ({pattern.total_occurrences}x seen)"

                    print(line)

                if len(changes) > 10:
                    print(f"      ... and {len(changes) - 10} more")
                print()

            # Show impact summary in detailed mode
            if args.detailed:
                helped_count = len(by_impact['helped'])
                hurt_count = len(by_impact['hurt'])
                neutral_count = len(by_impact['neutral'])
                unknown_count = len(by_impact['unknown'])
                print(f"    IMPACT SUMMARY: {helped_count} likely helped, {hurt_count} likely hurt, {neutral_count} neutral, {unknown_count} unknown")
                print()
        else:
            print("    No detailed changes stored. Run with --compute to analyze.")
            print()

    print()


def cmd_db_trend(args):
    """Show health trend analysis for a project with enhanced visualization."""
    from database import analyze_project_trend, get_learned_patterns

    result, message = analyze_project_trend(args.song)

    if not result:
        print(f"Error: {message}")
        sys.exit(1)

    print("=" * 70)
    print(f"TREND ANALYSIS: {result.song_name}")
    print("=" * 70)
    print()

    # Summary with visual trend indicator
    trend_sym = format_trend_symbol(result.trend_direction)
    trend_visual = {
        'improving': '📈',
        'declining': '📉',
        'stable': '📊',
    }.get(result.trend_direction, '📊')

    print(f"Direction: {trend_visual} {trend_sym} {result.trend_direction.upper()} (strength: {result.trend_strength:.0%})")
    print()
    print(result.summary)
    print()

    # Statistics in two columns
    print("-" * 70)
    print("STATISTICS")
    print("-" * 70)
    print(f"  {'Total versions:':<22} {result.total_versions:<10} {'Avg delta/version:':<22} {result.avg_delta_per_version:+.1f}")
    print(f"  {'First health:':<22} {result.first_health:<10} {'Recent momentum:':<22} {result.recent_momentum:+.1f}")
    print(f"  {'Latest health:':<22} {result.latest_health:<10} {'Biggest improvement:':<22} +{result.biggest_improvement}")
    print(f"  {'Best health:':<22} {result.best_health:<10} {'Biggest regression:':<22} -{result.biggest_regression}")
    print(f"  {'Worst health:':<22} {result.worst_health:<10} {'Average health:':<22} {result.avg_health:.1f}")
    print()

    # Visual timeline - enhanced ASCII graph
    print("-" * 70)
    print("HEALTH TIMELINE (vertical axis: 0-100)")
    print("-" * 70)

    scores = [p.health_score for p in result.timeline]
    min_score = min(scores)
    max_score = max(scores)

    # Draw ASCII graph with scale
    graph_height = 10
    graph_width = min(len(result.timeline), 50)

    # Scale scores to graph height
    if max_score == min_score:
        scaled = [graph_height // 2] * len(scores)
    else:
        scaled = [int((s - min_score) / (max_score - min_score) * (graph_height - 1)) for s in scores]

    # Draw from top to bottom
    for row in range(graph_height - 1, -1, -1):
        if row == graph_height - 1:
            label = f"{max_score:>3}"
        elif row == 0:
            label = f"{min_score:>3}"
        elif row == graph_height // 2:
            mid_val = (max_score + min_score) // 2
            label = f"{mid_val:>3}"
        else:
            label = "   "

        line = f"  {label} │"
        for i, s in enumerate(scaled[:graph_width]):
            if s == row:
                # Check if this is an improvement or regression from previous
                if i > 0:
                    if scores[i] > scores[i-1]:
                        line += "▲"  # Improvement
                    elif scores[i] < scores[i-1]:
                        line += "▼"  # Regression
                    else:
                        line += "●"  # Same
                else:
                    line += "●"  # First point
            elif s > row:
                # Fill below the line
                line += "│" if i == 0 or scaled[i-1] <= row else " "
            else:
                line += " "
        print(line)

    # X-axis
    print(f"      └{'─' * len(scaled[:graph_width])}")

    # Version labels
    if len(result.timeline) <= 20:
        print(f"       {''.join([str(i+1)[-1] for i in range(len(result.timeline[:graph_width]))])}")
        print(f"       Version numbers (1={result.timeline[0].als_filename[:15]}...)")
    else:
        print(f"       ← Oldest ({result.timeline[0].als_filename[:15]}...) to Newest ({result.timeline[-1].als_filename[:15]}...) →")

    print()

    # Sparkline version (compact)
    sparkline_chars = "▁▂▃▄▅▆▇█"
    if max_score != min_score:
        sparkline = ""
        for s in scores:
            idx = int((s - min_score) / (max_score - min_score) * 7)
            sparkline += sparkline_chars[idx]
        print(f"  Sparkline: {min_score} {sparkline} {max_score}")
        print()

    # Show milestones if any significant changes
    if hasattr(result, 'milestones') and result.milestones:
        print("-" * 70)
        print("KEY MILESTONES")
        print("-" * 70)
        for milestone in result.milestones[:5]:
            print(f"  • {milestone}")
        print()


def cmd_db_insights(args):
    """Show patterns and insights across all projects with recommendations."""
    from database import get_insights, get_learned_patterns

    result, message = get_insights()

    if not result:
        print(f"Error: {message}")
        sys.exit(1)

    print("=" * 70)
    print("INSIGHTS: PATTERNS ACROSS ALL PROJECTS")
    print("=" * 70)
    print()
    print(f"Data: {result.total_comparisons} version comparisons, {result.total_changes} changes analyzed")
    print()

    if result.insufficient_data:
        print("⚠ Insufficient data for reliable insights.")
        print("  Keep scanning versions to build up pattern data.")
        print(f"  Current: {result.total_comparisons} comparisons (need at least 10)")
        print()
        print("To build more data:")
        print("  1. Scan project files: als-doctor scan <directory>")
        print("  2. Compute changes: als-doctor db compute-changes <song>")
        return

    # Get learned patterns for recommendations
    patterns, _ = get_learned_patterns(min_occurrences=3)
    high_confidence_patterns = [p for p in patterns if p.confidence == 'HIGH']

    # Patterns that help
    if result.patterns_that_help:
        print("-" * 70)
        print("✓ PATTERNS THAT IMPROVE HEALTH")
        print("-" * 70)
        for p in result.patterns_that_help[:5]:
            action = p.change_type.replace('device_', '').replace('track_', '')
            device = p.device_type or 'various'
            conf_badge = {'HIGH': '●●●', 'MEDIUM': '●●○', 'LOW': '●○○'}.get(p.confidence, '○○○')
            print(f"  [{conf_badge}] {action} {device}: avg {p.avg_health_delta:+.1f} health ({p.occurrence_count}x)")
        print()

    # Patterns that hurt
    if result.patterns_that_hurt:
        print("-" * 70)
        print("✗ PATTERNS THAT HURT HEALTH")
        print("-" * 70)
        for p in result.patterns_that_hurt[:5]:
            action = p.change_type.replace('device_', '').replace('track_', '')
            device = p.device_type or 'various'
            conf_badge = {'HIGH': '●●●', 'MEDIUM': '●●○', 'LOW': '●○○'}.get(p.confidence, '○○○')
            print(f"  [{conf_badge}] {action} {device}: avg {p.avg_health_delta:+.1f} health ({p.occurrence_count}x)")
        print()

    # Common mistakes
    if result.common_mistakes:
        print("-" * 70)
        print("⚠ COMMON MISTAKES TO AVOID")
        print("-" * 70)
        for mistake in result.common_mistakes:
            print(f"  • {mistake.description}")
            print(f"    Seen {mistake.occurrence_count}x, avg {mistake.avg_health_impact:+.1f} health")
            if mistake.example_devices:
                print(f"    Examples: {', '.join(mistake.example_devices[:3])}")
            print()

    # Phase 2: Add actionable recommendations
    if high_confidence_patterns:
        helpful_high = [p for p in high_confidence_patterns if p.avg_health_delta > 3]
        harmful_high = [p for p in high_confidence_patterns if p.avg_health_delta < -3]

        if helpful_high or harmful_high:
            print("-" * 70)
            print("💡 HIGH-CONFIDENCE RECOMMENDATIONS")
            print("-" * 70)

            if helpful_high:
                print("  DO MORE:")
                for p in helpful_high[:3]:
                    action = p.change_type.replace('device_', '').replace('track_', '')
                    device = p.device_type or 'any device'
                    print(f"    → {action.capitalize()} {device} (avg +{p.avg_health_delta:.1f}, {p.total_occurrences}x proven)")

            if harmful_high:
                print("  AVOID:")
                for p in harmful_high[:3]:
                    action = p.change_type.replace('device_', '').replace('track_', '')
                    device = p.device_type or 'any device'
                    print(f"    → {action.capitalize()} {device} (avg {p.avg_health_delta:.1f}, {p.total_occurrences}x proven)")

            print()

    # Footer with next steps
    print("-" * 70)
    print("NEXT STEPS")
    print("-" * 70)
    print("  • Run 'als-doctor db recommend' for personalized recommendations")
    print("  • Run 'als-doctor db whatif <song>' for specific predictions")
    print("  • Run 'als-doctor db patterns' to see all learned patterns")
    print()


def cmd_db_compute_changes(args):
    """Compute and store changes between all versions of a project."""
    from database import compute_and_store_all_changes

    print(f"Computing changes for '{args.song}'...")

    success, message, total = compute_and_store_all_changes(args.song)

    if success:
        print(f"✓ {message}")
    else:
        print(f"✗ Error: {message}")
        sys.exit(1)


# ==================== PHASE 2: INTELLIGENCE COMMANDS ====================


def cmd_db_whatif(args):
    """Show what-if predictions for a project."""
    from database import get_what_if_predictions, find_project_by_name, get_project_history

    # If no file path, try to get latest version of the song
    if hasattr(args, 'file') and args.file:
        als_path = args.file
    else:
        # Find the project and get latest version
        history_result, message = get_project_history(args.song)
        if not history_result:
            print(f"Error: {message}")
            sys.exit(1)

        if not history_result.current_version:
            print(f"Error: No versions found for '{args.song}'")
            sys.exit(1)

        als_path = history_result.current_version.als_path

    result, message = get_what_if_predictions(als_path)

    if not result:
        print(f"Error: {message}")
        sys.exit(1)

    print("=" * 70)
    print(f"WHAT-IF PREDICTIONS")
    print("=" * 70)
    print(f"File: {Path(result.als_path).name}")
    print(f"Current Health: {result.current_health}/100")
    print()

    if not result.has_sufficient_data:
        print("⚠ Insufficient historical data for confident predictions.")
        print("  Keep scanning more versions to improve prediction accuracy.")
        print()

    if result.top_recommendation:
        rec = result.top_recommendation
        print("-" * 70)
        print("TOP RECOMMENDATION")
        print("-" * 70)
        print(f"  {rec.action.upper()} {rec.device_type} devices")
        print(f"  Predicted improvement: +{rec.predicted_health_delta:.1f} health")
        print(f"  Confidence: {rec.confidence} ({rec.success_rate*100:.0f}% success rate)")
        print(f"  Based on: {rec.sample_size} similar changes")
        print()

    if result.predictions:
        print("-" * 70)
        print("ALL PREDICTIONS (sorted by expected improvement)")
        print("-" * 70)
        print(f"{'Action':<12} {'Device Type':<20} {'Delta':>8} {'Confidence':>12} {'Success':>10}")
        print("-" * 70)

        for p in result.predictions:
            action = p.action.upper()
            device = p.device_type[:18] if len(p.device_type) > 18 else p.device_type
            delta = f"+{p.predicted_health_delta:.1f}"
            conf = p.confidence
            success = f"{p.success_rate*100:.0f}%"
            print(f"{action:<12} {device:<20} {delta:>8} {conf:>12} {success:>10}")

        print()
    else:
        print("No predictions available. Need more historical change data.")
        print()


def cmd_db_recommend(args):
    """Show smart recommendations based on learned patterns."""
    from database import get_learned_patterns, get_insights, find_project_by_name

    print("=" * 70)
    print("SMART RECOMMENDATIONS")
    print("=" * 70)
    print()

    # Get learned patterns
    patterns, pattern_msg = get_learned_patterns(min_occurrences=args.min_samples or 3)

    if not patterns:
        print("No patterns learned yet. Need more version history data.")
        print(f"  Status: {pattern_msg}")
        print()
        print("To build pattern data:")
        print("  1. Scan more .als files: als-doctor scan <directory>")
        print("  2. Compute changes: als-doctor db compute-changes <song>")
        print()
        return

    # Separate helpful vs harmful patterns
    helpful = [p for p in patterns if p.avg_health_delta > 2]
    harmful = [p for p in patterns if p.avg_health_delta < -2]
    neutral = [p for p in patterns if -2 <= p.avg_health_delta <= 2]

    # Sort by confidence then by impact
    helpful.sort(key=lambda p: (-{'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}.get(p.confidence, 0), -p.avg_health_delta))
    harmful.sort(key=lambda p: (-{'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}.get(p.confidence, 0), p.avg_health_delta))

    print(f"Based on {len(patterns)} patterns from your project history:")
    print()

    if helpful:
        print("-" * 70)
        print("✓ DO MORE OF THESE (consistently improve health)")
        print("-" * 70)
        for p in helpful[:5]:
            action = p.change_type.replace('device_', '').replace('track_', '')
            device = p.device_type or 'any'
            conf_badge = {'HIGH': '●●●', 'MEDIUM': '●●○', 'LOW': '●○○'}.get(p.confidence, '○○○')
            print(f"  [{conf_badge}] {action} {device}")
            print(f"        Avg: +{p.avg_health_delta:.1f} health | {p.times_helped}/{p.total_occurrences} times helped")
            if p.recommendation:
                print(f"        → {p.recommendation}")
            print()

    if harmful:
        print("-" * 70)
        print("✗ AVOID THESE (consistently hurt health)")
        print("-" * 70)
        for p in harmful[:5]:
            action = p.change_type.replace('device_', '').replace('track_', '')
            device = p.device_type or 'any'
            conf_badge = {'HIGH': '●●●', 'MEDIUM': '●●○', 'LOW': '●○○'}.get(p.confidence, '○○○')
            print(f"  [{conf_badge}] {action} {device}")
            print(f"        Avg: {p.avg_health_delta:.1f} health | {p.times_hurt}/{p.total_occurrences} times hurt")
            if p.recommendation:
                print(f"        → {p.recommendation}")
            print()

    # Get insights for common mistakes
    insights_result, _ = get_insights()
    if insights_result and insights_result.common_mistakes:
        print("-" * 70)
        print("⚠ COMMON MISTAKES TO AVOID")
        print("-" * 70)
        for mistake in insights_result.common_mistakes[:3]:
            print(f"  • {mistake.description}")
            print(f"    Seen {mistake.occurrence_count}x, avg {mistake.avg_health_impact:+.1f} health impact")
            if mistake.example_devices:
                print(f"    Examples: {', '.join(mistake.example_devices[:3])}")
            print()

    print()


def cmd_db_patterns(args):
    """Show all learned patterns with statistics."""
    from database import get_learned_patterns

    min_occurrences = args.min_samples or 2

    patterns, message = get_learned_patterns(min_occurrences=min_occurrences)

    print("=" * 70)
    print(f"LEARNED PATTERNS (min {min_occurrences} occurrences)")
    print("=" * 70)
    print()

    if not patterns:
        print(f"No patterns found: {message}")
        print()
        return

    print(f"Found {len(patterns)} patterns:")
    print()

    # Table header
    print(f"{'Change Type':<18} {'Device Type':<15} {'Avg Δ':>8} {'Helped':>8} {'Hurt':>8} {'Total':>6} {'Conf':>6}")
    print("-" * 70)

    for p in patterns:
        change = p.change_type.replace('device_', 'd_').replace('track_', 't_')
        device = (p.device_type or 'any')[:13]
        avg_delta = f"{p.avg_health_delta:+.1f}"
        helped = str(p.times_helped)
        hurt = str(p.times_hurt)
        total = str(p.total_occurrences)
        conf = p.confidence[:4]

        print(f"{change:<18} {device:<15} {avg_delta:>8} {helped:>8} {hurt:>8} {total:>6} {conf:>6}")

    print()

    # Show confidence legend
    print("Confidence: HIGH (10+ samples), MEDIUM (5-9 samples), LOW (2-4 samples)")
    print()


def cmd_dashboard(args):
    """Start the local web dashboard."""
    from dashboard import run_dashboard

    print("Starting ALS Doctor Dashboard...")
    print(f"  URL: http://{args.host}:{args.port}")
    print("  Press Ctrl+C to stop")
    print()

    run_dashboard(
        port=args.port,
        host=args.host,
        debug=args.debug,
        no_browser=args.no_browser,
        auto_refresh=not args.no_refresh,
        refresh_interval=args.refresh_interval
    )


def main():
    parser = argparse.ArgumentParser(
        description="ALS Doctor - Ableton Project Health Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s diagnose project.als
  %(prog)s diagnose project.als --html report.html
  %(prog)s compare old.als new.als
  %(prog)s scan "D:/Ableton Projects" --limit 20
  %(prog)s quick project.als

Database commands:
  %(prog)s db init
  %(prog)s db status
  %(prog)s db status --html library_report.html
  %(prog)s db list --sort score
  %(prog)s db history "22 Project"
  %(prog)s db history "22 Project" --html
  %(prog)s db changes "MyTrack"
  %(prog)s db trend "35"
  %(prog)s db insights

Dashboard:
  %(prog)s dashboard
  %(prog)s dashboard --port 8080
        """
    )
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--no-color', action='store_true', help='Disable colored output')

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Dashboard command
    p_dashboard = subparsers.add_parser('dashboard', help='Start the local web dashboard')
    p_dashboard.add_argument('--port', '-p', type=int, default=5000, help='Port number (default: 5000)')
    p_dashboard.add_argument('--host', default='127.0.0.1', help='Host address (default: 127.0.0.1)')
    p_dashboard.add_argument('--no-browser', action='store_true', help='Do not auto-open browser')
    p_dashboard.add_argument('--no-refresh', action='store_true', help='Disable auto-refresh')
    p_dashboard.add_argument('--refresh-interval', type=int, default=30, help='Refresh interval in seconds (default: 30)')
    p_dashboard.add_argument('--debug', action='store_true', help='Enable Flask debug mode')
    p_dashboard.set_defaults(func=cmd_dashboard)

    # Diagnose command
    p_diagnose = subparsers.add_parser('diagnose', help='Full diagnosis of a project')
    p_diagnose.add_argument('file', help='Path to .als file')
    p_diagnose.add_argument('--json', help='Export results to JSON file')
    p_diagnose.add_argument('--html', nargs='?', const=True, default=None,
                            help='Generate HTML report (optional: output path)')
    p_diagnose.set_defaults(func=cmd_diagnose)

    # Compare command
    p_compare = subparsers.add_parser('compare', help='Compare two project versions')
    p_compare.add_argument('before', help='Path to earlier version')
    p_compare.add_argument('after', help='Path to later version')
    p_compare.set_defaults(func=cmd_compare)

    # Scan command
    p_scan = subparsers.add_parser('scan', help='Batch scan directory')
    p_scan.add_argument('directory', help='Directory to scan')
    p_scan.add_argument('--limit', type=int, help='Limit number of files to scan')
    p_scan.add_argument('--min-number', type=int, help='Only scan projects with folder names starting with this number or higher (e.g., --min-number 22)')
    p_scan.add_argument('--no-recursive', action='store_true', help='Do not scan subdirectories')
    p_scan.set_defaults(func=cmd_scan)

    # Quick command
    p_quick = subparsers.add_parser('quick', help='Quick health check')
    p_quick.add_argument('file', help='Path to .als file')
    p_quick.set_defaults(func=cmd_quick)

    # ==================== DATABASE SUBCOMMAND ====================
    p_db = subparsers.add_parser('db', help='Database operations for tracking and intelligence')
    db_subparsers = p_db.add_subparsers(dest='db_command', help='Database commands')

    # db init
    p_db_init = db_subparsers.add_parser('init', help='Initialize the database')
    p_db_init.set_defaults(func=cmd_db_init)

    # db status
    p_db_status = db_subparsers.add_parser('status', help='Show library status overview')
    p_db_status.add_argument('--html', nargs='?', const=True, default=None,
                             help='Generate HTML library report (optional: output path)')
    p_db_status.set_defaults(func=cmd_db_status)

    # db list
    p_db_list = db_subparsers.add_parser('list', help='List all tracked projects')
    p_db_list.add_argument('--sort', choices=['name', 'score', 'date'], default='name',
                           help='Sort order (default: name)')
    p_db_list.set_defaults(func=cmd_db_list)

    # db history
    p_db_history = db_subparsers.add_parser('history', help='Show version history timeline')
    p_db_history.add_argument('song', help='Song name or partial match')
    p_db_history.add_argument('--html', nargs='?', const=True, default=None,
                              help='Generate HTML history report (optional: output path)')
    p_db_history.set_defaults(func=cmd_db_history)

    # db changes
    p_db_changes = db_subparsers.add_parser('changes', help='Show changes between versions')
    p_db_changes.add_argument('song', help='Song name or partial match')
    p_db_changes.add_argument('--no-compute', action='store_true',
                              help='Do not automatically compute missing changes')
    p_db_changes.add_argument('--detailed', '-d', action='store_true',
                              help='Show detailed impact assessments with pattern insights')
    p_db_changes.set_defaults(func=cmd_db_changes)

    # db trend
    p_db_trend = db_subparsers.add_parser('trend', help='Show health trend analysis')
    p_db_trend.add_argument('song', help='Song name or partial match')
    p_db_trend.set_defaults(func=cmd_db_trend)

    # db insights
    p_db_insights = db_subparsers.add_parser('insights', help='Show patterns across all projects')
    p_db_insights.set_defaults(func=cmd_db_insights)

    # db compute-changes
    p_db_compute = db_subparsers.add_parser('compute-changes', help='Compute and store changes for a project')
    p_db_compute.add_argument('song', help='Song name or partial match')
    p_db_compute.set_defaults(func=cmd_db_compute_changes)

    # ==================== PHASE 2: INTELLIGENCE COMMANDS ====================

    # db whatif
    p_db_whatif = db_subparsers.add_parser('whatif', help='Show what-if predictions based on patterns')
    p_db_whatif.add_argument('song', help='Song name or partial match')
    p_db_whatif.add_argument('--file', '-f', help='Specific .als file path (optional, defaults to latest version)')
    p_db_whatif.set_defaults(func=cmd_db_whatif)

    # db recommend
    p_db_recommend = db_subparsers.add_parser('recommend', help='Show smart recommendations based on learned patterns')
    p_db_recommend.add_argument('--min-samples', type=int, default=3,
                                 help='Minimum samples for pattern confidence (default: 3)')
    p_db_recommend.set_defaults(func=cmd_db_recommend)

    # db patterns
    p_db_patterns = db_subparsers.add_parser('patterns', help='Show all learned patterns with statistics')
    p_db_patterns.add_argument('--min-samples', type=int, default=2,
                                help='Minimum occurrences to include (default: 2)')
    p_db_patterns.set_defaults(func=cmd_db_patterns)

    args = parser.parse_args()

    # Handle --no-color flag
    if args.no_color:
        import os
        os.environ['NO_COLOR'] = '1'
        os.environ['ALS_DOCTOR_NO_COLOR'] = '1'

    if not args.command:
        parser.print_help()
        return

    # Handle db subcommand
    if args.command == 'db':
        if not args.db_command:
            p_db.print_help()
            return

    try:
        args.func(args)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        if hasattr(args, 'verbose') and args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
