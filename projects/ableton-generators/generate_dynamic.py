#!/usr/bin/env python3
"""
Dynamic MIDI Generator - Creates unique output each time.
Every generation sounds significantly different.
"""

import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage
from pathlib import Path
import random
import time

# Use current time as seed for true randomness
random.seed(int(time.time() * 1000) % 2**32)

output_dir = Path(r"D:\OneDrive\Music\Projects\Ableton\Ableton Projects\TEMPLATE\BabyBoomers_Final\midi")

# F minor scale
F_MINOR = [41, 43, 44, 46, 48, 49, 51, 53, 55, 56, 58, 60, 61, 63, 65, 67, 68, 70, 72, 73, 75, 77, 79, 80]

# Base chord progression
BASE_PROGRESSION = [
    # INTRO (32 bars)
    ('Fm', [41, 48, 53], 2), ('Db', [49, 53, 56], 2), ('Ab', [44, 48, 51], 2), ('Eb', [39, 46, 51], 2),
    ('Fm', [41, 48, 53], 2), ('Cm', [48, 51, 55], 2), ('Bb', [46, 50, 53], 2), ('Bbm', [46, 49, 53], 2),
    ('Fm', [41, 48, 53], 2), ('Db', [49, 53, 56], 2), ('Ab', [44, 48, 51], 2), ('Eb', [39, 46, 51], 2),
    ('Fm', [41, 48, 53], 2), ('Gb', [42, 46, 49], 2), ('Db', [49, 53, 56], 2), ('Eb', [39, 46, 51], 2),
    # BUILDUP (16 bars)
    ('Fm', [41, 48, 53], 1), ('Fm', [41, 48, 53], 1), ('Gb', [42, 46, 49], 1), ('Gb', [42, 46, 49], 1),
    ('Db', [49, 53, 56], 1), ('Dbmaj7', [49, 53, 56, 60], 1), ('Ab', [44, 48, 51], 1), ('Abmaj7', [44, 48, 51, 55], 1),
    ('Eb', [39, 46, 51], 1), ('Eb7', [39, 46, 51, 57], 1), ('Fm', [41, 48, 53], 1), ('Fm7', [41, 48, 53, 59], 1),
    ('Dbmaj7', [49, 53, 56, 60], 1), ('C', [48, 52, 55], 1), ('Bbm7', [46, 49, 53, 58], 1), ('Eb', [39, 46, 51], 1),
    # BREAKDOWN 1 (32 bars)
    ('Fm', [41, 48, 53], 2), ('Db', [49, 53, 56], 2), ('Ab', [44, 48, 51], 2), ('Eb', [39, 46, 51], 2),
    ('Fm', [41, 48, 53], 2), ('Cm', [48, 51, 55], 2), ('Bb', [46, 50, 53], 2), ('Bbm', [46, 49, 53], 2),
    ('Fm', [41, 48, 53], 2), ('Db', [49, 53, 56], 2), ('Ab', [44, 48, 51], 2), ('Eb', [39, 46, 51], 2),
    ('Fm', [41, 48, 53], 2), ('Gb', [42, 46, 49], 2), ('Db', [49, 53, 56], 2), ('Eb', [39, 46, 51], 2),
    # DROP 1 (32 bars)
    ('Fm', [41, 48, 53], 1), ('Fm', [41, 48, 53], 1), ('Db', [49, 53, 56], 1), ('Db', [49, 53, 56], 1),
    ('Ab', [44, 48, 51], 1), ('Ab', [44, 48, 51], 1), ('Eb', [39, 46, 51], 1), ('Eb', [39, 46, 51], 1),
    ('Fm', [41, 48, 53], 1), ('Cm', [48, 51, 55], 1), ('Db', [49, 53, 56], 1), ('Dbmaj7', [49, 53, 56, 60], 1),
    ('Bbm', [46, 49, 53], 1), ('Ab', [44, 48, 51], 1), ('Gdim', [43, 46, 49], 1), ('Eb', [39, 46, 51], 1),
    ('Fm', [41, 48, 53], 1), ('Fm', [41, 48, 53], 1), ('Db', [49, 53, 56], 1), ('Db', [49, 53, 56], 1),
    ('Ab', [44, 48, 51], 1), ('Ab', [44, 48, 51], 1), ('Eb', [39, 46, 51], 1), ('Ebsus4', [39, 44, 51], 1),
    ('Fm', [41, 48, 53], 1), ('Fm7', [41, 48, 53, 59], 1), ('Db', [49, 53, 56], 1), ('Gb', [42, 46, 49], 1),
    ('Bbm', [46, 49, 53], 1), ('Cm', [48, 51, 55], 1), ('Bb', [46, 50, 53], 1), ('Eb', [39, 46, 51], 1),
    # BREAK (16 bars)
    ('Fm', [41, 48, 53], 2), ('Db', [49, 53, 56], 2), ('Bbm', [46, 49, 53], 2), ('Eb', [39, 46, 51], 2),
    ('Fm', [41, 48, 53], 2), ('Ab', [44, 48, 51], 2), ('Db', [49, 53, 56], 2), ('Eb', [39, 46, 51], 2),
    # BREAKDOWN 2 (32 bars)
    ('Fm', [41, 48, 53], 2), ('Db', [49, 53, 56], 2), ('Ab', [44, 48, 51], 2), ('Eb', [39, 46, 51], 2),
    ('Fm', [41, 48, 53], 2), ('Gb', [42, 46, 49], 2), ('Db', [49, 53, 56], 2), ('Dbmaj7', [49, 53, 56, 60], 2),
    ('Bbm', [46, 49, 53], 2), ('Ab', [44, 48, 51], 2), ('Eb', [39, 46, 51], 2), ('Eb7', [39, 46, 51, 57], 2),
    ('Fm', [41, 48, 53], 2), ('Cm', [48, 51, 55], 2), ('Bb', [46, 50, 53], 2), ('Eb', [39, 46, 51], 2),
    # DROP 2 (32 bars)
    ('Fm', [41, 48, 53], 1), ('Fm', [41, 48, 53], 1), ('Db', [49, 53, 56], 1), ('Db', [49, 53, 56], 1),
    ('Ab', [44, 48, 51], 1), ('Ab', [44, 48, 51], 1), ('Eb', [39, 46, 51], 1), ('Eb', [39, 46, 51], 1),
    ('Fm', [41, 48, 53], 1), ('Gb', [42, 46, 49], 1), ('Db', [49, 53, 56], 1), ('C', [48, 52, 55], 1),
    ('Bbm', [46, 49, 53], 1), ('Ab', [44, 48, 51], 1), ('Eb', [39, 46, 51], 1), ('Eb7', [39, 46, 51, 57], 1),
    ('Fm', [41, 48, 53], 1), ('Fm7', [41, 48, 53, 59], 1), ('Db', [49, 53, 56], 1), ('Dbmaj7', [49, 53, 56, 60], 1),
    ('Ab', [44, 48, 51], 1), ('Abmaj7', [44, 48, 51, 55], 1), ('Eb', [39, 46, 51], 1), ('Ebsus4', [39, 44, 51], 1),
    ('Fm', [41, 48, 53], 1), ('Cm', [48, 51, 55], 1), ('Db', [49, 53, 56], 1), ('Gb', [42, 46, 49], 1),
    ('Bbm7', [46, 49, 53, 58], 1), ('Ab', [44, 48, 51], 1), ('Gdim', [43, 46, 49], 1), ('Eb', [39, 46, 51], 1),
    # OUTRO (32 bars)
    ('Fm', [41, 48, 53], 4), ('Db', [49, 53, 56], 4), ('Ab', [44, 48, 51], 4), ('Eb', [39, 46, 51], 4),
    ('Fm', [41, 48, 53], 4), ('Db', [49, 53, 56], 4), ('Bbm', [46, 49, 53], 4), ('Fm', [41, 48, 53], 4),
]

