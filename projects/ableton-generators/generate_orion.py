#!/usr/bin/env python3
"""
Orion Inspired - Euphoric Trance Generator
Based on Arcana - Orion (144 BPM, C# major)
Includes all dynamic features: fills, rolls, ghost notes, clean timing
"""

from mido import MidiFile, MidiTrack, Message, MetaMessage
import mido
from pathlib import Path
import random
import time

random.seed(int(time.time() * 1000) % 2**32)

# Output to project folder
project_name = 'Orion_Inspired'
output_dir = Path(r'D:\OneDrive\Music\Projects\Ableton\Ableton Projects\TEMPLATE') / project_name / 'midi'
output_dir.mkdir(parents=True, exist_ok=True)

# Settings
ticks_per_beat = 480
ticks_per_bar = ticks_per_beat * 4
sixteenth = ticks_per_beat // 4
eighth = ticks_per_beat // 2
tempo = mido.bpm2tempo(144)

# Drum notes - Octave 4 (C4=60)
KICK = 60
SNARE = 62
CLAP = 63
CLOSED_HH = 66
OPEN_HH = 70

# C# major chord progression
PROGRESSION = [
    # INTRO (36 bars)
    ('C#', [61, 65, 68], 4), ('A#m', [58, 61, 65], 4), ('F#', [54, 58, 61], 4), ('G#', [56, 60, 63], 4),
    ('C#', [61, 65, 68], 4), ('A#m', [58, 61, 65], 4), ('F#', [54, 58, 61], 4), ('G#', [56, 60, 63], 4),
    ('C#', [61, 65, 68], 4),
    # BUILDUP (16 bars)
    ('C#', [61, 65, 68], 2), ('C#', [61, 65, 68], 2), ('A#m', [58, 61, 65], 2), ('A#m', [58, 61, 65], 2),
    ('F#', [54, 58, 61], 2), ('F#', [54, 58, 61], 2), ('G#', [56, 60, 63], 2), ('G#', [56, 60, 63], 2),
    # BREAKDOWN 1 (32 bars)
    ('C#', [61, 65, 68], 4), ('A#m', [58, 61, 65], 4), ('F#', [54, 58, 61], 4), ('G#', [56, 60, 63], 4),
    ('C#', [61, 65, 68], 4), ('D#m', [51, 54, 58], 4), ('F#', [54, 58, 61], 4), ('G#', [56, 60, 63], 4),
    # DROP 1 (32 bars)
    ('C#', [61, 65, 68], 2), ('C#', [61, 65, 68], 2), ('A#m', [58, 61, 65], 2), ('A#m', [58, 61, 65], 2),
    ('F#', [54, 58, 61], 2), ('F#', [54, 58, 61], 2), ('G#', [56, 60, 63], 2), ('G#', [56, 60, 63], 2),
    ('C#', [61, 65, 68], 2), ('A#m', [58, 61, 65], 2), ('D#m', [51, 54, 58], 2), ('G#', [56, 60, 63], 2),
    ('C#', [61, 65, 68], 2), ('F#', [54, 58, 61], 2), ('G#', [56, 60, 63], 2), ('G#', [56, 60, 63], 2),
    # BREAK (16 bars)
    ('C#', [61, 65, 68], 4), ('A#m', [58, 61, 65], 4), ('F#', [54, 58, 61], 4), ('G#', [56, 60, 63], 4),
    # BREAKDOWN 2 (32 bars)
    ('C#', [61, 65, 68], 4), ('A#m', [58, 61, 65], 4), ('D#m', [51, 54, 58], 4), ('G#', [56, 60, 63], 4),
    ('C#', [61, 65, 68], 4), ('F#', [54, 58, 61], 4), ('A#m', [58, 61, 65], 4), ('G#', [56, 60, 63], 4),
    # DROP 2 (32 bars)
    ('C#', [61, 65, 68], 2), ('C#', [61, 65, 68], 2), ('A#m', [58, 61, 65], 2), ('A#m', [58, 61, 65], 2),
    ('F#', [54, 58, 61], 2), ('F#', [54, 58, 61], 2), ('G#', [56, 60, 63], 2), ('G#', [56, 60, 63], 2),
    ('C#', [61, 65, 68], 2), ('D#m', [51, 54, 58], 2), ('F#', [54, 58, 61], 2), ('G#', [56, 60, 63], 2),
    ('C#', [61, 65, 68], 2), ('A#m', [58, 61, 65], 2), ('F#', [54, 58, 61], 2), ('G#', [56, 60, 63], 2),
    # OUTRO (32 bars)
    ('C#', [61, 65, 68], 8), ('A#m', [58, 61, 65], 8), ('F#', [54, 58, 61], 8), ('C#', [61, 65, 68], 8),
]

total_bars = sum(bars for _, _, bars in PROGRESSION)

