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


@dataclass
class UserActivity:
    """Represents a user work session on a project."""
    id: int
    project_id: int
    worked_at: datetime
    hidden_until: Optional[datetime] = None
    notes: Optional[str] = None


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

-- Reference comparisons table: stores comparison results for learning
CREATE TABLE IF NOT EXISTS reference_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    version_id INTEGER,
    user_file_path TEXT NOT NULL,
    reference_file_path TEXT NOT NULL,
    reference_name TEXT,  -- Human-readable name of reference
    genre TEXT,  -- Genre tag for filtering
    overall_similarity_score REAL,  -- 0-100 similarity score
    loudness_diff_db REAL,
    balance_score REAL,  -- 0-100 mix balance similarity
    compared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL,
    FOREIGN KEY (version_id) REFERENCES versions(id) ON DELETE SET NULL
);

-- Reference stem comparisons: detailed per-stem data from comparisons
CREATE TABLE IF NOT EXISTS reference_stem_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comparison_id INTEGER NOT NULL,
    stem_type TEXT NOT NULL,  -- 'vocals', 'drums', 'bass', 'other'
    rms_diff_db REAL,
    lufs_diff REAL,
    spectral_centroid_diff_hz REAL,
    stereo_width_diff_pct REAL,
    bass_diff_pct REAL,
    mid_diff_pct REAL,
    high_diff_pct REAL,
    severity TEXT,  -- 'good', 'minor', 'moderate', 'significant'
    FOREIGN KEY (comparison_id) REFERENCES reference_comparisons(id) ON DELETE CASCADE
);

-- Reference recommendations: tracks which recommendations from comparisons helped
CREATE TABLE IF NOT EXISTS reference_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comparison_id INTEGER NOT NULL,
    recommendation TEXT NOT NULL,
    category TEXT,  -- 'eq', 'dynamics', 'balance', 'stereo'
    stem_type TEXT,  -- Which stem this applies to
    was_applied INTEGER DEFAULT 0,  -- 1 if user applied this recommendation
    helped_score INTEGER,  -- 1 if helped, -1 if hurt, 0 if neutral, NULL if unknown
    FOREIGN KEY (comparison_id) REFERENCES reference_comparisons(id) ON DELETE CASCADE
);

-- User activity table: tracks when user worked on projects
CREATE TABLE IF NOT EXISTS user_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    worked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hidden_until TIMESTAMP,  -- Hide from "work on" suggestions until this date
    notes TEXT,  -- Optional user notes about what they worked on
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
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
CREATE INDEX IF NOT EXISTS idx_reference_comparisons_project_id ON reference_comparisons(project_id);
CREATE INDEX IF NOT EXISTS idx_reference_stem_comparisons_comparison_id ON reference_stem_comparisons(comparison_id);
CREATE INDEX IF NOT EXISTS idx_user_activity_project_id ON user_activity(project_id);
CREATE INDEX IF NOT EXISTS idx_user_activity_worked_at ON user_activity(worked_at);
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
class ChangeImpactAssessment:
    """Assessment of a change's impact based on historical data."""
    category: str  # 'helped', 'hurt', 'neutral', 'unknown'
    confidence: str  # 'HIGH', 'MEDIUM', 'LOW', 'NONE'
    confidence_score: float  # 0.0 to 1.0
    historical_occurrences: int  # How many times this change type occurred before
    historical_avg_delta: float  # Average health delta for this change type
    historical_success_rate: float  # % of times this change type improved health
    reasoning: str  # Explanation of the assessment


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
    # Enhanced Phase 2 fields
    impact_assessment: Optional[ChangeImpactAssessment] = None  # Per-change confidence scoring
    change_intent: str = 'unknown'  # 'likely_fix' (addresses known issue), 'experiment' (new change), 'unknown'
    addressed_issue: Optional[str] = None  # Description of issue this change likely addresses


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


# ==================== PHASE 2: ENHANCED CHANGE IMPACT ASSESSMENT ====================


def _assess_change_impact(
    change_type: str,
    device_type: Optional[str],
    health_delta: int,
    db_path: Optional[Path] = None
) -> ChangeImpactAssessment:
    """
    Assess the impact of a specific change based on historical patterns.

    Uses historical data to determine if this type of change typically
    helps or hurts health, with confidence scoring.

    Args:
        change_type: Type of change (e.g., 'device_added', 'device_removed')
        device_type: Type of device involved (e.g., 'Eq8', 'Compressor')
        health_delta: The actual health delta for this specific change
        db_path: Optional custom path for the database

    Returns:
        ChangeImpactAssessment with categorization and confidence
    """
    db = Database(db_path)

    if not db.is_initialized():
        return ChangeImpactAssessment(
            category='unknown',
            confidence='NONE',
            confidence_score=0.0,
            historical_occurrences=0,
            historical_avg_delta=0.0,
            historical_success_rate=0.0,
            reasoning="Database not initialized"
        )

    # Query historical data for this change pattern
    with db.connection() as conn:
        cursor = conn.execute("""
            SELECT
                COUNT(*) as occurrence_count,
                AVG(health_delta) as avg_delta,
                SUM(CASE WHEN health_delta > 0 THEN 1 ELSE 0 END) as times_helped,
                SUM(CASE WHEN health_delta < 0 THEN 1 ELSE 0 END) as times_hurt,
                SUM(CASE WHEN health_delta = 0 THEN 1 ELSE 0 END) as times_neutral
            FROM changes
            WHERE change_type = ? AND (device_type = ? OR (device_type IS NULL AND ? IS NULL))
        """, (change_type, device_type, device_type))

        row = cursor.fetchone()

    if not row or row['occurrence_count'] == 0:
        # No historical data - use the actual delta to categorize
        if health_delta > 2:
            category = 'helped'
        elif health_delta < -2:
            category = 'hurt'
        else:
            category = 'neutral'

        return ChangeImpactAssessment(
            category=category,
            confidence='NONE',
            confidence_score=0.0,
            historical_occurrences=0,
            historical_avg_delta=0.0,
            historical_success_rate=0.5,
            reasoning=f"No historical data. Based on observed delta: {health_delta:+d}"
        )

    occurrences = row['occurrence_count']
    avg_delta = row['avg_delta'] or 0.0
    times_helped = row['times_helped'] or 0
    times_hurt = row['times_hurt'] or 0
    times_neutral = row['times_neutral'] or 0

    # Calculate success rate
    if occurrences > 0:
        success_rate = times_helped / occurrences
    else:
        success_rate = 0.5

    # Determine confidence based on sample size
    if occurrences >= 10:
        confidence = 'HIGH'
        confidence_score = min(1.0, 0.7 + (occurrences - 10) * 0.01)
    elif occurrences >= 5:
        confidence = 'MEDIUM'
        confidence_score = 0.4 + (occurrences - 5) * 0.06
    elif occurrences >= 2:
        confidence = 'LOW'
        confidence_score = 0.1 + (occurrences - 2) * 0.1
    else:
        confidence = 'NONE'
        confidence_score = 0.0

    # Categorize based on historical patterns AND actual outcome
    # Weight historical patterns more heavily with higher confidence
    historical_category = 'neutral'
    if avg_delta > 2:
        historical_category = 'helped'
    elif avg_delta < -2:
        historical_category = 'hurt'

    actual_category = 'neutral'
    if health_delta > 2:
        actual_category = 'helped'
    elif health_delta < -2:
        actual_category = 'hurt'

    # Combine historical and actual assessment
    # If they agree, high confidence in the category
    # If they disagree, lower confidence
    if historical_category == actual_category:
        category = historical_category
        reasoning_prefix = "Consistent with historical pattern"
    elif confidence in ('HIGH', 'MEDIUM'):
        # Trust historical pattern more
        category = historical_category
        reasoning_prefix = f"Historical pattern suggests '{historical_category}' (actual was '{actual_category}')"
        confidence_score *= 0.8  # Reduce confidence slightly due to disagreement
    else:
        # Trust actual outcome more when low historical data
        category = actual_category
        reasoning_prefix = f"Based on actual outcome (limited history)"

    # Build reasoning string
    device_str = device_type or 'unknown device'
    action_str = change_type.replace('device_', '').replace('track_', '')

    reasoning = (
        f"{reasoning_prefix}. "
        f"Historically, {action_str} {device_str}: "
        f"{times_helped} helped, {times_hurt} hurt, {times_neutral} neutral "
        f"(avg {avg_delta:+.1f} health). "
        f"This instance: {health_delta:+d}."
    )

    return ChangeImpactAssessment(
        category=category,
        confidence=confidence,
        confidence_score=confidence_score,
        historical_occurrences=occurrences,
        historical_avg_delta=avg_delta,
        historical_success_rate=success_rate,
        reasoning=reasoning
    )


