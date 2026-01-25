"""
Tests for HTML Report Generation (Story 4.2)

Tests the generation of self-contained HTML reports for:
- Single project diagnosis
- Project version history
- Full library overview
"""

import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


def test_jinja2_available():
    """Test that jinja2 is available."""
    from html_reports import JINJA2_AVAILABLE
    assert JINJA2_AVAILABLE, "jinja2 should be available"
    print("  ✓ jinja2 is available")


def test_grade_color_function():
    """Test _get_grade_color returns correct colors."""
    from html_reports import _get_grade_color

    assert _get_grade_color('A') == '#22c55e'  # green
    assert _get_grade_color('B') == '#06b6d4'  # cyan
    assert _get_grade_color('C') == '#eab308'  # yellow
    assert _get_grade_color('D') == '#f97316'  # orange
    assert _get_grade_color('F') == '#ef4444'  # red
    assert _get_grade_color('X') == '#9ca3af'  # default gray
    print("  ✓ Grade colors are correct")


def test_severity_color_function():
    """Test _get_severity_color returns correct colors."""
    from html_reports import _get_severity_color

    assert _get_severity_color('critical') == '#ef4444'
    assert _get_severity_color('Critical') == '#ef4444'  # case insensitive
    assert _get_severity_color('warning') == '#eab308'
    assert _get_severity_color('suggestion') == '#06b6d4'
    assert _get_severity_color('unknown') == '#9ca3af'
    print("  ✓ Severity colors are correct")


def test_severity_icon_function():
    """Test _get_severity_icon returns correct icons."""
    from html_reports import _get_severity_icon

    assert _get_severity_icon('critical') == '⛔'
    assert _get_severity_icon('warning') == '⚠️'
    assert _get_severity_icon('suggestion') == '💡'
    assert _get_severity_icon('unknown') == '•'
    print("  ✓ Severity icons are correct")


def test_report_issue_dataclass():
    """Test ReportIssue dataclass creation."""
    from html_reports import ReportIssue

    issue = ReportIssue(
        track_name="Bass",
        severity="critical",
        category="devices",
        description="Too many EQs",
        fix_suggestion="Remove one EQ"
    )

    assert issue.track_name == "Bass"
    assert issue.severity == "critical"
    assert issue.category == "devices"
    assert issue.description == "Too many EQs"
    assert issue.fix_suggestion == "Remove one EQ"
    print("  ✓ ReportIssue dataclass works")


def test_report_version_dataclass():
    """Test ReportVersion dataclass creation."""
    from html_reports import ReportVersion

    version = ReportVersion(
        id=1,
        filename="song_v1.als",
        path="/path/to/song_v1.als",
        health_score=85,
        grade="A",
        total_issues=5,
        critical_issues=1,
        warning_issues=4,
        scanned_at=datetime(2026, 1, 25, 12, 0, 0),
        delta=10,
        is_best=True,
        is_current=False
    )

    assert version.id == 1
    assert version.health_score == 85
    assert version.is_best == True
    assert version.delta == 10
    print("  ✓ ReportVersion dataclass works")


def test_project_report_data_dataclass():
    """Test ProjectReportData dataclass creation."""
    from html_reports import ProjectReportData, ReportIssue

    issues = [
        ReportIssue("Track 1", "warning", "devices", "Issue 1", "Fix 1")
    ]

    data = ProjectReportData(
        song_name="My Song",
        folder_path="/path/to/song",
        als_filename="song.als",
        als_path="/path/to/song/song.als",
        health_score=75,
        grade="B",
        total_issues=3,
        critical_issues=1,
        warning_issues=2,
        total_devices=50,
        disabled_devices=5,
        clutter_percentage=10.5,
        scanned_at=datetime.now(),
        issues=issues
    )

    assert data.song_name == "My Song"
    assert data.health_score == 75
    assert len(data.issues) == 1
    print("  ✓ ProjectReportData dataclass works")


