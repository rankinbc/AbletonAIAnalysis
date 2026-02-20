# Epic: Phase 2 - Intelligence (Analysis & Learning)

**Goal:** Transform the tool from a reporter into a coach - track changes, correlate outcomes, and provide personalized recommendations based on user history.

**Dependencies:** Phase 1 (Foundation) complete

**Unlocks:** Phase 4 (Visibility) - rich data for dashboards

---

## Strategic Context

Phase 2 is the **differentiation layer**. It doesn't just tell you what's wrong - it tells you:
1. What you changed
2. Whether it helped
3. What you keep doing wrong
4. What your best work looks like

This is what no other tool provides.

---

## Stories

### Story 2.1: Track Changes Between Versions ✅ IMPLEMENTED

**As a** music producer
**I want to** see exactly what changed between two versions
**So that** I can understand what made it better or worse

**Acceptance Criteria:**
- [x] `als-doctor db changes <song>` shows changes between latest and previous
- [x] `als-doctor db changes <song> --from <v1> --to <v2>` compares specific versions
- [x] Shows: devices added/removed, parameters changed, health delta
- [x] Categorizes changes: "Likely helped" vs "Likely hurt" based on health delta
- [x] Categorizes changes by type: structural, mixing, arrangement, plugin
- [x] Links changes to issue resolution (e.g., "Removed duplicate EQ -> fixed warning")
- [x] Stores change records in database for later analysis

**Example Output:**
```
CHANGES: 22 Project
From: 22_2.als (100) -> To: 22_3.als (88)
Health: -12 points

DEVICES ADDED (3):
  + Bass: Compressor2 (new)
  + Lead: EQ Eight (new)
  + Lead: EQ Eight (new)  <- Duplicate detected

DEVICES REMOVED (0):
  (none)

PARAMETERS CHANGED (2):
  Bass Compressor: Ratio 4:1 -> 20:1 (more aggressive)
  Master Limiter: Ceiling -0.3 -> 0.0 (risk of clipping)

LIKELY HURT (-12 health):
  - Added duplicate EQ on Lead (+1 warning)
  - Compressor ratio now extreme (+1 warning)
```

**Technical Notes:**
- Leverage existing project_differ.py
- Store diffs in new `changes` table for aggregation
- Schema addition:
```sql
changes (
    id INTEGER PRIMARY KEY,
    from_version_id INTEGER REFERENCES versions(id),
    to_version_id INTEGER REFERENCES versions(id),
    change_type TEXT,  -- 'device_added', 'device_removed', 'param_changed'
    track_name TEXT,
    device_type TEXT,
    details TEXT,
    health_delta INTEGER,
    created_at TIMESTAMP
)
```

**Effort:** Medium
**Dependencies:** Phase 1 complete, project_differ.py exists

---

### Story 2.2: Correlate Changes with Outcomes ✅ IMPLEMENTED

**As a** music producer
**I want to** know which types of changes typically help or hurt my mixes
**So that** I can learn what works for me

**Acceptance Criteria:**
- [x] `als-doctor db insights` shows aggregated change patterns
- [x] Tracks: "When you do X, health usually goes Y"
- [x] Categories: device additions, removals, parameter changes
- [x] Shows confidence level based on sample size (low/medium/high)
- [x] Highlights your most common mistakes
- [x] Shows "insufficient data" message if < 10 version comparisons available
- [ ] `--min-samples N` to adjust confidence threshold (optional, not yet implemented)