def _determine_change_intent(
    change_type: str,
    track_name: Optional[str],
    device_name: Optional[str],
    device_type: Optional[str],
    before_version_id: int,
    db_path: Optional[Path] = None
) -> Tuple[str, Optional[str]]:
    """
    Determine the intent behind a change based on issues from the previous version.

    A change is categorized as:
    - 'likely_fix': The change addresses a known issue from the previous version
    - 'experiment': The change doesn't address any known issue (user is trying something new)
    - 'unknown': Cannot determine intent

    Args:
        change_type: Type of change (device_added, device_removed, etc.)
        track_name: Track where the change occurred
        device_name: Name of the device involved
        device_type: Type/category of device
        before_version_id: ID of the version before this change
        db_path: Optional custom path for the database

    Returns:
        Tuple of (intent: str, addressed_issue: Optional[str])
    """
    db = Database(db_path)

    if not db.is_initialized():
        return ('unknown', None)

    # Get issues from the previous version
    with db.connection() as conn:
        cursor = conn.execute(
            "SELECT track_name, category, description, fix_suggestion FROM issues WHERE version_id = ?",
            (before_version_id,)
        )
        issues = cursor.fetchall()

    if not issues:
        # No issues in previous version - this is an experiment
        return ('experiment', None)

    # Define issue categories that are addressed by specific change types
    # device_removed or device_disabled can address: clutter, redundant_effect, wrong_effect
    # device_enabled can address: nothing typically (usually an experiment)
    # device_added can address: missing_effect (if we had such a category)

    addressed_issue = None

    for issue in issues:
        issue_track = issue['track_name']
        issue_category = issue['category']
        issue_description = issue['description']
        fix_suggestion = issue['fix_suggestion'] or ''

        # Check if this change addresses this issue
        # Track must match (or be a general change)
        track_matches = (
            not track_name or
            not issue_track or
            track_name.lower() == issue_track.lower() or
            track_name.lower() in issue_track.lower() or
            issue_track.lower() in track_name.lower()
        )

        if not track_matches:
            continue

        # Check if change type matches issue category
        is_fix = False

        # Device removal/disable addresses clutter issues
        if change_type in ('device_removed', 'device_disabled'):
            if issue_category in ('clutter', 'disabled_device'):
                is_fix = True
                addressed_issue = f"Addressed: {issue_description[:80]}"
            elif issue_category == 'redundant_effect':
                # Check if the removed device matches the redundant device
                if device_name and device_name.lower() in issue_description.lower():
                    is_fix = True
                    addressed_issue = f"Addressed: {issue_description[:80]}"
            elif issue_category == 'wrong_effect':
                # Check if the removed device was flagged as wrong
                if device_name and device_name.lower() in issue_description.lower():
                    is_fix = True
                    addressed_issue = f"Addressed: {issue_description[:80]}"
            elif issue_category == 'duplicate':
                # Removing a duplicate device
                if device_type and device_type.lower() in issue_description.lower():
                    is_fix = True
                    addressed_issue = f"Addressed: {issue_description[:80]}"
                elif device_name and device_name.lower() in issue_description.lower():
                    is_fix = True
                    addressed_issue = f"Addressed: {issue_description[:80]}"

        # Device enabling addresses issues where a device was needed
        elif change_type == 'device_enabled':
            # Less common, but could address issues about disabled important effects
            if 'enable' in fix_suggestion.lower() or 'disabled' in issue_description.lower():
                if device_name and device_name.lower() in issue_description.lower():
                    is_fix = True
                    addressed_issue = f"Addressed: {issue_description[:80]}"

        # Device addition can address suggestions to add effects
        elif change_type == 'device_added':
            if 'add' in fix_suggestion.lower() or 'missing' in issue_description.lower():
                if device_type and device_type.lower() in fix_suggestion.lower():
                    is_fix = True
                    addressed_issue = f"Addressed: {issue_description[:80]}"

        # Track removal addresses track-level issues
        elif change_type == 'track_removed':
            if issue_track and track_name and track_name.lower() == issue_track.lower():
                # Removing a problematic track
                is_fix = True
                addressed_issue = f"Addressed track issues: {issue_description[:60]}"

        if is_fix:
            return ('likely_fix', addressed_issue)

    # No matching issues found - this is an experiment
    return ('experiment', None)


def get_project_changes_enhanced(
    search_term: str,
    from_version: Optional[str] = None,
    to_version: Optional[str] = None,
    db_path: Optional[Path] = None
) -> Tuple[Optional[ProjectChangesResult], str]:
    """
    Get changes between versions with enhanced impact assessment.

    Same as get_project_changes but adds per-change confidence scoring
    and more accurate categorization based on historical patterns.

    Args:
        search_term: Song name or partial match
        from_version: Optional specific starting version filename
        to_version: Optional specific ending version filename
        db_path: Optional custom path for the database

    Returns:
        Tuple of (ProjectChangesResult or None, message)
    """
    # Get base changes
    result, message = get_project_changes(search_term, from_version, to_version, db_path)

    if result is None:
        return (result, message)

    # Enhance each change with impact assessment and intent detection
    for comparison in result.comparisons:
        for change in comparison.changes:
            # Add impact assessment
            assessment = _assess_change_impact(
                change.change_type,
                change.device_type,
                change.health_delta,
                db_path
            )
            change.impact_assessment = assessment

            # Update likely_helped based on assessment
            change.likely_helped = assessment.category == 'helped'

            # Determine change intent (likely_fix vs experiment)
            intent, addressed_issue = _determine_change_intent(
                change.change_type,
                change.track_name,
                change.device_name,
                change.device_type,
                change.before_version_id,
                db_path
            )
            change.change_intent = intent
            change.addressed_issue = addressed_issue

    return (result, "OK")


@dataclass
class ChangePattern:
    """A learned pattern about what changes help or hurt health."""
    change_type: str
    device_type: Optional[str]
    device_name_pattern: Optional[str]  # For specific device names (e.g., "Reverb", "Compressor")

    # Statistics
    total_occurrences: int
    times_helped: int
    times_hurt: int
    times_neutral: int
    avg_health_delta: float
    std_deviation: float  # Consistency of impact

    # Contextual factors
    best_context: Optional[str]  # When this change works best (e.g., "after mixing", "during cleanup")
    worst_context: Optional[str]  # When this change tends to fail

    # Recommendation
    recommendation: str  # e.g., "Usually beneficial", "Exercise caution", "Avoid unless necessary"
    confidence: str  # 'HIGH', 'MEDIUM', 'LOW'


def get_learned_patterns(
    db_path: Optional[Path] = None,
    min_occurrences: int = 3
) -> Tuple[List[ChangePattern], str]:
    """
    Get learned patterns from historical change data.

    Analyzes all tracked changes to identify patterns that consistently
    help or hurt health scores, with statistical confidence.

    Args:
        db_path: Optional custom path for the database
        min_occurrences: Minimum occurrences to consider a pattern (default: 3)

    Returns:
        Tuple of (List[ChangePattern], message)
    """
    db = Database(db_path)

    if not db.is_initialized():
        return ([], "Database not initialized")

    patterns = []

    with db.connection() as conn:
        # Query aggregated statistics by change_type and device_type
        cursor = conn.execute("""
            SELECT
                change_type,
                device_type,
                COUNT(*) as total_occurrences,
                SUM(CASE WHEN health_delta > 2 THEN 1 ELSE 0 END) as times_helped,
                SUM(CASE WHEN health_delta < -2 THEN 1 ELSE 0 END) as times_hurt,
                SUM(CASE WHEN health_delta BETWEEN -2 AND 2 THEN 1 ELSE 0 END) as times_neutral,
                AVG(health_delta) as avg_delta,
                GROUP_CONCAT(DISTINCT device_name) as device_names
            FROM changes
            GROUP BY change_type, device_type
            HAVING COUNT(*) >= ?
            ORDER BY ABS(AVG(health_delta)) DESC
        """, (min_occurrences,))

        for row in cursor.fetchall():
            total = row['total_occurrences']
            helped = row['times_helped'] or 0
            hurt = row['times_hurt'] or 0
            neutral = row['times_neutral'] or 0
            avg_delta = row['avg_delta'] or 0.0

            # Calculate success rate
            success_rate = helped / total if total > 0 else 0

            # Determine confidence
            if total >= 10:
                confidence = 'HIGH'
            elif total >= 5:
                confidence = 'MEDIUM'
            else:
                confidence = 'LOW'

            # Generate recommendation
            if avg_delta > 3 and success_rate > 0.6:
                recommendation = "Usually beneficial - consider applying"
            elif avg_delta > 0 and success_rate > 0.5:
                recommendation = "Slightly beneficial on average"
            elif avg_delta < -3 and success_rate < 0.4:
                recommendation = "Often harmful - avoid unless necessary"
            elif avg_delta < 0 and success_rate < 0.5:
                recommendation = "Exercise caution - mixed results"
            else:
                recommendation = "Neutral impact - depends on context"

            # Parse device names for pattern
            device_names = row['device_names'] or ''
            device_list = [d.strip() for d in device_names.split(',') if d.strip()][:5]
            device_name_pattern = ', '.join(device_list) if device_list else None

            patterns.append(ChangePattern(
                change_type=row['change_type'],
                device_type=row['device_type'],
                device_name_pattern=device_name_pattern,
                total_occurrences=total,
                times_helped=helped,
                times_hurt=hurt,
                times_neutral=neutral,
                avg_health_delta=avg_delta,
                std_deviation=0.0,  # Could calculate if needed
                best_context=None,  # Future enhancement
                worst_context=None,  # Future enhancement
                recommendation=recommendation,
                confidence=confidence
            ))

    return (patterns, f"Found {len(patterns)} learned patterns")


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


# ==================== PHASE 2: TREND ANALYSIS ====================


