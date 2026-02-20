# Phase 2: Intelligence Layer

## Overview

Phase 2 transforms ALS Doctor from a reporter into a **coach** - tracking changes over time, correlating them with outcomes, and providing personalized recommendations based on your production history.

**Key Concept:** The tool learns from your past decisions. If removing certain devices has consistently improved your project health, it will predict that same outcome for similar changes in the future.

---

## New CLI Commands

### 1. `als-doctor db trend <song>`

Analyzes the health trajectory of a project over its versions.

**Shows:**
- Trend direction: improving / stable / declining
- Trend strength (how strong the pattern is)
- Health timeline with deltas per version
- Velocity metrics (recent momentum)
- Biggest improvement and regression swings

**Example:**
```bash
als-doctor db trend "22 Project"
```

**Output:**
```
TREND ANALYSIS: 22 Project

------------------------------------------------------------
  ↗ IMPROVING (strength: 78%)

  Good progress! Health improved 45 → 78 (+33) over 12 versions.
  Recent momentum is strong.

------------------------------------------------------------
HEALTH METRICS:
  First scan:  45
  Latest:      78
  Best:        78
  Worst:       38
  Average:     62.3

------------------------------------------------------------
CHANGE METRICS:
  Avg change per version:  +2.8
  Recent momentum:         +5.3
  Biggest improvement:     +12
  Biggest regression:      -8

------------------------------------------------------------
TIMELINE (12 versions):

  22_1.als                          +0   health: 45
  22_2.als                          +5   health: 50
  22_3.als                          -2   health: 48
  ...
  22_12.als                         +8   health: 78

============================================================
```

---

### 2. `als-doctor db whatif <file>`

Predicts what would happen if you make certain changes, based on historical patterns across all your projects.

**Requires:** The file must be previously scanned with `--save`

**Shows:**
- Current health
- Top recommendation (highest confidence improvement)
- All predictions with confidence levels
- Success rates from similar changes

**Example:**
```bash
als-doctor db whatif "D:/Projects/22 Project/22_12.als"
```

**Output:**
```
WHAT-IF PREDICTIONS

File: 22_12.als
Current health: 65

------------------------------------------------------------
TOP RECOMMENDATION:

  REMOVE Eq8
  Predicted: +5.2 health
  Confidence: [HIGH] based on 24 similar changes
  Success rate: 83%

------------------------------------------------------------
ALL PREDICTIONS:

  ★ REMOVE   Eq8                      → +5.2 (24x, 83%)
  ★ DISABLE  Compressor2              → +3.8 (18x, 72%)
  ◐ REMOVE   Saturator                → +2.1 (7x, 71%)
  ○ DISABLE  AutoFilter               → +1.5 (3x, 67%)

  Legend: ★ HIGH confidence | ◐ MEDIUM | ○ LOW

============================================================
```

---

### 3. `als-doctor db recommend`

Shows smart recommendations using historical intelligence and learned patterns.

**Combines:**
- Learned patterns from your project history
- Historical success rates for different change types
- Confidence levels based on sample size
- Common mistakes identified across all projects

**Example:**
```bash
als-doctor db recommend
als-doctor db recommend --min-samples 5
```

**Output:**
```
SMART RECOMMENDATIONS

Based on 45 patterns from your project history:

------------------------------------------------------------
✓ DO MORE OF THESE (consistently improve health)
------------------------------------------------------------
  [●●●] removed Eq8
        Avg: +5.2 health | 18/24 times helped
        → Usually beneficial - consider applying

  [●●○] disabled Compressor2
        Avg: +3.8 health | 12/18 times helped
        → Slightly beneficial on average

------------------------------------------------------------
✗ AVOID THESE (consistently hurt health)
------------------------------------------------------------
  [●●●] added Saturator
        Avg: -4.2 health | 15/20 times hurt
        → Often harmful - avoid unless necessary

------------------------------------------------------------
⚠ COMMON MISTAKES TO AVOID
------------------------------------------------------------
  • Adding multiple compressors tends to hurt health
    Seen 25x, avg -3.5 health impact
    Examples: Compressor2, GlueCompressor

============================================================
```

---

### 4. `als-doctor db patterns`

Shows all learned patterns from your project history.

**Shows:**
- Change patterns that consistently help
- Change patterns that consistently hurt
- Neutral patterns (mixed results)
- Confidence levels based on sample size

**Example:**
```bash
als-doctor db patterns
als-doctor db patterns --min-samples 5
```

**Output:**
```
LEARNED PATTERNS

45 patterns identified from change history.

------------------------------------------------------------
PATTERNS THAT HELP (↑ health)
------------------------------------------------------------
  [HIGH  ] removed Eq8
           24 occurrences, avg delta: +5.2
           Success rate: 83%

  [MEDIUM] disabled Compressor2
           8 occurrences, avg delta: +3.8
           Success rate: 75%

------------------------------------------------------------
PATTERNS THAT HURT (↓ health)
------------------------------------------------------------
  [HIGH  ] added Saturator
           20 occurrences, avg delta: -4.2
           Failure rate: 75%

------------------------------------------------------------
NEUTRAL PATTERNS (mixed results)
------------------------------------------------------------
  [MEDIUM] added Eq8
           12 occurrences, avg delta: +0.5
           Mixed results - context dependent

============================================================
```

---

### 5. `als-doctor db changes <song>` (Enhanced)

