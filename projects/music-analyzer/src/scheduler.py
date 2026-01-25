"""
Scheduler Module for ALS Doctor

Provides scheduled batch scanning functionality for Ableton projects.
Manages schedule configurations stored in JSON and integrates with
OS task schedulers (cron on Linux/macOS, Task Scheduler on Windows).
"""

import os
import sys
import json
import uuid
import subprocess
import platform
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class ScheduleFrequency(Enum):
    """Frequency options for scheduled scans."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class Schedule:
    """Represents a scheduled scan configuration."""
    id: str
    name: str
    folder_path: str
    frequency: str  # 'hourly', 'daily', 'weekly'
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_run_at: Optional[str] = None
    last_run_status: Optional[str] = None  # 'success', 'failed', 'skipped'
    last_run_files_scanned: int = 0
    last_run_files_failed: int = 0
    # Optional: specific time for daily/weekly (HH:MM format)
    run_at_time: Optional[str] = None  # e.g., "03:00"
    # Optional: day of week for weekly (0=Monday, 6=Sunday)
    run_on_day: Optional[int] = None  # 0-6

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'folder_path': self.folder_path,
            'frequency': self.frequency,
            'enabled': self.enabled,
            'created_at': self.created_at,
            'last_run_at': self.last_run_at,
            'last_run_status': self.last_run_status,
            'last_run_files_scanned': self.last_run_files_scanned,
            'last_run_files_failed': self.last_run_files_failed,
            'run_at_time': self.run_at_time,
            'run_on_day': self.run_on_day,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Schedule':
        """Create Schedule from dictionary."""
        return cls(
            id=data['id'],
            name=data['name'],
            folder_path=data['folder_path'],
            frequency=data['frequency'],
            enabled=data.get('enabled', True),
            created_at=data.get('created_at', datetime.now().isoformat()),
            last_run_at=data.get('last_run_at'),
            last_run_status=data.get('last_run_status'),
            last_run_files_scanned=data.get('last_run_files_scanned', 0),
            last_run_files_failed=data.get('last_run_files_failed', 0),
            run_at_time=data.get('run_at_time'),
            run_on_day=data.get('run_on_day'),
        )


@dataclass
class ScheduleRunResult:
    """Result of running a scheduled scan."""
    schedule_id: str
    schedule_name: str
    success: bool
    files_scanned: int = 0
    files_failed: int = 0
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def summary(self) -> str:
        """Get a summary string for the run result."""
        if self.success:
            return f"Scanned {self.files_scanned} files ({self.files_failed} failed) in {self.duration_seconds:.1f}s"
        else:
            return f"Failed: {self.error_message}"


@dataclass
class ScheduleIndex:
    """Index of all schedules stored in JSON."""
    version: int = 1
    schedules: List[Schedule] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'version': self.version,
            'schedules': [s.to_dict() for s in self.schedules]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScheduleIndex':
        """Create ScheduleIndex from dictionary."""
        schedules = [Schedule.from_dict(s) for s in data.get('schedules', [])]
        return cls(
            version=data.get('version', 1),
            schedules=schedules
        )


# Default paths
def _get_schedules_path() -> Path:
    """Get the path to the schedules.json file."""
    return Path(__file__).parent.parent.parent.parent / "data" / "schedules.json"


def _get_run_log_path() -> Path:
    """Get the path to the scheduled_runs.log file."""
    return Path(__file__).parent.parent.parent.parent / "data" / "scheduled_runs.log"


def _load_schedules_index(schedules_path: Optional[Path] = None) -> ScheduleIndex:
    """
    Load the schedules index from JSON.

    Creates the file with empty index if it doesn't exist.
    """
    path = schedules_path or _get_schedules_path()

    # Ensure data directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        # Create empty index
        index = ScheduleIndex()
        _save_schedules_index(index, path)
        return index

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return ScheduleIndex.from_dict(data)
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to load schedules: {e}")
        # Return empty index on error
        return ScheduleIndex()


def _save_schedules_index(index: ScheduleIndex, schedules_path: Optional[Path] = None) -> bool:
    """Save the schedules index to JSON."""
    path = schedules_path or _get_schedules_path()

    # Ensure data directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(index.to_dict(), f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save schedules: {e}")
        return False


def _generate_schedule_id() -> str:
    """Generate a unique schedule ID."""
    return f"schedule_{uuid.uuid4().hex[:8]}"


def _log_run(result: ScheduleRunResult, log_path: Optional[Path] = None) -> None:
    """Log a schedule run result to the log file."""
    path = log_path or _get_run_log_path()

    # Ensure data directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = result.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    status = "OK" if result.success else "FAILED"

    line = f"{timestamp} | {status} | {result.schedule_name} | {result.summary}"

    try:
        with open(path, 'a', encoding='utf-8') as f:
            f.write(line + "\n")
    except Exception as e:
        logger.error(f"Failed to write to run log: {e}")


# ==================== PUBLIC API ====================


def list_schedules(schedules_path: Optional[Path] = None) -> Tuple[List[Schedule], str]:
    """
    List all schedules.

    Returns:
        Tuple of (list of schedules, message)
    """
    index = _load_schedules_index(schedules_path)

    if not index.schedules:
        return ([], "No schedules configured.")

    return (index.schedules, f"Found {len(index.schedules)} schedule(s).")


def get_schedule_by_id(schedule_id: str, schedules_path: Optional[Path] = None) -> Tuple[Optional[Schedule], str]:
    """
    Get a schedule by its ID.

    Args:
        schedule_id: Schedule ID or name to find

    Returns:
        Tuple of (schedule or None, message)
    """
    index = _load_schedules_index(schedules_path)

    # Try exact ID match first
    for schedule in index.schedules:
        if schedule.id == schedule_id:
            return (schedule, f"Found schedule: {schedule.name}")

    # Try name match (case-insensitive)
    for schedule in index.schedules:
        if schedule.name.lower() == schedule_id.lower():
            return (schedule, f"Found schedule: {schedule.name}")

    # Try partial name match
    for schedule in index.schedules:
        if schedule_id.lower() in schedule.name.lower():
            return (schedule, f"Found schedule: {schedule.name}")

    return (None, f"Schedule not found: {schedule_id}")


def add_schedule(
    folder_path: str,
    frequency: str,
    name: Optional[str] = None,
    run_at_time: Optional[str] = None,
    run_on_day: Optional[int] = None,
    schedules_path: Optional[Path] = None
) -> Tuple[Optional[Schedule], str]:
    """
    Add a new schedule.

    Args:
        folder_path: Path to folder to scan
        frequency: 'hourly', 'daily', or 'weekly'
        name: Optional friendly name (defaults to folder name)
        run_at_time: Optional time to run (HH:MM format)
        run_on_day: Optional day of week for weekly (0=Monday)

    Returns:
        Tuple of (created schedule or None, message)
    """
    # Validate folder path
    folder = Path(folder_path).absolute()
    if not folder.exists():
        return (None, f"Folder does not exist: {folder}")

    if not folder.is_dir():
        return (None, f"Path is not a directory: {folder}")

    # Validate frequency
    valid_frequencies = ['hourly', 'daily', 'weekly']
    if frequency.lower() not in valid_frequencies:
        return (None, f"Invalid frequency: {frequency}. Must be one of: {', '.join(valid_frequencies)}")

    # Validate run_at_time format
    if run_at_time:
        try:
            datetime.strptime(run_at_time, "%H:%M")
        except ValueError:
            return (None, f"Invalid time format: {run_at_time}. Use HH:MM format.")

    # Validate run_on_day
    if run_on_day is not None and (run_on_day < 0 or run_on_day > 6):
        return (None, f"Invalid day of week: {run_on_day}. Must be 0 (Monday) to 6 (Sunday).")

    # Generate name if not provided
    if not name:
        name = folder.name

    index = _load_schedules_index(schedules_path)

    # Check for duplicate name
    for existing in index.schedules:
        if existing.name.lower() == name.lower():
            return (None, f"Schedule with name '{name}' already exists. Use a different name.")

    # Create schedule
    schedule = Schedule(
        id=_generate_schedule_id(),
        name=name,
        folder_path=str(folder),
        frequency=frequency.lower(),
        run_at_time=run_at_time,
        run_on_day=run_on_day
    )

    index.schedules.append(schedule)

    if _save_schedules_index(index, schedules_path):
        return (schedule, f"Created schedule '{schedule.name}' ({schedule.id})")
    else:
        return (None, "Failed to save schedule configuration.")


def remove_schedule(schedule_id: str, schedules_path: Optional[Path] = None) -> Tuple[bool, str]:
    """
    Remove a schedule.

    Args:
        schedule_id: Schedule ID or name to remove

    Returns:
        Tuple of (success, message)
    """
    index = _load_schedules_index(schedules_path)

    # Find the schedule
    schedule_to_remove = None
    for schedule in index.schedules:
        if schedule.id == schedule_id or schedule.name.lower() == schedule_id.lower():
            schedule_to_remove = schedule
            break

    if not schedule_to_remove:
        return (False, f"Schedule not found: {schedule_id}")

    index.schedules.remove(schedule_to_remove)

    if _save_schedules_index(index, schedules_path):
        return (True, f"Removed schedule: {schedule_to_remove.name}")
    else:
        return (False, "Failed to save schedule configuration.")


def enable_schedule(schedule_id: str, enabled: bool = True, schedules_path: Optional[Path] = None) -> Tuple[bool, str]:
    """
    Enable or disable a schedule.

    Args:
        schedule_id: Schedule ID or name
        enabled: True to enable, False to disable

    Returns:
        Tuple of (success, message)
    """
    index = _load_schedules_index(schedules_path)

    # Find and update the schedule
    for schedule in index.schedules:
        if schedule.id == schedule_id or schedule.name.lower() == schedule_id.lower():
            schedule.enabled = enabled
            if _save_schedules_index(index, schedules_path):
                status = "enabled" if enabled else "disabled"
                return (True, f"Schedule '{schedule.name}' {status}.")
            else:
                return (False, "Failed to save schedule configuration.")

    return (False, f"Schedule not found: {schedule_id}")


def run_schedule(
    schedule_id: str,
    schedules_path: Optional[Path] = None,
    quiet: bool = False
) -> Tuple[ScheduleRunResult, str]:
    """
    Run a scheduled scan immediately.

    Args:
        schedule_id: Schedule ID or name to run
        quiet: Suppress non-essential output

    Returns:
        Tuple of (ScheduleRunResult, message)
    """
    # Find the schedule
    schedule, msg = get_schedule_by_id(schedule_id, schedules_path)

    if schedule is None:
        return (
            ScheduleRunResult(
                schedule_id=schedule_id,
                schedule_name=schedule_id,
                success=False,
                error_message=msg
            ),
            msg
        )

    # Check if folder still exists
    folder = Path(schedule.folder_path)
    if not folder.exists():
        result = ScheduleRunResult(
            schedule_id=schedule.id,
            schedule_name=schedule.name,
            success=False,
            error_message=f"Folder no longer exists: {schedule.folder_path}"
        )
        _log_run(result)
        return (result, result.error_message)

    # Run the scan
    start_time = datetime.now()

    try:
        from database import (
            get_db, persist_scan_result, ScanResult, ScanResultIssue, _calculate_grade
        )
        from device_chain_analyzer import analyze_als_devices
        from effect_chain_doctor import EffectChainDoctor

        db = get_db()
        if not db.is_initialized():
            result = ScheduleRunResult(
                schedule_id=schedule.id,
                schedule_name=schedule.name,
                success=False,
                error_message="Database not initialized"
            )
            _log_run(result)
            return (result, result.error_message)

        # Find all .als files
        als_files = list(folder.rglob("*.als"))

        # Exclude backup folders
        als_files = [
            f for f in als_files
            if not any(part.lower() in ['backup', 'backups', 'ableton project info']
                      for part in f.parts)
        ]

        files_scanned = 0
        files_failed = 0

        for als_path in als_files:
            try:
                # Analyze the file
                analysis = analyze_als_devices(str(als_path))
                doctor = EffectChainDoctor()
                diagnosis = doctor.diagnose(analysis)

                # Convert issues
                issues = []
                for issue in diagnosis.global_issues:
                    issues.append(ScanResultIssue(
                        track_name=issue.track_name,
                        severity=issue.severity.value,
                        category=issue.category.value,
                        description=issue.description,
                        fix_suggestion=issue.recommendation
                    ))

                for track_diag in diagnosis.track_diagnoses:
                    for issue in track_diag.issues:
                        issues.append(ScanResultIssue(
                            track_name=issue.track_name,
                            severity=issue.severity.value,
                            category=issue.category.value,
                            description=issue.description,
                            fix_suggestion=issue.recommendation
                        ))

                scan_result = ScanResult(
                    als_path=str(als_path),
                    health_score=diagnosis.overall_health,
                    grade=_calculate_grade(diagnosis.overall_health),
                    total_issues=diagnosis.total_issues,
                    critical_issues=diagnosis.critical_issues,
                    warning_issues=diagnosis.warning_issues,
                    total_devices=diagnosis.total_devices,
                    disabled_devices=diagnosis.total_disabled,
                    clutter_percentage=diagnosis.clutter_percentage,
                    issues=issues
                )

                persist_scan_result(scan_result)
                files_scanned += 1

                if not quiet:
                    logger.info(f"  Scanned: {als_path.name} [{diagnosis.overall_health}]")

            except Exception as e:
                files_failed += 1
                if not quiet:
                    logger.error(f"  Failed: {als_path.name}: {e}")

        duration = (datetime.now() - start_time).total_seconds()

        result = ScheduleRunResult(
            schedule_id=schedule.id,
            schedule_name=schedule.name,
            success=True,
            files_scanned=files_scanned,
            files_failed=files_failed,
            duration_seconds=duration
        )

        # Update schedule with last run info
        _update_schedule_run_status(
            schedule.id,
            success=True,
            files_scanned=files_scanned,
            files_failed=files_failed,
            schedules_path=schedules_path
        )

        _log_run(result)
        return (result, f"Scanned {files_scanned} files in {duration:.1f}s")

    except ImportError as e:
        result = ScheduleRunResult(
            schedule_id=schedule.id,
            schedule_name=schedule.name,
            success=False,
            error_message=f"Import error: {e}"
        )
        _log_run(result)
        return (result, result.error_message)
    except Exception as e:
        result = ScheduleRunResult(
            schedule_id=schedule.id,
            schedule_name=schedule.name,
            success=False,
            error_message=str(e)
        )
        _log_run(result)
        return (result, result.error_message)


def _update_schedule_run_status(
    schedule_id: str,
    success: bool,
    files_scanned: int,
    files_failed: int,
    schedules_path: Optional[Path] = None
) -> None:
    """Update a schedule's last run status."""
    index = _load_schedules_index(schedules_path)

    for schedule in index.schedules:
        if schedule.id == schedule_id:
            schedule.last_run_at = datetime.now().isoformat()
            schedule.last_run_status = 'success' if success else 'failed'
            schedule.last_run_files_scanned = files_scanned
            schedule.last_run_files_failed = files_failed
            _save_schedules_index(index, schedules_path)
            return


