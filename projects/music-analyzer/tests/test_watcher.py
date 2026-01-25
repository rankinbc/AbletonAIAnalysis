#!/usr/bin/env python3
"""
Tests for Watch Folder functionality (Story 3.1)

Tests the FolderWatcher, DebouncedQueue, and related components
for monitoring .als files and triggering analysis.
"""

import os
import sys
import time
import tempfile
import threading
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


def test_watch_event_dataclass():
    """Test WatchEvent dataclass."""
    from watcher import WatchEvent

    event = WatchEvent(
        file_path="/path/to/project/test.als",
        event_type="modified"
    )

    assert event.file_path == "/path/to/project/test.als"
    assert event.event_type == "modified"
    assert event.als_filename == "test.als"
    assert event.project_folder == "/path/to/project"
    assert isinstance(event.timestamp, datetime)

    print("  ✓ WatchEvent dataclass")


def test_watch_result_dataclass():
    """Test WatchResult dataclass."""
    from watcher import WatchResult

    # Success result
    result = WatchResult(
        file_path="/path/to/test.als",
        success=True,
        health_score=85,
        grade="A",
        total_issues=3
    )

    assert result.success is True
    assert result.health_score == 85
    assert result.grade == "A"
    assert result.error_message is None

    # Failure result
    fail_result = WatchResult(
        file_path="/path/to/test.als",
        success=False,
        error_message="File not found"
    )

    assert fail_result.success is False
    assert fail_result.error_message == "File not found"
    assert fail_result.health_score is None

    print("  ✓ WatchResult dataclass")


def test_watch_stats_dataclass():
    """Test WatchStats dataclass."""
    from watcher import WatchStats

    stats = WatchStats(
        started_at=datetime.now() - timedelta(minutes=5),
        folder_path="/test/folder"
    )

    # Check defaults
    assert stats.files_analyzed == 0
    assert stats.files_failed == 0
    assert stats.total_events == 0
    assert stats.last_event_at is None
    assert len(stats.results) == 0

    # Check uptime calculation
    assert stats.uptime_seconds >= 300  # At least 5 minutes
    assert "5m" in stats.uptime_formatted or "4m" in stats.uptime_formatted  # Approximately 5 minutes

    print("  ✓ WatchStats dataclass")


def test_is_backup_folder():
    """Test backup folder detection."""
    from watcher import is_backup_folder

    # Should be detected as backup
    assert is_backup_folder("/path/to/Backup/file.als") is True
    assert is_backup_folder("/path/to/backup/file.als") is True
    assert is_backup_folder("/path/to/BACKUP/file.als") is True
    assert is_backup_folder("C:\\Projects\\Backup\\test.als") is True
    assert is_backup_folder("/project/Ableton Project Info/file.als") is True

    # Should NOT be detected as backup
    assert is_backup_folder("/path/to/project/file.als") is False
    assert is_backup_folder("/path/to/my_backup_song/file.als") is False  # backup in name, not folder
    assert is_backup_folder("C:\\Projects\\MySong\\test.als") is False

    print("  ✓ is_backup_folder function")


def test_is_als_file():
    """Test .als file detection."""
    from watcher import is_als_file

    # Should be .als files
    assert is_als_file("/path/to/project.als") is True
    assert is_als_file("C:\\Projects\\song.ALS") is True
    assert is_als_file("test.Als") is True

    # Should NOT be .als files
    assert is_als_file("/path/to/project.wav") is False
    assert is_als_file("/path/to/project.als.bak") is False
    assert is_als_file("/path/to/project") is False
    assert is_als_file("/path/to/project.adg") is False

    print("  ✓ is_als_file function")


def test_debounced_queue_basic():
    """Test basic DebouncedQueue operations."""
    from watcher import DebouncedQueue, WatchEvent

    queue = DebouncedQueue(debounce_seconds=0.1)  # Short for testing

    # Add an event
    event = WatchEvent(file_path="/test/file.als", event_type="modified")
    queue.add_event(event)

    assert queue.pending_count == 1

    # Events shouldn't be ready immediately
    ready = queue.get_ready_events()
    assert len(ready) == 0
    assert queue.pending_count == 1

    # Wait for debounce period
    time.sleep(0.15)

    # Now event should be ready
    ready = queue.get_ready_events()
    assert len(ready) == 1
    assert ready[0].file_path == "/test/file.als"
    assert queue.pending_count == 0

    print("  ✓ DebouncedQueue basic operations")


