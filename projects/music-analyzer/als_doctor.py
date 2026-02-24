#!/usr/bin/env python3
"""
ALS Doctor - Ableton Live Set Health Analyzer

A CLI tool for analyzing Ableton Live projects, tracking health scores,
and providing actionable recommendations for improving your productions.

Usage:
    als-doctor db init          Initialize the project database
    als-doctor db list          List all scanned projects
    als-doctor db history <song> Show version history for a song
    als-doctor db status        Show library status summary
    als-doctor scan <dir>       Scan directory for .als files
    als-doctor diagnose <file>  Analyze a single .als file
    als-doctor best <song>      Find the best version of a song
"""

import click
from pathlib import Path
from typing import Optional
from datetime import datetime
import sys

# Add src to path for direct import (avoids src/__init__.py heavy imports)
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from database import (
    db_init, get_db, DEFAULT_DB_PATH,
    persist_scan_result, persist_batch_scan_results,
    ScanResult, ScanResultIssue, _calculate_grade,
    list_projects, ProjectSummary,
    get_project_history, ProjectHistory, VersionHistory,
    get_best_version, BestVersionResult,
    get_library_status, LibraryStatus, GradeDistribution, generate_grade_bar,
    get_project_changes, ProjectChangesResult, VersionComparison, VersionChange,
    compute_and_store_all_changes,
    get_insights, InsightsResult, InsightPattern, CommonMistake, _get_confidence_level,
    persist_midi_stats, MIDIStats, get_midi_stats,
    get_style_profile, StyleProfile, save_profile_to_json, load_profile_from_json,
    compare_file_against_profile, ProfileComparisonResult,
    # Template functions
    list_templates, get_template_by_name, add_template_from_file, remove_template,
    compare_template, ProjectTemplate, TemplateComparisonResult,
    # Smart recommendations
    smart_diagnose, SmartDiagnoseResult, SmartRecommendation,
    has_sufficient_history, _count_database_versions,
    # Phase 2: Intelligence features
    analyze_project_trend, ProjectTrend, TrendPoint,
    get_what_if_predictions, WhatIfAnalysis, WhatIfPrediction,
    get_change_impact_predictions, ChangeImpactPrediction,
    # Phase 2 Enhanced: Change impact assessment
    get_project_changes_enhanced, ChangeImpactAssessment,
    get_learned_patterns, ChangePattern,
    # Phase 2: Personalized recommendations
    get_project_specific_patterns, ProjectPatterns,
    get_personalized_recommendations, PersonalizedRecommendationsResult, PersonalizedRecommendation,
    # Phase 2: Enhanced trend analysis
    get_enhanced_trend_analysis, EnhancedTrendAnalysis, Milestone,
    # Phase 2: Reference comparison learning
    persist_reference_comparison, get_reference_insights, get_reference_history,
    ReferenceInsights, StoredReferenceComparison, ReferenceRecommendationPattern
)
from cli_formatter import get_formatter, CLIFormatter, reset_formatter
from midi_analyzer import MIDIAnalyzer, MIDIAnalysisResult, get_midi_issues
from html_reports import (
    generate_project_report, generate_history_report, generate_library_report,
    get_default_report_path, ProjectReportData, HistoryReportData, LibraryReportData,
    ReportIssue, ReportVersion, GradeData
)
from als_json_output import create_json_output, ALSDoctorJSON


@click.group()
@click.version_option(version="1.0.0", prog_name="als-doctor")
@click.option('--no-color', is_flag=True, envvar='NO_COLOR',
              help='Disable colored output')
@click.pass_context
def cli(ctx, no_color: bool):
    """ALS Doctor - Ableton Live Set Health Analyzer

    Analyze your Ableton projects, track health scores over time,
    and get actionable recommendations for improvement.
    """
    # Initialize formatter with color settings
    ctx.ensure_object(dict)
    ctx.obj['formatter'] = get_formatter(no_color=no_color)
    ctx.obj['no_color'] = no_color


@cli.group()
@click.pass_context
def db(ctx):
    """Database management commands."""
    pass


@db.command('init')
@click.option(
    '--path', '-p',
    type=click.Path(),
    default=None,
    help='Custom database path (default: data/projects.db)'
)
@click.pass_context
def db_init_cmd(ctx, path: Optional[str]):
    """Initialize the project database.

    Creates the SQLite database with the required schema for storing
    project analysis data. Safe to run multiple times - won't destroy
    existing data.

    Example:
        als-doctor db init
        als-doctor db init --path /custom/path/mydb.db
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    db_path = Path(path) if path else None

    success, message = db_init(db_path)

    if success:
        fmt.success(message)
    else:
        fmt.error(message)
        raise SystemExit(1)


@db.command('list')
@click.option(
    '--sort', '-s',
    type=click.Choice(['name', 'score', 'date']),
    default='name',
    help='Sort order (default: name)'
)
@click.pass_context
def db_list_cmd(ctx, sort: str):
    """List all scanned projects.

    Shows all projects in the database with their version counts,
    best/latest health scores, and trend indicators.

    Trend indicators:
      [up]     - Latest version improved from previous
      [down]   - Latest version declined from previous
      [stable] - No significant change (within 5 points)
      [new]    - Only one version exists

    Example:
        als-doctor db list
        als-doctor db list --sort score
        als-doctor db list --sort date
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    database = get_db()

    if not database.is_initialized():
        fmt.error("Database not initialized. Run 'als-doctor db init' first.")
        raise SystemExit(1)

    projects, stats = list_projects(sort_by=sort)

    if stats['projects'] == 0:
        fmt.print("No projects found. Use 'als-doctor scan <dir> --save' to add projects.")
        return

    # Header
    fmt.header(f"PROJECTS ({stats['projects']} songs, {stats['versions']} versions)")
    fmt.print("")

    # Create table
    table = fmt.create_table(show_header=True)
    table.add_column("Song", justify="left")
    table.add_column("Versions", justify="right")
    table.add_column("Best", justify="right")
    table.add_column("Latest", justify="right")
    table.add_column("Trend", justify="right")

    for project in projects:
        # Truncate song name if too long
        song_name = project.song_name[:18] + '..' if len(project.song_name) > 20 else project.song_name

        # Format scores with grades
        best_str = fmt.grade_with_score(project.best_score, project.best_grade)
        latest_str = fmt.grade_with_score(project.latest_score, project.latest_grade)
        trend_str = fmt.trend_text(project.trend)

        table.add_row(
            song_name,
            str(project.version_count),
            best_str,
            latest_str,
            trend_str
        )

    table.render()


@db.command('status')
@click.pass_context
def db_status_cmd(ctx):
    """Show library status summary.

    Displays an overview of your project library including
    grade distribution, top projects ready to release, and
    projects that need attention.

    Example:
        als-doctor db status
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    database = get_db()

    if not database.is_initialized():
        fmt.error("Database not initialized. Run 'als-doctor db init' first.")
        raise SystemExit(1)

    status, message = get_library_status()

    if status is None:
        fmt.error(message)
        raise SystemExit(1)

    # Header
    fmt.header("LIBRARY STATUS")
    fmt.print("")

    # Summary line
    last_scan_str = status.last_scan_date.strftime("%Y-%m-%d") if status.last_scan_date else "Never"
    fmt.print(f"Projects: {status.total_projects} | Versions: {status.total_versions} | Last Scan: {last_scan_str}")
    fmt.print("")

    # Grade distribution
    if status.total_versions > 0:
        fmt.print("Grade Distribution:")

        for grade_info in status.grade_distribution:
            bar = fmt.grade_bar(grade_info.grade, grade_info.count, status.total_versions, max_width=20)
            grade_str = fmt.grade_text(grade_info.grade)

            # Format: [A] ======== 8 versions (17%)
            count_str = f"{grade_info.count} version{'s' if grade_info.count != 1 else ''}"
            pct_str = f"({grade_info.percentage:.0f}%)"

            fmt.print(f"  {grade_str} {bar:<20} {count_str} {pct_str}")

        fmt.print("")

    # Ready to Release
    if status.ready_to_release:
        if fmt.use_rich:
            fmt.print("[status.success]Ready to Release:[/status.success]")
        else:
            fmt.print("Ready to Release:")
        items = []
        for filename, score, song_name in status.ready_to_release:
            items.append(f"{filename} ({score})")
        fmt.print("  * " + " | ".join(items))
        fmt.print("")

    # Needs Attention
    if status.needs_work:
        if fmt.use_rich:
            fmt.print("[status.error]Needs Attention:[/status.error]")
        else:
            fmt.print("Needs Attention:")
        items = []
        for filename, score, song_name in status.needs_work:
            items.append(f"{filename} ({score})")
        fmt.print("  ! " + " | ".join(items))
        fmt.print("")

    # Empty library message
    if status.total_projects == 0:
        fmt.print("No projects found. Use 'als-doctor scan <dir> --save' to add projects.")


@db.command('history')
@click.argument('song')
@click.pass_context
def db_history_cmd(ctx, song: str):
    """Show version history for a song.

    Displays all versions of a project with their health scores
    and when they were scanned. Sorted by scan date (oldest first).

    The best version is marked with a star (*).
    Delta shows the change from the previous version.

    Example:
        als-doctor db history "22 Project"
        als-doctor db history 22  (fuzzy match)
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    database = get_db()

    if not database.is_initialized():
        fmt.error("Database not initialized. Run 'als-doctor db init' first.")
        raise SystemExit(1)

    history, message = get_project_history(song)

    if history is None:
        fmt.error(message)
        raise SystemExit(1)

    # Header
    fmt.header(f"HEALTH HISTORY: {history.song_name}")
    fmt.print("")

    # Create table
    table = fmt.create_table(show_header=True)
    table.add_column("Version", justify="left")
    table.add_column("Score", justify="right")
    table.add_column("Grade", justify="center")
    table.add_column("Delta", justify="right")
    table.add_column("Scanned", justify="left")

    for version in history.versions:
        # Truncate filename if too long
        filename = version.als_filename
        if len(filename) > 23:
            filename = filename[:21] + '..'

        # Score
        score_str = str(version.health_score)

        # Grade with color
        grade_str = fmt.grade_text(version.grade)

        # Delta
        if version.delta is None:
            delta_str = "--"
            if version.is_best:
                if fmt.use_rich:
                    delta_str = "-- [highlight]*[/highlight]"
                else:
                    delta_str = "-- *"
        elif version.delta > 0:
            delta_str = fmt.delta_text(version.delta)
            if version.is_best:
                if fmt.use_rich:
                    delta_str += " [highlight]*[/highlight]"
                else:
                    delta_str += " *"
        elif version.delta < 0:
            delta_str = fmt.delta_text(version.delta)
        else:
            delta_str = "0"

        # Date
        date_str = version.scanned_at.strftime("%Y-%m-%d %H:%M")

        table.add_row(filename, score_str, grade_str, delta_str, date_str)

    table.render()
    fmt.print("")

    # Summary
    if history.best_version:
        best = history.best_version
        fmt.print(f"Best: {best.als_filename} ({best.health_score}/100)")

    if history.current_version:
        current = history.current_version
        fmt.print(f"Current: {current.als_filename} ({current.health_score}/100)")

    # Recommendation
    if history.best_version and history.current_version:
        if history.current_version.health_score < history.best_version.health_score:
            diff = history.best_version.health_score - history.current_version.health_score
            fmt.print("")
            if fmt.use_rich:
                fmt.print(f"[highlight]Recommendation:[/highlight] Review changes since {history.best_version.als_filename} (-{diff} points)")
            else:
                fmt.print(f"Recommendation: Review changes since {history.best_version.als_filename} (-{diff} points)")


