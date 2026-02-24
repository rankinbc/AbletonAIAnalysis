"""
Local Web Dashboard for ALS Doctor

Provides a local web interface for browsing and managing project analysis data.
Built with Flask for simple deployment.

Routes:
    /                   - Home page with health overview
    /projects           - Sortable/filterable project list
    /project/<id>       - Project detail with timeline chart
    /insights           - Pattern insights and learning
    /settings           - Dashboard settings
"""

import webbrowser
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field, asdict

try:
    from flask import Flask, render_template_string, jsonify, request, abort
    FLASK_AVAILABLE = True
except ImportError:
    Flask = None
    FLASK_AVAILABLE = False


@dataclass
class DashboardConfig:
    """Configuration for the dashboard."""
    port: int = 5000
    host: str = '127.0.0.1'
    debug: bool = False
    auto_open: bool = True
    auto_refresh: bool = True
    refresh_interval: int = 30  # seconds


@dataclass
class ProjectListItem:
    """Project data for dashboard list view."""
    id: int
    song_name: str
    folder_path: str
    version_count: int
    best_score: int
    best_grade: str
    latest_score: int
    latest_grade: str
    trend: str
    last_scanned: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class VersionDetail:
    """Version details for project view."""
    id: int
    filename: str
    path: str
    health_score: int
    grade: str
    total_issues: int
    critical_issues: int
    warning_issues: int
    scanned_at: str
    delta: Optional[int] = None
    is_best: bool = False
    is_current: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class IssueDetail:
    """Issue details for project view."""
    id: int
    track_name: str
    severity: str
    category: str
    description: str
    fix_suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class ProjectDetail:
    """Complete project detail for detail view."""
    id: int
    song_name: str
    folder_path: str
    versions: List[VersionDetail] = field(default_factory=list)
    best_version: Optional[VersionDetail] = None
    current_version: Optional[VersionDetail] = None
    issues: List[IssueDetail] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            'id': self.id,
            'song_name': self.song_name,
            'folder_path': self.folder_path,
            'versions': [v.to_dict() for v in self.versions],
            'issues': [i.to_dict() for i in self.issues],
        }
        if self.best_version:
            result['best_version'] = self.best_version.to_dict()
        if self.current_version:
            result['current_version'] = self.current_version.to_dict()
        return result


@dataclass
class InsightItem:
    """Pattern insight for insights view."""
    pattern_type: str
    description: str
    avg_impact: float
    occurrences: int
    confidence: str
    is_helpful: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class ComparisonIssue:
    """Issue difference for comparison view."""
    track_name: str
    severity: str
    description: str
    status: str  # 'added', 'removed', 'unchanged'

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class DeviceChange:
    """Device change for comparison view."""
    track_name: str
    device_name: str
    device_type: str
    change_type: str  # 'added', 'removed', 'enabled', 'disabled'
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class TrackBreakdown:
    """Track-by-track breakdown for comparison view."""
    track_name: str
    status: str  # 'added', 'removed', 'modified', 'unchanged'
    device_changes: List[DeviceChange] = field(default_factory=list)
    issues_added: int = 0
    issues_removed: int = 0
    net_change: str = ""  # Summary like "+2 devices, -1 issue"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'track_name': self.track_name,
            'status': self.status,
            'device_changes': [d.to_dict() for d in self.device_changes],
            'issues_added': self.issues_added,
            'issues_removed': self.issues_removed,
            'net_change': self.net_change
        }


@dataclass
class ComparisonResult:
    """Result of comparing two versions."""
    project_id: int
    song_name: str
    version_a: VersionDetail
    version_b: VersionDetail
    health_delta: int
    grade_change: str  # e.g., "B → A"
    issues_added: List[ComparisonIssue] = field(default_factory=list)
    issues_removed: List[ComparisonIssue] = field(default_factory=list)
    issues_unchanged: List[ComparisonIssue] = field(default_factory=list)
    track_breakdown: List[TrackBreakdown] = field(default_factory=list)
    devices_added: int = 0
    devices_removed: int = 0
    is_improvement: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'project_id': self.project_id,
            'song_name': self.song_name,
            'version_a': self.version_a.to_dict(),
            'version_b': self.version_b.to_dict(),
            'health_delta': self.health_delta,
            'grade_change': self.grade_change,
            'issues_added': [i.to_dict() for i in self.issues_added],
            'issues_removed': [i.to_dict() for i in self.issues_removed],
            'issues_unchanged': [i.to_dict() for i in self.issues_unchanged],
            'track_breakdown': [t.to_dict() for t in self.track_breakdown],
            'devices_added': self.devices_added,
            'devices_removed': self.devices_removed,
            'is_improvement': self.is_improvement,
        }


@dataclass
class WorkItem:
    """A project suggested for work today."""
    project_id: int
    song_name: str
    category: str  # 'quick_win', 'deep_work', 'ready_to_polish'
    reason: str
    health_score: int
    grade: str
    potential_gain: int  # Estimated score improvement
    days_since_worked: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class TodaysFocus:
    """Today's work prioritization data."""
    quick_wins: List[WorkItem] = field(default_factory=list)
    deep_work: List[WorkItem] = field(default_factory=list)
    ready_to_polish: List[WorkItem] = field(default_factory=list)
    total_suggestions: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'quick_wins': [w.to_dict() for w in self.quick_wins],
            'deep_work': [w.to_dict() for w in self.deep_work],
            'ready_to_polish': [w.to_dict() for w in self.ready_to_polish],
            'total_suggestions': self.total_suggestions
        }


@dataclass
class DashboardHome:
    """Data for the home page."""
    total_projects: int = 0
    total_versions: int = 0
    total_issues: int = 0
    last_scan_date: Optional[str] = None
    grade_distribution: Dict[str, int] = field(default_factory=dict)
    ready_to_release: List[Tuple[str, int, str]] = field(default_factory=list)
    needs_attention: List[Tuple[str, int, str]] = field(default_factory=list)
    todays_focus: Optional[TodaysFocus] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            'total_projects': self.total_projects,
            'total_versions': self.total_versions,
            'total_issues': self.total_issues,
            'last_scan_date': self.last_scan_date,
            'grade_distribution': self.grade_distribution,
            'ready_to_release': [
                {'filename': f, 'score': s, 'song_name': n}
                for f, s, n in self.ready_to_release
            ],
            'needs_attention': [
                {'filename': f, 'score': s, 'song_name': n}
                for f, s, n in self.needs_attention
            ],
        }
        if self.todays_focus:
            result['todays_focus'] = self.todays_focus.to_dict()
        return result


# ============================================================================
# CSS Styles (self-contained, dark mode)
# ============================================================================

DASHBOARD_CSS = """
:root {
    --bg-primary: #1a1a2e;
    --bg-secondary: #16213e;
    --bg-card: #1f2937;
    --text-primary: #f3f4f6;
    --text-secondary: #9ca3af;
    --border-color: #374151;
    --accent: #06b6d4;
    --success: #22c55e;
    --warning: #eab308;
    --error: #ef4444;
    --orange: #f97316;
    --grade-a: #22c55e;
    --grade-b: #06b6d4;
    --grade-c: #eab308;
    --grade-d: #f97316;
    --grade-f: #ef4444;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background-color: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.6;
    min-height: 100vh;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

/* Navigation */
.navbar {
    background-color: var(--bg-secondary);
    padding: 15px 20px;
    border-bottom: 1px solid var(--border-color);
    position: sticky;
    top: 0;
    z-index: 100;
}

.navbar-content {
    max-width: 1200px;
    margin: 0 auto;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.navbar-brand {
    font-size: 1.5rem;
    font-weight: bold;
    color: var(--accent);
    text-decoration: none;
}

.navbar-nav {
    display: flex;
    gap: 20px;
    list-style: none;
}

.navbar-nav a {
    color: var(--text-secondary);
    text-decoration: none;
    padding: 8px 16px;
    border-radius: 6px;
    transition: all 0.2s;
}

.navbar-nav a:hover,
.navbar-nav a.active {
    color: var(--text-primary);
    background-color: var(--bg-card);
}

/* Cards */
.card {
    background-color: var(--bg-card);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
    border: 1px solid var(--border-color);
}

.card-title {
    font-size: 1.1rem;
    margin-bottom: 15px;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Stats Grid */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}

.stat-card {
    background-color: var(--bg-card);
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    border: 1px solid var(--border-color);
}

.stat-value {
    font-size: 2.5rem;
    font-weight: bold;
    color: var(--accent);
}

.stat-label {
    color: var(--text-secondary);
    font-size: 0.9rem;
    margin-top: 5px;
}

/* Grade Badge */
.grade {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 6px;
    font-weight: bold;
    font-size: 0.9rem;
}

.grade-a { background-color: var(--grade-a); color: #000; }
.grade-b { background-color: var(--grade-b); color: #000; }
.grade-c { background-color: var(--grade-c); color: #000; }
.grade-d { background-color: var(--grade-d); color: #000; }
.grade-f { background-color: var(--grade-f); color: #fff; }

/* Trend indicators */
.trend {
    font-size: 0.85rem;
    padding: 2px 8px;
    border-radius: 4px;
}

.trend-up { color: var(--success); }
.trend-down { color: var(--error); }
.trend-stable { color: var(--text-secondary); }
.trend-new { color: var(--accent); }

/* Tables */
.data-table {
    width: 100%;
    border-collapse: collapse;
}

.data-table th,
.data-table td {
    padding: 12px 15px;
    text-align: left;
    border-bottom: 1px solid var(--border-color);
}

.data-table th {
    color: var(--text-secondary);
    font-weight: 500;
    text-transform: uppercase;
    font-size: 0.85rem;
    cursor: pointer;
}

.data-table th:hover {
    color: var(--text-primary);
}

.data-table tr:hover {
    background-color: rgba(255, 255, 255, 0.05);
}

.data-table a {
    color: var(--accent);
    text-decoration: none;
}

.data-table a:hover {
    text-decoration: underline;
}

/* Two-column layout */
.two-col {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
}

@media (max-width: 768px) {
    .two-col {
        grid-template-columns: 1fr;
    }
}

/* Lists */
.project-list {
    list-style: none;
}

.project-list li {
    padding: 10px 0;
    border-bottom: 1px solid var(--border-color);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.project-list li:last-child {
    border-bottom: none;
}

/* Chart container */
.chart-container {
    position: relative;
    height: 300px;
    margin: 20px 0;
}

/* Issues list */
.issue-list {
    list-style: none;
}

.issue-item {
    padding: 12px;
    margin-bottom: 10px;
    border-radius: 8px;
    background-color: rgba(0, 0, 0, 0.2);
}

.issue-critical {
    border-left: 4px solid var(--error);
}

.issue-warning {
    border-left: 4px solid var(--warning);
}

.issue-suggestion {
    border-left: 4px solid var(--accent);
}

.issue-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 5px;
}

.issue-track {
    font-weight: 500;
}

.issue-severity {
    font-size: 0.8rem;
    text-transform: uppercase;
}

.issue-description {
    color: var(--text-secondary);
    font-size: 0.9rem;
}

.issue-fix {
    margin-top: 8px;
    padding: 8px;
    background-color: rgba(6, 182, 212, 0.1);
    border-radius: 4px;
    font-size: 0.85rem;
    color: var(--accent);
}

/* Buttons */
.btn {
    display: inline-block;
    padding: 10px 20px;
    border-radius: 6px;
    font-size: 0.9rem;
    cursor: pointer;
    border: none;
    text-decoration: none;
    transition: all 0.2s;
}

.btn-primary {
    background-color: var(--accent);
    color: #000;
}

.btn-primary:hover {
    background-color: #0891b2;
}

/* Search/Filter */
.search-box {
    width: 100%;
    padding: 12px 15px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    background-color: var(--bg-secondary);
    color: var(--text-primary);
    font-size: 1rem;
    margin-bottom: 20px;
}

.search-box:focus {
    outline: none;
    border-color: var(--accent);
}

/* Version timeline */
.version-timeline {
    position: relative;
    padding-left: 30px;
}

.version-item {
    position: relative;
    padding: 15px;
    margin-bottom: 15px;
    background-color: rgba(0, 0, 0, 0.2);
    border-radius: 8px;
}

.version-item::before {
    content: '';
    position: absolute;
    left: -22px;
    top: 20px;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background-color: var(--border-color);
}

.version-item.best::before {
    background-color: var(--success);
}

.version-item.current::before {
    background-color: var(--accent);
}

.version-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.version-name {
    font-weight: 500;
}

.version-meta {
    color: var(--text-secondary);
    font-size: 0.85rem;
}

/* Grade distribution bar */
.grade-bar {
    display: flex;
    height: 30px;
    border-radius: 6px;
    overflow: hidden;
    margin: 15px 0;
}

.grade-segment {
    display: flex;
    align-items: center;
    justify-content: center;
    color: #000;
    font-weight: bold;
    font-size: 0.8rem;
    min-width: 30px;
}

/* Empty state */
.empty-state {
    text-align: center;
    padding: 40px;
    color: var(--text-secondary);
}

.empty-state-icon {
    font-size: 3rem;
    margin-bottom: 15px;
}

/* Settings form */
.settings-group {
    margin-bottom: 20px;
}

.settings-label {
    display: block;
    margin-bottom: 8px;
    color: var(--text-secondary);
}

.settings-input {
    width: 100%;
    padding: 10px;
    border-radius: 6px;
    border: 1px solid var(--border-color);
    background-color: var(--bg-secondary);
    color: var(--text-primary);
}

/* Loading state */
.loading {
    text-align: center;
    padding: 40px;
    color: var(--text-secondary);
}

.loading::after {
    content: '';
    display: inline-block;
    width: 20px;
    height: 20px;
    border: 2px solid var(--accent);
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-left: 10px;
    vertical-align: middle;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* Today's Focus section */
.three-col {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
}

@media (max-width: 992px) {
    .three-col {
        grid-template-columns: repeat(2, 1fr);
    }
}

@media (max-width: 640px) {
    .three-col {
        grid-template-columns: 1fr;
    }
}

.focus-category {
    padding: 15px;
    background-color: rgba(0, 0, 0, 0.2);
    border-radius: 8px;
}

.focus-list {
    list-style: none;
}

.focus-item {
    padding: 10px 0;
    border-bottom: 1px solid var(--border-color);
}

.focus-item:last-child {
    border-bottom: none;
}

.focus-item-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 5px;
}

.focus-item-header a {
    color: var(--text-primary);
    text-decoration: none;
}

.focus-item-header a:hover {
    color: var(--accent);
}

.focus-item-reason {
    font-size: 0.85rem;
    color: var(--text-secondary);
}

.focus-item-gain {
    font-size: 0.8rem;
    color: var(--success);
    margin-top: 3px;
}

.focus-item-actions {
    display: flex;
    gap: 8px;
    margin-top: 8px;
}

.focus-item-actions button {
    padding: 4px 10px;
    font-size: 0.75rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    cursor: pointer;
    background: var(--bg-card);
    color: var(--text-secondary);
    transition: all 0.2s;
}

.focus-item-actions button:hover {
    background: var(--border-color);
    color: var(--text-primary);
}

.focus-item-actions .btn-worked {
    background: var(--success);
    color: #fff;
    border-color: var(--success);
}

.focus-item-actions .btn-worked:hover {
    background: #16a34a;
}

.focus-item-actions .btn-hide {
    color: var(--text-secondary);
}

.focus-item .days-ago {
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-top: 2px;
}

/* Footer */
.footer {
    text-align: center;
    padding: 20px;
    color: var(--text-secondary);
    font-size: 0.85rem;
    border-top: 1px solid var(--border-color);
    margin-top: 40px;
}
"""


# ============================================================================
# HTML Templates
# ============================================================================

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - ALS Doctor</title>
    <style>{{ css }}</style>
    {{ extra_head|safe }}
</head>
<body>
    <nav class="navbar">
        <div class="navbar-content">
            <a href="/" class="navbar-brand">🎹 ALS Doctor</a>
            <ul class="navbar-nav">
                <li><a href="/" class="{{ 'active' if active == 'home' else '' }}">Home</a></li>
                <li><a href="/projects" class="{{ 'active' if active == 'projects' else '' }}">Projects</a></li>
                <li><a href="/arrangement" class="{{ 'active' if active == 'arrangement' else '' }}">Arrangement</a></li>
                <li><a href="/templates" class="{{ 'active' if active == 'templates' else '' }}">Templates</a></li>
                <li><a href="/midi" class="{{ 'active' if active == 'midi' else '' }}">MIDI</a></li>
                <li><a href="/insights" class="{{ 'active' if active == 'insights' else '' }}">Insights</a></li>
                <li><a href="/settings" class="{{ 'active' if active == 'settings' else '' }}">Settings</a></li>
            </ul>
        </div>
    </nav>

    <main class="container">
        {{ content|safe }}
    </main>

    <footer class="footer">
        ALS Doctor Dashboard • Last updated: {{ timestamp }}
        {% if auto_refresh %}
        <br>Auto-refresh every {{ refresh_interval }} seconds
        {% endif %}
    </footer>

    {{ extra_js|safe }}
</body>
</html>
"""


HOME_CONTENT = """
<h1 style="margin-bottom: 30px;">Dashboard</h1>

<div class="stats-grid">
    <div class="stat-card">
        <div class="stat-value">{{ data.total_projects }}</div>
        <div class="stat-label">Projects</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{{ data.total_versions }}</div>
        <div class="stat-label">Versions</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{{ data.total_issues }}</div>
        <div class="stat-label">Total Issues</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{{ data.last_scan_date or 'Never' }}</div>
        <div class="stat-label">Last Scan</div>
    </div>
</div>

{% if data.grade_distribution %}
<div class="card">
    <h2 class="card-title">Grade Distribution</h2>
    <div class="grade-bar">
        {% for grade, count in data.grade_distribution.items() %}
        {% if count > 0 %}
        <div class="grade-segment grade-{{ grade|lower }}" style="flex: {{ count }};">
            {{ grade }} ({{ count }})
        </div>
        {% endif %}
        {% endfor %}
    </div>
</div>
{% endif %}

<div class="two-col">
    <div class="card">
        <h2 class="card-title">✅ Ready to Release</h2>
        {% if data.ready_to_release %}
        <ul class="project-list">
            {% for item in data.ready_to_release %}
            <li>
                <span>{{ item.filename }}</span>
                <span class="grade grade-a">{{ item.score }}</span>
            </li>
            {% endfor %}
        </ul>
        {% else %}
        <div class="empty-state">
            <div class="empty-state-icon">📊</div>
            <p>No Grade A projects yet</p>
        </div>
        {% endif %}
    </div>

    <div class="card">
        <h2 class="card-title">⚠️ Needs Attention</h2>
        {% if data.needs_attention %}
        <ul class="project-list">
            {% for item in data.needs_attention %}
            <li>
                <span>{{ item.filename }}</span>
                <span class="grade grade-{{ 'f' if item.score < 40 else 'd' }}">{{ item.score }}</span>
            </li>
            {% endfor %}
        </ul>
        {% else %}
        <div class="empty-state">
            <div class="empty-state-icon">🎉</div>
            <p>All projects are in good shape!</p>
        </div>
        {% endif %}
    </div>
</div>

{% if data.todays_focus and data.todays_focus.total_suggestions > 0 %}
<div class="card" style="margin-top: 20px;">
    <h2 class="card-title">🎯 Today's Focus</h2>
    <p style="color: var(--text-secondary); margin-bottom: 20px;">
        Based on your history, here's what to work on today
    </p>

    <div class="three-col">
        <div class="focus-category">
            <h3 style="color: var(--success); margin-bottom: 15px;">⚡ Quick Wins</h3>
            <p style="color: var(--text-secondary); font-size: 0.85rem; margin-bottom: 10px;">
                Small fixes, big impact
            </p>
            {% if data.todays_focus.quick_wins %}
            <ul class="focus-list">
                {% for item in data.todays_focus.quick_wins[:3] %}
                <li class="focus-item" id="focus-{{ item.project_id }}">
                    <div class="focus-item-header">
                        <a href="/project/{{ item.project_id }}">{{ item.song_name }}</a>
                        <span class="grade grade-{{ item.grade|lower }}">{{ item.health_score }}</span>
                    </div>
                    <div class="focus-item-reason">{{ item.reason }}</div>
                    <div class="focus-item-gain">+{{ item.potential_gain }} potential</div>
                    {% if item.days_since_worked is not none %}
                    <div class="days-ago">Last worked: {{ item.days_since_worked }} days ago</div>
                    {% endif %}
                    <div class="focus-item-actions">
                        <button class="btn-worked" onclick="markWorked({{ item.project_id }})">✓ I worked on this</button>
                        <button class="btn-hide" onclick="hideProject({{ item.project_id }})">Hide 7 days</button>
                    </div>
                </li>
                {% endfor %}
            </ul>
            {% else %}
            <p style="color: var(--text-secondary); font-size: 0.9rem;">No quick wins available</p>
            {% endif %}
        </div>

        <div class="focus-category">
            <h3 style="color: var(--warning); margin-bottom: 15px;">🔨 Deep Work</h3>
            <p style="color: var(--text-secondary); font-size: 0.85rem; margin-bottom: 10px;">
                Needs focused attention
            </p>
            {% if data.todays_focus.deep_work %}
            <ul class="focus-list">
                {% for item in data.todays_focus.deep_work[:3] %}
                <li class="focus-item" id="focus-{{ item.project_id }}">
                    <div class="focus-item-header">
                        <a href="/project/{{ item.project_id }}">{{ item.song_name }}</a>
                        <span class="grade grade-{{ item.grade|lower }}">{{ item.health_score }}</span>
                    </div>
                    <div class="focus-item-reason">{{ item.reason }}</div>
                    <div class="focus-item-gain">+{{ item.potential_gain }} potential</div>
                    {% if item.days_since_worked is not none %}
                    <div class="days-ago">Last worked: {{ item.days_since_worked }} days ago</div>
                    {% endif %}
                    <div class="focus-item-actions">
                        <button class="btn-worked" onclick="markWorked({{ item.project_id }})">✓ I worked on this</button>
                        <button class="btn-hide" onclick="hideProject({{ item.project_id }})">Hide 7 days</button>
                    </div>
                </li>
                {% endfor %}
            </ul>
            {% else %}
            <p style="color: var(--text-secondary); font-size: 0.9rem;">No deep work items</p>
            {% endif %}
        </div>

        <div class="focus-category">
            <h3 style="color: var(--accent); margin-bottom: 15px;">✨ Ready to Polish</h3>
            <p style="color: var(--text-secondary); font-size: 0.85rem; margin-bottom: 10px;">
                Almost there, final touches
            </p>
            {% if data.todays_focus.ready_to_polish %}
            <ul class="focus-list">
                {% for item in data.todays_focus.ready_to_polish[:3] %}
                <li class="focus-item" id="focus-{{ item.project_id }}">
                    <div class="focus-item-header">
                        <a href="/project/{{ item.project_id }}">{{ item.song_name }}</a>
                        <span class="grade grade-{{ item.grade|lower }}">{{ item.health_score }}</span>
                    </div>
                    <div class="focus-item-reason">{{ item.reason }}</div>
                    <div class="focus-item-gain">+{{ item.potential_gain }} potential</div>
                    {% if item.days_since_worked is not none %}
                    <div class="days-ago">Last worked: {{ item.days_since_worked }} days ago</div>
                    {% endif %}
                    <div class="focus-item-actions">
                        <button class="btn-worked" onclick="markWorked({{ item.project_id }})">✓ I worked on this</button>
                        <button class="btn-hide" onclick="hideProject({{ item.project_id }})">Hide 7 days</button>
                    </div>
                </li>
                {% endfor %}
            </ul>
            {% else %}
            <p style="color: var(--text-secondary); font-size: 0.9rem;">No items ready to polish</p>
            {% endif %}
        </div>
    </div>
