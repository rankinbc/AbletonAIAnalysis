"""
Integration Layer

Connects the production-grade melody generation system to the
existing ableton-generators codebase.

Provides:
- MIDI export (NoteEvent → mido messages)
- Adapter for existing MelodyGenerator interface
- Track context builder from existing tracks
- Full generation pipeline
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

# Import mido for MIDI export
try:
    from mido import MidiFile, MidiTrack, Message
except ImportError:
    MidiFile = None
    MidiTrack = None
    Message = None
    print("Warning: mido not installed. MIDI export will not work.")

# Import our components
from .models import (
    NoteEvent, Pitch, PitchClass, ChordEvent, TrackContext,
    ArticulationType
)
from .harmonic_engine import HarmonicEngine, parse_progression
from .lead_generator import LeadGenerator
from .arp_generator import ArpGenerator, ArpStyle
from .humanizer import Humanizer, HumanizeConfig, GrooveStyle


# =============================================================================
# MIDI EXPORTER
# =============================================================================

class MIDIExporter:
    """
    Exports NoteEvent sequences to MIDI files.

    Handles:
    - Timing offset application
    - Velocity clamping
    - Note-off collision resolution
    - Multiple track export
    """

    def __init__(
        self,
        ticks_per_beat: int = 480,
        tempo: int = 138,
    ):
        self.ticks_per_beat = ticks_per_beat
        self.tempo = tempo

    def export_track(
        self,
        notes: List[NoteEvent],
        program: int = 81,  # Lead synth
        channel: int = 0,
    ) -> 'MidiTrack':
        """Export notes to a MidiTrack."""
        if MidiTrack is None:
            raise ImportError("mido is required for MIDI export")

        track = MidiTrack()

        # Add program change
        track.append(Message('program_change', program=program, channel=channel, time=0))

        if not notes:
            return track

        # Build event list (on/off) with actual start times
        events = []
        for note in notes:
            actual_start = note.actual_start
            on_tick = int(actual_start * self.ticks_per_beat)
            off_tick = int((actual_start + note.duration_beats) * self.ticks_per_beat)

            velocity = max(1, min(127, note.velocity))

            events.append(('on', on_tick, note.pitch.midi_note, velocity))
            events.append(('off', off_tick, note.pitch.midi_note, 0))

        # Sort events: by tick, then note-off before note-on
        events.sort(key=lambda e: (e[1], 0 if e[0] == 'off' else 1))

        # Track active notes for collision handling
        active: Dict[int, int] = {}
        current_tick = 0

        for event_type, tick, pitch, velocity in events:
            delta = max(0, tick - current_tick)

            if event_type == 'on':
                active[pitch] = active.get(pitch, 0) + 1
                track.append(Message(
                    'note_on',
                    note=pitch,
                    velocity=velocity,
                    channel=channel,
                    time=delta,
                ))
                current_tick = tick
            else:
                count = active.get(pitch, 0)
                if count > 1:
                    # Another note on same pitch still active
                    active[pitch] = count - 1
                else:
                    active[pitch] = 0
                    track.append(Message(
                        'note_off',
                        note=pitch,
                        velocity=0,
                        channel=channel,
                        time=delta,
                    ))
                    current_tick = tick

        return track

    def export_file(
        self,
        tracks: Dict[str, List[NoteEvent]],
        output_path: str,
        programs: Optional[Dict[str, int]] = None,
    ) -> str:
        """
        Export multiple tracks to a MIDI file.

        Args:
            tracks: Dict of track_name → notes
            output_path: Output file path
            programs: Optional dict of track_name → MIDI program number

        Returns:
            Path to created file
        """
        if MidiFile is None:
            raise ImportError("mido is required for MIDI export")

        if programs is None:
            programs = {
                'lead': 81,    # Lead 2 (sawtooth)
                'arp': 81,
                'bass': 38,    # Synth Bass 1
                'pad': 89,     # Pad 2 (warm)
            }

        midi = MidiFile(ticks_per_beat=self.ticks_per_beat)

        for i, (name, notes) in enumerate(tracks.items()):
            program = programs.get(name, 81)
            track = self.export_track(notes, program=program, channel=i % 16)
            midi.tracks.append(track)

        # Ensure directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        midi.save(output_path)
        return output_path


# =============================================================================
# LEGACY ADAPTER
# =============================================================================

@dataclass
class LegacyMelodyNote:
    """Adapter class matching original MelodyNote interface."""
    pitch: int
    start: float
    duration: float
    velocity: int


class LegacyAdapter:
    """
    Adapter that provides the same interface as the original MelodyGenerator.

    Use this as a drop-in replacement for the old generator.
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
        self._lead_gen = LeadGenerator(key, scale, tempo, "trance")
        self._arp_gen = ArpGenerator(key, scale, tempo)
        self._humanizer = Humanizer()

    def generate(
        self,
        bars: int = 8,
        pattern: str = "anthem",
        energy: float = 1.0,
        variation: float = 0.2,
        octave_offset: int = 0,
        phrase_length: int = 4,
        seed: Optional[int] = None,
    ) -> List[LegacyMelodyNote]:
        """Generate melody (legacy interface)."""
        notes = self._lead_gen.generate_for_section(
            section_type="drop",
            bars=bars,
            energy=energy,
            variation=variation,
        )

        # Humanize
        notes = self._humanizer.humanize(notes)

        # Convert to legacy format
        return [
            LegacyMelodyNote(
                pitch=n.pitch.midi_note,
                start=n.actual_start,
                duration=n.duration_beats,
                velocity=n.velocity,
            )
            for n in notes
        ]

    def generate_for_section(
        self,
        section_type: str,
        bars: int,
        energy: float,
        variation: float = 0.15,
        seed: Optional[int] = None,
    ) -> List[LegacyMelodyNote]:
        """Generate for section (legacy interface)."""
        notes = self._lead_gen.generate_for_section(
            section_type=section_type,
            bars=bars,
            energy=energy,
            variation=variation,
        )

        notes = self._humanizer.humanize(notes)

        return [
            LegacyMelodyNote(
                pitch=n.pitch.midi_note,
                start=n.actual_start,
                duration=n.duration_beats,
                velocity=n.velocity,
            )
            for n in notes
        ]


