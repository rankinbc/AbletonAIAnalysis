"""
Tests for CLI Formatter (Story 4.1)

Tests the cli_formatter module for colored output and formatting.
"""

import os
import sys
from pathlib import Path
from io import StringIO

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from cli_formatter import (
    CLIFormatter, FormatterConfig, get_formatter, reset_formatter,
    GRADE_COLORS, SEVERITY_COLORS, TREND_COLORS, TREND_SYMBOLS,
    print_success, print_error, print_warning,
    format_grade, format_severity, format_trend, format_delta
)


def run_tests():
    """Run all formatter tests."""
    print("=" * 60)
    print("CLI Formatter Tests (Story 4.1)")
    print("=" * 60)
    print()

    passed = 0
    failed = 0

    # Test 1: Color scheme constants
    print("  Testing color scheme constants...", end="")
    try:
        assert 'A' in GRADE_COLORS
        assert 'B' in GRADE_COLORS
        assert 'C' in GRADE_COLORS
        assert 'D' in GRADE_COLORS
        assert 'F' in GRADE_COLORS
        assert GRADE_COLORS['A'] == 'green'
        assert GRADE_COLORS['F'] == 'red'
        print(" PASS")
        passed += 1
    except AssertionError as e:
        print(f" FAIL: {e}")
        failed += 1

    # Test 2: Severity colors
    print("  Testing severity colors...", end="")
    try:
        assert 'critical' in SEVERITY_COLORS
        assert 'warning' in SEVERITY_COLORS
        assert 'suggestion' in SEVERITY_COLORS
        assert SEVERITY_COLORS['critical'] == 'red'
        assert SEVERITY_COLORS['warning'] == 'yellow'
        assert SEVERITY_COLORS['suggestion'] == 'cyan'
        print(" PASS")
        passed += 1
    except AssertionError as e:
        print(f" FAIL: {e}")
        failed += 1

    # Test 3: Trend colors and symbols
    print("  Testing trend colors and symbols...", end="")
    try:
        assert 'up' in TREND_COLORS
        assert 'down' in TREND_COLORS
        assert 'stable' in TREND_COLORS
        assert 'new' in TREND_COLORS
        assert TREND_SYMBOLS['up'] == '[up]'
        assert TREND_SYMBOLS['down'] == '[down]'
        print(" PASS")
        passed += 1
    except AssertionError as e:
        print(f" FAIL: {e}")
        failed += 1

    # Test 4: Formatter initialization with no_color=True
    print("  Testing formatter with no_color=True...", end="")
    try:
        reset_formatter()
        config = FormatterConfig(no_color=True)
        fmt = CLIFormatter(config)
        assert not fmt.use_rich, "Formatter should not use rich when no_color=True"
        print(" PASS")
        passed += 1
    except AssertionError as e:
        print(f" FAIL: {e}")
        failed += 1

    # Test 5: Environment variable NO_COLOR
    print("  Testing NO_COLOR environment variable...", end="")
    try:
        reset_formatter()
        os.environ['NO_COLOR'] = '1'
        config = FormatterConfig()
        fmt = CLIFormatter(config)
        assert not fmt.use_rich, "Formatter should not use rich when NO_COLOR=1"
        del os.environ['NO_COLOR']
        print(" PASS")
        passed += 1
    except AssertionError as e:
        print(f" FAIL: {e}")
        failed += 1
    finally:
        if 'NO_COLOR' in os.environ:
            del os.environ['NO_COLOR']

    # Test 6: Grade text formatting (no color mode)
    print("  Testing grade text formatting (no color)...", end="")
    try:
        reset_formatter()
        config = FormatterConfig(no_color=True)
        fmt = CLIFormatter(config)
        assert fmt.grade_text('A') == '[A]'
        assert fmt.grade_text('B') == '[B]'
        assert fmt.grade_text('F', include_brackets=False) == 'F'
        print(" PASS")
        passed += 1
    except AssertionError as e:
        print(f" FAIL: {e}")
        failed += 1

    # Test 7: Grade with score formatting
    print("  Testing grade with score formatting...", end="")
    try:
        reset_formatter()
        config = FormatterConfig(no_color=True)
        fmt = CLIFormatter(config)
        result = fmt.grade_with_score(85, 'A')
        assert '85' in result
        assert '[A]' in result
        print(" PASS")
        passed += 1
    except AssertionError as e:
        print(f" FAIL: {e}")
        failed += 1

    # Test 8: Trend text formatting
    print("  Testing trend text formatting...", end="")
    try:
        reset_formatter()
        config = FormatterConfig(no_color=True)
        fmt = CLIFormatter(config)
        assert fmt.trend_text('up') == '[up]'
        assert fmt.trend_text('down') == '[down]'
        assert fmt.trend_text('stable') == '[stable]'
        assert fmt.trend_text('new') == '[new]'
        print(" PASS")
        passed += 1
    except AssertionError as e:
        print(f" FAIL: {e}")
        failed += 1

    # Test 9: Delta text formatting
    print("  Testing delta text formatting...", end="")
    try:
        reset_formatter()
        config = FormatterConfig(no_color=True)
        fmt = CLIFormatter(config)
        assert fmt.delta_text(10) == '+10'
        assert fmt.delta_text(-5) == '-5'
        assert fmt.delta_text(0) == '0'
        print(" PASS")
        passed += 1
    except AssertionError as e:
        print(f" FAIL: {e}")
        failed += 1

    # Test 10: Disable and enable colors
    print("  Testing disable and enable colors...", end="")
    try:
        reset_formatter()
        fmt = get_formatter(no_color=False)
        # When rich is available, use_rich may be True
        # When disabled, it should be False
        fmt.disable_colors()
        assert not fmt.use_rich
        print(" PASS")
        passed += 1
    except AssertionError as e:
        print(f" FAIL: {e}")
        failed += 1

    # Test 11: TableBuilder in plain text mode
    print("  Testing TableBuilder in plain text mode...", end="")
    try:
        reset_formatter()
        config = FormatterConfig(no_color=True)
        fmt = CLIFormatter(config)
        table = fmt.create_table(title="Test Table")
        table.add_column("Name", justify="left")
        table.add_column("Score", justify="right")
        table.add_row("Song 1", "85")
        table.add_row("Song 2", "90")
        # Should not raise any errors
        # Note: render() prints to stdout, so just ensure no exceptions
        print(" PASS")
        passed += 1
    except Exception as e:
        print(f" FAIL: {e}")
        failed += 1

    # Test 12: Global formatter singleton
    print("  Testing global formatter singleton...", end="")
    try:
        reset_formatter()
        fmt1 = get_formatter(no_color=True)
        fmt2 = get_formatter()
        assert fmt1 is fmt2, "Should return same formatter instance"
        print(" PASS")
        passed += 1
    except AssertionError as e:
        print(f" FAIL: {e}")
        failed += 1

    # Test 13: Grade bar generation
    print("  Testing grade bar generation...", end="")
    try:
        reset_formatter()
        config = FormatterConfig(no_color=True)
        fmt = CLIFormatter(config)
        bar = fmt.grade_bar('A', 10, 100, max_width=20)
        assert len(bar) == 2  # 10% of 20 = 2 chars
        bar_empty = fmt.grade_bar('A', 0, 100, max_width=20)
        assert bar_empty == ''
        print(" PASS")
        passed += 1
    except AssertionError as e:
        print(f" FAIL: {e}")
        failed += 1

    # Test 14: Severity text formatting
    print("  Testing severity text formatting...", end="")
    try:
        reset_formatter()
        config = FormatterConfig(no_color=True)
        fmt = CLIFormatter(config)
        result = fmt.severity_text('critical', 'Error message')
        assert result == 'Error message'
        print(" PASS")
        passed += 1
    except AssertionError as e:
        print(f" FAIL: {e}")
        failed += 1

    # Test 15: Convenience functions
    print("  Testing convenience functions...", end="")
    try:
        reset_formatter()
        # These should not raise errors
        grade = format_grade('A')
        assert '[A]' in grade
        trend = format_trend('up')
        assert '[up]' in trend
        delta = format_delta(5)
        assert '+5' in delta
        print(" PASS")
        passed += 1
    except Exception as e:
        print(f" FAIL: {e}")
        failed += 1

    # Test 16: ALS_DOCTOR_NO_COLOR environment variable
    print("  Testing ALS_DOCTOR_NO_COLOR env variable...", end="")
    try:
        reset_formatter()
        os.environ['ALS_DOCTOR_NO_COLOR'] = 'true'
        config = FormatterConfig()
        fmt = CLIFormatter(config)
        assert not fmt.use_rich, "Formatter should not use rich when ALS_DOCTOR_NO_COLOR=true"
        del os.environ['ALS_DOCTOR_NO_COLOR']
        print(" PASS")
        passed += 1
    except AssertionError as e:
        print(f" FAIL: {e}")
        failed += 1
    finally:
        if 'ALS_DOCTOR_NO_COLOR' in os.environ:
            del os.environ['ALS_DOCTOR_NO_COLOR']

    # Test 17: Progress bar generation
    print("  Testing progress bar generation...", end="")
    try:
        reset_formatter()
        config = FormatterConfig(no_color=True)
        fmt = CLIFormatter(config)
        bar = fmt.progress_bar(50, 100, width=10)
        assert '=' in bar
        bar_empty = fmt.progress_bar(0, 100, width=10)
        assert '=' not in bar_empty or bar_empty.count('=') == 0
        print(" PASS")
        passed += 1
    except AssertionError as e:
        print(f" FAIL: {e}")
        failed += 1

    # Test 18: FormatterConfig defaults
    print("  Testing FormatterConfig defaults...", end="")
    try:
        config = FormatterConfig()
        assert config.no_color == False
        assert config.force_terminal == False
        assert config.width is None
        print(" PASS")
        passed += 1
    except AssertionError as e:
        print(f" FAIL: {e}")
        failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
