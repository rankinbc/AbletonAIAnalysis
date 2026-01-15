#!/usr/bin/env python3
"""
Frequency Collision Detection Analysis
Analyzes MIDI notes to find overlapping frequencies that cause mud and masking
"""

import json
import math
from collections import defaultdict
from pathlib import Path

def midi_to_hz(pitch):
    """Convert MIDI pitch to frequency"""
    return 440 * (2 ** ((pitch - 69) / 12))

def get_freq_band(hz):
    """Assign frequency band to a frequency"""
    if hz < 60:
        return "Sub bass (20-60Hz)"
    elif hz < 200:
        return "Bass (60-200Hz)"
    elif hz < 500:
        return "Low-mid (200-500Hz)"
    elif hz < 2000:
        return "Mid (500-2kHz)"
    elif hz < 6000:
        return "Upper-mid (2-6kHz)"
    else:
        return "High (6-20kHz)"

def get_severity(band, count):
    """Determine collision severity based on band and count"""
    if band == "Sub bass (20-60Hz)":
        return "CRITICAL" if count > 0 else "NONE"
    elif band == "Bass (60-200Hz)":
        if count > 100:
            return "CRITICAL"
        elif count > 50:
            return "SEVERE"
        else:
            return "MODERATE"
    elif band == "Low-mid (200-500Hz)":
        if count > 200:
            return "SEVERE"
        elif count > 100:
            return "MODERATE"
        else:
            return "MINOR"
    else:
        return "MINOR" if count > 0 else "OK"

def beats_to_time(beats, tempo):
    """Convert beats to MM:SS format"""
    seconds = beats * 60 / tempo
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}", seconds

def analyze_collisions(json_path):
    """Analyze frequency collisions from ALS JSON export"""

    with open(json_path, 'r') as f:
        data = json.load(f)

    tempo = data['als_project']['tempo']
    tracks_data = data['als_project']['tracks']

    # Build timeline of all notes
    notes_timeline = []

    for track_idx, track in enumerate(tracks_data):
        # Skip muted tracks
        if track['is_muted']:
            continue

        track_name = track['name']

        # Process MIDI clips
        for clip in track.get('midi_clips', []):
            clip_start = clip['start_time']

            for note in clip.get('notes', []):
                if note['mute']:
                    continue

                abs_start = clip_start + note['start_time']
                abs_end = abs_start + note['duration']
                pitch = note['pitch']
                hz = midi_to_hz(pitch)
                band = get_freq_band(hz)

                notes_timeline.append({
                    'track_idx': track_idx,
                    'track_name': track_name,
                    'abs_start': abs_start,
                    'abs_end': abs_end,
                    'pitch': pitch,
                    'hz': hz,
                    'band': band,
                    'duration': note['duration']
                })

    # Detect collisions
    collisions = []
    collision_count_by_band = defaultdict(int)
    collision_pairs = defaultdict(list)

    for i, note1 in enumerate(notes_timeline):
        for note2 in notes_timeline[i+1:]:
            # Check if time ranges overlap
            if note1['abs_start'] < note2['abs_end'] and note2['abs_start'] < note1['abs_end']:
                # Check if same band and different tracks
                if note1['band'] == note2['band'] and note1['track_idx'] != note2['track_idx']:
                    overlap_start = max(note1['abs_start'], note2['abs_start'])
                    overlap_end = min(note1['abs_end'], note2['abs_end'])
                    overlap_duration = overlap_end - overlap_start

                    collisions.append({
                        'track1_name': note1['track_name'],
                        'track2_name': note2['track_name'],
                        'track1_idx': note1['track_idx'],
                        'track2_idx': note2['track_idx'],
                        'start_beat': overlap_start,
                        'end_beat': overlap_end,
                        'hz1': note1['hz'],
                        'hz2': note2['hz'],
                        'pitch1': note1['pitch'],
                        'pitch2': note2['pitch'],
                        'band': note1['band'],
                        'duration': overlap_duration
                    })

                    collision_count_by_band[note1['band']] += 1
                    pair_key = tuple(sorted([note1['track_name'], note2['track_name']]))
                    collision_pairs[pair_key].append({
                        'band': note1['band'],
                        'hz1': note1['hz'],
                        'hz2': note2['hz'],
                        'pitch1': note1['pitch'],
                        'pitch2': note2['pitch'],
                        'beat': overlap_start
                    })

    # Calculate overall status
    sub_bass_count = collision_count_by_band.get("Sub bass (20-60Hz)", 0)
    bass_count = collision_count_by_band.get("Bass (60-200Hz)", 0)
    low_mid_count = collision_count_by_band.get("Low-mid (200-500Hz)", 0)

    if sub_bass_count > 0:
        overall_status = "CRITICAL"
    elif bass_count > 100:
        overall_status = "CRITICAL"
    elif bass_count > 50 or low_mid_count > 200:
        overall_status = "NEEDS WORK"
    elif bass_count > 20 or low_mid_count > 100:
        overall_status = "ACCEPTABLE"
    else:
        overall_status = "GOOD"

    # Get top problematic pairs
    sorted_pairs = sorted(collision_pairs.items(), key=lambda x: len(x[1]), reverse=True)

    return {
        'tempo': tempo,
        'total_collisions': len(collisions),
        'collisions_by_band': dict(collision_count_by_band),
        'overall_status': overall_status,
        'collisions': collisions,
        'collision_pairs': collision_pairs,
        'sorted_pairs': sorted_pairs,
        'notes_timeline': notes_timeline
    }

if __name__ == '__main__':
    json_path = 'C:/claude-workspace/AbletonAIAnalysis/projects/music-analyzer/reports/38b_5/38b_5_v1_analysis_2026-01-15.json'

    results = analyze_collisions(json_path)

    print(f"Tempo: {results['tempo']} BPM")
    print(f"Total collisions: {results['total_collisions']}")
    print(f"Overall status: {results['overall_status']}")
    print(f"\nCollisions by band:")
    for band in ["Sub bass (20-60Hz)", "Bass (60-200Hz)", "Low-mid (200-500Hz)", "Mid (500-2kHz)", "Upper-mid (2-6kHz)", "High (6-20kHz)"]:
        count = results['collisions_by_band'].get(band, 0)
        if count > 0:
            print(f"  {band}: {count}")

    print(f"\nTop 10 problematic pairs:")
    for i, (pair, clist) in enumerate(results['sorted_pairs'][:10]):
        track1, track2 = pair
        count = len(clist)
        primary_band = clist[0]['band']
        avg_hz = (sum(c['hz1'] for c in clist) + sum(c['hz2'] for c in clist)) / (len(clist) * 2)
        print(f"  {i+1}. {track1} + {track2}: {count} collisions, {primary_band}, ~{avg_hz:.0f}Hz")

    # Save full results
    with open('collision_results.json', 'w') as f:
        # Convert for JSON serialization
        output = {
            'tempo': results['tempo'],
            'total_collisions': results['total_collisions'],
            'overall_status': results['overall_status'],
            'collisions_by_band': results['collisions_by_band'],
            'problematic_pairs': [
                {
                    'tracks': list(pair),
                    'collision_count': len(clist),
                    'primary_bands': [c['band'] for c in clist[:3]]
                }
                for pair, clist in results['sorted_pairs'][:15]
            ],
            'sample_collisions': results['collisions'][:50]
        }
        json.dump(output, f, indent=2)

    print("\nFull results saved to collision_results.json")
