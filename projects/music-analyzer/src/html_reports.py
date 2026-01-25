"""
HTML Report Generator for ALS Doctor

Generates self-contained HTML reports for:
- Single project diagnosis (report_project.html)
- Project version history (report_history.html)
- Full library overview (report_library.html)

All reports are self-contained with inline CSS/JS for easy sharing.
Includes interactive Chart.js visualizations for health timeline.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field

try:
    from jinja2 import Environment, BaseLoader, select_autoescape
except ImportError:
    Environment = None
    BaseLoader = None
    select_autoescape = None

# Check if jinja2 is available
JINJA2_AVAILABLE = Environment is not None


@dataclass
class ReportIssue:
    """Issue data for HTML report."""
    track_name: str
    severity: str  # 'critical', 'warning', 'suggestion'
    category: str
    description: str
    fix_suggestion: Optional[str] = None


@dataclass
class ReportVersion:
    """Version data for HTML report."""
    id: int
    filename: str
    path: str
    health_score: int
    grade: str
    total_issues: int
    critical_issues: int
    warning_issues: int
    scanned_at: datetime
    delta: Optional[int] = None
    is_best: bool = False
    is_current: bool = False


@dataclass
class ProjectReportData:
    """Data for a single project report."""
    song_name: str
    folder_path: str
    als_filename: str
    als_path: str
    health_score: int
    grade: str
    total_issues: int
    critical_issues: int
    warning_issues: int
    total_devices: int
    disabled_devices: int
    clutter_percentage: float
    scanned_at: datetime
    issues: List[ReportIssue]


@dataclass
class HistoryReportData:
    """Data for a project history report."""
    song_name: str
    folder_path: str
    versions: List[ReportVersion]
    best_version: Optional[ReportVersion]
    current_version: Optional[ReportVersion]


@dataclass
class GradeData:
    """Grade distribution data."""
    grade: str
    count: int
    percentage: float


@dataclass
class LibraryReportData:
    """Data for library overview report."""
    total_projects: int
    total_versions: int
    total_issues: int
    last_scan_date: Optional[datetime]
    grade_distribution: List[GradeData]
    ready_to_release: List[Tuple[str, int, str]]  # (filename, score, song_name)
    needs_work: List[Tuple[str, int, str]]
    projects: List[Dict[str, Any]]  # List of project summaries


def _get_grade_color(grade: str) -> str:
    """Get color for a grade."""
    colors = {
        'A': '#22c55e',  # green
        'B': '#06b6d4',  # cyan
        'C': '#eab308',  # yellow
        'D': '#f97316',  # orange
        'F': '#ef4444',  # red
    }
    return colors.get(grade, '#9ca3af')


def _get_severity_color(severity: str) -> str:
    """Get color for a severity level."""
    colors = {
        'critical': '#ef4444',  # red
        'warning': '#eab308',   # yellow
        'suggestion': '#06b6d4', # cyan
    }
    return colors.get(severity.lower(), '#9ca3af')


def _get_severity_icon(severity: str) -> str:
    """Get icon for a severity level."""
    icons = {
        'critical': '⛔',
        'warning': '⚠️',
        'suggestion': '💡',
    }
    return icons.get(severity.lower(), '•')


@dataclass
class ChartDataPoint:
    """Data point for the health timeline chart."""
    label: str  # Version filename
    score: int  # Health score
    grade: str  # Letter grade
    scanned_at: str  # Date string
    delta: Optional[int] = None
    is_best: bool = False
    is_current: bool = False
    total_issues: int = 0


@dataclass
class TimelineChartData:
    """Complete data for the health timeline chart."""
    labels: List[str] = field(default_factory=list)
    scores: List[int] = field(default_factory=list)
    grades: List[str] = field(default_factory=list)
    dates: List[str] = field(default_factory=list)
    deltas: List[Optional[int]] = field(default_factory=list)
    is_best: List[bool] = field(default_factory=list)
    is_current: List[bool] = field(default_factory=list)
    issues: List[int] = field(default_factory=list)
    best_index: Optional[int] = None
    current_index: Optional[int] = None


def generate_chart_data(versions: List['ReportVersion']) -> TimelineChartData:
    """
    Generate chart data from a list of ReportVersion objects.

    Args:
        versions: List of ReportVersion objects (sorted by date, oldest first)

    Returns:
        TimelineChartData with all chart information
    """
    chart_data = TimelineChartData()

    for i, v in enumerate(versions):
        chart_data.labels.append(v.filename)
        chart_data.scores.append(v.health_score)
        chart_data.grades.append(v.grade)
        chart_data.dates.append(v.scanned_at.strftime('%Y-%m-%d %H:%M') if v.scanned_at else '')
        chart_data.deltas.append(v.delta)
        chart_data.is_best.append(v.is_best)
        chart_data.is_current.append(v.is_current)
        chart_data.issues.append(v.total_issues)

        if v.is_best:
            chart_data.best_index = i
        if v.is_current:
            chart_data.current_index = i

    return chart_data


def chart_data_to_json(chart_data: TimelineChartData) -> str:
    """
    Convert TimelineChartData to JSON for embedding in HTML.

    Args:
        chart_data: TimelineChartData object

    Returns:
        JSON string representation
    """
    import json

    return json.dumps({
        'labels': chart_data.labels,
        'scores': chart_data.scores,
        'grades': chart_data.grades,
        'dates': chart_data.dates,
        'deltas': chart_data.deltas,
        'isBest': chart_data.is_best,
        'isCurrent': chart_data.is_current,
        'issues': chart_data.issues,
        'bestIndex': chart_data.best_index,
        'currentIndex': chart_data.current_index
    })


# Chart.js v4.4.1 minified (subset for line charts with zoom plugin)
# Using CDN reference since full embedded version is too large
# The chart will still work offline - it gracefully degrades to table view
CHARTJS_CDN = """
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1/dist/chartjs-plugin-zoom.min.js"></script>
"""

# Embedded Chart.js config for offline use (minified essential subset)
CHARTJS_FALLBACK = """
<script>
// Minimal chart rendering fallback when CDN unavailable
window.ChartFallback = {
    render: function(ctx, data) {
        var canvas = ctx.canvas;
        ctx.fillStyle = '#94a3b8';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Chart requires internet connection for interactive features.', canvas.width/2, canvas.height/2 - 10);
        ctx.fillText('See table below for version data.', canvas.width/2, canvas.height/2 + 10);
    }
};
</script>
"""

# JavaScript for timeline chart initialization
TIMELINE_CHART_JS = """
<script>
document.addEventListener('DOMContentLoaded', function() {
    const chartData = window.timelineData;
    if (!chartData || !window.Chart) {
        // Fallback if Chart.js didn't load
        if (window.ChartFallback) {
            const canvas = document.getElementById('healthTimeline');
            if (canvas) {
                ChartFallback.render(canvas.getContext('2d'), chartData);
            }
        }
        return;
    }

    const ctx = document.getElementById('healthTimeline');
    if (!ctx) return;

    // Grade zone colors (translucent for background)
    const gradeZones = {
        A: { min: 80, max: 100, color: 'rgba(34, 197, 94, 0.1)', border: '#22c55e' },
        B: { min: 60, max: 79, color: 'rgba(6, 182, 212, 0.1)', border: '#06b6d4' },
        C: { min: 40, max: 59, color: 'rgba(234, 179, 8, 0.1)', border: '#eab308' },
        D: { min: 20, max: 39, color: 'rgba(249, 115, 22, 0.1)', border: '#f97316' },
        F: { min: 0, max: 19, color: 'rgba(239, 68, 68, 0.1)', border: '#ef4444' }
    };

    // Build point styles - star for best, diamond for current, circle for others
    const pointStyles = chartData.scores.map((_, i) => {
        if (chartData.isBest[i]) return 'star';
        if (chartData.isCurrent[i]) return 'rectRot';
        return 'circle';
    });

    // Point sizes - larger for best/current
    const pointRadii = chartData.scores.map((_, i) => {
        if (chartData.isBest[i] || chartData.isCurrent[i]) return 10;
        return 6;
    });

    // Point colors based on grade
    const gradeColors = {
        'A': '#22c55e',
        'B': '#06b6d4',
        'C': '#eab308',
        'D': '#f97316',
        'F': '#ef4444'
    };

    const pointColors = chartData.grades.map(g => gradeColors[g] || '#9ca3af');

    // Detect regressions (negative delta)
    const regressionIndices = [];
    chartData.deltas.forEach((d, i) => {
        if (d !== null && d < -5) {  // Significant regression threshold
            regressionIndices.push(i);
        }
    });

    // Grade zone annotation plugin
    const gradeZonePlugin = {
        id: 'gradeZones',
        beforeDraw: (chart) => {
            const ctx = chart.ctx;
            const chartArea = chart.chartArea;
            const yScale = chart.scales.y;

            Object.entries(gradeZones).forEach(([grade, zone]) => {
                const yTop = yScale.getPixelForValue(zone.max);
                const yBottom = yScale.getPixelForValue(zone.min);

                ctx.save();
                ctx.fillStyle = zone.color;
                ctx.fillRect(
                    chartArea.left,
                    yTop,
                    chartArea.right - chartArea.left,
                    yBottom - yTop
                );
                ctx.restore();
            });
        }
    };

    // Create the chart
    const chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartData.labels,
            datasets: [{
                label: 'Health Score',
                data: chartData.scores,
                borderColor: '#60a5fa',
                backgroundColor: 'rgba(96, 165, 250, 0.1)',
                borderWidth: 2,
                fill: false,
                tension: 0.1,
                pointStyle: pointStyles,
                pointRadius: pointRadii,
                pointBackgroundColor: pointColors,
                pointBorderColor: pointColors,
                pointHoverRadius: 12,
                pointHoverBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#1e293b',
                    titleColor: '#f1f5f9',
                    bodyColor: '#f1f5f9',
                    borderColor: '#475569',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        title: function(items) {
                            const i = items[0].dataIndex;
                            return chartData.labels[i];
                        },
                        label: function(context) {
                            const i = context.dataIndex;
                            const lines = [
                                'Score: ' + chartData.scores[i] + '/100',
                                'Grade: ' + chartData.grades[i]
                            ];
                            if (chartData.deltas[i] !== null) {
                                const delta = chartData.deltas[i];
                                lines.push('Delta: ' + (delta > 0 ? '+' : '') + delta);
                            }
                            lines.push('Issues: ' + chartData.issues[i]);
                            lines.push('Scanned: ' + chartData.dates[i]);
                            if (chartData.isBest[i]) lines.push('★ BEST VERSION');
                            if (chartData.isCurrent[i]) lines.push('◆ CURRENT');
                            return lines;
                        }
                    }
                },
                zoom: {
                    pan: {
                        enabled: true,
                        mode: 'x',
                        modifierKey: null
                    },
                    zoom: {
                        wheel: {
                            enabled: true
                        },
                        pinch: {
                            enabled: true
                        },
                        mode: 'x',
                        onZoomComplete: function({chart}) {
                            // Show reset button when zoomed
                            document.getElementById('resetZoom').style.display = 'inline-block';
                        }
                    }
                }
            },
            scales: {
                y: {
                    min: 0,
                    max: 100,
                    grid: {
                        color: '#334155',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#94a3b8',
                        stepSize: 20,
                        callback: function(value) {
                            const gradeLabels = {100: 'A', 80: 'A', 60: 'B', 40: 'C', 20: 'D', 0: 'F'};
                            return value + (gradeLabels[value] ? ' [' + gradeLabels[value] + ']' : '');
                        }
                    }
                },
                x: {
                    grid: {
                        color: '#334155',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#94a3b8',
                        maxRotation: 45,
                        minRotation: 45
                    }
                }
            }
        },
        plugins: [gradeZonePlugin]
    });

    // Reset zoom button handler
    const resetBtn = document.getElementById('resetZoom');
    if (resetBtn) {
        resetBtn.addEventListener('click', function() {
            chart.resetZoom();
            this.style.display = 'none';
        });
    }

    // Add regression markers annotation
    if (regressionIndices.length > 0) {
        const regList = document.getElementById('regressionList');
        if (regList) {
            regressionIndices.forEach(i => {
                const li = document.createElement('li');
                li.textContent = chartData.labels[i] + ': ' + chartData.deltas[i] + ' points';
                li.style.color = '#ef4444';
                regList.appendChild(li);
            });
        }
    }
});
</script>
"""

# CSS for chart container
CHART_CSS = """
.chart-container {
    position: relative;
    height: 400px;
    width: 100%;
    margin: 1rem 0;
}

