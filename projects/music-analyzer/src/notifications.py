"""
Desktop Notifications Module for ALS Doctor

Provides cross-platform desktop notifications for analysis events.
Uses the plyer library for cross-platform support.

Notification types:
- Analysis complete: Shows project name, score, and grade
- Scan complete: Shows summary of batch scan results
- Health alert: Notifies when health drops significantly

Features:
- Rate limiting (max 1 notification per 30 seconds)
- Notification levels: all, important, critical
- Click action can open dashboard URL
"""

import time
import threading
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# Track last notification time for rate limiting
_last_notification_time: Optional[float] = None
_notification_lock = threading.Lock()

# Default rate limit in seconds
DEFAULT_RATE_LIMIT = 30

# Try to import plyer
try:
    from plyer import notification as plyer_notification
    PLYER_AVAILABLE = True
except ImportError:
    plyer_notification = None
    PLYER_AVAILABLE = False


class NotificationLevel(Enum):
    """Notification filtering levels."""
    ALL = "all"           # All notifications
    IMPORTANT = "important"  # Analysis complete, significant changes
    CRITICAL = "critical"    # Only critical issues or major health drops


class NotificationType(Enum):
    """Types of notifications."""
    ANALYSIS_COMPLETE = "analysis_complete"
    SCAN_COMPLETE = "scan_complete"
    HEALTH_ALERT = "health_alert"
    WATCH_STARTED = "watch_started"
    WATCH_STOPPED = "watch_stopped"
    SCHEDULE_COMPLETE = "schedule_complete"


@dataclass
class NotificationConfig:
    """Configuration for notifications."""
    enabled: bool = True
    level: NotificationLevel = NotificationLevel.ALL
    rate_limit_seconds: float = DEFAULT_RATE_LIMIT
    app_name: str = "ALS Doctor"
    timeout: int = 10  # Notification display time in seconds
    click_action: Optional[str] = None  # URL or command to run on click