</div>
{% endif %}
"""

# JavaScript for the "I worked on this" and "Hide" buttons
FOCUS_JS = """
<script>
async function markWorked(projectId) {
    try {
        const response = await fetch(`/api/project/${projectId}/worked`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ notes: 'Marked as worked from dashboard' })
        });
        const result = await response.json();
        if (result.success) {
            // Fade out the item and refresh
            const item = document.getElementById(`focus-${projectId}`);
            if (item) {
                item.style.transition = 'opacity 0.3s';
                item.style.opacity = '0.3';
                item.innerHTML = '<div style="color: var(--success); text-align: center; padding: 10px;">✓ Marked as worked</div>';
            }
            // Refresh after delay to update suggestions
            setTimeout(() => location.reload(), 1500);
        } else {
            alert('Error: ' + result.error);
        }
    } catch (e) {
        alert('Failed to record work session: ' + e.message);
    }
}

async function hideProject(projectId) {
    try {
        const response = await fetch(`/api/project/${projectId}/hide`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ days: 7 })
        });
        const result = await response.json();
        if (result.success) {
            // Fade out the item and refresh
            const item = document.getElementById(`focus-${projectId}`);
            if (item) {
                item.style.transition = 'opacity 0.3s';
                item.style.opacity = '0.3';
                item.innerHTML = '<div style="color: var(--text-secondary); text-align: center; padding: 10px;">Hidden for 7 days</div>';
            }
            // Refresh after delay
            setTimeout(() => location.reload(), 1500);
        } else {
            alert('Error: ' + result.error);
        }
    } catch (e) {
        alert('Failed to hide project: ' + e.message);
    }
}
</script>
"""

PROJECTS_CONTENT = """
<h1 style="margin-bottom: 30px;">Projects</h1>

<input type="text" class="search-box" placeholder="Search projects..." id="searchInput" onkeyup="filterProjects()">

<div class="card">
    <table class="data-table" id="projectsTable">
        <thead>
            <tr>
                <th onclick="sortTable(0)">Song Name ↕</th>
                <th onclick="sortTable(1)">Versions ↕</th>
                <th onclick="sortTable(2)">Best ↕</th>
                <th onclick="sortTable(3)">Latest ↕</th>
                <th onclick="sortTable(4)">Trend ↕</th>
                <th onclick="sortTable(5)">Last Scan ↕</th>
            </tr>
        </thead>
        <tbody>
            {% for project in projects %}
            <tr>
                <td><a href="/project/{{ project.id }}">{{ project.song_name }}</a></td>
                <td>{{ project.version_count }}</td>
                <td><span class="grade grade-{{ project.best_grade|lower }}">{{ project.best_grade }}</span> {{ project.best_score }}</td>
                <td><span class="grade grade-{{ project.latest_grade|lower }}">{{ project.latest_grade }}</span> {{ project.latest_score }}</td>
                <td>
                    <span class="trend trend-{{ project.trend }}">
                        {% if project.trend == 'up' %}↑{% elif project.trend == 'down' %}↓{% elif project.trend == 'new' %}★{% else %}→{% endif %}
                        {{ project.trend }}
                    </span>
                </td>
                <td>{{ project.last_scanned }}</td>
            </tr>
            {% else %}
            <tr>
                <td colspan="6" class="empty-state">
                    <div class="empty-state-icon">📂</div>
                    <p>No projects found. Use 'als-doctor scan &lt;dir&gt; --save' to add projects.</p>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<script>
function filterProjects() {
    const input = document.getElementById('searchInput');
    const filter = input.value.toLowerCase();
    const table = document.getElementById('projectsTable');
    const rows = table.getElementsByTagName('tr');

    for (let i = 1; i < rows.length; i++) {
        const nameCell = rows[i].getElementsByTagName('td')[0];
        if (nameCell) {
            const text = nameCell.textContent || nameCell.innerText;
            rows[i].style.display = text.toLowerCase().indexOf(filter) > -1 ? '' : 'none';
        }
    }
}

function sortTable(columnIndex) {
    const table = document.getElementById('projectsTable');
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    const isNumeric = [1, 2, 3].includes(columnIndex);

    let direction = table.dataset.sortDir === 'asc' ? 'desc' : 'asc';
    table.dataset.sortDir = direction;

    rows.sort((a, b) => {
        let aVal = a.cells[columnIndex].textContent.trim();
        let bVal = b.cells[columnIndex].textContent.trim();

        if (isNumeric) {
            aVal = parseInt(aVal.replace(/[^0-9]/g, '')) || 0;
            bVal = parseInt(bVal.replace(/[^0-9]/g, '')) || 0;
        }

        if (direction === 'asc') {
            return aVal > bVal ? 1 : -1;
        } else {
            return aVal < bVal ? 1 : -1;
        }
    });

    rows.forEach(row => table.querySelector('tbody').appendChild(row));
}
</script>
"""


PROJECT_DETAIL_CONTENT = """
<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 30px;">
    <div>
        <h1 style="margin-bottom: 10px;">{{ project.song_name }}</h1>
        <p style="color: var(--text-secondary);">{{ project.folder_path }}</p>
    </div>
    <div style="display: flex; gap: 10px; flex-wrap: wrap;">
        <button class="btn btn-primary" onclick="markProjectWorked({{ project.id }})" id="workedBtn">✓ I worked on this</button>
        {% if project.versions|length >= 2 %}
        <a href="/project/{{ project.id }}/compare" class="btn btn-primary" style="background: var(--accent);">⇄ Compare Versions</a>
        {% endif %}
    </div>
</div>

<div class="stats-grid">
    <div class="stat-card">
        <div class="stat-value">{{ project.versions|length }}</div>
        <div class="stat-label">Versions</div>
    </div>
    {% if project.best_version %}
    <div class="stat-card">
        <div class="stat-value" style="color: var(--grade-{{ project.best_version.grade|lower }});">
            {{ project.best_version.health_score }}
        </div>
        <div class="stat-label">Best Score ({{ project.best_version.grade }})</div>
    </div>
    {% endif %}
    {% if project.current_version %}
    <div class="stat-card">
        <div class="stat-value" style="color: var(--grade-{{ project.current_version.grade|lower }});">
            {{ project.current_version.health_score }}
        </div>
        <div class="stat-label">Current Score ({{ project.current_version.grade }})</div>
    </div>
    {% endif %}
    <div class="stat-card">
        <div class="stat-value">{{ project.issues|length }}</div>
        <div class="stat-label">Current Issues</div>
    </div>
</div>

{% if project.versions|length > 1 %}
<div class="card">
    <h2 class="card-title">Health Timeline</h2>
    <div class="chart-container">
        <canvas id="healthChart"></canvas>
    </div>
</div>
{% endif %}

<div class="two-col">
    <div class="card">
        <h2 class="card-title">Version History</h2>
        <div class="version-timeline">
            {% for version in project.versions|reverse %}
            <div class="version-item {{ 'best' if version.is_best else '' }} {{ 'current' if version.is_current else '' }}">
                <div class="version-header">
                    <span class="version-name">{{ version.filename }}</span>
                    <span class="grade grade-{{ version.grade|lower }}">{{ version.health_score }}</span>
                </div>
                <div class="version-meta">
                    {{ version.scanned_at }}
                    {% if version.delta is not none %}
                    • <span class="trend-{{ 'up' if version.delta > 0 else ('down' if version.delta < 0 else 'stable') }}">
                        {{ '+' if version.delta > 0 else '' }}{{ version.delta }}
                    </span>
                    {% endif %}
                    • {{ version.total_issues }} issues
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <div class="card">
        <h2 class="card-title">Current Issues</h2>
        {% if project.issues %}
        <ul class="issue-list">
            {% for issue in project.issues %}
            <li class="issue-item issue-{{ issue.severity }}">
                <div class="issue-header">
                    <span class="issue-track">{{ issue.track_name }}</span>
                    <span class="issue-severity">{{ issue.severity }}</span>
                </div>
                <div class="issue-description">{{ issue.description }}</div>
                {% if issue.fix_suggestion %}
                <div class="issue-fix">💡 {{ issue.fix_suggestion }}</div>
                {% endif %}
            </li>
            {% endfor %}
        </ul>
        {% else %}
        <div class="empty-state">
            <div class="empty-state-icon">✅</div>
            <p>No issues detected!</p>
        </div>
        {% endif %}
    </div>
</div>
"""


PROJECT_CHART_JS = """
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
const ctx = document.getElementById('healthChart');
if (ctx) {
    const versions = {{ versions_json|safe }};

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: versions.map(v => v.filename),
            datasets: [{
                label: 'Health Score',
                data: versions.map(v => v.health_score),
                borderColor: '#06b6d4',
                backgroundColor: 'rgba(6, 182, 212, 0.1)',
                tension: 0.3,
                fill: true,
                pointRadius: versions.map(v => v.is_best ? 10 : (v.is_current ? 8 : 5)),
                pointBackgroundColor: versions.map(v => {
                    if (v.is_best) return '#22c55e';
                    if (v.is_current) return '#06b6d4';
                    return '#9ca3af';
                }),
                pointStyle: versions.map(v => v.is_best ? 'star' : 'circle')
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    min: 0,
                    max: 100,
                    grid: { color: '#374151' },
                    ticks: { color: '#9ca3af' }
                },
                x: {
                    grid: { color: '#374151' },
                    ticks: { color: '#9ca3af' }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const v = versions[context.dataIndex];
                            return [
                                'Score: ' + v.health_score + ' (' + v.grade + ')',
                                'Issues: ' + v.total_issues,
                                'Date: ' + v.scanned_at
                            ];
                        }
                    }
                }
            }
        }
    });
}

// Mark project as worked on
async function markProjectWorked(projectId) {
    const btn = document.getElementById('workedBtn');
    try {
        btn.disabled = true;
        btn.innerHTML = '...';

        const response = await fetch(`/api/project/${projectId}/worked`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ notes: 'Marked from project detail page' })
        });
        const result = await response.json();

        if (result.success) {
            btn.innerHTML = '✓ Done!';
            btn.style.background = 'var(--success)';
            setTimeout(() => {
                btn.innerHTML = '✓ I worked on this';
                btn.disabled = false;
            }, 2000);
        } else {
            btn.innerHTML = 'Error';
            btn.style.background = 'var(--error)';
            setTimeout(() => {
                btn.innerHTML = '✓ I worked on this';
                btn.disabled = false;
            }, 2000);
        }
    } catch (e) {
        btn.innerHTML = 'Error';
        btn.style.background = 'var(--error)';
        setTimeout(() => {
            btn.innerHTML = '✓ I worked on this';
            btn.disabled = false;
        }, 2000);
    }
}
</script>
"""


INSIGHTS_CONTENT = """
<h1 style="margin-bottom: 30px;">Insights</h1>

{% if not has_sufficient_data %}
<div class="card">
    <div class="empty-state">
        <div class="empty-state-icon">📊</div>
        <h3>Not Enough Data</h3>
        <p>Need at least 10 version comparisons to generate insights.</p>
        <p style="margin-top: 10px;">Keep scanning your projects with <code>--save</code> to build history.</p>
    </div>
</div>
{% else %}

<div class="two-col">
    <div class="card">
        <h2 class="card-title">✅ Patterns That Help</h2>
        {% if helpful_patterns %}
        <ul class="issue-list">
            {% for pattern in helpful_patterns %}
            <li class="issue-item" style="border-left-color: var(--success);">
                <div class="issue-header">
                    <span class="issue-track">{{ pattern.description }}</span>
                    <span class="issue-severity" style="color: var(--success);">{{ pattern.confidence }}</span>
                </div>
                <div class="issue-description">
                    Avg impact: <strong style="color: var(--success);">+{{ "%.1f"|format(pattern.avg_impact) }}</strong>
                    • {{ pattern.occurrences }} occurrences
                </div>
            </li>
            {% endfor %}
        </ul>
        {% else %}
        <p class="empty-state">No helpful patterns detected yet.</p>
        {% endif %}
    </div>

    <div class="card">
        <h2 class="card-title">⚠️ Patterns That Hurt</h2>
        {% if harmful_patterns %}
        <ul class="issue-list">
            {% for pattern in harmful_patterns %}
            <li class="issue-item" style="border-left-color: var(--error);">
                <div class="issue-header">
                    <span class="issue-track">{{ pattern.description }}</span>
                    <span class="issue-severity" style="color: var(--error);">{{ pattern.confidence }}</span>
                </div>
                <div class="issue-description">
                    Avg impact: <strong style="color: var(--error);">{{ "%.1f"|format(pattern.avg_impact) }}</strong>
                    • {{ pattern.occurrences }} occurrences
                </div>
            </li>
            {% endfor %}
        </ul>
        {% else %}
        <p class="empty-state">No harmful patterns detected yet.</p>
        {% endif %}
    </div>
</div>

{% if common_mistakes %}
<div class="card">
    <h2 class="card-title">🚫 Common Mistakes</h2>
    <ul class="issue-list">
        {% for mistake in common_mistakes %}
        <li class="issue-item issue-warning">
            <div class="issue-header">
                <span class="issue-track">{{ mistake.description }}</span>
                <span class="issue-severity">{{ mistake.occurrences }}x</span>
            </div>
            <div class="issue-description">
                Typically causes: <strong style="color: var(--error);">{{ "%.1f"|format(mistake.avg_impact) }}</strong> health drop
            </div>
        </li>
        {% endfor %}
    </ul>
</div>
{% endif %}

{% endif %}
"""


SETTINGS_CONTENT = """
<h1 style="margin-bottom: 30px;">Settings</h1>

<div class="card">
    <h2 class="card-title">Dashboard Settings</h2>

    <div class="settings-group">
        <label class="settings-label">Auto-refresh interval (seconds)</label>
        <input type="number" class="settings-input" value="{{ config.refresh_interval }}" min="10" max="300" id="refreshInterval">
    </div>

    <div class="settings-group">
        <label class="settings-label">
            <input type="checkbox" {{ 'checked' if config.auto_refresh else '' }} id="autoRefresh">
            Enable auto-refresh
        </label>
    </div>

    <button class="btn btn-primary" onclick="saveSettings()">Save Settings</button>
</div>

<div class="card">
    <h2 class="card-title">Database Information</h2>
    <p>Location: <code>{{ db_path }}</code></p>
    <p>Total Projects: {{ total_projects }}</p>
    <p>Total Versions: {{ total_versions }}</p>
</div>

<script>
function saveSettings() {
    // In a real implementation, this would POST to /api/settings
    alert('Settings saved! (Note: This is a demo - settings are stored in memory only)');
}
</script>
"""


COMPARE_CONTENT = """
<h1 style="margin-bottom: 10px;">{{ comparison.song_name }}</h1>
<p style="color: var(--text-secondary); margin-bottom: 20px;">Version Comparison</p>

<div class="card">
    <div style="display: flex; gap: 20px; align-items: center; flex-wrap: wrap; margin-bottom: 20px;">
        <div>
            <label class="settings-label">Version A</label>
            <select class="settings-input" id="versionA" onchange="updateComparison()" style="width: 250px;">
                {% for v in versions %}
                <option value="{{ v.id }}" {{ 'selected' if v.id == comparison.version_a.id else '' }}>
                    {{ v.filename }} ({{ v.health_score }})
                </option>
                {% endfor %}
            </select>
        </div>
        <div style="font-size: 1.5rem; padding-top: 20px;">→</div>
        <div>
            <label class="settings-label">Version B</label>
            <select class="settings-input" id="versionB" onchange="updateComparison()" style="width: 250px;">
                {% for v in versions %}
                <option value="{{ v.id }}" {{ 'selected' if v.id == comparison.version_b.id else '' }}>
                    {{ v.filename }} ({{ v.health_score }})
                </option>
                {% endfor %}
            </select>
        </div>
        <button class="btn btn-primary" onclick="swapVersions()" style="margin-top: 20px;">⇄ Swap</button>
    </div>
</div>

<div class="stats-grid">
    <div class="stat-card">
        <div class="stat-value" style="color: var(--grade-{{ comparison.version_a.grade|lower }});">
            {{ comparison.version_a.health_score }}
        </div>
        <div class="stat-label">Version A ({{ comparison.version_a.grade }})</div>
    </div>
    <div class="stat-card">
        <div class="stat-value" style="color: {{ 'var(--success)' if comparison.health_delta > 0 else ('var(--error)' if comparison.health_delta < 0 else 'var(--text-secondary)') }};">
            {{ '+' if comparison.health_delta > 0 else '' }}{{ comparison.health_delta }}
        </div>
        <div class="stat-label">Health Delta</div>
    </div>
    <div class="stat-card">
        <div class="stat-value" style="color: var(--grade-{{ comparison.version_b.grade|lower }});">
            {{ comparison.version_b.health_score }}
        </div>
        <div class="stat-label">Version B ({{ comparison.version_b.grade }})</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">
            <span style="color: var(--error);">+{{ comparison.issues_added|length }}</span>
            /
            <span style="color: var(--success);">-{{ comparison.issues_removed|length }}</span>
        </div>
        <div class="stat-label">Issues +/-</div>
    </div>
</div>

<div class="card" style="text-align: center; margin-bottom: 20px;">
    <h2 style="font-size: 1.5rem; margin-bottom: 10px;">
        {% if comparison.is_improvement %}
        <span style="color: var(--success);">✓ IMPROVEMENT</span>
        {% elif comparison.health_delta < 0 %}
        <span style="color: var(--error);">✗ REGRESSION</span>
        {% else %}
        <span style="color: var(--text-secondary);">→ NO CHANGE</span>
        {% endif %}
    </h2>
    <p>{{ comparison.grade_change }}</p>
</div>

<div class="two-col">
    <div class="card">
        <h2 class="card-title" style="color: var(--error);">🔴 Issues Added ({{ comparison.issues_added|length }})</h2>
        {% if comparison.issues_added %}
        <ul class="issue-list">
            {% for issue in comparison.issues_added %}
            <li class="issue-item issue-{{ issue.severity }}">
                <div class="issue-header">
                    <span class="issue-track">{{ issue.track_name }}</span>
                    <span class="issue-severity">{{ issue.severity }}</span>
                </div>
                <div class="issue-description">{{ issue.description }}</div>
            </li>
            {% endfor %}
        </ul>
        {% else %}
        <div class="empty-state">
            <p>No new issues</p>
        </div>
        {% endif %}
    </div>

    <div class="card">
        <h2 class="card-title" style="color: var(--success);">🟢 Issues Removed ({{ comparison.issues_removed|length }})</h2>
        {% if comparison.issues_removed %}
        <ul class="issue-list">
            {% for issue in comparison.issues_removed %}
            <li class="issue-item" style="border-left-color: var(--success);">
                <div class="issue-header">
                    <span class="issue-track">{{ issue.track_name }}</span>
                    <span class="issue-severity">{{ issue.severity }}</span>
                </div>
                <div class="issue-description">{{ issue.description }}</div>
            </li>
            {% endfor %}
        </ul>
        {% else %}
        <div class="empty-state">
            <p>No issues removed</p>
        </div>
        {% endif %}
    </div>
</div>

{% if comparison.track_breakdown %}
<div class="card">
    <h2 class="card-title">📊 Track-by-Track Breakdown</h2>
    <p style="color: var(--text-secondary); margin-bottom: 15px; font-size: 0.9rem;">
        {% if comparison.devices_added or comparison.devices_removed %}
        Device changes:
        {% if comparison.devices_added %}<span style="color: var(--error);">+{{ comparison.devices_added }}</span>{% endif %}
        {% if comparison.devices_added and comparison.devices_removed %} / {% endif %}
        {% if comparison.devices_removed %}<span style="color: var(--success);">-{{ comparison.devices_removed }}</span>{% endif %}
        {% else %}
        No device changes recorded
        {% endif %}
    </p>
    <table class="data-table">
        <thead>
            <tr>
                <th>Track</th>
                <th>Status</th>
                <th>Changes</th>
            </tr>
        </thead>
        <tbody>
            {% for track in comparison.track_breakdown %}
            {% if track.status != 'unchanged' %}
            <tr>
                <td>{{ track.track_name }}</td>
                <td>
                    {% if track.status == 'added' %}
                    <span style="color: var(--success);">✚ Added</span>
                    {% elif track.status == 'removed' %}
                    <span style="color: var(--error);">✖ Removed</span>
                    {% elif track.status == 'modified' %}
                    <span style="color: var(--warning);">✎ Modified</span>
                    {% endif %}
                </td>
                <td style="color: var(--text-secondary); font-size: 0.9rem;">
                    {{ track.net_change }}
                    {% if track.device_changes %}
                    <details style="margin-top: 5px;">
                        <summary style="cursor: pointer; font-size: 0.85rem;">Show {{ track.device_changes|length }} device change(s)</summary>
                        <ul style="margin-top: 5px; padding-left: 15px; font-size: 0.85rem;">
                            {% for change in track.device_changes %}
                            <li style="color: {% if 'added' in change.change_type %}var(--error){% elif 'removed' in change.change_type %}var(--success){% elif 'enabled' in change.change_type %}var(--accent){% else %}var(--warning){% endif %};">
                                {{ change.change_type.replace('_', ' ').title() }}: {{ change.device_name }} ({{ change.device_type }})
                            </li>
                            {% endfor %}
                        </ul>
                    </details>
                    {% endif %}
                </td>
            </tr>
            {% endif %}
            {% endfor %}
        </tbody>
    </table>
</div>
{% endif %}

{% if comparison.issues_unchanged %}
<div class="card">
    <details>
        <summary style="cursor: pointer; padding: 10px;">
            <span style="color: var(--text-secondary);">📋 Unchanged Issues ({{ comparison.issues_unchanged|length }})</span>
        </summary>
        <ul class="issue-list" style="margin-top: 15px;">
            {% for issue in comparison.issues_unchanged %}
            <li class="issue-item issue-{{ issue.severity }}">
                <div class="issue-header">
                    <span class="issue-track">{{ issue.track_name }}</span>
                    <span class="issue-severity">{{ issue.severity }}</span>
                </div>
                <div class="issue-description">{{ issue.description }}</div>
            </li>
            {% endfor %}
        </ul>
    </details>
</div>
{% endif %}

<div style="margin-top: 20px;">
    <a href="/project/{{ comparison.project_id }}" class="btn btn-primary">← Back to Project</a>
</div>

<script>
function updateComparison() {
    const versionA = document.getElementById('versionA').value;
    const versionB = document.getElementById('versionB').value;
    window.location.href = '/project/{{ comparison.project_id }}/compare?a=' + versionA + '&b=' + versionB;
}