.chart-controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}

.chart-legend {
    display: flex;
    gap: 1.5rem;
    flex-wrap: wrap;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    color: var(--text-secondary);
}

.legend-marker {
    width: 12px;
    height: 12px;
    border-radius: 2px;
}

.legend-marker.star {
    clip-path: polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%);
    background: var(--grade-a);
}

.legend-marker.diamond {
    transform: rotate(45deg);
    background: var(--grade-b);
}

.legend-marker.circle {
    border-radius: 50%;
    background: #60a5fa;
}

#resetZoom {
    display: none;
    padding: 0.5rem 1rem;
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-primary);
    cursor: pointer;
    font-size: 0.85rem;
}

#resetZoom:hover {
    background: var(--border-color);
}

.grade-zone-legend {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.5rem;
    flex-wrap: wrap;
}

.grade-zone-item {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.75rem;
    color: var(--text-secondary);
}

.grade-zone-color {
    width: 16px;
    height: 16px;
    border-radius: 2px;
    border: 1px solid;
}

.regression-note {
    margin-top: 1rem;
    padding: 0.75rem;
    background: rgba(239, 68, 68, 0.1);
    border-radius: 8px;
    border-left: 4px solid var(--grade-f);
}

.regression-note h4 {
    color: var(--grade-f);
    margin-bottom: 0.5rem;
    font-size: 0.9rem;
}