def test_history_report_data_dataclass():
    """Test HistoryReportData dataclass creation."""
    from html_reports import HistoryReportData, ReportVersion

    versions = [
        ReportVersion(
            id=1, filename="v1.als", path="/path/v1.als",
            health_score=60, grade="B", total_issues=5,
            critical_issues=1, warning_issues=4,
            scanned_at=datetime.now(), delta=None, is_best=False, is_current=False
        ),
        ReportVersion(
            id=2, filename="v2.als", path="/path/v2.als",
            health_score=85, grade="A", total_issues=2,
            critical_issues=0, warning_issues=2,
            scanned_at=datetime.now(), delta=25, is_best=True, is_current=True
        )
    ]

    data = HistoryReportData(
        song_name="Test Song",
        folder_path="/path/to/song",
        versions=versions,
        best_version=versions[1],
        current_version=versions[1]
    )

    assert data.song_name == "Test Song"
    assert len(data.versions) == 2
    assert data.best_version.health_score == 85
    print("  ✓ HistoryReportData dataclass works")


def test_library_report_data_dataclass():
    """Test LibraryReportData dataclass creation."""
    from html_reports import LibraryReportData, GradeData

    grade_dist = [
        GradeData(grade="A", count=5, percentage=25.0),
        GradeData(grade="B", count=10, percentage=50.0),
        GradeData(grade="C", count=5, percentage=25.0),
    ]

    data = LibraryReportData(
        total_projects=10,
        total_versions=20,
        total_issues=100,
        last_scan_date=datetime.now(),
        grade_distribution=grade_dist,
        ready_to_release=[("song1.als", 95, "Song 1")],
        needs_work=[("song2.als", 30, "Song 2")],
        projects=[{"song_name": "Song 1", "version_count": 3}]
    )

    assert data.total_projects == 10
    assert len(data.grade_distribution) == 3
    assert len(data.ready_to_release) == 1
    print("  ✓ LibraryReportData dataclass works")


def test_generate_project_report_returns_html():
    """Test that generate_project_report returns valid HTML."""
    from html_reports import generate_project_report, ProjectReportData, ReportIssue

    data = ProjectReportData(
        song_name="Test Song",
        folder_path="/test/path",
        als_filename="test.als",
        als_path="/test/path/test.als",
        health_score=85,
        grade="A",
        total_issues=2,
        critical_issues=0,
        warning_issues=2,
        total_devices=30,
        disabled_devices=3,
        clutter_percentage=8.5,
        scanned_at=datetime.now(),
        issues=[
            ReportIssue("Track 1", "warning", "devices", "Issue 1", "Fix 1"),
            ReportIssue("Track 2", "warning", "clutter", "Issue 2", None)
        ]
    )

    html, saved_path = generate_project_report(data)

    assert html is not None
    assert len(html) > 0
    assert "<!DOCTYPE html>" in html
    assert "Test Song" in html
    assert "85" in html  # health score
    assert "Issue 1" in html
    assert saved_path is None  # no output path provided
    print("  ✓ Project report generates valid HTML")


