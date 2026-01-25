#!/usr/bin/env python3
"""
Simple test runner for database module without pytest dependency.
"""

import sys
import tempfile
from pathlib import Path

# Add the src directory to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

# Import directly from database module
import importlib.util
spec = importlib.util.spec_from_file_location('database', src_path / 'database.py')
database_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(database_module)

Database = database_module.Database
db_init = database_module.db_init
get_db = database_module.get_db
persist_scan_result = database_module.persist_scan_result
persist_batch_scan_results = database_module.persist_batch_scan_results
ScanResult = database_module.ScanResult
ScanResultIssue = database_module.ScanResultIssue
_calculate_grade = database_module._calculate_grade
list_projects = database_module.list_projects
ProjectSummary = database_module.ProjectSummary
_calculate_trend = database_module._calculate_trend
get_project_history = database_module.get_project_history
ProjectHistory = database_module.ProjectHistory
VersionHistory = database_module.VersionHistory
_fuzzy_match_song = database_module._fuzzy_match_song
find_project_by_name = database_module.find_project_by_name
get_best_version = database_module.get_best_version
BestVersionResult = database_module.BestVersionResult
get_library_status = database_module.get_library_status
LibraryStatus = database_module.LibraryStatus
GradeDistribution = database_module.GradeDistribution
generate_grade_bar = database_module.generate_grade_bar
get_project_changes = database_module.get_project_changes
ProjectChangesResult = database_module.ProjectChangesResult
VersionComparison = database_module.VersionComparison
VersionChange = database_module.VersionChange
get_insights = database_module.get_insights
InsightsResult = database_module.InsightsResult
InsightPattern = database_module.InsightPattern
CommonMistake = database_module.CommonMistake
_get_confidence_level = database_module._get_confidence_level
get_style_profile = database_module.get_style_profile
StyleProfile = database_module.StyleProfile
save_profile_to_json = database_module.save_profile_to_json
load_profile_from_json = database_module.load_profile_from_json
compare_file_against_profile = database_module.compare_file_against_profile
ProfileComparisonResult = database_module.ProfileComparisonResult


def test_grade_calculation():
    """Test grade calculation helper."""
    assert _calculate_grade(100) == 'A', "100 should be A"
    assert _calculate_grade(80) == 'A', "80 should be A"
    assert _calculate_grade(79) == 'B', "79 should be B"
    assert _calculate_grade(60) == 'B', "60 should be B"
    assert _calculate_grade(59) == 'C', "59 should be C"
    assert _calculate_grade(40) == 'C', "40 should be C"
    assert _calculate_grade(39) == 'D', "39 should be D"
    assert _calculate_grade(20) == 'D', "20 should be D"
    assert _calculate_grade(19) == 'F', "19 should be F"
    assert _calculate_grade(0) == 'F', "0 should be F"
    return True


def test_persist_creates_project(tmp_path):
    """persist_scan_result should create project record."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Test Project'
    project_dir.mkdir()

    result = ScanResult(
        als_path=str(project_dir / 'song_v1.als'),
        health_score=75,
        grade='B',
        total_issues=5,
        critical_issues=1,
        warning_issues=3,
        total_devices=20,
        disabled_devices=4,
        clutter_percentage=20.0,
        issues=[
            ScanResultIssue(
                track_name='Kick',
                severity='critical',
                category='clutter',
                description='Too many disabled devices',
                fix_suggestion='Delete disabled devices'
            ),
            ScanResultIssue(
                track_name='Bass',
                severity='warning',
                category='chain_order',
                description='EQ after reverb',
                fix_suggestion='Move EQ before reverb'
            )
        ]
    )

    success, msg, version_id = persist_scan_result(result, db_path)
    assert success, f'Expected success but got: {msg}'
    assert version_id is not None
    assert 'created' in msg.lower()

    # Verify project was created
    db = Database(db_path)
    stats = db.get_stats()
    assert stats['projects'] == 1

    return True


def test_persist_creates_version_with_data(tmp_path):
    """persist_scan_result should create version with correct data."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Test Project'
    project_dir.mkdir()

    result = ScanResult(
        als_path=str(project_dir / 'song_v1.als'),
        health_score=75,
        grade='B',
        total_issues=5,
        critical_issues=1,
        warning_issues=3,
        total_devices=20,
        disabled_devices=4,
        clutter_percentage=20.0,
        issues=[]
    )

    persist_scan_result(result, db_path)

    db = Database(db_path)
    version = db.get_version_by_path(result.als_path)

    assert version is not None
    assert version.health_score == 75
    assert version.grade == 'B'
    assert version.total_issues == 5
    assert version.critical_issues == 1
    assert version.warning_issues == 3
    assert version.total_devices == 20
    assert version.disabled_devices == 4
    assert version.clutter_percentage == 20.0

    return True


def test_persist_stores_issues(tmp_path):
    """persist_scan_result should store all issues."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Test Project'
    project_dir.mkdir()

    result = ScanResult(
        als_path=str(project_dir / 'song_v1.als'),
        health_score=75,
        grade='B',
        total_issues=2,
        critical_issues=1,
        warning_issues=1,
        total_devices=20,
        disabled_devices=4,
        clutter_percentage=20.0,
        issues=[
            ScanResultIssue(
                track_name='Kick',
                severity='critical',
                category='clutter',
                description='Too many disabled devices',
                fix_suggestion='Delete disabled devices'
            ),
            ScanResultIssue(
                track_name='Bass',
                severity='warning',
                category='chain_order',
                description='EQ after reverb',
                fix_suggestion='Move EQ before reverb'
            )
        ]
    )

    persist_scan_result(result, db_path)

    db = Database(db_path)
    stats = db.get_stats()
    assert stats['issues'] == 2

    # Verify issue content
    with db.connection() as conn:
        cursor = conn.execute("SELECT * FROM issues WHERE severity = 'critical'")
        critical_issue = cursor.fetchone()
        assert critical_issue['track_name'] == 'Kick'
        assert critical_issue['category'] == 'clutter'
        assert critical_issue['description'] == 'Too many disabled devices'
        assert critical_issue['fix_suggestion'] == 'Delete disabled devices'

    return True


def test_upsert_updates_existing(tmp_path):
    """Re-scanning same file should update existing record."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Test Project'
    project_dir.mkdir()

    result = ScanResult(
        als_path=str(project_dir / 'song_v1.als'),
        health_score=75,
        grade='B',
        total_issues=5,
        critical_issues=1,
        warning_issues=3,
        total_devices=20,
        disabled_devices=4,
        clutter_percentage=20.0,
        issues=[]
    )

    # First scan
    persist_scan_result(result, db_path)

    # Update values and re-scan
    result.health_score = 90
    result.grade = 'A'
    result.total_issues = 2

    success, msg, _ = persist_scan_result(result, db_path)

    assert success
    assert 'updated' in msg.lower()

    db = Database(db_path)
    stats = db.get_stats()
    assert stats['versions'] == 1  # Still 1 version

    version = db.get_version_by_path(result.als_path)
    assert version.health_score == 90
    assert version.grade == 'A'
    assert version.total_issues == 2

    return True


def test_song_name_from_folder(tmp_path):
    """Song name should be extracted from parent folder."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'My Awesome Song'
    project_dir.mkdir()

    result = ScanResult(
        als_path=str(project_dir / 'song.als'),
        health_score=80,
        grade='B',
        total_issues=0,
        critical_issues=0,
        warning_issues=0,
        total_devices=10,
        disabled_devices=0,
        clutter_percentage=0.0,
        issues=[]
    )

    persist_scan_result(result, db_path)

    db = Database(db_path)
    project = db.get_project_by_folder(str(project_dir))
    assert project.song_name == 'My Awesome Song'

    return True


def test_multiple_versions_same_project(tmp_path):
    """Multiple .als files in same folder should share one project."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Test Project'
    project_dir.mkdir()

    result1 = ScanResult(
        als_path=str(project_dir / 'song_v1.als'),
        health_score=75,
        grade='B',
        total_issues=5,
        critical_issues=1,
        warning_issues=3,
        total_devices=20,
        disabled_devices=4,
        clutter_percentage=20.0,
        issues=[]
    )

    result2 = ScanResult(
        als_path=str(project_dir / 'song_v2.als'),
        health_score=85,
        grade='B',
        total_issues=3,
        critical_issues=0,
        warning_issues=2,
        total_devices=18,
        disabled_devices=2,
        clutter_percentage=11.0,
        issues=[]
    )

    persist_scan_result(result1, db_path)
    persist_scan_result(result2, db_path)

    db = Database(db_path)
    stats = db.get_stats()
    assert stats['projects'] == 1
    assert stats['versions'] == 2

    return True


def test_fails_without_init(tmp_path):
    """persist_scan_result should fail if database not initialized."""
    uninit_db = tmp_path / 'uninit.db'

    result = ScanResult(
        als_path='/some/path/song.als',
        health_score=80,
        grade='B',
        total_issues=0,
        critical_issues=0,
        warning_issues=0,
        total_devices=10,
        disabled_devices=0,
        clutter_percentage=0.0,
        issues=[]
    )

    success, msg, version_id = persist_scan_result(result, uninit_db)

    assert success is False
    assert 'not initialized' in msg.lower()
    assert version_id is None

    return True


def test_batch_persist(tmp_path):
    """persist_batch_scan_results should persist multiple results."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project1 = tmp_path / 'Song 1'
    project2 = tmp_path / 'Song 2'
    project1.mkdir()
    project2.mkdir()

    results = [
        ScanResult(
            als_path=str(project1 / 'v1.als'),
            health_score=80,
            grade='B',
            total_issues=3,
            critical_issues=0,
            warning_issues=2,
            total_devices=15,
            disabled_devices=2,
            clutter_percentage=13.3,
            issues=[]
        ),
        ScanResult(
            als_path=str(project2 / 'v1.als'),
            health_score=95,
            grade='A',
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

    return True


# ==================== STORY 1.3: LIST PROJECTS ====================


def test_trend_calculation():
    """Test trend calculation helper."""
    # Single version = new
    assert _calculate_trend([{'health_score': 80}]) == 'new'

    # Empty = new
    assert _calculate_trend([]) == 'new'

    # Improving trend (latest > previous by more than 5)
    versions_improving = [
        {'health_score': 80},  # latest
        {'health_score': 60}   # previous
    ]
    assert _calculate_trend(versions_improving) == 'up'

    # Declining trend (latest < previous by more than 5)
    versions_declining = [
        {'health_score': 50},  # latest
        {'health_score': 80}   # previous
    ]
    assert _calculate_trend(versions_declining) == 'down'

    # Stable trend (within 5 points)
    versions_stable = [
        {'health_score': 78},  # latest
        {'health_score': 75}   # previous
    ]
    assert _calculate_trend(versions_stable) == 'stable'

    # Edge case: exactly 5 points difference = stable
    versions_edge = [
        {'health_score': 85},  # latest
        {'health_score': 80}   # previous
    ]
    assert _calculate_trend(versions_edge) == 'stable'

    return True


def test_list_projects_empty_db(tmp_path):
    """list_projects should return empty list for empty database."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    projects, stats = list_projects(db_path)

    assert len(projects) == 0
    assert stats['projects'] == 0
    assert stats['versions'] == 0

    return True


