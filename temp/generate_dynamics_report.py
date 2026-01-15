#!/usr/bin/env python3
"""Generate Dynamics & Humanization Report from JSON analysis."""

import json
import statistics
from datetime import datetime

# Load the analysis JSON
json_file = r"C:\claude-workspace\AbletonAIAnalysis\projects\music-analyzer\reports\38b_5\38b_5_v1_analysis_2026-01-15.json"

with open(json_file) as f:
    data = json.load(f)

# Extract metadata and project info
metadata = data.get('metadata', {})
als_project = data.get('als_project', {})
tempo = als_project.get('tempo', 141.0)

# Process each track for MIDI analysis
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

    # Determine severity and recommendations
    if velocity_std == 0:
        severity = "CRITICAL"
    elif velocity_std < 3:
        severity = "SEVERE"
    elif velocity_std < 8:
        severity = "MODERATE"
    elif velocity_std < 15:
        severity = "MINOR"
    else:
        severity = "GOOD"

    track_analysis.append({
        'name': track_name,
        'track_type': track_type,
        'velocity_mean': round(velocity_mean, 1),
        'velocity_std': round(velocity_std, 2),
        'velocity_min': velocity_min,
        'velocity_max': velocity_max,
        'velocity_range': velocity_range,
        'humanization_score': 'robotic' if velocity_std < 15 else 'natural',
        'severity': severity,
        'note_count': note_count,
        'all_velocities': all_velocities
    })

# Sort by severity
severity_order = {'CRITICAL': 0, 'SEVERE': 1, 'MODERATE': 2, 'MINOR': 3, 'GOOD': 4}
track_analysis.sort(key=lambda x: (severity_order.get(x['severity'], 5), x['velocity_std']))

# Generate markdown report
report = []

# Header
report.append("# Dynamics & Humanization Report")
report.append(f"## Project: 38b_5 v1")
report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
report.append(f"**Tempo:** {tempo} BPM (Trance)")
report.append("")

# Overall status
critical_count = sum(1 for t in track_analysis if t['severity'] == 'CRITICAL')
severe_count = sum(1 for t in track_analysis if t['severity'] == 'SEVERE')
moderate_count = sum(1 for t in track_analysis if t['severity'] == 'MODERATE')
minor_count = sum(1 for t in track_analysis if t['severity'] == 'MINOR')
good_count = sum(1 for t in track_analysis if t['severity'] == 'GOOD')

if critical_count > 0:
    overall_status = "CRITICAL"
elif severe_count > 0:
    overall_status = "NEEDS WORK"
elif moderate_count > 0:
    overall_status = "ACCEPTABLE"
else:
    overall_status = "GOOD"

report.append("## Summary")
report.append("")
report.append(f"**Overall Status:** `{overall_status}`")
report.append("")
report.append("### Velocity Statistics:")
report.append(f"- Tracks analyzed: {len(track_analysis)}")
report.append(f"- Robotic tracks (std=0): **{critical_count}** [CRITICAL if >0]")
report.append(f"- Nearly robotic (std<3): **{severe_count}** [SEVERE]")
report.append(f"- Under-humanized (std<8): **{moderate_count}** [MODERATE]")
report.append(f"- Somewhat humanized (std<15): **{minor_count}** [MINOR]")
report.append(f"- Well-humanized (std≥15): **{good_count}** [GOOD]")
report.append("")

if track_analysis:
    worst = track_analysis[0]
    report.append(f"**Most Robotic Track:** {worst['name']} with velocity_std = {worst['velocity_std']}")
report.append("")

# Prioritized issues
report.append("---")
report.append("## Prioritized Issues (MOST IMPORTANT FIRST)")
report.append("")

