"""
Chord-Aware Arpeggio Generator

Production-grade arpeggio generation that:
- Follows chord changes automatically
- Varies patterns intelligently
- Creates interesting rhythmic variations
- Manages velocity for groove
- Supports multiple arp styles (up, down, random, pattern-based)
"""

from __future__ import annotations

import random
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable
from enum import Enum, auto

from .models import (
    NoteEvent, Pitch, PitchClass, Chord, ChordEvent,
    TrackContext, TensionLevel, ArticulationType
)
from .harmonic_engine import HarmonicEngine


# =============================================================================
# ARP PATTERNS
# =============================================================================

class ArpDirection(Enum):
    """Arpeggio direction."""
    UP = auto()
    DOWN = auto()
    UP_DOWN = auto()
    DOWN_UP = auto()
    RANDOM = auto()
    PATTERN = auto()


class ArpStyle(Enum):
    """Arpeggio style presets."""
    CLASSIC = auto()      # Simple up/down
    TRANCE = auto()       # 16th notes with octave jumps
    PROGRESSIVE = auto()  # Evolving patterns
    PLUCK = auto()        # Short staccato notes
    AMBIENT = auto()       # Sparse, long notes
    TECHNO = auto()        # Rhythmic, syncopated


# Pre-defined arp patterns (scale degree offsets within chord)
# Each pattern is a list of (chord_tone_index, octave_offset, duration_factor, velocity_factor)
ARP_PATTERNS: Dict[str, List[Tuple[int, int, float, float]]] = {
    # Classic trance: 0-2-4-7-0-4-2-7 (using chord tone indices)
    "trance_classic": [
        (0, 0, 1.0, 0.9),   # Root
        (1, 0, 1.0, 0.75),  # 3rd
        (2, 0, 1.0, 0.85),  # 5th
        (0, 1, 1.0, 1.0),   # Root+octave
        (0, 0, 1.0, 0.9),   # Root
        (2, 0, 1.0, 0.85),  # 5th
        (1, 0, 1.0, 0.75),  # 3rd
        (0, 1, 1.0, 1.0),   # Root+octave
    ],

    # Uplifting trance pattern
    "trance_uplifting": [
        (0, 0, 1.0, 0.85),
        (1, 0, 1.0, 0.7),
        (2, 0, 1.0, 0.8),
        (0, 1, 1.0, 0.95),
        (2, 0, 1.0, 0.8),
        (1, 0, 1.0, 0.7),
        (0, 0, 1.0, 0.85),
        (2, 0, 1.0, 0.9),
    ],

    # Progressive house
    "progressive": [
        (0, 0, 2.0, 0.8),
        (1, 0, 1.0, 0.7),
        (2, 0, 1.0, 0.75),
        (0, 0, 2.0, 0.8),
        (2, 0, 1.0, 0.75),
        (1, 0, 1.0, 0.7),
    ],

    # Minimal techno
    "techno_minimal": [
        (0, 0, 0.5, 1.0),
        (0, 0, 0.5, 0.0),  # Rest (velocity 0)
        (0, 0, 0.5, 0.8),
        (2, 0, 0.5, 0.9),
    ],

    # Ambient sparse
    "ambient": [
        (0, 0, 4.0, 0.6),
        (2, 0, 4.0, 0.55),
        (1, 0, 4.0, 0.5),
        (0, 1, 4.0, 0.65),
    ],

    # Simple up
    "up_simple": [
        (0, 0, 1.0, 0.9),
        (1, 0, 1.0, 0.8),
        (2, 0, 1.0, 0.85),
        (0, 1, 1.0, 0.95),
    ],

    # Simple down
    "down_simple": [
        (0, 1, 1.0, 0.95),
        (2, 0, 1.0, 0.85),
        (1, 0, 1.0, 0.8),
        (0, 0, 1.0, 0.9),
    ],

    # Rhythmic syncopated
    "syncopated": [
        (0, 0, 1.5, 0.9),
        (1, 0, 0.5, 0.75),
        (2, 0, 1.0, 0.85),
        (0, 1, 0.5, 1.0),
        (2, 0, 0.5, 0.8),
    ],

    # Broken chord
    "broken": [
        (0, 0, 1.0, 0.85),
        (2, 0, 0.5, 0.8),
        (1, 0, 0.5, 0.75),
        (2, 0, 1.0, 0.85),
        (0, 0, 0.5, 0.8),
        (1, 0, 0.5, 0.75),
    ],
}

