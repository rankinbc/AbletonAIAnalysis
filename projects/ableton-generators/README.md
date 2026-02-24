# Ableton AI Song Generator

AI-powered song scaffold generator for Ableton Live. Generate complete project structures with MIDI patterns, arrangement markers, and professional mixing configurations.

## Quick Start

```bash
# Recommended: Ready-to-play with clips split by section
python ai_song_generator.py --preset uplifting_trance --name "MyTrack" --embed-midi --split-sections

# With all mixing features
python ai_song_generator.py --preset dark_trance --name "Dark Dreams" --embed-midi --split-sections --full-mix

# Generate from natural language description
python claude_generator.py "uplifting trance with emotional breakdown"

# Interactive guided mode
python ai_song_generator.py --interactive
```

**Recommended flags:**
- `--embed-midi` - MIDI embedded in .als file (hit play immediately)
- `--split-sections` - Separate clips per section (Intro, Drop, etc.) instead of one giant clip

## Features

### Core Generation (Always Included)

| Feature | Description | File |
|---------|-------------|------|
| MIDI Pattern Generation | Drum patterns, bass lines, arps, chords | `midi_generator.py` |
| Melody Generation | Key-aware melodic phrases with motifs | `melody_generator.py` |
| Transition Generation | Buildups, risers, crashes, breakdowns | `transition_generator.py` |
| Ableton Project Assembly | .als file with tracks and markers | `ableton_project.py` |
| **Texture Generation** | Ambient pads, risers, impacts, atmospheres | `texture_generator.py` |
| **Stem Arrangement** | Intelligent track activation per section | `stem_arranger.py` |

### Recommended Flags

| Flag | Description |
|------|-------------|
| `--embed-midi` | Embed MIDI in .als file (ready to play immediately) |
| `--split-sections` | Split MIDI into separate clips per section (Intro, Drop, etc.) |

### Optional Mixing Features (CLI Flags)

| Feature | CLI Flag | Description | File |
|---------|----------|-------------|------|
| Sidechain Config | `--sidechain` | Auto-route kick->bass/pad compression | `sidechain_config.py` |
| Send Routing | `--sends` | Configure reverb/delay send levels | `send_routing.py` |
| Mix Templates | `--mix-templates` | Apply EQ/compression presets per track | `mix_templates.py` |
| VST Preset Matching | `--vst-presets` | Suggest synth presets for each track | `vst_preset_matcher.py` |
| All Mixing Features | `--full-mix` | Enable all mixing features | - |

## Available Presets

| Preset | Genre | BPM | Key | Mood |
|--------|-------|-----|-----|------|
| `uplifting_trance` | Trance | 138 | A minor | Euphoric |
| `dark_trance` | Trance | 140 | F# minor | Aggressive |
| `progressive` | Trance | 132 | D minor | Hypnotic |
| `psytrance` | Psytrance | 145 | E harmonic minor | Psychedelic |
| `techno` | Techno | 130 | F minor | Hypnotic |
| `dark_techno` | Techno | 135 | D minor | Aggressive |
| `melodic_techno` | Techno | 125 | C minor | Emotional |
| `progressive_house` | House | 124 | G minor | Groovy |

## Generated Output

With `--embed-midi --split-sections` (recommended):
```
MyTrack/
├── MyTrack.als          # Ableton Live project (MIDI embedded, ready to play!)
└── song_spec.json       # Generation parameters (for reference)
```

The .als file contains:
- All MIDI clips embedded (no external files needed)
- Clips split by section: "Kick - Intro", "Kick - Drop 1", etc.
- Textures: risers, impacts, atmospheres

Without `--embed-midi`:
```
MyTrack/
├── MyTrack.als          # Ableton Live project (references MIDI files)
├── song_spec.json       # Generation parameters
└── midi/                # MIDI files to drag into Ableton
    ├── kick.mid, bass.mid, chords.mid, arp.mid, lead.mid
    ├── hats.mid, clap.mid, fx.mid
    └── riser.mid, impact.mid, atmosphere.mid
```

## Feature Details

