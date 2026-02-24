"""
Pattern-based melody generator for trance music.
Generates melodies using pre-defined patterns with variations.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import random
from mido import MidiFile, MidiTrack, Message

from config import Config, DEFAULT_CONFIG


@dataclass
class MelodyNote:
    """A single note in a melody."""
    pitch: int       # MIDI note number (0-127)
    start: float     # Start time in beats
    duration: float  # Duration in beats
    velocity: int    # Velocity (0-127)


class MelodyGenerator:
    """Pattern-based trance melody generator."""

    # Scale intervals from root note
    SCALES = {
        "minor": [0, 2, 3, 5, 7, 8, 10],
        "major": [0, 2, 4, 5, 7, 9, 11],
        "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
        "melodic_minor": [0, 2, 3, 5, 7, 9, 11],
        "dorian": [0, 2, 3, 5, 7, 9, 10],
        "phrygian": [0, 1, 3, 5, 7, 8, 10],
    }

    # Note name to semitone offset
    NOTE_MAP = {
        "C": 0, "C#": 1, "Db": 1,
        "D": 2, "D#": 3, "Eb": 3,
        "E": 4,
        "F": 5, "F#": 6, "Gb": 6,
        "G": 7, "G#": 8, "Ab": 8,
        "A": 9, "A#": 10, "Bb": 10,
        "B": 11,
    }

    # Trance melody patterns
    # Format: list of (scale_degree, beat_offset, duration, velocity_multiplier)
    PATTERNS = {
        "anthem": [
            # Classic uplifting trance hook - memorable and singable
            (0, 0.0, 0.5, 1.0),
            (2, 0.5, 0.5, 0.9),
            (4, 1.0, 1.0, 1.0),
            (3, 2.0, 0.5, 0.85),
            (2, 2.5, 0.5, 0.9),
            (0, 3.0, 1.0, 1.0),
        ],
        "anthem_b": [
            # Variation - ascending resolution
            (0, 0.0, 0.5, 0.9),
            (2, 0.5, 0.5, 0.9),
            (3, 1.0, 0.5, 0.95),
            (4, 1.5, 1.5, 1.0),
            (5, 3.0, 1.0, 0.95),
        ],
        "call_response": [
            # Call phrase (bars 1-2)
            (4, 0.0, 0.5, 1.0),
            (3, 0.5, 0.5, 0.9),
            (2, 1.0, 0.5, 0.85),
            (0, 1.5, 0.5, 0.9),
            # Rest
            # Response phrase (bars 2-4)
            (2, 4.0, 0.5, 0.9),
            (3, 4.5, 0.5, 0.9),
            (4, 5.0, 1.0, 1.0),
            (5, 6.0, 2.0, 1.0),  # Climax note held
        ],
        "driving": [
            # 16th note driven pattern - energetic
            (0, 0.0, 0.25, 0.9),
            (0, 0.25, 0.25, 0.7),
            (2, 0.5, 0.25, 0.9),
            (2, 0.75, 0.25, 0.7),
            (3, 1.0, 0.25, 1.0),
            (2, 1.25, 0.25, 0.8),
            (0, 1.5, 0.5, 0.9),
        ],
        "driving_b": [
            # Driving variation with octave jump
            (0, 0.0, 0.25, 0.85),
            (2, 0.25, 0.25, 0.85),
            (4, 0.5, 0.25, 0.9),
            (7, 0.75, 0.25, 1.0),  # Octave
            (4, 1.0, 0.25, 0.9),
            (2, 1.25, 0.25, 0.85),
            (0, 1.5, 0.5, 0.85),
        ],
        "emotional": [
            # Longer notes, bigger intervals - breakdown style
            (0, 0.0, 2.0, 1.0),
            (4, 2.0, 2.0, 0.9),
            (5, 4.0, 1.0, 1.0),
            (4, 5.0, 1.0, 0.9),
            (2, 6.0, 2.0, 0.85),
        ],
        "emotional_b": [
            # Emotional variation - descending
            (5, 0.0, 1.5, 1.0),
            (4, 1.5, 1.5, 0.95),
            (2, 3.0, 1.0, 0.9),
            (0, 4.0, 2.0, 0.85),
            (-1, 6.0, 2.0, 0.8),  # Below root
        ],
        "arp_melody": [
            # Arpeggio-style melodic pattern
            (0, 0.0, 0.25, 0.8),
            (2, 0.25, 0.25, 0.8),
            (4, 0.5, 0.25, 0.9),
            (7, 0.75, 0.25, 1.0),
            (4, 1.0, 0.25, 0.9),
            (2, 1.25, 0.25, 0.8),
            (0, 1.5, 0.5, 0.85),
        ],
        "sustained": [
            # Long held notes - pad-like melody
            (0, 0.0, 4.0, 0.9),
            (4, 4.0, 4.0, 0.95),
        ],
        "staccato": [
            # Short punchy notes
            (0, 0.0, 0.125, 1.0),
            (0, 0.5, 0.125, 0.8),
            (2, 1.0, 0.125, 1.0),
            (2, 1.5, 0.125, 0.8),
            (4, 2.0, 0.125, 1.0),
            (4, 2.5, 0.125, 0.8),
            (5, 3.0, 0.125, 1.0),
            (5, 3.5, 0.125, 0.8),
        ],
        "climax": [
            # Building to a climax note
            (0, 0.0, 0.5, 0.7),
            (2, 0.5, 0.5, 0.75),
            (3, 1.0, 0.5, 0.8),
            (4, 1.5, 0.5, 0.85),
            (5, 2.0, 0.5, 0.9),
            (6, 2.5, 0.5, 0.95),
            (7, 3.0, 1.0, 1.0),  # Climax!
        ],
    }

    # Section type to pattern mapping
    SECTION_PATTERNS = {
        "intro": ["arp_melody", "sustained"],
        "buildup": ["driving", "driving_b", "staccato"],
        "breakdown": ["emotional", "emotional_b", "sustained"],
        "drop": ["anthem", "anthem_b", "call_response"],
        "break": ["driving", "arp_melody"],
        "outro": ["arp_melody", "sustained", "emotional"],
    }

    def __init__(
        self,
        key: str = "A",
        scale: str = "minor",
        tempo: int = 138,
        config: Config = None
    ):
        self.key = key
        self.scale = scale
        self.tempo = tempo
        self.config = config or DEFAULT_CONFIG
        self.root = self._note_to_midi(key, octave=4)
        self.scale_intervals = self.SCALES.get(scale, self.SCALES["minor"])

    def _note_to_midi(self, note: str, octave: int = 4) -> int:
        """Convert note name to MIDI number."""
        # Handle flats/sharps
        if len(note) > 1:
            base_note = note[0].upper()
            modifier = note[1:]
            semitone = self.NOTE_MAP.get(base_note, 9)  # Default to A
            if "#" in modifier:
                semitone += 1
            elif "b" in modifier:
                semitone -= 1
        else:
            semitone = self.NOTE_MAP.get(note.upper(), 9)

        return semitone + (octave + 1) * 12

    def _degree_to_midi(self, degree: int, octave_offset: int = 0) -> int:
        """Convert scale degree to MIDI note number."""
        # Handle negative degrees (below root)
        octave_shift = 0
        while degree < 0:
            degree += len(self.scale_intervals)
            octave_shift -= 1
        while degree >= len(self.scale_intervals):
            degree -= len(self.scale_intervals)
            octave_shift += 1

        interval = self.scale_intervals[degree]
        return self.root + interval + ((octave_shift + octave_offset) * 12)

    def generate(
        self,
        bars: int = 8,
        pattern: str = "anthem",
        energy: float = 1.0,
        variation: float = 0.2,
        octave_offset: int = 0,
        seed: Optional[int] = None
    ) -> List[MelodyNote]:
        """
        Generate melody for specified number of bars.

        Args:
            bars: Number of bars to generate
            pattern: Pattern name from PATTERNS dict
            energy: Energy level (0.0-1.0) affects velocity
            variation: Amount of random variation (0.0-1.0)
            octave_offset: Shift the melody up/down octaves
            seed: Random seed for reproducibility

        Returns:
            List of MelodyNote objects
        """
        if seed is not None:
            random.seed(seed)

        if pattern not in self.PATTERNS:
            pattern = "anthem"

        base_pattern = self.PATTERNS[pattern]

        # Calculate pattern length in beats
        pattern_length = max(note[1] + note[2] for note in base_pattern)
        pattern_bars = int(pattern_length / 4) + 1

        notes = []
        current_bar = 0

        while current_bar < bars:
            for degree, offset, duration, vel_mult in base_pattern:
                beat = current_bar * 4 + offset

                if beat >= bars * 4:
                    break

                # Apply variation to degree
                actual_degree = degree
                if variation > 0 and random.random() < variation:
                    # Slight pitch variation (stay in scale)
                    actual_degree += random.choice([-1, 0, 1])

                # Calculate pitch
                pitch = self._degree_to_midi(actual_degree, octave_offset)

                # Ensure valid MIDI range
                pitch = max(0, min(127, pitch))

                # Apply energy to velocity
                base_velocity = 100
                velocity = int(base_velocity * vel_mult * (0.5 + 0.5 * energy))
                velocity = max(40, min(127, velocity))

                # Apply slight velocity variation
                if variation > 0:
                    velocity += random.randint(-5, 5)
                    velocity = max(40, min(127, velocity))

                notes.append(MelodyNote(
                    pitch=pitch,
                    start=beat,
                    duration=duration,
                    velocity=velocity
                ))

            current_bar += pattern_bars

        return notes

    def generate_for_section(
        self,
        section_type: str,
        bars: int,
        energy: float,
        variation: float = 0.15,
        seed: Optional[int] = None
    ) -> List[MelodyNote]:
        """
        Generate appropriate melody for a section type.

        Args:
            section_type: Type of section (intro, breakdown, drop, etc.)
            bars: Number of bars
            energy: Energy level (0.0-1.0)
            variation: Amount of variation
            seed: Random seed

        Returns:
            List of MelodyNote objects
        """
        # Get appropriate patterns for this section type
        patterns = self.SECTION_PATTERNS.get(
            section_type.lower(),
            ["anthem"]
        )

        # Choose a pattern
        if seed is not None:
            random.seed(seed)
        pattern = random.choice(patterns)

        # Adjust octave based on section
        octave_offset = 0
        if section_type.lower() in ["breakdown"]:
            octave_offset = -1  # Lower for emotional feel
        elif section_type.lower() in ["drop"]:
            octave_offset = 0  # Normal range for punch

        return self.generate(
            bars=bars,
            pattern=pattern,
            energy=energy,
            variation=variation,
            octave_offset=octave_offset,
            seed=seed
        )

    def to_midi_track(
        self,
        notes: List[MelodyNote],
        ticks_per_beat: int = None,
        program: int = 81  # Lead synth
    ) -> MidiTrack:
        """
        Convert melody notes to a MIDI track.

        Args:
            notes: List of MelodyNote objects
            ticks_per_beat: MIDI resolution
            program: MIDI program number (instrument)

        Returns:
            mido MidiTrack
        """
        if ticks_per_beat is None:
            ticks_per_beat = self.config.TICKS_PER_BEAT

        track = MidiTrack()
        track.append(Message("program_change", program=program, time=0))

        if not notes:
            return track

        # Sort notes by start time
        sorted_notes = sorted(notes, key=lambda n: n.start)

        # Build event list: (tick, event_type, pitch, velocity)
        events = []
        for note in sorted_notes:
            start_tick = int(note.start * ticks_per_beat)
            end_tick = int((note.start + note.duration) * ticks_per_beat)
            events.append(("on", start_tick, note.pitch, note.velocity))
            events.append(("off", end_tick, note.pitch, 0))

        # Sort events: by tick, then note_off before note_on at same tick
        events.sort(key=lambda e: (e[1], 0 if e[0] == "off" else 1))

        # Convert to MIDI messages with delta times
        current_tick = 0
        for event_type, tick, pitch, velocity in events:
            delta = tick - current_tick
            if event_type == "on":
                track.append(Message("note_on", note=pitch, velocity=velocity, time=delta))
            else:
                track.append(Message("note_off", note=pitch, velocity=0, time=delta))
            current_tick = tick

        return track

    def to_midi_file(
        self,
        notes: List[MelodyNote],
        output_path: str,
        ticks_per_beat: int = None
    ) -> str:
        """
        Save melody to a MIDI file.

        Args:
            notes: List of MelodyNote objects
            output_path: Path to save MIDI file
            ticks_per_beat: MIDI resolution

        Returns:
            Path to saved file
        """
        if ticks_per_beat is None:
            ticks_per_beat = self.config.TICKS_PER_BEAT

        mid = MidiFile(ticks_per_beat=ticks_per_beat)
        track = self.to_midi_track(notes, ticks_per_beat)
        mid.tracks.append(track)
        mid.save(output_path)

        return output_path


def demo():
    """Demo the melody generator."""
    from pathlib import Path

    print("Melody Generator Demo")
    print("=" * 40)

    # Create generator
    gen = MelodyGenerator(key="A", scale="minor", tempo=138)

    # Generate different patterns
    patterns_to_demo = ["anthem", "emotional", "driving", "call_response"]

    output_dir = Path(DEFAULT_CONFIG.OUTPUT_BASE) / "melody_demo"
    output_dir.mkdir(parents=True, exist_ok=True)

    for pattern in patterns_to_demo:
        print(f"\nGenerating '{pattern}' pattern...")
        notes = gen.generate(bars=8, pattern=pattern, energy=0.9, seed=42)

        print(f"  Generated {len(notes)} notes")
        for note in notes[:5]:  # Show first 5
            print(f"    Beat {note.start:.2f}: pitch={note.pitch}, "
                  f"dur={note.duration:.2f}, vel={note.velocity}")
        if len(notes) > 5:
            print(f"    ... and {len(notes) - 5} more")

        # Save to MIDI
        output_path = output_dir / f"melody_{pattern}.mid"
        gen.to_midi_file(notes, str(output_path))
        print(f"  Saved to: {output_path}")

    print("\n" + "=" * 40)
    print("Demo complete!")


if __name__ == "__main__":
    demo()