@dataclass
class TrendPoint:
    """A single point in the health trend timeline."""
    version_id: int
    als_filename: str
    health_score: int
    scanned_at: datetime
    delta_from_previous: int  # Change from previous version


@dataclass
class ProjectTrend:
    """Trend analysis for a project over time."""
    project_id: int
    song_name: str
    total_versions: int

    # Trajectory
    trend_direction: str  # 'improving', 'stable', 'declining'
    trend_strength: float  # 0-1, how strong the trend is

    # Timeline data
    first_health: int
    latest_health: int
    best_health: int
    worst_health: int
    avg_health: float

    # Key changes
    biggest_improvement: int  # Largest positive delta
    biggest_regression: int  # Largest negative delta (stored as positive)

    # Velocity
    avg_delta_per_version: float  # Average health change between versions
    recent_momentum: float  # Average delta in last 3 versions

    # Timeline
    timeline: List[TrendPoint]

    # Interpretation
    summary: str  # Human-readable summary


def analyze_project_trend(
    search_term: str,
    db_path: Optional[Path] = None
) -> Tuple[Optional[ProjectTrend], str]:
    """
    Analyze the health trend of a project over time.

    Determines if the project is improving, stable, or declining based
    on version history.

    Args:
        search_term: Song name or partial match
        db_path: Optional custom path for the database

    Returns:
        Tuple of (ProjectTrend or None, message)
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
        # Get all versions ordered by scan date
        cursor = conn.execute("""
            SELECT id, als_filename, health_score, scanned_at
            FROM versions
            WHERE project_id = ?
            ORDER BY scanned_at ASC, id ASC
        """, (project_id,))

        versions = cursor.fetchall()

    if len(versions) < 2:
        return (None, f"Need at least 2 versions for trend analysis. '{song_name}' has {len(versions)}.")

    # Build timeline
    timeline = []
    deltas = []

    for i, v in enumerate(versions):
        scanned_at = v['scanned_at']
        if isinstance(scanned_at, str):
            scanned_at = datetime.fromisoformat(scanned_at)

        if i == 0:
            delta = 0
        else:
            delta = v['health_score'] - versions[i-1]['health_score']
            deltas.append(delta)

        timeline.append(TrendPoint(
            version_id=v['id'],
            als_filename=v['als_filename'],
            health_score=v['health_score'],
            scanned_at=scanned_at,
            delta_from_previous=delta
        ))

    # Calculate metrics
    health_scores = [v['health_score'] for v in versions]
    first_health = health_scores[0]
    latest_health = health_scores[-1]
    best_health = max(health_scores)
    worst_health = min(health_scores)
    avg_health = sum(health_scores) / len(health_scores)

    # Calculate deltas
    avg_delta = sum(deltas) / len(deltas) if deltas else 0
    recent_deltas = deltas[-3:] if len(deltas) >= 3 else deltas
    recent_momentum = sum(recent_deltas) / len(recent_deltas) if recent_deltas else 0

    # Find biggest swings
    biggest_improvement = max(deltas) if deltas else 0
    biggest_regression = abs(min(deltas)) if deltas else 0

    # Determine trend direction
    if avg_delta > 2:
        trend_direction = 'improving'
        trend_strength = min(1.0, avg_delta / 10)
    elif avg_delta < -2:
        trend_direction = 'declining'
        trend_strength = min(1.0, abs(avg_delta) / 10)
    else:
        trend_direction = 'stable'
        trend_strength = 1.0 - min(1.0, abs(avg_delta) / 2)

    # Generate summary
    total_change = latest_health - first_health
    if trend_direction == 'improving':
        summary = f"Good progress! Health improved {first_health} ->{latest_health} (+{total_change}) over {len(versions)} versions."
        if recent_momentum > avg_delta:
            summary += " Recent momentum is strong."
    elif trend_direction == 'declining':
        summary = f"Warning: Health dropped {first_health} ->{latest_health} ({total_change}) over {len(versions)} versions."
        if recent_momentum < avg_delta:
            summary += " Recent versions are declining faster."
    else:
        summary = f"Stable at ~{avg_health:.0f} health over {len(versions)} versions."
        if best_health - worst_health > 20:
            summary += f" Fluctuates between {worst_health}-{best_health}."

    return (ProjectTrend(
        project_id=project_id,
        song_name=song_name,
        total_versions=len(versions),
        trend_direction=trend_direction,
        trend_strength=trend_strength,
        first_health=first_health,
        latest_health=latest_health,
        best_health=best_health,
        worst_health=worst_health,
        avg_health=avg_health,
        biggest_improvement=biggest_improvement,
        biggest_regression=biggest_regression,
        avg_delta_per_version=avg_delta,
        recent_momentum=recent_momentum,
        timeline=timeline,
        summary=summary
    ), "OK")


# ==================== PHASE 2 ENHANCED: TREND VISUALIZATION & MILESTONES ====================


@dataclass
class Milestone:
    """A significant event in the project's history."""
    version_id: int
    als_filename: str
    health_score: int
    milestone_type: str  # 'first_a', 'new_best', 'major_improvement', 'major_regression', 'recovery'
    description: str
    scanned_at: datetime


@dataclass
class EnhancedTrendAnalysis:
    """Extended trend analysis with visualizations and milestones."""
    # Base trend data
    trend: ProjectTrend

    # Milestones
    milestones: List[Milestone]

    # ASCII graph data
    graph_lines: List[str]  # Pre-rendered ASCII graph
    graph_width: int
    graph_height: int

    # Additional metrics
    consistency_score: float  # How consistent the health changes are (0-1)
    recovery_count: int  # Number of times health recovered after a drop
    plateau_count: int  # Number of stable periods

    # Predictions
    predicted_next_health: float  # Linear prediction for next version
    days_to_grade_a: Optional[int]  # Estimated days to reach Grade A at current rate


def generate_ascii_trend_graph(
    timeline: List[TrendPoint],
    width: int = 50,
    height: int = 10
) -> List[str]:
    """
    Generate an ASCII graph of health scores over time.

    Args:
        timeline: List of TrendPoint from a ProjectTrend
        width: Width of the graph in characters
        height: Height of the graph in characters

    Returns:
        List of strings representing the graph lines
    """
    if not timeline:
        return ["No data to graph"]

    scores = [p.health_score for p in timeline]
    min_score = min(scores)
    max_score = max(scores)
    score_range = max(max_score - min_score, 1)  # Avoid division by zero

    # Create graph matrix
    graph = [[' ' for _ in range(width)] for _ in range(height)]

    # Calculate x positions
    if len(scores) > 1:
        x_step = (width - 1) / (len(scores) - 1)
    else:
        x_step = 0

    # Plot points
    for i, score in enumerate(scores):
        x = int(i * x_step) if i < len(scores) else width - 1
        # Normalize y to graph height (inverted since top is 0)
        y = height - 1 - int((score - min_score) / score_range * (height - 1))
        y = max(0, min(height - 1, y))

        # Determine character based on delta
        if i > 0:
            delta = scores[i] - scores[i - 1]
            if delta > 2:
                char = '▲'
            elif delta < -2:
                char = '▼'
            else:
                char = '●'
        else:
            char = '○'

        graph[y][x] = char

        # Draw connecting lines if there are intermediate x positions
        if i > 0:
            prev_x = int((i - 1) * x_step) if i > 1 else 0
            prev_y = height - 1 - int((scores[i - 1] - min_score) / score_range * (height - 1))
            prev_y = max(0, min(height - 1, prev_y))

            # Fill in dots between points
            if abs(x - prev_x) > 1:
                for mid_x in range(prev_x + 1, x):
                    # Interpolate y
                    t = (mid_x - prev_x) / (x - prev_x)
                    mid_y = int(prev_y + t * (y - prev_y))
                    mid_y = max(0, min(height - 1, mid_y))
                    if graph[mid_y][mid_x] == ' ':
                        graph[mid_y][mid_x] = '·'

    # Build output lines with y-axis labels
    lines = []
    lines.append(f"Health {max_score:>3} ┤{''.join(graph[0])}")
    for i in range(1, height - 1):
        # Calculate the score for this row
        row_score = max_score - int((i / (height - 1)) * score_range)
        if i == height // 2:
            lines.append(f"       {row_score:>3} ┤{''.join(graph[i])}")
        else:
            lines.append(f"           │{''.join(graph[i])}")
    lines.append(f"       {min_score:>3} └{'─' * width}")

    # X-axis labels
    first_ver = timeline[0].als_filename[:8] if timeline else ""
    last_ver = timeline[-1].als_filename[:8] if timeline else ""
    x_label = f"           {first_ver}" + " " * (width - len(first_ver) - len(last_ver)) + last_ver
    lines.append(x_label)

    return lines