@db.command('changes')
@click.argument('song')
@click.option('--from', 'from_version', default=None, help='Starting version filename')
@click.option('--to', 'to_version', default=None, help='Ending version filename')
@click.option('--compute', is_flag=True, help='Compute changes from .als files (requires files to exist)')
@click.option('--enhanced', '-e', is_flag=True, help='Show enhanced analysis with confidence scores')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed reasoning for each change')
@click.pass_context
def db_changes_cmd(ctx, song: str, from_version: Optional[str], to_version: Optional[str],
                   compute: bool, enhanced: bool, verbose: bool):
    """Show changes between versions of a song.

    Displays device and track changes between consecutive versions,
    categorizing them as 'Likely helped' or 'Likely hurt' based on
    the health score delta and historical patterns.

    Use --compute to analyze .als files and populate the changes database.
    Use --enhanced to see confidence scores based on historical patterns.
    Use --verbose to see detailed reasoning for each change assessment.

    Example:
        als-doctor db changes "22 Project"
        als-doctor db changes 22 --compute
        als-doctor db changes 22 --enhanced -v
        als-doctor db changes 22 --from v1.als --to v3.als
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    database = get_db()

    if not database.is_initialized():
        fmt.error("Database not initialized. Run 'als-doctor db init' first.")
        raise SystemExit(1)

    # If --compute flag is set, compute changes first
    if compute:
        fmt.print(f"Computing changes for '{song}'...")
        success, message, total = compute_and_store_all_changes(song)
        if not success:
            fmt.error(message)
            raise SystemExit(1)
        fmt.success(message)
        fmt.print("")

    # Get changes - use enhanced version if flag is set
    if enhanced:
        result, message = get_project_changes_enhanced(song, from_version, to_version)
    else:
        result, message = get_project_changes(song, from_version, to_version)

    if result is None:
        fmt.error(message)
        raise SystemExit(1)

    # Header
    header_suffix = " (Enhanced Analysis)" if enhanced else ""
    fmt.header(f"CHANGES: {result.song_name}{header_suffix}")
    fmt.print("")

    if not result.comparisons:
        fmt.print("No changes recorded. Use --compute to analyze .als files.")
        return

    for comparison in result.comparisons:
        # Version transition header
        if comparison.is_improvement:
            if fmt.use_rich:
                status_str = "[green][IMPROVED][/green]"
            else:
                status_str = "[IMPROVED]"
        elif comparison.health_delta < 0:
            if fmt.use_rich:
                status_str = "[red][REGRESSED][/red]"
            else:
                status_str = "[REGRESSED]"
        else:
            status_str = "[NO CHANGE]"

        fmt.print_line("-", 60)
        fmt.print(f"{comparison.before_filename} => {comparison.after_filename} {status_str}")
        fmt.print(f"  Health: {comparison.before_health} => {comparison.after_health} ({comparison.health_delta:+d})")
        fmt.print(f"  Issues: {comparison.before_issues} => {comparison.after_issues} ({comparison.issues_delta:+d})")

        if not comparison.changes:
            fmt.print("")
            fmt.print("  No detailed changes recorded. Use --compute to analyze .als files.")
            fmt.print("")
            continue

        # Group changes by category (enhanced mode uses impact_assessment)
        if enhanced:
            helped = [c for c in comparison.changes
                      if c.impact_assessment and c.impact_assessment.category == 'helped']
            hurt = [c for c in comparison.changes
                    if c.impact_assessment and c.impact_assessment.category == 'hurt']
            neutral = [c for c in comparison.changes
                       if c.impact_assessment and c.impact_assessment.category == 'neutral']
            unknown = [c for c in comparison.changes
                       if not c.impact_assessment or c.impact_assessment.category == 'unknown']
        else:
            helped = [c for c in comparison.changes if c.likely_helped]
            hurt = [c for c in comparison.changes if not c.likely_helped and comparison.health_delta != 0]
            neutral = [c for c in comparison.changes if comparison.health_delta == 0]
            unknown = []

        if helped:
            fmt.print("")
            if fmt.use_rich:
                fmt.print("  [green]Likely Helped:[/green]")
            else:
                fmt.print("  Likely Helped:")
            for change in helped[:10]:
                _print_change(fmt, change, enhanced, verbose)
            if len(helped) > 10:
                fmt.print(f"    ... and {len(helped) - 10} more")

        if hurt:
            fmt.print("")
            if fmt.use_rich:
                fmt.print("  [red]Likely Hurt:[/red]")
            else:
                fmt.print("  Likely Hurt:")
            for change in hurt[:10]:
                _print_change(fmt, change, enhanced, verbose)
            if len(hurt) > 10:
                fmt.print(f"    ... and {len(hurt) - 10} more")

        if neutral:
            fmt.print("")
            fmt.print("  Neutral:")
            for change in neutral[:5]:
                _print_change(fmt, change, enhanced, verbose)
            if len(neutral) > 5:
                fmt.print(f"    ... and {len(neutral) - 5} more")

        if unknown and enhanced:
            fmt.print("")
            if fmt.use_rich:
                fmt.print("  [dim]Unknown (insufficient history):[/dim]")
            else:
                fmt.print("  Unknown (insufficient history):")
            for change in unknown[:5]:
                _print_change(fmt, change, enhanced, verbose)
            if len(unknown) > 5:
                fmt.print(f"    ... and {len(unknown) - 5} more")

        fmt.print("")

    # Summary
    total_comparisons = len(result.comparisons)
    improvements = len([c for c in result.comparisons if c.is_improvement])
    regressions = len([c for c in result.comparisons if c.health_delta < 0])
    stable = total_comparisons - improvements - regressions

    fmt.print_line("=", 60)
    fmt.print(f"Summary: {total_comparisons} version transition(s)")
    fmt.print(f"  Improvements: {improvements} | Regressions: {regressions} | Stable: {stable}")

    if enhanced:
        # Count change intents
        all_changes = [c for comp in result.comparisons for c in comp.changes]
        fixes = len([c for c in all_changes if getattr(c, 'change_intent', 'unknown') == 'likely_fix'])
        experiments = len([c for c in all_changes if getattr(c, 'change_intent', 'unknown') == 'experiment'])

        if fixes or experiments:
            fmt.print("")
            fmt.print(f"  Change Intent: {fixes} fix(es) | {experiments} experiment(s)")
            if fixes > experiments:
                fmt.print("  -> You're mostly addressing known issues (good!)")
            elif experiments > fixes * 2:
                fmt.print("  -> Lots of experimentation - consider tracking what works")

        fmt.print("")
        fmt.print("  Tip: Use --verbose to see detailed reasoning for assessments")
        fmt.print("  Legend: [FIX]=Addresses known issue, [EXP]=Experiment/new change")


def _print_change(fmt, change, enhanced: bool, verbose: bool):
    """Print a single change with optional enhanced info."""
    change_symbol = _get_change_symbol(change.change_type)

    # Build base output
    if change.device_name:
        base_str = f"    {change_symbol} {change.track_name}: {change.device_name}"
    else:
        base_str = f"    {change_symbol} {change.track_name}"

    # Add confidence badge in enhanced mode
    if enhanced and change.impact_assessment:
        assessment = change.impact_assessment
        confidence = assessment.confidence

        if confidence == 'HIGH':
            badge = "[HIGH]" if not fmt.use_rich else "[green][HIGH][/green]"
        elif confidence == 'MEDIUM':
            badge = "[MED]" if not fmt.use_rich else "[yellow][MED][/yellow]"
        elif confidence == 'LOW':
            badge = "[LOW]" if not fmt.use_rich else "[dim][LOW][/dim]"
        else:
            badge = "[?]" if not fmt.use_rich else "[dim][?][/dim]"

        # Add intent indicator (Likely Fix vs Experiment)
        intent = getattr(change, 'change_intent', 'unknown')
        if intent == 'likely_fix':
            intent_badge = "[FIX]" if not fmt.use_rich else "[cyan][FIX][/cyan]"
        elif intent == 'experiment':
            intent_badge = "[EXP]" if not fmt.use_rich else "[magenta][EXP][/magenta]"
        else:
            intent_badge = ""

        # Add historical context
        if assessment.historical_occurrences > 0:
            hist_str = f"({assessment.historical_occurrences}x, avg {assessment.historical_avg_delta:+.1f})"
        else:
            hist_str = "(no history)"

        # Build full line with intent badge
        if intent_badge:
            fmt.print(f"{base_str} {badge} {intent_badge} {hist_str}")
        else:
            fmt.print(f"{base_str} {badge} {hist_str}")

        if verbose:
            if assessment.reasoning:
                if fmt.use_rich:
                    fmt.print(f"      [dim]{assessment.reasoning}[/dim]")
                else:
                    fmt.print(f"      {assessment.reasoning}")
            # Show addressed issue in verbose mode
            addressed_issue = getattr(change, 'addressed_issue', None)
            if addressed_issue:
                if fmt.use_rich:
                    fmt.print(f"      [cyan]{addressed_issue}[/cyan]")
                else:
                    fmt.print(f"      {addressed_issue}")
    else:
        fmt.print(base_str)


def _get_change_symbol(change_type: str) -> str:
    """Get a symbol for the change type."""
    symbols = {
        'device_added': '+',
        'device_removed': '-',
        'device_enabled': '*',
        'device_disabled': 'o',
        'track_added': '+',
        'track_removed': '-',
    }
    return symbols.get(change_type, '?')


def _format_change_type(change_type: str) -> str:
    """Format change type for display."""
    display_names = {
        'device_added': 'Adding device',
        'device_removed': 'Removing device',
        'device_enabled': 'Enabling device',
        'device_disabled': 'Disabling device',
        'track_added': 'Adding track',
        'track_removed': 'Removing track',
    }
    return display_names.get(change_type, change_type)


@db.command('insights')
@click.pass_context
def db_insights_cmd(ctx):
    """Show aggregated patterns from version changes.

    Analyzes all tracked changes across your projects to identify
    patterns that consistently help or hurt health scores.

    Requires at least 10 version comparisons with tracked changes.
    Use 'als-doctor db changes <song> --compute' to populate change data.

    Confidence levels:
      HIGH   - 10+ occurrences
      MEDIUM - 5-9 occurrences
      LOW    - 2-4 occurrences

    Example:
        als-doctor db insights
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    database = get_db()

    if not database.is_initialized():
        fmt.error("Database not initialized. Run 'als-doctor db init' first.")
        raise SystemExit(1)

    result, msg = get_insights()

    if result is None:
        fmt.error(msg)
        raise SystemExit(1)

    # Header
    fmt.header("INSIGHTS: Patterns from Your History")
    fmt.print("")

    # Summary
    fmt.print(f"Analyzed: {result.total_comparisons} version comparisons, {result.total_changes} changes")
    fmt.print("")

    # Handle insufficient data
    if result.insufficient_data:
        fmt.print_line("-", 60)
        if fmt.use_rich:
            fmt.print("[yellow]Insufficient data for analysis[/yellow]")
        else:
            fmt.print("Insufficient data for analysis")
        fmt.print("")
        fmt.print(f"Need at least 10 version comparisons, you have {result.total_comparisons}.")
        fmt.print("")
        fmt.print("To gather more data:")
        fmt.print("  1. Scan more projects: als-doctor scan <dir> --save")
        fmt.print("  2. Compute changes: als-doctor db changes <song> --compute")
        fmt.print("")
        return

    # Patterns that help
    if result.patterns_that_help:
        fmt.print_line("-", 60)
        if fmt.use_rich:
            fmt.print("[green]PATTERNS THAT HELP[/green]")
        else:
            fmt.print("PATTERNS THAT HELP")
        fmt.print("")

        for pattern in result.patterns_that_help:
            action = _format_change_type(pattern.change_type)
            device = pattern.device_type or 'tracks'
            confidence = pattern.confidence

            # Format: "+ Adding Eq8 devices: +12.5 avg health [HIGH]"
            delta_str = f"+{pattern.avg_health_delta:.1f}" if pattern.avg_health_delta > 0 else f"{pattern.avg_health_delta:.1f}"

            if fmt.use_rich:
                confidence_color = 'green' if confidence == 'HIGH' else 'yellow' if confidence == 'MEDIUM' else 'dim'
                fmt.print(f"  [green]+[/green] {action} ({device}): [{confidence_color}]{delta_str} avg[/{confidence_color}] [{confidence}] ({pattern.occurrence_count}x)")
            else:
                fmt.print(f"  + {action} ({device}): {delta_str} avg [{confidence}] ({pattern.occurrence_count}x)")

        fmt.print("")

    # Patterns that hurt
    if result.patterns_that_hurt:
        fmt.print_line("-", 60)
        if fmt.use_rich:
            fmt.print("[red]PATTERNS THAT HURT[/red]")
        else:
            fmt.print("PATTERNS THAT HURT")
        fmt.print("")

        for pattern in result.patterns_that_hurt:
            action = _format_change_type(pattern.change_type)
            device = pattern.device_type or 'tracks'
            confidence = pattern.confidence

            delta_str = f"{pattern.avg_health_delta:.1f}"

            if fmt.use_rich:
                confidence_color = 'green' if confidence == 'HIGH' else 'yellow' if confidence == 'MEDIUM' else 'dim'
                fmt.print(f"  [red]-[/red] {action} ({device}): [{confidence_color}]{delta_str} avg[/{confidence_color}] [{confidence}] ({pattern.occurrence_count}x)")
            else:
                fmt.print(f"  - {action} ({device}): {delta_str} avg [{confidence}] ({pattern.occurrence_count}x)")

        fmt.print("")

    # Common mistakes
    if result.common_mistakes:
        fmt.print_line("-", 60)
        if fmt.use_rich:
            fmt.print("[yellow]COMMON MISTAKES[/yellow]")
        else:
            fmt.print("COMMON MISTAKES")
        fmt.print("")

        for mistake in result.common_mistakes:
            impact_str = f"{mistake.avg_health_impact:.1f}"

            if fmt.use_rich:
                fmt.print(f"  [yellow]![/yellow] {mistake.description}")
                fmt.print(f"      Impact: [red]{impact_str}[/red] avg health, {mistake.occurrence_count} occurrences")
            else:
                fmt.print(f"  ! {mistake.description}")
                fmt.print(f"      Impact: {impact_str} avg health, {mistake.occurrence_count} occurrences")

            if mistake.example_devices:
                examples = ', '.join(mistake.example_devices[:3])
                fmt.print(f"      Examples: {examples}")

        fmt.print("")

    # No patterns found
    if not result.patterns_that_help and not result.patterns_that_hurt and not result.common_mistakes:
        fmt.print("No clear patterns identified yet.")
        fmt.print("")
        fmt.print("This could mean:")
        fmt.print("  - Changes have mixed effects (no consistent pattern)")
        fmt.print("  - Need more data points")
        fmt.print("")

    # Tips
    fmt.print_line("=", 60)
    fmt.print("Tips:")
    fmt.print("  - Higher confidence = more reliable pattern")
    fmt.print("  - Use patterns to guide your workflow")
    fmt.print("  - Scan more versions to improve accuracy")


@db.command('patterns')
@click.option('--min-occurrences', '-m', default=3, help='Minimum occurrences to show pattern (default: 3)')
@click.pass_context
def db_patterns_cmd(ctx, min_occurrences: int):
    """Show learned patterns with detailed statistics.

    Displays all patterns learned from your historical changes,
    including success rates, average health impact, and recommendations.

    This is similar to 'insights' but provides more detailed statistics
    and actionable recommendations for each pattern.

    Example:
        als-doctor db patterns
        als-doctor db patterns --min-occurrences 5
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    database = get_db()

    if not database.is_initialized():
        fmt.error("Database not initialized. Run 'als-doctor db init' first.")
        raise SystemExit(1)

    patterns, message = get_learned_patterns(min_occurrences=min_occurrences)

    if not patterns:
        fmt.print("No patterns found.")
        fmt.print("")
        fmt.print("To build patterns:")
        fmt.print("  1. Scan projects: als-doctor scan <dir> --save")
        fmt.print("  2. Compute changes: als-doctor db changes <song> --compute")
        fmt.print(f"  3. Need at least {min_occurrences} occurrences per pattern")
        return

    # Header
    fmt.header("LEARNED PATTERNS")
    fmt.print("")
    fmt.print(f"Found {len(patterns)} patterns (min {min_occurrences} occurrences)")
    fmt.print("")

    # Group by benefit (helpful vs harmful)
    helpful = [p for p in patterns if p.avg_health_delta > 0]
    harmful = [p for p in patterns if p.avg_health_delta < 0]
    neutral = [p for p in patterns if -0.5 <= p.avg_health_delta <= 0.5]

    # Helpful patterns
    if helpful:
        fmt.print_line("-", 70)
        if fmt.use_rich:
            fmt.print("[green]BENEFICIAL PATTERNS[/green]")
        else:
            fmt.print("BENEFICIAL PATTERNS")
        fmt.print("")

        for p in sorted(helpful, key=lambda x: -x.avg_health_delta)[:10]:
            _print_pattern(fmt, p)

    # Harmful patterns
    if harmful:
        fmt.print_line("-", 70)
        if fmt.use_rich:
            fmt.print("[red]HARMFUL PATTERNS[/red]")
        else:
            fmt.print("HARMFUL PATTERNS")
        fmt.print("")

        for p in sorted(harmful, key=lambda x: x.avg_health_delta)[:10]:
            _print_pattern(fmt, p)

    # Neutral patterns
    if neutral:
        fmt.print_line("-", 70)
        fmt.print("NEUTRAL PATTERNS")
        fmt.print("")

        for p in neutral[:5]:
            _print_pattern(fmt, p)

    fmt.print_line("=", 70)
    fmt.print("Legend:")
    fmt.print("  [HIGH] = 10+ occurrences, very reliable")
    fmt.print("  [MED]  = 5-9 occurrences, moderately reliable")
    fmt.print("  [LOW]  = 3-4 occurrences, limited confidence")


def _print_pattern(fmt, pattern: ChangePattern):
    """Print a single learned pattern with statistics."""
    action = _format_change_type(pattern.change_type)
    device = pattern.device_type or 'tracks'

    # Calculate success rate
    total = pattern.total_occurrences
    success_rate = (pattern.times_helped / total * 100) if total > 0 else 0

    # Confidence badge
    confidence = pattern.confidence
    if confidence == 'HIGH':
        badge = "[HIGH]" if not fmt.use_rich else "[green][HIGH][/green]"
    elif confidence == 'MEDIUM':
        badge = "[MED]" if not fmt.use_rich else "[yellow][MED][/yellow]"
    else:
        badge = "[LOW]" if not fmt.use_rich else "[dim][LOW][/dim]"

    # Format delta
    delta = pattern.avg_health_delta
    if delta > 0:
        delta_str = f"+{delta:.1f}" if not fmt.use_rich else f"[green]+{delta:.1f}[/green]"
    elif delta < 0:
        delta_str = f"{delta:.1f}" if not fmt.use_rich else f"[red]{delta:.1f}[/red]"
    else:
        delta_str = "0.0"

    # Main line
    fmt.print(f"  {action} {device} {badge}")
    fmt.print(f"    Avg health: {delta_str} | Occurrences: {total}")
    fmt.print(f"    Helped: {pattern.times_helped} | Hurt: {pattern.times_hurt} | Neutral: {pattern.times_neutral}")
    fmt.print(f"    Success rate: {success_rate:.0f}%")

    # Recommendation
    if fmt.use_rich:
        fmt.print(f"    [dim]-> {pattern.recommendation}[/dim]")
    else:
        fmt.print(f"    -> {pattern.recommendation}")

    # Example devices
    if pattern.device_name_pattern:
        fmt.print(f"    Examples: {pattern.device_name_pattern}")

    fmt.print("")


@db.command('profile')
@click.option('--compare', 'compare_file', type=click.Path(exists=True), default=None,
              help='Compare a scanned .als file against your profile')
@click.option('--save', is_flag=True, help='Save profile to data/profile.json')
@click.pass_context
def db_profile_cmd(ctx, compare_file: Optional[str], save: bool):
    """Show personal style profile from your best work.

    Analyzes patterns from your Grade A versions (score 80+) to identify
    what makes your projects successful. Compares against Grade D-F versions
    to highlight differences.

    Requires at least 3 Grade A versions in the database.

    Use --compare to see how a specific file matches your profile.
    Use --save to save the profile to data/profile.json.

    Example:
        als-doctor db profile
        als-doctor db profile --save
        als-doctor db profile --compare "D:/Projects/MySong.als"
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    database = get_db()

    if not database.is_initialized():
        fmt.error("Database not initialized. Run 'als-doctor db init' first.")
        raise SystemExit(1)

    # If --compare flag is set, compare the file against profile
    if compare_file:
        _compare_file_to_profile(compare_file, fmt)
        return

    # Generate profile
    profile, message = get_style_profile()

    if profile is None:
        fmt.error(message)

        # Check if it's due to insufficient data
        if "Insufficient data" in message:
            fmt.print("")
            fmt.print("To build a profile, you need at least 3 Grade A versions (score 80+).")
            fmt.print("")
            fmt.print("Steps to get started:")
            fmt.print("  1. Scan your projects: als-doctor scan <dir> --save")
            fmt.print("  2. Wait until you have 3+ versions scoring 80 or higher")
            fmt.print("  3. Run: als-doctor db profile")

        raise SystemExit(1)

    # Header
    fmt.header("PERSONAL STYLE PROFILE")
    fmt.print("")

    # Summary stats
    fmt.print(f"Analyzed: {profile.total_versions_analyzed} versions")
    fmt.print(f"Grade A (80+): {profile.grade_a_versions} versions")
    fmt.print(f"Grade D-F (<40): {profile.grade_df_versions} versions")
    fmt.print("")

    # Comparison table
    fmt.print_line("-", 60)
    fmt.print("BEST WORK vs WORST WORK")
    fmt.print_line("-", 60)

    # Create comparison table
    table = fmt.create_table(show_header=True)
    table.add_column("Metric", justify="left")
    table.add_column("Grade A", justify="right")
    table.add_column("Grade D-F", justify="right")
    table.add_column("Difference", justify="right")

    # Avg health score
    health_diff = profile.avg_health_score_a - profile.avg_health_score_df
    if fmt.use_rich:
        diff_color = 'green' if health_diff > 0 else 'red' if health_diff < 0 else 'white'
        table.add_row(
            "Avg Health Score",
            f"{profile.avg_health_score_a:.0f}",
            f"{profile.avg_health_score_df:.0f}" if profile.grade_df_versions > 0 else "-",
            f"[{diff_color}]{health_diff:+.0f}[/{diff_color}]" if profile.grade_df_versions > 0 else "-"
        )
    else:
        table.add_row(
            "Avg Health Score",
            f"{profile.avg_health_score_a:.0f}",
            f"{profile.avg_health_score_df:.0f}" if profile.grade_df_versions > 0 else "-",
            f"{health_diff:+.0f}" if profile.grade_df_versions > 0 else "-"
        )

    # Get raw data for more details
    raw = profile.raw_data or {}

    # Avg devices
    devices_a = raw.get('avg_devices_a', 0)
    devices_df = raw.get('avg_devices_df', 0)
    devices_diff = devices_df - devices_a
    table.add_row(
        "Avg Devices",
        f"{devices_a:.0f}",
        f"{devices_df:.0f}" if profile.grade_df_versions > 0 else "-",
        f"{devices_diff:+.0f}" if profile.grade_df_versions > 0 else "-"
    )

    # Disabled %
    disabled_a = raw.get('avg_disabled_pct_a', 0)
    disabled_df = raw.get('avg_disabled_pct_df', 0)
    disabled_diff = disabled_df - disabled_a
    table.add_row(
        "Disabled Devices %",
        f"{disabled_a:.0f}%",
        f"{disabled_df:.0f}%" if profile.grade_df_versions > 0 else "-",
        f"{disabled_diff:+.0f}%" if profile.grade_df_versions > 0 else "-"
    )

    # Clutter %
    clutter_a = raw.get('avg_clutter_a', 0)
    clutter_df = raw.get('avg_clutter_df', 0)
    clutter_diff = clutter_df - clutter_a
    table.add_row(
        "Clutter %",
        f"{clutter_a:.0f}%",
        f"{clutter_df:.0f}%" if profile.grade_df_versions > 0 else "-",
        f"{clutter_diff:+.0f}%" if profile.grade_df_versions > 0 else "-"
    )

    table.render()
    fmt.print("")

    # Insights
    if profile.insights:
        fmt.print_line("-", 60)
        if fmt.use_rich:
            fmt.print("[highlight]INSIGHTS FROM YOUR BEST WORK[/highlight]")
        else:
            fmt.print("INSIGHTS FROM YOUR BEST WORK")
        fmt.print_line("-", 60)
        fmt.print("")

        for insight in profile.insights:
            fmt.print(f"  - {insight}")

        fmt.print("")

    # Grade A files
    grade_a_files = raw.get('grade_a_files', [])
    if grade_a_files:
        fmt.print_line("-", 60)
        fmt.print("YOUR BEST VERSIONS (Grade A)")
        fmt.print_line("-", 60)

        for filename in grade_a_files[:10]:
            if fmt.use_rich:
                fmt.print(f"  [green]*[/green] {filename}")
            else:
                fmt.print(f"  * {filename}")

        if len(grade_a_files) > 10:
            fmt.print(f"  ... and {len(grade_a_files) - 10} more")

        fmt.print("")

    # Save if requested
    if save:
        success, msg = save_profile_to_json(profile)
        if success:
            fmt.success(msg)
        else:
            fmt.warning(msg)

    # Tips
    fmt.print_line("=", 60)
    fmt.print("Tips:")
    fmt.print("  - Use --compare <file> to compare a project against this profile")
    fmt.print("  - Use --save to export profile as JSON")
    fmt.print("  - Scan more projects to improve accuracy")


