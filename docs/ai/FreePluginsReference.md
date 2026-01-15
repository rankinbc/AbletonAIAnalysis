# Free Audio Plugins Reference Guide
## For AI-Assisted Music Production in Ableton 11

This document catalogs free plugins that can enhance your mixing workflow. The AI can reference this when making recommendations.

---

## Quick Reference

### Essential (Highly Recommended)
1. **Youlean Loudness Meter** - LUFS measurement
2. **SPAN** - Frequency spectrum analyzer

### Highly Recommended (Processing)
3. **TDR Nova** - Dynamic EQ
4. **TDR Kotelnikov** - Transparent compressor

### Nice to Have
5. **MeldaProduction Free Bundle** - 15+ analysis/processing tools
6. **Voxengo OldSkoolVerb** - Reverb
7. **TAL-Reverb-4** - Reverb alternative

---

## TIER 1: ESSENTIAL ANALYSIS TOOLS

### 1. Youlean Loudness Meter 2

**Category:** Loudness Analysis  
**Cost:** FREE  
**Platform:** Windows, Mac (VST, VST3, AU, AAX)  
**Download:** https://youlean.co/youlean-loudness-meter/

#### What It Does
Measures loudness in LUFS (Loudness Units relative to Full Scale) - the industry standard for streaming platforms.

#### Why It's Essential
- Ableton doesn't have built-in LUFS metering
- Python libraries can estimate LUFS, but this shows real-time measurements
- Streaming platforms (Spotify, Apple Music, YouTube) normalize to specific LUFS targets
- Helps you hit professional loudness targets

#### Key Features (Free Version)
- Real-time LUFS measurement
- Integrated LUFS (overall loudness)
- Short-term LUFS (moment-to-moment)
- True Peak detection
- Dynamic range display
- Loudness history graph
- Presets for streaming platforms (Spotify: -14 LUFS, YouTube: -14 LUFS, etc.)

#### When AI Should Recommend
```
Scenario 1: Loudness comparison
"Your mix is -20 LUFS, reference is -14 LUFS. 
Install Youlean Loudness Meter to monitor LUFS as you adjust levels."

Scenario 2: Mastering prep
"Before mastering, check your integrated LUFS with Youlean Loudness Meter.
Target -14 LUFS for streaming platforms."

Scenario 3: Dynamic range check
"Your dynamic range is 6dB (possibly over-compressed).
Youlean can show this in real-time."
```

#### How to Use in Ableton
1. Drag onto Master track
2. Play entire song (or use "Loop" mode in plugin)
3. Check "Integrated" LUFS value
4. Compare to streaming platform targets

#### Target Values
- **Spotify:** -14 LUFS
- **Apple Music:** -16 LUFS  
- **YouTube:** -14 LUFS
- **Club/DJ:** -8 to -10 LUFS
- **Broadcast:** -23 LUFS (TV/Radio)

#### Notes
- Free version is fully functional
- Pro version ($99) adds more features (not needed for most users)
- Works with any DAW, not just Ableton

---

### 2. SPAN (Voxengo)

**Category:** Frequency Spectrum Analyzer  
**Cost:** FREE  
**Platform:** Windows, Mac (VST, AU)  
**Download:** https://www.voxengo.com/product/span/

#### What It Does
Real-time frequency spectrum analyzer - shows which frequencies are present in your audio.

#### Why It's Useful
- Visual confirmation of AI analysis
- See frequency buildup in real-time
- Monitor stereo correlation
- Educational - helps you understand frequency content

#### Key Features
- Real-time FFT spectrum display
- Multiple time averaging modes
- Peak hold display
- Correlation meter (stereo width)
- Multiple presets for different analysis types
- Adjustable frequency scale (linear, logarithmic)

#### When AI Should Recommend
```
Scenario 1: Visual learning
"I detected a peak at 87Hz on the bass. If you'd like to see 
this visually, load SPAN on the bass track and look for the 
spike around 80-90Hz."

Scenario 2: Frequency comparison
"Load SPAN on your mix, then on the reference track. 
Compare the overall frequency curves to see where they differ."

Scenario 3: Stereo width check
"SPAN's correlation meter shows stereo width. 
Check if it matches my analysis (0.89 correlation = narrow)."
```

#### How to Use in Ableton
1. Drag onto any track (usually Master for full mix)
2. Play audio
3. Watch frequency spectrum in real-time
4. Look for:
   - **Peaks** - Problem frequencies
   - **Dips** - Missing frequencies
   - **Overall curve** - Tonal balance