### Texture Generator (Default)

Generates mood-based textures that match your song's energy:

**Texture Types:**
- Ambient Pad - Sustained harmonic background
- Riser - Upward pitch/filter sweep
- Tension Riser - Multi-layer dramatic build
- Impact - Crash + sub + mid hit
- Sub Drop - Low frequency thump
- Downlifter - Falling sweep
- Noise Sweep - Filtered white noise
- Atmosphere - Evolving sparse textures
- Reverse Crash - Crescendo swell

**Mood Presets:** dark, euphoric, aggressive, hypnotic, melancholic, ethereal, industrial, mysterious, uplifting, tense

### Stem Arranger (Default)

Controls which tracks are active in each section based on energy levels:

**Stem Groups:**
- Drums (kick, clap, hats, perc)
- Bass (bass, sub)
- Harmony (chords, pad)
- Leads (lead, arp, pluck)
- FX (riser, impact, texture)
- Percussion (shaker, ride, crash)

**Features:**
- Energy-based activation (tracks appear at thresholds)
- Counter-layers (elements that exit when energy increases)
- Transition automation (volume fades, filter sweeps)
- Genre templates (trance, techno, house, progressive)

### Sidechain Configuration (Optional: `--sidechain`)

Auto-configures kick->bass/pad compression routing:

| Mode | Ratio | Release | Use Case |
|------|-------|---------|----------|
| subtle | 2:1 | 150ms | Transparent ducking |
| moderate | 4:1 | 100ms | Classic EDM pump |
| heavy | 8:1 | 80ms | Strong pump (techno) |
| extreme | 20:1 | 50ms | Aggressive (future bass) |

### Send Routing (Optional: `--sends`)

Configures reverb/delay send levels per track type:

**Reverb Types:** hall, plate, room, chamber, ambient, trance_hall
**Delay Types:** 1/4, 1/8, 1/8D (dotted), 1/16, slapback, ambient

**Smart Levels:** Lead 35% reverb, Pad 50%, Bass 0%

### Mix Templates (Optional: `--mix-templates`)

Per-track EQ and compression presets:

- EQ bands (high-pass, shelves, bells, cuts)
- Compression settings (ratio, attack, release, style)
- Gain staging targets (peak dB, RMS dB)
- Stereo width recommendations

**Supported track types:** kick, snare, clap, hats, perc, bass, sub, chords, pad, arp, pluck, lead, vox, riser, impact, atmosphere, texture

### VST Preset Matching (Optional: `--vst-presets`)

Suggests synth presets based on track role and genre:

**Supported Synths:**
- Wavetable: Serum, Vital, Massive, Ableton Wavetable
- Subtractive: Sylenth1, Diva, Ableton Analog
- FM: Operator, FM8
- Hybrid: Omnisphere

**Features:**
- Natural language search ("fat supersaw lead")
- Genre/mood filtering
- Energy-based matching
- Alternative synth suggestions

## CLI Reference

```bash
# Basic usage
python ai_song_generator.py [options]

# Options:
--spec, -s PATH         Load song spec from JSON file
--json, -j JSON         Inline JSON song spec
--preset, -p NAME       Use preset configuration
--interactive, -i       Interactive guided mode
--name, -n NAME         Song/project name
--output, -o PATH       Output directory
--open                  Open in Ableton after generation
--dry-run               Show spec without generating
--embed-midi            Embed MIDI clips in .als file
--create-tracks         Create tracks in .als (uses template)

# Optional mixing features
--sidechain             Enable sidechain compression routing
--sends                 Enable send effect routing
--mix-templates         Enable mix templates (EQ/compression)
--vst-presets           Enable VST preset suggestions
--full-mix              Enable all mixing features

# Reference matching
--reference, -r PATH    Match reference audio file
--profile PATH          Use stored reference profile
--list-references       List available reference profiles

# Utilities
--list-presets          List available presets
--validate PATH         Validate existing .als file
```

## Python API

### Generate from Description (Claude Integration)

