# AI Mix Recommendation Pipeline

## Overview

This document outlines the end-to-end pipeline for analyzing music productions and generating AI-powered mixing recommendations.

---

## Pipeline Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER INPUT                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  Audio File (.wav/.flac/.mp3)  +  Optional: Reference Track  +  .als file  │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        STAGE 1: ANALYSIS ENGINE                              │
│                        (analyze.py + src modules)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │    Audio     │  │    Stem      │  │  Reference   │  │   Section    │    │
│  │   Analyzer   │  │  Separator   │  │  Comparator  │  │   Detector   │    │
│  │              │  │   (Demucs)   │  │              │  │              │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                 │                 │             │
│         ▼                 ▼                 ▼                 ▼             │
│  • Loudness (LUFS)  • Vocals stem    • Stem-by-stem    • Intro/Drop/etc   │
│  • Dynamics         • Drums stem       comparison      • Timestamps        │
│  • Frequency        • Bass stem      • dB differences  • Energy levels     │
│  • Stereo/Phase     • Other stem     • Recommendations • Contrast scores   │
│  • Clipping                                                                 │
│  • Transients                                                               │
│                                                                              │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        STAGE 2: REPORT GENERATION                            │
│                        (reporter.py)                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         JSON Report                                   │   │
│  │  {                                                                    │   │
│  │    "audio_analysis": { loudness, dynamics, frequency, stereo... }    │   │
│  │    "comparison_result": { stem_comparisons, overall_score... }       │   │
│  │    "section_analysis": { sections[], timestamps... }                 │   │
│  │  }                                                                    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                        │                                     │
│                    ┌───────────────────┼───────────────────┐                │
│                    ▼                   ▼                   ▼                │
│             ┌──────────┐        ┌──────────┐        ┌──────────┐           │
│             │   HTML   │        │   JSON   │        │   Text   │           │
│             │  Report  │        │  Export  │        │  Report  │           │
│             └──────────┘        └──────────┘        └──────────┘           │
│                                                                              │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        STAGE 3: AI RECOMMENDATION                            │
│                        (Claude + Triage → Specialist Prompts)                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Step 1: Run TRIAGE first (always)                                          │
│  claude --add-file "prompts/Triage.md" --add-file "analysis.json"           │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         TRIAGE ROUTER                                 │   │
│  │  • Shows current state snapshot (all metrics)                        │   │
│  │  • Detects issues across ALL categories                              │   │
│  │  • Calculates priority scores                                        │   │
│  │  • Routes to specific specialists with focus areas                   │   │
│  │  • Lists quick wins                                                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                        │                                     │
│                        Triage Output: "Run these specialists..."            │
│                                        │                                     │
│  Step 2: Run RECOMMENDED SPECIALISTS                                         │
│         ┌──────────────────────────────┼──────────────────────────────┐     │
│         ▼                              ▼                              ▼     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   LowEnd    │  │  Dynamics   │  │  Sections   │  │    etc.     │        │
│  │ (if routed) │  │ (if routed) │  │ (if routed) │  │             │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                                              │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        STAGE 4: OUTPUT                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                    AI-Generated Report                              │     │
│  │                                                                     │     │
│  │  • Executive Summary (overall status, biggest problem)             │     │
│  │  • Fix These First (top 5-7 prioritized issues with scores)        │     │
│  │  • Category Breakdown (issues grouped by type)                     │     │
│  │  • What's Working Well (positive feedback)                         │     │
│  │  • Quick Wins (easy high-impact fixes)                             │     │
│  │                                                                     │     │
│  │  Each issue includes:                                               │     │
│  │    - Priority score (Base × Category × Scope)                      │     │
│  │    - Specific measurements                                          │     │
│  │    - Step-by-step fix with exact values                            │     │
│  │    - Expected result                                                │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Current Components

### Stage 1: Analysis Engine

| Component | File | Purpose |
|-----------|------|---------|
| Audio Analyzer | `src/audio_analyzer.py` | Extracts loudness, dynamics, frequency, stereo, transients |
| Stem Separator | `src/stem_separator.py` | Demucs-based 4-stem separation (vocals, drums, bass, other) |
| Reference Comparator | `src/reference_comparator.py` | Compares user mix to reference track stem-by-stem |
| Reference Storage | `src/reference_storage.py` | Stores analyzed reference tracks for reuse |

### Stage 2: Report Generation

| Component | File | Purpose |
|-----------|------|---------|
| Reporter | `src/reporter.py` | Generates HTML, JSON, and text reports |
| CLI | `analyze.py` | Command-line interface for running analysis |

### Stage 3: AI Recommendation