#### Reading SPAN
- **X-axis:** Frequency (20Hz - 20kHz)
- **Y-axis:** Level (dB)
- **Green line:** Current spectrum
- **Yellow/red:** Peak hold
- **Correlation meter (bottom right):** Stereo width
  - 1.0 = Mono
  - 0.7-0.9 = Narrow
  - 0.3-0.6 = Good width
  - < 0.3 = Very wide (possible phase issues)

#### Notes
- Educational tool, not required for workflow
- AI can do everything SPAN does programmatically
- Great for visual learners

---

## TIER 2: HIGHLY RECOMMENDED PROCESSING

### 3. TDR Nova (Tokyo Dawn Records)

**Category:** Dynamic EQ / Parallel Dynamic EQ  
**Cost:** FREE (GE version), Paid ($49 for full features)  
**Platform:** Windows, Mac (VST, VST3, AU, AAX)  
**Download:** https://www.tokyodawn.net/tdr-nova/

#### What It Does
Dynamic EQ - cuts or boosts frequencies ONLY when they exceed a threshold. More surgical than static EQ.

#### Why It's Better Than Stock
Ableton's EQ Eight is static (always cutting/boosting). TDR Nova is dynamic (only acts when needed).

**Example:**
- Static EQ: "Always cut bass at 80Hz by -3dB"
- Dynamic EQ: "Cut bass at 80Hz by -3dB, but ONLY when it gets louder than -10dB"

