"""
MIDI Song Generator

Generates MIDI patterns for trance music production:
- Kick patterns (4-on-floor, variations)
- Bass lines (rolling, sidechained)
- Chord progressions (trance chords)
- Arpeggios (16th note patterns)
- Percussion (hats, claps, rides)

Patterns are generated based on:
- Key/scale
- Tempo
- Energy level (0-1)
- Section type (intro, buildup, drop, breakdown, outro)
"""

import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Tuple
import random
import math

from config import Config, DEFAULT_CONFIG

# Musical constants
NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

SCALES = {
    'minor': [0, 2, 3, 5, 7, 8, 10],  # Natural minor
    'major': [0, 2, 4, 5, 7, 9, 11],
    'harmonic_minor': [0, 2, 3, 5, 7, 8, 11],
    'melodic_minor': [0, 2, 3, 5, 7, 9, 11],
    'dorian': [0, 2, 3, 5, 7, 9, 10],
    'phrygian': [0, 1, 3, 5, 7, 8, 10],
}

# Trance chord progressions (scale degrees, 0-indexed)
TRANCE_PROGRESSIONS = [
    [(0, 'min'), (5, 'maj'), (3, 'maj'), (4, 'maj')],  # i - VI - IV - V (Am - F - Dm - E)
    [(0, 'min'), (3, 'maj'), (5, 'maj'), (4, 'maj')],  # i - IV - VI - V
    [(0, 'min'), (6, 'maj'), (3, 'maj'), (4, 'maj')],  # i - VII - IV - V
    [(0, 'min'), (4, 'maj'), (0, 'min'), (5, 'maj')],  # i - V - i - VI
]


@dataclass
class GeneratorConfig:
    """Configuration for song generation."""
    key: str = 'A'
    scale: str = 'minor'
    tempo: int = 138
    time_signature: Tuple[int, int] = (4, 4)
    bars: int = 8
    ticks_per_beat: int = 480


def note_to_midi(note: str, octave: int = 4) -> int:
    """Convert note name to MIDI number."""
    note_idx = NOTES.index(note.upper().replace('♯', '#').replace('♭', 'b'))
    return note_idx + (octave + 1) * 12


def get_scale_notes(root: str, scale_name: str, octave: int = 4) -> List[int]:
    """Get MIDI note numbers for a scale."""
    root_midi = note_to_midi(root, octave)
    intervals = SCALES.get(scale_name, SCALES['minor'])
    return [root_midi + interval for interval in intervals]


def get_chord_notes(root_midi: int, chord_type: str) -> List[int]:
    """Get MIDI notes for a chord."""
    if chord_type == 'maj':
        return [root_midi, root_midi + 4, root_midi + 7]
    elif chord_type == 'min':
        return [root_midi, root_midi + 3, root_midi + 7]
    elif chord_type == 'maj7':
        return [root_midi, root_midi + 4, root_midi + 7, root_midi + 11]
    elif chord_type == 'min7':
        return [root_midi, root_midi + 3, root_midi + 7, root_midi + 10]
    elif chord_type == 'sus4':
        return [root_midi, root_midi + 5, root_midi + 7]
    elif chord_type == 'sus2':
        return [root_midi, root_midi + 2, root_midi + 7]
    else:
        return [root_midi, root_midi + 4, root_midi + 7]  # Default major