| Component | File | Purpose |
|-----------|------|---------|
| **Triage** | `prompts/Triage.md` | **ENTRY POINT** - Prioritizes all issues, routes to specialists |
| Master Guide | `RecommendationGuide.md` | Legacy main prompt (still works) |
| Low End | `prompts/LowEnd.md` | Kick/bass relationship, sub, sidechain |
| Frequency | `prompts/FrequencyBalance.md` | Spectral balance, EQ, mud/harshness |
| Dynamics | `prompts/Dynamics.md` | Crest factor, compression, punch |
| Stereo/Phase | `prompts/StereoPhase.md` | Correlation, mono compatibility, width |
| Loudness | `prompts/Loudness.md` | LUFS, true peak, streaming targets |
| Sections | `prompts/Sections.md` | Drop impact, breakdown energy, transitions |
| Trance Arrangement | `prompts/TranceArrangement.md` | 8-bar rule, buildup mechanics |
| Stem Reference | `prompts/StemReference.md` | Stem-by-stem reference comparison |

---

## Data Flow

```
1. INPUT
   └── Audio file (WAV/FLAC/MP3)
   └── Reference track (optional)
   └── Ableton project (future)

2. EXTRACTION
   └── Librosa: spectral analysis, transients
   └── Pyloudnorm: ITU-R BS.1770-4 LUFS measurement
   └── Soundfile: audio I/O
   └── Demucs: AI stem separation

3. ANALYSIS
   └── Per-sample: clipping detection
   └── Per-frame: spectral centroid, RMS, correlation
   └── Per-stem: level, width, frequency balance
   └── Whole-file: integrated LUFS, dynamic range

4. COMPARISON (if reference provided)
   └── Separate both tracks into stems
   └── Analyze each stem independently
   └── Calculate differences (dB, %, Hz)
   └── Generate severity ratings
   └── Create per-stem recommendations

5. REPORT
   └── JSON: machine-readable, complete data
   └── HTML: human-readable, visualizations
   └── Text: console-friendly summary

6. AI ANALYSIS (Triage-First Workflow)
   └── Step 1: Run Triage.md
       └── Scans all JSON fields
       └── Detects and prioritizes all issues
       └── Routes to specific specialists
   └── Step 2: Run recommended specialists
       └── Each specialist provides deep, actionable fixes
       └── Focus on areas Triage identified
```

---

## Priority Scoring System

```
Priority Score = Base Severity × Category Multiplier × Scope Multiplier

Base Severity:
  CRITICAL = 100 (mix broken)
  SEVERE   = 70  (major issue)
  MODERATE = 40  (noticeable issue)
  MINOR    = 15  (polish item)

Category Multipliers:
  Phase/Mono    = ×3.0  (playback failure)
  Clipping      = ×2.5  (audible damage)
  Low-end       = ×2.5  (foundation)
  Loudness      = ×2.0  (streaming)
  Stereo        = ×2.0  (professional width)
  Frequency     = ×1.5  (clarity)
  Dynamics      = ×1.5  (punch)
  Sections      = ×1.5  (arrangement)

Scope Multipliers:
  Entire mix       = ×1.5
  Multiple sections = ×1.2
  Single section   = ×1.0
  Single track     = ×0.8

Example:
  Phase cancellation (entire mix)
  = 100 × 3.0 × 1.5 = 450 (CRITICAL tier)
```

---

## Improvement Opportunities

### 1. AUTOMATION GAPS

**Current State**: User must manually run Claude with JSON + prompt files

**Improvements**:

| Improvement | Description | Impact |
|-------------|-------------|--------|
| **Pre-calculated Scores** | Analyzer calculates priority scores in JSON | Claude can skip calculation |
| **Auto Executive Summary** | Reporter generates summary template | Faster AI response |
| **One-Command Analysis** | `analyze.py --ai-recommend` pipes to Claude | Seamless UX |
| **Batch Processing** | Analyze multiple versions, compare progress | Track improvement |

### 2. MISSING ANALYSIS TYPES

**Current State**: Audio-only analysis, no project/MIDI data

**Improvements**:

| Feature | Description | Value |
|---------|-------------|-------|
| **Ableton .als Parsing** | Extract track volumes, pan, devices | Gain staging, stereo field |
| **MIDI Analysis** | Velocity variation, note density, chords | Humanization, arrangement |
| **Key/Scale Detection** | Identify key, detect out-of-key notes | Harmonic clashes |
| **Tempo Analysis** | BPM changes, groove/swing detection | Timing issues |
| **Automation Curves** | Extract filter sweeps, volume rides | Transition quality |

### 3. REFERENCE COMPARISON ENHANCEMENTS

**Current State**: Single reference track, whole-file comparison

**Improvements**:

| Feature | Description | Value |
|---------|-------------|-------|
| **Multi-Reference Averaging** | Average 3-5 reference tracks | Reduce outlier influence |
| **Genre Profiles** | Pre-built targets for trance/house/etc | No reference needed |
| **Section-to-Section** | Compare drop-to-drop, breakdown-to-breakdown | Precise section matching |
| **A/B Versioning** | Compare v1 vs v2 of same project | Track progress |
| **Reference Library UI** | Browse/search stored references | Easier workflow |

### 4. OUTPUT IMPROVEMENTS

**Current State**: Static reports (HTML/JSON/text)

**Improvements**:

| Feature | Description | Value |
|---------|-------------|-------|
| **Interactive HTML** | Clickable waveform, jump to timestamps | Navigate issues |
| **Fix Checklist** | Checkboxes that persist state | Track completed fixes |
| **Before/After Compare** | Side-by-side spectrograms | Verify improvements |
| **Export to DAW** | Generate Ableton markers at issue timestamps | Direct workflow |
| **Progress Tracking** | Compare scores across versions | Measure improvement |

### 5. INTEGRATION IDEAS

**Current State**: Standalone CLI tool

**Improvements**:

| Integration | Description | Value |
|-------------|-------------|-------|
| **Max for Live Device** | Real-time analysis in Ableton | Live feedback |
| **VST/AU Plugin** | Standalone analyzer plugin | DAW-agnostic |
| **Web Dashboard** | Upload audio, view reports online | Share with collaborators |
| **CI/CD Pipeline** | Automated quality gates for releases | Professional workflow |
| **Discord/Slack Bot** | Upload audio, get recommendations | Social workflow |

---

## Proposed Enhanced Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ENHANCED PIPELINE (FUTURE)                            │
└─────────────────────────────────────────────────────────────────────────────┘

Phase 1: Multi-Source Input
├── Audio files (.wav, .flac, .mp3)
├── Ableton projects (.als) ← NEW
├── MIDI files (.mid) ← NEW
├── Reference library (stored profiles)
└── Genre presets (trance, house, dnb)

Phase 2: Comprehensive Analysis
├── Audio Analysis (current)
│   ├── Loudness, dynamics, frequency, stereo, transients
│   └── Clipping, phase, correlation
├── Project Analysis ← NEW
│   ├── Track hierarchy, gain staging
│   ├── Device chains, plugin detection
│   └── Automation curves
├── MIDI Analysis ← NEW
│   ├── Velocity distribution, humanization score
│   ├── Note density per section
│   └── Chord progressions, key detection
└── Stem Separation (current)
    └── Demucs 4-stem + optional 6-stem mode

Phase 3: Smart Comparison
├── Multi-reference averaging ← NEW
├── Section-aligned comparison ← NEW
├── Genre-specific targets ← NEW
└── Version-to-version tracking ← NEW

Phase 4: AI-Powered Recommendations
├── Pre-calculated priority scores ← NEW
├── Context-aware specialist routing
├── Incremental improvement suggestions ← NEW
└── DAW-specific fix instructions ← NEW

Phase 5: Rich Output
├── Interactive HTML with waveform ← NEW
├── Fix checklist with state ← NEW
├── Ableton marker export ← NEW
├── Progress dashboard ← NEW
└── Shareable report links ← NEW
```

---

## Implementation Priority

### Phase 1: Quick Wins (Low effort, High impact)

1. **Pre-calculate priority scores in JSON**
   - Add `priority_score` to each issue in `overall_issues`
   - AI can skip calculation, just sort and display

2. **One-command AI analysis**
   - `analyze.py --ai-recommend` pipes JSON to Claude
   - Includes appropriate specialist prompts automatically

3. **Genre presets**
   - Store target values for trance, house, techno, dnb
   - User selects genre, analysis uses those targets

### Phase 2: Medium Effort (High value)

4. **Ableton .als parsing**
   - Extract track volumes, pan positions, device chains
   - Enable gain staging and stereo field audits

5. **Section-aligned comparison**
   - Detect sections in both tracks
   - Compare drop-to-drop, breakdown-to-breakdown

6. **Interactive HTML report**
   - Waveform with clickable issue markers
   - Expandable fix details

### Phase 3: Major Features (High effort, Transformative)

7. **MIDI velocity/humanization analysis**
   - Parse MIDI clips from .als or standalone .mid
   - Score humanization, detect robotic patterns

8. **Multi-reference averaging**
   - Store multiple references per genre
   - Generate averaged target profile

9. **Progress tracking dashboard**
   - Store analysis history per project
   - Visualize improvement over time

---

## Questions to Consider

1. **Should priority scores be calculated in Python or by AI?**
   - Python: Consistent, fast, deterministic
   - AI: Contextual, can weigh factors dynamically
   - Hybrid: Python calculates, AI can override with justification

2. **How granular should section comparison be?**
   - Whole sections (drop vs drop): Simpler, less noise
   - Bar-by-bar: More precise, but more complex
   - Automatic: AI decides based on section similarity

3. **What's the right number of reference tracks to average?**
   - 1: Quick, but outlier-prone
   - 3-5: Good balance
   - 10+: Diminishing returns, slower processing

4. **Should we support DAWs other than Ableton?**
   - Logic Pro (.logicx): Large user base
   - FL Studio (.flp): Popular for EDM
   - Pro Tools (.ptx): Professional studios
   - Reaper (.rpp): Growing community

5. **Real-time vs batch analysis?**
   - Real-time: Immediate feedback, resource-intensive
   - Batch: More thorough, better for final checks
   - Hybrid: Quick real-time, detailed batch on export

---

## Next Steps

1. Review this document and identify priorities
2. Create GitHub issues for approved improvements
3. Implement Phase 1 quick wins
4. Gather user feedback on current pipeline
5. Iterate based on real-world usage