for track in track_analysis:
    if track['severity'] in ['GOOD']:
        continue

    report.append(f"### [{track['severity']}] {track['name']} — Drum Element")
    report.append("")
    report.append("#### CURRENT STATE:")
    report.append(f"- Velocity mean: {track['velocity_mean']}")
    report.append(f"- Velocity std: {track['velocity_std']}" + (" (completely static)" if track['velocity_std'] == 0 else ""))
    report.append(f"- Velocity range: [{track['velocity_min']}, {track['velocity_max']}]" + (" (no variation)" if track['velocity_range'] == 0 else ""))
    report.append(f"- Note count: {track['note_count']} notes")
    report.append("")

    # Problem statement
    if track['velocity_std'] == 0:
        report.append("#### PROBLEM:")
        report.append(f"Every single note is identical at velocity {track['velocity_mean']:.0f}.")
        report.append("This is the most robotic-sounding element in your mix.")
        report.append("")
        report.append("#### IMPACT:")
        report.append("Sounds mechanical and lifeless. Human players NEVER hit exactly the same twice.")
        report.append("Listeners experience fatigue from the lack of dynamics.")
        report.append("")
    elif track['velocity_std'] < 3:
        report.append("#### PROBLEM:")
        report.append(f"Velocity variation is minimal (std={track['velocity_std']}). All notes sound nearly identical.")
        report.append("")
        report.append("#### IMPACT:")
        report.append("Sounds mechanical despite slight variation. Groove lacks natural feel.")
        report.append("")
    else:
        report.append("#### PROBLEM:")
        report.append(f"Limited velocity variation (std={track['velocity_std']}). Velocity range only spans {track['velocity_range']} values.")
        report.append("")
        report.append("#### IMPACT:")
        report.append("Lacks dynamic life. Could benefit from more expressive velocity changes.")
        report.append("")

    # Action required
    report.append("#### ACTION REQUIRED:")
    report.append("")
    report.append("**Step 1 — Add Random Variation:**")

    if 'kick' in track['name'].lower():
        randomize_amount = 8
        target_std = "7-10"
        report.append(f"- Select all {track['note_count']} notes in track")
        report.append(f"- Apply velocity randomization: ±{randomize_amount} from current value")
        report.append(f"- Target velocity std: {target_std}")
    elif 'snare' in track['name'].lower():
        randomize_amount = 12
        target_std = "12-18"
        report.append(f"- Select all {track['note_count']} notes in track")
        report.append(f"- Apply velocity randomization: ±{randomize_amount} from current value")
        report.append(f"- Target velocity std: {target_std}")
    elif 'hat' in track['name'].lower() or 'hh' in track['name'].lower():
        randomize_amount = 15
        target_std = "18-25"
        report.append(f"- Select all {track['note_count']} notes in track")
        report.append(f"- Apply velocity randomization: ±{randomize_amount} from current value")
        report.append(f"- Target velocity std: {target_std}")
    elif 'clap' in track['name'].lower():
        randomize_amount = 10
        target_std = "10-15"
        report.append(f"- Select all {track['note_count']} notes in track")
        report.append(f"- Apply velocity randomization: ±{randomize_amount} from current value")
        report.append(f"- Target velocity std: {target_std}")
    else:
        randomize_amount = 10
        target_std = "10-15"
        report.append(f"- Select all {track['note_count']} notes in track")
        report.append(f"- Apply velocity randomization: ±{randomize_amount} from current value")
        report.append(f"- Target velocity std: {target_std}")

    report.append("")
    report.append("**Step 2 — Create Accent Pattern:**")
    report.append("")

    mean_vel = track['velocity_mean']
    accent_vel = min(127, round(mean_vel + 8))
    soft_vel = max(0, round(mean_vel - 5))

    if 'snare' in track['name'].lower():
        report.append(f"- Beats 2 & 4 (main hits): {accent_vel} velocity")
        report.append(f"- Beats 1 & 3 (supporting): {round(mean_vel)} velocity")
        report.append(f"- Ghost notes (if any): 50-70 velocity")
    elif 'kick' in track['name'].lower():
        report.append(f"- Downbeats (1, 2, 3, 4): {round(mean_vel)} velocity (consistent)")
        report.append(f"- Slight variation: ±3-5 on offbeats")
    elif 'hat' in track['name'].lower() or 'hh' in track['name'].lower():
        report.append(f"- Downbeats: {accent_vel} velocity")
        report.append(f"- Offbeats: {soft_vel} velocity")
        report.append(f"- 16th notes: 50-65 velocity (quieter layer)")
    elif 'clap' in track['name'].lower():
        report.append(f"- Main hits (2, 4): {accent_vel} velocity")
        report.append(f"- Supporting hits: {round(mean_vel)} velocity")
    else:
        report.append(f"- Pattern on main beats: {accent_vel} velocity")
        report.append(f"- Offbeats: {soft_vel} velocity")

    report.append("")
    report.append("**Step 3 — Add Dynamics Over Time:**")
    report.append(f"- During builds: Gradually increase from {round(mean_vel-10)} to {accent_vel} over 8 bars")
    report.append(f"- At drop: Start at {accent_vel}, settle to {round(mean_vel)} average")
    report.append(f"- During breakdowns: Reduce to {max(0, round(mean_vel-20))}-{soft_vel}")
    report.append("")

    report.append("#### SPECIFIC VALUES FOR THIS TRACK:")
    report.append(f"- Base velocity: {track['velocity_mean']}")
    report.append(f"- Accent hits: {accent_vel}")
    report.append(f"- Soft hits: {soft_vel}")
    report.append(f"- Target velocity_std: {target_std if 'target_std' in locals() else '12-18'}")
    report.append(f"- Target velocity_range: [{max(0, round(mean_vel-15))}, {min(127, round(mean_vel+15))}]")
    report.append("")

    report.append("#### HOW TO APPLY IN ABLETON:")
    report.append("1. Select all notes in the clip")
    report.append(f"2. Right-click → Randomize → Velocity (±{randomize_amount})")
    report.append("3. For specific patterns:")
    report.append("   - Click each note individually and adjust velocity in the bottom inspector")
    report.append("   - Or use MIDI editor and manually adjust notes on specific beats")
    report.append("")
    report.append("---")
    report.append("")