The existing `changes` command now shows predicted impacts alongside actual outcomes.

**New Fields:**
- Change categorization: "Likely Helped" / "Likely Hurt"
- Predicted delta based on historical patterns
- Confidence level for predictions

**Example:**
```bash
als-doctor db changes "22 Project" --compute
```

---

### 5. `als-doctor db insights` (Enhanced)

The existing `insights` command now includes more detailed pattern analysis.

**Shows:**
- Patterns that consistently help (with confidence levels)
- Patterns that consistently hurt
- Common mistakes (high frequency + negative impact)
- Sample sizes for statistical confidence

---

## How Intelligence Is Built

### Data Collection

Every time you scan a project with `--save`:
1. Health score and issues are recorded
2. Version is linked to previous versions of same song
3. Device changes between versions are computed (with `--compute`)

### Pattern Analysis

The system aggregates changes across all your projects:
```sql
SELECT change_type, device_type,
       COUNT(*) as occurrences,
       AVG(health_delta) as avg_impact
FROM changes
GROUP BY change_type, device_type
```

### Confidence Levels

| Level | Sample Size | Interpretation |
|-------|-------------|----------------|
| HIGH | 10+ occurrences | Very reliable pattern |
| MEDIUM | 5-9 occurrences | Fairly reliable |
| LOW | 2-4 occurrences | Use with caution |

---

## Workflow: Building Your Intelligence

### Step 1: Scan Your Library

```bash
# Scan all your projects
als-doctor scan "D:/Ableton Projects" --save

# Or scan a specific folder
als-doctor scan "D:/Ableton Projects/2026" --save --limit 50
```

### Step 2: Compute Changes

```bash
# For each song with multiple versions
als-doctor db changes "22 Project" --compute
als-doctor db changes "35 Project" --compute

# Or compute for all songs matching a pattern
als-doctor db changes 22 --compute
```

### Step 3: Check Insights

```bash
als-doctor db insights
```

Once you have 10+ version comparisons with computed changes, you'll start seeing patterns.

### Step 4: Use Intelligence

```bash
# Check trend for a song
als-doctor db trend "22 Project"

# Get what-if predictions
als-doctor db whatif "D:/Projects/22 Project/22_current.als"

# Get smart recommendations
als-doctor db smart "D:/Projects/22 Project/22_current.als"
```

---

## Data Requirements

| Feature | Minimum Data Needed |
|---------|---------------------|
| `db trend` | 2+ versions of same song |
| `db whatif` | 10+ change records in database |
| `db smart` | 20+ scanned versions total |
| HIGH confidence | 10+ occurrences of same pattern |
| Style profile | 3+ Grade A versions (score 80+) |

---

## Example Patterns Discovered

The system might discover patterns like:

**Patterns That Help:**
- Removing disabled devices: avg +6.1 health (HIGH confidence)
- Removing Eq8 from kick: avg +3.2 health (MEDIUM confidence)
- Disabling unused Reverb: avg +2.8 health (MEDIUM confidence)

**Patterns That Hurt:**
- Adding 3+ compressors: avg -4.5 health (HIGH confidence)
- Enabling bypassed limiters: avg -2.1 health (LOW confidence)

**Common Mistakes:**
- "Adding Saturator tends to hurt health" (15 occurrences, -3.2 avg)
- "Enabling disabled AutoFilter tends to hurt health" (8 occurrences, -2.1 avg)

---

## Integration with Existing Features

Phase 2 Intelligence builds on Phase 1 foundations:

| Phase 1 Feature | Phase 2 Enhancement |
|-----------------|---------------------|
| `db history` | Now feeds into trend analysis |
| `db changes` | Now includes predicted impacts |
| `db insights` | Now has confidence levels |
| `diagnose` | Now can use `db smart` for prioritization |
| `coach` mode | Can incorporate pattern-based suggestions |

---

## Technical Implementation

### New Database Tables/Fields

The existing `changes` table stores:
```sql
- change_type: 'device_added', 'device_removed', etc.
- device_type: 'Eq8', 'Compressor2', etc.
- health_delta: actual change in health score
```

### New Functions (database.py)

```python
# Trend analysis
analyze_project_trend(search_term) -> ProjectTrend

# What-if predictions
get_what_if_predictions(als_path) -> WhatIfAnalysis

# Enhanced change impact
get_change_impact_predictions(search_term) -> List[ChangeImpactPrediction]
```

### CLI Commands (als_doctor.py)

```python
@db.command('trend')      # cmd_db_trend
@db.command('whatif')     # cmd_db_whatif
@db.command('recommend')  # cmd_db_recommend
@db.command('patterns')   # cmd_db_patterns (shows learned patterns)
```

---

## Future Enhancements (Phase 3)

- **User feedback loop**: Track which recommendations you implement
- **Outcome verification**: Did the predicted improvement actually happen?
- **Weight refinement**: Learn from actual outcomes vs predictions
- **Similarity matching**: "This track is similar to your Grade A tracks"
- **Automated suggestions**: Proactive alerts when patterns are detected

---

## Summary

Phase 2 turns ALS Doctor into a personalized production coach:

1. **Track Changes** - `db changes <song> --compute`
2. **See Trends** - `db trend <song>`
3. **Predict Outcomes** - `db whatif <file>`
4. **Get Smart Advice** - `db recommend`
5. **Learn Patterns** - `db insights`

The more you scan, the smarter it gets.