def test_debounced_queue_coalesces_events():
    """Test that DebouncedQueue coalesces rapid events for same file."""
    from watcher import DebouncedQueue, WatchEvent

    queue = DebouncedQueue(debounce_seconds=0.2)

    # Add multiple events for same file rapidly
    for i in range(5):
        event = WatchEvent(
            file_path="/test/file.als",
            event_type="modified",
            timestamp=datetime.now()
        )
        queue.add_event(event)
        time.sleep(0.02)  # Small delay between events

    # Should still only have 1 pending (coalesced)
    assert queue.pending_count == 1

    # Wait for debounce
    time.sleep(0.25)

    # Should get only 1 event
    ready = queue.get_ready_events()
    assert len(ready) == 1

    print("  ✓ DebouncedQueue coalesces events")


def test_debounced_queue_multiple_files():
    """Test DebouncedQueue with multiple different files."""
    from watcher import DebouncedQueue, WatchEvent

    queue = DebouncedQueue(debounce_seconds=0.1)

    # Add events for different files
    queue.add_event(WatchEvent(file_path="/test/file1.als", event_type="modified"))
    queue.add_event(WatchEvent(file_path="/test/file2.als", event_type="modified"))
    queue.add_event(WatchEvent(file_path="/test/file3.als", event_type="created"))

    assert queue.pending_count == 3

    # Wait for debounce
    time.sleep(0.15)

    # Should get all 3 events
    ready = queue.get_ready_events()
    assert len(ready) == 3
    assert queue.pending_count == 0

    print("  ✓ DebouncedQueue multiple files")


def test_debounced_queue_clear():
    """Test DebouncedQueue clear operation."""
    from watcher import DebouncedQueue, WatchEvent

    queue = DebouncedQueue(debounce_seconds=1.0)

    queue.add_event(WatchEvent(file_path="/test/file1.als", event_type="modified"))
    queue.add_event(WatchEvent(file_path="/test/file2.als", event_type="modified"))

    assert queue.pending_count == 2

    queue.clear()

    assert queue.pending_count == 0

    print("  ✓ DebouncedQueue clear")


def test_event_handler_filters_non_als():
    """Test that event handler filters non-.als files."""
    from watcher import ALSFileEventHandler, WatchEvent

    callback = Mock(return_value=None)
    handler = ALSFileEventHandler(callback=callback, debounce_seconds=0.1, quiet=True)

    # Create mock event for non-.als file
    mock_event = Mock()
    mock_event.is_directory = False
    mock_event.src_path = "/test/file.wav"
    mock_event.event_type = "modified"

    handler.on_any_event(mock_event)

    # Should not add to queue
    assert handler.queue.pending_count == 0

    print("  ✓ Event handler filters non-.als files")


def test_event_handler_filters_backup():
    """Test that event handler filters backup folder files."""
    from watcher import ALSFileEventHandler

    callback = Mock(return_value=None)
    handler = ALSFileEventHandler(callback=callback, debounce_seconds=0.1, quiet=True)

    # Create mock event for backup file
    mock_event = Mock()
    mock_event.is_directory = False
    mock_event.src_path = "/test/Backup/file.als"
    mock_event.event_type = "modified"

    handler.on_any_event(mock_event)

    # Should not add to queue
    assert handler.queue.pending_count == 0

    print("  ✓ Event handler filters backup files")


def test_event_handler_filters_directories():
    """Test that event handler filters directory events."""
    from watcher import ALSFileEventHandler

    callback = Mock(return_value=None)
    handler = ALSFileEventHandler(callback=callback, debounce_seconds=0.1, quiet=True)

    # Create mock directory event
    mock_event = Mock()
    mock_event.is_directory = True
    mock_event.src_path = "/test/folder.als"  # Even if named .als
    mock_event.event_type = "created"

    handler.on_any_event(mock_event)

    # Should not add to queue
    assert handler.queue.pending_count == 0

    print("  ✓ Event handler filters directories")


