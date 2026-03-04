#!/usr/bin/env python3
"""
Motif-Based Lead Generator
Creates a core melodic motif and develops it throughout the track.
"""

import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage
from pathlib import Path
import random
import time

random.seed(int(time.time() * 1000) % 2**32)

output_dir = Path(r"D:\OneDrive\Music\Projects\Ableton\Ableton Projects\TEMPLATE\BabyBoomers_Final\midi")

ticks_per_beat = 480
ticks_per_bar = ticks_per_beat * 4
sixteenth = ticks_per_beat // 4
eighth = ticks_per_beat // 2
tempo = mido.bpm2tempo(140)

# F minor scale degrees (for transposition)
F_MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]  # Intervals from root
F_ROOT = 65  # F4

# Chord progression with scale degrees
PROGRESSION = [
    # (chord_root_offset, chord_type, bars)
    # Fm = 0, Db = 6 (bVI), Ab = 3 (bIII), Eb = 10 (bVII), etc.
    (0, 'min', 2), (8, 'maj', 2), (3, 'maj', 2), (10, 'maj', 2),  # Intro
    (0, 'min', 2), (7, 'min', 2), (5, 'maj', 2), (5, 'min', 2),
    (0, 'min', 2), (8, 'maj', 2), (3, 'maj', 2), (10, 'maj', 2),
    (0, 'min', 2), (1, 'maj', 2), (8, 'maj', 2), (10, 'maj', 2),  # Gb = Neapolitan

    # Buildup - 1 bar each
    (0, 'min', 1), (0, 'min', 1), (1, 'maj', 1), (1, 'maj', 1),
    (8, 'maj', 1), (8, 'maj7', 1), (3, 'maj', 1), (3, 'maj7', 1),
    (10, 'maj', 1), (10, '7', 1), (0, 'min', 1), (0, 'min7', 1),
    (8, 'maj7', 1), (9, 'maj', 1), (5, 'min7', 1), (10, 'maj', 1),

    # Breakdown 1
    (0, 'min', 2), (8, 'maj', 2), (3, 'maj', 2), (10, 'maj', 2),
    (0, 'min', 2), (7, 'min', 2), (5, 'maj', 2), (5, 'min', 2),
    (0, 'min', 2), (8, 'maj', 2), (3, 'maj', 2), (10, 'maj', 2),
    (0, 'min', 2), (1, 'maj', 2), (8, 'maj', 2), (10, 'maj', 2),

    # Drop 1 - 1 bar each
    (0, 'min', 1), (0, 'min', 1), (8, 'maj', 1), (8, 'maj', 1),
    (3, 'maj', 1), (3, 'maj', 1), (10, 'maj', 1), (10, 'maj', 1),
    (0, 'min', 1), (7, 'min', 1), (8, 'maj', 1), (8, 'maj7', 1),
    (5, 'min', 1), (3, 'maj', 1), (2, 'dim', 1), (10, 'maj', 1),
    (0, 'min', 1), (0, 'min', 1), (8, 'maj', 1), (8, 'maj', 1),
    (3, 'maj', 1), (3, 'maj', 1), (10, 'maj', 1), (10, 'sus4', 1),
    (0, 'min', 1), (0, 'min7', 1), (8, 'maj', 1), (1, 'maj', 1),
    (5, 'min', 1), (7, 'min', 1), (5, 'maj', 1), (10, 'maj', 1),

    # Break
    (0, 'min', 2), (8, 'maj', 2), (5, 'min', 2), (10, 'maj', 2),
    (0, 'min', 2), (3, 'maj', 2), (8, 'maj', 2), (10, 'maj', 2),

    # Breakdown 2
    (0, 'min', 2), (8, 'maj', 2), (3, 'maj', 2), (10, 'maj', 2),
    (0, 'min', 2), (1, 'maj', 2), (8, 'maj', 2), (8, 'maj7', 2),
    (5, 'min', 2), (3, 'maj', 2), (10, 'maj', 2), (10, '7', 2),
    (0, 'min', 2), (7, 'min', 2), (5, 'maj', 2), (10, 'maj', 2),

    # Drop 2
    (0, 'min', 1), (0, 'min', 1), (8, 'maj', 1), (8, 'maj', 1),
    (3, 'maj', 1), (3, 'maj', 1), (10, 'maj', 1), (10, 'maj', 1),
    (0, 'min', 1), (1, 'maj', 1), (8, 'maj', 1), (9, 'maj', 1),
    (5, 'min', 1), (3, 'maj', 1), (10, 'maj', 1), (10, '7', 1),
    (0, 'min', 1), (0, 'min7', 1), (8, 'maj', 1), (8, 'maj7', 1),
    (3, 'maj', 1), (3, 'maj7', 1), (10, 'maj', 1), (10, 'sus4', 1),
    (0, 'min', 1), (7, 'min', 1), (8, 'maj', 1), (1, 'maj', 1),
    (5, 'min7', 1), (3, 'maj', 1), (2, 'dim', 1), (10, 'maj', 1),

    # Outro
    (0, 'min', 4), (8, 'maj', 4), (3, 'maj', 4), (10, 'maj', 4),
    (0, 'min', 4), (8, 'maj', 4), (5, 'min', 4), (0, 'min', 4),
]

