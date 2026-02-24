# Phase 1 MVP Implementation Plan

## Overview

Transform natural language prompts into complete Ableton Live projects with MIDI patterns.

**Target Command:**
```bash
python ai_song_generator.py "uplifting trance in A minor, 138 BPM with punchy kick"
```

**Output:**
```
D:\OneDrive\Music\Projects\Ableton\Ableton Projects\TEMPLATE\
└── [SongName]/
    ├── [SongName].als          # Ableton project (with embedded MIDI if possible)
    ├── midi/
    │   ├── kick.mid
    │   ├── bass.mid
    │   ├── chords.mid
    │   ├── arp.mid
    │   ├── lead.mid            # Melody
    │   ├── hats.mid
    │   └── clap.mid
    └── song_spec.json          # Generation metadata
```

---

## Files to Create

### 1. `config.py` - Configuration & Paths

Centralize all paths and defaults. No more hardcoded paths scattered through code.

```python
from pathlib import Path
from dataclasses import dataclass

@dataclass
class Config:
    # Output paths
    OUTPUT_BASE: Path = Path(r"D:\OneDrive\Music\Projects\Ableton\Ableton Projects\TEMPLATE")

    # Ableton paths
    ABLETON_EXE: Path = Path(r"C:\ProgramData\Ableton\Live 11 Suite\Program\Ableton Live 11 Suite.exe")
    ABLETON_PREFS: Path = Path.home() / "AppData/Roaming/Ableton/Live 11.3.11"
    DEFAULT_LIVE_SET: Path = ABLETON_PREFS / "Preferences/DefaultLiveSet.als"

    # Defaults
    DEFAULT_TEMPO: int = 138
    DEFAULT_KEY: str = "A"
    DEFAULT_SCALE: str = "minor"
    DEFAULT_GENRE: str = "trance"
```

**Estimated effort:** Small (30 min)

---

### 2. `song_spec.py` - Data Models

Define the specification objects that flow through the system.

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

class SectionType(Enum):
    INTRO = "intro"
    BUILDUP = "buildup"
    BREAKDOWN = "breakdown"
    DROP = "drop"
    BREAK = "break"
    OUTRO = "outro"

@dataclass
class SectionSpec:
    name: str
    section_type: SectionType
    start_bar: int
    bars: int
    energy: float  # 0.0 - 1.0
    active_tracks: List[str] = field(default_factory=list)
    pattern_overrides: Dict[str, str] = field(default_factory=dict)

@dataclass
class TrackSpec:
    name: str
    track_type: str  # midi, audio, return
    color: int
    default_pattern: str
    instrument_hint: str = ""

@dataclass
class SongSpec:
    name: str
    genre: str = "trance"
    subgenre: str = "uplifting"
    tempo: int = 138
    key: str = "A"
    scale: str = "minor"
    mood: str = "euphoric"

    structure: List[SectionSpec] = field(default_factory=list)
    tracks: List[TrackSpec] = field(default_factory=list)

    # Parsing hints from NL
    hints: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_bars(self) -> int:
        if not self.structure:
            return 0
        last = self.structure[-1]
        return last.start_bar + last.bars

    @property
    def duration_seconds(self) -> float:
        bars = self.total_bars
        beats = bars * 4
        return beats * (60 / self.tempo)
```

**Estimated effort:** Small (30 min)

---

### 3. Natural Language Parsing - HANDLED BY CLAUDE

**Skipped** - Claude will parse natural language prompts directly and output a `SongSpec` JSON.

When invoking the generator through Claude Code, the conversation flow is:
1. User describes the track they want
2. Claude interprets the request and generates a complete `SongSpec`
3. Claude calls the generator with the spec as input

This eliminates the need for keyword-based parsing and provides much better understanding of nuanced requests.

---

### 4. `melody_generator.py` - Pattern-Based Melody Generation

Pre-defined trance melody patterns with variations.

```python
from dataclasses import dataclass
from typing import List, Tuple
import random
from mido import MidiFile, MidiTrack, Message

@dataclass
class MelodyNote:
    pitch: int      # MIDI note number
    start: float    # Start time in beats
    duration: float # Duration in beats
    velocity: int   # 0-127

