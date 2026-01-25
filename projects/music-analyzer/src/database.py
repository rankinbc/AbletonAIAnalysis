"""
Database Module for ALS Doctor

Provides SQLite database operations for persisting and querying
Ableton project analysis data.

Schema:
- projects: Unique songs identified by folder path
- versions: Individual .als files with health scores
- issues: Detected problems in each version
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from contextlib import contextmanager


# Default database location
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "projects.db"


@dataclass
class Project:
    """Represents a music project (song) in the database."""
    id: int
    folder_path: str
    song_name: str
    created_at: datetime


@dataclass
class Version:
    """Represents a specific .als file version."""
    id: int
    project_id: int
    als_path: str
    als_filename: str
    health_score: int
    grade: str
    total_issues: int
    critical_issues: int
    warning_issues: int
    total_devices: int
    disabled_devices: int
    clutter_percentage: float
    scanned_at: datetime


@dataclass
class Issue:
    """Represents an issue found in a version."""
    id: int
    version_id: int
    track_name: str
    severity: str  # 'critical', 'warning', 'suggestion'
    category: str
    description: str
    fix_suggestion: str


# SQL Schema
SCHEMA_SQL = """
-- Projects table: unique songs identified by folder path
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_path TEXT UNIQUE NOT NULL,
    song_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Versions table: individual .als files with health metrics
CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    als_path TEXT UNIQUE NOT NULL,
    als_filename TEXT NOT NULL,
    health_score INTEGER DEFAULT 0,
    grade TEXT DEFAULT 'F',
    total_issues INTEGER DEFAULT 0,
    critical_issues INTEGER DEFAULT 0,
    warning_issues INTEGER DEFAULT 0,
    total_devices INTEGER DEFAULT 0,
    disabled_devices INTEGER DEFAULT 0,
    clutter_percentage REAL DEFAULT 0.0,
    scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- Issues table: problems detected in each version
CREATE TABLE IF NOT EXISTS issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL,
    track_name TEXT,
    severity TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    fix_suggestion TEXT,
    FOREIGN KEY (version_id) REFERENCES versions(id) ON DELETE CASCADE
);

-- Changes table: tracks changes between consecutive versions
CREATE TABLE IF NOT EXISTS changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    before_version_id INTEGER NOT NULL,
    after_version_id INTEGER NOT NULL,
    change_type TEXT NOT NULL,  -- 'device_added', 'device_removed', 'device_enabled', 'device_disabled', 'track_added', 'track_removed'
    track_name TEXT,
    device_name TEXT,
    device_type TEXT,
    details TEXT,
    health_delta INTEGER,  -- health change associated with this version transition
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (before_version_id) REFERENCES versions(id) ON DELETE CASCADE,
    FOREIGN KEY (after_version_id) REFERENCES versions(id) ON DELETE CASCADE
);

-- MIDI stats table: MIDI analysis data for each version
CREATE TABLE IF NOT EXISTS midi_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER UNIQUE NOT NULL,
    total_midi_tracks INTEGER DEFAULT 0,
    total_midi_clips INTEGER DEFAULT 0,
    total_notes INTEGER DEFAULT 0,
    total_empty_clips INTEGER DEFAULT 0,
    total_short_clips INTEGER DEFAULT 0,
    total_duplicate_clips INTEGER DEFAULT 0,
    tracks_without_content INTEGER DEFAULT 0,
    has_arrangement_markers INTEGER DEFAULT 0,  -- boolean
    total_sections INTEGER DEFAULT 0,
    arrangement_structure TEXT,  -- e.g., 'intro-buildup-drop', 'verse-chorus'
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (version_id) REFERENCES versions(id) ON DELETE CASCADE
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_versions_project_id ON versions(project_id);
CREATE INDEX IF NOT EXISTS idx_versions_als_path ON versions(als_path);
CREATE INDEX IF NOT EXISTS idx_versions_health_score ON versions(health_score);
CREATE INDEX IF NOT EXISTS idx_issues_version_id ON issues(version_id);
CREATE INDEX IF NOT EXISTS idx_issues_severity ON issues(severity);
CREATE INDEX IF NOT EXISTS idx_changes_project_id ON changes(project_id);
CREATE INDEX IF NOT EXISTS idx_changes_before_version ON changes(before_version_id);
CREATE INDEX IF NOT EXISTS idx_changes_after_version ON changes(after_version_id);
CREATE INDEX IF NOT EXISTS idx_midi_stats_version_id ON midi_stats(version_id);
"""


class Database:
    """SQLite database handler for ALS Doctor."""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file. Defaults to data/projects.db
        """
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._connection: Optional[sqlite3.Connection] = None

    @contextmanager
    def connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init(self) -> bool:
        """
        Initialize the database schema.

        Creates the data directory if it doesn't exist and sets up
        the database tables. Safe to run multiple times (idempotent).

        Returns:
            True if initialization successful
        """
        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create tables
        with self.connection() as conn:
            conn.executescript(SCHEMA_SQL)

        return True

    def is_initialized(self) -> bool:
        """Check if the database exists and has the required schema."""
        if not self.db_path.exists():
            return False

        try:
            with self.connection() as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name IN (?, ?, ?, ?)",
                    ('projects', 'versions', 'issues', 'changes')
                )
                tables = [row['name'] for row in cursor.fetchall()]
                # Need at least projects, versions, issues (changes is optional for backwards compat)
                return len(tables) >= 3
        except sqlite3.Error:
            return False

    def get_stats(self) -> Dict[str, int]:
        """
        Get database statistics.

        Returns:
            Dict with counts for projects, versions, and issues
        """
        with self.connection() as conn:
            stats = {}

            cursor = conn.execute("SELECT COUNT(*) as count FROM projects")
            stats['projects'] = cursor.fetchone()['count']

            cursor = conn.execute("SELECT COUNT(*) as count FROM versions")
            stats['versions'] = cursor.fetchone()['count']

            cursor = conn.execute("SELECT COUNT(*) as count FROM issues")
            stats['issues'] = cursor.fetchone()['count']

            return stats

    def get_project_by_folder(self, folder_path: str) -> Optional[Project]:
        """
        Get a project by its folder path.

        Args:
            folder_path: Absolute path to project folder

        Returns:
            Project object or None if not found
        """
        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM projects WHERE folder_path = ?",
                (folder_path,)
            )
            row = cursor.fetchone()
            if row:
                return Project(
                    id=row['id'],
                    folder_path=row['folder_path'],
                    song_name=row['song_name'],
                    created_at=row['created_at']
                )
        return None

    def get_version_by_path(self, als_path: str) -> Optional[Version]:
        """
        Get a version by its .als file path.

        Args:
            als_path: Absolute path to .als file

        Returns:
            Version object or None if not found
        """
        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM versions WHERE als_path = ?",
                (als_path,)
            )
            row = cursor.fetchone()
            if row:
                return Version(
                    id=row['id'],
                    project_id=row['project_id'],
                    als_path=row['als_path'],
                    als_filename=row['als_filename'],
                    health_score=row['health_score'],
                    grade=row['grade'],
                    total_issues=row['total_issues'],
                    critical_issues=row['critical_issues'],
                    warning_issues=row['warning_issues'],
                    total_devices=row['total_devices'],
                    disabled_devices=row['disabled_devices'],
                    clutter_percentage=row['clutter_percentage'],
                    scanned_at=row['scanned_at']
                )
        return None


def db_init(db_path: Optional[Path] = None) -> Tuple[bool, str]:
    """
    Initialize the ALS Doctor database.

    Creates the data directory and SQLite database with the required schema.
    Safe to call multiple times - won't destroy existing data.

    Args:
        db_path: Optional custom path for the database

    Returns:
        Tuple of (success: bool, message: str)
    """
    db = Database(db_path)

    try:
        # Check if already initialized
        already_exists = db.is_initialized()

        # Initialize (create or verify schema)
        db.init()

        # Get stats to confirm
        stats = db.get_stats()

        if already_exists:
            return (
                True,
                f"Database already initialized at {db.db_path}\n"
                f"  Projects: {stats['projects']}\n"
                f"  Versions: {stats['versions']}\n"
                f"  Issues: {stats['issues']}"
            )
        else:
            return (
                True,
                f"Database created at {db.db_path}\n"
                f"  Tables: projects, versions, issues\n"
                f"  Ready to store scan results."
            )

    except Exception as e:
        return (False, f"Failed to initialize database: {e}")


def get_db(db_path: Optional[Path] = None) -> Database:
    """
    Get a database instance.

    Args:
        db_path: Optional custom path for the database

    Returns:
        Database instance
    """
    return Database(db_path)


# ==================== SCAN RESULT PERSISTENCE ====================


@dataclass
class ScanResultIssue:
    """An issue to persist from a scan result."""
    track_name: Optional[str]
    severity: str  # 'critical', 'warning', 'suggestion'
    category: str
    description: str
    fix_suggestion: Optional[str] = None


@dataclass
class ScanResult:
    """
    Scan result data to persist to the database.

    This is a simplified structure that can be populated from
    various analysis sources (BatchScanner, EffectChainDoctor, etc.)
    """
    als_path: str
    health_score: int
    grade: str
    total_issues: int
    critical_issues: int
    warning_issues: int
    total_devices: int
    disabled_devices: int
    clutter_percentage: float
    issues: List[ScanResultIssue] = field(default_factory=list)


def _calculate_grade(health_score: int) -> str:
    """Convert health score to letter grade."""
    if health_score >= 80:
        return 'A'
    elif health_score >= 60:
        return 'B'
    elif health_score >= 40:
        return 'C'
    elif health_score >= 20:
        return 'D'
    else:
        return 'F'


def persist_scan_result(
    scan_result: ScanResult,
    db_path: Optional[Path] = None
) -> Tuple[bool, str, Optional[int]]:
    """
    Persist a scan result to the database.

    Creates or updates project and version records based on the .als file path.
    Uses upsert semantics - re-scanning the same file updates the existing record.

    Args:
        scan_result: ScanResult object with analysis data
        db_path: Optional custom path for the database

    Returns:
        Tuple of (success: bool, message: str, version_id: Optional[int])
    """
    db = Database(db_path)

    if not db.is_initialized():
        return (False, "Database not initialized. Run 'als-doctor db init' first.", None)

    try:
        als_path = Path(scan_result.als_path).absolute()
        folder_path = str(als_path.parent)
        als_filename = als_path.name

        # Extract song name from parent folder name
        song_name = als_path.parent.name

        with db.connection() as conn:
            # Get or create project
            cursor = conn.execute(
                "SELECT id FROM projects WHERE folder_path = ?",
                (folder_path,)
            )
            row = cursor.fetchone()

            if row:
                project_id = row['id']
            else:
                cursor = conn.execute(
                    "INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
                    (folder_path, song_name)
                )
                project_id = cursor.lastrowid

            # Check if version already exists (upsert)
            cursor = conn.execute(
                "SELECT id FROM versions WHERE als_path = ?",
                (str(als_path),)
            )
            existing = cursor.fetchone()

            if existing:
                version_id = existing['id']
                # Update existing version
                conn.execute(
                    """UPDATE versions SET
                        health_score = ?,
                        grade = ?,
                        total_issues = ?,
                        critical_issues = ?,
                        warning_issues = ?,
                        total_devices = ?,
                        disabled_devices = ?,
                        clutter_percentage = ?,
                        scanned_at = CURRENT_TIMESTAMP
                    WHERE id = ?""",
                    (
                        scan_result.health_score,
                        scan_result.grade,
                        scan_result.total_issues,
                        scan_result.critical_issues,
                        scan_result.warning_issues,
                        scan_result.total_devices,
                        scan_result.disabled_devices,
                        scan_result.clutter_percentage,
                        version_id
                    )
                )
                # Delete existing issues for this version
                conn.execute("DELETE FROM issues WHERE version_id = ?", (version_id,))
                action = "updated"
            else:
                # Insert new version
                cursor = conn.execute(
                    """INSERT INTO versions (
                        project_id, als_path, als_filename,
                        health_score, grade, total_issues,
                        critical_issues, warning_issues,
                        total_devices, disabled_devices, clutter_percentage
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        project_id,
                        str(als_path),
                        als_filename,
                        scan_result.health_score,
                        scan_result.grade,
                        scan_result.total_issues,
                        scan_result.critical_issues,
                        scan_result.warning_issues,
                        scan_result.total_devices,
                        scan_result.disabled_devices,
                        scan_result.clutter_percentage
                    )
                )
                version_id = cursor.lastrowid
                action = "created"

            # Insert issues
            for issue in scan_result.issues:
                conn.execute(
                    """INSERT INTO issues (
                        version_id, track_name, severity,
                        category, description, fix_suggestion
                    ) VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        version_id,
                        issue.track_name,
                        issue.severity,
                        issue.category,
                        issue.description,
                        issue.fix_suggestion
                    )
                )

        return (
            True,
            f"Version {action}: {als_filename} (score: {scan_result.health_score}, grade: {scan_result.grade})",
            version_id
        )

    except Exception as e:
        return (False, f"Failed to persist scan result: {e}", None)