# Style to pattern mapping
STYLE_PATTERNS: Dict[ArpStyle, List[str]] = {
    ArpStyle.CLASSIC: ["up_simple", "down_simple", "broken"],
    ArpStyle.TRANCE: ["trance_classic", "trance_uplifting"],
    ArpStyle.PROGRESSIVE: ["progressive", "broken"],
    ArpStyle.PLUCK: ["syncopated", "techno_minimal"],
    ArpStyle.AMBIENT: ["ambient", "progressive"],
    ArpStyle.TECHNO: ["techno_minimal", "syncopated"],
}


# =============================================================================
# ARP GENERATOR
# =============================================================================

@dataclass
class ArpConfig:
    """Configuration for arp generation."""
    style: ArpStyle = ArpStyle.TRANCE
    direction: ArpDirection = ArpDirection.PATTERN
    note_length: float = 0.25  # Base note length in beats (16th notes)
    gate: float = 0.8  # Gate percentage (0-1)
    octave_range: int = 2  # How many octaves to span
    velocity_base: int = 90
    velocity_variation: float = 0.2
    humanize_timing: float = 0.02
    pattern_variation: float = 0.1


class ArpGenerator:
    """
    Production-grade arpeggio generator.

    Features:
    - Automatically follows chord changes
    - Multiple arp styles and patterns
    - Velocity shaping for groove
    - Pattern variation to avoid monotony
    - Register management
    """

    def __init__(
        self,
        key: str = "A",
        scale: str = "minor",
        tempo: int = 138,
        seed: Optional[int] = None,
    ):
        self.key = PitchClass.from_name(key)
        self.scale = scale
        self.tempo = tempo
        self.rng = random.Random(seed)

        self.harmonic = HarmonicEngine(self.key, scale)
        self.register = (48, 79)  # C3 to G5

    def generate_for_section(
        self,
        section_type: str,
        bars: int,
        energy: float,
        chord_events: List[ChordEvent],
        config: Optional[ArpConfig] = None,
    ) -> List[NoteEvent]:
        """
        Generate arpeggio for a section.

        Args:
            section_type: Type of section
            bars: Number of bars
            energy: Energy level 0-1
            chord_events: Chord progression with timing
            config: Optional arp configuration

        Returns:
            List of NoteEvent objects
        """
        if config is None:
            config = self._config_for_section(section_type, energy)

        notes = []
        total_beats = bars * 4

        for chord_event in chord_events:
            if chord_event.start_beat >= total_beats:
                break

            chord_notes = self._generate_for_chord(
                chord_event=chord_event,
                config=config,
                energy=energy,
                max_beat=min(chord_event.end_beat, total_beats),
            )
            notes.extend(chord_notes)

        return notes

    def _config_for_section(
        self,
        section_type: str,
        energy: float,
    ) -> ArpConfig:
        """Get appropriate arp config for section type."""
        section_configs = {
            "intro": ArpConfig(
                style=ArpStyle.AMBIENT,
                note_length=0.5,
                gate=0.9,
                velocity_base=70,
            ),
            "buildup": ArpConfig(
                style=ArpStyle.TRANCE,
                note_length=0.25,
                gate=0.75,
                velocity_base=85,
            ),
            "breakdown": ArpConfig(
                style=ArpStyle.PROGRESSIVE,
                note_length=0.5,
                gate=0.85,
                velocity_base=70,
            ),
            "drop": ArpConfig(
                style=ArpStyle.TRANCE,
                note_length=0.25,
                gate=0.7,
                velocity_base=95,
            ),
            "break": ArpConfig(
                style=ArpStyle.CLASSIC,
                note_length=0.25,
                gate=0.75,
                velocity_base=80,
            ),
            "outro": ArpConfig(
                style=ArpStyle.AMBIENT,
                note_length=0.5,
                gate=0.9,
                velocity_base=65,
            ),
        }

        config = section_configs.get(section_type, ArpConfig())

        # Adjust based on energy
        config.velocity_base = int(config.velocity_base * (0.7 + 0.3 * energy))

        return config

    def _generate_for_chord(
        self,
        chord_event: ChordEvent,
        config: ArpConfig,
        energy: float,
        max_beat: float,
    ) -> List[NoteEvent]:
        """Generate arp notes for a single chord."""
        notes = []

        # Get chord tones in register
        chord_tones = self.harmonic.get_chord_tones_in_register(
            chord_event.chord,
            self.register[0],
            self.register[1],
        )

        if not chord_tones:
            return notes

        # Select pattern
        pattern = self._select_pattern(config)

        current_beat = chord_event.start_beat
        pattern_idx = 0
        pattern_len = len(pattern)

        while current_beat < max_beat:
            # Get pattern step
            step = pattern[pattern_idx % pattern_len]
            chord_idx, octave_offset, dur_factor, vel_factor = step

            # Skip rests (velocity 0)
            if vel_factor <= 0:
                current_beat += config.note_length * dur_factor
                pattern_idx += 1
                continue

            # Get pitch from chord tones
            base_tone_idx = chord_idx % len(chord_tones)
            base_pitch = chord_tones[base_tone_idx]

            # Apply octave offset
            final_midi = base_pitch.midi_note + (octave_offset * 12)

            # Keep in register
            while final_midi < self.register[0]:
                final_midi += 12
            while final_midi > self.register[1]:
                final_midi -= 12

            # Calculate velocity with groove
            beat_in_bar = current_beat % 4
            groove_accent = 1.0
            if beat_in_bar < 0.1:  # Beat 1
                groove_accent = 1.1
            elif abs(beat_in_bar - 2) < 0.1:  # Beat 3
                groove_accent = 1.05

            velocity = int(
                config.velocity_base *
                vel_factor *
                groove_accent *
                (1 + self.rng.uniform(-config.velocity_variation, config.velocity_variation))
            )
            velocity = max(40, min(127, velocity))

            # Calculate duration
            duration = config.note_length * dur_factor * config.gate

            # Apply variation occasionally
            if self.rng.random() < config.pattern_variation:
                # Slight timing adjustment
                timing_offset = self.rng.uniform(-config.humanize_timing, config.humanize_timing)
            else:
                timing_offset = 0

            notes.append(NoteEvent(
                pitch=Pitch.from_midi(final_midi),
                start_beat=current_beat,
                duration_beats=duration,
                velocity=velocity,
                articulation=ArticulationType.STACCATO if config.gate < 0.7 else ArticulationType.LEGATO,
                timing_offset=timing_offset,
                chord_tone=True,
            ))

            current_beat += config.note_length * dur_factor
            pattern_idx += 1

        return notes

    def _select_pattern(
        self,
        config: ArpConfig,
    ) -> List[Tuple[int, int, float, float]]:
        """Select appropriate pattern based on config."""
        style_patterns = STYLE_PATTERNS.get(config.style, ["trance_classic"])
        pattern_name = self.rng.choice(style_patterns)
        return ARP_PATTERNS.get(pattern_name, ARP_PATTERNS["trance_classic"])

    def generate_evolving(
        self,
        bars: int,
        chord_events: List[ChordEvent],
        start_style: ArpStyle,
        end_style: ArpStyle,
        start_energy: float = 0.5,
        end_energy: float = 1.0,
    ) -> List[NoteEvent]:
        """
        Generate evolving arp that transitions between styles.

        Useful for buildups where arp intensifies.
        """
        notes = []
        total_beats = bars * 4

        # Get patterns for start and end
        start_patterns = STYLE_PATTERNS.get(start_style, ["up_simple"])
        end_patterns = STYLE_PATTERNS.get(end_style, ["trance_classic"])

        for chord_event in chord_events:
            if chord_event.start_beat >= total_beats:
                break

            # Calculate progress through section
            progress = chord_event.start_beat / total_beats

            # Interpolate energy
            current_energy = start_energy + (end_energy - start_energy) * progress

            # Select pattern based on progress
            if progress < 0.5:
                pattern_name = self.rng.choice(start_patterns)
            else:
                pattern_name = self.rng.choice(end_patterns)

            pattern = ARP_PATTERNS.get(pattern_name, ARP_PATTERNS["up_simple"])

            # Adjust note length (faster as we progress)
            note_length = 0.5 - (0.25 * progress)  # 8ths to 16ths

            config = ArpConfig(
                note_length=max(0.25, note_length),
                gate=0.7 + 0.2 * progress,
                velocity_base=int(70 + 50 * current_energy),
            )

            chord_notes = self._generate_for_chord(
                chord_event=chord_event,
                config=config,
                energy=current_energy,
                max_beat=min(chord_event.end_beat, total_beats),
            )

            # Override with specific pattern
            for note in chord_notes:
                notes.append(note)

        return notes


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def generate_arp(
    bars: int = 8,
    chord_progression: List[str] = None,
    key: str = "A",
    scale: str = "minor",
    style: ArpStyle = ArpStyle.TRANCE,
    energy: float = 0.8,
    seed: Optional[int] = None,
) -> List[NoteEvent]:
    """
    Quick function to generate arpeggio.

    Args:
        bars: Number of bars
        chord_progression: Chord symbols
        key: Musical key
        scale: Scale type
        style: Arp style
        energy: Energy level 0-1
        seed: Random seed

    Returns:
        List of NoteEvent objects
    """
    if chord_progression is None:
        chord_progression = ["Am", "F", "C", "G"]

    generator = ArpGenerator(key=key, scale=scale, seed=seed)

    # Parse chords
    harmonic = HarmonicEngine(PitchClass.from_name(key), scale)
    chord_events = harmonic.parse_progression(
        chord_progression,
        bars_per_chord=bars / len(chord_progression),
    )

    config = ArpConfig(style=style)

    return generator.generate_for_section(
        section_type="drop",
        bars=bars,
        energy=energy,
        chord_events=chord_events,
        config=config,
    )