class MelodyGenerator:
    """Pattern-based trance melody generator."""

    # Scale intervals from root
    SCALES = {
        'minor': [0, 2, 3, 5, 7, 8, 10],
        'major': [0, 2, 4, 5, 7, 9, 11],
        'harmonic_minor': [0, 2, 3, 5, 7, 8, 11],
    }

    # Trance melody patterns (scale degrees, relative timing)
    # Format: (degree, beat_offset, duration, velocity_mult)
    PATTERNS = {
        'anthem': [
            # Classic uplifting trance hook
            (0, 0.0, 0.5, 1.0),    # Root
            (2, 0.5, 0.5, 0.9),    # 3rd
            (4, 1.0, 1.0, 1.0),    # 5th (hold)
            (3, 2.0, 0.5, 0.8),    # 4th
            (2, 2.5, 0.5, 0.9),    # 3rd
            (0, 3.0, 1.0, 1.0),    # Root (hold)
        ],
        'call_response': [
            # Call (bars 1-2)
            (4, 0.0, 0.5, 1.0),
            (3, 0.5, 0.5, 0.9),
            (2, 1.0, 0.5, 0.8),
            (0, 1.5, 0.5, 0.9),
            # Response (bars 3-4)
            (2, 4.0, 0.5, 0.9),
            (3, 4.5, 0.5, 0.9),
            (4, 5.0, 1.0, 1.0),
            (5, 6.0, 2.0, 1.0),  # Climax note
        ],
        'driving': [
            # 16th note driven pattern
            (0, 0.0, 0.25, 0.9),
            (0, 0.25, 0.25, 0.7),
            (2, 0.5, 0.25, 0.9),
            (2, 0.75, 0.25, 0.7),
            (3, 1.0, 0.25, 1.0),
            (2, 1.25, 0.25, 0.8),
            (0, 1.5, 0.5, 0.9),
        ],
        'emotional': [
            # Longer notes, bigger intervals
            (0, 0.0, 2.0, 1.0),   # Hold root
            (4, 2.0, 2.0, 0.9),   # Jump to 5th
            (5, 4.0, 1.0, 1.0),   # 6th
            (4, 5.0, 1.0, 0.9),   # 5th
            (2, 6.0, 2.0, 0.8),   # 3rd (resolve)
        ],
        'arp_melody': [
            # Arpeggio-style melodic pattern
            (0, 0.0, 0.25, 0.8),
            (2, 0.25, 0.25, 0.8),
            (4, 0.5, 0.25, 0.9),
            (7, 0.75, 0.25, 1.0),  # Octave up
            (4, 1.0, 0.25, 0.9),
            (2, 1.25, 0.25, 0.8),
            (0, 1.5, 0.5, 0.8),
        ]
    }

    def __init__(self, key: str = 'A', scale: str = 'minor', tempo: int = 138):
        self.root = self._note_to_midi(key, octave=4)
        self.scale = scale
        self.tempo = tempo
        self.scale_notes = self._build_scale()

    def _note_to_midi(self, note: str, octave: int = 4) -> int:
        """Convert note name to MIDI number."""
        notes = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
        base = notes.get(note[0].upper(), 9)  # Default to A
        if len(note) > 1:
            if note[1] == '#':
                base += 1
            elif note[1] == 'b':
                base -= 1
        return base + (octave + 1) * 12

    def _build_scale(self) -> List[int]:
        """Build list of MIDI notes in scale across octaves."""
        intervals = self.SCALES.get(self.scale, self.SCALES['minor'])
        notes = []
        for octave_offset in range(-1, 2):  # 3 octaves
            for interval in intervals:
                notes.append(self.root + interval + (octave_offset * 12))
        return sorted(notes)

    def _degree_to_midi(self, degree: int) -> int:
        """Convert scale degree to MIDI note."""
        intervals = self.SCALES.get(self.scale, self.SCALES['minor'])
        octave_shift = degree // len(intervals)
        scale_index = degree % len(intervals)
        return self.root + intervals[scale_index] + (octave_shift * 12)

    def generate(
        self,
        bars: int = 8,
        pattern: str = 'anthem',
        energy: float = 1.0,
        variation: float = 0.2
    ) -> List[MelodyNote]:
        """Generate melody for specified number of bars."""

        if pattern not in self.PATTERNS:
            pattern = 'anthem'

        base_pattern = self.PATTERNS[pattern]
        pattern_length = max(note[1] + note[2] for note in base_pattern)
        pattern_bars = int(pattern_length / 4) + 1

        notes = []
        current_bar = 0

        while current_bar < bars:
            for degree, offset, duration, vel_mult in base_pattern:
                beat = current_bar * 4 + offset

                if beat >= bars * 4:
                    break

                # Apply variation
                actual_degree = degree
                if random.random() < variation:
                    actual_degree += random.choice([-1, 1])

                # Apply energy to velocity
                velocity = int(100 * vel_mult * (0.5 + 0.5 * energy))
                velocity = max(40, min(127, velocity))

                notes.append(MelodyNote(
                    pitch=self._degree_to_midi(actual_degree),
                    start=beat,
                    duration=duration,
                    velocity=velocity
                ))

            current_bar += pattern_bars

        return notes

    def to_midi(self, notes: List[MelodyNote], ticks_per_beat: int = 480) -> MidiTrack:
        """Convert melody notes to MIDI track."""
        track = MidiTrack()
        track.append(Message('program_change', program=81, time=0))  # Lead synth

        # Sort by start time
        sorted_notes = sorted(notes, key=lambda n: n.start)

        events = []
        for note in sorted_notes:
            start_tick = int(note.start * ticks_per_beat)
            end_tick = int((note.start + note.duration) * ticks_per_beat)
            events.append(('on', start_tick, note.pitch, note.velocity))
            events.append(('off', end_tick, note.pitch, 0))

        events.sort(key=lambda e: (e[1], e[0] == 'on'))

        current_tick = 0
        for event in events:
            delta = event[1] - current_tick
            if event[0] == 'on':
                track.append(Message('note_on', note=event[2], velocity=event[3], time=delta))
            else:
                track.append(Message('note_off', note=event[2], velocity=0, time=delta))
            current_tick = event[1]

        return track

    def generate_for_section(
        self,
        section_type: str,
        bars: int,
        energy: float
    ) -> List[MelodyNote]:
        """Generate appropriate melody for section type."""

        pattern_map = {
            'breakdown': 'emotional',
            'drop': 'anthem',
            'buildup': 'driving',
            'intro': 'arp_melody',
            'outro': 'arp_melody',
        }

        pattern = pattern_map.get(section_type, 'anthem')
        return self.generate(bars=bars, pattern=pattern, energy=energy)