def persist_batch_scan_results(
    scan_results: List[ScanResult],
    db_path: Optional[Path] = None
) -> Tuple[int, int, List[str]]:
    """
    Persist multiple scan results to the database.

    Args:
        scan_results: List of ScanResult objects
        db_path: Optional custom path for the database

    Returns:
        Tuple of (success_count: int, failure_count: int, error_messages: List[str])
    """
    success_count = 0
    failure_count = 0
    errors = []

    for result in scan_results:
        success, message, _ = persist_scan_result(result, db_path)
        if success:
            success_count += 1
        else:
            failure_count += 1
            errors.append(f"{result.als_path}: {message}")

    return (success_count, failure_count, errors)


# ==================== PROJECT LISTING ====================


@dataclass
class ProjectSummary:
    """Summary of a project for listing purposes."""
    id: int
    song_name: str
    folder_path: str
    version_count: int
    best_score: int
    best_grade: str
    latest_score: int
    latest_grade: str
    latest_scanned_at: datetime
    trend: str  # 'up', 'down', 'stable', 'new'


def _calculate_trend(versions_data: List[Dict[str, Any]]) -> str:
    """
    Calculate trend based on recent versions.

    Compares the latest score against the previous score (or previous few).
    - 'up': Latest score is higher than previous
    - 'down': Latest score is lower than previous
    - 'stable': Latest score is same as previous (within 5 points)
    - 'new': Only one version exists

    Args:
        versions_data: List of version dicts ordered by scanned_at DESC

    Returns:
        Trend string: 'up', 'down', 'stable', or 'new'
    """
    if len(versions_data) <= 1:
        return 'new'

    latest_score = versions_data[0]['health_score']
    previous_score = versions_data[1]['health_score']

    diff = latest_score - previous_score

    if diff > 5:
        return 'up'
    elif diff < -5:
        return 'down'
    else:
        return 'stable'


def list_projects(
    db_path: Optional[Path] = None,
    sort_by: str = 'name'
) -> Tuple[List[ProjectSummary], Dict[str, int]]:
    """
    List all projects with summary statistics.

    Args:
        db_path: Optional custom path for the database
        sort_by: Sort order - 'name', 'score', or 'date'

    Returns:
        Tuple of (list of ProjectSummary objects, stats dict with totals)
    """
    db = Database(db_path)

    if not db.is_initialized():
        return ([], {'projects': 0, 'versions': 0})

    projects = []

    with db.connection() as conn:
        # Get all projects with their version counts
        cursor = conn.execute("""
            SELECT
                p.id,
                p.song_name,
                p.folder_path,
                COUNT(v.id) as version_count,
                MAX(v.health_score) as best_score,
                MAX(v.scanned_at) as latest_scanned_at
            FROM projects p
            LEFT JOIN versions v ON p.id = v.project_id
            GROUP BY p.id
            ORDER BY p.song_name
        """)

        project_rows = cursor.fetchall()

        for row in project_rows:
            project_id = row['id']

            # Get version details for trend calculation and latest/best info
            # Order by scanned_at DESC, then by id DESC to handle same-second inserts
            version_cursor = conn.execute("""
                SELECT health_score, grade, scanned_at
                FROM versions
                WHERE project_id = ?
                ORDER BY scanned_at DESC, id DESC
            """, (project_id,))

            versions = [dict(v) for v in version_cursor.fetchall()]

            if not versions:
                # Project with no versions (shouldn't happen, but handle gracefully)
                continue

            # Latest version is first (ordered by scanned_at DESC)
            latest = versions[0]

            # Find best version (highest score)
            best_version = max(versions, key=lambda v: v['health_score'])

            # Calculate trend
            trend = _calculate_trend(versions)

            projects.append(ProjectSummary(
                id=project_id,
                song_name=row['song_name'],
                folder_path=row['folder_path'],
                version_count=row['version_count'] or 0,
                best_score=best_version['health_score'],
                best_grade=_calculate_grade(best_version['health_score']),
                latest_score=latest['health_score'],
                latest_grade=_calculate_grade(latest['health_score']),
                latest_scanned_at=latest['scanned_at'] if isinstance(latest['scanned_at'], datetime) else datetime.fromisoformat(latest['scanned_at']),
                trend=trend
            ))

        # Get total stats
        total_projects = len(projects)
        total_versions = sum(p.version_count for p in projects)

    # Sort projects
    if sort_by == 'score':
        projects.sort(key=lambda p: (-p.best_score, p.song_name.lower()))
    elif sort_by == 'date':
        # Sort by date descending, then by id descending for same-second inserts
        projects.sort(key=lambda p: (-p.latest_scanned_at.timestamp(), -p.id))
    else:  # 'name' is default
        projects.sort(key=lambda p: p.song_name.lower())

    return (projects, {'projects': total_projects, 'versions': total_versions})


# ==================== PROJECT HISTORY ====================


@dataclass
class VersionHistory:
    """Version data for history display."""
    id: int
    als_filename: str
    als_path: str
    health_score: int
    grade: str
    total_issues: int
    scanned_at: datetime
    delta: Optional[int] = None  # Change from previous version
    is_best: bool = False  # True if this is the best scoring version


@dataclass
class ProjectHistory:
    """Complete history for a project."""
    project_id: int
    song_name: str
    folder_path: str
    versions: List[VersionHistory]
    best_version: Optional[VersionHistory] = None
    current_version: Optional[VersionHistory] = None


def _fuzzy_match_song(search_term: str, song_name: str) -> bool:
    """
    Check if search term fuzzy matches the song name.

    Matching rules:
    - Case insensitive
    - Search term can be a substring of song name
    - Search term can match start of any word in song name

    Args:
        search_term: User's search input
        song_name: Song name from database

    Returns:
        True if search matches
    """
    search_lower = search_term.lower().strip()
    song_lower = song_name.lower()

    # Exact match
    if search_lower == song_lower:
        return True

    # Substring match (e.g., "22" matches "22 Project")
    if search_lower in song_lower:
        return True

    # Word start match (e.g., "proj" matches "22 Project")
    words = song_lower.split()
    for word in words:
        if word.startswith(search_lower):
            return True

    return False


def find_project_by_name(
    search_term: str,
    db_path: Optional[Path] = None
) -> Optional[Tuple[int, str]]:
    """
    Find a project by fuzzy matching the song name.

    Args:
        search_term: User's search input
        db_path: Optional custom path for the database

    Returns:
        Tuple of (project_id, song_name) or None if not found
    """
    db = Database(db_path)

    if not db.is_initialized():
        return None

    with db.connection() as conn:
        cursor = conn.execute("SELECT id, song_name FROM projects")
        projects = cursor.fetchall()

        matches = []
        for row in projects:
            if _fuzzy_match_song(search_term, row['song_name']):
                matches.append((row['id'], row['song_name']))

        if not matches:
            return None

        # If multiple matches, prefer exact match, then shortest name
        for proj_id, name in matches:
            if name.lower() == search_term.lower():
                return (proj_id, name)

        # Return the shortest matching name (most specific)
        matches.sort(key=lambda x: len(x[1]))
        return matches[0]


def get_project_history(
    search_term: str,
    db_path: Optional[Path] = None
) -> Tuple[Optional[ProjectHistory], str]:
    """
    Get complete version history for a project.

    Args:
        search_term: Song name or partial match
        db_path: Optional custom path for the database

    Returns:
        Tuple of (ProjectHistory or None, message)
    """
    db = Database(db_path)

    if not db.is_initialized():
        return (None, "Database not initialized. Run 'als-doctor db init' first.")

    # Find the project
    match = find_project_by_name(search_term, db_path)

    if not match:
        return (None, f"No project found matching '{search_term}'")

    project_id, song_name = match

    with db.connection() as conn:
        # Get project details
        cursor = conn.execute(
            "SELECT folder_path FROM projects WHERE id = ?",
            (project_id,)
        )
        project_row = cursor.fetchone()
        folder_path = project_row['folder_path']

        # Get all versions ordered by scan date (oldest first)
        cursor = conn.execute("""
            SELECT id, als_filename, als_path, health_score, grade,
                   total_issues, scanned_at
            FROM versions
            WHERE project_id = ?
            ORDER BY scanned_at ASC, id ASC
        """, (project_id,))

        version_rows = cursor.fetchall()

        if not version_rows:
            return (None, f"No versions found for '{song_name}'")

        # Build version history with deltas
        versions = []
        best_score = -1
        best_version = None
        prev_score = None

        for row in version_rows:
            # Calculate delta from previous version
            delta = None
            if prev_score is not None:
                delta = row['health_score'] - prev_score
            prev_score = row['health_score']

            # Parse scanned_at timestamp
            scanned_at = row['scanned_at']
            if isinstance(scanned_at, str):
                scanned_at = datetime.fromisoformat(scanned_at)

            version = VersionHistory(
                id=row['id'],
                als_filename=row['als_filename'],
                als_path=row['als_path'],
                health_score=row['health_score'],
                grade=row['grade'],
                total_issues=row['total_issues'],
                scanned_at=scanned_at,
                delta=delta,
                is_best=False
            )
            versions.append(version)

            # Track best version (highest score, most recent if tied)
            if row['health_score'] > best_score:
                best_score = row['health_score']
                best_version = version

        # Mark best version
        if best_version:
            best_version.is_best = True

        # Current version is the last one (most recent)
        current_version = versions[-1] if versions else None

        return (ProjectHistory(
            project_id=project_id,
            song_name=song_name,
            folder_path=folder_path,
            versions=versions,
            best_version=best_version,
            current_version=current_version
        ), "OK")


# ==================== BEST VERSION ====================


@dataclass
class BestVersionResult:
    """Result of finding the best version of a project."""
    project_id: int
    song_name: str
    folder_path: str
    # Best version info
    best_als_path: str
    best_als_filename: str
    best_health_score: int
    best_grade: str
    best_total_issues: int
    best_scanned_at: datetime
    # Latest version info (for comparison)
    latest_als_path: str
    latest_als_filename: str
    latest_health_score: int
    latest_grade: str
    latest_total_issues: int
    latest_scanned_at: datetime
    # Comparison
    is_best_same_as_latest: bool
    health_delta: int  # best - latest (positive if best is better)
    issues_delta: int  # latest - best (positive if latest has more issues)