def test_list_projects_returns_summary(tmp_path):
    """list_projects should return ProjectSummary objects with correct data."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Test Song'
    project_dir.mkdir()

    result = ScanResult(
        als_path=str(project_dir / 'song_v1.als'),
        health_score=85,
        grade='A',
        total_issues=2,
        critical_issues=0,
        warning_issues=2,
        total_devices=15,
        disabled_devices=1,
        clutter_percentage=6.7,
        issues=[]
    )
    persist_scan_result(result, db_path)

    projects, stats = list_projects(db_path)

    assert len(projects) == 1
    assert stats['projects'] == 1
    assert stats['versions'] == 1

    project = projects[0]
    assert project.song_name == 'Test Song'
    assert project.version_count == 1
    assert project.best_score == 85
    assert project.best_grade == 'A'
    assert project.latest_score == 85
    assert project.latest_grade == 'A'
    assert project.trend == 'new'

    return True


def test_list_projects_multiple_versions(tmp_path):
    """list_projects should handle multiple versions correctly."""
    import time
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Multi Version Song'
    project_dir.mkdir()

    # First version (lower score)
    result1 = ScanResult(
        als_path=str(project_dir / 'song_v1.als'),
        health_score=60,
        grade='B',
        total_issues=5,
        critical_issues=1,
        warning_issues=4,
        total_devices=20,
        disabled_devices=5,
        clutter_percentage=25.0,
        issues=[]
    )
    persist_scan_result(result1, db_path)

    # Small delay to ensure different timestamps
    time.sleep(0.1)

    # Second version (higher score - improvement)
    result2 = ScanResult(
        als_path=str(project_dir / 'song_v2.als'),
        health_score=85,
        grade='A',
        total_issues=2,
        critical_issues=0,
        warning_issues=2,
        total_devices=18,
        disabled_devices=1,
        clutter_percentage=5.6,
        issues=[]
    )
    persist_scan_result(result2, db_path)

    projects, stats = list_projects(db_path)

    assert len(projects) == 1
    assert stats['projects'] == 1
    assert stats['versions'] == 2

    project = projects[0]
    assert project.version_count == 2
    assert project.best_score == 85  # Best is v2
    assert project.latest_score == 85  # Latest is v2
    assert project.trend == 'up'  # Improved from 60 to 85

    return True


def test_list_projects_sort_by_name(tmp_path):
    """list_projects should sort by name alphabetically."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create projects in non-alphabetical order
    for name in ['Zebra Song', 'Apple Song', 'Mountain Song']:
        project_dir = tmp_path / name
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / 'v1.als'),
            health_score=80,
            grade='A',
            total_issues=0,
            critical_issues=0,
            warning_issues=0,
            total_devices=10,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)

    projects, _ = list_projects(db_path, sort_by='name')

    assert len(projects) == 3
    assert projects[0].song_name == 'Apple Song'
    assert projects[1].song_name == 'Mountain Song'
    assert projects[2].song_name == 'Zebra Song'

    return True


def test_list_projects_sort_by_score(tmp_path):
    """list_projects should sort by best score descending."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    scores = [('Low Song', 40), ('High Song', 95), ('Mid Song', 70)]

    for name, score in scores:
        project_dir = tmp_path / name
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / 'v1.als'),
            health_score=score,
            grade=_calculate_grade(score),
            total_issues=0,
            critical_issues=0,
            warning_issues=0,
            total_devices=10,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)

    projects, _ = list_projects(db_path, sort_by='score')

    assert len(projects) == 3
    assert projects[0].song_name == 'High Song'
    assert projects[0].best_score == 95
    assert projects[1].song_name == 'Mid Song'
    assert projects[1].best_score == 70
    assert projects[2].song_name == 'Low Song'
    assert projects[2].best_score == 40

    return True


def test_list_projects_sort_by_date(tmp_path):
    """list_projects should sort by most recently scanned."""
    import time
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create projects with delays to ensure different timestamps
    for name in ['First Song', 'Second Song', 'Third Song']:
        project_dir = tmp_path / name
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / 'v1.als'),
            health_score=80,
            grade='A',
            total_issues=0,
            critical_issues=0,
            warning_issues=0,
            total_devices=10,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)
        time.sleep(0.1)

    projects, _ = list_projects(db_path, sort_by='date')

    assert len(projects) == 3
    # Most recent first
    assert projects[0].song_name == 'Third Song'
    assert projects[1].song_name == 'Second Song'
    assert projects[2].song_name == 'First Song'

    return True


def test_list_projects_trend_declining(tmp_path):
    """list_projects should detect declining trend."""
    import time
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Declining Song'
    project_dir.mkdir()

    # First version (high score)
    result1 = ScanResult(
        als_path=str(project_dir / 'v1.als'),
        health_score=90,
        grade='A',
        total_issues=1,
        critical_issues=0,
        warning_issues=1,
        total_devices=15,
        disabled_devices=0,
        clutter_percentage=0.0,
        issues=[]
    )
    persist_scan_result(result1, db_path)

    time.sleep(0.1)

    # Second version (lower score - decline)
    result2 = ScanResult(
        als_path=str(project_dir / 'v2.als'),
        health_score=50,
        grade='C',
        total_issues=10,
        critical_issues=3,
        warning_issues=7,
        total_devices=25,
        disabled_devices=8,
        clutter_percentage=32.0,
        issues=[]
    )
    persist_scan_result(result2, db_path)

    projects, _ = list_projects(db_path)

    assert len(projects) == 1
    project = projects[0]
    assert project.best_score == 90  # Best is still v1
    assert project.latest_score == 50  # Latest is v2
    assert project.trend == 'down'

    return True


def test_list_projects_uninit_db(tmp_path):
    """list_projects should handle uninitialized database gracefully."""
    uninit_db = tmp_path / 'uninit.db'

    projects, stats = list_projects(uninit_db)

    assert len(projects) == 0
    assert stats['projects'] == 0
    assert stats['versions'] == 0

    return True


# ==================== STORY 1.4: PROJECT HISTORY ====================


def test_fuzzy_match_exact():
    """Fuzzy match should match exact song name."""
    assert _fuzzy_match_song("22 Project", "22 Project") is True
    assert _fuzzy_match_song("22 project", "22 Project") is True  # Case insensitive
    assert _fuzzy_match_song("Other Song", "22 Project") is False
    return True


def test_fuzzy_match_substring():
    """Fuzzy match should match substring."""
    assert _fuzzy_match_song("22", "22 Project") is True
    assert _fuzzy_match_song("Project", "22 Project") is True
    assert _fuzzy_match_song("proj", "22 Project") is True
    assert _fuzzy_match_song("xyz", "22 Project") is False
    return True


def test_fuzzy_match_word_start():
    """Fuzzy match should match word starts."""
    assert _fuzzy_match_song("Proj", "22 Project") is True
    assert _fuzzy_match_song("pro", "22 Project") is True
    assert _fuzzy_match_song("ject", "22 Project") is True  # substring
    return True


def test_find_project_by_name(tmp_path):
    """find_project_by_name should return matching project."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / '22 Project'
    project_dir.mkdir()

    result = ScanResult(
        als_path=str(project_dir / 'song.als'),
        health_score=80,
        grade='A',
        total_issues=0,
        critical_issues=0,
        warning_issues=0,
        total_devices=10,
        disabled_devices=0,
        clutter_percentage=0.0,
        issues=[]
    )
    persist_scan_result(result, db_path)

    # Exact match
    match = find_project_by_name("22 Project", db_path)
    assert match is not None
    assert match[1] == "22 Project"

    # Fuzzy match
    match = find_project_by_name("22", db_path)
    assert match is not None
    assert match[1] == "22 Project"

    # No match
    match = find_project_by_name("xyz", db_path)
    assert match is None

    return True


def test_find_project_prefers_exact_match(tmp_path):
    """find_project_by_name should prefer exact match over partial."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create two projects where one name contains the other
    for name in ['Test', 'Test Project']:
        project_dir = tmp_path / name
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / 'song.als'),
            health_score=80,
            grade='A',
            total_issues=0,
            critical_issues=0,
            warning_issues=0,
            total_devices=10,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)

    # "Test" should match "Test" exactly, not "Test Project"
    match = find_project_by_name("Test", db_path)
    assert match is not None
    assert match[1] == "Test"

    return True


def test_get_project_history_basic(tmp_path):
    """get_project_history should return history for a project."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Test Song'
    project_dir.mkdir()

    result = ScanResult(
        als_path=str(project_dir / 'song_v1.als'),
        health_score=85,
        grade='A',
        total_issues=2,
        critical_issues=0,
        warning_issues=2,
        total_devices=15,
        disabled_devices=1,
        clutter_percentage=6.7,
        issues=[]
    )
    persist_scan_result(result, db_path)

    history, msg = get_project_history("Test Song", db_path)

    assert history is not None
    assert msg == "OK"
    assert history.song_name == "Test Song"
    assert len(history.versions) == 1
    assert history.versions[0].health_score == 85
    assert history.versions[0].grade == 'A'
    assert history.versions[0].als_filename == 'song_v1.als'
    assert history.best_version is not None
    assert history.current_version is not None

    return True


def test_get_project_history_with_delta(tmp_path):
    """get_project_history should calculate deltas between versions."""
    import time
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Delta Song'
    project_dir.mkdir()

    # First version
    result1 = ScanResult(
        als_path=str(project_dir / 'v1.als'),
        health_score=60,
        grade='B',
        total_issues=5,
        critical_issues=1,
        warning_issues=4,
        total_devices=20,
        disabled_devices=5,
        clutter_percentage=25.0,
        issues=[]
    )
    persist_scan_result(result1, db_path)

    time.sleep(0.1)

    # Second version (improved)
    result2 = ScanResult(
        als_path=str(project_dir / 'v2.als'),
        health_score=80,
        grade='A',
        total_issues=2,
        critical_issues=0,
        warning_issues=2,
        total_devices=18,
        disabled_devices=1,
        clutter_percentage=5.6,
        issues=[]
    )
    persist_scan_result(result2, db_path)

    time.sleep(0.1)

    # Third version (declined)
    result3 = ScanResult(
        als_path=str(project_dir / 'v3.als'),
        health_score=50,
        grade='C',
        total_issues=8,
        critical_issues=2,
        warning_issues=6,
        total_devices=25,
        disabled_devices=8,
        clutter_percentage=32.0,
        issues=[]
    )
    persist_scan_result(result3, db_path)

    history, msg = get_project_history("Delta", db_path)

    assert history is not None
    assert len(history.versions) == 3

    # Check order (oldest first)
    assert history.versions[0].als_filename == 'v1.als'
    assert history.versions[1].als_filename == 'v2.als'
    assert history.versions[2].als_filename == 'v3.als'

    # Check deltas
    assert history.versions[0].delta is None  # First version has no delta
    assert history.versions[1].delta == 20    # 80 - 60 = +20
    assert history.versions[2].delta == -30   # 50 - 80 = -30

    return True


def test_get_project_history_best_version(tmp_path):
    """get_project_history should mark the best version."""
    import time
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Best Song'
    project_dir.mkdir()

    # Create versions with different scores
    versions = [
        ('v1.als', 60),
        ('v2.als', 100),  # Best!
        ('v3.als', 45),
    ]

    for filename, score in versions:
        result = ScanResult(
            als_path=str(project_dir / filename),
            health_score=score,
            grade=_calculate_grade(score),
            total_issues=0,
            critical_issues=0,
            warning_issues=0,
            total_devices=10,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)
        time.sleep(0.1)

    history, msg = get_project_history("Best", db_path)

    assert history is not None
    assert history.best_version is not None
    assert history.best_version.als_filename == 'v2.als'
    assert history.best_version.health_score == 100
    assert history.best_version.is_best is True

    # Only v2 should be marked as best
    assert history.versions[0].is_best is False
    assert history.versions[1].is_best is True
    assert history.versions[2].is_best is False

    return True