# Section energy
def get_section(bar):
    if bar < 32: return 'intro', 0.3
    elif bar < 48: return 'buildup', 0.5
    elif bar < 80: return 'breakdown', 0.4
    elif bar < 112: return 'drop', 1.0
    elif bar < 128: return 'break', 0.6
    elif bar < 160: return 'breakdown', 0.4
    elif bar < 192: return 'drop', 1.0
    else: return 'outro', 0.2


def generate_motif():
    """Generate a core 4-8 note motif."""
    # Motif as scale degree intervals from chord root
    motif_length = random.randint(4, 8)

    # Start with common trance motif shapes
    shapes = [
        [0, 2, 4, 2],           # Up and back
        [0, 4, 2, 0],           # Arch
        [4, 2, 0, 2],           # Down and up
        [0, 2, 0, -1, 0],       # Neighbor tone
        [0, 2, 4, 5, 4, 2],     # Rising then falling
        [0, 0, 2, 4, 2, 0],     # Repeated note start
        [0, 4, 7, 4, 2, 0],     # Arpeggio style
        [0, -1, 0, 2, 4, 2],    # Lower neighbor approach
    ]

    motif_shape = random.choice(shapes)

    # Rhythm pattern (in 16ths)
    rhythm_patterns = [
        [2, 2, 2, 2],           # Even 8ths
        [3, 1, 2, 2],           # Dotted + short
        [2, 2, 3, 1],           # Syncopated end
        [4, 2, 2],              # Quarter + 8ths
        [2, 1, 1, 2, 2],        # 16th burst
        [3, 3, 2],              # Triplet feel
        [2, 2, 2, 1, 1],        # End flourish
        [1, 1, 2, 2, 2],        # Start flourish
    ]

    motif_rhythm = random.choice(rhythm_patterns)

    # Extend or truncate to match
    while len(motif_rhythm) < len(motif_shape):
        motif_rhythm.append(random.choice([1, 2]))
    motif_rhythm = motif_rhythm[:len(motif_shape)]

    return motif_shape, motif_rhythm


def transpose_motif(motif_shape, chord_root_offset, octave=0):
    """Transpose motif to chord root."""
    transposed = []
    for degree in motif_shape:
        # Map scale degree to semitones
        octave_offset = 0
        deg = degree
        while deg < 0:
            deg += 7
            octave_offset -= 12
        while deg >= 7:
            deg -= 7
            octave_offset += 12

        interval = F_MINOR_SCALE[deg] + octave_offset
        note = F_ROOT + chord_root_offset + interval + (octave * 12)
        transposed.append(note)
    return transposed


