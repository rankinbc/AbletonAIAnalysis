# Live Control Testing Checklist

Manual testing guide for the AI Coaching Pipeline with Ableton Live.

## Prerequisites

- [ ] Ableton Live running with project open
- [ ] AbletonOSC installed and active
- [ ] OSC daemon running (`python osc_daemon.py`)
- [ ] MCP server available

## Unit Tests

Run all unit tests before manual testing:

```bash
cd src/live_control
python test_resolver.py      # DeviceResolver tests
python test_reference.py     # Reference integration tests
python test_integration.py   # Integration tests
```

```bash
cd src
python test_als_json.py      # ALS JSON output tests
```

## Manual Test Scenarios

### 1. Track Resolution

**Goal**: Verify DeviceResolver correctly maps names to indices.

```python
from resolver import DeviceResolver, get_resolver

resolver = get_resolver()

# Load from MCP response
mcp_response = '{"success": true, "tracks": [{"index": 0, "name": "Kick"}, {"index": 1, "name": "Bass"}]}'
resolver.load_tracks_from_mcp(mcp_response)

# Test resolution
assert resolver.resolve_track("Kick") == 0
assert resolver.resolve_track("kick") == 0  # Case insensitive
assert resolver.resolve_track("Bass Line") == 1  # Fuzzy match
```

**Checklist**:
- [ ] Exact match works
- [ ] Case-insensitive match works
- [ ] Fuzzy match works for similar names
- [ ] Returns None for non-existent tracks

### 2. Device Resolution

**Goal**: Verify device chain resolution.

```python
# Load devices for track
devices_response = '{"success": true, "track_index": 0, "devices": [{"index": 0, "name": "EQ Eight"}, {"index": 1, "name": "Compressor"}]}'
resolver.load_devices_from_mcp(0, devices_response)

# Test resolution
assert resolver.resolve_device(0, "EQ Eight") == 0
assert resolver.resolve_device(0, "Compressor") == 1
```

**Checklist**:
- [ ] Device resolution works
- [ ] Multiple devices on same track work
- [ ] Device on different tracks resolve independently

### 3. Value Conversions

**Goal**: Verify value conversions round-trip correctly.

```python
from conversions import hz_to_normalized, normalized_to_hz, db_to_normalized, normalized_to_db

# Frequency
for hz in [100, 500, 1000, 5000]:
    norm = hz_to_normalized(hz)
    back = normalized_to_hz(norm)
    assert abs(hz - back) < 1

# Decibels
for db in [-12, -6, 0, 6, 12]:
    norm = db_to_normalized(db)
    back = normalized_to_db(norm)
    assert abs(db - back) < 0.1
```

**Checklist**:
- [ ] Hz conversions round-trip within 1 Hz
- [ ] dB conversions round-trip within 0.1 dB
- [ ] ms conversions round-trip correctly
- [ ] Auto-detection identifies parameter types

### 4. Reference Gap Analysis

**Goal**: Verify gap analysis against reference profiles.

```python
from reference_integration import get_reference_integration

integration = get_reference_integration()
integration.load_profile("path/to/reference_profile.json")

user_metrics = {
    'integrated_lufs': -10.0,
    'bass_energy': 0.25,
    'stereo_width': 0.6
}

gaps = integration.analyze_gaps(user_metrics, "My Track")
print(f"Total gaps: {gaps.gap_count}")
print(f"In range: {gaps.in_range_count}")

for gap in gaps.get_prioritized_gaps(3):
    print(f"{gap.feature_name}: {gap.severity} - {gap.fix_suggestion}")
```

**Checklist**:
- [ ] Profile loads correctly
- [ ] Gap analysis identifies issues
- [ ] Severity levels are appropriate
- [ ] Fix suggestions are generated
- [ ] Prioritization works (critical first)

### 5. Session Persistence

**Goal**: Verify changes persist across sessions.

```python
from state import get_tracker, record_change, Change

tracker = get_tracker()
tracker.set_song("Test Song")

# Record a change
record_change(Change(
    track_index=0,
    track_name="Kick",
    previous_value=0.85,
    new_value=0.7,
    description="Reduce kick volume",
    change_type="volume"
))

# Close and reopen
tracker2 = get_tracker()  # Should load from file
assert tracker2.song_name == "Test Song"
assert tracker2.change_count == 1
```

**Checklist**:
- [ ] Changes persist to file
- [ ] Song name persists
- [ ] Undo/redo state persists
- [ ] Session survives restart

### 6. A/B Comparison

**Goal**: Verify A/B comparison workflow.