function swapVersions() {
    const versionA = document.getElementById('versionA').value;
    const versionB = document.getElementById('versionB').value;
    window.location.href = '/project/{{ comparison.project_id }}/compare?a=' + versionB + '&b=' + versionA;
}
</script>
"""


ARRANGEMENT_CONTENT = """
<h1 style="margin-bottom: 30px;">Arrangement Analysis</h1>

<div class="card" style="margin-bottom: 20px;">
    <div style="display: flex; gap: 20px; align-items: flex-end; flex-wrap: wrap;">
        <div style="flex: 1; min-width: 300px;">
            <label class="settings-label">Audio File</label>
            <select class="settings-input" id="audioFile" style="width: 100%;">
                <option value="">-- Select an audio file --</option>
                {% for file in audio_files %}
                <option value="{{ file.path }}">{{ file.name }}</option>
                {% endfor %}
            </select>
        </div>
        <button class="btn btn-primary" onclick="analyzeArrangement()" id="analyzeBtn">
            Analyze
        </button>
    </div>
</div>

<div id="loadingIndicator" style="display: none; text-align: center; padding: 40px;">
    <div style="font-size: 2rem; margin-bottom: 10px;">⏳</div>
    <p>Analyzing arrangement... This may take a minute.</p>
</div>

<div id="resultsContainer" style="display: none;">
    <!-- Overall Score -->
    <div class="card" style="margin-bottom: 20px;">
        <h2 class="card-title">Overall Score</h2>
        <div style="display: flex; align-items: center; gap: 20px;">
            <div id="overallScore" style="font-size: 3rem; font-weight: bold;"></div>
            <div id="overallGrade" style="font-size: 2rem; padding: 5px 15px; border-radius: 8px;"></div>
            <div style="flex: 1;">
                <div class="progress-bar" style="height: 20px; background: var(--bg-secondary); border-radius: 10px; overflow: hidden;">
                    <div id="scoreProgress" style="height: 100%; transition: width 0.5s;"></div>
                </div>
            </div>
        </div>
    </div>

    <!-- Section Timeline -->
    <div class="card" style="margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
            <h2 class="card-title" style="margin-bottom: 0;">Section Timeline</h2>
            <span id="totalDuration" style="color: var(--text-secondary);"></span>
        </div>
        <div id="timeline" style="display: flex; height: 60px; border-radius: 8px; overflow: hidden; margin-bottom: 10px;">
        </div>
        <div style="display: flex; justify-content: space-between; color: var(--text-secondary); font-size: 0.85rem;">
            <span>0:00</span>
            <span id="timelineEnd"></span>
        </div>
        <div id="timelineLegend" style="display: flex; gap: 15px; margin-top: 15px; flex-wrap: wrap;">
        </div>
    </div>

    <!-- Component Scores and Section Details -->
    <div class="two-col">
        <div class="card">
            <h2 class="card-title">Component Scores</h2>
            <div style="position: relative; height: 300px;">
                <canvas id="radarChart"></canvas>
            </div>
            <div id="componentList" style="margin-top: 20px;">
            </div>
        </div>

        <div class="card">
            <h2 class="card-title">Section Details</h2>
            <div id="sectionDetails" style="max-height: 400px; overflow-y: auto;">
            </div>
        </div>
    </div>

    <!-- Issues -->
    <div class="card" style="margin-top: 20px;">
        <h2 class="card-title">Issues</h2>
        <div id="issuesSummary" style="display: flex; gap: 15px; margin-bottom: 15px;">
        </div>
        <div id="issuesList">
        </div>
    </div>
</div>

<style>
.section-type-intro { background: #3b82f6; }
.section-type-buildup { background: #f97316; }
.section-type-drop { background: #ef4444; }
.section-type-breakdown { background: #8b5cf6; }
.section-type-outro { background: #14b8a6; }
.section-type-unknown { background: #6b7280; }

.timeline-section {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    color: white;
    font-size: 0.7rem;
    text-shadow: 0 1px 2px rgba(0,0,0,0.5);
    cursor: pointer;
    transition: opacity 0.2s;
    min-width: 30px;
}

.timeline-section:hover {
    opacity: 0.8;
}

.timeline-section .label {
    font-weight: bold;
    text-transform: uppercase;
}

.timeline-section .bars {
    font-size: 0.65rem;
    opacity: 0.9;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.85rem;
}

.legend-color {
    width: 12px;
    height: 12px;
    border-radius: 3px;
}

.section-card {
    background: var(--bg-secondary);
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 10px;
    border-left: 4px solid transparent;
}

.section-card.section-ok { border-left-color: var(--success); }
.section-card.section-warn { border-left-color: var(--warning); }
.section-card.section-error { border-left-color: var(--error); }

.section-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.type-badge {
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    text-transform: uppercase;
    font-weight: bold;
    color: white;
}

.section-card-body {
    font-size: 0.85rem;
    color: var(--text-secondary);
}

.check-item {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    margin-right: 10px;
}

.check-pass { color: var(--success); }
.check-fail { color: var(--error); }

.issue-card {
    background: var(--bg-secondary);
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 10px;
}

.issue-card.issue-critical { border-left: 4px solid var(--error); }
.issue-card.issue-warning { border-left: 4px solid var(--warning); }
.issue-card.issue-suggestion { border-left: 4px solid var(--accent); }

.issue-severity-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.7rem;
    text-transform: uppercase;
    font-weight: bold;
    margin-right: 8px;
}

.issue-severity-badge.critical { background: var(--error); color: white; }
.issue-severity-badge.warning { background: var(--warning); color: black; }
.issue-severity-badge.suggestion { background: var(--accent); color: white; }

.component-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid var(--border-color);
}

.component-row:last-child {
    border-bottom: none;
}

.component-name {
    text-transform: capitalize;
}

.component-score {
    font-weight: bold;
}
</style>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
let radarChart = null;

const SECTION_COLORS = {
    'intro': '#3b82f6',
    'buildup': '#f97316',
    'drop': '#ef4444',
    'breakdown': '#8b5cf6',
    'outro': '#14b8a6',
    'unknown': '#6b7280'
};

const GRADE_COLORS = {
    'A': '#22c55e',
    'B': '#06b6d4',
    'C': '#eab308',
    'D': '#f97316',
    'F': '#ef4444'
};

function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return mins + ':' + secs.toString().padStart(2, '0');
}

async function analyzeArrangement() {
    const audioFile = document.getElementById('audioFile').value;
    if (!audioFile) {
        alert('Please select an audio file');
        return;
    }

    document.getElementById('loadingIndicator').style.display = 'block';
    document.getElementById('resultsContainer').style.display = 'none';
    document.getElementById('analyzeBtn').disabled = true;

    try {
        const response = await fetch('/api/arrangement/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ audio_path: audioFile })
        });

        const data = await response.json();

        if (data.error) {
            alert('Error: ' + data.error);
            return;
        }

        renderResults(data);
    } catch (error) {
        alert('Error analyzing file: ' + error.message);
    } finally {
        document.getElementById('loadingIndicator').style.display = 'none';
        document.getElementById('analyzeBtn').disabled = false;
    }
}

function renderResults(data) {
    document.getElementById('resultsContainer').style.display = 'block';

    // Overall score
    const gradeColor = GRADE_COLORS[data.grade] || '#6b7280';
    document.getElementById('overallScore').textContent = data.overall_score + '/100';
    document.getElementById('overallScore').style.color = gradeColor;
    document.getElementById('overallGrade').textContent = data.grade;
    document.getElementById('overallGrade').style.background = gradeColor;
    document.getElementById('overallGrade').style.color = data.grade === 'C' ? 'black' : 'white';
    document.getElementById('scoreProgress').style.width = data.overall_score + '%';
    document.getElementById('scoreProgress').style.background = gradeColor;

    // Timeline
    renderTimeline(data.section_scores, data.total_duration);

    // Radar chart
    renderRadarChart(data.component_scores);

    // Component list
    renderComponentList(data.component_scores);

    // Section details
    renderSectionDetails(data.section_scores);

    // Issues
    renderIssues(data.issues);
}

function renderTimeline(sections, totalDuration) {
    const timeline = document.getElementById('timeline');
    timeline.innerHTML = '';

    const legend = document.getElementById('timelineLegend');
    legend.innerHTML = '';
    const seenTypes = new Set();

    sections.forEach(section => {
        const widthPct = (section.duration / totalDuration) * 100;
        const sectionType = section.section_type || 'unknown';

        const div = document.createElement('div');
        div.className = 'timeline-section section-type-' + sectionType;
        div.style.width = widthPct + '%';
        div.innerHTML = '<span class="label">' + sectionType.substring(0, 4).toUpperCase() + '</span>' +
                       '<span class="bars">' + section.bars + 'b</span>';
        div.title = sectionType + ': ' + formatTime(section.start_time) + ' - ' + formatTime(section.end_time) +
                   ' (' + section.bars + ' bars)';
        timeline.appendChild(div);

        if (!seenTypes.has(sectionType)) {
            seenTypes.add(sectionType);
            const legendItem = document.createElement('div');
            legendItem.className = 'legend-item';
            legendItem.innerHTML = '<div class="legend-color" style="background: ' + SECTION_COLORS[sectionType] + '"></div>' +
                                  '<span>' + sectionType.charAt(0).toUpperCase() + sectionType.slice(1) + '</span>';
            legend.appendChild(legendItem);
        }
    });

    document.getElementById('totalDuration').textContent = formatTime(totalDuration);
    document.getElementById('timelineEnd').textContent = formatTime(totalDuration);
}

function renderRadarChart(componentScores) {
    const ctx = document.getElementById('radarChart').getContext('2d');

    const labels = Object.keys(componentScores).map(k =>
        k.replace('_', ' ').replace(/\\b\\w/g, l => l.toUpperCase())
    );
    const values = Object.values(componentScores);

    if (radarChart) {
        radarChart.destroy();
    }

    radarChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Score',
                data: values,
                backgroundColor: 'rgba(6, 182, 212, 0.2)',
                borderColor: '#06b6d4',
                borderWidth: 2,
                pointBackgroundColor: '#06b6d4',
                pointRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    min: 0,
                    max: 100,
                    ticks: {
                        stepSize: 20,
                        color: '#9ca3af'
                    },
                    grid: {
                        color: '#374151'
                    },
                    angleLines: {
                        color: '#374151'
                    },
                    pointLabels: {
                        color: '#f3f4f6',
                        font: { size: 11 }
                    }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

function renderComponentList(componentScores) {
    const container = document.getElementById('componentList');
    container.innerHTML = '';

    Object.entries(componentScores).forEach(([key, value]) => {
        const name = key.replace('_', ' ');
        const color = value >= 70 ? 'var(--success)' : (value >= 50 ? 'var(--warning)' : 'var(--error)');

        const div = document.createElement('div');
        div.className = 'component-row';
        div.innerHTML = '<span class="component-name">' + name + '</span>' +
                       '<span class="component-score" style="color: ' + color + '">' + value + '/100</span>';
        container.appendChild(div);
    });
}

function renderSectionDetails(sections) {
    const container = document.getElementById('sectionDetails');
    container.innerHTML = '';

    sections.forEach((section, index) => {
        const statusClass = section.score >= 70 ? 'section-ok' : (section.score >= 50 ? 'section-warn' : 'section-error');
        const sectionType = section.section_type || 'unknown';

        const div = document.createElement('div');
        div.className = 'section-card ' + statusClass;
        div.innerHTML = '<div class="section-card-header">' +
            '<div>' +
                '<span class="type-badge section-type-' + sectionType + '">' + sectionType + '</span>' +
                '<span style="margin-left: 10px; color: var(--text-secondary);">' +
                    formatTime(section.start_time) + ' - ' + formatTime(section.end_time) +
                '</span>' +
            '</div>' +
            '<span style="font-weight: bold;">' + section.score + '/100</span>' +
        '</div>' +
        '<div class="section-card-body">' +
            '<span>' + section.bars + ' bars</span>' +
            (section.checks ? '<div style="margin-top: 5px;">' +
                section.checks.map(c =>
                    '<span class="check-item ' + (c.passed ? 'check-pass' : 'check-fail') + '">' +
                    (c.passed ? '✓' : '✗') + ' ' + c.name + '</span>'
                ).join('') +
            '</div>' : '') +
        '</div>';
        container.appendChild(div);
    });
}

function renderIssues(issues) {
    const summary = document.getElementById('issuesSummary');
    const list = document.getElementById('issuesList');

    const counts = { critical: 0, warning: 0, suggestion: 0 };
    issues.forEach(issue => {
        const sev = issue.severity.toLowerCase();
        if (counts[sev] !== undefined) counts[sev]++;
    });

    summary.innerHTML =
        '<span style="color: var(--error);">' + counts.critical + ' Critical</span>' +
        '<span style="color: var(--warning);">' + counts.warning + ' Warning</span>' +
        '<span style="color: var(--accent);">' + counts.suggestion + ' Suggestions</span>';

    list.innerHTML = '';

    if (issues.length === 0) {
        list.innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 20px;">No issues found!</div>';
        return;
    }

    // Sort by severity
    const severityOrder = { 'critical': 0, 'warning': 1, 'suggestion': 2 };
    issues.sort((a, b) => severityOrder[a.severity.toLowerCase()] - severityOrder[b.severity.toLowerCase()]);

    issues.forEach(issue => {
        const sev = issue.severity.toLowerCase();
        const div = document.createElement('div');
        div.className = 'issue-card issue-' + sev;
        div.innerHTML =
            '<div>' +
                '<span class="issue-severity-badge ' + sev + '">' + issue.severity + '</span>' +
                '<span>' + issue.message + '</span>' +
            '</div>' +
            (issue.fix_suggestion ? '<div style="margin-top: 8px; font-size: 0.85rem; color: var(--text-secondary);">Fix: ' + issue.fix_suggestion + '</div>' : '');
        list.appendChild(div);
    });
}
</script>
"""


TEMPLATES_CONTENT = """
<h1 style="margin-bottom: 30px;">Arrangement Templates</h1>

<div class="two-col">
    <!-- Source Selection -->
    <div class="card">
        <h2 class="card-title">Template Source</h2>

        <div style="margin-bottom: 20px;">
            <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; margin-bottom: 15px;">
                <input type="radio" name="source" value="preset" checked onchange="toggleSource()">
                <span>Genre Preset</span>
            </label>
            <select class="settings-input" id="presetSelect" style="width: 100%;" onchange="loadPreset()">
                {% for preset in presets %}
                <option value="{{ preset.id }}">{{ preset.name }} ({{ preset.default_bpm }} BPM)</option>
                {% endfor %}
            </select>
        </div>

        <div style="margin-bottom: 20px;">
            <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; margin-bottom: 15px;">
                <input type="radio" name="source" value="reference" onchange="toggleSource()">
                <span>From Reference Track</span>
            </label>
            <select class="settings-input" id="referenceSelect" style="width: 100%;" disabled>
                <option value="">-- Select audio file --</option>
                {% for file in audio_files %}
                <option value="{{ file.path }}">{{ file.name }}</option>
                {% endfor %}
            </select>
        </div>

        <button class="btn btn-primary" onclick="generateTemplate()" style="width: 100%;">
            Generate Template
        </button>
    </div>

    <!-- Parameters -->
    <div class="card">
        <h2 class="card-title">Parameters</h2>

        <div style="margin-bottom: 15px;">
            <label class="settings-label">BPM</label>
            <div style="display: flex; gap: 10px; align-items: center;">
                <input type="number" class="settings-input" id="bpmInput" value="138" min="60" max="200" style="width: 100px;">
                <input type="range" id="bpmSlider" min="60" max="200" value="138" style="flex: 1;" oninput="document.getElementById('bpmInput').value = this.value; updateTimings();">
            </div>
        </div>

        <div style="margin-bottom: 15px;">
            <label class="settings-label">Ableton Connection</label>
            <div id="abletonStatus" style="display: flex; align-items: center; gap: 10px;">
                <span class="status-dot" style="background: var(--text-secondary);"></span>
                <span>Not connected</span>
            </div>
        </div>

        <button class="btn" onclick="checkAbletonConnection()" style="width: 100%;">
            Check Connection
        </button>
    </div>
</div>

<!-- Section Presets Palette -->
<div class="card" style="margin-top: 20px;">
    <h2 class="card-title">Section Presets <span style="font-size: 0.8rem; color: var(--text-secondary); font-weight: normal;">(drag to add)</span></h2>

    <div id="presetPalette" style="display: flex; flex-wrap: wrap; gap: 10px;">
        <!-- Intro variants -->
        <div class="preset-card" draggable="true" data-type="intro" data-bars="16" style="background: linear-gradient(135deg, #3b82f6, #2563eb);">
            <div class="preset-label">INTRO</div>
            <div class="preset-bars">16 bars</div>
        </div>
        <div class="preset-card" draggable="true" data-type="intro" data-bars="32" style="background: linear-gradient(135deg, #3b82f6, #2563eb);">
            <div class="preset-label">INTRO</div>
            <div class="preset-bars">32 bars</div>
        </div>
        <div class="preset-card" draggable="true" data-type="intro" data-bars="64" style="background: linear-gradient(135deg, #3b82f6, #2563eb);">
            <div class="preset-label">INTRO</div>
            <div class="preset-bars">64 bars</div>
        </div>

        <!-- Buildup variants -->
        <div class="preset-card" draggable="true" data-type="buildup" data-bars="8" style="background: linear-gradient(135deg, #f97316, #ea580c);">
            <div class="preset-label">BUILDUP</div>
            <div class="preset-bars">8 bars</div>
        </div>
        <div class="preset-card" draggable="true" data-type="buildup" data-bars="16" style="background: linear-gradient(135deg, #f97316, #ea580c);">
            <div class="preset-label">BUILDUP</div>
            <div class="preset-bars">16 bars</div>
        </div>
        <div class="preset-card" draggable="true" data-type="buildup" data-bars="32" style="background: linear-gradient(135deg, #f97316, #ea580c);">
            <div class="preset-label">BUILDUP</div>
            <div class="preset-bars">32 bars</div>
        </div>

        <!-- Drop variants -->
        <div class="preset-card" draggable="true" data-type="drop" data-bars="16" style="background: linear-gradient(135deg, #ef4444, #dc2626);">
            <div class="preset-label">DROP</div>
            <div class="preset-bars">16 bars</div>
        </div>
        <div class="preset-card" draggable="true" data-type="drop" data-bars="32" style="background: linear-gradient(135deg, #ef4444, #dc2626);">
            <div class="preset-label">DROP</div>
            <div class="preset-bars">32 bars</div>
        </div>
        <div class="preset-card" draggable="true" data-type="drop" data-bars="64" style="background: linear-gradient(135deg, #ef4444, #dc2626);">
            <div class="preset-label">DROP</div>
            <div class="preset-bars">64 bars</div>
        </div>

        <!-- Breakdown variants -->
        <div class="preset-card" draggable="true" data-type="breakdown" data-bars="16" style="background: linear-gradient(135deg, #8b5cf6, #7c3aed);">
            <div class="preset-label">BREAK</div>
            <div class="preset-bars">16 bars</div>
        </div>
        <div class="preset-card" draggable="true" data-type="breakdown" data-bars="32" style="background: linear-gradient(135deg, #8b5cf6, #7c3aed);">
            <div class="preset-label">BREAK</div>
            <div class="preset-bars">32 bars</div>
        </div>
        <div class="preset-card" draggable="true" data-type="breakdown" data-bars="64" style="background: linear-gradient(135deg, #8b5cf6, #7c3aed);">
            <div class="preset-label">BREAK</div>
            <div class="preset-bars">64 bars</div>
        </div>

        <!-- Outro variants -->
        <div class="preset-card" draggable="true" data-type="outro" data-bars="16" style="background: linear-gradient(135deg, #14b8a6, #0d9488);">
            <div class="preset-label">OUTRO</div>
            <div class="preset-bars">16 bars</div>
        </div>
        <div class="preset-card" draggable="true" data-type="outro" data-bars="32" style="background: linear-gradient(135deg, #14b8a6, #0d9488);">
            <div class="preset-label">OUTRO</div>
            <div class="preset-bars">32 bars</div>
        </div>
        <div class="preset-card" draggable="true" data-type="outro" data-bars="64" style="background: linear-gradient(135deg, #14b8a6, #0d9488);">
            <div class="preset-label">OUTRO</div>
            <div class="preset-bars">64 bars</div>
        </div>
    </div>
</div>

<!-- Template Preview -->
<div class="card" style="margin-top: 20px;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
        <h2 class="card-title" style="margin-bottom: 0;">Template Preview</h2>
        <span id="totalDuration" style="color: var(--text-secondary);">Total: --:--</span>
    </div>

    <div id="templateTimeline" style="display: flex; height: 60px; border-radius: 8px; overflow: hidden; margin-bottom: 10px; background: var(--bg-secondary);">
        <div style="display: flex; align-items: center; justify-content: center; width: 100%; color: var(--text-secondary);">
            Select a source and click "Generate Template"
        </div>
    </div>

    <div style="display: flex; justify-content: space-between; color: var(--text-secondary); font-size: 0.85rem;">
        <span>0:00</span>
        <span id="timelineEnd">--:--</span>
    </div>
</div>

<!-- Section Editor -->
<div class="card" style="margin-top: 20px;" id="sectionEditorCard" style="display: none;">
    <h2 class="card-title">Section Editor</h2>

    <div id="sectionList" style="margin-bottom: 15px;">
        <!-- Sections will be rendered here -->
    </div>

    <button class="btn" onclick="addSection()" style="width: 100%;">
        + Add Section
    </button>
</div>

<!-- Actions -->
<div style="display: flex; gap: 15px; margin-top: 20px; flex-wrap: wrap;">
    <button class="btn btn-primary" onclick="sendToAbleton()" id="sendBtn" disabled>
        Send to Ableton
    </button>
    <button class="btn" onclick="saveToLibrary()" id="saveLibraryBtn" disabled style="background: #8b5cf6;">
        Save to Library
    </button>
    <button class="btn" onclick="exportJSON()" id="exportBtn" disabled>
        Export JSON
    </button>
    <button class="btn" onclick="copyLocators()" id="copyBtn" disabled>
        Copy Locator Times
    </button>
</div>

<!-- Save to Library Modal -->
<div id="saveLibraryModal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 1000; justify-content: center; align-items: center;">
    <div class="card" style="max-width: 500px; width: 90%;">
        <h2 class="card-title">Save to Reference Library</h2>

        <div style="margin-bottom: 15px;">
            <label class="settings-label">Name</label>
            <input type="text" id="libraryName" class="settings-input" style="width: 100%;" placeholder="Reference name">
        </div>

        <div style="margin-bottom: 15px;">
            <label class="settings-label">Tags (comma-separated)</label>
            <input type="text" id="libraryTags" class="settings-input" style="width: 100%;" placeholder="trance, uplifting, classic">
        </div>

        <div style="margin-bottom: 20px;">
            <label class="settings-label">Notes (optional)</label>
            <textarea id="libraryNotes" class="settings-input" style="width: 100%; height: 60px;" placeholder="Any notes about this reference..."></textarea>
        </div>

        <div style="display: flex; gap: 10px; justify-content: flex-end;">
            <button class="btn" onclick="closeLibraryModal()">Cancel</button>
            <button class="btn btn-primary" onclick="confirmSaveToLibrary()">Save</button>
        </div>
    </div>
</div>

<!-- Marker Sync Panel -->
<div class="card" style="margin-top: 20px;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
        <h2 class="card-title" style="margin-bottom: 0;">Ableton Marker Sync</h2>
        <button class="btn-small" onclick="refreshSyncStatus()">Refresh</button>
    </div>

    <div id="syncStatus" style="display: flex; align-items: center; gap: 10px; margin-bottom: 20px; padding: 10px; background: var(--bg-secondary); border-radius: 8px;">
        <span class="status-dot" id="syncStatusDot" style="background: var(--text-secondary);"></span>
        <span id="syncStatusText">Checking connection...</span>
    </div>

    <div style="display: grid; grid-template-columns: 1fr auto 1fr; gap: 15px; margin-bottom: 20px;">
        <!-- Ableton Markers Column -->
        <div>
            <h3 style="font-size: 0.9rem; margin-bottom: 10px; color: var(--text-secondary);">ABLETON MARKERS</h3>
            <div id="abletonMarkerList" style="min-height: 100px; background: var(--bg-secondary); border-radius: 8px; padding: 10px;">
                <div style="color: var(--text-secondary); font-size: 0.85rem; text-align: center;">
                    Click Refresh to load
                </div>
            </div>
        </div>

        <!-- Sync Arrows -->
        <div style="display: flex; flex-direction: column; justify-content: center; gap: 10px; padding-top: 30px;">
            <button class="btn sync-btn" onclick="pullFromAbleton()" id="pullBtn" disabled title="Pull markers from Ableton">
                ◀ Pull
            </button>
            <button class="btn sync-btn" onclick="pushToAbleton()" id="pushBtn" disabled title="Push markers to Ableton">
                Push ▶
            </button>
        </div>

        <!-- Dashboard Markers Column -->
        <div>
            <h3 style="font-size: 0.9rem; margin-bottom: 10px; color: var(--text-secondary);">DASHBOARD SECTIONS</h3>
            <div id="dashboardMarkerList" style="min-height: 100px; background: var(--bg-secondary); border-radius: 8px; padding: 10px;">
                <div style="color: var(--text-secondary); font-size: 0.85rem; text-align: center;">
                    Generate a template first
                </div>
            </div>
        </div>
    </div>

    <div id="syncFeedback" style="display: none; padding: 10px; border-radius: 8px; margin-top: 10px;"></div>
</div>

<!-- Manual Instructions (shown if Ableton can't receive locators) -->
<div id="manualInstructions" class="card" style="margin-top: 20px; display: none;">
    <h2 class="card-title" style="color: var(--warning);">Manual Locator Setup</h2>
    <p style="margin-bottom: 15px; color: var(--text-secondary);">
        Locators couldn't be added automatically. Add them manually in Ableton:
    </p>
    <div id="locatorList" style="font-family: monospace; background: var(--bg-secondary); padding: 15px; border-radius: 8px;">
    </div>
</div>

<style>
.section-row {
    display: flex;
    align-items: center;
    gap: 15px;
    padding: 12px;
    background: var(--bg-secondary);
    border-radius: 8px;
    margin-bottom: 8px;
}

.section-row:hover {
    background: var(--bg-primary);
}

.section-drag {
    cursor: grab;
    color: var(--text-secondary);
    font-size: 1.2rem;
}

.section-type {
    min-width: 100px;
    padding: 4px 12px;
    border-radius: 4px;
    text-transform: uppercase;
    font-weight: bold;
    font-size: 0.8rem;
    color: white;
    text-align: center;
}

.section-bars {
    display: flex;
    align-items: center;
    gap: 8px;
}

.section-bars input {
    width: 60px;
    text-align: center;
}

.section-time {
    color: var(--text-secondary);
    font-size: 0.9rem;
    min-width: 120px;
}

.section-delete {
    color: var(--error);
    cursor: pointer;
    font-size: 1.2rem;
    opacity: 0.6;
}

.section-delete:hover {
    opacity: 1;
}

.btn-small {
    padding: 4px 8px;
    font-size: 0.8rem;
    border-radius: 4px;
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    color: var(--text-primary);
    cursor: pointer;
}

.btn-small:hover {
    background: var(--border-color);
}

.timeline-section {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    color: white;
    font-size: 0.7rem;
    text-shadow: 0 1px 2px rgba(0,0,0,0.5);
    min-width: 40px;
}

.timeline-section .label {
    font-weight: bold;
    text-transform: uppercase;
}

.timeline-section .bars {
    font-size: 0.65rem;
    opacity: 0.9;
}

.status-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
}

/* Preset Cards */
.preset-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 80px;
    height: 60px;
    border-radius: 8px;
    cursor: grab;
    color: white;
    text-shadow: 0 1px 2px rgba(0,0,0,0.3);
    transition: transform 0.15s, box-shadow 0.15s;
    user-select: none;
}

.preset-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}

.preset-card:active {
    cursor: grabbing;
}

.preset-card.dragging {
    opacity: 0.5;
    transform: scale(0.95);
}

.preset-label {
    font-weight: bold;
    font-size: 0.75rem;
}

.preset-bars {
    font-size: 0.65rem;
    opacity: 0.9;
}

/* Drop zones for timeline */
.drop-zone {
    position: absolute;
    width: 4px;
    height: 100%;
    background: transparent;
    transition: all 0.2s;
    z-index: 10;
}

.drop-zone.active {
    background: var(--accent);
    width: 6px;
    box-shadow: 0 0 10px var(--accent);
}

.drop-zone-indicator {
    position: absolute;
    top: -8px;
    left: 50%;
    transform: translateX(-50%);
    width: 0;
    height: 0;
    border-left: 6px solid transparent;
    border-right: 6px solid transparent;
    border-top: 8px solid var(--accent);
    opacity: 0;
    transition: opacity 0.2s;
}

.drop-zone.active .drop-zone-indicator {
    opacity: 1;
}

/* Timeline drop highlight */
#templateTimeline.drag-over {
    outline: 2px dashed var(--accent);
    outline-offset: 2px;
}

