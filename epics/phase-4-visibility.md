# Epic: Phase 4 - Visibility (UI & Dashboard)

**Goal:** Make all the rich data visible and actionable through enhanced CLI output, HTML reports, and a local web dashboard.

**Dependencies:** Phase 1 (Foundation), Phase 2 (Intelligence) for insights, Phase 3 (Automation) for notifications

**Unlocks:** Complete user experience, shareable reports, at-a-glance project management

---

## Strategic Context

The goal is **reducing cognitive load**, not adding more screens. Every visualization should answer a specific question:

- "What should I work on?" → Story 4.6
- "Is my project getting better?" → Story 4.3
- "What changed between versions?" → Story 4.5
- "What's the state of my library?" → Story 4.4

---

## UI Technology Decision

| Approach | Effort | Flexibility | Deployment |
|----------|--------|-------------|------------|
| Enhanced CLI output | Low | Limited | Already there |
| Static HTML reports | Medium | Good | File-based |
| Local web dashboard | High | Excellent | localhost server |
| Electron app | Very High | Excellent | Installable |

**Recommended:** Local web dashboard (Flask/FastAPI on localhost) - good balance of effort vs capability.

---

## Stories

### Story 4.1: Enhanced CLI Output with Colors

**As a** music producer
**I want to** see clearly formatted, colored CLI output
**So that** I can quickly scan results without a UI

**Acceptance Criteria:**
- [ ] All CLI output uses consistent color coding
- [ ] Health grades colored: A=green, B=cyan, C=yellow, D=orange, F=red
- [ ] Issue severity colored: Critical=red, Warning=yellow, Suggestion=cyan, Info=white
- [ ] ASCII progress bars for grade distribution
- [ ] Tables aligned and readable
- [ ] `--no-color` flag for plain text output (for piping/logging)
- [ ] Works in Windows Terminal, PowerShell, and CMD
- [ ] Graceful fallback if terminal doesn't support ANSI colors

**Color Scheme:**
```
Grade A: Green     (#00FF00 / bright green)
Grade B: Cyan      (#00FFFF / bright cyan)
Grade C: Yellow    (#FFFF00 / bright yellow)
Grade D: Orange    (#FFA500 / using yellow+bold as fallback)
Grade F: Red       (#FF0000 / bright red)

Critical: Red background or bold red
Warning: Yellow
Suggestion: Cyan
Info: Default/white

Improvements: Green with + prefix
Regressions: Red with - prefix
```

**Technical Notes:**
- Use `rich` library (preferred) or `colorama` for cross-platform color
- Define color scheme in central config module
- Test on: Windows Terminal, PowerShell, CMD, VS Code terminal

**Effort:** Small
**Dependencies:** None

---

### Story 4.2: HTML Report Generation

**As a** music producer
**I want to** generate shareable HTML reports from analysis
**So that** I can review results in a browser or share with collaborators

**Acceptance Criteria:**
- [ ] `als-doctor diagnose <file> --html [output.html]` generates project report
- [ ] `als-doctor db report <song> --html` generates history report
- [ ] `als-doctor db report --all --html` generates library overview
- [ ] Reports saved to `reports/` folder with timestamp by default
- [ ] Reports are self-contained (inline CSS/JS, no external dependencies)
- [ ] Mobile-friendly responsive design
- [ ] Print-friendly stylesheet
- [ ] Dark mode support (auto-detect OS preference)

**Report Types:**

1. **Project Report** - Single .als analysis
   - Health score gauge
   - Issue list by severity
   - Device breakdown by track
   - Recommendations

2. **History Report** - Project health over time
   - Interactive health timeline chart
   - Version list with deltas
   - Best/worst version highlights
   - Trend analysis

3. **Library Report** - All projects overview
   - Grade distribution chart
   - Project rankings
   - "Needs attention" / "Ready to release" lists
   - Aggregate insights

**File Naming:** `reports/{song}_{date}.html` or `reports/library_{date}.html`

