# AbletonAIAnalysis - Features Overview

A comprehensive music production analysis toolkit for Ableton Live users, focused on trance music production.

---

## Quick Reference

| Task | Command |
|------|---------|
| Analyze a song | `python analyze.py --song <songname>` |
| Analyze audio file | `python analyze.py --audio mix.wav` |
| Interactive coaching | `als-doctor coach <file>` |
| Check export readiness | `als-doctor preflight <file>` |
| Compare to reference | `--compare-ref reference.wav` |
| Build ref library | `yt-analyzer ingest <url>` |
| View history | `als-doctor db history <song>` |
| Start dashboard | `als-doctor dashboard` |

---

## Core Features

### 1. Mix Analysis (`analyze.py`)

Analyzes your audio files with 7+ dimensions:

- **Clipping detection** with severity scoring
- **Dynamic range** (peak, RMS, crest factor)
- **Frequency balance** across 7 bands (sub, bass, low-mid, mid, high-mid, high, air)
- **Stereo width** and correlation
- **Loudness** (LUFS estimation)
- **Tempo detection**
- **Section-by-section** analysis (intro, buildup, drop, breakdown, outro)

**Usage:**
```bash
cd C:/claude-workspace/AbletonAIAnalysis/projects/music-analyzer
python analyze.py --audio "D:\OneDrive\Music\Projects\35_13_2.wav"
```

---

### 2. Stem Analysis

Analyzes multiple stems together to find mixing issues:

- **Frequency clashes** between instruments
- **Masking issues** (kick vs bass, lead vs pad, etc.)
- **Volume balance** problems
- **Panning conflicts**
- **Dominant frequency** extraction per stem

**Usage:**
```bash
python analyze.py --stems path/to/stems/
python analyze.py --audio mix.wav --stems path/to/stems/
```

---

### 3. ALS Project Doctor (`als_doctor.py`)

Deep inspection of Ableton Live project files:

- **Device chain analysis** (EQ, compressor, reverb settings)
- **MIDI health** (empty clips, duplicates, short clips)
- **Track routing** issues
- **Version history** tracking
- **Project health scoring** (A-F grades)
- **Effect chain optimization** suggestions

**Usage:**
```bash
als-doctor diagnose "path/to/project.als"
als-doctor db history <songname>
als-doctor best <songname>
```

**Available Commands:**
```bash
als-doctor db init                    # Initialize database
als-doctor db list                    # List all scanned projects
als-doctor db history <song>          # Show version history
als-doctor db status                  # Show library status
als-doctor scan <dir>                 # Scan directory for .als files
als-doctor diagnose <file>            # Analyze single .als file
als-doctor best <song>                # Find best version
als-doctor coach <file>               # Interactive coaching mode
als-doctor preflight <file>           # Check export readiness
als-doctor dashboard                  # Start local web dashboard
```

---

### 4. Reference Track Comparison

Compare your mix against professional references:

- **RMS/LUFS differences** per stem
- **Spectral centroid** comparison (brightness)
- **Stereo width** differences
- **Dynamic range** comparison
- **Frequency band** differences (bass, low-mid, mid, high-mid, high)
- **Specific dB/Hz adjustment** recommendations

**Usage:**
```bash
python analyze.py --audio mix.wav --compare-ref reference.wav
```

---

### 5. Coach Mode

Interactive step-by-step issue fixing workflow:

- Shows **one issue at a time** with specific fix instructions
- Waits for you to apply fix in Ableton
- **Re-analyzes** to verify improvement
- Tracks your session progress and statistics
- Celebrates health improvements

**Usage:**
```bash
als-doctor coach project.als
```

**Controls:**
- `Enter` = Done with fix
- `S` = Skip this issue
- `Q` = Quit session

---

### 6. Preflight Check

Export readiness verification before bouncing:

- Health score validation
- Blocker identification
- Checklist with pass/fail/warning status
- Strict mode option (requires Grade A)

**Usage:**
```bash
als-doctor preflight project.als
als-doctor preflight project.als --strict
```

---

### 7. YouTube Reference Library (`yt_analyzer.py`)

Build a reference track database from YouTube:

- **Download & convert** to WAV
- **Extract features** (BPM, key, loudness, spectral profile)
- **Stem separation** via Demucs
- **Trance arrangement analysis** (drops, breakdowns, buildups)
- **Rating system** for tracks

**Usage:**
```bash
yt-analyzer db init              # Initialize database
yt-analyzer ingest <url>         # Download and add track(s)
yt-analyzer analyze <id>         # Run analysis pipeline
yt-analyzer list                 # List all tracks
yt-analyzer show <id>            # Show track details
yt-analyzer search --similar-to  # Find similar tracks
```

---

### 8. Harmonic Analysis

Musical key and harmony detection:

- **Key detection** with confidence scores
- **Camelot notation** for DJ mixing compatibility
- **Harmonic complexity** scoring (0-100)
- **Key relationships** (relative major/minor)
- **Chord change rate** estimation

---

### 9. Spatial Analysis

