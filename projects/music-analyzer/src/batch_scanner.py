"""
Batch Scanner

Scans multiple Ableton Live Set (.als) files and ranks them by "workability".
Helps you decide which songs to focus on based on project health.

Answers: "Which of my songs should I keep working on?"
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from device_chain_analyzer import (
    ProjectDeviceAnalysis, DeviceChainAnalyzer, analyze_als_devices
)
from effect_chain_doctor import (
    ProjectDiagnosis, diagnose_project, EffectChainDoctor
)


@dataclass
class SongSummary:
    """Summary of a single song's analysis."""
    file_path: str
    file_name: str
    health_score: int
    total_issues: int
    critical_issues: int
    warning_issues: int
    total_devices: int
    disabled_devices: int
    clutter_percentage: float
    tempo: float
    track_count: int

    # Recommendations
    workability_grade: str  # A, B, C, D, F
    recommendation: str

    # Error handling
    error: Optional[str] = None


@dataclass
class BatchScanResult:
    """Results from scanning multiple projects."""
    scan_path: str
    total_scanned: int
    successful: int
    failed: int

    songs: List[SongSummary] = field(default_factory=list)

    # Rankings
    best_songs: List[str] = field(default_factory=list)  # Top picks
    needs_cleanup: List[str] = field(default_factory=list)  # Cluttered but salvageable
    consider_abandoning: List[str] = field(default_factory=list)  # Very low health