/* Section list drop zones */
.section-row.drop-target-above {
    border-top: 3px solid var(--accent);
    margin-top: -3px;
}

.section-row.drop-target-below {
    border-bottom: 3px solid var(--accent);
    margin-bottom: -3px;
}

/* Sync Panel Styles */
.sync-btn {
    padding: 8px 12px;
    font-size: 0.85rem;
    min-width: 70px;
}

.sync-marker {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    background: var(--bg-primary);
    border-radius: 4px;
    margin-bottom: 6px;
    font-size: 0.85rem;
}

.sync-marker .marker-name {
    flex: 1;
    font-weight: 500;
}

.sync-marker .marker-time {
    color: var(--text-secondary);
    font-size: 0.8rem;
}

.sync-marker .marker-color {
    width: 8px;
    height: 8px;
    border-radius: 50%;
}

.sync-marker.match {
    border-left: 3px solid var(--success);
}

.sync-marker.different {
    border-left: 3px solid var(--warning);
}

.sync-marker.missing {
    border-left: 3px solid var(--error);
    opacity: 0.7;
}
</style>

<script>
const SECTION_COLORS = {
    'intro': '#3b82f6',
    'buildup': '#f97316',
    'drop': '#ef4444',
    'breakdown': '#8b5cf6',
    'outro': '#14b8a6',
    'unknown': '#6b7280'
};

let currentTemplate = null;
let abletonConnected = false;

function toggleSource() {
    const isPreset = document.querySelector('input[name="source"][value="preset"]').checked;
    document.getElementById('presetSelect').disabled = !isPreset;
    document.getElementById('referenceSelect').disabled = isPreset;
}

function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return mins + ':' + secs.toString().padStart(2, '0');
}

async function generateTemplate() {
    const isPreset = document.querySelector('input[name="source"][value="preset"]').checked;
    const bpm = parseFloat(document.getElementById('bpmInput').value) || 138;

    let body;
    if (isPreset) {
        const preset = document.getElementById('presetSelect').value;
        body = JSON.stringify({ source: 'preset', preset: preset, bpm: bpm });
    } else {
        const reference = document.getElementById('referenceSelect').value;
        if (!reference) {
            alert('Please select a reference audio file');
            return;
        }
        body = JSON.stringify({ source: 'reference', audio_path: reference, bpm: bpm });
    }

    try {
        const response = await fetch('/api/templates/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: body
        });

        const data = await response.json();
        if (data.error) {
            alert('Error: ' + data.error);
            return;
        }

        currentTemplate = data;
        renderTemplate();

        // Enable action buttons
        document.getElementById('sendBtn').disabled = false;
        document.getElementById('saveLibraryBtn').disabled = false;
        document.getElementById('exportBtn').disabled = false;
        document.getElementById('copyBtn').disabled = false;

    } catch (error) {
        alert('Error generating template: ' + error.message);
    }
}

function loadPreset() {
    // Auto-generate when preset changes
    generateTemplate();
}

function renderTemplate() {
    if (!currentTemplate) return;

    // Update timeline
    const timeline = document.getElementById('templateTimeline');
    timeline.innerHTML = '';

    const totalDuration = currentTemplate.total_duration;

    currentTemplate.sections.forEach((section, index) => {
        const widthPct = (section.duration / totalDuration) * 100;
        const color = SECTION_COLORS[section.section_type] || SECTION_COLORS['unknown'];

        const div = document.createElement('div');
        div.className = 'timeline-section';
        div.style.width = widthPct + '%';
        div.style.background = color;
        div.innerHTML = '<span class="label">' + section.section_type.substring(0, 4).toUpperCase() + '</span>' +
                       '<span class="bars">' + section.bars + 'b</span>';
        div.title = section.section_type + ': ' + section.time_range;
        timeline.appendChild(div);
    });

    // Update totals
    document.getElementById('totalDuration').textContent = 'Total: ' + currentTemplate.total_duration_formatted;
    document.getElementById('timelineEnd').textContent = currentTemplate.total_duration_formatted;

    // Render section editor
    renderSectionEditor();
}

function renderSectionEditor() {
    const list = document.getElementById('sectionList');
    list.innerHTML = '';

    currentTemplate.sections.forEach((section, index) => {
        const color = SECTION_COLORS[section.section_type] || SECTION_COLORS['unknown'];

        const row = document.createElement('div');
        row.className = 'section-row';
        row.dataset.index = index;
        row.innerHTML = `
            <span class="section-drag">≡</span>
            <span class="section-type" style="background: ${color}">${section.section_type}</span>
            <div class="section-bars">
                <button class="btn-small" onclick="adjustSection(${index}, -8)">-8</button>
                <input type="number" value="${section.bars}" min="8" step="8" onchange="setSectionBars(${index}, this.value)">
                <button class="btn-small" onclick="adjustSection(${index}, 8)">+8</button>
                <span>bars</span>
            </div>
            <span class="section-time">${section.time_range}</span>
            <span class="section-delete" onclick="removeSection(${index})">×</span>
        `;
        list.appendChild(row);
    });
}

async function adjustSection(index, delta) {
    const sections = currentTemplate.sections.map(s => ({
        section_type: s.section_type,
        bars: s.bars
    }));

    sections[index].bars = Math.max(8, sections[index].bars + delta);

    await updateTemplate(sections);
}

async function setSectionBars(index, bars) {
    const sections = currentTemplate.sections.map(s => ({
        section_type: s.section_type,
        bars: s.bars
    }));

    sections[index].bars = Math.max(8, Math.round(parseInt(bars) / 8) * 8);

    await updateTemplate(sections);
}

async function removeSection(index) {
    const sections = currentTemplate.sections.map(s => ({
        section_type: s.section_type,
        bars: s.bars
    }));

    sections.splice(index, 1);

    await updateTemplate(sections);
}

async function addSection() {
    const sections = currentTemplate.sections.map(s => ({
        section_type: s.section_type,
        bars: s.bars
    }));

    // Add a new section (default: 32-bar breakdown)
    sections.push({ section_type: 'breakdown', bars: 32 });

    await updateTemplate(sections);
}

async function updateTemplate(sections) {
    const bpm = parseFloat(document.getElementById('bpmInput').value) || 138;

    try {
        const response = await fetch('/api/templates/customize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                template: currentTemplate,
                bpm: bpm,
                sections: sections
            })
        });

        const data = await response.json();
        if (data.error) {
            alert('Error: ' + data.error);
            return;
        }

        currentTemplate = data;
        renderTemplate();

    } catch (error) {
        alert('Error updating template: ' + error.message);
    }
}

function updateTimings() {
    if (currentTemplate) {
        const bpm = parseFloat(document.getElementById('bpmInput').value) || 138;
        currentTemplate.bpm = bpm;
        // Re-fetch to recalculate timings
        updateTemplate(currentTemplate.sections.map(s => ({
            section_type: s.section_type,
            bars: s.bars
        })));
    }
}

async function checkAbletonConnection() {
    try {
        const response = await fetch('/api/templates/ableton-status');
        const data = await response.json();

        const statusDiv = document.getElementById('abletonStatus');
        if (data.connected) {
            abletonConnected = true;
            statusDiv.innerHTML = '<span class="status-dot" style="background: var(--success);"></span>' +
                                 '<span>Connected - ' + data.tempo + ' BPM</span>';
        } else {
            abletonConnected = false;
            statusDiv.innerHTML = '<span class="status-dot" style="background: var(--error);"></span>' +
                                 '<span>' + (data.error || 'Not connected') + '</span>';
        }
    } catch (error) {
        document.getElementById('abletonStatus').innerHTML =
            '<span class="status-dot" style="background: var(--error);"></span>' +
            '<span>Error checking connection</span>';
    }
}

async function sendToAbleton() {
    if (!currentTemplate) return;

    try {
        const response = await fetch('/api/templates/send-to-ableton', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ template: currentTemplate })
        });

        const data = await response.json();

        if (data.success) {
            alert('Template sent to Ableton!\n' + data.message);
        } else {
            // Show manual instructions
            if (data.manual_locators && data.manual_locators.length > 0) {
                showManualInstructions(data.manual_locators);
            }
            alert(data.message || 'Failed to send to Ableton');
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

function showManualInstructions(locators) {
    const div = document.getElementById('manualInstructions');
    const list = document.getElementById('locatorList');

    div.style.display = 'block';

    list.innerHTML = locators.map(loc =>
        `${loc.name.padEnd(12)} @ ${formatTime(loc.time_seconds)} (bar ${Math.floor(loc.time_beats / 4)})`
    ).join('\\n');
}

function exportJSON() {
    if (!currentTemplate) return;

    const blob = new Blob([JSON.stringify(currentTemplate, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = currentTemplate.name.replace(/[^a-z0-9]/gi, '_') + '_template.json';
    a.click();
    URL.revokeObjectURL(url);
}

function copyLocators() {
    if (!currentTemplate) return;

    const text = currentTemplate.locators.map(loc =>
        `${loc.name}: ${formatTime(loc.time_seconds)} (bar ${Math.floor(loc.time_beats / 4)})`
    ).join('\\n');

    navigator.clipboard.writeText(text).then(() => {
        alert('Locator times copied to clipboard!');
    });
}

// ========================================
// Drag and Drop for Section Presets
// ========================================

let draggedPreset = null;

function initDragAndDrop() {
    // Setup drag events on preset cards
    document.querySelectorAll('.preset-card').forEach(card => {
        card.addEventListener('dragstart', handleDragStart);
        card.addEventListener('dragend', handleDragEnd);
    });

    // Setup drop zones on timeline
    const timeline = document.getElementById('templateTimeline');
    timeline.addEventListener('dragover', handleTimelineDragOver);
    timeline.addEventListener('dragleave', handleTimelineDragLeave);
    timeline.addEventListener('drop', handleTimelineDrop);

    // Setup drop zones on section list
    const sectionList = document.getElementById('sectionList');
    sectionList.addEventListener('dragover', handleSectionListDragOver);
    sectionList.addEventListener('dragleave', handleSectionListDragLeave);
    sectionList.addEventListener('drop', handleSectionListDrop);
}

function handleDragStart(e) {
    draggedPreset = {
        type: e.target.dataset.type,
        bars: parseInt(e.target.dataset.bars)
    };
    e.target.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'copy';
    e.dataTransfer.setData('text/plain', JSON.stringify(draggedPreset));
}

function handleDragEnd(e) {
    e.target.classList.remove('dragging');
    draggedPreset = null;
    clearAllDropIndicators();
}

function handleTimelineDragOver(e) {
    if (!draggedPreset) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    e.currentTarget.classList.add('drag-over');
}

function handleTimelineDragLeave(e) {
    e.currentTarget.classList.remove('drag-over');
}

function handleTimelineDrop(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-over');

    if (!draggedPreset || !currentTemplate) return;

    // Calculate drop position based on mouse X within timeline
    const timeline = e.currentTarget;
    const rect = timeline.getBoundingClientRect();
    const dropX = e.clientX - rect.left;
    const dropPercent = dropX / rect.width;

    // Find insert index based on drop position
    let insertIndex = 0;
    let accumulatedPercent = 0;

    for (let i = 0; i < currentTemplate.sections.length; i++) {
        const sectionPercent = currentTemplate.sections[i].duration / currentTemplate.total_duration;
        if (dropPercent < accumulatedPercent + sectionPercent / 2) {
            insertIndex = i;
            break;
        }
        accumulatedPercent += sectionPercent;
        insertIndex = i + 1;
    }

    insertSection(draggedPreset.type, draggedPreset.bars, insertIndex);
}

function handleSectionListDragOver(e) {
    if (!draggedPreset) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';

    // Find the section row we're hovering over
    const sectionRow = e.target.closest('.section-row');
    if (sectionRow) {
        clearAllDropIndicators();
        const rect = sectionRow.getBoundingClientRect();
        const midY = rect.top + rect.height / 2;

        if (e.clientY < midY) {
            sectionRow.classList.add('drop-target-above');
        } else {
            sectionRow.classList.add('drop-target-below');
        }
    }
}

function handleSectionListDragLeave(e) {
    // Only clear if leaving the section list entirely
    if (!e.currentTarget.contains(e.relatedTarget)) {
        clearAllDropIndicators();
    }
}

function handleSectionListDrop(e) {
    e.preventDefault();

    if (!draggedPreset || !currentTemplate) return;

    // Find insert index based on drop target
    const sectionRow = e.target.closest('.section-row');
    let insertIndex = currentTemplate.sections.length; // Default to end

    if (sectionRow) {
        const sectionIndex = parseInt(sectionRow.dataset.index);
        const rect = sectionRow.getBoundingClientRect();
        const midY = rect.top + rect.height / 2;

        if (e.clientY < midY) {
            insertIndex = sectionIndex;
        } else {
            insertIndex = sectionIndex + 1;
        }
    }

    clearAllDropIndicators();
    insertSection(draggedPreset.type, draggedPreset.bars, insertIndex);
}

function clearAllDropIndicators() {
    document.querySelectorAll('.drop-target-above, .drop-target-below').forEach(el => {
        el.classList.remove('drop-target-above', 'drop-target-below');
    });
    document.getElementById('templateTimeline').classList.remove('drag-over');
}

function insertSection(type, bars, index) {
    if (!currentTemplate) return;

    // Create new section
    const newSection = {
        section_type: type,
        bars: bars
    };

    // Build new sections array with insertion
    const sections = currentTemplate.sections.map(s => ({
        section_type: s.section_type,
        bars: s.bars
    }));

    sections.splice(index, 0, newSection);

    // Call customize API to update
    updateTemplate(sections);
}

// ========================================
// Save to Library Functions
// ========================================

function saveToLibrary() {
    if (!currentTemplate) return;

    // Pre-fill the name from the template
    document.getElementById('libraryName').value = currentTemplate.name || '';
    document.getElementById('libraryTags').value = '';
    document.getElementById('libraryNotes').value = '';

    // Show modal
    document.getElementById('saveLibraryModal').style.display = 'flex';
}

function closeLibraryModal() {
    document.getElementById('saveLibraryModal').style.display = 'none';
}

async function confirmSaveToLibrary() {
    if (!currentTemplate) return;

    const name = document.getElementById('libraryName').value.trim() || currentTemplate.name;
    const tagsStr = document.getElementById('libraryTags').value.trim();
    const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(t => t) : [];
    const notes = document.getElementById('libraryNotes').value.trim();

    try {
        const response = await fetch('/api/library/references', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                template: currentTemplate,
                name: name,
                tags: tags,
                notes: notes
            })
        });

        const data = await response.json();

        if (data.error) {
            alert('Error saving to library: ' + data.error);
            return;
        }

        closeLibraryModal();
        alert('Saved to library: ' + name);

    } catch (err) {
        alert('Error saving to library: ' + err.message);
    }
}

// Close modal on escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeLibraryModal();
    }
});

// Close modal on background click
document.getElementById('saveLibraryModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'saveLibraryModal') {
        closeLibraryModal();
    }
});

// Initialize
document.getElementById('bpmInput').addEventListener('change', updateTimings);

// ========================================
// Marker Sync Functions
// ========================================

async function refreshSyncStatus() {
    const statusDot = document.getElementById('syncStatusDot');
    const statusText = document.getElementById('syncStatusText');
    const pullBtn = document.getElementById('pullBtn');
    const pushBtn = document.getElementById('pushBtn');

    statusText.textContent = 'Checking connection...';
    statusDot.style.background = 'var(--text-secondary)';

    try {
        const response = await fetch('/api/sync/status');
        const status = await response.json();

        if (status.connected) {
            statusDot.style.background = 'var(--success)';
            statusText.textContent = `Connected (${status.tempo} BPM) - ${status.ableton_marker_count} markers`;
            pullBtn.disabled = false;
            pushBtn.disabled = !currentTemplate;

            // Update Ableton markers list
            renderAbletonMarkers(status.ableton_markers || []);
        } else {
            statusDot.style.background = 'var(--error)';
            statusText.textContent = status.error || 'Not connected';
            pullBtn.disabled = true;
            pushBtn.disabled = true;
            renderAbletonMarkers([]);
        }

        // Update dashboard markers list
        renderDashboardMarkers();

    } catch (err) {
        statusDot.style.background = 'var(--error)';
        statusText.textContent = 'Error: ' + err.message;
        pullBtn.disabled = true;
        pushBtn.disabled = true;
    }
}

function renderAbletonMarkers(markers) {
    const container = document.getElementById('abletonMarkerList');

    if (!markers || markers.length === 0) {
        container.innerHTML = '<div style="color: var(--text-secondary); font-size: 0.85rem; text-align: center;">No markers found</div>';
        return;
    }

    container.innerHTML = markers.map(m => {
        const time = formatTime((m.time_beats / (currentTemplate?.bpm || 138)) * 60);
        return `<div class="sync-marker">
            <span class="marker-color" style="background: var(--accent);"></span>
            <span class="marker-name">${m.name}</span>
            <span class="marker-time">${time}</span>
        </div>`;
    }).join('');
}

