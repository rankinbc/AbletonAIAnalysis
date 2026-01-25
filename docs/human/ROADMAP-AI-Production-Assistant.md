# AI-Assisted Trance Production System - Roadmap

**Created**: 2026-01-25
**Status**: Planning
**Goal**: Transform AbletonAIAnalysis from a post-analysis tool into a real-time AI production assistant that can guide trance music creation.

---

## Vision

> "AI-assisted music production where the AI handles making it sound good, and you inject your creativity where you want."

The system will learn what makes professional trance tracks sound polished by analyzing your reference library, then provide real-time guidance and automated fixes while you produce in Ableton.

---

## Feature Overview

| # | Feature | Status | Priority | Complexity |
|---|---------|--------|----------|------------|
| 1 | **Ableton Integration (AbletonOSC)** | ✅ DONE | - | - |
| 2 | **"Apply Fixes" Interface** | Ready to build | HIGH | Medium |
| 3 | **Synth Extraction Workflow** | Document & Integrate | MEDIUM | Low |
| 4 | **ML Trance Analysis Model** | Needs planning | HIGH | High |
| 5 | **Real-Time Production Guide** | Future | LOW | Very High |

---

## Feature 1: Ableton Integration ✅ COMPLETE

### What's Done
- AbletonOSC installed in `User Library/Remote Scripts/AbletonOSC/`
- PyLive + python-osc installed
- `src/ableton_bridge.py` module created with:
  - Connection management
  - Session state reading (tracks, devices, parameters)
  - Parameter writing (volume, pan, mute, device params)
  - Batch change application
  - Transport controls

### Usage
```python
from src.ableton_bridge import quick_connect, TrackChange, Fix

bridge = quick_connect()
state = bridge.read_session_state()

# Apply a fix
fix = Fix(
    id="reduce-bass",
    description="Reduce bass by 3dB",
    category="mixing",
    severity="suggestion",
    changes=[TrackChange(1, 'volume', 0.7, "Bass too loud")]
)
bridge.apply_fix(fix)
```

---

## Feature 2: "Apply Fixes" Interface

### Goal
Create a UI that shows analysis results and lets user apply recommended fixes to Ableton with one click.

### Workflow
```
[Analyze Song] → [Show Issues] → [Generate Fixes] → [Preview] → [Apply to Ableton]
```

### Implementation Plan

#### Phase 2.1: Fix Generator Module
Create `src/fix_generator.py` that converts analysis issues to actionable fixes:

```python
class FixGenerator:
    def generate_fixes(self, analysis_result, session_state) -> List[Fix]:
        """
        Maps analysis issues to Ableton parameter changes.

        Example mappings:
        - "Bass too loud" → Track volume reduction
        - "Muddy low-mids" → EQ cut on offending tracks
        - "Over-compressed" → Reduce limiter threshold on master
        - "Narrow stereo" → Increase Utility width on pads
        """
```

**Key mappings to implement:**
| Analysis Issue | Ableton Fix |
|----------------|-------------|
| Track too loud/quiet | Adjust track volume |
| Frequency buildup | Add/adjust EQ (if present) |
| Over-compression | Adjust compressor/limiter threshold |
| Narrow stereo | Adjust Utility width |
| Phase issues | Flag for manual review |
| Clipping | Reduce track/master gain |

#### Phase 2.2: CLI Interface
Create `apply_fixes.py` command:

```bash
# Analyze and show fixes
python apply_fixes.py --song mysong

# Output:
# Found 5 issues, generated 3 applicable fixes:
#
# [1] CRITICAL: Master clipping
#     Fix: Reduce master volume by 2dB
#     Affects: Master track
#
# [2] WARNING: Bass competing with kick (80-120Hz)
#     Fix: Cut bass EQ at 100Hz by 3dB
#     Affects: Track "Bass" → EQ Eight
#
# [3] SUGGESTION: Pad track too narrow
#     Fix: Increase Utility width to 130%
#     Affects: Track "Pads" → Utility
#
# Apply fixes? [a]ll / [1,2,3] select / [n]one:
```

