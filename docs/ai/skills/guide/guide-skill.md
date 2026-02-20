# /guide - Feature Navigation Skill

## Purpose
Interactive guide that helps users discover and learn all features of the AbletonAIAnalysis toolkit through a task-based, exploratory menu system.

## Invocation
- `/guide` - Show main menu
- `/guide <topic>` - Jump to topic via fuzzy matching
- `/guide back` - Go up one level
- `/guide home` - Return to main menu

---

## Main Menu

When user invokes `/guide` with no arguments, display:

```
===============================================================================
                    ABLETON AI ANALYSIS - FEATURE GUIDE
===============================================================================

What would you like to do?

ANALYZE YOUR MUSIC
   [1] "Analyze my mixdown for issues"
         Clipping, dynamics, frequency balance, loudness, stereo width

   [2] "Check my stems for clashes before mixing"
         Find kick/bass collisions, masking, balance problems

   [3] "Analyze my Ableton project without exporting"
         Device chains, MIDI health, effect order issues (no audio needed)

   [4] "Get a quick health score for my .als file"
         Instant A-F grade with top 5 issues in 30 seconds

COMPARE TO PROFESSIONAL TRACKS
   [5] "Compare my mix to a reference track"
         Side-by-side frequency, loudness, dynamics comparison

   [6] "Build a reference library from YouTube"
         Download, analyze, and profile professional trance tracks

   [7] "Find what's different about my mix vs the pros"
         Gap analysis showing exactly where you're off-target

   [8] "Get a trance authenticity score"
         Sidechain pumping, supersaw detection, 303 acid elements

USE AI/ML FEATURES
   [9] "Ask an AI specialist about my mix"
         17 specialized prompts: low end, dynamics, stereo, loudness, etc.

   [10] "Let the system learn my style preferences"
          Feedback loop that adapts recommendations to your taste

   [11] "Cluster my references by style"
          K-means clustering discovers sub-styles in your library

   [12] "Find tracks similar to this one"
          Embedding-based similarity search across your references

CONTROL ABLETON LIVE
   [13] "Connect Claude to Ableton via OSC"
          Setup guide for real-time MCP control

   [14] "Adjust mix levels from Claude"
          Set volumes, panning, sends without touching Ableton

   [15] "Read my track names and devices"
          Query your current Ableton session

FIX MY MIX
   [16] "Get specific fix recommendations"
          Prescriptive fixes with exact device parameters

   [17] "Walk me through issues one by one"
          Interactive coach mode with verification

   [18] "Check if my mix is ready for export"
          Preflight checklist identifying blockers

TRACK & ORGANIZE
   [19] "Track my project versions over time"
          Database of .als changes and health improvements

   [20] "Compare two versions of my project"
          Diff showing what changed between versions

   [21] "Batch analyze all my projects"
          Rank songs by health, find best/worst

   [22] "See trends and insights"
          Dashboard with progress charts and patterns

-------------------------------------------------------------------------------
Type a number [1-22] or keyword to explore (e.g., "youtube", "ai", "stems")
===============================================================================
```

---

## Fuzzy Matching Keywords

Map these keywords to features:

| Keyword(s) | Feature # | Description |
|------------|-----------|-------------|
| mixdown, mix, audio, analyze | 1 | Analyze mixdown |
| stems, stem, clash, collision | 2 | Stem analysis |
| als, project, ableton, device | 3 | ALS project analysis |
| quick, health, score, grade | 4 | Quick health score |
| compare, reference, ref, vs | 5 | Reference comparison |
| youtube, yt, library, download | 6 | YouTube library |
| gap, different, difference, pros | 7 | Gap analysis |
| trance, score, authenticity, pumping, 303 | 8 | Trance score |
| ai, ml, specialist, prompt, lowend | 9 | AI specialists |
| learn, learning, style, adapt | 10 | Style learning |
| cluster, kmeans, group, style | 11 | Style clustering |
| similar, similarity, find, embedding | 12 | Similarity search |
| osc, connect, setup, mcp | 13 | Ableton OSC setup |
| level, volume, pan, send, adjust | 14 | Mix level control |
| track names, devices, query, read | 15 | Query Ableton |
| fix, recommendation, prescriptive | 16 | Fix recommendations |
| coach, walk, interactive, step | 17 | Coach mode |
| preflight, export, ready, check | 18 | Preflight check |
| version, track, history, database | 19 | Version tracking |
| diff, compare versions, changed | 20 | Version compare |
| batch, all, multiple, rank | 21 | Batch analysis |
| trends, insights, dashboard, chart | 22 | Dashboard |

