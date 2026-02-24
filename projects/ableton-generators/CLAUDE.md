# Ableton AI Song Generator - Claude Instructions

## Overview

This project generates complete Ableton Live projects from natural language descriptions. When a user asks to create a song/track, guide them through an **interactive process** and always show a **final summary** before generating.

## Default Generation Command

**ALWAYS use this command when generating:**
```bash
cd C:\claude-workspace\AbletonAIAnalysis\projects\ableton-generators
python ai_song_generator.py --preset [preset] --name "[Name]" --embed-midi --split-sections
```

This creates a **ready-to-play** project with MIDI clips split by section (Intro, Buildup, Drop, etc.) instead of one giant clip per track.

## Interactive Song Generation Flow

When a user wants to create a track, follow this process:

### Step 1: Gather Requirements

Ask about (in order):
1. **Genre** - What style? (trance, techno, house, etc.)
2. **Mood** - How should it feel? (uplifting, dark, emotional, driving, etc.)
3. **Tempo** - Specific BPM or description (fast, slow, standard)
4. **Key** - Musical key preference or let system choose
5. **Structure** - Standard, extended DJ mix, radio edit, or custom
6. **Special requests** - Long breakdown, punchy kick, specific elements, etc.
7. **Track name** - What to call it

### Step 2: Show Final Summary (REQUIRED)

**ALWAYS show this summary before generating:**

```
============================================================
  SONG GENERATION SUMMARY
============================================================

  Name:       [Track Name]
  Genre:      [genre] / [subgenre]
  Tempo:      [XXX] BPM
  Key:        [X] [major/minor]
  Mood:       [mood description]
  Structure:  [structure type]
  Duration:   ~[X:XX] ([XXX] bars)

  Sections:
    - Intro:      [XX] bars
    - Buildup:    [XX] bars
    - Breakdown:  [XX] bars
    - Drop:       [XX] bars
    - Outro:      [XX] bars

  Special Features:
    - [feature 1]
    - [feature 2]

  Output Location:
    D:\OneDrive\Music\Projects\Ableton\Ableton Projects\TEMPLATE\[Name]\

============================================================
  Ready to generate? (yes/no)
============================================================
```

### Step 3: Generate

Only after user confirms, run the generation command.

---

## Available Features

### Genre Presets

| Preset | Genre | Tempo | Key | Mood |
|--------|-------|-------|-----|------|
| `uplifting_trance` | Trance | 138 | A minor | Euphoric |
| `dark_trance` | Trance | 140 | F# minor | Aggressive |
| `progressive` | Trance | 132 | D minor | Hypnotic |
| `psytrance` | Trance | 145 | E harmonic minor | Psychedelic |
| `techno` | Techno | 130 | F minor | Hypnotic |
| `dark_techno` | Techno | 135 | D minor | Aggressive |
| `melodic_techno` | Techno | 125 | C minor | Emotional |
| `progressive_house` | House | 124 | G minor | Groovy |
| `radio_edit` | Trance | 138 | A minor | Euphoric (short) |

### Structure Types

| Type | Description | Duration |
|------|-------------|----------|
| `standard` | Classic 2-drop structure | ~6 min |
| `progressive` | Long builds, big breakdown | ~7-8 min |
| `radio` | Short intro/outro, punchy | ~3:30 |
| `techno` | Driving, minimal breakdown | ~6 min |
| `psytrance` | Fast, intense, short breaks | ~6 min |
| `melodic_techno` | Emotional, multiple peaks | ~8 min |

### Generation Methods

#### Method 1: Natural Language (Recommended)

```python
from claude_generator import generate_from_description

result = generate_from_description(
    description="uplifting trance with emotional breakdown and big drop",
    name="Euphoria",
    tempo=138,  # optional override
    key="A",    # optional override
)
```

#### Method 2: Preset-Based

```bash
cd C:\claude-workspace\AbletonAIAnalysis\projects\ableton-generators
python ai_song_generator.py --preset uplifting_trance --name "MyTrack"
```

#### Method 3: Interactive CLI

```bash
python claude_generator.py --interactive
```

#### Method 4: Reference Matching

Generate a track that matches a reference audio file:

```bash
python reference_profile.py generate "path/to/reference.mp3" --name "MyMatch"
```

Or analyze first:
```bash
python reference_profile.py analyze "path/to/reference.mp3"
```

