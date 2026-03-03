#!/usr/bin/env python3
"""Generate enhanced lead melody with all the techniques."""

import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage
from pathlib import Path
import random

random.seed(42)  # Reproducible but varied

output_dir = Path(r"D:\OneDrive\Music\Projects\Ableton\Ableton Projects\TEMPLATE\BabyBoomers_Final\midi")

# F minor scale notes (for passing tones)
F_MINOR_SCALE = [41, 43, 44, 46, 48, 49, 51, 53, 55, 56, 58, 60, 61, 63, 65, 67, 68, 70, 72, 73, 75, 77]

def get_passing_tone(note1, note2):
    """Get a chromatic or scale passing tone between two notes."""
    if abs(note2 - note1) <= 2:
        return None
    mid = (note1 + note2) // 2
    # Prefer scale tones
    for scale_note in F_MINOR_SCALE:
        if abs(scale_note - mid) <= 1:
            return scale_note
    return mid

def get_neighbor_tone(note, direction='upper'):
    """Get upper or lower neighbor tone."""
    if direction == 'upper':
        for scale_note in F_MINOR_SCALE:
            if scale_note > note:
                return scale_note
        return note + 1
    else:
        for scale_note in reversed(F_MINOR_SCALE):
            if scale_note < note:
                return scale_note
        return note - 1

