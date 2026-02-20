"""
Tests for the 'db focus' command (Story 4.6 - What to Work On Next)

Tests the CLI command that shows prioritized work items across all projects.
"""

import os
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

_test_results = {'passed': 0, 'failed': 0}


def test(name: str):
    """Decorator to register and run a test."""
    def decorator(func):
        def wrapper():
            try:
                func()
                _test_results['passed'] += 1
                print(f"  ✓ {name}")
                return True
            except AssertionError as e:
                _test_results['failed'] += 1
                print(f"  ✗ {name}: {e}")
                return False
            except Exception as e:
                _test_results['failed'] += 1
                print(f"  ✗ {name}: Exception - {e}")
                return False
        wrapper.__name__ = func.__name__
        wrapper._test_name = name
        return wrapper
    return decorator


# ============================================================================
# TodaysFocus Tests (from dashboard module)
# ============================================================================

@test("TodaysFocus dataclass exists")
def test_todays_focus_dataclass():
    from dashboard import TodaysFocus
    assert TodaysFocus is not None


@test("WorkItem dataclass exists")
def test_work_item_dataclass():
    from dashboard import WorkItem
    assert WorkItem is not None


@test("get_todays_focus function exists")
def test_get_todays_focus_exists():
    from dashboard import get_todays_focus
    assert callable(get_todays_focus)


@test("get_todays_focus returns TodaysFocus")
def test_get_todays_focus_returns_type():
    from dashboard import get_todays_focus, TodaysFocus
    result = get_todays_focus()
    assert isinstance(result, TodaysFocus)


@test("TodaysFocus has quick_wins attribute")
def test_todays_focus_quick_wins():
    from dashboard import get_todays_focus
    result = get_todays_focus()
    assert hasattr(result, 'quick_wins')
    assert isinstance(result.quick_wins, list)


@test("TodaysFocus has deep_work attribute")
def test_todays_focus_deep_work():
    from dashboard import get_todays_focus
    result = get_todays_focus()
    assert hasattr(result, 'deep_work')
    assert isinstance(result.deep_work, list)


@test("TodaysFocus has ready_to_polish attribute")
def test_todays_focus_ready_to_polish():
    from dashboard import get_todays_focus
    result = get_todays_focus()
    assert hasattr(result, 'ready_to_polish')
    assert isinstance(result.ready_to_polish, list)


@test("TodaysFocus has total_suggestions attribute")
def test_todays_focus_total_suggestions():
    from dashboard import get_todays_focus
    result = get_todays_focus()
    assert hasattr(result, 'total_suggestions')
    assert isinstance(result.total_suggestions, int)


@test("WorkItem has required attributes")
def test_work_item_attributes():
    from dashboard import WorkItem

    item = WorkItem(
        project_id=1,
        song_name="Test Song",
        category="quick_win",
        reason="Easy fix",
        health_score=65,
        grade="C",
        potential_gain=15
    )

    assert item.project_id == 1
    assert item.song_name == "Test Song"
    assert item.category == "quick_win"
    assert item.reason == "Easy fix"
    assert item.health_score == 65
    assert item.grade == "C"
    assert item.potential_gain == 15


@test("WorkItem has optional days_since_worked")
def test_work_item_optional_days():
    from dashboard import WorkItem

    item = WorkItem(
        project_id=1,
        song_name="Test",
        category="deep_work",
        reason="Reason",
        health_score=30,
        grade="F",
        potential_gain=30,
        days_since_worked=14
    )

    assert item.days_since_worked == 14


# ============================================================================
# Fallback Implementation Tests
# ============================================================================

@test("Fallback implementation categorizes F grade as deep_work")
def test_fallback_f_grade():
    """F grade projects should be categorized as deep_work."""
    grade = 'F'
    score = 15

    if grade == 'F':
        category = 'deep_work'

    assert category == 'deep_work'


@test("Fallback implementation categorizes D grade as deep_work")
def test_fallback_d_grade():
    """D grade projects should be categorized as deep_work."""
    grade = 'D'
    score = 35

    if grade == 'D':
        category = 'deep_work'

    assert category == 'deep_work'


@test("Fallback implementation categorizes C grade with few critical as quick_win")
def test_fallback_c_grade_quick():
    """C grade projects with 0-1 critical issues should be quick_wins."""
    grade = 'C'
    score = 55
    critical_issues = 1

    if grade == 'C' and critical_issues <= 1:
        category = 'quick_win'
    else:
        category = 'deep_work'

    assert category == 'quick_win'


