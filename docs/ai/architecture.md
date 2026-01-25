# Architecture Documentation

Context documentation for AI assistance with this project.

## Related Projects

| Project | Location | Purpose |
|---------|----------|---------|
| **AbletonManagement** | `C:\claude-workspace\AbletonMangement` | Sister project for Ableton project management (separate from analysis) |

This project (AbletonAIAnalysis) focuses on **analysis and diagnostics**. The sister project handles broader Ableton project management tasks. They are designed to be independent but complementary.

---

## Project Overview

Ableton AI Analysis is a comprehensive music production analysis tool designed for **trance music producers** using Ableton Live. The system:

1. Parses Ableton Live Set (.als) files
2. Analyzes audio files for mixing issues with timestamped detection
3. Detects frequency clashes between stems
4. Compares mixes against professional reference tracks
5. Separates audio into stems using AI (Spleeter)
6. Provides AI-powered mastering (experimental)
7. Generates comprehensive reports (HTML/JSON/text)
8. Integrates with LLM-powered recommendation specialists

---

## System Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                           INPUT LAYER                                   │
├──────────────────┬────────────────────┬────────────────────────────────┤
│ /inputs/<song>/  │   Manual CLI Args  │     Reference Library          │
│ ├── mix/v1/      │   --audio, --stems │     (stored references)        │
│ ├── stems/       │   --als, --ref     │                                │
│ ├── references/  │                    │                                │
│ └── project.als  │                    │                                │
└──────────────────┴────────────────────┴────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      CONFIGURATION (config.yaml)                        │
│  Stage toggles, thresholds, frequency bands, platform targets          │
└────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       ANALYSIS PIPELINE                                 │
├──────────────────┬────────────────────┬────────────────────────────────┤
│ audio_analyzer   │   stem_analyzer    │      als_parser                │
│ ├─ Clipping      │   ├─ Freq Clashes  │      ├─ Project Info           │
│ ├─ Dynamics      │   ├─ Balance       │      ├─ MIDI Analysis          │
│ ├─ Frequency     │   ├─ Masking       │      ├─ Track Data             │
│ ├─ Stereo/Phase  │   └─ Recommendations│     └─ Plugin List            │
│ ├─ Loudness      │                    │                                │
│ ├─ Transients    │                    │                                │
│ └─ Sections      │                    │                                │
├──────────────────┴────────────────────┴────────────────────────────────┤
│                   reference_comparator + stem_separator                 │
│                   (Stem-by-stem comparison with AI separation)          │
└────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         OUTPUT LAYER                                    │
├──────────────────┬────────────────────┬────────────────────────────────┤
│    reporter.py   │    JSON Export     │    LLM Recommendation          │
│    ├─ HTML       │    (Full metrics)  │    Prompts (17 specialists)    │
│    ├─ Text       │                    │    ├─ LowEnd.md                │
│    └─ Charts     │                    │    ├─ Dynamics.md              │
│                  │                    │    ├─ Sections.md              │
│                  │                    │    └─ etc...                   │
└──────────────────┴────────────────────┴────────────────────────────────┘
```

---

## Module Architecture

```
projects/music-analyzer/
├── analyze.py              # CLI entry point (Click-based)
├── config.yaml             # Configuration file (thresholds, toggles)
├── requirements.txt        # Python dependencies
└── src/
    ├── __init__.py         # Package init, exports main classes
    ├── config.py           # Configuration loader
    ├── audio_analyzer.py   # Single audio file analysis + sections
    ├── stem_analyzer.py    # Multi-stem clash detection
    ├── als_parser.py       # Ableton .als file parsing (basic)
    ├── mastering.py        # Matchering integration (experimental)
    ├── reporter.py         # Report generation (HTML/text/JSON)
    ├── stem_separator.py   # Spleeter-based stem separation
    ├── reference_storage.py    # Reference track library
    ├── reference_comparator.py # Mix vs reference comparison
    │
    │   # ALS Doctor - Project Health Analysis (no audio export required)
    ├── als_doctor.py           # Unified CLI for ALS analysis
    ├── device_chain_analyzer.py # Deep .als device chain extraction
    ├── effect_chain_doctor.py  # Rules engine for mixing issues
    ├── project_differ.py       # Compare two .als versions
    └── batch_scanner.py        # Scan & rank multiple projects

