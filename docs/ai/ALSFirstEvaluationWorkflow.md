# ALS-First Evaluation Workflow
## No-Export Project Analysis with Optional Deep Dives

A streamlined workflow that evaluates Ableton projects **without requiring audio export**. Start with instant ALS analysis, then optionally add audio analysis and LLM expert recommendations.

---

## Table of Contents
- [Overview](#overview)
- [Phase 1: ALS Quick Check (Required)](#phase-1-als-quick-check-required)
- [Phase 2: Full ALS Diagnosis (Optional)](#phase-2-full-als-diagnosis-optional)
- [Phase 3: Audio Analysis (Optional)](#phase-3-audio-analysis-optional)
- [Phase 4: LLM Expert Analysis (Optional)](#phase-4-llm-expert-analysis-optional)
- [Workflow Paths](#workflow-paths)
- [Decision Tree](#decision-tree)

---

## Overview

### The Problem This Solves

Traditional workflow requires:
1. Export mix from Ableton (slow, friction)
2. Export stems (even slower)
3. Run analysis
4. Get overwhelmed by 17 different expert reports
5. Song ends up worse because you changed too many things

### The ALS-First Approach

```
1. ALS Quick Check (30 sec) → Know if project is worth working on
2. ALS Diagnosis (2 min) → Get specific device-level fixes
3. [OPTIONAL] Audio Analysis → Deep dive if needed
4. [OPTIONAL] LLM Experts → Domain-specific recommendations
```

### Key Benefits

- **No export required** for Phases 1-2
- **Instant feedback** - know your project health in seconds
- **Actionable fixes** - specific device changes, not vague suggestions
- **Version tracking** - see if changes help or hurt
- **Optional depth** - only run audio/LLM analysis when needed

---

## Phase 1: ALS Quick Check (Required)

**Time:** 30 seconds
**Requires:** Only the .als file
**Purpose:** Decide if project is worth working on right now

### Run Quick Check

```cmd
als-doctor quick "D:\Path\To\project.als"
```

### Output Example

```
[B] 72/100 - GOOD
    8 issues (2 critical, 4 warnings)
    45 devices, 12 disabled (27% clutter)
```

### Interpret Results

| Grade | Action |
|-------|--------|
| A (80-100) | Great shape - polish and release |
| B (60-79) | Good foundation - run Phase 2 for specifics |
| C (40-59) | Needs cleanup - run Phase 2, prioritize fixes |
| D (20-39) | Significant issues - consider which version to use |
| F (0-19) | Major problems - compare to earlier versions |

### Decision Point

- **Grade A-B:** Proceed to Phase 2 or skip to Phase 3 (audio)
- **Grade C-D:** Run Phase 2, fix issues before any audio work
- **Grade F:** Run version comparison, might need to roll back

---

## Phase 2: Full ALS Diagnosis (Optional)

**Time:** 2-5 minutes
**Requires:** Only the .als file
**Purpose:** Get specific, actionable device-level fixes

### Run Full Diagnosis

```cmd
als-doctor diagnose "D:\Path\To\project.als"
```

### Output Example

```
================================================================
         ALS DOCTOR - PROJECT DIAGNOSIS
================================================================

Project: MyTrack.als
Health Score: 72/100 [B - GOOD]

----------------------------------------------------------------
ISSUES BY TRACK
----------------------------------------------------------------

[!!!] CRITICAL - Bass (2 issues)
  - Limiter should be LAST in chain, found at position 2/4
    => Move Limiter after Saturator
  - Compressor ratio at infinity:1 (brick wall limiting)
    => Reduce ratio to 4:1 or less for musical compression

[!!] WARNING - Lead Synth (1 issue)
  - 3 EQ Eight devices in series
    => Consolidate into single EQ, remove duplicates

[!] WARNING - Hi-Hat (1 issue)
  - De-esser on non-vocal track
    => Remove De-esser, use EQ for high frequency control

[i] SUGGESTION - Master (1 issue)
  - Utility device not at end of chain
    => Move Utility to end for final gain staging

----------------------------------------------------------------
CLUTTER ANALYSIS
----------------------------------------------------------------
Total Devices: 45
Disabled (OFF): 12 (27%)
=> Delete disabled devices to reduce project clutter

----------------------------------------------------------------
SUMMARY
----------------------------------------------------------------
Critical: 2 | Warnings: 4 | Suggestions: 2

TOP 3 FIXES:
1. Fix Limiter position on Bass track
2. Reduce Compressor ratio on Bass track
3. Remove duplicate EQs on Lead Synth
```

### Make Fixes in Ableton

1. Open the .als file in Ableton
2. Fix issues in priority order (Critical > Warning > Suggestion)
3. Save the project
4. Re-run diagnosis to verify fixes

### Version Comparison

After making changes, compare versions:

```cmd
als-doctor compare "project_before.als" "project_after.als"
```

Output:
```
HEALTH CHANGE: 72 => 89 (+17) [IMPROVED]

FIXED:
  - Bass: Limiter position
  - Bass: Compressor ratio
  - Lead Synth: Duplicate EQs removed

REMAINING:
  - Hi-Hat: De-esser still present
  - Master: Utility position
```

### Decision Point

- **Health improved:** Continue to Phase 3 if you want audio analysis
- **Health same/worse:** Review what changed, possibly roll back
- **All issues fixed:** Project is clean, proceed to audio if desired

---

## Phase 3: Audio Analysis (Optional)

**Time:** 5-15 minutes
**Requires:** Exported audio (mix and/or stems)
**Purpose:** Analyze actual audio characteristics

### When to Use Phase 3

Use audio analysis when:
- ALS looks clean but mix still sounds wrong
- You need frequency/loudness measurements
- You want to compare against a reference track
- You're preparing for mastering

### Skip Phase 3 When

- ALS has critical issues (fix those first)
- You're just cleaning up a project
- You don't have time to export audio

### Export Requirements

**Minimum:** Mix only (master track export)
```
inputs/MySong/mix/v1/mix.flac
```

**Better:** Mix + stems
```
inputs/MySong/
  ├── mix/v1/mix.flac
  └── stems/
      ├── kick.wav
      ├── bass.wav
      └── ...
```

**Best:** Mix + stems + reference
```
inputs/MySong/
  ├── mix/v1/mix.flac
  ├── stems/...
  └── references/
      └── pro_track.wav
```

### Run Audio Analysis

```bash
cd C:\claude-workspace\AbletonAIAnalysis\projects\music-analyzer
python analyze.py --song MySong
```

### What You Get

| Analysis | What It Tells You |
|----------|-------------------|
| Clipping | Samples exceeding safe levels |
| Dynamics | Peak vs RMS, compression level |
| Frequency | Energy per band (sub to air) |
| Stereo | Width, correlation, mono safety |
| Loudness | LUFS for streaming platforms |
| Stems | Frequency clashes between tracks |
| Reference | How you compare to pro tracks |

### Decision Point

- **Issues found:** Fix in Ableton, re-export, re-analyze
- **Looks good:** Proceed to Phase 4 or finish
- **Need expert advice:** Continue to Phase 4

---

## Phase 4: LLM Expert Analysis (Optional)

**Time:** Variable
**Requires:** Audio analysis results from Phase 3
**Purpose:** Get domain-specific recommendations from specialized prompts

### When to Use Phase 4

Use LLM experts when:
- You want genre-specific advice
- You need help with a specific aspect (mastering, stereo, etc.)
- Audio analysis shows issues you don't know how to fix
- You want to learn mixing techniques

### Skip Phase 4 When

- Quick cleanup session
- You know what to fix already
- Time-constrained
- ALS + Audio analysis already gave clear direction

### Available Expert Modules

| Expert | Focus |
|--------|-------|
| Mix Engineer | Overall balance, separation |
| Mastering | Loudness, limiting, final polish |
| Stereo Field | Width, panning, correlation |
| Low End | Bass, kick, sub management |
| Dynamics | Compression, transients |
| Frequency | EQ, spectral balance |
| EDM/Trance | Genre-specific techniques |
| Psychoacoustics | Human perception optimization |

### Request Specific Experts

Instead of running all 17 experts, request only what you need:

```
"Analyze my mix focusing on low-end management and stereo width"
"Give me mastering recommendations for trance music"
"Help me fix the bass/kick clash identified in the analysis"
```

### Decision Point

- **Got actionable advice:** Implement in Ableton
- **Conflicting advice:** Trust your ears, pick one approach
- **Still stuck:** Try different reference track or get human feedback

---

## Workflow Paths

### Path A: Quick Cleanup (5 min)

```
ALS Quick Check → Grade B or better → Done
       ↓
   Grade C or lower
       ↓
ALS Full Diagnosis → Fix 3-5 issues → Re-check → Done
```

**Use for:** Quick project triage, cleanup sessions

### Path B: Standard Evaluation (15-30 min)

```
ALS Quick Check → ALS Diagnosis → Fix issues → Version Compare
                                      ↓
                              Health improved?
                                      ↓
                         Yes: Audio Analysis (optional)
                         No: Roll back, try different approach
```

**Use for:** Active projects you're improving

### Path C: Full Analysis (1-2 hours)

```
ALS Quick Check → ALS Diagnosis → Fix issues → Audio Export
                                                    ↓
                                            Audio Analysis
                                                    ↓
                                         Issues found? Fix them
                                                    ↓
                                         LLM Expert Analysis
                                                    ↓
                                      Implement recommendations
```

**Use for:** Final polish, preparing for release

### Path D: Portfolio Triage (30 min)

```
Batch Scan all projects → Sort by health → Pick best candidates
          ↓
als-doctor scan "D:\Projects" --min-number 20 --limit 30
          ↓
Work on Grade B-C projects (most potential)
Skip Grade F projects (too broken)
Polish Grade A projects (nearly done)
```

**Use for:** Deciding what to work on

---

## Decision Tree

```
START: Want to evaluate a project
  │
  ├─► Run: als-doctor quick "project.als"
  │
  ├─► Grade A? ──────► Project is healthy
  │     │               ├─► Want audio analysis? → Phase 3
  │     │               └─► Done
  │     │
  ├─► Grade B-C? ────► Run: als-doctor diagnose "project.als"
  │     │               │
  │     │               ├─► Fix 3-5 issues in Ableton
  │     │               ├─► Save new version
  │     │               ├─► Run: als-doctor compare old.als new.als
  │     │               │
  │     │               ├─► Health improved? ───► Continue or Phase 3
  │     │               └─► Health worse? ──────► Roll back, try again
  │     │
  ├─► Grade D-F? ────► Compare to older versions
  │                     │
  │                     ├─► als-doctor scan "project folder"
  │                     ├─► Find best version
  │                     └─► Work from that version instead
  │
  └─► END
```

---

## Tips

### For Quick Sessions
- Run quick check on 5-10 projects
- Pick the Grade B-C ones (most potential for improvement)
- Fix 3-5 issues per project
- Don't touch audio export

### For Deep Dives
- Start with ALS diagnosis even if you plan audio analysis
- Fix ALS issues BEFORE exporting audio
- Cleaner project = cleaner export

### For Tracking Progress
- Always save .als backup before changes
- Use als-doctor compare after each session
- Stop when health score stops improving

### For Learning
- Run full diagnosis on professional Ableton templates
- See how pros organize their device chains
- Compare your projects to templates

---

## Command Reference

```cmd
# Quick health check (30 sec)
als-doctor quick "project.als"

# Full diagnosis with specific fixes (2 min)
als-doctor diagnose "project.als"

# Compare two versions
als-doctor compare "before.als" "after.als"

# Scan and rank multiple projects
als-doctor scan "D:\Projects" --limit 20

# Filter by project number
als-doctor scan "D:\Projects" --min-number 22

# Export diagnosis to JSON
als-doctor diagnose "project.als" --json report.json
```

---

## Integration with Existing Workflow

This workflow **replaces or precedes** the [AI-Assisted Production Workflow](AIAssistedProductionWorkflow.md):

| Old Workflow | ALS-First Workflow |
|--------------|-------------------|
| Export first | ALS check first (no export) |
| Audio analysis required | Audio analysis optional |
| All experts run | Experts optional |
| Fix based on audio | Fix based on project structure |
| No version tracking | Built-in version comparison |

**Recommended:** Run ALS-First workflow (Phases 1-2) before any audio export. Only proceed to audio analysis (Phase 3) and LLM experts (Phase 4) when ALS is clean.

---

*Last updated: January 2026*