function renderDashboardMarkers() {
    const container = document.getElementById('dashboardMarkerList');

    if (!currentTemplate || !currentTemplate.locators || currentTemplate.locators.length === 0) {
        container.innerHTML = '<div style="color: var(--text-secondary); font-size: 0.85rem; text-align: center;">Generate a template first</div>';
        return;
    }

    container.innerHTML = currentTemplate.locators.map(loc => {
        const color = SECTION_COLORS[loc.name.toLowerCase().replace(/[^a-z]/g, '')] || 'var(--accent)';
        return `<div class="sync-marker">
            <span class="marker-color" style="background: ${color};"></span>
            <span class="marker-name">${loc.name}</span>
            <span class="marker-time">${loc.time_formatted}</span>
        </div>`;
    }).join('');
}

async function pullFromAbleton() {
    showSyncFeedback('Pulling markers from Ableton...', 'info');

    try {
        const response = await fetch('/api/sync/pull');
        const result = await response.json();

        if (result.success && result.markers && result.markers.length > 0) {
            // Convert pulled markers to template sections
            const bpm = currentTemplate?.bpm || 138;

            // Sort by time
            const sortedMarkers = result.markers.sort((a, b) => a.time_beats - b.time_beats);

            // Create sections from markers
            const sections = [];
            for (let i = 0; i < sortedMarkers.length; i++) {
                const marker = sortedMarkers[i];
                const nextMarker = sortedMarkers[i + 1];

                const startBeat = marker.time_beats;
                const endBeat = nextMarker ? nextMarker.time_beats : startBeat + 32 * 4; // Default 32 bars

                const bars = Math.round((endBeat - startBeat) / 4);
                const sectionType = detectSectionType(marker.name);

                sections.push({
                    section_type: sectionType,
                    bars: bars,
                    position_bars: Math.round(startBeat / 4),
                    duration: (bars * 4 / bpm) * 60
                });
            }

            if (sections.length > 0) {
                // Update current template
                currentTemplate = currentTemplate || { name: 'Imported from Ableton', bpm: bpm };
                currentTemplate.sections = sections;
                currentTemplate.locators = sortedMarkers.map(m => ({
                    name: m.name,
                    time_beats: m.time_beats,
                    time_formatted: formatTime((m.time_beats / bpm) * 60)
                }));

                // Recalculate total duration
                const lastSection = sections[sections.length - 1];
                currentTemplate.total_duration = ((lastSection.position_bars + lastSection.bars) * 4 / bpm) * 60;

                renderTemplate();
                showSyncFeedback(`Pulled ${result.markers.length} markers from Ableton`, 'success');

                // Enable buttons
                document.getElementById('sendBtn').disabled = false;
                document.getElementById('saveLibraryBtn').disabled = false;
                document.getElementById('exportBtn').disabled = false;
                document.getElementById('copyBtn').disabled = false;
            }
        } else {
            showSyncFeedback(result.message || 'No markers found', 'warning');
        }

        refreshSyncStatus();

    } catch (err) {
        showSyncFeedback('Error pulling markers: ' + err.message, 'error');
    }
}

function detectSectionType(name) {
    const nameLower = name.toLowerCase();
    if (nameLower.includes('intro')) return 'intro';
    if (nameLower.includes('build')) return 'buildup';
    if (nameLower.includes('drop') || nameLower.includes('main')) return 'drop';
    if (nameLower.includes('break') || nameLower.includes('down')) return 'breakdown';
    if (nameLower.includes('outro') || nameLower.includes('end')) return 'outro';
    return 'unknown';
}

async function pushToAbleton() {
    if (!currentTemplate || !currentTemplate.locators) {
        showSyncFeedback('No template to push', 'warning');
        return;
    }

    showSyncFeedback('Pushing markers to Ableton...', 'info');

    try {
        const markers = currentTemplate.locators.map(loc => ({
            name: loc.name,
            time_beats: loc.time_beats
        }));

        const response = await fetch('/api/sync/push', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ markers: markers, clear_first: true })
        });

        const result = await response.json();

        if (result.success) {
            showSyncFeedback(result.message || `Pushed ${result.added} markers`, 'success');
        } else {
            showSyncFeedback(result.message || 'Push failed', 'error');
        }

        refreshSyncStatus();

    } catch (err) {
        showSyncFeedback('Error pushing markers: ' + err.message, 'error');
    }
}

function showSyncFeedback(message, type) {
    const feedback = document.getElementById('syncFeedback');
    feedback.style.display = 'block';
    feedback.textContent = message;

    const colors = {
        'info': { bg: 'var(--bg-secondary)', color: 'var(--text-primary)' },
        'success': { bg: 'rgba(34, 197, 94, 0.2)', color: 'var(--success)' },
        'warning': { bg: 'rgba(245, 158, 11, 0.2)', color: 'var(--warning)' },
        'error': { bg: 'rgba(239, 68, 68, 0.2)', color: 'var(--error)' }
    };

    const style = colors[type] || colors['info'];
    feedback.style.background = style.bg;
    feedback.style.color = style.color;

    // Auto-hide after 5 seconds for success messages
    if (type === 'success') {
        setTimeout(() => {
            feedback.style.display = 'none';
        }, 5000);
    }
}

// Auto-load first preset on page load
window.addEventListener('load', () => {
    initDragAndDrop();
    generateTemplate();
    // Check sync status on load
    setTimeout(refreshSyncStatus, 500);
});
</script>
"""


# ============================================================================
# Reference Overlay Content
# ============================================================================

COMPARE_OVERLAY_CONTENT = """
<div class="card" style="margin-bottom: 24px;">
    <h2 style="margin: 0 0 8px 0; font-size: 1.5rem;">Reference Overlay Comparison</h2>
    <p style="margin: 0; color: var(--text-secondary);">Compare your track's structure against a reference to see how sections align.</p>
</div>

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px;">
    <!-- User Track Source -->
    <div class="card">
        <h3 style="margin: 0 0 16px 0; color: var(--accent);">Your Track</h3>

        <div style="margin-bottom: 16px;">
            <label style="display: block; margin-bottom: 8px;">Source:</label>
            <select id="userSource" onchange="updateUserSource()" style="width: 100%; padding: 8px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 4px; color: var(--text-primary);">
                <option value="audio">Audio File</option>
                <option value="preset">Genre Preset</option>
            </select>
        </div>

        <div id="userAudioSection">
            <label style="display: block; margin-bottom: 8px;">Select Audio File:</label>
            <select id="userAudioFile" style="width: 100%; padding: 8px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 4px; color: var(--text-primary);">
                {% for file in audio_files %}
                <option value="{{ file.path }}">{{ file.name }}</option>
                {% endfor %}
                {% if not audio_files %}
                <option value="">No audio files found</option>
                {% endif %}
            </select>
        </div>

        <div id="userPresetSection" style="display: none;">
            <label style="display: block; margin-bottom: 8px;">Preset:</label>
            <select id="userPreset" style="width: 100%; padding: 8px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 4px; color: var(--text-primary);">
                {% for preset in presets %}
                <option value="{{ preset.id }}">{{ preset.name }}</option>
                {% endfor %}
            </select>

            <label style="display: block; margin: 16px 0 8px 0;">BPM:</label>
            <input type="number" id="userBpm" value="138" min="60" max="200" style="width: 100%; padding: 8px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 4px; color: var(--text-primary);">
        </div>
    </div>

    <!-- Reference Track Source -->
    <div class="card">
        <h3 style="margin: 0 0 16px 0; color: #a855f7;">Reference Track</h3>

        <div style="margin-bottom: 16px;">
            <label style="display: block; margin-bottom: 8px;">Source:</label>
            <select id="refSource" onchange="updateRefSource()" style="width: 100%; padding: 8px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 4px; color: var(--text-primary);">
                <option value="library">From Library (instant)</option>
                <option value="audio">Audio File</option>
                <option value="preset">Genre Preset</option>
            </select>
        </div>

        <div id="refLibrarySection">
            <label style="display: block; margin-bottom: 8px;">Select Reference:</label>
            <select id="refLibrary" style="width: 100%; padding: 8px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 4px; color: var(--text-primary);">
                <option value="">Loading library...</option>
            </select>
            <div id="refLibraryPreview" style="margin-top: 12px; padding: 12px; background: var(--bg-primary); border-radius: 8px; display: none;">
                <div id="refLibraryInfo" style="font-size: 0.9rem; color: var(--text-secondary);"></div>
            </div>
        </div>

        <div id="refAudioSection" style="display: none;">
            <label style="display: block; margin-bottom: 8px;">Select Audio File:</label>
            <select id="refAudioFile" style="width: 100%; padding: 8px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 4px; color: var(--text-primary);">
                {% for file in audio_files %}
                <option value="{{ file.path }}">{{ file.name }}</option>
                {% endfor %}
                {% if not audio_files %}
                <option value="">No audio files found</option>
                {% endif %}
            </select>
        </div>

        <div id="refPresetSection" style="display: none;">
            <label style="display: block; margin-bottom: 8px;">Preset:</label>
            <select id="refPreset" style="width: 100%; padding: 8px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 4px; color: var(--text-primary);">
                {% for preset in presets %}
                <option value="{{ preset.id }}">{{ preset.name }}</option>
                {% endfor %}
            </select>

            <label style="display: block; margin: 16px 0 8px 0;">BPM:</label>
            <input type="number" id="refBpm" value="138" min="60" max="200" style="width: 100%; padding: 8px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 4px; color: var(--text-primary);">
        </div>
    </div>
</div>

<div class="card" style="margin-bottom: 24px; text-align: center;">
    <button onclick="runComparison()" class="btn btn-primary" style="padding: 12px 32px; font-size: 1.1rem;">
        Compare Structures
    </button>
    <span id="loadingIndicator" style="display: none; margin-left: 16px; color: var(--text-secondary);">
        Analyzing... (this may take a moment)
    </span>
</div>

<!-- Results Section (hidden until comparison runs) -->
<div id="resultsSection" style="display: none;">
    <!-- Alignment Score -->
    <div class="card" style="margin-bottom: 24px; text-align: center;">
        <h3 style="margin: 0 0 16px 0;">Overall Alignment Score</h3>
        <div id="alignmentScore" style="font-size: 3rem; font-weight: bold; color: var(--accent);">--</div>
        <div id="alignmentLabel" style="color: var(--text-secondary); font-size: 1.1rem;">--</div>
    </div>

    <!-- Timeline Comparison -->
    <div class="card" style="margin-bottom: 24px;">
        <h3 style="margin: 0 0 16px 0;">Structure Comparison</h3>

        <div style="margin-bottom: 24px;">
            <div style="display: flex; align-items: center; margin-bottom: 8px;">
                <div style="width: 120px; font-weight: bold; color: var(--accent);">Your Track:</div>
                <div id="userTrackName" style="color: var(--text-secondary);">--</div>
            </div>
            <div id="userTimeline" class="timeline-container" style="background: var(--bg-primary); border-radius: 8px; height: 50px; position: relative; overflow: hidden;"></div>
        </div>

        <!-- Alignment Markers -->
        <div id="alignmentMarkers" style="position: relative; height: 40px; margin-bottom: 24px;">
            <!-- Connection lines drawn via JS -->
        </div>

        <div>
            <div style="display: flex; align-items: center; margin-bottom: 8px;">
                <div style="width: 120px; font-weight: bold; color: #a855f7;">Reference:</div>
                <div id="refTrackName" style="color: var(--text-secondary);">--</div>
            </div>
            <div id="refTimeline" class="timeline-container" style="background: var(--bg-primary); border-radius: 8px; height: 50px; position: relative; overflow: hidden;"></div>
        </div>

        <!-- Time axis -->
        <div id="timeAxis" style="display: flex; justify-content: space-between; margin-top: 8px; color: var(--text-secondary); font-size: 0.85rem;"></div>
    </div>

    <!-- Section Alignments -->
    <div class="card" style="margin-bottom: 24px;">
        <h3 style="margin: 0 0 16px 0;">Section Alignment Details</h3>
        <div id="alignmentDetails" style="max-height: 400px; overflow-y: auto;"></div>
    </div>

    <!-- Insights -->
    <div class="card" style="margin-bottom: 24px;">
        <h3 style="margin: 0 0 16px 0;">Insights & Recommendations</h3>
        <div id="insightsList"></div>
    </div>

    <!-- Legend -->
    <div class="card">
        <h4 style="margin: 0 0 12px 0;">Legend</h4>
        <div style="display: flex; flex-wrap: wrap; gap: 16px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="display: inline-block; width: 16px; height: 16px; background: #3b82f6; border-radius: 2px;"></span>
                <span>Intro</span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="display: inline-block; width: 16px; height: 16px; background: #f97316; border-radius: 2px;"></span>
                <span>Buildup</span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="display: inline-block; width: 16px; height: 16px; background: #ef4444; border-radius: 2px;"></span>
                <span>Drop</span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="display: inline-block; width: 16px; height: 16px; background: #8b5cf6; border-radius: 2px;"></span>
                <span>Breakdown</span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="display: inline-block; width: 16px; height: 16px; background: #14b8a6; border-radius: 2px;"></span>
                <span>Outro</span>
            </div>
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 16px; margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border);">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="display: inline-block; width: 16px; height: 16px; background: #22c55e; border-radius: 50%;"></span>
                <span>Aligned</span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="display: inline-block; width: 16px; height: 16px; background: #eab308; border-radius: 50%;"></span>
                <span>Early/Late</span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="display: inline-block; width: 16px; height: 16px; background: #ef4444; border-radius: 50%;"></span>
                <span>Missing</span>
            </div>
        </div>
    </div>
</div>

<style>
.timeline-section {
    position: absolute;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: bold;
    color: white;
    text-shadow: 0 1px 2px rgba(0,0,0,0.5);
    box-sizing: border-box;
    border-right: 1px solid rgba(255,255,255,0.3);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    padding: 0 4px;
}

.alignment-row {
    display: flex;
    align-items: center;
    padding: 12px;
    border-radius: 8px;
    margin-bottom: 8px;
    background: var(--bg-primary);
}

.alignment-row.aligned {
    border-left: 4px solid #22c55e;
}

.alignment-row.early, .alignment-row.late {
    border-left: 4px solid #eab308;
}

.alignment-row.missing_user, .alignment-row.missing_ref {
    border-left: 4px solid #ef4444;
}

.insight-item {
    padding: 12px;
    border-radius: 8px;
    margin-bottom: 8px;
    background: var(--bg-primary);
    border-left: 4px solid var(--accent);
}

.insight-item.warning {
    border-left-color: #eab308;
}

.insight-item.error {
    border-left-color: #ef4444;
}

.insight-item.success {
    border-left-color: #22c55e;
}
</style>

<script>
const SECTION_COLORS = {
    'intro': '#3b82f6',
    'buildup': '#f97316',
    'drop': '#ef4444',
    'breakdown': '#8b5cf6',
    'outro': '#14b8a6'
};

let comparisonResult = null;

function updateUserSource() {
    const source = document.getElementById('userSource').value;
    document.getElementById('userAudioSection').style.display = source === 'audio' ? 'block' : 'none';
    document.getElementById('userPresetSection').style.display = source === 'preset' ? 'block' : 'none';
}

function updateRefSource() {
    const source = document.getElementById('refSource').value;
    document.getElementById('refLibrarySection').style.display = source === 'library' ? 'block' : 'none';
    document.getElementById('refAudioSection').style.display = source === 'audio' ? 'block' : 'none';
    document.getElementById('refPresetSection').style.display = source === 'preset' ? 'block' : 'none';
}

let libraryReferences = [];

async function loadLibraryReferences() {
    try {
        const response = await fetch('/api/library/references');
        const data = await response.json();

        libraryReferences = data.references || [];

        const select = document.getElementById('refLibrary');
        select.innerHTML = '';

        if (libraryReferences.length === 0) {
            select.innerHTML = '<option value="">No references saved yet</option>';
        } else {
            libraryReferences.forEach(ref => {
                const option = document.createElement('option');
                option.value = ref.id;
                option.textContent = `${ref.name} (${ref.bpm} BPM, ${ref.total_duration_formatted})`;
                select.appendChild(option);
            });

            // Show preview for first item
            updateLibraryPreview();
        }
    } catch (err) {
        console.error('Failed to load library:', err);
        document.getElementById('refLibrary').innerHTML = '<option value="">Error loading library</option>';
    }
}

function updateLibraryPreview() {
    const refId = document.getElementById('refLibrary').value;
    const previewDiv = document.getElementById('refLibraryPreview');
    const infoDiv = document.getElementById('refLibraryInfo');

    const ref = libraryReferences.find(r => r.id === refId);
    if (ref) {
        previewDiv.style.display = 'block';
        infoDiv.innerHTML = `
            <div><strong>${ref.section_count} sections:</strong> ${ref.section_summary}</div>
            ${ref.tags && ref.tags.length > 0 ? `<div style="margin-top: 4px;">Tags: ${ref.tags.join(', ')}</div>` : ''}
            ${ref.notes ? `<div style="margin-top: 4px; font-style: italic;">${ref.notes}</div>` : ''}
        `;
    } else {
        previewDiv.style.display = 'none';
    }
}

// Add event listener for library selection
document.addEventListener('DOMContentLoaded', () => {
    loadLibraryReferences();
    const refLibrarySelect = document.getElementById('refLibrary');
    if (refLibrarySelect) {
        refLibrarySelect.addEventListener('change', updateLibraryPreview);
    }
});

async function runComparison() {
    const userSource = document.getElementById('userSource').value;
    const refSource = document.getElementById('refSource').value;

    const payload = {
        user_source: userSource,
        ref_source: refSource
    };

    if (userSource === 'audio') {
        payload.user_path = document.getElementById('userAudioFile').value;
        if (!payload.user_path) {
            alert('Please select a user audio file');
            return;
        }
    } else {
        payload.user_preset = document.getElementById('userPreset').value;
        payload.user_bpm = parseFloat(document.getElementById('userBpm').value);
    }

    if (refSource === 'library') {
        payload.ref_library_id = document.getElementById('refLibrary').value;
        if (!payload.ref_library_id) {
            alert('Please select a reference from the library');
            return;
        }
    } else if (refSource === 'audio') {
        payload.ref_path = document.getElementById('refAudioFile').value;
        if (!payload.ref_path) {
            alert('Please select a reference audio file');
            return;
        }
    } else {
        payload.ref_preset = document.getElementById('refPreset').value;
        payload.ref_bpm = parseFloat(document.getElementById('refBpm').value);
    }

    document.getElementById('loadingIndicator').style.display = 'inline';

    try {
        const response = await fetch('/api/compare/overlay', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (data.error) {
            alert('Error: ' + data.error);
            return;
        }

        comparisonResult = data;
        displayResults(data);

    } catch (err) {
        alert('Error running comparison: ' + err.message);
    } finally {
        document.getElementById('loadingIndicator').style.display = 'none';
    }
}

function displayResults(data) {
    document.getElementById('resultsSection').style.display = 'block';

    // Alignment score
    const score = data.overall_alignment_score;
    const scoreEl = document.getElementById('alignmentScore');
    const labelEl = document.getElementById('alignmentLabel');

    scoreEl.textContent = Math.round(score * 100) + '%';

    if (score >= 0.9) {
        scoreEl.style.color = '#22c55e';
        labelEl.textContent = 'Excellent - Structure closely matches reference';
    } else if (score >= 0.7) {
        scoreEl.style.color = '#84cc16';
        labelEl.textContent = 'Good - Most sections align well';
    } else if (score >= 0.5) {
        scoreEl.style.color = '#eab308';
        labelEl.textContent = 'Fair - Some structural differences';
    } else {
        scoreEl.style.color = '#ef4444';
        labelEl.textContent = 'Different - Structure varies significantly from reference';
    }

    // Track names
    document.getElementById('userTrackName').textContent = data.user_template.name;
    document.getElementById('refTrackName').textContent = data.ref_template.name;

    // Timelines
    renderTimeline('userTimeline', data.user_template);
    renderTimeline('refTimeline', data.ref_template);

    // Time axis
    const maxDuration = Math.max(data.user_template.total_duration, data.ref_template.total_duration);
    renderTimeAxis(maxDuration);

    // Alignment details
    renderAlignments(data.alignments);

    // Insights
    renderInsights(data.insights);

    // Scroll to results
    document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth' });
}

function renderTimeline(containerId, template) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';

    const totalDuration = template.total_duration;

    template.sections.forEach(section => {
        const div = document.createElement('div');
        div.className = 'timeline-section';

        const startPercent = (section.start_time / totalDuration) * 100;
        const widthPercent = (section.duration / totalDuration) * 100;

        div.style.left = startPercent + '%';
        div.style.width = widthPercent + '%';
        div.style.background = SECTION_COLORS[section.section_type] || '#6b7280';

        div.textContent = section.section_type.toUpperCase();
        div.title = `${section.section_type} - ${section.bars} bars (${formatTime(section.start_time)} - ${formatTime(section.end_time)})`;

        container.appendChild(div);
    });
}

function renderTimeAxis(maxDuration) {
    const container = document.getElementById('timeAxis');
    container.innerHTML = '';

    const steps = 6;
    for (let i = 0; i <= steps; i++) {
        const time = (maxDuration / steps) * i;
        const span = document.createElement('span');
        span.textContent = formatTime(time);
        container.appendChild(span);
    }
}

function renderAlignments(alignments) {
    const container = document.getElementById('alignmentDetails');
    container.innerHTML = '';

    alignments.forEach(alignment => {
        const row = document.createElement('div');
        row.className = 'alignment-row ' + alignment.status;

        const statusIcon = {
            'aligned': '✓',
            'early': '◀',
            'late': '▶',
            'missing_user': '✗',
            'missing_ref': '+'
        }[alignment.status] || '?';

        const statusColor = {
            'aligned': '#22c55e',
            'early': '#eab308',
            'late': '#eab308',
            'missing_user': '#ef4444',
            'missing_ref': '#3b82f6'
        }[alignment.status] || '#6b7280';

        row.innerHTML = `
            <span style="font-size: 1.5rem; margin-right: 12px; color: ${statusColor};">${statusIcon}</span>
            <div style="flex: 1;">
                <div style="font-weight: bold; margin-bottom: 4px;">${alignment.message}</div>
                <div style="color: var(--text-secondary); font-size: 0.9rem;">
                    @ ${formatTime(alignment.time_position)}
                    ${alignment.time_diff !== 0 ? `(${alignment.time_diff > 0 ? '+' : ''}${alignment.time_diff.toFixed(1)}s)` : ''}
                </div>
            </div>
        `;

        container.appendChild(row);
    });

    if (alignments.length === 0) {
        container.innerHTML = '<div style="color: var(--text-secondary); text-align: center; padding: 24px;">No section alignments found</div>';
    }
}

function renderInsights(insights) {
    const container = document.getElementById('insightsList');
    container.innerHTML = '';

    insights.forEach(insight => {
        const item = document.createElement('div');
        item.className = 'insight-item';

        // Determine type based on content
        if (insight.includes('missing') || insight.includes('Missing')) {
            item.classList.add('warning');
        } else if (insight.includes('shorter') || insight.includes('longer')) {
            item.classList.add('warning');
        } else if (insight.includes('perfect') || insight.includes('matches')) {
            item.classList.add('success');
        }

        item.textContent = insight;
        container.appendChild(item);
    });

    if (insights.length === 0) {
        container.innerHTML = '<div class="insight-item success">Structures are well aligned - no specific recommendations</div>';
    }
}