def detect_milestones(timeline: List[TrendPoint]) -> List[Milestone]:
    """
    Detect significant milestones in a project's history.

    Milestones include:
    - First time reaching Grade A (80+)
    - New best score
    - Major improvements (+10 or more)
    - Major regressions (-10 or more)
    - Recovery after a regression

    Args:
        timeline: List of TrendPoint from a ProjectTrend

    Returns:
        List of Milestone objects
    """
    if not timeline:
        return []

    milestones = []
    best_score = 0
    reached_grade_a = False
    last_was_regression = False

    for i, point in enumerate(timeline):
        # First Grade A
        if not reached_grade_a and point.health_score >= 80:
            reached_grade_a = True
            milestones.append(Milestone(
                version_id=point.version_id,
                als_filename=point.als_filename,
                health_score=point.health_score,
                milestone_type='first_a',
                description=f"First Grade A achieved! Score: {point.health_score}",
                scanned_at=point.scanned_at
            ))

        # New best score
        if point.health_score > best_score:
            if best_score > 0:  # Skip first version
                milestones.append(Milestone(
                    version_id=point.version_id,
                    als_filename=point.als_filename,
                    health_score=point.health_score,
                    milestone_type='new_best',
                    description=f"New personal best! {best_score} ->{point.health_score}",
                    scanned_at=point.scanned_at
                ))
            best_score = point.health_score

        # Major improvement
        if point.delta_from_previous >= 10:
            milestones.append(Milestone(
                version_id=point.version_id,
                als_filename=point.als_filename,
                health_score=point.health_score,
                milestone_type='major_improvement',
                description=f"Major improvement: +{point.delta_from_previous} points",
                scanned_at=point.scanned_at
            ))
            if last_was_regression:
                milestones.append(Milestone(
                    version_id=point.version_id,
                    als_filename=point.als_filename,
                    health_score=point.health_score,
                    milestone_type='recovery',
                    description="Recovered from previous regression",
                    scanned_at=point.scanned_at
                ))
            last_was_regression = False

        # Major regression
        if point.delta_from_previous <= -10:
            milestones.append(Milestone(
                version_id=point.version_id,
                als_filename=point.als_filename,
                health_score=point.health_score,
                milestone_type='major_regression',
                description=f"Major regression: {point.delta_from_previous} points",
                scanned_at=point.scanned_at
            ))
            last_was_regression = True
        elif point.delta_from_previous > 0:
            last_was_regression = False

    return milestones


def get_enhanced_trend_analysis(
    search_term: str,
    db_path: Optional[Path] = None,
    graph_width: int = 50,
    graph_height: int = 10
) -> Tuple[Optional[EnhancedTrendAnalysis], str]:
    """
    Get enhanced trend analysis with visualizations and milestones.

    Extends the basic trend analysis with:
    - ASCII visualization of health over time
    - Milestone detection (achievements, improvements, regressions)
    - Consistency scoring
    - Predictive metrics

    Args:
        search_term: Song name or partial match
        db_path: Optional custom path for the database
        graph_width: Width of ASCII graph
        graph_height: Height of ASCII graph

    Returns:
        Tuple of (EnhancedTrendAnalysis or None, message)
    """
    # Get base trend analysis
    trend, msg = analyze_project_trend(search_term, db_path)
    if not trend:
        return (None, msg)

    # Generate ASCII graph
    graph_lines = generate_ascii_trend_graph(
        trend.timeline, graph_width, graph_height
    )

    # Detect milestones
    milestones = detect_milestones(trend.timeline)

    # Calculate consistency score
    # Based on standard deviation of deltas (lower = more consistent)
    if len(trend.timeline) >= 2:
        deltas = [p.delta_from_previous for p in trend.timeline[1:]]
        if deltas:
            mean_delta = sum(deltas) / len(deltas)
            variance = sum((d - mean_delta) ** 2 for d in deltas) / len(deltas)
            std_dev = variance ** 0.5
            # Normalize: std_dev of 0 = 1.0 consistency, std_dev of 20+ = 0.0
            consistency_score = max(0, 1 - (std_dev / 20))
        else:
            consistency_score = 1.0
    else:
        consistency_score = 1.0

    # Count recoveries and plateaus
    recovery_count = len([m for m in milestones if m.milestone_type == 'recovery'])
    plateau_count = len([p for p in trend.timeline if abs(p.delta_from_previous) <= 2])

    # Predict next health (simple linear extrapolation)
    if len(trend.timeline) >= 3:
        recent = trend.timeline[-3:]
        recent_avg_delta = sum(p.delta_from_previous for p in recent) / len(recent)
        predicted_next_health = trend.latest_health + recent_avg_delta
    else:
        predicted_next_health = trend.latest_health + trend.avg_delta_per_version

    # Estimate days to Grade A
    if trend.latest_health < 80 and trend.avg_delta_per_version > 0:
        points_needed = 80 - trend.latest_health
        versions_needed = points_needed / trend.avg_delta_per_version
        # Assume average 3 days between versions (rough estimate)
        days_to_grade_a = int(versions_needed * 3)
    else:
        days_to_grade_a = None

    return (EnhancedTrendAnalysis(
        trend=trend,
        milestones=milestones,
        graph_lines=graph_lines,
        graph_width=graph_width,
        graph_height=graph_height,
        consistency_score=consistency_score,
        recovery_count=recovery_count,
        plateau_count=plateau_count,
        predicted_next_health=predicted_next_health,
        days_to_grade_a=days_to_grade_a
    ), "OK")


# ==================== PHASE 2: WHAT-IF PREDICTIONS ====================


@dataclass
class WhatIfPrediction:
    """Prediction of what might happen if a change is made."""
    action: str  # 'remove', 'add', 'enable', 'disable'
    device_type: str
    predicted_health_delta: float  # Expected health change
    confidence: str  # 'LOW', 'MEDIUM', 'HIGH'
    sample_size: int  # How many similar changes in history
    success_rate: float  # What % of similar changes improved health
    reasoning: str  # Explanation of the prediction


@dataclass
class WhatIfAnalysis:
    """What-if analysis for a project's current state."""
    als_path: str
    current_health: int
    predictions: List[WhatIfPrediction]
    top_recommendation: Optional[WhatIfPrediction]  # Highest confidence improvement
    has_sufficient_data: bool


def get_what_if_predictions(
    als_path: str,
    db_path: Optional[Path] = None
) -> Tuple[Optional[WhatIfAnalysis], str]:
    """
    Generate what-if predictions for a scanned project.

    Analyzes historical patterns and predicts what would happen if
    certain devices were removed/disabled based on past outcomes.

    Args:
        als_path: Path to a scanned .als file
        db_path: Optional custom path for the database

    Returns:
        Tuple of (WhatIfAnalysis or None, message)
    """
    from pathlib import Path as PathLib

    db = Database(db_path)

    if not db.is_initialized():
        return (None, "Database not initialized. Run 'als-doctor db init' first.")

    # Get the version record
    version = db.get_version_by_path(als_path)
    if not version:
        return (None, f"File not scanned yet: {als_path}")

    # Get historical pattern data
    predictions = []

    with db.connection() as conn:
        # Get patterns for device removals that helped
        cursor = conn.execute("""
            SELECT
                device_type,
                change_type,
                COUNT(*) as sample_size,
                AVG(health_delta) as avg_delta,
                SUM(CASE WHEN health_delta > 0 THEN 1 ELSE 0 END) as improved_count
            FROM changes
            WHERE change_type IN ('device_removed', 'device_disabled')
            GROUP BY device_type, change_type
            HAVING COUNT(*) >= 2
            ORDER BY AVG(health_delta) DESC
        """)

        for row in cursor.fetchall():
            sample_size = row['sample_size']
            avg_delta = row['avg_delta']
            improved_count = row['improved_count'] or 0
            success_rate = improved_count / sample_size if sample_size > 0 else 0

            if sample_size >= 10:
                confidence = 'HIGH'
            elif sample_size >= 5:
                confidence = 'MEDIUM'
            else:
                confidence = 'LOW'

            action = 'remove' if row['change_type'] == 'device_removed' else 'disable'
            device_type = row['device_type'] or 'unknown'

            # Only show predictions with positive expected delta
            if avg_delta > 0:
                reasoning = f"Based on {sample_size} similar changes: {success_rate*100:.0f}% improved health, avg +{avg_delta:.1f}"

                predictions.append(WhatIfPrediction(
                    action=action,
                    device_type=device_type,
                    predicted_health_delta=avg_delta,
                    confidence=confidence,
                    sample_size=sample_size,
                    success_rate=success_rate,
                    reasoning=reasoning
                ))

    # Sort by predicted improvement
    predictions.sort(key=lambda p: (-p.predicted_health_delta, -p.sample_size))

    # Find top recommendation (highest confidence with positive delta)
    top_recommendation = None
    for p in predictions:
        if p.confidence in ('HIGH', 'MEDIUM') and p.predicted_health_delta > 2:
            top_recommendation = p
            break

    has_sufficient_data = len(predictions) > 0 and any(p.confidence in ('HIGH', 'MEDIUM') for p in predictions)

    return (WhatIfAnalysis(
        als_path=als_path,
        current_health=version.health_score,
        predictions=predictions[:10],  # Top 10
        top_recommendation=top_recommendation,
        has_sufficient_data=has_sufficient_data
    ), "OK")


# ==================== PHASE 2: ENHANCED CHANGE IMPACT ====================


@dataclass
class ChangeImpactPrediction:
    """Predicted impact of a specific change."""
    change_type: str
    device_type: str
    device_name: str
    track_name: str

    # Actual outcome (for historical changes)
    actual_health_delta: Optional[int]

    # Predicted impact (based on history)
    predicted_delta: float
    prediction_confidence: str

    # Context
    similar_changes_count: int
    similar_success_rate: float

    # Assessment
    likely_outcome: str  # 'helped', 'hurt', 'neutral', 'unknown'
    explanation: str