# =============================================================================
# FULL GENERATION PIPELINE
# =============================================================================

@dataclass
class GeneratedTrack:
    """Result of generating a single track."""
    name: str
    notes: List[NoteEvent]
    midi_notes: List[LegacyMelodyNote]


@dataclass
class GenerationResult:
    """Result of full generation pipeline."""
    lead: GeneratedTrack
    arp: GeneratedTrack
    chord_events: List[ChordEvent]
    midi_path: Optional[str] = None


class MelodyGenerationPipeline:
    """
    Full melody generation pipeline.

    Generates lead and arp tracks that work together,
    following a chord progression with proper coordination.
    """

    def __init__(
        self,
        key: str = "A",
        scale: str = "minor",
        tempo: int = 138,
        genre: str = "trance",
        output_dir: str = "output",
    ):
        self.key = key
        self.scale = scale
        self.tempo = tempo
        self.genre = genre
        self.output_dir = output_dir

        self.harmonic = HarmonicEngine(PitchClass.from_name(key), scale)
        self.lead_gen = LeadGenerator(key, scale, tempo, genre)
        self.arp_gen = ArpGenerator(key, scale, tempo)
        self.humanizer = Humanizer()
        self.exporter = MIDIExporter(tempo=tempo)

    def generate_section(
        self,
        section_type: str,
        bars: int,
        energy: float,
        chord_progression: Optional[List[str]] = None,
        export_midi: bool = True,
    ) -> GenerationResult:
        """
        Generate all tracks for a section.

        Args:
            section_type: Type of section (drop, breakdown, etc.)
            bars: Number of bars
            energy: Energy level 0-1
            chord_progression: Chord symbols (default: Am, F, C, G)
            export_midi: Whether to export MIDI file

        Returns:
            GenerationResult with all tracks
        """
        # Parse chords
        if chord_progression is None:
            chord_progression = ["Am", "F", "C", "G"]

        bars_per_chord = bars / len(chord_progression)
        chord_events = self.harmonic.parse_progression(chord_progression, bars_per_chord)

        # Create track context (initially just chords)
        context = TrackContext(chord_events=chord_events)

        # Generate arp first (lead will coordinate with it)
        arp_style = {
            "intro": ArpStyle.AMBIENT,
            "buildup": ArpStyle.TRANCE,
            "breakdown": ArpStyle.PROGRESSIVE,
            "drop": ArpStyle.TRANCE,
            "break": ArpStyle.CLASSIC,
            "outro": ArpStyle.AMBIENT,
        }.get(section_type, ArpStyle.TRANCE)

        arp_notes = self.arp_gen.generate_for_section(
            section_type=section_type,
            bars=bars,
            energy=energy,
            chord_events=chord_events,
        )

        # Add arp to context so lead can coordinate
        context.arp_notes = arp_notes

        # Generate lead
        lead_notes = self.lead_gen.generate_for_section(
            section_type=section_type,
            bars=bars,
            energy=energy,
            context=context,
        )

        # Humanize both
        groove = GrooveStyle.TRANCE if self.genre == "trance" else GrooveStyle.HUMAN
        lead_notes = self.humanizer.humanize(
            lead_notes,
            HumanizeConfig(groove_style=groove),
        )
        arp_notes = self.humanizer.humanize(
            arp_notes,
            HumanizeConfig(groove_style=groove, timing_variance=0.01),
        )

        # Convert to legacy format
        lead_legacy = [
            LegacyMelodyNote(n.pitch.midi_note, n.actual_start, n.duration_beats, n.velocity)
            for n in lead_notes
        ]
        arp_legacy = [
            LegacyMelodyNote(n.pitch.midi_note, n.actual_start, n.duration_beats, n.velocity)
            for n in arp_notes
        ]

        result = GenerationResult(
            lead=GeneratedTrack("lead", lead_notes, lead_legacy),
            arp=GeneratedTrack("arp", arp_notes, arp_legacy),
            chord_events=chord_events,
        )

        # Export MIDI if requested
        if export_midi:
            filename = f"{section_type}_{bars}bars_{self.key}{self.scale}.mid"
            midi_path = os.path.join(self.output_dir, filename)

            self.exporter.export_file(
                {"lead": lead_notes, "arp": arp_notes},
                midi_path,
            )
            result.midi_path = midi_path

        return result

    def generate_full_song(
        self,
        structure: List[Tuple[str, int, float]],  # (section_type, bars, energy)
        chord_progression: Optional[List[str]] = None,
        export_midi: bool = True,
    ) -> Dict[str, GenerationResult]:
        """
        Generate full song with multiple sections.

        Args:
            structure: List of (section_type, bars, energy) tuples
            chord_progression: Chord symbols to use throughout
            export_midi: Whether to export MIDI

        Returns:
            Dict of section_name → GenerationResult
        """
        results = {}

        for i, (section_type, bars, energy) in enumerate(structure):
            section_name = f"{i+1}_{section_type}"
            results[section_name] = self.generate_section(
                section_type=section_type,
                bars=bars,
                energy=energy,
                chord_progression=chord_progression,
                export_midi=export_midi,
            )

        return results


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def generate_melody(
    section_type: str = "drop",
    bars: int = 16,
    energy: float = 0.8,
    key: str = "A",
    scale: str = "minor",
    chord_progression: Optional[List[str]] = None,
    genre: str = "trance",
    humanize: bool = True,
) -> List[LegacyMelodyNote]:
    """
    Quick function to generate a melody.

    Returns notes in the legacy format for easy integration.
    """
    pipeline = MelodyGenerationPipeline(key, scale, 138, genre)
    result = pipeline.generate_section(
        section_type=section_type,
        bars=bars,
        energy=energy,
        chord_progression=chord_progression,
        export_midi=False,
    )
    return result.lead.midi_notes