# =============================================================================
# DEMO
# =============================================================================

def demo():
    """Demonstrate arp generator capabilities."""
    print("Arp Generator Demo")
    print("=" * 50)

    generator = ArpGenerator(key="A", scale="minor", seed=42)
    harmonic = HarmonicEngine(PitchClass.from_name("A"), "minor")

    chord_prog = ["Am", "F", "C", "G"]
    chord_events = harmonic.parse_progression(chord_prog, bars_per_chord=2.0)

    # Test different styles
    styles = [
        (ArpStyle.TRANCE, "drop", 0.9),
        (ArpStyle.PROGRESSIVE, "breakdown", 0.5),
        (ArpStyle.AMBIENT, "intro", 0.4),
    ]

    for style, section, energy in styles:
        print(f"\n{style.name} style ({section}, energy {energy}):")

        config = ArpConfig(style=style)
        notes = generator.generate_for_section(
            section_type=section,
            bars=8,
            energy=energy,
            chord_events=chord_events,
            config=config,
        )

        print(f"  Generated {len(notes)} notes")

        # Show pattern info
        unique_pitches = set(n.pitch.midi_note for n in notes)
        print(f"  Unique pitches: {len(unique_pitches)}")
        print(f"  Pitch range: {min(unique_pitches)} - {max(unique_pitches)}")

        # Show first few notes
        for note in notes[:6]:
            print(f"    Beat {note.start_beat:5.2f}: {note.pitch.to_name():4} "
                  f"dur={note.duration_beats:.2f} vel={note.velocity:3}")
        if len(notes) > 6:
            print(f"    ... and {len(notes) - 6} more")

    # Test evolving arp (buildup)
    print("\n\nEVOLVING ARP (buildup simulation):")
    evolving = generator.generate_evolving(
        bars=8,
        chord_events=chord_events,
        start_style=ArpStyle.PROGRESSIVE,
        end_style=ArpStyle.TRANCE,
        start_energy=0.4,
        end_energy=1.0,
    )
    print(f"  Generated {len(evolving)} notes")

    # Show density increase
    first_bar = [n for n in evolving if n.start_beat < 4]
    last_bar = [n for n in evolving if n.start_beat >= 28]
    print(f"  First bar density: {len(first_bar)} notes")
    print(f"  Last bar density: {len(last_bar)} notes")

    print("\n" + "=" * 50)
    print("Demo complete.")


if __name__ == "__main__":
    demo()