function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return mins + ':' + secs.toString().padStart(2, '0');
}
</script>
"""


# ============================================================================
# MIDI Extraction Page Content
# ============================================================================

MIDI_EXTRACTION_CONTENT = """
<h1 style="margin-bottom: 30px;">MIDI Extraction & Variations</h1>

<div class="two-col">
    <!-- ALS File Selection -->
    <div class="card">
        <h2 class="card-title">Load ALS File</h2>

        <div style="margin-bottom: 15px;">
            <label class="settings-label">Select Ableton Project</label>
            <select class="settings-input" id="alsFileSelect" style="width: 100%;">
                <option value="">-- Select ALS File --</option>
                {% for als in als_files %}
                <option value="{{ als.path }}">{{ als.folder }} / {{ als.name }}</option>
                {% endfor %}
            </select>
        </div>

        <button class="btn btn-primary" onclick="loadALSFile()" style="width: 100%;">
            Load MIDI Clips
        </button>

        <div id="loadStatus" style="margin-top: 15px; display: none; padding: 10px; border-radius: 8px; background: var(--bg-secondary);">
        </div>
    </div>

    <!-- Project Info -->
    <div class="card">
        <h2 class="card-title">Project Info</h2>
        <div id="projectInfo" style="color: var(--text-secondary);">
            <p>Select an ALS file to see project details</p>
        </div>
    </div>
</div>

<!-- Track & Clip Browser -->
<div class="card" style="margin-top: 20px;">
    <h2 class="card-title">Tracks & Clips</h2>

    <div style="display: grid; grid-template-columns: 300px 1fr; gap: 20px; min-height: 300px;">
        <!-- Track List -->
        <div id="trackList" style="background: var(--bg-secondary); border-radius: 8px; padding: 15px; overflow-y: auto; max-height: 400px;">
            <div style="color: var(--text-secondary); text-align: center;">
                No clips loaded
            </div>
        </div>

        <!-- Clip Details -->
        <div id="clipDetails" style="background: var(--bg-secondary); border-radius: 8px; padding: 15px;">
            <div style="color: var(--text-secondary); text-align: center;">
                Select a clip to see details
            </div>
        </div>
    </div>
</div>

<!-- Piano Roll Preview -->
<div class="card" style="margin-top: 20px;" id="pianoRollCard" style="display: none;">
    <h2 class="card-title">Piano Roll Preview</h2>
    <canvas id="pianoRollCanvas" style="width: 100%; height: 150px; background: var(--bg-secondary); border-radius: 8px;"></canvas>
</div>

<!-- Variation Generator -->
<div class="card" style="margin-top: 20px;">
    <h2 class="card-title">Generate Variations</h2>

    <div style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 15px;">
        <label style="display: flex; align-items: center; gap: 5px;">
            <input type="checkbox" id="varTranspose" checked> Transpose
        </label>
        <label style="display: flex; align-items: center; gap: 5px;">
            <input type="checkbox" id="varHumanize" checked> Humanize
        </label>
        <label style="display: flex; align-items: center; gap: 5px;">
            <input type="checkbox" id="varReverse"> Reverse
        </label>
        <label style="display: flex; align-items: center; gap: 5px;">
            <input type="checkbox" id="varQuantize"> Quantize
        </label>
        <label style="display: flex; align-items: center; gap: 5px;">
            <input type="checkbox" id="varVelocity"> Velocity Curves
        </label>
        <label style="display: flex; align-items: center; gap: 5px;">
            <input type="checkbox" id="varOctave"> Octave Double
        </label>
    </div>

    <div style="display: flex; gap: 10px; align-items: center; margin-bottom: 15px;">
        <label>Number of variations:</label>
        <input type="number" id="variationCount" value="4" min="1" max="8" style="width: 60px;" class="settings-input">
        <button class="btn btn-primary" onclick="generateVariations()" id="generateBtn" disabled>
            Generate Variations
        </button>
    </div>

    <div id="variationsList" style="display: none;">
        <h3 style="margin-bottom: 10px;">Generated Variations</h3>
        <div id="variationsContainer" style="display: flex; flex-wrap: wrap; gap: 10px;">
        </div>
    </div>
</div>

<!-- Export Actions -->
<div style="display: flex; gap: 15px; margin-top: 20px; flex-wrap: wrap;">
    <button class="btn btn-primary" onclick="downloadMIDI()" id="downloadBtn" disabled>
        Download Selected as MIDI
    </button>
    <button class="btn" onclick="downloadAllVariations()" id="downloadAllBtn" disabled>
        Download All Variations
    </button>
</div>

<style>
.track-item {
    padding: 8px 12px;
    background: var(--bg-primary);
    border-radius: 6px;
    margin-bottom: 8px;
    cursor: pointer;
    transition: background 0.2s;
}

.track-item:hover {
    background: var(--border-color);
}

.track-item.expanded {
    background: var(--bg-card);
}

.track-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 500;
}

.track-header .arrow {
    transition: transform 0.2s;
}

.track-item.expanded .track-header .arrow {
    transform: rotate(90deg);
}

.clip-list {
    margin-top: 8px;
    margin-left: 20px;
    display: none;
}

.track-item.expanded .clip-list {
    display: block;
}

.clip-item {
    padding: 6px 10px;
    background: var(--bg-secondary);
    border-radius: 4px;
    margin-bottom: 4px;
    cursor: pointer;
    font-size: 0.9rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.clip-item:hover {
    background: var(--accent);
    color: white;
}

.clip-item.selected {
    background: var(--accent);
    color: white;
}

.clip-notes {
    font-size: 0.8rem;
    opacity: 0.8;
}

.variation-card {
    background: var(--bg-secondary);
    border-radius: 8px;
    padding: 12px;
    min-width: 150px;
    cursor: pointer;
    border: 2px solid transparent;
    transition: all 0.2s;
}

.variation-card:hover {
    border-color: var(--accent);
}

.variation-card.selected {
    border-color: var(--accent);
    background: var(--bg-primary);
}

.variation-name {
    font-weight: 500;
    margin-bottom: 4px;
}

.variation-type {
    font-size: 0.8rem;
    color: var(--text-secondary);
}
</style>

<script>
let currentProject = null;
let selectedClip = null;
let selectedNotes = null;
let generatedVariations = [];
let selectedVariation = null;

async function loadALSFile() {
    const alsPath = document.getElementById('alsFileSelect').value;
    if (!alsPath) {
        alert('Please select an ALS file');
        return;
    }

    const status = document.getElementById('loadStatus');
    status.style.display = 'block';
    status.style.background = 'var(--bg-secondary)';
    status.textContent = 'Loading...';

    try {
        const response = await fetch('/api/midi/parse-als', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ als_path: alsPath })
        });

        const data = await response.json();

        if (data.error) {
            status.style.background = 'rgba(239, 68, 68, 0.2)';
            status.style.color = 'var(--error)';
            status.textContent = 'Error: ' + data.error;
            return;
        }

        currentProject = data;
        status.style.background = 'rgba(34, 197, 94, 0.2)';
        status.style.color = 'var(--success)';
        status.textContent = `Loaded ${data.total_clips} clips from ${data.total_tracks} tracks`;

        renderProjectInfo();
        renderTrackList();

    } catch (err) {
        status.style.background = 'rgba(239, 68, 68, 0.2)';
        status.style.color = 'var(--error)';
        status.textContent = 'Error: ' + err.message;
    }
}

function renderProjectInfo() {
    const info = document.getElementById('projectInfo');
    if (!currentProject) {
        info.innerHTML = '<p>Select an ALS file to see project details</p>';
        return;
    }

    info.innerHTML = `
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
            <div><strong>File:</strong> ${currentProject.file_name}</div>
            <div><strong>Tempo:</strong> ${currentProject.tempo} BPM</div>
            <div><strong>MIDI Tracks:</strong> ${currentProject.total_tracks}</div>
            <div><strong>Total Clips:</strong> ${currentProject.total_clips}</div>
        </div>
    `;
}

function renderTrackList() {
    const container = document.getElementById('trackList');

    if (!currentProject || !currentProject.tracks.length) {
        container.innerHTML = '<div style="color: var(--text-secondary); text-align: center;">No MIDI clips found</div>';
        return;
    }

    container.innerHTML = currentProject.tracks.map(track => `
        <div class="track-item" onclick="toggleTrack(this)">
            <div class="track-header">
                <span class="arrow">▶</span>
                <span>${track.name}</span>
                <span style="color: var(--text-secondary); font-size: 0.8rem;">(${track.clips.length} clips)</span>
            </div>
            <div class="clip-list">
                ${track.clips.map(clip => `
                    <div class="clip-item" onclick="event.stopPropagation(); selectClip(${track.id}, ${clip.id})">
                        <span>${clip.name || 'Unnamed'}</span>
                        <span class="clip-notes">${clip.note_count} notes</span>
                    </div>
                `).join('')}
            </div>
        </div>
    `).join('');
}

function toggleTrack(element) {
    element.classList.toggle('expanded');
}

function selectClip(trackId, clipId) {
    // Find the clip
    const track = currentProject.tracks.find(t => t.id === trackId);
    if (!track) return;

    const clip = track.clips.find(c => c.id === clipId);
    if (!clip) return;

    selectedClip = clip;
    selectedNotes = clip.notes;

    // Update UI selection
    document.querySelectorAll('.clip-item').forEach(el => el.classList.remove('selected'));
    event.target.closest('.clip-item').classList.add('selected');

    // Enable buttons
    document.getElementById('generateBtn').disabled = false;
    document.getElementById('downloadBtn').disabled = false;

    // Render clip details
    renderClipDetails(clip);

    // Render piano roll
    renderPianoRoll(clip.notes);
}

function renderClipDetails(clip) {
    const container = document.getElementById('clipDetails');

    // Calculate duration in bars (assuming 4/4)
    const durationBars = (clip.duration_beats / 4).toFixed(1);

    // Find pitch range
    const pitches = clip.notes.map(n => n.pitch);
    const minPitch = Math.min(...pitches);
    const maxPitch = Math.max(...pitches);

    const noteNames = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
    const minNoteName = noteNames[minPitch % 12] + Math.floor(minPitch / 12 - 1);
    const maxNoteName = noteNames[maxPitch % 12] + Math.floor(maxPitch / 12 - 1);

    // Calculate velocity range
    const velocities = clip.notes.map(n => n.velocity);
    const minVel = Math.min(...velocities);
    const maxVel = Math.max(...velocities);
    const avgVel = Math.round(velocities.reduce((a, b) => a + b, 0) / velocities.length);

    container.innerHTML = `
        <h3 style="margin-bottom: 15px;">${clip.name || 'Unnamed Clip'}</h3>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
            <div>
                <div style="color: var(--text-secondary); font-size: 0.85rem;">Notes</div>
                <div style="font-size: 1.2rem; font-weight: 500;">${clip.note_count}</div>
            </div>
            <div>
                <div style="color: var(--text-secondary); font-size: 0.85rem;">Duration</div>
                <div style="font-size: 1.2rem; font-weight: 500;">${durationBars} bars</div>
            </div>
            <div>
                <div style="color: var(--text-secondary); font-size: 0.85rem;">Pitch Range</div>
                <div style="font-size: 1rem;">${minNoteName} - ${maxNoteName}</div>
            </div>
            <div>
                <div style="color: var(--text-secondary); font-size: 0.85rem;">Velocity</div>
                <div style="font-size: 1rem;">${minVel} - ${maxVel} (avg ${avgVel})</div>
            </div>
        </div>

        <div style="margin-top: 20px;">
            <button class="btn" onclick="analyzeClip()" style="width: 100%;">
                Analyze Scale & Patterns
            </button>
        </div>

        <div id="analysisResult" style="margin-top: 15px; display: none;"></div>
    `;
}

async function analyzeClip() {
    if (!selectedNotes) return;

    try {
        const response = await fetch('/api/midi/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ notes: selectedNotes })
        });

        const data = await response.json();
        const result = document.getElementById('analysisResult');
        result.style.display = 'block';

        if (data.error) {
            result.innerHTML = `<div style="color: var(--error);">Error: ${data.error}</div>`;
            return;
        }

        result.innerHTML = `
            <div style="background: var(--bg-primary); padding: 10px; border-radius: 6px;">
                <div style="margin-bottom: 8px;">
                    <strong>Detected Scale:</strong> ${data.scale || 'Unknown'}
                </div>
            </div>
        `;

    } catch (err) {
        console.error(err);
    }
}

function renderPianoRoll(notes) {
    const canvas = document.getElementById('pianoRollCanvas');
    const ctx = canvas.getContext('2d');

    // Set canvas size
    canvas.width = canvas.offsetWidth * 2;
    canvas.height = 300;
    ctx.scale(2, 2);

    const width = canvas.offsetWidth;
    const height = 150;

    // Clear
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, width, height);

    if (!notes || notes.length === 0) return;

    // Find ranges
    const minPitch = Math.min(...notes.map(n => n.pitch)) - 2;
    const maxPitch = Math.max(...notes.map(n => n.pitch)) + 2;
    const pitchRange = maxPitch - minPitch;

    const minTime = Math.min(...notes.map(n => n.start_time));
    const maxTime = Math.max(...notes.map(n => n.start_time + n.duration));
    const timeRange = maxTime - minTime;

    // Draw grid lines
    ctx.strokeStyle = '#2a2a3e';
    ctx.lineWidth = 0.5;

    // Horizontal lines (pitches)
    for (let p = minPitch; p <= maxPitch; p++) {
        const y = height - ((p - minPitch) / pitchRange) * height;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
    }

    // Vertical lines (beats)
    for (let t = Math.floor(minTime); t <= Math.ceil(maxTime); t++) {
        const x = ((t - minTime) / timeRange) * width;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
    }

    // Draw notes
    notes.forEach(note => {
        const x = ((note.start_time - minTime) / timeRange) * width;
        const y = height - ((note.pitch - minPitch) / pitchRange) * height;
        const w = (note.duration / timeRange) * width;
        const h = height / pitchRange * 0.8;

        // Note color based on velocity
        const velRatio = note.velocity / 127;
        const r = Math.round(100 + velRatio * 155);
        const g = Math.round(120 + velRatio * 80);
        const b = Math.round(200 - velRatio * 50);

        ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
        ctx.fillRect(x, y - h/2, Math.max(w, 2), h);

        // Note border
        ctx.strokeStyle = 'rgba(255,255,255,0.3)';
        ctx.strokeRect(x, y - h/2, Math.max(w, 2), h);
    });

    document.getElementById('pianoRollCard').style.display = 'block';
}

async function generateVariations() {
    if (!selectedNotes || selectedNotes.length === 0) {
        alert('Please select a clip first');
        return;
    }

    const count = parseInt(document.getElementById('variationCount').value) || 4;

    // Build variation types based on checkboxes
    const types = [];
    if (document.getElementById('varTranspose').checked) {
        types.push('transpose_up', 'transpose_down');
    }
    if (document.getElementById('varHumanize').checked) {
        types.push('humanize');
    }
    if (document.getElementById('varReverse').checked) {
        types.push('reverse');
    }
    if (document.getElementById('varQuantize').checked) {
        types.push('quantize');
    }
    if (document.getElementById('varVelocity').checked) {
        types.push('crescendo', 'decrescendo');
    }
    if (document.getElementById('varOctave').checked) {
        types.push('octave_up', 'octave_down');
    }

    try {
        const response = await fetch('/api/midi/variations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                notes: selectedNotes,
                clip_name: selectedClip?.name || 'Clip',
                count: count,
                variation_types: types.length > 0 ? types : null
            })
        });

        const data = await response.json();

        if (data.error) {
            alert('Error: ' + data.error);
            return;
        }

        generatedVariations = data.variations;
        renderVariations();

        document.getElementById('downloadAllBtn').disabled = false;

    } catch (err) {
        alert('Error generating variations: ' + err.message);
    }
}

function renderVariations() {
    const container = document.getElementById('variationsContainer');
    const list = document.getElementById('variationsList');

    if (!generatedVariations.length) {
        list.style.display = 'none';
        return;
    }

    list.style.display = 'block';

    container.innerHTML = generatedVariations.map((v, i) => `
        <div class="variation-card ${selectedVariation === i ? 'selected' : ''}" onclick="selectVariation(${i})">
            <div class="variation-name">${v.name}</div>
            <div class="variation-type">${v.variation_type.replace('_', ' ')}</div>
            <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 4px;">
                ${v.note_count} notes
            </div>
        </div>
    `).join('');
}

function selectVariation(index) {
    selectedVariation = index;
    selectedNotes = generatedVariations[index].notes;

    document.querySelectorAll('.variation-card').forEach((el, i) => {
        el.classList.toggle('selected', i === index);
    });

    renderPianoRoll(selectedNotes);
}

async function downloadMIDI() {
    if (!selectedNotes || selectedNotes.length === 0) {
        alert('Please select a clip or variation first');
        return;
    }

    const clipName = selectedVariation !== null
        ? generatedVariations[selectedVariation].name
        : (selectedClip?.name || 'exported');

    try {
        const response = await fetch('/api/midi/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                notes: selectedNotes,
                clip_name: clipName,
                tempo: currentProject?.tempo || 120
            })
        });

        const data = await response.json();

        if (data.error) {
            alert('Error: ' + data.error);
            return;
        }

        // Download the file
        const blob = b64toBlob(data.data, 'audio/midi');
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = data.filename;
        a.click();
        URL.revokeObjectURL(url);

    } catch (err) {
        alert('Error downloading MIDI: ' + err.message);
    }
}

async function downloadAllVariations() {
    if (!generatedVariations.length) {
        alert('No variations to download');
        return;
    }

    for (let i = 0; i < generatedVariations.length; i++) {
        const v = generatedVariations[i];

        try {
            const response = await fetch('/api/midi/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    notes: v.notes,
                    clip_name: v.name,
                    tempo: currentProject?.tempo || 120
                })
            });

            const data = await response.json();

            if (!data.error) {
                const blob = b64toBlob(data.data, 'audio/midi');
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = data.filename;
                a.click();
                URL.revokeObjectURL(url);
            }

            // Small delay between downloads
            await new Promise(r => setTimeout(r, 200));

        } catch (err) {
            console.error('Error downloading variation:', err);
        }
    }
}

