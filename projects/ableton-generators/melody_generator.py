"""
Melody Generator - Production-Grade Wrapper

This module wraps the new melody-generation system to provide
backward compatibility with the existing ableton_project.py interface.

The new system provides:
- Chord-aware melody generation
- Motivic development across sections
- Phrase structure and cadences
- Inter-track coordination
- Humanization

Usage:
    # Same interface as before
    gen = MelodyGenerator(key="A", scale="minor", tempo=138)
    notes = gen.generate_for_section("drop", bars=16, energy=0.9)

    # New: chord-aware generation
    notes = gen.generate_for_section(
        "drop", bars=16, energy=0.9,
        chord_progression=["Am", "F", "C", "G"]
    )
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from mido import MidiFile, MidiTrack, Message

# Import the new production-grade system
try:
    from melody_generation import (
        LeadGenerator,
        ArpGenerator,
        Humanizer,
        HumanizeConfig,
        GrooveStyle,
        NoteEvent,
        Pitch,
        PitchClass,
        parse_progression,
        TrackContext,
        ArpStyle,
    )
    NEW_SYSTEM_AVAILABLE = True
except ImportError as e:
    warnings.warn(f"New melody generation system not available: {e}")
    NEW_SYSTEM_AVAILABLE = False


# =============================================================================
# LEGACY COMPATIBILITY - MelodyNote dataclass
# =============================================================================

@dataclass
class MelodyNote:
    """A single resolved note ready for MIDI output. Legacy interface."""
    pitch: int        # MIDI note number 0-127
    start: float      # Start time in beats (absolute, from bar 0)
    duration: float   # Duration in beats
    velocity: int     # Velocity 0-127


# =============================================================================
# MELODY GENERATOR - Wraps new system with legacy interface
# =============================================================================

class MelodyGenerator:
    """
    Production-grade melody generator with legacy interface compatibility.

    This wraps the new melody-generation system while maintaining
    backward compatibility with the existing codebase.

    New features available:
    - chord_progression parameter for chord-aware generation
    - variation parameter for controlling uniqueness
    - context parameter for inter-track coordination
    """

    def __init__(
        self,
        key: str = "A",
        scale: str = "minor",
        tempo: int = 138,
        config: Optional[Any] = None,  # Accept old Config object
    ):
        self.key = key
        self.scale = scale
        self.tempo = tempo
        self.config = config

        # Ticks per beat (for MIDI export)
        if config and hasattr(config, 'TICKS_PER_BEAT'):
            self.ticks_per_beat = config.TICKS_PER_BEAT
        else:
            self.ticks_per_beat = 480

        # Initialize new generators
        if NEW_SYSTEM_AVAILABLE:
            self._lead_gen = LeadGenerator(
                key=key,
                scale=scale,
                tempo=tempo,
                genre="trance",
            )
            self._arp_gen = ArpGenerator(key=key, scale=scale, tempo=tempo)
            self._humanizer = Humanizer()
        else:
            self._lead_gen = None
            self._arp_gen = None
            self._humanizer = None

        # Track state for coherence
        self._last_seed = None

    def generate(
        self,
        bars: int = 8,
        pattern: str = "anthem",
        energy: float = 1.0,
        variation: float = 0.2,
        octave_offset: int = 0,
        phrase_length: int = 4,
        seed: Optional[int] = None,
        chord_progression: Optional[List[str]] = None,
    ) -> List[MelodyNote]:
        """
        Generate melody notes.

        Args:
            bars: Number of bars to generate
            pattern: Pattern name (legacy, now maps to style)
            energy: Energy level 0-1
            variation: Variation amount 0-1
            octave_offset: Octave shift (legacy)
            phrase_length: Phrase length in bars
            seed: Random seed
            chord_progression: NEW - Chord symbols for chord-aware generation

        Returns:
            List of MelodyNote objects
        """
        if not NEW_SYSTEM_AVAILABLE:
            return self._fallback_generate(bars, energy, seed)

        # Generate with new system
        notes = self._lead_gen.generate_for_section(
            section_type="drop",  # Default to drop style
            bars=bars,
            energy=energy,
            chord_progression=chord_progression or ["Am", "F", "C", "G"],
            variation=variation,
        )

        # Humanize
        notes = self._humanizer.humanize(
            notes,
            HumanizeConfig(groove_style=GrooveStyle.TRANCE),
        )

        # Convert to legacy format
        return self._convert_to_legacy(notes)

    def generate_for_section(
        self,
        section_type: str,
        bars: int,
        energy: float,
        variation: float = 0.15,
        seed: Optional[int] = None,
        chord_progression: Optional[List[str]] = None,
        context: Optional[TrackContext] = None,
    ) -> List[MelodyNote]:
        """
        Generate melody for a specific section type.

        Args:
            section_type: Section type (intro, buildup, breakdown, drop, etc.)
            bars: Number of bars
            energy: Energy level 0-1
            variation: Variation amount
            seed: Random seed (legacy, new system uses time-based seeds)
            chord_progression: NEW - Chord symbols
            context: NEW - TrackContext with other track data

        Returns:
            List of MelodyNote objects
        """
        if not NEW_SYSTEM_AVAILABLE:
            return self._fallback_generate(bars, energy, seed)

        # Reinitialize with new seed if provided
        if seed is not None and seed != self._last_seed:
            self._lead_gen = LeadGenerator(
                key=self.key,
                scale=self.scale,
                tempo=self.tempo,
                genre="trance",
                seed=seed,
            )
            self._last_seed = seed

        # Generate with new system
        notes = self._lead_gen.generate_for_section(
            section_type=section_type.lower(),
            bars=bars,
            energy=energy,
            context=context,
            chord_progression=chord_progression,
            variation=variation,
        )

        # Humanize with section-appropriate groove
        groove = GrooveStyle.TRANCE if section_type in ["drop", "buildup"] else GrooveStyle.HUMAN
        notes = self._humanizer.humanize(
            notes,
            HumanizeConfig(
                groove_style=groove,
                timing_variance=0.02 if energy > 0.7 else 0.015,
            ),
        )

        # Convert to legacy format
        return self._convert_to_legacy(notes)

    def generate_procedural(
        self,
        bars: int = 8,
        section_type: str = "drop",
        energy: float = 1.0,
        octave_offset: int = 0,
        seed: Optional[int] = None,
        chord_progression: Optional[List[str]] = None,
    ) -> List[MelodyNote]:
        """
        Generate melody procedurally (different every time).

        This method now always produces unique results through
        the new system's motivic development engine.
        """
        return self.generate_for_section(
            section_type=section_type,
            bars=bars,
            energy=energy,
            variation=0.4,  # Higher variation for procedural
            seed=seed,
            chord_progression=chord_progression,
        )

    def _convert_to_legacy(self, notes: List[NoteEvent]) -> List[MelodyNote]:
        """Convert NoteEvent objects to legacy MelodyNote format."""
        return [
            MelodyNote(
                pitch=note.pitch.midi_note,
                start=note.actual_start,
                duration=note.duration_beats,
                velocity=note.velocity,
            )
            for note in notes
        ]

    def _fallback_generate(
        self,
        bars: int,
        energy: float,
        seed: Optional[int],
    ) -> List[MelodyNote]:
        """Fallback generation when new system unavailable."""
        warnings.warn("Using fallback generator - new system not available")
        import random

        rng = random.Random(seed)
        notes = []

        # Simple fallback: generate basic melody
        scale_intervals = [0, 2, 3, 5, 7, 8, 10]  # Minor scale
        root = {'C': 60, 'D': 62, 'E': 64, 'F': 65, 'G': 67, 'A': 69, 'B': 71}.get(self.key, 69)

        current_beat = 0.0
        while current_beat < bars * 4:
            degree = rng.choice(range(len(scale_intervals)))
            pitch = root + scale_intervals[degree]
            duration = rng.choice([0.5, 0.75, 1.0])
            velocity = int(70 + 50 * energy * rng.random())

            notes.append(MelodyNote(
                pitch=pitch,
                start=current_beat,
                duration=duration,
                velocity=min(127, max(40, velocity)),
            ))

            current_beat += duration + rng.choice([0, 0.25, 0.5])

        return notes

    def to_midi_track(
        self,
        notes: List[MelodyNote],
        ticks_per_beat: Optional[int] = None,
        program: Optional[int] = None,
    ) -> MidiTrack:
        """
        Convert notes to a mido MidiTrack.

        Handles overlapping notes on the same pitch.
        """
        tpb = ticks_per_beat or self.ticks_per_beat
        prog = program or 81  # Lead synth

        track = MidiTrack()
        track.append(Message("program_change", program=prog, time=0))

        if not notes:
            return track

        # Build on/off event list
        events = []
        for note in notes:
            on_tick = int(note.start * tpb)
            off_tick = int((note.start + note.duration) * tpb)
            events.append(("on", on_tick, note.pitch, note.velocity))
            events.append(("off", off_tick, note.pitch, 0))

        # Sort: by tick, note-off before note-on at same tick
        events.sort(key=lambda e: (e[1], 0 if e[0] == "off" else 1))

        # Emit MIDI messages with collision handling
        active: Dict[int, int] = {}
        current_tick = 0

        for event_type, tick, pitch, velocity in events:
            delta = tick - current_tick

            if event_type == "on":
                active[pitch] = active.get(pitch, 0) + 1
                track.append(Message("note_on", note=pitch, velocity=velocity, time=delta))
                current_tick = tick
            else:
                count = active.get(pitch, 0)
                if count > 1:
                    active[pitch] = count - 1
                else:
                    active[pitch] = 0
                    track.append(Message("note_off", note=pitch, velocity=0, time=delta))
                    current_tick = tick

        return track

    def to_midi_file(
        self,
        notes: List[MelodyNote],
        output_path: str,
        ticks_per_beat: Optional[int] = None,
    ) -> str:
        """Save notes to a MIDI file."""
        tpb = ticks_per_beat or self.ticks_per_beat
        mid = MidiFile(ticks_per_beat=tpb)
        mid.tracks.append(self.to_midi_track(notes, tpb))
        mid.save(output_path)
        return output_path


# =============================================================================
# ARP GENERATOR WRAPPER (Optional - for future integration)
# =============================================================================

class ArpGeneratorWrapper:
    """
    Wrapper for chord-aware arp generation.

    Use this to replace the basic arp generation in midi_generator.py.
    """

    def __init__(
        self,
        key: str = "A",
        scale: str = "minor",
        tempo: int = 138,
    ):
        self.key = key
        self.scale = scale
        self.tempo = tempo

        if NEW_SYSTEM_AVAILABLE:
            self._arp_gen = ArpGenerator(key=key, scale=scale, tempo=tempo)
            self._humanizer = Humanizer()
        else:
            self._arp_gen = None
            self._humanizer = None

    def generate_for_section(
        self,
        section_type: str,
        bars: int,
        energy: float,
        chord_progression: List[str],
        style: str = "trance",
    ) -> List[MelodyNote]:
        """Generate chord-aware arp for a section."""
        if not NEW_SYSTEM_AVAILABLE:
            return []

        # Parse chords
        from melody_generation import HarmonicEngine
        harmonic = HarmonicEngine(PitchClass.from_name(self.key), self.scale)
        chord_events = harmonic.parse_progression(
            chord_progression,
            bars_per_chord=bars / len(chord_progression),
        )

        # Map style string to ArpStyle enum
        style_map = {
            "trance": ArpStyle.TRANCE,
            "progressive": ArpStyle.PROGRESSIVE,
            "ambient": ArpStyle.AMBIENT,
            "techno": ArpStyle.TECHNO,
            "classic": ArpStyle.CLASSIC,
            "pluck": ArpStyle.PLUCK,
        }
        arp_style = style_map.get(style.lower(), ArpStyle.TRANCE)

        from melody_generation import ArpConfig
        config = ArpConfig(style=arp_style)

        # Generate
        notes = self._arp_gen.generate_for_section(
            section_type=section_type,
            bars=bars,
            energy=energy,
            chord_events=chord_events,
            config=config,
        )

        # Humanize
        notes = self._humanizer.humanize(
            notes,
            HumanizeConfig(groove_style=GrooveStyle.TRANCE, timing_variance=0.01),
        )

        # Convert to legacy format
        return [
            MelodyNote(
                pitch=note.pitch.midi_note,
                start=note.actual_start,
                duration=note.duration_beats,
                velocity=note.velocity,
            )
            for note in notes
        ]


# =============================================================================
# DEMO
# =============================================================================

def demo():
    """Demo the wrapped melody generator."""
    print("Melody Generator Demo (New System Wrapper)")
    print("=" * 50)

    gen = MelodyGenerator(key="A", scale="minor", tempo=138)

    # Test basic generation
    print("\n1. Basic generation (8 bars, drop):")
    notes = gen.generate(bars=8, energy=0.9)
    print(f"   Generated {len(notes)} notes")
    for note in notes[:5]:
        print(f"   pitch={note.pitch}, start={note.start:.2f}, "
              f"dur={note.duration:.2f}, vel={note.velocity}")

    # Test chord-aware generation
    print("\n2. Chord-aware generation:")
    notes = gen.generate_for_section(
        section_type="drop",
        bars=16,
        energy=0.95,
        chord_progression=["Am", "F", "C", "G"],
    )
    print(f"   Generated {len(notes)} notes (chord-aware)")

    # Test different sections
    print("\n3. Different section types:")
    for section in ["breakdown", "buildup", "drop"]:
        notes = gen.generate_for_section(section, bars=8, energy=0.7)
        print(f"   {section}: {len(notes)} notes")

    # Test MIDI export
    print("\n4. MIDI export:")
    track = gen.to_midi_track(notes)
    print(f"   Track has {len(track)} messages")

    print("\n" + "=" * 50)
    print("Demo complete.")
    print(f"New system available: {NEW_SYSTEM_AVAILABLE}")


if __name__ == "__main__":
    demo()