als-doctor.bat              # Windows batch wrapper (in project root)
```

---

## Standard Input Structure

Songs ready for analysis live in `/inputs/<songname>/`:

```
/inputs/
  └── <songname>/
      ├── info.json                 # Optional: Song metadata
      ├── project.als               # Optional: Ableton project file
      ├── mix/                      # Full mix exports (version subfolders)
      │   ├── v1/
      │   │   └── mix.flac          # Version 1 mixdown
      │   ├── v2/
      │   │   └── mix.flac          # Version 2 (current)
      │   └── ...
      ├── stems/                    # Individual track exports
      │   ├── kick.wav
      │   ├── bass.wav
      │   └── ...
      ├── midi/                     # Optional: MIDI files
      │   └── *.mid
      └── references/               # Optional: Reference tracks
          └── reference.wav
```

---

## Configuration System

**File:** `config.yaml` + `src/config.py`

### Stage Toggles (Feature Flags)

```yaml
stages:
  audio_analysis: true          # Main mix analysis
  section_analysis: true        # Timeline-based issue detection
  clipping_detection: true      # Find clipping with timestamps
  stem_separation: false        # AI separation (slow, requires spleeter)
  stem_analysis: true           # Analyze provided stems
  reference_comparison: true    # Compare against references
  als_parsing: true             # Parse Ableton projects
  midi_humanization: false      # MIDI natural/robotic scoring
  midi_quantization: false      # Off-grid note detection
  midi_chord_detection: false   # Chord identification
  ai_mastering: false           # Auto-master (experimental)
```

### Configuration Sections

| Section | Purpose | Key Values |
|---------|---------|------------|
| `stages` | Enable/disable analysis stages | Boolean flags |
| `report` | Report generation options | format, visualizations |
| `clipping` | Clipping detection | threshold (0.99), group_window, severity thresholds |
| `dynamics` | Crest factor interpretation | very_dynamic (18), good (12), compressed (8) |
| `frequency` | Band definitions & thresholds | sub_bass, bass, low_mid, mid, high_mid, high |
| `stereo` | Width/phase thresholds | mono (0.95), narrow (0.7), good (0.3), wide (0.0) |
| `loudness` | LUFS targets | spotify (-14), apple_music (-16), youtube (-14) |
| `transients` | Attack quality thresholds | punchy (0.7), average (0.4) |
| `sections` | Section detection | min_length, detection_weights, drop/breakdown thresholds |
| `stems` | Stem analysis | clash thresholds, balance thresholds, masking detection |
| `reference` | Reference comparison | loudness_threshold, frequency_threshold |
| `midi` | MIDI analysis | quantization, humanization, chord detection |
| `mastering` | AI mastering | peak limiting, K-weighting |
| `defaults` | Fallback values | sample_rate, tempo, duration |

### Configuration Loading

```python
from config import load_config, cfg

# Load with default or custom path
config = load_config()  # Uses config.yaml
config = load_config("/path/to/custom.yaml")

# Quick access
threshold = cfg('clipping', 'threshold')  # Returns 0.99
enabled = config.stage_enabled('section_analysis')  # Returns True
```

### Environment Variable Overrides

Format: `ANALYZER_<SECTION>_<KEY>=value`

```bash
ANALYZER_CLIPPING_THRESHOLD=0.98
ANALYZER_DYNAMICS_TARGET_CREST_FACTOR=10
```

---

## CLI Options

```bash
# Standard analysis from /inputs/<song>/
python analyze.py --song MySong
python analyze.py --song MySong --version v2

# Manual paths
python analyze.py --audio mix.wav
python analyze.py --audio mix.wav --stems ./stems/
python analyze.py --als project.als --stems ./stems/ --audio mix.wav

# Reference comparison
python analyze.py --audio mix.wav --compare-ref reference.wav
python analyze.py --song MySong --reference-id stored_ref_001

# Reference library management
python analyze.py --add-reference pro_track.wav --genre trance --tags "uplifting,anthem"
python analyze.py --list-references

# AI mastering (experimental)
python analyze.py --audio mix.wav --reference ref.wav --master

# AI stem separation
python analyze.py --separate mix.wav

# Configuration
python analyze.py --song MySong --config custom_config.yaml
python analyze.py --song MySong --no-sections --no-stems --no-midi

