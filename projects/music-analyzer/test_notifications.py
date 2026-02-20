"""
Tests for Desktop Notifications Module (Story 4.7)

Tests the notification system including:
- Notification configuration
- Rate limiting
- Level filtering
- Notification types
- Manager class
"""

import sys
import time
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))


def test_notification_level_enum():
    """Test NotificationLevel enum values."""
    from notifications import NotificationLevel

    assert NotificationLevel.ALL.value == "all"
    assert NotificationLevel.IMPORTANT.value == "important"
    assert NotificationLevel.CRITICAL.value == "critical"
    print("  ✓ NotificationLevel enum values correct")


def test_notification_type_enum():
    """Test NotificationType enum values."""
    from notifications import NotificationType

    assert NotificationType.ANALYSIS_COMPLETE.value == "analysis_complete"
    assert NotificationType.SCAN_COMPLETE.value == "scan_complete"
    assert NotificationType.HEALTH_ALERT.value == "health_alert"
    assert NotificationType.WATCH_STARTED.value == "watch_started"
    assert NotificationType.WATCH_STOPPED.value == "watch_stopped"
    assert NotificationType.SCHEDULE_COMPLETE.value == "schedule_complete"
    print("  ✓ NotificationType enum values correct")


def test_notification_config_defaults():
    """Test NotificationConfig default values."""
    from notifications import NotificationConfig, NotificationLevel

    config = NotificationConfig()

    assert config.enabled is True
    assert config.level == NotificationLevel.ALL
    assert config.rate_limit_seconds == 30
    assert config.app_name == "ALS Doctor"
    assert config.timeout == 10
    assert config.click_action is None
    print("  ✓ NotificationConfig defaults correct")


def test_notification_config_custom_values():
    """Test NotificationConfig with custom values."""
    from notifications import NotificationConfig, NotificationLevel

    config = NotificationConfig(
        enabled=False,
        level=NotificationLevel.CRITICAL,
        rate_limit_seconds=60,
        app_name="Test App",
        timeout=5,
        click_action="http://localhost:5000"
    )

    assert config.enabled is False
    assert config.level == NotificationLevel.CRITICAL
    assert config.rate_limit_seconds == 60
    assert config.app_name == "Test App"
    assert config.timeout == 5
    assert config.click_action == "http://localhost:5000"
    print("  ✓ NotificationConfig custom values correct")


def test_notification_result_dataclass():
    """Test NotificationResult dataclass."""
    from notifications import NotificationResult, NotificationType

    result = NotificationResult(
        sent=True,
        notification_type=NotificationType.ANALYSIS_COMPLETE,
        title="Test Title",
        message="Test message"
    )

    assert result.sent is True
    assert result.notification_type == NotificationType.ANALYSIS_COMPLETE
    assert result.title == "Test Title"
    assert result.message == "Test message"
    assert result.rate_limited is False
    assert result.filtered is False
    assert result.error is None
    assert result.success is True
    print("  ✓ NotificationResult dataclass works")


def test_notification_result_success_property():
    """Test NotificationResult success property."""
    from notifications import NotificationResult, NotificationType

    # Successful send
    result1 = NotificationResult(
        sent=True,
        notification_type=NotificationType.ANALYSIS_COMPLETE,
        title="Test",
        message="Test"
    )
    assert result1.success is True

    # Not sent (filtered)
    result2 = NotificationResult(
        sent=False,
        notification_type=NotificationType.ANALYSIS_COMPLETE,
        title="Test",
        message="Test",
        filtered=True
    )
    assert result2.success is False

    # Sent but with error
    result3 = NotificationResult(
        sent=True,
        notification_type=NotificationType.ANALYSIS_COMPLETE,
        title="Test",
        message="Test",
        error="Some error"
    )
    assert result3.success is False

    print("  ✓ NotificationResult success property works")