# F minor chord progression (same as other files)
progression = [
    # INTRO (32 bars) - 2 bars per chord
    ('Fm', [41, 48, 53], 2), ('Db', [49, 53, 56], 2), ('Ab', [32, 48, 51], 2), ('Eb', [39, 46, 51], 2),
    ('Fm', [41, 48, 53], 2), ('Cm', [36, 48, 51], 2), ('Bb', [34, 46, 50], 2), ('Bbm', [34, 46, 49], 2),
    ('Fm', [41, 48, 53], 2), ('Db', [49, 53, 56], 2), ('Ab', [32, 48, 51], 2), ('Eb', [39, 46, 51], 2),
    ('Fm', [41, 48, 53], 2), ('Gb', [30, 46, 49], 2), ('Db', [49, 53, 56], 2), ('Eb', [39, 46, 51], 2),

    # BUILDUP A (16 bars)
    ('Fm', [41, 48, 53], 1), ('Fm', [41, 48, 53], 1), ('Gb', [30, 46, 49], 1), ('Gb', [30, 46, 49], 1),
    ('Db', [49, 53, 56], 1), ('Dbmaj7', [49, 53, 56, 60], 1), ('Ab', [32, 48, 51], 1), ('Abmaj7', [32, 48, 51, 55], 1),
    ('Eb', [39, 46, 51], 1), ('Eb7', [39, 46, 51, 57], 1), ('Fm', [41, 48, 53], 1), ('Fm7', [41, 48, 53, 59], 1),
    ('Dbmaj7', [49, 53, 56, 60], 1), ('C', [36, 48, 52], 1), ('Bbm7', [34, 46, 49, 53], 1), ('Eb', [39, 46, 51], 1),

    # BREAKDOWN 1 (32 bars)
    ('Fm', [41, 48, 53], 2), ('Db', [49, 53, 56], 2), ('Ab', [32, 48, 51], 2), ('Eb', [39, 46, 51], 2),
    ('Fm', [41, 48, 53], 2), ('Cm', [36, 48, 51], 2), ('Bb', [34, 46, 50], 2), ('Bbm', [34, 46, 49], 2),
    ('Fm', [41, 48, 53], 2), ('Db', [49, 53, 56], 2), ('Ab', [32, 48, 51], 2), ('Eb', [39, 46, 51], 2),
    ('Fm', [41, 48, 53], 2), ('Gb', [30, 46, 49], 2), ('Db', [49, 53, 56], 2), ('Eb', [39, 46, 51], 2),

    # DROP 1 (32 bars)
    ('Fm', [41, 48, 53], 1), ('Fm', [41, 48, 53], 1), ('Db', [49, 53, 56], 1), ('Db', [49, 53, 56], 1),
    ('Ab', [32, 48, 51], 1), ('Ab', [32, 48, 51], 1), ('Eb', [39, 46, 51], 1), ('Eb', [39, 46, 51], 1),
    ('Fm', [41, 48, 53], 1), ('Cm', [36, 48, 51], 1), ('Db', [49, 53, 56], 1), ('Dbmaj7', [49, 53, 56, 60], 1),
    ('Bbm', [34, 46, 49], 1), ('Ab', [32, 48, 51], 1), ('Gdim', [31, 46, 49], 1), ('Eb', [39, 46, 51], 1),
    ('Fm', [41, 48, 53], 1), ('Fm', [41, 48, 53], 1), ('Db', [49, 53, 56], 1), ('Db', [49, 53, 56], 1),
    ('Ab', [32, 48, 51], 1), ('Ab', [32, 48, 51], 1), ('Eb', [39, 46, 51], 1), ('Ebsus4', [39, 44, 51], 1),
    ('Fm', [41, 48, 53], 1), ('Fm7', [41, 48, 53, 59], 1), ('Db', [49, 53, 56], 1), ('Gb', [30, 46, 49], 1),
    ('Bbm', [34, 46, 49], 1), ('Cm', [36, 48, 51], 1), ('Bb', [34, 46, 50], 1), ('Eb', [39, 46, 51], 1),

    # BREAK (16 bars)
    ('Fm', [41, 48, 53], 2), ('Db', [49, 53, 56], 2), ('Bbm', [34, 46, 49], 2), ('Eb', [39, 46, 51], 2),
    ('Fm', [41, 48, 53], 2), ('Ab', [32, 48, 51], 2), ('Db', [49, 53, 56], 2), ('Eb', [39, 46, 51], 2),

    # BREAKDOWN 2 (32 bars)
    ('Fm', [41, 48, 53], 2), ('Db', [49, 53, 56], 2), ('Ab', [32, 48, 51], 2), ('Eb', [39, 46, 51], 2),
    ('Fm', [41, 48, 53], 2), ('Gb', [30, 46, 49], 2), ('Db', [49, 53, 56], 2), ('Dbmaj7', [49, 53, 56, 60], 2),
    ('Bbm', [34, 46, 49], 2), ('Ab', [32, 48, 51], 2), ('Eb', [39, 46, 51], 2), ('Eb7', [39, 46, 51, 57], 2),
    ('Fm', [41, 48, 53], 2), ('Cm', [36, 48, 51], 2), ('Bb', [34, 46, 50], 2), ('Eb', [39, 46, 51], 2),

    # DROP 2 (32 bars)
    ('Fm', [41, 48, 53], 1), ('Fm', [41, 48, 53], 1), ('Db', [49, 53, 56], 1), ('Db', [49, 53, 56], 1),
    ('Ab', [32, 48, 51], 1), ('Ab', [32, 48, 51], 1), ('Eb', [39, 46, 51], 1), ('Eb', [39, 46, 51], 1),
    ('Fm', [41, 48, 53], 1), ('Gb', [30, 46, 49], 1), ('Db', [49, 53, 56], 1), ('C', [36, 48, 52], 1),
    ('Bbm', [34, 46, 49], 1), ('Ab', [32, 48, 51], 1), ('Eb', [39, 46, 51], 1), ('Eb7', [39, 46, 51, 57], 1),
    ('Fm', [41, 48, 53], 1), ('Fm7', [41, 48, 53, 59], 1), ('Db', [49, 53, 56], 1), ('Dbmaj7', [49, 53, 56, 60], 1),
    ('Ab', [32, 48, 51], 1), ('Abmaj7', [32, 48, 51, 55], 1), ('Eb', [39, 46, 51], 1), ('Ebsus4', [39, 44, 51], 1),
    ('Fm', [41, 48, 53], 1), ('Cm', [36, 48, 51], 1), ('Db', [49, 53, 56], 1), ('Gb', [30, 46, 49], 1),
    ('Bbm7', [34, 46, 49, 53], 1), ('Ab', [32, 48, 51], 1), ('Gdim', [31, 46, 49], 1), ('Eb', [39, 46, 51], 1),

    # OUTRO (32 bars)
    ('Fm', [41, 48, 53], 4), ('Db', [49, 53, 56], 4), ('Ab', [32, 48, 51], 4), ('Eb', [39, 46, 51], 4),
    ('Fm', [41, 48, 53], 4), ('Db', [49, 53, 56], 4), ('Bbm', [34, 46, 49], 4), ('Fm', [41, 48, 53], 4),
]