# Output options
python analyze.py --song MySong --output ./my_reports --format json
python analyze.py --song MySong -v  # Verbose
```

---

## JSON Output Structure

The analysis produces a comprehensive JSON file with all metrics:

```json
{
  "metadata": {
    "generated_at": "2026-01-14T12:00:00",
    "analyzer_version": "1.0.0",
    "project_name": "MySong",
    "version": "v1"
  },

  "als_project": {
    "tempo": 140.0,
    "time_signature_numerator": 4,
    "time_signature_denominator": 4,
    "tracks": [...],
    "midi_analysis": {...},
    "plugin_list": [...]
  },

  "audio_analysis": {
    "duration_seconds": 360.0,
    "sample_rate": 44100,
    "channels": 2,
    "detected_tempo": 140.0,

    "clipping": {
      "has_clipping": false,
      "clip_count": 0,
      "clip_positions": [],
      "max_peak": 0.95,
      "severity": "none"
    },

    "dynamics": {
      "peak_db": -0.5,
      "rms_db": -12.0,
      "dynamic_range_db": 11.5,
      "crest_factor_db": 11.5,
      "is_over_compressed": false,
      "crest_interpretation": "good",
      "recommended_action": "Good dynamic balance"
    },

    "frequency": {
      "spectral_centroid_hz": 2500.0,
      "bass_energy": 25.0,
      "low_mid_energy": 12.0,
      "mid_energy": 35.0,
      "high_mid_energy": 18.0,
      "high_energy": 10.0,
      "balance_issues": [],
      "problem_frequencies": []
    },

    "stereo": {
      "is_stereo": true,
      "correlation": 0.65,
      "width_estimate": 35.0,
      "is_mono_compatible": true,
      "width_category": "good",
      "phase_safe": true
    },

    "loudness": {
      "integrated_lufs": -10.5,
      "short_term_max_lufs": -8.0,
      "momentary_max_lufs": -6.0,
      "loudness_range_lu": 8.0,
      "true_peak_db": -0.3,
      "spotify_diff_db": 3.5,
      "apple_music_diff_db": 5.5,
      "target_platform": "spotify"
    },

    "transients": {
      "transient_count": 850,
      "transients_per_second": 2.36,
      "avg_transient_strength": 0.72,
      "attack_quality": "punchy"
    },

    "overall_issues": [...],
    "recommendations": [...]
  },

  "section_analysis": {
    "sections": [
      {
        "section_type": "intro",
        "start_time": 0.0,
        "end_time": 45.0,
        "avg_rms_db": -18.0,
        "peak_db": -12.0,
        "transient_density": 0.8,
        "spectral_centroid_hz": 1200.0,
        "issues": [],
        "severity_summary": "clean"
      },
      {
        "section_type": "drop",
        "start_time": 75.0,
        "end_time": 150.0,
        "avg_rms_db": -10.0,
        "peak_db": -1.0,
        "transient_density": 3.2,
        "spectral_centroid_hz": 3500.0,
        "issues": [],
        "severity_summary": "clean"
      }
    ],
    "all_issues": [],
    "clipping_timestamps": [],
    "section_summary": {"intro": 1, "buildup": 2, "drop": 2, "breakdown": 1, "outro": 1},
    "worst_section": null
  },

  "stem_analysis": {
    "stems": [...],
    "clashes": [
      {
        "stem1": "kick",
        "stem2": "bass",
        "frequency_range": [60, 120],
        "overlap_amount": 0.45,
        "severity": "moderate",
        "recommendation": "Sidechain compress bass to kick"
      }
    ],
    "balance_issues": [],
    "masking_issues": [],
    "recommendations": [...]
  },

  "comparison_result": {
    "user_file": "mix.wav",
    "reference_file": "reference.wav",
    "stem_comparisons": {...},
    "overall_balance_score": 85,
    "priority_recommendations": [...]
  },

  "summary": {
    "critical_issues": [],
    "warnings": [],
    "info": [],
    "recommendations": [...]
  }
}
```

---

## LLM Recommendation Module

**Location:** `/docs/ai/RecommendationGuide/`

### Usage

After running analysis, use specialist prompts with Claude:

```bash
claude --add-file "docs/ai/RecommendationGuide/prompts/LowEnd.md" \
       --add-file "reports/MySong/MySong_v1_analysis_2026-01-14.json"