---

## Feature Details

### [1] Analyze my mixdown for issues

**What it does:**
Analyzes your stereo mixdown for technical issues across 9 dimensions: clipping, dynamics, frequency balance, loudness, stereo width, transients, tempo, and section-based problems.

**What you need:**
- A mixdown file (.wav, .flac, .mp3)

**How to use it:**
```bash
cd C:/claude-workspace/AbletonAIAnalysis/projects/music-analyzer

# Basic analysis
python analyze.py --audio "path/to/mix.wav"

# With verbose output
python analyze.py --audio "path/to/mix.wav" --verbose

# Using standard input structure
python analyze.py --song MySong
```

**What you get:**
- Clipping count and locations
- Dynamic range (peak, RMS, crest factor)
- Frequency balance across 7 bands
- LUFS loudness measurement
- Stereo width and correlation
- Section-by-section issue detection
- HTML report saved to `/reports/`

**Related features:** [2] Stem analysis, [5] Reference comparison, [9] AI specialists

---

### [2] Check my stems for clashes before mixing

**What it does:**
Analyzes multiple stems together to find frequency collisions, masking issues, and balance problems BEFORE they become problems in your final mix.

**What you need:**
- A folder of stem files (kick.wav, bass.wav, etc.)

**How to use it:**
```bash
# Analyze stems folder
python analyze.py --stems "path/to/stems/"

# Combined with mix analysis
python analyze.py --audio mix.wav --stems "path/to/stems/"

# Using standard input structure (stems in /inputs/MySong/stems/)
python analyze.py --song MySong
```

**What you get:**
- Frequency clash detection (e.g., "kick vs bass collision at 60-120Hz")
- Masking risk warnings
- Per-stem dominant frequencies
- Balance issues (stems >6dB off average)
- Specific fix recommendations

**Related features:** [1] Mixdown analysis, [9] AI low end specialist

---

### [3] Analyze my Ableton project without exporting

**What it does:**
Reads your .als project file directly and analyzes device chains, MIDI health, and effect order WITHOUT needing audio export. Instant feedback on mixing anti-patterns.

**What you need:**
- An Ableton Live project file (.als)

**How to use it:**
```bash
cd C:/claude-workspace/AbletonAIAnalysis/projects/music-analyzer

# Full diagnosis
python src/als_doctor.py diagnose "path/to/project.als"

# Quick overview
python src/als_doctor.py quick "path/to/project.als"
```

**What you get:**
- Device chain analysis per track
- Effect order issues (e.g., "EQ after limiter is unusual")
- Disabled device clutter detection
- MIDI clip health (empty clips, duplicates)
- Double/triple compression warnings
- Unusual parameter values
- A-F health grade

**Related features:** [4] Quick health score, [16] Fix recommendations, [19] Version tracking

---

### [4] Get a quick health score for my .als file

**What it does:**
30-second health check that gives you an A-F grade and your top 5 issues. Perfect for quick triage.

**What you need:**
- An Ableton Live project file (.als)

**How to use it:**
```bash
python src/als_doctor.py quick "path/to/project.als"
```

**What you get:**
```
Project: MyTrack.als
Health Score: B+ (82/100)

Top Issues:
1. [WARNING] Track "Bass": EQ8 after Compressor - consider swapping order
2. [WARNING] Track "Lead": 3 disabled devices (clutter)
3. [INFO] Track "Drums": Limiter threshold at -12dB (aggressive)
4. [INFO] 2 empty MIDI clips detected
5. [INFO] Track "Pad": Very wide stereo (check mono compatibility)
```

**Related features:** [3] Full diagnosis, [17] Coach mode

---

### [5] Compare my mix to a reference track

**What it does:**
Side-by-side comparison of your mix against a professional reference track. Shows exactly where your frequency balance, loudness, dynamics, and stereo width differ.

**What you need:**
- Your mixdown file
- A reference track in the same genre

**How to use it:**
```bash
# Basic comparison
python analyze.py --audio "my_mix.wav" --compare-ref "reference.wav"

# Using standard input structure
python analyze.py --song MySong --compare-ref "references/pro_track.wav"
```

**What you get:**
- Frequency band comparison table (sub through air)
- Loudness difference in LUFS
- Dynamic range comparison
- Stereo width comparison
- Specific recommendations: "Your low-mids are +3dB hot compared to reference"

**Related features:** [6] YouTube library, [7] Gap analysis, [8] Trance score

---

### [6] Build a reference library from YouTube

**What it does:**
Download professional trance tracks from YouTube, extract audio, run full analysis, and build a reference profile. Creates a database of 215+ reference tracks for comparison.

