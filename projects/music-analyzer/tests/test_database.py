"""
Tests for the database module.

Tests database initialization, schema creation, and basic operations.
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
import sys

# Add the src directory to path for direct import (avoiding __init__.py)
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Import directly from database module, bypassing src/__init__.py
import importlib.util
spec = importlib.util.spec_from_file_location("database", src_path / "database.py")
database_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(database_module)

Database = database_module.Database
db_init = database_module.db_init
get_db = database_module.get_db
SCHEMA_SQL = database_module.SCHEMA_SQL
persist_scan_result = database_module.persist_scan_result
persist_batch_scan_results = database_module.persist_batch_scan_results
ScanResult = database_module.ScanResult
ScanResultIssue = database_module.ScanResultIssue
_calculate_grade = database_module._calculate_grade


class TestDatabaseInit:
    """Tests for database initialization."""

    def test_db_init_creates_database_file(self, tmp_path):
        """db_init should create the database file."""
        db_path = tmp_path / "test.db"

        success, message = db_init(db_path)

        assert success is True
        assert db_path.exists()
        assert "created" in message.lower() or "initialized" in message.lower()

    def test_db_init_creates_parent_directory(self, tmp_path):
        """db_init should create parent directories if they don't exist."""
        db_path = tmp_path / "subdir" / "nested" / "test.db"

        success, message = db_init(db_path)

        assert success is True
        assert db_path.exists()
        assert db_path.parent.exists()

    def test_db_init_is_idempotent(self, tmp_path):
        """Running db_init twice should not destroy data."""
        db_path = tmp_path / "test.db"

        # First init
        success1, _ = db_init(db_path)
        assert success1

        # Insert some test data
        db = Database(db_path)
        with db.connection() as conn:
            conn.execute(
                "INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
                ("/test/path", "Test Song")
            )

        # Second init
        success2, message = db_init(db_path)
        assert success2
        assert "already initialized" in message.lower()

        # Verify data still exists
        with db.connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM projects")
            count = cursor.fetchone()['count']
            assert count == 1

    def test_db_init_creates_all_tables(self, tmp_path):
        """db_init should create projects, versions, and issues tables."""
        db_path = tmp_path / "test.db"

        db_init(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        assert 'projects' in tables
        assert 'versions' in tables
        assert 'issues' in tables


class TestDatabaseSchema:
    """Tests for the database schema."""

    def test_projects_table_schema(self, tmp_path):
        """Projects table should have the correct columns."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(projects)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        assert 'id' in columns
        assert 'folder_path' in columns
        assert 'song_name' in columns
        assert 'created_at' in columns

    def test_versions_table_schema(self, tmp_path):
        """Versions table should have the correct columns."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(versions)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        expected_columns = [
            'id', 'project_id', 'als_path', 'als_filename',
            'health_score', 'grade', 'total_issues', 'critical_issues',
            'warning_issues', 'total_devices', 'disabled_devices',
            'clutter_percentage', 'scanned_at'
        ]

        for col in expected_columns:
            assert col in columns, f"Missing column: {col}"

    def test_issues_table_schema(self, tmp_path):
        """Issues table should have the correct columns."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(issues)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        expected_columns = [
            'id', 'version_id', 'track_name', 'severity',
            'category', 'description', 'fix_suggestion'
        ]

        for col in expected_columns:
            assert col in columns, f"Missing column: {col}"

    def test_folder_path_unique_constraint(self, tmp_path):
        """folder_path in projects should be unique."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        db = Database(db_path)
        with db.connection() as conn:
            conn.execute(
                "INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
                ("/test/path", "Song 1")
            )

        # Attempting to insert duplicate should fail
        with pytest.raises(sqlite3.IntegrityError):
            with db.connection() as conn:
                conn.execute(
                    "INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
                    ("/test/path", "Song 2")
                )

    def test_als_path_unique_constraint(self, tmp_path):
        """als_path in versions should be unique."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        db = Database(db_path)

        # Create a project first
        with db.connection() as conn:
            conn.execute(
                "INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
                ("/test/path", "Song 1")
            )

        # Insert first version
        with db.connection() as conn:
            conn.execute(
                "INSERT INTO versions (project_id, als_path, als_filename) VALUES (?, ?, ?)",
                (1, "/test/path/song.als", "song.als")
            )

        # Attempting to insert duplicate should fail
        with pytest.raises(sqlite3.IntegrityError):
            with db.connection() as conn:
                conn.execute(
                    "INSERT INTO versions (project_id, als_path, als_filename) VALUES (?, ?, ?)",
                    (1, "/test/path/song.als", "song_copy.als")
                )


class TestDatabaseOperations:
    """Tests for database operations."""

    def test_is_initialized_false_when_no_db(self, tmp_path):
        """is_initialized should return False when database doesn't exist."""
        db_path = tmp_path / "nonexistent.db"
        db = Database(db_path)

        assert db.is_initialized() is False

    def test_is_initialized_true_after_init(self, tmp_path):
        """is_initialized should return True after initialization."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        db = Database(db_path)
        assert db.is_initialized() is True

    def test_get_stats_empty_database(self, tmp_path):
        """get_stats should return zeros for empty database."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        db = Database(db_path)
        stats = db.get_stats()

        assert stats['projects'] == 0
        assert stats['versions'] == 0
        assert stats['issues'] == 0

    def test_get_stats_with_data(self, tmp_path):
        """get_stats should return correct counts."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        db = Database(db_path)

        # Insert test data
        with db.connection() as conn:
            conn.execute(
                "INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
                ("/path1", "Song 1")
            )
            conn.execute(
                "INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
                ("/path2", "Song 2")
            )
            conn.execute(
                "INSERT INTO versions (project_id, als_path, als_filename) VALUES (?, ?, ?)",
                (1, "/path1/v1.als", "v1.als")
            )
            conn.execute(
                "INSERT INTO issues (version_id, severity, category, description) VALUES (?, ?, ?, ?)",
                (1, "warning", "clutter", "Too many disabled devices")
            )

        stats = db.get_stats()

        assert stats['projects'] == 2
        assert stats['versions'] == 1
        assert stats['issues'] == 1

    def test_get_project_by_folder(self, tmp_path):
        """get_project_by_folder should return correct project."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        db = Database(db_path)

        with db.connection() as conn:
            conn.execute(
                "INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
                ("/test/path", "Test Song")
            )

        project = db.get_project_by_folder("/test/path")

        assert project is not None
        assert project.folder_path == "/test/path"
        assert project.song_name == "Test Song"

    def test_get_project_by_folder_not_found(self, tmp_path):
        """get_project_by_folder should return None when not found."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        db = Database(db_path)
        project = db.get_project_by_folder("/nonexistent/path")

        assert project is None

    def test_get_version_by_path(self, tmp_path):
        """get_version_by_path should return correct version."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        db = Database(db_path)

        with db.connection() as conn:
            conn.execute(
                "INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
                ("/test/path", "Test Song")
            )
            conn.execute(
                """INSERT INTO versions
                   (project_id, als_path, als_filename, health_score, grade)
                   VALUES (?, ?, ?, ?, ?)""",
                (1, "/test/path/song.als", "song.als", 85, "B")
            )

        version = db.get_version_by_path("/test/path/song.als")

        assert version is not None
        assert version.als_path == "/test/path/song.als"
        assert version.als_filename == "song.als"
        assert version.health_score == 85
        assert version.grade == "B"


