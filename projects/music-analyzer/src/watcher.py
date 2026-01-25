"""
File Watcher Module for ALS Doctor

Monitors folders for changes to .als files and triggers automatic analysis.
Uses the watchdog library for cross-platform file system monitoring.
"""

import os
import sys
import time
import threading
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, Dict, List, Set
from dataclasses import dataclass, field
from collections import deque
from contextlib import contextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


@dataclass
class WatchEvent:
    """Represents a file system event for an .als file."""
    file_path: str
    event_type: str  # 'created', 'modified', 'deleted', 'moved'
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def als_filename(self) -> str:
        return Path(self.file_path).name

    @property
    def project_folder(self) -> str:
        return str(Path(self.file_path).parent)


@dataclass
class WatchResult:
    """Result of processing a watch event."""
    file_path: str
    success: bool
    health_score: Optional[int] = None
    grade: Optional[str] = None
    total_issues: Optional[int] = None
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class WatchStats:
    """Statistics for a watch session."""
    started_at: datetime
    folder_path: str
    files_analyzed: int = 0
    files_failed: int = 0
    total_events: int = 0
    last_event_at: Optional[datetime] = None
    results: List[WatchResult] = field(default_factory=list)

    @property
    def uptime_seconds(self) -> float:
        return (datetime.now() - self.started_at).total_seconds()

    @property
    def uptime_formatted(self) -> str:
        seconds = int(self.uptime_seconds)
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"


class DebouncedQueue:
    """
    Queue that debounces rapid file events.

    Multiple rapid changes to the same file are coalesced into a single event
    after the debounce period expires.
    """

    def __init__(self, debounce_seconds: float = 5.0):
        self.debounce_seconds = debounce_seconds
        self._pending: Dict[str, WatchEvent] = {}
        self._lock = threading.Lock()

    def add_event(self, event: WatchEvent) -> None:
        """Add an event to the queue, resetting debounce timer for this file."""
        with self._lock:
            # Use the latest event for this file
            self._pending[event.file_path] = event

    def get_ready_events(self) -> List[WatchEvent]:
        """Get events that have passed the debounce period."""
        now = datetime.now()
        ready = []

        with self._lock:
            expired_keys = []
            for file_path, event in self._pending.items():
                elapsed = (now - event.timestamp).total_seconds()
                if elapsed >= self.debounce_seconds:
                    ready.append(event)
                    expired_keys.append(file_path)

            for key in expired_keys:
                del self._pending[key]

        return ready

    def clear(self) -> None:
        """Clear all pending events."""
        with self._lock:
            self._pending.clear()

    @property
    def pending_count(self) -> int:
        """Number of events waiting in the queue."""
        with self._lock:
            return len(self._pending)


def is_backup_folder(path: str) -> bool:
    """Check if a path is inside a Backup folder."""
    # Normalize path separators and convert to lowercase
    path_normalized = path.replace('\\', '/').lower()

    # Check for common backup folder names as complete folder components
    backup_folders = ['backup', 'backups', 'ableton project info']

    # Split path into components and check each
    parts = path_normalized.split('/')
    for part in parts:
        if part in backup_folders:
            return True
    return False


def is_als_file(path: str) -> bool:
    """Check if a path is an .als file."""
    return path.lower().endswith('.als')


class ALSFileEventHandler:
    """
    Event handler for .als file changes.

    Filters events to only process .als files and exclude backup folders.
    Uses a debounced queue to handle rapid changes.
    """

    def __init__(
        self,
        callback: Callable[[WatchEvent], Optional[WatchResult]],
        debounce_seconds: float = 5.0,
        quiet: bool = False
    ):
        """
        Initialize the event handler.

        Args:
            callback: Function to call when an .als file changes
            debounce_seconds: Time to wait after last change before processing
            quiet: Suppress non-essential output
        """
        self.callback = callback
        self.queue = DebouncedQueue(debounce_seconds)
        self.quiet = quiet
        self._processed_files: Set[str] = set()

    def on_any_event(self, event) -> None:
        """Handle any file system event."""
        # Skip directory events
        if event.is_directory:
            return

        # Get the file path
        src_path = event.src_path

        # Skip non-.als files
        if not is_als_file(src_path):
            return

        # Skip backup folders
        if is_backup_folder(src_path):
            if not self.quiet:
                logger.debug(f"Ignoring backup file: {src_path}")
            return

        # Map event type
        event_type_map = {
            'created': 'created',
            'modified': 'modified',
            'deleted': 'deleted',
            'moved': 'moved'
        }

        event_type = event_type_map.get(event.event_type, 'modified')

        # Skip deleted events (we only analyze existing files)
        if event_type == 'deleted':
            if not self.quiet:
                logger.info(f"File deleted: {Path(src_path).name}")
            return

        # For moved events, use the destination path
        if event_type == 'moved' and hasattr(event, 'dest_path'):
            src_path = event.dest_path
            if not is_als_file(src_path) or is_backup_folder(src_path):
                return

        # Create watch event and add to debounced queue
        watch_event = WatchEvent(
            file_path=src_path,
            event_type=event_type,
            timestamp=datetime.now()
        )

        self.queue.add_event(watch_event)

        if not self.quiet:
            logger.debug(f"Queued event: {event_type} - {Path(src_path).name}")

    def process_ready_events(self) -> List[WatchResult]:
        """Process events that have passed the debounce period."""
        ready_events = self.queue.get_ready_events()
        results = []

        for event in ready_events:
            if not self.quiet:
                logger.info(f"Processing: {event.als_filename}")

            try:
                result = self.callback(event)
                if result:
                    results.append(result)
            except Exception as e:
                error_result = WatchResult(
                    file_path=event.file_path,
                    success=False,
                    error_message=str(e)
                )
                results.append(error_result)
                if not self.quiet:
                    logger.error(f"Error processing {event.als_filename}: {e}")

        return results


