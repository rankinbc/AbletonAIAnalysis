"""
Tests for the Local Web Dashboard (Story 4.4)

Tests cover:
- Flask availability check
- Dashboard config dataclass
- Data classes (ProjectListItem, VersionDetail, etc.)
- Dashboard data fetching functions
- Flask app creation and routes
- Template rendering
- Auto-refresh functionality
"""

import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Test counter for tracking
_test_results = {'passed': 0, 'failed': 0}


def test(name: str):
    """Decorator to register and run a test."""
    def decorator(func):
        def wrapper():
            try:
                func()
                _test_results['passed'] += 1
                print(f"  \u2713 {name}")
                return True
            except AssertionError as e:
                _test_results['failed'] += 1
                print(f"  X {name}: {e}")
                return False
            except Exception as e:
                _test_results['failed'] += 1
                print(f"  X {name}: Exception - {e}")
                return False
        wrapper.__name__ = func.__name__
        wrapper._test_name = name
        return wrapper
    return decorator


# ============================================================================
# Flask Availability Tests
# ============================================================================

@test("Flask is available")
def test_flask_available():
    from dashboard import FLASK_AVAILABLE
    assert FLASK_AVAILABLE, "Flask should be importable"


@test("Flask module imports successfully")
def test_flask_import():
    from flask import Flask
    assert Flask is not None


# ============================================================================
# DashboardConfig Tests
# ============================================================================

@test("DashboardConfig has default values")
def test_dashboard_config_defaults():
    from dashboard import DashboardConfig

    config = DashboardConfig()
    assert config.port == 5000
    assert config.host == '127.0.0.1'
    assert config.debug is False
    assert config.auto_open is True
    assert config.auto_refresh is True
    assert config.refresh_interval == 30


@test("DashboardConfig accepts custom values")
def test_dashboard_config_custom():
    from dashboard import DashboardConfig

    config = DashboardConfig(
        port=8080,
        host='0.0.0.0',
        debug=True,
        auto_open=False,
        auto_refresh=False,
        refresh_interval=60
    )
    assert config.port == 8080
    assert config.host == '0.0.0.0'
    assert config.debug is True
    assert config.auto_open is False
    assert config.auto_refresh is False
    assert config.refresh_interval == 60


# ============================================================================
# Data Class Tests
# ============================================================================

@test("ProjectListItem dataclass works")
def test_project_list_item():
    from dashboard import ProjectListItem

    item = ProjectListItem(
        id=1,
        song_name="Test Song",
        folder_path="/path/to/song",
        version_count=5,
        best_score=85,
        best_grade="A",
        latest_score=80,
        latest_grade="A",
        trend="up",
        last_scanned="2026-01-25"
    )

    assert item.id == 1
    assert item.song_name == "Test Song"
    assert item.version_count == 5
    assert item.best_score == 85


@test("ProjectListItem to_dict works")
def test_project_list_item_to_dict():
    from dashboard import ProjectListItem

    item = ProjectListItem(
        id=1,
        song_name="Test",
        folder_path="/path",
        version_count=3,
        best_score=70,
        best_grade="B",
        latest_score=65,
        latest_grade="C",
        trend="down",
        last_scanned="2026-01-25"
    )

    d = item.to_dict()
    assert isinstance(d, dict)
    assert d['id'] == 1
    assert d['song_name'] == "Test"
    assert d['trend'] == "down"


@test("VersionDetail dataclass works")
def test_version_detail():
    from dashboard import VersionDetail

    version = VersionDetail(
        id=1,
        filename="song_v1.als",
        path="/path/to/song_v1.als",
        health_score=75,
        grade="B",
        total_issues=5,
        critical_issues=1,
        warning_issues=3,
        scanned_at="2026-01-25",
        delta=5,
        is_best=True,
        is_current=False
    )

    assert version.id == 1
    assert version.health_score == 75
    assert version.is_best is True
    assert version.delta == 5


