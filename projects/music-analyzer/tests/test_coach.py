"""
Tests for Coach Mode (Story 3.2)

Tests the interactive guided workflow for fixing Ableton project issues.
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from io import StringIO

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from coach import (
    CoachSession, CoachSessionStats, IssueProgress, coach_mode
)


# Mock classes for testing
class MockIssue:
    """Mock issue for testing."""
    def __init__(self, description: str, severity: str = 'warning',
                 track_name: str = None, category: str = 'test',
                 fix_suggestion: str = 'Fix this issue'):
        self.description = description
        self.severity = severity
        self.track_name = track_name
        self.category = category
        self.fix_suggestion = fix_suggestion


class MockScanResult:
    """Mock scan result for testing."""
    def __init__(self, health_score: int = 75, grade: str = 'B',
                 total_issues: int = 5, issues: list = None):
        self.health_score = health_score
        self.grade = grade
        self.total_issues = total_issues
        self.issues = issues or []


class MockFormatter:
    """Mock formatter for testing that captures output."""
    def __init__(self):
        self.output = []
        self.use_rich = False

    def print(self, text='', style=None):
        self.output.append(str(text))

    def print_line(self, char='-', width=50):
        self.output.append(char * width)

    def header(self, text, style=None):
        self.output.append(f"HEADER: {text}")

    def error(self, message, prefix='ERROR: '):
        self.output.append(f"{prefix}{message}")

    def warning(self, message, prefix='WARNING: '):
        self.output.append(f"{prefix}{message}")

    def success(self, message, prefix='SUCCESS: '):
        self.output.append(f"{prefix}{message}")

    def get_output(self) -> str:
        return '\n'.join(self.output)


def run_tests():
    """Run all coach mode tests."""
    print("=" * 60)
    print("Coach Mode Tests (Story 3.2)")
    print("=" * 60)
    print()

    passed = 0
    failed = 0

    # Test 1: IssueProgress dataclass
    def test_issue_progress_dataclass():
        progress = IssueProgress(
            description="Test issue",
            track_name="Bass",
            severity="warning",
            category="test",
            fix_suggestion="Fix it",
            status="pending"
        )
        assert progress.description == "Test issue"
        assert progress.track_name == "Bass"
        assert progress.severity == "warning"
        assert progress.status == "pending"
        assert progress.health_before == 0
        assert progress.health_after == 0

    try:
        test_issue_progress_dataclass()
        print("  ✓ IssueProgress dataclass")
        passed += 1
    except Exception as e:
        print(f"  ✗ IssueProgress dataclass: {e}")
        failed += 1

    # Test 2: CoachSessionStats dataclass
    def test_coach_session_stats_dataclass():
        stats = CoachSessionStats(
            file_path="/test/file.als",
            started_at=datetime.now()
        )
        assert stats.file_path == "/test/file.als"
        assert stats.initial_health == 0
        assert stats.final_health == 0
        assert stats.issues_fixed == 0
        assert stats.issues_skipped == 0
        assert stats.re_analyses == 0

    try:
        test_coach_session_stats_dataclass()
        print("  ✓ CoachSessionStats dataclass")
        passed += 1
    except Exception as e:
        print(f"  ✗ CoachSessionStats dataclass: {e}")
        failed += 1

    # Test 3: Session stats duration formatting
    def test_session_stats_duration():
        stats = CoachSessionStats(
            file_path="/test/file.als",
            started_at=datetime.now() - timedelta(seconds=125)
        )
        # Duration should be ~2m 5s
        formatted = stats.duration_formatted
        assert 'm' in formatted or 's' in formatted

    try:
        test_session_stats_duration()
        print("  ✓ Session stats duration formatting")
        passed += 1
    except Exception as e:
        print(f"  ✗ Session stats duration formatting: {e}")
        failed += 1

    # Test 4: Health delta calculation
    def test_health_delta():
        stats = CoachSessionStats(
            file_path="/test/file.als",
            started_at=datetime.now()
        )
        stats.initial_health = 50
        stats.final_health = 75
        assert stats.health_delta == 25

    try:
        test_health_delta()
        print("  ✓ Health delta calculation")
        passed += 1
    except Exception as e:
        print(f"  ✗ Health delta calculation: {e}")
        failed += 1

    # Test 5: Average improvement per fix
    def test_avg_improvement_per_fix():
        stats = CoachSessionStats(
            file_path="/test/file.als",
            started_at=datetime.now()
        )
        stats.issues_fixed = 3
        stats.health_improvements = [5, 10, 15]
        avg = stats.avg_improvement_per_fix
        assert avg == 10.0

    try:
        test_avg_improvement_per_fix()
        print("  ✓ Average improvement per fix")
        passed += 1
    except Exception as e:
        print(f"  ✗ Average improvement per fix: {e}")
        failed += 1

    # Test 6: CoachSession initialization
    def test_coach_session_init():
        fmt = MockFormatter()

        def mock_analyzer(path):
            return MockScanResult()

        session = CoachSession(
            file_path="/test/file.als",
            analyzer_fn=mock_analyzer,
            formatter=fmt
        )
        assert session.file_path == Path("/test/file.als").absolute()
        assert session.current_scan is None
        assert session.auto_check_interval is None

    try:
        test_coach_session_init()
        print("  ✓ CoachSession initialization")
        passed += 1
    except Exception as e:
        print(f"  ✗ CoachSession initialization: {e}")
        failed += 1

    # Test 7: CoachSession with auto-check interval
    def test_coach_session_auto_check():
        fmt = MockFormatter()

        def mock_analyzer(path):
            return MockScanResult()

        session = CoachSession(
            file_path="/test/file.als",
            analyzer_fn=mock_analyzer,
            formatter=fmt,
            auto_check_interval=30
        )
        assert session.auto_check_interval == 30

    try:
        test_coach_session_auto_check()
        print("  ✓ CoachSession with auto-check interval")
        passed += 1
    except Exception as e:
        print(f"  ✗ CoachSession with auto-check interval: {e}")
        failed += 1

    # Test 8: Get top issue priority (critical first)
    def test_get_top_issue_priority():
        fmt = MockFormatter()
        issues = [
            MockIssue("Warning issue", severity="warning"),
            MockIssue("Critical issue", severity="critical"),
            MockIssue("Suggestion issue", severity="suggestion"),
        ]

        def mock_analyzer(path):
            return MockScanResult(issues=issues, total_issues=3)

        session = CoachSession(
            file_path="/test/file.als",
            analyzer_fn=mock_analyzer,
            formatter=fmt
        )
        session.current_scan = mock_analyzer("/test/file.als")

        top_issue = session._get_top_issue()
        assert top_issue is not None
        assert top_issue.severity == "critical"

    try:
        test_get_top_issue_priority()
        print("  ✓ Get top issue priority (critical first)")
        passed += 1
    except Exception as e:
        print(f"  ✗ Get top issue priority (critical first): {e}")
        failed += 1

    # Test 9: Get top issue - no issues
    def test_get_top_issue_empty():
        fmt = MockFormatter()

        def mock_analyzer(path):
            return MockScanResult(issues=[], total_issues=0)

        session = CoachSession(
            file_path="/test/file.als",
            analyzer_fn=mock_analyzer,
            formatter=fmt
        )
        session.current_scan = mock_analyzer("/test/file.als")

        top_issue = session._get_top_issue()
        assert top_issue is None

    try:
        test_get_top_issue_empty()
        print("  ✓ Get top issue - no issues")
        passed += 1
    except Exception as e:
        print(f"  ✗ Get top issue - no issues: {e}")
        failed += 1

    # Test 10: Display issue formatting
    def test_display_issue():
        fmt = MockFormatter()
        issues = [MockIssue("Test issue", track_name="Bass", severity="warning")]

        def mock_analyzer(path):
            return MockScanResult(issues=issues, total_issues=1)

        session = CoachSession(
            file_path="/test/file.als",
            analyzer_fn=mock_analyzer,
            formatter=fmt
        )

        session._display_issue(issues[0], 1, 1)
        output = fmt.get_output()

        assert "Issue 1/1" in output
        assert "WARNING" in output
        assert "Test issue" in output
        assert "Bass" in output
        assert "HOW TO FIX" in output

    try:
        test_display_issue()
        print("  ✓ Display issue formatting")
        passed += 1
    except Exception as e:
        print(f"  ✗ Display issue formatting: {e}")
        failed += 1

    # Test 11: Display current health
    def test_display_current_health():
        fmt = MockFormatter()

        def mock_analyzer(path):
            return MockScanResult(health_score=85, grade='A', total_issues=2)

        session = CoachSession(
            file_path="/test/file.als",
            analyzer_fn=mock_analyzer,
            formatter=fmt
        )
        session.current_scan = mock_analyzer("/test/file.als")

        session._display_current_health()
        output = fmt.get_output()

        assert "85" in output
        assert "A" in output
        assert "2" in output

    try:
        test_display_current_health()
        print("  ✓ Display current health")
        passed += 1
    except Exception as e:
        print(f"  ✗ Display current health: {e}")
        failed += 1

    # Test 12: Celebrate improvement (big improvement)
    def test_celebrate_big_improvement():
        fmt = MockFormatter()

        def mock_analyzer(path):
            return MockScanResult()

        session = CoachSession(
            file_path="/test/file.als",
            analyzer_fn=mock_analyzer,
            formatter=fmt
        )

        session._celebrate_improvement(50, 75, 10, 5)
        output = fmt.get_output()

        assert "EXCELLENT" in output or "+25" in output or "improved" in output.lower()
        assert "5" in output  # issues resolved

    try:
        test_celebrate_big_improvement()
        print("  ✓ Celebrate big improvement")
        passed += 1
    except Exception as e:
        print(f"  ✗ Celebrate big improvement: {e}")
        failed += 1

    # Test 13: Celebrate improvement (small improvement)
    def test_celebrate_small_improvement():
        fmt = MockFormatter()

        def mock_analyzer(path):
            return MockScanResult()

        session = CoachSession(
            file_path="/test/file.als",
            analyzer_fn=mock_analyzer,
            formatter=fmt
        )

        session._celebrate_improvement(70, 73, 5, 4)
        output = fmt.get_output()

        assert "improved" in output.lower() or "+3" in output

    try:
        test_celebrate_small_improvement()
        print("  ✓ Celebrate small improvement")
        passed += 1
    except Exception as e:
        print(f"  ✗ Celebrate small improvement: {e}")
        failed += 1

    # Test 14: Session summary display
    def test_session_summary_display():
        fmt = MockFormatter()

        def mock_analyzer(path):
            return MockScanResult()

        session = CoachSession(
            file_path="/test/file.als",
            analyzer_fn=mock_analyzer,
            formatter=fmt
        )
        session.stats.initial_health = 50
        session.stats.final_health = 80
        session.stats.initial_grade = 'C'
        session.stats.final_grade = 'A'
        session.stats.initial_issues = 10
        session.stats.final_issues = 3
        session.stats.issues_fixed = 5
        session.stats.issues_skipped = 2

        session._display_session_summary()
        output = fmt.get_output()

        assert "COACHING SESSION COMPLETE" in output
        assert "50" in output  # initial health
        assert "80" in output  # final health
        assert "Fixed" in output

    try:
        test_session_summary_display()
        print("  ✓ Session summary display")
        passed += 1
    except Exception as e:
        print(f"  ✗ Session summary display: {e}")
        failed += 1

    # Test 15: Stop session
    def test_stop_session():
        fmt = MockFormatter()

        def mock_analyzer(path):
            return MockScanResult()

        session = CoachSession(
            file_path="/test/file.als",
            analyzer_fn=mock_analyzer,
            formatter=fmt
        )
        session._running = True
        session.stop()
        assert session._running == False

    try:
        test_stop_session()
        print("  ✓ Stop session")
        passed += 1
    except Exception as e:
        print(f"  ✗ Stop session: {e}")
        failed += 1

    # Test 16: Analysis tracking
    def test_analysis_tracking():
        fmt = MockFormatter()
        call_count = [0]

        def mock_analyzer(path):
            call_count[0] += 1
            return MockScanResult()

        session = CoachSession(
            file_path="/test/file.als",
            analyzer_fn=mock_analyzer,
            formatter=fmt
        )

        session._analyze()
        session._analyze()
        session._analyze()

        assert session.stats.re_analyses == 3
        assert call_count[0] == 3

    try:
        test_analysis_tracking()
        print("  ✓ Analysis tracking")
        passed += 1
    except Exception as e:
        print(f"  ✗ Analysis tracking: {e}")
        failed += 1

    # Test 17: Analysis failure handling
    def test_analysis_failure():
        fmt = MockFormatter()

        def mock_analyzer(path):
            return None  # Simulates failure

        session = CoachSession(
            file_path="/test/file.als",
            analyzer_fn=mock_analyzer,
            formatter=fmt
        )

        result = session._analyze()
        assert result == False

    try:
        test_analysis_failure()
        print("  ✓ Analysis failure handling")
        passed += 1
    except Exception as e:
        print(f"  ✗ Analysis failure handling: {e}")
        failed += 1

    # Test 18: Issue history tracking
    def test_issue_history_tracking():
        fmt = MockFormatter()

        def mock_analyzer(path):
            return MockScanResult()

        session = CoachSession(
            file_path="/test/file.als",
            analyzer_fn=mock_analyzer,
            formatter=fmt
        )

        progress = IssueProgress(
            description="Test issue",
            track_name="Bass",
            severity="warning",
            category="test",
            fix_suggestion="Fix it",
            status="fixed"
        )
        session.issue_history.append(progress)

        assert len(session.issue_history) == 1
        assert session.issue_history[0].status == "fixed"

    try:
        test_issue_history_tracking()
        print("  ✓ Issue history tracking")
        passed += 1
    except Exception as e:
        print(f"  ✗ Issue history tracking: {e}")
        failed += 1

    # Test 19: Duration formatting - seconds
    def test_duration_seconds():
        stats = CoachSessionStats(
            file_path="/test/file.als",
            started_at=datetime.now() - timedelta(seconds=45)
        )
        assert 's' in stats.duration_formatted
        assert 'm' not in stats.duration_formatted or '0m' in stats.duration_formatted

    try:
        test_duration_seconds()
        print("  ✓ Duration formatting - seconds")
        passed += 1
    except Exception as e:
        print(f"  ✗ Duration formatting - seconds: {e}")
        failed += 1

    # Test 20: Duration formatting - hours
    def test_duration_hours():
        stats = CoachSessionStats(
            file_path="/test/file.als",
            started_at=datetime.now() - timedelta(hours=2, minutes=30)
        )
        assert 'h' in stats.duration_formatted

    try:
        test_duration_hours()
        print("  ✓ Duration formatting - hours")
        passed += 1
    except Exception as e:
        print(f"  ✗ Duration formatting - hours: {e}")
        failed += 1

    # Test 21: No issues celebration message
    def test_no_issues_message():
        fmt = MockFormatter()

        def mock_analyzer(path):
            return MockScanResult(health_score=100, grade='A', total_issues=0, issues=[])

        session = CoachSession(
            file_path="/test/file.als",
            analyzer_fn=mock_analyzer,
            formatter=fmt
        )

        # The run method would normally handle this - test the condition
        session._analyze()
        session.stats.initial_health = 100
        session.stats.initial_issues = 0

        assert session.current_scan.total_issues == 0

    try:
        test_no_issues_message()
        print("  ✓ No issues detection")
        passed += 1
    except Exception as e:
        print(f"  ✗ No issues detection: {e}")
        failed += 1

    # Test 22: coach_mode function exists and is callable
    def test_coach_mode_function():
        # Just verify the function exists and has correct signature
        import inspect
        sig = inspect.signature(coach_mode)
        params = list(sig.parameters.keys())

        assert 'file_path' in params
        assert 'analyzer_fn' in params
        assert 'formatter' in params
        assert 'auto_check_interval' in params
        assert 'quiet' in params

    try:
        test_coach_mode_function()
        print("  ✓ coach_mode function signature")
        passed += 1
    except Exception as e:
        print(f"  ✗ coach_mode function signature: {e}")
        failed += 1

    # Summary
    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return passed, failed


if __name__ == "__main__":
    passed, failed = run_tests()
    sys.exit(0 if failed == 0 else 1)
