# AI-Assisted Music Production Workflow
## The Iterative Improvement Process

A practical guide for using AI analysis to improve your mixes through systematic iteration.

---

## Table of Contents
- [Core Workflow](#core-workflow)
- [Phase 1: First Analysis](#phase-1-first-analysis)
- [Phase 2: Making Improvements](#phase-2-making-improvements)
- [Phase 3: Re-Analysis & Iteration](#phase-3-re-analysis--iteration)
- [Phase 4: Final Mastering](#phase-4-final-mastering)
- [Advanced Strategies](#advanced-strategies)
- [Common Scenarios](#common-scenarios)

---

## Core Workflow

### The Process

```
1. Export mix from Ableton → 2. Analyze → 3. Fix 1-3 issues → 
4. Export again → 5. Compare → Repeat until satisfied → 6. Master
```

### Key Principles

1. **Fix iteratively, not all at once**
   - Address 1-3 issues per iteration
   - Re-analyze after each change
   - Prevents making things worse

2. **Trust your ears, then verify with AI**
   - Make change → listen → sounds better? → confirm with analysis
   - If AI says "better" but sounds worse → trust your ears

3. **Prioritize ruthlessly**
   - Critical: Clipping, major frequency clashes, bad balance
   - Important: Stereo width, brightness, dynamics
   - Polish: Minor frequency tweaks, fine-tuning

4. **Save versions**
   - mix_v1, mix_v2, mix_v3, etc.
   - Allows comparison and rollback

---

## Phase 1: First Analysis

### Prepare Reference Tracks

**Find 2-3 professional tracks in your genre:**
- Well-produced, similar style to yours
- WAV/FLAC preferred, 320kbps MP3 minimum
- These guide AI mastering and comparisons
### Export Initial Mix

**From Ableton (see Export Guide for details):**
- Master track only
- Include Effects: OFF
- Normalize: OFF
- 16 or 24-bit WAV
- Peak: -6dB (lower master fader if needed)

**Also export stems (optional but helpful):**
- All Individual Tracks
- Same settings as above

---

### Run First Analysis

**Request from AI:**
- Analyze mix for clipping, frequency balance, dynamics, stereo width
- If stems provided: find frequency clashes between stems
- Compare to reference track
- Provide specific, actionable recommendations ranked by priority

---

### Review the Report & Prioritize

**Example issues you might see:**

```
🔴 CRITICAL (fix first):
1. Clipping detected at 0:45, 1:23, 2:34
2. Bass and Kick major clash at 60-100Hz

🟡 IMPORTANT (fix next):
3. Mix is narrow (stereo correlation: 0.89)
4. Too dark (lacking high frequencies)

ℹ️ POLISH (fix last):
5. Snare and vocals slight clash at 200-400Hz
6. Minor dynamic inconsistencies
```

**Create your fix list:**

```
Iteration 1: Fix clipping + bass/kick clash
Iteration 2: Add stereo width + brighten
Iteration 3: Address snare/vocal clash
```

**Strategy:** Fix 1-3 issues per iteration, starting with critical.

---

## Phase 2: Making Improvements

### Focus on Top Issues Only

Open Ableton and address your top 1-3 issues. Don't try to fix everything at once.

---

### Example: Fixing Clipping

**Problem:** "Clipping at 0:45, 1:23, 2:34 on bass notes"

**Solution options:**
1. Lower bass track by 3dB
2. Lower master fader by 3dB
3. Use compressor on bass to control peaks

**Process:**
- Apply fix
- Play through problem sections
- Verify no more clipping
- Listen to full mix for overall balance

---

### Example: Fixing Bass/Kick Frequency Clash

**Problem:** "Bass and Kick clash at 60-100Hz"

**Solution (EQ the bass):**
1. Add EQ to bass track
2. Create bell cut at 80Hz
3. Q: 1.5, Gain: -3dB to -4dB
4. Sweep between 60-100Hz to find worst spot
5. A/B toggle EQ on/off to compare

**Result:** Clearer low end, kick punches through

---

### Document Your Changes

Keep notes on what you changed:
```
Iteration 1:
- Lowered bass 3dB (fixed clipping)
- EQ cut on bass at 80Hz, -3.5dB (fixed clash)
- Result: Clean low end, no clipping
```

---

## Phase 3: Re-Analysis & Iteration

### Export New Version

Export with same settings as before, increment version number (v2, v3, etc.)

---

### Request Comparison Analysis

**Ask AI to:**
- Compare new version to previous version
- Confirm fixes worked
- Check if anything got worse
- Identify next priorities

---

### Example Comparison Report

```
✅ IMPROVEMENTS:
- Clipping FIXED (was 3 instances, now 0)
- Bass/kick clash IMPROVED (60-100Hz reduced 4dB)
- Low end clarity much better

⚠️ REMAINING:
- Still narrow stereo
- Still too dark

🆕 NEW ISSUES:
- None detected

VERDICT: Significant improvement!

NEXT PRIORITIES:
1. Add stereo width
2. Brighten high frequencies
```

---

### Decide Next Steps

**Three outcomes:**

1. **Issues fixed, nothing worse** → Move to next 1-3 issues
2. **Issues fixed, but something broke** → Adjust and re-export
3. **Issues not fixed** → Make more aggressive change, try again

---

### Keep Iterating

Repeat until you've addressed all critical and important issues.

**Typical iterations:** 3-5 for most mixes
**When to stop:** No critical issues, sounds good to your ears

---

## Phase 4: Final Mastering

### Prepare Final Mix

**Your mix should have:**
- ✅ No clipping
- ✅ Good frequency balance
- ✅ Clear low end
- ✅ Good stereo width
- ✅ Peak level at -6dB

**Export:**
- Master track
- Effects OFF (especially limiters!)
- 24-bit WAV recommended
- Peak: -6dB to -3dB

---

### AI Mastering

Use Matchering (or similar) to master against your reference track.

**What it does:**
- Matches loudness to reference
- Matches frequency response
- Matches stereo width
- Applies intelligent limiting

---

### Review Mastered Version

**Listen critically:**
1. Compare unmastered vs mastered
2. Compare mastered vs reference
3. Check for artifacts (distortion, over-compression)
4. Trust your ears

**If mastering sounds bad:**
- Try different reference track
- Check your unmastered mix (too quiet/loud?)
- Adjust mix before mastering again

---

## Advanced Strategies

### Strategy 1: The "Before/After Toggle"

Use Ableton's undo (Cmd/Ctrl + Z) to A/B compare:
- Make change
- Listen
- Undo to hear original
- Keep if better, undo if worse

**Don't rely only on AI - your ears decide.**

---

### Strategy 2: The "One Track at a Time" Approach

For complex mixes:
1. Fix drums only → analyze → iterate
2. Add bass → analyze → iterate
3. Add mids → analyze → iterate
4. Add vocals → analyze → iterate
5. Add FX → final polish

**Benefits:** Isolates problems, less overwhelming

---

### Strategy 3: Reference Matching

**Constantly A/B with reference:**
- Play your mix 30 seconds
- Play reference 30 seconds
- What's different?
- Make targeted change
- Re-analyze to confirm

---

### Strategy 4: The Checkpoint System

Save versions at key milestones:
```
mix_v1_initial.wav
mix_v2_clipping_fixed.wav
mix_v3_lowend_clear.wav
mix_v4_stereo_width.wav
mix_v5_final.wav
```

**Why:** Can compare any versions, roll back if needed, track progress

---

### Strategy 5: Focus Sessions

Dedicate each session to one aspect:
- **Session 1:** Low end only (bass, kick, sub)
- **Session 2:** Vocal clarity only
- **Session 3:** Stereo width only
- **Session 4:** Final balance

**Benefits:** Prevents decision fatigue, deeper focus

---

## Common Scenarios

### "AI Says Better But Sounds Worse"

**What to do:**
1. Trust your ears first - if it sounds bad, it IS bad
2. Check what AI actually measured
3. Dial back the change by 50%
4. Re-analyze to find sweet spot

**Lesson:** AI is a tool, not a dictator.

---

### "I Fixed One Thing, Three Things Broke"

**What to do:**
1. Roll back the change
2. Try different approach (e.g., EQ instead of volume)
3. Make smaller adjustments
4. Fix in isolation, then check full mix

---

### "Mix Never Sounds Good Enough"

**What to do:**
1. Take a break - ear fatigue is real
2. Compare to iteration 1 - is it much better?
3. Set realistic expectations - amateur ≠ pro
4. Ask AI for objective comparison to reference
5. Know when to stop - diminishing returns after 5-7 iterations

---

### "AI Keeps Finding New Issues"

**What to do:**
1. Distinguish critical vs minor issues
2. Ignore minor issues until later iterations
3. Ask AI: "Give me only top 3 issues"
4. Set goals per iteration:
   - Iterations 1-2: Critical only
   - Iterations 3-4: Important issues
   - Iterations 5+: Polish

**Lesson:** Not every issue needs immediate fixing.

---

### "Too Many Stems to Manage"

**What to do:**
1. Group stems before exporting (drums, bass, keys, vocals, FX)
2. Analyze selectively (low-freq stems first, then mids, then highs)
3. Focus analysis on tracks that might clash

---

## Timeline

**Typical project (3-4 min song):**

- First Analysis: 15 min
- Iteration 1: 30-45 min
- Iterations 2-4: 30-45 min each
- Final Master: 15 min

**Total: 3-4 hours** (spread over sessions)
**With practice: 2-3 hours**

---

## Key Takeaways

1. **Iterate, don't perfect**
   - Small improvements each time
   - Better than trying to fix everything at once

2. **AI assists, you decide**
   - Use AI as second opinion
   - Your ears have final say

3. **Prioritize ruthlessly**
   - Critical → Important → Polish
   - Stop when good enough

4. **Save versions**
   - Track progress
   - Allow rollback
   - Learn what works

5. **Stop at 5-7 iterations**
   - Diminishing returns after that
   - Good enough is good enough
   - Move on to next song

---

**The goal isn't perfection - it's improvement. Each iteration teaches you something. Keep going!** 🎵

---

*Last updated: January 2026*