def _compare_file_to_profile(file_path: str, fmt: CLIFormatter):
    """Compare a file against the style profile."""
    from pathlib import Path

    als_path = Path(file_path).absolute()

    result, message = compare_file_against_profile(str(als_path))

    if result is None:
        fmt.error(message)
        raise SystemExit(1)

    # Header
    fmt.header(f"PROFILE COMPARISON: {result.als_filename}")
    fmt.print("")

    # Basic info
    grade_str = fmt.grade_text(result.grade)
    fmt.print(f"Health Score: {result.health_score}/100 {grade_str}")
    fmt.print(f"Similarity to Best Work: {result.similarity_score}%")
    fmt.print("")

    # Similarity gauge
    _display_similarity_gauge(result.similarity_score, fmt)
    fmt.print("")

    # Deviations
    fmt.print_line("-", 50)
    fmt.print("DEVIATIONS FROM YOUR PROFILE")
    fmt.print_line("-", 50)

    # Device count
    if result.device_count_deviation != 0:
        if result.device_count_deviation > 0:
            if fmt.use_rich:
                fmt.print(f"  Device Count: [yellow]+{result.device_count_deviation:.0f}[/yellow] more than typical")
            else:
                fmt.print(f"  Device Count: +{result.device_count_deviation:.0f} more than typical")
        else:
            if fmt.use_rich:
                fmt.print(f"  Device Count: [cyan]{result.device_count_deviation:.0f}[/cyan] fewer than typical")
            else:
                fmt.print(f"  Device Count: {result.device_count_deviation:.0f} fewer than typical")
    else:
        if fmt.use_rich:
            fmt.print("  Device Count: [green]typical[/green]")
        else:
            fmt.print("  Device Count: typical")

    # Disabled %
    if abs(result.disabled_pct_deviation) > 5:
        if result.disabled_pct_deviation > 0:
            if fmt.use_rich:
                fmt.print(f"  Disabled Devices: [yellow]+{result.disabled_pct_deviation:.0f}%[/yellow] more than typical")
            else:
                fmt.print(f"  Disabled Devices: +{result.disabled_pct_deviation:.0f}% more than typical")
        else:
            if fmt.use_rich:
                fmt.print(f"  Disabled Devices: [green]{result.disabled_pct_deviation:.0f}%[/green] less than typical")
            else:
                fmt.print(f"  Disabled Devices: {result.disabled_pct_deviation:.0f}% less than typical")
    else:
        if fmt.use_rich:
            fmt.print("  Disabled Devices: [green]typical[/green]")
        else:
            fmt.print("  Disabled Devices: typical")

    fmt.print("")

    # Unusual patterns
    if result.unusual_patterns:
        if fmt.use_rich:
            fmt.print("[yellow]Unusual Patterns:[/yellow]")
        else:
            fmt.print("Unusual Patterns:")
        for pattern in result.unusual_patterns:
            fmt.print(f"  ! {pattern}")
        fmt.print("")

    # Missing patterns
    if result.missing_patterns:
        fmt.print("Missing from your typical best work:")
        for pattern in result.missing_patterns:
            fmt.print(f"  - {pattern}")
        fmt.print("")

    # Recommendations
    if result.recommendations:
        fmt.print_line("-", 50)
        if fmt.use_rich:
            fmt.print("[highlight]RECOMMENDATIONS[/highlight]")
        else:
            fmt.print("RECOMMENDATIONS")
        fmt.print_line("-", 50)

        for rec in result.recommendations:
            fmt.print(f"  - {rec}")

        fmt.print("")

    # Summary
    fmt.print_line("=", 50)
    if result.similarity_score >= 80:
        if fmt.use_rich:
            fmt.print("[green]This project closely matches your best work patterns![/green]")
        else:
            fmt.print("This project closely matches your best work patterns!")
    elif result.similarity_score >= 60:
        fmt.print("This project has some similarities to your best work.")
    else:
        fmt.print("This project differs significantly from your best work patterns.")


def _display_similarity_gauge(score: int, fmt: CLIFormatter):
    """Display a visual gauge for similarity score."""
    bar_width = 20
    filled = int(score / 100 * bar_width)
    empty = bar_width - filled

    if fmt.use_rich:
        if score >= 80:
            color = 'green'
        elif score >= 60:
            color = 'yellow'
        else:
            color = 'red'

        bar = f"[{color}]{'█' * filled}[/{color}]{'░' * empty}"
        fmt.print(f"  [{bar}] {score}%")
    else:
        bar = '=' * filled + '-' * empty
        fmt.print(f"  [{bar}] {score}%")


@db.command('trend')
@click.argument('song')
@click.option('--graph', '-g', is_flag=True, help='Show ASCII graph visualization')
@click.option('--milestones', '-m', is_flag=True, help='Show milestone events')
@click.option('--enhanced', '-e', is_flag=True, help='Show all enhanced features (graph + milestones)')
@click.pass_context
def db_trend_cmd(ctx, song: str, graph: bool, milestones: bool, enhanced: bool):
    """Show health trend analysis for a project.

    Analyzes the health trajectory of a project over its versions
    to determine if it's improving, stable, or declining.

    Includes:
      - Trend direction and strength
      - Health timeline with deltas
      - Biggest improvements and regressions
      - Recent momentum

    Use --graph to see an ASCII visualization of health over time.
    Use --milestones to see significant events (achievements, regressions).
    Use --enhanced for both graph and milestones with additional metrics.

    Example:
        als-doctor db trend "22 Project"
        als-doctor db trend 35 --graph
        als-doctor db trend 35 --enhanced
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    database = get_db()

    if not database.is_initialized():
        fmt.error("Database not initialized. Run 'als-doctor db init' first.")
        raise SystemExit(1)

    # Use enhanced analysis if any enhanced options are set
    use_enhanced = graph or milestones or enhanced

    if use_enhanced:
        enhanced_result, msg = get_enhanced_trend_analysis(song)
        if enhanced_result is None:
            fmt.error(msg)
            raise SystemExit(1)
        result = enhanced_result.trend
    else:
        result, msg = analyze_project_trend(song)
        if result is None:
            fmt.error(msg)
            raise SystemExit(1)
        enhanced_result = None

    # Header
    fmt.header(f"TREND ANALYSIS: {result.song_name}")
    fmt.print("")

    # Trend direction with visual indicator
    fmt.print_line("-", 60)
    if result.trend_direction == 'improving':
        if fmt.use_rich:
            fmt.print(f"  [green]^ IMPROVING[/green] (strength: {result.trend_strength:.0%})")
        else:
            fmt.print(f"  ^ IMPROVING (strength: {result.trend_strength:.0%})")
    elif result.trend_direction == 'declining':
        if fmt.use_rich:
            fmt.print(f"  [red]v DECLINING[/red] (strength: {result.trend_strength:.0%})")
        else:
            fmt.print(f"  v DECLINING (strength: {result.trend_strength:.0%})")
    else:
        if fmt.use_rich:
            fmt.print(f"  [yellow]- STABLE[/yellow] (consistency: {result.trend_strength:.0%})")
        else:
            fmt.print(f"  - STABLE (consistency: {result.trend_strength:.0%})")

    fmt.print("")
    fmt.print(f"  {result.summary}")
    fmt.print("")

    # ASCII Graph (if enabled)
    if (graph or enhanced) and enhanced_result:
        fmt.print_line("-", 60)
        fmt.print("HEALTH TREND GRAPH:")
        fmt.print("")
        for line in enhanced_result.graph_lines:
            fmt.print(f"  {line}")
        fmt.print("")

    # Health metrics
    fmt.print_line("-", 60)
    fmt.print("HEALTH METRICS:")
    fmt.print(f"  First scan:  {result.first_health}")
    fmt.print(f"  Latest:      {result.latest_health}")
    fmt.print(f"  Best:        {result.best_health}")
    fmt.print(f"  Worst:       {result.worst_health}")
    fmt.print(f"  Average:     {result.avg_health:.1f}")

    # Additional metrics for enhanced mode
    if enhanced and enhanced_result:
        fmt.print("")
        fmt.print(f"  Consistency: {enhanced_result.consistency_score:.0%}")
        fmt.print(f"  Recoveries:  {enhanced_result.recovery_count}")
        fmt.print(f"  Plateaus:    {enhanced_result.plateau_count}")
        if enhanced_result.predicted_next_health:
            fmt.print(f"  Predicted next: {enhanced_result.predicted_next_health:.0f}")
        if enhanced_result.days_to_grade_a is not None:
            fmt.print(f"  Est. days to Grade A: ~{enhanced_result.days_to_grade_a}")

    fmt.print("")

    # Change metrics
    fmt.print_line("-", 60)
    fmt.print("CHANGE METRICS:")
    fmt.print(f"  Avg change per version:  {result.avg_delta_per_version:+.1f}")
    fmt.print(f"  Recent momentum:         {result.recent_momentum:+.1f}")
    fmt.print(f"  Biggest improvement:     +{result.biggest_improvement}")
    fmt.print(f"  Biggest regression:      -{result.biggest_regression}")
    fmt.print("")

    # Milestones (if enabled)
    if (milestones or enhanced) and enhanced_result and enhanced_result.milestones:
        fmt.print_line("-", 60)
        fmt.print("MILESTONES:")
        fmt.print("")

        # Group by type for cleaner display
        milestone_icons = {
            'first_a': '[A]',
            'new_best': '[+]',
            'major_improvement': '[^]',
            'major_regression': '[v]',
            'recovery': '[~]'
        }

        for m in enhanced_result.milestones[-10:]:  # Last 10 milestones
            icon = milestone_icons.get(m.milestone_type, '[*]')
            if fmt.use_rich:
                if m.milestone_type in ('first_a', 'new_best', 'major_improvement', 'recovery'):
                    color = 'green'
                else:
                    color = 'red'
                fmt.print(f"  [{color}]{icon}[/{color}] {m.als_filename[:25]:25} {m.description}")
            else:
                fmt.print(f"  {icon} {m.als_filename[:25]:25} {m.description}")

        if len(enhanced_result.milestones) > 10:
            fmt.print(f"  ... and {len(enhanced_result.milestones) - 10} earlier milestones")
        fmt.print("")

    # Timeline (last 10 versions) - skip if graph is shown
    if not graph and not enhanced:
        fmt.print_line("-", 60)
        fmt.print(f"TIMELINE ({result.total_versions} versions):")
        fmt.print("")

        display_timeline = result.timeline[-10:] if len(result.timeline) > 10 else result.timeline
        if len(result.timeline) > 10:
            fmt.print(f"  (showing last 10 of {len(result.timeline)})")
            fmt.print("")

        for point in display_timeline:
            delta_str = f"{point.delta_from_previous:+d}" if point.delta_from_previous != 0 else " 0"
            if fmt.use_rich:
                if point.delta_from_previous > 0:
                    delta_color = 'green'
                elif point.delta_from_previous < 0:
                    delta_color = 'red'
                else:
                    delta_color = 'dim'
                fmt.print(f"  {point.als_filename:30} [{delta_color}]{delta_str:>4}[/{delta_color}]  health: {point.health_score}")
            else:
                fmt.print(f"  {point.als_filename:30} {delta_str:>4}  health: {point.health_score}")

        fmt.print("")

    fmt.print_line("=", 60)

    if not use_enhanced:
        fmt.print("Tip: Use --graph for visualization, --enhanced for full analysis")


@db.command('whatif')
@click.argument('file_path', type=click.Path(exists=True))
@click.pass_context
def db_whatif_cmd(ctx, file_path: str):
    """Show what-if predictions for a scanned project.

    Predicts the impact of potential changes based on historical
    patterns across all your projects.

    Shows predictions like:
      "If you remove Eq8, expect +5.2 health (82% success rate)"

    The file must have been previously scanned with --save.

    Example:
        als-doctor db whatif "D:/Projects/MySong.als"
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    database = get_db()

    if not database.is_initialized():
        fmt.error("Database not initialized. Run 'als-doctor db init' first.")
        raise SystemExit(1)

    result, msg = get_what_if_predictions(file_path)

    if result is None:
        fmt.error(msg)
        raise SystemExit(1)

    # Header
    fmt.header("WHAT-IF PREDICTIONS")
    fmt.print("")
    fmt.print(f"File: {Path(result.als_path).name}")
    fmt.print(f"Current health: {result.current_health}")
    fmt.print("")

    if not result.has_sufficient_data:
        fmt.print_line("-", 60)
        if fmt.use_rich:
            fmt.print("[yellow]Limited historical data for predictions.[/yellow]")
        else:
            fmt.print("Limited historical data for predictions.")
        fmt.print("")
        fmt.print("To improve predictions:")
        fmt.print("  1. Scan more projects: als-doctor scan <dir> --save")
        fmt.print("  2. Compute changes:    als-doctor db changes <song> --compute")
        fmt.print("")

    # Top recommendation
    if result.top_recommendation:
        fmt.print_line("-", 60)
        if fmt.use_rich:
            fmt.print("[green]TOP RECOMMENDATION:[/green]")
        else:
            fmt.print("TOP RECOMMENDATION:")
        fmt.print("")
        rec = result.top_recommendation
        fmt.print(f"  {rec.action.upper()} {rec.device_type}")
        fmt.print(f"  Predicted: +{rec.predicted_health_delta:.1f} health")
        fmt.print(f"  Confidence: [{rec.confidence}] based on {rec.sample_size} similar changes")
        fmt.print(f"  Success rate: {rec.success_rate*100:.0f}%")
        fmt.print("")

    # All predictions
    if result.predictions:
        fmt.print_line("-", 60)
        fmt.print("ALL PREDICTIONS:")
        fmt.print("")

        for pred in result.predictions:
            confidence_marker = "**" if pred.confidence == 'HIGH' else "*" if pred.confidence == 'MEDIUM' else "."

            if fmt.use_rich:
                delta_color = 'green' if pred.predicted_health_delta > 0 else 'red'
                fmt.print(f"  {confidence_marker} {pred.action.upper():8} {pred.device_type:20} -> [{delta_color}]+{pred.predicted_health_delta:.1f}[/{delta_color}] ({pred.sample_size}x, {pred.success_rate*100:.0f}%)")
            else:
                fmt.print(f"  {confidence_marker} {pred.action.upper():8} {pred.device_type:20} -> +{pred.predicted_health_delta:.1f} ({pred.sample_size}x, {pred.success_rate*100:.0f}%)")

        fmt.print("")
        fmt.print("  Legend: ** HIGH confidence | * MEDIUM | . LOW")
        fmt.print("")
    else:
        fmt.print("No predictions available. Need more historical data.")
        fmt.print("")

    fmt.print_line("=", 60)