```python
from claude_generator import generate_from_description

result = generate_from_description(
    description="uplifting trance with emotional breakdown",
    name="Euphoria",
    tempo=138,
    key="A",
    scale="minor"
)

print(f"Created: {result['als_path']}")
```

### Generate from Spec

```python
from song_spec import create_default_trance_spec
from ableton_project import AbletonProject

spec = create_default_trance_spec("MyTrack")
spec.tempo = 140
spec.key = "F#"

project = AbletonProject(spec)
als_path = project.generate()
```

### Use Individual Modules

```python
# Texture generation
from texture_generator import TextureGenerator, Mood

gen = TextureGenerator(tempo=138, key="A", mood=Mood.EUPHORIC)
textures = gen.generate_full_song_textures(structure, energy_curve)

# Stem arrangement
from stem_arranger import StemArranger

arranger = StemArranger(genre="trance")
layers = arranger.generate_arrangement(song_spec)

# Sidechain configuration
from sidechain_config import SidechainConfigurator

config = SidechainConfigurator(genre="trance", tempo=138)
routes = config.get_routes(["kick", "bass", "pad"])

# Send routing
from send_routing import SendRouter

router = SendRouter(genre="trance")
levels = router.get_levels_for_track("lead")

# Mix templates
from mix_templates import MixTemplateManager

manager = MixTemplateManager()
template = manager.get_template("bass")
print(template.eq_bands)

# VST preset matching
from vst_preset_matcher import VSTPresetMatcher

matcher = VSTPresetMatcher()
presets = matcher.search("fat supersaw lead", genre="trance")
```

## Configuration

Edit `config.py` to customize paths:

```python
@dataclass
class Config:
    OUTPUT_BASE: Path = Path(r"D:\Music\Projects\Ableton")
    ABLETON_EXE: Path = Path(r"C:\Program Files\Ableton\Live 11 Suite\Program\Ableton Live 11 Suite.exe")
    DEFAULT_LIVE_SET: Path = Path(r"D:\Music\Templates\Base_Template.als")
    TICKS_PER_BEAT: int = 480
    DEFAULT_TEMPO: int = 138
    DEFAULT_KEY: str = "A"
    DEFAULT_SCALE: str = "minor"
```

## File Structure

```
ableton-generators/
├── Core Generation
│   ├── midi_generator.py        # MIDI pattern generation
│   ├── melody_generator.py      # Melodic generation
│   ├── transition_generator.py  # Section transitions
│   ├── ableton_project.py       # .als file assembly
│   └── clip_embedder.py         # MIDI embedding in .als
│
├── Texture & Arrangement (Default)
│   ├── texture_generator.py     # Ambient/riser/impact generation
│   ├── texture_midi_export.py   # MIDI export for textures
│   └── stem_arranger.py         # Intelligent layering
│
├── Mixing (Optional)
│   ├── sidechain_config.py      # Sidechain compression routing
│   ├── send_routing.py          # Reverb/delay send levels
│   └── mix_templates.py         # EQ/compression per track
│
├── Integration
│   ├── vst_preset_matcher.py    # VST preset suggestions
│   └── reference_profile.py     # Reference track analysis
│
├── Specification
│   ├── song_spec.py             # Data models
│   └── config.py                # Configuration
│
├── CLI
│   ├── ai_song_generator.py     # Main CLI interface
│   └── claude_generator.py      # Claude Code integration
│
├── Utilities
│   ├── xml_utils.py             # .als XML manipulation
│   ├── device_library.py        # Device templates
│   ├── sample_generator.py      # Sample-based devices
│   └── debug_als.py             # .als debugging
│
└── docs/
    └── ADVANCED_FEATURES.md     # Feature roadmap
```

## Requirements

- Python 3.8+
- mido (MIDI file handling)
- Ableton Live 10+ (for opening .als files)

```bash
pip install mido
```

## Contributing

1. Create a new module in the appropriate category
2. Follow existing patterns (dataclasses, enums, convenience functions)
3. Include a `__main__` demo section
4. Update this README and `docs/ADVANCED_FEATURES.md`

## License

MIT License - See LICENSE file for details.