# Section definitions (bar ranges) - matches the progression
SECTIONS = [
    ('intro', 0, 36, 0.3),
    ('buildup', 36, 52, 0.5),
    ('breakdown1', 52, 84, 0.4),
    ('drop1', 84, 116, 1.0),
    ('break', 116, 132, 0.6),
    ('breakdown2', 132, 164, 0.4),
    ('drop2', 164, 196, 1.0),
    ('outro', 196, 228, 0.2),
]

def get_section(bar):
    for name, start, end, energy in SECTIONS:
        if start <= bar < end:
            return name, energy
    return 'outro', 0.2

print('=' * 60)
print('ORION INSPIRED - Euphoric Trance Generator')
print('=' * 60)
print(f'BPM: 144, Key: C# major')
print(f'Total bars: {total_bars}')
print(f'Output: {output_dir}')

# ============ KICK with fills and ghost notes ============
def generate_kick():
    print('Generating dynamic kick...')
    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

    events = []

    for bar in range(total_bars):
        section, energy = get_section(bar)
        bar_start = bar * ticks_per_bar

        # Skip kick in breakdowns (mostly)
        if section in ['breakdown1', 'breakdown2'] and random.random() < 0.7:
            continue

        # Check if this is the last bar before a drop
        next_section, _ = get_section(bar + 1)
        is_pre_drop = section in ['buildup', 'break', 'breakdown1', 'breakdown2'] and next_section in ['drop1', 'drop2']

        if is_pre_drop:
            # Kick roll into drop - accelerating
            roll_pattern = [0, 4, 8, 10, 12, 13, 14, 15]
            for i, pos in enumerate(roll_pattern):
                tick = bar_start + pos * sixteenth
                vel = 80 + (i * 5)
                events.append((tick, 'on', KICK, min(vel, 127)))
                events.append((tick + sixteenth - 20, 'off', KICK, 0))
        else:
            # Normal four-on-the-floor
            for beat in range(4):
                tick = bar_start + beat * ticks_per_beat

                # Ghost kick before main hit
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

    events.sort(key=lambda x: (x[0], 0 if x[1] == 'on' else 1))
    last_tick = 0
    for tick, evt, note, vel in events:
        delta = max(0, tick - last_tick)
        track.append(Message('note_on' if evt == 'on' else 'note_off', note=note, velocity=vel, time=delta))
        last_tick = tick

    mid.save(output_dir / 'kick.mid')
    print(f'  Saved kick.mid with fills and ghost notes')

