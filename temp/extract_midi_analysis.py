#!/usr/bin/env python3
"""Extract MIDI analysis from JSON file and compute statistics."""

import json
import statistics
from collections import defaultdict

json_file = r"C:\claude-workspace\AbletonAIAnalysis\projects\music-analyzer\reports\38b_5\38b_5_v1_analysis_2026-01-15.json"

with open(json_file) as f:
    data = json.load(f)

# Extract metadata
metadata = data.get('metadata', {})
als_project = data.get('als_project', {})
tempo = als_project.get('tempo', 'N/A')

# Process each track
track_analysis = []

for track in als_project.get('tracks', []):
    track_name = track.get('name', 'Unknown')
    track_type = track.get('track_type', 'unknown')

    # Skip audio-only tracks
    if track_type != 'midi':
        continue

    # Collect all note velocities
    all_velocities = []
    note_count = 0

    for midi_clip in track.get('midi_clips', []):
        for note in midi_clip.get('notes', []):
            velocity = note.get('velocity', 0)
            all_velocities.append(velocity)
            note_count += 1

    if not all_velocities:
        continue

    # Calculate statistics
    velocity_mean = statistics.mean(all_velocities)
    velocity_std = statistics.stdev(all_velocities) if len(all_velocities) > 1 else 0.0
    velocity_min = min(all_velocities)
    velocity_max = max(all_velocities)
    velocity_range = velocity_max - velocity_min

    # Humanization scoring
    if velocity_std == 0:
        humanization_score = "robotic"
        severity = "CRITICAL"
    elif velocity_std < 3:
        humanization_score = "robotic"
        severity = "SEVERE"
    elif velocity_std < 8:
        humanization_score = "robotic"
        severity = "MODERATE"
    elif velocity_std < 15:
        humanization_score = "somewhat_robotic"
        severity = "MINOR"
    else:
        humanization_score = "natural"
        severity = "GOOD"

    track_analysis.append({
        'name': track_name,
        'track_type': track_type,
        'velocity_mean': round(velocity_mean, 2),
        'velocity_std': round(velocity_std, 2),
        'velocity_range': [velocity_min, velocity_max],
        'velocity_span': velocity_range,
        'humanization_score': humanization_score,
        'severity': severity,
        'note_count': note_count,
        'all_velocities': all_velocities
    })

# Sort by severity and std
severity_order = {'CRITICAL': 0, 'SEVERE': 1, 'MODERATE': 2, 'MINOR': 3, 'GOOD': 4}
track_analysis.sort(key=lambda x: (severity_order.get(x['severity'], 5), x['velocity_std']))

# Print summary
print("=" * 80)
print("DYNAMICS & HUMANIZATION ANALYSIS")
print("=" * 80)
print(f"\nProject: 38b_5 v1")
print(f"Tempo: {tempo} BPM")
print(f"Analysis Date: {metadata.get('generated_at', 'N/A')}")
print(f"\nTotal MIDI Tracks Analyzed: {len(track_analysis)}")

critical_count = sum(1 for t in track_analysis if t['severity'] == 'CRITICAL')
severe_count = sum(1 for t in track_analysis if t['severity'] == 'SEVERE')
moderate_count = sum(1 for t in track_analysis if t['severity'] == 'MODERATE')
minor_count = sum(1 for t in track_analysis if t['severity'] == 'MINOR')
good_count = sum(1 for t in track_analysis if t['severity'] == 'GOOD')

print(f"\nRobotic Tracks (std=0): {critical_count} [CRITICAL]")
print(f"Nearly robotic (std<3): {severe_count} [SEVERE]")
print(f"Under-humanized (std<8): {moderate_count} [MODERATE]")
print(f"Minimal issues (std<15): {minor_count} [MINOR]")
print(f"Well-humanized (std≥15): {good_count} [GOOD]")

if track_analysis:
    worst = track_analysis[0]
    print(f"\nMost Robotic Track: {worst['name']} with velocity_std = {worst['velocity_std']}")

# Print detailed analysis
print("\n" + "=" * 80)
print("DETAILED TRACK ANALYSIS")
print("=" * 80)

for track in track_analysis:
    print(f"\n[{track['severity']}] {track['name']}")
    print(f"{'─' * 70}")
    print(f"Velocity mean: {track['velocity_mean']}")
    print(f"Velocity std: {track['velocity_std']}")
    print(f"Velocity range: {track['velocity_range']} (span: {track['velocity_span']})")
    print(f"Note count: {track['note_count']} notes")
    print(f"Humanization score: {track['humanization_score']}")

    # Export for report generation
    print(json.dumps(track, indent=2))
    print()