@test("VersionDetail to_dict works")
def test_version_detail_to_dict():
    from dashboard import VersionDetail

    version = VersionDetail(
        id=1,
        filename="test.als",
        path="/path",
        health_score=80,
        grade="A",
        total_issues=2,
        critical_issues=0,
        warning_issues=1,
        scanned_at="2026-01-25"
    )

    d = version.to_dict()
    assert isinstance(d, dict)
    assert d['health_score'] == 80
    assert d['grade'] == "A"


@test("IssueDetail dataclass works")
def test_issue_detail():
    from dashboard import IssueDetail

    issue = IssueDetail(
        id=1,
        track_name="Kick",
        severity="critical",
        category="effect_chain",
        description="Multiple limiters detected",
        fix_suggestion="Remove one limiter"
    )

    assert issue.track_name == "Kick"
    assert issue.severity == "critical"
    assert issue.fix_suggestion == "Remove one limiter"


@test("ProjectDetail dataclass works")
def test_project_detail():
    from dashboard import ProjectDetail, VersionDetail, IssueDetail

    project = ProjectDetail(
        id=1,
        song_name="Test Song",
        folder_path="/path"
    )

    version = VersionDetail(
        id=1, filename="v1.als", path="/path/v1.als",
        health_score=75, grade="B", total_issues=3,
        critical_issues=1, warning_issues=2, scanned_at="2026-01-25"
    )

    issue = IssueDetail(
        id=1, track_name="Bass", severity="warning",
        category="test", description="Test issue"
    )

    project.versions = [version]
    project.issues = [issue]
    project.best_version = version
    project.current_version = version

    d = project.to_dict()
    assert d['song_name'] == "Test Song"
    assert len(d['versions']) == 1
    assert len(d['issues']) == 1
    assert d['best_version']['health_score'] == 75


@test("DashboardHome dataclass works")
def test_dashboard_home():
    from dashboard import DashboardHome

    home = DashboardHome(
        total_projects=10,
        total_versions=50,
        total_issues=100,
        last_scan_date="2026-01-25",
        grade_distribution={'A': 5, 'B': 10, 'C': 15},
        ready_to_release=[('song_v1.als', 90, 'Song')],
        needs_attention=[('bad_v1.als', 30, 'Bad Song')]
    )

    assert home.total_projects == 10
    assert home.total_versions == 50
    assert home.grade_distribution['A'] == 5


@test("DashboardHome to_dict works")
def test_dashboard_home_to_dict():
    from dashboard import DashboardHome

    home = DashboardHome(
        total_projects=5,
        ready_to_release=[('a.als', 95, 'A')],
        needs_attention=[('b.als', 20, 'B')]
    )

    d = home.to_dict()
    assert d['total_projects'] == 5
    assert len(d['ready_to_release']) == 1
    assert d['ready_to_release'][0]['filename'] == 'a.als'
    assert d['ready_to_release'][0]['score'] == 95


@test("InsightItem dataclass works")
def test_insight_item():
    from dashboard import InsightItem

    insight = InsightItem(
        pattern_type="device_removed",
        description="Removing EQ8",
        avg_impact=5.2,
        occurrences=15,
        confidence="HIGH",
        is_helpful=True
    )

    assert insight.pattern_type == "device_removed"
    assert insight.avg_impact == 5.2
    assert insight.is_helpful is True


# ============================================================================
# Flask App Tests
# ============================================================================

@test("create_dashboard_app returns Flask app")
def test_create_app():
    from dashboard import create_dashboard_app, DashboardConfig

    config = DashboardConfig()
    app = create_dashboard_app(config)

    assert app is not None
    assert hasattr(app, 'run')


@test("Dashboard app has required routes")
def test_app_routes():
    from dashboard import create_dashboard_app, DashboardConfig

    config = DashboardConfig()
    app = create_dashboard_app(config)

    # Get registered routes
    routes = [rule.rule for rule in app.url_map.iter_rules()]

    assert '/' in routes
    assert '/projects' in routes
    assert '/project/<int:project_id>' in routes
    assert '/insights' in routes
    assert '/settings' in routes
    assert '/api/home' in routes
    assert '/api/projects' in routes