def test_is_plyer_available():
    """Test is_plyer_available function."""
    from notifications import is_plyer_available, PLYER_AVAILABLE

    result = is_plyer_available()
    assert result == PLYER_AVAILABLE
    print("  ✓ is_plyer_available function works")


def test_check_rate_limit_first_call():
    """Test rate limit allows first call."""
    from notifications import _check_rate_limit, _reset_rate_limit

    # Reset for clean test
    _reset_rate_limit()

    result = _check_rate_limit(30)
    assert result is True
    print("  ✓ Rate limit allows first call")


def test_check_rate_limit_blocks_rapid_calls():
    """Test rate limit blocks rapid calls."""
    from notifications import _check_rate_limit, _reset_rate_limit

    # Reset for clean test
    _reset_rate_limit()

    # First call should pass
    result1 = _check_rate_limit(30)
    assert result1 is True

    # Second rapid call should be blocked
    result2 = _check_rate_limit(30)
    assert result2 is False

    print("  ✓ Rate limit blocks rapid calls")


def test_check_rate_limit_allows_after_period():
    """Test rate limit allows call after period expires."""
    from notifications import _check_rate_limit, _reset_rate_limit

    # Reset for clean test
    _reset_rate_limit()

    # Use very short rate limit for testing
    result1 = _check_rate_limit(0.1)
    assert result1 is True

    # Wait for rate limit to expire
    time.sleep(0.15)

    # Should now be allowed
    result2 = _check_rate_limit(0.1)
    assert result2 is True

    print("  ✓ Rate limit allows after period expires")


def test_reset_rate_limit():
    """Test rate limit reset."""
    from notifications import _check_rate_limit, _reset_rate_limit

    # First call
    _reset_rate_limit()
    _check_rate_limit(30)

    # Reset
    _reset_rate_limit()

    # Should be allowed again
    result = _check_rate_limit(30)
    assert result is True
    print("  ✓ Rate limit reset works")


def test_should_notify_all_level():
    """Test should_notify with ALL level."""
    from notifications import _should_notify, NotificationLevel, NotificationType

    # ALL level should allow all types
    assert _should_notify(NotificationType.ANALYSIS_COMPLETE, NotificationLevel.ALL) is True
    assert _should_notify(NotificationType.SCAN_COMPLETE, NotificationLevel.ALL) is True
    assert _should_notify(NotificationType.HEALTH_ALERT, NotificationLevel.ALL) is True
    assert _should_notify(NotificationType.WATCH_STARTED, NotificationLevel.ALL) is True
    print("  ✓ should_notify ALL level works")


def test_should_notify_important_level():
    """Test should_notify with IMPORTANT level."""
    from notifications import _should_notify, NotificationLevel, NotificationType

    # IMPORTANT level should allow analysis/scan complete
    assert _should_notify(NotificationType.ANALYSIS_COMPLETE, NotificationLevel.IMPORTANT) is True
    assert _should_notify(NotificationType.SCAN_COMPLETE, NotificationLevel.IMPORTANT) is True
    assert _should_notify(NotificationType.SCHEDULE_COMPLETE, NotificationLevel.IMPORTANT) is True

    # Health alert only if significant drop
    assert _should_notify(NotificationType.HEALTH_ALERT, NotificationLevel.IMPORTANT, health_delta=-5) is False
    assert _should_notify(NotificationType.HEALTH_ALERT, NotificationLevel.IMPORTANT, health_delta=-15) is True

    # Watch events not important
    assert _should_notify(NotificationType.WATCH_STARTED, NotificationLevel.IMPORTANT) is False

    print("  ✓ should_notify IMPORTANT level works")


