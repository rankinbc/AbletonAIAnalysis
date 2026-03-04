#!/usr/bin/env python3
"""
Expand 42-3-1 composition from 128 bars to 224 bars

Current structure (128 bars):
  0-24: Intro/Build
  24-32: Transition
  32-80: Drop 1 / Main
  80-112: Variation
  112-128: Brief outro

New structure (224 bars):
  0-24: Intro (keep)
  24-32: Build (keep)
  32-80: Drop 1 (keep)
  80-112: Variation (keep)
  112-128: Breakdown intro (modify)
  128-160: Full Breakdown (NEW)
  160-168: Build 2 (NEW)
  168-200: Drop 2 (NEW)
  200-224: Outro (NEW)
"""

import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage
import os
from pathlib import Path

# Output directory
OUTPUT_DIR = Path("D:/OneDrive/Music/Projects/Ableton/Ableton Projects/42 Project/expanded_midi")
OUTPUT_DIR.mkdir(exist_ok=True)

# 140 BPM
BPM = 140
TICKS_PER_BEAT = 480
TICKS_PER_BAR = TICKS_PER_BEAT * 4
MICROSECONDS_PER_BEAT = int(60_000_000 / BPM)

# Total bars
TOTAL_BARS = 224

# Section definitions
SECTIONS = {
    'intro': (0, 24),
    'build1': (24, 32),
    'drop1': (32, 80),
    'variation': (80, 112),
    'breakdown_intro': (112, 128),
    'breakdown': (128, 160),
    'build2': (160, 168),
    'drop2': (168, 200),
    'outro': (200, 224)
}

# Drum notes (Octave 4)
KICK = 60
SNARE = 62
CLAP = 63
CLOSED_HH = 66
OPEN_HH = 70
CRASH = 72

def create_midi_file():
    mid = MidiFile(ticks_per_beat=TICKS_PER_BEAT)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('set_tempo', tempo=MICROSECONDS_PER_BEAT, time=0))
    return mid, track

def add_note(track, note, velocity, duration, delta=0):
    track.append(Message('note_on', note=note, velocity=velocity, time=delta))
    track.append(Message('note_off', note=note, velocity=0, time=duration))