.regression-note ul {
    margin: 0;
    padding-left: 1.5rem;
    font-size: 0.85rem;
}

@media (max-width: 600px) {
    .chart-container {
        height: 300px;
    }

    .chart-legend {
        gap: 0.75rem;
    }

    .legend-item {
        font-size: 0.75rem;
    }
}
"""

# Base CSS for all reports (dark mode, mobile responsive)
BASE_CSS = """
:root {
    --bg-primary: #0f172a;
    --bg-secondary: #1e293b;
    --bg-card: #334155;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --border-color: #475569;
    --grade-a: #22c55e;
    --grade-b: #06b6d4;
    --grade-c: #eab308;
    --grade-d: #f97316;
    --grade-f: #ef4444;
    --severity-critical: #ef4444;
    --severity-warning: #eab308;
    --severity-suggestion: #06b6d4;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.6;
    min-height: 100vh;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
}

@media (max-width: 768px) {
    .container {
        padding: 1rem;
    }
}

header {
    text-align: center;
    margin-bottom: 2rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--border-color);
}

header h1 {
    font-size: 1.5rem;
    color: var(--text-primary);
    margin-bottom: 0.5rem;
}

header .subtitle {
    color: var(--text-secondary);
    font-size: 0.9rem;
}

header .generated {
    color: var(--text-secondary);
    font-size: 0.75rem;
    margin-top: 0.5rem;
}