def test_get_project_history_fuzzy_match(tmp_path):
    """get_project_history should support fuzzy matching."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / '22 Project Remix'
    project_dir.mkdir()

    result = ScanResult(
        als_path=str(project_dir / 'song.als'),
        health_score=80,
        grade='A',
        total_issues=0,
        critical_issues=0,
        warning_issues=0,
        total_devices=10,
        disabled_devices=0,
        clutter_percentage=0.0,
        issues=[]
    )
    persist_scan_result(result, db_path)

    # All these should find the project
    for search in ["22 Project Remix", "22", "remix", "proj"]:
        history, msg = get_project_history(search, db_path)
        assert history is not None, f"Should find project with search '{search}'"
        assert history.song_name == "22 Project Remix"

    return True


def test_get_project_history_not_found(tmp_path):
    """get_project_history should return None for non-existent project."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    history, msg = get_project_history("nonexistent", db_path)

    assert history is None
    assert "not found" in msg.lower() or "no project" in msg.lower()

    return True


def test_get_project_history_uninit_db(tmp_path):
    """get_project_history should handle uninitialized database."""
    uninit_db = tmp_path / 'uninit.db'

    history, msg = get_project_history("any", uninit_db)

    assert history is None
    assert "not initialized" in msg.lower()

    return True


def test_get_project_history_current_version(tmp_path):
    """get_project_history should identify current (latest) version."""
    import time
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Current Song'
    project_dir.mkdir()

    for filename in ['old.als', 'newer.als', 'latest.als']:
        result = ScanResult(
            als_path=str(project_dir / filename),
            health_score=80,
            grade='A',
            total_issues=0,
            critical_issues=0,
            warning_issues=0,
            total_devices=10,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)
        time.sleep(0.1)

    history, msg = get_project_history("Current", db_path)

    assert history is not None
    assert history.current_version is not None
    assert history.current_version.als_filename == 'latest.als'

    return True


# ==================== STORY 1.5: BEST VERSION ====================


def test_get_best_version_basic(tmp_path):
    """get_best_version should return the highest scoring version."""
    import time
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Best Test Song'
    project_dir.mkdir()

    # Create multiple versions with different scores
    versions = [
        ('v1.als', 60, 5),
        ('v2.als', 95, 1),  # Best!
        ('v3.als', 70, 3),
    ]

    for filename, score, issues in versions:
        result = ScanResult(
            als_path=str(project_dir / filename),
            health_score=score,
            grade=_calculate_grade(score),
            total_issues=issues,
            critical_issues=0,
            warning_issues=issues,
            total_devices=10,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)
        time.sleep(0.1)

    best, msg = get_best_version("Best Test", db_path)

    assert best is not None
    assert msg == "OK"
    assert best.best_als_filename == 'v2.als'
    assert best.best_health_score == 95
    assert best.best_grade == 'A'
    assert best.best_total_issues == 1

    return True


def test_get_best_version_tie_prefers_recent(tmp_path):
    """When scores tie, get_best_version should return most recent."""
    import time
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Tie Song'
    project_dir.mkdir()

    # Two versions with same score
    for filename in ['older.als', 'newer.als']:
        result = ScanResult(
            als_path=str(project_dir / filename),
            health_score=85,
            grade='A',
            total_issues=2,
            critical_issues=0,
            warning_issues=2,
            total_devices=10,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)
        time.sleep(0.1)

    best, msg = get_best_version("Tie", db_path)

    assert best is not None
    assert best.best_als_filename == 'newer.als'  # Most recent wins tie

    return True


def test_get_best_version_comparison_to_latest(tmp_path):
    """get_best_version should include comparison to latest version."""
    import time
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Compare Song'
    project_dir.mkdir()

    # Best version first
    result1 = ScanResult(
        als_path=str(project_dir / 'v1_best.als'),
        health_score=100,
        grade='A',
        total_issues=0,
        critical_issues=0,
        warning_issues=0,
        total_devices=10,
        disabled_devices=0,
        clutter_percentage=0.0,
        issues=[]
    )
    persist_scan_result(result1, db_path)

    time.sleep(0.1)

    # Latest version (worse)
    result2 = ScanResult(
        als_path=str(project_dir / 'v2_latest.als'),
        health_score=45,
        grade='C',
        total_issues=12,
        critical_issues=3,
        warning_issues=9,
        total_devices=25,
        disabled_devices=8,
        clutter_percentage=32.0,
        issues=[]
    )
    persist_scan_result(result2, db_path)

    best, msg = get_best_version("Compare", db_path)

    assert best is not None
    assert best.best_als_filename == 'v1_best.als'
    assert best.latest_als_filename == 'v2_latest.als'
    assert best.is_best_same_as_latest is False
    assert best.health_delta == 55  # 100 - 45
    assert best.issues_delta == 12  # 12 - 0

    return True


def test_get_best_version_best_is_latest(tmp_path):
    """get_best_version should detect when best and latest are the same."""
    import time
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Same Song'
    project_dir.mkdir()

    # Old worse version
    result1 = ScanResult(
        als_path=str(project_dir / 'v1_old.als'),
        health_score=50,
        grade='C',
        total_issues=8,
        critical_issues=2,
        warning_issues=6,
        total_devices=20,
        disabled_devices=5,
        clutter_percentage=25.0,
        issues=[]
    )
    persist_scan_result(result1, db_path)

    time.sleep(0.1)

    # Latest is also best
    result2 = ScanResult(
        als_path=str(project_dir / 'v2_best_and_latest.als'),
        health_score=95,
        grade='A',
        total_issues=1,
        critical_issues=0,
        warning_issues=1,
        total_devices=15,
        disabled_devices=0,
        clutter_percentage=0.0,
        issues=[]
    )
    persist_scan_result(result2, db_path)

    best, msg = get_best_version("Same", db_path)

    assert best is not None
    assert best.is_best_same_as_latest is True
    assert best.best_als_filename == 'v2_best_and_latest.als'
    assert best.latest_als_filename == 'v2_best_and_latest.als'
    assert best.health_delta == 0
    assert best.issues_delta == 0

    return True


def test_get_best_version_fuzzy_match(tmp_path):
    """get_best_version should support fuzzy matching."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / '22 Project Remix Extended'
    project_dir.mkdir()

    result = ScanResult(
        als_path=str(project_dir / 'song.als'),
        health_score=80,
        grade='A',
        total_issues=2,
        critical_issues=0,
        warning_issues=2,
        total_devices=10,
        disabled_devices=0,
        clutter_percentage=0.0,
        issues=[]
    )
    persist_scan_result(result, db_path)

    # All these should find the project
    for search in ["22 Project Remix Extended", "22", "remix", "Extended"]:
        best, msg = get_best_version(search, db_path)
        assert best is not None, f"Should find project with search '{search}'"
        assert best.song_name == "22 Project Remix Extended"

    return True


def test_get_best_version_not_found(tmp_path):
    """get_best_version should return None for non-existent project."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    best, msg = get_best_version("nonexistent", db_path)

    assert best is None
    assert "not found" in msg.lower() or "no project" in msg.lower()

    return True


def test_get_best_version_uninit_db(tmp_path):
    """get_best_version should handle uninitialized database."""
    uninit_db = tmp_path / 'uninit.db'

    best, msg = get_best_version("any", uninit_db)

    assert best is None
    assert "not initialized" in msg.lower()

    return True


def test_get_best_version_single_version(tmp_path):
    """get_best_version should work with only one version."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Single Version Song'
    project_dir.mkdir()

    result = ScanResult(
        als_path=str(project_dir / 'only.als'),
        health_score=75,
        grade='B',
        total_issues=3,
        critical_issues=0,
        warning_issues=3,
        total_devices=12,
        disabled_devices=1,
        clutter_percentage=8.3,
        issues=[]
    )
    persist_scan_result(result, db_path)

    best, msg = get_best_version("Single", db_path)

    assert best is not None
    assert best.best_als_filename == 'only.als'
    assert best.latest_als_filename == 'only.als'
    assert best.is_best_same_as_latest is True
    assert best.health_delta == 0
    assert best.issues_delta == 0

    return True


# ==================== STORY 1.6: LIBRARY STATUS ====================


def test_generate_grade_bar():
    """Test ASCII bar generation."""
    # 50% should give 10 characters out of 20
    bar = generate_grade_bar(5, 10, max_width=20)
    assert len(bar) == 10
    assert bar == "=========="

    # 100% should give max_width
    bar = generate_grade_bar(10, 10, max_width=20)
    assert len(bar) == 20

    # 0% should give empty string
    bar = generate_grade_bar(0, 10, max_width=20)
    assert bar == ""

    # Empty total should give empty string
    bar = generate_grade_bar(0, 0, max_width=20)
    assert bar == ""

    # Small percentage should still show at least something if count > 0
    bar = generate_grade_bar(1, 100, max_width=20)
    # 1% of 20 = 0.2, rounds to 0 - empty is expected
    assert bar == ""

    return True


def test_get_library_status_empty_db(tmp_path):
    """get_library_status should work with empty database."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    status, msg = get_library_status(db_path)

    assert status is not None
    assert msg == "OK"
    assert status.total_projects == 0
    assert status.total_versions == 0
    assert status.total_issues == 0
    assert status.last_scan_date is None
    assert len(status.grade_distribution) == 5  # A, B, C, D, F
    assert len(status.ready_to_release) == 0
    assert len(status.needs_work) == 0

    return True


def test_get_library_status_uninit_db(tmp_path):
    """get_library_status should handle uninitialized database."""
    uninit_db = tmp_path / 'uninit.db'

    status, msg = get_library_status(uninit_db)

    assert status is None
    assert "not initialized" in msg.lower()

    return True


def test_get_library_status_with_data(tmp_path):
    """get_library_status should return correct summary."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create some projects with varying grades
    projects = [
        ('Song A', 'v1.als', 95, 'A', 1),   # Ready to release
        ('Song B', 'v1.als', 85, 'A', 2),   # Ready to release
        ('Song C', 'v1.als', 70, 'B', 3),
        ('Song D', 'v1.als', 55, 'C', 5),
        ('Song E', 'v1.als', 30, 'D', 8),   # Needs work
        ('Song F', 'v1.als', 15, 'F', 12),  # Needs work
    ]

    for name, filename, score, grade, issues in projects:
        project_dir = tmp_path / name
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / filename),
            health_score=score,
            grade=grade,
            total_issues=issues,
            critical_issues=0,
            warning_issues=issues,
            total_devices=10,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[
                ScanResultIssue(
                    track_name='Track',
                    severity='warning',
                    category='test',
                    description='Test issue',
                    fix_suggestion='Fix it'
                )
            ] * issues
        )
        persist_scan_result(result, db_path)

    status, msg = get_library_status(db_path)

    assert status is not None
    assert status.total_projects == 6
    assert status.total_versions == 6
    assert status.total_issues == sum(p[4] for p in projects)  # Sum of all issues
    assert status.last_scan_date is not None

    # Check grade distribution
    grade_counts = {g.grade: g.count for g in status.grade_distribution}
    assert grade_counts['A'] == 2
    assert grade_counts['B'] == 1
    assert grade_counts['C'] == 1
    assert grade_counts['D'] == 1
    assert grade_counts['F'] == 1

    # Check ready to release (should be Grade A)
    assert len(status.ready_to_release) == 2
    # Should be sorted by score descending
    assert status.ready_to_release[0][1] == 95  # Highest score first

    # Check needs work (should be Grade D-F)
    assert len(status.needs_work) == 2
    # Should be sorted by score ascending
    assert status.needs_work[0][1] == 15  # Lowest score first

    return True


def test_get_library_status_grade_distribution_percentages(tmp_path):
    """get_library_status should calculate percentages correctly."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create 4 versions: 2 A, 1 B, 1 C
    scores = [('P1', 95, 'A'), ('P2', 85, 'A'), ('P3', 70, 'B'), ('P4', 50, 'C')]

    for name, score, grade in scores:
        project_dir = tmp_path / name
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / 'v1.als'),
            health_score=score,
            grade=grade,
            total_issues=0,
            critical_issues=0,
            warning_issues=0,
            total_devices=10,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)

    status, msg = get_library_status(db_path)

    assert status is not None

    grade_percentages = {g.grade: g.percentage for g in status.grade_distribution}

    # 2 out of 4 = 50%
    assert grade_percentages['A'] == 50.0
    # 1 out of 4 = 25%
    assert grade_percentages['B'] == 25.0
    # 1 out of 4 = 25%
    assert grade_percentages['C'] == 25.0
    # 0 out of 4 = 0%
    assert grade_percentages['D'] == 0.0
    assert grade_percentages['F'] == 0.0

    return True