**What you need:**
- YouTube URLs of reference tracks

**How to use it:**
```bash
cd C:/claude-workspace/AbletonAIAnalysis/projects/youtube-reference-track-analysis

# Initialize database
python yt_analyzer.py db init

# Ingest a track
python yt_analyzer.py ingest "https://youtube.com/watch?v=..."

# Run analysis
python yt_analyzer.py analyze <track_id>

# List all tracks
python yt_analyzer.py list

# Search similar
python yt_analyzer.py search --similar-to <track_id>
```

**What you get:**
- Downloaded audio (MP3/WAV)
- Full feature extraction (tempo, key, energy, trance features)
- Arrangement analysis (intro, buildup, drop, breakdown, outro)
- Stem separation via Demucs
- Database entry for future comparison

**Related features:** [7] Gap analysis, [11] Style clustering, [12] Similarity search

---

### [7] Find what's different about my mix vs the pros

**What it does:**
Gap analysis comparing your track against the statistical profile of 215+ reference tracks. Shows exactly where you're outside the "pro" range with severity ratings.

**What you need:**
- Your mixdown file
- Reference profile built (from YouTube library or manual references)

**How to use it:**
```bash
python analyze.py --audio "my_mix.wav" --gap-analysis

# With prescriptive fixes
python analyze.py --audio "my_mix.wav" --gap-analysis --prescriptive
```

**What you get:**
- Per-feature gap analysis with z-scores
- Severity classification (Critical >3σ, Warning 2-3σ, Minor 1-2σ)
- Direction indicators (too high / too low)
- Percentile placement (where you fall in the reference distribution)
- Prioritized fix recommendations

**Related features:** [5] Reference comparison, [8] Trance score, [16] Fix recommendations

---

### [8] Get a trance authenticity score

**What it does:**
Measures how "trance" your track sounds using genre-specific feature extraction: sidechain pumping depth, supersaw presence, 303 acid elements, energy progression, four-on-floor kick patterns.

**What you need:**
- Your mixdown file

**How to use it:**
```bash
python analyze.py --audio "my_mix.wav" --trance-score
```

**What you get:**
- Overall trance score (0-100%)
- Breakdown by feature:
  - Tempo score (is it 130-150 BPM?)
  - Pumping score (sidechain compression depth)
  - Energy progression (breakdown/buildup detection)
  - Four-on-floor kick pattern
  - Supersaw presence (stereo width, detuning)
  - 303/acid elements (filter sweeps, resonance)
  - Off-beat hi-hat patterns

**Related features:** [7] Gap analysis, [9] AI trance specialist

---

### [9] Ask an AI specialist about my mix

**What it does:**
17 specialized AI prompts for detailed mixing advice. Each specialist focuses on one aspect of your mix and provides actionable recommendations.

**Available specialists:**
1. **Low End** - Kick/bass relationship, sub-bass, sidechain
2. **Frequency Balance** - EQ decisions, mud, harshness
3. **Dynamics** - Compression, punch, crest factor
4. **Stereo & Phase** - Width, mono compatibility
5. **Loudness** - LUFS, streaming optimization
6. **Sections** - Drop impact, arrangement flow
7. **Trance Arrangement** - Buildup mechanics, 8-bar rule
8. **Stem Reference** - Stem-by-stem vs reference
9. **Gain Staging** - Level management, headroom
10. **Stereo Field** - Detailed stereo image
11. **Frequency Collision** - Element-by-element clashes
12. **Dynamics Humanization** - Velocity variation
13. **Section Contrast** - Energy flow analysis
14. **Density/Busyness** - Arrangement density
15. **Chord/Harmony** - Harmonic analysis
16. **Device Chain** - Plugin optimization
17. **Priority Summary** - Aggregated issue ranking

**How to use it:**
```bash
# Generate analysis JSON first
python analyze.py --audio "my_mix.wav" --output-json

# Then ask Claude with the specialist prompt
# (prompts are in docs/ai/RecommendationGuide/prompts/)
```

**Related features:** [1] Mixdown analysis, [7] Gap analysis

---

### [10] Let the system learn my style preferences

**What it does:**
Feedback loop that learns from your fix acceptance/rejection. Over time, recommendations adapt to your specific style preferences.

**How to use it:**
```bash
# After applying fixes, rate them
python analyze.py --feedback

# View learning statistics
python analyze.py --learning-stats

# Reset learning data
python analyze.py --reset-learning
```

**What you get:**
- Personalized recommendations based on past feedback
- Feature weight adjustment
- Style profile tuning

