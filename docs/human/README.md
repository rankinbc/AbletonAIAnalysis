# Ableton AI Analysis

AI-powered music production analysis tool for Ableton 11 projects.

Analyze your mixes, detect frequency clashes between stems, compare against professional references, and get specific recommendations to improve your amateur mixes to professional quality.

## Features

- **Standard Input Structure** - Organize songs in `/inputs/<songname>/` with version tracking
- **Mix Quality Analyzer** - Clipping, dynamics, frequency balance, stereo width, loudness (LUFS)
- **Stem Clash Detector** - Find frequency overlaps between stems that cause muddiness
- **Reference Comparison** - Compare your mix against professional tracks stem-by-stem
- **AI Stem Separation** - Separate any mix into vocals, drums, bass, other (Spleeter)
- **AI Mastering** - Match your mix to a reference track using Matchering
- **ALS Project Parser** - Extract tempo, tracks, MIDI data from Ableton .als files
- **Comprehensive Reports** - HTML, text, or JSON reports with actionable suggestions

---

## Quick Start

### Recommended: Standard Input Structure

1. Create your song folder:
   ```
   inputs/MySong/
   ├── mix/v1/mix.flac      # Your mixdown
   ├── stems/               # Exported stems
   │   ├── kick.wav
   │   ├── bass.wav
   │   └── ...
   └── references/          # Professional reference track
       └── reference.wav
   ```

2. Run analysis:
   ```bash
   cd projects/music-analyzer
   python analyze.py --song MySong
   ```

3. View report at `reports/MySong/MySong_v1_analysis_<date>.html`

---

## Installation

1. Navigate to the project directory:
   ```bash
   cd projects/music-analyzer
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. (Optional) Install FFmpeg for full audio format support:
   - Windows: `choco install ffmpeg` or download from ffmpeg.org
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`

---

## Usage

### Standard Structure (Recommended)

```bash
# Analyze latest version
python analyze.py --song MySong

# Analyze specific version
python analyze.py --song MySong --version v1
```

### Manual Mode

```bash
# Single mixdown
python analyze.py --audio my_mix.wav

# With stems
python analyze.py --audio my_mix.wav --stems ./stems/

# Compare to reference
python analyze.py --audio my_mix.wav --compare-ref pro_track.wav

# Full analysis with Ableton project
python analyze.py --als my_song.als --audio my_mix.wav --stems ./stems/

# AI Mastering
python analyze.py --audio my_mix.wav --reference pro_track.wav --master
```

### Stem Separation

```bash
# Separate any audio into stems
python analyze.py --separate my_mix.wav
```

### Reference Library

```bash
# Add reference to library
python analyze.py --add-reference pro_track.wav --genre trance --tags "anthem,uplifting"

# List stored references
python analyze.py --list-references

# Use stored reference (faster)
python analyze.py --audio my_mix.wav --reference-id <track_id>
```

---

## Command Line Options

| Option | Short | Description |
|--------|-------|-------------|
| `--song` | | Song name in `/inputs/<song>/` (recommended) |
| `--version` | | Mix version to analyze (e.g., v1, v2) |
| `--audio` | `-a` | Path to audio file (WAV/FLAC) |
| `--stems` | `-s` | Path to directory containing stems |
| `--als` | | Path to Ableton .als project file |
| `--reference` | `-r` | Reference track for mastering |
| `--compare-ref` | | Compare mix against reference stem-by-stem |
| `--master` | `-m` | Apply AI mastering |
| `--separate` | | Separate audio into stems |
| `--add-reference` | | Add track to reference library |
| `--list-references` | | List stored reference tracks |
| `--output` | `-o` | Output directory (default: ./reports) |
| `--format` | | Report format: html, text, json |
| `--verbose` | `-v` | Enable verbose output |

---

## What Gets Analyzed

### Audio Analysis
| Metric | Description |
|--------|-------------|
| **Clipping** | Samples exceeding safe levels, with timestamps |
| **Dynamic Range** | Peak vs RMS, crest factor interpretation |
| **Frequency Balance** | Energy in 7 bands (sub to air) |
| **Stereo Width** | Correlation, mono compatibility, phase safety |
| **Loudness** | Integrated LUFS, short-term, momentary, true peak |
| **Transients** | Density, strength, attack quality |
| **Sections** | Auto-detected intro/buildup/drop/breakdown/outro |

### Stem Analysis
| Metric | Description |
|--------|-------------|
| **Frequency Clashes** | Overlapping frequencies between stems |
| **Masking** | Louder stems hiding quieter ones |
| **Volume Balance** | Stems too loud or quiet vs average |
| **Panning** | Distribution across stereo field |

### Reference Comparison
| Metric | Description |
|--------|-------------|
| **Stem-by-Stem** | Level, width, brightness per stem |
| **Frequency Bands** | Per-band energy comparison |
| **Balance Score** | 0-100 similarity rating |
| **Priority Actions** | Ranked recommendations |

