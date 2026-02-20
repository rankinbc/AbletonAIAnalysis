#!/usr/bin/env python
"""
Batch Analyze All Ableton Projects

Scans all .als files in the Ableton projects folder, analyzes them,
identifies the top 3 versions per project, and stores results in the database.

Usage:
    python batch_analyze_all.py [--ableton-path PATH] [--top N] [--verbose]
"""

import os
import sys
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from batch_scanner import BatchScanner, SongSummary, BatchScanResult
from database import (
    Database, ScanResult, ScanResultIssue, persist_scan_result, db_init, get_db
)

# Default paths
DEFAULT_ABLETON_PATH = r"D:\OneDrive\Music\Projects\Ableton\Ableton Projects"
DEFAULT_TOP_N = 3


def extract_project_name(als_path: str) -> str:
    """
    Extract the project name from an .als file path.

    The project is identified by the parent folder name.
    E.g., "D:/...Ableton Projects/22 Project/22_5.als" -> "22 Project"
    """
    return Path(als_path).parent.name


def group_by_project(songs: List[SongSummary]) -> Dict[str, List[SongSummary]]:
    """Group song summaries by their project folder."""
    groups = defaultdict(list)
    for song in songs:
        project_name = extract_project_name(song.file_path)
        groups[project_name].append(song)
    return dict(groups)


def get_top_versions(songs: List[SongSummary], top_n: int = 3) -> List[SongSummary]:
    """
    Get the top N versions by health score.

    Excludes songs with errors.
    """
    valid_songs = [s for s in songs if s.error is None]
    sorted_songs = sorted(valid_songs, key=lambda s: s.health_score, reverse=True)
    return sorted_songs[:top_n]


def song_summary_to_scan_result(song: SongSummary) -> ScanResult:
    """Convert a SongSummary to a ScanResult for database persistence."""
    return ScanResult(
        als_path=song.file_path,
        health_score=song.health_score,
        grade=song.workability_grade,
        total_issues=song.total_issues,
        critical_issues=song.critical_issues,
        warning_issues=song.warning_issues,
        total_devices=song.total_devices,
        disabled_devices=song.disabled_devices,
        clutter_percentage=song.clutter_percentage,
        issues=[]  # Could be populated if we had detailed issues
    )


def analyze_all_projects(
    ableton_path: str = DEFAULT_ABLETON_PATH,
    top_n: int = DEFAULT_TOP_N,
    verbose: bool = False
) -> Tuple[Dict[str, List[SongSummary]], BatchScanResult]:
    """
    Analyze all Ableton projects and identify top versions.

    Args:
        ableton_path: Path to Ableton projects folder
        top_n: Number of top versions to identify per project
        verbose: Print verbose output

    Returns:
        Tuple of (top_versions_by_project, full_scan_result)
    """
    print(f"\n{'='*70}")
    print(f"BATCH ABLETON PROJECT ANALYSIS")
    print(f"{'='*70}")
    print(f"Scanning: {ableton_path}")
    print(f"Top versions per project: {top_n}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")

    # Initialize scanner
    scanner = BatchScanner(verbose=verbose)

    # Scan all .als files
    print("Scanning for .als files...")
    result = scanner.scan_directory(ableton_path, recursive=True, max_workers=4)

    print(f"\nFound {result.total_scanned} .als files")
    print(f"  Successful: {result.successful}")
    print(f"  Failed: {result.failed}")

    # Group by project
    print("\nGrouping by project...")
    projects = group_by_project(result.songs)
    print(f"Found {len(projects)} unique projects")

    # Get top versions for each project
    print(f"\nIdentifying top {top_n} versions per project...")
    top_versions = {}
    for project_name, songs in projects.items():
        top = get_top_versions(songs, top_n)
        if top:
            top_versions[project_name] = top

    return top_versions, result