def test_generate_project_report_saves_file():
    """Test that generate_project_report can save to file."""
    from html_reports import generate_project_report, ProjectReportData

    data = ProjectReportData(
        song_name="Test Song",
        folder_path="/test/path",
        als_filename="test.als",
        als_path="/test/path/test.als",
        health_score=75,
        grade="B",
        total_issues=0,
        critical_issues=0,
        warning_issues=0,
        total_devices=20,
        disabled_devices=2,
        clutter_percentage=5.0,
        scanned_at=datetime.now(),
        issues=[]
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_report.html"
        html, saved_path = generate_project_report(data, output_path)

        assert saved_path is not None
        assert saved_path.exists()
        assert saved_path.read_text().startswith("<!DOCTYPE html>")
    print("  ✓ Project report saves to file")


def test_generate_history_report_returns_html():
    """Test that generate_history_report returns valid HTML."""
    from html_reports import generate_history_report, HistoryReportData, ReportVersion

    versions = [
        ReportVersion(
            id=1, filename="v1.als", path="/path/v1.als",
            health_score=60, grade="B", total_issues=5,
            critical_issues=1, warning_issues=4,
            scanned_at=datetime(2026, 1, 20), delta=None, is_best=False, is_current=False
        ),
        ReportVersion(
            id=2, filename="v2.als", path="/path/v2.als",
            health_score=85, grade="A", total_issues=2,
            critical_issues=0, warning_issues=2,
            scanned_at=datetime(2026, 1, 25), delta=25, is_best=True, is_current=True
        )
    ]

    data = HistoryReportData(
        song_name="History Test",
        folder_path="/test/folder",
        versions=versions,
        best_version=versions[1],
        current_version=versions[1]
    )

    html, saved_path = generate_history_report(data)

    assert html is not None
    assert "<!DOCTYPE html>" in html
    assert "History Test" in html
    assert "v1.als" in html
    assert "v2.als" in html
    assert "+25" in html  # delta
    assert saved_path is None
    print("  ✓ History report generates valid HTML")


def test_generate_history_report_saves_file():
    """Test that generate_history_report can save to file."""
    from html_reports import generate_history_report, HistoryReportData, ReportVersion

    data = HistoryReportData(
        song_name="Save Test",
        folder_path="/test",
        versions=[
            ReportVersion(
                id=1, filename="v1.als", path="/test/v1.als",
                health_score=70, grade="B", total_issues=3,
                critical_issues=0, warning_issues=3,
                scanned_at=datetime.now(), delta=None, is_best=True, is_current=True
            )
        ],
        best_version=None,
        current_version=None
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "history.html"
        html, saved_path = generate_history_report(data, output_path)

        assert saved_path is not None
        assert saved_path.exists()
    print("  ✓ History report saves to file")


def test_generate_library_report_returns_html():
    """Test that generate_library_report returns valid HTML."""
    from html_reports import generate_library_report, LibraryReportData, GradeData

    data = LibraryReportData(
        total_projects=5,
        total_versions=15,
        total_issues=50,
        last_scan_date=datetime(2026, 1, 25),
        grade_distribution=[
            GradeData(grade="A", count=3, percentage=20.0),
            GradeData(grade="B", count=5, percentage=33.3),
            GradeData(grade="C", count=4, percentage=26.7),
            GradeData(grade="D", count=2, percentage=13.3),
            GradeData(grade="F", count=1, percentage=6.7),
        ],
        ready_to_release=[
            ("best_song.als", 95, "Best Song"),
            ("good_song.als", 88, "Good Song")
        ],
        needs_work=[
            ("bad_song.als", 25, "Bad Song")
        ],
        projects=[
            {"song_name": "Best Song", "version_count": 5, "best_score": 95, "best_grade": "A",
             "latest_score": 95, "latest_grade": "A", "trend": "stable"},
            {"song_name": "Bad Song", "version_count": 2, "best_score": 35, "best_grade": "D",
             "latest_score": 25, "latest_grade": "D", "trend": "down"}
        ]
    )

    html, saved_path = generate_library_report(data)

    assert html is not None
    assert "<!DOCTYPE html>" in html
    assert "Library Status" in html
    assert "5" in html  # total projects
    assert "Best Song" in html
    assert "Bad Song" in html
    assert saved_path is None
    print("  ✓ Library report generates valid HTML")


def test_generate_library_report_saves_file():
    """Test that generate_library_report can save to file."""
    from html_reports import generate_library_report, LibraryReportData, GradeData

    data = LibraryReportData(
        total_projects=1,
        total_versions=2,
        total_issues=5,
        last_scan_date=datetime.now(),
        grade_distribution=[GradeData("B", 2, 100.0)],
        ready_to_release=[],
        needs_work=[],
        projects=[]
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "library.html"
        html, saved_path = generate_library_report(data, output_path)

        assert saved_path is not None
        assert saved_path.exists()
    print("  ✓ Library report saves to file")


def test_get_default_report_path_library():
    """Test default path for library reports."""
    from html_reports import get_default_report_path

    path = get_default_report_path('library')

    assert path is not None
    assert 'library_report_' in str(path)
    assert '.html' in str(path)
    assert 'reports' in str(path)
    print("  ✓ Default library report path is correct")


def test_get_default_report_path_project():
    """Test default path for project reports."""
    from html_reports import get_default_report_path

    path = get_default_report_path('project', 'My Test Song')

    assert path is not None
    assert 'My_Test_Song' in str(path)  # sanitized name
    assert 'project_' in str(path)
    assert '.html' in str(path)
    print("  ✓ Default project report path is correct")


def test_get_default_report_path_history():
    """Test default path for history reports."""
    from html_reports import get_default_report_path

    path = get_default_report_path('history', 'Test Song 123')

    assert path is not None
    assert 'Test_Song_123' in str(path)
    assert 'history_' in str(path)
    assert '.html' in str(path)
    print("  ✓ Default history report path is correct")


def test_report_includes_css():
    """Test that generated reports include inline CSS."""
    from html_reports import generate_project_report, ProjectReportData

    data = ProjectReportData(
        song_name="CSS Test",
        folder_path="/test",
        als_filename="test.als",
        als_path="/test/test.als",
        health_score=80,
        grade="A",
        total_issues=0,
        critical_issues=0,
        warning_issues=0,
        total_devices=10,
        disabled_devices=0,
        clutter_percentage=0.0,
        scanned_at=datetime.now(),
        issues=[]
    )

    html, _ = generate_project_report(data)

    # Check that CSS is inline in <style> tag
    assert "<style>" in html
    assert "--bg-primary:" in html  # CSS variable
    assert ".card {" in html or ".card{" in html
    print("  ✓ Report includes inline CSS")


def test_report_is_self_contained():
    """Test that reports don't have external dependencies."""
    from html_reports import generate_library_report, LibraryReportData, GradeData

    data = LibraryReportData(
        total_projects=1,
        total_versions=1,
        total_issues=0,
        last_scan_date=datetime.now(),
        grade_distribution=[GradeData("A", 1, 100.0)],
        ready_to_release=[],
        needs_work=[],
        projects=[]
    )

    html, _ = generate_library_report(data)

    # Should not have external CSS or JS links
    assert 'href="http' not in html.lower()
    assert 'src="http' not in html.lower()
    assert '<link rel="stylesheet"' not in html.lower() or 'href="http' not in html.lower()
    print("  ✓ Report is self-contained (no external dependencies)")


def test_report_has_dark_mode():
    """Test that reports use dark mode styling."""
    from html_reports import generate_project_report, ProjectReportData

    data = ProjectReportData(
        song_name="Dark Mode Test",
        folder_path="/test",
        als_filename="test.als",
        als_path="/test/test.als",
        health_score=70,
        grade="B",
        total_issues=0,
        critical_issues=0,
        warning_issues=0,
        total_devices=10,
        disabled_devices=1,
        clutter_percentage=5.0,
        scanned_at=datetime.now(),
        issues=[]
    )

    html, _ = generate_project_report(data)

    # Check for dark mode colors in CSS
    assert "#0f172a" in html or "0f172a" in html  # bg-primary dark color
    print("  ✓ Report uses dark mode styling")


def test_report_is_mobile_responsive():
    """Test that reports include responsive design."""
    from html_reports import generate_project_report, ProjectReportData

    data = ProjectReportData(
        song_name="Mobile Test",
        folder_path="/test",
        als_filename="test.als",
        als_path="/test/test.als",
        health_score=65,
        grade="B",
        total_issues=0,
        critical_issues=0,
        warning_issues=0,
        total_devices=10,
        disabled_devices=0,
        clutter_percentage=0.0,
        scanned_at=datetime.now(),
        issues=[]
    )

    html, _ = generate_project_report(data)

    # Check for responsive viewport and media queries
    assert 'viewport' in html.lower()
    assert '@media' in html
    print("  ✓ Report is mobile responsive")


def test_report_escapes_html_characters():
    """Test that reports properly escape HTML special characters."""
    from html_reports import generate_project_report, ProjectReportData, ReportIssue

    data = ProjectReportData(
        song_name="Test <script>alert('xss')</script>",
        folder_path="/test",
        als_filename="test.als",
        als_path="/test/test.als",
        health_score=50,
        grade="C",
        total_issues=1,
        critical_issues=0,
        warning_issues=1,
        total_devices=10,
        disabled_devices=0,
        clutter_percentage=0.0,
        scanned_at=datetime.now(),
        issues=[
            ReportIssue(
                track_name="<script>evil</script>",
                severity="warning",
                category="test",
                description="Issue with <html> tags",
                fix_suggestion=None
            )
        ]
    )

    html, _ = generate_project_report(data)

    # Raw script tags should be escaped
    assert "<script>alert" not in html or "&lt;script&gt;alert" in html
    print("  ✓ Report escapes HTML special characters")


def test_create_subdirectory_for_report():
    """Test that generate_project_report creates subdirectory if needed."""
    from html_reports import generate_project_report, ProjectReportData

    data = ProjectReportData(
        song_name="Subdir Test",
        folder_path="/test",
        als_filename="test.als",
        als_path="/test/test.als",
        health_score=80,
        grade="A",
        total_issues=0,
        critical_issues=0,
        warning_issues=0,
        total_devices=10,
        disabled_devices=0,
        clutter_percentage=0.0,
        scanned_at=datetime.now(),
        issues=[]
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "nested" / "dir" / "report.html"
        html, saved_path = generate_project_report(data, output_path)

        assert saved_path is not None
        assert saved_path.exists()
        assert saved_path.parent.name == "dir"
    print("  ✓ Creates subdirectories for report output")


# =============================================================================
# Story 4.3 - Health Timeline Charts Tests
# =============================================================================


def test_chart_data_point_dataclass():
    """Test ChartDataPoint dataclass creation."""
    from html_reports import ChartDataPoint

    point = ChartDataPoint(
        label="v1.als",
        score=85,
        grade="A",
        scanned_at="2026-01-25 12:00",
        delta=10,
        is_best=True,
        is_current=False,
        total_issues=3
    )

    assert point.label == "v1.als"
    assert point.score == 85
    assert point.grade == "A"
    assert point.delta == 10
    assert point.is_best == True
    assert point.is_current == False
    print("  ✓ ChartDataPoint dataclass works")


def test_timeline_chart_data_dataclass():
    """Test TimelineChartData dataclass creation."""
    from html_reports import TimelineChartData

    data = TimelineChartData()
    data.labels.append("v1.als")
    data.scores.append(75)
    data.grades.append("B")
    data.best_index = 0

    assert len(data.labels) == 1
    assert data.scores[0] == 75
    assert data.best_index == 0
    print("  ✓ TimelineChartData dataclass works")


def test_generate_chart_data_empty():
    """Test generate_chart_data with empty list."""
    from html_reports import generate_chart_data

    data = generate_chart_data([])

    assert data.labels == []
    assert data.scores == []
    assert data.best_index is None
    print("  ✓ generate_chart_data handles empty list")


def test_generate_chart_data_single_version():
    """Test generate_chart_data with single version."""
    from html_reports import generate_chart_data, ReportVersion

    versions = [
        ReportVersion(
            id=1, filename="v1.als", path="/path/v1.als",
            health_score=80, grade="A", total_issues=2,
            critical_issues=0, warning_issues=2,
            scanned_at=datetime(2026, 1, 25, 12, 0),
            delta=None, is_best=True, is_current=True
        )
    ]

    data = generate_chart_data(versions)

    assert len(data.labels) == 1
    assert data.labels[0] == "v1.als"
    assert data.scores[0] == 80
    assert data.grades[0] == "A"
    assert data.is_best[0] == True
    assert data.is_current[0] == True
    assert data.best_index == 0
    assert data.current_index == 0
    print("  ✓ generate_chart_data handles single version")


def test_generate_chart_data_multiple_versions():
    """Test generate_chart_data with multiple versions."""
    from html_reports import generate_chart_data, ReportVersion

    versions = [
        ReportVersion(
            id=1, filename="v1.als", path="/path/v1.als",
            health_score=60, grade="B", total_issues=5,
            critical_issues=1, warning_issues=4,
            scanned_at=datetime(2026, 1, 20, 10, 0),
            delta=None, is_best=False, is_current=False
        ),
        ReportVersion(
            id=2, filename="v2.als", path="/path/v2.als",
            health_score=85, grade="A", total_issues=2,
            critical_issues=0, warning_issues=2,
            scanned_at=datetime(2026, 1, 22, 12, 0),
            delta=25, is_best=True, is_current=False
        ),
        ReportVersion(
            id=3, filename="v3.als", path="/path/v3.als",
            health_score=70, grade="B", total_issues=4,
            critical_issues=0, warning_issues=4,
            scanned_at=datetime(2026, 1, 25, 14, 0),
            delta=-15, is_best=False, is_current=True
        )
    ]

    data = generate_chart_data(versions)

    assert len(data.labels) == 3
    assert data.labels == ["v1.als", "v2.als", "v3.als"]
    assert data.scores == [60, 85, 70]
    assert data.grades == ["B", "A", "B"]
    assert data.deltas == [None, 25, -15]
    assert data.issues == [5, 2, 4]
    assert data.best_index == 1
    assert data.current_index == 2
    print("  ✓ generate_chart_data handles multiple versions")


def test_chart_data_to_json():
    """Test chart_data_to_json produces valid JSON."""
    import json
    from html_reports import chart_data_to_json, TimelineChartData

    data = TimelineChartData(
        labels=["v1.als", "v2.als"],
        scores=[60, 85],
        grades=["B", "A"],
        dates=["2026-01-20", "2026-01-25"],
        deltas=[None, 25],
        is_best=[False, True],
        is_current=[False, True],
        issues=[5, 2],
        best_index=1,
        current_index=1
    )

    json_str = chart_data_to_json(data)
    parsed = json.loads(json_str)

    assert parsed['labels'] == ["v1.als", "v2.als"]
    assert parsed['scores'] == [60, 85]
    assert parsed['grades'] == ["B", "A"]
    assert parsed['isBest'] == [False, True]  # camelCase in JSON
    assert parsed['isCurrent'] == [False, True]
    assert parsed['bestIndex'] == 1
    assert parsed['currentIndex'] == 1
    print("  ✓ chart_data_to_json produces valid JSON")


def test_chart_css_exists():
    """Test that CHART_CSS constant is defined."""
    from html_reports import CHART_CSS

    assert CHART_CSS is not None
    assert len(CHART_CSS) > 0
    assert ".chart-container" in CHART_CSS
    assert "#resetZoom" in CHART_CSS
    print("  ✓ CHART_CSS constant exists")


def test_chartjs_cdn_exists():
    """Test that CHARTJS_CDN constant is defined."""
    from html_reports import CHARTJS_CDN

    assert CHARTJS_CDN is not None
    assert "chart.js" in CHARTJS_CDN
    assert "chartjs-plugin-zoom" in CHARTJS_CDN
    print("  ✓ CHARTJS_CDN constant exists")


def test_chartjs_fallback_exists():
    """Test that CHARTJS_FALLBACK constant is defined."""
    from html_reports import CHARTJS_FALLBACK

    assert CHARTJS_FALLBACK is not None
    assert "ChartFallback" in CHARTJS_FALLBACK
    print("  ✓ CHARTJS_FALLBACK constant exists")


def test_timeline_chart_js_exists():
    """Test that TIMELINE_CHART_JS constant is defined."""
    from html_reports import TIMELINE_CHART_JS

    assert TIMELINE_CHART_JS is not None
    assert "window.timelineData" in TIMELINE_CHART_JS
    assert "healthTimeline" in TIMELINE_CHART_JS
    assert "gradeZones" in TIMELINE_CHART_JS
    print("  ✓ TIMELINE_CHART_JS constant exists")


def test_history_report_includes_chart():
    """Test that history report includes chart elements."""
    from html_reports import generate_history_report, HistoryReportData, ReportVersion

    versions = [
        ReportVersion(
            id=1, filename="v1.als", path="/path/v1.als",
            health_score=60, grade="B", total_issues=5,
            critical_issues=1, warning_issues=4,
            scanned_at=datetime(2026, 1, 20), delta=None, is_best=False, is_current=False
        ),
        ReportVersion(
            id=2, filename="v2.als", path="/path/v2.als",
            health_score=85, grade="A", total_issues=2,
            critical_issues=0, warning_issues=2,
            scanned_at=datetime(2026, 1, 25), delta=25, is_best=True, is_current=True
        )
    ]

    data = HistoryReportData(
        song_name="Chart Test",
        folder_path="/test/folder",
        versions=versions,
        best_version=versions[1],
        current_version=versions[1]
    )

    html, _ = generate_history_report(data)

    # Should include chart canvas
    assert 'id="healthTimeline"' in html
    # Should include chart CSS
    assert ".chart-container" in html
    # Should include chart data
    assert "window.timelineData" in html
    # Should include Chart.js
    assert "chart.js" in html.lower()
    print("  ✓ History report includes chart elements")


def test_history_report_chart_data_correct():
    """Test that history report includes correct chart data."""
    import json
    import re
    from html_reports import generate_history_report, HistoryReportData, ReportVersion

    versions = [
        ReportVersion(
            id=1, filename="song_v1.als", path="/path/song_v1.als",
            health_score=55, grade="C", total_issues=8,
            critical_issues=2, warning_issues=6,
            scanned_at=datetime(2026, 1, 20), delta=None, is_best=False, is_current=False
        ),
        ReportVersion(
            id=2, filename="song_v2.als", path="/path/song_v2.als",
            health_score=90, grade="A", total_issues=1,
            critical_issues=0, warning_issues=1,
            scanned_at=datetime(2026, 1, 25), delta=35, is_best=True, is_current=True
        )
    ]

    data = HistoryReportData(
        song_name="Data Test",
        folder_path="/test/folder",
        versions=versions,
        best_version=versions[1],
        current_version=versions[1]
    )

    html, _ = generate_history_report(data)

    # Extract JSON data from HTML
    match = re.search(r'window\.timelineData = ({[^;]+});', html)
    assert match is not None, "Chart data not found in HTML"

    chart_data = json.loads(match.group(1))
    assert chart_data['labels'] == ["song_v1.als", "song_v2.als"]
    assert chart_data['scores'] == [55, 90]
    assert chart_data['grades'] == ["C", "A"]
    assert chart_data['bestIndex'] == 1
    print("  ✓ History report includes correct chart data")


def test_history_report_shows_regressions():
    """Test that history report shows regression warnings."""
    from html_reports import generate_history_report, HistoryReportData, ReportVersion

    versions = [
        ReportVersion(
            id=1, filename="v1.als", path="/path/v1.als",
            health_score=85, grade="A", total_issues=2,
            critical_issues=0, warning_issues=2,
            scanned_at=datetime(2026, 1, 20), delta=None, is_best=True, is_current=False
        ),
        ReportVersion(
            id=2, filename="v2.als", path="/path/v2.als",
            health_score=50, grade="C", total_issues=8,
            critical_issues=2, warning_issues=6,
            scanned_at=datetime(2026, 1, 25), delta=-35, is_best=False, is_current=True
        )
    ]

    data = HistoryReportData(
        song_name="Regression Test",
        folder_path="/test/folder",
        versions=versions,
        best_version=versions[0],
        current_version=versions[1]
    )

    html, _ = generate_history_report(data)

    # Should include regression note
    assert "regression" in html.lower()
    assert "regressionList" in html
    print("  ✓ History report shows regressions")


def test_history_report_hides_chart_for_single_version():
    """Test that chart is hidden when only one version exists."""
    from html_reports import generate_history_report, HistoryReportData, ReportVersion

    versions = [
        ReportVersion(
            id=1, filename="v1.als", path="/path/v1.als",
            health_score=75, grade="B", total_issues=3,
            critical_issues=0, warning_issues=3,
            scanned_at=datetime(2026, 1, 25), delta=None, is_best=True, is_current=True
        )
    ]

    data = HistoryReportData(
        song_name="Single Version",
        folder_path="/test/folder",
        versions=versions,
        best_version=versions[0],
        current_version=versions[0]
    )

    html, _ = generate_history_report(data)

    # Chart card should not appear for single version
    # The template has: {% if data.versions|length > 1 %}
    assert "Health Timeline" not in html
    print("  ✓ Chart hidden for single version")


def test_history_report_includes_grade_zones_legend():
    """Test that history report includes grade zone legend."""
    from html_reports import generate_history_report, HistoryReportData, ReportVersion

    versions = [
        ReportVersion(
            id=1, filename="v1.als", path="/path/v1.als",
            health_score=60, grade="B", total_issues=5,
            critical_issues=0, warning_issues=5,
            scanned_at=datetime(2026, 1, 20), delta=None, is_best=False, is_current=False
        ),
        ReportVersion(
            id=2, filename="v2.als", path="/path/v2.als",
            health_score=85, grade="A", total_issues=2,
            critical_issues=0, warning_issues=2,
            scanned_at=datetime(2026, 1, 25), delta=25, is_best=True, is_current=True
        )
    ]

    data = HistoryReportData(
        song_name="Grade Zones Test",
        folder_path="/test/folder",
        versions=versions,
        best_version=versions[1],
        current_version=versions[1]
    )

    html, _ = generate_history_report(data)

    # Should include grade zone legend
    assert "grade-zone-legend" in html
    assert "A (80-100)" in html
    assert "B (60-79)" in html
    assert "F (0-19)" in html
    print("  ✓ History report includes grade zone legend")


def test_history_report_includes_reset_zoom():
    """Test that history report includes reset zoom button."""
    from html_reports import generate_history_report, HistoryReportData, ReportVersion

    versions = [
        ReportVersion(
            id=1, filename="v1.als", path="/path/v1.als",
            health_score=70, grade="B", total_issues=4,
            critical_issues=0, warning_issues=4,
            scanned_at=datetime(2026, 1, 20), delta=None, is_best=False, is_current=False
        ),
        ReportVersion(
            id=2, filename="v2.als", path="/path/v2.als",
            health_score=80, grade="A", total_issues=2,
            critical_issues=0, warning_issues=2,
            scanned_at=datetime(2026, 1, 25), delta=10, is_best=True, is_current=True
        )
    ]

    data = HistoryReportData(
        song_name="Zoom Test",
        folder_path="/test/folder",
        versions=versions,
        best_version=versions[1],
        current_version=versions[1]
    )

    html, _ = generate_history_report(data)

    assert 'id="resetZoom"' in html
    assert "Reset Zoom" in html
    print("  ✓ History report includes reset zoom button")


def test_history_report_includes_legend_markers():
    """Test that history report includes chart legend markers."""
    from html_reports import generate_history_report, HistoryReportData, ReportVersion

    versions = [
        ReportVersion(
            id=1, filename="v1.als", path="/path/v1.als",
            health_score=65, grade="B", total_issues=4,
            critical_issues=0, warning_issues=4,
            scanned_at=datetime(2026, 1, 20), delta=None, is_best=False, is_current=False
        ),
        ReportVersion(
            id=2, filename="v2.als", path="/path/v2.als",
            health_score=90, grade="A", total_issues=1,
            critical_issues=0, warning_issues=1,
            scanned_at=datetime(2026, 1, 25), delta=25, is_best=True, is_current=True
        )
    ]

    data = HistoryReportData(
        song_name="Legend Test",
        folder_path="/test/folder",
        versions=versions,
        best_version=versions[1],
        current_version=versions[1]
    )

    html, _ = generate_history_report(data)

    assert "chart-legend" in html
    assert "Best Version" in html
    assert "Current" in html
    print("  ✓ History report includes legend markers")


def run_all_tests():
    """Run all HTML report tests."""
    print("")
    print("=" * 60)
    print("HTML Report Tests (Story 4.2 + 4.3)")
    print("=" * 60)
    print("")

    tests = [
        # Story 4.2 - HTML Report Generation
        test_jinja2_available,
        test_grade_color_function,
        test_severity_color_function,
        test_severity_icon_function,
        test_report_issue_dataclass,
        test_report_version_dataclass,
        test_project_report_data_dataclass,
        test_history_report_data_dataclass,
        test_library_report_data_dataclass,
        test_generate_project_report_returns_html,
        test_generate_project_report_saves_file,
        test_generate_history_report_returns_html,
        test_generate_history_report_saves_file,
        test_generate_library_report_returns_html,
        test_generate_library_report_saves_file,
        test_get_default_report_path_library,
        test_get_default_report_path_project,
        test_get_default_report_path_history,
        test_report_includes_css,
        test_report_is_self_contained,
        test_report_has_dark_mode,
        test_report_is_mobile_responsive,
        test_report_escapes_html_characters,
        test_create_subdirectory_for_report,
        # Story 4.3 - Health Timeline Charts
        test_chart_data_point_dataclass,
        test_timeline_chart_data_dataclass,
        test_generate_chart_data_empty,
        test_generate_chart_data_single_version,
        test_generate_chart_data_multiple_versions,
        test_chart_data_to_json,
        test_chart_css_exists,
        test_chartjs_cdn_exists,
        test_chartjs_fallback_exists,
        test_timeline_chart_js_exists,
        test_history_report_includes_chart,
        test_history_report_chart_data_correct,
        test_history_report_shows_regressions,
        test_history_report_hides_chart_for_single_version,
        test_history_report_includes_grade_zones_legend,
        test_history_report_includes_reset_zoom,
        test_history_report_includes_legend_markers,
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
