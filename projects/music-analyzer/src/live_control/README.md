# Live Control - AI Coaching Pipeline

Session state management and coaching utilities for Claude Code to interact with Ableton Live via MCP.

## Overview

The Live Control module provides the infrastructure for an AI coaching pipeline that:

1. **Analyzes** Ableton projects using ALS Doctor
2. **Compares** against professional reference profiles
3. **Resolves** track/device names to MCP indices
4. **Applies** parameter changes via MCP tools
5. **Tracks** all changes for undo/redo
6. **Enables** A/B comparison of fixes

## Architecture

```
                    +----------------+
                    |  Claude Code   |
                    +--------+-------+
                             |
              +--------------+--------------+
              |              |              |
    +---------v----+  +------v------+  +----v--------+
    | Reference    |  | Device      |  | Session     |
    | Integration  |  | Resolver    |  | State       |
    +---------+----+  +------+------+  +----+--------+
              |              |              |
              +--------------+--------------+
                             |
                    +--------v-------+
                    |   MCP Server   |
                    +--------+-------+
                             |
                    +--------v-------+
                    |  Ableton Live  |
                    +----------------+
```

## Modules

### state.py - Session State Management

Tracks all changes made during a coaching session with full undo/redo support.

```python
from live_control import get_tracker, record_change, Change

# Get or create session tracker
tracker = get_tracker()
tracker.set_song("My Project")

# Record a parameter change
record_change(Change(
    track_index=1,
    track_name="Bass",
    device_index=0,
    device_name="EQ Eight",
    parameter_index=2,
    parameter_name="Band 1 Gain",
    previous_value=0.5,
    new_value=0.3,
    description="Reduce bass 200Hz by 3dB",
    change_type="parameter"
))

# Undo/Redo
if tracker.can_undo:
    undo = tracker.get_undo()
    print(f"Undo: {undo.description}")
    # Apply previous_value via MCP
    tracker.confirm_undo()

# A/B Comparison
tracker.start_ab(
    description="EQ fix comparison",
    track_index=1,
    original_value=0.5,
    fix_value=0.3
)
tracker.toggle_ab()  # Switch between A and B
tracker.end_ab('B')  # Keep the fix
```

**Features**:
- File-based persistence (`~/.claude_ableton_session.json`)
- Full change history with undo/redo stacks
- A/B comparison state machine
- Session survives conversation restarts

### resolver.py - Device Resolution

Maps human-readable track/device/parameter names to numeric indices for MCP.

```python
from live_control import get_resolver, DeviceResolver

resolver = get_resolver()

# Load from MCP JSON responses
resolver.load_tracks_from_mcp(tracks_json)
resolver.load_devices_from_mcp(track_index, devices_json)
resolver.load_parameters_from_mcp(track_index, device_index, params_json)

# Or load from ALS Doctor JSON
resolver.load_from_als_doctor(als_doctor_data)

# Resolve names to indices
track_idx = resolver.resolve_track("Bass")  # Returns 1
device_idx = resolver.resolve_device(1, "EQ Eight")  # Returns 0
param_idx = resolver.resolve_parameter(1, 0, "Band 1 Gain")  # Returns 2

# Resolve a complete fix specification
resolved = resolver.resolve_fix({
    'track_name': 'Bass',
    'device_name': 'EQ Eight',
    'parameter_name': 'Band 1 Gain',
    'value': 0.3
})
# Returns ResolvedFix with track_index, device_index, parameter_index, value
```

**Features**:
- Case-insensitive matching
- Fuzzy matching for similar names (0.8 threshold)
- Caches lookups for performance
- Works with both MCP JSON and ALS Doctor output

### conversions.py - Value Conversions

Converts human-readable values (Hz, dB, ms) to normalized 0.0-1.0 format for MCP.

```python
from live_control import (
    hz_to_normalized, normalized_to_hz,
    db_to_normalized, normalized_to_db,
    ms_to_normalized, normalized_to_ms,
    convert_to_normalized, convert_from_normalized
)

# Frequency (logarithmic scale, 10Hz - 22kHz)
norm = hz_to_normalized(1000)  # ~0.58
hz = normalized_to_hz(0.58)    # ~1000

# Decibels (linear scale, -15dB to +15dB)
norm = db_to_normalized(-6)    # 0.3
db = normalized_to_db(0.3)     # -6.0

# Milliseconds (logarithmic scale, 0.1ms - 5000ms)
norm = ms_to_normalized(100)   # ~0.52
ms = normalized_to_ms(0.52)    # ~100

# Auto-detection based on parameter name
norm, unit = convert_to_normalized(1000, "Low Frequency")  # ('0.58', 'Hz')
value, unit = convert_from_normalized(0.5, "Attack Time")  # (30, 'ms')
```

**Supported Types**:
- Frequency (Hz) - logarithmic 10-22000 Hz
- Gain (dB) - linear -15 to +15 dB
- Time (ms) - logarithmic 0.1-5000 ms
- Ratio - linear 1:1 to 20:1
- Percentage - linear 0-100%

