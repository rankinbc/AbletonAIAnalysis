# Ableton Generator Template Requirements

This document specifies everything a template `.als` file must contain for the AI Song Generator to produce valid, playable Ableton projects.

---

## Overview

The generator:
1. Copies tracks from the template
2. Renames them based on song spec
3. Embeds MIDI clips into the arrangement
4. Adds section markers (locators)
5. Sets tempo
6. Updates IDs to avoid conflicts

**The template is the foundation - if it's broken, all generated projects will be broken.**

---

## Required XML Structure

### Root Element
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Ableton MajorVersion="5" MinorVersion="11.0_..." ...>
  <LiveSet>
    ...
  </LiveSet>
</Ableton>
```

### LiveSet Required Children
```xml
<LiveSet>
  <NextPointeeId Value="[number higher than all IDs]"/>
  <Tracks>
    <!-- MIDI and Audio tracks here -->
  </Tracks>
  <MasterTrack>
    <!-- Master track configuration -->
  </MasterTrack>
  <Locators>
    <Locators>
      <!-- Section markers go here (generator clears and recreates) -->
    </Locators>
  </Locators>
</LiveSet>
```

---

## Track Requirements

### Minimum Tracks Needed

The generator expects these MIDI tracks (by name, case-insensitive):

| Track Name | Purpose | Required |
|------------|---------|----------|
| `Kick` | Kick drum | Yes |
| `Bass` | Bass line | Yes |
| `Chords` | Chord stabs/pads | Yes |
| `Arp` | Arpeggios | Yes |
| `Lead` | Melody/lead | Yes |
| `Hats` | Hi-hats | Yes |
| `Clap` | Clap/snare | Yes |
| `FX` | Risers, crashes, transitions | Yes |
| `Riser` | Texture: risers | Optional |
| `Impact` | Texture: impacts | Optional |
| `Atmosphere` | Texture: pads/atmosphere | Optional |

**Recommended: 11 MIDI tracks** (8 core + 3 texture)

### Track XML Structure

Each MIDI track MUST have this structure for clip embedding to work:

```xml
<MidiTrack Id="[unique_id]">
  <LomId Value="0"/>

  <!-- Track name (generator updates these) -->
  <Name>
    <EffectiveName Value="Kick"/>
    <UserName Value="Kick"/>
    <!-- other name elements -->
  </Name>

  <!-- Track color (generator updates) -->
  <Color Value="0"/>

  <!-- THIS PATH IS CRITICAL FOR CLIP EMBEDDING -->
  <DeviceChain>
    <MainSequencer>
      <ClipTimeable>
        <ArrangerAutomation>
          <Events>
            <!-- MIDI clips go here -->
          </Events>
        </ArrangerAutomation>
      </ClipTimeable>
      <!-- other MainSequencer elements -->
    </MainSequencer>
    <!-- devices, mixer, etc. -->
  </DeviceChain>
</MidiTrack>
```

**CRITICAL PATH**: `MidiTrack → DeviceChain → MainSequencer → ClipTimeable → ArrangerAutomation → Events`

If this path is missing or malformed, clip embedding will silently fail.

---

## Send/Return Track Configuration

### The Problem
Ableton projects can have sends (Send A, Send B, etc.) that route to Return tracks. If a track has 2 send knobs but there's only 1 return track, **Ableton will refuse to load the file**.

### The Solution
**EITHER:**
1. Have NO sends and NO return tracks (simplest)
2. Have matching sends and returns (e.g., 2 sends = 2 return tracks)

### Recommended Approach
For a generator template, use **Option 2** with standard returns:
- **Return A**: Reverb (for leads, pads, atmosphere)
- **Return B**: Delay (for rhythmic elements)

### Return Track Structure
```xml
<ReturnTrack Id="[id]">
  <LomId Value="0"/>
  <Name>
    <EffectiveName Value="A-Reverb"/>
    <UserName Value=""/>
  </Name>
  <DeviceChain>
    <!-- Reverb device here -->
    <Mixer>
      <Sends>
        <!-- Return tracks also have sends (for send-to-send routing) -->
      </Sends>
    </Mixer>
  </DeviceChain>
</ReturnTrack>
```

### Send Configuration on MIDI Tracks
Each MIDI track's `Mixer → Sends` must have entries matching return tracks:
```xml
<Mixer>
  <Sends>
    <TrackSendHolder Id="[id]">
      <Send>
        <Manual Value="0.0"/>  <!-- Send level: 0.0 = -inf, 1.0 = 0dB -->
        <!-- automation elements -->
      </Send>
      <Active Value="true"/>
    </TrackSendHolder>
    <!-- One TrackSendHolder per Return track -->
  </Sends>
</Mixer>
```

---

## ID Management

### Rules
1. Every element with an `Id` attribute must have a **unique** value
2. `NextPointeeId` in `<LiveSet>` must be **greater than** all used IDs
3. `Pointee` and `PointeeId` elements reference other IDs - these must be valid

### What the Generator Does
- Analyzes existing IDs
- Generates new IDs starting from `max(all_ids) + 1`
- Updates `NextPointeeId` after modifications

### Template Requirement
- Start with clean, sequential IDs
- `NextPointeeId` should be set correctly
- No orphaned `Pointee` references

---

## Tempo Configuration

The generator sets tempo via:
```xml
<MasterTrack>
  <...>
  <DeviceChain>
    <Mixer>
      <Tempo>
        <Manual Value="138.0"/>  <!-- Generator updates this -->
      </Tempo>
    </Mixer>
  </DeviceChain>