ticks_per_beat = 480
ticks_per_bar = ticks_per_beat * 4
sixteenth = ticks_per_beat // 4
eighth = ticks_per_beat // 2
tempo = mido.bpm2tempo(140)

# ============================================================================
# RANDOMIZATION FUNCTIONS
# ============================================================================

def randomize_voicing(notes, style='normal'):
    """Create random chord voicing."""
    if style == 'spread':
        # Spread voicing - wider intervals
        result = [notes[0] - 12, notes[1], notes[2] + 12]
    elif style == 'drop2':
        # Drop 2 voicing
        result = [notes[0], notes[2], notes[1] + 12]
    elif style == 'close':
        # Close position
        result = sorted(notes)
    elif style == 'high':
        # Higher register
        result = [n + 12 for n in notes]
    else:
        result = list(notes)

    # Random octave shift
    if random.random() < 0.2:
        shift = random.choice([-12, 12])
        result = [n + shift for n in result]

    return result

def get_neighbor(note, direction=None):
    """Get scale neighbor tone."""
    if direction is None:
        direction = random.choice(['up', 'down'])

    for i, n in enumerate(F_MINOR):
        if n >= note:
            if direction == 'up' and i + 1 < len(F_MINOR):
                return F_MINOR[i + 1]
            elif direction == 'down' and i > 0:
                return F_MINOR[i - 1]
            break
    return note + (1 if direction == 'up' else -1)