class MIDIGenerator:
    """Generates MIDI patterns for trance production."""

    def __init__(self, config: GeneratorConfig = None):
        self.config = config or GeneratorConfig()
        self.ticks_per_beat = self.config.ticks_per_beat
        self.ticks_per_bar = self.ticks_per_beat * self.config.time_signature[0]

    def create_midi_file(self, tracks_data: List[Tuple[str, List]], filename: str):
        """Create a MIDI file with multiple tracks."""
        mid = MidiFile(ticks_per_beat=self.ticks_per_beat)

        for track_name, events in tracks_data:
            track = MidiTrack()
            mid.tracks.append(track)

            # Track name
            track.append(MetaMessage('track_name', name=track_name, time=0))

            # Tempo (only on first track)
            if len(mid.tracks) == 1:
                tempo_us = mido.bpm2tempo(self.config.tempo)
                track.append(MetaMessage('set_tempo', tempo=tempo_us, time=0))

            # Add events
            current_time = 0
            for event in sorted(events, key=lambda x: x[0]):
                abs_time, msg_type, *params = event
                delta = abs_time - current_time
                current_time = abs_time

                if msg_type == 'note_on':
                    note, velocity = params
                    track.append(Message('note_on', note=note, velocity=velocity, time=delta))
                elif msg_type == 'note_off':
                    note = params[0]
                    track.append(Message('note_off', note=note, velocity=0, time=delta))

            # End of track
            track.append(MetaMessage('end_of_track', time=0))

        mid.save(filename)
        return filename

    # =========================================================================
    # KICK PATTERNS
    # =========================================================================

    def generate_kick(self, bars: int = None, energy: float = 1.0,
                      pattern_type: str = 'four_on_floor') -> List:
        """Generate kick drum pattern.

        Args:
            bars: Number of bars
            energy: 0-1, affects velocity and density
            pattern_type: 'four_on_floor', 'offbeat', 'half', 'broken'

        Returns:
            List of MIDI events
        """
        bars = bars or self.config.bars
        events = []
        kick_note = 60  # C3 - all drums on C3

        base_velocity = int(100 + energy * 27)  # 100-127

        for bar in range(bars):
            bar_start = bar * self.ticks_per_bar

            if pattern_type == 'four_on_floor':
                # Standard 4-on-the-floor
                for beat in range(4):
                    pos = bar_start + beat * self.ticks_per_beat
                    vel = base_velocity if beat == 0 else base_velocity - 10
                    events.append((pos, 'note_on', kick_note, vel))
                    events.append((pos + self.ticks_per_beat // 2, 'note_off', kick_note))

            elif pattern_type == 'offbeat':
                # Offbeat kicks (beats 2 and 4)
                for beat in [1, 3]:
                    pos = bar_start + beat * self.ticks_per_beat
                    events.append((pos, 'note_on', kick_note, base_velocity - 5))
                    events.append((pos + self.ticks_per_beat // 2, 'note_off', kick_note))

            elif pattern_type == 'half':
                # Half-time (beats 1 and 3)
                for beat in [0, 2]:
                    pos = bar_start + beat * self.ticks_per_beat
                    vel = base_velocity if beat == 0 else base_velocity - 10
                    events.append((pos, 'note_on', kick_note, vel))
                    events.append((pos + self.ticks_per_beat // 2, 'note_off', kick_note))

            elif pattern_type == 'broken':
                # Broken pattern with some 16ths
                positions = [0, 1, 2, 3]  # Beats
                if energy > 0.5:
                    # Add some 16th notes
                    positions.extend([0.5, 2.75])
                for beat_pos in positions:
                    if random.random() < energy or beat_pos in [0, 2]:
                        pos = bar_start + int(beat_pos * self.ticks_per_beat)
                        vel = base_velocity if beat_pos == 0 else base_velocity - 15
                        events.append((pos, 'note_on', kick_note, vel))
                        events.append((pos + self.ticks_per_beat // 4, 'note_off', kick_note))

        return events

    # =========================================================================
    # BASS PATTERNS
    # =========================================================================

    def generate_bass(self, bars: int = None, energy: float = 1.0,
                      pattern_type: str = 'rolling', root_note: int = None) -> List:
        """Generate bass pattern.

        Args:
            bars: Number of bars
            energy: 0-1, affects velocity and note density
            pattern_type: 'rolling', 'sustained', 'stabs', 'octave'
            root_note: MIDI note for root (default: A1 = 33)

        Returns:
            List of MIDI events
        """
        bars = bars or self.config.bars
        events = []

        if root_note is None:
            root_note = note_to_midi(self.config.key, 1)  # Song key, octave 1

        base_velocity = int(80 + energy * 40)
        sixteenth = self.ticks_per_beat // 4

        for bar in range(bars):
            bar_start = bar * self.ticks_per_bar

            if pattern_type == 'rolling':
                # Rolling 16th note bass (with sidechain gaps)
                for beat in range(4):
                    beat_start = bar_start + beat * self.ticks_per_beat
                    # Skip first 16th (sidechain duck), play remaining 3
                    for sub in range(1, 4):
                        if random.random() < energy:
                            pos = beat_start + sub * sixteenth
                            vel = base_velocity - (10 if sub == 1 else 0)
                            note = root_note if sub != 3 else root_note + 12  # Octave on last 16th
                            events.append((pos, 'note_on', note, vel))
                            events.append((pos + sixteenth - 10, 'note_off', note))

            elif pattern_type == 'sustained':
                # Long sustained notes - one note every 2 bars
                if bar % 2 == 0:  # Only trigger on even bars
                    note_length = self.ticks_per_bar * 2 - 20  # 2 full bars
                    events.append((bar_start, 'note_on', root_note, base_velocity))
                    events.append((bar_start + note_length, 'note_off', root_note))

            elif pattern_type == 'stabs':
                # Short staccato stabs
                stab_positions = [0, 1.5, 2, 3.5] if energy > 0.5 else [0, 2]
                for beat_pos in stab_positions:
                    pos = bar_start + int(beat_pos * self.ticks_per_beat)
                    events.append((pos, 'note_on', root_note, base_velocity))
                    events.append((pos + sixteenth * 2, 'note_off', root_note))

            elif pattern_type == 'octave':
                # Alternating octaves
                for beat in range(4):
                    pos = bar_start + beat * self.ticks_per_beat
                    note = root_note if beat % 2 == 0 else root_note + 12
                    events.append((pos, 'note_on', note, base_velocity))
                    events.append((pos + self.ticks_per_beat - 20, 'note_off', note))

        return events

    # =========================================================================
    # CHORD PROGRESSIONS
    # =========================================================================

    def generate_chords(self, bars: int = None, energy: float = 1.0,
                        pattern_type: str = 'sustained', progression_idx: int = 0,
                        octave: int = 4) -> List:
        """Generate chord progression.

        Args:
            bars: Number of bars (should be multiple of 4 for full progression)
            energy: 0-1, affects velocity
            pattern_type: 'sustained', 'stabs', 'rhythmic', 'arp_chords'
            progression_idx: Index into TRANCE_PROGRESSIONS
            octave: Base octave for chords

        Returns:
            List of MIDI events
        """
        bars = bars or self.config.bars
        events = []

        progression = TRANCE_PROGRESSIONS[progression_idx % len(TRANCE_PROGRESSIONS)]
        scale_notes = get_scale_notes(self.config.key, self.config.scale, octave)
        base_velocity = int(70 + energy * 40)

        # Each chord lasts 1 bar (or 2 bars for slower feel)
        bars_per_chord = max(1, bars // len(progression))

        for chord_idx, (degree, chord_type) in enumerate(progression):
            chord_start = chord_idx * bars_per_chord * self.ticks_per_bar

            # Get root note from scale
            root_midi = scale_notes[degree % len(scale_notes)]
            chord_notes = get_chord_notes(root_midi, chord_type)

            if pattern_type == 'sustained':
                # Long sustained chords - play once and hold for full duration
                chord_duration = bars_per_chord * self.ticks_per_bar - 20
                for note in chord_notes:
                    events.append((chord_start, 'note_on', note, base_velocity))
                    events.append((chord_start + chord_duration, 'note_off', note))
                continue  # Skip the per-bar loop for sustained

            for bar in range(bars_per_chord):
                bar_start = chord_start + bar * self.ticks_per_bar

                if pattern_type == 'stabs':
                    # Chord stabs on beat 1
                    stab_length = self.ticks_per_beat // 2
                    for note in chord_notes:
                        events.append((bar_start, 'note_on', note, base_velocity + 10))
                        events.append((bar_start + stab_length, 'note_off', note))

                elif pattern_type == 'rhythmic':
                    # Rhythmic chord pattern
                    positions = [0, 0.5, 1.5, 2, 3] if energy > 0.5 else [0, 2]
                    for pos in positions:
                        abs_pos = bar_start + int(pos * self.ticks_per_beat)
                        note_len = self.ticks_per_beat // 2
                        vel = base_velocity if pos == 0 else base_velocity - 15
                        for note in chord_notes:
                            events.append((abs_pos, 'note_on', note, vel))
                            events.append((abs_pos + note_len, 'note_off', note))

                elif pattern_type == 'arp_chords':
                    # Arpeggiated chord (broken chord)
                    sixteenth = self.ticks_per_beat // 4
                    for beat in range(4):
                        beat_start = bar_start + beat * self.ticks_per_beat
                        for i, note in enumerate(chord_notes):
                            pos = beat_start + i * sixteenth
                            events.append((pos, 'note_on', note, base_velocity - i * 5))
                            events.append((pos + sixteenth * 2, 'note_off', note))

        return events

    # =========================================================================
    # ARPEGGIOS
    # =========================================================================

    def generate_arp(self, bars: int = None, energy: float = 1.0,
                     pattern_type: str = 'up', octaves: int = 2,
                     note_value: str = '16th') -> List:
        """Generate arpeggio pattern.

        Args:
            bars: Number of bars
            energy: 0-1, affects velocity variation
            pattern_type: 'up', 'down', 'updown', 'random', 'trance'
            octaves: Number of octaves to span
            note_value: '8th', '16th', '32nd'

        Returns:
            List of MIDI events
        """
        bars = bars or self.config.bars
        events = []

        scale_notes = get_scale_notes(self.config.key, self.config.scale, 4)
        # Extend to multiple octaves
        all_notes = []
        for oct in range(octaves):
            all_notes.extend([n + oct * 12 for n in scale_notes])

        note_divisions = {'8th': 2, '16th': 4, '32nd': 8}
        notes_per_beat = note_divisions.get(note_value, 4)
        note_length = self.ticks_per_beat // notes_per_beat

        base_velocity = int(60 + energy * 50)

        for bar in range(bars):
            bar_start = bar * self.ticks_per_bar
            notes_in_bar = notes_per_beat * 4  # 4 beats per bar

            for i in range(notes_in_bar):
                pos = bar_start + i * note_length

                if pattern_type == 'up':
                    note_idx = i % len(all_notes)
                elif pattern_type == 'down':
                    note_idx = (len(all_notes) - 1 - i) % len(all_notes)
                elif pattern_type == 'updown':
                    cycle_len = len(all_notes) * 2 - 2
                    cycle_pos = i % cycle_len
                    if cycle_pos < len(all_notes):
                        note_idx = cycle_pos
                    else:
                        note_idx = len(all_notes) - 2 - (cycle_pos - len(all_notes))
                elif pattern_type == 'random':
                    note_idx = random.randint(0, len(all_notes) - 1)
                elif pattern_type == 'trance':
                    # Classic trance arp pattern: 1-3-5-8 / 1-5-3-8
                    trance_pattern = [0, 2, 4, 7, 0, 4, 2, 7]
                    degree = trance_pattern[i % len(trance_pattern)]
                    note_idx = degree % len(all_notes)
                else:
                    note_idx = i % len(all_notes)

                note = all_notes[note_idx]
                # Velocity variation based on position
                vel = base_velocity + random.randint(-10, 10) if energy > 0.3 else base_velocity
                vel = max(40, min(127, vel))

                # Accent on beat
                if i % notes_per_beat == 0:
                    vel = min(127, vel + 15)

                events.append((pos, 'note_on', note, vel))
                events.append((pos + note_length - 10, 'note_off', note))

        return events

    # =========================================================================
    # PERCUSSION
    # =========================================================================

    def generate_hats(self, bars: int = None, energy: float = 1.0,
                      pattern_type: str = 'offbeat') -> List:
        """Generate hi-hat pattern."""
        bars = bars or self.config.bars
        events = []

        closed_hat = 60  # C3 - all drums on C3
        open_hat = 60    # C3 - all drums on C3

        base_velocity = int(60 + energy * 40)
        sixteenth = self.ticks_per_beat // 4

        for bar in range(bars):
            bar_start = bar * self.ticks_per_bar

            if pattern_type == 'offbeat':
                # Offbeat 8ths
                for beat in range(4):
                    pos = bar_start + beat * self.ticks_per_beat + self.ticks_per_beat // 2
                    events.append((pos, 'note_on', closed_hat, base_velocity))
                    events.append((pos + sixteenth, 'note_off', closed_hat))

            elif pattern_type == '16ths':
                # 16th note hats
                for i in range(16):
                    pos = bar_start + i * sixteenth
                    vel = base_velocity if i % 4 == 0 else base_velocity - 20
                    vel = vel + random.randint(-5, 5) if energy > 0.5 else vel
                    events.append((pos, 'note_on', closed_hat, max(40, vel)))
                    events.append((pos + sixteenth - 10, 'note_off', closed_hat))

            elif pattern_type == 'rides':
                # Ride pattern (every beat)
                ride = 60  # C3 - all drums on C3
                for beat in range(4):
                    pos = bar_start + beat * self.ticks_per_beat
                    events.append((pos, 'note_on', ride, base_velocity + 10))
                    events.append((pos + self.ticks_per_beat - 20, 'note_off', ride))

        return events

    def generate_clap(self, bars: int = None, energy: float = 1.0) -> List:
        """Generate clap pattern (beats 2 and 4)."""
        bars = bars or self.config.bars
        events = []

        clap = 60  # C3 - all drums on C3
        base_velocity = int(90 + energy * 30)

        for bar in range(bars):
            bar_start = bar * self.ticks_per_bar
            for beat in [1, 3]:  # Beats 2 and 4
                pos = bar_start + beat * self.ticks_per_beat
                events.append((pos, 'note_on', clap, base_velocity))
                events.append((pos + self.ticks_per_beat // 4, 'note_off', clap))

        return events


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def generate_pattern(pattern_type: str, bars: int = 8, key: str = 'A',
                     scale: str = 'minor', tempo: int = 138,
                     energy: float = 1.0, output_path: str = None) -> str:
    """Generate a single pattern and save to file.

    Args:
        pattern_type: 'kick', 'bass', 'chords', 'arp', 'hats', 'clap'
        bars: Number of bars
        key: Musical key
        scale: Scale type
        tempo: BPM
        energy: 0-1
        output_path: Output file path

    Returns:
        Path to generated MIDI file
    """
    config = GeneratorConfig(key=key, scale=scale, tempo=tempo, bars=bars)
    gen = MIDIGenerator(config)

    if pattern_type == 'kick':
        events = gen.generate_kick(energy=energy)
    elif pattern_type == 'bass':
        events = gen.generate_bass(energy=energy)
    elif pattern_type == 'chords':
        events = gen.generate_chords(energy=energy)
    elif pattern_type == 'arp':
        events = gen.generate_arp(energy=energy)
    elif pattern_type == 'hats':
        events = gen.generate_hats(energy=energy)
    elif pattern_type == 'clap':
        events = gen.generate_clap(energy=energy)
    else:
        raise ValueError(f"Unknown pattern type: {pattern_type}")

    if output_path is None:
        output_path = f"{pattern_type}_{key}_{scale}_{bars}bars.mid"

    gen.create_midi_file([(pattern_type, events)], output_path)
    return output_path


if __name__ == '__main__':
    # Demo: Generate all pattern types
    output_dir = DEFAULT_CONFIG.OUTPUT_BASE / "midi_patterns_demo"
    output_dir.mkdir(parents=True, exist_ok=True)

    config = GeneratorConfig(key='A', scale='minor', tempo=138, bars=8)
    gen = MIDIGenerator(config)

    print("=" * 60)
    print("MIDI PATTERN GENERATOR")
    print(f"Key: {config.key} {config.scale}, Tempo: {config.tempo} BPM")
    print("=" * 60)
    print()

    # Generate each pattern type
    patterns = [
        ('kick', gen.generate_kick(pattern_type='four_on_floor')),
        ('bass', gen.generate_bass(pattern_type='rolling')),
        ('chords', gen.generate_chords(pattern_type='sustained')),
        ('arp', gen.generate_arp(pattern_type='trance')),
        ('hats', gen.generate_hats(pattern_type='offbeat')),
        ('clap', gen.generate_clap()),
    ]

    for name, events in patterns:
        output_file = output_dir / f"{name}_Am_138.mid"
        gen.create_midi_file([(name, events)], str(output_file))
        print(f"  Generated: {output_file.name}")

    print()
    print(f"All patterns saved to: {output_dir}")