#### Phase 2.3: Web Dashboard (Future)
- Flask/FastAPI backend
- Real-time session state display
- Visual fix preview
- One-click apply buttons
- Before/after comparison

### Files to Create
- `src/fix_generator.py` - Issue → Fix mapping logic
- `src/fix_mappings.py` - Database of fix templates
- `apply_fixes.py` - CLI interface
- `src/web/` - Future web dashboard

---

## Feature 3: Synth Extraction Workflow

### Goal
Document and partially automate the workflow for extracting synth sounds from reference tracks and recreating them.

### Workflow Steps

```
┌─────────────────────────────────────────────────────────────────┐
│                    SYNTH EXTRACTION WORKFLOW                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. EXTRACT          2. ANALYZE           3. RECREATE           │
│  ─────────           ────────             ─────────             │
│  LALAL.AI            Your Analyzers       Serum/Wavetable       │
│  - Synth stem        - Spectral analysis  - Oscillator setup    │
│  - Isolate element   - Envelope shape     - Filter settings     │
│  - Clean up          - Filter character   - Modulation          │
│                      - Stereo width       - Effects chain       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation Plan

#### Phase 3.1: Synth Analysis Module
Create `src/synth_analyzer.py`:

```python
class SynthAnalyzer:
    def analyze_synth_sound(self, audio_path) -> SynthCharacteristics:
        """
        Analyzes an extracted synth sound and returns:
        - Waveform type (saw, square, triangle, complex)
        - Harmonic content (fundamental, overtones)
        - Filter characteristics (cutoff, resonance, type)
        - Envelope shape (ADSR estimates)
        - Modulation characteristics (LFO rate, depth)
        - Stereo width and processing
        """
```

**Output format:**
```yaml
synth_analysis:
  waveform:
    primary: sawtooth
    unison_voices: 7-9 (estimated from chorus depth)
    detune_amount: ~20 cents

  filter:
    type: lowpass
    cutoff_hz: 2400
    resonance: moderate
    envelope_amount: 60%
    envelope_decay_ms: 150

  amplitude:
    attack_ms: 5
    decay_ms: 180
    sustain: 0.65
    release_ms: 250

  stereo:
    width: 85%
    correlation: 0.45

  recreation_guide:
    synth: "Serum or Wavetable"
    oscillators:
      - "OSC1: Saw, 7 unison voices, 20% detune"
      - "OSC2: Saw, +7 semitones, 5 unison"
    filter: "LP 24dB, cutoff 2.4kHz, env mod 60%"
    amp_env: "A:5ms D:180ms S:65% R:250ms"
```

#### Phase 3.2: Integration with External Tools
Document integration points:

| Tool | Purpose | Integration |
|------|---------|-------------|
| **LALAL.AI** | Synth stem extraction | Manual (API costs $$$) |
| **UVR5** | Free stem separation | Can automate via CLI |
| **iZotope RX** | Spectral cleanup | Manual |
| **Your Analyzer** | Characterization | Automated |

#### Phase 3.3: Recreation Guide Generator
Create templates for common trance synths:

```
/docs/ai/synth-recipes/
  ├── supersaw-lead.md
  ├── trance-pluck.md
  ├── evolving-pad.md
  ├── acid-bass.md
  └── template.md
