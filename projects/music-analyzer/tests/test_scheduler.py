#!/usr/bin/env python3
"""
Tests for Scheduled Batch Scan functionality (Story 3.3)

Tests the scheduler module for managing scheduled scans,
including schedule CRUD operations, cron expression generation,
and due schedule detection.
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


def test_schedule_dataclass():
    """Test Schedule dataclass."""
    from scheduler import Schedule

    schedule = Schedule(
        id="schedule_test123",
        name="Test Schedule",
        folder_path="/path/to/folder",
        frequency="daily"
    )

    assert schedule.id == "schedule_test123"
    assert schedule.name == "Test Schedule"
    assert schedule.folder_path == "/path/to/folder"
    assert schedule.frequency == "daily"
    assert schedule.enabled is True
    assert schedule.last_run_at is None
    assert schedule.last_run_status is None

    print("  ✓ Schedule dataclass")


def test_schedule_to_dict():
    """Test Schedule.to_dict() method."""
    from scheduler import Schedule

    schedule = Schedule(
        id="schedule_test123",
        name="Test Schedule",
        folder_path="/path/to/folder",
        frequency="daily",
        run_at_time="03:00",
        run_on_day=0
    )

    data = schedule.to_dict()

    assert data['id'] == "schedule_test123"
    assert data['name'] == "Test Schedule"
    assert data['frequency'] == "daily"
    assert data['run_at_time'] == "03:00"
    assert data['run_on_day'] == 0

    print("  ✓ Schedule to_dict")


def test_schedule_from_dict():
    """Test Schedule.from_dict() method."""
    from scheduler import Schedule

    data = {
        'id': 'schedule_abc',
        'name': 'My Schedule',
        'folder_path': '/test/path',
        'frequency': 'weekly',
        'enabled': False,
        'run_at_time': '09:30',
        'run_on_day': 5
    }

    schedule = Schedule.from_dict(data)

    assert schedule.id == 'schedule_abc'
    assert schedule.name == 'My Schedule'
    assert schedule.frequency == 'weekly'
    assert schedule.enabled is False
    assert schedule.run_at_time == '09:30'
    assert schedule.run_on_day == 5

    print("  ✓ Schedule from_dict")


def test_schedule_run_result_dataclass():
    """Test ScheduleRunResult dataclass."""
    from scheduler import ScheduleRunResult

    # Success result
    result = ScheduleRunResult(
        schedule_id="schedule_123",
        schedule_name="Test",
        success=True,
        files_scanned=10,
        files_failed=2,
        duration_seconds=5.5
    )

    assert result.success is True
    assert result.files_scanned == 10
    assert "10 files" in result.summary
    assert "5.5s" in result.summary

    # Failure result
    fail_result = ScheduleRunResult(
        schedule_id="schedule_123",
        schedule_name="Test",
        success=False,
        error_message="Test error"
    )

    assert fail_result.success is False
    assert "Test error" in fail_result.summary

    print("  ✓ ScheduleRunResult dataclass")


def test_schedule_index_dataclass():
    """Test ScheduleIndex dataclass."""
    from scheduler import ScheduleIndex, Schedule

    index = ScheduleIndex()
    assert index.version == 1
    assert len(index.schedules) == 0

    # Add a schedule
    index.schedules.append(Schedule(
        id="test",
        name="Test",
        folder_path="/path",
        frequency="daily"
    ))

    # to_dict
    data = index.to_dict()
    assert data['version'] == 1
    assert len(data['schedules']) == 1

    # from_dict
    index2 = ScheduleIndex.from_dict(data)
    assert len(index2.schedules) == 1
    assert index2.schedules[0].id == "test"

    print("  ✓ ScheduleIndex dataclass")


def test_load_schedules_creates_file():
    """Test that loading schedules creates file if missing."""
    from scheduler import _load_schedules_index, _get_schedules_path

    with tempfile.TemporaryDirectory() as tmpdir:
        schedules_path = Path(tmpdir) / "schedules.json"

        # File shouldn't exist yet
        assert not schedules_path.exists()

        # Load should create it
        index = _load_schedules_index(schedules_path)

        assert schedules_path.exists()
        assert len(index.schedules) == 0

    print("  ✓ Load schedules creates file")


def test_save_and_load_schedules():
    """Test saving and loading schedules."""
    from scheduler import (
        _load_schedules_index, _save_schedules_index,
        ScheduleIndex, Schedule
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        schedules_path = Path(tmpdir) / "schedules.json"

        # Create index with schedule
        index = ScheduleIndex()
        index.schedules.append(Schedule(
            id="schedule_save_test",
            name="Save Test",
            folder_path="/test/path",
            frequency="weekly"
        ))

        # Save
        assert _save_schedules_index(index, schedules_path)

        # Load and verify
        loaded = _load_schedules_index(schedules_path)
        assert len(loaded.schedules) == 1
        assert loaded.schedules[0].id == "schedule_save_test"
        assert loaded.schedules[0].name == "Save Test"

    print("  ✓ Save and load schedules")


def test_list_schedules_empty():
    """Test listing schedules when empty."""
    from scheduler import list_schedules

    with tempfile.TemporaryDirectory() as tmpdir:
        schedules_path = Path(tmpdir) / "schedules.json"

        schedules, msg = list_schedules(schedules_path)

        assert len(schedules) == 0
        assert "No schedules" in msg

    print("  ✓ List schedules empty")


def test_list_schedules_with_data():
    """Test listing schedules with data."""
    from scheduler import (
        _save_schedules_index, ScheduleIndex, Schedule,
        list_schedules
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        schedules_path = Path(tmpdir) / "schedules.json"

        # Create schedules
        index = ScheduleIndex()
        index.schedules.append(Schedule(
            id="sched1", name="First", folder_path="/path1", frequency="daily"
        ))
        index.schedules.append(Schedule(
            id="sched2", name="Second", folder_path="/path2", frequency="weekly"
        ))
        _save_schedules_index(index, schedules_path)

        # List
        schedules, msg = list_schedules(schedules_path)

        assert len(schedules) == 2
        assert "2 schedule(s)" in msg

    print("  ✓ List schedules with data")


def test_add_schedule_success():
    """Test adding a schedule successfully."""
    from scheduler import add_schedule

    with tempfile.TemporaryDirectory() as tmpdir:
        schedules_path = Path(tmpdir) / "schedules.json"
        folder_path = tmpdir  # Use tmpdir as folder to scan

        schedule, msg = add_schedule(
            folder_path=folder_path,
            frequency="daily",
            name="Test Schedule",
            schedules_path=schedules_path
        )

        assert schedule is not None
        assert schedule.name == "Test Schedule"
        assert schedule.frequency == "daily"
        assert schedule.folder_path == str(Path(folder_path).absolute())
        assert "Created schedule" in msg

    print("  ✓ Add schedule success")


def test_add_schedule_folder_not_exists():
    """Test adding schedule with non-existent folder."""
    from scheduler import add_schedule

    with tempfile.TemporaryDirectory() as tmpdir:
        schedules_path = Path(tmpdir) / "schedules.json"

        schedule, msg = add_schedule(
            folder_path="/nonexistent/path",
            frequency="daily",
            schedules_path=schedules_path
        )

        assert schedule is None
        assert "does not exist" in msg

    print("  ✓ Add schedule folder not exists")


def test_add_schedule_invalid_frequency():
    """Test adding schedule with invalid frequency."""
    from scheduler import add_schedule

    with tempfile.TemporaryDirectory() as tmpdir:
        schedules_path = Path(tmpdir) / "schedules.json"

        schedule, msg = add_schedule(
            folder_path=tmpdir,
            frequency="every5minutes",
            schedules_path=schedules_path
        )

        assert schedule is None
        assert "Invalid frequency" in msg

    print("  ✓ Add schedule invalid frequency")


def test_add_schedule_invalid_time_format():
    """Test adding schedule with invalid time format."""
    from scheduler import add_schedule

    with tempfile.TemporaryDirectory() as tmpdir:
        schedules_path = Path(tmpdir) / "schedules.json"

        schedule, msg = add_schedule(
            folder_path=tmpdir,
            frequency="daily",
            run_at_time="3pm",  # Invalid format
            schedules_path=schedules_path
        )

        assert schedule is None
        assert "Invalid time format" in msg

    print("  ✓ Add schedule invalid time format")


def test_add_schedule_duplicate_name():
    """Test adding schedule with duplicate name."""
    from scheduler import add_schedule

    with tempfile.TemporaryDirectory() as tmpdir:
        schedules_path = Path(tmpdir) / "schedules.json"

        # Add first schedule
        schedule1, _ = add_schedule(
            folder_path=tmpdir,
            frequency="daily",
            name="MySchedule",
            schedules_path=schedules_path
        )
        assert schedule1 is not None

        # Try to add duplicate
        schedule2, msg = add_schedule(
            folder_path=tmpdir,
            frequency="weekly",
            name="MySchedule",
            schedules_path=schedules_path
        )

        assert schedule2 is None
        assert "already exists" in msg

    print("  ✓ Add schedule duplicate name")


def test_get_schedule_by_id():
    """Test getting schedule by ID."""
    from scheduler import add_schedule, get_schedule_by_id

    with tempfile.TemporaryDirectory() as tmpdir:
        schedules_path = Path(tmpdir) / "schedules.json"

        # Add schedule
        schedule, _ = add_schedule(
            folder_path=tmpdir,
            frequency="daily",
            name="FindMe",
            schedules_path=schedules_path
        )

        # Find by ID
        found, msg = get_schedule_by_id(schedule.id, schedules_path)
        assert found is not None
        assert found.name == "FindMe"

        # Find by name
        found2, msg2 = get_schedule_by_id("FindMe", schedules_path)
        assert found2 is not None
        assert found2.id == schedule.id

        # Find by partial name (case-insensitive)
        found3, msg3 = get_schedule_by_id("findme", schedules_path)
        assert found3 is not None

    print("  ✓ Get schedule by ID")


def test_get_schedule_not_found():
    """Test getting non-existent schedule."""
    from scheduler import get_schedule_by_id

    with tempfile.TemporaryDirectory() as tmpdir:
        schedules_path = Path(tmpdir) / "schedules.json"

        found, msg = get_schedule_by_id("nonexistent", schedules_path)

        assert found is None
        assert "not found" in msg

    print("  ✓ Get schedule not found")


def test_remove_schedule():
    """Test removing a schedule."""
    from scheduler import add_schedule, remove_schedule, list_schedules

    with tempfile.TemporaryDirectory() as tmpdir:
        schedules_path = Path(tmpdir) / "schedules.json"

        # Add schedule
        schedule, _ = add_schedule(
            folder_path=tmpdir,
            frequency="daily",
            name="ToRemove",
            schedules_path=schedules_path
        )

        # Verify it exists
        schedules, _ = list_schedules(schedules_path)
        assert len(schedules) == 1

        # Remove it
        success, msg = remove_schedule(schedule.id, schedules_path)
        assert success is True
        assert "Removed schedule" in msg

        # Verify it's gone
        schedules2, _ = list_schedules(schedules_path)
        assert len(schedules2) == 0

    print("  ✓ Remove schedule")


def test_remove_schedule_not_found():
    """Test removing non-existent schedule."""
    from scheduler import remove_schedule

    with tempfile.TemporaryDirectory() as tmpdir:
        schedules_path = Path(tmpdir) / "schedules.json"

        success, msg = remove_schedule("nonexistent", schedules_path)

        assert success is False
        assert "not found" in msg

    print("  ✓ Remove schedule not found")


def test_enable_disable_schedule():
    """Test enabling and disabling a schedule."""
    from scheduler import add_schedule, enable_schedule, get_schedule_by_id

    with tempfile.TemporaryDirectory() as tmpdir:
        schedules_path = Path(tmpdir) / "schedules.json"

        # Add schedule (enabled by default)
        schedule, _ = add_schedule(
            folder_path=tmpdir,
            frequency="daily",
            name="ToggleMe",
            schedules_path=schedules_path
        )
        assert schedule.enabled is True

        # Disable
        success, msg = enable_schedule(schedule.id, enabled=False, schedules_path=schedules_path)
        assert success is True
        assert "disabled" in msg

        # Verify
        found, _ = get_schedule_by_id(schedule.id, schedules_path)
        assert found.enabled is False

        # Enable
        success2, msg2 = enable_schedule(schedule.id, enabled=True, schedules_path=schedules_path)
        assert success2 is True
        assert "enabled" in msg2

        # Verify
        found2, _ = get_schedule_by_id(schedule.id, schedules_path)
        assert found2.enabled is True

    print("  ✓ Enable/disable schedule")


def test_get_cron_expression_hourly():
    """Test cron expression for hourly schedule."""
    from scheduler import Schedule, get_cron_expression

    schedule = Schedule(
        id="test",
        name="Test",
        folder_path="/path",
        frequency="hourly"
    )

    cron = get_cron_expression(schedule)
    # Should be "0 * * * *" (at minute 0 every hour)
    assert cron == "0 * * * *"

    print("  ✓ Cron expression hourly")


def test_get_cron_expression_daily():
    """Test cron expression for daily schedule."""
    from scheduler import Schedule, get_cron_expression

    schedule = Schedule(
        id="test",
        name="Test",
        folder_path="/path",
        frequency="daily",
        run_at_time="03:30"
    )

    cron = get_cron_expression(schedule)
    # Should be "30 3 * * *" (at 3:30 AM every day)
    assert cron == "30 3 * * *"

    print("  ✓ Cron expression daily")


def test_get_cron_expression_weekly():
    """Test cron expression for weekly schedule."""
    from scheduler import Schedule, get_cron_expression

    schedule = Schedule(
        id="test",
        name="Test",
        folder_path="/path",
        frequency="weekly",
        run_at_time="09:00",
        run_on_day=1  # Tuesday
    )

    cron = get_cron_expression(schedule)
    # Should be "0 9 * * 1" (at 9:00 AM on Tuesday)
    assert cron == "0 9 * * 1"

    print("  ✓ Cron expression weekly")


def test_check_due_schedules_never_run():
    """Test that schedules that never ran are due."""
    from scheduler import add_schedule, check_due_schedules

    with tempfile.TemporaryDirectory() as tmpdir:
        schedules_path = Path(tmpdir) / "schedules.json"

        # Add schedule (never run)
        schedule, _ = add_schedule(
            folder_path=tmpdir,
            frequency="daily",
            name="NeverRun",
            schedules_path=schedules_path
        )

        due = check_due_schedules(schedules_path)

        assert len(due) == 1
        assert due[0].id == schedule.id

    print("  ✓ Check due schedules - never run")


def test_check_due_schedules_disabled():
    """Test that disabled schedules are not due."""
    from scheduler import add_schedule, enable_schedule, check_due_schedules

    with tempfile.TemporaryDirectory() as tmpdir:
        schedules_path = Path(tmpdir) / "schedules.json"

        # Add and disable schedule
        schedule, _ = add_schedule(
            folder_path=tmpdir,
            frequency="daily",
            name="Disabled",
            schedules_path=schedules_path
        )
        enable_schedule(schedule.id, enabled=False, schedules_path=schedules_path)

        due = check_due_schedules(schedules_path)

        assert len(due) == 0

    print("  ✓ Check due schedules - disabled")


def test_check_due_schedules_hourly():
    """Test hourly schedule due detection."""
    from scheduler import (
        _save_schedules_index, ScheduleIndex, Schedule,
        check_due_schedules
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        schedules_path = Path(tmpdir) / "schedules.json"

        # Create schedule that ran 2 hours ago
        index = ScheduleIndex()
        two_hours_ago = (datetime.now() - timedelta(hours=2)).isoformat()
        index.schedules.append(Schedule(
            id="hourly_test",
            name="Hourly Test",
            folder_path=tmpdir,
            frequency="hourly",
            last_run_at=two_hours_ago
        ))
        _save_schedules_index(index, schedules_path)

        due = check_due_schedules(schedules_path)

        assert len(due) == 1  # Should be due (ran 2 hours ago)

    print("  ✓ Check due schedules - hourly")


def test_check_due_schedules_not_due():
    """Test schedule that is not due yet."""
    from scheduler import (
        _save_schedules_index, ScheduleIndex, Schedule,
        check_due_schedules
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        schedules_path = Path(tmpdir) / "schedules.json"

        # Create daily schedule that ran 1 hour ago
        index = ScheduleIndex()
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        index.schedules.append(Schedule(
            id="daily_test",
            name="Daily Test",
            folder_path=tmpdir,
            frequency="daily",
            last_run_at=one_hour_ago
        ))
        _save_schedules_index(index, schedules_path)

        due = check_due_schedules(schedules_path)

        assert len(due) == 0  # Should NOT be due (ran 1 hour ago, daily frequency)

    print("  ✓ Check due schedules - not due")


def test_generate_schedule_id():
    """Test schedule ID generation."""
    from scheduler import _generate_schedule_id

    id1 = _generate_schedule_id()
    id2 = _generate_schedule_id()

    assert id1.startswith("schedule_")
    assert id2.startswith("schedule_")
    assert id1 != id2  # Should be unique

    print("  ✓ Generate schedule ID")


def test_log_run():
    """Test logging run results."""
    from scheduler import _log_run, ScheduleRunResult

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "runs.log"

        result = ScheduleRunResult(
            schedule_id="test_id",
            schedule_name="Test Schedule",
            success=True,
            files_scanned=5,
            duration_seconds=2.5
        )

        _log_run(result, log_path)

        # Check log file
        assert log_path.exists()
        content = log_path.read_text()
        assert "Test Schedule" in content
        assert "5 files" in content

    print("  ✓ Log run")


def test_schedule_with_time_options():
    """Test schedule with all time options."""
    from scheduler import add_schedule, get_schedule_by_id

    with tempfile.TemporaryDirectory() as tmpdir:
        schedules_path = Path(tmpdir) / "schedules.json"

        schedule, _ = add_schedule(
            folder_path=tmpdir,
            frequency="weekly",
            name="Full Options",
            run_at_time="14:30",
            run_on_day=3,  # Thursday
            schedules_path=schedules_path
        )

        assert schedule is not None
        assert schedule.run_at_time == "14:30"
        assert schedule.run_on_day == 3

        # Verify persistence
        found, _ = get_schedule_by_id(schedule.id, schedules_path)
        assert found.run_at_time == "14:30"
        assert found.run_on_day == 3

    print("  ✓ Schedule with time options")


def test_schedule_folder_missing_on_check():
    """Test that schedules with missing folders are skipped."""
    from scheduler import (
        _save_schedules_index, ScheduleIndex, Schedule,
        check_due_schedules
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        schedules_path = Path(tmpdir) / "schedules.json"

        # Create schedule pointing to non-existent folder
        index = ScheduleIndex()
        index.schedules.append(Schedule(
            id="missing_folder",
            name="Missing Folder",
            folder_path="/nonexistent/path/that/doesnt/exist",
            frequency="daily"
        ))
        _save_schedules_index(index, schedules_path)

        due = check_due_schedules(schedules_path)

        assert len(due) == 0  # Skipped because folder doesn't exist

    print("  ✓ Schedule folder missing on check")


def run_all_tests():
    """Run all scheduler tests."""
    print("=" * 60)
    print("Scheduler Tests (Story 3.3)")
    print("=" * 60)
    print("")

    tests = [
        test_schedule_dataclass,
        test_schedule_to_dict,
        test_schedule_from_dict,
        test_schedule_run_result_dataclass,
        test_schedule_index_dataclass,
        test_load_schedules_creates_file,
        test_save_and_load_schedules,
        test_list_schedules_empty,
        test_list_schedules_with_data,
        test_add_schedule_success,
        test_add_schedule_folder_not_exists,
        test_add_schedule_invalid_frequency,
        test_add_schedule_invalid_time_format,
        test_add_schedule_duplicate_name,
        test_get_schedule_by_id,
        test_get_schedule_not_found,
        test_remove_schedule,
        test_remove_schedule_not_found,
        test_enable_disable_schedule,
        test_get_cron_expression_hourly,
        test_get_cron_expression_daily,
        test_get_cron_expression_weekly,
        test_check_due_schedules_never_run,
        test_check_due_schedules_disabled,
        test_check_due_schedules_hourly,
        test_check_due_schedules_not_due,
        test_generate_schedule_id,
        test_log_run,
        test_schedule_with_time_options,
        test_schedule_folder_missing_on_check,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1

    print("")
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
