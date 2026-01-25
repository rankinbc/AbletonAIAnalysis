"""
Coach Mode - Interactive Guided Workflow for ALS Doctor

Provides a step-by-step guided workflow for fixing issues in Ableton projects.
Shows one issue at a time with specific fix instructions, then re-analyzes
after the user confirms the fix.

Features:
- Shows top priority issue with clear fix instructions
- Waits for user input: Enter (done), S (skip), Q (quit)
- Re-analyzes after fix confirmation to verify improvement
- Tracks session progress (fixed, skipped)
- Celebrates health improvements
- Session summary at the end
"""

import time
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Callable, Any
from datetime import datetime


@dataclass
class IssueProgress:
    """Tracks the progress of a single issue during coaching."""
    description: str
    track_name: Optional[str]
    severity: str
    category: str
    fix_suggestion: str
    status: str  # 'pending', 'fixed', 'skipped'
    health_before: int = 0
    health_after: int = 0
    fix_duration: float = 0.0  # seconds spent on this fix


@dataclass
class CoachSessionStats:
    """Statistics for a coaching session."""
    file_path: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    initial_health: int = 0
    final_health: int = 0
    initial_grade: str = 'F'
    final_grade: str = 'F'
    initial_issues: int = 0
    final_issues: int = 0
    issues_fixed: int = 0
    issues_skipped: int = 0
    total_issues_addressed: int = 0
    re_analyses: int = 0
    health_improvements: List[int] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        """Get session duration in seconds."""
        if self.ended_at is None:
            return (datetime.now() - self.started_at).total_seconds()
        return (self.ended_at - self.started_at).total_seconds()

    @property
    def duration_formatted(self) -> str:
        """Get session duration as formatted string."""
        seconds = int(self.duration_seconds)
        if seconds < 60:
            return f"{seconds}s"
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        if minutes < 60:
            return f"{minutes}m {remaining_seconds}s"
        hours = minutes // 60
        remaining_minutes = minutes % 60
        return f"{hours}h {remaining_minutes}m"

    @property
    def health_delta(self) -> int:
        """Get total health improvement."""
        return self.final_health - self.initial_health

    @property
    def avg_improvement_per_fix(self) -> float:
        """Get average health improvement per fixed issue."""
        if self.issues_fixed == 0:
            return 0.0
        return sum(self.health_improvements) / self.issues_fixed if self.health_improvements else 0.0