```

### Files to Create
- `src/synth_analyzer.py` - Synth sound analysis
- `docs/human/SynthExtractionGuide.md` - Step-by-step workflow
- `docs/ai/synth-recipes/` - Recreation templates

---

## Feature 4: ML Trance Analysis Model

### Goal
Train a model on your reference library to learn what makes professional trance tracks sound polished, then use it to identify the **delta** (difference) between your tracks and professional quality.

### Key Insight
> The ML model shouldn't generate music - it should generate **rules/recommendations** like "bass too wide below 100Hz" or "lead competing with vocal at 2-4kHz".

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ML PRODUCTION GUIDE SYSTEM                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   TRAINING PHASE                    INFERENCE PHASE              │
│   ──────────────                    ───────────────              │
│                                                                  │
│   Reference Tracks                  Your Track                   │
│        ↓                                 ↓                       │
│   Feature Extraction                Feature Extraction           │
│        ↓                                 ↓                       │
│   "Good" Feature DB    ──────→     Compare & Score              │
│                                          ↓                       │
│                                    Delta Analysis                │
│                                          ↓                       │
│                                    Recommendations               │
│                                          ↓                       │
│                                    Actionable Fixes              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation Plan

#### Phase 4.1: Feature Engineering
Define the feature vector for trance tracks:

```python
class TranceFeatureExtractor:
    """
    Extracts production-relevant features from audio.
    Uses existing analyzers + new trance-specific features.
    """

    def extract_features(self, audio_path) -> TranceFeatures:
        # Frequency balance (per section)
        # - Sub bass energy ratio (20-60Hz)
        # - Kick/bass separation score
        # - Low-mid mud ratio (200-500Hz)
        # - Presence (2-5kHz)
        # - Air (10-20kHz)

        # Dynamics
        # - Crest factor (overall + per section)
        # - Sidechain depth and timing
        # - Transient punch score

        # Stereo
        # - Width by frequency band
        # - Bass mono-ness score
        # - Phase correlation

        # Arrangement (trance-specific)
        # - Build energy curve
        # - Drop impact score
        # - Breakdown contrast

        # Mix clarity
        # - Spectral clarity score
        # - Masking estimation
        # - Frequency slot occupancy
```

#### Phase 4.2: Reference Library Analysis
Batch process your reference tracks:

```bash
# Scan reference library
python train_model.py --scan-references "D:/Music/References/Trance/"

# Output:
# Found 47 reference tracks
# Analyzing... [████████████████████] 100%
#
# Reference Profile Summary:
# - Average loudness: -8.2 LUFS (range: -10 to -6)
# - Typical crest factor: 8-12 dB
# - Bass width: 95% mono below 150Hz
# - Sidechain depth: 4-8 dB on bass
# - Drop impact: avg 6dB energy increase
#
# Saved to: models/trance_reference_profile.json
```

#### Phase 4.3: Comparison Model
Two approaches (can do both):

**Approach A: Statistical Comparison**
- No ML training needed
- Compare your track's features to reference statistics
- Score each dimension (within range = good, outside = issue)
- Fast, interpretable, no training data needed

**Approach B: Learned Model**
- Train classifier: "professional" vs "amateur"
- Use your tracks + reference tracks as training data
- Model learns subtle feature interactions
- Requires labeled data (your tracks = amateur, refs = professional)

**Recommended: Start with Approach A, add B later**

#### Phase 4.4: Delta Analyzer
```python
class ProductionDeltaAnalyzer:
    def analyze_delta(self, your_track, reference_profile) -> ProductionDelta:
        """
        Compares your track against reference profile.
        Returns specific, actionable deltas.
        """

        # Example output:
        return ProductionDelta(
            overall_score=72,  # 0-100

            issues=[
                DeltaIssue(
                    category="low_end",
                    severity="warning",
                    message="Bass 4dB quieter than reference average",
                    recommendation="Boost bass or check high-pass filter settings",
                    reference_value=-8.2,
                    your_value=-12.1,
                    unit="dB RMS"
                ),
                DeltaIssue(
                    category="stereo",
                    severity="critical",
                    message="Sub bass too wide (45% vs 95% mono)",
                    recommendation="Apply Utility with Bass Mono below 150Hz",
                    ableton_fix=Fix(...)  # Auto-applicable!
                ),
            ]
        )
```

### Training Data Requirements

| Data | Source | Quantity |
|------|--------|----------|
| Reference tracks | Your trance library | 30-100+ tracks |
| Your tracks | Your productions | 10-50+ tracks |
| Feature labels | Auto-extracted | N/A |
| Quality labels | Manual or inferred | Optional for Approach B |

### Files to Create
```
src/ml/
├── feature_extractor.py      # TranceFeatureExtractor
├── reference_profiler.py     # Build reference statistics
├── delta_analyzer.py         # Compare your tracks
├── production_scorer.py      # Overall scoring
└── models/
    └── trance_reference_profile.json