@db.command('smart')
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--limit', default=10, help='Maximum recommendations to show')
@click.pass_context
def db_smart_cmd(ctx, file_path: str, limit: int):
    """Show smart recommendations using historical intelligence.

    Analyzes a scanned project and prioritizes recommendations based on:
      - What has helped you before
      - Historical success rates
      - Your personal style profile

    Recommendations include confidence levels and predicted impact.

    Example:
        als-doctor db smart "D:/Projects/MySong.als"
        als-doctor db smart "D:/Projects/MySong.als" --limit 5
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    database = get_db()

    if not database.is_initialized():
        fmt.error("Database not initialized. Run 'als-doctor db init' first.")
        raise SystemExit(1)

    result, msg = smart_diagnose(file_path)

    if result is None:
        fmt.error(msg)
        raise SystemExit(1)

    # Header
    fmt.header("SMART RECOMMENDATIONS")
    fmt.print("")
    fmt.print(f"File: {result.als_filename}")
    fmt.print(f"Health: {result.health_score} ({result.grade})")
    fmt.print(f"Issues: {result.total_issues} total ({result.critical_count} critical, {result.warning_count} warnings)")
    fmt.print("")

    # Context
    fmt.print_line("-", 60)
    if result.has_sufficient_history:
        if fmt.use_rich:
            fmt.print(f"[green]OK[/green] Using intelligence from {result.versions_analyzed} scanned versions")
        else:
            fmt.print(f"OK Using intelligence from {result.versions_analyzed} scanned versions")
    else:
        if fmt.use_rich:
            fmt.print(f"[yellow]![/yellow] Limited history ({result.versions_analyzed} versions, need 20+)")
        else:
            fmt.print(f"! Limited history ({result.versions_analyzed} versions, need 20+)")

    if result.profile_available:
        if result.profile_similarity is not None:
            fmt.print(f"  Profile similarity: {result.profile_similarity}%")
    else:
        fmt.print("  No style profile yet (need 3+ Grade A versions)")

    fmt.print("")

    # Recommendations
    if not result.recommendations:
        fmt.print("No recommendations - this project looks good!")
        return

    fmt.print_line("-", 60)
    fmt.print("PRIORITIZED RECOMMENDATIONS:")
    fmt.print("")

    for i, rec in enumerate(result.recommendations[:limit], 1):
        # Priority and confidence indicator
        if rec.confidence == 'HIGH':
            conf_marker = "***"
        elif rec.confidence == 'MEDIUM':
            conf_marker = "**"
        else:
            conf_marker = "*"

        # Severity color
        if fmt.use_rich:
            if rec.severity == 'critical':
                sev_color = 'red'
            elif rec.severity == 'warning':
                sev_color = 'yellow'
            else:
                sev_color = 'dim'

            fmt.print(f"{i:2}. [{sev_color}][{rec.severity.upper():10}][/{sev_color}] {conf_marker}")
        else:
            fmt.print(f"{i:2}. [{rec.severity.upper():10}] {conf_marker}")

        if rec.track_name:
            fmt.print(f"    Track: {rec.track_name}")

        fmt.print(f"    {rec.description}")
        fmt.print(f"    -> {rec.recommendation}")

        if rec.helped_before:
            if fmt.use_rich:
                fmt.print(f"    [green]History: This fix improved health {rec.times_helped}x (avg +{rec.avg_improvement:.1f})[/green]")
            else:
                fmt.print(f"    History: This fix improved health {rec.times_helped}x (avg +{rec.avg_improvement:.1f})")
        elif rec.confidence_reason:
            fmt.print(f"    Note: {rec.confidence_reason}")

        fmt.print("")

    if len(result.recommendations) > limit:
        fmt.print(f"  ... and {len(result.recommendations) - limit} more recommendations")
        fmt.print(f"  Use --limit {len(result.recommendations)} to see all")

    fmt.print("")
    fmt.print_line("=", 60)


@db.command('recommend')
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--limit', default=10, help='Maximum recommendations to show')
@click.pass_context
def db_recommend_cmd(ctx, file_path: str, limit: int):
    """Show personalized recommendations combining global and project patterns.

    Unlike 'smart' which focuses on issue severity, 'recommend' focuses on
    what has historically improved health scores, with special emphasis on
    patterns specific to THIS project.

    Recommendations are sourced from:
      - [project] Patterns specific to this song
      - [global] Patterns from all your projects
      - [both] Confirmed by both sources (highest confidence)

    Example:
        als-doctor db recommend "D:/Projects/MySong.als"
        als-doctor db recommend "D:/Projects/MySong.als" --limit 5
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    database = get_db()

    if not database.is_initialized():
        fmt.error("Database not initialized. Run 'als-doctor db init' first.")
        raise SystemExit(1)

    result, msg = get_personalized_recommendations(file_path)

    if result is None:
        fmt.error(msg)
        raise SystemExit(1)

    # Header
    fmt.header("PERSONALIZED RECOMMENDATIONS")
    fmt.print("")
    fmt.print(f"File: {Path(file_path).name}")
    fmt.print(f"Current Health: {result.current_health} ({result.current_grade})")
    fmt.print("")

    # Data sources
    fmt.print_line("-", 60)
    fmt.print("DATA SOURCES:")

    if result.has_project_history:
        if fmt.use_rich:
            fmt.print(f"  [green]OK[/green] Project history: {result.project_changes_count} changes tracked")
        else:
            fmt.print(f"  OK Project history: {result.project_changes_count} changes tracked")
    else:
        if fmt.use_rich:
            fmt.print(f"  [dim].[/dim] Project history: insufficient ({result.project_changes_count} changes)")
        else:
            fmt.print(f"  . Project history: insufficient ({result.project_changes_count} changes)")

    if result.has_global_history:
        if fmt.use_rich:
            fmt.print(f"  [green]OK[/green] Global patterns: {result.global_changes_count} changes analyzed")
        else:
            fmt.print(f"  OK Global patterns: {result.global_changes_count} changes analyzed")
    else:
        if fmt.use_rich:
            fmt.print(f"  [dim].[/dim] Global patterns: insufficient ({result.global_changes_count} changes)")
        else:
            fmt.print(f"  . Global patterns: insufficient ({result.global_changes_count} changes)")

    fmt.print("")

    # Top recommendation highlight
    if result.top_recommendation:
        rec = result.top_recommendation
        fmt.print_line("-", 60)
        if fmt.use_rich:
            fmt.print("[green]TOP RECOMMENDATION[/green]")
        else:
            fmt.print("TOP RECOMMENDATION")
        fmt.print("")
        fmt.print(f"  {rec.action} {rec.target}")
        fmt.print(f"  Priority: {rec.priority}/100 | Confidence: {rec.confidence}")
        fmt.print(f"  Source: {rec.source}")
        fmt.print(f"  {rec.reasoning}")
        fmt.print("")

    # All recommendations
    if not result.recommendations:
        fmt.print("No recommendations available. Need more change history.")
        fmt.print("")
        fmt.print("To build history:")
        fmt.print("  1. Scan projects: als-doctor scan <dir> --save")
        fmt.print("  2. Compute changes: als-doctor db changes <song> --compute")
        return

    fmt.print_line("-", 60)
    fmt.print("ALL RECOMMENDATIONS:")
    fmt.print("")

    for i, rec in enumerate(result.recommendations[:limit], 1):
        # Source badge
        if rec.source == 'both':
            source_badge = "[both]" if not fmt.use_rich else "[green][both][/green]"
        elif rec.source == 'project':
            source_badge = "[project]" if not fmt.use_rich else "[cyan][project][/cyan]"
        else:
            source_badge = "[global]" if not fmt.use_rich else "[dim][global][/dim]"

        # Confidence stars
        if rec.confidence == 'HIGH':
            conf = "***"
        elif rec.confidence == 'MEDIUM':
            conf = "**"
        else:
            conf = "*"

        fmt.print(f"{i:2}. {rec.action} {rec.target} {source_badge} {conf}")

        # Show deltas
        if rec.source == 'both':
            fmt.print(f"    Global: avg {rec.global_avg_delta:+.1f} ({rec.global_occurrences}x)")
            fmt.print(f"    Project: avg {rec.project_avg_delta:+.1f} ({rec.project_occurrences}x)")
        elif rec.source == 'project':
            fmt.print(f"    Project: avg {rec.project_avg_delta:+.1f} ({rec.project_occurrences}x)")
        else:
            fmt.print(f"    Global: avg {rec.global_avg_delta:+.1f} ({rec.global_occurrences}x)")

        fmt.print("")

    if len(result.recommendations) > limit:
        fmt.print(f"  ... and {len(result.recommendations) - limit} more")
        fmt.print(f"  Use --limit {len(result.recommendations)} to see all")

    # Summary
    fmt.print_line("=", 60)
    if result.estimated_improvement > 0:
        if fmt.use_rich:
            fmt.print(f"[green]Estimated improvement if top 5 applied: +{result.estimated_improvement:.1f} health[/green]")
        else:
            fmt.print(f"Estimated improvement if top 5 applied: +{result.estimated_improvement:.1f} health")
    fmt.print("")
    fmt.print("Legend: [both]=confirmed by global+project, [project]=this song only, [global]=all projects")


@db.command('ref-insights')
@click.option('--genre', '-g', default=None, help='Filter by genre')
@click.pass_context
def db_ref_insights_cmd(ctx, genre: Optional[str]):
    """Show insights learned from reference comparisons.

    Analyzes your stored reference comparisons to identify:
    - Common mixing issues across your tracks
    - Which recommendations tend to help
    - Genre-specific patterns
    - Your personal mixing tendencies

    Requires at least 3 stored reference comparisons.

    Example:
        als-doctor db ref-insights
        als-doctor db ref-insights --genre trance
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    database = get_db()

    if not database.is_initialized():
        fmt.error("Database not initialized. Run 'als-doctor db init' first.")
        raise SystemExit(1)

    result, msg = get_reference_insights(genre=genre)

    if result is None:
        fmt.error(msg)
        raise SystemExit(1)

    # Header
    fmt.header("REFERENCE COMPARISON INSIGHTS")
    fmt.print("")
    fmt.print(f"Total comparisons: {result.total_comparisons}")
    fmt.print(f"Total recommendations tracked: {result.total_recommendations}")

    if genre:
        fmt.print(f"Filtered by genre: {genre}")
    fmt.print("")

    # Personal tendency
    fmt.print_line("-", 60)
    fmt.print("YOUR MIXING TENDENCIES:")
    fmt.print("")
    fmt.print(f"  {result.tendency_summary}")
    fmt.print("")

    # Common issues
    if result.common_issues:
        fmt.print_line("-", 60)
        fmt.print("COMMON ISSUES FOUND:")
        fmt.print("")

        for issue in result.common_issues[:7]:
            stem = issue['stem_type'] or 'overall'
            issue_type = issue['issue_type']
            freq = issue['frequency']
            severity = issue['avg_severity']

            if fmt.use_rich:
                fmt.print(f"  [yellow]![/yellow] {stem}: {issue_type} issues ({freq}x, avg severity: {severity:.1f})")
            else:
                fmt.print(f"  ! {stem}: {issue_type} issues ({freq}x, avg severity: {severity:.1f})")

        fmt.print("")

    # Helpful recommendations
    if result.helpful_recommendations:
        fmt.print_line("-", 60)
        fmt.print("RECOMMENDATION EFFECTIVENESS:")
        fmt.print("")

        for rec in result.helpful_recommendations[:7]:
            if rec.times_applied == 0:
                continue

            success_rate = (rec.times_helped / rec.times_applied * 100) if rec.times_applied > 0 else 0

            # Color based on effectiveness
            if rec.avg_effect > 0.5:
                effect_str = "helpful" if not fmt.use_rich else "[green]helpful[/green]"
            elif rec.avg_effect < -0.5:
                effect_str = "not helpful" if not fmt.use_rich else "[red]not helpful[/red]"
            else:
                effect_str = "mixed results" if not fmt.use_rich else "[yellow]mixed results[/yellow]"

            cat = rec.category
            stem = f" ({rec.stem_type})" if rec.stem_type else ""
            fmt.print(f"  {cat}{stem}: {effect_str}")
            fmt.print(f"    Applied {rec.times_applied}x | Helped {rec.times_helped}x | Success: {success_rate:.0f}%")

        fmt.print("")

    # Genre patterns
    if result.genre_patterns:
        fmt.print_line("-", 60)
        fmt.print("GENRE-SPECIFIC PATTERNS:")
        fmt.print("")

        for g, patterns in result.genre_patterns.items():
            loudness = patterns['avg_loudness_diff']
            balance = patterns['avg_balance_score']
            count = patterns['count']

            loudness_str = f"{loudness:+.1f}dB" if loudness != 0 else "on target"
            fmt.print(f"  {g}: avg loudness {loudness_str}, balance {balance:.0f}% ({count} comparisons)")

        fmt.print("")

    if result.total_comparisons < 5:
        fmt.print_line("=", 60)
        fmt.print("Tip: Compare more tracks against references to improve insights.")
        fmt.print("     Use: python analyze.py --audio mix.wav --compare-ref reference.wav")


@db.command('ref-history')
@click.argument('song', required=False, default=None)
@click.option('--limit', '-n', default=10, help='Number of comparisons to show')
@click.pass_context
def db_ref_history_cmd(ctx, song: Optional[str], limit: int):
    """Show history of reference comparisons.

    Lists stored reference comparisons with similarity scores
    and key metrics. Optionally filter by project.

    Example:
        als-doctor db ref-history
        als-doctor db ref-history "22 Project"
        als-doctor db ref-history --limit 20
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    database = get_db()

    if not database.is_initialized():
        fmt.error("Database not initialized. Run 'als-doctor db init' first.")
        raise SystemExit(1)

    comparisons, msg = get_reference_history(search_term=song, limit=limit)

    if not comparisons:
        fmt.print("No reference comparisons found.")
        fmt.print("")
        fmt.print("To store comparisons:")
        fmt.print("  python analyze.py --audio mix.wav --compare-ref reference.wav --save")
        return

    # Header
    fmt.header("REFERENCE COMPARISON HISTORY")
    fmt.print("")
    fmt.print(f"Found {len(comparisons)} comparison(s)")
    if song:
        fmt.print(f"Filtered by: {song}")
    fmt.print("")

    fmt.print_line("-", 70)

    for comp in comparisons:
        # File info
        user_name = Path(comp.user_file_path).name[:30]
        ref_name = comp.reference_name or Path(comp.reference_file_path).name[:25]

        fmt.print(f"{user_name}")
        fmt.print(f"  vs: {ref_name}")

        # Metrics
        balance = comp.balance_score
        loudness = comp.loudness_diff_db

        if fmt.use_rich:
            if balance >= 80:
                balance_str = f"[green]{balance:.0f}%[/green]"
            elif balance >= 60:
                balance_str = f"[yellow]{balance:.0f}%[/yellow]"
            else:
                balance_str = f"[red]{balance:.0f}%[/red]"
        else:
            balance_str = f"{balance:.0f}%"

        loudness_str = f"{loudness:+.1f}dB" if loudness != 0 else "0dB"

        fmt.print(f"  Balance: {balance_str} | Loudness diff: {loudness_str}")

        # Stem summary if available
        if comp.stem_comparisons:
            stems = list(comp.stem_comparisons.keys())
            severities = [comp.stem_comparisons[s].get('severity', 'unknown') for s in stems]
            issues = [s for s, sev in zip(stems, severities) if sev in ('moderate', 'significant')]
            if issues:
                fmt.print(f"  Issues in: {', '.join(issues)}")

        # Date
        date_str = comp.compared_at.strftime("%Y-%m-%d %H:%M")
        if fmt.use_rich:
            fmt.print(f"  [dim]{date_str}[/dim]")
        else:
            fmt.print(f"  {date_str}")

        fmt.print("")

    fmt.print_line("=", 70)
    fmt.print(f"Use 'als-doctor db ref-insights' to see patterns learned from these comparisons")


@db.command('focus')
@click.option('--limit', default=5, help='Maximum items per category (default: 5)')
@click.pass_context
def db_focus_cmd(ctx, limit: int):
    """Show what to work on next across all projects.

    Analyzes all projects and categorizes them into actionable groups:

    - Quick Wins: Grade C projects with few critical issues - easy fixes, big impact
    - Deep Work: Grade D-F projects needing significant attention
    - Ready to Polish: Grade B projects close to A - final touches

    This helps you prioritize your mixing time effectively.

    Example:
        als-doctor db focus
        als-doctor db focus --limit 3
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    database = get_db()

    if not database.is_initialized():
        fmt.error("Database not initialized. Run 'als-doctor db init' first.")
        raise SystemExit(1)

    # Get today's focus data using dashboard function
    try:
        from dashboard import get_todays_focus, TodaysFocus
        focus = get_todays_focus()
    except ImportError:
        # Fallback implementation if dashboard module isn't available
        focus = _get_todays_focus_fallback(database)

    if focus.total_suggestions == 0:
        fmt.print("")
        fmt.print("No projects need attention right now!")
        fmt.print("")
        fmt.print("Either all projects are Grade A, or there's no data yet.")
        fmt.print("Scan some projects with: als-doctor scan <folder> --save")
        return

    fmt.header("🎯 WHAT TO WORK ON TODAY")
    fmt.print("")
    fmt.print("Based on your project health, here's where to focus your energy:")
    fmt.print("")

    # Quick Wins
    if focus.quick_wins:
        if fmt.use_rich:
            fmt.print(f"[bold green]⚡ QUICK WINS[/bold green] (small fixes, big impact)")
        else:
            fmt.print("⚡ QUICK WINS (small fixes, big impact)")
        fmt.print_line("-", 50)

        for item in focus.quick_wins[:limit]:
            score_text = fmt.grade_with_score(item.health_score, item.grade)
            gain_text = f"+{item.potential_gain}" if item.potential_gain > 0 else ""
            if fmt.use_rich:
                fmt.print(f"  • [bold]{item.song_name}[/bold] {score_text}")
                fmt.print(f"    [dim]{item.reason}[/dim]")
                if gain_text:
                    fmt.print(f"    [green]Potential: {gain_text} points[/green]")
            else:
                fmt.print(f"  • {item.song_name} {score_text}")
                fmt.print(f"    {item.reason}")
                if gain_text:
                    fmt.print(f"    Potential: {gain_text} points")
            fmt.print("")
    else:
        if fmt.use_rich:
            fmt.print("[dim]No quick wins available - all easy fixes done![/dim]")
        else:
            fmt.print("No quick wins available - all easy fixes done!")
        fmt.print("")

    # Deep Work
    if focus.deep_work:
        if fmt.use_rich:
            fmt.print(f"[bold yellow]🔨 DEEP WORK[/bold yellow] (needs focused attention)")
        else:
            fmt.print("🔨 DEEP WORK (needs focused attention)")
        fmt.print_line("-", 50)

        for item in focus.deep_work[:limit]:
            score_text = fmt.grade_with_score(item.health_score, item.grade)
            gain_text = f"+{item.potential_gain}" if item.potential_gain > 0 else ""
            if fmt.use_rich:
                fmt.print(f"  • [bold]{item.song_name}[/bold] {score_text}")
                fmt.print(f"    [dim]{item.reason}[/dim]")
                if gain_text:
                    fmt.print(f"    [yellow]Potential: {gain_text} points[/yellow]")
            else:
                fmt.print(f"  • {item.song_name} {score_text}")
                fmt.print(f"    {item.reason}")
                if gain_text:
                    fmt.print(f"    Potential: {gain_text} points")
            fmt.print("")
    else:
        if fmt.use_rich:
            fmt.print("[dim]No deep work items - nothing in critical condition![/dim]")
        else:
            fmt.print("No deep work items - nothing in critical condition!")
        fmt.print("")

    # Ready to Polish
    if focus.ready_to_polish:
        if fmt.use_rich:
            fmt.print(f"[bold cyan]✨ READY TO POLISH[/bold cyan] (almost there, final touches)")
        else:
            fmt.print("✨ READY TO POLISH (almost there, final touches)")
        fmt.print_line("-", 50)

        for item in focus.ready_to_polish[:limit]:
            score_text = fmt.grade_with_score(item.health_score, item.grade)
            gain_text = f"+{item.potential_gain}" if item.potential_gain > 0 else ""
            if fmt.use_rich:
                fmt.print(f"  • [bold]{item.song_name}[/bold] {score_text}")
                fmt.print(f"    [dim]{item.reason}[/dim]")
                if gain_text:
                    fmt.print(f"    [cyan]Potential: {gain_text} points[/cyan]")
            else:
                fmt.print(f"  • {item.song_name} {score_text}")
                fmt.print(f"    {item.reason}")
                if gain_text:
                    fmt.print(f"    Potential: {gain_text} points")
            fmt.print("")
    else:
        if fmt.use_rich:
            fmt.print("[dim]No items ready to polish - work on quick wins first![/dim]")
        else:
            fmt.print("No items ready to polish - work on quick wins first!")
        fmt.print("")

    # Summary
    fmt.print_line("=", 50)
    fmt.print(f"Total suggestions: {focus.total_suggestions}")
    fmt.print("")
    fmt.print("Use 'als-doctor db smart <file>' to get specific recommendations for a project.")


def _get_todays_focus_fallback(database):
    """Fallback implementation if dashboard module isn't available."""
    from dataclasses import dataclass, field
    from typing import List, Optional

    @dataclass
    class WorkItemFallback:
        project_id: int
        song_name: str
        category: str
        reason: str
        health_score: int
        grade: str
        potential_gain: int
        days_since_worked: Optional[int] = None

    @dataclass
    class TodaysFocusFallback:
        quick_wins: List[WorkItemFallback] = field(default_factory=list)
        deep_work: List[WorkItemFallback] = field(default_factory=list)
        ready_to_polish: List[WorkItemFallback] = field(default_factory=list)
        total_suggestions: int = 0

    conn = database.connection
    cursor = conn.cursor()

    quick_wins = []
    deep_work = []
    ready_to_polish = []

    # Get all projects with their latest version scores
    cursor.execute("""
        SELECT p.id, p.song_name, v.health_score, v.grade, v.critical_issues, v.total_issues
        FROM projects p
        JOIN versions v ON v.id = (
            SELECT id FROM versions WHERE project_id = p.id ORDER BY scanned_at DESC LIMIT 1
        )
        ORDER BY v.health_score ASC
    """)

    for row in cursor.fetchall():
        project_id = row['id']
        song_name = row['song_name']
        score = row['health_score']
        grade = row['grade']
        critical = row['critical_issues']
        total_issues = row['total_issues']

        if grade == 'F':
            potential = min(30, 100 - score)
            reason = f"{critical} critical issues to fix"
            deep_work.append(WorkItemFallback(
                project_id=project_id,
                song_name=song_name,
                category='deep_work',
                reason=reason,
                health_score=score,
                grade=grade,
                potential_gain=potential
            ))
        elif grade == 'D':
            potential = min(25, 60 - score)
            reason = f"{total_issues} total issues, {critical} critical"
            deep_work.append(WorkItemFallback(
                project_id=project_id,
                song_name=song_name,
                category='deep_work',
                reason=reason,
                health_score=score,
                grade=grade,
                potential_gain=potential
            ))
        elif grade == 'C':
            if critical <= 1:
                potential = min(20, 80 - score)
                reason = f"Only {critical} critical issue{'s' if critical != 1 else ''}"
                quick_wins.append(WorkItemFallback(
                    project_id=project_id,
                    song_name=song_name,
                    category='quick_win',
                    reason=reason,
                    health_score=score,
                    grade=grade,
                    potential_gain=potential
                ))
            else:
                potential = min(20, 80 - score)
                reason = f"{critical} critical issues need fixing"
                deep_work.append(WorkItemFallback(
                    project_id=project_id,
                    song_name=song_name,
                    category='deep_work',
                    reason=reason,
                    health_score=score,
                    grade=grade,
                    potential_gain=potential
                ))
        elif grade == 'B':
            potential = 80 - score
            if potential > 0:
                reason = f"Just {potential} points from Grade A"
                ready_to_polish.append(WorkItemFallback(
                    project_id=project_id,
                    song_name=song_name,
                    category='ready_to_polish',
                    reason=reason,
                    health_score=score,
                    grade=grade,
                    potential_gain=potential
                ))

    # Sort by potential gain
    quick_wins.sort(key=lambda x: x.potential_gain, reverse=True)
    deep_work.sort(key=lambda x: x.potential_gain, reverse=True)
    ready_to_polish.sort(key=lambda x: x.potential_gain, reverse=True)

    total = len(quick_wins) + len(deep_work) + len(ready_to_polish)

    return TodaysFocusFallback(
        quick_wins=quick_wins,
        deep_work=deep_work,
        ready_to_polish=ready_to_polish,
        total_suggestions=total
    )