@test("Dashboard config is stored in app")
def test_app_config():
    from dashboard import create_dashboard_app, DashboardConfig

    config = DashboardConfig(port=8080, auto_refresh=False)
    app = create_dashboard_app(config)

    assert app.config['dashboard_config'].port == 8080
    assert app.config['dashboard_config'].auto_refresh is False


# ============================================================================
# Template Tests
# ============================================================================

@test("DASHBOARD_CSS is defined")
def test_dashboard_css():
    from dashboard import DASHBOARD_CSS

    assert DASHBOARD_CSS is not None
    assert len(DASHBOARD_CSS) > 1000  # Should be substantial CSS
    assert ':root' in DASHBOARD_CSS
    assert '--bg-primary' in DASHBOARD_CSS
    assert 'grade-a' in DASHBOARD_CSS


@test("BASE_TEMPLATE is defined")
def test_base_template():
    from dashboard import BASE_TEMPLATE

    assert BASE_TEMPLATE is not None
    assert '<!DOCTYPE html>' in BASE_TEMPLATE
    assert '{{ title }}' in BASE_TEMPLATE
    assert '{{ content|safe }}' in BASE_TEMPLATE
    assert 'ALS Doctor' in BASE_TEMPLATE


@test("HOME_CONTENT is defined")
def test_home_content():
    from dashboard import HOME_CONTENT

    assert HOME_CONTENT is not None
    assert 'Dashboard' in HOME_CONTENT
    assert 'total_projects' in HOME_CONTENT
    assert 'grade_distribution' in HOME_CONTENT
    assert 'Ready to Release' in HOME_CONTENT
    assert 'Needs Attention' in HOME_CONTENT


@test("PROJECTS_CONTENT is defined")
def test_projects_content():
    from dashboard import PROJECTS_CONTENT

    assert PROJECTS_CONTENT is not None
    assert 'Projects' in PROJECTS_CONTENT
    assert 'searchInput' in PROJECTS_CONTENT
    assert 'sortTable' in PROJECTS_CONTENT
    assert 'filterProjects' in PROJECTS_CONTENT


@test("PROJECT_DETAIL_CONTENT is defined")
def test_project_detail_content():
    from dashboard import PROJECT_DETAIL_CONTENT

    assert PROJECT_DETAIL_CONTENT is not None
    assert 'song_name' in PROJECT_DETAIL_CONTENT
    assert 'Health Timeline' in PROJECT_DETAIL_CONTENT
    assert 'Version History' in PROJECT_DETAIL_CONTENT
    assert 'Current Issues' in PROJECT_DETAIL_CONTENT


@test("PROJECT_CHART_JS is defined")
def test_project_chart_js():
    from dashboard import PROJECT_CHART_JS

    assert PROJECT_CHART_JS is not None
    assert 'chart.js' in PROJECT_CHART_JS.lower()
    assert 'healthChart' in PROJECT_CHART_JS
    assert 'Health Score' in PROJECT_CHART_JS


@test("INSIGHTS_CONTENT is defined")
def test_insights_content():
    from dashboard import INSIGHTS_CONTENT

    assert INSIGHTS_CONTENT is not None
    assert 'Insights' in INSIGHTS_CONTENT
    assert 'Patterns That Help' in INSIGHTS_CONTENT
    assert 'Patterns That Hurt' in INSIGHTS_CONTENT
    assert 'Common Mistakes' in INSIGHTS_CONTENT


@test("SETTINGS_CONTENT is defined")
def test_settings_content():
    from dashboard import SETTINGS_CONTENT

    assert SETTINGS_CONTENT is not None
    assert 'Settings' in SETTINGS_CONTENT
    assert 'Auto-refresh' in SETTINGS_CONTENT
    assert 'Database' in SETTINGS_CONTENT


# ============================================================================
# Auto-refresh Tests
# ============================================================================

@test("get_auto_refresh_meta returns meta tag when enabled")
def test_auto_refresh_meta_enabled():
    from dashboard import get_auto_refresh_meta, DashboardConfig

    config = DashboardConfig(auto_refresh=True, refresh_interval=45)
    meta = get_auto_refresh_meta(config)

    assert meta is not None
    assert 'http-equiv="refresh"' in meta
    assert 'content="45"' in meta