.card {
    background: var(--bg-secondary);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
    border: 1px solid var(--border-color);
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid var(--border-color);
}

.card-title {
    font-size: 1.1rem;
    font-weight: 600;
}

.health-gauge {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2rem;
}

.health-score {
    font-size: 4rem;
    font-weight: 700;
    line-height: 1;
}

.health-grade {
    font-size: 2rem;
    font-weight: 600;
    padding: 0.5rem 1.5rem;
    border-radius: 8px;
    margin-top: 1rem;
}

.health-label {
    color: var(--text-secondary);
    margin-top: 0.5rem;
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 1rem;
}

.stat-item {
    background: var(--bg-card);
    padding: 1rem;
    border-radius: 8px;
    text-align: center;
}

.stat-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-primary);
}

.stat-label {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-top: 0.25rem;
}

.issue-list {
    list-style: none;
}

.issue-item {
    display: flex;
    gap: 0.75rem;
    padding: 0.75rem;
    margin-bottom: 0.5rem;
    background: var(--bg-card);
    border-radius: 8px;
    border-left: 4px solid;
}

.issue-item.critical {
    border-left-color: var(--severity-critical);
}

.issue-item.warning {
    border-left-color: var(--severity-warning);
}

.issue-item.suggestion {
    border-left-color: var(--severity-suggestion);
}

.issue-icon {
    font-size: 1.2rem;
    flex-shrink: 0;
}

.issue-content {
    flex: 1;
}

.issue-track {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-bottom: 0.25rem;
}

.issue-description {
    margin-bottom: 0.25rem;
}

.issue-fix {
    font-size: 0.85rem;
    color: var(--text-secondary);
    font-style: italic;
}

.version-table {
    width: 100%;
    border-collapse: collapse;
}

.version-table th,
.version-table td {
    padding: 0.75rem;
    text-align: left;
    border-bottom: 1px solid var(--border-color);
}

.version-table th {
    color: var(--text-secondary);
    font-weight: 500;
    font-size: 0.85rem;
}

.version-table tr:hover {
    background: var(--bg-card);
}

.version-table .best-marker {
    color: var(--grade-a);
}

.delta-positive {
    color: var(--grade-a);
}