@db.command('report')
@click.argument('song', required=False, default=None)
@click.option('--all', 'all_projects', is_flag=True, help='Generate library report for all projects')
@click.option('--html', 'output_path', type=click.Path(), default=None,
              help='Output path for HTML file (defaults to reports/<song>/)')
@click.pass_context
def db_report_cmd(ctx, song: Optional[str], all_projects: bool, output_path: Optional[str]):
    """Generate HTML reports for projects.

    Generate self-contained HTML reports with health data,
    issue lists, and version history. Reports are mobile-friendly
    with dark mode design.

    Without arguments: generates history report for a song.
    With --all: generates library overview report.

    Example:
        als-doctor db report "My Song"
        als-doctor db report "My Song" --html output.html
        als-doctor db report --all
        als-doctor db report --all --html library.html
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    database = get_db()

    if not database.is_initialized():
        fmt.error("Database not initialized. Run 'als-doctor db init' first.")
        raise SystemExit(1)

    if all_projects:
        # Generate library report
        _generate_library_html_report(fmt, output_path)
    elif song:
        # Generate history report for specific song
        _generate_history_html_report(song, fmt, output_path)
    else:
        fmt.error("Please specify a song name or use --all for library report.")
        fmt.print("")
        fmt.print("Examples:")
        fmt.print("  als-doctor db report \"My Song\"       - History report for a song")
        fmt.print("  als-doctor db report --all           - Full library report")
        raise SystemExit(1)


def _generate_history_html_report(song: str, fmt: CLIFormatter, output_path: Optional[str]):
    """Generate HTML history report for a song."""
    # Get project history
    history, message = get_project_history(song)

    if history is None:
        fmt.error(message)
        raise SystemExit(1)

    # Convert versions to ReportVersion objects
    report_versions = []
    best_report_version = None
    current_report_version = None

    for v in history.versions:
        rv = ReportVersion(
            id=v.id,
            filename=v.als_filename,
            path=v.als_path,
            health_score=v.health_score,
            grade=v.grade,
            total_issues=v.total_issues,
            critical_issues=0,  # Not in VersionHistory, use 0
            warning_issues=0,   # Not in VersionHistory, use 0
            scanned_at=v.scanned_at,
            delta=v.delta,
            is_best=v.is_best,
            is_current=(v.id == history.current_version.id if history.current_version else False)
        )
        report_versions.append(rv)

        if v.is_best:
            best_report_version = rv
        if history.current_version and v.id == history.current_version.id:
            current_report_version = rv

    # Prepare report data
    report_data = HistoryReportData(
        song_name=history.song_name,
        folder_path=history.folder_path,
        versions=report_versions,
        best_version=best_report_version,
        current_version=current_report_version
    )

    # Determine output path
    if output_path:
        out_path = Path(output_path)
    else:
        out_path = get_default_report_path('history', history.song_name)

    # Generate report
    try:
        _, saved_path = generate_history_report(report_data, out_path)
        if saved_path:
            fmt.success(f"History report saved to: {saved_path}")
    except Exception as e:
        fmt.error(f"Failed to generate HTML report: {e}")
        raise SystemExit(1)


def _generate_library_html_report(fmt: CLIFormatter, output_path: Optional[str]):
    """Generate HTML library report."""
    # Get library status
    status, message = get_library_status()

    if status is None:
        fmt.error(message)
        raise SystemExit(1)

    # Get all projects for the projects table
    projects_list, stats = list_projects(sort_by='name')

    # Convert to dict format for template
    projects_data = [
        {
            'song_name': p.song_name,
            'version_count': p.version_count,
            'best_score': p.best_score,
            'best_grade': p.best_grade,
            'latest_score': p.latest_score,
            'latest_grade': p.latest_grade,
            'trend': p.trend
        }
        for p in projects_list
    ]

    # Convert grade distribution
    grade_data = [
        GradeData(
            grade=g.grade,
            count=g.count,
            percentage=g.percentage
        )
        for g in status.grade_distribution
    ]

    # Prepare report data
    report_data = LibraryReportData(
        total_projects=status.total_projects,
        total_versions=status.total_versions,
        total_issues=status.total_issues,
        last_scan_date=status.last_scan_date,
        grade_distribution=grade_data,
        ready_to_release=status.ready_to_release,
        needs_work=status.needs_work,
        projects=projects_data
    )

    # Determine output path
    if output_path:
        out_path = Path(output_path)
    else:
        out_path = get_default_report_path('library')

    # Generate report
    try:
        _, saved_path = generate_library_report(report_data, out_path)
        if saved_path:
            fmt.success(f"Library report saved to: {saved_path}")
    except Exception as e:
        fmt.error(f"Failed to generate HTML report: {e}")
        raise SystemExit(1)


def _analyze_als_file(als_path: Path, fmt: Optional[CLIFormatter] = None) -> Optional[ScanResult]:
    """
    Analyze a single .als file and return a ScanResult.

    Returns None if analysis fails.
    """
    result = _analyze_als_file_full(als_path, fmt)
    if result:
        return result[0]  # Just the ScanResult
    return None


def _analyze_als_file_full(als_path: Path, fmt: Optional[CLIFormatter] = None):
    """
    Analyze a single .als file and return both ScanResult and device analysis.

    Returns:
        Tuple of (ScanResult, ProjectDeviceAnalysis) or None if analysis fails.
    """
    if fmt is None:
        fmt = get_formatter()

    try:
        # Import analysis modules
        from device_chain_analyzer import analyze_als_devices
        from effect_chain_doctor import EffectChainDoctor

        # Analyze the project
        analysis = analyze_als_devices(str(als_path))
        doctor = EffectChainDoctor()
        diagnosis = doctor.diagnose(analysis)

        # Convert issues to ScanResultIssue format
        issues = []

        # Add global issues
        for issue in diagnosis.global_issues:
            issues.append(ScanResultIssue(
                track_name=issue.track_name,
                severity=issue.severity.value,
                category=issue.category.value,
                description=issue.description,
                fix_suggestion=issue.recommendation
            ))

        # Add track issues
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
            als_path=str(als_path),
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

        return (scan_result, analysis)
    except Exception as e:
        fmt.error(f"analyzing {als_path.name}: {e}", prefix="  ERROR ")
        return None


@cli.command('scan')
@click.argument('directory', type=click.Path(exists=True))
@click.option('--save', is_flag=True, help='Save results to database')
@click.option('--limit', '-l', type=int, default=None, help='Limit number of files to scan')
@click.pass_context
def scan_cmd(ctx, directory: str, save: bool, limit: Optional[int]):
    """Scan a directory for .als files.

    Recursively scans the directory for Ableton Live Set files
    and analyzes their health.

    Example:
        als-doctor scan "D:/Ableton Projects"
        als-doctor scan "D:/Ableton Projects" --save
        als-doctor scan "D:/Ableton Projects" --save --limit 10
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    dir_path = Path(directory)
    als_files = list(dir_path.rglob("*.als"))

    if limit:
        als_files = als_files[:limit]

    fmt.print(f"Found {len(als_files)} .als file(s) in {directory}")

    if save:
        database = get_db()
        if not database.is_initialized():
            fmt.error("Database not initialized. Run 'als-doctor db init' first.")
            raise SystemExit(1)

    if not als_files:
        fmt.print("No .als files found.")
        return

    # Analyze each file
    results = []
    success_count = 0
    fail_count = 0

    fmt.print("")
    for i, als_path in enumerate(als_files, 1):
        # Use print for progress since we need inline output
        print(f"[{i}/{len(als_files)}] Analyzing {als_path.name}...", end="", flush=True)

        scan_result = _analyze_als_file(als_path, fmt)

        if scan_result:
            results.append(scan_result)
            grade = scan_result.grade
            score = scan_result.health_score

            # Format grade with color
            grade_str = fmt.grade_text(grade)
            if fmt.use_rich:
                print(f" {grade_str} {score}/100, {scan_result.total_issues} issues")
            else:
                print(f" [{grade}] {score}/100, {scan_result.total_issues} issues")
            success_count += 1
        else:
            print()  # Newline after error
            fail_count += 1

    fmt.print("")
    fmt.print(f"Scanned: {success_count} successful, {fail_count} failed")

    if save and results:
        fmt.print("")
        fmt.print("Saving to database...")

        saved_count = 0
        for result in results:
            success, message, _ = persist_scan_result(result)
            if success:
                saved_count += 1
            else:
                fmt.warning(message, prefix="  WARN: ")

        fmt.success(f"Saved {saved_count} scan result(s) to database.")
    elif not save:
        fmt.print("")
        fmt.print("Use --save to persist results to database.")


@cli.command('diagnose')
@click.argument('file', type=click.Path(exists=True))
@click.option('--save', is_flag=True, help='Save results to database')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed issue list')
@click.option('--midi', is_flag=True, help='Include MIDI analysis')
@click.option('--smart', is_flag=True, default=None,
              help='Use smart recommendations based on history (auto-enabled with 20+ versions)')
@click.option('--no-smart', is_flag=True, help='Disable smart recommendations')
@click.option('--html', type=click.Path(), default=None,
              help='Generate HTML report (optionally specify output path)')
@click.option('--format', '-f', 'output_format', type=click.Choice(['text', 'json']),
              default='text', help='Output format (default: text)')
@click.option('--output', '-o', type=click.Path(), default=None,
              help='Output file for JSON format')