def get_cron_expression(schedule: Schedule) -> str:
    """
    Get a cron expression for a schedule.

    Args:
        schedule: Schedule to generate cron expression for

    Returns:
        Cron expression string (5 fields: minute hour day month weekday)
    """
    # Default time is midnight
    minute = 0
    hour = 0

    if schedule.run_at_time:
        try:
            time_parts = schedule.run_at_time.split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1])
        except (ValueError, IndexError):
            pass

    if schedule.frequency == 'hourly':
        # Run at the specified minute every hour
        return f"{minute} * * * *"

    elif schedule.frequency == 'daily':
        # Run at the specified time every day
        return f"{minute} {hour} * * *"

    elif schedule.frequency == 'weekly':
        # Run at the specified time on the specified day
        weekday = schedule.run_on_day if schedule.run_on_day is not None else 0
        return f"{minute} {hour} * * {weekday}"

    return f"{minute} {hour} * * *"  # Default to daily


def generate_cron_command(schedule: Schedule, python_path: Optional[str] = None) -> str:
    """
    Generate the cron command for a schedule.

    Args:
        schedule: Schedule to generate command for
        python_path: Path to python executable (defaults to current)

    Returns:
        Full cron command string
    """
    if python_path is None:
        python_path = sys.executable

    als_doctor_path = Path(__file__).parent.parent / "als_doctor.py"

    return f'{python_path} "{als_doctor_path}" schedule run "{schedule.id}"'