def test_get_library_status_ready_to_release_limit(tmp_path):
    """get_library_status should return max 3 ready to release."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create 5 Grade A projects
    for i in range(5):
        project_dir = tmp_path / f'Project {i}'
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / 'v1.als'),
            health_score=80 + i,  # 80, 81, 82, 83, 84
            grade='A',
            total_issues=0,
            critical_issues=0,
            warning_issues=0,
            total_devices=10,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)

    status, msg = get_library_status(db_path)

    assert status is not None
    assert len(status.ready_to_release) == 3
    # Should be top 3 by score (84, 83, 82)
    assert status.ready_to_release[0][1] == 84
    assert status.ready_to_release[1][1] == 83
    assert status.ready_to_release[2][1] == 82

    return True


def test_get_library_status_needs_work_limit(tmp_path):
    """get_library_status should return max 3 needs work."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create 5 Grade D/F projects
    scores = [(25, 'D'), (20, 'D'), (15, 'F'), (10, 'F'), (5, 'F')]

    for i, (score, grade) in enumerate(scores):
        project_dir = tmp_path / f'Problem Project {i}'
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / 'v1.als'),
            health_score=score,
            grade=grade,
            total_issues=10,
            critical_issues=5,
            warning_issues=5,
            total_devices=20,
            disabled_devices=10,
            clutter_percentage=50.0,
            issues=[]
        )
        persist_scan_result(result, db_path)

    status, msg = get_library_status(db_path)

    assert status is not None
    assert len(status.needs_work) == 3
    # Should be bottom 3 by score (5, 10, 15)
    assert status.needs_work[0][1] == 5
    assert status.needs_work[1][1] == 10
    assert status.needs_work[2][1] == 15

    return True


def test_get_library_status_grade_order(tmp_path):
    """get_library_status should return grades in A-F order."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create one of each grade (in random order)
    scores = [('P1', 15, 'F'), ('P2', 85, 'A'), ('P3', 35, 'D'), ('P4', 55, 'C'), ('P5', 70, 'B')]

    for name, score, grade in scores:
        project_dir = tmp_path / name
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / 'v1.als'),
            health_score=score,
            grade=grade,
            total_issues=0,
            critical_issues=0,
            warning_issues=0,
            total_devices=10,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)

    status, msg = get_library_status(db_path)

    assert status is not None

    # Should be in A, B, C, D, F order
    grades = [g.grade for g in status.grade_distribution]
    assert grades == ['A', 'B', 'C', 'D', 'F']

    return True


# ==================== STORY 2.1: TRACK CHANGES BETWEEN VERSIONS ====================


def test_get_project_changes_schema(tmp_path):
    """Database should have changes table after init."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    db = Database(db_path)
    with db.connection() as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='changes'"
        )
        tables = [row['name'] for row in cursor.fetchall()]
        assert 'changes' in tables, "changes table should exist"

    return True


def test_get_project_changes_not_enough_versions(tmp_path):
    """get_project_changes should error with less than 2 versions."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Single Song'
    project_dir.mkdir()

    result = ScanResult(
        als_path=str(project_dir / 'v1.als'),
        health_score=80,
        grade='A',
        total_issues=0,
        critical_issues=0,
        warning_issues=0,
        total_devices=10,
        disabled_devices=0,
        clutter_percentage=0.0,
        issues=[]
    )
    persist_scan_result(result, db_path)

    changes, msg = get_project_changes("Single", db_path=db_path)

    assert changes is None
    assert "at least 2 versions" in msg.lower()

    return True


def test_get_project_changes_no_changes_stored(tmp_path):
    """get_project_changes should return empty changes when none stored."""
    import time
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Change Song'
    project_dir.mkdir()

    # Create two versions
    result1 = ScanResult(
        als_path=str(project_dir / 'v1.als'),
        health_score=60,
        grade='B',
        total_issues=5,
        critical_issues=1,
        warning_issues=4,
        total_devices=15,
        disabled_devices=3,
        clutter_percentage=20.0,
        issues=[]
    )
    persist_scan_result(result1, db_path)

    time.sleep(0.1)

    result2 = ScanResult(
        als_path=str(project_dir / 'v2.als'),
        health_score=85,
        grade='A',
        total_issues=2,
        critical_issues=0,
        warning_issues=2,
        total_devices=12,
        disabled_devices=1,
        clutter_percentage=8.3,
        issues=[]
    )
    persist_scan_result(result2, db_path)

    changes_result, msg = get_project_changes("Change", db_path=db_path)

    assert changes_result is not None
    assert msg == "OK"
    assert len(changes_result.comparisons) == 1

    # The comparison should exist but have no detailed changes
    comparison = changes_result.comparisons[0]
    assert comparison.before_filename == 'v1.als'
    assert comparison.after_filename == 'v2.als'
    assert comparison.health_delta == 25  # 85 - 60
    assert len(comparison.changes) == 0  # No changes stored yet

    return True


def test_get_project_changes_fuzzy_match(tmp_path):
    """get_project_changes should support fuzzy matching."""
    import time
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / '22 Project Remix'
    project_dir.mkdir()

    for i in range(2):
        result = ScanResult(
            als_path=str(project_dir / f'v{i+1}.als'),
            health_score=60 + i * 20,
            grade=_calculate_grade(60 + i * 20),
            total_issues=0,
            critical_issues=0,
            warning_issues=0,
            total_devices=10,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)
        time.sleep(0.1)

    # All these should find the project
    for search in ["22 Project Remix", "22", "remix", "proj"]:
        changes_result, msg = get_project_changes(search, db_path=db_path)
        assert changes_result is not None, f"Should find project with search '{search}'"
        assert changes_result.song_name == "22 Project Remix"

    return True


def test_get_project_changes_not_found(tmp_path):
    """get_project_changes should return None for non-existent project."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    changes_result, msg = get_project_changes("nonexistent", db_path=db_path)

    assert changes_result is None
    assert "not found" in msg.lower() or "no project" in msg.lower()

    return True


def test_get_project_changes_uninit_db(tmp_path):
    """get_project_changes should handle uninitialized database."""
    uninit_db = tmp_path / 'uninit.db'

    changes_result, msg = get_project_changes("any", db_path=uninit_db)

    assert changes_result is None
    assert "not initialized" in msg.lower()

    return True


def test_get_project_changes_multiple_versions(tmp_path):
    """get_project_changes should show all consecutive comparisons."""
    import time
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Multi Version Song'
    project_dir.mkdir()

    # Create 4 versions
    scores = [50, 70, 45, 80]  # Up, down, up pattern

    for i, score in enumerate(scores):
        result = ScanResult(
            als_path=str(project_dir / f'v{i+1}.als'),
            health_score=score,
            grade=_calculate_grade(score),
            total_issues=10 - i,
            critical_issues=0,
            warning_issues=10 - i,
            total_devices=15,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)
        time.sleep(0.1)

    changes_result, msg = get_project_changes("Multi", db_path=db_path)

    assert changes_result is not None
    assert len(changes_result.comparisons) == 3  # 4 versions = 3 transitions

    # Check transitions
    assert changes_result.comparisons[0].before_filename == 'v1.als'
    assert changes_result.comparisons[0].after_filename == 'v2.als'
    assert changes_result.comparisons[0].health_delta == 20  # 70 - 50
    assert changes_result.comparisons[0].is_improvement is True

    assert changes_result.comparisons[1].before_filename == 'v2.als'
    assert changes_result.comparisons[1].after_filename == 'v3.als'
    assert changes_result.comparisons[1].health_delta == -25  # 45 - 70
    assert changes_result.comparisons[1].is_improvement is False

    assert changes_result.comparisons[2].before_filename == 'v3.als'
    assert changes_result.comparisons[2].after_filename == 'v4.als'
    assert changes_result.comparisons[2].health_delta == 35  # 80 - 45
    assert changes_result.comparisons[2].is_improvement is True

    return True


def test_get_project_changes_from_version_filter(tmp_path):
    """get_project_changes should support --from filter."""
    import time
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Filter Song'
    project_dir.mkdir()

    for i in range(3):
        result = ScanResult(
            als_path=str(project_dir / f'v{i+1}.als'),
            health_score=50 + i * 15,
            grade=_calculate_grade(50 + i * 15),
            total_issues=0,
            critical_issues=0,
            warning_issues=0,
            total_devices=10,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)
        time.sleep(0.1)

    # Get changes from v2 to latest (v3)
    changes_result, msg = get_project_changes("Filter", from_version='v2.als', db_path=db_path)

    assert changes_result is not None
    assert len(changes_result.comparisons) == 1
    assert changes_result.comparisons[0].before_filename == 'v2.als'
    assert changes_result.comparisons[0].after_filename == 'v3.als'

    return True


def test_get_project_changes_to_version_filter(tmp_path):
    """get_project_changes should support --to filter."""
    import time
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Filter2 Song'
    project_dir.mkdir()

    for i in range(3):
        result = ScanResult(
            als_path=str(project_dir / f'v{i+1}.als'),
            health_score=50 + i * 15,
            grade=_calculate_grade(50 + i * 15),
            total_issues=0,
            critical_issues=0,
            warning_issues=0,
            total_devices=10,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)
        time.sleep(0.1)

    # Get changes from first to v2
    changes_result, msg = get_project_changes("Filter2", to_version='v2.als', db_path=db_path)

    assert changes_result is not None
    assert len(changes_result.comparisons) == 1
    assert changes_result.comparisons[0].before_filename == 'v1.als'
    assert changes_result.comparisons[0].after_filename == 'v2.als'

    return True


def test_get_project_changes_from_to_filter(tmp_path):
    """get_project_changes should support both --from and --to filters."""
    import time
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Filter3 Song'
    project_dir.mkdir()

    for i in range(4):
        result = ScanResult(
            als_path=str(project_dir / f'v{i+1}.als'),
            health_score=50 + i * 10,
            grade=_calculate_grade(50 + i * 10),
            total_issues=0,
            critical_issues=0,
            warning_issues=0,
            total_devices=10,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)
        time.sleep(0.1)

    # Get changes from v2 to v3 specifically
    changes_result, msg = get_project_changes("Filter3", from_version='v2.als', to_version='v3.als', db_path=db_path)

    assert changes_result is not None
    assert len(changes_result.comparisons) == 1
    assert changes_result.comparisons[0].before_filename == 'v2.als'
    assert changes_result.comparisons[0].after_filename == 'v3.als'

    return True