def test_should_notify_critical_level():
    """Test should_notify with CRITICAL level."""
    from notifications import _should_notify, NotificationLevel, NotificationType

    # CRITICAL level should only allow major health alerts
    assert _should_notify(NotificationType.ANALYSIS_COMPLETE, NotificationLevel.CRITICAL) is False
    assert _should_notify(NotificationType.SCAN_COMPLETE, NotificationLevel.CRITICAL) is False

    # Health alert only if major drop or very low score
    assert _should_notify(NotificationType.HEALTH_ALERT, NotificationLevel.CRITICAL, health_delta=-10) is False
    assert _should_notify(NotificationType.HEALTH_ALERT, NotificationLevel.CRITICAL, health_delta=-25) is True
    assert _should_notify(NotificationType.HEALTH_ALERT, NotificationLevel.CRITICAL, health_score=30) is True
    assert _should_notify(NotificationType.HEALTH_ALERT, NotificationLevel.CRITICAL, health_score=50) is False

    print("  ✓ should_notify CRITICAL level works")


def test_get_grade_emoji():
    """Test grade emoji function."""
    from notifications import _get_grade_emoji

    assert _get_grade_emoji('A') == '🏆'
    assert _get_grade_emoji('B') == '👍'
    assert _get_grade_emoji('C') == '📊'
    assert _get_grade_emoji('D') == '⚠️'
    assert _get_grade_emoji('F') == '❌'
    assert _get_grade_emoji('X') == '📋'  # Unknown grade
    print("  ✓ get_grade_emoji works")


def test_send_notification_disabled():
    """Test send_notification when disabled."""
    from notifications import (
        send_notification, NotificationConfig, NotificationType, _reset_rate_limit
    )

    _reset_rate_limit()

    config = NotificationConfig(enabled=False)
    result = send_notification(
        title="Test",
        message="Test message",
        notification_type=NotificationType.ANALYSIS_COMPLETE,
        config=config
    )

    assert result.sent is False
    assert result.filtered is True
    print("  ✓ send_notification respects enabled=False")


def test_send_notification_filtered_by_level():
    """Test send_notification when filtered by level."""
    from notifications import (
        send_notification, NotificationConfig, NotificationType,
        NotificationLevel, _reset_rate_limit
    )

    _reset_rate_limit()

    config = NotificationConfig(level=NotificationLevel.CRITICAL)
    result = send_notification(
        title="Test",
        message="Test message",
        notification_type=NotificationType.WATCH_STARTED,
        config=config
    )

    assert result.sent is False
    assert result.filtered is True
    print("  ✓ send_notification respects level filter")


def test_send_notification_rate_limited():
    """Test send_notification when rate limited."""
    from notifications import (
        send_notification, NotificationConfig, NotificationType, _reset_rate_limit
    )

    _reset_rate_limit()

    config = NotificationConfig(rate_limit_seconds=60)

    # First call should not be rate limited (may still fail without plyer)
    result1 = send_notification(
        title="Test 1",
        message="Test message",
        notification_type=NotificationType.ANALYSIS_COMPLETE,
        config=config
    )
    # First call passes rate limit check
    assert result1.rate_limited is False

    # Second rapid call should be rate limited
    result2 = send_notification(
        title="Test 2",
        message="Test message",
        notification_type=NotificationType.ANALYSIS_COMPLETE,
        config=config
    )
    assert result2.sent is False
    assert result2.rate_limited is True

    print("  ✓ send_notification respects rate limit")


def test_notify_analysis_complete():
    """Test notify_analysis_complete function."""
    from notifications import (
        notify_analysis_complete, NotificationConfig, NotificationType, _reset_rate_limit
    )

    _reset_rate_limit()

    # Disable to just test function structure
    config = NotificationConfig(enabled=False)

    result = notify_analysis_complete(
        song_name="Test Song",
        health_score=85,
        grade="A",
        total_issues=3,
        config=config
    )

    assert result.notification_type == NotificationType.ANALYSIS_COMPLETE
    assert "Test Song" in result.title
    assert "85" in result.message
    assert "Grade A" in result.message
    print("  ✓ notify_analysis_complete works")


