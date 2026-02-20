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