</MasterTrack>
```

**Template must have**: `MasterTrack → DeviceChain → Mixer → Tempo → Manual`

---

## MIDI Clip Structure (For Reference)

The generator creates clips with this structure. Template doesn't need clips, but understanding helps debugging:

```xml
<MidiClip Id="[id]" Time="0">
  <LomId Value="0"/>
  <LomIdView Value="0"/>
  <WarpMarkers>
    <WarpMarker Id="[id]" SecTime="0" BeatTime="0"/>
  </WarpMarkers>
  <CurrentStart Value="0"/>
  <CurrentEnd Value="128"/>  <!-- 32 bars = 128 beats -->
  <Loop>
    <LoopStart Value="0"/>
    <LoopEnd Value="128"/>
    <LoopOn Value="true"/>
    <!-- other loop settings -->
  </Loop>
  <Name Value="Kick - Intro"/>
  <ColorIndex Value="0"/>
  <TimeSignature>
    <TimeSignatures>
      <RemoteableTimeSignature Id="[id]">
        <Numerator Value="4"/>
        <Denominator Value="4"/>
        <Time Value="0"/>
      </RemoteableTimeSignature>
    </TimeSignatures>
  </TimeSignature>
  <Envelopes><Envelopes/></Envelopes>
  <Notes>
    <KeyTracks>
      <KeyTrack Id="[id]">
        <Notes>
          <MidiNoteEvent Time="0" Duration="0.5" Velocity="100" OffVelocity="64" IsEnabled="true"/>
          <!-- more notes -->
        </Notes>
        <MidiKey Value="36"/>  <!-- MIDI note number -->
      </KeyTrack>
      <!-- more KeyTracks for different pitches -->
    </KeyTracks>
  </Notes>
  <!-- many other required elements -->
</MidiClip>
```

---

## What the Template Should NOT Have

1. **Existing MIDI clips** - Generator clears and recreates
2. **Broken send/return configuration** - Causes load failure
3. **Duplicate IDs** - Causes unpredictable behavior
4. **Missing `Value` attributes** - Causes "Required attribute 'Value' missing" error
5. **Orphaned Pointee references** - IDs that point to non-existent elements

---

## Validation Checklist

Run this to validate a template:

```bash
cd C:\claude-workspace\AbletonAIAnalysis\projects\ableton-generators
python xml_utils.py "path/to/template.als" --analyze -v
```

Expected output for valid template:
```
=== ID Analysis: template.als ===
Total IDs: ~500-1000
Max numeric ID: [number]
NextPointeeId: [higher than max]
Referenced IDs: [number]
Duplicates: 0

[OK] Live Set is valid
```

---

## Creating a Valid Template

### Method 1: From Scratch in Ableton (Recommended)

1. Open Ableton Live
2. Create a new empty project
3. Add 11 MIDI tracks, name them:
   - Kick, Bass, Chords, Arp, Lead, Hats, Clap, FX, Riser, Impact, Atmosphere
4. Add 2 Return tracks:
   - A-Reverb (add a Reverb device)
   - B-Delay (add a Delay device)
5. Set tempo to 138 BPM (default)
6. **Delete any clips** (tracks should be empty)
7. Save as "Generator_Template.als"
8. Validate with `xml_utils.py`

### Method 2: Fix Existing Template

1. Load in Ableton (if it loads)
2. Check View → Returns to see return tracks
3. Ensure # of sends on each track = # of return tracks
4. Re-save
5. Validate

---

## Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| "Track has more send knobs than set has return tracks" | Send/return mismatch | Add return tracks or remove sends |
| "Required attribute 'Value' missing" | Malformed XML element | Find element at line/column, add Value attribute |
| "is corrupt and cannot be loaded" | Generic XML error | Validate with xml_utils.py, check IDs |
| Clips don't appear | Wrong path in MidiTrack | Ensure DeviceChain→MainSequencer→ClipTimeable→ArrangerAutomation→Events exists |
| Wrong track names | Generator can't find tracks | Ensure EffectiveName and UserName are set |

---

## Generator Files That Touch Template

| File | What It Does |
|------|--------------|
| `ableton_project.py` | Main orchestrator, copies tracks, sets tempo, adds locators |
| `clip_embedder.py` | Embeds MIDI clips into track Events |
| `xml_utils.py` | ID analysis, validation, safe ID generation |

---

## Summary: Minimal Valid Template

A working template needs:
1. `Ableton` root → `LiveSet`
2. `NextPointeeId` set correctly
3. `Tracks` with 8-11 named MIDI tracks
4. Each MIDI track with full `DeviceChain→MainSequencer→ClipTimeable→ArrangerAutomation→Events` path
5. Matching Return tracks for any sends configured
6. `MasterTrack` with tempo configuration
7. `Locators` container (can be empty)
8. No duplicate IDs, no orphaned references

**Test**: After creating template, run the generator. If project loads in Ableton, template is valid.