def store_in_database(
    top_versions: Dict[str, List[SongSummary]],
    verbose: bool = False
) -> Tuple[int, int]:
    """
    Store top versions in the database.

    Args:
        top_versions: Dict of project_name -> list of top SongSummary
        verbose: Print verbose output

    Returns:
        Tuple of (success_count, failure_count)
    """
    # Initialize database
    print("\nInitializing database...")
    success, msg = db_init()
    if not success:
        print(f"ERROR: {msg}")
        return 0, 0
    print(f"  {msg.split(chr(10))[0]}")  # First line only

    # Store each top version
    print("\nStoring top versions in database...")
    success_count = 0
    failure_count = 0

    for project_name, songs in top_versions.items():
        for song in songs:
            scan_result = song_summary_to_scan_result(song)
            ok, msg, version_id = persist_scan_result(scan_result)

            if ok:
                success_count += 1
                if verbose:
                    print(f"  [OK] {song.file_name} (score: {song.health_score})")
            else:
                failure_count += 1
                if verbose:
                    print(f"  [FAIL] {song.file_name}: {msg}")

    return success_count, failure_count


def generate_report(
    top_versions: Dict[str, List[SongSummary]],
    full_result: BatchScanResult
) -> str:
    """Generate a summary report."""
    lines = []

    lines.append("\n" + "="*70)
    lines.append("TOP VERSIONS BY PROJECT")
    lines.append("="*70 + "\n")

    # Sort projects by best health score
    sorted_projects = sorted(
        top_versions.items(),
        key=lambda x: x[1][0].health_score if x[1] else 0,
        reverse=True
    )

    for project_name, songs in sorted_projects:
        lines.append(f"\n{project_name}")
        lines.append("-" * len(project_name))

        for i, song in enumerate(songs, 1):
            lines.append(
                f"  #{i}: [{song.workability_grade}] {song.file_name} "
                f"- Score: {song.health_score}/100, "
                f"Issues: {song.total_issues}, "
                f"Devices: {song.total_devices}"
            )

    # Summary stats
    lines.append("\n" + "="*70)
    lines.append("SUMMARY")
    lines.append("="*70)

    total_top = sum(len(songs) for songs in top_versions.values())
    lines.append(f"Total projects: {len(top_versions)}")
    lines.append(f"Total top versions stored: {total_top}")

    # Grade distribution of top versions
    grades = defaultdict(int)
    for songs in top_versions.values():
        for song in songs:
            grades[song.workability_grade] += 1

    lines.append("\nGrade distribution of top versions:")
    for grade in ["A", "B", "C", "D", "F"]:
        count = grades.get(grade, 0)
        bar = "#" * count
        lines.append(f"  {grade}: {count:3d} {bar}")

    # Best overall projects
    lines.append("\nBest overall projects (by top version score):")
    for project_name, songs in sorted_projects[:10]:
        if songs:
            lines.append(f"  [{songs[0].workability_grade}] {project_name}: {songs[0].health_score}/100")

    lines.append("\n" + "="*70)

    return "\n".join(lines)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze all Ableton projects and store top versions in database"
    )
    parser.add_argument(
        "--ableton-path", "-p",
        default=DEFAULT_ABLETON_PATH,
        help=f"Path to Ableton projects folder (default: {DEFAULT_ABLETON_PATH})"
    )
    parser.add_argument(
        "--top", "-t",
        type=int,
        default=DEFAULT_TOP_N,
        help=f"Number of top versions per project (default: {DEFAULT_TOP_N})"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze without storing in database"
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Only generate report, don't store"
    )

    args = parser.parse_args()

    # Run analysis
    top_versions, full_result = analyze_all_projects(
        ableton_path=args.ableton_path,
        top_n=args.top,
        verbose=args.verbose
    )

    # Generate and print report
    report = generate_report(top_versions, full_result)
    print(report)

    # Store in database unless dry run
    if not args.dry_run and not args.report_only:
        success, failure = store_in_database(top_versions, verbose=args.verbose)
        print(f"\nDatabase storage complete:")
        print(f"  Stored: {success}")
        print(f"  Failed: {failure}")

        # Show final stats
        db = get_db()
        stats = db.get_stats()
        print(f"\nDatabase now contains:")
        print(f"  Projects: {stats['projects']}")
        print(f"  Versions: {stats['versions']}")
        print(f"  Issues: {stats['issues']}")
    else:
        print("\n[DRY RUN] No data stored in database")

    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
