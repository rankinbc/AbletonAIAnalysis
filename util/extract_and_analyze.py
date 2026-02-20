#!/usr/bin/env python3
"""Extract track data and perform gain staging analysis."""

import json
import statistics
from collections import defaultdict

# Load the JSON file
json_path = 'C:/claude-workspace/AbletonAIAnalysis/projects/music-analyzer/reports/38b_5/38b_5_v1_analysis_2026-01-15.json'
with open(json_path, 'r') as f:
    data = json.load(f)

# Extract tracks
tracks = data.get('als_project', {}).get('tracks', [])
print(f'Total tracks: {len(tracks)}\n')

# Separate unmuted and muted
unmuted_tracks = [t for t in tracks if not t.get('is_muted', False)]
muted_tracks = [t for t in tracks if t.get('is_muted', False)]

print(f'Unmuted tracks: {len(unmuted_tracks)}')
print(f'Muted tracks: {len(muted_tracks)}\n')

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

# Define track type detection
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
    track_type = get_track_type(track['name'])
    if not track.get('is_muted', False):
        type_volumes[track_type].append((track['name'], track['volume_db']))
        track_details.append({
            'name': track['name'],
            'volume': track['volume_db'],
            'type': track_type,
            'muted': track.get('is_muted'),
            'solo': track.get('is_solo'),
            'id': track.get('id')
        })

# Sort by volume descending
track_details_sorted = sorted(track_details, key=lambda x: x['volume'], reverse=True)

print('\n=== ALL UNMUTED TRACKS SORTED BY VOLUME ===\n')
for i, track in enumerate(track_details_sorted, 1):
    print(f'{i:2d}. [{track["type"]:15s}] {track["name"][:45]:45s} | {track["volume"]:7.2f}dB')

# Find extremes
print(f'\n\n=== EXTREMES (Potential Outliers) ===\n')
top_10 = track_details_sorted[:10]
bottom_10 = track_details_sorted[-10:]

print(f'Top 10 Hottest:')
for track in top_10:
    print(f'  {track["name"][:50]:50s} | {track["volume"]:7.2f}dB')

print(f'\nBottom 10 Quietest:')
for track in bottom_10:
    print(f'  {track["name"][:50]:50s} | {track["volume"]:7.2f}dB')

# Analyze by type
print(f'\n\n=== BY TRACK TYPE (unmuted only) ===\n')
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

# Check for problematic conditions
print(f'\n\n=== PROBLEM DETECTION ===\n')

problems = []

# Check for no headroom
if at_20plus / len(volumes) > 0.80:
    problems.append(('CRITICAL', 'No headroom', f'{at_20plus} tracks at >=20dB ({100*at_20plus/len(volumes):.1f}%)'))

# Check for all identical
if std_dev < 2:
    problems.append(('CRITICAL', 'All tracks identical', f'Std dev: {std_dev:.2f}dB'))

# Check for clipping risk
if at_24plus > 0:
    problems.append(('SEVERE', 'Clipping risk', f'{at_24plus} tracks at >=24dB'))

# Check for extreme outliers
outlier_threshold_high = mean_vol + 8
outlier_threshold_low = mean_vol - 10
outliers_high = [t for t in track_details if t['volume'] > outlier_threshold_high]
outliers_low = [t for t in track_details if t['volume'] < outlier_threshold_low]

if outliers_high:
    for t in outliers_high:
        problems.append(('SEVERE', f'Extreme outlier (hot): {t["name"]}', f'{t["volume"]:.2f}dB ({t["volume"]-mean_vol:+.2f}dB from mean)'))

if outliers_low:
    for t in outliers_low:
        problems.append(('MODERATE', f'Extreme outlier (buried): {t["name"]}', f'{t["volume"]:.2f}dB ({t["volume"]-mean_vol:.2f}dB from mean)'))

# Check for no level hierarchy
if std_dev < 4:
    problems.append(('MODERATE', 'No level hierarchy', f'Std dev: {std_dev:.2f}dB'))

if problems:
    for severity, issue, detail in sorted(problems, key=lambda x: ['CRITICAL', 'SEVERE', 'MODERATE'].index(x[0])):
        print(f'[{severity}] {issue}')
        print(f'  {detail}\n')
else:
    print('No critical problems detected.\n')

# Write summary to file for later use
summary = {
    'total_tracks': len(tracks),
    'unmuted_tracks': len(unmuted_tracks),
    'muted_tracks': len(muted_tracks),
    'stats': {
        'mean': mean_vol,
        'std_dev': std_dev,
        'min': min_vol,
        'max': max_vol,
        'range': max_vol - min_vol
    },
    'thresholds': {
        'at_20plus': at_20plus,
        'at_20plus_pct': 100*at_20plus/len(volumes),
        'at_24plus': at_24plus,
        'below_10': below_10
    },
    'track_details': track_details_sorted,
    'problems': problems
}

with open('/tmp/gain_staging_summary.json', 'w') as f:
    json.dump(summary, f, indent=2)

print(f'\nSummary written to /tmp/gain_staging_summary.json')
