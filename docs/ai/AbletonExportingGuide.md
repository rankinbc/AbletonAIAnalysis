# Ableton 11 Export Guide for AI Analysis
## Optimal Settings for Different Analysis Scenarios

This guide shows you exactly how to export your Ableton 11 projects for AI analysis and mastering.

---

## Table of Contents
- [Quick Reference](#quick-reference)
- [Scenario 1: Export for AI Mastering](#scenario-1-export-for-ai-mastering)
- [Scenario 2: Export Stems for Mix Analysis](#scenario-2-export-stems-for-mix-analysis)
- [Scenario 3: Export for Frequency Clash Detection](#scenario-3-export-for-frequency-clash-detection)
- [Scenario 4: MIDI Analysis Only](#scenario-4-midi-analysis-only)
- [Understanding Each Setting](#understanding-each-setting)
- [File Format Comparison](#file-format-comparison)
- [Common Mistakes](#common-mistakes)
- [Troubleshooting](#troubleshooting)

---

## Quick Reference

### TL;DR - Most Common Use Case

**For full mix analysis + mastering:**
```
Rendered Track: Master
Include Return and Master Effects: OFF
Normalize: OFF
Convert to Mono: OFF
Bit Depth: 16-bit (if size matters) or 24-bit (if not)
Sample Rate: 44100 Hz
File Type: WAV
Peak level should be: -6dB to -3dB
```

**For stem analysis:**
```
Rendered Track: All Individual Tracks
Include Return and Master Effects: OFF
Normalize: OFF
Convert to Mono: OFF (unless the track is truly mono)
Bit Depth: 16-bit
File Type: WAV
```

---

## Scenario 1: Export for AI Mastering

**Use Case:** You have a finished mix and want AI to master it using a reference track.

### Step-by-Step Process

#### Before Exporting:

1. **Check Your Master Channel:**
   - Make sure peak level is between **-6dB and -3dB**
   - Remove any limiter/maximizer from master channel
   - Remove any master bus EQ (unless it's part of your artistic vision)
   - Aim for dynamic range, not loudness

2. **Set Your Loop Brace:**
   - Press `Cmd/Ctrl + L` to set loop to selection
   - Cover the entire song from first sound to last

#### Export Settings:

```
File → Export Audio/Video

Selection:
  Rendered Track: Master

Render Start: 1.1.1 (or wherever your song starts)
Render Length: [Full song length]

Rendering Options:
  Include Return and Master Effects: OFF ⚠️ IMPORTANT
  Render as Loop: OFF
  Convert to Mono: OFF
  Normalize: OFF
  Create Analysis File: OFF

Sample Rate: 44100 Hz (or match your project rate)

PCM:
  Encode PCM: ON
  File Type: WAV
  Bit Depth: 24-bit (preferred) or 16-bit (if size matters)
  Dither Options: Triangular (if using 16-bit)

MP3:
  Encode MP3: OFF (not needed)

Video:
  Create Video: OFF
```

#### After Exporting:

1. **Verify the export:**
   - Peak should be around -6dB to -3dB
   - No clipping (peaks shouldn't touch 0dB)
   - If too loud: reduce master fader, re-export
   - If too quiet: that's okay! Mastering will fix it

2. **File location:**
   - Ableton exports to your project folder by default
   - Or choose a specific location

**Why these settings?**
- Master channel only = full mix
- Effects OFF = leaves headroom for mastering
- No normalize = preserves your actual levels
- 24-bit or 16-bit = either works, 24-bit is safer

---

## Scenario 2: Export Stems for Mix Analysis

**Use Case:** You want AI to analyze individual tracks and find frequency clashes, balance issues, etc.

### What Are Stems?

Stems = individual tracks or groups exported separately. Common examples:
- Kick
- Bass
- Drums (all percussion)
- Synths/Keys
- Lead Vocals
- Backing Vocals
- FX/Ambient

### Option A: Export All Individual Tracks (Most Detailed)

#### Step-by-Step:

1. **Prepare Your Project:**
   - Solo/unsolo all tracks (make sure nothing is soloed or muted unless intentional)
   - Make sure all tracks have meaningful names
   - Example: rename "Audio 3" to "Lead Synth"

2. **Export Settings:**

```
File → Export Audio/Video

Selection:
  Rendered Track: All Individual Tracks ✅

Render Start: 1.1.1
Render Length: [Full song length]

Rendering Options:
  Include Return and Master Effects: OFF ⚠️ IMPORTANT
  Render as Loop: OFF
  Convert to Mono: (See below)
  Normalize: OFF
  Create Analysis File: OFF

Sample Rate: 44100 Hz

PCM:
  Encode PCM: ON
  File Type: WAV
  Bit Depth: 16-bit (good compromise)
  Dither Options: Triangular

MP3:
  Encode MP3: OFF
```

#### Convert to Mono - When to Use:

| Track Type | Convert to Mono? | Reason |
|------------|------------------|---------|
| Kick | ✅ YES | Mono source, saves 50% space |
| Bass | ✅ YES | Usually mono, saves space |
| Snare | ✅ YES | Mono source |
| Mono synths | ✅ YES | If truly mono |
| Stereo pads | ❌ NO | Stereo width matters |
| Vocals (with stereo FX) | ❌ NO | Stereo info matters |
| Drum bus | ❌ NO | Contains stereo panning |
| Lead synth (mono + stereo FX) | ❌ NO | Effects create stereo |

**Rule of thumb:** If unsure, leave "Convert to Mono" OFF.

#### After Exporting:

You'll get one file per track:
```
my_song/
├── Kick.wav
├── Bass.wav
├── Lead Synth.wav
├── Pad.wav
├── Vocals.wav
└── ...
```

**File size:** ~45 MB per 4-min track (16-bit stereo)
- If too large: enable "Convert to Mono" for truly mono tracks
- If still too large: use 16-bit instead of 24-bit

---

### Option B: Export Groups/Buses (Faster, Smaller)

If you have many tracks, group them first:

**Typical stem grouping:**
1. **Drums** (kick, snare, hats, percussion)
2. **Bass** (all bass elements)
3. **Keys/Synths** (all melodic synths)
4. **Leads** (main melodic elements)
5. **Vocals** (all vocal tracks)
6. **FX** (risers, impacts, ambient)

#### How to Group in Ableton:

1. Select tracks you want to group
2. `Cmd/Ctrl + G` to create group
3. Name the group track (e.g., "Drums")
4. Repeat for all groups

#### Export Settings:

```
Rendered Track: All Individual Tracks
(This will now export each GROUP as one file)

[Same settings as Option A above]
```

**Result:** 4-6 files instead of 20-50 files
- Much more manageable
- Still enough detail for analysis
- Smaller file sizes

---

## Scenario 3: Export for Frequency Clash Detection

**Use Case:** You want to find which tracks are fighting for the same frequency space.

This is similar to Scenario 2, but with specific considerations:

### Export Settings:

```
Rendered Track: All Individual Tracks (or groups)
Include Return and Master Effects: OFF ⚠️ CRITICAL
Render as Loop: OFF
Convert to Mono: OFF (need stereo info)
Normalize: OFF ⚠️ CRITICAL
Bit Depth: 16-bit (sufficient)
File Type: WAV
```

**Why these specific settings?**

1. **Effects OFF:** 
   - Need clean, unprocessed tracks
   - Reverb/delay can mask frequency issues
   - Want to analyze the raw sound

2. **Normalize OFF:**
   - Need to preserve relative volume levels
   - If bass is too loud vs kick, we need to know!
   - Normalization would hide this

3. **No Mono conversion:**
   - Stereo width affects perceived frequency content
   - Need accurate stereo information

### Which Tracks to Export:

Focus on tracks that might clash:
- ✅ Kick + Bass (classic clash at 60-100Hz)
- ✅ Bass + Sub synths (low-end overlap)
- ✅ Lead vocal + backing vocals (midrange clash)
- ✅ Snare + claps (200-400Hz area)
- ✅ Multiple synths in same register
- ❌ Skip pure FX tracks (risers, impacts)
- ❌ Skip very quiet ambient tracks

### Pro Tip: Two-Pass Export

**Pass 1:** Export low-frequency tracks
```
Select: Kick, Bass, Sub, 808
Export as: low_freq_stems/
```

**Pass 2:** Export mid-frequency tracks
```
Select: Vocals, Leads, Snares, Mid synths
Export as: mid_freq_stems/
```

**Pass 3:** Export high-frequency tracks
```
Select: Hats, Cymbals, High synths, Air/breaths
Export as: high_freq_stems/
```

This organization helps focus analysis on relevant frequency ranges.

---

## Scenario 4: MIDI Analysis Only

**Use Case:** You just want AI to analyze your chord progressions, melodies, and MIDI data.

### The Easy Way: No Export Needed!

The `pyableton` library can extract MIDI directly from your .als file:

```python
from pyableton import Ableton
project = Ableton("my_song.als")
project.to_midi("output.mid")
```

**No audio export required!** Just provide your .als file.

### The Manual Way (If You Want Control):

#### Export Individual MIDI Clips:

1. **Right-click each MIDI clip → Export MIDI Clip**
2. Name it clearly (e.g., "Bassline.mid", "Chords.mid")
3. Save to a folder

#### Export Multiple Clips at Once:

Unfortunately, Ableton doesn't have "export all MIDI" like it does for audio. You'll need to:
- Export clips one by one, OR
- Use the `pyableton` library (recommended)

---

## Understanding Each Setting

### Rendered Track

| Option | What It Does | When to Use |
|--------|--------------|-------------|
| **Master** | Exports full mix through master channel | Final mix for mastering |
| **All Individual Tracks** | Exports each track separately | Stem analysis |
| **Selected Tracks Only** | Exports only highlighted tracks | Specific stem analysis |

### Include Return and Master Effects

| Setting | Result | Use For |
|---------|--------|---------|
| **ON** | Includes reverb, delay, master processing | Creative exports, bounce for collaboration |
| **OFF** | Raw, unprocessed stems | AI analysis, mastering, remixing |

**For AI analysis: Always OFF!**

### Normalize

| Setting | What It Does | Impact on Analysis |
|---------|--------------|-------------------|
| **ON** | Makes loudest peak hit 0dB | ❌ DESTROYS relative levels between stems |
| **OFF** | Preserves original levels | ✅ REQUIRED for accurate analysis |

**For AI analysis: Always OFF!**

### Convert to Mono

| Setting | Result | When to Use |
|---------|--------|-------------|
| **ON** | L+R channels summed to mono | Mono sources (kick, bass, mono synths) |
| **OFF** | Preserves stereo | Anything with stereo width |

**Benefit of mono:** 50% smaller file size
**Cost of mono:** Loses stereo information (don't use on stereo tracks!)

### Sample Rate

| Rate | Quality | File Size | Use For |
|------|---------|-----------|---------|
| **44100 Hz** | CD quality | Standard | ✅ Default choice |
| **48000 Hz** | Video standard | 9% larger | Video sync needed |
| **88200 Hz** | High quality | 2x larger | Overkill for analysis |
| **96000 Hz** | Very high | 2.2x larger | Unnecessary for analysis |

**For analysis: Use 44100 Hz** (or match your project rate)

### Bit Depth

| Bit Depth | Dynamic Range | File Size | Quality |
|-----------|---------------|-----------|---------|
| **16-bit** | 96 dB | 1x | ✅ Good enough for most analysis |
| **24-bit** | 144 dB | 1.5x | ✅ Safer choice, more headroom |
| **32-bit float** | ~1500 dB | 2x | Overkill for analysis |

**For analysis:**
- 16-bit: Perfectly fine, saves space
- 24-bit: Recommended if you have space
- 32-bit: Unnecessary

### Dither Options

Only matters if converting from higher to lower bit depth (e.g., 32-bit project → 16-bit export).

| Option | Quality | Use Case |
|--------|---------|----------|
| **None** | Can add distortion | Only if no bit reduction |
| **Triangular** | ✅ Best general purpose | Default choice |
| **Rectangular** | Slightly worse | Not recommended |

**Default: Triangular** (if exporting to 16-bit)

---

## File Format Comparison

### For Analysis:

| Format | Lossless? | Size | Support | Recommendation |
|--------|-----------|------|---------|----------------|
| **WAV** | ✅ Yes | Large | Universal | ✅ **Best choice** |
| **FLAC** | ✅ Yes | Medium | Good | ✅ Good if space matters |
| **AIFF** | ✅ Yes | Large | Mac-focused | Use WAV instead |
| **MP3** | ❌ No | Small | Universal | ❌ Never for analysis |
| **OGG** | ❌ No | Small | Limited | ❌ Never for analysis |

### File Size Examples (4-minute song, 44.1kHz):

```
24-bit WAV stereo:    ~68 MB
16-bit WAV stereo:    ~45 MB
16-bit WAV mono:      ~23 MB
24-bit FLAC stereo:   ~35 MB
16-bit FLAC stereo:   ~25 MB
320kbps MP3:          ~10 MB (but lossy!)
```

**Recommendation:**
- **Primary choice:** 16-bit WAV (good balance)
- **If space is critical:** 16-bit FLAC or convert WAV→FLAC after export
- **If quality is critical:** 24-bit WAV

---

## Common Mistakes

### ❌ Mistake #1: Including Master Effects

**Problem:**
```
Include Return and Master Effects: ON
Result: Reverb, limiting, compression baked in
Impact: Can't analyze clean stems
```

**Fix:** Turn OFF

---

### ❌ Mistake #2: Normalizing Stems

**Problem:**
```
Normalize: ON
Result: Every stem hits 0dB
Impact: Loses relative volume relationships
```

**Example:**
- Your bass is too loud vs kick (problem!)
- Normalize makes both hit 0dB
- AI can't tell which is actually louder
- Can't detect the mixing issue

**Fix:** Turn OFF

---

### ❌ Mistake #3: Too Hot Mix (for Mastering)

**Problem:**
```
Master fader: 0dB
Peak level: -0.1dB (almost clipping)
Result: No headroom for mastering
```

**Fix:** 
- Lower master fader until peaks are at -6dB to -3dB
- Re-export

---

### ❌ Mistake #4: Exporting MP3 for Analysis

**Problem:**
```
File Type: MP3
Result: Lossy compression artifacts
Impact: Frequency analysis is inaccurate
```

**Fix:** Always use WAV or FLAC

---

### ❌ Mistake #5: Converting Stereo Tracks to Mono

**Problem:**
```
Track: Stereo pad with wide stereo image
Convert to Mono: ON
Result: Collapses stereo width
Impact: Loses stereo information, phase issues
```

**Fix:** Only convert truly mono sources (kick, bass, mono synths)

---

### ❌ Mistake #6: Wrong Render Range

**Problem:**
```
Render Start: 1.1.1
Render Length: 4.0.0
Song actually: 192 bars long
Result: Only exports 4 bars!
```

**Fix:** Check your render length matches your song!

---

## Troubleshooting

### Problem: "Export is Silent"

**Possible causes:**
1. Track is muted
2. Render range is wrong (exporting empty space)
3. Solo is enabled on other tracks

**Fix:**
- Unsolo all tracks
- Unmute all tracks
- Check render start/length

---

### Problem: "Files Are Too Large"

**Current export:** 24-bit stereo WAV for 40 tracks

**Solutions (in order of preference):**
1. **Reduce bit depth:** 24-bit → 16-bit (33% smaller)
2. **Convert mono tracks:** Enable "Convert to Mono" for kick/bass/etc (50% smaller each)
3. **Export groups:** Combine tracks into 6-8 stems instead of 40
4. **Use FLAC:** Convert WAV to FLAC after export (40-50% smaller)
5. **Shorter export:** Export only 1 minute for testing

---

### Problem: "Exported File Sounds Different"

**Possible causes:**
1. Master effects are included
2. Return effects are included
3. Automation is changing things
4. External plugins not rendering correctly

**Fix:**
- Turn off "Include Return and Master Effects"
- Freeze tracks with external plugins first
- Check automation lanes

---

### Problem: "Getting Clipping in Export"

**If your mix sounds fine in Ableton but export clips:**

1. **Check master fader:** Should be at 0dB or lower
2. **Check peak level:** Use utility plugin to monitor
3. **Check for automation:** Master fader automation might cause clipping
4. **Disable normalize:** Can cause clipping

**Fix:**
- Lower master fader by 6dB
- Re-export

---

### Problem: "Stems Don't Line Up"

**All stems should start at the same time and be the same length.**

**If they don't:**
1. **Render Start is different:** Always use same start point
2. **Render Length is different:** Always use same length
3. **Clips have delays:** Disable any external delay plugins

**Best practice:**
- Always render from bar 1 (or wherever first sound occurs)
- Always render entire song length
- All stems will perfectly align

---

## Workflow Checklist

### Before Exporting:

- [ ] Save your project
- [ ] Name all tracks clearly
- [ ] Check track isn't muted/soloed unintentionally
- [ ] Set loop brace to full song length (Cmd/Ctrl + L)
- [ ] Check master peak level (-6dB to -3dB for mastering)
- [ ] Disable limiter on master (for mastering export)

### During Export:

- [ ] Rendered Track: Set appropriately (Master vs All Tracks)
- [ ] Include Effects: OFF
- [ ] Normalize: OFF
- [ ] Convert to Mono: Only for true mono sources
- [ ] Bit Depth: 16 or 24-bit
- [ ] File Type: WAV
- [ ] Sample Rate: 44100 Hz (or project rate)
- [ ] Dither: Triangular (if 16-bit)

### After Export:

- [ ] Listen to export (does it sound correct?)
- [ ] Check file size (reasonable?)
- [ ] Verify all files are present (for stem export)
- [ ] Check peak levels (for mastering: -6dB to -3dB)
- [ ] Organize files in folders

---

## Quick Export Templates

Save these as reference:

### Template 1: "Final Mix for Mastering"
```
Rendered Track: Master
Include Effects: OFF
Normalize: OFF
Convert to Mono: OFF
Bit Depth: 24-bit
File Type: WAV
Sample Rate: 44100 Hz
Target peak: -6dB
```

### Template 2: "All Stems for Analysis"
```
Rendered Track: All Individual Tracks
Include Effects: OFF
Normalize: OFF
Convert to Mono: (selective - see guide)
Bit Depth: 16-bit
File Type: WAV
Sample Rate: 44100 Hz
```

### Template 3: "Grouped Stems (Smaller)"
```
[Create groups first: Drums, Bass, Keys, Vocals, FX]
Rendered Track: All Individual Tracks
Include Effects: OFF
Normalize: OFF
Convert to Mono: OFF
Bit Depth: 16-bit
File Type: WAV
Sample Rate: 44100 Hz
```

### Template 4: "Test Export (Quick)"
```
Rendered Track: Master
Include Effects: OFF
Normalize: OFF
Render Length: 32.0.0 (32 bars only)
Bit Depth: 16-bit
File Type: WAV
Sample Rate: 44100 Hz
```

---

## Pro Tips

### Tip 1: Create Export Presets in Ableton

You can't officially save presets, but you can:
1. Set up your export settings
2. Take a screenshot
3. Reference it each time

### Tip 2: Batch Export Strategy

If exporting stems regularly:
1. Create a template project with all tracks named
2. Import audio/MIDI into template
3. Export using same settings every time
4. Consistent workflow every time!

### Tip 3: Use Project Folders

Organize exports:
```
My Song/
├── my_song.als
├── exports/
│   ├── mix_v1.wav
│   ├── mix_v2.wav
│   └── stems/
│       ├── kick.wav
│       ├── bass.wav
│       └── ...
└── references/
    └── professional_track.wav
```

### Tip 4: Leave Headroom

**For final mixes going to mastering:**
- Target: -6dB peak (safest)
- Acceptable: -3dB peak (still okay)
- Too hot: -1dB peak (risky)
- Clipping: 0dB peak (bad!)

**How to check:** Add Utility plugin on master, watch "Out" meter

### Tip 5: Test Your Export

Before exporting 40 stems:
1. Export just 2-3 test stems
2. Load them in analysis tool
3. Verify they work correctly
4. Then export everything

---

## Summary

**For most users, use this:**

### Mastering Export:
```
Master channel only
24-bit or 16-bit WAV
Effects OFF, Normalize OFF
Peak at -6dB
```

### Stem Analysis Export:
```
All individual tracks (or groups)
16-bit WAV
Effects OFF, Normalize OFF
Convert to Mono: Only for mono sources
```

**That's it! Keep it simple, and you'll get great results.**

---

**Good luck with your analysis! 🎵**

*Last updated: January 2026*