```

Then ask: "Analyze my mix"

### Available Specialists (17 total)

#### Core Mix Analysis (6 detailed prompts)
| Specialist | File | Focus |
|------------|------|-------|
| Low End | `LowEnd.md` | Kick/bass relationship, sub-bass, sidechain, mono compatibility |
| Frequency Balance | `FrequencyBalance.md` | EQ decisions, muddy frequencies, harshness, frequency clashes |
| Dynamics | `Dynamics.md` | Compression, transients, punch, crest factor |
| Stereo & Phase | `StereoPhase.md` | Width, mono compatibility, phase issues, panning |
| Loudness | `Loudness.md` | LUFS targets, true peak, streaming optimization, limiting |
| Sections | `Sections.md` | Drop impact, breakdown energy, transitions, arrangement |

#### Trance-Specific (1 prompt)
| Specialist | File | Focus |
|------------|------|-------|
| Trance Arrangement | `TranceArrangement.md` | Section contrast, buildup mechanics, drop impact, 8-bar rule |

#### Reference Comparison (1 prompt)
| Specialist | File | Focus |
|------------|------|-------|
| Stem Reference | `StemReference.md` | Stem-by-stem comparison with reference tracks |

#### Advanced Analysis (9 prompts)
| Specialist | File | Focus |
|------------|------|-------|
| Gain Staging | `GainStagingAudit.md` | Level management, headroom, gain structure |
| Stereo Field | `StereoFieldAudit.md` | Detailed stereo image analysis |
| Frequency Collision | `FrequencyCollisionDetection.md` | Element-by-element frequency clashes |
| Dynamics Humanization | `DynamicsHumanizationReport.md` | Natural dynamics, velocity variation |
| Section Contrast | `SectionContrastAnalysis.md` | Energy flow between sections |
| Density & Busyness | `DensityBusynessReport.md` | Arrangement density, element count |
| Chord & Harmony | `ChordHarmonyAnalysis.md` | Chord progressions, harmonic analysis |
| Device Chain | `DeviceChainAnalysis.md` | Plugin/effect chain optimization |
| Priority Summary | `PriorityProblemSummary.md` | Aggregated issues ranked by priority |

### Recommended Analysis Order

1. **Low End** - Foundation must be solid first
2. **Frequency Balance** - Fix major EQ issues
3. **Dynamics** - Get punch and energy right
4. **Stereo & Phase** - Ensure mono compatibility
5. **Sections** - Check arrangement/energy flow
6. **Loudness** - Final loudness optimization

---

## Complete Analysis Capabilities

### 1. AudioAnalyzer (audio_analyzer.py)

Comprehensive single audio file analysis.

#### Clipping Detection
| Metric | Description |
|--------|-------------|
| Clipping count | Number of samples exceeding threshold |
| Clip positions | Timestamps where clipping occurs |
| Maximum peak | Highest sample value |
| Severity | none / minor / moderate / severe |

**Threshold**: 0.99 normalized amplitude (configurable)

#### Dynamic Range Analysis
| Metric | Description |
|--------|-------------|
| Peak dB | Maximum level in dBFS |
| RMS dB | Average loudness in dBFS |
| Dynamic range | Peak minus RMS |
| Crest factor | Interpretation of dynamics |

**Crest Factor Interpretation:**
- `very_dynamic`: >18 dB (classical, jazz)
- `good`: 12-18 dB (balanced)
- `compressed`: 8-12 dB (modern pop)
- `over_compressed`: <8 dB (problem!)

#### Frequency Balance (6 bands)
| Band | Frequency Range | Issues Detected |
|------|-----------------|-----------------|
| Sub-bass | 20-60 Hz | Rumble, phase issues |
| Bass | 60-250 Hz | Muddiness (>45% = muddy, <15% = thin) |
| Low-mid | 250-500 Hz | Boxiness, buildup (>25% = muddy) |
| Mid | 500-2000 Hz | Vocal clarity |
| High-mid | 2000-6000 Hz | Presence, harshness |
| High | 6000-20000 Hz | Air (<5% = dull, >25% = harsh) |

**Additional Metrics:**
- Spectral centroid (brightness in Hz)
- Spectral rolloff frequency
- Problem frequency identification

#### Stereo Analysis
| Metric | Description |
|--------|-------------|
| Correlation | -1 (out of phase) to +1 (mono) |
| Stereo width | 0-100% estimate |
| Mono compatibility | Safe if correlation > 0.3 |
| Phase safety | Safe if correlation > 0 |

**Width Categories:**
- `mono`: >0.95 correlation
- `narrow`: 0.7-0.95
- `good`: 0.3-0.7
- `wide`: 0.0-0.3
- `out_of_phase`: <0 (CRITICAL!)

#### Loudness Measurement (ITU-R BS.1770-4)
| Metric | Description |
|--------|-------------|
| Integrated LUFS | Overall loudness |
| Short-term max | Loudest 3-second window |
| Momentary max | Loudest 400ms window |
| Loudness range | Dynamic variation (LU) |
| True peak dB | Inter-sample peaks |

**Streaming Platform Targets:**
| Platform | Target LUFS |
|----------|-------------|
| Spotify | -14 |
| Apple Music | -16 |
| YouTube | -14 |
| Tidal | -14 |
| Amazon Music | -14 |
| SoundCloud | -14 |

#### Transient Analysis
| Metric | Description |
|--------|-------------|
| Transient count | Number of transients detected |
| Density | Transients per second |
| Average strength | 0-1 normalized |
| Peak strength | Strongest transient |
| Attack quality | punchy / soft / average |

#### Section Analysis
- Automatic section detection (intro, buildup, drop, breakdown, outro)
- Per-section metrics (RMS, peak, transient density, spectral centroid)
- Timestamped issue detection
- Timeline data for visualization

---

### 2. StemAnalyzer (stem_analyzer.py)

Multi-stem mixing analysis for frequency clashes and balance.

#### Per-Stem Metrics
| Metric | Description |
|--------|-------------|
| Peak dB | Maximum level |
| RMS dB | Average loudness |
| Dominant frequencies | Top 5 frequency peaks |
| Frequency profile | 7-band energy distribution |
| Mono/stereo | Channel configuration |
| Panning estimate | -1 (L) to +1 (R) |

#### Frequency Clash Detection
| Severity | Overlap Threshold | Action |
|----------|-------------------|--------|
| Minor | 10-30% | Monitor |
| Moderate | 30-50% | EQ recommended |
| Severe | >50% | EQ required |

**Output per clash:**
- Stem 1 and Stem 2 names
- Frequency range of overlap
- Overlap percentage
- Specific EQ recommendation

#### Balance Issues Detected
- Stems >6 dB louder than average
- Stems >12 dB quieter than average
- Masking (louder stem obscuring quieter, >10 dB difference)
- Panning distribution (warning if >70% center)

#### Instrument Frequency Ranges (Built-in)
| Instrument | Frequency Range |
|------------|-----------------|
| Kick | 30-150 Hz |
| Bass | 40-300 Hz |
| Snare | 150-5000 Hz |
| Hihat | 3000-16000 Hz |
| Vocal | 100-8000 Hz |
| Guitar | 80-5000 Hz |
| Piano | 30-8000 Hz |
| Synth | 100-10000 Hz |
| Pad | 200-8000 Hz |

---

### 3. ALSParser (als_parser.py)

Ableton Live Set file extraction.

#### Project-Level Data
| Data | Description |
|------|-------------|
| Ableton version | Software version |
| Tempo | BPM (with tempo automation detection) |
| Time signature | Numerator/denominator |
| Sample rate | Hz |
| Duration | Beats and seconds |
| MIDI note count | Total notes |
| Audio clip count | Total audio clips |
| Plugin list | VST, AU, Max for Live |

#### Track-Level Data
| Data | Description |
|------|-------------|
| Track type | MIDI, audio, return, master, group |
| Name, color | Display properties |
| Mute/solo state | Current status |
| Volume, pan | Mixer settings |
| Device chain | Effects and instruments |

#### MIDI Analysis
- Humanization scoring (robotic / slightly_humanized / natural)
- Velocity statistics (mean, std, range)
- Quantization error detection (off-grid notes)
- Chord detection
- Swing analysis

#### Audio Data
- File path references
- Warp modes (Beats, Tones, Texture, Re-Pitch, Complex, Complex Pro)
- Clip arrangement positions

#### Project Structure
- Locators/markers
- Scenes
- Tempo automation points

---

### 4. ReferenceComparator (reference_comparator.py)

Professional reference track comparison with stem separation.

#### Stem-by-Stem Comparison (vocals, drums, bass, other)
| Metric | Threshold | Description |
|--------|-----------|-------------|
| RMS difference | ±2 dB | Level match |
| LUFS difference | ±2 dB | Loudness match |
| Spectral centroid | ±200 Hz | Brightness match |
| Stereo width | ±15% | Width match |
| Dynamic range | ±3 dB | Compression match |

#### Per-Band Frequency Comparison
| Band | Range | Issue Threshold |
|------|-------|-----------------|
| Bass | 20-250 Hz | >8% difference |
| Low-mid | 250-500 Hz | >8% difference |
| Mid | 500-2000 Hz | >8% difference |
| High-mid | 2000-6000 Hz | >8% difference |
| High | 6000-20000 Hz | >8% difference |

#### Output
- Overall balance score (0-100)
- Severity per stem (good / minor / moderate / significant)
- Priority-ranked recommendations
- Specific dB adjustments per stem
- EQ recommendations per band

---

### 5. StemSeparator (stem_separator.py)

AI-powered audio source separation.

#### Separation Model: Spleeter 4-stems
| Stem | Content |
|------|---------|
| Vocals | Lead and backing vocals |
| Drums | Percussion, drums |
| Bass | Bass instruments |
| Other | Everything else |

#### Features
- **MD5-based caching** - Skip re-processing identical files
- **Format support**: WAV, MP3, FLAC, AIFF, OGG, M4A, AAC
- **Progress callbacks** - Real-time status updates
- **Cache management** - Clear by file, all, or age

#### Per-Stem Output
- Duration, sample rate
- Peak dB, RMS dB

---

### 6. MasteringEngine (mastering.py)

AI-powered mastering with reference matching (experimental).

#### Primary Method: Matchering
- Loudness matching (LUFS)
- EQ matching (spectral balance)
- Dynamics matching (compression)
- True peak limiting

#### Fallback Method
- RMS-based loudness matching
- Simple limiting

#### Output Metrics
| Metric | Description |
|--------|-------------|
| Before LUFS | Original loudness |
| After LUFS | Mastered loudness |
| Loudness increase | dB gained |
| True peak | Final peak level |
| Match quality | Similarity to reference |

---

### 7. ReferenceStorage (reference_storage.py)

Reference track library management.

#### Stored Per Reference
- Track ID (hash-based)
- File name, path
- Genre, custom tags
- Tempo (BPM)
- Duration
- Full stem analytics

#### Features
- Add references with metadata
- Query by ID or genre
- Library statistics
- Pre-analyzed for fast comparisons

---

## Complete Issue Detection Matrix

| Issue | Module | Severity Levels | Threshold |
|-------|--------|-----------------|-----------|
| Clipping | audio_analyzer | none/minor/moderate/severe | 0.99 |
| Over-compression | audio_analyzer | minor/moderate/severe | <6 dB crest |
| Phase issues | audio_analyzer | CRITICAL | correlation < 0 |
| Narrow stereo | audio_analyzer | warning | correlation > 0.95 |
| Frequency imbalance | audio_analyzer | warning/info | band-specific |
| Loudness | audio_analyzer | critical/warning/info | ±2 dB from target |
| True peak | audio_analyzer | warning | >-1.0 dB |
| Low-end buildup | section_analysis | minor/moderate/severe | >25% in 200-500Hz |
| Harsh highs | section_analysis | minor/moderate/severe | >35% in 3-8kHz |
| Weak sub | section_analysis | minor | <5% in drops |
| Frequency clash | stem_analyzer | minor/moderate/severe | >10% overlap |
| Masking | stem_analyzer | warning | >10 dB level diff |
| Volume balance | stem_analyzer | warning/info | ±6 dB variance |
| Reference mismatch | reference_comparator | good/minor/moderate/significant | metric-specific |
| Robotic MIDI | als_parser | warning | velocity std <5 |
| Off-grid notes | als_parser | minor/severe | >0.03 beats off |

---

## Recommendation Categories

The system generates actionable recommendations for:

1. **Level/Loudness** - Specific dB adjustments
2. **EQ/Frequency** - Hz ranges with cut/boost amounts (e.g., "Cut 200-400 Hz by 2 dB")
3. **Compression** - Crest factor targets, attack/release suggestions
4. **Stereo** - Width adjustment, panning changes, mono compatibility
5. **Mastering** - Platform-specific loudness targets
6. **Mixing** - Stem balance, frequency carving, sidechain settings
7. **Transients** - Attack enhancement
8. **Structure** - Section-level improvements, drop impact, transition quality

---

## Dependencies

**Core:**
- `librosa` - Audio feature extraction
- `soundfile` - High-quality audio I/O
- `numpy` - Numerical operations
- `scipy` - Signal processing
- `pyloudnorm` - ITU-R BS.1770-4 loudness
- `pyyaml` - Configuration loading

**AI/ML:**
- `spleeter` - Stem separation
- `matchering` - AI mastering (fallback available)

**CLI:**
- `click` - Command-line interface
- `colorama` - Cross-platform colors
- `tqdm` - Progress bars
- `jinja2` - HTML templating

---

## Quick Functions

Each module exports convenience functions:
```python
quick_analyze(audio_path)           # Full audio analysis
analyze_stems_quick(stem_paths)     # Stem clash detection
parse_als(als_path)                 # Ableton project parsing
quick_master(target, reference)     # AI mastering

