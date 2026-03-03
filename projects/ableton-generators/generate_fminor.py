#!/usr/bin/env python3
"""Generate all MIDI files in F minor with sustained bass."""

import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage
from pathlib import Path

# Output directory
output_dir = Path(r"D:\OneDrive\Music\Projects\Ableton\Ableton Projects\TEMPLATE\BabyBoomers_Final\midi")

# F minor chord progression
# Format: (chord_name, [chord_notes], bars)
progression = [
    # INTRO (32 bars) - 2 bars per chord
    ('Fm', [41, 48, 53], 2), ('Db', [49, 53, 56], 2), ('Ab', [32, 48, 51], 2), ('Eb', [39, 46, 51], 2),
    ('Fm', [41, 48, 53], 2), ('Cm', [36, 48, 51], 2), ('Bb', [34, 46, 50], 2), ('Bbm', [34, 46, 49], 2),
    ('Fm', [41, 48, 53], 2), ('Db', [49, 53, 56], 2), ('Ab', [32, 48, 51], 2), ('Eb', [39, 46, 51], 2),
    ('Fm', [41, 48, 53], 2), ('Gb', [30, 46, 49], 2), ('Db', [49, 53, 56], 2), ('Eb', [39, 46, 51], 2),

    # BUILDUP A (16 bars) - 1 bar per chord
    ('Fm', [41, 48, 53], 1), ('Fm', [41, 48, 53], 1), ('Gb', [30, 46, 49], 1), ('Gb', [30, 46, 49], 1),
    ('Db', [49, 53, 56], 1), ('Dbmaj7', [49, 53, 56, 60], 1), ('Ab', [32, 48, 51], 1), ('Abmaj7', [32, 48, 51, 55], 1),
    ('Eb', [39, 46, 51], 1), ('Eb7', [39, 46, 51, 57], 1), ('Fm', [41, 48, 53], 1), ('Fm7', [41, 48, 53, 59], 1),
    ('Dbmaj7', [49, 53, 56, 60], 1), ('C', [36, 48, 52], 1), ('Bbm7', [34, 46, 49, 53], 1), ('Eb', [39, 46, 51], 2),

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

ticks_per_beat = 480
ticks_per_bar = ticks_per_beat * 4
tempo = mido.bpm2tempo(140)

# Bass root notes (low octave, F1 = 29)
bass_roots = {
    'Fm': 29, 'Db': 25, 'Ab': 32, 'Eb': 27, 'Cm': 24, 'Bb': 22, 'Bbm': 22,
    'Gb': 30, 'Dbmaj7': 25, 'Abmaj7': 32, 'Eb7': 27, 'Fm7': 29, 'C': 24,
    'Bbm7': 22, 'Gdim': 31, 'Ebsus4': 27
}

def get_bass_root(chord_name):
    if chord_name in bass_roots:
        return bass_roots[chord_name]
    # Strip extensions
    base = chord_name.replace('maj7', '').replace('m7', 'm').replace('7', '').replace('sus4', '').replace('dim', '')
    if base in bass_roots:
        return bass_roots[base]
    return 29  # Default to F

# ========== CHORDS ==========
print("Generating chords.mid...")
mid = MidiFile(ticks_per_beat=ticks_per_beat)
track = MidiTrack()
mid.tracks.append(track)
track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

for chord_name, notes, bars in progression:
    duration = bars * ticks_per_bar - 10
    # Note on for all chord notes
    for i, note in enumerate(notes):
        track.append(Message('note_on', note=note, velocity=80, time=0))
    # Note off for all chord notes
    for i, note in enumerate(notes):
        track.append(Message('note_off', note=note, velocity=0, time=duration if i == 0 else 0))

mid.save(output_dir / "chords.mid")
print(f"  Saved chords.mid ({len(progression)} chords)")

# ========== BASS (long sustained notes, no jumps) ==========
print("Generating bass.mid...")
mid = MidiFile(ticks_per_beat=ticks_per_beat)
track = MidiTrack()
mid.tracks.append(track)
track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

for chord_name, notes, bars in progression:
    root = get_bass_root(chord_name)
    duration = bars * ticks_per_bar - 10

    track.append(Message('note_on', note=root, velocity=100, time=0))
    track.append(Message('note_off', note=root, velocity=0, time=duration))

mid.save(output_dir / "bass.mid")
print(f"  Saved bass.mid (sustained root notes)")

# ========== ARP ==========
print("Generating arp.mid...")
mid = MidiFile(ticks_per_beat=ticks_per_beat)
track = MidiTrack()
mid.tracks.append(track)
track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

sixteenth = ticks_per_beat // 4

for chord_name, notes, bars in progression:
    chord_ticks = bars * ticks_per_bar
    num_16ths = chord_ticks // sixteenth

    # Arp pattern: cycle through chord tones + octave up
    arp_notes = list(notes[:3]) + [notes[0] + 12]

    for i in range(num_16ths):
        note = arp_notes[i % len(arp_notes)] + 12  # Up an octave from chord
        vel = 90 if i % 4 == 0 else 70
        dur = sixteenth - 30
        gap = 30

        delta = 0 if i == 0 else gap
        track.append(Message('note_on', note=note, velocity=vel, time=delta))
        track.append(Message('note_off', note=note, velocity=0, time=dur))

mid.save(output_dir / "arp.mid")
print(f"  Saved arp.mid (16th note arpeggios)")

# ========== LEAD ==========
print("Generating lead.mid...")
mid = MidiFile(ticks_per_beat=ticks_per_beat)
track = MidiTrack()
mid.tracks.append(track)
track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

for chord_name, notes, bars in progression:
    # Lead plays chord tones 2 octaves up
    lead_notes = [n + 24 for n in notes[:3]]
    beat_ticks = ticks_per_beat

    for beat in range(bars * 4):
        note_idx = beat % 4
        if note_idx < 3:
            note = lead_notes[note_idx]
        else:
            note = lead_notes[1]  # back to 3rd

        vel = 85 if beat % 4 == 0 else 70
        dur = beat_ticks - 60
        gap = 60

        delta = 0 if beat == 0 else gap
        track.append(Message('note_on', note=note, velocity=vel, time=delta))
        track.append(Message('note_off', note=note, velocity=0, time=dur))

mid.save(output_dir / "lead.mid")
print(f"  Saved lead.mid (melodic phrases)")

print("\nAll MIDI files regenerated in F minor!")