def generate_arp(
    section_type: str = "drop",
    bars: int = 16,
    energy: float = 0.8,
    key: str = "A",
    scale: str = "minor",
    chord_progression: Optional[List[str]] = None,
    style: str = "trance",
) -> List[LegacyMelodyNote]:
    """Quick function to generate an arp."""
    pipeline = MelodyGenerationPipeline(key, scale, 138, style)
    result = pipeline.generate_section(
        section_type=section_type,
        bars=bars,
        energy=energy,
        chord_progression=chord_progression,
        export_midi=False,
    )
    return result.arp.midi_notes


# =============================================================================
# DEMO
# =============================================================================

def demo():
    """Demonstrate integration capabilities."""
    print("Integration Demo")
    print("=" * 50)

    # Test legacy adapter
    print("\n1. Legacy Adapter (drop-in replacement):")
    adapter = LegacyAdapter(key="A", scale="minor")
    legacy_notes = adapter.generate(bars=8, energy=0.9)
    print(f"   Generated {len(legacy_notes)} notes")
    for note in legacy_notes[:3]:
        print(f"   pitch={note.pitch}, start={note.start:.2f}, "
              f"dur={note.duration:.2f}, vel={note.velocity}")

    # Test full pipeline
    print("\n2. Full Pipeline (with coordination):")
    pipeline = MelodyGenerationPipeline(
        key="A",
        scale="minor",
        genre="trance",
        output_dir="output/integration_demo",
    )

    result = pipeline.generate_section(
        section_type="drop",
        bars=16,
        energy=0.9,
        chord_progression=["Am", "F", "C", "G"],
        export_midi=True,
    )

    print(f"   Lead: {len(result.lead.notes)} notes")
    print(f"   Arp: {len(result.arp.notes)} notes")
    print(f"   Chords: {len(result.chord_events)} changes")
    if result.midi_path:
        print(f"   MIDI exported to: {result.midi_path}")

    # Test full song
    print("\n3. Full Song Generation:")
    song_structure = [
        ("intro", 8, 0.4),
        ("buildup", 8, 0.7),
        ("drop", 16, 0.95),
        ("breakdown", 8, 0.5),
        ("buildup", 8, 0.8),
        ("drop", 16, 1.0),
        ("outro", 8, 0.3),
    ]

    song = pipeline.generate_full_song(
        structure=song_structure,
        chord_progression=["Am", "F", "C", "G"],
        export_midi=True,
    )

    print(f"   Generated {len(song)} sections:")
    total_lead = 0
    total_arp = 0
    for name, res in song.items():
        total_lead += len(res.lead.notes)
        total_arp += len(res.arp.notes)
        print(f"     {name}: lead={len(res.lead.notes)}, arp={len(res.arp.notes)}")

    print(f"   Total: {total_lead} lead notes, {total_arp} arp notes")

    print("\n" + "=" * 50)
    print("Demo complete.")


if __name__ == "__main__":
    demo()