@test("get_auto_refresh_meta returns empty when disabled")
def test_auto_refresh_meta_disabled():
    from dashboard import get_auto_refresh_meta, DashboardConfig

    config = DashboardConfig(auto_refresh=False)
    meta = get_auto_refresh_meta(config)

    assert meta == ''


# ============================================================================
# Data Fetching Tests (with mocked/empty database)
# ============================================================================

@test("get_dashboard_home_data returns DashboardHome")
def test_get_dashboard_home_data():
    from dashboard import get_dashboard_home_data, DashboardHome

    data = get_dashboard_home_data()
    assert isinstance(data, DashboardHome)


@test("get_project_list_data returns list")
def test_get_project_list_data():
    from dashboard import get_project_list_data

    data = get_project_list_data()
    assert isinstance(data, list)


@test("get_project_detail_data returns None for invalid ID")
def test_get_project_detail_data_invalid():
    from dashboard import get_project_detail_data

    data = get_project_detail_data(99999)
    # Should return None for non-existent project
    assert data is None


@test("get_insights_data returns dict with expected keys")
def test_get_insights_data():
    from dashboard import get_insights_data

    data = get_insights_data()
    assert isinstance(data, dict)
    assert 'has_sufficient_data' in data
    assert 'helpful_patterns' in data
    assert 'harmful_patterns' in data
    assert 'common_mistakes' in data


@test("get_database_info returns dict with expected keys")
def test_get_database_info():
    from dashboard import get_database_info

    info = get_database_info()
    assert isinstance(info, dict)
    assert 'path' in info
    assert 'total_projects' in info
    assert 'total_versions' in info


# ============================================================================
# Flask Route Tests (using test client)
# ============================================================================

@test("Home route returns 200")
def test_home_route():
    from dashboard import create_dashboard_app, DashboardConfig

    app = create_dashboard_app(DashboardConfig())
    with app.test_client() as client:
        response = client.get('/')
        assert response.status_code == 200


@test("Home route returns HTML")
def test_home_route_html():
    from dashboard import create_dashboard_app, DashboardConfig

    app = create_dashboard_app(DashboardConfig())
    with app.test_client() as client:
        response = client.get('/')
        assert b'<!DOCTYPE html>' in response.data
        assert b'ALS Doctor' in response.data


@test("Projects route returns 200")
def test_projects_route():
    from dashboard import create_dashboard_app, DashboardConfig

    app = create_dashboard_app(DashboardConfig())
    with app.test_client() as client:
        response = client.get('/projects')
        assert response.status_code == 200


@test("Insights route returns 200")
def test_insights_route():
    from dashboard import create_dashboard_app, DashboardConfig

    app = create_dashboard_app(DashboardConfig())
    with app.test_client() as client:
        response = client.get('/insights')
        assert response.status_code == 200


@test("Settings route returns 200")
def test_settings_route():
    from dashboard import create_dashboard_app, DashboardConfig

    app = create_dashboard_app(DashboardConfig())
    with app.test_client() as client:
        response = client.get('/settings')
        assert response.status_code == 200


@test("Project detail route returns 404 for invalid ID")
def test_project_detail_404():
    from dashboard import create_dashboard_app, DashboardConfig

    app = create_dashboard_app(DashboardConfig())
    with app.test_client() as client:
        response = client.get('/project/99999')
        assert response.status_code == 404


@test("API home route returns JSON")
def test_api_home():
    from dashboard import create_dashboard_app, DashboardConfig

    app = create_dashboard_app(DashboardConfig())
    with app.test_client() as client:
        response = client.get('/api/home')
        assert response.status_code == 200
        assert response.content_type == 'application/json'

        data = response.get_json()
        assert 'total_projects' in data


@test("API projects route returns JSON list")
def test_api_projects():
    from dashboard import create_dashboard_app, DashboardConfig

    app = create_dashboard_app(DashboardConfig())
    with app.test_client() as client:
        response = client.get('/api/projects')
        assert response.status_code == 200

        data = response.get_json()
        assert isinstance(data, list)