def test_notify_scan_complete():
    """Test notify_scan_complete function."""
    from notifications import (
        notify_scan_complete, NotificationConfig, NotificationType, _reset_rate_limit
    )

    _reset_rate_limit()

    config = NotificationConfig(enabled=False)

    result = notify_scan_complete(
        folder_name="My Projects",
        files_scanned=10,
        files_failed=2,
        avg_health=75.5,
        config=config
    )

    assert result.notification_type == NotificationType.SCAN_COMPLETE
    assert "My Projects" in result.title
    assert "10" in result.message
    assert "2" in result.message
    print("  ✓ notify_scan_complete works")


def test_notify_health_alert():
    """Test notify_health_alert function."""
    from notifications import (
        notify_health_alert, NotificationConfig, NotificationType, _reset_rate_limit
    )

    _reset_rate_limit()

    config = NotificationConfig(enabled=False)

    # Test with health drop
    result = notify_health_alert(
        song_name="Test Song",
        old_score=80,
        new_score=60,
        old_grade="A",
        new_grade="C",
        config=config
    )

    assert result.notification_type == NotificationType.HEALTH_ALERT
    assert "Test Song" in result.title
    assert "80" in result.message
    assert "60" in result.message

    # Test with improvement (should be filtered)
    result2 = notify_health_alert(
        song_name="Test Song",
        old_score=60,
        new_score=80,
        old_grade="C",
        new_grade="A",
        config=config
    )
    assert result2.filtered is True

    print("  ✓ notify_health_alert works")


def test_notify_watch_started():
    """Test notify_watch_started function."""
    from notifications import (
        notify_watch_started, NotificationConfig, NotificationType, _reset_rate_limit
    )

    _reset_rate_limit()

    config = NotificationConfig(enabled=False)

    result = notify_watch_started(
        folder_path="/path/to/folder",
        config=config
    )

    assert result.notification_type == NotificationType.WATCH_STARTED
    assert "Watch Mode" in result.title
    print("  ✓ notify_watch_started works")


def test_notify_watch_stopped():
    """Test notify_watch_stopped function."""
    from notifications import (
        notify_watch_stopped, NotificationConfig, NotificationType, _reset_rate_limit
    )

    _reset_rate_limit()

    config = NotificationConfig(enabled=False)

    result = notify_watch_stopped(
        files_analyzed=5,
        uptime="1h 30m",
        config=config
    )

    assert result.notification_type == NotificationType.WATCH_STOPPED
    assert "5" in result.message
    assert "1h 30m" in result.message
    print("  ✓ notify_watch_stopped works")


def test_notify_schedule_complete():
    """Test notify_schedule_complete function."""
    from notifications import (
        notify_schedule_complete, NotificationConfig, NotificationType, _reset_rate_limit
    )

    _reset_rate_limit()

    config = NotificationConfig(enabled=False)

    # Test success
    result = notify_schedule_complete(
        schedule_name="Daily Scan",
        files_scanned=15,
        success=True,
        config=config
    )

    assert result.notification_type == NotificationType.SCHEDULE_COMPLETE
    assert "Daily Scan" in result.title
    assert "15" in result.message

    # Test failure
    result2 = notify_schedule_complete(
        schedule_name="Weekly Scan",
        files_scanned=0,
        success=False,
        error_message="Folder not found",
        config=config
    )

    assert "Failed" in result2.title
    assert "Folder not found" in result2.message
    print("  ✓ notify_schedule_complete works")


def test_notification_manager_init():
    """Test NotificationManager initialization."""
    from notifications import NotificationManager, NotificationConfig, NotificationLevel

    # Default config
    manager = NotificationManager()
    assert manager.config.enabled is True

    # Custom config
    config = NotificationConfig(level=NotificationLevel.IMPORTANT)
    manager2 = NotificationManager(config=config)
    assert manager2.config.level == NotificationLevel.IMPORTANT

    print("  ✓ NotificationManager initialization works")