def transform_motif(motif_shape, transform_type):
    """Apply transformation to motif."""
    if transform_type == 'invert':
        # Flip intervals
        return [-d for d in motif_shape]
    elif transform_type == 'retrograde':
        # Reverse
        return motif_shape[::-1]
    elif transform_type == 'augment':
        # Double intervals
        return [d * 2 for d in motif_shape]
    elif transform_type == 'diminish':
        # Halve intervals (round)
        return [d // 2 for d in motif_shape]
    elif transform_type == 'shift_up':
        # Shift all up by 2
        return [d + 2 for d in motif_shape]
    elif transform_type == 'shift_down':
        return [d - 2 for d in motif_shape]
    elif transform_type == 'fragment':
        # Use first half
        return motif_shape[:len(motif_shape)//2 + 1]
    elif transform_type == 'extend':
        # Repeat with variation
        return motif_shape + [motif_shape[-1] + random.choice([-1, 1, 2])]
    else:
        return motif_shape


def generate_lead_with_motif():
    """Generate lead melody based on motif development."""
    print("Generating motif-based lead...")

    # Create core motif
    motif_shape, motif_rhythm = generate_motif()
    print(f"  Core motif: {motif_shape}")
    print(f"  Rhythm: {motif_rhythm} (16ths)")

    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

    events = []
    current_bar = 0

    # Track motif usage for variety
    transforms_used = []

    for chord_idx, (chord_root, chord_type, bars) in enumerate(PROGRESSION):
        section, energy = get_section(current_bar)
        chord_start = current_bar * ticks_per_bar
        chord_ticks = bars * ticks_per_bar

        # Decide what to do with the motif based on section
        if section == 'intro':
            # Sparse - occasional motif statements
            if random.random() < 0.3:
                current_shape = motif_shape
                current_rhythm = motif_rhythm
            else:
                current_bar += bars
                continue

        elif section == 'breakdown':
            # Emotional - use motif with inversions, slower
            transform = random.choice(['original', 'invert', 'shift_up'])
            current_shape = transform_motif(motif_shape, transform) if transform != 'original' else motif_shape
            current_rhythm = [r * 2 for r in motif_rhythm]  # Double durations

        elif section == 'buildup':
            # Building - fragments, intensifying
            transform = random.choice(['fragment', 'original', 'extend'])
            current_shape = transform_motif(motif_shape, transform) if transform != 'original' else motif_shape
            current_rhythm = motif_rhythm

        elif section == 'drop':
            # Full energy - variations and development
            transform = random.choice(['original', 'invert', 'retrograde', 'shift_up', 'shift_down', 'extend'])
            if transform not in transforms_used:
                transforms_used.append(transform)
            current_shape = transform_motif(motif_shape, transform) if transform != 'original' else motif_shape
            current_rhythm = motif_rhythm

        elif section == 'break':
            # Variation
            transform = random.choice(['fragment', 'diminish'])
            current_shape = transform_motif(motif_shape, transform)
            current_rhythm = motif_rhythm

        else:  # outro
            # Fading - sparse, original motif
            if random.random() < 0.4:
                current_shape = motif_shape
                current_rhythm = [r * 2 for r in motif_rhythm]
            else:
                current_bar += bars
                continue

        # Transpose motif to current chord
        octave = 0 if section in ['breakdown', 'intro', 'outro'] else random.choice([0, 1])
        notes = transpose_motif(current_shape, chord_root, octave)

        # Match rhythm to notes
        rhythm = current_rhythm[:len(notes)]
        while len(rhythm) < len(notes):
            rhythm.append(2)

        # Generate notes
        tick_offset = 0
        total_rhythm = sum(rhythm) * sixteenth

        # If motif doesn't fill the bars, decide what to do
        repetitions = max(1, (chord_ticks // total_rhythm) if total_rhythm > 0 else 1)

        for rep in range(int(repetitions)):
            if tick_offset >= chord_ticks:
                break

            # Add slight variation on repetitions
            if rep > 0 and random.random() < 0.3:
                # Slight variation
                notes = transpose_motif(
                    transform_motif(current_shape, random.choice(['shift_up', 'shift_down'])),
                    chord_root, octave
                )

            for i, (note, dur_16ths) in enumerate(zip(notes, rhythm)):
                note_tick = chord_start + tick_offset
                dur_ticks = dur_16ths * sixteenth - 30

                if note_tick >= chord_start + chord_ticks:
                    break

                # Velocity based on position in motif and section
                if i == 0:
                    vel = random.randint(85, 100)  # Emphasize first note
                elif i == len(notes) - 1:
                    vel = random.randint(75, 90)   # Slight emphasis on last
                else:
                    vel = random.randint(65, 80)

                # Boost in drops
                if section == 'drop':
                    vel = min(127, vel + 15)

                events.append((note_tick, 'on', note, vel))
                events.append((note_tick + dur_ticks, 'off', note, 0))

                tick_offset += dur_16ths * sixteenth

            # Gap between repetitions
            tick_offset += sixteenth * 2

        current_bar += bars

    # Sort and write
    events.sort(key=lambda x: (x[0], 0 if x[1] == 'on' else 1))
    last_tick = 0
    for tick, evt, note, vel in events:
        delta = max(0, tick - last_tick)
        track.append(Message('note_on' if evt == 'on' else 'note_off', note=note, velocity=vel, time=delta))
        last_tick = tick

    mid.save(output_dir / "lead.mid")
    note_count = len([e for e in events if e[1] == 'on'])
    print(f"  Saved lead.mid with {note_count} notes")
    print(f"  Transforms used: {transforms_used}")


if __name__ == "__main__":
    print("=" * 60)
    print("MOTIF-BASED LEAD GENERATOR")
    print("=" * 60)

    generate_lead_with_motif()

    print("\nMotif-based lead generated!")
    print("The melody develops from a core idea throughout the track.")