# Configuration
from config import load_config, cfg
config = load_config()
threshold = cfg('clipping', 'threshold')
```

---

## Output Directory Structure

```
/reports/
  └── <songname>/
      ├── <songname>_v1_analysis_2026-01-14.html    # HTML report
      ├── <songname>_v1_analysis_2026-01-14.json    # Full JSON data
      ├── mix_<original_name>.flac                   # Copy of analyzed mix
      └── reference_<original_name>.wav              # Copy of reference (if used)
```

---

## Version History

- **v1.0.0** - Initial release with core analysis pipeline
- **v1.1.0** - Added configuration system (config.yaml)
- **v1.2.0** - Added LLM recommendation module (17 specialist prompts)
- **v1.3.0** - Added section analysis with timestamped issue detection
- **v1.4.0** - Added ALS Doctor: project health analysis without audio export

---

## ALS Doctor - Project Health Analysis

**Location:** `projects/music-analyzer/src/als_doctor.py`
**Batch file:** `als-doctor.bat` (project root)

### Overview

ALS Doctor analyzes Ableton Live Set (.als) files **without requiring audio export**. It extracts device chains, parameters, and project structure directly from the .als file (gzipped XML) to detect mixing problems and track project health over time.

### CLI Usage

```cmd
cd C:\claude-workspace\AbletonAIAnalysis