def test_get_project_changes_version_not_found(tmp_path):
    """get_project_changes should error when specified version not found."""
    import time
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Version Song'
    project_dir.mkdir()

    for i in range(2):
        result = ScanResult(
            als_path=str(project_dir / f'v{i+1}.als'),
            health_score=60 + i * 20,
            grade=_calculate_grade(60 + i * 20),
            total_issues=0,
            critical_issues=0,
            warning_issues=0,
            total_devices=10,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)
        time.sleep(0.1)

    # Try to get changes with non-existent version
    changes_result, msg = get_project_changes("Version", from_version='v99.als', db_path=db_path)

    assert changes_result is None
    assert "not found" in msg.lower()

    return True


# ==================== STORY 2.2: CORRELATE CHANGES WITH OUTCOMES (INSIGHTS) ====================


def test_confidence_level():
    """Test confidence level calculation."""
    assert _get_confidence_level(1) == 'LOW', "1 should be LOW"
    assert _get_confidence_level(2) == 'LOW', "2 should be LOW"
    assert _get_confidence_level(4) == 'LOW', "4 should be LOW"
    assert _get_confidence_level(5) == 'MEDIUM', "5 should be MEDIUM"
    assert _get_confidence_level(9) == 'MEDIUM', "9 should be MEDIUM"
    assert _get_confidence_level(10) == 'HIGH', "10 should be HIGH"
    assert _get_confidence_level(100) == 'HIGH', "100 should be HIGH"
    return True


def test_get_insights_uninit_db(tmp_path):
    """get_insights should handle uninitialized database."""
    uninit_db = tmp_path / 'uninit.db'

    result, msg = get_insights(uninit_db)

    assert result is None
    assert "not initialized" in msg.lower()

    return True


def test_get_insights_empty_db(tmp_path):
    """get_insights should work with empty database."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    result, msg = get_insights(db_path)

    assert result is not None
    assert msg == "OK"
    assert result.insufficient_data is True
    assert result.total_comparisons == 0
    assert result.total_changes == 0
    assert len(result.patterns_that_help) == 0
    assert len(result.patterns_that_hurt) == 0
    assert len(result.common_mistakes) == 0

    return True


def test_get_insights_insufficient_data(tmp_path):
    """get_insights should show insufficient data for < 10 comparisons."""
    import time
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create a project with just 3 versions (2 comparisons worth of changes)
    project_dir = tmp_path / 'Insight Song'
    project_dir.mkdir()

    for i in range(3):
        result = ScanResult(
            als_path=str(project_dir / f'v{i+1}.als'),
            health_score=50 + i * 15,
            grade=_calculate_grade(50 + i * 15),
            total_issues=5 - i,
            critical_issues=0,
            warning_issues=5 - i,
            total_devices=10,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)
        time.sleep(0.1)

    # Manually insert some changes (simulating track_changes)
    db = Database(db_path)
    with db.connection() as conn:
        # Get version IDs
        cursor = conn.execute("SELECT id FROM versions ORDER BY scanned_at")
        version_ids = [row['id'] for row in cursor.fetchall()]

        # Insert a change between v1 and v2
        conn.execute("""
            INSERT INTO changes (project_id, before_version_id, after_version_id,
                                 change_type, track_name, device_name, device_type, health_delta)
            VALUES (1, ?, ?, 'device_removed', 'Kick', 'Unused EQ', 'Eq8', 15)
        """, (version_ids[0], version_ids[1]))

    result, msg = get_insights(db_path)

    assert result is not None
    assert msg == "OK"
    assert result.insufficient_data is True
    assert "Insufficient data" in result.message
    assert result.total_comparisons < 10

    return True


def test_get_insights_with_sufficient_data(tmp_path):
    """get_insights should return patterns when sufficient data exists."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create enough data (10+ comparisons)
    db = Database(db_path)
    with db.connection() as conn:
        # Create a project
        conn.execute("INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
                     ('/test/project', 'Test Song'))

        # Create versions
        for i in range(12):
            conn.execute("""
                INSERT INTO versions (project_id, als_path, als_filename, health_score, grade, total_issues)
                VALUES (1, ?, ?, ?, ?, ?)
            """, (f'/test/project/v{i+1}.als', f'v{i+1}.als', 50 + i * 3, 'B', 5 - (i % 3)))

        # Get version IDs
        cursor = conn.execute("SELECT id FROM versions ORDER BY id")
        version_ids = [row['id'] for row in cursor.fetchall()]

        # Create 11 comparisons with changes - use consistent health delta to create clear patterns
        for i in range(11):
            # Insert multiple changes per comparison with positive delta for removed devices
            conn.execute("""
                INSERT INTO changes (project_id, before_version_id, after_version_id,
                                     change_type, track_name, device_name, device_type, health_delta)
                VALUES (1, ?, ?, 'device_removed', 'Kick', ?, 'Eq8', ?)
            """, (version_ids[i], version_ids[i+1], f'EQ_{i}', 8))

            # Insert changes with negative delta for added devices
            conn.execute("""
                INSERT INTO changes (project_id, before_version_id, after_version_id,
                                     change_type, track_name, device_name, device_type, health_delta)
                VALUES (1, ?, ?, 'device_added', 'Bass', ?, 'Compressor', ?)
            """, (version_ids[i], version_ids[i+1], f'Comp_{i}', -5))

    result, msg = get_insights(db_path)

    assert result is not None
    assert msg == "OK"
    assert result.insufficient_data is False
    assert result.total_comparisons >= 10
    assert result.total_changes > 0

    # Should have some patterns identified - since we have clear positive and negative patterns
    all_patterns = len(result.patterns_that_help) + len(result.patterns_that_hurt)
    assert all_patterns > 0, f"Should have patterns, got help={len(result.patterns_that_help)}, hurt={len(result.patterns_that_hurt)}"

    return True


def test_get_insights_patterns_that_help(tmp_path):
    """get_insights should identify patterns that help health."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    db = Database(db_path)
    with db.connection() as conn:
        # Create a project
        conn.execute("INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
                     ('/test/project', 'Test Song'))

        # Create versions
        for i in range(12):
            conn.execute("""
                INSERT INTO versions (project_id, als_path, als_filename, health_score, grade, total_issues)
                VALUES (1, ?, ?, ?, ?, ?)
            """, (f'/test/project/v{i+1}.als', f'v{i+1}.als', 50 + i * 3, 'B', 5))

        # Get version IDs
        cursor = conn.execute("SELECT id FROM versions ORDER BY id")
        version_ids = [row['id'] for row in cursor.fetchall()]

        # Create changes where removing Eq8 always helps (positive delta)
        for i in range(11):
            conn.execute("""
                INSERT INTO changes (project_id, before_version_id, after_version_id,
                                     change_type, track_name, device_name, device_type, health_delta)
                VALUES (1, ?, ?, 'device_removed', 'Kick', ?, 'Eq8', ?)
            """, (version_ids[i], version_ids[i+1], f'EQ_{i}', 10))  # Always positive delta

    result, msg = get_insights(db_path)

    assert result is not None
    assert result.insufficient_data is False

    # Should have identified removing Eq8 as helpful
    eq8_patterns = [p for p in result.patterns_that_help if p.device_type == 'Eq8']
    assert len(eq8_patterns) > 0, "Should identify Eq8 removal as helpful"

    # Check pattern details
    pattern = eq8_patterns[0]
    assert pattern.change_type == 'device_removed'
    assert pattern.helps_health is True
    assert pattern.avg_health_delta > 0
    assert pattern.confidence == 'HIGH'  # 11 occurrences

    return True


def test_get_insights_patterns_that_hurt(tmp_path):
    """get_insights should identify patterns that hurt health."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    db = Database(db_path)
    with db.connection() as conn:
        # Create a project
        conn.execute("INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
                     ('/test/project', 'Test Song'))

        # Create versions
        for i in range(12):
            conn.execute("""
                INSERT INTO versions (project_id, als_path, als_filename, health_score, grade, total_issues)
                VALUES (1, ?, ?, ?, ?, ?)
            """, (f'/test/project/v{i+1}.als', f'v{i+1}.als', 80 - i * 2, 'A', 3))

        # Get version IDs
        cursor = conn.execute("SELECT id FROM versions ORDER BY id")
        version_ids = [row['id'] for row in cursor.fetchall()]

        # Create changes where adding Reverb always hurts (negative delta)
        for i in range(11):
            conn.execute("""
                INSERT INTO changes (project_id, before_version_id, after_version_id,
                                     change_type, track_name, device_name, device_type, health_delta)
                VALUES (1, ?, ?, 'device_added', 'Master', ?, 'Reverb', ?)
            """, (version_ids[i], version_ids[i+1], f'Reverb_{i}', -8))  # Always negative delta

    result, msg = get_insights(db_path)

    assert result is not None
    assert result.insufficient_data is False

    # Should have identified adding Reverb as harmful
    reverb_patterns = [p for p in result.patterns_that_hurt if p.device_type == 'Reverb']
    assert len(reverb_patterns) > 0, "Should identify Reverb addition as harmful"

    # Check pattern details
    pattern = reverb_patterns[0]
    assert pattern.change_type == 'device_added'
    assert pattern.helps_health is False
    assert pattern.avg_health_delta < 0
    assert pattern.confidence == 'HIGH'  # 11 occurrences

    return True