.delta-negative {
    color: var(--grade-f);
}

.grade-bar-container {
    margin-bottom: 1rem;
}

.grade-bar-label {
    display: flex;
    justify-content: space-between;
    margin-bottom: 0.25rem;
}

.grade-bar {
    height: 24px;
    background: var(--bg-card);
    border-radius: 4px;
    overflow: hidden;
}

.grade-bar-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s ease;
}

.project-list {
    list-style: none;
}

.project-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem;
    margin-bottom: 0.5rem;
    background: var(--bg-card);
    border-radius: 8px;
}

.project-name {
    font-weight: 500;
}

.project-score {
    font-weight: 600;
}

.summary-section {
    margin-bottom: 1.5rem;
}

.summary-section h3 {
    color: var(--text-secondary);
    font-size: 0.9rem;
    margin-bottom: 0.75rem;
}

footer {
    text-align: center;
    padding: 2rem;
    color: var(--text-secondary);
    font-size: 0.8rem;
    border-top: 1px solid var(--border-color);
    margin-top: 2rem;
}

/* Responsive adjustments */
@media (max-width: 600px) {
    .health-score {
        font-size: 3rem;
    }

    .stats-grid {
        grid-template-columns: repeat(2, 1fr);
    }

    .version-table {
        font-size: 0.85rem;
    }

    .version-table th,
    .version-table td {
        padding: 0.5rem;
    }
}
"""

# Project Report Template
PROJECT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ALS Doctor Report - {{ data.song_name }}</title>
    <style>{{ css }}</style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🩺 ALS Doctor Report</h1>
            <div class="subtitle">{{ data.song_name }}</div>
            <div class="generated">Generated: {{ generated_at }}</div>
        </header>

        <div class="card">
            <div class="card-header">
                <span class="card-title">Health Score</span>
                <span>{{ data.als_filename }}</span>
            </div>
            <div class="health-gauge">
                <div class="health-score" style="color: {{ grade_color }}">{{ data.health_score }}</div>
                <div class="health-grade" style="background: {{ grade_color }}20; color: {{ grade_color }}">
                    Grade {{ data.grade }}
                </div>
                <div class="health-label">out of 100</div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <span class="card-title">Project Statistics</span>
            </div>
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-value">{{ data.total_devices }}</div>
                    <div class="stat-label">Total Devices</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{{ data.disabled_devices }}</div>
                    <div class="stat-label">Disabled</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{{ data.total_issues }}</div>
                    <div class="stat-label">Issues Found</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{{ "%.1f"|format(data.clutter_percentage) }}%</div>
                    <div class="stat-label">Clutter</div>
                </div>
            </div>
        </div>

        {% if data.issues %}
        <div class="card">
            <div class="card-header">
                <span class="card-title">Issues Found ({{ data.total_issues }})</span>
                <span>{{ data.critical_issues }} critical, {{ data.warning_issues }} warnings</span>
            </div>
            <ul class="issue-list">
                {% for issue in data.issues %}
                <li class="issue-item {{ issue.severity }}">
                    <span class="issue-icon">{{ get_severity_icon(issue.severity) }}</span>
                    <div class="issue-content">
                        {% if issue.track_name %}
                        <div class="issue-track">{{ issue.track_name }}</div>
                        {% endif %}
                        <div class="issue-description">{{ issue.description }}</div>
                        {% if issue.fix_suggestion %}
                        <div class="issue-fix">Fix: {{ issue.fix_suggestion }}</div>
                        {% endif %}
                    </div>
                </li>
                {% endfor %}
            </ul>
        </div>
        {% else %}
        <div class="card">
            <div class="card-header">
                <span class="card-title">No Issues Found</span>
            </div>
            <p style="text-align: center; padding: 2rem; color: var(--grade-a);">
                ✓ Your project looks great!
            </p>
        </div>
        {% endif %}

        <footer>
            <p>ALS Doctor - Ableton Live Set Health Analyzer</p>
            <p>Path: {{ data.als_path }}</p>
        </footer>
    </div>
</body>
</html>"""