### Standard Flags (ALWAYS USE)

| Flag | What it does |
|------|--------------|
| `--embed-midi` | Embeds MIDI directly in .als file (ready to play) |
| `--split-sections` | Creates separate clips per section instead of one giant clip |

### Optional Mixing Features

Ask user if they want these extras:

| Flag | Feature | When to suggest |
|------|---------|-----------------|
| `--sidechain` | Sidechain compression routing | User wants "pumping bass" |
| `--sends` | Reverb/delay send levels | User wants mixing advice |
| `--mix-templates` | EQ/compression per track | User is new to mixing |
| `--vst-presets` | VST synth preset suggestions | User asks "what synth?" |
| `--full-mix` | All of the above | User wants complete setup |

### Default Features (always included)

- **Texture generation** - Risers, impacts, atmospheres
- **Stem arrangement** - Intelligent track activation per section

Disable with `--no-textures` or `--no-stem-arrange` if needed.

### Output Structure

Generated projects are saved to:
```
D:\OneDrive\Music\Projects\Ableton\Ableton Projects\TEMPLATE\[TrackName]\
├── [TrackName].als      # Ableton Live project
├── song_spec.json       # Generation metadata
├── mix_config.json      # Mixing config (if --full-mix used)
└── midi/
    ├── kick.mid, bass.mid, chords.mid, arp.mid, lead.mid
    ├── hats.mid, clap.mid, fx.mid
    └── riser.mid, impact.mid, atmosphere.mid  # Textures
```

---

## Quick Commands Reference

### Generate Track (after interactive session)

```bash
cd C:\claude-workspace\AbletonAIAnalysis\projects\ableton-generators

# STANDARD COMMAND (use this by default)
python ai_song_generator.py --preset [preset_name] --name "[TrackName]" --embed-midi --split-sections

# With all mixing features (sidechain, sends, templates, presets)
python ai_song_generator.py --preset [preset_name] --name "[TrackName]" --embed-midi --split-sections --full-mix

# From natural language description
python claude_generator.py "[description]" --name "[TrackName]"

# With reference matching
python ai_song_generator.py --reference "[reference.mp3]" --name "[TrackName]" --embed-midi --split-sections
```

**Why `--embed-midi --split-sections`?**
- `--embed-midi` = MIDI is inside the .als file, ready to play immediately
- `--split-sections` = Each track has separate clips per section (Intro, Drop, etc.) instead of one giant clip

### Open in Ableton

```bash
start "" "C:\ProgramData\Ableton\Live 11 Suite\Program\Ableton Live 11 Suite.exe" "[path_to_als]"
```

### List Presets

```bash
python ai_song_generator.py --list-presets
```

### Dry Run (preview without generating)

```bash
python ai_song_generator.py --preset uplifting_trance --name "Test" --dry-run
```

---

## Advanced Features

### Automation Curves

Generate automation for effects:

```python
from automation_generator import AutomationGenerator, generate_section_automation

gen = AutomationGenerator(tempo=138)

# Filter sweep for buildup
sweep = gen.filter_sweep(start_bar=32, bars=16, start_freq=200, end_freq=8000)

# Riser effect (filter + volume)
riser = gen.riser_sweep(start_bar=48, bars=8)

# Sidechain pumping
pump = gen.sidechain_pump(start_bar=0, bars=32)

# Section-based automation
curves = generate_section_automation("buildup", start_bar=32, bars=16, tempo=138)
```

### Device Library

Extract and reuse devices from existing projects:

```bash
# Extract devices from a project
python device_library.py extract "project.als"

# List available devices
python device_library.py list

# Show device details
python device_library.py show "My Synth"
```

### Reference Profile Analysis

Analyze a reference track to extract parameters:

```python
from reference_profile import ReferenceExtractor

extractor = ReferenceExtractor()
profile = extractor.extract_from_audio("reference.mp3")

print(f"Tempo: {profile.tempo}")
print(f"Key: {profile.key}")
print(f"Genre: {profile.genre}/{profile.subgenre}")
```

---

## Example Conversation Flow

**User:** "Make me a trance track"

**Claude:** "Let's create your track! A few questions:

1. **Style** - What kind of trance?
   - Uplifting (euphoric, emotional)
   - Progressive (hypnotic, building)
   - Dark (aggressive, driving)
   - Psytrance (fast, psychedelic)