# Quick health check (instant score)
als-doctor quick "path\to\project.als"

# Full diagnosis with actionable fixes
als-doctor diagnose "path\to\project.als"

# Compare two versions (track improvement/regression)
als-doctor compare "v1.als" "v2.als"

# Batch scan and rank projects
als-doctor scan "D:\Ableton Projects" --limit 30
als-doctor scan "D:\Ableton Projects" --min-number 22  # Projects 22+
```

### Modules

#### 1. DeviceChainAnalyzer (device_chain_analyzer.py)

Extracts detailed device information from .als files.

| Data Extracted | Example |
|----------------|---------|
| Device order in chain | EQ8 -> Compressor2 -> Saturator -> Limiter |
| Device ON/OFF state | `[ON] Eq8`, `[OFF] Compressor2` |
| Device parameters | Threshold=0.04, Ratio=4:1, Attack=0.05 |
| Track volume/pan | +6.0 dB, pan -0.3 |
| VST/AU plugin names | TRITON, FabFilter Pro-Q 4 |
| Custom device names | "Kick Reducer", "De-esser" |

**Device Categories Detected:**
- INSTRUMENT (Simpler, Operator, VST synths)
- EQ (Eq8, Eq3, ChannelEq)
- COMPRESSOR (Compressor2, GlueCompressor)
- LIMITER
- SATURATOR (Saturator, Overdrive, Amp)
- REVERB, DELAY
- MODULATION (Chorus, Flanger, Phaser)
- FILTER (AutoFilter)
- UTILITY (Gain, Utility)
- VST, AU, MAX4LIVE

#### 2. EffectChainDoctor (effect_chain_doctor.py)

Rules engine that diagnoses mixing problems based on device chain analysis.

**Issue Categories:**

| Category | Example Issue |
|----------|--------------|
| CLUTTER | "36% of devices are disabled - delete them" |
| WRONG_EFFECT | "De-esser on hi-hat - remove it" |
| CHAIN_ORDER | "Limiter should be LAST in chain" |
| DUPLICATE | "3 compressors in series - too many?" |
| PARAMETERS | "Ratio at infinity:1 - use a Limiter instead" |
| GAIN_STAGING | "Track volume at +140 dB" |

**Severity Levels:**
- CRITICAL: Will definitely cause problems
- WARNING: Likely causing problems
- SUGGESTION: Could be improved
- INFO: Just FYI

**Health Score:** 0-100 (calculated from issues found)
- A (80-100): Great shape
- B (60-79): Good, some cleanup needed
- C (40-59): Needs work
- D (20-39): Significant issues
- F (0-19): Major problems

**Trance-Specific Rules:**
- De-essers flagged on drum tracks (kick, hat, snare, clap)
- Limiter should be last in chain
- EQ before compressor (subtractive EQ first)
- Multiple limiters on same track flagged
- 3+ compressors flagged as suspicious

#### 3. ProjectDiffer (project_differ.py)

Compares two versions of a project to track improvement or regression.

**Comparison Metrics:**
| Metric | Tracked |
|--------|---------|
| Health score delta | +15 (improved) or -20 (regressed) |
| Issue count delta | +5 more issues or -3 fewer |
| Device count | 40 -> 115 devices |
| Disabled device count | 5 -> 35 clutter |
| Devices added/removed | List of changes |
| Tracks added/removed | List of changes |

**Output:**
- `[IMPROVEMENT]` / `[REGRESSION]` / `[NO CHANGE]` verdict
- What got better (reasons)
- What got worse (reasons)
- Specific device and track changes

#### 4. BatchScanner (batch_scanner.py)

Scans multiple projects and ranks them by workability.

**Features:**
- Recursive directory scanning
- Filter by project number (`--min-number 22`)
- Limit scan size (`--limit 50`)
- Grade distribution summary
- Best songs to work on
- Songs that need cleanup
- Songs to consider abandoning

**Output Example:**
```
GRADE DISTRIBUTION:
  A:   3 ###
  B:   5 #####
  C:   8 ########
  D:   4 ####
  F:   2 ##