**Example Output:**
```
INSIGHTS FROM YOUR HISTORY (47 versions analyzed)

PATTERNS THAT HELP:
  + Removing disabled devices     -> +8 avg health (12 instances) [HIGH]
  + Reducing compressor ratio     -> +5 avg health (6 instances) [MEDIUM]
  + Fixing limiter position       -> +12 avg health (4 instances) [LOW]

PATTERNS THAT HURT:
  - Adding multiple EQs           -> -7 avg health (8 instances) [HIGH]
  - Extreme compressor settings   -> -10 avg health (5 instances) [MEDIUM]
  - Adding de-esser to non-vocals -> -3 avg health (3 instances) [LOW]

YOUR COMMON MISTAKES:
  1. Duplicate EQ Eight devices (found in 40% of low-scoring versions)
  2. Disabled device clutter (avg 28% in your projects)
  3. Compressor ratio > 10:1 on bass (found in 6 projects)

Confidence: HIGH (10+ samples), MEDIUM (5-9), LOW (2-4)
```

**Technical Notes:**
- Aggregation queries on changes table
- Group by change_type + device_type
- Calculate avg health_delta per group
- Minimum 2 samples to show pattern

**Effort:** Large
**Dependencies:** Story 2.1, significant history in DB

---

### Story 2.3: Extend ALS Parser for MIDI/Arrangement ✅ IMPLEMENTED

**As a** music producer
**I want to** analyze MIDI content and arrangement structure
**So that** I can get feedback on composition, not just mixing

**Acceptance Criteria:**
- [x] `als-doctor diagnose <file> --midi` includes MIDI analysis
- [x] Detects: empty MIDI clips, very short clips (<1 bar), duplicate clips
- [x] Analyzes arrangement: locators/markers if present
- [x] Counts: total MIDI notes, clip count, track density
- [x] Flags: tracks with no content, orphaned clips
- [x] Shows arrangement structure if markers exist
- [x] Stores MIDI stats in database when using --save

**Example Output:**
```
MIDI ANALYSIS: 22_2.als

Tracks with MIDI: 8
Total Clips: 24
Total Notes: 1,847

ARRANGEMENT (from locators):
  Intro: 0:00 - 0:32 (8 bars)
  Buildup: 0:32 - 1:28 (16 bars)
  Drop: 1:28 - 2:24 (16 bars)
  Breakdown: 2:24 - 3:20 (16 bars)
  Drop 2: 3:20 - 4:16 (16 bars)
  Outro: 4:16 - 4:48 (8 bars)

ISSUES:
  [i] "Chord Stabs" has 3 empty clips
  [i] "FX Riser" clip is only 2 beats long
  [i] "Unused Ideas" track has 0 active clips
```

**Technical Notes:**
- Extend als_parser.py or device_chain_analyzer.py
- Parse MidiClip elements in .als XML
- Extract Locators for arrangement markers
- New issues category: ARRANGEMENT

**Effort:** Medium
**Dependencies:** als_parser.py extension

---

### Story 2.4: Build Personal Style Profile ✅ IMPLEMENTED

**As a** music producer
**I want to** see patterns from my best-scoring projects
**So that** I can understand and replicate my winning formula

**Acceptance Criteria:**
- [x] `als-doctor db profile` analyzes Grade A versions (80+ score)
- [x] Shows: common device chains, typical device counts, parameter ranges
- [x] `als-doctor db profile --compare <file>` compares project against profile
- [x] Identifies what makes your best work different from your worst
- [x] Shows "insufficient data" if < 3 Grade A versions
- [x] Stores profile as JSON for quick access

**Example Output:**
```
YOUR STYLE PROFILE (based on 8 Grade-A versions)

TYPICAL DEVICE CHAIN - BASS:
  1. EQ Eight (high-pass ~30Hz)
  2. Compressor2 (ratio 3:1 - 5:1)
  3. Saturator (soft clip)
  4. Utility (mono below 120Hz)

TYPICAL DEVICE CHAIN - DRUMS:
  1. EQ Eight
  2. Glue Compressor (ratio 2:1 - 4:1)
  3. Utility

TYPICAL DEVICE COUNTS:
  Per track: 3-5 devices (you avg 4.2)
  Master chain: 3-4 devices
  Disabled: <10% (your best work has minimal clutter)

YOUR BEST WORK vs WORST:
  | Metric              | Grade A | Grade D-F |
  |---------------------|---------|-----------|
  | Devices per track   | 4.2     | 7.8       |
  | Disabled devices    | 8%      | 34%       |
  | Duplicate effects   | 0.2     | 2.4       |
  | Compressor ratio    | 4.1:1   | 12.3:1    |

INSIGHT: Your best mixes are SIMPLER.
```