class CoachSession:
    """
    Interactive coaching session for fixing Ableton project issues.

    Guides the user through one issue at a time, providing specific
    fix instructions and re-analyzing after each confirmed fix.
    """

    def __init__(
        self,
        file_path: str,
        analyzer_fn: Callable[[str], Any],
        formatter: Optional[Any] = None,
        auto_check_interval: Optional[int] = None,
        quiet: bool = False
    ):
        """
        Initialize a coaching session.

        Args:
            file_path: Path to the .als file to coach
            analyzer_fn: Function that analyzes the file and returns a ScanResult
            formatter: CLIFormatter instance for output (optional)
            auto_check_interval: Seconds between auto re-checks (optional)
            quiet: Suppress non-essential output
        """
        self.file_path = Path(file_path).absolute()
        self.analyzer_fn = analyzer_fn
        self.auto_check_interval = auto_check_interval
        self.quiet = quiet

        # Lazy import formatter to avoid circular deps
        if formatter is None:
            from cli_formatter import get_formatter
            self.fmt = get_formatter()
        else:
            self.fmt = formatter

        # Session state
        self.stats = CoachSessionStats(
            file_path=str(self.file_path),
            started_at=datetime.now()
        )
        self.current_scan: Optional[Any] = None
        self.issue_history: List[IssueProgress] = []
        self._running = False
        self._last_check_time: float = 0

    def _analyze(self) -> bool:
        """
        Analyze the file and update current scan result.

        Returns:
            True if analysis successful, False otherwise
        """
        try:
            self.current_scan = self.analyzer_fn(str(self.file_path))
            if self.current_scan is None:
                return False
            self.stats.re_analyses += 1
            return True
        except Exception as e:
            self.fmt.error(f"Analysis failed: {e}")
            return False

    def _get_top_issue(self) -> Optional[Any]:
        """Get the highest priority issue from current scan."""
        if self.current_scan is None or not self.current_scan.issues:
            return None

        # Priority: critical > warning > suggestion
        severity_priority = {'critical': 0, 'warning': 1, 'suggestion': 2}

        sorted_issues = sorted(
            self.current_scan.issues,
            key=lambda i: (severity_priority.get(i.severity, 3), i.description)
        )

        return sorted_issues[0] if sorted_issues else None

    def _display_issue(self, issue: Any, issue_num: int, total: int):
        """Display a single issue with fix instructions."""
        self.fmt.print("")
        self.fmt.print_line("-", 60)
        self.fmt.print(f"Issue {issue_num}/{total}")
        self.fmt.print_line("-", 60)

        # Severity badge
        severity = issue.severity.upper()
        if self.fmt.use_rich:
            if severity == 'CRITICAL':
                self.fmt.print(f"[red][{severity}][/red]")
            elif severity == 'WARNING':
                self.fmt.print(f"[yellow][{severity}][/yellow]")
            else:
                self.fmt.print(f"[cyan][{severity}][/cyan]")
        else:
            self.fmt.print(f"[{severity}]")

        # Track and description
        if issue.track_name:
            self.fmt.print(f"Track: {issue.track_name}")
        self.fmt.print(f"Issue: {issue.description}")

        # Category
        if hasattr(issue, 'category') and issue.category:
            self.fmt.print(f"Category: {issue.category}")

        # Fix instructions
        self.fmt.print("")
        if self.fmt.use_rich:
            self.fmt.print("[highlight]HOW TO FIX:[/highlight]")
        else:
            self.fmt.print("HOW TO FIX:")

        if issue.fix_suggestion:
            self.fmt.print(f"  {issue.fix_suggestion}")
        else:
            # Provide generic fix suggestion based on category
            self.fmt.print(f"  Resolve the {issue.severity} issue in Ableton")

        self.fmt.print("")

    def _display_current_health(self):
        """Display current health score."""
        if self.current_scan is None:
            return

        score = self.current_scan.health_score
        grade = self.current_scan.grade
        issues = self.current_scan.total_issues

        self.fmt.print("")
        if self.fmt.use_rich:
            grade_style = f"grade.{grade.lower()}"
            self.fmt.print(f"Current Health: [{grade_style}]{score}/100 [{grade}][/{grade_style}] | {issues} issue(s)")
        else:
            self.fmt.print(f"Current Health: {score}/100 [{grade}] | {issues} issue(s)")

    def _celebrate_improvement(self, old_score: int, new_score: int, old_issues: int, new_issues: int):
        """Celebrate when health improves."""
        delta = new_score - old_score
        issues_fixed = old_issues - new_issues

        if delta > 0:
            self.stats.health_improvements.append(delta)

            self.fmt.print("")
            if self.fmt.use_rich:
                if delta >= 10:
                    self.fmt.print(f"[green bold]EXCELLENT! Health improved by +{delta} points![/green bold]")
                elif delta >= 5:
                    self.fmt.print(f"[green]Great! Health improved by +{delta} points[/green]")
                else:
                    self.fmt.print(f"[green]Health improved by +{delta} points[/green]")
            else:
                if delta >= 10:
                    self.fmt.print(f"EXCELLENT! Health improved by +{delta} points!")
                elif delta >= 5:
                    self.fmt.print(f"Great! Health improved by +{delta} points")
                else:
                    self.fmt.print(f"Health improved by +{delta} points")

        if issues_fixed > 0:
            if self.fmt.use_rich:
                self.fmt.print(f"[cyan]{issues_fixed} issue(s) resolved[/cyan]")
            else:
                self.fmt.print(f"{issues_fixed} issue(s) resolved")

    def _get_user_input(self) -> str:
        """
        Get user input for the current issue.

        Returns:
            'done', 'skip', or 'quit'
        """
        self.fmt.print("")
        if self.fmt.use_rich:
            self.fmt.print("[dim]Commands: [Enter]=Fixed  [S]=Skip  [Q]=Quit[/dim]")
        else:
            self.fmt.print("Commands: [Enter]=Fixed  [S]=Skip  [Q]=Quit")

        try:
            response = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return 'quit'

        if response == '' or response == 'done' or response == 'd':
            return 'done'
        elif response == 's' or response == 'skip':
            return 'skip'
        elif response == 'q' or response == 'quit':
            return 'quit'
        else:
            self.fmt.print("Unknown command. Use Enter, S, or Q.")
            return self._get_user_input()

    def _display_session_summary(self):
        """Display the final session summary."""
        self.stats.ended_at = datetime.now()

        self.fmt.print("")
        self.fmt.print_line("=", 60)
        self.fmt.header("COACHING SESSION COMPLETE")
        self.fmt.print_line("=", 60)

        # File info
        self.fmt.print(f"  File: {self.file_path.name}")
        self.fmt.print(f"  Duration: {self.stats.duration_formatted}")
        self.fmt.print("")

        # Health comparison
        if self.fmt.use_rich:
            initial_grade_style = f"grade.{self.stats.initial_grade.lower()}"
            final_grade_style = f"grade.{self.stats.final_grade.lower()}"

            self.fmt.print("  Health Score:")
            self.fmt.print(f"    Before: [{initial_grade_style}]{self.stats.initial_health}/100 [{self.stats.initial_grade}][/{initial_grade_style}]")
            self.fmt.print(f"    After:  [{final_grade_style}]{self.stats.final_health}/100 [{self.stats.final_grade}][/{final_grade_style}]")

            if self.stats.health_delta > 0:
                self.fmt.print(f"    Change: [green]+{self.stats.health_delta}[/green]")
            elif self.stats.health_delta < 0:
                self.fmt.print(f"    Change: [red]{self.stats.health_delta}[/red]")
            else:
                self.fmt.print("    Change: 0")
        else:
            self.fmt.print("  Health Score:")
            self.fmt.print(f"    Before: {self.stats.initial_health}/100 [{self.stats.initial_grade}]")
            self.fmt.print(f"    After:  {self.stats.final_health}/100 [{self.stats.final_grade}]")
            self.fmt.print(f"    Change: {self.stats.health_delta:+d}")

        self.fmt.print("")

        # Issue stats
        self.fmt.print("  Issues:")
        self.fmt.print(f"    Before: {self.stats.initial_issues}")
        self.fmt.print(f"    After:  {self.stats.final_issues}")
        self.fmt.print(f"    Fixed:  {self.stats.issues_fixed}")
        self.fmt.print(f"    Skipped: {self.stats.issues_skipped}")
        self.fmt.print("")

        # Re-analysis count
        self.fmt.print(f"  Re-analyses: {self.stats.re_analyses}")

        # Encouragement message
        self.fmt.print("")
        if self.stats.health_delta >= 20:
            if self.fmt.use_rich:
                self.fmt.print("[green bold]Outstanding work! Major improvement achieved![/green bold]")
            else:
                self.fmt.print("Outstanding work! Major improvement achieved!")
        elif self.stats.health_delta >= 10:
            if self.fmt.use_rich:
                self.fmt.print("[green]Great progress! Keep it up![/green]")
            else:
                self.fmt.print("Great progress! Keep it up!")
        elif self.stats.health_delta > 0:
            self.fmt.print("Good effort! Every improvement counts.")
        elif self.stats.issues_skipped > 0 and self.stats.issues_fixed == 0:
            self.fmt.print("No fixes confirmed. Consider addressing skipped issues later.")
        else:
            self.fmt.print("Session complete. Run coach mode again to continue improving.")

        self.fmt.print("")

    def run(self) -> CoachSessionStats:
        """
        Run the interactive coaching session.

        Returns:
            CoachSessionStats with session results
        """
        self._running = True

        # Initial analysis
        self.fmt.header(f"ALS DOCTOR - Coach Mode")
        self.fmt.print(f"File: {self.file_path.name}")
        self.fmt.print("")
        self.fmt.print("Analyzing...")

        if not self._analyze():
            self.fmt.error("Failed to analyze file. Cannot start coaching session.")
            self.stats.ended_at = datetime.now()
            return self.stats

        # Store initial stats
        self.stats.initial_health = self.current_scan.health_score
        self.stats.initial_grade = self.current_scan.grade
        self.stats.initial_issues = self.current_scan.total_issues
        self.stats.final_health = self.stats.initial_health
        self.stats.final_grade = self.stats.initial_grade
        self.stats.final_issues = self.stats.initial_issues

        # Display initial state
        self._display_current_health()

        if self.current_scan.total_issues == 0:
            self.fmt.print("")
            if self.fmt.use_rich:
                self.fmt.print("[green]No issues found! Your project is in great shape.[/green]")
            else:
                self.fmt.print("No issues found! Your project is in great shape.")
            self._display_session_summary()
            return self.stats

        self.fmt.print("")
        self.fmt.print("Starting guided coaching session...")
        self.fmt.print("Fix issues one at a time. I'll re-analyze after each fix.")

        # Main coaching loop
        issue_num = 0
        while self._running:
            issue = self._get_top_issue()

            if issue is None:
                self.fmt.print("")
                if self.fmt.use_rich:
                    self.fmt.print("[green bold]All issues resolved! Excellent work![/green bold]")
                else:
                    self.fmt.print("All issues resolved! Excellent work!")
                break

            issue_num += 1
            total_issues = len(self.current_scan.issues) if self.current_scan else 0

            # Display the issue
            self._display_issue(issue, issue_num, total_issues)
            self._display_current_health()

            # Get user input
            fix_start_time = time.time()
            response = self._get_user_input()
            fix_duration = time.time() - fix_start_time

            if response == 'quit':
                self.fmt.print("")
                self.fmt.print("Exiting coach mode...")
                break

            # Track issue progress
            progress = IssueProgress(
                description=issue.description,
                track_name=issue.track_name if hasattr(issue, 'track_name') else None,
                severity=issue.severity,
                category=issue.category if hasattr(issue, 'category') else '',
                fix_suggestion=issue.fix_suggestion if hasattr(issue, 'fix_suggestion') else '',
                status='pending',
                health_before=self.current_scan.health_score if self.current_scan else 0,
                fix_duration=fix_duration
            )

            if response == 'skip':
                progress.status = 'skipped'
                self.stats.issues_skipped += 1
                self.issue_history.append(progress)

                if self.fmt.use_rich:
                    self.fmt.print("[dim]Skipped. Moving to next issue...[/dim]")
                else:
                    self.fmt.print("Skipped. Moving to next issue...")

                # We need to move to the next issue, but we don't re-analyze
                # Just remove this issue from consideration temporarily
                if self.current_scan and self.current_scan.issues:
                    # Filter out the skipped issue for next iteration
                    self.current_scan.issues = [
                        i for i in self.current_scan.issues
                        if not (i.description == issue.description and
                               getattr(i, 'track_name', None) == getattr(issue, 'track_name', None))
                    ]
                continue

            elif response == 'done':
                # Re-analyze to check if fix worked
                self.fmt.print("")
                self.fmt.print("Re-analyzing to verify fix...")

                old_score = self.current_scan.health_score if self.current_scan else 0
                old_issues = self.current_scan.total_issues if self.current_scan else 0

                if not self._analyze():
                    self.fmt.warning("Re-analysis failed. Continuing with previous state.")
                    continue

                new_score = self.current_scan.health_score
                new_issues = self.current_scan.total_issues

                progress.health_after = new_score
                progress.status = 'fixed'
                self.stats.issues_fixed += 1
                self.issue_history.append(progress)

                # Update final stats
                self.stats.final_health = new_score
                self.stats.final_grade = self.current_scan.grade
                self.stats.final_issues = new_issues

                # Celebrate improvement
                self._celebrate_improvement(old_score, new_score, old_issues, new_issues)

            self.stats.total_issues_addressed += 1

            # Auto-check mode
            if self.auto_check_interval and self._running:
                current_time = time.time()
                if current_time - self._last_check_time >= self.auto_check_interval:
                    self._last_check_time = current_time
                    self.fmt.print("")
                    self.fmt.print(f"[Auto-check after {self.auto_check_interval}s]")
                    if not self._analyze():
                        self.fmt.warning("Auto re-analysis failed.")

        self._running = False
        self._display_session_summary()
        return self.stats

    def stop(self):
        """Stop the coaching session."""
        self._running = False


def coach_mode(
    file_path: str,
    analyzer_fn: Callable[[str], Any],
    formatter: Optional[Any] = None,
    auto_check_interval: Optional[int] = None,
    quiet: bool = False
) -> CoachSessionStats:
    """
    Run an interactive coaching session for fixing Ableton project issues.

    Args:
        file_path: Path to the .als file to coach
        analyzer_fn: Function that analyzes the file and returns a ScanResult
        formatter: CLIFormatter instance for output (optional)
        auto_check_interval: Seconds between auto re-checks (optional)
        quiet: Suppress non-essential output

    Returns:
        CoachSessionStats with session results
    """
    session = CoachSession(
        file_path=file_path,
        analyzer_fn=analyzer_fn,
        formatter=formatter,
        auto_check_interval=auto_check_interval,
        quiet=quiet
    )
    return session.run()