@click.pass_context
def diagnose_cmd(ctx, file: str, save: bool, verbose: bool, midi: bool,
                 smart: Optional[bool], no_smart: bool, html: Optional[str],
                 output_format: str, output: Optional[str]):
    """Analyze a single .als file.

    Performs a detailed health analysis on the specified
    Ableton Live Set file.

    Use --format json for structured JSON output:
    - Includes track names and indices for DeviceResolver
    - Includes device chains with indices and types
    - Machine-readable for Claude Code integration
    - Use -o/--output to save to file

    Use --smart to get prioritized recommendations based on your history:
    - Prioritizes fixes that have helped before
    - Shows confidence levels based on past results
    - Automatically enabled when 20+ versions in database

    Use --midi to include MIDI and arrangement analysis:
    - Detects empty MIDI clips
    - Detects very short clips (< 1 beat)
    - Finds duplicate MIDI content
    - Shows arrangement structure from locators

    Use --html to generate a self-contained HTML report:
    - Mobile-responsive dark mode design
    - Includes health gauge, statistics, and issue list
    - Can specify output path or use default (reports/<song>/)

    Example:
        als-doctor diagnose "D:/Projects/MySong.als"
        als-doctor diagnose "D:/Projects/MySong.als" --save
        als-doctor diagnose "D:/Projects/MySong.als" --verbose
        als-doctor diagnose "D:/Projects/MySong.als" --midi
        als-doctor diagnose "D:/Projects/MySong.als" --smart
        als-doctor diagnose "D:/Projects/MySong.als" --html
        als-doctor diagnose "D:/Projects/MySong.als" --html report.html
        als-doctor diagnose "D:/Projects/MySong.als" --format json
        als-doctor diagnose "D:/Projects/MySong.als" -f json -o analysis.json
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    file_path = Path(file)

    if file_path.suffix.lower() != '.als':
        fmt.error("File must be an Ableton Live Set (.als)")
        raise SystemExit(1)

    # Handle JSON output format
    if output_format == 'json':
        result = _analyze_als_file_full(file_path, fmt)
        if not result:
            # Output error as JSON
            import json as json_module
            error_json = json_module.dumps({"success": False, "error": "Failed to analyze file"})
            click.echo(error_json)
            raise SystemExit(1)

        scan_result, device_analysis = result

        # Analyze MIDI if requested
        midi_analysis = None
        if midi:
            midi_analysis = _analyze_midi(file_path, fmt)

        # Create JSON output
        json_output = create_json_output(
            str(file_path),
            scan_result,
            device_analysis,
            midi_analysis
        )

        # Output or save JSON
        if output:
            json_output.save(output)
            click.echo(f"JSON saved to: {output}")
        else:
            click.echo(json_output.to_json())

        return  # Exit early for JSON format

    fmt.print(f"Diagnosing: {file_path.name}")
    fmt.print("")

    scan_result = _analyze_als_file(file_path, fmt)

    if not scan_result:
        fmt.error("Failed to analyze file.")
        raise SystemExit(1)

    # Determine if smart mode should be used
    # Auto-enable smart mode when 20+ versions exist, unless --no-smart
    use_smart = False
    if no_smart:
        use_smart = False
    elif smart:
        use_smart = True
    else:
        # Auto-enable if sufficient history
        use_smart = has_sufficient_history()

    # Display results
    grade = scan_result.grade
    score = scan_result.health_score

    fmt.section_header(f"HEALTH SCORE: {score}/100 [{grade}]")
    fmt.health_score_display(score, grade)
    fmt.print_line("=", 50)
    fmt.print("")

    # Stats with colored values
    fmt.print(f"  Total Issues:    {scan_result.total_issues}")
    critical_color = "red" if scan_result.critical_issues > 0 else "green"
    warning_color = "yellow" if scan_result.warning_issues > 0 else "green"

    if fmt.use_rich:
        fmt.print(f"  Critical:        [{critical_color}]{scan_result.critical_issues}[/{critical_color}]")
        fmt.print(f"  Warnings:        [{warning_color}]{scan_result.warning_issues}[/{warning_color}]")
    else:
        fmt.print(f"  Critical:        {scan_result.critical_issues}")
        fmt.print(f"  Warnings:        {scan_result.warning_issues}")

    fmt.print(f"  Total Devices:   {scan_result.total_devices}")
    fmt.print(f"  Disabled:        {scan_result.disabled_devices}")
    fmt.print(f"  Clutter:         {scan_result.clutter_percentage:.1f}%")
    fmt.print("")

    # MIDI analysis
    midi_analysis = None
    if midi:
        midi_analysis = _analyze_midi(file_path, fmt)
        if midi_analysis:
            _display_midi_analysis(midi_analysis, fmt, verbose)

    # Smart recommendations mode
    if use_smart:
        _display_smart_recommendations(str(file_path), scan_result, fmt, verbose)
    elif verbose and scan_result.issues:
        fmt.print_line("-", 50)
        fmt.header("ISSUES:")
        fmt.print_line("-", 50)

        # Group by severity
        critical = [i for i in scan_result.issues if i.severity == 'critical']
        warnings = [i for i in scan_result.issues if i.severity == 'warning']
        suggestions = [i for i in scan_result.issues if i.severity == 'suggestion']

        if critical:
            fmt.print("")
            if fmt.use_rich:
                fmt.print("[severity.critical]CRITICAL:[/severity.critical]")
            else:
                fmt.print("CRITICAL:")
            for issue in critical[:5]:
                fmt.issue('critical', issue.description, issue.track_name)

        if warnings:
            fmt.print("")
            if fmt.use_rich:
                fmt.print("[severity.warning]WARNINGS:[/severity.warning]")
            else:
                fmt.print("WARNINGS:")
            for issue in warnings[:10]:
                fmt.issue('warning', issue.description, issue.track_name)

        if suggestions and verbose:
            fmt.print("")
            if fmt.use_rich:
                fmt.print("[severity.suggestion]SUGGESTIONS:[/severity.suggestion]")
            else:
                fmt.print("SUGGESTIONS:")
            for issue in suggestions[:5]:
                fmt.issue('suggestion', issue.description, issue.track_name)

        fmt.print("")

    if save:
        database = get_db()
        if not database.is_initialized():
            fmt.error("Database not initialized. Run 'als-doctor db init' first.")
            raise SystemExit(1)

        success, message, version_id = persist_scan_result(scan_result)
        if success:
            fmt.success(message)

            # Save MIDI stats if MIDI analysis was performed
            if midi_analysis and version_id:
                midi_stats = MIDIStats(
                    version_id=version_id,
                    total_midi_tracks=midi_analysis.total_midi_tracks,
                    total_midi_clips=midi_analysis.total_midi_clips,
                    total_notes=midi_analysis.total_notes,
                    total_empty_clips=midi_analysis.total_empty_clips,
                    total_short_clips=midi_analysis.total_short_clips,
                    total_duplicate_clips=midi_analysis.total_duplicate_clips,
                    tracks_without_content=midi_analysis.tracks_without_content,
                    has_arrangement_markers=midi_analysis.arrangement.has_arrangement_markers if midi_analysis.arrangement else False,
                    total_sections=midi_analysis.arrangement.total_sections if midi_analysis.arrangement else 0,
                    arrangement_structure=midi_analysis.arrangement.suggested_structure if midi_analysis.arrangement else None
                )
                midi_success, midi_message = persist_midi_stats(midi_stats)
                if midi_success:
                    fmt.success(f"  {midi_message}")
                else:
                    fmt.warning(f"  {midi_message}")
        else:
            fmt.error(message)
            raise SystemExit(1)
    else:
        fmt.print("Use --save to persist results to database.")

    # Generate HTML report if requested
    if html is not None:
        # Determine output path
        if html == '' or html is True:
            # --html flag without path, use default
            song_name = file_path.parent.name
            output_path = get_default_report_path('project', song_name)
        else:
            output_path = Path(html)

        # Prepare report data
        report_issues = [
            ReportIssue(
                track_name=i.track_name or '',
                severity=i.severity,
                category=i.category,
                description=i.description,
                fix_suggestion=i.fix_suggestion
            )
            for i in scan_result.issues
        ]

        report_data = ProjectReportData(
            song_name=file_path.parent.name,
            folder_path=str(file_path.parent),
            als_filename=file_path.name,
            als_path=str(file_path),
            health_score=scan_result.health_score,
            grade=scan_result.grade,
            total_issues=scan_result.total_issues,
            critical_issues=scan_result.critical_issues,
            warning_issues=scan_result.warning_issues,
            total_devices=scan_result.total_devices,
            disabled_devices=scan_result.disabled_devices,
            clutter_percentage=scan_result.clutter_percentage,
            scanned_at=datetime.now(),
            issues=report_issues
        )

        try:
            _, saved_path = generate_project_report(report_data, output_path)
            if saved_path:
                fmt.success(f"HTML report saved to: {saved_path}")
        except Exception as e:
            fmt.error(f"Failed to generate HTML report: {e}")


def _display_smart_recommendations(
    als_path: str,
    scan_result: ScanResult,
    fmt: CLIFormatter,
    verbose: bool
):
    """Display smart recommendations with confidence scoring."""
    result, message = smart_diagnose(als_path, scan_result)

    if result is None:
        # Fallback to standard display if smart diagnose fails
        fmt.warning(f"Smart recommendations unavailable: {message}")
        fmt.print("Showing standard recommendations instead.")
        fmt.print("")

        if verbose and scan_result.issues:
            fmt.print_line("-", 50)
            fmt.header("ISSUES:")
            fmt.print_line("-", 50)

            for issue in scan_result.issues[:15]:
                fmt.issue(issue.severity, issue.description, issue.track_name)
            fmt.print("")
        return

    # Show smart recommendations header
    fmt.print_line("-", 50)
    if fmt.use_rich:
        fmt.print("[highlight]SMART RECOMMENDATIONS[/highlight]")
    else:
        fmt.print("SMART RECOMMENDATIONS")
    fmt.print_line("-", 50)

    # Context info
    if result.has_sufficient_history:
        if fmt.use_rich:
            fmt.print(f"  Based on: [cyan]{result.versions_analyzed}[/cyan] versions analyzed")
        else:
            fmt.print(f"  Based on: {result.versions_analyzed} versions analyzed")
    else:
        fmt.print(f"  Limited history: {result.versions_analyzed} versions (need 20+ for full insights)")

    if result.profile_available and result.profile_similarity is not None:
        if fmt.use_rich:
            if result.profile_similarity >= 80:
                sim_color = 'green'
            elif result.profile_similarity >= 60:
                sim_color = 'yellow'
            else:
                sim_color = 'red'
            fmt.print(f"  Profile similarity: [{sim_color}]{result.profile_similarity}%[/{sim_color}]")
        else:
            fmt.print(f"  Profile similarity: {result.profile_similarity}%")

    fmt.print("")

    if not result.recommendations:
        if fmt.use_rich:
            fmt.print("[green]No issues found! Your project is in great shape.[/green]")
        else:
            fmt.print("No issues found! Your project is in great shape.")
        return

    # Display recommendations grouped by priority
    high_priority = [r for r in result.recommendations if r.priority >= 80]
    medium_priority = [r for r in result.recommendations if 50 <= r.priority < 80]
    low_priority = [r for r in result.recommendations if r.priority < 50]

    # Limit display
    max_high = 5 if verbose else 3
    max_medium = 5 if verbose else 2
    max_low = 3 if verbose else 0

    if high_priority:
        if fmt.use_rich:
            fmt.print("[red]HIGH PRIORITY:[/red]")
        else:
            fmt.print("HIGH PRIORITY:")

        for rec in high_priority[:max_high]:
            _display_recommendation(rec, fmt, verbose)

        if len(high_priority) > max_high:
            fmt.print(f"  ... and {len(high_priority) - max_high} more")
        fmt.print("")

    if medium_priority:
        if fmt.use_rich:
            fmt.print("[yellow]MEDIUM PRIORITY:[/yellow]")
        else:
            fmt.print("MEDIUM PRIORITY:")

        for rec in medium_priority[:max_medium]:
            _display_recommendation(rec, fmt, verbose)

        if len(medium_priority) > max_medium:
            fmt.print(f"  ... and {len(medium_priority) - max_medium} more")
        fmt.print("")

    if low_priority and max_low > 0:
        if fmt.use_rich:
            fmt.print("[dim]LOW PRIORITY:[/dim]")
        else:
            fmt.print("LOW PRIORITY:")

        for rec in low_priority[:max_low]:
            _display_recommendation(rec, fmt, verbose)

        if len(low_priority) > max_low:
            fmt.print(f"  ... and {len(low_priority) - max_low} more")
        fmt.print("")

    # Summary
    fmt.print_line("-", 50)
    fmt.print(f"Total: {result.critical_count} critical, {result.warning_count} warnings, {result.suggestion_count} suggestions")

    # Tips based on history
    if result.has_sufficient_history:
        helped_count = len([r for r in result.recommendations if r.helped_before])
        if helped_count > 0:
            if fmt.use_rich:
                fmt.print(f"[green]OK[/green] {helped_count} recommendation(s) based on fixes that worked for you before")
            else:
                fmt.print(f"OK {helped_count} recommendation(s) based on fixes that worked for you before")


def _display_recommendation(rec: SmartRecommendation, fmt: CLIFormatter, verbose: bool):
    """Display a single smart recommendation."""
    # Severity icon
    if rec.severity == 'critical':
        icon = '!' if not fmt.use_rich else '[red]![/red]'
    elif rec.severity == 'warning':
        icon = '*' if not fmt.use_rich else '[yellow]*[/yellow]'
    else:
        icon = '-' if not fmt.use_rich else '[dim]-[/dim]'

    # Track info
    track_str = f" ({rec.track_name})" if rec.track_name else ""

    # Priority indicator
    priority_str = f"[P{rec.priority}]"

    # Confidence
    conf_str = f"[{rec.confidence}]"
    if fmt.use_rich:
        if rec.confidence == 'HIGH':
            conf_str = f"[green][HIGH][/green]"
        elif rec.confidence == 'MEDIUM':
            conf_str = f"[yellow][MEDIUM][/yellow]"
        else:
            conf_str = f"[dim][LOW][/dim]"

    # Main line
    fmt.print(f"  {icon} {rec.description}{track_str}")

    if verbose:
        # Show recommendation and confidence reason
        if rec.recommendation:
            fmt.print(f"      Fix: {rec.recommendation}")
        if rec.helped_before:
            if fmt.use_rich:
                fmt.print(f"      [green]OK This type of fix helped {rec.times_helped}x before (avg +{rec.avg_improvement:.1f})[/green]")
            else:
                fmt.print(f"      OK This type of fix helped {rec.times_helped}x before (avg +{rec.avg_improvement:.1f})")
        elif rec.confidence_reason:
            if fmt.use_rich:
                fmt.print(f"      [dim]{rec.confidence_reason}[/dim]")
            else:
                fmt.print(f"      {rec.confidence_reason}")


def _analyze_midi(file_path: Path, fmt: CLIFormatter) -> Optional[MIDIAnalysisResult]:
    """Analyze MIDI content in an ALS file."""
    try:
        from als_parser import ALSParser

        parser = ALSParser()
        project = parser.parse(str(file_path))

        analyzer = MIDIAnalyzer()
        return analyzer.analyze(project)
    except Exception as e:
        fmt.warning(f"MIDI analysis failed: {e}")
        return None


def _display_midi_analysis(analysis: MIDIAnalysisResult, fmt: CLIFormatter, verbose: bool):
    """Display MIDI analysis results."""
    fmt.print_line("-", 50)
    fmt.header("MIDI ANALYSIS")
    fmt.print_line("-", 50)
    fmt.print("")

    # Summary stats
    fmt.print(f"  MIDI Tracks:     {analysis.total_midi_tracks}")
    fmt.print(f"  MIDI Clips:      {analysis.total_midi_clips}")
    fmt.print(f"  Total Notes:     {analysis.total_notes}")
    fmt.print("")

    # Issues summary
    if analysis.total_empty_clips > 0:
        if fmt.use_rich:
            fmt.print(f"  [yellow]Empty Clips:     {analysis.total_empty_clips}[/yellow]")
        else:
            fmt.print(f"  Empty Clips:     {analysis.total_empty_clips}")

    if analysis.total_short_clips > 0:
        if fmt.use_rich:
            fmt.print(f"  [yellow]Short Clips:     {analysis.total_short_clips}[/yellow]")
        else:
            fmt.print(f"  Short Clips:     {analysis.total_short_clips}")

    if analysis.total_duplicate_clips > 0:
        if fmt.use_rich:
            fmt.print(f"  [yellow]Duplicate Clips: {analysis.total_duplicate_clips}[/yellow]")
        else:
            fmt.print(f"  Duplicate Clips: {analysis.total_duplicate_clips}")

    if analysis.tracks_without_content > 0:
        if fmt.use_rich:
            fmt.print(f"  [yellow]Empty Tracks:    {analysis.tracks_without_content}[/yellow]")
        else:
            fmt.print(f"  Empty Tracks:    {analysis.tracks_without_content}")

    # Arrangement structure
    if analysis.arrangement:
        arr = analysis.arrangement
        fmt.print("")
        fmt.print("  Arrangement:")
        if arr.has_arrangement_markers:
            fmt.print(f"    Markers:       {len(arr.locators)}")
            fmt.print(f"    Sections:      {arr.total_sections}")
            if arr.suggested_structure:
                fmt.print(f"    Structure:     {arr.suggested_structure}")

            # List sections if verbose
            if verbose and arr.sections:
                fmt.print("")
                fmt.print("    Sections:")
                for section in arr.sections[:10]:
                    bars = f"({section.duration_bars:.1f} bars)" if section.duration_bars > 0 else ""
                    fmt.print(f"      - {section.name}: {section.start_beat:.0f}-{section.end_beat:.0f} beats {bars}")
                if len(arr.sections) > 10:
                    fmt.print(f"      ... and {len(arr.sections) - 10} more")
        else:
            if fmt.use_rich:
                fmt.print("    [dim]No arrangement markers found[/dim]")
            else:
                fmt.print("    No arrangement markers found")
            fmt.print("    Tip: Add locators to mark sections (Intro, Buildup, Drop, etc.)")

    # Detailed clip issues (if verbose)
    if verbose and (analysis.clip_issues or analysis.track_issues):
        fmt.print("")
        fmt.print("  MIDI Issues:")

        for issue in analysis.clip_issues[:8]:
            severity_color = 'yellow' if issue.severity == 'warning' else 'cyan'
            if fmt.use_rich:
                fmt.print(f"    [{severity_color}]-[/{severity_color}] {issue.description}")
            else:
                fmt.print(f"    - {issue.description}")

        for issue in analysis.track_issues[:5]:
            if fmt.use_rich:
                fmt.print(f"    [cyan]-[/cyan] {issue.description}")
            else:
                fmt.print(f"    - {issue.description}")

        total_issues = len(analysis.clip_issues) + len(analysis.track_issues)
        shown = min(8, len(analysis.clip_issues)) + min(5, len(analysis.track_issues))
        if total_issues > shown:
            fmt.print(f"    ... and {total_issues - shown} more")

    fmt.print("")


@cli.command('best')
@click.argument('song')
@click.option('--open', 'open_folder', is_flag=True, help='Open folder in file explorer')
@click.pass_context
def best_cmd(ctx, song: str, open_folder: bool):
    """Find the best version of a song.

    Looks up the highest-scoring version of the specified song
    in the database. If multiple versions tie for the highest score,
    the most recently scanned one is returned.

    Shows a comparison against the latest version if they differ.

    Example:
        als-doctor best "22 Project"
        als-doctor best 22 --open
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    database = get_db()

    if not database.is_initialized():
        fmt.error("Database not initialized. Run 'als-doctor db init' first.")
        raise SystemExit(1)

    result, message = get_best_version(song)

    if result is None:
        fmt.error(message)
        raise SystemExit(1)

    # Header
    fmt.header(f"BEST VERSION: {result.song_name}")
    fmt.print("")

    # Best version details
    grade_str = fmt.grade_text(result.best_grade)
    if fmt.use_rich:
        fmt.print(f"[status.success]* {result.best_als_filename}[/status.success]")
    else:
        fmt.print(f"* {result.best_als_filename}")
    fmt.print(f"  Score: {result.best_health_score}/100 {grade_str}")
    fmt.print(f"  Path: {result.best_als_path}")
    fmt.print(f"  Scanned: {result.best_scanned_at.strftime('%Y-%m-%d %H:%M')}")

    # Comparison with latest if different
    if not result.is_best_same_as_latest:
        fmt.print("")
        fmt.print(f"  vs Latest ({result.latest_als_filename}):")

        # Health comparison - note: delta is best - latest, so negative means latest is better
        if result.health_delta > 0:
            # Latest is worse than best
            health_str = fmt.delta_text(-result.health_delta)
        elif result.health_delta < 0:
            # Latest is better than best
            health_str = fmt.delta_text(abs(result.health_delta))
        else:
            health_str = "0"

        fmt.print(f"    Health: {result.best_health_score} -> {result.latest_health_score} ({health_str})")

        # Issues comparison
        if result.issues_delta > 0:
            if fmt.use_rich:
                issues_str = f"[red]+{result.issues_delta} new[/red]"
            else:
                issues_str = f"+{result.issues_delta} new"
        elif result.issues_delta < 0:
            if fmt.use_rich:
                issues_str = f"[green]{result.issues_delta} fewer[/green]"
            else:
                issues_str = f"{result.issues_delta} fewer"
        else:
            issues_str = "same"

        fmt.print(f"    Issues: {result.best_total_issues} -> {result.latest_total_issues} ({issues_str})")

        # Recommendation
        fmt.print("")
        if result.health_delta > 20:
            if fmt.use_rich:
                fmt.print(f"  [highlight]Recommendation:[/highlight] Consider rolling back to {result.best_als_filename}")
            else:
                fmt.print(f"  Recommendation: Consider rolling back to {result.best_als_filename}")
        elif result.health_delta > 0:
            if fmt.use_rich:
                fmt.print(f"  [highlight]Recommendation:[/highlight] Review changes since {result.best_als_filename}")
            else:
                fmt.print(f"  Recommendation: Review changes since {result.best_als_filename}")
    else:
        fmt.print("")
        if fmt.use_rich:
            fmt.print("  [status.success]Your latest version is your best version![/status.success]")
        else:
            fmt.print("  Your latest version is your best version!")

    # Open folder if requested
    if open_folder:
        fmt.print("")
        folder_path = Path(result.best_als_path).parent
        try:
            import subprocess
            import platform

            system = platform.system()
            if system == 'Windows':
                subprocess.run(['explorer', str(folder_path)], check=False)
            elif system == 'Darwin':  # macOS
                subprocess.run(['open', str(folder_path)], check=False)
            else:  # Linux and others
                subprocess.run(['xdg-open', str(folder_path)], check=False)

            fmt.print(f"Opened folder: {folder_path}")
        except Exception as e:
            fmt.warning(f"Could not open folder: {e}")


# ==================== TEMPLATES COMMANDS ====================


@cli.group()
@click.pass_context
def templates(ctx):
    """Template management commands."""
    pass


@templates.command('list')
@click.pass_context
def templates_list_cmd(ctx):
    """List all available templates.

    Shows all templates in the template library with their track/device counts.

    Example:
        als-doctor templates list
    """
    fmt = ctx.obj.get('formatter', get_formatter())

    template_list, msg = list_templates()

    if not template_list:
        fmt.print("No templates found.")
        fmt.print("")
        fmt.print("Create a template from a project:")
        fmt.print("  als-doctor templates add <file.als> --name <name>")
        return

    # Header
    fmt.header(f"TEMPLATES ({len(template_list)} available)")
    fmt.print("")

    # Create table
    table = fmt.create_table(show_header=True)
    table.add_column("Name", justify="left")
    table.add_column("Tracks", justify="right")
    table.add_column("Devices", justify="right")
    table.add_column("Tags", justify="left")
    table.add_column("Created", justify="left")

    for template in template_list:
        tags_str = ", ".join(template.tags[:3]) if template.tags else "-"
        date_str = template.created_at.strftime("%Y-%m-%d")

        table.add_row(
            template.name[:20] + '..' if len(template.name) > 22 else template.name,
            str(template.total_tracks),
            str(template.total_devices),
            tags_str,
            date_str
        )

    table.render()
    fmt.print("")
    fmt.print("Use 'als-doctor compare-template <file> --template <name>' to compare a project")