def install_cron_job(schedule: Schedule, schedules_path: Optional[Path] = None) -> Tuple[bool, str]:
    """
    Install a cron job for the schedule (Linux/macOS only).

    Args:
        schedule: Schedule to install cron for

    Returns:
        Tuple of (success, message)
    """
    if platform.system() == 'Windows':
        return (False, "Cron is not available on Windows. Use Task Scheduler instead.")

    cron_expr = get_cron_expression(schedule)
    command = generate_cron_command(schedule)

    # Create cron line with comment
    cron_line = f"{cron_expr} {command} # als-doctor:{schedule.id}"

    try:
        # Get existing crontab
        result = subprocess.run(
            ['crontab', '-l'],
            capture_output=True,
            text=True
        )

        existing_crontab = result.stdout if result.returncode == 0 else ""

        # Check if already installed
        if f"als-doctor:{schedule.id}" in existing_crontab:
            return (False, f"Cron job already exists for schedule: {schedule.name}")

        # Add new cron line
        new_crontab = existing_crontab.rstrip() + "\n" + cron_line + "\n"

        # Install new crontab
        process = subprocess.Popen(
            ['crontab', '-'],
            stdin=subprocess.PIPE,
            text=True
        )
        process.communicate(input=new_crontab)

        if process.returncode == 0:
            return (True, f"Installed cron job for '{schedule.name}': {cron_expr}")
        else:
            return (False, "Failed to install cron job")

    except FileNotFoundError:
        return (False, "crontab command not found. Is cron installed?")
    except Exception as e:
        return (False, f"Failed to install cron job: {e}")


