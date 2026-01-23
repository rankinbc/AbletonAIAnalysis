# Mix Recommendation Module System

This folder contains specialized AI prompts for analyzing music production JSON files. Each prompt focuses on a specific aspect of mixing and provides **actionable, specific recommendations**.

---

## Recommended Workflow

### Step 1: Run the analyzer
```bash
python analyze.py --song MySong
```

### Step 2: Run Triage FIRST (always)
```bash
claude --add-file "docs/ai/RecommendationGuide/prompts/Triage.md" --add-file "reports/MySong/MySong_v1_analysis_2026-01-14.json"
```

Ask: "Triage my mix"

Triage will:
- Show you the **current state** of your mix (all metrics at a glance)
- Identify and **prioritize all issues** across every category
- Tell you **which specialists to run** and what to focus on
- List **quick wins** you can fix immediately

### Step 3: Run the specialists Triage recommends
```bash
claude --add-file "docs/ai/RecommendationGuide/prompts/LowEnd.md" --add-file "reports/MySong/MySong_v1_analysis_2026-01-14.json"
```

Ask: "Analyze my mix, focusing on [what Triage told you]"

---

## System Entry Point

| Prompt | File | Purpose |
|--------|------|---------|
| **Triage** | `prompts/Triage.md` | **START HERE** - Prioritizes all issues, routes to specialists |

---

## Available Specialists

### Core Mix Analysis
| Specialist | File | Focus Area |
|------------|------|------------|
| **Low End** | `prompts/LowEnd.md` | Kick/bass relationship, sub-bass, sidechain, low-end clarity |
| **Frequency Balance** | `prompts/FrequencyBalance.md` | EQ decisions, muddy frequencies, harshness, frequency clashes |
| **Dynamics** | `prompts/Dynamics.md` | Compression, transients, punch, crest factor, dynamic range |
| **Stereo & Phase** | `prompts/StereoPhase.md` | Width, mono compatibility, phase issues, panning |
| **Loudness** | `prompts/Loudness.md` | LUFS targets, true peak, streaming optimization, limiting |
| **Sections** | `prompts/Sections.md` | Drop impact, breakdown energy, transitions, arrangement |

### Trance-Specific
| Specialist | File | Focus Area |
|------------|------|------------|
| **Trance Arrangement** | `prompts/TranceArrangement.md` | Section contrast, buildup mechanics, drop impact, 8-bar rule |

### Reference Comparison
| Specialist | File | Focus Area |
|------------|------|------------|
| **Stem Reference** | `prompts/StemReference.md` | Stem-by-stem comparison with reference tracks |

### Extended Analysis (NEW)
| Specialist | File | Focus Area |
|------------|------|------------|
| **Harmonic Analysis** | `prompts/HarmonicAnalysis.md` | Key detection, Camelot notation, DJ mixing compatibility |
| **Clarity Analysis** | `prompts/ClarityAnalysis.md` | Spectral clarity, masking risk, frequency separation |
| **Spatial Analysis** | `prompts/SpatialAnalysis.md` | 3D spatial perception (height, depth, width) |
| **Surround Compatibility** | `prompts/SurroundCompatibility.md` | Mono compatibility, phase coherence for all playback |
| **Playback Optimization** | `prompts/PlaybackOptimization.md` | Headphone/speaker optimization, bass translation |
| **Overall Score** | `prompts/OverallScore.md` | Weighted quality score interpretation and improvement plan |

### Additional Analysis (Advanced)
| Specialist | File | Focus Area |
|------------|------|------------|
| **Gain Staging** | `prompts/GainStagingAudit.md` | Level management, headroom, gain structure |
| **Stereo Field** | `prompts/StereoFieldAudit.md` | Detailed stereo image analysis |
| **Frequency Collision** | `prompts/FrequencyCollisionDetection.md` | Element-by-element frequency clashes |
| **Dynamics Humanization** | `prompts/DynamicsHumanizationReport.md` | Natural dynamics, velocity variation |
| **Section Contrast** | `prompts/SectionContrastAnalysis.md` | Energy flow between sections |
| **Density & Busyness** | `prompts/DensityBusynessReport.md` | Arrangement density, element count |
| **Chord & Harmony** | `prompts/ChordHarmonyAnalysis.md` | Chord progressions, harmonic analysis |
| **Device Chain** | `prompts/DeviceChainAnalysis.md` | Plugin/effect chain optimization |
| **Priority Summary** | `prompts/PriorityProblemSummary.md` | Aggregated issues ranked by priority |

