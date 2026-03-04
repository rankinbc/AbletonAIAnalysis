#!/usr/bin/env python3
"""
Dynamic Drum Generator - Adds fills, rolls, ghost notes
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

# Drum notes - Octave 4 (C4=60)
KICK = 60        # C4
SNARE = 62       # D4
CLAP = 63        # D#4
CLOSED_HH = 66   # F#4
OPEN_HH = 70     # A#4
TOM_LOW = 65     # F4
TOM_MID = 67     # G4
TOM_HIGH = 69    # A4
CRASH = 61       # C#4
RIDE = 71        # B4

# Section definitions (bar ranges)
SECTIONS = [
    ('intro', 0, 32, 0.3),
    ('buildup', 32, 48, 0.5),
    ('breakdown1', 48, 80, 0.4),
    ('drop1', 80, 112, 1.0),
    ('break', 112, 128, 0.6),
    ('breakdown2', 128, 160, 0.4),
    ('drop2', 160, 192, 1.0),
    ('outro', 192, 224, 0.2),
]

def get_section(bar):
    for name, start, end, energy in SECTIONS:
        if start <= bar < end:
            return name, energy
    return 'outro', 0.2

def generate_kick():
    """Generate kick with variations and fills."""
    print("Generating dynamic kick...")

    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

    events = []

    for bar in range(224):
        section, energy = get_section(bar)
        bar_start = bar * ticks_per_bar

        # Skip kick in breakdowns (mostly)
        if section in ['breakdown1', 'breakdown2'] and random.random() < 0.7:
            continue

        # Check if this is the last bar before a drop (fill opportunity)
        next_section, _ = get_section(bar + 1)
        is_pre_drop = section in ['buildup', 'break', 'breakdown1', 'breakdown2'] and next_section in ['drop1', 'drop2']

        if is_pre_drop:
            # Kick roll into drop - accelerating kicks
            roll_pattern = [0, 4, 8, 10, 12, 13, 14, 15]  # 16ths, accelerating
            for i, pos in enumerate(roll_pattern):
                tick = bar_start + pos * sixteenth
                vel = 80 + (i * 5)  # Building velocity
                events.append((tick, 'on', KICK, min(vel, 127)))
                events.append((tick + sixteenth - 20, 'off', KICK, 0))
        else:
            # Normal four-on-the-floor with subtle variations
            for beat in range(4):
                tick = bar_start + beat * ticks_per_beat

                # Occasional ghost kick before main hit
                if random.random() < 0.1 and beat > 0:
                    ghost_tick = tick - sixteenth
                    events.append((ghost_tick, 'on', KICK, 50))
                    events.append((ghost_tick + sixteenth - 30, 'off', KICK, 0))

                # Main kick
                vel = random.randint(95, 110) if energy > 0.5 else random.randint(80, 95)
                events.append((tick, 'on', KICK, vel))
                events.append((tick + sixteenth * 2, 'off', KICK, 0))

                # Occasional offbeat kick in drops
                if section in ['drop1', 'drop2'] and random.random() < 0.15:
                    off_tick = tick + eighth + sixteenth
                    events.append((off_tick, 'on', KICK, 70))
                    events.append((off_tick + sixteenth, 'off', KICK, 0))

    # Write events
    events.sort(key=lambda x: (x[0], 0 if x[1] == 'on' else 1))
    last_tick = 0
    for tick, evt, note, vel in events:
        delta = max(0, tick - last_tick)
        track.append(Message('note_on' if evt == 'on' else 'note_off', note=note, velocity=vel, time=delta))
        last_tick = tick

    mid.save(output_dir / "kick.mid")
    print(f"  Saved kick.mid with fills and ghost notes")

def generate_clap():
    """Generate clap/snare with rolls and fills."""
    print("Generating dynamic clap...")

    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

    events = []

    for bar in range(224):
        section, energy = get_section(bar)
        bar_start = bar * ticks_per_bar

        # Skip in intro/outro mostly
        if section in ['intro', 'outro'] and random.random() < 0.8:
            continue

        # Skip in breakdowns
        if section in ['breakdown1', 'breakdown2'] and random.random() < 0.6:
            continue

        next_section, _ = get_section(bar + 1)
        is_pre_drop = section in ['buildup', 'breakdown1', 'breakdown2'] and next_section in ['drop1', 'drop2']

        if is_pre_drop:
            # Snare roll building into drop
            roll_style = random.choice(['accelerating', '16ths', '32nds'])

            if roll_style == 'accelerating':
                # Start slow, get faster
                positions = [0, 4, 6, 8, 9, 10, 11, 12, 13, 14, 14.5, 15, 15.5]
            elif roll_style == '16ths':
                positions = list(range(16))
            else:  # 32nds in last half
                positions = list(range(8)) + [x/2 + 8 for x in range(16)]

            for i, pos in enumerate(positions):
                tick = bar_start + int(pos * sixteenth)
                vel = 60 + int((i / len(positions)) * 50)  # Building
                events.append((tick, 'on', SNARE, min(vel, 120)))
                events.append((tick + sixteenth//2, 'off', SNARE, 0))
        else:
            # Standard clap on 2 and 4
            for beat in [1, 3]:  # Beats 2 and 4 (0-indexed)
                tick = bar_start + beat * ticks_per_beat
                vel = random.randint(90, 110)
                events.append((tick, 'on', CLAP, vel))
                events.append((tick + sixteenth * 2, 'off', CLAP, 0))

                # Occasional flam (double hit)
                if random.random() < 0.1:
                    flam_tick = tick + sixteenth // 4
                    events.append((flam_tick, 'on', CLAP, vel - 20))
                    events.append((flam_tick + sixteenth, 'off', CLAP, 0))

            # Ghost snares in drops
            if section in ['drop1', 'drop2'] and random.random() < 0.2:
                ghost_positions = random.sample([2, 6, 10, 14], k=random.randint(1, 2))
                for pos in ghost_positions:
                    tick = bar_start + pos * sixteenth
                    events.append((tick, 'on', SNARE, random.randint(40, 60)))
                    events.append((tick + sixteenth, 'off', SNARE, 0))

    # Write events
    events.sort(key=lambda x: (x[0], 0 if x[1] == 'on' else 1))
    last_tick = 0
    for tick, evt, note, vel in events:
        delta = max(0, tick - last_tick)
        track.append(Message('note_on' if evt == 'on' else 'note_off', note=note, velocity=vel, time=delta))
        last_tick = tick

    mid.save(output_dir / "clap.mid")
    print(f"  Saved clap.mid with rolls and ghost snares")

def generate_hats():
    """Generate hi-hats - offbeat pattern with rolls only in transitions."""
    print("Generating dynamic hats...")

    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

    events = []

    # Classic trance offbeat positions - consistent throughout
    OFFBEAT_POSITIONS = [2, 6, 10, 14]
    print(f"  Hat style: offbeat (positions {OFFBEAT_POSITIONS})")

    for bar in range(224):
        section, energy = get_section(bar)
        bar_start = bar * ticks_per_bar

        # Sparse in intro/outro
        if section in ['intro', 'outro'] and random.random() < 0.4:
            continue

        next_section, _ = get_section(bar + 1)
        is_pre_drop = section in ['buildup', 'breakdown1', 'breakdown2'] and next_section in ['drop1', 'drop2']

        if is_pre_drop:
            # Hi-hat roll building into drop - THIS is where variation happens
            # Start with 8ths, move to 16ths, then 32nds
            for i in range(32):  # 32nd notes
                tick = bar_start + i * (sixteenth // 2)

                # Accelerate: first half slower
                if i < 8:
                    if i % 2 != 0:
                        continue  # Skip to make 16ths
                elif i < 16:
                    pass  # 16ths
                # else: 32nds in last half

                vel = 50 + int((i / 32) * 60)
                note = OPEN_HH if i >= 28 else CLOSED_HH
                events.append((tick, 'on', note, min(vel, 110)))
                events.append((tick + sixteenth//4, 'off', note, 0))
        else:
            # Normal pattern - ALWAYS offbeat, no variation
            for pos in OFFBEAT_POSITIONS:
                tick = bar_start + pos * sixteenth

                # Consistent velocity with slight humanization
                vel = random.randint(88, 98)

                # Always closed hat in normal sections
                note = CLOSED_HH

                events.append((tick, 'on', note, vel))
                events.append((tick + sixteenth - 20, 'off', note, 0))

    # Write events
    events.sort(key=lambda x: (x[0], 0 if x[1] == 'on' else 1))
    last_tick = 0
    for tick, evt, note, vel in events:
        delta = max(0, tick - last_tick)
        track.append(Message('note_on' if evt == 'on' else 'note_off', note=note, velocity=vel, time=delta))
        last_tick = tick

    mid.save(output_dir / "hats.mid")
    print(f"  Saved hats.mid with rolls and ghost hits")


if __name__ == "__main__":
    print("=" * 60)
    print("DYNAMIC DRUM GENERATOR")
    print("=" * 60)

    generate_kick()
    generate_clap()
    generate_hats()

    print("\nDrum MIDI files generated with fills and variations!")