# Melodic phrase patterns (rhythm in 16th notes, relative pitch)
# Format: [(duration_16ths, pitch_index, velocity_mult)]
PHRASE_PATTERNS = {
    # Call phrases (asking)
    'call_rising': [
        (2, 0, 1.0), (2, 1, 0.9), (4, 2, 1.1), (2, 'pass', 0.7), (2, 2, 0.8), (4, 'oct_up', 1.2)
    ],
    'call_syncopated': [
        (3, 0, 1.0), (1, 1, 0.7), (2, 2, 0.9), (2, 'neigh_up', 0.6), (4, 2, 1.0), (4, 1, 0.8)
    ],
    'call_dramatic': [
        (1, 0, 0.8), (1, 'oct_up', 1.2), (2, 2, 1.0), (4, 1, 0.9), (2, 0, 0.7), (2, 'neigh_low', 0.6), (4, 0, 1.0)
    ],

    # Response phrases (answering)
    'response_falling': [
        (2, 2, 1.0), (2, 1, 0.9), (2, 'pass', 0.7), (2, 0, 0.8), (4, 0, 1.1), (4, 'neigh_low', 0.6)
    ],
    'response_resolved': [
        (4, 2, 1.0), (2, 1, 0.8), (2, 0, 0.9), (2, 'neigh_up', 0.6), (2, 0, 1.0), (4, 0, 1.1)
    ],
    'response_dramatic': [
        (2, 'oct_up', 1.2), (2, 2, 0.9), (2, 1, 0.8), (2, 'pass', 0.6), (4, 0, 1.0), (4, 0, 0.7)
    ],

    # Energetic patterns for drops
    'drop_energy': [
        (1, 0, 1.0), (1, 1, 0.9), (1, 2, 1.0), (1, 'oct_up', 1.2),
        (2, 2, 1.0), (2, 1, 0.8), (1, 0, 0.9), (1, 'neigh_up', 0.7), (2, 0, 1.0), (4, 0, 0.8)
    ],
    'drop_syncopated': [
        (3, 0, 1.0), (1, 2, 1.1), (2, 1, 0.8), (2, 'oct_up', 1.2),
        (1, 2, 0.9), (1, 1, 0.8), (2, 0, 1.0), (4, 0, 0.9)
    ],

    # Breakdown patterns (more sparse, emotional)
    'breakdown_sparse': [
        (8, 0, 0.9), (4, 1, 0.7), (4, 2, 0.8)
    ],
    'breakdown_emotional': [
        (4, 0, 0.8), (2, 'neigh_up', 0.6), (2, 0, 0.9), (4, 1, 0.7), (2, 2, 0.8), (2, 1, 0.6)
    ],
}

def get_section_type(bar_position):
    """Determine section type based on bar position."""
    if bar_position < 32:
        return 'intro'
    elif bar_position < 48:
        return 'buildup'
    elif bar_position < 80:
        return 'breakdown'
    elif bar_position < 112:
        return 'drop'
    elif bar_position < 128:
        return 'break'
    elif bar_position < 160:
        return 'breakdown'
    elif bar_position < 192:
        return 'drop'
    else:
        return 'outro'