**User:** "Uplifting"

**Claude:** "Great choice!

2. **Tempo** - Standard uplifting is 138 BPM. Want to adjust?
   - Keep 138 BPM (recommended)
   - Slower (~130 BPM)
   - Faster (~142 BPM)

**User:** "138 is fine"

**Claude:** "

3. **Key** - A minor is classic for uplifting. Preference?
   - A minor (classic, emotional)
   - F# minor (darker tone)
   - D minor (melancholic)

**User:** "A minor"

**Claude:** "

4. **Structure** - How should it be arranged?
   - Standard (2 drops, ~6 min)
   - Extended DJ (longer intro/outro)
   - Radio edit (short, punchy)

**User:** "Standard"

**Claude:** "

5. **Special requests?**
   - Long emotional breakdown?
   - Extra punchy kick?
   - Specific elements?

**User:** "Long breakdown with piano feel"

**Claude:** "

6. **Track name?**

**User:** "Sunrise"

**Claude:** "
```
============================================================
  SONG GENERATION SUMMARY
============================================================

  Name:       Sunrise
  Genre:      trance / uplifting
  Tempo:      138 BPM
  Key:        A minor
  Mood:       euphoric
  Structure:  standard (2 drops)
  Duration:   ~6:29 (224 bars)

  Sections:
    - Intro:      32 bars (0:56)
    - Buildup:    16 bars (0:28)
    - Breakdown:  32 bars (0:56) [extended, emotional]
    - Drop 1:     32 bars (0:56)
    - Break:      16 bars (0:28)
    - Breakdown:  32 bars (0:56)
    - Drop 2:     32 bars (0:56)
    - Outro:      32 bars (0:56)

  Special Features:
    - Extended emotional breakdown
    - Piano-style chord voicings

  Output Location:
    D:\OneDrive\Music\Projects\Ableton\Ableton Projects\TEMPLATE\Sunrise\

============================================================
  Ready to generate? (yes/no)
============================================================
```

**User:** "yes"

**Claude:** [Generates track and reports success]

---

## Files in This Project

### Core Generation
| File | Purpose |
|------|---------|
| `ai_song_generator.py` | Main CLI entry point |
| `claude_generator.py` | Claude Code integration + interactive mode |
| `song_spec.py` | Data models (SongSpec, SectionSpec, TrackSpec) |
| `ableton_project.py` | ALS file generation |
| `midi_generator.py` | MIDI pattern generation |
| `melody_generator.py` | Melody/lead generation |
| `transition_generator.py` | Transition effects between sections |
| `config.py` | Configuration and paths |

### Default Features (Always Active)
| File | Purpose |
|------|---------|
| `texture_generator.py` | Risers, impacts, atmospheres based on mood |
| `texture_midi_export.py` | MIDI export for textures |
| `stem_arranger.py` | Intelligent track activation per section |

### Optional Mixing Features
| File | Purpose | CLI Flag |
|------|---------|----------|
| `sidechain_config.py` | Sidechain compression routing | `--sidechain` |
| `send_routing.py` | Reverb/delay send levels | `--sends` |
| `mix_templates.py` | EQ/compression per track type | `--mix-templates` |
| `vst_preset_matcher.py` | VST preset suggestions | `--vst-presets` |

### Other
| File | Purpose |
|------|---------|
| `reference_profile.py` | Reference track analysis & matching |
| `automation_generator.py` | Automation curve generation |
| `device_library.py` | Device preset management |

---

## Important Notes

1. **Always use `--embed-midi --split-sections`** - This creates ready-to-play projects with organized clips
2. **Always show summary before generating** - Users should confirm before files are created
3. **Output location is fixed** - All projects go to the TEMPLATE folder
4. **MIDI is embedded** - With `--embed-midi`, user can hit play immediately (no dragging needed)
5. **Clips are per-section** - With `--split-sections`, each section (Intro, Drop, etc.) is a separate clip

## Troubleshooting

**"Module not found" errors:**
```bash
cd C:\claude-workspace\AbletonAIAnalysis\projects\ableton-generators
```

**Check if dependencies are installed:**
```bash
pip install mido
```

**List what's available:**
```bash
python ai_song_generator.py --list-presets
python reference_profile.py list
```
