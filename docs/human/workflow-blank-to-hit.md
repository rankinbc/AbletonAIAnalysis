# From Blank Project to Hit Song

A step-by-step workflow for using the AbletonAIAnalysis system to assist in producing a professional-quality track.

---

## Phase 1: Build Your Reference Library

Before writing, collect 5-10 pro tracks you want to sound like.

```bash
cd C:/claude-workspace/AbletonAIAnalysis/projects/youtube-reference-track-analysis

# Initialize database (first time only)
python yt_analyzer.py db init

# Download and analyze reference tracks
python yt_analyzer.py ingest "https://youtube.com/watch?v=..."
python yt_analyzer.py analyze <track_id>
```

**What happens:** The system extracts their DNA - tempo, energy curves, frequency balance, sidechain depth, arrangement patterns. This becomes your target profile.

---

## Phase 2: Write & Arrange (with Live Feedback)

Work in Ableton normally - write your track.

Periodically check your project health **without exporting audio**:

```bash
cd C:/claude-workspace/AbletonAIAnalysis/projects/music-analyzer

# Quick 30-second health check
python src/als_doctor.py quick "D:/Music/Projects/MyTrack.als"

# Full diagnosis when you want details
python src/als_doctor.py diagnose "D:/Music/Projects/MyTrack.als"
```

**What you get:**
- A-F health grade
- Device chain issues (EQ after limiter, double compression)
- MIDI health (empty clips, duplicates)
- Effect order problems
- Disabled device clutter

---

## Phase 3: First Mixdown Analysis

Export your mix from Ableton, then analyze:

```bash
# Basic analysis
python analyze.py --audio "mix_v1.wav"

# With trance authenticity score
python analyze.py --audio "mix_v1.wav" --trance-score
```

**Trance score shows:**
- Sidechain pumping depth
- Supersaw presence
- 303/acid elements
- Four-on-floor kick pattern
- Energy progression (breakdowns/buildups)

---

## Phase 4: Gap Analysis vs References

Compare your mix against the professional reference profile:

```bash
# See where you're off-target
python analyze.py --audio "mix_v1.wav" --gap-analysis

# With specific fix parameters
python analyze.py --audio "mix_v1.wav" --gap-analysis --prescriptive
```

**Example output:**
```
CRITICAL: Bass is +3.2dB too loud (z-score: 2.8)
  Fix: Reduce bass fader by 3dB or cut 80-120Hz by 2dB

WARNING: Stereo width is 15% narrower than references
  Fix: Add stereo widener to lead synth, target 85% width

WARNING: Sidechain pumping depth is 40% below target
  Fix: Increase compressor ratio to 4:1, threshold to -18dB
```

---

## Phase 5: Real-Time Mix Adjustments

Connect Claude to Ableton via OSC for hands-free mixing:

**Setup (one time):**
```bash
# Terminal 1: Start OSC daemon
cd C:/claude-workspace/ableton-live-mcp-server
python osc_daemon.py

# In Ableton: Preferences > Link/Tempo/MIDI > Control Surface > AbletonOSC
```

**Then ask Claude naturally:**
- "Set the bass track to -3dB"
- "Pan the hi-hats 25% left"
- "Increase the reverb send on the lead"
- "What's the current volume of the kick?"

Claude adjusts your mix while you listen.

---

## Phase 6: Iterate with Version Tracking

Track your improvement across versions using the database:

```bash
# Analyze your project (stored in database)
python als_doctor.py diagnose "MyTrack.als"

# Compare to reference
python analyze.py --audio "MyTrack_mix.wav" --compare-ref "references/pro_track.wav"

# Track project history in database
python als_doctor.py db history "MyTrack"
python als_doctor.py db trends "MyTrack"
```

**The system learns:** Your fix acceptance/rejection teaches it your style preferences over time.

---

## Phase 7: Preflight Check

Before final export, catch any blockers:

```bash
# Standard preflight
python src/als_doctor.py preflight "MyTrack_Final.als"

# Strict mode (catches more issues)
python src/als_doctor.py preflight "MyTrack_Final.als" --strict
```

**Checks for:**
- Clipping on any track
- LUFS too hot for streaming (-14 LUFS target)
- Mono compatibility issues
- DC offset / rumble
- Solo buttons left on
- Bypassed effects that should be active

---

## Quick Reference

| Phase | Command | Time |
|-------|---------|------|
| References | `yt_analyzer.py ingest <url>` | 2-5 min per track |
| Writing | `als_doctor.py quick <file>` | 30 sec |
| Mixdown | `analyze.py --audio <file> --trance-score` | 1-2 min |
| Gap Analysis | `analyze.py --audio <file> --gap-analysis --prescriptive` | 1-2 min |
| Live Control | Ask Claude after OSC setup | Real-time |
| Versioning | `analyze.py --song <name> --version <v>` | 1-2 min |
| Preflight | `als_doctor.py preflight <file>` | 30 sec |

---

## The Loop

```
Reference → Write → Quick-check → Mixdown → Gap analysis → Fix → Repeat → Preflight → Export
```

Each iteration gets you closer to the professional sound you're targeting.