# Add reference table
report.append("## Velocity Reference Table (Trance @ 141 BPM)")
report.append("")
report.append("| Element | Base Vel | Range | Std | Notes |")
report.append("|---------|----------|-------|-----|-------|")
report.append("| Kick | 110 | 100-120 | 5-10 | Consistent, slight variation |")
report.append("| Snare | 100 | 60-115 | 12-18 | Loud on 2/4, ghost notes 50-70 |")
report.append("| Clap | 95 | 80-110 | 10-15 | Layer with snare, offset timing |")
report.append("| Closed HH | 80 | 50-100 | 18-25 | Offbeats louder, 16ths quiet |")
report.append("| Open HH | 90 | 70-110 | 12-18 | Accent hits before snare |")
report.append("| Ride | 85 | 60-100 | 15-20 | Quarters louder |")
report.append("| Crash | 110 | 100-120 | 5-10 | Consistent (one-shots) |")
report.append("")

# Priority summary
report.append("## Action Priority")
report.append("")
report.append("### Critical (Fix immediately):")
for track in track_analysis:
    if track['severity'] == 'CRITICAL':
        report.append(f"- **{track['name']}** (std={track['velocity_std']})")
report.append("")

report.append("### Severe (Fix soon):")
for track in track_analysis:
    if track['severity'] == 'SEVERE':
        report.append(f"- **{track['name']}** (std={track['velocity_std']})")
report.append("")

report.append("### Moderate (Should fix):")
for track in track_analysis:
    if track['severity'] == 'MODERATE':
        report.append(f"- **{track['name']}** (std={track['velocity_std']})")
report.append("")

report.append("### Minor (Optional enhancement):")
for track in track_analysis:
    if track['severity'] == 'MINOR':
        report.append(f"- **{track['name']}** (std={track['velocity_std']})")
report.append("")

# Write report to file
output_file = r"C:\claude-workspace\AbletonAIAnalysis\reports\38b_5\recommendations\DynamicsHumanization.md"
with open(output_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(report))

print(f"Report generated: {output_file}")
print(f"Total tracks analyzed: {len(track_analysis)}")
print(f"Overall status: {overall_status}")