```

**Estimated effort:** Medium-High (2-3 hours)

---

### 5. `ableton_project.py` - Project Assembly

Handles both .als generation AND MIDI file output.

```python
import gzip
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict
from datetime import datetime
from dataclasses import dataclass

from config import Config
from song_spec import SongSpec, SectionSpec
from midi_generator import MIDIGenerator
from melody_generator import MelodyGenerator

class AbletonProject:
    """Generates complete Ableton Live project with MIDI."""

    def __init__(self, spec: SongSpec, config: Config = None):
        self.spec = spec
        self.config = config or Config()
        self.output_dir = self.config.OUTPUT_BASE / spec.name
        self.midi_dir = self.output_dir / "midi"

    def generate(self) -> Path:
        """Generate complete project. Returns path to .als file."""

        # Create directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.midi_dir.mkdir(exist_ok=True)

        # Generate all MIDI files
        midi_files = self._generate_all_midi()

        # Generate .als file
        als_path = self._generate_als(midi_files)

        # Save spec for reference
        self._save_spec()

        return als_path

    def _generate_all_midi(self) -> Dict[str, Path]:
        """Generate MIDI files for all tracks."""

        midi_gen = MIDIGenerator(
            key=self.spec.key,
            scale=self.spec.scale,
            tempo=self.spec.tempo
        )

        melody_gen = MelodyGenerator(
            key=self.spec.key,
            scale=self.spec.scale,
            tempo=self.spec.tempo
        )

        files = {}

        # Generate patterns for each track based on structure
        for track in self.spec.tracks:
            if track.track_type != 'midi':
                continue

            if track.name.lower() == 'lead':
                # Use melody generator
                midi_path = self._generate_lead_track(melody_gen)
            else:
                # Use pattern generator
                midi_path = self._generate_pattern_track(midi_gen, track)

            files[track.name] = midi_path

        return files

    def _generate_lead_track(self, melody_gen: MelodyGenerator) -> Path:
        """Generate lead/melody track following song structure."""
        from mido import MidiFile, MidiTrack

        mid = MidiFile(ticks_per_beat=480)
        track = MidiTrack()
        mid.tracks.append(track)

        # Only generate melody in breakdown and drop sections
        for section in self.spec.structure:
            if section.section_type.value in ['breakdown', 'drop']:
                notes = melody_gen.generate_for_section(
                    section.section_type.value,
                    section.bars,
                    section.energy
                )
                # Offset notes to section start
                for note in notes:
                    note.start += section.start_bar * 4

                melody_track = melody_gen.to_midi(notes)
                for msg in melody_track:
                    track.append(msg.copy())

        midi_path = self.midi_dir / "lead.mid"
        mid.save(str(midi_path))
        return midi_path

    def _generate_pattern_track(self, midi_gen: MIDIGenerator, track) -> Path:
        """Generate pattern track following song structure."""
        # Use existing song_generator logic but output to specific path
        from song_generator import SongGenerator

        # Map track names to generator methods
        track_generators = {
            'kick': 'generate_kick',
            'bass': 'generate_bass',
            'chords': 'generate_chords',
            'arp': 'generate_arp',
            'hats': 'generate_hats',
            'clap': 'generate_clap',
        }

        gen_method = track_generators.get(track.name.lower())
        if not gen_method:
            return None

        # Generate full track following structure
        # ... (implementation follows song_generator pattern)

        midi_path = self.midi_dir / f"{track.name.lower()}.mid"
        # Save MIDI
        return midi_path

    def _generate_als(self, midi_files: Dict[str, Path]) -> Path:
        """Generate Ableton Live Set file."""

        # Load template
        template_path = self._find_template()
        with gzip.open(template_path, 'rb') as f:
            tree = ET.parse(f)
        root = tree.getroot()

        # Modify template
        self._set_tempo(root)
        self._add_tracks(root)
        self._add_locators(root)
        # Note: Adding MIDI clips directly is complex -
        # may need to import via file references

        # Save
        als_path = self.output_dir / f"{self.spec.name}.als"
        with gzip.open(als_path, 'wb') as f:
            tree.write(f, encoding='UTF-8', xml_declaration=True)

        return als_path

    def _find_template(self) -> Path:
        """Find suitable Ableton template."""
        # Try custom template first, fall back to default
        custom = self.config.OUTPUT_BASE / "Base_Template.als"
        if custom.exists():
            return custom
        return self.config.DEFAULT_LIVE_SET

    def _set_tempo(self, root: ET.Element):
        """Set project tempo."""
        # Find and update tempo element
        pass

    def _add_tracks(self, root: ET.Element):
        """Add/configure tracks."""
        pass

    def _add_locators(self, root: ET.Element):
        """Add arrangement locators for sections."""
        pass

    def _save_spec(self):
        """Save song spec as JSON for reference."""
        import json
        from dataclasses import asdict

        spec_path = self.output_dir / "song_spec.json"
        with open(spec_path, 'w') as f:
            json.dump(asdict(self.spec), f, indent=2, default=str)