@templates.command('add')
@click.argument('file', type=click.Path(exists=True))
@click.option('--name', '-n', required=True, help='Template name')
@click.option('--description', '-d', default='', help='Template description')
@click.option('--tags', '-t', multiple=True, help='Tags for the template (can specify multiple)')
@click.pass_context
def templates_add_cmd(ctx, file: str, name: str, description: str, tags: tuple):
    """Add a new template from an .als file.

    Analyzes the structure of the specified Ableton Live Set and saves it
    as a reusable template for comparison.

    Example:
        als-doctor templates add "D:/Projects/MyTemplate.als" --name "Trance Template"
        als-doctor templates add "MyProject.als" -n "Mixdown" -d "Final mix structure" -t trance -t mixdown
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    file_path = Path(file)

    fmt.print(f"Creating template from: {file_path.name}")
    fmt.print("")

    template, msg = add_template_from_file(
        str(file_path.absolute()),
        name,
        description,
        list(tags) if tags else None
    )

    if template is None:
        fmt.error(msg)
        raise SystemExit(1)

    fmt.success(msg)
    fmt.print("")

    # Show template details
    fmt.print(f"  ID: {template.id}")
    fmt.print(f"  Tracks: {template.total_tracks}")
    fmt.print(f"  Devices: {template.total_devices}")

    if template.device_categories:
        fmt.print("  Device categories:")
        for cat, count in sorted(template.device_categories.items(), key=lambda x: -x[1])[:5]:
            fmt.print(f"    - {cat}: {count}")

    if tags:
        fmt.print(f"  Tags: {', '.join(tags)}")


@templates.command('remove')
@click.argument('name')
@click.option('--force', '-f', is_flag=True, help='Skip confirmation')
@click.pass_context
def templates_remove_cmd(ctx, name: str, force: bool):
    """Remove a template by name or ID.

    Example:
        als-doctor templates remove "Trance Template"
        als-doctor templates remove template_abc123 --force
    """
    fmt = ctx.obj.get('formatter', get_formatter())

    # Get template to show info before removal
    template, msg = get_template_by_name(name)
    if template is None:
        fmt.error(msg)
        raise SystemExit(1)

    if not force:
        fmt.print(f"About to remove template: {template.name}")
        fmt.print(f"  Tracks: {template.total_tracks}, Devices: {template.total_devices}")
        fmt.print("")
        if not click.confirm("Are you sure?"):
            fmt.print("Cancelled.")
            return

    success, msg = remove_template(name)

    if success:
        fmt.success(msg)
    else:
        fmt.error(msg)
        raise SystemExit(1)


@templates.command('show')
@click.argument('name')
@click.pass_context
def templates_show_cmd(ctx, name: str):
    """Show details of a specific template.

    Example:
        als-doctor templates show "Trance Template"
    """
    fmt = ctx.obj.get('formatter', get_formatter())

    template, msg = get_template_by_name(name)
    if template is None:
        fmt.error(msg)
        raise SystemExit(1)

    # Header
    fmt.header(f"TEMPLATE: {template.name}")
    fmt.print("")

    # Basic info
    fmt.print(f"  ID: {template.id}")
    fmt.print(f"  Created: {template.created_at.strftime('%Y-%m-%d %H:%M')}")
    if template.description:
        fmt.print(f"  Description: {template.description}")
    if template.source_file:
        fmt.print(f"  Source: {template.source_file}")
    if template.tags:
        fmt.print(f"  Tags: {', '.join(template.tags)}")
    fmt.print("")

    # Stats
    fmt.print_line("-", 50)
    fmt.print("STRUCTURE")
    fmt.print_line("-", 50)
    fmt.print(f"  Total Tracks: {template.total_tracks}")
    fmt.print(f"  Total Devices: {template.total_devices}")
    fmt.print("")

    # Device categories
    if template.device_categories:
        fmt.print("  Device Categories:")
        for cat, count in sorted(template.device_categories.items(), key=lambda x: -x[1]):
            fmt.print(f"    {cat}: {count}")
        fmt.print("")

    # Track list (first 10)
    if template.tracks:
        fmt.print_line("-", 50)
        fmt.print("TRACKS")
        fmt.print_line("-", 50)

        for i, track in enumerate(template.tracks[:15]):
            track_name = track.name_pattern or f"Track {i+1}"
            device_count = len(track.device_chain)
            device_types = [d.device_type for d in track.device_chain[:3]]
            devices_str = ", ".join(device_types)
            if len(track.device_chain) > 3:
                devices_str += f", +{len(track.device_chain) - 3} more"

            fmt.print(f"  [{track.track_type}] {track_name}: {device_count} device(s)")
            if devices_str:
                fmt.print(f"         {devices_str}")

        if len(template.tracks) > 15:
            fmt.print(f"  ... and {len(template.tracks) - 15} more tracks")


@cli.command('compare-template')
@click.argument('file', type=click.Path(exists=True))
@click.option('--template', '-t', required=True, help='Template name to compare against')
@click.pass_context
def compare_template_cmd(ctx, file: str, template: str):
    """Compare an .als file against a template.

    Analyzes how closely the project structure matches the specified template,
    showing similarity score and recommendations.

    Example:
        als-doctor compare-template "D:/Projects/MySong.als" --template "Trance Template"
        als-doctor compare-template "MySong.als" -t "Mixdown"
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    file_path = Path(file)

    fmt.print(f"Comparing: {file_path.name}")
    fmt.print(f"Template: {template}")
    fmt.print("")

    result, msg = compare_template(str(file_path.absolute()), template)

    if result is None:
        fmt.error(msg)
        raise SystemExit(1)

    # Header with similarity score
    fmt.header(f"TEMPLATE COMPARISON: {result.template_name}")
    fmt.print("")

    # Similarity gauge
    fmt.print(f"Similarity Score: {result.similarity_score}%")
    _display_template_similarity_gauge(result.similarity_score, fmt)
    fmt.print("")

    # Track comparison
    fmt.print_line("-", 50)
    fmt.print("TRACK COMPARISON")
    fmt.print_line("-", 50)

    fmt.print(f"  Matched: {result.matched_tracks}")
    if result.extra_tracks > 0:
        if fmt.use_rich:
            fmt.print(f"  Extra: [yellow]{result.extra_tracks}[/yellow] (not in template)")
        else:
            fmt.print(f"  Extra: {result.extra_tracks} (not in template)")
    if result.missing_tracks > 0:
        if fmt.use_rich:
            fmt.print(f"  Missing: [red]{result.missing_tracks}[/red] (from template)")
        else:
            fmt.print(f"  Missing: {result.missing_tracks} (from template)")
    fmt.print("")

    # Device chain comparison
    if result.matching_device_chains or result.deviating_device_chains:
        fmt.print_line("-", 50)
        fmt.print("DEVICE CHAINS")
        fmt.print_line("-", 50)

        if result.matching_device_chains:
            if fmt.use_rich:
                fmt.print(f"  [green]Matching:[/green] {len(result.matching_device_chains)} track(s)")
            else:
                fmt.print(f"  Matching: {len(result.matching_device_chains)} track(s)")
            for track_name in result.matching_device_chains[:5]:
                fmt.print(f"    OK {track_name}")
            if len(result.matching_device_chains) > 5:
                fmt.print(f"    ... and {len(result.matching_device_chains) - 5} more")

        if result.deviating_device_chains:
            fmt.print("")
            if fmt.use_rich:
                fmt.print(f"  [yellow]Deviating:[/yellow] {len(result.deviating_device_chains)} track(s)")
            else:
                fmt.print(f"  Deviating: {len(result.deviating_device_chains)} track(s)")
            for track_name, deviation in result.deviating_device_chains[:5]:
                fmt.print(f"    ! {track_name}: {deviation}")
            if len(result.deviating_device_chains) > 5:
                fmt.print(f"    ... and {len(result.deviating_device_chains) - 5} more")

        fmt.print("")

    # Category differences
    if result.category_differences:
        fmt.print_line("-", 50)
        fmt.print("DEVICE CATEGORY DIFFERENCES")
        fmt.print_line("-", 50)

        for cat, diff in sorted(result.category_differences.items(), key=lambda x: -abs(x[1])):
            if diff > 0:
                if fmt.use_rich:
                    fmt.print(f"  {cat}: [yellow]+{diff}[/yellow] more than template")
                else:
                    fmt.print(f"  {cat}: +{diff} more than template")
            else:
                if fmt.use_rich:
                    fmt.print(f"  {cat}: [cyan]{diff}[/cyan] fewer than template")
                else:
                    fmt.print(f"  {cat}: {diff} fewer than template")

        fmt.print("")

    # Recommendations
    if result.recommendations:
        fmt.print_line("-", 50)
        if fmt.use_rich:
            fmt.print("[highlight]RECOMMENDATIONS[/highlight]")
        else:
            fmt.print("RECOMMENDATIONS")
        fmt.print_line("-", 50)

        for rec in result.recommendations:
            fmt.print(f"  - {rec}")

        fmt.print("")

    # Summary
    fmt.print_line("=", 50)
    if result.similarity_score >= 80:
        if fmt.use_rich:
            fmt.print("[green]This project closely matches the template![/green]")
        else:
            fmt.print("This project closely matches the template!")
    elif result.similarity_score >= 60:
        fmt.print("This project has moderate similarity to the template.")
    else:
        fmt.print("This project differs significantly from the template.")


def _display_template_similarity_gauge(score: int, fmt: CLIFormatter):
    """Display a visual gauge for template similarity score."""
    bar_width = 20
    filled = int(score / 100 * bar_width)
    empty = bar_width - filled

    if fmt.use_rich:
        if score >= 80:
            color = 'green'
        elif score >= 60:
            color = 'yellow'
        else:
            color = 'red'

        bar = f"[{color}]{'█' * filled}[/{color}]{'░' * empty}"
        fmt.print(f"  [{bar}] {score}%")
    else:
        bar = '=' * filled + '-' * empty
        fmt.print(f"  [{bar}] {score}%")


# ==================== WATCH COMMAND ====================


@cli.command('watch')
@click.argument('folder', type=click.Path(exists=True))
@click.option('--debounce', '-d', type=float, default=5.0,
              help='Seconds to wait after last change before analyzing (default: 5)')
@click.option('--quiet', '-q', is_flag=True,
              help='Suppress non-essential output')
@click.option('--no-save', is_flag=True,
              help='Do not save results to database')
@click.option('--notify', is_flag=True,
              help='Enable desktop notifications for analysis events')
@click.option('--notify-level', type=click.Choice(['all', 'important', 'critical']),
              default='all', help='Filter notifications by importance level')
@click.pass_context
def watch_cmd(ctx, folder: str, debounce: float, quiet: bool, no_save: bool,
              notify: bool, notify_level: str):
    """Watch a folder for .als file changes and auto-analyze.

    Monitors the specified folder (recursively) for changes to Ableton Live Set
    files. When a file is created or modified, it automatically triggers analysis.

    Features:
    - Recursive monitoring of all subfolders
    - Automatically excludes Backup folders
    - Debounces rapid changes (configurable, default 5 seconds)
    - Logs results to data/watch.log
    - Press Ctrl+C to stop watching

    The watcher will automatically save results to the database unless --no-save
    is specified. Make sure to run 'als-doctor db init' first if saving.

    Example:
        als-doctor watch "D:/Ableton Projects"
        als-doctor watch "D:/Ableton Projects" --debounce 10
        als-doctor watch "D:/Ableton Projects" --quiet
        als-doctor watch "D:/Ableton Projects" --no-save
        als-doctor watch "D:/Ableton Projects" --notify
        als-doctor watch "D:/Ableton Projects" --notify --notify-level important
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    save_to_db = not no_save

    # Check database if saving
    if save_to_db:
        database = get_db()
        if not database.is_initialized():
            fmt.error("Database not initialized. Run 'als-doctor db init' first.")
            fmt.print("Or use --no-save to watch without saving to database.")
            raise SystemExit(1)

    # Import watcher module
    try:
        from watcher import FolderWatcher
    except ImportError as e:
        fmt.error(f"Failed to import watcher module: {e}")
        fmt.print("Make sure watchdog is installed: pip install watchdog")
        raise SystemExit(1)

    # Set up notifications if enabled
    notification_manager = None
    if notify:
        try:
            from notifications import (
                configure_notifications, get_notification_manager,
                is_plyer_available
            )
            if not is_plyer_available():
                fmt.warning("plyer library not available for notifications.")
                fmt.print("Install with: pip install plyer")
            else:
                notification_manager = configure_notifications(
                    enabled=True,
                    level=notify_level,
                    rate_limit=30
                )
        except ImportError as e:
            fmt.warning(f"Failed to import notifications module: {e}")

    folder_path = Path(folder).absolute()

    # Display startup info
    fmt.header("ALS DOCTOR - Watch Mode")
    fmt.print("")
    fmt.print(f"  Folder: {folder_path}")
    fmt.print(f"  Debounce: {debounce}s")
    fmt.print(f"  Save to DB: {'Yes' if save_to_db else 'No'}")
    fmt.print(f"  Notifications: {'Yes (' + notify_level + ')' if notify else 'No'}")
    fmt.print("")
    fmt.print("Waiting for .als file changes...")
    fmt.print("(Press Ctrl+C to stop)")
    fmt.print_line("-", 50)

    # Send start notification
    if notification_manager:
        notification_manager.watch_started(str(folder_path))

    # Create and start watcher
    watcher = FolderWatcher(
        folder_path=str(folder_path),
        debounce_seconds=debounce,
        quiet=quiet,
        save_to_db=save_to_db
    )

    try:
        watcher.start(blocking=True)
    except KeyboardInterrupt:
        pass  # Handled by watcher
    except ValueError as e:
        fmt.error(str(e))
        raise SystemExit(1)
    except Exception as e:
        fmt.error(f"Watch error: {e}")
        raise SystemExit(1)

    # Show final stats
    stats = watcher.stats
    if stats and not quiet:
        fmt.print("")
        fmt.print_line("=", 50)
        fmt.header("Watch Session Complete")
        fmt.print(f"  Duration: {stats.uptime_formatted}")
        fmt.print(f"  Files Analyzed: {stats.files_analyzed}")
        fmt.print(f"  Files Failed: {stats.files_failed}")

        if stats.results:
            # Show last few results
            fmt.print("")
            fmt.print("Recent Results:")
            for result in stats.results[-5:]:
                filename = Path(result.file_path).name
                if result.success:
                    grade_str = fmt.grade_text(result.grade)
                    fmt.print(f"  {grade_str} {filename}: {result.health_score}/100")
                else:
                    fmt.print(f"  [!] {filename}: Failed")

        fmt.print("")
        fmt.print(f"Log file: {watcher.log_path}")

    # Send stop notification
    if notification_manager and stats:
        notification_manager.watch_stopped(
            files_analyzed=stats.files_analyzed,
            uptime=stats.uptime_formatted
        )


# ==================== COACH COMMAND ====================


@cli.command('coach')
@click.argument('file', type=click.Path(exists=True))
@click.option('--auto-check', '-a', type=int, default=None,
              help='Auto re-analyze every N seconds (default: disabled)')
@click.option('--quiet', '-q', is_flag=True,
              help='Suppress non-essential output')
@click.pass_context
def coach_cmd(ctx, file: str, auto_check: Optional[int], quiet: bool):
    """Start a guided coaching session to fix issues one by one.

    Coach mode provides an interactive, step-by-step workflow for improving
    your Ableton project's health. It shows one issue at a time with specific
    fix instructions, waits for you to fix it, then re-analyzes to verify.

    Controls:
      [Enter] - Mark issue as fixed (triggers re-analysis)
      [S]     - Skip issue and move to next
      [Q]     - Quit coaching session

    Features:
    - Shows one issue at a time with clear fix instructions
    - Re-analyzes after each confirmed fix to verify improvement
    - Tracks session progress (fixed, skipped counts)
    - Celebrates health improvements
    - Shows detailed session summary at the end

    Use --auto-check N to automatically re-analyze every N seconds
    while you're working on a fix.

    Example:
        als-doctor coach "D:/Projects/MySong.als"
        als-doctor coach "D:/Projects/MySong.als" --auto-check 30
        als-doctor coach "D:/Projects/MySong.als" --quiet
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    file_path = Path(file)

    if file_path.suffix.lower() != '.als':
        fmt.error("File must be an Ableton Live Set (.als)")
        raise SystemExit(1)

    # Import coach module
    try:
        from coach import coach_mode
    except ImportError as e:
        fmt.error(f"Failed to import coach module: {e}")
        raise SystemExit(1)

    # Run coaching session
    try:
        stats = coach_mode(
            file_path=str(file_path.absolute()),
            analyzer_fn=_analyze_als_file,
            formatter=fmt,
            auto_check_interval=auto_check,
            quiet=quiet
        )

        # Exit with appropriate code based on session results
        if stats.issues_fixed > 0 or stats.health_delta > 0:
            raise SystemExit(0)  # Success, improvements made
        elif stats.issues_skipped > 0 and stats.issues_fixed == 0:
            raise SystemExit(0)  # User skipped all, but session completed
        else:
            raise SystemExit(0)  # Session completed normally

    except KeyboardInterrupt:
        fmt.print("")
        fmt.print("Coaching session interrupted.")
        raise SystemExit(130)  # Standard exit code for Ctrl+C


# ==================== SCHEDULE COMMANDS ====================


@cli.group()
@click.pass_context
def schedule(ctx):
    """Schedule management commands for automated batch scanning."""
    pass


@schedule.command('add')
@click.argument('folder', type=click.Path(exists=True))
@click.option('--daily', 'frequency', flag_value='daily', default=True,
              help='Run daily (default)')
@click.option('--weekly', 'frequency', flag_value='weekly',
              help='Run weekly')
@click.option('--hourly', 'frequency', flag_value='hourly',
              help='Run hourly')
@click.option('--name', '-n', type=str, default=None,
              help='Schedule name (defaults to folder name)')
@click.option('--time', '-t', 'run_time', type=str, default=None,
              help='Time to run (HH:MM format, e.g., "03:00")')
@click.option('--day', '-d', type=int, default=None,
              help='Day of week for weekly (0=Monday, 6=Sunday)')
@click.pass_context
def schedule_add_cmd(ctx, folder: str, frequency: str, name: Optional[str],
                     run_time: Optional[str], day: Optional[int]):
    """Add a scheduled batch scan.

    Creates a new schedule to automatically scan a folder for .als files
    at regular intervals.

    Examples:
        als-doctor schedule add "D:/Ableton Projects" --daily
        als-doctor schedule add "D:/Projects" --weekly --day 0 --time 09:00
        als-doctor schedule add "D:/Projects" --hourly --name "My Projects"
    """
    fmt = ctx.obj.get('formatter', get_formatter())

    try:
        from scheduler import add_schedule
    except ImportError as e:
        fmt.error(f"Failed to import scheduler module: {e}")
        raise SystemExit(1)

    schedule, msg = add_schedule(
        folder_path=folder,
        frequency=frequency,
        name=name,
        run_at_time=run_time,
        run_on_day=day
    )

    if schedule is None:
        fmt.error(msg)
        raise SystemExit(1)

    fmt.success(msg)
    fmt.print("")
    fmt.print(f"  ID: {schedule.id}")
    fmt.print(f"  Folder: {schedule.folder_path}")
    fmt.print(f"  Frequency: {schedule.frequency}")
    if schedule.run_at_time:
        fmt.print(f"  Run at: {schedule.run_at_time}")
    if schedule.run_on_day is not None:
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        fmt.print(f"  Run on: {days[schedule.run_on_day]}")
    fmt.print("")
    fmt.print("To run scheduled scans:")
    fmt.print("  - Manually: als-doctor schedule run <id>")
    fmt.print("  - Via cron: als-doctor schedule install <id>")
    fmt.print("  - Or run: python run_scheduled_scans.py")