def get_change_impact_predictions(
    search_term: str,
    db_path: Optional[Path] = None
) -> Tuple[Optional[List[ChangeImpactPrediction]], str]:
    """
    Get enhanced impact predictions for changes between versions.

    This augments the basic change tracking with predicted impacts
    based on historical patterns, not just observed outcomes.

    Args:
        search_term: Song name or partial match
        db_path: Optional custom path for the database

    Returns:
        Tuple of (List[ChangeImpactPrediction] or None, message)
    """
    db = Database(db_path)

    if not db.is_initialized():
        return (None, "Database not initialized.")

    # Find the project
    match = find_project_by_name(search_term, db_path)
    if not match:
        return (None, f"No project found matching '{search_term}'")

    project_id, song_name = match

    # Build pattern lookup from all history
    pattern_stats = {}
    with db.connection() as conn:
        cursor = conn.execute("""
            SELECT
                change_type,
                device_type,
                COUNT(*) as count,
                AVG(health_delta) as avg_delta,
                SUM(CASE WHEN health_delta > 0 THEN 1 ELSE 0 END) as helped
            FROM changes
            GROUP BY change_type, device_type
            HAVING COUNT(*) >= 2
        """)

        for row in cursor.fetchall():
            key = (row['change_type'], row['device_type'] or 'unknown')
            pattern_stats[key] = {
                'count': row['count'],
                'avg_delta': row['avg_delta'],
                'success_rate': (row['helped'] or 0) / row['count']
            }

    # Get changes for this project
    with db.connection() as conn:
        cursor = conn.execute("""
            SELECT
                c.change_type, c.device_type, c.device_name, c.track_name,
                c.health_delta
            FROM changes c
            WHERE c.project_id = ?
            ORDER BY c.recorded_at DESC
            LIMIT 50
        """, (project_id,))

        predictions = []
        for row in cursor.fetchall():
            change_type = row['change_type']
            device_type = row['device_type'] or 'unknown'

            # Look up pattern stats
            key = (change_type, device_type)
            stats = pattern_stats.get(key, {})

            if stats:
                predicted_delta = stats['avg_delta']
                count = stats['count']
                success_rate = stats['success_rate']

                if count >= 10:
                    confidence = 'HIGH'
                elif count >= 5:
                    confidence = 'MEDIUM'
                else:
                    confidence = 'LOW'
            else:
                predicted_delta = 0
                count = 0
                success_rate = 0.5
                confidence = 'LOW'

            # Determine likely outcome
            actual_delta = row['health_delta']
            if actual_delta is not None:
                if actual_delta > 2:
                    likely_outcome = 'helped'
                elif actual_delta < -2:
                    likely_outcome = 'hurt'
                else:
                    likely_outcome = 'neutral'
            else:
                likely_outcome = 'unknown'

            # Generate explanation
            if stats:
                explanation = f"Pattern seen {count}x with avg {predicted_delta:+.1f} health ({success_rate*100:.0f}% positive)"
            else:
                explanation = "No historical data for this pattern"

            predictions.append(ChangeImpactPrediction(
                change_type=change_type,
                device_type=device_type,
                device_name=row['device_name'] or '',
                track_name=row['track_name'] or '',
                actual_health_delta=actual_delta,
                predicted_delta=predicted_delta,
                prediction_confidence=confidence,
                similar_changes_count=count,
                similar_success_rate=success_rate,
                likely_outcome=likely_outcome,
                explanation=explanation
            ))

    return (predictions, "OK")


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


# ==================== PHASE 2: PERSONALIZED RECOMMENDATIONS ====================


@dataclass
class ProjectPatterns:
    """Patterns specific to a single project."""
    project_id: int
    song_name: str
    total_changes: int
    patterns: List[ChangePattern]

    # Project-specific insights
    best_change: Optional[ChangePattern]  # Change with highest positive impact
    worst_change: Optional[ChangePattern]  # Change with highest negative impact
    project_trend: str  # 'improving', 'stable', 'declining'


@dataclass
class PersonalizedRecommendation:
    """A recommendation that combines global and project-specific patterns."""
    action: str  # What to do (e.g., "Remove", "Add", "Disable")
    target: str  # What to target (e.g., "Compressor", "Reverb")
    track_name: Optional[str]  # Specific track if applicable

    # Scoring
    priority: int  # 0-100
    confidence: str  # 'HIGH', 'MEDIUM', 'LOW'

    # Evidence
    global_avg_delta: float  # Average health delta globally
    global_occurrences: int  # How many times seen globally
    project_avg_delta: Optional[float]  # Average delta for this specific project
    project_occurrences: int  # How many times seen in this project

    # Source
    source: str  # 'global', 'project', 'both'
    reasoning: str  # Explanation of why this is recommended


@dataclass
class PersonalizedRecommendationsResult:
    """Result of personalized recommendation analysis."""
    als_path: str
    current_health: int
    current_grade: str

    # Recommendations sorted by priority
    recommendations: List[PersonalizedRecommendation]

    # Context
    has_project_history: bool  # True if project has change history
    has_global_history: bool  # True if global patterns available
    project_changes_count: int
    global_changes_count: int

    # Summary
    top_recommendation: Optional[PersonalizedRecommendation]
    estimated_improvement: float  # Estimated health gain if all recommendations followed


def get_project_specific_patterns(
    search_term: str,
    db_path: Optional[Path] = None,
    min_occurrences: int = 2
) -> Tuple[Optional[ProjectPatterns], str]:
    """
    Get patterns specific to a single project.

    Unlike global patterns, these are based only on the history of
    the specified project, revealing what works for this specific song.

    Args:
        search_term: Song name or partial match
        db_path: Optional custom path for the database
        min_occurrences: Minimum occurrences for a pattern (default: 2)

    Returns:
        Tuple of (ProjectPatterns or None, message)
    """
    db = Database(db_path)

    if not db.is_initialized():
        return (None, "Database not initialized")

    match = find_project_by_name(search_term, db_path)
    if not match:
        return (None, f"No project found matching '{search_term}'")

    project_id, song_name = match

    patterns = []

    with db.connection() as conn:
        # Count total changes for this project
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM changes WHERE project_id = ?",
            (project_id,)
        )
        row = cursor.fetchone()
        total_changes = row['count'] if row else 0

        if total_changes < min_occurrences:
            return (ProjectPatterns(
                project_id=project_id,
                song_name=song_name,
                total_changes=total_changes,
                patterns=[],
                best_change=None,
                worst_change=None,
                project_trend='unknown'
            ), "Insufficient changes for pattern analysis")

        # Get patterns specific to this project
        cursor = conn.execute("""
            SELECT
                change_type,
                device_type,
                COUNT(*) as total_occurrences,
                SUM(CASE WHEN health_delta > 2 THEN 1 ELSE 0 END) as times_helped,
                SUM(CASE WHEN health_delta < -2 THEN 1 ELSE 0 END) as times_hurt,
                SUM(CASE WHEN health_delta BETWEEN -2 AND 2 THEN 1 ELSE 0 END) as times_neutral,
                AVG(health_delta) as avg_delta,
                GROUP_CONCAT(DISTINCT device_name) as device_names
            FROM changes
            WHERE project_id = ?
            GROUP BY change_type, device_type
            HAVING COUNT(*) >= ?
            ORDER BY ABS(AVG(health_delta)) DESC
        """, (project_id, min_occurrences))

        best_change = None
        worst_change = None
        best_delta = 0
        worst_delta = 0

        for row in cursor.fetchall():
            total = row['total_occurrences']
            helped = row['times_helped'] or 0
            hurt = row['times_hurt'] or 0
            neutral = row['times_neutral'] or 0
            avg_delta = row['avg_delta'] or 0.0

            if total >= 5:
                confidence = 'HIGH'
            elif total >= 3:
                confidence = 'MEDIUM'
            else:
                confidence = 'LOW'

            # Generate recommendation
            success_rate = helped / total if total > 0 else 0
            if avg_delta > 2 and success_rate > 0.5:
                recommendation = "Works well for this project"
            elif avg_delta < -2 and success_rate < 0.5:
                recommendation = "Tends to cause issues in this project"
            else:
                recommendation = "Mixed results in this project"

            device_names = row['device_names'] or ''
            device_list = [d.strip() for d in device_names.split(',') if d.strip()][:5]

            pattern = ChangePattern(
                change_type=row['change_type'],
                device_type=row['device_type'],
                device_name_pattern=', '.join(device_list) if device_list else None,
                total_occurrences=total,
                times_helped=helped,
                times_hurt=hurt,
                times_neutral=neutral,
                avg_health_delta=avg_delta,
                std_deviation=0.0,
                best_context=None,
                worst_context=None,
                recommendation=recommendation,
                confidence=confidence
            )
            patterns.append(pattern)

            # Track best/worst
            if avg_delta > best_delta:
                best_delta = avg_delta
                best_change = pattern
            if avg_delta < worst_delta:
                worst_delta = avg_delta
                worst_change = pattern

        # Determine project trend
        cursor = conn.execute("""
            SELECT AVG(health_delta) as avg_delta
            FROM changes
            WHERE project_id = ?
        """, (project_id,))
        row = cursor.fetchone()
        avg_project_delta = row['avg_delta'] if row and row['avg_delta'] else 0

        if avg_project_delta > 2:
            project_trend = 'improving'
        elif avg_project_delta < -2:
            project_trend = 'declining'
        else:
            project_trend = 'stable'

    return (ProjectPatterns(
        project_id=project_id,
        song_name=song_name,
        total_changes=total_changes,
        patterns=patterns,
        best_change=best_change,
        worst_change=worst_change,
        project_trend=project_trend
    ), "OK")