**Technical Notes:**
- Use Jinja2 templates for HTML generation
- Inline Chart.js (minified) for visualizations
- CSS grid/flexbox for responsive layout
- Single-file output with embedded assets
- Template location: `templates/report_*.html`

**Effort:** Medium
**Dependencies:** Phase 1 (data in DB)

---

### Story 4.3: Health Timeline Chart

**As a** music producer
**I want to** see my project's health over time as a visual chart
**So that** I can identify trends and regression points

**Acceptance Criteria:**
- [ ] HTML history reports include interactive health timeline
- [ ] X-axis: scan date/version, Y-axis: health score (0-100)
- [ ] Hover/click shows: version name, score, grade, issues count, date
- [ ] Grade zones marked with background colors (A=green zone, F=red zone)
- [ ] Best version highlighted with star marker
- [ ] Current/latest version highlighted
- [ ] Regression points marked (where score dropped significantly)
- [ ] Can zoom/pan on timeline for projects with many versions
- [ ] Tooltip shows delta from previous version

**Chart Features:**
```
Health Score
100 |----[A ZONE - GREEN]----------------------
    |    ★ 22_2.als (100)
 80 |----[B ZONE - CYAN]-----------------------
    |  ●╱  ╲
 60 |----[C ZONE - YELLOW]---------------------
    | ╱    ●╲  ╱╲
 40 |----[D ZONE - ORANGE]---------------------
    |       ╲╱  ╲●  <- Current (regression!)
 20 |----[F ZONE - RED]------------------------
    |
  0 +--+--+--+--+--+--+--+--+--+--+--+--+->
     v1 v2 v3 v4 v5 v6 v7 v8 v9 v10 v11 v12
```

**Technical Notes:**
- Use Chart.js line chart with plugins
- Background color zones using chart annotation plugin
- Store chart data as JSON embedded in HTML
- Point markers: star for best, circle for normal, triangle for regression

**Effort:** Medium (part of Story 4.2)
**Dependencies:** Story 4.2, Phase 1

---

### Story 4.4: Local Web Dashboard

**As a** music producer
**I want to** view my entire library in a web dashboard
**So that** I have a single place to see all project status

**Acceptance Criteria:**
- [ ] `als-doctor dashboard` starts local web server
- [ ] Dashboard accessible at `http://localhost:8080`
- [ ] `--port N` to specify custom port
- [ ] `--no-browser` to skip auto-opening browser
- [ ] `Ctrl+C` gracefully stops server
- [ ] Auto-refresh when database changes (polling or WebSocket)
- [ ] Responsive design (works on tablet for studio use)

**Pages:**

1. **Home (/)** - At-a-glance library health
   - Overall health score average
   - Grade distribution pie/bar chart
   - "Needs Attention" list (Grade D-F)
   - "Ready to Release" list (Grade A)
   - Recent activity feed
   - Quick actions: Scan, Open project

2. **Projects (/projects)** - Sortable/filterable project list
   - Table: Name, Versions, Best Score, Latest Score, Trend, Last Scanned
   - Sort by any column
   - Filter by grade, search by name
   - Click row to go to detail

3. **Project Detail (/project/<id>)** - Deep dive on single project
   - Health timeline chart
   - Current issues list
   - Version history table
   - Compare versions (link to 4.5)
   - Quick actions: Coach, Diagnose, Open folder

4. **Insights (/insights)** - Your patterns and common mistakes
   - Patterns that help/hurt (from Phase 2)
   - Your common mistakes
   - Style profile summary
   - Requires Phase 2 data

5. **Settings (/settings)** - Configuration
   - Watch folder path
   - Scan schedule
   - Notification preferences
   - Theme (light/dark)

**Technical Notes:**
- Flask or FastAPI backend
- Simple HTML/CSS/JS frontend - consider htmx for interactivity
- No heavy frontend framework (React/Vue) - keep it simple
- SQLite queries for all data
- Consider Tailwind CSS for styling
- WebSocket or SSE for live updates (optional, polling OK for MVP)