class FolderWatcher:
    """
    Watches a folder for .als file changes and triggers analysis.

    Features:
    - Recursive monitoring of all subfolders
    - Excludes Backup folders
    - Debounces rapid changes (configurable, default 5 seconds)
    - Logs results to data/watch.log
    - Graceful shutdown on Ctrl+C
    """

    def __init__(
        self,
        folder_path: str,
        debounce_seconds: float = 5.0,
        quiet: bool = False,
        save_to_db: bool = True,
        log_path: Optional[str] = None
    ):
        """
        Initialize the folder watcher.

        Args:
            folder_path: Path to the folder to watch
            debounce_seconds: Seconds to wait after last change before processing
            quiet: Suppress non-essential output
            save_to_db: Whether to save results to the database
            log_path: Path to log file (default: data/watch.log)
        """
        self.folder_path = str(Path(folder_path).absolute())
        self.debounce_seconds = debounce_seconds
        self.quiet = quiet
        self.save_to_db = save_to_db

        # Set up log path
        if log_path:
            self.log_path = Path(log_path)
        else:
            self.log_path = Path(__file__).parent.parent.parent.parent / "data" / "watch.log"

        # Ensure log directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        self._observer = None
        self._running = False
        self._stats: Optional[WatchStats] = None
        self._event_handler: Optional[ALSFileEventHandler] = None
        self._stop_event = threading.Event()

    def _analyze_file(self, event: WatchEvent) -> Optional[WatchResult]:
        """Analyze a single .als file and optionally save to database."""
        from pathlib import Path

        file_path = Path(event.file_path)

        # Verify file still exists
        if not file_path.exists():
            return WatchResult(
                file_path=event.file_path,
                success=False,
                error_message="File no longer exists"
            )

        try:
            # Import analysis functions
            from database import (
                persist_scan_result, ScanResult, ScanResultIssue, _calculate_grade, get_db
            )
            from device_chain_analyzer import analyze_als_devices
            from effect_chain_doctor import EffectChainDoctor

            # Perform analysis
            analysis = analyze_als_devices(str(file_path))
            doctor = EffectChainDoctor()
            diagnosis = doctor.diagnose(analysis)

            # Build result
            result = WatchResult(
                file_path=event.file_path,
                success=True,
                health_score=diagnosis.overall_health,
                grade=_calculate_grade(diagnosis.overall_health),
                total_issues=diagnosis.total_issues
            )

            # Save to database if enabled
            if self.save_to_db:
                # Convert issues to ScanResultIssue format
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
                    als_path=str(file_path),
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

                db = get_db()
                if db.is_initialized():
                    persist_scan_result(scan_result)
                else:
                    if not self.quiet:
                        logger.warning("Database not initialized, skipping save")

            return result

        except Exception as e:
            return WatchResult(
                file_path=event.file_path,
                success=False,
                error_message=str(e)
            )

    def _log_result(self, result: WatchResult) -> None:
        """Log a watch result to the log file."""
        timestamp = result.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        filename = Path(result.file_path).name

        if result.success:
            line = f"{timestamp} | OK | {filename} | Score: {result.health_score} [{result.grade}] | Issues: {result.total_issues}"
        else:
            line = f"{timestamp} | ERROR | {filename} | {result.error_message}"

        try:
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(line + "\n")
        except Exception as e:
            logger.error(f"Failed to write to log: {e}")

    def _process_callback(self, event: WatchEvent) -> Optional[WatchResult]:
        """Callback for processing file events."""
        result = self._analyze_file(event)

        if result:
            # Update stats
            if self._stats:
                self._stats.total_events += 1
                self._stats.last_event_at = datetime.now()

                if result.success:
                    self._stats.files_analyzed += 1
                else:
                    self._stats.files_failed += 1

                self._stats.results.append(result)
                # Keep only last 100 results
                if len(self._stats.results) > 100:
                    self._stats.results = self._stats.results[-100:]

            # Log the result
            self._log_result(result)

            # Print result
            if not self.quiet:
                filename = Path(result.file_path).name
                if result.success:
                    print(f"  [{result.grade}] {filename}: {result.health_score}/100, {result.total_issues} issues")
                else:
                    print(f"  [!] {filename}: {result.error_message}")

        return result

    def start(self, blocking: bool = True) -> None:
        """
        Start watching the folder.

        Args:
            blocking: If True, blocks until stopped (Ctrl+C)
        """
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            raise ImportError("watchdog library is required. Install with: pip install watchdog")

        if self._running:
            raise RuntimeError("Watcher is already running")

        # Verify folder exists
        if not Path(self.folder_path).exists():
            raise ValueError(f"Folder does not exist: {self.folder_path}")

        if not Path(self.folder_path).is_dir():
            raise ValueError(f"Path is not a directory: {self.folder_path}")

        # Initialize stats
        self._stats = WatchStats(
            started_at=datetime.now(),
            folder_path=self.folder_path
        )

        # Create event handler
        self._event_handler = ALSFileEventHandler(
            callback=self._process_callback,
            debounce_seconds=self.debounce_seconds,
            quiet=self.quiet
        )

        # Create watchdog adapter
        class WatchdogAdapter(FileSystemEventHandler):
            def __init__(self, handler):
                self.handler = handler

            def on_any_event(self, event):
                self.handler.on_any_event(event)

        adapter = WatchdogAdapter(self._event_handler)

        # Create observer
        self._observer = Observer()
        self._observer.schedule(adapter, self.folder_path, recursive=True)
        self._observer.start()
        self._running = True
        self._stop_event.clear()

        if not self.quiet:
            logger.info(f"Watching: {self.folder_path}")
            logger.info(f"Debounce: {self.debounce_seconds}s")
            logger.info(f"Log file: {self.log_path}")
            logger.info("Press Ctrl+C to stop")

        # Log start
        with open(self.log_path, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{timestamp} | START | Watching: {self.folder_path}\n")

        if blocking:
            self._run_loop()

    def _run_loop(self) -> None:
        """Main loop for processing events."""
        try:
            while self._running and not self._stop_event.is_set():
                # Process any ready events
                if self._event_handler:
                    self._event_handler.process_ready_events()

                # Sleep briefly to avoid busy waiting
                self._stop_event.wait(timeout=0.5)

        except KeyboardInterrupt:
            if not self.quiet:
                print("\nStopping watcher...")
        finally:
            self.stop()

    def stop(self) -> Optional[WatchStats]:
        """
        Stop watching and return session statistics.

        Returns:
            WatchStats with session summary
        """
        if not self._running:
            return self._stats

        self._running = False
        self._stop_event.set()

        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5.0)
            self._observer = None

        # Log stop
        try:
            with open(self.log_path, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if self._stats:
                    f.write(f"{timestamp} | STOP | Uptime: {self._stats.uptime_formatted} | "
                           f"Analyzed: {self._stats.files_analyzed} | "
                           f"Failed: {self._stats.files_failed}\n")
                else:
                    f.write(f"{timestamp} | STOP | Watcher stopped\n")
        except Exception as e:
            logger.error(f"Failed to write to log: {e}")

        if not self.quiet and self._stats:
            print(f"\nSession Summary:")
            print(f"  Uptime: {self._stats.uptime_formatted}")
            print(f"  Files analyzed: {self._stats.files_analyzed}")
            print(f"  Files failed: {self._stats.files_failed}")
            print(f"  Log: {self.log_path}")

        return self._stats

    @property
    def is_running(self) -> bool:
        """Check if the watcher is currently running."""
        return self._running

    @property
    def stats(self) -> Optional[WatchStats]:
        """Get current session statistics."""
        return self._stats


def watch_folder(
    folder_path: str,
    debounce_seconds: float = 5.0,
    quiet: bool = False,
    save_to_db: bool = True
) -> WatchStats:
    """
    Watch a folder for .als file changes and run analysis.

    Convenience function that creates a FolderWatcher and runs it
    in blocking mode until interrupted.

    Args:
        folder_path: Path to the folder to watch
        debounce_seconds: Seconds to wait after last change before processing
        quiet: Suppress non-essential output
        save_to_db: Whether to save results to the database

    Returns:
        WatchStats with session summary
    """
    watcher = FolderWatcher(
        folder_path=folder_path,
        debounce_seconds=debounce_seconds,
        quiet=quiet,
        save_to_db=save_to_db
    )

    watcher.start(blocking=True)
    return watcher.stats
