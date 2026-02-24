# AI Song Scaffold Generator

## Project Overview

An AI-powered system that takes natural language descriptions of songs and generates complete Ableton Live project files with:
- Pre-configured tracks
- MIDI patterns placed in arrangement
- Structure markers
- Mixing setup (routing, sends, returns)
- Ready to produce - just add sounds

**Example Input:**
> "Create an uplifting trance track in A minor at 138 BPM. I want a long emotional breakdown with piano chords,
> a punchy kick, rolling bassline, and a classic supersaw lead. The drop should hit hard with lots of energy.
> Make it DJ-friendly with proper intro/outro."

**Output:**
- `MyTrack.als` - Complete Ableton project
- `MyTrack/midi/` - All MIDI patterns
- `MyTrack/structure.json` - Song structure metadata

---

## Core Features

### 1. Natural Language Understanding

The system should parse user descriptions to extract:

| Parameter | Examples | Default |
|-----------|----------|---------|
| **Genre** | trance, progressive, tech house, dubstep | trance |
| **Subgenre** | uplifting, dark, progressive, psytrance | uplifting |
| **Mood** | emotional, aggressive, euphoric, melancholic | euphoric |
| **Tempo** | "138 BPM", "fast", "slow" | 138 |
| **Key** | "A minor", "F# minor", "relative minor" | A minor |
| **Energy Curve** | "big drop", "gradual build", "multiple peaks" | standard |
| **Structure** | "long breakdown", "double drop", "radio edit" | standard |
| **Elements** | "punchy kick", "rolling bass", "supersaw lead" | default set |
| **Duration** | "6 minutes", "radio length", "extended mix" | ~6 min |
| **DJ-Friendly** | "proper intro/outro", "mixable" | yes |

### 2. Structure Generation

Generate song structure based on:

**Preset Structures:**
- `standard_trance` - Intro → Build → Breakdown → Drop → Break → Breakdown → Drop → Outro
- `extended_mix` - Longer intro/outro, 3 drops
- `radio_edit` - Short intro, 2 drops, quick outro (~3:30)
- `progressive` - Long builds, gradual energy changes
- `festival` - Big drops, short breakdowns, maximum energy

**Custom Structure from Description:**
- "long emotional breakdown" → 64-bar breakdown
- "quick build" → 8-bar buildup instead of 16
- "double drop" → Two drops back-to-back
- "DJ-friendly" → 32+ bar intro/outro

### 3. Track Generation

**Standard Trance Track Set:**
```
├── Kick (MIDI)       - 4-on-floor patterns
├── Bass (MIDI)       - Sub + mid bass patterns
├── Perc (MIDI)       - Hats, claps, rides, fills
├── Pad (MIDI)        - Atmospheric chords
├── Lead (MIDI)       - Main melody
├── Arp (MIDI)        - Rolling patterns
├── Pluck (MIDI)      - Pluck/stab patterns
├── FX (Audio)        - Risers, impacts, sweeps
├── Vox (Audio)       - Vocal chops
├── Piano (MIDI)      - Breakdown piano (if requested)
├── A-Reverb (Return) - Reverb send
├── B-Delay (Return)  - Delay send
└── Master            - Master bus
```

**Track Configuration:**
- Proper routing (all tracks → Master)
- Send levels pre-configured
- Color coding by element type
- Track annotations with purpose

### 4. MIDI Pattern Generation

**Pattern Types per Element:**

| Track | Pattern Options | Variations |
|-------|----------------|------------|
| Kick | 4-on-floor, offbeat, broken, half-time | Energy levels 0.3-1.0 |
| Bass | Rolling 16ths, sustained, stabs, octave | Sidechain-friendly |
| Chords | Sustained, stabs, rhythmic, arpeggiated | Chord progressions |
| Arp | Up, down, up-down, trance, random | 8th/16th/32nd |
| Lead | Melody lines (AI-generated) | Phrase variations |
| Hats | Offbeat, 16ths, rides | Open/closed patterns |
| Clap | 2&4, fills, rolls | Build variations |

**Pattern Placement Rules:**
```
INTRO:      Kick (soft), Hats (light)
BUILDUP:    + Bass, Arp, Clap, Perc
BREAKDOWN:  - Kick, - Bass, + Chords, + Lead melody
DROP:       ALL elements at full energy
BREAK:      Kick + Bass only (stripped)
OUTRO:      Mirror intro, fade elements
```

### 5. Chord Progression Generation

**Built-in Progressions:**
- Trance classics: i-VI-III-VII, i-VI-iv-V
- Emotional: i-iv-VI-V, i-III-VII-VI
- Dark: i-VII-VI-VII, i-iv-v-i
- Uplifting: I-V-vi-IV (major key)

**AI-Generated Progressions:**
- Based on mood description
- Key-aware
- Voice leading optimization

### 6. Melody Generation