```

---

## Feature 5: Real-Time Production Guide (Future)

### Goal
While producing in Ableton, receive real-time feedback comparing your current mix to reference standards.

### Prerequisites
- Feature 2 (Apply Fixes) complete
- Feature 4 (ML Model) complete
- AbletonOSC listener for change events

### Concept
```
┌─────────────────────────────────────────────────────────────────┐
│                     REAL-TIME FEEDBACK LOOP                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Ableton Session                 Analysis Engine                │
│        │                               │                         │
│        │ ──── OSC: State Changed ────→ │                        │
│        │                               │                         │
│        │                          [Analyze Current Mix]          │
│        │                               │                         │
│        │                          [Compare to References]        │
│        │                               │                         │
│        │ ←─── UI: Show Suggestions ─── │                        │
│        │                               │                         │
│        │ ←─── Optional: Auto-Fix ───── │                        │
│        │                               │                         │
└─────────────────────────────────────────────────────────────────┘
```

### Interaction Modes

1. **Passive Dashboard**
   - Small floating window showing real-time scores
   - Color-coded: green (good), yellow (warning), red (issue)
   - Updates as you make changes

2. **On-Demand Analysis**
   - "Analyze Now" button
   - Full report with recommendations
   - Explicit "Apply" action

3. **Auto-Assist Mode**
   - AI suggests fixes in real-time
   - User approves before applying
   - Learning from user preferences

### Technical Challenges
- Real-time audio analysis (need efficient feature extraction)
- State change detection (debounce rapid changes)
- Non-intrusive UI (shouldn't interrupt creative flow)
- Latency budget (<100ms for "real-time" feel)

---

## Implementation Phases

### Phase 1: Foundation (DONE)
- [x] AbletonOSC integration
- [x] Session state reading
- [x] Parameter writing

### Phase 2: Fix Application (NEXT)
- [ ] Fix generator module
- [ ] Issue → Fix mapping database
- [ ] CLI interface
- [ ] Basic testing with real session

### Phase 3: Synth Workflow
- [ ] Synth analyzer module
- [ ] Documentation guide
- [ ] Recreation templates

### Phase 4: ML Model
- [ ] Feature extractor
- [ ] Reference library analyzer
- [ ] Statistical comparison (Approach A)
- [ ] Delta analyzer with auto-fix generation

### Phase 5: Real-Time Guide
- [ ] OSC listener for state changes
- [ ] Incremental analysis engine
- [ ] Floating dashboard UI
- [ ] User preference learning

---

## Quick Wins (Can Do Now)

1. **Fix Generator Prototype** - Map 5 common issues to Ableton fixes
2. **CLI Apply Tool** - Basic "analyze → show fixes → apply" flow
3. **Reference Batch Analyzer** - Process your trance library, build stats
4. **Synth Analysis** - Characterize a single extracted synth sound

---

## Resources & References

### Research Documents
- `C:\Users\badmin\Desktop\Audio Research\SynthExtractionResearch.md`
- `C:\Users\badmin\Desktop\Audio Research\AbletonOSCResearch.md`

### Tools
- **AbletonOSC**: https://github.com/ideoforms/AbletonOSC
- **PyLive**: `pip install pylive`
- **LALAL.AI**: Synth stem extraction (paid)
- **UVR5**: Free stem separation

### Existing Analyzers (in this project)
- `src/audio_analyzer.py` - Core analysis
- `src/analyzers/harmonic_analyzer.py` - Key detection
- `src/analyzers/clarity_analyzer.py` - Spectral clarity
- `src/analyzers/spatial_analyzer.py` - Stereo analysis
- `src/reference_comparator.py` - Reference comparison
- `src/ableton_bridge.py` - Ableton integration (NEW)

---

## Notes

- Start with statistical comparison before ML - simpler, faster, more interpretable
- The "Apply Fixes" feature is the highest-impact next step
- Synth extraction is mostly a documentation/workflow task
- Real-time guide requires all other pieces to be solid first