@schedule.command('list')
@click.pass_context
def schedule_list_cmd(ctx):
    """List all scheduled scans.

    Shows all configured schedules with their status and last run information.

    Example:
        als-doctor schedule list
    """
    fmt = ctx.obj.get('formatter', get_formatter())

    try:
        from scheduler import list_schedules
    except ImportError as e:
        fmt.error(f"Failed to import scheduler module: {e}")
        raise SystemExit(1)

    schedules, msg = list_schedules()

    if not schedules:
        fmt.print("No schedules configured.")
        fmt.print("")
        fmt.print("Create a schedule:")
        fmt.print("  als-doctor schedule add <folder> --daily")
        return

    # Header
    fmt.header(f"SCHEDULES ({len(schedules)} configured)")
    fmt.print("")

    # Create table
    table = fmt.create_table(show_header=True)
    table.add_column("ID", justify="left")
    table.add_column("Name", justify="left")
    table.add_column("Frequency", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Last Run", justify="left")

    for sched in schedules:
        # Status
        if sched.enabled:
            if fmt.use_rich:
                status = "[green]enabled[/green]"
            else:
                status = "enabled"
        else:
            if fmt.use_rich:
                status = "[dim]disabled[/dim]"
            else:
                status = "disabled"

        # Last run
        if sched.last_run_at:
            last_run = sched.last_run_at[:16].replace('T', ' ')
            if sched.last_run_status == 'success':
                last_run += f" ({sched.last_run_files_scanned} files)"
            elif sched.last_run_status == 'failed':
                if fmt.use_rich:
                    last_run = f"[red]{last_run} (failed)[/red]"
                else:
                    last_run = f"{last_run} (failed)"
        else:
            last_run = "never"

        # Truncate name
        name = sched.name[:18] + '..' if len(sched.name) > 20 else sched.name

        table.add_row(
            sched.id[-8:],  # Show last 8 chars of ID
            name,
            sched.frequency,
            status,
            last_run
        )

    table.render()
    fmt.print("")
    fmt.print(f"Run all due: als-doctor schedule run-due")
    fmt.print(f"Run specific: als-doctor schedule run <id>")


@schedule.command('remove')
@click.argument('schedule_id')
@click.option('--force', '-f', is_flag=True, help='Skip confirmation')
@click.pass_context
def schedule_remove_cmd(ctx, schedule_id: str, force: bool):
    """Remove a scheduled scan.

    Removes a schedule by its ID or name. Use 'als-doctor schedule list'
    to see available schedules.

    Example:
        als-doctor schedule remove schedule_abc12345
        als-doctor schedule remove "My Projects" --force
    """
    fmt = ctx.obj.get('formatter', get_formatter())

    try:
        from scheduler import get_schedule_by_id, remove_schedule
    except ImportError as e:
        fmt.error(f"Failed to import scheduler module: {e}")
        raise SystemExit(1)

    # Get schedule to show info before removal
    sched, msg = get_schedule_by_id(schedule_id)
    if sched is None:
        fmt.error(msg)
        raise SystemExit(1)

    if not force:
        fmt.print(f"About to remove schedule: {sched.name}")
        fmt.print(f"  Folder: {sched.folder_path}")
        fmt.print(f"  Frequency: {sched.frequency}")
        fmt.print("")
        if not click.confirm("Are you sure?"):
            fmt.print("Cancelled.")
            return

    success, msg = remove_schedule(schedule_id)

    if success:
        fmt.success(msg)
    else:
        fmt.error(msg)
        raise SystemExit(1)


@schedule.command('run')
@click.argument('schedule_id')
@click.option('--quiet', '-q', is_flag=True, help='Suppress output')
@click.option('--notify', is_flag=True,
              help='Send desktop notification when complete')
@click.option('--notify-level', type=click.Choice(['all', 'important', 'critical']),
              default='all', help='Filter notifications by importance level')
@click.pass_context
def schedule_run_cmd(ctx, schedule_id: str, quiet: bool, notify: bool, notify_level: str):
    """Run a scheduled scan immediately.

    Executes a specific schedule right now, regardless of whether it's due.
    Results are saved to the database.

    Example:
        als-doctor schedule run schedule_abc12345
        als-doctor schedule run "My Projects" --quiet
        als-doctor schedule run schedule_abc12345 --notify
    """
    fmt = ctx.obj.get('formatter', get_formatter())

    try:
        from scheduler import run_schedule, get_schedule_by_id
    except ImportError as e:
        fmt.error(f"Failed to import scheduler module: {e}")
        raise SystemExit(1)

    # Set up notifications if enabled
    notification_manager = None
    if notify:
        try:
            from notifications import configure_notifications, is_plyer_available
            if is_plyer_available():
                notification_manager = configure_notifications(
                    enabled=True,
                    level=notify_level,
                    rate_limit=30
                )
        except ImportError:
            pass  # Notifications not available

    # Check database
    database = get_db()
    if not database.is_initialized():
        fmt.error("Database not initialized. Run 'als-doctor db init' first.")
        raise SystemExit(1)

    # Get schedule info
    sched, msg = get_schedule_by_id(schedule_id)
    if sched is None:
        fmt.error(msg)
        raise SystemExit(1)

    if not quiet:
        fmt.print(f"Running schedule: {sched.name}")
        fmt.print(f"  Folder: {sched.folder_path}")
        fmt.print("")

    result, msg = run_schedule(schedule_id, quiet=quiet)

    if result.success:
        fmt.success(f"Completed: {result.summary}")
        # Send notification
        if notification_manager:
            notification_manager.schedule_complete(
                schedule_name=sched.name,
                files_scanned=result.files_scanned if hasattr(result, 'files_scanned') else 0,
                success=True
            )
    else:
        fmt.error(f"Failed: {result.error_message}")
        # Send failure notification
        if notification_manager:
            notification_manager.schedule_complete(
                schedule_name=sched.name,
                files_scanned=0,
                success=False,
                error_message=result.error_message
            )
        raise SystemExit(1)


@schedule.command('run-due')
@click.option('--quiet', '-q', is_flag=True, help='Suppress output')
@click.option('--notify', is_flag=True,
              help='Send desktop notification when complete')
@click.option('--notify-level', type=click.Choice(['all', 'important', 'critical']),
              default='all', help='Filter notifications by importance level')
@click.pass_context
def schedule_run_due_cmd(ctx, quiet: bool, notify: bool, notify_level: str):
    """Run all schedules that are due.

    Checks all enabled schedules and runs those that are overdue
    based on their frequency. This is typically called by a cron job
    or task scheduler.

    Example:
        als-doctor schedule run-due
        als-doctor schedule run-due --quiet
        als-doctor schedule run-due --notify
    """
    fmt = ctx.obj.get('formatter', get_formatter())

    try:
        from scheduler import check_due_schedules, run_due_schedules
    except ImportError as e:
        fmt.error(f"Failed to import scheduler module: {e}")
        raise SystemExit(1)

    # Set up notifications if enabled
    notification_manager = None
    if notify:
        try:
            from notifications import configure_notifications, is_plyer_available
            if is_plyer_available():
                notification_manager = configure_notifications(
                    enabled=True,
                    level=notify_level,
                    rate_limit=30
                )
        except ImportError:
            pass  # Notifications not available

    # Check database
    database = get_db()
    if not database.is_initialized():
        fmt.error("Database not initialized. Run 'als-doctor db init' first.")
        raise SystemExit(1)

    due_schedules = check_due_schedules()

    if not due_schedules:
        if not quiet:
            fmt.print("No schedules due to run.")
        return

    if not quiet:
        fmt.print(f"Running {len(due_schedules)} due schedule(s)...")
        fmt.print("")

    results = run_due_schedules(quiet=quiet)

    success_count = sum(1 for r in results if r.success)
    fail_count = sum(1 for r in results if not r.success)

    if not quiet:
        fmt.print("")
        if fail_count == 0:
            fmt.success(f"Completed: {success_count} schedule(s) run successfully")
        else:
            fmt.warning(f"Completed: {success_count} succeeded, {fail_count} failed")

    # Send summary notification
    if notification_manager:
        total_files = sum(getattr(r, 'files_scanned', 0) for r in results)
        notification_manager.scan_complete(
            folder_name=f"{len(due_schedules)} schedule(s)",
            files_scanned=total_files,
            files_failed=fail_count
        )

    if fail_count > 0:
        raise SystemExit(1)


@schedule.command('enable')
@click.argument('schedule_id')
@click.pass_context
def schedule_enable_cmd(ctx, schedule_id: str):
    """Enable a disabled schedule.

    Example:
        als-doctor schedule enable schedule_abc12345
    """
    fmt = ctx.obj.get('formatter', get_formatter())

    try:
        from scheduler import enable_schedule
    except ImportError as e:
        fmt.error(f"Failed to import scheduler module: {e}")
        raise SystemExit(1)

    success, msg = enable_schedule(schedule_id, enabled=True)

    if success:
        fmt.success(msg)
    else:
        fmt.error(msg)
        raise SystemExit(1)


@schedule.command('disable')
@click.argument('schedule_id')
@click.pass_context
def schedule_disable_cmd(ctx, schedule_id: str):
    """Disable a schedule (without removing it).

    Example:
        als-doctor schedule disable schedule_abc12345
    """
    fmt = ctx.obj.get('formatter', get_formatter())

    try:
        from scheduler import enable_schedule
    except ImportError as e:
        fmt.error(f"Failed to import scheduler module: {e}")
        raise SystemExit(1)

    success, msg = enable_schedule(schedule_id, enabled=False)

    if success:
        fmt.success(msg)
    else:
        fmt.error(msg)
        raise SystemExit(1)


@schedule.command('install')
@click.argument('schedule_id')
@click.pass_context
def schedule_install_cmd(ctx, schedule_id: str):
    """Install a cron job for a schedule (Linux/macOS only).

    Creates a cron entry that will automatically run the schedule
    at its configured frequency.

    Example:
        als-doctor schedule install schedule_abc12345
    """
    fmt = ctx.obj.get('formatter', get_formatter())

    try:
        from scheduler import get_schedule_by_id, install_cron_job, get_cron_expression
        import platform
    except ImportError as e:
        fmt.error(f"Failed to import scheduler module: {e}")
        raise SystemExit(1)

    if platform.system() == 'Windows':
        fmt.error("Cron is not available on Windows.")
        fmt.print("")
        fmt.print("For Windows, use Task Scheduler instead:")
        fmt.print("  1. Open Task Scheduler")
        fmt.print("  2. Create a new task")
        fmt.print("  3. Set trigger to your preferred schedule")
        fmt.print("  4. Set action to run:")
        fmt.print(f'     python "{Path(__file__).parent / "run_scheduled_scans.py"}"')
        raise SystemExit(1)

    # Get schedule
    sched, msg = get_schedule_by_id(schedule_id)
    if sched is None:
        fmt.error(msg)
        raise SystemExit(1)

    # Show what will be installed
    cron_expr = get_cron_expression(sched)
    fmt.print(f"Installing cron job for: {sched.name}")
    fmt.print(f"  Cron expression: {cron_expr}")
    fmt.print("")

    success, msg = install_cron_job(sched)

    if success:
        fmt.success(msg)
        fmt.print("")
        fmt.print("View your crontab with: crontab -l")
    else:
        fmt.error(msg)
        raise SystemExit(1)


@schedule.command('uninstall')
@click.argument('schedule_id')
@click.pass_context
def schedule_uninstall_cmd(ctx, schedule_id: str):
    """Remove a cron job for a schedule (Linux/macOS only).

    Example:
        als-doctor schedule uninstall schedule_abc12345
    """
    fmt = ctx.obj.get('formatter', get_formatter())

    try:
        from scheduler import get_schedule_by_id, uninstall_cron_job
        import platform
    except ImportError as e:
        fmt.error(f"Failed to import scheduler module: {e}")
        raise SystemExit(1)

    if platform.system() == 'Windows':
        fmt.error("Cron is not available on Windows. Use Task Scheduler to manage scheduled tasks.")
        raise SystemExit(1)

    # Get schedule
    sched, msg = get_schedule_by_id(schedule_id)
    if sched is None:
        fmt.error(msg)
        raise SystemExit(1)

    success, msg = uninstall_cron_job(sched)

    if success:
        fmt.success(msg)
    else:
        fmt.error(msg)
        raise SystemExit(1)


@cli.command('preflight')
@click.argument('file', type=click.Path(exists=True))
@click.option('--strict', is_flag=True, help='Require Grade A (80+ health score)')
@click.option('--min-score', type=int, default=60, help='Minimum health score (default: 60)')
@click.pass_context
def preflight_cmd(ctx, file: str, strict: bool, min_score: int):
    """Run pre-export checklist on an .als file.

    Verifies that a project is ready for final export by checking:
    - Health score meets threshold
    - No critical issues
    - No solo'd tracks
    - Master track not muted
    - Limiter ceiling at safe level (<= -0.3dB)
    - Project clutter level

    Returns exit code 0 if ready (GO), 1 if not ready (NO-GO).

    Use --strict to require Grade A (80+ score).
    Use --min-score to set a custom minimum threshold.

    Example:
        als-doctor preflight "D:/Projects/MySong.als"
        als-doctor preflight "D:/Projects/MySong.als" --strict
        als-doctor preflight "D:/Projects/MySong.als" --min-score 75
    """
    fmt = ctx.obj.get('formatter', get_formatter())
    file_path = Path(file)

    if file_path.suffix.lower() != '.als':
        fmt.error("File must be an Ableton Live Set (.als)")
        raise SystemExit(1)

    fmt.print(f"Running preflight check: {file_path.name}")
    fmt.print("")

    # Import preflight module
    try:
        from preflight import preflight_check, PreflightResult, CheckStatus
    except ImportError as e:
        fmt.error(f"Failed to import preflight module: {e}")
        raise SystemExit(1)

    # Run preflight check
    result, message = preflight_check(
        str(file_path),
        min_score=min_score,
        strict=strict
    )

    if result is None:
        fmt.error(message)
        raise SystemExit(1)

    # Display results
    _display_preflight_result(result, fmt)

    # Return appropriate exit code
    if result.is_ready:
        raise SystemExit(0)
    else:
        raise SystemExit(1)


def _display_preflight_result(result: 'PreflightResult', fmt: 'CLIFormatter'):
    """Display preflight check results."""
    from preflight import CheckStatus

    # Verdict header
    if result.is_ready:
        fmt.print_line("=", 50)
        if fmt.use_rich:
            fmt.print("[bold green]VERDICT: GO[/bold green] - Ready to export!")
        else:
            fmt.print("VERDICT: GO - Ready to export!")
        fmt.print_line("=", 50)
    else:
        fmt.print_line("=", 50)
        if fmt.use_rich:
            fmt.print("[bold red]VERDICT: NO-GO[/bold red] - Issues must be resolved")
        else:
            fmt.print("VERDICT: NO-GO - Issues must be resolved")
        fmt.print_line("=", 50)

    fmt.print("")

    # Summary
    grade_str = fmt.grade_text(result.grade)
    fmt.print(f"Health Score: {result.health_score}/100 {grade_str}")

    mode_str = "Strict (Grade A required)" if result.strict_mode else f"Normal (min: {result.min_score})"
    fmt.print(f"Mode: {mode_str}")
    fmt.print("")

    # Statistics
    fmt.print(f"Checks: {result.total_checks} total | {result.passed_count} passed | {result.failed_count} blocked | {result.warning_count} warnings")
    fmt.print("")

    # Blockers (must fix)
    if result.blockers:
        fmt.print_line("-", 50)
        if fmt.use_rich:
            fmt.print("[bold red]BLOCKERS (must fix before export):[/bold red]")
        else:
            fmt.print("BLOCKERS (must fix before export):")
        fmt.print("")

        for check in result.blockers:
            if fmt.use_rich:
                fmt.print(f"  [red]X[/red] {check.name}")
                fmt.print(f"    {check.details}")
            else:
                fmt.print(f"  X {check.name}")
                fmt.print(f"    {check.details}")
        fmt.print("")

    # Warnings (optional cleanup)
    if result.warnings:
        fmt.print_line("-", 50)
        if fmt.use_rich:
            fmt.print("[bold yellow]WARNINGS (optional cleanup):[/bold yellow]")
        else:
            fmt.print("WARNINGS (optional cleanup):")
        fmt.print("")

        for check in result.warnings:
            if fmt.use_rich:
                fmt.print(f"  [yellow]![/yellow] {check.name}")
                fmt.print(f"    {check.details}")
            else:
                fmt.print(f"  ! {check.name}")
                fmt.print(f"    {check.details}")
        fmt.print("")

    # Passed checks
    if result.passed:
        fmt.print_line("-", 50)
        if fmt.use_rich:
            fmt.print("[bold green]PASSED:[/bold green]")
        else:
            fmt.print("PASSED:")
        fmt.print("")

        for check in result.passed:
            if fmt.use_rich:
                fmt.print(f"  [green]+[/green] {check.name}")
            else:
                fmt.print(f"  + {check.name}")
        fmt.print("")

    # Final message
    fmt.print_line("=", 50)
    if result.is_ready:
        fmt.success("Project is ready for export!")
    else:
        fmt.error(f"Fix {result.failed_count} blocker(s) before exporting.")


# ============================================================================
# Dashboard Command
# ============================================================================

@cli.command('dashboard')
@click.option(
    '--port', '-p',
    type=int,
    default=5000,
    help='Port to run the dashboard on (default: 5000)'
)
@click.option(
    '--no-browser',
    is_flag=True,
    default=False,
    help='Don\'t automatically open browser'
)
@click.option(
    '--host',
    type=str,
    default='127.0.0.1',
    help='Host to bind to (default: 127.0.0.1)'
)
@click.option(
    '--debug',
    is_flag=True,
    default=False,
    help='Enable debug mode'
)
@click.option(
    '--refresh', '-r',
    type=int,
    default=30,
    help='Auto-refresh interval in seconds (default: 30)'
)
@click.option(
    '--no-refresh',
    is_flag=True,
    default=False,
    help='Disable auto-refresh'
)
@click.pass_context
def dashboard_cmd(ctx, port: int, no_browser: bool, host: str, debug: bool,
                  refresh: int, no_refresh: bool):
    """Start the local web dashboard.

    Opens an interactive web dashboard in your browser for browsing
    and managing your project analysis data.

    The dashboard includes:
      - Health overview with grade distribution
      - Sortable/filterable project list
      - Project detail pages with timeline charts
      - Pattern insights from your history

    Example:
        als-doctor dashboard
        als-doctor dashboard --port 8080
        als-doctor dashboard --no-browser
        als-doctor dashboard --refresh 60
    """
    fmt = ctx.obj.get('formatter', get_formatter())

    # Check if database is initialized
    database = get_db()
    if not database.is_initialized():
        fmt.error("Database not initialized. Run 'als-doctor db init' first.")
        raise SystemExit(1)

    # Import dashboard module
    try:
        from dashboard import run_dashboard, FLASK_AVAILABLE

        if not FLASK_AVAILABLE:
            fmt.error("Flask is not installed. Install with: pip install flask")
            raise SystemExit(1)

    except ImportError as e:
        fmt.error(f"Failed to import dashboard module: {e}")
        fmt.error("Install Flask with: pip install flask")
        raise SystemExit(1)

    # Show startup info
    url = f"http://{host}:{port}"
    fmt.header("ALS DOCTOR DASHBOARD")
    fmt.print("")
    fmt.print(f"Starting dashboard at: {url}")
    fmt.print("")

    if no_browser:
        fmt.print("Open the URL in your browser to access the dashboard.")
    else:
        fmt.print("Browser will open automatically...")

    fmt.print("")
    fmt.print("Press Ctrl+C to stop the server.")
    fmt.print("")

    # Run the dashboard
    try:
        run_dashboard(
            port=port,
            host=host,
            debug=debug,
            no_browser=no_browser,
            auto_refresh=not no_refresh,
            refresh_interval=refresh
        )
    except KeyboardInterrupt:
        fmt.print("")
        fmt.print("Dashboard stopped.")
    except OSError as e:
        if "Address already in use" in str(e):
            fmt.error(f"Port {port} is already in use. Try a different port with --port")
        else:
            fmt.error(f"Failed to start dashboard: {e}")
        raise SystemExit(1)


if __name__ == '__main__':
    cli()