**Melody Characteristics:**
- Scale-constrained
- Phrase structure (4/8 bar phrases)
- Rhythmic patterns typical of genre
- Call-and-response patterns
- Climactic note placement

**AI Melody Input:**
- "catchy hook" → Repetitive, memorable motif
- "emotional" → Larger intervals, sustained notes
- "driving" → 16th note patterns, rhythmic

### 7. Energy Curve Modeling

**Energy Parameters:**
- `0.0-0.3`: Minimal (intro/outro)
- `0.3-0.5`: Building (buildup sections)
- `0.5-0.7`: Medium (breaks, transitions)
- `0.7-0.9`: High (pre-drop builds)
- `1.0`: Maximum (drops)

**Energy Affects:**
- MIDI velocity
- Note density
- Pattern complexity
- Which tracks are active

---

## Technical Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACE                           │
│  (CLI / Web / Chat Interface)                               │
│  "Create an uplifting trance track..."                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 AI INTERPRETATION LAYER                      │
│  - Natural language parsing                                  │
│  - Parameter extraction                                      │
│  - Ambiguity resolution                                      │
│  - Genre/style inference                                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 SONG SPECIFICATION                           │
│  {                                                           │
│    "genre": "trance",                                        │
│    "subgenre": "uplifting",                                  │
│    "tempo": 138,                                             │
│    "key": "Am",                                              │
│    "structure": [...],                                       │
│    "tracks": [...],                                          │
│    "mood": "euphoric"                                        │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 GENERATION ENGINE                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Structure   │  │    MIDI      │  │   Ableton    │       │
│  │  Generator   │  │  Generator   │  │  Project     │       │
│  │              │  │              │  │  Generator   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    OUTPUT FILES                              │
│  - project.als (Ableton Live Set)                            │
│  - midi/*.mid (MIDI patterns)                                │
│  - structure.json (metadata)                                 │
│  - README.txt (generation notes)                             │
└─────────────────────────────────────────────────────────────┘
```

### Module Breakdown

```
projects/ableton-generators/
├── ai_song_generator.py      # Main entry point
├── nl_parser.py              # Natural language parsing
├── song_spec.py              # Song specification dataclasses
├── structure_generator.py    # Generate song structure
├── midi_generator.py         # MIDI pattern generation (exists)
├── melody_generator.py       # AI melody generation
├── chord_generator.py        # Chord progression generation
├── ableton_project.py        # .als file generation (exists)
├── templates/
│   ├── trance.json           # Trance genre template
│   ├── progressive.json      # Progressive template
│   └── techno.json           # Techno template
├── presets/
│   ├── progressions.json     # Chord progressions library
│   ├── patterns.json         # Rhythm patterns library
│   └── structures.json       # Arrangement structures
└── tests/
    └── test_generation.py
```

---

## User Interface Options

### 1. CLI Interface (Phase 1)
```bash
# Basic usage
python ai_song_generator.py "uplifting trance in A minor, 138 BPM"

# With options
python ai_song_generator.py \
  --prompt "emotional breakdown, punchy kick" \
  --output ~/Music/MyTrack \
  --open-ableton

# Interactive mode
python ai_song_generator.py --interactive
> What kind of track do you want to create?
> uplifting trance with a long breakdown
> What tempo?
> 138
> Generating...
```

### 2. Chat Interface (Phase 2)
Integration with Claude Code for conversational generation:
```
User: Create a trance track for me
AI: What style are you going for? (uplifting, dark, progressive, psytrance)
User: Uplifting, something emotional with a big breakdown
AI: Got it! What about:
    - Tempo: 138 BPM (standard) or different?
    - Key: A minor works great for emotional trance
    - Duration: ~6 minutes (DJ-friendly)?
User: Perfect, go with those
AI: Generating your track... [creates files]
    Done! I've created:
    - MyTrack.als with 8 tracks
    - Full arrangement (208 bars)
    - MIDI patterns for kick, bass, chords, arp, lead

    Open in Ableton? [Y/n]
```

### 3. Web Interface (Phase 3)
- Visual structure editor
- Preview generated MIDI
- Drag-drop arrangement customization
- Export to Ableton

---

## Generation Examples

### Example 1: Basic Trance
**Input:** `"trance track"`

**Output:**
- Standard trance structure
- A minor, 138 BPM
- Default patterns for all elements

### Example 2: Specific Request
**Input:** `"dark psytrance in F# minor at 145 BPM with a driving bassline and short 16-bar breakdown"`

**Output:**
- F# minor, 145 BPM
- Psytrance structure (shorter breakdowns)
- Aggressive bass pattern
- Dark chord voicings
- 16-bar breakdown instead of 32

### Example 3: Mood-Based
**Input:** `"something melancholic and emotional, slow build, really let the breakdown breathe"`

**Output:**
- Inferred: progressive trance, ~132 BPM
- D minor (melancholic key)
- 64-bar breakdown
- Gradual energy curve
- Piano chords in breakdown
- Sustained pad textures

### Example 4: Reference-Based
**Input:** `"something like Chicane - Saltwater, that emotional progressive vibe"`

**Output:**
- Analyze reference (if available)
- Progressive trance structure
- Piano-driven breakdown
- Building arp patterns
- Emotional chord progression

---

## Data Models

### SongSpec
```python
@dataclass
class SongSpec:
    # Basic info
    name: str
    genre: str
    subgenre: str
    tempo: int
    key: str
    scale: str

    # Structure
    structure: List[SectionSpec]
    total_bars: int
    duration_seconds: float

    # Mood/style
    mood: str  # euphoric, dark, melancholic, aggressive
    energy_profile: str  # standard, building, peaks, flat

    # Track configuration
    tracks: List[TrackSpec]

    # Generation hints from AI parsing
    hints: Dict[str, Any]
```

### SectionSpec
```python
@dataclass
class SectionSpec:
    name: str
    section_type: str  # intro, buildup, breakdown, drop, outro
    start_bar: int
    bars: int
    energy: float
    active_tracks: List[str]
    pattern_overrides: Dict[str, str]  # track -> pattern_type
```

### TrackSpec
```python
@dataclass
class TrackSpec:
    name: str
    track_type: str  # midi, audio, return
    instrument_hint: str  # "punchy kick", "supersaw lead"
    color: int
    default_pattern: str
    send_levels: Dict[str, float]
```

---

## AI Integration Points

### 1. Prompt Parsing
Use Claude to parse natural language:
```python
def parse_song_request(prompt: str) -> SongSpec:
    """Use AI to extract song parameters from natural language."""
    # Send to Claude with structured output
    # Return parsed SongSpec
```

### 2. Melody Generation
Use AI for creative melody generation:
```python
def generate_melody(
    key: str,
    scale: str,
    bars: int,
    style_hints: List[str]
) -> List[MIDINote]:
    """Generate melody using AI with musical constraints."""
```

### 3. Chord Suggestions
```python
def suggest_progression(
    mood: str,
    key: str,
    bars: int
) -> List[Chord]:
    """AI suggests chord progression based on mood."""
```

### 4. Structure Optimization
```python
def optimize_structure(
    base_structure: List[Section],
    user_feedback: str
) -> List[Section]:
    """Refine structure based on user feedback."""
```

---

## Implementation Phases

### Phase 1: Core Generator (MVP)
- [ ] CLI interface
- [ ] Basic NL parsing (keyword extraction)
- [ ] Structure generation from presets
- [ ] MIDI pattern generation (existing)
- [ ] Ableton project generation (existing)
- [ ] Single genre: Trance

**Deliverable:** Working CLI that generates trance tracks from simple prompts

### Phase 2: AI Enhancement
- [ ] Claude integration for NL parsing
- [ ] AI melody generation
- [ ] AI chord progression suggestions
- [ ] Multiple genre support
- [ ] Reference track analysis integration

**Deliverable:** Intelligent parsing, creative generation

### Phase 3: Polish & UX
- [ ] Interactive chat mode
- [ ] Web interface
- [ ] Visual structure editor
- [ ] MIDI preview
- [ ] User presets/favorites

**Deliverable:** Full-featured creative tool

### Phase 4: Advanced Features
- [ ] Audio generation (stems)
- [ ] Device preset generation
- [ ] Automation curves
- [ ] Mix suggestions
- [ ] Collaboration features

---

## Success Metrics

1. **Generation Quality**
   - Generated MIDI should be musically coherent
   - Arrangements should follow genre conventions
   - Energy curves should feel natural

2. **User Experience**
   - < 30 seconds to generate a full project
   - Natural language should "just work"
   - Output should be immediately usable in Ableton

3. **Flexibility**
   - Support for major electronic genres
   - Customizable at every level
   - Extensible preset/template system

---

## Dependencies

- **Python 3.10+**
- **mido** - MIDI file generation
- **Claude API** - Natural language parsing (Phase 2)
- **librosa** (optional) - Reference track analysis
- **Existing modules:**
  - `midi_generator.py`
  - `create_trance_template.py`
  - `structure_detector.py`

---

## File Locations

```
Project Root: C:\claude-workspace\AbletonAIAnalysis\

Source Code:
  projects/ableton-generators/
    ├── ai_song_generator.py
    ├── midi_generator.py (exists)
    ├── song_generator.py (exists)
    └── create_trance_template.py (exists)

Output:
  C:\Users\badmin\Music\Generated_Songs\
    └── [SongName]/
        ├── [SongName].als
        ├── midi/
        │   ├── kick.mid
        │   ├── bass.mid
        │   └── ...
        └── structure.json

Templates:
  projects/ableton-generators/templates/
```

---

## Next Steps

1. **Review this requirements doc** - Any changes/additions?
2. **Decide on Phase 1 scope** - What's the MVP?
3. **Start implementation** - Begin with CLI and basic parsing
4. **Test with real usage** - Generate tracks, import to Ableton, iterate
