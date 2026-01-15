#!/usr/bin/env python3
import json
import statistics
from collections import defaultdict
import re

# Load the JSON file
with open('C:/claude-workspace/AbletonAIAnalysis/projects/music-analyzer/reports/38b_5/38b_5_v1_analysis_2026-01-15.json', 'r') as f:
    data = json.load(f)

# Extract tracks
tracks = data.get('als_project', {}).get('tracks', [])
print(f'Total tracks: {len(tracks)}\n')

# Get all unmuted tracks
unmuted_tracks = [t for t in tracks if not t.get('is_muted', False)]
print(f'Unmuted tracks: {len(unmuted_tracks)}')
print(f'Muted tracks: {len(tracks) - len(unmuted_tracks)}\n')

# Get volumes for unmuted tracks
volumes = [t['volume_db'] for t in unmuted_tracks]

if volumes:
    mean_vol = statistics.mean(volumes)
    std_dev = statistics.stdev(volumes) if len(volumes) > 1 else 0
    min_vol = min(volumes)
    max_vol = max(volumes)

    print(f'Volume Statistics (unmuted tracks):')
    print(f'  Mean: {mean_vol:.2f}dB')
    print(f'  Std Dev: {std_dev:.2f}dB')
    print(f'  Min: {min_vol:.2f}dB')
    print(f'  Max: {max_vol:.2f}dB')
    print(f'  Range: {max_vol - min_vol:.2f}dB\n')

    # Count tracks at thresholds
    at_20plus = len([v for v in volumes if v >= 20])
    at_24plus = len([v for v in volumes if v >= 24])
    below_10 = len([v for v in volumes if v < 10])

    print(f'Threshold counts:')
    print(f'  Tracks at >=20dB: {at_20plus} ({100*at_20plus/len(volumes):.1f}%)')
    print(f'  Tracks at >=24dB: {at_24plus}')
    print(f'  Tracks below 10dB: {below_10}\n')

# Identify track types
def get_track_type(name):
    name_lower = name.lower()
    if any(x in name_lower for x in ['kick', 'kck', 'bd']):
        return 'Kick'
    elif any(x in name_lower for x in ['snare', 'snr', 'clap', 'clp']):
        return 'Snare/Clap'
    elif any(x in name_lower for x in ['hat', 'hh', 'cymbal', 'ride', 'crash']):
        return 'Hi-hat/Cymbal'
    elif any(x in name_lower for x in ['bass', 'sub', 'low']):
        return 'Bass'
    elif any(x in name_lower for x in ['lead', 'synth', 'poly', 'triton', 'monopoly']):
        return 'Lead/Synth'
    elif any(x in name_lower for x in ['pad', 'string', 'str', 'atmosphere']):
        return 'Pad'
    elif any(x in name_lower for x in ['fx', 'riser', 'sweep', 'impact']):
        return 'FX'
    elif any(x in name_lower for x in ['group', 'bus', 'drum', 'master']):
        return 'Group/Bus'
    else:
        return 'Other'

# Categorize and find outliers
type_volumes = defaultdict(list)
track_details = []

for track in tracks:
    if not track.get('is_muted', False):
        track_type = get_track_type(track['name'])
        type_volumes[track_type].append((track['name'], track['volume_db']))
        track_details.append({
            'name': track['name'],
            'volume': track['volume_db'],
            'type': track_type,
            'muted': track.get('is_muted'),
            'solo': track.get('is_solo')
        })

# Print all tracks sorted by volume (descending)
print('All unmuted tracks sorted by volume (descending):')
track_details_sorted = sorted(track_details, key=lambda x: x['volume'], reverse=True)
for i, track in enumerate(track_details_sorted):
    print(f'{i+1:2d}. [{track["type"]:15s}] {track["name"][:45]:45s} | {track["volume"]:7.2f}dB')

print(f'\n\nExtremes (potential outliers):')
top_5 = track_details_sorted[:5]
bottom_5 = track_details_sorted[-5:]

print(f'Top 5 (hottest):')
for track in top_5:
    print(f'  {track["name"][:50]:50s} | {track["volume"]:7.2f}dB')

print(f'\nBottom 5 (quietest):')
for track in bottom_5:
    print(f'  {track["name"][:50]:50s} | {track["volume"]:7.2f}dB')

# Analyze by type
print(f'\n\nBy Track Type (unmuted only):')
for track_type in sorted(type_volumes.keys()):
    type_vols = [v for _, v in type_volumes[track_type]]
    if type_vols:
        type_mean = statistics.mean(type_vols)
        type_std = statistics.stdev(type_vols) if len(type_vols) > 1 else 0
        print(f'\n{track_type}:')
        print(f'  Count: {len(type_vols)}, Mean: {type_mean:.2f}dB, Std Dev: {type_std:.2f}dB')
        print(f'  Range: {min(type_vols):.2f}dB to {max(type_vols):.2f}dB')
        for name, vol in sorted(type_volumes[track_type], key=lambda x: x[1], reverse=True):
            print(f'    {name[:45]:45s} | {vol:7.2f}dB')