**Technical Notes:**
- Aggregate device chains from Grade A versions
- Find common patterns using frequency analysis
- Store profile in `data/profile.json`
- Compare any project against profile

**Effort:** Large
**Dependencies:** Significant history in DB (minimum 3 Grade A versions)

---

### Story 2.5: Compare Against Templates ✅ IMPLEMENTED

**As a** music producer
**I want to** compare my project against professional templates
**So that** I can learn from established patterns

**Acceptance Criteria:**
- [x] `als-doctor compare-template <file> --template <template.als>` compares structure
- [x] Templates stored in `templates/` folder
- [x] Compares: device chain patterns, track organization, device counts
- [x] Highlights deviations from template patterns
- [x] `als-doctor templates list` shows available templates
- [x] `als-doctor templates add <file> --name <name>` adds template to library
- [x] Similarity score (0-100%) for overall match

**Example Output:**
```
TEMPLATE COMPARISON
Your project: 22_3.als
Template: trance-template-pro.als

OVERALL SIMILARITY: 72%

STRUCTURE MATCH:
  Track types: 85% similar
  Device patterns: 62% similar
  Organization: 70% similar

DEVIATIONS:
  - Your bass has 6 devices, template has 4
  - Template uses Glue Compressor on drums, you use Compressor2
  - Template has dedicated FX return tracks, yours are inline
  - Template master chain: Limiter last; yours: Limiter at position 2

SUGGESTIONS:
  1. Consider consolidating bass devices (template is leaner)
  2. Try Glue Compressor on drum bus for cohesion
  3. Move reverb/delay to return tracks for CPU efficiency
  4. Move Limiter to end of master chain
```

**Technical Notes:**
- Reuse device_chain_analyzer for both files
- Pattern matching algorithm for chain comparison
- Store template metadata in `templates/index.json`

**Effort:** Medium
**Dependencies:** None (standalone feature)

---

### Story 2.6: Smart Recommendations Engine ✅ IMPLEMENTED

**As a** music producer
**I want to** get personalized fix suggestions based on my history
**So that** recommendations are tailored to what works for ME

**Acceptance Criteria:**
- [x] `als-doctor diagnose <file> --smart` uses history for recommendations
- [x] Prioritizes fixes that have helped YOU before (from insights)
- [x] De-prioritizes fixes you've ignored multiple times
- [x] References your style profile for context
- [x] Shows confidence: "Based on your history, this fix typically helps"
- [x] Falls back to standard recommendations if insufficient history
- [x] `--smart` becomes default once enough history exists (20+ versions)

**Example Output:**
```
SMART DIAGNOSIS: 38b_5.als
(Using personalized recommendations from 47 analyzed versions)

[!!!] CRITICAL - Bass: Compressor ratio at 20:1
  Standard fix: Reduce to 4:1
  YOUR HISTORY: You've fixed this 4 times before, avg +8 health
  CONFIDENCE: High - this fix works for you
  PRIORITY: #1

[!!] WARNING - Lead: 3 duplicate EQs
  Standard fix: Consolidate to single EQ
  YOUR HISTORY: This is your #1 recurring issue (8 times)
  CONFIDENCE: High - consolidating EQs helped in 6/6 cases
  PRIORITY: #2

[!] SUGGESTION - Master: Add Utility at end
  Standard fix: Add for gain staging
  YOUR HISTORY: You've skipped this 3 times, no health impact
  CONFIDENCE: Low - may not matter for your workflow
  PRIORITY: Deprioritized

PERSONALIZED SUMMARY:
  Focus on #1 and #2 - these fixes consistently help YOUR mixes.
  Skip the Utility suggestion - your history shows it doesn't affect your scores.
```