def test_get_insights_common_mistakes(tmp_path):
    """get_insights should identify common mistakes."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    db = Database(db_path)
    with db.connection() as conn:
        # Create a project
        conn.execute("INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
                     ('/test/project', 'Test Song'))

        # Create versions
        for i in range(15):
            conn.execute("""
                INSERT INTO versions (project_id, als_path, als_filename, health_score, grade, total_issues)
                VALUES (1, ?, ?, ?, ?, ?)
            """, (f'/test/project/v{i+1}.als', f'v{i+1}.als', 70, 'B', 3))

        # Get version IDs
        cursor = conn.execute("SELECT id FROM versions ORDER BY id")
        version_ids = [row['id'] for row in cursor.fetchall()]

        # Create a repeated pattern of mistakes (adding Limiter with negative health)
        for i in range(14):
            conn.execute("""
                INSERT INTO changes (project_id, before_version_id, after_version_id,
                                     change_type, track_name, device_name, device_type, health_delta)
                VALUES (1, ?, ?, 'device_added', 'Master', ?, 'Limiter', ?)
            """, (version_ids[i], version_ids[i+1], f'Limiter_{i}', -5))

    result, msg = get_insights(db_path)

    assert result is not None
    assert result.insufficient_data is False

    # Should have common mistakes identified
    # With 14 occurrences of the same harmful pattern, it should appear
    # Note: common_mistakes requires 3+ occurrences and negative delta
    limiter_mistakes = [m for m in result.common_mistakes if 'Limiter' in m.description]
    assert len(limiter_mistakes) > 0 or len(result.patterns_that_hurt) > 0, \
        "Should identify Limiter addition pattern"

    return True


def test_get_insights_confidence_levels(tmp_path):
    """get_insights should assign correct confidence levels."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    db = Database(db_path)
    with db.connection() as conn:
        # Create a project
        conn.execute("INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
                     ('/test/project', 'Test Song'))

        # Create many versions
        for i in range(25):
            conn.execute("""
                INSERT INTO versions (project_id, als_path, als_filename, health_score, grade, total_issues)
                VALUES (1, ?, ?, ?, ?, ?)
            """, (f'/test/project/v{i+1}.als', f'v{i+1}.als', 60 + i, 'B', 3))

        # Get version IDs
        cursor = conn.execute("SELECT id FROM versions ORDER BY id")
        version_ids = [row['id'] for row in cursor.fetchall()]

        # Create different patterns with different frequencies
        # Pattern A: 12 occurrences (HIGH confidence)
        for i in range(12):
            conn.execute("""
                INSERT INTO changes (project_id, before_version_id, after_version_id,
                                     change_type, track_name, device_name, device_type, health_delta)
                VALUES (1, ?, ?, 'device_removed', 'Kick', 'HighFreq', 'HighFreqDevice', 10)
            """, (version_ids[i], version_ids[i+1]))

        # Pattern B: 7 occurrences (MEDIUM confidence)
        for i in range(12, 19):
            conn.execute("""
                INSERT INTO changes (project_id, before_version_id, after_version_id,
                                     change_type, track_name, device_name, device_type, health_delta)
                VALUES (1, ?, ?, 'device_added', 'Bass', 'MedFreq', 'MedFreqDevice', 8)
            """, (version_ids[i], version_ids[i+1]))

        # Pattern C: 3 occurrences (LOW confidence)
        for i in range(19, 22):
            conn.execute("""
                INSERT INTO changes (project_id, before_version_id, after_version_id,
                                     change_type, track_name, device_name, device_type, health_delta)
                VALUES (1, ?, ?, 'device_disabled', 'Synth', 'LowFreq', 'LowFreqDevice', 5)
            """, (version_ids[i], version_ids[i+1]))

    result, msg = get_insights(db_path)

    assert result is not None
    assert result.insufficient_data is False

    # Check confidence levels are assigned
    all_patterns = result.patterns_that_help + result.patterns_that_hurt
    high_conf = [p for p in all_patterns if p.confidence == 'HIGH']
    med_conf = [p for p in all_patterns if p.confidence == 'MEDIUM']
    low_conf = [p for p in all_patterns if p.confidence == 'LOW']

    # We should have patterns at different confidence levels
    assert len(high_conf) > 0 or len(med_conf) > 0 or len(low_conf) > 0, \
        "Should have patterns with confidence levels"

    return True


# ==================== STORY 2.4: STYLE PROFILE ====================


def test_get_style_profile_uninit_db(tmp_path):
    """get_style_profile should handle uninitialized database."""
    uninit_db = tmp_path / 'uninit.db'

    result, msg = get_style_profile(uninit_db)

    assert result is None
    assert "not initialized" in msg.lower()

    return True


def test_get_style_profile_empty_db(tmp_path):
    """get_style_profile should handle empty database."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    result, msg = get_style_profile(db_path)

    assert result is None
    assert "no versions" in msg.lower() or "insufficient" in msg.lower()

    return True


def test_get_style_profile_insufficient_grade_a(tmp_path):
    """get_style_profile should require minimum Grade A versions."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create only 2 Grade A versions (need 3 minimum by default)
    for i in range(2):
        project_dir = tmp_path / f'Song {i}'
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / 'v1.als'),
            health_score=85 + i * 5,  # 85, 90 - both Grade A
            grade='A',
            total_issues=1,
            critical_issues=0,
            warning_issues=1,
            total_devices=10,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)

    profile, msg = get_style_profile(db_path, min_grade_a_versions=3)

    assert profile is None
    assert "at least 3" in msg.lower() or "insufficient" in msg.lower()

    return True


def test_get_style_profile_with_sufficient_data(tmp_path):
    """get_style_profile should return profile with sufficient Grade A versions."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create 4 Grade A versions
    for i in range(4):
        project_dir = tmp_path / f'Good Song {i}'
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / 'v1.als'),
            health_score=80 + i * 5,  # 80, 85, 90, 95 - all Grade A
            grade='A',
            total_issues=2 - (i % 2),
            critical_issues=0,
            warning_issues=2 - (i % 2),
            total_devices=12 + i,
            disabled_devices=i % 2,
            clutter_percentage=5.0 + i,
            issues=[]
        )
        persist_scan_result(result, db_path)

    # Create 2 Grade D/F versions for comparison
    for i in range(2):
        project_dir = tmp_path / f'Bad Song {i}'
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / 'v1.als'),
            health_score=15 + i * 10,  # 15, 25 - Grade F and D
            grade='F' if i == 0 else 'D',
            total_issues=10 + i,
            critical_issues=3,
            warning_issues=7 + i,
            total_devices=25 + i * 5,
            disabled_devices=8 + i,
            clutter_percentage=35.0 + i * 5,
            issues=[]
        )
        persist_scan_result(result, db_path)

    profile, msg = get_style_profile(db_path, min_grade_a_versions=3)

    assert profile is not None
    assert msg == "OK"
    assert profile.grade_a_versions == 4
    assert profile.grade_df_versions == 2
    assert profile.avg_health_score_a >= 80
    assert profile.avg_health_score_df < 40
    assert profile.avg_devices_per_track_a > 0
    assert len(profile.insights) > 0

    return True


def test_get_style_profile_calculates_averages(tmp_path):
    """get_style_profile should calculate correct averages."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create 3 Grade A versions with known values
    devices = [10, 12, 14]
    disabled = [0, 1, 2]
    scores = [80, 90, 100]

    for i in range(3):
        project_dir = tmp_path / f'Song {i}'
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / 'v1.als'),
            health_score=scores[i],
            grade='A',
            total_issues=1,
            critical_issues=0,
            warning_issues=1,
            total_devices=devices[i],
            disabled_devices=disabled[i],
            clutter_percentage=(disabled[i] / devices[i]) * 100,
            issues=[]
        )
        persist_scan_result(result, db_path)

    profile, msg = get_style_profile(db_path, min_grade_a_versions=3)

    assert profile is not None
    # Average health score: (80 + 90 + 100) / 3 = 90
    assert profile.avg_health_score_a == 90.0
    # Average devices: (10 + 12 + 14) / 3 = 12
    assert profile.avg_devices_per_track_a == 12.0
    # Average disabled %: (0 + 8.33 + 14.29) / 3 ≈ 7.54
    assert 5.0 <= profile.avg_disabled_pct_a <= 10.0

    return True


def test_save_profile_to_json(tmp_path):
    """save_profile_to_json should save profile correctly."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create sufficient data
    for i in range(3):
        project_dir = tmp_path / f'Song {i}'
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / 'v1.als'),
            health_score=85 + i * 5,
            grade='A',
            total_issues=1,
            critical_issues=0,
            warning_issues=1,
            total_devices=12,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)

    profile, msg = get_style_profile(db_path, min_grade_a_versions=3)
    assert profile is not None

    # Save to a custom path
    output_path = tmp_path / 'profile.json'
    success, save_msg = save_profile_to_json(profile, output_path)

    assert success is True
    assert output_path.exists()

    # Verify JSON content
    import json
    with open(output_path) as f:
        data = json.load(f)

    assert 'generated_at' in data
    assert data['grade_a_versions'] == 3
    assert data['avg_health_score_a'] == profile.avg_health_score_a

    return True


def test_load_profile_from_json(tmp_path):
    """load_profile_from_json should load profile correctly."""
    # Create a test JSON file
    import json
    profile_path = tmp_path / 'profile.json'
    test_data = {
        'generated_at': '2026-01-25T12:00:00',
        'total_versions_analyzed': 5,
        'grade_a_versions': 3,
        'grade_df_versions': 2,
        'avg_health_score_a': 90.0,
        'avg_health_score_df': 25.0,
        'avg_devices_per_track_a': 12.0,
        'avg_devices_per_track_df': 20.0,
        'avg_disabled_pct_a': 5.0,
        'avg_disabled_pct_df': 30.0,
        'track_profiles': {},
        'common_plugins': [['Eq8', 10, 85.0]],
        'insights': ['Test insight']
    }

    with open(profile_path, 'w') as f:
        json.dump(test_data, f)

    data, msg = load_profile_from_json(profile_path)

    assert data is not None
    assert msg == "OK"
    assert data['grade_a_versions'] == 3
    assert data['avg_health_score_a'] == 90.0
    assert len(data['common_plugins']) == 1
    assert data['insights'][0] == 'Test insight'

    return True


def test_load_profile_from_json_not_found(tmp_path):
    """load_profile_from_json should handle missing file."""
    missing_path = tmp_path / 'nonexistent.json'

    data, msg = load_profile_from_json(missing_path)

    assert data is None
    assert "not found" in msg.lower() or "does not exist" in msg.lower()

    return True


def test_compare_file_against_profile_no_profile(tmp_path):
    """compare_file_against_profile should handle missing profile."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create a version but no profile
    project_dir = tmp_path / 'Test Song'
    project_dir.mkdir()
    result = ScanResult(
        als_path=str(project_dir / 'v1.als'),
        health_score=70,
        grade='B',
        total_issues=3,
        critical_issues=0,
        warning_issues=3,
        total_devices=15,
        disabled_devices=2,
        clutter_percentage=13.3,
        issues=[]
    )
    persist_scan_result(result, db_path)

    # Try to compare without profile (not enough Grade A versions)
    comparison, msg = compare_file_against_profile(str(project_dir / 'v1.als'), db_path)

    # Should fail because no profile can be generated
    assert comparison is None or "profile" in msg.lower() or "insufficient" in msg.lower()

    return True


def test_compare_file_against_profile_file_not_scanned(tmp_path):
    """compare_file_against_profile should handle unscanned file."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create enough Grade A versions for a profile
    for i in range(3):
        project_dir = tmp_path / f'Good Song {i}'
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / 'v1.als'),
            health_score=85 + i * 5,
            grade='A',
            total_issues=1,
            critical_issues=0,
            warning_issues=1,
            total_devices=12,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)

    # Try to compare a file that hasn't been scanned
    comparison, msg = compare_file_against_profile('/nonexistent/path/song.als', db_path)

    assert comparison is None
    assert "not found" in msg.lower() or "not scanned" in msg.lower()

    return True


def test_compare_file_against_profile_success(tmp_path):
    """compare_file_against_profile should return comparison results."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create enough Grade A versions for a profile
    for i in range(3):
        project_dir = tmp_path / f'Good Song {i}'
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / 'v1.als'),
            health_score=85 + i * 5,
            grade='A',
            total_issues=1,
            critical_issues=0,
            warning_issues=1,
            total_devices=12,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)

    # Create a file to compare
    compare_dir = tmp_path / 'Compare Song'
    compare_dir.mkdir()
    compare_result = ScanResult(
        als_path=str(compare_dir / 'compare.als'),
        health_score=70,
        grade='B',
        total_issues=5,
        critical_issues=1,
        warning_issues=4,
        total_devices=18,
        disabled_devices=4,
        clutter_percentage=22.2,
        issues=[]
    )
    persist_scan_result(compare_result, db_path)

    # Compare the file
    comparison, msg = compare_file_against_profile(str(compare_dir / 'compare.als'), db_path)

    assert comparison is not None
    assert msg == "OK"
    assert comparison.als_filename == 'compare.als'
    assert comparison.health_score == 70
    assert comparison.grade == 'B'
    assert comparison.similarity_score >= 0 and comparison.similarity_score <= 100
    assert len(comparison.recommendations) >= 0

    return True