def generate_kick_expanded():
    """Generate expanded kick pattern with dynamic fills"""
    mid, track = create_midi_file()

    current_tick = 0
    events = []

    for bar in range(TOTAL_BARS):
        bar_start = bar * TICKS_PER_BAR

        # Determine section
        if bar < 8:
            # Intro - sparse kick (every 2 bars)
            if bar % 2 == 0:
                events.append((bar_start, KICK, 100, TICKS_PER_BEAT // 2))
        elif bar < 24:
            # Building intro - kick on 1 and 3
            events.append((bar_start, KICK, 100, TICKS_PER_BEAT // 2))
            events.append((bar_start + TICKS_PER_BEAT * 2, KICK, 90, TICKS_PER_BEAT // 2))
        elif bar < 32:
            # Build section - four on floor starting
            for beat in range(4):
                events.append((bar_start + beat * TICKS_PER_BEAT, KICK, 100, TICKS_PER_BEAT // 2))
        elif 32 <= bar < 112:
            # Drop 1 + Variation - full four on floor with ghost notes
            for beat in range(4):
                events.append((bar_start + beat * TICKS_PER_BEAT, KICK, 110, TICKS_PER_BEAT // 2))
                # Ghost kicks on offbeats (16th note subdivision)
                if beat < 3 and bar % 4 == 3:  # Add ghost on last bar of 4-bar phrase
                    events.append((bar_start + beat * TICKS_PER_BEAT + TICKS_PER_BEAT // 2, KICK, 50, TICKS_PER_BEAT // 4))
        elif 112 <= bar < 128:
            # Breakdown intro - kick dropping out gradually
            if bar < 120:
                for beat in range(4):
                    events.append((bar_start + beat * TICKS_PER_BEAT, KICK, 90 - (bar - 112) * 5, TICKS_PER_BEAT // 2))
            elif bar < 124:
                events.append((bar_start, KICK, 70, TICKS_PER_BEAT // 2))
                events.append((bar_start + TICKS_PER_BEAT * 2, KICK, 60, TICKS_PER_BEAT // 2))
        elif 128 <= bar < 160:
            # Full breakdown - NO kick (emotional section)
            pass
        elif 160 <= bar < 168:
            # Build 2 - kick returns with building intensity
            build_progress = bar - 160
            if build_progress < 2:
                events.append((bar_start, KICK, 70, TICKS_PER_BEAT // 2))
            elif build_progress < 4:
                events.append((bar_start, KICK, 80, TICKS_PER_BEAT // 2))
                events.append((bar_start + TICKS_PER_BEAT * 2, KICK, 75, TICKS_PER_BEAT // 2))
            else:
                for beat in range(4):
                    events.append((bar_start + beat * TICKS_PER_BEAT, KICK, 90 + build_progress * 2, TICKS_PER_BEAT // 2))
        elif 168 <= bar < 200:
            # Drop 2 - full power with more fills
            for beat in range(4):
                events.append((bar_start + beat * TICKS_PER_BEAT, KICK, 115, TICKS_PER_BEAT // 2))
            # More aggressive ghost notes
            if bar % 2 == 1:
                events.append((bar_start + TICKS_PER_BEAT * 3 + TICKS_PER_BEAT // 2, KICK, 55, TICKS_PER_BEAT // 4))
        elif bar >= 200:
            # Outro - kick fading out
            outro_bar = bar - 200
            if outro_bar < 16:
                vel = max(50, 100 - outro_bar * 4)
                for beat in range(4):
                    events.append((bar_start + beat * TICKS_PER_BEAT, KICK, vel, TICKS_PER_BEAT // 2))
            elif outro_bar < 20:
                events.append((bar_start, KICK, 60, TICKS_PER_BEAT // 2))
                events.append((bar_start + TICKS_PER_BEAT * 2, KICK, 50, TICKS_PER_BEAT // 2))

    # Sort and write events
    events.sort(key=lambda x: x[0])
    for tick, note, vel, dur in events:
        delta = tick - current_tick
        add_note(track, note, vel, dur, delta)
        current_tick = tick + dur

    track.append(MetaMessage('end_of_track', time=0))
    mid.save(OUTPUT_DIR / 'kick_expanded.mid')
    print(f"Created: kick_expanded.mid ({TOTAL_BARS} bars)")

def generate_clap_expanded():
    """Generate expanded clap with rolls before drops"""
    mid, track = create_midi_file()

    events = []

    for bar in range(TOTAL_BARS):
        bar_start = bar * TICKS_PER_BAR

        # Claps on beats 2 and 4 in drop/main sections
        if (32 <= bar < 112) or (168 <= bar < 200):
            events.append((bar_start + TICKS_PER_BEAT, CLAP, 100, TICKS_PER_BEAT // 2))
            events.append((bar_start + TICKS_PER_BEAT * 3, CLAP, 100, TICKS_PER_BEAT // 2))

        # Pre-drop clap rolls (bar before drops)
        if bar in [31, 167]:  # Before drop 1 and drop 2
            # 16th note clap roll
            for i in range(16):
                tick = bar_start + i * (TICKS_PER_BAR // 16)
                vel = 70 + int(i * 2.5)  # Building intensity
                events.append((tick, CLAP, vel, TICKS_PER_BEAT // 4))

        # Breakdown clap accents (sparse emotional hits)
        if 140 <= bar < 156:
            if bar % 4 == 0:
                events.append((bar_start + TICKS_PER_BEAT * 2, CLAP, 60, TICKS_PER_BEAT))

        # Outro claps (fading)
        if 200 <= bar < 216:
            outro_bar = bar - 200
            vel = max(50, 90 - outro_bar * 3)
            events.append((bar_start + TICKS_PER_BEAT, CLAP, vel, TICKS_PER_BEAT // 2))
            events.append((bar_start + TICKS_PER_BEAT * 3, CLAP, vel, TICKS_PER_BEAT // 2))

    events.sort(key=lambda x: x[0])
    current_tick = 0
    for tick, note, vel, dur in events:
        delta = tick - current_tick
        add_note(track, note, vel, dur, delta)
        current_tick = tick + dur

    track.append(MetaMessage('end_of_track', time=0))
    mid.save(OUTPUT_DIR / 'clap_expanded.mid')
    print(f"Created: clap_expanded.mid")

def generate_hats_expanded():
    """Generate expanded hat patterns - offbeat with transition rolls"""
    mid, track = create_midi_file()

    events = []
    offbeat_positions = [2, 6, 10, 14]  # 16th positions
    sixteenth = TICKS_PER_BAR // 16

    for bar in range(TOTAL_BARS):
        bar_start = bar * TICKS_PER_BAR

        # Determine section
        if bar < 24:
            # Intro - sparse hats
            if bar >= 8:
                for pos in [6, 14]:
                    events.append((bar_start + pos * sixteenth, 'on', CLOSED_HH, 70))
                    events.append((bar_start + pos * sixteenth + sixteenth - 10, 'off', CLOSED_HH, 0))
        elif 24 <= bar < 32:
            # Build - more hats
            for pos in offbeat_positions:
                events.append((bar_start + pos * sixteenth, 'on', CLOSED_HH, 80))
                events.append((bar_start + pos * sixteenth + sixteenth - 10, 'off', CLOSED_HH, 0))
        elif (32 <= bar < 112) or (168 <= bar < 200):
            # Drop sections - full offbeat hats with open hat accents
            for pos in offbeat_positions:
                events.append((bar_start + pos * sixteenth, 'on', CLOSED_HH, 90))
                events.append((bar_start + pos * sixteenth + sixteenth - 10, 'off', CLOSED_HH, 0))
            # Open hat on beat 4.5 every 2 bars
            if bar % 2 == 1:
                events.append((bar_start + 14 * sixteenth, 'on', OPEN_HH, 85))
                events.append((bar_start + 14 * sixteenth + sixteenth * 2 - 10, 'off', OPEN_HH, 0))
        elif 112 <= bar < 128:
            # Breakdown intro - hats thinning
            for pos in [6, 14]:
                events.append((bar_start + pos * sixteenth, 'on', CLOSED_HH, 70))
                events.append((bar_start + pos * sixteenth + sixteenth - 10, 'off', CLOSED_HH, 0))
        elif 128 <= bar < 160:
            # Full breakdown - very sparse hats
            if bar % 4 == 0:
                events.append((bar_start + 6 * sixteenth, 'on', CLOSED_HH, 50))
                events.append((bar_start + 6 * sixteenth + sixteenth - 10, 'off', CLOSED_HH, 0))
        elif 160 <= bar < 168:
            # Build 2 - hats building with rolls
            build_bar = bar - 160
            if build_bar < 4:
                for pos in [6, 14]:
                    events.append((bar_start + pos * sixteenth, 'on', CLOSED_HH, 70 + build_bar * 5))
                    events.append((bar_start + pos * sixteenth + sixteenth - 10, 'off', CLOSED_HH, 0))
            else:
                # Hat roll building to drop
                for i in range(16):
                    vel = min(60 + i * 3 + (build_bar - 4) * 5, 110)
                    events.append((bar_start + i * sixteenth, 'on', CLOSED_HH, vel))
                    events.append((bar_start + i * sixteenth + sixteenth // 2, 'off', CLOSED_HH, 0))
        elif 200 <= bar < 220:
            # Outro - hats fading
            for pos in offbeat_positions:
                vel = max(50, 80 - (bar - 200) * 2)
                events.append((bar_start + pos * sixteenth, 'on', CLOSED_HH, vel))
                events.append((bar_start + pos * sixteenth + sixteenth - 10, 'off', CLOSED_HH, 0))

        # Transition rolls before drops (avoid duplicate at bars with offbeats)
        if bar == 31 or bar == 167:
            for i in range(16):
                # Skip positions that overlap with offbeats
                if bar != 31 or i not in offbeat_positions:
                    vel = 70 + i * 2
                    events.append((bar_start + i * sixteenth, 'on', CLOSED_HH, vel))
                    events.append((bar_start + i * sixteenth + sixteenth // 2 - 5, 'off', CLOSED_HH, 0))

    # Sort events by time, then note_off before note_on at same tick
    events.sort(key=lambda x: (x[0], 0 if x[1] == 'off' else 1))

    current_tick = 0
    for tick, event_type, note, vel in events:
        delta = max(0, tick - current_tick)  # Safety clamp
        if event_type == 'on':
            track.append(Message('note_on', note=note, velocity=vel, time=delta))
        else:
            track.append(Message('note_off', note=note, velocity=0, time=delta))
        current_tick = tick

    track.append(MetaMessage('end_of_track', time=0))
    mid.save(OUTPUT_DIR / 'hats_expanded.mid')
    print(f"Created: hats_expanded.mid")

def generate_crash_expanded():
    """Generate crash hits at key moments"""
    mid, track = create_midi_file()

    events = []

    # Crash on drop starts and key moments
    crash_bars = [32, 48, 64, 80, 96, 128, 160, 168, 184, 200]

    for bar in crash_bars:
        if bar < TOTAL_BARS:
            bar_start = bar * TICKS_PER_BAR
            events.append((bar_start, CRASH, 110, TICKS_PER_BAR // 2))

    events.sort(key=lambda x: x[0])
    current_tick = 0
    for tick, note, vel, dur in events:
        delta = tick - current_tick
        add_note(track, note, vel, dur, delta)
        current_tick = tick + dur

    track.append(MetaMessage('end_of_track', time=0))
    mid.save(OUTPUT_DIR / 'crash_expanded.mid')
    print(f"Created: crash_expanded.mid")

def generate_breakdown_pad():
    """Generate emotional breakdown pad (bars 128-168)

    Using notes that work with the existing progression.
    Based on F minor / Db major vibes from the existing TRITON parts.
    """
    mid, track = create_midi_file()

    events = []

    # Breakdown chord progression - emotional, sustained
    # Fm - Db - Ab - Eb (classic trance breakdown)
    breakdown_chords = [
        # (bar_offset, notes, duration_bars)
        (0, [53, 56, 60, 65], 8),    # Fm (F3, Ab3, C4, F4) - bars 128-136
        (8, [49, 53, 56, 61], 8),    # Db (Db3, F3, Ab3, Db4) - bars 136-144
        (16, [44, 48, 51, 56], 8),   # Ab (Ab2, C3, Eb3, Ab3) - bars 144-152
        (24, [51, 55, 58, 63], 8),   # Eb (Eb3, G3, Bb3, Eb4) - bars 152-160
    ]

    breakdown_start = 128 * TICKS_PER_BAR

    for bar_offset, notes, duration_bars in breakdown_chords:
        chord_start = breakdown_start + bar_offset * TICKS_PER_BAR
        chord_duration = duration_bars * TICKS_PER_BAR - TICKS_PER_BEAT

        for note in notes:
            events.append((chord_start, 'on', note, 75))
            events.append((chord_start + chord_duration, 'off', note, 0))

    # Build 2 section - rising tension (160-168)
    build_start = 160 * TICKS_PER_BAR
    build_chords = [
        (0, [53, 56, 60], 2),   # Fm
        (2, [55, 58, 62], 2),   # Gm
        (4, [56, 60, 63], 2),   # Ab
        (6, [58, 62, 65], 2),   # Bb
    ]

    for bar_offset, notes, duration_bars in build_chords:
        chord_start = build_start + bar_offset * TICKS_PER_BAR
        chord_duration = duration_bars * TICKS_PER_BAR - TICKS_PER_BEAT // 2
        vel = 80 + bar_offset * 5

        for note in notes:
            events.append((chord_start, 'on', note, vel))
            events.append((chord_start + chord_duration, 'off', note, 0))

    # Sort events
    events.sort(key=lambda x: (x[0], 0 if x[1] == 'on' else 1))

    current_tick = 0
    for tick, event_type, note, vel in events:
        delta = tick - current_tick
        if event_type == 'on':
            track.append(Message('note_on', note=note, velocity=vel, time=delta))
        else:
            track.append(Message('note_off', note=note, velocity=0, time=delta))
        current_tick = tick

    track.append(MetaMessage('end_of_track', time=0))
    mid.save(OUTPUT_DIR / 'breakdown_pad.mid')
    print(f"Created: breakdown_pad.mid (bars 128-168)")

def generate_drop2_lead():
    """Generate lead melody for drop 2 (bars 168-200)

    A variation on the original lead but with new melodic content.
    """
    mid, track = create_midi_file()

    events = []

    # Lead melody pattern - energetic, trance-style
    # 8-bar phrase repeated with variations
    drop2_start = 168 * TICKS_PER_BAR

    # Main melodic motif (F minor based)
    # Notes: F4(65), Ab4(68), C5(72), Db5(73), Eb5(75), F5(77)
    melody_phrase = [
        # (bar_offset_16ths, note, duration_16ths, velocity)
        # Bar 1
        (0, 72, 2, 100),   # C5
        (2, 68, 2, 90),    # Ab4
        (4, 65, 4, 95),    # F4
        (8, 68, 2, 90),    # Ab4
        (10, 72, 2, 100),  # C5
        (12, 75, 4, 105),  # Eb5
        # Bar 2
        (16, 77, 4, 100),  # F5
        (20, 75, 2, 95),   # Eb5
        (22, 72, 2, 90),   # C5
        (24, 68, 4, 85),   # Ab4
        (28, 65, 4, 80),   # F4
        # Bar 3
        (32, 73, 2, 100),  # Db5
        (34, 72, 2, 95),   # C5
        (36, 68, 4, 90),   # Ab4
        (40, 65, 2, 85),   # F4
        (42, 63, 2, 80),   # Eb4
        (44, 65, 4, 90),   # F4
        # Bar 4
        (48, 68, 8, 100),  # Ab4 long
        (56, 72, 8, 105),  # C5 long
    ]

    sixteenth = TICKS_PER_BAR // 16

    # Play the phrase 4 times (bars 168-200 = 32 bars, 8 bar phrase x 4)
    for phrase_num in range(4):
        phrase_start = drop2_start + phrase_num * 8 * TICKS_PER_BAR

        # Add variation on later phrases
        pitch_offset = 0
        if phrase_num == 2:
            pitch_offset = 5  # Up a fourth
        elif phrase_num == 3:
            pitch_offset = 0  # Back to original for resolution

        for bar_16th, note, dur_16ths, vel in melody_phrase:
            note_tick = phrase_start + bar_16th * sixteenth
            note_dur = dur_16ths * sixteenth - 10

            # Add velocity variation
            vel_var = vel + (phrase_num * 3)

            events.append((note_tick, 'on', note + pitch_offset, min(vel_var, 120)))
            events.append((note_tick + note_dur, 'off', note + pitch_offset, 0))

    # Sort events
    events.sort(key=lambda x: (x[0], 0 if x[1] == 'on' else 1))

    current_tick = 0
    for tick, event_type, note, vel in events:
        delta = tick - current_tick
        if event_type == 'on':
            track.append(Message('note_on', note=note, velocity=vel, time=delta))
        else:
            track.append(Message('note_off', note=note, velocity=0, time=delta))
        current_tick = tick

    track.append(MetaMessage('end_of_track', time=0))
    mid.save(OUTPUT_DIR / 'drop2_lead.mid')
    print(f"Created: drop2_lead.mid (bars 168-200)")

def generate_outro_arp():
    """Generate arpeggio for outro (bars 200-224)"""
    mid, track = create_midi_file()

    events = []

    outro_start = 200 * TICKS_PER_BAR
    sixteenth = TICKS_PER_BAR // 16

    # Fm arpeggio pattern fading out
    arp_notes = [53, 56, 60, 65, 60, 56]  # F3, Ab3, C4, F4, C4, Ab3

    for bar in range(24):
        bar_start = outro_start + bar * TICKS_PER_BAR

        # Velocity fading out
        base_vel = max(40, 90 - bar * 3)

        # 16th note arpeggios
        for beat in range(16):
            note = arp_notes[beat % len(arp_notes)]
            note_tick = bar_start + beat * sixteenth
            vel = base_vel + (beat % 4 == 0) * 10  # Accent on beat

            events.append((note_tick, 'on', note, vel))
            events.append((note_tick + sixteenth - 10, 'off', note, 0))

        # Stop arp in final 4 bars
        if bar >= 20:
            break

    # Sort events
    events.sort(key=lambda x: (x[0], 0 if x[1] == 'on' else 1))

    current_tick = 0
    for tick, event_type, note, vel in events:
        delta = tick - current_tick
        if event_type == 'on':
            track.append(Message('note_on', note=note, velocity=vel, time=delta))
        else:
            track.append(Message('note_off', note=note, velocity=0, time=delta))
        current_tick = tick

    track.append(MetaMessage('end_of_track', time=0))
    mid.save(OUTPUT_DIR / 'outro_arp.mid')
    print(f"Created: outro_arp.mid (bars 200-224)")

if __name__ == "__main__":
    print("=" * 50)
    print("EXPANDING 42-3-1 COMPOSITION")
    print(f"From 128 bars to {TOTAL_BARS} bars")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 50)
    print()

    # Generate all expanded MIDI files
    generate_kick_expanded()
    generate_clap_expanded()
    generate_hats_expanded()
    generate_crash_expanded()
    generate_breakdown_pad()
    generate_drop2_lead()
    generate_outro_arp()

    print()
    print("=" * 50)
    print("EXPANSION COMPLETE!")
    print()
    print("New structure:")
    for section, (start, end) in SECTIONS.items():
        duration = end - start
        print(f"  {section:20}: bars {start:3}-{end:3} ({duration:2} bars)")
    print()
    print(f"Total duration: {TOTAL_BARS} bars ({TOTAL_BARS * 4 / BPM:.1f} minutes)")
    print()
    print("Files created:")
    print("  - kick_expanded.mid     (extended kick with fills)")
    print("  - clap_expanded.mid     (clap with pre-drop rolls)")
    print("  - hats_expanded.mid     (hats with transition rolls)")
    print("  - crash_expanded.mid    (crash at key moments)")
    print("  - breakdown_pad.mid     (emotional breakdown chords)")
    print("  - drop2_lead.mid        (new lead melody for drop 2)")
    print("  - outro_arp.mid         (fading outro arpeggio)")
    print()
    print("Import these into Ableton and place on new tracks or")
    print("extend existing clips with this content.")