def get_passing_tones(note1, note2, count=1):
    """Get passing tones between two notes."""
    if abs(note2 - note1) < 3:
        return []

    result = []
    step = (note2 - note1) / (count + 1)
    for i in range(1, count + 1):
        target = int(note1 + step * i)
        # Snap to scale
        closest = min(F_MINOR, key=lambda n: abs(n - target))
        if closest not in result:
            result.append(closest)
    return result

def random_rhythm_pattern(total_16ths, density='normal'):
    """Generate random rhythm pattern."""
    patterns = []
    remaining = total_16ths

    if density == 'sparse':
        min_dur, max_dur = 4, 16
    elif density == 'dense':
        min_dur, max_dur = 1, 4
    else:
        min_dur, max_dur = 2, 8

    while remaining > 0:
        if remaining < min_dur:
            patterns.append(remaining)
            break
        dur = random.randint(min_dur, max(min_dur, min(max_dur, remaining)))
        patterns.append(dur)
        remaining -= dur

    return patterns

def section_type(bar):
    """Get section type for bar position."""
    if bar < 32: return 'intro'
    elif bar < 48: return 'buildup'
    elif bar < 80: return 'breakdown'
    elif bar < 112: return 'drop'
    elif bar < 128: return 'break'
    elif bar < 160: return 'breakdown'
    elif bar < 192: return 'drop'
    else: return 'outro'

# ============================================================================
# DYNAMIC CHORD GENERATOR
# ============================================================================

def generate_chords():
    """Generate clean chords in octave 4-5, no timing variation."""
    print("Generating clean chords (octave 4-5)...")

    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

    events = []
    current_tick = 0

    for chord_name, notes, bars in BASE_PROGRESSION:
        # Shift notes up one octave to get into octave 4-5 range
        chord_notes = [n + 12 for n in notes]
        duration = bars * ticks_per_bar - 10
        vel = 80

        # All notes start at exactly the same time
        for note in chord_notes:
            events.append((current_tick, 'on', note, vel))
        # All notes end at exactly the same time
        for note in chord_notes:
            events.append((current_tick + duration, 'off', note, 0))

        current_tick += bars * ticks_per_bar

    # Sort and write - ensures clean timing
    events.sort(key=lambda x: (x[0], 0 if x[1] == 'on' else 1))
    last_tick = 0
    for tick, evt, note, vel in events:
        delta = tick - last_tick
        if evt == 'on':
            track.append(Message('note_on', note=note, velocity=vel, time=delta))
        else:
            track.append(Message('note_off', note=note, velocity=0, time=delta))
        last_tick = tick

    mid.save(output_dir / "chords.mid")
    return mid

# ============================================================================
# DYNAMIC BASS GENERATOR
# ============================================================================

def generate_bass():
    """Generate bass with sustained notes."""
    print("Generating dynamic bass...")

    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

    # Bass roots in Octave 2 (F2=41, C2=36, etc.)
    bass_roots = {
        'Fm': 41, 'Db': 37, 'Ab': 44, 'Eb': 39, 'Cm': 36, 'Bb': 34, 'Bbm': 34,
        'Gb': 42, 'Dbmaj7': 37, 'Abmaj7': 44, 'Eb7': 39, 'Fm7': 41, 'C': 36,
        'Bbm7': 34, 'Gdim': 43, 'Ebsus4': 39
    }

    for chord_name, notes, bars in BASE_PROGRESSION:
        base = chord_name.replace('maj7', '').replace('m7', 'm').replace('7', '').replace('sus4', '').replace('dim', '')
        root = bass_roots.get(chord_name, bass_roots.get(base, 29))

        # Occasional octave variation
        if random.random() < 0.15:
            root += random.choice([-12, 12])

        duration = bars * ticks_per_bar - 10
        vel = random.randint(90, 110)

        track.append(Message('note_on', note=root, velocity=vel, time=0))
        track.append(Message('note_off', note=root, velocity=0, time=duration))

    mid.save(output_dir / "bass.mid")
    return mid