def get_personalized_recommendations(
    als_path: str,
    db_path: Optional[Path] = None
) -> Tuple[Optional[PersonalizedRecommendationsResult], str]:
    """
    Get personalized recommendations combining global and project-specific patterns.

    Analyzes a scanned project and generates recommendations based on:
    1. Global patterns (what works across all your projects)
    2. Project-specific patterns (what works for this specific song)
    3. Weighted by confidence and relevance

    Project-specific patterns are weighted more heavily when available,
    as they reflect what works for this particular song's style.

    Args:
        als_path: Path to a scanned .als file
        db_path: Optional custom path for the database

    Returns:
        Tuple of (PersonalizedRecommendationsResult or None, message)
    """
    from pathlib import Path as PathLib

    db = Database(db_path)

    if not db.is_initialized():
        return (None, "Database not initialized")

    # Get version info
    version = db.get_version_by_path(als_path)
    if not version:
        return (None, f"File not scanned: {als_path}")

    # Find project
    als_path_obj = PathLib(als_path).absolute()
    folder_path = str(als_path_obj.parent)

    project = db.get_project_by_folder(folder_path)
    if not project:
        return (None, "Project not found")

    # Get global patterns
    global_patterns, _ = get_learned_patterns(db_path, min_occurrences=3)

    # Get project-specific patterns
    project_patterns_result, _ = get_project_specific_patterns(
        project.song_name, db_path, min_occurrences=2
    )
    project_patterns = project_patterns_result.patterns if project_patterns_result else []

    # Count changes
    with db.connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) as count FROM changes")
        row = cursor.fetchone()
        global_changes_count = row['count'] if row else 0

        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM changes WHERE project_id = ?",
            (project.id,)
        )
        row = cursor.fetchone()
        project_changes_count = row['count'] if row else 0

    recommendations = []

    # Build lookup for project patterns
    project_pattern_lookup = {}
    for p in project_patterns:
        key = (p.change_type, p.device_type)
        project_pattern_lookup[key] = p

    # Process global patterns and combine with project-specific data
    for gp in global_patterns:
        key = (gp.change_type, gp.device_type)
        pp = project_pattern_lookup.get(key)

        # Determine source
        if pp:
            source = 'both'
            project_avg = pp.avg_health_delta
            project_occurrences = pp.total_occurrences
        else:
            source = 'global'
            project_avg = None
            project_occurrences = 0

        # Calculate priority
        # Weight project-specific data higher when available
        if source == 'both':
            # Combine global and project data
            combined_delta = (gp.avg_health_delta * 0.4) + (pp.avg_health_delta * 0.6)
            combined_confidence = pp.confidence  # Use project confidence if available
        else:
            combined_delta = gp.avg_health_delta
            combined_confidence = gp.confidence

        # Only recommend changes that help
        if combined_delta <= 0:
            continue

        # Map change type to action
        action_map = {
            'device_removed': 'Remove',
            'device_disabled': 'Disable',
            'device_added': 'Add',
            'device_enabled': 'Enable',
            'track_removed': 'Remove track',
            'track_added': 'Add track'
        }
        action = action_map.get(gp.change_type, gp.change_type)
        target = gp.device_type or 'device'

        # Calculate priority score (0-100)
        priority = min(100, int(combined_delta * 10 + (gp.total_occurrences * 2)))
        if source == 'both':
            priority = min(100, priority + 15)  # Bonus for project-specific confirmation

        # Build reasoning
        if source == 'both':
            reasoning = (
                f"Both global ({gp.total_occurrences}x, avg {gp.avg_health_delta:+.1f}) "
                f"and project ({pp.total_occurrences}x, avg {pp.avg_health_delta:+.1f}) "
                f"data suggest this helps."
            )
        else:
            reasoning = (
                f"Global pattern ({gp.total_occurrences}x, avg {gp.avg_health_delta:+.1f}) "
                f"suggests this helps. No project-specific data yet."
            )

        recommendations.append(PersonalizedRecommendation(
            action=action,
            target=target,
            track_name=None,
            priority=priority,
            confidence=combined_confidence,
            global_avg_delta=gp.avg_health_delta,
            global_occurrences=gp.total_occurrences,
            project_avg_delta=project_avg,
            project_occurrences=project_occurrences,
            source=source,
            reasoning=reasoning
        ))

    # Add project-only patterns not in global
    for pp in project_patterns:
        key = (pp.change_type, pp.device_type)
        if key not in [(gp.change_type, gp.device_type) for gp in global_patterns]:
            if pp.avg_health_delta <= 0:
                continue

            action_map = {
                'device_removed': 'Remove',
                'device_disabled': 'Disable',
                'device_added': 'Add',
                'device_enabled': 'Enable',
                'track_removed': 'Remove track',
                'track_added': 'Add track'
            }
            action = action_map.get(pp.change_type, pp.change_type)
            target = pp.device_type or 'device'

            priority = min(100, int(pp.avg_health_delta * 8 + (pp.total_occurrences * 3)))

            reasoning = (
                f"Project-specific pattern ({pp.total_occurrences}x, avg {pp.avg_health_delta:+.1f}). "
                f"This works well for this particular song."
            )

            recommendations.append(PersonalizedRecommendation(
                action=action,
                target=target,
                track_name=None,
                priority=priority,
                confidence=pp.confidence,
                global_avg_delta=0.0,
                global_occurrences=0,
                project_avg_delta=pp.avg_health_delta,
                project_occurrences=pp.total_occurrences,
                source='project',
                reasoning=reasoning
            ))

    # Sort by priority
    recommendations.sort(key=lambda r: -r.priority)

    # Calculate estimated improvement
    estimated_improvement = sum(
        r.project_avg_delta if r.project_avg_delta else r.global_avg_delta
        for r in recommendations[:5]  # Top 5 recommendations
    )

    top_recommendation = recommendations[0] if recommendations else None

    return (PersonalizedRecommendationsResult(
        als_path=als_path,
        current_health=version.health_score,
        current_grade=version.grade,
        recommendations=recommendations[:20],  # Limit to top 20
        has_project_history=project_changes_count >= 2,
        has_global_history=global_changes_count >= 10,
        project_changes_count=project_changes_count,
        global_changes_count=global_changes_count,
        top_recommendation=top_recommendation,
        estimated_improvement=estimated_improvement
    ), "OK")


# ==================== PHASE 2: REFERENCE COMPARISON LEARNING ====================


@dataclass
class StoredReferenceComparison:
    """A stored reference comparison from the database."""
    id: int
    project_id: Optional[int]
    version_id: Optional[int]
    user_file_path: str
    reference_file_path: str
    reference_name: Optional[str]
    genre: Optional[str]
    overall_similarity_score: float
    loudness_diff_db: float
    balance_score: float
    compared_at: datetime
    stem_comparisons: Dict[str, Dict[str, float]]  # stem_type -> metrics


@dataclass
class ReferenceRecommendationPattern:
    """A learned pattern from reference comparison recommendations."""
    category: str  # 'eq', 'dynamics', 'balance', 'stereo'
    stem_type: Optional[str]
    recommendation_pattern: str  # Summary of the recommendation type
    times_suggested: int
    times_applied: int
    times_helped: int
    times_hurt: int
    avg_effect: float  # Average effect on subsequent comparisons
    confidence: str  # 'HIGH', 'MEDIUM', 'LOW'


@dataclass
class ReferenceInsights:
    """Insights learned from reference comparisons."""
    total_comparisons: int
    total_recommendations: int

    # Common issues found
    common_issues: List[Dict[str, Any]]  # List of {stem_type, issue_type, frequency, avg_severity}

    # What recommendations helped
    helpful_recommendations: List[ReferenceRecommendationPattern]

    # Genre-specific insights
    genre_patterns: Dict[str, Dict[str, float]]  # genre -> {avg_loudness_diff, avg_balance_score}

    # Personal tendencies
    tendency_summary: str  # e.g., "You tend to have loud bass and quiet mids"