def test_event_handler_accepts_valid_als():
    """Test that event handler accepts valid .als files."""
    from watcher import ALSFileEventHandler

    callback = Mock(return_value=None)
    handler = ALSFileEventHandler(callback=callback, debounce_seconds=0.1, quiet=True)

    # Create mock event for valid .als file
    mock_event = Mock()
    mock_event.is_directory = False
    mock_event.src_path = "/test/project/song.als"
    mock_event.event_type = "modified"

    handler.on_any_event(mock_event)

    # Should add to queue
    assert handler.queue.pending_count == 1

    print("  ✓ Event handler accepts valid .als files")


def test_event_handler_skips_deleted():
    """Test that event handler skips deleted events."""
    from watcher import ALSFileEventHandler

    callback = Mock(return_value=None)
    handler = ALSFileEventHandler(callback=callback, debounce_seconds=0.1, quiet=True)

    # Create mock delete event
    mock_event = Mock()
    mock_event.is_directory = False
    mock_event.src_path = "/test/project/song.als"
    mock_event.event_type = "deleted"

    handler.on_any_event(mock_event)

    # Should not add to queue (deleted files can't be analyzed)
    assert handler.queue.pending_count == 0

    print("  ✓ Event handler skips deleted events")


def test_event_handler_processes_ready_events():
    """Test that event handler processes ready events."""
    from watcher import ALSFileEventHandler, WatchResult

    # Mock callback that returns a result
    def mock_callback(event):
        return WatchResult(
            file_path=event.file_path,
            success=True,
            health_score=75,
            grade="B",
            total_issues=5
        )

    handler = ALSFileEventHandler(callback=mock_callback, debounce_seconds=0.1, quiet=True)

    # Add an event
    mock_event = Mock()
    mock_event.is_directory = False
    mock_event.src_path = "/test/project/song.als"
    mock_event.event_type = "modified"

    handler.on_any_event(mock_event)

    # Wait for debounce
    time.sleep(0.15)

    # Process events
    results = handler.process_ready_events()

    assert len(results) == 1
    assert results[0].success is True
    assert results[0].health_score == 75

    print("  ✓ Event handler processes ready events")


def test_folder_watcher_init():
    """Test FolderWatcher initialization."""
    from watcher import FolderWatcher

    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = FolderWatcher(
            folder_path=tmpdir,
            debounce_seconds=3.0,
            quiet=True,
            save_to_db=False
        )

        assert watcher.folder_path == str(Path(tmpdir).absolute())
        assert watcher.debounce_seconds == 3.0
        assert watcher.quiet is True
        assert watcher.save_to_db is False
        assert watcher.is_running is False

    print("  ✓ FolderWatcher initialization")


def test_folder_watcher_invalid_path():
    """Test FolderWatcher with invalid path."""
    from watcher import FolderWatcher

    watcher = FolderWatcher(
        folder_path="/nonexistent/path/that/doesnt/exist",
        save_to_db=False,
        quiet=True
    )

    try:
        watcher.start(blocking=False)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "does not exist" in str(e)

    print("  ✓ FolderWatcher invalid path handling")


def test_folder_watcher_not_directory():
    """Test FolderWatcher with file instead of directory."""
    from watcher import FolderWatcher

    with tempfile.NamedTemporaryFile(delete=False) as f:
        temp_file = f.name

    try:
        watcher = FolderWatcher(
            folder_path=temp_file,
            save_to_db=False,
            quiet=True
        )

        try:
            watcher.start(blocking=False)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "not a directory" in str(e)
    finally:
        os.unlink(temp_file)

    print("  ✓ FolderWatcher not directory handling")


def test_folder_watcher_start_stop():
    """Test FolderWatcher start and stop."""
    from watcher import FolderWatcher

    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = FolderWatcher(
            folder_path=tmpdir,
            debounce_seconds=1.0,
            quiet=True,
            save_to_db=False
        )

        # Start in background thread
        def run_watcher():
            watcher.start(blocking=True)

        thread = threading.Thread(target=run_watcher)
        thread.start()

        # Wait for watcher to start
        time.sleep(0.2)
        assert watcher.is_running is True

        # Stop the watcher
        stats = watcher.stop()

        # Wait for thread to finish
        thread.join(timeout=2.0)

        assert watcher.is_running is False
        assert stats is not None
        assert stats.folder_path == tmpdir

    print("  ✓ FolderWatcher start and stop")