**Technical Notes:**
- Query insights data for each issue type
- Track "ignored" fixes (issue present in consecutive versions)
- Scoring algorithm: base_priority * history_multiplier
- History multiplier: positive correlation boosts, negative dampens

**Effort:** Large
**Dependencies:** Stories 2.1, 2.2, 2.4

---

## Summary

| Story | Description | Effort | Dependencies |
|-------|-------------|--------|--------------|
| 2.1 | Track Changes | Medium | Phase 1, project_differ |
| 2.2 | Correlate Outcomes | Large | 2.1 |
| 2.3 | MIDI/Arrangement | Medium | als_parser extension |
| 2.4 | Style Profile | Large | History in DB |
| 2.5 | Template Compare | Medium | None |
| 2.6 | Smart Recommendations | Large | 2.1, 2.2, 2.4 |

**Critical Path:** 2.1 -> 2.2 -> 2.6
**Parallel Track:** 2.3, 2.5 (independent)
**Data Requirements:** 2.2, 2.4, 2.6 improve with more history

---

## Data Thresholds

| Feature | Minimum Data | Optimal Data |
|---------|--------------|--------------|
| Track Changes (2.1) | 2 versions | Any |
| Correlate Outcomes (2.2) | 10 comparisons | 30+ comparisons |
| Style Profile (2.4) | 3 Grade A versions | 8+ Grade A |
| Smart Recommendations (2.6) | 20 versions | 50+ versions |

Show helpful "insufficient data" messages below thresholds.

---

## CLI Command Summary

### ✅ All Phase 2 Commands Implemented

```bash
# Database initialization
als-doctor db init                              # Initialize database

# Library overview
als-doctor db status                            # Show library status with grade distribution
als-doctor db list [--sort name|score|date]     # List all tracked projects

# Version history
als-doctor db history <song>                    # Show version timeline with sparkline
als-doctor db trend <song>                      # Show health trend analysis

# Change tracking
als-doctor db changes <song>                    # Show changes between versions
als-doctor db changes <song> --no-compute       # Don't auto-compute missing changes
als-doctor db compute-changes <song>            # Compute and store changes for a project

# Insights and patterns
als-doctor db insights                          # Show patterns across all projects
als-doctor db patterns                          # Show learned patterns with confidence levels

# MIDI/Arrangement analysis (Story 2.3)
als-doctor diagnose <file> --midi               # Include MIDI analysis in diagnosis

# Style profile (Story 2.4)
als-doctor db profile                           # Show patterns from your best work
als-doctor db profile --compare <file>          # Compare a file against your profile
als-doctor db profile --save                    # Save profile to data/profile.json

# Template comparison (Story 2.5)
als-doctor templates list                       # List all available templates
als-doctor templates add <file> --name <name>   # Add a new template
als-doctor templates remove <name>              # Remove a template
als-doctor templates show <name>                # Show template details
als-doctor compare-template <file> -t <name>    # Compare project to template

# Smart recommendations (Story 2.6)
als-doctor diagnose <file> --smart              # Use personalized recommendations
als-doctor diagnose <file> --no-smart           # Disable smart mode
als-doctor db smart <file>                      # Smart diagnosis standalone
als-doctor db recommend                         # Get prioritized recommendations
als-doctor db whatif <song>                     # Predict impact of changes
```

### Change Categories

Changes are automatically categorized into:
- **📁 STRUCTURAL**: Track additions/removals
- **🎚️ MIXING**: EQ, Compressor, Limiter, Utility, etc.
- **🎵 ARRANGEMENT**: Reverb, Delay, Chorus, Flanger, etc.
- **🔌 PLUGIN**: Other device changes