def persist_reference_comparison(
    user_file_path: str,
    reference_file_path: str,
    comparison_data: Dict[str, Any],
    project_id: Optional[int] = None,
    version_id: Optional[int] = None,
    reference_name: Optional[str] = None,
    genre: Optional[str] = None,
    db_path: Optional[Path] = None
) -> Tuple[bool, str, Optional[int]]:
    """
    Store a reference comparison result in the database for learning.

    Args:
        user_file_path: Path to the user's mix file
        reference_file_path: Path to the reference track
        comparison_data: Dict with comparison metrics (from ReferenceComparator)
        project_id: Optional project ID to link this comparison to
        version_id: Optional version ID to link this comparison to
        reference_name: Human-readable name of the reference
        genre: Genre tag for filtering/learning
        db_path: Optional custom path for the database

    Returns:
        Tuple of (success: bool, message: str, comparison_id: Optional[int])
    """
    db = Database(db_path)

    if not db.is_initialized():
        return (False, "Database not initialized", None)

    try:
        with db.connection() as conn:
            # Insert main comparison record
            cursor = conn.execute("""
                INSERT INTO reference_comparisons (
                    project_id, version_id, user_file_path, reference_file_path,
                    reference_name, genre, overall_similarity_score,
                    loudness_diff_db, balance_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id,
                version_id,
                user_file_path,
                reference_file_path,
                reference_name,
                genre,
                comparison_data.get('overall_balance_score', 0.0),
                comparison_data.get('overall_loudness_diff_db', 0.0),
                comparison_data.get('overall_balance_score', 0.0)
            ))
            comparison_id = cursor.lastrowid

            # Insert stem comparisons if available
            stem_comparisons = comparison_data.get('stem_comparisons', {})
            for stem_type, stem_data in stem_comparisons.items():
                conn.execute("""
                    INSERT INTO reference_stem_comparisons (
                        comparison_id, stem_type, rms_diff_db, lufs_diff,
                        spectral_centroid_diff_hz, stereo_width_diff_pct,
                        bass_diff_pct, mid_diff_pct, high_diff_pct, severity
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    comparison_id,
                    stem_type,
                    stem_data.get('rms_diff_db', 0.0),
                    stem_data.get('lufs_diff', 0.0),
                    stem_data.get('spectral_centroid_diff_hz', 0.0),
                    stem_data.get('stereo_width_diff_pct', 0.0),
                    stem_data.get('bass_diff_pct', 0.0),
                    stem_data.get('mid_diff_pct', 0.0),
                    stem_data.get('high_diff_pct', 0.0),
                    stem_data.get('severity', 'minor')
                ))

            # Insert recommendations for learning
            recommendations = comparison_data.get('priority_recommendations', [])
            for rec in recommendations:
                # Try to categorize the recommendation
                category = 'other'
                if 'eq' in rec.lower() or 'frequency' in rec.lower() or 'boost' in rec.lower() or 'cut' in rec.lower():
                    category = 'eq'
                elif 'compress' in rec.lower() or 'dynamic' in rec.lower():
                    category = 'dynamics'
                elif 'balance' in rec.lower() or 'level' in rec.lower() or 'db' in rec.lower():
                    category = 'balance'
                elif 'stereo' in rec.lower() or 'width' in rec.lower() or 'pan' in rec.lower():
                    category = 'stereo'

                conn.execute("""
                    INSERT INTO reference_recommendations (
                        comparison_id, recommendation, category, stem_type
                    ) VALUES (?, ?, ?, ?)
                """, (comparison_id, rec, category, None))

        return (True, f"Stored comparison with {len(stem_comparisons)} stem comparisons", comparison_id)

    except Exception as e:
        return (False, f"Failed to store comparison: {e}", None)


def mark_recommendation_applied(
    recommendation_id: int,
    helped: Optional[bool] = None,
    db_path: Optional[Path] = None
) -> Tuple[bool, str]:
    """
    Mark a recommendation as applied and optionally record if it helped.

    Args:
        recommendation_id: ID of the recommendation to mark
        helped: True if it helped, False if it hurt, None if neutral/unknown
        db_path: Optional custom path for the database

    Returns:
        Tuple of (success: bool, message: str)
    """
    db = Database(db_path)

    if not db.is_initialized():
        return (False, "Database not initialized")

    helped_score = None
    if helped is True:
        helped_score = 1
    elif helped is False:
        helped_score = -1
    elif helped is None:
        helped_score = 0

    try:
        with db.connection() as conn:
            conn.execute("""
                UPDATE reference_recommendations
                SET was_applied = 1, helped_score = ?
                WHERE id = ?
            """, (helped_score, recommendation_id))

        return (True, "Recommendation marked as applied")

    except Exception as e:
        return (False, f"Failed to update recommendation: {e}")


def get_reference_insights(
    db_path: Optional[Path] = None,
    genre: Optional[str] = None
) -> Tuple[Optional[ReferenceInsights], str]:
    """
    Get insights learned from reference comparisons.

    Analyzes stored comparisons to identify:
    - Common mixing issues
    - Which recommendations tend to help
    - Genre-specific patterns
    - Personal tendencies

    Args:
        db_path: Optional custom path for the database
        genre: Optional genre filter

    Returns:
        Tuple of (ReferenceInsights or None, message)
    """
    db = Database(db_path)

    if not db.is_initialized():
        return (None, "Database not initialized")

    with db.connection() as conn:
        # Count comparisons
        if genre:
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM reference_comparisons WHERE genre = ?",
                (genre,)
            )
        else:
            cursor = conn.execute("SELECT COUNT(*) as count FROM reference_comparisons")
        row = cursor.fetchone()
        total_comparisons = row['count'] if row else 0

        if total_comparisons < 3:
            return (ReferenceInsights(
                total_comparisons=total_comparisons,
                total_recommendations=0,
                common_issues=[],
                helpful_recommendations=[],
                genre_patterns={},
                tendency_summary="Insufficient data - need at least 3 reference comparisons"
            ), "OK")

        # Count recommendations
        cursor = conn.execute("SELECT COUNT(*) as count FROM reference_recommendations")
        row = cursor.fetchone()
        total_recommendations = row['count'] if row else 0

        # Find common issues (stem differences that appear frequently)
        cursor = conn.execute("""
            SELECT
                stem_type,
                CASE
                    WHEN ABS(rms_diff_db) > 3 THEN 'level'
                    WHEN ABS(bass_diff_pct) > 10 THEN 'bass'
                    WHEN ABS(high_diff_pct) > 10 THEN 'highs'
                    WHEN ABS(stereo_width_diff_pct) > 15 THEN 'width'
                    ELSE 'other'
                END as issue_type,
                COUNT(*) as frequency,
                AVG(ABS(rms_diff_db)) as avg_severity
            FROM reference_stem_comparisons
            WHERE severity IN ('moderate', 'significant')
            GROUP BY stem_type, issue_type
            HAVING COUNT(*) >= 2
            ORDER BY frequency DESC
            LIMIT 10
        """)

        common_issues = []
        for row in cursor.fetchall():
            common_issues.append({
                'stem_type': row['stem_type'],
                'issue_type': row['issue_type'],
                'frequency': row['frequency'],
                'avg_severity': row['avg_severity']
            })

        # Find helpful recommendations
        cursor = conn.execute("""
            SELECT
                category,
                stem_type,
                COUNT(*) as times_suggested,
                SUM(was_applied) as times_applied,
                SUM(CASE WHEN helped_score = 1 THEN 1 ELSE 0 END) as times_helped,
                SUM(CASE WHEN helped_score = -1 THEN 1 ELSE 0 END) as times_hurt
            FROM reference_recommendations
            GROUP BY category, stem_type
            HAVING COUNT(*) >= 2
            ORDER BY times_helped DESC
        """)

        helpful_recommendations = []
        for row in cursor.fetchall():
            times_suggested = row['times_suggested']
            times_applied = row['times_applied'] or 0
            times_helped = row['times_helped'] or 0
            times_hurt = row['times_hurt'] or 0

            if times_applied > 0:
                avg_effect = (times_helped - times_hurt) / times_applied
            else:
                avg_effect = 0.0

            if times_applied >= 5:
                confidence = 'HIGH'
            elif times_applied >= 3:
                confidence = 'MEDIUM'
            else:
                confidence = 'LOW'

            helpful_recommendations.append(ReferenceRecommendationPattern(
                category=row['category'],
                stem_type=row['stem_type'],
                recommendation_pattern=f"{row['category']} adjustments",
                times_suggested=times_suggested,
                times_applied=times_applied,
                times_helped=times_helped,
                times_hurt=times_hurt,
                avg_effect=avg_effect,
                confidence=confidence
            ))

        # Genre-specific patterns
        cursor = conn.execute("""
            SELECT
                genre,
                AVG(loudness_diff_db) as avg_loudness_diff,
                AVG(balance_score) as avg_balance_score,
                COUNT(*) as count
            FROM reference_comparisons
            WHERE genre IS NOT NULL
            GROUP BY genre
            HAVING COUNT(*) >= 2
        """)

        genre_patterns = {}
        for row in cursor.fetchall():
            genre_patterns[row['genre']] = {
                'avg_loudness_diff': row['avg_loudness_diff'],
                'avg_balance_score': row['avg_balance_score'],
                'count': row['count']
            }

        # Calculate personal tendency summary
        cursor = conn.execute("""
            SELECT
                AVG(rms_diff_db) as avg_rms_diff,
                AVG(bass_diff_pct) as avg_bass_diff,
                AVG(mid_diff_pct) as avg_mid_diff,
                AVG(high_diff_pct) as avg_high_diff
            FROM reference_stem_comparisons
        """)
        row = cursor.fetchone()

        tendencies = []
        if row:
            if row['avg_bass_diff'] and row['avg_bass_diff'] > 5:
                tendencies.append("bass tends to be loud")
            elif row['avg_bass_diff'] and row['avg_bass_diff'] < -5:
                tendencies.append("bass tends to be quiet")

            if row['avg_mid_diff'] and row['avg_mid_diff'] > 5:
                tendencies.append("mids tend to be loud")
            elif row['avg_mid_diff'] and row['avg_mid_diff'] < -5:
                tendencies.append("mids tend to be quiet")

            if row['avg_high_diff'] and row['avg_high_diff'] > 5:
                tendencies.append("highs tend to be loud")
            elif row['avg_high_diff'] and row['avg_high_diff'] < -5:
                tendencies.append("highs tend to be quiet")

        if tendencies:
            tendency_summary = f"Compared to references, your mixes: {', '.join(tendencies)}"
        else:
            tendency_summary = "Your mixes are generally well-balanced compared to references"

        return (ReferenceInsights(
            total_comparisons=total_comparisons,
            total_recommendations=total_recommendations,
            common_issues=common_issues,
            helpful_recommendations=helpful_recommendations,
            genre_patterns=genre_patterns,
            tendency_summary=tendency_summary
        ), "OK")