---

## Recommended Order

**Always start with Triage.** It will tell you which specialists to run.

If running manually without Triage, use this order:

1. **Stereo & Phase** - Fix phase issues FIRST (everything else is meaningless if phase is broken)
2. **Low End** - Foundation must be solid
3. **Dynamics** - Get punch and energy right
4. **Sections** - Check arrangement/energy flow
5. **Frequency Balance** - Fix major EQ issues
6. **Loudness** - Final loudness optimization

---

## Quick Commands

```bash
# Low End Analysis
claude --add-file "C:\claude-workspace\AbletonAIAnalysis\docs\ai\RecommendationGuide\prompts\LowEnd.md" --add-file "<json_path>"

# Frequency Balance Analysis
claude --add-file "C:\claude-workspace\AbletonAIAnalysis\docs\ai\RecommendationGuide\prompts\FrequencyBalance.md" --add-file "<json_path>"

# Dynamics Analysis
claude --add-file "C:\claude-workspace\AbletonAIAnalysis\docs\ai\RecommendationGuide\prompts\Dynamics.md" --add-file "<json_path>"

# Stereo & Phase Analysis
claude --add-file "C:\claude-workspace\AbletonAIAnalysis\docs\ai\RecommendationGuide\prompts\StereoPhase.md" --add-file "<json_path>"

# Loudness Analysis
claude --add-file "C:\claude-workspace\AbletonAIAnalysis\docs\ai\RecommendationGuide\prompts\Loudness.md" --add-file "<json_path>"

# Section Analysis
claude --add-file "C:\claude-workspace\AbletonAIAnalysis\docs\ai\RecommendationGuide\prompts\Sections.md" --add-file "<json_path>"
```

---

## Output Format (All Specialists Use This)

Each specialist will provide:

```markdown
# [SPECIALIST] Analysis Results

## Verdict: [PASS / NEEDS WORK / CRITICAL ISSUES]

## Issues Found (Priority Order)

### 1. [Issue Name]
- **Problem**: What's wrong and why it matters
- **Location**: Timestamp or element
- **Fix**: Exact steps with specific values
- **Ableton Tip**: Specific plugin/technique suggestion

### 2. [Next Issue]
...

## Summary Checklist
- [ ] Fix 1: [one-line summary]
- [ ] Fix 2: [one-line summary]
...
```

---

## Files in This Directory

```
RecommendationGuide/
├── INDEX.md                    # This file
├── PIPELINE.md                 # System architecture documentation
├── RecommendationGuide.md      # General guide (legacy, still works)
└── prompts/
    │
    │   # ENTRY POINT (Run First)
    ├── Triage.md               # START HERE - Prioritizes issues, routes to specialists
    │
    │   # Core Mix Analysis
    ├── LowEnd.md               # Core: Kick/bass/sub
    ├── FrequencyBalance.md     # Core: EQ & frequency
    ├── Dynamics.md             # Core: Compression & transients
    ├── StereoPhase.md          # Core: Stereo & phase
    ├── Loudness.md             # Core: Loudness & mastering
    ├── Sections.md             # Core: Section arrangement
    │
    │   # Trance-Specific
    ├── TranceArrangement.md    # Trance-specific arrangement
    │
    │   # Reference Comparison
    ├── StemReference.md        # Reference track comparison
    │
    │   # Extended Analysis
    ├── HarmonicAnalysis.md     # Key detection, Camelot, DJ mixing
    ├── ClarityAnalysis.md      # Spectral clarity, masking risk
    ├── SpatialAnalysis.md      # 3D spatial (height, depth, width)
    ├── SurroundCompatibility.md # Mono compatibility, phase
    ├── PlaybackOptimization.md # Headphone/speaker optimization
    ├── OverallScore.md         # Weighted quality score guide
    │
    │   # Advanced Analysis
    ├── GainStagingAudit.md     # Advanced: Gain staging
    ├── StereoFieldAudit.md     # Advanced: Stereo field
    ├── FrequencyCollisionDetection.md
    ├── DynamicsHumanizationReport.md
    ├── SectionContrastAnalysis.md
    ├── DensityBusynessReport.md
    ├── ChordHarmonyAnalysis.md
    ├── DeviceChainAnalysis.md
    └── PriorityProblemSummary.md
```