@test("API project route returns 404 for invalid ID")
def test_api_project_404():
    from dashboard import create_dashboard_app, DashboardConfig

    app = create_dashboard_app(DashboardConfig())
    with app.test_client() as client:
        response = client.get('/api/project/99999')
        assert response.status_code == 404


# ============================================================================
# run_dashboard Function Tests
# ============================================================================

@test("run_dashboard function exists")
def test_run_dashboard_exists():
    from dashboard import run_dashboard

    assert callable(run_dashboard)


@test("run_dashboard has expected parameters")
def test_run_dashboard_params():
    import inspect
    from dashboard import run_dashboard

    sig = inspect.signature(run_dashboard)
    params = list(sig.parameters.keys())

    assert 'port' in params
    assert 'host' in params
    assert 'debug' in params
    assert 'no_browser' in params
    assert 'auto_refresh' in params
    assert 'refresh_interval' in params


# ============================================================================
# CSS Content Tests
# ============================================================================

@test("CSS includes dark mode colors")
def test_css_dark_mode():
    from dashboard import DASHBOARD_CSS

    assert '--bg-primary: #1a1a2e' in DASHBOARD_CSS
    assert '--bg-secondary: #16213e' in DASHBOARD_CSS
    assert '--text-primary: #f3f4f6' in DASHBOARD_CSS


@test("CSS includes grade colors")
def test_css_grade_colors():
    from dashboard import DASHBOARD_CSS

    assert '--grade-a: #22c55e' in DASHBOARD_CSS
    assert '--grade-b: #06b6d4' in DASHBOARD_CSS
    assert '--grade-c: #eab308' in DASHBOARD_CSS
    assert '--grade-d: #f97316' in DASHBOARD_CSS
    assert '--grade-f: #ef4444' in DASHBOARD_CSS


@test("CSS includes responsive styles")
def test_css_responsive():
    from dashboard import DASHBOARD_CSS

    assert '@media' in DASHBOARD_CSS
    assert 'max-width: 768px' in DASHBOARD_CSS


@test("CSS includes loading animation")
def test_css_loading():
    from dashboard import DASHBOARD_CSS

    assert '@keyframes spin' in DASHBOARD_CSS
    assert '.loading' in DASHBOARD_CSS


# ============================================================================
# Comparison View Tests (Story 4.5)
# ============================================================================

@test("ComparisonIssue dataclass works")
def test_comparison_issue():
    from dashboard import ComparisonIssue

    issue = ComparisonIssue(
        track_name="Kick",
        severity="critical",
        description="Multiple limiters",
        status="added"
    )

    assert issue.track_name == "Kick"
    assert issue.status == "added"


@test("ComparisonIssue to_dict works")
def test_comparison_issue_to_dict():
    from dashboard import ComparisonIssue

    issue = ComparisonIssue(
        track_name="Bass",
        severity="warning",
        description="High frequency content",
        status="removed"
    )

    d = issue.to_dict()
    assert isinstance(d, dict)
    assert d['status'] == "removed"


@test("ComparisonResult dataclass works")
def test_comparison_result():
    from dashboard import ComparisonResult, VersionDetail, ComparisonIssue

    version_a = VersionDetail(
        id=1, filename="v1.als", path="/path/v1.als",
        health_score=70, grade="B", total_issues=5,
        critical_issues=1, warning_issues=3, scanned_at="2026-01-20"
    )

    version_b = VersionDetail(
        id=2, filename="v2.als", path="/path/v2.als",
        health_score=85, grade="A", total_issues=2,
        critical_issues=0, warning_issues=1, scanned_at="2026-01-25"
    )

    comparison = ComparisonResult(
        project_id=1,
        song_name="Test Song",
        version_a=version_a,
        version_b=version_b,
        health_delta=15,
        grade_change="B → A",
        is_improvement=True
    )

    assert comparison.health_delta == 15
    assert comparison.is_improvement is True
    assert comparison.grade_change == "B → A"