def test_notification_manager_configure():
    """Test NotificationManager.configure method."""
    from notifications import NotificationManager, NotificationLevel

    manager = NotificationManager()

    manager.configure(
        enabled=False,
        level=NotificationLevel.CRITICAL,
        rate_limit=60
    )

    assert manager.config.enabled is False
    assert manager.config.level == NotificationLevel.CRITICAL
    assert manager.config.rate_limit_seconds == 60
    print("  ✓ NotificationManager.configure works")


def test_notification_manager_history():
    """Test NotificationManager history tracking."""
    from notifications import NotificationManager, NotificationConfig, _reset_rate_limit

    _reset_rate_limit()

    config = NotificationConfig(enabled=False)  # Disable to avoid actual notifications
    manager = NotificationManager(config=config)

    # Initially empty
    assert len(manager.history) == 0

    # Send some notifications (disabled, so they won't actually send)
    manager.analysis_complete("Song 1", 80, "A", 2)
    manager.analysis_complete("Song 2", 70, "B", 5)

    assert len(manager.history) == 2
    print("  ✓ NotificationManager history tracking works")


def test_notification_manager_counters():
    """Test NotificationManager counter properties."""
    from notifications import NotificationManager, NotificationConfig, _reset_rate_limit

    _reset_rate_limit()

    config = NotificationConfig(enabled=False)  # All will be filtered
    manager = NotificationManager(config=config)

    manager.analysis_complete("Song 1", 80, "A", 2)
    manager.scan_complete("Folder", 10, 0)

    assert manager.filtered_count == 2
    assert manager.sent_count == 0
    assert manager.rate_limited_count == 0
    print("  ✓ NotificationManager counters work")


def test_get_notification_manager():
    """Test get_notification_manager singleton."""
    from notifications import get_notification_manager

    manager1 = get_notification_manager()
    manager2 = get_notification_manager()

    assert manager1 is manager2
    print("  ✓ get_notification_manager singleton works")


def test_configure_notifications():
    """Test configure_notifications convenience function."""
    from notifications import configure_notifications, NotificationLevel

    manager = configure_notifications(
        enabled=True,
        level="important",
        rate_limit=45
    )

    assert manager.config.enabled is True
    assert manager.config.level == NotificationLevel.IMPORTANT
    assert manager.config.rate_limit_seconds == 45
    print("  ✓ configure_notifications function works")


def test_long_path_truncation():
    """Test that long paths are truncated in watch_started."""
    from notifications import notify_watch_started, NotificationConfig, _reset_rate_limit

    _reset_rate_limit()

    config = NotificationConfig(enabled=False)
    long_path = "/very/long/path/that/goes/on/and/on/for/a/really/long/time/folder"

    result = notify_watch_started(long_path, config=config)

    # Message should be truncated
    assert len(result.message) < len(long_path) + 20  # Some overhead for "Watching: ..."
    print("  ✓ Long path truncation works")


def run_tests():
    """Run all notification tests."""
    print("=" * 60)
    print("Notifications Tests (Story 4.7)")
    print("=" * 60)
    print("")

    tests = [
        test_notification_level_enum,
        test_notification_type_enum,
        test_notification_config_defaults,
        test_notification_config_custom_values,
        test_notification_result_dataclass,
        test_notification_result_success_property,
        test_is_plyer_available,
        test_check_rate_limit_first_call,
        test_check_rate_limit_blocks_rapid_calls,
        test_check_rate_limit_allows_after_period,
        test_reset_rate_limit,
        test_should_notify_all_level,
        test_should_notify_important_level,
        test_should_notify_critical_level,
        test_get_grade_emoji,
        test_send_notification_disabled,
        test_send_notification_filtered_by_level,
        test_send_notification_rate_limited,
        test_notify_analysis_complete,
        test_notify_scan_complete,
        test_notify_health_alert,
        test_notify_watch_started,
        test_notify_watch_stopped,
        test_notify_schedule_complete,
        test_notification_manager_init,
        test_notification_manager_configure,
        test_notification_manager_history,
        test_notification_manager_counters,
        test_get_notification_manager,
        test_configure_notifications,
        test_long_path_truncation,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print("")
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