**Related features:** [11] Style clustering, [16] Fix recommendations

---

### [11] Cluster my references by style

**What it does:**
Uses K-means clustering to discover sub-styles within your reference library. Automatically groups similar tracks and names clusters by their distinctive features.

**How to use it:**
```bash
cd C:/claude-workspace/AbletonAIAnalysis/projects/music-analyzer
python -m src.profiling.style_clusters --visualize
```

**What you get:**
- Auto-detected clusters (e.g., "Heavy Sidechain + High Energy", "Melodic + Wide Stereo")
- Exemplar tracks per cluster
- Cluster statistics
- Visualization of style distribution

**Related features:** [6] YouTube library, [12] Similarity search

---

### [12] Find tracks similar to this one

**What it does:**
Embedding-based similarity search using OpenL3 audio embeddings. Find tracks in your reference library that sound similar to a query track.

**How to use it:**
```bash
# Build embedding index (one time)
python analyze.py --build-embeddings

# Find similar tracks
python analyze.py --find-similar "query_track.wav" --top 10
```

**What you get:**
- Top N most similar tracks
- Similarity scores (cosine distance)
- Feature comparison with matches

**Related features:** [6] YouTube library, [11] Style clustering

---

### [13] Connect Claude to Ableton via OSC

**What it does:**
Setup guide for connecting Claude to Ableton Live via OSC for real-time control. Allows Claude to adjust your mix without you touching Ableton.

**Setup steps:**
1. Start the OSC daemon (keep running in separate terminal):
   ```bash
   cd C:/claude-workspace/ableton-live-mcp-server
   python osc_daemon.py
   ```

2. In Ableton Live:
   - Preferences → Link/Tempo/MIDI
   - Control Surface: AbletonOSC
   - Enable it

3. Test the connection:
   - Ask Claude: "get track names"
   - If it works, you're connected

**Troubleshooting:**
- Timeout errors: Restart OSC daemon
- No response: Check AbletonOSC is enabled in Ableton
- Wrong tracks: Make sure you're in the right Ableton project

**Related features:** [14] Mix level control, [15] Query Ableton

---

### [14] Adjust mix levels from Claude

**What it does:**
Control Ableton mixer parameters from Claude without touching Ableton. Set volumes, panning, send levels, and effect parameters.

**What you need:**
- OSC daemon running (see feature [13])
- Ableton project open

**How to use it:**
Just ask Claude naturally:
- "Set the bass track to -6dB"
- "Pan the hi-hats 30% left"
- "Turn up send A on the lead by 20%"
- "Disable the reverb on track 3"

**What Claude can do:**
- Set track volumes
- Adjust panning
- Control send levels
- Enable/disable devices
- Adjust effect parameters

**What Claude cannot do:**
- Delete devices
- Edit MIDI notes
- Draw automation
- Create new tracks

**Related features:** [13] OSC setup, [15] Query Ableton

---

### [15] Read my track names and devices

**What it does:**
Query your current Ableton session to see track names, device chains, and current parameter values.

**What you need:**
- OSC daemon running (see feature [13])
- Ableton project open

**How to use it:**
Ask Claude:
- "What tracks do I have?"
- "What devices are on my bass track?"
- "What's the current volume of the kick?"

**Related features:** [13] OSC setup, [14] Mix level control

---

### [16] Get specific fix recommendations

**What it does:**
Generates prescriptive fix recommendations with exact device parameters. Maps detected issues to specific Ableton device settings.

**How to use it:**
```bash
python analyze.py --audio "my_mix.wav" --prescriptive

# Or with gap analysis
python analyze.py --audio "my_mix.wav" --gap-analysis --prescriptive
```

**What you get:**
```
Issue: Low-mids too loud (+2.7dB vs reference)
Fix: Add EQ8 → Cut 200-400Hz by 2-3dB with Q=1.0
Confidence: High
Impact: Should reduce mud and improve clarity

Issue: Insufficient sidechain pumping
Fix: Add Compressor on bass → Sidechain to kick
     Attack: 0.5ms, Release: 150ms, Ratio: 4:1, Threshold: -18dB
Confidence: Medium
Impact: Will add rhythmic energy typical of trance
```

**Related features:** [7] Gap analysis, [17] Coach mode

---

### [17] Walk me through issues one by one

**What it does:**
Interactive coaching mode that walks you through each issue, waits for you to fix it, then re-analyzes to verify the improvement.

**How to use it:**
```bash
python src/als_doctor.py coach "path/to/project.als"
```