### Ableton Project
| Metric | Description |
|--------|-------------|
| **Project Info** | Tempo, time signature, duration |
| **Tracks** | Names, types, volumes, pans |
| **MIDI** | Notes, clips, density |
| **Plugins** | VST/AU/Max devices used |

---

## Issues Detected

| Issue | Severity | Threshold |
|-------|----------|-----------|
| Clipping | Critical | Samples > 0.99 |
| Over-compression | Warning | Dynamic range < 6 dB |
| Phase issues | Critical | Correlation < 0 |
| Narrow stereo | Warning | Correlation > 0.95 |
| Frequency imbalance | Info | Band-specific |
| Too loud/quiet | Warning | >2 dB from target |
| True peak | Warning | >-1.0 dB |
| Frequency clash | Varies | >10% overlap |
| Masking | Warning | >10 dB level diff |

---

## Streaming Platform Targets

| Platform | Target LUFS |
|----------|-------------|
| Spotify | -14 |
| Apple Music | -16 |
| YouTube | -14 |
| Tidal | -14 |
| Amazon Music | -14 |
| SoundCloud | -14 |

---

## Input Structure

```
inputs/
└── MySong/
    ├── info.json           # Optional: metadata
    ├── project.als         # Optional: Ableton project
    ├── mix/
    │   ├── v1/
    │   │   └── mix.flac    # Version 1
    │   └── v2/
    │       └── mix.flac    # Version 2 (latest)
    ├── stems/
    │   ├── kick.wav
    │   ├── bass.wav
    │   ├── snare.wav
    │   └── lead.wav
    ├── midi/               # Optional
    │   └── chords.mid
    └── references/
        └── pro_track.wav
```

### info.json (Optional)
```json
{
  "title": "My Song",
  "genre": "trance",
  "tempo": 140,
  "key": "Am",
  "current_version": "v2",
  "versions": {
    "v1": { "date": "2026-01-14", "notes": "Initial mix" },
    "v2": { "date": "2026-01-15", "notes": "Fixed bass" }
  }
}
```

---

## Output Structure

Reports are saved with version tracking:

```
reports/
└── MySong/
    ├── MySong_v1_analysis_2026-01-14.html
    ├── MySong_v1_analysis_2026-01-16.html
    └── MySong_v2_analysis_2026-01-17.html
```

---

## Example Output

```
================================================================
         ABLETON AI ANALYSIS
         Music Production Analysis Tool
================================================================

>> Detecting Song Structure: MySong
  Song: MySong
  Version: v2
  Mix: mix.flac
  Stems: Found
  Reference: Found

>> Analyzing Audio Mix
  Duration: 4:32
  Detected Tempo: 140.0 BPM

  Issues Found:
  [!] Warning: Mix is 3.2dB quieter than streaming targets
  [i] Info: Slight low-mid buildup (280-400 Hz)

  Key Metrics:
    Peak: -0.3 dBFS
    RMS: -12.4 dBFS
    Dynamic Range: 12.1 dB
    Est. LUFS: -11.2
    Stereo Width: 68%

>> Analyzing Stems
  Found 8 stems

  Frequency Clashes Found:
    [MODERATE] Kick vs Bass
      Range: 60-120 Hz
      Fix: Cut bass at 80 Hz by 3 dB

>> Reference Track Comparison
  Your Mix: mix.flac
  Reference: pro_track.wav

  STEM-BY-STEM COMPARISON:

  DRUMS: [GOOD]
    Level: -8.2 dB (ref: -8.0 dB) → -0.2 dB

  BASS: [MODERATE]
    Level: -6.1 dB (ref: -8.3 dB) → +2.2 dB
    → Reduce bass by 2 dB

  Overall Balance Score: 78/100

>> Recommendations Summary
  1. Reduce bass volume by 2 dB to match reference
  2. Cut 60-120 Hz on bass to reduce kick clash
  3. Increase overall loudness by 3 dB for streaming

================================================================
Analysis Complete!

Report: reports/MySong/MySong_v2_analysis_2026-01-15.html
```

---

## Tips for Best Results

1. **Export stems at mix volume** - Don't normalize individual stems
2. **Use consistent sample rates** - 44.1kHz or 48kHz
3. **Name stems descriptively** - "Kick", "Bass", "Lead Synth", etc.
4. **Choose similar references** - Same genre, professionally mastered
5. **Use version folders** - Track your mix progress over time
6. **Leave headroom** - Export mix at -6 dB peak for mastering

---

## Troubleshooting

**"Song not found in /inputs/"**
- Create the folder structure: `inputs/MySong/mix/v1/mix.flac`

**"No audio files found"**
- Ensure files are WAV, FLAC, or AIFF format

**"matchering not available"**
- Install with `pip install matchering`
- Fallback loudness matching will be used

**"spleeter not available"**
- Install with `pip install spleeter`
- Required for stem separation and reference comparison

**"Error parsing ALS file"**
- Ensure it's Ableton 11 or compatible
- Try with `--verbose` for details

---

## License

MIT License - See LICENSE file for details.