class BatchScanner:
    """
    Scans multiple Ableton projects and ranks them.

    Helps producers prioritize which songs to work on.
    """

    # Grade thresholds
    GRADES = {
        "A": (80, 100),  # Great shape, keep refining
        "B": (60, 79),   # Good, some cleanup needed
        "C": (40, 59),   # Needs work, but salvageable
        "D": (20, 39),   # Significant issues
        "F": (0, 19),    # Major problems, consider starting fresh
    }

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.analyzer = DeviceChainAnalyzer(verbose=verbose)
        self.doctor = EffectChainDoctor(verbose=verbose)

    def scan_directory(self, directory: str, recursive: bool = True,
                      max_workers: int = 4) -> BatchScanResult:
        """
        Scan all .als files in a directory.

        Args:
            directory: Path to scan
            recursive: Whether to scan subdirectories
            max_workers: Parallel workers for scanning

        Returns:
            BatchScanResult with all song summaries
        """
        path = Path(directory)
        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        # Find all .als files
        if recursive:
            als_files = list(path.rglob("*.als"))
        else:
            als_files = list(path.glob("*.als"))

        if self.verbose:
            print(f"Found {len(als_files)} .als files to scan...")

        result = BatchScanResult(
            scan_path=str(path.absolute()),
            total_scanned=len(als_files),
            successful=0,
            failed=0
        )

        # Scan files (parallel for speed)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._scan_file, str(f)): f
                for f in als_files
            }

            for future in as_completed(futures):
                als_file = futures[future]
                try:
                    summary = future.result()
                    result.songs.append(summary)
                    if summary.error:
                        result.failed += 1
                    else:
                        result.successful += 1
                except Exception as e:
                    result.failed += 1
                    result.songs.append(SongSummary(
                        file_path=str(als_file),
                        file_name=als_file.name,
                        health_score=0,
                        total_issues=0,
                        critical_issues=0,
                        warning_issues=0,
                        total_devices=0,
                        disabled_devices=0,
                        clutter_percentage=0,
                        tempo=0,
                        track_count=0,
                        workability_grade="?",
                        recommendation="Could not scan",
                        error=str(e)
                    ))

        # Sort by health score (best first)
        result.songs.sort(key=lambda s: s.health_score, reverse=True)

        # Categorize songs
        self._categorize_songs(result)

        return result

    def scan_files(self, file_paths: List[str]) -> BatchScanResult:
        """
        Scan specific .als files.

        Args:
            file_paths: List of paths to .als files

        Returns:
            BatchScanResult with all song summaries
        """
        result = BatchScanResult(
            scan_path="Multiple files",
            total_scanned=len(file_paths),
            successful=0,
            failed=0
        )

        for file_path in file_paths:
            summary = self._scan_file(file_path)
            result.songs.append(summary)
            if summary.error:
                result.failed += 1
            else:
                result.successful += 1

        # Sort by health score
        result.songs.sort(key=lambda s: s.health_score, reverse=True)
        self._categorize_songs(result)

        return result

    def _scan_file(self, file_path: str) -> SongSummary:
        """Scan a single .als file."""
        try:
            # Analyze
            analysis = self.analyzer.analyze(file_path)
            diagnosis = self.doctor.diagnose(analysis)

            # Calculate grade
            grade = self._calculate_grade(diagnosis.overall_health)
            recommendation = self._generate_recommendation(diagnosis, grade)

            # Use folder name if file is generic (project.als, etc)
            file_name = Path(file_path).name
            if file_name.lower() in ["project.als", "untitled.als"]:
                parent_name = Path(file_path).parent.name
                file_name = f"{parent_name}/{file_name}"

            return SongSummary(
                file_path=file_path,
                file_name=file_name,
                health_score=diagnosis.overall_health,
                total_issues=diagnosis.total_issues,
                critical_issues=diagnosis.critical_issues,
                warning_issues=diagnosis.warning_issues,
                total_devices=diagnosis.total_devices,
                disabled_devices=diagnosis.total_disabled,
                clutter_percentage=diagnosis.clutter_percentage,
                tempo=analysis.tempo,
                track_count=len(analysis.tracks),
                workability_grade=grade,
                recommendation=recommendation
            )
        except Exception as e:
            return SongSummary(
                file_path=file_path,
                file_name=Path(file_path).name,
                health_score=0,
                total_issues=0,
                critical_issues=0,
                warning_issues=0,
                total_devices=0,
                disabled_devices=0,
                clutter_percentage=0,
                tempo=0,
                track_count=0,
                workability_grade="?",
                recommendation="Could not analyze",
                error=str(e)
            )

    def _calculate_grade(self, health_score: int) -> str:
        """Convert health score to letter grade."""
        for grade, (min_score, max_score) in self.GRADES.items():
            if min_score <= health_score <= max_score:
                return grade
        return "?"

    def _generate_recommendation(self, diagnosis: ProjectDiagnosis,
                                grade: str) -> str:
        """Generate a recommendation based on diagnosis."""
        if grade == "A":
            return "Great shape! Focus on arrangement and final polish."
        elif grade == "B":
            return "Looking good. Clean up clutter, then focus on the mix."
        elif grade == "C":
            return "Needs work. Delete disabled devices, fix chain issues."
        elif grade == "D":
            return "Significant cleanup needed. Consider simplifying."
        else:
            return "Major issues. Consider starting fresh or heavy cleanup."

    def _categorize_songs(self, result: BatchScanResult) -> None:
        """Categorize songs into recommendation buckets."""
        for song in result.songs:
            if song.error:
                continue

            if song.workability_grade in ["A", "B"]:
                result.best_songs.append(song.file_name)
            elif song.workability_grade == "C":
                result.needs_cleanup.append(song.file_name)
            elif song.workability_grade in ["D", "F"]:
                result.consider_abandoning.append(song.file_name)

    def generate_report(self, result: BatchScanResult) -> str:
        """Generate a human-readable scan report."""
        lines = []
        lines.append("=" * 70)
        lines.append("BATCH PROJECT SCAN REPORT")
        lines.append("=" * 70)
        lines.append(f"Scanned: {result.scan_path}")
        lines.append(f"Total files: {result.total_scanned}")
        lines.append(f"Successful: {result.successful}")
        lines.append(f"Failed: {result.failed}")
        lines.append("")

        # Summary by grade
        grades = {}
        for song in result.songs:
            grade = song.workability_grade
            grades[grade] = grades.get(grade, 0) + 1

        lines.append("-" * 70)
        lines.append("GRADE DISTRIBUTION:")
        lines.append("-" * 70)
        for grade in ["A", "B", "C", "D", "F", "?"]:
            count = grades.get(grade, 0)
            bar = "#" * count
            lines.append(f"  {grade}: {count:3d} {bar}")
        lines.append("")

        # Top picks
        if result.best_songs:
            lines.append("-" * 70)
            lines.append("BEST SONGS TO WORK ON (Grade A/B):")
            lines.append("-" * 70)
            for name in result.best_songs[:10]:
                song = next((s for s in result.songs if s.file_name == name), None)
                if song:
                    lines.append(f"  [{song.workability_grade}] {name} - {song.health_score}/100, {song.tempo:.0f} BPM")
            lines.append("")

        # Needs cleanup
        if result.needs_cleanup:
            lines.append("-" * 70)
            lines.append("SALVAGEABLE - NEEDS CLEANUP (Grade C):")
            lines.append("-" * 70)
            for name in result.needs_cleanup[:10]:
                song = next((s for s in result.songs if s.file_name == name), None)
                if song:
                    lines.append(f"  [{song.workability_grade}] {name} - {song.health_score}/100, {song.clutter_percentage:.0f}% clutter")
            lines.append("")

        # Consider abandoning
        if result.consider_abandoning:
            lines.append("-" * 70)
            lines.append("CONSIDER STARTING FRESH (Grade D/F):")
            lines.append("-" * 70)
            for name in result.consider_abandoning[:10]:
                song = next((s for s in result.songs if s.file_name == name), None)
                if song:
                    lines.append(f"  [{song.workability_grade}] {name} - {song.health_score}/100, {song.total_issues} issues")
            lines.append("")

        # Full ranking
        lines.append("-" * 70)
        lines.append("FULL RANKING (by health score):")
        lines.append("-" * 70)
        lines.append(f"{'Rank':<5} {'Grade':<6} {'Health':<8} {'Issues':<8} {'Clutter':<10} {'Name'}")
        lines.append("-" * 70)

        for i, song in enumerate(result.songs[:30], 1):
            if song.error:
                lines.append(f"{i:<5} {'ERR':<6} {'-':<8} {'-':<8} {'-':<10} {song.file_name} ({song.error[:30]})")
            else:
                lines.append(
                    f"{i:<5} {song.workability_grade:<6} {song.health_score:<8} "
                    f"{song.total_issues:<8} {song.clutter_percentage:>6.0f}%    {song.file_name}"
                )

        if len(result.songs) > 30:
            lines.append(f"  ... and {len(result.songs) - 30} more")

        lines.append("")
        lines.append("=" * 70)
        lines.append("RECOMMENDATION: Start with Grade A/B songs. Clean up Grade C songs")
        lines.append("if you like the musical idea. Consider fresh starts for D/F grades.")
        lines.append("=" * 70)

        return "\n".join(lines)


def scan_directory(directory: str, recursive: bool = True,
                  verbose: bool = False) -> BatchScanResult:
    """Quick function to scan a directory."""
    scanner = BatchScanner(verbose=verbose)
    return scanner.scan_directory(directory, recursive=recursive)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = scan_directory(sys.argv[1], verbose=True)
        scanner = BatchScanner()
        print(scanner.generate_report(result))
    else:
        print("Usage: python batch_scanner.py <directory>")
        print("Scans all .als files in directory and ranks by workability")