function b64toBlob(b64Data, contentType) {
    const byteCharacters = atob(b64Data);
    const byteArrays = [];

    for (let offset = 0; offset < byteCharacters.length; offset += 512) {
        const slice = byteCharacters.slice(offset, offset + 512);
        const byteNumbers = new Array(slice.length);

        for (let i = 0; i < slice.length; i++) {
            byteNumbers[i] = slice.charCodeAt(i);
        }

        byteArrays.push(new Uint8Array(byteNumbers));
    }

    return new Blob(byteArrays, { type: contentType });
}
</script>
"""


# ============================================================================
# Flask Application Factory
# ============================================================================

def create_dashboard_app(config: Optional[DashboardConfig] = None) -> 'Flask':
    """
    Create and configure the Flask dashboard application.

    Args:
        config: Dashboard configuration options

    Returns:
        Configured Flask application
    """
    if not FLASK_AVAILABLE:
        raise ImportError("Flask is required for the dashboard. Install with: pip install flask")

    app = Flask(__name__)
    app.config['dashboard_config'] = config or DashboardConfig()

    # Register routes
    register_routes(app)

    return app


def register_routes(app: 'Flask'):
    """Register all dashboard routes."""

    @app.route('/')
    def home():
        """Home page with health overview."""
        config = app.config['dashboard_config']
        data = get_dashboard_home_data()

        content = render_template_string(HOME_CONTENT, data=data.to_dict())

        return render_template_string(
            BASE_TEMPLATE,
            title="Dashboard",
            css=DASHBOARD_CSS,
            content=content,
            active='home',
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            auto_refresh=config.auto_refresh,
            refresh_interval=config.refresh_interval,
            extra_head=get_auto_refresh_meta(config) if config.auto_refresh else '',
            extra_js=FOCUS_JS
        )

    @app.route('/projects')
    def projects():
        """Project list page."""
        config = app.config['dashboard_config']
        project_list = get_project_list_data()

        content = render_template_string(
            PROJECTS_CONTENT,
            projects=[p.to_dict() for p in project_list]
        )

        return render_template_string(
            BASE_TEMPLATE,
            title="Projects",
            css=DASHBOARD_CSS,
            content=content,
            active='projects',
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            auto_refresh=config.auto_refresh,
            refresh_interval=config.refresh_interval,
            extra_head=get_auto_refresh_meta(config) if config.auto_refresh else '',
            extra_js=''
        )

    @app.route('/project/<int:project_id>')
    def project_detail(project_id: int):
        """Project detail page."""
        config = app.config['dashboard_config']
        project = get_project_detail_data(project_id)

        if project is None:
            abort(404)

        import json
        versions_json = json.dumps([v.to_dict() for v in project.versions])

        content = render_template_string(PROJECT_DETAIL_CONTENT, project=project.to_dict())
        chart_js = render_template_string(PROJECT_CHART_JS, versions_json=versions_json)

        return render_template_string(
            BASE_TEMPLATE,
            title=project.song_name,
            css=DASHBOARD_CSS,
            content=content,
            active='projects',
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            auto_refresh=config.auto_refresh,
            refresh_interval=config.refresh_interval,
            extra_head=get_auto_refresh_meta(config) if config.auto_refresh else '',
            extra_js=chart_js if len(project.versions) > 1 else ''
        )

    @app.route('/project/<int:project_id>/compare')
    def project_compare(project_id: int):
        """Project version comparison page."""
        config = app.config['dashboard_config']

        # Get all versions for the project
        versions = get_project_versions(project_id)
        if len(versions) < 2:
            abort(404)  # Need at least 2 versions to compare

        # Get version IDs from query params (or use defaults)
        version_a_id = request.args.get('a', type=int)
        version_b_id = request.args.get('b', type=int)

        # Default to first and last versions
        if version_a_id is None:
            version_a_id = versions[0].id
        if version_b_id is None:
            version_b_id = versions[-1].id

        # Get comparison data
        comparison = get_comparison_data(project_id, version_a_id, version_b_id)
        if comparison is None:
            abort(404)

        content = render_template_string(
            COMPARE_CONTENT,
            comparison=comparison.to_dict(),
            versions=[v.to_dict() for v in versions]
        )

        return render_template_string(
            BASE_TEMPLATE,
            title=f"{comparison.song_name} - Compare",
            css=DASHBOARD_CSS,
            content=content,
            active='projects',
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            auto_refresh=False,  # Don't auto-refresh comparison pages
            refresh_interval=config.refresh_interval,
            extra_head='',
            extra_js=''
        )

    @app.route('/insights')
    def insights():
        """Insights page with pattern analysis."""
        config = app.config['dashboard_config']
        insights_data = get_insights_data()

        content = render_template_string(
            INSIGHTS_CONTENT,
            **insights_data
        )

        return render_template_string(
            BASE_TEMPLATE,
            title="Insights",
            css=DASHBOARD_CSS,
            content=content,
            active='insights',
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            auto_refresh=config.auto_refresh,
            refresh_interval=config.refresh_interval,
            extra_head=get_auto_refresh_meta(config) if config.auto_refresh else '',
            extra_js=''
        )

    @app.route('/settings')
    def settings():
        """Settings page."""
        config = app.config['dashboard_config']
        db_info = get_database_info()

        content = render_template_string(
            SETTINGS_CONTENT,
            config=config,
            db_path=db_info['path'],
            total_projects=db_info['total_projects'],
            total_versions=db_info['total_versions']
        )

        return render_template_string(
            BASE_TEMPLATE,
            title="Settings",
            css=DASHBOARD_CSS,
            content=content,
            active='settings',
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            auto_refresh=False,
            refresh_interval=config.refresh_interval,
            extra_head='',
            extra_js=''
        )

    # API endpoints for auto-refresh
    @app.route('/api/home')
    def api_home():
        """API endpoint for home data."""
        data = get_dashboard_home_data()
        return jsonify(data.to_dict())

    @app.route('/api/projects')
    def api_projects():
        """API endpoint for project list."""
        projects = get_project_list_data()
        return jsonify([p.to_dict() for p in projects])

    @app.route('/api/project/<int:project_id>')
    def api_project(project_id: int):
        """API endpoint for project detail."""
        project = get_project_detail_data(project_id)
        if project is None:
            return jsonify({'error': 'Project not found'}), 404
        return jsonify(project.to_dict())

    # User activity API endpoints (Story 4.6)
    @app.route('/api/project/<int:project_id>/worked', methods=['POST'])
    def api_mark_worked(project_id: int):
        """Record that the user worked on this project."""
        from database import record_work_session

        # Get optional parameters from request
        data = request.get_json() or {}
        notes = data.get('notes')
        hide_days = data.get('hide_days', 0)

        success, message = record_work_session(project_id, notes=notes, hide_days=hide_days)

        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 400

    @app.route('/api/project/<int:project_id>/hide', methods=['POST'])
    def api_hide_project(project_id: int):
        """Temporarily hide a project from work suggestions."""
        from database import hide_project_temporarily

        data = request.get_json() or {}
        days = data.get('days', 7)  # Default to 7 days

        success, message = hide_project_temporarily(project_id, days)

        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 400

    @app.route('/api/project/<int:project_id>/unhide', methods=['POST'])
    def api_unhide_project(project_id: int):
        """Make a project visible in suggestions again."""
        from database import unhide_project

        success, message = unhide_project(project_id)

        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 400

    @app.route('/api/project/<int:project_id>/activity')
    def api_project_activity(project_id: int):
        """Get work activity history for a project."""
        from database import get_work_history, get_days_since_worked, is_project_hidden

        history = get_work_history(project_id)
        days_since = get_days_since_worked(project_id)
        is_hidden = is_project_hidden(project_id)

        return jsonify({
            'days_since_worked': days_since,
            'is_hidden': is_hidden,
            'history': [
                {
                    'id': a.id,
                    'worked_at': a.worked_at.isoformat() if a.worked_at else None,
                    'notes': a.notes
                }
                for a in history
            ]
        })

    # ========================================================================
    # Arrangement Analysis Routes
    # ========================================================================

    @app.route('/arrangement')
    def arrangement():
        """Arrangement analysis page."""
        config = app.config['dashboard_config']
        audio_files = get_audio_files_list()

        content = render_template_string(
            ARRANGEMENT_CONTENT,
            audio_files=audio_files
        )

        return render_template_string(
            BASE_TEMPLATE,
            title="Arrangement Analysis",
            css=DASHBOARD_CSS,
            content=content,
            active='arrangement',
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            auto_refresh=False,
            refresh_interval=config.refresh_interval,
            extra_head='',
            extra_js=''
        )

    @app.route('/api/arrangement/files')
    def api_arrangement_files():
        """Get list of available audio files."""
        return jsonify(get_audio_files_list())

    @app.route('/api/arrangement/analyze', methods=['POST'])
    def api_arrangement_analyze():
        """Analyze arrangement of an audio file."""
        import json

        audio_path = request.json.get('audio_path')
        if not audio_path:
            return jsonify({'error': 'No audio path provided'}), 400

        audio_path = Path(audio_path)
        if not audio_path.exists():
            return jsonify({'error': f'File not found: {audio_path}'}), 404

        try:
            # Import the analyzers
            try:
                from structure_detector import StructureDetector
                from arrangement_scorer import ArrangementScorer
            except ImportError:
                from src.structure_detector import StructureDetector
                from src.arrangement_scorer import ArrangementScorer

            # Run structure detection
            detector = StructureDetector()
            structure = detector.detect(str(audio_path))

            # Run arrangement scoring
            scorer = ArrangementScorer()
            score = scorer.score(structure)

            # Convert to JSON-serializable format
            result = score.to_dict()

            return jsonify(result)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    # ========================================================================
    # Template Routes
    # ========================================================================

    @app.route('/templates')
    def templates():
        """Arrangement templates page."""
        config = app.config['dashboard_config']

        # Get presets and audio files
        try:
            from template_generator import TemplateGenerator
        except ImportError:
            from src.template_generator import TemplateGenerator

        generator = TemplateGenerator()
        presets = generator.get_preset_names()
        audio_files = get_audio_files_list()

        content = render_template_string(
            TEMPLATES_CONTENT,
            presets=presets,
            audio_files=audio_files
        )

        return render_template_string(
            BASE_TEMPLATE,
            title="Arrangement Templates",
            css=DASHBOARD_CSS,
            content=content,
            active='templates',
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            auto_refresh=False,
            refresh_interval=config.refresh_interval,
            extra_head='',
            extra_js=''
        )

    @app.route('/midi')
    def midi_extraction():
        """MIDI extraction and variation generator page."""
        config = app.config['dashboard_config']

        als_files = get_als_files_list()

        content = render_template_string(
            MIDI_EXTRACTION_CONTENT,
            als_files=als_files
        )

        return render_template_string(
            BASE_TEMPLATE,
            title="MIDI Extraction",
            css=DASHBOARD_CSS,
            content=content,
            active='midi',
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            auto_refresh=False,
            refresh_interval=config.refresh_interval,
            extra_head='',
            extra_js=''
        )

    @app.route('/api/templates/presets')
    def api_template_presets():
        """Get list of available template presets."""
        try:
            from template_generator import TemplateGenerator
        except ImportError:
            from src.template_generator import TemplateGenerator

        generator = TemplateGenerator()
        return jsonify(generator.get_preset_names())

    @app.route('/api/templates/generate', methods=['POST'])
    def api_generate_template():
        """Generate a template from preset or reference."""
        try:
            from template_generator import TemplateGenerator
        except ImportError:
            from src.template_generator import TemplateGenerator

        data = request.json
        source = data.get('source')
        bpm = data.get('bpm', 138)

        generator = TemplateGenerator()

        try:
            if source == 'preset':
                preset = data.get('preset', 'standard_trance')
                template = generator.from_genre_preset(preset, bpm)
            elif source == 'reference':
                audio_path = data.get('audio_path')
                if not audio_path:
                    return jsonify({'error': 'No audio path provided'}), 400
                template = generator.from_reference(audio_path)
                # Apply custom BPM if different
                if bpm and abs(template.bpm - bpm) > 1:
                    template = generator.customize(template, bpm=bpm)
            else:
                return jsonify({'error': 'Invalid source type'}), 400

            return jsonify(template.to_dict())

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/templates/customize', methods=['POST'])
    def api_customize_template():
        """Customize a template's sections or BPM."""
        try:
            from template_generator import TemplateGenerator, ArrangementTemplate
        except ImportError:
            from src.template_generator import TemplateGenerator, ArrangementTemplate

        data = request.json
        template_data = data.get('template')
        bpm = data.get('bpm')
        sections = data.get('sections')

        if not template_data:
            return jsonify({'error': 'No template provided'}), 400

        try:
            # Reconstruct template from dict
            template = ArrangementTemplate.from_dict(template_data)

            # Apply customizations
            generator = TemplateGenerator()
            template = generator.customize(template, bpm=bpm, sections=sections)

            return jsonify(template.to_dict())

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/templates/ableton-status')
    def api_ableton_status():
        """Check Ableton connection status."""
        try:
            from ableton_bridge import AbletonBridge
        except ImportError:
            from src.ableton_bridge import AbletonBridge

        try:
            bridge = AbletonBridge()
            if bridge.connect():
                state = bridge.read_session_state(include_devices=False)
                if state:
                    return jsonify({
                        'connected': True,
                        'tempo': state.tempo,
                        'tracks': len(state.tracks)
                    })
            return jsonify({
                'connected': False,
                'error': bridge.last_error or 'Could not connect'
            })
        except Exception as e:
            return jsonify({
                'connected': False,
                'error': str(e)
            })

    @app.route('/api/templates/send-to-ableton', methods=['POST'])
    def api_send_to_ableton():
        """Send template to Ableton Live."""
        try:
            from ableton_bridge import AbletonBridge
            from template_generator import ArrangementTemplate
        except ImportError:
            from src.ableton_bridge import AbletonBridge
            from src.template_generator import ArrangementTemplate

        data = request.json
        template_data = data.get('template')

        if not template_data:
            return jsonify({'error': 'No template provided'}), 400

        try:
            template = ArrangementTemplate.from_dict(template_data)

            bridge = AbletonBridge()
            if not bridge.connect():
                return jsonify({
                    'success': False,
                    'message': 'Could not connect to Ableton: ' + (bridge.last_error or 'Unknown error'),
                    'manual_locators': template.to_locators()
                })

            success, message, manual_locators = bridge.send_template(template)

            return jsonify({
                'success': success,
                'message': message,
                'manual_locators': manual_locators
            })

        except Exception as e:
            return jsonify({
                'success': False,
                'message': str(e),
                'manual_locators': []
            }), 500

    # ========================================================================
    # Reference Overlay Routes
    # ========================================================================

    @app.route('/compare')
    def compare_page():
        """Reference overlay comparison page."""
        config = app.config['dashboard_config']
        audio_files = get_audio_files_list()

        # Get presets for quick reference selection
        try:
            from template_generator import TemplateGenerator
        except ImportError:
            from src.template_generator import TemplateGenerator

        generator = TemplateGenerator()
        presets = generator.get_preset_names()

        content = render_template_string(
            COMPARE_OVERLAY_CONTENT,
            audio_files=audio_files,
            presets=presets
        )

        return render_template_string(
            BASE_TEMPLATE,
            title="Reference Overlay",
            css=DASHBOARD_CSS,
            content=content,
            active='templates',  # Keep Templates highlighted in nav
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            auto_refresh=False,
            refresh_interval=config.refresh_interval,
            extra_head='',
            extra_js=''
        )

    @app.route('/api/compare/overlay', methods=['POST'])
    def api_compare_overlay():
        """Compare user track against reference track."""
        try:
            from template_generator import TemplateGenerator, ReferenceOverlay, ArrangementTemplate
            from reference_library import ReferenceLibrary
        except ImportError:
            from src.template_generator import TemplateGenerator, ReferenceOverlay, ArrangementTemplate
            from src.reference_library import ReferenceLibrary

        data = request.json
        user_source = data.get('user_source')  # 'audio', 'preset', or 'library'
        ref_source = data.get('ref_source')    # 'audio', 'preset', or 'library'

        generator = TemplateGenerator()
        library = ReferenceLibrary()

        try:
            # Get user template
            if user_source == 'audio':
                user_path = data.get('user_path')
                if not user_path:
                    return jsonify({'error': 'No user audio path provided'}), 400
                user_template = generator.from_reference(user_path)
            elif user_source == 'preset':
                preset = data.get('user_preset', 'standard_trance')
                bpm = data.get('user_bpm', 138)
                user_template = generator.from_genre_preset(preset, bpm)
            elif user_source == 'library':
                ref_id = data.get('user_library_id')
                if not ref_id:
                    return jsonify({'error': 'No library reference ID provided'}), 400
                user_template = library.to_template(ref_id)
                if not user_template:
                    return jsonify({'error': 'User reference not found in library'}), 404
            else:
                return jsonify({'error': 'Invalid user source'}), 400

            # Get reference template
            if ref_source == 'audio':
                ref_path = data.get('ref_path')
                if not ref_path:
                    return jsonify({'error': 'No reference audio path provided'}), 400
                ref_template = generator.from_reference(ref_path)
            elif ref_source == 'preset':
                preset = data.get('ref_preset', 'standard_trance')
                bpm = data.get('ref_bpm', 138)
                ref_template = generator.from_genre_preset(preset, bpm)
            elif ref_source == 'library':
                ref_id = data.get('ref_library_id')
                if not ref_id:
                    return jsonify({'error': 'No library reference ID provided'}), 400
                ref_template = library.to_template(ref_id)
                if not ref_template:
                    return jsonify({'error': 'Reference not found in library'}), 404
            else:
                return jsonify({'error': 'Invalid reference source'}), 400

            # Run comparison
            overlay = ReferenceOverlay()
            comparison = overlay.compare(user_template, ref_template)

            return jsonify(comparison.to_dict())

        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    # ========================================================================
    # Reference Library Routes
    # ========================================================================

    @app.route('/api/library/references')
    def api_list_references():
        """List all saved references in the library."""
        try:
            from reference_library import ReferenceLibrary
        except ImportError:
            from src.reference_library import ReferenceLibrary

        try:
            library = ReferenceLibrary()
            tag = request.args.get('tag')
            references = library.list_references(tag=tag)
            stats = library.get_stats()

            return jsonify({
                'references': [ref.to_dict() for ref in references],
                'stats': stats
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/library/references', methods=['POST'])
    def api_save_reference():
        """Save a template to the library."""
        try:
            from reference_library import ReferenceLibrary
            from template_generator import ArrangementTemplate
        except ImportError:
            from src.reference_library import ReferenceLibrary
            from src.template_generator import ArrangementTemplate

        data = request.json
        template_data = data.get('template')
        name = data.get('name')
        tags = data.get('tags', [])
        notes = data.get('notes', '')

        if not template_data:
            return jsonify({'error': 'No template provided'}), 400

        try:
            template = ArrangementTemplate.from_dict(template_data)
            library = ReferenceLibrary()
            ref_id = library.save_reference(template, name=name, tags=tags, notes=notes)

            return jsonify({
                'success': True,
                'id': ref_id,
                'message': f'Saved "{name or template.name}" to library'
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/library/references/<ref_id>')
    def api_get_reference(ref_id):
        """Get a specific reference from the library."""
        try:
            from reference_library import ReferenceLibrary
        except ImportError:
            from src.reference_library import ReferenceLibrary

        try:
            library = ReferenceLibrary()
            ref = library.get_reference(ref_id)

            if ref:
                return jsonify(ref.to_dict())
            else:
                return jsonify({'error': 'Reference not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/library/references/<ref_id>', methods=['DELETE'])
    def api_delete_reference(ref_id):
        """Delete a reference from the library."""
        try:
            from reference_library import ReferenceLibrary
        except ImportError:
            from src.reference_library import ReferenceLibrary

        try:
            library = ReferenceLibrary()
            if library.delete_reference(ref_id):
                return jsonify({'success': True, 'message': 'Reference deleted'})
            else:
                return jsonify({'error': 'Reference not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/library/references/<ref_id>', methods=['PUT'])
    def api_update_reference(ref_id):
        """Update reference metadata."""
        try:
            from reference_library import ReferenceLibrary
        except ImportError:
            from src.reference_library import ReferenceLibrary

        data = request.json

        try:
            library = ReferenceLibrary()
            if library.update_reference(
                ref_id,
                name=data.get('name'),
                tags=data.get('tags'),
                notes=data.get('notes')
            ):
                return jsonify({'success': True, 'message': 'Reference updated'})
            else:
                return jsonify({'error': 'Reference not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/library/references/<ref_id>/template')
    def api_reference_to_template(ref_id):
        """Convert a library reference to a template."""
        try:
            from reference_library import ReferenceLibrary
        except ImportError:
            from src.reference_library import ReferenceLibrary

        bpm = request.args.get('bpm', type=float)

        try:
            library = ReferenceLibrary()
            template = library.to_template(ref_id, bpm=bpm)

            if template:
                return jsonify(template.to_dict())
            else:
                return jsonify({'error': 'Reference not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # ==================== Marker Sync API ====================

    @app.route('/api/sync/status')
    def api_sync_status():
        """Get current sync status and Ableton connection info."""
        try:
            from sync_manager import MarkerSyncManager
        except ImportError:
            from src.sync_manager import MarkerSyncManager

        try:
            manager = MarkerSyncManager()
            status = manager.get_status()
            return jsonify(status)
        except Exception as e:
            return jsonify({
                'connected': False,
                'error': str(e)
            })

    @app.route('/api/sync/pull')
    def api_sync_pull():
        """Pull markers from Ableton."""
        try:
            from sync_manager import MarkerSyncManager
        except ImportError:
            from src.sync_manager import MarkerSyncManager

        try:
            manager = MarkerSyncManager()
            markers, message = manager.pull_from_ableton()
            return jsonify({
                'success': len(markers) > 0,
                'message': message,
                'markers': markers
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
                'markers': []
            })

    @app.route('/api/sync/push', methods=['POST'])
    def api_sync_push():
        """Push markers to Ableton."""
        try:
            from sync_manager import MarkerSyncManager
        except ImportError:
            from src.sync_manager import MarkerSyncManager

        data = request.get_json() or {}
        markers = data.get('markers', [])
        clear_first = data.get('clear_first', True)

        try:
            manager = MarkerSyncManager()
            result = manager.push_to_ableton(markers, clear_first=clear_first)
            return jsonify(result.to_dict())
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            })

    @app.route('/api/sync/diff', methods=['POST'])
    def api_sync_diff():
        """Get diff between dashboard markers and Ableton markers."""
        try:
            from sync_manager import MarkerSyncManager
        except ImportError:
            from src.sync_manager import MarkerSyncManager

        data = request.get_json() or {}
        dashboard_markers = data.get('markers', [])

        try:
            manager = MarkerSyncManager()
            diffs = manager.diff(dashboard_markers)
            return jsonify({
                'success': True,
                'diffs': [d.to_dict() for d in diffs],
                'summary': {
                    'matches': sum(1 for d in diffs if d.action.value == 'match'),
                    'to_add': sum(1 for d in diffs if d.action.value == 'add'),
                    'to_delete': sum(1 for d in diffs if d.action.value == 'delete'),
                    'to_update': sum(1 for d in diffs if d.action.value == 'update')
                }
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            })

    # ==================== MIDI Extraction API ====================

    @app.route('/api/midi/als-files')
    def api_midi_als_files():
        """Get list of ALS files from project directories."""
        als_files = get_als_files_list()
        return jsonify(als_files)

    @app.route('/api/midi/parse-als', methods=['POST'])
    def api_midi_parse_als():
        """Parse ALS file and return all MIDI clips."""
        try:
            from als_parser import ALSParser
        except ImportError:
            from src.als_parser import ALSParser

        data = request.get_json() or {}
        als_path = data.get('als_path')

        if not als_path:
            return jsonify({'error': 'No ALS path provided'}), 400

        als_path = Path(als_path)
        if not als_path.exists():
            return jsonify({'error': f'File not found: {als_path}'}), 404

        try:
            parser = ALSParser()
            project = parser.parse(str(als_path))

            # Build response with tracks and clips
            tracks = []
            for track in project.tracks:
                if track.midi_clips:
                    track_data = {
                        'id': track.id,
                        'name': track.name,
                        'type': track.track_type,
                        'clips': []
                    }
                    for i, clip in enumerate(track.midi_clips):
                        clip_data = {
                            'id': i,
                            'name': clip.name,
                            'start_time': clip.start_time,
                            'end_time': clip.end_time,
                            'note_count': len(clip.notes),
                            'duration_beats': round(clip.end_time - clip.start_time, 2),
                            'notes': [
                                {
                                    'pitch': n.pitch,
                                    'velocity': n.velocity,
                                    'start_time': round(n.start_time, 4),
                                    'duration': round(n.duration, 4)
                                }
                                for n in clip.notes
                            ]
                        }
                        track_data['clips'].append(clip_data)
                    tracks.append(track_data)

            return jsonify({
                'success': True,
                'file_name': als_path.name,
                'tempo': project.tempo,
                'tracks': tracks,
                'total_tracks': len(tracks),
                'total_clips': sum(len(t['clips']) for t in tracks)
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/midi/variations', methods=['POST'])
    def api_midi_variations():
        """Generate variations of a MIDI clip."""
        try:
            from midi_generator import MIDIVariationGenerator, MIDIVariation
            from als_parser import MIDINote, MIDIClip
        except ImportError:
            from src.midi_generator import MIDIVariationGenerator, MIDIVariation
            from src.als_parser import MIDINote, MIDIClip

        data = request.get_json() or {}
        notes_data = data.get('notes', [])
        clip_name = data.get('clip_name', 'Clip')
        count = data.get('count', 4)
        variation_types = data.get('variation_types')

        if not notes_data:
            return jsonify({'error': 'No notes provided'}), 400

        try:
            # Reconstruct notes
            notes = [
                MIDINote(
                    pitch=n['pitch'],
                    velocity=n['velocity'],
                    start_time=n['start_time'],
                    duration=n['duration'],
                    mute=n.get('mute', False)
                )
                for n in notes_data
            ]

            # Create clip
            clip = MIDIClip(
                name=clip_name,
                start_time=0,
                end_time=max(n.start_time + n.duration for n in notes) if notes else 0,
                loop_start=0,
                loop_end=0,
                notes=notes
            )

            # Generate variations
            generator = MIDIVariationGenerator()
            variations = generator.generate_variations(clip, count, variation_types)

            return jsonify({
                'success': True,
                'variations': [v.to_dict() for v in variations],
                'count': len(variations)
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/midi/export', methods=['POST'])
    def api_midi_export():
        """Export MIDI clip to downloadable file."""
        try:
            from midi_exporter import MIDIExporter
            from als_parser import MIDINote
        except ImportError:
            from src.midi_exporter import MIDIExporter
            from src.als_parser import MIDINote

        data = request.get_json() or {}
        notes_data = data.get('notes', [])
        clip_name = data.get('clip_name', 'exported')
        tempo = data.get('tempo', 120)

        if not notes_data:
            return jsonify({'error': 'No notes provided'}), 400

        try:
            # Reconstruct notes
            notes = [
                MIDINote(
                    pitch=n['pitch'],
                    velocity=n['velocity'],
                    start_time=n['start_time'],
                    duration=n['duration'],
                    mute=n.get('mute', False)
                )
                for n in notes_data
            ]

            # Export to bytes
            exporter = MIDIExporter(default_tempo=tempo)
            midi_data = exporter.export_to_bytes(notes, tempo, clip_name)

            if midi_data:
                import base64
                return jsonify({
                    'success': True,
                    'data': base64.b64encode(midi_data).decode('utf-8'),
                    'filename': f"{clip_name}.mid",
                    'size': len(midi_data)
                })
            else:
                return jsonify({'error': 'Failed to generate MIDI data'}), 500

        except ImportError as e:
            return jsonify({'error': f'MIDI export not available: {str(e)}. Install midiutil: pip install midiutil'}), 500
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/midi/analyze', methods=['POST'])
    def api_midi_analyze():
        """Analyze MIDI notes and return statistics."""
        try:
            from midi_generator import MIDIVariationGenerator
            from als_parser import MIDINote
        except ImportError:
            from src.midi_generator import MIDIVariationGenerator
            from src.als_parser import MIDINote

        data = request.get_json() or {}
        notes_data = data.get('notes', [])

        if not notes_data:
            return jsonify({'error': 'No notes provided'}), 400

        try:
            notes = [
                MIDINote(
                    pitch=n['pitch'],
                    velocity=n['velocity'],
                    start_time=n['start_time'],
                    duration=n['duration'],
                    mute=n.get('mute', False)
                )
                for n in notes_data
            ]

            generator = MIDIVariationGenerator()
            stats = generator.get_note_stats(notes)

            return jsonify({
                'success': True,
                **stats
            })

        except Exception as e:
            return jsonify({'error': str(e)}), 500


def get_als_files_list() -> List[Dict[str, str]]:
    """Get list of ALS files from project directories."""
    als_files = []

    # Check Ableton Projects folder
    projects_dir = Path("D:/OneDrive/Music/Projects/Ableton/Ableton Projects")
    if projects_dir.exists():
        for als in projects_dir.glob('**/*.als'):
            als_files.append({
                'name': als.stem,
                'path': str(als),
                'folder': als.parent.name
            })

    # Sort by folder then name
    als_files.sort(key=lambda x: (x['folder'].lower(), x['name'].lower()))

    return als_files


def get_audio_files_list() -> List[Dict[str, str]]:
    """Get list of audio files from configured directories."""
    audio_files = []
    audio_extensions = {'.wav', '.mp3', '.flac', '.aiff', '.ogg', '.m4a'}

    # Check the standard music projects directory
    projects_dir = Path("D:/OneDrive/Music/Projects")
    if projects_dir.exists():
        for f in projects_dir.glob('*'):
            if f.is_file() and f.suffix.lower() in audio_extensions:
                audio_files.append({
                    'name': f.name,
                    'path': str(f)
                })

    # Also check local test files
    local_dir = Path(".")
    for f in local_dir.glob('*.wav'):
        audio_files.append({
            'name': f.name,
            'path': str(f.absolute())
        })

    # Sort by name
    audio_files.sort(key=lambda x: x['name'].lower())

    return audio_files


def get_auto_refresh_meta(config: DashboardConfig) -> str:
    """Generate auto-refresh meta tag."""
    if config.auto_refresh:
        return f'<meta http-equiv="refresh" content="{config.refresh_interval}">'
    return ''


# ============================================================================
# Data Fetching Functions
# ============================================================================

def get_todays_focus() -> TodaysFocus:
    """
    Generate today's work prioritization based on project health and history.

    Categories:
    - Quick Wins: Grade C projects with few critical issues (easy fixes)
    - Deep Work: Grade D-F projects needing significant work
    - Ready to Polish: Grade B projects close to A

    Respects user activity:
    - Hidden projects are excluded
    - Recently worked projects are deprioritized
    """
    try:
        from database import get_db, is_project_hidden, get_days_since_worked

        db = get_db()
        if not db.is_initialized():
            return TodaysFocus()

        conn = db.connection
        cursor = conn.cursor()

        quick_wins = []
        deep_work = []
        ready_to_polish = []

        # Get all projects with their latest version scores
        cursor.execute("""
            SELECT p.id, p.song_name, v.health_score, v.grade, v.critical_issues, v.total_issues
            FROM projects p
            JOIN versions v ON v.id = (
                SELECT id FROM versions WHERE project_id = p.id ORDER BY scanned_at DESC LIMIT 1
            )
            ORDER BY v.health_score ASC
        """)

        for row in cursor.fetchall():
            project_id = row['id']
            song_name = row['song_name']
            score = row['health_score']
            grade = row['grade']
            critical = row['critical_issues']
            total_issues = row['total_issues']

            # Skip hidden projects
            if is_project_hidden(project_id):
                continue

            # Get days since last worked (for prioritization)
            days_since = get_days_since_worked(project_id)

            # Calculate potential gain (rough estimate)
            if grade == 'F':
                potential = min(30, 100 - score)
                reason = f"{critical} critical issues to fix"
                deep_work.append(WorkItem(
                    project_id=project_id,
                    song_name=song_name,
                    category='deep_work',
                    reason=reason,
                    health_score=score,
                    grade=grade,
                    potential_gain=potential,
                    days_since_worked=days_since
                ))
            elif grade == 'D':
                potential = min(25, 60 - score)
                reason = f"{total_issues} total issues, {critical} critical"
                deep_work.append(WorkItem(
                    project_id=project_id,
                    song_name=song_name,
                    category='deep_work',
                    reason=reason,
                    health_score=score,
                    grade=grade,
                    potential_gain=potential,
                    days_since_worked=days_since
                ))
            elif grade == 'C':
                if critical <= 1:
                    # Quick win - few critical issues
                    potential = min(20, 80 - score)
                    reason = f"Only {critical} critical issue{'s' if critical != 1 else ''}"
                    quick_wins.append(WorkItem(
                        project_id=project_id,
                        song_name=song_name,
                        category='quick_win',
                        reason=reason,
                        health_score=score,
                        grade=grade,
                        potential_gain=potential,
                        days_since_worked=days_since
                    ))
                else:
                    # More work needed
                    potential = min(20, 80 - score)
                    reason = f"{critical} critical issues need fixing"
                    deep_work.append(WorkItem(
                        project_id=project_id,
                        song_name=song_name,
                        category='deep_work',
                        reason=reason,
                        health_score=score,
                        grade=grade,
                        potential_gain=potential,
                        days_since_worked=days_since
                    ))
            elif grade == 'B':
                # Ready to polish - close to Grade A
                potential = 80 - score
                if potential > 0:
                    reason = f"Just {potential} points from Grade A"
                    ready_to_polish.append(WorkItem(
                        project_id=project_id,
                        song_name=song_name,
                        category='ready_to_polish',
                        reason=reason,
                        health_score=score,
                        grade=grade,
                        potential_gain=potential,
                        days_since_worked=days_since
                    ))

        # Sort by potential gain and days since worked (prioritize neglected projects)
        def sort_key(item):
            # Higher potential gain = better
            # More days since worked = better (prioritize neglected projects)
            days_bonus = (item.days_since_worked or 0) * 0.5  # 0.5 points per day
            return item.potential_gain + days_bonus

        quick_wins.sort(key=sort_key, reverse=True)
        deep_work.sort(key=sort_key, reverse=True)
        ready_to_polish.sort(key=sort_key, reverse=True)

        total = len(quick_wins) + len(deep_work) + len(ready_to_polish)

        return TodaysFocus(
            quick_wins=quick_wins[:3],
            deep_work=deep_work[:3],
            ready_to_polish=ready_to_polish[:3],
            total_suggestions=total
        )
    except Exception:
        return TodaysFocus()


def get_dashboard_home_data() -> DashboardHome:
    """Fetch data for the home page."""
    try:
        from database import get_library_status, get_db

        db = get_db()
        if not db.is_initialized():
            return DashboardHome()

        status, message = get_library_status()
        if status is None:
            return DashboardHome()

        # Build grade distribution dict
        grade_dist = {}
        for gd in status.grade_distribution:
            grade_dist[gd.grade] = gd.count

        # Get today's focus recommendations
        todays_focus = get_todays_focus()

        return DashboardHome(
            total_projects=status.total_projects,
            total_versions=status.total_versions,
            total_issues=status.total_issues,
            last_scan_date=status.last_scan_date.strftime('%Y-%m-%d') if status.last_scan_date else None,
            grade_distribution=grade_dist,
            ready_to_release=status.ready_to_release,
            needs_attention=status.needs_work,
            todays_focus=todays_focus if todays_focus.total_suggestions > 0 else None
        )
    except Exception:
        return DashboardHome()


def get_project_list_data() -> List[ProjectListItem]:
    """Fetch project list data."""
    try:
        from database import list_projects, get_db

        db = get_db()
        if not db.is_initialized():
            return []

        projects, stats = list_projects(sort_by='name')

        result = []
        for p in projects:
            result.append(ProjectListItem(
                id=p.id,
                song_name=p.song_name,
                folder_path=p.folder_path,
                version_count=p.version_count,
                best_score=p.best_score,
                best_grade=p.best_grade,
                latest_score=p.latest_score,
                latest_grade=p.latest_grade,
                trend=p.trend,
                last_scanned=p.latest_scanned_at.strftime('%Y-%m-%d') if p.latest_scanned_at else ''
            ))

        return result
    except Exception:
        return []


def get_project_detail_data(project_id: int) -> Optional[ProjectDetail]:
    """Fetch project detail data."""
    try:
        from database import get_db

        db = get_db()
        if not db.is_initialized():
            return None

        conn = db.connection
        cursor = conn.cursor()

        # Get project info
        cursor.execute(
            "SELECT id, folder_path, song_name FROM projects WHERE id = ?",
            (project_id,)
        )
        project_row = cursor.fetchone()
        if not project_row:
            return None

        project = ProjectDetail(
            id=project_row['id'],
            song_name=project_row['song_name'],
            folder_path=project_row['folder_path']
        )

        # Get versions
        cursor.execute("""
            SELECT id, als_path, als_filename, health_score, grade,
                   total_issues, critical_issues, warning_issues, scanned_at
            FROM versions
            WHERE project_id = ?
            ORDER BY scanned_at ASC
        """, (project_id,))

        versions = []
        best_idx = -1
        best_score = -1
        prev_score = None

        for i, row in enumerate(cursor.fetchall()):
            delta = None
            if prev_score is not None:
                delta = row['health_score'] - prev_score
            prev_score = row['health_score']

            is_best = row['health_score'] > best_score
            if is_best:
                best_score = row['health_score']
                best_idx = i

            versions.append(VersionDetail(
                id=row['id'],
                filename=row['als_filename'],
                path=row['als_path'],
                health_score=row['health_score'],
                grade=row['grade'],
                total_issues=row['total_issues'],
                critical_issues=row['critical_issues'],
                warning_issues=row['warning_issues'],
                scanned_at=row['scanned_at'][:10] if row['scanned_at'] else '',
                delta=delta,
                is_best=False,
                is_current=False
            ))

        # Mark best and current
        if versions:
            versions[best_idx].is_best = True
            versions[-1].is_current = True
            project.best_version = versions[best_idx]
            project.current_version = versions[-1]

        project.versions = versions

        # Get issues for current version
        if project.current_version:
            cursor.execute("""
                SELECT id, track_name, severity, category, description, fix_suggestion
                FROM issues
                WHERE version_id = ?
                ORDER BY
                    CASE severity
                        WHEN 'critical' THEN 1
                        WHEN 'warning' THEN 2
                        ELSE 3
                    END
            """, (project.current_version.id,))

            for row in cursor.fetchall():
                project.issues.append(IssueDetail(
                    id=row['id'],
                    track_name=row['track_name'] or 'Unknown',
                    severity=row['severity'] or 'warning',
                    category=row['category'] or 'general',
                    description=row['description'] or '',
                    fix_suggestion=row['fix_suggestion']
                ))

        return project
    except Exception:
        return None


def get_insights_data() -> Dict[str, Any]:
    """Fetch insights data."""
    try:
        from database import get_insights, get_db

        db = get_db()
        if not db.is_initialized():
            return {'has_sufficient_data': False, 'helpful_patterns': [], 'harmful_patterns': [], 'common_mistakes': []}

        result, message = get_insights()

        if result is None or not result.has_sufficient_data:
            return {'has_sufficient_data': False, 'helpful_patterns': [], 'harmful_patterns': [], 'common_mistakes': []}

        helpful = []
        for p in result.patterns_that_help:
            helpful.append({
                'description': f"{p.change_type} {p.device_type or ''} on {p.track_type or 'any track'}".strip(),
                'avg_impact': p.avg_health_delta,
                'occurrences': p.occurrences,
                'confidence': p.confidence
            })

        harmful = []
        for p in result.patterns_that_hurt:
            harmful.append({
                'description': f"{p.change_type} {p.device_type or ''} on {p.track_type or 'any track'}".strip(),
                'avg_impact': p.avg_health_delta,
                'occurrences': p.occurrences,
                'confidence': p.confidence
            })

        mistakes = []
        for m in result.common_mistakes:
            mistakes.append({
                'description': f"{m.change_type} {m.device_type or ''} on {m.track_type or 'any track'}".strip(),
                'avg_impact': m.avg_health_delta,
                'occurrences': m.occurrences
            })

        return {
            'has_sufficient_data': True,
            'helpful_patterns': helpful,
            'harmful_patterns': harmful,
            'common_mistakes': mistakes
        }
    except Exception:
        return {'has_sufficient_data': False, 'helpful_patterns': [], 'harmful_patterns': [], 'common_mistakes': []}


def get_database_info() -> Dict[str, Any]:
    """Get database information for settings page."""
    try:
        from database import get_db, DEFAULT_DB_PATH

        db = get_db()

        if not db.is_initialized():
            return {
                'path': str(DEFAULT_DB_PATH),
                'total_projects': 0,
                'total_versions': 0
            }

        conn = db.connection
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM projects")
        total_projects = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM versions")
        total_versions = cursor.fetchone()[0]

        return {
            'path': str(DEFAULT_DB_PATH),
            'total_projects': total_projects,
            'total_versions': total_versions
        }
    except Exception:
        from database import DEFAULT_DB_PATH
        return {
            'path': str(DEFAULT_DB_PATH),
            'total_projects': 0,
            'total_versions': 0
        }


def get_comparison_data(project_id: int, version_a_id: int, version_b_id: int) -> Optional[ComparisonResult]:
    """Fetch comparison data for two versions."""
    try:
        from database import get_db

        db = get_db()
        if not db.is_initialized():
            return None

        conn = db.connection
        cursor = conn.cursor()

        # Get project info
        cursor.execute(
            "SELECT id, folder_path, song_name FROM projects WHERE id = ?",
            (project_id,)
        )
        project_row = cursor.fetchone()
        if not project_row:
            return None

        # Get version A
        cursor.execute("""
            SELECT id, als_path, als_filename, health_score, grade,
                   total_issues, critical_issues, warning_issues, scanned_at
            FROM versions
            WHERE id = ? AND project_id = ?
        """, (version_a_id, project_id))
        version_a_row = cursor.fetchone()
        if not version_a_row:
            return None

        # Get version B
        cursor.execute("""
            SELECT id, als_path, als_filename, health_score, grade,
                   total_issues, critical_issues, warning_issues, scanned_at
            FROM versions
            WHERE id = ? AND project_id = ?
        """, (version_b_id, project_id))
        version_b_row = cursor.fetchone()
        if not version_b_row:
            return None

        # Create VersionDetail objects
        version_a = VersionDetail(
            id=version_a_row['id'],
            filename=version_a_row['als_filename'],
            path=version_a_row['als_path'],
            health_score=version_a_row['health_score'],
            grade=version_a_row['grade'],
            total_issues=version_a_row['total_issues'],
            critical_issues=version_a_row['critical_issues'],
            warning_issues=version_a_row['warning_issues'],
            scanned_at=version_a_row['scanned_at'][:10] if version_a_row['scanned_at'] else ''
        )

        version_b = VersionDetail(
            id=version_b_row['id'],
            filename=version_b_row['als_filename'],
            path=version_b_row['als_path'],
            health_score=version_b_row['health_score'],
            grade=version_b_row['grade'],
            total_issues=version_b_row['total_issues'],
            critical_issues=version_b_row['critical_issues'],
            warning_issues=version_b_row['warning_issues'],
            scanned_at=version_b_row['scanned_at'][:10] if version_b_row['scanned_at'] else ''
        )

        # Get issues for version A
        cursor.execute("""
            SELECT track_name, severity, description
            FROM issues WHERE version_id = ?
        """, (version_a_id,))
        issues_a = {
            f"{r['track_name']}:{r['description']}": {
                'track_name': r['track_name'] or 'Unknown',
                'severity': r['severity'] or 'warning',
                'description': r['description'] or ''
            }
            for r in cursor.fetchall()
        }

        # Get issues for version B
        cursor.execute("""
            SELECT track_name, severity, description
            FROM issues WHERE version_id = ?
        """, (version_b_id,))
        issues_b = {
            f"{r['track_name']}:{r['description']}": {
                'track_name': r['track_name'] or 'Unknown',
                'severity': r['severity'] or 'warning',
                'description': r['description'] or ''
            }
            for r in cursor.fetchall()
        }

        # Calculate differences
        issues_added = []
        issues_removed = []
        issues_unchanged = []

        # Issues in B but not in A (added)
        for key, issue in issues_b.items():
            if key not in issues_a:
                issues_added.append(ComparisonIssue(
                    track_name=issue['track_name'],
                    severity=issue['severity'],
                    description=issue['description'],
                    status='added'
                ))

        # Issues in A but not in B (removed)
        for key, issue in issues_a.items():
            if key not in issues_b:
                issues_removed.append(ComparisonIssue(
                    track_name=issue['track_name'],
                    severity=issue['severity'],
                    description=issue['description'],
                    status='removed'
                ))

        # Issues in both (unchanged)
        for key, issue in issues_a.items():
            if key in issues_b:
                issues_unchanged.append(ComparisonIssue(
                    track_name=issue['track_name'],
                    severity=issue['severity'],
                    description=issue['description'],
                    status='unchanged'
                ))

        # Get device changes from the changes table (if available)
        track_breakdown = []
        devices_added = 0
        devices_removed = 0

        try:
            cursor.execute("""
                SELECT change_type, track_name, device_name, device_type, details
                FROM changes
                WHERE project_id = ? AND before_version_id = ? AND after_version_id = ?
                ORDER BY track_name, change_type
            """, (project_id, version_a_id, version_b_id))

            # Group changes by track
            track_changes: Dict[str, List[DeviceChange]] = {}
            for row in cursor.fetchall():
                track = row['track_name'] or 'Unknown'
                change = DeviceChange(
                    track_name=track,
                    device_name=row['device_name'] or '',
                    device_type=row['device_type'] or '',
                    change_type=row['change_type'] or '',
                    details=row['details'] or ''
                )
                if track not in track_changes:
                    track_changes[track] = []
                track_changes[track].append(change)

                if row['change_type'] == 'device_added':
                    devices_added += 1
                elif row['change_type'] == 'device_removed':
                    devices_removed += 1

            # Build track breakdown
            all_tracks = set(track_changes.keys())
            # Add tracks with issue changes
            for issue in issues_added + issues_removed:
                all_tracks.add(issue.track_name)

            for track in sorted(all_tracks):
                changes = track_changes.get(track, [])

                # Count issues for this track
                track_issues_added = len([i for i in issues_added if i.track_name == track])
                track_issues_removed = len([i for i in issues_removed if i.track_name == track])

                # Determine status
                if any(c.change_type == 'track_added' for c in changes):
                    status = 'added'
                elif any(c.change_type == 'track_removed' for c in changes):
                    status = 'removed'
                elif changes or track_issues_added or track_issues_removed:
                    status = 'modified'
                else:
                    status = 'unchanged'

                # Build summary
                parts = []
                dev_added = len([c for c in changes if c.change_type == 'device_added'])
                dev_removed = len([c for c in changes if c.change_type == 'device_removed'])
                dev_enabled = len([c for c in changes if c.change_type == 'device_enabled'])
                dev_disabled = len([c for c in changes if c.change_type == 'device_disabled'])

                if dev_added:
                    parts.append(f"+{dev_added} device{'s' if dev_added != 1 else ''}")
                if dev_removed:
                    parts.append(f"-{dev_removed} device{'s' if dev_removed != 1 else ''}")
                if dev_enabled:
                    parts.append(f"{dev_enabled} enabled")
                if dev_disabled:
                    parts.append(f"{dev_disabled} disabled")
                if track_issues_added:
                    parts.append(f"+{track_issues_added} issue{'s' if track_issues_added != 1 else ''}")
                if track_issues_removed:
                    parts.append(f"-{track_issues_removed} issue{'s' if track_issues_removed != 1 else ''}")

                net_change = ", ".join(parts) if parts else "no changes"

                track_breakdown.append(TrackBreakdown(
                    track_name=track,
                    status=status,
                    device_changes=changes,
                    issues_added=track_issues_added,
                    issues_removed=track_issues_removed,
                    net_change=net_change
                ))
        except Exception:
            # Changes table might not exist or have data
            pass

        # Calculate metrics
        health_delta = version_b.health_score - version_a.health_score
        grade_change = f"{version_a.grade} → {version_b.grade}"
        is_improvement = health_delta > 0

        return ComparisonResult(
            project_id=project_id,
            song_name=project_row['song_name'],
            version_a=version_a,
            version_b=version_b,
            health_delta=health_delta,
            grade_change=grade_change,
            issues_added=issues_added,
            issues_removed=issues_removed,
            issues_unchanged=issues_unchanged,
            track_breakdown=track_breakdown,
            devices_added=devices_added,
            devices_removed=devices_removed,
            is_improvement=is_improvement
        )
    except Exception:
        return None


def get_project_versions(project_id: int) -> List[VersionDetail]:
    """Get all versions for a project (for comparison dropdowns)."""
    try:
        from database import get_db

        db = get_db()
        if not db.is_initialized():
            return []

        conn = db.connection
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, als_path, als_filename, health_score, grade,
                   total_issues, critical_issues, warning_issues, scanned_at
            FROM versions
            WHERE project_id = ?
            ORDER BY scanned_at ASC
        """, (project_id,))

        versions = []
        for row in cursor.fetchall():
            versions.append(VersionDetail(
                id=row['id'],
                filename=row['als_filename'],
                path=row['als_path'],
                health_score=row['health_score'],
                grade=row['grade'],
                total_issues=row['total_issues'],
                critical_issues=row['critical_issues'],
                warning_issues=row['warning_issues'],
                scanned_at=row['scanned_at'][:10] if row['scanned_at'] else ''
            ))

        return versions
    except Exception:
        return []


# ============================================================================
# Dashboard Runner
# ============================================================================

def run_dashboard(
    port: int = 5000,
    host: str = '127.0.0.1',
    debug: bool = False,
    no_browser: bool = False,
    auto_refresh: bool = True,
    refresh_interval: int = 30
) -> None:
    """
    Start the dashboard web server.

    Args:
        port: Port number to listen on
        host: Host to bind to
        debug: Enable Flask debug mode
        no_browser: Don't auto-open browser
        auto_refresh: Enable auto-refresh of pages
        refresh_interval: Refresh interval in seconds
    """
    config = DashboardConfig(
        port=port,
        host=host,
        debug=debug,
        auto_open=not no_browser,
        auto_refresh=auto_refresh,
        refresh_interval=refresh_interval
    )

    app = create_dashboard_app(config)

    # Open browser after short delay
    if config.auto_open:
        url = f"http://{host}:{port}"
        def open_browser():
            time.sleep(1)
            webbrowser.open(url)
        threading.Thread(target=open_browser, daemon=True).start()

    # Run the app
    app.run(
        host=host,
        port=port,
        debug=debug,
        use_reloader=debug
    )


if __name__ == '__main__':
    run_dashboard(no_browser=True)