BEST SONGS TO WORK ON (Grade A/B):
  [A] 22_2.als - 100/100, 140 BPM
  [A] 35_3.als - 92/100, 138 BPM
  [B] 41_1.als - 78/100, 142 BPM
```

### Workflow Integration

**See:** [ALS-First Evaluation Workflow](ALSFirstEvaluationWorkflow.md) for complete workflow documentation.

The ALS-First workflow makes audio export and LLM expert analysis optional:
- **Phase 1:** ALS Quick Check (required, 30 sec)
- **Phase 2:** Full ALS Diagnosis (optional, 2 min)
- **Phase 3:** Audio Analysis (optional, requires export)
- **Phase 4:** LLM Expert Analysis (optional)

**Quick Reference:**

**Before/After Workflow:**
1. `als-doctor quick project.als` - Check current health
2. Save backup copy of .als file
3. Make changes in Ableton
4. `als-doctor compare backup.als project.als` - Verify improvement

**Project Selection Workflow:**
1. `als-doctor scan "Ableton Projects" --min-number 20 --limit 50`
2. Pick a Grade A/B project to polish
3. Or pick a Grade C project with a good musical idea to clean up

**Version Comparison:**
```cmd
als-doctor compare "22 Project\22_2.als" "22 Project\22_12.als"
```
Shows exactly what changed between your cleanest and most cluttered versions.

### Data Extracted From .als Files

The .als file is gzipped XML containing complete project state:

```
.als file (gzipped XML)
├── Project metadata (tempo, time sig, version)
├── Tracks[]
│   ├── Name, type (MIDI/Audio/Return/Master)
│   ├── Volume, pan, mute, solo
│   └── DeviceChain[]
│       ├── Device type (Eq8, Compressor2, VST, etc.)
│       ├── ON/OFF state
│       ├── User-assigned name
│       └── Parameters (Threshold, Ratio, Attack, etc.)
├── MIDI clips and notes
├── Audio clip references
├── Locators/markers
└── Plugin list (VST, AU, Max4Live)
```

### No Audio Export Required

Unlike the audio analysis pipeline, ALS Doctor works **entirely from the .als file**:

| Analysis Type | Requires Audio Export? |
|--------------|------------------------|
| Audio analysis (clipping, loudness, etc.) | YES |
| Stem analysis (frequency clashes) | YES |
| Reference comparison | YES |
| **Device chain analysis** | **NO** |
| **Effect chain diagnosis** | **NO** |
| **Version comparison** | **NO** |
| **Batch project ranking** | **NO** |

This enables instant feedback on project health without the Ableton export workflow.