def uninstall_cron_job(schedule: Schedule) -> Tuple[bool, str]:
    """
    Remove a cron job for the schedule (Linux/macOS only).

    Args:
        schedule: Schedule to remove cron for

    Returns:
        Tuple of (success, message)
    """
    if platform.system() == 'Windows':
        return (False, "Cron is not available on Windows.")

    try:
        # Get existing crontab
        result = subprocess.run(
            ['crontab', '-l'],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return (False, "No crontab exists")

        existing_crontab = result.stdout

        # Filter out lines for this schedule
        new_lines = []
        removed = False
        for line in existing_crontab.split('\n'):
            if f"als-doctor:{schedule.id}" not in line:
                new_lines.append(line)
            else:
                removed = True

        if not removed:
            return (False, f"No cron job found for schedule: {schedule.name}")

        new_crontab = '\n'.join(new_lines)

        # Install new crontab
        process = subprocess.Popen(
            ['crontab', '-'],
            stdin=subprocess.PIPE,
            text=True
        )
        process.communicate(input=new_crontab)

        if process.returncode == 0:
            return (True, f"Removed cron job for '{schedule.name}'")
        else:
            return (False, "Failed to remove cron job")

    except FileNotFoundError:
        return (False, "crontab command not found")
    except Exception as e:
        return (False, f"Failed to remove cron job: {e}")


def check_due_schedules(schedules_path: Optional[Path] = None) -> List[Schedule]:
    """
    Check which schedules are due to run.

    This is used by the wrapper script to determine which schedules
    should be executed based on their frequency and last run time.

    Returns:
        List of schedules that are due to run
    """
    index = _load_schedules_index(schedules_path)
    now = datetime.now()
    due_schedules = []

    for schedule in index.schedules:
        if not schedule.enabled:
            continue

        # Check if folder exists
        if not Path(schedule.folder_path).exists():
            continue

        # Determine if due based on frequency
        is_due = False

        if schedule.last_run_at is None:
            # Never run, so it's due
            is_due = True
        else:
            try:
                last_run = datetime.fromisoformat(schedule.last_run_at)
                elapsed = (now - last_run).total_seconds()

                if schedule.frequency == 'hourly':
                    is_due = elapsed >= 3600  # 1 hour
                elif schedule.frequency == 'daily':
                    is_due = elapsed >= 86400  # 24 hours
                elif schedule.frequency == 'weekly':
                    is_due = elapsed >= 604800  # 7 days
            except (ValueError, TypeError):
                is_due = True

        if is_due:
            due_schedules.append(schedule)

    return due_schedules


def run_due_schedules(
    schedules_path: Optional[Path] = None,
    quiet: bool = False
) -> List[ScheduleRunResult]:
    """
    Run all schedules that are due.

    This is the main entry point for the wrapper script.

    Returns:
        List of ScheduleRunResult for each schedule that was run
    """
    due_schedules = check_due_schedules(schedules_path)
    results = []

    if not due_schedules:
        if not quiet:
            logger.info("No schedules due to run")
        return results

    if not quiet:
        logger.info(f"Running {len(due_schedules)} due schedule(s)")

    for schedule in due_schedules:
        if not quiet:
            logger.info(f"Running schedule: {schedule.name}")

        result, msg = run_schedule(schedule.id, schedules_path, quiet)
        results.append(result)

        if not quiet:
            if result.success:
                logger.info(f"  Completed: {result.summary}")
            else:
                logger.error(f"  Failed: {result.error_message}")

    return results