@dataclass
class NotificationResult:
    """Result of attempting to send a notification."""
    sent: bool
    notification_type: NotificationType
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    rate_limited: bool = False
    filtered: bool = False
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Check if notification was successfully sent."""
        return self.sent and not self.error


def is_plyer_available() -> bool:
    """Check if plyer library is available."""
    return PLYER_AVAILABLE


def _check_rate_limit(rate_limit_seconds: float) -> bool:
    """
    Check if we're within rate limit.

    Returns True if we can send a notification, False if rate limited.
    """
    global _last_notification_time

    with _notification_lock:
        current_time = time.time()

        if _last_notification_time is None:
            _last_notification_time = current_time
            return True

        elapsed = current_time - _last_notification_time
        if elapsed >= rate_limit_seconds:
            _last_notification_time = current_time
            return True

        return False


def _reset_rate_limit() -> None:
    """Reset the rate limit timer (for testing)."""
    global _last_notification_time
    with _notification_lock:
        _last_notification_time = None


def _should_notify(
    notification_type: NotificationType,
    level: NotificationLevel,
    health_score: Optional[int] = None,
    health_delta: Optional[int] = None
) -> bool:
    """
    Determine if a notification should be sent based on level filter.

    Args:
        notification_type: Type of notification
        level: Current filter level
        health_score: Optional health score for context
        health_delta: Optional health change for context

    Returns:
        True if notification should be sent
    """
    if level == NotificationLevel.ALL:
        return True

    if level == NotificationLevel.IMPORTANT:
        # Important: Analysis complete, significant health changes, scan complete
        if notification_type in (
            NotificationType.ANALYSIS_COMPLETE,
            NotificationType.SCAN_COMPLETE,
            NotificationType.SCHEDULE_COMPLETE
        ):
            return True

        if notification_type == NotificationType.HEALTH_ALERT:
            # Only if significant drop (more than 10 points)
            if health_delta is not None and health_delta <= -10:
                return True
            return False

        return False

    if level == NotificationLevel.CRITICAL:
        # Critical: Only health alerts with critical issues or major drops
        if notification_type == NotificationType.HEALTH_ALERT:
            # Major drop (more than 20 points) or very low score
            if health_delta is not None and health_delta <= -20:
                return True
            if health_score is not None and health_score < 40:
                return True
        return False

    return False


def _get_grade_emoji(grade: str) -> str:
    """Get an emoji for a grade."""
    grade_emojis = {
        'A': '🏆',
        'B': '👍',
        'C': '📊',
        'D': '⚠️',
        'F': '❌'
    }
    return grade_emojis.get(grade.upper(), '📋')


def send_notification(
    title: str,
    message: str,
    notification_type: NotificationType = NotificationType.ANALYSIS_COMPLETE,
    config: Optional[NotificationConfig] = None,
    health_score: Optional[int] = None,
    health_delta: Optional[int] = None
) -> NotificationResult:
    """
    Send a desktop notification.

    Args:
        title: Notification title
        message: Notification message body
        notification_type: Type of notification
        config: Optional configuration
        health_score: Optional health score for filtering
        health_delta: Optional health delta for filtering

    Returns:
        NotificationResult with status information
    """
    if config is None:
        config = NotificationConfig()

    # Check if notifications are enabled
    if not config.enabled:
        return NotificationResult(
            sent=False,
            notification_type=notification_type,
            title=title,
            message=message,
            filtered=True
        )

    # Check notification level filter
    if not _should_notify(notification_type, config.level, health_score, health_delta):
        return NotificationResult(
            sent=False,
            notification_type=notification_type,
            title=title,
            message=message,
            filtered=True
        )

    # Check rate limit
    if not _check_rate_limit(config.rate_limit_seconds):
        return NotificationResult(
            sent=False,
            notification_type=notification_type,
            title=title,
            message=message,
            rate_limited=True
        )

    # Check if plyer is available
    if not PLYER_AVAILABLE:
        return NotificationResult(
            sent=False,
            notification_type=notification_type,
            title=title,
            message=message,
            error="plyer library not available"
        )

    # Send the notification
    try:
        plyer_notification.notify(
            title=title,
            message=message,
            app_name=config.app_name,
            timeout=config.timeout
        )

        return NotificationResult(
            sent=True,
            notification_type=notification_type,
            title=title,
            message=message
        )

    except Exception as e:
        return NotificationResult(
            sent=False,
            notification_type=notification_type,
            title=title,
            message=message,
            error=str(e)
        )


def notify_analysis_complete(
    song_name: str,
    health_score: int,
    grade: str,
    total_issues: int,
    config: Optional[NotificationConfig] = None
) -> NotificationResult:
    """
    Send notification when analysis is complete.

    Args:
        song_name: Name of the analyzed song/project
        health_score: Health score (0-100)
        grade: Grade letter (A-F)
        total_issues: Number of issues found
        config: Optional notification configuration

    Returns:
        NotificationResult
    """
    emoji = _get_grade_emoji(grade)
    title = f"{emoji} Analysis Complete: {song_name}"

    issues_text = f"{total_issues} issue{'s' if total_issues != 1 else ''}"
    message = f"Health: {health_score}/100 (Grade {grade})\n{issues_text} found"

    return send_notification(
        title=title,
        message=message,
        notification_type=NotificationType.ANALYSIS_COMPLETE,
        config=config,
        health_score=health_score
    )


def notify_scan_complete(
    folder_name: str,
    files_scanned: int,
    files_failed: int,
    avg_health: Optional[float] = None,
    config: Optional[NotificationConfig] = None
) -> NotificationResult:
    """
    Send notification when a batch scan is complete.

    Args:
        folder_name: Name of scanned folder
        files_scanned: Number of files successfully scanned
        files_failed: Number of files that failed
        avg_health: Optional average health score
        config: Optional notification configuration

    Returns:
        NotificationResult
    """
    success_emoji = "✅" if files_failed == 0 else "⚠️"
    title = f"{success_emoji} Scan Complete: {folder_name}"

    message_parts = [f"{files_scanned} file{'s' if files_scanned != 1 else ''} analyzed"]

    if files_failed > 0:
        message_parts.append(f"{files_failed} failed")

    if avg_health is not None:
        message_parts.append(f"Avg health: {avg_health:.0f}/100")

    message = "\n".join(message_parts)

    return send_notification(
        title=title,
        message=message,
        notification_type=NotificationType.SCAN_COMPLETE,
        config=config
    )


def notify_health_alert(
    song_name: str,
    old_score: int,
    new_score: int,
    old_grade: str,
    new_grade: str,
    config: Optional[NotificationConfig] = None
) -> NotificationResult:
    """
    Send notification when health score drops significantly.

    Args:
        song_name: Name of the song/project
        old_score: Previous health score
        new_score: New health score
        old_grade: Previous grade
        new_grade: New grade
        config: Optional notification configuration

    Returns:
        NotificationResult
    """
    delta = new_score - old_score

    if delta >= 0:
        # No alert for improvements
        return NotificationResult(
            sent=False,
            notification_type=NotificationType.HEALTH_ALERT,
            title="",
            message="",
            filtered=True
        )

    title = f"⚠️ Health Drop: {song_name}"
    message = f"Score: {old_score} → {new_score} ({delta:+d})\nGrade: {old_grade} → {new_grade}"

    return send_notification(
        title=title,
        message=message,
        notification_type=NotificationType.HEALTH_ALERT,
        config=config,
        health_score=new_score,
        health_delta=delta
    )


def notify_watch_started(
    folder_path: str,
    config: Optional[NotificationConfig] = None
) -> NotificationResult:
    """
    Send notification when watch mode starts.

    Args:
        folder_path: Path being watched
        config: Optional notification configuration

    Returns:
        NotificationResult
    """
    title = "👁️ Watch Mode Started"

    # Truncate path if too long
    if len(folder_path) > 50:
        folder_display = "..." + folder_path[-47:]
    else:
        folder_display = folder_path

    message = f"Watching: {folder_display}"

    return send_notification(
        title=title,
        message=message,
        notification_type=NotificationType.WATCH_STARTED,
        config=config
    )


def notify_watch_stopped(
    files_analyzed: int,
    uptime: str,
    config: Optional[NotificationConfig] = None
) -> NotificationResult:
    """
    Send notification when watch mode stops.

    Args:
        files_analyzed: Number of files analyzed during session
        uptime: Session duration string
        config: Optional notification configuration

    Returns:
        NotificationResult
    """
    title = "⏹️ Watch Mode Stopped"
    message = f"Duration: {uptime}\nFiles analyzed: {files_analyzed}"

    return send_notification(
        title=title,
        message=message,
        notification_type=NotificationType.WATCH_STOPPED,
        config=config
    )


def notify_schedule_complete(
    schedule_name: str,
    files_scanned: int,
    success: bool,
    error_message: Optional[str] = None,
    config: Optional[NotificationConfig] = None
) -> NotificationResult:
    """
    Send notification when a scheduled scan completes.

    Args:
        schedule_name: Name of the schedule
        files_scanned: Number of files scanned
        success: Whether the scan succeeded
        error_message: Optional error message if failed
        config: Optional notification configuration

    Returns:
        NotificationResult
    """
    if success:
        title = f"📅 Scheduled Scan: {schedule_name}"
        message = f"{files_scanned} file{'s' if files_scanned != 1 else ''} scanned successfully"
    else:
        title = f"❌ Schedule Failed: {schedule_name}"
        message = error_message or "Unknown error occurred"

    return send_notification(
        title=title,
        message=message,
        notification_type=NotificationType.SCHEDULE_COMPLETE,
        config=config
    )


class NotificationManager:
    """
    Manager class for handling notifications with configuration.

    Use this class to create a persistent notification handler with
    consistent configuration throughout an application session.
    """

    def __init__(self, config: Optional[NotificationConfig] = None):
        """
        Initialize the notification manager.

        Args:
            config: Optional notification configuration
        """
        self.config = config or NotificationConfig()
        self._history: list = []
        self._max_history = 100

    def configure(
        self,
        enabled: Optional[bool] = None,
        level: Optional[NotificationLevel] = None,
        rate_limit: Optional[float] = None
    ) -> None:
        """
        Update configuration.

        Args:
            enabled: Enable/disable notifications
            level: Notification filter level
            rate_limit: Rate limit in seconds
        """
        if enabled is not None:
            self.config.enabled = enabled
        if level is not None:
            self.config.level = level
        if rate_limit is not None:
            self.config.rate_limit_seconds = rate_limit

    def analysis_complete(
        self,
        song_name: str,
        health_score: int,
        grade: str,
        total_issues: int
    ) -> NotificationResult:
        """Send analysis complete notification."""
        result = notify_analysis_complete(
            song_name, health_score, grade, total_issues, self.config
        )
        self._add_to_history(result)
        return result

    def scan_complete(
        self,
        folder_name: str,
        files_scanned: int,
        files_failed: int,
        avg_health: Optional[float] = None
    ) -> NotificationResult:
        """Send scan complete notification."""
        result = notify_scan_complete(
            folder_name, files_scanned, files_failed, avg_health, self.config
        )
        self._add_to_history(result)
        return result

    def health_alert(
        self,
        song_name: str,
        old_score: int,
        new_score: int,
        old_grade: str,
        new_grade: str
    ) -> NotificationResult:
        """Send health alert notification."""
        result = notify_health_alert(
            song_name, old_score, new_score, old_grade, new_grade, self.config
        )
        self._add_to_history(result)
        return result

    def watch_started(self, folder_path: str) -> NotificationResult:
        """Send watch started notification."""
        result = notify_watch_started(folder_path, self.config)
        self._add_to_history(result)
        return result

    def watch_stopped(
        self,
        files_analyzed: int,
        uptime: str
    ) -> NotificationResult:
        """Send watch stopped notification."""
        result = notify_watch_stopped(files_analyzed, uptime, self.config)
        self._add_to_history(result)
        return result

    def schedule_complete(
        self,
        schedule_name: str,
        files_scanned: int,
        success: bool,
        error_message: Optional[str] = None
    ) -> NotificationResult:
        """Send schedule complete notification."""
        result = notify_schedule_complete(
            schedule_name, files_scanned, success, error_message, self.config
        )
        self._add_to_history(result)
        return result

    def _add_to_history(self, result: NotificationResult) -> None:
        """Add a notification result to history."""
        self._history.append(result)
        # Keep only recent history
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    @property
    def history(self) -> list:
        """Get notification history."""
        return self._history.copy()

    @property
    def sent_count(self) -> int:
        """Count of successfully sent notifications."""
        return sum(1 for r in self._history if r.sent)

    @property
    def filtered_count(self) -> int:
        """Count of filtered notifications."""
        return sum(1 for r in self._history if r.filtered)

    @property
    def rate_limited_count(self) -> int:
        """Count of rate-limited notifications."""
        return sum(1 for r in self._history if r.rate_limited)


# Global notification manager instance
_default_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """Get the global notification manager instance."""
    global _default_manager
    if _default_manager is None:
        _default_manager = NotificationManager()
    return _default_manager


def configure_notifications(
    enabled: bool = True,
    level: str = "all",
    rate_limit: float = DEFAULT_RATE_LIMIT
) -> NotificationManager:
    """
    Configure the global notification manager.

    Args:
        enabled: Enable/disable notifications
        level: Notification level ("all", "important", "critical")
        rate_limit: Rate limit in seconds

    Returns:
        The configured NotificationManager
    """
    manager = get_notification_manager()

    # Convert level string to enum
    level_map = {
        "all": NotificationLevel.ALL,
        "important": NotificationLevel.IMPORTANT,
        "critical": NotificationLevel.CRITICAL
    }
    notification_level = level_map.get(level.lower(), NotificationLevel.ALL)

    manager.configure(
        enabled=enabled,
        level=notification_level,
        rate_limit=rate_limit
    )

    return manager