### reference_integration.py - Reference Profile Integration

Compares user tracks against professional reference profiles.

```python
from live_control import get_reference_integration, GapAnalysis

integration = get_reference_integration()

# Load reference profile
integration.load_profile("trance_reference.json")
# Or from dict
integration.load_profile_dict(profile_data)

# Analyze user track against reference
user_metrics = {
    'integrated_lufs': -10.0,
    'bass_energy': 0.25,
    'stereo_width': 0.65
}

gaps = integration.analyze_gaps(user_metrics, "My Track")

print(f"In range: {gaps.in_range_count}/{gaps.total_features}")
print(f"Issues found: {gaps.gap_count}")

# Get prioritized issues (worst first)
for gap in gaps.get_prioritized_gaps(3):
    print(f"{gap.feature_name}: {gap.severity}")
    print(f"  Current: {gap.user_value}, Target: {gap.target_value}")
    print(f"  Fix: {gap.fix_suggestion}")
```

**Severity Levels**:
- `good` - Within acceptable range
- `minor` - 0.5-1.0 standard deviations
- `moderate` - 1.0-2.0 standard deviations
- `significant` - 2.0-3.0 standard deviations
- `critical` - >3.0 standard deviations

### errors.py - Error Handling

Structured error handling with recovery suggestions.

```python
from live_control import (
    CoachingError, ErrorCategory, RecoveryAction,
    track_not_found, device_not_found, mcp_timeout,
    format_manual_instructions, can_retry, get_error_handler
)

# Create structured errors
error = track_not_found("NonExistent", ["Kick", "Bass", "Lead"])
print(error.message)        # "Track 'NonExistent' not found in Ableton"
print(error.recovery_hint)  # "The track may have been renamed..."

# Check if retriable
if can_retry(error):
    # Retry the operation
    pass

# Generate manual fallback instructions
instructions = format_manual_instructions(
    operation="reduce bass EQ",
    track_name="Bass",
    device_name="EQ Eight",
    parameter_name="Band 1 Gain",
    display_value="-3dB"
)
```

**Error Categories**:
- `CONNECTION` - Ableton/OSC connection issues
- `RESOLUTION` - Track/device/parameter not found
- `MCP` - MCP tool failures
- `ANALYSIS` - Audio/ALS analysis failures
- `REFERENCE` - Reference profile issues
- `STATE` - Session state issues
- `VALIDATION` - Invalid input/values
- `INTERNAL` - Unexpected errors

**Recovery Actions**:
- `RETRY` - Try operation again
- `REFRESH` - Refresh caches/state
- `RECONNECT` - Reconnect to Ableton
- `MANUAL` - Provide manual instructions
- `SKIP` - Skip this operation
- `ABORT` - Cannot recover

## Installation

The module is part of the music-analyzer project:

```bash
cd projects/music-analyzer/src
```

No additional dependencies beyond standard library.

## Testing

```bash
# Unit tests
python -m live_control.test_resolver
python -m live_control.test_reference
python -m live_control.test_integration

# Or run directly
cd src/live_control
python test_resolver.py
python test_reference.py
python test_integration.py
```

See [TESTING.md](TESTING.md) for manual testing checklist.

## Usage with Claude Code

### Typical Coaching Flow

1. **Load Project Analysis**
   ```python
   # From ALS Doctor JSON
   resolver = get_resolver()
   resolver.load_from_als_doctor(als_analysis)
   ```

2. **Compare to Reference**
   ```python
   integration = get_reference_integration()
   integration.load_profile("genre_reference.json")
   gaps = integration.analyze_gaps(audio_features, "Project")
   ```

3. **Get Top Issues**
   ```python
   for gap in gaps.get_prioritized_gaps(3):
       print(f"{gap.severity}: {gap.description}")
       print(f"Suggestion: {gap.fix_suggestion}")
   ```

4. **Resolve and Apply Fix**
   ```python
   resolved = resolver.resolve_fix({
       'track_name': gap.affected_track,
       'device_name': 'EQ Eight',
       'parameter_name': 'Band 1 Gain',
       'value': db_to_normalized(-3)
   })

   # Record for undo
   record_change(Change(
       track_index=resolved.track_index,
       # ... other fields
   ))

   # Apply via MCP
   mcp.set_device_parameter(
       resolved.track_index,
       resolved.device_index,
       resolved.parameter_index,
       resolved.value
   )
   ```

5. **A/B Compare**
   ```python
   tracker.start_ab("EQ fix", track_index, original, fix_value)
   # User listens...
   tracker.toggle_ab()  # Switch A/B
   # User decides...
   tracker.end_ab('B')  # Keep fix
   ```

## Version History

- **1.2.0** - Added reference integration, error handling
- **1.1.0** - Added DeviceResolver, value conversions
- **1.0.0** - Initial session state management