#### Key Features (Free GE Version)
- 4 dynamic EQ bands
- Adjustable threshold per band
- Attack/release controls
- Solo functionality (hear what's being affected)
- Linear-phase option (prevents phase issues)
- Parallel processing

#### When AI Should Recommend
```
Scenario 1: Occasional problems
"Bass is fine most of the time, but peaks at 80Hz during loud sections.
Use TDR Nova for dynamic cut at 80Hz (only when bass is loud)."

Scenario 2: Taming resonances
"Vocal has harsh resonance at 3.2kHz during loud notes.
TDR Nova can tame this without dulling quiet sections."

Scenario 3: Multiband compression alternative
"Instead of Ableton's Multiband Dynamics, try TDR Nova for 
more precise frequency-specific compression."
```

#### How to Use in Ableton
1. Add to track where frequency issue occurs
2. Enable a band (1-4)
3. Set frequency (e.g., 80Hz)
4. Set gain (e.g., -3dB)
5. Set threshold (only cuts when signal exceeds this)
6. Adjust attack/release
7. Use "Delta" mode to hear what's being affected

#### Common Settings
```
Bass/Kick clash fix:
- Frequency: 80Hz
- Gain: -3dB
- Threshold: -10dB
- Attack: 10ms
- Release: 100ms
- Q: 1.5

Vocal de-essing:
- Frequency: 6-8kHz
- Gain: -4dB  
- Threshold: -15dB
- Attack: 1ms
- Release: 50ms
- Q: 2.0
```

#### Notes
- Free version (GE) is excellent, full version adds more bands and features
- More advanced than stock Ableton tools
- Steeper learning curve than static EQ

---

### 4. TDR Kotelnikov (Tokyo Dawn Records)

**Category:** Compressor (Mastering-grade)  
**Cost:** FREE (GE version), Paid ($49 for full features)  
**Platform:** Windows, Mac (VST, VST3, AU, AAX)  
**Download:** https://www.tokyodawn.net/tdr-kotelnikov/

#### What It Does
Extremely transparent compressor designed for mastering and mix bus compression.

#### Why It's Better Than Stock
- More transparent than Ableton Compressor
- Better for gentle, "glue" compression
- Mastering-grade quality
- Delta Solo mode (hear what's being compressed)

#### Key Features (Free GE Version)
- Peak and RMS detection
- Multiple knee settings
- Mix knob (parallel compression)
- Delta Solo (hear compressed signal)
- Stereo and dual-mono modes
- Look-ahead
- Auto-release

#### When AI Should Recommend
```
Scenario 1: Mix bus compression
"Add gentle glue compression to mix bus using TDR Kotelnikov:
- Threshold: -18dB, Ratio: 2:1, Attack: 30ms, Release: auto
- Use Delta Solo to hear what's being compressed."

Scenario 2: Transparent mastering compression
"For final mastering compression, TDR Kotelnikov is more 
transparent than Ableton's Limiter."

Scenario 3: Parallel compression
"Use Kotelnikov's mix knob for parallel compression
(compress hard, blend back with dry signal)."
```

#### How to Use in Ableton
1. Add to mix bus or master
2. Set threshold (start at -18dB)
3. Set ratio (2:1 for gentle, 4:1 for more)
4. Set attack (10-30ms for mix bus)
5. Set release (auto or 100-300ms)
6. Use Delta Solo to hear compressed signal
7. Adjust to taste

#### Common Settings
```
Mix bus glue:
- Threshold: -18dB
- Ratio: 2:1
- Attack: 30ms
- Release: Auto
- Knee: Medium
- Gain reduction: 2-3dB

Mastering compression:
- Threshold: -12dB
- Ratio: 1.5:1
- Attack: 10ms
- Release: Auto
- Knee: Soft
- Gain reduction: 1-2dB
```

#### Notes
- Free version is excellent for most uses
- Full version adds more features (not necessary for beginners)
- Great learning tool - Delta Solo shows what compression does

---

## TIER 3: NICE TO HAVE

### 5. MeldaProduction Free Bundle

**Category:** Various (15+ plugins)  
**Cost:** FREE  
**Platform:** Windows, Mac (VST, VST3, AU, AAX)  
**Download:** https://www.meldaproduction.com/MFreeFXBundle

#### What's Included

**Analysis:**
- **MAnalyzer** - Spectrum analyzer (alternative to SPAN)
- **MStereoScope** - Stereo width visualization
- **MLoudnessAnalyzer** - Loudness analysis

**Processing:**
- **MAutoPitch** - Pitch correction
- **MCompressor** - Compressor
- **MEqualizer** - 6-band parametric EQ
- **MLimiter** - Limiter
- **MReverb** - Reverb
- **MMultiBandSaturator** - Saturation
- **Plus many more** (15 total)

#### When AI Should Recommend
```
Scenario: Alternative analysis tools
"If you want an alternative to SPAN, try MAnalyzer from Melda's free bundle.
For stereo visualization, use MStereoScope."

Scenario: Pitch correction
"Vocal slightly off-pitch at 1:23. If you have MAutoPitch 
from Melda's free bundle, use it for subtle correction."
```

#### Notes
- Large bundle, lots of options
- Interface is consistent across all plugins
- Can be overwhelming for beginners
- Not essential - stick with stock Ableton plugins first

---

### 6. Voxengo OldSkoolVerb

**Category:** Reverb  
**Cost:** FREE  
**Platform:** Windows, Mac (VST, AU)  
**Download:** https://www.voxengo.com/product/oldskoolverb/

#### What It Does
Algorithmic reverb with classic sound.

#### Why Include It
Ableton's stock Reverb is good, but OldSkoolVerb offers different character.

#### When AI Should Recommend
```
Only if user asks about reverb alternatives:
"Ableton's Reverb is great, but if you want a different character,
try Voxengo OldSkoolVerb (free)."
```

#### Notes
- Not essential - Ableton's Reverb is good
- Include for completeness

---

### 7. TAL-Reverb-4

**Category:** Reverb  
**Cost:** FREE  
**Platform:** Windows, Mac (VST, AU)  
**Download:** https://tal-software.com/products/tal-reverb-4

#### What It Does
Vintage-style plate reverb with modern features.

#### Why Include It
Another reverb alternative with different character than Ableton stock.

#### When AI Should Recommend
```
"For vintage plate reverb sound, try TAL-Reverb-4 (free).
Ableton's Reverb is more versatile for general use."
```

#### Notes
- Not essential
- Nice character for specific sounds

---

## TIER 4: WHAT NOT TO RECOMMEND

### Plugins AI Should NOT Suggest (Paid)

**REFERENCE by Mastering The Mix** (~$99)
- Great for A/B comparison, but can do manually in Ableton
- Not necessary for workflow

**LEVELS by Mastering The Mix** (~$99)
- Does what AI already does programmatically
- Redundant

**FabFilter Plugins** (Pro-Q 3, Pro-C 2, etc.) (~$150+ each)
- Excellent but expensive
- Ableton stock + free plugins are sufficient

**Waves Plugins** (Various, $30-300)
- Not necessary for beginners
- Only suggest if user specifically asks

**iZotope Ozone/Neutron** ($200-500)
- We're using Matchering for mastering (free)
- Expensive for hobbyists

---

## Plugin Installation Guide

### Windows Installation
1. Download plugin installer
2. Run installer
3. Choose VST3 or VST2 folder (usually `C:\Program Files\VSTPlugins\`)
4. Restart Ableton
5. Plugins appear in Ableton's browser under "Plug-ins"

### Mac Installation
1. Download plugin installer (usually .dmg or .pkg)
2. Run installer
3. Plugins install to:
   - AU: `/Library/Audio/Plug-Ins/Components/`
   - VST: `/Library/Audio/Plug-Ins/VST/`
   - VST3: `/Library/Audio/Plug-Ins/VST3/`
4. Restart Ableton
5. Plugins appear in Ableton's browser under "Plug-ins"

### Ableton Plugin Folders Setup
1. Open Ableton Preferences
2. Go to "Plug-Ins" tab
3. Enable "Use VST3 Plug-In System Folders" (recommended)
4. Enable "Use Audio Units" (Mac only)
5. Add custom folders if needed
6. Click "Rescan"

---

## When AI Should Recommend Plugins

### Stock Plugins FIRST (Always Available)

```
Priority 1: Ableton stock plugins
"Add EQ Eight to bass track, cut 80Hz by -3dB, Q=1.5"

Why: User definitely has these, no installation needed
```

### Free Plugins SECOND (When Beneficial)

```
Priority 2: Free plugins when they offer clear advantage
"For dynamic EQ (cuts only when needed), install TDR Nova (free).
Or use static EQ with EQ Eight if you prefer simplicity."

Why: Acknowledges advantage, but offers stock alternative
```

### Paid Plugins NEVER (Unless User Asks)

```
Priority 3: Only mention paid plugins if user specifically asks
User: "What's the best EQ plugin?"
AI: "FabFilter Pro-Q 3 is industry standard, but expensive ($180).
Ableton's EQ Eight + free TDR Nova cover 95% of needs."

Why: Don't recommend expensive plugins to hobbyists
```

---

## AI Recommendation Templates

### Template 1: Analysis Tool

```
"To accurately measure LUFS, I recommend installing 
Youlean Loudness Meter (free):
https://youlean.co/youlean-loudness-meter/

This will help you monitor loudness in real-time as you mix.
Target -14 LUFS for Spotify/streaming platforms."
```

### Template 2: Processing Upgrade

```
"To fix this bass/kick clash, add EQ Eight to bass:
- Cut 80Hz by -3dB, Q=1.5

Note: This is a dynamic problem (only happens during loud sections).
If you have TDR Nova (free), you can make this cut dynamic:
- Cut 80Hz by -3dB, but only when bass exceeds -10dB

TDR Nova download: https://www.tokyodawn.net/tdr-nova/

Static EQ will work fine if you don't want to install anything!"
```

### Template 3: Visual Learning

```
"I detected a frequency buildup at 200Hz. If you'd like to see 
this visually, load SPAN (free) on the track:
https://www.voxengo.com/product/span/

Look for the peak/hump around 200Hz. This is educational - 
not required for the workflow!"
```

### Template 4: Don't Recommend

```
User: "My mix sounds bad, what plugin do I need?"
AI: "The issue isn't plugins - it's mixing technique.

Problems detected:
1. Bass/kick clash at 80Hz → Fix with EQ Eight (you have this)
2. Mix too narrow → Fix with Utility width control (you have this)
3. Clipping on master → Lower master fader (no plugin needed)

Ableton's stock plugins are excellent. Let's fix these issues first!"
```

---

## Summary

### Essential Downloads (Do These First)
1. ✅ **Youlean Loudness Meter** - LUFS measurement
2. ✅ **SPAN** - Frequency visualization

**Total cost: $0**

### Highly Recommended (When You Want More Control)
3. **TDR Nova** - Dynamic EQ
4. **TDR Kotelnikov** - Transparent compression

**Total cost: $0**

### Nice to Have (Completeness)
5. **MeldaProduction Free Bundle** - Various tools
6. **Voxengo OldSkoolVerb** - Reverb alternative
7. **TAL-Reverb-4** - Reverb alternative

**Total cost: $0**

---

## Key Principles for AI

1. **Stock plugins first** - User already has excellent tools
2. **Free plugins when beneficial** - Clear advantage over stock
3. **Explain the WHY** - Why this plugin helps this specific problem
4. **Always offer stock alternative** - Don't force plugin installation
5. **Never recommend paid** - Unless user specifically asks
6. **Installation is optional** - Workflow should work without any downloads

---

## Quick Decision Tree

```
Does user need to measure LUFS?
├─ YES → Recommend Youlean Loudness Meter
└─ NO → Continue

Is it a frequency problem?
├─ Static (always present) → Use EQ Eight (stock)
└─ Dynamic (only sometimes) → Mention TDR Nova option

Is it a compression problem?
├─ Heavy/obvious → Use Compressor (stock)
└─ Subtle/transparent → Mention TDR Kotelnikov option

Does user want visual confirmation?
├─ YES → Mention SPAN for learning
└─ NO → Continue (not needed)
```

---

**Remember: Ableton 11 stock plugins are professional-grade. Free plugins enhance, but aren't required!**

---

*Last updated: January 2026*