def test_style_profile_generates_insights(tmp_path):
    """get_style_profile should generate meaningful insights."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create Grade A versions with low device counts and disabled %
    for i in range(3):
        project_dir = tmp_path / f'Good Song {i}'
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / 'v1.als'),
            health_score=90,
            grade='A',
            total_issues=1,
            critical_issues=0,
            warning_issues=1,
            total_devices=10,
            disabled_devices=0,
            clutter_percentage=0.0,
            issues=[]
        )
        persist_scan_result(result, db_path)

    # Create Grade D/F versions with high device counts and disabled %
    for i in range(2):
        project_dir = tmp_path / f'Bad Song {i}'
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / 'v1.als'),
            health_score=20,
            grade='D',
            total_issues=15,
            critical_issues=5,
            warning_issues=10,
            total_devices=30,
            disabled_devices=12,
            clutter_percentage=40.0,
            issues=[]
        )
        persist_scan_result(result, db_path)

    profile, msg = get_style_profile(db_path, min_grade_a_versions=3)

    assert profile is not None
    assert len(profile.insights) > 0

    # Should have insights about device counts and disabled percentages
    insights_text = ' '.join(profile.insights).lower()
    assert 'device' in insights_text or 'clutter' in insights_text or 'disabled' in insights_text

    return True


# ==================== SMART RECOMMENDATIONS TESTS (Story 2.6) ====================

# Import smart recommendations functions
smart_diagnose = database_module.smart_diagnose
SmartDiagnoseResult = database_module.SmartDiagnoseResult
SmartRecommendation = database_module.SmartRecommendation
has_sufficient_history = database_module.has_sufficient_history
_count_database_versions = database_module._count_database_versions
_get_pattern_history = database_module._get_pattern_history
_calculate_recommendation_priority = database_module._calculate_recommendation_priority


def test_count_database_versions(tmp_path):
    """_count_database_versions should return correct version count."""
    db_path = tmp_path / 'test.db'

    # Empty DB
    db_init(db_path)
    count = _count_database_versions(db_path)
    assert count == 0, f"Expected 0, got {count}"

    # Add versions
    for i in range(5):
        project_dir = tmp_path / f'Project{i}'
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / 'v1.als'),
            health_score=70,
            grade='B',
            total_issues=2,
            critical_issues=0,
            warning_issues=2,
            total_devices=10,
            disabled_devices=1,
            clutter_percentage=10.0,
            issues=[]
        )
        persist_scan_result(result, db_path)

    count = _count_database_versions(db_path)
    assert count == 5, f"Expected 5, got {count}"

    return True


def test_has_sufficient_history(tmp_path):
    """has_sufficient_history should return True when 20+ versions exist."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create 19 versions - should be False
    for i in range(19):
        project_dir = tmp_path / f'Project{i}'
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / 'v1.als'),
            health_score=70,
            grade='B',
            total_issues=2,
            critical_issues=0,
            warning_issues=2,
            total_devices=10,
            disabled_devices=1,
            clutter_percentage=10.0,
            issues=[]
        )
        persist_scan_result(result, db_path)

    assert has_sufficient_history(db_path) is False

    # Add one more to reach 20
    project_dir = tmp_path / 'Project20'
    project_dir.mkdir()
    result = ScanResult(
        als_path=str(project_dir / 'v1.als'),
        health_score=70,
        grade='B',
        total_issues=2,
        critical_issues=0,
        warning_issues=2,
        total_devices=10,
        disabled_devices=1,
        clutter_percentage=10.0,
        issues=[]
    )
    persist_scan_result(result, db_path)

    assert has_sufficient_history(db_path) is True

    return True


def test_smart_diagnose_uninit_db(tmp_path):
    """smart_diagnose should fail gracefully with uninitialized DB."""
    db_path = tmp_path / 'test.db'

    result, msg = smart_diagnose("/fake/path.als", db_path=db_path)

    assert result is None
    assert "not initialized" in msg.lower()

    return True


def test_smart_diagnose_file_not_in_db(tmp_path):
    """smart_diagnose should fail when file not in database."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    result, msg = smart_diagnose("/fake/path.als", db_path=db_path)

    assert result is None
    assert "not found" in msg.lower() or "diagnose" in msg.lower()

    return True


def test_smart_diagnose_with_scan_result(tmp_path):
    """smart_diagnose should work with provided scan result."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Test Project'
    project_dir.mkdir()
    als_path = str(project_dir / 'v1.als')

    # Create scan result
    scan_result = ScanResult(
        als_path=als_path,
        health_score=65,
        grade='B',
        total_issues=5,
        critical_issues=1,
        warning_issues=3,
        total_devices=15,
        disabled_devices=3,
        clutter_percentage=20.0,
        issues=[
            ScanResultIssue(
                track_name='Kick',
                severity='critical',
                category='clutter',
                description='Too many disabled devices',
                fix_suggestion='Delete disabled devices'
            ),
            ScanResultIssue(
                track_name='Bass',
                severity='warning',
                category='chain_order',
                description='EQ before compressor',
                fix_suggestion='Move EQ after compressor'
            ),
            ScanResultIssue(
                track_name=None,
                severity='suggestion',
                category='optimization',
                description='Consider freezing tracks',
                fix_suggestion='Freeze CPU-heavy tracks'
            )
        ]
    )

    # Persist to DB first
    persist_scan_result(scan_result, db_path)

    # Now smart diagnose
    result, msg = smart_diagnose(als_path, scan_result, db_path)

    assert result is not None, f"Expected result, got None: {msg}"
    assert result.health_score == 65
    assert result.grade == 'B'
    assert len(result.recommendations) == 3
    assert result.critical_count == 1
    assert result.warning_count == 1
    assert result.suggestion_count == 1

    return True


def test_smart_diagnose_prioritizes_critical(tmp_path):
    """smart_diagnose should prioritize critical issues higher."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Test Project'
    project_dir.mkdir()
    als_path = str(project_dir / 'v1.als')

    # Create scan result with mixed severities
    scan_result = ScanResult(
        als_path=als_path,
        health_score=50,
        grade='C',
        total_issues=3,
        critical_issues=1,
        warning_issues=1,
        total_devices=10,
        disabled_devices=2,
        clutter_percentage=20.0,
        issues=[
            ScanResultIssue(
                track_name=None,
                severity='suggestion',
                category='optimization',
                description='Suggestion issue',
                fix_suggestion='Fix suggestion'
            ),
            ScanResultIssue(
                track_name='Kick',
                severity='critical',
                category='clutter',
                description='Critical issue',
                fix_suggestion='Fix critical'
            ),
            ScanResultIssue(
                track_name='Bass',
                severity='warning',
                category='chain_order',
                description='Warning issue',
                fix_suggestion='Fix warning'
            ),
        ]
    )

    persist_scan_result(scan_result, db_path)
    result, msg = smart_diagnose(als_path, scan_result, db_path)

    assert result is not None
    # Critical should be first (highest priority)
    assert result.recommendations[0].severity == 'critical'
    # Critical priority should be 90 base
    assert result.recommendations[0].priority >= 80

    return True


def test_smart_diagnose_insufficient_history_flag(tmp_path):
    """smart_diagnose should flag when history is insufficient."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Test Project'
    project_dir.mkdir()
    als_path = str(project_dir / 'v1.als')

    scan_result = ScanResult(
        als_path=als_path,
        health_score=70,
        grade='B',
        total_issues=1,
        critical_issues=0,
        warning_issues=1,
        total_devices=10,
        disabled_devices=1,
        clutter_percentage=10.0,
        issues=[
            ScanResultIssue(
                track_name='Kick',
                severity='warning',
                category='clutter',
                description='Test issue',
                fix_suggestion='Fix it'
            )
        ]
    )

    persist_scan_result(scan_result, db_path)
    result, msg = smart_diagnose(als_path, scan_result, db_path)

    assert result is not None
    assert result.has_sufficient_history is False
    assert result.versions_analyzed == 1

    return True


def test_get_pattern_history(tmp_path):
    """_get_pattern_history should return historical patterns from changes."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Initially empty
    patterns = _get_pattern_history(db_path)
    assert len(patterns) == 0

    # Add some versions with change data
    db = get_db(db_path)
    with db.connection() as conn:
        # Create a project
        cursor = conn.execute(
            "INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
            ('/test/path', 'Test Song')
        )
        project_id = cursor.lastrowid

        # Create versions
        cursor = conn.execute(
            "INSERT INTO versions (project_id, als_path, als_filename, health_score, grade) VALUES (?, ?, ?, ?, ?)",
            (project_id, '/test/path/v1.als', 'v1.als', 50, 'C')
        )
        v1_id = cursor.lastrowid

        cursor = conn.execute(
            "INSERT INTO versions (project_id, als_path, als_filename, health_score, grade) VALUES (?, ?, ?, ?, ?)",
            (project_id, '/test/path/v2.als', 'v2.als', 70, 'B')
        )
        v2_id = cursor.lastrowid

        # Add change records
        for i in range(3):
            conn.execute(
                """INSERT INTO changes
                   (project_id, before_version_id, after_version_id, change_type, device_type, health_delta)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (project_id, v1_id, v2_id, 'device_removed', 'Eq8', 10)
            )

    patterns = _get_pattern_history(db_path)
    assert len(patterns) > 0
    key = ('device_removed', 'Eq8')
    assert key in patterns
    assert patterns[key]['occurrence_count'] == 3
    assert patterns[key]['times_helped'] == 3  # All had positive health_delta

    return True


def test_calculate_recommendation_priority(tmp_path):
    """_calculate_recommendation_priority should boost priority based on history."""
    # No history - should use base severity priority
    issue = ScanResultIssue(
        track_name='Kick',
        severity='critical',
        category='clutter',
        description='Test issue',
        fix_suggestion='Fix it'
    )

    priority, confidence, helped_before, times_helped, avg_improvement = _calculate_recommendation_priority(
        issue, {}, None
    )

    # Critical base priority is 90
    assert priority == 90
    assert confidence == 'LOW'
    assert helped_before is False

    # With history that shows this type of fix helps
    pattern_history = {
        ('device_disabled', 'unknown'): {
            'occurrence_count': 15,
            'avg_health_delta': 8.5,
            'times_helped': 12,
            'times_hurt': 3
        }
    }

    priority2, confidence2, helped_before2, times_helped2, avg_improvement2 = _calculate_recommendation_priority(
        issue, pattern_history, None
    )

    # Should boost priority and mark as helped before
    assert priority2 >= priority  # Priority should be same or higher
    assert helped_before2 is True
    assert times_helped2 == 12
    assert avg_improvement2 == 8.5
    assert confidence2 == 'HIGH'  # 15 occurrences = HIGH confidence

    return True


