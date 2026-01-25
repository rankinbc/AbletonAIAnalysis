# Epic: Phase 1 - Foundation (Project Database & History)

**Goal:** Establish persistent storage for project analysis data, enabling historical tracking and cross-project insights.

**Dependencies:** None (foundational)

**Unlocks:** Phase 2 (Intelligence), Phase 3 (Automation), Phase 4 (Visibility)

---

## Stories

### Story 1.1: Initialize Project Database

**As a** music producer using AbletonAIAnalysis
**I want to** initialize a persistent database for my projects
**So that** scan results are saved and queryable over time

**Acceptance Criteria:**
- [ ] `als-doctor db init` creates SQLite database at `data/projects.db`
- [ ] Database schema includes: projects, versions, issues tables
- [ ] Running init twice doesn't destroy existing data (idempotent)
- [ ] Success message confirms database location

**Technical Notes:**
```sql
-- Schema
projects (
    id INTEGER PRIMARY KEY,
    folder_path TEXT UNIQUE,
    song_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

versions (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    als_path TEXT UNIQUE,
    als_filename TEXT,
    health_score INTEGER,
    grade TEXT,
    total_issues INTEGER,
    critical_issues INTEGER,
    warning_issues INTEGER,
    total_devices INTEGER,
    disabled_devices INTEGER,
    clutter_percentage REAL,
    scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

issues (
    id INTEGER PRIMARY KEY,
    version_id INTEGER REFERENCES versions(id),
    track_name TEXT,
    severity TEXT,
    category TEXT,
    description TEXT,
    fix_suggestion TEXT
)
```

**Effort:** Small

---

### Story 1.2: Persist Scan Results

**As a** music producer
**I want to** save batch scan results to the database
**So that** I don't lose analysis data between sessions

**Acceptance Criteria:**
- [ ] `als-doctor scan <dir> --save` persists results to DB
- [ ] Each .als file creates/updates a version record
- [ ] Issues are stored with severity, category, and fix suggestion
- [ ] Re-scanning same file updates existing record (upsert by path)
- [ ] Scan without `--save` works as before (no DB dependency)
- [ ] `als-doctor diagnose <file> --save` also persists single file

**Technical Notes:**
- Upsert based on als_path (unique constraint)
- Track `scanned_at` timestamp for history
- Auto-create project record if folder not seen before
- Extract song_name from parent folder name

**Effort:** Medium
**Dependencies:** Story 1.1

---

### Story 1.3: List All Projects

**As a** music producer
**I want to** see all my scanned projects in one view
**So that** I know what's in my database

**Acceptance Criteria:**
- [ ] `als-doctor db list` shows all projects
- [ ] Output includes: song name, version count, best score, latest score
- [ ] Sortable by: name, score, date (default: name)
- [ ] `--sort score` sorts by best health score descending
- [ ] `--sort date` sorts by most recently scanned
- [ ] Shows trend indicator (up arrow improving, down arrow declining, arrow right stable)

**Example Output:**
```
PROJECTS (12 songs, 47 versions)

Song              Versions  Best    Latest  Trend
------------------------------------------------
22 Project        18        100 [A] 45 [C]  [down]
35 Project        5         78 [B]  78 [B]  [stable]
38b Project       3         24 [D]  41 [C]  [up]
```

**Effort:** Small
**Dependencies:** Story 1.2

---

### Story 1.4: View Project Health History

**As a** music producer
**I want to** see how a project's health changed over time
**So that** I can identify when it got better or worse

**Acceptance Criteria:**
- [ ] `als-doctor db history <song>` shows all versions
- [ ] Output includes: version name, health score, grade, date scanned
- [ ] Sorted by scan date (oldest first)
- [ ] Shows delta from previous version
- [ ] Highlights best version with star marker
- [ ] Fuzzy matches song name (e.g., "22" matches "22 Project")

**Example Output:**
```
HEALTH HISTORY: 22 Project

Version              Score  Grade  Delta   Scanned
--------------------------------------------------
22_1.als             65     [B]    --      2026-01-10
22_2.als             100    [A]    +35 *   2026-01-12
22_3.als             88     [A]    -12     2026-01-14
22_12recompose.als   45     [C]    -43     2026-01-20

Best: 22_2.als (100/100)
Current: 22_12recompose.als (45/100)
Recommendation: Review changes since 22_2.als
```

**Effort:** Small
**Dependencies:** Story 1.2

---

### Story 1.5: Find Best Version

**As a** music producer
**I want to** quickly find the healthiest version of a song
**So that** I can roll back or compare against it

**Acceptance Criteria:**
- [ ] `als-doctor best <song>` returns best version
- [ ] Shows: file path, health score, grade, scan date
- [ ] If multiple versions tie for best, shows most recent
- [ ] Shows quick comparison to latest version
- [ ] `--open` flag opens the folder containing the .als in explorer
- [ ] Fuzzy matches song name

**Example Output:**
```
BEST VERSION: 22 Project

* 22_2.als
  Score: 100/100 [A]
  Path: D:\Ableton Projects\22 Project\22_2.als
  Scanned: 2026-01-12

  vs Latest (22_12recompose.als):
    Health: 100 -> 45 (-55)
    Issues: 0 -> 12 (+12 new)

  Recommendation: Consider rolling back to 22_2.als
```

**Effort:** Small
**Dependencies:** Story 1.2

---

### Story 1.6: Library Status Summary

**As a** music producer
**I want to** get a quick summary of my entire library
**So that** I know the overall state of my projects

**Acceptance Criteria:**
- [ ] `als-doctor db status` shows library summary
- [ ] Shows: total projects, total versions, grade distribution
- [ ] Grade distribution shown as ASCII bar chart
- [ ] Lists top 3 "ready to release" (Grade A, highest scores)
- [ ] Lists top 3 "needs work" (Grade D-F, lowest scores)
- [ ] Shows last scan date

**Example Output:**
```
LIBRARY STATUS

Projects: 12 | Versions: 47 | Last Scan: 2026-01-25

Grade Distribution:
  [A] ======== 8 versions (17%)
  [B] ============== 14 versions (30%)
  [C] ============ 12 versions (26%)
  [D] ====== 6 versions (13%)
  [F] ======= 7 versions (15%)

Ready to Release:
  * 22_2.als (100) | 35_5.als (92) | 41_3.als (88)

Needs Attention:
  ! 38b_5.als (24) | 29_old.als (18) | 33_draft.als (12)
```

**Effort:** Medium
**Dependencies:** Story 1.2

---

## Summary

| Story | Description | Effort | Dependencies |
|-------|-------------|--------|--------------|
| 1.1 | DB Init | Small | None |
| 1.2 | Persist Scan | Medium | 1.1 |
| 1.3 | List Projects | Small | 1.2 |
| 1.4 | Health History | Small | 1.2 |
| 1.5 | Best Version | Small | 1.2 |
| 1.6 | Library Status | Medium | 1.2 |

**Critical Path:** 1.1 → 1.2 → (1.3, 1.4, 1.5, 1.6 in parallel)

**Total Effort:** ~1 week

---

## CLI Command Summary

```
als-doctor db init                  # Initialize database
als-doctor db list [--sort X]       # List all projects
als-doctor db history <song>        # Show version history
als-doctor db status                # Library summary
als-doctor best <song> [--open]     # Find best version
als-doctor scan <dir> --save        # Scan and persist
als-doctor diagnose <file> --save   # Diagnose and persist
```