def get_best_version(
    search_term: str,
    db_path: Optional[Path] = None
) -> Tuple[Optional[BestVersionResult], str]:
    """
    Find the best (highest health score) version of a project.

    If multiple versions tie for the highest score, returns the most recent one.

    Args:
        search_term: Song name or partial match
        db_path: Optional custom path for the database

    Returns:
        Tuple of (BestVersionResult or None, message)
    """
    db = Database(db_path)

    if not db.is_initialized():
        return (None, "Database not initialized. Run 'als-doctor db init' first.")

    # Find the project
    match = find_project_by_name(search_term, db_path)

    if not match:
        return (None, f"No project found matching '{search_term}'")

    project_id, song_name = match

    with db.connection() as conn:
        # Get project details
        cursor = conn.execute(
            "SELECT folder_path FROM projects WHERE id = ?",
            (project_id,)
        )
        project_row = cursor.fetchone()
        folder_path = project_row['folder_path']

        # Get best version (highest score, most recent if tied)
        # ORDER BY health_score DESC, scanned_at DESC, id DESC
        cursor = conn.execute("""
            SELECT id, als_path, als_filename, health_score, grade,
                   total_issues, scanned_at
            FROM versions
            WHERE project_id = ?
            ORDER BY health_score DESC, scanned_at DESC, id DESC
            LIMIT 1
        """, (project_id,))

        best_row = cursor.fetchone()

        if not best_row:
            return (None, f"No versions found for '{song_name}'")

        # Get latest version (most recent scan)
        cursor = conn.execute("""
            SELECT id, als_path, als_filename, health_score, grade,
                   total_issues, scanned_at
            FROM versions
            WHERE project_id = ?
            ORDER BY scanned_at DESC, id DESC
            LIMIT 1
        """, (project_id,))

        latest_row = cursor.fetchone()

        # Parse timestamps
        best_scanned_at = best_row['scanned_at']
        if isinstance(best_scanned_at, str):
            best_scanned_at = datetime.fromisoformat(best_scanned_at)

        latest_scanned_at = latest_row['scanned_at']
        if isinstance(latest_scanned_at, str):
            latest_scanned_at = datetime.fromisoformat(latest_scanned_at)

        # Calculate comparisons
        is_same = best_row['als_path'] == latest_row['als_path']
        health_delta = best_row['health_score'] - latest_row['health_score']
        issues_delta = latest_row['total_issues'] - best_row['total_issues']

        return (BestVersionResult(
            project_id=project_id,
            song_name=song_name,
            folder_path=folder_path,
            best_als_path=best_row['als_path'],
            best_als_filename=best_row['als_filename'],
            best_health_score=best_row['health_score'],
            best_grade=best_row['grade'],
            best_total_issues=best_row['total_issues'],
            best_scanned_at=best_scanned_at,
            latest_als_path=latest_row['als_path'],
            latest_als_filename=latest_row['als_filename'],
            latest_health_score=latest_row['health_score'],
            latest_grade=latest_row['grade'],
            latest_total_issues=latest_row['total_issues'],
            latest_scanned_at=latest_scanned_at,
            is_best_same_as_latest=is_same,
            health_delta=health_delta,
            issues_delta=issues_delta
        ), "OK")


# ==================== LIBRARY STATUS ====================


@dataclass
class GradeDistribution:
    """Grade distribution for library status."""
    grade: str
    count: int
    percentage: float


@dataclass
class LibraryStatus:
    """Library status summary."""
    total_projects: int
    total_versions: int
    total_issues: int
    last_scan_date: Optional[datetime]
    grade_distribution: List[GradeDistribution]
    ready_to_release: List[Tuple[str, int, str]]  # (filename, score, song_name)
    needs_work: List[Tuple[str, int, str]]  # (filename, score, song_name)


def get_library_status(db_path: Optional[Path] = None) -> Tuple[Optional[LibraryStatus], str]:
    """
    Get library status summary with grade distribution and recommendations.

    Args:
        db_path: Optional custom path for the database

    Returns:
        Tuple of (LibraryStatus or None, message)
    """
    db = Database(db_path)

    if not db.is_initialized():
        return (None, "Database not initialized. Run 'als-doctor db init' first.")

    with db.connection() as conn:
        # Get basic stats
        cursor = conn.execute("SELECT COUNT(*) as count FROM projects")
        total_projects = cursor.fetchone()['count']

        cursor = conn.execute("SELECT COUNT(*) as count FROM versions")
        total_versions = cursor.fetchone()['count']

        cursor = conn.execute("SELECT COUNT(*) as count FROM issues")
        total_issues = cursor.fetchone()['count']

        # Get last scan date
        cursor = conn.execute("SELECT MAX(scanned_at) as last_scan FROM versions")
        row = cursor.fetchone()
        last_scan = row['last_scan'] if row else None
        if last_scan and isinstance(last_scan, str):
            last_scan = datetime.fromisoformat(last_scan)

        # Get grade distribution
        # We count the latest version per project for grade distribution
        cursor = conn.execute("""
            SELECT grade, COUNT(*) as count
            FROM versions
            GROUP BY grade
            ORDER BY
                CASE grade
                    WHEN 'A' THEN 1
                    WHEN 'B' THEN 2
                    WHEN 'C' THEN 3
                    WHEN 'D' THEN 4
                    WHEN 'F' THEN 5
                    ELSE 6
                END
        """)

        grade_rows = cursor.fetchall()

        grade_distribution = []
        for row in grade_rows:
            percentage = (row['count'] / total_versions * 100) if total_versions > 0 else 0.0
            grade_distribution.append(GradeDistribution(
                grade=row['grade'],
                count=row['count'],
                percentage=percentage
            ))

        # Fill in missing grades with 0
        existing_grades = {g.grade for g in grade_distribution}
        for grade in ['A', 'B', 'C', 'D', 'F']:
            if grade not in existing_grades:
                grade_distribution.append(GradeDistribution(
                    grade=grade,
                    count=0,
                    percentage=0.0
                ))

        # Sort by grade order
        grade_order = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'F': 4}
        grade_distribution.sort(key=lambda g: grade_order.get(g.grade, 5))

        # Get top 3 ready to release (Grade A, highest scores)
        cursor = conn.execute("""
            SELECT v.als_filename, v.health_score, p.song_name
            FROM versions v
            JOIN projects p ON v.project_id = p.id
            WHERE v.grade = 'A'
            ORDER BY v.health_score DESC, v.scanned_at DESC
            LIMIT 3
        """)
        ready_to_release = [(row['als_filename'], row['health_score'], row['song_name'])
                           for row in cursor.fetchall()]

        # Get top 3 needs work (Grade D-F, lowest scores)
        cursor = conn.execute("""
            SELECT v.als_filename, v.health_score, p.song_name
            FROM versions v
            JOIN projects p ON v.project_id = p.id
            WHERE v.grade IN ('D', 'F')
            ORDER BY v.health_score ASC, v.scanned_at DESC
            LIMIT 3
        """)
        needs_work = [(row['als_filename'], row['health_score'], row['song_name'])
                      for row in cursor.fetchall()]

        return (LibraryStatus(
            total_projects=total_projects,
            total_versions=total_versions,
            total_issues=total_issues,
            last_scan_date=last_scan,
            grade_distribution=grade_distribution,
            ready_to_release=ready_to_release,
            needs_work=needs_work
        ), "OK")


def generate_grade_bar(count: int, total: int, max_width: int = 20) -> str:
    """
    Generate an ASCII bar for grade distribution.

    Args:
        count: Number of versions with this grade
        total: Total number of versions
        max_width: Maximum bar width in characters

    Returns:
        ASCII bar string
    """
    if total == 0:
        return ""

    percentage = count / total
    bar_length = int(percentage * max_width)
    return "=" * bar_length if bar_length > 0 else ""


# ==================== CHANGE TRACKING ====================


@dataclass
class VersionChange:
    """A single change between versions."""
    id: int
    project_id: int
    before_version_id: int
    after_version_id: int
    change_type: str  # 'device_added', 'device_removed', 'device_enabled', 'device_disabled', 'track_added', 'track_removed'
    track_name: Optional[str]
    device_name: Optional[str]
    device_type: Optional[str]
    details: Optional[str]
    health_delta: int
    recorded_at: datetime
    # These are populated for display purposes
    likely_helped: bool = False  # True if change correlates with improvement


@dataclass
class VersionComparison:
    """Comparison between two specific versions."""
    before_version_id: int
    after_version_id: int
    before_filename: str
    after_filename: str
    before_health: int
    after_health: int
    health_delta: int
    before_issues: int
    after_issues: int
    issues_delta: int
    changes: List[VersionChange]
    is_improvement: bool


@dataclass
class ProjectChangesResult:
    """Result of getting changes for a project."""
    project_id: int
    song_name: str
    folder_path: str
    comparisons: List[VersionComparison]  # Each comparison is between consecutive versions


def track_changes(
    before_path: str,
    after_path: str,
    db_path: Optional[Path] = None
) -> Tuple[bool, str, Optional[int]]:
    """
    Compare two .als files and store the changes in the database.

    Uses project_differ to detect device and track changes between versions.

    Args:
        before_path: Path to the earlier version .als file
        after_path: Path to the later version .als file
        db_path: Optional custom path for the database

    Returns:
        Tuple of (success: bool, message: str, changes_count: int or None)
    """
    db = Database(db_path)

    if not db.is_initialized():
        return (False, "Database not initialized. Run 'als-doctor db init' first.", None)

    # Import project_differ here to avoid circular imports
    try:
        from project_differ import compare_projects
    except ImportError:
        return (False, "project_differ module not found", None)

    # Get version records from database
    before_version = db.get_version_by_path(before_path)
    after_version = db.get_version_by_path(after_path)

    if not before_version:
        return (False, f"Before version not found in database: {before_path}", None)
    if not after_version:
        return (False, f"After version not found in database: {after_path}", None)

    if before_version.project_id != after_version.project_id:
        return (False, "Versions are from different projects", None)

    project_id = before_version.project_id

    # Calculate health delta for this transition
    health_delta = after_version.health_score - before_version.health_score

    # Compare the projects
    try:
        diff = compare_projects(before_path, after_path)
    except Exception as e:
        return (False, f"Failed to compare projects: {e}", None)

    changes_count = 0

    with db.connection() as conn:
        # Delete existing changes for this version pair (in case of re-comparison)
        conn.execute(
            "DELETE FROM changes WHERE before_version_id = ? AND after_version_id = ?",
            (before_version.id, after_version.id)
        )

        # Insert device changes
        for device_change in diff.device_changes:
            conn.execute(
                """INSERT INTO changes (
                    project_id, before_version_id, after_version_id,
                    change_type, track_name, device_name, device_type,
                    details, health_delta
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    project_id,
                    before_version.id,
                    after_version.id,
                    f"device_{device_change.change_type}",  # e.g., device_added, device_removed
                    device_change.track_name,
                    device_change.device_name,
                    device_change.device_type,
                    device_change.details,
                    health_delta
                )
            )
            changes_count += 1

        # Insert track changes
        for track_change in diff.track_changes:
            conn.execute(
                """INSERT INTO changes (
                    project_id, before_version_id, after_version_id,
                    change_type, track_name, device_name, device_type,
                    details, health_delta
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    project_id,
                    before_version.id,
                    after_version.id,
                    f"track_{track_change.change_type}",  # e.g., track_added, track_removed
                    track_change.track_name,
                    None,
                    None,
                    track_change.details,
                    health_delta
                )
            )
            changes_count += 1

    return (
        True,
        f"Tracked {changes_count} change(s) between versions (health: {health_delta:+d})",
        changes_count
    )