# ============================================================================
# DYNAMIC ARP GENERATOR
# ============================================================================

def generate_arp():
    """Generate arp with varied patterns."""
    print("Generating dynamic arp...")

    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

    # Random arp characteristics for this generation
    arp_style = random.choice(['up', 'down', 'updown', 'random', 'pattern'])
    octave_range = random.choice([1, 2])
    note_length = random.choice([0.7, 0.8, 0.9])  # Percentage of 16th

    print(f"  Arp style: {arp_style}, octaves: {octave_range}")

    current_bar = 0
    events = []

    for chord_name, notes, bars in BASE_PROGRESSION:
        sect = section_type(current_bar)
        chord_start = current_bar * ticks_per_bar

        # Build arp note pool
        base_notes = [n + 12 for n in notes[:3]]  # One octave up
        if octave_range == 2:
            base_notes += [n + 24 for n in notes[:3]]

        # Determine pattern for this chord
        if arp_style == 'up':
            pattern = sorted(base_notes)
        elif arp_style == 'down':
            pattern = sorted(base_notes, reverse=True)
        elif arp_style == 'updown':
            up = sorted(base_notes)
            pattern = up + up[-2:0:-1]
        elif arp_style == 'random':
            pattern = base_notes[:]
            random.shuffle(pattern)
        else:  # pattern - create rhythmic pattern
            pattern = [base_notes[i % len(base_notes)] for i in random.sample(range(8), min(6, len(base_notes) * 2))]

        # Generate notes
        num_16ths = bars * 16

        # Vary density by section
        if sect in ['breakdown', 'intro', 'outro']:
            skip_prob = 0.3
        else:
            skip_prob = 0.1

        for i in range(num_16ths):
            if random.random() < skip_prob:
                continue

            note = pattern[i % len(pattern)]

            # Occasional octave jump
            if random.random() < 0.05:
                note += random.choice([-12, 12])

            tick = chord_start + i * sixteenth
            dur = int(sixteenth * note_length)
            vel = random.randint(60, 95) if i % 4 == 0 else random.randint(50, 75)

            events.append((tick, 'on', note, vel))
            events.append((tick + dur, 'off', note, 0))

        current_bar += bars

    # Write events
    events.sort(key=lambda x: (x[0], 0 if x[1] == 'on' else 1))
    last_tick = 0
    for tick, evt, note, vel in events:
        delta = tick - last_tick
        if evt == 'on':
            track.append(Message('note_on', note=note, velocity=vel, time=delta))
        else:
            track.append(Message('note_off', note=note, velocity=0, time=delta))
        last_tick = tick

    mid.save(output_dir / "arp.mid")
    return mid

# ============================================================================
# DYNAMIC LEAD GENERATOR
# ============================================================================