**Session flow:**
1. Shows first issue with explanation
2. Provides fix suggestion
3. Waits for you to make the change in Ableton
4. Press Enter to re-analyze
5. Verifies if fixed, moves to next issue
6. Tracks progress throughout session

**Related features:** [16] Fix recommendations, [18] Preflight check

---

### [18] Check if my mix is ready for export

**What it does:**
Preflight checklist that identifies blockers before you export. Catches issues that would cause problems on streaming platforms.

**How to use it:**
```bash
# Basic preflight
python src/als_doctor.py preflight "path/to/project.als"

# Strict mode (catches more issues)
python src/als_doctor.py preflight "path/to/project.als" --strict
```

**What you get:**
```
PREFLIGHT CHECK: MyTrack.als

BLOCKERS (must fix):
  [X] Clipping detected on Master track
  [X] LUFS is -5.2, target is -14 for streaming

WARNINGS (should fix):
  [!] Bass track has no high-pass filter (DC rumble risk)
  [!] 3 tracks have solo enabled

INFO:
  [i] Project tempo: 140 BPM
  [i] Estimated loudness: -5.2 LUFS
  [i] Total tracks: 24

Ready for export: NO (2 blockers)
```

**Related features:** [17] Coach mode, [1] Mixdown analysis

---

### [19] Track my project versions over time

**What it does:**
Database that tracks every version of your .als files, their health scores, and changes over time. See your improvement history.

**How to use it:**
```bash
# Initialize database
python src/als_doctor.py db init

# After each save, scan your project
python src/als_doctor.py db scan "path/to/project.als"

# View history
python src/als_doctor.py db history "song_name"

# View trends
python src/als_doctor.py db trends "song_name"
```

**What you get:**
- Version history with timestamps
- Health score progression
- Issue count over time
- Change annotations

**Related features:** [20] Version compare, [22] Dashboard

---

### [20] Compare two versions of my project

**What it does:**
Diff between two .als files showing exactly what changed: track additions/removals, device modifications, parameter changes.

**How to use it:**
```bash
python src/als_doctor.py compare "v1.als" "v2.als"
```

**What you get:**
```
CHANGES: v1.als → v2.als

TRACKS:
  + Added: "Arp Synth"
  ~ Modified: "Bass" (device chain changed)
  - Removed: "FX Layer 2"

DEVICES:
  [Bass] + Added: Compressor (after EQ8)
  [Bass] ~ EQ8: Band 3 gain: -2dB → -4dB
  [Lead] ~ Reverb: Decay: 2.5s → 1.8s

HEALTH SCORE:
  v1: C+ (72/100)
  v2: B  (78/100)
  Improvement: +6 points
```

**Related features:** [19] Version tracking, [3] ALS analysis

---

### [21] Batch analyze all my projects

**What it does:**
Analyze multiple .als files at once. Rank them by health score, find your best and worst projects.

**How to use it:**
```bash
# Scan directory
python src/als_doctor.py scan "D:/Music/Projects" --limit 50

# Sort by score
python src/als_doctor.py scan "D:/Music/Projects" --sort score

# Find cleanup candidates
python src/als_doctor.py scan "D:/Music/Projects" --filter low
```

**What you get:**
```
BATCH ANALYSIS: 47 projects scanned

TOP 5 (healthiest):
  1. Summer_Trance_Final.als   A  (94/100)
  2. Progressive_v3.als        A- (91/100)
  3. Uplifting_Remake.als      B+ (88/100)
  ...

BOTTOM 5 (needs work):
  1. Old_Sketch_2019.als       D  (52/100)
  2. Experiment_Bass.als       D+ (58/100)
  ...

GRADE DISTRIBUTION:
  A: 8 projects
  B: 15 projects
  C: 18 projects
  D: 6 projects
```

**Related features:** [19] Version tracking, [22] Dashboard

---

### [22] See trends and insights

**What it does:**
Dashboard with visualizations of your progress over time. See patterns in your mixing habits.

**How to use it:**
```bash
python src/als_doctor.py dashboard
```

Then open http://localhost:8050 in your browser.

**What you get:**
- Health score trends over time
- Common issues frequency
- Improvement velocity
- Time spent on each project
- Genre/style distribution
- Recommendations based on patterns

**Related features:** [19] Version tracking, [21] Batch analysis

---

## Navigation Instructions

When user selects a feature:
1. Show the full feature detail from above
2. End with related features for exploration
3. Always show navigation: `Back: /guide back  |  Home: /guide`

When user types a keyword:
1. Fuzzy match against keyword table
2. If single match, show that feature
3. If multiple matches, show options to choose from
4. If no match, show "Feature not found" and main menu