def get_project_changes(
    search_term: str,
    from_version: Optional[str] = None,
    to_version: Optional[str] = None,
    db_path: Optional[Path] = None
) -> Tuple[Optional[ProjectChangesResult], str]:
    """
    Get changes between versions of a project.

    If from_version and to_version are not specified, shows all consecutive
    version comparisons in the database.

    Args:
        search_term: Song name or partial match
        from_version: Optional specific starting version filename
        to_version: Optional specific ending version filename
        db_path: Optional custom path for the database

    Returns:
        Tuple of (ProjectChangesResult or None, message)
    """
    db = Database(db_path)

    if not db.is_initialized():
        return (None, "Database not initialized. Run 'als-doctor db init' first.")

    # Find the project
    match = find_project_by_name(search_term, db_path)

    if not match:
        return (None, f"No project found matching '{search_term}'")

    project_id, song_name = match

    with db.connection() as conn:
        # Get project details
        cursor = conn.execute(
            "SELECT folder_path FROM projects WHERE id = ?",
            (project_id,)
        )
        project_row = cursor.fetchone()
        folder_path = project_row['folder_path']

        # Get all versions for this project ordered by scan date
        cursor = conn.execute("""
            SELECT id, als_filename, als_path, health_score, total_issues, scanned_at
            FROM versions
            WHERE project_id = ?
            ORDER BY scanned_at ASC, id ASC
        """, (project_id,))

        versions = cursor.fetchall()

        if len(versions) < 2:
            return (None, f"Need at least 2 versions to show changes. '{song_name}' has {len(versions)} version(s).")

        # Build version lookup for filtering
        version_by_filename = {v['als_filename']: v for v in versions}

        # Determine which version pairs to show
        if from_version and to_version:
            # Specific versions requested
            if from_version not in version_by_filename:
                return (None, f"Version not found: {from_version}")
            if to_version not in version_by_filename:
                return (None, f"Version not found: {to_version}")

            before = version_by_filename[from_version]
            after = version_by_filename[to_version]
            version_pairs = [(before, after)]
        elif from_version:
            # From a specific version to latest
            if from_version not in version_by_filename:
                return (None, f"Version not found: {from_version}")

            before = version_by_filename[from_version]
            after = versions[-1]  # Latest
            version_pairs = [(before, after)]
        elif to_version:
            # From first to a specific version
            if to_version not in version_by_filename:
                return (None, f"Version not found: {to_version}")

            before = versions[0]  # First
            after = version_by_filename[to_version]
            version_pairs = [(before, after)]
        else:
            # All consecutive pairs
            version_pairs = [(versions[i], versions[i+1]) for i in range(len(versions) - 1)]

        comparisons = []

        for before, after in version_pairs:
            # Get stored changes for this pair
            cursor = conn.execute("""
                SELECT id, project_id, before_version_id, after_version_id,
                       change_type, track_name, device_name, device_type,
                       details, health_delta, recorded_at
                FROM changes
                WHERE before_version_id = ? AND after_version_id = ?
                ORDER BY change_type, track_name
            """, (before['id'], after['id']))

            changes = []
            health_delta = after['health_score'] - before['health_score']

            for row in cursor.fetchall():
                recorded_at = row['recorded_at']
                if isinstance(recorded_at, str):
                    recorded_at = datetime.fromisoformat(recorded_at)

                # Determine if this change likely helped
                # For simplicity: if health went up and device was removed/disabled, it helped
                # If health went down and device was added, it hurt
                likely_helped = False
                if health_delta > 0:
                    # Improvement - removals and disables likely helped
                    if row['change_type'] in ('device_removed', 'device_disabled', 'track_removed'):
                        likely_helped = True
                elif health_delta < 0:
                    # Regression - additions might have hurt (inverse logic)
                    if row['change_type'] in ('device_added', 'device_enabled', 'track_added'):
                        likely_helped = False  # This hurt

                changes.append(VersionChange(
                    id=row['id'],
                    project_id=row['project_id'],
                    before_version_id=row['before_version_id'],
                    after_version_id=row['after_version_id'],
                    change_type=row['change_type'],
                    track_name=row['track_name'],
                    device_name=row['device_name'],
                    device_type=row['device_type'],
                    details=row['details'],
                    health_delta=row['health_delta'],
                    recorded_at=recorded_at,
                    likely_helped=likely_helped
                ))

            issues_delta = after['total_issues'] - before['total_issues']

            comparisons.append(VersionComparison(
                before_version_id=before['id'],
                after_version_id=after['id'],
                before_filename=before['als_filename'],
                after_filename=after['als_filename'],
                before_health=before['health_score'],
                after_health=after['health_score'],
                health_delta=health_delta,
                before_issues=before['total_issues'],
                after_issues=after['total_issues'],
                issues_delta=issues_delta,
                changes=changes,
                is_improvement=health_delta > 0
            ))

        return (ProjectChangesResult(
            project_id=project_id,
            song_name=song_name,
            folder_path=folder_path,
            comparisons=comparisons
        ), "OK")


def compute_and_store_all_changes(
    search_term: str,
    db_path: Optional[Path] = None
) -> Tuple[bool, str, int]:
    """
    Compute and store changes between all consecutive versions of a project.

    This is useful for populating the changes table for existing scanned data.

    Args:
        search_term: Song name or partial match
        db_path: Optional custom path for the database

    Returns:
        Tuple of (success: bool, message: str, total_changes: int)
    """
    db = Database(db_path)

    if not db.is_initialized():
        return (False, "Database not initialized. Run 'als-doctor db init' first.", 0)

    # Find the project
    match = find_project_by_name(search_term, db_path)

    if not match:
        return (False, f"No project found matching '{search_term}'", 0)

    project_id, song_name = match

    with db.connection() as conn:
        # Get all versions ordered by scan date
        cursor = conn.execute("""
            SELECT id, als_path, health_score
            FROM versions
            WHERE project_id = ?
            ORDER BY scanned_at ASC, id ASC
        """, (project_id,))

        versions = cursor.fetchall()

    if len(versions) < 2:
        return (True, f"'{song_name}' has {len(versions)} version(s) - need at least 2 to compare.", 0)

    total_changes = 0
    comparisons_made = 0

    for i in range(len(versions) - 1):
        before = versions[i]
        after = versions[i + 1]

        # Check if .als files exist
        before_path = Path(before['als_path'])
        after_path = Path(after['als_path'])

        if not before_path.exists():
            continue
        if not after_path.exists():
            continue

        success, message, changes = track_changes(
            str(before_path),
            str(after_path),
            db_path
        )

        if success and changes is not None:
            total_changes += changes
            comparisons_made += 1

    return (
        True,
        f"Computed changes for {comparisons_made} version pair(s) of '{song_name}' ({total_changes} total changes)",
        total_changes
    )


# ==================== INSIGHTS: CORRELATE CHANGES WITH OUTCOMES ====================


@dataclass
class InsightPattern:
    """A pattern discovered from analyzing changes across versions."""
    change_type: str  # e.g., 'device_added', 'device_removed'
    device_type: Optional[str]  # e.g., 'Eq8', 'Compressor', None for track changes
    device_name: Optional[str]  # Specific device name if relevant
    occurrence_count: int  # How many times this pattern occurred
    avg_health_delta: float  # Average health change when this happens
    total_health_delta: int  # Sum of all health deltas
    helps_health: bool  # True if typically improves health
    confidence: str  # 'LOW', 'MEDIUM', 'HIGH' based on sample size


@dataclass
class CommonMistake:
    """A common mistake pattern identified from the data."""
    description: str  # Human-readable description
    occurrence_count: int
    avg_health_impact: float  # Negative = bad
    example_devices: List[str]  # Example device names involved


@dataclass
class InsightsResult:
    """Result of analyzing patterns across all projects."""
    total_comparisons: int  # Number of version comparisons analyzed
    total_changes: int  # Total number of changes analyzed
    patterns_that_help: List[InsightPattern]  # Patterns with positive health impact
    patterns_that_hurt: List[InsightPattern]  # Patterns with negative health impact
    common_mistakes: List[CommonMistake]  # High frequency, negative impact patterns
    insufficient_data: bool  # True if < 10 comparisons
    message: str


def _get_confidence_level(count: int) -> str:
    """
    Determine confidence level based on sample size.

    Args:
        count: Number of occurrences

    Returns:
        'LOW' (2-4), 'MEDIUM' (5-9), or 'HIGH' (10+)
    """
    if count >= 10:
        return 'HIGH'
    elif count >= 5:
        return 'MEDIUM'
    else:
        return 'LOW'


def get_insights(db_path: Optional[Path] = None) -> Tuple[Optional[InsightsResult], str]:
    """
    Analyze patterns across all version changes to identify what helps and hurts health.

    Groups changes by type and device_type, calculates average health_delta per pattern,
    and identifies common mistakes (high frequency, negative impact).

    Args:
        db_path: Optional custom path for the database

    Returns:
        Tuple of (InsightsResult or None, message)
    """
    db = Database(db_path)

    if not db.is_initialized():
        return (None, "Database not initialized. Run 'als-doctor db init' first.")

    with db.connection() as conn:
        # Check if we have enough data
        cursor = conn.execute("""
            SELECT COUNT(DISTINCT before_version_id || '-' || after_version_id) as comparison_count
            FROM changes
        """)
        row = cursor.fetchone()
        total_comparisons = row['comparison_count'] if row else 0

        cursor = conn.execute("SELECT COUNT(*) as total FROM changes")
        row = cursor.fetchone()
        total_changes = row['total'] if row else 0

        if total_comparisons < 10:
            return (InsightsResult(
                total_comparisons=total_comparisons,
                total_changes=total_changes,
                patterns_that_help=[],
                patterns_that_hurt=[],
                common_mistakes=[],
                insufficient_data=True,
                message=f"Insufficient data: {total_comparisons} comparisons (need at least 10)"
            ), "OK")

        # Aggregate changes by type and device_type
        cursor = conn.execute("""
            SELECT
                change_type,
                device_type,
                COUNT(*) as occurrence_count,
                AVG(health_delta) as avg_health_delta,
                SUM(health_delta) as total_health_delta,
                GROUP_CONCAT(DISTINCT device_name) as device_names
            FROM changes
            GROUP BY change_type, device_type
            HAVING COUNT(*) >= 2
            ORDER BY AVG(health_delta) DESC
        """)

        patterns = []
        for row in cursor.fetchall():
            helps = row['avg_health_delta'] > 0
            confidence = _get_confidence_level(row['occurrence_count'])

            # Get example device names (limit to 3)
            device_names = row['device_names'] or ''
            example_devices = [d.strip() for d in device_names.split(',') if d.strip()][:3]

            patterns.append(InsightPattern(
                change_type=row['change_type'],
                device_type=row['device_type'],
                device_name=example_devices[0] if example_devices else None,
                occurrence_count=row['occurrence_count'],
                avg_health_delta=row['avg_health_delta'],
                total_health_delta=int(row['total_health_delta']),
                helps_health=helps,
                confidence=confidence
            ))

        # Separate patterns that help vs hurt
        patterns_that_help = [p for p in patterns if p.helps_health and p.avg_health_delta > 1]
        patterns_that_hurt = [p for p in patterns if not p.helps_health and p.avg_health_delta < -1]

        # Sort by impact magnitude
        patterns_that_help.sort(key=lambda p: (-p.avg_health_delta, -p.occurrence_count))
        patterns_that_hurt.sort(key=lambda p: (p.avg_health_delta, -p.occurrence_count))

        # Limit to top 10 each
        patterns_that_help = patterns_that_help[:10]
        patterns_that_hurt = patterns_that_hurt[:10]

        # Identify common mistakes (high frequency + negative impact)
        cursor = conn.execute("""
            SELECT
                change_type,
                device_type,
                COUNT(*) as occurrence_count,
                AVG(health_delta) as avg_health_delta,
                GROUP_CONCAT(DISTINCT device_name) as device_names
            FROM changes
            WHERE health_delta < 0
            GROUP BY change_type, device_type
            HAVING COUNT(*) >= 3
            ORDER BY COUNT(*) DESC, AVG(health_delta) ASC
            LIMIT 5
        """)

        common_mistakes = []
        for row in cursor.fetchall():
            change_type = row['change_type']
            device_type = row['device_type'] or 'unknown'

            # Generate human-readable description
            if change_type == 'device_added':
                description = f"Adding {device_type} devices tends to hurt health"
            elif change_type == 'device_removed':
                description = f"Removing {device_type} devices tends to hurt health"
            elif change_type == 'device_enabled':
                description = f"Enabling {device_type} devices tends to hurt health"
            elif change_type == 'device_disabled':
                description = f"Disabling {device_type} devices tends to hurt health"
            elif change_type == 'track_added':
                description = "Adding tracks tends to hurt health"
            elif change_type == 'track_removed':
                description = "Removing tracks tends to hurt health"
            else:
                description = f"{change_type} on {device_type} tends to hurt health"

            device_names = row['device_names'] or ''
            example_devices = [d.strip() for d in device_names.split(',') if d.strip()][:3]

            common_mistakes.append(CommonMistake(
                description=description,
                occurrence_count=row['occurrence_count'],
                avg_health_impact=row['avg_health_delta'],
                example_devices=example_devices
            ))

        return (InsightsResult(
            total_comparisons=total_comparisons,
            total_changes=total_changes,
            patterns_that_help=patterns_that_help,
            patterns_that_hurt=patterns_that_hurt,
            common_mistakes=common_mistakes,
            insufficient_data=False,
            message="OK"
        ), "OK")