class TestForeignKeys:
    """Tests for foreign key constraints."""

    def test_version_requires_valid_project(self, tmp_path):
        """Versions should reference valid projects."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        db = Database(db_path)

        # Try to insert version with non-existent project_id
        with pytest.raises(sqlite3.IntegrityError):
            with db.connection() as conn:
                conn.execute(
                    "INSERT INTO versions (project_id, als_path, als_filename) VALUES (?, ?, ?)",
                    (999, "/path/song.als", "song.als")
                )

    def test_issue_requires_valid_version(self, tmp_path):
        """Issues should reference valid versions."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        db = Database(db_path)

        # Try to insert issue with non-existent version_id
        with pytest.raises(sqlite3.IntegrityError):
            with db.connection() as conn:
                conn.execute(
                    "INSERT INTO issues (version_id, severity, category, description) VALUES (?, ?, ?, ?)",
                    (999, "warning", "test", "Test issue")
                )

    def test_cascade_delete_project(self, tmp_path):
        """Deleting a project should cascade delete its versions and issues."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        db = Database(db_path)

        # Create project with version and issue
        with db.connection() as conn:
            conn.execute(
                "INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
                ("/test/path", "Test Song")
            )
            conn.execute(
                "INSERT INTO versions (project_id, als_path, als_filename) VALUES (?, ?, ?)",
                (1, "/test/path/song.als", "song.als")
            )
            conn.execute(
                "INSERT INTO issues (version_id, severity, category, description) VALUES (?, ?, ?, ?)",
                (1, "warning", "test", "Test issue")
            )

        # Delete project
        with db.connection() as conn:
            conn.execute("DELETE FROM projects WHERE id = 1")

        # Verify cascade delete
        stats = db.get_stats()
        assert stats['projects'] == 0
        assert stats['versions'] == 0
        assert stats['issues'] == 0


class TestPersistScanResult:
    """Tests for scan result persistence (Story 1.2)."""

    def _create_test_scan_result(self, tmp_path, filename="song_v1.als"):
        """Helper to create a test ScanResult."""
        # Create a test .als file path
        project_dir = tmp_path / "Test Project"
        project_dir.mkdir(parents=True, exist_ok=True)
        als_file = project_dir / filename

        return ScanResult(
            als_path=str(als_file),
            health_score=75,
            grade="B",
            total_issues=5,
            critical_issues=1,
            warning_issues=3,
            total_devices=20,
            disabled_devices=4,
            clutter_percentage=20.0,
            issues=[
                ScanResultIssue(
                    track_name="Kick",
                    severity="critical",
                    category="clutter",
                    description="Too many disabled devices",
                    fix_suggestion="Delete disabled devices"
                ),
                ScanResultIssue(
                    track_name="Bass",
                    severity="warning",
                    category="chain_order",
                    description="EQ after reverb",
                    fix_suggestion="Move EQ before reverb"
                )
            ]
        )

    def test_persist_scan_result_creates_project(self, tmp_path):
        """persist_scan_result should create project record from folder path."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        scan_result = self._create_test_scan_result(tmp_path)

        success, message, version_id = persist_scan_result(scan_result, db_path)

        assert success is True
        assert version_id is not None
        assert "created" in message.lower()

        # Verify project was created
        db = Database(db_path)
        stats = db.get_stats()
        assert stats['projects'] == 1

    def test_persist_scan_result_creates_version(self, tmp_path):
        """persist_scan_result should create version record with correct data."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        scan_result = self._create_test_scan_result(tmp_path)

        persist_scan_result(scan_result, db_path)

        # Verify version data
        db = Database(db_path)
        version = db.get_version_by_path(scan_result.als_path)

        assert version is not None
        assert version.health_score == 75
        assert version.grade == "B"
        assert version.total_issues == 5
        assert version.critical_issues == 1
        assert version.warning_issues == 3
        assert version.total_devices == 20
        assert version.disabled_devices == 4
        assert version.clutter_percentage == 20.0

    def test_persist_scan_result_stores_issues(self, tmp_path):
        """persist_scan_result should store all issues."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        scan_result = self._create_test_scan_result(tmp_path)

        persist_scan_result(scan_result, db_path)

        # Verify issues were stored
        db = Database(db_path)
        stats = db.get_stats()
        assert stats['issues'] == 2

        # Verify issue content
        with db.connection() as conn:
            cursor = conn.execute("SELECT * FROM issues WHERE severity = 'critical'")
            critical_issue = cursor.fetchone()
            assert critical_issue['track_name'] == "Kick"
            assert critical_issue['category'] == "clutter"
            assert critical_issue['description'] == "Too many disabled devices"
            assert critical_issue['fix_suggestion'] == "Delete disabled devices"

    def test_persist_scan_result_upsert_updates_existing(self, tmp_path):
        """Re-scanning same file should update existing record."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        scan_result = self._create_test_scan_result(tmp_path)

        # First scan
        persist_scan_result(scan_result, db_path)

        # Update values and re-scan
        scan_result.health_score = 90
        scan_result.grade = "A"
        scan_result.total_issues = 2

        success, message, version_id = persist_scan_result(scan_result, db_path)

        assert success is True
        assert "updated" in message.lower()

        # Verify only one version exists
        db = Database(db_path)
        stats = db.get_stats()
        assert stats['versions'] == 1

        # Verify data was updated
        version = db.get_version_by_path(scan_result.als_path)
        assert version.health_score == 90
        assert version.grade == "A"
        assert version.total_issues == 2

    def test_persist_scan_result_extracts_song_name_from_folder(self, tmp_path):
        """Song name should be extracted from parent folder."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        scan_result = self._create_test_scan_result(tmp_path)

        persist_scan_result(scan_result, db_path)

        # Verify song name matches folder name
        db = Database(db_path)
        project = db.get_project_by_folder(str(Path(scan_result.als_path).parent))
        assert project is not None
        assert project.song_name == "Test Project"

    def test_persist_scan_result_multiple_versions_same_project(self, tmp_path):
        """Multiple .als files in same folder should share one project."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        # Create two versions of the same project
        scan_result1 = self._create_test_scan_result(tmp_path, "song_v1.als")
        scan_result2 = self._create_test_scan_result(tmp_path, "song_v2.als")

        persist_scan_result(scan_result1, db_path)
        persist_scan_result(scan_result2, db_path)

        # Verify one project, two versions
        db = Database(db_path)
        stats = db.get_stats()
        assert stats['projects'] == 1
        assert stats['versions'] == 2

    def test_persist_scan_result_fails_without_db_init(self, tmp_path):
        """persist_scan_result should fail if database not initialized."""
        db_path = tmp_path / "uninit.db"

        scan_result = self._create_test_scan_result(tmp_path)

        success, message, version_id = persist_scan_result(scan_result, db_path)

        assert success is False
        assert "not initialized" in message.lower()
        assert version_id is None

    def test_persist_batch_scan_results(self, tmp_path):
        """persist_batch_scan_results should persist multiple results."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        # Create multiple scan results for different projects
        project1 = tmp_path / "Song 1"
        project2 = tmp_path / "Song 2"
        project1.mkdir()
        project2.mkdir()

        results = [
            ScanResult(
                als_path=str(project1 / "v1.als"),
                health_score=80,
                grade="B",
                total_issues=3,
                critical_issues=0,
                warning_issues=2,
                total_devices=15,
                disabled_devices=2,
                clutter_percentage=13.3,
                issues=[]
            ),
            ScanResult(
                als_path=str(project2 / "v1.als"),
                health_score=95,
                grade="A",
                total_issues=1,
                critical_issues=0,
                warning_issues=0,
                total_devices=10,
                disabled_devices=0,
                clutter_percentage=0.0,
                issues=[]
            )
        ]

        success_count, fail_count, errors = persist_batch_scan_results(results, db_path)

        assert success_count == 2
        assert fail_count == 0
        assert len(errors) == 0

        db = Database(db_path)
        stats = db.get_stats()
        assert stats['projects'] == 2
        assert stats['versions'] == 2


class TestCalculateGrade:
    """Tests for grade calculation."""

    def test_grade_a(self):
        """Scores 80-100 should be grade A."""
        assert _calculate_grade(100) == 'A'
        assert _calculate_grade(80) == 'A'

    def test_grade_b(self):
        """Scores 60-79 should be grade B."""
        assert _calculate_grade(79) == 'B'
        assert _calculate_grade(60) == 'B'

    def test_grade_c(self):
        """Scores 40-59 should be grade C."""
        assert _calculate_grade(59) == 'C'
        assert _calculate_grade(40) == 'C'

    def test_grade_d(self):
        """Scores 20-39 should be grade D."""
        assert _calculate_grade(39) == 'D'
        assert _calculate_grade(20) == 'D'

    def test_grade_f(self):
        """Scores 0-19 should be grade F."""
        assert _calculate_grade(19) == 'F'
        assert _calculate_grade(0) == 'F'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