def generate_lead():
    """Generate lead with all melodic techniques."""
    print("Generating dynamic lead...")

    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

    # Random melodic tendencies for this generation
    contour = random.choice(['rising', 'falling', 'arch', 'wave'])
    ornament_prob = random.uniform(0.1, 0.3)
    octave_jump_prob = random.uniform(0.05, 0.15)
    syncopation = random.uniform(0.1, 0.4)

    print(f"  Contour: {contour}, ornaments: {ornament_prob:.0%}, syncopation: {syncopation:.0%}")

    events = []
    current_bar = 0
    last_note = None
    phrase_direction = 1  # 1 = up, -1 = down

    for chord_idx, (chord_name, notes, bars) in enumerate(BASE_PROGRESSION):
        sect = section_type(current_bar)
        chord_start = current_bar * ticks_per_bar
        chord_ticks = bars * ticks_per_bar

        # Lead notes (2 octaves up from chord)
        lead_pool = [n + 24 for n in notes[:3]]

        # Determine density based on section
        if sect in ['drop']:
            density = 'dense'
        elif sect in ['breakdown', 'intro', 'outro']:
            density = 'sparse'
        else:
            density = 'normal'

        # Generate rhythm pattern
        rhythm = random_rhythm_pattern(bars * 16, density)

        tick_offset = 0
        note_idx = 0

        for dur_16ths in rhythm:
            if tick_offset >= chord_ticks:
                break

            # Choose note based on contour
            if contour == 'rising':
                note = lead_pool[min(note_idx % 3, 2)]
                note_idx += 1
            elif contour == 'falling':
                note = lead_pool[max(2 - (note_idx % 3), 0)]
                note_idx += 1
            elif contour == 'arch':
                cycle_pos = note_idx % 6
                if cycle_pos < 3:
                    note = lead_pool[cycle_pos]
                else:
                    note = lead_pool[5 - cycle_pos]
                note_idx += 1
            else:  # wave
                note = lead_pool[note_idx % len(lead_pool)]
                note_idx += phrase_direction
                if note_idx >= len(lead_pool) or note_idx < 0:
                    phrase_direction *= -1
                    note_idx = max(0, min(note_idx, len(lead_pool) - 1))

            # Octave jump
            if random.random() < octave_jump_prob:
                note += random.choice([-12, 12])

            # Add syncopation (shift note slightly)
            sync_shift = 0
            if random.random() < syncopation:
                sync_shift = random.choice([-sixteenth//2, sixteenth//2, sixteenth])

            note_tick = chord_start + tick_offset + sync_shift
            note_tick = max(chord_start, note_tick)  # Don't go before chord

            dur_ticks = dur_16ths * sixteenth - 30
            vel = random.randint(70, 95)

            # Add main note
            events.append((note_tick, 'on', note, vel))
            events.append((note_tick + dur_ticks, 'off', note, 0))

            # Add ornaments
            if random.random() < ornament_prob and dur_16ths >= 2:
                ornament_type = random.choice(['grace', 'neighbor', 'passing'])

                if ornament_type == 'grace':
                    # Grace note before main note
                    grace = get_neighbor(note, 'down')
                    grace_tick = max(chord_start, note_tick - sixteenth//2)
                    events.append((grace_tick, 'on', grace, vel - 20))
                    events.append((grace_tick + sixteenth//4, 'off', grace, 0))

                elif ornament_type == 'neighbor' and dur_16ths >= 3:
                    # Upper neighbor in middle
                    neighbor = get_neighbor(note, 'up')
                    n_tick = note_tick + sixteenth
                    events.append((n_tick, 'on', neighbor, vel - 15))
                    events.append((n_tick + sixteenth//2, 'off', neighbor, 0))

                elif ornament_type == 'passing' and last_note and dur_16ths >= 4:
                    # Passing tones
                    passing = get_passing_tones(last_note, note, 1)
                    for j, p in enumerate(passing):
                        p_tick = note_tick + (j + 1) * sixteenth
                        if p_tick < note_tick + dur_ticks - sixteenth:
                            events.append((p_tick, 'on', p, vel - 20))
                            events.append((p_tick + sixteenth//2, 'off', p, 0))

            last_note = note
            tick_offset += dur_16ths * sixteenth

        # Call and response - add "answer" phrase occasionally
        if random.random() < 0.3 and bars >= 2:
            answer_start = chord_start + chord_ticks // 2
            answer_notes = random.sample(lead_pool, min(3, len(lead_pool)))
            for i, ans_note in enumerate(answer_notes):
                t = answer_start + i * eighth
                events.append((t, 'on', ans_note, random.randint(60, 80)))
                events.append((t + eighth - 30, 'off', ans_note, 0))

        current_bar += bars

    # Sort and write
    events.sort(key=lambda x: (x[0], 0 if x[1] == 'on' else 1))
    last_tick = 0
    for tick, evt, note, vel in events:
        delta = max(0, tick - last_tick)
        if evt == 'on':
            track.append(Message('note_on', note=note, velocity=vel, time=delta))
        else:
            track.append(Message('note_off', note=note, velocity=0, time=delta))
        last_tick = tick

    mid.save(output_dir / "lead.mid")
    return mid

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("DYNAMIC MIDI GENERATOR")
    print(f"Seed: {int(time.time())}")
    print("=" * 60)

    generate_chords()
    generate_bass()
    generate_arp()
    generate_lead()

    print("\nAll MIDI files generated with unique variations!")
    print("Run again for a completely different result.")
