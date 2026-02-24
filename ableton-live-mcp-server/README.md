# Ableton Live MCP Server

MCP (Model Context Protocol) server enabling Claude Code to control Ableton Live via OSC.

## Overview

This server bridges Claude Code with Ableton Live, allowing real-time parameter control for mixing assistance.

## Setup

### Prerequisites

- Ableton Live 11+ with AbletonOSC installed
- Python 3.9+

### Installation

```bash
pip install python-osc
```

### Running

1. **Start OSC Daemon** (keep running in separate terminal):
   ```bash
   python osc_daemon.py
   ```

2. **Configure Ableton**:
   - Preferences → Link/Tempo/MIDI → Control Surface
   - Enable AbletonOSC

3. **Test Connection**:
   Ask Claude: "Get track names from Ableton"

## Available MCP Tools

All tools return JSON for reliable parsing.

### Track Operations

| Tool | Description |
|------|-------------|
| `get_track_names` | List all tracks with indices |
| `get_track_volume` | Get track volume (normalized 0.0-1.0) |
| `set_track_volume` | Set track volume |
| `get_track_pan` | Get track pan (-1.0 to 1.0) |
| `set_track_pan` | Set track pan |
| `get_track_mute` | Get mute state |
| `set_track_mute` | Set mute state |

### Device Operations

| Tool | Description |
|------|-------------|
| `get_device_list` | List devices on a track |
| `get_device_parameters` | List parameters for a device |
| `get_device_parameter` | Get parameter value |
| `set_device_parameter` | Set parameter value |
| `get_device_enabled` | Get device on/off state |
| `set_device_enabled` | Enable/disable device |

### Send Operations

| Tool | Description |
|------|-------------|
| `get_send_value` | Get send level |
| `set_send_value` | Set send level |

### Transport

| Tool | Description |
|------|-------------|
| `get_tempo` | Get project tempo |
| `set_tempo` | Set project tempo |

## JSON Response Format

All tools return structured JSON:

```json
{
  "success": true,
  "track_index": 0,
  "volume": 0.85
}
```

Error responses:

```json
{
  "success": false,
  "error": "Track not found"
}
```

## Integration with Live Control

The MCP server works with the Live Control coaching pipeline:

1. **DeviceResolver** loads track/device structure from MCP responses
2. **Session State** tracks all parameter changes for undo/redo
3. **Value Conversions** translate dB/Hz to normalized values
4. **Reference Integration** compares against professional profiles

### Example Flow

```python
# 1. Get tracks from MCP
tracks_json = mcp.get_track_names()

# 2. Load into DeviceResolver
from live_control import get_resolver
resolver = get_resolver()
resolver.load_tracks_from_mcp(tracks_json)

# 3. Resolve a fix
resolved = resolver.resolve_fix({
    'track_name': 'Bass',
    'device_name': 'EQ Eight',
    'parameter_name': 'Band 1 Gain',
    'value': 0.4
})

# 4. Apply via MCP
mcp.set_device_parameter(
    resolved.track_index,
    resolved.device_index,
    resolved.parameter_index,
    resolved.value
)

# 5. Record for undo
from live_control import record_change, Change
record_change(Change(
    track_index=resolved.track_index,
    track_name=resolved.track_name,
    previous_value=old_value,
    new_value=resolved.value,
    description="Reduce bass EQ"
))
```

## Troubleshooting

### Connection Timeout

- Ensure Ableton is running and AbletonOSC is active
- Restart the OSC daemon
- Check firewall settings

### Track Not Found

- Refresh track list with `get_track_names`
- Use DeviceResolver fuzzy matching for similar names

### Device Not Found

- Get fresh device list with `get_device_list`
- Rack-nested devices may not be accessible

## Limitations

- Cannot create/delete tracks or devices
- Cannot edit MIDI clips
- Cannot draw automation
- Rack-nested devices have limited support
- One parameter change at a time (no batching)

## Related Documentation

- [Live Control README](../projects/music-analyzer/src/live_control/README.md)
- [Live Control Testing](../projects/music-analyzer/src/live_control/TESTING.md)
- [CLAUDE.md](../CLAUDE.md) - Main project instructions