```

**Estimated effort:** High (3-4 hours)

---

### 6. `ai_song_generator.py` - CLI Entry Point

```python
#!/usr/bin/env python3
"""
AI Song Scaffold Generator
Generate complete Ableton Live projects from natural language descriptions.

Usage:
    python ai_song_generator.py "uplifting trance in A minor at 138 BPM"
    python ai_song_generator.py --interactive
    python ai_song_generator.py --preset uplifting_trance
"""

import argparse
import sys
from pathlib import Path

from config import Config
from nl_parser import NLParser
from ableton_project import AbletonProject


def main():
    parser = argparse.ArgumentParser(
        description="Generate Ableton Live projects from natural language"
    )
    parser.add_argument(
        'prompt',
        nargs='?',
        help='Natural language description of the track'
    )
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Interactive mode with guided questions'
    )
    parser.add_argument(
        '--preset', '-p',
        choices=['uplifting_trance', 'dark_trance', 'progressive', 'radio_edit'],
        help='Use a preset configuration'
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        help='Output directory (default: configured template folder)'
    )
    parser.add_argument(
        '--open',
        action='store_true',
        help='Open generated project in Ableton'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be generated without creating files'
    )

    args = parser.parse_args()

    # Get prompt
    if args.interactive:
        prompt = interactive_mode()
    elif args.preset:
        prompt = get_preset(args.preset)
    elif args.prompt:
        prompt = args.prompt
    else:
        parser.print_help()
        sys.exit(1)

    # Parse prompt
    print(f"\n🎵 Parsing: {prompt}")
    nl_parser = NLParser()
    spec = nl_parser.parse(prompt)

    # Show what will be generated
    print(f"\n📋 Song Specification:")
    print(f"   Name: {spec.name}")
    print(f"   Genre: {spec.genre} / {spec.subgenre}")
    print(f"   Tempo: {spec.tempo} BPM")
    print(f"   Key: {spec.key} {spec.scale}")
    print(f"   Bars: {spec.total_bars} ({spec.duration_seconds/60:.1f} minutes)")
    print(f"\n   Structure:")
    for section in spec.structure:
        print(f"     - {section.name}: {section.bars} bars @ energy {section.energy}")

    if args.dry_run:
        print("\n✅ Dry run complete")
        return

    # Generate project
    print(f"\n🔨 Generating project...")
    config = Config()
    if args.output:
        config.OUTPUT_BASE = args.output

    project = AbletonProject(spec, config)
    als_path = project.generate()

    print(f"\n✅ Project generated!")
    print(f"   📁 {als_path.parent}")
    print(f"   📄 {als_path.name}")

    # Open in Ableton if requested
    if args.open:
        import subprocess
        print(f"\n🎹 Opening in Ableton Live...")
        subprocess.run([str(config.ABLETON_EXE), str(als_path)])