@test("ComparisonResult to_dict works")
def test_comparison_result_to_dict():
    from dashboard import ComparisonResult, VersionDetail

    version_a = VersionDetail(
        id=1, filename="v1.als", path="/path/v1.als",
        health_score=60, grade="C", total_issues=8,
        critical_issues=2, warning_issues=4, scanned_at="2026-01-15"
    )

    version_b = VersionDetail(
        id=2, filename="v2.als", path="/path/v2.als",
        health_score=55, grade="C", total_issues=10,
        critical_issues=3, warning_issues=5, scanned_at="2026-01-20"
    )

    comparison = ComparisonResult(
        project_id=1,
        song_name="Test",
        version_a=version_a,
        version_b=version_b,
        health_delta=-5,
        grade_change="C → C",
        is_improvement=False
    )

    d = comparison.to_dict()
    assert isinstance(d, dict)
    assert d['health_delta'] == -5
    assert d['is_improvement'] is False
    assert 'version_a' in d
    assert 'version_b' in d


@test("COMPARE_CONTENT is defined")
def test_compare_content():
    from dashboard import COMPARE_CONTENT

    assert COMPARE_CONTENT is not None
    assert 'Version Comparison' in COMPARE_CONTENT
    assert 'Version A' in COMPARE_CONTENT
    assert 'Version B' in COMPARE_CONTENT
    assert 'Health Delta' in COMPARE_CONTENT
    assert 'Issues Added' in COMPARE_CONTENT
    assert 'Issues Removed' in COMPARE_CONTENT
    assert 'swapVersions' in COMPARE_CONTENT
    assert 'updateComparison' in COMPARE_CONTENT


@test("Compare route exists in app")
def test_compare_route_exists():
    from dashboard import create_dashboard_app, DashboardConfig

    app = create_dashboard_app(DashboardConfig())
    routes = [rule.rule for rule in app.url_map.iter_rules()]

    assert '/project/<int:project_id>/compare' in routes


@test("Compare route returns 404 for invalid project")
def test_compare_route_404():
    from dashboard import create_dashboard_app, DashboardConfig

    app = create_dashboard_app(DashboardConfig())
    with app.test_client() as client:
        response = client.get('/project/99999/compare')
        assert response.status_code == 404


@test("get_comparison_data returns None for invalid project")
def test_get_comparison_data_invalid():
    from dashboard import get_comparison_data

    result = get_comparison_data(99999, 1, 2)
    assert result is None


@test("get_project_versions returns list")
def test_get_project_versions():
    from dashboard import get_project_versions

    versions = get_project_versions(99999)
    assert isinstance(versions, list)


@test("COMPARE_CONTENT includes Swap button")
def test_compare_swap_button():
    from dashboard import COMPARE_CONTENT

    assert 'Swap' in COMPARE_CONTENT
    assert 'swapVersions()' in COMPARE_CONTENT


@test("COMPARE_CONTENT includes Back to Project link")
def test_compare_back_link():
    from dashboard import COMPARE_CONTENT

    assert 'Back to Project' in COMPARE_CONTENT


@test("COMPARE_CONTENT includes expandable unchanged issues")
def test_compare_expandable_unchanged():
    from dashboard import COMPARE_CONTENT

    assert 'Unchanged Issues' in COMPARE_CONTENT
    assert '<details>' in COMPARE_CONTENT


@test("PROJECT_DETAIL_CONTENT includes Compare link")
def test_project_detail_compare_link():
    from dashboard import PROJECT_DETAIL_CONTENT

    assert 'Compare Versions' in PROJECT_DETAIL_CONTENT
    assert '/compare' in PROJECT_DETAIL_CONTENT


# ============================================================================
# What Should I Work On Tests (Story 4.6)
# ============================================================================

@test("WorkItem dataclass works")
def test_work_item():
    from dashboard import WorkItem

    item = WorkItem(
        project_id=1,
        song_name="Test Song",
        category="quick_win",
        reason="Only 1 critical issue",
        health_score=65,
        grade="C",
        potential_gain=15
    )

    assert item.project_id == 1
    assert item.category == "quick_win"
    assert item.potential_gain == 15


@test("WorkItem to_dict works")
def test_work_item_to_dict():
    from dashboard import WorkItem

    item = WorkItem(
        project_id=2,
        song_name="Song",
        category="deep_work",
        reason="Needs attention",
        health_score=30,
        grade="F",
        potential_gain=30
    )

    d = item.to_dict()
    assert isinstance(d, dict)
    assert d['category'] == "deep_work"
    assert d['potential_gain'] == 30