def get_pattern_for_section(section_type, is_call=True):
    """Get appropriate pattern for section."""
    if section_type in ['drop']:
        patterns = ['drop_energy', 'drop_syncopated']
    elif section_type in ['breakdown', 'intro', 'outro']:
        patterns = ['breakdown_sparse', 'breakdown_emotional']
    elif section_type == 'buildup':
        if is_call:
            patterns = ['call_rising', 'call_syncopated']
        else:
            patterns = ['response_falling', 'response_resolved']
    else:  # break
        if is_call:
            patterns = ['call_rising', 'call_dramatic']
        else:
            patterns = ['response_falling', 'response_dramatic']

    return random.choice(patterns)

def resolve_pitch(pitch_spec, chord_notes, last_note):
    """Resolve pitch specification to actual MIDI note."""
    base_notes = [n + 24 for n in chord_notes[:3]]  # 2 octaves up

    if isinstance(pitch_spec, int):
        return base_notes[pitch_spec % len(base_notes)]
    elif pitch_spec == 'oct_up':
        return base_notes[0] + 12
    elif pitch_spec == 'oct_down':
        return base_notes[0] - 12
    elif pitch_spec == 'neigh_up':
        return get_neighbor_tone(last_note or base_notes[0], 'upper')
    elif pitch_spec == 'neigh_low':
        return get_neighbor_tone(last_note or base_notes[0], 'lower')
    elif pitch_spec == 'pass':
        target = base_notes[1] if last_note else base_notes[0]
        passing = get_passing_tone(last_note or base_notes[0], target)
        return passing if passing else target
    else:
        return base_notes[0]


# Generate the lead
print("Generating enhanced lead.mid...")

ticks_per_beat = 480
ticks_per_bar = ticks_per_beat * 4
sixteenth = ticks_per_beat // 4
tempo = mido.bpm2tempo(140)

mid = MidiFile(ticks_per_beat=ticks_per_beat)
track = MidiTrack()
mid.tracks.append(track)
track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

current_bar = 0
phrase_count = 0
last_note = None
events = []  # (tick, 'on'/'off', note, velocity)

for chord_idx, (chord_name, notes, bars) in enumerate(progression):
    section_type = get_section_type(current_bar)

    # Alternate call and response
    is_call = (phrase_count % 2 == 0)
    pattern_name = get_pattern_for_section(section_type, is_call)
    pattern = PHRASE_PATTERNS[pattern_name]

    # Calculate timing
    chord_start_tick = current_bar * ticks_per_bar
    chord_duration_ticks = bars * ticks_per_bar

    # Generate notes from pattern
    tick_offset = 0
    available_ticks = chord_duration_ticks

    for dur_16ths, pitch_spec, vel_mult in pattern:
        if tick_offset >= available_ticks:
            break

        note_duration = dur_16ths * sixteenth
        if tick_offset + note_duration > available_ticks:
            note_duration = available_ticks - tick_offset

        note = resolve_pitch(pitch_spec, notes, last_note)
        velocity = int(80 * vel_mult)
        velocity = max(50, min(127, velocity))

        note_start = chord_start_tick + tick_offset
        note_end = note_start + note_duration - 20  # Small gap

        events.append((note_start, 'on', note, velocity))
        events.append((note_end, 'off', note, 0))

        last_note = note
        tick_offset += note_duration

    current_bar += bars
    phrase_count += 1

# Sort events by time and write to track
events.sort(key=lambda x: (x[0], 0 if x[1] == 'on' else 1))

last_tick = 0
for tick, event_type, note, velocity in events:
    delta = tick - last_tick
    if event_type == 'on':
        track.append(Message('note_on', note=note, velocity=velocity, time=delta))
    else:
        track.append(Message('note_off', note=note, velocity=0, time=delta))
    last_tick = tick

mid.save(output_dir / "lead.mid")
print(f"  Saved enhanced lead.mid with {len(events)//2} notes")
print(f"  Features: passing tones, neighbor notes, syncopation, call/response, octave jumps")