```python
tracker.start_ab(
    description="Test EQ change",
    track_index=0,
    original_value=0.5,
    fix_value=0.3,
    device_index=0,
    parameter_index=1
)

assert tracker.is_comparing
assert tracker.ab_state.current_state == 'B'

tracker.toggle_ab()
assert tracker.ab_state.current_state == 'A'

change = tracker.end_ab('B')  # Keep the fix
assert change is not None
assert tracker.change_count >= 1
```

**Checklist**:
- [ ] Start A/B creates comparison state
- [ ] Toggle switches between A and B
- [ ] End with 'B' records change
- [ ] End with 'A' discards fix

### 7. Error Handling

**Goal**: Verify error recovery suggestions.

```python
from errors import track_not_found, can_retry, format_manual_instructions

error = track_not_found("NonExistent", ["Kick", "Bass", "Lead"])
print(error)

assert can_retry(error)  # REFRESH action is retriable

instructions = format_manual_instructions(
    operation="reduce bass",
    track_name="Bass",
    device_name="EQ Eight",
    parameter_name="Band 1 Gain",
    value=0.4,
    display_value="-3dB"
)
print(instructions)
```

**Checklist**:
- [ ] Errors include recovery hints
- [ ] Manual instructions are clear
- [ ] Retriable errors identified correctly

### 8. ALS Doctor JSON Output

**Goal**: Verify JSON output for DeviceResolver.

```bash
cd projects/music-analyzer
python als_doctor.py diagnose path/to/project.als --format json --output report.json
```

```python
import json
from live_control.resolver import DeviceResolver

with open('report.json') as f:
    data = json.load(f)

resolver = DeviceResolver()
resolver.load_from_als_doctor(data)

# Should have tracks and devices loaded
assert resolver.track_count > 0
```

**Checklist**:
- [ ] JSON output is valid JSON
- [ ] Tracks have index and name
- [ ] Devices have index, name, type
- [ ] DeviceResolver can load output
- [ ] Health metrics included

## Integration Test with Ableton

### Full Coaching Flow

1. **Analyze Project**
   ```bash
   python als_doctor.py diagnose "path/to/project.als" --format json --output analysis.json
   ```

2. **Load into Resolver**
   ```python
   resolver = get_resolver()
   with open('analysis.json') as f:
       resolver.load_from_als_doctor(json.load(f))
   ```

3. **Compare to Reference**
   ```python
   integration = get_reference_integration()
   integration.load_profile('reference.json')
   gaps = integration.analyze_gaps(user_metrics, "My Project")
   ```

4. **Generate Fix**
   ```python
   # Get top issue
   top_gap = gaps.get_prioritized_gaps(1)[0]

   # Resolve fix
   fix = resolver.resolve_fix({
       'track_name': 'Bass',
       'device_name': 'EQ Eight',
       'parameter_name': 'Band 1 Gain',
       'value': db_to_normalized(-3)
   })
   ```

5. **Apply via MCP** (would use actual MCP tools)
   ```python
   # mcp.set_device_parameter(fix.track_index, fix.device_index, fix.parameter_index, fix.value)
   ```

6. **Record for Undo**
   ```python
   record_change(Change(
       track_index=fix.track_index,
       track_name=fix.track_name,
       device_index=fix.device_index,
       device_name=fix.device_name,
       parameter_index=fix.parameter_index,
       parameter_name=fix.parameter_name,
       previous_value=old_value,
       new_value=fix.value,
       description="Fix bass EQ"
   ))
   ```

7. **A/B Compare**
   - Toggle between original and fix
   - Listen for difference
   - Keep or discard

8. **Undo if needed**
   ```python
   undo = tracker.get_undo()
   # mcp.set_device_parameter(..., undo.previous_value)
   tracker.confirm_undo()
   ```

## Troubleshooting

### Common Issues

**Track not found**
- Refresh track list from Ableton
- Check for renamed tracks
- Try fuzzy matching

**Device not found**
- Ensure device is in track's device chain
- Check for rack-nested devices (not supported)
- Verify device name spelling

**MCP timeout**
- Check OSC daemon is running
- Verify Ableton is responsive
- Retry after brief wait

**Invalid value**
- Check parameter ranges
- Ensure normalized 0.0-1.0 format
- Use conversion utilities

### Debug Mode

Enable verbose error handling:
```python
from errors import get_error_handler
handler = get_error_handler(verbose=True)
```

## Performance Notes

- DeviceResolver caches track/device lookups
- Reference profiles are loaded once per session
- Session state persists to reduce round-trips
- Batch multiple parameter changes when possible
