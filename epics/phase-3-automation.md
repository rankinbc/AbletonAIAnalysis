# Epic: Phase 3 - Automation

**Goal:** Reduce friction by automating analysis, providing guided workflows, and exploring direct Ableton integration.

**Dependencies:** Phase 1 (Foundation) complete

**Unlocks:** Hands-off operation, faster iteration cycles

---

## Strategic Context

Automation has three tiers of complexity:

1. **Safe automation** - Watch folders, scheduled scans (low risk)
2. **Guided automation** - CLI tells you what to do next (medium risk)
3. **Active automation** - System controls Ableton directly (high risk, high reward)

Build tiers 1 and 2 fully. Explore tier 3 with clear experimental boundaries.

---

## Stories

### Story 3.1: Watch Folder for Auto-Analysis

**As a** music producer
**I want to** have my projects analyzed automatically when I save them
**So that** I get instant feedback without running commands

**Acceptance Criteria:**
- [ ] `als-doctor watch <folder>` monitors folder for .als changes
- [ ] Triggers `diagnose --save` when .als file is modified
- [ ] Debounce: waits 5 seconds after last change before analyzing (configurable)
- [ ] Shows notification in terminal when analysis completes
- [ ] Logs results to `data/watch.log`
- [ ] `--quiet` flag for minimal output
- [ ] `--debounce N` to set wait time in seconds
- [ ] `Ctrl+C` gracefully stops watching
- [ ] Ignores Ableton backup files (Backup/*.als)

**Example Output:**
```
WATCHING: D:\Ableton Projects
Press Ctrl+C to stop

[14:32:05] Detected change: 22 Project\22_3.als
[14:32:10] Analyzing...
[14:32:12] Result: 88/100 [A] (was 85, +3)
           2 issues fixed, 1 new warning

[14:45:22] Detected change: 35 Project\35_2.als
[14:45:27] Analyzing...
[14:45:29] Result: 72/100 [B] (new project)
           5 issues detected

[15:01:03] Ignored: 22 Project\Backup\22_3.als (backup file)
```

**Technical Notes:**
- Use `watchdog` library for cross-platform file monitoring
- Filter for .als files only, exclude Backup/ folders
- Debounce to avoid analyzing during Ableton autosave bursts
- Store watch session events in DB for history

**Effort:** Medium
**Risk:** Low
**Dependencies:** Phase 1 (--save functionality)

---

### Story 3.2: Guided Workflow Mode (CLI Coach)

**As a** music producer
**I want to** be told exactly what to do next
**So that** I don't have to decide what to fix

**Acceptance Criteria:**
- [ ] `als-doctor coach <file>` enters guided mode
- [ ] Shows top issue with specific fix instructions
- [ ] After user confirms fix, re-analyzes and shows next issue
- [ ] Tracks progress within session (issues fixed, skipped)
- [ ] `--auto-check` re-analyzes every N seconds while waiting
- [ ] Celebrates when health improves (positive reinforcement)
- [ ] Exits when no critical/warning issues remain or user quits
- [ ] Session summary at end showing total improvement

**Example Session:**
```
COACH MODE: 22_3.als
Starting health: 72/100 [B]
Target: 80+ [A]

==================================================
STEP 1 of 5: Fix Bass Compressor

ISSUE: Compressor ratio at 20:1 (too aggressive)
SEVERITY: Critical
IMPACT: Likely +5-10 health points

ACTION:
  1. Open 22_3.als in Ableton
  2. Go to "Bass" track
  3. Find Compressor2 device
  4. Change Ratio from 20:1 to 4:1
  5. Save the project (Ctrl+S)

Press [Enter] when done, [S] to skip, [Q] to quit: _

[User presses Enter]

Re-analyzing... Done!
Health: 72 -> 78 (+6) Nice!
Issue FIXED.

==================================================
STEP 2 of 4: Remove Duplicate EQ...

[... continues ...]

==================================================
SESSION COMPLETE!

Started: 72/100 [B]
Finished: 91/100 [A]
Improvement: +19 points

Fixed: 4 issues
Skipped: 1 issue
Time: 12 minutes

Great work! Your project is now Grade A.
```

**Technical Notes:**
- Interactive CLI session using `input()` or `prompt_toolkit`
- Re-run diagnose after each step
- Track skipped issues in session state (don't re-suggest)
- Save session summary to DB
- Integrate with Phase 2 smart recommendations if available

**Effort:** Medium
**Risk:** Low
**Dependencies:** Phase 1, Phase 2 (smart recommendations enhance this)

---

### Story 3.3: Scheduled Batch Scan

**As a** music producer
**I want to** schedule regular scans of my project library
**So that** my database stays current without manual effort

**Acceptance Criteria:**
- [ ] `als-doctor schedule add <folder> --daily` sets up daily scan
- [ ] `als-doctor schedule add <folder> --weekly --day sunday` weekly scan
- [ ] `als-doctor schedule add <folder> --hourly` for active development
- [ ] `als-doctor schedule list` shows all scheduled tasks
- [ ] `als-doctor schedule remove <id>` removes scheduled task
- [ ] `als-doctor schedule run <id>` manually triggers scheduled task
- [ ] Uses OS task scheduler (Windows Task Scheduler)
- [ ] Logs summary to `data/scheduled_runs.log`
- [ ] `--notify` option for Windows toast notification on completion

**Example:**
```
> als-doctor schedule add "D:\Ableton Projects" --weekly --day sunday

Scheduled weekly scan:
  Folder: D:\Ableton Projects
  Day: Sunday
  Time: 03:00
  Task ID: scan_weekly_001

Created Windows Task Scheduler entry.

> als-doctor schedule list

SCHEDULED TASKS:

ID                 Folder                    Schedule        Last Run
---------------------------------------------------------------------------
scan_weekly_001    D:\Ableton Projects       Sun 03:00       2026-01-19
scan_daily_002     D:\WIP Projects           Daily 06:00     2026-01-25

> als-doctor schedule remove scan_daily_002

Removed schedule: scan_daily_002
Deleted Windows Task Scheduler entry.
```

**Technical Notes:**
- Windows: Use `schtasks` command to create/delete tasks
- Store schedule config in `data/schedules.json`
- Create wrapper batch script that runs `als-doctor scan --save`
- Parse Task Scheduler XML for last run time

**Effort:** Medium
**Risk:** Low
**Dependencies:** Phase 1 (scan --save)

---

### Story 3.4: Pre-Export Checklist

**As a** music producer
**I want to** verify my project is ready before exporting
**So that** I don't waste time exporting a problematic mix

**Acceptance Criteria:**
- [ ] `als-doctor preflight <file>` runs comprehensive pre-export check
- [ ] Checks: health score, critical issues, export-specific problems
- [ ] Returns exit code 0 (ready) or 1 (not ready) for scripting
- [ ] `--strict` mode requires Grade A (80+)
- [ ] `--min-score N` sets custom minimum score
- [ ] Shows clear GO / NO-GO verdict with reasoning
- [ ] Lists optional cleanup items separately from blockers

**Export-Specific Checks:**
- Limiter ceiling (should be <= -0.3dB)
- No bypassed master effects that should be on
- No solo'd tracks
- No muted master
- Sample rate consistency (if detectable)

**Example Output (PASS):**
```
PREFLIGHT CHECK: 22_2.als

[PASS] Health Score: 92/100 [A]
[PASS] No critical issues
[PASS] No clipping risk (limiter ceiling: -0.3dB)
[PASS] No solo'd tracks
[PASS] Master not muted
[WARN] 3 disabled devices (cleanup recommended)

==================================================
VERDICT: GO FOR EXPORT

Optional cleanup before export:
  - Delete 3 disabled devices to reduce CPU load
```

**Example Output (FAIL):**
```
PREFLIGHT CHECK: 38b_5.als

[FAIL] Health Score: 24/100 [D] (minimum: 60)
[FAIL] 2 critical issues must be fixed
[FAIL] Limiter ceiling at 0.0dB (clipping risk!)
[WARN] Track "Lead" is solo'd (intentional?)
[PASS] Master not muted

==================================================
VERDICT: NOT READY FOR EXPORT

Must fix before exporting:
  1. [CRITICAL] Bass: Limiter should be last in chain
  2. [CRITICAL] Lead: Compressor ratio at infinity
  3. [BLOCKING] Reduce limiter ceiling to -0.3dB or lower

Warnings to review:
  4. [WARNING] "Lead" track is solo'd - disable solo before export
```

**Technical Notes:**
- Extend diagnose with export-specific checks
- Parse solo/mute states from .als XML
- Exit codes for CI/scripting integration

**Effort:** Small
**Risk:** Low
**Dependencies:** Phase 1 (diagnose)

---

### Story 3.5: AbletonOSC Integration (Experimental)

**As a** music producer
**I want to** query Ableton's live state from the analysis tool
**So that** I can see real-time information without exporting

**Acceptance Criteria:**
- [ ] `als-doctor osc connect` establishes OSC connection to Ableton
- [ ] `als-doctor osc status` shows connection state and Ableton info
- [ ] `als-doctor osc tracks` lists current tracks with device counts
- [ ] `als-doctor osc devices <track>` lists devices on a track
- [ ] `als-doctor osc param <track> <device> <param>` reads parameter value
- [ ] Read-only operations only (no writes in this story)
- [ ] Clear documentation for AbletonOSC setup requirements
- [ ] Graceful error messages if Ableton not running or OSC not installed
- [ ] `--timeout N` for connection timeout

**Example Output:**
```
> als-doctor osc connect

Connecting to Ableton via OSC (localhost:11000)...
[OK] Connected to Ableton Live 11.3.4
[OK] AbletonOSC detected

Current Session:
  Project: 22_3.als
  Tracks: 12
  Tempo: 140 BPM
  Playing: No

> als-doctor osc tracks

LIVE TRACKS (12):

  #   Name            Type    Devices  Armed  Solo  Mute
  --------------------------------------------------------
  1   Kick            Audio   3        -      -     -
  2   Bass            MIDI    4        -      -     -
  3   Lead            MIDI    6        -      Yes   -
  4   Pad             MIDI    2        -      -     -
  ...

> als-doctor osc devices 2

DEVICES ON "Bass":

  #   Name           Type          On/Off
  -----------------------------------------
  1   EQ Eight       AudioEffect   ON
  2   Compressor     AudioEffect   ON
  3   Saturator      AudioEffect   OFF
  4   Utility        AudioEffect   ON
```

**Technical Notes:**
- Requires user to install AbletonOSC from GitHub
- Use `python-osc` library for communication
- Default ports: send 11000, receive 11001
- Document compatible Ableton versions (11.x)
- Start read-only; write operations in Story 3.6

**Effort:** Large
**Risk:** High (external dependency, version compatibility)
**Dependencies:** None (standalone experimental feature)

---

### Story 3.6: Quick Actions via OSC (Experimental)

**As a** music producer
**I want to** apply simple fixes directly from the CLI
**So that** I can fix issues without switching to Ableton

**Acceptance Criteria:**
- [ ] `als-doctor osc fix <issue-id>` applies fix via OSC
- [ ] Only "safe" fixes supported initially:
  - Delete disabled device
  - Toggle device on/off
  - Adjust numeric parameter within safe range
- [ ] Always requires confirmation before applying (no --force)
- [ ] Shows before/after state in terminal
- [ ] `--dry-run` shows what would change without applying
- [ ] Maintains audit log of all OSC changes in `data/osc_audit.log`
- [ ] Integrates with coach mode (Story 3.2) for seamless flow

**Safe Operations Whitelist:**
- Delete device (only if currently OFF)
- Set parameter to specific value (within defined safe ranges)
- Toggle device bypass

**Forbidden Operations:**
- Delete enabled devices
- Delete tracks
- Any destructive action without explicit user confirmation

**Example:**
```
> als-doctor coach 22_3.als --live

Connected to Ableton via OSC.

STEP 1: Remove disabled Saturator on Bass

ISSUE: Disabled device adds clutter
DEVICE: Bass -> Saturator (currently OFF)

[A] Apply fix automatically via OSC
[M] I'll fix it manually in Ableton
[S] Skip this issue
[Q] Quit

Choice: A

Are you sure you want to delete "Saturator" from "Bass"? [y/N]: y

Applying fix via OSC...
[OK] Deleted "Saturator" from "Bass" track
[OK] Change logged to osc_audit.log

Waiting for Ableton to save... (Ctrl+S in Ableton)
[OK] Project saved detected

Re-analyzing... Health: 72 -> 75 (+3)
```

**Technical Notes:**
- Strict whitelist of allowed operations
- Confirmation required for every write operation
- Audit log format: timestamp, operation, track, device, before, after, user_confirmed
- Coach mode integration: detect --live flag, offer OSC options

**Effort:** Large
**Risk:** High (modifies user's live project)
**Dependencies:** Story 3.5 (OSC connection established)

---

## Summary

| Story | Description | Effort | Risk | Dependencies |
|-------|-------------|--------|------|--------------|
| 3.1 | Watch Folder | Medium | Low | Phase 1 |
| 3.2 | Coach Mode | Medium | Low | Phase 1 |
| 3.3 | Scheduled Scan | Medium | Low | Phase 1 |
| 3.4 | Preflight Check | Small | Low | Phase 1 |
| 3.5 | OSC Connect (Experimental) | Large | High | None |
| 3.6 | OSC Quick Actions (Experimental) | Large | High | 3.5 |

---

## Implementation Order

**Recommended sequence:**

1. **3.4 Preflight Check** (Small, immediate value)
2. **3.1 Watch Folder** (Medium, high convenience)
3. **3.2 Coach Mode** (Medium, high engagement)
4. **3.3 Scheduled Scan** (Medium, "set and forget")
5. **3.5 OSC Connect** (Large, experimental - assess feasibility)
6. **3.6 OSC Quick Actions** (Large, experimental - only if 3.5 stable)

**Safe to ship:** 3.1, 3.2, 3.3, 3.4
**Experimental (label clearly):** 3.5, 3.6

---

## CLI Command Summary

```
# Safe Automation
als-doctor watch <folder> [--quiet] [--debounce N]
als-doctor coach <file> [--auto-check N]
als-doctor schedule add <folder> --daily|--weekly|--hourly
als-doctor schedule list
als-doctor schedule remove <id>
als-doctor schedule run <id>
als-doctor preflight <file> [--strict] [--min-score N]

# Experimental (OSC)
als-doctor osc connect [--timeout N]
als-doctor osc status
als-doctor osc tracks
als-doctor osc devices <track>
als-doctor osc param <track> <device> <param>
als-doctor osc fix <issue-id> [--dry-run]
```

---

## External Dependencies

### AbletonOSC (for Stories 3.5, 3.6)

- **Repository:** https://github.com/ideoforms/AbletonOSC
- **Compatibility:** Ableton Live 11.x (verify 12.x support)
- **Installation:** User must install manually into Ableton's MIDI Remote Scripts
- **Risk:** External project, may break with Ableton updates

### Python Libraries

- `watchdog` - File system monitoring (3.1)
- `python-osc` - OSC communication (3.5, 3.6)
- Both are stable, well-maintained libraries