# History Report Template (with interactive timeline chart)
HISTORY_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Version History - {{ data.song_name }}</title>
    <style>{{ css }}{{ chart_css }}</style>
    {{ chartjs_cdn }}
    {{ chartjs_fallback }}
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 Version History</h1>
            <div class="subtitle">{{ data.song_name }}</div>
            <div class="generated">Generated: {{ generated_at }}</div>
        </header>

        {% if data.best_version and data.current_version %}
        <div class="card">
            <div class="card-header">
                <span class="card-title">Summary</span>
            </div>
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-value">{{ data.versions|length }}</div>
                    <div class="stat-label">Total Versions</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color: {{ get_grade_color(data.best_version.grade) }}">
                        {{ data.best_version.health_score }}
                    </div>
                    <div class="stat-label">Best Score</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color: {{ get_grade_color(data.current_version.grade) }}">
                        {{ data.current_version.health_score }}
                    </div>
                    <div class="stat-label">Current Score</div>
                </div>
                {% if data.best_version.health_score != data.current_version.health_score %}
                <div class="stat-item">
                    <div class="stat-value {% if data.current_version.health_score < data.best_version.health_score %}delta-negative{% else %}delta-positive{% endif %}">
                        {{ data.current_version.health_score - data.best_version.health_score }}
                    </div>
                    <div class="stat-label">vs Best</div>
                </div>
                {% endif %}
            </div>
        </div>
        {% endif %}

        {% if data.versions|length > 1 %}
        <div class="card">
            <div class="card-header">
                <span class="card-title">Health Timeline</span>
                <button id="resetZoom">Reset Zoom</button>
            </div>
            <div class="chart-controls">
                <div class="chart-legend">
                    <div class="legend-item">
                        <div class="legend-marker star"></div>
                        <span>Best Version</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-marker diamond"></div>
                        <span>Current</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-marker circle"></div>
                        <span>Version</span>
                    </div>
                </div>
            </div>
            <div class="chart-container">
                <canvas id="healthTimeline"></canvas>
            </div>
            <div class="grade-zone-legend">
                <div class="grade-zone-item">
                    <div class="grade-zone-color" style="background: rgba(34, 197, 94, 0.2); border-color: #22c55e;"></div>
                    <span>A (80-100)</span>
                </div>
                <div class="grade-zone-item">
                    <div class="grade-zone-color" style="background: rgba(6, 182, 212, 0.2); border-color: #06b6d4;"></div>
                    <span>B (60-79)</span>
                </div>
                <div class="grade-zone-item">
                    <div class="grade-zone-color" style="background: rgba(234, 179, 8, 0.2); border-color: #eab308;"></div>
                    <span>C (40-59)</span>
                </div>
                <div class="grade-zone-item">
                    <div class="grade-zone-color" style="background: rgba(249, 115, 22, 0.2); border-color: #f97316;"></div>
                    <span>D (20-39)</span>
                </div>
                <div class="grade-zone-item">
                    <div class="grade-zone-color" style="background: rgba(239, 68, 68, 0.2); border-color: #ef4444;"></div>
                    <span>F (0-19)</span>
                </div>
            </div>
            {% if has_regressions %}
            <div class="regression-note">
                <h4>⚠️ Significant Regressions Detected</h4>
                <ul id="regressionList"></ul>
            </div>
            {% endif %}
        </div>
        {% endif %}

        <div class="card">
            <div class="card-header">
                <span class="card-title">Version Details</span>
            </div>
            <table class="version-table">
                <thead>
                    <tr>
                        <th></th>
                        <th>Version</th>
                        <th>Score</th>
                        <th>Grade</th>
                        <th>Delta</th>
                        <th>Issues</th>
                        <th>Scanned</th>
                    </tr>
                </thead>
                <tbody>
                    {% for version in data.versions %}
                    <tr>
                        <td>
                            {% if version.is_best %}
                            <span class="best-marker" title="Best Version">★</span>
                            {% elif version.is_current %}
                            <span style="color: var(--grade-b);" title="Current Version">◆</span>
                            {% endif %}
                        </td>
                        <td>{{ version.filename }}</td>
                        <td>{{ version.health_score }}</td>
                        <td style="color: {{ get_grade_color(version.grade) }}">{{ version.grade }}</td>
                        <td>
                            {% if version.delta is not none %}
                            <span class="{% if version.delta > 0 %}delta-positive{% elif version.delta < 0 %}delta-negative{% endif %}">
                                {% if version.delta > 0 %}+{% endif %}{{ version.delta }}
                            </span>
                            {% else %}
                            --
                            {% endif %}
                        </td>
                        <td>{{ version.total_issues }}</td>
                        <td>{{ version.scanned_at.strftime('%Y-%m-%d %H:%M') if version.scanned_at else '--' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        {% if data.best_version and data.current_version and data.best_version.id != data.current_version.id %}
        <div class="card">
            <div class="card-header">
                <span class="card-title">Recommendation</span>
            </div>
            <p style="padding: 1rem;">
                {% if data.current_version.health_score < data.best_version.health_score %}
                Your current version ({{ data.current_version.health_score }}) has a lower health score than your best version ({{ data.best_version.health_score }}).
                Consider reviewing the changes since <strong>{{ data.best_version.filename }}</strong> to understand what may have caused the decline.
                {% else %}
                Great job! Your current version is performing well.
                {% endif %}
            </p>
        </div>
        {% endif %}

        <footer>
            <p>ALS Doctor - Ableton Live Set Health Analyzer</p>
            <p>Path: {{ data.folder_path }}</p>
        </footer>
    </div>

    <script>
    // Timeline chart data
    window.timelineData = {{ chart_data_json | safe }};
    </script>
    {{ timeline_chart_js }}
</body>
</html>"""

# Library Report Template
LIBRARY_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Library Status - ALS Doctor</title>
    <style>{{ css }}</style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📚 Library Status</h1>
            <div class="subtitle">{{ data.total_projects }} Projects • {{ data.total_versions }} Versions</div>
            <div class="generated">Generated: {{ generated_at }}</div>
        </header>

        <div class="card">
            <div class="card-header">
                <span class="card-title">Overview</span>
            </div>
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-value">{{ data.total_projects }}</div>
                    <div class="stat-label">Projects</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{{ data.total_versions }}</div>
                    <div class="stat-label">Versions</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{{ data.total_issues }}</div>
                    <div class="stat-label">Total Issues</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{{ data.last_scan_date.strftime('%Y-%m-%d') if data.last_scan_date else '--' }}</div>
                    <div class="stat-label">Last Scan</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <span class="card-title">Grade Distribution</span>
            </div>
            {% for grade in data.grade_distribution %}
            <div class="grade-bar-container">
                <div class="grade-bar-label">
                    <span style="color: {{ get_grade_color(grade.grade) }}">Grade {{ grade.grade }}</span>
                    <span>{{ grade.count }} ({{ "%.1f"|format(grade.percentage) }}%)</span>
                </div>
                <div class="grade-bar">
                    <div class="grade-bar-fill" style="width: {{ grade.percentage }}%; background: {{ get_grade_color(grade.grade) }}"></div>
                </div>
            </div>
            {% endfor %}
        </div>

        {% if data.ready_to_release %}
        <div class="card">
            <div class="card-header">
                <span class="card-title" style="color: var(--grade-a)">✓ Ready to Release</span>
            </div>
            <ul class="project-list">
                {% for item in data.ready_to_release %}
                <li class="project-item">
                    <span class="project-name">{{ item[2] }} - {{ item[0] }}</span>
                    <span class="project-score" style="color: var(--grade-a)">{{ item[1] }}</span>
                </li>
                {% endfor %}
            </ul>
        </div>
        {% endif %}

        {% if data.needs_work %}
        <div class="card">
            <div class="card-header">
                <span class="card-title" style="color: var(--grade-f)">⚠ Needs Attention</span>
            </div>
            <ul class="project-list">
                {% for item in data.needs_work %}
                <li class="project-item">
                    <span class="project-name">{{ item[2] }} - {{ item[0] }}</span>
                    <span class="project-score" style="color: var(--grade-f)">{{ item[1] }}</span>
                </li>
                {% endfor %}
            </ul>
        </div>
        {% endif %}

        {% if data.projects %}
        <div class="card">
            <div class="card-header">
                <span class="card-title">All Projects</span>
            </div>
            <table class="version-table">
                <thead>
                    <tr>
                        <th>Song</th>
                        <th>Versions</th>
                        <th>Best</th>
                        <th>Latest</th>
                        <th>Trend</th>
                    </tr>
                </thead>
                <tbody>
                    {% for project in data.projects %}
                    <tr>
                        <td>{{ project.song_name }}</td>
                        <td>{{ project.version_count }}</td>
                        <td style="color: {{ get_grade_color(project.best_grade) }}">
                            {{ project.best_score }} [{{ project.best_grade }}]
                        </td>
                        <td style="color: {{ get_grade_color(project.latest_grade) }}">
                            {{ project.latest_score }} [{{ project.latest_grade }}]
                        </td>
                        <td>
                            {% if project.trend == 'up' %}
                            <span style="color: var(--grade-a)">↑</span>
                            {% elif project.trend == 'down' %}
                            <span style="color: var(--grade-f)">↓</span>
                            {% elif project.trend == 'new' %}
                            <span style="color: var(--grade-b)">★</span>
                            {% else %}
                            <span>→</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}

        <footer>
            <p>ALS Doctor - Ableton Live Set Health Analyzer</p>
        </footer>
    </div>
</body>
</html>"""


def _create_jinja_env() -> 'Environment':
    """Create a Jinja2 environment with custom functions and auto-escaping."""
    if not JINJA2_AVAILABLE:
        raise ImportError("jinja2 is required for HTML report generation. Install with: pip install jinja2")

    # Enable autoescape for HTML to prevent XSS
    env = Environment(
        loader=BaseLoader(),
        autoescape=select_autoescape(default=True, default_for_string=True)
    )
    env.globals['get_grade_color'] = _get_grade_color
    env.globals['get_severity_icon'] = _get_severity_icon
    return env


def generate_project_report(
    data: ProjectReportData,
    output_path: Optional[Path] = None
) -> Tuple[str, Optional[Path]]:
    """
    Generate an HTML report for a single project diagnosis.

    Args:
        data: ProjectReportData with diagnosis information
        output_path: Optional path to save the HTML file

    Returns:
        Tuple of (html_content, saved_path or None)
    """
    env = _create_jinja_env()
    template = env.from_string(PROJECT_TEMPLATE)

    html = template.render(
        data=data,
        css=BASE_CSS,
        grade_color=_get_grade_color(data.grade),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    saved_path = None
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding='utf-8')
        saved_path = output_path

    return html, saved_path


def generate_history_report(
    data: HistoryReportData,
    output_path: Optional[Path] = None
) -> Tuple[str, Optional[Path]]:
    """
    Generate an HTML report for project version history with interactive timeline chart.

    Args:
        data: HistoryReportData with version history
        output_path: Optional path to save the HTML file

    Returns:
        Tuple of (html_content, saved_path or None)
    """
    env = _create_jinja_env()
    template = env.from_string(HISTORY_TEMPLATE)

    # Generate chart data from versions
    chart_data = generate_chart_data(data.versions)
    chart_data_json = chart_data_to_json(chart_data)

    # Detect if there are significant regressions (delta < -5)
    has_regressions = any(
        v.delta is not None and v.delta < -5
        for v in data.versions
    )

    html = template.render(
        data=data,
        css=BASE_CSS,
        chart_css=CHART_CSS,
        chartjs_cdn=CHARTJS_CDN,
        chartjs_fallback=CHARTJS_FALLBACK,
        timeline_chart_js=TIMELINE_CHART_JS,
        chart_data_json=chart_data_json,
        has_regressions=has_regressions,
        get_grade_color=_get_grade_color,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    saved_path = None
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding='utf-8')
        saved_path = output_path

    return html, saved_path


def generate_library_report(
    data: LibraryReportData,
    output_path: Optional[Path] = None
) -> Tuple[str, Optional[Path]]:
    """
    Generate an HTML report for library overview.

    Args:
        data: LibraryReportData with library statistics
        output_path: Optional path to save the HTML file

    Returns:
        Tuple of (html_content, saved_path or None)
    """
    env = _create_jinja_env()
    template = env.from_string(LIBRARY_TEMPLATE)

    html = template.render(
        data=data,
        css=BASE_CSS,
        get_grade_color=_get_grade_color,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    saved_path = None
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding='utf-8')
        saved_path = output_path

    return html, saved_path


def get_default_report_path(
    report_type: str,
    song_name: Optional[str] = None
) -> Path:
    """
    Get the default path for a report.

    Args:
        report_type: 'project', 'history', or 'library'
        song_name: Song name for project/history reports

    Returns:
        Path for the report file
    """
    reports_dir = Path(__file__).parent.parent.parent.parent / "reports"
    date_str = datetime.now().strftime("%Y-%m-%d")

    if report_type == 'library':
        return reports_dir / f"library_report_{date_str}.html"
    elif song_name:
        # Sanitize song name for filename
        safe_name = "".join(c if c.isalnum() or c in ' -_' else '_' for c in song_name)
        safe_name = safe_name.strip().replace(' ', '_')
        return reports_dir / safe_name / f"{safe_name}_{report_type}_{date_str}.html"
    else:
        return reports_dir / f"{report_type}_report_{date_str}.html"