def test_smart_diagnose_with_sufficient_history(tmp_path):
    """smart_diagnose should work better with 20+ versions."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create 22 versions
    for i in range(22):
        project_dir = tmp_path / f'Project{i}'
        project_dir.mkdir()
        result = ScanResult(
            als_path=str(project_dir / 'v1.als'),
            health_score=60 + (i % 30),
            grade='B' if i % 2 == 0 else 'C',
            total_issues=2,
            critical_issues=0,
            warning_issues=2,
            total_devices=10,
            disabled_devices=1,
            clutter_percentage=10.0,
            issues=[]
        )
        persist_scan_result(result, db_path)

    # Now diagnose a new one
    project_dir = tmp_path / 'TestProject'
    project_dir.mkdir()
    als_path = str(project_dir / 'v1.als')

    scan_result = ScanResult(
        als_path=als_path,
        health_score=65,
        grade='B',
        total_issues=2,
        critical_issues=1,
        warning_issues=1,
        total_devices=12,
        disabled_devices=2,
        clutter_percentage=16.0,
        issues=[
            ScanResultIssue(
                track_name='Kick',
                severity='critical',
                category='clutter',
                description='Test critical',
                fix_suggestion='Fix critical'
            ),
            ScanResultIssue(
                track_name='Bass',
                severity='warning',
                category='chain_order',
                description='Test warning',
                fix_suggestion='Fix warning'
            )
        ]
    )

    persist_scan_result(scan_result, db_path)
    result, msg = smart_diagnose(als_path, scan_result, db_path)

    assert result is not None
    assert result.has_sufficient_history is True
    assert result.versions_analyzed >= 20

    return True


def test_smart_recommendation_dataclass():
    """SmartRecommendation dataclass should have all required fields."""
    rec = SmartRecommendation(
        severity='warning',
        category='clutter',
        description='Test description',
        recommendation='Test fix',
        track_name='Kick',
        priority=75,
        confidence='MEDIUM',
        confidence_reason='Test reason',
        helped_before=True,
        times_helped=5,
        avg_improvement=3.5,
        previously_ignored=False,
        times_ignored=0
    )

    assert rec.severity == 'warning'
    assert rec.category == 'clutter'
    assert rec.priority == 75
    assert rec.confidence == 'MEDIUM'
    assert rec.helped_before is True
    assert rec.times_helped == 5
    assert rec.avg_improvement == 3.5

    return True


def test_smart_diagnose_result_dataclass(tmp_path):
    """SmartDiagnoseResult dataclass should have all required fields."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    project_dir = tmp_path / 'Test'
    project_dir.mkdir()
    als_path = str(project_dir / 'v1.als')

    scan_result = ScanResult(
        als_path=als_path,
        health_score=80,
        grade='A',
        total_issues=0,
        critical_issues=0,
        warning_issues=0,
        total_devices=10,
        disabled_devices=0,
        clutter_percentage=0.0,
        issues=[]
    )

    persist_scan_result(scan_result, db_path)
    result, msg = smart_diagnose(als_path, scan_result, db_path)

    assert result is not None
    assert hasattr(result, 'als_path')
    assert hasattr(result, 'als_filename')
    assert hasattr(result, 'health_score')
    assert hasattr(result, 'grade')
    assert hasattr(result, 'total_issues')
    assert hasattr(result, 'recommendations')
    assert hasattr(result, 'has_sufficient_history')
    assert hasattr(result, 'versions_analyzed')
    assert hasattr(result, 'profile_available')
    assert hasattr(result, 'critical_count')
    assert hasattr(result, 'warning_count')
    assert hasattr(result, 'suggestion_count')
    assert hasattr(result, 'profile_similarity')

    return True


def run_all_tests():
    """Run all tests and report results."""
    tests_1_2 = [
        # Story 1.2: Persist Scan Results
        ('Grade calculation', test_grade_calculation),
        ('Persist creates project', test_persist_creates_project),
        ('Persist creates version with data', test_persist_creates_version_with_data),
        ('Persist stores issues', test_persist_stores_issues),
        ('Upsert updates existing', test_upsert_updates_existing),
        ('Song name from folder', test_song_name_from_folder),
        ('Multiple versions same project', test_multiple_versions_same_project),
        ('Fails without init', test_fails_without_init),
        ('Batch persist', test_batch_persist),
    ]

    tests_1_3 = [
        # Story 1.3: List All Projects
        ('Trend calculation', test_trend_calculation),
        ('List projects empty DB', test_list_projects_empty_db),
        ('List projects returns summary', test_list_projects_returns_summary),
        ('List projects multiple versions', test_list_projects_multiple_versions),
        ('List projects sort by name', test_list_projects_sort_by_name),
        ('List projects sort by score', test_list_projects_sort_by_score),
        ('List projects sort by date', test_list_projects_sort_by_date),
        ('List projects trend declining', test_list_projects_trend_declining),
        ('List projects uninit DB', test_list_projects_uninit_db),
    ]

    tests_1_4 = [
        # Story 1.4: Project History
        ('Fuzzy match exact', test_fuzzy_match_exact),
        ('Fuzzy match substring', test_fuzzy_match_substring),
        ('Fuzzy match word start', test_fuzzy_match_word_start),
        ('Find project by name', test_find_project_by_name),
        ('Find project prefers exact match', test_find_project_prefers_exact_match),
        ('Get project history basic', test_get_project_history_basic),
        ('Get project history with delta', test_get_project_history_with_delta),
        ('Get project history best version', test_get_project_history_best_version),
        ('Get project history fuzzy match', test_get_project_history_fuzzy_match),
        ('Get project history not found', test_get_project_history_not_found),
        ('Get project history uninit DB', test_get_project_history_uninit_db),
        ('Get project history current version', test_get_project_history_current_version),
    ]

    tests_1_5 = [
        # Story 1.5: Best Version
        ('Get best version basic', test_get_best_version_basic),
        ('Get best version tie prefers recent', test_get_best_version_tie_prefers_recent),
        ('Get best version comparison to latest', test_get_best_version_comparison_to_latest),
        ('Get best version best is latest', test_get_best_version_best_is_latest),
        ('Get best version fuzzy match', test_get_best_version_fuzzy_match),
        ('Get best version not found', test_get_best_version_not_found),
        ('Get best version uninit DB', test_get_best_version_uninit_db),
        ('Get best version single version', test_get_best_version_single_version),
    ]

    tests_1_6 = [
        # Story 1.6: Library Status
        ('Generate grade bar', test_generate_grade_bar),
        ('Get library status empty DB', test_get_library_status_empty_db),
        ('Get library status uninit DB', test_get_library_status_uninit_db),
        ('Get library status with data', test_get_library_status_with_data),
        ('Get library status grade distribution percentages', test_get_library_status_grade_distribution_percentages),
        ('Get library status ready to release limit', test_get_library_status_ready_to_release_limit),
        ('Get library status needs work limit', test_get_library_status_needs_work_limit),
        ('Get library status grade order', test_get_library_status_grade_order),
    ]

    tests_2_1 = [
        # Story 2.1: Track Changes Between Versions
        ('Changes table schema', test_get_project_changes_schema),
        ('Not enough versions', test_get_project_changes_not_enough_versions),
        ('No changes stored', test_get_project_changes_no_changes_stored),
        ('Fuzzy match', test_get_project_changes_fuzzy_match),
        ('Not found', test_get_project_changes_not_found),
        ('Uninit DB', test_get_project_changes_uninit_db),
        ('Multiple versions', test_get_project_changes_multiple_versions),
        ('From version filter', test_get_project_changes_from_version_filter),
        ('To version filter', test_get_project_changes_to_version_filter),
        ('From and to filter', test_get_project_changes_from_to_filter),
        ('Version not found', test_get_project_changes_version_not_found),
    ]

    tests_2_2 = [
        # Story 2.2: Correlate Changes with Outcomes (Insights)
        ('Confidence level calculation', test_confidence_level),
        ('Uninit DB', test_get_insights_uninit_db),
        ('Empty DB', test_get_insights_empty_db),
        ('Insufficient data', test_get_insights_insufficient_data),
        ('Sufficient data', test_get_insights_with_sufficient_data),
        ('Patterns that help', test_get_insights_patterns_that_help),
        ('Patterns that hurt', test_get_insights_patterns_that_hurt),
        ('Common mistakes', test_get_insights_common_mistakes),
        ('Confidence levels', test_get_insights_confidence_levels),
    ]

    tests_2_4 = [
        # Story 2.4: Style Profile
        ('Uninit DB', test_get_style_profile_uninit_db),
        ('Empty DB', test_get_style_profile_empty_db),
        ('Insufficient Grade A versions', test_get_style_profile_insufficient_grade_a),
        ('Sufficient data', test_get_style_profile_with_sufficient_data),
        ('Calculates averages', test_get_style_profile_calculates_averages),
        ('Save profile to JSON', test_save_profile_to_json),
        ('Load profile from JSON', test_load_profile_from_json),
        ('Load profile not found', test_load_profile_from_json_not_found),
        ('Compare no profile', test_compare_file_against_profile_no_profile),
        ('Compare file not scanned', test_compare_file_against_profile_file_not_scanned),
        ('Compare success', test_compare_file_against_profile_success),
        ('Generates insights', test_style_profile_generates_insights),
    ]

    tests_2_6 = [
        # Story 2.6: Smart Recommendations Engine
        ('Count database versions', test_count_database_versions),
        ('Has sufficient history', test_has_sufficient_history),
        ('Smart diagnose uninit DB', test_smart_diagnose_uninit_db),
        ('Smart diagnose file not in DB', test_smart_diagnose_file_not_in_db),
        ('Smart diagnose with scan result', test_smart_diagnose_with_scan_result),
        ('Smart diagnose prioritizes critical', test_smart_diagnose_prioritizes_critical),
        ('Smart diagnose insufficient history flag', test_smart_diagnose_insufficient_history_flag),
        ('Get pattern history', test_get_pattern_history),
        ('Calculate recommendation priority', test_calculate_recommendation_priority),
        ('Smart diagnose with sufficient history', test_smart_diagnose_with_sufficient_history),
        ('SmartRecommendation dataclass', test_smart_recommendation_dataclass),
        ('SmartDiagnoseResult dataclass', test_smart_diagnose_result_dataclass),
    ]

    no_tmp_tests = [test_grade_calculation, test_trend_calculation,
                    test_fuzzy_match_exact, test_fuzzy_match_substring, test_fuzzy_match_word_start,
                    test_generate_grade_bar, test_confidence_level, test_smart_recommendation_dataclass]

    passed = 0
    failed = 0

    def run_test_suite(tests, title):
        nonlocal passed, failed
        print("=" * 60)
        print(title)
        print("=" * 60)
        print()

        for name, test_func in tests:
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_path = Path(tmp)
                    if test_func in no_tmp_tests:
                        result = test_func()
                    else:
                        result = test_func(tmp_path)

                    if result:
                        print(f"  [PASS] {name}")
                        passed += 1
                    else:
                        print(f"  [FAIL] {name} - returned False")
                        failed += 1
            except AssertionError as e:
                print(f"  [FAIL] {name}")
                print(f"    Assertion failed: {e}")
                failed += 1
            except Exception as e:
                print(f"  [FAIL] {name}")
                print(f"    Error: {e}")
                failed += 1

        print()

    run_test_suite(tests_1_2, "Database Persistence Tests (Story 1.2)")
    run_test_suite(tests_1_3, "List Projects Tests (Story 1.3)")
    run_test_suite(tests_1_4, "Project History Tests (Story 1.4)")
    run_test_suite(tests_1_5, "Best Version Tests (Story 1.5)")
    run_test_suite(tests_1_6, "Library Status Tests (Story 1.6)")
    run_test_suite(tests_2_1, "Track Changes Tests (Story 2.1)")
    run_test_suite(tests_2_2, "Insights Tests (Story 2.2)")
    run_test_suite(tests_2_4, "Style Profile Tests (Story 2.4)")
    run_test_suite(tests_2_6, "Smart Recommendations Tests (Story 2.6)")
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