**Effort:** Large
**Dependencies:** Phase 1 (DB), Phase 2 (insights page)

---

### Story 4.5: Side-by-Side Version Comparison View

**As a** music producer
**I want to** visually compare two versions side by side
**So that** I can see exactly what changed

**Acceptance Criteria:**
- [ ] Dashboard includes comparison page at `/project/<id>/compare`
- [ ] Dropdown selectors for version A (before) and version B (after)
- [ ] URL supports direct linking: `/project/22/compare?a=22_2.als&b=22_12.als`
- [ ] Shows: health delta, grade change, issues added/removed, devices changed
- [ ] Color-coded diff: green=improvement, red=regression, yellow=neutral
- [ ] Expandable track-by-track breakdown
- [ ] Link to open either version's folder in explorer
- [ ] "Swap A/B" button to reverse comparison

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  COMPARE VERSIONS                    [Swap] [Close]     │
├─────────────────────────┬───────────────────────────────┤
│  VERSION A (Before)     │  VERSION B (After)            │
│  [Dropdown: 22_2.als ▼] │  [Dropdown: 22_12.als ▼]     │
├─────────────────────────┼───────────────────────────────┤
│  Score: 100 [A]         │  Score: 45 [C]                │
│  Issues: 0              │  Issues: 12                   │
│  Devices: 38            │  Devices: 67                  │
│  Clutter: 5%            │  Clutter: 34%                 │
├─────────────────────────┴───────────────────────────────┤
│                                                         │
│  SUMMARY: -55 health, +12 issues, +29 devices  [WORSE]  │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  CHANGES BY TRACK                              [Expand] │
│  ▼ Bass (+4 devices, +3 issues)                        │
│      + EQ Eight (duplicate)                             │
│      + EQ Eight (duplicate)                             │
│      + Compressor2 (ratio: 20:1 - extreme)              │
│      + Compressor2 (duplicate)                          │
│  ▶ Lead (+8 devices, +2 issues)                        │
│  ▶ Master (+2 devices, +1 issue)                       │
├─────────────────────────────────────────────────────────┤
│  RECOMMENDATION                                         │
│  Consider rolling back to 22_2.als - significant        │
│  regression detected.                                   │
└─────────────────────────────────────────────────────────┘
```

**Technical Notes:**
- Reuse project_differ.py for diff data
- Lazy-load track details on expand
- Deep link support for sharing comparisons

**Effort:** Medium
**Dependencies:** Story 4.4 (dashboard infrastructure)

---

### Story 4.6: "What Should I Work On?" View

**As a** music producer
**I want to** see a prioritized list of what to work on today
**So that** I can start producing instead of deciding

**Acceptance Criteria:**
- [ ] Dashboard home prominently features "Today's Focus" section
- [ ] Three categories with different time commitments:
  - **Quick Wins** (15-30 min): Grade C projects needing 1-2 fixes to reach B
  - **Deep Work** (1-2 hours): Grade D projects with improvement potential
  - **Ready to Polish** (30 min): Grade A/B projects for final touches
- [ ] Click project to go to detail or start coach mode
- [ ] "I worked on this" button marks project as touched today
- [ ] "Not today" button hides project from today's list
- [ ] Respects user's project number filter (--min-number equivalent)
- [ ] Refreshes daily or on manual refresh

**Prioritization Algorithm:**
```python
score = base_potential

# Boost projects not touched recently
if days_since_last_work > 7:
    score += 20
elif days_since_last_work > 3:
    score += 10

# Boost projects with momentum (recently improved)
if recent_improvement > 0:
    score += recent_improvement

# Boost "almost there" projects (Grade C close to B)
if grade == 'C' and health_score >= 55:
    score += 15  # Quick win potential

# Penalize projects touched today
if touched_today:
    score -= 50