@test("TodaysFocus dataclass works")
def test_todays_focus():
    from dashboard import TodaysFocus, WorkItem

    item1 = WorkItem(1, "Song1", "quick_win", "Easy fix", 70, "B", 10)
    item2 = WorkItem(2, "Song2", "deep_work", "Needs work", 35, "D", 25)

    focus = TodaysFocus(
        quick_wins=[item1],
        deep_work=[item2],
        ready_to_polish=[],
        total_suggestions=2
    )

    assert len(focus.quick_wins) == 1
    assert len(focus.deep_work) == 1
    assert focus.total_suggestions == 2


@test("TodaysFocus to_dict works")
def test_todays_focus_to_dict():
    from dashboard import TodaysFocus, WorkItem

    item = WorkItem(1, "Song", "ready_to_polish", "Almost there", 78, "B", 2)
    focus = TodaysFocus(
        quick_wins=[],
        deep_work=[],
        ready_to_polish=[item],
        total_suggestions=1
    )

    d = focus.to_dict()
    assert isinstance(d, dict)
    assert len(d['ready_to_polish']) == 1
    assert d['total_suggestions'] == 1


@test("DashboardHome includes todays_focus")
def test_dashboard_home_todays_focus():
    from dashboard import DashboardHome, TodaysFocus, WorkItem

    item = WorkItem(1, "Song", "quick_win", "Quick fix", 65, "C", 15)
    focus = TodaysFocus(quick_wins=[item], total_suggestions=1)

    home = DashboardHome(
        total_projects=5,
        todays_focus=focus
    )

    d = home.to_dict()
    assert 'todays_focus' in d
    assert d['todays_focus']['total_suggestions'] == 1


@test("get_todays_focus returns TodaysFocus")
def test_get_todays_focus():
    from dashboard import get_todays_focus, TodaysFocus

    result = get_todays_focus()
    assert isinstance(result, TodaysFocus)


@test("HOME_CONTENT includes Today's Focus section")
def test_home_content_todays_focus():
    from dashboard import HOME_CONTENT

    assert "Today's Focus" in HOME_CONTENT
    assert "Quick Wins" in HOME_CONTENT
    assert "Deep Work" in HOME_CONTENT
    assert "Ready to Polish" in HOME_CONTENT
    assert "potential" in HOME_CONTENT


@test("CSS includes three-col layout")
def test_css_three_col():
    from dashboard import DASHBOARD_CSS

    assert '.three-col' in DASHBOARD_CSS
    assert 'grid-template-columns: repeat(3, 1fr)' in DASHBOARD_CSS


@test("CSS includes focus-item styles")
def test_css_focus_item():
    from dashboard import DASHBOARD_CSS

    assert '.focus-item' in DASHBOARD_CSS
    assert '.focus-category' in DASHBOARD_CSS
    assert '.focus-item-reason' in DASHBOARD_CSS
    assert '.focus-item-gain' in DASHBOARD_CSS


@test("WorkItem has days_since_worked field")
def test_work_item_days_since_worked():
    from dashboard import WorkItem

    item = WorkItem(
        project_id=1,
        song_name="Test",
        category="quick_win",
        reason="Reason",
        health_score=60,
        grade="C",
        potential_gain=20,
        days_since_worked=7
    )

    assert item.days_since_worked == 7


# ============================================================================
# Run all tests
# ============================================================================

def run_all_tests():
    """Run all test functions."""
    print("=" * 60)
    print("Dashboard Tests (Story 4.4)")
    print("=" * 60)
    print("")

    # Get all test functions
    test_functions = [
        obj for name, obj in globals().items()
        if callable(obj) and hasattr(obj, '_test_name')
    ]

    # Run each test
    for test_func in test_functions:
        test_func()

    print("")
    print("=" * 60)
    print(f"Results: {_test_results['passed']} passed, {_test_results['failed']} failed")
    print("=" * 60)

    return _test_results['failed'] == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