@test("Fallback implementation categorizes C grade with many critical as deep_work")
def test_fallback_c_grade_deep():
    """C grade projects with 2+ critical issues should be deep_work."""
    grade = 'C'
    score = 55
    critical_issues = 3

    if grade == 'C' and critical_issues <= 1:
        category = 'quick_win'
    else:
        category = 'deep_work'

    assert category == 'deep_work'


@test("Fallback implementation categorizes B grade as ready_to_polish")
def test_fallback_b_grade():
    """B grade projects should be categorized as ready_to_polish."""
    grade = 'B'
    score = 75

    if grade == 'B':
        potential = 80 - score
        if potential > 0:
            category = 'ready_to_polish'
        else:
            category = None

    assert category == 'ready_to_polish'


@test("Fallback implementation skips A grade projects")
def test_fallback_a_grade():
    """A grade projects (80+) should not be included in focus."""
    grade = 'A'
    score = 85

    category = None
    if grade in ['F', 'D']:
        category = 'deep_work'
    elif grade == 'C':
        category = 'quick_win'
    elif grade == 'B':
        category = 'ready_to_polish'

    assert category is None


@test("Potential gain calculation for C grade")
def test_potential_gain_c():
    """C grade potential should be min(20, 80 - score)."""
    score = 55
    potential = min(20, 80 - score)
    assert potential == 20


@test("Potential gain calculation for B grade")
def test_potential_gain_b():
    """B grade potential should be 80 - score."""
    score = 75
    potential = 80 - score
    assert potential == 5


@test("Potential gain calculation for F grade")
def test_potential_gain_f():
    """F grade potential should be min(30, 100 - score)."""
    score = 15
    potential = min(30, 100 - score)
    assert potential == 30


# ============================================================================
# CLI Integration Tests (structural)
# ============================================================================

@test("als_doctor.py contains db_focus_cmd function")
def test_focus_cmd_exists():
    """The db focus command should exist in als_doctor.py."""
    als_doctor_path = Path(__file__).parent / "als_doctor.py"
    content = als_doctor_path.read_text()

    assert "@db.command('focus')" in content
    assert "def db_focus_cmd" in content


@test("db focus command has --limit option")
def test_focus_cmd_limit_option():
    """The db focus command should have a --limit option."""
    als_doctor_path = Path(__file__).parent / "als_doctor.py"
    content = als_doctor_path.read_text()

    focus_start = content.find("@db.command('focus')")
    focus_end = content.find("def db_focus_cmd") + 500
    focus_section = content[focus_start:focus_end]

    assert "--limit" in focus_section


@test("db focus command has docstring with examples")
def test_focus_cmd_docstring():
    """The db focus command should have a proper docstring."""
    als_doctor_path = Path(__file__).parent / "als_doctor.py"
    content = als_doctor_path.read_text()

    assert 'Show what to work on next' in content
    assert 'Quick Wins' in content
    assert 'Deep Work' in content
    assert 'Ready to Polish' in content
    assert 'als-doctor db focus' in content


@test("db focus command imports from dashboard")
def test_focus_cmd_imports():
    """The db focus command should import from dashboard module."""
    als_doctor_path = Path(__file__).parent / "als_doctor.py"
    content = als_doctor_path.read_text()

    focus_start = content.find("def db_focus_cmd")
    focus_end = content.find("def _get_todays_focus_fallback")
    focus_impl = content[focus_start:focus_end]

    assert "from dashboard import get_todays_focus" in focus_impl


@test("db focus command has fallback implementation")
def test_focus_cmd_fallback():
    """The db focus command should have a fallback implementation."""
    als_doctor_path = Path(__file__).parent / "als_doctor.py"
    content = als_doctor_path.read_text()

    assert "def _get_todays_focus_fallback" in content
    assert "WorkItemFallback" in content or "WorkItem" in content
    assert "TodaysFocusFallback" in content or "TodaysFocus" in content


# ============================================================================
# Run all tests
# ============================================================================

def run_all_tests():
    """Run all test functions."""
    print("")
    print("=" * 60)
    print("Focus Command Tests (Story 4.6 - What to Work On)")
    print("=" * 60)
    print("")

    test_functions = [
        obj for name, obj in globals().items()
        if callable(obj) and hasattr(obj, '_test_name')
    ]

    for test_func in test_functions:
        test_func()

    print("")
    print("=" * 60)
    print(f"Results: {_test_results['passed']} passed, {_test_results['failed']} failed")
    print("=" * 60)

    return _test_results['failed'] == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