# ==================== MIDI STATS PERSISTENCE ====================


@dataclass
class MIDIStats:
    """MIDI analysis statistics to persist."""
    version_id: int
    total_midi_tracks: int
    total_midi_clips: int
    total_notes: int
    total_empty_clips: int
    total_short_clips: int
    total_duplicate_clips: int
    tracks_without_content: int
    has_arrangement_markers: bool
    total_sections: int
    arrangement_structure: Optional[str]


def persist_midi_stats(
    stats: MIDIStats,
    db_path: Optional[Path] = None
) -> Tuple[bool, str]:
    """
    Persist MIDI analysis statistics to the database.

    Uses upsert semantics - if stats already exist for this version, they are updated.

    Args:
        stats: MIDIStats object with analysis data
        db_path: Optional custom path for the database

    Returns:
        Tuple of (success: bool, message: str)
    """
    db = Database(db_path)

    if not db.is_initialized():
        return (False, "Database not initialized. Run 'als-doctor db init' first.")

    try:
        with db.connection() as conn:
            # Check if stats already exist for this version
            cursor = conn.execute(
                "SELECT id FROM midi_stats WHERE version_id = ?",
                (stats.version_id,)
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing
                conn.execute(
                    """UPDATE midi_stats SET
                        total_midi_tracks = ?,
                        total_midi_clips = ?,
                        total_notes = ?,
                        total_empty_clips = ?,
                        total_short_clips = ?,
                        total_duplicate_clips = ?,
                        tracks_without_content = ?,
                        has_arrangement_markers = ?,
                        total_sections = ?,
                        arrangement_structure = ?,
                        analyzed_at = CURRENT_TIMESTAMP
                    WHERE version_id = ?""",
                    (
                        stats.total_midi_tracks,
                        stats.total_midi_clips,
                        stats.total_notes,
                        stats.total_empty_clips,
                        stats.total_short_clips,
                        stats.total_duplicate_clips,
                        stats.tracks_without_content,
                        1 if stats.has_arrangement_markers else 0,
                        stats.total_sections,
                        stats.arrangement_structure,
                        stats.version_id
                    )
                )
                return (True, "MIDI stats updated")
            else:
                # Insert new
                conn.execute(
                    """INSERT INTO midi_stats (
                        version_id, total_midi_tracks, total_midi_clips,
                        total_notes, total_empty_clips, total_short_clips,
                        total_duplicate_clips, tracks_without_content,
                        has_arrangement_markers, total_sections, arrangement_structure
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        stats.version_id,
                        stats.total_midi_tracks,
                        stats.total_midi_clips,
                        stats.total_notes,
                        stats.total_empty_clips,
                        stats.total_short_clips,
                        stats.total_duplicate_clips,
                        stats.tracks_without_content,
                        1 if stats.has_arrangement_markers else 0,
                        stats.total_sections,
                        stats.arrangement_structure
                    )
                )
                return (True, "MIDI stats saved")

    except Exception as e:
        return (False, f"Failed to persist MIDI stats: {e}")


def get_midi_stats(
    version_id: int,
    db_path: Optional[Path] = None
) -> Tuple[Optional[MIDIStats], str]:
    """
    Get MIDI stats for a specific version.

    Args:
        version_id: Version ID to look up
        db_path: Optional custom path for the database

    Returns:
        Tuple of (MIDIStats or None, message)
    """
    db = Database(db_path)

    if not db.is_initialized():
        return (None, "Database not initialized. Run 'als-doctor db init' first.")

    try:
        with db.connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM midi_stats WHERE version_id = ?""",
                (version_id,)
            )
            row = cursor.fetchone()

            if not row:
                return (None, f"No MIDI stats found for version {version_id}")

            return (MIDIStats(
                version_id=row['version_id'],
                total_midi_tracks=row['total_midi_tracks'],
                total_midi_clips=row['total_midi_clips'],
                total_notes=row['total_notes'],
                total_empty_clips=row['total_empty_clips'],
                total_short_clips=row['total_short_clips'],
                total_duplicate_clips=row['total_duplicate_clips'],
                tracks_without_content=row['tracks_without_content'],
                has_arrangement_markers=bool(row['has_arrangement_markers']),
                total_sections=row['total_sections'],
                arrangement_structure=row['arrangement_structure']
            ), "OK")

    except Exception as e:
        return (None, f"Failed to get MIDI stats: {e}")


# ==================== STYLE PROFILE ====================


@dataclass
class DeviceChainPattern:
    """A common device chain pattern found in high-quality versions."""
    track_type: str  # 'midi', 'audio', 'return', 'master'
    device_sequence: List[str]  # e.g., ['Eq8', 'Compressor2', 'Saturator']
    occurrence_count: int
    avg_health_score: float  # Average health of versions with this pattern
    example_tracks: List[str]  # Track names where this pattern was found


@dataclass
class DeviceUsageStats:
    """Statistics about device usage across high-quality versions."""
    device_type: str
    category: str  # From DeviceCategory
    total_count: int
    avg_per_version: float
    pct_versions_using: float  # Percentage of versions that use this device
    typical_position: Optional[float]  # Average position in chain (0-1)
    often_disabled: bool  # True if > 30% disabled


@dataclass
class TrackTypeProfile:
    """Profile for a specific track type (midi, audio, etc.)."""
    track_type: str
    avg_device_count: float
    min_device_count: int
    max_device_count: int
    common_device_chains: List[DeviceChainPattern]
    top_devices: List[DeviceUsageStats]


@dataclass
class StyleProfile:
    """Personal style profile built from high-quality versions."""
    generated_at: datetime
    total_versions_analyzed: int
    grade_a_versions: int  # Versions with score >= 80
    grade_df_versions: int  # Versions with score < 40
    avg_health_score_a: float
    avg_health_score_df: float

    # Device metrics
    avg_devices_per_track_a: float
    avg_devices_per_track_df: float
    avg_disabled_pct_a: float
    avg_disabled_pct_df: float

    # Track-type profiles
    track_profiles: Dict[str, TrackTypeProfile]

    # Common patterns in best work
    common_plugins: List[Tuple[str, int, float]]  # (name, count, pct_usage)

    # Recommendations based on comparison
    insights: List[str]

    # Raw data for JSON export
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class ProfileComparisonResult:
    """Result of comparing a file against the style profile."""
    als_path: str
    als_filename: str
    health_score: int
    grade: str

    # Deviations from profile
    device_count_deviation: float  # Positive = more than typical, negative = less
    disabled_pct_deviation: float

    # Missing common patterns
    missing_patterns: List[str]

    # Unusual patterns (not typical in best work)
    unusual_patterns: List[str]

    # Similarity score (0-100)
    similarity_score: int

    # Recommendations
    recommendations: List[str]


def _get_version_device_data(
    conn,
    version_ids: List[int]
) -> Dict[int, Dict[str, Any]]:
    """
    Get device data for a list of versions from the database.

    This queries the database for device information. Since we don't store
    full device data in the DB, we need to look at what we can infer from
    issues, MIDI stats, and basic version info.

    For a more complete profile, we'd need to re-parse the .als files or
    store device data at scan time.
    """
    version_data = {}

    for vid in version_ids:
        cursor = conn.execute("""
            SELECT v.*, p.song_name, p.folder_path
            FROM versions v
            JOIN projects p ON v.project_id = p.id
            WHERE v.id = ?
        """, (vid,))
        row = cursor.fetchone()

        if row:
            version_data[vid] = {
                'id': vid,
                'als_path': row['als_path'],
                'als_filename': row['als_filename'],
                'health_score': row['health_score'],
                'grade': row['grade'],
                'total_devices': row['total_devices'],
                'disabled_devices': row['disabled_devices'],
                'clutter_percentage': row['clutter_percentage'],
                'song_name': row['song_name'],
                'folder_path': row['folder_path'],
            }

            # Get issue counts by category
            issue_cursor = conn.execute("""
                SELECT category, COUNT(*) as count
                FROM issues
                WHERE version_id = ?
                GROUP BY category
            """, (vid,))
            version_data[vid]['issues_by_category'] = {
                r['category']: r['count'] for r in issue_cursor.fetchall()
            }

    return version_data


def get_style_profile(
    db_path: Optional[Path] = None,
    min_grade_a_versions: int = 3
) -> Tuple[Optional[StyleProfile], str]:
    """
    Build a personal style profile from analyzing Grade A versions (80+ score).

    Extracts common patterns from your best work to help identify what makes
    your projects successful.

    Args:
        db_path: Optional custom path for the database
        min_grade_a_versions: Minimum Grade A versions required (default: 3)

    Returns:
        Tuple of (StyleProfile or None, message)
    """
    db = Database(db_path)

    if not db.is_initialized():
        return (None, "Database not initialized. Run 'als-doctor db init' first.")

    with db.connection() as conn:
        # Count total versions
        cursor = conn.execute("SELECT COUNT(*) as count FROM versions")
        total_versions = cursor.fetchone()['count']

        if total_versions == 0:
            return (None, "No versions in database. Scan some projects first.")

        # Get Grade A versions (score >= 80)
        cursor = conn.execute("""
            SELECT id, als_path, als_filename, health_score, grade,
                   total_devices, disabled_devices, clutter_percentage,
                   total_issues, critical_issues, warning_issues,
                   scanned_at
            FROM versions
            WHERE health_score >= 80
            ORDER BY health_score DESC
        """)
        grade_a_rows = cursor.fetchall()

        # Get Grade D-F versions (score < 40)
        cursor = conn.execute("""
            SELECT id, als_path, als_filename, health_score, grade,
                   total_devices, disabled_devices, clutter_percentage,
                   total_issues, critical_issues, warning_issues,
                   scanned_at
            FROM versions
            WHERE health_score < 40
            ORDER BY health_score ASC
        """)
        grade_df_rows = cursor.fetchall()

        grade_a_count = len(grade_a_rows)
        grade_df_count = len(grade_df_rows)

        # Check if we have enough data
        if grade_a_count < min_grade_a_versions:
            return (None, f"Insufficient data: {grade_a_count} Grade A versions (need at least {min_grade_a_versions})")

        # Calculate Grade A averages
        avg_health_a = sum(r['health_score'] for r in grade_a_rows) / grade_a_count if grade_a_count > 0 else 0
        avg_devices_a = sum(r['total_devices'] for r in grade_a_rows) / grade_a_count if grade_a_count > 0 else 0
        avg_disabled_pct_a = sum(
            (r['disabled_devices'] / r['total_devices'] * 100) if r['total_devices'] > 0 else 0
            for r in grade_a_rows
        ) / grade_a_count if grade_a_count > 0 else 0

        # Calculate Grade D-F averages
        avg_health_df = sum(r['health_score'] for r in grade_df_rows) / grade_df_count if grade_df_count > 0 else 0
        avg_devices_df = sum(r['total_devices'] for r in grade_df_rows) / grade_df_count if grade_df_count > 0 else 0
        avg_disabled_pct_df = sum(
            (r['disabled_devices'] / r['total_devices'] * 100) if r['total_devices'] > 0 else 0
            for r in grade_df_rows
        ) / grade_df_count if grade_df_count > 0 else 0

        # Get issue category patterns for Grade A
        grade_a_ids = [r['id'] for r in grade_a_rows]
        grade_df_ids = [r['id'] for r in grade_df_rows]

        # Get common issue categories in Grade D-F that are absent in Grade A
        cursor = conn.execute("""
            SELECT category, COUNT(*) as count, AVG(
                CASE severity
                    WHEN 'critical' THEN 3
                    WHEN 'warning' THEN 2
                    ELSE 1
                END
            ) as avg_severity
            FROM issues
            WHERE version_id IN ({})
            GROUP BY category
            ORDER BY count DESC
        """.format(','.join('?' * len(grade_df_ids))), grade_df_ids) if grade_df_ids else []

        common_df_issues = []
        if grade_df_ids:
            common_df_issues = [(r['category'], r['count'], r['avg_severity']) for r in cursor.fetchall()]

        # Generate insights
        insights = []

        # Device count insight
        if grade_a_count > 0 and grade_df_count > 0:
            device_diff = avg_devices_df - avg_devices_a
            if device_diff > 5:
                insights.append(f"Your best work averages {avg_devices_a:.0f} devices - lower-quality versions have {device_diff:.0f} more on average")
            elif device_diff < -5:
                insights.append(f"Your lower-quality versions use fewer devices ({avg_devices_df:.0f}) than your best work ({avg_devices_a:.0f})")

        # Disabled devices insight
        if avg_disabled_pct_df > avg_disabled_pct_a + 10:
            insights.append(f"Lower-quality versions have {avg_disabled_pct_df:.0f}% disabled devices vs {avg_disabled_pct_a:.0f}% in best work - clean up unused devices")

        # Clutter insight
        avg_clutter_a = sum(r['clutter_percentage'] for r in grade_a_rows) / grade_a_count if grade_a_count > 0 else 0
        avg_clutter_df = sum(r['clutter_percentage'] for r in grade_df_rows) / grade_df_count if grade_df_count > 0 else 0

        if avg_clutter_df > avg_clutter_a + 15:
            insights.append(f"Lower-quality versions have {avg_clutter_df:.0f}% clutter vs {avg_clutter_a:.0f}% in best work")

        # Issue category insights
        for category, count, avg_sev in common_df_issues[:3]:
            if avg_sev > 2:
                insights.append(f"'{category}' issues are common in lower-quality versions (avg severity {avg_sev:.1f})")

        # Score distribution insight
        if grade_a_count > 0:
            insights.append(f"Your best versions score {avg_health_a:.0f} on average - aim for 80+ to maintain quality")

        # Build raw data for JSON export
        raw_data = {
            'generated_at': datetime.now().isoformat(),
            'total_versions_analyzed': total_versions,
            'grade_a_versions': grade_a_count,
            'grade_df_versions': grade_df_count,
            'avg_health_score_a': round(avg_health_a, 1),
            'avg_health_score_df': round(avg_health_df, 1),
            'avg_devices_per_track_a': round(avg_devices_a, 1),
            'avg_devices_per_track_df': round(avg_devices_df, 1),
            'avg_disabled_pct_a': round(avg_disabled_pct_a, 1),
            'avg_disabled_pct_df': round(avg_disabled_pct_df, 1),
            'avg_clutter_a': round(avg_clutter_a, 1),
            'avg_clutter_df': round(avg_clutter_df, 1),
            'grade_a_files': [r['als_filename'] for r in grade_a_rows],
            'grade_df_files': [r['als_filename'] for r in grade_df_rows],
            'insights': insights,
        }

        return (StyleProfile(
            generated_at=datetime.now(),
            total_versions_analyzed=total_versions,
            grade_a_versions=grade_a_count,
            grade_df_versions=grade_df_count,
            avg_health_score_a=round(avg_health_a, 1),
            avg_health_score_df=round(avg_health_df, 1),
            avg_devices_per_track_a=round(avg_devices_a, 1),
            avg_devices_per_track_df=round(avg_devices_df, 1) if grade_df_count > 0 else 0,
            avg_disabled_pct_a=round(avg_disabled_pct_a, 1),
            avg_disabled_pct_df=round(avg_disabled_pct_df, 1),
            track_profiles={},  # Would require .als re-parsing for detailed data
            common_plugins=[],  # Would require plugin tracking at scan time
            insights=insights,
            raw_data=raw_data
        ), "OK")


def save_profile_to_json(
    profile: StyleProfile,
    output_path: Optional[Path] = None
) -> Tuple[bool, str]:
    """
    Save style profile to a JSON file.

    Args:
        profile: StyleProfile to save
        output_path: Optional output path (default: data/profile.json)

    Returns:
        Tuple of (success: bool, message: str)
    """
    import json

    if output_path is None:
        output_path = DEFAULT_DB_PATH.parent / "profile.json"

    try:
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Use raw_data if available, otherwise build from profile
        data = profile.raw_data if profile.raw_data else {
            'generated_at': profile.generated_at.isoformat(),
            'total_versions_analyzed': profile.total_versions_analyzed,
            'grade_a_versions': profile.grade_a_versions,
            'grade_df_versions': profile.grade_df_versions,
            'avg_health_score_a': profile.avg_health_score_a,
            'avg_health_score_df': profile.avg_health_score_df,
            'avg_devices_per_track_a': profile.avg_devices_per_track_a,
            'avg_devices_per_track_df': profile.avg_devices_per_track_df,
            'avg_disabled_pct_a': profile.avg_disabled_pct_a,
            'avg_disabled_pct_df': profile.avg_disabled_pct_df,
            'insights': profile.insights,
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        return (True, f"Profile saved to {output_path}")

    except Exception as e:
        return (False, f"Failed to save profile: {e}")


def load_profile_from_json(
    profile_path: Optional[Path] = None
) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Load style profile from a JSON file.

    Args:
        profile_path: Path to profile.json (default: data/profile.json)

    Returns:
        Tuple of (profile data dict or None, message)
    """
    import json

    if profile_path is None:
        profile_path = DEFAULT_DB_PATH.parent / "profile.json"

    if not profile_path.exists():
        return (None, f"Profile not found: {profile_path}")

    try:
        with open(profile_path, 'r') as f:
            data = json.load(f)
        return (data, "OK")
    except Exception as e:
        return (None, f"Failed to load profile: {e}")


def compare_file_against_profile(
    als_path: str,
    db_path: Optional[Path] = None
) -> Tuple[Optional[ProfileComparisonResult], str]:
    """
    Compare a scanned .als file against the style profile.

    The file must already be scanned and in the database.

    Args:
        als_path: Path to the .als file (must be in database)
        db_path: Optional custom path for the database

    Returns:
        Tuple of (ProfileComparisonResult or None, message)
    """
    db = Database(db_path)

    if not db.is_initialized():
        return (None, "Database not initialized. Run 'als-doctor db init' first.")

    # Get the version from database
    version = db.get_version_by_path(als_path)
    if not version:
        return (None, f"File not found in database: {als_path}. Run 'als-doctor diagnose {als_path} --save' first.")

    # Get or generate profile
    profile_data, msg = load_profile_from_json()

    if profile_data is None:
        # Try to generate profile
        profile, msg = get_style_profile(db_path)
        if profile is None:
            return (None, msg)
        profile_data = profile.raw_data

    # Calculate deviations
    avg_devices_a = profile_data.get('avg_devices_a', version.total_devices)
    avg_disabled_pct_a = profile_data.get('avg_disabled_pct_a', 0)

    disabled_pct = (version.disabled_devices / version.total_devices * 100) if version.total_devices > 0 else 0

    device_deviation = version.total_devices - avg_devices_a
    disabled_deviation = disabled_pct - avg_disabled_pct_a

    # Generate recommendations
    recommendations = []
    unusual_patterns = []
    missing_patterns = []

    if device_deviation > 10:
        recommendations.append(f"You have {device_deviation:.0f} more devices than your typical best work - consider simplifying")
        unusual_patterns.append("High device count")
    elif device_deviation < -10:
        missing_patterns.append("Typical device count for your best work")

    if disabled_deviation > 15:
        recommendations.append(f"Disabled devices are {disabled_deviation:.0f}% higher than in your best work - clean up unused devices")
        unusual_patterns.append("Many disabled devices")

    if version.clutter_percentage > profile_data.get('avg_clutter_a', 0) + 20:
        recommendations.append("Clutter is higher than your best work - remove unused devices")
        unusual_patterns.append("High clutter percentage")

    if version.health_score < 80:
        target = profile_data.get('avg_health_a', 85)
        gap = target - version.health_score
        recommendations.append(f"Score is {gap:.0f} points below your typical best work ({target:.0f})")

    # Calculate similarity score
    # Based on how close key metrics are to the profile
    similarity = 100

    # Penalize for device count deviation (max -30)
    if avg_devices_a > 0:
        device_pct_diff = abs(device_deviation) / avg_devices_a * 100
        similarity -= min(30, device_pct_diff / 2)

    # Penalize for disabled percentage deviation (max -30)
    similarity -= min(30, abs(disabled_deviation))

    # Penalize for low health score (max -40)
    if version.health_score < 80:
        similarity -= min(40, (80 - version.health_score))

    similarity = max(0, int(similarity))

    return (ProfileComparisonResult(
        als_path=als_path,
        als_filename=version.als_filename,
        health_score=version.health_score,
        grade=version.grade,
        device_count_deviation=round(device_deviation, 1),
        disabled_pct_deviation=round(disabled_deviation, 1),
        missing_patterns=missing_patterns,
        unusual_patterns=unusual_patterns,
        similarity_score=similarity,
        recommendations=recommendations
    ), "OK")


# ==================== TEMPLATE COMPARISON ====================


# Default templates directory
DEFAULT_TEMPLATES_PATH = Path(__file__).parent.parent.parent.parent / "templates"


@dataclass
class DeviceChainTemplate:
    """Represents a device chain in a template."""
    device_type: str  # Raw Ableton device type (Eq8, Compressor2, etc.)
    category: str  # From DeviceCategory
    name: Optional[str] = None  # User-assigned name


@dataclass
class TrackTemplate:
    """Template for a single track's structure."""
    track_type: str  # 'midi', 'audio', 'return', 'master', 'group'
    name_pattern: Optional[str] = None  # Optional regex or wildcard pattern
    device_chain: List[DeviceChainTemplate] = field(default_factory=list)


@dataclass
class ProjectTemplate:
    """A complete project template for comparison."""
    id: str  # Unique identifier
    name: str  # Display name
    description: str
    created_at: datetime
    source_file: Optional[str]  # Original .als file path if created from scan

    # Track structure
    tracks: List[TrackTemplate] = field(default_factory=list)

    # High-level metrics
    total_tracks: int = 0
    total_devices: int = 0
    device_categories: Dict[str, int] = field(default_factory=dict)  # category -> count

    # Template tags for categorization
    tags: List[str] = field(default_factory=list)  # e.g., ['trance', 'mixdown', 'mastering']


@dataclass
class TemplateComparisonResult:
    """Result of comparing a file against a template."""
    template_name: str
    template_id: str
    similarity_score: int  # 0-100

    # Track comparison
    matched_tracks: int  # Tracks that match the template pattern
    extra_tracks: int  # Tracks not in template
    missing_tracks: int  # Template tracks not found in file

    # Device chain comparison
    matching_device_chains: List[str]  # Track names with matching chains
    deviating_device_chains: List[Tuple[str, str]]  # (track_name, deviation_description)

    # Category comparison
    category_differences: Dict[str, int]  # category -> difference from template

    # Recommendations
    recommendations: List[str]


def _get_templates_index_path(templates_path: Optional[Path] = None) -> Path:
    """Get the path to templates/index.json."""
    if templates_path is None:
        templates_path = DEFAULT_TEMPLATES_PATH
    return templates_path / "index.json"


def _load_templates_index(templates_path: Optional[Path] = None) -> Tuple[Optional[Dict], str]:
    """
    Load the templates index.

    Returns:
        Tuple of (index dict or None, message)
    """
    import json

    index_path = _get_templates_index_path(templates_path)

    if not index_path.exists():
        # Create empty index
        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(index_path, 'w') as f:
                json.dump({"version": "1.0", "templates": []}, f, indent=2)
        except Exception as e:
            return (None, f"Failed to create templates index: {e}")

    try:
        with open(index_path, 'r') as f:
            index = json.load(f)
        return (index, "OK")
    except Exception as e:
        return (None, f"Failed to load templates index: {e}")


def _save_templates_index(index: Dict, templates_path: Optional[Path] = None) -> Tuple[bool, str]:
    """
    Save the templates index.

    Returns:
        Tuple of (success, message)
    """
    import json

    index_path = _get_templates_index_path(templates_path)

    try:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(index_path, 'w') as f:
            json.dump(index, f, indent=2)
        return (True, "OK")
    except Exception as e:
        return (False, f"Failed to save templates index: {e}")


def list_templates(
    templates_path: Optional[Path] = None
) -> Tuple[List[ProjectTemplate], str]:
    """
    List all available templates.

    Returns:
        Tuple of (list of ProjectTemplate, message)
    """
    index, msg = _load_templates_index(templates_path)

    if index is None:
        return ([], msg)

    templates = []
    for t in index.get('templates', []):
        try:
            created_at = datetime.fromisoformat(t.get('created_at', datetime.now().isoformat()))
        except (ValueError, TypeError):
            created_at = datetime.now()

        templates.append(ProjectTemplate(
            id=t.get('id', ''),
            name=t.get('name', 'Unnamed'),
            description=t.get('description', ''),
            created_at=created_at,
            source_file=t.get('source_file'),
            tracks=[TrackTemplate(
                track_type=tr.get('track_type', 'audio'),
                name_pattern=tr.get('name_pattern'),
                device_chain=[DeviceChainTemplate(
                    device_type=d.get('device_type', 'Unknown'),
                    category=d.get('category', 'unknown'),
                    name=d.get('name')
                ) for d in tr.get('device_chain', [])]
            ) for tr in t.get('tracks', [])],
            total_tracks=t.get('total_tracks', 0),
            total_devices=t.get('total_devices', 0),
            device_categories=t.get('device_categories', {}),
            tags=t.get('tags', [])
        ))

    return (templates, "OK")


def get_template_by_name(
    name: str,
    templates_path: Optional[Path] = None
) -> Tuple[Optional[ProjectTemplate], str]:
    """
    Get a template by name (case-insensitive, fuzzy match).

    Returns:
        Tuple of (ProjectTemplate or None, message)
    """
    templates, msg = list_templates(templates_path)

    if not templates:
        return (None, "No templates found")

    # Try exact match first (case-insensitive)
    name_lower = name.lower()
    for t in templates:
        if t.name.lower() == name_lower:
            return (t, "OK")

    # Try partial match
    for t in templates:
        if name_lower in t.name.lower():
            return (t, "OK")

    # Try ID match
    for t in templates:
        if t.id == name:
            return (t, "OK")

    return (None, f"No template found matching '{name}'")


def add_template_from_file(
    als_path: str,
    name: str,
    description: str = "",
    tags: Optional[List[str]] = None,
    templates_path: Optional[Path] = None,
    db_path: Optional[Path] = None
) -> Tuple[Optional[ProjectTemplate], str]:
    """
    Create a template from an .als file structure.

    The file must be scanned first (in the database) or the .als file must exist.

    Args:
        als_path: Path to the .als file
        name: Template name
        description: Optional description
        tags: Optional list of tags
        templates_path: Optional custom templates directory
        db_path: Optional custom database path

    Returns:
        Tuple of (ProjectTemplate or None, message)
    """
    import json
    import uuid

    # Try to analyze the .als file
    als_file = Path(als_path)
    if not als_file.exists():
        return (None, f"File not found: {als_path}")

    if als_file.suffix.lower() != '.als':
        return (None, "File must be an Ableton Live Set (.als)")

    # Parse the .als file to extract structure
    try:
        # Import the device chain analyzer to get track/device info
        import sys
        src_path = Path(__file__).parent
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from device_chain_analyzer import analyze_als_devices

        analysis = analyze_als_devices(str(als_file))

        # Build template from analysis
        tracks = []
        device_categories = {}
        total_devices = 0

        for track in analysis.tracks:
            device_chain = []
            for device in track.devices:
                device_chain.append({
                    'device_type': device.device_type,
                    'category': device.category.value if hasattr(device.category, 'value') else str(device.category),
                    'name': device.name
                })

                # Count by category
                cat = device.category.value if hasattr(device.category, 'value') else str(device.category)
                device_categories[cat] = device_categories.get(cat, 0) + 1
                total_devices += 1

            tracks.append({
                'track_type': track.track_type,
                'name_pattern': track.track_name,
                'device_chain': device_chain
            })

        # Generate unique ID
        template_id = f"template_{uuid.uuid4().hex[:8]}"

        # Create template data
        template_data = {
            'id': template_id,
            'name': name,
            'description': description,
            'created_at': datetime.now().isoformat(),
            'source_file': str(als_file.absolute()),
            'tracks': tracks,
            'total_tracks': len(tracks),
            'total_devices': total_devices,
            'device_categories': device_categories,
            'tags': tags or []
        }

        # Load index and add template
        index, msg = _load_templates_index(templates_path)
        if index is None:
            return (None, msg)

        # Check for duplicate name
        for existing in index.get('templates', []):
            if existing.get('name', '').lower() == name.lower():
                return (None, f"Template with name '{name}' already exists")

        index['templates'].append(template_data)

        # Save index
        success, msg = _save_templates_index(index, templates_path)
        if not success:
            return (None, msg)

        # Return the created template
        return (ProjectTemplate(
            id=template_id,
            name=name,
            description=description,
            created_at=datetime.now(),
            source_file=str(als_file.absolute()),
            tracks=[TrackTemplate(
                track_type=tr['track_type'],
                name_pattern=tr.get('name_pattern'),
                device_chain=[DeviceChainTemplate(
                    device_type=d['device_type'],
                    category=d['category'],
                    name=d.get('name')
                ) for d in tr['device_chain']]
            ) for tr in tracks],
            total_tracks=len(tracks),
            total_devices=total_devices,
            device_categories=device_categories,
            tags=tags or []
        ), f"Template '{name}' created with {len(tracks)} tracks and {total_devices} devices")

    except Exception as e:
        return (None, f"Failed to analyze .als file: {e}")


def remove_template(
    name_or_id: str,
    templates_path: Optional[Path] = None
) -> Tuple[bool, str]:
    """
    Remove a template by name or ID.

    Returns:
        Tuple of (success, message)
    """
    index, msg = _load_templates_index(templates_path)
    if index is None:
        return (False, msg)

    # Find template
    name_lower = name_or_id.lower()
    found_idx = None

    for i, t in enumerate(index.get('templates', [])):
        if t.get('id') == name_or_id or t.get('name', '').lower() == name_lower:
            found_idx = i
            break

    if found_idx is None:
        return (False, f"Template not found: {name_or_id}")

    removed = index['templates'].pop(found_idx)

    success, msg = _save_templates_index(index, templates_path)
    if not success:
        return (False, msg)

    return (True, f"Template '{removed.get('name', name_or_id)}' removed")


def compare_template(
    als_path: str,
    template_name: str,
    templates_path: Optional[Path] = None
) -> Tuple[Optional[TemplateComparisonResult], str]:
    """
    Compare an .als file against a template.

    Args:
        als_path: Path to the .als file to compare
        template_name: Name or ID of the template to compare against
        templates_path: Optional custom templates directory

    Returns:
        Tuple of (TemplateComparisonResult or None, message)
    """
    # Get the template
    template, msg = get_template_by_name(template_name, templates_path)
    if template is None:
        return (None, msg)

    # Parse the .als file
    als_file = Path(als_path)
    if not als_file.exists():
        return (None, f"File not found: {als_path}")

    try:
        import sys
        src_path = Path(__file__).parent
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from device_chain_analyzer import analyze_als_devices

        analysis = analyze_als_devices(str(als_file))

        # Compare tracks
        file_tracks = {t.track_name: t for t in analysis.tracks}
        template_tracks = {t.name_pattern: t for t in template.tracks if t.name_pattern}

        matched_tracks = 0
        extra_tracks = 0
        missing_tracks = 0

        matching_device_chains = []
        deviating_device_chains = []

        # Check template tracks against file
        for track_name, track_template in template_tracks.items():
            if track_name in file_tracks:
                matched_tracks += 1

                # Compare device chains
                file_track = file_tracks[track_name]
                file_chain = [d.device_type for d in file_track.devices]
                template_chain = [d.device_type for d in track_template.device_chain]

                if file_chain == template_chain:
                    matching_device_chains.append(track_name)
                else:
                    # Describe deviation
                    if len(file_chain) > len(template_chain):
                        deviation = f"Extra devices: {len(file_chain) - len(template_chain)}"
                    elif len(file_chain) < len(template_chain):
                        deviation = f"Missing devices: {len(template_chain) - len(file_chain)}"
                    else:
                        deviation = "Different device order/types"
                    deviating_device_chains.append((track_name, deviation))
            else:
                missing_tracks += 1

        # Count extra tracks
        for track_name in file_tracks:
            if track_name not in template_tracks:
                extra_tracks += 1

        # Compare device categories
        file_categories = {}
        for track in analysis.tracks:
            for device in track.devices:
                cat = device.category.value if hasattr(device.category, 'value') else str(device.category)
                file_categories[cat] = file_categories.get(cat, 0) + 1

        category_differences = {}
        all_categories = set(file_categories.keys()) | set(template.device_categories.keys())
        for cat in all_categories:
            file_count = file_categories.get(cat, 0)
            template_count = template.device_categories.get(cat, 0)
            diff = file_count - template_count
            if diff != 0:
                category_differences[cat] = diff

        # Calculate similarity score
        similarity = 100

        # Track matching penalty (max -30)
        if template.total_tracks > 0:
            track_match_pct = matched_tracks / template.total_tracks * 100
            similarity -= max(0, min(30, 30 - track_match_pct * 0.3))

        # Extra tracks penalty (max -20)
        if extra_tracks > 0:
            similarity -= min(20, extra_tracks * 2)

        # Missing tracks penalty (max -30)
        if missing_tracks > 0:
            similarity -= min(30, missing_tracks * 5)

        # Device chain deviation penalty (max -20)
        chain_deviation_pct = len(deviating_device_chains) / max(1, len(template_tracks)) * 100
        similarity -= min(20, chain_deviation_pct / 5)

        similarity = max(0, int(similarity))

        # Generate recommendations
        recommendations = []

        if missing_tracks > 0:
            recommendations.append(f"Add {missing_tracks} missing track(s) from template")

        if extra_tracks > 5:
            recommendations.append(f"Consider removing {extra_tracks - 5} extra tracks to match template structure")

        if deviating_device_chains:
            recommendations.append(f"Review device chains on {len(deviating_device_chains)} track(s)")

        for cat, diff in sorted(category_differences.items(), key=lambda x: abs(x[1]), reverse=True)[:3]:
            if diff > 3:
                recommendations.append(f"Reduce {cat} devices by {diff}")
            elif diff < -3:
                recommendations.append(f"Add {abs(diff)} more {cat} device(s)")

        if similarity >= 80:
            recommendations.append("Good match! Minor adjustments may help align with template")
        elif similarity < 50:
            recommendations.append("Significant differences from template - review structure")

        return (TemplateComparisonResult(
            template_name=template.name,
            template_id=template.id,
            similarity_score=similarity,
            matched_tracks=matched_tracks,
            extra_tracks=extra_tracks,
            missing_tracks=missing_tracks,
            matching_device_chains=matching_device_chains,
            deviating_device_chains=deviating_device_chains,
            category_differences=category_differences,
            recommendations=recommendations
        ), "OK")

    except Exception as e:
        return (None, f"Failed to compare against template: {e}")


# ==================== SMART RECOMMENDATIONS ENGINE ====================


@dataclass
class SmartRecommendation:
    """A recommendation with confidence scoring based on user history."""
    severity: str  # 'critical', 'warning', 'suggestion'
    category: str  # Issue category
    description: str  # Issue description
    recommendation: str  # Fix suggestion
    track_name: Optional[str] = None

    # Smart scoring
    priority: int = 0  # Higher = more important (0-100)
    confidence: str = 'LOW'  # 'LOW', 'MEDIUM', 'HIGH'
    confidence_reason: str = ''  # Why we're confident

    # History context
    helped_before: bool = False  # This fix has improved health for user before
    times_helped: int = 0  # How many times this type of fix helped
    avg_improvement: float = 0.0  # Average health improvement

    # User behavior
    previously_ignored: bool = False  # User has ignored this recommendation before
    times_ignored: int = 0  # How many times ignored


@dataclass
class SmartDiagnoseResult:
    """Result of smart diagnosis with prioritized recommendations."""
    als_path: str
    als_filename: str
    health_score: int
    grade: str
    total_issues: int

    # Prioritized recommendations
    recommendations: List[SmartRecommendation]

    # Context
    has_sufficient_history: bool  # True if 20+ versions in DB
    versions_analyzed: int  # Total versions used for insights
    profile_available: bool  # True if style profile is available

    # Summary stats
    critical_count: int = 0
    warning_count: int = 0
    suggestion_count: int = 0

    # Comparison to profile
    profile_similarity: Optional[int] = None  # Similarity to best work (if profile available)


def _count_database_versions(db_path: Optional[Path] = None) -> int:
    """Count total versions in the database."""
    db = Database(db_path)

    if not db.is_initialized():
        return 0

    with db.connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) as count FROM versions")
        row = cursor.fetchone()
        return row['count'] if row else 0


def has_sufficient_history(db_path: Optional[Path] = None, min_versions: int = 20) -> bool:
    """
    Check if the database has sufficient history for smart recommendations.

    Args:
        db_path: Optional custom path for the database
        min_versions: Minimum number of versions required (default: 20)

    Returns:
        True if database has at least min_versions versions
    """
    return _count_database_versions(db_path) >= min_versions


def _get_pattern_history(
    db_path: Optional[Path] = None
) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """
    Build a lookup of historical patterns from changes.

    Returns:
        Dict mapping (change_type, device_type) to stats about that pattern
    """
    db = Database(db_path)

    if not db.is_initialized():
        return {}

    patterns = {}

    with db.connection() as conn:
        # Get aggregated stats for each change pattern
        cursor = conn.execute("""
            SELECT
                change_type,
                device_type,
                COUNT(*) as occurrence_count,
                AVG(health_delta) as avg_health_delta,
                SUM(CASE WHEN health_delta > 0 THEN 1 ELSE 0 END) as times_helped,
                SUM(CASE WHEN health_delta < 0 THEN 1 ELSE 0 END) as times_hurt
            FROM changes
            GROUP BY change_type, device_type
            HAVING COUNT(*) >= 2
        """)

        for row in cursor.fetchall():
            key = (row['change_type'], row['device_type'] or 'unknown')
            patterns[key] = {
                'occurrence_count': row['occurrence_count'],
                'avg_health_delta': row['avg_health_delta'],
                'times_helped': row['times_helped'],
                'times_hurt': row['times_hurt']
            }

    return patterns


def _calculate_recommendation_priority(
    issue: ScanResultIssue,
    pattern_history: Dict[Tuple[str, str], Dict[str, Any]],
    profile_data: Optional[Dict] = None
) -> Tuple[int, str, bool, int, float]:
    """
    Calculate priority score for a recommendation based on history.

    Args:
        issue: The issue to prioritize
        pattern_history: Historical pattern data
        profile_data: Optional style profile data

    Returns:
        Tuple of (priority, confidence, helped_before, times_helped, avg_improvement)
    """
    base_priority = 50  # Default priority
    confidence = 'LOW'
    confidence_reason = 'Default priority'
    helped_before = False
    times_helped = 0
    avg_improvement = 0.0

    # Severity-based base priority
    if issue.severity == 'critical':
        base_priority = 90
    elif issue.severity == 'warning':
        base_priority = 60
    else:
        base_priority = 30

    # Check if we have historical data for this type of issue
    # Map issue categories to change types
    category_to_change_type = {
        'clutter': ('device_disabled', None),
        'disabled_device': ('device_disabled', None),
        'redundant_effect': ('device_added', None),
        'chain_order': ('device_added', None),
    }

    # Try to find matching historical pattern
    change_type, device_type = category_to_change_type.get(issue.category, (None, None))

    if change_type:
        # Look for any matching pattern
        for (ct, dt), stats in pattern_history.items():
            if ct == change_type or (change_type in ct):
                if stats['times_helped'] > stats['times_hurt']:
                    helped_before = True
                    times_helped = stats['times_helped']
                    avg_improvement = stats['avg_health_delta']

                    # Boost priority based on success rate
                    success_rate = stats['times_helped'] / max(1, stats['occurrence_count'])
                    priority_boost = int(success_rate * 20)
                    base_priority = min(100, base_priority + priority_boost)

                    if stats['occurrence_count'] >= 10:
                        confidence = 'HIGH'
                        confidence_reason = f"This fix helped {times_helped} times with avg +{avg_improvement:.1f} health"
                    elif stats['occurrence_count'] >= 5:
                        confidence = 'MEDIUM'
                        confidence_reason = f"This fix helped {times_helped} times"
                    else:
                        confidence = 'LOW'
                        confidence_reason = f"Limited data ({stats['occurrence_count']} occurrences)"

                    break
                elif stats['times_hurt'] > stats['times_helped']:
                    # This type of fix has hurt before - lower priority
                    base_priority = max(10, base_priority - 20)
                    confidence_reason = f"Caution: similar fixes hurt health {stats['times_hurt']} times"

    # Adjust based on profile if available
    if profile_data:
        # If this issue is common in Grade D-F work, boost priority
        # (means fixing it is important for best work)
        pass  # Profile integration - could expand later

    return base_priority, confidence, helped_before, times_helped, avg_improvement


def smart_diagnose(
    als_path: str,
    scan_result: Optional['ScanResult'] = None,
    db_path: Optional[Path] = None
) -> Tuple[Optional[SmartDiagnoseResult], str]:
    """
    Perform smart diagnosis using historical data to prioritize recommendations.

    Prioritizes fixes based on:
    - What has helped the user before (from change tracking)
    - The user's style profile (patterns from best work)
    - Issue severity
    - Historical success rates

    Falls back to standard recommendations if insufficient history.

    Args:
        als_path: Path to the .als file to diagnose
        scan_result: Optional pre-computed scan result (if None, will analyze file)
        db_path: Optional custom path for the database

    Returns:
        Tuple of (SmartDiagnoseResult or None, message)
    """
    from pathlib import Path as PathLib

    db = Database(db_path)

    if not db.is_initialized():
        return (None, "Database not initialized. Run 'als-doctor db init' first.")

    als_path_obj = PathLib(als_path).absolute()

    # Get or compute scan result
    if scan_result is None:
        # Check if file was already scanned
        version = db.get_version_by_path(str(als_path_obj))
        if version:
            # Create a basic scan result from version data
            # We need the issues from the database
            with db.connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM issues WHERE version_id = ?",
                    (version.id,)
                )
                issues = []
                for row in cursor.fetchall():
                    issues.append(ScanResultIssue(
                        track_name=row['track_name'],
                        severity=row['severity'],
                        category=row['category'],
                        description=row['description'],
                        fix_suggestion=row['fix_suggestion']
                    ))

            scan_result = ScanResult(
                als_path=str(als_path_obj),
                health_score=version.health_score,
                grade=version.grade,
                total_issues=version.total_issues,
                critical_issues=version.critical_issues,
                warning_issues=version.warning_issues,
                total_devices=version.total_devices,
                disabled_devices=version.disabled_devices,
                clutter_percentage=version.clutter_percentage,
                issues=issues
            )
        else:
            return (None, f"File not found in database. Run 'als-doctor diagnose \"{als_path}\" --save' first.")

    # Get historical pattern data
    pattern_history = _get_pattern_history(db_path)

    # Check version count for sufficient history
    versions_analyzed = _count_database_versions(db_path)
    has_history = versions_analyzed >= 20

    # Try to load profile data
    profile_data = None
    profile_available = False
    profile_similarity = None

    try:
        profile, _ = get_style_profile(db_path)
        if profile and profile.grade_a_versions >= 3:
            profile_available = True
            profile_data = profile.raw_data

            # Calculate similarity if version is in database
            if db.get_version_by_path(str(als_path_obj)):
                comparison, _ = compare_file_against_profile(str(als_path_obj), db_path)
                if comparison:
                    profile_similarity = comparison.similarity_score
    except Exception:
        pass  # Profile not available, continue without it

    # Build smart recommendations
    smart_recommendations = []

    for issue in scan_result.issues:
        priority, confidence, helped_before, times_helped, avg_improvement = _calculate_recommendation_priority(
            issue, pattern_history, profile_data
        )

        confidence_reason = ''
        if helped_before:
            confidence_reason = f"Similar fixes improved health {times_helped} time(s), avg +{avg_improvement:.1f}"
        elif has_history and not helped_before:
            confidence_reason = "No historical data for this issue type"
        else:
            confidence_reason = "Limited history data - using default priority"

        smart_recommendations.append(SmartRecommendation(
            severity=issue.severity,
            category=issue.category,
            description=issue.description,
            recommendation=issue.fix_suggestion or "Review and fix this issue",
            track_name=issue.track_name,
            priority=priority,
            confidence=confidence,
            confidence_reason=confidence_reason,
            helped_before=helped_before,
            times_helped=times_helped,
            avg_improvement=avg_improvement,
            previously_ignored=False,  # Would need to track user actions
            times_ignored=0
        ))

    # Sort by priority (highest first)
    smart_recommendations.sort(key=lambda r: (-r.priority, r.severity != 'critical', r.severity != 'warning'))

    # Count by severity
    critical_count = len([r for r in smart_recommendations if r.severity == 'critical'])
    warning_count = len([r for r in smart_recommendations if r.severity == 'warning'])
    suggestion_count = len([r for r in smart_recommendations if r.severity == 'suggestion'])

    return (SmartDiagnoseResult(
        als_path=str(als_path_obj),
        als_filename=als_path_obj.name,
        health_score=scan_result.health_score,
        grade=scan_result.grade,
        total_issues=scan_result.total_issues,
        recommendations=smart_recommendations,
        has_sufficient_history=has_history,
        versions_analyzed=versions_analyzed,
        profile_available=profile_available,
        critical_count=critical_count,
        warning_count=warning_count,
        suggestion_count=suggestion_count,
        profile_similarity=profile_similarity
    ), "OK")