def get_reference_history(
    search_term: Optional[str] = None,
    limit: int = 20,
    db_path: Optional[Path] = None
) -> Tuple[List[StoredReferenceComparison], str]:
    """
    Get history of reference comparisons, optionally filtered by project.

    Args:
        search_term: Optional song name to filter by
        limit: Maximum number of comparisons to return
        db_path: Optional custom path for the database

    Returns:
        Tuple of (List[StoredReferenceComparison], message)
    """
    db = Database(db_path)

    if not db.is_initialized():
        return ([], "Database not initialized")

    comparisons = []

    with db.connection() as conn:
        if search_term:
            match = find_project_by_name(search_term, db_path)
            if not match:
                return ([], f"No project found matching '{search_term}'")
            project_id, _ = match

            cursor = conn.execute("""
                SELECT * FROM reference_comparisons
                WHERE project_id = ?
                ORDER BY compared_at DESC
                LIMIT ?
            """, (project_id, limit))
        else:
            cursor = conn.execute("""
                SELECT * FROM reference_comparisons
                ORDER BY compared_at DESC
                LIMIT ?
            """, (limit,))

        for row in cursor.fetchall():
            compared_at = row['compared_at']
            if isinstance(compared_at, str):
                compared_at = datetime.fromisoformat(compared_at)

            # Get stem comparisons for this comparison
            stem_cursor = conn.execute("""
                SELECT * FROM reference_stem_comparisons
                WHERE comparison_id = ?
            """, (row['id'],))

            stem_comparisons = {}
            for stem_row in stem_cursor.fetchall():
                stem_comparisons[stem_row['stem_type']] = {
                    'rms_diff_db': stem_row['rms_diff_db'],
                    'lufs_diff': stem_row['lufs_diff'],
                    'bass_diff_pct': stem_row['bass_diff_pct'],
                    'mid_diff_pct': stem_row['mid_diff_pct'],
                    'high_diff_pct': stem_row['high_diff_pct'],
                    'severity': stem_row['severity']
                }

            comparisons.append(StoredReferenceComparison(
                id=row['id'],
                project_id=row['project_id'],
                version_id=row['version_id'],
                user_file_path=row['user_file_path'],
                reference_file_path=row['reference_file_path'],
                reference_name=row['reference_name'],
                genre=row['genre'],
                overall_similarity_score=row['overall_similarity_score'] or 0.0,
                loudness_diff_db=row['loudness_diff_db'] or 0.0,
                balance_score=row['balance_score'] or 0.0,
                compared_at=compared_at,
                stem_comparisons=stem_comparisons
            ))

    return (comparisons, f"Found {len(comparisons)} comparison(s)")


# ============================================================================
# User Activity Functions (Story 4.6: "What Should I Work On")
# ============================================================================


def record_work_session(
    project_id: int,
    notes: Optional[str] = None,
    hide_days: int = 0,
    db_path: Optional[Path] = None
) -> Tuple[bool, str]:
    """
    Record that the user worked on a project.

    Args:
        project_id: ID of the project worked on
        notes: Optional notes about what was done
        hide_days: Number of days to hide from suggestions (0 = don't hide)
        db_path: Optional database path

    Returns:
        Tuple of (success, message)
    """
    db = get_db(db_path)

    try:
        with db.connection() as conn:
            # Calculate hidden_until if requested
            hidden_until = None
            if hide_days > 0:
                from datetime import timedelta
                hidden_until = datetime.now() + timedelta(days=hide_days)

            cursor = conn.execute("""
                INSERT INTO user_activity (project_id, worked_at, hidden_until, notes)
                VALUES (?, CURRENT_TIMESTAMP, ?, ?)
            """, (project_id, hidden_until, notes))

            return (True, f"Recorded work session for project {project_id}")
    except Exception as e:
        return (False, f"Error recording work session: {e}")


def get_last_worked(
    project_id: int,
    db_path: Optional[Path] = None
) -> Tuple[Optional[datetime], str]:
    """
    Get the last time the user worked on a project.

    Args:
        project_id: ID of the project

    Returns:
        Tuple of (last_worked_at datetime or None, message)
    """
    db = get_db(db_path)

    try:
        with db.connection() as conn:
            row = conn.execute("""
                SELECT worked_at
                FROM user_activity
                WHERE project_id = ?
                ORDER BY worked_at DESC
                LIMIT 1
            """, (project_id,)).fetchone()

            if row:
                worked_at = row['worked_at']
                if isinstance(worked_at, str):
                    worked_at = datetime.fromisoformat(worked_at.replace('Z', '+00:00'))
                return (worked_at, "Found last work session")
            else:
                return (None, "No work sessions recorded")
    except Exception as e:
        return (None, f"Error getting last worked: {e}")


def is_project_hidden(
    project_id: int,
    db_path: Optional[Path] = None
) -> bool:
    """
    Check if a project is currently hidden from suggestions.

    Args:
        project_id: ID of the project

    Returns:
        True if project should be hidden from suggestions
    """
    db = get_db(db_path)

    try:
        with db.connection() as conn:
            row = conn.execute("""
                SELECT hidden_until
                FROM user_activity
                WHERE project_id = ?
                  AND hidden_until IS NOT NULL
                  AND hidden_until > CURRENT_TIMESTAMP
                ORDER BY hidden_until DESC
                LIMIT 1
            """, (project_id,)).fetchone()

            return row is not None
    except Exception:
        return False


def get_days_since_worked(
    project_id: int,
    db_path: Optional[Path] = None
) -> Optional[int]:
    """
    Get the number of days since the user last worked on a project.

    Args:
        project_id: ID of the project

    Returns:
        Number of days since last work, or None if never worked on
    """
    last_worked, _ = get_last_worked(project_id, db_path)
    if last_worked is None:
        return None

    delta = datetime.now() - last_worked
    return delta.days


def get_work_history(
    project_id: int,
    limit: int = 10,
    db_path: Optional[Path] = None
) -> List[UserActivity]:
    """
    Get the work history for a project.

    Args:
        project_id: ID of the project
        limit: Maximum number of entries to return

    Returns:
        List of UserActivity objects
    """
    db = get_db(db_path)
    activities = []

    try:
        with db.connection() as conn:
            rows = conn.execute("""
                SELECT id, project_id, worked_at, hidden_until, notes
                FROM user_activity
                WHERE project_id = ?
                ORDER BY worked_at DESC
                LIMIT ?
            """, (project_id, limit)).fetchall()

            for row in rows:
                worked_at = row['worked_at']
                if isinstance(worked_at, str):
                    worked_at = datetime.fromisoformat(worked_at.replace('Z', '+00:00'))

                hidden_until = row['hidden_until']
                if hidden_until and isinstance(hidden_until, str):
                    hidden_until = datetime.fromisoformat(hidden_until.replace('Z', '+00:00'))

                activities.append(UserActivity(
                    id=row['id'],
                    project_id=row['project_id'],
                    worked_at=worked_at,
                    hidden_until=hidden_until,
                    notes=row['notes']
                ))

    except Exception:
        pass

    return activities


def hide_project_temporarily(
    project_id: int,
    days: int,
    db_path: Optional[Path] = None
) -> Tuple[bool, str]:
    """
    Hide a project from work suggestions for a number of days.

    Args:
        project_id: ID of the project
        days: Number of days to hide

    Returns:
        Tuple of (success, message)
    """
    from datetime import timedelta

    db = get_db(db_path)
    hidden_until = datetime.now() + timedelta(days=days)

    try:
        with db.connection() as conn:
            conn.execute("""
                INSERT INTO user_activity (project_id, worked_at, hidden_until, notes)
                VALUES (?, CURRENT_TIMESTAMP, ?, 'Hidden from suggestions')
            """, (project_id, hidden_until))

            return (True, f"Project hidden until {hidden_until.strftime('%Y-%m-%d')}")
    except Exception as e:
        return (False, f"Error hiding project: {e}")


def unhide_project(
    project_id: int,
    db_path: Optional[Path] = None
) -> Tuple[bool, str]:
    """
    Remove hide status from a project (make it visible in suggestions again).

    Args:
        project_id: ID of the project

    Returns:
        Tuple of (success, message)
    """
    db = get_db(db_path)

    try:
        with db.connection() as conn:
            # Clear hidden_until for all activity records
            conn.execute("""
                UPDATE user_activity
                SET hidden_until = NULL
                WHERE project_id = ? AND hidden_until IS NOT NULL
            """, (project_id,))

            return (True, "Project is now visible in suggestions")
    except Exception as e:
        return (False, f"Error unhiding project: {e}")