```

**Technical Notes:**
- Store `last_worked_at` timestamp in projects table
- Store `hidden_until` for "not today" feature
- Recalculate recommendations on page load
- Consider user work patterns over time (Phase 2 integration)

**Effort:** Medium
**Dependencies:** Story 4.4 (dashboard), Phase 1, Phase 2 enhances this

---

### Story 4.7: Desktop Notifications

**As a** music producer
**I want to** receive desktop notifications for important events
**So that** I stay informed without watching the terminal

**Acceptance Criteria:**
- [ ] Watch mode (3.1) sends notification when analysis completes
- [ ] Scheduled scan (3.3) sends summary notification
- [ ] Significant health changes trigger notification (>10 point change)
- [ ] Notifications show: project name, health score, brief status
- [ ] Click notification opens dashboard or relevant project
- [ ] `--notify` flag enables notifications (off by default)
- [ ] `--notify-level` sets threshold: all, important, critical
- [ ] Works on Windows 10/11
- [ ] Rate limited: max 1 notification per 30 seconds

**Notification Types:**

1. **Analysis Complete**
   - Title: "ALS Doctor"
   - Body: "22_3.als: 88/100 [A] (+3)"

2. **Scheduled Scan Complete**
   - Title: "Weekly Scan Complete"
   - Body: "47 projects scanned. 3 need attention."

3. **Health Alert** (optional)
   - Title: "Health Regression Detected"
   - Body: "22_12.als dropped to 45/100 (-43)"

**Technical Notes:**
- Windows: Use `win10toast-click` or `plyer` library
- Support click action to open URL (dashboard link)
- Store notification preferences in config
- Queue notifications to respect rate limit

**Effort:** Small
**Dependencies:** Stories 3.1, 3.3 (automation features)

---

## Summary

| Story | Description | Effort | Dependencies |
|-------|-------------|--------|--------------|
| 4.1 | CLI Colors | Small | None |
| 4.2 | HTML Reports | Medium | Phase 1 |
| 4.3 | Health Timeline | Medium | 4.2 |
| 4.4 | Web Dashboard | Large | Phase 1, 2 |
| 4.5 | Compare View | Medium | 4.4 |
| 4.6 | "What to Work On" | Medium | 4.4, Phase 2 |
| 4.7 | Notifications | Small | 3.1, 3.3 |

---

## Implementation Order

**Recommended sequence:**

1. **4.1 CLI Colors** - Quick win, immediate improvement, no dependencies
2. **4.7 Notifications** - Small effort, enhances Phase 3 automation
3. **4.2 HTML Reports** - Medium effort, standalone value without dashboard
4. **4.3 Health Timeline** - Part of 4.2, ships together
5. **4.4 Web Dashboard** - Large effort, but foundation for 4.5 and 4.6
6. **4.5 Compare View** - Builds on dashboard
7. **4.6 "What to Work On"** - The crown jewel, maximum user value

---

## CLI Command Summary

```
# Enhanced Output
als-doctor [any command] --no-color    # Disable colors

# HTML Reports
als-doctor diagnose <file> --html [output.html]
als-doctor db report <song> --html
als-doctor db report --all --html

# Web Dashboard
als-doctor dashboard [--port N] [--no-browser]

# Notifications (flags for other commands)
als-doctor watch <folder> --notify
als-doctor schedule add <folder> --daily --notify
```

---

## Technical Dependencies

### Python Libraries

- `rich` - Terminal formatting and colors (4.1)
- `jinja2` - HTML templating (4.2, 4.4)
- `flask` or `fastapi` - Web server (4.4)
- `win10toast-click` or `plyer` - Desktop notifications (4.7)
- `chart.js` - Visualizations (inline in HTML)

### Frontend (for Dashboard)

- No heavy framework - vanilla JS + htmx for interactivity
- Tailwind CSS or simple custom CSS
- Chart.js for charts
- Mobile-responsive design