3D audio and stereo field analysis:

- **3D spatial scoring** (height, depth, width)
- **Mono compatibility** check
- **Phase coherence** analysis
- **Headphone vs speaker** translation scoring
- **Surround/Atmos readiness** assessment

---

### 10. Live Ableton Control (MCP/OSC)

Real-time control of Ableton Live via OSC:

- **Get track names** and info
- **Set volumes, panning, sends**
- **Control effect parameters**
- **Enable/disable devices**
- **Apply fixes automatically**

**Setup:**
1. Start OSC daemon (keep running):
   ```bash
   cd C:\claude-workspace\ableton-live-mcp-server
   python osc_daemon.py
   ```
2. Enable AbletonOSC in Live: Preferences → Link/Tempo/MIDI → Control Surface
3. Test: Ask Claude to "get track names"

**Capabilities:**
- Can: set volumes, panning, sends, effect parameters, enable/disable devices
- Cannot: delete devices, edit MIDI, draw automation

---

### 11. Dashboard (Web Interface)

Local web UI for browsing analysis data:

- Project list with health scores
- Sortable/filterable views
- Version timeline per project
- Health trend charts
- Learning insights display

**Usage:**
```bash
als-doctor dashboard
```

**Routes:**
- `/` - Home with health overview
- `/projects` - Sortable/filterable project list
- `/project/<id>` - Project detail with timeline
- `/insights` - Pattern insights and learning

---

### 12. Automated Scanning

Background monitoring and scheduled analysis:

**Watcher** - Auto-analyze on file save:
- Monitors folders for .als changes
- Triggers automatic analysis
- Rate limiting for frequent saves

**Scheduler** - Batch scans on schedule:
```bash
als-doctor schedule add --path D:/Projects --frequency daily --time 03:00
```

**Notifications** - Desktop alerts:
- Analysis completion alerts
- Health drop warnings
- Batch scan summaries

---

### 13. Fix Generation

Converts analysis issues into actionable fixes:

- Maps problems to **specific parameter changes**
- **Severity-based** prioritization
- Confidence scoring for recommendations
- Categorizes fixes (levels, frequency, dynamics, stereo, mastering)
- Can **auto-apply** via Ableton connection

**Smart Apply Tool:**
```bash
python smart_apply.py --stems path/to/stems/
python smart_apply.py --stems path/to/stems/ --connect --auto-apply
```

---

## Specialized Analyzers

### Clarity Analyzer
- Spectral contrast measurement
- Masking risk assessment
- Brightness categorization (dark/balanced/bright/harsh)
- Clarity scoring (0-100)

### Synth Analyzer
- Waveform type estimation (saw, square, triangle, sine, complex, noise)
- Filter characteristics (type, cutoff, resonance)
- ADSR envelope shape estimation
- Modulation detection (vibrato, tremolo, LFO)
- Unison/detuning estimation

### Device Chain Analyzer
- Complete device chain extraction from .als files
- Device ON/OFF state tracking
- Full parameter values for native Ableton devices
- VST/AU plugin detection
- 14 device categories

### MIDI Analyzer
- Empty clip detection
- Very short clip identification
- Duplicate clip detection
- Empty track detection
- Arrangement structure analysis

---

## Project Comparison

### Project Differ
Compare two .als versions:
- Track device changes (added, removed, modified)
- Parameter change detection
- Health score delta calculation
- Improvement vs regression assessment

---

## Standard Input Structure

Songs ready for analysis live in `/inputs/<songname>/`:

```
/inputs/
  └── <songname>/
      ├── info.json                 # Optional: Song metadata
      ├── project.als               # Optional: Ableton project file
      ├── mix/                      # Full mix exports
      │   ├── v1/
      │   │   └── mix.flac
      │   └── v2/
      │       └── mix.flac
      ├── stems/                    # Individual track exports
      │   ├── kick.wav
      │   ├── bass.wav
      │   └── ...
      ├── midi/                     # Optional: MIDI files
      └── references/               # Optional: Reference tracks
```

Reports are saved to `/reports/<songname>/<songname>_<version>_analysis_<date>.html`

---

## Trance-Specific Features

This toolkit is optimized for trance production:

- **Arrangement analysis** with trance terminology (DROP, BREAKDOWN, BUILDUP)
- **Bars to first drop** calculation
- **Drop energy** measurement
- **Breakdown characteristics** analysis
- **Genre presets** for progressive, uplifting, psytrance sub-genres
- **BPM range** optimization (typically 128-150)

---

## Database & Tracking

SQLite database stores all analysis data:

- Project version history
- Health score trending
- Issue patterns across projects
- Reference comparison history
- Learning-based recommendations
- Template management

---

## File Locations

| Component | Path |
|-----------|------|
| Music Analyzer | `projects/music-analyzer/` |
| YouTube Analyzer | `projects/youtube-reference-track-analysis/` |
| Analysis Reports | `reports/<songname>/` |
| Song Inputs | `inputs/<songname>/` |
| Database | `data/projects.db` |
| References | `references/` |