def test_folder_watcher_stats_tracking():
    """Test that FolderWatcher tracks statistics."""
    from watcher import FolderWatcher

    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = FolderWatcher(
            folder_path=tmpdir,
            debounce_seconds=1.0,
            quiet=True,
            save_to_db=False
        )

        # Start watcher
        def run_watcher():
            watcher.start(blocking=True)

        thread = threading.Thread(target=run_watcher)
        thread.start()

        time.sleep(0.2)

        # Check initial stats
        assert watcher.stats is not None
        assert watcher.stats.files_analyzed == 0
        assert watcher.stats.total_events == 0

        # Stop and get final stats
        stats = watcher.stop()
        thread.join(timeout=2.0)

        assert stats.uptime_seconds >= 0

    print("  ✓ FolderWatcher stats tracking")


def test_folder_watcher_log_file_creation():
    """Test that FolderWatcher creates log file."""
    from watcher import FolderWatcher

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test_watch.log"

        watcher = FolderWatcher(
            folder_path=tmpdir,
            debounce_seconds=1.0,
            quiet=True,
            save_to_db=False,
            log_path=str(log_path)
        )

        # Start and stop watcher
        def run_watcher():
            watcher.start(blocking=True)

        thread = threading.Thread(target=run_watcher)
        thread.start()
        time.sleep(0.2)
        watcher.stop()
        thread.join(timeout=2.0)

        # Check log file was created
        assert log_path.exists()

        # Check log content
        content = log_path.read_text()
        assert "START" in content
        assert "STOP" in content

    print("  ✓ FolderWatcher log file creation")


def test_watch_stats_uptime_formatting():
    """Test WatchStats uptime formatting for various durations."""
    from watcher import WatchStats

    # Test seconds
    stats = WatchStats(
        started_at=datetime.now() - timedelta(seconds=30),
        folder_path="/test"
    )
    assert "30s" in stats.uptime_formatted or "29s" in stats.uptime_formatted

    # Test minutes
    stats = WatchStats(
        started_at=datetime.now() - timedelta(minutes=3, seconds=30),
        folder_path="/test"
    )
    assert "3m" in stats.uptime_formatted

    # Test hours
    stats = WatchStats(
        started_at=datetime.now() - timedelta(hours=1, minutes=15),
        folder_path="/test"
    )
    assert "1h" in stats.uptime_formatted

    print("  ✓ WatchStats uptime formatting")


def test_folder_watcher_double_start():
    """Test that FolderWatcher raises error on double start."""
    from watcher import FolderWatcher

    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = FolderWatcher(
            folder_path=tmpdir,
            debounce_seconds=1.0,
            quiet=True,
            save_to_db=False
        )

        # Start in background
        def run_watcher():
            watcher.start(blocking=True)

        thread = threading.Thread(target=run_watcher)
        thread.start()
        time.sleep(0.2)

        # Try to start again
        try:
            watcher.start(blocking=False)
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "already running" in str(e)
        finally:
            watcher.stop()
            thread.join(timeout=2.0)

    print("  ✓ FolderWatcher double start handling")


def run_all_tests():
    """Run all watcher tests."""
    print("=" * 60)
    print("Watch Folder Tests (Story 3.1)")
    print("=" * 60)
    print("")

    tests = [
        test_watch_event_dataclass,
        test_watch_result_dataclass,
        test_watch_stats_dataclass,
        test_is_backup_folder,
        test_is_als_file,
        test_debounced_queue_basic,
        test_debounced_queue_coalesces_events,
        test_debounced_queue_multiple_files,
        test_debounced_queue_clear,
        test_event_handler_filters_non_als,
        test_event_handler_filters_backup,
        test_event_handler_filters_directories,
        test_event_handler_accepts_valid_als,
        test_event_handler_skips_deleted,
        test_event_handler_processes_ready_events,
        test_folder_watcher_init,
        test_folder_watcher_invalid_path,
        test_folder_watcher_not_directory,
        test_folder_watcher_start_stop,
        test_folder_watcher_stats_tracking,
        test_folder_watcher_log_file_creation,
        test_watch_stats_uptime_formatting,
        test_folder_watcher_double_start,
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


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
