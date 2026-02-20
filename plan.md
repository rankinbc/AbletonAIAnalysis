# AbletonAIAnalysis - Ralph Loop Implementation Plan

## Current Sprint: Phase 1 - Foundation (Database & History)

This plan follows the Ralph Wiggum loop methodology. Each task has a `passes` field that gets set to `true` when complete.

---

## Tasks

```json
[
  {
    "id": "1.1",
    "category": "foundation",
    "description": "Initialize SQLite Database",
    "steps": [
      "Create data/ directory if not exists",
      "Create projects/music-analyzer/src/database.py with SQLite schema",
      "Implement db_init() function that creates projects.db at data/projects.db",
      "Schema: projects (id, folder_path, song_name, created_at)",
      "Schema: versions (id, project_id, als_path, als_filename, health_score, grade, total_issues, critical_issues, warning_issues, total_devices, disabled_devices, clutter_percentage, scanned_at)",
      "Schema: issues (id, version_id, track_name, severity, category, description, fix_suggestion)",
      "Make init idempotent (running twice doesn't destroy data)",
      "Add CLI command: als-doctor db init",
      "Write tests for database initialization"
    ],
    "acceptance": [
      "als-doctor db init creates SQLite database at data/projects.db",
      "Database schema includes projects, versions, issues tables",
      "Running init twice doesn't destroy existing data",
      "Success message confirms database location"
    ],
    "passes": true
  },
  {
    "id": "1.2",
    "category": "foundation",
    "description": "Persist Scan Results to Database",
    "steps": [
      "Add --save flag to scan and diagnose commands",
      "Implement persist_scan_result() in database.py",
      "Upsert version records based on als_path (unique constraint)",
      "Store all issues with severity, category, fix suggestion",
      "Auto-create project record if folder not seen before",
      "Extract song_name from parent folder name",
      "Track scanned_at timestamp for history",
      "Ensure scan without --save still works (no DB dependency)",
      "Write tests for persistence"
    ],
    "acceptance": [
      "als-doctor scan <dir> --save persists results to DB",
      "Each .als file creates/updates a version record",
      "Issues are stored with severity, category, and fix suggestion",
      "Re-scanning same file updates existing record",
      "Scan without --save works as before"
    ],
    "passes": true
  },
  {
    "id": "1.3",
    "category": "foundation",
    "description": "List All Projects Command",
    "steps": [
      "Implement list_projects() in database.py",
      "Query to get all projects with version counts and scores",
      "Calculate best score and latest score per project",
      "Determine trend indicator (up/down/stable)",
      "Add CLI command: als-doctor db list",
      "Support --sort flag (name, score, date)",
      "Format output as clean table",
      "Write tests for list functionality"
    ],
    "acceptance": [
      "als-doctor db list shows all projects",
      "Output includes: song name, version count, best score, latest score",
      "Sortable by name, score, date",
      "Shows trend indicator"
    ],
    "passes": true
  },
  {
    "id": "1.4",
    "category": "foundation",
    "description": "View Project Health History",
    "steps": [
      "Implement get_project_history() in database.py",
      "Query versions for a project ordered by scan date",
      "Calculate delta from previous version",
      "Identify and mark best version with star",
      "Implement fuzzy song name matching",
      "Add CLI command: als-doctor db history <song>",
      "Format output showing version, score, grade, delta, date",
      "Write tests for history functionality"
    ],
    "acceptance": [
      "als-doctor db history <song> shows all versions",
      "Output includes version name, health score, grade, date scanned",
      "Sorted by scan date (oldest first)",
      "Shows delta from previous version",
      "Highlights best version with star marker",
      "Fuzzy matches song name"
    ],
    "passes": true
  },
  {
    "id": "1.5",
    "category": "foundation",
    "description": "Find Best Version Command",
    "steps": [
      "Implement get_best_version() in database.py",
      "Query for highest health_score version",
      "If tie, return most recent",
      "Compare against latest version for summary",
      "Add --open flag to open folder in explorer",
      "Add CLI command: als-doctor best <song>",
      "Implement fuzzy song name matching",
      "Write tests for best version functionality"
    ],
    "acceptance": [
      "als-doctor best <song> returns best version",
      "Shows file path, health score, grade, scan date",
      "If multiple tie for best, shows most recent",
      "Shows comparison to latest version",
      "--open flag opens containing folder",
      "Fuzzy matches song name"
    ],
    "passes": true
  },
  {
    "id": "1.6",
    "category": "foundation",
    "description": "Library Status Summary",
    "steps": [
      "Implement get_library_status() in database.py",
      "Calculate total projects and versions",
      "Calculate grade distribution",
      "Generate ASCII bar chart for distribution",
      "Identify top 3 'ready to release' (Grade A)",
      "Identify top 3 'needs work' (Grade D-F)",
      "Track last scan date",
      "Add CLI command: als-doctor db status",
      "Write tests for status functionality"
    ],
    "acceptance": [
      "als-doctor db status shows library summary",
      "Shows total projects, versions, grade distribution",
      "Grade distribution as ASCII bar chart",
      "Lists top 3 ready to release",
      "Lists top 3 needs work",
      "Shows last scan date"
    ],
    "passes": true
  },
  {
    "id": "4.1",
    "category": "visibility",
    "description": "CLI Colors and Formatting",
    "steps": [
      "Add rich library to requirements.txt",
      "Create projects/music-analyzer/src/cli_formatter.py",
      "Define color scheme: A=green, B=cyan, C=yellow, D=orange, F=red",
      "Define severity colors: Critical=red, Warning=yellow, Suggestion=cyan",
      "Implement colored grade display",
      "Implement colored issue severity display",
      "Add --no-color flag for plain text output",
      "Test on Windows Terminal, PowerShell, CMD",
      "Graceful fallback if no ANSI support",
      "Update all CLI commands to use formatter"
    ],
    "acceptance": [
      "All CLI output uses consistent color coding",
      "Health grades colored appropriately",
      "Issue severity colored appropriately",
      "--no-color flag works",
      "Works in Windows Terminal, PowerShell, CMD"
    ],
    "passes": true
  },
  {
    "id": "2.1",
    "category": "intelligence",
    "description": "Track Changes Between Versions",
    "steps": [
      "Add changes table to database schema",
      "Implement track_changes() in database.py using project_differ",
      "Store diffs: device_added, device_removed, param_changed",
      "Link changes to health_delta",
      "Add CLI: als-doctor db changes <song>",
      "Support --from and --to flags for specific versions",
      "Categorize changes as 'Likely helped' vs 'Likely hurt'",
      "Write tests for change tracking"
    ],
    "acceptance": [
      "als-doctor db changes <song> shows changes between versions",
      "Shows devices added/removed, parameters changed",
      "Categorizes changes based on health delta",
      "Stores change records in database"
    ],
    "passes": true
  },
  {
    "id": "2.2",
    "category": "intelligence",
    "description": "Correlate Changes with Outcomes",
    "steps": [
      "Implement get_insights() aggregation queries",
      "Group changes by type and device_type",
      "Calculate avg health_delta per pattern",
      "Identify common mistakes (high frequency, negative impact)",
      "Add confidence levels: LOW (2-4), MEDIUM (5-9), HIGH (10+)",
      "Add CLI: als-doctor db insights",
      "Show 'insufficient data' if < 10 comparisons",
      "Write tests for insights"
    ],
    "acceptance": [
      "als-doctor db insights shows aggregated patterns",
      "Shows patterns that help vs hurt",
      "Shows confidence level based on sample size",
      "Highlights common mistakes"
    ],
    "passes": true
  },
  {
    "id": "2.3",
    "category": "intelligence",
    "description": "MIDI and Arrangement Analysis",
    "steps": [
      "Extend als_parser.py to parse MidiClip elements",
      "Extract MIDI note counts, clip counts, durations",
      "Parse Locators for arrangement markers",
      "Detect empty clips, very short clips, duplicate clips",
      "Flag tracks with no content",
      "Add --midi flag to diagnose command",
      "Store MIDI stats in database when using --save",
      "Write tests for MIDI analysis"
    ],
    "acceptance": [
      "als-doctor diagnose <file> --midi includes MIDI analysis",
      "Detects empty MIDI clips, short clips, duplicates",
      "Shows arrangement structure from markers",
      "Counts total notes, clips, track density"
    ],
    "passes": true
  },
  {
    "id": "2.4",
    "category": "intelligence",
    "description": "Build Personal Style Profile",
    "steps": [
      "Implement get_style_profile() in database.py",
      "Analyze Grade A versions (80+ score) for patterns",
      "Extract common device chains per track type",
      "Calculate typical device counts and parameter ranges",
      "Compare best work vs worst work metrics",
      "Store profile as JSON in data/profile.json",
      "Add CLI: als-doctor db profile",
      "Support --compare flag to compare file against profile",
      "Write tests for profile generation"
    ],
    "acceptance": [
      "als-doctor db profile shows patterns from best work",
      "Shows typical device chains, counts, parameter ranges",
      "Compares Grade A vs Grade D-F versions",
      "Shows 'insufficient data' if < 3 Grade A versions"
    ],
    "passes": true
  },
  {
    "id": "2.5",
    "category": "intelligence",
    "description": "Compare Against Templates",
    "steps": [
      "Create templates/ directory structure",
      "Implement template storage with templates/index.json",
      "Create compare_template() function",
      "Pattern matching for device chain comparison",
      "Calculate similarity score (0-100%)",
      "Add CLI: als-doctor templates list",
      "Add CLI: als-doctor templates add <file> --name <name>",
      "Add CLI: als-doctor compare-template <file> --template <T>",
      "Write tests for template comparison"
    ],
    "acceptance": [
      "als-doctor compare-template compares structure to template",
      "Shows similarity score and deviations",
      "als-doctor templates list shows available templates",
      "als-doctor templates add saves template to library"
    ],
    "passes": true
  },
  {
    "id": "2.6",
    "category": "intelligence",
    "description": "Smart Recommendations Engine",
    "steps": [
      "Implement smart_diagnose() using history data",
      "Prioritize fixes that helped user before",
      "De-prioritize fixes user ignored multiple times",
      "Reference style profile for context",
      "Show confidence based on history",
      "Add --smart flag to diagnose command",
      "Make --smart default when 20+ versions exist",
      "Fallback to standard recommendations if insufficient history",
      "Write tests for smart recommendations"
    ],
    "acceptance": [
      "als-doctor diagnose <file> --smart uses history",
      "Prioritizes fixes based on what worked for user",
      "Shows confidence level for each recommendation",
      "Falls back gracefully with insufficient data"
    ],
    "passes": true
  },
  {
    "id": "3.1",
    "category": "automation",
    "description": "Watch Folder for Auto-Analysis",
    "steps": [
      "Add watchdog library to requirements.txt",
      "Implement watch_folder() with file system monitoring",
      "Filter for .als files, exclude Backup/ folders",
      "Debounce changes (5 second default, configurable)",
      "Trigger diagnose --save on file change",
      "Log results to data/watch.log",
      "Add CLI: als-doctor watch <folder>",
      "Support --quiet and --debounce flags",
      "Handle Ctrl+C gracefully",
      "Write tests for watch functionality"
    ],
    "acceptance": [
      "als-doctor watch <folder> monitors for .als changes",
      "Triggers analysis when file is modified",
      "Debounces rapid changes",
      "Ignores backup files",
      "Logs results and shows notifications"
    ],
    "passes": true
  },
  {
    "id": "3.2",
    "category": "automation",
    "description": "Guided Workflow Mode (CLI Coach)",
    "steps": [
      "Implement coach_mode() interactive session",
      "Show top issue with specific fix instructions",
      "Wait for user input: Enter (done), S (skip), Q (quit)",
      "Re-analyze after each fix confirmation",
      "Track session progress (fixed, skipped)",
      "Celebrate health improvements",
      "Add CLI: als-doctor coach <file>",
      "Support --auto-check flag for periodic re-analysis",
      "Show session summary at end",
      "Write tests for coach mode"
    ],
    "acceptance": [
      "als-doctor coach <file> enters guided mode",
      "Shows one issue at a time with fix instructions",
      "Re-analyzes after user confirms fix",
      "Tracks and reports session progress"
    ],
    "passes": true
  },
  {
    "id": "3.3",
    "category": "automation",
    "description": "Scheduled Batch Scan",
    "steps": [
      "Create schedule config storage in data/schedules.json",
      "Implement schedule management functions",
      "Create wrapper script for scheduled execution",
      "Integrate with OS task scheduler (cron for Linux)",
      "Add CLI: als-doctor schedule add <folder> --daily/--weekly/--hourly",
      "Add CLI: als-doctor schedule list",
      "Add CLI: als-doctor schedule remove <id>",
      "Add CLI: als-doctor schedule run <id>",
      "Log scheduled runs to data/scheduled_runs.log",
      "Write tests for scheduling"
    ],
    "acceptance": [
      "als-doctor schedule add creates scheduled task",
      "als-doctor schedule list shows all tasks",
      "als-doctor schedule remove deletes task",
      "Scheduled scans run automatically"
    ],
    "passes": true
  },
  {
    "id": "3.4",
    "category": "automation",
    "description": "Pre-Export Checklist",
    "steps": [
      "Implement preflight_check() function",
      "Check health score against threshold",
      "Check for critical issues",
      "Check limiter ceiling (should be <= -0.3dB)",
      "Check for solo'd tracks, muted master",
      "Return exit code 0 (ready) or 1 (not ready)",
      "Add CLI: als-doctor preflight <file>",
      "Support --strict (requires Grade A) and --min-score flags",
      "Separate blockers from optional cleanup items",
      "Write tests for preflight checks"
    ],
    "acceptance": [
      "als-doctor preflight <file> runs pre-export check",
      "Shows GO/NO-GO verdict with reasoning",
      "Returns proper exit codes for scripting",
      "--strict requires Grade A"
    ],
    "passes": true
  },
  {
    "id": "4.2",
    "category": "visibility",
    "description": "HTML Report Generation",
    "steps": [
      "Add jinja2 library to requirements.txt",
      "Create templates/report_project.html template",
      "Create templates/report_history.html template",
      "Create templates/report_library.html template",
      "Implement generate_html_report() function",
      "Make reports self-contained (inline CSS/JS)",
      "Add --html flag to diagnose command",
      "Add CLI: als-doctor db report <song> --html",
      "Add CLI: als-doctor db report --all --html",
      "Support dark mode and mobile-responsive design",
      "Write tests for HTML generation"
    ],
    "acceptance": [
      "als-doctor diagnose <file> --html generates project report",
      "als-doctor db report generates history/library reports",
      "Reports are self-contained and mobile-friendly",
      "Includes health gauge, issue list, recommendations"
    ],
    "passes": true
  },
  {
    "id": "4.3",
    "category": "visibility",
    "description": "Health Timeline Charts",
    "steps": [
      "Embed Chart.js (minified) in HTML templates",
      "Implement health timeline line chart",
      "Add grade zone background colors",
      "Mark best version with star, current with highlight",
      "Show regression points with markers",
      "Add hover tooltips with version details",
      "Support zoom/pan for many versions",
      "Integrate into history HTML reports",
      "Write tests for chart data generation"
    ],
    "acceptance": [
      "HTML history reports include interactive timeline",
      "Shows health score over time with grade zones",
      "Highlights best version and regressions",
      "Tooltips show version details"
    ],
    "passes": true
  },
  {
    "id": "4.4",
    "category": "visibility",
    "description": "Local Web Dashboard",
    "steps": [
      "Add flask library to requirements.txt",
      "Create dashboard/ directory with templates",
      "Implement routes: /, /projects, /project/<id>, /insights, /settings",
      "Home page: health overview, needs attention, ready to release",
      "Projects page: sortable/filterable table",
      "Project detail: timeline chart, issues, history",
      "Add CLI: als-doctor dashboard",
      "Support --port and --no-browser flags",
      "Auto-refresh on database changes",
      "Write tests for dashboard routes"
    ],
    "acceptance": [
      "als-doctor dashboard starts local web server",
      "Dashboard shows library overview and project details",
      "Projects sortable and filterable",
      "Includes health timeline and issue lists"
    ],
    "passes": true
  },
  {
    "id": "4.5",
    "category": "visibility",
    "description": "Side-by-Side Version Comparison View",
    "steps": [
      "Add /project/<id>/compare route to dashboard",
      "Implement version selector dropdowns",
      "Show health delta, grade change, issues diff",
      "Color-code: green=improvement, red=regression",
      "Add expandable track-by-track breakdown",
      "Support deep linking with query params",
      "Add 'Swap A/B' button",
      "Reuse project_differ for diff data",
      "Write tests for comparison view"
    ],
    "acceptance": [
      "Dashboard includes comparison page",
      "Can select any two versions to compare",
      "Shows detailed diff with color coding",
      "Expandable track-level details"
    ],
    "passes": true
  },
  {
    "id": "4.6",
    "category": "visibility",
    "description": "What Should I Work On View",
    "steps": [
      "Add 'Today's Focus' section to dashboard home",
      "Implement prioritization algorithm",
      "Categories: Quick Wins, Deep Work, Ready to Polish",
      "Track last_worked_at in projects table",
      "Add 'I worked on this' button",
      "Add 'Not today' button with hidden_until",
      "Refresh recommendations daily",
      "Boost projects not touched recently",
      "Write tests for prioritization"
    ],
    "acceptance": [
      "Dashboard shows prioritized 'What to Work On' list",
      "Three categories based on effort/potential",
      "Can mark projects as worked on or hidden",
      "Prioritizes based on recency and momentum"
    ],
    "passes": true
  },
  {
    "id": "4.7",
    "category": "visibility",
    "description": "Desktop Notifications",
    "steps": [
      "Add plyer library to requirements.txt",
      "Implement notify() function for cross-platform notifications",
      "Notification types: analysis complete, scan complete, health alert",
      "Add --notify flag to watch and schedule commands",
      "Support --notify-level (all, important, critical)",
      "Rate limit: max 1 per 30 seconds",
      "Click action opens dashboard URL",
      "Write tests for notification logic"
    ],
    "acceptance": [
      "Watch mode sends notification on analysis complete",
      "Scheduled scans send summary notification",
      "Notifications show project name, score, status",
      "Rate limited to prevent spam"
    ],
    "passes": true
  }
]
```

---

## Completion Criteria

When ALL tasks have `"passes": true`, output:

```
<promise>COMPLETE</promise>
```

---

## Notes

### Phase Dependencies
- **Phase 1 (1.1-1.6)**: Foundation - must complete first
- **Phase 2 (2.1-2.6)**: Intelligence - requires Phase 1
- **Phase 3 (3.1-3.4)**: Automation - requires Phase 1
- **Phase 4 (4.1-4.7)**: Visibility - 4.1 has no deps, others need Phase 1+

### Task Order
1. Complete Phase 1 first (1.1 done, continue 1.2-1.6)
2. 4.1 (CLI Colors) can run anytime
3. Then Phase 2 and Phase 3 can run in parallel
4. Phase 4 (4.2-4.7) after foundations are solid

### Rules
- Each task should include tests
- Update activity.md after completing each task
- Make one git commit per completed task
- Total: 25 tasks across all phases