# ============ CLAP with rolls ============
def generate_clap():
    print('Generating dynamic clap...')
    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

    events = []

    for bar in range(total_bars):
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
                positions = [0, 4, 6, 8, 9, 10, 11, 12, 13, 14, 14.5, 15, 15.5]
            elif roll_style == '16ths':
                positions = list(range(16))
            else:
                positions = list(range(8)) + [x/2 + 8 for x in range(16)]

            for i, pos in enumerate(positions):
                tick = bar_start + int(pos * sixteenth)
                vel = 60 + int((i / len(positions)) * 50)
                events.append((tick, 'on', SNARE, min(vel, 120)))
                events.append((tick + sixteenth//2, 'off', SNARE, 0))
        else:
            # Standard clap on 2 and 4
            for beat in [1, 3]:
                tick = bar_start + beat * ticks_per_beat
                vel = random.randint(90, 110)
                events.append((tick, 'on', CLAP, vel))
                events.append((tick + sixteenth * 2, 'off', CLAP, 0))

                # Occasional flam
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

    events.sort(key=lambda x: (x[0], 0 if x[1] == 'on' else 1))
    last_tick = 0
    for tick, evt, note, vel in events:
        delta = max(0, tick - last_tick)
        track.append(Message('note_on' if evt == 'on' else 'note_off', note=note, velocity=vel, time=delta))
        last_tick = tick

    mid.save(output_dir / 'clap.mid')
    print(f'  Saved clap.mid with rolls and ghost snares')

# ============ HATS - offbeat with transition rolls ============
def generate_hats():
    print('Generating dynamic hats...')
    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

    events = []
    OFFBEAT_POSITIONS = [2, 6, 10, 14]

    for bar in range(total_bars):
        section, energy = get_section(bar)
        bar_start = bar * ticks_per_bar

        # Sparse in intro/outro
        if section in ['intro', 'outro'] and random.random() < 0.4:
            continue

        next_section, _ = get_section(bar + 1)
        is_pre_drop = section in ['buildup', 'breakdown1', 'breakdown2'] and next_section in ['drop1', 'drop2']

        if is_pre_drop:
            # Hi-hat roll building into drop
            for i in range(32):
                tick = bar_start + i * (sixteenth // 2)

                if i < 8:
                    if i % 2 != 0:
                        continue
                elif i < 16:
                    pass

                vel = 50 + int((i / 32) * 60)
                note = OPEN_HH if i >= 28 else CLOSED_HH
                events.append((tick, 'on', note, min(vel, 110)))
                events.append((tick + sixteenth//4, 'off', note, 0))
        else:
            # Normal offbeat pattern - no variation
            for pos in OFFBEAT_POSITIONS:
                tick = bar_start + pos * sixteenth
                vel = random.randint(88, 98)
                events.append((tick, 'on', CLOSED_HH, vel))
                events.append((tick + sixteenth - 20, 'off', CLOSED_HH, 0))

    events.sort(key=lambda x: (x[0], 0 if x[1] == 'on' else 1))
    last_tick = 0
    for tick, evt, note, vel in events:
        delta = max(0, tick - last_tick)
        track.append(Message('note_on' if evt == 'on' else 'note_off', note=note, velocity=vel, time=delta))
        last_tick = tick

    mid.save(output_dir / 'hats.mid')
    print(f'  Saved hats.mid with transition rolls')

# ============ BASS - simple 2 note (C#2/G#2) ============
def generate_bass():
    print('Generating bass (C#2/G#2)...')
    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

    CS2 = 37
    GS2 = 44
    bass_pattern = [(CS2, 4), (GS2, 4)]
    pattern_idx = 0
    current_bar = 0

    while current_bar < total_bars:
        note, bars = bass_pattern[pattern_idx % len(bass_pattern)]
        bars = min(bars, total_bars - current_bar)
        duration = bars * ticks_per_bar - 10
        track.append(Message('note_on', note=note, velocity=100, time=0))
        track.append(Message('note_off', note=note, velocity=0, time=duration))
        current_bar += bars
        pattern_idx += 1

    mid.save(output_dir / 'bass.mid')
    print(f'  Saved bass.mid (C#2/G#2, 4 bars each)')

# ============ CHORDS - clean timing, octave 4-5 ============
def generate_chords():
    print('Generating chords (octave 4-5, clean timing)...')
    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

    events = []
    current_tick = 0

    for chord_name, notes, bars in PROGRESSION:
        chord_notes = [n + 12 for n in notes]
        duration = bars * ticks_per_bar - 10
        for note in chord_notes:
            events.append((current_tick, 'on', note, 80))
            events.append((current_tick + duration, 'off', note, 0))
        current_tick += bars * ticks_per_bar

    events.sort(key=lambda x: (x[0], 0 if x[1] == 'on' else 1))
    last_tick = 0
    for tick, evt, note, vel in events:
        delta = tick - last_tick
        track.append(Message('note_on' if evt == 'on' else 'note_off', note=note, velocity=vel, time=delta))
        last_tick = tick

    mid.save(output_dir / 'chords.mid')
    print(f'  Saved chords.mid')

# ============ ARP ============
def generate_arp():
    print('Generating arp...')
    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

    events = []
    current_tick = 0

    for chord_name, notes, bars in PROGRESSION:
        arp_notes = [n + 24 for n in notes]
        chord_ticks = bars * ticks_per_bar
        for i in range(bars * 16):
            note = arp_notes[i % len(arp_notes)]
            tick = current_tick + i * sixteenth
            vel = 85 if i % 4 == 0 else 65
            events.append((tick, 'on', note, vel))
            events.append((tick + sixteenth - 30, 'off', note, 0))
        current_tick += chord_ticks

    events.sort(key=lambda x: (x[0], 0 if x[1] == 'on' else 1))
    last_tick = 0
    for tick, evt, note, vel in events:
        delta = tick - last_tick
        track.append(Message('note_on' if evt == 'on' else 'note_off', note=note, velocity=vel, time=delta))
        last_tick = tick

    mid.save(output_dir / 'arp.mid')
    print(f'  Saved arp.mid')

# ============ LEAD with variations ============
def generate_lead():
    print('Generating lead melody...')
    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

    events = []
    current_tick = 0

    for chord_name, notes, bars in PROGRESSION:
        lead_notes = [n + 24 for n in notes[:2]]
        chord_ticks = bars * ticks_per_bar
        rhythm = [4, 4, 2, 2, 4]
        note_idx = 0
        tick_offset = 0

        while tick_offset < chord_ticks:
            dur = rhythm[note_idx % len(rhythm)] * sixteenth
            note = lead_notes[note_idx % len(lead_notes)]
            if random.random() < 0.1:
                note += 12

            tick = current_tick + tick_offset
            events.append((tick, 'on', note, 85))
            events.append((tick + dur - 30, 'off', note, 0))

            tick_offset += dur
            note_idx += 1

        current_tick += chord_ticks

    events.sort(key=lambda x: (x[0], 0 if x[1] == 'on' else 1))
    last_tick = 0
    for tick, evt, note, vel in events:
        delta = tick - last_tick
        track.append(Message('note_on' if evt == 'on' else 'note_off', note=note, velocity=vel, time=delta))
        last_tick = tick

    mid.save(output_dir / 'lead.mid')
    print(f'  Saved lead.mid')

# Run all generators
if __name__ == "__main__":
    generate_kick()
    generate_clap()
    generate_hats()
    generate_bass()
    generate_chords()
    generate_arp()
    generate_lead()

    print(f'\nGenerated {total_bars} bars of euphoric trance with all dynamic features!')