def interactive_mode() -> str:
    """Guided interactive prompting."""
    print("\n🎵 AI Song Generator - Interactive Mode\n")

    genre = input("Genre (trance/progressive/techno) [trance]: ").strip() or "trance"
    mood = input("Mood (uplifting/dark/emotional) [uplifting]: ").strip() or "uplifting"
    tempo = input("Tempo (BPM) [138]: ").strip() or "138"
    key = input("Key (e.g., A minor, F# minor) [A minor]: ").strip() or "A minor"
    extras = input("Any special requests? [none]: ").strip()

    prompt = f"{mood} {genre} in {key} at {tempo} BPM"
    if extras:
        prompt += f", {extras}"

    return prompt


def get_preset(preset: str) -> str:
    """Get prompt for preset configuration."""
    presets = {
        'uplifting_trance': 'uplifting trance in A minor at 138 BPM, euphoric with big breakdown',
        'dark_trance': 'dark driving trance in F# minor at 140 BPM, aggressive bassline',
        'progressive': 'progressive trance in D minor at 132 BPM, hypnotic long build',
        'radio_edit': 'radio edit trance in A minor at 138 BPM, short intro, punchy'
    }
    return presets.get(preset, presets['uplifting_trance'])


if __name__ == '__main__':
    main()
```

**Estimated effort:** Medium (1-2 hours)

---

### 7. `requirements.txt` - Dependencies

```
mido>=1.3.0
```

---

## Implementation Order

1. **`config.py`** - Remove hardcoded paths
2. **`song_spec.py`** - Data models
3. **`requirements.txt`** - Dependencies file
4. **`melody_generator.py`** - Pattern-based melodies
5. **Refactor `midi_generator.py`** - Use config, integrate with spec
6. **Refactor `song_generator.py`** - Use config, accept SongSpec
7. **`ableton_project.py`** - Project assembly
8. **`ai_song_generator.py`** - CLI entry point (Claude-invoked)
9. **Testing** - End-to-end validation

**Note:** NL parsing is handled by Claude directly, not by code.

---

## Success Criteria

Phase 1 MVP is complete when:

- [ ] `python ai_song_generator.py "uplifting trance in A minor"` works end-to-end
- [ ] Output includes .als file + midi/ folder
- [ ] All 7 tracks have MIDI patterns (kick, bass, chords, arp, lead, hats, clap)
- [ ] Lead track has pattern-based melody
- [ ] Project opens in Ableton Live without errors
- [ ] Arrangement markers match song structure
- [ ] No hardcoded paths in source code

---

## Notes

- The .als XML embedding is complex. Initial MVP may rely on MIDI files being drag-dropped, with .als providing structure/markers only.
- Pattern-based melody provides consistency; AI melody can be Phase 2.
- Focus on trance only for MVP; other genres are future expansion.
